require("fake-indexeddb/auto");
const fs = require('fs');
const path = require('path');

// Polyfill structuredClone for Node versions that might not have it or where it's not global in jsdom
if (typeof structuredClone === 'undefined') {
    global.structuredClone = function(val) {
        return JSON.parse(JSON.stringify(val));
    };
}

const offlineQueueCode = fs.readFileSync(path.resolve(__dirname, 'offline-queue.js'), 'utf8');

describe('Offline Queue', () => {
    let mockFetch;

    beforeEach(async () => {
        document.body.innerHTML = '';

        Object.defineProperty(global, 'navigator', {
            value: {
                onLine: true,
                serviceWorker: {
                    register: jest.fn().mockResolvedValue({}),
                    addEventListener: jest.fn()
                }
            },
            configurable: true,
            writable: true
        });

        // Mock window.addEventListener
        global.window.addEventListener = jest.fn();

        mockFetch = jest.fn().mockResolvedValue({
            ok: true,
            status: 200
        });
        global.fetch = mockFetch;

        // suppress console.log and error in tests
        global.console.log = jest.fn();
        global.console.error = jest.fn();

        // Run the script to initialize window.OfflineQueue
        eval(offlineQueueCode);

        // Pre-create the database to ensure it exists before tests run, mimicking browser state
        await eval(`window.OfflineQueue.enqueueRequest('init_url', {}, {}, 'POST')`);

        await new Promise(r => setTimeout(r, 50));

        // Clear the init data from the store
        await new Promise((resolve, reject) => {
            const request = indexedDB.open('CampotOfflineDB', 1);
            request.onsuccess = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains('log_queue')) {
                    db.close();
                    return resolve();
                }
                const tx = db.transaction('log_queue', 'readwrite');
                tx.objectStore('log_queue').clear();
                tx.oncomplete = () => {
                    db.close();
                    resolve();
                };
                tx.onerror = () => reject(tx.error);
            };
            request.onerror = () => reject(request.error);
        });

        // Reset fetch mock from init call
        mockFetch.mockClear();
    });

    afterEach(async () => {
        // Clear the data from the store, but keep the database structure
        // This avoids issues where the internal dbPromise holds a closed or deleted connection
        await new Promise((resolve, reject) => {
            const request = indexedDB.open('CampotOfflineDB', 1);
            request.onsuccess = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains('log_queue')) {
                    db.close();
                    return resolve();
                }
                const tx = db.transaction('log_queue', 'readwrite');
                tx.objectStore('log_queue').clear();
                tx.oncomplete = () => {
                    db.close();
                    resolve();
                };
                tx.onerror = () => reject(tx.error);
            };
            request.onerror = () => reject(request.error);
        });

        // Reset syncing state for next test
        eval("isSyncing = false;");
    });

    // Helper function to easily check contents of IndexedDB store
    const getQueueItems = () => new Promise((resolve, reject) => {
        const request = indexedDB.open('CampotOfflineDB', 1);
        request.onsuccess = (e) => {
            const db = e.target.result;
            const tx = db.transaction('log_queue', 'readonly');
            const store = tx.objectStore('log_queue');
            const getReq = store.getAll();
            getReq.onsuccess = () => {
                db.close();
                resolve(getReq.result);
            };
            getReq.onerror = () => {
                db.close();
                reject(getReq.error);
            };
        };
        request.onerror = () => reject(request.error);
    });

    it('should have initialized OfflineQueue globally', () => {
        expect(window.OfflineQueue).toBeDefined();
        expect(typeof window.OfflineQueue.enqueueRequest).toBe('function');
        expect(typeof window.OfflineQueue.trySync).toBe('function');
    });

    describe('Offline Sync Functionality', () => {
        it('should create the database and store when enqueueing', async () => {
            const url = 'https://example.com/api';
            const headers = { 'Content-Type': 'application/json' };
            const body = { test: true };

            global.navigator.onLine = false;

            await window.OfflineQueue.enqueueRequest(url, headers, body, 'POST');

            const items = await getQueueItems();
            expect(items.length).toBe(1);
            expect(items[0].url).toBe(url);
            expect(items[0].method).toBe('POST');
            expect(items[0].body).toEqual(body);
        });

        it('should enqueue and then trySync when online', async () => {
            const url = 'https://example.com/api';
            const headers = { 'Content-Type': 'application/json' };
            const body = { test: true };

            global.navigator.onLine = true;
            await window.OfflineQueue.enqueueRequest(url, headers, body, 'POST');

            // wait for the sync processing to complete
            await new Promise(r => setTimeout(r, 100));

            expect(mockFetch).toHaveBeenCalled();
            expect(mockFetch).toHaveBeenCalledWith(url, expect.objectContaining({
                method: 'POST',
                headers: headers,
                body: JSON.stringify(body)
            }));

            // Should delete item after success
            const items = await getQueueItems();
            expect(items.length).toBe(0);
        });

        it('should remove items from queue on unrecoverable errors (400, 404, 409)', async () => {
            const url = 'https://example.com/api';

            mockFetch.mockResolvedValue({
                ok: false,
                status: 404
            });

            global.navigator.onLine = true;
            await window.OfflineQueue.enqueueRequest(url, {}, {}, 'POST');

            await new Promise(r => setTimeout(r, 100));

            const items = await getQueueItems();
            expect(items.length).toBe(0);
        });

        it('should keep items in queue on network failures', async () => {
            const url = 'https://example.com/api';

            mockFetch.mockRejectedValue(new TypeError('Failed to fetch'));

            global.navigator.onLine = true;
            await window.OfflineQueue.enqueueRequest(url, {}, {}, 'POST');

            await new Promise(r => setTimeout(r, 100));

            const items = await getQueueItems();
            expect(items.length).toBe(1);
        });
    });
});
