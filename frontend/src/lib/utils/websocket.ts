/**
 * 🔥 WebSocket Natif Bidirectionnel pour Svelte
 * Point d'entrée principal - Ré-exporte tout depuis websocket-impl.ts
 * Ce fichier est le point d'entrée principal pour garantir la compatibilité Vite/SvelteKit
 */

// 🔥 FIX: Import et ré-export explicite pour garantir la résolution correcte
import type {
    WebSocketMessage,
    CommandCallback
} from './websocket-impl';

import {
    BidirectionalWebSocket,
    initWebSocket,
    getWebSocket,
    sendCommandViaWS,
    sendRequestViaWS
} from './websocket-impl';

// Ré-export explicite de tous les exports
export {
    BidirectionalWebSocket,
    initWebSocket,
    getWebSocket,
    sendCommandViaWS,
    sendRequestViaWS
};

export type {
    WebSocketMessage,
    CommandCallback
};

// Export default
export { BidirectionalWebSocket as default };
