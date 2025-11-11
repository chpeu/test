<script>
	import { activePosition, pnlColor, slDistance, tpDistance, positionDuration, clearPosition, updatePosition } from '$lib/stores/position';
	import { formatPrice, formatPercent, formatUSDT } from '$lib/utils/format';
	import { sendCommandViaWS } from '$lib/utils/websocket';
	import { onMount } from 'svelte';

	// 🔥 FIX: Extraire la précision depuis les données de position
	$: pricePrecision = $activePosition?.price_precision;
	$: tickSize = $activePosition?.tickSize || $activePosition?.tick_size;
	
	// 🔥 FIX: Récupérer la config pour afficher les bonnes informations TP/SL
	let tradingConfig = null;
	
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
	
	onMount(async () => {
		await loadConfig();
		// Écouter les mises à jour de config
		const { getWebSocket } = await import('$lib/utils/websocket');
		const ws = getWebSocket();
		if (ws) {
			ws.on('config_updated', (data) => {
				if (data.updated) {
					tradingConfig = { ...tradingConfig, ...data.updated };
				}
			});
		}
	});
	
	// 🔥 FIX: Calculer les informations de la prochaine clôture
	$: nextTpInfo = (() => {
		if (!$activePosition || !tradingConfig) return null;
		
		const tpSlMode = tradingConfig.tp_sl_mode || $activePosition.tp_sl_mode || 'FIXE';
		
		// Mode TP_MULTI/ESCALIER
		if (tpSlMode === 'TP_MULTI' || tpSlMode === 'ESCALIER') {
			const levels = $activePosition.tp_escalier_levels ? JSON.parse($activePosition.tp_escalier_levels) : [];
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
		
		// Mode FIXE ou ATR
		// Vérifier si TP partiel déjà vendu
		if (!$activePosition.partial_tp_sold && tradingConfig.partial_tp_percent) {
			// TP partiel pas encore vendu
			return {
				pnl: tradingConfig.tp_percent || 0.6,
				size: tradingConfig.partial_tp_percent || 50
			};
		}
		
		// TP complet
		return {
			pnl: tradingConfig.tp_percent || 0.6,
			size: 100
		};
	})();
	
	$: nextSlInfo = (() => {
		if (!$activePosition || !tradingConfig) return null;
		
		return {
			pnl: tradingConfig.sl_percent || 0.25,
			size: 100
		};
	})();
	
	// 🔥 FIX: Fonction helper pour formater avec précision
	function formatPriceWithPrecision(price) {
		// Si on a price_precision (nombre de décimales), l'utiliser directement
		if (pricePrecision !== null && pricePrecision !== undefined) {
			return formatPrice(price, pricePrecision);
		}
		// Si on a tickSize, le passer comme objet pour que formatPrice calcule les décimales
		if (tickSize !== null && tickSize !== undefined) {
			return formatPrice(price, { tickSize: tickSize });
		}
		// Fallback: utiliser formatPrice sans précision (utilisera le comportement adaptatif)
		return formatPrice(price);
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
</script>

{#if $activePosition}
	<div class="position-card" data-debug-name="activePosition">
		<div class="position-header">
			<div class="symbol" data-debug-name="activePosition.symbol">{$activePosition.symbol}</div>
			<div class="header-right">
				<div class="direction" class:long={$activePosition.direction === 'LONG'} class:short={$activePosition.direction === 'SHORT'} data-debug-name="activePosition.direction">
					{$activePosition.direction}
				</div>
				{#if $activePosition.tp_sl_mode}
					<div class="tp-sl-mode" data-debug-name="activePosition.tp_sl_mode">
						Mode: {$activePosition.tp_sl_mode}
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
			</div>
		</div>

		<div class="tpsl-grid">
			<div class="tpsl-box tp" data-debug-name="activePosition.tp">
				<div class="tpsl-label" data-debug-name="activePosition.tp">Prochain Take Profit</div>
				<div class="tpsl-price" data-debug-name="activePosition.tp">{formatPriceWithPrecision($activePosition.tp)}</div>
				{#if nextTpInfo}
					<div class="tpsl-info">
						<div class="tpsl-pnl" data-debug-name="nextTpInfo.pnl">PnL objectif: <span class="tpsl-value" data-debug-name="nextTpInfo.pnl">+{formatPercent(nextTpInfo.pnl)}%</span></div>
						<div class="tpsl-size" data-debug-name="nextTpInfo.size">Taille: <span class="tpsl-value" data-debug-name="nextTpInfo.size">{nextTpInfo.size}% de la position</span></div>
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

		{#if $positionDuration}
			<div class="duration" data-debug-name="positionDuration">
				Duration: {$positionDuration}
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

	.tpsl-grid {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 15px;
		margin-bottom: 15px;
	}

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
		text-align: center;
		font-size: 14px;
		color: #888;
		margin-bottom: 15px;
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

		.pnl-value {
			font-size: 36px;
		}

		.symbol {
			font-size: 20px;
		}
	}
</style>
