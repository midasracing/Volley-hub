import test from 'node:test';
import assert from 'node:assert/strict';
import { shareFeedValue } from '../src/feedUpdates.js';
import { fetchLeague, matchesFromFeeds, LEAGUES } from '../src/data.js';

const fixture = () => ({ updated_at: '2026-10-31T15:00:00Z', teams: [{ name: 'A', logo: '/a.svg' }], matches: [
  { id: 'live', date: '31.10.2026', time: '15:00', home: 'A', away: 'B', status: 'live', home_sets: 1, away_sets: 0, current_points: '20:19', set_scores: ['25:20'] },
  { id: 'next', date: '31.10.2026', time: '18:00', home: 'C', away: 'D', status: 'scheduled' }
] });

test('a live score update retains other cards, team logos and normalized match identities', () => {
  const previous = fixture();
  const oldViews = matchesFromFeeds({ men: previous });
  const incoming = fixture();
  incoming.matches[0].current_points = '21:19';
  const next = shareFeedValue(previous, incoming);
  assert.equal(previous.matches[0].current_points, '20:19');
  assert.equal(next.teams, previous.teams);
  assert.equal(next.matches[1], previous.matches[1]);
  assert.notEqual(next.matches[0], previous.matches[0]);
  const views = matchesFromFeeds({ men: next });
  assert.equal(views[1], oldViews[1]);
  assert.equal(views[0].current_points, '21:19');
});

test('finishing a live match removes stale fields even when the source timestamp is unchanged', () => {
  const previous = fixture(), incoming = fixture();
  Object.assign(incoming.matches[0], { status: 'finished', home_sets: 3, away_sets: 1 });
  delete incoming.matches[0].current_points;
  const next = shareFeedValue(previous, incoming);
  assert.equal(next.matches[0].status, 'finished');
  assert.equal(next.matches[0].home_sets, 3);
  assert.equal(Object.hasOwn(next.matches[0], 'current_points'), false);
  assert.equal(next.matches[1], previous.matches[1]);
});

test('schedule insertions and removals preserve unchanged matches by identity', () => {
  const previous = fixture();
  const incoming = fixture();
  incoming.matches.unshift({ id: 'new', home: 'E', away: 'F', date: '31.10.2026', time: '14:00' });
  const next = shareFeedValue(previous, incoming);
  assert.equal(next.matches[1], previous.matches[0]);
  assert.equal(next.matches[2], previous.matches[1]);
  const removed = shareFeedValue(next, fixture());
  assert.equal(removed.matches.length, 2);
  assert.equal(removed.matches[0], previous.matches[0]);
});

test('every poll reaches the source while identical snapshots avoid parsing and object churn', async t => {
  let payload = fixture();
  const calls = [];
  t.mock.method(globalThis, 'fetch', async (path, options) => {
    calls.push({ path, options });
    return new Response(JSON.stringify(payload));
  });
  const a = await fetchLeague(LEAGUES[0]);
  const b = await fetchLeague(LEAGUES[0]);
  assert.equal(a, b);
  payload = fixture();
  payload.matches[0].current_points = '22:19';
  const c = await fetchLeague(LEAGUES[0]);
  assert.equal(c.matches[1], a.matches[1]);
  assert.equal(c.matches[0].current_points, '22:19');
  assert.equal(c.teams, a.teams);
  assert.equal(calls.length, 3);
  assert.ok(calls.every(call => call.options.cache === 'no-store'));
});
