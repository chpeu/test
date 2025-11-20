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
		if (value >= 0.8) return '#10b981'; // green
		if (value >= 0.65) return '#f59e0b'; // orange
		return '#ef4444'; // red
	}

	function getOverfittingColor(gap) {
		if (gap < 0.1) return '#10b981';
		if (gap < 0.2) return '#f59e0b';
		return '#ef4444';
	}

	function getPriorityColor(priority) {
		switch (priority) {
			case 'high':
				return '#ef4444';
			case 'medium':
				return '#f59e0b';
			case 'low':
				return '#3b82f6';
			default:
				return '#6b7280';
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
		border: 3px solid #f3f4f6;
		border-top: 3px solid #667eea;
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
		color: #dc2626;
		margin-bottom: 0.5rem;
	}

	.error .hint {
		color: #6b7280;
		font-size: 0.9rem;
		margin-top: 0.5rem;
	}

	.header {
		margin-bottom: 2rem;
		padding-bottom: 1rem;
		border-bottom: 2px solid #e5e7eb;
	}

	.title-section {
		display: flex;
		align-items: center;
		gap: 1rem;
		margin-bottom: 0.5rem;
	}

	.title-section h2 {
		font-size: 1.5rem;
		color: #111827;
		margin: 0;
	}

	.model-type {
		background: #eff6ff;
		color: #1e40af;
		padding: 0.25rem 0.75rem;
		border-radius: 12px;
		font-size: 0.85rem;
		font-weight: 600;
	}

	.trained-date {
		color: #6b7280;
		font-size: 0.9rem;
	}

	.section {
		margin-bottom: 2rem;
	}

	.section h3 {
		font-size: 1.1rem;
		color: #111827;
		margin: 0 0 1rem 0;
	}

	.section h4 {
		font-size: 0.95rem;
		color: #374151;
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
		color: #6b7280;
		font-size: 0.85rem;
	}

	.info-value {
		color: #111827;
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
		background: #f9fafb;
		border: 2px solid #e5e7eb;
		border-radius: 8px;
		padding: 1rem;
	}

	.metric-card.secondary {
		background: #fafafa;
		opacity: 0.9;
	}

	.metric-row {
		display: flex;
		justify-content: space-between;
		padding: 0.5rem 0;
		border-bottom: 1px solid #e5e7eb;
	}

	.metric-row:last-child {
		border-bottom: none;
	}

	.metric-label {
		color: #6b7280;
		font-size: 0.9rem;
	}

	.metric-value {
		font-weight: 600;
		color: #111827;
	}

	.overfitting-card {
		background: #f9fafb;
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
		color: #6b7280;
		font-weight: 600;
	}

	.overfitting-value {
		font-size: 1.2rem;
		font-weight: 700;
	}

	.overfitting-bar {
		height: 12px;
		background: #e5e7eb;
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
		background: #f3f4f6;
		color: #374151;
		font-size: 0.85rem;
	}

	.cm-cell.true-negative {
		background: #d1fae5;
		color: #065f46;
		font-size: 1.5rem;
	}

	.cm-cell.false-positive {
		background: #fee2e2;
		color: #991b1b;
		font-size: 1.5rem;
	}

	.cm-cell.false-negative {
		background: #fef3c7;
		color: #92400e;
		font-size: 1.5rem;
	}

	.cm-cell.true-positive {
		background: #d1fae5;
		color: #065f46;
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
		background: #f9fafb;
		border-radius: 8px;
	}

	.feature-rank {
		background: #667eea;
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
		color: #374151;
		font-weight: 600;
		font-size: 0.9rem;
		margin-bottom: 0.25rem;
	}

	.feature-bar-container {
		height: 6px;
		background: #e5e7eb;
		border-radius: 3px;
		overflow: hidden;
	}

	.feature-bar {
		height: 100%;
		background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
		transition: width 0.5s ease;
	}

	.feature-importance {
		color: #667eea;
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
		background: #f9fafb;
		border-radius: 8px;
	}

	.quality-label {
		color: #6b7280;
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
		background: #d1fae5;
		color: #065f46;
	}

	.quality-badge.moderate,
	.quality-badge.acceptable {
		background: #fef3c7;
		color: #92400e;
	}

	.quality-badge.high,
	.quality-badge.poor,
	.quality-badge.limited {
		background: #fee2e2;
		color: #991b1b;
	}

	.recommendations {
		display: grid;
		gap: 1rem;
	}

	.recommendation {
		background: #f9fafb;
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
		background: #e5e7eb;
		color: #374151;
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
		color: #374151;
		font-size: 0.9rem;
		margin: 0;
		line-height: 1.5;
	}
</style>
