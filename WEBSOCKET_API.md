# 📡 WebSocket API Documentation

Documentation complète de l'API WebSocket bidirectionnelle native (FastAPI backend + TypeScript frontend).

---

## 📋 Table des Matières

1. [Connexion](#connexion)
2. [Format des Messages](#format-des-messages)
3. [Commandes Disponibles](#commandes-disponibles)
4. [Événements Temps Réel](#événements-temps-réel)
5. [Gestion des Erreurs](#gestion-des-erreurs)
6. [Métriques & Monitoring](#métriques--monitoring)
7. [Exemples d'Utilisation](#exemples-dutilisation)

---

## 🔌 Connexion

### Backend (FastAPI)
```python
# Endpoint WebSocket
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    # ...
```

### Frontend (TypeScript)
```typescript
import { initWebSocket, getWebSocket } from '$lib/utils/websocket';

// Initialiser connexion
const ws = initWebSocket();  // Auto-détecte ws://localhost:port/ws

// Ou avec URL spécifique
const ws = initWebSocket('ws://localhost:5001');
```

---

## 📦 Format des Messages

### Message Command (Frontend → Backend)
```json
{
  "type": "command",
  "id": 123,
  "command": "start_scanner",
  "params": {},
  "timestamp": 1699999999999
}
```

### Message Response (Backend → Frontend)
```json
{
  "type": "command_response",
  "id": 123,
  "result": {"status": "started"},
  "error": null,
  "timestamp": 1699999999999
}
```

### Message Event (Backend → Frontend)
```json
{
  "type": "event",
  "event": "status",
  "data": {"is_scanning": true},
  "timestamp": 1699999999999
}
```

---

## 🎮 Commandes Disponibles

### Scanner Commands

#### `start_scanner`
Démarrer le scanner de top pairs.

**Params:** `{}`
**Returns:**
```json
{
  "status": "started",
  "is_scanning": true
}
```

**Example:**
```typescript
const result = await ws.sendCommand('start_scanner');
console.log(result.status); // "started"
```

---

#### `stop_scanner`
Arrêter le scanner.

**Params:** `{}`
**Returns:**
```json
{
  "status": "stopped",
  "is_scanning": false
}
```

---

### Config Commands

#### `get_config`
Récupérer configuration actuelle.

**Params:** `{}`
**Returns:**
```json
{
  "volume_multiplier": 0.95,
  "min_score_required": 7.5,
  "use_confluence": false,
  "tp_sl_mode": "FIXE",
  "tp_percent": 0.25,
  "sl_percent": 0.25,
  "snr_threshold": 0.25,
  "breakout_threshold": 0.35,
  "wick_ratio_max": 2.8,
  "di_gap_min": 4.0,
  "trend_timeframe": "15m",
  "account_size": 1000.0,
  "risk_per_trade": 2.0
}
```

**Example:**
```typescript
const config = await ws.sendCommand('get_config');
console.log(config.tp_sl_mode); // "FIXE"
```

---

#### `update_config`
Mettre à jour la configuration.

**Params:**
```json
{
  "volume_multiplier": 0.9,
  "min_score_required": 8.0
}
```

**Returns:**
```json
{
  "updated": {
    "volume_multiplier": 0.9,
    "min_score_required": 8.0
  }
}
```

**Example:**
```typescript
await ws.sendCommand('update_config', {
  volume_multiplier: 0.9,
  min_score_required: 8.0
});
// Émet automatiquement l'événement 'config_updated'
```

---

### Session Commands

#### `get_sessions`
Récupérer liste des sessions.

**Params:** `{}`
**Returns:**
```json
{
  "sessions": [
    {
      "session_id": "live_1699999999",
      "status": "running",
      "port": 5001,
      "started_at": 1699999999.123
    }
  ]
}
```

---

#### `get_sessions_stats`
Récupérer statistiques globales des sessions.

**Params:** `{}`
**Returns:**
```json
{
  "total_sessions": 1,
  "active_sessions": 1,
  "global_stats": {
    "total_trades": 42,
    "wins": 28,
    "losses": 14,
    "winrate": 66.67
  }
}
```

---

### State Commands

#### `get_state`
Récupérer état complet de l'application.

**Params:** `{}`
**Returns:**
```json
{
  "success": true,
  "session_id": "live_1699999999",
  "config": { ... },
  "scanner": {
    "is_scanning": false,
    "top_pairs": []
  },
  "position": {
    "active": false,
    "data": null
  },
  "stats": {
    "total_trades": 0,
    "wins": 0,
    "losses": 0,
    "winrate": 0.0
  },
  "trades": [],
  "timestamp": 1699999999.123
}
```

---

#### `get_status`
Récupérer status simple (app_state).

**Params:** `{}`
**Returns:** `app_state` complet

---

### Position Commands

#### `close_position`
Fermer position active manuellement.

**Params:** `{}`
**Returns:**
```json
{
  "status": "closed",
  "result": { ... }
}
```

**Throws:** `"Aucune position active"` si pas de position

---

### Log Commands

#### `log_config`
Logger changement de configuration.

**Params:**
```json
{
  "key": "volume_multiplier",
  "change": "0.95 → 0.90"
}
```

**Returns:**
```json
{
  "status": "logged",
  "key": "volume_multiplier",
  "change": "0.95 → 0.90"
}
```

---

## 📡 Événements Temps Réel

### Scanner Events

#### `status`
État global du scanner.

**Data:**
```json
{
  "is_scanning": true,
  "active_position": null,
  "stats": {},
  "top_pairs": []
}
```

**Listener:**
```typescript
ws.on('status', (data) => {
  console.log('Scanner status:', data.is_scanning);
});
```

---

#### `scan_started`
Scanner démarré.

**Data:**
```json
{
  "timestamp": 1699999999.123
}
```

---

#### `top_pairs_update`
Mise à jour des top pairs.

**Data:**
```json
{
  "pairs": [
    {"symbol": "BTCUSDT", "score": 9.5},
    {"symbol": "ETHUSDT", "score": 8.2}
  ]
}
```

---

### Session Events

#### `sessions_update`
État sessions changé.

**Data:**
```json
{
  "timestamp": 1699999999.123
}
```

---

#### `session_started`
Session/scanner démarré.

**Data:**
```json
{
  "timestamp": 1699999999.123
}
```

---

#### `session_stopped`
Session/scanner arrêté.

**Data:**
```json
{
  "timestamp": 1699999999.123
}
```

---

### Config Events

#### `config_updated`
Configuration mise à jour.

**Data:**
```json
{
  "updated": {
    "volume_multiplier": 0.9
  },
  "timestamp": 1699999999.123
}
```

**Listener:**
```typescript
ws.on('config_updated', (data) => {
  console.log('Config changed:', data.updated);
  // Rafraîchir UI automatiquement
});
```

---

### Connection Events

#### `connect`
Connexion établie.

**Listener:**
```typescript
ws.on('connect', () => {
  console.log('✅ Connected to WebSocket');
});
```

---

#### `disconnect`
Connexion perdue.

**Data:**
```json
{
  "code": 1006,
  "reason": "Connection lost"
}
```

---

#### `error`
Erreur WebSocket.

**Data:** `Error` object

---

## ⚠️ Gestion des Erreurs

### Erreur Command Timeout
```typescript
try {
  await ws.sendCommand('get_config');
} catch (error) {
  if (error.message.includes('timeout')) {
    console.error('Command timeout après 30s');
  }
}
```

### Erreur Rate Limit
```typescript
try {
  // Trop de commandes en 1 seconde
  for (let i = 0; i < 20; i++) {
    await ws.sendCommand('get_status');
  }
} catch (error) {
  if (error.message.includes('Rate limit')) {
    console.error('Rate limit: max 10 commands/sec');
  }
}
```

### Retry Automatique
```typescript
import { sendCommandWithRetryViaWS } from '$lib/utils/websocket';

// Retry jusqu'à 3 fois avec exponential backoff
const result = await sendCommandWithRetryViaWS('start_scanner', {}, 3);
```

---

## 📊 Métriques & Monitoring

### Récupérer Métriques
```typescript
import { getWebSocketMetrics } from '$lib/utils/websocket';

const metrics = getWebSocketMetrics();
console.log(metrics);
// {
//   commandsSent: 150,
//   commandsSucceeded: 148,
//   commandsFailed: 2,
//   averageResponseTime: 45.2,
//   totalResponseTime: 6780,
//   reconnections: 1
// }
```

### Component Svelte Métriques
```svelte
<script>
  import WebSocketMetrics from '$lib/components/WebSocketMetrics.svelte';
</script>

<WebSocketMetrics />
```

---

## 💡 Exemples d'Utilisation

### Démarrer Scanner avec Retry
```typescript
import { getWebSocket, sendCommandWithRetryViaWS } from '$lib/utils/websocket';

async function startScanning() {
  try {
    // Retry automatique si échec (max 3 tentatives)
    const result = await sendCommandWithRetryViaWS('start_scanner', {}, 3);
    console.log('Scanner started:', result.status);
  } catch (error) {
    console.error('Failed to start scanner after 3 retries:', error);
  }
}
```

### Mettre à Jour Config et Écouter Changements
```typescript
const ws = getWebSocket();

// Écouter les mises à jour de config
ws.on('config_updated', (data) => {
  console.log('Config updated:', data.updated);
  // Rafraîchir UI
  refreshConfigPanel();
});

// Mettre à jour config
await ws.sendCommand('update_config', {
  volume_multiplier: 0.95,
  min_score_required: 8.0
});
// → Émet automatiquement 'config_updated'
```

### Écouter Événements Sessions avec Cleanup
```typescript
import { onMount, onDestroy } from 'svelte';

let unsubscribe = [];

onMount(() => {
  const ws = getWebSocket();

  unsubscribe.push(ws.on('session_started', () => {
    console.log('Session started!');
    loadGlobalStats();
  }));

  unsubscribe.push(ws.on('session_stopped', () => {
    console.log('Session stopped!');
    loadGlobalStats();
  }));
});

onDestroy(() => {
  // Cleanup listeners (évite memory leaks)
  unsubscribe.forEach(fn => fn());
});
```

### Monitorer Performance
```typescript
import { getWebSocketMetrics } from '$lib/utils/websocket';

setInterval(() => {
  const metrics = getWebSocketMetrics();
  console.log(`
    Commands: ${metrics.commandsSent}
    Success Rate: ${(metrics.commandsSucceeded / metrics.commandsSent * 100).toFixed(1)}%
    Avg Response: ${metrics.averageResponseTime.toFixed(0)}ms
    Reconnections: ${metrics.reconnections}
  `);
}, 10000); // Toutes les 10 secondes
```

---

## 🔥 Migration depuis REST

| REST Endpoint | WebSocket Command | Event |
|--------------|-------------------|-------|
| GET /api/config | `get_config` | `config_updated` |
| POST /api/config | `update_config` | `config_updated` |
| GET /api/state | `get_state` | - |
| GET /api/status | `get_status` | `status` |
| POST /api/start | `start_scanner` | `session_started` |
| POST /api/stop | `stop_scanner` | `session_stopped` |
| GET /api/sessions | `get_sessions` | `sessions_update` |
| GET /api/sessions/stats/global | `get_sessions_stats` | `sessions_update` |

**Avantages WebSocket:**
- ✅ Bidirectionnel (push temps réel)
- ✅ Pas de polling (économie bande passante)
- ✅ Retry automatique intégré
- ✅ Rate limiting anti-spam
- ✅ Métriques de performance
- ✅ Événements temps réel

---

## 🛡️ Sécurité & Limites

- **Rate Limit**: Max 10 commands/seconde
- **Timeout**: 30 secondes par command
- **Max Queue**: 100 messages (évite memory overflow)
- **Reconnexion**: Max 10 tentatives avec exponential backoff
- **Heartbeat**: Ping/Pong toutes les 30 secondes

---

**Dernière mise à jour**: 2025-11-10
**Version API**: 1.0.0
**Branche**: claude/claude3-011CUycbZyp8U3cuy4HYLNWy
