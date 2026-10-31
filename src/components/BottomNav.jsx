import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import GlassSurface from './react-bits/GlassSurface.jsx';
import { NAV } from '../navigation.js';
import { calculateNavLayout } from './navLayout.js';
import { advanceNavSpring, isNavSpringSettled, navLensStretch } from './navSpring.js';
import './BottomNav.css';

// React Bits GlassSurface is made for custom shapes like this pill.
// It stays mounted as one uninterrupted glass layer while the spring moves it.
const StaticGlass = memo(function StaticGlass() {
  return <GlassSurface
    className="vh-react-glass"
    width="100%" height="100%" borderRadius={999}
    borderWidth={0.12} brightness={55} opacity={0.9} blur={8}
    displace={0} backgroundOpacity={0.06} saturation={1.16}
    distortionScale={-82} redOffset={-7} greenOffset={4} blueOffset={14}
    mixBlendMode="screen"
  />;
});

function BottomNav({ active, onNavigate }) {
  const trackRef = useRef(null);
  const lensRef = useRef(null);
  const frameRef = useRef(0);
  const reducedMotionRef = useRef(false);
  const springRef = useRef({
    position: NaN, velocity: 0, target: 0, width: 0, lastTime: 0
  });
  const [dimensions, setDimensions] = useState(null);
  const activeIndex = Math.max(0, NAV.findIndex(item => item.id === active));

  useLayoutEffect(() => {
    const track = trackRef.current;
    if (!track) return undefined;
    const measure = () => {
      const style = getComputedStyle(track);
      const width = track.clientWidth;
      const padding = parseFloat(style.paddingLeft) || 0;
      const gap = parseFloat(style.getPropertyValue('--vh-nav-gap')) || 0;
      setDimensions(previous =>
        previous && Math.abs(previous.width - width) < 0.5 &&
          previous.padding === padding && previous.gap === gap
          ? previous : { width, padding, gap }
      );
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(track);
    return () => observer.disconnect();
  }, []);

  const layout = useMemo(() => dimensions ? calculateNavLayout({
    ...dimensions, activeIndex, count: NAV.length
  }) : null, [dimensions, activeIndex]);

  // Write only a transform (translate + a velocity-dependent stretch).
  // The React tree never renders on animation frames.
  const paintLens = useCallback(() => {
    const lens = lensRef.current;
    const state = springRef.current;
    if (!lens || !Number.isFinite(state.position)) return;
    const stretch = reducedMotionRef.current ? 1 :
      navLensStretch(state.velocity, state.target - state.position);
    lens.style.transform =
      `translate3d(${state.position.toFixed(3)}px,0,0) scaleX(${stretch.toFixed(4)})`;
  }, []);

  const animateLens = useCallback(function frame(timestamp) {
    frameRef.current = 0;
    const state = springRef.current;
    const seconds = state.lastTime
      ? Math.max(0, Math.min((timestamp - state.lastTime) / 1000, 0.04))
      : 1 / 60;
    state.lastTime = timestamp;

    if (document.hidden || reducedMotionRef.current) {
      state.position = state.target;
      state.velocity = 0;
    } else {
      const next = advanceNavSpring(state, state.target, seconds);
      state.position = next.position;
      state.velocity = next.velocity;
      if (isNavSpringSettled(state.position, state.velocity, state.target)) {
        state.position = state.target;
        state.velocity = 0;
      }
    }
    paintLens();
    if (state.position !== state.target || state.velocity !== 0) {
      frameRef.current = requestAnimationFrame(frame);
    }
  }, [paintLens]);

  useLayoutEffect(() => {
    if (!layout || !lensRef.current) return;
    const state = springRef.current;
    const changedWidth = Math.abs(state.width - layout.lens.width) > 0.5;
    state.target = layout.lens.left;
    state.width = layout.lens.width;

    // First paint, resize and accessibility modes must never jump or animate.
    const snap = !Number.isFinite(state.position) || changedWidth ||
      reducedMotionRef.current || document.hidden;
    if (snap) {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
      frameRef.current = 0;
      state.position = state.target;
      state.velocity = 0;
      state.lastTime = 0;
      paintLens();
      return;
    }
    // Retarget the *existing* motion. Even rapid taps preserve velocity:
    // nothing remounts, resets, or queues another transition.
    if (!frameRef.current) {
      state.lastTime = 0;
      frameRef.current = requestAnimationFrame(animateLens);
    }
  }, [layout, animateLens, paintLens]);

  useEffect(() => {
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    const snap = () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
      frameRef.current = 0;
      const state = springRef.current;
      state.position = state.target;
      state.velocity = 0;
      state.lastTime = 0;
      paintLens();
    };
    const onMotionChange = () => {
      reducedMotionRef.current = Boolean(media?.matches);
      if (reducedMotionRef.current) snap();
    };
    reducedMotionRef.current = Boolean(media?.matches);
    if (reducedMotionRef.current) snap();
    // A hidden tab should not resume midway through a stale frame.
    const onVisibilityChange = () => { if (document.hidden) snap(); };
    media?.addEventListener?.('change', onMotionChange);
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
      frameRef.current = 0;
      media?.removeEventListener?.('change', onMotionChange);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [paintLens]);

  return <nav className="vh-bottom" aria-label="Główna nawigacja">
    <div ref={trackRef} className={'vh-nav-items' + (layout ? ' is-ready' : '')} data-active={active}>
      {layout && <div ref={lensRef} className="vh-nav-lens" aria-hidden="true"
        style={{ width: layout.lens.width }}>
        <StaticGlass />
      </div>}
      {NAV.map(({ id, label, Icon }, index) => {
        const selected = active === id;
        const slot = layout?.items[index];
        return <button key={id} type="button" aria-label={label}
          aria-current={selected ? 'page' : undefined}
          onClick={() => onNavigate(id)}
          className={'vh-nav-item' + (selected ? ' active' : '')}
          style={slot ? { flexGrow: selected ? 2.5 : 1 } : { visibility: 'hidden' }}>
          <Icon size={23} strokeWidth={selected ? 2.3 : 1.8}
            fill={selected && id === 'favorites' ? 'currentColor' : 'none'} />
          <span>{label}</span>
        </button>;
      })}
    </div>
  </nav>;
}

export default memo(BottomNav);
