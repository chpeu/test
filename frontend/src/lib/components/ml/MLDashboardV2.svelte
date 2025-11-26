<script>
	import { onMount } from 'svelte';

	// État général
	let loading = false;
	let error = null;
	let activeSubTab = 'training';

	// État entraînement
	let trainingInProgress = false;
	let trainingProgress = 0;
	let trainingLogs = [];

	// Paramètres entraînement
	let trainParams = {
		timeframe_days: 270,
		min_trades: 50,
		filter_marginal_trades: false,
		marginal_threshold: 0.20,
		max_features: 40,
		test_size: 0.2,
		validation_size: 0.1
	};

	// Modèles
	let models = [];
	let selectedModel = null;

	// Métriques
	let metrics = null;

	const tabs = [
		{ id: 'training', label: 'Entraînement', icon: '🎯' },
		{ id: 'models', label: 'Modèles', icon: '🤖' },
		{ id: 'analysis', label: 'Analyse', icon: '📊' }
	];

	onMount(async () => {
		await loadModels();
	});

	async function loadModels() {
		try {
			loading = true;
			error = null;

			const response = await fetch('/api/ml/models');
			if (!response.ok) throw new Error('Erreur chargement modèles');

			const data = await response.json();
			models = data.models || [];
		} catch (e) {
			error = e.message;
			console.error('Error loading models:', e);
		} finally {
			loading = false;
		}
	}

	async function startTraining() {
		try {
			trainingInProgress = true;
			trainingProgress = 0;
			trainingLogs = ['🚀 Démarrage entraînement XGBoost V2...'];
			error = null;

			const response = await fetch('/api/ml/train_v2', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(trainParams)
			});

			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || 'Erreur entraînement');
			}

			const result = await response.json();

			trainingLogs = [
				...trainingLogs,
				'✅ Entraînement terminé',
				`📊 Test Accuracy: ${(result.test_accuracy * 100).toFixed(1)}%`,
				`📈 Test ROC-AUC: ${(result.test_roc_auc * 100).toFixed(1)}%`
			];

			metrics = result;
			await loadModels();
		} catch (e) {
			error = e.message;
			trainingLogs = [...trainingLogs, `❌ Erreur: ${e.message}`];
		} finally {
			trainingInProgress = false;
			trainingProgress = 100;
		}
	}

	function formatDate(dateString) {
		if (!dateString) return 'N/A';
		const date = new Date(dateString);
		return date.toLocaleDateString('fr-FR', {
			day: '2-digit',
			month: '2-digit',
			year: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	}
</script>

<div class="ml-dashboard-v2">
	<!-- Header -->
	<div class="header">
		<div class="title-section">
			<h2>🚀 XGBoost V2 - Enhanced ML Pipeline</h2>
			<p class="subtitle">Split temporel • Filtrage qualité • Features avancées</p>
		</div>
	</div>

	<!-- Tabs -->
	<div class="tabs">
		{#each tabs as tab}
			<button
				class="tab"
				class:active={activeSubTab === tab.id}
				on:click={() => (activeSubTab = tab.id)}
			>
				<span class="icon">{tab.icon}</span>
				<span class="label">{tab.label}</span>
			</button>
		{/each}
	</div>

	<!-- Content -->
	<div class="content">
		{#if error}
			<div class="error-banner">
				<span class="error-icon">⚠️</span>
				<span>{error}</span>
			</div>
		{/if}

		{#if activeSubTab === 'training'}
			<div class="training-section">
				<!-- Paramètres -->
				<div class="card">
					<h3>⚙️ Paramètres Entraînement</h3>

					<div class="param-grid">
						<div class="param">
							<label>Timeframe (jours)</label>
							<input
								type="number"
								bind:value={trainParams.timeframe_days}
								min="30"
								max="730"
								disabled={trainingInProgress}
							/>
						</div>

						<div class="param">
							<label>Min Trades</label>
							<input
								type="number"
								bind:value={trainParams.min_trades}
								min="10"
								max="500"
								disabled={trainingInProgress}
							/>
						</div>

						<div class="param">
							<label>Max Features</label>
							<input
								type="number"
								bind:value={trainParams.max_features}
								min="10"
								max="100"
								disabled={trainingInProgress}
							/>
						</div>

						<div class="param">
							<label>Marginal Threshold (%)</label>
							<input
								type="number"
								step="0.05"
								bind:value={trainParams.marginal_threshold}
								min="0.10"
								max="1.00"
								disabled={trainingInProgress}
							/>
						</div>

						<div class="param checkbox">
							<label>
								<input
									type="checkbox"
									bind:checked={trainParams.filter_marginal_trades}
									disabled={trainingInProgress}
								/>
								Filtrer trades marginaux
							</label>
						</div>
					</div>

					<button
						class="btn-primary"
						on:click={startTraining}
						disabled={trainingInProgress}
					>
						{#if trainingInProgress}
							<span class="spinner"></span>
							Entraînement en cours...
						{:else}
							🎯 Lancer Entraînement
						{/if}
					</button>
				</div>

				<!-- Logs -->
				{#if trainingLogs.length > 0}
					<div class="card">
						<h3>📝 Logs Entraînement</h3>
						<div class="logs">
							{#each trainingLogs as log}
								<div class="log-line">{log}</div>
							{/each}
						</div>
					</div>
				{/if}

				<!-- Métriques -->
				{#if metrics}
					<div class="card">
						<h3>📊 Résultats</h3>
						<div class="metrics-grid">
							<div class="metric-card train">
								<div class="metric-label">Train</div>
								<div class="metric-value">
									{(metrics.train_accuracy * 100).toFixed(1)}%
								</div>
								<div class="metric-sublabel">Accuracy</div>
							</div>

							<div class="metric-card test">
								<div class="metric-label">Test</div>
								<div class="metric-value">
									{(metrics.test_accuracy * 100).toFixed(1)}%
								</div>
								<div class="metric-sublabel">Accuracy</div>
							</div>

							<div class="metric-card gap">
								<div class="metric-label">Gap</div>
								<div class="metric-value">
									{(metrics.accuracy_gap * 100).toFixed(1)}%
								</div>
								<div class="metric-sublabel">Overfitting</div>
							</div>

							<div class="metric-card roc">
								<div class="metric-label">ROC-AUC</div>
								<div class="metric-value">
									{(metrics.test_roc_auc * 100).toFixed(1)}%
								</div>
								<div class="metric-sublabel">Test</div>
							</div>
						</div>
					</div>
				{/if}
			</div>
		{:else if activeSubTab === 'models'}
			<div class="models-section">
				<div class="card">
					<div class="card-header">
						<h3>🤖 Modèles Entraînés</h3>
						<button class="btn-secondary" on:click={loadModels}>
							🔄 Rafraîchir
						</button>
					</div>

					{#if loading}
						<div class="loading">Chargement...</div>
					{:else if models.length === 0}
						<div class="empty-state">
							<span class="icon">📭</span>
							<p>Aucun modèle entraîné</p>
							<p class="hint">Lancez un entraînement dans l'onglet "Entraînement"</p>
						</div>
					{:else}
						<div class="models-table">
							<table>
								<thead>
									<tr>
										<th>Nom</th>
										<th>Version</th>
										<th>Test Acc</th>
										<th>ROC-AUC</th>
										<th>Gap</th>
										<th>Samples</th>
										<th>Date</th>
										<th>Actif</th>
									</tr>
								</thead>
								<tbody>
									{#each models as model}
										<tr>
											<td class="model-name">{model.model_name}</td>
											<td>{model.version}</td>
											<td>
												<span
													class="metric-badge"
													class:good={model.test_accuracy >= 0.65}
													class:medium={model.test_accuracy >= 0.55 &&
														model.test_accuracy < 0.65}
													class:bad={model.test_accuracy < 0.55}
												>
													{(model.test_accuracy * 100).toFixed(1)}%
												</span>
											</td>
											<td>{(model.test_roc_auc * 100).toFixed(1)}%</td>
											<td>
												<span
													class="metric-badge"
													class:good={model.accuracy_gap < 0.15}
													class:medium={model.accuracy_gap >= 0.15 &&
														model.accuracy_gap < 0.25}
													class:bad={model.accuracy_gap >= 0.25}
												>
													{(model.accuracy_gap * 100).toFixed(1)}%
												</span>
											</td>
											<td>{model.total_samples}</td>
											<td class="date">{formatDate(model.trained_at)}</td>
											<td>
												{#if model.is_active}
													<span class="badge active">✓ Actif</span>
												{:else}
													<span class="badge">Inactif</span>
												{/if}
											</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}
				</div>
			</div>
		{:else if activeSubTab === 'analysis'}
			<div class="analysis-section">
				<div class="card">
					<h3>📊 Analyse Approfondie</h3>
					<p class="hint">
						Cette section affichera l'analyse des features, les courbes d'apprentissage, et les
						métriques détaillées.
					</p>
					<p class="hint">🚧 En développement</p>
				</div>
			</div>
		{/if}
	</div>
</div>

<style>
	.ml-dashboard-v2 {
		height: 100%;
		display: flex;
		flex-direction: column;
	}

	.header {
		padding: 1.5rem;
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		color: white;
	}

	.title-section h2 {
		margin: 0 0 0.5rem 0;
		font-size: 1.5rem;
	}

	.subtitle {
		margin: 0;
		opacity: 0.9;
		font-size: 0.9rem;
	}

	.tabs {
		display: flex;
		gap: 0.5rem;
		padding: 1rem 1.5rem;
		background: #f9fafb;
		border-bottom: 2px solid #e5e7eb;
	}

	.tab {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.75rem 1.5rem;
		background: white;
		border: 1px solid #e5e7eb;
		border-radius: 8px;
		color: #6b7280;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.2s;
	}

	.tab:hover {
		border-color: #667eea;
		color: #667eea;
	}

	.tab.active {
		background: #667eea;
		color: white;
		border-color: #667eea;
	}

	.content {
		flex: 1;
		overflow-y: auto;
		padding: 1.5rem;
	}

	.card {
		background: white;
		border-radius: 12px;
		padding: 1.5rem;
		margin-bottom: 1.5rem;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
	}

	.card h3 {
		margin: 0 0 1rem 0;
		font-size: 1.2rem;
	}

	.card-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1rem;
	}

	.card-header h3 {
		margin: 0;
	}

	.param-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 1rem;
		margin-bottom: 1.5rem;
	}

	.param label {
		display: block;
		margin-bottom: 0.5rem;
		font-weight: 500;
		color: #374151;
	}

	.param input[type='number'],
	.param input[type='text'] {
		width: 100%;
		padding: 0.75rem;
		border: 1px solid #d1d5db;
		border-radius: 8px;
		font-size: 1rem;
	}

	.param.checkbox label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		cursor: pointer;
	}

	.btn-primary,
	.btn-secondary {
		padding: 0.875rem 1.75rem;
		border: none;
		border-radius: 8px;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s;
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
	}

	.btn-primary {
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		color: white;
	}

	.btn-primary:hover:not(:disabled) {
		transform: translateY(-2px);
		box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
	}

	.btn-primary:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.btn-secondary {
		background: white;
		color: #667eea;
		border: 2px solid #667eea;
	}

	.btn-secondary:hover {
		background: #667eea;
		color: white;
	}

	.spinner {
		width: 16px;
		height: 16px;
		border: 2px solid rgba(255, 255, 255, 0.3);
		border-top-color: white;
		border-radius: 50%;
		animation: spin 0.6s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	.logs {
		background: #1f2937;
		color: #10b981;
		padding: 1rem;
		border-radius: 8px;
		max-height: 200px;
		overflow-y: auto;
		font-family: 'Courier New', monospace;
		font-size: 0.875rem;
	}

	.log-line {
		margin-bottom: 0.25rem;
	}

	.metrics-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 1rem;
	}

	.metric-card {
		padding: 1.5rem;
		border-radius: 12px;
		text-align: center;
	}

	.metric-card.train {
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		color: white;
	}

	.metric-card.test {
		background: linear-gradient(135deg, #10b981 0%, #059669 100%);
		color: white;
	}

	.metric-card.gap {
		background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
		color: white;
	}

	.metric-card.roc {
		background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
		color: white;
	}

	.metric-label {
		font-size: 0.875rem;
		opacity: 0.9;
		margin-bottom: 0.5rem;
	}

	.metric-value {
		font-size: 2rem;
		font-weight: 700;
		margin-bottom: 0.25rem;
	}

	.metric-sublabel {
		font-size: 0.75rem;
		opacity: 0.8;
	}

	.models-table {
		overflow-x: auto;
	}

	.models-table table {
		width: 100%;
		border-collapse: collapse;
	}

	.models-table th,
	.models-table td {
		padding: 0.75rem;
		text-align: left;
		border-bottom: 1px solid #e5e7eb;
	}

	.models-table th {
		background: #f9fafb;
		font-weight: 600;
		color: #374151;
	}

	.models-table tbody tr:hover {
		background: #f9fafb;
	}

	.model-name {
		font-weight: 600;
		color: #667eea;
	}

	.date {
		color: #6b7280;
		font-size: 0.875rem;
	}

	.metric-badge {
		padding: 0.25rem 0.75rem;
		border-radius: 12px;
		font-weight: 600;
		font-size: 0.875rem;
	}

	.metric-badge.good {
		background: #d1fae5;
		color: #065f46;
	}

	.metric-badge.medium {
		background: #fef3c7;
		color: #92400e;
	}

	.metric-badge.bad {
		background: #fee2e2;
		color: #991b1b;
	}

	.badge {
		padding: 0.25rem 0.75rem;
		border-radius: 12px;
		font-size: 0.75rem;
		font-weight: 600;
		background: #e5e7eb;
		color: #6b7280;
	}

	.badge.active {
		background: #d1fae5;
		color: #065f46;
	}

	.empty-state {
		text-align: center;
		padding: 3rem;
		color: #6b7280;
	}

	.empty-state .icon {
		font-size: 3rem;
		display: block;
		margin-bottom: 1rem;
	}

	.hint {
		color: #6b7280;
		font-size: 0.875rem;
		margin-top: 1rem;
	}

	.error-banner {
		background: #fee2e2;
		color: #991b1b;
		padding: 1rem;
		border-radius: 8px;
		margin-bottom: 1rem;
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.error-icon {
		font-size: 1.5rem;
	}

	.loading {
		text-align: center;
		padding: 2rem;
		color: #6b7280;
	}
</style>
