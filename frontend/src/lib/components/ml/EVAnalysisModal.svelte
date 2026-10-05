<script>
	import { createEventDispatcher } from 'svelte';

	export let show = false;
	
	const dispatch = createEventDispatcher();

	let loading = false;
	let error = null;
	let data = null;
	
	// Parameters
	let days = 180;
	let testRatio = 0.30;
	let step = 5;
	let trainingFilter = true;

	async function runAnalysis() {
		loading = true;
		error = null;
		data = null;

		try {
			const params = new URLSearchParams({
				days: days.toString(),
				test_ratio: testRatio.toString(),
				step: step.toString(),
				training_filter: trainingFilter.toString()
			});

			const response = await fetch(`/api/ml/ev-analysis?${params}`);
			const result = await response.json();

			if (!result.success) {
				error = result.error || 'Erreur inconnue';
			} else {
				data = result.data;
			}
		} catch (err) {
			error = err.message || 'Erreur réseau';
		} finally {
			loading = false;
		}
	}

	function close() {
		show = false;
		dispatch('close');
	}

	function formatPF(pf) {
		if (pf >= 999) return '∞';
		return pf.toFixed(2);
	}

	function formatPnL(val) {
		const sign = val >= 0 ? '+' : '';
		return `${sign}${val.toFixed(2)}$`;
	}

	function getBestThresholdSummary(best) {
		if (!best) return 'N/A';
		return `≥${best.threshold_pct}% → ${formatPnL(best.test_total_pnl_usdt)}`;
	}
</script>

{#if show}
	<div class="modal-overlay" on:click={close} on:keydown={(e) => e.key === 'Escape' && close()}>
		<div class="modal-content" on:click|stopPropagation>
			<div class="modal-header">
				<h2>📊 Analyse EV par ml_confidence</h2>
				<button class="close-btn" on:click={close}>✕</button>
			</div>

			<div class="modal-body">
				<!-- Parameters -->
				<div class="params-section">
					<div class="param">
						<label for="days">Jours</label>
						<input id="days" type="number" bind:value={days} min="7" max="365" />
					</div>
					<div class="param">
						<label for="testRatio">Test ratio</label>
						<input id="testRatio" type="number" bind:value={testRatio} min="0.1" max="0.5" step="0.05" />
					</div>
					<div class="param">
						<label for="step">Step %</label>
						<input id="step" type="number" bind:value={step} min="1" max="20" />
					</div>
					<div class="param checkbox">
						<label>
							<input type="checkbox" bind:checked={trainingFilter} />
							Filtre training
						</label>
					</div>
					<button class="run-btn" on:click={runAnalysis} disabled={loading}>
						{loading ? '⏳ Analyse...' : '▶ Lancer'}
					</button>
				</div>

				{#if error}
					<div class="error-box">❌ {error}</div>
				{/if}

				{#if data}
					<!-- Summary -->
					<div class="summary-section">
						<div class="summary-card">
							<span class="label">Période</span>
							<span class="value">{data.period.days}j</span>
						</div>
						<div class="summary-card">
							<span class="label">Trades</span>
							<span class="value">{data.trades_count}</span>
						</div>
						<div class="summary-card">
							<span class="label">Avec ML</span>
							<span class="value">{data.trades_with_ml_pct}%</span>
						</div>
						<div class="summary-card">
							<span class="label">Split</span>
							<span class="value">{data.split.train_count}/{data.split.test_count}</span>
						</div>
					</div>

					<!-- Best Thresholds -->
					<div class="best-section">
						<h3>🏆 Meilleurs seuils (optimisés sur TRAIN)</h3>
						<div class="best-grid">
							<div class="best-card" class:positive={data.best_thresholds.unconstrained?.test_total_pnl_usdt > 0}>
								<span class="title">Max PnL</span>
								<span class="value">{getBestThresholdSummary(data.best_thresholds.unconstrained)}</span>
							</div>
							<div class="best-card" class:positive={data.best_thresholds.keep_80pct?.test_total_pnl_usdt > 0}>
								<span class="title">≥80% trades</span>
								<span class="value">{getBestThresholdSummary(data.best_thresholds.keep_80pct)}</span>
							</div>
							<div class="best-card" class:positive={data.best_thresholds.keep_90pct?.test_total_pnl_usdt > 0}>
								<span class="title">≥90% trades</span>
								<span class="value">{getBestThresholdSummary(data.best_thresholds.keep_90pct)}</span>
							</div>
						</div>
					</div>

					<!-- Buckets Table -->
					<div class="table-section">
						<h3>📈 Buckets (EV net par tranche 5%)</h3>
						<div class="table-wrapper">
							<table>
								<thead>
									<tr>
										<th>Bucket</th>
										<th>N</th>
										<th>WR%</th>
										<th>EV%</th>
										<th>PF</th>
										<th>PnL$</th>
									</tr>
								</thead>
								<tbody>
									{#each data.buckets as bucket}
										<tr class:positive={bucket.total_pnl_usdt > 0} class:negative={bucket.total_pnl_usdt < 0}>
											<td>{bucket.bucket}</td>
											<td>{bucket.trades}</td>
											<td>{bucket.winrate.toFixed(1)}</td>
											<td>{bucket.avg_pnl_pct.toFixed(3)}</td>
											<td>{formatPF(bucket.profit_factor)}</td>
											<td>{formatPnL(bucket.total_pnl_usdt)}</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					</div>

					<!-- Thresholds Table (collapsed) -->
					<details class="table-section">
						<summary><h3>📋 Table complète par seuil (TEST)</h3></summary>
						<div class="table-wrapper">
							<table>
								<thead>
									<tr>
										<th>Seuil</th>
										<th>Keep%</th>
										<th>N</th>
										<th>WR%</th>
										<th>EV%</th>
										<th>PF</th>
										<th>PnL$</th>
									</tr>
								</thead>
								<tbody>
									{#each data.thresholds_table.sort((a, b) => b.test_total_pnl_usdt - a.test_total_pnl_usdt) as row}
										<tr class:positive={row.test_total_pnl_usdt > 0} class:negative={row.test_total_pnl_usdt < 0}>
											<td>≥{row.threshold_pct}%</td>
											<td>{row.test_retention_pct.toFixed(1)}</td>
											<td>{row.test_count}</td>
											<td>{row.test_wr.toFixed(1)}</td>
											<td>{row.test_avg_pnl_pct.toFixed(3)}</td>
											<td>{formatPF(row.test_pf)}</td>
											<td>{formatPnL(row.test_total_pnl_usdt)}</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					</details>
				{/if}
			</div>
		</div>
	</div>
{/if}

<style>
	.modal-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
	}

	.modal-content {
		background: var(--bg-primary, #1a1a2e);
		border-radius: 12px;
		width: 90%;
		max-width: 900px;
		max-height: 85vh;
		overflow: hidden;
		display: flex;
		flex-direction: column;
		box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 1rem 1.5rem;
		border-bottom: 1px solid var(--border-color, #333);
		background: var(--bg-secondary, #16213e);
	}

	.modal-header h2 {
		margin: 0;
		font-size: 1.25rem;
		color: var(--text-primary, #fff);
	}

	.close-btn {
		background: none;
		border: none;
		font-size: 1.5rem;
		color: var(--text-secondary, #888);
		cursor: pointer;
		padding: 0.25rem;
	}

	.close-btn:hover {
		color: var(--text-primary, #fff);
	}

	.modal-body {
		padding: 1.5rem;
		overflow-y: auto;
		flex: 1;
	}

	.params-section {
		display: flex;
		gap: 1rem;
		flex-wrap: wrap;
		align-items: flex-end;
		margin-bottom: 1.5rem;
		padding: 1rem;
		background: var(--bg-secondary, #16213e);
		border-radius: 8px;
	}

	.param {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.param label {
		font-size: 0.75rem;
		color: var(--text-secondary, #888);
	}

	.param input[type="number"] {
		width: 80px;
		padding: 0.5rem;
		border: 1px solid var(--border-color, #333);
		border-radius: 4px;
		background: var(--bg-primary, #1a1a2e);
		color: var(--text-primary, #fff);
	}

	.param.checkbox {
		flex-direction: row;
		align-items: center;
	}

	.param.checkbox label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.85rem;
		color: var(--text-primary, #fff);
	}

	.run-btn {
		padding: 0.5rem 1.5rem;
		background: linear-gradient(135deg, #667eea, #764ba2);
		color: white;
		border: none;
		border-radius: 6px;
		font-weight: 600;
		cursor: pointer;
		transition: opacity 0.2s;
	}

	.run-btn:hover:not(:disabled) {
		opacity: 0.9;
	}

	.run-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.error-box {
		background: #fef2f2;
		color: #dc2626;
		padding: 1rem;
		border-radius: 8px;
		margin-bottom: 1rem;
	}

	.summary-section {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
		gap: 1rem;
		margin-bottom: 1.5rem;
	}

	.summary-card {
		background: var(--bg-secondary, #16213e);
		padding: 1rem;
		border-radius: 8px;
		text-align: center;
	}

	.summary-card .label {
		display: block;
		font-size: 0.75rem;
		color: var(--text-secondary, #888);
		margin-bottom: 0.25rem;
	}

	.summary-card .value {
		font-size: 1.25rem;
		font-weight: 600;
		color: var(--text-primary, #fff);
	}

	.best-section {
		margin-bottom: 1.5rem;
	}

	.best-section h3 {
		font-size: 1rem;
		margin-bottom: 0.75rem;
		color: var(--text-primary, #fff);
	}

	.best-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 1rem;
	}

	.best-card {
		background: var(--bg-secondary, #16213e);
		padding: 1rem;
		border-radius: 8px;
		border-left: 3px solid var(--border-color, #333);
	}

	.best-card.positive {
		border-left-color: #10b981;
	}

	.best-card .title {
		display: block;
		font-size: 0.75rem;
		color: var(--text-secondary, #888);
		margin-bottom: 0.25rem;
	}

	.best-card .value {
		font-size: 1rem;
		font-weight: 600;
		color: var(--text-primary, #fff);
	}

	.table-section {
		margin-bottom: 1.5rem;
	}

	.table-section h3 {
		font-size: 1rem;
		margin-bottom: 0.75rem;
		color: var(--text-primary, #fff);
	}

	.table-section summary h3 {
		display: inline;
		cursor: pointer;
	}

	.table-wrapper {
		overflow-x: auto;
		border-radius: 8px;
		border: 1px solid var(--border-color, #333);
	}

	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.85rem;
	}

	th, td {
		padding: 0.5rem 0.75rem;
		text-align: right;
		border-bottom: 1px solid var(--border-color, #333);
	}

	th:first-child, td:first-child {
		text-align: left;
	}

	th {
		background: var(--bg-secondary, #16213e);
		color: var(--text-secondary, #888);
		font-weight: 500;
		font-size: 0.75rem;
		text-transform: uppercase;
	}

	td {
		color: var(--text-primary, #fff);
	}

	tr.positive td:last-child {
		color: #10b981;
	}

	tr.negative td:last-child {
		color: #ef4444;
	}

	details summary {
		cursor: pointer;
		user-select: none;
	}

	details[open] summary {
		margin-bottom: 0.75rem;
	}
</style>
