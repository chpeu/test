<script>
	import { isScanning, top10Pairs, pairsCount, avgSpread, avgVolume } from '$lib/stores/scanner';

	async function startScan() {
		try {
			const res = await fetch('/api/scanner/start', { method: 'POST' });
			const data = await res.json();
			console.log('Scan started:', data);
		} catch (err) {
			console.error('Error starting scan:', err);
		}
	}

	async function stopScan() {
		try {
			const res = await fetch('/api/scanner/stop', { method: 'POST' });
			const data = await res.json();
			console.log('Scan stopped:', data);
		} catch (err) {
			console.error('Error stopping scan:', err);
		}
	}

	function formatNumber(num) {
		if (!num) return '0';
		return Number(num).toLocaleString('en-US');
	}
</script>

<div class="scanner-panel">
	<div class="scanner-header">
		<h3>Scalability Scanner</h3>
		<button
			class="btn"
			class:btn-danger={$isScanning}
			class:btn-primary={!$isScanning}
			on:click={$isScanning ? stopScan : startScan}
		>
			{$isScanning ? 'Stop Scan' : 'Start Scan'}
		</button>
	</div>

	<div class="scanner-stats">
		<div class="scanner-stat">
			<div class="stat-label">Total Pairs</div>
			<div class="stat-value">{$pairsCount}</div>
		</div>
		<div class="scanner-stat">
			<div class="stat-label">Avg Spread</div>
			<div class="stat-value">{$avgSpread}%</div>
		</div>
		<div class="scanner-stat">
			<div class="stat-label">Avg Volume</div>
			<div class="stat-value">{formatNumber($avgVolume)}</div>
		</div>
	</div>

	{#if $top10Pairs.length > 0}
		<div class="pairs-list">
			<div class="pairs-header">Top 10 Scalable Pairs</div>
			{#each $top10Pairs as pair, i}
				<div class="pair-item">
					<div class="pair-rank">#{i + 1}</div>
					<div class="pair-symbol">{pair.symbol}</div>
					<div class="pair-score">{pair.score?.toFixed(1) || 'N/A'}</div>
					<div class="pair-spread">{pair.spread_pct?.toFixed(4) || 'N/A'}%</div>
				</div>
			{/each}
		</div>
	{:else}
		<div class="no-pairs">
			{#if $isScanning}
				<div class="scanning-icon">🔍</div>
				<div class="scanning-text">Scanning markets...</div>
			{:else}
				<div class="no-pairs-text">No pairs scanned yet</div>
			{/if}
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
	}

	.btn {
		padding: 10px 24px;
		border: none;
		border-radius: 8px;
		font-size: 14px;
		font-weight: bold;
		cursor: pointer;
		transition: all 0.3s;
		text-transform: uppercase;
	}

	.btn-primary {
		background: linear-gradient(135deg, #00ff88 0%, #00cc6a 100%);
		color: #0a0e27;
	}

	.btn-primary:hover {
		transform: translateY(-2px);
		box-shadow: 0 4px 15px rgba(0, 255, 136, 0.4);
	}

	.btn-danger {
		background: linear-gradient(135deg, #ff4444 0%, #cc0000 100%);
		color: white;
	}

	.btn-danger:hover {
		transform: translateY(-2px);
		box-shadow: 0 4px 15px rgba(255, 68, 68, 0.4);
	}

	.scanner-stats {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 15px;
		margin-bottom: 20px;
	}

	.scanner-stat {
		background: #0a0e27;
		padding: 12px;
		border-radius: 8px;
		text-align: center;
		border: 1px solid #2a3a6b;
	}

	.stat-label {
		font-size: 11px;
		color: #888;
		margin-bottom: 5px;
		text-transform: uppercase;
	}

	.stat-value {
		font-size: 18px;
		font-weight: bold;
		color: #00aaff;
	}

	.pairs-list {
		background: #0a0e27;
		border-radius: 8px;
		padding: 15px;
	}

	.pairs-header {
		font-size: 14px;
		color: #00ff88;
		font-weight: bold;
		margin-bottom: 15px;
		text-align: center;
	}

	.pair-item {
		display: grid;
		grid-template-columns: 40px 1fr auto auto;
		gap: 15px;
		align-items: center;
		padding: 10px;
		background: #1e2749;
		border-radius: 6px;
		margin-bottom: 8px;
		border: 1px solid #2a3a6b;
		transition: all 0.3s;
	}

	.pair-item:hover {
		border-color: #00ff88;
		transform: translateX(5px);
	}

	.pair-rank {
		font-size: 14px;
		font-weight: bold;
		color: #888;
	}

	.pair-symbol {
		font-size: 14px;
		font-weight: bold;
		color: #fff;
	}

	.pair-score {
		font-size: 16px;
		font-weight: bold;
		color: #00ff88;
		padding: 4px 12px;
		background: rgba(0, 255, 136, 0.1);
		border-radius: 6px;
	}

	.pair-spread {
		font-size: 12px;
		color: #00aaff;
	}

	.no-pairs {
		text-align: center;
		padding: 40px 20px;
	}

	.scanning-icon {
		font-size: 48px;
		margin-bottom: 15px;
		animation: spin 2s linear infinite;
	}

	.scanning-text {
		font-size: 16px;
		color: #888;
	}

	.no-pairs-text {
		font-size: 16px;
		color: #888;
	}

	@keyframes spin {
		from {
			transform: rotate(0deg);
		}
		to {
			transform: rotate(360deg);
		}
	}

	/* Mobile */
	@media (max-width: 768px) {
		.scanner-header {
			flex-direction: column;
			gap: 15px;
		}

		.scanner-stats {
			grid-template-columns: 1fr;
		}

		.pair-item {
			grid-template-columns: 30px 1fr;
			gap: 10px;
		}

		.pair-score,
		.pair-spread {
			grid-column: 2;
		}
	}
</style>
