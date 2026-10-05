<script>
	import { onMount } from 'svelte';
	import { sendCommandViaWS } from '$lib/utils/websocket';
	
	let loading = true;
	let saving = false;
	let error = null;
	let success = null;
	let hasUnsavedChanges = false;
	let debounceTimer = null;
	const AUTO_SAVE_DELAY = 2500;
	
	// Valeurs par défaut (seront écrasées par loadConfig)
	const DEFAULT_CONFIG = {
		// Filtrage GradientBoosting
		gb_filter_enabled: true,
		gb_min_confidence: 0.55,
		// Calibration ML
		ml_calibration_enabled: false,
		ml_calib_min_winrate: 45,
		ml_calib_decay_days: 14,
		// Threshold Optimizer
		threshold_optimizer_enabled: false,
		threshold_min: 0.45,
		threshold_max: 0.70,
		// Drift Detection
		drift_detection_enabled: true
	};
	
	let config = { ...DEFAULT_CONFIG };
	
	let status = null;
	let thresholds = null;
	
	async function loadConfig() {
		loading = true;
		error = null;
		try {
			// Charger depuis /api/config (config principale) + /api/ml/status
			const [configRes, statusRes] = await Promise.all([
				fetch('/api/config'),
				fetch('/api/ml/status')
			]);
			
			if (configRes.ok) {
				const data = await configRes.json();
				console.log('📥 MLConfigPanel loaded from /api/config:', data);
				// Fusionner avec les valeurs par défaut (data écrase les défauts)
				config = { ...DEFAULT_CONFIG, ...data };
				console.log('📋 MLConfigPanel config après fusion:', {
					gb_filter_enabled: config.gb_filter_enabled,
					gb_min_confidence: config.gb_min_confidence,
					ml_calibration_enabled: config.ml_calibration_enabled,
					ml_calib_min_winrate: config.ml_calib_min_winrate
				});
			}
			if (statusRes.ok) {
				status = await statusRes.json();
			}
			
			// Charger les seuils si optimizer activé
			if (config.threshold_optimizer_enabled) {
				await loadThresholds();
			}
		} catch (err) {
			error = err.message;
		} finally {
			loading = false;
		}
	}
	
	async function loadThresholds() {
		try {
			const res = await fetch('/api/ml/thresholds');
			if (res.ok) {
				thresholds = await res.json();
			}
		} catch (err) {
			console.error('Erreur chargement seuils:', err);
		}
	}
	
	// 🔥 Sauvegarde via WebSocket (identique à VariablesPanel)
	function triggerAutoSave(key, value) {
		config[key] = value;
		hasUnsavedChanges = true;
		
		console.log(`📝 MLConfig AutoSave queued: ${key} = ${value}`);
		
		if (debounceTimer) {
			clearTimeout(debounceTimer);
		}
		
		debounceTimer = setTimeout(async () => {
			await autoSaveConfig();
		}, AUTO_SAVE_DELAY);
	}
	
	async function autoSaveConfig() {
		if (saving || !hasUnsavedChanges) return;
		
		saving = true;
		error = null;
		success = null;
		
		try {
			const result = await sendCommandViaWS('update_config', config);
			
			if (result && result.updated) {
				const updatedCount = Object.keys(result.updated).length;
				success = `✅ ${updatedCount} paramètre(s) sauvegardé(s)`;
				hasUnsavedChanges = false;
				console.log('✅ MLConfig sauvegardée via WebSocket:', result.updated);
				setTimeout(() => success = null, 3000);
			} else {
				success = '✅ Configuration sauvegardée';
				hasUnsavedChanges = false;
				setTimeout(() => success = null, 3000);
			}
		} catch (err) {
			console.error('❌ Erreur sauvegarde WebSocket:', err);
			error = `Erreur: ${err.message || 'WebSocket non connecté'}`;
			setTimeout(() => error = null, 5000);
		} finally {
			saving = false;
			debounceTimer = null;
		}
	}
	
	async function resetOptimizers() {
		if (!confirm('Réinitialiser tous les optimiseurs ML?')) return;
		
		try {
			const res = await fetch('/api/ml/reset', { method: 'POST' });
			if (res.ok) {
				success = 'Optimiseurs réinitialisés!';
				await loadConfig();
				setTimeout(() => success = null, 3000);
			}
		} catch (err) {
			error = err.message;
		}
	}
	
	onMount(() => {
		loadConfig();
	});
</script>

<div class="ml-config-panel">
	<div class="header">
		<h3>⚙️ Configuration ML Phase 2D</h3>
		<div class="header-actions">
			{#if hasUnsavedChanges}
				<span class="unsaved-indicator">⏳ Sauvegarde...</span>
			{/if}
			<button class="refresh-btn" on:click={loadConfig} disabled={loading}>
				🔄
			</button>
		</div>
	</div>
	
	{#if error}
		<div class="alert error">{error}</div>
	{/if}
	
	{#if success}
		<div class="alert success">{success}</div>
	{/if}
	
	{#if loading}
		<div class="loading">Chargement...</div>
	{:else}
		<div class="modules">
			<!-- 🎯 Filtrage ML GradientBoosting -->
			<div class="module-card">
				<div class="module-header">
					<label class="toggle">
						<input 
							type="checkbox" 
							bind:checked={config.gb_filter_enabled}
							on:change={() => triggerAutoSave('gb_filter_enabled', config.gb_filter_enabled)}
						/>
						<span class="slider"></span>
					</label>
					<div class="module-info">
						<h4>🎯 Filtrage ML GradientBoosting</h4>
						<p>Bloquer automatiquement les trades avec faible probabilité de succès</p>
					</div>
					{#if status?.modules?.trade_filter?.model_loaded}
						<span class="badge success">Modèle chargé</span>
					{:else}
						<span class="badge warning">Non chargé</span>
					{/if}
				</div>
				
				{#if config.gb_filter_enabled}
					<div class="module-params">
						<label>
							<span>Seuil de Confiance Minimum: {Math.round(config.gb_min_confidence * 100)}%</span>
							<span class="param-hint">Probabilité minimale de WIN pour accepter le trade (25-80%)</span>
							<input 
								type="range" 
								min="0.25" 
								max="0.80" 
								step="0.01"
								bind:value={config.gb_min_confidence}
								on:change={() => triggerAutoSave('gb_min_confidence', config.gb_min_confidence)}
							/>
						</label>
					</div>
				{/if}
			</div>
			
			<!-- ⚖️ Calibration ML Auto-Adaptative -->
			<div class="module-card">
				<div class="module-header">
					<label class="toggle">
						<input 
							type="checkbox" 
							bind:checked={config.ml_calibration_enabled}
							on:change={() => triggerAutoSave('ml_calibration_enabled', config.ml_calibration_enabled)}
						/>
						<span class="slider"></span>
					</label>
					<div class="module-info">
						<h4>⚖️ Calibration ML Auto-Adaptative</h4>
						<p>Ajuste automatiquement la confiance ML en fonction du WinRate réel observé</p>
					</div>
					<span class="badge phase">Phase 2D</span>
				</div>
				
				{#if config.ml_calibration_enabled}
					<div class="module-params">
						<label>
							<span>WinRate Min: {config.ml_calib_min_winrate}%</span>
							<span class="param-hint">Seuil WR calibré pour accepter (30-60%)</span>
							<input 
								type="range" 
								min="30" 
								max="60" 
								step="1"
								bind:value={config.ml_calib_min_winrate}
								on:change={() => triggerAutoSave('ml_calib_min_winrate', config.ml_calib_min_winrate)}
							/>
						</label>
						<label>
							<span>Demi-vie (Decay): {config.ml_calib_decay_days} jours</span>
							<span class="param-hint">Impact historique divisé par 2 après X jours (7-60)</span>
							<input 
								type="range" 
								min="7" 
								max="60" 
								step="1"
								bind:value={config.ml_calib_decay_days}
								on:change={() => triggerAutoSave('ml_calib_decay_days', config.ml_calib_decay_days)}
							/>
						</label>
						<label>
							<span>Demi-vie (Decay): {config.ml_calib_decay_days} jours</span>
							<span class="param-hint">Impact historique divisé par 2 après X jours (7-60)</span>
							<input 
								type="range" 
								min="7" 
								max="60" 
								step="1"
								bind:value={config.ml_calib_decay_days}
								on:change={() => triggerAutoSave('ml_calib_decay_days', config.ml_calib_decay_days)}
							/>
						</label>
					</div>
				{/if}
			</div>
			
			<!-- Threshold Optimizer -->
			<div class="module-card" class:disabled={!config.threshold_optimizer_enabled}>
				<div class="module-header">
					<label class="toggle">
						<input 
							type="checkbox" 
							bind:checked={config.threshold_optimizer_enabled}
							on:change={() => triggerAutoSave('threshold_optimizer_enabled', config.threshold_optimizer_enabled)}
						/>
						<span class="slider"></span>
					</label>
					<div class="module-info">
						<h4>📊 Threshold Optimizer</h4>
						<p>Seuil dynamique par contexte (régime, session)</p>
					</div>
					<span class="badge phase">Phase 2D</span>
				</div>
				
				{#if config.threshold_optimizer_enabled}
					<div class="module-params">
						<label>
							<span>Min Threshold: {(config.threshold_min * 100).toFixed(0)}%</span>
							<input 
								type="range" 
								min="0.25" 
								max="0.60" 
								step="0.05"
								bind:value={config.threshold_min}
								on:change={() => triggerAutoSave('threshold_min', config.threshold_min)}
							/>
						</label>
						<label>
							<span>Max Threshold: {(config.threshold_max * 100).toFixed(0)}%</span>
							<input 
								type="range" 
								min="0.40" 
								max="0.80" 
								step="0.05"
								bind:value={config.threshold_max}
								on:change={() => triggerAutoSave('threshold_max', config.threshold_max)}
							/>
						</label>
					</div>
					
					{#if status?.modules?.threshold_optimizer}
						<div class="module-stats">
							<span>Contexts: {status.modules.threshold_optimizer.total_contexts || 0}</span>
							<span>Updates: {status.modules.threshold_optimizer.total_updates || 0}</span>
						</div>
					{/if}
				{/if}
			</div>
			
			<!-- Drift Detection -->
			<div class="module-card">
				<div class="module-header">
					<label class="toggle">
						<input 
							type="checkbox" 
							bind:checked={config.drift_detection_enabled}
							on:change={() => triggerAutoSave('drift_detection_enabled', config.drift_detection_enabled)}
						/>
						<span class="slider"></span>
					</label>
					<div class="module-info">
						<h4>⚠️ Drift Detection</h4>
						<p>Détecte les changements de comportement marché</p>
					</div>
					<span class="badge phase">Phase 2D</span>
				</div>
				
				{#if config.drift_detection_enabled && status?.modules?.drift_detector}
					<div class="module-stats">
						<span>Trades: {status.modules.drift_detector.total_trades || 0}</span>
						<span>Drifts: {status.modules.drift_detector.recent_drifts || 0}</span>
						{#if status.modules.drift_detector.pnl_stats?.count > 0}
							<span>PnL moy: {(status.modules.drift_detector.pnl_stats.mean * 100).toFixed(2)}%</span>
						{/if}
					</div>
				{/if}
			</div>
			
			<!-- Modules Phase 3 (à venir) -->
			<div class="module-card disabled">
				<div class="module-header">
					<label class="toggle">
						<input type="checkbox" disabled />
						<span class="slider"></span>
					</label>
					<div class="module-info">
						<h4>🧠 ML Regime Classifier</h4>
						<p>Classification ML du régime (LightGBM)</p>
					</div>
					<span class="badge coming">Phase 3A</span>
				</div>
			</div>
			
			<div class="module-card disabled">
				<div class="module-header">
					<label class="toggle">
						<input type="checkbox" disabled />
						<span class="slider"></span>
					</label>
					<div class="module-info">
						<h4>💰 Dynamic SL/TP Predictor</h4>
						<p>Prédit multiplicateurs optimaux (CatBoost)</p>
					</div>
					<span class="badge coming">Phase 3B</span>
				</div>
			</div>
		</div>
		
		<div class="actions">
			<span class="auto-save-info">💾 Sauvegarde automatique via WebSocket</span>
			<button class="reset-btn" on:click={resetOptimizers}>
				🔄 Reset Optimizers
			</button>
		</div>
	{/if}
</div>

<style>
	.ml-config-panel {
		padding: 1rem;
		background: var(--bg-secondary, #1a1a2e);
		border-radius: 8px;
	}
	
	.header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1rem;
	}
	
	.header h3 {
		margin: 0;
		color: var(--text-primary, #fff);
	}
	
	.header-actions {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}
	
	.unsaved-indicator {
		font-size: 0.8rem;
		color: #ffc107;
		background: rgba(255, 193, 7, 0.15);
		padding: 0.25rem 0.5rem;
		border-radius: 4px;
	}
	
	.refresh-btn {
		background: none;
		border: none;
		font-size: 1.2rem;
		cursor: pointer;
		padding: 0.5rem;
	}
	
	.param-hint {
		display: block;
		font-size: 0.75rem;
		color: var(--text-tertiary, #666);
		margin-top: 0.25rem;
	}
	
	.alert {
		padding: 0.75rem;
		border-radius: 4px;
		margin-bottom: 1rem;
	}
	
	.alert.error {
		background: rgba(220, 53, 69, 0.2);
		color: #ff6b6b;
		border: 1px solid rgba(220, 53, 69, 0.3);
	}
	
	.alert.success {
		background: rgba(40, 167, 69, 0.2);
		color: #51cf66;
		border: 1px solid rgba(40, 167, 69, 0.3);
	}
	
	.loading {
		text-align: center;
		padding: 2rem;
		color: var(--text-secondary, #888);
	}
	
	.modules {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}
	
	.module-card {
		background: var(--bg-tertiary, #252540);
		border-radius: 8px;
		padding: 1rem;
		border: 1px solid rgba(255, 255, 255, 0.1);
	}
	
	.module-card.disabled {
		opacity: 0.5;
	}
	
	.module-header {
		display: flex;
		align-items: center;
		gap: 1rem;
	}
	
	.module-info {
		flex: 1;
	}
	
	.module-info h4 {
		margin: 0 0 0.25rem 0;
		color: var(--text-primary, #fff);
		font-size: 0.95rem;
	}
	
	.module-info p {
		margin: 0;
		color: var(--text-secondary, #888);
		font-size: 0.8rem;
	}
	
	.module-params {
		margin-top: 1rem;
		padding-top: 1rem;
		border-top: 1px solid rgba(255, 255, 255, 0.1);
	}
	
	.module-params label {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
	}
	
	.module-params span {
		color: var(--text-secondary, #aaa);
		font-size: 0.85rem;
	}
	
	.module-params input[type="range"] {
		width: 100%;
		accent-color: var(--accent-color, #4a9eff);
	}
	
	.module-stats {
		display: flex;
		gap: 1rem;
		margin-top: 0.75rem;
		padding-top: 0.75rem;
		border-top: 1px solid rgba(255, 255, 255, 0.05);
	}
	
	.module-stats span {
		font-size: 0.75rem;
		color: var(--text-secondary, #888);
		background: rgba(255, 255, 255, 0.05);
		padding: 0.25rem 0.5rem;
		border-radius: 4px;
	}
	
	.badge {
		font-size: 0.7rem;
		padding: 0.25rem 0.5rem;
		border-radius: 4px;
		font-weight: 500;
	}
	
	.badge.success {
		background: rgba(40, 167, 69, 0.2);
		color: #51cf66;
	}
	
	.badge.warning {
		background: rgba(255, 193, 7, 0.2);
		color: #ffc107;
	}
	
	.badge.phase {
		background: rgba(74, 158, 255, 0.2);
		color: #4a9eff;
	}
	
	.badge.coming {
		background: rgba(108, 117, 125, 0.2);
		color: #6c757d;
	}
	
	/* Toggle switch */
	.toggle {
		position: relative;
		display: inline-block;
		width: 44px;
		height: 24px;
		flex-shrink: 0;
	}
	
	.toggle input {
		opacity: 0;
		width: 0;
		height: 0;
	}
	
	.slider {
		position: absolute;
		cursor: pointer;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background-color: #444;
		transition: 0.3s;
		border-radius: 24px;
	}
	
	.slider:before {
		position: absolute;
		content: "";
		height: 18px;
		width: 18px;
		left: 3px;
		bottom: 3px;
		background-color: white;
		transition: 0.3s;
		border-radius: 50%;
	}
	
	.toggle input:checked + .slider {
		background-color: #28a745;
	}
	
	.toggle input:checked + .slider:before {
		transform: translateX(20px);
	}
	
	.toggle input:disabled + .slider {
		opacity: 0.5;
		cursor: not-allowed;
	}
	
	.actions {
		display: flex;
		gap: 1rem;
		margin-top: 1.5rem;
		padding-top: 1rem;
		border-top: 1px solid rgba(255, 255, 255, 0.1);
	}
	
	.auto-save-info {
		flex: 1;
		padding: 0.75rem;
		color: var(--text-secondary, #888);
		font-size: 0.85rem;
	}
	
	.reset-btn {
		padding: 0.75rem 1rem;
		background: rgba(220, 53, 69, 0.2);
		color: #ff6b6b;
		border: 1px solid rgba(220, 53, 69, 0.3);
		border-radius: 6px;
		cursor: pointer;
	}
	
	.reset-btn:hover {
		background: rgba(220, 53, 69, 0.3);
	}
</style>
