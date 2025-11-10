/**
 * Utility functions for formatting numbers and values
 */

/**
 * Format a number with adaptive decimal places
 * @param {number} value - The value to format
 * @param {number} minDecimals - Minimum decimal places
 * @param {number} maxDecimals - Maximum decimal places
 * @returns {string} Formatted value
 */
export function formatAdaptive(value, minDecimals = 2, maxDecimals = 4) {
	if (value === null || value === undefined || isNaN(value)) {
		return '0';
	}

	const num = Number(value);

	// For very small numbers, use more decimals
	if (Math.abs(num) < 0.001 && num !== 0) {
		return num.toFixed(maxDecimals + 2);
	}

	// For normal numbers
	if (Math.abs(num) < 1) {
		return num.toFixed(maxDecimals);
	}

	return num.toFixed(minDecimals);
}

/**
 * Format a spread percentage
 * @param {number} spread - The spread value
 * @returns {string} Formatted spread
 */
export function formatSpread(spread) {
	if (spread === null || spread === undefined || isNaN(spread)) {
		return '0.00';
	}
	return Number(spread).toFixed(4);
}

/**
 * Format a price with adaptive decimals based on value
 * @param {number} price - The price to format
 * @returns {string} Formatted price
 */
export function formatPrice(price) {
	if (price === null || price === undefined || isNaN(price)) {
		return '0.00';
	}

	const num = Number(price);

	// For very small prices (< 0.01), use more decimals
	if (num < 0.01 && num > 0) {
		return num.toFixed(6);
	}

	// For small prices (< 1), use 4 decimals
	if (num < 1) {
		return num.toFixed(4);
	}

	// For normal prices, use 2 decimals
	return num.toFixed(2);
}

/**
 * Format a percentage value
 * @param {number} percent - The percentage value
 * @returns {string} Formatted percentage
 */
export function formatPercent(percent) {
	if (percent === null || percent === undefined || isNaN(percent)) {
		return '0.00';
	}
	return Number(percent).toFixed(2);
}

/**
 * Format a volume value
 * @param {number} volume - The volume value
 * @returns {string} Formatted volume
 */
export function formatVolume(volume) {
	if (volume === null || volume === undefined || isNaN(volume)) {
		return '0';
	}

	const num = Number(volume);

	// Format with K, M, B suffixes
	if (num >= 1_000_000_000) {
		return (num / 1_000_000_000).toFixed(2) + 'B';
	}
	if (num >= 1_000_000) {
		return (num / 1_000_000).toFixed(2) + 'M';
	}
	if (num >= 1_000) {
		return (num / 1_000).toFixed(2) + 'K';
	}

	return num.toFixed(0);
}

/**
 * Format a USDT value
 * @param {number} value - The USDT value
 * @returns {string} Formatted USDT value
 */
export function formatUSDT(value) {
	if (value === null || value === undefined || isNaN(value)) {
		return '0.00';
	}

	const num = Number(value);

	// For very small values, use more decimals
	if (Math.abs(num) < 0.01 && num !== 0) {
		return num.toFixed(4);
	}

	// For normal values, use 2 decimals
	return num.toFixed(2);
}

/**
 * Format a PnL value with color indication
 * @param {number} pnl - The PnL value
 * @param {boolean} isPercent - Whether the value is a percentage
 * @returns {string} Formatted PnL
 */
export function formatPnL(pnl, isPercent = false) {
	if (pnl === null || pnl === undefined || isNaN(pnl)) {
		return isPercent ? '0.00%' : '$0.00';
	}

	const num = Number(pnl);
	const sign = num >= 0 ? '+' : '';
	const formatted = isPercent
		? num.toFixed(2) + '%'
		: '$' + num.toFixed(2);

	return sign + formatted;
}

/**
 * Format a duration in seconds to human readable format
 * @param {number} seconds - Duration in seconds
 * @returns {string} Formatted duration
 */
export function formatDuration(seconds) {
	if (seconds === null || seconds === undefined || isNaN(seconds)) {
		return '0s';
	}

	const num = Number(seconds);

	if (num < 60) {
		return num.toFixed(0) + 's';
	}

	const minutes = Math.floor(num / 60);
	const remainingSeconds = num % 60;

	if (minutes < 60) {
		return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
	}

	const hours = Math.floor(minutes / 60);
	const remainingMinutes = minutes % 60;

	return `${hours}h ${remainingMinutes}m`;
}

/**
 * Format a timestamp to local time
 * @param {number|string} timestamp - Unix timestamp or ISO string
 * @returns {string} Formatted time
 */
export function formatTime(timestamp) {
	if (!timestamp) {
		return '-';
	}

	const date = new Date(timestamp);

	if (isNaN(date.getTime())) {
		return '-';
	}

	return date.toLocaleTimeString('en-US', {
		hour: '2-digit',
		minute: '2-digit',
		second: '2-digit',
		hour12: false
	});
}

/**
 * Format a timestamp to local date and time
 * @param {number|string} timestamp - Unix timestamp or ISO string
 * @returns {string} Formatted date and time
 */
export function formatDateTime(timestamp) {
	if (!timestamp) {
		return '-';
	}

	const date = new Date(timestamp);

	if (isNaN(date.getTime())) {
		return '-';
	}

	return date.toLocaleString('en-US', {
		year: 'numeric',
		month: '2-digit',
		day: '2-digit',
		hour: '2-digit',
		minute: '2-digit',
		second: '2-digit',
		hour12: false
	});
}
