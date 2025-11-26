<script lang="ts">
	import { onMount } from 'svelte';
	import { sendCommandViaWS } from '$lib/utils/websocket';
	import OptimizationPanel from '$lib/components/ml/OptimizationPanel.svelte';
	import MLCONTENT_V2_Variables from '$lib/components/ml/MLCONTENT_V2_Variables.svelte';

	const DEFAULTS = {
		// Patterns Techniques
		use_breakout: true,
		use_snr: true,
		use_wick: true,
		use_divergence: true,
		// Patterns de Bougies (Candlestick Patterns)
		use_engulfing: true,
		use_hammer: true,
		use_shooting_star: true,
		use_doji: true,
		use_marubozu: true,
		use_morning_star: true,
		use_evening_star: true,
		// Indicateurs Techniques
		snr_threshold: 0.15,  // 🔥 PHASE 1 : 0.15 (était 0.25)
		breakout_threshold: 0.25,  // 🔥 PHASE 1 : 0.25 (était 0.35)
		wick_ratio_max: 4.5,  // 🔥 PHASE 1 : 4.5 (était 2.8)
		di_gap_min: 4.0,
		di_gap_adx_threshold: 25,
		trend_timeframe: '15m',
		// Optimal ATR ranges
		optimal_atr_min_1m: 0.12,
		optimal_atr_max_1m: 0.75,
		optimal_atr_min_5m: 0.22,
		optimal_atr_max_5m: 1.4,
		// Validation Setups (déplacé depuis Stratégie)
		use_confluence: false,
		volume_multiplier: 0.95,
		min_score_required: 6.5,  // 🔥 PHASE 1 : 6.5 (était 7.5)
		max_slippage_pct: 0.03,
		// Money Management
		account_size: 1000.0,
		risk_per_trade: 2.0,
		// 🔥 Live Trading (persistés dans config_overrides.json)
		default_leverage: 10,
		max_latency_ms: 1000,
		// TP/SL Mode
		tp_sl_mode: 'FIXE',
		// Mode FIXE
		tp_percent: 0.50,  // 🔥 PHASE 3 : 0.50 (était 0.6)
		sl_percent: 0.20,  // 🔥 PHASE 3 : 0.20 (était 0.25)
		partial_tp_percent: 50,
		break_even_trigger: 0.3,
		trailing_distance: 0.15,
		// Mode ATR
		atr_mult_tp: 1.5,
		atr_mult_sl: 1.0,
		atr_min: 0.15,
		atr_max: 1.5,
		// Mode ESCALIER (TP_MULTI) - 4 niveaux
		escalier_level1_pnl: 0.20,
		escalier_level1_size: 25,
		escalier_level2_pnl: 0.35,
		escalier_level2_size: 25,
		escalier_level3_pnl: 0.50,
		escalier_level3_size: 25,
		escalier_level4_pnl: 0.80,
		escalier_level4_size: 25,
		// Trailing Stop Adaptatif (tous modes)
		trailing_enabled: true,
		trailing_trigger_pnl: 0.15,  // 🔥 PHASE 2 : 0.15 (était 0.25)
		trailing_atr_multiplier: 0.4,
		trailing_min_distance: 0.08,
		trailing_max_distance: 0.25,
		// Machine Learning V1
		ml_filter_enabled: false,  // 🔥 PHASE 4 : Désactivé (accuracy 51%)
		ml_min_confidence: 0.60,  // 60% (si réactivé plus tard)
		// Hyperparamètres XGBoost V1
		ml_max_depth: 6,
		ml_min_child_weight: 3,
		ml_reg_alpha: 0.5,
		ml_reg_lambda: 2.0,
		ml_subsample: 0.8,
		ml_colsample_bytree: 0.8,
		ml_colsample_bylevel: 0.8,
		ml_gamma: 0.0,
		ml_scale_pos_weight: 1.0,
		ml_n_estimators: 300,
		ml_learning_rate: 0.03,
		// Machine Learning V2 (Régression PNL%)
		ml_v2_filter_enabled: false,
		ml_v2_min_confidence: 0.60,
		ml_v2_timeframe_days: 270,
		ml_v2_max_features: 40,
		ml_v2_marginal_threshold: 0.20,
		ml_v2_filter_marginal_trades: true,
		ml_v2_test_size: 0.2,
		ml_v2_validation_size: 0.1,
		// Hyperparamètres XGBoost V2 (Régression)
		ml_v2_n_estimators: 600,
		ml_v2_max_depth: 4,
		ml_v2_learning_rate: 0.03,
		ml_v2_min_child_weight: 5,
		ml_v2_reg_alpha: 1.0,
		ml_v2_reg_lambda: 3.0,
		ml_v2_subsample: 0.7,
		ml_v2_colsample_bytree: 0.7,
		ml_v2_gamma: 0.5
	};

	let config = { ...DEFAULTS };
	let loading = false;
	let saveMessage = '';
	let activeSubTab = 'setups';
	let mlVersion = 'v1'; // 'v1' ou 'v2' pour les sous-onglets ML
	let viewMode = 'FIXE'; // Mode affiché dans TP/SL (ne modifie PAS config.tp_sl_mode)
	
	// 🔥 NOUVEAU: Système de sauvegarde automatique avec debounce
	let hasUnsavedChanges = false;
	let debounceTimer: ReturnType<typeof setTimeout> | null = null;
	const AUTO_SAVE_DELAY = 2500; // 2.5 secondes d'inactivité avant sauvegarde automatique
	
	// Variables pour l'onglet "Variables en cours"
	let completeConfig = null;
	let loadingCompleteConfig = false;
	let completeConfigError = null;
	
	// 🔥 Variables Live Trading
	let liveConfig = null;
	let loadingLiveConfig = false;
	
	// Variables pour export Excel et reset DB
	let exportingExcel = false;
	let retrainingML = false;
	let resettingDB = false;
	
	// 🔥 FIX: Variables pour métriques ML dynamiques
	let mlMetrics = {
		test_accuracy: 55.3,
		roc_auc: 55.4,
		overfitting_gap: 33.1,
		trades_count: 940
	};
	let loadingMLMetrics = false;

	// Auto-ajustement sliders Escalier pour que la somme = 100%
	function autoAdjustEscalierSize(changedLevel) {
		const levels = [1, 2, 3, 4];
		const otherLevels = levels.filter(l => l !== changedLevel);

		const changedValue = config[`escalier_level${changedLevel}_size`];
		const totalOthers = otherLevels.reduce((sum, l) => sum + config[`escalier_level${l}_size`], 0);
		const totalAll = changedValue + totalOthers;

		if (totalAll > 100) {
			// Réduire proportionnellement les autres niveaux
			const excess = totalAll - 100;
			const reductionRatio = excess / totalOthers;

			otherLevels.forEach(l => {
				const currentValue = config[`escalier_level${l}_size`];
				const reduction = currentValue * reductionRatio;
				config[`escalier_level${l}_size`] = Math.max(0, Math.round(currentValue - reduction));
			});
		}

	}

	function autoAdjustEscalierPnL(changedLevel) {
		// S'assurer que les niveaux suivants sont >= niveau actuel
		const currentPnl = config[`escalier_level${changedLevel}_pnl`];

		for (let i = changedLevel + 1; i <= 4; i++) {
			if (config[`escalier_level${i}_pnl`] < currentPnl) {
				config[`escalier_level${i}_pnl`] = currentPnl;
			}
		}

		// S'assurer que les niveaux précédents sont <= niveau actuel
		for (let i = changedLevel - 1; i >= 1; i--) {
			if (config[`escalier_level${i}_pnl`] > currentPnl) {
				config[`escalier_level${i}_pnl`] = currentPnl;
			}
		}
	}

	onMount(async () => {
		await loadConfig();
	});
	
	// Fonction pour charger la configuration complète
	async function handleParamsApplied() {
		try {
			saveMessage = '⏳ Synchronisation des paramètres...';
			
			// Annuler le debounce timer si en cours
			if (debounceTimer) {
				clearTimeout(debounceTimer);
				debounceTimer = null;
			}
			
			// Forcer hasUnsavedChanges à false AVANT de recharger
			hasUnsavedChanges = false;
			
			// Polling: attendre que le backend ait écrit config_overrides.json
			let attempts = 0;
			const maxAttempts = 10;
			let configUpdated = false;
			
			while (attempts < maxAttempts && !configUpdated) {
				await new Promise(resolve => setTimeout(resolve, 300));
				attempts++;
				
				try {
					const response = await fetch('/api/config/complete');
					if (response.ok) {
						const data = await response.json();
						// Vérifier si les paramètres ML (V1 ou V2) sont présents
						if (data.trading_config && 
							(data.trading_config.ml_max_depth !== undefined || 
							 data.trading_config.ml_v2_max_depth !== undefined)) {
							configUpdated = true;
							console.log(` Config backend mise à jour (tentative ${attempts})`);
						}
					}
				} catch (e) {
					console.warn(`Tentative ${attempts} échouée:`, e);
				}
			}
			
			if (!configUpdated) {
				console.warn(' Timeout: config backend non confirmée après 3s');
			}
			
			// Recharger la configuration locale et "Variables en cours" en forçant le reload
			console.log('🔄 Rechargement config après Apply...');
			await loadConfig(true); // force = true pour bypasser le guard
			await loadCompleteConfig();
			
			console.log('✅ Paramètres optimisés appliqués et synchronisés via REST');
			console.log('🎯 Config.ml_v2_max_depth après reload:', config.ml_v2_max_depth);
			console.log('🎯 Config.ml_v2_learning_rate après reload:', config.ml_v2_learning_rate);
			saveMessage = '✅ Paramètres optimisés appliqués - sliders mis à jour';
			setTimeout(() => { saveMessage = ''; }, 3000);
		} catch (error) {
			console.error('❌ Erreur handleParamsApplied:', error);
			saveMessage = '❌ Erreur lors de l\'application des paramètres';
			setTimeout(() => { saveMessage = ''; }, 5000);
		}
	}
	
	async function loadCompleteConfig() {
		loadingCompleteConfig = true;
		completeConfigError = null;
		try {
			const response = await fetch('/api/config/complete');
			if (!response.ok) {
				throw new Error(`Erreur HTTP: ${response.status}`);
			}
			completeConfig = await response.json();
			console.log('✅ Configuration complète chargée:', completeConfig);
			
			// 🔥 Charger également la config live pour afficher dans "Variables en cours"
			await loadLiveConfig();
		} catch (err) {
			console.error('❌ Erreur chargement config complète:', err);
			completeConfigError = err.message || 'Impossible de charger la configuration complète';
		} finally {
			loadingCompleteConfig = false;
		}
	}
	
	async function loadLiveConfig() {
		loadingLiveConfig = true;
		try {
			const response = await fetch('/api/live/config');
			if (!response.ok) {
				throw new Error(`Erreur HTTP: ${response.status}`);
			}
			liveConfig = await response.json();
			console.log('✅ Config Live chargée:', liveConfig);
		} catch (err) {
			console.error('❌ Erreur chargement config live:', err);
			// Ne pas afficher d'erreur, juste ne pas afficher la config live
			liveConfig = null;
		} finally {
			loadingLiveConfig = false;
		}
	}
	
	// Fonction pour charger les métriques ML depuis l'API
	let mlMetricsLoadAttempts = 0;
	let mlMetricsLoaded = false;
	const MAX_ML_METRICS_ATTEMPTS = 3;
	
	async function loadMLMetrics() {
		// 🔥 FIX: Empêcher les tentatives infinies si le backend n'est pas prêt
		if (loadingMLMetrics || mlMetricsLoadAttempts >= MAX_ML_METRICS_ATTEMPTS) {
			return;
		}
		
		loadingMLMetrics = true;
		mlMetricsLoadAttempts++;
		
		try {
			const response = await fetch('/api/ml/models/overview');
			if (!response.ok) {
				throw new Error(`Erreur HTTP: ${response.status}`);
			}
			const data = await response.json();
			
			// Extraire les métriques du modèle actuel (xgboost_v1)
			const currentModel = data.models?.find(m => m.name === 'xgboost_v1');
			if (currentModel && currentModel.metrics) {
				mlMetrics = {
					test_accuracy: (currentModel.metrics.test?.accuracy || 0) * 100,
					roc_auc: (currentModel.metrics.test?.roc_auc || 0) * 100,
					overfitting_gap: currentModel.overfitting_gap || 0,
					trades_count: currentModel.dataset_info?.total_samples || 0
				};
				console.log('✅ Métriques ML chargées:', mlMetrics);
				mlMetricsLoadAttempts = 0; // Reset sur succès
				mlMetricsLoaded = true;
			}
		} catch (err) {
			console.error(`❌ Erreur chargement métriques ML (tentative ${mlMetricsLoadAttempts}/${MAX_ML_METRICS_ATTEMPTS}):`, err);
			if (mlMetricsLoadAttempts >= MAX_ML_METRICS_ATTEMPTS) {
				saveMessage = '⚠️ Impossible de charger les métriques ML. Backend non accessible.';
				setTimeout(() => saveMessage = '', 5000);
			}
		} finally {
			loadingMLMetrics = false;
		}
	}
	
	// Charger la config complète quand on active l'onglet
	// 🔥 FIX: Ne recharger que si pas de changements non sauvegardés pour préserver les modifications locales
	$: if (activeSubTab === 'current' && !completeConfig && !loadingCompleteConfig && !hasUnsavedChanges) {
		loadCompleteConfig();
	}
	
	// 🔥 FIX: Charger les métriques ML quand on active l'onglet Machine Learning une seule fois
	$: if (activeSubTab === 'ml' && !loadingMLMetrics && !mlMetricsLoaded && mlMetricsLoadAttempts === 0) {
		loadMLMetrics();
	}
	
	// 🔥 FIX: Mettre à jour completeConfig.trading_config avec les valeurs locales si on a des changements non sauvegardés
	$: if (activeSubTab === 'current' && completeConfig && hasUnsavedChanges) {
		// Synchroniser les valeurs locales dans completeConfig pour affichage en temps réel
		if (completeConfig.trading_config) {
			Object.keys(config).forEach(key => {
				if (config[key] !== completeConfig.trading_config[key]) {
					completeConfig.trading_config[key] = config[key];
				}
			});
		}
	}
	
	// Fonction pour formater une valeur selon son type
	function formatValue(value: any): string {
		if (value === null || value === undefined) return 'N/A';
		if (typeof value === 'boolean') return value ? '✅ Activé' : '❌ Désactivé';
		if (typeof value === 'object') {
			// Pour les objets, retourner une représentation compacte
			if (Array.isArray(value)) {
				return `[${value.length} éléments]`;
			}
			return `{${Object.keys(value).length} propriétés}`;
		}
		if (typeof value === 'number') {
			// Formater les nombres avec 2-4 décimales selon la valeur
			if (value < 0.01) return value.toFixed(4);
			if (value < 1) return value.toFixed(3);
			if (value < 100) return value.toFixed(2);
			return value.toFixed(0);
		}
		return String(value);
	}

	// Fonction pour formater une valeur complète (pour les objets)
	function formatFullValue(value: any): string {
		if (value === null || value === undefined) return 'N/A';
		if (typeof value === 'boolean') return value ? '✅ Activé' : '❌ Désactivé';
		if (typeof value === 'object') {
			return JSON.stringify(value, null, 2);
		}
		return formatValue(value);
	}

	// Fonction pour organiser TRADING_CONFIG par catégories
	function organizeTradingConfig(tradingConfig: any) {
		if (!tradingConfig) return {};
		
		return {
			'⚙️ Général': {
				fee_per_trade: tradingConfig.fee_per_trade,
				use_slippage_calculation: tradingConfig.use_slippage_calculation,
				position_timeout: tradingConfig.position_timeout,
				check_interval: tradingConfig.check_interval,
				scan_interval: tradingConfig.scan_interval,
				scalability_interval: tradingConfig.scalability_interval,
			},
			'📊 Validation & Scoring': {
				min_conditions: tradingConfig.min_conditions,
				use_weighted_scoring: tradingConfig.use_weighted_scoring,
				min_score_required: tradingConfig.min_score_required,
				max_slippage_pct: tradingConfig.max_slippage_pct,
				min_score_adx_high: tradingConfig.min_score_adx_high,
				min_score_adx_low: tradingConfig.min_score_adx_low,
				dynamic_tolerance_adx_high: tradingConfig.dynamic_tolerance_adx_high,
				dynamic_tolerance_adx_low: tradingConfig.dynamic_tolerance_adx_low,
			},
			'🎯 Patterns Techniques': {
				use_breakout: tradingConfig.use_breakout,
				use_snr: tradingConfig.use_snr,
				use_wick: tradingConfig.use_wick,
				use_divergence: tradingConfig.use_divergence,
			},
			'🕯️ Patterns de Bougies': {
				use_engulfing: tradingConfig.use_engulfing,
				use_hammer: tradingConfig.use_hammer,
				use_shooting_star: tradingConfig.use_shooting_star,
				use_doji: tradingConfig.use_doji,
				use_marubozu: tradingConfig.use_marubozu,
				use_morning_star: tradingConfig.use_morning_star,
				use_evening_star: tradingConfig.use_evening_star,
			},
			'📈 Seuils & Filtres': {
				snr_threshold: tradingConfig.snr_threshold,
				breakout_threshold: tradingConfig.breakout_threshold,
				wick_ratio_max: tradingConfig.wick_ratio_max,
				di_gap_min: tradingConfig.di_gap_min,
				di_gap_adx_threshold: tradingConfig.di_gap_adx_threshold,
				optimal_atr_min_1m: tradingConfig.optimal_atr_min_1m,
				optimal_atr_max_1m: tradingConfig.optimal_atr_max_1m,
				optimal_atr_min_5m: tradingConfig.optimal_atr_min_5m,
				optimal_atr_max_5m: tradingConfig.optimal_atr_max_5m,
			},
			'💰 Money Management': {
				account_size: tradingConfig.account_size,
				risk_per_trade: tradingConfig.risk_per_trade,
				volume_multiplier: tradingConfig.volume_multiplier,
				use_confluence: tradingConfig.use_confluence,
			},
			'🎯 TP/SL Configuration': {
				tp_sl_mode: tradingConfig.tp_sl_mode,
				tp_percent: tradingConfig.tp_percent,
				sl_percent: tradingConfig.sl_percent,
				break_even_trigger: tradingConfig.break_even_trigger,
				trailing_distance: tradingConfig.trailing_distance,
			},
			'📐 Mode ATR': {
				atr_mult_tp: tradingConfig.atr_mult_tp,
				atr_mult_sl: tradingConfig.atr_mult_sl,
				atr_min: tradingConfig.atr_min,
				atr_max: tradingConfig.atr_max,
			},
			'🪜 TP Escalier': {
				partial_tp_percent: tradingConfig.partial_tp_percent,
				escalier_level1_pnl: tradingConfig.escalier_level1_pnl,
				escalier_level1_size: tradingConfig.escalier_level1_size,
				escalier_level2_pnl: tradingConfig.escalier_level2_pnl,
				escalier_level2_size: tradingConfig.escalier_level2_size,
				escalier_level3_pnl: tradingConfig.escalier_level3_pnl,
				escalier_level3_size: tradingConfig.escalier_level3_size,
				escalier_level4_pnl: tradingConfig.escalier_level4_pnl,
				escalier_level4_size: tradingConfig.escalier_level4_size,
			},
			'📉 Trailing Stop': {
				trailing_enabled: tradingConfig.trailing_enabled,
				trailing_trigger_pnl: tradingConfig.trailing_trigger_pnl,
				trailing_atr_multiplier: tradingConfig.trailing_atr_multiplier,
				trailing_min_distance: tradingConfig.trailing_min_distance,
				trailing_max_distance: tradingConfig.trailing_max_distance,
			},
			'⏱️ Timeframe & Trend': {
				trend_timeframe: tradingConfig.trend_timeframe,
			},
			'🔍 Scanner': {
				top_pairs_limit: tradingConfig.top_pairs_limit,
				balance_score_min: tradingConfig.balance_score_min,
			},
			'🤖 Machine Learning V1': {
				ml_filter_enabled: tradingConfig.ml_filter_enabled,
				ml_min_confidence: tradingConfig.ml_min_confidence,
				ml_max_depth: tradingConfig.ml_max_depth,
				ml_min_child_weight: tradingConfig.ml_min_child_weight,
				ml_reg_alpha: tradingConfig.ml_reg_alpha,
				ml_reg_lambda: tradingConfig.ml_reg_lambda,
				ml_subsample: tradingConfig.ml_subsample,
				ml_colsample_bytree: tradingConfig.ml_colsample_bytree,
				ml_colsample_bylevel: tradingConfig.ml_colsample_bylevel,
				ml_gamma: tradingConfig.ml_gamma,
				ml_scale_pos_weight: tradingConfig.ml_scale_pos_weight,
				ml_n_estimators: tradingConfig.ml_n_estimators,
				ml_learning_rate: tradingConfig.ml_learning_rate,
			},
			'🚀 Machine Learning V2 (Régression)': {
				ml_v2_filter_enabled: tradingConfig.ml_v2_filter_enabled,
				ml_v2_min_confidence: tradingConfig.ml_v2_min_confidence,
				ml_v2_timeframe_days: tradingConfig.ml_v2_timeframe_days,
				ml_v2_max_features: tradingConfig.ml_v2_max_features,
				ml_v2_marginal_threshold: tradingConfig.ml_v2_marginal_threshold,
				ml_v2_filter_marginal_trades: tradingConfig.ml_v2_filter_marginal_trades,
				ml_v2_test_size: tradingConfig.ml_v2_test_size,
				ml_v2_validation_size: tradingConfig.ml_v2_validation_size,
				ml_v2_n_estimators: tradingConfig.ml_v2_n_estimators,
				ml_v2_max_depth: tradingConfig.ml_v2_max_depth,
				ml_v2_learning_rate: tradingConfig.ml_v2_learning_rate,
				ml_v2_min_child_weight: tradingConfig.ml_v2_min_child_weight,
				ml_v2_reg_alpha: tradingConfig.ml_v2_reg_alpha,
				ml_v2_reg_lambda: tradingConfig.ml_v2_reg_lambda,
				ml_v2_subsample: tradingConfig.ml_v2_subsample,
				ml_v2_colsample_bytree: tradingConfig.ml_v2_colsample_bytree,
				ml_v2_gamma: tradingConfig.ml_v2_gamma,
			},
			'💎 Live Trading': {
				default_leverage: tradingConfig.default_leverage,
				max_latency_ms: tradingConfig.max_latency_ms,
			},
			'⚙️ Configurations Avancées': {
				early_invalidation: tradingConfig.early_invalidation,
				trailing_stop: tradingConfig.trailing_stop,
				adaptive_thresholds: tradingConfig.adaptive_thresholds,
				dynamic_correlation: tradingConfig.dynamic_correlation,
				position_sizing: tradingConfig.position_sizing,
				correlation_filter: tradingConfig.correlation_filter,
				recovery_mode: tradingConfig.recovery_mode,
				tp_escalier: tradingConfig.tp_escalier,
			},
		};
	}
	
	// Fonction pour organiser Live Config en sections
	function organizeLiveConfig(live: any) {
		if (!live) return {};
		
		// Badge pour le mode
		let modeBadge = '📄 PAPER';
		if (live.trading_mode === 'LIVE') {
			modeBadge = live.dry_run ? '🧪 LIVE DRY-RUN' : '🔴 LIVE RÉEL';
		}
		
		return {
			'🎯 Mode Trading': {
				'Mode actuel': modeBadge,
				trading_mode: live.trading_mode,
				dry_run: live.dry_run,
			},
			'🔑 API Configuration': {
				api_key_configured: live.api_key_mexc !== '' && live.api_key_mexc !== undefined,
				api_secret_configured: live.api_secret_mexc === '***',
			},
			'⚙️ Paramètres Live': {
				default_leverage: live.default_leverage,
				max_latency_ms: live.max_latency_ms,
				max_slippage_pct: live.max_slippage_pct,
				max_pnl_discrepancy_pct: live.max_pnl_discrepancy_pct,
			},
		};
	}

	async function loadConfig(force = false) {
		try {
			// 🔥 FIX: Ne JAMAIS recharger la config si on a des changements non sauvegardés
			// Cela évite d'écraser les modifications lors des changements d'onglet
			// SAUF si force=true (utilisé après apply params depuis OptimizationPanel)
			if (hasUnsavedChanges && !force) {
				console.log('⚠️ Changements non sauvegardés détectés, chargement de la config ignoré pour préserver les modifications');
				return;
			}
			
			// 🔥 NOUVEAU: Utiliser /api/config/complete REST au lieu de WebSocket
			// pour garantir que les 11 paramètres ML sont correctement chargés
			const response = await fetch('/api/config/complete');
			if (!response.ok) {
				throw new Error(`Erreur HTTP: ${response.status}`);
			}
			
			const data = await response.json();
			const stateData = { config: data.trading_config };
			
			if (stateData && stateData.config) {
				// 🔥 FIX: Ne PAS écraser avec DEFAULTS, utiliser directement data.config
				// 🔥 NOUVEAU: Annuler le timer de debounce si en cours (on charge depuis le backend)
				if (debounceTimer) {
					clearTimeout(debounceTimer);
					debounceTimer = null;
				}
				hasUnsavedChanges = false; // Marquer comme sauvegardé (on charge depuis le backend)
				
				// 🔥 FIX: Créer un nouvel objet pour forcer la réactivité Svelte et éviter les changements d'état non désirés
				// IMPORTANT: Copier DEFAULTS en profondeur pour les listes/objets (technical_patterns, candlestick_patterns)
				const newConfig = JSON.parse(JSON.stringify(DEFAULTS));
				// Ensuite écraser avec les valeurs du backend
				Object.keys(stateData.config).forEach(key => {
					if (stateData.config[key] !== undefined && stateData.config[key] !== null) {
						// Pour les listes, copier en profondeur
						if (Array.isArray(stateData.config[key])) {
							newConfig[key] = [...stateData.config[key]];
						} else if (typeof stateData.config[key] === 'object' && stateData.config[key] !== null) {
							newConfig[key] = { ...stateData.config[key] };
						} else {
							// 🔥 FIX: Pour les booléens (checkboxes), s'assurer qu'ils sont bien convertis
							if (typeof stateData.config[key] === 'boolean') {
								newConfig[key] = stateData.config[key];
							} else {
								newConfig[key] = stateData.config[key];
							}
						}
					}
				});
				config = newConfig; // Assigner le nouvel objet pour déclencher la réactivité
				viewMode = config.tp_sl_mode || 'FIXE';
				console.log('✅ Config chargée depuis backend via REST API');
				console.log('✅ ML V1 params:', {
					ml_max_depth: config.ml_max_depth,
					ml_min_child_weight: config.ml_min_child_weight,
					ml_reg_alpha: config.ml_reg_alpha,
					ml_reg_lambda: config.ml_reg_lambda,
					ml_subsample: config.ml_subsample,
					ml_colsample_bytree: config.ml_colsample_bytree,
					ml_colsample_bylevel: config.ml_colsample_bylevel,
					ml_gamma: config.ml_gamma,
					ml_scale_pos_weight: config.ml_scale_pos_weight,
					ml_n_estimators: config.ml_n_estimators,
					ml_learning_rate: config.ml_learning_rate
				});
				console.log('✅ ML V2 params:', {
					ml_v2_filter_enabled: config.ml_v2_filter_enabled,
					ml_v2_min_confidence: config.ml_v2_min_confidence,
					ml_v2_n_estimators: config.ml_v2_n_estimators,
					ml_v2_max_depth: config.ml_v2_max_depth,
					ml_v2_learning_rate: config.ml_v2_learning_rate,
					ml_v2_min_child_weight: config.ml_v2_min_child_weight,
					ml_v2_reg_alpha: config.ml_v2_reg_alpha,
					ml_v2_reg_lambda: config.ml_v2_reg_lambda,
					ml_v2_gamma: config.ml_v2_gamma,
					ml_v2_subsample: config.ml_v2_subsample,
					ml_v2_colsample_bytree: config.ml_v2_colsample_bytree
				});
			} else {
				console.warn('⚠️ Aucune config reçue, utilisation des defaults');
				// 🔥 NOUVEAU: Annuler le timer de debounce si en cours
				if (debounceTimer) {
					clearTimeout(debounceTimer);
					debounceTimer = null;
				}
				hasUnsavedChanges = false; // Pas de changements non sauvegardés au chargement
				config = { ...DEFAULTS };
				viewMode = 'FIXE';
			}
		} catch (err) {
			console.error('❌ Error loading config:', err);
			config = { ...DEFAULTS };
			viewMode = 'FIXE';
		}
	}

	// 🔥 MODIFIÉ: Sauvegarde manuelle (bouton Save) - annule le debounce et sauvegarde immédiatement
	async function saveConfig() {
		// Annuler le timer de debounce si en cours
		if (debounceTimer) {
			clearTimeout(debounceTimer);
			debounceTimer = null;
		}
		
		// Si pas de changements, ne rien faire
		if (!hasUnsavedChanges && !loading) {
			saveMessage = 'ℹ️ Aucun changement à sauvegarder';
			setTimeout(() => (saveMessage = ''), 2000);
			return;
		}
		
		loading = true;
		saveMessage = '';
		
		try {
			// 🔥 MIGRATION COMPLÈTE: Utiliser WebSocket natif au lieu de REST
			const result = await sendCommandViaWS('update_config', config);
			
			// 🔥 MIGRATION COMPLÈTE: Résultat de la commande WebSocket
			if (result && result.updated) {
				const updatedCount = Object.keys(result.updated).length;
				saveMessage = `✅ ${updatedCount} paramètre(s) sauvegardé(s) via WebSocket`;
				hasUnsavedChanges = false; // Marquer comme sauvegardé
				console.log('✅ Paramètres mis à jour via WebSocket:', result.updated);
				
				// Vérifier que min_score_required est bien dans les updates
				if (result.updated.min_score_required !== undefined) {
					console.log(`✅ min_score_required mis à jour: ${result.updated.min_score_required}`);
				}
				
				setTimeout(() => (saveMessage = ''), 3000);
				
				// 🔥 FIX: Rafraîchir automatiquement le sous-onglet "Variables en cours" après sauvegarde manuelle
				if (activeSubTab === 'current') {
					await loadCompleteConfig();
				}
			} else {
				saveMessage = `✅ Configuration sauvegardée via WebSocket`;
				hasUnsavedChanges = false;
				setTimeout(() => (saveMessage = ''), 3000);
				
				// 🔥 FIX: Rafraîchir automatiquement le sous-onglet "Variables en cours" après sauvegarde manuelle
				if (activeSubTab === 'current') {
					await loadCompleteConfig();
				}
			}
		} catch (err) {
			console.error('❌ Error saving config via WebSocket:', err);
			saveMessage = `❌ Erreur: ${err.message || 'Impossible de sauvegarder. Vérifiez la connexion WebSocket.'}`;
			// Ne pas marquer comme sauvegardé en cas d'erreur
			setTimeout(() => (saveMessage = ''), 5000);
		} finally {
			loading = false;
		}
	}

	function resetDefaults() {
		if (confirm('Réinitialiser toutes les variables aux valeurs par défaut ?')) {
			config = { ...DEFAULTS };
			// 🔥 MODIFIÉ: Utiliser triggerAutoSave au lieu de logConfigChange
			triggerAutoSave('ALL', 'Reset to defaults');
		}
	}

	function resetVariable(key: string) {
		const oldValue = config[key];
		config[key] = DEFAULTS[key];
		// 🔥 MODIFIÉ: Utiliser triggerAutoSave au lieu de logConfigChange
		triggerAutoSave(key, `${oldValue} → ${DEFAULTS[key]}`);
	}

	async function retrainModel() {
		retrainingML = true;
		saveMessage = '⏳ Réentraînement en cours...';
		
		try {
			// 1. Déclencher le réentraînement
			const response = await fetch('/api/ml/retrain?force=true', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' }
			});

			if (!response.ok) {
				throw new Error('Erreur: ' + response.statusText);
			}

			const result = await response.json();
			
			// 🔥 FIX: L'API retourne un task_id, pas le résultat immédiatement
			if (result.status === 'pending' && result.task_id) {
				saveMessage = '⏳ Réentraînement démarré, vérification de l\'état...';
				
				// 2. Attendre la completion de la tâche (polling)
				const taskId = result.task_id;
				let attempts = 0;
				const maxAttempts = 60; // 5 minutes max (60 * 5s)
				
				while (attempts < maxAttempts) {
					await new Promise(resolve => setTimeout(resolve, 5000)); // Attendre 5 secondes
					
					// Vérifier l'état de la tâche
					const statusResponse = await fetch(`/api/ml/tasks/${taskId}`);
					if (!statusResponse.ok) {
						throw new Error('Impossible de vérifier l\'état du réentraînement');
					}
					
					const taskStatus = await statusResponse.json();
					
					if (taskStatus.status === 'completed' && taskStatus.result) {
						// ✅ Réentraînement terminé avec succès
						const metrics = taskStatus.result.metrics;
						if (metrics && metrics.test) {
							const accuracy = (metrics.test.accuracy * 100).toFixed(1);
							const rocauc = (metrics.test.roc_auc * 100).toFixed(1);
							const gap = ((metrics.train.accuracy - metrics.test.accuracy) * 100).toFixed(1);
							
							saveMessage = `✅ Modèle réentraîné! Accuracy: ${accuracy}%, ROC-AUC: ${rocauc}%, Gap: ${gap}%`;
							
							// 🔥 FIX: Recharger les métriques ML pour mettre à jour le tableau
							await loadMLMetrics();
							
							setTimeout(() => {
								alert(`Modèle réentraîné avec succès!\n\nAccuracy: ${accuracy}%\nROC-AUC: ${rocauc}%\nOverfitting Gap: ${gap}%`);
								location.reload();
							}, 1000);
							return;
						}
					} else if (taskStatus.status === 'error') {
						throw new Error(taskStatus.error || 'Erreur lors du réentraînement');
					}
					
					// Mise à jour du message de progression
					saveMessage = `⏳ Réentraînement en cours... (${Math.round(taskStatus.progress || 0)}%)`;
					attempts++;
				}
				
				throw new Error('Timeout: Le réentraînement prend trop de temps');
			} else if (result.status === 'skipped') {
				saveMessage = `ℹ️ ${result.message}`;
				setTimeout(() => saveMessage = '', 5000);
			}
		} catch (err) {
			console.error('Erreur réentraînement:', err);
			saveMessage = `❌ Erreur: ${err.message}`;
			setTimeout(() => saveMessage = '', 5000);
		} finally {
			retrainingML = false;
		}
	}

	// 🔥 NOUVEAU: Fonction générique pour déclencher la sauvegarde automatique avec debounce
	function triggerAutoSave(key: string, change: any) {
		// Marquer qu'il y a des changements non sauvegardés
		hasUnsavedChanges = true;
		
		// Logger le changement (pour historique)
		logConfigChange(key, change).catch(err => {
			console.error('❌ Error logging config change:', err);
		});
		
		// Annuler le timer précédent s'il existe
		if (debounceTimer) {
			clearTimeout(debounceTimer);
		}
		
		// Déclencher un nouveau timer pour la sauvegarde automatique
		debounceTimer = setTimeout(async () => {
			await autoSaveConfig();
		}, AUTO_SAVE_DELAY);
	}
	
	// 🔥 NOUVEAU: Sauvegarde automatique (appelée par le debounce)
	async function autoSaveConfig() {
		if (loading || !hasUnsavedChanges) {
			return; // Déjà en cours de sauvegarde ou rien à sauvegarder
		}
		
		loading = true;
		saveMessage = '';
		
		try {
			const result = await sendCommandViaWS('update_config', config);
			
			if (result && result.updated) {
				const updatedCount = Object.keys(result.updated).length;
				saveMessage = `✅ ${updatedCount} paramètre(s) sauvegardé(s) automatiquement`;
				hasUnsavedChanges = false; // Marquer comme sauvegardé
				console.log('✅ Paramètres sauvegardés automatiquement via WebSocket:', result.updated);
				setTimeout(() => (saveMessage = ''), 3000);
				
				// 🔥 FIX: Rafraîchir automatiquement le sous-onglet "Variables en cours" après sauvegarde
				if (activeSubTab === 'current') {
					await loadCompleteConfig();
				}
			} else {
				saveMessage = `✅ Configuration sauvegardée automatiquement`;
				hasUnsavedChanges = false;
				setTimeout(() => (saveMessage = ''), 3000);
				
				// 🔥 FIX: Rafraîchir automatiquement le sous-onglet "Variables en cours" après sauvegarde
				if (activeSubTab === 'current') {
					await loadCompleteConfig();
				}
			}
		} catch (err) {
			console.error('❌ Error auto-saving config via WebSocket:', err);
			saveMessage = `❌ Erreur sauvegarde automatique: ${err.message || 'Vérifiez la connexion WebSocket.'}`;
			// Ne pas marquer comme sauvegardé en cas d'erreur
			setTimeout(() => (saveMessage = ''), 5000);
		} finally {
			loading = false;
			debounceTimer = null;
		}
	}
	
	// 🔥 Export Excel du datalogger
	async function exportExcel() {
		if (exportingExcel) return;
		
		exportingExcel = true;
		saveMessage = '⏳ Export Excel en cours...';
		
		try {
			const response = await fetch('/api/datalogger/export/excel');
			
			if (!response.ok) {
				const error = await response.json();
				throw new Error(error.error || 'Erreur export Excel');
			}
			
			// Télécharger le fichier
			const blob = await response.blob();
			const url = window.URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `datalogger_export_${new Date().toISOString().split('T')[0]}.xlsx`;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			window.URL.revokeObjectURL(url);
			
			saveMessage = '✅ Export Excel réussi !';
			setTimeout(() => saveMessage = '', 3000);
		} catch (error: any) {
			saveMessage = `❌ Erreur export Excel: ${error.message}`;
			setTimeout(() => saveMessage = '', 5000);
		} finally {
			exportingExcel = false;
		}
	}
	
	// 🔥 Reset de la base de données PostgreSQL
	async function resetDatabase() {
		if (resettingDB) return;
		
		// Confirmation avant reset
		if (!confirm('⚠️ ATTENTION: Cette opération va supprimer TOUTES les données de la base PostgreSQL (scans, opportunities, trades, etc.).\n\nÊtes-vous sûr de vouloir continuer ?')) {
			return;
		}
		
		// Double confirmation
		if (!confirm('⚠️ DERNIÈRE CONFIRMATION: Toutes les données seront PERDUES de manière irréversible.\n\nConfirmez-vous le reset ?')) {
			return;
		}
		
		resettingDB = true;
		saveMessage = '⏳ Reset de la base de données en cours...';
		
		try {
			const response = await fetch('/api/datalogger/reset', {
				method: 'DELETE'
			});
			
			if (!response.ok) {
				const error = await response.json();
				throw new Error(error.error || 'Erreur reset DB');
			}
			
			const result = await response.json();
			saveMessage = `✅ Base de données resetée: ${result.total_deleted} enregistrements supprimés`;
			setTimeout(() => saveMessage = '', 5000);
		} catch (error: any) {
			saveMessage = `❌ Erreur reset DB: ${error.message}`;
			setTimeout(() => saveMessage = '', 5000);
		} finally {
			resettingDB = false;
		}
	}
	
	// Fonction pour logger les changements (pour historique backend)
	async function logConfigChange(key: string, change: any) {
		// MIGRATION COMPLÈTE: Envoyer log via WebSocket natif uniquement
		try {
			await sendCommandViaWS('log_config', {
				key,
				change,
				timestamp: new Date().toISOString()
			});
		} catch (err) {
			console.error('❌ Error logging config change via WebSocket:', err);
		}
	}

	// Watcher pour logger les changements
	$: if (config) {
		Object.keys(config).forEach(key => {
			const oldValue = DEFAULTS[key];
			// Note: dans un vrai système, on voudrait comparer avec la valeur précédente, pas DEFAULTS
		});
	}

	// 🔥 BIDIRECTIONNEL: Écouter les mises à jour de config depuis le backend
	onMount(async () => {
		const { getWebSocket } = await import('$lib/utils/websocket');
		const ws = getWebSocket();
		if (ws) {
			ws.on('config_updated', (data: any) => {
				console.log('🔄 Config mise à jour depuis backend:', data.updated);
				// Synchroniser la config locale avec les changements du backend
				if (data.updated) {
					// 🔥 FIX: Ne pas déclencher le debounce pour les mises à jour depuis le backend
					// Annuler le timer de debounce si en cours (le backend a déjà sauvegardé)
					if (debounceTimer) {
						clearTimeout(debounceTimer);
						debounceTimer = null;
					}
					hasUnsavedChanges = false; // Marquer comme sauvegardé (le backend a mis à jour)
					
					// 🔥 FIX: Créer un NOUVEL objet pour forcer la réactivité Svelte et éviter les changements d'état non désirés
					// IMPORTANT: Copier DEFAULTS en profondeur pour les listes/objets
					const newConfig = JSON.parse(JSON.stringify(DEFAULTS));
					// D'abord copier la config actuelle
					Object.keys(config).forEach(key => {
						if (config[key] !== undefined && config[key] !== null) {
							if (Array.isArray(config[key])) {
								newConfig[key] = [...config[key]];
							} else if (typeof config[key] === 'object' && config[key] !== null) {
								newConfig[key] = { ...config[key] };
							} else {
								newConfig[key] = config[key];
							}
						}
					});
					// Ensuite appliquer les mises à jour du backend
					Object.keys(data.updated).forEach(key => {
						if (key in newConfig) {
							if (Array.isArray(data.updated[key])) {
								newConfig[key] = [...data.updated[key]];
							} else if (typeof data.updated[key] === 'object' && data.updated[key] !== null) {
								newConfig[key] = { ...data.updated[key] };
							} else {
								// 🔥 FIX: Pour les booléens (checkboxes), s'assurer qu'ils sont bien convertis
								if (typeof data.updated[key] === 'boolean') {
									newConfig[key] = data.updated[key];
								} else {
									newConfig[key] = data.updated[key];
								}
							}
						}
					});
					// 🔥 FIX: S'assurer que break_even_trigger et trailing_distance sont bien mis à jour depuis le backend
					if (data.updated.break_even_trigger !== undefined && data.updated.break_even_trigger !== null) {
						newConfig.break_even_trigger = data.updated.break_even_trigger;
					}
					if (data.updated.trailing_distance !== undefined && data.updated.trailing_distance !== null) {
						newConfig.trailing_distance = data.updated.trailing_distance;
					}
					config = newConfig; // Assigner le nouvel objet pour déclencher la réactivité
					
					if (data.updated.tp_sl_mode) {
						viewMode = data.updated.tp_sl_mode;
					}
					
					// 🔥 FIX: Toujours rafraîchir completeConfig (même si pas sur l'onglet 'current')
					// pour que les changements soient visibles quand l'utilisateur revient sur cet onglet
					loadCompleteConfig();
				}
			});
		}
		
		// 🔥 NOUVEAU: Nettoyer le timer quand le composant est détruit
		return () => {
			if (debounceTimer) {
				clearTimeout(debounceTimer);
				debounceTimer = null;
			}
		};
	});
</script>

<div class="variables-panel" data-debug-name="variablesPanel">
	<div class="panel-header" data-debug-name="variablesPanel.header">
		<h2 data-debug-name="variablesPanel.title">🎯 Variables de Trading</h2>
		<div class="header-actions" data-debug-name="variablesPanel.actions">
			{#if hasUnsavedChanges}
				<span class="unsaved-indicator" title="Modifications non sauvegardées - Sauvegarde automatique dans quelques secondes..." data-debug-name="hasUnsavedChanges">
					⚠️ Non sauvegardé
				</span>
			{/if}
			<button class="btn-secondary" on:click={resetDefaults} data-debug-name="variablesPanel.resetButton">🔄 Reset All</button>
			<button class="btn-primary" on:click={saveConfig} disabled={loading} title={hasUnsavedChanges ? 'Sauvegarder immédiatement (annule la sauvegarde automatique)' : 'Forcer la sauvegarde'} data-debug-name="variablesPanel.saveButton">
				{loading ? '⏳ Saving...' : '💾 Save'}
			</button>
			<button class="btn-export" on:click={exportExcel} disabled={exportingExcel} title="Exporter les données du datalogger en Excel (.xlsx)" data-debug-name="variablesPanel.exportExcelButton">
				{exportingExcel ? '⏳ Export...' : '📊 Export Excel'}
			</button>
			<button class="btn-danger" on:click={resetDatabase} disabled={resettingDB} title="⚠️ ATTENTION: Supprime TOUTES les données de la base PostgreSQL" data-debug-name="variablesPanel.resetDBButton">
				{resettingDB ? '⏳ Reset...' : '🗑️ Reset DB'}
			</button>
		</div>
	</div>

	{#if saveMessage}
		<div class="save-message" class:success={saveMessage.includes('✅')} class:error={saveMessage.includes('❌')} data-debug-name="saveMessage">
			{saveMessage}
		</div>
	{/if}

	<!-- Sous-onglets -->
	<div class="subtabs" data-debug-name="variablesPanel.subtabs">
		<button class="subtab" class:active={activeSubTab === 'setups'} on:click={() => activeSubTab = 'setups'} data-debug-name="activeSubTab">
			📊 Setups & Validation
		</button>
		<button class="subtab" class:active={activeSubTab === 'money'} on:click={() => activeSubTab = 'money'} data-debug-name="activeSubTab">
			💰 Money Management
		</button>
		<button class="subtab" class:active={activeSubTab === 'position'} on:click={() => activeSubTab = 'position'} data-debug-name="activeSubTab">
			🎯 TP/SL & Position
		</button>
		<button class="subtab" class:active={activeSubTab === 'ml'} on:click={() => activeSubTab = 'ml'} data-debug-name="activeSubTab">
			🤖 Machine Learning
		</button>
		<button class="subtab" class:active={activeSubTab === 'current'} on:click={() => activeSubTab = 'current'} data-debug-name="activeSubTab">
			📋 Variables en cours
		</button>
	</div>

	<div class="variables-grid">
		<!-- ONGLET SETUPS -->
		{#if activeSubTab === 'setups'}
			<!-- Texte Explicatif: Comment fonctionne la validation des setups -->
			<section class="variable-section">
				<h3>📖 Système de Validation des Setups</h3>
				<div class="setup-explanation">
					<p class="explanation-intro">
						<strong>Comment un setup est-il validé ?</strong><br/>
						Le bot analyse chaque paire en temps réel et combine plusieurs types d'indicateurs pour décider si un trade doit être pris.
					</p>

					<div class="explanation-section">
						<h4>1️⃣ Patterns Techniques</h4>
						<p>
							Les patterns détectent des situations de marché spécifiques (cassure, rebond, rejet, divergence).
							Chaque pattern activé ajoute des conditions qui doivent être remplies avec leurs indicateurs associés.
						</p>
					</div>

					<div class="explanation-section">
						<h4>2️⃣ Patterns de Bougies</h4>
						<p>
							Les patterns de bougies (Doji, Hammer, Engulfing, etc.) détectent des signaux de retournement ou continuation.
							Ils sont calculés automatiquement si activés et augmentent le score du setup.
						</p>
					</div>

					<div class="explanation-section">
						<h4>3️⃣ Système de Score</h4>
						<p>
							Chaque indicateur valide donne des points au setup :
						</p>
						<ul>
							<li><strong>EMAs (2.5 pts)</strong> - Tendance haussière/baissière</li>
							<li><strong>ADX/DI (2.5 pts)</strong> - Force de la tendance</li>
							<li><strong>MACD (2.0 pts)</strong> - Momentum haussier/baissier</li>
							<li><strong>RSI (1.5 pts)</strong> - Momentum + divergences</li>
							<li><strong>Volume (1.5 pts)</strong> - Confirmation par le volume</li>
							<li><strong>Bollinger (0.8 pts)</strong> - Position dans les bandes</li>
							<li><strong>Pattern (0.8 pts)</strong> - Patterns de bougies</li>
						</ul>
						<p>
							Le setup est validé si le <strong>score total</strong> dépasse le <strong>seuil minimum requis</strong> (configurable ci-dessous).
						</p>
					</div>

					<div class="explanation-section">
						<h4>4️⃣ Confluence (Optionnel)</h4>
						<p>
							Si activée, la confluence exige que <strong>TOUS les timeframes</strong> (1m + 5m) confirment le signal.
							Cela réduit le nombre de trades mais augmente la qualité.
						</p>
					</div>

					<div class="explanation-section">
						<h4>5️⃣ Volume</h4>
						<p>
							Le volume actuel doit être supérieur à <strong>volume_multiplier × moyenne</strong>.
							Un volume élevé confirme la validité du mouvement.
						</p>
					</div>
				</div>
			</section>

			<!-- Section 1: Patterns Techniques & Indicateurs Associés -->
			<section class="variable-section">
				<h3>🎯 Patterns Techniques & Indicateurs</h3>
				<p class="section-subtitle">Activez/désactivez chaque pattern et ajustez ses indicateurs associés</p>
				
				<!-- 🔥 FIX: Explication sur le rejet orderbook -->
				<div class="info-box orderbook-info">
					<div class="info-icon">ℹ️</div>
					<div class="info-content">
						<strong>Pourquoi un setup peut être rejeté ?</strong>
						<p>
							Un setup LONG est rejeté si le ratio orderbook (bid/ask) est &lt; 1.1. 
							Ce ratio mesure la pression acheteuse : il faut plus d'ordres d'achat que de vente pour valider un LONG.
							<strong>Ratio actuel &lt; 1.1 = pas assez de pression acheteuse = setup rejeté</strong>
						</p>
						<p>
							Pour un SHORT, le ratio doit être &gt; 0.95 (plus de pression vendeuse).
						</p>
					</div>
				</div>

				<div class="variables-list">
					<!-- 🔥 FIX: Toutes les cases de patterns utilisent le même système de rafraîchissement automatique que confluence -->
					<!-- Mécanisme: bind:checked + triggerAutoSave + config_updated (WebSocket) -->
					<!-- 1. Breakout Pattern -->
					<div class="pattern-group">
						<div class="pattern-header">
							<div class="variable-item checkbox" data-debug-name="config.use_breakout">
								<label for="use-breakout" data-debug-name="config.use_breakout">
									<input
										id="use-breakout"
										type="checkbox"
										bind:checked={config.use_breakout}
										on:change={() => triggerAutoSave('use_breakout', config.use_breakout ? 'Activé' : 'Désactivé')}
										data-debug-name="config.use_breakout"
									/>
									<span class="var-name" data-debug-name="config.use_breakout">🔼 Breakout Pattern</span>
									<span class="var-desc" data-debug-name="config.use_breakout">Cassure de niveaux clés (support/résistance)</span>
								</label>
								<button class="btn-reset" on:click={() => resetVariable('use_breakout')} title="Réinitialiser" data-debug-name="config.use_breakout.reset">⟲</button>
							</div>
						</div>

						{#if config.use_breakout}
							<div class="pattern-indicators">
								<div class="variable-item" data-debug-name="config.breakout_threshold">
									<div class="var-header" data-debug-name="config.breakout_threshold">
										<label for="breakout-threshold" data-debug-name="config.breakout_threshold">
											<span class="var-name" data-debug-name="config.breakout_threshold">Breakout Threshold</span>
											<span class="var-desc" data-debug-name="config.breakout_threshold">Seuil de cassure (distance minimale en × ATR)</span>
										</label>
										<button class="btn-reset" on:click={() => resetVariable('breakout_threshold')} title="Réinitialiser" data-debug-name="config.breakout_threshold.reset">⟲</button>
									</div>
									<div class="slider-container" data-debug-name="config.breakout_threshold">
										<input
											id="breakout-threshold"
											type="range"
											step="0.01"
											min="0"
											max="1"
											bind:value={config.breakout_threshold}
											on:change={() => triggerAutoSave('breakout_threshold', config.breakout_threshold.toFixed(2))}
											data-debug-name="config.breakout_threshold"
										/>
										<span class="slider-value" data-debug-name="config.breakout_threshold">{Number(config.breakout_threshold).toFixed(2)}</span>
									</div>
								</div>
							</div>
						{/if}
					</div>

					<!-- 2. SNR Pattern -->
					<div class="pattern-group">
						<div class="pattern-header">
							<div class="variable-item checkbox" data-debug-name="config.use_snr">
								<label for="use-snr" data-debug-name="config.use_snr">
									<input
										id="use-snr"
										type="checkbox"
										bind:checked={config.use_snr}
										on:change={() => triggerAutoSave('use_snr', config.use_snr ? 'Activé' : 'Désactivé')}
										data-debug-name="config.use_snr"
									/>
									<span class="var-name" data-debug-name="config.use_snr">📍 SNR Pattern</span>
									<span class="var-desc" data-debug-name="config.use_snr">Rebond sur support/résistance</span>
								</label>
								<button class="btn-reset" on:click={() => resetVariable('use_snr')} title="Réinitialiser" data-debug-name="config.use_snr.reset">⟲</button>
							</div>
						</div>

						{#if config.use_snr}
							<div class="pattern-indicators">
								<div class="variable-item" data-debug-name="config.snr_threshold">
									<div class="var-header" data-debug-name="config.snr_threshold">
										<label for="snr-threshold" data-debug-name="config.snr_threshold">
											<span class="var-name" data-debug-name="config.snr_threshold">SNR Threshold</span>
											<span class="var-desc" data-debug-name="config.snr_threshold">Seuil de support/résistance (distance en × ATR)</span>
										</label>
										<button class="btn-reset" on:click={() => resetVariable('snr_threshold')} title="Réinitialiser" data-debug-name="config.snr_threshold.reset">⟲</button>
									</div>
									<div class="slider-container" data-debug-name="config.snr_threshold">
										<input
											id="snr-threshold"
											type="range"
											step="0.01"
											min="0"
											max="1"
											bind:value={config.snr_threshold}
											on:change={() => triggerAutoSave('snr_threshold', config.snr_threshold.toFixed(2))}
											data-debug-name="config.snr_threshold"
										/>
										<span class="slider-value" data-debug-name="config.snr_threshold">{Number(config.snr_threshold).toFixed(2)}</span>
									</div>
								</div>
							</div>
						{/if}
					</div>

					<!-- 3. Wick Pattern -->
					<div class="pattern-group">
						<div class="pattern-header">
							<div class="variable-item checkbox" data-debug-name="config.use_wick">
								<label for="use-wick" data-debug-name="config.use_wick">
									<input
										id="use-wick"
										type="checkbox"
										bind:checked={config.use_wick}
										on:change={() => triggerAutoSave('use_wick', config.use_wick ? 'Activé' : 'Désactivé')}
										data-debug-name="config.use_wick"
									/>
									<span class="var-name" data-debug-name="config.use_wick">📏 Wick Pattern</span>
									<span class="var-desc" data-debug-name="config.use_wick">Rejet de prix via longues mèches</span>
								</label>
								<button class="btn-reset" on:click={() => resetVariable('use_wick')} title="Réinitialiser" data-debug-name="config.use_wick.reset">⟲</button>
							</div>
						</div>

						{#if config.use_wick}
							<div class="pattern-indicators">
								<div class="variable-item" data-debug-name="config.wick_ratio_max">
									<div class="var-header" data-debug-name="config.wick_ratio_max">
										<label for="wick-ratio" data-debug-name="config.wick_ratio_max">
											<span class="var-name" data-debug-name="config.wick_ratio_max">Wick Ratio Max</span>
											<span class="var-desc" data-debug-name="config.wick_ratio_max">Ratio maximum mèche/corps de bougie</span>
										</label>
										<button class="btn-reset" on:click={() => resetVariable('wick_ratio_max')} title="Réinitialiser" data-debug-name="config.wick_ratio_max.reset">⟲</button>
									</div>
									<div class="slider-container" data-debug-name="config.wick_ratio_max">
										<input
											id="wick-ratio"
											type="range"
											step="0.1"
											min="0"
											max="10"
											bind:value={config.wick_ratio_max}
											on:change={() => triggerAutoSave('wick_ratio_max', config.wick_ratio_max.toFixed(1))}
											data-debug-name="config.wick_ratio_max"
										/>
										<span class="slider-value" data-debug-name="config.wick_ratio_max">{Number(config.wick_ratio_max).toFixed(1)}</span>
									</div>
								</div>
							</div>
						{/if}
					</div>

					<!-- 4. Divergence Pattern -->
					<div class="pattern-group">
						<div class="pattern-header">
							<div class="variable-item checkbox" data-debug-name="config.use_divergence">
								<label for="use-divergence" data-debug-name="config.use_divergence">
									<input
										id="use-divergence"
										type="checkbox"
										bind:checked={config.use_divergence}
										on:change={() => triggerAutoSave('use_divergence', config.use_divergence ? 'Activé' : 'Désactivé')}
										data-debug-name="config.use_divergence"
									/>
									<span class="var-name" data-debug-name="config.use_divergence">🔀 Divergence Pattern</span>
									<span class="var-desc" data-debug-name="config.use_divergence">Divergence DI+ vs DI-</span>
								</label>
								<button class="btn-reset" on:click={() => resetVariable('use_divergence')} title="Réinitialiser" data-debug-name="config.use_divergence.reset">⟲</button>
							</div>
						</div>

						{#if config.use_divergence}
							<div class="pattern-indicators">
								<div class="variable-item" data-debug-name="config.di_gap_min">
									<div class="var-header" data-debug-name="config.di_gap_min">
										<label for="di-gap" data-debug-name="config.di_gap_min">
											<span class="var-name" data-debug-name="config.di_gap_min">DI Gap Min</span>
											<span class="var-desc" data-debug-name="config.di_gap_min">Gap minimum entre DI+ et DI-</span>
										</label>
										<button class="btn-reset" on:click={() => resetVariable('di_gap_min')} title="Réinitialiser" data-debug-name="config.di_gap_min.reset">⟲</button>
									</div>
									<div class="slider-container" data-debug-name="config.di_gap_min">
										<input
											id="di-gap"
											type="range"
											step="0.5"
											min="0"
											max="20"
											bind:value={config.di_gap_min}
											on:change={() => triggerAutoSave('di_gap_min', config.di_gap_min.toFixed(1))}
											data-debug-name="config.di_gap_min"
										/>
										<span class="slider-value" data-debug-name="config.di_gap_min">{Number(config.di_gap_min).toFixed(1)}</span>
									</div>
								</div>

								<div class="variable-item" data-debug-name="config.di_gap_adx_threshold">
									<div class="var-header" data-debug-name="config.di_gap_adx_threshold">
										<label for="di-gap-adx-threshold" data-debug-name="config.di_gap_adx_threshold">
											<span class="var-name" data-debug-name="config.di_gap_adx_threshold">DI Gap ADX Threshold</span>
											<span class="var-desc" data-debug-name="config.di_gap_adx_threshold">Seuil ADX pour valider le DI gap</span>
										</label>
										<button class="btn-reset" on:click={() => resetVariable('di_gap_adx_threshold')} title="Réinitialiser" data-debug-name="config.di_gap_adx_threshold.reset">⟲</button>
									</div>
									<div class="slider-container" data-debug-name="config.di_gap_adx_threshold">
										<input
											id="di-gap-adx-threshold"
											type="range"
											step="1"
											min="0"
											max="100"
											bind:value={config.di_gap_adx_threshold}
											on:change={() => triggerAutoSave('di_gap_adx_threshold', config.di_gap_adx_threshold.toFixed(0))}
											data-debug-name="config.di_gap_adx_threshold"
										/>
										<span class="slider-value" data-debug-name="config.di_gap_adx_threshold">{Number(config.di_gap_adx_threshold).toFixed(0)}</span>
									</div>
								</div>
							</div>
						{/if}
					</div>
				</div>
			</section>

			<!-- Section 2: Patterns de Bougies (Candlestick Patterns) -->
			<section class="variable-section">
				<h3>🕯️ Patterns de Bougies</h3>
				<p class="section-subtitle">Patterns de chandeliers détectés automatiquement (1 à 3 bougies)</p>

				<!-- 🔥 FIX: Toutes les cases de bougies utilisent le même système de rafraîchissement automatique que confluence -->
				<!-- Mécanisme: bind:checked + triggerAutoSave + config_updated (WebSocket) -->
				<div class="variables-list candlestick-patterns">
					<div class="variable-item checkbox" data-debug-name="config.use_engulfing">
						<label for="use-engulfing" data-debug-name="config.use_engulfing">
							<input
								id="use-engulfing"
								type="checkbox"
								bind:checked={config.use_engulfing}
								on:change={() => triggerAutoSave('use_engulfing', config.use_engulfing ? 'Activé' : 'Désactivé')}
								data-debug-name="config.use_engulfing"
							/>
							<span class="var-name" data-debug-name="config.use_engulfing">Engulfing</span>
							<span class="var-desc" data-debug-name="config.use_engulfing">Bougie engloutissante (bullish/bearish)</span>
						</label>
						<button class="btn-reset" on:click={() => resetVariable('use_engulfing')} title="Réinitialiser" data-debug-name="config.use_engulfing.reset">⟲</button>
					</div>

					<div class="variable-item checkbox" data-debug-name="config.use_hammer">
						<label for="use-hammer" data-debug-name="config.use_hammer">
							<input
								id="use-hammer"
								type="checkbox"
								bind:checked={config.use_hammer}
								on:change={() => triggerAutoSave('use_hammer', config.use_hammer ? 'Activé' : 'Désactivé')}
								data-debug-name="config.use_hammer"
							/>
							<span class="var-name" data-debug-name="config.use_hammer">Hammer</span>
							<span class="var-desc" data-debug-name="config.use_hammer">Marteau (reversal haussier)</span>
						</label>
						<button class="btn-reset" on:click={() => resetVariable('use_hammer')} title="Réinitialiser" data-debug-name="config.use_hammer.reset">⟲</button>
					</div>

					<div class="variable-item checkbox" data-debug-name="config.use_shooting_star">
						<label for="use-shooting-star" data-debug-name="config.use_shooting_star">
							<input
								id="use-shooting-star"
								type="checkbox"
								bind:checked={config.use_shooting_star}
								on:change={() => triggerAutoSave('use_shooting_star', config.use_shooting_star ? 'Activé' : 'Désactivé')}
								data-debug-name="config.use_shooting_star"
							/>
							<span class="var-name" data-debug-name="config.use_shooting_star">Shooting Star</span>
							<span class="var-desc" data-debug-name="config.use_shooting_star">Étoile filante (reversal baissier)</span>
						</label>
						<button class="btn-reset" on:click={() => resetVariable('use_shooting_star')} title="Réinitialiser" data-debug-name="config.use_shooting_star.reset">⟲</button>
					</div>

					<div class="variable-item checkbox" data-debug-name="config.use_doji">
						<label for="use-doji" data-debug-name="config.use_doji">
							<input
								id="use-doji"
								type="checkbox"
								bind:checked={config.use_doji}
								on:change={() => triggerAutoSave('use_doji', config.use_doji ? 'Activé' : 'Désactivé')}
								data-debug-name="config.use_doji"
							/>
							<span class="var-name" data-debug-name="config.use_doji">Doji</span>
							<span class="var-desc" data-debug-name="config.use_doji">Doji, Dragonfly, Gravestone (indécision)</span>
						</label>
						<button class="btn-reset" on:click={() => resetVariable('use_doji')} title="Réinitialiser" data-debug-name="config.use_doji.reset">⟲</button>
					</div>

					<div class="variable-item checkbox" data-debug-name="config.use_marubozu">
						<label for="use-marubozu" data-debug-name="config.use_marubozu">
							<input
								id="use-marubozu"
								type="checkbox"
								bind:checked={config.use_marubozu}
								on:change={() => triggerAutoSave('use_marubozu', config.use_marubozu ? 'Activé' : 'Désactivé')}
								data-debug-name="config.use_marubozu"
							/>
							<span class="var-name" data-debug-name="config.use_marubozu">Marubozu</span>
							<span class="var-desc" data-debug-name="config.use_marubozu">Bougie pleine (momentum fort)</span>
						</label>
						<button class="btn-reset" on:click={() => resetVariable('use_marubozu')} title="Réinitialiser" data-debug-name="config.use_marubozu.reset">⟲</button>
					</div>

					<div class="variable-item checkbox" data-debug-name="config.use_morning_star">
						<label for="use-morning-star" data-debug-name="config.use_morning_star">
							<input
								id="use-morning-star"
								type="checkbox"
								bind:checked={config.use_morning_star}
								on:change={() => triggerAutoSave('use_morning_star', config.use_morning_star ? 'Activé' : 'Désactivé')}
								data-debug-name="config.use_morning_star"
							/>
							<span class="var-name" data-debug-name="config.use_morning_star">Morning Star</span>
							<span class="var-desc" data-debug-name="config.use_morning_star">Étoile du matin (3 bougies, reversal haussier)</span>
						</label>
						<button class="btn-reset" on:click={() => resetVariable('use_morning_star')} title="Réinitialiser" data-debug-name="config.use_morning_star.reset">⟲</button>
					</div>

					<div class="variable-item checkbox" data-debug-name="config.use_evening_star">
						<label for="use-evening-star" data-debug-name="config.use_evening_star">
							<input
								id="use-evening-star"
								type="checkbox"
								bind:checked={config.use_evening_star}
								on:change={() => triggerAutoSave('use_evening_star', config.use_evening_star ? 'Activé' : 'Désactivé')}
								data-debug-name="config.use_evening_star"
							/>
							<span class="var-name" data-debug-name="config.use_evening_star">Evening Star</span>
							<span class="var-desc" data-debug-name="config.use_evening_star">Étoile du soir (3 bougies, reversal baissier)</span>
						</label>
						<button class="btn-reset" on:click={() => resetVariable('use_evening_star')} title="Réinitialiser" data-debug-name="config.use_evening_star.reset">⟲</button>
					</div>
				</div>
			</section>

			<!-- Section 3: Validation des Setups -->
			<section class="variable-section">
				<h3>✅ Validation des Setups</h3>
				<p class="section-subtitle">Critères pour valider un trade (confluence, volume, score minimum)</p>

				<div class="variables-list">
					<div class="variable-item checkbox" data-debug-name="config.use_confluence">
						<label for="use-confluence" data-debug-name="config.use_confluence">
							<input
								id="use-confluence"
								type="checkbox"
								bind:checked={config.use_confluence}
								on:change={() => triggerAutoSave('use_confluence', config.use_confluence ? 'Activé' : 'Désactivé')}
								data-debug-name="config.use_confluence"
							/>
							<span class="var-name" data-debug-name="config.use_confluence">Use Confluence</span>
							<span class="var-desc" data-debug-name="config.use_confluence">Exiger confirmation sur TOUS les timeframes (1m + 5m)</span>
						</label>
						<button class="btn-reset" on:click={() => resetVariable('use_confluence')} title="Réinitialiser" data-debug-name="config.use_confluence.reset">⟲</button>
					</div>

					<div class="variable-item" data-debug-name="config.volume_multiplier">
						<div class="var-header" data-debug-name="config.volume_multiplier">
							<label for="volume-multiplier" data-debug-name="config.volume_multiplier">
								<span class="var-name" data-debug-name="config.volume_multiplier">Volume Multiplier</span>
								<span class="var-desc" data-debug-name="config.volume_multiplier">Volume actuel doit être > moyenne × ce multiplicateur</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('volume_multiplier')} title="Réinitialiser" data-debug-name="config.volume_multiplier.reset">⟲</button>
						</div>
						<div class="slider-container" data-debug-name="config.volume_multiplier">
							<input
								id="volume-multiplier"
								type="range"
								step="0.05"
								min="0.5"
								max="2"
								bind:value={config.volume_multiplier}
								on:change={() => triggerAutoSave('volume_multiplier', config.volume_multiplier.toFixed(2))}
								data-debug-name="config.volume_multiplier"
							/>
							<span class="slider-value" data-debug-name="config.volume_multiplier">{Number(config.volume_multiplier).toFixed(2)}×</span>
						</div>
					</div>

					<div class="variable-item" data-debug-name="config.min_score_required">
						<div class="var-header" data-debug-name="config.min_score_required">
							<label for="min-score" data-debug-name="config.min_score_required">
								<span class="var-name" data-debug-name="config.min_score_required">Min Score Required</span>
								<span class="var-desc" data-debug-name="config.min_score_required">Score minimum pour valider un setup</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('min_score_required')} title="Réinitialiser" data-debug-name="config.min_score_required.reset">⟲</button>
						</div>
						<div class="slider-container" data-debug-name="config.min_score_required">
							<input
								id="min-score"
								type="range"
								step="0.5"
								min="0"
								max="20"
								bind:value={config.min_score_required}
								on:change={() => triggerAutoSave('min_score_required', config.min_score_required.toFixed(1))}
								data-debug-name="config.min_score_required"
							/>
							<span class="slider-value" data-debug-name="config.min_score_required">{Number(config.min_score_required).toFixed(1)} pts</span>
						</div>
					</div>

					<div class="variable-item" data-debug-name="config.max_slippage_pct">
						<div class="var-header" data-debug-name="config.max_slippage_pct">
							<label for="max-slippage" data-debug-name="config.max_slippage_pct">
								<span class="var-name" data-debug-name="config.max_slippage_pct">Max Slippage</span>
								<span class="var-desc" data-debug-name="config.max_slippage_pct">Slippage maximum accepté avant ouverture de position (0.00% - 0.20%)</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('max_slippage_pct')} title="Réinitialiser" data-debug-name="config.max_slippage_pct.reset">⟲</button>
						</div>
						<div class="slider-container" data-debug-name="config.max_slippage_pct">
							<input
								id="max-slippage"
								type="range"
								step="0.01"
								min="0"
								max="0.20"
								bind:value={config.max_slippage_pct}
								on:change={() => triggerAutoSave('max_slippage_pct', config.max_slippage_pct.toFixed(2))}
								data-debug-name="config.max_slippage_pct"
							/>
							<span class="slider-value" data-debug-name="config.max_slippage_pct">{Number(config.max_slippage_pct).toFixed(2)}%</span>
						</div>
					</div>
				</div>
			</section>

			<!-- Section 4: Timeframes & ATR Optimal -->
			<section class="variable-section">
				<h3>⏱️ Timeframes & ATR Optimal</h3>
				<p class="section-subtitle">Configuration des timeframes et plages ATR optimales pour filtrage</p>

				<div class="variables-list">
					<div class="variable-item" data-debug-name="config.trend_timeframe">
						<div class="var-header" data-debug-name="config.trend_timeframe">
							<label for="trend-timeframe" data-debug-name="config.trend_timeframe">
								<span class="var-name" data-debug-name="config.trend_timeframe">Trend Timeframe</span>
								<span class="var-desc" data-debug-name="config.trend_timeframe">Période pour l'analyse de tendance</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('trend_timeframe')} title="Réinitialiser" data-debug-name="config.trend_timeframe.reset">⟲</button>
						</div>
						<select
							id="trend-timeframe"
							bind:value={config.trend_timeframe}
							on:change={() => triggerAutoSave('trend_timeframe', config.trend_timeframe)}
							data-debug-name="config.trend_timeframe"
						>
							<option value="5m" data-debug-name="config.trend_timeframe.5m">5 minutes</option>
							<option value="15m" data-debug-name="config.trend_timeframe.15m">15 minutes</option>
							<option value="30m" data-debug-name="config.trend_timeframe.30m">30 minutes</option>
							<option value="1h" data-debug-name="config.trend_timeframe.1h">1 heure</option>
						</select>
					</div>

					<div class="variable-item" data-debug-name="config.optimal_atr_min_1m">
						<div class="var-header" data-debug-name="config.optimal_atr_min_1m">
							<label for="optimal-atr-min-1m" data-debug-name="config.optimal_atr_min_1m">
								<span class="var-name" data-debug-name="config.optimal_atr_min_1m">ATR Min 1m (%)</span>
								<span class="var-desc" data-debug-name="config.optimal_atr_min_1m">ATR minimum pour timeframe 1m</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('optimal_atr_min_1m')} title="Réinitialiser" data-debug-name="config.optimal_atr_min_1m.reset">⟲</button>
						</div>
						<div class="slider-container" data-debug-name="config.optimal_atr_min_1m">
							<input
								id="optimal-atr-min-1m"
								type="range"
								step="0.01"
								min="0.01"
								max="1"
								bind:value={config.optimal_atr_min_1m}
								on:change={() => triggerAutoSave('optimal_atr_min_1m', config.optimal_atr_min_1m.toFixed(2) + '%')}
								data-debug-name="config.optimal_atr_min_1m"
							/>
							<span class="slider-value" data-debug-name="config.optimal_atr_min_1m">{Number(config.optimal_atr_min_1m).toFixed(2)}%</span>
						</div>
					</div>

					<div class="variable-item" data-debug-name="config.optimal_atr_max_1m">
						<div class="var-header" data-debug-name="config.optimal_atr_max_1m">
							<label for="optimal-atr-max-1m" data-debug-name="config.optimal_atr_max_1m">
								<span class="var-name" data-debug-name="config.optimal_atr_max_1m">ATR Max 1m (%)</span>
								<span class="var-desc" data-debug-name="config.optimal_atr_max_1m">ATR maximum pour timeframe 1m</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('optimal_atr_max_1m')} title="Réinitialiser" data-debug-name="config.optimal_atr_max_1m.reset">⟲</button>
						</div>
						<div class="slider-container" data-debug-name="config.optimal_atr_max_1m">
							<input
								id="optimal-atr-max-1m"
								type="range"
								step="0.01"
								min="0.1"
								max="5"
								bind:value={config.optimal_atr_max_1m}
								on:change={() => triggerAutoSave('optimal_atr_max_1m', config.optimal_atr_max_1m.toFixed(2) + '%')}
								data-debug-name="config.optimal_atr_max_1m"
							/>
							<span class="slider-value" data-debug-name="config.optimal_atr_max_1m">{Number(config.optimal_atr_max_1m).toFixed(2)}%</span>
						</div>
					</div>

					<div class="variable-item" data-debug-name="config.optimal_atr_min_5m">
						<div class="var-header" data-debug-name="config.optimal_atr_min_5m">
							<label for="optimal-atr-min-5m" data-debug-name="config.optimal_atr_min_5m">
								<span class="var-name" data-debug-name="config.optimal_atr_min_5m">ATR Min 5m (%)</span>
								<span class="var-desc" data-debug-name="config.optimal_atr_min_5m">ATR minimum pour timeframe 5m</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('optimal_atr_min_5m')} title="Réinitialiser" data-debug-name="config.optimal_atr_min_5m.reset">⟲</button>
						</div>
						<div class="slider-container" data-debug-name="config.optimal_atr_min_5m">
							<input
								id="optimal-atr-min-5m"
								type="range"
								step="0.01"
								min="0.01"
								max="1"
								bind:value={config.optimal_atr_min_5m}
								on:change={() => triggerAutoSave('optimal_atr_min_5m', config.optimal_atr_min_5m.toFixed(2) + '%')}
								data-debug-name="config.optimal_atr_min_5m"
							/>
							<span class="slider-value" data-debug-name="config.optimal_atr_min_5m">{Number(config.optimal_atr_min_5m).toFixed(2)}%</span>
						</div>
					</div>

					<div class="variable-item" data-debug-name="config.optimal_atr_max_5m">
						<div class="var-header" data-debug-name="config.optimal_atr_max_5m">
							<label for="optimal-atr-max-5m" data-debug-name="config.optimal_atr_max_5m">
								<span class="var-name" data-debug-name="config.optimal_atr_max_5m">ATR Max 5m (%)</span>
								<span class="var-desc" data-debug-name="config.optimal_atr_max_5m">ATR maximum pour timeframe 5m</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('optimal_atr_max_5m')} title="Réinitialiser" data-debug-name="config.optimal_atr_max_5m.reset">⟲</button>
						</div>
						<div class="slider-container" data-debug-name="config.optimal_atr_max_5m">
							<input
								id="optimal-atr-max-5m"
								type="range"
								step="0.01"
								min="0.1"
								max="5"
								bind:value={config.optimal_atr_max_5m}
								on:change={() => triggerAutoSave('optimal_atr_max_5m', config.optimal_atr_max_5m.toFixed(2) + '%')}
								data-debug-name="config.optimal_atr_max_5m"
							/>
							<span class="slider-value" data-debug-name="config.optimal_atr_max_5m">{Number(config.optimal_atr_max_5m).toFixed(2)}%</span>
						</div>
					</div>
				</div>
			</section>
		{/if}
		<!-- ONGLET MONEY MANAGEMENT -->
		{#if activeSubTab === 'money'}
			<section class="variable-section">
				<h3>💰 Money Management</h3>
				<div class="variables-list">
					<div class="variable-item" data-debug-name="config.account_size">
						<div class="var-header" data-debug-name="config.account_size">
							<label for="account-size" data-debug-name="config.account_size">
								<span class="var-name" data-debug-name="config.account_size">Account Size (USDT)</span>
								<span class="var-desc" data-debug-name="config.account_size">Taille du compte</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('account_size')} title="Réinitialiser" data-debug-name="config.account_size.reset">⟲</button>
						</div>
						<div class="slider-container" data-debug-name="config.account_size">
							<input
								id="account-size"
								type="range"
								step="100"
								min="100"
								max="100000"
								bind:value={config.account_size}
								on:change={() => triggerAutoSave('account_size', `${config.account_size} USDT`)}
								data-debug-name="config.account_size"
							/>
							<span class="slider-value" data-debug-name="config.account_size">{Number(config.account_size).toFixed(0)} USDT</span>
						</div>
					</div>

					<div class="variable-item" data-debug-name="config.risk_per_trade">
						<div class="var-header" data-debug-name="config.risk_per_trade">
							<label for="risk-per-trade" data-debug-name="config.risk_per_trade">
								<span class="var-name" data-debug-name="config.risk_per_trade">Risk per Trade (%)</span>
								<span class="var-desc" data-debug-name="config.risk_per_trade">Risque par trade</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('risk_per_trade')} title="Réinitialiser" data-debug-name="config.risk_per_trade.reset">⟲</button>
						</div>
						<div class="slider-container" data-debug-name="config.risk_per_trade">
							<input
								id="risk-per-trade"
								type="range"
								step="0.1"
								min="0.1"
								max="10"
								bind:value={config.risk_per_trade}
								on:change={() => triggerAutoSave('risk_per_trade', `${config.risk_per_trade.toFixed(1)}%`)}
								data-debug-name="config.risk_per_trade"
							/>
							<span class="slider-value" data-debug-name="config.risk_per_trade">{Number(config.risk_per_trade).toFixed(1)}%</span>
						</div>
					</div>
				</div>

				<!-- 🔥 Section Live Trading -->
				<h3>🔴 Live Trading</h3>
				<div class="variables-list">
					<div class="variable-item" data-debug-name="config.default_leverage">
						<div class="var-header" data-debug-name="config.default_leverage">
							<label for="default-leverage" data-debug-name="config.default_leverage">
								<span class="var-name" data-debug-name="config.default_leverage">Levier par défaut</span>
								<span class="var-desc" data-debug-name="config.default_leverage">Levier utilisé pour les positions Futures (1-50x)</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('default_leverage')} title="Réinitialiser" data-debug-name="config.default_leverage.reset">⟲</button>
						</div>
						<div class="slider-container" data-debug-name="config.default_leverage">
							<input
								id="default-leverage"
								type="range"
								step="1"
								min="1"
								max="50"
								bind:value={config.default_leverage}
								on:change={() => triggerAutoSave('default_leverage', `${config.default_leverage}x`)}
								data-debug-name="config.default_leverage"
							/>
							<span class="slider-value" data-debug-name="config.default_leverage">{Number(config.default_leverage).toFixed(0)}x</span>
						</div>
					</div>

					<div class="variable-item" data-debug-name="config.max_latency_ms">
						<div class="var-header" data-debug-name="config.max_latency_ms">
							<label for="max-latency" data-debug-name="config.max_latency_ms">
								<span class="var-name" data-debug-name="config.max_latency_ms">Latence Max (ms)</span>
								<span class="var-desc" data-debug-name="config.max_latency_ms">Alerter si latence API dépasse ce seuil</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('max_latency_ms')} title="Réinitialiser" data-debug-name="config.max_latency_ms.reset">⟲</button>
						</div>
						<div class="slider-container" data-debug-name="config.max_latency_ms">
							<input
								id="max-latency"
								type="range"
								step="100"
								min="100"
								max="5000"
								bind:value={config.max_latency_ms}
								on:change={() => triggerAutoSave('max_latency_ms', `${config.max_latency_ms}ms`)}
								data-debug-name="config.max_latency_ms"
							/>
							<span class="slider-value" data-debug-name="config.max_latency_ms">{Number(config.max_latency_ms).toFixed(0)}ms</span>
						</div>
					</div>
				</div>
			</section>
		{/if}

		<!-- ONGLET TP/SL & POSITION -->
		{#if activeSubTab === 'position'}
			<section class="variable-section tp-sl-section">
				<h3>🎯 Take Profit / Stop Loss</h3>
				<p class="section-info">
					⚠️ <strong>Note:</strong> Ce sélecteur sert uniquement à afficher les paramètres d'un mode.
					Pour changer le mode actif du bot, utilisez le sélecteur dans l'onglet <strong>Dashboard</strong>.
				</p>
				<div class="variables-list">
					<div class="variable-item" data-debug-name="viewMode">
						<div class="var-header" data-debug-name="viewMode">
							<label for="tp-sl-mode-view" data-debug-name="viewMode">
								<span class="var-name" data-debug-name="viewMode">Afficher Mode</span>
								<span class="var-desc" data-debug-name="viewMode">Sélectionner le mode à configurer (affichage uniquement)</span>
							</label>
						</div>
						<select
							id="tp-sl-mode-view"
							bind:value={viewMode}
							data-debug-name="viewMode"
						>
							<option value="FIXE" data-debug-name="viewMode.FIXE">FIXE - Pourcentages fixes</option>
							<option value="ATR" data-debug-name="viewMode.ATR">ATR - Basé sur volatilité</option>
							<option value="ESCALIER" data-debug-name="viewMode.ESCALIER">ESCALIER - TP partiel progressif</option>
						</select>
					</div>

					<div class="active-mode-indicator" data-debug-name="config.tp_sl_mode">
						<span class="indicator-label" data-debug-name="config.tp_sl_mode">Mode Actif Bot:</span>
						<span class="indicator-value mode-{config.tp_sl_mode.toLowerCase()}" data-debug-name="config.tp_sl_mode">{config.tp_sl_mode}</span>
					</div>

					<!-- Mode FIXE -->
					{#if viewMode === 'FIXE'}
						<div class="mode-settings" data-debug-name="config.mode.FIXE">
							<div class="variable-item" data-debug-name="config.tp_percent">
								<div class="var-header" data-debug-name="config.tp_percent">
									<label for="tp-percent" data-debug-name="config.tp_percent">
										<span class="var-name" data-debug-name="config.tp_percent">TP Percent (%)</span>
										<span class="var-desc" data-debug-name="config.tp_percent">Take profit final en %</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('tp_percent')} title="Réinitialiser" data-debug-name="config.tp_percent.reset">⟲</button>
								</div>
								<div class="slider-container" data-debug-name="config.tp_percent">
									<input
										id="tp-percent"
										type="range"
										step="0.05"
										min="0.05"
										max="5"
										bind:value={config.tp_percent}
										on:change={() => triggerAutoSave('tp_percent', `${config.tp_percent.toFixed(2)}%`)}
										data-debug-name="config.tp_percent"
									/>
									<span class="slider-value" data-debug-name="config.tp_percent">{Number(config.tp_percent).toFixed(2)}%</span>
								</div>
							</div>

							<div class="variable-item" data-debug-name="config.sl_percent">
								<div class="var-header" data-debug-name="config.sl_percent">
									<label for="sl-percent" data-debug-name="config.sl_percent">
										<span class="var-name" data-debug-name="config.sl_percent">SL Percent (%)</span>
										<span class="var-desc" data-debug-name="config.sl_percent">Stop loss en %</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('sl_percent')} title="Réinitialiser" data-debug-name="config.sl_percent.reset">⟲</button>
								</div>
								<div class="slider-container" data-debug-name="config.sl_percent">
									<input
										id="sl-percent"
										type="range"
										step="0.05"
										min="0.05"
										max="5"
										bind:value={config.sl_percent}
										on:change={() => triggerAutoSave('sl_percent', `${config.sl_percent.toFixed(2)}%`)}
										data-debug-name="config.sl_percent"
									/>
									<span class="slider-value" data-debug-name="config.sl_percent">{Number(config.sl_percent).toFixed(2)}%</span>
								</div>
							</div>

							<div class="variable-item" data-debug-name="config.partial_tp_percent">
								<div class="var-header" data-debug-name="config.partial_tp_percent">
									<label for="partial-tp-percent-fixe" data-debug-name="config.partial_tp_percent">
										<span class="var-name" data-debug-name="config.partial_tp_percent">TP Partiel (%)</span>
										<span class="var-desc" data-debug-name="config.partial_tp_percent">% de position clôturée au 1er TP</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('partial_tp_percent')} title="Réinitialiser" data-debug-name="config.partial_tp_percent.reset">⟲</button>
								</div>
								<div class="slider-container" data-debug-name="config.partial_tp_percent">
									<input
										id="partial-tp-percent-fixe"
										type="range"
										step="5"
										min="0"
										max="100"
										bind:value={config.partial_tp_percent}
										on:change={() => triggerAutoSave('partial_tp_percent', `${config.partial_tp_percent}%`)}
										data-debug-name="config.partial_tp_percent"
									/>
									<span class="slider-value" data-debug-name="config.partial_tp_percent">{Number(config.partial_tp_percent).toFixed(0)}%</span>
								</div>
							</div>

							<div class="variable-item" data-debug-name="config.break_even_trigger">
								<div class="var-header" data-debug-name="config.break_even_trigger">
									<label for="break-even-trigger" data-debug-name="config.break_even_trigger">
										<span class="var-name" data-debug-name="config.break_even_trigger">Break Even Trigger (%)</span>
										<span class="var-desc" data-debug-name="config.break_even_trigger">% du 1er TP et d'activation du trailing stop</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('break_even_trigger')} title="Réinitialiser" data-debug-name="config.break_even_trigger.reset">⟲</button>
								</div>
								<div class="slider-container" data-debug-name="config.break_even_trigger">
									<input
										id="break-even-trigger"
										type="range"
										step="0.01"
										min="0.05"
										max="2"
										bind:value={config.break_even_trigger}
										on:change={() => triggerAutoSave('break_even_trigger', `${config.break_even_trigger.toFixed(2)}%`)}
										data-debug-name="config.break_even_trigger"
									/>
									<span class="slider-value" data-debug-name="config.break_even_trigger">{Number(config.break_even_trigger).toFixed(2)}%</span>
								</div>
							</div>

							<div class="variable-item" data-debug-name="config.trailing_distance">
								<div class="var-header" data-debug-name="config.trailing_distance">
									<label for="trailing-distance-fixe" data-debug-name="config.trailing_distance">
										<span class="var-name" data-debug-name="config.trailing_distance">Trailing Distance (%)</span>
										<span class="var-desc" data-debug-name="config.trailing_distance">Distance du trailing stop (après 1er TP)</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('trailing_distance')} title="Réinitialiser" data-debug-name="config.trailing_distance.reset">⟲</button>
								</div>
								<div class="slider-container" data-debug-name="config.trailing_distance">
									<input
										id="trailing-distance-fixe"
										type="range"
										step="0.01"
										min="0.05"
										max="1"
										bind:value={config.trailing_distance}
										on:change={() => triggerAutoSave('trailing_distance', `${config.trailing_distance.toFixed(2)}%`)}
										data-debug-name="config.trailing_distance"
									/>
									<span class="slider-value" data-debug-name="config.trailing_distance">{Number(config.trailing_distance).toFixed(2)}%</span>
								</div>
							</div>
						</div>
					{/if}

					<!-- Mode ATR -->
					{#if viewMode === 'ATR'}
						<div class="mode-settings" data-debug-name="config.mode.ATR">
							<div class="variable-item" data-debug-name="config.atr_mult_tp">
								<div class="var-header" data-debug-name="config.atr_mult_tp">
									<label for="atr-tp" data-debug-name="config.atr_mult_tp">
										<span class="var-name" data-debug-name="config.atr_mult_tp">ATR Mult TP</span>
										<span class="var-desc" data-debug-name="config.atr_mult_tp">Multiplicateur ATR pour TP</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('atr_mult_tp')} title="Réinitialiser" data-debug-name="config.atr_mult_tp.reset">⟲</button>
								</div>
								<div class="slider-container" data-debug-name="config.atr_mult_tp">
									<input
										id="atr-tp"
										type="range"
										step="0.1"
										min="0.5"
										max="5"
										bind:value={config.atr_mult_tp}
										on:change={() => triggerAutoSave('atr_mult_tp', `${config.atr_mult_tp.toFixed(1)}x`)}
										data-debug-name="config.atr_mult_tp"
									/>
									<span class="slider-value" data-debug-name="config.atr_mult_tp">{Number(config.atr_mult_tp).toFixed(1)}x ATR</span>
								</div>
							</div>

							<div class="variable-item" data-debug-name="config.atr_mult_sl">
								<div class="var-header" data-debug-name="config.atr_mult_sl">
									<label for="atr-sl" data-debug-name="config.atr_mult_sl">
										<span class="var-name" data-debug-name="config.atr_mult_sl">ATR Mult SL</span>
										<span class="var-desc" data-debug-name="config.atr_mult_sl">Multiplicateur ATR pour SL</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('atr_mult_sl')} title="Réinitialiser" data-debug-name="config.atr_mult_sl.reset">⟲</button>
								</div>
								<div class="slider-container" data-debug-name="config.atr_mult_sl">
									<input
										id="atr-sl"
										type="range"
										step="0.1"
										min="0.5"
										max="3"
										bind:value={config.atr_mult_sl}
										on:change={() => triggerAutoSave('atr_mult_sl', `${config.atr_mult_sl.toFixed(1)}x`)}
										data-debug-name="config.atr_mult_sl"
									/>
									<span class="slider-value" data-debug-name="config.atr_mult_sl">{Number(config.atr_mult_sl).toFixed(1)}x ATR</span>
								</div>
							</div>

							<div class="variable-item" data-debug-name="config.atr_min">
								<div class="var-header" data-debug-name="config.atr_min">
									<label for="atr-min" data-debug-name="config.atr_min">
										<span class="var-name" data-debug-name="config.atr_min">ATR Min (%)</span>
										<span class="var-desc" data-debug-name="config.atr_min">ATR minimum (limite basse)</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('atr_min')} title="Réinitialiser" data-debug-name="config.atr_min.reset">⟲</button>
								</div>
								<div class="slider-container" data-debug-name="config.atr_min">
									<input
										id="atr-min"
										type="range"
										step="0.01"
										min="0.05"
										max="1"
										bind:value={config.atr_min}
										on:change={() => triggerAutoSave('atr_min', `${config.atr_min.toFixed(2)}%`)}
										data-debug-name="config.atr_min"
									/>
									<span class="slider-value" data-debug-name="config.atr_min">{Number(config.atr_min).toFixed(2)}%</span>
								</div>
							</div>

							<div class="variable-item" data-debug-name="config.atr_max">
								<div class="var-header" data-debug-name="config.atr_max">
									<label for="atr-max" data-debug-name="config.atr_max">
										<span class="var-name" data-debug-name="config.atr_max">ATR Max (%)</span>
										<span class="var-desc" data-debug-name="config.atr_max">ATR maximum (limite haute)</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('atr_max')} title="Réinitialiser" data-debug-name="config.atr_max.reset">⟲</button>
								</div>
								<div class="slider-container" data-debug-name="config.atr_max">
									<input
										id="atr-max"
										type="range"
										step="0.05"
										min="0.5"
										max="5"
										bind:value={config.atr_max}
										on:change={() => triggerAutoSave('atr_max', `${config.atr_max.toFixed(2)}%`)}
										data-debug-name="config.atr_max"
									/>
									<span class="slider-value" data-debug-name="config.atr_max">{Number(config.atr_max).toFixed(2)}%</span>
								</div>
							</div>
						</div>
					{/if}

					<!-- Mode ESCALIER -->
					{#if viewMode === 'ESCALIER'}
						<div class="mode-settings" data-debug-name="config.mode.ESCALIER">
							<p class="mode-description" data-debug-name="config.mode.ESCALIER.description">
								Mode Escalier : Vendez votre position en 4 étapes pour sécuriser progressivement vos profits.
								À chaque niveau, définissez le % de profit (PnL) et la taille de position à clôturer.
							</p>

							<!-- Niveau 1 -->
							<div class="escalier-level" data-debug-name="config.escalier.level1">
								<h4 data-debug-name="config.escalier.level1.title">🎯 Niveau 1</h4>
								<div class="level-inputs" data-debug-name="config.escalier.level1">
									<div class="variable-item" data-debug-name="config.escalier_level1_pnl">
										<div class="var-header" data-debug-name="config.escalier_level1_pnl">
											<label for="escalier-l1-pnl" data-debug-name="config.escalier_level1_pnl">
												<span class="var-name" data-debug-name="config.escalier_level1_pnl">PnL Niveau 1 (%)</span>
												<span class="var-desc" data-debug-name="config.escalier_level1_pnl">% profit pour déclencher TP1</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level1_pnl')} title="Réinitialiser" data-debug-name="config.escalier_level1_pnl.reset">⟲</button>
										</div>
										<div class="slider-container" data-debug-name="config.escalier_level1_pnl">
											<input
												id="escalier-l1-pnl"
												type="range"
												step="0.05"
												min="0.1"
												max="2"
												bind:value={config.escalier_level1_pnl}
												on:change={() => {
													autoAdjustEscalierPnL(1);
													triggerAutoSave('escalier_level1_pnl', `${config.escalier_level1_pnl.toFixed(2)}%`);
												}}
												data-debug-name="config.escalier_level1_pnl"
											/>
											<span class="slider-value" data-debug-name="config.escalier_level1_pnl">{Number(config.escalier_level1_pnl).toFixed(2)}%</span>
										</div>
									</div>

									<div class="variable-item" data-debug-name="config.escalier_level1_size">
										<div class="var-header" data-debug-name="config.escalier_level1_size">
											<label for="escalier-l1-size" data-debug-name="config.escalier_level1_size">
												<span class="var-name" data-debug-name="config.escalier_level1_size">Taille Niveau 1 (%)</span>
												<span class="var-desc" data-debug-name="config.escalier_level1_size">% de position à clôturer</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level1_size')} title="Réinitialiser" data-debug-name="config.escalier_level1_size.reset">⟲</button>
										</div>
										<div class="slider-container" data-debug-name="config.escalier_level1_size">
											<input
												id="escalier-l1-size"
												type="range"
												step="5"
												min="0"
												max="100"
												bind:value={config.escalier_level1_size}
												on:change={() => {
													autoAdjustEscalierSize(1);
													triggerAutoSave('escalier_level1_size', `${config.escalier_level1_size}%`);
												}}
												data-debug-name="config.escalier_level1_size"
											/>
											<span class="slider-value" data-debug-name="config.escalier_level1_size">{Number(config.escalier_level1_size).toFixed(0)}%</span>
										</div>
									</div>
								</div>
							</div>

							<!-- Niveau 2 -->
							<div class="escalier-level" data-debug-name="config.escalier.level2">
								<h4 data-debug-name="config.escalier.level2.title">🎯 Niveau 2</h4>
								<div class="level-inputs" data-debug-name="config.escalier.level2">
									<div class="variable-item" data-debug-name="config.escalier_level2_pnl">
										<div class="var-header" data-debug-name="config.escalier_level2_pnl">
											<label for="escalier-l2-pnl" data-debug-name="config.escalier_level2_pnl">
												<span class="var-name" data-debug-name="config.escalier_level2_pnl">PnL Niveau 2 (%)</span>
												<span class="var-desc" data-debug-name="config.escalier_level2_pnl">% profit pour déclencher TP2</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level2_pnl')} title="Réinitialiser" data-debug-name="config.escalier_level2_pnl.reset">⟲</button>
										</div>
										<div class="slider-container" data-debug-name="config.escalier_level2_pnl">
											<input
												id="escalier-l2-pnl"
												type="range"
												step="0.05"
												min="0.1"
												max="2"
												bind:value={config.escalier_level2_pnl}
												on:change={() => {
													autoAdjustEscalierPnL(2);
													triggerAutoSave('escalier_level2_pnl', `${config.escalier_level2_pnl.toFixed(2)}%`);
												}}
												data-debug-name="config.escalier_level2_pnl"
											/>
											<span class="slider-value" data-debug-name="config.escalier_level2_pnl">{Number(config.escalier_level2_pnl).toFixed(2)}%</span>
										</div>
									</div>

									<div class="variable-item" data-debug-name="config.escalier_level2_size">
										<div class="var-header" data-debug-name="config.escalier_level2_size">
											<label for="escalier-l2-size" data-debug-name="config.escalier_level2_size">
												<span class="var-name" data-debug-name="config.escalier_level2_size">Taille Niveau 2 (%)</span>
												<span class="var-desc" data-debug-name="config.escalier_level2_size">% de position à clôturer</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level2_size')} title="Réinitialiser" data-debug-name="config.escalier_level2_size.reset">⟲</button>
										</div>
										<div class="slider-container" data-debug-name="config.escalier_level2_size">
											<input
												id="escalier-l2-size"
												type="range"
												step="5"
												min="0"
												max="100"
												bind:value={config.escalier_level2_size}
												on:change={() => {
													autoAdjustEscalierSize(2);
													triggerAutoSave('escalier_level2_size', `${config.escalier_level2_size}%`);
												}}
												data-debug-name="config.escalier_level2_size"
											/>
											<span class="slider-value" data-debug-name="config.escalier_level2_size">{Number(config.escalier_level2_size).toFixed(0)}%</span>
										</div>
									</div>
								</div>
							</div>

							<!-- Niveau 3 -->
							<div class="escalier-level" data-debug-name="config.escalier.level3">
								<h4 data-debug-name="config.escalier.level3.title">🎯 Niveau 3</h4>
								<div class="level-inputs" data-debug-name="config.escalier.level3">
									<div class="variable-item" data-debug-name="config.escalier_level3_pnl">
										<div class="var-header" data-debug-name="config.escalier_level3_pnl">
											<label for="escalier-l3-pnl" data-debug-name="config.escalier_level3_pnl">
												<span class="var-name" data-debug-name="config.escalier_level3_pnl">PnL Niveau 3 (%)</span>
												<span class="var-desc" data-debug-name="config.escalier_level3_pnl">% profit pour déclencher TP3</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level3_pnl')} title="Réinitialiser" data-debug-name="config.escalier_level3_pnl.reset">⟲</button>
										</div>
										<div class="slider-container" data-debug-name="config.escalier_level3_pnl">
											<input
												id="escalier-l3-pnl"
												type="range"
												step="0.05"
												min="0.1"
												max="2"
												bind:value={config.escalier_level3_pnl}
												on:change={() => {
													autoAdjustEscalierPnL(3);
													triggerAutoSave('escalier_level3_pnl', `${config.escalier_level3_pnl.toFixed(2)}%`);
												}}
												data-debug-name="config.escalier_level3_pnl"
											/>
											<span class="slider-value" data-debug-name="config.escalier_level3_pnl">{Number(config.escalier_level3_pnl).toFixed(2)}%</span>
										</div>
									</div>

									<div class="variable-item" data-debug-name="config.escalier_level3_size">
										<div class="var-header" data-debug-name="config.escalier_level3_size">
											<label for="escalier-l3-size" data-debug-name="config.escalier_level3_size">
												<span class="var-name" data-debug-name="config.escalier_level3_size">Taille Niveau 3 (%)</span>
												<span class="var-desc" data-debug-name="config.escalier_level3_size">% de position à clôturer</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level3_size')} title="Réinitialiser" data-debug-name="config.escalier_level3_size.reset">⟲</button>
										</div>
										<div class="slider-container" data-debug-name="config.escalier_level3_size">
											<input
												id="escalier-l3-size"
												type="range"
												step="5"
												min="0"
												max="100"
												bind:value={config.escalier_level3_size}
												on:change={() => {
													autoAdjustEscalierSize(3);
													triggerAutoSave('escalier_level3_size', `${config.escalier_level3_size}%`);
												}}
												data-debug-name="config.escalier_level3_size"
											/>
											<span class="slider-value" data-debug-name="config.escalier_level3_size">{Number(config.escalier_level3_size).toFixed(0)}%</span>
										</div>
									</div>
								</div>
							</div>

							<!-- Niveau 4 -->
							<div class="escalier-level" data-debug-name="config.escalier.level4">
								<h4 data-debug-name="config.escalier.level4.title">🎯 Niveau 4</h4>
								<div class="level-inputs" data-debug-name="config.escalier.level4">
									<div class="variable-item" data-debug-name="config.escalier_level4_pnl">
										<div class="var-header" data-debug-name="config.escalier_level4_pnl">
											<label for="escalier-l4-pnl" data-debug-name="config.escalier_level4_pnl">
												<span class="var-name" data-debug-name="config.escalier_level4_pnl">PnL Niveau 4 (%)</span>
												<span class="var-desc" data-debug-name="config.escalier_level4_pnl">% profit pour déclencher TP4 (final)</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level4_pnl')} title="Réinitialiser" data-debug-name="config.escalier_level4_pnl.reset">⟲</button>
										</div>
										<div class="slider-container" data-debug-name="config.escalier_level4_pnl">
											<input
												id="escalier-l4-pnl"
												type="range"
												step="0.05"
												min="0.1"
												max="3"
												bind:value={config.escalier_level4_pnl}
												on:change={() => {
													autoAdjustEscalierPnL(4);
													triggerAutoSave('escalier_level4_pnl', `${config.escalier_level4_pnl.toFixed(2)}%`);
												}}
												data-debug-name="config.escalier_level4_pnl"
											/>
											<span class="slider-value" data-debug-name="config.escalier_level4_pnl">{Number(config.escalier_level4_pnl).toFixed(2)}%</span>
										</div>
									</div>

									<div class="variable-item" data-debug-name="config.escalier_level4_size">
										<div class="var-header" data-debug-name="config.escalier_level4_size">
											<label for="escalier-l4-size" data-debug-name="config.escalier_level4_size">
												<span class="var-name" data-debug-name="config.escalier_level4_size">Taille Niveau 4 (%)</span>
												<span class="var-desc" data-debug-name="config.escalier_level4_size">% de position à clôturer</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level4_size')} title="Réinitialiser" data-debug-name="config.escalier_level4_size.reset">⟲</button>
										</div>
										<div class="slider-container" data-debug-name="config.escalier_level4_size">
											<input
												id="escalier-l4-size"
												type="range"
												step="5"
												min="0"
												max="100"
												bind:value={config.escalier_level4_size}
												on:change={() => {
													autoAdjustEscalierSize(4);
													triggerAutoSave('escalier_level4_size', `${config.escalier_level4_size}%`);
												}}
												data-debug-name="config.escalier_level4_size"
											/>
											<span class="slider-value" data-debug-name="config.escalier_level4_size">{Number(config.escalier_level4_size).toFixed(0)}%</span>
										</div>
									</div>
								</div>
							</div>
						</div>
					{/if}
				</div>
			</section>

			<!-- Section Trailing Stop Adaptatif -->
			<section class="variable-section" data-debug-name="config.trailing">
				<h3 data-debug-name="config.trailing.title">🔄 Trailing Stop Adaptatif</h3>
				<p class="section-desc" data-debug-name="config.trailing.description">S'applique à tous les modes TP/SL</p>
				<div class="variables-list" data-debug-name="config.trailing">
					<div class="variable-item checkbox" data-debug-name="config.trailing_enabled">
						<div class="var-header" data-debug-name="config.trailing_enabled">
							<label for="trailing-enabled" data-debug-name="config.trailing_enabled">
								<input
									id="trailing-enabled"
									type="checkbox"
									bind:checked={config.trailing_enabled}
									on:change={() => triggerAutoSave('trailing_enabled', config.trailing_enabled ? 'Activé' : 'Désactivé')}
									data-debug-name="config.trailing_enabled"
								/>
								<span class="var-name" data-debug-name="config.trailing_enabled">Trailing Stop Enabled</span>
								<span class="var-desc" data-debug-name="config.trailing_enabled">Activer le trailing stop adaptatif</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('trailing_enabled')} title="Réinitialiser" data-debug-name="config.trailing_enabled.reset">⟲</button>
						</div>
					</div>

					<div class="variable-item" data-debug-name="config.trailing_trigger_pnl">
						<div class="var-header" data-debug-name="config.trailing_trigger_pnl">
							<label for="trailing-trigger" data-debug-name="config.trailing_trigger_pnl">
								<span class="var-name" data-debug-name="config.trailing_trigger_pnl">Trigger PnL (%)</span>
								<span class="var-desc" data-debug-name="config.trailing_trigger_pnl">% profit pour activer le trailing</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('trailing_trigger_pnl')} title="Réinitialiser" data-debug-name="config.trailing_trigger_pnl.reset">⟲</button>
						</div>
						<div class="slider-container" data-debug-name="config.trailing_trigger_pnl">
							<input
								id="trailing-trigger"
								type="range"
								step="0.05"
								min="0.1"
								max="3"
								bind:value={config.trailing_trigger_pnl}
								on:change={() => triggerAutoSave('trailing_trigger_pnl', `${config.trailing_trigger_pnl.toFixed(2)}%`)}
								data-debug-name="config.trailing_trigger_pnl"
							/>
							<span class="slider-value" data-debug-name="config.trailing_trigger_pnl">{Number(config.trailing_trigger_pnl).toFixed(2)}%</span>
						</div>
					</div>

					<div class="variable-item" data-debug-name="config.trailing_atr_multiplier">
						<div class="var-header" data-debug-name="config.trailing_atr_multiplier">
							<label for="trailing-atr-mult" data-debug-name="config.trailing_atr_multiplier">
								<span class="var-name" data-debug-name="config.trailing_atr_multiplier">ATR Multiplier</span>
								<span class="var-desc" data-debug-name="config.trailing_atr_multiplier">Distance = ATR × multiplier</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('trailing_atr_multiplier')} title="Réinitialiser" data-debug-name="config.trailing_atr_multiplier.reset">⟲</button>
						</div>
						<div class="slider-container" data-debug-name="config.trailing_atr_multiplier">
							<input
								id="trailing-atr-mult"
								type="range"
								step="0.1"
								min="0.1"
								max="2"
								bind:value={config.trailing_atr_multiplier}
								on:change={() => triggerAutoSave('trailing_atr_multiplier', `${config.trailing_atr_multiplier.toFixed(1)}x`)}
								data-debug-name="config.trailing_atr_multiplier"
							/>
							<span class="slider-value" data-debug-name="config.trailing_atr_multiplier">{Number(config.trailing_atr_multiplier).toFixed(1)}x</span>
						</div>
					</div>

					<div class="variable-item" data-debug-name="config.trailing_min_distance">
						<div class="var-header" data-debug-name="config.trailing_min_distance">
							<label for="trailing-min-dist" data-debug-name="config.trailing_min_distance">
								<span class="var-name" data-debug-name="config.trailing_min_distance">Min Distance (%)</span>
								<span class="var-desc" data-debug-name="config.trailing_min_distance">Distance minimum du trailing</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('trailing_min_distance')} title="Réinitialiser" data-debug-name="config.trailing_min_distance.reset">⟲</button>
						</div>
						<div class="slider-container" data-debug-name="config.trailing_min_distance">
							<input
								id="trailing-min-dist"
								type="range"
								step="0.01"
								min="0.05"
								max="0.5"
								bind:value={config.trailing_min_distance}
								on:change={() => triggerAutoSave('trailing_min_distance', `${config.trailing_min_distance.toFixed(2)}%`)}
								data-debug-name="config.trailing_min_distance"
							/>
							<span class="slider-value" data-debug-name="config.trailing_min_distance">{Number(config.trailing_min_distance).toFixed(2)}%</span>
						</div>
					</div>

					<div class="variable-item" data-debug-name="config.trailing_max_distance">
						<div class="var-header" data-debug-name="config.trailing_max_distance">
							<label for="trailing-max-dist" data-debug-name="config.trailing_max_distance">
								<span class="var-name" data-debug-name="config.trailing_max_distance">Max Distance (%)</span>
								<span class="var-desc" data-debug-name="config.trailing_max_distance">Distance maximum du trailing</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('trailing_max_distance')} title="Réinitialiser" data-debug-name="config.trailing_max_distance.reset">⟲</button>
						</div>
						<div class="slider-container" data-debug-name="config.trailing_max_distance">
							<input
								id="trailing-max-dist"
								type="range"
								step="0.05"
								min="0.1"
								max="2"
								bind:value={config.trailing_max_distance}
								on:change={() => triggerAutoSave('trailing_max_distance', `${config.trailing_max_distance.toFixed(2)}%`)}
								data-debug-name="config.trailing_max_distance"
							/>
							<span class="slider-value" data-debug-name="config.trailing_max_distance">{Number(config.trailing_max_distance).toFixed(2)}%</span>
						</div>
					</div>
				</div>
			</section>
		{/if}

	{#if activeSubTab === 'ml'}
	<!-- Titre et sélecteurs Version ML -->
	<div class="ml-header">
		<h3 class="ml-title">🤖 Machine Learning</h3>
		<div class="ml-version-selector-compact">
			<button
				class="version-btn-compact"
				class:active={mlVersion === 'v1'}
				on:click={() => (mlVersion = 'v1')}
			>
				<span class="version-icon-compact">📊</span>
				<span class="version-label-compact">XGBoost V1</span>
			</button>

			<button
				class="version-btn-compact"
				class:active={mlVersion === 'v2'}
				on:click={() => (mlVersion = 'v2')}
			>
				<span class="version-icon-compact">🚀</span>
				<span class="version-label-compact">XGBoost V2</span>
			</button>
		</div>
	</div>

	{#if mlVersion === 'v1'}
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

	<!-- 3. Section Optimisation Automatique -->
	<section class="variable-section optimization-section">
		<h3>⚡ Optimisation Automatique des Hyperparamètres</h3>
		<p class="section-desc">
			Recherche automatique des meilleurs hyperparamètres par optimisation bayésienne (Optuna).
			Nécessite 1000+ trades pour des résultats fiables.
		</p>

		<OptimizationPanel on:paramsApplied={handleParamsApplied} />
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
				<div class="slider-container">
					<input
						type="range"
						id="ml_min_child_weight"
						min="1"
						max="20"
						step="1"
						bind:value={config.ml_min_child_weight}
						on:change={() => triggerAutoSave('ml_min_child_weight', config.ml_min_child_weight)}
						class="slider"
					/>
					<span class="slider-value">{config.ml_min_child_weight}</span>
				</div>
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
				<div class="slider-container">
					<input
						type="range"
						id="ml_learning_rate"
						min="0.001"
						max="0.2"
						step="0.001"
						bind:value={config.ml_learning_rate}
						on:change={() => triggerAutoSave('ml_learning_rate', config.ml_learning_rate.toFixed(3))}
						class="slider"
					/>
					<span class="slider-value">{Number(config.ml_learning_rate).toFixed(3)}</span>
				</div>
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
	{:else if mlVersion === 'v2'}
	<!-- Contenu XGBoost V2 -->
	<MLCONTENT_V2_Variables {config} {triggerAutoSave} on:paramsApplied={handleParamsApplied} />
	{/if}
	{/if}

	{#if activeSubTab === 'current'}
			<section class="variable-section current-vars-section" data-debug-name="variablesPanel.current">
				<div class="current-vars-header" data-debug-name="variablesPanel.current.header">
					<h3 data-debug-name="variablesPanel.current.title">📋 Variables en cours</h3>
					<button class="btn-refresh" on:click={loadCompleteConfig} disabled={loadingCompleteConfig} data-debug-name="variablesPanel.current.refreshButton">
						{loadingCompleteConfig ? '⏳ Chargement...' : '🔄 Actualiser'}
					</button>
				</div>
				<p class="section-desc" data-debug-name="variablesPanel.current.description">Récapitulatif de toutes les variables actuellement prises en compte par le bot</p>

				{#if loadingCompleteConfig}
					<div class="loading-message" data-debug-name="loadingCompleteConfig">
						⏳ Chargement de la configuration complète...
					</div>
				{:else if completeConfigError}
					<div class="error-message" data-debug-name="completeConfigError">
						❌ Erreur: {completeConfigError}
					</div>
				{:else if completeConfig}
					<div class="complete-config-container" data-debug-name="completeConfig">
						<!-- TRADING_CONFIG organisé par catégories -->
						<div class="config-category main-category" data-debug-name="completeConfig.trading_config">
							<h4 class="category-title" data-debug-name="completeConfig.trading_config.title">🔧 TRADING_CONFIG</h4>
							{#each Object.entries(organizeTradingConfig(completeConfig.trading_config)) as [categoryName, categoryVars]}
								<div class="config-subcategory" data-debug-name="completeConfig.trading_config.{categoryName}">
									<h5 class="subcategory-title" data-debug-name="completeConfig.trading_config.{categoryName}.title">{categoryName}</h5>
									<div class="config-grid" data-debug-name="completeConfig.trading_config.{categoryName}">
										{#each Object.entries(categoryVars) as [key, value]}
											{#if value !== undefined && value !== null}
												<div class="config-item" data-debug-name="completeConfig.trading_config.{categoryName}.{key}">
													<span class="config-key" data-debug-name="completeConfig.trading_config.{categoryName}.{key}">{key}:</span>
													<span class="config-value" title={typeof value === 'object' ? formatFullValue(value) : ''} data-debug-name="completeConfig.trading_config.{categoryName}.{key}">
														{formatValue(value)}
													</span>
												</div>
											{/if}
										{/each}
									</div>
									{#if Object.values(categoryVars).some(v => typeof v === 'object' && v !== null && !Array.isArray(v))}
										<!-- Afficher les objets complexes en détail -->
										{#each Object.entries(categoryVars) as [key, value]}
											{#if typeof value === 'object' && value !== null && !Array.isArray(value)}
												<div class="config-object-detail">
													<details>
														<summary class="config-object-summary">{key} (détails)</summary>
														<pre class="config-object-content">{formatFullValue(value)}</pre>
													</details>
												</div>
											{/if}
										{/each}
									{/if}
								</div>
							{/each}
						</div>

						<!-- RISK_CONFIG -->
						<div class="config-category" data-debug-name="completeConfig.risk_config">
							<h4 class="category-title" data-debug-name="completeConfig.risk_config.title">⚠️ RISK_CONFIG</h4>
							<div class="config-grid" data-debug-name="completeConfig.risk_config">
								{#each Object.entries(completeConfig.risk_config || {}) as [key, value]}
									<div class="config-item" data-debug-name="completeConfig.risk_config.{key}">
										<span class="config-key" data-debug-name="completeConfig.risk_config.{key}">{key}:</span>
										<span class="config-value" data-debug-name="completeConfig.risk_config.{key}">{formatValue(value)}</span>
									</div>
								{/each}
							</div>
						</div>

						<!-- CONDITION_WEIGHTS -->
						<div class="config-category" data-debug-name="completeConfig.condition_weights">
							<h4 class="category-title" data-debug-name="completeConfig.condition_weights.title">⚖️ CONDITION_WEIGHTS</h4>
							<div class="config-grid" data-debug-name="completeConfig.condition_weights">
								{#each Object.entries(completeConfig.condition_weights || {}) as [key, value]}
									<div class="config-item" data-debug-name="completeConfig.condition_weights.{key}">
										<span class="config-key" data-debug-name="completeConfig.condition_weights.{key}">{key}:</span>
										<span class="config-value" data-debug-name="completeConfig.condition_weights.{key}">{formatValue(value)}</span>
									</div>
								{/each}
							</div>
						</div>

						<!-- TREND_BONUS_CONFIG -->
						<div class="config-category" data-debug-name="completeConfig.trend_bonus_config">
							<h4 class="category-title" data-debug-name="completeConfig.trend_bonus_config.title">📈 TREND_BONUS_CONFIG</h4>
							<div class="config-grid" data-debug-name="completeConfig.trend_bonus_config">
								{#each Object.entries(completeConfig.trend_bonus_config || {}) as [key, value]}
									<div class="config-item" data-debug-name="completeConfig.trend_bonus_config.{key}">
										<span class="config-key" data-debug-name="completeConfig.trend_bonus_config.{key}">{key}:</span>
										<span class="config-value" data-debug-name="completeConfig.trend_bonus_config.{key}">{formatValue(value)}</span>
									</div>
								{/each}
							</div>
						</div>

						<!-- RETRY_CONFIG -->
						<div class="config-category" data-debug-name="completeConfig.retry_config">
							<h4 class="category-title" data-debug-name="completeConfig.retry_config.title">🔄 RETRY_CONFIG</h4>
							<div class="config-grid" data-debug-name="completeConfig.retry_config">
								{#each Object.entries(completeConfig.retry_config || {}) as [key, value]}
									<div class="config-item" data-debug-name="completeConfig.retry_config.{key}">
										<span class="config-key" data-debug-name="completeConfig.retry_config.{key}">{key}:</span>
										<span class="config-value" data-debug-name="completeConfig.retry_config.{key}">{formatValue(value)}</span>
									</div>
								{/each}
							</div>
						</div>

						<!-- CIRCUIT_BREAKER_CONFIG -->
						<div class="config-category" data-debug-name="completeConfig.circuit_breaker_config">
							<h4 class="category-title" data-debug-name="completeConfig.circuit_breaker_config.title">⚡ CIRCUIT_BREAKER_CONFIG</h4>
							<div class="config-grid" data-debug-name="completeConfig.circuit_breaker_config">
								{#each Object.entries(completeConfig.circuit_breaker_config || {}) as [key, value]}
									<div class="config-item" data-debug-name="completeConfig.circuit_breaker_config.{key}">
										<span class="config-key" data-debug-name="completeConfig.circuit_breaker_config.{key}">{key}:</span>
										<span class="config-value" data-debug-name="completeConfig.circuit_breaker_config.{key}">{formatValue(value)}</span>
									</div>
								{/each}
							</div>
						</div>

						<!-- WEBSOCKET_CONFIG -->
						<div class="config-category" data-debug-name="completeConfig.websocket_config">
							<h4 class="category-title" data-debug-name="completeConfig.websocket_config.title">📡 WEBSOCKET_CONFIG</h4>
							<div class="config-grid" data-debug-name="completeConfig.websocket_config">
								{#each Object.entries(completeConfig.websocket_config || {}) as [key, value]}
									<div class="config-item" data-debug-name="completeConfig.websocket_config.{key}">
										<span class="config-key" data-debug-name="completeConfig.websocket_config.{key}">{key}:</span>
										<span class="config-value" data-debug-name="completeConfig.websocket_config.{key}">{formatValue(value)}</span>
									</div>
								{/each}
							</div>
						</div>

						<!-- 🔥 LIVE TRADING CONFIG -->
						{#if liveConfig}
							<div class="config-category live-config-highlight" data-debug-name="completeConfig.live_config">
								<h4 class="category-title" data-debug-name="completeConfig.live_config.title">🔴 LIVE TRADING CONFIG</h4>
								{#each Object.entries(organizeLiveConfig(liveConfig)) as [categoryName, categoryVars]}
									<div class="config-subcategory" data-debug-name="completeConfig.live_config.{categoryName}">
										<h5 class="subcategory-title" data-debug-name="completeConfig.live_config.{categoryName}.title">{categoryName}</h5>
										<div class="config-grid" data-debug-name="completeConfig.live_config.{categoryName}">
											{#each Object.entries(categoryVars) as [key, value]}
												<div class="config-item" data-debug-name="completeConfig.live_config.{categoryName}.{key}">
													<span class="config-key" data-debug-name="completeConfig.live_config.{categoryName}.{key}">{key}:</span>
													<span class="config-value" data-debug-name="completeConfig.live_config.{categoryName}.{key}">{formatValue(value)}</span>
												</div>
											{/each}
										</div>
									</div>
								{/each}
							</div>
						{/if}

						<div class="config-timestamp" data-debug-name="completeConfig.timestamp">
							<small data-debug-name="completeConfig.timestamp">Dernière mise à jour: {new Date(completeConfig.timestamp * 1000).toLocaleString('fr-FR')}</small>
						</div>
					</div>
				{:else}
					<div class="info-message" data-debug-name="variablesPanel.current.empty">
						ℹ️ Cliquez sur "Actualiser" pour charger la configuration complète
					</div>
				{/if}
			</section>
		{/if}
	</div>
</div>

<style>
	/* Sélecteurs Version ML */
	.ml-version-selector {
		display: flex;
		gap: 1rem;
		margin-bottom: 2rem;
		padding: 1rem;
		background: rgba(42, 58, 107, 0.3);
		border-radius: 12px;
	}

	.ml-version-selector .version-btn {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		padding: 1rem 1.5rem;
		background: rgba(255, 255, 255, 0.05);
		border: 2px solid rgba(255, 255, 255, 0.1);
		border-radius: 8px;
		color: #a0aec0;
		font-size: 1rem;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.3s;
	}

	.ml-version-selector .version-btn:hover {
		border-color: #667eea;
		transform: translateY(-2px);
		background: rgba(102, 126, 234, 0.1);
	}

	.ml-version-selector .version-btn.active {
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		color: white;
		border-color: #667eea;
		box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
	}

	.ml-version-selector .version-icon {
		font-size: 1.5rem;
	}

	.ml-version-selector .version-label {
		font-size: 1rem;
	}

	.ml-version-selector .version-badge {
		padding: 0.25rem 0.75rem;
		border-radius: 12px;
		font-size: 0.75rem;
		font-weight: 600;
		background: rgba(0, 0, 0, 0.2);
		color: white;
	}

	.ml-version-selector .version-btn:not(.active) .version-badge {
		background: rgba(255, 255, 255, 0.1);
		color: #a0aec0;
	}

	.ml-version-selector .version-badge.new {
		background: linear-gradient(135deg, #10b981 0%, #059669 100%);
		color: white;
		animation: pulse-badge 2s infinite;
	}

	.ml-version-selector .version-btn:not(.active) .version-badge.new {
		background: #10b981;
		color: white;
	}

	@keyframes pulse-badge {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.7;
		}
	}

	/* ML Header avec sélecteur compact */
	.ml-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 1.5rem;
		padding: 1rem 1.5rem;
		background: rgba(42, 58, 107, 0.2);
		border-radius: 10px;
		border: 1px solid rgba(102, 126, 234, 0.2);
	}

	.ml-title {
		margin: 0;
		font-size: 1.25rem;
		color: #00ff88;
		font-weight: 700;
	}

	.ml-version-selector-compact {
		display: flex;
		gap: 0.5rem;
		background: rgba(0, 0, 0, 0.2);
		padding: 0.25rem;
		border-radius: 8px;
		border: 1px solid rgba(255, 255, 255, 0.1);
	}

	.version-btn-compact {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.5rem 1rem;
		background: rgba(255, 255, 255, 0.03);
		border: 1px solid rgba(255, 255, 255, 0.05);
		border-radius: 6px;
		color: #a0aec0;
		font-size: 0.875rem;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s;
	}

	.version-btn-compact:hover {
		border-color: #667eea;
		background: rgba(102, 126, 234, 0.1);
		transform: translateY(-1px);
	}

	.version-btn-compact.active {
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		color: white;
		border-color: #667eea;
		box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
	}

	.version-icon-compact {
		font-size: 1.1rem;
	}

	.version-label-compact {
		font-size: 0.875rem;
		white-space: nowrap;
	}

	.variables-panel {
		background: #1e2749;
		border-radius: 12px;
		padding: 24px;
		border: 2px solid #2a3a6b;
	}

	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 24px;
		padding-bottom: 16px;
		border-bottom: 2px solid #2a3a6b;
	}

	.panel-header h2 {
		font-size: 24px;
		color: #00ff88;
		margin: 0;
	}

	.header-actions {
		display: flex;
		gap: 10px;
		align-items: center;
	}

	.unsaved-indicator {
		padding: 8px 16px;
		background: rgba(255, 193, 7, 0.2);
		border: 1px solid rgba(255, 193, 7, 0.5);
		border-radius: 6px;
		color: #ffc107;
		font-size: 13px;
		font-weight: bold;
		animation: pulse 2s infinite;
		cursor: help;
	}

	@keyframes pulse {
		0%, 100% {
			opacity: 1;
		}
		50% {
			opacity: 0.7;
		}
	}

	.btn-primary,
	.btn-secondary {
		padding: 10px 20px;
		border: none;
		border-radius: 8px;
		font-size: 14px;
		font-weight: bold;
		cursor: pointer;
		transition: all 0.3s;
		text-transform: uppercase;
	}

	.btn-primary {
		background: linear-gradient(135deg, #00ff88 0%, #00cc6a 100%);
		color: #0a0e27;
	}

	.btn-primary:hover:not(:disabled) {
		transform: translateY(-2px);
		box-shadow: 0 4px 15px rgba(0, 255, 136, 0.4);
	}

	.btn-primary:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.btn-secondary {
		background: #2a3a6b;
		color: #fff;
		border: 2px solid #00aaff;
	}

	.btn-secondary:hover {
		background: rgba(0, 170, 255, 0.1);
		transform: translateY(-2px);
	}

	.btn-export {
		background: linear-gradient(135deg, #4a90e2 0%, #357abd 100%);
		color: #fff;
		border: none;
		padding: 10px 20px;
		border-radius: 8px;
		cursor: pointer;
		font-weight: 600;
		transition: all 0.3s ease;
	}

	.btn-export:hover:not(:disabled) {
		transform: translateY(-2px);
		box-shadow: 0 4px 15px rgba(74, 144, 226, 0.4);
	}

	.btn-export:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.btn-danger {
		background: linear-gradient(135deg, #ff4444 0%, #cc0000 100%);
		color: #fff;
		border: none;
		padding: 10px 20px;
		border-radius: 8px;
		cursor: pointer;
		font-weight: 600;
		transition: all 0.3s ease;
	}

	.btn-danger:hover:not(:disabled) {
		transform: translateY(-2px);
		box-shadow: 0 4px 15px rgba(255, 68, 68, 0.4);
	}

	.btn-danger:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.save-message {
		padding: 12px 16px;
		border-radius: 8px;
		margin-bottom: 20px;
		font-size: 14px;
		font-weight: bold;
		text-align: center;
	}

	.save-message.success {
		background: rgba(0, 255, 136, 0.1);
		color: #00ff88;
		border: 1px solid #00ff88;
	}

	.save-message.error {
		background: rgba(255, 68, 68, 0.1);
		color: #ff4444;
		border: 1px solid #ff4444;
	}

	.subtabs {
		display: flex;
		gap: 8px;
		margin-bottom: 24px;
		flex-wrap: wrap;
	}

	.subtab {
		padding: 10px 16px;
		background: #2a3a6b;
		border: 2px solid transparent;
		border-radius: 8px;
		color: #888;
		font-size: 13px;
		font-weight: bold;
		cursor: pointer;
		transition: all 0.3s;
	}

	.subtab:hover {
		background: rgba(0, 170, 255, 0.1);
		border-color: #00aaff;
		color: #00aaff;
	}

	.subtab.active {
		background: linear-gradient(135deg, #00aaff 0%, #0088cc 100%);
		border-color: #00aaff;
		color: #fff;
		box-shadow: 0 2px 10px rgba(0, 170, 255, 0.3);
	}

	.variables-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
		gap: 24px;
	}

	.variable-section {
		background: #0a0e27;
		border-radius: 10px;
		padding: 20px;
		border: 2px solid #2a3a6b;
	}

	.variable-section.tp-sl-section {
		grid-column: 1 / -1;
	}

	.variable-section h3 {
		font-size: 18px;
		color: #00aaff;
		margin: 0 0 16px 0;
		padding-bottom: 12px;
		border-bottom: 1px solid #2a3a6b;
	}

	.section-desc {
		font-size: 13px;
		color: #888;
		margin: -8px 0 16px 0;
		font-style: italic;
	}

	.variables-list {
		display: flex;
		flex-direction: column;
		gap: 20px;
	}

	.variable-item {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.var-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 12px;
	}

	.var-header label {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 4px;
		color: #fff;
	}

	.variable-item.checkbox .var-header label {
		flex-direction: row;
		align-items: center;
		gap: 10px;
	}

	.var-name {
		font-size: 14px;
		font-weight: bold;
		color: #00ff88;
	}

	.var-desc {
		font-size: 12px;
		color: #888;
		font-style: italic;
	}

	.btn-reset {
		background: rgba(255, 170, 0, 0.1);
		border: 1px solid #ffaa00;
		color: #ffaa00;
		padding: 6px 10px;
		border-radius: 6px;
		cursor: pointer;
		font-size: 16px;
		transition: all 0.2s;
		flex-shrink: 0;
	}

	.btn-reset:hover {
		background: rgba(255, 170, 0, 0.2);
		transform: scale(1.1);
	}

	.slider-container {
		display: flex;
		align-items: center;
		gap: 14px;
		padding: 10px 16px;
		background: rgba(255, 255, 255, 0.04);
		border-radius: 14px;
		border: 1px solid rgba(255, 255, 255, 0.08);
		box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.25);
	}

	.slider-container input[type='range'] {
		flex: 1;
		height: 8px;
		background: linear-gradient(90deg, rgba(0, 255, 136, 0.9) 0%, rgba(102, 126, 234, 0.9) 100%);
		border-radius: 999px;
		border: none;
		outline: none;
		-webkit-appearance: none;
	}

	.slider-container input[type='range']::-webkit-slider-thumb {
		-webkit-appearance: none;
		appearance: none;
		width: 18px;
		height: 18px;
		background: #00ff88;
		cursor: pointer;
		border-radius: 50%;
		box-shadow: 0 0 8px rgba(0, 255, 136, 0.5);
		transition: all 0.2s;
	}

	.slider-container input[type='range']::-webkit-slider-thumb:hover {
		width: 22px;
		height: 22px;
		box-shadow: 0 0 15px rgba(0, 255, 136, 0.8);
	}

	.slider-container input[type='range']::-moz-range-thumb {
		width: 18px;
		height: 18px;
		background: #00ff88;
		cursor: pointer;
		border-radius: 50%;
		border: none;
		box-shadow: 0 0 8px rgba(0, 255, 136, 0.5);
		transition: all 0.2s;
	}

	.slider-container input[type='range']::-moz-range-thumb:hover {
		width: 22px;
		height: 22px;
		box-shadow: 0 0 15px rgba(0, 255, 136, 0.8);
	}

	.slider-value {
		font-family: 'Courier New', monospace;
		font-size: 14px;
		font-weight: bold;
		color: #0f172a;
		background: linear-gradient(135deg, #00ff88, #06b6d4);
		padding: 6px 14px;
		border-radius: 999px;
		box-shadow: 0 6px 18px rgba(0, 0, 0, 0.25);
		min-width: 80px;
		text-align: right;
	}

	.variable-item select {
		background: #1e2749;
		border: 2px solid #2a3a6b;
		color: #fff;
		padding: 12px;
		border-radius: 8px;
		font-family: 'Courier New', monospace;
		font-size: 14px;
		transition: all 0.3s;
		cursor: pointer;
	}

	.variable-item select:hover {
		border-color: #00ff88;
	}

	.variable-item select:focus {
		border-color: #00ff88;
		box-shadow: 0 0 0 3px rgba(0, 255, 136, 0.1);
		outline: none;
	}

	.variable-item input[type='checkbox'] {
		width: 20px;
		height: 20px;
		cursor: pointer;
		accent-color: #00ff88;
	}

	.mode-settings {
		background: rgba(0, 170, 255, 0.05);
		border: 1px solid rgba(0, 170, 255, 0.2);
		border-radius: 8px;
		padding: 16px;
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.mode-description {
		color: #888;
		font-size: 13px;
		line-height: 1.6;
		margin-bottom: 8px;
		padding: 12px;
		background: rgba(0, 170, 255, 0.1);
		border-left: 3px solid #00aaff;
		border-radius: 4px;
	}

	.escalier-level {
		background: rgba(0, 255, 136, 0.05);
		border: 1px solid rgba(0, 255, 136, 0.2);
		border-radius: 6px;
		padding: 12px;
		margin-top: 8px;
	}

	.escalier-level h4 {
		color: #00ff88;
		font-size: 14px;
		margin: 0 0 12px 0;
		padding-bottom: 8px;
		border-bottom: 1px solid rgba(0, 255, 136, 0.3);
	}

	.level-inputs {
		display: flex;
		flex-direction: column;
		gap: 12px;
		margin-top: 8px;
	}

	@media (max-width: 768px) {
		.variables-grid {
			grid-template-columns: 1fr;
		}

		.panel-header {
			flex-direction: column;
			gap: 16px;
			align-items: flex-start;
		}

		.header-actions {
			width: 100%;
		}

		.btn-primary,
		.btn-secondary {
			flex: 1;
		}

		.slider-container {
			flex-direction: column;
			align-items: flex-start;
			gap: 8px;
		}

		.slider-container input[type='range'] {
			width: 100%;
		}

		.slider-value {
			min-width: 60px;
			font-size: 12px;
		}

		.subtabs {
			overflow-x: auto;
		}
	}

	/* Section info styling */
	.section-info {
		background: rgba(255, 170, 0, 0.1);
		border-left: 3px solid #ffaa00;
		padding: 12px;
		margin-bottom: 20px;
		font-size: 13px;
		color: #ffaa00;
		border-radius: 4px;
	}

	.section-info strong {
		color: #ffcc00;
	}

	/* Active mode indicator */
	.active-mode-indicator {
		background: rgba(0, 170, 255, 0.1);
		border: 1px solid #00aaff;
		padding: 12px 16px;
		border-radius: 8px;
		display: flex;
		align-items: center;
		gap: 12px;
		margin-bottom: 20px;
	}

	.indicator-label {
		font-weight: bold;
		color: #00aaff;
		font-size: 14px;
	}

	.indicator-value {
		padding: 6px 16px;
		border-radius: 6px;
		font-weight: bold;
		font-size: 14px;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.indicator-value.mode-fixe {
		background: linear-gradient(135deg, #00ff88 0%, #00cc6a 100%);
		color: #0a0e27;
	}

	.indicator-value.mode-atr {
		background: linear-gradient(135deg, #00aaff 0%, #0088cc 100%);
		color: #0a0e27;
	}

	.indicator-value.mode-escalier {
		background: linear-gradient(135deg, #ff8800 0%, #cc6600 100%);
		color: #fff;
	}

	/* Setup Explanation Section */
	.setup-explanation {
		background: rgba(0, 170, 255, 0.05);
		border: 1px solid rgba(0, 170, 255, 0.2);
		border-radius: 8px;
		padding: 20px;
	}

	.explanation-intro {
		font-size: 14px;
		line-height: 1.6;
		color: #ccc;
		margin-bottom: 20px;
	}

	.explanation-section {
		margin-bottom: 16px;
		padding-left: 12px;
		border-left: 2px solid rgba(0, 255, 136, 0.3);
	}

	.explanation-section h4 {
		font-size: 14px;
		color: #00ff88;
		margin: 0 0 8px 0;
	}

	.explanation-section p {
		font-size: 13px;
		line-height: 1.5;
		color: #bbb;
		margin: 0 0 8px 0;
	}

	.explanation-section ul {
		margin: 8px 0;
		padding-left: 20px;
	}

	.explanation-section li {
		font-size: 13px;
		line-height: 1.6;
		color: #bbb;
		margin-bottom: 4px;
	}

	/* 🔥 FIX: Style pour la box d'info orderbook */
	.info-box {
		background: rgba(0, 170, 255, 0.1);
		border: 1px solid rgba(0, 170, 255, 0.3);
		border-radius: 8px;
		padding: 15px;
		margin: 15px 0;
		display: flex;
		gap: 12px;
		align-items: flex-start;
	}

	.info-box.orderbook-info {
		background: rgba(255, 170, 0, 0.1);
		border-color: rgba(255, 170, 0, 0.3);
	}

	.info-icon {
		font-size: 20px;
		flex-shrink: 0;
	}

	.info-content {
		flex: 1;
	}

	.info-content strong {
		color: #00aaff;
		display: block;
		margin-bottom: 8px;
		font-size: 14px;
	}

	.info-content p {
		font-size: 12px;
		color: #aaa;
		line-height: 1.6;
		margin: 5px 0;
	}

	.orderbook-info .info-content strong {
		color: #ffaa00;
	}

	/* Section Subtitle */
	.section-subtitle {
		font-size: 13px;
		color: #888;
		font-style: italic;
		margin: -8px 0 16px 0;
	}

	/* Pattern Groups */
	.pattern-group {
		background: rgba(0, 255, 136, 0.03);
		border: 1px solid rgba(0, 255, 136, 0.15);
		border-radius: 8px;
		padding: 12px;
		margin-bottom: 12px;
	}

	.pattern-header {
		margin-bottom: 8px;
	}

	.pattern-indicators {
		margin-left: 24px;
		padding-left: 16px;
		border-left: 2px solid rgba(0, 255, 136, 0.3);
	}

	/* Candlestick Patterns Grid */
	.candlestick-patterns {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
		gap: 12px;
	}

	/* Variables en cours - Styles */
	.current-vars-section {
		grid-column: 1 / -1;
	}

	.current-vars-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 16px;
	}

	.current-vars-header h3 {
		margin: 0;
	}

	.btn-refresh {
		background: linear-gradient(135deg, #00aaff 0%, #0088cc 100%);
		border: none;
		color: #fff;
		padding: 8px 16px;
		border-radius: 6px;
		font-size: 13px;
		font-weight: bold;
		cursor: pointer;
		transition: all 0.3s;
	}

	.btn-refresh:hover:not(:disabled) {
		transform: translateY(-2px);
		box-shadow: 0 4px 12px rgba(0, 170, 255, 0.4);
	}

	.btn-refresh:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.loading-message,
	.error-message,
	.info-message {
		padding: 20px;
		border-radius: 8px;
		text-align: center;
		font-size: 14px;
		margin: 20px 0;
	}

	.loading-message {
		background: rgba(0, 170, 255, 0.1);
		border: 1px solid rgba(0, 170, 255, 0.3);
		color: #00aaff;
	}

	.error-message {
		background: rgba(255, 68, 68, 0.1);
		border: 1px solid rgba(255, 68, 68, 0.3);
		color: #ff4444;
	}

	.info-message {
		background: rgba(255, 170, 0, 0.1);
		border: 1px solid rgba(255, 170, 0, 0.3);
		color: #ffaa00;
	}

	.complete-config-container {
		display: flex;
		flex-direction: column;
		gap: 24px;
	}

	.config-category {
		background: rgba(0, 170, 255, 0.05);
		border: 1px solid rgba(0, 170, 255, 0.2);
		border-radius: 8px;
		padding: 16px;
	}

	.config-category.main-category {
		background: rgba(0, 170, 255, 0.08);
		border: 2px solid rgba(0, 170, 255, 0.3);
	}

	.config-category.live-config-highlight {
		background: rgba(0, 170, 255, 0.03);
		border: 2px solid rgba(0, 170, 255, 0.2);
		box-shadow: 0 0 10px rgba(0, 170, 255, 0.1);
	}

	.category-title {
		font-size: 18px;
		color: #00aaff;
		margin: 0 0 20px 0;
		padding-bottom: 12px;
		border-bottom: 2px solid rgba(0, 170, 255, 0.3);
		font-weight: bold;
	}

	.config-subcategory {
		margin-bottom: 24px;
		padding: 16px;
		background: rgba(0, 0, 0, 0.2);
		border-radius: 6px;
		border-left: 3px solid rgba(0, 255, 136, 0.5);
	}

	.subcategory-title {
		font-size: 14px;
		color: #00ff88;
		margin: 0 0 12px 0;
		padding-bottom: 8px;
		border-bottom: 1px solid rgba(0, 255, 136, 0.2);
		font-weight: bold;
	}

	.config-object-detail {
		margin-top: 12px;
		padding: 12px;
		background: rgba(0, 0, 0, 0.3);
		border-radius: 6px;
		border: 1px solid rgba(255, 255, 255, 0.1);
	}

	.config-object-summary {
		cursor: pointer;
		color: #00aaff;
		font-size: 13px;
		font-weight: bold;
		padding: 8px;
		user-select: none;
	}

	.config-object-summary:hover {
		color: #00ff88;
	}

	.config-object-content {
		margin: 8px 0 0 0;
		padding: 12px;
		background: rgba(0, 0, 0, 0.5);
		border-radius: 4px;
		font-family: 'Courier New', monospace;
		font-size: 12px;
		color: #ccc;
		overflow-x: auto;
		white-space: pre-wrap;
		word-wrap: break-word;
	}

	.config-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
		gap: 12px;
	}

	.config-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 10px 12px;
		background: rgba(0, 0, 0, 0.3);
		border-radius: 6px;
		border: 1px solid rgba(255, 255, 255, 0.1);
		gap: 12px;
	}

	.config-key {
		font-family: 'Courier New', monospace;
		font-size: 13px;
		color: #00ff88;
		font-weight: bold;
		flex-shrink: 0;
	}

	.config-value {
		font-family: 'Courier New', monospace;
		font-size: 13px;
		color: #fff;
		text-align: right;
		word-break: break-word;
		flex: 1;
	}

	.config-timestamp {
		text-align: center;
		padding: 12px;
		color: #888;
		font-size: 12px;
		border-top: 1px solid rgba(255, 255, 255, 0.1);
		margin-top: 8px;
	}

	@media (max-width: 768px) {
		.config-grid {
			grid-template-columns: 1fr;
		}

		.config-item {
			flex-direction: column;
			align-items: flex-start;
		}

		.config-value {
			text-align: left;
		}
	}
	/* ML Section Styles */
	.ml-info-box {
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		border-radius: 12px;
		padding: 20px;
		color: white;
		margin-top: 20px;
	}

	.ml-info-box h4 {
		margin: 0 0 15px 0;
		font-size: 16px;
		font-weight: 600;
	}

	.ml-metrics {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 15px;
		margin-bottom: 15px;
	}

	.metric {
		background: rgba(255, 255, 255, 0.15);
		padding: 12px;
		border-radius: 8px;
		text-align: center;
	}

	.metric-label {
		display: block;
		font-size: 12px;
		opacity: 0.9;
		margin-bottom: 5px;
	}

	.metric-value {
		display: block;
		font-size: 20px;
		font-weight: bold;
	}

	.metric-value.warning {
		color: #fbbf24;
	}

	.metric-value.danger {
		color: #f87171;
	}

	.ml-warning {
		background: rgba(239, 68, 68, 0.2);
		border: 1px solid rgba(239, 68, 68, 0.4);
		padding: 10px;
		border-radius: 6px;
		font-size: 14px;
		margin: 0;
	}

	.recommendations-box {
		background: #f9fafb;
		border: 2px solid #e5e7eb;
		border-radius: 12px;
		padding: 20px;
		margin-top: 20px;
	}

	.recommendations-box h4 {
		margin: 0 0 15px 0;
		color: #111827;
		font-size: 16px;
	}

	.recommendations-box ul {
		list-style: none;
		padding: 0;
		margin: 0 0 15px 0;
	}

	.recommendations-box li {
		padding: 8px 0;
		border-bottom: 1px solid #e5e7eb;
	}

	.recommendations-box li:last-child {
		border-bottom: none;
	}

	.info-text {
		background: #eff6ff;
		border: 1px solid #93c5fd;
		padding: 12px;
		border-radius: 6px;
		color: #1e40af;
		font-size: 14px;
		margin: 0;
	}

	.variable-item.disabled {
		opacity: 0.5;
		pointer-events: none;
	}

	/* Hyperparameters Subsections */
	.subsection {
		margin: 20px 0;
		padding: 15px;
		background: rgba(0, 0, 0, 0.2);
		border-radius: 8px;
		border-left: 3px solid #00ff88;
	}

	.subsection h4 {
		margin: 0 0 15px 0;
		color: #00ff88;
		font-size: 15px;
		font-weight: 600;
	}

	/* Select Input Styling */
	.select-input {
		width: 100%;
		padding: 8px 12px;
		background: rgba(0, 0, 0, 0.3);
		border: 1px solid rgba(255, 255, 255, 0.2);
		border-radius: 6px;
		color: white;
		font-size: 14px;
		cursor: pointer;
		transition: all 0.2s;
	}

	.select-input:hover {
		border-color: #00ff88;
		background: rgba(0, 0, 0, 0.4);
	}

	.select-input:focus {
		outline: none;
		border-color: #00ff88;
		box-shadow: 0 0 0 2px rgba(0, 255, 136, 0.2);
	}

	.select-input option {
		background: #1a1a1a;
		color: white;
	}

	/* Retrain Section */
	.retrain-section {
		margin-top: 25px;
		padding: 20px;
		background: rgba(0, 255, 136, 0.05);
		border-radius: 8px;
		border: 1px solid rgba(0, 255, 136, 0.2);
		text-align: center;
	}

	.btn-retrain {
		padding: 12px 30px;
		background: linear-gradient(135deg, #00ff88 0%, #00cc6a 100%);
		color: #000;
		border: none;
		border-radius: 8px;
		font-size: 16px;
		font-weight: bold;
		cursor: pointer;
		transition: all 0.3s;
		box-shadow: 0 4px 12px rgba(0, 255, 136, 0.3);
	}

	.btn-retrain:hover:not(:disabled) {
		transform: translateY(-2px);
		box-shadow: 0 6px 16px rgba(0, 255, 136, 0.4);
	}

	.btn-retrain:active:not(:disabled) {
		transform: translateY(0);
	}

	.btn-retrain:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.retrain-hint {
		margin-top: 12px;
		font-size: 13px;
		color: #888;
		line-height: 1.5;
	}

	/* ML Metrics Grid */
	.ml-metrics-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 15px;
		margin-top: 15px;
	}

	.metric-card {
		background: rgba(0, 0, 0, 0.3);
		border: 1px solid rgba(255, 255, 255, 0.1);
		border-radius: 8px;
		padding: 15px;
		text-align: center;
		transition: all 0.2s;
	}

	.metric-card:hover {
		border-color: rgba(0, 255, 136, 0.3);
		background: rgba(0, 0, 0, 0.4);
	}

	.metric-card .metric-label {
		display: block;
		font-size: 12px;
		color: #888;
		margin-bottom: 8px;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.metric-card .metric-value {
		display: block;
		font-size: 24px;
		font-weight: bold;
		color: white;
		margin-bottom: 8px;
	}

	.metric-card .metric-value.danger {
		color: #f87171;
	}

	.metric-status {
		display: inline-block;
		padding: 4px 12px;
		border-radius: 12px;
		font-size: 11px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.metric-status.poor {
		background: rgba(239, 68, 68, 0.2);
		color: #f87171;
		border: 1px solid rgba(239, 68, 68, 0.4);
	}

	.metric-status.ok {
		background: rgba(59, 130, 246, 0.2);
		color: #60a5fa;
		border: 1px solid rgba(59, 130, 246, 0.4);
	}

	.metric-status.good {
		background: rgba(16, 185, 129, 0.2);
		color: #10b981;
		border: 1px solid rgba(16, 185, 129, 0.4);
	}

	.metric-status.danger {
		background: rgba(239, 68, 68, 0.2);
		color: #f87171;
		border: 1px solid rgba(239, 68, 68, 0.4);
	}

	/* Optimisation automatique */
	.optimization-section {
		margin-top: 2rem;
	}

	.optimization-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1.5rem;
		margin-top: 1rem;
	}

	@media (max-width: 1200px) {
		.optimization-grid {
			grid-template-columns: 1fr;
		}
	}

</style>
