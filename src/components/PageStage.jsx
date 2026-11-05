import { useLayoutEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import './PageStage.css';

const ROW_COUNT = 36;
const ROW_DURATION = 195;
const ROW_STAGGER = 2.7;
const LABELS = {
  home: 'DZISIAJ',
  matches: 'KALENDARZ',
  competitions: 'ROZGRYWKI',
  favorites: 'ULUBIONE'
};
const LINES = Array.from({ length: ROW_COUNT }, (_, index) => index);

// The reference's densely repeated type compresses into ink-like horizontal
// streaks, expands into wide glyphs and then leaves the screen in a snake.
// Each red row also masks its own slice of the newly selected page.
export default function PageStage({ page, direction, reducedMotion, children }) {
  const main = useRef(null);
  const serpent = useRef(null);
  const previous = useRef(page);

  useLayoutEffect(() => {
    const changed = previous.current !== page;
    previous.current = page;
    const cover = serpent.current;
    const host = main.current;
    if (!changed || reducedMotion || document.hidden || !cover || !host?.animate) return undefined;

    const sense = direction === 'backward' ? -1 : 1;
    const animations = [];
    let disposed = false;
    cover.style.visibility = 'visible';
    host.style.willChange = 'transform, opacity';

    const rows = Array.from(cover.children);
    rows.forEach((row, index) => {
      // Adjacent rows always depart in opposite directions; reading from top
      // to bottom creates one continuous serpentine sweep.
      const sign = (index % 2 === 0 ? -1 : 1) * sense;
      const delay = index * ROW_STAGGER;
      const pressure = 1 - Math.pow(Math.abs((index - (ROW_COUNT - 1) / 2) / ((ROW_COUNT - 1) / 2)), 1.6);
      const smearX = (2.2 + pressure * 4).toFixed(2);
      const flareX = (1.6 + pressure * 2.4).toFixed(2);
      const smallX = (.82 + pressure * .18).toFixed(2);

      animations.push(row.animate([
        { transform: 'translate3d(0,0,0)', offset: 0 },
        { transform: 'translate3d(' + sign * 12 + '%,0,0)', offset: .3 },
        { transform: 'translate3d(' + sign * 107 + '%,0,0)', offset: 1 }
      ], {
        id: index === 0 ? 'vh-type-serpent' : undefined,
        duration: ROW_DURATION,
        delay,
        fill: 'both',
        easing: 'cubic-bezier(.75,0,.22,1)'
      }));

      const text = row.firstElementChild;
      animations.push(text.animate([
        { transform: 'translate3d(0,0,0) scaleX(' + smallX + ') scaleY(.95)', offset: 0 },
        { transform: 'translate3d(' + sign * 9 + 'px,0,0) scaleX(' + smearX + ') scaleY(.20)', offset: .34 },
        { transform: 'translate3d(' + sign * 16 + 'px,0,0) scaleX(' + flareX + ') scaleY(1.62)', offset: .72 },
        { transform: 'translate3d(' + sign * 22 + 'px,0,0) scaleX(1.15) scaleY(.82)', offset: 1 }
      ], {
        duration: ROW_DURATION,
        delay,
        fill: 'both',
        easing: 'linear'
      }));
    });

    animations.push(host.animate([
      { opacity: .76, transform: 'translate3d(0,7px,0) scale(.988)' },
      { opacity: 1, transform: 'translate3d(0,0,0) scale(1)' }
    ], { id: 'vh-route-transition', duration: 260, easing: 'cubic-bezier(.2,1,.22,1)', fill: 'both' }));

    const clear = () => {
      cover.style.visibility = 'hidden';
      host.style.removeProperty('will-change');
      animations.forEach(animation => animation.cancel());
    };
    Promise.all(animations.map(animation => animation.finished))
      .then(() => { if (!disposed) clear(); })
      .catch(() => {});
    const onVisibility = () => { if (document.hidden) clear(); };
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      disposed = true;
      document.removeEventListener('visibilitychange', onVisibility);
      clear();
    };
  }, [page, direction, reducedMotion]);

  const title = LABELS[page] || 'DZISIAJ';
  const repeat = title;

  return <div className={'vh-route-stage is-' + direction}>
    <main ref={main} id="main-content" data-page={page}
      className={'vh-page' + (!reducedMotion ? ' vh-page-enter' : '')}>
      {children}
    </main>
    {createPortal(
      <div ref={serpent} className="vh-type-serpent" aria-hidden="true">
        {LINES.map(index => <div key={index} className="vh-type-serpent-row">
          <span className="vh-type-serpent-text">{repeat}</span>
        </div>)}
      </div>,
      document.body
    )}
  </div>;
}
