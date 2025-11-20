<script>
	import { predictionSettings } from '$lib/stores/ml.js';

	let threshold = $predictionSettings.confidenceThreshold;
	let filterEnabled = $predictionSettings.filterEnabled;

	// Estimations basées sur les métriques actuelles (530 trades)
	// Formules calibrées sur votre confusion matrix
	$: estimatedTotal = 48;
	$: estimatedQualified = Math.max(5, Math.round(48 * Math.pow((threshold - 0.45) / 0.45, 0.8)));
	$: estimatedWinRate = Math.min(70, Math.round(45.8 + (threshold - 0.5) * 48));
	$: estimatedFiltered = estimatedTotal - estimatedQualified;

	function updateThreshold() {
		predictionSettings.set({
			confidenceThreshold: threshold,
			filterEnabled
		});
	}

	// Convertir valeur slider (50-90) en decimal (0.50-0.90)
	function handleSliderInput(e) {
		threshold = parseFloat(e.target.value) / 100;
	}
</script>

<div class="confidence-filter">
	<div class="header">
		<h3>🎯 Filtrage de Confiance ML</h3>
		<label class="toggle">
			<input type="checkbox" bind:checked={filterEnabled} on:change={updateThreshold} />
			<span class="toggle-text">{filterEnabled ? 'Activé' : 'Désactivé'}</span>
		</label>
	</div>

	<div class="slider-container" class:disabled={!filterEnabled}>
		<div class="slider-header">
			<span>Seuil Minimum</span>
			<span class="threshold-value">{Math.round(threshold * 100)}%</span>
		</div>

		<input
			type="range"
			min="50"
			max="90"
			step="5"
			value={threshold * 100}
			on:input={handleSliderInput}
			on:change={updateThreshold}
			disabled={!filterEnabled}
			class="slider"
		/>

		<div class="range-labels">
			<span>50%</span>
			<span>60%</span>
			<span>70%</span>
			<span>80%</span>
			<span>90%</span>
		</div>
	</div>

	{#if filterEnabled}
		<div class="impact-stats">
			<div class="stat">
				<span class="label">📊 Trades Qualifiés</span>
				<span class="value">{estimatedQualified}/{estimatedTotal}</span>
			</div>
			<div class="stat">
				<span class="label">📈 Win Rate Estimé</span>
				<span class="value" class:good={estimatedWinRate > 55}>
					~{estimatedWinRate}%
				</span>
			</div>
			<div class="stat">
				<span class="label">⏭️ Filtrés</span>
				<span class="value">{estimatedFiltered} trades</span>
			</div>
		</div>

		<div class="recommendations">
			{#if threshold < 0.6}
				<div class="rec warning">
					⚠️ Seuil bas : Beaucoup de trades mais qualité faible
				</div>
			{:else if threshold >= 0.65 && threshold <= 0.75}
				<div class="rec good">
					✅ Seuil recommandé : Bon équilibre volume/qualité
				</div>
			{:else if threshold > 0.8}
				<div class="rec info">
					🔒 Seuil élevé : Peu de trades mais haute qualité
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.confidence-filter {
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		border-radius: 12px;
		padding: 20px;
		color: white;
		margin-bottom: 20px;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
	}

	.header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 20px;
	}

	h3 {
		margin: 0;
		font-size: 18px;
		font-weight: 600;
	}

	.toggle {
		display: flex;
		align-items: center;
		gap: 8px;
		cursor: pointer;
	}

	.toggle input {
		cursor: pointer;
	}

	.toggle-text {
		font-size: 14px;
		font-weight: 500;
	}

	.slider-container {
		margin: 20px 0;
		transition: opacity 0.2s;
	}

	.slider-container.disabled {
		opacity: 0.5;
		pointer-events: none;
	}

	.slider-header {
		display: flex;
		justify-content: space-between;
		margin-bottom: 10px;
		font-size: 14px;
	}

	.threshold-value {
		font-size: 24px;
		font-weight: bold;
	}

	.slider {
		width: 100%;
		height: 8px;
		border-radius: 5px;
		background: rgba(255, 255, 255, 0.3);
		outline: none;
		margin: 10px 0;
		cursor: pointer;
		transition: background 0.2s;
	}

	.slider:hover:not(:disabled) {
		background: rgba(255, 255, 255, 0.4);
	}

	.slider::-webkit-slider-thumb {
		appearance: none;
		width: 24px;
		height: 24px;
		border-radius: 50%;
		background: white;
		cursor: pointer;
		box-shadow: 0 2px 8px rgba(0,0,0,0.3);
		transition: transform 0.2s;
	}

	.slider::-webkit-slider-thumb:hover {
		transform: scale(1.1);
	}

	.slider::-moz-range-thumb {
		width: 24px;
		height: 24px;
		border-radius: 50%;
		background: white;
		cursor: pointer;
		border: none;
		box-shadow: 0 2px 8px rgba(0,0,0,0.3);
	}

	.range-labels {
		display: flex;
		justify-content: space-between;
		font-size: 12px;
		opacity: 0.8;
		padding: 0 5px;
	}

	.impact-stats {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 12px;
		margin: 20px 0;
	}

	.stat {
		background: rgba(255, 255, 255, 0.15);
		padding: 12px;
		border-radius: 8px;
		text-align: center;
		transition: background 0.2s;
	}

	.stat:hover {
		background: rgba(255, 255, 255, 0.2);
	}

	.stat .label {
		display: block;
		font-size: 12px;
		opacity: 0.9;
		margin-bottom: 5px;
	}

	.stat .value {
		display: block;
		font-size: 18px;
		font-weight: bold;
	}

	.stat .value.good {
		color: #10b981;
		text-shadow: 0 0 10px rgba(16, 185, 129, 0.5);
	}

	.recommendations {
		margin-top: 15px;
	}

	.rec {
		padding: 10px;
		border-radius: 6px;
		font-size: 14px;
		font-weight: 500;
	}

	.rec.good {
		background: rgba(16, 185, 129, 0.2);
		border: 1px solid rgba(16, 185, 129, 0.4);
	}

	.rec.warning {
		background: rgba(245, 158, 11, 0.2);
		border: 1px solid rgba(245, 158, 11, 0.4);
	}

	.rec.info {
		background: rgba(59, 130, 246, 0.2);
		border: 1px solid rgba(59, 130, 246, 0.4);
	}
</style>
