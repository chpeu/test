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
		<div class="pairs-grid" data-debug-name="top20Pairs">
			{#each $top20Pairs as pair, i}
				<div class="pair-card" data-debug-name="top20Pairs[{i}]">
					<div class="pair-symbol" data-debug-name="pair.symbol">{pair.symbol}</div>
					<div class="pair-metrics">
						<div class="metric" data-debug-name="pair.score">
							<span class="metric-label" data-debug-name="pair.score">Score</span>
							<div class="score-with-rank">
								<span class="metric-value score" data-debug-name="pair.score">{formatAdaptive(pair.score, 2, 4)}</span>
								<div class="pair-rank-inline" data-debug-name="pair.rank">#{i + 1}</div>
							</div>
						</div>
						<div class="metric" data-debug-name="pair.price">
							<span class="metric-label" data-debug-name="pair.price">Price</span>
							<span class="metric-value price" data-debug-name="pair.price">{formatPrice(pair.price)}</span>
						</div>
						<div class="metric" data-debug-name="pair.vol5">
							<span class="metric-label" data-debug-name="pair.vol5">Vol5</span>
							<span class="metric-value vol" data-debug-name="pair.vol5">{formatPercent(pair.vol5)}%</span>
						</div>
						<div class="metric" data-debug-name="pair.vol15">
							<span class="metric-label" data-debug-name="pair.vol15">Vol15</span>
							<span class="metric-value vol" data-debug-name="pair.vol15">{formatPercent(pair.vol15)}%</span>
						</div>
						<div class="metric" data-debug-name="pair.spread">
							<span class="metric-label" data-debug-name="pair.spread">Spread</span>
							<span class="metric-value spread" data-debug-name="pair.spread">{formatSpread(pair.spread)}%</span>
						</div>
						<div class="metric" data-debug-name="pair.bookDepth">
							<span class="metric-label" data-debug-name="pair.bookDepth">Depth</span>
							<span class="metric-value depth" data-debug-name="pair.bookDepth">{formatAdaptive(pair.bookDepth, 0, 2)}</span>
						</div>
						<div class="metric" data-debug-name="pair.balanceScore">
							<span class="metric-label" data-debug-name="pair.balanceScore">Balance</span>
							<span class="metric-value balance" data-debug-name="pair.balanceScore">{formatAdaptive(pair.balanceScore, 2, 4)}</span>
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
		background: var(--bg-secondary);
		border-radius: 12px;
		padding: 20px;
		border: 2px solid var(--border);
	}

	.scanner-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 20px;
	}

	.scanner-header h3 {
		font-size: 20px;
		color: var(--accent-green);
		font-weight: bold;
		margin: 0;
	}

	.scan-status {
		background: rgba(var(--accent-blue-rgb), 0.2);
		color: var(--accent-blue);
		padding: 6px 14px;
		border-radius: 12px;
		font-size: 12px;
		font-weight: bold;
		border: 1px solid var(--accent-blue);
	}

	.pairs-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
		gap: 4px 5px;
		max-height: 600px;
		overflow-y: auto;
	}

	.pair-card {
		background: var(--bg-primary);
		border: 1px solid var(--border);
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
		background: linear-gradient(180deg, var(--accent-green) 0%, var(--accent-green-strong) 100%);
	}

	.pair-card:hover {
		transform: translateY(-2px);
		border-color: var(--accent-green);
		box-shadow: 0 2px 12px rgba(var(--accent-green-rgb), 0.3);
	}

	.score-with-rank {
		display: flex;
		flex-direction: row;
		align-items: center;
		gap: 3px;
		flex-wrap: nowrap;
	}

	.pair-rank-inline {
		background: rgba(var(--accent-blue-rgb), 0.2);
		color: var(--accent-blue);
		padding: 1px 4px;
		border-radius: 8px;
		font-size: 7px;
		font-weight: bold;
		font-family: var(--font-ui);
		line-height: 1.0;
		flex-shrink: 0;
	}

	.pair-symbol {
		font-size: 10px;
		font-weight: bold;
		color: var(--text-primary);
		margin-bottom: 5px;
		font-family: var(--font-ui);
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
		color: var(--text-secondary);
		text-transform: uppercase;
		font-weight: bold;
		line-height: 1.1;
	}

	.metric-value {
		font-size: 10px;
		font-family: var(--font-ui);
		font-weight: bold;
		line-height: 1.2;
		word-break: break-word;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.metric-value.score {
		color: var(--accent-green);
		font-size: 11px;
	}

	.metric-value.price {
		color: var(--accent-blue);
	}

	.metric-value.vol {
		color: var(--accent-orange);
	}

	.metric-value.spread {
		color: var(--accent-purple);
	}

	.metric-value.depth {
		color: var(--accent-blue);
	}

	.metric-value.balance {
		color: var(--accent-green);
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
		color: var(--text-secondary);
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
