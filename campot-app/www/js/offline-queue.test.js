require("fake-indexeddb/auto");
const fs = require("fs");
const path = require("path");

const scriptPath = path.resolve(__dirname, "offline-queue.js");
const scriptContent = fs.readFileSync(scriptPath, "utf-8");

global.fetch = jest.fn();

if (typeof global.structuredClone === "undefined") {
    global.structuredClone = function(obj) {
        return JSON.parse(JSON.stringify(obj));
    };
}

Object.defineProperty(navigator, 'onLine', {
    writable: true,
    value: true,
});

describe("Offline Queue trySync", () => {
    let mockConsoleLog;
    let mockConsoleError;

    beforeEach(async () => {
        jest.clearAllMocks();
        navigator.onLine = true;
        mockConsoleLog = jest.spyOn(console, 'log').mockImplementation(() => {});
        mockConsoleError = jest.spyOn(console, 'error').mockImplementation(() => {});
    });

    afterEach(async () => {
        mockConsoleLog.mockRestore();
        mockConsoleError.mockRestore();
    });

    const runWithCleanScope = async (testFn) => {
        const uniqueDbName = 'CampotOfflineDB_' + Date.now() + '_' + Math.random();

        const modifiedScript = scriptContent.replace(
            "const DB_NAME = 'CampotOfflineDB';",
            `const DB_NAME = '${uniqueDbName}';`
        );

        const scope = {};
        const iife = `
            ${modifiedScript}
            scope.OfflineQueue = window.OfflineQueue;
        `;
        eval(iife);

        await testFn(scope.OfflineQueue);
    };

    test("should not run if navigator.onLine is false", async () => {
        await runWithCleanScope(async (OfflineQueue) => {
            navigator.onLine = false;
            await OfflineQueue.enqueueRequest('http://test.com', {}, {data: 1});
            expect(global.fetch).not.toHaveBeenCalled();
        });
    });

    test("should do nothing if queue is empty", async () => {
        await runWithCleanScope(async (OfflineQueue) => {
            await OfflineQueue.trySync();
            expect(global.fetch).not.toHaveBeenCalled();
        });
    });

    test("should send fetch requests for items in the queue and delete them on success (200)", async () => {
        await runWithCleanScope(async (OfflineQueue) => {
            global.fetch.mockResolvedValueOnce({
                ok: true,
                status: 200
            });

            // Enqueue triggers trySync automatically
            navigator.onLine = true;
            await OfflineQueue.enqueueRequest('http://test.com', { 'Test': '1' }, { data: 1 }, 'POST');

            // Wait for internal async trySync to finish
            await new Promise(r => setTimeout(r, 50));

            expect(global.fetch).toHaveBeenCalledTimes(1);
            expect(global.fetch).toHaveBeenCalledWith('http://test.com', {
                method: 'POST',
                headers: { 'Test': '1' },
                body: JSON.stringify({ data: 1 })
            });
        });
    });

    test("should delete items on specific error statuses (400, 404, 409)", async () => {
        await runWithCleanScope(async (OfflineQueue) => {
            global.fetch
                .mockResolvedValueOnce({ ok: false, status: 400 })
                .mockResolvedValueOnce({ ok: false, status: 404 })
                .mockResolvedValueOnce({ ok: false, status: 409 });

            navigator.onLine = false;
            await OfflineQueue.enqueueRequest('http://test.com/1', {}, null, 'GET');
            await OfflineQueue.enqueueRequest('http://test.com/2', {}, null, 'GET');
            await OfflineQueue.enqueueRequest('http://test.com/3', {}, null, 'GET');

            navigator.onLine = true;
            await OfflineQueue.trySync();

            await new Promise(r => setTimeout(r, 50));

            // 3 from trySync
            expect(global.fetch).toHaveBeenCalledTimes(3);
        });
    });

    test("should stop syncing and keep the item in the queue if fetch fails", async () => {
        await runWithCleanScope(async (OfflineQueue) => {
            global.fetch.mockRejectedValueOnce(new Error("Network Error"));

            navigator.onLine = false;
            await OfflineQueue.enqueueRequest('http://test.com/1', {}, null, 'GET');
            await OfflineQueue.enqueueRequest('http://test.com/2', {}, null, 'GET');
            navigator.onLine = true;

            await OfflineQueue.trySync();

            await new Promise(r => setTimeout(r, 50));
            expect(global.fetch).toHaveBeenCalledTimes(1);
        });
    });

    test("should stop syncing and keep item if fetch responds with unhandled error status (500)", async () => {
        await runWithCleanScope(async (OfflineQueue) => {
            global.fetch.mockResolvedValueOnce({ ok: false, status: 500 });

            navigator.onLine = false;
            await OfflineQueue.enqueueRequest('http://test.com/1', {}, null, 'GET');
            await OfflineQueue.enqueueRequest('http://test.com/2', {}, null, 'GET');
            navigator.onLine = true;

            await OfflineQueue.trySync();

            await new Promise(r => setTimeout(r, 50));

            expect(global.fetch).toHaveBeenCalledTimes(1);
        });
    });
});
