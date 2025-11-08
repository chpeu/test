/**
 * Utilitaire pour les notifications push desktop
 * Compatible Chrome, Firefox, Safari, Edge
 */
import { writable } from 'svelte/store';
import { browser } from '$app/environment';

// Store pour l'état des notifications
export const notificationsEnabled = writable(false);
export const notificationPermission = writable('default');

/**
 * Demander permission utilisateur pour notifications
 */
export async function requestNotificationPermission() {
	if (!browser || !('Notification' in window)) {
		console.warn('Notifications not supported in this browser');
		return false;
	}

	try {
		const permission = await Notification.requestPermission();
		notificationPermission.set(permission);

		if (permission === 'granted') {
			notificationsEnabled.set(true);
			// Sauvegarder préférence
			localStorage.setItem('notifications_enabled', 'true');
			return true;
		} else {
			notificationsEnabled.set(false);
			localStorage.setItem('notifications_enabled', 'false');
			return false;
		}
	} catch (error) {
		console.error('Error requesting notification permission:', error);
		return false;
	}
}

/**
 * Envoyer notification desktop
 */
export function sendNotification(title, options = {}) {
	if (!browser || !('Notification' in window)) {
		return;
	}

	// Vérifier permission
	if (Notification.permission !== 'granted') {
		return;
	}

	// Vérifier si activé
	const enabled = localStorage.getItem('notifications_enabled') === 'true';
	if (!enabled) {
		return;
	}

	// Créer notification
	const notification = new Notification(title, {
		icon: '/icon-192.png',
		badge: '/badge-72.png',
		vibrate: [200, 100, 200],
		requireInteraction: false,
		...options
	});

	// Auto-close après 5 secondes
	setTimeout(() => {
		notification.close();
	}, 5000);

	return notification;
}

/**
 * Notifications prédéfinies
 */

export function notifyPositionOpened(position) {
	const emoji = position.direction === 'LONG' ? '🟢' : '🔴';
	sendNotification(`${emoji} Position Ouverte`, {
		body: `${position.symbol} ${position.direction}\nEntry: ${position.entry}\nSize: ${position.size} USDT`,
		tag: 'position-opened'
	});
}

export function notifyPositionClosed(result) {
	const emoji = result.net_pnl_usdt >= 0 ? '🎉' : '😢';
	const pnlPct = result.net_pnl_pct || 0;
	const pnlUsdt = result.net_pnl_usdt || 0;
	const pnlSign = pnlPct >= 0 ? '+' : '';

	sendNotification(`${emoji} Position Fermée`, {
		body: `${result.symbol} - ${result.reason}\nPnL: ${pnlSign}${pnlPct.toFixed(2)}% (${pnlSign}${pnlUsdt.toFixed(2)} USDT)`,
		tag: 'position-closed',
		requireInteraction: true // Reste affichée jusqu'à clic
	});
}

export function notifySetupFound(setup) {
	sendNotification('🔍 Setup Détecté', {
		body: `${setup.symbol} ${setup.direction}\nScore: ${setup.score}\nConditions: ${setup.confirmed_by}`,
		tag: 'setup-found'
	});
}

export function notifyError(message) {
	sendNotification('❌ Erreur', {
		body: message,
		tag: 'error',
		requireInteraction: true
	});
}

export function notifyWinrate(winrate, total) {
	if (winrate >= 70 && total >= 10) {
		sendNotification('🏆 Excellent Winrate!', {
			body: `${winrate}% de réussite sur ${total} trades`,
			tag: 'milestone'
		});
	}
}

/**
 * Initialiser notifications au démarrage
 */
export function initNotifications() {
	if (!browser) return;

	// Charger préférence sauvegardée
	const enabled = localStorage.getItem('notifications_enabled') === 'true';
	notificationsEnabled.set(enabled);

	if ('Notification' in window) {
		notificationPermission.set(Notification.permission);
	}
}

/**
 * Toggle notifications on/off
 */
export function toggleNotifications() {
	if (!browser) return;

	const currentState = localStorage.getItem('notifications_enabled') === 'true';
	const newState = !currentState;

	if (newState && Notification.permission !== 'granted') {
		// Demander permission si pas encore accordée
		return requestNotificationPermission();
	}

	localStorage.setItem('notifications_enabled', String(newState));
	notificationsEnabled.set(newState);
	return Promise.resolve(newState);
}

// Auto-init
if (browser) {
	initNotifications();
}
