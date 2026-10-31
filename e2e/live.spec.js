import { test, expect } from '@playwright/test';

const match = (id, home, away) => ({ id, home, away, date: '31.10.2026', time: '15:00', status: 'live', home_sets: 1, away_sets: 0, current_points: '20:19', set_scores: ['25:20'] });
async function setup(page) {
  await page.clock.install({ time: new Date('2026-10-31T15:05:00Z') });
  await page.clock.pauseAt(new Date('2026-10-31T15:05:00Z'));
  const state = {
    payload: { updated_at: 'unchanged-timestamp', teams: [], matches: [match('live-one', 'A', 'B'), match('live-two', 'C', 'D')] },
    counts: {}, fail: false, hold: false, pending: null
  };
  await page.route('**/data/*.json', async route => {
    const file = new URL(route.request().url()).pathname.split('/').pop();
    state.counts[file] = (state.counts[file] || 0) + 1;
    if (file === 'tauron.json' && state.hold) {
      state.pending = route;
      return;
    }
    if (file === 'tauron.json' && state.fail) return route.fulfill({ status: 503, body: 'Unavailable' });
    return route.fulfill({ json: file === 'tauron.json' ? state.payload : { matches: [], teams: [], groups: [] } });
  });
  await page.goto('/#matches');
  await expect(page.locator('[data-route="matches"] [data-match-id="live-one"]')).toContainText('20:19');
  return state;
}
const card = (page, id) => page.locator(`[data-route="matches"] [data-match-id="${id}"]`);

test('live polls update changed cards only, retain expanded sets and detect completed/new matches', async ({ page }) => {
  const state = await setup(page);
  const stable = card(page, 'live-two');
  await stable.getByRole('button', { name: 'Pokaż sety' }).evaluate(el => el.click());
  await expect(stable.getByRole('button', { name: 'Ukryj sety' })).toHaveAttribute('aria-expanded', 'true');
  await stable.evaluate(el => {
    window.__stableCard = el;
    window.__stableMutations = 0;
    new MutationObserver(records => { window.__stableMutations += records.length; }).observe(el, { subtree: true, childList: true, characterData: true, attributes: true });
  });
  const otherRequests = state.counts['2liga.json'];
  state.payload.matches[0].current_points = '21:19';
  await page.clock.fastForward(10000);
  await expect(card(page, 'live-one')).toContainText('21:19');
  expect(state.counts['tauron.json']).toBe(2);
  expect(state.counts['2liga.json']).toBe(otherRequests);
  expect(await stable.evaluate(el => el === window.__stableCard && window.__stableMutations === 0)).toBe(true);
  await expect(stable.getByRole('button', { name: 'Ukryj sety' })).toHaveAttribute('aria-expanded', 'true');

  for (const item of state.payload.matches) Object.assign(item, { status: 'finished', home_sets: 3, away_sets: 1, current_points: null });
  await page.clock.fastForward(10000);
  await expect(card(page, 'live-one')).toContainText('Zakończony');
  await expect(card(page, 'live-one').locator('.im-pts')).toHaveText(['3', '1']);
  const afterFinish = state.counts['tauron.json'];
  await page.clock.fastForward(10000);
  expect(state.counts['tauron.json']).toBe(afterFinish);

  state.payload.matches.push(match('new-live', 'E', 'F'));
  await page.clock.fastForward(30000);
  await expect(card(page, 'new-live')).toContainText('NA ŻYWO');
  expect(state.counts['2liga.json']).toBe(otherRequests + 1);
});

test('failed live polls retain scores and recover without replacing cards', async ({ page }) => {
  const state = await setup(page);
  const target = await card(page, 'live-one').elementHandle();
  state.fail = true;
  await page.clock.fastForward(10000);
  await expect(page.locator('[data-route="matches"]').getByRole('alert')).toBeVisible();
  await expect(card(page, 'live-one')).toContainText('20:19');
  state.fail = false;
  state.payload.matches[0].current_points = '22:19';
  await page.clock.fastForward(10000);
  await expect(card(page, 'live-one')).toContainText('22:19');
  await expect(page.locator('[data-route="matches"]').getByRole('alert')).toHaveCount(0);
  expect(await target.evaluate(el => el === document.querySelector('[data-route="matches"] [data-match-id="live-one"]'))).toBe(true);
});

test('slow requests do not overlap and hidden pages pause polling until visible again', async ({ page }) => {
  const state = await setup(page);
  state.hold = true;
  await page.clock.fastForward(10000);
  await expect.poll(() => Boolean(state.pending)).toBe(true);
  const count = state.counts['tauron.json'];
  await page.clock.fastForward(30000);
  expect(state.counts['tauron.json']).toBe(count);
  state.hold = false;
  await state.pending.fulfill({ json: state.payload });
  await expect.poll(() => page.evaluate(() => document.querySelectorAll('[data-match-id="live-one"]').length)).toBeGreaterThan(0);
  // Let the request body's promise and React commit finish before changing visibility.
  await page.clock.runFor(100);
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, value: true });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  const paused = state.counts['tauron.json'];
  await page.clock.fastForward(30000);
  expect(state.counts['tauron.json']).toBe(paused);
  state.payload.matches[0].current_points = '23:19';
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await expect(card(page, 'live-one')).toContainText('23:19');
});
