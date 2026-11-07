import { useContext, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { WEEKDAYS, dateKey, addDays } from '../data.js';
import { DATE_FORMAT, MONTH_FORMAT, NOW } from '../dateUtils.js';
import { MotionEnabled } from './MatchMotion.jsx';

const CALENDAR_RADIUS = 90;
const CALENDAR_EDGE_DAYS = 20;
const CALENDAR_SHIFT_DAYS = 42;

export default function DateStrip({ selected, onSelect }) {
  const strip = useRef(null);
  const marker = useRef(null);
  const enabled = useContext(MotionEnabled);
  const [anchor, setAnchor] = useState(selected);
  const [visibleMonth, setVisibleMonth] = useState(() => MONTH_FORMAT.format(selected));
  const pendingRebase = useRef(null);
  const selectedKey = dateKey(selected), anchorKey = dateKey(anchor);
  const lastExternallySelected = useRef(selectedKey);
  const todayKey = dateKey(NOW());
  const previous = useRef({ selected: null, anchor: null, width: 0 });
  // Keep a bounded window of 181 days. When the user approaches either edge,
  // recycle off-screen dates instead of exposing the blank spacer at its end.
  const days = useMemo(() => Array.from({ length: CALENDAR_RADIUS * 2 + 1 },
    (_, index) => addDays(anchor, index - CALENDAR_RADIUS)), [anchorKey]);
  useLayoutEffect(() => {
    // Swiping may move far beyond the selected day. Do not pull the strip
    // back to that day when it leaves the recycled window.
    if (lastExternallySelected.current === selectedKey) return;
    lastExternallySelected.current = selectedKey;
    if (days.some(day => dateKey(day) === selectedKey)) return;
    pendingRebase.current = null;
    setAnchor(selected);
  }, [selectedKey, days]);

  useLayoutEffect(() => {
    const host = strip.current, pill = marker.current;
    if (!host || !pill) return undefined;
    const last = previous.current;
    const shift = pendingRebase.current;
    if (shift) {
      const reference = host.querySelector('.im-day[data-day="' + shift.key + '"]');
      if (reference) {
        // Chrome and Safari may already scroll-anchor when we recycle dates.
        // Correct only the residual pixel movement, never a full chunk twice.
        const movedBy = (reference.offsetLeft - host.scrollLeft) - shift.viewportLeft;
        if (Math.abs(movedBy) > 0.5) host.scrollLeft += movedBy;
      }
      pendingRebase.current = null;
    }
    const updateMarker = smooth => {
      const active = host.querySelector('[aria-selected="true"]');
      if (!active) {
        // The selected day may be far outside the recycled window.
        // Do not leave its red indicator drawn over an unrelated date.
        host.classList.remove('has-date-indicator');
        return null;
      }
      pill.style.transitionDuration = smooth ? '' : '0s';
      pill.style.width = active.offsetWidth + 'px';
      pill.style.height = active.offsetHeight + 'px';
      pill.style.top = active.offsetTop + 'px';
      pill.style.transform = 'translate3d(' + active.offsetLeft + 'px,0,0)';
      host.classList.add('has-date-indicator');
      return active;
    };
    const center = smooth => {
      if (!host.clientWidth) { previous.current.width = 0; return; }
      const active = updateMarker(smooth);
      if (!active) return;
      const left = Math.max(0, active.offsetLeft + active.offsetWidth / 2 - host.clientWidth / 2);
      host.scrollTo({ left, behavior: smooth ? 'smooth' : 'auto' });
      setVisibleMonth(MONTH_FORMAT.format(selected));
      previous.current = { selected: selectedKey, anchor: anchorKey, width: host.clientWidth };
    };
    const selectionChanged = last.selected !== selectedKey;
    if (selectionChanged || (!shift && host.clientWidth !== last.width)) {
      center(enabled && last.selected !== null && last.anchor === anchorKey && selectionChanged);
    } else {
      // A scroll-triggered window shift must NOT jump back to the selected day.
      updateMarker(false);
      previous.current = { selected: selectedKey, anchor: anchorKey, width: host.clientWidth };
    }
    const observer = new ResizeObserver(() => {
      if (host.clientWidth !== previous.current.width) center(false);
    });
    observer.observe(host);
    return () => observer.disconnect();
  }, [selectedKey, anchorKey, enabled]);

  const onStripScroll = () => {
    const host = strip.current;
    if (!host) return;
    const first = host.querySelector('.im-day');
    const last = host.querySelector('.im-day:last-child');
    if (!first || !last || !first.offsetWidth) return;
    const center = host.scrollLeft + host.clientWidth / 2;
    const dayWidth = first.offsetWidth;
    const index = Math.max(0, Math.min(days.length - 1,
      Math.round((center - first.offsetLeft - dayWidth / 2) / dayWidth)));
    const month = MONTH_FORMAT.format(days[index]);
    setVisibleMonth(previousMonth => previousMonth === month ? previousMonth : month);
    if (pendingRebase.current) return;
    const distanceToLeft = center - first.offsetLeft;
    const distanceToRight = last.offsetLeft + last.offsetWidth - center;
    const delta = distanceToLeft < dayWidth * CALENDAR_EDGE_DAYS ? -CALENDAR_SHIFT_DAYS
      : distanceToRight < dayWidth * CALENDAR_EDGE_DAYS ? CALENDAR_SHIFT_DAYS : 0;
    if (!delta) return;
    const reference = host.querySelector('.im-day[data-day="' + anchorKey + '"]');
    if (!reference) return;
    pendingRebase.current = {
      key: anchorKey, viewportLeft: reference.offsetLeft - host.scrollLeft
    };
    setAnchor(current => addDays(current, delta));
  };
  return <div className="im-strip-wrap vh-date-wrap">
    <h1 className="vh-calendar-month">{visibleMonth}</h1>
    <div className="im-strip" role="tablist" aria-label="Wybierz dzień" ref={strip} onScroll={onStripScroll}>
      <span ref={marker} className="vh-date-indicator" aria-hidden="true" />
      {days.map(day => {
        const key = dateKey(day);
        const active = key === selectedKey;
        return <button className={'im-day ' + (active ? 'is-sel ' : '') + (key === todayKey ? 'is-today' : '')} role="tab" data-day={key} aria-selected={active} aria-label={DATE_FORMAT.format(day)} onClick={() => onSelect(day)} key={key} type="button">
          <b>{day.getDate()}</b><span>{WEEKDAYS[day.getDay()]}</span>
        </button>;
      })}
    </div>
  </div>;
}
