import { useEffect, useLayoutEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import './PageStage.css';

const ROUTE_MS = 210;
const ACCENT_MS = 165;
const RECENT_TAP_MS = 260;

// The active panel is visible immediately. A tiny compositor-only motion
// gives navigation continuity; Rive is a decorative optional accent.
export default function PageStage({ page, direction, reducedMotion, children }) {
  const main = useRef(null);
  const overlay = useRef(null);
  const canvas = useRef(null);
  const rive = useRef(null);
  const ready = useRef(false);
  const previous = useRef(page);
  const lastTapAt = useRef(0);
  const interrupted = useRef(null);

  useEffect(() => {
    if (reducedMotion) return undefined;
    let disposed = false;
    import('../motionRuntime.js').then(({ createRoutePulse }) => {
      if (disposed || !canvas.current) return;
      rive.current = createRoutePulse(canvas.current, () => {
        if (disposed) return;
        ready.current = true;
        if (overlay.current) overlay.current.dataset.riveReady = 'true';
      }, () => { ready.current = false; });
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
    if (!changed || reducedMotion || document.hidden || !host?.animate ||
        document.documentElement.classList.contains('vh-native-route')) return undefined;

    const now = performance.now();
    const rapid = now - lastTapAt.current < RECENT_TAP_MS;
    lastTapAt.current = now;

    // An interrupted transition continues from its *actual rendered frame*,
    // instead of restarting at low opacity and producing a visible flash.
    const carry = interrupted.current;
    interrupted.current = null;
    const from = carry && now - carry.time < ROUTE_MS
      ? Math.max(.9, Math.min(1, carry.opacity)) : .94;
    const offset = carry && now - carry.time < ROUTE_MS ? carry.y : 4;
    const animation = host.animate([
      { opacity: from, transform: 'translate3d(0,' + offset + 'px,0)' },
      { opacity: 1, transform: 'translate3d(0,0,0)' }
    ], { id: 'vh-route-transition', duration: ROUTE_MS,
      easing: 'cubic-bezier(.22,1,.36,1)' });

    let accent = null;
    // Repeated taps never restart a decoding canvas on each interaction.
    if (!rapid && ready.current && light && rive.current?.loaded) {
      try {
        rive.current.stop('Strike');
        rive.current.play('Strike');
        light.style.visibility = 'visible';
        accent = light.animate([
          { opacity: .085 },
          { opacity: .055, offset: .35 },
          { opacity: 0 }
        ], { id: 'vh-rive-route-flash', duration: ACCENT_MS,
          easing: 'cubic-bezier(.22,1,.36,1)', fill: 'both' });
      } catch {
        light.style.visibility = 'hidden';
      }
    } else if (light) {
      light.style.visibility = 'hidden';
      rive.current?.pause();
    }

    let disposed = false;
    const clear = () => {
      // Capture the current composite before canceling animations; the next
      // page can then resume the easing instead of snapping back.
      if (animation.playState === 'running') {
        const style = getComputedStyle(host);
        const matrix = new DOMMatrixReadOnly(style.transform === 'none' ? undefined : style.transform);
        interrupted.current = { opacity: parseFloat(style.opacity) || 1,
          y: matrix.m42, time: performance.now() };
      }
      animation.cancel();
      accent?.cancel();
      if (light) light.style.visibility = 'hidden';
      rive.current?.pause();
    };
    Promise.all([animation.finished, ...(accent ? [accent.finished] : [])])
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
