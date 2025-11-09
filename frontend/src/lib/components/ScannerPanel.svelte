<script>
	import { top10Pairs } from '$lib/stores/scanner';

	function formatNumber(num) {
		if (!num) return '0';
		return Number(num).toLocaleString('en-US', { maximumFractionDigits: 2 });
	}

	function formatPercent(num) {
		if (num === null || num === undefined) return 'N/A';
		return Number(num).toFixed(4);
	}

	function formatVolume(num) {
		if (!num) return '0';
		if (num >= 1000000) {
			return (num / 1000000).toFixed(2) + 'M';
		} else if (num >= 1000) {
			return (num / 1000).toFixed(2) + 'K';
		}
		return num.toFixed(0);
	}
</script>

<div class="scanner-panel">
	<div class="scanner-header">
		<h3>🔥 Scalability Scanner - Top Pairs</h3>
		<div class="scan-status">
			{$top10Pairs.length > 0 ? `${$top10Pairs.length} paires` : 'En attente...'}
		</div>
	</div>

	{#if $top10Pairs.length > 0}
		<div class="pairs-list">
			<div class="pairs-table-header">
				<div class="col-rank">#</div>
				<div class="col-symbol">Paire</div>
				<div class="col-score">Score</div>
				<div class="col-spread">Spread</div>
				<div class="col-volume">Volume 24h</div>
				<div class="col-price">Prix</div>
				<div class="col-fees">Fees</div>
			</div>
			{#each $top10Pairs as pair, i}
				<div class="pair-item">
					<div class="col-rank">#{i + 1}</div>
					<div class="col-symbol">{pair.symbol}</div>
					<div class="col-score">
						<span class="score-badge">{formatNumber(pair.score)}</span>
					</div>
					<div class="col-spread">
						<span class="spread-value">{formatPercent(pair.spread_pct)}%</span>
					</div>
					<div class="col-volume">
						<span class="volume-value">{formatVolume(pair.volume_24h)} USDT</span>
					</div>
					<div class="col-price">
						<span class="price-value">{formatNumber(pair.price)}</span>
					</div>
					<div class="col-fees">
						<span class="fees-value">{pair.maker_fee || '0'}% / {pair.taker_fee || '0'}%</span>
					</div>
				</div>
			{/each}
		</div>
	{:else}
		<div class="no-pairs">
			<div class="no-pairs-icon">🔍</div>
			<div class="no-pairs-text">Aucune paire scannée. Lancez le bot pour commencer.</div>
		</div>
	{/if}
</div>

<style>
	.scanner-panel {
		background: #1e2749;
		border-radius: 12px;
		padding: 20px;
		border: 2px solid #2a3a6b;
	}

	.scanner-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 20px;
	}

	.scanner-header h3 {
		font-size: 20px;
		color: #00ff88;
		font-weight: bold;
		margin: 0;
	}

	.scan-status {
		background: rgba(0, 170, 255, 0.2);
		color: #00aaff;
		padding: 6px 14px;
		border-radius: 12px;
		font-size: 12px;
		font-weight: bold;
		border: 1px solid #00aaff;
	}

	.pairs-list {
		background: #0a0e27;
		border-radius: 8px;
		padding: 15px;
		overflow-x: auto;
	}

	.pairs-table-header {
		display: grid;
		grid-template-columns: 40px 120px 80px 100px 120px 100px 90px;
		gap: 10px;
		padding: 10px;
		background: rgba(0, 255, 136, 0.1);
		border-radius: 6px;
		margin-bottom: 10px;
		font-size: 11px;
		font-weight: bold;
		color: #00ff88;
		text-transform: uppercase;
	}

	.pair-item {
		display: grid;
		grid-template-columns: 40px 120px 80px 100px 120px 100px 90px;
		gap: 10px;
		align-items: center;
		padding: 12px 10px;
		background: #1e2749;
		border-radius: 6px;
		margin-bottom: 6px;
		border: 1px solid #2a3a6b;
		transition: all 0.3s;
		font-size: 12px;
	}

	.pair-item:hover {
		border-color: #00ff88;
		background: rgba(0, 255, 136, 0.05);
		transform: translateX(3px);
	}

	.col-rank {
		font-weight: bold;
		color: #888;
	}

	.col-symbol {
		font-weight: bold;
		color: #fff;
	}

	.score-badge {
		display: inline-block;
		font-weight: bold;
		color: #00ff88;
		padding: 4px 10px;
		background: rgba(0, 255, 136, 0.1);
		border-radius: 6px;
		border: 1px solid rgba(0, 255, 136, 0.3);
	}

	.spread-value {
		color: #00aaff;
		font-weight: 600;
	}

	.volume-value {
		color: #ffaa00;
		font-weight: 600;
	}

	.price-value {
		color: #fff;
		font-family: 'Courier New', monospace;
	}

	.fees-value {
		color: #888;
		font-size: 11px;
	}

	.no-pairs {
		text-align: center;
		padding: 60px 20px;
	}

	.no-pairs-icon {
		font-size: 64px;
		margin-bottom: 15px;
		opacity: 0.5;
	}

	.no-pairs-text {
		font-size: 14px;
		color: #888;
	}

	/* Mobile */
	@media (max-width: 768px) {
		.scanner-header {
			flex-direction: column;
			gap: 15px;
		}

		.pairs-table-header {
			display: none;
		}

		.pair-item {
			grid-template-columns: 1fr;
			gap: 8px;
			padding: 15px;
		}

		.pair-item > div {
			display: flex;
			justify-content: space-between;
		}

		.pair-item > div::before {
			content: attr(class);
			color: #888;
			font-size: 11px;
			text-transform: uppercase;
			margin-right: 10px;
		}

		.col-rank::before {
			content: 'Rang';
		}

		.col-symbol::before {
			content: 'Paire';
		}

		.col-score::before {
			content: 'Score';
		}

		.col-spread::before {
			content: 'Spread';
		}

		.col-volume::before {
			content: 'Volume';
		}

		.col-price::before {
			content: 'Prix';
		}

		.col-fees::before {
			content: 'Fees';
		}
	}
</style>
