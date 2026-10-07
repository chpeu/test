<script>
	import { onMount } from 'svelte';

	export let modelName = 'xgboost_v1';

	let metrics = null;
	let loading = true;
	let error = null;

	async function loadMetrics() {
		try {
			const response = await fetch(`/api/ml/models/metrics/${modelName}`);
			if (!response.ok) {
				throw new Error(`Modèle non trouvé ou non entraîné`);
			}
			metrics = await response.json();
			error = null;
		} catch (err) {
			console.error('Error loading model metrics:', err);
			error = err.message;
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		loadMetrics();

		// Refresh every 60s
		const interval = setInterval(loadMetrics, 60000);
		return () => clearInterval(interval);
	});

	function getPerformanceColor(value) {
		if (value >= 0.8) return 'var(--accent-green-strong)'; // green
		if (value >= 0.65) return 'var(--accent-orange)'; // orange
		return 'var(--accent-red-strong)'; // red
	}

	function getOverfittingColor(gap) {
		if (gap < 0.1) return 'var(--accent-green-strong)';
		if (gap < 0.2) return 'var(--accent-orange)';
		return 'var(--accent-red-strong)';
	}

	function getPriorityColor(priority) {
		switch (priority) {
			case 'high':
				return 'var(--accent-red-strong)';
			case 'medium':
				return 'var(--accent-orange)';
			case 'low':
				return 'var(--accent-blue)';
			default:
				return 'var(--text-tertiary)';
		}
	}

	function getPriorityIcon(priority) {
		switch (priority) {
			case 'high':
				return '🔴';
			case 'medium':
				return '🟡';
			case 'low':
				return '🟢';
			default:
				return 'ℹ️';
		}
	}
</script>

<div class="metrics-card">
	{#if loading}
		<div class="loading">
			<div class="spinner"></div>
			<p>Chargement métriques...</p>
		</div>
	{:else if error}
		<div class="error">
			<h3>⚠️ Modèle non disponible</h3>
			<p>{error}</p>
			<p class="hint">Entraînez d'abord le modèle pour voir ses métriques.</p>
		</div>
	{:else if metrics}
		<!-- Header -->
		<div class="header">
			<div class="title-section">
				<h2>📊 {metrics.model_name}</h2>
				<span class="model-type">{metrics.model_type}</span>
			</div>
			<div class="meta">
				<span class="trained-date">Entraîné le {new Date(metrics.trained_at).toLocaleDateString('fr-FR')}</span>
			</div>
		</div>

		<!-- Training Info -->
		<div class="section">
			<h3>📈 Informations d'entraînement</h3>
			<div class="info-grid">
				<div class="info-item">
					<span class="info-label">Total samples</span>
					<span class="info-value">{metrics.training_info.total_samples}</span>
				</div>
				<div class="info-item">
					<span class="info-label">Train samples</span>
					<span class="info-value">{metrics.training_info.train_samples}</span>
				</div>
				<div class="info-item">
					<span class="info-label">Test samples</span>
					<span class="info-value">{metrics.training_info.test_samples}</span>
				</div>
				<div class="info-item">
					<span class="info-label">Temps d'entraînement</span>
					<span class="info-value">{metrics.training_info.training_time_seconds}s</span>
				</div>
			</div>
		</div>

		<!-- Performance Metrics -->
		<div class="section">
			<h3>🎯 Performance</h3>
			<div class="performance-grid">
				<!-- Test Metrics -->
				<div class="metric-card">
					<h4>Test Set</h4>
					<div class="metric-row">
						<span class="metric-label">Accuracy</span>
						<span
							class="metric-value"
							style="color: {getPerformanceColor(metrics.performance.test.accuracy)}"
						>
							{(metrics.performance.test.accuracy * 100).toFixed(1)}%
						</span>
					</div>
					<div class="metric-row">
						<span class="metric-label">Precision</span>
						<span class="metric-value">{(metrics.performance.test.precision * 100).toFixed(1)}%</span>
					</div>
					<div class="metric-row">
						<span class="metric-label">Recall</span>
						<span class="metric-value">{(metrics.performance.test.recall * 100).toFixed(1)}%</span>
					</div>
					<div class="metric-row">
						<span class="metric-label">F1 Score</span>
						<span class="metric-value">{(metrics.performance.test.f1 * 100).toFixed(1)}%</span>
					</div>
					<div class="metric-row">
						<span class="metric-label">ROC-AUC</span>
						<span class="metric-value">{(metrics.performance.test.roc_auc * 100).toFixed(1)}%</span>
					</div>
				</div>

				<!-- Train Metrics -->
				<div class="metric-card secondary">
					<h4>Train Set</h4>
					<div class="metric-row">
						<span class="metric-label">Accuracy</span>
						<span class="metric-value">{(metrics.performance.train.accuracy * 100).toFixed(1)}%</span>
					</div>
					<div class="metric-row">
						<span class="metric-label">F1 Score</span>
						<span class="metric-value">{(metrics.performance.train.f1 * 100).toFixed(1)}%</span>
					</div>
					<div class="metric-row">
						<span class="metric-label">ROC-AUC</span>
						<span class="metric-value">{(metrics.performance.train.roc_auc * 100).toFixed(1)}%</span>
					</div>
				</div>
			</div>

			<!-- Overfitting Gap -->
			<div class="overfitting-card" style="border-color: {getOverfittingColor(metrics.performance.overfitting_gap)}">
				<div class="overfitting-header">
					<span class="overfitting-label">Overfitting Gap</span>
					<span
						class="overfitting-value"
						style="color: {getOverfittingColor(metrics.performance.overfitting_gap)}"
					>
						{(metrics.performance.overfitting_gap * 100).toFixed(1)}%
					</span>
				</div>
				<div class="overfitting-bar">
					<div
						class="overfitting-fill"
						style="width: {Math.min(metrics.performance.overfitting_gap * 100, 100)}%; background: {getOverfittingColor(metrics.performance.overfitting_gap)}"
					></div>
				</div>
			</div>
		</div>

		<!-- Confusion Matrix -->
		{#if metrics.confusion_matrix}
			<div class="section">
				<h3>🔢 Matrice de Confusion</h3>
				<div class="confusion-matrix">
					<div class="cm-grid">
						<div class="cm-cell header"></div>
						<div class="cm-cell header">Prédit: Loss</div>
						<div class="cm-cell header">Prédit: Win</div>

						<div class="cm-cell header">Réel: Loss</div>
						<div class="cm-cell true-negative">{metrics.confusion_matrix[0][0]}</div>
						<div class="cm-cell false-positive">{metrics.confusion_matrix[0][1]}</div>

						<div class="cm-cell header">Réel: Win</div>
						<div class="cm-cell false-negative">{metrics.confusion_matrix[1][0]}</div>
						<div class="cm-cell true-positive">{metrics.confusion_matrix[1][1]}</div>
					</div>
				</div>
			</div>
		{/if}

		<!-- Top Features -->
		<div class="section">
			<h3>⭐ Top 10 Features</h3>
			<div class="features-list">
				{#each metrics.top_features as feature, i}
					<div class="feature-item">
						<div class="feature-rank">#{i + 1}</div>
						<div class="feature-info">
							<span class="feature-name">{feature.feature}</span>
							<div class="feature-bar-container">
								<div class="feature-bar" style="width: {feature.importance}%"></div>
							</div>
						</div>
						<span class="feature-importance">{feature.importance.toFixed(1)}%</span>
					</div>
				{/each}
			</div>
		</div>

		<!-- Quality Assessment -->
		<div class="section">
			<h3>⚖️ Évaluation Qualité</h3>
			<div class="quality-grid">
				<div class="quality-item">
					<span class="quality-label">Overfitting</span>
					<span class="quality-badge {metrics.quality_assessment.overfitting}">
						{metrics.quality_assessment.overfitting}
					</span>
				</div>
				<div class="quality-item">
					<span class="quality-label">Performance Test</span>
					<span class="quality-badge {metrics.quality_assessment.test_performance}">
						{metrics.quality_assessment.test_performance}
					</span>
				</div>
				<div class="quality-item">
					<span class="quality-label">Suffisance Données</span>
					<span class="quality-badge {metrics.quality_assessment.data_sufficiency}">
						{metrics.quality_assessment.data_sufficiency}
					</span>
				</div>
			</div>
		</div>

		<!-- Recommendations -->
		<div class="section">
			<h3>💡 Recommandations</h3>
			<div class="recommendations">
				{#each metrics.recommendations as rec}
					<div class="recommendation" style="border-left-color: {getPriorityColor(rec.priority)}">
						<div class="rec-header">
							<span class="rec-icon">{getPriorityIcon(rec.priority)}</span>
							<span class="rec-type">{rec.type.toUpperCase()}</span>
							<span class="rec-priority" style="color: {getPriorityColor(rec.priority)}">
								{rec.priority}
							</span>
						</div>
						<p class="rec-message">{rec.message}</p>
					</div>
				{/each}
			</div>
		</div>
	{/if}
</div>

<style>
	.metrics-card {
		background: white;
		border-radius: 12px;
		padding: 1.5rem;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
	}

	.loading,
	.error {
		text-align: center;
		padding: 3rem 2rem;
	}

	.spinner {
		border: 3px solid var(--border);
		border-top: 3px solid var(--accent-indigo);
		border-radius: 50%;
		width: 40px;
		height: 40px;
		animation: spin 1s linear infinite;
		margin: 0 auto 1rem;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	.error h3 {
		color: var(--accent-red-strong);
		margin-bottom: 0.5rem;
	}

	.error .hint {
		color: var(--text-tertiary);
		font-size: 0.9rem;
		margin-top: 0.5rem;
	}

	.header {
		margin-bottom: 2rem;
		padding-bottom: 1rem;
		border-bottom: 2px solid var(--border);
	}

	.title-section {
		display: flex;
		align-items: center;
		gap: 1rem;
		margin-bottom: 0.5rem;
	}

	.title-section h2 {
		font-size: 1.5rem;
		color: var(--text-primary);
		margin: 0;
	}

	.model-type {
		background: rgba(var(--accent-blue-rgb), 0.12);
		color: var(--accent-blue-dark);
		padding: 0.25rem 0.75rem;
		border-radius: 12px;
		font-size: 0.85rem;
		font-weight: 600;
	}

	.trained-date {
		color: var(--text-tertiary);
		font-size: 0.9rem;
	}

	.section {
		margin-bottom: 2rem;
	}

	.section h3 {
		font-size: 1.1rem;
		color: var(--text-primary);
		margin: 0 0 1rem 0;
	}

	.section h4 {
		font-size: 0.95rem;
		color: var(--text-primary);
		margin: 0 0 0.75rem 0;
	}

	.info-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 1rem;
	}

	.info-item {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.info-label {
		color: var(--text-tertiary);
		font-size: 0.85rem;
	}

	.info-value {
		color: var(--text-primary);
		font-size: 1.1rem;
		font-weight: 600;
	}

	.performance-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
		gap: 1rem;
		margin-bottom: 1rem;
	}

	.metric-card {
		background: var(--bg-input);
		border: 2px solid var(--border);
		border-radius: 8px;
		padding: 1rem;
	}

	.metric-card.secondary {
		background: var(--bg-input);
		opacity: 0.9;
	}

	.metric-row {
		display: flex;
		justify-content: space-between;
		padding: 0.5rem 0;
		border-bottom: 1px solid var(--border);
	}

	.metric-row:last-child {
		border-bottom: none;
	}

	.metric-label {
		color: var(--text-tertiary);
		font-size: 0.9rem;
	}

	.metric-value {
		font-weight: 600;
		color: var(--text-primary);
	}

	.overfitting-card {
		background: var(--bg-input);
		border: 2px solid;
		border-radius: 8px;
		padding: 1rem;
	}

	.overfitting-header {
		display: flex;
		justify-content: space-between;
		margin-bottom: 0.5rem;
	}

	.overfitting-label {
		color: var(--text-tertiary);
		font-weight: 600;
	}

	.overfitting-value {
		font-size: 1.2rem;
		font-weight: 700;
	}

	.overfitting-bar {
		height: 12px;
		background: var(--bg-hover);
		border-radius: 6px;
		overflow: hidden;
	}

	.overfitting-fill {
		height: 100%;
		transition: width 0.5s ease;
	}

	.confusion-matrix {
		overflow-x: auto;
	}

	.cm-grid {
		display: grid;
		grid-template-columns: 100px 1fr 1fr;
		gap: 0.5rem;
		min-width: 400px;
	}

	.cm-cell {
		padding: 1rem;
		text-align: center;
		border-radius: 6px;
		font-weight: 600;
	}

	.cm-cell.header {
		background: var(--bg-input);
		color: var(--text-primary);
		font-size: 0.85rem;
	}

	.cm-cell.true-negative {
		background: rgba(var(--accent-green-rgb), 0.12);
		color: var(--accent-green-strong);
		font-size: 1.5rem;
	}

	.cm-cell.false-positive {
		background: rgba(var(--accent-red-rgb), 0.12);
		color: var(--accent-red-strong);
		font-size: 1.5rem;
	}

	.cm-cell.false-negative {
		background: rgba(var(--accent-orange-rgb), 0.12);
		color: var(--accent-orange);
		font-size: 1.5rem;
	}

	.cm-cell.true-positive {
		background: rgba(var(--accent-green-rgb), 0.12);
		color: var(--accent-green-strong);
		font-size: 1.5rem;
	}

	.features-list {
		display: grid;
		gap: 0.75rem;
	}

	.feature-item {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 0.75rem;
		background: var(--bg-input);
		border-radius: 8px;
	}

	.feature-rank {
		background: var(--accent-indigo);
		color: white;
		width: 32px;
		height: 32px;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-weight: 700;
		font-size: 0.85rem;
		flex-shrink: 0;
	}

	.feature-info {
		flex: 1;
		min-width: 0;
	}

	.feature-name {
		display: block;
		color: var(--text-primary);
		font-weight: 600;
		font-size: 0.9rem;
		margin-bottom: 0.25rem;
	}

	.feature-bar-container {
		height: 6px;
		background: var(--bg-hover);
		border-radius: 3px;
		overflow: hidden;
	}

	.feature-bar {
		height: 100%;
		background: linear-gradient(90deg, var(--accent-indigo) 0%, var(--accent-purple) 100%);
		transition: width 0.5s ease;
	}

	.feature-importance {
		color: var(--accent-indigo);
		font-weight: 700;
		font-size: 0.9rem;
		flex-shrink: 0;
	}

	.quality-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 1rem;
	}

	.quality-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 1rem;
		background: var(--bg-input);
		border-radius: 8px;
	}

	.quality-label {
		color: var(--text-tertiary);
		font-weight: 600;
	}

	.quality-badge {
		padding: 0.25rem 0.75rem;
		border-radius: 12px;
		font-size: 0.85rem;
		font-weight: 600;
		text-transform: capitalize;
	}

	.quality-badge.low,
	.quality-badge.good,
	.quality-badge.sufficient {
		background: rgba(var(--accent-green-rgb), 0.12);
		color: var(--accent-green-strong);
	}

	.quality-badge.moderate,
	.quality-badge.acceptable {
		background: rgba(var(--accent-orange-rgb), 0.12);
		color: var(--accent-orange);
	}

	.quality-badge.high,
	.quality-badge.poor,
	.quality-badge.limited {
		background: rgba(var(--accent-red-rgb), 0.12);
		color: var(--accent-red-strong);
	}

	.recommendations {
		display: grid;
		gap: 1rem;
	}

	.recommendation {
		background: var(--bg-input);
		border-left: 4px solid;
		border-radius: 8px;
		padding: 1rem;
	}

	.rec-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}

	.rec-icon {
		font-size: 1.2rem;
	}

	.rec-type {
		background: var(--bg-hover);
		color: var(--text-primary);
		padding: 0.2rem 0.5rem;
		border-radius: 6px;
		font-size: 0.75rem;
		font-weight: 700;
	}

	.rec-priority {
		font-size: 0.85rem;
		font-weight: 600;
		text-transform: uppercase;
	}

	.rec-message {
		color: var(--text-primary);
		font-size: 0.9rem;
		margin: 0;
		line-height: 1.5;
	}
</style>
