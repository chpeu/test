/**
 * Store Svelte pour l'état de connexion WebSocket natif
 * Gère reconnexion automatique et état en temps réel
 */
import { writable, derived } from 'svelte/store';

// Connection state
export const connected = writable(false);
export const reconnecting = writable(false);
export const reconnectAttempts = writable(0);

// Computed: Connection status text
export const connectionStatus = derived(
	[connected, reconnecting],
	([$connected, $reconnecting]) => {
		if ($connected) return 'Connected';
		if ($reconnecting) return 'Reconnecting...';
		return 'Disconnected';
	}
);

// Computed: Connection status color
export const connectionColor = derived(
	[connected, reconnecting],
	([$connected, $reconnecting]) => {
		if ($connected) return '#00ff88';
		if ($reconnecting) return '#ffaa00';
		return '#ff4444';
	}
);

// Computed: Connection icon
export const connectionIcon = derived(
	[connected, reconnecting],
	([$connected, $reconnecting]) => {
		if ($connected) return '🟢';
		if ($reconnecting) return '🟡';
		return '🔴';
	}
);

// Actions
export function setConnected() {
	connected.set(true);
	reconnecting.set(false);
	reconnectAttempts.set(0);
}

export function setDisconnected() {
	connected.set(false);
	reconnecting.set(false);
}

export function setReconnecting() {
	connected.set(false);
	reconnecting.set(true);
	reconnectAttempts.update(n => n + 1);
}

export function resetReconnectAttempts() {
	reconnectAttempts.set(0);
}
