<script>
	import { settings, updateSetting, resetSettings, exportSettings, importSettings } from '$lib/stores/settings';
	import { onMount } from 'svelte';

	let fileInput;
	let showResetConfirm = false;
	let importError = '';
	let backendConfig = {};

	// ✅ Charger la config depuis le backend au démarrage
	onMount(async () => {
		await loadBackendConfig();
	});

	async function loadBackendConfig() {
		try {
			const res = await fetch('/api/state');
			if (res.ok) {
				const data = await res.json();
				if (data.config) {
					backendConfig = data.config;
					// ✅ Synchroniser les paramètres qui existent dans le backend
					if (data.config.sl_percent !== undefined) {
						updateSetting('stopLossPercent', data.config.sl_percent);
					}
					if (data.config.tp_percent !== undefined) {
						updateSetting('takeProfitPercent', data.config.tp_percent);
					}
					if (data.config.trailing_trigger_pnl !== undefined) {
						updateSetting('trailingStopPercent', data.config.trailing_trigger_pnl);
					}
				}
			}
		} catch (err) {
			console.error('Error loading backend config:', err);
		}
	}

	// ✅ Synchroniser avec le backend lors des changements
	async function syncWithBackend(key, value) {
		updateSetting(key, value);
		
		// ✅ Mapper les clés SettingsPanel vers TRADING_CONFIG
		const configMap = {
			'stopLossPercent': 'sl_percent',
			'takeProfitPercent': 'tp_percent',
			'trailingStopPercent': 'trailing_trigger_pnl'
		};

		const backendKey = configMap[key];
		if (backendKey) {
			try {
				const res = await fetch('/api/config/update', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ [backendKey]: value })
				});

				if (res.ok) {
					console.log(`✅ ${key} synchronisé avec backend: ${backendKey} = ${value}`);
				} else {
					console.error(`❌ Erreur synchronisation ${key}:`, res.status);
				}
			} catch (err) {
				console.error(`❌ Erreur synchronisation ${key}:`, err);
			}
		}
	}

	function handleImport() {
		const file = fileInput.files[0];
		if (!file) return;

		importSettings(file)
			.then(() => {
				importError = '';
				alert('✅ Settings imported successfully!');
				// ✅ Synchroniser les paramètres importés avec le backend
				loadBackendConfig();
			})
			.catch(err => {
				importError = `❌ Error: ${err.message}`;
			});
	}

	function handleReset() {
		if (showResetConfirm) {
			resetSettings();
			showResetConfirm = false;
			alert('✅ Settings reset to defaults!');
			// ✅ Recharger la config backend après reset
			loadBackendConfig();
		} else {
			showResetConfirm = true;
			setTimeout(() => (showResetConfirm = false), 3000);
		}
	}
</script>

<div class="settings-panel">
	<div class="settings-header">
		<h2>⚙️ Settings</h2>
		<div class="header-actions">
			<button class="btn-secondary" on:click={exportSettings}>📥 Export</button>
			<label class="btn-secondary">
				📤 Import
				<input
					type="file"
					accept=".json"
					bind:this={fileInput}
					on:change={handleImport}
					style="display: none"
				/>
			</label>
			<button
				class="btn-danger"
				class:confirm={showResetConfirm}
				on:click={handleReset}
			>
				{showResetConfirm ? '⚠️ Confirm Reset?' : '🔄 Reset'}
			</button>
		</div>
	</div>

	{#if importError}
		<div class="error-message">{importError}</div>
	{/if}

	<!-- Trading Settings -->
	<section class="settings-section">
		<h3>💰 Trading</h3>
		<div class="settings-grid">
			<div class="setting-item">
				<label>
					Max Position Size (USDT)
					<input
						type="number"
						min="10"
						max="10000"
						step="10"
						bind:value={$settings.maxPositionSize}
						on:change={() => updateSetting('maxPositionSize', $settings.maxPositionSize)}
					/>
				</label>
				<span class="hint">Maximum size per position</span>
			</div>

			<div class="setting-item">
				<label>
					Stop Loss (%)
					<input
						type="number"
						min="0.1"
						max="10"
						step="0.1"
						bind:value={$settings.stopLossPercent}
						on:change={() => syncWithBackend('stopLossPercent', $settings.stopLossPercent)}
					/>
				</label>
				<span class="hint">Stop loss percentage (synchronisé avec backend: sl_percent)</span>
			</div>

			<div class="setting-item">
				<label>
					Take Profit (%)
					<input
						type="number"
						min="0.1"
						max="20"
						step="0.1"
						bind:value={$settings.takeProfitPercent}
						on:change={() => syncWithBackend('takeProfitPercent', $settings.takeProfitPercent)}
					/>
				</label>
				<span class="hint">Take profit percentage (synchronisé avec backend: tp_percent)</span>
			</div>

			<div class="setting-item">
				<label>
					Trailing Stop Trigger (%)
					<input
						type="number"
						min="0.1"
						max="5"
						step="0.1"
						bind:value={$settings.trailingStopPercent}
						on:change={() => syncWithBackend('trailingStopPercent', $settings.trailingStopPercent)}
					/>
				</label>
				<span class="hint">Trailing stop trigger PnL (synchronisé avec backend: trailing_trigger_pnl)</span>
			</div>

			<div class="setting-item">
				<label>
					Max Daily Loss (USDT)
					<input
						type="number"
						min="10"
						max="1000"
						step="10"
						bind:value={$settings.maxDailyLoss}
						on:change={() => updateSetting('maxDailyLoss', $settings.maxDailyLoss)}
					/>
				</label>
				<span class="hint">Stop trading if reached</span>
			</div>

			<div class="setting-item">
				<label>
					Max Daily Trades
					<input
						type="number"
						min="1"
						max="100"
						step="1"
						bind:value={$settings.maxDailyTrades}
						on:change={() => updateSetting('maxDailyTrades', $settings.maxDailyTrades)}
					/>
				</label>
				<span class="hint">Maximum trades per day</span>
			</div>
		</div>
	</section>

	<!-- Scanner Settings -->
	<section class="settings-section">
		<h3>🔍 Scanner</h3>
		<div class="settings-grid">
			<div class="setting-item">
				<label>
					Scan Interval (seconds)
					<input
						type="number"
						min="10"
						max="600"
						step="10"
						bind:value={$settings.scanInterval}
						on:change={() => updateSetting('scanInterval', $settings.scanInterval)}
					/>
				</label>
				<span class="hint">Time between scans</span>
			</div>

			<div class="setting-item">
				<label>
					Min Volume (USDT)
					<input
						type="number"
						min="100000"
						max="10000000"
						step="100000"
						bind:value={$settings.minVolume}
						on:change={() => updateSetting('minVolume', $settings.minVolume)}
					/>
				</label>
				<span class="hint">Minimum 24h volume</span>
			</div>

			<div class="setting-item">
				<label>
					Max Spread (%)
					<input
						type="number"
						min="0.1"
						max="2"
						step="0.1"
						bind:value={$settings.maxSpread}
						on:change={() => updateSetting('maxSpread', $settings.maxSpread)}
					/>
				</label>
				<span class="hint">Maximum bid/ask spread</span>
			</div>

			<div class="setting-item">
				<label>
					Top Pairs Count
					<input
						type="number"
						min="5"
						max="50"
						step="5"
						bind:value={$settings.topPairsCount}
						on:change={() => updateSetting('topPairsCount', $settings.topPairsCount)}
					/>
				</label>
				<span class="hint">Number of pairs to show</span>
			</div>
		</div>
	</section>

	<!-- UI Settings -->
	<section class="settings-section">
		<h3>🎨 Interface</h3>
		<div class="settings-toggles">
			<label class="toggle-item">
				<input
					type="checkbox"
					bind:checked={$settings.autoRefresh}
					on:change={() => updateSetting('autoRefresh', $settings.autoRefresh)}
				/>
				<span>Auto Refresh</span>
			</label>

			<label class="toggle-item">
				<input
					type="checkbox"
					bind:checked={$settings.showAdvancedStats}
					on:change={() => updateSetting('showAdvancedStats', $settings.showAdvancedStats)}
				/>
				<span>Show Advanced Stats</span>
			</label>

			<label class="toggle-item">
				<input
					type="checkbox"
					bind:checked={$settings.compactMode}
					on:change={() => updateSetting('compactMode', $settings.compactMode)}
				/>
				<span>Compact Mode</span>
			</label>

			<label class="toggle-item">
				<input
					type="checkbox"
					bind:checked={$settings.soundEnabled}
					on:change={() => updateSetting('soundEnabled', $settings.soundEnabled)}
				/>
				<span>Sound Effects</span>
			</label>

			<label class="toggle-item">
				<input
					type="checkbox"
					bind:checked={$settings.chartAnimations}
					on:change={() => updateSetting('chartAnimations', $settings.chartAnimations)}
				/>
				<span>Chart Animations</span>
			</label>
		</div>

		<div class="settings-grid">
			<div class="setting-item">
				<label>
					Refresh Interval (ms)
					<input
						type="number"
						min="1000"
						max="30000"
						step="1000"
						bind:value={$settings.refreshInterval}
						on:change={() => updateSetting('refreshInterval', $settings.refreshInterval)}
					/>
				</label>
				<span class="hint">UI refresh rate</span>
			</div>

			<div class="setting-item">
				<label>
					Chart Max Trades
					<input
						type="number"
						min="5"
						max="100"
						step="5"
						bind:value={$settings.chartMaxTrades}
						on:change={() => updateSetting('chartMaxTrades', $settings.chartMaxTrades)}
					/>
				</label>
				<span class="hint">Trades to show in charts</span>
			</div>
		</div>
	</section>
</div>

<style>
	.settings-panel {
		background: var(--bg-secondary);
		border-radius: 12px;
		padding: 24px;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
	}

	.settings-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 30px;
		padding-bottom: 16px;
		border-bottom: 2px solid var(--bg-tertiary);
	}

	.settings-header h2 {
		font-size: 24px;
		color: var(--accent-green);
		margin: 0;
	}

	.header-actions {
		display: flex;
		gap: 10px;
	}

	.btn-secondary,
	.btn-danger {
		background: var(--bg-tertiary);
		border: 1px solid var(--accent-blue);
		color: var(--text-primary);
		padding: 8px 16px;
		border-radius: 6px;
		cursor: pointer;
		font-size: 13px;
		transition: all 0.3s ease;
	}

	.btn-secondary:hover {
		background: var(--accent-blue);
		transform: translateY(-2px);
	}

	.btn-danger {
		border-color: var(--accent-red);
	}

	.btn-danger:hover {
		background: var(--accent-red);
		transform: translateY(-2px);
	}

	.btn-danger.confirm {
		background: var(--accent-orange);
		border-color: var(--accent-orange);
		animation: pulse 0.5s ease-in-out infinite;
	}

	@keyframes pulse {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.7; }
	}

	.error-message {
		background: rgba(255, 68, 68, 0.1);
		border: 1px solid var(--accent-red);
		padding: 12px;
		border-radius: 6px;
		color: var(--accent-red);
		margin-bottom: 20px;
	}

	.settings-section {
		margin-bottom: 30px;
	}

	.settings-section h3 {
		font-size: 18px;
		color: var(--accent-blue);
		margin-bottom: 16px;
		padding-bottom: 8px;
		border-bottom: 1px solid var(--bg-tertiary);
	}

	.settings-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
		gap: 20px;
	}

	.setting-item {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.setting-item label {
		color: var(--text-primary);
		font-size: 14px;
		font-weight: 500;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.setting-item input[type='number'] {
		background: var(--bg-primary);
		border: 1px solid var(--bg-tertiary);
		color: var(--text-primary);
		padding: 10px 12px;
		border-radius: 6px;
		font-family: 'Courier New', monospace;
		font-size: 14px;
		transition: all 0.3s ease;
	}

	.setting-item input[type='number']:hover {
		border-color: var(--accent-green);
	}

	.setting-item input[type='number']:focus {
		border-color: var(--accent-green);
		box-shadow: 0 0 0 3px rgba(0, 255, 136, 0.1);
	}

	.hint {
		font-size: 12px;
		color: var(--text-secondary);
		font-style: italic;
	}

	.settings-toggles {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 16px;
		margin-bottom: 20px;
	}

	.toggle-item {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 12px;
		background: var(--bg-primary);
		border-radius: 6px;
		cursor: pointer;
		transition: all 0.3s ease;
	}

	.toggle-item:hover {
		background: var(--bg-tertiary);
	}

	.toggle-item input[type='checkbox'] {
		width: 20px;
		height: 20px;
		cursor: pointer;
		accent-color: var(--accent-green);
	}

	.toggle-item span {
		color: var(--text-primary);
		font-size: 14px;
	}

	@media (max-width: 768px) {
		.settings-header {
			flex-direction: column;
			gap: 16px;
			align-items: flex-start;
		}

		.header-actions {
			flex-wrap: wrap;
		}

		.settings-grid {
			grid-template-columns: 1fr;
		}

		.settings-toggles {
			grid-template-columns: 1fr;
		}
	}
</style>
