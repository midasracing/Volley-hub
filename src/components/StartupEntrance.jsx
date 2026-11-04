import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import './StartupEntrance.css';

const LOGO = import.meta.env.BASE_URL + 'kiedy-siatka-logo.svg?v=4';

// The approved entrance plays once on an initial app load. Navigation and real
// feed requests remain independent; the intro is never a data-loading gate.
export default function StartupEntrance({ enabled, onComplete }) {
  const canvas = useRef(null);
  const [rivePlaying, setRivePlaying] = useState(false);
  useEffect(() => {
    if (!enabled || document.hidden) { onComplete(); return undefined; }
    let disposed = false, rive, ready = false;
    const timers = [], animations = [];
    const started = performance.now();
    const later = (callback, delay) => timers.push(window.setTimeout(callback, delay));
    const finish = () => { if (!disposed) onComplete(); };
    const animate = (element, frames, options) => {
      if (!element?.animate) return;
      animations.push(element.animate(frames, { fill: 'both', easing: 'cubic-bezier(.16,1,.3,1)', ...options }));
    };
    import('../motionRuntime.js').then(({ createEntrance }) => {
      if (disposed || performance.now() - started >= 950) return;
      rive = createEntrance(canvas.current, () => { ready = !disposed && performance.now() - started < 1000; }, () => { ready = false; });
    }).catch(() => { /* The matching CSS curtain remains available offline. */ });
    later(() => {
      if (disposed || !ready || !rive) return;
      try { rive.play(); setRivePlaying(true); } catch { /* Keep the CSS curtain. */ }
    }, 1020);
    later(() => {
      if (disposed) return;
      const home = document.querySelector('.vh-tab-panel:not([hidden])');
      const elements = [
        document.querySelector('.vh-floating-head'),
        home?.querySelector('.vh-section-heading, .vh-page-head'),
        home?.querySelector('.im-league'),
        ...Array.from(home?.querySelectorAll('.vh-match') || []).slice(0, 6),
        home?.querySelectorAll('.vh-section-heading')[1],
      ].filter(Boolean);
      elements.forEach((element, index) => {
        const card = element.classList.contains('vh-match');
        animate(element, [
          { opacity: 0, transform: `translateY(${card ? 54 : 24}px) scale(${card ? .96 : 1})`, clipPath: card ? 'inset(0 0 100% round 22px)' : 'inset(0)' },
          { opacity: 1, transform: 'translateY(0) scale(1)', clipPath: card ? 'inset(0 round 22px)' : 'inset(0)' },
        ], { duration: card ? 800 : 650, delay: index * 75 });
      });
      // Preserve the fixed dock's centering and its independent spring.
      animate(document.querySelector('.vh-bottom'), [{ opacity: 0 }, { opacity: 1 }], { duration: 650, delay: 450 });
    }, 1490);
    later(finish, 3000);
    const onVisibility = () => { if (document.hidden) finish(); };
    const onKey = () => finish();
    document.addEventListener('visibilitychange', onVisibility);
    document.addEventListener('keydown', onKey);
    return () => {
      disposed = true;
      timers.forEach(window.clearTimeout);
      animations.forEach(animation => animation.cancel());
      rive?.cleanup();
      document.removeEventListener('visibilitychange', onVisibility);
      document.removeEventListener('keydown', onKey);
    };
  }, [enabled, onComplete]);
  if (!enabled) return null;
  return createPortal(<div className={'vh-startup-intro' + (rivePlaying ? ' has-rive' : '')}>
    <div className="vh-startup-copy" aria-hidden="true">
      <div className="vh-startup-mask"><div className="vh-startup-logo-rise">
        <img className="vh-startup-logo" src={LOGO} width="1180" height="655" alt="" draggable={false} fetchPriority="high" />
      </div></div>
      <div className="vh-startup-rule" />
    </div>
    <div className="vh-startup-curtain" aria-hidden="true" />
    <canvas className="vh-startup-rive" ref={canvas} aria-hidden="true" />
    <button type="button" className="vh-startup-skip" onClick={onComplete} aria-label="Pomiń animację wejścia">Pomiń ↗</button>
  </div>, document.body);
}
