import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { StaticGlassSurface } from './react-bits/GlassSurface.jsx';
import { NAV } from '../navigation.js';
import { calculateNavLayout } from './navLayout.js';
import { planNavMotion, sampleNavMotion, navLensStretch } from './navSpring.js';
import './BottomNav.css';

// A static material can move as a cached texture. Sampling/filtering the page
// underneath it on every frame defeats compositor-only transform animation.
const StaticGlass = memo(function StaticGlass() {
  return <StaticGlassSurface className="vh-react-glass" />;
});

const lensTransform = (position, stretch = 1) =>
  `translate3d(${position.toFixed(3)}px,0,0) scaleX(${stretch.toFixed(4)})`;

function BottomNav({ active, onNavigate }) {
  const trackRef = useRef(null);
  const lensRef = useRef(null);
  const animationRef = useRef(null);
  const motionRef = useRef(null);
  const reducedMotionRef = useRef(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true);
  const springRef = useRef({
    position: NaN, velocity: 0, target: 0, width: 0
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

  const snapLens = useCallback(() => {
    animationRef.current?.cancel();
    animationRef.current = null;
    const state = springRef.current;
    state.position = state.target;
    state.velocity = 0;
    if (lensRef.current) lensRef.current.style.transform = lensTransform(state.target);
  }, []);

  useLayoutEffect(() => {
    const lens = lensRef.current;
    if (!layout || !lens) return;
    const state = springRef.current;
    const previous = animationRef.current;
    if (previous && motionRef.current) {
      Object.assign(state, sampleNavMotion(motionRef.current, Number(previous.currentTime) || 0));
    }
    previous?.cancel();
    animationRef.current = null;
    const changedWidth = Math.abs(state.width - layout.lens.width) > 0.5;
    state.target = layout.lens.left;
    state.width = layout.lens.width;

    if (!Number.isFinite(state.position) || changedWidth || reducedMotionRef.current ||
        document.hidden || typeof lens.animate !== 'function') {
      snapLens();
      return;
    }
    const motion = planNavMotion(state, state.target);
    motionRef.current = motion;
    // The underlying style is the destination, so no finished animations need
    // fill:forwards or a per-frame JS writer. Retarget from the current sample.
    lens.style.transform = lensTransform(state.target);
    const animation = lens.animate(motion.samples.map(sample => ({
      transform: lensTransform(sample.position,
        navLensStretch(sample.velocity, state.target - sample.position))
    })), { duration: motion.duration, easing: 'linear' });
    animationRef.current = animation;
    animation.onfinish = () => {
      if (animationRef.current !== animation) return;
      animationRef.current = null;
      state.position = state.target;
      state.velocity = 0;
    };
  }, [layout, snapLens]);

  useEffect(() => {
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    const onMotionChange = () => {
      reducedMotionRef.current = Boolean(media?.matches);
      if (reducedMotionRef.current) snapLens();
    };
    onMotionChange();
    const onVisibilityChange = () => { if (document.hidden) snapLens(); };
    media?.addEventListener?.('change', onMotionChange);
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      animationRef.current?.cancel();
      animationRef.current = null;
      media?.removeEventListener?.('change', onMotionChange);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [snapLens]);

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
