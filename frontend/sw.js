const CACHE_NAME = 'soho-cafe-v2';
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/css/style.css',
    '/js/app.js',
    '/manifest.json'
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(STATIC_ASSETS))
            .then(() => self.skipWaiting())
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames
                    .filter(name => name !== CACHE_NAME)
                    .map(name => caches.delete(name))
            );
        }).then(() => self.clients.claim())
    );
});

// Fetch event - serve from cache or network
self.addEventListener('fetch', (event) => {
    const { request } = event;
    
    // Skip non-GET requests
    if (request.method !== 'GET') return;
    
    // Skip API requests
    if (request.url.includes('/api/')) {
        event.respondWith(fetch(request));
        return;
    }
    
    // Skip CRM pages - always fetch fresh
    if (request.url.includes('/crm-')) {
        event.respondWith(fetch(request));
        return;
    }
    
    event.respondWith(
        caches.match(request)
            .then(response => {
                // Return cached version or fetch from network
                if (response) {
                    return response;
                }
                
                return fetch(request)
                    .then(networkResponse => {
                        // Cache successful responses
                        if (networkResponse.ok && request.url.startsWith(self.location.origin)) {
                            const clone = networkResponse.clone();
                            caches.open(CACHE_NAME)
                                .then(cache => cache.put(request, clone));
                        }
                        return networkResponse;
                    })
                    .catch(() => {
                        // Offline fallback for HTML requests
                        if (request.headers.get('accept').includes('text/html')) {
                            return caches.match('/index.html');
                        }
                    });
            })
    );
});

// Background sync for offline orders
self.addEventListener('sync', (event) => {
    if (event.tag === 'sync-orders') {
        event.waitUntil(syncOrders());
    }
});

async function syncOrders() {
    // Sync pending orders when back online
    const pending = await getPendingOrders();
    for (const order of pending) {
        try {
            await fetch('/api/orders/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(order)
            });
            await removePendingOrder(order.id);
        } catch (err) {
            console.error('Failed to sync order:', err);
        }
    }
}

// Push notifications
self.addEventListener('push', (event) => {
    const data = event.data.json();
    event.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: '/icons/icon-192x192.png',
            badge: '/icons/icon-72x72.png',
            data: data.url
        })
    );
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    event.waitUntil(
        clients.openWindow(event.notification.data || '/')
    );
});
