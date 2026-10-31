import { test, expect } from '@playwright/test';

test('renders React navigation and shared match design', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /^(Mecze dzisiaj|Co przed nami)$/ })).toBeVisible();
  const nav = page.getByRole('navigation', { name: 'Główna nawigacja' });
  await nav.getByRole('button', { name: 'Mecze' }).click();
  await expect(page.getByRole('heading', { name: 'Mecze' })).toBeVisible();
  await expect(page.getByRole('tablist', { name: 'Wybierz dzień' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Wszystkie ligi' })).toBeVisible();
  await nav.getByRole('button', { name: 'Rozgrywki' }).click();
  await expect(page.getByRole('heading', { name: 'Rozgrywki' })).toBeVisible();
  await expect(page.getByText('TAURON Liga Mężczyzn').first()).toBeVisible();
});

test('home starts with match list, without the marked intro and hero banner', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('img', { name: 'Kiedy Siatka?' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Szukaj', exact: true })).toBeVisible();
  await expect(page.locator('#main-content').getByRole('heading', { name: /^(Mecze dzisiaj|Co przed nami)$/ })).toBeVisible();
  await expect(page.locator('.vh-hero')).toHaveCount(0);
  await expect(page.locator('#main-content').getByRole('heading', { name: 'Volley Hub', exact: true })).toHaveCount(0);
  await expect(page.getByText('Twoje centrum siatkówki. Wszystko, co ważne, w jednym miejscu.')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Zobacz mecze' })).toBeVisible();
});

test('favorites persist after reload', async ({ page }) => {
  await page.goto('/#competitions');
  await page.getByRole('button', { name: 'Dodaj do ulubionych: TAURON Liga Mężczyzn' }).click();
  await page.reload();
  await page.getByRole('navigation', { name: 'Główna nawigacja' }).getByRole('button', { name: 'Ulubione' }).click();
  await page.getByRole('tab', { name: /Rozgrywki/ }).click();
  await expect(page.locator('#main-content .vh-league-stack').getByText('TAURON Liga Mężczyzn')).toBeVisible();
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


test('Kiedy Siatka SVG loads without an animated or hidden logo', async ({ page }) => {
  await page.goto('/');
  const logo = page.getByRole('img', { name: 'Kiedy Siatka?' });
  await expect(logo).toBeVisible();
  await expect(page.locator('.vh-brand-signature img')).toHaveCount(1);
  await expect.poll(() => logo.evaluate(img => img.naturalWidth)).toBe(340);
  await expect.poll(() => logo.evaluate(img => img.naturalHeight)).toBe(184);
  await expect(page.locator('.vh-brand-tech, .vh-brand-tech-fallback, .tech-text, .vh-rive-layer, .vh-wordmark-icon')).toHaveCount(0);
  await expect(page.locator('.vh-brand-signature canvas')).toHaveCount(0);
  await expect(page.locator('.vh-floating-head img')).toHaveCount(1);
  await page.getByRole('button', { name: 'Szukaj', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Wyszukiwarka' })).toBeVisible();
});

test('Kiedy Siatka wordmark stays static in reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  const logo = page.getByRole('img', { name: 'Kiedy Siatka?' });
  await expect(logo).toBeVisible();
  expect(await logo.evaluate(img => getComputedStyle(img).animationName)).toBe('none');
  await expect(page.locator('.vh-brand-signature canvas')).toHaveCount(0);
});

test('floating logo and search bubble never overlap at 320px and 375px', async ({ page }) => {
  for (const width of [320, 375]) {
    await page.setViewportSize({ width, height: 700 });
    await page.goto('/');
    const logo = await page.locator('.vh-brand-signature').boundingBox();
    const bubble = await page.getByRole('button', { name: 'Szukaj', exact: true }).boundingBox();
    expect(logo).toBeTruthy();
    expect(bubble).toBeTruthy();
    expect(logo.x + logo.width).toBeLessThanOrEqual(bubble.x - 2);
    expect(bubble.x + bubble.width).toBeLessThanOrEqual(width);
  }
});

test('stacked SVG wordmark stays proportional to the search control and page title', async ({ page }) => {
  for (const width of [320, 375, 430, 768]) {
    await page.setViewportSize({ width, height: 780 });
    await page.goto('/#favorites');
    const { brand, image, bubble, heading, header } = await page.evaluate(() => {
      const box = element => {
        const { x, y, width, height } = element.getBoundingClientRect();
        return { x, y, width, height };
      };
      return {
        brand: box(document.querySelector('.vh-brand-signature')),
        image: box(document.querySelector('.vh-brand-signature img')),
        bubble: box(document.querySelector('.vh-search-bubble')),
        heading: box(document.querySelector('#main-content h1')),
        header: box(document.querySelector('.vh-floating-head'))
      };
    });
    expect(brand.width).toBeLessThanOrEqual(197);
    expect(image.height).toBeLessThanOrEqual(110);
    expect(Math.abs((image.y + image.height / 2) - (bubble.y + bubble.height / 2))).toBeLessThan(10);
    expect(image.x + image.width + 10).toBeLessThanOrEqual(bubble.x);
    expect(heading.y - (header.y + header.height)).toBeLessThan(35);
  }
});

test('old Rive wordmark assets are no longer used', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.vh-rive-layer')).toHaveCount(0);
  await expect(page.locator('.vh-wordmark-icon')).toHaveCount(0);
});


test('navigation and search use React Bits GlassSurface without old bubble canvases', async ({ page }) => {
  await page.goto('/');
  const nav = page.getByRole('navigation', { name: 'Główna nawigacja' });
  await expect(nav.locator('.vh-nav-lens .glass-surface')).toHaveCount(1);
  await expect(nav.locator('.vh-nav-lens .fluid-glass')).toHaveCount(0);
  await expect(page.locator('.vh-search-glass .glass-surface')).toHaveCount(1);
  await expect(page.locator('.vh-search-glass .fluid-glass')).toHaveCount(0);
  for (const name of ['Główna', 'Mecze', 'Rozgrywki', 'Ulubione']) {
    await expect(nav.getByRole('button', { name })).toBeVisible();
  }
  await nav.getByRole('button', { name: 'Ulubione' }).click();
  await expect(nav.locator('.vh-nav-lens .glass-surface')).toHaveCount(1);
});

test('rapid switches keep one live screen and menu in sync, without cloning page lists', async ({ page }) => {
  await page.goto('/');
  const nav = page.getByRole('navigation', { name: 'Główna nawigacja' });
  for (const [name, route] of [
    ['Mecze','matches'], ['Ulubione','favorites'], ['Rozgrywki','competitions'], ['Główna','home']
  ]) {
    await nav.getByRole('button', { name }).evaluate(button => button.click());
    await expect(nav.locator('.vh-nav-items')).toHaveAttribute('data-active', route);
    await expect(page.locator('#main-content')).toHaveAttribute('data-page', route);
    await expect(page.locator('.vh-page')).toHaveCount(1);
    await expect(page.locator('.vh-page-exit')).toHaveCount(0);
  }
});

test('switching tabs crossfades pages and animates the menu label', async ({ page }) => {
  await page.goto('/');
  const nav = page.getByRole('navigation', { name: 'Główna nawigacja' });
  await nav.getByRole('button', { name: 'Mecze' }).click();
  await expect(page.locator('#main-content').getByRole('heading', { name: 'Mecze' })).toBeVisible();
  await expect(nav.getByRole('button', { name: 'Mecze' })).toHaveAttribute('aria-current', 'page');
  const label = nav.locator('.vh-nav-item.active > span');
  await expect(label).toHaveCSS('display', 'block');
  await expect.poll(() => label.evaluate(el => parseFloat(getComputedStyle(el).maxWidth))).toBeGreaterThan(0);
  await expect(page.locator('.vh-page-exit')).toHaveCount(0, { timeout: 3000 });
  await nav.getByRole('button', { name: 'Ulubione' }).click();
  await expect(page.locator('#main-content').getByRole('heading', { name: 'Ulubione' })).toBeVisible();
  await expect(page.locator('.vh-route-stage')).toHaveClass(/is-forward/);
  await nav.getByRole('button', { name: 'Główna' }).click();
  await expect(page.locator('#main-content').getByRole('heading', { name: /^(Mecze dzisiaj|Co przed nami)$/ })).toBeVisible();
  await expect(page.locator('.vh-route-stage')).toHaveClass(/is-backward/);
  await expect(nav.locator('.vh-nav-item.active')).toHaveCount(1);
});

test('reduced motion skips page exit transitions', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await page.getByRole('navigation', { name: 'Główna nawigacja' })
    .getByRole('button', { name: 'Rozgrywki' }).click();
  await expect(page.locator('#main-content').getByRole('heading', { name: 'Rozgrywki' })).toBeVisible();
  await expect(page.locator('.vh-page-exit')).toHaveCount(0);
  await expect(page.locator('.vh-page-enter')).toHaveCount(0);
});

test('quick tab changes keep navigation and content synchronized', async ({ page }) => {
  await page.goto('/');
  const nav = page.getByRole('navigation', { name: 'Główna nawigacja' });
  await nav.getByRole('button', { name: 'Mecze' }).click();
  await nav.getByRole('button', { name: 'Rozgrywki' }).click();
  await nav.getByRole('button', { name: 'Ulubione' }).click();
  await expect(page.locator('#main-content').getByRole('heading', { name: 'Ulubione' })).toBeVisible();
  await expect(nav.locator('.vh-nav-item.active')).toHaveCount(1);
  await expect(page.locator('.vh-page-exit')).toHaveCount(0, { timeout: 3000 });
  await page.goBack();
  await expect(page.locator('#main-content').getByRole('heading', { name: 'Rozgrywki' })).toBeVisible();
});

test('liquid lens moves with one interruptible spring, not a CSS lens transition', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 760 });
  await page.goto('/');
  const nav = page.getByRole('navigation', { name: 'Główna nawigacja' });
  const lens = nav.locator('.vh-nav-lens');
  const track = nav.locator('.vh-nav-items');
  await expect(track).toHaveClass(/is-ready/);
  await expect(lens).toBeVisible();

  const computed = await nav.evaluate(root => ({
    lensTransition: getComputedStyle(root.querySelector('.vh-nav-lens')).transitionDuration,
    tabTransition: getComputedStyle(root.querySelector('.vh-nav-item')).transitionDuration,
    trackProperties: getComputedStyle(root.querySelector('.vh-nav-items')).transitionProperty
  }));
  expect(computed.lensTransition).toBe('0s');
  expect(computed.tabTransition).not.toBe('0s');
  expect(computed.trackProperties).not.toContain('grid-template-columns');

  const left = async () => lens.evaluate(el =>
    new DOMMatrixReadOnly(getComputedStyle(el).transform).m41);
  const initial = await left();
  await nav.getByRole('button', { name: 'Rozgrywki' }).click();
  await expect(track).toHaveAttribute('data-active', 'competitions');
  await page.waitForTimeout(60);
  const inFlight = await left();
  expect(inFlight).toBeGreaterThan(initial);

  // Dispatch immediately: Playwright's standard click waits for moving
  // elements to become stable, which would skip the interruption case.
  await nav.getByRole('button', { name: 'Mecze' }).evaluate(el => el.click());
  await expect(track).toHaveAttribute('data-active', 'matches');
  await page.waitForTimeout(850);
  const settled = await left();
  const target = await nav.getByRole('button', { name: 'Mecze' }).evaluate(el =>
    el.getBoundingClientRect().left - el.parentElement.getBoundingClientRect().left);
  expect(Math.abs(settled - target)).toBeLessThan(0.6);
  await expect(page.locator('#main-content').getByRole('heading', { name: 'Mecze' })).toBeVisible();
});

test('reduced motion snaps the liquid lens immediately to its selected tab', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  const nav = page.getByRole('navigation', { name: 'Główna nawigacja' });
  const targetButton = nav.getByRole('button', { name: 'Ulubione' });
  await targetButton.click();
  const difference = await nav.evaluate(root => {
    const lens = root.querySelector('.vh-nav-lens');
    const selected = root.querySelector('.vh-nav-item.active');
    return Math.abs(lens.getBoundingClientRect().left - selected.getBoundingClientRect().left);
  });
  expect(difference).toBeLessThan(0.6);
});

test('buttons remain separated throughout the transition at 320px and 375px',async({page})=>{
  for(const width of [320,375]){
    await page.setViewportSize({width,height:760});
    await page.goto('/');
    const nav=page.getByRole('navigation',{name:'Główna nawigacja'});
    for(const name of ['Mecze','Rozgrywki','Ulubione','Główna']){
      await nav.getByRole('button',{name}).click();
      for(const pause of [60,100,130,260]){
        await page.waitForTimeout(pause);
        const positions=await nav.locator('.vh-nav-item').evaluateAll(items=>items.map(item=>{
          const rect=item.getBoundingClientRect();
          return {left:rect.left,right:rect.right};
        }));
        for(let i=1;i<positions.length;i++){
          expect(positions[i].left+1).toBeGreaterThanOrEqual(positions[i-1].right);
        }
      }
    }
  }
});

test('menu remains aligned and readable at narrow mobile widths', async ({ page }) => {
  for (const width of [320, 375]) {
    await page.setViewportSize({ width, height: 720 });
    await page.goto('/');
    const nav = page.getByRole('navigation', { name: 'Główna nawigacja' });
    for (const name of ['Mecze', 'Rozgrywki', 'Ulubione', 'Główna']) {
      await nav.getByRole('button', { name }).click();
      await expect(nav.getByRole('button', { name })).toHaveAttribute('aria-current', 'page');
      const rects = await nav.evaluate(element => {
        const active = element.querySelector('.vh-nav-item.active').getBoundingClientRect();
        const host = element.getBoundingClientRect();
        return { left: active.left, right: active.right, hostLeft: host.left, hostRight: host.right };
      });
      expect(rects.left).toBeGreaterThanOrEqual(rects.hostLeft - 1);
      expect(rects.right).toBeLessThanOrEqual(rects.hostRight + 1);
    }
  }
});

test('floating nav is a persistent portal, separate from route content', async ({ page }) => {
  await page.goto('/');
  const nav = page.getByRole('navigation', { name: 'Główna nawigacja' });
  await expect(nav).toBeVisible();
  expect(await nav.evaluate(el => el.parentElement === document.body)).toBe(true);
  for (const target of ['Mecze', 'Rozgrywki', 'Ulubione', 'Główna']) {
    await nav.getByRole('button', { name: target }).click();
    await expect(nav.getByRole('button', { name: target })).toHaveAttribute('aria-current', 'page');
    await expect(nav).toBeVisible();
    expect(await nav.evaluate(el => el.parentElement === document.body)).toBe(true);
  }
});

test('nav glass draws at higher device pixel ratio when WebGL is available', async ({ page }) => {
  await page.goto('/');
  const canvas = page.getByRole('navigation', { name: 'Główna nawigacja' }).locator('.fluid-glass__canvas');
  if (await canvas.count()) {
    const ratio = await canvas.evaluate(el => {
      const rect = el.getBoundingClientRect();
      return rect.width ? el.width / rect.width : 0;
    });
    expect(ratio).toBeGreaterThanOrEqual(1.5);
  }
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
