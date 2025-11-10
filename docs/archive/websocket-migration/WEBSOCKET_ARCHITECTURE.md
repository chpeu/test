# Architecture WebSocket - Trade Cursor

## 📊 État Actuel

### Backend (Python/FastAPI)

#### 1. **SocketIO Server** (`main.py`)
```python
sio = socketio.AsyncServer(cors_allowed_origins="*", async_mode='asgi')
socketio_app = socketio.ASGIApp(sio, app)
```

**Handlers actuels :**
- `@sio.on('connect')` - Connexion client
- `@sio.on('disconnect')` - Déconnexion client
- `@sio.on('request_logs')` - Demande de logs (unidirectionnel)

**Événements émis (Backend → Frontend) :**
- `status` - État global de l'application
- `log` - Nouveau log
- `position_update` - Mise à jour position active
- `position_opened` - Position ouverte
- `position_closed` - Position fermée
- `top_pairs_update` - Mise à jour des top pairs
- `volume_stats_update` - Statistiques de validation
- `scan_started` - Scan démarré
- `scan_completed` - Scan terminé
- `scan_error` - Erreur scan

### Frontend (JavaScript/Socket.IO Client)

**Connexion :**
```javascript
socket = io(API_BASE_URL);
```

**Écouteurs actuels :**
- `connect` / `disconnect` - Gestion connexion
- `log` - Affichage logs
- `status` - Mise à jour état
- `position_update` - Mise à jour position
- `position_opened` / `position_closed` - Événements position
- `top_pairs_update` - Mise à jour pairs
- `volume_validation_update` - Validation volume
- `volume_stats_update` - Stats validation
- `scan_completed` / `scan_error` - Événements scan

## ⚠️ Problèmes Identifiés

### 1. **Communication Unidirectionnelle**
- ❌ Le frontend ne peut pas envoyer de commandes via WebSocket
- ❌ Pas de confirmation de réception (acknowledgment)
- ❌ Pas de gestion d'erreurs bidirectionnelle

### 2. **Pas de Rooms/Namespaces**
- ❌ Tous les clients reçoivent tous les événements
- ❌ Pas de séparation par instance/session
- ❌ Pas de broadcast sélectif

### 3. **Pas de Reconnexion Automatique**
- ❌ Le frontend ne gère pas la reconnexion automatique
- ❌ Pas de queue de messages en cas de déconnexion

### 4. **Pas de Heartbeat/Ping-Pong**
- ❌ Pas de détection de connexion morte
- ❌ Pas de keep-alive automatique

### 5. **Pas de Compression**
- ❌ Messages JSON non compressés
- ❌ Pas d'optimisation pour gros volumes

## 🚀 Améliorations Proposées

### 1. **Communication Bidirectionnelle**

#### Backend - Ajouter Handlers Récepteurs

```python
# Dans main.py - Ajouter après les handlers existants

@sio.on('client_command')
async def handle_client_command(sid, data):
    """Recevoir commandes du client"""
    try:
        command = data.get('command')
        params = data.get('params', {})
        
        if command == 'start_scanner':
            await api_start()
            await sio.emit('command_ack', {
                'command': command,
                'status': 'success',
                'timestamp': time.time()
            }, room=sid)
        
        elif command == 'stop_scanner':
            await api_stop()
            await sio.emit('command_ack', {
                'command': command,
                'status': 'success',
                'timestamp': time.time()
            }, room=sid)
        
        elif command == 'update_config':
            # Mettre à jour config
            from config import TRADING_CONFIG
            for key, value in params.items():
                if key in TRADING_CONFIG:
                    TRADING_CONFIG[key] = value
            await sio.emit('command_ack', {
                'command': command,
                'status': 'success',
                'updated': params
            }, room=sid)
        
        elif command == 'request_position':
            # Envoyer position active
            if position_manager and position_manager.active_position:
                await sio.emit('position_data', {
                    'position': position_manager.active_position.to_dict()
                }, room=sid)
        
        else:
            await sio.emit('command_error', {
                'command': command,
                'error': f'Commande inconnue: {command}'
            }, room=sid)
            
    except Exception as e:
        logger.error(f"Erreur commande client: {e}")
        await sio.emit('command_error', {
            'command': data.get('command'),
            'error': str(e)
        }, room=sid)

@sio.on('ping')
async def handle_ping(sid):
    """Répondre au ping client (heartbeat)"""
    await sio.emit('pong', {'timestamp': time.time()}, room=sid)

@sio.on('subscribe')
async def handle_subscribe(sid, data):
    """Client s'abonne à un canal spécifique"""
    channel = data.get('channel', 'all')
    await sio.enter_room(sid, channel)
    await sio.emit('subscribed', {'channel': channel}, room=sid)

@sio.on('unsubscribe')
async def handle_unsubscribe(sid, data):
    """Client se désabonne d'un canal"""
    channel = data.get('channel', 'all')
    await sio.leave_room(sid, channel)
    await sio.emit('unsubscribed', {'channel': channel}, room=sid)
```

#### Frontend - Envoyer Commandes

```javascript
// Dans index.html - Ajouter fonctions d'envoi

function sendCommand(command, params = {}) {
    if (!socket || !socket.connected) {
        console.error('Socket non connecté');
        return Promise.reject('Socket non connecté');
    }
    
    return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
            reject('Timeout commande');
        }, 5000);
        
        socket.emit('client_command', {
            command: command,
            params: params,
            timestamp: Date.now()
        });
        
        // Écouter la réponse
        socket.once('command_ack', (data) => {
            clearTimeout(timeout);
            if (data.status === 'success') {
                resolve(data);
            } else {
                reject(data.error);
            }
        });
        
        socket.once('command_error', (data) => {
            clearTimeout(timeout);
            reject(data.error);
        });
    });
}

// Utilisation
async function startScanner() {
    try {
        await sendCommand('start_scanner');
        console.log('Scanner démarré');
    } catch (error) {
        console.error('Erreur démarrage scanner:', error);
    }
}

async function updateConfig(config) {
    try {
        await sendCommand('update_config', config);
        console.log('Config mise à jour');
    } catch (error) {
        console.error('Erreur mise à jour config:', error);
    }
}
```

### 2. **Système de Rooms/Namespaces**

```python
# Backend - Émettre vers des rooms spécifiques

# Room par instance
instance_room = f"instance_{port}"

# Room par session utilisateur
user_room = f"user_{user_id}"

# Émettre vers une room spécifique
await sio.emit('position_update', data, room=instance_room)

# Émettre vers toutes les rooms sauf une
await sio.emit('admin_notification', data, skip_sid=sid)
```

### 3. **Reconnexion Automatique avec Queue**

```javascript
// Frontend - Gestionnaire de reconnexion amélioré

class WebSocketManager {
    constructor(url) {
        this.url = url;
        this.socket = null;
        this.messageQueue = [];
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000;
        this.isReconnecting = false;
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
        
        this.socket.on('connect', () => {
            console.log('✅ WebSocket connecté');
            this.reconnectAttempts = 0;
            this.isReconnecting = false;
            
            // Envoyer les messages en queue
            this.flushMessageQueue();
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
    }
    
    emit(event, data, callback) {
        if (this.socket && this.socket.connected) {
            this.socket.emit(event, data, callback);
        } else {
            // Mettre en queue si déconnecté
            this.messageQueue.push({ event, data, callback });
            console.warn('Message mis en queue (déconnecté):', event);
        }
    }
    
    flushMessageQueue() {
        while (this.messageQueue.length > 0) {
            const { event, data, callback } = this.messageQueue.shift();
            this.socket.emit(event, data, callback);
        }
    }
    
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
        }
    }
}

// Utilisation
const wsManager = new WebSocketManager(API_BASE_URL);
wsManager.connect();
```

### 4. **Heartbeat/Ping-Pong**

```python
# Backend - Tâche de heartbeat périodique

async def heartbeat_task():
    """Envoyer ping périodique aux clients"""
    while True:
        try:
            await asyncio.sleep(30)  # Toutes les 30 secondes
            await sio.emit('ping', {'timestamp': time.time()})
            
            # Vérifier connexions mortes (optionnel)
            # Les clients doivent répondre avec 'pong'
        except Exception as e:
            logger.error(f"Erreur heartbeat: {e}")

# Démarrer dans le main
if __name__ == '__main__':
    asyncio.create_task(heartbeat_task())
```

```javascript
// Frontend - Répondre au ping

socket.on('ping', (data) => {
    socket.emit('pong', { timestamp: Date.now() });
});

// Vérifier connexion
let lastPing = Date.now();
socket.on('ping', () => {
    lastPing = Date.now();
});

setInterval(() => {
    if (Date.now() - lastPing > 60000) {
        console.warn('⚠️ Pas de ping depuis 60s, reconnexion...');
        socket.disconnect();
        socket.connect();
    }
}, 10000);
```

### 5. **Compression et Optimisation**

```python
# Backend - Compression des gros messages

import gzip
import json

async def emit_compressed(event, data, room=None):
    """Émettre événement avec compression si nécessaire"""
    data_str = json.dumps(data)
    
    # Compresser si > 1KB
    if len(data_str) > 1024:
        compressed = gzip.compress(data_str.encode())
        await sio.emit(event, {
            'compressed': True,
            'data': compressed.hex()  # Envoyer en hex
        }, room=room)
    else:
        await sio.emit(event, data, room=room)
```

```javascript
// Frontend - Décompression

socket.on('position_update', (data) => {
    if (data.compressed) {
        // Décompresser
        const decompressed = pako.inflate(data.data, { to: 'string' });
        data = JSON.parse(decompressed);
    }
    // Traiter data normalement
});
```

### 6. **Gestion d'Erreurs Améliorée**

```python
# Backend - Wrapper avec gestion d'erreurs

async def safe_emit(event, data, room=None, callback=None):
    """Émettre avec gestion d'erreurs"""
    try:
        if room:
            await sio.emit(event, data, room=room, callback=callback)
        else:
            await sio.emit(event, data, callback=callback)
    except Exception as e:
        logger.error(f"Erreur emit {event}: {e}")
        # Retry logic ou fallback
```

### 7. **Événements Typés avec Validation**

```python
# Backend - Validation des événements

from pydantic import BaseModel

class PositionUpdateEvent(BaseModel):
    symbol: str
    direction: str
    entry: float
    current_price: float
    pnl: float
    pnl_usdt: float

async def emit_position_update(position_data: dict):
    """Émettre avec validation"""
    try:
        validated = PositionUpdateEvent(**position_data)
        await sio.emit('position_update', validated.dict())
    except Exception as e:
        logger.error(f"Erreur validation position_update: {e}")
```

## 📋 Plan d'Implémentation

### Phase 1 : Communication Bidirectionnelle (Priorité Haute)
1. ✅ Ajouter handlers `client_command`, `ping`, `subscribe`
2. ✅ Implémenter fonctions `sendCommand()` frontend
3. ✅ Tester commandes start/stop/config

### Phase 2 : Reconnexion et Robustesse (Priorité Haute)
1. ✅ Implémenter `WebSocketManager` avec queue
2. ✅ Ajouter heartbeat ping-pong
3. ✅ Gestion erreurs améliorée

### Phase 3 : Optimisation (Priorité Moyenne)
1. ✅ Système de rooms/namespaces
2. ✅ Compression pour gros messages
3. ✅ Validation avec Pydantic

### Phase 4 : Monitoring (Priorité Basse)
1. ✅ Métriques WebSocket (connexions, messages/sec)
2. ✅ Dashboard monitoring
3. ✅ Alertes sur déconnexions

## 🔧 Exemple d'Utilisation Complète

```python
# Backend - main.py

@sio.on('client_command')
async def handle_client_command(sid, data):
    command = data.get('command')
    
    # Exécuter commande
    result = await execute_command(command, data.get('params'))
    
    # Confirmer avec callback
    await sio.emit('command_ack', {
        'command': command,
        'result': result,
        'status': 'success'
    }, room=sid, callback=lambda: logger.debug(f"ACK envoyé pour {command}"))
```

```javascript
// Frontend - index.html

// Envoyer commande avec callback
socket.emit('client_command', {
    command: 'start_scanner',
    params: { top_n: 20 }
}, (ack) => {
    if (ack.status === 'success') {
        console.log('✅ Scanner démarré');
    }
});

// Écouter événements
socket.on('position_update', (data) => {
    updatePositionUI(data);
});
```

## 📊 Métriques à Surveiller

- **Latence** : Temps entre émission et réception
- **Throughput** : Messages/seconde
- **Taux de reconnexion** : Fréquence des déconnexions
- **Taille moyenne messages** : Optimisation compression
- **Connexions actives** : Monitoring charge

## 🎯 Résultat Attendu

- ✅ Communication bidirectionnelle fiable
- ✅ Reconnexion automatique robuste
- ✅ Latence minimale (< 100ms)
- ✅ Gestion d'erreurs complète
- ✅ Scalabilité (multi-instances)
- ✅ Monitoring en temps réel

