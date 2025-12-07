<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { getWebSocket } from '$lib/utils/websocket';

	// Types
	interface CBStatus {
		can_trade: boolean;
		state: string;
		consecutive_losses: number;
		daily_pnl_pct: number;
		daily_pnl_usdt: number;
		daily_trades: number;
		daily_wins: number;
		daily_losses: number;
		score_boost: number;
		paused_until: string | null;
		remaining_pause_seconds: number | null;
		pause_reason: string | null;
		thresholds: {
			max_consecutive_losses: number;
			daily_drawdown_pause_pct: number;
			daily_drawdown_stop_pct: number;
			pause_duration_minutes: number;
		};
	}

	// État
	let cbData: CBStatus = {
		can_trade: true,
		state: 'ACTIVE',
		consecutive_losses: 0,
		daily_pnl_pct: 0,
		daily_pnl_usdt: 0,
		daily_trades: 0,
		daily_wins: 0,
		daily_losses: 0,
		score_boost: 0,
		paused_until: null,
		remaining_pause_seconds: null,
		pause_reason: null,
		thresholds: {
			max_consecutive_losses: 5,
			daily_drawdown_pause_pct: -2.0,
			daily_drawdown_stop_pct: -5.0,
			pause_duration_minutes: 30
		}
	};

	let loading = false;
	let error: string | null = null;
	let refreshInterval: ReturnType<typeof setInterval>;
	let countdownInterval: ReturnType<typeof setInterval>;
	let remainingSeconds = 0;

	// Couleurs selon l'état
	$: statusColor = cbData.can_trade ? '#10b981' : '#ef4444';
	$: statusText = cbData.state === 'ACTIVE' ? 'ACTIF' : cbData.state === 'PAUSED' ? 'PAUSE' : 'ARRÊT';
	$: statusIcon = cbData.can_trade ? '✅' : cbData.state === 'PAUSED' ? '⏸️' : '🛑';

	// Niveaux d'alerte pour les losses
	$: lossLevel = cbData.consecutive_losses >= cbData.thresholds.max_consecutive_losses ? 'critical' 
		: cbData.consecutive_losses >= cbData.thresholds.max_consecutive_losses - 2 ? 'warning' 
		: 'normal';

	// Niveaux d'alerte pour le PnL
	$: pnlLevel = cbData.daily_pnl_pct <= cbData.thresholds.daily_drawdown_stop_pct ? 'critical'
		: cbData.daily_pnl_pct <= cbData.thresholds.daily_drawdown_pause_pct ? 'warning'
		: cbData.daily_pnl_pct > 0 ? 'positive'
		: 'normal';

	onMount(async () => {
		await loadCBStatus();
		
		// Refresh toutes les 10 secondes
		refreshInterval = setInterval(loadCBStatus, 10000);
		
		// Countdown pour la pause
		countdownInterval = setInterval(() => {
			if (remainingSeconds > 0) {
				remainingSeconds--;
			}
		}, 1000);
		
		// WebSocket listeners
		const ws = getWebSocket();
		if (ws) {
			ws.on('circuit_breaker_trading_update', handleCBUpdate);
			ws.on('circuit_breaker_trading_pause', handleCBPause);
			ws.on('circuit_breaker_trading_resume', handleCBResume);
		}
	});

	onDestroy(() => {
		if (refreshInterval) clearInterval(refreshInterval);
		if (countdownInterval) clearInterval(countdownInterval);
	});

	async function loadCBStatus() {
		try {
			const res = await fetch('/api/circuit-breaker/trading/status');
			if (res.ok) {
				const data = await res.json();
				if (data.success !== false) {
					cbData = {
						can_trade: data.can_trade ?? true,
						state: data.state || 'ACTIVE',
						consecutive_losses: data.consecutive_losses || 0,
						daily_pnl_pct: data.daily_pnl_pct || 0,
						daily_pnl_usdt: data.daily_pnl_usdt || 0,
						daily_trades: data.daily_trades || 0,
						daily_wins: data.daily_wins || 0,
						daily_losses: data.daily_losses || 0,
						score_boost: data.score_boost || 0,
						paused_until: data.paused_until,
						remaining_pause_seconds: data.remaining_pause_seconds,
						pause_reason: data.pause_reason,
						thresholds: data.thresholds || cbData.thresholds
					};
					
					// Mettre à jour le countdown
					if (data.remaining_pause_seconds && data.remaining_pause_seconds > 0) {
						remainingSeconds = data.remaining_pause_seconds;
					}
					
					error = null;
				}
			}
		} catch (e) {
			console.error('Erreur chargement CB status:', e);
			error = 'Erreur connexion';
		}
	}

	async function resetCB() {
		loading = true;
		error = null;
		try {
			const res = await fetch('/api/circuit-breaker/trading/reset', { method: 'POST' });
			if (res.ok) {
				const data = await res.json();
				if (data.success) {
					await loadCBStatus();
					remainingSeconds = 0;
				} else {
					error = data.error || 'Erreur reset';
				}
			} else {
				error = 'Erreur reset';
			}
		} catch (e) {
			console.error('Erreur reset CB:', e);
			error = 'Erreur réseau';
		} finally {
			loading = false;
		}
	}

	function handleCBUpdate(data: any) {
		if (data) {
			cbData = { ...cbData, ...data };
		}
	}

	function handleCBPause(data: any) {
		if (data) {
			cbData = { ...cbData, ...data, can_trade: false };
			if (data.remaining_pause_seconds) {
				remainingSeconds = data.remaining_pause_seconds;
			}
		}
	}

	function handleCBResume(data: any) {
		if (data) {
			cbData = { ...cbData, ...data, can_trade: true };
			remainingSeconds = 0;
		}
	}

	function formatCountdown(seconds: number): string {
		if (seconds <= 0) return '-';
		const min = Math.floor(seconds / 60);
		const sec = seconds % 60;
		return `${min}:${sec.toString().padStart(2, '0')}`;
	}
</script>

<div 
	class="cb-widget" 
	class:paused={!cbData.can_trade}
	style="border-color: {statusColor}"
>
	<div class="cb-header">
		<span class="cb-icon">🛑</span>
		<h4>Circuit Breaker</h4>
		<span 
			class="cb-status" 
			style="background: {statusColor}20; color: {statusColor}"
		>
			{statusIcon} {statusText}
		</span>
	</div>
	
	<div class="cb-metrics">
		<div class="metric" class:warning={lossLevel === 'warning'} class:critical={lossLevel === 'critical'}>
			<span class="label">Pertes consec.</span>
			<span class="value">
				{cbData.consecutive_losses}/{cbData.thresholds.max_consecutive_losses}
			</span>
		</div>
		
		<div 
			class="metric" 
			class:positive={pnlLevel === 'positive'}
			class:warning={pnlLevel === 'warning'} 
			class:critical={pnlLevel === 'critical'}
		>
			<span class="label">PnL Jour</span>
			<span class="value">
				{cbData.daily_pnl_pct > 0 ? '+' : ''}{cbData.daily_pnl_pct.toFixed(2)}%
			</span>
		</div>
		
		<div class="metric">
			<span class="label">Score+</span>
			<span class="value boost" class:active={cbData.score_boost > 0}>
				+{cbData.score_boost.toFixed(1)}
			</span>
		</div>
	</div>
	
	<div class="cb-stats">
		<span class="stat">
			Trades: <strong>{cbData.daily_trades}</strong>
		</span>
		<span class="stat win">
			W: <strong>{cbData.daily_wins}</strong>
		</span>
		<span class="stat loss">
			L: <strong>{cbData.daily_losses}</strong>
		</span>
	</div>
	
	{#if cbData.pause_reason || remainingSeconds > 0}
		<div class="pause-info">
			{#if cbData.pause_reason}
				<span class="pause-reason">⏸️ {cbData.pause_reason}</span>
			{/if}
			{#if remainingSeconds > 0}
				<span class="pause-countdown">
					Reprise dans: <strong>{formatCountdown(remainingSeconds)}</strong>
				</span>
			{/if}
		</div>
	{/if}
	
	<div class="cb-footer">
		{#if error}
			<span class="error-msg">⚠️ {error}</span>
		{:else}
			<span class="threshold-info" title="Seuils: pause à {cbData.thresholds.daily_drawdown_pause_pct}%, stop à {cbData.thresholds.daily_drawdown_stop_pct}%">
				DD pause: {cbData.thresholds.daily_drawdown_pause_pct}%
			</span>
		{/if}
		
		<button 
			class="reset-btn" 
			on:click={resetCB} 
			disabled={loading || (cbData.can_trade && cbData.consecutive_losses === 0)}
			title="Réinitialiser le circuit breaker"
		>
			{loading ? '⏳' : '🔄'} Reset
		</button>
	</div>
</div>

<style>
	.cb-widget {
		background: rgba(30, 39, 73, 0.8);
		border: 2px solid;
		border-radius: 10px;
		padding: 12px 15px;
		display: flex;
		flex-direction: column;
		gap: 10px;
		transition: all 0.3s ease;
	}

	.cb-widget.paused {
		animation: pulse-border 2s ease-in-out infinite;
	}

	@keyframes pulse-border {
		0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
		50% { box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.1); }
	}

	.cb-header {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.cb-icon {
		font-size: 18px;
	}

	.cb-header h4 {
		margin: 0;
		font-size: 13px;
		color: #aaa;
		font-weight: 500;
		flex: 1;
	}

	.cb-status {
		padding: 3px 8px;
		border-radius: 4px;
		font-size: 11px;
		font-weight: 600;
	}

	.cb-metrics {
		display: flex;
		gap: 15px;
	}

	.metric {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: 4px 8px;
		border-radius: 5px;
		background: rgba(0, 0, 0, 0.2);
	}

	.metric.warning {
		background: rgba(245, 158, 11, 0.2);
	}

	.metric.critical {
		background: rgba(239, 68, 68, 0.2);
	}

	.metric.positive {
		background: rgba(16, 185, 129, 0.2);
	}

	.metric .label {
		font-size: 10px;
		color: #666;
		text-transform: uppercase;
	}

	.metric .value {
		font-size: 14px;
		font-weight: 600;
		color: #fff;
		font-family: 'Courier New', monospace;
	}

	.metric.warning .value {
		color: #f59e0b;
	}

	.metric.critical .value {
		color: #ef4444;
	}

	.metric.positive .value {
		color: #10b981;
	}

	.value.boost.active {
		color: #f59e0b;
	}

	.cb-stats {
		display: flex;
		gap: 12px;
		font-size: 12px;
		color: #888;
	}

	.stat strong {
		color: #fff;
	}

	.stat.win strong {
		color: #10b981;
	}

	.stat.loss strong {
		color: #ef4444;
	}

	.pause-info {
		background: rgba(239, 68, 68, 0.15);
		border: 1px solid rgba(239, 68, 68, 0.3);
		border-radius: 6px;
		padding: 8px 10px;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.pause-reason {
		font-size: 12px;
		color: #ef4444;
	}

	.pause-countdown {
		font-size: 11px;
		color: #f59e0b;
	}

	.pause-countdown strong {
		font-family: 'Courier New', monospace;
		font-size: 13px;
	}

	.cb-footer {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding-top: 8px;
		border-top: 1px solid rgba(255, 255, 255, 0.1);
	}

	.threshold-info {
		font-size: 10px;
		color: #666;
		cursor: help;
	}

	.error-msg {
		font-size: 11px;
		color: #f59e0b;
	}

	.reset-btn {
		background: rgba(59, 130, 246, 0.15);
		border: 1px solid #3b82f6;
		color: #3b82f6;
		padding: 4px 10px;
		border-radius: 5px;
		font-size: 11px;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.reset-btn:hover:not(:disabled) {
		background: rgba(59, 130, 246, 0.3);
	}

	.reset-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
</style>
