/**
 * Store Svelte pour l'historique des trades
 * Tri automatique et statistiques
 */
import { writable, derived } from 'svelte/store';

// Trade history array
export const tradeHistory = writable([]);

// Computed: Sorted by date (most recent first)
export const sortedTrades = derived(tradeHistory, $trades =>
	[...$trades].sort((a, b) => new Date(b.closed_at) - new Date(a.closed_at))
);

// Computed: Winning trades only
export const winningTrades = derived(tradeHistory, $trades =>
	$trades.filter(t => t.net_pnl_usdt > 0)
);

// Computed: Losing trades only
export const losingTrades = derived(tradeHistory, $trades =>
	$trades.filter(t => t.net_pnl_usdt <= 0)
);

// Computed: Today's trades
export const todayTrades = derived(tradeHistory, $trades => {
	const today = new Date().toDateString();
	return $trades.filter(t => {
		const tradeDate = new Date(t.closed_at).toDateString();
		return tradeDate === today;
	});
});

// Computed: PnL chart data (last 20 trades)
export const pnlChartData = derived(sortedTrades, $trades => {
	const last20 = $trades.slice(0, 20).reverse();
	return {
		labels: last20.map((t, i) => `#${i + 1}`),
		values: last20.map(t => t.net_pnl_usdt || 0),
		colors: last20.map(t => t.net_pnl_usdt >= 0 ? '#00ff88' : '#ff4444')
	};
});

// Actions
export function addTrade(trade) {
	const fallbackId = trade?.id || trade?.trade_id || trade?.closure_id || `${trade.symbol}_${trade.closed_at || trade.opened_at || trade.timestamp || ''}`;
	const tradeWithId = { ...trade, id: fallbackId };
	tradeHistory.update($trades => {
		const idx = $trades.findIndex(t => t.id === tradeWithId.id);
		if (idx >= 0) {
			const copy = [...$trades];
			copy[idx] = { ...copy[idx], ...tradeWithId };
			return copy;
		}
		return [tradeWithId, ...$trades];
	});
}

export function updateTrade(tradeId, updates) {
	tradeHistory.update($trades =>
		$trades.map(t => t.id === tradeId ? { ...t, ...updates } : t)
	);
}

export function clearHistory() {
	tradeHistory.set([]);
}

export function setTradeHistory(trades) {
	const tradesWithIds = trades.map((trade, index) => ({
		...trade,
		id: trade?.id || trade?.trade_id || trade?.closure_id || `${trade.symbol}_${trade.closed_at || trade.opened_at || trade.timestamp || ''}_${index}`
	}));
	// Dedup par id (garder la premiere occurrence)
	const seen = new Set();
	const deduped = [];
	for (const t of tradesWithIds) {
		if (!t.id || seen.has(t.id)) continue;
		seen.add(t.id);
		deduped.push(t);
	}
	tradeHistory.set(deduped);
}
