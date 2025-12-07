<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { getWebSocket } from '$lib/utils/websocket';

	// Types
	interface RegimeStatus {
		current_regime: string;
		avg_atr: number;
		avg_adx: number;
		last_check: string | null;
		next_check: string | null;
		regime_since: string | null;
		config_active: Record<string, any>;
		atr_sample_count: number;
		check_interval_minutes: number;
	}

	// État
	let regimeData: RegimeStatus = {
		current_regime: 'UNKNOWN',
		avg_atr: 0,
		avg_adx: 0,
		last_check: null,
		next_check: null,
		regime_since: null,
		config_active: {},
		atr_sample_count: 0,
		check_interval_minutes: 60
	};
	
	let loading = false;
	let error: string | null = null;
	let refreshInterval: ReturnType<typeof setInterval>;

	// Couleurs par régime
	const REGIME_COLORS: Record<string, { bg: string; border: string; icon: string; text: string }> = {
		'CALME': { bg: 'rgba(16, 185, 129, 0.15)', border: '#10b981', icon: '🟢', text: '#10b981' },
		'NORMAL': { bg: 'rgba(59, 130, 246, 0.15)', border: '#3b82f6', icon: '🔵', text: '#3b82f6' },
		'VOLATILE': { bg: 'rgba(245, 158, 11, 0.15)', border: '#f59e0b', icon: '🟠', text: '#f59e0b' },
		'CHOPPY': { bg: 'rgba(239, 68, 68, 0.15)', border: '#ef4444', icon: '🔴', text: '#ef4444' },
		'UNKNOWN': { bg: 'rgba(107, 114, 128, 0.15)', border: '#6b7280', icon: '⚪', text: '#6b7280' }
	};

	$: colors = REGIME_COLORS[regimeData.current_regime] || REGIME_COLORS['UNKNOWN'];

	onMount(async () => {
		await loadRegimeStatus();
		
		// Refresh toutes les 60 secondes
		refreshInterval = setInterval(loadRegimeStatus, 60000);
		
		// WebSocket listener pour changements temps réel
		const ws = getWebSocket();
		if (ws) {
			ws.on('regime_changed', handleRegimeChange);
		}
	});

	onDestroy(() => {
		if (refreshInterval) clearInterval(refreshInterval);
	});

	async function loadRegimeStatus() {
		try {
			const res = await fetch('/api/regime/status');
			if (res.ok) {
				const data = await res.json();
				if (data.success) {
					regimeData = {
						current_regime: data.current_regime || 'UNKNOWN',
						avg_atr: data.avg_atr || 0,
						avg_adx: data.avg_adx || 0,
						last_check: data.last_check,
						next_check: data.next_check,
						regime_since: data.regime_since,
						config_active: data.config_active || {},
						atr_sample_count: data.atr_sample_count || 0,
						check_interval_minutes: data.check_interval_minutes || 60
					};
					error = null;
				}
			}
		} catch (e) {
			console.error('Erreur chargement régime:', e);
			error = 'Erreur connexion';
		}
	}

	async function forceCheck() {
		loading = true;
		error = null;
		try {
			const res = await fetch('/api/regime/force-check', { method: 'POST' });
			if (res.ok) {
				const data = await res.json();
				if (data.success) {
					regimeData = {
						current_regime: data.current_regime || 'UNKNOWN',
						avg_atr: data.avg_atr || 0,
						avg_adx: data.avg_adx || 0,
						last_check: data.last_check,
						next_check: data.next_check,
						regime_since: data.regime_since,
						config_active: data.config_active || {},
						atr_sample_count: data.atr_sample_count || 0,
						check_interval_minutes: data.check_interval_minutes || 60
					};
				}
			} else {
				error = 'Erreur vérification';
			}
		} catch (e) {
			console.error('Erreur force check:', e);
			error = 'Erreur réseau';
		} finally {
			loading = false;
		}
	}

	function handleRegimeChange(data: any) {
		if (data) {
			regimeData = { ...regimeData, ...data };
		}
	}

	function formatTime(isoString: string | null): string {
		if (!isoString) return '-';
		try {
			const date = new Date(isoString);
			return date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
		} catch {
			return '-';
		}
	}

	function formatDuration(isoString: string | null): string {
		if (!isoString) return '-';
		try {
			const since = new Date(isoString);
			const now = new Date();
			const diffMs = now.getTime() - since.getTime();
			const diffMin = Math.floor(diffMs / 60000);
			
			if (diffMin < 60) return `${diffMin}min`;
			const diffH = Math.floor(diffMin / 60);
			return `${diffH}h${diffMin % 60}min`;
		} catch {
			return '-';
		}
	}
</script>

<div 
	class="regime-widget" 
	style="background: {colors.bg}; border-color: {colors.border}"
>
	<div class="regime-header">
		<span class="regime-icon">{colors.icon}</span>
		<h4>Market Regime</h4>
		{#if error}
			<span class="error-badge" title={error}>⚠️</span>
		{/if}
	</div>
	
	<div class="regime-main">
		<span class="regime-name" style="color: {colors.text}">{regimeData.current_regime}</span>
		{#if regimeData.regime_since}
			<span class="regime-since">depuis {formatDuration(regimeData.regime_since)}</span>
		{/if}
	</div>
	
	<div class="regime-metrics">
		<div class="metric">
			<span class="label">ATR</span>
			<span class="value">{regimeData.avg_atr.toFixed(3)}%</span>
		</div>
		<div class="metric">
			<span class="label">ADX</span>
			<span class="value">{regimeData.avg_adx.toFixed(0)}</span>
		</div>
		<div class="metric">
			<span class="label">Samples</span>
			<span class="value">{regimeData.atr_sample_count}</span>
		</div>
	</div>
	
	{#if regimeData.config_active && Object.keys(regimeData.config_active).length > 0}
		<div class="config-preview">
			<span class="config-item" title="Score minimum requis">
				Score: {regimeData.config_active.min_score_required || '-'}
			</span>
			<span class="config-item" title="Multiplicateur SL">
				SL: {regimeData.config_active.atr_mult_sl || '-'}x
			</span>
		</div>
	{/if}
	
	<div class="regime-footer">
		<span class="last-check" title="Dernière vérification">
			MAJ: {formatTime(regimeData.last_check)}
		</span>
		<button 
			class="force-btn" 
			on:click={forceCheck} 
			disabled={loading}
			title="Forcer une vérification immédiate"
		>
			{loading ? '⏳' : '🔄'} Vérifier
		</button>
	</div>
</div>

<style>
	.regime-widget {
		border: 2px solid;
		border-radius: 10px;
		padding: 12px 15px;
		display: flex;
		flex-direction: column;
		gap: 10px;
		transition: all 0.3s ease;
	}

	.regime-header {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.regime-icon {
		font-size: 18px;
	}

	.regime-header h4 {
		margin: 0;
		font-size: 13px;
		color: #aaa;
		font-weight: 500;
		flex: 1;
	}

	.error-badge {
		font-size: 14px;
		cursor: help;
	}

	.regime-main {
		display: flex;
		align-items: baseline;
		gap: 10px;
	}

	.regime-name {
		font-size: 22px;
		font-weight: bold;
		letter-spacing: 1px;
	}

	.regime-since {
		font-size: 11px;
		color: #888;
	}

	.regime-metrics {
		display: flex;
		gap: 15px;
	}

	.metric {
		display: flex;
		flex-direction: column;
		gap: 2px;
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

	.config-preview {
		display: flex;
		gap: 12px;
		padding: 6px 10px;
		background: rgba(0, 0, 0, 0.2);
		border-radius: 6px;
	}

	.config-item {
		font-size: 11px;
		color: #aaa;
		cursor: help;
	}

	.regime-footer {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding-top: 8px;
		border-top: 1px solid rgba(255, 255, 255, 0.1);
	}

	.last-check {
		font-size: 11px;
		color: #666;
	}

	.force-btn {
		background: rgba(0, 255, 136, 0.15);
		border: 1px solid #00ff88;
		color: #00ff88;
		padding: 4px 10px;
		border-radius: 5px;
		font-size: 11px;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.force-btn:hover:not(:disabled) {
		background: rgba(0, 255, 136, 0.3);
	}

	.force-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
</style>
