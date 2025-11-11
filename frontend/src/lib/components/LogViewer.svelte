<script>
	import { onMount, afterUpdate } from 'svelte';
	import { recentLogs, errorCount, recentConfigLogs, configChangesCount } from '$lib/stores/logs';
	import { derived } from 'svelte/store';

	let logContainer;
	let errorContainer;
	let configContainer;
	let autoScroll = true;
	let autoScrollErrors = true;
	let autoScrollConfig = true;
	let showErrorPopup = false;
	let lastErrorId = null;

	// 🔥 FIX: Seulement les erreurs (pas les warnings)
	const errorLogs = derived(recentLogs, $logs =>
		$logs.filter(log => log.level === 'ERROR' || log.level === 'CRITICAL')
	);

	// 🔥 FIX: Détecter les nouvelles erreurs pour afficher le popup
	$: if ($errorLogs.length > 0) {
		const latestError = $errorLogs[$errorLogs.length - 1];
		if (latestError && latestError.id !== lastErrorId) {
			lastErrorId = latestError.id;
			showErrorPopup = true;
		}
	}

	function acknowledgeError() {
		showErrorPopup = false;
	}

	// 🔥 FIX: Tous les logs backend (INFO, DEBUG, etc.) avec couleurs
	const regularLogs = derived(recentLogs, $logs =>
		$logs.filter(log => log.level !== 'ERROR' && log.level !== 'CRITICAL')
	);

	// Auto-scroll to bottom when new logs arrive
	afterUpdate(() => {
		if (autoScroll && logContainer) {
			logContainer.scrollTop = logContainer.scrollHeight;
		}
		if (autoScrollErrors && errorContainer) {
			errorContainer.scrollTop = errorContainer.scrollHeight;
		}
		if (autoScrollConfig && configContainer) {
			configContainer.scrollTop = configContainer.scrollHeight;
		}
	});

	function handleScroll(container, type = 'regular') {
		if (!container) return;
		const { scrollTop, scrollHeight, clientHeight } = container;
		// Auto-scroll if user is within 50px of bottom
		const isAtBottom = scrollTop + clientHeight >= scrollHeight - 50;
		if (type === 'error') {
			autoScrollErrors = isAtBottom;
		} else if (type === 'config') {
			autoScrollConfig = isAtBottom;
		} else {
			autoScroll = isAtBottom;
		}
	}

	function getLogColor(level) {
		switch (level) {
			case 'ERROR':
			case 'CRITICAL':
				return '#ff4444';
			case 'WARNING':
				return '#ffaa00';
			case 'INFO':
				return '#00ff88';
			case 'DEBUG':
				return '#888';
			default:
				return '#fff';
		}
	}

	function formatTime(timestamp) {
		if (!timestamp) return '';
		const date = new Date(timestamp);
		return date.toLocaleTimeString('en-US', { hour12: false });
	}

	function stripAnsiCodes(text) {
		if (!text) return '';
		// Supprimer les codes ANSI de couleur: \x1b[XXm ou [XXm
		return text.replace(/\x1b\[\d+m/g, '').replace(/\[\d+m/g, '');
	}

	// 🔥 FIX: Extraire les emojis et couleurs des logs backend
	function parseLogMessage(message) {
		if (!message) return { icon: '', text: message };
		// Extraire les emojis au début du message
		const emojiMatch = message.match(/^([\u{1F300}-\u{1F9FF}]|[\u{2600}-\u{26FF}]|[\u{2700}-\u{27BF}])+/u);
		const icon = emojiMatch ? emojiMatch[0] : '';
		const text = emojiMatch ? message.slice(emojiMatch[0].length).trim() : message;
		return { icon, text };
	}

	function exportLogs() {
		const allLogs = [...$errorLogs, ...$regularLogs];
		const csv = [
			['Timestamp', 'Level', 'Message'].join(','),
			...allLogs.map(log => [
				new Date(log.timestamp).toISOString(),
				log.level || 'CONFIG',
				`"${(log.message || log.change || '').replace(/"/g, '""')}"`
			].join(','))
		].join('\n');

		const blob = new Blob([csv], { type: 'text/csv' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `logs_${new Date().toISOString().split('T')[0]}.csv`;
		a.click();
		URL.revokeObjectURL(url);
	}
</script>

<!-- 🔥 FIX: Popup d'erreur clignotant -->
{#if showErrorPopup && $errorLogs.length > 0}
	{@const latestError = $errorLogs[$errorLogs.length - 1]}
	<div class="error-popup" class:blinking={showErrorPopup}>
		<div class="error-popup-content">
			<div class="error-popup-header">
				<span class="error-icon">🚨</span>
				<h3>Erreur détectée</h3>
				<button class="close-popup-btn" on:click={acknowledgeError}>✕</button>
			</div>
			<div class="error-popup-message">
				<span class="error-time">{formatTime(latestError.timestamp)}</span>
				<span class="error-level">[{latestError.level}]</span>
				<span class="error-text">{stripAnsiCodes(latestError.message)}</span>
			</div>
			<button class="acknowledge-btn" on:click={acknowledgeError}>Acquitter</button>
		</div>
	</div>
{/if}

<div class="log-viewer">
	<!-- Section Erreurs/Warnings -->
	<div class="errors-section">
		<div class="log-header">
			<h3>🚨 Erreurs & Warnings</h3>
			<div class="header-controls">
				<div class="error-badge">{$errorLogs.length} problèmes</div>
				<button class="export-btn" on:click={exportLogs}>📥 Export</button>
			</div>
		</div>

		<div class="log-container errors" bind:this={errorContainer} on:scroll={() => handleScroll(errorContainer, 'error')}>
			{#if $errorLogs.length === 0}
				<div class="no-logs">
					<div class="no-logs-icon">✅</div>
					<div class="no-logs-text">Aucune erreur</div>
				</div>
			{:else}
				{#each $errorLogs as log (log.id)}
					<div class="log-entry" style="border-left-color: {getLogColor(stripAnsiCodes(log.level))}">
						<span class="log-time">{formatTime(log.timestamp)}</span>
						<span class="log-level" style="color: {getLogColor(stripAnsiCodes(log.level))}">[{stripAnsiCodes(log.level)}]</span>
						<span class="log-message">{stripAnsiCodes(log.message)}</span>
					</div>
				{/each}
			{/if}
		</div>

		<div class="log-footer">
			<label class="auto-scroll-toggle">
				<input type="checkbox" bind:checked={autoScrollErrors} />
				<span>Auto-scroll</span>
			</label>
			<div class="log-count">{$errorLogs.length} erreurs/warnings</div>
		</div>
	</div>

	<!-- Section Logs Backend -->
	<div class="logs-section">
		<div class="log-header">
			<h3>📝 Logs Backend</h3>
			<div class="info-badge">{$regularLogs.length} entrées</div>
		</div>

		<div class="log-container" bind:this={logContainer} on:scroll={() => handleScroll(logContainer, 'regular')}>
			{#if $regularLogs.length === 0}
				<div class="no-logs">
					<div class="no-logs-icon">📝</div>
					<div class="no-logs-text">Aucun log</div>
				</div>
			{:else}
				{#each $regularLogs as log (log.id)}
					{@const parsed = parseLogMessage(stripAnsiCodes(log.message))}
					<div class="log-entry" style="border-left-color: {getLogColor(stripAnsiCodes(log.level))}">
						<span class="log-time">{formatTime(log.timestamp)}</span>
						<span class="log-icon">{parsed.icon}</span>
						<span class="log-level" style="color: {getLogColor(stripAnsiCodes(log.level))}">[{stripAnsiCodes(log.level)}]</span>
						<span class="log-message">{parsed.text}</span>
					</div>
				{/each}
			{/if}
		</div>

		<div class="log-footer">
			<label class="auto-scroll-toggle">
				<input type="checkbox" bind:checked={autoScroll} />
				<span>Auto-scroll</span>
			</label>
			<div class="log-count">{$regularLogs.length} logs</div>
		</div>
	</div>
</div>

<style>
	.log-viewer {
		display: flex;
		flex-direction: column;
		gap: 20px;
	}

	.errors-section,
	.logs-section {
		background: #1e2749;
		border-radius: 12px;
		border: 2px solid #2a3a6b;
		display: flex;
		flex-direction: column;
		max-height: 400px;
	}

	.logs-section {
		max-height: 600px;
	}

	.log-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 15px 20px;
		border-bottom: 1px solid #2a3a6b;
		flex-wrap: wrap;
		gap: 10px;
	}

	.header-controls {
		display: flex;
		align-items: center;
		gap: 10px;
		flex-wrap: wrap;
	}

	.level-filter,
	.search-input {
		background: #0a0e27;
		border: 1px solid #2a3a6b;
		color: #fff;
		padding: 6px 12px;
		border-radius: 6px;
		font-size: 13px;
	}

	.search-input {
		min-width: 150px;
	}

	.export-btn {
		background: rgba(0, 255, 136, 0.1);
		border: 1px solid #00ff88;
		color: #00ff88;
		padding: 6px 12px;
		border-radius: 6px;
		font-size: 13px;
		cursor: pointer;
		transition: all 0.3s;
	}

	.export-btn:hover {
		background: rgba(0, 255, 136, 0.2);
	}

	.log-header h3 {
		font-size: 18px;
		color: #00ff88;
		font-weight: bold;
		margin: 0;
	}

	.error-badge {
		background: rgba(255, 68, 68, 0.2);
		color: #ff4444;
		padding: 4px 12px;
		border-radius: 12px;
		font-size: 12px;
		font-weight: bold;
		border: 1px solid #ff4444;
	}

	.info-badge {
		background: rgba(0, 170, 255, 0.2);
		color: #00aaff;
		padding: 4px 12px;
		border-radius: 12px;
		font-size: 12px;
		font-weight: bold;
		border: 1px solid #00aaff;
	}

	.config-badge {
		background: rgba(0, 255, 136, 0.2);
		color: #00ff88;
		padding: 4px 12px;
		border-radius: 12px;
		font-size: 12px;
		font-weight: bold;
		border: 1px solid #00ff88;
	}

	.log-container {
		flex: 1;
		overflow-y: auto;
		padding: 15px;
		background: #0a0e27;
		font-family: 'Courier New', monospace;
		font-size: 13px;
		line-height: 1.6;
	}

	/* Custom scrollbar */
	.log-container::-webkit-scrollbar {
		width: 8px;
	}

	.log-container::-webkit-scrollbar-track {
		background: #1e2749;
	}

	.log-container::-webkit-scrollbar-thumb {
		background: #00ff88;
		border-radius: 4px;
	}

	.log-container::-webkit-scrollbar-thumb:hover {
		background: #00cc6a;
	}

	.log-entry {
		padding: 8px 12px;
		margin-bottom: 5px;
		background: rgba(30, 39, 73, 0.3);
		border-radius: 4px;
		border-left: 3px solid;
		display: flex;
		gap: 10px;
		transition: all 0.2s;
	}

	.log-entry:hover {
		background: rgba(30, 39, 73, 0.6);
	}

	.log-time {
		color: #888;
		flex-shrink: 0;
	}

	.log-icon {
		font-size: 14px;
		flex-shrink: 0;
		width: 20px;
		text-align: center;
	}

	.log-level {
		font-weight: bold;
		flex-shrink: 0;
		min-width: 80px;
	}

	.log-message {
		color: #fff;
		flex: 1;
		word-break: break-word;
	}

	.config-entry {
		padding: 8px 12px;
		margin-bottom: 5px;
		background: rgba(0, 255, 136, 0.05);
		border-radius: 4px;
		border-left: 3px solid #00ff88;
		display: flex;
		gap: 10px;
		align-items: center;
		transition: all 0.2s;
	}

	.config-entry:hover {
		background: rgba(0, 255, 136, 0.1);
	}

	.config-time {
		color: #888;
		flex-shrink: 0;
	}

	.config-key {
		color: #00aaff;
		font-weight: bold;
		flex-shrink: 0;
		font-family: 'Courier New', monospace;
	}

	.config-arrow {
		color: #00ff88;
		font-weight: bold;
	}

	.config-change {
		color: #fff;
		flex: 1;
		font-family: 'Courier New', monospace;
	}

	.no-logs {
		text-align: center;
		padding: 60px 20px;
	}

	.no-logs-icon {
		font-size: 48px;
		margin-bottom: 15px;
	}

	.no-logs-text {
		font-size: 16px;
		color: #888;
	}

	.log-footer {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 12px 20px;
		border-top: 1px solid #2a3a6b;
		background: rgba(10, 14, 39, 0.5);
	}

	.auto-scroll-toggle {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 13px;
		color: #888;
		cursor: pointer;
	}

	.auto-scroll-toggle input {
		cursor: pointer;
	}

	.log-count {
		font-size: 12px;
		color: #888;
	}

	/* 🔥 FIX: Popup d'erreur clignotant */
	.error-popup {
		position: fixed;
		top: 20px;
		right: 20px;
		z-index: 10000;
		background: linear-gradient(135deg, #ff4444 0%, #cc0000 100%);
		border: 3px solid #fff;
		border-radius: 12px;
		padding: 0;
		box-shadow: 0 8px 32px rgba(255, 68, 68, 0.6);
		min-width: 400px;
		max-width: 600px;
	}

	.error-popup.blinking {
		animation: blink 1s ease-in-out infinite;
	}

	@keyframes blink {
		0%, 100% {
			opacity: 1;
			transform: scale(1);
		}
		50% {
			opacity: 0.8;
			transform: scale(1.02);
		}
	}

	.error-popup-content {
		background: #1e2749;
		border-radius: 10px;
		padding: 20px;
		border: 2px solid #ff4444;
	}

	.error-popup-header {
		display: flex;
		align-items: center;
		gap: 12px;
		margin-bottom: 15px;
		padding-bottom: 15px;
		border-bottom: 2px solid rgba(255, 68, 68, 0.3);
	}

	.error-icon {
		font-size: 32px;
	}

	.error-popup-header h3 {
		flex: 1;
		color: #ff4444;
		font-size: 20px;
		font-weight: bold;
		margin: 0;
		text-transform: uppercase;
	}

	.close-popup-btn {
		background: rgba(255, 68, 68, 0.2);
		border: 1px solid #ff4444;
		color: #ff4444;
		width: 32px;
		height: 32px;
		border-radius: 50%;
		cursor: pointer;
		font-size: 18px;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.3s;
	}

	.close-popup-btn:hover {
		background: rgba(255, 68, 68, 0.4);
		transform: scale(1.1);
	}

	.error-popup-message {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin-bottom: 15px;
		padding: 12px;
		background: rgba(0, 0, 0, 0.3);
		border-radius: 8px;
		font-family: 'Courier New', monospace;
	}

	.error-time {
		color: #888;
		font-size: 11px;
	}

	.error-level {
		color: #ff4444;
		font-weight: bold;
		font-size: 12px;
	}

	.error-text {
		color: #fff;
		font-size: 13px;
		line-height: 1.5;
	}

	.acknowledge-btn {
		width: 100%;
		background: linear-gradient(135deg, #ff4444 0%, #cc0000 100%);
		border: 2px solid #fff;
		color: #fff;
		padding: 12px 24px;
		border-radius: 8px;
		font-size: 14px;
		font-weight: bold;
		cursor: pointer;
		text-transform: uppercase;
		transition: all 0.3s;
	}

	.acknowledge-btn:hover {
		transform: translateY(-2px);
		box-shadow: 0 6px 20px rgba(255, 68, 68, 0.5);
	}

	/* Mobile */
	@media (max-width: 768px) {
		.error-popup {
			left: 10px;
			right: 10px;
			min-width: auto;
		}

		.errors-section,
		.config-section,
		.logs-section {
			max-height: 300px;
		}

		.log-entry,
		.config-entry {
			flex-direction: column;
			gap: 5px;
		}

		.log-level {
			min-width: auto;
		}
	}
</style>
