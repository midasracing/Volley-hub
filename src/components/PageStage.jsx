import { useEffect, useLayoutEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import './PageStage.css';

// A quiet route handoff: the page responds immediately, while a small Rive
// streak underlines the change. The old typographic full-screen wipe is gone.
export default function PageStage({ page, direction, reducedMotion, children }) {
  const main = useRef(null);
  const overlay = useRef(null);
  const canvas = useRef(null);
  const rive = useRef(null);
  const ready = useRef(false);
  const previous = useRef(page);

  // Warm the shared, self-hosted Rive asset once instead of waiting for a tap.
  // If WASM loads late or fails, navigation still uses the native fade.
  useEffect(() => {
    if (reducedMotion) return undefined;
    let disposed = false;
    import('../motionRuntime.js').then(({ createRoutePulse }) => {
      if (disposed || !canvas.current) return;
      rive.current = createRoutePulse(canvas.current, () => {
        if (disposed) return;
        ready.current = true;
        if (overlay.current) overlay.current.dataset.riveReady = 'true';
      }, () => {
        ready.current = false;
      });
    }).catch(() => {});
    return () => {
      disposed = true;
      ready.current = false;
      rive.current?.cleanup();
      rive.current = null;
    };
  }, [reducedMotion]);

  useLayoutEffect(() => {
    const changed = previous.current !== page;
    previous.current = page;
    const host = main.current;
    const light = overlay.current;
    if (!changed || reducedMotion || document.hidden || !host?.animate) return undefined;

    const sign = direction === 'backward' ? -1 : 1;
    const animations = [];
    let disposed = false;

    // Avoid any holding state: destination content is already rendered.
    animations.push(host.animate([
      { opacity: .73, transform: 'translate3d(' + (sign * 7) + 'px,4px,0)' },
      { opacity: 1, transform: 'translate3d(0,0,0)' }
    ], { id: 'vh-route-transition', duration: 185, easing: 'cubic-bezier(.2,.8,.2,1)' }));

    if (ready.current && light && rive.current) {
      light.style.visibility = 'visible';
      try {
        rive.current.stop('Strike');
        rive.current.play('Strike');
        animations.push(light.animate([
          { opacity: .21 },
          { opacity: .13, offset: .38 },
          { opacity: 0 }
        ], { id: 'vh-rive-route-flash', duration: 200, easing: 'ease-out', fill: 'both' }));
      } catch {
        light.style.visibility = 'hidden';
      }
    }

    const finish = () => {
      animations.forEach(animation => animation.cancel());
      if (light) light.style.visibility = 'hidden';
      rive.current?.pause();
    };
    Promise.all(animations.map(animation => animation.finished))
      .then(() => { if (!disposed) finish(); })
      .catch(() => {});

    const onVisibility = () => { if (document.hidden) finish(); };
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      disposed = true;
      document.removeEventListener('visibilitychange', onVisibility);
      finish();
    };
  }, [page, direction, reducedMotion]);

  return <div className={'vh-route-stage is-' + direction}>
    <main ref={main} id="main-content" data-page={page}
      className={'vh-page' + (!reducedMotion ? ' vh-page-enter' : '')}>
      {children}
    </main>
    {createPortal(<div className="vh-route-rive" ref={overlay}
      data-rive-ready="false" aria-hidden="true">
      <canvas className="vh-route-rive-canvas" ref={canvas}/>
    </div>, document.body)}
  </div>;
}
