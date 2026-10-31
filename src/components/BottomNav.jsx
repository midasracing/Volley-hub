import { memo, useLayoutEffect, useRef, useState } from 'react';
import useFluidGlass from '../hooks/useFluidGlass.js';
import { NAV } from '../navigation.js';
import './BottomNav.css';

// Persistent overlay. All WebGL state survives page transitions.
function NavGlass({ hostRef, active }) {
  const Glass = useFluidGlass();
  const [placement, setPlacement] = useState({ position: [0.23, 0.5], size: 116 });

  useLayoutEffect(() => {
    const host = hostRef.current;
    const track = host?.querySelector('.vh-nav-items');
    if (!host || !track) return undefined;
    const index = NAV.findIndex(item => item.id === active);
    if (index < 0) return undefined;
    const update = () => {
      const styles = getComputedStyle(track);
      const leftPadding = parseFloat(styles.paddingLeft) || 0;
      const rightPadding = parseFloat(styles.paddingRight) || 0;
      const gap = parseFloat(styles.columnGap) || 0;
      const available = track.clientWidth - leftPadding - rightPadding - gap * (NAV.length - 1);
      if (available <= 0 || host.clientWidth <= 0 || host.clientHeight <= 0) return;

      // Track uses one 2.5fr slot and three 1fr slots. Compute the *final*
      // center directly: no layout reads or React updates during the animation.
      const small = available / (NAV.length - 1 + 2.5);
      const selectedWidth = small * 2.5;
      const x = track.offsetLeft + leftPadding + index * (small + gap) + selectedWidth / 2;
      const y = track.offsetTop + track.clientHeight / 2;
      const next = { position: [x / host.clientWidth, y / host.clientHeight], size: selectedWidth };
      setPlacement(previous =>
        Math.abs(previous.position[0] - next.position[0]) < 0.001 &&
        Math.abs(previous.position[1] - next.position[1]) < 0.001 &&
        Math.abs(previous.size - next.size) < 0.5 ? previous : next
      );
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(host);
    return () => observer.disconnect();
  }, [active, hostRef]);

  return Glass ? <div className="vh-glass-layer" aria-hidden="true"><Glass
    text="" shape="pill" shapes={['pill']} size={placement.size} position={placement.position}
    interaction="static" smoothness={0.48} morphOnClick={false} idle={false} spin={0} wobble={0}
    refraction={1.08} dispersion={0} reflection={0.7} tint={0.08} shadow={0.12}
    color="#ffffff" intro={false} maxDevicePixelRatio={2}
  /></div> : null;
}
function BottomNav({ active, onNavigate }) {
  const hostRef = useRef(null);
  return <nav ref={hostRef} className="vh-bottom" aria-label="Główna nawigacja"><NavGlass hostRef={hostRef} active={active} /><div className="vh-nav-items" data-active={active}>{NAV.map(({ id, label, Icon }) => <button key={id} onClick={() => onNavigate(id)} className={'vh-nav-item ' + (active === id ? 'active' : '')} type="button" aria-current={active === id ? 'page' : undefined} aria-label={label}><Icon size={23} strokeWidth={active === id ? 2.3 : 1.8} fill={active === id && id === 'favorites' ? 'currentColor' : 'none'} /><span>{label}</span></button>)}</div></nav>;
}

export default memo(BottomNav);
