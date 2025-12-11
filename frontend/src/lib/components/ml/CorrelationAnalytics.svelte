<script>
	import { onMount } from 'svelte';
	
	let loading = true;
	let error = null;
	let data = null;
	let days = 7;
	
	async function loadCorrelations() {
		loading = true;
		error = null;
		try {
			const response = await fetch(`/api/ml/analytics/correlations?days=${days}`);
			if (!response.ok) throw new Error('Erreur chargement corrélations');
			data = await response.json();
		} catch (err) {
			error = err.message;
		} finally {
			loading = false;
		}
	}
	
	onMount(() => {
		loadCorrelations();
	});
	
	function getRecommendationClass(rec) {
		if (rec === 'FAVOR') return 'favor';
		if (rec === 'AVOID') return 'avoid';
		return 'neutral';
	}
	
	function getConfidenceClass(conf) {
		if (conf === 'HIGH') return 'high';
		if (conf === 'MEDIUM') return 'medium';
		return 'low';
	}
</script>

<div class="correlation-analytics">
	<div class="header">
		<h2>📊 Analyse des Corrélations</h2>
		<div class="controls">
			<select bind:value={days} on:change={loadCorrelations}>
				<option value={1}>1 jour</option>
				<option value={7}>7 jours</option>
				<option value={14}>14 jours</option>
				<option value={30}>30 jours</option>
			</select>
			<button on:click={loadCorrelations} disabled={loading}>
				{loading ? '⏳' : '🔄'} Actualiser
			</button>
		</div>
	</div>
	
	{#if loading}
		<div class="loading">
			<div class="spinner"></div>
			<p>Chargement des corrélations...</p>
		</div>
	{:else if error}
		<div class="error">❌ {error}</div>
	{:else if data}
		<!-- Performance par Session -->
		<div class="section">
			<h3>🌍 Performance par Session</h3>
			<div class="table-container">
				<table>
					<thead>
						<tr>
							<th>Session</th>
							<th>Trades</th>
							<th>Win Rate</th>
							<th>PnL Total</th>
							<th>Recommandation</th>
						</tr>
					</thead>
					<tbody>
						{#each data.by_session || [] as item}
							<tr class={getRecommendationClass(item.recommendation)}>
								<td class="session">{item.value}</td>
								<td>{item.trades}</td>
								<td class="winrate">{item.winrate}%</td>
								<td class="pnl {item.total_pnl >= 0 ? 'positive' : 'negative'}">
									{item.total_pnl >= 0 ? '+' : ''}{item.total_pnl?.toFixed(2)} USDT
								</td>
								<td>
									<span class="badge {getRecommendationClass(item.recommendation)}">
										{item.recommendation}
									</span>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
		
		<!-- Performance par Régime Local -->
		<div class="section">
			<h3>📈 Performance par Régime Local (ATR%)</h3>
			<div class="table-container">
				<table>
					<thead>
						<tr>
							<th>Régime</th>
							<th>Seuil ATR</th>
							<th>Trades</th>
							<th>Win Rate</th>
							<th>PnL Total</th>
							<th>Recommandation</th>
						</tr>
					</thead>
					<tbody>
						{#each data.by_local_regime || [] as item}
							<tr class={getRecommendationClass(item.recommendation)}>
								<td class="regime">{item.value}</td>
								<td class="threshold">
									{#if item.value === 'LOW'}&lt;0.2%
									{:else if item.value === 'MEDIUM'}0.2-0.5%
									{:else}&gt;0.5%
									{/if}
								</td>
								<td>{item.trades}</td>
								<td class="winrate">{item.winrate}%</td>
								<td class="pnl {item.total_pnl >= 0 ? 'positive' : 'negative'}">
									{item.total_pnl >= 0 ? '+' : ''}{item.total_pnl?.toFixed(2)} USDT
								</td>
								<td>
									<span class="badge {getRecommendationClass(item.recommendation)}">
										{item.recommendation}
									</span>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
		
		<!-- Distribution Régime Optimal -->
		{#if data.optimal_regime_distribution?.distribution}
			<div class="section">
				<h3>🎯 Distribution Régime Optimal (What-If)</h3>
				<div class="regime-distribution">
					{#each Object.entries(data.optimal_regime_distribution.distribution) as [regime, info]}
						<div class="regime-bar">
							<span class="regime-name">{regime}</span>
							<div class="bar-container">
								<div class="bar" style="width: {info.percentage}%"></div>
							</div>
							<span class="percentage">{info.percentage}%</span>
							<span class="count">({info.trades} trades)</span>
						</div>
					{/each}
				</div>
				{#if data.optimal_regime_distribution.dominant_regime}
					<p class="dominant">
						Régime dominant: <strong>{data.optimal_regime_distribution.dominant_regime}</strong>
					</p>
				{/if}
			</div>
		{/if}
		
		<!-- Performance par Exit Reason -->
		<div class="section">
			<h3>🚪 Performance par Raison de Sortie</h3>
			<div class="table-container">
				<table>
					<thead>
						<tr>
							<th>Raison</th>
							<th>Trades</th>
							<th>Win Rate</th>
							<th>PnL Total</th>
						</tr>
					</thead>
					<tbody>
						{#each data.by_exit_reason || [] as item}
							<tr>
								<td class="reason">{item.value}</td>
								<td>{item.trades}</td>
								<td class="winrate">{item.winrate}%</td>
								<td class="pnl {item.total_pnl >= 0 ? 'positive' : 'negative'}">
									{item.total_pnl >= 0 ? '+' : ''}{item.total_pnl?.toFixed(2)} USDT
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
</div>

<style>
	.correlation-analytics {
		padding: 1rem;
		background: var(--bg-secondary, #1a1a2e);
		border-radius: 8px;
	}
	
	.header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1.5rem;
	}
	
	.header h2 {
		margin: 0;
		color: var(--text-primary, #fff);
	}
	
	.controls {
		display: flex;
		gap: 0.5rem;
	}
	
	.controls select, .controls button {
		padding: 0.5rem 1rem;
		border-radius: 4px;
		border: 1px solid var(--border-color, #333);
		background: var(--bg-tertiary, #252540);
		color: var(--text-primary, #fff);
		cursor: pointer;
	}
	
	.controls button:hover:not(:disabled) {
		background: var(--accent-color, #4a9eff);
	}
	
	.loading, .error {
		text-align: center;
		padding: 2rem;
		color: var(--text-secondary, #aaa);
	}
	
	.error {
		color: #ff6b6b;
	}
	
	.spinner {
		width: 40px;
		height: 40px;
		border: 3px solid var(--border-color, #333);
		border-top-color: var(--accent-color, #4a9eff);
		border-radius: 50%;
		animation: spin 1s linear infinite;
		margin: 0 auto 1rem;
	}
	
	@keyframes spin {
		to { transform: rotate(360deg); }
	}
	
	.section {
		margin-bottom: 2rem;
		background: var(--bg-tertiary, #252540);
		border-radius: 8px;
		padding: 1rem;
	}
	
	.section h3 {
		margin: 0 0 1rem 0;
		color: var(--text-primary, #fff);
		font-size: 1rem;
	}
	
	.table-container {
		overflow-x: auto;
	}
	
	table {
		width: 100%;
		border-collapse: collapse;
	}
	
	th, td {
		padding: 0.75rem;
		text-align: left;
		border-bottom: 1px solid var(--border-color, #333);
	}
	
	th {
		color: var(--text-secondary, #888);
		font-weight: 500;
		font-size: 0.85rem;
	}
	
	td {
		color: var(--text-primary, #fff);
	}
	
	tr.favor { background: rgba(40, 167, 69, 0.1); }
	tr.avoid { background: rgba(220, 53, 69, 0.1); }
	
	.badge {
		padding: 0.25rem 0.5rem;
		border-radius: 4px;
		font-size: 0.75rem;
		font-weight: bold;
	}
	
	.badge.favor { background: #28a745; color: #fff; }
	.badge.avoid { background: #dc3545; color: #fff; }
	.badge.neutral { background: #6c757d; color: #fff; }
	
	.winrate {
		font-weight: bold;
	}
	
	.pnl.positive { color: #28a745; }
	.pnl.negative { color: #dc3545; }
	
	.regime-distribution {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	
	.regime-bar {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}
	
	.regime-name {
		width: 80px;
		font-weight: bold;
		color: var(--text-primary, #fff);
	}
	
	.bar-container {
		flex: 1;
		height: 20px;
		background: var(--bg-secondary, #1a1a2e);
		border-radius: 4px;
		overflow: hidden;
	}
	
	.bar {
		height: 100%;
		background: linear-gradient(90deg, #4a9eff, #28a745);
		border-radius: 4px;
		transition: width 0.3s ease;
	}
	
	.percentage {
		width: 50px;
		text-align: right;
		font-weight: bold;
		color: var(--accent-color, #4a9eff);
	}
	
	.count {
		color: var(--text-secondary, #888);
		font-size: 0.85rem;
	}
	
	.dominant {
		margin-top: 1rem;
		padding: 0.75rem;
		background: var(--bg-secondary, #1a1a2e);
		border-radius: 4px;
		text-align: center;
		color: var(--text-secondary, #888);
	}
	
	.dominant strong {
		color: var(--accent-color, #4a9eff);
	}
</style>
