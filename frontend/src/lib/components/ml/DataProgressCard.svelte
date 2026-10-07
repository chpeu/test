<script>
	export let stats = {};

	$: tradesCount = stats.trades_count || 0;
	$: targetTrades = stats.target_trades || 500;
	$: progressPct = stats.progress_pct || 0;
	$: nextMilestone = stats.next_milestone || null;
	$: readiness = stats.readiness || {};

	// Milestones
	const milestones = [
		{ name: 'Exploratory', threshold: 10, icon: '📊', color: 'var(--accent-green-strong)' },
		{ name: 'Features', threshold: 30, icon: '🔍', color: 'var(--accent-blue)' },
		{ name: 'XGBoost', threshold: 50, icon: '🌲', color: 'var(--accent-purple)' },
		{ name: 'GRU', threshold: 200, icon: '🧠', color: 'var(--accent-purple)' },
		{ name: 'PPO', threshold: 500, icon: '🎮', color: 'var(--accent-orange)' }
	];

	function getMilestoneStatus(threshold) {
		return tradesCount >= threshold;
	}
</script>

<div class="progress-card">
	<div class="card-header">
		<h3>📈 Progression Collecte de Données</h3>
		<div class="count-badge">{tradesCount} / {targetTrades} trades</div>
	</div>

	<!-- Barre progression principale -->
	<div class="main-progress">
		<div class="progress-bar">
			<div class="progress-fill" style="width: {progressPct}%"></div>
		</div>
		<div class="progress-label">{progressPct.toFixed(1)}%</div>
	</div>

	<!-- Next milestone -->
	{#if nextMilestone}
		<div class="next-milestone">
			<div class="milestone-info">
				<span class="milestone-name">🎯 Prochain objectif: {nextMilestone.name}</span>
				<span class="milestone-count"
					>{nextMilestone.remaining} trades restants ({nextMilestone.threshold} requis)</span
				>
			</div>
			<div class="milestone-progress">
				<div class="progress-bar small">
					<div class="progress-fill" style="width: {nextMilestone.progress_pct}%"></div>
				</div>
			</div>
		</div>
	{/if}

	<!-- Milestones débloqués -->
	<div class="milestones-grid">
		{#each milestones as milestone}
			{@const unlocked = getMilestoneStatus(milestone.threshold)}
			<div class="milestone-item" class:unlocked>
				<div class="milestone-icon" style="background: {unlocked ? milestone.color : 'var(--border-strong)'}">
					{milestone.icon}
				</div>
				<div class="milestone-details">
					<div class="milestone-name">{milestone.name}</div>
					<div class="milestone-threshold">{milestone.threshold} trades</div>
				</div>
				{#if unlocked}
					<div class="check">✓</div>
				{:else}
					<div class="lock">🔒</div>
				{/if}
			</div>
		{/each}
	</div>
</div>

<style>
	.progress-card {
		background: white;
		border-radius: 12px;
		padding: 1.5rem;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
	}

	.card-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1.5rem;
	}

	.card-header h3 {
		font-size: 1.1rem;
		color: var(--text-primary);
		margin: 0;
	}

	.count-badge {
		background: linear-gradient(135deg, var(--accent-indigo) 0%, var(--accent-purple) 100%);
		color: white;
		padding: 0.5rem 1rem;
		border-radius: 20px;
		font-size: 0.9rem;
		font-weight: 600;
	}

	.main-progress {
		margin-bottom: 1.5rem;
	}

	.progress-bar {
		height: 24px;
		background: var(--bg-input);
		border-radius: 12px;
		overflow: hidden;
		position: relative;
	}

	.progress-bar.small {
		height: 8px;
	}

	.progress-fill {
		height: 100%;
		background: linear-gradient(90deg, var(--accent-indigo) 0%, var(--accent-purple) 100%);
		border-radius: 12px;
		transition: width 0.5s ease;
	}

	.progress-label {
		text-align: right;
		font-size: 0.85rem;
		color: var(--text-tertiary);
		margin-top: 0.5rem;
		font-weight: 600;
	}

	.next-milestone {
		background: rgba(var(--accent-blue-rgb), 0.12);
		border: 1px solid rgba(var(--accent-blue-rgb), 0.4);
		border-radius: 8px;
		padding: 1rem;
		margin-bottom: 1.5rem;
	}

	.milestone-info {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.5rem;
		font-size: 0.9rem;
	}

	.milestone-name {
		font-weight: 600;
		color: var(--accent-blue-dark);
	}

	.milestone-count {
		color: var(--text-tertiary);
		font-size: 0.85rem;
	}

	.milestones-grid {
		display: grid;
		gap: 0.75rem;
	}

	.milestone-item {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 0.75rem;
		background: var(--bg-input);
		border-radius: 8px;
		transition: all 0.2s;
	}

	.milestone-item.unlocked {
		background: rgba(var(--accent-green-rgb), 0.10);
		border: 1px solid rgba(var(--accent-green-rgb), 0.4);
	}

	.milestone-icon {
		width: 40px;
		height: 40px;
		border-radius: 8px;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 1.3rem;
		color: white;
	}

	.milestone-details {
		flex: 1;
	}

	.milestone-details .milestone-name {
		font-weight: 600;
		color: var(--text-primary);
		font-size: 0.95rem;
	}

	.milestone-details .milestone-threshold {
		font-size: 0.85rem;
		color: var(--text-tertiary);
	}

	.check {
		color: var(--accent-green);
		font-size: 1.5rem;
		font-weight: bold;
	}

	.lock {
		font-size: 1.2rem;
		opacity: 0.4;
	}
</style>
