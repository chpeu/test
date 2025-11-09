<script lang="ts">
	import { onMount } from 'svelte';
	import { initWebSocket } from '$lib/utils/websocket';
	type BidirectionalWebSocket = ReturnType<typeof initWebSocket>;
	import Tabs from '$lib/components/Tabs.svelte';
	import PositionCard from '$lib/components/PositionCard.svelte';
	import StatsPanel from '$lib/components/StatsPanel.svelte';
	import ScannerPanel from '$lib/components/ScannerPanel.svelte';
	import LogViewer from '$lib/components/LogViewer.svelte';
	import TradeHistory from '$lib/components/TradeHistory.svelte';
	import ConnectionStatus from '$lib/components/ConnectionStatus.svelte';
	import NotificationSettings from '$lib/components/NotificationSettings.svelte';
	import PnLChart from '$lib/components/PnLChart.svelte';
	import WinLossChart from '$lib/components/WinLossChart.svelte';
	import VolumeChart from '$lib/components/VolumeChart.svelte';
	import ThemeToggle from '$lib/components/ThemeToggle.svelte';
	import SettingsPanel from '$lib/components/SettingsPanel.svelte';
	import ExportPanel from '$lib/components/ExportPanel.svelte';
	import SessionSelector from '$lib/components/SessionSelector.svelte';
	import GlobalStats from '$lib/components/GlobalStats.svelte';
	import BotControls from '$lib/components/BotControls.svelte';
	import VariablesPanel from '$lib/components/VariablesPanel.svelte';

	let backendConnected = false;
	let backendError = '';
	let activeTab = 'dashboard';
	let tpSlMode = 'FIXE'; // Mode TP/SL actif du bot

	const tabs = [
		{ id: 'dashboard', label: 'Dashboard', icon: '📊' },
		{ id: 'variables', label: 'Variables', icon: '⚙️' },
		{ id: 'logs', label: 'Logs', icon: '📝' },
		{ id: 'charts', label: 'Graphiques', icon: '📉' },
		{ id: 'history', label: 'Historique', icon: '📜' },
		{ id: 'sessions', label: 'Sessions', icon: '🔄' },
		{ id: 'settings', label: 'Paramètres', icon: '⚙️' }
	];

	async function changeTpSlMode() {
		try {
			// 🔥 MIGRATION COMPLÈTE: Utiliser WebSocket natif au lieu de REST
			const ws = initWebSocket();
			const result = await ws.sendCommand('update_config', { tp_sl_mode: tpSlMode });
			
			if (result && result.updated) {
				console.log(`✅ TP/SL Mode changé via WebSocket: ${tpSlMode}`);
			} else {
				console.error('⚠️ Erreur changement mode TP/SL: pas de réponse');
			}
		} catch (err) {
			console.error('❌ Erreur changement mode TP/SL:', err);
			// Fallback REST si WebSocket non disponible
			try {
				const res = await fetch('/api/config/update', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ tp_sl_mode: tpSlMode })
				});
				if (res.ok) {
					console.log(`✅ TP/SL Mode changé via REST (fallback): ${tpSlMode}`);
				}
			} catch (fallbackErr) {
				console.error('❌ Erreur fallback REST:', fallbackErr);
			}
		}
	}

	// Fetch initial state on mount
	onMount(async () => {
		// 🔥 MIGRATION COMPLÈTE: Initialiser WebSocket natif
		try {
			const ws = initWebSocket();
			
			// Vérifier que l'instance est correcte
			if (!ws) {
				console.error('❌ WebSocket instance est null');
				return;
			}
			
			// Vérifier que la méthode on existe (la classe est exportée, donc ws devrait avoir la méthode)
			if (typeof ws.on !== 'function') {
				console.error('❌ WebSocket.on n\'est pas une fonction', ws);
				console.error('Type de ws:', typeof ws);
				console.error('Méthodes disponibles:', Object.keys(ws || {}));
				console.error('ws.constructor:', ws?.constructor?.name);
				// Ne pas retourner, essayer quand même
			}
			
			// Attendre un peu pour que la connexion soit établie
			await new Promise(resolve => setTimeout(resolve, 100));
			
			// Utiliser ws.on directement si disponible, sinon utiliser une approche alternative
			if (typeof ws.on === 'function') {
				setupWebSocketListeners(ws);
			} else {
				console.warn('⚠️ WebSocket.on non disponible, utilisation alternative');
				// Les événements seront gérés via les callbacks de connexion
			}
		} catch (error) {
			console.error('❌ Erreur initialisation WebSocket:', error);
		}
		
		// Charger l'état initial (via REST pour le premier chargement, puis WebSocket pour les updates)
		await loadInitialState();
	});
	
	function setupWebSocketListeners(ws: BidirectionalWebSocket) {
		// 🔥 MIGRATION COMPLÈTE: Écouter les événements WebSocket pour mises à jour temps réel
		ws.on('status', (data: any) => {
			// Mettre à jour l'état quand le backend envoie un update
			if (data.config && data.config.tp_sl_mode) {
				tpSlMode = data.config.tp_sl_mode;
			}
		});
		
		ws.on('connect', () => {
			console.log('✅ WebSocket connecté');
			backendConnected = true;
			backendError = '';
		});
		
		ws.on('disconnect', () => {
			console.warn('⚠️ WebSocket déconnecté');
			backendConnected = false;
		});
	}

	async function loadInitialState() {
		try {
			const res = await fetch('/api/state');
			if (res.ok) {
				const data = await res.json();
				console.log('Initial state loaded:', data);
				backendConnected = true;
				backendError = '';
				
				// 🔥 FIX: Charger le mode TP/SL actif
				if (data.config && data.config.tp_sl_mode) {
					tpSlMode = data.config.tp_sl_mode;
				}
				
				// 🔥 FIX: Mettre à jour l'état du bot dans BotControls via l'API status
				// (BotControls utilise le store isScanning mis à jour via WebSocket natif)
				if (data.is_scanning !== undefined) {
					// L'état sera mis à jour via WebSocket natif ou le composant BotControls
				}
				
				// 🔥 FIX: Nettoyer les données d'anciennes sessions si aucune position active
				// Les données seront rechargées via WebSocket natif si nécessaire
				if (!data.active_position) {
					// Nettoyer la position
					const { clearPosition } = await import('$lib/stores/position');
					clearPosition();
				}
				
				// 🔥 FIX: Nettoyer et charger l'historique des trades depuis le backend
				const { setTradeHistory, clearHistory } = await import('$lib/stores/trades');
				if (data.trade_history && Array.isArray(data.trade_history) && data.trade_history.length > 0) {
					setTradeHistory(data.trade_history);
				} else {
					// Nettoyer si pas de trades ou liste vide
					clearHistory();
				}
				
				// 🔥 FIX: Charger les stats depuis le backend (remplace les anciennes stats)
				if (data.stats) {
					const { updateStats } = await import('$lib/stores/stats');
					// S'assurer que les valeurs sont numériques
					const cleanStats = {
						wins: Number(data.stats.wins || 0),
						losses: Number(data.stats.losses || 0),
						total_trades: Number(data.stats.total_trades || 0),
						total_pnl_usdt: Number(data.stats.total_pnl_usdt || 0),
						total_pnl_pct: Number(data.stats.total_pnl_pct || 0),
						best_trade: data.stats.best_trade || null,
						worst_trade: data.stats.worst_trade || null,
						avg_trade_duration: Number(data.stats.avg_trade_duration || 0)
					};
					updateStats(cleanStats);
				}
				
				// 🔥 FIX: Nettoyer les graphiques PnL au démarrage si pas de trades
				if (!data.trade_history || data.trade_history.length === 0) {
					const { clearHistory: clearTrades } = await import('$lib/stores/trades');
					clearTrades();
				}
			} else {
				throw new Error(`Backend returned ${res.status}`);
			}
		} catch (err) {
			console.error('Error loading initial state:', err);
			backendError = err.message || 'Backend not reachable';
			backendConnected = false;
			// Réessayer toutes les 5 secondes
			const retry = setInterval(async () => {
				try {
					const res = await fetch('/api/state');
					if (res.ok) {
						backendConnected = true;
						backendError = '';
						clearInterval(retry);
						// Recharger les données sans recharger toute la page
						await loadInitialState();
					}
				} catch (e) {
					// Continue trying
				}
			}, 5000);
		}
	}

	// 🔥 FIX: Recharger les données quand on change d'onglet (évite pages vides)
	let lastTab = activeTab;
	$: if (activeTab && activeTab !== lastTab && backendConnected) {
		const currentTab = activeTab;
		lastTab = currentTab; // Mettre à jour immédiatement pour éviter les boucles
		// Petit délai pour laisser le DOM se mettre à jour
		setTimeout(() => {
			if (activeTab === currentTab) { // Vérifier que l'onglet n'a pas changé entre-temps
				loadInitialState().catch(err => {
					console.error('Error reloading state on tab change:', err);
				});
			}
		}, 100);
	}
</script>

<svelte:head>
	<title>Trade Cursor v7.0 - MEXC Smart Scalping Scanner</title>
</svelte:head>

<div class="app">
	<header class="header">
		<div class="header-content">
			<div class="title-section">
				<h1>⚡ TRADE CURSOR v7.0</h1>
				<div class="subtitle">✅ Stats temps réel • ✅ Volume à la volée • ✅ ATR auto • ✅ No timeout<br>📊 Mode FIXE/ATR • 🧩 Clamp ATR • ⚖️ Win/Loss adjust • 🛡️ BE ATR • 💰 Position Sizing • 📊 Volume Quality • 🎯 Confluence • 🔥 Scanner Scalabilité 0% fees • ⚡ SCAN PARALLÈLE • 🎯 Filtre ATR Optimal</div>
				<span class="mexc-badge">MEXC FUTURES</span>
			</div>
			<div class="header-controls">
				<ThemeToggle />
				<ConnectionStatus />
			</div>
		</div>
	</header>

	{#if backendError}
		<div class="backend-error-banner">
			<div class="error-content">
				<span class="error-icon">⚠️</span>
				<div class="error-text">
					<strong>Backend Not Connected</strong>
					<p>Please start the backend server: <code>python main.py</code></p>
					<p class="retry-text">Retrying connection every 5 seconds...</p>
				</div>
			</div>
		</div>
	{/if}

	<main class="main-content">
		<div class="container">
			<Tabs {tabs} bind:activeTab />
			
			<!-- Tab Content -->
			{#if !backendConnected}
				<div class="tab-content">
					<div class="loading-state">
						<div class="loading-spinner">⏳</div>
						<p>Connexion au backend...</p>
						<p class="retry-text">Tentative de reconnexion en cours...</p>
					</div>
				</div>
			{:else if activeTab === 'dashboard'}
				<div class="tab-content">
					<div class="bot-controls-panel">
						<BotControls />
					</div>
					<div class="status-panel">
						<StatsPanel />
					</div>

					<!-- Sélecteur Mode TP/SL -->
					<div class="tpsl-mode-selector">
						<h3>🎯 Mode TP/SL Actif</h3>
						<div class="mode-selector-content">
							<label for="tp-sl-mode-dashboard">
								<span class="mode-label">Sélectionner le mode de Take Profit / Stop Loss:</span>
							</label>
							<select
								id="tp-sl-mode-dashboard"
								bind:value={tpSlMode}
								on:change={changeTpSlMode}
							>
								<option value="FIXE">FIXE - Pourcentages fixes</option>
								<option value="ATR">ATR - Basé sur volatilité</option>
								<option value="ESCALIER">ESCALIER - TP partiel progressif</option>
							</select>
						</div>
						<p class="mode-info">
							Mode actuel: <strong class="mode-value mode-{tpSlMode.toLowerCase()}">{tpSlMode}</strong>
							<br/>
							<small>Configurez les paramètres de chaque mode dans l'onglet <strong>Variables → TP/SL & Position</strong></small>
						</p>
					</div>

					<div class="position-panel">
						<PositionCard />
					</div>
					<div class="scanner-panel">
						<ScannerPanel />
					</div>
				</div>
			{:else if activeTab === 'variables'}
				<div class="tab-content">
					<VariablesPanel />
				</div>
			{:else if activeTab === 'logs'}
				<div class="tab-content">
					<div class="logs-panel">
						<LogViewer />
					</div>
				</div>
			{:else if activeTab === 'charts'}
				<div class="tab-content">
					<div class="charts-grid">
						<PnLChart />
						<WinLossChart />
					</div>
				</div>
			{:else if activeTab === 'history'}
				<div class="tab-content">
					<TradeHistory />
					<div class="export-panel">
						<ExportPanel />
					</div>
				</div>
			{:else if activeTab === 'sessions'}
				<div class="tab-content">
					<div class="tab-description">
						<h2>📂 Gestion des Sessions de Trading</h2>
						<p>
							Les sessions vous permettent de gérer plusieurs stratégies de trading simultanément,
							chacune avec ses propres paires et configurations.
							<strong>Note:</strong> Cette fonctionnalité est avancée et nécessite que le backend supporte le multi-sessions.
						</p>
					</div>
					<SessionSelector />
					<div class="sessions-stats">
						<GlobalStats />
					</div>
				</div>
			{:else if activeTab === 'settings'}
				<div class="tab-content">
					<SettingsPanel />
					<div class="export-settings">
						<ExportPanel />
					</div>
					<div class="notifications-settings">
						<NotificationSettings />
					</div>
				</div>
			{/if}
		</div>
	</main>

	<footer class="footer">
		<div class="footer-content">
			<div class="footer-text">
				Trade Cursor v7.0 | Python Backend | SvelteKit Frontend
			</div>
			<div class="footer-links">
				<a href="https://github.com/chpeu/trade_cursor_py" target="_blank" rel="noopener">GitHub</a>
			</div>
		</div>
	</footer>
</div>

<style>
	/* Style port 5000 - Fond sombre, couleurs néon */
	:global(body) {
		font-family: 'Courier New', monospace;
		background: #0a0e27;
		color: #fff;
		min-height: 100vh;
		padding: 10px;
		font-size: 14px;
		line-height: 1.4;
		margin: 0;
	}

	.app {
		min-height: 100vh;
		display: flex;
		flex-direction: column;
	}

	.container {
		max-width: 100%;
		margin: 0 auto;
	}

	/* Header style port 5000 */
	.header {
		text-align: center;
		padding: 15px 0;
		border-bottom: 2px solid #1e2749;
		margin-bottom: 15px;
		background: #0a0e27;
	}

	.header-content {
		max-width: 100%;
		margin: 0 auto;
		padding: 0 15px;
		display: flex;
		justify-content: space-between;
		align-items: center;
		flex-wrap: wrap;
		gap: 15px;
	}

	.title-section {
		flex: 1;
		text-align: center;
	}

	h1 {
		font-size: 24px;
		color: #00ff88;
		text-shadow: 0 0 20px rgba(0, 255, 136, 0.5);
		margin-bottom: 8px;
		font-weight: bold;
	}

	.subtitle {
		color: #888;
		font-size: 12px;
		line-height: 1.4;
		margin-bottom: 8px;
	}

	.mexc-badge {
		display: inline-block;
		background: linear-gradient(135deg, #1e90ff 0%, #00bfff 100%);
		color: white;
		padding: 5px 14px;
		border-radius: 20px;
		font-size: 11px;
		font-weight: bold;
		margin-top: 8px;
	}

	.header-controls {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	/* Backend error banner */
	.backend-error-banner {
		background: linear-gradient(135deg, #ff4444 0%, #cc0000 100%);
		border-bottom: 2px solid #ff6666;
		padding: 15px 0;
		animation: slideDown 0.5s ease-out;
	}

	@keyframes slideDown {
		from {
			transform: translateY(-100%);
			opacity: 0;
		}
		to {
			transform: translateY(0);
			opacity: 1;
		}
	}

	.error-content {
		max-width: 100%;
		margin: 0 auto;
		padding: 0 15px;
		display: flex;
		align-items: center;
		gap: 15px;
	}

	.error-icon {
		font-size: 36px;
		animation: pulse 2s ease-in-out infinite;
	}

	@keyframes pulse {
		0%, 100% {
			transform: scale(1);
		}
		50% {
			transform: scale(1.1);
		}
	}

	.error-text {
		flex: 1;
		color: white;
	}

	.error-text strong {
		font-size: 18px;
		display: block;
		margin-bottom: 6px;
	}

	.error-text p {
		margin: 3px 0;
		font-size: 13px;
	}

	.error-text code {
		background: rgba(255, 255, 255, 0.2);
		padding: 2px 6px;
		border-radius: 4px;
		font-family: 'Courier New', monospace;
		font-weight: bold;
	}

	.retry-text {
		font-size: 11px !important;
		opacity: 0.8;
		font-style: italic;
	}

	/* Main content */
	.main-content {
		flex: 1;
		padding: 0;
	}

	/* Tab content */
	.tab-content {
		display: flex;
		flex-direction: column;
		gap: 15px;
	}

	.bot-controls-panel,
	.status-panel,
	.position-panel,
	.scanner-panel,
	.notifications-panel,
	.logs-panel,
	.position-details,
	.stats-grid,
	.charts-grid,
	.export-panel,
	.sessions-stats,
	.export-settings,
	.notifications-settings {
		background: #1e2749;
		border-radius: 10px;
		padding: 18px;
		border: 2px solid #2a3a6b;
	}

	.charts-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
		gap: 15px;
	}

	/* Footer */
	.footer {
		background: #1e2749;
		border-top: 2px solid #2a3a6b;
		padding: 15px 0;
		margin-top: 15px;
	}

	.footer-content {
		max-width: 100%;
		margin: 0 auto;
		padding: 0 15px;
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 15px;
		flex-wrap: wrap;
	}

	.footer-text {
		font-size: 11px;
		color: #888;
	}

	.footer-links a {
		color: #00ff88;
		text-decoration: none;
		font-size: 11px;
		font-weight: bold;
		transition: color 0.3s;
	}

	.footer-links a:hover {
		color: #00cc6a;
		text-decoration: underline;
	}

	/* Tab description */
	.tab-description {
		background: rgba(0, 170, 255, 0.1);
		border: 2px solid #00aaff;
		border-radius: 10px;
		padding: 20px;
		margin-bottom: 20px;
	}

	.tab-description h2 {
		font-size: 18px;
		color: #00aaff;
		margin: 0 0 10px 0;
	}

	.tab-description p {
		font-size: 14px;
		color: #aaa;
		line-height: 1.6;
		margin: 0;
	}

	.tab-description strong {
		color: #00ff88;
	}

	/* Mobile Responsive */
	@media (max-width: 768px) {
		:global(body) {
			padding: 8px;
			font-size: 13px;
		}

		h1 {
			font-size: 20px;
		}

		.subtitle {
			font-size: 11px;
		}

		.header-content {
			flex-direction: column;
			text-align: center;
		}

		.charts-grid {
			grid-template-columns: 1fr;
		}

		.footer-content {
			flex-direction: column;
			text-align: center;
		}

		.bot-controls-panel,
		.tab-description {
			padding: 15px;
		}

		.tab-description h2 {
			font-size: 16px;
		}

		.tab-description p {
			font-size: 13px;
		}

		.status-panel,
		.position-panel,
		.scanner-panel,
		.notifications-panel,
		.logs-panel,
		.position-details,
		.stats-grid,
		.charts-grid,
		.export-panel,
		.sessions-stats,
		.export-settings,
		.notifications-settings {
			padding: 12px;
		}
	}

	/* TP/SL Mode Selector */
	.tpsl-mode-selector {
		background: #1e2749;
		border-radius: 12px;
		padding: 24px;
		border: 2px solid #2a3a6b;
		margin-bottom: 20px;
	}

	.tpsl-mode-selector h3 {
		font-size: 20px;
		color: #00ff88;
		margin: 0 0 16px 0;
	}

	.mode-selector-content {
		display: flex;
		flex-direction: column;
		gap: 12px;
		margin-bottom: 16px;
	}

	.mode-label {
		font-size: 14px;
		color: #00aaff;
		font-weight: bold;
	}

	.tpsl-mode-selector select {
		background: #0a0e27;
		color: #fff;
		border: 2px solid #00aaff;
		border-radius: 8px;
		padding: 12px 16px;
		font-size: 14px;
		font-weight: bold;
		cursor: pointer;
		transition: all 0.3s;
	}

	.tpsl-mode-selector select:hover {
		border-color: #00ff88;
		background: rgba(0, 170, 255, 0.1);
	}

	.tpsl-mode-selector select:focus {
		outline: none;
		border-color: #00ff88;
		box-shadow: 0 0 10px rgba(0, 255, 136, 0.3);
	}

	.mode-info {
		background: rgba(0, 170, 255, 0.1);
		border-left: 3px solid #00aaff;
		padding: 12px;
		font-size: 13px;
		color: #ccc;
		margin: 0;
	}

	.mode-info strong {
		color: #00aaff;
	}

	.mode-value {
		padding: 4px 12px;
		border-radius: 6px;
		font-weight: bold;
		font-size: 13px;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.mode-value.mode-fixe {
		background: linear-gradient(135deg, #00ff88 0%, #00cc6a 100%);
		color: #0a0e27;
	}

	.mode-value.mode-atr {
		background: linear-gradient(135deg, #00aaff 0%, #0088cc 100%);
		color: #0a0e27;
	}

	.mode-value.mode-escalier {
		background: linear-gradient(135deg, #ff8800 0%, #cc6600 100%);
		color: #fff;
	}

	.mode-info small {
		font-size: 11px;
		color: #888;
	}

	/* 🔥 FIX: Style pour état de chargement */
	.loading-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 60px 20px;
		text-align: center;
		min-height: 400px;
	}

	.loading-spinner {
		font-size: 48px;
		animation: spin 2s linear infinite;
		margin-bottom: 20px;
	}

	@keyframes spin {
		from {
			transform: rotate(0deg);
		}
		to {
			transform: rotate(360deg);
		}
	}

	.loading-state p {
		font-size: 16px;
		color: #00ff88;
		margin: 10px 0;
	}

	.loading-state .retry-text {
		font-size: 13px;
		color: #888;
		margin-top: 10px;
	}
</style>
