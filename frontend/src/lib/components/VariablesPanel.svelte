<script>
	import { onMount } from 'svelte';

	let config = {
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
		volume_multiplier: 0.95,
		min_score_required: 7.5
	};

	let loading = false;
	let saveMessage = '';

	onMount(async () => {
		await loadConfig();
	});

	async function loadConfig() {
		try {
			const res = await fetch('/api/state');
			if (res.ok) {
				const data = await res.json();
				if (data.config) {
					config = { ...config, ...data.config };
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
			config = {
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
				volume_multiplier: 0.95,
				min_score_required: 7.5
			};
		}
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

	<div class="variables-grid">
		<!-- Section Indicateurs -->
		<section class="variable-section">
			<h3>📊 Indicateurs Techniques</h3>
			<div class="variables-list">
				<div class="variable-item">
					<label for="snr-threshold">
						<span class="var-name">SNR Threshold</span>
						<span class="var-desc">Seuil de support/résistance</span>
					</label>
					<input
						id="snr-threshold"
						type="number"
						step="0.01"
						min="0"
						max="1"
						bind:value={config.snr_threshold}
					/>
				</div>

				<div class="variable-item">
					<label for="breakout-threshold">
						<span class="var-name">Breakout Threshold</span>
						<span class="var-desc">Seuil de cassure</span>
					</label>
					<input
						id="breakout-threshold"
						type="number"
						step="0.01"
						min="0"
						max="1"
						bind:value={config.breakout_threshold}
					/>
				</div>

				<div class="variable-item">
					<label for="wick-ratio">
						<span class="var-name">Wick Ratio Max</span>
						<span class="var-desc">Ratio maximum des mèches</span>
					</label>
					<input
						id="wick-ratio"
						type="number"
						step="0.1"
						min="0"
						max="10"
						bind:value={config.wick_ratio_max}
					/>
				</div>

				<div class="variable-item">
					<label for="di-gap">
						<span class="var-name">DI Gap Min</span>
						<span class="var-desc">Gap minimum directional indicator</span>
					</label>
					<input
						id="di-gap"
						type="number"
						step="0.5"
						min="0"
						max="20"
						bind:value={config.di_gap_min}
					/>
				</div>

				<div class="variable-item">
					<label for="trend-timeframe">
						<span class="var-name">Trend Timeframe</span>
						<span class="var-desc">Période pour l'analyse de tendance</span>
					</label>
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
					<label for="account-size">
						<span class="var-name">Account Size (USDT)</span>
						<span class="var-desc">Taille du compte</span>
					</label>
					<input
						id="account-size"
						type="number"
						step="10"
						min="100"
						max="1000000"
						bind:value={config.account_size}
					/>
				</div>

				<div class="variable-item">
					<label for="risk-per-trade">
						<span class="var-name">Risk per Trade (%)</span>
						<span class="var-desc">Risque par trade</span>
					</label>
					<input
						id="risk-per-trade"
						type="number"
						step="0.1"
						min="0.1"
						max="10"
						bind:value={config.risk_per_trade}
					/>
				</div>
			</div>
		</section>

		<!-- Section TP/SL -->
		<section class="variable-section">
			<h3>🎯 Take Profit / Stop Loss</h3>
			<div class="variables-list">
				<div class="variable-item">
					<label for="tp-sl-mode">
						<span class="var-name">TP/SL Mode</span>
						<span class="var-desc">Mode de calcul TP/SL</span>
					</label>
					<select id="tp-sl-mode" bind:value={config.tp_sl_mode}>
						<option value="FIXE">FIXE</option>
						<option value="ATR">ATR</option>
					</select>
				</div>

				<div class="variable-item">
					<label for="tp-percent">
						<span class="var-name">TP Percent (%)</span>
						<span class="var-desc">Take profit en %</span>
					</label>
					<input
						id="tp-percent"
						type="number"
						step="0.05"
						min="0.05"
						max="5"
						bind:value={config.tp_percent}
					/>
				</div>

				<div class="variable-item">
					<label for="sl-percent">
						<span class="var-name">SL Percent (%)</span>
						<span class="var-desc">Stop loss en %</span>
					</label>
					<input
						id="sl-percent"
						type="number"
						step="0.05"
						min="0.05"
						max="5"
						bind:value={config.sl_percent}
					/>
				</div>
			</div>
		</section>

		<!-- Section Stratégie -->
		<section class="variable-section">
			<h3>⚙️ Stratégie</h3>
			<div class="variables-list">
				<div class="variable-item checkbox">
					<label for="use-confluence">
						<input
							id="use-confluence"
							type="checkbox"
							bind:checked={config.use_confluence}
						/>
						<span class="var-name">Use Confluence</span>
						<span class="var-desc">Utiliser la confluence de signaux</span>
					</label>
				</div>

				<div class="variable-item">
					<label for="volume-multiplier">
						<span class="var-name">Volume Multiplier</span>
						<span class="var-desc">Multiplicateur de volume</span>
					</label>
					<input
						id="volume-multiplier"
						type="number"
						step="0.05"
						min="0.5"
						max="2"
						bind:value={config.volume_multiplier}
					/>
				</div>

				<div class="variable-item">
					<label for="min-score">
						<span class="var-name">Min Score Required</span>
						<span class="var-desc">Score minimum pour un trade</span>
					</label>
					<input
						id="min-score"
						type="number"
						step="0.5"
						min="0"
						max="20"
						bind:value={config.min_score_required}
					/>
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
		grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
		gap: 24px;
	}

	.variable-section {
		background: #0a0e27;
		border-radius: 10px;
		padding: 20px;
		border: 2px solid #2a3a6b;
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
		gap: 16px;
	}

	.variable-item {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.variable-item label {
		display: flex;
		flex-direction: column;
		gap: 4px;
		color: #fff;
	}

	.variable-item.checkbox label {
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

	.variable-item.checkbox .var-name {
		margin-left: 0;
	}

	.variable-item input[type='number'],
	.variable-item select {
		background: #1e2749;
		border: 2px solid #2a3a6b;
		color: #fff;
		padding: 10px 12px;
		border-radius: 6px;
		font-family: 'Courier New', monospace;
		font-size: 14px;
		transition: all 0.3s;
	}

	.variable-item input[type='number']:hover,
	.variable-item select:hover {
		border-color: #00ff88;
	}

	.variable-item input[type='number']:focus,
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
	}
</style>
