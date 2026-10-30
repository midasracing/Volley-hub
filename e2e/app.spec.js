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
  expect((svg.match(/<path /g) || []).length).toBe(11);
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

test('CONTACT original mark is vector, not a copied font or raster', async ({ request }) => {
  const response = await request.get('/brand/volley-hub-static.svg');
  expect(response.ok()).toBeTruthy();
  const text = await response.text();
  expect(text).toContain('fill-rule="evenodd"');
  expect(text).toContain('#CCFD61');
  expect(text).not.toContain('<image');
  expect(text).not.toContain('<text');
});

test('CONTACT symbol is a valid standalone vector', async ({ request }) => {
  const response = await request.get('/brand/volley-hub-symbol.svg');
  expect(response.ok()).toBeTruthy();
  expect(await response.text()).toContain('viewBox="0 0 64 64"');
});

test('native CONTACT Rive binary is served as a nonempty asset', async ({ request }) => {
  const response = await request.get('/brand/volley-hub.riv');
  expect(response.ok()).toBeTruthy();
  const body = await response.body();
  expect(body.length).toBeGreaterThan(500);
});

test('installable mobile PWA icon assets are valid PNG files', async ({ request }) => {
  for (const size of [192, 512]) {
    const response = await request.get('/brand/volley-hub-icon-' + size + '.png');
    expect(response.ok()).toBeTruthy();
    const buffer = await response.body();
    expect(Array.from(buffer.subarray(0, 8))).toEqual([137, 80, 78, 71, 13, 10, 26, 10]);
    expect(buffer.length).toBeGreaterThan(500);
  }
  const manifest = await (await request.get('/manifest.webmanifest')).json();
  expect(manifest.icons).toEqual(expect.arrayContaining([expect.objectContaining({ sizes: '512x512', type: 'image/png' })]));
});
