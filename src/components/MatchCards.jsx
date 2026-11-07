import React, { useId, useState } from 'react';
import { ArrowRight, ChevronRight, Clock3 } from 'lucide-react';
import { LEAGUES, isFinished, isLive, normalizeName } from '../data.js';
import { broadcastLinks } from '../broadcasts.js';
import { AnimatedSets } from './ScheduleMotion.jsx';
import { ScoreValue } from './MatchMotion.jsx';
import TeamLogo from './TeamLogo.jsx';
import { EmptyState } from './UiPrimitives.jsx';

function Status({ match }) {
  if (isLive(match)) return <span className="im-live">NA ŻYWO</span>;
  if (isFinished(match)) return <span>Zakończony</span>;
  return <span>Zaplanowany</span>;
}
const MatchCard = React.memo(function MatchCard({ match, logos, compact = false }) {
  const [expanded, setExpanded] = useState(false);
  const [infoOpen, setInfoOpen] = useState(false);
  const detailsId = useId();
  const infoId = useId();
  const finished = isFinished(match);
  const score = finished || isLive(match);
  const homeWins = score && Number(match.home_sets) > Number(match.away_sets);
  const awayWins = score && Number(match.away_sets) > Number(match.home_sets);
  const scores = Array.isArray(match.set_scores) ? match.set_scores : [];
  const channels = Array.isArray(match.broadcast) ? match.broadcast : match.broadcast ? [match.broadcast] : [];
  const streams = broadcastLinks(match);
  const hasInfo = Boolean(match.round != null || match.venue || channels.length || match.phase || match.match_number || match.term_number || match.source_url);
  const verifiedPlsUrl = /^(https:\/\/www\.tauron(?:1)?liga\.pl\/games\/action\/show\/id\/\d+\/)/.test(match.source_url || '') ? match.source_url : null;
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
    {(score || match.time || hasInfo) && <div className="vh-match-footer">
      <span><Clock3 size={14} /> {match.time || 'Godzina nieustalona'}</span>
      {streams.map(url => <a key={url} className="vh-details-button" href={url} target="_blank" rel="noopener noreferrer">{finished ? 'Nagranie' : 'Transmisja'} · YouTube<ArrowRight size={15} /></a>)}
      {scores.length > 0 && <button className="vh-details-button" onClick={() => setExpanded(current => !current)} type="button" aria-expanded={expanded} aria-controls={detailsId}>{expanded ? 'Ukryj sety' : 'Pokaż sety'}<ChevronRight size={15} className={expanded ? 'vh-rotate' : ''} /></button>}
      {hasInfo && <button className="vh-details-button" onClick={() => setInfoOpen(value => !value)} type="button" aria-expanded={infoOpen} aria-controls={infoId}>{infoOpen ? 'Ukryj informacje' : 'Informacje o meczu'}<ChevronRight size={15} className={infoOpen ? 'vh-rotate' : ''} /></button>}
      {isLive(match) && match.current_points && <span>Aktualny set: <ScoreValue className="vh-live-points" value={String(match.current_points)} /></span>}
    </div>}
    {scores.length > 0 && <AnimatedSets scores={scores} expanded={expanded} detailsId={detailsId} />}
    {hasInfo && infoOpen && <div id={infoId} className="vh-match-information" role="region" aria-label="Informacje o meczu">
      <dl>
        {match.round != null && <><dt>Kolejka</dt><dd>{match.round}</dd></>}
        {match.phase && <><dt>Faza</dt><dd>{match.phase}</dd></>}
        {match.venue?.name && <><dt>Hala</dt><dd>{match.venue.name}</dd></>}
        {(match.venue?.address || match.venue?.city) && <><dt>Lokalizacja</dt><dd>{[match.venue.address, match.venue.city].filter(Boolean).join(', ')}</dd></>}
        {channels.length > 0 && <><dt>Transmisja</dt><dd>{channels.join(', ')}</dd></>}
        {match.match_number && <><dt>Numer meczu</dt><dd>{match.match_number}</dd></>}
        {match.term_number != null && <><dt>Termin PLS</dt><dd>{match.term_number}</dd></>}
      </dl>
      {verifiedPlsUrl && <a href={verifiedPlsUrl} target="_blank" rel="noopener noreferrer">Oficjalna karta meczu w PLS</a>}
    </div>}
  </article>;
});

export function MatchGroups({ matches, logos, emptyMessage, compact = false }) {
  if (!matches.length) return <EmptyState title="Brak meczów" message={emptyMessage || 'Na razie nie ma spotkań spełniających te kryteria.'} />;
  const groups = LEAGUES.map(league => ({ league, matches: matches.filter(match => match.leagueId === league.id) })).filter(group => group.matches.length);
  return <div className="vh-match-groups">{groups.map(group => <section key={group.league.id}>
    <h3 className="im-league"><span className="im-flag">{group.league.flag || '🇵🇱'}</span>{group.league.short}<span className="vh-count">{group.matches.length}</span></h3>
    {group.matches.map(match => <MatchCard key={group.league.id + ':' + (match.id ?? [match.date, match.time || '', match.home, match.away].join('|'))} match={match} logos={logos} compact={compact} />)}
  </section>)}</div>;
}
