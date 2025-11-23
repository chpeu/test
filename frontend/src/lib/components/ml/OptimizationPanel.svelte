<script>
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { createEventDispatcher } from 'svelte';
	import { TrendingUp, PlayCircle, AlertCircle, CheckCircle, Activity, Package, Clock, Target } from 'lucide-svelte';

	const dispatch = createEventDispatcher();

	// Constantes
	const METRIC_OPTIONS = [
		{ key: 'trading_composite', label: 'Trading Composite', description: 'Score custom équilibré' },
		{ key: 'f1_score', label: 'F1-Score', description: 'Équilibre précision/recall' },
		{ key: 'accuracy', label: 'Accuracy', description: 'Taux de bonnes prédictions' },
		{ key: 'roc_auc', label: 'ROC AUC', description: 'Capacité de discrimination' }
	];

	const METRIC_KEYS = METRIC_OPTIONS.map((m) => m.key);
	const DEFAULT_METRIC = 'trading_composite';

	// États
	let metricSummary = { metrics: {} };
	let selectedMetric = DEFAULT_METRIC;
	let selectedMetricInfo = METRIC_OPTIONS[0];
	let bestParams = null;
	let isLoading = false;
	let errorMessage = null;
	let statusCheckInterval = null;
	let isInitializing = true;

	// Configuration optimisation
	let config = {
		n_trials: 50,
		timeout: 3600,
		metric: DEFAULT_METRIC,
		use_gpu: false,
		max_samples: null
	};

	function updateConfig(updates) {
		config = { ...config, ...updates };
	}

	// Persistance dans localStorage
	function saveConfig() {
		if (browser && !isInitializing) {
			try {
				localStorage.setItem('optimizationConfig', JSON.stringify(config));
				console.log('💾 Config saved to localStorage:', config);
			} catch (e) {
				console.warn('Failed to save config:', e);
			}
		}
	}

	function loadConfig() {
		if (browser) {
			try {
				const stored = localStorage.getItem('optimizationConfig');
				if (stored) {
					const parsed = JSON.parse(stored);
					config = { ...config, ...parsed };
					if (!config.metric || !METRIC_KEYS.includes(config.metric)) {
						config.metric = DEFAULT_METRIC;
					}
					console.log('📂 Config loaded from localStorage:', config);
				}
			} catch (e) {
				console.warn('Failed to load config:', e);
			}
		}
	}

	function saveSummary() {
		if (browser) {
			try {
				localStorage.setItem('metricSummary', JSON.stringify(metricSummary));
			} catch (e) {
				console.warn('Failed to save summary:', e);
			}
		}
	}

	function loadSummary() {
		if (browser) {
			try {
				const stored = localStorage.getItem('metricSummary');
				if (stored) {
					metricSummary = JSON.parse(stored);
				}
			} catch (e) {
				console.warn('Failed to load summary:', e);
			}
		}
	}

	// Formatage score
	function formatScore(score) {
		if (score == null) return 'N/A';
		return typeof score === 'number' ? score.toFixed(4) : score;
	}

	function getMetricDisplayScore(metricKey) {
		const entry = metricSummary.metrics?.[metricKey];
		if (!entry) return null;
		return entry.last_run?.score ?? null;
	}

	function applyMetricSelection(metricKey = DEFAULT_METRIC) {
		if (!METRIC_KEYS.includes(metricKey)) {
			metricKey = DEFAULT_METRIC;
		}
		selectedMetric = metricKey;
		selectedMetricInfo = METRIC_OPTIONS.find((option) => option.key === selectedMetric) || METRIC_OPTIONS[0];
		const entry = metricSummary.metrics?.[selectedMetric];
		if (!entry) {
			bestParams = null;
			return;
		}
		const candidate = entry.last_run;
		bestParams = candidate ? { ...candidate, metric: selectedMetric, found: true } : null;
	}

	function handleMetricSelect(metricKey) {
		updateConfig({ metric: metricKey });
		applyMetricSelection(metricKey);
	}

	function handleMetricDropdownChange(event) {
		const metricKey = event.target.value;
		updateConfig({ metric: metricKey });
		applyMetricSelection(metricKey);
	}

	function handleGpuToggle(event) {
		updateConfig({ use_gpu: event.target.checked });
	}

	// Récupérer le summary
	async function fetchSummary() {
		try {
			const response = await fetch('/api/ml/optimize/summary');
			if (!response.ok) throw new Error('Failed to fetch summary');
			const data = await response.json();
			metricSummary = data;
			saveSummary();
		} catch (err) {
			console.warn('Failed to fetch metric summary:', err);
		}
	}

	// Démarrer optimisation
	async function startOptimization() {
		try {
			isLoading = true;
			errorMessage = null;

			const params = new URLSearchParams({
				n_trials: config.n_trials?.toString() ?? '50',
				timeout: config.timeout?.toString() ?? '3600',
				metric: config.metric,
				use_gpu: config.use_gpu ? 'true' : 'false'
			});
			if (config.max_samples) {
				params.set('max_samples', config.max_samples.toString());
			}

			const response = await fetch(`/api/ml/optimize/start?${params.toString()}`, {
				method: 'POST'
			});

			if (!response.ok) {
				const error = await response.json();
				throw new Error(error.detail || 'Erreur démarrage');
			}

			const data = await response.json();
			const taskId = data.task_id;
			alert(data.message || 'Optimisation démarrée');
			
			// Démarrer le polling pour mettre à jour le summary quand l'optimisation se termine
			if (taskId) {
				startTaskPolling(taskId);
			}
		} catch (error) {
			errorMessage = error.message;
			console.error('Error starting optimization:', error);
		} finally {
			isLoading = false;
		}
	}

	// Polling pour suivre l'optimisation
	async function startTaskPolling(taskId) {
		let attempts = 0;
		const maxAttempts = 360; // 30 minutes max (5s interval)
		
		const pollInterval = setInterval(async () => {
			attempts++;
			
			if (attempts > maxAttempts) {
				clearInterval(pollInterval);
				console.warn('Polling timeout reached');
				return;
			}
			
			try {
				const response = await fetch(`/api/ml/tasks/${taskId}`);
				if (!response.ok) {
					clearInterval(pollInterval);
					return;
				}
				
				const task = await response.json();
				
				if (task.status === 'completed') {
					clearInterval(pollInterval);
					console.log('✅ Optimisation terminée, rafraîchissement du summary');
					
					// Attendre un peu pour que le backend écrive optuna_last_runs.json
					await new Promise(resolve => setTimeout(resolve, 1000));
					
					// Rafraîchir le summary
					await fetchSummary();
					
					// Réappliquer la sélection métrique pour afficher les nouveaux résultats
					applyMetricSelection(config.metric);
					
					alert(`✅ Optimisation ${config.metric} terminée!\nScore: ${task.run_best_score?.toFixed(4) || 'N/A'}`);
				} else if (task.status === 'failed') {
					clearInterval(pollInterval);
					errorMessage = `Optimisation échouée: ${task.error || 'Erreur inconnue'}`;
				}
			} catch (err) {
				console.warn('Error polling task:', err);
			}
		}, 5000); // Poll toutes les 5 secondes
		
		// Stocker l'interval pour le cleanup
		if (statusCheckInterval) clearInterval(statusCheckInterval);
		statusCheckInterval = pollInterval;
	}

	// Appliquer les meilleurs paramètres
	async function applyBestParams() {
		if (!bestParams || !bestParams.params) {
			alert('Aucun paramètre sélectionné');
			return;
		}

		try {
			isLoading = true;
			errorMessage = null;

			const paramsToSend = {
				...bestParams.params,
				_metric: selectedMetric
			};

			const response = await fetch('/api/ml/optimize/apply', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(paramsToSend)
			});

			if (!response.ok) {
				const error = await response.json();
				throw new Error(error.detail || 'Erreur application params');
			}

			const data = await response.json();
			alert(`${data.message}\n\nSource: Dernière optimisation (${selectedMetricInfo.label})\n\n⚠️ ${data.warning || ''}`);

			dispatch('paramsApplied');
		} catch (error) {
			errorMessage = error.message;
			console.error('Error applying params:', error);
		} finally {
			isLoading = false;
		}
	}

	// Lifecycle
	onMount(async () => {
		// 1. Charger config depuis localStorage en PREMIER
		loadConfig();
		loadSummary();
		
		// 2. Fetch backend summary
		await fetchSummary();
		
		// 3. Appliquer sélection métrique APRÈS avoir chargé config
		// Utiliser la métrique stockée dans config, pas DEFAULT_METRIC
		applyMetricSelection(config.metric);
		
		// 4. Activer la sauvegarde automatique APRÈS l'initialisation
		isInitializing = false;
	});

	onDestroy(() => {
		if (statusCheckInterval) {
			clearInterval(statusCheckInterval);
		}
	});

	// Sauvegarde automatique quand config change (après initialisation)
	$: if (browser && config && !isInitializing) {
		saveConfig();
	}
</script>

<div class="optimization-panel">
	<div class="panel-header">
		<div class="header-content">
			<div class="header-icon">
				<Activity size={28} />
			</div>
			<div>
				<h2>Optimisation Hyperparamètres</h2>
				<p class="subtitle">Recherche automatique des meilleurs paramètres XGBoost</p>
			</div>
		</div>
	</div>

	<!-- Configuration -->
	<div class="config-section">
		<h3><Package size={18} /> Configuration</h3>
		<div class="config-grid">
			<div class="config-item">
				<label for="n_trials">Nombre d'essais</label>
				<input
					id="n_trials"
					type="number"
					bind:value={config.n_trials}
					min="1"
					max="1000"
					disabled={isLoading}
				/>
				<span class="hint">Plus = meilleur mais plus long</span>
			</div>

			<div class="config-item">
				<label for="timeout">Timeout (secondes)</label>
				<input
					id="timeout"
					type="number"
					bind:value={config.timeout}
					min="60"
					max="86400"
					disabled={isLoading}
				/>
				<span class="hint">Limite de temps max</span>
			</div>

			<div class="config-item">
				<label for="metric">Métrique cible</label>
				<select
					id="metric"
					value={config.metric}
					on:change={handleMetricDropdownChange}
					disabled={isLoading}
				>
					{#each METRIC_OPTIONS as opt}
						<option value={opt.key}>{opt.label}</option>
					{/each}
				</select>
			</div>

			<div class="config-item">
				<label for="max_samples">Max samples</label>
				<input
					id="max_samples"
					type="number"
					bind:value={config.max_samples}
					placeholder="Tous"
					disabled={isLoading}
				/>
				<span class="hint">Limite pour debug rapide</span>
			</div>
		</div>

		<div class="config-switches">
			<label class="switch-item">
				<input
					type="checkbox"
					checked={config.use_gpu}
					on:change={handleGpuToggle}
					disabled={isLoading}
				/>
				Utiliser le GPU (si disponible)
			</label>
		</div>

		<div class="action-buttons">
			<button class="btn-primary" on:click={startOptimization} disabled={isLoading}>
				{#if isLoading}
					<div class="spin"><Clock size={16} /></div>
				{:else}
					<PlayCircle size={16} />
				{/if}
				{isLoading ? 'En cours...' : 'Lancer l\'optimisation'}
			</button>
		</div>

		{#if errorMessage}
			<div class="error-message">
				<AlertCircle size={16} />
				{errorMessage}
			</div>
		{/if}
	</div>

	<!-- Métriques -->
	<div class="metrics-section">
		<h3><TrendingUp size={18} /> Métriques Optimisées</h3>
		<div class="metric-grid">
			{#each METRIC_OPTIONS as metric}
				<div
					class="metric-card"
					class:active={selectedMetric === metric.key}
					on:click={() => handleMetricSelect(metric.key)}
					role="button"
					tabindex="0"
					on:keypress={(e) => e.key === 'Enter' && handleMetricSelect(metric.key)}
				>
					<div class="metric-header">
						<h4>{metric.label}</h4>
						<p class="metric-description">{metric.description}</p>
					</div>
					<div class="metric-content">
						{#if metricSummary.metrics?.[metric.key]?.last_run}
							<div class="metric-value">
								{formatScore(metricSummary.metrics[metric.key].last_run.score)}
								<span class="metric-subtitle">Dernière optimisation</span>
							</div>
						{:else}
							<div class="metric-value">N/A</div>
							<p class="metric-hint">Aucune optimisation trouvée</p>
						{/if}
					</div>
				</div>
			{/each}
		</div>
	</div>

	<!-- Meilleurs paramètres -->
	{#if bestParams && bestParams.found}
		<div class="current-best-section">
			<div class="best-source-row">
				<div class="source-info">
					<h3><Target size={18} /> Paramètres à appliquer</h3>
					<p class="source-label">
						<strong>{selectedMetricInfo.label}</strong> — Dernière optimisation
						{#if bestParams.score}
							<span class="score-badge">{formatScore(bestParams.score)}</span>
						{/if}
					</p>
				</div>
				<button class="btn-success" on:click={applyBestParams} disabled={isLoading}>
					<CheckCircle size={16} />
					Appliquer ces paramètres
				</button>
			</div>

			<div class="params-grid">
				{#each Object.entries(bestParams.params) as [key, value]}
					<div class="param-item">
						<span class="param-key">{key}</span>
						<span class="param-value">{value}</span>
					</div>
				{/each}
			</div>
		</div>
	{/if}
</div>

<style>
	.optimization-panel {
		padding: 1.5rem;
		background: var(--bg-secondary, #1a1a2e);
		border-radius: 12px;
		color: var(--text-primary, #e0e0e0);
	}
	
	.panel-header {
		margin-bottom: 2rem;
		padding-bottom: 1rem;
		border-bottom: 1px solid var(--border-color, #333);
	}
	
	.header-content {
		display: flex;
		align-items: center;
		gap: 1rem;
	}
	
	.header-icon {
		color: var(--accent-yellow, #ffd700);
	}
	
	h2 {
		margin: 0;
		font-size: 1.5rem;
		color: var(--text-primary, #e0e0e0);
	}
	
	.subtitle {
		margin: 0.25rem 0 0 0;
		font-size: 0.875rem;
		color: var(--text-secondary, #888);
	}
	
	.config-section, .progress-section, .result-section, .current-best-section {
		margin-top: 1.5rem;
		padding: 1.5rem;
		background: var(--bg-tertiary, #252540);
		border-radius: 8px;
	}
	
	h3 {
		margin: 0 0 1rem 0;
		font-size: 1.125rem;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	
	.config-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 1rem;
		margin-bottom: 1rem;
	}
	
	.config-item {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
	
	label {
		font-size: 0.875rem;
		color: var(--text-secondary, #888);
		font-weight: 500;
	}
	
	input, select {
		padding: 0.5rem;
		background: var(--bg-input, #1a1a2e);
		border: 1px solid var(--border-color, #333);
		border-radius: 4px;
		color: var(--text-primary, #e0e0e0);
		font-size: 0.875rem;
	}
	
	input:focus, select:focus {
		outline: none;
		border-color: var(--accent-blue, #4a9eff);
	}
	
	input:disabled, select:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	
	.hint {
		font-size: 0.75rem;
		color: var(--text-muted, #666);
	}
	
	.config-switches {
		margin-top: 1rem;
	}
	
	.switch-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		cursor: pointer;
	}
	
	.switch-item input[type="checkbox"] {
		width: auto;
	}
	
	.action-buttons {
		margin-top: 1.5rem;
		display: flex;
		gap: 1rem;
	}
	
	button {
		padding: 0.75rem 1.5rem;
		border: none;
		border-radius: 6px;
		font-size: 0.875rem;
		font-weight: 600;
		cursor: pointer;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		transition: all 0.2s;
	}
	
	.btn-primary {
		background: var(--accent-blue, #4a9eff);
		color: white;
	}
	
	.btn-primary:hover:not(:disabled) {
		background: var(--accent-blue-dark, #3a7ecf);
		transform: translateY(-2px);
	}
	
	.btn-primary:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
	
	.btn-success {
		background: var(--accent-green, #00ff88);
		color: #0a0a0a;
	}
	
	.btn-success:hover {
		background: var(--accent-green-light, #33ffaa);
		transform: translateY(-2px);
	}
	
	.btn-outline {
		background: transparent;
		border: 1px solid var(--accent-blue, #4a9eff);
		color: var(--accent-blue, #4a9eff);
	}
	
	.btn-outline:hover {
		background: var(--accent-blue, #4a9eff);
		color: white;
	}
	
	.error-message {
		margin-top: 1rem;
		padding: 1rem;
		background: rgba(255, 0, 0, 0.1);
		border: 1px solid rgba(255, 0, 0, 0.3);
		border-radius: 6px;
		color: #ff4444;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	
	.progress-bar-container {
		width: 100%;
		height: 8px;
		background: var(--bg-input, #1a1a2e);
		border-radius: 4px;
		overflow: hidden;
		margin-bottom: 1rem;
	}
	
	.progress-bar {
		height: 100%;
		background: linear-gradient(90deg, var(--accent-blue, #4a9eff), var(--accent-green, #00ff88));
		transition: width 0.3s ease;
	}
	
	.progress-details {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 1rem;
	}
	
	.detail-item {
		display: flex;
		justify-content: space-between;
		padding: 0.5rem;
		background: var(--bg-input, #1a1a2e);
		border-radius: 4px;
	}
	
	.label {
		color: var(--text-secondary, #888);
		font-size: 0.875rem;
	}
	
	.value {
		color: var(--text-primary, #e0e0e0);
		font-weight: 600;
	}
	
	.current-best {
		margin-top: 1rem;
		padding: 0.75rem;
		background: rgba(0, 255, 136, 0.1);
		border: 1px solid rgba(0, 255, 136, 0.3);
		border-radius: 6px;
		color: var(--accent-green, #00ff88);
	}
	
	.result-section.success {
		border: 1px solid var(--accent-green, #00ff88);
	}
	
	.result-section.error {
		border: 1px solid #ff4444;
	}
	
	.result-stats {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 1rem;
		margin-bottom: 1.5rem;
	}
	
	.stat-card {
		padding: 1rem;
		background: var(--bg-input, #1a1a2e);
		border-radius: 6px;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	
	.stat-label {
		font-size: 0.75rem;
		color: var(--text-secondary, #888);
		text-transform: uppercase;
	}
	
	.stat-value {
		font-size: 1.5rem;
		font-weight: 700;
		color: var(--accent-green, #00ff88);
	}
	
	.best-params, .best-info {
		margin-top: 1rem;
	}
	
	h4 {
		margin: 0 0 0.75rem 0;
		font-size: 1rem;
		color: var(--text-secondary, #888);
	}
	
	.params-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
		gap: 0.5rem;
		margin-bottom: 1rem;
	}
	
	.param-item {
		padding: 0.5rem;
		background: var(--bg-input, #1a1a2e);
		border-radius: 4px;
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	
	.param-key {
		font-size: 0.875rem;
		color: var(--text-secondary, #888);
	}
	
	.param-value {
		font-size: 0.875rem;
		color: var(--text-primary, #e0e0e0);
		font-weight: 600;
		font-family: 'Courier New', monospace;
	}
	
	.error-text {
		color: #ff4444;
		margin: 0.5rem 0;
	}
	
	.best-source-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1.5rem;
		padding: 1rem;
		background: var(--bg-input, #1a1a2e);
		border-radius: 8px;
		gap: 1rem;
		flex-wrap: wrap;
	}
	
	.source-pill {
		padding: 0.5rem 1rem;
		border-radius: 999px;
		background: rgba(74, 158, 255, 0.2);
		color: var(--accent-blue, #4a9eff);
		font-size: 0.875rem;
		font-weight: 600;
		border: 2px solid var(--accent-blue, #4a9eff);
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}
	
	.source-pill[data-active="false"] {
		background: rgba(255, 255, 255, 0.05);
		color: var(--text-secondary, #888);
		border-color: var(--border-color, #333);
	}
	
	.source-actions {
		display: flex;
		gap: 0.5rem;
		background: rgba(255, 255, 255, 0.03);
		padding: 0.25rem;
		border-radius: 8px;
	}
	
	.source-actions button {
		padding: 0.5rem 1rem;
		background: transparent;
		border: none;
		color: var(--text-secondary, #888);
		border-radius: 6px;
		font-size: 0.875rem;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.2s;
		position: relative;
	}
	
	.source-actions button:hover:not(:disabled) {
		background: rgba(74, 158, 255, 0.1);
		color: var(--accent-blue, #4a9eff);
	}
	
	.source-actions button.active {
		background: var(--accent-blue, #4a9eff);
		color: #fff;
		font-weight: 600;
		box-shadow: 0 2px 8px rgba(74, 158, 255, 0.3);
	}
	
	.source-actions button:disabled {
		opacity: 0.3;
		cursor: not-allowed;
	}
	
	.source-actions button:disabled:hover {
		background: transparent;
		color: var(--text-secondary, #888);
	}
	
	.metrics-section {
		margin-top: 1.5rem;
		padding: 1.5rem;
		background: var(--bg-tertiary, #252540);
		border-radius: 8px;
	}
	
	.metric-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
		gap: 1rem;
		margin-top: 1rem;
	}
	
	.metric-card {
		padding: 1.25rem;
		background: var(--bg-input, #1a1a2e);
		border: 2px solid var(--border-color, #333);
		border-radius: 8px;
		cursor: pointer;
		transition: all 0.2s;
	}
	
	.metric-card:hover {
		border-color: var(--accent-blue, #4a9eff);
		transform: translateY(-2px);
	}
	
	.metric-card.active {
		border-color: var(--accent-green, #00ff88);
		background: rgba(0, 255, 136, 0.05);
	}
	
	.metric-header h4 {
		margin: 0 0 0.25rem 0;
		font-size: 1rem;
		color: var(--text-primary, #e0e0e0);
	}
	
	.metric-description {
		margin: 0;
		font-size: 0.75rem;
		color: var(--text-secondary, #888);
	}
	
	.metric-content {
		margin-top: 1rem;
	}
	
	.metric-value {
		font-size: 1.75rem;
		font-weight: 700;
		color: var(--accent-green, #00ff88);
		margin-bottom: 0.75rem;
	}
	
	.metric-hint {
		margin: 0;
		font-size: 0.75rem;
		color: var(--text-muted, #666);
		font-style: italic;
	}
	
	.metric-source {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	
	.metric-source button {
		padding: 0.5rem;
		background: transparent;
		border: 1px solid var(--border-color, #333);
		color: var(--text-secondary, #888);
		border-radius: 4px;
		font-size: 0.75rem;
		cursor: pointer;
		transition: all 0.2s;
	}
	
	.metric-source button:hover:not(:disabled) {
		border-color: var(--accent-blue, #4a9eff);
		color: var(--accent-blue, #4a9eff);
	}
	
	.metric-source button.active {
		background: var(--accent-blue, #4a9eff);
		border-color: var(--accent-blue, #4a9eff);
		color: white;
		font-weight: 600;
	}
	
	.metric-source button.disabled,
	.metric-source button:disabled {
		opacity: 0.3;
		cursor: not-allowed;
	}
	
	.source-info h3 {
		margin: 0 0 0.5rem 0;
	}
	
	.source-label {
		margin: 0;
		font-size: 0.875rem;
		color: var(--text-secondary, #888);
	}
	
	.score-badge {
		display: inline-block;
		margin-left: 0.5rem;
		padding: 0.25rem 0.5rem;
		background: rgba(0, 255, 136, 0.2);
		border-radius: 4px;
		color: var(--accent-green, #00ff88);
		font-weight: 600;
		font-family: 'Courier New', monospace;
	}
	
	.spin {
		animation: spin 1s linear infinite;
	}
	
	@keyframes spin {
		from { transform: rotate(0deg); }
		to { transform: rotate(360deg); }
	}
</style>
