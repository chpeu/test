<script>
	import { onMount } from 'svelte';

	const DEFAULTS = {
		// Patterns Techniques
		use_breakout: true,
		use_snr: true,
		use_wick: true,
		use_divergence: true,
		// Patterns de Bougies (Candlestick Patterns)
		use_engulfing: true,
		use_hammer: true,
		use_shooting_star: true,
		use_doji: true,
		use_marubozu: true,
		use_morning_star: true,
		use_evening_star: true,
		// Indicateurs Techniques
		snr_threshold: 0.25,
		breakout_threshold: 0.35,
		wick_ratio_max: 2.8,
		di_gap_min: 4.0,
		di_gap_adx_threshold: 25,
		trend_timeframe: '15m',
		// Optimal ATR ranges
		optimal_atr_min_1m: 0.12,
		optimal_atr_max_1m: 0.75,
		optimal_atr_min_5m: 0.22,
		optimal_atr_max_5m: 1.4,
		// Validation Setups (déplacé depuis Stratégie)
		use_confluence: false,
		volume_multiplier: 0.95,
		min_score_required: 7.5,
		// Money Management
		account_size: 1000.0,
		risk_per_trade: 2.0,
		// TP/SL Mode
		tp_sl_mode: 'FIXE',
		// Mode FIXE
		tp_percent: 0.6,
		sl_percent: 0.25,
		partial_tp_percent: 50,
		// Mode ATR
		atr_mult_tp: 1.5,
		atr_mult_sl: 1.0,
		atr_min: 0.15,
		atr_max: 1.5,
		// Mode ESCALIER (TP_MULTI) - 4 niveaux
		escalier_level1_pnl: 0.20,
		escalier_level1_size: 25,
		escalier_level2_pnl: 0.35,
		escalier_level2_size: 25,
		escalier_level3_pnl: 0.50,
		escalier_level3_size: 25,
		escalier_level4_pnl: 0.80,
		escalier_level4_size: 25,
		// Trailing Stop Adaptatif (tous modes)
		trailing_enabled: true,
		trailing_trigger_pnl: 0.25,
		trailing_atr_multiplier: 0.4,
		trailing_min_distance: 0.08,
		trailing_max_distance: 0.25
	};

	let config = { ...DEFAULTS };
	let loading = false;
	let saveMessage = '';
	let activeSubTab = 'setups';
	let viewMode = 'FIXE'; // Mode affiché dans TP/SL (ne modifie PAS config.tp_sl_mode)

	// Auto-ajustement sliders Escalier pour que la somme = 100%
	function autoAdjustEscalierSize(changedLevel) {
		const levels = [1, 2, 3, 4];
		const otherLevels = levels.filter(l => l !== changedLevel);

		const changedValue = config[`escalier_level${changedLevel}_size`];
		const totalOthers = otherLevels.reduce((sum, l) => sum + config[`escalier_level${l}_size`], 0);
		const totalAll = changedValue + totalOthers;

		if (totalAll > 100) {
			// Réduire proportionnellement les autres niveaux
			const excess = totalAll - 100;
			const reductionRatio = excess / totalOthers;

			otherLevels.forEach(l => {
				const currentValue = config[`escalier_level${l}_size`];
				const reduction = currentValue * reductionRatio;
				config[`escalier_level${l}_size`] = Math.max(0, Math.round(currentValue - reduction));
			});
		}
	}

	function autoAdjustEscalierPnL(changedLevel) {
		// S'assurer que les niveaux suivants sont >= niveau actuel
		const currentPnl = config[`escalier_level${changedLevel}_pnl`];

		for (let i = changedLevel + 1; i <= 4; i++) {
			if (config[`escalier_level${i}_pnl`] < currentPnl) {
				config[`escalier_level${i}_pnl`] = currentPnl;
			}
		}

		// S'assurer que les niveaux précédents sont <= niveau actuel
		for (let i = changedLevel - 1; i >= 1; i--) {
			if (config[`escalier_level${i}_pnl`] > currentPnl) {
				config[`escalier_level${i}_pnl`] = currentPnl;
			}
		}
	}

	onMount(async () => {
		await loadConfig();
	});

	async function loadConfig() {
		try {
			const res = await fetch('/api/state');
			if (res.ok) {
				const data = await res.json();
				if (data.config) {
					config = { ...DEFAULTS, ...data.config };
					viewMode = config.tp_sl_mode; // Sync viewMode avec le mode actif
				}
			}
		} catch (err) {
			console.error('Error loading config:', err);
		}
	}

	async function saveConfig() {
		loading = true;
		saveMessage = '';
		try {
			const res = await fetch('/api/config/update', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(config)
			});

			if (res.ok) {
				saveMessage = '✅ Configuration sauvegardée avec succès';
				setTimeout(() => (saveMessage = ''), 3000);
			} else {
				saveMessage = '❌ Erreur lors de la sauvegarde';
			}
		} catch (err) {
			console.error('Error saving config:', err);
			saveMessage = '❌ Erreur: Backend non accessible';
		} finally {
			loading = false;
		}
	}

	function resetDefaults() {
		if (confirm('Réinitialiser toutes les variables aux valeurs par défaut ?')) {
			config = { ...DEFAULTS };
			logConfigChange('ALL', 'Reset to defaults');
		}
	}

	function resetVariable(key) {
		const oldValue = config[key];
		config[key] = DEFAULTS[key];
		logConfigChange(key, `${oldValue} → ${DEFAULTS[key]}`);
	}

	function logConfigChange(key, change) {
		// Envoyer log de modification au backend
		fetch('/api/log/config', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				key,
				change,
				timestamp: new Date().toISOString()
			})
		}).catch(err => console.error('Error logging config change:', err));
	}

	// Watcher pour logger les changements
	$: if (config) {
		Object.keys(config).forEach(key => {
			const oldValue = DEFAULTS[key];
			// Note: dans un vrai système, on voudrait comparer avec la valeur précédente, pas DEFAULTS
		});
	}
</script>

<div class="variables-panel">
	<div class="panel-header">
		<h2>🎯 Variables de Trading</h2>
		<div class="header-actions">
			<button class="btn-secondary" on:click={resetDefaults}>🔄 Reset All</button>
			<button class="btn-primary" on:click={saveConfig} disabled={loading}>
				{loading ? '⏳ Saving...' : '💾 Save'}
			</button>
		</div>
	</div>

	{#if saveMessage}
		<div class="save-message" class:success={saveMessage.includes('✅')} class:error={saveMessage.includes('❌')}>
			{saveMessage}
		</div>
	{/if}

	<!-- Sous-onglets -->
	<div class="subtabs">
		<button class="subtab" class:active={activeSubTab === 'setups'} on:click={() => activeSubTab = 'setups'}>
			📊 Setups & Validation
		</button>
		<button class="subtab" class:active={activeSubTab === 'money'} on:click={() => activeSubTab = 'money'}>
			💰 Money Management
		</button>
		<button class="subtab" class:active={activeSubTab === 'position'} on:click={() => activeSubTab = 'position'}>
			🎯 TP/SL & Position
		</button>
	</div>

	<div class="variables-grid">
		<!-- ONGLET SETUPS -->
		{#if activeSubTab === 'setups'}
			<!-- Section Patterns Actifs -->
			<section class="variable-section">
				<h3>🎯 Patterns Actifs</h3>
				<div class="variables-list">
					<div class="variable-item checkbox">
						<div class="var-header">
							<label for="use-breakout">
								<input
									id="use-breakout"
									type="checkbox"
									bind:checked={config.use_breakout}
									on:change={() => logConfigChange('use_breakout', config.use_breakout ? 'Activé' : 'Désactivé')}
								/>
								<span class="var-name">Breakout Pattern</span>
								<span class="var-desc">Activer les signaux de cassure</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('use_breakout')} title="Réinitialiser">⟲</button>
						</div>
					</div>

					<div class="variable-item checkbox">
						<div class="var-header">
							<label for="use-snr">
								<input
									id="use-snr"
									type="checkbox"
									bind:checked={config.use_snr}
									on:change={() => logConfigChange('use_snr', config.use_snr ? 'Activé' : 'Désactivé')}
								/>
								<span class="var-name">SNR Pattern</span>
								<span class="var-desc">Activer les signaux support/résistance</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('use_snr')} title="Réinitialiser">⟲</button>
						</div>
					</div>

					<div class="variable-item checkbox">
						<div class="var-header">
							<label for="use-wick">
								<input
									id="use-wick"
									type="checkbox"
									bind:checked={config.use_wick}
									on:change={() => logConfigChange('use_wick', config.use_wick ? 'Activé' : 'Désactivé')}
								/>
								<span class="var-name">Wick Pattern</span>
								<span class="var-desc">Activer les signaux de rejet (mèches)</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('use_wick')} title="Réinitialiser">⟲</button>
						</div>
					</div>

					<div class="variable-item checkbox">
						<div class="var-header">
							<label for="use-divergence">
								<input
									id="use-divergence"
									type="checkbox"
									bind:checked={config.use_divergence}
									on:change={() => logConfigChange('use_divergence', config.use_divergence ? 'Activé' : 'Désactivé')}
								/>
								<span class="var-name">Divergence Pattern</span>
								<span class="var-desc">Activer les signaux de divergence DI</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('use_divergence')} title="Réinitialiser">⟲</button>
						</div>
					</div>
				</div>
			</section>

			<!-- Section Indicateurs Techniques -->
			<section class="variable-section">
				<h3>📊 Indicateurs Techniques</h3>
				<div class="variables-list">
					<div class="variable-item">
						<div class="var-header">
							<label for="snr-threshold">
								<span class="var-name">SNR Threshold</span>
								<span class="var-desc">Seuil de support/résistance</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('snr_threshold')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="snr-threshold"
								type="range"
								step="0.01"
								min="0"
								max="1"
								bind:value={config.snr_threshold}
								on:change={() => logConfigChange('snr_threshold', config.snr_threshold.toFixed(2))}
							/>
							<span class="slider-value">{Number(config.snr_threshold).toFixed(2)}</span>
						</div>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="breakout-threshold">
								<span class="var-name">Breakout Threshold</span>
								<span class="var-desc">Seuil de cassure</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('breakout_threshold')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="breakout-threshold"
								type="range"
								step="0.01"
								min="0"
								max="1"
								bind:value={config.breakout_threshold}
								on:change={() => logConfigChange('breakout_threshold', config.breakout_threshold.toFixed(2))}
							/>
							<span class="slider-value">{Number(config.breakout_threshold).toFixed(2)}</span>
						</div>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="wick-ratio">
								<span class="var-name">Wick Ratio Max</span>
								<span class="var-desc">Ratio maximum des mèches</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('wick_ratio_max')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="wick-ratio"
								type="range"
								step="0.1"
								min="0"
								max="10"
								bind:value={config.wick_ratio_max}
								on:change={() => logConfigChange('wick_ratio_max', config.wick_ratio_max.toFixed(1))}
							/>
							<span class="slider-value">{Number(config.wick_ratio_max).toFixed(1)}</span>
						</div>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="di-gap">
								<span class="var-name">DI Gap Min</span>
								<span class="var-desc">Gap minimum directional indicator</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('di_gap_min')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="di-gap"
								type="range"
								step="0.5"
								min="0"
								max="20"
								bind:value={config.di_gap_min}
								on:change={() => logConfigChange('di_gap_min', config.di_gap_min.toFixed(1))}
							/>
							<span class="slider-value">{Number(config.di_gap_min).toFixed(1)}</span>
						</div>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="di-gap-adx-threshold">
								<span class="var-name">DI Gap ADX Threshold</span>
								<span class="var-desc">Seuil ADX pour le DI gap</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('di_gap_adx_threshold')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="di-gap-adx-threshold"
								type="range"
								step="1"
								min="0"
								max="100"
								bind:value={config.di_gap_adx_threshold}
								on:change={() => logConfigChange('di_gap_adx_threshold', config.di_gap_adx_threshold.toFixed(0))}
							/>
							<span class="slider-value">{Number(config.di_gap_adx_threshold).toFixed(0)}</span>
						</div>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="trend-timeframe">
								<span class="var-name">Trend Timeframe</span>
								<span class="var-desc">Période pour l'analyse de tendance</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('trend_timeframe')} title="Réinitialiser">⟲</button>
						</div>
						<select
							id="trend-timeframe"
							bind:value={config.trend_timeframe}
							on:change={() => logConfigChange('trend_timeframe', config.trend_timeframe)}
						>
							<option value="5m">5 minutes</option>
							<option value="15m">15 minutes</option>
							<option value="30m">30 minutes</option>
							<option value="1h">1 heure</option>
						</select>
					</div>
				</div>
			</section>

			<!-- Section Optimal ATR Ranges -->
			<section class="variable-section">
				<h3>📉 Optimal ATR Ranges</h3>
				<div class="variables-list">
					<div class="variable-item">
						<div class="var-header">
							<label for="optimal-atr-min-1m">
								<span class="var-name">ATR Min 1m (%)</span>
								<span class="var-desc">ATR minimum pour timeframe 1m</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('optimal_atr_min_1m')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="optimal-atr-min-1m"
								type="range"
								step="0.01"
								min="0.01"
								max="1"
								bind:value={config.optimal_atr_min_1m}
								on:change={() => logConfigChange('optimal_atr_min_1m', config.optimal_atr_min_1m.toFixed(2) + '%')}
							/>
							<span class="slider-value">{Number(config.optimal_atr_min_1m).toFixed(2)}%</span>
						</div>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="optimal-atr-max-1m">
								<span class="var-name">ATR Max 1m (%)</span>
								<span class="var-desc">ATR maximum pour timeframe 1m</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('optimal_atr_max_1m')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="optimal-atr-max-1m"
								type="range"
								step="0.01"
								min="0.1"
								max="5"
								bind:value={config.optimal_atr_max_1m}
								on:change={() => logConfigChange('optimal_atr_max_1m', config.optimal_atr_max_1m.toFixed(2) + '%')}
							/>
							<span class="slider-value">{Number(config.optimal_atr_max_1m).toFixed(2)}%</span>
						</div>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="optimal-atr-min-5m">
								<span class="var-name">ATR Min 5m (%)</span>
								<span class="var-desc">ATR minimum pour timeframe 5m</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('optimal_atr_min_5m')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="optimal-atr-min-5m"
								type="range"
								step="0.01"
								min="0.01"
								max="1"
								bind:value={config.optimal_atr_min_5m}
								on:change={() => logConfigChange('optimal_atr_min_5m', config.optimal_atr_min_5m.toFixed(2) + '%')}
							/>
							<span class="slider-value">{Number(config.optimal_atr_min_5m).toFixed(2)}%</span>
						</div>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="optimal-atr-max-5m">
								<span class="var-name">ATR Max 5m (%)</span>
								<span class="var-desc">ATR maximum pour timeframe 5m</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('optimal_atr_max_5m')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="optimal-atr-max-5m"
								type="range"
								step="0.01"
								min="0.1"
								max="5"
								bind:value={config.optimal_atr_max_5m}
								on:change={() => logConfigChange('optimal_atr_max_5m', config.optimal_atr_max_5m.toFixed(2) + '%')}
							/>
							<span class="slider-value">{Number(config.optimal_atr_max_5m).toFixed(2)}%</span>
						</div>
					</div>
				</div>
			</section>
		{/if}

		<!-- ONGLET MONEY MANAGEMENT -->
		{#if activeSubTab === 'money'}
			<section class="variable-section">
				<h3>💰 Money Management</h3>
				<div class="variables-list">
					<div class="variable-item">
						<div class="var-header">
							<label for="account-size">
								<span class="var-name">Account Size (USDT)</span>
								<span class="var-desc">Taille du compte</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('account_size')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="account-size"
								type="range"
								step="100"
								min="100"
								max="100000"
								bind:value={config.account_size}
								on:change={() => logConfigChange('account_size', `${config.account_size} USDT`)}
							/>
							<span class="slider-value">{Number(config.account_size).toFixed(0)} USDT</span>
						</div>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="risk-per-trade">
								<span class="var-name">Risk per Trade (%)</span>
								<span class="var-desc">Risque par trade</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('risk_per_trade')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="risk-per-trade"
								type="range"
								step="0.1"
								min="0.1"
								max="10"
								bind:value={config.risk_per_trade}
								on:change={() => logConfigChange('risk_per_trade', `${config.risk_per_trade.toFixed(1)}%`)}
							/>
							<span class="slider-value">{Number(config.risk_per_trade).toFixed(1)}%</span>
						</div>
					</div>
				</div>
			</section>
		{/if}

		<!-- ONGLET TP/SL & POSITION -->
		{#if activeSubTab === 'position'}
			<section class="variable-section tp-sl-section">
				<h3>🎯 Take Profit / Stop Loss</h3>
				<p class="section-info">
					⚠️ <strong>Note:</strong> Ce sélecteur sert uniquement à afficher les paramètres d'un mode.
					Pour changer le mode actif du bot, utilisez le sélecteur dans l'onglet <strong>Dashboard</strong>.
				</p>
				<div class="variables-list">
					<div class="variable-item">
						<div class="var-header">
							<label for="tp-sl-mode-view">
								<span class="var-name">Afficher Mode</span>
								<span class="var-desc">Sélectionner le mode à configurer (affichage uniquement)</span>
							</label>
						</div>
						<select
							id="tp-sl-mode-view"
							bind:value={viewMode}
						>
							<option value="FIXE">FIXE - Pourcentages fixes</option>
							<option value="ATR">ATR - Basé sur volatilité</option>
							<option value="ESCALIER">ESCALIER - TP partiel progressif</option>
						</select>
					</div>

					<div class="active-mode-indicator">
						<span class="indicator-label">Mode Actif Bot:</span>
						<span class="indicator-value mode-{config.tp_sl_mode.toLowerCase()}">{config.tp_sl_mode}</span>
					</div>

					<!-- Mode FIXE -->
					{#if viewMode === 'FIXE'}
						<div class="mode-settings">
							<div class="variable-item">
								<div class="var-header">
									<label for="tp-percent">
										<span class="var-name">TP Percent (%)</span>
										<span class="var-desc">Take profit final en %</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('tp_percent')} title="Réinitialiser">⟲</button>
								</div>
								<div class="slider-container">
									<input
										id="tp-percent"
										type="range"
										step="0.05"
										min="0.05"
										max="5"
										bind:value={config.tp_percent}
										on:change={() => logConfigChange('tp_percent', `${config.tp_percent.toFixed(2)}%`)}
									/>
									<span class="slider-value">{Number(config.tp_percent).toFixed(2)}%</span>
								</div>
							</div>

							<div class="variable-item">
								<div class="var-header">
									<label for="sl-percent">
										<span class="var-name">SL Percent (%)</span>
										<span class="var-desc">Stop loss en %</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('sl_percent')} title="Réinitialiser">⟲</button>
								</div>
								<div class="slider-container">
									<input
										id="sl-percent"
										type="range"
										step="0.05"
										min="0.05"
										max="5"
										bind:value={config.sl_percent}
										on:change={() => logConfigChange('sl_percent', `${config.sl_percent.toFixed(2)}%`)}
									/>
									<span class="slider-value">{Number(config.sl_percent).toFixed(2)}%</span>
								</div>
							</div>

							<div class="variable-item">
								<div class="var-header">
									<label for="partial-tp-percent-fixe">
										<span class="var-name">TP Partiel (%)</span>
										<span class="var-desc">% de position clôturée au 1er TP</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('partial_tp_percent')} title="Réinitialiser">⟲</button>
								</div>
								<div class="slider-container">
									<input
										id="partial-tp-percent-fixe"
										type="range"
										step="5"
										min="0"
										max="100"
										bind:value={config.partial_tp_percent}
										on:change={() => logConfigChange('partial_tp_percent', `${config.partial_tp_percent}%`)}
									/>
									<span class="slider-value">{Number(config.partial_tp_percent).toFixed(0)}%</span>
								</div>
							</div>
						</div>
					{/if}

					<!-- Mode ATR -->
					{#if viewMode === 'ATR'}
						<div class="mode-settings">
							<div class="variable-item">
								<div class="var-header">
									<label for="atr-tp">
										<span class="var-name">ATR Mult TP</span>
										<span class="var-desc">Multiplicateur ATR pour TP</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('atr_mult_tp')} title="Réinitialiser">⟲</button>
								</div>
								<div class="slider-container">
									<input
										id="atr-tp"
										type="range"
										step="0.1"
										min="0.5"
										max="5"
										bind:value={config.atr_mult_tp}
										on:change={() => logConfigChange('atr_mult_tp', `${config.atr_mult_tp.toFixed(1)}x`)}
									/>
									<span class="slider-value">{Number(config.atr_mult_tp).toFixed(1)}x ATR</span>
								</div>
							</div>

							<div class="variable-item">
								<div class="var-header">
									<label for="atr-sl">
										<span class="var-name">ATR Mult SL</span>
										<span class="var-desc">Multiplicateur ATR pour SL</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('atr_mult_sl')} title="Réinitialiser">⟲</button>
								</div>
								<div class="slider-container">
									<input
										id="atr-sl"
										type="range"
										step="0.1"
										min="0.5"
										max="3"
										bind:value={config.atr_mult_sl}
										on:change={() => logConfigChange('atr_mult_sl', `${config.atr_mult_sl.toFixed(1)}x`)}
									/>
									<span class="slider-value">{Number(config.atr_mult_sl).toFixed(1)}x ATR</span>
								</div>
							</div>

							<div class="variable-item">
								<div class="var-header">
									<label for="atr-min">
										<span class="var-name">ATR Min (%)</span>
										<span class="var-desc">ATR minimum (limite basse)</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('atr_min')} title="Réinitialiser">⟲</button>
								</div>
								<div class="slider-container">
									<input
										id="atr-min"
										type="range"
										step="0.01"
										min="0.05"
										max="1"
										bind:value={config.atr_min}
										on:change={() => logConfigChange('atr_min', `${config.atr_min.toFixed(2)}%`)}
									/>
									<span class="slider-value">{Number(config.atr_min).toFixed(2)}%</span>
								</div>
							</div>

							<div class="variable-item">
								<div class="var-header">
									<label for="atr-max">
										<span class="var-name">ATR Max (%)</span>
										<span class="var-desc">ATR maximum (limite haute)</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('atr_max')} title="Réinitialiser">⟲</button>
								</div>
								<div class="slider-container">
									<input
										id="atr-max"
										type="range"
										step="0.05"
										min="0.5"
										max="5"
										bind:value={config.atr_max}
										on:change={() => logConfigChange('atr_max', `${config.atr_max.toFixed(2)}%`)}
									/>
									<span class="slider-value">{Number(config.atr_max).toFixed(2)}%</span>
								</div>
							</div>
						</div>
					{/if}

					<!-- Mode ESCALIER -->
					{#if viewMode === 'ESCALIER'}
						<div class="mode-settings">
							<p class="mode-description">
								Mode Escalier : Vendez votre position en 4 étapes pour sécuriser progressivement vos profits.
								À chaque niveau, définissez le % de profit (PnL) et la taille de position à clôturer.
							</p>

							<!-- Niveau 1 -->
							<div class="escalier-level">
								<h4>🎯 Niveau 1</h4>
								<div class="level-inputs">
									<div class="variable-item">
										<div class="var-header">
											<label for="escalier-l1-pnl">
												<span class="var-name">PnL Niveau 1 (%)</span>
												<span class="var-desc">% profit pour déclencher TP1</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level1_pnl')} title="Réinitialiser">⟲</button>
										</div>
										<div class="slider-container">
											<input
												id="escalier-l1-pnl"
												type="range"
												step="0.05"
												min="0.1"
												max="2"
												bind:value={config.escalier_level1_pnl}
												on:change={() => {
													autoAdjustEscalierPnL(1);
													logConfigChange('escalier_level1_pnl', `${config.escalier_level1_pnl.toFixed(2)}%`);
												}}
											/>
											<span class="slider-value">{Number(config.escalier_level1_pnl).toFixed(2)}%</span>
										</div>
									</div>

									<div class="variable-item">
										<div class="var-header">
											<label for="escalier-l1-size">
												<span class="var-name">Taille Niveau 1 (%)</span>
												<span class="var-desc">% de position à clôturer</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level1_size')} title="Réinitialiser">⟲</button>
										</div>
										<div class="slider-container">
											<input
												id="escalier-l1-size"
												type="range"
												step="5"
												min="0"
												max="100"
												bind:value={config.escalier_level1_size}
												on:change={() => {
													autoAdjustEscalierSize(1);
													logConfigChange('escalier_level1_size', `${config.escalier_level1_size}%`);
												}}
											/>
											<span class="slider-value">{Number(config.escalier_level1_size).toFixed(0)}%</span>
										</div>
									</div>
								</div>
							</div>

							<!-- Niveau 2 -->
							<div class="escalier-level">
								<h4>🎯 Niveau 2</h4>
								<div class="level-inputs">
									<div class="variable-item">
										<div class="var-header">
											<label for="escalier-l2-pnl">
												<span class="var-name">PnL Niveau 2 (%)</span>
												<span class="var-desc">% profit pour déclencher TP2</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level2_pnl')} title="Réinitialiser">⟲</button>
										</div>
										<div class="slider-container">
											<input
												id="escalier-l2-pnl"
												type="range"
												step="0.05"
												min="0.1"
												max="2"
												bind:value={config.escalier_level2_pnl}
												on:change={() => {
													autoAdjustEscalierPnL(2);
													logConfigChange('escalier_level2_pnl', `${config.escalier_level2_pnl.toFixed(2)}%`);
												}}
											/>
											<span class="slider-value">{Number(config.escalier_level2_pnl).toFixed(2)}%</span>
										</div>
									</div>

									<div class="variable-item">
										<div class="var-header">
											<label for="escalier-l2-size">
												<span class="var-name">Taille Niveau 2 (%)</span>
												<span class="var-desc">% de position à clôturer</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level2_size')} title="Réinitialiser">⟲</button>
										</div>
										<div class="slider-container">
											<input
												id="escalier-l2-size"
												type="range"
												step="5"
												min="0"
												max="100"
												bind:value={config.escalier_level2_size}
												on:change={() => {
													autoAdjustEscalierSize(2);
													logConfigChange('escalier_level2_size', `${config.escalier_level2_size}%`);
												}}
											/>
											<span class="slider-value">{Number(config.escalier_level2_size).toFixed(0)}%</span>
										</div>
									</div>
								</div>
							</div>

							<!-- Niveau 3 -->
							<div class="escalier-level">
								<h4>🎯 Niveau 3</h4>
								<div class="level-inputs">
									<div class="variable-item">
										<div class="var-header">
											<label for="escalier-l3-pnl">
												<span class="var-name">PnL Niveau 3 (%)</span>
												<span class="var-desc">% profit pour déclencher TP3</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level3_pnl')} title="Réinitialiser">⟲</button>
										</div>
										<div class="slider-container">
											<input
												id="escalier-l3-pnl"
												type="range"
												step="0.05"
												min="0.1"
												max="2"
												bind:value={config.escalier_level3_pnl}
												on:change={() => {
													autoAdjustEscalierPnL(3);
													logConfigChange('escalier_level3_pnl', `${config.escalier_level3_pnl.toFixed(2)}%`);
												}}
											/>
											<span class="slider-value">{Number(config.escalier_level3_pnl).toFixed(2)}%</span>
										</div>
									</div>

									<div class="variable-item">
										<div class="var-header">
											<label for="escalier-l3-size">
												<span class="var-name">Taille Niveau 3 (%)</span>
												<span class="var-desc">% de position à clôturer</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level3_size')} title="Réinitialiser">⟲</button>
										</div>
										<div class="slider-container">
											<input
												id="escalier-l3-size"
												type="range"
												step="5"
												min="0"
												max="100"
												bind:value={config.escalier_level3_size}
												on:change={() => {
													autoAdjustEscalierSize(3);
													logConfigChange('escalier_level3_size', `${config.escalier_level3_size}%`);
												}}
											/>
											<span class="slider-value">{Number(config.escalier_level3_size).toFixed(0)}%</span>
										</div>
									</div>
								</div>
							</div>

							<!-- Niveau 4 -->
							<div class="escalier-level">
								<h4>🎯 Niveau 4</h4>
								<div class="level-inputs">
									<div class="variable-item">
										<div class="var-header">
											<label for="escalier-l4-pnl">
												<span class="var-name">PnL Niveau 4 (%)</span>
												<span class="var-desc">% profit pour déclencher TP4 (final)</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level4_pnl')} title="Réinitialiser">⟲</button>
										</div>
										<div class="slider-container">
											<input
												id="escalier-l4-pnl"
												type="range"
												step="0.05"
												min="0.1"
												max="3"
												bind:value={config.escalier_level4_pnl}
												on:change={() => {
													autoAdjustEscalierPnL(4);
													logConfigChange('escalier_level4_pnl', `${config.escalier_level4_pnl.toFixed(2)}%`);
												}}
											/>
											<span class="slider-value">{Number(config.escalier_level4_pnl).toFixed(2)}%</span>
										</div>
									</div>

									<div class="variable-item">
										<div class="var-header">
											<label for="escalier-l4-size">
												<span class="var-name">Taille Niveau 4 (%)</span>
												<span class="var-desc">% de position à clôturer</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level4_size')} title="Réinitialiser">⟲</button>
										</div>
										<div class="slider-container">
											<input
												id="escalier-l4-size"
												type="range"
												step="5"
												min="0"
												max="100"
												bind:value={config.escalier_level4_size}
												on:change={() => {
													autoAdjustEscalierSize(4);
													logConfigChange('escalier_level4_size', `${config.escalier_level4_size}%`);
												}}
											/>
											<span class="slider-value">{Number(config.escalier_level4_size).toFixed(0)}%</span>
										</div>
									</div>
								</div>
							</div>
						</div>
					{/if}
				</div>
			</section>

			<!-- Section Trailing Stop Adaptatif -->
			<section class="variable-section">
				<h3>🔄 Trailing Stop Adaptatif</h3>
				<p class="section-desc">S'applique à tous les modes TP/SL</p>
				<div class="variables-list">
					<div class="variable-item checkbox">
						<div class="var-header">
							<label for="trailing-enabled">
								<input
									id="trailing-enabled"
									type="checkbox"
									bind:checked={config.trailing_enabled}
									on:change={() => logConfigChange('trailing_enabled', config.trailing_enabled ? 'Activé' : 'Désactivé')}
								/>
								<span class="var-name">Trailing Stop Enabled</span>
								<span class="var-desc">Activer le trailing stop adaptatif</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('trailing_enabled')} title="Réinitialiser">⟲</button>
						</div>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="trailing-trigger">
								<span class="var-name">Trigger PnL (%)</span>
								<span class="var-desc">% profit pour activer le trailing</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('trailing_trigger_pnl')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="trailing-trigger"
								type="range"
								step="0.05"
								min="0.1"
								max="3"
								bind:value={config.trailing_trigger_pnl}
								on:change={() => logConfigChange('trailing_trigger_pnl', `${config.trailing_trigger_pnl.toFixed(2)}%`)}
							/>
							<span class="slider-value">{Number(config.trailing_trigger_pnl).toFixed(2)}%</span>
						</div>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="trailing-atr-mult">
								<span class="var-name">ATR Multiplier</span>
								<span class="var-desc">Distance = ATR × multiplier</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('trailing_atr_multiplier')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="trailing-atr-mult"
								type="range"
								step="0.1"
								min="0.1"
								max="2"
								bind:value={config.trailing_atr_multiplier}
								on:change={() => logConfigChange('trailing_atr_multiplier', `${config.trailing_atr_multiplier.toFixed(1)}x`)}
							/>
							<span class="slider-value">{Number(config.trailing_atr_multiplier).toFixed(1)}x</span>
						</div>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="trailing-min-dist">
								<span class="var-name">Min Distance (%)</span>
								<span class="var-desc">Distance minimum du trailing</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('trailing_min_distance')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="trailing-min-dist"
								type="range"
								step="0.01"
								min="0.05"
								max="0.5"
								bind:value={config.trailing_min_distance}
								on:change={() => logConfigChange('trailing_min_distance', `${config.trailing_min_distance.toFixed(2)}%`)}
							/>
							<span class="slider-value">{Number(config.trailing_min_distance).toFixed(2)}%</span>
						</div>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="trailing-max-dist">
								<span class="var-name">Max Distance (%)</span>
								<span class="var-desc">Distance maximum du trailing</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('trailing_max_distance')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="trailing-max-dist"
								type="range"
								step="0.05"
								min="0.1"
								max="2"
								bind:value={config.trailing_max_distance}
								on:change={() => logConfigChange('trailing_max_distance', `${config.trailing_max_distance.toFixed(2)}%`)}
							/>
							<span class="slider-value">{Number(config.trailing_max_distance).toFixed(2)}%</span>
						</div>
					</div>
				</div>
			</section>
		{/if}

		<!-- ONGLET STRATEGIE -->
	</div>
</div>

<style>
	.variables-panel {
		background: #1e2749;
		border-radius: 12px;
		padding: 24px;
		border: 2px solid #2a3a6b;
	}

	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 24px;
		padding-bottom: 16px;
		border-bottom: 2px solid #2a3a6b;
	}

	.panel-header h2 {
		font-size: 24px;
		color: #00ff88;
		margin: 0;
	}

	.header-actions {
		display: flex;
		gap: 10px;
	}

	.btn-primary,
	.btn-secondary {
		padding: 10px 20px;
		border: none;
		border-radius: 8px;
		font-size: 14px;
		font-weight: bold;
		cursor: pointer;
		transition: all 0.3s;
		text-transform: uppercase;
	}

	.btn-primary {
		background: linear-gradient(135deg, #00ff88 0%, #00cc6a 100%);
		color: #0a0e27;
	}

	.btn-primary:hover:not(:disabled) {
		transform: translateY(-2px);
		box-shadow: 0 4px 15px rgba(0, 255, 136, 0.4);
	}

	.btn-primary:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.btn-secondary {
		background: #2a3a6b;
		color: #fff;
		border: 2px solid #00aaff;
	}

	.btn-secondary:hover {
		background: rgba(0, 170, 255, 0.1);
		transform: translateY(-2px);
	}

	.save-message {
		padding: 12px 16px;
		border-radius: 8px;
		margin-bottom: 20px;
		font-size: 14px;
		font-weight: bold;
		text-align: center;
	}

	.save-message.success {
		background: rgba(0, 255, 136, 0.1);
		color: #00ff88;
		border: 1px solid #00ff88;
	}

	.save-message.error {
		background: rgba(255, 68, 68, 0.1);
		color: #ff4444;
		border: 1px solid #ff4444;
	}

	.subtabs {
		display: flex;
		gap: 8px;
		margin-bottom: 24px;
		flex-wrap: wrap;
	}

	.subtab {
		padding: 10px 16px;
		background: #2a3a6b;
		border: 2px solid transparent;
		border-radius: 8px;
		color: #888;
		font-size: 13px;
		font-weight: bold;
		cursor: pointer;
		transition: all 0.3s;
	}

	.subtab:hover {
		background: rgba(0, 170, 255, 0.1);
		border-color: #00aaff;
		color: #00aaff;
	}

	.subtab.active {
		background: linear-gradient(135deg, #00aaff 0%, #0088cc 100%);
		border-color: #00aaff;
		color: #fff;
		box-shadow: 0 2px 10px rgba(0, 170, 255, 0.3);
	}

	.variables-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
		gap: 24px;
	}

	.variable-section {
		background: #0a0e27;
		border-radius: 10px;
		padding: 20px;
		border: 2px solid #2a3a6b;
	}

	.variable-section.tp-sl-section {
		grid-column: 1 / -1;
	}

	.variable-section h3 {
		font-size: 18px;
		color: #00aaff;
		margin: 0 0 16px 0;
		padding-bottom: 12px;
		border-bottom: 1px solid #2a3a6b;
	}

	.section-desc {
		font-size: 13px;
		color: #888;
		margin: -8px 0 16px 0;
		font-style: italic;
	}

	.variables-list {
		display: flex;
		flex-direction: column;
		gap: 20px;
	}

	.variable-item {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.var-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 12px;
	}

	.var-header label {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 4px;
		color: #fff;
	}

	.variable-item.checkbox .var-header label {
		flex-direction: row;
		align-items: center;
		gap: 10px;
	}

	.var-name {
		font-size: 14px;
		font-weight: bold;
		color: #00ff88;
	}

	.var-desc {
		font-size: 12px;
		color: #888;
		font-style: italic;
	}

	.btn-reset {
		background: rgba(255, 170, 0, 0.1);
		border: 1px solid #ffaa00;
		color: #ffaa00;
		padding: 6px 10px;
		border-radius: 6px;
		cursor: pointer;
		font-size: 16px;
		transition: all 0.2s;
		flex-shrink: 0;
	}

	.btn-reset:hover {
		background: rgba(255, 170, 0, 0.2);
		transform: scale(1.1);
	}

	.slider-container {
		display: flex;
		align-items: center;
		gap: 12px;
		background: #1e2749;
		padding: 12px;
		border-radius: 8px;
		border: 2px solid #2a3a6b;
	}

	.slider-container input[type='range'] {
		flex: 1;
		height: 6px;
		background: #2a3a6b;
		border-radius: 3px;
		outline: none;
		-webkit-appearance: none;
	}

	.slider-container input[type='range']::-webkit-slider-thumb {
		-webkit-appearance: none;
		appearance: none;
		width: 18px;
		height: 18px;
		background: #00ff88;
		cursor: pointer;
		border-radius: 50%;
		box-shadow: 0 0 8px rgba(0, 255, 136, 0.5);
		transition: all 0.2s;
	}

	.slider-container input[type='range']::-webkit-slider-thumb:hover {
		width: 22px;
		height: 22px;
		box-shadow: 0 0 15px rgba(0, 255, 136, 0.8);
	}

	.slider-container input[type='range']::-moz-range-thumb {
		width: 18px;
		height: 18px;
		background: #00ff88;
		cursor: pointer;
		border-radius: 50%;
		border: none;
		box-shadow: 0 0 8px rgba(0, 255, 136, 0.5);
		transition: all 0.2s;
	}

	.slider-container input[type='range']::-moz-range-thumb:hover {
		width: 22px;
		height: 22px;
		box-shadow: 0 0 15px rgba(0, 255, 136, 0.8);
	}

	.slider-value {
		font-family: 'Courier New', monospace;
		font-size: 14px;
		font-weight: bold;
		color: #00ff88;
		min-width: 80px;
		text-align: right;
	}

	.variable-item select {
		background: #1e2749;
		border: 2px solid #2a3a6b;
		color: #fff;
		padding: 12px;
		border-radius: 8px;
		font-family: 'Courier New', monospace;
		font-size: 14px;
		transition: all 0.3s;
		cursor: pointer;
	}

	.variable-item select:hover {
		border-color: #00ff88;
	}

	.variable-item select:focus {
		border-color: #00ff88;
		box-shadow: 0 0 0 3px rgba(0, 255, 136, 0.1);
		outline: none;
	}

	.variable-item input[type='checkbox'] {
		width: 20px;
		height: 20px;
		cursor: pointer;
		accent-color: #00ff88;
	}

	.mode-settings {
		background: rgba(0, 170, 255, 0.05);
		border: 1px solid rgba(0, 170, 255, 0.2);
		border-radius: 8px;
		padding: 16px;
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.mode-description {
		color: #888;
		font-size: 13px;
		line-height: 1.6;
		margin-bottom: 8px;
		padding: 12px;
		background: rgba(0, 170, 255, 0.1);
		border-left: 3px solid #00aaff;
		border-radius: 4px;
	}

	.escalier-level {
		background: rgba(0, 255, 136, 0.05);
		border: 1px solid rgba(0, 255, 136, 0.2);
		border-radius: 6px;
		padding: 12px;
		margin-top: 8px;
	}

	.escalier-level h4 {
		color: #00ff88;
		font-size: 14px;
		margin: 0 0 12px 0;
		padding-bottom: 8px;
		border-bottom: 1px solid rgba(0, 255, 136, 0.3);
	}

	.level-inputs {
		display: flex;
		flex-direction: column;
		gap: 12px;
		margin-top: 8px;
	}

	@media (max-width: 768px) {
		.variables-grid {
			grid-template-columns: 1fr;
		}

		.panel-header {
			flex-direction: column;
			gap: 16px;
			align-items: flex-start;
		}

		.header-actions {
			width: 100%;
		}

		.btn-primary,
		.btn-secondary {
			flex: 1;
		}

		.slider-value {
			min-width: 60px;
			font-size: 12px;
		}

		.subtabs {
			overflow-x: auto;
		}
	}

	/* Section info styling */
	.section-info {
		background: rgba(255, 170, 0, 0.1);
		border-left: 3px solid #ffaa00;
		padding: 12px;
		margin-bottom: 20px;
		font-size: 13px;
		color: #ffaa00;
		border-radius: 4px;
	}

	.section-info strong {
		color: #ffcc00;
	}

	/* Active mode indicator */
	.active-mode-indicator {
		background: rgba(0, 170, 255, 0.1);
		border: 1px solid #00aaff;
		padding: 12px 16px;
		border-radius: 8px;
		display: flex;
		align-items: center;
		gap: 12px;
		margin-bottom: 20px;
	}

	.indicator-label {
		font-weight: bold;
		color: #00aaff;
		font-size: 14px;
	}

	.indicator-value {
		padding: 6px 16px;
		border-radius: 6px;
		font-weight: bold;
		font-size: 14px;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.indicator-value.mode-fixe {
		background: linear-gradient(135deg, #00ff88 0%, #00cc6a 100%);
		color: #0a0e27;
	}

	.indicator-value.mode-atr {
		background: linear-gradient(135deg, #00aaff 0%, #0088cc 100%);
		color: #0a0e27;
	}

	.indicator-value.mode-escalier {
		background: linear-gradient(135deg, #ff8800 0%, #cc6600 100%);
		color: #fff;
	}
</style>
