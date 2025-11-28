<script>
	import { onMount, createEventDispatcher } from 'svelte';
	import OptimizationPanelV2 from './OptimizationPanelV2.svelte';

	const dispatch = createEventDispatcher();

	// Props reçus du parent
	export let config;
	export let triggerAutoSave;

	let mlMetricsV2 = {
		test_r2: -0.130,
		test_mae: 0.35,
		test_f1: 0.000,
		trades_count: 940
	};
	let loadingMLMetrics = false;
	let retrainingML = false;

	onMount(async () => {
		await loadMLMetricsV2();
	});

	async function loadMLMetricsV2() {
		if (loadingMLMetrics) return;

		loadingMLMetrics = true;

		try {
			const response = await fetch('/api/ml/models/overview');
			if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);

			const data = await response.json();
			const v2Model = data.models?.find(m => m.name === 'xgboost_v2');

			if (v2Model && v2Model.metrics) {
				mlMetricsV2 = {
					test_r2: v2Model.metrics.test?.r2 || -0.130,
					test_mae: v2Model.metrics.test?.mae || 0.35,
					test_f1: v2Model.metrics.test?.f1_score || 0.000,
					trades_count: v2Model.dataset_info?.total_samples || 0
				};
			}
		} catch (err) {
			console.error('❌ Erreur chargement métriques ML V2:', err);
		} finally {
			loadingMLMetrics = false;
		}
	}

	async function handleParamsApplied() {
		dispatch('paramsApplied');
	}

	async function retrainModelV2() {
		retrainingML = true;

		try {
			// Démarrer entraînement
			const response = await fetch('/api/ml/train_v2', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' }
			});

			if (!response.ok) throw new Error('Erreur réentraînement V2');

			const result = await response.json();
			const taskId = result.task_id;
			
			console.log('⏳ Entraînement V2 démarré, task_id:', taskId);

			// Polling du status
			let completed = false;
			let attempts = 0;
			const maxAttempts = 120; // 2 minutes max

			while (!completed && attempts < maxAttempts) {
				await new Promise(resolve => setTimeout(resolve, 1000)); // 1s
				attempts++;

				try {
					const statusRes = await fetch(`/api/ml/task/${taskId}`);
					if (!statusRes.ok) continue;

					const taskData = await statusRes.json();
					
					if (taskData.status === 'completed') {
						completed = true;
						const r2 = taskData.test_r2?.toFixed(3) || taskData.metrics?.test?.r2?.toFixed(3) || 'N/A';
						const mae = taskData.test_mae?.toFixed(3) || taskData.metrics?.test?.mae?.toFixed(3) || 'N/A';
						
						alert(`✅ Modèle V2 réentraîné!\n\nR²: ${r2}\nMAE: ${mae}%`);
						await loadMLMetricsV2();
					} else if (taskData.status === 'error') {
						throw new Error(taskData.error || 'Erreur inconnue');
					}
				} catch (pollErr) {
					console.warn('Poll attempt failed:', pollErr);
				}
			}

			if (!completed) {
				throw new Error('Timeout: entraînement trop long');
			}

		} catch (err) {
			alert(`❌ Erreur: ${err.message}`);
		} finally {
			retrainingML = false;
		}
	}
</script>

<div class="ml-v2-wrapper">
	<section class="variable-section">
		<h3>🎯 Filtrage ML V2 (Régression)</h3>
		<p class="section-desc">
			Activez le filtre pour bloquer automatiquement les opportunités avec prédiction PNL% trop faible.
		</p>

		<div class="variable-item toggle-item">
			<div class="var-header">
				<label for="ml_v2_filter_enabled">
					<span class="var-name">Activer Filtrage ML V2</span>
					<span class="var-desc">Bloquer les trades avec R² insuffisant</span>
				</label>
			</div>
			<label class="toggle">
				<input
					type="checkbox"
					id="ml_v2_filter_enabled"
					bind:checked={config.ml_v2_filter_enabled}
					on:change={() => triggerAutoSave('ml_v2_filter_enabled', config.ml_v2_filter_enabled ? 'Activé' : 'Désactivé')}
				/>
				<span class="toggle-slider"></span>
			</label>
		</div>

		<div class="variable-item" class:disabled={!config.ml_v2_filter_enabled}>
			<div class="var-header">
				<label for="ml_v2_min_confidence">
					<span class="var-name">Seuil R² Minimum</span>
					<span class="var-desc">Fixe le niveau minimal accepté (50 % → 90 %)</span>
				</label>
			</div>
			<div class="slider-container">
				<input
					type="range"
					id="ml_v2_min_confidence"
					min="0.50"
					max="0.90"
					step="0.05"
					bind:value={config.ml_v2_min_confidence}
					on:change={() => triggerAutoSave('ml_v2_min_confidence', Math.round(config.ml_v2_min_confidence * 100) + '%')}
					disabled={!config.ml_v2_filter_enabled}
				/>
				<span class="slider-value">{Math.round(config.ml_v2_min_confidence * 100)}%</span>
			</div>
		</div>
	</section>

	<section class="variable-section metrics-section">
		<h3>📊 Métriques du Modèle V2</h3>
		{#if loadingMLMetrics}
			<div class="loading-message">⏳ Chargement des métriques...</div>
		{:else}
			<div class="ml-metrics-grid">
				<div class="metric-card" class:warning={mlMetricsV2.test_r2 < 0.5} class:danger={mlMetricsV2.test_r2 < 0}>
					<span class="metric-label">R² Test</span>
					<strong class="metric-value">{mlMetricsV2.test_r2.toFixed(3)}</strong>
					<span class="metric-hint">{mlMetricsV2.test_r2 < 0 ? 'Très faible' : mlMetricsV2.test_r2 < 0.5 ? 'Amélioration conseillée' : 'Correct'}</span>
				</div>
				<div class="metric-card" class:warning={mlMetricsV2.test_mae > 0.3} class:danger={mlMetricsV2.test_mae > 0.5}>
					<span class="metric-label">MAE (%)</span>
					<strong class="metric-value">{mlMetricsV2.test_mae.toFixed(3)}%</strong>
					<span class="metric-hint">{mlMetricsV2.test_mae > 0.5 ? 'Erreur élevée' : mlMetricsV2.test_mae > 0.3 ? 'Peut mieux faire' : 'Bon'}</span>
				</div>
				<div class="metric-card" class:warning={mlMetricsV2.test_f1 < 0.3}>
					<span class="metric-label">F1 Score</span>
					<strong class="metric-value">{mlMetricsV2.test_f1.toFixed(3)}</strong>
					<span class="metric-hint">{mlMetricsV2.test_f1 < 0.3 ? 'Faible' : 'OK'}</span>
				</div>
				<div class="metric-card" class:warning={mlMetricsV2.trades_count < 500}>
					<span class="metric-label">Dataset</span>
					<strong class="metric-value">{mlMetricsV2.trades_count}</strong>
					<span class="metric-hint">{mlMetricsV2.trades_count < 500 ? 'Ajoutez des trades' : '👍 Suffisant'}</span>
				</div>
			</div>
		{/if}
	</section>

	<section class="variable-section">
		<h3>⚡ Optimisation Automatique V2 (Optuna)</h3>
		<p class="section-desc">
			Lancez une recherche bayésienne pour trouver automatiquement les hyperparamètres optimaux (500+ trades recommandés).
		</p>
		<div class="optimization-panel-wrapper">
			<OptimizationPanelV2 on:paramsApplied={handleParamsApplied} />
		</div>
	</section>

	<section class="variable-section">
		<h3>⚙️ Paramètres d'Entraînement</h3>
		<div class="subsection-grid">
			<div class="subsection-card">
				<h4>⏱️ Fenêtre & Dataset</h4>
				<div class="variable-item">
					<div class="var-header">
						<label for="ml_v2_timeframe_days">
							<span class="var-name">Timeframe (jours)</span>
							<span class="var-desc">Taille de l'historique utilisé</span>
						</label>
					</div>
					<div class="slider-container">
						<input type="range" id="ml_v2_timeframe_days" min="30" max="730" step="30" bind:value={config.ml_v2_timeframe_days} on:change={() => triggerAutoSave('ml_v2_timeframe_days', config.ml_v2_timeframe_days + ' jours')} />
						<span class="slider-value">{config.ml_v2_timeframe_days} jours</span>
					</div>
				</div>
				<div class="variable-item">
					<div class="var-header">
						<label for="ml_v2_max_features">
							<span class="var-name">Max Features</span>
							<span class="var-desc">Nombre de features conservées</span>
						</label>
					</div>
					<div class="slider-container">
						<input type="range" id="ml_v2_max_features" min="10" max="100" step="5" bind:value={config.ml_v2_max_features} on:change={() => triggerAutoSave('ml_v2_max_features', config.ml_v2_max_features)} />
						<span class="slider-value">{config.ml_v2_max_features}</span>
					</div>
				</div>
			</div>

			<div class="subsection-card">
				<h4>🧹 Nettoyage & Split</h4>
				<div class="variable-item">
					<div class="var-header">
						<label for="ml_v2_marginal_threshold">
							<span class="var-name">Marginal Threshold</span>
							<span class="var-desc">Ignore les trades |PNL| &lt; seuil</span>
						</label>
					</div>
					<div class="slider-container">
						<input type="range" id="ml_v2_marginal_threshold" min="0.05" max="1.0" step="0.05" bind:value={config.ml_v2_marginal_threshold} on:change={() => triggerAutoSave('ml_v2_marginal_threshold', config.ml_v2_marginal_threshold.toFixed(2) + '%')} />
						<span class="slider-value">{config.ml_v2_marginal_threshold.toFixed(2)}%</span>
					</div>
				</div>

				<div class="variable-item toggle-item">
					<div class="var-header">
						<label for="ml_v2_filter_marginal_trades">
							<span class="var-name">Filtrer Trades Marginaux</span>
							<span class="var-desc">Retire les trades trop proches de 0%</span>
						</label>
					</div>
					<label class="toggle">
						<input type="checkbox" id="ml_v2_filter_marginal_trades" bind:checked={config.ml_v2_filter_marginal_trades} on:change={() => triggerAutoSave('ml_v2_filter_marginal_trades', config.ml_v2_filter_marginal_trades ? 'Activé' : 'Désactivé')} />
						<span class="toggle-slider"></span>
					</label>
				</div>

				<div class="split-grid">
					<div class="variable-item">
						<div class="var-header">
							<label for="ml_v2_test_size">
								<span class="var-name">Test Size</span>
								<span class="var-desc">Part du dataset réservée au test</span>
							</label>
						</div>
						<div class="slider-container">
							<input type="range" id="ml_v2_test_size" min="0.05" max="0.40" step="0.05" bind:value={config.ml_v2_test_size} on:change={() => triggerAutoSave('ml_v2_test_size', Math.round(config.ml_v2_test_size * 100) + '%')} />
							<span class="slider-value">{Math.round(config.ml_v2_test_size * 100)}%</span>
						</div>
					</div>
					<div class="variable-item">
						<div class="var-header">
							<label for="ml_v2_validation_size">
								<span class="var-name">Validation Size</span>
								<span class="var-desc">Part dédiée à la validation</span>
							</label>
						</div>
						<div class="slider-container">
							<input type="range" id="ml_v2_validation_size" min="0.05" max="0.30" step="0.05" bind:value={config.ml_v2_validation_size} on:change={() => triggerAutoSave('ml_v2_validation_size', Math.round(config.ml_v2_validation_size * 100) + '%')} />
							<span class="slider-value">{Math.round(config.ml_v2_validation_size * 100)}%</span>
						</div>
					</div>
				</div>
			</div>
		</div>
	</section>

	<section class="variable-section">
		<h3>⚙️ Hyperparamètres XGBoost V2</h3>
		<div class="subsection-grid">
			<div class="subsection-card">
				<h4>🌳 Configuration Arbres</h4>
				{#each [
					{ id: 'ml_v2_n_estimators', label: 'N Estimators', desc: 'Nombre total d\'arbres', min: 100, max: 1000, step: 50 },
					{ id: 'ml_v2_learning_rate', label: 'Learning Rate', desc: 'Taux d\'apprentissage', min: 0.001, max: 0.3, step: 0.001 }
				] as slider (slider.id)}
					<div class="variable-item">
						<div class="var-header">
							<label for={slider.id}>
								<span class="var-name">{slider.label}</span>
								<span class="var-desc">{slider.desc}</span>
							</label>
						</div>
						<div class="slider-container">
							<input
								type="range"
								id={slider.id}
								min={slider.min}
								max={slider.max}
								step={slider.step}
								bind:value={config[slider.id]}
								on:change={() => triggerAutoSave(slider.id, typeof config[slider.id] === 'number' ? Number(config[slider.id]) : config[slider.id])}
							/>
							<span class="slider-value">{slider.id === 'ml_v2_learning_rate' ? Number(config[slider.id]).toFixed(3) : config[slider.id]}</span>
						</div>
					</div>
				{/each}
				<div class="variable-item">
					<div class="var-header">
						<label for="ml_v2_max_depth">
							<span class="var-name">Max Depth</span>
							<span class="var-desc">Profondeur maximale des arbres</span>
						</label>
					</div>
					<select id="ml_v2_max_depth" bind:value={config.ml_v2_max_depth} on:change={() => triggerAutoSave('ml_v2_max_depth', config.ml_v2_max_depth)}>
						{#each [2, 3, 4, 5, 6] as depth}
							<option value={depth}>{depth}</option>
						{/each}
					</select>
				</div>
			</div>

			<div class="subsection-card">
				<h4>🛡️ Régularisation</h4>
				{#each [
					{ id: 'ml_v2_min_child_weight', label: 'Min Child Weight', desc: 'Samples min par feuille', min: 1, max: 20, step: 1 },
					{ id: 'ml_v2_reg_alpha', label: 'Régularisation L1 (Alpha)', desc: 'Lasso regularization', min: 0, max: 10, step: 0.1 },
					{ id: 'ml_v2_reg_lambda', label: 'Régularisation L2 (Lambda)', desc: 'Ridge regularization', min: 0, max: 10, step: 0.1 },
					{ id: 'ml_v2_gamma', label: 'Gamma', desc: 'Gain minimal pour split', min: 0, max: 5, step: 0.1 }
				] as slider (slider.id)}
					<div class="variable-item">
						<div class="var-header">
							<label for={slider.id}>
								<span class="var-name">{slider.label}</span>
								<span class="var-desc">{slider.desc}</span>
							</label>
						</div>
						<div class="slider-container">
							<input type="range" id={slider.id} min={slider.min} max={slider.max} step={slider.step} bind:value={config[slider.id]} on:change={() => triggerAutoSave(slider.id, Number(config[slider.id]).toFixed(slider.step < 1 ? 1 : 0))} />
							<span class="slider-value">{Number(config[slider.id]).toFixed(slider.step < 1 ? 1 : 0)}</span>
						</div>
					</div>
				{/each}
			</div>

			<div class="subsection-card">
				<h4>🎲 Sampling</h4>
				{#each [
					{ id: 'ml_v2_subsample', label: 'Subsample', desc: '% de données par arbre', min: 0.5, max: 1, step: 0.05 },
					{ id: 'ml_v2_colsample_bytree', label: 'Colsample by Tree', desc: '% features par arbre', min: 0.5, max: 1, step: 0.05 }
				] as slider (slider.id)}
					<div class="variable-item">
						<div class="var-header">
							<label for={slider.id}>
								<span class="var-name">{slider.label}</span>
								<span class="var-desc">{slider.desc}</span>
							</label>
						</div>
						<div class="slider-container">
							<input type="range" id={slider.id} min={slider.min} max={slider.max} step={slider.step} bind:value={config[slider.id]} on:change={() => triggerAutoSave(slider.id, Number(config[slider.id]).toFixed(2))} />
							<span class="slider-value">{Number(config[slider.id]).toFixed(2)}</span>
						</div>
					</div>
				{/each}
			</div>
		</div>

		<div class="retrain-card">
			<div>
				<h4>🚀 Réentraîner Modèle V2</h4>
				<p>Utilise les paramètres ci-dessus pour générer un nouveau modèle (split temporel).</p>
			</div>
			<button class="btn-retrain" on:click={retrainModelV2} disabled={retrainingML}>
				{retrainingML ? '⏳ Réentraînement en cours...' : 'Réentraîner maintenant'}
			</button>
		</div>
	</section>
</div>

<style>
	.ml-v2-wrapper {
		display: flex;
		flex-direction: column;
		gap: 24px;
	}

	.variable-section {
		background: rgba(7, 11, 30, 0.85);
		border: 1px solid rgba(255, 255, 255, 0.05);
		border-radius: 12px;
		padding: 24px;
		box-shadow: 0 10px 25px rgba(0, 0, 0, 0.25);
	}

	.subsection-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
		gap: 16px;
		margin-top: 16px;
	}

	.subsection-card {
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid rgba(255, 255, 255, 0.05);
		border-radius: 10px;
		padding: 16px;
	}

	.var-header {
		display: flex;
		gap: 8px;
		flex-direction: column;
	}

	.var-name {
		font-weight: 600;
		color: #f8fafc;
	}

	.var-desc {
		font-size: 13px;
		color: #7f8ba7;
	}

	.toggle-item {
		align-items: center;
		justify-content: space-between;
	}

	.slider-container {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 10px 14px;
		border-radius: 10px;
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid rgba(255, 255, 255, 0.05);
	}

	.slider-value {
		min-width: 60px;
		font-family: 'Space Mono', monospace;
		text-align: right;
		padding: 3px 10px;
		border-radius: 999px;
		background: rgba(0, 255, 136, 0.1);
		border: 1px solid rgba(0, 255, 136, 0.4);
		color: #6ee7b7;
		font-size: 0.85rem;
		font-weight: 500;
	}

	.ml-metrics-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 16px;
	}

	.metric-card {
		background: rgba(0, 0, 0, 0.25);
		border-radius: 10px;
		padding: 14px;
		border: 1px solid rgba(255, 255, 255, 0.05);
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.metric-card .metric-label {
		color: #9ca3af;
		font-size: 13px;
	}

	.metric-card .metric-value {
		font-size: 22px;
		color: #f8fafc;
	}

	.metric-card .metric-hint {
		font-size: 12px;
		color: #94a3b8;
	}

	.metric-card.warning {
		border-color: rgba(250, 204, 21, 0.4);
	}

	.metric-card.danger {
		border-color: rgba(248, 113, 113, 0.4);
	}

	.optimization-panel-wrapper {
		border-radius: 12px;
		background: rgba(255, 255, 255, 0.01);
		border: 1px solid rgba(255, 255, 255, 0.04);
		padding: 16px;
	}

	.split-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 12px;
	}

	.retrain-card {
		margin-top: 20px;
		padding: 16px;
		border-radius: 10px;
		background: linear-gradient(135deg, rgba(59, 130, 246, 0.15), rgba(16, 185, 129, 0.12));
		border: 1px solid rgba(59, 130, 246, 0.3);
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
	}

	button.btn-retrain {
		padding: 0.75rem 1.5rem;
		border: none;
		border-radius: 8px;
		font-weight: 600;
		cursor: pointer;
		background: linear-gradient(135deg, #22d3ee, #0ea5e9);
		color: #0f172a;
		transition: transform 0.2s ease;
	}

	button.btn-retrain:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	button.btn-retrain:not(:disabled):hover {
		transform: translateY(-2px);
	}
</style>
