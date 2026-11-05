import { useLayoutEffect, useRef } from 'react';
import './PageStage.css';

// Active screen switches immediately. No snapshots, overlays or canvases
// can ever cover the live dock during navigation.
export default function PageStage({ page, direction, reducedMotion, children }) {
  const main = useRef(null);
  const previous = useRef(page);
  useLayoutEffect(() => {
    const changed = previous.current !== page;
    previous.current = page;
    const host = main.current;
    if (!changed || reducedMotion || document.hidden || !host?.animate) return undefined;
    const animation = host.animate([
      { opacity: .95, transform: 'translate3d(0,3px,0)' },
      { opacity: 1, transform: 'translate3d(0,0,0)' }
    ], { id: 'vh-route-transition', duration: 180, easing: 'cubic-bezier(.22,1,.36,1)' });
    const finish = () => animation.cancel();
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
