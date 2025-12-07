<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { initWebSocket, sendCommandViaWS } from '$lib/utils/websocket';

	// États principaux
	let tradingMode = 'PAPER';
	let dryRunMode = true;
	let apiKeyMexc = '';
	let apiSecretMexc = '';
	let apiKeyVisible = false;
	let apiSecretVisible = false;
	let defaultLeverage = 10;

	// États temps réel (WebSocket)
	let wsConnected = false;
	let balance = 0;
	let lastUpdate = new Date();

	// Stats
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
		warnings: [] as string[]
	};

	// UI States
	let saving = false;
	let saveStatus = '';
	let showApiKeys = false;
	let activeTab: 'config' | 'risk' | 'health' = 'config';
	let emergencyConfirm = false;

	// 🔥 Health Dashboard data
	let healthData: any = null;

	// Risk Settings (slippage géré dans VariablesPanel via config.max_slippage_pct)
	let maxLatencyMs = 1000;

	// Note: Trailing Stop est configuré dans l'onglet Variables (trailing_enabled, etc.)

	// WebSocket & Intervals
	let ws: any = null;
	let refreshInterval: ReturnType<typeof setInterval> | null = null;

	onMount(async () => {
		ws = initWebSocket();
		wsConnected = ws?.connected || false;

		// Écouter les événements WS
		ws?.on('connect', () => { wsConnected = true; refreshData(); });
		ws?.on('disconnect', () => { wsConnected = false; });

		await loadConfig();
		await refreshData();

		// Refresh stats toutes les 30s en mode LIVE
		refreshInterval = setInterval(() => {
			if (tradingMode === 'LIVE') {
				refreshData();
			}
		}, 30000);
	});

	onDestroy(() => {
		if (refreshInterval) clearInterval(refreshInterval);
	});

	// 🔥 Indicateurs visuels pour API keys configurées
	let apiKeyConfigured = false;
	let apiSecretConfigured = false;

	async function loadConfig() {
		try {
			// 1. Charger config live (API keys, mode, etc.)
			const liveRes = await fetch('/api/live/config');
			if (liveRes.ok) {
				const data = await liveRes.json();
				tradingMode = data.trading_mode || 'PAPER';
				dryRunMode = data.dry_run !== false;
				// 🔥 FIX: Indiquer si les API keys sont configurées (masquées côté backend)
				apiKeyConfigured = data.api_key_mexc && data.api_key_mexc !== '' && data.api_key_mexc !== '***';
				apiSecretConfigured = data.api_secret_mexc && data.api_secret_mexc === '***';
			}

			// 2. 🔥 Charger valeurs persistées depuis TRADING_CONFIG
			const configRes = await fetch('/api/config/complete');
			if (configRes.ok) {
				const { trading_config } = await configRes.json();
				if (trading_config) {
					defaultLeverage = trading_config.default_leverage ?? 10;
					maxLatencyMs = trading_config.max_latency_ms ?? 1000;
					// 🔥 FIX: Utiliser uniquement config.max_slippage_pct (pas de doublon)
				}
			}
		} catch (e) {
			console.error('Erreur chargement config:', e);
		}
	}

	async function refreshData() {
		try {
			// Récupérer stats, balance et health
			const [statsRes, balRes, healthRes] = await Promise.all([
				fetch('/api/live/stats'),
				ws?.sendCommand('get_balance', {}),
				fetch('/api/live/health')  // 🔥 NOUVEAU: Health dashboard
			]);

			if (statsRes.ok) liveStats = await statsRes.json();
			if (balRes?.success) balance = balRes.balance || 0;
			if (healthRes.ok) {
				const data = await healthRes.json();
				if (data.success) healthData = data.health;
			}

			lastUpdate = new Date();
		} catch (e) {
			console.error('Erreur refresh:', e);
		}
	}

	async function saveConfig() {
		saving = true;
		saveStatus = '';
		try {
			// 1. Sauvegarder config live (API keys, mode, etc.)
			const result = await ws?.sendCommand('update_live_config', {
				trading_mode: tradingMode,
				dry_run: dryRunMode,
				api_key_mexc: apiKeyMexc || undefined,
				api_secret_mexc: apiSecretMexc || undefined,
				max_latency_ms: maxLatencyMs,
				default_leverage: defaultLeverage
			});

			// 2. 🔥 Persister dans config_overrides.json via update_config
			// Note: max_slippage_pct est géré uniquement dans VariablesPanel
			await sendCommandViaWS('update_config', {
				default_leverage: defaultLeverage,
				max_latency_ms: maxLatencyMs
			});

			// 🔥 FIX: Marquer les clés comme configurées après sauvegarde
			if (apiKeyMexc) apiKeyConfigured = true;
			if (apiSecretMexc) apiSecretConfigured = true;

			if (result?.success) {
				saveStatus = '✅ Configuration sauvegardée et persistée';
				setTimeout(() => saveStatus = '', 3000);
				await refreshData();
			} else {
				saveStatus = 'Erreur: ' + (result?.error || 'Inconnue');
			}
		} catch (e: any) {
			saveStatus = 'Erreur: ' + e.message;
		} finally {
			saving = false;
		}
	}

	async function testConnection() {
		saving = true;
		saveStatus = 'Test connexion...';
		try {
			// 🔥 FIX: Si aucune clé saisie, utiliser les clés du backend (déjà configurées)
			const result = await ws?.sendCommand('test_mexc_connection', {
				api_key: apiKeyMexc || undefined,  // undefined = utiliser clé backend
				api_secret: apiSecretMexc || undefined  // undefined = utiliser clé backend
			});

			if (result?.success) {
				saveStatus = `✅ Connexion OK | Balance: ${result.balance_usdt?.toFixed(2)} USDT | ${result.latency_ms?.toFixed(0)}ms`;
				balance = result.balance_usdt || 0;
			} else {
				saveStatus = '❌ Échec: ' + (result?.error || 'Inconnue');
			}
		} catch (e: any) {
			saveStatus = '❌ Erreur: ' + e.message;
		} finally {
			saving = false;
		}
	}

	async function emergencyStop() {
		if (!emergencyConfirm) {
			emergencyConfirm = true;
			setTimeout(() => emergencyConfirm = false, 5000);
			return;
		}

		saving = true;
		try {
			const result = await ws?.sendCommand('emergency_stop', {});
			if (result?.success) {
				saveStatus = `Arrêt d'urgence | ${result.closed_positions || 0} positions fermées`;
				await refreshData();
			}
		} catch (e: any) {
			saveStatus = 'Erreur: ' + e.message;
		} finally {
			saving = false;
			emergencyConfirm = false;
		}
	}

	// Note: Trailing Stop est géré via les variables (onglet Variables)
	// trailing_enabled, trailing_trigger_pnl, etc.

	function getModeColor(): string {
		if (liveStats.mode === 'PAPER') return '#6b7280';
		if (liveStats.dry_run) return '#f59e0b';
		return '#ef4444';
	}

	function getModeLabel(): string {
		if (liveStats.mode === 'PAPER') return 'PAPER';
		if (liveStats.dry_run) return 'DRY-RUN';
		return 'LIVE';
	}
</script>

<div class="live-panel">
	<!-- Header compact -->
	<header class="header">
		<div class="header-left">
			<div class="mode-badge" style="background: {getModeColor()}20; border-color: {getModeColor()}">
				<span class="mode-dot" style="background: {getModeColor()}"></span>
				<span style="color: {getModeColor()}">{getModeLabel()}</span>
			</div>
			<div class="ws-status" class:connected={wsConnected}>
				{wsConnected ? '● WS' : '○ WS'}
			</div>
			{#if balance > 0}
				<div class="balance-display">
					<span class="balance-value">{balance.toFixed(2)}</span>
					<span class="balance-currency">USDT</span>
				</div>
			{/if}
		</div>
		<div class="header-right">
			{#if liveStats.live_enabled}
				<div class="metric">{liveStats.avg_latency_ms.toFixed(0)}ms</div>
				<div class="metric">{liveStats.success_rate.toFixed(0)}%</div>
			{/if}
			<span class="last-update">MAJ: {lastUpdate.toLocaleTimeString()}</span>
		</div>
	</header>

	<!-- Tabs Navigation -->
	<nav class="tabs">
		<button class="tab" class:active={activeTab === 'config'} on:click={() => activeTab = 'config'}>
			⚙️ Configuration
		</button>
		<button class="tab" class:active={activeTab === 'risk'} on:click={() => activeTab = 'risk'}>
			🛡️ Risk & Stats
		</button>
		<button class="tab" class:active={activeTab === 'health'} on:click={() => activeTab = 'health'}>
			🏥 Health Dashboard
		</button>
	</nav>

	<!-- Tab: Configuration -->
	{#if activeTab === 'config'}
		<section class="section">
			<h3>Mode de Trading</h3>
			<div class="mode-selector">
				<button class="mode-btn" class:active={tradingMode === 'PAPER'} on:click={() => tradingMode = 'PAPER'}>
					<span class="mode-icon">📝</span>
					<div>
						<div class="mode-title">PAPER</div>
						<div class="mode-desc">Simulation</div>
					</div>
				</button>
				<button class="mode-btn" class:active={tradingMode === 'LIVE'} on:click={() => tradingMode = 'LIVE'}>
					<span class="mode-icon">🔴</span>
					<div>
						<div class="mode-title">LIVE</div>
						<div class="mode-desc">MEXC Futures</div>
					</div>
				</button>
			</div>

			{#if tradingMode === 'LIVE'}
				<div class="dry-run-toggle">
					<label>
						<input type="checkbox" bind:checked={dryRunMode} />
						<span>DRY-RUN {dryRunMode ? '(simulé)' : ''}</span>
					</label>
					{#if !dryRunMode}
						<span class="warning-text">⚠️ ORDRES RÉELS</span>
					{/if}
				</div>

				<div class="leverage-control">
					<label>Levier par défaut</label>
					<div class="leverage-slider">
						<input type="range" min="1" max="50" bind:value={defaultLeverage} />
						<span class="leverage-value">{defaultLeverage}x</span>
					</div>
				</div>

				<button class="toggle-btn" on:click={() => showApiKeys = !showApiKeys}>
					{showApiKeys ? '▼' : '▶'} API Keys MEXC
				</button>

				{#if showApiKeys}
					<div class="api-section">
						<div class="input-row">
							{#if apiKeyVisible}
							<input type="text" bind:value={apiKeyMexc} placeholder={apiKeyConfigured ? '••••••••' : 'API Key'} />
						{:else}
							<input type="password" bind:value={apiKeyMexc} placeholder={apiKeyConfigured ? '••••••••' : 'API Key'} />
						{/if}
						{#if apiKeyConfigured && !apiKeyMexc}
							<span class="key-status configured">✓ Configurée</span>
						{/if}
							<button class="icon-btn" on:click={() => apiKeyVisible = !apiKeyVisible}>
								{apiKeyVisible ? '👁️' : '🙈'}
							</button>
						</div>
						<div class="input-row">
							{#if apiSecretVisible}
							<input type="text" bind:value={apiSecretMexc} placeholder={apiSecretConfigured ? '••••••••' : 'API Secret'} />
						{:else}
							<input type="password" bind:value={apiSecretMexc} placeholder={apiSecretConfigured ? '••••••••' : 'API Secret'} />
						{/if}
						{#if apiSecretConfigured && !apiSecretMexc}
							<span class="key-status configured">✓ Configurée</span>
						{/if}
							<button class="icon-btn" on:click={() => apiSecretVisible = !apiSecretVisible}>
								{apiSecretVisible ? '👁️' : '🙈'}
							</button>
						</div>
						<div class="api-note">
							Permissions: Futures Trading Read/Trade | Pas de Withdrawal
						</div>
						<button 
						class="test-btn" 
						on:click={testConnection} 
						disabled={saving || ((!apiKeyMexc || !apiSecretMexc) && (!apiKeyConfigured || !apiSecretConfigured))}
					>
						🧪 Tester Connexion
					</button>
					</div>
				{/if}
			{/if}

			<div class="actions">
				<button class="primary-btn" on:click={saveConfig} disabled={saving}>
					{saving ? '⏳' : '💾'} Sauvegarder
				</button>
				{#if tradingMode === 'LIVE' && !dryRunMode}
					<button class="danger-btn" class:confirm={emergencyConfirm} on:click={emergencyStop}>
						{emergencyConfirm ? '⚠️ CONFIRMER ?' : '🛑 STOP'}
					</button>
				{/if}
			</div>

			{#if saveStatus}
				<div class="status-msg" class:error={saveStatus.includes('Erreur')}>{saveStatus}</div>
			{/if}
		</section>
	{/if}

	<!-- Tab: Risk Management -->
	{#if activeTab === 'risk'}
		<section class="section">
			<h3>Paramètres de Risque</h3>
			
			<div class="risk-grid">
				<div class="risk-item">
					<label>Latence Max (ms)</label>
					<input type="number" bind:value={maxLatencyMs} step="100" min="100" max="5000" />
				</div>
			</div>
			<p class="info-note">💡 Slippage Max configuré dans l'onglet Variables (config.max_slippage_pct)</p>

			{#if liveStats.live_enabled}
				<div class="stats-mini">
					<div class="stat-mini">
						<span class="stat-num">{liveStats.orders_placed}</span>
						<span class="stat-lbl">Ordres</span>
					</div>
					<div class="stat-mini">
						<span class="stat-num">{liveStats.orders_filled}</span>
						<span class="stat-lbl">Remplis</span>
					</div>
					<div class="stat-mini">
						<span class="stat-num">{liveStats.orders_failed}</span>
						<span class="stat-lbl">Échoués</span>
					</div>
					<div class="stat-mini">
						<span class="stat-num">{liveStats.success_rate.toFixed(0)}%</span>
						<span class="stat-lbl">Succès</span>
					</div>
				</div>
			{/if}

			{#if liveStats.warnings && liveStats.warnings.length > 0}
				<div class="warnings">
					{#each liveStats.warnings as warning}
						<div class="warning-item">⚠️ {warning}</div>
					{/each}
				</div>
			{/if}
		</section>
	{/if}

	<!-- Tab: Health Dashboard -->
	{#if activeTab === 'health'}
		<section class="section">
			<div class="section-header">
				<h3>🏥 Health Dashboard</h3>
				<button class="refresh-btn" on:click={refreshData}>🔄</button>
			</div>

			{#if !healthData}
				<div class="empty-state">
					<span class="empty-icon">⏳</span>
					<p>Chargement des données de santé...</p>
				</div>
			{:else}
				<!-- System Overview -->
				<div class="health-overview">
					<div class="health-card">
						<div class="health-header">
							<span class="health-icon">🖥️</span>
							<span class="health-title">Système</span>
						</div>
						<div class="health-meta">
							<span class="meta-label">Mode:</span>
							<span class="meta-value {healthData.mode}">{healthData.mode.toUpperCase()}</span>
						</div>
						<div class="health-meta">
							<span class="meta-label">Dry Run:</span>
							<span class="meta-value">{healthData.dry_run ? 'Oui' : 'Non'}</span>
						</div>
					</div>

					<!-- Circuit Breaker -->
					{#if healthData.circuit_breaker?.enabled}
						<div class="health-card circuit-breaker {healthData.circuit_breaker.state}">
							<div class="health-header">
								<span class="health-icon">🔴</span>
								<span class="health-title">Circuit Breaker</span>
								<span class="cb-state-badge {healthData.circuit_breaker.state}">
									{healthData.circuit_breaker.state.toUpperCase()}
								</span>
							</div>
							<div class="health-stats">
								<div class="stat-item">
									<span class="stat-label">Échecs:</span>
									<span class="stat-value">{healthData.circuit_breaker.failure_count}/{healthData.circuit_breaker.threshold}</span>
								</div>
								{#if healthData.circuit_breaker.state === 'half_open'}
									<div class="stat-item">
										<span class="stat-label">Succès (test):</span>
										<span class="stat-value success">{healthData.circuit_breaker.success_count}/2</span>
									</div>
								{/if}
							</div>
						</div>
					{/if}

					<!-- Token Monitor -->
					{#if healthData.token_monitor?.enabled}
						<div class="health-card token-monitor">
							<div class="health-header">
								<span class="health-icon">🔑</span>
								<span class="health-title">Token Monitor</span>
								<span class="token-status {healthData.token_monitor.is_valid ? 'valid' : 'invalid'}">
									{healthData.token_monitor.is_valid ? '✓ Valide' : '✗ Expiré'}
								</span>
							</div>
							<div class="health-meta">
								<span class="meta-label">Check Interval:</span>
								<span class="meta-value">{healthData.token_monitor.check_interval_sec}s</span>
							</div>
							{#if healthData.token_monitor.last_check_time > 0}
								<div class="health-meta">
									<span class="meta-label">Dernière vérif:</span>
									<span class="meta-value">{new Date(healthData.token_monitor.last_check_time * 1000).toLocaleTimeString()}</span>
								</div>
							{/if}
						</div>
					{/if}

					<!-- Rate Limiter -->
					{#if healthData.rate_limiter?.enabled}
						<div class="health-card rate-limiter">
							<div class="health-header">
								<span class="health-icon">⏱️</span>
								<span class="health-title">Rate Limiter</span>
							</div>
							<div class="rate-gauge">
								<div class="gauge-bar">
									<div
										class="gauge-fill"
										style="width: {(healthData.rate_limiter.current_rate_per_sec / healthData.rate_limiter.max_rate) * 100}%"
									></div>
								</div>
								<span class="gauge-label">
									{healthData.rate_limiter.current_rate_per_sec.toFixed(1)} req/s
								</span>
							</div>
							<div class="health-stats">
								<div class="stat-item">
									<span class="stat-label">429 consécutifs:</span>
									<span class="stat-value warn">{healthData.rate_limiter.consecutive_429s}</span>
								</div>
								<div class="stat-item">
									<span class="stat-label">200 consécutifs:</span>
									<span class="stat-value success">{healthData.rate_limiter.consecutive_200s}</span>
								</div>
							</div>
						</div>
					{/if}
				</div>

				<!-- System Stats -->
				<div class="system-stats-grid">
					<div class="sys-stat">
						<span class="sys-label">Ordres Placés</span>
						<span class="sys-value">{healthData.system.orders_placed}</span>
					</div>
					<div class="sys-stat">
						<span class="sys-label">Ordres Remplis</span>
						<span class="sys-value success">{healthData.system.orders_filled}</span>
					</div>
					<div class="sys-stat">
						<span class="sys-label">Échecs</span>
						<span class="sys-value warn">{healthData.system.orders_failed}</span>
					</div>
					<div class="sys-stat">
						<span class="sys-label">Success Rate</span>
						<span class="sys-value">{healthData.system.success_rate_pct.toFixed(1)}%</span>
					</div>
					<div class="sys-stat">
						<span class="sys-label">Latence Moy</span>
						<span class="sys-value">{healthData.system.avg_latency_ms.toFixed(0)}ms</span>
					</div>
					<div class="sys-stat">
						<span class="sys-label">PnL Total</span>
						<span class="sys-value {healthData.system.total_pnl_usdt >= 0 ? 'success' : 'error'}">
							{healthData.system.total_pnl_usdt >= 0 ? '+' : ''}{healthData.system.total_pnl_usdt.toFixed(2)} USDT
						</span>
					</div>
				</div>

				<div class="health-footer">
					<span class="footer-label">Dernière mise à jour:</span>
					<span class="footer-value">{new Date(healthData.timestamp).toLocaleString()}</span>
				</div>
			{/if}
		</section>
	{/if}
</div>

<style>
	.live-panel { padding: 16px; max-width: 900px; margin: 0 auto; }

	/* Header */
	.header { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background: #1a1f2e; border-radius: 8px; margin-bottom: 16px; }
	.header-left { display: flex; align-items: center; gap: 12px; }
	.header-right { display: flex; align-items: center; gap: 12px; font-size: 12px; color: #6b7280; }
	.mode-badge { display: flex; align-items: center; gap: 8px; padding: 6px 12px; border-radius: 20px; border: 1px solid; font-weight: 600; font-size: 12px; }
	.mode-dot { width: 8px; height: 8px; border-radius: 50%; animation: pulse 2s infinite; }
	@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
	.ws-status { font-size: 11px; color: #6b7280; }
	.ws-status.connected { color: #10b981; }
	.balance-display { display: flex; align-items: baseline; gap: 4px; padding: 4px 10px; background: rgba(16, 185, 129, 0.1); border-radius: 6px; }
	.balance-value { font-size: 14px; font-weight: 600; color: #10b981; }
	.balance-currency { font-size: 10px; color: #6b7280; }
	.metric { padding: 4px 8px; background: rgba(99, 102, 241, 0.1); border-radius: 4px; font-size: 11px; color: #a5b4fc; }
	.last-update { font-size: 10px; }

	/* Tabs */
	.tabs { display: flex; gap: 4px; margin-bottom: 16px; background: #1a1f2e; padding: 4px; border-radius: 8px; }
	.tab { flex: 1; padding: 10px 16px; background: transparent; border: none; border-radius: 6px; color: #6b7280; font-size: 13px; cursor: pointer; transition: all 0.2s; }
	.tab:hover { background: rgba(255,255,255,0.05); color: #fff; }
	.tab.active { background: #2563eb; color: #fff; }
	.badge { display: inline-flex; align-items: center; justify-content: center; min-width: 18px; height: 18px; padding: 0 5px; background: #ef4444; border-radius: 9px; font-size: 10px; margin-left: 6px; }

	/* Section */
	.section { background: #1a1f2e; border-radius: 10px; padding: 20px; }
	.section h3 { margin: 0 0 16px 0; color: #fff; font-size: 15px; font-weight: 600; }
	.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
	.section-header h3 { margin: 0; }
	.refresh-btn { padding: 6px 10px; background: rgba(99, 102, 241, 0.1); border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
	.refresh-btn:hover { background: rgba(99, 102, 241, 0.2); }

	/* Mode Selector */
	.mode-selector { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px; }
	.mode-btn { display: flex; align-items: center; gap: 12px; padding: 16px; background: rgba(0,0,0,0.2); border: 2px solid transparent; border-radius: 10px; cursor: pointer; transition: all 0.2s; color: #6b7280; }
	.mode-btn:hover { border-color: #3b82f6; }
	.mode-btn.active { border-color: #10b981; background: rgba(16, 185, 129, 0.1); color: #10b981; }
	.mode-btn .mode-icon { font-size: 24px; }
	.mode-btn .mode-title { font-weight: 600; font-size: 14px; }
	.mode-btn .mode-desc { font-size: 11px; opacity: 0.7; }

	/* Dry Run Toggle */
	.dry-run-toggle { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; background: rgba(245, 158, 11, 0.1); border-radius: 8px; margin-bottom: 16px; }
	.dry-run-toggle label { display: flex; align-items: center; gap: 10px; cursor: pointer; font-size: 13px; }
	.dry-run-toggle input { width: 18px; height: 18px; accent-color: #10b981; }
	.warning-text { color: #ef4444; font-size: 12px; font-weight: 600; }

	/* Leverage */
	.leverage-control { margin-bottom: 16px; }
	.leverage-control label { display: block; font-size: 12px; color: #9ca3af; margin-bottom: 8px; }
	.leverage-slider { display: flex; align-items: center; gap: 12px; }
	.leverage-slider input[type="range"] { flex: 1; height: 6px; -webkit-appearance: none; background: #374151; border-radius: 3px; }
	.leverage-slider input[type="range"]::-webkit-slider-thumb { -webkit-appearance: none; width: 18px; height: 18px; background: #3b82f6; border-radius: 50%; cursor: pointer; }
	.leverage-value { min-width: 40px; padding: 4px 8px; background: #374151; border-radius: 4px; font-size: 13px; font-weight: 600; color: #10b981; text-align: center; }

	/* Toggle Button */
	.toggle-btn { width: 100%; padding: 10px; background: rgba(0,0,0,0.2); border: 1px solid #374151; border-radius: 6px; color: #9ca3af; font-size: 13px; cursor: pointer; text-align: left; margin-bottom: 12px; }
	.toggle-btn:hover { background: rgba(0,0,0,0.3); color: #fff; }

	/* API Section */
	.api-section { padding: 16px; background: rgba(0,0,0,0.2); border-radius: 8px; }
	.input-row { display: flex; gap: 8px; margin-bottom: 10px; }
	.input-row input { flex: 1; padding: 10px 12px; background: #0f1219; border: 1px solid #374151; border-radius: 6px; color: #fff; font-size: 13px; font-family: monospace; }
	.input-row input:focus { outline: none; border-color: #3b82f6; }
	.icon-btn { padding: 10px; background: #374151; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
	.api-note { font-size: 11px; color: #6b7280; margin: 12px 0; padding: 8px; background: rgba(245, 158, 11, 0.1); border-radius: 4px; }
	.test-btn { width: 100%; padding: 10px; background: linear-gradient(135deg, #10b981, #059669); border: none; border-radius: 6px; color: #000; font-weight: 600; font-size: 13px; cursor: pointer; }
	.test-btn:disabled { opacity: 0.5; cursor: not-allowed; }
	.key-status { font-size: 11px; padding: 4px 8px; border-radius: 4px; white-space: nowrap; }
	.key-status.configured { background: rgba(16, 185, 129, 0.2); color: #10b981; }
	.info-note { font-size: 12px; color: #9ca3af; padding: 8px 12px; background: rgba(99, 102, 241, 0.1); border-radius: 6px; margin-top: 8px; }

	/* Actions */
	.actions { display: flex; gap: 10px; margin-top: 20px; }
	.primary-btn { flex: 1; padding: 12px; background: linear-gradient(135deg, #3b82f6, #2563eb); border: none; border-radius: 8px; color: #fff; font-weight: 600; font-size: 14px; cursor: pointer; }
	.primary-btn:disabled { opacity: 0.5; }
	.danger-btn { padding: 12px 20px; background: linear-gradient(135deg, #ef4444, #dc2626); border: none; border-radius: 8px; color: #fff; font-weight: 600; font-size: 14px; cursor: pointer; }
	.danger-btn.confirm { animation: blink 0.4s infinite; }
	@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
	.secondary-btn { padding: 10px 16px; background: #374151; border: none; border-radius: 6px; color: #fff; cursor: pointer; }
	.small-btn { padding: 6px 12px; background: rgba(99, 102, 241, 0.2); border: none; border-radius: 4px; color: #a5b4fc; font-size: 11px; cursor: pointer; }
	.small-btn:hover { background: rgba(99, 102, 241, 0.3); }

	/* Status Message */
	.status-msg { margin-top: 12px; padding: 10px; background: rgba(16, 185, 129, 0.1); border-left: 3px solid #10b981; border-radius: 4px; font-size: 13px; color: #10b981; }
	.status-msg.error { background: rgba(239, 68, 68, 0.1); border-color: #ef4444; color: #ef4444; }

	/* Empty State */
	.empty-state { text-align: center; padding: 40px 20px; color: #6b7280; }
	.empty-icon { font-size: 48px; display: block; margin-bottom: 12px; }
	.empty-state p { margin: 0; font-size: 14px; }

	/* Positions */
	.positions-list { display: flex; flex-direction: column; gap: 12px; }
	.position-card { background: rgba(0,0,0,0.2); border-radius: 10px; padding: 16px; border-left: 4px solid #6b7280; }
	.position-card.long { border-color: #10b981; }
	.position-card.short { border-color: #ef4444; }
	.pos-header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
	.pos-symbol { font-weight: 600; font-size: 15px; color: #fff; }
	.pos-side { padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 600; text-transform: uppercase; background: rgba(239, 68, 68, 0.2); color: #ef4444; }
	.pos-side.long { background: rgba(16, 185, 129, 0.2); color: #10b981; }
	.pos-leverage { font-size: 11px; color: #9ca3af; margin-left: auto; }
	.pos-details { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
	.pos-row { display: flex; justify-content: space-between; font-size: 12px; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
	.pos-row span:first-child { color: #6b7280; }
	.pos-row span:last-child { color: #fff; font-weight: 500; }
	.pos-row.pnl.positive span:last-child { color: #10b981; }
	.pos-row.pnl.negative span:last-child { color: #ef4444; }
	.pos-row.liq span:last-child { color: #f59e0b; }
	.pos-actions { margin-top: 12px; display: flex; gap: 8px; }

	/* Trailing Config */
	.trailing-config { margin-top: 16px; padding: 16px; background: rgba(99, 102, 241, 0.1); border-radius: 8px; }
	.trailing-config h4 { margin: 0 0 12px 0; font-size: 14px; color: #a5b4fc; }
	.trailing-row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
	.trailing-row label { font-size: 12px; color: #9ca3af; }
	.trailing-row input { width: 80px; padding: 8px; background: #0f1219; border: 1px solid #374151; border-radius: 4px; color: #fff; text-align: center; }
	.trailing-actions { display: flex; gap: 8px; }

	/* Risk Grid */
	.risk-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }
	.risk-item label { display: block; font-size: 12px; color: #9ca3af; margin-bottom: 6px; }
	.risk-item input { width: 100%; padding: 10px; background: #0f1219; border: 1px solid #374151; border-radius: 6px; color: #fff; }

	/* Stats Mini */
	.stats-mini { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 20px; }
	.stat-mini { text-align: center; padding: 12px; background: rgba(0,0,0,0.2); border-radius: 8px; }
	.stat-num { display: block; font-size: 20px; font-weight: 600; color: #10b981; }
	.stat-lbl { font-size: 10px; color: #6b7280; text-transform: uppercase; }

	/* Warnings */
	.warnings { margin-top: 16px; }
	.warnings .warning-item { padding: 10px; background: rgba(239, 68, 68, 0.1); border-radius: 6px; font-size: 12px; color: #fca5a5; margin-bottom: 8px; }

	/* 🔥 Health Dashboard Styles */
	.health-overview { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 20px; }
	.health-card { background: rgba(0,0,0,0.3); border-radius: 10px; padding: 16px; border: 1px solid #374151; }
	.health-card.circuit-breaker.open { border-color: #ef4444; background: rgba(239, 68, 68, 0.05); }
	.health-card.circuit-breaker.half_open { border-color: #f59e0b; background: rgba(245, 158, 11, 0.05); }
	.health-card.circuit-breaker.closed { border-color: #10b981; background: rgba(16, 185, 129, 0.05); }
	.health-header { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.05); }
	.health-icon { font-size: 20px; }
	.health-title { font-weight: 600; font-size: 14px; color: #fff; }
	.cb-state-badge { margin-left: auto; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 600; }
	.cb-state-badge.closed { background: rgba(16, 185, 129, 0.2); color: #10b981; }
	.cb-state-badge.open { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
	.cb-state-badge.half_open { background: rgba(245, 158, 11, 0.2); color: #f59e0b; }
	.token-status { margin-left: auto; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 600; }
	.token-status.valid { background: rgba(16, 185, 129, 0.2); color: #10b981; }
	.token-status.invalid { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
	.health-meta { display: flex; justify-content: space-between; padding: 6px 0; font-size: 12px; }
	.meta-label { color: #9ca3af; }
	.meta-value { color: #fff; font-weight: 500; }
	.meta-value.bypass { color: #a5b4fc; }
	.meta-value.ccxt { color: #fbbf24; }
	.health-stats { display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }
	.stat-item { display: flex; justify-content: space-between; font-size: 12px; }
	.stat-label { color: #9ca3af; }
	.stat-value { color: #fff; font-weight: 500; }
	.stat-value.success { color: #10b981; }
	.stat-value.warn { color: #f59e0b; }
	.rate-gauge { margin: 12px 0; }
	.gauge-bar { height: 8px; background: #1f2937; border-radius: 4px; overflow: hidden; }
	.gauge-fill { height: 100%; background: linear-gradient(90deg, #10b981, #3b82f6); transition: width 0.3s ease; }
	.gauge-label { display: block; text-align: center; margin-top: 6px; font-size: 13px; font-weight: 600; color: #10b981; }
	.system-stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 16px; }
	.sys-stat { background: rgba(0,0,0,0.3); border-radius: 8px; padding: 12px; text-align: center; border: 1px solid #374151; }
	.sys-label { display: block; font-size: 11px; color: #9ca3af; margin-bottom: 6px; text-transform: uppercase; }
	.sys-value { display: block; font-size: 16px; font-weight: 600; color: #fff; }
	.sys-value.success { color: #10b981; }
	.sys-value.warn { color: #f59e0b; }
	.sys-value.error { color: #ef4444; }
	.health-footer { margin-top: 16px; padding-top: 12px; border-top: 1px solid #374151; display: flex; justify-content: space-between; font-size: 11px; color: #6b7280; }
	.footer-label { color: #9ca3af; }
	.footer-value { color: #fff; }

	/* Responsive */
	@media (max-width: 640px) {
		.mode-selector { grid-template-columns: 1fr; }
		.pos-details { grid-template-columns: 1fr; }
		.stats-mini { grid-template-columns: repeat(2, 1fr); }
		.risk-grid { grid-template-columns: 1fr; }
		.health-overview { grid-template-columns: 1fr; }
		.system-stats-grid { grid-template-columns: repeat(2, 1fr); }
	}
</style>
