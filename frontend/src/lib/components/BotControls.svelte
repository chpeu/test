<script>
	import { isScanning } from '$lib/stores/scanner';

	let loading = false;

	async function startBot() {
		try {
			loading = true;
			const { getWebSocket, sendCommandViaWS } = await import('$lib/utils/websocket');
			const ws = getWebSocket();

			if (!ws || !ws.connected) {
				throw new Error('WebSocket non connecté. Veuillez attendre la connexion.');
			}

			await sendCommandViaWS('start_scanner', {});
			console.log('✅ Bot started via WebSocket');
		} catch (err) {
			console.error('❌ Error starting bot:', err);
			alert(`❌ Erreur: ${err.message || 'Impossible de démarrer le scanner'}`);
		} finally {
			loading = false;
		}
	}

	async function stopBot() {
		try {
			loading = true;
			const { getWebSocket, sendCommandViaWS } = await import('$lib/utils/websocket');
			const ws = getWebSocket();

			if (!ws || !ws.connected) {
				throw new Error('WebSocket non connecté. Veuillez attendre la connexion.');
			}

			await sendCommandViaWS('stop_scanner', {});
			console.log('✅ Bot stopped via WebSocket');
		} catch (err) {
			console.error('❌ Error stopping bot:', err);
			alert(`❌ Erreur: ${err.message || 'Impossible d\'arrêter le scanner'}`);
		} finally {
			loading = false;
		}
	}
</script>

<div class="bot-controls" data-debug-name="botControls">
	<div class="controls-header" data-debug-name="botControls.header">
		<h3 data-debug-name="botControls.title">🤖 Bot Controls</h3>
		<div class="bot-status" class:active={$isScanning} data-debug-name="isScanning">
			{$isScanning ? '🟢 Running' : '🔴 Stopped'}
		</div>
	</div>

	<div class="controls-buttons" data-debug-name="botControls.buttons">
		{#if !$isScanning}
			<button
				class="btn btn-primary"
				on:click={startBot}
				disabled={loading}
				data-debug-name="botControls.startButton"
			>
				{loading ? '⏳ Starting...' : '▶️ Start Scanner'}
			</button>
		{:else}
			<button
				class="btn btn-danger"
				on:click={stopBot}
				disabled={loading}
				data-debug-name="botControls.stopButton"
			>
				{loading ? '⏳ Stopping...' : '⏹️ Stop Scanner'}
			</button>
		{/if}
	</div>

	<div class="controls-info" data-debug-name="botControls.info">
		<p class="info-text" data-debug-name="botControls.statusText">
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
