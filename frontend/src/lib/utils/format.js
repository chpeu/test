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
 * Calculate number of decimal places from tickSize
 * @param {number} tickSize - The tick size (e.g., 0.01, 0.0001, 0.000001)
 * @returns {number} Number of decimal places
 */
function getDecimalsFromTickSize(tickSize) {
	if (!tickSize || tickSize <= 0) return null;
	
	// Convert to string to handle scientific notation
	const str = tickSize.toString();
	
	// If in scientific notation (e.g., 1e-8)
	if (str.includes('e') || str.includes('E')) {
		const parts = str.toLowerCase().split('e');
		const exponent = parseInt(parts[1]);
		if (exponent < 0) {
			// Pour un tickSize de 1e-8, on veut 8 décimales
			return Math.abs(exponent);
		}
	}
	
	// Count decimal places from decimal notation
	if (str.includes('.')) {
		const decimalPart = str.split('.')[1];
		// Compter toutes les décimales, y compris les zéros
		// Exemple: 0.00000001 -> 8 décimales
		return decimalPart.length;
	}
	
	// Si pas de point décimal, essayer de calculer depuis la valeur
	// Pour un tickSize très petit, calculer le nombre de décimales nécessaires
	if (tickSize < 1) {
		// Multiplier par 10 jusqu'à obtenir un entier >= 1
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

/**
 * Format a price with adaptive decimals based on value or precision from API
 * @param {number} price - The price to format
 * @param {number|object} precision - Optional: number of decimals, or object with {pricePrecision, tickSize}
 * @returns {string} Formatted price
 */
export function formatPrice(price, precision = null) {
	if (price === null || price === undefined || isNaN(price)) {
		return '0.00';
	}

	const num = Number(price);
	
	// If precision is provided, use it
	if (precision !== null && precision !== undefined) {
		let decimals;
		
		// If precision is an object with pricePrecision or tickSize
		if (typeof precision === 'object') {
			if (precision.pricePrecision !== undefined && precision.pricePrecision !== null) {
				decimals = precision.pricePrecision;
			} else if (precision.tickSize !== undefined && precision.tickSize !== null) {
				decimals = getDecimalsFromTickSize(precision.tickSize);
			} else if (precision.decimals !== undefined && precision.decimals !== null) {
				decimals = precision.decimals;
			}
		} else if (typeof precision === 'number') {
			decimals = precision;
		}
		
		// Use the calculated decimals if available
		if (decimals !== null && decimals !== undefined && decimals >= 0) {
			return num.toFixed(decimals);
		}
	}

	// Fallback: adaptive decimals based on value (comportement similaire au backend)
	// Pour les très petits prix, utiliser plus de décimales (jusqu'à 10 comme le backend)
	if (num < 0.01 && num > 0) {
		// Formater avec 10 décimales puis supprimer les zéros de fin
		let formatted = num.toFixed(10);
		// Supprimer les zéros de fin mais garder au moins 6 décimales
		formatted = formatted.replace(/0+$/, '');
		if (formatted.endsWith('.')) {
			formatted = formatted.slice(0, -1);
		}
		// S'assurer qu'on a au moins 6 décimales pour les très petits prix
		const decimalPart = formatted.includes('.') ? formatted.split('.')[1] : '';
		if (decimalPart.length < 6) {
			return num.toFixed(6);
		}
		return formatted;
	}

	// For small prices (< 1), use 4 decimals
	if (num < 1) {
		return num.toFixed(4);
	}
	
	// 🔥 FIX: Pour les prix moyens (1-1000), utiliser 4 décimales pour préserver la précision
	// Exemple: 664.75 doit afficher "664.7500" ou mieux "664.75" sans arrondir à "665"
	if (num < 1000) {
		// Formater avec 4 décimales puis supprimer les zéros de fin
		let formatted = num.toFixed(4);
		// Supprimer les zéros de fin mais garder au moins 2 décimales
		// 🔥 FIX: Regex corrigée pour ne pas supprimer tous les chiffres
		formatted = formatted.replace(/\.?0+$/, '');
		// Si plus de point décimal, ajouter .00
		if (!formatted.includes('.')) {
			formatted += '.00';
		} else {
			// S'assurer d'avoir au moins 2 décimales
			const decimalPart = formatted.split('.')[1];
			if (decimalPart.length < 2) {
				formatted += '0'.repeat(2 - decimalPart.length);
			}
		}
		return formatted;
	}

	// For large prices (>= 1000), use 2 decimals
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
