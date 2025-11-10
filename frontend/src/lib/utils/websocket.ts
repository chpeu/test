/**
 * 🔥 WebSocket Natif Bidirectionnel pour Svelte
 * Point d'entrée principal - Ré-exporte tout depuis websocket-impl.ts
 * Ce fichier est le point d'entrée principal pour garantir la compatibilité Vite/SvelteKit
 */

// Import explicite de tous les exports
import {
    BidirectionalWebSocket,
    initWebSocket,
    getWebSocket,
    sendCommandViaWS,
    sendRequestViaWS,
    type WebSocketMessage,
    type CommandCallback
} from './websocket-impl';

import BidirectionalWebSocketDefault from './websocket-impl';

// Ré-export explicite de tous les exports nommés
export {
    BidirectionalWebSocket,
    initWebSocket,
    getWebSocket,
    sendCommandViaWS,
    sendRequestViaWS,
    type WebSocketMessage,
    type CommandCallback
};

// Ré-export du default
export default BidirectionalWebSocketDefault;
