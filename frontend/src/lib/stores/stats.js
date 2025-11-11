/**
 * Store Svelte pour les statistiques de session
 * Auto-calculées via derived stores
 */
import { writable, derived } from 'svelte/store';

// Stats brutes
export const stats = writable({
	wins: 0,
	losses: 0,
	total_trades: 0,
	total_pnl_usdt: 0,
	total_pnl_pct: 0,
	best_trade: null,
	worst_trade: null,
	avg_trade_duration: 0
});

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

// Computed: Profit Factor
export const profitFactor = derived(stats, $stats => {
	if (!$stats.best_trade || !$stats.worst_trade) return null;
	const grossProfit = $stats.wins * ($stats.best_trade?.pnl_usdt || 0);
	const grossLoss = Math.abs($stats.losses * ($stats.worst_trade?.pnl_usdt || 0));
	if (grossLoss === 0) return grossProfit > 0 ? '∞' : '0';
	return (grossProfit / grossLoss).toFixed(2);
});

// Actions
export function updateStats(newStats) {
	stats.set(newStats);
}

export function incrementWin(trade) {
	stats.update($stats => ({
		...$stats,
		wins: $stats.wins + 1,
		total_trades: $stats.total_trades + 1,
		total_pnl_usdt: $stats.total_pnl_usdt + (trade.net_pnl_usdt || trade.pnl_usdt || 0),
		total_pnl_pct: $stats.total_pnl_pct + (trade.net_pnl || trade.net_pnl_pct || trade.pnl_pct || 0),
		best_trade: !$stats.best_trade || (trade.net_pnl_usdt || trade.pnl_usdt || 0) > ($stats.best_trade.net_pnl_usdt || $stats.best_trade.pnl_usdt || 0)
			? trade
			: $stats.best_trade
	}));
}

export function incrementLoss(trade) {
	stats.update($stats => ({
		...$stats,
		losses: $stats.losses + 1,
		total_trades: $stats.total_trades + 1,
		total_pnl_usdt: $stats.total_pnl_usdt + (trade.net_pnl_usdt || trade.pnl_usdt || 0),
		total_pnl_pct: $stats.total_pnl_pct + (trade.net_pnl || trade.net_pnl_pct || trade.pnl_pct || 0),
		worst_trade: !$stats.worst_trade || (trade.net_pnl_usdt || trade.pnl_usdt || 0) < ($stats.worst_trade.net_pnl_usdt || $stats.worst_trade.pnl_usdt || 0)
			? trade
			: $stats.worst_trade
	}));
}

export function resetStats() {
	stats.set({
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