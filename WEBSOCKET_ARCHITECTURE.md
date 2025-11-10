# 🏗️ Architecture WebSocket - Diagramme Complet

Documentation visuelle de l'architecture WebSocket bidirectionnelle native.

---

## 📐 Vue d'Ensemble

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ARCHITECTURE WEBSOCKET                              │
│                         (100% Natif - Socket.IO supprimé)                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────┐                    ┌──────────────────────────┐
│   FRONTEND (Svelte)      │◄──────WebSocket───►│   BACKEND (FastAPI)      │
│   Port: 5173 (dev)       │   bidirectionnel   │   Port: 5001             │
└──────────────────────────┘                    └──────────────────────────┘
```

---

## 🔄 Flux de Communication

### 1️⃣ Initialisation Connexion

```
FRONTEND                                    BACKEND
    │                                           │
    │  new WebSocket('ws://localhost:5001/ws') │
    ├──────────────────────────────────────────►
    │                                           │
    │                       WebSocket.onopen()  │
    │◄──────────────────────────────────────────┤
    │  {type: 'event', event: 'connect'}        │
    │◄──────────────────────────────────────────┤
    │                                           │
    │  État initial envoyé                      │
    │◄──────────────────────────────────────────┤
    │  {type: 'event', event: 'status',         │
    │   data: {is_scanning: false, ...}}        │
    │                                           │
```

### 2️⃣ Envoi Command (Frontend → Backend)

```
FRONTEND                                    BACKEND
    │                                           │
    │  ws.sendCommand('start_scanner')          │
    │  {type: 'command', id: 1,                 │
    │   command: 'start_scanner', params: {}}   │
    ├──────────────────────────────────────────►
    │                                           │
    │                  handle_client_command()  │
    │                            ▼               │
    │                       await api_start()   │
    │                            ▼               │
    │                   app_state['is_scanning']=True
    │                            ▼               │
    │  Réponse command                          │
    │◄──────────────────────────────────────────┤
    │  {type: 'command_response', id: 1,        │
    │   result: {status: 'started'}}            │
    │                                           │
    │  Événement push automatique               │
    │◄──────────────────────────────────────────┤
    │  {type: 'event', event: 'session_started'}│
    │◄──────────────────────────────────────────┤
    │  {type: 'event', event: 'status',         │
    │   data: {is_scanning: true}}              │
    │                                           │
```

### 3️⃣ Événement Push (Backend → Frontend)

```
BACKEND (Trigger Interne)                   FRONTEND
    │                                           │
    ▼                                           │
  Trade fermé (position_manager)                │
    ▼                                           │
  ws_manager.emit('trade_closed', {...})        │
    ├──────────────────────────────────────────►
    │  {type: 'event', event: 'trade_closed',   │
    │   data: {pnl: 12.5, symbol: 'BTCUSDT'}}   │
    │                                           │
    │                      ws.on('trade_closed')│
    │                           ▼               │
    │                  updateUI() automatique   │
    │                  notification browser     │
    │                                           │
```

---

## 🏗️ Architecture Détaillée

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            FRONTEND (SvelteKit)                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  COMPOSANTS SVELTE                                                 │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │  │
│  │  │ +page.svelte│  │GlobalStats  │  │ Settings    │               │  │
│  │  │ (12 events) │  │ (3 events)  │  │ (1 command) │               │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │  │
│  │         │                 │                 │                      │  │
│  │         └─────────────────┴─────────────────┘                      │  │
│  │                           │                                        │  │
│  └───────────────────────────┼────────────────────────────────────────┘  │
│                              │                                           │
│  ┌───────────────────────────┼────────────────────────────────────────┐  │
│  │  STORES (Svelte)          │                                         │  │
│  │  ┌────────────────────────▼─────────────────────────┐              │  │
│  │  │  sessions.js                                      │              │  │
│  │  │  • loadSessions() → ws.sendCommand()             │              │  │
│  │  │  • loadGlobalStats() → ws.sendCommand()          │              │  │
│  │  └────────────────────────┬─────────────────────────┘              │  │
│  └───────────────────────────┼────────────────────────────────────────┘  │
│                              │                                           │
│  ┌───────────────────────────┼────────────────────────────────────────┐  │
│  │  WEBSOCKET CLIENT         │                                         │  │
│  │  ┌────────────────────────▼─────────────────────────┐              │  │
│  │  │  websocket-impl.ts (BidirectionalWebSocket)      │              │  │
│  │  │  ┌────────────────────────────────────────────┐  │              │  │
│  │  │  │  FEATURES                                   │  │              │  │
│  │  │  │  • sendCommand(cmd, params)                │  │              │  │
│  │  │  │  • sendCommandWithRetry() [NOUVEAU]        │  │              │  │
│  │  │  │  • Rate Limiting (10/sec) [NOUVEAU]        │  │              │  │
│  │  │  │  • Timeout (30s) [NOUVEAU]                 │  │              │  │
│  │  │  │  • Métriques Performance [NOUVEAU]         │  │              │  │
│  │  │  │  • Queue MAX_SIZE=100                      │  │              │  │
│  │  │  │  • Exponential Backoff Reconnect           │  │              │  │
│  │  │  │  • Heartbeat Ping/Pong (30s)               │  │              │  │
│  │  │  └────────────────────────────────────────────┘  │              │  │
│  │  └──────────────────────────────────────────────────┘              │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                              │                                           │
│                              │ WebSocket Native                          │
│                              │ ws://localhost:5001/ws                   │
└──────────────────────────────┼───────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                            BACKEND (FastAPI)                              │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  WEBSOCKET ENDPOINT                                                  │  │
│  │  ┌───────────────────────────────────────────────────────────────┐  │  │
│  │  │  @app.websocket("/ws")                                         │  │  │
│  │  │  async def websocket_endpoint(websocket: WebSocket)            │  │  │
│  │  │  ▼                                                              │  │  │
│  │  │  • ws_manager.connect(websocket)                               │  │  │
│  │  │  • Envoyer état initial                                        │  │  │
│  │  │  • Boucle receive messages                                     │  │  │
│  │  │    ├─ type='command' → handle_client_command()                │  │  │
│  │  │    ├─ type='request' → handle_client_request()                │  │  │
│  │  │    └─ type='ping' → send pong                                 │  │  │
│  │  └───────────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  COMMAND HANDLER                                                     │  │
│  │  ┌───────────────────────────────────────────────────────────────┐  │  │
│  │  │  async def handle_client_command(command, params)              │  │  │
│  │  │  ▼                                                              │  │  │
│  │  │  • start_scanner      → api_start()                            │  │  │
│  │  │  • stop_scanner       → api_stop()                             │  │  │
│  │  │  • update_config      → TRADING_CONFIG.update()                │  │  │
│  │  │  • get_config         → TRADING_CONFIG.get()                   │  │  │
│  │  │  • get_state          → _get_complete_state_data()             │  │  │
│  │  │  • get_sessions       → sessions data                          │  │  │
│  │  │  • get_sessions_stats → global stats                           │  │  │
│  │  │  • close_position     → api_close_position()                   │  │  │
│  │  │  • log_config         → add_log()                              │  │  │
│  │  └───────────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  WEBSOCKET MANAGER                                                   │  │
│  │  ┌───────────────────────────────────────────────────────────────┐  │  │
│  │  │  class WebSocketManager                                        │  │  │
│  │  │  • connect(websocket)                                          │  │  │
│  │  │  • disconnect(websocket)                                       │  │  │
│  │  │  • emit(event, data) → broadcast à tous clients               │  │  │
│  │  │  • send_personal_message(data, websocket)                     │  │  │
│  │  └───────────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  EVENT SOURCES (Émetteurs d'événements)                             │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │  │
│  │  │api_start()   │  │api_stop()    │  │update_config │              │  │
│  │  │emit:         │  │emit:         │  │emit:         │              │  │
│  │  │session_start │  │session_stop  │  │config_updated│              │  │
│  │  │sessions_upd  │  │sessions_upd  │  │              │              │  │
│  │  │status        │  │status        │  │              │              │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Flux de Données - Exemple Complet

### Scénario : Démarrer Scanner et Recevoir Updates

```
┌────────────┐                                          ┌────────────┐
│  FRONTEND  │                                          │  BACKEND   │
└─────┬──────┘                                          └──────┬─────┘
      │                                                        │
      │ 1. User click "Start Scanner"                         │
      │                                                        │
      │ 2. ws.sendCommand('start_scanner')                    │
      ├───────────────────────────────────────────────────────►
      │                                                        │
      │                                3. handle_client_command()
      │                                   ▼                    │
      │                                4. api_start()          │
      │                                   ▼                    │
      │                                5. scanner.scan_top_pairs()
      │                                   ▼                    │
      │                                6. app_state['is_scanning']=True
      │                                   ▼                    │
      │                                7. ws_manager.emit('status')
      │                                   ▼                    │
      │                                8. ws_manager.emit('session_started')
      │                                   ▼                    │
      │ 9. Response command                                    │
      │◄───────────────────────────────────────────────────────┤
      │    {type: 'command_response', result: {status: 'started'}}
      │                                                        │
      │ 10. Event 'status' (push)                             │
      │◄───────────────────────────────────────────────────────┤
      │    {type: 'event', event: 'status',                   │
      │     data: {is_scanning: true}}                        │
      │                                                        │
      │ 11. Event 'session_started' (push)                    │
      │◄───────────────────────────────────────────────────────┤
      │    {type: 'event', event: 'session_started'}          │
      │                                                        │
      │ 12. Event 'sessions_update' (push)                    │
      │◄───────────────────────────────────────────────────────┤
      │    {type: 'event', event: 'sessions_update'}          │
      │                                                        │
      ▼                                                        ▼
 ┌─────────┐                                           ┌─────────┐
 │ UI Update│                                           │ Scanner │
 │ - Button │                                           │ Running │
 │ - Stats  │                                           │         │
 └─────────┘                                           └─────────┘
```

---

## 🔧 Mécanismes Clés

### Rate Limiting
```
┌─────────────────────────────────────────────┐
│  Rate Limiter (Frontend)                     │
├─────────────────────────────────────────────┤
│  • MAX: 10 commands / 1 seconde             │
│  • Sliding Window Algorithm                 │
│  • Reject avec error "Rate limit exceeded"  │
└─────────────────────────────────────────────┘

Timeline (1 seconde):
|---C---C---C---C---C---C---C---C---C---C---|  OK (10 commands)
                                         C  X   REJECTED (11ème)
```

### Retry Logic avec Exponential Backoff
```
Attempt 1:  Send ──X Failed
             ▼
            Wait 1s (2^0 * 1000ms)
             ▼
Attempt 2:  Send ──X Failed
             ▼
            Wait 2s (2^1 * 1000ms)
             ▼
Attempt 3:  Send ──X Failed
             ▼
            Wait 4s (2^2 * 1000ms)
             ▼
Attempt 4:  Send ──✓ Success!
```

### Command Timeout
```
Send Command (t=0s)
    │
    ├─ Timeout Timer Started (30s)
    │
    ├─ ... waiting ...
    │
    ├─ t=30s → No response
    │
    └─ Reject Promise: "Command timeout after 30000ms"
```

### Queue Overflow Protection
```
WebSocket Disconnected
    ▼
Messages queued: [M1, M2, M3, ..., M100]  ← MAX_QUEUE_SIZE=100
    ▼
New message M101 arrives
    ▼
FIFO Strategy: Remove M1 (oldest)
    ▼
Queue: [M2, M3, ..., M100, M101]  ← Still 100 messages
```

---

## 📈 Métriques Collectées

```
┌────────────────────────────────────────────────────┐
│  WebSocket Metrics                                 │
├────────────────────────────────────────────────────┤
│  • commandsSent:        150                        │
│  • commandsSucceeded:   148  (98.7%)               │
│  • commandsFailed:      2    (1.3%)                │
│  • averageResponseTime: 45.2ms                     │
│  • totalResponseTime:   6780ms                     │
│  • reconnections:       1                          │
└────────────────────────────────────────────────────┘

Calcul Success Rate:
  successRate = (commandsSucceeded / commandsSent) * 100
  successRate = (148 / 150) * 100 = 98.7%

Calcul Average Response Time:
  avgResponseTime = totalResponseTime / (commandsSucceeded + commandsFailed)
  avgResponseTime = 6780 / 150 = 45.2ms
```

---

## 🔄 Comparaison REST vs WebSocket

| Fonctionnalité | REST (Avant) | WebSocket (Après) |
|----------------|-------------|-------------------|
| **Latence** | 50-200ms (HTTP) | 1-5ms (WS frame) |
| **Overhead** | Headers HTTP (800B) | Frame WS (2-14B) |
| **Bidirectionnel** | ❌ Polling requis | ✅ Natif |
| **Push Serveur** | ❌ Long Polling | ✅ Natif |
| **Bande passante** | 10 req/sec = 8KB/sec | 10 msg/sec = 1KB/sec |
| **Connexions** | 1 par requête | 1 persistante |
| **Retry Logic** | ❌ Manuel | ✅ Automatique |
| **Rate Limiting** | ❌ | ✅ Intégré |
| **Métriques** | ❌ | ✅ Automatique |

**Gain Bande Passante:**
- REST: 10 requêtes/sec × 800 bytes = **8 KB/sec**
- WebSocket: 10 messages/sec × 100 bytes = **1 KB/sec**
- **Réduction: 87.5%** 🎉

---

## 🛡️ Sécurité

```
┌─────────────────────────────────────────────────────────┐
│  LAYERS DE SÉCURITÉ                                      │
├─────────────────────────────────────────────────────────┤
│  1. Rate Limiting         → Max 10 cmd/sec              │
│  2. Command Timeout       → Max 30s par command         │
│  3. Queue Max Size        → Max 100 messages            │
│  4. Input Validation      → Validation params backend   │
│  5. Error Handling        → Pas de stack trace exposé   │
│  6. Heartbeat             → Détection connexion morte   │
│  7. Max Reconnect Attempts→ Max 10 tentatives           │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 Points Clés Architecture

1. **100% WebSocket Natif** - Socket.IO complètement supprimé
2. **Bidirectionnel Complet** - Commands (F→B) + Events (B→F)
3. **Retry Automatique** - Exponential backoff intégré
4. **Rate Limiting** - Protection anti-spam 10 cmd/sec
5. **Métriques Temps Réel** - Performance monitoring intégré
6. **Memory Safe** - Queue bounded, listener cleanup
7. **Production Ready** - Timeout, reconnect, error handling

---

**Dernière mise à jour**: 2025-11-10
**Version**: 1.0.0
**Branche**: claude/claude3-011CUycbZyp8U3cuy4HYLNWy
