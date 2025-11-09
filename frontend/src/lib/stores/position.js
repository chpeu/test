/**
 * Store Svelte pour la position active
 * Synchronisé automatiquement avec WebSocket natif
 */
import { writable, derived } from 'svelte/store';

// Position active (null si aucune)
export const activePosition = writable(null);

// Computed: PnL color
export const pnlColor = derived(activePosition, $pos => {
	if (!$pos || $pos.pnl === undefined) return '#888';
	return $pos.pnl >= 0 ? '#00ff88' : '#ff4444';
});

// Computed: SL distance
export const slDistance = derived(activePosition, $pos => {
	if (!$pos || !$pos.sl || !$pos.current_price) return null;
	const distance = (($pos.sl - $pos.current_price) / $pos.current_price) * 100;
	return distance.toFixed(2);
});

// Computed: TP distance
export const tpDistance = derived(activePosition, $pos => {
	if (!$pos || !$pos.tp || !$pos.current_price) return null;
	const distance = (($pos.tp - $pos.current_price) / $pos.current_price) * 100;
	return distance.toFixed(2);
});

// Computed: Position opened duration
export const positionDuration = derived(activePosition, $pos => {
	if (!$pos || !$pos.opened_at) return null;
	const now = new Date();
	const opened = new Date($pos.opened_at);
	const diffMs = now - opened;
	const diffSec = Math.floor(diffMs / 1000);

	if (diffSec < 60) return `${diffSec}s`;
	if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ${diffSec % 60}s`;
	return `${Math.floor(diffSec / 3600)}h ${Math.floor((diffSec % 3600) / 60)}m`;
});

// Actions
export function updatePosition(data) {
	activePosition.set(data);
}

export function clearPosition() {
	activePosition.set(null);
}

export function updatePositionPrice(price) {
	activePosition.update($pos => {
		if (!$pos) return $pos;
		return { ...$pos, current_price: price };
	});
}
