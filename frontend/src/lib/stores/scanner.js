/**
 * Store Svelte pour le scanner de top pairs
 * Gère l'état du scan et les paires détectées
 */
import { writable, derived } from 'svelte/store';

// Scanner state
export const isScanning = writable(false);
export const topPairs = writable([]);
export const scanProgress = writable(0);

// Computed: Top 10 pairs by score
export const top10Pairs = derived(topPairs, $pairs =>
	[...$pairs]
		.sort((a, b) => (b.score || 0) - (a.score || 0))
		.slice(0, 10)
);

// Computed: Pairs count
export const pairsCount = derived(topPairs, $pairs => $pairs.length);

// Computed: Average spread
export const avgSpread = derived(topPairs, $pairs => {
	if ($pairs.length === 0) return 0;
	const total = $pairs.reduce((sum, p) => sum + (p.spread_pct || 0), 0);
	return (total / $pairs.length).toFixed(4);
});

// Computed: Average volume
export const avgVolume = derived(topPairs, $pairs => {
	if ($pairs.length === 0) return 0;
	const total = $pairs.reduce((sum, p) => sum + (p.volume_usdt || 0), 0);
	return (total / $pairs.length).toFixed(0);
});

// Actions
export function startScanning() {
	isScanning.set(true);
	scanProgress.set(0);
}

export function stopScanning() {
	isScanning.set(false);
	scanProgress.set(100);
}

export function updateTopPairs(pairs) {
	topPairs.set(pairs);
}

export function updateScanProgress(progress) {
	scanProgress.set(progress);
}

export function clearTopPairs() {
	topPairs.set([]);
}
