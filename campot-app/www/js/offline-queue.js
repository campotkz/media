const DB_NAME = 'CampotOfflineDB';
const STORE_NAME = 'log_queue';

let dbPromise = null;

function initDB() {
    if (!dbPromise) {
        dbPromise = new Promise((resolve, reject) => {
            const request = indexedDB.open(DB_NAME, 1);
            request.onupgradeneeded = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains(STORE_NAME)) {
                    db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
                }
            };
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
    return dbPromise;
}

// enqueue fetch request params
async function enqueueRequest(url, headers, body) {
    const db = await initDB();
    const item = {
        url: url,
        headers: headers,
        body: body,
        timestamp: new Date().getTime()
    };
    return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, 'readwrite');
        const store = tx.objectStore(STORE_NAME);
        store.add(item);
        tx.oncomplete = () => {
            console.log('[Offline Queue] Saved locally:', item);
            trySync();
            resolve();
        };
        tx.onerror = () => reject(tx.error);
    });
}

let isSyncing = false;
async function trySync() {
    if (isSyncing || !navigator.onLine) return;
    isSyncing = true;
    const db = await initDB();

    return new Promise((resolve) => {
        const tx = db.transaction(STORE_NAME, 'readonly');
        const store = tx.objectStore(STORE_NAME);
        const req = store.getAll();

        req.onsuccess = async () => {
            const items = req.result;
            if (items.length === 0) {
                isSyncing = false;
                return resolve();
            }
            console.log(`[Offline Queue] Found ${items.length} items to sync`);

            for (const item of items) {
                try {
                    const res = await fetch(item.url, {
                        method: 'POST',
                        headers: item.headers || { 'Content-Type': 'application/json' },
                        body: JSON.stringify(item.body),
                    });

                    if (res.ok || res.status === 400 || res.status === 409) {
                        // Delete item from local queue on success or unrecoverable error
                        const delTx = db.transaction(STORE_NAME, 'readwrite');
                        delTx.objectStore(STORE_NAME).delete(item.id);
                        await new Promise(r => delTx.oncomplete = r);
                        console.log(`[Offline Queue] Synced item ${item.id}`);
                    } else {
                        throw new Error(`Server returned ${res.status}`);
                    }
                } catch (e) {
                    console.error('[Offline Queue] Sync failed for item', item.id, e);
                    break; // Stop syncing on first network failure
                }
            }
            isSyncing = false;
            resolve();
        };
    });
}

window.addEventListener('online', () => {
    console.log('[Offline Queue] Back online. Flushing queue...');
    trySync();
});

// Expose API globally
window.OfflineQueue = { enqueueRequest, trySync };

if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('./sw.js').then(reg => {
        console.log('SW Registered');
        navigator.serviceWorker.addEventListener('message', event => {
            if (event.data && event.data.type === 'FLUSH_QUEUE') {
                trySync();
            }
        });
    });
}
