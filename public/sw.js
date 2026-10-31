/* The app shell must be built by Vite, not GitHub Pages' Jekyll branch build. */
const CACHE = 'volley-hub-vite-shell-v3';
const SHELL = ['./manifest.webmanifest'];
const isBuiltApp = html =>
  html.includes('assets/index-') &&
  html.includes('type="module"') &&
  !html.includes('src/main.jsx');

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL))
    .then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(key => key.startsWith('volley-hub-') && key !== CACHE)
      .map(key => caches.delete(key))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  const data = url.pathname.includes('/data/') && url.pathname.endsWith('.json');

  if (request.mode === 'navigate') {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE);
      try {
        const response = await fetch(request, { cache: 'no-store' });
        if (!response.ok) throw new Error('Unavailable app shell');
        const html = await response.clone().text();
        if (!isBuiltApp(html)) throw new Error('Wrong GitHub Pages source');
        await cache.put('./index.html', response.clone());
        return response;
      } catch {
        return (await cache.match('./index.html')) ||
          new Response('Aplikacja chwilowo niedostępna. Odśwież stronę.', {
            status: 503, headers: { 'Content-Type': 'text/plain; charset=utf-8' }
          });
      }
    })());
    return;
  }

  if (data) {
    event.respondWith(fetch(request).then(response => {
      if (response.ok) caches.open(CACHE).then(cache => cache.put(request, response.clone())).catch(() => {});
      return response;
    }).catch(async () =>
      (await caches.match(request, { ignoreSearch: true })) ||
      new Response(JSON.stringify({ error: true, message: 'Brak połączenia' }), {
        status: 503, headers: { 'Content-Type': 'application/json' }
      })));
    return;
  }

  // Versioned Vite JS/CSS assets are immutable and safe to cache-first.
  event.respondWith(caches.match(request).then(cached => cached || fetch(request).then(response => {
    if (response.ok) caches.open(CACHE).then(cache => cache.put(request, response.clone())).catch(() => {});
    return response;
  })));
});
