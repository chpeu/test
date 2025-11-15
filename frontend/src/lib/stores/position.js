/**
 * Store Svelte pour la position active
 * Synchronisé automatiquement avec WebSocket natif
 */
import { writable, derived } from 'svelte/store';

function getDecimalsFromTickSize(tickSize) {
	if (!tickSize || tickSize <= 0) return null;
	const str = tickSize.toString();
	if (str.includes('e') || str.includes('E')) {
		const exponent = parseInt(str.split('e')[1]);
		if (!Number.isNaN(exponent) && exponent < 0) {
			return Math.abs(exponent);
		}
	}
	if (str.includes('.')) {
		return str.split('.')[1].length;
	}
	if (tickSize < 1) {
		let decimals = 0;
		let value = tickSize;
		while (value < 1 && decimals < 20) {
			value *= 10;
			decimals++;
		}
		return decimals;
	}
	return 0;
}

function resolvePriceDecimals(position) {
	if (!position) return null;
	const directPrecision = position.price_precision ?? position.pricePrecision;
	if (typeof directPrecision === 'number') {
		return directPrecision;
	}
	const tickSize = position.tickSize ?? position.tick_size;
	if (typeof tickSize === 'number') {
		return getDecimalsFromTickSize(tickSize);
	}
	return null;
}

function roundWithPrecision(value, decimals) {
	if (decimals === null || decimals === undefined) return value;
	if (value === null || value === undefined || typeof value !== 'number') {
		return value;
	}
	return Number(value.toFixed(decimals));
}

function normalizePositionPrecision(position) {
	if (!position) return position;
	const decimals = resolvePriceDecimals(position);
	if (decimals === null || decimals === undefined) {
		return position;
	}
	return {
		...position,
		price_precision: decimals,
		entry: roundWithPrecision(position.entry, decimals),
		current_price: roundWithPrecision(position.current_price, decimals),
		tp: roundWithPrecision(position.tp, decimals),
		sl: roundWithPrecision(position.sl, decimals)
	};
}

// Position active (null si aucune)
export const activePosition = writable(null);

// Computed: PnL color
export const pnlColor = derived(activePosition, $pos => {
	if (!$pos || $pos.pnl === undefined) return '#888';
	return $pos.pnl >= 0 ? '#00ff88' : '#ff4444';
});

// Computed: SL distance (toujours positif, indique la distance en %)
export const slDistance = derived(activePosition, $pos => {
	if (!$pos || !$pos.sl || !$pos.current_price) return null;
	// 🔥 FIX BUG: Calcul absolu de la distance, pas de signe négatif
	const distance = Math.abs((($pos.sl - $pos.current_price) / $pos.current_price) * 100);
	return distance.toFixed(2);
});

// Computed: TP distance (toujours positif, indique la distance en %)
export const tpDistance = derived(activePosition, $pos => {
	if (!$pos || !$pos.tp || !$pos.current_price) return null;
	// 🔥 FIX BUG: Calcul absolu de la distance, pas de signe négatif
	const distance = Math.abs((($pos.tp - $pos.current_price) / $pos.current_price) * 100);
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
	// 🔥 DEBUG: Log pour diagnostiquer le problème de précision
	console.log('📥 updatePosition reçu:', {
		symbol: data?.symbol,
		entry: data?.entry,
		current_price: data?.current_price,
		price_precision: data?.price_precision,
		tickSize: data?.tickSize || data?.tick_size
	});
	const normalized = normalizePositionPrecision(data);
	console.log('📤 updatePosition normalisé:', {
		symbol: normalized?.symbol,
		entry: normalized?.entry,
		current_price: normalized?.current_price,
		price_precision: normalized?.price_precision
	});
	activePosition.set(normalized);
}

export function clearPosition() {
	activePosition.set(null);
}

export function updatePositionPrice(price) {
	activePosition.update($pos => {
		if (!$pos) return $pos;
		const decimals = resolvePriceDecimals($pos);
		return { ...$pos, current_price: roundWithPrecision(price, decimals) };
	});
}
