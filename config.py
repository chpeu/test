"""
Configuration globale pour Trade Cursor
"""
import os

# 🔥 NOUVEAU: Charger variables d'environnement depuis .env si disponible
try:
    from dotenv import load_dotenv
    from pathlib import Path
    # 🔥 FIX: Charger .env depuis la racine du projet (où se trouve config.py)
    env_path = Path(__file__).parent / '.env'
    load_dotenv(dotenv_path=env_path)  # Charge .env à la racine du projet
except ImportError:
    # python-dotenv non installé, continuer sans
    pass
except Exception as e:
    # Erreur lors du chargement .env, continuer sans
    import logging
    logging.warning(f"⚠️ Erreur chargement .env: {e}")

# API MEXC
MEXC_FUTURES_URL = "https://contract.mexc.com"

# Trading parameters
TRADING_CONFIG = {
    "fee_per_trade": 0.0004,  # 0.04% par trade
    "use_slippage_calculation": True,  # Calculer slippage estimé basé sur spread et profondeur
    "position_timeout": 300,  # 5 minutes
    "check_interval": 0.1,  # 🔥 FIX: 0.1 secondes pour scalping ultra-rapide (optimisé)
    "scan_interval": 30,  # 🔥 OPT #14: 30 secondes pour capture plus rapide des setups
    "scalability_interval": 90,  # 90 secondes pour scalability scan
    # 🔥 Liste des paires à exclure manuellement (par exemple contraintes de taille minimale)
    # ZEC retiré - bug contractSize corrigé le 29/11/2025
    "excluded_symbols": [],

    # BUG #14 FIX: Suppression doublon volume_multiplier (défini ligne 77 avec valeur ajustée 0.95)
    "volume_multiplier_range": (0.10, 2.00),

    # ============================================================
    # 🔥 HYBRID INTELLIGENT TP/SL SYSTEM (Option C)
    # ============================================================
    # Système adaptatif basé sur ATR - s'adapte à la volatilité réelle
    # 
    # Principes:
    # 1. SL Initial: ATR × 1.2 (dynamique, respire avec le marché)
    # 2. Break-even: dès que PnL >= 1.2 × ATR (laisse respirer)
    # 3. Trailing: distance = ATR × 0.8, trigger = 1.5 × ATR
    # 4. Time decay: si stagnation > 2min et PnL < 0.1%, sortie
    # 5. Pas de TP fixe (laisser trailing capturer)
    # ============================================================
    
    "tp_sl_mode": "ATR",  # 🔥 HYBRID: Mode ATR dynamique (pas FIXE)
    
    # Fallback FIXE mode (si ATR invalide)
    "tp_percent": 0.80,  # TP large (rarement atteint, trailing prend le relais)
    "sl_percent": 0.30,  # SL fallback (mode FIXE)
    "sl_exchange_percent": 0.30,  # 🔥 SL MEXC fixe (filet de sécurité) - dynamique par régime
    "break_even_trigger": 0.20,  # BE fallback
    "trailing_distance": 0.15,  # Trailing fallback
    
    # 🔥 ATR mode - HYBRID INTELLIGENT
    "atr_mult_tp": 2.2,   # 🔥 TP = 2.2 × ATR (plus atteignable, était 3.0)
    "atr_mult_sl": 1.2,   # 🔥 SL = 1.2 × ATR (laisse respirer le trade)
    "atr_min": 0.10,      # ATR minimum 0.10% (micro-volatilité)
    "atr_max": 1.0,       # ATR maximum 1.0% (macro-volatilité)
    
    # 🔥 Break-even ATR-based (moins agressif pour laisser respirer)
    "break_even_atr_mult": 1.2,  # 🔥 BE dès PnL >= 1.2 × ATR% (était 0.5, trop serré)
    "break_even_use_atr": True,  # Utiliser ATR pour BE (pas % fixe)
    
    # 🔥 Stagnation Exit (Time Decay)
    "stagnation_exit": {
        "enabled": True,
        "timeout_seconds": 120,    # 2 minutes de stagnation
        "min_pnl_to_stay": 0.10,   # Rester si PnL > 0.1%
        "max_loss_to_exit": -0.05, # Sortir si PnL < -0.05% après timeout
    },
    # 🔥 FLAT KEYS pour config_overrides.json (copie des valeurs imbriquées)
    "stagnation_exit_enabled": True,
    "stagnation_exit_timeout_seconds": 120,
    "stagnation_exit_min_pnl_to_stay": 0.10,
    "stagnation_exit_max_loss_to_exit": -0.05,
    
    # 🔥 STAGNATION POSITIVE EXIT (sortie anticipée en profit)
    "stagnation_positive_exit_enabled": True,       # Activer sortie positive anticipée
    "stagnation_positive_threshold": 0.03,          # Seuil profit minimum (0.03%)
    "stagnation_positive_timeout_seconds": 60,      # Timeout réduit si en profit (< 120s normal)
    "stagnation_use_mfe_tracking": True,            # Suivre le MFE pour protection
    "stagnation_mfe_pullback_pct": 0.08,            # Sortir si pullback > 0.08% depuis MFE
    
    # Trend timeframe pour calculer trend_data (bonus)
    "trend_timeframe": "15m",  # 5m, 15m, 30m, 1h
    
    # Position entry conditions
    "min_conditions": 6,
    "dynamic_tolerance_adx_high": 30,  # ADX > 30 → 5 conditions
    "dynamic_tolerance_adx_low": 25,  # ADX < 25 → 6 conditions
    
    # 🔥 PHASE 3: Pondération des conditions (système de score)
    "use_weighted_scoring": True,  # Activer le système de score pondéré
    "min_score_required": 6.5,  # 🔥 PHASE 1 : Score minimum (était 7.5, baissé pour plus d'opportunités)
    "min_score_adx_high": 6.0,  # 🔥 PHASE 1 : Score si ADX > 30 (était 7.0)
    "min_score_adx_low": 7.0,  # 🔥 PHASE 1 : Score si ADX < 25 (était 8.0)
    
    # ✅ Patterns Techniques (activés par défaut)
    "use_breakout": True,  # Cassure de niveaux clés
    "use_snr": True,  # Rebond support/résistance
    "use_wick": True,  # Rejet via mèches
    "use_divergence": True,  # Divergence DI+/DI-

    # ✅ Patterns de Bougies (activés par défaut)
    "use_engulfing": True,
    "use_hammer": True,
    "use_shooting_star": True,
    "use_doji": True,
    "use_marubozu": True,
    "use_morning_star": True,
    "use_evening_star": True,

    # Phase 1+2: New filters (configurable) - 🔥 Valeurs mises à jour
    "snr_threshold": 0.15,  # 🔥 PHASE 1 : SNR minimum (était 0.25, baissé pour rebonds EMA)
    "breakout_threshold": 0.25,  # 🔥 PHASE 1 : Breakout multiplier (était 0.35, baissé)
    "wick_ratio_max": 4.5,  # 🔥 PHASE 1 : Max wick ratio (était 2.8, wicks normaux en scalping)
    "di_gap_min": 4.0,  # Minimum DI+ - DI- gap (était 5)
    "di_gap_adx_threshold": 25,  # ADX threshold for DI gap
    
    # Optimal ATR filter (configurables via /api/config) - 🔥 Valeurs mises à jour
    "optimal_atr_min_1m": 0.12,  # 🔥 Ajusté (était 0.10)
    "optimal_atr_max_1m": 0.75,  # 🔥 Ajusté (était 0.8)
    "optimal_atr_min_5m": 0.22,  # 🔥 Ajusté (était 0.20)
    "optimal_atr_max_5m": 1.4,  # 🔥 Ajusté (était 1.5)
    "volume_multiplier": 0.95,  # 🔥 Ajusté (était 1.0)
    
    # Scalability scanner
    "top_pairs_limit": 20,
    "balance_score_min": 0.7,
    
    # 🔥 OPT SCALABILITY: Paramètres configurables (anciennement hardcodés)
    "scalability_spread_min": 0.001,  # Spread minimum % (évite slippage nul)
    "scalability_spread_max": 0.02,   # Spread maximum % (évite coûts excessifs)
    "scalability_volume_min": 100000,  # Volume minimum USDT (5 dernières bougies)
    "scalability_volume_24h_min": 500000,  # Volume 24h minimum pour pré-filtrage
    "scalability_funding_rate_max": 0.05,  # Funding rate max % (évite coûts cachés)
    "scalability_adx_bonus_threshold": 25,  # ADX > seuil = bonus trend
    "scalability_adx_bonus_multiplier": 1.2,  # Multiplicateur bonus si trend fort
    "scalability_klines_limit": 30,  # Nombre de klines à récupérer (était 60)
    "scalability_orderbook_cache_ttl": 30,  # TTL cache orderbook en secondes
    "scalability_interval_min": 60,  # Intervalle minimum en secondes
    "scalability_interval_max": 180,  # Intervalle maximum en secondes
    "scalability_log_rejected": True,  # Logger les paires rejetées avec raison
    
    # Confluence
    "use_confluence": False,  # False = 1m OU 5m, True = 1m ET 5m
    
    # 🔥 Filtre RSI Final (bloque trades contre-logiques)
    "rsi_final_filter_enabled": True,  # Activer le filtre RSI final
    "rsi_final_long_max": 65,  # LONG bloqué si RSI > ce seuil (suracheté)
    "rsi_final_short_min": 35,  # SHORT bloqué si RSI < ce seuil (survendu)
    
    # 🔥 OPT #15: Anti-Whipsaw Filter
    "use_anti_whipsaw": True,  # Détecter et rejeter les marchés en zigzag
    "whipsaw_lookback": 5,  # Nombre de bougies à analyser
    "whipsaw_threshold_pct": 0.2,  # Amplitude min pour compter comme mouvement significatif
    "whipsaw_max_alternations": 3,  # Nombre max d'alternances avant rejet
    
    # 🔥 OPT #16: Confirmation Retest Breakout
    "use_retest_confirmation": False,  # Attendre retest du niveau cassé avant entrée
    "retest_tolerance_pct": 0.1,  # Tolérance pour considérer un retest valide
    "retest_timeout_seconds": 300,  # Timeout avant abandon du pending breakout (5 min)
    
    # 🔥 OPT #17: Cooldown Post-Trade
    "use_cooldown": True,  # Activer cooldown entre trades
    "cooldown_seconds": 30,  # Délai minimum entre fermeture et nouvelle ouverture
    "cooldown_same_symbol": 60,  # Délai supplémentaire pour même symbole
    
    # 🔥 OPT #18: Candle Close Confirmation  
    "use_candle_close": False,  # Attendre fermeture bougie avant entrée
    "candle_close_threshold_seconds": 5,  # Seuil pour considérer proche de la fermeture
    
    # 🔥 OPT #19: Momentum Continuity Filter
    "use_momentum_continuity": True,  # Vérifier que le momentum est croissant
    "momentum_lookback": 3,  # Nombre de bougies pour vérifier continuité
    
    # Position sizing (pour ouverture automatique)
    "account_size": 1000.0,  # Capital total en USDT
    "risk_per_trade": 2.0,  # % de capital risqué par trade (2% par défaut)
    "min_risk_per_trade": 2.0,  # 🔥 Borne min = risk_per_trade pour sizing strict
    "max_risk_per_trade": 2.0,  # 🔥 Borne max = risk_per_trade pour sizing strict
    
    # 🔥 FUTURES: Levier par défaut (1-125x pour MEXC)
    "default_leverage": 10,  # Levier 10x par défaut (recommandé pour débuter)
    
    # 🔥 BYPASS MODE: Token browser pour bypasser blocage API MEXC Futures
    # Récupérer depuis DevTools > Network > Headers > authorization (commence par "WEB_")
    # ⚠️ Le token expire après quelques heures, nécessite refresh manuel
    "mexc_browser_token": os.getenv("MEXC_BROWSER_TOKEN", ""),
    "use_bypass_mode": True,  # Utiliser le mode bypass (recommandé si API bloquée)
    # 🔄 Synchronisation des entrées live (éviter décalages prix/size)
    "live_entry_sync_delay_sec": 2,  # attendre 2s avant lecture de la position réelle (ouverture)
    "live_resync_delay_sec": 2,  # 🔥 FIX: attendre 2s avant resynchronisation (TP partiel, etc.)
    "live_entry_sync_use_ccxt": True,  # utiliser l'API clés (CCXT) pour lecture plutôt que bypass quand dispo
    
    # 🔥 FIX: Validation slippage avant ouverture position
    "max_slippage_pct": 0.03,  # 0.03% maximum de slippage accepté (scalping: 5% du TP, 12% du SL)
    
    # 🔥 Live Trading: Latence max API (alerter si dépassée)
    "max_latency_ms": 1000,  # 1000ms par défaut
    
    # 🔥 PHASE 1: Invalidation précoce (30 premières secondes)
    "early_invalidation": {
        "enabled": False,  # 🔥 DÉSACTIVÉ - trop agressif (0% winrate sur 9 trades)
        "delay": 15,  # 🔥 PHASE 2 : 15s au lieu de 10s (laisser plus de temps)
        "threshold_15s": -0.15,  # 🔥 PHASE 2 : -0.15% (était -0.12%, moins agressif)
        "threshold_30s": -0.12,  # 🔥 PHASE 2 : -0.12% (était -0.08%, moins agressif)
    },
    
    # 🔥 HYBRID: Trailing stop adaptatif ATR (moins agressif)
    "trailing_stop": {
        "enabled": True,
        "trigger_pnl": 0.20,        # 🔥 Déclencher à +0.20% (fallback si ATR désactivé)
        "trigger_atr_mult": 1.5,    # 🔥 Trigger dès PnL >= 1.5 × ATR (était 1.0, trop tôt)
        "use_atr_trigger": True,    # 🔥 Utiliser ATR pour trigger (pas % fixe)
        "atr_multiplier": 0.8,      # 🔥 Distance = ATR × 0.8 (était 0.4, trop serré)
        "min_distance": 0.08,       # 🔥 Minimum 0.08%
        "max_distance": 0.25,       # Maximum 0.25%
    },
    # 🔥 FLAT KEYS pour config_overrides.json (copie des valeurs trailing_stop)
    "trailing_use_atr_trigger": True,
    "trailing_trigger_atr_mult": 1.5,  # 🔥 (était 1.0, trop tôt)
    
    # 🔥 PHASE 8: Seuils adaptatifs ATR pour invalidation
    "adaptive_thresholds": {
        "enabled": True,
        "early_invalidation": {
            "low_vol_multiplier": 0.7,   # ATR < 0.3%
            "high_vol_multiplier": 1.3,  # ATR > 0.8%
        },
        "stagnation": {
            "low_vol_threshold": 0.015,  # ATR < 0.3%
            "high_vol_threshold": 0.04,  # ATR > 0.8%
        }
    },
    
    # 🔥 PHASE 8: Corrélation dynamique (basée sur prix réels)
    "dynamic_correlation": {
        "enabled": False,  # Désactivé par défaut (besoin historique)
        "period": 50,      # 50 bougies pour calcul
        "threshold": 0.7,  # Corrélation > 0.7 = pénalité
        "max_penalty": -3.0  # Pénalité max
    },
    
    # 🔥 PHASE 2: Position sizing adaptatif
    "position_sizing": {
        "base_risk": 0.02,  # 2% du capital
        "min_risk": 0.005,  # 0.5% minimum
        "max_risk": 0.03,   # 3% maximum (conservateur)
        "quality_multipliers": {
            "excellent": 1.4,   # Score ≥ 12
            "good": 1.2,        # Score ≥ 10
            "acceptable": 1.0,  # Score ≥ 8
            "weak": 0.8         # Score < 8
        },
        "streak_multipliers": {
            "win_streak_3+": 1.1,   # Win streak ≥ 3
            "loss_streak_2+": 0.85  # Loss streak ≥ 2
        }
    },
    
    # 🔥 PHASE 6: Correlation Filter
    "correlation_filter": {
        "enabled": True,
        "mode": "SOFT",  # SOFT ou HARD
        "max_positions_per_group": 2,  # Maximum 2 positions par groupe (SOFT mode)
        "penalty_score": -1.5,  # Pénalité si corrélé (SOFT mode)
        "groups": {
            "BTC_GROUP": ["BTC", "ETH", "BNB", "SOL"],
            "MEME_GROUP": ["DOGE", "SHIB", "PEPE", "FLOKI", "BONK"],
            "LAYER1_GROUP": ["ADA", "DOT", "AVAX", "NEAR", "ATOM", "ALGO"],
            "DEFI_GROUP": ["UNI", "AAVE", "SUSHI", "LINK", "MKR", "CRV"],
            "L2_GROUP": ["MATIC", "ARB", "OP", "STRK", "IMX"],
            "EXCHANGE_GROUP": ["BNB", "FTT", "HT", "OKB"],
            "STABLECOIN_GROUP": ["USDC", "USDT", "DAI", "BUSD"],
        }
    },
    
    # 🔥 PHASE 6: Recovery Mode
    "recovery_mode": {
        "enabled": True,
        "mode": "PROGRESSIVE",  # "SIMPLE" ou "PROGRESSIVE"
        # Mode SIMPLE (fallback si mode PROGRESSIVE désactivé)
        "trigger_loss_streak": 3,     # Activer après 3 losses
        "min_score_boost": 1.5,       # Score requis +1.5 points (réduit de 2.5)
        "position_size_reduction": 0.7,  # Taille -30% (au lieu de -50%)
        "confluence_forced": False,    # Ne pas forcer confluence (garder opportunités)
        "duration_trades": 5,         # Dure 5 trades
        # Mode PROGRESSIVE : Niveaux selon loss streak
        "levels": [
            {
                "trigger_loss_streak": 2,
                "min_score_boost": 0.5,
                "position_size_reduction": 0.85,  # -15%
                "confluence_forced": False,
                "duration_trades": 3
            },
            {
                "trigger_loss_streak": 3,
                "min_score_boost": 1.5,
                "position_size_reduction": 0.7,  # -30%
                "confluence_forced": False,
                "duration_trades": 5
            },
            {
                "trigger_loss_streak": 5,
                "min_score_boost": 2.5,
                "position_size_reduction": 0.5,  # -50%
                "confluence_forced": True,
                "duration_trades": 7
            }
        ]
    },
    
    # 🔥 PHASE 8: Sizing Adaptatif par Paire/Session (basé sur WR temps réel)
    "adaptive_sizing_enabled": True,
    "adaptive_sizing_min_trades": 3,        # Minimum trades avant ajustement
    "adaptive_sizing_excellent_wr": 0.75,   # WR >= 75% = excellent
    "adaptive_sizing_good_wr": 0.60,        # WR >= 60% = bon
    "adaptive_sizing_poor_wr": 0.40,        # WR <= 40% = mauvais
    "adaptive_sizing_very_poor_wr": 0.30,   # WR <= 30% = très mauvais
    "adaptive_sizing_excellent_mult": 1.50, # +50% si excellent
    "adaptive_sizing_good_mult": 1.25,      # +25% si bon
    "adaptive_sizing_poor_mult": 0.70,      # -30% si mauvais
    "adaptive_sizing_very_poor_mult": 0.50, # -50% si très mauvais
    "adaptive_sizing_max_mult": 1.50,       # Limite max
    "adaptive_sizing_min_mult": 0.50,       # Limite min
    "adaptive_sizing_reset_hours": 8,       # Reset après 8h d'inactivité
    "adaptive_sizing_reset_big_loss": True, # Reset si grosse perte
    "adaptive_sizing_big_loss_threshold": -2.0, # Seuil grosse perte %

    # ✅ TP Escalier / Multi-Level TP (paramètres individuels pour frontend)
    "partial_tp_percent": 50,  # % de position vendue au 1er TP (mode FIXE)
    "escalier_level1_pnl": 0.20,
    "escalier_level1_size": 25,
    "escalier_level2_pnl": 0.35,
    "escalier_level2_size": 25,
    "escalier_level3_pnl": 0.50,
    "escalier_level3_size": 25,
    "escalier_level4_pnl": 0.80,
    "escalier_level4_size": 25,

    # ✅ Trailing Stop Adaptatif (paramètres individuels - moins agressif)
    "trailing_enabled": True,
    "trailing_trigger_pnl": 0.20,  # 🔥 Fallback 0.20% (si ATR désactivé)
    "trailing_atr_multiplier": 0.8,  # 🔥 Distance = ATR × 0.8 (était 0.4, trop serré)
    "trailing_distance_atr_mult": 0.8,  # 🔥 ALIAS clair pour trailing_atr_multiplier
    "trailing_min_distance": 0.10,  # 🔥 Minimum 0.10% (était 0.08)
    "trailing_max_distance": 0.30,  # 🔥 Maximum 0.30% (était 0.25)

    # 🔥 PHASE 7: TP Escalier (Multi-Level TP) - Format legacy
    "tp_escalier": {
        "enabled": True,  # Activé automatiquement si tp_sl_mode = "TP_MULTI"
        "levels": [
            {"pnl": 0.20, "size_pct": 0.25, "move_sl": "entry"},      # 25% à +0.20%
            {"pnl": 0.35, "size_pct": 0.25, "move_sl": "breakeven"},  # 25% à +0.35%
            {"pnl": 0.50, "size_pct": 0.25, "move_sl": "trailing"},  # 25% à +0.50%
            {"pnl": 0.80, "size_pct": 0.25, "move_sl": "trailing"},  # 25% à +0.80%
        ]
    },

    # 🤖 Machine Learning Configuration
    "ml_filter_enabled": False,  # 🔥 PHASE 4 : Désactivé (accuracy 51% = aléatoire)
    "ml_min_confidence": 0.60,  # 60% (si réactivé plus tard)

    # 🤖 Hyperparamètres XGBoost (ajustables via UI)
    "ml_max_depth": 6,
    "ml_min_child_weight": 3,
    "ml_reg_alpha": 0.5,
    "ml_reg_lambda": 2.0,
    "ml_subsample": 0.8,
    "ml_colsample_bytree": 0.8,
    "ml_colsample_bylevel": 0.8,
    "ml_gamma": 0.0,
    "ml_scale_pos_weight": 1.0,
    "ml_n_estimators": 300,
    "ml_learning_rate": 0.03,

    # 🤖 XGBoost V2 (Régression PNL%) - Paramètres frontend/backend
    "ml_v2_filter_enabled": False,
    "ml_v2_min_confidence": 0.60,
    "ml_v2_timeframe_days": 270,
    "ml_v2_max_features": 40,
    "ml_v2_marginal_threshold": 0.20,
    "ml_v2_filter_marginal_trades": True,
    "ml_v2_test_size": 0.20,
    "ml_v2_validation_size": 0.10,
    "ml_v2_n_estimators": 600,
    "ml_v2_max_depth": 4,
    "ml_v2_learning_rate": 0.03,
    "ml_v2_min_child_weight": 5,
    "ml_v2_reg_alpha": 1.0,
    "ml_v2_reg_lambda": 3.0,
    "ml_v2_subsample": 0.70,
    "ml_v2_colsample_bytree": 0.70,
    "ml_v2_gamma": 0.50,
    
    # HistGradientBoosting (Modèle Optimisé 64-69% accuracy)
    # Note: Utilise HistGradientBoostingClassifier (10x plus rapide)
    "gb_filter_enabled": True,  # Activé par défaut car performant
    "gb_min_confidence": 0.55,  # 55% seuil de confiance
    "gb_max_iter": 100,         # Nombre d'itérations (équivalent n_estimators)
    "gb_max_depth": 3,          # Profondeur max (2-4 recommandé)
    "gb_learning_rate": 0.08,   # Taux d'apprentissage
    "gb_min_samples_leaf": 30,  # Samples minimum par feuille
    "gb_l2_regularization": 0.5,  # Régularisation L2 (évite overfitting)
    "gb_n_features": 30,        # Nombre de features sélectionnées
    "gb_model_type": "histgb",  # Toujours HistGradientBoosting maintenant
    
    # ============================================================
    # 🔥 ML AUTO-CALIBRATION SYSTEM
    # ============================================================
    # Recalibre automatiquement la confiance ML basée sur les résultats live réels
    # La confiance affichée devient le winrate réel observé par bucket
    # ============================================================
    
    "ml_calibration_enabled": True,          # Activer l'auto-calibration
    "ml_calib_live_weight": 1.0,             # Poids des trades LIVE (slider: 0.5-1.0)
    "ml_calib_dryrun_weight": 0.5,           # Poids des trades DRY-RUN (slider: 0.0-1.0)
    "ml_calib_decay_days": 14,               # Demi-vie en jours (slider: 7-60)
    "ml_calib_min_trades": 30,               # Minimum de trades pondérés pour activer (slider: 10-100)
    "ml_calib_min_winrate": 40.0,            # Seuil WR minimum pour accepter un trade (slider: 30-60%)
    "ml_calib_bucket_size": 5,               # Taille des buckets de confiance (ex: 30-35, 35-40)
    
    # ============================================================
    # 🔥 PHASE 2D: AUTO-ADAPTATION ML
    # ============================================================
    # Système d'adaptation automatique des seuils et paramètres ML
    # basé sur les performances par contexte (régime, session, heure)
    # ============================================================
    
    # Threshold Optimizer (Thompson Sampling)
    "threshold_optimizer_enabled": False,    # Activer l'optimisation dynamique des seuils
    "threshold_min": 0.45,                   # Seuil minimum (mode agressif)
    "threshold_max": 0.70,                   # Seuil maximum (mode conservateur)
    "threshold_exploration_bonus": 0.05,     # Bonus d'exploration pour nouveaux contextes
    
    # Drift Detection (ADWIN)
    "drift_detection_enabled": True,         # Activer la détection de drift
    "drift_pnl_delta": 0.002,                # Sensibilité PnL (plus petit = plus sensible)
    "drift_winrate_delta": 0.005,            # Sensibilité WinRate
    "drift_min_window": 20,                  # Minimum trades avant détection
    "drift_alert_cooldown": 50,              # Trades entre alertes
    
    # ============================================================
    # 🔥 SPRINT 1: MARKET REGIME SELECTOR
    # ============================================================
    # Détecte automatiquement le régime de marché et adapte les paramètres
    # Régimes: CALME (ATR<0.20%), NORMAL (0.20-0.40%), VOLATILE (>0.40%), CHOPPY (ADX<20)
    # ============================================================
    
    "market_regime_enabled": True,           # Activer la détection automatique du régime
    "market_regime_check_interval": 60,      # Intervalle de vérification en minutes
    "market_regime_sample_count": 10,        # Nombre de paires pour calcul ATR moyen
    "market_regime_atr_calme_max": 0.20,     # Seuil ATR max pour régime CALME (%)
    "market_regime_atr_normal_max": 0.40,    # Seuil ATR max pour régime NORMAL (%)
    "market_regime_adx_choppy": 20,          # ADX sous ce seuil = CHOPPY
    
    # 🔥 PHASE 1D: Auto-Calibration Seuils ATR (11/12/2025)
    "market_regime_auto_calibration_enabled": False,  # Toggle principal calibration
    "market_regime_calibration_lookback_days": 7,     # Fenêtre historique (jours)
    "market_regime_calibration_percentile_calme": 33, # P33 = seuil CALME
    "market_regime_calibration_percentile_volatile": 66,  # P66 = seuil VOLATILE
    "market_regime_calibration_min_samples": 50,      # Minimum samples requis
    
    # 🔥 PHASE 1D: BTC Indicator (11/12/2025)
    "market_regime_btc_indicator_enabled": False,     # Toggle principal BTC
    "market_regime_btc_volatile_threshold_1h": 2.0,   # % variation 1h = volatile
    "market_regime_btc_trend_threshold_24h": 5.0,     # % variation 24h = trend fort
    "market_regime_btc_force_volatile_enabled": True, # Forcer VOLATILE si BTC volatile
    
    # ============================================================
    # 🔥 SPRINT 1: TRADING CIRCUIT BREAKER
    # ============================================================
    # Protège le capital en cas de séries de pertes ou drawdown journalier
    # PAUSE = temporaire (auto-resume), STOP = manuel requis
    # ============================================================
    
    "trading_circuit_breaker_enabled": True,      # Activer le circuit breaker trading
    "trading_cb_max_consecutive_losses": 5,       # Pertes consécutives avant PAUSE
    "trading_cb_daily_drawdown_pause_pct": -2.0,  # Drawdown jour pour PAUSE (%)
    "trading_cb_daily_drawdown_stop_pct": -5.0,   # Drawdown jour pour STOP (%)
    "trading_cb_pause_duration_minutes": 30,      # Durée pause automatique (min)
    "trading_cb_score_boost_enabled": True,       # Activer score boost après pertes
    "trading_cb_score_boost_per_loss": 0.5,       # Score boost par perte consécutive
    
    # ============================================================
    # 🔥 SPRINT 2: PAIR SCORER - Score Pair Dynamique
    # ============================================================
    # Ajuste le score minimum par paire selon performance historique
    # Bonus pour paires performantes, malus pour paires sous-performantes
    # ============================================================
    
    "pair_scorer_enabled": True,                  # Activer l'ajustement de score par paire
    "pair_scorer_min_trades": 15,                 # Trades minimum pour calculer un ajustement
    "pair_scorer_max_adjustment": 2.0,            # Ajustement max (±2.0 points)
    "pair_scorer_lookback_days": 30,              # Jours d'historique à analyser
    "pair_scorer_refresh_minutes": 60,            # Intervalle de refresh des stats (min)
}

# Risk management
RISK_CONFIG = {
    "base_risk": 0.02,  # 2% par défaut
    "quality_multiplier_perfect": 1.5,  # 7 conditions
    "quality_multiplier_good": 1.2,  # 6 conditions
    "quality_multiplier_ok": 0.8,  # 5 conditions
    "quality_multiplier_weak": 0.5,  # <5 conditions
    "vol_multiplier_high": 0.7,  # ATR > 2.0%
    "vol_multiplier_low": 1.3,  # ATR < 0.5%
    "max_risk": 0.05,  # 5%
    "min_risk": 0.005,  # 0.5%
}

# 🔥 PHASE 3: Poids des conditions pour système de score pondéré
CONDITION_WEIGHTS = {
    # Conditions critiques (forte corrélation avec winrate)
    'EMAs': 2.5,           # Tendance = critique (augmenté de 2.0)
    'ADX_DI': 2.5,         # Force = critique (augmenté de 2.0)
    'MACD': 2.0,           # Momentum = fort
    
    # Conditions importantes (bonne corrélation)
    'RSI': 1.5,            # Momentum = important
    'Volume': 1.5,         # Confirmation = important
    
    # Conditions utiles (moins fiables)
    'Bollinger': 0.8,      # Niveau = moins fiable (réduit de 1.0)
    'Pattern': 0.8,        # Structure = moins fiable (réduit de 1.0)
    'Divergence': 1.0,     # Divergence RSI/MACD = bonus
}

# 🔥 PHASE 2: Paramètres trend_bonus
TREND_BONUS_CONFIG = {
    "use_direct_score": True,  # True = ajouter directement au score, False = bonus conditionnel
    "bonus_divisor": 5,  # Diviser bonus par 5 au lieu de 10 (plus impactant)
}

# 🔥 v6.6: Retry & Circuit Breaker settings
RETRY_CONFIG = {
    "max_attempts": 5,
    "wait_multiplier": 1,
    "wait_min": 1,
    "wait_max": 10,
}

CIRCUIT_BREAKER_CONFIG = {
    "fail_max": 5,
    "reset_timeout": 60,  # 60 seconds (délai avant retry)
}

# 🔥 v6.6: WebSocket settings
WEBSOCKET_CONFIG = {
    "url": "wss://contract.mexc.com/edge",  # ✅ URL VALIDE TROUVEE pour Futures
    "ping_interval": 30,  # Heartbeat toutes les 30s
    "reconnect_delay": 5,  # Délai reconnexion en s
    "timeout": 10,  # Timeout connexion
    "watchdog_timeout": 30,  # 🔥 PHASE 2: Timeout watchdog (30s pour scalping)
}

# Debug
DEBUG_ENABLED = os.getenv("DEBUG", "False").lower() == "true"

# ==================== ARCHITECTURE V2 - NOUVEAUX PARAMÈTRES ====================

# Analytics Database (Single Source of Truth)
ANALYTICS_DB_PATH = "data/analytics.db"

# Telegram Notifications (optionnel)
# 🔥 NOUVEAU: Charger depuis .env ou variables d'environnement
# Priorité: 1) Variables d'environnement, 2) Fichier .env, 3) None
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", None)  # "123456:ABC-DEF..."
TELEGRAM_CHAT_ID_RAW = os.getenv("TELEGRAM_CHAT_ID", None)  # "123456789" ou "-123456789" pour groupes
# 🔥 FIX: Parser Chat ID en nombre si possible (pour compatibilité API Telegram)
# Les groupes/channels ont des IDs négatifs, donc on garde la conversion flexible
try:
    TELEGRAM_CHAT_ID = int(TELEGRAM_CHAT_ID_RAW) if TELEGRAM_CHAT_ID_RAW else None
except (ValueError, TypeError):
    # Si conversion échoue (username de channel), garder tel quel
    TELEGRAM_CHAT_ID = TELEGRAM_CHAT_ID_RAW
TELEGRAM_ENABLED = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

# Paper Trading Mode (optionnel)
PAPER_TRADING_MODE = os.getenv("PAPER_TRADING_MODE", "False").lower() == "true"
PAPER_TRADING_INITIAL_CAPITAL = float(os.getenv("PAPER_TRADING_INITIAL_CAPITAL", "1000.0"))

# Backtesting
BACKTEST_DATA_PATH = "historical_data"

# API REST
API_RATE_LIMIT_REQUESTS = 100
API_RATE_LIMIT_WINDOW = 60  # secondes

# Notifications
NOTIFICATION_BATCHING_ENABLED = True
NOTIFICATION_BATCH_INTERVAL = 5  # secondes
NOTIFICATION_THROTTLE_SECONDS = 2  # délai min entre messages Telegram

# Types de notifications Telegram (activer/désactiver par type)
# Format: "TELEGRAM_NOTIFY_<TYPE>" = True/False
TELEGRAM_NOTIFY_POSITION_OPENED = os.getenv("TELEGRAM_NOTIFY_POSITION_OPENED", "true").lower() == "true"
TELEGRAM_NOTIFY_POSITION_CLOSED = os.getenv("TELEGRAM_NOTIFY_POSITION_CLOSED", "true").lower() == "true"
TELEGRAM_NOTIFY_TP_ESCALIER = os.getenv("TELEGRAM_NOTIFY_TP_ESCALIER", "true").lower() == "true"
TELEGRAM_NOTIFY_EARLY_INVALIDATION = os.getenv("TELEGRAM_NOTIFY_EARLY_INVALIDATION", "true").lower() == "true"
TELEGRAM_NOTIFY_ERROR = os.getenv("TELEGRAM_NOTIFY_ERROR", "true").lower() == "true"
TELEGRAM_NOTIFY_RECONNECTION = os.getenv("TELEGRAM_NOTIFY_RECONNECTION", "true").lower() == "true"
TELEGRAM_NOTIFY_DAILY_SUMMARY = os.getenv("TELEGRAM_NOTIFY_DAILY_SUMMARY", "false").lower() == "true"
TELEGRAM_NOTIFY_RECOVERY_MODE = os.getenv("TELEGRAM_NOTIFY_RECOVERY_MODE", "true").lower() == "true"
TELEGRAM_NOTIFY_SETUP_REJECTED = os.getenv("TELEGRAM_NOTIFY_SETUP_REJECTED", "false").lower() == "true"

# ============================================================================
# PostgreSQL Configuration (pour ML Datalogger)
# ============================================================================
POSTGRES_ENABLED = os.getenv('POSTGRES_ENABLED', 'false').lower() == 'true'
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', '5432'))
POSTGRES_DB = os.getenv('POSTGRES_DB', 'trade_cursor_ml')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', '')
POSTGRES_USE_SSL = os.getenv('POSTGRES_USE_SSL', 'false').lower() == 'true'
POSTGRES_MIN_CONN = int(os.getenv('POSTGRES_MIN_CONN', '1'))
POSTGRES_MAX_CONN = int(os.getenv('POSTGRES_MAX_CONN', '5'))

# ============================================================================
# ML Configuration (Machine Learning Predictions)
# ============================================================================
ML_CONFIG = {
    # Activation du filtre ML pour le trading
    "enabled": os.getenv('ML_FILTER_ENABLED', 'false').lower() == 'true',

    # Modèle à utiliser ("optimized" = GradientBoosting 64-69% accuracy, "xgboost_v1" = ancien ~50%)
    "model_name": os.getenv('ML_MODEL_NAME', 'optimized'),

    # Seuil de confiance minimum pour accepter un trade
    "min_confidence": float(os.getenv('ML_MIN_CONFIDENCE', '0.60')),  # 60% par défaut

    # Seuil de confiance pour rejeter un trade (prédiction loss)
    "max_loss_confidence": float(os.getenv('ML_MAX_LOSS_CONFIDENCE', '0.70')),  # 70% par défaut

    # Mode de fonctionnement
    # - "STRICT": Accepter uniquement les prédictions 'win' avec confiance >= min_confidence
    # - "SOFT": Rejeter seulement les prédictions 'loss' avec confiance >= max_loss_confidence
    # - "NEGATIVE": 🔥 NOUVEAU - Rejeter si P(loss) >= loss_threshold (filtre négatif, +6.8% win rate)
    "mode": os.getenv('ML_MODE', 'NEGATIVE'),  # 🔥 NEGATIVE par défaut (meilleurs résultats)
    
    # 🔥 NOUVEAU: Seuil pour le mode NEGATIVE (rejeter si P(loss) >= ce seuil)
    "loss_threshold": float(os.getenv('ML_LOSS_THRESHOLD', '0.45')),  # 45% = +6.8% win rate

    # Logger les prédictions dans PostgreSQL
    "log_predictions": True,

    # Envoyer des alertes ML (Telegram) quand confiance >= seuil
    "send_alerts": False,
    "alert_confidence_threshold": 0.75,
}


# ═══════════════════════════════════════════════════════════════════════════
# MARKET REGIME V2 CONFIGURATION
# Phase 0: Infrastructure pour détection avancée des régimes de marché
# ═══════════════════════════════════════════════════════════════════════════

MARKET_REGIME_V2_CONFIG = {
    # ┌─────────────────────────────────────────────────────────────────────┐
    # │ MASTER TOGGLES                                                      │
    # │ Tous désactivés par défaut = comportement V1 inchangé              │
    # └─────────────────────────────────────────────────────────────────────┘
    "v2_enabled": False,
    "use_median": False,
    "use_hysteresis": False,
    "use_smoothing": False,
    "use_atr_5m": False,
    "use_seasonality": False,
    "use_ml_regime": False,
    
    # ┌─────────────────────────────────────────────────────────────────────┐
    # │ CALCUL ATR                                                          │
    # └─────────────────────────────────────────────────────────────────────┘
    "outlier_filter_enabled": True,
    "outlier_std_threshold": 2.5,
    "min_pairs_for_valid_regime": 5,
    "atr_1m_weight": 0.40,
    "atr_5m_weight": 0.60,
    
    # ┌─────────────────────────────────────────────────────────────────────┐
    # │ HYSTÉRÉSIS                                                          │
    # └─────────────────────────────────────────────────────────────────────┘
    "hysteresis_buffer_percent": 0.10,
    "threshold_calme_max": 0.20,
    "threshold_normal_max": 0.40,
    "threshold_adx_choppy": 20,
    
    # ┌─────────────────────────────────────────────────────────────────────┐
    # │ LISSAGE TEMPOREL                                                    │
    # └─────────────────────────────────────────────────────────────────────┘
    "smoothing_alpha": 0.3,
    
    # ┌─────────────────────────────────────────────────────────────────────┐
    # │ STABILITÉ                                                           │
    # └─────────────────────────────────────────────────────────────────────┘
    "min_regime_duration_minutes": 30,
    "confirmation_required_checks": 2,
    "cooldown_after_change_minutes": 15,
    
    # ┌─────────────────────────────────────────────────────────────────────┐
    # │ SESSIONS (heures UTC)                                               │
    # └─────────────────────────────────────────────────────────────────────┘
    "sessions": {
        "ASIA":        {"start_hour_utc": 0,  "end_hour_utc": 7,  "atr_threshold_multiplier": 0.80, "min_score_adjustment": 0.5},
        "EUROPE_OPEN": {"start_hour_utc": 7,  "end_hour_utc": 9,  "atr_threshold_multiplier": 1.20, "min_score_adjustment": 0.0},
        "EUROPE":      {"start_hour_utc": 9,  "end_hour_utc": 13, "atr_threshold_multiplier": 1.00, "min_score_adjustment": 0.0},
        "US_PREMARKET":{"start_hour_utc": 13, "end_hour_utc": 14, "atr_threshold_multiplier": 1.10, "min_score_adjustment": 0.3},
        "US_OPEN":     {"start_hour_utc": 14, "end_hour_utc": 16, "atr_threshold_multiplier": 1.50, "min_score_adjustment": -0.5},
        "US_SESSION":  {"start_hour_utc": 16, "end_hour_utc": 20, "atr_threshold_multiplier": 1.20, "min_score_adjustment": 0.0},
        "US_CLOSE":    {"start_hour_utc": 20, "end_hour_utc": 21, "atr_threshold_multiplier": 1.30, "min_score_adjustment": -0.3},
        "NIGHT":       {"start_hour_utc": 21, "end_hour_utc": 24, "atr_threshold_multiplier": 0.70, "min_score_adjustment": 1.0},
    },
    
    # ┌─────────────────────────────────────────────────────────────────────┐
    # │ LOGGING                                                             │
    # └─────────────────────────────────────────────────────────────────────┘
    "log_regime_details": True,
    "log_session_changes": True,
    "emit_websocket_on_change": True,
}


# 🔥 FIX: Appliquer les overrides persistés depuis config_overrides.json
# Permet de conserver les modifications faites via l'UI entre redémarrages
try:
    from utils.config_persistence import apply_config_overrides
    TRADING_CONFIG = apply_config_overrides(TRADING_CONFIG)
    
    # 🔥 FIX: Synchroniser ML_CONFIG avec TRADING_CONFIG après chargement des overrides
    if 'ml_filter_enabled' in TRADING_CONFIG:
        ML_CONFIG['enabled'] = TRADING_CONFIG['ml_filter_enabled']
    if 'ml_min_confidence' in TRADING_CONFIG:
        ML_CONFIG['min_confidence'] = TRADING_CONFIG['ml_min_confidence']
    if 'ml_filter_mode' in TRADING_CONFIG:
        ML_CONFIG['mode'] = TRADING_CONFIG['ml_filter_mode']
    if 'ml_loss_threshold' in TRADING_CONFIG:
        ML_CONFIG['loss_threshold'] = TRADING_CONFIG['ml_loss_threshold']
    
    import logging
    logging.info(f"✅ ML_CONFIG synchronisé: enabled={ML_CONFIG['enabled']}, mode={ML_CONFIG.get('mode', 'NEGATIVE')}, loss_threshold={ML_CONFIG.get('loss_threshold', 0.45)}")
    
except Exception as e:
    import logging
    logging.warning(f"⚠️ Impossible d'appliquer config overrides: {e}")

