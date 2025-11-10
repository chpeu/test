# 🧪 Plan de Tests Frontend - WebSocket Client

Documentation des tests à implémenter pour le client WebSocket TypeScript.

---

## 📋 Tests à Implémenter

### 1. Tests Retry Logic

**Fichier**: `src/lib/utils/__tests__/websocket-retry.test.ts`

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { WebSocketClient } from '../websocket-impl';

describe('WebSocket Retry Logic', () => {
  let client: WebSocketClient;
  let mockWebSocket: any;

  beforeEach(() => {
    // Mock WebSocket
    global.WebSocket = vi.fn(() => mockWebSocket) as any;
    client = new WebSocketClient('ws://localhost:5000/ws');
  });

  afterEach(() => {
    client.disconnect();
    vi.restoreAllMocks();
  });

  it('should retry command on failure with exponential backoff', async () => {
    let attempts = 0;
    const startTime = Date.now();

    // Mock sendCommand to fail twice, succeed on third attempt
    vi.spyOn(client as any, 'sendCommand').mockImplementation(async () => {
      attempts++;
      if (attempts < 3) {
        throw new Error('Command failed');
      }
      return { success: true };
    });

    const result = await client.sendCommandWithRetry('test_command', {}, 3);

    expect(result).toEqual({ success: true });
    expect(attempts).toBe(3);

    // Verify exponential backoff (1s + 2s = 3s minimum)
    const elapsed = Date.now() - startTime;
    expect(elapsed).toBeGreaterThanOrEqual(3000);
  });

  it('should not retry on rate limit error', async () => {
    let attempts = 0;

    vi.spyOn(client as any, 'sendCommand').mockImplementation(async () => {
      attempts++;
      throw new Error('Rate limit exceeded');
    });

    await expect(client.sendCommandWithRetry('test_command', {}, 3))
      .rejects.toThrow('Rate limit exceeded');

    // Should fail immediately without retries
    expect(attempts).toBe(1);
  });

  it('should throw error after max retries exceeded', async () => {
    vi.spyOn(client as any, 'sendCommand').mockRejectedValue(new Error('Permanent failure'));

    await expect(client.sendCommandWithRetry('test_command', {}, 2))
      .rejects.toThrow("Command 'test_command' failed after 3 attempts");
  });
});
```

---

### 2. Tests Rate Limiting

**Fichier**: `src/lib/utils/__tests__/websocket-ratelimit.test.ts`

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { WebSocketClient } from '../websocket-impl';

describe('WebSocket Rate Limiting', () => {
  let client: WebSocketClient;

  beforeEach(() => {
    client = new WebSocketClient('ws://localhost:5000/ws');
    // Mock connected state
    (client as any).connected = true;
  });

  it('should allow up to 10 commands per second', async () => {
    const commands = Array(10).fill(null).map((_, i) =>
      client.sendCommand(`cmd_${i}`, {})
    );

    // All 10 should succeed
    await expect(Promise.all(commands)).resolves.toBeDefined();
  });

  it('should block 11th command within 1 second', async () => {
    // Send 10 commands rapidly
    for (let i = 0; i < 10; i++) {
      await client.sendCommand(`cmd_${i}`, {});
    }

    // 11th command should fail due to rate limit
    await expect(client.sendCommand('cmd_11', {}))
      .rejects.toThrow('Rate limit');
  });

  it('should reset rate limit after 1 second', async () => {
    // Send 10 commands
    for (let i = 0; i < 10; i++) {
      await client.sendCommand(`cmd_${i}`, {});
    }

    // Wait 1.1 seconds
    await new Promise(resolve => setTimeout(resolve, 1100));

    // Should allow new commands
    await expect(client.sendCommand('cmd_after_wait', {}))
      .resolves.toBeDefined();
  });

  it('should track command timestamps in sliding window', () => {
    const now = Date.now();
    (client as any).commandTimestamps = [
      now - 2000,  // Outside window
      now - 500,   // Inside window
      now - 200,   // Inside window
    ];

    const canSend = (client as any).checkRateLimit();

    // Should have removed old timestamp
    expect((client as any).commandTimestamps.length).toBe(3); // 2 old + 1 new
  });
});
```

---

### 3. Tests Timeout

**Fichier**: `src/lib/utils/__tests__/websocket-timeout.test.ts`

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { WebSocketClient } from '../websocket-impl';

describe('WebSocket Command Timeout', () => {
  let client: WebSocketClient;

  beforeEach(() => {
    client = new WebSocketClient('ws://localhost:5000/ws');
    (client as any).connected = true;
  });

  it('should timeout command after 30 seconds', async () => {
    vi.useFakeTimers();

    // Mock send to never respond
    vi.spyOn(client as any, 'send').mockImplementation(() => {});

    const commandPromise = client.sendCommand('slow_command', {});

    // Fast-forward 30 seconds
    vi.advanceTimersByTime(30000);

    await expect(commandPromise).rejects.toThrow('timeout');

    vi.useRealTimers();
  });

  it('should not timeout if response received within 30s', async () => {
    vi.useFakeTimers();

    const commandPromise = client.sendCommand('fast_command', {});

    // Simulate response after 10 seconds
    vi.advanceTimersByTime(10000);

    // Manually trigger response
    const commandId = (client as any).lastCommandId;
    (client as any).handleMessage({
      type: 'command_response',
      id: commandId,
      result: { success: true },
      error: null
    });

    await expect(commandPromise).resolves.toEqual({ success: true });

    vi.useRealTimers();
  });

  it('should clean up timeout on successful response', async () => {
    const clearTimeoutSpy = vi.spyOn(global, 'clearTimeout');

    const promise = client.sendCommand('test', {});

    // Trigger response
    const commandId = (client as any).lastCommandId;
    (client as any).handleMessage({
      type: 'command_response',
      id: commandId,
      result: {},
      error: null
    });

    await promise;

    expect(clearTimeoutSpy).toHaveBeenCalled();
  });
});
```

---

### 4. Tests Métriques

**Fichier**: `src/lib/utils/__tests__/websocket-metrics.test.ts`

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { WebSocketClient, getWebSocketMetrics, resetWebSocketMetrics } from '../websocket-impl';

describe('WebSocket Metrics', () => {
  let client: WebSocketClient;

  beforeEach(() => {
    resetWebSocketMetrics();
    client = new WebSocketClient('ws://localhost:5000/ws');
  });

  it('should track commands sent', async () => {
    await client.sendCommand('cmd1', {});
    await client.sendCommand('cmd2', {});

    const metrics = getWebSocketMetrics();
    expect(metrics.commandsSent).toBe(2);
  });

  it('should track successful commands', async () => {
    // Mock successful response
    const commandId = (client as any).lastCommandId + 1;
    const promise = client.sendCommand('cmd', {});

    (client as any).handleMessage({
      type: 'command_response',
      id: commandId,
      result: {},
      error: null
    });

    await promise;

    const metrics = getWebSocketMetrics();
    expect(metrics.commandsSucceeded).toBe(1);
    expect(metrics.commandsFailed).toBe(0);
  });

  it('should track failed commands', async () => {
    const commandId = (client as any).lastCommandId + 1;
    const promise = client.sendCommand('cmd', {});

    (client as any).handleMessage({
      type: 'command_response',
      id: commandId,
      result: null,
      error: 'Command failed'
    });

    await expect(promise).rejects.toThrow();

    const metrics = getWebSocketMetrics();
    expect(metrics.commandsSucceeded).toBe(0);
    expect(metrics.commandsFailed).toBe(1);
  });

  it('should calculate average response time', async () => {
    // Simulate multiple commands with different response times
    const times = [100, 200, 300];

    for (const time of times) {
      const start = Date.now();
      const commandId = (client as any).lastCommandId + 1;
      const promise = client.sendCommand('cmd', {});

      setTimeout(() => {
        (client as any).handleMessage({
          type: 'command_response',
          id: commandId,
          result: {},
          error: null
        });
      }, time);

      await promise;
    }

    const metrics = getWebSocketMetrics();
    expect(metrics.averageResponseTime).toBeCloseTo(200, 0); // (100+200+300)/3
  });

  it('should track reconnections', () => {
    (client as any).handleReconnect();
    (client as any).handleReconnect();

    const metrics = getWebSocketMetrics();
    expect(metrics.reconnections).toBe(2);
  });

  it('should reset metrics', () => {
    client.sendCommand('cmd', {});

    resetWebSocketMetrics();

    const metrics = getWebSocketMetrics();
    expect(metrics.commandsSent).toBe(0);
    expect(metrics.commandsSucceeded).toBe(0);
    expect(metrics.commandsFailed).toBe(0);
  });
});
```

---

### 5. Tests Queue Overflow

**Fichier**: `src/lib/utils/__tests__/websocket-queue.test.ts`

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { WebSocketClient } from '../websocket-impl';

describe('WebSocket Queue Overflow Protection', () => {
  let client: WebSocketClient;

  beforeEach(() => {
    client = new WebSocketClient('ws://localhost:5000/ws');
  });

  it('should queue messages when disconnected', () => {
    (client as any).connected = false;

    client.sendCommand('cmd1', {});
    client.sendCommand('cmd2', {});

    expect((client as any).messageQueue.length).toBe(2);
  });

  it('should limit queue to MAX_QUEUE_SIZE (100)', () => {
    (client as any).connected = false;
    const MAX_QUEUE_SIZE = 100;

    // Send 150 messages
    for (let i = 0; i < 150; i++) {
      client.sendCommand(`cmd_${i}`, {});
    }

    // Should only keep last 100
    expect((client as any).messageQueue.length).toBe(MAX_QUEUE_SIZE);
  });

  it('should use FIFO when queue overflows', () => {
    (client as any).connected = false;
    const MAX_QUEUE_SIZE = 100;

    // Send 110 messages
    for (let i = 0; i < 110; i++) {
      client.sendCommand(`cmd_${i}`, {});
    }

    const queue = (client as any).messageQueue;

    // First message should be cmd_10 (first 10 dropped)
    expect(JSON.parse(queue[0]).command).toBe('cmd_10');

    // Last message should be cmd_109
    expect(JSON.parse(queue[99]).command).toBe('cmd_109');
  });

  it('should flush queue on reconnect', async () => {
    (client as any).connected = false;

    // Queue 5 messages
    for (let i = 0; i < 5; i++) {
      client.sendCommand(`cmd_${i}`, {});
    }

    expect((client as any).messageQueue.length).toBe(5);

    // Reconnect
    (client as any).connected = true;
    await (client as any).flushQueue();

    // Queue should be empty
    expect((client as any).messageQueue.length).toBe(0);
  });
});
```

---

## 🚀 Installation et Exécution

### Installation Vitest

```bash
cd frontend
npm install -D vitest @vitest/ui
```

### Configuration package.json

Ajouter dans `scripts`:
```json
"test": "vitest",
"test:ui": "vitest --ui",
"test:coverage": "vitest --coverage"
```

### Exécution Tests

```bash
# Run all tests
npm test

# Run tests with UI
npm run test:ui

# Run tests with coverage
npm run test:coverage

# Run specific test file
npm test websocket-retry.test.ts
```

---

## 📊 Couverture Attendue

| Module | Tests | Couverture Cible |
|--------|-------|------------------|
| Retry Logic | 3 tests | 100% |
| Rate Limiting | 4 tests | 100% |
| Timeout | 3 tests | 100% |
| Métriques | 6 tests | 100% |
| Queue Overflow | 4 tests | 100% |
| **TOTAL** | **20 tests** | **100%** |

---

## 🔧 Prochaines Étapes

1. ✅ Installer Vitest
2. ✅ Créer fichiers de tests
3. ✅ Implémenter les tests listés ci-dessus
4. ✅ Exécuter et vérifier couverture
5. ✅ Intégrer dans CI/CD

---

**Créé**: 10 Novembre 2025
**Version**: v7.0
**Branche**: claude/fix-multiple-errors-011CUycbZyp8U3cuy4HYLNWy
