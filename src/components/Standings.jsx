import { Trophy } from 'lucide-react';
import { normalizeName } from '../data.js';
import TeamLogo from './TeamLogo.jsx';
import { EmptyState } from './UiPrimitives.jsx';

export default function Standings({ rows = [], logos }) {
  if (!rows.length) return <EmptyState title="Tabela niedostępna" message="Oficjalne źródło nie udostępnia jeszcze tabeli dla tej grupy." icon={Trophy} />;
  return <div className="vh-table-scroll" role="region" tabIndex={0} aria-label="Tabela ligowa — przewijana poziomo">
    <table className="vh-table"><thead><tr><th scope="col">#</th><th scope="col">Drużyna</th><th scope="col">Pkt</th><th scope="col">M</th><th scope="col">W</th><th scope="col">P</th><th scope="col">Sety</th></tr></thead>
      <tbody>{rows.map((row, index) => <tr key={row.team || index}><td>{row.rank || index + 1}</td><td><span className="vh-table-team"><TeamLogo name={row.team} logo={logos.get(normalizeName(row.team))} />{row.team}</span></td><td><strong>{row.points ?? '–'}</strong></td><td>{row.played ?? '–'}</td><td>{row.wins ?? '–'}</td><td>{row.losses ?? '–'}</td><td>{row.sets_for ?? '–'}:{row.sets_against ?? '–'}</td></tr>)}</tbody></table>
  </div>;
}
