import React, { useCallback, useContext, useEffect, useId, useLayoutEffect, useMemo, useRef, useState, startTransition } from 'react';
import { createRoot } from 'react-dom/client';
import { createPortal, flushSync } from 'react-dom';
import { CalendarDays, Trophy, Heart, Search, ArrowRight, ArrowLeft, Star, Clock3, RotateCw, ChevronRight, ChevronLeft, WifiOff, Check } from 'lucide-react';
import {
  LEAGUES, CATEGORIES, WEEKDAYS, dateKey, addDays, feedDateKey,
  isLive, isFinished, matchesFromFeeds, teamIndex, normalizeName, readFavorites
} from './data.js';
import BrandSignature from './components/BrandSignature.jsx';
import StartupEntrance from './components/StartupEntrance.jsx';
import { useAnimatedDate, AnimatedSets } from './components/ScheduleMotion.jsx';
import BottomNav from './components/BottomNav.jsx';
import PageStage from './components/PageStage.jsx';
import useFeeds from './useFeeds.js';
import { MotionEnabled, ScoreValue, LeagueEntrance } from './components/MatchMotion.jsx';
import { ROUTES } from './navigation.js';
import '../matches-ios.css';
import './app.css';
import './theme.css';

const DATE_FORMAT = new Intl.DateTimeFormat('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' });
const NOW = () => { const today = new Date(); today.setHours(12, 0, 0, 0); return today; };
const leagueByName = name => LEAGUES.find(item => item.name === name);
const sameName = (a, b) => normalizeName(a) === normalizeName(b);
const MONTH_FORMAT = new Intl.DateTimeFormat('pl-PL', { month: 'long' });


function TeamLogo({ name, logo, className = '' }) {
  const [broken, setBroken] = useState(false);
  const initials = String(name || '?').split(/\s+/).filter(Boolean).slice(0, 2).map(word => word[0]).join('').toUpperCase();
  useEffect(() => setBroken(false), [logo, name]);
  return <span className={'vh-team-logo ' + className}>
    {logo && !broken ? <img src={logo} alt="" loading="lazy" onError={() => setBroken(true)} /> : <span className="team-mark" aria-hidden="true">{initials || '?'}</span>}
  </span>;
}

function SectionTitle({ eyebrow, title, action, onAction }) {
  return <div className="vh-section-heading">
    <div>{eyebrow && <span className="vh-eyebrow">{eyebrow}</span>}<h2>{title}</h2></div>
    {action && <button className="vh-text-action" type="button" onClick={onAction}>{action}<ArrowRight size={17} /></button>}
  </div>;
}

function EmptyState({ icon: Icon = CalendarDays, title, message, action, onAction }) {
  return <div className="vh-empty" role="status">
    <div className="vh-empty-icon"><Icon size={25} strokeWidth={1.8} /></div>
    <h3>{title}</h3><p>{message}</p>
    {action && <button type="button" className="vh-button vh-button-soft" onClick={onAction}>{action}</button>}
  </div>;
}
function FeedWarning({ errors, refresh }) {
  const count = Object.keys(errors).length;
  if (!count) return null;
  return <div className="vh-warning" role="alert">
    <WifiOff size={18} /><span>Nie udało się odświeżyć {count === 1 ? 'jednej ligi' : count + ' lig'}. Pokazujemy ostatnio dostępne dane, jeśli zostały wczytane.</span>
    <button type="button" aria-label="Spróbuj ponownie" onClick={refresh}><RotateCw size={17} /></button>
  </div>;
}
function LoadingCards() {
  return <div aria-label="Ładowanie meczów" role="status"><div className="im-skel" /><div className="im-skel" /><div className="im-skel" /></div>;
}
function Status({ match }) {
  if (isLive(match)) return <span className="im-live">NA ŻYWO</span>;
  if (isFinished(match)) return <span>Zakończony</span>;
  return <span>Zaplanowany</span>;
}
const MatchCard = React.memo(function MatchCard({ match, logos, compact = false }) {
  const [expanded, setExpanded] = useState(false);
  const detailsId = useId();
  const finished = isFinished(match);
  const score = finished || isLive(match);
  const homeWins = score && Number(match.home_sets) > Number(match.away_sets);
  const awayWins = score && Number(match.away_sets) > Number(match.home_sets);
  const scores = Array.isArray(match.set_scores) ? match.set_scores : [];
  return <article data-match-id={match.id || [match.leagueId, match.date, match.home, match.away].join(':')} className={'im-card vh-match ' + (compact ? 'vh-match-compact' : '')}>
    <div className="im-meta"><span>{match.group ? match.group + ' · ' : ''}{match.leagueName || match.competition || 'Siatkówka'}</span><Status match={match} /></div>
    <div className={'im-body ' + (score ? 'has-score' : '')}>
      <div className="im-row">
        <TeamLogo name={match.home} logo={logos.get(normalizeName(match.home))} className="im-logo" />
        <span className={'im-name ' + (homeWins ? 'win' : '')}>{match.home}</span>
        {score && <ScoreValue className={'im-pts ' + (awayWins ? 'lose' : '')} value={match.home_sets ?? '–'} />}
      </div>
      <div className="im-sep" />
      <div className="im-row">
        <TeamLogo name={match.away} logo={logos.get(normalizeName(match.away))} className="im-logo" />
        <span className={'im-name ' + (awayWins ? 'win' : '')}>{match.away}</span>
        {score && <ScoreValue className={'im-pts ' + (homeWins ? 'lose' : '')} value={match.away_sets ?? '–'} />}
      </div>
      {!score && <span className="im-time">{match.time || '–:–'}</span>}
    </div>
    {(score || match.time) && <div className="vh-match-footer">
      <span><Clock3 size={14} /> {match.time || 'Godzina nieustalona'}</span>
      {scores.length > 0 && <button className="vh-details-button" onClick={() => setExpanded(current => !current)} type="button" aria-expanded={expanded} aria-controls={detailsId}>{expanded ? 'Ukryj sety' : 'Pokaż sety'}<ChevronRight size={15} className={expanded ? 'vh-rotate' : ''} /></button>}
      {isLive(match) && match.current_points && <span>Aktualny set: <ScoreValue className="vh-live-points" value={String(match.current_points)} /></span>}
    </div>}
    {scores.length > 0 && <AnimatedSets scores={scores} expanded={expanded} detailsId={detailsId} />}
  </article>;
});

function MatchGroups({ matches, logos, emptyMessage, compact = false }) {
  if (!matches.length) return <EmptyState title="Brak meczów" message={emptyMessage || 'Na razie nie ma spotkań spełniających te kryteria.'} />;
  const groups = LEAGUES.map(league => ({ league, matches: matches.filter(match => match.leagueId === league.id) })).filter(group => group.matches.length);
  return <div className="vh-match-groups">{groups.map(group => <section key={group.league.id}>
    <h3 className="im-league"><span className="im-flag">🇵🇱</span>{group.league.short}<span className="vh-count">{group.matches.length}</span></h3>
    {group.matches.map(match => <MatchCard key={group.league.id + ':' + (match.id ?? [match.date, match.time || '', match.home, match.away].join('|'))} match={match} logos={logos} compact={compact} />)}
  </section>)}</div>;
}
function PageHeader({ title, subtitle, actions }) {
  return <div className="vh-page-head im-top"><div className="vh-header-actions">{actions}</div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div>;
}
function IconButton({ Icon, label, onClick, active = false }) {
  return <button type="button" className={'im-round vh-icon-button ' + (active ? 'is-active' : '')} aria-label={label} title={label} onClick={onClick}><Icon size={21} strokeWidth={1.9} /></button>;
}

function DateStrip({ selected, onSelect }) {
  const strip = useRef(null);
  const marker = useRef(null);
  const enabled = useContext(MotionEnabled);
  const [anchor, setAnchor] = useState(selected);
  const selectedKey = dateKey(selected), anchorKey = dateKey(anchor);
  const todayKey = dateKey(NOW());
  const previous = useRef({ selected: null, anchor: null, width: 0 });
  // Retain the same date nodes while picking nearby days. Rebuilding the range
  // on each tap shifted every label before the browser could animate anything.
  const days = useMemo(() => Array.from({ length: 61 }, (_, index) => addDays(anchor, index - 30)), [anchorKey]);
  useLayoutEffect(() => {
    if (!days.some(day => dateKey(day) === selectedKey)) setAnchor(selected);
  }, [selectedKey, days]);
  useEffect(() => {
    const index = days.findIndex(day => dateKey(day) === selectedKey);
    if (index < 0 || (index >= 7 && index <= 53)) return undefined;
    // Extend the window after the native scroll settles, preserving its view.
    const timer = window.setTimeout(() => setAnchor(selected), 700);
    return () => window.clearTimeout(timer);
  }, [selectedKey, days]);
  useLayoutEffect(() => {
    const host = strip.current, pill = marker.current;
    if (!host || !pill) return undefined;
    const last = previous.current;
    const animate = enabled && last.selected !== null && last.selected !== selectedKey && last.anchor === anchorKey;
    const center = smooth => {
      if (!host.clientWidth) { previous.current.width = 0; return; }
      const active = host.querySelector('[aria-selected="true"]');
      if (!active) return;
      pill.style.transitionDuration = smooth ? '' : '0s';
      pill.style.width = active.offsetWidth + 'px';
      pill.style.height = active.offsetHeight + 'px';
      pill.style.top = active.offsetTop + 'px';
      pill.style.transform = `translate3d(${active.offsetLeft}px,0,0)`;
      host.classList.add('has-date-indicator');
      const left = Math.max(0, active.offsetLeft + active.offsetWidth / 2 - host.clientWidth / 2);
      host.scrollTo({ left, behavior: smooth ? 'smooth' : 'auto' });
      previous.current = { selected: selectedKey, anchor: anchorKey, width: host.clientWidth };
    };
    center(animate);
    const observer = new ResizeObserver(() => {
      // Ignore the observer's first unchanged measurement: it otherwise cancels
      // the smooth scroll immediately after every selection.
      if (host.clientWidth !== previous.current.width) center(false);
    });
    observer.observe(host);
    return () => observer.disconnect();
  }, [selectedKey, anchorKey, enabled]);
  return <div className="im-strip-wrap vh-date-wrap">
    <h1 className="vh-calendar-month">{MONTH_FORMAT.format(selected)}</h1>
    <div className="im-strip" role="tablist" aria-label="Wybierz dzień" ref={strip}>
      <span ref={marker} className="vh-date-indicator" aria-hidden="true" />
      {days.map(day => {
        const key = dateKey(day);
        const active = key === selectedKey;
        return <button className={'im-day ' + (active ? 'is-sel ' : '') + (key === todayKey ? 'is-today' : '')} role="tab" aria-selected={active} aria-label={DATE_FORMAT.format(day)} onClick={() => onSelect(day)} key={key} type="button">
          <b>{day.getDate()}</b><span>{WEEKDAYS[day.getDay()]}</span>
        </button>;
      })}
    </div>
  </div>;
}

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
      <LeagueEntrance key={league.id} league={league} active={active}><span className="vh-eyebrow">🇵🇱 POLSKA · MĘŻCZYŹNI</span><h2>{league.name}</h2><p>{league.description}</p><button className="vh-cover-favorite" type="button" onClick={() => toggleFavorite('leagues', league.name)}><Star size={17} fill={favorites.leagues.includes(league.name) ? 'currentColor' : 'none'} /> {favorites.leagues.includes(league.name) ? 'W ulubionych' : 'Dodaj do ulubionych'}</button></LeagueEntrance>
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
    </> : <>
      <div className="vh-segmented" role="tablist" aria-label="Region rozgrywek">{CATEGORIES.map(item => <button role="tab" aria-selected={category === item} className={category === item ? 'selected' : ''} key={item} onClick={() => setCategory(item)}>{item}</button>)}</div>
      {category === 'Polska' ? <><SectionTitle eyebrow="POLSKA · MĘŻCZYŹNI" title="Dostępne ligi" /><div className="vh-league-stack">{LEAGUES.map((item, index) => <article className="vh-league-tile vh-league-select" key={item.id}><button className="vh-league-main" onClick={() => openLeague(item.id)}><span className="vh-league-number">{String(index + 1).padStart(2, '0')}</span><span><strong>{item.name}</strong><small>{item.description}</small></span><ChevronRight size={20} /></button><button type="button" className={'vh-star-button ' + (favorites.leagues.includes(item.name) ? 'is-favorite' : '')} aria-label={(favorites.leagues.includes(item.name) ? 'Usuń z' : 'Dodaj do') + ' ulubionych: ' + item.name} onClick={() => toggleFavorite('leagues', item.name)}><Star size={20} fill={favorites.leagues.includes(item.name) ? 'currentColor' : 'none'} /></button></article>)}</div></> : <EmptyState Icon={Trophy} title="Wkrótce" message="Nowe rozgrywki dodamy dopiero po weryfikacji oficjalnych źródeł danych. Nie pokazujemy fikcyjnych wyników." />}
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
  const matches = useMemo(() => matchesFromFeeds(feeds), [feeds.men?.matches, feeds.first?.matches, feeds.second?.matches, feeds.pomorska?.matches]);
  const teams = useMemo(() => teamIndex(feeds), [feeds.men?.teams, feeds.first?.teams, feeds.second?.teams, feeds.pomorska?.teams]);
  const logos = useMemo(() => new Map(teams.filter(team => team.logo).map(team => [normalizeName(team.name), team.logo])), [teams]);
  const viewTransition = useRef(null);
  const switchPage = useCallback(id => {
    if (!ROUTES.includes(id) || currentPage.current === id) return;
    const oldPage = currentPage.current;
    currentPage.current = id;
    const newDirection = ROUTES.indexOf(id) < ROUTES.indexOf(oldPage) ? 'backward' : 'forward';
    const change = () => {
      setDirection(newDirection);
      setVisitedPages(seen => seen.includes(id) ? seen : [...seen, id]);
      setPage(id);
    };
    // Keep both snapshots for one short, compositor-driven crossfade.
    // No waiting for the exit animation before mounting the destination.
    if (reducedMotion || startup || document.hidden ||
        typeof document.startViewTransition !== 'function') {
      viewTransition.current?.skipTransition();
      change();
      return;
    }
    viewTransition.current?.skipTransition();
    document.documentElement.classList.add('vh-native-route');
    try {
      const transition = document.startViewTransition(() => flushSync(change));
      viewTransition.current = transition;
      transition.finished.catch(() => {}).finally(() => {
        if (viewTransition.current !== transition) return;
        viewTransition.current = null;
        document.documentElement.classList.remove('vh-native-route');
      });
    } catch {
      document.documentElement.classList.remove('vh-native-route');
      change();
    }
  }, [reducedMotion, startup]);
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
