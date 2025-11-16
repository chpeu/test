<script>
	import { onMount } from 'svelte';
	import { featureImportance, loadFeatureImportance } from '$lib/stores/ml';

	export let tradesCount = 0;

	let loading = true;
	let method = 'correlation';

	onMount(async () => {
		if (tradesCount >= 30) {
			await loadData();
		}
		loading = false;
	});

	async function loadData() {
		loading = true;
		try {
			await loadFeatureImportance(method, 20);
		} catch (error) {
			console.error('Error loading feature importance:', error);
		}
		loading = false;
	}

	async function changeMethod(newMethod) {
		method = newMethod;
		await loadData();
	}
</script>

<div class="feature-importance">
	{#if tradesCount < 30}
		<div class="insufficient-data">
			<div class="icon">🔒</div>
			<h3>Feature Importance Débloquée à 30 Trades</h3>
			<p>Collectez plus de données pour débloquer cette fonctionnalité</p>
			<p class="count">{tradesCount} / 30 trades</p>
		</div>
	{:else}
		<div class="header">
			<div>
				<h2>🔍 Feature Importance</h2>
				<p class="subtitle">Top 20 features les plus corrélées avec le succès des trades</p>
			</div>

			<div class="method-selector">
				<button
					class="method-btn"
					class:active={method === 'correlation'}
					on:click={() => changeMethod('correlation')}
				>
					Corrélation
				</button>
				<button
					class:active={method === 'mutual_info'}
					on:click={() => changeMethod('mutual_info')}
					class="method-btn"
					disabled
					title="Coming soon"
				>
					Mutual Info
				</button>
			</div>
		</div>

		{#if loading}
			<div class="loading">
				<div class="spinner"></div>
				<p>Chargement features...</p>
			</div>
		{:else if $featureImportance.features && $featureImportance.features.length > 0}
			<div class="confidence-badge" class:low={$featureImportance.confidence === 'low'}>
				{#if $featureImportance.confidence === 'low'}
					⚠️ Confiance: Faible ({$featureImportance.trades_count} trades) - Optimal après 100
					trades
				{:else if $featureImportance.confidence === 'medium'}
					✓ Confiance: Moyenne ({$featureImportance.trades_count} trades)
				{:else}
					✓ Confiance: Élevée ({$featureImportance.trades_count} trades)
				{/if}
			</div>

			<div class="features-list">
				{#each $featureImportance.features as feature, i}
					<div class="feature-item">
						<div class="feature-rank">#{feature.rank}</div>
						<div class="feature-name">{feature.name}</div>
						<div class="feature-bar-container">
							<div class="feature-bar" style="width: {feature.importance * 100}%"></div>
						</div>
						<div class="feature-score">{(feature.importance * 100).toFixed(1)}%</div>
					</div>
				{/each}
			</div>
		{:else}
			<div class="no-data">
				<p>Aucune donnée de feature importance disponible</p>
			</div>
		{/if}
	{/if}
</div>

<style>
	.feature-importance {
		background: white;
		border-radius: 12px;
		padding: 1.5rem;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
	}

	.insufficient-data {
		text-align: center;
		padding: 4rem 2rem;
		background: #f9fafb;
		border-radius: 8px;
	}

	.insufficient-data .icon {
		font-size: 4rem;
		margin-bottom: 1rem;
	}

	.insufficient-data h3 {
		color: #374151;
		margin-bottom: 0.5rem;
	}

	.insufficient-data p {
		color: #6b7280;
		margin: 0.5rem 0;
	}

	.insufficient-data .count {
		font-size: 1.2rem;
		font-weight: 600;
		color: #111827;
	}

	.header {
		display: flex;
		justify-content: space-between;
		align-items: start;
		margin-bottom: 1.5rem;
	}

	h2 {
		font-size: 1.3rem;
		color: #111827;
		margin: 0 0 0.5rem 0;
	}

	.subtitle {
		color: #6b7280;
		font-size: 0.9rem;
		margin: 0;
	}

	.method-selector {
		display: flex;
		gap: 0.5rem;
		background: #f3f4f6;
		padding: 0.25rem;
		border-radius: 8px;
	}

	.method-btn {
		padding: 0.5rem 1rem;
		background: transparent;
		border: none;
		border-radius: 6px;
		color: #6b7280;
		font-size: 0.9rem;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.2s;
	}

	.method-btn:hover:not(:disabled) {
		color: #111827;
	}

	.method-btn.active {
		background: white;
		color: #667eea;
		box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
	}

	.method-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.loading {
		text-align: center;
		padding: 3rem;
	}

	.spinner {
		border: 3px solid #f3f4f6;
		border-top: 3px solid #667eea;
		border-radius: 50%;
		width: 40px;
		height: 40px;
		animation: spin 1s linear infinite;
		margin: 0 auto 1rem;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	.confidence-badge {
		padding: 0.75rem 1rem;
		background: #d1fae5;
		color: #065f46;
		border-radius: 8px;
		font-size: 0.9rem;
		margin-bottom: 1.5rem;
		text-align: center;
	}

	.confidence-badge.low {
		background: #fef3c7;
		color: #92400e;
	}

	.features-list {
		display: grid;
		gap: 0.75rem;
	}

	.feature-item {
		display: grid;
		grid-template-columns: 40px 1fr 2fr 60px;
		align-items: center;
		gap: 1rem;
		padding: 0.75rem;
		background: #f9fafb;
		border-radius: 8px;
		transition: all 0.2s;
	}

	.feature-item:hover {
		background: #f3f4f6;
		transform: translateX(4px);
	}

	.feature-rank {
		font-weight: 700;
		color: #667eea;
		font-size: 0.9rem;
	}

	.feature-name {
		font-size: 0.9rem;
		color: #374151;
		font-weight: 500;
	}

	.feature-bar-container {
		height: 8px;
		background: #e5e7eb;
		border-radius: 4px;
		overflow: hidden;
	}

	.feature-bar {
		height: 100%;
		background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
		border-radius: 4px;
		transition: width 0.5s ease;
	}

	.feature-score {
		font-size: 0.85rem;
		font-weight: 600;
		color: #667eea;
		text-align: right;
	}

	.no-data {
		text-align: center;
		padding: 3rem;
		color: #6b7280;
	}
</style>
