// Service Worker — Macro Placenta PWA
const CACHE_NAME = 'placenta-v7';
const ASSETS = [
  '/pwa/placentas/',
  '/pwa/placentas/index.html',
  '/pwa/placentas/macro_frais.html',
  '/pwa/placentas/tranches_section.html',
  '/pwa/placentas/manifest.json',
  '/pwa/placentas/logo.png',
  '/pwa/placentas/sw.js',
  '/static/i18n.js',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  // Network-first pour les API, cache-first pour les assets
  if (e.request.url.includes('/placenta/api/')) {
    e.respondWith(
      fetch(e.request).catch(() => caches.match(e.request))
    );
  } else {
    e.respondWith(
      caches.match(e.request).then(r => r || fetch(e.request))
    );
  }
});
