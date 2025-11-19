<script>
	import { onMount, onDestroy } from 'svelte';
	import { predictionSettings } from '$lib/stores/ml.js';
	import ConfidenceFilter from './ConfidenceFilter.svelte';

	let predictions = [];
	let loading = false;
	let error = null;
	let autoRefresh = true;
	let refreshInterval;

	async function fetchPrediction() {
		loading = true;
		error = null;

		try {
			// Utiliser le nouvel endpoint qui récupère les données réelles
			const response = await fetch('/api/ml/predict/current');

			if (!response.ok) {
				const errorText = await response.text();
				if (response.status === 404) {
					throw new Error('Aucune donnée de marché récente. Lancez un scan pour obtenir des prédictions.');
				}
				throw new Error(`HTTP ${response.status}: ${errorText}`);
			}

			const prediction = await response.json();
			
			// Ajouter timestamp et ID
			prediction.id = Date.now();
			prediction.timestamp = new Date().toLocaleTimeString('fr-FR');
			
			// Ajouter en tete de liste
			predictions = [prediction, ...predictions].slice(0, 10); // Garder max 10
			
		} catch (err) {
			console.error('Error fetching prediction:', err);
			error = err.message;
		} finally {
			loading = false;
		}
	}

	function toggleAutoRefresh() {
		autoRefresh = !autoRefresh;
		if (autoRefresh) {
			startAutoRefresh();
		} else {
			stopAutoRefresh();
		}
	}

	function startAutoRefresh() {
		if (refreshInterval) clearInterval(refreshInterval);
		refreshInterval = setInterval(fetchPrediction, 10000); // Toutes les 10s
	}

	function stopAutoRefresh() {
		if (refreshInterval) {
			clearInterval(refreshInterval);
			refreshInterval = null;
		}
	}

	onMount(() => {
		fetchPrediction(); // Premiere prediction
		if (autoRefresh) {
			startAutoRefresh();
		}
	});

	onDestroy(() => {
		stopAutoRefresh();
	});

	function getConfidenceColor(confidence) {
		if (confidence >= 0.8) return '#10b981';
		if (confidence >= 0.7) return '#3b82f6';
		if (confidence >= 0.6) return '#f59e0b';
		return '#ef4444';
	}

	function getRecommendation(prediction, confidence) {
		if (prediction === 'win' && confidence >= 0.7) {
			return { text: 'FORTEMENT RECOMMANDE', color: '#10b981', icon: '🚀' };
		} else if (prediction === 'win' && confidence >= 0.6) {
			return { text: 'RECOMMANDE', color: '#3b82f6', icon: '✅' };
		} else if (prediction === 'loss' && confidence >= 0.7) {
			return { text: 'A EVITER', color: '#ef4444', icon: '🚫' };
		} else {
			return { text: 'INCERTAIN', color: '#6b7280', icon: '❓' };
		}
	}
</script>

<div class="live-predictions">
	<div class="header">
		<div class="title-section">
			<h2>🔮 Prédictions ML Live</h2>
			<p class="subtitle">Prédictions en temps réel sur les opportunités de trading</p>
		</div>
		<div class="controls">
			<button class="refresh-btn" on:click={fetchPrediction} disabled={loading}>
				{loading ? '⏳' : '🔄'} Prédire
			</button>
			<button class="auto-refresh-btn" class:active={autoRefresh} on:click={toggleAutoRefresh}>
				{autoRefresh ? '⏸️' : '▶️'} Auto
			</button>
		</div>
	</div>

	<!-- Slider de filtrage ML -->
	<ConfidenceFilter />

	{#if error}
		<div class="error-card">
			<h3>⚠️ Erreur</h3>
			<p>{error}</p>
			<p class="hint">Assurez-vous que le modèle XGBoost est entraîné.</p>
		</div>
	{/if}

	{#if predictions.length === 0 && !error}
		<div class="empty-state">
			<p>Aucune prédiction pour le moment</p>
			<p class="hint">Cliquez sur "Prédire" pour obtenir une prédiction ML</p>
		</div>
	{:else}
		<div class="predictions-list">
			{#each predictions as pred (pred.id)}
				{@const rec = getRecommendation(pred.prediction, pred.confidence)}
				{@const wouldTake = !$predictionSettings.filterEnabled || (pred.prediction === 'win' && pred.win_probability >= $predictionSettings.confidenceThreshold)}
				<div class="prediction-card" class:win={pred.prediction === 'win'} class:loss={pred.prediction === 'loss'} class:filtered={!wouldTake}>
					<div class="pred-header">
						<div class="pred-info">
							<div class="pred-time">{pred.timestamp}</div>
							{#if pred.symbol}
								<div class="pred-symbol">{pred.symbol}</div>
							{/if}
						</div>
						<div class="pred-actions">
							{#if wouldTake}
								<span class="trade-badge trade">✓ TRADE</span>
							{:else}
								<span class="trade-badge skip">✗ SKIP</span>
							{/if}
							<div class="pred-model">{pred.model_name}</div>
						</div>
					</div>

					<div class="pred-main">
						<div class="pred-result">
							<div class="pred-label">{pred.prediction === 'win' ? '🟢 WIN' : '🔴 LOSS'}</div>
							<div class="pred-confidence" style="color: {getConfidenceColor(pred.confidence)}">
								{(pred.confidence * 100).toFixed(1)}%
							</div>
						</div>

						<div class="pred-probabilities">
							<div class="prob-item">
								<span class="prob-label">Win:</span>
								<div class="prob-bar-container">
									<div
										class="prob-bar win-bar"
										style="width: {pred.win_probability * 100}%"
									></div>
								</div>
								<span class="prob-value">{(pred.win_probability * 100).toFixed(1)}%</span>
							</div>
							<div class="prob-item">
								<span class="prob-label">Loss:</span>
								<div class="prob-bar-container">
									<div
										class="prob-bar loss-bar"
										style="width: {pred.loss_probability * 100}%"
									></div>
								</div>
								<span class="prob-value">{(pred.loss_probability * 100).toFixed(1)}%</span>
							</div>
						</div>
					</div>

					<div class="pred-recommendation" style="background-color: {rec.color}20; border-color: {rec.color}">
						<span class="rec-icon">{rec.icon}</span>
						<span class="rec-text" style="color: {rec.color}">{rec.text}</span>
					</div>

					{#if pred.top_features && pred.top_features.length > 0}
						<div class="pred-features">
							<div class="features-title">Top Features:</div>
							<div class="features-list">
								{#each pred.top_features.slice(0, 3) as feat}
									<div class="feature-tag">{feat.feature}</div>
								{/each}
							</div>
						</div>
					{/if}

					{#if pred.model_performance}
						<div class="pred-performance">
							<span class="perf-label">Accuracy Modèle:</span>
							<span class="perf-value">{(pred.model_performance.test_accuracy * 100).toFixed(1)}%</span>
						</div>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.live-predictions {
		background: white;
		border-radius: 12px;
		padding: 1.5rem;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
	}

	.header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 1.5rem;
		flex-wrap: wrap;
		gap: 1rem;
	}

	.title-section h2 {
		font-size: 1.3rem;
		color: #111827;
		margin: 0 0 0.5rem 0;
	}

	.subtitle {
		color: #6b7280;
		font-size: 0.9rem;
		margin: 0;
	}

	.controls {
		display: flex;
		gap: 0.5rem;
	}

	.refresh-btn,
	.auto-refresh-btn {
		padding: 0.5rem 1rem;
		border: 2px solid #e5e7eb;
		border-radius: 8px;
		background: white;
		color: #374151;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s;
	}

	.refresh-btn:hover:not(:disabled),
	.auto-refresh-btn:hover {
		border-color: #667eea;
		color: #667eea;
		transform: translateY(-2px);
	}

	.refresh-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.auto-refresh-btn.active {
		background: #667eea;
		color: white;
		border-color: #667eea;
	}

	.error-card {
		background: #fef2f2;
		border: 2px solid #fecaca;
		border-radius: 8px;
		padding: 1.5rem;
		text-align: center;
	}

	.error-card h3 {
		color: #dc2626;
		margin: 0 0 0.5rem 0;
	}

	.hint {
		color: #6b7280;
		font-size: 0.85rem;
		margin-top: 0.5rem;
	}

	.empty-state {
		text-align: center;
		padding: 3rem 2rem;
		color: #6b7280;
	}

	.predictions-list {
		display: grid;
		gap: 1rem;
	}

	.prediction-card {
		background: #f9fafb;
		border: 2px solid #e5e7eb;
		border-radius: 12px;
		padding: 1.25rem;
		transition: all 0.3s;
	}

	.prediction-card.win {
		border-color: #86efac;
		background: #f0fdf4;
	}

	.prediction-card.loss {
		border-color: #fca5a5;
		background: #fef2f2;
	}

	.prediction-card.filtered {
		opacity: 0.5;
		border-style: dashed;
	}

	.pred-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 1rem;
		font-size: 0.85rem;
	}

	.pred-info {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.pred-time {
		color: #6b7280;
		font-weight: 600;
	}

	.pred-symbol {
		background: #fef3c7;
		color: #92400e;
		padding: 0.15rem 0.4rem;
		border-radius: 4px;
		font-weight: 700;
		font-size: 0.75rem;
		display: inline-block;
		width: fit-content;
	}

	.pred-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.trade-badge {
		font-size: 0.75rem;
		font-weight: 700;
		padding: 0.25rem 0.5rem;
		border-radius: 4px;
		white-space: nowrap;
	}

	.trade-badge.trade {
		background: #dcfce7;
		color: #166534;
		border: 1px solid #86efac;
	}

	.trade-badge.skip {
		background: #fee2e2;
		color: #991b1b;
		border: 1px solid #fca5a5;
	}

	.pred-model {
		background: #eff6ff;
		color: #1e40af;
		padding: 0.2rem 0.5rem;
		border-radius: 6px;
		font-weight: 600;
	}

	.pred-main {
		display: grid;
		gap: 1rem;
		margin-bottom: 1rem;
	}

	.pred-result {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.pred-label {
		font-size: 1.5rem;
		font-weight: 700;
	}

	.pred-confidence {
		font-size: 1.8rem;
		font-weight: 800;
	}

	.pred-probabilities {
		display: grid;
		gap: 0.5rem;
	}

	.prob-item {
		display: grid;
		grid-template-columns: 50px 1fr 60px;
		align-items: center;
		gap: 0.75rem;
		font-size: 0.9rem;
	}

	.prob-label {
		color: #6b7280;
		font-weight: 600;
	}

	.prob-bar-container {
		height: 12px;
		background: #e5e7eb;
		border-radius: 6px;
		overflow: hidden;
	}

	.prob-bar {
		height: 100%;
		transition: width 0.5s ease;
	}

	.prob-bar.win-bar {
		background: linear-gradient(90deg, #10b981 0%, #059669 100%);
	}

	.prob-bar.loss-bar {
		background: linear-gradient(90deg, #ef4444 0%, #dc2626 100%);
	}

	.prob-value {
		text-align: right;
		font-weight: 700;
		color: #374151;
	}

	.pred-recommendation {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.75rem 1rem;
		border: 2px solid;
		border-radius: 8px;
		margin-bottom: 1rem;
	}

	.rec-icon {
		font-size: 1.5rem;
	}

	.rec-text {
		font-weight: 700;
		font-size: 1rem;
	}

	.pred-features {
		margin-bottom: 0.75rem;
	}

	.features-title {
		color: #6b7280;
		font-size: 0.85rem;
		font-weight: 600;
		margin-bottom: 0.5rem;
	}

	.features-list {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.feature-tag {
		background: #eff6ff;
		color: #1e40af;
		padding: 0.25rem 0.75rem;
		border-radius: 12px;
		font-size: 0.8rem;
		font-weight: 600;
	}

	.pred-performance {
		display: flex;
		justify-content: space-between;
		padding-top: 0.75rem;
		border-top: 1px solid #e5e7eb;
		font-size: 0.85rem;
	}

	.perf-label {
		color: #6b7280;
	}

	.perf-value {
		font-weight: 700;
		color: #374151;
	}
</style>
