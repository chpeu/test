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
	// 🔥 FIX: S'assurer que le trade a un ID unique
	const tradeWithId = {
		...trade,
		id: trade.id || `${trade.symbol}_${trade.closed_at || trade.opened_at}_${Date.now()}_${Math.random()}`
	};
	tradeHistory.update($trades => [tradeWithId, ...$trades]);
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
	// 🔥 FIX: S'assurer que chaque trade a un ID unique
	const tradesWithIds = trades.map((trade, index) => ({
		...trade,
		id: trade.id || `${trade.symbol}_${trade.closed_at || trade.opened_at}_${index}_${Date.now()}`
	}));
	tradeHistory.set(tradesWithIds);
}
