import { test, expect } from '@playwright/test';

test('renders React navigation and shared match design', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Volley Hub' })).toBeVisible();
  const nav = page.getByRole('navigation', { name: 'Główna nawigacja' });
  await nav.getByRole('button', { name: 'Mecze' }).click();
  await expect(page.getByRole('heading', { name: 'Mecze' })).toBeVisible();
  await expect(page.getByRole('tablist', { name: 'Wybierz dzień' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Wszystkie ligi' })).toBeVisible();
  await nav.getByRole('button', { name: 'Rozgrywki' }).click();
  await expect(page.getByRole('heading', { name: 'Rozgrywki' })).toBeVisible();
  await expect(page.getByText('TAURON Liga Mężczyzn').first()).toBeVisible();
});

test('favorites persist after reload', async ({ page }) => {
  await page.goto('/#competitions');
  await page.getByRole('button', { name: 'Dodaj do ulubionych: TAURON Liga Mężczyzn' }).click();
  await page.reload();
  await page.getByRole('navigation', { name: 'Główna nawigacja' }).getByRole('button', { name: 'Ulubione' }).click();
  await page.getByRole('tab', { name: /Rozgrywki/ }).click();
  await expect(page.locator('.vh-league-stack').getByText('TAURON Liga Mężczyzn')).toBeVisible();
});

test('search overlay finds an existing league and opens its details', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Szukaj', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Wyszukiwarka' });
  await expect(dialog).toBeVisible();
  await dialog.getByRole('searchbox').fill('pomorska');
  await dialog.getByRole('button', { name: /Pomorska III Liga Męska/ }).click();
  await expect(page.getByRole('heading', { name: 'Pomorska III Liga Męska' })).toBeVisible();
  await expect(dialog).toHaveCount(0);
});

test('mobile brand stays accessible and can replay without hover', async ({ page }) => {
  await page.goto('/');
  const brand = page.getByRole('button', { name: 'Volley Hub — odtwórz animację logo' });
  await expect(brand).toBeVisible();
  await expect(brand).toContainText('VOLLEY');
  await brand.tap();
  await expect(brand).toBeVisible();
});

test('reduced motion preserves readable brand without Rive canvas', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  const brand = page.getByRole('img', { name: 'VOLLEY HUB' });
  await expect(brand).toBeVisible();
  await expect(brand).toContainText('VOLLEY');
  await expect(brand.locator('canvas')).toHaveCount(0);
});

test('static brand asset is available and remains usable offline-first', async ({ page, request }) => {
  const asset = await request.get('/brand/volley-hub-static.svg');
  expect(asset.ok()).toBeTruthy();
  const svg = await asset.text();
  expect(svg).toContain('viewBox="0 0 234 48"');
  expect((svg.match(/<path /g) || []).length).toBe(9);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await expect(page.locator('.vh-brand-static img')).toBeVisible();
  await expect(page.locator('.vh-brand-signature canvas')).toHaveCount(0);
  await expect(page.getByRole('button', { name: /odtwórz animację logo/ })).toHaveCount(0);
});

test('320px mobile header does not collide with search control', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto('/');
  const brand = await page.locator('.vh-brand-signature').boundingBox();
  const search = await page.getByRole('button', { name: 'Szukaj', exact: true }).boundingBox();
  expect(brand).toBeTruthy();
  expect(search).toBeTruthy();
  expect(brand.x + brand.width).toBeLessThanOrEqual(search.x + 0.5);
});
