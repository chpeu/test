<script>
	import { globalStats, loadGlobalStats } from '$lib/stores/sessions';
	import { onMount, onDestroy } from 'svelte';
	import { formatUSDT, formatPercent } from '$lib/utils/format';

	let interval;

	onMount(async () => {
		// Charger stats initiales
		loadGlobalStats();

		// 🔥 BIDIRECTIONNEL: Utiliser WebSocket pour mises à jour temps réel au lieu de polling REST
		const { getWebSocket } = await import('$lib/utils/websocket');
		const ws = getWebSocket();
		if (ws) {
			// Écouter les événements de mise à jour de sessions
			ws.on('sessions_update', () => {
				loadGlobalStats();
			});
			ws.on('session_started', () => {
				loadGlobalStats();
			});
			ws.on('session_stopped', () => {
				loadGlobalStats();
			});
		} else {
			// Fallback: Auto-refresh toutes les 10 secondes si WebSocket non disponible
			interval = setInterval(loadGlobalStats, 10000);
		}
	});

	onDestroy(() => {
		if (interval) clearInterval(interval);
	});
</script>

<div class="global-stats">
	<div class="stats-header">
		<h3>🌍 Global Stats</h3>
	</div>

	<div class="stats-grid">
		<div class="stat-card">
			<div class="stat-icon">📂</div>
			<div class="stat-content">
				<div class="stat-label">Total Sessions</div>
				<div class="stat-value">{$globalStats.total_sessions}</div>
			</div>
		</div>

		<div class="stat-card running">
			<div class="stat-icon">🟢</div>
			<div class="stat-content">
				<div class="stat-label">Running</div>
				<div class="stat-value">{$globalStats.running_sessions}</div>
			</div>
		</div>

		<div class="stat-card paused">
			<div class="stat-icon">🟡</div>
			<div class="stat-content">
				<div class="stat-label">Paused</div>
				<div class="stat-value">{$globalStats.paused_sessions}</div>
			</div>
		</div>

		<div class="stat-card stopped">
			<div class="stat-icon">⚫</div>
			<div class="stat-content">
				<div class="stat-label">Stopped</div>
				<div class="stat-value">{$globalStats.stopped_sessions}</div>
			</div>
		</div>

		<div class="stat-card">
			<div class="stat-icon">📊</div>
			<div class="stat-content">
				<div class="stat-label">Total Trades</div>
				<div class="stat-value">{$globalStats.total_trades}</div>
			</div>
		</div>

		<div class="stat-card" class:profit={$globalStats.total_pnl >= 0} class:loss={$globalStats.total_pnl < 0}>
			<div class="stat-icon">{$globalStats.total_pnl >= 0 ? '💰' : '📉'}</div>
			<div class="stat-content">
				<div class="stat-label">Total PnL</div>
				<div class="stat-value">
					{$globalStats.total_pnl >= 0 ? '+' : ''}{formatUSDT($globalStats.total_pnl)} USDT
				</div>
				<div class="stat-secondary">
					{$globalStats.total_pnl_percent >= 0 ? '+' : ''}{formatPercent($globalStats.total_pnl_percent)}%
				</div>
			</div>
		</div>

		<div class="stat-card">
			<div class="stat-icon">🏆</div>
			<div class="stat-content">
				<div class="stat-label">Wins</div>
				<div class="stat-value">{$globalStats.total_wins}</div>
			</div>
		</div>

		<div class="stat-card">
			<div class="stat-icon">❌</div>
			<div class="stat-content">
				<div class="stat-label">Losses</div>
				<div class="stat-value">{$globalStats.total_losses}</div>
			</div>
		</div>

		<div class="stat-card winrate">
			<div class="stat-icon">📈</div>
			<div class="stat-content">
				<div class="stat-label">Win Rate</div>
				<div class="stat-value">{formatPercent($globalStats.win_rate)}%</div>
			</div>
		</div>
	</div>
</div>

<style>
	.global-stats {
		background: var(--bg-secondary);
		border-radius: 12px;
		padding: 20px;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
	}

	.stats-header {
		margin-bottom: 16px;
		padding-bottom: 12px;
		border-bottom: 1px solid var(--bg-tertiary);
	}

	.stats-header h3 {
		font-size: 18px;
		color: var(--accent-blue);
		margin: 0;
	}

	.stats-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
		gap: 12px;
	}

	.stat-card {
		background: var(--bg-primary);
		border: 1px solid var(--bg-tertiary);
		border-radius: 8px;
		padding: 12px;
		display: flex;
		align-items: center;
		gap: 10px;
		transition: all 0.3s ease;
	}

	.stat-card:hover {
		border-color: var(--accent-green);
		transform: translateY(-2px);
	}

	.stat-card.running {
		border-color: var(--accent-green);
		background: rgba(0, 255, 136, 0.05);
	}

	.stat-card.paused {
		border-color: var(--accent-orange);
		background: rgba(255, 170, 0, 0.05);
	}

	.stat-card.stopped {
		border-color: var(--text-secondary);
		background: rgba(136, 136, 136, 0.05);
	}

	.stat-card.profit {
		border-color: var(--accent-green);
		background: rgba(0, 255, 136, 0.05);
	}

	.stat-card.loss {
		border-color: var(--accent-red);
		background: rgba(255, 68, 68, 0.05);
	}

	.stat-card.winrate {
		border-color: var(--accent-blue);
		background: rgba(0, 170, 255, 0.05);
	}

	.stat-icon {
		font-size: 24px;
		line-height: 1;
	}

	.stat-content {
		flex: 1;
		min-width: 0;
	}

	.stat-label {
		font-size: 11px;
		color: var(--text-secondary);
		text-transform: uppercase;
		letter-spacing: 0.5px;
		margin-bottom: 4px;
	}

	.stat-value {
		font-size: 16px;
		font-weight: 600;
		color: var(--text-primary);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.stat-secondary {
		font-size: 12px;
		color: var(--text-secondary);
		margin-top: 2px;
	}

	.stat-card.profit .stat-value {
		color: var(--accent-green);
	}

	.stat-card.loss .stat-value {
		color: var(--accent-red);
	}

	.stat-card.running .stat-value {
		color: var(--accent-green);
	}

	.stat-card.paused .stat-value {
		color: var(--accent-orange);
	}

	.stat-card.winrate .stat-value {
		color: var(--accent-blue);
	}

	@media (max-width: 768px) {
		.stats-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}

	@media (max-width: 480px) {
		.stats-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
