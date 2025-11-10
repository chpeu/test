/**
 * 🔥 WebSocket Natif Bidirectionnel
 * Classe JavaScript pour communication WebSocket native avec le backend FastAPI
 * Compatible avec l'API Socket.IO pour migration progressive
 */
class BidirectionalWebSocket {
    constructor(url) {
        // Convertir http:// en ws:// ou https:// en wss://
        this.baseUrl = url.replace(/^http/, 'ws');
        this.url = this.baseUrl + '/ws';
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
        this.connected = false;
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
            console.log('✅ WebSocket natif connecté');
            this.connected = true;
            this.reconnectAttempts = 0;
            this.isReconnecting = false;
            this.lastPing = Date.now();
            
            // Envoyer messages en queue
            this.flushMessageQueue();
            
            // Émettre événement 'connect'
            this.emitEvent('connect', {});
            
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
            this.emitEvent('error', error);
        };
        
        this.ws.onclose = (event) => {
            console.warn('❌ WebSocket fermé:', event.code, event.reason);
            this.connected = false;
            this.emitEvent('disconnect', { code: event.code, reason: event.reason });
            
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
            const data = message.data;
            
            // Émettre vers les handlers
            this.emitEvent(event, data);
            return;
        }
        
        // Messages directs (compatibilité)
        this.emitEvent(type, message);
    }
    
    emitEvent(event, data) {
        const handlers = this.eventHandlers.get(event) || [];
        handlers.forEach(handler => {
            try {
                handler(data);
            } catch (error) {
                console.error(`Erreur handler ${event}:`, error);
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
            console.warn('⚠️ Message mis en queue (déconnecté):', data.type || data.command);
        }
    }
    
    sendCommand(command, params = {}) {
        return new Promise((resolve, reject) => {
            if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
                // Mettre en queue pour reconnexion
                this.messageQueue.push({ command, params, resolve, reject });
                reject(new Error('WebSocket non connecté'));
                return;
            }
            
            const commandId = ++this.commandIdCounter;
            const timeout = setTimeout(() => {
                this.commandCallbacks.delete(commandId);
                reject(new Error('Timeout commande'));
            }, 10000);  // 10 secondes timeout
            
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
    
    sendRequest(request, params = {}) {
        return new Promise((resolve, reject) => {
            if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
                reject(new Error('WebSocket non connecté'));
                return;
            }
            
            const requestId = ++this.commandIdCounter;
            const timeout = setTimeout(() => {
                this.commandCallbacks.delete(requestId);
                reject(new Error('Timeout requête'));
            }, 10000);
            
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
            
            this.send({
                type: 'request',
                id: requestId,
                request: request,
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
        // 🔥 MIGRATION COMPLÈTE: Émettre événement via WebSocket natif
        this.send({
            type: 'event',
            event: event,
            data: data,
            timestamp: Date.now()
        });
    }
    
    once(event, handler) {
        // 🔥 MIGRATION COMPLÈTE: Écouter événement une seule fois (compatibilité)
        const onceHandler = (data) => {
            this.off(event, onceHandler);
            handler(data);
        };
        this.on(event, onceHandler);
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
            30000  // Max 30 secondes
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
        this.connected = false;
    }
}

// Exporter pour utilisation globale
if (typeof window !== 'undefined') {
    window.BidirectionalWebSocket = BidirectionalWebSocket;
}
