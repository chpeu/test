<script>
	import { formatUSDT } from '$lib/utils/format';
	import {
		sessions,
		activeSessionId,
		sessionsError,
		createSession,
		startSession,
		stopSession,
		pauseSession,
		resumeSession,
		deleteSession,
		selectSession,
		loadSessions
	} from '$lib/stores/sessions';
	import { onMount } from 'svelte';

	let showCreateModal = false;
	let newSessionName = '';
	let newSessionPairs = '';
	let newSessionStrategy = 'scalping';

	onMount(() => {
		// Charger les sessions au démarrage
		loadSessions();
	});

	function handleSelectSession(sessionId) {
		selectSession(sessionId);
	}

	async function handleStart(sessionId) {
		const success = await startSession(sessionId);
		if (success) {
			console.log(`Session ${sessionId} started`);
		}
	}

	async function handleStop(sessionId) {
		const success = await stopSession(sessionId);
		if (success) {
			console.log(`Session ${sessionId} stopped`);
		}
	}

	async function handlePause(sessionId) {
		const success = await pauseSession(sessionId);
		if (success) {
			console.log(`Session ${sessionId} paused`);
		}
	}

	async function handleResume(sessionId) {
		const success = await resumeSession(sessionId);
		if (success) {
			console.log(`Session ${sessionId} resumed`);
		}
	}

	async function handleDelete(sessionId) {
		if (confirm(`Are you sure you want to delete session "${sessionId}"?`)) {
			const success = await deleteSession(sessionId);
			if (success) {
				console.log(`Session ${sessionId} deleted`);
			}
		}
	}

	async function handleCreate() {
		if (!newSessionName || !newSessionPairs) {
			alert('Please fill in all fields');
			return;
		}

		const pairs = newSessionPairs.split(',').map(p => p.trim()).filter(p => p);

		if (pairs.length === 0) {
			alert('Please enter at least one trading pair');
			return;
		}

		const session = await createSession({
			session_id: `session_${Date.now()}`,
			name: newSessionName,
			pairs: pairs,
			strategy: newSessionStrategy,
			config: {}
		});

		if (session) {
			// Reset form
			showCreateModal = false;
			newSessionName = '';
			newSessionPairs = '';
			newSessionStrategy = 'scalping';
		}
	}

	function getStatusColor(status) {
		if (status === 'running') return '#00ff88';
		if (status === 'paused') return '#ffaa00';
		return '#888888';
	}

	function getStatusIcon(status) {
		if (status === 'running') return '🟢';
		if (status === 'paused') return '🟡';
		return '⚫';
	}
</script>

<div class="session-selector" data-debug-name="sessionSelector">
	<div class="selector-header" data-debug-name="selectorHeader">
		<h3 data-debug-name="sessionsTitle">📂 Sessions</h3>
		<button class="btn-create" on:click={() => (showCreateModal = true)} data-debug-name="btnCreate">➕ New</button>
	</div>

	{#if $sessionsError}
		<div class="error-banner" data-debug-name="sessionsError">⚠️ {$sessionsError}</div>
	{/if}

	<div class="session-list" data-debug-name="sessionList">
		{#if $sessions && $sessions.length > 0}
			{#each $sessions as session (session.session_id)}
				<div
					class="session-item"
					class:active={session.session_id === $activeSessionId}
					role="button"
					tabindex="0"
					on:click={() => handleSelectSession(session.session_id)}
					on:keydown={(e) => e.key === 'Enter' && handleSelectSession(session.session_id)}
					data-debug-name="sessionItem.{session.session_id}"
				>
					<div class="session-main" data-debug-name="sessionMain">
						<div class="session-info" data-debug-name="sessionInfo">
							<span class="session-status" style="color: {getStatusColor(session.status)}" data-debug-name="session.status">
								{getStatusIcon(session.status)}
							</span>
							<span class="session-name" data-debug-name="session.name">{session.name}</span>
						</div>

						<div class="session-controls" role="group" on:click|stopPropagation data-debug-name="sessionControls">
							{#if session.status === 'stopped'}
								<button
									class="control-btn start"
									on:click={() => handleStart(session.session_id)}
									title="Start"
									data-debug-name="controlBtn.start"
								>
									▶️
								</button>
							{/if}

							{#if session.status === 'running'}
								<button
									class="control-btn pause"
									on:click={() => handlePause(session.session_id)}
									title="Pause"
									data-debug-name="controlBtn.pause"
								>
									⏸️
								</button>
								<button
									class="control-btn stop"
									on:click={() => handleStop(session.session_id)}
									title="Stop"
									data-debug-name="controlBtn.stop"
								>
									⏹️
								</button>
							{/if}

							{#if session.status === 'paused'}
								<button
									class="control-btn resume"
									on:click={() => handleResume(session.session_id)}
									title="Resume"
									data-debug-name="controlBtn.resume"
								>
									▶️
								</button>
								<button
									class="control-btn stop"
									on:click={() => handleStop(session.session_id)}
									title="Stop"
									data-debug-name="controlBtn.stop"
								>
									⏹️
								</button>
							{/if}

							{#if session.status === 'stopped'}
								<button
									class="control-btn delete"
									on:click={() => handleDelete(session.session_id)}
									title="Delete"
									data-debug-name="controlBtn.delete"
								>
									🗑️
								</button>
							{/if}
						</div>
					</div>

					<div class="session-stats" data-debug-name="sessionStats">
						<span class="stat" data-debug-name="session.stats.trades">{session.stats?.trades || 0} trades</span>
						<span class="stat" class:profit={session.stats?.pnl >= 0} class:loss={session.stats?.pnl < 0} data-debug-name="session.stats.pnl">
							{formatUSDT(session.stats?.pnl || 0)} USDT
						</span>
					</div>

					<div class="session-details" data-debug-name="sessionDetails">
						<span class="detail" data-debug-name="session.pairs">Pairs: {session.pairs?.join(', ') || 'N/A'}</span>
						<span class="detail" data-debug-name="session.strategy">Strategy: {session.strategy || 'N/A'}</span>
					</div>
				</div>
			{/each}
		{:else}
			<div class="empty-state" data-debug-name="emptyState">
				<span class="empty-icon" data-debug-name="emptyIcon">📭</span>
				<p data-debug-name="emptyMessage">No sessions yet</p>
				<p class="hint" data-debug-name="emptyHint">Create a session to get started</p>
			</div>
		{/if}
	</div>

		{#if showCreateModal}
		<div
			class="modal-overlay"
			role="button"
			tabindex="0"
			on:click|stopPropagation={() => (showCreateModal = false)}
			on:keydown={(e) => {
				if (e.key === 'Escape') {
					showCreateModal = false;
				}
			}}
			data-debug-name="createModal.overlay"
		>
			<div class="modal-content" role="dialog" on:click|stopPropagation data-debug-name="createModal.content">
				<h3 data-debug-name="createModal.title">Create New Session</h3>

				<div class="form-group" data-debug-name="formGroup.name">
					<label for="session-name" data-debug-name="label.sessionName">Session Name</label>
					<input
						id="session-name"
						type="text"
						placeholder="e.g., BTC Scalping"
						bind:value={newSessionName}
						data-debug-name="input.sessionName"
					/>
				</div>

				<div class="form-group" data-debug-name="formGroup.pairs">
					<label for="session-pairs" data-debug-name="label.sessionPairs">Trading Pairs (comma-separated)</label>
					<input
						id="session-pairs"
						type="text"
						placeholder="e.g., BTC/USDT, ETH/USDT, SOL/USDT"
						bind:value={newSessionPairs}
						data-debug-name="input.sessionPairs"
					/>
				</div>

				<div class="form-group" data-debug-name="formGroup.strategy">
					<label for="session-strategy" data-debug-name="label.sessionStrategy">Strategy</label>
					<select id="session-strategy" bind:value={newSessionStrategy} data-debug-name="select.sessionStrategy">
						<option value="scalping" data-debug-name="option.scalping">Scalping</option>
						<option value="swing" data-debug-name="option.swing">Swing Trading</option>
						<option value="momentum" data-debug-name="option.momentum">Momentum</option>
					</select>
				</div>

				<div class="modal-actions" data-debug-name="modalActions">
					<button class="btn-primary" on:click={handleCreate} data-debug-name="btnCreateSession">Create</button>
					<button class="btn-secondary" on:click={() => (showCreateModal = false)} data-debug-name="btnCancel">
						Cancel
					</button>
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	.session-selector {
		background: var(--bg-secondary);
		border-radius: 12px;
		padding: 20px;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
	}

	.selector-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 16px;
		padding-bottom: 12px;
		border-bottom: 1px solid var(--bg-tertiary);
	}

	.selector-header h3 {
		font-size: 18px;
		color: var(--accent-blue);
		margin: 0;
	}

	.btn-create {
		background: var(--accent-green);
		color: var(--bg-primary);
		border: none;
		padding: 8px 16px;
		border-radius: 6px;
		font-size: 13px;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.3s ease;
	}

	.btn-create:hover {
		background: #00cc6a;
		transform: translateY(-2px);
	}

	.error-banner {
		background: rgba(255, 68, 68, 0.1);
		border: 1px solid var(--accent-red);
		color: var(--accent-red);
		padding: 10px 12px;
		border-radius: 6px;
		margin-bottom: 12px;
		font-size: 13px;
	}

	.session-list {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.session-item {
		background: var(--bg-primary);
		border: 1px solid var(--bg-tertiary);
		border-radius: 8px;
		padding: 14px;
		cursor: pointer;
		transition: all 0.3s ease;
	}

	.session-item:hover {
		border-color: var(--accent-green);
		box-shadow: 0 4px 12px rgba(0, 255, 136, 0.1);
	}

	.session-item.active {
		border-color: var(--accent-green);
		background: rgba(0, 255, 136, 0.05);
	}

	.session-main {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 8px;
	}

	.session-info {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.session-status {
		font-size: 16px;
	}

	.session-name {
		font-size: 14px;
		font-weight: 500;
		color: var(--text-primary);
	}

	.session-controls {
		display: flex;
		gap: 6px;
	}

	.control-btn {
		background: transparent;
		border: none;
		font-size: 16px;
		cursor: pointer;
		padding: 4px 8px;
		border-radius: 4px;
		transition: background 0.2s;
	}

	.control-btn:hover {
		background: rgba(255, 255, 255, 0.1);
	}

	.session-stats {
		display: flex;
		gap: 12px;
		font-size: 13px;
		margin-bottom: 6px;
	}

	.session-stats .stat {
		padding: 4px 8px;
		background: var(--bg-tertiary);
		border-radius: 4px;
	}

	.session-stats .stat.profit {
		background: rgba(0, 255, 136, 0.1);
		color: var(--accent-green);
	}

	.session-stats .stat.loss {
		background: rgba(255, 68, 68, 0.1);
		color: var(--accent-red);
	}

	.session-details {
		display: flex;
		flex-direction: column;
		gap: 4px;
		font-size: 12px;
		color: var(--text-secondary);
	}

	.empty-state {
		text-align: center;
		padding: 40px 20px;
		color: var(--text-secondary);
	}

	.empty-icon {
		font-size: 48px;
		display: block;
		margin-bottom: 12px;
		opacity: 0.5;
	}

	.empty-state p {
		margin: 6px 0;
	}

	.empty-state .hint {
		font-size: 11px;
		font-style: italic;
	}

	/* Modal */
	.modal-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.7);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
		pointer-events: auto; /* 🔥 FIX: Permettre les clics sur le modal */
	}

	.modal-content {
		background: var(--bg-secondary);
		border: 1px solid var(--accent-green);
		border-radius: 12px;
		padding: 24px;
		max-width: 500px;
		width: 90%;
	}

	.modal-content h3 {
		color: var(--accent-green);
		margin-bottom: 20px;
	}

	.form-group {
		margin-bottom: 16px;
	}

	.form-group label {
		display: block;
		color: var(--text-primary);
		font-size: 13px;
		margin-bottom: 6px;
		font-weight: 500;
	}

	.form-group input,
	.form-group select {
		width: 100%;
		background: var(--bg-primary);
		border: 1px solid var(--bg-tertiary);
		color: var(--text-primary);
		padding: 10px 12px;
		border-radius: 6px;
		font-family: 'Courier New', monospace;
		font-size: 13px;
	}

	.form-group input:focus,
	.form-group select:focus {
		border-color: var(--accent-green);
		outline: none;
	}

	.modal-actions {
		display: flex;
		gap: 10px;
		margin-top: 20px;
	}

	.btn-primary,
	.btn-secondary {
		flex: 1;
		padding: 10px 16px;
		border: none;
		border-radius: 6px;
		font-size: 14px;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.3s ease;
	}

	.btn-primary {
		background: var(--accent-green);
		color: var(--bg-primary);
	}

	.btn-primary:hover {
		background: #00cc6a;
	}

	.btn-secondary {
		background: var(--bg-tertiary);
		color: var(--text-primary);
	}

	.btn-secondary:hover {
		background: var(--bg-secondary);
	}

	@media (max-width: 768px) {
		.session-main {
			flex-direction: column;
			align-items: flex-start;
			gap: 8px;
		}

		.session-controls {
			width: 100%;
			justify-content: flex-end;
		}
	}
</style>
