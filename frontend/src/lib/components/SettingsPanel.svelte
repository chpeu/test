<script lang="ts">
	import { settings, updateSetting, resetSettings, exportSettings, importSettings } from '$lib/stores/settings';

	let fileInput;
	let showResetConfirm = false;
	let importError = '';

	// 🔥 FIX: Plus besoin de charger la config backend, on garde uniquement les paramètres frontend

	function handleImport() {
		const file = fileInput.files[0];
		if (!file) return;

		importSettings(file)
			.then(() => {
				importError = '';
				alert('✅ Settings imported successfully!');
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
	}
</style>
