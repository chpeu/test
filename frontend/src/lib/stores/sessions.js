// Store pour la gestion des sessions multiples

import { writable, derived } from 'svelte/store';
import { browser } from '$app/environment';

// Toutes les sessions
export const sessions = writable([]);

// Session actuellement sélectionnée (ID)
export const activeSessionId = writable(null);

// Session active (dérivé)
export const activeSession = derived(
	[sessions, activeSessionId],
	([$sessions, $activeSessionId]) => {
		if (!$activeSessionId) return null;
		return $sessions.find(s => s.session_id === $activeSessionId) || null;
	}
);

// Stats globales de toutes les sessions
export const globalStats = writable({
	total_sessions: 0,
	running_sessions: 0,
	stopped_sessions: 0,
	paused_sessions: 0,
	total_trades: 0,
	total_pnl: 0,
	total_pnl_percent: 0,
	total_wins: 0,
	total_losses: 0,
	win_rate: 0
});

// Loading state
export const sessionsLoading = writable(false);

// Error state
export const sessionsError = writable(null);

// ============================================================================
// API Functions
// ============================================================================

/**
 * Charger toutes les sessions depuis l'API
 */
export async function loadSessions() {
	if (!browser) return;

	sessionsLoading.set(true);
	sessionsError.set(null);

	try {
		const res = await fetch('/api/sessions');
		const data = await res.json();

		if (data.error) {
			throw new Error(data.error);
		}

		sessions.set(data.sessions || []);

		// Si aucune session active et qu'il y a des sessions, sélectionner la première
		const currentActiveId = getActiveSessionId();
		if (!currentActiveId && data.sessions && data.sessions.length > 0) {
			activeSessionId.set(data.sessions[0].session_id);
		}

	} catch (error) {
		console.error('Error loading sessions:', error);
		sessionsError.set(error.message);
	} finally {
		sessionsLoading.set(false);
	}
}

/**
 * Charger les stats globales
 */
export async function loadGlobalStats() {
	if (!browser) return;

	try {
		const res = await fetch('/api/sessions/stats/global');
		const data = await res.json();

		if (!data.error) {
			globalStats.set(data);
		}
	} catch (error) {
		console.error('Error loading global stats:', error);
	}
}

/**
 * Créer une nouvelle session
 */
export async function createSession(sessionData) {
	if (!browser) return null;

	sessionsError.set(null);

	try {
		const res = await fetch('/api/sessions/create', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(sessionData)
		});

		const data = await res.json();

		if (data.error) {
			throw new Error(data.error);
		}

		// Recharger la liste des sessions
		await loadSessions();

		// Sélectionner la nouvelle session
		if (data.session) {
			activeSessionId.set(data.session.session_id);
		}

		return data.session;

	} catch (error) {
		console.error('Error creating session:', error);
		sessionsError.set(error.message);
		return null;
	}
}

/**
 * Démarrer une session
 */
export async function startSession(sessionId) {
	if (!browser) return false;

	try {
		const res = await fetch(`/api/sessions/${sessionId}/start`, {
			method: 'POST'
		});

		const data = await res.json();

		if (data.error) {
			throw new Error(data.error);
		}

		// Recharger les sessions
		await loadSessions();
		await loadGlobalStats();

		return true;

	} catch (error) {
		console.error('Error starting session:', error);
		sessionsError.set(error.message);
		return false;
	}
}

/**
 * Arrêter une session
 */
export async function stopSession(sessionId) {
	if (!browser) return false;

	try {
		const res = await fetch(`/api/sessions/${sessionId}/stop`, {
			method: 'POST'
		});

		const data = await res.json();

		if (data.error) {
			throw new Error(data.error);
		}

		// Recharger les sessions
		await loadSessions();
		await loadGlobalStats();

		return true;

	} catch (error) {
		console.error('Error stopping session:', error);
		sessionsError.set(error.message);
		return false;
	}
}

/**
 * Mettre en pause une session
 */
export async function pauseSession(sessionId) {
	if (!browser) return false;

	try {
		const res = await fetch(`/api/sessions/${sessionId}/pause`, {
			method: 'POST'
		});

		const data = await res.json();

		if (data.error) {
			throw new Error(data.error);
		}

		await loadSessions();
		return true;

	} catch (error) {
		console.error('Error pausing session:', error);
		sessionsError.set(error.message);
		return false;
	}
}

/**
 * Reprendre une session
 */
export async function resumeSession(sessionId) {
	if (!browser) return false;

	try {
		const res = await fetch(`/api/sessions/${sessionId}/resume`, {
			method: 'POST'
		});

		const data = await res.json();

		if (data.error) {
			throw new Error(data.error);
		}

		await loadSessions();
		return true;

	} catch (error) {
		console.error('Error resuming session:', error);
		sessionsError.set(error.message);
		return false;
	}
}

/**
 * Supprimer une session
 */
export async function deleteSession(sessionId) {
	if (!browser) return false;

	try {
		const res = await fetch(`/api/sessions/${sessionId}`, {
			method: 'DELETE'
		});

		const data = await res.json();

		if (data.error) {
			throw new Error(data.error);
		}

		// Si la session supprimée était active, désélectionner
		const currentActiveId = getActiveSessionId();
		if (currentActiveId === sessionId) {
			activeSessionId.set(null);
		}

		// Recharger les sessions
		await loadSessions();
		await loadGlobalStats();

		return true;

	} catch (error) {
		console.error('Error deleting session:', error);
		sessionsError.set(error.message);
		return false;
	}
}

/**
 * Sélectionner une session
 */
export function selectSession(sessionId) {
	activeSessionId.set(sessionId);

	// Persister dans localStorage
	if (browser) {
		localStorage.setItem('activeSessionId', sessionId);
	}
}

/**
 * Obtenir l'ID de la session active
 */
function getActiveSessionId() {
	let id = null;

	activeSessionId.subscribe(value => {
		id = value;
	})();

	return id;
}

// 🔥 BIDIRECTIONNEL: Plus de polling REST - Utiliser WebSocket pour mises à jour temps réel
// Les mises à jour seront déclenchées par les événements WebSocket dans les composants
