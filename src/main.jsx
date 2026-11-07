import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, startTransition } from 'react';
import { createRoot } from 'react-dom/client';
import { createPortal } from 'react-dom';
import { dateKey, feedDateKey, matchesFromFeeds, teamIndex, normalizeName, readFavorites } from './data.js';
import { NOW } from './dateUtils.js';
import { sameName } from './nameUtils.js';
import BrandSignature from './components/BrandSignature.jsx';
import StartupEntrance from './components/StartupEntrance.jsx';
import BottomNav from './components/BottomNav.jsx';
import PageStage from './components/PageStage.jsx';
import useFeeds from './useFeeds.js';
import { MotionEnabled } from './components/MatchMotion.jsx';
import { ROUTES } from './navigation.js';
import HomePage from './pages/HomePage.jsx';
import MatchesPage from './pages/MatchesPage.jsx';
import CompetitionsPage from './pages/CompetitionsPage.jsx';
import FavoritesPage from './pages/FavoritesPage.jsx';
import '../matches-ios.css';
import './app.css';
import './theme.css';

function App() {
  const route = () => { const hash = window.location.hash.replace(/^#\/?/, ''); return ROUTES.includes(hash) ? hash : 'home'; };
  const [page, setPage] = useState(route);
  const [visitedPages, setVisitedPages] = useState(() => [page]);
  const [direction, setDirection] = useState('forward');
  const [reducedMotion, setReducedMotion] = useState(() =>
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true
  );
  useEffect(() => {
    if (reducedMotion) return undefined;
    const warm = () => import('./motionRuntime.js').catch(() => {});
    if (window.requestIdleCallback) {
      const task = window.requestIdleCallback(warm, { timeout: 2500 });
      return () => window.cancelIdleCallback(task);
    }
    const task = window.setTimeout(warm, 1500);
    return () => window.clearTimeout(task);
  }, [reducedMotion]);
  const startupPage = useRef(page);
  const [startup, setStartup] = useState(() =>
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches !== true);
  const finishStartup = useCallback(() => setStartup(false), []);
  useEffect(() => {
    if (page !== startupPage.current || reducedMotion) finishStartup();
  }, [page, reducedMotion, finishStartup]);
  const currentPage = useRef(page);
  const [selectedDate, setSelectedDate] = useState(NOW);
  const [leagueFilter, setLeagueFilter] = useState(null);
  const [selectedLeague, setSelectedLeague] = useState(null);
  const [favorites, setFavorites] = useState(readFavorites);
  const { feeds, errors, loading, refresh } = useFeeds();
  // A single normalized/sorted feed shared by all tabs. Avoid expensive
  // duplicate sorting on every page mount, especially on older iPhones.
  const matches = useMemo(() => matchesFromFeeds(feeds), [feeds.men?.matches, feeds.first?.matches, feeds.second?.matches, feeds.pomorska?.matches, feeds.italy?.matches, feeds.japan?.matches]);
  const teams = useMemo(() => teamIndex(feeds), [feeds.men?.teams, feeds.first?.teams, feeds.second?.teams, feeds.pomorska?.teams, feeds.italy?.teams, feeds.japan?.teams]);
  const logos = useMemo(() => new Map(teams.filter(team => team.logo).map(team => [normalizeName(team.name), team.logo])), [teams]);
  const switchPage = useCallback(id => {
    if (!ROUTES.includes(id) || currentPage.current === id) return;
    const previous = currentPage.current;
    currentPage.current = id;
    // Render the page and the selected tab in the SAME React update.
    // Deferring the page made the bar jump ahead of the content on Safari.
    const nextDirection = ROUTES.indexOf(id) < ROUTES.indexOf(previous) ? 'backward' : 'forward';
    setDirection(nextDirection);
    setVisitedPages(previous => previous.includes(id) ? previous : [...previous, id]);
    setPage(id);
  }, []);
  // Only four bounded tabs: prepare one hidden panel at a time after data
  // arrives. Low-priority renders can yield to a tap; subsequent navigation
  // only toggles visibility, including the first visit after the app settles.
  useEffect(() => {
    if (loading) return undefined;
    const next = ROUTES.find(id => !visitedPages.includes(id));
    if (!next) return undefined;
    const prepare = () => startTransition(() => {
      setVisitedPages(previous => previous.includes(next) ? previous : [...previous, next]);
    });
    if (window.requestIdleCallback) {
      const task = window.requestIdleCallback(prepare, { timeout: 2000 });
      return () => window.cancelIdleCallback(task);
    }
    const task = window.setTimeout(prepare, 150);
    return () => window.clearTimeout(task);
  }, [loading, visitedPages]);
  const navigate = useCallback(id => {
    if (!ROUTES.includes(id)) return;
    if (currentPage.current === id) window.scrollTo({ top: 0, behavior: 'instant' });
    switchPage(id);
    if (window.location.hash !== '#' + id) window.history.pushState(null, '', '#' + id);
  }, [switchPage]);
  useEffect(() => {
    const sync = () => switchPage(route());
    window.addEventListener('hashchange', sync);
    window.addEventListener('popstate', sync);
    return () => {
      window.removeEventListener('hashchange', sync);
      window.removeEventListener('popstate', sync);
    };
  }, [switchPage]);
  // Reset after the new panel is visible, avoiding layout of the outgoing list.
  useLayoutEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' });
  }, [page]);
  useEffect(() => {
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if (!media) return undefined;
    const onChange = () => setReducedMotion(media.matches);
    media.addEventListener?.('change', onChange);
    return () => media.removeEventListener?.('change', onChange);
  }, []);
  useEffect(() => {
    try { localStorage.setItem('vh-favs', JSON.stringify(favorites)); } catch { /* storage may be blocked */ }
  }, [favorites]);
  useEffect(() => {
    if ('serviceWorker' in navigator && import.meta.env.PROD && location.protocol.startsWith('http')) {
      navigator.serviceWorker.register(import.meta.env.BASE_URL + 'sw.js').catch(() => {});
    }
  }, []);
  const openLeague = useCallback(id => {
    if (!id) return;
    setSelectedLeague(id);
    navigate('competitions');
  }, [navigate]);
  const goToMatches = useCallback(id => {
    setLeagueFilter(id || null);
    navigate('matches');
  }, [navigate]);
  const toggleFavorite = useCallback((type, name) => {
    setFavorites(current => {
      const exists = current[type].some(value => sameName(value, name));
      return { ...current, [type]: exists ? current[type].filter(value => !sameName(value, name)) : [...current[type], name] };
    });
  }, []);
  function renderPage(id) {
    if (id === 'home') return <HomePage feeds={feeds} matches={matches} loading={loading} errors={errors} refresh={refresh} logos={logos} />;
    if (id === 'matches') return <MatchesPage feeds={feeds} matches={matches} loading={loading} errors={errors} refresh={refresh} logos={logos} selectedDate={selectedDate} setSelectedDate={setSelectedDate} leagueFilter={leagueFilter} setLeagueFilter={setLeagueFilter} />;
    if (id === 'competitions') return <CompetitionsPage active={page === 'competitions'} feeds={feeds} matches={matches} loading={loading} errors={errors} refresh={refresh} logos={logos} favorites={favorites} toggleFavorite={toggleFavorite} selectedLeague={selectedLeague} setSelectedLeague={setSelectedLeague} onMatches={goToMatches} />;
    if (id === 'favorites') return <FavoritesPage teams={teams} logos={logos} favorites={favorites} toggleFavorite={toggleFavorite} onOpenLeague={openLeague} />;
    return null;
  }
  return <MotionEnabled.Provider value={!reducedMotion}><div className="vh-app" id="ios-matches" data-page={page}>
    <div className="vh-floating-head" aria-label="Nagłówek Kiedy Siatka?">
      <BrandSignature />
      {page === 'home' && <h2 className="vh-home-heading">{matches.some(match => feedDateKey(match.date) === dateKey(NOW())) ? 'Dzisiaj' : 'Najbliższe mecze'}</h2>}
    </div>
    <PageStage page={page} direction={direction} reducedMotion={reducedMotion}>
      {visitedPages.map(id => <div key={id} className="vh-tab-panel" data-route={id} hidden={page !== id} inert={page !== id}>
        {renderPage(id)}
      </div>)}
    </PageStage>
    {startup && <StartupEntrance enabled={!reducedMotion && page === startupPage.current} onComplete={finishStartup} />}
    {createPortal(<BottomNav active={page} onNavigate={navigate} />, document.body)}
  </div></MotionEnabled.Provider>;
}

createRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>);
