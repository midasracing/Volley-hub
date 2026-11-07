// Match-specific canonical links published by the importer. Channel names in
// `broadcast` remain labels; a bare TV marker never becomes a guessed stream.
export function broadcastLinks(match) {
  if (!Array.isArray(match?.broadcast_urls)) return [];
  return [...new Set(match.broadcast_urls.filter(url => typeof url === 'string' &&
    /^https:\/\/www\.youtube\.com\/watch\?v=[A-Za-z0-9_-]{11}$/.test(url)))];
}
