<script lang="ts">
	import { onMount } from 'svelte';
	import { initWebSocket } from '$lib/utils/websocket';

	// États
	let tradingMode = 'PAPER'; // PAPER | LIVE
	let dryRunMode = true;
	let apiKeyMexc = '';
	let apiSecretMexc = '';
	let apiKeyVisible = false;
	let apiSecretVisible = false;

	// Statistiques live
	let liveStats = {
		mode: 'PAPER',
		live_enabled: false,
		dry_run: true,
		orders_placed: 0,
		orders_filled: 0,
		orders_failed: 0,
		success_rate: 0,
		avg_latency_ms: 0,
		api_healthy: true,
		warnings: []
	};

	// Status de sauvegarde
	let saving = false;
	let saveStatus = '';
	let showApiKeysSection = false;

	// Alertes
	let maxSlippagePct = 0.15;
	let maxLatencyMs = 1000;
	let maxPnlDiscrepancyPct = 20;

	// Emergency
	let emergencyStopConfirm = false;

	onMount(async () => {
		await loadLiveConfig();
		await loadLiveStats();

		// Rafraîchir stats toutes les 5 secondes
		setInterval(loadLiveStats, 5000);
	});

	async function loadLiveConfig() {
		try {
			const ws = initWebSocket();
			const result = await ws.sendCommand('get_live_config');

			if (result && result.success) {
				tradingMode = result.trading_mode || 'PAPER';
				dryRunMode = result.dry_run !== false; // Par défaut true
				maxSlippagePct = result.max_slippage_pct || 0.15;
				maxLatencyMs = result.max_latency_ms || 1000;
				maxPnlDiscrepancyPct = result.max_pnl_discrepancy_pct || 20;
			}
		} catch (err) {
			console.error('Erreur chargement config live:', err);
		}
	}

	async function loadLiveStats() {
		try {
			const response = await fetch('/api/live/stats');
			if (response.ok) {
				liveStats = await response.json();
			}
		} catch (err) {
			console.error('Erreur chargement stats live:', err);
		}
	}

	async function saveLiveConfig() {
		saving = true;
		saveStatus = '';

		try {
			const ws = initWebSocket();
			const result = await ws.sendCommand('update_live_config', {
				trading_mode: tradingMode,
				dry_run: dryRunMode,
				api_key_mexc: apiKeyMexc || undefined,
				api_secret_mexc: apiSecretMexc || undefined,
				max_slippage_pct: maxSlippagePct,
				max_latency_ms: maxLatencyMs,
				max_pnl_discrepancy_pct: maxPnlDiscrepancyPct
			});

			if (result && result.success) {
				saveStatus = '✅ Configuration sauvegardée';
				await loadLiveStats();

				// Effacer le message après 3 secondes
				setTimeout(() => saveStatus = '', 3000);
			} else {
				saveStatus = '❌ Erreur: ' + (result.error || 'Inconnue');
			}
		} catch (err: any) {
			saveStatus = '❌ Erreur: ' + err.message;
		} finally {
			saving = false;
		}
	}

	async function testApiConnection() {
		saving = true;
		saveStatus = 'Test connexion API...';

		try {
			const ws = initWebSocket();
			const result = await ws.sendCommand('test_mexc_connection', {
				api_key: apiKeyMexc,
				api_secret: apiSecretMexc
			});

			if (result && result.success) {
				saveStatus = '✅ Connexion API réussie | Latence: ' + result.latency_ms + 'ms';
			} else {
				saveStatus = '❌ Connexion échouée: ' + (result.error || 'Inconnue');
			}
		} catch (err: any) {
			saveStatus = '❌ Erreur: ' + err.message;
		} finally {
			saving = false;
		}
	}

	async function emergencyStop() {
		if (!emergencyStopConfirm) {
			emergencyStopConfirm = true;
			setTimeout(() => emergencyStopConfirm = false, 5000);
			return;
		}

		saving = true;
		saveStatus = '🛑 ARRÊT D\'URGENCE...';

		try {
			const ws = initWebSocket();
			await ws.sendCommand('emergency_stop');
			saveStatus = '✅ Trading arrêté';
			await loadLiveStats();
		} catch (err: any) {
			saveStatus = '❌ Erreur: ' + err.message;
		} finally {
			saving = false;
			emergencyStopConfirm = false;
		}
	}

	function getModeColor(mode: string, dryRun: boolean): string {
		if (mode === 'PAPER') return '#888';
		if (dryRun) return '#ffaa00';
		return '#ff4444';
	}

	function getModeLabel(mode: string, dryRun: boolean): string {
		if (mode === 'PAPER') return 'PAPER TRADING';
		if (dryRun) return 'DRY-RUN (Simulation)';
		return 'LIVE TRADING (RÉEL)';
	}
</script>

<div class="live-panel">
	<!-- Header avec status -->
	<div class="status-header">
		<div class="status-badge" style="border-color: {getModeColor(liveStats.mode, liveStats.dry_run)}">
			<span class="status-icon">🔴</span>
			<span class="status-text" style="color: {getModeColor(liveStats.mode, liveStats.dry_run)}">
				{getModeLabel(liveStats.mode, liveStats.dry_run)}
			</span>
		</div>

		{#if liveStats.live_enabled}
			<div class="health-indicators">
				<div class="health-item" class:healthy={liveStats.api_healthy}>
					<span class="health-icon">{liveStats.api_healthy ? '✅' : '⚠️'}</span>
					<span>API: {liveStats.avg_latency_ms.toFixed(0)}ms</span>
				</div>
				<div class="health-item healthy">
					<span class="health-icon">📊</span>
					<span>{liveStats.success_rate.toFixed(1)}% succès</span>
				</div>
			</div>
		{/if}
	</div>

	<!-- Configuration Mode -->
	<div class="config-section">
		<h3>⚙️ Mode de Trading</h3>

		<div class="mode-selector">
			<button
				class="mode-button"
				class:active={tradingMode === 'PAPER'}
				on:click={() => tradingMode = 'PAPER'}
			>
				<div class="mode-icon">📝</div>
				<div class="mode-info">
					<div class="mode-title">PAPER TRADING</div>
					<div class="mode-desc">Simulation complète (aucun ordre réel)</div>
				</div>
			</button>

			<button
				class="mode-button"
				class:active={tradingMode === 'LIVE'}
				on:click={() => tradingMode = 'LIVE'}
			>
				<div class="mode-icon">🔴</div>
				<div class="mode-info">
					<div class="mode-title">LIVE TRADING</div>
					<div class="mode-desc">Trading réel avec MEXC API</div>
				</div>
			</button>
		</div>

		{#if tradingMode === 'LIVE'}
			<div class="dry-run-toggle">
				<label class="toggle-label">
					<input type="checkbox" bind:checked={dryRunMode} />
					<span class="toggle-text">
						<strong>Mode DRY-RUN</strong>
						{#if dryRunMode}
							<span class="toggle-hint">✅ Ordres simulés (recommandé pour tests)</span>
						{:else}
							<span class="toggle-hint warning">⚠️ ORDRES RÉELS - Argent en jeu !</span>
						{/if}
					</span>
				</label>
			</div>
		{/if}
	</div>

	<!-- API Keys Section -->
	{#if tradingMode === 'LIVE'}
		<div class="config-section">
			<h3>🔑 API Keys MEXC</h3>

			<button
				class="toggle-section-btn"
				on:click={() => showApiKeysSection = !showApiKeysSection}
			>
				{showApiKeysSection ? '▼' : '▶'} {showApiKeysSection ? 'Masquer' : 'Afficher'} API Keys
			</button>

			{#if showApiKeysSection}
				<div class="api-keys-section">
					<div class="input-group">
						<label>API Key</label>
						<div class="password-input">
							<input
								type={apiKeyVisible ? 'text' : 'password'}
								bind:value={apiKeyMexc}
								placeholder="Votre API Key MEXC"
							/>
							<button
								class="toggle-visibility"
								on:click={() => apiKeyVisible = !apiKeyVisible}
							>
								{apiKeyVisible ? '👁️' : '🙈'}
							</button>
						</div>
					</div>

					<div class="input-group">
						<label>API Secret</label>
						<div class="password-input">
							<input
								type={apiSecretVisible ? 'text' : 'password'}
								bind:value={apiSecretMexc}
								placeholder="Votre API Secret MEXC"
							/>
							<button
								class="toggle-visibility"
								on:click={() => apiSecretVisible = !apiSecretVisible}
							>
								{apiSecretVisible ? '👁️' : '🙈'}
							</button>
						</div>
					</div>

					<div class="api-warning">
						⚠️ <strong>Permissions requises:</strong> Spot Trading - Read, Spot Trading - Trade<br/>
						❌ <strong>Désactiver:</strong> Withdrawal, Transfer, Futures
					</div>

					<button
						class="test-btn"
						on:click={testApiConnection}
						disabled={saving || !apiKeyMexc || !apiSecretMexc}
					>
						🧪 Tester Connexion API
					</button>
				</div>
			{/if}
		</div}
	{/if}

	<!-- Alertes et Limites -->
	<div class="config-section">
		<h3>🚨 Alertes et Limites</h3>

		<div class="input-group">
			<label>Slippage Max (%)
				<span class="hint">Alerter si slippage > ce seuil</span>
			</label>
			<input type="number" bind:value={maxSlippagePct} step="0.01" min="0" max="1" />
		</div>

		<div class="input-group">
			<label>Latence Max (ms)
				<span class="hint">Alerter si latence API > ce seuil</span>
			</label>
			<input type="number" bind:value={maxLatencyMs} step="100" min="100" max="5000" />
		</div>

		<div class="input-group">
			<label>Écart PnL Max (%)
				<span class="hint">Alerter si écart théorique/réel > ce seuil</span>
			</label>
			<input type="number" bind:value={maxPnlDiscrepancyPct} step="5" min="5" max="100" />
		</div>
	</div>

	<!-- Statistiques Live -->
	{#if liveStats.live_enabled}
		<div class="config-section">
			<h3>📊 Statistiques Live</h3>

			<div class="stats-grid">
				<div class="stat-card">
					<div class="stat-value">{liveStats.orders_placed}</div>
					<div class="stat-label">Ordres Placés</div>
				</div>
				<div class="stat-card">
					<div class="stat-value">{liveStats.orders_filled}</div>
					<div class="stat-label">Ordres Remplis</div>
				</div>
				<div class="stat-card">
					<div class="stat-value">{liveStats.orders_failed}</div>
					<div class="stat-label">Ordres Échoués</div>
				</div>
				<div class="stat-card">
					<div class="stat-value">{liveStats.success_rate.toFixed(1)}%</div>
					<div class="stat-label">Taux Succès</div>
				</div>
				<div class="stat-card">
					<div class="stat-value">{liveStats.avg_latency_ms.toFixed(0)}ms</div>
					<div class="stat-label">Latence Moyenne</div>
				</div>
			</div>

			{#if liveStats.warnings.length > 0}
				<div class="warnings-list">
					<h4>⚠️ Avertissements</h4>
					{#each liveStats.warnings as warning}
						<div class="warning-item">{warning}</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}

	<!-- Actions -->
	<div class="actions-section">
		<button
			class="save-btn"
			on:click={saveLiveConfig}
			disabled={saving}
		>
			{saving ? '⏳ Sauvegarde...' : '💾 Sauvegarder Configuration'}
		</button>

		{#if tradingMode === 'LIVE' && !dryRunMode}
			<button
				class="emergency-btn"
				class:confirm={emergencyStopConfirm}
				on:click={emergencyStop}
			>
				{emergencyStopConfirm ? '⚠️ CONFIRMER ARRÊT ?' : '🛑 ARRÊT D\'URGENCE'}
			</button>
		{/if}

		{#if saveStatus}
			<div class="save-status" class:error={saveStatus.includes('❌')}>
				{saveStatus}
			</div>
		{/if}
	</div>

	<!-- Guide et Documentation -->
	<div class="config-section docs-section">
		<h3>📚 Documentation</h3>

		<div class="doc-links">
			<a href="/SESSIONS_VS_DRYRUN_VS_LIVE.md" target="_blank" class="doc-link">
				📖 Différence Paper / Dry-Run / Live
			</a>
			<a href="/MIGRATION_GUIDE_LIVE_TRADING.md" target="_blank" class="doc-link">
				🚀 Guide Migration vers Live
			</a>
			<a href="/ARCHITECTURE_HYBRID_LIVE.md" target="_blank" class="doc-link">
				🏗️ Architecture Hybride
			</a>
			<a href="/INTEGRATION_LIVE_ORDER_MANAGER.md" target="_blank" class="doc-link">
				🔌 Guide d'Intégration
			</a>
		</div>

		<div class="safety-checklist">
			<h4>✅ Checklist Sécurité (Live Trading)</h4>
			<ul>
				<li>✓ Tests DRY-RUN réussis (1-2 semaines)</li>
				<li>✓ API Keys avec permissions LIMITÉES</li>
				<li>✓ IP Whitelist activée sur MEXC</li>
				<li>✓ 2FA activé sur compte</li>
				<li>✓ Capital test limité ($100-200)</li>
				<li>✓ Paires liquides uniquement (BTC/ETH/SOL)</li>
				<li>✓ Dashboard monitoring actif</li>
				<li>✓ Alertes Telegram configurées</li>
			</ul>
		</div>
	</div>
</div>

<style>
	.live-panel {
		padding: 20px;
		max-width: 1200px;
		margin: 0 auto;
	}

	.status-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 30px;
		padding: 20px;
		background: rgba(0, 0, 0, 0.3);
		border-radius: 10px;
		border: 2px solid rgba(255, 255, 255, 0.1);
	}

	.status-badge {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 12px 24px;
		background: rgba(0, 0, 0, 0.5);
		border-radius: 25px;
		border: 2px solid;
	}

	.status-icon {
		font-size: 20px;
		animation: pulse 2s infinite;
	}

	@keyframes pulse {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.5; }
	}

	.status-text {
		font-weight: bold;
		font-size: 16px;
		text-transform: uppercase;
		letter-spacing: 1px;
	}

	.health-indicators {
		display: flex;
		gap: 15px;
	}

	.health-item {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 8px 16px;
		background: rgba(255, 68, 68, 0.1);
		border-radius: 8px;
		font-size: 13px;
	}

	.health-item.healthy {
		background: rgba(0, 255, 136, 0.1);
		color: #00ff88;
	}

	.config-section {
		background: #1e2749;
		border-radius: 10px;
		padding: 20px;
		margin-bottom: 20px;
		border: 2px solid #2a3a6b;
	}

	.config-section h3 {
		margin: 0 0 20px 0;
		color: #00ff88;
		font-size: 18px;
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.mode-selector {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
		gap: 15px;
		margin-bottom: 20px;
	}

	.mode-button {
		display: flex;
		align-items: center;
		gap: 15px;
		padding: 20px;
		background: rgba(0, 0, 0, 0.3);
		border: 2px solid #2a3a6b;
		border-radius: 10px;
		cursor: pointer;
		transition: all 0.3s;
		color: #888;
	}

	.mode-button:hover {
		border-color: #00ff88;
		background: rgba(0, 255, 136, 0.05);
	}

	.mode-button.active {
		border-color: #00ff88;
		background: rgba(0, 255, 136, 0.1);
		color: #00ff88;
	}

	.mode-icon {
		font-size: 32px;
	}

	.mode-info {
		flex: 1;
		text-align: left;
	}

	.mode-title {
		font-weight: bold;
		font-size: 14px;
		margin-bottom: 4px;
	}

	.mode-desc {
		font-size: 12px;
		opacity: 0.7;
	}

	.dry-run-toggle {
		padding: 15px;
		background: rgba(255, 170, 0, 0.1);
		border-radius: 8px;
		border-left: 4px solid #ffaa00;
	}

	.toggle-label {
		display: flex;
		align-items: center;
		gap: 12px;
		cursor: pointer;
	}

	.toggle-label input[type="checkbox"] {
		width: 20px;
		height: 20px;
		cursor: pointer;
	}

	.toggle-text {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.toggle-hint {
		font-size: 12px;
		opacity: 0.8;
	}

	.toggle-hint.warning {
		color: #ff4444;
		font-weight: bold;
	}

	.toggle-section-btn {
		padding: 10px 15px;
		background: rgba(0, 0, 0, 0.3);
		border: 1px solid #2a3a6b;
		border-radius: 5px;
		color: #00ff88;
		cursor: pointer;
		margin-bottom: 15px;
		transition: all 0.3s;
	}

	.toggle-section-btn:hover {
		background: rgba(0, 255, 136, 0.1);
	}

	.api-keys-section {
		padding: 15px;
		background: rgba(0, 0, 0, 0.2);
		border-radius: 8px;
	}

	.input-group {
		margin-bottom: 15px;
	}

	.input-group label {
		display: block;
		margin-bottom: 8px;
		color: #00ff88;
		font-size: 13px;
		font-weight: bold;
	}

	.hint {
		color: #888;
		font-size: 11px;
		font-weight: normal;
		margin-left: 8px;
	}

	.input-group input {
		width: 100%;
		padding: 10px;
		background: rgba(0, 0, 0, 0.5);
		border: 1px solid #2a3a6b;
		border-radius: 5px;
		color: #fff;
		font-family: 'Courier New', monospace;
	}

	.password-input {
		display: flex;
		gap: 5px;
	}

	.password-input input {
		flex: 1;
	}

	.toggle-visibility {
		padding: 10px 15px;
		background: rgba(0, 0, 0, 0.5);
		border: 1px solid #2a3a6b;
		border-radius: 5px;
		cursor: pointer;
		transition: all 0.3s;
	}

	.toggle-visibility:hover {
		background: rgba(0, 255, 136, 0.1);
	}

	.api-warning {
		padding: 12px;
		background: rgba(255, 170, 0, 0.1);
		border-left: 4px solid #ffaa00;
		border-radius: 5px;
		font-size: 12px;
		line-height: 1.6;
		margin: 15px 0;
	}

	.test-btn {
		width: 100%;
		padding: 12px;
		background: linear-gradient(135deg, #00ff88, #00cc6a);
		border: none;
		border-radius: 8px;
		color: #000;
		font-weight: bold;
		cursor: pointer;
		transition: all 0.3s;
	}

	.test-btn:hover:not(:disabled) {
		transform: translateY(-2px);
		box-shadow: 0 5px 15px rgba(0, 255, 136, 0.4);
	}

	.test-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.stats-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 15px;
		margin-bottom: 20px;
	}

	.stat-card {
		background: rgba(0, 0, 0, 0.3);
		padding: 15px;
		border-radius: 8px;
		text-align: center;
		border: 1px solid #2a3a6b;
	}

	.stat-value {
		font-size: 24px;
		font-weight: bold;
		color: #00ff88;
		margin-bottom: 5px;
	}

	.stat-label {
		font-size: 12px;
		color: #888;
		text-transform: uppercase;
	}

	.warnings-list {
		padding: 15px;
		background: rgba(255, 68, 68, 0.1);
		border-left: 4px solid #ff4444;
		border-radius: 5px;
	}

	.warnings-list h4 {
		margin: 0 0 10px 0;
		color: #ff4444;
		font-size: 14px;
	}

	.warning-item {
		padding: 8px;
		background: rgba(0, 0, 0, 0.3);
		border-radius: 5px;
		margin-bottom: 5px;
		font-size: 12px;
	}

	.actions-section {
		display: flex;
		flex-direction: column;
		gap: 15px;
	}

	.save-btn {
		padding: 15px;
		background: linear-gradient(135deg, #00ff88, #00cc6a);
		border: none;
		border-radius: 10px;
		color: #000;
		font-weight: bold;
		font-size: 16px;
		cursor: pointer;
		transition: all 0.3s;
	}

	.save-btn:hover:not(:disabled) {
		transform: translateY(-2px);
		box-shadow: 0 5px 15px rgba(0, 255, 136, 0.4);
	}

	.save-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.emergency-btn {
		padding: 15px;
		background: linear-gradient(135deg, #ff4444, #cc0000);
		border: none;
		border-radius: 10px;
		color: #fff;
		font-weight: bold;
		font-size: 16px;
		cursor: pointer;
		transition: all 0.3s;
	}

	.emergency-btn:hover {
		transform: translateY(-2px);
		box-shadow: 0 5px 15px rgba(255, 68, 68, 0.4);
	}

	.emergency-btn.confirm {
		animation: blink 0.5s infinite;
	}

	@keyframes blink {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.5; }
	}

	.save-status {
		padding: 12px;
		background: rgba(0, 255, 136, 0.1);
		border-left: 4px solid #00ff88;
		border-radius: 5px;
		text-align: center;
		font-weight: bold;
	}

	.save-status.error {
		background: rgba(255, 68, 68, 0.1);
		border-left-color: #ff4444;
		color: #ff4444;
	}

	.docs-section {
		background: rgba(0, 102, 204, 0.1);
		border-color: #0066cc;
	}

	.doc-links {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 10px;
		margin-bottom: 20px;
	}

	.doc-link {
		display: block;
		padding: 12px;
		background: rgba(0, 0, 0, 0.3);
		border: 1px solid #0066cc;
		border-radius: 8px;
		color: #00aaff;
		text-decoration: none;
		font-size: 13px;
		transition: all 0.3s;
		text-align: center;
	}

	.doc-link:hover {
		background: rgba(0, 102, 204, 0.2);
		transform: translateY(-2px);
	}

	.safety-checklist {
		padding: 15px;
		background: rgba(0, 0, 0, 0.3);
		border-radius: 8px;
	}

	.safety-checklist h4 {
		margin: 0 0 15px 0;
		color: #00ff88;
		font-size: 14px;
	}

	.safety-checklist ul {
		list-style: none;
		padding: 0;
		margin: 0;
	}

	.safety-checklist li {
		padding: 6px 0;
		font-size: 13px;
		color: #888;
	}

	@media (max-width: 768px) {
		.status-header {
			flex-direction: column;
			gap: 15px;
		}

		.mode-selector {
			grid-template-columns: 1fr;
		}

		.stats-grid {
			grid-template-columns: repeat(2, 1fr);
		}

		.doc-links {
			grid-template-columns: 1fr;
		}
	}
</style>
