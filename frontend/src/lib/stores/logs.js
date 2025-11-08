/**
 * Store Svelte pour les logs en temps réel
 * Auto-scrolling et limit des entrées
 */
import { writable, derived } from 'svelte/store';

const MAX_LOGS = 200;

// Logs array
export const logs = writable([]);

// Computed: Last 50 logs (pour affichage)
export const recentLogs = derived(logs, $logs => $logs.slice(-50));

// Computed: Error logs only
export const errorLogs = derived(logs, $logs =>
	$logs.filter(log => log.level === 'ERROR' || log.level === 'CRITICAL')
);

// Computed: Error count
export const errorCount = derived(errorLogs, $errors => $errors.length);

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
}

export function clearLogs() {
	logs.set([]);
}

export function filterLogsByLevel(level) {
	return derived(logs, $logs =>
		$logs.filter(log => log.level === level)
	);
}
