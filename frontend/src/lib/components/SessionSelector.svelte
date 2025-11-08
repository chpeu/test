<script>
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

<div class="session-selector">
	<div class="selector-header">
		<h3>📂 Sessions</h3>
		<button class="btn-create" on:click={() => (showCreateModal = true)}>➕ New</button>
	</div>

	{#if $sessionsError}
		<div class="error-banner">⚠️ {$sessionsError}</div>
	{/if}

	<div class="session-list">
		{#if $sessions && $sessions.length > 0}
			{#each $sessions as session (session.session_id)}
				<div
					class="session-item"
					class:active={session.session_id === $activeSessionId}
					role="button"
					tabindex="0"
					on:click={() => handleSelectSession(session.session_id)}
					on:keydown={(e) => e.key === 'Enter' && handleSelectSession(session.session_id)}
				>
					<div class="session-main">
						<div class="session-info">
							<span class="session-status" style="color: {getStatusColor(session.status)}">
								{getStatusIcon(session.status)}
							</span>
							<span class="session-name">{session.name}</span>
						</div>

						<div class="session-controls" role="group" on:click|stopPropagation>
							{#if session.status === 'stopped'}
								<button
									class="control-btn start"
									on:click={() => handleStart(session.session_id)}
									title="Start"
								>
									▶️
								</button>
							{/if}

							{#if session.status === 'running'}
								<button
									class="control-btn pause"
									on:click={() => handlePause(session.session_id)}
									title="Pause"
								>
									⏸️
								</button>
								<button
									class="control-btn stop"
									on:click={() => handleStop(session.session_id)}
									title="Stop"
								>
									⏹️
								</button>
							{/if}

							{#if session.status === 'paused'}
								<button
									class="control-btn resume"
									on:click={() => handleResume(session.session_id)}
									title="Resume"
								>
									▶️
								</button>
								<button
									class="control-btn stop"
									on:click={() => handleStop(session.session_id)}
									title="Stop"
								>
									⏹️
								</button>
							{/if}

							{#if session.status === 'stopped'}
								<button
									class="control-btn delete"
									on:click={() => handleDelete(session.session_id)}
									title="Delete"
								>
									🗑️
								</button>
							{/if}
						</div>
					</div>

					<div class="session-stats">
						<span class="stat">{session.stats?.trades || 0} trades</span>
						<span class="stat" class:profit={session.stats?.pnl >= 0} class:loss={session.stats?.pnl < 0}>
							{(session.stats?.pnl || 0).toFixed(2)} USDT
						</span>
					</div>

					<div class="session-details">
						<span class="detail">Pairs: {session.pairs?.join(', ') || 'N/A'}</span>
						<span class="detail">Strategy: {session.strategy || 'N/A'}</span>
					</div>
				</div>
			{/each}
		{:else}
			<div class="empty-state">
				<span class="empty-icon">📭</span>
				<p>No sessions yet</p>
				<p class="hint">Create a session to get started</p>
			</div>
		{/if}
	</div>

	{#if showCreateModal}
		<div
			class="modal-overlay"
			role="button"
			tabindex="0"
			on:click={() => (showCreateModal = false)}
			on:keydown={(e) => e.key === 'Escape' && (showCreateModal = false)}
		>
			<div class="modal-content" role="dialog" on:click|stopPropagation>
				<h3>Create New Session</h3>

				<div class="form-group">
					<label for="session-name">Session Name</label>
					<input
						id="session-name"
						type="text"
						placeholder="e.g., BTC Scalping"
						bind:value={newSessionName}
					/>
				</div>

				<div class="form-group">
					<label for="session-pairs">Trading Pairs (comma-separated)</label>
					<input
						id="session-pairs"
						type="text"
						placeholder="e.g., BTC/USDT, ETH/USDT, SOL/USDT"
						bind:value={newSessionPairs}
					/>
				</div>

				<div class="form-group">
					<label for="session-strategy">Strategy</label>
					<select id="session-strategy" bind:value={newSessionStrategy}>
						<option value="scalping">Scalping</option>
						<option value="swing">Swing Trading</option>
						<option value="momentum">Momentum</option>
					</select>
				</div>

				<div class="modal-actions">
					<button class="btn-primary" on:click={handleCreate}>Create</button>
					<button class="btn-secondary" on:click={() => (showCreateModal = false)}>
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
