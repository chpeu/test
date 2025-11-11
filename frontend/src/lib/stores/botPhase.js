/**
 * Store Svelte pour suivre la phase en cours du bot
 * Phases possibles:
 * - "arrêt" : Bot arrêté
 * - "scan_scalability" : Scan des paires scalables
 * - "scan_setups" : Scan des setups
 * - "position_active" : Position en cours
 * - "pause" : Bot en pause
 */
import { writable } from 'svelte/store';

// Phase actuelle du bot
export const botPhase = writable('arrêt');

// Messages associés à chaque phase
export const phaseMessages = {
	'arrêt': '💤 Bot arrêté',
	'scan_scalability': '🔍 Scan des paires scalables',
	'scan_setups': '📊 Scan des setups',
	'position_active': '💰 Position en cours',
	'pause': '⏸️ Pause'
};

// Actions
export function setBotPhase(phase) {
	if (phaseMessages[phase]) {
		botPhase.set(phase);
	} else {
		console.warn(`⚠️ Phase inconnue: ${phase}`);
	}
}

export function getPhaseMessage(phase) {
	return phaseMessages[phase] || '❓ Phase inconnue';
}

