import test from 'node:test';
import assert from 'node:assert/strict';
import { fromKey, dateKey, feedDateKey, uniqueMatches, flattenFeed, isLive, normalizeName, LEAGUES } from '../src/data.js';

test('validates local calendar dates (including overflow)', () => {
  assert.equal(dateKey(fromKey('2026-10-30')), '2026-10-30');
  assert.equal(fromKey('2026-02-30'), null);
  assert.equal(fromKey('not-a-date'), null);
});
test('parses Polish dates', () => {
  assert.equal(feedDateKey('03.10.2026'), '2026-10-03');
  assert.equal(feedDateKey('unknown'), '');
});
test('keeps a final result rather than a scheduled duplicate', () => {
  const base = { date: '30.10.2026', time: '18:00', home: 'Team A', away: 'Team B' };
  const matches = uniqueMatches([{ ...base, status: 'scheduled' }, { ...base, status: 'finished', home_sets: 3, away_sets: 1 }]);
  assert.equal(matches.length, 1);
  assert.equal(matches[0].home_sets, 3);
});
test('flattens second-league groups without mutating the feed', () => {
  const source = { groups: [{ name: 'Grupa 1', teams: [{ name: 'ABC' }], matches: [{ home: 'ABC', away: 'DEF' }] }] };
  const flattened = flattenFeed(source, 'second');
  assert.equal(flattened.matches[0].group, 'Grupa 1');
  assert.equal(flattened.teams.length, 1);
  assert.equal(source.matches, undefined);
});
test('scheduled matches are not automatically classified as live', () => {
  assert.equal(isLive({ status: 'scheduled', home_sets: 0, away_sets: 0 }), false);
});

test('Japanese team names stay unique in same-time fixtures', () => {
  assert.notEqual(normalizeName('ヴォレアス'), normalizeName('サントリー'));
  assert.notEqual(normalizeName('ガンバ'), normalizeName('カンバ'));
  assert.ok(normalizeName('ヴォレアス').length > 0);
  const base = { date: '07.11.2026', time: '05:35', status: 'scheduled' };
  assert.equal(uniqueMatches([
    { ...base, home: 'ヴォレアス', away: 'F鹿児島' },
    { ...base, home: '松本TD', away: 'サントリー' }
  ]).length, 2);
});

test('international leagues are available in distinct regions', () => {
  assert.equal(LEAGUES.find(item => item.id === 'italy').category, 'Europa');
  assert.equal(LEAGUES.find(item => item.id === 'japan').category, 'Świat');
});
