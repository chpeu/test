<script>
	import { top20Pairs } from '$lib/stores/scanner';
	import { formatAdaptive, formatSpread, formatPrice, formatPercent } from '$lib/utils/format';
</script>

<div class="scanner-panel">
	<div class="scanner-header">
		<h3>🔥 Scalability Scanner - Top 20 Pairs</h3>
		<div class="scan-status">
			{$top20Pairs.length > 0 ? `${$top20Pairs.length} paires` : 'En attente...'}
		</div>
	</div>

	{#if $top20Pairs.length > 0}
		<div class="pairs-grid">
			{#each $top20Pairs as pair, i}
				<div class="pair-card">
					<div class="pair-symbol">{pair.symbol}</div>
					<div class="pair-metrics">
						<div class="metric">
							<span class="metric-label">Score</span>
							<div class="score-with-rank">
								<span class="metric-value score">{formatAdaptive(pair.score, 2, 4)}</span>
								<div class="pair-rank-inline">#{i + 1}</div>
							</div>
						</div>
						<div class="metric">
							<span class="metric-label">Price</span>
							<span class="metric-value price">{formatPrice(pair.price)}</span>
						</div>
						<div class="metric">
							<span class="metric-label">Vol5</span>
							<span class="metric-value vol">{formatPercent(pair.vol5)}%</span>
						</div>
						<div class="metric">
							<span class="metric-label">Vol15</span>
							<span class="metric-value vol">{formatPercent(pair.vol15)}%</span>
						</div>
						<div class="metric">
							<span class="metric-label">Spread</span>
							<span class="metric-value spread">{formatSpread(pair.spread)}%</span>
						</div>
						<div class="metric">
							<span class="metric-label">Depth</span>
							<span class="metric-value depth">{formatAdaptive(pair.bookDepth, 0, 2)}</span>
						</div>
						<div class="metric">
							<span class="metric-label">Balance</span>
							<span class="metric-value balance">{formatAdaptive(pair.balanceScore, 2, 4)}</span>
						</div>
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

	.pairs-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
		gap: 4px 5px;
		max-height: 600px;
		overflow-y: auto;
	}

	.pair-card {
		background: #0a0e27;
		border: 1px solid #2a3a6b;
		border-radius: 14px;
		padding: 5px 4px 5px 6px;
		transition: all 0.3s;
		position: relative;
		overflow: hidden;
		min-height: fit-content;
	}

	.pair-card::before {
		content: '';
		position: absolute;
		top: 0;
		left: 0;
		width: 3px;
		height: 100%;
		background: linear-gradient(180deg, #00ff88 0%, #00cc6a 100%);
	}

	.pair-card:hover {
		transform: translateY(-2px);
		border-color: #00ff88;
		box-shadow: 0 2px 12px rgba(0, 255, 136, 0.3);
	}

	.score-with-rank {
		display: flex;
		flex-direction: row;
		align-items: center;
		gap: 3px;
		flex-wrap: nowrap;
	}

	.pair-rank-inline {
		background: rgba(0, 170, 255, 0.2);
		color: #00aaff;
		padding: 1px 4px;
		border-radius: 8px;
		font-size: 7px;
		font-weight: bold;
		font-family: 'Courier New', monospace;
		line-height: 1.0;
		flex-shrink: 0;
	}

	.pair-symbol {
		font-size: 10px;
		font-weight: bold;
		color: #fff;
		margin-bottom: 5px;
		font-family: 'Courier New', monospace;
		padding-left: 3px;
		line-height: 1.1;
	}

	.pair-metrics {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 2px 3px;
	}

	.metric {
		display: flex;
		flex-direction: column;
		gap: 2px;
		overflow: hidden;
	}

	.metric-label {
		font-size: 9px;
		color: #888;
		text-transform: uppercase;
		font-weight: bold;
		line-height: 1.1;
	}

	.metric-value {
		font-size: 10px;
		font-family: 'Courier New', monospace;
		font-weight: bold;
		line-height: 1.2;
		word-break: break-word;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.metric-value.score {
		color: #00ff88;
		font-size: 11px;
	}

	.metric-value.price {
		color: #00aaff;
	}

	.metric-value.vol {
		color: #ffaa00;
	}

	.metric-value.spread {
		color: #ff00ff;
	}

	.metric-value.depth {
		color: #00ffff;
	}

	.metric-value.balance {
		color: #00ff88;
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
		.pairs-grid {
			grid-template-columns: 1fr;
		}
	}

	@media (min-width: 769px) and (max-width: 1200px) {
		.pairs-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}

	@media (min-width: 1201px) {
		.pairs-grid {
			grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
		}
	}
</style>
