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
  await expect(page.locator('.vh-tab-panel:not([hidden])').getByText('TAURON Liga Mężczyzn').first()).toBeVisible();
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
  await expect(page.locator('.vh-tab-panel:not([hidden]) .vh-league-stack').getByText('TAURON Liga Mężczyzn')).toBeVisible();
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
  const vector = await page.evaluate(async () => {
    const img = document.querySelector('.vh-brand-signature img');
    const res = await fetch(img.currentSrc, { cache: 'no-store' });
    return await res.text();
  });
  expect(vector).toContain('viewBox="0 0 1180 655"');
  expect((vector.match(/<path /g) || []).length).toBe(15);
  expect(vector).not.toContain('<image ');
  expect(vector).not.toContain('<text ');
  await expect.poll(() => logo.evaluate(img => img.naturalWidth)).toBe(1180);
  await expect.poll(() => logo.evaluate(img => img.naturalHeight)).toBe(655);
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


test('exactly one React Bits glass surface is mounted in the dock, without legacy FluidGlass', async ({ page }) => {
  await page.goto('/');
  const nav = page.getByRole('navigation', { name: 'Główna nawigacja' });
  await expect(nav.locator('.vh-nav-lens .glass-surface')).toHaveCount(1);
  await expect(nav.locator('.vh-nav-lens .fluid-glass')).toHaveCount(0);
  await expect(page.locator('.glass-surface')).toHaveCount(1);
  await expect(page.locator('.fluid-glass')).toHaveCount(0);
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

test('switching tabs renders the page immediately without delayed transitions', async ({ page }) => {
  await page.goto('/');
  const nav = page.getByRole('navigation', { name: 'Główna nawigacja' });
  await nav.getByRole('button', { name: 'Mecze' }).click();
  await expect(page.locator('#main-content').getByRole('heading', { name: 'Mecze' })).toBeVisible();
  await expect(page.locator('#main-content')).toHaveCSS('animation-name', 'none');
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
  await lens.evaluate(el => Promise.all(el.getAnimations().map(animation => animation.ready)));
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

test('no unused WebGL fluid glass canvas or second navigation is rendered', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.fluid-glass__canvas')).toHaveCount(0);
  await expect(page.getByRole('navigation', { name: 'Główna nawigacja' })).toHaveCount(1);
  await expect(page.locator('.vh-nav-lens .glass-surface')).toHaveCount(1);
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
  await expect(page.locator('.vh-tab-panel:not([hidden])').getByText('TAURON Liga Mężczyzn').first()).toBeVisible();
});

test('tabs display a new page without CSS entrance delay or extra icon animations', async ({ page }) => {
  await page.goto('/');
  const nav = page.getByRole('navigation', { name: 'Główna nawigacja' });
  for (const [label, target] of [['Mecze','matches'], ['Ulubione','favorites'], ['Główna','home']]) {
    await nav.getByRole('button',{name:label}).evaluate(button=>button.click());
    await expect(page.locator('#main-content')).toHaveAttribute('data-page',target);
    await expect(page.locator('#main-content')).toHaveCSS('animation-name','none');
    await expect(page.locator('.vh-page')).toHaveCount(1);
  }
  const motionCount = await nav.locator('.vh-nav-item svg').evaluateAll(icons =>
    icons.flatMap(icon => icon.getAnimations())
      .filter(animation => animation.effect?.getKeyframes?.().some(frame => frame.transform != null)).length);
  expect(motionCount).toBe(0);
});

test('prepared tabs reuse their DOM and keep filters while only one panel is visible', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.vh-tab-panel')).toHaveCount(4);
  const nav = page.getByRole('navigation', { name: 'Główna nawigacja' });
  await nav.getByRole('button', { name: 'Mecze' }).click();
  await page.getByRole('button', { name: 'TAURON 1. Liga', exact: true }).click();
  const strip = page.getByRole('tablist', { name: 'Wybierz dzień' });
  await expect.poll(() => strip.evaluate(el => {
    const selected = el.querySelector('[aria-selected="true"]').getBoundingClientRect();
    const host = el.getBoundingClientRect();
    return Math.abs(selected.left + selected.width / 2 - host.left - host.width / 2);
  })).toBeLessThan(3);
  const panel = await page.locator('[data-route="matches"]').elementHandle();
  const stripHandle = await strip.elementHandle();
  await nav.getByRole('button', { name: 'Ulubione' }).click();
  await expect(page.getByRole('tablist', { name: 'Wybierz dzień' })).toHaveCount(0);
  await nav.getByRole('button', { name: 'Mecze' }).click();
  expect(await panel.evaluate(el => el === document.querySelector('[data-route="matches"]'))).toBe(true);
  expect(await stripHandle.evaluate(el => el === document.querySelector('.im-strip'))).toBe(true);
  await expect(page.getByRole('button', { name: 'TAURON 1. Liga', exact: true })).toHaveClass(/chosen/);
  await expect(page.locator('.vh-tab-panel:not([hidden])')).toHaveCount(1);

  // No page/list nodes may be created by a warm route switch. This catches
  // remount regressions without a timing budget that depends on CI hardware.
  const added = await page.evaluate(async () => {
    let count = 0;
    const observer = new MutationObserver(records => {
      for (const record of records) count += record.addedNodes.length;
    });
    observer.observe(document.querySelector('#main-content'), { childList: true, subtree: true });
    for (const label of ['Rozgrywki', 'Ulubione', 'Główna', 'Mecze']) {
      document.querySelector(`.vh-nav-item[aria-label="${label}"]`).click();
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    }
    observer.disconnect();
    return count;
  });
  expect(added).toBe(0);
});

test('moving lens uses native transforms with no backdrop filters or filter maps', async ({ page }) => {
  await page.goto('/');
  const nav = page.getByRole('navigation', { name: 'Główna nawigacja' });
  await expect(nav.locator('.vh-nav-lens')).toBeVisible();
  const animated = await nav.evaluate(root => new Promise(resolve => {
    const observer = new MutationObserver(() => {
      if (root.querySelector('.vh-nav-items').dataset.active !== 'favorites') return;
      observer.disconnect();
      const lens = root.querySelector('.vh-nav-lens');
      const material = lens.querySelector('.glass-surface');
      resolve({
        nativeTransforms: lens.getAnimations().some(animation =>
          animation.effect.getKeyframes().every(frame => typeof frame.transform === 'string')),
        backdrop: getComputedStyle(material).backdropFilter,
        filter: getComputedStyle(material).filter,
        filterNodes: lens.querySelectorAll('svg, canvas, filter').length
      });
    });
    observer.observe(root, { attributes: true, subtree: true });
    root.querySelector('[aria-label="Ulubione"]').click();
  }));
  expect(animated).toEqual({ nativeTransforms: true, backdrop: 'none', filter: 'none', filterNodes: 0 });
});

test('cached inactive tabs stay out of focus, accessibility and document scrolling', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.vh-tab-panel')).toHaveCount(4);
  const nav = page.getByRole('navigation', { name: 'Główna nawigacja' });
  // Give the longest page a real layout before hiding it again.
  await nav.getByRole('button', { name: 'Ulubione' }).click();
  await expect(page.getByRole('heading', { name: 'Dodaj drużyny' })).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  await nav.getByRole('button', { name: 'Rozgrywki' }).click();
  await expect(page.getByRole('heading', { name: 'Rozgrywki', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Dodaj drużyny' })).toHaveCount(0);
  const metrics = await page.evaluate(() => {
    const active = document.querySelector('.vh-tab-panel:not([hidden])');
    const hidden = [...document.querySelectorAll('.vh-tab-panel[hidden]')];
    const focus = document.activeElement;
    hidden[0].querySelector('button')?.focus();
    return {
      activeInert: active.inert,
      hiddenInert: hidden.every(panel => panel.inert),
      focusPreserved: document.activeElement === focus,
      top: window.scrollY,
      excessHeight: document.documentElement.scrollHeight - Math.max(
        window.innerHeight, document.querySelector('.vh-app').getBoundingClientRect().bottom + window.scrollY
      ),
      cachedLayout: !CSS.supports('content-visibility', 'hidden') || hidden.every(panel =>
        getComputedStyle(panel).display !== 'none' && getComputedStyle(panel).contentVisibility === 'hidden')
    };
  });
  expect(metrics).toMatchObject({ activeInert: false, hiddenInert: true, focusPreserved: true, top: 0, cachedLayout: true });
  expect(metrics.excessHeight).toBeLessThanOrEqual(2);
  // Returning to the cached calendar must still center the selected day.
  await nav.getByRole('button', { name: 'Mecze' }).click();
  const strip = page.getByRole('tablist', { name: 'Wybierz dzień' });
  await expect(strip).toBeVisible();
  await expect.poll(() => strip.evaluate(el => {
    const day = el.querySelector('[aria-selected="true"]').getBoundingClientRect();
    const host = el.getBoundingClientRect();
    return Math.abs(day.left + day.width / 2 - host.left - host.width / 2);
  })).toBeLessThan(3);
});
