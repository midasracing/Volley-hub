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
  await expect(page.getByRole('img', { name: 'VOLLEY HUB' })).toBeVisible();
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

test('TechText logo does not register pointer interactions', async ({ page }) => {
  await page.addInitScript(() => {
    window.__techTextPointerListeners = 0;
    const originalAdd = EventTarget.prototype.addEventListener;
    EventTarget.prototype.addEventListener = function (type, listener, options) {
      if (String(type).startsWith('pointer') && this instanceof HTMLElement && this.classList.contains('tech-text')) {
        window.__techTextPointerListeners += 1;
      }
      return originalAdd.call(this, type, listener, options);
    };
  });
  await page.goto('/');
  const logo = page.locator('.vh-brand-tech .tech-text');
  await expect(page.locator('.vh-brand-tech.has-canvas')).toBeVisible();
  await expect(logo).toHaveCSS('pointer-events', 'none');
  expect(await page.evaluate(() => window.__techTextPointerListeners)).toBe(0);
});

test('TechText performs its dashed outline sweep automatically, not particle assembly', async ({ page }) => {
  await page.goto('/');
  const canvas = page.locator('.vh-brand-tech .tech-text canvas');
  await expect(page.locator('.vh-brand-tech.has-canvas')).toBeVisible();
  const start = await canvas.evaluate(el => el.toDataURL());
  await page.waitForTimeout(1500);
  const middle = await canvas.evaluate(el => el.toDataURL());
  expect(middle).not.toBe(start);
  await page.waitForTimeout(1600);
  expect(await canvas.evaluate(el => el.toDataURL())).not.toBe(middle);
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

test('bubble and icons share compositor timing instead of animating the grid', async ({page}) => {
  await page.setViewportSize({width:375,height:760});
  await page.goto('/');
  const nav=page.getByRole('navigation',{name:'Główna nawigacja'});
  const lens=nav.locator('.vh-nav-lens');
  const track=nav.locator('.vh-nav-items');
  await expect(track).toHaveClass(/is-ready/);
  await expect(lens).toBeVisible();
  const timings=await nav.evaluate(root=>{
    const pill=getComputedStyle(root.querySelector('.vh-nav-lens'));
    const icon=getComputedStyle(root.querySelector('.vh-nav-item'));
    const tabs=getComputedStyle(root.querySelector('.vh-nav-items'));
    return {
      pillDuration:pill.transitionDuration.split(',')[0],
      iconDuration:icon.transitionDuration.split(',')[0],
      pillCurve:pill.transitionTimingFunction.split('),')[0],
      iconCurve:icon.transitionTimingFunction.split('),')[0],
      tabsProperty:tabs.transitionProperty
    };
  });
  expect(timings.pillDuration).toBe(timings.iconDuration);
  expect(timings.pillCurve).toBe(timings.iconCurve);
  expect(timings.tabsProperty).not.toContain('grid-template-columns');
  await nav.getByRole('button',{name:'Rozgrywki'}).click();
  await expect(track).toHaveAttribute('data-active','competitions');
  await expect(page.locator('#main-content').getByRole('heading',{name:'Rozgrywki'})).toBeVisible();
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
