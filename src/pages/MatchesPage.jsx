import React, { useMemo, useRef, useState } from 'react';
import { LEAGUES, dateKey, feedDateKey } from '../data.js';
import DateStrip from '../components/DateStrip.jsx';
import { useAnimatedDate } from '../components/ScheduleMotion.jsx';
import { FeedWarning, LoadingCards } from '../components/UiPrimitives.jsx';
import { MatchGroups } from '../components/MatchCards.jsx';

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
export default MatchesPage;
