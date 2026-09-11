const CACHE_NAME = 'trainings-tracker-v1';

const ASSETS = [
    '/',
    '/static/style.css',
    '/static/manifest.json',
    '/static/icons/icon-192x192.png',
    '/static/icons/icon-512x512.png'
];

// Bei Installation: Dateien cachen
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(ASSETS);
        })
    );
    self.skipWaiting();
});

// Bei Aktivierung: alte Caches löschen
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(
                keys.filter(key => key !== CACHE_NAME)
                    .map(key => caches.delete(key))
            );
        })
    );
});

// Netzwerk-Anfragen: erst Netzwerk, dann Cache als Fallback
self.addEventListener('fetch', event => {
    event.respondWith(
        fetch(event.request)
            .then(response => {
                // Kopie im Cache speichern
                const copy = response.clone();
                caches.open(CACHE_NAME).then(cache => {
                    cache.put(event.request, copy);
                });
                return response;
            })
            .catch(() => {
                // Kein Netzwerk? Aus Cache laden
                return caches.match(event.request);
            })
    );
});