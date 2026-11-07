import { Star } from 'lucide-react';
import { normalizeName } from '../data.js';
import { sameName } from '../nameUtils.js';
import TeamLogo from './TeamLogo.jsx';
import { EmptyState } from './UiPrimitives.jsx';

export default function TeamsGrid({ teams = [], logos, favorites, toggleFavorite }) {
  if (!teams.length) return <EmptyState title="Brak listy drużyn" message="Lista zespołów nie jest jeszcze dostępna w oficjalnym źródle." />;
  return <div className="vh-team-grid">{teams.map((team, index) => <article className="vh-team-tile" key={team.name + index}><TeamLogo name={team.name} logo={team.logo || logos.get(normalizeName(team.name))} /><strong>{team.name}</strong><button type="button" aria-label={(favorites.teams.some(x => sameName(x, team.name)) ? 'Usuń z' : 'Dodaj do') + ' ulubionych: ' + team.name} onClick={() => toggleFavorite('teams', team.name)} className={favorites.teams.some(x => sameName(x, team.name)) ? 'is-favorite' : ''}><Star size={19} fill={favorites.teams.some(x => sameName(x, team.name)) ? 'currentColor' : 'none'} /></button></article>)}</div>;
}
