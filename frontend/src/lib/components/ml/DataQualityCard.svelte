<script>
	export let quality = {};

	$: status = quality.status || 'unknown';
	$: qualityScore = quality.quality_score || 0;
	$: winLoss = quality.win_loss_distribution || {};
	$: tradesCount = quality.trades_count || 0;

	function getStatusColor(status) {
		switch (status) {
			case 'good':
				return '#10b981';
			case 'acceptable':
				return '#f59e0b';
			case 'poor':
				return '#ef4444';
			default:
				return '#6b7280';
		}
	}

	function getStatusLabel(status) {
		switch (status) {
			case 'good':
				return 'Excellente';
			case 'acceptable':
				return 'Acceptable';
			case 'poor':
				return 'Faible';
			case 'insufficient_data':
				return 'Données insuffisantes';
			default:
				return 'Inconnue';
		}
	}
</script>

<div class="quality-card">
	<div class="card-header">
		<h3>✨ Qualité des Données</h3>
		{#if status !== 'insufficient_data'}
			<div class="score-badge" style="background: {getStatusColor(status)}">
				{qualityScore}/100
			</div>
		{/if}
	</div>

	{#if status === 'insufficient_data'}
		<div class="insufficient-data">
			<div class="icon">🔒</div>
			<p>Minimum 10 trades requis pour analyse qualité</p>
			<p class="count">{tradesCount} / 10 trades collectés</p>
		</div>
	{:else}
		<!-- Status qualité -->
		<div class="status-section">
			<div class="status-label">
				Statut: <span style="color: {getStatusColor(status)}">{getStatusLabel(status)}</span>
			</div>
		</div>

		<!-- Win/Loss Distribution -->
		{#if winLoss.wins !== undefined}
			<div class="distribution-section">
				<h4>📊 Distribution Win/Loss</h4>
				<div class="distribution-stats">
					<div class="stat">
						<div class="stat-label">Wins</div>
						<div class="stat-value win">{winLoss.wins || 0}</div>
					</div>
					<div class="stat">
						<div class="stat-label">Losses</div>
						<div class="stat-value loss">{winLoss.losses || 0}</div>
					</div>
					<div class="stat">
						<div class="stat-label">Win Rate</div>
						<div class="stat-value">{((winLoss.win_rate || 0) * 100).toFixed(1)}%</div>
					</div>
				</div>

				<!-- Barre win/loss -->
				<div class="win-loss-bar">
					<div class="win-fill" style="width: {(winLoss.win_rate || 0) * 100}%"></div>
				</div>

				<!-- Balanced indicator -->
				{#if winLoss.balanced}
					<div class="balanced-indicator success">✓ Distribution équilibrée (40-60%)</div>
				{:else}
					<div class="balanced-indicator warning">
						⚠️ Distribution déséquilibrée - Modèle peut être biaisé
					</div>
				{/if}
			</div>
		{/if}

		<!-- Missing Values -->
		{#if quality.missing_values}
			<div class="missing-section">
				<h4>📉 Valeurs Manquantes</h4>
				{#if quality.missing_values.total_features_with_missing === 0}
					<div class="success-msg">✓ Aucune valeur manquante</div>
				{:else}
					<div class="warning-msg">
						⚠️ {quality.missing_values.total_features_with_missing} features avec données manquantes
					</div>
					{#if Object.keys(quality.missing_values.high_missing_features || {}).length > 0}
						<div class="high-missing">
							<strong>Features critiques (&gt;10%):</strong>
							<ul>
								{#each Object.entries(quality.missing_values.high_missing_features) as [feat, pct]}
									<li>{feat}: {pct.toFixed(1)}%</li>
								{/each}
							</ul>
						</div>
					{/if}
				{/if}
			</div>
		{/if}

		<!-- Low Variance Features -->
		{#if quality.variance && quality.variance.count > 0}
			<div class="variance-section">
				<h4>⚠️ Features faible variance</h4>
				<p>{quality.variance.count} features avec variance trop faible (peuvent être supprimées)</p>
			</div>
		{/if}
	{/if}
</div>

<style>
	.quality-card {
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

	.score-badge {
		color: white;
		padding: 0.5rem 1rem;
		border-radius: 20px;
		font-size: 0.9rem;
		font-weight: 700;
	}

	.insufficient-data {
		text-align: center;
		padding: 2rem 1rem;
		background: #f9fafb;
		border-radius: 8px;
	}

	.insufficient-data .icon {
		font-size: 3rem;
		margin-bottom: 1rem;
	}

	.insufficient-data p {
		margin: 0.5rem 0;
		color: #6b7280;
	}

	.insufficient-data .count {
		font-weight: 600;
		color: #111827;
		font-size: 1.1rem;
	}

	.status-section {
		margin-bottom: 1.5rem;
	}

	.status-label {
		font-size: 1rem;
		color: #374151;
		font-weight: 500;
	}

	.distribution-section,
	.missing-section,
	.variance-section {
		margin-top: 1.5rem;
		padding-top: 1.5rem;
		border-top: 1px solid #e5e7eb;
	}

	h4 {
		font-size: 0.95rem;
		color: #374151;
		margin: 0 0 1rem 0;
	}

	.distribution-stats {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 1rem;
		margin-bottom: 1rem;
	}

	.stat {
		text-align: center;
	}

	.stat-label {
		font-size: 0.85rem;
		color: #6b7280;
		margin-bottom: 0.25rem;
	}

	.stat-value {
		font-size: 1.5rem;
		font-weight: 700;
		color: #111827;
	}

	.stat-value.win {
		color: #10b981;
	}

	.stat-value.loss {
		color: #ef4444;
	}

	.win-loss-bar {
		height: 12px;
		background: #fee2e2;
		border-radius: 6px;
		overflow: hidden;
		margin-bottom: 0.75rem;
	}

	.win-fill {
		height: 100%;
		background: #10b981;
		transition: width 0.5s ease;
	}

	.balanced-indicator {
		font-size: 0.85rem;
		padding: 0.5rem;
		border-radius: 6px;
		text-align: center;
	}

	.balanced-indicator.success {
		background: #d1fae5;
		color: #065f46;
	}

	.balanced-indicator.warning {
		background: #fef3c7;
		color: #92400e;
	}

	.success-msg {
		color: #065f46;
		background: #d1fae5;
		padding: 0.75rem;
		border-radius: 6px;
		font-size: 0.9rem;
	}

	.warning-msg {
		color: #92400e;
		background: #fef3c7;
		padding: 0.75rem;
		border-radius: 6px;
		font-size: 0.9rem;
		margin-bottom: 0.75rem;
	}

	.high-missing {
		background: #fef2f2;
		border: 1px solid #fecaca;
		padding: 0.75rem;
		border-radius: 6px;
		font-size: 0.85rem;
	}

	.high-missing ul {
		margin: 0.5rem 0 0 1rem;
		padding: 0;
	}

	.variance-section p {
		color: #6b7280;
		font-size: 0.9rem;
	}
</style>
