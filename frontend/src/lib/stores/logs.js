/**
 * Store Svelte pour les logs en temps réel
 * Auto-scrolling et limit des entrées
 */
import { writable, derived } from 'svelte/store';

const MAX_LOGS = 200;
const MAX_CONFIG_LOGS = 100;

// Logs array (pour les logs normaux via WebSocket)
export const logs = writable([]);

// Config change logs array (separate store)
export const configLogs = writable([]);

// 🔥 NEW: Store séparé pour l'historique complet des erreurs persistantes
export const persistentErrors = writable([]);
export const persistentErrorsLoading = writable(false);
export const persistentErrorsCount = writable(0);

// Computed: Last 50 logs (pour affichage)
export const recentLogs = derived(logs, $logs => $logs.slice(-50));

// Computed: Last 50 config logs (pour affichage)
export const recentConfigLogs = derived(configLogs, $logs => $logs.slice(-50));

// Computed: Error logs - utilise les erreurs persistantes au lieu de logs WebSocket
export const errorLogs = derived(persistentErrors, $errors => $errors || []);

// Computed: Error count - utilise le store persistant
export const errorCount = derived(persistentErrorsCount, $count => $count);

// Computed: Config changes count
export const configChangesCount = derived(configLogs, $configLogs => $configLogs.length);

// Actions
export function addLog(logEntry) {
	logs.update($logs => {
		const newLogs = [...$logs, {
			...logEntry,
			timestamp: logEntry.timestamp || new Date().toISOString(),
			id: `${Date.now()}-${Math.random()}`
		}];

		// Keep only last MAX_LOGS
		if (newLogs.length > MAX_LOGS) {
			return newLogs.slice(-MAX_LOGS);
		}
		return newLogs;
	});
	
	// 🔥 NEW: Si c'est une erreur, rafraîchir l'historique persistant
	if (logEntry.level === 'ERROR' || logEntry.level === 'CRITICAL') {
		loadRecentErrors();
	}
}

export function clearLogs() {
	logs.set([]);
}

export function addConfigLog(configLogEntry) {
	configLogs.update($logs => {
		const newLogs = [...$logs, {
			...configLogEntry,
			timestamp: configLogEntry.timestamp || new Date().toISOString(),
			id: `${Date.now()}-${Math.random()}`
		}];

		// Keep only last MAX_CONFIG_LOGS
		if (newLogs.length > MAX_CONFIG_LOGS) {
			return newLogs.slice(-MAX_CONFIG_LOGS);
		}
		return newLogs;
	});
}

// 🔥 NEW: Fonctions pour charger l'historique persistant des erreurs
export async function loadAllErrors(limit = null, offset = 0) {
	persistentErrorsLoading.set(true);
	try {
		const params = new URLSearchParams();
		if (limit) params.append('limit', limit.toString());
		if (offset > 0) params.append('offset', offset.toString());
		
		const response = await fetch(`/api/logs/errors?${params}`);
		const data = await response.json();
		
		if (data.success) {
			persistentErrors.set(data.errors);
			persistentErrorsCount.set(data.total_count);
		} else {
			console.error('Erreur chargement erreurs:', data.error);
		}
	} catch (error) {
		console.error('Erreur chargement erreurs:', error);
	} finally {
		persistentErrorsLoading.set(false);
	}
}

export async function loadMoreErrors(currentCount) {
	persistentErrorsLoading.set(true);
	try {
		const response = await fetch(`/api/logs/errors?limit=50&offset=${currentCount}`);
		const data = await response.json();
		
		if (data.success) {
			// Ajouter les nouvelles erreurs à la liste existante
			persistentErrors.update($errors => [...$errors, ...data.errors]);
			persistentErrorsCount.set(data.total_count);
		} else {
			console.error('Erreur chargement plus d\'erreurs:', data.error);
		}
	} catch (error) {
		console.error('Erreur chargement plus d\'erreurs:', error);
	} finally {
		persistentErrorsLoading.set(false);
	}
}

export async function loadRecentErrors(limit = 50) {
	try {
		const response = await fetch(`/api/logs/errors/recent?limit=${limit}`);
		const data = await response.json();
		
		if (data.success) {
			persistentErrors.set(data.errors);
		}
	} catch (error) {
		console.error('Erreur chargement erreurs récentes:', error);
	}
}

export async function clearAllErrors() {
	try {
		const response = await fetch('/api/logs/errors/clear', {
			method: 'POST'
		});
		const data = await response.json();
		
		if (data.success) {
			persistentErrors.set([]);
			persistentErrorsCount.set(0);
		} else {
			console.error('Erreur vidage erreurs:', data.error);
		}
	} catch (error) {
		console.error('Erreur vidage erreurs:', error);
	}
}

// 🔥 NEW: Charger les erreurs récentes au démarrage (avec délai pour laisser le backend démarrer)
const INITIAL_ERRORS_LOAD_DELAY_MS = 8000;
if (typeof window !== 'undefined') {
	setTimeout(() => {
		loadRecentErrors();
	}, INITIAL_ERRORS_LOAD_DELAY_MS);
}

export function clearConfigLogs() {
	configLogs.set([]);
}

export function filterLogsByLevel(level) {
	return derived(logs, $logs =>
		$logs.filter(log => log.level === level)
	);
}
