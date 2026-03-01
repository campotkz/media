require("fake-indexeddb/auto");
if (!global.structuredClone) {
    global.structuredClone = function structuredClone(obj) {
        return JSON.parse(JSON.stringify(obj));
    };
}

const fs = require('fs');
const path = require('path');

const code = fs.readFileSync(path.resolve(__dirname, './offline-queue.js'), 'utf8');

describe('offline-queue.js', () => {
    let originalConsoleLog;
    let originalNavigatorOnLine;

    beforeEach(() => {
        if (global.indexedDB) {
            global.indexedDB = new (require("fake-indexeddb").IDBFactory)();
        }

        Object.defineProperty(navigator, 'serviceWorker', {
            value: {
                register: jest.fn().mockResolvedValue({}),
                addEventListener: jest.fn()
            },
            configurable: true
        });

        originalNavigatorOnLine = navigator.onLine;
        Object.defineProperty(navigator, 'onLine', {
            value: false,
            configurable: true,
            writable: true
        });

        originalConsoleLog = console.log;
        console.log = jest.fn();

        eval(`
            (function() {
                ${code.replace('let dbPromise = null;', 'window.dbPromise = null;').replace(/dbPromise/g, 'window.dbPromise')}
            })();
        `);
    });

    afterEach(() => {
        console.log = originalConsoleLog;
        navigator.onLine = originalNavigatorOnLine;
    });

    describe('enqueueRequest', () => {
        it('should save fetch request params into IndexedDB', async () => {
            const url = 'https://example.com/api';
            const headers = { 'Authorization': 'Bearer test' };
            const body = { data: 'test' };
            const method = 'POST';

            await window.OfflineQueue.enqueueRequest(url, headers, body, method);

            const dbName = 'CampotOfflineDB';
            const storeName = 'log_queue';

            const dbPromise = new Promise((resolve, reject) => {
                const request = indexedDB.open(dbName, 1);
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error);
            });

            const db = await dbPromise;
            const tx = db.transaction(storeName, 'readonly');
            const store = tx.objectStore(storeName);
            const getAllPromise = new Promise((resolve, reject) => {
                const req = store.getAll();
                req.onsuccess = () => resolve(req.result);
                req.onerror = () => reject(req.error);
            });

            const items = await getAllPromise;

            expect(items.length).toBe(1);
            expect(items[0]).toEqual(expect.objectContaining({
                url,
                method,
                headers,
                body,
            }));

            expect(console.log).toHaveBeenCalledWith(
                expect.stringContaining('[Offline Queue] Saved locally [POST]:'),
                expect.any(Object)
            );
        });

        it('should use POST as default method', async () => {
            await window.OfflineQueue.enqueueRequest('url', {}, {});

            const dbName = 'CampotOfflineDB';
            const storeName = 'log_queue';

            const dbPromise = new Promise((resolve, reject) => {
                const request = indexedDB.open(dbName, 1);
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error);
            });

            const db = await dbPromise;
            const tx = db.transaction(storeName, 'readonly');
            const items = await new Promise((resolve, reject) => {
                const req = tx.objectStore(storeName).getAll();
                req.onsuccess = () => resolve(req.result);
                req.onerror = () => reject(req.error);
            });

            expect(items[0].method).toBe('POST');
        });

        it('should reject promise if IndexedDB transaction fails', async () => {
            window.dbPromise = Promise.resolve({
                transaction: function() {
                    return {
                        objectStore: function() {
                            return {
                                add: function() {}
                            };
                        },
                        get error() { return new Error("Transaction failed manually"); },
                        set oncomplete(cb) {},
                        set onerror(cb) {
                            setTimeout(cb, 10);
                        }
                    };
                }
            });

            await expect(window.OfflineQueue.enqueueRequest('url', {}, {}))
                .rejects
                .toThrow('Transaction failed manually');

            window.dbPromise = null;
        });
    });

    describe('trySync', () => {
        beforeEach(() => {
            global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200 });
            navigator.onLine = true;
            eval('isSyncing = false;');
        });

        it('should exit early if offline', async () => {
            navigator.onLine = false;
            await window.OfflineQueue.trySync();
            expect(global.fetch).not.toHaveBeenCalled();
        });

        it('should exit early if already syncing', async () => {
            navigator.onLine = true;
            eval('isSyncing = true;');
            await window.OfflineQueue.trySync();
            expect(global.fetch).not.toHaveBeenCalled();
            eval('isSyncing = false;');
        });

        it('should read items and process them', async () => {
            navigator.onLine = true;
            const url = 'https://example.com/sync';
            const headers = { 'X-Test': '1' };
            const body = { test: 1 };

            window.dbPromise = null;

            // disable sync while enqueueing
            navigator.onLine = false;
            await window.OfflineQueue.enqueueRequest(url, headers, body, 'POST');
            navigator.onLine = true;

            await new Promise((resolve) => {
                window.OfflineQueue.trySync().then(() => {
                    setTimeout(resolve, 50); // wait for internal loop
                });
            });

            expect(global.fetch).toHaveBeenCalledTimes(1);
            expect(global.fetch).toHaveBeenCalledWith(url, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(body)
            });

            const dbPromise = new Promise((resolve, reject) => {
                const request = indexedDB.open('CampotOfflineDB', 1);
                request.onsuccess = () => resolve(request.result);
            });
            const db = await dbPromise;
            const items = await new Promise((resolve, reject) => {
                const req = db.transaction('log_queue', 'readonly').objectStore('log_queue').getAll();
                req.onsuccess = () => resolve(req.result);
            });

            expect(items.length).toBe(0);
        });

        it('should keep items and stop syncing if network fails', async () => {
            navigator.onLine = false; // to prevent sync during enqueueing
            await window.OfflineQueue.enqueueRequest('url1', {}, {}, 'POST');
            await window.OfflineQueue.enqueueRequest('url2', {}, {}, 'POST');
            navigator.onLine = true;

            global.fetch.mockRejectedValueOnce(new Error('Network disconnected'));

            const originalConsoleError = console.error;
            console.error = jest.fn();

            await new Promise((resolve) => {
                window.OfflineQueue.trySync().then(() => {
                    setTimeout(resolve, 50);
                });
            });

            console.error = originalConsoleError;

            expect(global.fetch).toHaveBeenCalledTimes(1);

            const dbPromise = new Promise((resolve, reject) => {
                const request = indexedDB.open('CampotOfflineDB', 1);
                request.onsuccess = () => resolve(request.result);
            });
            const db = await dbPromise;
            const items = await new Promise((resolve, reject) => {
                const req = db.transaction('log_queue', 'readonly').objectStore('log_queue').getAll();
                req.onsuccess = () => resolve(req.result);
            });

            expect(items.length).toBe(2);
        });

        it('should delete items on 400, 404, 409 status codes', async () => {
             navigator.onLine = false;
             await window.OfflineQueue.enqueueRequest('url1', {}, {}, 'POST');
             await window.OfflineQueue.enqueueRequest('url2', {}, {}, 'POST');
             await window.OfflineQueue.enqueueRequest('url3', {}, {}, 'POST');
             navigator.onLine = true;

             global.fetch
                 .mockResolvedValueOnce({ ok: false, status: 400 })
                 .mockResolvedValueOnce({ ok: false, status: 404 })
                 .mockResolvedValueOnce({ ok: false, status: 409 });

             await new Promise((resolve) => {
                window.OfflineQueue.trySync().then(() => {
                    setTimeout(resolve, 50);
                });
            });

             expect(global.fetch).toHaveBeenCalledTimes(3);

             const dbPromise = new Promise((resolve, reject) => {
                const request = indexedDB.open('CampotOfflineDB', 1);
                request.onsuccess = () => resolve(request.result);
            });
            const db = await dbPromise;
            const items = await new Promise((resolve, reject) => {
                const req = db.transaction('log_queue', 'readonly').objectStore('log_queue').getAll();
                req.onsuccess = () => resolve(req.result);
            });

            expect(items.length).toBe(0);
        });
    });
});
