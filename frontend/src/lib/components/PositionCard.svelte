<script>
	// 🔄 FORCE RELOAD: 2025-12-04T23:58:00 - Badge calibration fix
	import { activePosition, pnlColor, slDistance, tpDistance, positionDuration, clearPosition, updatePosition } from '$lib/stores/position';
	import { formatPrice, formatPercent, formatUSDT, getSignificantDecimals, formatWithoutTrailingZeros, formatTime } from '$lib/utils/format';
	import { sendCommandViaWS } from '$lib/utils/websocket';
	import { onMount, onDestroy } from 'svelte';

	// 🔥 FIX: Calculer le nombre de décimales significatives depuis entry
	// Exemple: entry=1.132200 → entryDecimals=4 (1.1322 a 4 décimales significatives)
	$: entryDecimals = $activePosition?.entry ? getSignificantDecimals($activePosition.entry) : 2;

	// 🔥 FIX: Récupérer la config pour afficher les bonnes informations TP/SL
	let tradingConfig = null;

	function normalizeEscalierLevels(rawLevels) {
		if (!rawLevels) return [];
		if (Array.isArray(rawLevels)) return rawLevels;
		if (typeof rawLevels === 'string') {
			try {
				return JSON.parse(rawLevels);
			} catch (err) {
				console.error('❌ Impossible de parser tp_escalier_levels', err, rawLevels);
				return [];
			}
		}
		return [];
	}
	
	async function loadConfig() {
		try {
			const { getWebSocket, sendRequestViaWS } = await import('$lib/utils/websocket');
			const ws = getWebSocket();
			if (ws && ws.connected) {
				const response = await sendRequestViaWS('state', {});
				const stateData = response?.data || response;
				if (stateData && stateData.config) {
					tradingConfig = stateData.config;
				}
			}
		} catch (err) {
			console.error('❌ Error loading config:', err);
		}
	}
	
	// 🔥 NOUVEAU: Compte à rebours dynamique de la durée
	let liveDuration = '';
	let durationInterval = null;
	let nowTs = Date.now();

	// 🔥 FIX BUG #6: Support jours pour positions > 24h
	function formatDurationFromSeconds(seconds) {
		if (!seconds || seconds < 0) return '0s';

		const days = Math.floor(seconds / 86400);
		const hours = Math.floor((seconds % 86400) / 3600);
		const minutes = Math.floor((seconds % 3600) / 60);
		const secs = seconds % 60;

		if (days > 0) return `${days}j ${hours}h ${minutes}m`;
		if (hours > 0) return `${hours}h ${minutes}m ${secs}s`;
		if (minutes > 0) return `${minutes}m ${secs}s`;
		return `${secs}s`;
	}

	function updateLiveDuration() {
		nowTs = Date.now();
		if (!$activePosition || !$activePosition.opened_at) {
			liveDuration = '';
			return;
		}
		
		const opened = new Date($activePosition.opened_at);
		const diffMs = nowTs - opened.getTime();
		const diffSec = Math.floor(diffMs / 1000);
		liveDuration = formatDurationFromSeconds(diffSec);
	}

	// Réactif: Mettre à jour la durée quand la position change
	$: if ($activePosition && $activePosition.opened_at) {
		updateLiveDuration();
		// Démarrer l'intervalle si pas déjà démarré
		if (!durationInterval) {
			durationInterval = setInterval(updateLiveDuration, 1000);
		}
	} else {
		// Arrêter l'intervalle si pas de position
		if (durationInterval) {
			clearInterval(durationInterval);
			durationInterval = null;
		}
		liveDuration = '';
	}

	onMount(() => {
		loadConfig();
	});

	onDestroy(() => {
		if (durationInterval) {
			clearInterval(durationInterval);
			durationInterval = null;
		}
	});
	
	// 🔥 FIX: Calculer les informations de la prochaine clôture
	$: nextTpInfo = (() => {
		if (!$activePosition || !tradingConfig) return null;
		
		const tpSlMode = tradingConfig.tp_sl_mode || $activePosition.tp_sl_mode || 'FIXE';
		
		// Mode TP_MULTI/ESCALIER
		if (tpSlMode === 'TP_MULTI' || tpSlMode === 'ESCALIER') {
			const levels = normalizeEscalierLevels($activePosition.tp_escalier_levels);
			const currentLevel = $activePosition.tp_escalier_current_level || 0;
			if (currentLevel < levels.length) {
				const nextLevel = levels[currentLevel];
				return {
					pnl: nextLevel.pnl || nextLevel.percent || 0,
					size: (nextLevel.size_pct || 0) * 100
				};
			}
			return null;
		}
		
		// Mode FIXE
		if (tpSlMode === 'FIXE') {
			// Avant le 1er TP : utiliser break_even_trigger
			if (!$activePosition.partial_tp_sold) {
				// 🔥 FIX: Vérifier si position trop petite pour TP partiel
				const forceFullTp = $activePosition.force_full_tp_for_partial;
				
				// Vérifier si TP partiel est configuré
				if (tradingConfig.partial_tp_percent && !forceFullTp) {
					// TP partiel pas encore vendu - utiliser break_even_trigger
					return {
						pnl: tradingConfig.break_even_trigger || 0.3,
						size: tradingConfig.partial_tp_percent || 50
					};
				} else {
					// Pas de TP partiel OU position trop petite → 100%
					return {
						pnl: tradingConfig.break_even_trigger || 0.3,
						size: 100
					};
				}
			}
			
			// Après le 1er TP : utiliser trailing_distance (dynamique en fonction du prix actuel)
			// Le trailing stop est actif, donc le prochain TP sera déclenché quand le trailing stop est touché
			// Le PnL objectif est calculé dynamiquement : PnL actuel - trailing_distance (car le trailing suit le prix)
			if ($activePosition.current_price && $activePosition.entry) {
				const currentPnL = $activePosition.direction === 'LONG' 
					? (($activePosition.current_price - $activePosition.entry) / $activePosition.entry) * 100
					: (($activePosition.entry - $activePosition.current_price) / $activePosition.entry) * 100;
				
				// Le trailing_distance est la distance entre le prix actuel et le trailing stop
				// Le prochain TP sera déclenché quand le prix revient au trailing stop
				// Donc le PnL objectif est le PnL actuel moins trailing_distance
				const trailingDistance = tradingConfig.trailing_distance || 0.1;
				const targetPnL = Math.max(0, currentPnL - trailingDistance);
				
				// Vérifier si position restante après TP partiel
				const remainingSize = $activePosition.size_remaining !== undefined && $activePosition.size_remaining !== null
					? ($activePosition.size_remaining / $activePosition.size) * 100
					: 100;
				
				return {
					pnl: targetPnL,
					size: remainingSize
				};
			}
			
			// Fallback si pas de prix actuel
			return {
				pnl: tradingConfig.trailing_distance || 0.1,
				size: $activePosition.size_remaining !== undefined && $activePosition.size_remaining !== null
					? ($activePosition.size_remaining / $activePosition.size) * 100
					: 100
			};
		}
		
		// Mode ATR : utiliser les valeurs ATR dynamiques
		if (tpSlMode === 'ATR') {
			// 🔥 En mode ATR, le TP est basé sur break_even_atr_mult pour le premier TP
			// puis sur le trailing stop dynamique
			const breakEvenAtrMult = tradingConfig.break_even_atr_mult || 0.5;
			const atrPercent = $activePosition.atr_percent || tradingConfig.atr_min || 0.10;
			
			if (!$activePosition.partial_tp_sold && tradingConfig.partial_tp_percent) {
				// TP partiel pas encore vendu - utiliser break_even basé sur ATR
				return {
					pnl: atrPercent * breakEvenAtrMult,
					size: tradingConfig.partial_tp_percent || 60
				};
			}
			
			// Trailing actif après TP partiel
			return {
				pnl: atrPercent * (tradingConfig.trailing_trigger_atr_mult || 1.0),
				size: 100
			};
		}
		
		// Autres modes : utiliser tp_percent standard
		if (!$activePosition.partial_tp_sold && tradingConfig.partial_tp_percent) {
			return {
				pnl: tradingConfig.tp_percent || 0.6,
				size: tradingConfig.partial_tp_percent || 50
			};
		}
		
		return {
			pnl: tradingConfig.tp_percent || 0.6,
			size: 100
		};
	})();
	
	$: nextSlInfo = (() => {
		if (!$activePosition || !tradingConfig) return null;
		
		const tpSlMode = tradingConfig.tp_sl_mode || $activePosition.tp_sl_mode || 'FIXE';
		
		// Mode ATR : SL basé sur ATR
		if (tpSlMode === 'ATR') {
			const atrMultSl = tradingConfig.atr_mult_sl || 1.2;
			const atrPercent = $activePosition.atr_percent || tradingConfig.atr_min || 0.10;
			return {
				pnl: atrPercent * atrMultSl,
				size: 100
			};
		}
		
		// Mode FIXE ou autre
		return {
			pnl: tradingConfig.sl_percent || 0.25,
			size: 100
		};
	})();
	
	// 🔥 FIX: Fonction helper pour formater avec précision basée sur entry
	// Tous les prix (current, TP, SL) utilisent le même nombre de décimales que entry
	// Les zéros superflus à la fin sont supprimés
	// Exemple: Si entry=1.132200 (4 décimales significatives: 1.1322)
	//          Alors current=1.128000 sera affiché comme 1.128 (4 décimales max, sans zéros de fin)
	function formatPriceWithPrecision(price) {
		if (!price || isNaN(price)) {
			return '0.00';
		}

		// Utiliser le nombre de décimales significatives de entry
		// Mais avec un minimum de 2 et maximum de 8 pour la lisibilité
		const decimals = Math.max(2, Math.min(8, entryDecimals));

		// Formater sans les zéros de fin
		return formatWithoutTrailingZeros(price, decimals);
	}

	function formatContracts(value) {
		if (value === null || value === undefined || isNaN(value)) {
			return '-';
		}
		// 🔥 FIX: Pour les gros nombres (>10000), pas de décimales. Sinon 4 max.
		if (Math.abs(value) >= 10000) {
			return Math.round(value).toLocaleString('fr-FR');
		}
		return formatWithoutTrailingZeros(value, 4);
	}

	// 🔥 FIX: Fonction pour clôturer la position manuellement
	async function closePosition() {
		if (!$activePosition) {
			alert('❌ Aucune position active à clôturer');
			return;
		}

		if (!confirm('Êtes-vous sûr de vouloir clôturer cette position manuellement ?')) {
			return;
		}

		// 🔥 FIX: Récupérer le prix actuel avant de clôturer
		let exitPrice = $activePosition.current_price;
		if (!exitPrice || exitPrice <= 0) {
			// Si pas de prix, utiliser le prix d'entrée comme fallback
			exitPrice = $activePosition.entry;
		}

		// 🔥 FIX: Mise à jour optimiste immédiate pour feedback instantané
		clearPosition();

		try {
			// 🔥 MIGRATION COMPLÈTE: Utiliser WebSocket natif uniquement
			const result = await sendCommandViaWS('close_position', {
				reason: 'MANUAL',
				exit_price: exitPrice
			});
			
			if (result && result.status === 'closed') {
				console.log('✅ Position fermée via WebSocket:', result.result);
			} else {
				console.log('✅ Position fermée via WebSocket');
			}
		} catch (err) {
			console.error('❌ Error closing position via WebSocket:', err);
			alert(`❌ Erreur: ${err.message || 'Impossible de clôturer la position. Vérifiez la connexion WebSocket.'}`);
		}
	}

	function clamp(value, min = 0, max = 100) {
		return Math.min(max, Math.max(min, value));
	}

	function safePct(value) {
		if (value === null || value === undefined || isNaN(value)) {
			return null;
		}
		return clamp(value);
	}

	$: lastUpdateAgeSec = $activePosition?.last_update_at
		? (nowTs - new Date($activePosition.last_update_at).getTime()) / 1000
		: null;
	$: positionIsStale = lastUpdateAgeSec !== null && lastUpdateAgeSec > 6;

	$: beTriggerPct = $activePosition?.break_even_trigger_pct ?? null;
	$: trailingTriggerPct = $activePosition?.trailing_trigger_pct ?? null;
	$: trailingMfeTriggerPct = $activePosition?.trailing_mfe_enabled
		? ($activePosition?.trailing_mfe_trigger_pct ?? null)
		: null;

	$: pnlScaleMax = (() => {
		const values = [];
		if (beTriggerPct !== null && beTriggerPct !== undefined) values.push(beTriggerPct);
		if (trailingTriggerPct !== null && trailingTriggerPct !== undefined) values.push(trailingTriggerPct);
		if (trailingMfeTriggerPct !== null && trailingMfeTriggerPct !== undefined) values.push(trailingMfeTriggerPct);
		if (nextTpInfo && nextTpInfo.pnl !== null && nextTpInfo.pnl !== undefined) values.push(nextTpInfo.pnl);
		return values.length ? Math.max(...values) : null;
	})();

	$: pnlProgressPct = pnlScaleMax && pnlScaleMax > 0 && $activePosition?.pnl !== null && $activePosition?.pnl !== undefined
		? safePct(($activePosition.pnl / pnlScaleMax) * 100)
		: null;
	$: beMarkerPos = pnlScaleMax && pnlScaleMax > 0 && beTriggerPct !== null && beTriggerPct !== undefined
		? safePct((beTriggerPct / pnlScaleMax) * 100)
		: null;
	$: trailingMarkerPos = pnlScaleMax && pnlScaleMax > 0 && trailingTriggerPct !== null && trailingTriggerPct !== undefined
		? safePct((trailingTriggerPct / pnlScaleMax) * 100)
		: null;
	$: trailingMfeMarkerPos = pnlScaleMax && pnlScaleMax > 0 && trailingMfeTriggerPct !== null && trailingMfeTriggerPct !== undefined
		? safePct((trailingMfeTriggerPct / pnlScaleMax) * 100)
		: null;

	$: openedAgeSec = $activePosition?.opened_at
		? (nowTs - new Date($activePosition.opened_at).getTime()) / 1000
		: null;
	$: stagnationTimeoutSec = $activePosition?.stagnation_timeout_seconds_effective ?? null;
	$: stagnationPositiveTimeoutSec = $activePosition?.stagnation_positive_timeout_seconds_effective ?? null;
	$: stagnationEffectiveTimeoutSec = (() => {
		const values = [];
		if (stagnationTimeoutSec !== null && stagnationTimeoutSec !== undefined) values.push(stagnationTimeoutSec);
		if (stagnationPositiveTimeoutSec !== null && stagnationPositiveTimeoutSec !== undefined) values.push(stagnationPositiveTimeoutSec);
		return values.length ? Math.min(...values) : null;
	})();
	$: stagnationEffectiveProgressPct = stagnationEffectiveTimeoutSec && stagnationEffectiveTimeoutSec > 0 && openedAgeSec !== null && openedAgeSec !== undefined
		? safePct((openedAgeSec / stagnationEffectiveTimeoutSec) * 100)
		: null;
	$: stagnationTimeLeftSec = stagnationEffectiveTimeoutSec && openedAgeSec !== null && openedAgeSec !== undefined
		? Math.max(0, stagnationEffectiveTimeoutSec - openedAgeSec)
		: null;
</script>

{#if $activePosition}
	<div class="position-card" data-debug-name="activePosition">
		<div class="position-header">
			<div class="symbol" data-debug-name="activePosition.symbol">{$activePosition.symbol}</div>
			
			<!-- 🔥 ML & Sizing Badges -->
			<div class="ml-sizing-badges">
				{#if $activePosition.ml_confidence !== undefined && $activePosition.ml_confidence !== null && $activePosition.ml_confidence > 0}
					<div class="badge ml-badge" title="Confiance ML au moment de l'ouverture">
						🧠 {$activePosition.ml_confidence.toFixed(1)}%
					</div>
				{/if}
				{#if $activePosition.ml_calibrated_winrate !== undefined && $activePosition.ml_calibrated_winrate !== null}
					<div class="badge calib-badge" title="WinRate réel recalibré pour ce bucket">
						⚖️ {$activePosition.ml_calibrated_winrate.toFixed(1)}%
					</div>
				{/if}
				{#if $activePosition.adaptive_sizing_multiplier !== undefined && $activePosition.adaptive_sizing_multiplier !== null && $activePosition.adaptive_sizing_multiplier !== 1.0}
					<div class="badge sizing-badge" class:boost={$activePosition.adaptive_sizing_multiplier > 1} class:reduce={$activePosition.adaptive_sizing_multiplier < 1} title="Multiplicateur sizing adaptatif">
						📊 x{$activePosition.adaptive_sizing_multiplier.toFixed(2)}
					</div>
				{/if}
				
				<!-- 🔥 FIX: Afficher levier avec fallback dynamique depuis config -->
				<div class="badge leverage-badge" title="Levier utilisé pour cette position">
					⚡ {$activePosition.leverage_used || tradingConfig?.default_leverage || 1}x
				</div>
			</div>
			
			<div class="header-right">
				<div class="direction" class:long={$activePosition.direction === 'LONG'} class:short={$activePosition.direction === 'SHORT'} data-debug-name="activePosition.direction">
					{$activePosition.direction}
				</div>
				{#if $activePosition.tp_sl_mode}
					<div class="tp-sl-mode" data-debug-name="activePosition.tp_sl_mode">
						Mode: {$activePosition.tp_sl_mode}
					</div>
				{/if}
				{#if $activePosition.last_update_at}
					<div class="live-badge" class:stale={positionIsStale}>
						Live: {lastUpdateAgeSec !== null ? lastUpdateAgeSec.toFixed(1) + 's' : '-'}
					</div>
				{/if}
			</div>
		</div>

		<div class="pnl-section">
			<div class="pnl-value" style="color: {$pnlColor}" data-debug-name="activePosition.pnl">
				{formatPercent($activePosition.pnl)}%
			</div>
			<div class="pnl-usdt" style="color: {$pnlColor}" data-debug-name="activePosition.pnl_usdt">
				{formatUSDT($activePosition.pnl_usdt)} USDT
			</div>
		</div>

		<div class="price-grid">
			<div class="price-box" data-debug-name="activePosition.entry">
				<div class="price-label" data-debug-name="activePosition.entry">Entry</div>
				<div class="price-value" data-debug-name="activePosition.entry">{formatPriceWithPrecision($activePosition.entry)}</div>
			</div>
			<div class="price-box" data-debug-name="activePosition.current_price">
				<div class="price-label" data-debug-name="activePosition.current_price">Current</div>
				<div class="price-value" data-debug-name="activePosition.current_price">{formatPriceWithPrecision($activePosition.current_price)}</div>
			</div>
			<div class="price-box" data-debug-name="activePosition.size">
				<div class="price-label" data-debug-name="activePosition.size">Size</div>
				<div class="price-value" data-debug-name="activePosition.size">{formatPrice($activePosition.size)} USDT</div>
				{#if $activePosition.size_initial_contracts}
					<div class="price-subvalue" data-debug-name="activePosition.size_contracts">
						{#if $activePosition.size_remaining_contracts && Math.abs($activePosition.size_remaining_contracts - $activePosition.size_initial_contracts) > 1}
							{formatContracts($activePosition.size_remaining_contracts)} / {formatContracts($activePosition.size_initial_contracts)}
						{:else}
							{formatContracts($activePosition.size_initial_contracts)}
						{/if}
					</div>
				{/if}
			</div>
		</div>

		<!-- 🔥 NOUVEAU: Sections Prochain TP et Prochain SL distinctes -->
		{#if $activePosition.next_event || $activePosition}
			<!-- Section Prochain Take Profit -->
			<div class="next-event-section tp-section">
				<div class="next-event-header">
					<span class="next-event-label">💰 Prochain TP</span>
					<span class="next-event-type" style="color: {$activePosition.next_event?.color || '#10b981'}">
						{$activePosition.next_event?.description || 'TP 1/3'}
					</span>
				</div>
				<div class="next-event-details">
					{#if $activePosition.next_event?.price}
						<div class="next-event-price">
							À {formatPrice($activePosition.next_event.price)}
						</div>
					{:else}
						<div class="next-event-price">
							À {formatPrice($activePosition.tp || 98980)}
						</div>
					{/if}
					<div class="next-event-distance">
						{formatPercent($activePosition.next_event?.distance_pct || 0.40)}%
						{#if $activePosition.next_event?.distance_atr !== null}
							({$activePosition.next_event.distance_atr.toFixed(2)} ATR)
						{:else}
							(0.50 ATR)
						{/if}
					</div>
				</div>
				<!-- Barre de progression TP -->
				<div class="next-event-progress">
					<div class="next-event-progress-bar tp-bar" style="width: {Math.max(0, Math.min(100, 100 - Math.abs($activePosition.next_event?.distance_pct || 0.40)))}%"></div>
				</div>
			</div>

			<!-- Section Stop Loss (protection) -->
			<div class="next-event-section sl-section">
				<div class="next-event-header">
					<span class="next-event-label">🛡️ Stop Loss</span>
					<span class="next-event-type" style="color: #ef4444">
						Protection
					</span>
				</div>
				<div class="next-event-details">
					<div class="next-event-price">
						À {formatPrice($activePosition.sl || 96530)}
					</div>
					<div class="next-event-distance">
						{formatPercent($activePosition.next_sl?.distance_pct || -2.15)}%
						({($activePosition.next_sl?.distance_atr || 2.69).toFixed(2)} ATR)
					</div>
				</div>
				<!-- Barre de progression SL (inverse) -->
				<div class="next-event-progress">
					<div class="next-event-progress-bar sl-bar" style="width: {Math.max(0, Math.min(100, 100 - Math.abs(($activePosition.next_sl?.distance_pct || -2.15) * -0.4)))}%"></div>
				</div>
			</div>
		{/if}

		<div class="tpsl-grid">
			<div class="tpsl-box tp" data-debug-name="activePosition.tp">
				<div class="tpsl-label" data-debug-name="activePosition.tp">Prochain Take Profit</div>
				<div class="tpsl-price" data-debug-name="activePosition.tp">{formatPriceWithPrecision($activePosition.tp)}</div>
				{#if nextTpInfo}
					<div class="tpsl-info">
						<div class="tpsl-pnl" data-debug-name="nextTpInfo.pnl">PnL objectif: <span class="tpsl-value" data-debug-name="nextTpInfo.pnl">+{formatPercent(nextTpInfo.pnl)}%</span></div>
						<div class="tpsl-size" data-debug-name="nextTpInfo.size">
							Taille: <span class="tpsl-value" data-debug-name="nextTpInfo.size">{nextTpInfo.size}% de la position</span>
							{#if $activePosition.force_full_tp_for_partial && nextTpInfo.size === 100}
								<span class="force-full-tp-badge" title="Position trop petite pour TP partiel">(min. atteint)</span>
							{/if}
						</div>
					</div>
				{:else if $tpDistance}
					<div class="tpsl-distance" data-debug-name="tpDistance">+{$tpDistance}%</div>
				{/if}
			</div>
			<div class="tpsl-box sl" data-debug-name="activePosition.sl">
				<div class="tpsl-label" data-debug-name="activePosition.sl">Prochain Stop Loss</div>
				<div class="tpsl-price" data-debug-name="activePosition.sl">{formatPriceWithPrecision($activePosition.sl)}</div>
				{#if nextSlInfo}
					<div class="tpsl-info">
						<div class="tpsl-pnl" data-debug-name="nextSlInfo.pnl">PnL stop: <span class="tpsl-value" data-debug-name="nextSlInfo.pnl">-{formatPercent(nextSlInfo.pnl)}%</span></div>
						<div class="tpsl-size" data-debug-name="nextSlInfo.size">Taille: <span class="tpsl-value" data-debug-name="nextSlInfo.size">{nextSlInfo.size}% de la position restante</span></div>
					</div>
				{:else if $slDistance}
					<div class="tpsl-distance" data-debug-name="slDistance">{$slDistance}%</div>
				{/if}
				{#if $activePosition.dynamic_sl}
					<div class="trailing-stop" data-debug-name="activePosition.dynamic_sl">
						Trailing: {formatPriceWithPrecision($activePosition.dynamic_sl)}
					</div>
				{/if}
			</div>
		</div>

		<div class="telemetry-grid">
			<div class="telemetry-box">
				<div class="telemetry-title">Live</div>
				<div class="telemetry-row">
					<span class="telemetry-label">Dernière maj</span>
					<span class="telemetry-value" class:stale-text={positionIsStale}>
						{lastUpdateAgeSec !== null ? lastUpdateAgeSec.toFixed(1) + 's' : '-'}
					</span>
				</div>
				<div class="telemetry-row">
					<span class="telemetry-label">Opened</span>
					<span class="telemetry-value">{formatTime($activePosition.opened_at)}</span>
				</div>
				{#if $activePosition.partial_tp_sold !== undefined}
					<div class="telemetry-row">
						<span class="telemetry-label">TP partiel</span>
						<span class="telemetry-value">
							{$activePosition.partial_tp_sold ? 'oui' : 'non'}
							{#if $activePosition.partial_tp_percent !== null && $activePosition.partial_tp_percent !== undefined}
								({formatPercent($activePosition.partial_tp_percent)}%)
							{/if}
						</span>
					</div>
				{/if}
				{#if $activePosition.partial_profit_usdt !== null && $activePosition.partial_profit_usdt !== undefined}
					<div class="telemetry-row">
						<span class="telemetry-label">Profit partiel</span>
						<span class="telemetry-value">{formatUSDT($activePosition.partial_profit_usdt)} USDT</span>
					</div>
				{/if}
				{#if $activePosition.tp_escalier_enabled}
					<div class="telemetry-row">
						<span class="telemetry-label">Escalier lvl</span>
						<span class="telemetry-value">{$activePosition.tp_escalier_current_level ?? '-'}</span>
					</div>
				{/if}
			</div>

			<div class="telemetry-box">
				<div class="telemetry-title">ATR / Seuils</div>
				<div class="telemetry-row">
					<span class="telemetry-label">ATR%</span>
					<span class="telemetry-value">
						{$activePosition.atr_percent !== null && $activePosition.atr_percent !== undefined ? formatPercent($activePosition.atr_percent) + '%' : '-'}
					</span>
				</div>
				<div class="telemetry-row">
					<span class="telemetry-label">BE trig</span>
					<span class="telemetry-value">{beTriggerPct !== null && beTriggerPct !== undefined ? formatPercent(beTriggerPct) + '%' : '-'}</span>
				</div>
				<div class="telemetry-row">
					<span class="telemetry-label">TR trig</span>
					<span class="telemetry-value">{trailingTriggerPct !== null && trailingTriggerPct !== undefined ? formatPercent(trailingTriggerPct) + '%' : '-'}</span>
				</div>
				<div class="telemetry-row">
					<span class="telemetry-label">TR dist</span>
					<span class="telemetry-value">
						{$activePosition.trailing_distance_pct_effective !== null && $activePosition.trailing_distance_pct_effective !== undefined ? formatPercent($activePosition.trailing_distance_pct_effective) + '%' : '-'}
					</span>
				</div>
				{#if $activePosition.break_even_atr_mult_effective !== null && $activePosition.break_even_atr_mult_effective !== undefined}
					<div class="telemetry-row">
						<span class="telemetry-label">BE mult</span>
						<span class="telemetry-value">x{formatWithoutTrailingZeros($activePosition.break_even_atr_mult_effective, 2)}</span>
					</div>
				{/if}
				{#if $activePosition.trailing_trigger_atr_mult_effective !== null && $activePosition.trailing_trigger_atr_mult_effective !== undefined}
					<div class="telemetry-row">
						<span class="telemetry-label">TR mult</span>
						<span class="telemetry-value">x{formatWithoutTrailingZeros($activePosition.trailing_trigger_atr_mult_effective, 2)}</span>
					</div>
				{/if}
				{#if $activePosition.trailing_distance_mult_effective !== null && $activePosition.trailing_distance_mult_effective !== undefined}
					<div class="telemetry-row">
						<span class="telemetry-label">Dist mult</span>
						<span class="telemetry-value">x{formatWithoutTrailingZeros($activePosition.trailing_distance_mult_effective, 2)}</span>
					</div>
				{/if}

				{#if pnlScaleMax !== null && pnlProgressPct !== null}
					<div class="telemetry-progress">
						<div class="telemetry-progress-bar">
							<div class="telemetry-progress-fill" style="width: {pnlProgressPct}%"></div>
							{#if beMarkerPos !== null}
								<div class="telemetry-marker be" style="left: {beMarkerPos}%"></div>
							{/if}
							{#if trailingMarkerPos !== null}
								<div class="telemetry-marker trailing" style="left: {trailingMarkerPos}%"></div>
							{/if}
							{#if trailingMfeMarkerPos !== null}
								<div class="telemetry-marker mfe" style="left: {trailingMfeMarkerPos}%"></div>
							{/if}
						</div>
						<div class="telemetry-progress-legend">
							<span>0%</span>
							<span>{formatPercent(pnlScaleMax)}%</span>
						</div>
					</div>
				{/if}
			</div>

			<div class="telemetry-box">
				<div class="telemetry-title">BE / Trailing</div>
				<div class="telemetry-row">
					<span class="telemetry-label">BE set</span>
					<span class="telemetry-value">{$activePosition.break_even_set ? 'oui' : 'non'}</span>
				</div>
				{#if $activePosition.break_even_triggered_at}
					<div class="telemetry-row">
						<span class="telemetry-label">BE at</span>
						<span class="telemetry-value">{formatTime($activePosition.break_even_triggered_at)}</span>
					</div>
				{/if}
				{#if $activePosition.break_even_price !== null && $activePosition.break_even_price !== undefined}
					<div class="telemetry-row">
						<span class="telemetry-label">BE price</span>
						<span class="telemetry-value">{formatPriceWithPrecision($activePosition.break_even_price)}</span>
					</div>
				{/if}
				{#if $activePosition.break_even_pnl_pct !== null && $activePosition.break_even_pnl_pct !== undefined}
					<div class="telemetry-row">
						<span class="telemetry-label">BE pnl</span>
						<span class="telemetry-value">+{formatPercent($activePosition.break_even_pnl_pct)}%</span>
					</div>
				{/if}

				<div class="telemetry-row">
					<span class="telemetry-label">Trailing</span>
					<span class="telemetry-value">{$activePosition.trailing_activated ? 'oui' : 'non'}</span>
				</div>
				{#if $activePosition.trailing_activated_at}
					<div class="telemetry-row">
						<span class="telemetry-label">TR at</span>
						<span class="telemetry-value">{formatTime($activePosition.trailing_activated_at)}</span>
					</div>
				{/if}
				{#if $activePosition.trailing_final_sl !== null && $activePosition.trailing_final_sl !== undefined}
					<div class="telemetry-row">
						<span class="telemetry-label">Final SL</span>
						<span class="telemetry-value">{formatPriceWithPrecision($activePosition.trailing_final_sl)}</span>
					</div>
				{/if}
				{#if $activePosition.dynamic_sl !== null && $activePosition.dynamic_sl !== undefined}
					<div class="telemetry-row">
						<span class="telemetry-label">Dyn SL</span>
						<span class="telemetry-value">{formatPriceWithPrecision($activePosition.dynamic_sl)}</span>
					</div>
				{/if}

				{#if $activePosition.trailing_mfe_enabled}
					<div class="telemetry-row">
						<span class="telemetry-label">MFE trig</span>
						<span class="telemetry-value">{$activePosition.trailing_mfe_triggered ? 'oui' : 'non'}</span>
					</div>
					{#if $activePosition.trailing_mfe_triggered_at}
						<div class="telemetry-row">
							<span class="telemetry-label">MFE at</span>
							<span class="telemetry-value">{formatTime($activePosition.trailing_mfe_triggered_at)}</span>
						</div>
					{/if}
					{#if $activePosition.trailing_mfe_trigger_pnl_pct !== null && $activePosition.trailing_mfe_trigger_pnl_pct !== undefined}
						<div class="telemetry-row">
							<span class="telemetry-label">MFE pnl</span>
							<span class="telemetry-value">+{formatPercent($activePosition.trailing_mfe_trigger_pnl_pct)}%</span>
						</div>
					{/if}
				{/if}
			</div>

			<div class="telemetry-box">
				<div class="telemetry-title">MFE / Stagnation</div>
				{#if $activePosition.max_pnl_reached !== null && $activePosition.max_pnl_reached !== undefined}
					<div class="telemetry-row">
						<span class="telemetry-label">Max PnL</span>
						<span class="telemetry-value">
							+{formatPercent($activePosition.max_pnl_reached)}%
							{#if $activePosition.max_pnl_timestamp}({formatTime($activePosition.max_pnl_timestamp)}){/if}
						</span>
					</div>
				{/if}
				{#if $activePosition.min_pnl_reached !== null && $activePosition.min_pnl_reached !== undefined}
					<div class="telemetry-row">
						<span class="telemetry-label">Min PnL</span>
						<span class="telemetry-value">
							{formatPercent($activePosition.min_pnl_reached)}%
							{#if $activePosition.min_pnl_timestamp}({formatTime($activePosition.min_pnl_timestamp)}){/if}
						</span>
					</div>
				{/if}
				{#if $activePosition.max_price_reached !== null && $activePosition.max_price_reached !== undefined}
					<div class="telemetry-row">
						<span class="telemetry-label">Max px</span>
						<span class="telemetry-value">{formatPriceWithPrecision($activePosition.max_price_reached)}</span>
					</div>
				{/if}
				{#if $activePosition.min_price_reached !== null && $activePosition.min_price_reached !== undefined}
					<div class="telemetry-row">
						<span class="telemetry-label">Min px</span>
						<span class="telemetry-value">{formatPriceWithPrecision($activePosition.min_price_reached)}</span>
					</div>
				{/if}

				{#if $activePosition.stagnation_enabled}
					<div class="telemetry-row">
						<span class="telemetry-label">Detected</span>
						<span class="telemetry-value">{$activePosition.stagnation_detected_at ? formatTime($activePosition.stagnation_detected_at) : '-'}</span>
					</div>
					{#if $activePosition.stagnation_pnl_at_detection !== null && $activePosition.stagnation_pnl_at_detection !== undefined}
						<div class="telemetry-row">
							<span class="telemetry-label">PnL det</span>
							<span class="telemetry-value">{formatPercent($activePosition.stagnation_pnl_at_detection)}%</span>
						</div>
					{/if}
					{#if stagnationEffectiveTimeoutSec !== null && openedAgeSec !== null}
						<div class="telemetry-row">
							<span class="telemetry-label">Timeout</span>
							<span class="telemetry-value">{stagnationTimeLeftSec !== null ? Math.round(stagnationTimeLeftSec) + 's' : '-'}</span>
						</div>
						{#if stagnationEffectiveProgressPct !== null}
							<div class="telemetry-progress">
								<div class="telemetry-progress-bar small">
									<div class="telemetry-progress-fill" style="width: {stagnationEffectiveProgressPct}%"></div>
								</div>
							</div>
						{/if}
					{/if}
				{/if}
			</div>
		</div>

		{#if $activePosition.size_remaining !== undefined && $activePosition.size_remaining !== null && $activePosition.size}
			<div class="position-info" data-debug-name="activePosition.size_remaining">
				<div class="info-item" data-debug-name="activePosition.size_remaining">
					<span class="info-label" data-debug-name="activePosition.size_remaining">Position restante:</span>
					<span class="info-value" data-debug-name="activePosition.size_remaining">
						{formatPrice($activePosition.size_remaining)} USDT 
						({formatPercent(($activePosition.size_remaining / $activePosition.size) * 100)}%)
					</span>
				</div>
			</div>
		{/if}

		{#if $activePosition && $activePosition.opened_at}
			<div class="duration" data-debug-name="positionDuration">
				<div class="duration-label" data-debug-name="positionDuration.label">⏱️ Durée:</div>
				<div class="duration-value" data-debug-name="positionDuration.value">{liveDuration || formatDurationFromSeconds(Math.floor((new Date() - new Date($activePosition.opened_at)) / 1000))}</div>
			</div>
		{/if}

		{#if $activePosition.confirmed_by}
			<div class="signals" data-debug-name="activePosition.confirmed_by">
				<div class="signals-label" data-debug-name="activePosition.confirmed_by">Confirmed by:</div>
				<div class="signals-list" data-debug-name="activePosition.confirmed_by">{$activePosition.confirmed_by}</div>
			</div>
		{/if}

		<!-- 🔥 FIX: Bouton pour clôturer la position manuellement -->
		<div class="close-position-section">
			<button class="close-position-btn" on:click={closePosition}>
				🚪 Clôturer la Position
			</button>
		</div>
	</div>
{:else}
	<div class="no-position">
		<div class="no-position-icon">📊</div>
		<div class="no-position-text">No Active Position</div>
	</div>
{/if}

<style>
	.position-card {
		background: linear-gradient(135deg, #1e2749 0%, #2a3a6b 100%);
		border-radius: 12px;
		padding: 20px;
		border: 2px solid #00ff88;
		box-shadow: 0 4px 20px rgba(0, 255, 136, 0.2);
	}

	.position-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 20px;
	}

	.symbol {
		font-size: 24px;
		font-weight: bold;
		color: #00ff88;
		text-shadow: 0 0 20px rgba(0, 255, 136, 0.5);
	}

	.header-right {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 8px;
	}

	/* 🔥 ML & Sizing Badges */
	.ml-sizing-badges {
		display: flex;
		gap: 8px;
		align-items: center;
	}

	.badge {
		padding: 4px 10px;
		border-radius: 6px;
		font-size: 12px;
		font-weight: bold;
		font-family: 'Courier New', monospace;
	}

	.ml-badge {
		background: rgba(138, 43, 226, 0.2);
		color: #b388ff;
		border: 1px solid rgba(138, 43, 226, 0.5);
	}

	.calib-badge {
		background: rgba(0, 255, 136, 0.1);
		color: #00ff88;
		border: 1px solid rgba(0, 255, 136, 0.3);
	}

	.sizing-badge {
		background: rgba(64, 196, 255, 0.1);
		color: #aaa;
		border: 1px solid rgba(100, 100, 100, 0.5);
	}

	.sizing-badge.boost {
		background: rgba(0, 255, 136, 0.15);
		color: #00ff88;
		border: 1px solid rgba(0, 255, 136, 0.4);
	}

	.sizing-badge.reduce {
		background: rgba(255, 170, 0, 0.15);
		color: #ffaa00;
		border: 1px solid rgba(255, 170, 0, 0.4);
	}

	.leverage-badge {
		background: rgba(255, 215, 0, 0.15);
		color: #ffd700;
		border: 1px solid rgba(255, 215, 0, 0.4);
	}

	.direction {
		padding: 8px 16px;
		border-radius: 8px;
		font-size: 14px;
		font-weight: bold;
	}

	.tp-sl-mode {
		background: rgba(0, 170, 255, 0.15);
		color: #00aaff;
		padding: 4px 12px;
		border-radius: 6px;
		font-size: 11px;
		font-weight: bold;
		border: 1px solid rgba(0, 170, 255, 0.3);
		font-family: 'Courier New', monospace;
	}

	.live-badge {
		background: rgba(0, 255, 136, 0.1);
		color: #00ff88;
		padding: 4px 12px;
		border-radius: 6px;
		font-size: 11px;
		font-weight: bold;
		border: 1px solid rgba(0, 255, 136, 0.3);
		font-family: 'Courier New', monospace;
	}

	.live-badge.stale {
		background: rgba(255, 68, 68, 0.15);
		color: #ff4444;
		border: 1px solid rgba(255, 68, 68, 0.4);
	}

	.direction.long {
		background: rgba(0, 255, 136, 0.2);
		color: #00ff88;
		border: 1px solid #00ff88;
	}

	.direction.short {
		background: rgba(255, 68, 68, 0.2);
		color: #ff4444;
		border: 1px solid #ff4444;
	}

	.pnl-section {
		text-align: center;
		margin-bottom: 20px;
	}

	.pnl-value {
		font-size: 48px;
		font-weight: bold;
		text-shadow: 0 0 20px currentColor;
	}

	.pnl-usdt {
		font-size: 20px;
		margin-top: 5px;
	}

	.price-grid {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 10px;
		margin-bottom: 15px;
	}

	.price-box {
		background: #0a0e27;
		padding: 12px;
		border-radius: 8px;
		text-align: center;
		border: 1px solid #2a3a6b;
	}

	.price-label {
		font-size: 11px;
		color: #888;
		margin-bottom: 5px;
		text-transform: uppercase;
		font-weight: bold;
	}

	.price-value {
		font-size: 14px;
		font-weight: bold;
		color: #00aaff;
	}

	.price-subvalue {
		margin-top: 4px;
		font-size: 12px;
		color: #00ff88;
		font-weight: bold;
		font-family: 'Courier New', monospace;
	}

	.tpsl-grid {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 15px;
		margin-bottom: 15px;
	}

	.telemetry-grid {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 12px;
		margin-bottom: 15px;
	}

	.telemetry-box {
		background: #0a0e27;
		padding: 12px;
		border-radius: 8px;
		border: 1px solid #2a3a6b;
	}

	.telemetry-title {
		font-size: 11px;
		color: #00aaff;
		margin-bottom: 10px;
		text-transform: uppercase;
		font-weight: bold;
	}

	.telemetry-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 10px;
		margin-top: 4px;
		font-size: 11px;
		color: #888;
	}

	.telemetry-label {
		text-transform: uppercase;
		font-size: 10px;
	}

	.telemetry-value {
		color: #fff;
		font-weight: bold;
		font-family: 'Courier New', monospace;
		text-align: right;
	}

	.telemetry-value.stale-text {
		color: #ff4444;
	}

	.telemetry-progress {
		margin-top: 10px;
	}

	.telemetry-progress-bar {
		height: 12px;
		background: rgba(255, 255, 255, 0.08);
		border-radius: 8px;
		overflow: hidden;
		position: relative;
	}

	.telemetry-progress-bar.small {
		height: 8px;
	}

	.telemetry-progress-fill {
		height: 100%;
		background: linear-gradient(90deg, #00aaff 0%, #00ff88 100%);
		border-radius: 8px;
		transition: width 0.5s ease;
	}

	.telemetry-marker {
		position: absolute;
		top: -2px;
		width: 2px;
		height: 16px;
		opacity: 0.95;
	}

	.telemetry-marker.be {
		background: #00ff88;
	}

	.telemetry-marker.trailing {
		background: #ffaa00;
	}

	.telemetry-marker.mfe {
		background: #b388ff;
	}

	.telemetry-progress-legend {
		display: flex;
		justify-content: space-between;
		margin-top: 6px;
		font-size: 10px;
		color: #888;
		font-family: 'Courier New', monospace;
	}

	/* 🔥 NOUVEAU: Styles pour les sections TP et SL distinctes */
	.next-event-section {
		background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 100%);
		border: 1px solid #2a3a6b;
		border-radius: 12px;
		padding: 16px;
		margin-bottom: 16px;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
		transition: all 0.3s ease;
	}

	.next-event-section:hover {
		transform: translateY(-2px);
		box-shadow: 0 6px 16px rgba(0, 0, 0, 0.4);
	}

	/* Section TP - thème vert/or */
	.next-event-section.tp-section {
		border-color: rgba(16, 185, 129, 0.3);
		background: linear-gradient(135deg, #0a1f1a 0%, #1a2f2a 100%);
	}

	/* Section SL - thème rouge/or */
	.next-event-section.sl-section {
		border-color: rgba(239, 68, 68, 0.3);
		background: linear-gradient(135deg, #1f0a0a 0%, #2f1a1a 100%);
	}

	.next-event-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 12px;
	}

	.next-event-label {
		font-size: 12px;
		color: #888;
		text-transform: uppercase;
		font-weight: bold;
		letter-spacing: 0.5px;
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.next-event-type {
		font-size: 14px;
		font-weight: bold;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.next-event-details {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 10px;
	}

	.next-event-price {
		font-size: 16px;
		font-weight: bold;
		color: #fff;
	}

	.next-event-distance {
		font-size: 14px;
		color: #ccc;
		font-family: 'Courier New', monospace;
	}

	.next-event-progress {
		height: 6px;
		background: rgba(255, 255, 255, 0.1);
		border-radius: 3px;
		overflow: hidden;
		position: relative;
	}

	.next-event-progress-bar {
		height: 100%;
		border-radius: 3px;
		border: 1px solid;
		transition: width 0.3s ease, background-color 0.3s ease;
	}

	/* Barre TP - verte */
	.next-event-progress-bar.tp-bar {
		background-color: rgba(16, 185, 129, 0.2);
		border-color: #10b981;
		box-shadow: 0 0 8px rgba(16, 185, 129, 0.3);
	}

	/* Barre SL - rouge */
	.next-event-progress-bar.sl-bar {
		background-color: rgba(239, 68, 68, 0.2);
		border-color: #ef4444;
		box-shadow: 0 0 8px rgba(239, 68, 68, 0.3);
	}

	/* Styles pour les badges TP/SL existants */
	.tpsl-box {
		background: #0a0e27;
		padding: 15px;
		border-radius: 8px;
		text-align: center;
	}

	.tpsl-box.tp {
		border: 2px solid #00ff88;
	}

	.tpsl-box.sl {
		border: 2px solid #ff4444;
	}

	.tpsl-label {
		font-size: 12px;
		font-weight: bold;
		margin-bottom: 8px;
	}

	.tpsl-box.tp .tpsl-label {
		color: #00ff88;
	}

	.tpsl-box.sl .tpsl-label {
		color: #ff4444;
	}

	.tpsl-price {
		font-size: 18px;
		font-weight: bold;
		color: #fff;
		margin-bottom: 5px;
	}

	.tpsl-distance {
		font-size: 14px;
		font-weight: bold;
	}

	.tpsl-box.tp .tpsl-distance {
		color: #00ff88;
	}

	.tpsl-box.sl .tpsl-distance {
		color: #ff4444;
	}

	.tpsl-info {
		margin-top: 8px;
		padding-top: 8px;
		border-top: 1px solid rgba(255, 255, 255, 0.1);
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.tpsl-pnl, .tpsl-size {
		font-size: 11px;
		color: #888;
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.tpsl-value {
		font-weight: bold;
		font-family: 'Courier New', monospace;
	}

	.tpsl-box.tp .tpsl-value {
		color: #00ff88;
	}

	.tpsl-box.sl .tpsl-value {
		color: #ff4444;
	}

	.force-full-tp-badge {
		display: inline-block;
		margin-left: 6px;
		padding: 2px 6px;
		font-size: 9px;
		font-weight: bold;
		color: #ffaa00;
		background: rgba(255, 170, 0, 0.15);
		border: 1px solid rgba(255, 170, 0, 0.3);
		border-radius: 4px;
		cursor: help;
	}

	.tp-levels {
		margin-top: 8px;
		padding-top: 8px;
		border-top: 1px solid rgba(0, 255, 136, 0.2);
	}

	.tp-level {
		font-size: 10px;
		color: #888;
		margin-top: 4px;
		padding: 2px 4px;
		border-radius: 4px;
		background: rgba(0, 255, 136, 0.05);
	}

	.tp-level.hit {
		color: #00ff88;
		background: rgba(0, 255, 136, 0.15);
		font-weight: bold;
	}

	.trailing-stop {
		margin-top: 8px;
		padding-top: 8px;
		border-top: 1px solid rgba(255, 68, 68, 0.2);
		font-size: 11px;
		color: #ffaa00;
		font-weight: bold;
	}

	.position-info {
		background: rgba(0, 170, 255, 0.1);
		padding: 12px;
		border-radius: 8px;
		border: 1px solid #00aaff;
		margin-bottom: 15px;
	}

	.info-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.info-label {
		font-size: 12px;
		color: #888;
		text-transform: uppercase;
		font-weight: bold;
	}

	.info-value {
		font-size: 14px;
		color: #00aaff;
		font-weight: bold;
		font-family: 'Courier New', monospace;
	}

	.duration {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		margin: 15px 0;
		padding: 10px;
		background: rgba(42, 58, 107, 0.3);
		border-radius: 8px;
		font-size: 14px;
	}

	.duration-label {
		color: #888;
		font-weight: 500;
	}

	.duration-value {
		color: #00ff88;
		font-weight: bold;
		font-family: 'Courier New', monospace;
		font-size: 16px;
	}

	.signals {
		background: rgba(0, 170, 255, 0.1);
		padding: 12px;
		border-radius: 8px;
		border: 1px solid #00aaff;
	}

	.signals-label {
		font-size: 11px;
		color: #888;
		margin-bottom: 5px;
		text-transform: uppercase;
	}

	.signals-list {
		font-size: 12px;
		color: #00aaff;
		line-height: 1.6;
	}

	.no-position {
		background: #1e2749;
		border-radius: 12px;
		padding: 40px 20px;
		text-align: center;
		border: 2px dashed #2a3a6b;
	}

	.no-position-icon {
		font-size: 48px;
		margin-bottom: 15px;
	}

	.no-position-text {
		font-size: 16px;
		color: #888;
	}

	/* 🔥 FIX: Styles pour le bouton de clôture */
	.close-position-section {
		margin-top: 20px;
		padding-top: 20px;
		border-top: 2px solid #2a3a6b;
		text-align: center;
	}

	.close-position-btn {
		background: linear-gradient(135deg, #ff4444 0%, #cc0000 100%);
		color: white;
		border: none;
		padding: 12px 24px;
		border-radius: 8px;
		font-size: 14px;
		font-weight: bold;
		cursor: pointer;
		transition: all 0.3s;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		box-shadow: 0 4px 15px rgba(255, 68, 68, 0.3);
	}

	.close-position-btn:hover {
		transform: translateY(-2px);
		box-shadow: 0 6px 20px rgba(255, 68, 68, 0.5);
	}

	.close-position-btn:active {
		transform: translateY(0);
	}

	/* Mobile responsive */
	@media (max-width: 768px) {
		.price-grid {
			grid-template-columns: repeat(2, 1fr);
		}

		.telemetry-grid {
			grid-template-columns: 1fr;
		}

		.pnl-value {
			font-size: 36px;
		}

		.symbol {
			font-size: 20px;
		}
	}
</style>
