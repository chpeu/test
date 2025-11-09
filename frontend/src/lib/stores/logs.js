/**
 * Store Svelte pour les logs en temps réel
 * Auto-scrolling et limit des entrées
 */
import { writable, derived } from 'svelte/store';

const MAX_LOGS = 200;
const MAX_CONFIG_LOGS = 100;

// Logs array
export const logs = writable([]);

// Config change logs array (separate store)
export const configLogs = writable([]);

// Computed: Last 50 logs (pour affichage)
export const recentLogs = derived(logs, $logs => $logs.slice(-50));

// Computed: Last 50 config logs (pour affichage)
export const recentConfigLogs = derived(configLogs, $logs => $logs.slice(-50));

// Computed: Error logs only
export const errorLogs = derived(logs, $logs =>
	$logs.filter(log => log.level === 'ERROR' || log.level === 'CRITICAL')
);

// Computed: Error count
export const errorCount = derived(errorLogs, $errors => $errors.length);

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

export function clearConfigLogs() {
	configLogs.set([]);
}

export function filterLogsByLevel(level) {
	return derived(logs, $logs =>
		$logs.filter(log => log.level === level)
	);
}
