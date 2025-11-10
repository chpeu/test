/**
 * 🔥 WebSocket Natif Bidirectionnel pour Svelte
 * Classe TypeScript pour communication WebSocket native avec le backend FastAPI
 * Migration complète depuis Socket.IO vers WebSocket natif
 */

export interface WebSocketMessage {
    type: string;
    event?: string;
    command?: string;
    request_type?: string;
    id?: number;
    params?: any;
    data?: any;
    result?: any;
    error?: string;
    timestamp?: number;
}

export interface CommandCallback {
    resolve: (data: any) => void;
    reject: (error: Error) => void;
}

export class BidirectionalWebSocket {
    private baseUrl: string;
    private url: string;
    private ws: WebSocket | null = null;
    private reconnectAttempts: number = 0;
    private maxReconnectAttempts: number = 10;
    private reconnectDelay: number = 1000;
    private messageQueue: any[] = [];
    private commandCallbacks: Map<number, CommandCallback> = new Map();
    private commandIdCounter: number = 0;
    private eventHandlers: Map<string, Array<(data: any) => void>> = new Map();
    private isReconnecting: boolean = false;
    private lastPing: number = Date.now();
    private pingInterval: number | null = null;
    private reconnectTimeout: number | null = null;
    private rooms: Set<string> = new Set();
    public connected: boolean = false;

    constructor(url: string = '') {
        // Détecter l'URL depuis window.location si non fournie
        if (!url) {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.host;
            url = `${protocol}//${host}`;
        }
        
        // Convertir http:// en ws:// ou https:// en wss://
        this.baseUrl = url.replace(/^http/, 'ws');
        this.url = this.baseUrl + '/ws';
    }

    connect(): void {
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

    private setupEventHandlers(): void {
        if (!this.ws) return;

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

        this.ws.onmessage = (event: MessageEvent) => {
            try {
                const message: WebSocketMessage = JSON.parse(event.data);
                this.handleMessage(message);
            } catch (error) {
                console.error('❌ Erreur parsing message:', error, event.data);
            }
        };

        this.ws.onerror = (error: Event) => {
            console.error('❌ Erreur WebSocket:', error);
            this.emitEvent('error', error);
        };

        this.ws.onclose = (event: CloseEvent) => {
            console.warn('❌ WebSocket fermé:', event.code, event.reason);
            this.connected = false;
            this.emitEvent('disconnect', { code: event.code, reason: event.reason });
            
            if (event.code !== 1000) {  // Pas une fermeture normale
                this.scheduleReconnect();
            }
        };
    }

    private handleMessage(message: WebSocketMessage): void {
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
            const callback = this.commandCallbacks.get(message.id || 0);
            if (callback) {
                callback.resolve(message);
                this.commandCallbacks.delete(message.id || 0);
            }
            return;
        }

        if (type === 'command_error') {
            const callback = this.commandCallbacks.get(message.id || 0);
            if (callback) {
                callback.reject(new Error(message.error || 'Unknown error'));
                this.commandCallbacks.delete(message.id || 0);
            }
            return;
        }

        // Réponses aux requêtes
        if (type === 'request_response') {
            const callback = this.commandCallbacks.get(message.id || 0);
            if (callback) {
                callback.resolve(message.data);
                this.commandCallbacks.delete(message.id || 0);
            }
            return;
        }

        // Événements
        if (type === 'event') {
            const event = message.event;
            const data = message.data;
            
            // Émettre vers les handlers
            this.emitEvent(event || 'unknown', data);
            return;
        }

        // Messages directs (compatibilité)
        this.emitEvent(type, message);
    }

    private emitEvent(event: string, data: any): void {
        const handlers = this.eventHandlers.get(event) || [];
        handlers.forEach(handler => {
            try {
                handler(data);
            } catch (error) {
                console.error(`Erreur handler ${event}:`, error);
            }
        });
    }

    private send(data: any): void {
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

    sendCommand(command: string, params: any = {}): Promise<any> {
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
                resolve: (data: any) => {
                    clearTimeout(timeout);
                    resolve(data.result || data);
                },
                reject: (error: Error) => {
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

    sendRequest(requestType: string, params: any = {}): Promise<any> {
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
                resolve: (data: any) => {
                    clearTimeout(timeout);
                    resolve(data);
                },
                reject: (error: Error) => {
                    clearTimeout(timeout);
                    reject(error);
                }
            });

            this.send({
                type: 'request',
                id: requestId,
                request_type: requestType,
                params: params,
                timestamp: Date.now()
            });
        });
    }

    on(event: string, handler: (data: any) => void): void {
        if (!this.eventHandlers.has(event)) {
            this.eventHandlers.set(event, []);
        }
        this.eventHandlers.get(event)!.push(handler);
    }

    off(event: string, handler: (data: any) => void): void {
        const handlers = this.eventHandlers.get(event);
        if (handlers) {
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }

    emit(event: string, data: any): void {
        // 🔥 MIGRATION COMPLÈTE: Émettre événement via WebSocket natif
        this.send({
            type: 'event',
            event: event,
            data: data,
            timestamp: Date.now()
        });
    }

    once(event: string, handler: (data: any) => void): void {
        // 🔥 MIGRATION COMPLÈTE: Écouter événement une seule fois (compatibilité)
        const onceHandler = (data: any) => {
            this.off(event, onceHandler);
            handler(data);
        };
        this.on(event, onceHandler);
    }

    subscribe(channel: string): void {
        this.rooms.add(channel);
        this.send({ type: 'subscribe', channel: channel });
    }

    unsubscribe(channel: string): void {
        this.rooms.delete(channel);
        this.send({ type: 'unsubscribe', channel: channel });
    }

    private flushMessageQueue(): void {
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

    private scheduleReconnect(): void {
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

        this.reconnectTimeout = window.setTimeout(() => {
            this.connect();
        }, delay);
    }

    private startHeartbeat(): void {
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
        this.pingInterval = window.setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.send({ type: 'ping', timestamp: Date.now() });
            }
        }, 30000);
    }

    disconnect(): void {
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

// Instance globale
let wsInstance: BidirectionalWebSocket | null = null;

export function initWebSocket(url?: string): BidirectionalWebSocket {
    if (!wsInstance) {
        wsInstance = new BidirectionalWebSocket(url);
        wsInstance.connect();
    }
    return wsInstance;
}

export function getWebSocket(): BidirectionalWebSocket | null {
    return wsInstance;
}

export function sendCommandViaWS(command: string, params: any = {}): Promise<any> {
    if (!wsInstance || !wsInstance.connected) {
        return Promise.reject(new Error('WebSocket non connecté'));
    }
    return wsInstance.sendCommand(command, params);
}

export function sendRequestViaWS(requestType: string, params: any = {}): Promise<any> {
    if (!wsInstance || !wsInstance.connected) {
        return Promise.reject(new Error('WebSocket non connecté'));
    }
    return wsInstance.sendRequest(requestType, params);
}

// Export default pour compatibilité
export default BidirectionalWebSocket;

// Ré-exports explicites pour garantir la compatibilité (au cas où)
export { sendCommandViaWS, sendRequestViaWS, initWebSocket, getWebSocket };

