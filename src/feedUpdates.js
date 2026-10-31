// Immutable sharing keeps a score update local to the changed match.
const itemKey = value => {
  if (!value || typeof value !== 'object') return null;
  if (value.home && value.away) return 'match:' + (value.id ?? [value.date, value.time || '', value.home, value.away].join('|'));
  if (value.name) return 'name:' + value.name;
  if (value.team) return 'team:' + value.team;
  return null;
};
export function shareFeedValue(previous, next) {
  if (Object.is(previous, next)) return previous;
  if (!previous || !next || typeof previous !== 'object' || typeof next !== 'object' || Array.isArray(previous) !== Array.isArray(next)) return next;
  if (Array.isArray(next)) {
    const keys = next.map(itemKey), oldKeys = previous.map(itemKey);
    const keyed = keys.every(key => key !== null) && oldKeys.every(key => key !== null) && new Set(keys).size === keys.length && new Set(oldKeys).size === oldKeys.length;
    const byKey = keyed ? new Map(oldKeys.map((key, index) => [key, previous[index]])) : null;
    const values = next.map((value, index) => shareFeedValue(byKey ? byKey.get(keys[index]) : previous[index], value));
    return values.length === previous.length && values.every((value, index) => value === previous[index]) ? previous : values;
  }
  const keys = Object.keys(next);
  let unchanged = keys.length === Object.keys(previous).length;
  const result = {};
  for (const key of keys) {
    result[key] = shareFeedValue(previous[key], next[key]);
    if (!Object.hasOwn(previous, key) || result[key] !== previous[key]) unchanged = false;
  }
  return unchanged ? previous : result;
}
export const LIVE_REFRESH_MS = 10000;
export const FULL_REFRESH_MS = 60000;
