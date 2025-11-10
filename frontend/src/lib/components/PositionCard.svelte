<script>
	import { activePosition, pnlColor, slDistance, tpDistance, positionDuration, clearPosition, updatePosition } from '$lib/stores/position';
	import { formatPrice, formatPercent, formatUSDT } from '$lib/utils/format';
	import { sendCommandViaWS } from '$lib/utils/websocket';

	// 🔥 FIX: Fonction pour clôturer la position manuellement
	async function closePosition() {
		if (!confirm('Êtes-vous sûr de vouloir clôturer cette position manuellement ?')) {
			return;
		}

		// 🔥 FIX: Mise à jour optimiste immédiate pour feedback instantané
		clearPosition();

		try {
			// 🔥 MIGRATION COMPLÈTE: Utiliser WebSocket natif au lieu de REST
			const result = await sendCommandViaWS('close_position', {
				reason: 'MANUAL',
				exit_price: $activePosition.current_price
			});
			
			if (result && result.status === 'closed') {
				console.log('✅ Position fermée via WebSocket:', result.result);
				// La synchronisation WebSocket natif confirmera et mettra à jour les stats/historique
			} else {
				console.log('✅ Position fermée via WebSocket');
			}
		} catch (err) {
			console.error('❌ Error closing position via WebSocket:', err);
			// Fallback REST si WebSocket non disponible
			try {
				const res = await fetch('/api/position/close', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({
						reason: 'MANUAL',
						exit_price: $activePosition.current_price
					})
				});
				
				if (res.ok) {
					const data = await res.json();
					console.log('✅ Position fermée via REST (fallback):', data);
				} else {
					const errorData = await res.json().catch(() => ({}));
					alert(`❌ Erreur: ${errorData.error || res.statusText}`);
					// En cas d'erreur, recharger la position depuis le backend
					const stateRes = await fetch('/api/state');
					if (stateRes.ok) {
						const stateData = await stateRes.json();
						if (stateData.active_position) {
							updatePosition(stateData.active_position);
						}
					}
				}
			} catch (fallbackErr) {
				console.error('❌ Erreur fallback REST:', fallbackErr);
				alert('❌ Erreur: Impossible de clôturer la position');
				// En cas d'erreur, recharger la position depuis le backend
				try {
					const stateRes = await fetch('/api/state');
					if (stateRes.ok) {
						const stateData = await stateRes.json();
						if (stateData.active_position) {
							updatePosition(stateData.active_position);
						}
					}
				} catch (e) {
					console.error('Error reloading position:', e);
				}
			}
		}
	}
</script>

{#if $activePosition}
	<div class="position-card">
		<div class="position-header">
			<div class="symbol">{$activePosition.symbol}</div>
			<div class="header-right">
				<div class="direction" class:long={$activePosition.direction === 'LONG'} class:short={$activePosition.direction === 'SHORT'}>
					{$activePosition.direction}
				</div>
				{#if $activePosition.tp_sl_mode}
					<div class="tp-sl-mode">
						Mode: {$activePosition.tp_sl_mode}
					</div>
				{/if}
			</div>
		</div>

		<div class="pnl-section">
			<div class="pnl-value" style="color: {$pnlColor}">
				{formatPercent($activePosition.pnl)}%
			</div>
			<div class="pnl-usdt" style="color: {$pnlColor}">
				{formatUSDT($activePosition.pnl_usdt)} USDT
			</div>
		</div>

		<div class="price-grid">
			<div class="price-box">
				<div class="price-label">Entry</div>
				<div class="price-value">{formatPrice($activePosition.entry)}</div>
			</div>
			<div class="price-box">
				<div class="price-label">Current</div>
				<div class="price-value">{formatPrice($activePosition.current_price)}</div>
			</div>
			<div class="price-box">
				<div class="price-label">Size</div>
				<div class="price-value">{formatPrice($activePosition.size)} USDT</div>
			</div>
		</div>

		<div class="tpsl-grid">
			<div class="tpsl-box tp">
				<div class="tpsl-label">TP</div>
				<div class="tpsl-price">{formatPrice($activePosition.tp)}</div>
				{#if $tpDistance}
					<div class="tpsl-distance">+{$tpDistance}%</div>
				{/if}
			</div>
			<div class="tpsl-box sl">
				<div class="tpsl-label">SL</div>
				<div class="tpsl-price">{formatPrice($activePosition.sl)}</div>
				{#if $slDistance}
					<div class="tpsl-distance">{$slDistance}%</div>
				{/if}
			</div>
		</div>

		{#if $positionDuration}
			<div class="duration">
				Duration: {$positionDuration}
			</div>
		{/if}

		{#if $activePosition.confirmed_by}
			<div class="signals">
				<div class="signals-label">Confirmed by:</div>
				<div class="signals-list">{$activePosition.confirmed_by}</div>
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
