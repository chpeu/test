# Améliorations WebSocket - Implémentation

## 🎯 Objectif
Transformer la communication WebSocket unidirectionnelle en communication bidirectionnelle robuste avec reconnexion automatique, gestion d'erreurs et optimisation.

## 📝 Résumé de l'Architecture Actuelle

### Backend (SocketIO)
- **Serveur** : `socketio.AsyncServer` avec mode ASGI
- **Handlers** : `connect`, `disconnect`, `request_logs` (unidirectionnel)
- **Émissions** : `status`, `log`, `position_update`, `position_opened`, `position_closed`, `top_pairs_update`, etc.

### Frontend (Socket.IO Client)
- **Connexion** : `socket = io(API_BASE_URL)`
- **Écouteurs** : Tous les événements émis par le backend
- **Problème** : Pas d'envoi de commandes au backend

## 🔧 Implémentations Concrètes

### 1. Handlers Backend pour Communication Bidirectionnelle

```python
# À ajouter dans main.py après les handlers existants

@sio.on('client_command')
async def handle_client_command(sid, data):
    """Recevoir et exécuter commandes du client"""
    try:
        command = data.get('command')
        params = data.get('params', {})
        command_id = data.get('id')  # ID pour tracking
        
        logger.info(f"📨 Commande reçue: {command} (ID: {command_id})")
        
        result = None
        error = None
        
        if command == 'start_scanner':
            await api_start()
            result = {'status': 'started', 'is_scanning': True}
        
        elif command == 'stop_scanner':
            await api_stop()
            result = {'status': 'stopped', 'is_scanning': False}
        
        elif command == 'update_config':
            from config import TRADING_CONFIG
            updated = {}
            for key, value in params.items():
                if key in TRADING_CONFIG:
                    TRADING_CONFIG[key] = value
                    updated[key] = value
            
            if updated:
                logger.info(f"✅ Config mise à jour: {updated}")
                result = {'updated': updated}
        
        elif command == 'request_position':
            if position_manager and position_manager.active_position:
                result = {'position': position_manager.active_position.to_dict()}
            else:
                result = {'position': None}
        
        elif command == 'close_position':
            if position_manager and position_manager.active_position:
                await api_close_position()
                result = {'status': 'closed'}
            else:
                error = 'Aucune position active'
        
        else:
            error = f'Commande inconnue: {command}'
        
        # Envoyer réponse
        if error:
            await sio.emit('command_error', {
                'id': command_id,
                'command': command,
                'error': error
            }, room=sid)
        else:
            await sio.emit('command_ack', {
                'id': command_id,
                'command': command,
                'result': result,
                'status': 'success'
            }, room=sid)
            
    except Exception as e:
        logger.error(f"Erreur commande client: {e}")
        await sio.emit('command_error', {
            'id': data.get('id'),
            'command': data.get('command'),
            'error': str(e)
        }, room=sid)

@sio.on('ping')
async def handle_ping(sid, data=None):
    """Répondre au ping client (heartbeat)"""
    await sio.emit('pong', {
        'timestamp': time.time(),
        'server_time': datetime.now().isoformat()
    }, room=sid)

@sio.on('subscribe')
async def handle_subscribe(sid, data):
    """Client s'abonne à un canal spécifique"""
    channel = data.get('channel', 'all')
    await sio.enter_room(sid, channel)
    logger.info(f"📡 Client {sid} abonné à {channel}")
    await sio.emit('subscribed', {
        'channel': channel,
        'timestamp': time.time()
    }, room=sid)

@sio.on('unsubscribe')
async def handle_unsubscribe(sid, data):
    """Client se désabonne d'un canal"""
    channel = data.get('channel', 'all')
    await sio.leave_room(sid, channel)
    logger.info(f"📡 Client {sid} désabonné de {channel}")
    await sio.emit('unsubscribed', {
        'channel': channel,
        'timestamp': time.time()
    }, room=sid)
```

### 2. Gestionnaire Frontend Amélioré

```javascript
// À ajouter dans templates/index.html

class WebSocketManager {
    constructor(url) {
        this.url = url;
        this.socket = null;
        this.messageQueue = [];
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000;
        this.isReconnecting = false;
        this.commandCallbacks = new Map(); // Pour tracking des commandes
        this.commandIdCounter = 0;
        this.lastPing = Date.now();
        this.pingInterval = null;
    }
    
    connect() {
        this.socket = io(this.url, {
            reconnection: true,
            reconnectionDelay: this.reconnectDelay,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: this.maxReconnectAttempts,
            timeout: 20000,
            transports: ['websocket', 'polling']
        });
        
        this.setupEventHandlers();
        this.startHeartbeat();
    }
    
    setupEventHandlers() {
        this.socket.on('connect', () => {
            console.log('✅ WebSocket connecté');
            this.reconnectAttempts = 0;
            this.isReconnecting = false;
            this.lastPing = Date.now();
            
            // Envoyer les messages en queue
            this.flushMessageQueue();
            
            // S'abonner aux canaux par défaut
            this.subscribe('all');
        });
        
        this.socket.on('disconnect', (reason) => {
            console.warn('❌ WebSocket déconnecté:', reason);
            if (reason === 'io server disconnect') {
                // Reconnexion forcée
                this.socket.connect();
            }
        });
        
        this.socket.on('reconnect_attempt', (attemptNumber) => {
            console.log(`🔄 Tentative reconnexion ${attemptNumber}/${this.maxReconnectAttempts}`);
            this.reconnectAttempts = attemptNumber;
            this.isReconnecting = true;
        });
        
        this.socket.on('reconnect_failed', () => {
            console.error('❌ Échec reconnexion après', this.maxReconnectAttempts, 'tentatives');
            this.isReconnecting = false;
        });
        
        // Heartbeat
        this.socket.on('ping', (data) => {
            this.lastPing = Date.now();
            this.socket.emit('pong', { timestamp: Date.now() });
        });
        
        this.socket.on('pong', (data) => {
            this.lastPing = Date.now();
            const latency = Date.now() - (data.timestamp || Date.now());
            console.debug(`📡 Latence: ${latency}ms`);
        });
        
        // Réponses aux commandes
        this.socket.on('command_ack', (data) => {
            const callback = this.commandCallbacks.get(data.id);
            if (callback) {
                callback.resolve(data);
                this.commandCallbacks.delete(data.id);
            }
        });
        
        this.socket.on('command_error', (data) => {
            const callback = this.commandCallbacks.get(data.id);
            if (callback) {
                callback.reject(new Error(data.error));
                this.commandCallbacks.delete(data.id);
            }
        });
    }
    
    startHeartbeat() {
        // Vérifier connexion toutes les 10 secondes
        setInterval(() => {
            if (Date.now() - this.lastPing > 60000) {
                console.warn('⚠️ Pas de ping depuis 60s, reconnexion...');
                if (this.socket) {
                    this.socket.disconnect();
                    this.socket.connect();
                }
            }
        }, 10000);
        
        // Envoyer ping toutes les 30 secondes
        this.pingInterval = setInterval(() => {
            if (this.socket && this.socket.connected) {
                this.socket.emit('ping', { timestamp: Date.now() });
            }
        }, 30000);
    }
    
    sendCommand(command, params = {}) {
        return new Promise((resolve, reject) => {
            if (!this.socket || !this.socket.connected) {
                // Mettre en queue si déconnecté
                this.messageQueue.push({ command, params, resolve, reject });
                reject(new Error('Socket non connecté - message mis en queue'));
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
            
            this.socket.emit('client_command', {
                id: commandId,
                command: command,
                params: params,
                timestamp: Date.now()
            });
        });
    }
    
    flushMessageQueue() {
        while (this.messageQueue.length > 0) {
            const { command, params, resolve, reject } = this.messageQueue.shift();
            this.sendCommand(command, params)
                .then(resolve)
                .catch(reject);
        }
    }
    
    subscribe(channel) {
        if (this.socket && this.socket.connected) {
            this.socket.emit('subscribe', { channel: channel });
        }
    }
    
    unsubscribe(channel) {
        if (this.socket && this.socket.connected) {
            this.socket.emit('unsubscribe', { channel: channel });
        }
    }
    
    disconnect() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
        }
        if (this.socket) {
            this.socket.disconnect();
        }
    }
}

// Utilisation globale
let wsManager = null;

function initWebSocketManager() {
    wsManager = new WebSocketManager(API_BASE_URL);
    wsManager.connect();
    
    // Utiliser wsManager.sendCommand() au lieu de fetch() pour certaines actions
}

// Exemples d'utilisation
async function startScannerViaWS() {
    try {
        const result = await wsManager.sendCommand('start_scanner');
        console.log('✅ Scanner démarré:', result);
        showSuccess('Scanner démarré');
    } catch (error) {
        console.error('❌ Erreur démarrage scanner:', error);
        showError('Erreur démarrage scanner: ' + error.message);
    }
}

async function updateConfigViaWS(config) {
    try {
        const result = await wsManager.sendCommand('update_config', config);
        console.log('✅ Config mise à jour:', result.updated);
        showSuccess('Configuration mise à jour');
    } catch (error) {
        console.error('❌ Erreur mise à jour config:', error);
        showError('Erreur mise à jour config: ' + error.message);
    }
}
```

### 3. Rooms/Namespaces pour Multi-Instances

```python
# Backend - Émettre vers des rooms spécifiques

# Dans init_instances() ou au démarrage
instance_room = f"instance_{port}"

# Émettre vers une room spécifique
await sio.emit('position_update', data, room=instance_room)

# Émettre vers toutes les instances sauf une
await sio.emit('admin_notification', data, skip_sid=sid)
```

### 4. Compression pour Gros Messages

```python
# Backend - Compression optionnelle

import gzip
import base64

async def emit_compressed(event, data, room=None):
    """Émettre avec compression si message > 1KB"""
    data_str = json.dumps(data)
    
    if len(data_str) > 1024:
        compressed = gzip.compress(data_str.encode())
        compressed_b64 = base64.b64encode(compressed).decode()
        
        await sio.emit(event, {
            'compressed': True,
            'data': compressed_b64
        }, room=room)
    else:
        await sio.emit(event, data, room=room)
```

```javascript
// Frontend - Décompression

socket.on('position_update', (data) => {
    if (data.compressed) {
        // Utiliser pako.js pour décompresser
        const decompressed = pako.inflate(atob(data.data), { to: 'string' });
        data = JSON.parse(decompressed);
    }
    // Traiter data normalement
    updatePositionUI(data);
});
```

## 🚀 Plan d'Implémentation Priorisé

### Phase 1 : Communication Bidirectionnelle (URGENT)
1. ✅ Ajouter handlers `client_command`, `ping`, `subscribe` dans `main.py`
2. ✅ Créer classe `WebSocketManager` dans `index.html`
3. ✅ Remplacer `fetch()` par `wsManager.sendCommand()` pour start/stop/config

### Phase 2 : Robustesse (HAUTE)
1. ✅ Implémenter reconnexion automatique avec queue
2. ✅ Ajouter heartbeat ping-pong
3. ✅ Gestion d'erreurs améliorée

### Phase 3 : Optimisation (MOYENNE)
1. ✅ Système de rooms pour multi-instances
2. ✅ Compression pour messages > 1KB
3. ✅ Validation avec Pydantic

### Phase 4 : Monitoring (BASSE)
1. ✅ Métriques WebSocket (connexions, latence)
2. ✅ Dashboard monitoring
3. ✅ Alertes sur déconnexions

## 📊 Bénéfices Attendus

- **Latence réduite** : < 50ms pour commandes (vs 100-200ms avec REST)
- **Fiabilité** : Reconnexion automatique, queue de messages
- **Scalabilité** : Rooms pour multi-instances
- **Performance** : Compression pour gros volumes
- **UX** : Feedback immédiat, pas de polling

