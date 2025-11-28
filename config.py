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
    "scan_interval": 45,  # 45 secondes pour position scan
    "scalability_interval": 90,  # 90 secondes pour scalability scan
    # 🔥 Liste des paires à exclure manuellement (par exemple contraintes de taille minimale)
    "excluded_symbols": [
        "ZEC/USDT:USDT",
    ],

    # BUG #14 FIX: Suppression doublon volume_multiplier (défini ligne 77 avec valeur ajustée 0.95)
    "volume_multiplier_range": (0.10, 2.00),

    # TP/SL settings
    "tp_sl_mode": "FIXE",  # FIXE ou ATR
    
    # FIXE mode
    "tp_percent": 0.50,  # 🔥 PHASE 3 : +0.50% (optimisé pour scalping, était 0.6%)
    "sl_percent": 0.20,  # 🔥 PHASE 3 : -0.20% (SL serré, était 0.25%)
    "break_even_trigger": 0.3,  # +0.3%
    "trailing_distance": 0.15,  # 0.15%
    
    # ATR mode
    "atr_mult_tp": 1.5,
    "atr_mult_sl": 1.0,
    "atr_min": 0.15,  # %
    "atr_max": 1.5,  # %
    
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
    
    # Confluence
    "use_confluence": False,  # False = 1m OU 5m, True = 1m ET 5m
    
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
        "enabled": True,
        "delay": 15,  # 🔥 PHASE 2 : 15s au lieu de 10s (laisser plus de temps)
        "threshold_15s": -0.15,  # 🔥 PHASE 2 : -0.15% (était -0.12%, moins agressif)
        "threshold_30s": -0.12,  # 🔥 PHASE 2 : -0.12% (était -0.08%, moins agressif)
    },
    
    # 🔥 PHASE 2: Trailing stop adaptatif ATR
    "trailing_stop": {
        "enabled": True,
        "trigger_pnl": 0.15,      # 🔥 PHASE 2 : Déclencher à +0.15% (était 0.25%, protection plus tôt)
        "atr_multiplier": 0.4,   # Distance = ATR × 0.4
        "min_distance": 0.08,    # Minimum 0.08%
        "max_distance": 0.25,    # Maximum 0.25%
    },
    
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

    # ✅ Trailing Stop Adaptatif (paramètres individuels)
    "trailing_enabled": True,
    "trailing_trigger_pnl": 0.15,  # 🔥 PHASE 2 : 0.15% (était 0.25%)
    "trailing_atr_multiplier": 0.4,
    "trailing_min_distance": 0.08,
    "trailing_max_distance": 0.25,

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

    # Modèle à utiliser
    "model_name": os.getenv('ML_MODEL_NAME', 'xgboost_v1'),

    # Seuil de confiance minimum pour accepter un trade
    "min_confidence": float(os.getenv('ML_MIN_CONFIDENCE', '0.60')),  # 60% par défaut

    # Seuil de confiance pour rejeter un trade (prédiction loss)
    "max_loss_confidence": float(os.getenv('ML_MAX_LOSS_CONFIDENCE', '0.70')),  # 70% par défaut

    # Mode de fonctionnement
    # - "STRICT": Accepter uniquement les prédictions 'win' avec confiance >= min_confidence
    # - "SOFT": Rejeter seulement les prédictions 'loss' avec confiance >= max_loss_confidence
    "mode": os.getenv('ML_MODE', 'STRICT'),

    # Logger les prédictions dans PostgreSQL
    "log_predictions": True,

    # Envoyer des alertes ML (Telegram) quand confiance >= seuil
    "send_alerts": False,
    "alert_confidence_threshold": 0.75,
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
    
    import logging
    logging.info(f"✅ ML_CONFIG synchronisé: enabled={ML_CONFIG['enabled']}, min_confidence={ML_CONFIG.get('min_confidence', 0.6)}")
    
except Exception as e:
    import logging
    logging.warning(f"⚠️ Impossible d'appliquer config overrides: {e}")

