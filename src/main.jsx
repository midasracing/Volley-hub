import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, startTransition } from 'react';
import { createRoot } from 'react-dom/client';
import { createPortal } from 'react-dom';
import { Trophy, Heart, Search, ArrowRight, ArrowLeft, Star, ChevronRight, ChevronLeft, WifiOff, Check } from 'lucide-react';
import {
  LEAGUES, CATEGORIES, dateKey, feedDateKey,
  isFinished, matchesFromFeeds, teamIndex, normalizeName, readFavorites
} from './data.js';
import BrandSignature from './components/BrandSignature.jsx';
import StartupEntrance from './components/StartupEntrance.jsx';
import { useAnimatedDate } from './components/ScheduleMotion.jsx';
import BottomNav from './components/BottomNav.jsx';
import PageStage from './components/PageStage.jsx';
import useFeeds from './useFeeds.js';
import { MotionEnabled, LeagueEntrance } from './components/MatchMotion.jsx';
import { ROUTES } from './navigation.js';
import { NOW } from './dateUtils.js';
import DateStrip from './components/DateStrip.jsx';
import TeamLogo from './components/TeamLogo.jsx';
import { SectionTitle, EmptyState, FeedWarning, LoadingCards, PageHeader, IconButton } from './components/UiPrimitives.jsx';
import { MatchGroups } from './components/MatchCards.jsx';
import '../matches-ios.css';
import './app.css';
import './theme.css';

const leagueByName = name => LEAGUES.find(item => item.name === name);
const sameName = (a, b) => normalizeName(a) === normalizeName(b);

const MatchesPage = React.memo(function MatchesPage({ feeds, matches, loading, errors, refresh, logos, selectedDate, setSelectedDate, leagueFilter, setLeagueFilter }) {
  const resultsRef = useRef(null);
  const displayedDate = useAnimatedDate(selectedDate, resultsRef);
  const [groupFilter, setGroupFilter] = useState('all');
  const all = useMemo(() => leagueFilter ? matches.filter(match => match.leagueId === leagueFilter) : matches, [matches, leagueFilter]);
  const groups = [...new Set(all.filter(match => match.leagueId === 'second').map(match => match.group).filter(Boolean))];
  const filtered = all.filter(match => feedDateKey(match.date) === dateKey(displayedDate) && (groupFilter === 'all' || match.leagueId !== 'second' || match.group === groupFilter));
  const updateLeague = id => { setLeagueFilter(id); setGroupFilter('all'); };
  return <>
    <DateStrip selected={selectedDate} onSelect={setSelectedDate} />
    <div className="vh-controls">
      <button type="button" className={'vh-filter-chip ' + (!leagueFilter ? 'chosen' : '')} onClick={() => updateLeague(null)}>Wszystkie ligi</button>
      {LEAGUES.map(league => <button className={'vh-filter-chip ' + (leagueFilter === league.id ? 'chosen' : '')} type="button" key={league.id} onClick={() => updateLeague(league.id)}>{league.short}</button>)}
    </div>
    {leagueFilter === 'second' && <div className="vh-controls vh-secondary-filters"><button className={'vh-filter-chip ' + (groupFilter === 'all' ? 'chosen' : '')} onClick={() => setGroupFilter('all')}>Wszystkie grupy</button>{groups.map(group => <button key={group} className={'vh-filter-chip ' + (groupFilter === group ? 'chosen' : '')} onClick={() => setGroupFilter(group)}>{group}</button>)}</div>}
    <FeedWarning errors={errors} refresh={refresh} />
    <div className="vh-day-results" ref={resultsRef} data-day={dateKey(displayedDate)} aria-busy={dateKey(displayedDate) !== dateKey(selectedDate)}>
    {loading && !Object.keys(feeds).length ? <LoadingCards /> : <MatchGroups matches={filtered} logos={logos} emptyMessage="Nie znaleziono meczów na wybrany dzień. Przesuń kalendarz lub wybierz inną ligę." />}
    </div>
    <p className="vh-source-note">Dane pochodzą z oficjalnych źródeł rozgrywek. Wyniki aktualizują się automatycznie, gdy aplikacja jest aktywna.</p>
  </>;
});

const HomePage = React.memo(function HomePage({ feeds, matches, loading, errors, refresh, logos }) {
  const allMatches = matches;
  const today = dateKey(NOW());
  const todayMatches = allMatches.filter(match => feedDateKey(match.date) === today);
  const upcoming = allMatches.filter(match => feedDateKey(match.date) >= today).slice(0, 3);
  const featured = todayMatches.length ? todayMatches : upcoming;
  return <>
    <FeedWarning errors={errors} refresh={refresh} />
    {loading && !Object.keys(feeds).length ? <LoadingCards /> : <MatchGroups compact matches={featured} logos={logos} emptyMessage="Nie mamy jeszcze zaplanowanych spotkań w pobranych danych." />}

  </>;
});

function Standings({ rows = [], logos }) {
  if (!rows.length) return <EmptyState title="Tabela niedostępna" message="Oficjalne źródło nie udostępnia jeszcze tabeli dla tej grupy." Icon={Trophy} />;
  return <div className="vh-table-scroll" role="region" tabIndex={0} aria-label="Tabela ligowa — przewijana poziomo">
    <table className="vh-table"><thead><tr><th scope="col">#</th><th scope="col">Drużyna</th><th scope="col">Pkt</th><th scope="col">M</th><th scope="col">W</th><th scope="col">P</th><th scope="col">Sety</th></tr></thead>
      <tbody>{rows.map((row, index) => <tr key={row.team || index}><td>{row.rank || index + 1}</td><td><span className="vh-table-team"><TeamLogo name={row.team} logo={logos.get(normalizeName(row.team))} />{row.team}</span></td><td><strong>{row.points ?? '–'}</strong></td><td>{row.played ?? '–'}</td><td>{row.wins ?? '–'}</td><td>{row.losses ?? '–'}</td><td>{row.sets_for ?? '–'}:{row.sets_against ?? '–'}</td></tr>)}</tbody></table>
  </div>;
}
function TeamsGrid({ teams = [], logos, favorites, toggleFavorite }) {
  if (!teams.length) return <EmptyState title="Brak listy drużyn" message="Lista zespołów nie jest jeszcze dostępna w oficjalnym źródle." />;
  return <div className="vh-team-grid">{teams.map((team, index) => <article className="vh-team-tile" key={team.name + index}><TeamLogo name={team.name} logo={team.logo || logos.get(normalizeName(team.name))} /><strong>{team.name}</strong><button type="button" aria-label={(favorites.teams.some(x => sameName(x, team.name)) ? 'Usuń z' : 'Dodaj do') + ' ulubionych: ' + team.name} onClick={() => toggleFavorite('teams', team.name)} className={favorites.teams.some(x => sameName(x, team.name)) ? 'is-favorite' : ''}><Star size={19} fill={favorites.teams.some(x => sameName(x, team.name)) ? 'currentColor' : 'none'} /></button></article>)}</div>;
}
const CompetitionsPage = React.memo(function CompetitionsPage({ active, feeds, matches, loading, errors, refresh, logos, favorites, toggleFavorite, selectedLeague, setSelectedLeague, onMatches }) {
  const [category, setCategory] = useState('Polska');
  const [view, setView] = useState('matches');
  const [group, setGroup] = useState('all');
  const league = LEAGUES.find(item => item.id === selectedLeague);
  const data = league ? feeds[league.id] : null;
  const grouped = league?.id === 'second' ? (data?.groups || []) : [];
  const groupChoices = group === 'all' ? grouped : grouped.filter(item => item.name === group);
  const openLeague = id => { setSelectedLeague(id); setView('matches'); setGroup('all'); };
  const all = league ? matches.filter(match => match.leagueId === league.id && (group === 'all' || match.group === group)) : [];
  const today = dateKey(NOW());
  const pageMatches = view === 'results' ? all.filter(isFinished).reverse().slice(0, 40) : all.filter(match => feedDateKey(match.date) >= today).slice(0, 25);
  return <>
    <PageHeader title="Rozgrywki" subtitle="Wybierz ligę. Poznaj drużyny, wyniki i aktualną tabelę." actions={league ? <IconButton Icon={ArrowLeft} label="Wszystkie ligi" onClick={() => setSelectedLeague(null)} /> : null} />
    {league ? <>
      <button className="vh-back" onClick={() => setSelectedLeague(null)}><ChevronLeft size={18} /> Wszystkie rozgrywki</button>
      <LeagueEntrance key={league.id} league={league} active={active}><span className="vh-eyebrow">{league.flag || '🇵🇱'} {league.category === 'Europa' ? 'WŁOCHY' : league.category === 'Świat' ? 'JAPONIA' : 'POLSKA'} · MĘŻCZYŹNI</span><h2>{league.name}</h2><p>{league.description}</p><button className="vh-cover-favorite" type="button" onClick={() => toggleFavorite('leagues', league.name)}><Star size={17} fill={favorites.leagues.includes(league.name) ? 'currentColor' : 'none'} /> {favorites.leagues.includes(league.name) ? 'W ulubionych' : 'Dodaj do ulubionych'}</button></LeagueEntrance>
      <div className="vh-segmented" role="tablist" aria-label="Widok rozgrywek">{[['matches','Mecze'], ['results','Wyniki'], ['table','Tabela'], ['teams','Drużyny']].map(([id,label]) => <button key={id} role="tab" aria-selected={view === id} className={view === id ? 'selected' : ''} onClick={() => setView(id)}>{label}</button>)}</div>
      {grouped.length > 0 && <div className="vh-controls"><button type="button" className={'vh-filter-chip ' + (group === 'all' ? 'chosen' : '')} onClick={() => setGroup('all')}>Wszystkie grupy</button>{grouped.map(item => <button key={item.name} type="button" className={'vh-filter-chip ' + (group === item.name ? 'chosen' : '')} onClick={() => setGroup(item.name)}>{item.name}</button>)}</div>}
      <FeedWarning errors={league && errors[league.id] ? { [league.id]: errors[league.id] } : {}} refresh={refresh} />
      {!data && loading ? <LoadingCards /> : !data ? <EmptyState Icon={WifiOff} title="Nie udało się pobrać ligi" message="Sprawdź połączenie i spróbuj ponownie." action="Odśwież dane" onAction={refresh} /> : <>
        {view === 'matches' && <><div className="vh-day-heading"><h2>Najbliższe mecze</h2><button className="vh-text-action" onClick={() => onMatches(league.id)}>Pełny terminarz <ArrowRight size={17} /></button></div><MatchGroups matches={pageMatches} logos={logos} emptyMessage="Brak przyszłych spotkań w pobranym terminarzu. Sprawdź pełny kalendarz." /></>}
        {view === 'results' && <><SectionTitle title="Ostatnie wyniki" /><MatchGroups matches={pageMatches} logos={logos} emptyMessage="Brak zakończonych spotkań w pobranych danych." /></>}
        {view === 'table' && (league.id === 'second' ? groupChoices.map(item => <section key={item.name}><SectionTitle title={item.name} /><Standings rows={item.table} logos={logos} /></section>) : <Standings rows={data.table} logos={logos} />)}
        {view === 'teams' && <TeamsGrid teams={league.id === 'second' ? groupChoices.flatMap(item => item.teams || []) : data.teams} logos={logos} favorites={favorites} toggleFavorite={toggleFavorite} />}
      </>}
      {data?.updated_at && <p className="vh-source-note">Aktualizacja źródła: {new Date(data.updated_at).toLocaleString('pl-PL')}</p>}
      {view === 'table' && (league.id === 'second' ? groupChoices : [data]).some(item => Object.keys(item?.source_table_discrepancies || {}).length > 0) && <p className="vh-source-note" role="status">Wyniki i tabela VolleyStation są publikowane osobno. Pokazujemy tabelę dokładnie według źródła.</p>}
    </> : <>
      <div className="vh-segmented" role="tablist" aria-label="Region rozgrywek">{CATEGORIES.map(item => <button role="tab" aria-selected={category === item} className={category === item ? 'selected' : ''} key={item} onClick={() => setCategory(item)}>{item}</button>)}</div>
      {LEAGUES.some(item => item.category === category) ? <><SectionTitle eyebrow={(category === 'Polska' ? 'POLSKA' : category === 'Europa' ? 'EUROPA' : 'ŚWIAT') + ' · MĘŻCZYŹNI'} title="Dostępne ligi" /><div className="vh-league-stack">{LEAGUES.filter(item => item.category === category).map((item, index) => <article className="vh-league-tile vh-league-select" key={item.id}><button className="vh-league-main" onClick={() => openLeague(item.id)}><span className="vh-league-number">{String(index + 1).padStart(2, '0')}</span><span><strong>{item.name}</strong><small>{item.description}</small></span><ChevronRight size={20} /></button><button type="button" className={'vh-star-button ' + (favorites.leagues.includes(item.name) ? 'is-favorite' : '')} aria-label={(favorites.leagues.includes(item.name) ? 'Usuń z' : 'Dodaj do') + ' ulubionych: ' + item.name} onClick={() => toggleFavorite('leagues', item.name)}><Star size={20} fill={favorites.leagues.includes(item.name) ? 'currentColor' : 'none'} /></button></article>)}</div></> : <EmptyState Icon={Trophy} title="Wkrótce" message="Nowe rozgrywki dodamy dopiero po weryfikacji oficjalnych źródeł danych. Nie pokazujemy fikcyjnych wyników." />}
    </>}
  </>;
});

const FavoritesPage = React.memo(function FavoritesPage({ teams, logos, favorites, toggleFavorite, onOpenLeague }) {
  const [tab, setTab] = useState('teams');
  const [query, setQuery] = useState('');
  const matches = useMemo(() => {
    const term = normalizeName(query);
    return teams.filter(team => normalizeName(team.name).includes(term));
  }, [teams, query]);
  const selected = tab === 'teams' ? favorites.teams : favorites.leagues;
  return <>
    <PageHeader title="Ulubione" subtitle="Twoje drużyny i ligi. Zawsze pod ręką." />
    <div className="vh-segmented" role="tablist" aria-label="Rodzaj ulubionych"><button className={tab === 'teams' ? 'selected' : ''} role="tab" aria-selected={tab === 'teams'} onClick={() => { setTab('teams'); setQuery(''); }}>Drużyny <span>{favorites.teams.length}</span></button><button className={tab === 'leagues' ? 'selected' : ''} role="tab" aria-selected={tab === 'leagues'} onClick={() => { setTab('leagues'); setQuery(''); }}>Rozgrywki <span>{favorites.leagues.length}</span></button></div>
    {selected.length > 0 ? <><SectionTitle eyebrow="OBSERWOWANE" title={tab === 'teams' ? 'Twoje drużyny' : 'Twoje rozgrywki'} />
      {tab === 'teams' ? <TeamsGrid teams={selected.map(name => teams.find(team => sameName(team.name, name)) || { name })} logos={logos} favorites={favorites} toggleFavorite={toggleFavorite} /> : <div className="vh-league-stack">{selected.map(name => <div className="vh-league-tile vh-league-select" key={name}><button className="vh-league-main" type="button" onClick={() => onOpenLeague(leagueByName(name)?.id)}><span className="vh-league-number"><Trophy size={19} /></span><span><strong>{name}</strong><small>Otwórz rozgrywki</small></span><ChevronRight size={18} /></button><button className="vh-star-button is-favorite" type="button" aria-label={'Usuń z ulubionych: ' + name} onClick={() => toggleFavorite('leagues', name)}><Star size={20} fill="currentColor" /></button></div>)}</div>}
    </> : <EmptyState Icon={Heart} title="Jeszcze nic tutaj nie ma" message={tab === 'teams' ? 'Znajdź drużyny poniżej i dodaj je do obserwowanych.' : 'Dodaj ulubione ligi, aby mieć do nich szybki dostęp.'} />}
    <SectionTitle eyebrow="ODKRYWAJ" title={tab === 'teams' ? 'Dodaj drużyny' : 'Dodaj rozgrywki'} />
    {tab === 'teams' && <label className="vh-search-input"><Search size={20} /><input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Szukaj drużyny…" /></label>}
    <div className="vh-picker-list">{(tab === 'teams' ? matches : LEAGUES.map(item => ({ name: item.name }))).slice(0, 100).map(item => {
      const chosen = selected.some(name => sameName(name, item.name));
      return <button key={item.name} type="button" className="vh-picker-row" onClick={() => toggleFavorite(tab, item.name)}>{tab === 'teams' ? <TeamLogo name={item.name} logo={item.logo || logos.get(normalizeName(item.name))} /> : <span className="vh-mini-league"><Trophy size={17} /></span>}<span>{item.name}</span><span className={'vh-picker-check ' + (chosen ? 'selected' : '')}>{chosen ? <Check size={17} /> : <Star size={16} />}</span></button>;
    })}{tab === 'teams' && !matches.length && <p className="vh-source-note">Nie znaleziono drużyn.</p>}</div>
  </>;
});

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
