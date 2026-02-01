import { writable, derived } from 'svelte/store';

const LOG_MODES = ['logs', 'quiet', 'debug'];

export const logMode = writable('logs');
export const quietMode = derived(logMode, $mode => $mode === 'quiet');

export function setLogMode(mode) {
	const normalized = String(mode || '').toLowerCase();
	logMode.set(LOG_MODES.includes(normalized) ? normalized : 'logs');
}

export function setQuietMode(enabled) {
	setLogMode(enabled ? 'quiet' : 'logs');
}
