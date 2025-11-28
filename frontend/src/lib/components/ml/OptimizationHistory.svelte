<script>
	import { onMount } from 'svelte';
	import { History, TrendingUp } from 'lucide-svelte';
	
	let history = null;
	let isLoading = true;
	
	onMount(async () => {
		await loadHistory();
	});
	
	async function loadHistory() {
		try {
			isLoading = true;
			const response = await fetch(`/api/ml/optimize/history?limit=1`);
			history = await response.json();
		} catch (error) {
			console.error('Error loading history:', error);
		} finally {
			isLoading = false;
		}
	}
	
	function formatScore(score) {
		return score ? (score * 100).toFixed(2) + '%' : 'N/A';
	}
	
	function formatDate(dateStr) {
		if (!dateStr) return 'N/A';
		const date = new Date(dateStr);
		return date.toLocaleString();
	}
</script>

<div class="history-panel">
	<div class="panel-header">
		<div class="header-content">
			<History size={24} class="header-icon" />
			<div>
				<h2>Résumé des Optimisations</h2>
				<p class="subtitle">Statistiques et meilleur résultat</p>
			</div>
		</div>
		
		<div class="header-actions">
			<button class="btn-refresh" on:click={loadHistory}>
				<TrendingUp size={16} />
				Actualiser
			</button>
		</div>
	</div>
	
	{#if isLoading}
		<div class="loading">
			<div class="spinner"></div>
			<p>Chargement historique...</p>
		</div>
	{:else if history}
		<!-- Stats globales -->
		<div class="stats-summary">
			<div class="stat-item">
				<span class="stat-label">Total trials</span>
				<span class="stat-value">{history.total_trials || 0}</span>
			</div>
			<div class="stat-item">
				<span class="stat-label">Complétés</span>
				<span class="stat-value success">{history.completed_trials || 0}</span>
			</div>
			<div class="stat-item">
				<span class="stat-label">Pruned</span>
				<span class="stat-value muted">{history.pruned_trials || 0}</span>
			</div>
			{#if history.best_trial}
				<div class="stat-item">
					<span class="stat-label">Meilleur score</span>
					<span class="stat-value highlight">{formatScore(history.best_trial.value)}</span>
				</div>
			{/if}
		</div>
		
		<!-- Meilleur trial uniquement -->
		{#if history.best_trial}
			<div class="best-trial-section">
				<h3>🏆 Meilleur Trial</h3>
				<div class="best-trial-card">
					<div class="trial-info-row">
						<div class="info-item">
							<span class="info-label">Trial #</span>
							<span class="info-value">{history.best_trial.number}</span>
						</div>
						<div class="info-item">
							<span class="info-label">Score</span>
							<span class="info-value highlight">{formatScore(history.best_trial.value)}</span>
						</div>
						<div class="info-item">
							<span class="info-label">Date</span>
							<span class="info-value">{formatDate(history.best_trial.datetime)}</span>
						</div>
					</div>
				</div>
			</div>
		{/if}
	{:else}
		<div class="empty-state">
			<History size={48} class="empty-icon" />
			<h3>Aucun historique</h3>
			<p>Lance une optimisation pour voir l'historique des trials</p>
		</div>
	{/if}
</div>

<style>
	.history-panel {
		padding: 1.5rem;
		background: var(--bg-secondary, #1a1a2e);
		border-radius: 12px;
		color: var(--text-primary, #e0e0e0);
	}
	
	.panel-header {
		margin-bottom: 1.5rem;
		padding-bottom: 1rem;
		border-bottom: 1px solid var(--border-color, #333);
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	
	.header-content {
		display: flex;
		align-items: center;
		gap: 1rem;
	}
	
	.header-icon {
		color: var(--accent-blue, #4a9eff);
	}
	
	h2 {
		margin: 0;
		font-size: 1.5rem;
		color: var(--text-primary, #e0e0e0);
	}
	
	.subtitle {
		margin: 0.25rem 0 0 0;
		font-size: 0.875rem;
		color: var(--text-secondary, #888);
	}
	
	.btn-refresh {
		padding: 0.5rem 1rem;
		background: var(--bg-tertiary, #252540);
		border: 1px solid var(--border-color, #333);
		border-radius: 6px;
		color: var(--text-primary, #e0e0e0);
		cursor: pointer;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		transition: all 0.2s;
	}
	
	.btn-refresh:hover {
		background: var(--bg-hover, #2a2a50);
		border-color: var(--accent-blue, #4a9eff);
	}
	
	.loading {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 3rem;
		gap: 1rem;
	}
	
	.spinner {
		width: 40px;
		height: 40px;
		border: 3px solid var(--border-color, #333);
		border-top-color: var(--accent-blue, #4a9eff);
		border-radius: 50%;
		animation: spin 1s linear infinite;
	}
	
	@keyframes spin {
		to { transform: rotate(360deg); }
	}
	
	.stats-summary {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 1rem;
		margin-bottom: 1.5rem;
	}
	
	.stat-item {
		padding: 1rem;
		background: var(--bg-tertiary, #252540);
		border-radius: 8px;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	
	.stat-label {
		font-size: 0.75rem;
		color: var(--text-secondary, #888);
		text-transform: uppercase;
		font-weight: 600;
	}
	
	.stat-value {
		font-size: 1.5rem;
		font-weight: 700;
		color: var(--text-primary, #e0e0e0);
	}
	
	.stat-value.success {
		color: var(--accent-green, #00ff88);
	}
	
	.stat-value.muted {
		color: var(--text-secondary, #888);
	}
	
	.stat-value.highlight {
		color: var(--accent-yellow, #ffd700);
	}
	
	.best-trial-section {
		margin-top: 1.5rem;
	}
	
	.best-trial-section h3 {
		margin: 0 0 1rem 0;
		font-size: 1.125rem;
		color: var(--text-primary, #e0e0e0);
	}
	
	.best-trial-card {
		padding: 1.25rem;
		background: var(--bg-tertiary, #252540);
		border: 2px solid var(--accent-yellow, #ffd700);
		border-radius: 8px;
	}
	
	.trial-info-row {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 1rem;
	}
	
	.info-item {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	
	.info-label {
		font-size: 0.75rem;
		color: var(--text-secondary, #888);
		text-transform: uppercase;
		font-weight: 600;
	}
	
	.info-value {
		font-size: 1.25rem;
		font-weight: 700;
		color: var(--text-primary, #e0e0e0);
		font-family: 'Courier New', monospace;
	}
	
	.info-value.highlight {
		color: var(--accent-yellow, #ffd700);
	}
	
	.trials-list {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	
	.trial-card {
		padding: 1rem;
		background: var(--bg-tertiary, #252540);
		border: 1px solid var(--border-color, #333);
		border-radius: 8px;
		cursor: pointer;
		transition: all 0.2s;
	}
	
	.trial-card:hover {
		border-color: var(--accent-blue, #4a9eff);
		transform: translateX(4px);
	}
	
	.trial-card.selected {
		border-color: var(--accent-blue, #4a9eff);
		background: var(--bg-hover, #2a2a50);
	}
	
	.trial-card.gold {
		border-left: 3px solid #ffd700;
	}
	
	.trial-card.silver {
		border-left: 3px solid #c0c0c0;
	}
	
	.trial-card.bronze {
		border-left: 3px solid #cd7f32;
	}
	
	.trial-header {
		display: grid;
		grid-template-columns: auto 1fr auto;
		gap: 1rem;
		align-items: center;
	}
	
	.trial-rank {
		display: flex;
		align-items: center;
		justify-content: center;
		min-width: 40px;
	}
	
	.gold-icon {
		color: #ffd700;
	}
	
	.silver-icon {
		color: #c0c0c0;
	}
	
	.bronze-icon {
		color: #cd7f32;
	}
	
	.rank-number {
		font-size: 1.125rem;
		font-weight: 700;
		color: var(--text-secondary, #888);
	}
	
	.trial-info {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
	
	.trial-number {
		font-weight: 600;
		color: var(--text-primary, #e0e0e0);
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}
	
	.trial-date {
		font-size: 0.75rem;
		color: var(--text-secondary, #888);
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}
	
	.trial-score {
		font-size: 1.25rem;
		font-weight: 700;
		color: var(--accent-green, #00ff88);
		font-family: 'Courier New', monospace;
	}
	
	.trial-details {
		margin-top: 1rem;
		padding-top: 1rem;
		border-top: 1px solid var(--border-color, #333);
	}
	
	h4 {
		margin: 0 0 0.75rem 0;
		font-size: 0.875rem;
		color: var(--text-secondary, #888);
		text-transform: uppercase;
	}
	
	.params-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
		gap: 0.5rem;
	}
	
	.param-row {
		padding: 0.5rem;
		background: var(--bg-input, #1a1a2e);
		border-radius: 4px;
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	
	.param-key {
		font-size: 0.75rem;
		color: var(--text-secondary, #888);
	}
	
	.param-value {
		font-size: 0.875rem;
		color: var(--text-primary, #e0e0e0);
		font-weight: 600;
		font-family: 'Courier New', monospace;
	}
	
	.controls {
		margin-top: 1.5rem;
		padding-top: 1rem;
		border-top: 1px solid var(--border-color, #333);
		display: flex;
		justify-content: center;
	}
	
	label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.875rem;
		color: var(--text-secondary, #888);
	}
	
	select {
		padding: 0.5rem;
		background: var(--bg-input, #1a1a2e);
		border: 1px solid var(--border-color, #333);
		border-radius: 4px;
		color: var(--text-primary, #e0e0e0);
		cursor: pointer;
	}
	
	.empty-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 3rem;
		text-align: center;
		color: var(--text-secondary, #888);
	}
	
	.empty-icon {
		opacity: 0.3;
		margin-bottom: 1rem;
	}
	
	.empty-state h3 {
		margin: 0.5rem 0;
		color: var(--text-primary, #e0e0e0);
	}
	
	.empty-state p {
		margin: 0;
		font-size: 0.875rem;
	}
</style>
