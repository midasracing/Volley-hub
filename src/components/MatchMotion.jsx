import { createContext, useContext, useEffect, useLayoutEffect, useRef, useState } from 'react';
import './MatchMotion.css';

export const MotionEnabled = createContext(true);

// Decorative only: real scores and headings always remain accessible DOM text.
export function RiveImpact({ className = '' }) {
  const enabled = useContext(MotionEnabled);
  const canvas = useRef(null);
  const [ready, setReady] = useState(false);
  const [done, setDone] = useState(false);
  useEffect(() => {
    if (done || !enabled || document.hidden || !canvas.current?.getClientRects().length ||
        canvas.current.closest('[hidden]')) return undefined;
    let disposed = false, animation;
    const finish = () => { if (!disposed) { animation?.pause(); setDone(true); } };
    // Never play a delayed flash if a slow device/network misses this interaction.
    const deadline = performance.now() + 450;
    const timeout = window.setTimeout(finish, 1200);
    import('../motionRuntime.js').then(({ createImpact }) => {
      if (disposed || performance.now() > deadline) return finish();
      animation = createImpact(canvas.current, () => {
        if (disposed) return;
        if (performance.now() > deadline) finish();
        else setReady(true);
      }, finish);
    }).catch(finish);
    return () => { disposed = true; window.clearTimeout(timeout); animation?.cleanup(); };
  }, [enabled, done]);
  if (!enabled || done) return null;
  return <canvas ref={canvas} className={'vh-rive-impact ' + className + (ready ? ' is-ready' : '')}
    aria-hidden="true" />;
}

export function ScoreValue({ value, className = '' }) {
  const enabled = useContext(MotionEnabled);
  const host = useRef(null);
  const previous = useRef(value);
  const [change, setChange] = useState(null);
  useLayoutEffect(() => {
    const from = previous.current;
    previous.current = value;
    if (Object.is(from, value)) return undefined;
    if (!enabled || document.hidden || host.current?.closest('[hidden]')) {
      setChange(null);
      return undefined;
    }
    setChange({ from, value });
    const timeout = window.setTimeout(() => setChange(null), 800);
    return () => window.clearTimeout(timeout);
  }, [value, enabled]);
  const changing = enabled && change && Object.is(change.value, value);
  return <span ref={host} className={className + ' vh-score' + (changing ? ' is-changing' : '')}
    data-previous={changing ? String(change.from) : undefined}>
    {changing && <RiveImpact key={String(value)} className="vh-score-impact" />}
    <span key={String(value)} className="vh-score-window" data-previous={changing ? String(change.from) : undefined}>
      <span className="vh-score-current">{value}</span>
    </span>
  </span>;
}

export function LeagueEntrance({ league, active, children }) {
  const enabled = useContext(MotionEnabled);
  return <div className={'vh-league-cover vh-league-entrance' + (enabled && active ? ' has-motion' : '')}>
    {enabled && active && <RiveImpact key={league.id} className="vh-league-impact" />}
    <div className="vh-league-copy">{children}</div>
  </div>;
}
