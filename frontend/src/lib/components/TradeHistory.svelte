<script>
	import { sortedTrades } from '$lib/stores/trades';

	function formatDate(dateStr) {
		if (!dateStr) return '';
		const date = new Date(dateStr);
		return date.toLocaleString('fr-FR', {
			day: '2-digit',
			month: '2-digit',
			year: 'numeric',
			hour: '2-digit',
			minute: '2-digit',
			second: '2-digit'
		});
	}

	function formatNumber(num, decimals = 2) {
		if (num === null || num === undefined) return '0.00';
		return Number(num).toFixed(decimals);
	}

	function formatDuration(openedAt, closedAt) {
		if (!openedAt || !closedAt) return 'N/A';
		const diff = new Date(closedAt) - new Date(openedAt);
		const seconds = Math.floor(diff / 1000);
		const minutes = Math.floor(seconds / 60);
		const hours = Math.floor(minutes / 60);

		if (hours > 0) return `${hours}h ${minutes % 60}m`;
		if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
		return `${seconds}s`;
	}
</script>

<div class="trade-history">
	<div class="history-header">
		<h3>📜 Historique des Trades</h3>
		<div class="total-count">{$sortedTrades.length} trades</div>
	</div>

	{#if $sortedTrades.length === 0}
		<div class="no-trades">
			<div class="no-trades-icon">📊</div>
			<div class="no-trades-text">Aucun trade pour le moment</div>
		</div>
	{:else}
		<div class="table-container">
			<table class="trades-table">
				<thead>
					<tr>
						<th>Timestamp</th>
						<th>Symbol</th>
						<th>Direction</th>
						<th>Entry</th>
						<th>Exit</th>
						<th>Size (USDT)</th>
						<th>PnL %</th>
						<th>PnL USDT</th>
						<th>Reason</th>
						<th>Duration</th>
						<th>Signals</th>
					</tr>
				</thead>
				<tbody>
					{#each $sortedTrades as trade (trade.id || `${trade.symbol}_${trade.closed_at}`)}
						<tr class:win={trade.net_pnl_usdt >= 0} class:loss={trade.net_pnl_usdt < 0}>
							<td class="timestamp">{formatDate(trade.closed_at)}</td>
							<td class="symbol">{trade.symbol}</td>
							<td class="direction">
								<span class:long={trade.direction === 'LONG'} class:short={trade.direction === 'SHORT'}>
									{trade.direction}
								</span>
							</td>
							<td class="price">{formatNumber(trade.entry, 6)}</td>
							<td class="price">{formatNumber(trade.exit_price, 6)}</td>
							<td class="size">{formatNumber(trade.size, 2)}</td>
							<td class="pnl-pct" class:positive={trade.net_pnl_pct >= 0} class:negative={trade.net_pnl_pct < 0}>
								{trade.net_pnl_pct >= 0 ? '+' : ''}{formatNumber(trade.net_pnl_pct, 2)}%
							</td>
							<td class="pnl-usdt" class:positive={trade.net_pnl_usdt >= 0} class:negative={trade.net_pnl_usdt < 0}>
								{trade.net_pnl_usdt >= 0 ? '+' : ''}{formatNumber(trade.net_pnl_usdt, 2)}
							</td>
							<td class="reason">{trade.reason || 'N/A'}</td>
							<td class="duration">{formatDuration(trade.opened_at, trade.closed_at)}</td>
							<td class="signals">{trade.confirmed_by || 'N/A'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>

<style>
	.trade-history {
		background: #1e2749;
		border-radius: 12px;
		padding: 20px;
		border: 2px solid #2a3a6b;
	}

	.history-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 20px;
		padding-bottom: 15px;
		border-bottom: 2px solid #2a3a6b;
	}

	.history-header h3 {
		font-size: 20px;
		color: #00ff88;
		font-weight: bold;
		margin: 0;
	}

	.total-count {
		background: rgba(0, 170, 255, 0.2);
		color: #00aaff;
		padding: 6px 14px;
		border-radius: 12px;
		font-size: 12px;
		font-weight: bold;
		border: 1px solid #00aaff;
	}

	.no-trades {
		text-align: center;
		padding: 60px 20px;
	}

	.no-trades-icon {
		font-size: 64px;
		margin-bottom: 15px;
		opacity: 0.5;
	}

	.no-trades-text {
		font-size: 14px;
		color: #888;
	}

	.table-container {
		overflow-x: auto;
		background: #0a0e27;
		border-radius: 8px;
		padding: 15px;
	}

	.trades-table {
		width: 100%;
		border-collapse: collapse;
		font-family: 'Courier New', monospace;
		font-size: 12px;
	}

	.trades-table thead {
		background: rgba(0, 255, 136, 0.1);
		border-bottom: 2px solid #00ff88;
	}

	.trades-table th {
		padding: 12px 10px;
		text-align: left;
		font-weight: bold;
		color: #00ff88;
		text-transform: uppercase;
		font-size: 11px;
		letter-spacing: 0.5px;
		border-bottom: 2px solid #00ff88;
	}

	.trades-table tbody tr {
		border-bottom: 1px solid #2a3a6b;
		transition: all 0.2s;
	}

	.trades-table tbody tr:hover {
		background: rgba(0, 255, 136, 0.05);
	}

	.trades-table tbody tr.win {
		border-left: 4px solid #00ff88;
	}

	.trades-table tbody tr.loss {
		border-left: 4px solid #ff4444;
	}

	.trades-table td {
		padding: 10px;
		color: #fff;
	}

	.timestamp {
		color: #888;
		font-size: 11px;
		white-space: nowrap;
	}

	.symbol {
		font-weight: bold;
		color: #fff;
	}

	.direction span {
		padding: 4px 8px;
		border-radius: 4px;
		font-weight: bold;
		font-size: 11px;
	}

	.direction .long {
		background: rgba(0, 255, 136, 0.2);
		color: #00ff88;
		border: 1px solid #00ff88;
	}

	.direction .short {
		background: rgba(255, 68, 68, 0.2);
		color: #ff4444;
		border: 1px solid #ff4444;
	}

	.price {
		font-family: 'Courier New', monospace;
		color: #00aaff;
	}

	.size {
		color: #ffaa00;
	}

	.pnl-pct, .pnl-usdt {
		font-weight: bold;
	}

	.positive {
		color: #00ff88;
	}

	.negative {
		color: #ff4444;
	}

	.reason {
		color: #888;
		font-size: 11px;
	}

	.duration {
		color: #888;
		font-size: 11px;
	}

	.signals {
		color: #00aaff;
		font-size: 10px;
		max-width: 150px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	/* Mobile responsive */
	@media (max-width: 1024px) {
		.table-container {
			overflow-x: scroll;
		}

		.trades-table {
			min-width: 1200px;
		}
	}

	@media (max-width: 768px) {
		.trades-table {
			font-size: 10px;
		}

		.trades-table th,
		.trades-table td {
			padding: 8px 6px;
		}
	}
</style>
