<script>
	import { onMount } from 'svelte';
	import { mlStats, dataQuality, loadAllMLData } from '$lib/stores/ml';
	import MLTabs from './MLTabs.svelte';
	import DataQualityCard from './DataQualityCard.svelte';
	import DataProgressCard from './DataProgressCard.svelte';
	import FeatureImportance from './FeatureImportance.svelte';
	import ModelsOverview from './ModelsOverview.svelte';
	import LivePredictions from './LivePredictions.svelte';
	import CorrelationAnalytics from './CorrelationAnalytics.svelte';
	import EVAnalysisModal from './EVAnalysisModal.svelte';

	let activeSubTab = 'dashboard';
	let loading = true;
	let error = null;
	let showEVAnalysis = false;

	onMount(async () => {
		try {
			await loadAllMLData();
			loading = false;
		} catch (err) {
			console.error('Error loading ML dashboard:', err);
			error = err.message;
			loading = false;
		}

		// Refresh toutes les 30 secondes
		const interval = setInterval(async () => {
			try {
				await loadAllMLData();
			} catch (err) {
				console.error('Error refreshing ML data:', err);
			}
		}, 30000);

		return () => clearInterval(interval);
	});
</script>

<div class="ml-container">
	<!-- Header ML -->
	<div class="ml-header">
		<h1>🤖 Machine Learning</h1>
		<p class="subtitle">Collecte de données, Feature Engineering & Modèles Prédictifs</p>
		<button class="ev-analysis-btn" on:click={() => showEVAnalysis = true}>
			📊 Analyse EV
		</button>
	</div>

	<!-- EV Analysis Modal -->
	<EVAnalysisModal bind:show={showEVAnalysis} />

	{#if loading}
		<div class="loading">
			<div class="spinner"></div>
			<p>Chargement données ML...</p>
		</div>
	{:else if error}
		<div class="error-card">
			<h3>❌ Erreur</h3>
			<p>{error}</p>
		</div>
	{:else}
		<!-- Tabs ML -->
		<MLTabs bind:activeSubTab tradesCount={$mlStats.trades_count} />

		<!-- Content selon tab active -->
		<div class="ml-content">
			{#if activeSubTab === 'dashboard'}
				<div class="dashboard-grid">
					<DataProgressCard stats={$mlStats} />
					<DataQualityCard quality={$dataQuality} />
				</div>
			{:else if activeSubTab === 'predictions'}
				<LivePredictions />
			{:else if activeSubTab === 'features'}
				<FeatureImportance tradesCount={$mlStats.trades_count} />
			{:else if activeSubTab === 'models'}
				<ModelsOverview tradesCount={$mlStats.trades_count} />
			{:else if activeSubTab === 'correlations'}
				<CorrelationAnalytics />
			{:else if activeSubTab === 'exploratory'}
				<div class="coming-soon">
					<h3>📊 Analyse Exploratoire</h3>
					<p>Coming soon...</p>
				</div>
			{:else if activeSubTab === 'backtesting'}
				<div class="coming-soon">
					<h3>🎯 Backtesting ML</h3>
					<p>Coming soon...</p>
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.ml-container {
		padding: 1rem;
		max-width: 1400px;
		margin: 0 auto;
	}

	.ml-header {
		margin-bottom: 2rem;
		text-align: center;
	}

	.ml-header h1 {
		font-size: 2rem;
		margin-bottom: 0.5rem;
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
	}

	.ev-analysis-btn {
		margin-top: 1rem;
		padding: 0.6rem 1.2rem;
		background: linear-gradient(135deg, #667eea, #764ba2);
		color: white;
		border: none;
		border-radius: 8px;
		font-weight: 600;
		font-size: 0.9rem;
		cursor: pointer;
		transition: transform 0.2s, box-shadow 0.2s;
	}

	.ev-analysis-btn:hover {
		transform: translateY(-2px);
		box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
	}

	.subtitle {
		color: #6b7280;
		font-size: 0.95rem;
	}

	.loading {
		text-align: center;
		padding: 4rem 2rem;
	}

	.spinner {
		border: 4px solid #f3f4f6;
		border-top: 4px solid #667eea;
		border-radius: 50%;
		width: 50px;
		height: 50px;
		animation: spin 1s linear infinite;
		margin: 0 auto 1rem;
	}

	@keyframes spin {
		0% {
			transform: rotate(0deg);
		}
		100% {
			transform: rotate(360deg);
		}
	}

	.error-card {
		background: #fef2f2;
		border: 1px solid #fecaca;
		border-radius: 8px;
		padding: 1.5rem;
		text-align: center;
	}

	.error-card h3 {
		color: #dc2626;
		margin-bottom: 0.5rem;
	}

	.ml-content {
		margin-top: 2rem;
	}

	.dashboard-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
		gap: 1.5rem;
	}

	.coming-soon {
		text-align: center;
		padding: 4rem 2rem;
		background: #f9fafb;
		border-radius: 12px;
	}

	.coming-soon h3 {
		font-size: 1.5rem;
		margin-bottom: 0.5rem;
		color: #374151;
	}

	.coming-soon p {
		color: #6b7280;
	}
</style>
