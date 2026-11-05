import { test, expect } from '@playwright/test';

async function setup(page) {
  const now = new Date('2026-11-04T12:00:00Z');
  await page.clock.install({ time: now });
  await page.clock.pauseAt(now);
  await page.route('**/data/*.json', route => route.fulfill({ json: route.request().url().includes('/tauron.json') ? {
    teams: [], matches: [4, 5].map(day => ({
      id: `day-${day}`, date: `0${day}.11.2026`, time: '17:30',
      home: `Gospodarze dnia ${day}`, away: `Goście dnia ${day}`,
      status: 'finished', home_sets: 3, away_sets: 1,
      set_scores: ['25:22', '25:18', '20:25', '25:19'],
    })),
  } : { teams: [], matches: [], groups: [] } }));
  await page.goto('/#matches');
  // No skip button. Advance the frozen clock through the intro handoff.
  await page.clock.runFor(2350);
  await expect(page.locator('[data-route="matches"] [data-match-id="day-4"]')).toBeVisible();
}

test('calendar selection responds immediately and rapid taps settle on the latest day', async ({ page }) => {
  await setup(page);
  const results = page.locator('[data-route="matches"] .vh-day-results');
  const next = page.getByRole('tab', { name: '5 listopada 2026', exact: true });
  const originalPosition = await next.evaluate(element => element.offsetLeft);
  await next.click();
  await expect(next).toHaveAttribute('aria-selected', 'true');
  expect(await next.evaluate(element => element.offsetLeft)).toBe(originalPosition);
  await expect(results).toHaveAttribute('aria-busy', 'true');
  await page.clock.runFor(200);
  await expect(results).toHaveAttribute('data-day', '2026-11-05');
  await expect(results).toContainText('Gospodarze dnia 5');
  await expect.poll(() => next.evaluate(button => {
    const selected = button.getBoundingClientRect();
    const marker = button.parentElement.querySelector('.vh-date-indicator').getBoundingClientRect();
    return Math.abs(marker.left + marker.width / 2 - selected.left - selected.width / 2);
  })).toBeLessThan(1);
  await page.getByRole('tab', { name: '6 listopada 2026', exact: true }).click();
  await page.getByRole('tab', { name: '4 listopada 2026', exact: true }).click();
  await page.clock.runFor(700);
  await expect(results).toHaveAttribute('data-day', '2026-11-04');
  await expect(results).toHaveAttribute('aria-busy', 'false');
  await expect(results).toContainText('Gospodarze dnia 4');
  await expect(results).not.toContainText('Gospodarze dnia 5');
});

test('sets remain readable after interrupting a close with another expansion', async ({ page }) => {
  await setup(page);
  const card = page.locator('[data-route="matches"] [data-match-id="day-4"]');
  await card.getByRole('button', { name: 'Pokaż sety' }).click();
  await page.clock.runFor(100);
  await card.getByRole('button', { name: 'Ukryj sety' }).click();
  await card.getByRole('button', { name: 'Pokaż sety' }).click();
  await page.clock.runFor(700);
  const region = card.getByRole('region', { name: 'Wyniki setów' });
  await expect(region).toBeVisible();
  await expect(region.locator('strong')).toHaveText(['25:22', '25:18', '20:25', '25:19']);
  // WAAPI uses the native rendering timeline, independently of page.clock.
  await expect.poll(() => region.locator('span').evaluateAll(cells => cells.every(cell => getComputedStyle(cell).opacity === '1'))).toBe(true);
  await card.getByRole('button', { name: 'Ukryj sety' }).click();
  await page.clock.runFor(400);
  await expect(card.locator('.vh-sets-wrap')).toHaveAttribute('aria-hidden', 'true');
  await expect(card.locator('.vh-sets-wrap')).toHaveAttribute('inert', '');
});

test('reduced motion changes the day immediately and expands sets without stagger', async ({ page }) => {
  await setup(page);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.getByRole('tab', { name: '5 listopada 2026', exact: true }).click();
  const results = page.locator('[data-route="matches"] .vh-day-results');
  await expect(results).toHaveAttribute('data-day', '2026-11-05');
  await results.getByRole('button', { name: 'Pokaż sety' }).click();
  await expect(results.getByRole('region', { name: 'Wyniki setów' })).toBeVisible();
  expect(await results.locator('.vh-sets > span').evaluateAll(cells => cells.every(cell => cell.getAnimations().length === 0))).toBe(true);
});
