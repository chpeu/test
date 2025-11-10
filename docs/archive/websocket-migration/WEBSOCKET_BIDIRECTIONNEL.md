# Communication Bidirectionnelle WebSocket Natif

## ✅ Oui, c'est totalement possible !

WebSocket natif supporte **parfaitement** la communication bidirectionnelle. C'est même **plus simple** qu'avec Socket.IO car le protocole est standard.

## 🔄 Architecture Bidirectionnelle

```
Frontend                    Backend
   │                          │
   │  ──── connect ────────>  │
   │ <─── status ───────────  │
   │                          │
   │  ──── command ────────>  │
   │ <─── response ─────────  │
   │                          │
   │ <─── event ────────────  │
   │                          │
   │  ──── ping ───────────>  │
   │ <─── pong ─────────────  │
```

## 🔧 Backend - Réception et Envoi

### Endpoint WebSocket avec Gestion Bidirectionnelle

```python
# main.py
from fastapi import WebSocket, WebSocketDisconnect
from core.websocket_manager import WebSocketManager
import json
import time
import logging

logger = logging.getLogger(__name__)
ws_manager = WebSocketManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Endpoint WebSocket bidirectionnel"""
    await ws_manager.connect(websocket)
    
    # 🔥 ENVOI INITIAL : Envoyer état au client
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
        # 🔥 BOUCLE BIDIRECTIONNELLE : Recevoir et traiter messages
        while True:
            # ⬇️ RÉCEPTION : Recevoir message du client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            msg_type = message.get('type')
            
            # 🔥 TRAITEMENT COMMANDES (Frontend → Backend)
            if msg_type == 'command':
                command = message.get('command')
                params = message.get('params', {})
                command_id = message.get('id')
                
                logger.info(f"📨 Commande reçue: {command} (ID: {command_id})")
                
                try:
                    # Exécuter la commande
                    result = await handle_client_command(command, params)
                    
                    # ⬆️ ENVOI : Envoyer réponse au client
                    await ws_manager.send_personal_message({
                        'type': 'command_response',
                        'id': command_id,
                        'command': command,
                        'result': result,
                        'status': 'success',
                        'timestamp': time.time()
                    }, websocket)
                    
                except Exception as e:
                    logger.error(f"Erreur commande {command}: {e}")
                    # ⬆️ ENVOI : Envoyer erreur au client
                    await ws_manager.send_personal_message({
                        'type': 'command_error',
                        'id': command_id,
                        'command': command,
                        'error': str(e),
                        'timestamp': time.time()
                    }, websocket)
            
            # 🔥 HEARTBEAT (Frontend ↔ Backend)
            elif msg_type == 'ping':
                # ⬆️ ENVOI : Répondre au ping
                await ws_manager.send_personal_message({
                    'type': 'pong',
                    'timestamp': time.time()
                }, websocket)
            
            # 🔥 SUBSCRIPTION (Frontend → Backend)
            elif msg_type == 'subscribe':
                channel = message.get('channel', 'all')
                ws_manager.subscribe(websocket, channel)
                # ⬆️ ENVOI : Confirmer subscription
                await ws_manager.send_personal_message({
                    'type': 'subscribed',
                    'channel': channel,
                    'timestamp': time.time()
                }, websocket)
            
            # 🔥 UNSUBSCRIBE (Frontend → Backend)
            elif msg_type == 'unsubscribe':
                channel = message.get('channel', 'all')
                ws_manager.unsubscribe(websocket, channel)
                # ⬆️ ENVOI : Confirmer unsubscription
                await ws_manager.send_personal_message({
                    'type': 'unsubscribed',
                    'channel': channel,
                    'timestamp': time.time()
                }, websocket)
            
            # 🔥 REQUEST (Frontend → Backend)
            elif msg_type == 'request':
                request_type = message.get('request_type')
                request_id = message.get('id')
                
                if request_type == 'logs':
                    # ⬆️ ENVOI : Envoyer logs
                    await ws_manager.send_personal_message({
                        'type': 'request_response',
                        'id': request_id,
                        'request_type': request_type,
                        'data': app_state['logs'][-100:]
                    }, websocket)
                
                elif request_type == 'position':
                    # ⬆️ ENVOI : Envoyer position active
                    if position_manager and position_manager.active_position:
                        await ws_manager.send_personal_message({
                            'type': 'request_response',
                            'id': request_id,
                            'request_type': request_type,
                            'data': position_manager.active_position.to_dict()
                        }, websocket)
                    else:
                        await ws_manager.send_personal_message({
                            'type': 'request_response',
                            'id': request_id,
                            'request_type': request_type,
                            'data': None
                        }, websocket)
    
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Erreur WebSocket: {e}")
        await ws_manager.disconnect(websocket)


# 🔥 FONCTION : Traiter commandes du client
async def handle_client_command(command: str, params: dict):
    """Exécuter une commande du client"""
    
    if command == 'start_scanner':
        await api_start()
        return {'status': 'started', 'is_scanning': True}
    
    elif command == 'stop_scanner':
        await api_stop()
        return {'status': 'stopped', 'is_scanning': False}
    
    elif command == 'update_config':
        from config import TRADING_CONFIG
        updated = {}
        for key, value in params.items():
            if key in TRADING_CONFIG:
                TRADING_CONFIG[key] = value
                updated[key] = value
        
        if updated:
            logger.info(f"✅ Config mise à jour: {updated}")
            await add_log('INFO', 'Config mise à jour', str(updated))
        
        return {'updated': updated}
    
    elif command == 'open_position':
        # Ouvrir position manuellement
        symbol = params.get('symbol')
        direction = params.get('direction')
        entry = params.get('entry')
        
        if not all([symbol, direction, entry]):
            raise ValueError('Paramètres manquants: symbol, direction, entry')
        
        # Ouvrir position
        result = await api_open_position(symbol, direction, entry)
        return {'position': result}
    
    elif command == 'close_position':
        # Fermer position active
        if position_manager and position_manager.active_position:
            result = await api_close_position()
            return {'status': 'closed', 'result': result}
        else:
            raise ValueError('Aucune position active')
    
    elif command == 'get_status':
        # Obtenir état complet
        status_data = app_state.copy()
        if status_data.get('active_position') and hasattr(status_data['active_position'], 'to_dict'):
            status_data['active_position'] = status_data['active_position'].to_dict()
        return status_data
    
    else:
        raise ValueError(f'Commande inconnue: {command}')


# 🔥 ENVOI AUTOMATIQUE : Émettre événements (Backend → Frontend)
async def add_log(level, message, detail=''):
    """Ajouter un log et envoyer via WebSocket"""
    from datetime import datetime
    
    entry = {
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'level': level,
        'message': message,
        'detail': detail
    }
    app_state['logs'].append(entry)
    
    if len(app_state['logs']) > 1000:
        app_state['logs'] = app_state['logs'][-1000:]
    
    # ⬆️ ENVOI : Diffuser à tous les clients
    await ws_manager.emit('log', entry)
    logger.info(f"[{entry['timestamp']}] {entry['level']}: {entry['message']}")


# 🔥 EXEMPLE : Émettre événement position (Backend → Frontend)
async def emit_position_update(position_data: dict):
    """Émettre mise à jour position à tous les clients"""
    await ws_manager.emit('position_update', position_data)


# 🔥 EXEMPLE : Émettre événement scan (Backend → Frontend)
async def emit_scan_completed(pairs: list):
    """Émettre scan terminé à tous les clients"""
    await ws_manager.emit('top_pairs_update', {'pairs': pairs})
```

## 🎨 Frontend - Envoi et Réception

### Classe JavaScript Bidirectionnelle Complète

```javascript
class BidirectionalWebSocket {
    constructor(url) {
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
    }
    
    connect() {
        try {
            console.log('🔄 Connexion WebSocket:', this.url);
            this.ws = new WebSocket(this.url);
            this.setupEventHandlers();
            this.startHeartbeat();
        } catch (error) {
            console.error('❌ Erreur connexion:', error);
            this.scheduleReconnect();
        }
    }
    
    setupEventHandlers() {
        // ⬆️ RÉCEPTION : Message reçu du serveur
        this.ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                this.handleMessage(message);
            } catch (error) {
                console.error('❌ Erreur parsing:', error);
            }
        };
        
        this.ws.onopen = () => {
            console.log('✅ WebSocket connecté');
            this.reconnectAttempts = 0;
            this.isReconnecting = false;
            this.lastPing = Date.now();
            this.flushMessageQueue();
            this.subscribe('all');
        };
        
        this.ws.onerror = (error) => {
            console.error('❌ Erreur WebSocket:', error);
        };
        
        this.ws.onclose = (event) => {
            console.warn('❌ WebSocket fermé:', event.code);
            if (event.code !== 1000) {
                this.scheduleReconnect();
            }
        };
    }
    
    handleMessage(message) {
        const type = message.type;
        
        // 🔥 HEARTBEAT (Backend → Frontend)
        if (type === 'ping') {
            this.lastPing = Date.now();
            // ⬇️ ENVOI : Répondre au ping
            this.send({ type: 'pong', timestamp: Date.now() });
            return;
        }
        
        if (type === 'pong') {
            this.lastPing = Date.now();
            const latency = Date.now() - (message.timestamp || Date.now());
            console.debug(`📡 Latence: ${latency}ms`);
            return;
        }
        
        // 🔥 RÉPONSE COMMANDE (Backend → Frontend)
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
        
        // 🔥 ÉVÉNEMENTS (Backend → Frontend)
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
        
        // 🔥 RÉPONSE REQUEST (Backend → Frontend)
        if (type === 'request_response') {
            const callback = this.commandCallbacks.get(message.id);
            if (callback) {
                callback.resolve(message.data);
                this.commandCallbacks.delete(message.id);
            }
            return;
        }
    }
    
    // ⬇️ ENVOI : Envoyer message au serveur
    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            try {
                this.ws.send(JSON.stringify(data));
            } catch (error) {
                console.error('❌ Erreur envoi:', error);
                this.messageQueue.push(data);
            }
        } else {
            this.messageQueue.push(data);
            console.warn('⚠️ Message en queue:', data.type);
        }
    }
    
    // 🔥 ENVOI COMMANDE (Frontend → Backend)
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
            
            // ⬇️ ENVOI : Envoyer commande au serveur
            this.send({
                type: 'command',
                id: commandId,
                command: command,
                params: params,
                timestamp: Date.now()
            });
        });
    }
    
    // 🔥 ENVOI REQUEST (Frontend → Backend)
    sendRequest(requestType, params = {}) {
        return new Promise((resolve, reject) => {
            if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
                reject(new Error('WebSocket non connecté'));
                return;
            }
            
            const requestId = ++this.commandIdCounter;
            const timeout = setTimeout(() => {
                this.commandCallbacks.delete(requestId);
                reject(new Error('Timeout request'));
            }, 5000);
            
            this.commandCallbacks.set(requestId, {
                resolve: (data) => {
                    clearTimeout(timeout);
                    resolve(data);
                },
                reject: (error) => {
                    clearTimeout(timeout);
                    reject(error);
                }
            });
            
            // ⬇️ ENVOI : Envoyer request au serveur
            this.send({
                type: 'request',
                id: requestId,
                request_type: requestType,
                params: params,
                timestamp: Date.now()
            });
        });
    }
    
    // 🔥 ÉCOUTER ÉVÉNEMENTS (Backend → Frontend)
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
    
    // 🔥 ENVOI ÉVÉNEMENT (Frontend → Backend) - Optionnel
    emit(event, data) {
        this.send({
            type: 'event',
            event: event,
            data: data,
            timestamp: Date.now()
        });
    }
    
    flushMessageQueue() {
        while (this.messageQueue.length > 0) {
            const item = this.messageQueue.shift();
            if (item.command) {
                this.sendCommand(item.command, item.params)
                    .then(item.resolve)
                    .catch(item.reject);
            } else {
                this.send(item);
            }
        }
    }
    
    scheduleReconnect() {
        if (this.isReconnecting) return;
        
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('❌ Échec reconnexion');
            this.isReconnecting = false;
            return;
        }
        
        this.isReconnecting = true;
        this.reconnectAttempts++;
        const delay = Math.min(
            this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
            30000
        );
        
        console.log(`🔄 Reconnexion dans ${delay}ms`);
        
        this.reconnectTimeout = setTimeout(() => {
            this.connect();
        }, delay);
    }
    
    startHeartbeat() {
        // Vérifier connexion
        setInterval(() => {
            if (Date.now() - this.lastPing > 60000) {
                console.warn('⚠️ Pas de ping depuis 60s');
                if (this.ws) {
                    this.ws.close();
                    this.connect();
                }
            }
        }, 10000);
        
        // ⬇️ ENVOI : Envoyer ping toutes les 30s
        this.pingInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.send({ type: 'ping', timestamp: Date.now() });
            }
        }, 30000);
    }
    
    disconnect() {
        if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout);
        if (this.pingInterval) clearInterval(this.pingInterval);
        if (this.ws) this.ws.close(1000, 'Déconnexion normale');
    }
}

// 🔥 UTILISATION
const ws = new BidirectionalWebSocket(API_BASE_URL);
ws.connect();

// ⬆️ RÉCEPTION : Écouter événements du serveur
ws.on('status', (status) => {
    console.log('📊 Status:', status);
    if (status.is_scanning !== undefined) {
        isScanning = status.is_scanning;
        updateStateDisplay();
    }
});

ws.on('log', (logEntry) => {
    console.log('📝 Log:', logEntry);
    displayLog(logEntry);
});

ws.on('position_update', (update) => {
    console.log('📈 Position update:', update);
    updatePositionUI(update);
});

ws.on('position_opened', (position) => {
    console.log('🟢 Position ouverte:', position);
    handlePositionOpened(position);
});

ws.on('position_closed', (result) => {
    console.log('🔴 Position fermée:', result);
    handlePositionClosed(result);
});

ws.on('top_pairs_update', (data) => {
    console.log('📊 Top pairs:', data.pairs);
    displayTopPairs(data.pairs);
});

// ⬇️ ENVOI : Envoyer commandes au serveur
async function startScanner() {
    try {
        const result = await ws.sendCommand('start_scanner');
        console.log('✅ Scanner démarré:', result);
        showSuccess('Scanner démarré');
    } catch (error) {
        console.error('❌ Erreur:', error);
        showError('Erreur démarrage: ' + error.message);
    }
}

async function stopScanner() {
    try {
        const result = await ws.sendCommand('stop_scanner');
        console.log('✅ Scanner arrêté:', result);
        showSuccess('Scanner arrêté');
    } catch (error) {
        console.error('❌ Erreur:', error);
        showError('Erreur arrêt: ' + error.message);
    }
}

async function updateConfig(config) {
    try {
        const result = await ws.sendCommand('update_config', config);
        console.log('✅ Config mise à jour:', result.updated);
        showSuccess('Configuration mise à jour');
    } catch (error) {
        console.error('❌ Erreur:', error);
        showError('Erreur config: ' + error.message);
    }
}

async function openPosition(symbol, direction, entry) {
    try {
        const result = await ws.sendCommand('open_position', {
            symbol: symbol,
            direction: direction,
            entry: entry
        });
        console.log('✅ Position ouverte:', result);
        showSuccess('Position ouverte: ' + symbol);
    } catch (error) {
        console.error('❌ Erreur:', error);
        showError('Erreur ouverture: ' + error.message);
    }
}

async function closePosition() {
    try {
        const result = await ws.sendCommand('close_position');
        console.log('✅ Position fermée:', result);
        showSuccess('Position fermée');
    } catch (error) {
        console.error('❌ Erreur:', error);
        showError('Erreur fermeture: ' + error.message);
    }
}

// ⬇️ ENVOI : Demander des données
async function getStatus() {
    try {
        const status = await ws.sendCommand('get_status');
        console.log('📊 Status:', status);
        updateUI(status);
    } catch (error) {
        console.error('❌ Erreur:', error);
    }
}

async function getLogs() {
    try {
        const logs = await ws.sendRequest('logs');
        console.log('📝 Logs:', logs);
        displayLogs(logs);
    } catch (error) {
        console.error('❌ Erreur:', error);
    }
}

async function getPosition() {
    try {
        const position = await ws.sendRequest('position');
        console.log('📈 Position:', position);
        if (position) {
            displayPosition(position);
        }
    } catch (error) {
        console.error('❌ Erreur:', error);
    }
}
```

## 📊 Flux de Communication

### Exemple : Démarrer le Scanner

```
Frontend                          Backend
   │                                │
   │  sendCommand('start_scanner')  │
   │  ───────────────────────────>  │
   │                                │  handle_client_command()
   │                                │  api_start()
   │                                │  ──┐
   │                                │    │ Scanner démarre
   │                                │  <─┘
   │  <───────────────────────────  │
   │  command_response              │
   │  {status: 'started'}           │
   │                                │
   │  <───────────────────────────  │
   │  event: 'status'               │  emit('status', {...})
   │  {is_scanning: true}          │
   │                                │
   │  <───────────────────────────  │
   │  event: 'log'                  │  emit('log', {...})
   │  {message: 'Scanner démarré'}  │
```

### Exemple : Mise à Jour Position

```
Frontend                          Backend
   │                                │
   │                                │  Position check loop
   │                                │  ──┐
   │                                │    │ Prix change
   │                                │  <─┘
   │                                │
   │  <───────────────────────────  │
   │  event: 'position_update'      │  emit('position_update', {...})
   │  {current_price: 1.2345}      │
   │                                │
   │  updatePositionUI()            │
   │  ──┐                           │
   │  <─┘                           │
```

## ✅ Avantages Communication Bidirectionnelle

1. **Latence minimale** : Pas de requête HTTP, communication directe
2. **Temps réel** : Mises à jour instantanées
3. **Efficacité** : Une connexion pour tout
4. **Simplicité** : API claire et standard
5. **Fiabilité** : Reconnexion automatique

## 🎯 Résumé

**OUI, la communication bidirectionnelle est parfaitement possible !**

- ✅ **Frontend → Backend** : `sendCommand()`, `sendRequest()`, `send()`
- ✅ **Backend → Frontend** : `emit()`, `send_personal_message()`, `broadcast()`
- ✅ **Heartbeat** : Ping/Pong automatique
- ✅ **Reconnexion** : Automatique avec queue
- ✅ **Performance** : Latence < 10ms

