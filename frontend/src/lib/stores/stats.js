/**
 * Store Svelte pour les statistiques de session
 * Auto-calculées via derived stores
 */
import { writable, derived } from 'svelte/store';
import { tradeHistory } from './trades';

// Stats brutes (mises à jour par le backend)
const backendStats = writable({
	wins: 0,
	losses: 0,
	total_trades: 0,
	total_pnl_usdt: 0,
	total_pnl_pct: 0,
	best_trade: null,
	worst_trade: null,
	avg_trade_duration: 0
});

// 🔥 FIX: Calculer les stats depuis les trades du frontend pour garantir la cohérence
// Cela garantit que les stats correspondent exactement aux trades visibles
export const stats = derived([tradeHistory, backendStats], ([$trades, $backendStats]) => {
	if ($trades.length === 0) {
		// Si pas de trades, utiliser les stats du backend (pour les autres métriques)
		return $backendStats;
	}

	// Calculer depuis les trades du frontend
	const total = $trades.length;
	const wins = $trades.filter(t => (t.net_pnl_usdt || t.pnl_usdt || 0) > 0).length;
	const losses = total - wins;
	
	// Calculer PnL total depuis les trades
	const total_pnl_usdt = $trades.reduce((sum, t) => sum + (t.net_pnl_usdt || t.pnl_usdt || 0), 0);
	const total_pnl_pct = $trades.reduce((sum, t) => sum + (t.net_pnl_pct || t.pnl_pct || 0), 0);
	
	// Trouver best/worst trade
	const best_trade = $trades.reduce((best, t) => {
		const pnl = t.net_pnl_usdt || t.pnl_usdt || 0;
		const bestPnl = best ? (best.net_pnl_usdt || best.pnl_usdt || 0) : -Infinity;
		return pnl > bestPnl ? t : best;
	}, null);
	
	const worst_trade = $trades.reduce((worst, t) => {
		const pnl = t.net_pnl_usdt || t.pnl_usdt || 0;
		const worstPnl = worst ? (worst.net_pnl_usdt || worst.pnl_usdt || 0) : Infinity;
		return pnl < worstPnl ? t : worst;
	}, null);
	
	// Calculer durée moyenne
	const durations = $trades.map(t => t.duration_seconds || 0).filter(d => d > 0);
	const avg_duration = durations.length > 0 ? durations.reduce((sum, d) => sum + d, 0) / durations.length : 0;

	return {
		wins,
		losses,
		total_trades: total,
		total_pnl_usdt: round(total_pnl_usdt, 4),
		total_pnl_pct: round(total_pnl_pct, 4),
		best_trade,
		worst_trade,
		avg_trade_duration: round(avg_duration, 2)
	};
});

// Helper pour arrondir
function round(value, decimals) {
	return Math.round(value * Math.pow(10, decimals)) / Math.pow(10, decimals);
}

// Computed: Winrate
export const winrate = derived(stats, $stats => {
	if ($stats.total_trades === 0) return '0.00';
	const winrateValue = ($stats.wins / $stats.total_trades) * 100;
	return winrateValue.toFixed(2);
});

// Computed: Win/Loss ratio
export const winLossRatio = derived(stats, $stats => {
	if ($stats.losses === 0) return $stats.wins > 0 ? '∞' : '0.00';
	const ratio = $stats.wins / $stats.losses;
	return ratio.toFixed(2);
});

// Computed: Average PnL per trade
export const avgPnl = derived(stats, $stats => {
	if ($stats.total_trades === 0) return 0;
	return ($stats.total_pnl_usdt / $stats.total_trades).toFixed(2);
});

// Computed: Profit Factor (Somme profits / |Somme pertes|)
export const profitFactor = derived(tradeHistory, $trades => {
	if ($trades.length === 0) return '0.00';

	// 🔥 FIX BUG CRITIQUE: Profit Factor = Σ(profits) / |Σ(losses)|
	// Ancienne formule incorrecte: (wins × best_trade) / (losses × worst_trade)
	const grossProfit = $trades
		.filter(t => (t.net_pnl_usdt || t.pnl_usdt || 0) > 0)
		.reduce((sum, t) => sum + (t.net_pnl_usdt || t.pnl_usdt || 0), 0);

	const grossLoss = Math.abs($trades
		.filter(t => (t.net_pnl_usdt || t.pnl_usdt || 0) < 0)
		.reduce((sum, t) => sum + (t.net_pnl_usdt || t.pnl_usdt || 0), 0));

	if (grossLoss === 0) return grossProfit > 0 ? '∞' : '0.00';
	return (grossProfit / grossLoss).toFixed(2);
});

// Actions
export function updateStats(newStats) {
	// Mettre à jour backendStats (utilisé comme fallback si pas de trades)
	backendStats.set(newStats);
}

// 🔥 REMOVED: incrementWin et incrementLoss ne sont plus nécessaires
// Les stats sont maintenant calculées automatiquement depuis tradeHistory via le derived store

export function resetStats() {
	backendStats.set({
		wins: 0,
		losses: 0,
		total_trades: 0,
		total_pnl_usdt: 0,
		total_pnl_pct: 0,
		best_trade: null,
		worst_trade: null,
		avg_trade_duration: 0
	});
}

// 🔥 FIX: Reset des stats de session (alias pour resetStats)
export function resetSessionStats() {
	resetStats();
}