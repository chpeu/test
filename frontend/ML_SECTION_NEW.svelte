<!-- ONGLET MACHINE LEARNING - VERSION RÉORGANISÉE -->
{#if activeSubTab === 'ml'}
	<!-- 1. Section Filtrage ML (inchangée) -->
	<section class="variable-section">
		<h3>🎯 Filtrage ML des Trades</h3>
		<p class="section-desc">
			Activez le filtrage pour que le bot rejette automatiquement les opportunités avec faible confiance ML.
		</p>

		<div class="variable-item">
			<div class="variable-label-container">
				<label for="ml_filter_enabled">
					<span class="variable-name">Activer Filtrage ML</span>
					<span class="variable-desc">Bloquer les trades avec faible prédiction</span>
				</label>
			</div>
			<label class="toggle">
				<input
					type="checkbox"
					id="ml_filter_enabled"
					bind:checked={config.ml_filter_enabled}
					on:change={() => triggerAutoSave('ml_filter_enabled', config.ml_filter_enabled ? 'Activé' : 'Désactivé')}
				/>
				<span class="toggle-slider"></span>
			</label>
		</div>

		<div class="variable-item" class:disabled={!config.ml_filter_enabled}>
			<div class="variable-label-container">
				<label for="ml_min_confidence">
					<span class="variable-name">Seuil de Confiance Minimum</span>
					<span class="variable-desc">Confiance minimale pour accepter un trade (50-90%)</span>
				</label>
			</div>
			<div class="slider-container">
				<input
					type="range"
					id="ml_min_confidence"
					min="0.50"
					max="0.90"
					step="0.05"
					bind:value={config.ml_min_confidence}
					on:change={() => triggerAutoSave('ml_min_confidence', Math.round(config.ml_min_confidence * 100) + '%')}
					disabled={!config.ml_filter_enabled}
					class="slider"
				/>
				<span class="slider-value">{Math.round(config.ml_min_confidence * 100)}%</span>
			</div>
		</div>
	</section>

	<!-- 2. Métriques du Modèle Actuel (déplacée ici) -->
	<section class="variable-section">
		<h3>📊 Métriques du Modèle Actuel</h3>
		{#if loadingMLMetrics}
			<div class="loading-message">⏳ Chargement des métriques...</div>
		{:else}
			<div class="ml-metrics-grid">
				<div class="metric-card">
					<div class="metric-label">Test Accuracy</div>
					<div class="metric-value">{mlMetrics.test_accuracy.toFixed(1)}%</div>
					<div class="metric-status" class:poor={mlMetrics.test_accuracy < 60} class:ok={mlMetrics.test_accuracy >= 60 && mlMetrics.test_accuracy < 70} class:good={mlMetrics.test_accuracy >= 70}>
						{mlMetrics.test_accuracy < 60 ? 'Faible' : mlMetrics.test_accuracy < 70 ? 'Moyen' : 'Bon'}
					</div>
				</div>
				<div class="metric-card">
					<div class="metric-label">ROC-AUC</div>
					<div class="metric-value">{mlMetrics.roc_auc.toFixed(1)}%</div>
					<div class="metric-status" class:poor={mlMetrics.roc_auc < 60} class:ok={mlMetrics.roc_auc >= 60 && mlMetrics.roc_auc < 70} class:good={mlMetrics.roc_auc >= 70}>
						{mlMetrics.roc_auc < 60 ? 'Faible' : mlMetrics.roc_auc < 70 ? 'Moyen' : 'Bon'}
					</div>
				</div>
				<div class="metric-card">
					<div class="metric-label">Overfitting Gap</div>
					<div class="metric-value" class:danger={mlMetrics.overfitting_gap > 20} class:warning={mlMetrics.overfitting_gap > 10 && mlMetrics.overfitting_gap <= 20} class:ok={mlMetrics.overfitting_gap <= 10}>
						{mlMetrics.overfitting_gap.toFixed(1)}%
					</div>
					<div class="metric-status" class:danger={mlMetrics.overfitting_gap > 20} class:warning={mlMetrics.overfitting_gap > 10 && mlMetrics.overfitting_gap <= 20} class:ok={mlMetrics.overfitting_gap <= 10}>
						{mlMetrics.overfitting_gap > 20 ? 'Élevé' : mlMetrics.overfitting_gap > 10 ? 'Modéré' : 'Faible'}
					</div>
				</div>
				<div class="metric-card">
					<div class="metric-label">Trades</div>
					<div class="metric-value">{mlMetrics.trades_count}</div>
					<div class="metric-status" class:poor={mlMetrics.trades_count < 100} class:ok={mlMetrics.trades_count >= 100 && mlMetrics.trades_count < 500} class:good={mlMetrics.trades_count >= 500}>
						{mlMetrics.trades_count < 100 ? 'Insuffisant' : mlMetrics.trades_count < 500 ? 'Suffisant' : 'Excellent'}
					</div>
				</div>
			</div>
		{/if}
	</section>

	<!-- 3. Historique Optimisations (version simplifiée) -->
	<section class="variable-section">
		<h3>📈 Historique des Optimisations</h3>
		<p class="section-desc">
			Résumé des optimisations précédentes
		</p>
		<OptimizationHistory />
	</section>

	<!-- 4. Section Hyperparamètres (avec les 3 nouveaux params) -->
	<section class="variable-section">
		<h3>⚙️ Hyperparamètres XGBoost</h3>
		<p class="section-desc">
			Ajustez les hyperparamètres pour combattre l'overfitting et améliorer les performances du modèle.
		</p>

		<!-- Anti-Overfitting -->
		<div class="subsection">
			<h4>🛡️ Anti-Overfitting</h4>
			
			<div class="variable-item">
				<div class="variable-label-container">
					<label for="ml_max_depth">
						<span class="variable-name">Max Depth</span>
						<span class="variable-desc">Profondeur max des arbres (↓ réduit overfitting)</span>
					</label>
				</div>
				<select
					id="ml_max_depth"
					bind:value={config.ml_max_depth}
					on:change={() => triggerAutoSave('ml_max_depth', config.ml_max_depth)}
					class="select-input"
				>
					<option value={2}>2 (très conservateur)</option>
					<option value={3}>3 (conservateur)</option>
					<option value={4}>4 (équilibré)</option>
					<option value={5}>5 (modéré)</option>
					<option value={6}>6 (actuel)</option>
					<option value={7}>7 (agressif)</option>
					<option value={8}>8 (très agressif)</option>
				</select>
			</div>

			<div class="variable-item">
				<div class="variable-label-container">
					<label for="ml_min_child_weight">
						<span class="variable-name">Min Child Weight</span>
						<span class="variable-desc">Samples minimum par feuille (↑ réduit overfitting)</span>
					</label>
				</div>
				<select
					id="ml_min_child_weight"
					bind:value={config.ml_min_child_weight}
					on:change={() => triggerAutoSave('ml_min_child_weight', config.ml_min_child_weight)}
					class="select-input"
				>
					<option value={1}>1 (faible)</option>
					<option value={3}>3</option>
					<option value={5}>5</option>
					<option value={10}>10</option>
					<option value={15}>15</option>
					<option value={18}>18</option>
					<option value={20}>20 (très élevé)</option>
				</select>
			</div>

			<div class="variable-item">
				<div class="variable-label-container">
					<label for="ml_reg_alpha">
						<span class="variable-name">Régularisation L1 (Alpha)</span>
						<span class="variable-desc">Régularisation Lasso (↑ réduit overfitting)</span>
					</label>
				</div>
				<div class="slider-container">
					<input
						type="range"
						id="ml_reg_alpha"
						min="0.0"
						max="15.0"
						step="0.1"
						bind:value={config.ml_reg_alpha}
						on:change={() => triggerAutoSave('ml_reg_alpha', config.ml_reg_alpha.toFixed(1))}
						class="slider"
					/>
					<span class="slider-value">{Number(config.ml_reg_alpha).toFixed(1)}</span>
				</div>
			</div>

			<div class="variable-item">
				<div class="variable-label-container">
					<label for="ml_reg_lambda">
						<span class="variable-name">Régularisation L2 (Lambda)</span>
						<span class="variable-desc">Régularisation Ridge (↑ réduit overfitting)</span>
					</label>
				</div>
				<div class="slider-container">
					<input
						type="range"
						id="ml_reg_lambda"
						min="0.0"
						max="15.0"
						step="0.1"
						bind:value={config.ml_reg_lambda}
						on:change={() => triggerAutoSave('ml_reg_lambda', config.ml_reg_lambda.toFixed(1))}
						class="slider"
					/>
					<span class="slider-value">{Number(config.ml_reg_lambda).toFixed(1)}</span>
				</div>
			</div>

			<!-- NOUVEAU: Gamma -->
			<div class="variable-item">
				<div class="variable-label-container">
					<label for="ml_gamma">
						<span class="variable-name">Gamma</span>
						<span class="variable-desc">Seuil minimum de gain pour split (↑ réduit overfitting)</span>
					</label>
				</div>
				<div class="slider-container">
					<input
						type="range"
						id="ml_gamma"
						min="0.0"
						max="5.0"
						step="0.1"
						bind:value={config.ml_gamma}
						on:change={() => triggerAutoSave('ml_gamma', config.ml_gamma.toFixed(1))}
						class="slider"
					/>
					<span class="slider-value">{Number(config.ml_gamma).toFixed(1)}</span>
				</div>
			</div>
		</div>

		<!-- Sampling -->
		<div class="subsection">
			<h4>🎲 Sampling</h4>

			<div class="variable-item">
				<div class="variable-label-container">
					<label for="ml_subsample">
						<span class="variable-name">Subsample</span>
						<span class="variable-desc">% données par arbre (↓ réduit overfitting)</span>
					</label>
				</div>
				<div class="slider-container">
					<input
						type="range"
						id="ml_subsample"
						min="0.5"
						max="1.0"
						step="0.01"
						bind:value={config.ml_subsample}
						on:change={() => triggerAutoSave('ml_subsample', (config.ml_subsample * 100).toFixed(0) + '%')}
						class="slider"
					/>
					<span class="slider-value">{(config.ml_subsample * 100).toFixed(0)}%</span>
				</div>
			</div>

			<div class="variable-item">
				<div class="variable-label-container">
					<label for="ml_colsample_bytree">
						<span class="variable-name">Colsample by Tree</span>
						<span class="variable-desc">% features par arbre (↓ réduit overfitting)</span>
					</label>
				</div>
				<div class="slider-container">
					<input
						type="range"
						id="ml_colsample_bytree"
						min="0.5"
						max="1.0"
						step="0.01"
						bind:value={config.ml_colsample_bytree}
						on:change={() => triggerAutoSave('ml_colsample_bytree', (config.ml_colsample_bytree * 100).toFixed(0) + '%')}
						class="slider"
					/>
					<span class="slider-value">{(config.ml_colsample_bytree * 100).toFixed(0)}%</span>
				</div>
			</div>

			<!-- NOUVEAU: Colsample by Level -->
			<div class="variable-item">
				<div class="variable-label-container">
					<label for="ml_colsample_bylevel">
						<span class="variable-name">Colsample by Level</span>
						<span class="variable-desc">% features par niveau de profondeur (↓ réduit overfitting)</span>
				</label>
				</div>
				<div class="slider-container">
					<input
						type="range"
						id="ml_colsample_bylevel"
						min="0.5"
						max="1.0"
						step="0.01"
						bind:value={config.ml_colsample_bylevel}
						on:change={() => triggerAutoSave('ml_colsample_bylevel', (config.ml_colsample_bylevel * 100).toFixed(0) + '%')}
						class="slider"
					/>
					<span class="slider-value">{(config.ml_colsample_bylevel * 100).toFixed(0)}%</span>
				</div>
			</div>

			<!-- NOUVEAU: Scale Pos Weight -->
			<div class="variable-item">
				<div class="variable-label-container">
					<label for="ml_scale_pos_weight">
						<span class="variable-name">Scale Pos Weight</span>
						<span class="variable-desc">Équilibre classes déséquilibrées (1.0 = équilibré)</span>
					</label>
				</div>
				<div class="slider-container">
					<input
						type="range"
						id="ml_scale_pos_weight"
						min="0.5"
						max="2.0"
						step="0.01"
						bind:value={config.ml_scale_pos_weight}
						on:change={() => triggerAutoSave('ml_scale_pos_weight', config.ml_scale_pos_weight.toFixed(2))}
						class="slider"
					/>
					<span class="slider-value">{Number(config.ml_scale_pos_weight).toFixed(2)}</span>
				</div>
			</div>
		</div>

		<!-- Apprentissage -->
		<div class="subsection">
			<h4>📚 Apprentissage</h4>

			<div class="variable-item">
				<div class="variable-label-container">
					<label for="ml_n_estimators">
						<span class="variable-name">Nombre d'Arbres</span>
						<span class="variable-desc">Plus d'arbres = meilleure performance (mais plus lent)</span>
					</label>
				</div>
				<select
					id="ml_n_estimators"
					bind:value={config.ml_n_estimators}
					on:change={() => triggerAutoSave('ml_n_estimators', config.ml_n_estimators)}
					class="select-input"
				>
					<option value={50}>50 (rapide)</option>
					<option value={100}>100 (équilibré)</option>
					<option value={150}>150</option>
					<option value={200}>200</option>
					<option value={300}>300</option>
					<option value={400}>400</option>
					<option value={500}>500</option>
					<option value={600}>600</option>
					<option value={700}>700</option>
					<option value={800}>800 (très lent)</option>
				</select>
			</div>

			<div class="variable-item">
				<div class="variable-label-container">
					<label for="ml_learning_rate">
						<span class="variable-name">Learning Rate</span>
						<span class="variable-desc">Vitesse d'apprentissage (↓ plus stable mais plus lent)</span>
					</label>
				</div>
				<select
					id="ml_learning_rate"
					bind:value={config.ml_learning_rate}
					on:change={() => triggerAutoSave('ml_learning_rate', config.ml_learning_rate)}
					class="select-input"
				>
					<option value={0.005}>0.005</option>
					<option value={0.007}>0.007</option>
					<option value={0.01}>0.01</option>
					<option value={0.012}>0.012</option>
					<option value={0.015}>0.015</option>
					<option value={0.02}>0.02</option>
					<option value={0.03}>0.03</option>
					<option value={0.05}>0.05</option>
					<option value={0.1}>0.1</option>
				</select>
			</div>
		</div>

		<!-- Bouton Réentraîner -->
		<div class="retrain-section">
			<button class="btn-retrain" on:click={retrainModel} disabled={retrainingML}>
				{retrainingML ? '⏳ Réentraînement en cours...' : '🚀 Réentraîner le Modèle'}
			</button>
			<p class="retrain-hint">
				💡 Utilisez les hyperparamètres ci-dessus pour combattre l'overfitting
			</p>
		</div>
	</section>

	<!-- 5. Section Optimisation Automatique (Panel uniquement) -->
	<section class="variable-section optimization-section">
		<h3>⚡ Optimisation Automatique des Hyperparamètres</h3>
		<p class="section-desc">
			Recherche automatique des meilleurs hyperparamètres par optimisation bayésienne (Optuna).
			Nécessite 1000+ trades pour des résultats fiables.
		</p>

		<OptimizationPanel />
	</section>
{/if}
