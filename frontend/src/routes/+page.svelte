<script lang="ts">
	import { onMount } from 'svelte';
	import { initWebSocket, getWebSocket } from '$lib/utils/websocket';
	type BidirectionalWebSocket = ReturnType<typeof initWebSocket>;
	
	// 🔥 FIX: SvelteKit passe automatiquement params, mais on ne l'utilise pas
	export let params = {};
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
	import { recentLogs } from '$lib/stores/logs';
	import { derived } from 'svelte/store';

	// 🔥 FIX: Popup d'erreur global (affiché sur toutes les pages)
	let showErrorPopup = false;
	let lastErrorId: string | null = null;
	let popupHiddenUntil: number | null = null; // Timestamp jusqu'auquel le popup est caché

	// 🔥 FIX: Erreurs critiques uniquement (pour le popup)
	const criticalErrorLogs = derived(recentLogs, $logs =>
		$logs.filter(log => log.level === 'ERROR' || log.level === 'CRITICAL')
	);

	// 🔥 FIX: Détecter les nouvelles erreurs CRITIQUES pour afficher le popup
	$: if ($criticalErrorLogs.length > 0) {
		const latestError = $criticalErrorLogs[$criticalErrorLogs.length - 1];
		const now = Date.now();
		// Vérifier si le popup n'est pas caché temporairement
		if (latestError && latestError.id !== lastErrorId && (popupHiddenUntil === null || now > popupHiddenUntil)) {
			lastErrorId = latestError.id;
			showErrorPopup = true;
			popupHiddenUntil = null; // Réinitialiser le timer
		}
	}

	// 🔥 FIX: Fonction pour acquitter et cacher le popup pendant 5 secondes
	function acknowledgeError() {
		showErrorPopup = false;
		// Cacher le popup pendant 5 secondes
		popupHiddenUntil = Date.now() + 5000;
	}

	// 🔥 FIX: Fonction helper pour formater le temps
	function formatTime(timestamp: string | number): string {
		if (!timestamp) return '';
		const date = new Date(timestamp);
		return date.toLocaleTimeString('en-US', { hour12: false });
	}

	// 🔥 FIX: Fonction helper pour supprimer les codes ANSI
	function stripAnsiCodes(text: string): string {
		if (!text) return '';
		return text.replace(/\x1b\[\d+m/g, '').replace(/\[\d+m/g, '');
	}

	let backendConnected = false;
	let backendError = '';
	let activeTab = 'dashboard';
	let tpSlMode = 'FIXE'; // Mode TP/SL actif du bot
	let tpSlModeDebounceTimer: ReturnType<typeof setTimeout> | null = null;
	const TP_SL_MODE_SAVE_DELAY = 2500; // 2.5 secondes d'inactivité avant sauvegarde automatique

	const tabs = [
		{ id: 'dashboard', label: 'Dashboard', icon: '📊' },
		{ id: 'variables', label: 'Variables', icon: '⚙️' },
		{ id: 'logs', label: 'Logs', icon: '📝' },
		{ id: 'charts', label: 'Graphiques', icon: '📉' },
		{ id: 'history', label: 'Historique', icon: '📜' },
		{ id: 'sessions', label: 'Sessions', icon: '🔄' },
		{ id: 'settings', label: 'Paramètres', icon: '⚙️' }
	];

	// 🔥 FIX: Fonction pour sauvegarder le mode TP/SL avec debounce
	async function saveTpSlMode() {
		if (tpSlModeDebounceTimer) {
			clearTimeout(tpSlModeDebounceTimer);
		}
		
		tpSlModeDebounceTimer = setTimeout(async () => {
			try {
				// 🔥 MIGRATION COMPLÈTE: Utiliser WebSocket natif au lieu de REST
				const ws = initWebSocket();
				const result = await ws.sendCommand('update_config', { tp_sl_mode: tpSlMode });
				
				if (result && result.updated) {
					console.log(`✅ TP/SL Mode sauvegardé via WebSocket: ${tpSlMode}`);
					// 🔥 FIX: L'événement config_updated sera émis automatiquement par le backend
					// VariablesPanel écoutera cet événement et rafraîchira completeConfig
				} else {
					console.error('⚠️ Erreur sauvegarde mode TP/SL: pas de réponse');
				}
			} catch (err) {
				console.error('❌ Erreur sauvegarde mode TP/SL:', err);
			} finally {
				tpSlModeDebounceTimer = null;
			}
		}, TP_SL_MODE_SAVE_DELAY);
	}

	// 🔥 FIX: Fonction appelée lors du changement de mode (déclenche le debounce)
	function changeTpSlMode() {
		saveTpSlMode();
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
			
			// Vérifier que la méthode on existe
			if (!('on' in ws) || typeof ws.on !== 'function') {
				console.error('❌ WebSocket.on n\'est pas une fonction', ws);
				// Attendre un peu et réessayer
				await new Promise(resolve => setTimeout(resolve, 500));
				if (!('on' in ws) || typeof ws.on !== 'function') {
					console.error('❌ WebSocket.on toujours non disponible après attente');
					return;
				}
			}
			
			// 🔥 FIX: Écouter l'événement 'connect' avant de charger l'état initial
			ws.once('connect', async () => {
				console.log('✅ WebSocket connecté, chargement de l\'état initial...');
				await loadInitialState();
			});
			
			// Configurer les listeners
			setupWebSocketListeners(ws);
			
			// Si déjà connecté, charger immédiatement
			if (ws.connected) {
				await loadInitialState();
			} else {
				// Attendre la connexion (max 5 secondes)
				let attempts = 0;
				const maxAttempts = 50; // 50 * 100ms = 5 secondes
				while ((!ws.connected) && attempts < maxAttempts) {
					await new Promise(resolve => setTimeout(resolve, 100));
					attempts++;
				}
				
				if (ws.connected) {
					await loadInitialState();
				} else {
					console.warn('⚠️ WebSocket non connecté après 5 secondes, le chargement se fera automatiquement à la connexion');
				}
			}
		} catch (error) {
			console.error('❌ Erreur initialisation WebSocket:', error);
			// Réessayer après un délai
			setTimeout(() => {
				loadInitialState().catch(err => {
					console.error('Error loading initial state:', err);
				});
			}, 2000);
		}
	});
	
	function setupWebSocketListeners(ws: BidirectionalWebSocket) {
		// 🔥 MIGRATION COMPLÈTE: Écouter les événements WebSocket pour mises à jour temps réel
		ws.on('status', (data: any) => {
			// Mettre à jour l'état quand le backend envoie un update
			if (data.config && data.config.tp_sl_mode) {
				tpSlMode = data.config.tp_sl_mode;
			}
		});
		
		// 🔥 BIDIRECTIONNEL: Écouter les mises à jour de config depuis le backend
		ws.on('config_updated', (data: any) => {
			console.log('🔄 Config mise à jour depuis backend:', data.updated);
			// Le frontend peut réagir aux changements de config du backend
			if (data.updated && data.updated.tp_sl_mode) {
				tpSlMode = data.updated.tp_sl_mode;
			}
		});
		
		// 🔥 BIDIRECTIONNEL: Écouter les logs depuis le backend pour synchronisation temps réel
		ws.on('log', async (logEntry: any) => {
			const { addLog } = await import('$lib/stores/logs');
			// Convertir le timestamp si nécessaire
			if (logEntry.timestamp && !logEntry.timestamp.includes('T')) {
				// Format HH:MM:SS -> ISO
				const today = new Date().toISOString().split('T')[0];
				logEntry.timestamp = `${today}T${logEntry.timestamp}`;
			}
			addLog(logEntry);
		});
		
		// 🔥 BIDIRECTIONNEL: Écouter les mises à jour de position
		ws.on('position_update', async (data: any) => {
			const { updatePosition } = await import('$lib/stores/position');
			if (data) {
				updatePosition(data);
			}
		});
		
		ws.on('position_opened', async (data: any) => {
			const { updatePosition } = await import('$lib/stores/position');
			if (data) {
				updatePosition(data);
			}
		});
		
		ws.on('position_closed', async (data: any) => {
			const { clearPosition } = await import('$lib/stores/position');
			clearPosition();
			// Recharger l'historique des trades
			const { setTradeHistory } = await import('$lib/stores/trades');
			if (data && data.trade) {
				setTradeHistory([data.trade]);
			}
		});
		
		// 🔥 BIDIRECTIONNEL: Écouter les mises à jour de stats
		ws.on('stats_update', async (data: any) => {
			console.log('📊 stats_update reçu:', data);
			const { updateStats } = await import('$lib/stores/stats');
			if (data) {
				updateStats(data);
			}
		});
		
		// 🔥 BIDIRECTIONNEL: Écouter les mises à jour des top pairs
		ws.on('top_pairs_update', async (data: any) => {
			// 🔥 FIX: Mettre à jour le store scanner avec les paires
			if (data && data.pairs) {
				const { updateTopPairs } = await import('$lib/stores/scanner');
				updateTopPairs(data.pairs);
			}
		});
		
		// 🔥 BIDIRECTIONNEL: Écouter les événements de scan
		ws.on('scan_started', async (data: any) => {
			const { startScanning } = await import('$lib/stores/scanner');
			startScanning();
		});
		
		ws.on('scan_complete', async (data: any) => {
			const { stopScanning } = await import('$lib/stores/scanner');
			stopScanning();
		});
		
		// 🔥 FIX: Écouter l'événement reset_session depuis le backend (au démarrage, AVANT le scan)
		ws.on('reset_session', async (data: any) => {
			console.log('🔄 Reset session reçu depuis backend:', data);
			const { clearHistory } = await import('$lib/stores/trades');
			clearHistory();
			const { resetSessionStats } = await import('$lib/stores/stats');
			resetSessionStats();
			// Note: Les graphiques seront automatiquement réinitialisés via les stores réinitialisés
		});
		
		ws.on('connect', async () => {
			console.log('✅ WebSocket connecté');
			backendConnected = true;
			backendError = '';
			// 🔥 FIX: Ne plus réinitialiser ici - le backend enverra reset_session au démarrage
			// 🔥 FIX: Charger l'état initial quand le WebSocket se connecte
			try {
				await loadInitialState();
			} catch (err) {
				console.error('Error loading initial state on connect:', err);
			}
		});
		
		ws.on('disconnect', async () => {
			console.warn('⚠️ WebSocket déconnecté');
			backendConnected = false;
			// 🔥 FIX: Reset trades à la fermeture du backend
			const { clearHistory } = await import('$lib/stores/trades');
			clearHistory();
			// 🔥 FIX: Reset stats session
			const { resetSessionStats } = await import('$lib/stores/stats');
			resetSessionStats();
		});
	}

	// 🔥 BIDIRECTIONNEL: Fonction helper pour traiter les données d'état
	async function processStateData(data: any) {
		// 🔥 FIX: Mettre à jour l'état du bot dans BotControls via l'API status
		// (BotControls utilise le store isScanning mis à jour via WebSocket natif)
		if (data.is_scanning !== undefined) {
			// L'état sera mis à jour via WebSocket natif ou le composant BotControls
		}
		
		// 🔥 FIX: Mettre à jour la position active si présente
		if (data.active_position || data.position?.active) {
			const { updatePosition } = await import('$lib/stores/position');
			const positionData = data.active_position || data.position;
			if (positionData) {
				updatePosition(positionData);
			}
		} else {
			// Nettoyer la position si aucune position active
			const { clearPosition } = await import('$lib/stores/position');
			clearPosition();
		}
		
		// 🔥 FIX: Nettoyer et charger l'historique des trades depuis le backend
		const { setTradeHistory, clearHistory } = await import('$lib/stores/trades');
		const tradeHistory = data.trade_history || (data.position?.data ? [] : []);
		if (tradeHistory && Array.isArray(tradeHistory) && tradeHistory.length > 0) {
			setTradeHistory(tradeHistory);
		} else {
			// Nettoyer si pas de trades ou liste vide
			clearHistory();
		}
		
		// 🔥 FIX: Charger les stats depuis le backend (remplace les anciennes stats)
		const stats = data.stats || {};
		if (stats && (stats.wins !== undefined || stats.total_trades !== undefined)) {
			const { updateStats } = await import('$lib/stores/stats');
			// S'assurer que les valeurs sont numériques
			const cleanStats = {
				wins: Number(stats.wins || 0),
				losses: Number(stats.losses || 0),
				total_trades: Number(stats.total_trades || 0),
				total_pnl_usdt: Number(stats.total_pnl_usdt || 0),
				total_pnl_pct: Number(stats.total_pnl_pct || 0),
				best_trade: stats.best_trade || null,
				worst_trade: stats.worst_trade || null,
				avg_trade_duration: Number(stats.avg_trade_duration || 0)
			};
			updateStats(cleanStats);
		}
		
		// 🔥 FIX: Nettoyer les graphiques PnL au démarrage si pas de trades
		if (!tradeHistory || tradeHistory.length === 0) {
			const { clearHistory: clearTrades } = await import('$lib/stores/trades');
			clearTrades();
		}
	}

	async function loadInitialState() {
		try {
			// 🔥 BIDIRECTIONNEL: Utiliser WebSocket uniquement (plus de fallback REST)
			const ws = getWebSocket();
			if (!ws || !ws.connected) {
				throw new Error('WebSocket non connecté. Veuillez attendre la connexion.');
			}

			const response = await ws.sendRequest('state', {});
			// 🔥 FIX: Le backend envoie { type: 'request_response', data: state_data }
			const stateData = response?.data || response;
			if (!stateData || (!stateData.success && !stateData.config && stateData.trade_history === undefined)) {
				throw new Error('Données d\'état invalides reçues du backend');
			}

			console.log('Initial state loaded via WebSocket:', stateData);
			backendConnected = true;
			backendError = '';
			
			// 🔥 FIX: Charger le mode TP/SL actif
			if (stateData.config && stateData.config.tp_sl_mode) {
				tpSlMode = stateData.config.tp_sl_mode;
			}
			
			// Traiter les autres données
			await processStateData(stateData);
		} catch (err) {
			console.error('Error loading initial state:', err);
			backendError = err.message || 'Backend not reachable';
			backendConnected = false;
			// 🔥 BIDIRECTIONNEL: Plus de retry REST - La reconnexion WebSocket gère automatiquement les tentatives
			// Le WebSocket se reconnectera automatiquement et chargera l'état via WebSocket
		}
	}

	// 🔥 FIX: Recharger les données quand on change d'onglet (évite pages vides)
	// 🔥 FIX: Ne pas recharger si on est dans l'onglet Variables avec des changements non sauvegardés
	let lastTab = activeTab;
	$: if (activeTab && activeTab !== lastTab && backendConnected && activeTab !== 'variables') {
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
	} else if (activeTab && activeTab !== lastTab) {
		// Mettre à jour lastTab même si on ne recharge pas
		lastTab = activeTab;
	}
</script>

<!-- 🔥 FIX: Popup d'erreur global (affiché sur toutes les pages) -->
{#if showErrorPopup && $criticalErrorLogs.length > 0}
	{@const latestError = $criticalErrorLogs[$criticalErrorLogs.length - 1]}
	<div class="error-popup" class:blinking={showErrorPopup}>
		<div class="error-popup-content">
			<div class="error-popup-header">
				<span class="error-icon">🚨</span>
				<h3>Erreur détectée</h3>
				<button class="close-popup-btn" on:click={acknowledgeError}>✕</button>
			</div>
			<div class="error-popup-message">
				<span class="error-time">{formatTime(latestError.timestamp)}</span>
				<span class="error-level">[{latestError.level}]</span>
				<span class="error-text">{stripAnsiCodes(latestError.message)}</span>
			</div>
			<button class="acknowledge-btn" on:click={acknowledgeError}>Acquitter</button>
		</div>
	</div>
{/if}

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

	/* 🔥 FIX: Popup d'erreur global (affiché sur toutes les pages) */
	.error-popup {
		position: fixed;
		top: 20px;
		right: 20px;
		z-index: 10000;
		background: linear-gradient(135deg, #ff4444 0%, #cc0000 100%);
		border: 3px solid #fff;
		border-radius: 12px;
		padding: 0;
		box-shadow: 0 8px 32px rgba(255, 68, 68, 0.6);
		min-width: 400px;
		max-width: 600px;
	}

	.error-popup.blinking {
		animation: blink 1s ease-in-out infinite;
	}

	@keyframes blink {
		0%, 100% {
			opacity: 1;
			transform: scale(1);
		}
		50% {
			opacity: 0.8;
			transform: scale(1.02);
		}
	}

	.error-popup-content {
		background: #1e2749;
		border-radius: 10px;
		padding: 20px;
		border: 2px solid #ff4444;
	}

	.error-popup-header {
		display: flex;
		align-items: center;
		gap: 12px;
		margin-bottom: 15px;
		padding-bottom: 15px;
		border-bottom: 2px solid rgba(255, 68, 68, 0.3);
	}

	.error-icon {
		font-size: 24px;
		animation: pulse 2s ease-in-out infinite;
	}

	@keyframes pulse {
		0%, 100% {
			transform: scale(1);
		}
		50% {
			transform: scale(1.2);
		}
	}

	.error-popup-header h3 {
		flex: 1;
		margin: 0;
		color: #fff;
		font-size: 18px;
		font-weight: bold;
	}

	.close-popup-btn {
		background: rgba(255, 255, 255, 0.2);
		border: 1px solid rgba(255, 255, 255, 0.3);
		color: #fff;
		border-radius: 50%;
		width: 28px;
		height: 28px;
		cursor: pointer;
		font-size: 16px;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.2s;
	}

	.close-popup-btn:hover {
		background: rgba(255, 255, 255, 0.3);
		transform: scale(1.1);
	}

	.error-popup-message {
		margin-bottom: 15px;
		padding: 12px;
		background: rgba(0, 0, 0, 0.3);
		border-radius: 6px;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.error-time {
		font-size: 12px;
		color: #888;
		font-family: 'Courier New', monospace;
	}

	.error-level {
		font-size: 13px;
		color: #ff4444;
		font-weight: bold;
		font-family: 'Courier New', monospace;
	}

	.error-text {
		font-size: 14px;
		color: #fff;
		line-height: 1.5;
		word-break: break-word;
	}

	.acknowledge-btn {
		width: 100%;
		padding: 12px;
		background: linear-gradient(135deg, #00ff88 0%, #00cc6a 100%);
		border: none;
		border-radius: 8px;
		color: #0a0e27;
		font-weight: bold;
		font-size: 14px;
		cursor: pointer;
		transition: all 0.3s;
		box-shadow: 0 4px 12px rgba(0, 255, 136, 0.3);
	}

	.acknowledge-btn:hover {
		transform: translateY(-2px);
		box-shadow: 0 6px 16px rgba(0, 255, 136, 0.5);
	}

	.acknowledge-btn:active {
		transform: translateY(0);
	}

	/* Mobile */
	@media (max-width: 768px) {
		.error-popup {
			left: 10px;
			right: 10px;
			min-width: auto;
		}
	}
</style>
