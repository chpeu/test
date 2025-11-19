<script>
	import { predictionSettings } from '$lib/stores/ml.js';

	let threshold = $predictionSettings.confidenceThreshold;
	let filterEnabled = $predictionSettings.filterEnabled;

	// Mettre à jour le store quand le slider change
	$: {
		predictionSettings.update(settings => ({
			...settings,
			confidenceThreshold: threshold,
			filterEnabled: filterEnabled
		}));
	}

	// Estimations basées sur les données
	$: estimatedQualified = Math.max(5, Math.round(48 * Math.pow((threshold - 0.45) / 0.45, 0.8)));
	$: estimatedWinRate = Math.min(70, Math.round(45.8 + (threshold - 0.5) * 48));

	function toggleFilter() {
		filterEnabled = !filterEnabled;
	}
</script>

<div class="confidence-filter">
	<div class="filter-header">
		<div class="title-section">
			<h3>🎯 Filtrage de Confiance ML</h3>
			<p class="description">
				Ajustez le seuil pour trader tous les signaux ou seulement les plus sûrs
			</p>
		</div>
		<button class="toggle-btn" class:active={filterEnabled} on:click={toggleFilter}>
			{filterEnabled ? '✓ Actif' : '○ Désactivé'}
		</button>
	</div>

	{#if filterEnabled}
		<div class="slider-section">
			<div class="slider-header">
				<span class="slider-label">Seuil de confiance minimum</span>
				<span class="slider-value">{(threshold * 100).toFixed(0)}%</span>
			</div>

			<input
				type="range"
				min="0.50"
				max="0.90"
				step="0.01"
				bind:value={threshold}
				class="slider"
			/>

			<div class="slider-marks">
				<span class="mark">50% (Tous)</span>
				<span class="mark">70% (Équilibré)</span>
				<span class="mark">90% (Strict)</span>
			</div>
		</div>

		<div class="stats-grid">
			<div class="stat-card">
				<div class="stat-icon">📊</div>
				<div class="stat-content">
					<div class="stat-label">Signaux qualifiés (estimé)</div>
					<div class="stat-value">{estimatedQualified}%</div>
				</div>
			</div>

			<div class="stat-card">
				<div class="stat-icon">🎯</div>
				<div class="stat-content">
					<div class="stat-label">Win rate attendu</div>
					<div class="stat-value">{estimatedWinRate}%</div>
				</div>
			</div>
		</div>

		<div class="recommendation">
			{#if threshold <= 0.55}
				<span class="rec-icon">🔓</span>
				<span class="rec-text">Mode COLLECTE : Maximum de signaux, validation du modèle</span>
			{:else if threshold <= 0.75}
				<span class="rec-icon">⚖️</span>
				<span class="rec-text">Mode ÉQUILIBRÉ : Bon compromis volume/qualité</span>
			{:else}
				<span class="rec-icon">🔒</span>
				<span class="rec-text">Mode STRICT : Seulement les signaux très sûrs</span>
			{/if}
		</div>
	{:else}
		<div class="disabled-notice">
			<p>⚠️ Filtrage désactivé - Tous les signaux WIN seront tradés</p>
		</div>
	{/if}
</div>

<style>
	.confidence-filter {
		background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
		border: 2px solid #667eea40;
		border-radius: 12px;
		padding: 1.5rem;
		margin-bottom: 1.5rem;
	}

	.filter-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 1.5rem;
		flex-wrap: wrap;
		gap: 1rem;
	}

	.title-section h3 {
		font-size: 1.2rem;
		color: #111827;
		margin: 0 0 0.5rem 0;
	}

	.description {
		color: #6b7280;
		font-size: 0.9rem;
		margin: 0;
	}

	.toggle-btn {
		padding: 0.5rem 1.25rem;
		border: 2px solid #d1d5db;
		border-radius: 8px;
		background: white;
		color: #6b7280;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s;
	}

	.toggle-btn.active {
		background: #667eea;
		border-color: #667eea;
		color: white;
	}

	.toggle-btn:hover {
		transform: translateY(-2px);
		box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
	}

	.slider-section {
		background: white;
		border-radius: 10px;
		padding: 1.25rem;
		margin-bottom: 1rem;
	}

	.slider-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1rem;
	}

	.slider-label {
		color: #374151;
		font-weight: 600;
		font-size: 0.95rem;
	}

	.slider-value {
		background: #667eea;
		color: white;
		padding: 0.25rem 0.75rem;
		border-radius: 6px;
		font-weight: 700;
		font-size: 1.1rem;
	}

	.slider {
		width: 100%;
		height: 8px;
		border-radius: 4px;
		background: linear-gradient(
			to right,
			#10b981 0%,
			#3b82f6 50%,
			#f59e0b 75%,
			#ef4444 100%
		);
		outline: none;
		-webkit-appearance: none;
		margin-bottom: 0.5rem;
	}

	.slider::-webkit-slider-thumb {
		-webkit-appearance: none;
		appearance: none;
		width: 24px;
		height: 24px;
		border-radius: 50%;
		background: white;
		border: 3px solid #667eea;
		cursor: pointer;
		box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
		transition: all 0.2s;
	}

	.slider::-webkit-slider-thumb:hover {
		transform: scale(1.2);
		box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
	}

	.slider::-moz-range-thumb {
		width: 24px;
		height: 24px;
		border-radius: 50%;
		background: white;
		border: 3px solid #667eea;
		cursor: pointer;
		box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
		transition: all 0.2s;
	}

	.slider::-moz-range-thumb:hover {
		transform: scale(1.2);
		box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
	}

	.slider-marks {
		display: flex;
		justify-content: space-between;
		font-size: 0.75rem;
		color: #9ca3af;
		padding: 0 4px;
	}

	.stats-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 1rem;
		margin-bottom: 1rem;
	}

	.stat-card {
		background: white;
		border-radius: 10px;
		padding: 1rem;
		display: flex;
		align-items: center;
		gap: 1rem;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
	}

	.stat-icon {
		font-size: 2rem;
	}

	.stat-content {
		flex: 1;
	}

	.stat-label {
		color: #6b7280;
		font-size: 0.85rem;
		margin-bottom: 0.25rem;
	}

	.stat-value {
		color: #111827;
		font-size: 1.5rem;
		font-weight: 700;
	}

	.recommendation {
		background: white;
		border-left: 4px solid #667eea;
		border-radius: 8px;
		padding: 1rem 1.25rem;
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.rec-icon {
		font-size: 1.5rem;
	}

	.rec-text {
		color: #374151;
		font-weight: 600;
		font-size: 0.95rem;
	}

	.disabled-notice {
		background: #fef3c7;
		border: 2px solid #f59e0b;
		border-radius: 8px;
		padding: 1rem;
		text-align: center;
	}

	.disabled-notice p {
		color: #92400e;
		font-weight: 600;
		margin: 0;
	}
</style>
