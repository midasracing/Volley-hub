import React, { useMemo, useState } from 'react';
import { Check, ChevronRight, Heart, Search, Star, Trophy } from 'lucide-react';
import { LEAGUES, normalizeName } from '../data.js';
import { sameName } from '../nameUtils.js';
import TeamLogo from '../components/TeamLogo.jsx';
import TeamsGrid from '../components/TeamsGrid.jsx';
import { EmptyState, PageHeader, SectionTitle } from '../components/UiPrimitives.jsx';

const leagueByName = name => LEAGUES.find(item => item.name === name);

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
    </> : <EmptyState icon={Heart} title="Jeszcze nic tutaj nie ma" message={tab === 'teams' ? 'Znajdź drużyny poniżej i dodaj je do obserwowanych.' : 'Dodaj ulubione ligi, aby mieć do nich szybki dostęp.'} />}
    <SectionTitle eyebrow="ODKRYWAJ" title={tab === 'teams' ? 'Dodaj drużyny' : 'Dodaj rozgrywki'} />
    {tab === 'teams' && <label className="vh-search-input"><Search size={20} /><input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Szukaj drużyny…" /></label>}
    <div className="vh-picker-list">{(tab === 'teams' ? matches : LEAGUES.map(item => ({ name: item.name }))).slice(0, 100).map(item => {
      const chosen = selected.some(name => sameName(name, item.name));
      return <button key={item.name} type="button" className="vh-picker-row" onClick={() => toggleFavorite(tab, item.name)}>{tab === 'teams' ? <TeamLogo name={item.name} logo={item.logo || logos.get(normalizeName(item.name))} /> : <span className="vh-mini-league"><Trophy size={17} /></span>}<span>{item.name}</span><span className={'vh-picker-check ' + (chosen ? 'selected' : '')}>{chosen ? <Check size={17} /> : <Star size={16} />}</span></button>;
    })}{tab === 'teams' && !matches.length && <p className="vh-source-note">Nie znaleziono drużyn.</p>}</div>
  </>;
});
export default FavoritesPage;
