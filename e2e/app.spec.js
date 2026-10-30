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


test('Tech Text logo animates itself with no mouse interaction and search bubble opens', async ({ page }) => {
  await page.goto('/');
  const logo = page.getByRole('img', { name: 'VOLLEY HUB' });
  await expect(logo).toBeVisible();
  await expect(logo).toContainText('VOLLEY');
  await expect(page.locator('.vh-topline')).toHaveCount(0);
  await expect(page.locator('.vh-floating-head')).toBeVisible();
  const canvas = page.locator('.vh-brand-tech .tech-text canvas');
  await expect(canvas).toBeVisible();
  await expect(page.locator('.vh-brand-tech.has-canvas')).toBeVisible();
  const first = await canvas.evaluate(element => element.toDataURL());
  await page.waitForTimeout(1900);
  const last = await canvas.evaluate(element => element.toDataURL());
  expect(last).not.toBe(first);
  await page.getByRole('button', { name: 'Szukaj', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Wyszukiwarka' })).toBeVisible();
});

test('TechText logo ignores all pointer events after its automatic intro', async ({ page }) => {
  await page.goto('/');
  const logo = page.locator('.vh-brand-tech .tech-text');
  const canvas = logo.locator('canvas');
  await expect(page.locator('.vh-brand-tech.has-canvas')).toBeVisible();
  await page.waitForTimeout(2600);
  const before = await canvas.evaluate(el => el.toDataURL());
  for (const event of ['pointermove', 'pointerdown', 'pointerup']) {
    await logo.dispatchEvent(event, { clientX: 90, clientY: 25, pointerType: 'mouse' });
  }
  await page.waitForTimeout(350);
  expect(await canvas.evaluate(el => el.toDataURL())).toBe(before);
});

test('TechText logo replays by itself without a tap', async ({ page }) => {
  await page.clock.install();
  await page.goto('/');
  const canvas = page.locator('.vh-brand-tech .tech-text canvas');
  await expect(page.locator('.vh-brand-tech.has-canvas')).toBeVisible();
  await page.waitForTimeout(2600);
  const settled = await canvas.evaluate(el => el.toDataURL());
  await page.clock.fastForward(18000);
  await expect.poll(() => canvas.evaluate(el => el.toDataURL()), { timeout: 4000 }).not.toBe(settled);
});

test('reduced motion keeps accessible static logo and no canvas', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  const logo = page.getByRole('img', { name: 'VOLLEY HUB' });
  await expect(logo).toBeVisible();
  await expect(logo).toContainText('VOLLEY');
  await expect(logo).toContainText('HUB');
  await expect(page.locator('.vh-brand-tech canvas')).toHaveCount(0);
});

test('floating logo and search bubble never overlap at 320px and 375px', async ({ page }) => {
  for (const width of [320, 375]) {
    await page.setViewportSize({ width, height: 700 });
    await page.goto('/');
    const logo = await page.locator('.vh-brand-tech').boundingBox();
    const bubble = await page.getByRole('button', { name: 'Szukaj', exact: true }).boundingBox();
    expect(logo).toBeTruthy();
    expect(bubble).toBeTruthy();
    expect(logo.x + logo.width).toBeLessThanOrEqual(bubble.x - 2);
    expect(bubble.x + bubble.width).toBeLessThanOrEqual(width);
  }
});

test('old Rive wordmark assets are no longer used', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.vh-rive-layer')).toHaveCount(0);
  await expect(page.locator('.vh-wordmark-icon')).toHaveCount(0);
});

test('bottom navigation uses just one React glass lens and no CSS pill overlay', async ({ page }) => {
  await page.goto('/');
  const nav = page.getByRole('navigation', { name: 'Główna nawigacja' });
  await expect(nav).toBeVisible();
  const active = nav.locator('.vh-nav-item.active');
  await expect(active).toHaveCount(1);
  const css = await active.evaluate(el => {
    const style = getComputedStyle(el);
    return { background: style.backgroundColor, image: style.backgroundImage, shadow: style.boxShadow };
  });
  expect(css.background).toBe('rgba(0, 0, 0, 0)');
  expect(css.image).toBe('none');
  expect(css.shadow).toBe('none');
  await nav.getByRole('button', { name: 'Mecze' }).click();
  await expect(nav.locator('.vh-nav-item.active')).toHaveCount(1);
  await expect(nav.getByRole('button', { name: 'Mecze' })).toHaveAttribute('aria-current', 'page');
});

test('search bubble is glass powered by React or a readable static fallback', async ({ page }) => {
  await page.goto('/');
  const bubble = page.getByRole('button', { name: 'Szukaj', exact: true });
  await expect(bubble).toBeVisible();
  expect(await bubble.evaluate(el => getComputedStyle(el).backdropFilter)).toBe('none');
  await bubble.click();
  const search = page.getByRole('dialog', { name: 'Wyszukiwarka' });
  await expect(search).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(search).toHaveCount(0);
  await expect(bubble).toBeFocused();
});

test('mobile navigation, date strip and saved favorites survive the cleanup', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto('/');
  const nav = page.getByRole('navigation', { name: 'Główna nawigacja' });
  await nav.getByRole('button', { name: 'Mecze' }).click();
  await expect(page.getByRole('tablist', { name: 'Wybierz dzień' })).toBeVisible();
  await nav.getByRole('button', { name: 'Rozgrywki' }).click();
  await page.getByRole('button', { name: 'Dodaj do ulubionych: TAURON Liga Mężczyzn' }).click();
  await nav.getByRole('button', { name: 'Ulubione' }).click();
  await page.getByRole('tab', { name: /Rozgrywki/ }).click();
  await expect(page.getByText('TAURON Liga Mężczyzn').first()).toBeVisible();
});
