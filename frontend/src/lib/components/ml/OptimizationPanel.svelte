<script>
	import { onMount, onDestroy } from 'svelte';
	import { createEventDispatcher } from 'svelte';
	import { Activity, Zap, TrendingUp, Cpu, CheckCircle, AlertCircle, Loader } from 'lucide-svelte';
	
	const dispatch = createEventDispatcher();
	
	let optimizationConfig = {
		n_trials: 100,
		timeout: null,
		metric: 'trading_composite',
		use_gpu: false,
		max_samples: null
	};
	
	let currentTask = null;
	let taskStatus = null;
	let bestParams = null;
	let optimizationHistory = null;
	let isLoading = false;
	let errorMessage = null;
	let statusInterval = null;
	
	// Charger meilleurs params et historique au montage
	onMount(async () => {
		await loadBestParams();
		await loadHistory();
	});
	
	onDestroy(() => {
		if (statusInterval) {
			clearInterval(statusInterval);
		}
	});
	
	async function loadBestParams() {
		try {
			const response = await fetch('/api/ml/optimize/best');
			const data = await response.json();
			if (data.found) {
				bestParams = data;
			}
		} catch (error) {
			console.error('Error loading best params:', error);
		}
	}
	
	async function loadHistory() {
		try {
			const response = await fetch('/api/ml/optimize/history?limit=20');
			optimizationHistory = await response.json();
		} catch (error) {
			console.error('Error loading history:', error);
		}
	}
	
	async function startOptimization() {
		try {
			isLoading = true;
			errorMessage = null;
			
			// Construire query params
			const params = new URLSearchParams();
			params.append('n_trials', optimizationConfig.n_trials);
			if (optimizationConfig.timeout) {
				params.append('timeout', optimizationConfig.timeout);
			}
			params.append('metric', optimizationConfig.metric);
			params.append('use_gpu', optimizationConfig.use_gpu);
			if (optimizationConfig.max_samples) {
				params.append('max_samples', optimizationConfig.max_samples);
			}
			
			const response = await fetch(`/api/ml/optimize/start?${params}`, {
				method: 'POST'
			});
			
			if (!response.ok) {
				const error = await response.json();
				throw new Error(error.detail || 'Erreur démarrage optimisation');
			}
			
			const data = await response.json();
			currentTask = data.task_id;
			
			// Démarrer polling du status
			startStatusPolling();
			
		} catch (error) {
			errorMessage = error.message;
			console.error('Error starting optimization:', error);
		} finally {
			isLoading = false;
		}
	}
	
	function startStatusPolling() {
		if (statusInterval) {
			clearInterval(statusInterval);
		}
		
		statusInterval = setInterval(async () => {
			if (!currentTask) return;
			
			try {
				const response = await fetch(`/api/ml/tasks/${currentTask}`);
				const data = await response.json();
				taskStatus = data;
				
				// Si terminé ou échoué, arrêter polling
				if (data.status === 'completed' || data.status === 'failed') {
					clearInterval(statusInterval);
					statusInterval = null;
					
					// Recharger best params et history
					if (data.status === 'completed') {
						await loadBestParams();
						await loadHistory();
					}
				}
			} catch (error) {
				console.error('Error polling status:', error);
			}
		}, 2000); // Poll toutes les 2 secondes
	}
	
	async function applyBestParams() {
		try {
			isLoading = true;
			errorMessage = null;
			
			const response = await fetch('/api/ml/optimize/apply', {
				method: 'POST'
			});
			
			if (!response.ok) {
				const error = await response.json();
				throw new Error(error.detail || 'Erreur application params');
			}
			
			const data = await response.json();
			alert(data.message + '\n\n⚠️ ' + data.warning);
			
			// Émettre un événement pour notifier VariablesPanel de recharger la config
			dispatch('paramsApplied');
			
		} catch (error) {
			errorMessage = error.message;
			console.error('Error applying params:', error);
		} finally {
			isLoading = false;
		}
	}
	
	function formatScore(score) {
		return score ? (score * 100).toFixed(2) + '%' : 'N/A';
	}
	
	function formatParam(value) {
		if (typeof value === 'number') {
			return value.toFixed(4);
		}
		return value;
	}
</script>

<div class="optimization-panel">
	<!-- Header -->
	<div class="panel-header">
		<div class="header-content">
			<Zap size={24} class="header-icon" />
			<div>
				<h2>Optimisation Hyperparamètres</h2>
				<p class="subtitle">Recherche automatique des meilleurs paramètres XGBoost</p>
			</div>
		</div>
	</div>
	
	<!-- Configuration -->
	<div class="config-section">
		<h3><Activity size={18} /> Configuration</h3>
		
		<div class="config-grid">
			<div class="config-item">
				<label for="n_trials">Nombre de trials</label>
				<input 
					id="n_trials"
					type="number" 
					bind:value={optimizationConfig.n_trials}
					min="10"
					max="1000"
					disabled={taskStatus && taskStatus.status === 'running'}
				/>
				<span class="hint">10-1000 (recommandé: 50-200)</span>
			</div>
			
			<div class="config-item">
				<label for="metric">Métrique</label>
				<select 
					id="metric"
					bind:value={optimizationConfig.metric}
					disabled={taskStatus && taskStatus.status === 'running'}
				>
					<option value="trading_composite">Trading Composite (recommandé)</option>
					<option value="f1_score">F1-Score</option>
					<option value="accuracy">Accuracy</option>
					<option value="roc_auc">ROC AUC</option>
				</select>
				<span class="hint">Métrique à maximiser</span>
			</div>
			
			<div class="config-item">
				<label for="timeout">Timeout (secondes)</label>
				<input 
					id="timeout"
					type="number" 
					bind:value={optimizationConfig.timeout}
					min="60"
					placeholder="Illimité"
					disabled={taskStatus && taskStatus.status === 'running'}
				/>
				<span class="hint">Optionnel (ex: 3600 = 1h)</span>
			</div>
			
			<div class="config-item">
				<label for="max_samples">Limite samples</label>
				<input 
					id="max_samples"
					type="number" 
					bind:value={optimizationConfig.max_samples}
					min="100"
					placeholder="Tous"
					disabled={taskStatus && taskStatus.status === 'running'}
				/>
				<span class="hint">Pour rapidité (optionnel)</span>
			</div>
		</div>
		
		<div class="config-switches">
			<label class="switch-item">
				<input 
					type="checkbox" 
					bind:checked={optimizationConfig.use_gpu}
					disabled={taskStatus && taskStatus.status === 'running'}
				/>
				<span><Cpu size={16} /> Utiliser GPU (30x plus rapide)</span>
			</label>
		</div>
		
		<div class="action-buttons">
			<button 
				class="btn-primary"
				on:click={startOptimization}
				disabled={isLoading || (taskStatus && taskStatus.status === 'running')}
			>
				{#if isLoading || (taskStatus && taskStatus.status === 'running')}
					<Loader size={16} class="spin" />
					{taskStatus?.status === 'running' ? 'Optimisation en cours...' : 'Démarrage...'}
				{:else}
					<Zap size={16} />
					Lancer optimisation
				{/if}
			</button>
		</div>
		
		{#if errorMessage}
			<div class="error-message">
				<AlertCircle size={16} />
				{errorMessage}
			</div>
		{/if}
	</div>
	
	<!-- Progression en temps réel -->
	{#if taskStatus && taskStatus.status !== 'completed' && taskStatus.status !== 'failed'}
		<div class="progress-section">
			<h3><TrendingUp size={18} /> Progression</h3>
			
			<div class="progress-bar-container">
				<div class="progress-bar" style="width: {taskStatus.progress || 0}%"></div>
			</div>
			
			<div class="progress-details">
				<div class="detail-item">
					<span class="label">Trial:</span>
					<span class="value">{taskStatus.current_trial || 0} / {taskStatus.n_trials || 0}</span>
				</div>
				<div class="detail-item">
					<span class="label">Progress:</span>
					<span class="value">{taskStatus.progress || 0}%</span>
				</div>
				<div class="detail-item">
					<span class="label">Stage:</span>
					<span class="value">{taskStatus.stage || 'Initializing...'}</span>
				</div>
			</div>
			
			{#if taskStatus.best_score}
				<div class="current-best">
					<strong>Meilleur score actuel:</strong> {formatScore(taskStatus.best_score)}
				</div>
			{/if}
		</div>
	{/if}
	
	<!-- Résultat de l'optimisation -->
	{#if taskStatus && taskStatus.status === 'completed'}
		<div class="result-section success">
			<h3><CheckCircle size={18} /> Optimisation terminée</h3>
			
			<div class="result-stats">
				<div class="stat-card">
					<span class="stat-label">Meilleur score</span>
					<span class="stat-value">{formatScore(taskStatus.best_score)}</span>
				</div>
				<div class="stat-card">
					<span class="stat-label">Trials complétés</span>
					<span class="stat-value">{taskStatus.n_trials_completed || 0}</span>
				</div>
				<div class="stat-card">
					<span class="stat-label">Trials pruned</span>
					<span class="stat-value">{taskStatus.n_trials_pruned || 0}</span>
				</div>
			</div>
			
			{#if taskStatus.best_params}
				<div class="best-params">
					<h4>Meilleurs hyperparamètres</h4>
					<div class="params-grid">
						{#each Object.entries(taskStatus.best_params) as [key, value]}
							<div class="param-item">
								<span class="param-key">{key}:</span>
								<span class="param-value">{formatParam(value)}</span>
							</div>
						{/each}
					</div>
				</div>
			{/if}
			
			<button class="btn-success" on:click={applyBestParams}>
				<CheckCircle size={16} />
				Appliquer ces paramètres
			</button>
		</div>
	{/if}
	
	{#if taskStatus && taskStatus.status === 'failed'}
		<div class="result-section error">
			<h3><AlertCircle size={18} /> Échec optimisation</h3>
			<p class="error-text">{taskStatus.error || 'Erreur inconnue'}</p>
		</div>
	{/if}
	
	<!-- Meilleurs params actuels -->
	{#if bestParams && bestParams.found}
		<div class="current-best-section">
			<h3>📊 Meilleurs paramètres actuels</h3>
			
			<div class="best-info">
				<p><strong>Score:</strong> {formatScore(bestParams.score)}</p>
				<p><strong>Trial:</strong> #{bestParams.trial_number}</p>
				<p><strong>Total trials:</strong> {bestParams.total_trials}</p>
				{#if bestParams.datetime}
					<p><strong>Date:</strong> {new Date(bestParams.datetime).toLocaleString()}</p>
				{/if}
			</div>
			
			<div class="params-grid">
				{#each Object.entries(bestParams.params) as [key, value]}
					<div class="param-item">
						<span class="param-key">{key}:</span>
						<span class="param-value">{formatParam(value)}</span>
					</div>
				{/each}
			</div>
			
			<button class="btn-outline" on:click={applyBestParams}>
				<CheckCircle size={16} />
				Appliquer ces paramètres
			</button>
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
	
	.spin {
		animation: spin 1s linear infinite;
	}
	
	@keyframes spin {
		from { transform: rotate(0deg); }
		to { transform: rotate(360deg); }
	}
</style>
