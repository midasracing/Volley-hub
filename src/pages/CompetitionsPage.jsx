import React, { useState } from 'react';
import { ArrowLeft, ArrowRight, ChevronLeft, ChevronRight, Star, Trophy, WifiOff } from 'lucide-react';
import { CATEGORIES, LEAGUES, dateKey, feedDateKey, isFinished } from '../data.js';
import { NOW } from '../dateUtils.js';
import { LeagueEntrance } from '../components/MatchMotion.jsx';
import { EmptyState, FeedWarning, IconButton, LoadingCards, PageHeader, SectionTitle } from '../components/UiPrimitives.jsx';
import { MatchGroups } from '../components/MatchCards.jsx';
import Standings from '../components/Standings.jsx';
import TeamsGrid from '../components/TeamsGrid.jsx';

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
      {!data && loading ? <LoadingCards /> : !data ? <EmptyState icon={WifiOff} title="Nie udało się pobrać ligi" message="Sprawdź połączenie i spróbuj ponownie." action="Odśwież dane" onAction={refresh} /> : <>
        {view === 'matches' && <><div className="vh-day-heading"><h2>Najbliższe mecze</h2><button className="vh-text-action" onClick={() => onMatches(league.id)}>Pełny terminarz <ArrowRight size={17} /></button></div><MatchGroups matches={pageMatches} logos={logos} emptyMessage="Brak przyszłych spotkań w pobranym terminarzu. Sprawdź pełny kalendarz." /></>}
        {view === 'results' && <><SectionTitle title="Ostatnie wyniki" /><MatchGroups matches={pageMatches} logos={logos} emptyMessage="Brak zakończonych spotkań w pobranych danych." /></>}
        {view === 'table' && (league.id === 'second' ? groupChoices.map(item => <section key={item.name}><SectionTitle title={item.name} /><Standings rows={item.table} logos={logos} /></section>) : <Standings rows={data.table} logos={logos} />)}
        {view === 'teams' && <TeamsGrid teams={league.id === 'second' ? groupChoices.flatMap(item => item.teams || []) : data.teams} logos={logos} favorites={favorites} toggleFavorite={toggleFavorite} />}
      </>}
      {data?.updated_at && <p className="vh-source-note">Aktualizacja źródła: {new Date(data.updated_at).toLocaleString('pl-PL')}</p>}
      {view === 'table' && (league.id === 'second' ? groupChoices : [data]).some(item => Object.keys(item?.source_table_discrepancies || {}).length > 0) && <p className="vh-source-note" role="status">Wyniki i tabela VolleyStation są publikowane osobno. Pokazujemy tabelę dokładnie według źródła.</p>}
    </> : <>
      <div className="vh-segmented" role="tablist" aria-label="Region rozgrywek">{CATEGORIES.map(item => <button role="tab" aria-selected={category === item} className={category === item ? 'selected' : ''} key={item} onClick={() => setCategory(item)}>{item}</button>)}</div>
      {LEAGUES.some(item => item.category === category) ? <><SectionTitle eyebrow={(category === 'Polska' ? 'POLSKA' : category === 'Europa' ? 'EUROPA' : 'ŚWIAT') + ' · MĘŻCZYŹNI'} title="Dostępne ligi" /><div className="vh-league-stack">{LEAGUES.filter(item => item.category === category).map((item, index) => <article className="vh-league-tile vh-league-select" key={item.id}><button className="vh-league-main" onClick={() => openLeague(item.id)}><span className="vh-league-number">{String(index + 1).padStart(2, '0')}</span><span><strong>{item.name}</strong><small>{item.description}</small></span><ChevronRight size={20} /></button><button type="button" className={'vh-star-button ' + (favorites.leagues.includes(item.name) ? 'is-favorite' : '')} aria-label={(favorites.leagues.includes(item.name) ? 'Usuń z' : 'Dodaj do') + ' ulubionych: ' + item.name} onClick={() => toggleFavorite('leagues', item.name)}><Star size={20} fill={favorites.leagues.includes(item.name) ? 'currentColor' : 'none'} /></button></article>)}</div></> : <EmptyState icon={Trophy} title="Wkrótce" message="Nowe rozgrywki dodamy dopiero po weryfikacji oficjalnych źródeł danych. Nie pokazujemy fikcyjnych wyników." />}
    </>}
  </>;
});
export default CompetitionsPage;
