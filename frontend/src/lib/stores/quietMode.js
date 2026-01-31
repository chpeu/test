import { writable } from 'svelte/store';

export const quietMode = writable(false);

export function setQuietMode(enabled) {
	quietMode.set(Boolean(enabled));
}
