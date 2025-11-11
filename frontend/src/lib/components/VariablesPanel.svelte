<script lang="ts">
	import { onMount } from 'svelte';
	import { sendCommandViaWS } from '$lib/utils/websocket';

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
		snr_threshold: 0.25,
		breakout_threshold: 0.35,
		wick_ratio_max: 2.8,
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
		min_score_required: 7.5,
		// Money Management
		account_size: 1000.0,
		risk_per_trade: 2.0,
		// TP/SL Mode
		tp_sl_mode: 'FIXE',
		// Mode FIXE
		tp_percent: 0.6,
		sl_percent: 0.25,
		partial_tp_percent: 50,
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
		trailing_trigger_pnl: 0.25,
		trailing_atr_multiplier: 0.4,
		trailing_min_distance: 0.08,
		trailing_max_distance: 0.25
	};

	let config = { ...DEFAULTS };
	let loading = false;
	let saveMessage = '';
	let activeSubTab = 'setups';
	let viewMode = 'FIXE'; // Mode affiché dans TP/SL (ne modifie PAS config.tp_sl_mode)
	
	// 🔥 NOUVEAU: Système de sauvegarde automatique avec debounce
	let hasUnsavedChanges = false;
	let debounceTimer: ReturnType<typeof setTimeout> | null = null;
	const AUTO_SAVE_DELAY = 2500; // 2.5 secondes d'inactivité avant sauvegarde automatique
	
	// Variables pour l'onglet "Variables en cours"
	let completeConfig = null;
	let loadingCompleteConfig = false;
	let completeConfigError = null;

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
		} catch (err) {
			console.error('❌ Erreur chargement config complète:', err);
			completeConfigError = err.message || 'Impossible de charger la configuration complète';
		} finally {
			loadingCompleteConfig = false;
		}
	}
	
	// Charger la config complète quand on active l'onglet
	$: if (activeSubTab === 'current' && !completeConfig && !loadingCompleteConfig) {
		loadCompleteConfig();
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

	async function loadConfig() {
		try {
			// 🔥 FIX: Ne pas recharger la config si on a des changements non sauvegardés (pour éviter d'écraser les modifications)
			if (hasUnsavedChanges) {
				console.log('⚠️ Changements non sauvegardés détectés, chargement de la config ignoré pour préserver les modifications');
				return;
			}
			
			// 🔥 BIDIRECTIONNEL: Utiliser WebSocket uniquement
			const { getWebSocket, sendRequestViaWS } = await import('$lib/utils/websocket');
			const ws = getWebSocket();

			if (!ws || !ws.connected) {
				throw new Error('WebSocket non connecté');
			}

			const response = await sendRequestViaWS('state', {});
			const stateData = response?.data || response;
			
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
							newConfig[key] = stateData.config[key];
						}
					}
				});
				config = newConfig; // Assigner le nouvel objet pour déclencher la réactivité
				viewMode = config.tp_sl_mode || 'FIXE';
				console.log('✅ Config chargée depuis backend via WebSocket:', config);
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
	
	// Fonction pour logger les changements (pour historique backend)
	async function logConfigChange(key: string, change: any) {
		// 🔥 MIGRATION COMPLÈTE: Envoyer log via WebSocket natif uniquement
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
								newConfig[key] = data.updated[key];
							}
						}
					});
					config = newConfig; // Assigner le nouvel objet pour déclencher la réactivité
					
					if (data.updated.tp_sl_mode) {
						viewMode = data.updated.tp_sl_mode;
					}
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

<div class="variables-panel">
	<div class="panel-header">
		<h2>🎯 Variables de Trading</h2>
		<div class="header-actions">
			{#if hasUnsavedChanges}
				<span class="unsaved-indicator" title="Modifications non sauvegardées - Sauvegarde automatique dans quelques secondes...">
					⚠️ Non sauvegardé
				</span>
			{/if}
			<button class="btn-secondary" on:click={resetDefaults}>🔄 Reset All</button>
			<button class="btn-primary" on:click={saveConfig} disabled={loading} title={hasUnsavedChanges ? 'Sauvegarder immédiatement (annule la sauvegarde automatique)' : 'Forcer la sauvegarde'}>
				{loading ? '⏳ Saving...' : '💾 Save'}
			</button>
		</div>
	</div>

	{#if saveMessage}
		<div class="save-message" class:success={saveMessage.includes('✅')} class:error={saveMessage.includes('❌')}>
			{saveMessage}
		</div>
	{/if}

	<!-- Sous-onglets -->
	<div class="subtabs">
		<button class="subtab" class:active={activeSubTab === 'setups'} on:click={() => activeSubTab = 'setups'}>
			📊 Setups & Validation
		</button>
		<button class="subtab" class:active={activeSubTab === 'money'} on:click={() => activeSubTab = 'money'}>
			💰 Money Management
		</button>
		<button class="subtab" class:active={activeSubTab === 'position'} on:click={() => activeSubTab = 'position'}>
			🎯 TP/SL & Position
		</button>
		<button class="subtab" class:active={activeSubTab === 'current'} on:click={() => activeSubTab = 'current'}>
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
					<!-- 1. Breakout Pattern -->
					<div class="pattern-group">
						<div class="pattern-header">
							<div class="variable-item checkbox">
								<label for="use-breakout">
									<input
										id="use-breakout"
										type="checkbox"
										bind:checked={config.use_breakout}
										on:change={() => triggerAutoSave('use_breakout', config.use_breakout ? 'Activé' : 'Désactivé')}
									/>
									<span class="var-name">🔼 Breakout Pattern</span>
									<span class="var-desc">Cassure de niveaux clés (support/résistance)</span>
								</label>
								<button class="btn-reset" on:click={() => resetVariable('use_breakout')} title="Réinitialiser">⟲</button>
							</div>
						</div>

						{#if config.use_breakout}
							<div class="pattern-indicators">
								<div class="variable-item">
									<div class="var-header">
										<label for="breakout-threshold">
											<span class="var-name">Breakout Threshold</span>
											<span class="var-desc">Seuil de cassure (distance minimale en × ATR)</span>
										</label>
										<button class="btn-reset" on:click={() => resetVariable('breakout_threshold')} title="Réinitialiser">⟲</button>
									</div>
									<div class="slider-container">
										<input
											id="breakout-threshold"
											type="range"
											step="0.01"
											min="0"
											max="1"
											bind:value={config.breakout_threshold}
											on:change={() => triggerAutoSave('breakout_threshold', config.breakout_threshold.toFixed(2))}
										/>
										<span class="slider-value">{Number(config.breakout_threshold).toFixed(2)}</span>
									</div>
								</div>
							</div>
						{/if}
					</div>

					<!-- 2. SNR Pattern -->
					<div class="pattern-group">
						<div class="pattern-header">
							<div class="variable-item checkbox">
								<label for="use-snr">
									<input
										id="use-snr"
										type="checkbox"
										bind:checked={config.use_snr}
										on:change={() => triggerAutoSave('use_snr', config.use_snr ? 'Activé' : 'Désactivé')}
									/>
									<span class="var-name">📍 SNR Pattern</span>
									<span class="var-desc">Rebond sur support/résistance</span>
								</label>
								<button class="btn-reset" on:click={() => resetVariable('use_snr')} title="Réinitialiser">⟲</button>
							</div>
						</div>

						{#if config.use_snr}
							<div class="pattern-indicators">
								<div class="variable-item">
									<div class="var-header">
										<label for="snr-threshold">
											<span class="var-name">SNR Threshold</span>
											<span class="var-desc">Seuil de support/résistance (distance en × ATR)</span>
										</label>
										<button class="btn-reset" on:click={() => resetVariable('snr_threshold')} title="Réinitialiser">⟲</button>
									</div>
									<div class="slider-container">
										<input
											id="snr-threshold"
											type="range"
											step="0.01"
											min="0"
											max="1"
											bind:value={config.snr_threshold}
											on:change={() => triggerAutoSave('snr_threshold', config.snr_threshold.toFixed(2))}
										/>
										<span class="slider-value">{Number(config.snr_threshold).toFixed(2)}</span>
									</div>
								</div>
							</div>
						{/if}
					</div>

					<!-- 3. Wick Pattern -->
					<div class="pattern-group">
						<div class="pattern-header">
							<div class="variable-item checkbox">
								<label for="use-wick">
									<input
										id="use-wick"
										type="checkbox"
										bind:checked={config.use_wick}
										on:change={() => triggerAutoSave('use_wick', config.use_wick ? 'Activé' : 'Désactivé')}
									/>
									<span class="var-name">📏 Wick Pattern</span>
									<span class="var-desc">Rejet de prix via longues mèches</span>
								</label>
								<button class="btn-reset" on:click={() => resetVariable('use_wick')} title="Réinitialiser">⟲</button>
							</div>
						</div>

						{#if config.use_wick}
							<div class="pattern-indicators">
								<div class="variable-item">
									<div class="var-header">
										<label for="wick-ratio">
											<span class="var-name">Wick Ratio Max</span>
											<span class="var-desc">Ratio maximum mèche/corps de bougie</span>
										</label>
										<button class="btn-reset" on:click={() => resetVariable('wick_ratio_max')} title="Réinitialiser">⟲</button>
									</div>
									<div class="slider-container">
										<input
											id="wick-ratio"
											type="range"
											step="0.1"
											min="0"
											max="10"
											bind:value={config.wick_ratio_max}
											on:change={() => triggerAutoSave('wick_ratio_max', config.wick_ratio_max.toFixed(1))}
										/>
										<span class="slider-value">{Number(config.wick_ratio_max).toFixed(1)}</span>
									</div>
								</div>
							</div>
						{/if}
					</div>

					<!-- 4. Divergence Pattern -->
					<div class="pattern-group">
						<div class="pattern-header">
							<div class="variable-item checkbox">
								<label for="use-divergence">
									<input
										id="use-divergence"
										type="checkbox"
										bind:checked={config.use_divergence}
										on:change={() => triggerAutoSave('use_divergence', config.use_divergence ? 'Activé' : 'Désactivé')}
									/>
									<span class="var-name">🔀 Divergence Pattern</span>
									<span class="var-desc">Divergence DI+ vs DI-</span>
								</label>
								<button class="btn-reset" on:click={() => resetVariable('use_divergence')} title="Réinitialiser">⟲</button>
							</div>
						</div>

						{#if config.use_divergence}
							<div class="pattern-indicators">
								<div class="variable-item">
									<div class="var-header">
										<label for="di-gap">
											<span class="var-name">DI Gap Min</span>
											<span class="var-desc">Gap minimum entre DI+ et DI-</span>
										</label>
										<button class="btn-reset" on:click={() => resetVariable('di_gap_min')} title="Réinitialiser">⟲</button>
									</div>
									<div class="slider-container">
										<input
											id="di-gap"
											type="range"
											step="0.5"
											min="0"
											max="20"
											bind:value={config.di_gap_min}
											on:change={() => triggerAutoSave('di_gap_min', config.di_gap_min.toFixed(1))}
										/>
										<span class="slider-value">{Number(config.di_gap_min).toFixed(1)}</span>
									</div>
								</div>

								<div class="variable-item">
									<div class="var-header">
										<label for="di-gap-adx-threshold">
											<span class="var-name">DI Gap ADX Threshold</span>
											<span class="var-desc">Seuil ADX pour valider le DI gap</span>
										</label>
										<button class="btn-reset" on:click={() => resetVariable('di_gap_adx_threshold')} title="Réinitialiser">⟲</button>
									</div>
									<div class="slider-container">
										<input
											id="di-gap-adx-threshold"
											type="range"
											step="1"
											min="0"
											max="100"
											bind:value={config.di_gap_adx_threshold}
											on:change={() => triggerAutoSave('di_gap_adx_threshold', config.di_gap_adx_threshold.toFixed(0))}
										/>
										<span class="slider-value">{Number(config.di_gap_adx_threshold).toFixed(0)}</span>
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

				<div class="variables-list candlestick-patterns">
					<div class="variable-item checkbox">
						<label for="use-engulfing">
							<input
								id="use-engulfing"
								type="checkbox"
								bind:checked={config.use_engulfing}
								on:change={() => triggerAutoSave('use_engulfing', config.use_engulfing ? 'Activé' : 'Désactivé')}
							/>
							<span class="var-name">Engulfing</span>
							<span class="var-desc">Bougie engloutissante (bullish/bearish)</span>
						</label>
						<button class="btn-reset" on:click={() => resetVariable('use_engulfing')} title="Réinitialiser">⟲</button>
					</div>

					<div class="variable-item checkbox">
						<label for="use-hammer">
							<input
								id="use-hammer"
								type="checkbox"
								bind:checked={config.use_hammer}
								on:change={() => triggerAutoSave('use_hammer', config.use_hammer ? 'Activé' : 'Désactivé')}
							/>
							<span class="var-name">Hammer</span>
							<span class="var-desc">Marteau (reversal haussier)</span>
						</label>
						<button class="btn-reset" on:click={() => resetVariable('use_hammer')} title="Réinitialiser">⟲</button>
					</div>

					<div class="variable-item checkbox">
						<label for="use-shooting-star">
							<input
								id="use-shooting-star"
								type="checkbox"
								bind:checked={config.use_shooting_star}
								on:change={() => triggerAutoSave('use_shooting_star', config.use_shooting_star ? 'Activé' : 'Désactivé')}
							/>
							<span class="var-name">Shooting Star</span>
							<span class="var-desc">Étoile filante (reversal baissier)</span>
						</label>
						<button class="btn-reset" on:click={() => resetVariable('use_shooting_star')} title="Réinitialiser">⟲</button>
					</div>

					<div class="variable-item checkbox">
						<label for="use-doji">
							<input
								id="use-doji"
								type="checkbox"
								bind:checked={config.use_doji}
								on:change={() => triggerAutoSave('use_doji', config.use_doji ? 'Activé' : 'Désactivé')}
							/>
							<span class="var-name">Doji</span>
							<span class="var-desc">Doji, Dragonfly, Gravestone (indécision)</span>
						</label>
						<button class="btn-reset" on:click={() => resetVariable('use_doji')} title="Réinitialiser">⟲</button>
					</div>

					<div class="variable-item checkbox">
						<label for="use-marubozu">
							<input
								id="use-marubozu"
								type="checkbox"
								bind:checked={config.use_marubozu}
								on:change={() => triggerAutoSave('use_marubozu', config.use_marubozu ? 'Activé' : 'Désactivé')}
							/>
							<span class="var-name">Marubozu</span>
							<span class="var-desc">Bougie pleine (momentum fort)</span>
						</label>
						<button class="btn-reset" on:click={() => resetVariable('use_marubozu')} title="Réinitialiser">⟲</button>
					</div>

					<div class="variable-item checkbox">
						<label for="use-morning-star">
							<input
								id="use-morning-star"
								type="checkbox"
								bind:checked={config.use_morning_star}
								on:change={() => triggerAutoSave('use_morning_star', config.use_morning_star ? 'Activé' : 'Désactivé')}
							/>
							<span class="var-name">Morning Star</span>
							<span class="var-desc">Étoile du matin (3 bougies, reversal haussier)</span>
						</label>
						<button class="btn-reset" on:click={() => resetVariable('use_morning_star')} title="Réinitialiser">⟲</button>
					</div>

					<div class="variable-item checkbox">
						<label for="use-evening-star">
							<input
								id="use-evening-star"
								type="checkbox"
								bind:checked={config.use_evening_star}
								on:change={() => triggerAutoSave('use_evening_star', config.use_evening_star ? 'Activé' : 'Désactivé')}
							/>
							<span class="var-name">Evening Star</span>
							<span class="var-desc">Étoile du soir (3 bougies, reversal baissier)</span>
						</label>
						<button class="btn-reset" on:click={() => resetVariable('use_evening_star')} title="Réinitialiser">⟲</button>
					</div>
				</div>
			</section>

			<!-- Section 3: Validation des Setups -->
			<section class="variable-section">
				<h3>✅ Validation des Setups</h3>
				<p class="section-subtitle">Critères pour valider un trade (confluence, volume, score minimum)</p>

				<div class="variables-list">
					<div class="variable-item checkbox">
						<label for="use-confluence">
							<input
								id="use-confluence"
								type="checkbox"
								bind:checked={config.use_confluence}
								on:change={() => triggerAutoSave('use_confluence', config.use_confluence ? 'Activé' : 'Désactivé')}
							/>
							<span class="var-name">Use Confluence</span>
							<span class="var-desc">Exiger confirmation sur TOUS les timeframes (1m + 5m)</span>
						</label>
						<button class="btn-reset" on:click={() => resetVariable('use_confluence')} title="Réinitialiser">⟲</button>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="volume-multiplier">
								<span class="var-name">Volume Multiplier</span>
								<span class="var-desc">Volume actuel doit être > moyenne × ce multiplicateur</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('volume_multiplier')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="volume-multiplier"
								type="range"
								step="0.05"
								min="0.5"
								max="2"
								bind:value={config.volume_multiplier}
								on:change={() => triggerAutoSave('volume_multiplier', config.volume_multiplier.toFixed(2))}
							/>
							<span class="slider-value">{Number(config.volume_multiplier).toFixed(2)}×</span>
						</div>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="min-score">
								<span class="var-name">Min Score Required</span>
								<span class="var-desc">Score minimum pour valider un setup</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('min_score_required')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="min-score"
								type="range"
								step="0.5"
								min="0"
								max="20"
								bind:value={config.min_score_required}
								on:change={() => triggerAutoSave('min_score_required', config.min_score_required.toFixed(1))}
							/>
							<span class="slider-value">{Number(config.min_score_required).toFixed(1)} pts</span>
						</div>
					</div>
				</div>
			</section>

			<!-- Section 4: Timeframes & ATR Optimal -->
			<section class="variable-section">
				<h3>⏱️ Timeframes & ATR Optimal</h3>
				<p class="section-subtitle">Configuration des timeframes et plages ATR optimales pour filtrage</p>

				<div class="variables-list">
					<div class="variable-item">
						<div class="var-header">
							<label for="trend-timeframe">
								<span class="var-name">Trend Timeframe</span>
								<span class="var-desc">Période pour l'analyse de tendance</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('trend_timeframe')} title="Réinitialiser">⟲</button>
						</div>
						<select
							id="trend-timeframe"
							bind:value={config.trend_timeframe}
							on:change={() => triggerAutoSave('trend_timeframe', config.trend_timeframe)}
						>
							<option value="5m">5 minutes</option>
							<option value="15m">15 minutes</option>
							<option value="30m">30 minutes</option>
							<option value="1h">1 heure</option>
						</select>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="optimal-atr-min-1m">
								<span class="var-name">ATR Min 1m (%)</span>
								<span class="var-desc">ATR minimum pour timeframe 1m</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('optimal_atr_min_1m')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="optimal-atr-min-1m"
								type="range"
								step="0.01"
								min="0.01"
								max="1"
								bind:value={config.optimal_atr_min_1m}
								on:change={() => triggerAutoSave('optimal_atr_min_1m', config.optimal_atr_min_1m.toFixed(2) + '%')}
							/>
							<span class="slider-value">{Number(config.optimal_atr_min_1m).toFixed(2)}%</span>
						</div>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="optimal-atr-max-1m">
								<span class="var-name">ATR Max 1m (%)</span>
								<span class="var-desc">ATR maximum pour timeframe 1m</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('optimal_atr_max_1m')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="optimal-atr-max-1m"
								type="range"
								step="0.01"
								min="0.1"
								max="5"
								bind:value={config.optimal_atr_max_1m}
								on:change={() => triggerAutoSave('optimal_atr_max_1m', config.optimal_atr_max_1m.toFixed(2) + '%')}
							/>
							<span class="slider-value">{Number(config.optimal_atr_max_1m).toFixed(2)}%</span>
						</div>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="optimal-atr-min-5m">
								<span class="var-name">ATR Min 5m (%)</span>
								<span class="var-desc">ATR minimum pour timeframe 5m</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('optimal_atr_min_5m')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="optimal-atr-min-5m"
								type="range"
								step="0.01"
								min="0.01"
								max="1"
								bind:value={config.optimal_atr_min_5m}
								on:change={() => triggerAutoSave('optimal_atr_min_5m', config.optimal_atr_min_5m.toFixed(2) + '%')}
							/>
							<span class="slider-value">{Number(config.optimal_atr_min_5m).toFixed(2)}%</span>
						</div>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="optimal-atr-max-5m">
								<span class="var-name">ATR Max 5m (%)</span>
								<span class="var-desc">ATR maximum pour timeframe 5m</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('optimal_atr_max_5m')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="optimal-atr-max-5m"
								type="range"
								step="0.01"
								min="0.1"
								max="5"
								bind:value={config.optimal_atr_max_5m}
								on:change={() => triggerAutoSave('optimal_atr_max_5m', config.optimal_atr_max_5m.toFixed(2) + '%')}
							/>
							<span class="slider-value">{Number(config.optimal_atr_max_5m).toFixed(2)}%</span>
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
					<div class="variable-item">
						<div class="var-header">
							<label for="account-size">
								<span class="var-name">Account Size (USDT)</span>
								<span class="var-desc">Taille du compte</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('account_size')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="account-size"
								type="range"
								step="100"
								min="100"
								max="100000"
								bind:value={config.account_size}
								on:change={() => triggerAutoSave('account_size', `${config.account_size} USDT`)}
							/>
							<span class="slider-value">{Number(config.account_size).toFixed(0)} USDT</span>
						</div>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="risk-per-trade">
								<span class="var-name">Risk per Trade (%)</span>
								<span class="var-desc">Risque par trade</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('risk_per_trade')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="risk-per-trade"
								type="range"
								step="0.1"
								min="0.1"
								max="10"
								bind:value={config.risk_per_trade}
								on:change={() => triggerAutoSave('risk_per_trade', `${config.risk_per_trade.toFixed(1)}%`)}
							/>
							<span class="slider-value">{Number(config.risk_per_trade).toFixed(1)}%</span>
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
					<div class="variable-item">
						<div class="var-header">
							<label for="tp-sl-mode-view">
								<span class="var-name">Afficher Mode</span>
								<span class="var-desc">Sélectionner le mode à configurer (affichage uniquement)</span>
							</label>
						</div>
						<select
							id="tp-sl-mode-view"
							bind:value={viewMode}
						>
							<option value="FIXE">FIXE - Pourcentages fixes</option>
							<option value="ATR">ATR - Basé sur volatilité</option>
							<option value="ESCALIER">ESCALIER - TP partiel progressif</option>
						</select>
					</div>

					<div class="active-mode-indicator">
						<span class="indicator-label">Mode Actif Bot:</span>
						<span class="indicator-value mode-{config.tp_sl_mode.toLowerCase()}">{config.tp_sl_mode}</span>
					</div>

					<!-- Mode FIXE -->
					{#if viewMode === 'FIXE'}
						<div class="mode-settings">
							<div class="variable-item">
								<div class="var-header">
									<label for="tp-percent">
										<span class="var-name">TP Percent (%)</span>
										<span class="var-desc">Take profit final en %</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('tp_percent')} title="Réinitialiser">⟲</button>
								</div>
								<div class="slider-container">
									<input
										id="tp-percent"
										type="range"
										step="0.05"
										min="0.05"
										max="5"
										bind:value={config.tp_percent}
										on:change={() => triggerAutoSave('tp_percent', `${config.tp_percent.toFixed(2)}%`)}
									/>
									<span class="slider-value">{Number(config.tp_percent).toFixed(2)}%</span>
								</div>
							</div>

							<div class="variable-item">
								<div class="var-header">
									<label for="sl-percent">
										<span class="var-name">SL Percent (%)</span>
										<span class="var-desc">Stop loss en %</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('sl_percent')} title="Réinitialiser">⟲</button>
								</div>
								<div class="slider-container">
									<input
										id="sl-percent"
										type="range"
										step="0.05"
										min="0.05"
										max="5"
										bind:value={config.sl_percent}
										on:change={() => triggerAutoSave('sl_percent', `${config.sl_percent.toFixed(2)}%`)}
									/>
									<span class="slider-value">{Number(config.sl_percent).toFixed(2)}%</span>
								</div>
							</div>

							<div class="variable-item">
								<div class="var-header">
									<label for="partial-tp-percent-fixe">
										<span class="var-name">TP Partiel (%)</span>
										<span class="var-desc">% de position clôturée au 1er TP</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('partial_tp_percent')} title="Réinitialiser">⟲</button>
								</div>
								<div class="slider-container">
									<input
										id="partial-tp-percent-fixe"
										type="range"
										step="5"
										min="0"
										max="100"
										bind:value={config.partial_tp_percent}
										on:change={() => triggerAutoSave('partial_tp_percent', `${config.partial_tp_percent}%`)}
									/>
									<span class="slider-value">{Number(config.partial_tp_percent).toFixed(0)}%</span>
								</div>
							</div>
						</div>
					{/if}

					<!-- Mode ATR -->
					{#if viewMode === 'ATR'}
						<div class="mode-settings">
							<div class="variable-item">
								<div class="var-header">
									<label for="atr-tp">
										<span class="var-name">ATR Mult TP</span>
										<span class="var-desc">Multiplicateur ATR pour TP</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('atr_mult_tp')} title="Réinitialiser">⟲</button>
								</div>
								<div class="slider-container">
									<input
										id="atr-tp"
										type="range"
										step="0.1"
										min="0.5"
										max="5"
										bind:value={config.atr_mult_tp}
										on:change={() => triggerAutoSave('atr_mult_tp', `${config.atr_mult_tp.toFixed(1)}x`)}
									/>
									<span class="slider-value">{Number(config.atr_mult_tp).toFixed(1)}x ATR</span>
								</div>
							</div>

							<div class="variable-item">
								<div class="var-header">
									<label for="atr-sl">
										<span class="var-name">ATR Mult SL</span>
										<span class="var-desc">Multiplicateur ATR pour SL</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('atr_mult_sl')} title="Réinitialiser">⟲</button>
								</div>
								<div class="slider-container">
									<input
										id="atr-sl"
										type="range"
										step="0.1"
										min="0.5"
										max="3"
										bind:value={config.atr_mult_sl}
										on:change={() => triggerAutoSave('atr_mult_sl', `${config.atr_mult_sl.toFixed(1)}x`)}
									/>
									<span class="slider-value">{Number(config.atr_mult_sl).toFixed(1)}x ATR</span>
								</div>
							</div>

							<div class="variable-item">
								<div class="var-header">
									<label for="atr-min">
										<span class="var-name">ATR Min (%)</span>
										<span class="var-desc">ATR minimum (limite basse)</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('atr_min')} title="Réinitialiser">⟲</button>
								</div>
								<div class="slider-container">
									<input
										id="atr-min"
										type="range"
										step="0.01"
										min="0.05"
										max="1"
										bind:value={config.atr_min}
										on:change={() => triggerAutoSave('atr_min', `${config.atr_min.toFixed(2)}%`)}
									/>
									<span class="slider-value">{Number(config.atr_min).toFixed(2)}%</span>
								</div>
							</div>

							<div class="variable-item">
								<div class="var-header">
									<label for="atr-max">
										<span class="var-name">ATR Max (%)</span>
										<span class="var-desc">ATR maximum (limite haute)</span>
									</label>
									<button class="btn-reset" on:click={() => resetVariable('atr_max')} title="Réinitialiser">⟲</button>
								</div>
								<div class="slider-container">
									<input
										id="atr-max"
										type="range"
										step="0.05"
										min="0.5"
										max="5"
										bind:value={config.atr_max}
										on:change={() => triggerAutoSave('atr_max', `${config.atr_max.toFixed(2)}%`)}
									/>
									<span class="slider-value">{Number(config.atr_max).toFixed(2)}%</span>
								</div>
							</div>
						</div>
					{/if}

					<!-- Mode ESCALIER -->
					{#if viewMode === 'ESCALIER'}
						<div class="mode-settings">
							<p class="mode-description">
								Mode Escalier : Vendez votre position en 4 étapes pour sécuriser progressivement vos profits.
								À chaque niveau, définissez le % de profit (PnL) et la taille de position à clôturer.
							</p>

							<!-- Niveau 1 -->
							<div class="escalier-level">
								<h4>🎯 Niveau 1</h4>
								<div class="level-inputs">
									<div class="variable-item">
										<div class="var-header">
											<label for="escalier-l1-pnl">
												<span class="var-name">PnL Niveau 1 (%)</span>
												<span class="var-desc">% profit pour déclencher TP1</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level1_pnl')} title="Réinitialiser">⟲</button>
										</div>
										<div class="slider-container">
											<input
												id="escalier-l1-pnl"
												type="range"
												step="0.05"
												min="0.1"
												max="2"
												bind:value={config.escalier_level1_pnl}
												on:change={() => {
													autoAdjustEscalierPnL(1);
													logConfigChange('escalier_level1_pnl', `${config.escalier_level1_pnl.toFixed(2)}%`);
												}}
											/>
											<span class="slider-value">{Number(config.escalier_level1_pnl).toFixed(2)}%</span>
										</div>
									</div>

									<div class="variable-item">
										<div class="var-header">
											<label for="escalier-l1-size">
												<span class="var-name">Taille Niveau 1 (%)</span>
												<span class="var-desc">% de position à clôturer</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level1_size')} title="Réinitialiser">⟲</button>
										</div>
										<div class="slider-container">
											<input
												id="escalier-l1-size"
												type="range"
												step="5"
												min="0"
												max="100"
												bind:value={config.escalier_level1_size}
												on:change={() => {
													autoAdjustEscalierSize(1);
													logConfigChange('escalier_level1_size', `${config.escalier_level1_size}%`);
												}}
											/>
											<span class="slider-value">{Number(config.escalier_level1_size).toFixed(0)}%</span>
										</div>
									</div>
								</div>
							</div>

							<!-- Niveau 2 -->
							<div class="escalier-level">
								<h4>🎯 Niveau 2</h4>
								<div class="level-inputs">
									<div class="variable-item">
										<div class="var-header">
											<label for="escalier-l2-pnl">
												<span class="var-name">PnL Niveau 2 (%)</span>
												<span class="var-desc">% profit pour déclencher TP2</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level2_pnl')} title="Réinitialiser">⟲</button>
										</div>
										<div class="slider-container">
											<input
												id="escalier-l2-pnl"
												type="range"
												step="0.05"
												min="0.1"
												max="2"
												bind:value={config.escalier_level2_pnl}
												on:change={() => {
													autoAdjustEscalierPnL(2);
													logConfigChange('escalier_level2_pnl', `${config.escalier_level2_pnl.toFixed(2)}%`);
												}}
											/>
											<span class="slider-value">{Number(config.escalier_level2_pnl).toFixed(2)}%</span>
										</div>
									</div>

									<div class="variable-item">
										<div class="var-header">
											<label for="escalier-l2-size">
												<span class="var-name">Taille Niveau 2 (%)</span>
												<span class="var-desc">% de position à clôturer</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level2_size')} title="Réinitialiser">⟲</button>
										</div>
										<div class="slider-container">
											<input
												id="escalier-l2-size"
												type="range"
												step="5"
												min="0"
												max="100"
												bind:value={config.escalier_level2_size}
												on:change={() => {
													autoAdjustEscalierSize(2);
													logConfigChange('escalier_level2_size', `${config.escalier_level2_size}%`);
												}}
											/>
											<span class="slider-value">{Number(config.escalier_level2_size).toFixed(0)}%</span>
										</div>
									</div>
								</div>
							</div>

							<!-- Niveau 3 -->
							<div class="escalier-level">
								<h4>🎯 Niveau 3</h4>
								<div class="level-inputs">
									<div class="variable-item">
										<div class="var-header">
											<label for="escalier-l3-pnl">
												<span class="var-name">PnL Niveau 3 (%)</span>
												<span class="var-desc">% profit pour déclencher TP3</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level3_pnl')} title="Réinitialiser">⟲</button>
										</div>
										<div class="slider-container">
											<input
												id="escalier-l3-pnl"
												type="range"
												step="0.05"
												min="0.1"
												max="2"
												bind:value={config.escalier_level3_pnl}
												on:change={() => {
													autoAdjustEscalierPnL(3);
													logConfigChange('escalier_level3_pnl', `${config.escalier_level3_pnl.toFixed(2)}%`);
												}}
											/>
											<span class="slider-value">{Number(config.escalier_level3_pnl).toFixed(2)}%</span>
										</div>
									</div>

									<div class="variable-item">
										<div class="var-header">
											<label for="escalier-l3-size">
												<span class="var-name">Taille Niveau 3 (%)</span>
												<span class="var-desc">% de position à clôturer</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level3_size')} title="Réinitialiser">⟲</button>
										</div>
										<div class="slider-container">
											<input
												id="escalier-l3-size"
												type="range"
												step="5"
												min="0"
												max="100"
												bind:value={config.escalier_level3_size}
												on:change={() => {
													autoAdjustEscalierSize(3);
													logConfigChange('escalier_level3_size', `${config.escalier_level3_size}%`);
												}}
											/>
											<span class="slider-value">{Number(config.escalier_level3_size).toFixed(0)}%</span>
										</div>
									</div>
								</div>
							</div>

							<!-- Niveau 4 -->
							<div class="escalier-level">
								<h4>🎯 Niveau 4</h4>
								<div class="level-inputs">
									<div class="variable-item">
										<div class="var-header">
											<label for="escalier-l4-pnl">
												<span class="var-name">PnL Niveau 4 (%)</span>
												<span class="var-desc">% profit pour déclencher TP4 (final)</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level4_pnl')} title="Réinitialiser">⟲</button>
										</div>
										<div class="slider-container">
											<input
												id="escalier-l4-pnl"
												type="range"
												step="0.05"
												min="0.1"
												max="3"
												bind:value={config.escalier_level4_pnl}
												on:change={() => {
													autoAdjustEscalierPnL(4);
													logConfigChange('escalier_level4_pnl', `${config.escalier_level4_pnl.toFixed(2)}%`);
												}}
											/>
											<span class="slider-value">{Number(config.escalier_level4_pnl).toFixed(2)}%</span>
										</div>
									</div>

									<div class="variable-item">
										<div class="var-header">
											<label for="escalier-l4-size">
												<span class="var-name">Taille Niveau 4 (%)</span>
												<span class="var-desc">% de position à clôturer</span>
											</label>
											<button class="btn-reset" on:click={() => resetVariable('escalier_level4_size')} title="Réinitialiser">⟲</button>
										</div>
										<div class="slider-container">
											<input
												id="escalier-l4-size"
												type="range"
												step="5"
												min="0"
												max="100"
												bind:value={config.escalier_level4_size}
												on:change={() => {
													autoAdjustEscalierSize(4);
													logConfigChange('escalier_level4_size', `${config.escalier_level4_size}%`);
												}}
											/>
											<span class="slider-value">{Number(config.escalier_level4_size).toFixed(0)}%</span>
										</div>
									</div>
								</div>
							</div>
						</div>
					{/if}
				</div>
			</section>

			<!-- Section Trailing Stop Adaptatif -->
			<section class="variable-section">
				<h3>🔄 Trailing Stop Adaptatif</h3>
				<p class="section-desc">S'applique à tous les modes TP/SL</p>
				<div class="variables-list">
					<div class="variable-item checkbox">
						<div class="var-header">
							<label for="trailing-enabled">
								<input
									id="trailing-enabled"
									type="checkbox"
									bind:checked={config.trailing_enabled}
									on:change={() => triggerAutoSave('trailing_enabled', config.trailing_enabled ? 'Activé' : 'Désactivé')}
								/>
								<span class="var-name">Trailing Stop Enabled</span>
								<span class="var-desc">Activer le trailing stop adaptatif</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('trailing_enabled')} title="Réinitialiser">⟲</button>
						</div>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="trailing-trigger">
								<span class="var-name">Trigger PnL (%)</span>
								<span class="var-desc">% profit pour activer le trailing</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('trailing_trigger_pnl')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="trailing-trigger"
								type="range"
								step="0.05"
								min="0.1"
								max="3"
								bind:value={config.trailing_trigger_pnl}
								on:change={() => triggerAutoSave('trailing_trigger_pnl', `${config.trailing_trigger_pnl.toFixed(2)}%`)}
							/>
							<span class="slider-value">{Number(config.trailing_trigger_pnl).toFixed(2)}%</span>
						</div>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="trailing-atr-mult">
								<span class="var-name">ATR Multiplier</span>
								<span class="var-desc">Distance = ATR × multiplier</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('trailing_atr_multiplier')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="trailing-atr-mult"
								type="range"
								step="0.1"
								min="0.1"
								max="2"
								bind:value={config.trailing_atr_multiplier}
								on:change={() => triggerAutoSave('trailing_atr_multiplier', `${config.trailing_atr_multiplier.toFixed(1)}x`)}
							/>
							<span class="slider-value">{Number(config.trailing_atr_multiplier).toFixed(1)}x</span>
						</div>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="trailing-min-dist">
								<span class="var-name">Min Distance (%)</span>
								<span class="var-desc">Distance minimum du trailing</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('trailing_min_distance')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="trailing-min-dist"
								type="range"
								step="0.01"
								min="0.05"
								max="0.5"
								bind:value={config.trailing_min_distance}
								on:change={() => triggerAutoSave('trailing_min_distance', `${config.trailing_min_distance.toFixed(2)}%`)}
							/>
							<span class="slider-value">{Number(config.trailing_min_distance).toFixed(2)}%</span>
						</div>
					</div>

					<div class="variable-item">
						<div class="var-header">
							<label for="trailing-max-dist">
								<span class="var-name">Max Distance (%)</span>
								<span class="var-desc">Distance maximum du trailing</span>
							</label>
							<button class="btn-reset" on:click={() => resetVariable('trailing_max_distance')} title="Réinitialiser">⟲</button>
						</div>
						<div class="slider-container">
							<input
								id="trailing-max-dist"
								type="range"
								step="0.05"
								min="0.1"
								max="2"
								bind:value={config.trailing_max_distance}
								on:change={() => triggerAutoSave('trailing_max_distance', `${config.trailing_max_distance.toFixed(2)}%`)}
							/>
							<span class="slider-value">{Number(config.trailing_max_distance).toFixed(2)}%</span>
						</div>
					</div>
				</div>
			</section>
		{/if}

		<!-- ONGLET VARIABLES EN COURS -->
		{#if activeSubTab === 'current'}
			<section class="variable-section current-vars-section">
				<div class="current-vars-header">
					<h3>📋 Variables en cours</h3>
					<button class="btn-refresh" on:click={loadCompleteConfig} disabled={loadingCompleteConfig}>
						{loadingCompleteConfig ? '⏳ Chargement...' : '🔄 Actualiser'}
					</button>
				</div>
				<p class="section-desc">Récapitulatif de toutes les variables actuellement prises en compte par le bot</p>

				{#if loadingCompleteConfig}
					<div class="loading-message">
						⏳ Chargement de la configuration complète...
					</div>
				{:else if completeConfigError}
					<div class="error-message">
						❌ Erreur: {completeConfigError}
					</div>
				{:else if completeConfig}
					<div class="complete-config-container">
						<!-- TRADING_CONFIG organisé par catégories -->
						<div class="config-category main-category">
							<h4 class="category-title">🔧 TRADING_CONFIG</h4>
							{#each Object.entries(organizeTradingConfig(completeConfig.trading_config)) as [categoryName, categoryVars]}
								<div class="config-subcategory">
									<h5 class="subcategory-title">{categoryName}</h5>
									<div class="config-grid">
										{#each Object.entries(categoryVars) as [key, value]}
											{#if value !== undefined && value !== null}
												<div class="config-item">
													<span class="config-key">{key}:</span>
													<span class="config-value" title={typeof value === 'object' ? formatFullValue(value) : ''}>
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
						<div class="config-category">
							<h4 class="category-title">⚠️ RISK_CONFIG</h4>
							<div class="config-grid">
								{#each Object.entries(completeConfig.risk_config || {}) as [key, value]}
									<div class="config-item">
										<span class="config-key">{key}:</span>
										<span class="config-value">{formatValue(value)}</span>
									</div>
								{/each}
							</div>
						</div>

						<!-- CONDITION_WEIGHTS -->
						<div class="config-category">
							<h4 class="category-title">⚖️ CONDITION_WEIGHTS</h4>
							<div class="config-grid">
								{#each Object.entries(completeConfig.condition_weights || {}) as [key, value]}
									<div class="config-item">
										<span class="config-key">{key}:</span>
										<span class="config-value">{formatValue(value)}</span>
									</div>
								{/each}
							</div>
						</div>

						<!-- TREND_BONUS_CONFIG -->
						<div class="config-category">
							<h4 class="category-title">📈 TREND_BONUS_CONFIG</h4>
							<div class="config-grid">
								{#each Object.entries(completeConfig.trend_bonus_config || {}) as [key, value]}
									<div class="config-item">
										<span class="config-key">{key}:</span>
										<span class="config-value">{formatValue(value)}</span>
									</div>
								{/each}
							</div>
						</div>

						<!-- RETRY_CONFIG -->
						<div class="config-category">
							<h4 class="category-title">🔄 RETRY_CONFIG</h4>
							<div class="config-grid">
								{#each Object.entries(completeConfig.retry_config || {}) as [key, value]}
									<div class="config-item">
										<span class="config-key">{key}:</span>
										<span class="config-value">{formatValue(value)}</span>
									</div>
								{/each}
							</div>
						</div>

						<!-- CIRCUIT_BREAKER_CONFIG -->
						<div class="config-category">
							<h4 class="category-title">⚡ CIRCUIT_BREAKER_CONFIG</h4>
							<div class="config-grid">
								{#each Object.entries(completeConfig.circuit_breaker_config || {}) as [key, value]}
									<div class="config-item">
										<span class="config-key">{key}:</span>
										<span class="config-value">{formatValue(value)}</span>
									</div>
								{/each}
							</div>
						</div>

						<!-- WEBSOCKET_CONFIG -->
						<div class="config-category">
							<h4 class="category-title">📡 WEBSOCKET_CONFIG</h4>
							<div class="config-grid">
								{#each Object.entries(completeConfig.websocket_config || {}) as [key, value]}
									<div class="config-item">
										<span class="config-key">{key}:</span>
										<span class="config-value">{formatValue(value)}</span>
									</div>
								{/each}
							</div>
						</div>

						<div class="config-timestamp">
							<small>Dernière mise à jour: {new Date(completeConfig.timestamp * 1000).toLocaleString('fr-FR')}</small>
						</div>
					</div>
				{:else}
					<div class="info-message">
						ℹ️ Cliquez sur "Actualiser" pour charger la configuration complète
					</div>
				{/if}
			</section>
		{/if}
	</div>
</div>

<style>
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
		gap: 12px;
		background: #1e2749;
		padding: 12px;
		border-radius: 8px;
		border: 2px solid #2a3a6b;
	}

	.slider-container input[type='range'] {
		flex: 1;
		height: 6px;
		background: #2a3a6b;
		border-radius: 3px;
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
		color: #00ff88;
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
</style>
