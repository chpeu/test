<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { getWebSocket } from '$lib/utils/websocket';

	// Types
	interface RegimeStatus {
		enabled: boolean;
		current_regime: string;
		avg_atr: number;
		avg_adx: number;
		last_check: string | null;
		next_check: string | null;
		regime_since: string | null;
		tp_sl_mode?: string;
		config_active: Record<string, any>;
		atr_sample_count: number;
		check_interval_minutes: number;
	}

	// État
	let regimeData: RegimeStatus = {
		enabled: true,
		current_regime: 'UNKNOWN',
		avg_atr: 0,
		avg_adx: 0,
		last_check: null,
		next_check: null,
		regime_since: null,
		tp_sl_mode: 'FIXE',
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
		'UNKNOWN': { bg: 'rgba(107, 114, 128, 0.15)', border: '#6b7280', icon: '⚪', text: '#6b7280' },
		'DISABLED': { bg: 'rgba(75, 85, 99, 0.15)', border: '#4b5563', icon: '⏸️', text: '#4b5563' }
	};

	// 🔥 FIX: Si désactivé, afficher couleur "DISABLED"
	$: colors = !regimeData.enabled 
		? REGIME_COLORS['DISABLED'] 
		: (REGIME_COLORS[regimeData.current_regime] || REGIME_COLORS['UNKNOWN']);

	$: isAtrMode = (regimeData.tp_sl_mode || 'FIXE') === 'ATR';

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
						enabled: data.enabled !== false,  // 🔥 FIX: Récupérer l'état enabled
						current_regime: data.current_regime || 'UNKNOWN',
						avg_atr: data.avg_atr || 0,
						avg_adx: data.avg_adx || 0,
						last_check: data.last_check,
						next_check: data.next_check,
						regime_since: data.regime_since,
						tp_sl_mode: data.tp_sl_mode || 'FIXE',
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
						enabled: data.enabled !== false,
						current_regime: data.current_regime || 'UNKNOWN',
						avg_atr: data.avg_atr || 0,
						avg_adx: data.avg_adx || 0,
						last_check: data.last_check,
						next_check: data.next_check,
						regime_since: data.regime_since,
						tp_sl_mode: data.tp_sl_mode || regimeData.tp_sl_mode || 'FIXE',
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
	class:disabled={!regimeData.enabled}
	style="background: {colors.bg}; border-color: {colors.border}"
>
	<div class="regime-header">
		<span class="regime-icon">{colors.icon}</span>
		<h4>Market Regime</h4>
		{#if !regimeData.enabled}
			<span class="disabled-badge">DÉSACTIVÉ</span>
		{:else if error}
			<span class="error-badge" title={error}>⚠️</span>
		{/if}
	</div>
	
	{#if regimeData.enabled}
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
				<!-- Ligne 1: Score & TP/SL -->
				<div class="config-row">
					<span class="config-item" title="Score minimum requis pour ouvrir un trade">
						📊 Score: {regimeData.config_active.min_score_required || '-'}
					</span>
					{#if isAtrMode}
						<span class="config-item" title="Multiplicateur ATR pour Stop Loss">
							🛑 SL: {regimeData.config_active.atr_mult_sl || '-'}x
						</span>
						<span class="config-item" title="Multiplicateur ATR pour Take Profit">
							🎯 TP: {regimeData.config_active.atr_mult_tp || '-'}x
						</span>
					{/if}
				</div>
				<!-- Ligne 2: Filtres dynamiques -->
				<div class="config-row">
					<span class="config-item" title="Multiplicateur volume (exigence de volume)">
						📊 Vol: {regimeData.config_active.volume_multiplier || '-'}x
					</span>
					{#if isAtrMode}
						<span class="config-item atr-max-disabled" title="ATR Max DÉSACTIVÉ si régime actif (données prouvent ATR haut = rentable)">
							📈 ATR Max: <span class="disabled-badge">OFF</span>
						</span>
						<span class="config-item" title="ATR 5m range optimal (ATR Min uniquement, Max désactivé)">
							📊 ATR5m: {regimeData.config_active.optimal_atr_min_5m?.toFixed(2) || '-'}%+
						</span>
					{/if}
				</div>
				<!-- Ligne 3: Timeout & Trailing -->
				<div class="config-row">
					<span class="config-item" title="Durée max position avant sortie stagnation">
						⏱️ Timeout: {regimeData.config_active.position_timeout ? Math.floor(regimeData.config_active.position_timeout / 60) + 'min' : '-'}
					</span>
					{#if isAtrMode}
						<span class="config-item" title="Break-Even trigger (multiplicateur ATR)">
							💰 BE: {regimeData.config_active.break_even_atr_mult || '-'}x
						</span>
						<span class="config-item" title="Trailing Stop trigger (multiplicateur ATR)">
							🔄 TS: {regimeData.config_active.trailing_trigger_atr_mult || '-'}x
						</span>
					{/if}
				</div>
				<!-- Ligne 4: RSI Thresholds -->
				<div class="config-row">
					<span class="config-item rsi-threshold" title="RSI max pour LONG (bloque si RSI > seuil)">
						📈 RSI Long Max: {regimeData.config_active.rsi_final_long_max || '65'}
					</span>
					<span class="config-item rsi-threshold" title="RSI min pour SHORT (bloque si RSI < seuil)">
						📉 RSI Short Min: {regimeData.config_active.rsi_final_short_min || '35'}
					</span>
				</div>
				<!-- Ligne 5: SL Exchange dynamique (filet de sécurité) -->
				{#if isAtrMode}
					<div class="config-row">
						<span class="config-item sl-exchange" title="Stop Loss MEXC dynamique = SL ATR × 1.1 (filet de sécurité si bot crash)">
							🛡️ SL MEXC: SL×1.1 (~{regimeData.config_active.atr_mult_sl ? (regimeData.config_active.atr_mult_sl * 1.1).toFixed(1) : '-'}x ATR)
						</span>
					</div>
				{/if}
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
	{:else}
		<div class="disabled-message">
			<p>La détection automatique du régime de marché est désactivée.</p>
			<p class="hint">Activez dans Protection & Régime → Market Regime Selector</p>
		</div>
	{/if}
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
		flex-direction: column;
		gap: 6px;
		padding: 8px 10px;
		background: rgba(0, 0, 0, 0.2);
		border-radius: 6px;
	}

	.config-row {
		display: flex;
		gap: 12px;
		flex-wrap: wrap;
	}

	.config-item {
		font-size: 11px;
		color: #aaa;
		cursor: help;
	}

	.config-item.sl-exchange {
		color: #ff9800;
		font-weight: 500;
		background: rgba(255, 152, 0, 0.1);
		padding: 2px 6px;
		border-radius: 4px;
	}

	.config-item.atr-max-disabled {
		color: #888;
	}

	.config-item.rsi-threshold {
		color: #a78bfa;
		font-weight: 500;
	}

	.disabled-badge {
		background: rgba(136, 136, 136, 0.3);
		color: #aaa;
		padding: 1px 5px;
		border-radius: 3px;
		font-size: 10px;
		font-weight: 600;
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

	/* 🔥 Styles pour état DÉSACTIVÉ */
	.regime-widget.disabled {
		opacity: 0.7;
	}

	.disabled-badge {
		background: rgba(239, 68, 68, 0.2);
		color: #ef4444;
		padding: 2px 8px;
		border-radius: 4px;
		font-size: 10px;
		font-weight: 600;
		text-transform: uppercase;
	}

	.disabled-message {
		padding: 15px 10px;
		text-align: center;
	}

	.disabled-message p {
		margin: 0 0 8px 0;
		font-size: 12px;
		color: #888;
	}

	.disabled-message .hint {
		font-size: 10px;
		color: #666;
		font-style: italic;
		margin: 0;
	}
</style>
