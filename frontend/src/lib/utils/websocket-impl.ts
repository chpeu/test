/**
 * 🔥 WebSocket Natif Bidirectionnel pour Svelte
 * Classe TypeScript pour communication WebSocket native avec le backend FastAPI
 * Migration complète depuis Socket.IO vers WebSocket natif
 * 
 * IMPORTANT: Tous les exports doivent être au niveau racine pour compatibilité Vite/SvelteKit
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
            // 🔥 FIX: En développement, utiliser directement le backend (port 5000)
            // En production, utiliser le proxy Vite (window.location.host)
            const isDev = window.location.hostname === 'localhost' && window.location.port === '3000';
            if (isDev) {
                // Développement: connexion directe au backend
                url = 'ws://localhost:5000';
            } else {
                // Production: utiliser le proxy ou l'URL de production
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const host = window.location.host;
                url = `${protocol}//${host}`;
            }
        }
        
        // Convertir http:// en ws:// ou https:// en wss:// si nécessaire
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
            this.flushQueue();
            // 🔥 FIX: Mettre à jour le store de connexion
            import('$lib/stores/connection').then(({ setConnected }) => {
                setConnected();
            });
            this.emit('connect', {}); // Émettre un événement de connexion
        };

        this.ws.onmessage = (event) => {
            try {
                const message: WebSocketMessage = JSON.parse(event.data);
                // console.log('⬇️ Message WebSocket reçu:', message);

                if (message.type === 'event' && message.event) {
                    this.handleEvent(message.event, message.data);
                } else if (message.type === 'response' && message.id !== undefined) {
                    this.handleResponse(message.id, message.result, message.error);
                } else if (message.type === 'command_response' && message.id !== undefined) {
                    this.handleResponse(message.id, message.result, message.error);
                } else if (message.type === 'request_response' && message.id !== undefined) {
                    this.handleResponse(message.id, message.data, message.error);
                } else if (message.type === 'ping') {
                    // 🔥 FIX: Répondre au ping du serveur
                    this.sendRaw(JSON.stringify({ type: 'pong' }));
                } else if (message.type === 'pong') {
                    // 🔥 FIX: Mettre à jour lastPing quand on reçoit le pong (réponse à notre ping)
                    this.lastPing = Date.now();
                }
            } catch (error) {
                console.error('❌ Erreur traitement message WebSocket:', error, event.data);
            }
        };

        this.ws.onclose = (event) => {
            this.connected = false;
            console.warn('⚠️ WebSocket déconnecté:', event.code, event.reason);
            this.stopHeartbeat();
            // 🔥 FIX: Mettre à jour le store de connexion
            import('$lib/stores/connection').then(({ setDisconnected, setReconnecting }) => {
                if (this.reconnectAttempts < this.maxReconnectAttempts) {
                    setReconnecting();
                } else {
                    setDisconnected();
                }
            });
            this.emit('disconnect', { code: event.code, reason: event.reason }); // Émettre un événement de déconnexion
            this.scheduleReconnect();
        };

        this.ws.onerror = (error) => {
            console.error('❌ Erreur WebSocket:', error);
            this.emit('error', error); // Émettre un événement d'erreur
            if (this.ws && this.ws.readyState === WebSocket.CLOSED) {
                this.scheduleReconnect();
            }
        };
    }

    private sendRaw(message: string): void {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(message);
        } else {
            this.messageQueue.push(message);
        }
    }

    private flushQueue(): void {
        while (this.messageQueue.length > 0 && this.ws && this.ws.readyState === WebSocket.OPEN) {
            const message = this.messageQueue.shift();
            this.ws.send(message);
        }
    }

    sendCommand(command: string, params: any = {}): Promise<any> {
        return new Promise((resolve, reject) => {
            const id = this.commandIdCounter++;
            this.commandCallbacks.set(id, { resolve, reject });
            const message: WebSocketMessage = {
                type: 'command',
                id,
                command,
                params,
                timestamp: Date.now()
            };
            this.sendRaw(JSON.stringify(message));
        });
    }

    sendRequest(requestType: string, params: any = {}): Promise<any> {
        return new Promise((resolve, reject) => {
            const id = this.commandIdCounter++;
            this.commandCallbacks.set(id, { resolve, reject });
            const message: WebSocketMessage = {
                type: 'request',
                id,
                request_type: requestType,
                params,
                timestamp: Date.now()
            };
            this.sendRaw(JSON.stringify(message));
        });
    }

    private handleResponse(id: number, result: any, error: string | undefined): void {
        const callback = this.commandCallbacks.get(id);
        if (callback) {
            if (error) {
                callback.reject(new Error(error));
            } else {
                callback.resolve(result);
            }
            this.commandCallbacks.delete(id);
        }
    }

    private handleEvent(event: string, data: any): void {
        const handlers = this.eventHandlers.get(event);
        if (handlers) {
            handlers.forEach(handler => handler(data));
        }
    }

    on(event: string, handler: (data: any) => void): () => void {
        if (!this.eventHandlers.has(event)) {
            this.eventHandlers.set(event, []);
        }
        this.eventHandlers.get(event)?.push(handler);
        // Retourne une fonction de désinscription
        return () => {
            this.off(event, handler);
        };
    }

    off(event: string, handler: (data: any) => void): void {
        const handlers = this.eventHandlers.get(event);
        if (handlers) {
            this.eventHandlers.set(event, handlers.filter(h => h !== handler));
        }
    }

    emit(event: string, data: any): void {
        const handlers = this.eventHandlers.get(event);
        if (handlers) {
            handlers.forEach(handler => handler(data));
        }
    }

    once(event: string, handler: (data: any) => void): void {
        const wrappedHandler = (data: any) => {
            handler(data);
            this.off(event, wrappedHandler);
        };
        this.on(event, wrappedHandler);
    }

    private scheduleReconnect(): void {
        if (this.isReconnecting) return;

        this.isReconnecting = true;
        // 🔥 FIX: Mettre à jour le store pour indiquer la reconnexion
        import('$lib/stores/connection').then(({ setReconnecting }) => {
            setReconnecting();
        });
        this.reconnectTimeout = window.setTimeout(() => {
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                console.log(`🔄 Tentative de reconnexion WebSocket #${this.reconnectAttempts}...`);
                this.connect();
            } else {
                console.error('❌ Nombre maximal de tentatives de reconnexion WebSocket atteint.');
                // 🔥 FIX: Mettre à jour le store pour indiquer la déconnexion finale
                import('$lib/stores/connection').then(({ setDisconnected }) => {
                    setDisconnected();
                });
                this.emit('error', new Error('Max reconnect attempts reached'));
            }
            this.isReconnecting = false;
        }, this.reconnectDelay * Math.pow(2, this.reconnectAttempts)); // Backoff exponentiel
    }

    private startHeartbeat(): void {
        this.stopHeartbeat(); // S'assurer qu'il n'y a qu'un seul intervalle
        const PING_INTERVAL = 30000; // 30 secondes (augmenté pour éviter reconnexions fréquentes)
        const PONG_TIMEOUT = 60000; // 60 secondes (2x ping interval)
        
        // 🔥 FIX: Initialiser lastPing à la connexion
        this.lastPing = Date.now();
        
        this.pingInterval = window.setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                // 🔥 FIX: Vérifier d'abord si pas de pong reçu depuis PONG_TIMEOUT ms
                const timeSinceLastPong = Date.now() - this.lastPing;
                if (timeSinceLastPong > PONG_TIMEOUT) {
                    console.warn('⚠️ Pas de pong reçu depuis', Math.round(timeSinceLastPong / 1000), 'secondes, reconnexion forcée.');
                    this.ws.close(); // Force la reconnexion via onclose
                    return;
                }
                // Envoyer ping seulement si connexion OK
                this.sendRaw(JSON.stringify({ type: 'ping' }));
            }
        }, PING_INTERVAL);
    }

    private stopHeartbeat(): void {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
        if (this.reconnectTimeout) {
            clearTimeout(this.reconnectTimeout);
            this.reconnectTimeout = null;
        }
    }

    disconnect(): void {
        if (this.ws) {
            console.log('👋 Déconnexion WebSocket manuelle');
            this.stopHeartbeat();
            this.ws.close();
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

// Exports directs - Structure simplifiée pour compatibilité maximale avec Vite/SvelteKit
// IMPORTANT: Utilisation de function declaration (pas arrow function) pour meilleure compatibilité
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

