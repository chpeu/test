<script>
	import { stats, winrate, winLossRatio } from '$lib/stores/stats';
	import { onMount, onDestroy } from 'svelte';
	import { writable } from 'svelte/store';
	import { getSocket } from '$lib/utils/socket';

	// État du bot
	let botRunning = writable(false);
	let botLoading = writable(false);
	let statusInterval = null;
	let socket = null;

	function formatNumber(num) {
		if (num === null || num === undefined || isNaN(num)) return '0.00';
		return Number(num).toFixed(2);
	}

	async function toggleBot() {
		$botLoading = true;
		try {
			const endpoint = $botRunning ? '/api/stop' : '/api/start';
			const res = await fetch(endpoint, { method: 'POST' });

			if (res.ok) {
				const data = await res.json();
				$botRunning = data.is_scanning || false;
				console.log(`Bot ${$botRunning ? 'started' : 'stopped'}`);
			} else {
				console.error('Error toggling bot:', res.status);
				alert('❌ Erreur: Impossible de contrôler le bot. Vérifiez que le backend est démarré.');
			}
		} catch (err) {
			console.error('Error toggling bot:', err);
			alert('❌ Erreur: Backend non accessible');
		} finally {
			$botLoading = false;
		}
	}

	// Vérifier l'état initial du bot
	async function checkBotStatus() {
		try {
			const res = await fetch('/api/status');
			if (res.ok) {
				const data = await res.json();
				$botRunning = data.is_scanning || false;
			}
		} catch (err) {
			console.error('Error checking bot status:', err);
		}
	}

	// 🔥 FIX: Écouter les événements Socket.IO pour mettre à jour l'état
	function setupSocketListeners() {
		socket = getSocket();
		if (!socket) {
			setTimeout(setupSocketListeners, 1000);
			return;
		}

		socket.on('status', (status) => {
			if (status.is_scanning !== undefined) {
				$botRunning = status.is_scanning;
			}
		});

		socket.on('scan_started', () => {
			$botRunning = true;
		});
	}

	onMount(() => {
		checkBotStatus();
		setupSocketListeners();
		statusInterval = setInterval(checkBotStatus, 5000);
	});

	onDestroy(() => {
		if (statusInterval) {
			clearInterval(statusInterval);
		}
	});
</script>

<div class="stats-panel">
	<div class="stats-header">
		<div class="header-content">
			<h3>Session Statistics</h3>
			<button
				class="bot-control-btn"
				class:running={$botRunning}
				class:loading={$botLoading}
				on:click={toggleBot}
				disabled={$botLoading}
			>
				{#if $botLoading}
					⏳ Loading...
				{:else if $botRunning}
					⏸️ Stop Bot
				{:else}
					▶️ Start Bot
				{/if}
			</button>
		</div>
	</div>

	<div class="stats-grid">
		<div class="stat-box">
			<div class="stat-label">Total Trades</div>
			<div class="stat-value">{$stats.total_trades}</div>
		</div>

		<div class="stat-box wins">
			<div class="stat-label">Wins</div>
			<div class="stat-value">{$stats.wins}</div>
		</div>

		<div class="stat-box losses">
			<div class="stat-label">Losses</div>
			<div class="stat-value">{$stats.losses}</div>
		</div>

		<div class="stat-box winrate">
			<div class="stat-label">Winrate</div>
			<div class="stat-value">{$winrate}%</div>
		</div>

		<div class="stat-box">
			<div class="stat-label">W/L Ratio</div>
			<div class="stat-value">{$winLossRatio}</div>
		</div>

		<div class="stat-box pnl" class:positive={$stats.total_pnl_usdt >= 0} class:negative={$stats.total_pnl_usdt < 0}>
			<div class="stat-label">Total PnL</div>
			<div class="stat-value">
				{formatNumber($stats.total_pnl_usdt)} USDT
			</div>
			<div class="stat-subvalue">
				{formatNumber($stats.total_pnl_pct)}%
			</div>
		</div>


		{#if $stats.best_trade}
			<div class="stat-box best">
				<div class="stat-label">Best Trade</div>
				<div class="stat-value">+{formatNumber($stats.best_trade.pnl_usdt)} USDT</div>
				<div class="stat-subvalue">{$stats.best_trade.symbol}</div>
			</div>
		{/if}

		{#if $stats.worst_trade}
			<div class="stat-box worst">
				<div class="stat-label">Worst Trade</div>
				<div class="stat-value">{formatNumber($stats.worst_trade.pnl_usdt)} USDT</div>
				<div class="stat-subvalue">{$stats.worst_trade.symbol}</div>
			</div>
		{/if}
	</div>
</div>

<style>
	.stats-panel {
		background: #1e2749;
		border-radius: 12px;
		padding: 20px;
		border: 2px solid #2a3a6b;
	}

	.stats-header {
		margin-bottom: 20px;
	}

	.header-content {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 15px;
	}

	.stats-header h3 {
		font-size: 20px;
		color: #00ff88;
		font-weight: bold;
		margin: 0;
	}

	.bot-control-btn {
		padding: 10px 20px;
		border: 2px solid #2a3a6b;
		border-radius: 8px;
		font-size: 14px;
		font-weight: bold;
		cursor: pointer;
		transition: all 0.3s;
		background: #0a0e27;
		color: #fff;
		text-transform: uppercase;
		white-space: nowrap;
	}

	.bot-control-btn:not(.running):not(.loading) {
		border-color: #00ff88;
		color: #00ff88;
	}

	.bot-control-btn:not(.running):not(.loading):hover {
		background: rgba(0, 255, 136, 0.1);
		transform: translateY(-2px);
		box-shadow: 0 4px 15px rgba(0, 255, 136, 0.3);
	}

	.bot-control-btn.running {
		border-color: #ff4444;
		color: #ff4444;
		background: rgba(255, 68, 68, 0.1);
	}

	.bot-control-btn.running:hover {
		background: rgba(255, 68, 68, 0.2);
		transform: translateY(-2px);
		box-shadow: 0 4px 15px rgba(255, 68, 68, 0.3);
	}

	.bot-control-btn.loading {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.bot-control-btn:disabled {
		cursor: not-allowed;
	}

	.stats-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 15px;
	}

	.stat-box {
		background: #0a0e27;
		padding: 15px;
		border-radius: 10px;
		text-align: center;
		border: 2px solid #2a3a6b;
		transition: all 0.3s;
	}

	.stat-box:hover {
		transform: translateY(-2px);
		box-shadow: 0 4px 15px rgba(0, 255, 136, 0.2);
	}

	.stat-label {
		font-size: 11px;
		color: #888;
		margin-bottom: 8px;
		text-transform: uppercase;
		font-weight: bold;
	}

	.stat-value {
		font-size: 24px;
		font-weight: bold;
		color: #fff;
	}

	.stat-subvalue {
		font-size: 12px;
		color: #888;
		margin-top: 5px;
	}

	/* Specific styles */
	.stat-box.wins {
		border-color: #00ff88;
	}

	.stat-box.wins .stat-value {
		color: #00ff88;
	}

	.stat-box.losses {
		border-color: #ff4444;
	}

	.stat-box.losses .stat-value {
		color: #ff4444;
	}

	.stat-box.winrate {
		border-color: #00aaff;
	}

	.stat-box.winrate .stat-value {
		color: #00aaff;
	}

	.stat-box.pnl.positive {
		border-color: #00ff88;
	}

	.stat-box.pnl.positive .stat-value {
		color: #00ff88;
		text-shadow: 0 0 20px rgba(0, 255, 136, 0.5);
	}

	.stat-box.pnl.negative {
		border-color: #ff4444;
	}

	.stat-box.pnl.negative .stat-value {
		color: #ff4444;
		text-shadow: 0 0 20px rgba(255, 68, 68, 0.5);
	}

	.stat-box.best {
		border-color: #00ff88;
	}

	.stat-box.best .stat-value {
		color: #00ff88;
	}

	.stat-box.worst {
		border-color: #ff4444;
	}

	.stat-box.worst .stat-value {
		color: #ff4444;
	}

	/* Mobile responsive */
	@media (max-width: 768px) {
		.stats-grid {
			grid-template-columns: repeat(2, 1fr);
		}

		.stat-value {
			font-size: 20px;
		}
	}
</style>
