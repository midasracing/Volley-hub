import { useLayoutEffect, useRef } from 'react';
import './PageStage.css';

// Switch the retained panel immediately; native compositor motion never delays
// navigation or remounts lists, filters, expanded sets, or the floating dock.
export default function PageStage({ page, direction, reducedMotion, children }) {
  const main = useRef(null);
  const previous = useRef(page);
  useLayoutEffect(() => {
    const changed = previous.current !== page;
    previous.current = page;
    const host = main.current;
    if (!changed || reducedMotion || document.hidden || !host?.animate) return undefined;
    const travel = direction === 'backward' ? -12 : 12;
    host.style.willChange = 'transform, opacity';
    const animation = host.animate([
      { opacity: .25, transform: `translate3d(${travel}px,8px,0)` },
      { opacity: 1, transform: 'translate3d(0,0,0)' }
    ], { id: 'vh-route-transition', duration: 360, easing: 'cubic-bezier(.16,1,.3,1)' });
    const finish = () => {
      animation.cancel();
      host.style.removeProperty('will-change');
    };
    animation.finished.then(finish).catch(() => {});
    const onVisibility = () => { if (document.hidden) finish(); };
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      finish();
    };
  }, [page, direction, reducedMotion]);
  return <div className={'vh-route-stage is-' + direction}>
    <main ref={main} id="main-content" data-page={page}
      className={'vh-page' + (!reducedMotion ? ' vh-page-enter' : '')}>
      {children}
    </main>
  </div>;
}
