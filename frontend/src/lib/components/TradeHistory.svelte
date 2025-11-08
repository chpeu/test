<script>
	import { sortedTrades } from '$lib/stores/trades';
	import { flip } from 'svelte/animate';
	import { fade } from 'svelte/transition';

	let showCount = 10;

	function formatDate(dateStr) {
		if (!dateStr) return '';
		const date = new Date(dateStr);
		return date.toLocaleString('en-US', {
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	}

	function formatNumber(num) {
		if (num === null || num === undefined) return '0.00';
		return Number(num).toFixed(2);
	}

	$: displayTrades = $sortedTrades.slice(0, showCount);
</script>

<div class="trade-history">
	<div class="history-header">
		<h3>Trade History</h3>
		<div class="total-count">{$sortedTrades.length} total trades</div>
	</div>

	{#if $sortedTrades.length === 0}
		<div class="no-trades">
			<div class="no-trades-icon">📊</div>
			<div class="no-trades-text">No trades yet</div>
		</div>
	{:else}
		<div class="trades-list">
			{#each displayTrades as trade (trade.id || trade.symbol + trade.closed_at)}
				<div
					class="trade-item"
					class:win={trade.net_pnl_usdt >= 0}
					class:loss={trade.net_pnl_usdt < 0}
					animate:flip={{ duration: 300 }}
					in:fade={{ duration: 200 }}
				>
					<div class="trade-header">
						<div class="trade-symbol">{trade.symbol}</div>
						<div
							class="trade-direction"
							class:long={trade.direction === 'LONG'}
							class:short={trade.direction === 'SHORT'}
						>
							{trade.direction}
						</div>
						<div class="trade-reason">{trade.reason}</div>
					</div>

					<div class="trade-pnl">
						<div class="pnl-percent" class:positive={trade.net_pnl_pct >= 0} class:negative={trade.net_pnl_pct < 0}>
							{trade.net_pnl_pct >= 0 ? '+' : ''}{formatNumber(trade.net_pnl_pct)}%
						</div>
						<div class="pnl-usdt" class:positive={trade.net_pnl_usdt >= 0} class:negative={trade.net_pnl_usdt < 0}>
							{trade.net_pnl_usdt >= 0 ? '+' : ''}{formatNumber(trade.net_pnl_usdt)} USDT
						</div>
					</div>

					<div class="trade-details">
						<div class="detail">
							<span class="detail-label">Entry:</span>
							<span class="detail-value">{formatNumber(trade.entry)}</span>
						</div>
						<div class="detail">
							<span class="detail-label">Exit:</span>
							<span class="detail-value">{formatNumber(trade.exit_price)}</span>
						</div>
						<div class="detail">
							<span class="detail-label">Size:</span>
							<span class="detail-value">{formatNumber(trade.size)} USDT</span>
						</div>
						<div class="detail">
							<span class="detail-label">Closed:</span>
							<span class="detail-value">{formatDate(trade.closed_at)}</span>
						</div>
					</div>

					{#if trade.slippage_pct}
						<div class="trade-footer">
							<div class="slippage">Slippage: {formatNumber(trade.slippage_pct)}%</div>
							<div class="fees">Fees: {formatNumber(trade.fees_usdt)} USDT</div>
						</div>
					{/if}
				</div>
			{/each}
		</div>

		{#if $sortedTrades.length > showCount}
			<div class="load-more">
				<button class="btn-load-more" on:click={() => (showCount += 10)}>
					Load More ({$sortedTrades.length - showCount} remaining)
				</button>
			</div>
		{/if}
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
	}

	.history-header h3 {
		font-size: 20px;
		color: #00ff88;
		font-weight: bold;
	}

	.total-count {
		font-size: 14px;
		color: #888;
	}

	.no-trades {
		text-align: center;
		padding: 60px 20px;
	}

	.no-trades-icon {
		font-size: 64px;
		margin-bottom: 20px;
	}

	.no-trades-text {
		font-size: 18px;
		color: #888;
	}

	.trades-list {
		display: flex;
		flex-direction: column;
		gap: 15px;
	}

	.trade-item {
		background: #0a0e27;
		border-radius: 10px;
		padding: 15px;
		border: 2px solid;
		transition: all 0.3s;
	}

	.trade-item.win {
		border-color: rgba(0, 255, 136, 0.3);
	}

	.trade-item.loss {
		border-color: rgba(255, 68, 68, 0.3);
	}

	.trade-item:hover {
		transform: translateX(5px);
	}

	.trade-item.win:hover {
		border-color: #00ff88;
		box-shadow: 0 4px 15px rgba(0, 255, 136, 0.2);
	}

	.trade-item.loss:hover {
		border-color: #ff4444;
		box-shadow: 0 4px 15px rgba(255, 68, 68, 0.2);
	}

	.trade-header {
		display: flex;
		align-items: center;
		gap: 12px;
		margin-bottom: 12px;
	}

	.trade-symbol {
		font-size: 16px;
		font-weight: bold;
		color: #fff;
	}

	.trade-direction {
		padding: 4px 10px;
		border-radius: 6px;
		font-size: 11px;
		font-weight: bold;
	}

	.trade-direction.long {
		background: rgba(0, 255, 136, 0.2);
		color: #00ff88;
	}

	.trade-direction.short {
		background: rgba(255, 68, 68, 0.2);
		color: #ff4444;
	}

	.trade-reason {
		margin-left: auto;
		font-size: 12px;
		color: #888;
		padding: 4px 10px;
		background: rgba(255, 255, 255, 0.05);
		border-radius: 6px;
	}

	.trade-pnl {
		display: flex;
		gap: 15px;
		margin-bottom: 12px;
	}

	.pnl-percent {
		font-size: 24px;
		font-weight: bold;
	}

	.pnl-percent.positive {
		color: #00ff88;
		text-shadow: 0 0 10px rgba(0, 255, 136, 0.5);
	}

	.pnl-percent.negative {
		color: #ff4444;
		text-shadow: 0 0 10px rgba(255, 68, 68, 0.5);
	}

	.pnl-usdt {
		font-size: 18px;
		font-weight: bold;
		align-self: flex-end;
	}

	.pnl-usdt.positive {
		color: #00ff88;
	}

	.pnl-usdt.negative {
		color: #ff4444;
	}

	.trade-details {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 8px;
		margin-bottom: 10px;
	}

	.detail {
		font-size: 12px;
	}

	.detail-label {
		color: #888;
		margin-right: 5px;
	}

	.detail-value {
		color: #00aaff;
		font-weight: bold;
	}

	.trade-footer {
		display: flex;
		gap: 15px;
		padding-top: 10px;
		border-top: 1px solid #2a3a6b;
		font-size: 11px;
		color: #888;
	}

	.load-more {
		text-align: center;
		margin-top: 20px;
	}

	.btn-load-more {
		padding: 12px 24px;
		background: #2a3a6b;
		border: 2px solid #00ff88;
		border-radius: 8px;
		color: #00ff88;
		font-size: 14px;
		font-weight: bold;
		cursor: pointer;
		transition: all 0.3s;
	}

	.btn-load-more:hover {
		background: rgba(0, 255, 136, 0.1);
		transform: translateY(-2px);
	}

	/* Mobile */
	@media (max-width: 768px) {
		.trade-header {
			flex-wrap: wrap;
		}

		.trade-reason {
			margin-left: 0;
			flex-basis: 100%;
		}

		.trade-details {
			grid-template-columns: 1fr;
		}

		.trade-pnl {
			flex-direction: column;
			gap: 5px;
		}
	}
</style>
