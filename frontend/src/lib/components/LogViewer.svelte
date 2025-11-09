<script>
	import { onMount, afterUpdate } from 'svelte';
	import { recentLogs, errorCount } from '$lib/stores/logs';
	import { derived } from 'svelte/store';

	let logContainer;
	let errorContainer;
	let autoScroll = true;
	let autoScrollErrors = true;

	// Séparer les erreurs/warnings des autres logs
	const errorLogs = derived(recentLogs, $logs =>
		$logs.filter(log => log.level === 'ERROR' || log.level === 'WARNING' || log.level === 'CRITICAL')
	);

	const regularLogs = derived(recentLogs, $logs =>
		$logs.filter(log => log.level !== 'ERROR' && log.level !== 'WARNING' && log.level !== 'CRITICAL')
	);

	// Auto-scroll to bottom when new logs arrive
	afterUpdate(() => {
		if (autoScroll && logContainer) {
			logContainer.scrollTop = logContainer.scrollHeight;
		}
		if (autoScrollErrors && errorContainer) {
			errorContainer.scrollTop = errorContainer.scrollHeight;
		}
	});

	function handleScroll(container, isError = false) {
		if (!container) return;
		const { scrollTop, scrollHeight, clientHeight } = container;
		// Auto-scroll if user is within 50px of bottom
		const isAtBottom = scrollTop + clientHeight >= scrollHeight - 50;
		if (isError) {
			autoScrollErrors = isAtBottom;
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
</script>

<div class="log-viewer">
	<!-- Section Erreurs/Warnings -->
	<div class="errors-section">
		<div class="log-header">
			<h3>🚨 Erreurs & Warnings</h3>
			<div class="error-badge">{$errorLogs.length} problèmes</div>
		</div>

		<div class="log-container errors" bind:this={errorContainer} on:scroll={() => handleScroll(errorContainer, true)}>
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

	<!-- Section Logs Standards -->
	<div class="logs-section">
		<div class="log-header">
			<h3>📝 Logs Backend</h3>
			<div class="info-badge">{$regularLogs.length} entrées</div>
		</div>

		<div class="log-container" bind:this={logContainer} on:scroll={() => handleScroll(logContainer, false)}>
			{#if $regularLogs.length === 0}
				<div class="no-logs">
					<div class="no-logs-icon">📝</div>
					<div class="no-logs-text">Aucun log</div>
				</div>
			{:else}
				{#each $regularLogs as log (log.id)}
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

	.log-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 15px 20px;
		border-bottom: 1px solid #2a3a6b;
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

	/* Mobile */
	@media (max-width: 768px) {
		.errors-section,
		.logs-section {
			max-height: 300px;
		}

		.log-entry {
			flex-direction: column;
			gap: 5px;
		}

		.log-level {
			min-width: auto;
		}
	}
</style>
