const CACHE = 'volley-hub-techtext-v1';
const SHELL = ['./', './index.html', './manifest.webmanifest'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('volley-hub-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  const json = url.pathname.includes('/data/') && url.pathname.endsWith('.json');
  if (json || request.mode === 'navigate') {
    event.respondWith(fetch(request).then(response => {
      if (response.ok) caches.open(CACHE).then(cache => cache.put(request, response.clone())).catch(() => {});
      return response;
    }).catch(async () => {
      const cached = await caches.match(request, { ignoreSearch: true });
      if (cached) return cached;
      if (json) return new Response(JSON.stringify({ error: true, message: 'Brak połączenia' }), { status: 503, headers: { 'Content-Type': 'application/json' } });
      return (await caches.match('./index.html')) || new Response('Offline', { status: 503 });
    }));
    return;
  }
  event.respondWith(caches.match(request).then(cached => cached || fetch(request).then(response => {
    if (response.ok) caches.open(CACHE).then(cache => cache.put(request, response.clone())).catch(() => {});
    return response;
  })));
});
