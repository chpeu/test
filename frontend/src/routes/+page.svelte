<script>
	import { onMount } from 'svelte';
	import PositionCard from '$lib/components/PositionCard.svelte';
	import StatsPanel from '$lib/components/StatsPanel.svelte';
	import ScannerPanel from '$lib/components/ScannerPanel.svelte';
	import LogViewer from '$lib/components/LogViewer.svelte';
	import TradeHistory from '$lib/components/TradeHistory.svelte';
	import ConnectionStatus from '$lib/components/ConnectionStatus.svelte';

	// Fetch initial state on mount
	onMount(async () => {
		try {
			const res = await fetch('/api/state');
			const data = await res.json();
			console.log('Initial state loaded:', data);
		} catch (err) {
			console.error('Error loading initial state:', err);
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
				<h1 class="title">🚀 Trade Cursor v7.0</h1>
				<div class="subtitle">MEXC Smart Scalping Scanner - Powered by Svelte</div>
				<div class="mexc-badge">MEXC Futures</div>
			</div>
			<ConnectionStatus />
		</div>
	</header>

	<main class="main-content">
		<div class="container">
			<!-- Position Section -->
			<section class="section position-section slide-up">
				<PositionCard />
			</section>

			<!-- Stats Section -->
			<section class="section stats-section slide-up" style="animation-delay: 0.1s">
				<StatsPanel />
			</section>

			<!-- Scanner Section -->
			<section class="section scanner-section slide-up" style="animation-delay: 0.2s">
				<ScannerPanel />
			</section>

			<!-- Two Column Layout -->
			<div class="two-column slide-up" style="animation-delay: 0.3s">
				<!-- Trade History -->
				<section class="section history-section">
					<TradeHistory />
				</section>

				<!-- Logs -->
				<section class="section logs-section">
					<LogViewer />
				</section>
			</div>
		</div>
	</main>

	<footer class="footer">
		<div class="footer-content">
			<div class="footer-text">
				Trade Cursor v7.0 | Python {navigator.platform} | SvelteKit Frontend
			</div>
			<div class="footer-links">
				<a href="https://github.com/chpeu/trade_cursor_py" target="_blank" rel="noopener">GitHub</a>
			</div>
		</div>
	</footer>
</div>

<style>
	.app {
		min-height: 100vh;
		display: flex;
		flex-direction: column;
	}

	.header {
		background: linear-gradient(135deg, #1e2749 0%, #2a3a6b 100%);
		border-bottom: 2px solid var(--accent-green);
		padding: 20px 0;
		box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
		position: sticky;
		top: 0;
		z-index: 100;
		backdrop-filter: blur(10px);
	}

	.header-content {
		max-width: 1400px;
		margin: 0 auto;
		padding: 0 20px;
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 20px;
	}

	.title-section {
		flex: 1;
	}

	.title {
		font-size: 32px;
		color: var(--accent-green);
		text-shadow: 0 0 30px rgba(0, 255, 136, 0.5);
		margin-bottom: 8px;
		font-weight: bold;
	}

	.subtitle {
		font-size: 14px;
		color: var(--text-secondary);
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
	}

	.main-content {
		flex: 1;
		padding: 30px 0;
	}

	.container {
		max-width: 1400px;
		margin: 0 auto;
		padding: 0 20px;
	}

	.section {
		margin-bottom: 30px;
	}

	.two-column {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 30px;
	}

	.footer {
		background: var(--bg-secondary);
		border-top: 1px solid var(--bg-tertiary);
		padding: 20px 0;
		margin-top: auto;
	}

	.footer-content {
		max-width: 1400px;
		margin: 0 auto;
		padding: 0 20px;
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 20px;
	}

	.footer-text {
		font-size: 12px;
		color: var(--text-secondary);
	}

	.footer-links a {
		color: var(--accent-green);
		text-decoration: none;
		font-size: 12px;
		font-weight: bold;
		transition: color 0.3s;
	}

	.footer-links a:hover {
		color: #00cc6a;
		text-decoration: underline;
	}

	/* Mobile Responsive */
	@media (max-width: 1024px) {
		.two-column {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 768px) {
		.header-content {
			flex-direction: column;
			text-align: center;
		}

		.title {
			font-size: 24px;
		}

		.subtitle {
			font-size: 12px;
		}

		.footer-content {
			flex-direction: column;
			text-align: center;
		}

		.section {
			margin-bottom: 20px;
		}

		.main-content {
			padding: 20px 0;
		}
	}

	/* Animations */
	.slide-up {
		animation: slideUp 0.5s ease-out;
	}

	@keyframes slideUp {
		from {
			transform: translateY(30px);
			opacity: 0;
		}
		to {
			transform: translateY(0);
			opacity: 1;
		}
	}
</style>
