<script>
	import { onMount } from 'svelte';
	import { modelsStatus, loadModelsStatus } from '$lib/stores/ml';

	export let tradesCount = 0;

	let loading = true;

	onMount(async () => {
		await loadModelsStatus();
		loading = false;

		// Refresh every 30s
		const interval = setInterval(() => {
			loadModelsStatus();
		}, 30000);

		return () => clearInterval(interval);
	});

	function getModelIcon(modelType) {
		switch (modelType) {
			case 'xgboost':
				return '🌲';
			case 'gru':
				return '🧠';
			case 'ppo':
				return '🎮';
			default:
				return '🤖';
		}
	}

	function getModelName(modelType) {
		switch (modelType) {
			case 'xgboost':
				return 'XGBoost';
			case 'gru':
				return 'GRU';
			case 'ppo':
				return 'PPO (RL)';
			default:
				return modelType;
		}
	}
</script>

<div class="models-overview">
	<div class="header">
		<h2>🤖 Modèles ML</h2>
		<p class="subtitle">Statut et disponibilité des modèles de prédiction</p>
	</div>

	{#if loading}
		<div class="loading">
			<div class="spinner"></div>
			<p>Chargement status modèles...</p>
		</div>
	{:else}
		<div class="models-grid">
			{#each Object.entries($modelsStatus) as [modelType, status]}
				<div class="model-card" class:ready={status.ready} class:trained={status.trained}>
					<div class="model-header">
						<div class="model-icon">{getModelIcon(modelType)}</div>
						<div class="model-title">
							<h3>{getModelName(modelType)}</h3>
							<div class="model-status">
								{#if status.trained}
									<span class="badge trained">✓ Entraîné</span>
								{:else if status.ready}
									<span class="badge ready">Prêt</span>
								{:else}
									<span class="badge locked">🔒 Verrouillé</span>
								{/if}
							</div>
						</div>
					</div>

					<div class="model-info">
						<div class="info-row">
							<span class="label">Minimum requis:</span>
							<span class="value">{status.min_required} trades</span>
						</div>
						{#if status.optimal_required}
							<div class="info-row">
								<span class="label">Optimal:</span>
								<span class="value">{status.optimal_required} trades</span>
							</div>
						{/if}
						{#if status.confidence}
							<div class="info-row">
								<span class="label">Confiance:</span>
								<span class="value confidence">{status.confidence}</span>
							</div>
						{/if}
					</div>

					{#if status.warning}
						<div class="warning">{status.warning}</div>
					{/if}

					{#if status.ready && !status.trained}
						<button class="train-btn" disabled title="Training à implémenter Phase 3">
							Entraîner le Modèle
						</button>
					{:else if !status.ready}
						<div class="progress-info">
							<div class="progress-bar">
								<div
									class="progress-fill"
									style="width: {(tradesCount / status.min_required) * 100}%"
								></div>
							</div>
							<div class="progress-label">
								{tradesCount} / {status.min_required} trades ({((tradesCount /
									status.min_required) *
									100).toFixed(0)}%)
							</div>
						</div>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.models-overview {
		background: white;
		border-radius: 12px;
		padding: 1.5rem;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
	}

	.header {
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

	.models-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
		gap: 1.5rem;
	}

	.model-card {
		background: #f9fafb;
		border: 2px solid #e5e7eb;
		border-radius: 12px;
		padding: 1.5rem;
		transition: all 0.2s;
	}

	.model-card.ready {
		border-color: #bfdbfe;
		background: #eff6ff;
	}

	.model-card.trained {
		border-color: #86efac;
		background: #f0fdf4;
	}

	.model-header {
		display: flex;
		align-items: center;
		gap: 1rem;
		margin-bottom: 1rem;
	}

	.model-icon {
		font-size: 2.5rem;
	}

	.model-title h3 {
		font-size: 1.1rem;
		color: #111827;
		margin: 0 0 0.5rem 0;
	}

	.model-status {
		display: flex;
		gap: 0.5rem;
	}

	.badge {
		padding: 0.25rem 0.75rem;
		border-radius: 12px;
		font-size: 0.75rem;
		font-weight: 600;
	}

	.badge.trained {
		background: #86efac;
		color: #065f46;
	}

	.badge.ready {
		background: #bfdbfe;
		color: #1e40af;
	}

	.badge.locked {
		background: #e5e7eb;
		color: #6b7280;
	}

	.model-info {
		display: grid;
		gap: 0.5rem;
		margin-bottom: 1rem;
	}

	.info-row {
		display: flex;
		justify-content: space-between;
		font-size: 0.9rem;
	}

	.label {
		color: #6b7280;
	}

	.value {
		font-weight: 600;
		color: #111827;
	}

	.value.confidence {
		text-transform: capitalize;
	}

	.warning {
		background: #fef3c7;
		color: #92400e;
		padding: 0.75rem;
		border-radius: 6px;
		font-size: 0.85rem;
		margin-bottom: 1rem;
	}

	.train-btn {
		width: 100%;
		padding: 0.75rem;
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		color: white;
		border: none;
		border-radius: 8px;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s;
	}

	.train-btn:hover:not(:disabled) {
		transform: translateY(-2px);
		box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
	}

	.train-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.progress-info {
		margin-top: 1rem;
	}

	.progress-bar {
		height: 8px;
		background: #e5e7eb;
		border-radius: 4px;
		overflow: hidden;
		margin-bottom: 0.5rem;
	}

	.progress-fill {
		height: 100%;
		background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
		transition: width 0.5s ease;
	}

	.progress-label {
		font-size: 0.85rem;
		color: #6b7280;
		text-align: center;
	}
</style>
