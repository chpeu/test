# Exemples d'Implémentation WebSocket Natif

## 🔧 Backend - Migration Complète

### 1. Modifier `main.py`

```python
# AVANT (Socket.IO)
import socketio

sio = socketio.AsyncServer(cors_allowed_origins="*", async_mode='asgi')
socketio_app = socketio.ASGIApp(sio, app)

@sio.on('connect')
async def handle_connect(sid, environ):
    await sio.emit('status', app_state, room=sid)

# APRÈS (WebSocket Natif)
from fastapi import WebSocket, WebSocketDisconnect
from core.websocket_manager import WebSocketManager

ws_manager = WebSocketManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Endpoint WebSocket principal"""
    await ws_manager.connect(websocket)
    
    # Envoyer état initial
    status_data = app_state.copy()
    if status_data.get('active_position') and hasattr(status_data['active_position'], 'to_dict'):
        status_data['active_position'] = status_data['active_position'].to_dict()
    
    await ws_manager.send_personal_message({
        'type': 'event',
        'event': 'status',
        'data': status_data
    }, websocket)
    
    # Envoyer les derniers logs
    for log_entry in app_state['logs'][-50:]:
        await ws_manager.send_personal_message({
            'type': 'event',
            'event': 'log',
            'data': log_entry
        }, websocket)
    
    try:
        while True:
            # Recevoir message du client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Traiter selon le type
            msg_type = message.get('type')
            
            if msg_type == 'command':
                # Exécuter commande
                command = message.get('command')
                params = message.get('params', {})
                command_id = message.get('id')
                
                try:
                    result = await handle_client_command(command, params)
                    await ws_manager.send_personal_message({
                        'type': 'command_response',
                        'id': command_id,
                        'command': command,
                        'result': result,
                        'status': 'success'
                    }, websocket)
                except Exception as e:
                    await ws_manager.send_personal_message({
                        'type': 'command_error',
                        'id': command_id,
                        'command': command,
                        'error': str(e)
                    }, websocket)
            
            elif msg_type == 'ping':
                # Heartbeat
                await ws_manager.send_personal_message({
                    'type': 'pong',
                    'timestamp': time.time()
                }, websocket)
            
            elif msg_type == 'subscribe':
                # S'abonner à un canal
                channel = message.get('channel', 'all')
                # Implémenter rooms si nécessaire
                await ws_manager.send_personal_message({
                    'type': 'subscribed',
                    'channel': channel
                }, websocket)
            
            elif msg_type == 'request_logs':
                # Envoyer logs
                await ws_manager.send_personal_message({
                    'type': 'event',
                    'event': 'logs',
                    'data': app_state['logs'][-100:]
                }, websocket)
    
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Erreur WebSocket: {e}")
        await ws_manager.disconnect(websocket)

# Modifier la fonction add_log
async def add_log(level, message, detail=''):
    """Ajouter un log et envoyer via WebSocket natif"""
    from datetime import datetime
    
    entry = {
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'level': level,
        'message': message,
        'detail': detail
    }
    app_state['logs'].append(entry)
    
    # Garder seulement les 1000 derniers logs
    if len(app_state['logs']) > 1000:
        app_state['logs'] = app_state['logs'][-1000:]
    
    # Envoyer via WebSocket natif
    await ws_manager.emit('log', entry)
    logger.info(f"[{entry['timestamp']}] {entry['level']}: {entry['message']}")

# Modifier le main pour utiliser app au lieu de socketio_app
if __name__ == '__main__':
    import uvicorn
    
    load_trade_history()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    
    # Utiliser app directement (WebSocket intégré)
    uvicorn.run(app, host='0.0.0.0', port=port, log_level="info")
```

### 2. Remplacer tous les `sio.emit()`

```python
# AVANT
await sio.emit('position_update', update_data)
await sio.emit('position_opened', position.to_dict())
await sio.emit('position_closed', result)
await sio.emit('top_pairs_update', {'pairs': top_pairs})

# APRÈS
await ws_manager.emit('position_update', update_data)
await ws_manager.emit('position_opened', position.to_dict())
await ws_manager.emit('position_closed', result)
await ws_manager.emit('top_pairs_update', {'pairs': top_pairs})
```

### 3. Améliorer `core/websocket_manager.py`

```python
# Ajouter support rooms/namespaces
class WebSocketManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.connection_data: Dict[WebSocket, dict] = {}
        self.rooms: Dict[str, Set[WebSocket]] = {}  # Nouveau
        self._lock = asyncio.Lock()
    
    def subscribe(self, websocket: WebSocket, room: str):
        """S'abonner à une room"""
        if room not in self.rooms:
            self.rooms[room] = set()
        self.rooms[room].add(websocket)
    
    def unsubscribe(self, websocket: WebSocket, room: str):
        """Se désabonner d'une room"""
        if room in self.rooms:
            self.rooms[room].discard(websocket)
    
    async def emit_to_room(self, event: str, data: any, room: str):
        """Émettre vers une room spécifique"""
        if room not in self.rooms:
            return
        
        message = {
            'type': 'event',
            'event': event,
            'data': data,
            'timestamp': datetime.now().isoformat()
        }
        message_json = json.dumps(message)
        
        for connection in list(self.rooms[room]):
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.warning(f"Erreur emit room: {e}")
                await self.disconnect(connection)
```

## 🎨 Frontend - Migration Complète

### 1. Remplacer Socket.IO dans `templates/index.html`

```javascript
// AVANT
<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
<script>
    socket = io(API_BASE_URL);
    socket.on('connect', function() { ... });
    socket.on('log', function(logEntry) { ... });
</script>

// APRÈS
<script>
// Classe NativeWebSocketManager (voir code complet ci-dessous)
const ws = new NativeWebSocketManager(API_BASE_URL);
ws.connect();

ws.on('connect', () => {
    console.log('✅ WebSocket connecté');
});

ws.on('log', (logEntry) => {
    var level = logEntry.level || 'INFO';
    var message = logEntry.message || '';
    var detail = logEntry.detail || '';
    var timestamp = logEntry.timestamp || '';
    
    // Filtrer uniquement les logs de décision de trade
    var tradeKeywords = ['Setup trouvé', 'Position ouverte', 'Position fermée'];
    var isTradeLog = tradeKeywords.some(keyword => 
        message.indexOf(keyword) !== -1 || detail.indexOf(keyword) !== -1
    );
    
    if (isTradeLog) {
        debugLog('📡 ' + level, message + (detail ? ' - ' + detail : ''));
    }
});
</script>
```

### 2. Classe JavaScript Complète

```javascript
class NativeWebSocketManager {
    constructor(url) {
        // Convertir http:// en ws:// ou https:// en wss://
        this.url = url.replace(/^http/, 'ws') + '/ws';
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000;
        this.messageQueue = [];
        this.commandCallbacks = new Map();
        this.commandIdCounter = 0;
        this.eventHandlers = new Map();
        this.isReconnecting = false;
        this.lastPing = Date.now();
        this.pingInterval = null;
        this.reconnectTimeout = null;
        this.rooms = new Set();
    }
    
    connect() {
        try {
            console.log('🔄 Connexion WebSocket:', this.url);
            this.ws = new WebSocket(this.url);
            this.setupEventHandlers();
            this.startHeartbeat();
        } catch (error) {
            console.error('❌ Erreur connexion WebSocket:', error);
            this.scheduleReconnect();
        }
    }
    
    setupEventHandlers() {
        this.ws.onopen = () => {
            console.log('✅ WebSocket connecté');
            this.reconnectAttempts = 0;
            this.isReconnecting = false;
            this.lastPing = Date.now();
            
            // Envoyer messages en queue
            this.flushMessageQueue();
            
            // S'abonner par défaut
            this.subscribe('all');
        };
        
        this.ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                this.handleMessage(message);
            } catch (error) {
                console.error('❌ Erreur parsing message:', error, event.data);
            }
        };
        
        this.ws.onerror = (error) => {
            console.error('❌ Erreur WebSocket:', error);
        };
        
        this.ws.onclose = (event) => {
            console.warn('❌ WebSocket fermé:', event.code, event.reason);
            if (event.code !== 1000) {  // Pas une fermeture normale
                this.scheduleReconnect();
            }
        };
    }
    
    handleMessage(message) {
        const type = message.type;
        
        // Heartbeat
        if (type === 'ping') {
            this.lastPing = Date.now();
            this.send({ type: 'pong', timestamp: Date.now() });
            return;
        }
        
        if (type === 'pong') {
            this.lastPing = Date.now();
            const latency = Date.now() - (message.timestamp || Date.now());
            console.debug(`📡 Latence: ${latency}ms`);
            return;
        }
        
        // Réponses aux commandes
        if (type === 'command_response') {
            const callback = this.commandCallbacks.get(message.id);
            if (callback) {
                callback.resolve(message);
                this.commandCallbacks.delete(message.id);
            }
            return;
        }
        
        if (type === 'command_error') {
            const callback = this.commandCallbacks.get(message.id);
            if (callback) {
                callback.reject(new Error(message.error));
                this.commandCallbacks.delete(message.id);
            }
            return;
        }
        
        // Événements
        if (type === 'event') {
            const event = message.event;
            const handlers = this.eventHandlers.get(event) || [];
            handlers.forEach(handler => {
                try {
                    handler(message.data);
                } catch (error) {
                    console.error(`Erreur handler ${event}:`, error);
                }
            });
            return;
        }
        
        // Messages directs (compatibilité)
        const handlers = this.eventHandlers.get(type) || [];
        handlers.forEach(handler => {
            try {
                handler(message);
            } catch (error) {
                console.error(`Erreur handler ${type}:`, error);
            }
        });
    }
    
    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            try {
                this.ws.send(JSON.stringify(data));
            } catch (error) {
                console.error('❌ Erreur envoi message:', error);
                this.messageQueue.push(data);
            }
        } else {
            // Mettre en queue si déconnecté
            this.messageQueue.push(data);
            console.warn('⚠️ Message mis en queue (déconnecté):', data.type);
        }
    }
    
    sendCommand(command, params = {}) {
        return new Promise((resolve, reject) => {
            if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
                this.messageQueue.push({ command, params, resolve, reject });
                reject(new Error('WebSocket non connecté'));
                return;
            }
            
            const commandId = ++this.commandIdCounter;
            const timeout = setTimeout(() => {
                this.commandCallbacks.delete(commandId);
                reject(new Error('Timeout commande'));
            }, 5000);
            
            this.commandCallbacks.set(commandId, {
                resolve: (data) => {
                    clearTimeout(timeout);
                    resolve(data);
                },
                reject: (error) => {
                    clearTimeout(timeout);
                    reject(error);
                }
            });
            
            this.send({
                type: 'command',
                id: commandId,
                command: command,
                params: params,
                timestamp: Date.now()
            });
        });
    }
    
    on(event, handler) {
        if (!this.eventHandlers.has(event)) {
            this.eventHandlers.set(event, []);
        }
        this.eventHandlers.get(event).push(handler);
    }
    
    off(event, handler) {
        const handlers = this.eventHandlers.get(event);
        if (handlers) {
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }
    
    emit(event, data) {
        // Compatibilité avec API Socket.IO
        this.send({
            type: 'event',
            event: event,
            data: data,
            timestamp: Date.now()
        });
    }
    
    subscribe(channel) {
        this.rooms.add(channel);
        this.send({ type: 'subscribe', channel: channel });
    }
    
    unsubscribe(channel) {
        this.rooms.delete(channel);
        this.send({ type: 'unsubscribe', channel: channel });
    }
    
    flushMessageQueue() {
        while (this.messageQueue.length > 0) {
            const item = this.messageQueue.shift();
            if (item.command) {
                // C'est une commande
                this.sendCommand(item.command, item.params)
                    .then(item.resolve)
                    .catch(item.reject);
            } else {
                // C'est un message simple
                this.send(item);
            }
        }
    }
    
    scheduleReconnect() {
        if (this.isReconnecting) return;
        
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('❌ Échec reconnexion après', this.maxReconnectAttempts, 'tentatives');
            this.isReconnecting = false;
            return;
        }
        
        this.isReconnecting = true;
        this.reconnectAttempts++;
        const delay = Math.min(
            this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
            30000
        );
        
        console.log(`🔄 Reconnexion dans ${delay}ms (tentative ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        
        this.reconnectTimeout = setTimeout(() => {
            this.connect();
        }, delay);
    }
    
    startHeartbeat() {
        // Vérifier connexion toutes les 10 secondes
        setInterval(() => {
            if (Date.now() - this.lastPing > 60000) {
                console.warn('⚠️ Pas de ping depuis 60s, reconnexion...');
                if (this.ws) {
                    this.ws.close();
                    this.connect();
                }
            }
        }, 10000);
        
        // Envoyer ping toutes les 30 secondes
        this.pingInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.send({ type: 'ping', timestamp: Date.now() });
            }
        }, 30000);
    }
    
    disconnect() {
        if (this.reconnectTimeout) {
            clearTimeout(this.reconnectTimeout);
        }
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
        }
        if (this.ws) {
            this.ws.close(1000, 'Déconnexion normale');
        }
    }
}

// Utilisation globale (remplace socket)
let ws = null;

function initWebSocket() {
    ws = new NativeWebSocketManager(API_BASE_URL);
    ws.connect();
    
    // Écouter les événements (compatible avec Socket.IO)
    ws.on('status', (status) => {
        if (status.is_scanning !== undefined) {
            isScanning = status.is_scanning;
            updateStateDisplay();
        }
    });
    
    ws.on('log', (logEntry) => {
        // ... code existant ...
    });
    
    ws.on('position_update', (update) => {
        // ... code existant ...
    });
    
    ws.on('position_opened', (position) => {
        // ... code existant ...
    });
    
    ws.on('position_closed', (result) => {
        // ... code existant ...
    });
    
    ws.on('top_pairs_update', (data) => {
        // ... code existant ...
    });
    
    // ... autres événements ...
}

// Utiliser ws.sendCommand() au lieu de fetch() pour certaines actions
async function startScanner() {
    try {
        await ws.sendCommand('start_scanner');
        console.log('✅ Scanner démarré');
    } catch (error) {
        console.error('❌ Erreur démarrage scanner:', error);
    }
}
```

## 🔄 Migration Progressive (Optionnel)

Si vous voulez migrer progressivement, garder les deux en parallèle :

```python
# main.py - Support hybride
@app.websocket("/ws")  # WebSocket natif
async def websocket_native(websocket: WebSocket):
    # ... code WebSocket natif ...

# Garder Socket.IO temporairement
@app.websocket("/socket.io")  # Socket.IO (déprécié)
async def websocket_socketio(websocket: WebSocket):
    # ... code Socket.IO ...
```

```javascript
// Frontend - Détecter support et choisir
function initWebSocket() {
    if (window.WebSocket) {
        // Utiliser WebSocket natif
        ws = new NativeWebSocketManager(API_BASE_URL);
    } else {
        // Fallback Socket.IO
        socket = io(API_BASE_URL);
    }
}
```

## ✅ Checklist de Migration

### Backend
- [ ] Créer endpoint `/ws` dans FastAPI
- [ ] Remplacer `sio.emit()` par `ws_manager.emit()`
- [ ] Migrer handlers `@sio.on()` vers endpoint WebSocket
- [ ] Tester tous les événements
- [ ] Supprimer `python-socketio` des requirements

### Frontend
- [ ] Créer classe `NativeWebSocketManager`
- [ ] Remplacer `socket = io()` par `ws = new NativeWebSocketManager()`
- [ ] Migrer tous les `socket.on()` vers `ws.on()`
- [ ] Migrer tous les `socket.emit()` vers `ws.sendCommand()`
- [ ] Tester reconnexion automatique
- [ ] Supprimer `<script src="socket.io.js">` du HTML

### Tests
- [ ] Test connexion/déconnexion
- [ ] Test reconnexion automatique
- [ ] Test tous les événements
- [ ] Test commandes bidirectionnelles
- [ ] Test performance (latence)
- [ ] Test avec plusieurs clients

