/**
 * Store Svelte pour le mode debug
 * Active l'affichage des noms de variables dans les tooltips
 */
import { writable } from 'svelte/store';
import { browser } from '$app/environment';

// Charger depuis localStorage
function loadDebugMode() {
	if (!browser) return false;
	const saved = localStorage.getItem('debugMode');
	return saved === 'true';
}

// Store principal
export const debugMode = writable(loadDebugMode());

// Sauvegarder dans localStorage à chaque changement
debugMode.subscribe(value => {
	if (browser) {
		localStorage.setItem('debugMode', String(value));
	}
});


