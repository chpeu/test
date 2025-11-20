<script>
	export let stats = {};

	$: tradesCount = stats.trades_count || 0;
	$: targetTrades = stats.target_trades || 500;
	$: progressPct = stats.progress_pct || 0;
	$: nextMilestone = stats.next_milestone || null;
	$: readiness = stats.readiness || {};

	// Milestones
	const milestones = [
		{ name: 'Exploratory', threshold: 10, icon: '📊', color: '#10b981' },
		{ name: 'Features', threshold: 30, icon: '🔍', color: '#3b82f6' },
		{ name: 'XGBoost', threshold: 50, icon: '🌲', color: '#8b5cf6' },
		{ name: 'GRU', threshold: 200, icon: '🧠', color: '#ec4899' },
		{ name: 'PPO', threshold: 500, icon: '🎮', color: '#f59e0b' }
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
				<div class="milestone-icon" style="background: {unlocked ? milestone.color : '#e5e7eb'}">
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
		color: #111827;
		margin: 0;
	}

	.count-badge {
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
		background: #f3f4f6;
		border-radius: 12px;
		overflow: hidden;
		position: relative;
	}

	.progress-bar.small {
		height: 8px;
	}

	.progress-fill {
		height: 100%;
		background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
		border-radius: 12px;
		transition: width 0.5s ease;
	}

	.progress-label {
		text-align: right;
		font-size: 0.85rem;
		color: #6b7280;
		margin-top: 0.5rem;
		font-weight: 600;
	}

	.next-milestone {
		background: #eff6ff;
		border: 1px solid #bfdbfe;
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
		color: #1e40af;
	}

	.milestone-count {
		color: #6b7280;
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
		background: #f9fafb;
		border-radius: 8px;
		transition: all 0.2s;
	}

	.milestone-item.unlocked {
		background: #f0fdf4;
		border: 1px solid #bbf7d0;
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
		color: #111827;
		font-size: 0.95rem;
	}

	.milestone-details .milestone-threshold {
		font-size: 0.85rem;
		color: #6b7280;
	}

	.check {
		color: #10b981;
		font-size: 1.5rem;
		font-weight: bold;
	}

	.lock {
		font-size: 1.2rem;
		opacity: 0.4;
	}
</style>
