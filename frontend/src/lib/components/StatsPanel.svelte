<script>
	import { stats, winrate } from '$lib/stores/stats';
	import { formatUSDT, formatPercent } from '$lib/utils/format';
</script>

<div class="stats-panel">
	<div class="stats-header">
		<h3>Session Statistics</h3>
	</div>

	<div class="stats-grid">
		<div class="stat-box" data-debug-name="stats.total_trades">
			<div class="stat-label" data-debug-name="stats.total_trades">Total Trades</div>
			<div class="stat-value" data-debug-name="stats.total_trades">{$stats.total_trades}</div>
		</div>

		<div class="stat-box wins" data-debug-name="stats.wins">
			<div class="stat-label" data-debug-name="stats.wins">Wins</div>
			<div class="stat-value" data-debug-name="stats.wins">{$stats.wins}</div>
		</div>

		<div class="stat-box losses" data-debug-name="stats.losses">
			<div class="stat-label" data-debug-name="stats.losses">Losses</div>
			<div class="stat-value" data-debug-name="stats.losses">{$stats.losses}</div>
		</div>

		<div class="stat-box winrate" data-debug-name="winrate">
			<div class="stat-label" data-debug-name="winrate">Winrate</div>
			<div class="stat-value" data-debug-name="winrate">{$winrate}%</div>
		</div>

		<div class="stat-box pnl-pct" class:positive={$stats.total_pnl_pct >= 0} class:negative={$stats.total_pnl_pct < 0} data-debug-name="stats.total_pnl_pct">
			<div class="stat-label" data-debug-name="stats.total_pnl_pct">Total PnL %</div>
			<div class="stat-value" data-debug-name="stats.total_pnl_pct">
				{formatPercent($stats.total_pnl_pct)}%
			</div>
		</div>

		<div class="stat-box pnl" class:positive={$stats.total_pnl_usdt >= 0} class:negative={$stats.total_pnl_usdt < 0} data-debug-name="stats.total_pnl_usdt">
			<div class="stat-label" data-debug-name="stats.total_pnl_usdt">Total PnL</div>
			<div class="stat-value" data-debug-name="stats.total_pnl_usdt">
				{formatUSDT($stats.total_pnl_usdt)} USDT
			</div>
		</div>


		{#if $stats.best_trade}
			<div class="stat-box best" data-debug-name="stats.best_trade">
				<div class="stat-label" data-debug-name="stats.best_trade">Best Trade</div>
				<div class="stat-value" data-debug-name="stats.best_trade.pnl_pct">+{formatPercent($stats.best_trade.net_pnl_pct || $stats.best_trade.pnl_pct || 0)}%</div>
				<div class="stat-subvalue" data-debug-name="stats.best_trade.usdt">+{formatUSDT($stats.best_trade.net_pnl_usdt || $stats.best_trade.pnl_usdt || 0)} USDT</div>
				<div class="stat-subvalue" data-debug-name="stats.best_trade.symbol">{$stats.best_trade.symbol}</div>
			</div>
		{/if}

		{#if $stats.worst_trade}
			<div class="stat-box worst" data-debug-name="stats.worst_trade">
				<div class="stat-label" data-debug-name="stats.worst_trade">Worst Trade</div>
				<div class="stat-value" data-debug-name="stats.worst_trade.pnl_pct">{formatPercent($stats.worst_trade.net_pnl_pct || $stats.worst_trade.pnl_pct || 0)}%</div>
				<div class="stat-subvalue" data-debug-name="stats.worst_trade.usdt">{formatUSDT($stats.worst_trade.net_pnl_usdt || $stats.worst_trade.pnl_usdt || 0)} USDT</div>
				<div class="stat-subvalue" data-debug-name="stats.worst_trade.symbol">{$stats.worst_trade.symbol}</div>
			</div>
		{/if}
	</div>
</div>

<style>
	.stats-panel {
		background: #1e2749;
		border-radius: 12px;
		padding: 20px;
		border: 2px solid #2a3a6b;
	}

	.stats-header {
		margin-bottom: 20px;
	}


	.stats-header h3 {
		font-size: 20px;
		color: #00ff88;
		font-weight: bold;
		margin: 0;
	}


	.stats-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 15px;
	}

	.stat-box {
		background: #0a0e27;
		padding: 15px;
		border-radius: 10px;
		text-align: center;
		border: 2px solid #2a3a6b;
		transition: all 0.3s;
	}

	.stat-box:hover {
		transform: translateY(-2px);
		box-shadow: 0 4px 15px rgba(0, 255, 136, 0.2);
	}

	.stat-label {
		font-size: 11px;
		color: #888;
		margin-bottom: 8px;
		text-transform: uppercase;
		font-weight: bold;
	}

	.stat-value {
		font-size: 24px;
		font-weight: bold;
		color: #fff;
	}

	.stat-subvalue {
		font-size: 12px;
		color: #888;
		margin-top: 5px;
	}

	/* Specific styles */
	.stat-box.wins {
		border-color: #00ff88;
	}

	.stat-box.wins .stat-value {
		color: #00ff88;
	}

	.stat-box.losses {
		border-color: #ff4444;
	}

	.stat-box.losses .stat-value {
		color: #ff4444;
	}

	.stat-box.winrate {
		border-color: #00aaff;
	}

	.stat-box.winrate .stat-value {
		color: #00aaff;
	}

	.stat-box.pnl-pct.positive {
		border-color: #00ff88;
	}

	.stat-box.pnl-pct.positive .stat-value {
		color: #00ff88;
		text-shadow: 0 0 20px rgba(0, 255, 136, 0.5);
	}

	.stat-box.pnl-pct.negative {
		border-color: #ff4444;
	}

	.stat-box.pnl-pct.negative .stat-value {
		color: #ff4444;
		text-shadow: 0 0 20px rgba(255, 68, 68, 0.5);
	}

	.stat-box.pnl.positive {
		border-color: #00ff88;
	}

	.stat-box.pnl.positive .stat-value {
		color: #00ff88;
		text-shadow: 0 0 20px rgba(0, 255, 136, 0.5);
	}

	.stat-box.pnl.negative {
		border-color: #ff4444;
	}

	.stat-box.pnl.negative .stat-value {
		color: #ff4444;
		text-shadow: 0 0 20px rgba(255, 68, 68, 0.5);
	}

	.stat-box.best {
		border-color: #00ff88;
	}

	.stat-box.best .stat-value {
		color: #00ff88;
	}

	.stat-box.worst {
		border-color: #ff4444;
	}

	.stat-box.worst .stat-value {
		color: #ff4444;
	}

	/* Mobile responsive */
	@media (max-width: 768px) {
		.stats-grid {
			grid-template-columns: repeat(2, 1fr);
		}

		.stat-value {
			font-size: 20px;
		}
	}
</style>
