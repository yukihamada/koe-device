const CACHE = 'koe-v2';
const PRECACHE = ['/app', '/manifest.json'];
const MUSIC_CACHE = 'koe-music-v1';

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE && k !== MUSIC_CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  // Cache music files on first play
  if (url.pathname.startsWith('/music/')) {
    e.respondWith(
      caches.open(MUSIC_CACHE).then(c =>
        c.match(e.request).then(r => r || fetch(e.request).then(resp => {
          c.put(e.request, resp.clone());
          return resp;
        }))
      )
    );
    return;
  }
  // Network first, cache fallback for app
  e.respondWith(
    fetch(e.request).then(r => {
      if (r.ok && url.pathname === '/app') {
        caches.open(CACHE).then(c => c.put(e.request, r.clone()));
      }
      return r;
    }).catch(() => caches.match(e.request))
  );
});
