/* FoetoPath PWA — Service Worker */
const CACHE_NAME = 'foetopath-foet-v10';
const ASSETS = [
  '/pwa/foet/',
  '/pwa/foet/index.html',
  '/pwa/foet/dossier_router.html',
  '/pwa/foet/style.css',
  '/pwa/foet/helpers.js',
  '/pwa/foet/pwa_common.js',
  '/pwa/foet/references.js',
  '/pwa/foet/logo.png',
  '/pwa/foet/manifest.json',
  '/pwa/foet/macro_frais.html',
  '/pwa/foet/macro_autopsie.html',
  '/pwa/foet/macro_fixe.html',
  '/pwa/foet/radio.html',
  '/pwa/foet/neuropath.html',
  '/pwa/foet/settings.html',
  '/static/i18n.js',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  // API calls: network-first
  if (url.pathname.startsWith('/admin/api/') || url.pathname.startsWith('/api/')) {
    e.respondWith(
      fetch(e.request).catch(() => caches.match(e.request))
    );
    return;
  }
  // Assets: cache-first
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request))
  );
});
