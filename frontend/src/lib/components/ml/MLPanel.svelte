<script>
	import { onMount } from 'svelte';
	import { sendCommandViaWS } from '$lib/utils/websocket';
	import CorrelationAnalytics from './CorrelationAnalytics.svelte';
	import MLCONTENT_GB_Variables from './MLCONTENT_GB_Variables.svelte';
	import MLConfigPanel from './MLConfigPanel.svelte';
	
	// Configuration GB avec valeurs par défaut (identique à VariablesPanel)
	let config = {
		// GradientBoosting hyperparameters
		gb_filter_enabled: true,
		gb_min_confidence: 0.50,
		gb_n_estimators: 100,
		gb_max_depth: 3,
		gb_learning_rate: 0.1,
		gb_min_samples_split: 2,
		gb_min_samples_leaf: 1,
		gb_subsample: 1.0,
		gb_max_iter: 100,
		gb_l2_regularization: 0.0,
		gb_max_leaf_nodes: 31,
		gb_early_stopping: true,
		gb_validation_fraction: 0.1,
		gb_n_iter_no_change: 10,
		gb_tol: 0.0001,
		// Calibration ML
		ml_calibration_enabled: false,
		ml_calib_live_weight: 0.8,
		ml_calib_dryrun_weight: 0.5,
		ml_calib_decay_days: 30,
		ml_calib_min_trades: 20,
		ml_calib_min_winrate: 45
	};
	
	let configLoaded = false;
	let activeTab = 'correlations';
	let saveMessage = '';
	let loading = false;
	let hasUnsavedChanges = false;
	let debounceTimer = null;
	const AUTO_SAVE_DELAY = 2500; // 2.5 secondes comme VariablesPanel
	
	onMount(async () => {
		await loadConfig();
	});
	
	async function loadConfig() {
		try {
			const response = await fetch('/api/config');
			if (response.ok) {
				const data = await response.json();
				// Fusionner avec les valeurs par défaut
				config = { ...config, ...data };
				configLoaded = true;
			}
		} catch (e) {
			console.warn('Config non chargée, utilisation des valeurs par défaut');
			configLoaded = true;
		}
	}
	
	// 🔥 Fonction triggerAutoSave identique à VariablesPanel (WebSocket + debounce)
	function triggerAutoSave(key, value) {
		// Mettre à jour la config locale
		config[key] = value;
		hasUnsavedChanges = true;
		
		console.log(`📝 AutoSave queued: ${key} = ${value}`);
		
		// Annuler le timer précédent
		if (debounceTimer) {
			clearTimeout(debounceTimer);
		}
		
		// Déclencher sauvegarde après délai
		debounceTimer = setTimeout(async () => {
			await autoSaveConfig();
		}, AUTO_SAVE_DELAY);
	}
	
	// 🔥 Sauvegarde via WebSocket (comme VariablesPanel)
	async function autoSaveConfig() {
		if (loading || !hasUnsavedChanges) {
			return;
		}
		
		loading = true;
		saveMessage = '';
		
		try {
			const result = await sendCommandViaWS('update_config', config);
			
			if (result && result.updated) {
				const updatedCount = Object.keys(result.updated).length;
				saveMessage = `✅ ${updatedCount} paramètre(s) sauvegardé(s)`;
				hasUnsavedChanges = false;
				console.log('✅ Config sauvegardée via WebSocket:', result.updated);
				setTimeout(() => (saveMessage = ''), 3000);
			} else {
				saveMessage = `✅ Configuration sauvegardée`;
				hasUnsavedChanges = false;
				setTimeout(() => (saveMessage = ''), 3000);
			}
		} catch (err) {
			console.error('❌ Erreur sauvegarde WebSocket:', err);
			saveMessage = `❌ Erreur: ${err.message || 'WebSocket non connecté'}`;
			setTimeout(() => (saveMessage = ''), 5000);
		} finally {
			loading = false;
			debounceTimer = null;
		}
	}
	
	function handleParamsApplied(event) {
		console.log('Params applied:', event.detail);
	}
</script>

<div class="ml-panel">
	<div class="ml-header">
		<h1>🤖 Machine Learning</h1>
		<p class="subtitle">Analyse des corrélations & Optimisation GradientBoosting</p>
		{#if saveMessage}
			<div class="save-status" class:success={saveMessage.includes('✅')} class:error={saveMessage.includes('❌')}>
				{saveMessage}
			</div>
		{/if}
		{#if hasUnsavedChanges}
			<div class="unsaved-indicator">⏳ Sauvegarde en attente...</div>
		{/if}
	</div>
	
	<div class="ml-tabs">
		<button 
			class="tab" 
			class:active={activeTab === 'correlations'}
			on:click={() => activeTab = 'correlations'}
		>
			<span class="icon">🔗</span>
			<span class="label">Corrélations</span>
		</button>
		<button 
			class="tab" 
			class:active={activeTab === 'optimization'}
			on:click={() => activeTab = 'optimization'}
		>
			<span class="icon">⚡</span>
			<span class="label">Optimisation GB</span>
		</button>
		<button 
			class="tab" 
			class:active={activeTab === 'config'}
			on:click={() => activeTab = 'config'}
		>
			<span class="icon">⚙️</span>
			<span class="label">Config ML</span>
		</button>
	</div>
	
	<div class="ml-content">
		{#if activeTab === 'correlations'}
			<CorrelationAnalytics />
		{:else if activeTab === 'optimization'}
			{#if configLoaded}
				<MLCONTENT_GB_Variables {config} {triggerAutoSave} on:paramsApplied={handleParamsApplied} />
			{:else}
				<div class="loading">⏳ Chargement de la configuration...</div>
			{/if}
		{:else if activeTab === 'config'}
			<MLConfigPanel />
		{/if}
	</div>
</div>

<style>
	.ml-panel {
		height: 100%;
		display: flex;
		flex-direction: column;
		background: var(--bg-primary, #0f0f1a);
	}
	
	.ml-header {
		padding: 1.5rem;
		text-align: center;
		border-bottom: 1px solid var(--border-color, #333);
	}
	
	.ml-header h1 {
		margin: 0 0 0.5rem 0;
		font-size: 1.75rem;
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
		background-clip: text;
	}
	
	.subtitle {
		margin: 0;
		color: var(--text-secondary, #888);
		font-size: 0.9rem;
	}
	
	.ml-tabs {
		display: flex;
		gap: 0.5rem;
		padding: 1rem 1.5rem;
		background: var(--bg-secondary, #1a1a2e);
		border-bottom: 1px solid var(--border-color, #333);
	}
	
	.tab {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.75rem 1.5rem;
		background: var(--bg-tertiary, #252540);
		border: 2px solid transparent;
		border-radius: 8px;
		color: var(--text-secondary, #888);
		font-size: 0.95rem;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s ease;
	}
	
	.tab:hover {
		border-color: var(--accent-color, #667eea);
		color: var(--text-primary, #fff);
	}
	
	.tab.active {
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		color: white;
		border-color: transparent;
	}
	
	.tab .icon {
		font-size: 1.1rem;
	}
	
	.ml-content {
		flex: 1;
		overflow-y: auto;
		padding: 1rem;
	}
	
	.loading {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 200px;
		color: var(--text-secondary, #888);
		font-size: 1.1rem;
	}
	
	.save-status {
		margin-top: 0.5rem;
		padding: 0.5rem 1rem;
		border-radius: 6px;
		font-size: 0.85rem;
		font-weight: 500;
	}
	
	.save-status.success {
		background: rgba(40, 167, 69, 0.2);
		color: #51cf66;
		border: 1px solid rgba(40, 167, 69, 0.3);
	}
	
	.save-status.error {
		background: rgba(220, 53, 69, 0.2);
		color: #ff6b6b;
		border: 1px solid rgba(220, 53, 69, 0.3);
	}
	
	.unsaved-indicator {
		margin-top: 0.5rem;
		padding: 0.35rem 0.75rem;
		background: rgba(255, 193, 7, 0.15);
		color: #ffc107;
		border-radius: 4px;
		font-size: 0.8rem;
	}
</style>
