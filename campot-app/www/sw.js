const CACHE_NAME = 'campot-cache-v1';
const ASSETS = [
    './index.html',
    './timer.html',
    './manifest.json',
    './favicon.png',
    './js/offline-queue.js'
];

self.addEventListener('install', (e) => {
    e.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(ASSETS);
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', (e) => {
    e.waitUntil(
        caches.keys().then((keyList) => {
            return Promise.all(keyList.map((key) => {
                if (key !== CACHE_NAME) {
                    return caches.delete(key);
                }
            }));
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', (e) => {
    // Only cache GET requests going to same origin or explicitly added to cache
    if (e.request.method !== 'GET') return;

    e.respondWith(
        fetch(e.request).catch(() => caches.match(e.request))
    );
});

// Periodic background sync if supported/fired
self.addEventListener('sync', (event) => {
    if (event.tag === 'campot-sync-logs') {
        event.waitUntil(flushQueue());
    }
});

async function flushQueue() {
    // In Capacitor/PWA context, we assume the window client will handle flush 
    // when coming online via standard listeners, but we keep this stub for background sync
    const clients = await self.clients.matchAll({ type: 'window' });
    for (const client of clients) {
        client.postMessage({ type: 'FLUSH_QUEUE' });
    }
}
