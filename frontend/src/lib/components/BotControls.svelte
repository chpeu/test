<script>
	import { isScanning } from '$lib/stores/scanner';
	import { initWebSocket, getWebSocket } from '$lib/utils/websocket';
	import { onMount } from 'svelte';

	let loading = false;
	let rebooting = false;

	async function startBot() {
		try {
			loading = true;
			const ws = initWebSocket();

			if (!ws || !ws.connected) {
				// Fallback to REST API if WebSocket not available
				const res = await fetch('/api/scanner/start', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' }
				});

				if (res.ok) {
					console.log('✅ Bot started via REST API');
				} else {
					console.error('❌ Failed to start bot');
				}
			} else {
				await ws.sendCommand('start_scanner');
				console.log('✅ Bot started via WebSocket');
			}
		} catch (err) {
			console.error('❌ Error starting bot:', err);
		} finally {
			loading = false;
		}
	}

	async function stopBot() {
		try {
			loading = true;
			const ws = initWebSocket();

			if (!ws || !ws.connected) {
				// Fallback to REST API if WebSocket not available
				const res = await fetch('/api/scanner/stop', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' }
				});

				if (res.ok) {
					console.log('✅ Bot stopped via REST API');
				} else {
					console.error('❌ Failed to stop bot');
				}
			} else {
				await ws.sendCommand('stop_scanner');
				console.log('✅ Bot stopped via WebSocket');
			}
		} catch (err) {
			console.error('❌ Error stopping bot:', err);
		} finally {
			loading = false;
		}
	}

	async function rebootBot() {
		if (!confirm('⚠️ Redémarrer le bot (backend + frontend) ?\n\nCela arrêtera toutes les opérations en cours.')) {
			return;
		}

		try {
			rebooting = true;
			const ws = initWebSocket();

			if (ws && ws.connected) {
				await ws.sendCommand('reboot_bot');
				console.log('🔄 Bot redémarrage en cours...');

				// Afficher un message pendant le redémarrage
				alert('🔄 Bot en cours de redémarrage...\n\nLa page se rechargera automatiquement dans quelques secondes.');

				// Recharger la page après 5 secondes
				setTimeout(() => {
					window.location.reload();
				}, 5000);
			} else {
				alert('❌ WebSocket non connecté. Impossible de redémarrer le bot.');
			}
		} catch (err) {
			console.error('❌ Error rebooting bot:', err);
			alert('❌ Erreur lors du redémarrage du bot.');
			rebooting = false;
		}
	}

	// Écouter l'événement de redémarrage du bot
	onMount(() => {
		const ws = getWebSocket();
		if (ws) {
			ws.on('bot_rebooting', (data) => {
				console.log('🔄 Bot rebooting:', data);
				rebooting = true;

				// Recharger la page après 3 secondes
				setTimeout(() => {
					window.location.reload();
				}, 3000);
			});
		}
	});
</script>

<div class="bot-controls">
	<div class="controls-header">
		<h3>🤖 Bot Controls</h3>
		<div class="bot-status" class:active={$isScanning}>
			{$isScanning ? '🟢 Running' : '🔴 Stopped'}
		</div>
	</div>

	<div class="controls-buttons">
		{#if !$isScanning}
			<button
				class="btn btn-primary"
				on:click={startBot}
				disabled={loading || rebooting}
			>
				{loading ? '⏳ Starting...' : '▶️ Start Scanner'}
			</button>
		{:else}
			<button
				class="btn btn-danger"
				on:click={stopBot}
				disabled={loading || rebooting}
			>
				{loading ? '⏳ Stopping...' : '⏹️ Stop Scanner'}
			</button>
		{/if}

		<button
			class="btn btn-warning"
			on:click={rebootBot}
			disabled={loading || rebooting}
		>
			{rebooting ? '🔄 Rebooting...' : '🔄 Reboot Bot'}
		</button>
	</div>

	<div class="controls-info">
		<p class="info-text">
			{#if $isScanning}
				🔍 Scanner is actively searching for trading opportunities
			{:else}
				💤 Scanner is stopped. Click "Start Scanner" to begin
			{/if}
		</p>
	</div>
</div>

<style>
	.bot-controls {
		background: #1e2749;
		border-radius: 12px;
		padding: 20px;
		border: 2px solid #2a3a6b;
	}

	.controls-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 20px;
	}

	.controls-header h3 {
		font-size: 20px;
		color: #00ff88;
		font-weight: bold;
		margin: 0;
	}

	.bot-status {
		background: rgba(255, 68, 68, 0.2);
		color: #ff4444;
		padding: 8px 16px;
		border-radius: 12px;
		font-size: 13px;
		font-weight: bold;
		border: 2px solid #ff4444;
		transition: all 0.3s;
	}

	.bot-status.active {
		background: rgba(0, 255, 136, 0.2);
		color: #00ff88;
		border-color: #00ff88;
		animation: pulse 2s ease-in-out infinite;
	}

	@keyframes pulse {
		0%, 100% {
			opacity: 1;
		}
		50% {
			opacity: 0.7;
		}
	}

	.controls-buttons {
		display: flex;
		gap: 12px;
		margin-bottom: 16px;
	}

	.btn {
		flex: 1;
		padding: 14px 24px;
		border: none;
		border-radius: 10px;
		font-size: 15px;
		font-weight: bold;
		cursor: pointer;
		transition: all 0.3s;
		font-family: 'Courier New', monospace;
		text-transform: uppercase;
		box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
	}

	.btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.btn-primary {
		background: linear-gradient(135deg, #00ff88 0%, #00cc6a 100%);
		color: #0a0e27;
	}

	.btn-primary:hover:not(:disabled) {
		transform: translateY(-2px);
		box-shadow: 0 6px 20px rgba(0, 255, 136, 0.4);
	}

	.btn-danger {
		background: linear-gradient(135deg, #ff4444 0%, #cc0000 100%);
		color: white;
	}

	.btn-danger:hover:not(:disabled) {
		transform: translateY(-2px);
		box-shadow: 0 6px 20px rgba(255, 68, 68, 0.4);
	}

	.btn-warning {
		background: linear-gradient(135deg, #ffaa00 0%, #dd8800 100%);
		color: #0a0e27;
	}

	.btn-warning:hover:not(:disabled) {
		transform: translateY(-2px);
		box-shadow: 0 6px 20px rgba(255, 170, 0, 0.4);
	}

	.controls-info {
		background: rgba(0, 170, 255, 0.1);
		border-left: 3px solid #00aaff;
		padding: 12px;
		border-radius: 6px;
	}

	.info-text {
		font-size: 13px;
		color: #aaa;
		margin: 0;
		line-height: 1.5;
	}

	/* Mobile */
	@media (max-width: 768px) {
		.controls-buttons {
			flex-direction: column;
		}

		.bot-controls {
			padding: 15px;
		}

		.controls-header h3 {
			font-size: 18px;
		}

		.bot-status {
			font-size: 11px;
			padding: 6px 12px;
		}
	}
</style>
