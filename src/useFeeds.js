import { useCallback, useEffect, useRef, useState } from 'react';
import { LEAGUES, fetchLeague, isLive } from './data.js';
import { FULL_REFRESH_MS, LIVE_REFRESH_MS } from './feedUpdates.js';

export default function useFeeds() {
  const [feeds, setFeeds] = useState({});
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(true);
  const feedsRef = useRef({});
  const refreshRef = useRef(() => {});

  useEffect(() => {
    let stopped = false, timer = 0, controller = null, queuedFull = false, lastFull = 0;
    const liveLeagues = () => LEAGUES.filter(league => feedsRef.current[league.id]?.matches?.some(isLive));
    function schedule() {
      window.clearTimeout(timer);
      if (stopped || document.hidden) return;
      const fullDue = Math.max(1000, lastFull + FULL_REFRESH_MS - Date.now());
      timer = window.setTimeout(() => load(), liveLeagues().length ? Math.min(LIVE_REFRESH_MS, fullDue) : fullDue);
    }
    async function load(forceFull = false) {
      if (stopped || document.hidden) return;
      window.clearTimeout(timer);
      if (controller) { queuedFull ||= forceFull; return; }
      const full = forceFull || Date.now() - lastFull >= FULL_REFRESH_MS;
      const leagues = full ? LEAGUES : liveLeagues();
      if (!leagues.length) { schedule(); return; }
      const request = new AbortController();
      controller = request;
      try {
        const results = await Promise.all(leagues.map(async league => {
          try { return { id: league.id, data: await fetchLeague(league, request.signal) }; }
          catch (error) { return { id: league.id, error }; }
        }));
        if (stopped || request.signal.aborted) return;
        let next = feedsRef.current;
        for (const result of results) {
          if (result.data && result.data !== next[result.id]) {
            if (next === feedsRef.current) next = { ...next };
            next[result.id] = result.data;
          }
        }
        feedsRef.current = next;
        setFeeds(previous => previous === next ? previous : next);
        setErrors(previous => {
          const nextErrors = { ...previous };
          for (const result of results) {
            if (result.error) nextErrors[result.id] = result.error.message;
            else delete nextErrors[result.id];
          }
          return Object.keys(previous).length === Object.keys(nextErrors).length &&
            Object.keys(nextErrors).every(id => nextErrors[id] === previous[id]) ? previous : nextErrors;
        });
        setLoading(false);
        if (full) lastFull = Date.now();
      } finally {
        controller = null;
        if (!stopped && queuedFull) { queuedFull = false; load(true); }
        else schedule();
      }
    }
    const refresh = () => load(true);
    const onVisibility = () => {
      window.clearTimeout(timer);
      if (document.hidden) controller?.abort();
      else load(true);
    };
    refreshRef.current = refresh;
    document.addEventListener('visibilitychange', onVisibility);
    load(true);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      controller?.abort();
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);
  const refresh = useCallback(() => refreshRef.current(), []);
  return { feeds, errors, loading, refresh };
}
