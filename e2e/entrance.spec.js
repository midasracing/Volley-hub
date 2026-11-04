import { test, expect } from '@playwright/test';

test('home entrance uses the original logo, can be skipped and never replays on tab changes', async ({ page }) => {
  const now = new Date('2026-11-04T12:00:00Z');
  await page.clock.install({ time: now });
  await page.clock.pauseAt(now);
  await page.goto('/');
  const intro = page.locator('.vh-startup-intro');
  await expect(intro).toBeVisible();
  await expect(intro.locator('img')).toHaveAttribute('src', /kiedy-siatka-logo\.svg\?v=4$/);
  await expect(intro.locator('img')).toHaveAttribute('alt', '');
  await expect(intro).not.toContainText('WCHODZIMY DO GRY');
  await intro.getByRole('button', { name: 'Pomiń animację wejścia' }).click();
  await expect(intro).toHaveCount(0);
  const nav = page.getByRole('navigation', { name: 'Główna nawigacja' });
  await nav.getByRole('button', { name: 'Mecze', exact: true }).evaluate(button => button.click());
  await expect(page.locator('#main-content')).toHaveAttribute('data-page', 'matches');
  await nav.getByRole('button', { name: 'Główna', exact: true }).evaluate(button => button.click());
  await expect(page.locator('#main-content')).toHaveAttribute('data-page', 'home');
  await expect(intro).toHaveCount(0);
});

test('entrance finishes on schedule even if the Rive asset is unavailable', async ({ page }) => {
  const now = new Date('2026-11-04T12:00:00Z');
  await page.clock.install({ time: now });
  await page.clock.pauseAt(now);
  await page.route('**/motion/entrance.riv*', route => route.abort());
  await page.goto('/');
  await expect(page.locator('.vh-startup-intro')).toHaveCount(1);
  await page.clock.fastForward(3100);
  await expect(page.locator('.vh-startup-intro')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: /^(Mecze dzisiaj|Co przed nami)$/ })).toBeVisible();
  expect(await page.locator('.vh-floating-head').evaluate(element => element.getAnimations().length)).toBe(0);
});

test('reduced motion bypasses the entrance and direct links retain their destination', async ({ page }) => {
  const now = new Date('2026-11-04T12:00:00Z');
  await page.clock.install({ time: now });
  await page.clock.pauseAt(now);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await expect(page.locator('.vh-startup-intro')).toHaveCount(0);
  await expect(page.getByRole('img', { name: 'Kiedy Siatka?' })).toBeVisible();
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/#matches');
  await page.reload();
  await expect(page.locator('.vh-startup-intro')).toHaveCount(1);
  await page.getByRole('button', { name: 'Pomiń animację wejścia' }).click();
  await expect(page.locator('.vh-startup-intro')).toHaveCount(0);
  await expect(page).toHaveURL(/#matches$/);
  await expect(page.getByRole('heading', { name: 'Mecze', exact: true })).toBeVisible();
});
