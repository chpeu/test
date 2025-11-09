<script>
	import { top10Pairs } from '$lib/stores/scanner';

	function formatNumber(num) {
		if (!num) return '0';
		return Number(num).toFixed(4);
	}

	function formatSpread(num) {
		if (num === null || num === undefined || isNaN(num)) return 'N/A';
		return (num * 100).toFixed(4);
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
		<div class="pairs-list-backend">
			{#each $top10Pairs as pair, i}
				<div class="pair-line" class:even={i % 2 === 0}>
					<span class="rank">#{i + 1}</span>
					<span class="symbol">{pair.symbol}</span>
					| <span class="label">Price:</span> <span class="price">{formatNumber(pair.price)}</span>
					| <span class="label">Vol5:</span> <span class="vol5">{formatNumber(pair.vol5)}%</span>
					| <span class="label">Vol15:</span> <span class="vol15">{formatNumber(pair.vol15)}%</span>
					| <span class="label">Spread:</span> <span class="spread">{formatSpread(pair.spread)}%</span>
					| <span class="label">Depth:</span> <span class="depth">{formatNumber(pair.bookDepth)}</span>
					| <span class="label">Balance:</span> <span class="balance">{formatNumber(pair.balanceScore)}</span>
					| <span class="label">Score:</span> <span class="score">{formatNumber(pair.score)}</span>
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

	.pairs-list-backend {
		font-family: 'Courier New', monospace;
		font-size: 13px;
		line-height: 1.8;
		background: #0a0e27;
		padding: 15px;
		border-radius: 8px;
	}

	.pair-line {
		padding: 10px;
		margin-bottom: 3px;
		background: #0a0e27;
		border-left: 4px solid #00ff88;
		transition: all 0.2s;
	}

	.pair-line.even {
		background: #1a1e3a;
	}

	.pair-line:hover {
		background: rgba(0, 255, 136, 0.1);
		transform: translateX(5px);
		border-left-color: #00ff88;
		box-shadow: 0 2px 10px rgba(0, 255, 136, 0.2);
	}

	.rank {
		color: #888;
		font-weight: bold;
	}

	.symbol {
		color: #fff;
		font-weight: bold;
		font-size: 14px;
	}

	.label {
		color: #888;
		font-size: 12px;
	}

	.price {
		color: #00aaff;
	}

	.vol5, .vol15 {
		color: #ffaa00;
	}

	.spread {
		color: #ff00ff;
		font-weight: bold;
	}

	.depth {
		color: #00ffff;
	}

	.balance {
		color: #00ff88;
	}

	.score {
		color: #00ff88;
		font-weight: bold;
		font-size: 15px;
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
		.pairs-list-backend {
			font-size: 11px;
			overflow-x: auto;
		}

		.pair-line {
			white-space: nowrap;
		}
	}
</style>
