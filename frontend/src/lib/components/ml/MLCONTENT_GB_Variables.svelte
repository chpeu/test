<script>
	import { onMount, createEventDispatcher } from 'svelte';

	const dispatch = createEventDispatcher();

	// Props reçus du parent
	export let config;
	export let triggerAutoSave;

	let mlMetricsGB = {
		test_accuracy: 64.3,
		test_f1: 0.415,
		test_precision: 0.629,
		overfitting_gap: 12.7,
		trades_count: 2893
	};
	let loadingMLMetrics = false;
	
	// 🔢 Stats trades ML filtrés
	let mlTradesStats = null;
	let loadingTradesStats = false;
	let retrainingML = false;
	let verifyingML = false;
	let verifyResult = null;
	
	// Optuna optimization state
	let optimizingOptuna = false;
	let optunaProgress = 0;
	let optunaStatus = null;
	let optunaPollingInterval = null;
	
	// Vérification complète
	let verifyingComplete = false;
	let verifyCompleteResult = null;
	
	// Type de modèle: 'gb' = GradientBoosting, 'histgb' = HistGradientBoosting (10x plus rapide)
	let modelType = config.gb_model_type || 'gb';

	onMount(async () => {
		await loadMLMetricsGB();
		await loadMLTradesStats();
	});
	
	// 🔢 Charger stats trades ML filtrés
	async function loadMLTradesStats() {
		if (loadingTradesStats) return;
		loadingTradesStats = true;
		
		try {
			const response = await fetch('/api/ml/dashboard/ml_trades_count');
			if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);
			mlTradesStats = await response.json();
		} catch (err) {
			console.error('❌ Erreur chargement stats trades ML:', err);
			mlTradesStats = null;
		} finally {
			loadingTradesStats = false;
		}
	}
	
	function setModelType(type) {
		modelType = type;
		config.gb_model_type = type;
		triggerAutoSave('gb_model_type', type === 'histgb' ? 'HistGradientBoosting (Rapide)' : 'GradientBoosting (Standard)');
	}

	async function loadMLMetricsGB() {
		if (loadingMLMetrics) return;

		loadingMLMetrics = true;

		try {
			const response = await fetch('/api/ml/models/overview');
			if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);

			const data = await response.json();
			// Chercher le modèle GradientBoosting optimisé
			const gbModel = data.models?.find(m => 
				m.name === 'optimized_classifier' || 
				m.name === 'best_classifier' ||
				m.name === 'gradientboosting'
			);

			if (gbModel && gbModel.metrics) {
				mlMetricsGB = {
					test_accuracy: (gbModel.metrics.test?.accuracy || 0.643) * 100,
					test_f1: gbModel.metrics.test?.f1_score || 0.415,
					test_precision: gbModel.metrics.test?.precision || 0.629,
					overfitting_gap: gbModel.overfitting_gap || 12.7,
					trades_count: gbModel.dataset_info?.total_samples || 2893
				};
			}
		} catch (err) {
			console.error('❌ Erreur chargement métriques GradientBoosting:', err);
			// Utiliser les valeurs par défaut (modèle actuel)
		} finally {
			loadingMLMetrics = false;
		}
	}

	async function handleParamsApplied() {
		dispatch('paramsApplied');
	}

	async function retrainModelGB() {
		retrainingML = true;

		try {
			const response = await fetch('/api/ml/train_gb', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					n_estimators: config.gb_n_estimators,
					max_depth: config.gb_max_depth,
					learning_rate: config.gb_learning_rate,
					min_samples_split: config.gb_min_samples_split,
					min_samples_leaf: config.gb_min_samples_leaf,
					subsample: config.gb_subsample,
					max_features: config.gb_max_features
				})
			});

			if (!response.ok) throw new Error('Erreur réentraînement GradientBoosting');

			const result = await response.json();
			
			if (result.status === 'success' || result.task_id) {
				// Polling si task async
				if (result.task_id) {
					let completed = false;
					let attempts = 0;
					const maxAttempts = 120;

					while (!completed && attempts < maxAttempts) {
						await new Promise(resolve => setTimeout(resolve, 1000));
						attempts++;

						try {
							const statusRes = await fetch(`/api/ml/task/${result.task_id}`);
							if (!statusRes.ok) continue;

							const taskData = await statusRes.json();
							
							if (taskData.status === 'completed') {
								completed = true;
								alert(`✅ Modèle GradientBoosting réentraîné!\n\nAccuracy: ${(taskData.accuracy * 100).toFixed(1)}%\nF1: ${taskData.f1?.toFixed(3) || 'N/A'}`);
								await loadMLMetricsGB();
							} else if (taskData.status === 'error') {
								throw new Error(taskData.error || 'Erreur inconnue');
							}
						} catch (pollErr) {
							console.warn('Poll attempt failed:', pollErr);
						}
					}
				} else {
					alert(`✅ Modèle GradientBoosting réentraîné!\n\nAccuracy: ${(result.accuracy * 100).toFixed(1)}%`);
					await loadMLMetricsGB();
				}
			}

		} catch (err) {
			alert(`❌ Erreur: ${err.message}`);
		} finally {
			retrainingML = false;
		}
	}

	async function verifyModel() {
		verifyingML = true;
		verifyResult = null;

		try {
			const response = await fetch('/api/ml/verify_gb', {
				method: 'POST'
			});

			if (!response.ok) throw new Error('Erreur vérification');

			verifyResult = await response.json();
		} catch (err) {
			verifyResult = { status: 'error', message: err.message };
		} finally {
			verifyingML = false;
		}
	}
	
	// 🔬 Optimisation Optuna
	async function startOptunaOptimization() {
		optimizingOptuna = true;
		optunaProgress = 0;
		optunaStatus = { status: 'starting', message: 'Démarrage de l\'optimisation...' };
		
		try {
			const response = await fetch('/api/ml/optimize_gb?n_trials=100&timeout_minutes=30', {
				method: 'POST'
			});
			
			if (!response.ok) throw new Error('Erreur démarrage optimisation');
			
			const result = await response.json();
			
			if (result.success) {
				// Démarrer le polling
				optunaPollingInterval = setInterval(pollOptunaStatus, 2000);
			} else {
				throw new Error(result.error || 'Erreur inconnue');
			}
		} catch (err) {
			optunaStatus = { status: 'error', message: err.message };
			optimizingOptuna = false;
		}
	}
	
	async function pollOptunaStatus() {
		try {
			const response = await fetch('/api/ml/optimize_gb/status');
			if (!response.ok) return;
			
			const status = await response.json();
			optunaProgress = status.progress || 0;
			optunaStatus = status;
			
			if (status.status === 'completed') {
				clearInterval(optunaPollingInterval);
				optimizingOptuna = false;
				optunaStatus = {
					...status,
					message: `✅ Optimisation terminée! Best F1=${(status.best_score * 100).toFixed(1)}%`
				};
			} else if (status.status === 'error') {
				clearInterval(optunaPollingInterval);
				optimizingOptuna = false;
			}
		} catch (err) {
			console.error('Erreur polling Optuna:', err);
		}
	}
	
	async function applyOptunaParams() {
		try {
			const response = await fetch('/api/ml/optimize_gb/apply', {
				method: 'POST'
			});
			
			if (!response.ok) throw new Error('Erreur application paramètres');
			
			const result = await response.json();
			
			if (result.success) {
				// Mettre à jour config local avec les nouveaux params
				if (result.applied_params) {
					Object.assign(config, result.applied_params);
				}
				optunaStatus = {
					...optunaStatus,
					applied: true,
					message: `✅ ${Object.keys(result.applied_params || {}).length} paramètres appliqués!`
				};
			}
		} catch (err) {
			console.error('Erreur application params:', err);
		}
	}
	
	// 🔍 Vérification complète
	async function runCompleteVerification() {
		verifyingComplete = true;
		verifyCompleteResult = null;
		
		try {
			const response = await fetch('/api/ml/verify_gb/complete');
			if (!response.ok) throw new Error('Erreur vérification');
			
			verifyCompleteResult = await response.json();
		} catch (err) {
			verifyCompleteResult = { overall_status: 'ERROR', errors: [err.message] };
		} finally {
			verifyingComplete = false;
		}
	}
</script>

<div class="ml-gb-wrapper">
	<!-- Info Banner -->
	<div class="info-banner">
		<div class="banner-icon">🎯</div>
		<div class="banner-content">
			<h4>GradientBoosting Optimisé</h4>
			<p>Ce modèle a été optimisé pour atteindre <strong>64-69% d'accuracy</strong> (vs ~50% pour XGBoost V1). 
			Il utilise des features temporelles (heures favorables) et une forte régularisation pour éviter l'overfitting.</p>
		</div>
	</div>

	<!-- Sélection Type de Modèle -->
	<section class="variable-section model-type-section">
		<h3>⚡ Type de Modèle</h3>
		<p class="section-desc">
			Choisissez l'algorithme d'entraînement. HistGradientBoosting est <strong>10x plus rapide</strong> avec des performances similaires.
		</p>
		
		<div class="model-type-selector">
			<button 
				class="model-type-btn" 
				class:active={modelType === 'gb'}
				on:click={() => setModelType('gb')}
			>
				<span class="model-icon">🌳</span>
				<div class="model-info">
					<span class="model-name">GradientBoosting</span>
					<span class="model-desc">Standard - Plus précis sur petits datasets</span>
				</div>
				<span class="model-speed">1x</span>
			</button>
			
			<button 
				class="model-type-btn" 
				class:active={modelType === 'histgb'}
				on:click={() => setModelType('histgb')}
			>
				<span class="model-icon">⚡</span>
				<div class="model-info">
					<span class="model-name">HistGradientBoosting</span>
					<span class="model-desc">Rapide - Idéal pour Optuna (100+ trials)</span>
				</div>
				<span class="model-speed">10x</span>
			</button>
		</div>
		
		<div class="model-comparison">
			<div class="comparison-item">
				<span class="comp-label">Vitesse entraînement</span>
				<div class="comp-bars">
					<div class="comp-bar gb" style="width: {modelType === 'gb' ? '30%' : '15%'}">GB</div>
					<div class="comp-bar histgb" style="width: {modelType === 'histgb' ? '100%' : '50%'}">HistGB</div>
				</div>
			</div>
			<div class="comparison-item">
				<span class="comp-label">Optuna 100 trials</span>
				<span class="comp-value">{modelType === 'histgb' ? '~2-5 min' : '~15-30 min'}</span>
			</div>
			<div class="comparison-item">
				<span class="comp-label">Accuracy attendue</span>
				<span class="comp-value">~64% (équivalent)</span>
			</div>
		</div>
	</section>

	<!-- Filtrage ML -->
	<section class="variable-section">
		<h3>🎯 Filtrage ML GradientBoosting</h3>
		<p class="section-desc">
			Activez le filtre pour bloquer automatiquement les trades avec faible probabilité de succès.
		</p>

		<div class="variable-item toggle-item">
			<div class="var-header">
				<label for="gb_filter_enabled">
					<span class="var-name">Activer Filtrage GradientBoosting</span>
					<span class="var-desc">Bloquer les trades avec confiance &lt; seuil</span>
				</label>
			</div>
			<label class="toggle">
				<input
					type="checkbox"
					id="gb_filter_enabled"
					bind:checked={config.gb_filter_enabled}
					on:change={() => triggerAutoSave('gb_filter_enabled', config.gb_filter_enabled ? 'Activé' : 'Désactivé')}
				/>
				<span class="toggle-slider"></span>
			</label>
		</div>

		<div class="variable-item" class:disabled={!config.gb_filter_enabled}>
			<div class="var-header">
				<label for="gb_min_confidence">
					<span class="var-name">Seuil de Confiance Minimum</span>
					<span class="var-desc">Probabilité minimale de WIN pour accepter le trade (50-80%)</span>
				</label>
			</div>
			<div class="slider-container">
				<input
					type="range"
					id="gb_min_confidence"
					min="0.50"
					max="0.80"
					step="0.05"
					bind:value={config.gb_min_confidence}
					on:change={() => triggerAutoSave('gb_min_confidence', Math.round(config.gb_min_confidence * 100) + '%')}
					disabled={!config.gb_filter_enabled}
				/>
				<span class="slider-value">{Math.round(config.gb_min_confidence * 100)}%</span>
			</div>
		</div>
	</section>

	<!-- Métriques -->
	<section class="variable-section metrics-section">
		<h3>📊 Métriques du Modèle GradientBoosting</h3>
		{#if loadingMLMetrics}
			<div class="loading-message">⏳ Chargement des métriques...</div>
		{:else}
			<div class="ml-metrics-grid">
				<div class="metric-card" class:good={mlMetricsGB.test_accuracy >= 60} class:ok={mlMetricsGB.test_accuracy >= 55 && mlMetricsGB.test_accuracy < 60} class:warning={mlMetricsGB.test_accuracy < 55}>
					<span class="metric-label">Test Accuracy</span>
					<strong class="metric-value">{mlMetricsGB.test_accuracy.toFixed(1)}%</strong>
					<span class="metric-hint">{mlMetricsGB.test_accuracy >= 60 ? '🎉 Excellent' : mlMetricsGB.test_accuracy >= 55 ? '✅ Bon' : '⚠️ À améliorer'}</span>
				</div>
				<div class="metric-card" class:good={mlMetricsGB.test_f1 >= 0.4} class:warning={mlMetricsGB.test_f1 < 0.4}>
					<span class="metric-label">F1 Score</span>
					<strong class="metric-value">{mlMetricsGB.test_f1.toFixed(3)}</strong>
					<span class="metric-hint">{mlMetricsGB.test_f1 >= 0.4 ? 'Bon équilibre' : 'Modéré'}</span>
				</div>
				<div class="metric-card" class:good={mlMetricsGB.test_precision >= 0.6}>
					<span class="metric-label">Precision</span>
					<strong class="metric-value">{mlMetricsGB.test_precision.toFixed(3)}</strong>
					<span class="metric-hint">{mlMetricsGB.test_precision >= 0.6 ? 'Peu de faux positifs' : 'OK'}</span>
				</div>
				<div class="metric-card" class:good={mlMetricsGB.overfitting_gap <= 15} class:warning={mlMetricsGB.overfitting_gap > 15 && mlMetricsGB.overfitting_gap <= 25} class:danger={mlMetricsGB.overfitting_gap > 25}>
					<span class="metric-label">Overfitting Gap</span>
					<strong class="metric-value">{mlMetricsGB.overfitting_gap.toFixed(1)}%</strong>
					<span class="metric-hint">{mlMetricsGB.overfitting_gap <= 15 ? 'Stable' : mlMetricsGB.overfitting_gap <= 25 ? 'Modéré' : 'Élevé'}</span>
				</div>
				<div class="metric-card" class:good={mlMetricsGB.trades_count >= 1000} class:ok={mlMetricsGB.trades_count >= 500} class:warning={mlMetricsGB.trades_count < 500}>
					<span class="metric-label">Dataset</span>
					<strong class="metric-value">{mlMetricsGB.trades_count.toLocaleString()}</strong>
					<span class="metric-hint">{mlMetricsGB.trades_count >= 1000 ? '👍 Excellent' : mlMetricsGB.trades_count >= 500 ? 'Suffisant' : 'Besoin de plus'}</span>
				</div>
			</div>
		{/if}
	</section>

	<!-- 🔢 Stats Trades ML -->
	<section class="variable-section trades-stats-section">
		<h3>🔢 Données ML Disponibles</h3>
		<p class="section-desc">
			Nombre de trades utilisables pour l'entraînement ML après filtrage (exclusion des trades manuels et configs différentes).
		</p>
		
		{#if loadingTradesStats}
			<div class="loading-message">⏳ Chargement des stats...</div>
		{:else if mlTradesStats}
			<div class="trades-stats-grid">
				<div class="stat-card total">
					<span class="stat-icon">📊</span>
					<div class="stat-content">
						<span class="stat-value">{mlTradesStats.total_trades?.toLocaleString() || 0}</span>
						<span class="stat-label">Trades Total</span>
					</div>
				</div>
				
				<div class="stat-card excluded">
					<span class="stat-icon">🚫</span>
					<div class="stat-content">
						<span class="stat-value">-{mlTradesStats.manual_excluded || 0}</span>
						<span class="stat-label">Manuels exclus</span>
					</div>
				</div>
				
				<div class="stat-card excluded">
					<span class="stat-icon">⚙️</span>
					<div class="stat-content">
						<span class="stat-value">-{mlTradesStats.different_config_excluded || 0}</span>
						<span class="stat-label">Configs différentes</span>
					</div>
				</div>
				
				<div class="stat-card final" class:good={mlTradesStats.config_filtered_trades >= 500} class:warning={mlTradesStats.config_filtered_trades < 500}>
					<span class="stat-icon">✅</span>
					<div class="stat-content">
						<span class="stat-value">{mlTradesStats.config_filtered_trades?.toLocaleString() || 0}</span>
						<span class="stat-label">Trades ML utilisables</span>
					</div>
				</div>
			</div>
			
			{#if mlTradesStats.current_config}
				<div class="config-info">
					<strong>Config actuelle:</strong>
					min_score={mlTradesStats.current_config.min_score}, 
					snr={mlTradesStats.current_config.snr_threshold}, 
					vol_mult={mlTradesStats.current_config.volume_mult}
				</div>
			{/if}
			
			<button class="refresh-btn" on:click={loadMLTradesStats} disabled={loadingTradesStats}>
				🔄 Rafraîchir
			</button>
		{:else}
			<div class="error-message">❌ Impossible de charger les stats</div>
		{/if}
	</section>

	<!-- Hyperparamètres -->
	<section class="variable-section">
		<h3>⚙️ Hyperparamètres GradientBoosting</h3>
		<p class="section-desc">
			Ces paramètres ont été optimisés pour réduire l'overfitting tout en gardant une bonne accuracy.
		</p>

		<div class="subsection-grid">
			<div class="subsection-card">
				<h4>🌳 Configuration Arbres</h4>
				<div class="variable-item">
					<div class="var-header">
						<label for="gb_n_estimators">
							<span class="var-name">N Estimators</span>
							<span class="var-desc">Nombre total d'arbres</span>
						</label>
					</div>
					<div class="slider-container">
						<input type="range" id="gb_n_estimators" min="50" max="500" step="25" bind:value={config.gb_n_estimators} on:change={() => triggerAutoSave('gb_n_estimators', config.gb_n_estimators)} />
						<span class="slider-value">{config.gb_n_estimators}</span>
					</div>
				</div>
				<div class="variable-item">
					<div class="var-header">
						<label for="gb_max_depth">
							<span class="var-name">Max Depth</span>
							<span class="var-desc">Profondeur max des arbres (↓ réduit overfitting)</span>
						</label>
					</div>
					<select id="gb_max_depth" bind:value={config.gb_max_depth} on:change={() => triggerAutoSave('gb_max_depth', config.gb_max_depth)} class="select-input">
						<option value={2}>2 (très conservateur)</option>
						<option value={3}>3 (recommandé)</option>
						<option value={4}>4 (modéré)</option>
						<option value={5}>5 (agressif)</option>
					</select>
				</div>
				<div class="variable-item">
					<div class="var-header">
						<label for="gb_learning_rate">
							<span class="var-name">Learning Rate</span>
							<span class="var-desc">Taux d'apprentissage (↓ plus stable)</span>
						</label>
					</div>
					<div class="slider-container">
						<input type="range" id="gb_learning_rate" min="0.01" max="0.15" step="0.01" bind:value={config.gb_learning_rate} on:change={() => triggerAutoSave('gb_learning_rate', config.gb_learning_rate.toFixed(2))} />
						<span class="slider-value">{config.gb_learning_rate.toFixed(2)}</span>
					</div>
				</div>
			</div>

			<div class="subsection-card">
				<h4>🛡️ Régularisation</h4>
				<div class="variable-item">
					<div class="var-header">
						<label for="gb_min_samples_split">
							<span class="var-name">Min Samples Split</span>
							<span class="var-desc">Samples minimum pour diviser un noeud</span>
						</label>
					</div>
					<div class="slider-container">
						<input type="range" id="gb_min_samples_split" min="5" max="50" step="5" bind:value={config.gb_min_samples_split} on:change={() => triggerAutoSave('gb_min_samples_split', config.gb_min_samples_split)} />
						<span class="slider-value">{config.gb_min_samples_split}</span>
					</div>
				</div>
				<div class="variable-item">
					<div class="var-header">
						<label for="gb_min_samples_leaf">
							<span class="var-name">Min Samples Leaf</span>
							<span class="var-desc">Samples minimum par feuille</span>
						</label>
					</div>
					<div class="slider-container">
						<input type="range" id="gb_min_samples_leaf" min="5" max="30" step="5" bind:value={config.gb_min_samples_leaf} on:change={() => triggerAutoSave('gb_min_samples_leaf', config.gb_min_samples_leaf)} />
						<span class="slider-value">{config.gb_min_samples_leaf}</span>
					</div>
				</div>
			</div>

			<div class="subsection-card">
				<h4>🎲 Sampling</h4>
				<div class="variable-item">
					<div class="var-header">
						<label for="gb_subsample">
							<span class="var-name">Subsample</span>
							<span class="var-desc">% de données par arbre</span>
						</label>
					</div>
					<div class="slider-container">
						<input type="range" id="gb_subsample" min="0.5" max="1.0" step="0.05" bind:value={config.gb_subsample} on:change={() => triggerAutoSave('gb_subsample', config.gb_subsample.toFixed(2))} />
						<span class="slider-value">{config.gb_subsample.toFixed(2)}</span>
					</div>
				</div>
				<div class="variable-item">
					<div class="var-header">
						<label for="gb_max_features">
							<span class="var-name">Max Features</span>
							<span class="var-desc">% de features par split</span>
						</label>
					</div>
					<div class="slider-container">
						<input type="range" id="gb_max_features" min="0.3" max="1.0" step="0.1" bind:value={config.gb_max_features} on:change={() => triggerAutoSave('gb_max_features', config.gb_max_features.toFixed(1))} />
						<span class="slider-value">{config.gb_max_features.toFixed(1)}</span>
					</div>
				</div>
			</div>
		</div>

		<div class="action-buttons">
			<div class="retrain-card">
				<div>
					<h4>🚀 Réentraîner Modèle</h4>
					<p>Génère un nouveau modèle avec les paramètres ci-dessus.</p>
				</div>
				<button class="btn-retrain" on:click={retrainModelGB} disabled={retrainingML}>
					{retrainingML ? '⏳ Réentraînement...' : 'Réentraîner'}
				</button>
			</div>

			<div class="verify-card">
				<div>
					<h4>🔍 Vérifier Modèle</h4>
					<p>Teste le modèle sur les données récentes.</p>
				</div>
				<button class="btn-verify" on:click={verifyModel} disabled={verifyingML}>
					{verifyingML ? '⏳ Vérification...' : 'Vérifier'}
				</button>
			</div>
		</div>
		
		<!-- 🔬 Optuna Optimization -->
		<div class="optuna-section">
			<div class="optuna-header">
				<h4>🔬 Optimisation Automatique (Optuna)</h4>
				<p>Recherche automatique des meilleurs hyperparamètres (~100 trials, ~15-30 min)</p>
			</div>
			
			<div class="optuna-actions">
				<button 
					class="btn-optuna" 
					on:click={startOptunaOptimization} 
					disabled={optimizingOptuna}
				>
					{#if optimizingOptuna}
						⏳ Optimisation en cours... ({optunaProgress}%)
					{:else}
						🔬 Lancer Optimisation Optuna
					{/if}
				</button>
				
				{#if optunaStatus?.status === 'completed' && !optunaStatus?.applied}
					<button class="btn-apply-optuna" on:click={applyOptunaParams}>
						✅ Appliquer les meilleurs paramètres
					</button>
				{/if}
			</div>
			
			{#if optimizingOptuna}
				<div class="optuna-progress">
					<div class="progress-bar">
						<div class="progress-fill" style="width: {optunaProgress}%"></div>
					</div>
					<span class="progress-text">Trial {optunaStatus?.current_trial || 0}/{optunaStatus?.total_trials || 100}</span>
				</div>
			{/if}
			
			{#if optunaStatus?.best_params}
				<div class="optuna-result" class:success={optunaStatus.status === 'completed'}>
					<h5>🎯 Meilleurs paramètres trouvés (F1: {(optunaStatus.best_score * 100).toFixed(1)}%)</h5>
					<div class="params-grid">
						{#each Object.entries(optunaStatus.best_params) as [key, value]}
							<div class="param-item">
								<span class="param-key">{key}</span>
								<span class="param-value">{typeof value === 'number' ? value.toFixed(4) : value}</span>
							</div>
						{/each}
					</div>
					{#if optunaStatus.applied}
						<div class="applied-badge">✅ Appliqué</div>
					{/if}
				</div>
			{/if}
		</div>
		
		<!-- 🔍 Vérification Complète -->
		<div class="verify-complete-section">
			<div class="verify-header">
				<h4>🔍 Boucle de Vérification Complète</h4>
				<p>Vérifie la configuration, le modèle, et la cohérence du système</p>
			</div>
			
			<button 
				class="btn-verify-complete" 
				on:click={runCompleteVerification} 
				disabled={verifyingComplete}
			>
				{verifyingComplete ? '⏳ Vérification...' : '🔍 Lancer Vérification Complète'}
			</button>
			
			{#if verifyCompleteResult}
				<div class="verify-complete-result" class:ok={verifyCompleteResult.overall_status === 'OK'} class:warning={verifyCompleteResult.overall_status === 'WARNING'} class:error={verifyCompleteResult.overall_status === 'ERROR'}>
					<div class="result-header">
						{#if verifyCompleteResult.overall_status === 'OK'}
							✅ Système OK
						{:else if verifyCompleteResult.overall_status === 'WARNING'}
							⚠️ Avertissements détectés
						{:else}
							❌ Erreurs détectées
						{/if}
						<span class="result-summary">
							{verifyCompleteResult.summary?.ok || 0} OK / {verifyCompleteResult.summary?.warnings || 0} Warn / {verifyCompleteResult.summary?.errors || 0} Err
						</span>
					</div>
					
					<div class="checks-list">
						{#each verifyCompleteResult.checks || [] as check}
							<div class="check-item" class:ok={check.status === 'OK'} class:warning={check.status === 'WARNING'} class:error={check.status === 'ERROR'}>
								<span class="check-icon">
									{#if check.status === 'OK'}✅{:else if check.status === 'WARNING'}⚠️{:else}❌{/if}
								</span>
								<span class="check-name">{check.name}</span>
								<span class="check-details">{check.details}</span>
							</div>
						{/each}
					</div>
				</div>
			{/if}
		</div>

		{#if verifyResult}
			<div class="verify-result" class:success={verifyResult.status === 'PASS'} class:error={verifyResult.status === 'error' || verifyResult.status === 'FAIL'}>
				{#if verifyResult.status === 'PASS'}
					<span>✅ Modèle valide - Accuracy: {(verifyResult.accuracy * 100).toFixed(1)}%</span>
				{:else if verifyResult.status === 'error'}
					<span>❌ Erreur: {verifyResult.message}</span>
				{:else}
					<span>⚠️ Modèle non performant: {verifyResult.message}</span>
				{/if}
			</div>
		{/if}
	</section>

	<!-- Features Info -->
	<section class="variable-section info-section">
		<h3>ℹ️ Features Importantes</h3>
		<div class="features-grid">
			<div class="feature-card">
				<span class="feature-icon">🕐</span>
				<div>
					<h5>Heures Favorables (UTC)</h5>
					<p class="good">2h, 12h, 16h → Win rate ~55%</p>
				</div>
			</div>
			<div class="feature-card">
				<span class="feature-icon">⚠️</span>
				<div>
					<h5>Heures Défavorables (UTC)</h5>
					<p class="bad">4h, 18h, 23h → Win rate ~35%</p>
				</div>
			</div>
			<div class="feature-card">
				<span class="feature-icon">📈</span>
				<div>
					<h5>RSI Momentum</h5>
					<p>Différence RSI 1m vs 5m</p>
				</div>
			</div>
			<div class="feature-card">
				<span class="feature-icon">📊</span>
				<div>
					<h5>MACD Aligné</h5>
					<p>MACD 1m et 5m même signe</p>
				</div>
			</div>
		</div>
	</section>
</div>

<style>
	.ml-gb-wrapper {
		display: flex;
		flex-direction: column;
		gap: 24px;
	}

	.info-banner {
		display: flex;
		gap: 16px;
		padding: 20px;
		background: linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(59, 130, 246, 0.1));
		border: 1px solid rgba(16, 185, 129, 0.3);
		border-radius: 12px;
	}

	.banner-icon {
		font-size: 32px;
	}

	.banner-content h4 {
		margin: 0 0 8px 0;
		color: #10b981;
		font-size: 18px;
	}

	.banner-content p {
		margin: 0;
		color: #94a3b8;
		font-size: 14px;
		line-height: 1.5;
	}

	.variable-section {
		background: rgba(7, 11, 30, 0.85);
		border: 1px solid rgba(255, 255, 255, 0.05);
		border-radius: 12px;
		padding: 24px;
		box-shadow: 0 10px 25px rgba(0, 0, 0, 0.25);
	}

	.variable-section h3 {
		margin: 0 0 8px 0;
		font-size: 18px;
		color: #f8fafc;
	}

	.section-desc {
		color: #94a3b8;
		font-size: 14px;
		margin-bottom: 20px;
	}

	.subsection-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
		gap: 16px;
		margin-top: 16px;
	}

	.subsection-card {
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid rgba(255, 255, 255, 0.05);
		border-radius: 10px;
		padding: 16px;
	}

	.subsection-card h4 {
		margin: 0 0 16px 0;
		color: #e2e8f0;
		font-size: 15px;
	}

	.variable-item {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin-bottom: 16px;
	}

	.variable-item.toggle-item {
		flex-direction: row;
		align-items: center;
		justify-content: space-between;
	}

	.var-header {
		display: flex;
		gap: 4px;
		flex-direction: column;
	}

	.var-name {
		font-weight: 600;
		color: #f8fafc;
		font-size: 14px;
	}

	.var-desc {
		font-size: 12px;
		color: #7f8ba7;
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

	.slider-container input[type="range"] {
		flex: 1;
	}

	.slider-value {
		min-width: 50px;
		font-family: 'Space Mono', monospace;
		text-align: right;
		padding: 3px 10px;
		border-radius: 999px;
		background: rgba(16, 185, 129, 0.1);
		border: 1px solid rgba(16, 185, 129, 0.4);
		color: #6ee7b7;
		font-size: 0.85rem;
		font-weight: 500;
	}

	.select-input {
		padding: 10px 14px;
		border-radius: 10px;
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid rgba(255, 255, 255, 0.1);
		color: #f8fafc;
		font-size: 14px;
	}

	.toggle {
		position: relative;
		width: 50px;
		height: 26px;
	}

	.toggle input {
		opacity: 0;
		width: 0;
		height: 0;
	}

	.toggle-slider {
		position: absolute;
		cursor: pointer;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background-color: rgba(255, 255, 255, 0.1);
		transition: 0.3s;
		border-radius: 26px;
	}

	.toggle-slider:before {
		position: absolute;
		content: "";
		height: 20px;
		width: 20px;
		left: 3px;
		bottom: 3px;
		background-color: white;
		transition: 0.3s;
		border-radius: 50%;
	}

	.toggle input:checked + .toggle-slider {
		background-color: #10b981;
	}

	.toggle input:checked + .toggle-slider:before {
		transform: translateX(24px);
	}

	.ml-metrics-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
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

	.metric-card.good {
		border-color: rgba(16, 185, 129, 0.4);
	}

	.metric-card.ok {
		border-color: rgba(59, 130, 246, 0.4);
	}

	.metric-card.warning {
		border-color: rgba(250, 204, 21, 0.4);
	}

	.metric-card.danger {
		border-color: rgba(248, 113, 113, 0.4);
	}

	.action-buttons {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
		gap: 16px;
		margin-top: 20px;
	}

	.retrain-card, .verify-card {
		padding: 16px;
		border-radius: 10px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
	}

	.retrain-card {
		background: linear-gradient(135deg, rgba(59, 130, 246, 0.15), rgba(16, 185, 129, 0.12));
		border: 1px solid rgba(59, 130, 246, 0.3);
	}

	.verify-card {
		background: linear-gradient(135deg, rgba(139, 92, 246, 0.15), rgba(59, 130, 246, 0.12));
		border: 1px solid rgba(139, 92, 246, 0.3);
	}

	.retrain-card h4, .verify-card h4 {
		margin: 0 0 4px 0;
		font-size: 15px;
		color: #f8fafc;
	}

	.retrain-card p, .verify-card p {
		margin: 0;
		font-size: 13px;
		color: #94a3b8;
	}

	.btn-retrain, .btn-verify {
		padding: 0.75rem 1.5rem;
		border: none;
		border-radius: 8px;
		font-weight: 600;
		cursor: pointer;
		transition: transform 0.2s ease;
		white-space: nowrap;
	}

	.btn-retrain {
		background: linear-gradient(135deg, #22d3ee, #0ea5e9);
		color: #0f172a;
	}

	.btn-verify {
		background: linear-gradient(135deg, #a78bfa, #8b5cf6);
		color: #0f172a;
	}

	.btn-retrain:disabled, .btn-verify:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.btn-retrain:not(:disabled):hover, .btn-verify:not(:disabled):hover {
		transform: translateY(-2px);
	}

	.verify-result {
		margin-top: 16px;
		padding: 12px 16px;
		border-radius: 8px;
		font-size: 14px;
	}

	.verify-result.success {
		background: rgba(16, 185, 129, 0.1);
		border: 1px solid rgba(16, 185, 129, 0.3);
		color: #6ee7b7;
	}

	.verify-result.error {
		background: rgba(248, 113, 113, 0.1);
		border: 1px solid rgba(248, 113, 113, 0.3);
		color: #fca5a5;
	}

	.features-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 12px;
	}

	.feature-card {
		display: flex;
		gap: 12px;
		padding: 12px;
		background: rgba(255, 255, 255, 0.02);
		border-radius: 8px;
		border: 1px solid rgba(255, 255, 255, 0.05);
	}

	.feature-icon {
		font-size: 24px;
	}

	.feature-card h5 {
		margin: 0 0 4px 0;
		font-size: 14px;
		color: #e2e8f0;
	}

	.feature-card p {
		margin: 0;
		font-size: 13px;
		color: #94a3b8;
	}

	.feature-card p.good {
		color: #6ee7b7;
	}

	.feature-card p.bad {
		color: #fca5a5;
	}

	.disabled {
		opacity: 0.5;
		pointer-events: none;
	}

	/* Model Type Selector */
	.model-type-section {
		background: linear-gradient(135deg, rgba(34, 211, 238, 0.08), rgba(59, 130, 246, 0.05));
		border: 1px solid rgba(34, 211, 238, 0.2);
	}

	.model-type-selector {
		display: flex;
		gap: 12px;
		margin-bottom: 16px;
	}

	.model-type-btn {
		flex: 1;
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 16px;
		background: rgba(0, 0, 0, 0.3);
		border: 2px solid rgba(255, 255, 255, 0.1);
		border-radius: 12px;
		cursor: pointer;
		transition: all 0.2s ease;
		text-align: left;
	}

	.model-type-btn:hover {
		border-color: rgba(34, 211, 238, 0.4);
		background: rgba(34, 211, 238, 0.1);
	}

	.model-type-btn.active {
		border-color: #22d3ee;
		background: rgba(34, 211, 238, 0.15);
		box-shadow: 0 0 20px rgba(34, 211, 238, 0.2);
	}

	.model-icon {
		font-size: 28px;
	}

	.model-info {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.model-name {
		font-weight: 600;
		color: #f8fafc;
		font-size: 15px;
	}

	.model-desc {
		font-size: 12px;
		color: #94a3b8;
	}

	.model-speed {
		padding: 4px 10px;
		background: rgba(16, 185, 129, 0.2);
		border-radius: 20px;
		font-size: 12px;
		font-weight: 700;
		color: #10b981;
	}

	.model-type-btn.active .model-speed {
		background: rgba(34, 211, 238, 0.3);
		color: #22d3ee;
	}

	.model-comparison {
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 12px;
		background: rgba(0, 0, 0, 0.2);
		border-radius: 8px;
	}

	.comparison-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		font-size: 13px;
	}

	.comp-label {
		color: #94a3b8;
	}

	.comp-value {
		color: #22d3ee;
		font-weight: 600;
	}

	.comp-bars {
		display: flex;
		gap: 8px;
		flex: 1;
		margin-left: 16px;
	}

	.comp-bar {
		height: 20px;
		border-radius: 4px;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 10px;
		font-weight: 600;
		transition: width 0.3s ease;
	}

	.comp-bar.gb {
		background: linear-gradient(90deg, #6366f1, #8b5cf6);
		color: white;
	}

	.comp-bar.histgb {
		background: linear-gradient(90deg, #10b981, #22d3ee);
		color: #0f172a;
	}

	/* Optuna Section */
	.optuna-section {
		margin-top: 24px;
		padding: 20px;
		background: linear-gradient(135deg, rgba(234, 179, 8, 0.1), rgba(245, 158, 11, 0.05));
		border: 1px solid rgba(234, 179, 8, 0.3);
		border-radius: 12px;
	}

	.optuna-header h4 {
		margin: 0 0 8px 0;
		color: #fbbf24;
		font-size: 16px;
	}

	.optuna-header p {
		margin: 0 0 16px 0;
		color: #94a3b8;
		font-size: 13px;
	}

	.optuna-actions {
		display: flex;
		gap: 12px;
		flex-wrap: wrap;
	}

	.btn-optuna {
		padding: 0.75rem 1.5rem;
		background: linear-gradient(135deg, #f59e0b, #d97706);
		border: none;
		border-radius: 8px;
		color: #0f172a;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.btn-optuna:disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}

	.btn-optuna:not(:disabled):hover {
		transform: translateY(-2px);
		box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3);
	}

	.btn-apply-optuna {
		padding: 0.75rem 1.5rem;
		background: linear-gradient(135deg, #10b981, #059669);
		border: none;
		border-radius: 8px;
		color: white;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.btn-apply-optuna:hover {
		transform: translateY(-2px);
	}

	.optuna-progress {
		margin-top: 16px;
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.progress-bar {
		flex: 1;
		height: 8px;
		background: rgba(255, 255, 255, 0.1);
		border-radius: 4px;
		overflow: hidden;
	}

	.progress-fill {
		height: 100%;
		background: linear-gradient(90deg, #f59e0b, #10b981);
		border-radius: 4px;
		transition: width 0.3s ease;
	}

	.progress-text {
		font-size: 13px;
		color: #94a3b8;
		white-space: nowrap;
	}

	.optuna-result {
		margin-top: 16px;
		padding: 16px;
		background: rgba(0, 0, 0, 0.2);
		border-radius: 8px;
		border: 1px solid rgba(255, 255, 255, 0.1);
	}

	.optuna-result.success {
		border-color: rgba(16, 185, 129, 0.3);
		background: rgba(16, 185, 129, 0.1);
	}

	.optuna-result h5 {
		margin: 0 0 12px 0;
		color: #10b981;
		font-size: 14px;
	}

	.params-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 8px;
	}

	.param-item {
		display: flex;
		justify-content: space-between;
		padding: 6px 10px;
		background: rgba(255, 255, 255, 0.05);
		border-radius: 4px;
		font-size: 12px;
	}

	.param-key {
		color: #94a3b8;
	}

	.param-value {
		color: #10b981;
		font-weight: 600;
	}

	.applied-badge {
		margin-top: 12px;
		padding: 8px 12px;
		background: rgba(16, 185, 129, 0.2);
		border-radius: 6px;
		color: #6ee7b7;
		font-weight: 600;
		text-align: center;
	}

	/* Vérification Complète */
	.verify-complete-section {
		margin-top: 24px;
		padding: 20px;
		background: linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(139, 92, 246, 0.05));
		border: 1px solid rgba(99, 102, 241, 0.3);
		border-radius: 12px;
	}

	.verify-header h4 {
		margin: 0 0 8px 0;
		color: #818cf8;
		font-size: 16px;
	}

	.verify-header p {
		margin: 0 0 16px 0;
		color: #94a3b8;
		font-size: 13px;
	}

	.btn-verify-complete {
		padding: 0.75rem 1.5rem;
		background: linear-gradient(135deg, #6366f1, #8b5cf6);
		border: none;
		border-radius: 8px;
		color: white;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.btn-verify-complete:disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}

	.btn-verify-complete:not(:disabled):hover {
		transform: translateY(-2px);
		box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
	}

	.verify-complete-result {
		margin-top: 16px;
		padding: 16px;
		border-radius: 8px;
	}

	.verify-complete-result.ok {
		background: rgba(16, 185, 129, 0.1);
		border: 1px solid rgba(16, 185, 129, 0.3);
	}

	.verify-complete-result.warning {
		background: rgba(234, 179, 8, 0.1);
		border: 1px solid rgba(234, 179, 8, 0.3);
	}

	.verify-complete-result.error {
		background: rgba(239, 68, 68, 0.1);
		border: 1px solid rgba(239, 68, 68, 0.3);
	}

	.result-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 12px;
		font-weight: 600;
	}

	.result-summary {
		font-size: 12px;
		color: #94a3b8;
		font-weight: normal;
	}

	.checks-list {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.check-item {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 8px 12px;
		background: rgba(0, 0, 0, 0.2);
		border-radius: 6px;
		font-size: 13px;
	}

	.check-item.ok {
		border-left: 3px solid #10b981;
	}

	.check-item.warning {
		border-left: 3px solid #f59e0b;
	}

	.check-item.error {
		border-left: 3px solid #ef4444;
	}

	.check-icon {
		font-size: 14px;
	}

	.check-name {
		font-weight: 600;
		color: #e2e8f0;
	}

	.check-details {
		color: #94a3b8;
		margin-left: auto;
		font-size: 12px;
	}

	/* 🔢 Stats Trades ML */
	.trades-stats-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 12px;
		margin-bottom: 16px;
	}

	.stat-card {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 16px;
		background: rgba(30, 41, 59, 0.6);
		border-radius: 10px;
		border: 1px solid rgba(148, 163, 184, 0.1);
	}

	.stat-card.total {
		background: rgba(59, 130, 246, 0.1);
		border-color: rgba(59, 130, 246, 0.3);
	}

	.stat-card.excluded {
		background: rgba(239, 68, 68, 0.1);
		border-color: rgba(239, 68, 68, 0.2);
	}

	.stat-card.final {
		background: rgba(16, 185, 129, 0.1);
		border-color: rgba(16, 185, 129, 0.3);
	}

	.stat-card.final.warning {
		background: rgba(234, 179, 8, 0.1);
		border-color: rgba(234, 179, 8, 0.3);
	}

	.stat-icon {
		font-size: 24px;
	}

	.stat-content {
		display: flex;
		flex-direction: column;
	}

	.stat-value {
		font-size: 20px;
		font-weight: 700;
		color: #f1f5f9;
	}

	.stat-label {
		font-size: 12px;
		color: #94a3b8;
	}

	.config-info {
		padding: 12px 16px;
		background: rgba(30, 41, 59, 0.4);
		border-radius: 8px;
		font-size: 13px;
		color: #94a3b8;
		margin-bottom: 12px;
	}

	.config-info strong {
		color: #e2e8f0;
	}

	.refresh-btn {
		padding: 8px 16px;
		background: rgba(59, 130, 246, 0.2);
		border: 1px solid rgba(59, 130, 246, 0.4);
		border-radius: 6px;
		color: #60a5fa;
		font-size: 13px;
		cursor: pointer;
		transition: all 0.2s;
	}

	.refresh-btn:hover:not(:disabled) {
		background: rgba(59, 130, 246, 0.3);
	}

	.refresh-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.error-message {
		padding: 12px;
		background: rgba(239, 68, 68, 0.1);
		border: 1px solid rgba(239, 68, 68, 0.3);
		border-radius: 8px;
		color: #fca5a5;
	}

	@media (max-width: 768px) {
		.trades-stats-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}
</style>
