<script>
	import { onMount, onDestroy } from 'svelte';
	import { getWebSocketMetrics, resetWebSocketMetrics } from '$lib/utils/websocket';

	let metrics = null;
	let interval;

	function updateMetrics() {
		metrics = getWebSocketMetrics();
	}

	function handleReset() {
		resetWebSocketMetrics();
		updateMetrics();
	}

	onMount(() => {
		updateMetrics();
		// Rafraîchir toutes les 2 secondes
		interval = setInterval(updateMetrics, 2000);
	});

	onDestroy(() => {
		if (interval) clearInterval(interval);
	});

	// Calculer taux de succès
	$: successRate = metrics
		? (metrics.commandsSucceeded / (metrics.commandsSucceeded + metrics.commandsFailed) * 100).toFixed(1)
		: '0.0';
</script>

<div class="ws-metrics">
	<div class="metrics-header">
		<h3>📊 WebSocket Métriques</h3>
		<button class="reset-btn" on:click={handleReset}>Reset</button>
	</div>

	{#if metrics}
		<div class="metrics-grid">
			<div class="metric-card">
				<div class="metric-icon">📤</div>
				<div class="metric-content">
					<div class="metric-label">Commands Envoyés</div>
					<div class="metric-value">{metrics.commandsSent}</div>
				</div>
			</div>

			<div class="metric-card success">
				<div class="metric-icon">✅</div>
				<div class="metric-content">
					<div class="metric-label">Succès</div>
					<div class="metric-value">{metrics.commandsSucceeded}</div>
				</div>
			</div>

			<div class="metric-card error">
				<div class="metric-icon">❌</div>
				<div class="metric-content">
					<div class="metric-label">Échecs</div>
					<div class="metric-value">{metrics.commandsFailed}</div>
				</div>
			</div>

			<div class="metric-card">
				<div class="metric-icon">📈</div>
				<div class="metric-content">
					<div class="metric-label">Taux Succès</div>
					<div class="metric-value">{successRate}%</div>
				</div>
			</div>

			<div class="metric-card">
				<div class="metric-icon">⏱️</div>
				<div class="metric-content">
					<div class="metric-label">Temps Réponse Moyen</div>
					<div class="metric-value">{metrics.averageResponseTime.toFixed(0)}ms</div>
				</div>
			</div>

			<div class="metric-card">
				<div class="metric-icon">🔄</div>
				<div class="metric-content">
					<div class="metric-label">Reconnexions</div>
					<div class="metric-value">{metrics.reconnections}</div>
				</div>
			</div>
		</div>
	{:else}
		<div class="no-metrics">
			<p>⚠️ Métriques non disponibles (WebSocket non connecté)</p>
		</div>
	{/if}
</div>

<style>
	.ws-metrics {
		background: var(--bg-secondary, #2a2a2a);
		border-radius: 12px;
		padding: 20px;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
	}

	.metrics-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 16px;
		padding-bottom: 12px;
		border-bottom: 1px solid var(--bg-tertiary, #3a3a3a);
	}

	.metrics-header h3 {
		font-size: 18px;
		color: var(--accent-blue, #00aaff);
		margin: 0;
	}

	.reset-btn {
		background: var(--bg-tertiary, #3a3a3a);
		color: var(--text-primary, #ffffff);
		border: 1px solid var(--bg-quaternary, #4a4a4a);
		border-radius: 6px;
		padding: 6px 12px;
		font-size: 12px;
		cursor: pointer;
		transition: all 0.2s;
	}

	.reset-btn:hover {
		background: var(--bg-quaternary, #4a4a4a);
		border-color: var(--accent-blue, #00aaff);
	}

	.metrics-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
		gap: 12px;
	}

	.metric-card {
		background: var(--bg-primary, #1a1a1a);
		border: 1px solid var(--bg-tertiary, #3a3a3a);
		border-radius: 8px;
		padding: 12px;
		display: flex;
		align-items: center;
		gap: 10px;
		transition: all 0.3s ease;
	}

	.metric-card:hover {
		border-color: var(--accent-blue, #00aaff);
		transform: translateY(-2px);
	}

	.metric-card.success {
		border-color: var(--accent-green, #00ff88);
		background: rgba(0, 255, 136, 0.05);
	}

	.metric-card.error {
		border-color: var(--accent-red, #ff4444);
		background: rgba(255, 68, 68, 0.05);
	}

	.metric-icon {
		font-size: 24px;
		line-height: 1;
	}

	.metric-content {
		flex: 1;
		min-width: 0;
	}

	.metric-label {
		font-size: 11px;
		color: var(--text-secondary, #888888);
		text-transform: uppercase;
		letter-spacing: 0.5px;
		margin-bottom: 4px;
	}

	.metric-value {
		font-size: 16px;
		font-weight: 600;
		color: var(--text-primary, #ffffff);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.metric-card.success .metric-value {
		color: var(--accent-green, #00ff88);
	}

	.metric-card.error .metric-value {
		color: var(--accent-red, #ff4444);
	}

	.no-metrics {
		padding: 40px 20px;
		text-align: center;
		color: var(--text-secondary, #888888);
	}

	@media (max-width: 768px) {
		.metrics-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}

	@media (max-width: 480px) {
		.metrics-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
