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
    ping_id?: number;
    client_ts?: number;
    connection_id?: number;
    client_id?: string;
    session_id?: string;
    context?: any;
    response_id?: string;
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
    private clientId: string | null = null;
    private serverConnectionId: number | null = null;
    private lastPongAt: number | null = null;
    private lastRttMs: number | null = null;
    private clientPingIdCounter: number = 0;
    public connected: boolean = false;

    constructor(url: string = '') {
        if (typeof window !== 'undefined') {
            try {
                const stored = window.localStorage.getItem('ws_client_id');
                if (stored) {
                    this.clientId = stored;
                } else {
                    const randomUUID = (window.crypto as any)?.randomUUID;
                    const generated = (window.crypto && typeof randomUUID === 'function')
                        ? randomUUID.call(window.crypto)
                        : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
                    this.clientId = generated;
                    window.localStorage.setItem('ws_client_id', generated);
                }
            } catch {
                this.clientId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
            }
        }

        if (!url) {
            if (typeof window !== 'undefined' && window.location) {
                // Par défaut, utiliser la même origine (permet le proxy Vite /ws en dev)
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const host = window.location.host;
                url = `${protocol}//${host}`;
                console.log('🔧 Connexion WebSocket via origin/proxy:', url);
            } else {
                // Fallback (SSR ou environnement sans window)
                url = 'ws://localhost:5000';
            }
        }
        
        // Convertir http:// en ws:// ou https:// en wss:// si nécessaire
        this.baseUrl = url.replace(/^http/, 'ws');
        this.url = this.baseUrl + '/ws';
        
        console.log('🎯 WebSocket URL finale construite:', this.url);
    }

    connect(): void {
        try {
            console.log('🔄 Connexion WebSocket:', this.url);
            this.serverConnectionId = null;
            this.lastPongAt = null;
            this.lastRttMs = null;
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
            this.lastPing = Date.now();
            this.lastPongAt = null;
            this.lastRttMs = null;
            this.flushQueue();
            // 🔥 FIX: Mettre à jour le store de connexion
            import('$lib/stores/connection')
                .then(({ setConnected }) => {
                    setConnected();
                })
                .catch((err) => {
                    console.error('❌ [WEBSOCKET-CLIENT] Failed to import connection store on open:', err);
                });
            this.sendClientHello();
            this.emit('connect', {}); // Émettre un événement de connexion
        };

        this.ws.onmessage = (event) => {
            try {
                console.log('� WEBSOCKET MESSAGE RECEIVED:', event.data);
                const message: WebSocketMessage = JSON.parse(event.data);
                console.log('� Received:', message.type, message.event || 'unknown');
                
                if (message.type === 'ping') {
                    this.lastPing = Date.now();
                    const pongPayload: any = { type: 'pong', timestamp: Date.now() };
                    if (typeof message.ping_id === 'number') {
                        pongPayload.ping_id = message.ping_id;
                    }
                    this.sendRaw(JSON.stringify(pongPayload));
                    return;
                }
                
                if (message.type === 'pong') {
                    this.lastRttMs = Date.now() - this.lastPing;
                    this.lastPongAt = Date.now();
                    return;
                }
                
                if (message.type === 'server_hello') {
                    this.serverConnectionId = message.connection_id || null;
                    console.log(`🤝 Server hello: connection ${this.serverConnectionId}`);
                    return;
                }

                if ((message.type === 'request_response' || message.type === 'command_response') && typeof message.id === 'number') {
                    const payload = message.type === 'command_response' ? message.result : message.data;
                    this.handleResponse(message.id, payload, message.error);
                } else if (message.type === 'event' && message.event) {
                    console.log('� PROCESSING EVENT:', message.event);
                    const eventData = {
                        ...message.data,
                        session_id: message.session_id,
                        timestamp: message.timestamp
                    };
                    this.handleEvent(message.event, eventData);
                }
            } catch (error) {
                console.error('WebSocket message parsing error:', error, 'Raw data:', event.data);
            }
        };

        this.ws.onclose = (event) => {
            this.connected = false;
            const now = Date.now();
            const timeSinceLastActivityMs = now - this.lastPing;
            const timeSinceLastPongMs = this.lastPongAt ? (now - this.lastPongAt) : null;
            const online = typeof navigator !== 'undefined' ? navigator.onLine : null;
            const visibility = typeof document !== 'undefined' ? document.visibilityState : null;
            console.warn('⚠️ WebSocket déconnecté:', {
                url: this.url,
                code: event.code,
                reason: event.reason,
                wasClean: event.wasClean,
                readyState: this.ws?.readyState,
                reconnectAttempts: this.reconnectAttempts,
                serverConnectionId: this.serverConnectionId,
                clientId: this.clientId,
                lastRttMs: this.lastRttMs,
                timeSinceLastActivityMs,
                timeSinceLastPongMs,
                online,
                visibility,
            });
            this.stopHeartbeat();
            // 🔥 FIX: Mettre à jour le store de connexion
            import('$lib/stores/connection')
                .then(({ setDisconnected, setReconnecting }) => {
                    if (this.reconnectAttempts < this.maxReconnectAttempts) {
                        setReconnecting();
                    } else {
                        setDisconnected();
                    }
                })
                .catch((err) => {
                    console.error('❌ [WEBSOCKET-CLIENT] Failed to import connection store on close:', err);
                });
            this.emit('disconnect', {
                code: event.code,
                reason: event.reason,
                wasClean: event.wasClean,
                reconnectAttempts: this.reconnectAttempts,
                serverConnectionId: this.serverConnectionId,
                clientId: this.clientId,
                lastRttMs: this.lastRttMs,
                timeSinceLastActivityMs,
                timeSinceLastPongMs,
                online,
                visibility,
            }); // Émettre un événement de déconnexion
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
        try {
            const callback = this.commandCallbacks.get(id);
            if (!callback) return;
            if (error) {
                callback.reject(new Error(error));
            } else {
                callback.resolve(result);
            }
            this.commandCallbacks.delete(id);
        } catch (e) {
            console.error('❌ [WEBSOCKET-CLIENT] handleResponse error:', e);
            this.commandCallbacks.delete(id);
        }
    }

    private handleEvent(event: string, data: any): void {
        const handlers = this.eventHandlers.get(event);
        if (!handlers || handlers.length === 0) return;

        handlers.forEach((handler) => {
            try {
                const maybePromise: any = handler(data);
                if (maybePromise && typeof (maybePromise as any).then === 'function') {
                    (maybePromise as Promise<any>).catch((err) => {
                        console.error(`❌ [WEBSOCKET-CLIENT] Unhandled async error in handler for event '${event}':`, err);
                    });
                }
            } catch (err) {
                console.error(`❌ [WEBSOCKET-CLIENT] Error in handler for event '${event}':`, err);
            }
        });
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
        if (!handlers || handlers.length === 0) return;
        handlers.forEach((handler) => {
            try {
                const maybePromise: any = handler(data);
                if (maybePromise && typeof (maybePromise as any).then === 'function') {
                    (maybePromise as Promise<any>).catch((err) => {
                        console.error(`❌ [WEBSOCKET-CLIENT] Unhandled async error in emit('${event}') handler:`, err);
                    });
                }
            } catch (err) {
                console.error(`❌ [WEBSOCKET-CLIENT] Error in emit('${event}') handler:`, err);
            }
        });
    }

    once(event: string, handler: (data: any) => void): void {
        const wrappedHandler = (data: any) => {
            try {
                const maybePromise: any = handler(data);
                if (maybePromise && typeof (maybePromise as any).then === 'function') {
                    (maybePromise as Promise<any>).catch((err) => {
                        console.error(`❌ [WEBSOCKET-CLIENT] Unhandled async error in once('${event}') handler:`, err);
                    }).finally(() => {
                        this.off(event, wrappedHandler);
                    });
                    return;
                }
            } catch (err) {
                console.error(`❌ [WEBSOCKET-CLIENT] Error in once('${event}') handler:`, err);
            } finally {
                this.off(event, wrappedHandler);
            }
        };
        this.on(event, wrappedHandler);
    }

    private scheduleReconnect(): void {
        if (this.isReconnecting) return;

        this.isReconnecting = true;
        // 🔥 FIX: Mettre à jour le store pour indiquer la reconnexion
        import('$lib/stores/connection')
            .then(({ setReconnecting }) => {
                setReconnecting();
            })
            .catch((err) => {
                console.error('❌ [WEBSOCKET-CLIENT] Failed to import connection store on reconnect:', err);
            });
        this.reconnectTimeout = window.setTimeout(() => {
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                console.log(`🔄 Tentative de reconnexion WebSocket #${this.reconnectAttempts}...`);
                this.connect();
            } else {
                console.error('❌ Nombre maximal de tentatives de reconnexion WebSocket atteint.');
                // 🔥 FIX: Mettre à jour le store pour indiquer la déconnexion finale
                import('$lib/stores/connection')
                    .then(({ setDisconnected }) => {
                        setDisconnected();
                    })
                    .catch((err) => {
                        console.error('❌ [WEBSOCKET-CLIENT] Failed to import connection store on final disconnect:', err);
                    });
                this.emit('error', new Error('Max reconnect attempts reached'));
            }
            this.isReconnecting = false;
        }, this.reconnectDelay * Math.pow(2, this.reconnectAttempts)); // Backoff exponentiel
    }

    private startHeartbeat(): void {
        this.stopHeartbeat(); // S'assurer qu'il n'y a qu'un seul intervalle
        const PING_INTERVAL = 60000; // 60 secondes pour être compatible avec server 120s timeout
        const PONG_TIMEOUT = 180000; // 180 secondes (3x ping interval pour être tolérant)
        
        // 🔥 FIX: Initialiser correctement les timestamps
        const now = Date.now();
        this.lastPing = now;
        this.lastPongAt = now; // Considérer la connexion comme "vivante" au début
        
        this.pingInterval = window.setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                const now = Date.now();
                
                // 🔥 FIX: Vérifier si pas de pong reçu depuis PONG_TIMEOUT (utiliser lastPongAt, pas lastPing)
                const timeSinceLastPong = this.lastPongAt ? (now - this.lastPongAt) : (now - this.lastPing);
                if (timeSinceLastPong > PONG_TIMEOUT) {
                    console.warn(`⚠️ [WEBSOCKET-CLIENT] Pas d'activité depuis ${Math.round(timeSinceLastPong / 1000)}s (seuil: ${PONG_TIMEOUT/1000}s), reconnexion forcée.`);
                    this.ws.close(1000, "Client heartbeat timeout"); // Force la reconnexion via onclose
                    return;
                }
                
                // Envoyer ping client pour mesurer RTT
                this.clientPingIdCounter += 1;
                const pingId = this.clientPingIdCounter;
                const clientTs = now;
                console.debug(`📡 [WEBSOCKET-CLIENT] Envoi ping #${pingId} au serveur`);
                this.sendRaw(JSON.stringify({ 
                    type: 'ping', 
                    ping_id: pingId, 
                    timestamp: clientTs,
                    client_ts: clientTs
                }));
                
                // Mettre à jour lastPing pour indiquer qu'on a envoyé un ping
                this.lastPing = now;
            } else {
                console.debug(`⚠️ [WEBSOCKET-CLIENT] WebSocket pas ouvert (state: ${this.ws?.readyState}), arrêt heartbeat`);
                this.stopHeartbeat();
            }
        }, PING_INTERVAL);
        
        console.debug(`💓 [WEBSOCKET-CLIENT] Heartbeat démarré (ping: ${PING_INTERVAL/1000}s, timeout: ${PONG_TIMEOUT/1000}s)`);
    }

    private sendClientHello(): void {
        if (typeof window === 'undefined') return;
        const nav: any = window.navigator as any;
        const ctx: any = {
            userAgent: nav?.userAgent,
            language: nav?.language,
            languages: nav?.languages,
            platform: nav?.platform,
            timezone: (() => {
                try {
                    return Intl.DateTimeFormat().resolvedOptions().timeZone;
                } catch {
                    return null;
                }
            })(),
            href: window.location?.href,
            origin: window.location?.origin,
            pathname: window.location?.pathname,
            visibility: typeof document !== 'undefined' ? document.visibilityState : null,
            online: nav?.onLine,
            deviceMemory: nav?.deviceMemory,
            hardwareConcurrency: nav?.hardwareConcurrency,
            screen: {
                width: window.screen?.width,
                height: window.screen?.height,
                devicePixelRatio: window.devicePixelRatio,
            },
            viewport: {
                innerWidth: window.innerWidth,
                innerHeight: window.innerHeight,
            },
            connection: nav?.connection ? {
                effectiveType: nav.connection.effectiveType,
                rtt: nav.connection.rtt,
                downlink: nav.connection.downlink,
                saveData: nav.connection.saveData,
            } : null,
        };

        this.sendRaw(JSON.stringify({
            type: 'client_hello',
            client_id: this.clientId,
            context: ctx,
            timestamp: Date.now(),
        }));
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

