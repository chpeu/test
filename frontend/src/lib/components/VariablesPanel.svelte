<script>
	import { onMount } from 'svelte';

	const DEFAULTS = {
		snr_threshold: 0.25,
		breakout_threshold: 0.35,
		wick_ratio_max: 2.8,
		di_gap_min: 4.0,
		trend_timeframe: '15m',
		account_size: 1000.0,
		risk_per_trade: 2.0,
		use_confluence: false,
		tp_sl_mode: 'FIXE',
		tp_percent: 0.25,
		sl_percent: 0.25,
		atr_multiplier_tp: 2.0,
		atr_multiplier_sl: 1.5,
		trailing_activation: 0.5,
		trailing_callback: 0.3,
		partial_tp_percent: 50,
		break_even_trigger: 0.5,
		volume_multiplier: 0.95,
		min_score_required: 7.5,
		// Patterns
		use_breakout: true,
		use_snr: true,
		use_wick: true,
		use_divergence: true
	};

	let config = { ...DEFAULTS };
	let loading = false;
	let saveMessage = '';
	let activeSubTab = 'setups'; // setups, money, position, strategy

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
		}
	}

	function resetVariable(key) {
		config[key] = DEFAULTS[key];
	}
</script>

<div class="variables-panel">
	<div class="panel-header">
		<h2>🎯 Variables de Trading</h2>
		<div class="header-actions">
			<button class="btn-secondary" on:click={resetDefaults}>🔄 Reset</button>
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
			📊 Setups
		</button>
		<button class="subtab" class:active={activeSubTab === 'money'} on:click={() => activeSubTab = 'money'}>
			💰 Money Management
		</button>
		<button class="subtab" class:active={activeSubTab === 'position'} on:click={() => activeSubTab = 'position'}>
			🎯 TP/SL & Position
		</button>
		<button class="subtab" class:active={activeSubTab === 'strategy'} on:click={() => activeSubTab = 'strategy'}>
			⚙️ Stratégie
		</button>
	</div>

	<div class="variables-grid">
		<!-- Section Indicateurs -->
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
						/>
						<span class="slider-value">{Number(config.di_gap_min).toFixed(1)}</span>
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
					<select id="trend-timeframe" bind:value={config.trend_timeframe}>
						<option value="5m">5 minutes</option>
						<option value="15m">15 minutes</option>
						<option value="30m">30 minutes</option>
						<option value="1h">1 heure</option>
					</select>
				</div>
			</div>
		</section>

		<!-- Section Money Management -->
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
						/>
						<span class="slider-value">{Number(config.risk_per_trade).toFixed(1)}%</span>
					</div>
				</div>
			</div>
		</section>

		<!-- Section TP/SL -->
		<section class="variable-section tp-sl-section">
			<h3>🎯 Take Profit / Stop Loss</h3>
			<div class="variables-list">
				<div class="variable-item">
					<div class="var-header">
						<label for="tp-sl-mode">
							<span class="var-name">TP/SL Mode</span>
							<span class="var-desc">Mode de calcul TP/SL</span>
						</label>
						<button class="btn-reset" on:click={() => resetVariable('tp_sl_mode')} title="Réinitialiser">⟲</button>
					</div>
					<select id="tp-sl-mode" bind:value={config.tp_sl_mode}>
						<option value="FIXE">FIXE - Pourcentages fixes</option>
						<option value="ATR">ATR - Basé sur volatilité</option>
						<option value="ESCALIER">ESCALIER - TP partiel progressif</option>
						<option value="TRAILING">TRAILING - Stop suiveur</option>
					</select>
				</div>

				<!-- Mode FIXE -->
				{#if config.tp_sl_mode === 'FIXE'}
					<div class="mode-settings">
						<div class="variable-item">
							<div class="var-header">
								<label for="tp-percent">
									<span class="var-name">TP Percent (%)</span>
									<span class="var-desc">Take profit en %</span>
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
								/>
								<span class="slider-value">{Number(config.sl_percent).toFixed(2)}%</span>
							</div>
						</div>
					</div>
				{/if}

				<!-- Mode ATR -->
				{#if config.tp_sl_mode === 'ATR'}
					<div class="mode-settings">
						<div class="variable-item">
							<div class="var-header">
								<label for="atr-tp">
									<span class="var-name">ATR Multiplier TP</span>
									<span class="var-desc">Multiplicateur ATR pour TP</span>
								</label>
								<button class="btn-reset" on:click={() => resetVariable('atr_multiplier_tp')} title="Réinitialiser">⟲</button>
							</div>
							<div class="slider-container">
								<input
									id="atr-tp"
									type="range"
									step="0.1"
									min="0.5"
									max="5"
									bind:value={config.atr_multiplier_tp}
								/>
								<span class="slider-value">{Number(config.atr_multiplier_tp).toFixed(1)}x ATR</span>
							</div>
						</div>

						<div class="variable-item">
							<div class="var-header">
								<label for="atr-sl">
									<span class="var-name">ATR Multiplier SL</span>
									<span class="var-desc">Multiplicateur ATR pour SL</span>
								</label>
								<button class="btn-reset" on:click={() => resetVariable('atr_multiplier_sl')} title="Réinitialiser">⟲</button>
							</div>
							<div class="slider-container">
								<input
									id="atr-sl"
									type="range"
									step="0.1"
									min="0.5"
									max="3"
									bind:value={config.atr_multiplier_sl}
								/>
								<span class="slider-value">{Number(config.atr_multiplier_sl).toFixed(1)}x ATR</span>
							</div>
						</div>
					</div>
				{/if}

				<!-- Mode ESCALIER -->
				{#if config.tp_sl_mode === 'ESCALIER'}
					<div class="mode-settings">
						<div class="variable-item">
							<div class="var-header">
								<label for="partial-tp">
									<span class="var-name">Partial TP (%)</span>
									<span class="var-desc">% de position vendue au 1er TP</span>
								</label>
								<button class="btn-reset" on:click={() => resetVariable('partial_tp_percent')} title="Réinitialiser">⟲</button>
							</div>
							<div class="slider-container">
								<input
									id="partial-tp"
									type="range"
									step="5"
									min="25"
									max="75"
									bind:value={config.partial_tp_percent}
								/>
								<span class="slider-value">{Number(config.partial_tp_percent).toFixed(0)}%</span>
							</div>
						</div>

						<div class="variable-item">
							<div class="var-header">
								<label for="break-even">
									<span class="var-name">Break Even Trigger (%)</span>
									<span class="var-desc">% profit pour passer SL à break-even</span>
								</label>
								<button class="btn-reset" on:click={() => resetVariable('break_even_trigger')} title="Réinitialiser">⟲</button>
							</div>
							<div class="slider-container">
								<input
									id="break-even"
									type="range"
									step="0.1"
									min="0.2"
									max="2"
									bind:value={config.break_even_trigger}
								/>
								<span class="slider-value">{Number(config.break_even_trigger).toFixed(1)}%</span>
							</div>
						</div>
					</div>
				{/if}

				<!-- Mode TRAILING -->
				{#if config.tp_sl_mode === 'TRAILING'}
					<div class="mode-settings">
						<div class="variable-item">
							<div class="var-header">
								<label for="trailing-activation">
									<span class="var-name">Activation (%)</span>
									<span class="var-desc">% profit pour activer trailing stop</span>
								</label>
								<button class="btn-reset" on:click={() => resetVariable('trailing_activation')} title="Réinitialiser">⟲</button>
							</div>
							<div class="slider-container">
								<input
									id="trailing-activation"
									type="range"
									step="0.1"
									min="0.2"
									max="3"
									bind:value={config.trailing_activation}
								/>
								<span class="slider-value">{Number(config.trailing_activation).toFixed(1)}%</span>
							</div>
						</div>

						<div class="variable-item">
							<div class="var-header">
								<label for="trailing-callback">
									<span class="var-name">Callback (%)</span>
									<span class="var-desc">% de retour avant trigger</span>
								</label>
								<button class="btn-reset" on:click={() => resetVariable('trailing_callback')} title="Réinitialiser">⟲</button>
							</div>
							<div class="slider-container">
								<input
									id="trailing-callback"
									type="range"
									step="0.05"
									min="0.1"
									max="1"
									bind:value={config.trailing_callback}
								/>
								<span class="slider-value">{Number(config.trailing_callback).toFixed(2)}%</span>
							</div>
						</div>
					</div>
				{/if}
			</div>
		</section>

		<!-- Section Stratégie -->
		<section class="variable-section">
			<h3>⚙️ Stratégie</h3>
			<div class="variables-list">
				<div class="variable-item checkbox">
					<div class="var-header">
						<label for="use-confluence">
							<input
								id="use-confluence"
								type="checkbox"
								bind:checked={config.use_confluence}
							/>
							<span class="var-name">Use Confluence</span>
							<span class="var-desc">Utiliser la confluence de signaux</span>
						</label>
						<button class="btn-reset" on:click={() => resetVariable('use_confluence')} title="Réinitialiser">⟲</button>
					</div>
				</div>

				<div class="variable-item">
					<div class="var-header">
						<label for="volume-multiplier">
							<span class="var-name">Volume Multiplier</span>
							<span class="var-desc">Multiplicateur de volume</span>
						</label>
						<button class="btn-reset" on:click={() => resetVariable('volume_multiplier')} title="Réinitialiser">⟲</button>
					</div>
					<div class="slider-container">
						<input
							id="volume-multiplier"
							type="range"
							step="0.05"
							min="0.5"
							max="2"
							bind:value={config.volume_multiplier}
						/>
						<span class="slider-value">{Number(config.volume_multiplier).toFixed(2)}</span>
					</div>
				</div>

				<div class="variable-item">
					<div class="var-header">
						<label for="min-score">
							<span class="var-name">Min Score Required</span>
							<span class="var-desc">Score minimum pour un trade</span>
						</label>
						<button class="btn-reset" on:click={() => resetVariable('min_score_required')} title="Réinitialiser">⟲</button>
					</div>
					<div class="slider-container">
						<input
							id="min-score"
							type="range"
							step="0.5"
							min="0"
							max="20"
							bind:value={config.min_score_required}
						/>
						<span class="slider-value">{Number(config.min_score_required).toFixed(1)}</span>
					</div>
				</div>
			</div>
		</section>
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
	}
</style>
