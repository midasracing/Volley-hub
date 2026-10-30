import { test, expect } from '@playwright/test';

test('CONTACT renders as native Rive on a 390px phone', async ({ page }) => {
  await page.goto('/');
  const brand = page.getByRole('button', { name: 'Volley Hub — odtwórz animację logo' });
  await expect(brand).toBeVisible();
  await expect(brand).toHaveClass(/is-ready/, { timeout: 20000 });
  await expect(brand.locator('canvas')).toBeVisible();
  await page.waitForTimeout(1400);
  await page.locator('.vh-topline').screenshot({ path: 'test-results/contact-mobile-390.png' });
  await brand.tap();
  await expect(brand).toHaveClass(/is-ready/, { timeout: 20000 });
});

test('CONTACT fits 320px viewport and does not collide with search', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto('/');
  const brand = page.getByRole('button', { name: /odtwórz animację logo/ });
  await expect(brand).toHaveClass(/is-ready/, { timeout: 20000 });
  const a = await brand.boundingBox();
  const b = await page.getByRole('button', { name: 'Szukaj', exact: true }).boundingBox();
  expect(a.x + a.width).toBeLessThanOrEqual(b.x + 1);
  await page.waitForTimeout(1400);
  await page.locator('.vh-topline').screenshot({ path: 'test-results/contact-mobile-320.png' });
});

test('reduced-motion shows a still vector and never mounts a canvas', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  const logo = page.getByRole('img', { name: 'VOLLEY HUB' });
  await expect(logo).toBeVisible();
  await expect(page.locator('.vh-brand-signature canvas')).toHaveCount(0);
  await page.locator('.vh-topline').screenshot({ path: 'test-results/contact-reduced-motion.png' });
});
