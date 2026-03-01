const fs = require('fs');
const path = require('path');

// Read the service worker code
const swCode = fs.readFileSync(path.join(__dirname, 'sw.js'), 'utf8');

describe('Service Worker', () => {
    let mockClients;

    beforeEach(() => {
        // Mock self and clients
        mockClients = {
            matchAll: jest.fn()
        };

        global.self = {
            addEventListener: jest.fn(),
            skipWaiting: jest.fn(),
            clients: mockClients
        };

        // We can't use eval to define the global functions properly if they aren't on the global object,
        // so we use a small script wrapper to ensure `flushQueue` is accessible on the `global` object.
        const script = `
            ${swCode}
            if (typeof flushQueue !== 'undefined') {
                global.flushQueue = flushQueue;
            }
        `;

        // Execute the service worker code in the current context
        try {
            eval(script);
        } catch (e) {
            // Ignore errors from missing Cache APIs, etc. We just want flushQueue
            // which is defined at the bottom.
        }
    });

    afterEach(() => {
        delete global.self;
        delete global.flushQueue;
    });

    describe('flushQueue', () => {
        it('should post FLUSH_QUEUE message to all window clients', async () => {
            // Arrange
            const client1 = { postMessage: jest.fn() };
            const client2 = { postMessage: jest.fn() };
            mockClients.matchAll.mockResolvedValue([client1, client2]);

            // Act
            await global.flushQueue();

            // Assert
            expect(mockClients.matchAll).toHaveBeenCalledWith({ type: 'window' });
            expect(client1.postMessage).toHaveBeenCalledWith({ type: 'FLUSH_QUEUE' });
            expect(client2.postMessage).toHaveBeenCalledWith({ type: 'FLUSH_QUEUE' });
        });

        it('should do nothing if there are no window clients', async () => {
            // Arrange
            mockClients.matchAll.mockResolvedValue([]);

            // Act
            await global.flushQueue();

            // Assert
            expect(mockClients.matchAll).toHaveBeenCalledWith({ type: 'window' });
            // Should not throw or fail
        });
    });
});
