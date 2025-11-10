/**
 * Socket.IO Wrapper pour Trade Cursor
 * Synchronise automatiquement les stores Svelte avec le backend FastAPI
 */
import { io } from 'socket.io-client';
import { browser } from '$app/environment';

// Stores
import { updatePosition, clearPosition } from '$lib/stores/position';
import { updateStats, incrementWin, incrementLoss } from '$lib/stores/stats';
import { addLog, addConfigLog } from '$lib/stores/logs';
import { addTrade, setTradeHistory } from '$lib/stores/trades';
import {
	startScanning,
	stopScanning,
	updateTopPairs,
	updateScanProgress
} from '$lib/stores/scanner';
import {
	setConnected,
	setDisconnected,
	setReconnecting
} from '$lib/stores/connection';

// Notifications
import {
	notifyPositionOpened,
	notifyPositionClosed,
	notifySetupFound,
	notifyError,
	notifyWinrate
} from './notifications';

let socket = null;

/**
 * Initialiser Socket.IO avec reconnexion automatique
 */
export function initSocket() {
	if (!browser) return null;

	socket = io({
		reconnection: true,
		reconnectionDelay: 1000,
		reconnectionDelayMax: 5000,
		reconnectionAttempts: Infinity,
		timeout: 20000
	});

	// === ÉVÉNEMENTS CONNEXION ===

	socket.on('connect', () => {
		console.log('✅ Socket.IO connected');
		setConnected();
	});

	socket.on('disconnect', () => {
		console.log('❌ Socket.IO disconnected');
		setDisconnected();
	});

	socket.on('reconnecting', (attemptNumber) => {
		console.log(`🔄 Socket.IO reconnecting... (attempt ${attemptNumber})`);
		setReconnecting();
	});

	socket.on('reconnect', (attemptNumber) => {
		console.log(`✅ Socket.IO reconnected after ${attemptNumber} attempts`);
		setConnected();
	});

	// === ÉVÉNEMENTS LOGS ===

	socket.on('log', (logEntry) => {
		addLog(logEntry);
	});

	socket.on('config_change', (configLogEntry) => {
		addConfigLog(configLogEntry);
		// 🔥 FIX: Recharger la config depuis le backend pour synchronisation temps réel
		if (configLogEntry.changes) {
			console.log('🔄 Config changée via Socket.IO:', configLogEntry.changes);
			// Les composants qui utilisent la config devront recharger depuis /api/state
		}
	});

	// === ÉVÉNEMENTS SCANNER ===

	socket.on('scan_started', (data) => {
		console.log('🔍 Scan started:', data);
		startScanning();
	});

	socket.on('scan_complete', (data) => {
		console.log('✅ Scan complete:', data);
		stopScanning();
		if (data.top_pairs) {
			updateTopPairs(data.top_pairs);
		}
	});

	socket.on('scan_progress', (data) => {
		if (data.progress !== undefined) {
			updateScanProgress(data.progress);
		}
	});

	socket.on('top_pairs_update', (data) => {
		if (data.pairs) {
			updateTopPairs(data.pairs);
		}
	});

	// === ÉVÉNEMENTS POSITION ===

	socket.on('position_opened', (data) => {
		console.log('🟢 Position opened:', data);
		updatePosition(data);
		addLog({
			level: 'INFO',
			message: `Position ouverte: ${data.symbol} ${data.direction}`
		});

		// Notification push
		notifyPositionOpened(data);
	});

	socket.on('position_update', (data) => {
		updatePosition(data);
		// 🔥 FIX: Mise à jour immédiate pour synchronisation temps réel
		console.log('🔄 Position mise à jour via Socket.IO:', data.symbol);
	});

	socket.on('position_closed', (result) => {
		console.log('🔴 Position closed:', result);
		clearPosition();

		// Update stats
		if (result.net_pnl_usdt > 0) {
			incrementWin(result);
		} else {
			incrementLoss(result);
		}

		// Add to trade history
		addTrade(result);

		// Log
		const pnlText = result.net_pnl_usdt >= 0 ? `+${result.net_pnl_pct}%` : `${result.net_pnl_pct}%`;
		addLog({
			level: 'INFO',
			message: `Position fermée: ${result.symbol} | ${result.reason} | ${pnlText}`
		});

		// Notification push
		notifyPositionClosed(result);
	});

	// === ÉVÉNEMENTS STATS ===

	socket.on('stats_update', (data) => {
		updateStats(data);

		// Notification milestone winrate
		if (data.winrate && data.total_trades) {
			notifyWinrate(data.winrate, data.total_trades);
		}
	});

	// === ÉVÉNEMENTS ÉTAT ===

	socket.on('status', (status) => {
		// 🔥 FIX: Mise à jour immédiate pour synchronisation temps réel
		console.log('🔄 Status mis à jour via Socket.IO:', {
			is_scanning: status.is_scanning,
			has_position: !!status.active_position,
			trades_count: status.trade_history?.length || 0
		});

		// Update scanning state
		if (status.is_scanning !== undefined) {
			if (status.is_scanning) {
				startScanning();
			} else {
				stopScanning();
			}
		}

		// Update active position
		if (status.active_position) {
			updatePosition(status.active_position);
		} else if (status.active_position === null) {
			clearPosition();
		}

		// Update stats
		if (status.stats) {
			updateStats(status.stats);
		}

		// Update trade history
		if (status.trade_history) {
			setTradeHistory(status.trade_history);
		}

		// Update top pairs
		if (status.top_pairs) {
			updateTopPairs(status.top_pairs);
		}
	});

	return socket;
}

/**
 * Envoyer événement au serveur
 */
export function emit(event, data) {
	if (socket) {
		socket.emit(event, data);
	}
}

/**
 * Déconnecter Socket.IO
 */
export function disconnect() {
	if (socket) {
		socket.disconnect();
		socket = null;
	}
}

/**
 * Getter pour accès direct au socket
 */
export function getSocket() {
	return socket;
}

// 🔥 REMPLACEMENT: WebSocket natif utilisé maintenant
// Auto-init désactivé - utiliser websocket.js à la place
// if (browser) {
// 	initSocket();
// }
