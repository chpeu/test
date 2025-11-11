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
	// 🔥 FIX: Erreurs uniquement pour la section "Erreurs" (WARNING exclu)
	const errorLogs = derived(recentLogs, $logs =>
		$logs.filter(log => log.level === 'ERROR' || log.level === 'CRITICAL')
	);

	// 🔥 FIX: Tous les logs backend (INFO, DEBUG, etc.) avec couleurs (exclure ERROR, CRITICAL et WARNING)
	const regularLogs = derived(recentLogs, $logs =>
		$logs.filter(log => log.level !== 'ERROR' && log.level !== 'CRITICAL' && log.level !== 'WARNING')
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
		// 🔥 FIX: Couleurs identiques à la console backend (ColoredFormatter dans utils/logger.py)
		switch (level) {
			case 'ERROR':
				return '#ff4444'; // Rouge (#ff4444)
			case 'CRITICAL':
				return '#ff6666'; // Rouge clair (#ff6666)
			case 'WARNING':
				return '#ffaa00'; // Jaune (#ffaa00)
			case 'INFO':
				return '#00ff88'; // Vert (#00ff88)
			case 'DEBUG':
				return '#00aaff'; // Cyan (#00aaff)
			default:
				return '#fff';
		}
	}

	function formatTime(timestamp) {
		if (!timestamp) return '';
		// 🔥 FIX: Si timestamp est déjà au format HH:MM:SS, le retourner tel quel
		if (typeof timestamp === 'string' && /^\d{2}:\d{2}:\d{2}$/.test(timestamp)) {
			return timestamp;
		}
		const date = new Date(timestamp);
		return date.toLocaleTimeString('en-US', { hour12: false });
	}

	function stripAnsiCodes(text) {
		if (!text) return '';
		// Supprimer les codes ANSI de couleur: \x1b[XXm ou [XXm
		return text.replace(/\x1b\[\d+m/g, '').replace(/\[\d+m/g, '');
	}

	// 🔥 FIX: Convertir les codes ANSI en spans HTML avec couleurs (identique à la console backend)
	// Dans la console, seul le timestamp et le niveau sont colorés, le reste du texte est blanc
	function ansiToHtml(text) {
		if (!text) return '';
		
		// 🔥 FIX: Supprimer d'abord tous les codes ANSI pour obtenir le texte brut
		const textWithoutAnsi = stripAnsiCodes(text);
		
		// 🔥 FIX: Extraire et colorer uniquement le timestamp et le niveau, le reste en blanc
		// Format attendu: [HH:MM:SS] INFO: message ou [HH:MM:SS] INFO - message
		// Pattern: [timestamp] LEVEL: ou [timestamp] LEVEL -
		const logPattern = /^(\[\d{2}:\d{2}:\d{2}\])\s*(\[?\w+\]?)\s*([:-])\s*(.*)$/;
		const match = textWithoutAnsi.match(logPattern);
		
		if (match) {
			const timestamp = match[1]; // [HH:MM:SS]
			const level = match[2].replace(/[\[\]]/g, ''); // INFO, WARNING, etc. (sans crochets)
			const separator = match[3]; // : ou -
			const message = match[4]; // Le reste du message
			
			// Déterminer la couleur du niveau
			const levelColor = getLogColor(level);
			
			// Construire le HTML avec timestamp et niveau colorés, message en blanc
			return `<span style="color: #00ff88;">${timestamp}</span> <span style="color: ${levelColor};">${level}</span>${separator} <span style="color: #fff;">${message}</span>`;
		}
		
		// Si le pattern ne correspond pas, retourner le texte en blanc
		return `<span style="color: #fff;">${textWithoutAnsi}</span>`;
	}

	// 🔥 FIX: Extraire les emojis et couleurs des logs backend
	function parseLogMessage(message) {
		if (!message) return { icon: '', text: message, fullText: message };
		// 🔥 FIX: Extraire les emojis au début du message (support Unicode complet)
		// Pattern pour capturer tous les emojis: ✅📊❌⚠️🔍 etc.
		const emojiPattern = /^([\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{1F1E0}-\u{1F1FF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FA6F}\u{1FA70}-\u{1FAFF}]+)/u;
		const emojiMatch = message.match(emojiPattern);
		const icon = emojiMatch ? emojiMatch[0] : '';
		// Retirer l'emoji du texte pour éviter la duplication, mais garder le message complet pour ansiToHtml
		const textWithoutEmoji = emojiMatch ? message.slice(emojiMatch[0].length).trim() : message;
		return { icon, text: textWithoutEmoji, fullText: message };
	}

	function exportLogs() {
		import('xlsx').then(XLSX => {
			const allLogs = [...$errorLogs, ...$regularLogs];
			
			// Headers
			const headers = ['Timestamp', 'Level', 'Message'];
			
			// Convert logs to rows
			const rows = allLogs.map(log => [
				log.timestamp || new Date().toISOString(),
				log.level || 'CONFIG',
				stripAnsiCodes(log.message || log.change || '')
			]);
			
			// Create workbook and worksheet
			const wb = XLSX.utils.book_new();
			const ws = XLSX.utils.aoa_to_sheet([headers, ...rows]);
			
			// Set column widths
			ws['!cols'] = [
				{ wch: 12 }, // Timestamp
				{ wch: 10 }, // Level
				{ wch: 80 }  // Message
			];
			
			// Style header row
			const headerRange = XLSX.utils.decode_range(ws['!ref'] || 'A1');
			for (let col = headerRange.s.c; col <= headerRange.e.c; col++) {
				const cellAddress = XLSX.utils.encode_cell({ r: 0, c: col });
				if (!ws[cellAddress]) continue;
				ws[cellAddress].s = {
					font: { bold: true },
					fill: { fgColor: { rgb: 'E0E0E0' } },
					alignment: { horizontal: 'center', vertical: 'center' }
				};
			}
			
			// Add worksheet to workbook
			XLSX.utils.book_append_sheet(wb, ws, 'Logs');
			
			// Write file
			const filename = `logs_${new Date().toISOString().split('T')[0]}.xlsx`;
			XLSX.writeFile(wb, filename);
			console.log(`✅ Exported: ${filename}`);
		}).catch(err => {
			console.error('❌ Erreur export logs:', err);
			alert('⚠️ Erreur lors de l\'export des logs');
		});
	}
</script>

<!-- 🔥 FIX: Popup d'erreur déplacé dans +page.svelte pour affichage sur toutes les pages -->

<div class="log-viewer" data-debug-name="logViewer">
	<!-- Section Erreurs/Warnings -->
	<div class="errors-section" data-debug-name="logViewer.errors">
		<div class="log-header" data-debug-name="logViewer.errors.header">
			<h3 data-debug-name="logViewer.errors.title">🚨 Erreurs</h3>
			<div class="header-controls" data-debug-name="logViewer.errors.controls">
				<div class="error-badge" data-debug-name="errorLogs.length">{$errorLogs.length} erreurs</div>
				<button class="export-btn" on:click={exportLogs} data-debug-name="logViewer.exportButton">📥 Export</button>
			</div>
		</div>

		<div class="log-container errors" bind:this={errorContainer} on:scroll={() => handleScroll(errorContainer, 'error')} data-debug-name="logViewer.errors.container">
			{#if $errorLogs.length === 0}
				<div class="no-logs" data-debug-name="logViewer.errors.empty">
					<div class="no-logs-icon" data-debug-name="logViewer.errors.empty.icon">✅</div>
					<div class="no-logs-text" data-debug-name="logViewer.errors.empty.text">Aucune erreur</div>
				</div>
			{:else}
				{#each $errorLogs as log (log.id)}
					{@const parsed = parseLogMessage(log.message || '')}
					{@const hasAnsi = log.message && (log.message.includes('\x1b[') || log.message.includes('[32m') || log.message.includes('[31m') || log.message.includes('[33m') || log.message.includes('[36m'))}
					<div class="log-entry" style="border-left-color: {getLogColor(stripAnsiCodes(log.level))}" data-debug-name="errorLogs[{log.id}]">
						<span class="log-time" data-debug-name="log.timestamp">{formatTime(log.timestamp)}</span>
						{#if parsed.icon}
							<span class="log-icon" data-debug-name="log.icon">{parsed.icon}</span>
						{/if}
						<span class="log-level" style="color: {getLogColor(stripAnsiCodes(log.level))}" data-debug-name="log.level">[{stripAnsiCodes(log.level)}]</span>
						{#if hasAnsi}
							<span class="log-message" data-debug-name="log.message">{@html ansiToHtml(parsed.fullText || log.message)}</span>
						{:else}
							<span class="log-message" data-debug-name="log.message">{parsed.text || log.message}</span>
						{/if}
						{#if log.detail}
							<span class="log-detail" data-debug-name="log.detail">{log.detail}</span>
						{/if}
					</div>
				{/each}
			{/if}
		</div>

		<div class="log-footer" data-debug-name="logViewer.errors.footer">
			<label class="auto-scroll-toggle" data-debug-name="logViewer.errors.autoScroll">
				<input type="checkbox" bind:checked={autoScrollErrors} data-debug-name="autoScrollErrors" />
				<span data-debug-name="autoScrollErrors">Auto-scroll</span>
			</label>
			<div class="log-count" data-debug-name="errorLogs.length">{$errorLogs.length} erreurs</div>
		</div>
	</div>

	<!-- Section Logs Backend -->
	<div class="logs-section" data-debug-name="logViewer.backend">
		<div class="log-header" data-debug-name="logViewer.backend.header">
			<h3 data-debug-name="logViewer.backend.title">📝 Logs Backend</h3>
			<div class="info-badge" data-debug-name="regularLogs.length">{$regularLogs.length} entrées</div>
		</div>

		<div class="log-container" bind:this={logContainer} on:scroll={() => handleScroll(logContainer, 'regular')} data-debug-name="logViewer.backend.container">
			{#if $regularLogs.length === 0}
				<div class="no-logs" data-debug-name="logViewer.backend.empty">
					<div class="no-logs-icon" data-debug-name="logViewer.backend.empty.icon">📝</div>
					<div class="no-logs-text" data-debug-name="logViewer.backend.empty.text">Aucun log</div>
				</div>
			{:else}
				{#each $regularLogs as log (log.id)}
					{@const parsed = parseLogMessage(log.message || '')}
					{@const hasAnsi = log.message && (log.message.includes('\x1b[') || log.message.includes('[32m') || log.message.includes('[31m') || log.message.includes('[33m') || log.message.includes('[36m'))}
					<div class="log-entry" style="border-left-color: {getLogColor(stripAnsiCodes(log.level))}" data-debug-name="regularLogs[{log.id}]">
						{#if hasAnsi}
							<!-- 🔥 FIX: Reconstruire le format [HH:MM:SS] LEVEL - message et colorer uniquement timestamp et niveau -->
							{@const formattedLog = `[${formatTime(log.timestamp)}] ${log.level} - ${parsed.text || log.message}`}
							<span class="log-message" data-debug-name="log.message">{@html ansiToHtml(formattedLog)}</span>
						{:else}
							<!-- Si pas de codes ANSI, afficher timestamp, niveau et message séparément -->
							<span class="log-time" data-debug-name="log.timestamp">{formatTime(log.timestamp)}</span>
							{#if parsed.icon}
								<span class="log-icon" data-debug-name="log.icon">{parsed.icon}</span>
							{/if}
							<span class="log-level" style="color: {getLogColor(stripAnsiCodes(log.level))}" data-debug-name="log.level">[{stripAnsiCodes(log.level)}]</span>
							<span class="log-message" data-debug-name="log.message">{parsed.text || log.message}</span>
						{/if}
					</div>
				{/each}
			{/if}
		</div>

		<div class="log-footer" data-debug-name="logViewer.backend.footer">
			<label class="auto-scroll-toggle" data-debug-name="logViewer.backend.autoScroll">
				<input type="checkbox" bind:checked={autoScroll} data-debug-name="autoScroll" />
				<span data-debug-name="autoScroll">Auto-scroll</span>
			</label>
			<div class="log-count" data-debug-name="regularLogs.length">{$regularLogs.length} logs</div>
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
		font-family: 'Courier New', monospace;
		font-size: 12px;
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
		font-family: 'Courier New', monospace;
		font-size: 12px;
	}

	.log-message {
		color: #fff;
		flex: 1;
		word-break: break-word;
		font-family: 'Courier New', monospace;
		font-size: 13px;
		line-height: 1.5;
	}

	.log-detail {
		color: #888;
		font-size: 12px;
		margin-left: 10px;
		flex-shrink: 0;
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

	/* 🔥 FIX: Styles du popup d'erreur déplacés dans +page.svelte pour affichage global */

	/* Mobile */
	@media (max-width: 768px) {
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
