🧪 Add tests for offline-queue using fake-indexeddb

🎯 **What:** The testing gap addressed
Tested the IndexedDB interaction inside the `initDB`, `enqueueRequest` and `trySync` methods of the `OfflineQueue` implementation. Added missing environment testing by mocking `indexedDB` with `fake-indexeddb` and polyfilling dependencies required by `fake-indexeddb` like `structuredClone` (since jest jsdom doesn't expose it correctly).
Set up testing environment to `jsdom` via `package.json` configurations.

📊 **Coverage:** What scenarios are now tested
- The queue functionality properly inserts the URL payload into IndexedDB.
- `trySync` sends offline queued items using `fetch` API when the device correctly reports being online.
- Errors thrown by network (i.e., fetch failures) appropriately keep items in the IndexedDB.
- Unrecoverable HTTP errors (400, 404, 409) will appropriately discard the task from the offline queue.

✨ **Result:** The improvement in test coverage
The critical `offline-queue` synchronization component which ensures that offline users won't lose data and get their interactions synced properly is now reliably verified to catch bugs from refactoring.
