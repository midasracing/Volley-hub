import { useContext, useLayoutEffect, useRef, useState } from 'react';
import { dateKey } from '../data.js';
import { MotionEnabled } from './MatchMotion.jsx';
import './ScheduleMotion.css';

const cancel = animations => { animations.splice(0).forEach(animation => animation.cancel()); };
function play(element, frames, options, animations) {
  if (!element?.animate) return;
  const animation = element.animate(frames, { fill: 'both', easing: 'cubic-bezier(.16,1,.3,1)', ...options });
  animations.push(animation);
  animation.finished.then(() => animation.cancel()).catch(() => {});
}

// The calendar responds immediately. Only the outgoing result cards stay for
// 180ms, then the latest requested day enters. Rapid taps cancel pending work.
export function useAnimatedDate(selectedDate, results) {
  const enabled = useContext(MotionEnabled);
  const [displayedDate, setDisplayedDate] = useState(selectedDate);
  const selectedKey = dateKey(selectedDate), displayedKey = dateKey(displayedDate);
  const previous = useRef(displayedKey);
  const direction = useRef(1);
  const entering = useRef([]), leaving = useRef([]);
  useLayoutEffect(() => {
    cancel(entering.current);
    cancel(leaving.current);
    if (selectedKey === displayedKey) return undefined;
    direction.current = selectedKey > displayedKey ? 1 : -1;
    const host = results.current;
    const cards = Array.from(host?.querySelectorAll('.vh-match, .vh-empty') || []).slice(0, 8);
    if (!enabled || document.hidden || host?.closest('[hidden]') || !cards.length || !cards[0].animate) {
      setDisplayedDate(selectedDate);
      return undefined;
    }
    cards.forEach((card, index) => play(card, [
      { opacity: 1, transform: 'translate3d(0,0,0)' },
      { opacity: 0, transform: `translate3d(${-direction.current * 24}px,0,0)` },
    ], { duration: 150, delay: Math.min(index * 6, 18), easing: 'cubic-bezier(.4,0,1,1)' }, leaving.current));
    const timer = window.setTimeout(() => setDisplayedDate(selectedDate), 180);
    return () => { window.clearTimeout(timer); cancel(leaving.current); };
    // displayedDate is the committed result of this transition, not a new request.
  }, [selectedKey, enabled, results]);
  useLayoutEffect(() => {
    const changed = previous.current !== displayedKey;
    previous.current = displayedKey;
    cancel(leaving.current);
    cancel(entering.current);
    const host = results.current;
    if (!changed || !enabled || document.hidden || host?.closest('[hidden]')) return undefined;
    Array.from(host?.querySelectorAll('.vh-match, .vh-empty') || []).slice(0, 8).forEach((card, index) => play(card, [
      { opacity: 0, transform: `translate3d(${direction.current * 32}px,16px,0)` },
      { opacity: 1, transform: 'translate3d(0,0,0)' },
    ], { duration: 460, delay: Math.min(index * 55, 220) }, entering.current));
    return () => cancel(entering.current);
  }, [displayedKey, enabled, results]);
  return displayedDate;
}

export function AnimatedSets({ scores, expanded, detailsId }) {
  const enabled = useContext(MotionEnabled);
  const host = useRef(null);
  const previous = useRef(false);
  useLayoutEffect(() => {
    const changed = previous.current !== expanded;
    previous.current = expanded;
    const animations = [];
    if (!changed || !enabled || document.hidden || host.current?.closest('[hidden]')) return undefined;
    const cells = Array.from(host.current?.children || []);
    cells.forEach((cell, index) => play(cell, expanded ? [
      { opacity: 0, transform: 'translateY(14px) scale(.95)' },
      { opacity: 1, transform: 'translateY(0) scale(1)' },
    ] : [
      { opacity: 1, transform: 'translateY(0)' },
      { opacity: 0, transform: 'translateY(-8px)' },
    ], { duration: expanded ? 340 : 120, delay: expanded ? index * 45 : (cells.length - index - 1) * 20 }, animations));
    return () => cancel(animations);
  }, [expanded, enabled]);
  return <div className={'vh-sets-wrap' + (expanded ? ' is-expanded' : '')} aria-hidden={!expanded} inert={!expanded}>
    <div ref={host} id={detailsId} className="vh-sets" role="region" aria-label="Wyniki setów">
      {scores.map((set, index) => <span key={index}><small>SET {index + 1}</small><strong>{set}</strong></span>)}
    </div>
  </div>;
}
