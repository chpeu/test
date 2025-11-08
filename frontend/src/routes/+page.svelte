<script>
	import { onMount } from 'svelte';
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

	let backendConnected = false;
	let backendError = '';
	let activeTab = 'dashboard';

	const tabs = [
		{ id: 'dashboard', label: 'Dashboard', icon: '📊' },
		{ id: 'scanner', label: 'Scanner', icon: '🔍' },
		{ id: 'position', label: 'Position', icon: '💰' },
		{ id: 'stats', label: 'Stats', icon: '📈' },
		{ id: 'charts', label: 'Graphiques', icon: '📉' },
		{ id: 'history', label: 'Historique', icon: '📜' },
		{ id: 'sessions', label: 'Sessions', icon: '🔄' },
		{ id: 'settings', label: 'Paramètres', icon: '⚙️' }
	];

	// Fetch initial state on mount
	onMount(async () => {
		try {
			const res = await fetch('/api/state');
			if (res.ok) {
				const data = await res.json();
				console.log('Initial state loaded:', data);
				backendConnected = true;
			} else {
				throw new Error(`Backend returned ${res.status}`);
			}
		} catch (err) {
			console.error('Error loading initial state:', err);
			backendError = err.message || 'Backend not reachable';
			// Réessayer toutes les 5 secondes
			const retry = setInterval(async () => {
				try {
					const res = await fetch('/api/state');
					if (res.ok) {
						backendConnected = true;
						backendError = '';
						clearInterval(retry);
						window.location.reload();
					}
				} catch (e) {
					// Continue trying
				}
			}, 5000);
		}
	});
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
			{#if activeTab === 'dashboard'}
				<div class="tab-content">
					<div class="status-panel">
						<StatsPanel />
					</div>
					<div class="position-panel">
						<PositionCard />
					</div>
					<div class="scanner-panel">
						<ScannerPanel />
					</div>
					<div class="notifications-panel">
						<NotificationSettings />
					</div>
				</div>
			{:else if activeTab === 'scanner'}
				<div class="tab-content">
					<ScannerPanel />
					<div class="logs-panel">
						<LogViewer />
					</div>
				</div>
			{:else if activeTab === 'position'}
				<div class="tab-content">
					<PositionCard />
					<div class="position-details">
						<StatsPanel />
					</div>
				</div>
			{:else if activeTab === 'stats'}
				<div class="tab-content">
					<GlobalStats />
					<div class="stats-grid">
						<StatsPanel />
					</div>
				</div>
			{:else if activeTab === 'charts'}
				<div class="tab-content">
					<div class="charts-grid">
						<PnLChart />
						<WinLossChart />
						<VolumeChart />
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
</style>
