<script>
	import { onMount } from 'svelte';
	import { createEventDispatcher } from 'svelte';

	const dispatch = createEventDispatcher();

	let optimizationState = {
		isRunning: false,
		progress: 0,
		currentTrial: 0,
		totalTrials: 0,
		bestScore: null,
		elapsedTime: 0,
		estimatedRemaining: 0
	};

	let bestParams = {
		params: null,
		score: null,
		trial: null,
		source: 'none' // 'latest' ou 'global'
	};

	let runBestParams = {
		params: null,
		score: null,
		trial: null
	};

	let globalBestParams = {
		params: null,
		score: null,
		trial: null
	};

	let nTrials = 50;
	let loading = false;
	let message = '';

	onMount(() => {
		checkOptimizationStatus();
	});

	async function checkOptimizationStatus() {
		try {
			const response = await fetch('/api/ml/optimize_v2/status');
			if (response.ok) {
				const data = await response.json();
				if (data.study_name) {
					globalBestParams = {
						params: data.best_params,
						score: data.best_value,
						trial: data.n_trials
					};
					showGlobalBest();
				}
			}
		} catch (e) {
			console.error('Erreur checkOptimizationStatus V2:', e);
		}
	}

	async function startOptimization() {
		if (loading || optimizationState.isRunning) return;

		loading = true;
		message = '🚀 Démarrage optimisation V2...';

		try {
			const response = await fetch('/api/ml/optimize_v2/start', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ n_trials: nTrials })
			});

			if (!response.ok) throw new Error('Erreur démarrage');

			const data = await response.json();
			message = '⏳ Optimisation en cours...';
			optimizationState.isRunning = true;

			// Polling status
			pollOptimizationStatus();
		} catch (e) {
			message = `❌ Erreur: ${e.message}`;
			setTimeout(() => (message = ''), 5000);
		} finally {
			loading = false;
		}
	}

	async function pollOptimizationStatus() {
		const interval = setInterval(async () => {
			try {
				const response = await fetch('/api/ml/optimize_v2/status');
				if (!response.ok) {
					clearInterval(interval);
					return;
				}

				const data = await response.json();

				if (!data.is_running) {
					clearInterval(interval);
					optimizationState.isRunning = false;

					runBestParams = {
						params: data.run_best_params,
						score: data.run_best_score,
						trial: data.run_best_trial
					};

					globalBestParams = {
						params: data.best_params,
						score: data.best_value,
						trial: data.n_trials
					};

					showLatestResult();
					message = '✅ Optimisation terminée!';
					setTimeout(() => (message = ''), 3000);
				} else {
					optimizationState.progress = data.progress || 0;
					optimizationState.currentTrial = data.current_trial || 0;
					optimizationState.totalTrials = data.total_trials || nTrials;
				}
			} catch (e) {
				console.error('Erreur polling V2:', e);
				clearInterval(interval);
			}
		}, 2000);
	}

	function showLatestResult() {
		bestParams = {
			...bestParams,
			params: { ...runBestParams.params },
			score: runBestParams.score,
			trial: runBestParams.trial,
			source: 'latest'
		};
	}

	function showGlobalBest() {
		bestParams = {
			...bestParams,
			params: { ...globalBestParams.params },
			score: globalBestParams.score,
			trial: globalBestParams.trial,
			source: 'global'
		};
	}

	async function applyBestParams() {
		if (!bestParams.params) {
			alert('Aucun paramètre à appliquer');
			return;
		}

		const sourceLabel = bestParams.source === 'latest' ? 'Latest run' : 'Global best';
		const scoreLabel = bestParams.score ? bestParams.score.toFixed(4) : 'N/A';

		if (!confirm(`Appliquer les paramètres:\nSource: ${sourceLabel}\nScore: ${scoreLabel}\n\nContinuer?`)) {
			return;
		}

		loading = true;
		message = '💾 Application des paramètres V2...';

		try {
			// Whitelist des paramètres XGBoost V2 valides
			const validParamKeys = [
				'n_estimators',
				'max_depth',
				'learning_rate',
				'min_child_weight',
				'reg_alpha',
				'reg_lambda',
				'gamma',
				'subsample',
				'colsample_bytree'
			];

			// Filtrer pour ne garder que les paramètres valides
			const cleanParams = {};
			Object.keys(bestParams.params).forEach(key => {
				if (validParamKeys.includes(key)) {
					cleanParams[key] = bestParams.params[key];
				} else {
					console.warn(`⚠️ Paramètre non-standard ignoré: ${key}`);
				}
			});

			console.log('📤 Envoi params V2 nettoyés:', cleanParams);

			const response = await fetch('/api/ml/optimize_v2/apply', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(cleanParams)
			});

			if (!response.ok) throw new Error('Erreur application');

			const data = await response.json();
			message = '✅ Paramètres V2 appliqués!';

			dispatch('paramsApplied', { params: cleanParams });

			setTimeout(() => (message = ''), 3000);
		} catch (e) {
			message = `❌ Erreur: ${e.message}`;
			setTimeout(() => (message = ''), 5000);
		} finally {
			loading = false;
		}
	}
</script>

<div class="optimization-panel-v2">
	<div class="panel-header">
		<h4>⚡ Optimisation Bayésienne V2 (Optuna)</h4>
		<p class="panel-desc">
			Recherche automatique des hyperparamètres optimaux pour XGBoost V2 (Régression PNL%)
		</p>
	</div>

	<div class="optimization-controls">
		<div class="control-row">
			<label for="n-trials-v2">Nombre d'essais:</label>
			<input
				type="number"
				id="n-trials-v2"
				min="10"
				max="200"
				step="10"
				bind:value={nTrials}
				disabled={optimizationState.isRunning}
			/>
		</div>

		<button class="btn-start" on:click={startOptimization} disabled={loading || optimizationState.isRunning}>
			{optimizationState.isRunning ? '⏳ En cours...' : '🚀 Lancer Optimisation V2'}
		</button>
	</div>

	{#if optimizationState.isRunning}
		<div class="progress-section">
			<div class="progress-bar">
				<div class="progress-fill" style="width: {optimizationState.progress}%"></div>
			</div>
			<p class="progress-text">
				Trial {optimizationState.currentTrial}/{optimizationState.totalTrials} ({optimizationState.progress.toFixed(0)}%)
			</p>
		</div>
	{/if}

	{#if bestParams.params}
		<div class="results-section">
			<div class="best-source-row">
				<button class="source-pill" class:active={bestParams.source === 'latest'} on:click={showLatestResult}>
					📊 Latest Run
				</button>
				<button class="source-pill" class:active={bestParams.source === 'global'} on:click={showGlobalBest}>
					🏆 Global Best
				</button>
			</div>

			<div class="params-display">
				<h5>
					{bestParams.source === 'latest' ? '📊 Meilleurs Params (Latest Run)' : '🏆 Meilleurs Params (Global)'}
				</h5>
				<p class="score">Score R²: <strong>{bestParams.score?.toFixed(4) || 'N/A'}</strong></p>

				<div class="params-grid">
					{#each Object.entries(bestParams.params) as [key, value]}
						<div class="param-item">
							<span class="param-key">{key}:</span>
							<span class="param-value">{typeof value === 'number' ? value.toFixed(3) : value}</span>
						</div>
					{/each}
				</div>

				<button class="btn-apply" on:click={applyBestParams} disabled={loading}>
					💾 Appliquer ces Paramètres
				</button>
			</div>
		</div>
	{/if}

	{#if message}
		<div class="message">{message}</div>
	{/if}
</div>

<style>
	.optimization-panel-v2 {
		background: rgba(42, 58, 107, 0.3);
		border-radius: 12px;
		padding: 1.5rem;
	}

	.panel-header h4 {
		margin: 0 0 0.5rem 0;
		color: #00ff88;
		font-size: 1.1rem;
	}

	.panel-desc {
		margin: 0 0 1rem 0;
		color: #a0aec0;
		font-size: 0.9rem;
	}

	.optimization-controls {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		margin-bottom: 1.5rem;
	}

	.control-row {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.control-row label {
		color: #cbd5e0;
		font-weight: 600;
	}

	.control-row input {
		padding: 0.5rem;
		border: 1px solid rgba(255, 255, 255, 0.2);
		border-radius: 6px;
		background: rgba(255, 255, 255, 0.05);
		color: white;
		width: 100px;
	}

	.btn-start {
		padding: 0.75rem 1.5rem;
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		color: white;
		border: none;
		border-radius: 8px;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.3s;
	}

	.btn-start:hover:not(:disabled) {
		transform: translateY(-2px);
		box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
	}

	.btn-start:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.progress-section {
		margin: 1.5rem 0;
	}

	.progress-bar {
		width: 100%;
		height: 8px;
		background: rgba(0, 0, 0, 0.3);
		border-radius: 4px;
		overflow: hidden;
	}

	.progress-fill {
		height: 100%;
		background: linear-gradient(90deg, #10b981, #34d399);
		transition: width 0.3s;
	}

	.progress-text {
		margin-top: 0.5rem;
		color: #cbd5e0;
		font-size: 0.9rem;
	}

	.results-section {
		background: rgba(0, 0, 0, 0.2);
		border-radius: 8px;
		padding: 1rem;
	}

	.best-source-row {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 1rem;
	}

	.source-pill {
		flex: 1;
		padding: 0.5rem 1rem;
		background: rgba(255, 255, 255, 0.05);
		border: 2px solid rgba(255, 255, 255, 0.1);
		border-radius: 6px;
		color: #a0aec0;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s;
	}

	.source-pill:hover {
		border-color: #667eea;
		background: rgba(102, 126, 234, 0.1);
	}

	.source-pill.active {
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		color: white;
		border-color: #667eea;
	}

	.params-display h5 {
		margin: 0 0 0.5rem 0;
		color: #00ff88;
		font-size: 1rem;
	}

	.score {
		margin: 0 0 1rem 0;
		color: #cbd5e0;
	}

	.score strong {
		color: #00ff88;
		font-size: 1.2rem;
	}

	.params-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 0.75rem;
		margin-bottom: 1rem;
	}

	.param-item {
		padding: 0.5rem;
		background: rgba(0, 0, 0, 0.2);
		border-radius: 6px;
		display: flex;
		justify-content: space-between;
	}

	.param-key {
		color: #a0aec0;
		font-size: 0.875rem;
	}

	.param-value {
		color: white;
		font-weight: 600;
	}

	.btn-apply {
		width: 100%;
		padding: 0.75rem;
		background: linear-gradient(135deg, #10b981 0%, #059669 100%);
		color: white;
		border: none;
		border-radius: 8px;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.3s;
	}

	.btn-apply:hover:not(:disabled) {
		transform: translateY(-2px);
		box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
	}

	.btn-apply:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.message {
		margin-top: 1rem;
		padding: 0.75rem;
		background: rgba(0, 0, 0, 0.3);
		border-radius: 6px;
		color: #cbd5e0;
		text-align: center;
	}
</style>
