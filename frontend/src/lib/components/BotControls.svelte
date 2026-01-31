<script>
	import { isScanning } from '$lib/stores/scanner';
	import { botPhase, getPhaseMessage } from '$lib/stores/botPhase';
	import { activePosition } from '$lib/stores/position';
	import { onMount } from 'svelte';
	import { quietMode, setQuietMode } from '$lib/stores/quietMode';

	let loading = false;
	let rebooting = false;
	let quietLoading = false;

	// 🔧 FIX: S'assurer que loading est toujours false au démarrage
	onMount(() => {
		loading = false;
		rebooting = false;
	});

	// 🔥 NOUVEAU: Calculer le message de statut dynamique
	$: statusMessage = (() => {
		// Priorité 1: Position active
		if ($activePosition) {
			return getPhaseMessage('position_active');
		}
		// Priorité 2: Phase du bot
		if ($botPhase && $botPhase !== 'arrêt') {
			return getPhaseMessage($botPhase);
		}
		// Priorité 3: État du scanner
		if ($isScanning) {
			return getPhaseMessage('scan_setups');
		}
		// Fallback: Arrêt
		return getPhaseMessage('arrêt');
	})();

	async function startBot() {
		try {
			console.log('🔍 [BOTCONTROLS] startBot called');
			loading = true;
			// 🔧 PROTECTION: Timeout automatique pour éviter loading bloqué
			const timeoutId = setTimeout(() => {
				loading = false;
				console.warn('⚠️ Timeout startBot - loading forcé à false');
			}, 10000); // 10 secondes max

			const { getWebSocket, sendCommandViaWS } = await import('$lib/utils/websocket');
			const ws = getWebSocket();

			if (!ws || !ws.connected) {
				throw new Error('WebSocket non connecté. Veuillez attendre la connexion.');
			}

			console.log('🔍 [BOTCONTROLS] Sending start_scanner command');
			await sendCommandViaWS('start_scanner', {});
			console.log('✅ Bot started via WebSocket');
			clearTimeout(timeoutId);
		} catch (err) {
			console.error('❌ Error starting bot:', err);
			alert(`❌ Erreur: ${err.message || 'Impossible de démarrer le scanner'}`);
		} finally {
			loading = false;
		}
	}

	async function stopBot() {
		try {
			console.log('🔍 [BOTCONTROLS] stopBot called');
			loading = true;
			// 🔧 PROTECTION: Timeout automatique pour éviter loading bloqué
			const timeoutId = setTimeout(() => {
				loading = false;
				console.warn('⚠️ Timeout stopBot - loading forcé à false');
			}, 10000); // 10 secondes max

			const { getWebSocket, sendCommandViaWS } = await import('$lib/utils/websocket');
			const ws = getWebSocket();

			if (!ws || !ws.connected) {
				throw new Error('WebSocket non connecté. Veuillez attendre la connexion.');
			}

			console.log('🔍 [BOTCONTROLS] Sending stop_scanner command');
			await sendCommandViaWS('stop_scanner', {});
			console.log('✅ Bot stopped via WebSocket');
			clearTimeout(timeoutId);
		} catch (err) {
			console.error('❌ Error stopping bot:', err);
			alert(`❌ Erreur: ${err.message || 'Impossible d\'arrêter le scanner'}`);
		} finally {
			loading = false;
		}
	}

	async function rebootBackend() {
		if (rebooting) return;
		if (typeof window !== 'undefined') {
			const confirmed = window.confirm('⚠️ Redémarrer le backend ? Tous les processus seront relancés.');
			if (!confirmed) {
				return;
			}
		}

		try {
			rebooting = true;
			const { getWebSocket, sendCommandViaWS } = await import('$lib/utils/websocket');
			const ws = getWebSocket();

			if (!ws || !ws.connected) {
				throw new Error('WebSocket non connecté. Réessayez après reconnexion.');
			}

			await sendCommandViaWS('reboot_backend', {});
			console.log('♻️ Backend reboot demandé');
			if (typeof window !== 'undefined') {
				alert('♻️ Redémarrage du backend en cours...');
			}
		} catch (err) {
			console.error('❌ Error rebooting backend:', err);
			alert(`❌ Erreur: ${err.message || 'Impossible de redémarrer le backend'}`);
		} finally {
			rebooting = false;
		}
	}

	async function toggleQuietMode() {
		if (quietLoading) return;
		try {
			quietLoading = true;
			const { getWebSocket, sendCommandViaWS } = await import('$lib/utils/websocket');
			const ws = getWebSocket();

			if (!ws || !ws.connected) {
				throw new Error('WebSocket non connecté. Veuillez attendre la connexion.');
			}

			const target = !$quietMode;
			const result = await sendCommandViaWS('set_quiet_mode', { enabled: target });
			if (result && typeof result.quiet_mode !== 'undefined') {
				setQuietMode(result.quiet_mode);
			} else {
				setQuietMode(target);
			}
		} catch (err) {
			console.error('❌ Error toggling quiet mode:', err);
			alert(`❌ Erreur: ${err.message || 'Impossible de changer le mode quiet'}`);
		} finally {
			quietLoading = false;
		}
	}
</script>

<div class="bot-controls" data-debug-name="botControls">
	<div class="controls-header" data-debug-name="botControls.header">
		<div class="title-group">
			<h3 data-debug-name="botControls.title">🤖 Bot Controls</h3>
			<button
				class="btn-reboot"
				on:click={rebootBackend}
				disabled={rebooting}
				data-debug-name="botControls.rebootButton"
			>
				{rebooting ? '♻️ Rebooting...' : 'Reboot backend'}
			</button>
			<button
				class="btn-quiet"
				class:active={$quietMode}
				on:click={toggleQuietMode}
				disabled={quietLoading}
				data-debug-name="botControls.quietModeButton"
			>
				{quietLoading ? '⏳ Quiet...' : $quietMode ? '🔕 Quiet' : '🔊 Logs'}
			</button>
		</div>
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
			{statusMessage}
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

	.title-group {
		display: flex;
		align-items: center;
		gap: 12px;
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

	.btn-reboot {
		padding: 8px 14px;
		border-radius: 8px;
		border: 1px solid #ffaa33;
		background: rgba(255, 170, 51, 0.15);
		color: #ffaa33;
		font-size: 13px;
		font-weight: bold;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.btn-reboot:hover:not(:disabled) {
		background: rgba(255, 170, 51, 0.3);
		transform: translateY(-1px);
	}

	.btn-reboot:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.btn-quiet {
		padding: 8px 12px;
		border-radius: 8px;
		border: 1px solid #5cc8ff;
		background: rgba(92, 200, 255, 0.15);
		color: #5cc8ff;
		font-size: 13px;
		font-weight: bold;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.btn-quiet:hover:not(:disabled) {
		background: rgba(92, 200, 255, 0.3);
		transform: translateY(-1px);
	}

	.btn-quiet.active {
		background: rgba(92, 200, 255, 0.4);
		border-color: #9be0ff;
		color: #e6f7ff;
	}

	.btn-quiet:disabled {
		opacity: 0.6;
		cursor: not-allowed;
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

		.title-group {
			flex-direction: column;
			align-items: flex-start;
		}

		.bot-status {
			font-size: 11px;
			padding: 6px 12px;
		}
	}
</style>
