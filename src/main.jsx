import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Home, CalendarDays, Trophy, Heart, Search, ArrowRight, ArrowLeft, X, Star, Clock3, RotateCw, ChevronRight, ChevronLeft, CalendarCheck2, SlidersHorizontal, WifiOff, Check, Info, Volleyball } from 'lucide-react';
import {
  LEAGUES, CATEGORIES, WEEKDAYS, dateKey, fromKey, addDays, feedDateKey,
  isLive, isFinished, fetchLeague, matchesFromFeeds, teamIndex, normalizeName, readFavorites
} from './data.js';
import BrandSignature from './components/BrandSignature.jsx';
import '../matches-ios.css';
import './app.css';

const NAV = [
  { id: 'home', label: 'Główna', Icon: Home },
  { id: 'matches', label: 'Mecze', Icon: CalendarDays },
  { id: 'competitions', label: 'Rozgrywki', Icon: Trophy },
  { id: 'favorites', label: 'Ulubione', Icon: Heart }
];
const ROUTES = NAV.map(item => item.id);
const DATE_FORMAT = new Intl.DateTimeFormat('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' });
const NOW = () => { const today = new Date(); today.setHours(12, 0, 0, 0); return today; };
const leagueByName = name => LEAGUES.find(item => item.name === name);
const sameName = (a, b) => normalizeName(a) === normalizeName(b);

function useFeeds() {
  const [feeds, setFeeds] = useState({});
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    async function load() {
      const results = await Promise.all(LEAGUES.map(async league => {
        try { return { id: league.id, data: await fetchLeague(league, controller.signal) }; }
        catch (error) { return { id: league.id, error }; }
      }));
      if (!active) return;
      setFeeds(previous => {
        const next = { ...previous };
        for (const result of results) if (result.data) next[result.id] = result.data;
        return next;
      });
      setErrors(Object.fromEntries(results.filter(result => result.error).map(result => [result.id, result.error.message])));
      setLoading(false);
    }
    load();
    return () => { active = false; controller.abort(); };
  }, [revision]);
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') setRevision(current => current + 1);
    }, 60000);
    return () => window.clearInterval(timer);
  }, []);
  return { feeds, errors, loading, refresh: () => setRevision(current => current + 1) };
}

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
function MatchCard({ match, logos, compact = false }) {
  const [expanded, setExpanded] = useState(false);
  const finished = isFinished(match);
  const score = finished || isLive(match);
  const homeWins = score && Number(match.home_sets) > Number(match.away_sets);
  const awayWins = score && Number(match.away_sets) > Number(match.home_sets);
  const scores = Array.isArray(match.set_scores) ? match.set_scores : [];
  return <article className={'im-card vh-match ' + (compact ? 'vh-match-compact' : '')}>
    <div className="im-meta"><span>{match.group ? match.group + ' · ' : ''}{match.leagueName || match.competition || 'Siatkówka'}</span><Status match={match} /></div>
    <div className={'im-body ' + (score ? 'has-score' : '')}>
      <div className="im-row">
        <TeamLogo name={match.home} logo={logos.get(normalizeName(match.home))} className="im-logo" />
        <span className={'im-name ' + (homeWins ? 'win' : '')}>{match.home}</span>
        {score && <span className={'im-pts ' + (awayWins ? 'lose' : '')}>{match.home_sets ?? '–'}</span>}
      </div>
      <div className="im-sep" />
      <div className="im-row">
        <TeamLogo name={match.away} logo={logos.get(normalizeName(match.away))} className="im-logo" />
        <span className={'im-name ' + (awayWins ? 'win' : '')}>{match.away}</span>
        {score && <span className={'im-pts ' + (homeWins ? 'lose' : '')}>{match.away_sets ?? '–'}</span>}
      </div>
      {!score && <span className="im-time">{match.time || '–:–'}</span>}
    </div>
    {(score || match.time) && <div className="vh-match-footer">
      <span><Clock3 size={14} /> {match.time || 'Godzina nieustalona'}</span>
      {scores.length > 0 && <button className="vh-details-button" onClick={() => setExpanded(current => !current)} type="button" aria-expanded={expanded}>{expanded ? 'Ukryj sety' : 'Pokaż sety'}<ChevronRight size={15} className={expanded ? 'vh-rotate' : ''} /></button>}
      {!scores.length && isLive(match) && match.current_points && <span>Aktualny set: {String(match.current_points)}</span>}
    </div>}
    {expanded && scores.length > 0 && <div className="vh-sets" aria-label="Wyniki setów">{scores.map((set, index) => <span key={index}><small>SET {index + 1}</small><strong>{set}</strong></span>)}</div>}
  </article>;
}
function MatchGroups({ matches, logos, emptyMessage, compact = false }) {
  if (!matches.length) return <EmptyState title="Brak meczów" message={emptyMessage || 'Na razie nie ma spotkań spełniających te kryteria.'} />;
  const groups = LEAGUES.map(league => ({ league, matches: matches.filter(match => match.leagueId === league.id) })).filter(group => group.matches.length);
  return <div className="vh-match-groups">{groups.map(group => <section key={group.league.id}>
    <h3 className="im-league"><span className="im-flag">🇵🇱</span>{group.league.short}<span className="vh-count">{group.matches.length}</span></h3>
    {group.matches.map((match, index) => <MatchCard key={group.league.id + ':' + (match.id || index) + ':' + match.date} match={match} logos={logos} compact={compact} />)}
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
  const selectedKey = dateKey(selected);
  const days = useMemo(() => Array.from({ length: 61 }, (_, index) => addDays(selected, index - 30)), [selectedKey]);
  useEffect(() => {
    const active = strip.current?.querySelector('[aria-selected="true"]');
    if (active) active.scrollIntoView({ behavior: 'auto', block: 'nearest', inline: 'center' });
  }, [selectedKey]);
  return <div className="im-strip-wrap vh-date-wrap">
    <div className="im-strip" role="tablist" aria-label="Wybierz dzień" ref={strip}>
      {days.map((day, index) => {
        const key = dateKey(day);
        const active = key === selectedKey;
        return <button className={'im-day ' + (active ? 'is-sel ' : '') + (key === dateKey(NOW()) ? 'is-today' : '')} role="tab" aria-selected={active} aria-label={DATE_FORMAT.format(day)} onClick={() => onSelect(day)} key={key} type="button">
          <small className={'im-month ' + (day.getDate() === 1 || index === 0 ? '' : 'is-empty')}>{new Intl.DateTimeFormat('pl-PL', { month: 'short' }).format(day).replace('.', '').toUpperCase()}</small>
          <b>{day.getDate()}</b><span>{WEEKDAYS[day.getDay()]}</span>
        </button>;
      })}
    </div>
  </div>;
}

function MatchesPage({ feeds, loading, errors, refresh, logos, selectedDate, setSelectedDate, leagueFilter, setLeagueFilter }) {
  const [liveOnly, setLiveOnly] = useState(false);
  const [groupFilter, setGroupFilter] = useState('all');
  const input = useRef(null);
  const all = useMemo(() => matchesFromFeeds(feeds, leagueFilter), [feeds, leagueFilter]);
  const groups = [...new Set(all.filter(match => match.leagueId === 'second').map(match => match.group).filter(Boolean))];
  const filtered = all.filter(match => (!liveOnly || isLive(match)) && (liveOnly || feedDateKey(match.date) === dateKey(selectedDate)) && (groupFilter === 'all' || match.leagueId !== 'second' || match.group === groupFilter));
  const updateLeague = id => { setLeagueFilter(id); setGroupFilter('all'); };
  return <>
    <PageHeader title="Mecze" subtitle="Terminarze i wyniki w jednym miejscu." actions={<>
      <IconButton Icon={SlidersHorizontal} label={liveOnly ? 'Pokaż wszystkie mecze' : 'Tylko mecze na żywo'} active={liveOnly} onClick={() => setLiveOnly(current => !current)} />
      <IconButton Icon={CalendarDays} label="Wybierz datę" onClick={() => { const picker = input.current; if (!picker) return; if (typeof picker.showPicker === 'function') picker.showPicker(); else picker.click(); }} />
      <IconButton Icon={CalendarCheck2} label="Przejdź do dzisiaj" onClick={() => { setLiveOnly(false); setSelectedDate(NOW()); }} />
    </>} />
    <input className="vh-visually-hidden-date" type="date" aria-label="Wybierz datę" ref={input} value={dateKey(selectedDate)} onChange={event => { const next = fromKey(event.target.value); if (next) { setLiveOnly(false); setSelectedDate(next); } }} />
    <DateStrip selected={selectedDate} onSelect={value => { setLiveOnly(false); setSelectedDate(value); }} />
    <div className="vh-controls">
      <button type="button" className={'vh-filter-chip ' + (!leagueFilter ? 'chosen' : '')} onClick={() => updateLeague(null)}>Wszystkie ligi</button>
      {LEAGUES.map(league => <button className={'vh-filter-chip ' + (leagueFilter === league.id ? 'chosen' : '')} type="button" key={league.id} onClick={() => updateLeague(league.id)}>{league.short}</button>)}
    </div>
    {leagueFilter === 'second' && <div className="vh-controls vh-secondary-filters"><button className={'vh-filter-chip ' + (groupFilter === 'all' ? 'chosen' : '')} onClick={() => setGroupFilter('all')}>Wszystkie grupy</button>{groups.map(group => <button key={group} className={'vh-filter-chip ' + (groupFilter === group ? 'chosen' : '')} onClick={() => setGroupFilter(group)}>{group}</button>)}</div>}
    <div className="vh-day-heading"><div><span className="vh-eyebrow">{liveOnly ? 'TRANSMISJA WYNIKÓW' : 'WYBRANY DZIEŃ'}</span><h2>{liveOnly ? 'Teraz na żywo' : DATE_FORMAT.format(selectedDate)}</h2></div><button className="vh-refresh" title="Odśwież" aria-label="Odśwież dane" onClick={refresh}><RotateCw size={18} /></button></div>
    <FeedWarning errors={errors} refresh={refresh} />
    {loading && !Object.keys(feeds).length ? <LoadingCards /> : <MatchGroups matches={filtered} logos={logos} emptyMessage={liveOnly ? 'Żaden z obserwowanych meczów nie jest obecnie oznaczony jako na żywo.' : 'Nie znaleziono meczów na wybrany dzień. Przesuń kalendarz lub wybierz inną ligę.'} />}
    <p className="vh-source-note">Dane pochodzą z oficjalnych źródeł rozgrywek. Wyniki aktualizują się automatycznie, gdy aplikacja jest aktywna.</p>
  </>;
}

function HomePage({ feeds, loading, errors, refresh, logos, favorites, onNavigate, onOpenLeague }) {
  const todayMatches = matchesFromFeeds(feeds).filter(match => feedDateKey(match.date) === dateKey(NOW()));
  const upcoming = matchesFromFeeds(feeds).filter(match => feedDateKey(match.date) >= dateKey(NOW())).slice(0, 3);
  const featured = todayMatches.length ? todayMatches : upcoming;
  const savedCount = favorites.teams.length + favorites.leagues.length;
  return <>
    <PageHeader title="Volley Hub" subtitle="Twoje centrum siatkówki. Wszystko, co ważne, w jednym miejscu." actions={<span className="vh-date-stamp">{new Intl.DateTimeFormat('pl-PL', { weekday: 'long', day: 'numeric', month: 'long' }).format(NOW())}</span>} />
    <div className="vh-hero">
      <span className="vh-hero-tag"><span className="vh-hero-dot" /> SIATKÓWKA NA ŻYWO</span>
      <h2>Gra toczy się <em>tutaj.</em></h2>
      <p>Sprawdź mecze, poznaj wyniki i bądź bliżej swoich drużyn.</p>
      <button type="button" className="vh-hero-action" onClick={() => onNavigate('matches')}>Przejdź do meczów <ArrowRight size={20} /></button>
      <div className="vh-hero-decor" aria-hidden="true"><Volleyball size={120} strokeWidth={0.7} /></div>
    </div>
    <SectionTitle eyebrow={todayMatches.length ? 'DZISIAJ NA PARKIECIE' : 'NAJBLIŻSZE SPOTKANIA'} title={todayMatches.length ? 'Mecze dzisiaj' : 'Co przed nami'} action="Zobacz mecze" onAction={() => onNavigate('matches')} />
    <FeedWarning errors={errors} refresh={refresh} />
    {loading && !Object.keys(feeds).length ? <LoadingCards /> : <MatchGroups compact matches={featured} logos={logos} emptyMessage="Nie mamy jeszcze zaplanowanych spotkań w pobranych danych." />}
    <SectionTitle eyebrow="ODKRYWAJ" title="Rozgrywki" action="Wszystkie" onAction={() => onNavigate('competitions')} />
    <div className="vh-league-stack">{LEAGUES.slice(0, 4).map((league, index) => <button className="vh-league-tile" type="button" key={league.id} onClick={() => onOpenLeague(league.id)}><span className="vh-league-number">{String(index + 1).padStart(2, '0')}</span><span><strong>{league.short}</strong><small>{league.description}</small></span><ChevronRight size={20} /></button>)}</div>
    <SectionTitle eyebrow="TWOJA STREFA" title="Ulubione" action="Otwórz" onAction={() => onNavigate('favorites')} />
    <button type="button" className="vh-favorites-teaser" onClick={() => onNavigate('favorites')}><span className="vh-heart-icon"><Heart size={24} /></span><span><strong>{savedCount ? savedCount + ' zapisanych elementów' : 'Twój skład, Twoje ligi'}</strong><small>{savedCount ? 'Przejdź do obserwowanych drużyn i rozgrywek' : 'Dodaj drużyny i ligi, które chcesz śledzić'}</small></span><ChevronRight size={19} /></button>
  </>;
}

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
function CompetitionsPage({ feeds, loading, errors, refresh, logos, favorites, toggleFavorite, selectedLeague, setSelectedLeague, onMatches }) {
  const [category, setCategory] = useState('Polska');
  const [view, setView] = useState('matches');
  const [group, setGroup] = useState('all');
  const league = LEAGUES.find(item => item.id === selectedLeague);
  const data = league ? feeds[league.id] : null;
  const grouped = league?.id === 'second' ? (data?.groups || []) : [];
  const groupChoices = group === 'all' ? grouped : grouped.filter(item => item.name === group);
  const openLeague = id => { setSelectedLeague(id); setView('matches'); setGroup('all'); };
  const all = league ? matchesFromFeeds(feeds, league.id).filter(match => group === 'all' || match.group === group) : [];
  const today = dateKey(NOW());
  const pageMatches = view === 'results' ? all.filter(isFinished).reverse().slice(0, 40) : all.filter(match => feedDateKey(match.date) >= today).slice(0, 25);
  return <>
    <PageHeader title="Rozgrywki" subtitle="Wybierz ligę. Poznaj drużyny, wyniki i aktualną tabelę." actions={league ? <IconButton Icon={ArrowLeft} label="Wszystkie ligi" onClick={() => setSelectedLeague(null)} /> : null} />
    {league ? <>
      <button className="vh-back" onClick={() => setSelectedLeague(null)}><ChevronLeft size={18} /> Wszystkie rozgrywki</button>
      <div className="vh-league-cover"><span className="vh-eyebrow">🇵🇱 POLSKA · MĘŻCZYŹNI</span><h2>{league.name}</h2><p>{league.description}</p><button className="vh-cover-favorite" type="button" onClick={() => toggleFavorite('leagues', league.name)}><Star size={17} fill={favorites.leagues.includes(league.name) ? 'currentColor' : 'none'} /> {favorites.leagues.includes(league.name) ? 'W ulubionych' : 'Dodaj do ulubionych'}</button></div>
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
}

function FavoritesPage({ feeds, logos, favorites, toggleFavorite, onOpenLeague }) {
  const [tab, setTab] = useState('teams');
  const [query, setQuery] = useState('');
  const teams = teamIndex(feeds);
  const matches = teams.filter(team => normalizeName(team.name).includes(normalizeName(query)));
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
}

function SearchSheet({ feeds, logos, onClose, onOpenLeague, onMatches, favorites, toggleFavorite }) {
  const [query, setQuery] = useState('');
  const input = useRef(null);
  useEffect(() => { input.current?.focus(); const onEscape = event => { if (event.key === 'Escape') onClose(); }; window.addEventListener('keydown', onEscape); return () => { window.removeEventListener('keydown', onEscape); document.querySelector('.vh-global-search')?.focus(); }; }, []);
  const results = useMemo(() => {
    const term = normalizeName(query);
    if (!term) return { leagues: LEAGUES, teams: [] };
    return { leagues: LEAGUES.filter(item => normalizeName(item.name).includes(term)), teams: teamIndex(feeds).filter(team => normalizeName(team.name).includes(term)).slice(0, 24) };
  }, [query, feeds]);
  return <div className="vh-search-overlay" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="vh-search-sheet" role="dialog" aria-modal="true" aria-label="Wyszukiwarka" onKeyDown={event => {
      if (event.key !== 'Tab') return;
      const elements = Array.from(event.currentTarget.querySelectorAll('button:not([disabled]), input:not([disabled])'));
      if (!elements.length) return;
      const first = elements[0], last = elements[elements.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }}>
      <div className="vh-sheet-header"><h2>Szukaj</h2><button className="vh-close" type="button" aria-label="Zamknij wyszukiwarkę" onClick={onClose}><X size={22} /></button></div>
      <label className="vh-search-input"><Search size={20} /><input ref={input} type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Drużyna lub rozgrywki…" /></label>
      <div className="vh-search-results">
        {!!results.leagues.length && <><h3>Rozgrywki</h3>{results.leagues.map(league => <button className="vh-picker-row" type="button" key={league.id} onClick={() => { onOpenLeague(league.id); onClose(); }}><span className="vh-mini-league"><Trophy size={18} /></span><span>{league.name}</span><ChevronRight size={18} /></button>)}</>}
        {!!results.teams.length && <><h3>Drużyny</h3>{results.teams.map(team => <button className="vh-picker-row" type="button" key={team.name} onClick={() => { toggleFavorite('teams', team.name); }}><TeamLogo name={team.name} logo={team.logo || logos.get(normalizeName(team.name))} /><span>{team.name}</span><Star size={18} fill={favorites.teams.some(x => sameName(x, team.name)) ? 'currentColor' : 'none'} className={favorites.teams.some(x => sameName(x, team.name)) ? 'vh-favorite-color' : ''} /></button>)}</>}
        {query && !results.leagues.length && !results.teams.length && <EmptyState Icon={Search} title="Brak wyników" message="Sprawdź pisownię lub wpisz inny fragment nazwy." />}
        {!query && <p className="vh-source-note">Wpisz nazwę drużyny, aby dodać ją do ulubionych, albo otwórz rozgrywki.</p>}
      </div>
    </section>
  </div>;
}

function NavGlass({ hostRef, active }) {
  const [Glass, setGlass] = useState(null);
  const [placement, setPlacement] = useState({ position: [.5, .5], size: 116 });
  useEffect(() => {
    if (!window.WebGL2RenderingContext || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return;
    let alive = true;
    import('./FluidGlass.jsx').then(module => { if (alive) setGlass(() => module.default); }).catch(error => console.warn('Fluid Glass is unavailable; using CSS fallback.', error));
    return () => { alive = false; };
  }, []);
  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const update = () => {
      const button = host.querySelector('.vh-nav-item.active');
      if (!button) return;
      const bounds = host.getBoundingClientRect();
      const selected = button.getBoundingClientRect();
      if (!bounds.width || !bounds.height || !selected.width) return;
      const next = {
        position: [(selected.left + selected.width / 2 - bounds.left) / bounds.width, (selected.top + selected.height / 2 - bounds.top) / bounds.height],
        size: selected.width
      };
      setPlacement(previous => (
        Math.abs(previous.position[0] - next.position[0]) < .002 &&
        Math.abs(previous.position[1] - next.position[1]) < .002 &&
        Math.abs(previous.size - next.size) < 1 ? previous : next
      ));
    };
    const resize = new ResizeObserver(update);
    resize.observe(host);
    const buttons = host.querySelectorAll('.vh-nav-item');
    buttons.forEach(button => resize.observe(button));
    host.addEventListener('transitionend', update);
    requestAnimationFrame(update);
    return () => { resize.disconnect(); host.removeEventListener('transitionend', update); };
  }, [active, hostRef]);
  return Glass ? <div className="vh-glass-layer" aria-hidden="true"><Glass
    text="" shape="pill" shapes={['pill']} size={placement.size} position={placement.position}
    interaction="static" morphOnClick={false} idle={false} spin={0} wobble={0.02}
    refraction={1.15} dispersion={0.2} reflection={1.1} tint={0.1} shadow={0.24}
    color="#ffffff" intro={false} maxDevicePixelRatio={1.5}
  /></div> : null;
}
function BottomNav({ active, onNavigate }) {
  const hostRef = useRef(null);
  return <nav ref={hostRef} className="vh-bottom" aria-label="Główna nawigacja"><NavGlass hostRef={hostRef} active={active} /><div className="vh-nav-items">{NAV.map(({ id, label, Icon }) => <button key={id} onClick={() => onNavigate(id)} className={'vh-nav-item ' + (active === id ? 'active' : '')} type="button" aria-current={active === id ? 'page' : undefined} aria-label={label}><Icon size={23} strokeWidth={active === id ? 2.3 : 1.8} fill={active === id && id === 'favorites' ? 'currentColor' : 'none'} /><span>{label}</span></button>)}</div></nav>;
}

function App() {
  const route = () => { const hash = window.location.hash.replace(/^#\/?/, ''); return ROUTES.includes(hash) ? hash : 'home'; };
  const [page, setPage] = useState(route);
  const [selectedDate, setSelectedDate] = useState(NOW);
  const [leagueFilter, setLeagueFilter] = useState(null);
  const [selectedLeague, setSelectedLeague] = useState(null);
  const [favorites, setFavorites] = useState(readFavorites);
  const [searchOpen, setSearchOpen] = useState(false);
  const { feeds, errors, loading, refresh } = useFeeds();
  const logos = useMemo(() => new Map(teamIndex(feeds).filter(team => team.logo).map(team => [normalizeName(team.name), team.logo])), [feeds]);
  useEffect(() => {
    const sync = () => setPage(route());
    window.addEventListener('hashchange', sync);
    return () => window.removeEventListener('hashchange', sync);
  }, []);
  useEffect(() => {
    try { localStorage.setItem('vh-favs', JSON.stringify(favorites)); } catch { /* storage may be blocked */ }
  }, [favorites]);
  useEffect(() => {
    if (searchOpen) document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, [searchOpen]);
  useEffect(() => {
    if ('serviceWorker' in navigator && import.meta.env.PROD && location.protocol.startsWith('http')) {
      navigator.serviceWorker.register(import.meta.env.BASE_URL + 'sw.js').catch(() => {});
    }
  }, []);
  function navigate(id) {
    if (!ROUTES.includes(id)) return;
    setSearchOpen(false);
    setPage(id);
    window.location.hash = id;
    window.scrollTo({ top: 0, behavior: 'instant' });
  }
  function openLeague(id) {
    if (!id) return;
    setSelectedLeague(id);
    navigate('competitions');
  }
  function goToMatches(id) {
    setLeagueFilter(id || null);
    navigate('matches');
  }
  function toggleFavorite(type, name) {
    setFavorites(current => {
      const exists = current[type].some(value => sameName(value, name));
      return { ...current, [type]: exists ? current[type].filter(value => !sameName(value, name)) : [...current[type], name] };
    });
  }
  return <div className="vh-app" id="ios-matches">
    <div className="vh-floating-head" aria-label="Nagłówek Volley Hub">
      <BrandSignature />
      <div className="vh-floating-actions">
        <button type="button" className="vh-search-bubble" aria-label="Szukaj" title="Szukaj w Volley Hub" onClick={() => setSearchOpen(true)}>
          <Search size={23} strokeWidth={2.1} aria-hidden="true" />
        </button>
      </div>
    </div>
    <main id="main-content" key={page}>
      {page === 'home' && <HomePage feeds={feeds} loading={loading} errors={errors} refresh={refresh} logos={logos} favorites={favorites} onNavigate={navigate} onOpenLeague={openLeague} />}
      {page === 'matches' && <MatchesPage feeds={feeds} loading={loading} errors={errors} refresh={refresh} logos={logos} selectedDate={selectedDate} setSelectedDate={setSelectedDate} leagueFilter={leagueFilter} setLeagueFilter={setLeagueFilter} />}
      {page === 'competitions' && <CompetitionsPage feeds={feeds} loading={loading} errors={errors} refresh={refresh} logos={logos} favorites={favorites} toggleFavorite={toggleFavorite} selectedLeague={selectedLeague} setSelectedLeague={setSelectedLeague} onMatches={goToMatches} />}
      {page === 'favorites' && <FavoritesPage feeds={feeds} logos={logos} favorites={favorites} toggleFavorite={toggleFavorite} onOpenLeague={openLeague} />}
    </main>
    <BottomNav active={page} onNavigate={navigate} />
    {searchOpen && <SearchSheet feeds={feeds} logos={logos} favorites={favorites} toggleFavorite={toggleFavorite} onClose={() => setSearchOpen(false)} onOpenLeague={openLeague} onMatches={goToMatches} />}
  </div>;
}

createRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>);
