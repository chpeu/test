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

<div class="global-stats" data-debug-name="globalStats">
	<div class="stats-header" data-debug-name="statsHeader">
		<h3 data-debug-name="globalStatsTitle">🌍 Global Stats</h3>
	</div>

	<div class="stats-grid" data-debug-name="statsGrid">
		<div class="stat-card" data-debug-name="statCard.totalSessions">
			<div class="stat-icon" data-debug-name="statIcon.totalSessions">📂</div>
			<div class="stat-content" data-debug-name="statContent.totalSessions">
				<div class="stat-label" data-debug-name="statLabel.totalSessions">Total Sessions</div>
				<div class="stat-value" data-debug-name="globalStats.total_sessions">{$globalStats.total_sessions}</div>
			</div>
		</div>

		<div class="stat-card running" data-debug-name="statCard.running">
			<div class="stat-icon" data-debug-name="statIcon.running">🟢</div>
			<div class="stat-content" data-debug-name="statContent.running">
				<div class="stat-label" data-debug-name="statLabel.running">Running</div>
				<div class="stat-value" data-debug-name="globalStats.running_sessions">{$globalStats.running_sessions}</div>
			</div>
		</div>

		<div class="stat-card paused" data-debug-name="statCard.paused">
			<div class="stat-icon" data-debug-name="statIcon.paused">🟡</div>
			<div class="stat-content" data-debug-name="statContent.paused">
				<div class="stat-label" data-debug-name="statLabel.paused">Paused</div>
				<div class="stat-value" data-debug-name="globalStats.paused_sessions">{$globalStats.paused_sessions}</div>
			</div>
		</div>

		<div class="stat-card stopped" data-debug-name="statCard.stopped">
			<div class="stat-icon" data-debug-name="statIcon.stopped">⚫</div>
			<div class="stat-content" data-debug-name="statContent.stopped">
				<div class="stat-label" data-debug-name="statLabel.stopped">Stopped</div>
				<div class="stat-value" data-debug-name="globalStats.stopped_sessions">{$globalStats.stopped_sessions}</div>
			</div>
		</div>

		<div class="stat-card" data-debug-name="statCard.totalTrades">
			<div class="stat-icon" data-debug-name="statIcon.totalTrades">📊</div>
			<div class="stat-content" data-debug-name="statContent.totalTrades">
				<div class="stat-label" data-debug-name="statLabel.totalTrades">Total Trades</div>
				<div class="stat-value" data-debug-name="globalStats.total_trades">{$globalStats.total_trades}</div>
			</div>
		</div>

		<div class="stat-card" class:profit={$globalStats.total_pnl >= 0} class:loss={$globalStats.total_pnl < 0} data-debug-name="statCard.totalPnL">
			<div class="stat-icon" data-debug-name="statIcon.totalPnL">{$globalStats.total_pnl >= 0 ? '💰' : '📉'}</div>
			<div class="stat-content" data-debug-name="statContent.totalPnL">
				<div class="stat-label" data-debug-name="statLabel.totalPnL">Total PnL</div>
				<div class="stat-value" data-debug-name="globalStats.total_pnl">
					{$globalStats.total_pnl >= 0 ? '+' : ''}{formatUSDT($globalStats.total_pnl)} USDT
				</div>
				<div class="stat-secondary" data-debug-name="globalStats.total_pnl_percent">
					{$globalStats.total_pnl_percent >= 0 ? '+' : ''}{formatPercent($globalStats.total_pnl_percent)}%
				</div>
			</div>
		</div>

		<div class="stat-card" data-debug-name="statCard.totalWins">
			<div class="stat-icon" data-debug-name="statIcon.totalWins">🏆</div>
			<div class="stat-content" data-debug-name="statContent.totalWins">
				<div class="stat-label" data-debug-name="statLabel.totalWins">Wins</div>
				<div class="stat-value" data-debug-name="globalStats.total_wins">{$globalStats.total_wins}</div>
			</div>
		</div>

		<div class="stat-card" data-debug-name="statCard.totalLosses">
			<div class="stat-icon" data-debug-name="statIcon.totalLosses">❌</div>
			<div class="stat-content" data-debug-name="statContent.totalLosses">
				<div class="stat-label" data-debug-name="statLabel.totalLosses">Losses</div>
				<div class="stat-value" data-debug-name="globalStats.total_losses">{$globalStats.total_losses}</div>
			</div>
		</div>

		<div class="stat-card winrate" data-debug-name="statCard.winRate">
			<div class="stat-icon" data-debug-name="statIcon.winRate">📈</div>
			<div class="stat-content" data-debug-name="statContent.winRate">
				<div class="stat-label" data-debug-name="statLabel.winRate">Win Rate</div>
				<div class="stat-value" data-debug-name="globalStats.win_rate">{formatPercent($globalStats.win_rate)}%</div>
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
