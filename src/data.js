export const LEAGUES = [
  { id: 'men', name: 'TAURON Liga Mężczyzn', short: 'TAURON Liga', category: 'Polska', description: 'Najwyższa klasa rozgrywkowa mężczyzn', file: 'tauron.json' },
  { id: 'first', name: 'TAURON 1. Liga Mężczyzn', short: 'TAURON 1. Liga', category: 'Polska', description: 'Pierwsza liga mężczyzn', file: 'tauron1liga.json' },
  { id: 'second', name: 'II Liga Mężczyzn', short: 'II Liga Mężczyzn', category: 'Polska', description: 'Rozgrywki grupowe PZPS', file: '2liga.json' },
  { id: 'pomorska', name: 'Pomorska III Liga Męska', short: 'Pomorska III Liga', category: 'Polska', description: 'Dane oficjalne z VolleyStation', file: 'pomorska3liga.json' }
];

export const CATEGORIES = ['Polska', 'Europa', 'Reprezentacje', 'Świat'];
export const WEEKDAYS = ['NIEDZ.', 'PON.', 'WT.', 'ŚR.', 'CZW.', 'PT.', 'SOB.'];
export const pad = number => String(number).padStart(2, '0');
export function dateKey(date) {
  return [date.getFullYear(), pad(date.getMonth() + 1), pad(date.getDate())].join('-');
}
export function fromKey(key) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(key || ''));
  if (!match) return null;
  const date = new Date(+match[1], +match[2] - 1, +match[3], 12);
  return dateKey(date) === key ? date : null;
}
export function addDays(value, count) {
  const date = new Date(value);
  date.setDate(date.getDate() + count);
  return date;
}
export function feedDateKey(value) {
  const match = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(String(value || ''));
  return match ? match[3] + '-' + match[2] + '-' + match[1] : '';
}
export function normalizeName(value) {
  return String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pl-PL').replace(/[^a-z0-9]/g, '');
}
export function isLive(match) {
  return match?.status === 'live' || (match?.status !== 'finished' && match?.status !== 'scheduled' && match?.current_points != null);
}
export function isFinished(match) {
  return match?.status === 'finished';
}
export function flattenFeed(data, id) {
  if (id !== 'second') return { ...data, matches: Array.isArray(data.matches) ? data.matches : [], teams: Array.isArray(data.teams) ? data.teams : [] };
  const groups = Array.isArray(data.groups) ? data.groups : [];
  return {
    ...data,
    matches: groups.flatMap(group => (group.matches || []).map(match => ({ ...match, group: match.group || group.name }))),
    teams: groups.flatMap(group => group.teams || [])
  };
}
export function uniqueMatches(matches) {
  const seen = new Map();
  for (const match of matches || []) {
    if (!match?.home || !match?.away) continue;
    const key = [feedDateKey(match.date), match.time || '', ...[normalizeName(match.home), normalizeName(match.away)].sort()].join('|');
    const previous = seen.get(key);
    const weight = value => (isFinished(value) ? 2 : isLive(value) ? 1 : 0) * 100 + (value?.set_scores?.length || 0);
    if (!previous || weight(match) > weight(previous)) seen.set(key, match);
  }
  return [...seen.values()].sort((a, b) => (feedDateKey(a.date) + (a.time || '')).localeCompare(feedDateKey(b.date) + (b.time || '')));
}
export function teamIndex(feeds) {
  const teams = new Map();
  for (const league of LEAGUES) {
    const data = feeds[league.id];
    for (const item of data?.teams || []) {
      const key = normalizeName(item.name);
      const existing = teams.get(key);
      if (!existing || (!existing.logo && item.logo)) teams.set(key, { name: item.name, logo: item.logo || '' });
    }
  }
  return [...teams.values()].sort((a, b) => a.name.localeCompare(b.name, 'pl'));
}
export function matchesFromFeeds(feeds, selectedLeague = null) {
  return LEAGUES.filter(league => !selectedLeague || league.id === selectedLeague).flatMap(league =>
    uniqueMatches(feeds[league.id]?.matches).map(match => ({ ...match, leagueId: league.id, leagueName: league.short }))
  ).sort((a, b) => (feedDateKey(a.date) + (a.time || '')).localeCompare(feedDateKey(b.date) + (b.time || '')));
}
export async function fetchLeague(league, signal) {
  const path = import.meta.env.BASE_URL + 'data/' + league.file;
  const response = await fetch(path, { signal, cache: 'no-store' });
  if (!response.ok) throw new Error('HTTP ' + response.status);
  const json = await response.json();
  if (!json || typeof json !== 'object') throw new Error('Nieprawidłowy format danych');
  return flattenFeed(json, league.id);
}
export function readFavorites() {
  try {
    const saved = JSON.parse(localStorage.getItem('vh-favs') || '{}');
    return {
      teams: Array.isArray(saved.teams) ? [...new Set(saved.teams.filter(x => typeof x === 'string'))] : [],
      leagues: Array.isArray(saved.leagues) ? [...new Set(saved.leagues.filter(x => typeof x === 'string'))] : []
    };
  } catch {
    return { teams: [], leagues: [] };
  }
}
