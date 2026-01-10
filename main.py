#!/usr/bin/env python3
"""
Trade Cursor v7.0 - Application FastAPI (async natif)
Interface HTML identique à v5.1 avec backend Python
"""

# ⚠️ IMPORTANT : Charger .env AVANT tout autre import
from dotenv import load_dotenv
load_dotenv()

import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import asyncio
import logging
import json
import os
import csv
import io
import subprocess
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple, Callable
from fastapi import FastAPI, Request, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
# 🔥 CLEANUP: HTMLResponse, StaticFiles et Jinja2Templates supprimés - Frontend Svelte gère l'interface
# 🔥 MIGRATION COMPLÈTE: socketio supprimé - WebSocket natif uniquement
from core.websocket_manager import get_websocket_manager, WebSocketManager
import time
from utils.effective_config import get_effective_value
# 🔥 FIX: Import colorama pour les couleurs dans les logs
try:
    import colorama
    colorama.init()  # Initialiser colorama
except ImportError:
    colorama = None

# 🔥 SPRINT 2.1: StateManager for centralized state management
from core.state_manager import get_state_manager, LegacyAppStateProxy

# 🔥 v7.0: Imports complets
try:
    from api.price_provider import get_price_provider as create_price_provider
    from core.scanner import ScalabilityScanner
    from core.analyzer import TechnicalAnalyzer
    from core.position_manager import PositionManager, PositionConfig
    from core.scheduler import Scheduler
    from core.metrics import get_metrics_collector
    from core.database import TradeDatabase  # 🔥 PHASE 8: SQLite (legacy)
    from core.shutdown import GracefulShutdown  # 🔥 SPRINT 1.3: Graceful shutdown
    # 🔥 LIVE TRADING: Imports pour live trading
    from api.live_trading_endpoints import router as live_router, register_websocket_commands
    from api.regime_endpoints import router as regime_router
    from trading.live_order_manager_futures import LiveOrderManagerFutures as LiveOrderManager
    from utils.pricing import get_preferred_price
except ImportError as e:
    logging.error(f"Import error: {e}")
    # Fallback pour les dépendances manquantes
    create_price_provider = None
    TradeDatabase = None
    GracefulShutdown = None
    ScalabilityScanner = None
    TechnicalAnalyzer = None
    PositionManager = None
    PositionConfig = None
    Scheduler = None
    get_metrics_collector = None

# 🔥 ARCHITECTURE V2: Nouveaux imports
try:
    from core.analytics_database import AnalyticsDatabase
    from notifications import create_notification_manager
    from api.routes import router as api_router, set_analytics_db, set_position_manager, set_notification_manager, set_instance_port, set_app_state, set_websocket_manager as set_websocket_manager_routes
except ImportError as e:
    logging.warning(f"Architecture V2 imports (optionnels): {e}")
    AnalyticsDatabase = None
    create_notification_manager = None
    api_router = None
    set_analytics_db = None

# 🔥 REFACTORING SPRINT 1.1: Exception Handling System
try:
    from core.exceptions import (
        TradeCursorError,
        ConfigurationError,
        ValidationError,
        MarketDataError,
        PriceDataError,
        PositionError,
        OrderExecutionError,
        APIError,
        NetworkError,
        WebSocketError,
        DatabaseError,
        NotificationError,
    )
    from core.error_handling import (
        handle_errors,
        log_errors,
        suppress_errors,
        ErrorContext,
    )
except ImportError as e:
    logging.warning(f"Exception handling system (Sprint 1.1): {e}")
    # Fallback to standard exceptions
    TradeCursorError = Exception
    ConfigurationError = Exception
    handle_errors = lambda **kwargs: lambda f: f

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 🔥 FIX: Configurer le logger avec WebSocket handler après l'initialisation de ws_manager
# (sera fait dans init_instances ou après l'initialisation de ws_manager)

# 🔥 IMPORTANT: FastAPI imports (app sera créé après définition du lifespan)
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# 🔥 FIX: Exception handler global (défini comme fonction, sera attaché après création de app)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler global pour toutes les exceptions - retourne 200 avec success=False au lieu de 503 pour /api/state"""
    import time
    
    # Ne pas intercepter les HTTPException (déjà gérées)
    if isinstance(exc, (StarletteHTTPException, RequestValidationError)):
        raise exc
    
    logger.error(f"❌ Exception globale capturée dans {request.url.path}: {exc}", exc_info=True)
    
    # Si c'est une route /api/state, retourner réponse minimale avec 200
    if request.url.path == "/api/state":
        logger.info(f"🔍 Exception handler global appelé pour /api/state - Exception: {type(exc).__name__}: {exc}")
        # 🔥 FIX: Gestion sécurisée de session_id (try/except imbriqué redondant supprimé)
        try:
            session_id_value = state.session_id or f"live_{int(time.time())}"
        except Exception:
            session_id_value = f"live_{int(time.time())}"
        
        return JSONResponse({
            'success': False,
            'error': str(exc),
            'session_id': session_id_value,
            'config': {},
            'scanner': {'is_scanning': False, 'top_pairs': []},
            'position': {'active': False, 'data': None},
            'stats': {'total_trades': 0, 'wins': 0, 'losses': 0, 'winrate': 0.0},
            'trades': [],
            'timestamp': time.time()
        }, status_code=200)
    
    # Pour les autres routes, retourner l'erreur normale
    return JSONResponse({
        'error': str(exc),
        'path': request.url.path
    }, status_code=500)
# 🔥 CLEANUP: Jinja2Templates supprimé - Frontend Svelte gère l'interface

# 🔥 FIX: Middleware pour logger toutes les requêtes et réponses
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        import time
        start_time = time.time()
        path = request.url.path

        logger.info(f"📥 Requête entrante: {request.method} {path}")

        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            logger.info(f"📤 Réponse: {request.method} {path} - {response.status_code} ({process_time:.3f}s)")
            return response
        except WebSocketDisconnect:
            # WebSocket disconnect is normal, not an error
            process_time = time.time() - start_time
            logger.debug(f"🔌 WebSocket déconnecté: {path} ({process_time:.3f}s)")
            raise
        except TradeCursorError as e:
            # Application-specific errors with context
            process_time = time.time() - start_time
            logger.error(
                f"❌ Erreur application dans middleware pour {path}: {type(e).__name__}: {e} ({process_time:.3f}s)",
                exc_info=True,
                extra={'path': path, 'method': request.method, 'context': getattr(e, 'context', {})}
            )
            raise
        except Exception as e:
            # Unexpected errors (framework, system, etc.)
            process_time = time.time() - start_time
            logger.critical(
                f"❌ ERREUR INATTENDUE dans middleware pour {path}: {type(e).__name__}: {e} ({process_time:.3f}s)",
                exc_info=True,
                extra={'path': path, 'method': request.method}
            )
            raise

# Middleware sera attaché APRES la création de app (ligne ~280)

# 🔒 Security Middleware: Ajout des headers de sécurité
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)

        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdn.socket.io; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "connect-src 'self' ws: wss:; "
            "font-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )

        # Autres headers de sécurité
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response

# Middleware sera attaché APRES la création de app (ligne ~280)

# 🔥 CLEANUP: Fichiers statiques supprimés - Frontend Svelte gère l'interface
# Plus besoin de servir des fichiers statiques, le frontend Svelte est indépendant

# Les routers seront inclus APRES la création de app (ligne ~280)

# 🔥 MIGRATION COMPLÈTE: Socket.IO supprimé - WebSocket natif uniquement

# 🔥 SPRINT 2.1: Initialize StateManager singleton
state = get_state_manager()

# 🔥 WebSocket Natif - Initialize and store in StateManager
state.set_ws_manager(get_websocket_manager())

# 🔥 MIGRATION COMPLÈTE: Injecter ws_manager dans les routes
def get_websocket_manager_for_routes() -> WebSocketManager:
    """Obtenir l'instance WebSocketManager pour les routes."""
    return state.get_ws_manager()

def _organize_trading_config_for_export(trading_config: Dict[str, Any]) -> OrderedDict:
    """Organise TRADING_CONFIG in the same categories as frontend for XLSM export."""
    categories = OrderedDict()
    categories['⚙️ Général'] = OrderedDict(
        fee_per_trade=trading_config.get('fee_per_trade'),
        use_slippage_calculation=trading_config.get('use_slippage_calculation'),
        position_timeout=trading_config.get('position_timeout'),
        check_interval=trading_config.get('check_interval'),
        scan_interval=trading_config.get('scan_interval'),
        scalability_interval=trading_config.get('scalability_interval')
    )
    categories['📊 Validation & Scoring'] = OrderedDict(
        min_conditions=trading_config.get('min_conditions'),
        use_weighted_scoring=trading_config.get('use_weighted_scoring'),
        min_score_required=trading_config.get('min_score_required'),
        max_slippage_pct=trading_config.get('max_slippage_pct'),
        min_score_adx_high=trading_config.get('min_score_adx_high'),
        min_score_adx_low=trading_config.get('min_score_adx_low'),
        dynamic_tolerance_adx_high=trading_config.get('dynamic_tolerance_adx_high'),
        dynamic_tolerance_adx_low=trading_config.get('dynamic_tolerance_adx_low')
    )
    categories['🎯 Patterns Techniques'] = OrderedDict(
        use_breakout=trading_config.get('use_breakout'),
        use_snr=trading_config.get('use_snr'),
        use_wick=trading_config.get('use_wick'),
        use_divergence=trading_config.get('use_divergence')
    )
    categories['🕯️ Patterns de Bougies'] = OrderedDict(
        use_engulfing=trading_config.get('use_engulfing'),
        use_hammer=trading_config.get('use_hammer'),
        use_shooting_star=trading_config.get('use_shooting_star'),
        use_doji=trading_config.get('use_doji'),
        use_marubozu=trading_config.get('use_marubozu'),
        use_morning_star=trading_config.get('use_morning_star'),
        use_evening_star=trading_config.get('use_evening_star')
    )
    categories['📈 Seuils & Filtres'] = OrderedDict(
        snr_threshold=trading_config.get('snr_threshold'),
        breakout_threshold=trading_config.get('breakout_threshold'),
        wick_ratio_max=trading_config.get('wick_ratio_max'),
        di_gap_min=trading_config.get('di_gap_min'),
        di_gap_adx_threshold=trading_config.get('di_gap_adx_threshold'),
        optimal_atr_min_1m=trading_config.get('optimal_atr_min_1m'),
        optimal_atr_max_1m=trading_config.get('optimal_atr_max_1m'),
        optimal_atr_min_5m=trading_config.get('optimal_atr_min_5m'),
        optimal_atr_max_5m=trading_config.get('optimal_atr_max_5m')
    )
    categories['💰 Money Management'] = OrderedDict(
        account_size=trading_config.get('account_size'),
        risk_per_trade=trading_config.get('risk_per_trade'),
        volume_multiplier=trading_config.get('volume_multiplier'),
        use_confluence=trading_config.get('use_confluence')
    )
    categories['🎯 TP/SL Configuration'] = OrderedDict(
        tp_sl_mode=trading_config.get('tp_sl_mode'),
        tp_percent=trading_config.get('tp_percent'),
        sl_percent=trading_config.get('sl_percent'),
        break_even_trigger=trading_config.get('break_even_trigger'),
        trailing_distance=trading_config.get('trailing_distance'),
        invert_signals=trading_config.get('invert_signals')
    )
    categories['📐 Mode ATR'] = OrderedDict(
        atr_mult_tp=trading_config.get('atr_mult_tp'),
        atr_mult_sl=trading_config.get('atr_mult_sl'),
        atr_min=trading_config.get('atr_min'),
        atr_max=trading_config.get('atr_max')
    )
    categories['🪜 TP Escalier'] = OrderedDict(
        partial_tp_percent=trading_config.get('partial_tp_percent'),
        escalier_level1_pnl=trading_config.get('escalier_level1_pnl'),
        escalier_level1_size=trading_config.get('escalier_level1_size'),
        escalier_level2_pnl=trading_config.get('escalier_level2_pnl'),
        escalier_level2_size=trading_config.get('escalier_level2_size'),
        escalier_level3_pnl=trading_config.get('escalier_level3_pnl'),
        escalier_level3_size=trading_config.get('escalier_level3_size'),
        escalier_level4_pnl=trading_config.get('escalier_level4_pnl'),
        escalier_level4_size=trading_config.get('escalier_level4_size')
    )
    categories['📉 Trailing Stop'] = OrderedDict(
        trailing_enabled=trading_config.get('trailing_enabled'),
        trailing_trigger_pnl=trading_config.get('trailing_trigger_pnl'),
        trailing_atr_multiplier=trading_config.get('trailing_atr_multiplier'),
        trailing_min_distance=trading_config.get('trailing_min_distance'),
        trailing_max_distance=trading_config.get('trailing_max_distance')
    )
    categories['⏱️ Timeframe & Trend'] = OrderedDict(
        trend_timeframe=trading_config.get('trend_timeframe'),
        top_pairs_limit=trading_config.get('top_pairs_limit'),
        balance_score_min=trading_config.get('balance_score_min')
    )
    categories['🤖 Machine Learning V1'] = OrderedDict(
        ml_filter_enabled=trading_config.get('ml_filter_enabled'),
        ml_min_confidence=trading_config.get('ml_min_confidence'),
        ml_max_depth=trading_config.get('ml_max_depth'),
        ml_min_child_weight=trading_config.get('ml_min_child_weight'),
        ml_reg_alpha=trading_config.get('ml_reg_alpha'),
        ml_reg_lambda=trading_config.get('ml_reg_lambda'),
        ml_subsample=trading_config.get('ml_subsample'),
        ml_colsample_bytree=trading_config.get('ml_colsample_bytree'),
        ml_colsample_bylevel=trading_config.get('ml_colsample_bylevel'),
        ml_gamma=trading_config.get('ml_gamma'),
        ml_scale_pos_weight=trading_config.get('ml_scale_pos_weight'),
        ml_n_estimators=trading_config.get('ml_n_estimators'),
        ml_learning_rate=trading_config.get('ml_learning_rate')
    )
    categories['🚀 Machine Learning V2 (Régression)'] = OrderedDict(
        ml_v2_filter_enabled=trading_config.get('ml_v2_filter_enabled'),
        ml_v2_min_confidence=trading_config.get('ml_v2_min_confidence'),
        ml_v2_timeframe_days=trading_config.get('ml_v2_timeframe_days'),
        ml_v2_max_features=trading_config.get('ml_v2_max_features'),
        ml_v2_marginal_threshold=trading_config.get('ml_v2_marginal_threshold'),
        ml_v2_filter_marginal_trades=trading_config.get('ml_v2_filter_marginal_trades'),
        ml_v2_test_size=trading_config.get('ml_v2_test_size'),
        ml_v2_validation_size=trading_config.get('ml_v2_validation_size'),
        ml_v2_n_estimators=trading_config.get('ml_v2_n_estimators'),
        ml_v2_max_depth=trading_config.get('ml_v2_max_depth'),
        ml_v2_learning_rate=trading_config.get('ml_v2_learning_rate'),
        ml_v2_min_child_weight=trading_config.get('ml_v2_min_child_weight'),
        ml_v2_reg_alpha=trading_config.get('ml_v2_reg_alpha'),
        ml_v2_reg_lambda=trading_config.get('ml_v2_reg_lambda'),
        ml_v2_subsample=trading_config.get('ml_v2_subsample'),
        ml_v2_colsample_bytree=trading_config.get('ml_v2_colsample_bytree'),
        ml_v2_gamma=trading_config.get('ml_v2_gamma')
    )
    categories['🎯 HistGradientBoosting (Optimisé 68%)'] = OrderedDict(
        gb_filter_enabled=trading_config.get('gb_filter_enabled'),
        gb_min_confidence=trading_config.get('gb_min_confidence'),
        gb_max_iter=trading_config.get('gb_max_iter'),
        gb_max_depth=trading_config.get('gb_max_depth'),
        gb_learning_rate=trading_config.get('gb_learning_rate'),
        gb_min_samples_leaf=trading_config.get('gb_min_samples_leaf'),
        gb_l2_regularization=trading_config.get('gb_l2_regularization'),
        gb_model_type=trading_config.get('gb_model_type')
    )
    categories['💎 Live Trading'] = OrderedDict(
        default_leverage=trading_config.get('default_leverage'),
        max_latency_ms=trading_config.get('max_latency_ms')
    )
    categories['💱 Spread Thresholds'] = OrderedDict(
        max_spread_pct=trading_config.get('max_spread_pct'),
        max_spread_pct_fixe=trading_config.get('max_spread_pct_fixe'),
        max_spread_pct_atr=trading_config.get('max_spread_pct_atr')
    )
    categories['🛡️ Filtres Avancés (OPT #15-19)'] = OrderedDict(
        use_anti_whipsaw=trading_config.get('use_anti_whipsaw'),
        whipsaw_lookback=trading_config.get('whipsaw_lookback'),
        whipsaw_threshold_pct=trading_config.get('whipsaw_threshold_pct'),
        whipsaw_max_alternations=trading_config.get('whipsaw_max_alternations'),
        use_retest_confirmation=trading_config.get('use_retest_confirmation'),
        retest_tolerance_pct=trading_config.get('retest_tolerance_pct'),
        retest_timeout_seconds=trading_config.get('retest_timeout_seconds'),
        use_cooldown=trading_config.get('use_cooldown'),
        cooldown_seconds=trading_config.get('cooldown_seconds'),
        cooldown_same_symbol=trading_config.get('cooldown_same_symbol'),
        use_candle_close=trading_config.get('use_candle_close'),
        candle_close_threshold_seconds=trading_config.get('candle_close_threshold_seconds'),
        use_momentum_continuity=trading_config.get('use_momentum_continuity'),
        momentum_lookback=trading_config.get('momentum_lookback'),
        use_micro_confirmation=trading_config.get('use_micro_confirmation'),
        micro_confirmation_delay_ms=trading_config.get('micro_confirmation_delay_ms')
    )
    categories['⚙️ Configurations Avancées'] = OrderedDict(
        early_invalidation=trading_config.get('early_invalidation'),
        trailing_stop=trading_config.get('trailing_stop'),
        adaptive_thresholds=trading_config.get('adaptive_thresholds'),
        dynamic_correlation=trading_config.get('dynamic_correlation'),
        position_sizing=trading_config.get('position_sizing'),
        correlation_filter=trading_config.get('correlation_filter'),
        recovery_mode=trading_config.get('recovery_mode'),
        tp_escalier=trading_config.get('tp_escalier')
    )
    return categories

def _flatten_trading_config_for_excel(categories: OrderedDict) -> List[Dict[str, Any]]:
    rows = []
    for category, vars_dict in categories.items():
        for key, value in vars_dict.items():
            if value is None:
                value_str = ''
            elif isinstance(value, bool):
                value_str = '✅' if value else '❌'
            elif isinstance(value, (dict, list)):
                value_str = json.dumps(value, ensure_ascii=False)
            else:
                value_str = value
            rows.append({
                'category': category,
                'variable': key,
                'value': value_str
            })
    return rows

# 🔥 LIVE TRADING: Enregistrer les commandes WebSocket pour live trading
try:
    ws_mgr = state.get_ws_manager()
    register_websocket_commands(ws_mgr)
    logger.info("✅ Commandes WebSocket live trading enregistrées")
except (ImportError, AttributeError, TypeError) as e:
    # Dépendances manquantes ou configuration incorrecte (non-critique)
    logger.warning(f"⚠️ Impossible d'enregistrer commandes WebSocket live trading: {e}")
except ConfigurationError as e:
    # Configuration WebSocket invalide
    logger.error(f"❌ Configuration WebSocket invalide: {e}", exc_info=True)
    raise
except WebSocketError as e:
    # Erreur WebSocket (connection, manager init, etc.)
    logger.error(f"❌ Erreur WebSocket lors de l'enregistrement: {e}", exc_info=True)
    raise
except Exception as e:
    # Erreur système inattendue
    logger.critical(
        f"❌ ERREUR CRITIQUE lors de l'enregistrement WebSocket: {type(e).__name__}: {e}",
        exc_info=True
    )
    raise

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager pour initialiser et fermer proprement les ressources"""
    logger.info("🚀 LIFESPAN ENTER: Début du context manager (avant initialisation)")
    logger.info("🚀 LIFESPAN STARTUP: Initialisation...")

    # 🔥 SPRINT 1.3: Graceful shutdown manager
    shutdown_manager = GracefulShutdown(timeout=30.0) if GracefulShutdown else None
    data_logger = None
    try:
        try:
            from backend.ml.data_logger import DataLogger
            data_logger = DataLogger()
            await data_logger.initialize()
            app.state.data_logger = data_logger
            logger.info("✅ DataLogger initialisé")

            # Register cleanup
            if shutdown_manager and data_logger:
                shutdown_manager.register(
                    "DataLogger",
                    data_logger.shutdown,
                    async_cleanup=True,
                    priority=80
                )
        except ImportError as e:
            logger.warning(f"⚠️ Module DataLogger non disponible: {e}")
            app.state.data_logger = None
        except (OSError, IOError, ConnectionError) as e:
            logger.warning(f"⚠️ Erreur I/O lors de l'initialisation DataLogger: {e}")
            app.state.data_logger = None
        except Exception as e:
            logger.error(f"❌ Erreur inattendue initialisation DataLogger: {e}", exc_info=True)
            app.state.data_logger = None

        init_instances()
        logger.info("✅ LIFESPAN: init_instances() terminé")

        # 🔬 Vérification système HistGradientBoosting au démarrage
        try:
            from verification.verify_histgb_system import verify_config_overrides, verify_model_file
            config_result = verify_config_overrides(auto_fix=True)  # Auto-repair si nécessaire
            model_result = verify_model_file()
            
            if config_result.passed and model_result.passed:
                logger.info("✅ HISTGB: Système ML vérifié et fonctionnel")
            else:
                if not config_result.passed:
                    logger.warning(f"⚠️ HISTGB Config: {len(config_result.errors)} erreur(s)")
                if not model_result.passed:
                    logger.warning(f"⚠️ HISTGB Model: {len(model_result.errors)} erreur(s)")
        except ImportError as e:
            # Module verification non disponible (optionnel)
            logger.debug(f"Module verification non disponible, skip vérification ML: {e}")
        except ConfigurationError as e:
            # Configuration ML invalide
            logger.warning(f"⚠️ Configuration ML invalide: {e}")
        except Exception as e:
            # Erreur non-critique durant vérification ML
            logger.warning(f"⚠️ Vérification ML non critique échouée: {type(e).__name__}: {e}")

        # 🔥 AUTO-SEED CALIBRATION: Initialiser la calibration ML avec l'historique des trades
        try:
            from config import TRADING_CONFIG
            if TRADING_CONFIG.get('ml_calibration_enabled', True):
                from ml.calibration import get_calibration_manager
                calib_manager = get_calibration_manager()
                
                # Vérifier si la calibration a des données
                decay_days = TRADING_CONFIG.get('ml_calib_decay_days', 14)
                seeded_count = calib_manager.seed_from_historical_trades(days=decay_days)
                
                if seeded_count > 0:
                    logger.info(f"✅ CALIBRATION: Auto-seed avec {seeded_count} trades ({decay_days} jours)")
                else:
                    logger.info("ℹ️ CALIBRATION: Aucun trade historique trouvé pour le seed")
        except ImportError as e:
            # Module calibration non disponible
            logger.debug(f"Module calibration non disponible: {e}")
        except ConfigurationError as e:
            # Configuration calibration invalide
            logger.warning(f"⚠️ Configuration calibration invalide: {e}")
        except DatabaseError as e:
            # Erreur lors de la lecture des trades historiques
            logger.warning(f"⚠️ Impossible de charger trades pour calibration: {e}")
        except Exception as e:
            # Erreur non-bloquante durant calibration
            logger.warning(f"⚠️ Auto-seed calibration échoué (non-bloquant): {type(e).__name__}: {e}")

        try:
            await asyncio.wait_for(asyncio.sleep(1.0), timeout=2.0)
        except asyncio.TimeoutError:
            logger.warning("⚠️ Timeout lors de l'initialisation WebSocket")

        ws_mgr = state.get_ws_manager()
        if ws_mgr:
            await ws_mgr.emit('reset_session', {
                'timestamp': time.time(),
                'reason': 'backend_startup'
            })
            logger.info("✅ Événement reset_session émis au démarrage (AVANT le scan)")

        yield

        logger.info("🟢 LIFESPAN YIELD: Execution principale terminée, début du shutdown")

    finally:
        # 🔥 SPRINT 1.3: Graceful shutdown orchestré
        if shutdown_manager:
            # Register remaining resources that weren't registered at startup
            try:
                from core.callbacks.scanner_loop import get_pg_datalogger
                pg_datalogger = get_pg_datalogger()
                if pg_datalogger:
                    shutdown_manager.register(
                        "PostgreSQL_DataLogger",
                        pg_datalogger.close,
                        async_cleanup=False,
                        priority=70
                    )
            except ImportError:
                pass
            except Exception as e:
                logger.debug(f"PostgreSQL DataLogger non enregistré: {e}")

            try:
                from api.mexc import get_mexc_client
                mexc_client = get_mexc_client()
                if mexc_client:
                    shutdown_manager.register(
                        "MEXC_Client",
                        mexc_client.close,
                        async_cleanup=True,
                        priority=60
                    )
            except ImportError:
                pass
            except Exception as e:
                logger.debug(f"MEXC client non enregistré: {e}")

            # TradeDatabase cleanup
            global trade_db
            if trade_db:
                shutdown_manager.register(
                    "TradeDatabase",
                    trade_db.close,
                    async_cleanup=False,
                    priority=50
                )

            # Execute graceful shutdown
            await shutdown_manager.shutdown()

        else:
            # Fallback: Old shutdown logic if GracefulShutdown not available
            logger.warning("⚠️ GracefulShutdown non disponible, utilisation legacy cleanup")

            try:
                if hasattr(app.state, 'data_logger') and app.state.data_logger:
                    try:
                        await app.state.data_logger.shutdown()
                        logger.info("✅ DataLogger arrêté proprement")
                    except Exception as e:
                        logger.error(f"❌ Erreur arrêt DataLogger: {e}", exc_info=True)

                try:
                    from core.callbacks.scanner_loop import get_pg_datalogger
                    pg_datalogger = get_pg_datalogger()
                    if pg_datalogger:
                        pg_datalogger.close()
                        logger.info("✅ PostgreSQL DataLogger fermé proprement")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur fermeture PostgreSQL DataLogger: {e}")

                try:
                    from api.mexc import get_mexc_client
                    mexc_client = get_mexc_client()
                    if mexc_client:
                        await mexc_client.close()
                        logger.info("✅ MEXC client fermé proprement")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur fermeture MEXC client: {e}")

            except Exception as e:
                logger.warning(f"⚠️ Erreur shutdown legacy: {e}", exc_info=True)

        logger.info("🏁 LIFESPAN EXIT: Contexte fermé")


# 🔥 CRITICAL: Créer FastAPI avec lifespan attaché (orchestrera startup/shutdown)
app = FastAPI(title="Trade Cursor v7.0", lifespan=lifespan)
logger.info("✅ FastAPI créé avec lifespan attaché (init_instances exécuté au démarrage)")

# Attacher l'exception handler
app.add_exception_handler(Exception, global_exception_handler)
logger.info("✅ Exception handler global attaché")

# Attacher les middlewares (doivent être attachés APRES la création de app)
app.add_middleware(LoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
logger.info("✅ Middlewares attachés (Logging + Security)")

# Inclure les routers
if api_router:
    app.include_router(api_router)
    logger.info("✅ API REST routes incluses: /api/*")

# 🔥 LIVE TRADING: Inclure les routes live trading
try:
    app.include_router(live_router)
    logger.info("✅ Live trading routes incluses: /api/live/*")
except ImportError as e:
    # Module live trading non disponible (optionnel)
    logger.debug(f"Module live trading non disponible: {e}")
except ConfigurationError as e:
    # Configuration invalide pour live trading
    logger.error(f"❌ Configuration live trading invalide: {e}", exc_info=True)
    raise
except Exception as e:
    # Erreur inattendue lors de l'inclusion du router
    logger.warning(f"⚠️ Impossible d'inclure live trading routes: {type(e).__name__}: {e}", exc_info=True)

# 🔥 SPRINT 1: Inclure les routes Market Regime et Circuit Breaker Trading
try:
    app.include_router(regime_router)
    logger.info("✅ Regime & CB Trading routes incluses: /api/regime/*, /api/circuit-breaker/trading/*")
except ImportError as e:
    # Module regime trading non disponible (optionnel)
    logger.debug(f"Module regime trading non disponible: {e}")
except ConfigurationError as e:
    # Configuration invalide pour regime trading
    logger.error(f"❌ Configuration regime trading invalide: {e}", exc_info=True)
    raise
except Exception as e:
    # Erreur inattendue lors de l'inclusion du router
    logger.warning(f"⚠️ Impossible d'inclure regime routes: {type(e).__name__}: {e}", exc_info=True)

# 🔥 PHASE 4: Fichier de persistance pour trade history
# 🔥 FIX: Fichier historique par instance pour éviter conflits multi-instances
# Utiliser le port comme identifiant d'instance (défaut: 5000)
def get_trade_history_file() -> str:
    """
    Retourner le nom du fichier historique selon le port de l'instance.

    Returns:
        Nom du fichier d'historique spécifique à l'instance
    """
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    return f"trade_history_instance_{port}.json"

# 🔥 SPRINT 2.1: TRADE_HISTORY_FILE et trade_db migrés vers StateManager
# Utiliser: state.trade_history_file et state.get_trade_db()
TRADE_HISTORY_FILE: Optional[str] = None
trade_db: Optional['TradeDatabase'] = None

def init_trade_database() -> None:
    """
    Initialiser base de données SQLite.

    Crée l'instance globale TradeDatabase si elle n'existe pas.
    Gère les erreurs d'accès fichier et I/O de manière spécifique.
    """
    global trade_db
    if TradeDatabase and not trade_db:
        try:
            trade_db = TradeDatabase()
            logger.info("✅ Base de données SQLite initialisée")
        except (FileNotFoundError, PermissionError) as e:
            logger.error(f"❌ Erreur d'accès fichier DB: {e}")
            trade_db = None
        except (OSError, IOError) as e:
            logger.error(f"❌ Erreur I/O lors de l'initialisation DB: {e}")
            trade_db = None
        except DatabaseError as e:
            # Erreur database spécifique (corruption, schema, etc.)
            logger.error(f"❌ Erreur database lors de l'initialisation: {e}", exc_info=True)
            trade_db = None
        except Exception as e:
            # Erreur système inattendue
            logger.critical(f"❌ Erreur critique initialisation DB: {type(e).__name__}: {e}", exc_info=True)
            trade_db = None

def save_trade_history() -> None:
    """Sauvegarder l'historique des trades dans un fichier JSON et SQLite"""
    global TRADE_HISTORY_FILE, trade_db
    
    if TRADE_HISTORY_FILE is None:
        TRADE_HISTORY_FILE = get_trade_history_file()
    
    try:
        # 🔥 FIX: Écriture atomique avec fichier temporaire puis rename
        temp_file = TRADE_HISTORY_FILE + ".tmp"
        trade_history = state.trade_history
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(trade_history, f, indent=2, ensure_ascii=False)
        # Renommer atomiquement (Windows supporte cette opération)
        if os.path.exists(TRADE_HISTORY_FILE):
            os.replace(temp_file, TRADE_HISTORY_FILE)
        else:
            os.rename(temp_file, TRADE_HISTORY_FILE)
        logger.debug(f"✅ Historique sauvegardé: {len(trade_history)} trades (fichier: {TRADE_HISTORY_FILE})")
    except (FileNotFoundError, PermissionError) as e:
        # Erreur d'accès fichier (permissions, fichier manquant)
        logger.error(f"❌ Erreur d'accès fichier lors sauvegarde JSON: {e}")
    except (OSError, IOError) as e:
        # Erreur I/O système
        logger.error(f"❌ Erreur I/O lors sauvegarde historique JSON: {e}")
        # Nettoyer fichier temporaire en cas d'erreur
        temp_file = TRADE_HISTORY_FILE + ".tmp"
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except (OSError, PermissionError):
                logger.debug(f"⚠️ Impossible de supprimer fichier temporaire: {temp_file}")
    except Exception as e:
        # Erreur inattendue (JSON serialization, etc.)
        logger.error(f"❌ Erreur inattendue sauvegarde historique JSON: {type(e).__name__}: {e}", exc_info=True)
        # Nettoyer fichier temporaire en cas d'erreur
        temp_file = TRADE_HISTORY_FILE + ".tmp"
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except (OSError, PermissionError):
                logger.debug(f"⚠️ Impossible de supprimer fichier temporaire: {temp_file}")
    
    # 🔥 PHASE 8: Sauvegarde SQLite via AnalyticsLogger uniquement
    # Les insertions directes ici provoquaient des erreurs car trade_history ne contient
    # pas toutes les colonnes requises (114). Les trades sont déjà loggés ailleurs via
    # analytics_logger, donc on évite toute duplication.

def load_trade_history() -> None:
    """Charger l'historique des trades depuis PostgreSQL (priorité) ou JSON (fallback)"""
    global TRADE_HISTORY_FILE, trade_db
    
    if TRADE_HISTORY_FILE is None:
        TRADE_HISTORY_FILE = get_trade_history_file()
    
    # 🔥 FIX: Charger depuis PostgreSQL (source de vérité)
    try:
        from core.postgresql_datalogger import PostgreSQLDataLogger
        pg_logger = PostgreSQLDataLogger()
        if pg_logger.enabled:
            conn = pg_logger.pool.getconn()
            try:
                with conn.cursor() as cur:
                    # Charger les trades des dernières 24h pour l'UI
                    cur.execute("""
                        SELECT id, symbol, direction, entry_price, exit_price,
                               pnl_pct, pnl_usdt, net_pnl_pct, net_pnl_usdt,
                               exit_reason, duration_seconds, created_at,
                               size_usdt, session_id
                        FROM trades 
                        WHERE created_at > NOW() - INTERVAL '24 hours'
                        AND exit_reason IS NOT NULL
                        ORDER BY created_at DESC
                        LIMIT 100
                    """)
                    rows = cur.fetchall()
                    if rows:
                        trades = []
                        for r in rows:
                            trades.append({
                                'id': str(r[0]),
                                'symbol': r[1],
                                'direction': r[2],
                                'entry_price': float(r[3]) if r[3] else 0,
                                'exit_price': float(r[4]) if r[4] else 0,
                                'pnl_pct': float(r[5]) if r[5] else 0,
                                'pnl_usdt': float(r[6]) if r[6] else 0,
                                'net_pnl_pct': float(r[7]) if r[7] else 0,
                                'net_pnl_usdt': float(r[8]) if r[8] else 0,
                                'reason': r[9],
                                'close_reason': r[9],
                                'duration_seconds': float(r[10]) if r[10] else 0,
                                'closed_at': r[11].isoformat() if r[11] else None,
                                'size': float(r[12]) if r[12] else 0,
                                'session_id': str(r[13]) if r[13] else None
                            })
                        state.set_trade_history(trades)
                        logger.info(f"Historique charge depuis PostgreSQL: {len(trades)} trades (24h)")
                        return
            finally:
                pg_logger.pool.putconn(conn)
    except ImportError as e:
        # PostgreSQL module non disponible
        logger.debug(f"Module PostgreSQL non disponible: {e}")
    except DatabaseConnectionError as e:
        # Erreur de connexion à la base de données
        logger.warning(f"⚠️ Impossible de se connecter à PostgreSQL: {e}")
    except DatabaseError as e:
        # Erreur database (query, schema, etc.)
        logger.warning(f"⚠️ Erreur database PostgreSQL lors chargement: {e}")
    except Exception as e:
        # Erreur inattendue
        logger.warning(f"⚠️ Impossible de charger depuis PostgreSQL: {type(e).__name__}: {e}", exc_info=True)
    
    # Fallback: Charger depuis JSON
    try:
        if os.path.exists(TRADE_HISTORY_FILE):
            with open(TRADE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                trades = json.load(f)
            state.set_trade_history(trades)
            logger.info(f"Historique charge depuis JSON: {len(trades)} trades")
        else:
            state.set_trade_history([])
            logger.info(f"Nouveau fichier historique cree: {TRADE_HISTORY_FILE}")
    except (FileNotFoundError, PermissionError) as e:
        # Erreur d'accès fichier
        logger.warning(f"⚠️ Erreur d'accès fichier JSON: {e}")
        state.set_trade_history([])
    except json.JSONDecodeError as e:
        # Fichier JSON corrompu
        logger.error(f"❌ Fichier historique JSON corrompu: {e}")
        state.set_trade_history([])
    except (OSError, IOError) as e:
        # Erreur I/O
        logger.error(f"❌ Erreur I/O chargement historique JSON: {e}")
        state.set_trade_history([])
    except Exception as e:
        # Erreur inattendue
        logger.error(f"❌ Erreur inattendue chargement historique: {type(e).__name__}: {e}", exc_info=True)
        state.set_trade_history([])

# 🔥 SPRINT 2.1: app_state migré vers StateManager
# Utiliser: state.is_scanning, state.active_position, state.stats, etc.
# Pour compatibilité avec routes qui attendent app_state dict:
app_state = LegacyAppStateProxy(state)  # Wrapper pour accès legacy


async def _run_initial_top_pairs_scan() -> None:
    """
    Lancer le scan initial des top pairs sans bloquer la boucle d'événements.

    Cette fonction est exécutée en arrière-plan au démarrage de l'application
    pour identifier les paires les plus prometteuses et initialiser les
    connexions WebSocket pour le suivi des prix en temps réel.

    Side Effects:
        - Initialise les instances globales (scanner, price_provider)
        - Met à jour app_state['top_pairs']
        - Démarre les WebSocket pour le suivi des prix
        - Émet des événements WebSocket vers le frontend
        - Ajoute des logs dans la base de données

    Note:
        Ne fait rien si le scan a déjà été effectué (top_pairs présent)
    """
    init_instances()

    if app_state.get('top_pairs'):
        return  # Scan déjà effectué

    try:
        await add_log('INFO', 'Scanner démarré', 'Scan initial des top pairs en arrière-plan...')
        scanner_inst = state.get_scanner()
        if not scanner_inst:
            logger.warning("⚠️ Scanner non disponible")
            return
        
        # 🔥 FIX: Vérifier si le scanner est déjà en cours
        if scanner_inst.is_scanning:
            logger.debug("⏸️ Scan initial ignoré - Scanner déjà actif")
            return
        
        top_pairs = await scanner_inst.scan_top_pairs(20)

        if not top_pairs:
            logger.warning("⚠️ Scan initial terminé sans résultats")
            return

        state.set_top_pairs(top_pairs)

        ws_mgr = state.get_ws_manager()
        if ws_mgr:
            await ws_mgr.emit('top_pairs_update', {'pairs': top_pairs})

        price_prov = state.get_price_provider()
        if price_prov:
            symbols = [p.get('symbol', '') for p in top_pairs[:30] if p.get('symbol')]
            if symbols:
                try:
                    await price_prov.start_websocket(symbols)
                    await add_log('INFO', 'WebSocket démarré', f'{len(symbols)} symboles monitorés')
                except WebSocketError as e:
                    # Erreur WebSocket lors du démarrage
                    logger.warning(f"⚠️ Erreur WebSocket lors du démarrage: {e}")
                except NetworkError as e:
                    # Erreur réseau lors de la connexion WebSocket
                    logger.warning(f"⚠️ Erreur réseau WebSocket: {e}")
                except Exception as e:
                    # Erreur inattendue lors du démarrage WebSocket
                    logger.warning(f"⚠️ Erreur inattendue démarrage WebSocket: {type(e).__name__}: {e}", exc_info=True)

    except MarketDataError as e:
        # Erreur lors du scan des paires (pas de données, etc.)
        logger.error(f"❌ Erreur données marché lors scan initial: {e}", exc_info=True)
    except NetworkError as e:
        # Erreur réseau lors du scan
        logger.error(f"❌ Erreur réseau lors scan initial: {e}", exc_info=True)
    except Exception as e:
        # Erreur inattendue durant le scan
        logger.error(f"❌ Erreur inattendue scan initial en arrière-plan: {type(e).__name__}: {e}", exc_info=True)

# 🔥 FIX: Injecter app_state dans le router APRÈS définition
if api_router and set_app_state:
    set_app_state(app_state)
    logger.info("✅ app_state injecté dans API routes")

# 🔥 MIGRATION COMPLÈTE: ws_manager injecté dans les routes (fait après création de ws_manager)

# 🔥 SPRINT 2.1: Variables globales migrées vers StateManager
# Toutes les instances sont maintenant gérées par state = get_state_manager()
# Utiliser:
#   state.get_scanner() / state.set_scanner()
#   state.get_analyzer() / state.set_analyzer()
#   state.get_position_manager() / state.set_position_manager()
#   state.get_price_provider() / state.set_price_provider()
#   state.get_scheduler() / state.set_scheduler()
#   state.get_trade_db() / state.set_trade_db()
#   state.get_analytics_db() / state.set_analytics_db()
#   state.get_notification_manager() / state.set_notification_manager()
#   state.get_live_order_manager() / state.set_live_order_manager()
#   state.get_simple_logger() / state.set_simple_logger()
#   state.backend_reboot_in_progress
#   state.session_id
#   state.lock("position") / state.lock("scanner")

# ⚠️ TODO: Legacy code still uses global variables - will be refactored incrementally
# For now, keep compatibility by accessing through functions
def get_scanner():
    return state.get_scanner()

def get_analyzer():
    return state.get_analyzer()

def get_position_manager():
    return state.get_position_manager()

def get_price_provider():
    return state.get_price_provider()

# Temporary global references for compatibility (will be removed)
scanner = None
analyzer = None
position_config = None
position_manager = None
price_provider = None
scheduler = None
backend_reboot_in_progress = False
analytics_db = None
notification_manager = None
session_id = None
live_order_manager = None
_simple_logger = None
position_lock = asyncio.Lock()
scanner_lock = asyncio.Lock()


# 🔥 NOUVEAU: Fonction helper pour notifier les erreurs via Telegram
async def notify_error_telegram(error_type: str, details: str):
    """
    Notifier une erreur via Telegram si TELEGRAM_NOTIFY_ERROR est activé.
    
    Args:
        error_type: Type d'erreur (ex: 'Scalability Data', 'API Error')
        details: Détails de l'erreur
    """
    try:
        notif_mgr = state.get_notification_manager()
        if notif_mgr:
            # Vérifier si les notifications d'erreur sont activées
            if notif_mgr.telegram_notify_settings.get('error', True):
                await notif_mgr.notify('error', {
                    'error_type': error_type,
                    'details': details
                }, priority='high')
    except NotificationError as e:
        # Erreur spécifique notification (Telegram, etc.)
        logger.debug(f"⚠️ Erreur notification Telegram: {e}")
    except NetworkError as e:
        # Erreur réseau lors de l'envoi de la notification
        logger.debug(f"⚠️ Erreur réseau notification Telegram: {e}")
    except Exception as e:
        # Erreur inattendue lors de la notification
        logger.debug(f"⚠️ Impossible de notifier l'erreur via Telegram: {type(e).__name__}: {e}")


def notify_error_sync(error_type: str, details: str) -> None:
    """
    Version synchrone de notify_error_telegram.
    Utilise asyncio pour envoyer la notification.
    """
    try:
        notif_mgr = state.get_notification_manager()
        if notif_mgr and notif_mgr.telegram_notifier:
            if notif_mgr.telegram_notify_settings.get('error', True):
                notif_mgr.telegram_notifier.send_error_sync(error_type, details)
    except NotificationError as e:
        # Erreur spécifique notification (Telegram, etc.)
        logger.debug(f"⚠️ Erreur notification Telegram (sync): {e}")
    except NetworkError as e:
        # Erreur réseau lors de l'envoi de la notification
        logger.debug(f"⚠️ Erreur réseau notification Telegram (sync): {e}")
    except Exception as e:
        # Erreur inattendue lors de la notification
        logger.debug(f"⚠️ Impossible de notifier l'erreur (sync): {type(e).__name__}: {e}")


# 🔥 FIX SL MISMATCH: Fonction pour configurer vérification SL temps réel
async def setup_realtime_sl_check(position: Any, price_provider_instance: Any) -> None:
    """
    Configure la vérification SL en temps réel via WebSocket.

    Cette fonction est appelée après l'ouverture d'une position pour garantir
    que le SL sera détecté immédiatement à chaque tick, pas toutes les 2 secondes.

    Args:
        position: Position active (objet Position ou dict)
        price_provider_instance: Instance HybridPriceProvider
    """
    if not position or not price_provider_instance:
        return
    
    # Extraire les paramètres de la position
    symbol = position.symbol if hasattr(position, 'symbol') else position.get('symbol')
    direction = position.direction if hasattr(position, 'direction') else position.get('direction')
    sl_level = position.sl if hasattr(position, 'sl') else position.get('sl')
    entry_price = position.entry if hasattr(position, 'entry') else position.get('entry')
    
    if not all([symbol, direction, sl_level, entry_price]):
        logger.warning(f"⚠️ Impossible de configurer SL temps réel: paramètres manquants")
        return
    
    # Callback appelé quand SL est touché
    async def on_sl_triggered(exit_price: float, reason: str):
        """Callback appelé immédiatement quand SL est touché via WebSocket"""
        logger.info(f"⚡ SL temps réel déclenché: {symbol} @ {exit_price:.8f} | Raison: {reason}")
        
        # Acquérir le lock pour éviter les conditions de course
        async with state.lock("position"):
            pos_mgr = state.get_position_manager()
            # Vérifier que la position est toujours active
            if not pos_mgr or not pos_mgr.active_position:
                logger.debug("Position déjà fermée, callback SL ignoré")
                return
            
            # Fermer la position
            try:
                result = pos_mgr.close_position(exit_price=exit_price, reason=reason)
                
                # Mettre à jour l'état
                state.set_active_position(None)
                
                # Archiver dans l'historique
                if result:
                    result['timestamp'] = datetime.now().isoformat()
                    # 🔥 FIX: Utiliser add_trade pour upsert sécurisé
                    state.add_trade(result)
                
                # Désactiver le callback SL (déjà fait dans price_provider)
                if price_provider_instance:
                    price_provider_instance.set_sl_check_callback(None)
                
                # 🔥 FIX SL MISMATCH V2: Annuler tâche SL en attente
                cancel_pending_sl_task(symbol)
                
                # Émettre événement de fermeture
                ws_mgr = state.get_ws_manager()
                if ws_mgr:
                    await ws_mgr.emit('position_closed', result)
                    # Stats update
                    await ws_mgr.emit('stats_update', app_state.get('stats', {}))
                
                logger.info(
                    f"✅ Position fermée via SL temps réel: {symbol} | "
                    f"PnL: {result.get('pnl_percent', 0):+.2f}% | "
                    f"Raison: {reason}"
                )
                
            except PositionError as e:
                # Erreur position spécifique (position inexistante, déjà fermée, etc.)
                logger.error(f"❌ Erreur position lors fermeture SL temps réel: {e}", exc_info=True)
            except OrderExecutionError as e:
                # Erreur lors de l'exécution de l'ordre de fermeture
                logger.error(f"❌ Erreur exécution ordre fermeture SL: {e}", exc_info=True)
            except DatabaseError as e:
                # Erreur lors de la sauvegarde du trade fermé
                logger.error(f"❌ Erreur DB lors fermeture SL (trade fermé mais non sauvegardé): {e}", exc_info=True)
            except WebSocketError as e:
                # Erreur lors de l'émission WebSocket (position fermée mais frontend pas notifié)
                logger.warning(f"⚠️ Erreur WS lors émission fermeture SL: {e}")
            except Exception as e:
                # Erreur inattendue lors de la fermeture
                logger.error(f"❌ Erreur inattendue fermeture position SL temps réel: {type(e).__name__}: {e}", exc_info=True)
    
    # Configurer le callback dans le price_provider
    price_provider_instance.set_sl_check_callback(
        callback=on_sl_triggered,
        symbol=symbol,
        direction=direction,
        sl_level=sl_level,
        entry_price=entry_price
    )
    
    logger.info(
        f"🛡️ SL temps réel configuré: {symbol} {direction} | "
        f"SL={sl_level:.8f} | Entry={entry_price:.8f}"
    )


# 🔥 FIX SL MISMATCH V2: Tâches SL différées (placement sur exchange après 3s)
_pending_sl_tasks: Dict[str, asyncio.Task] = {}


async def schedule_sl_order_placement(position: Any, delay_seconds: float = 3.0) -> None:
    """
    Planifie le placement d'un ordre SL sur l'exchange après un délai.

    Cette fonction attend que le prix d'entrée réel soit disponible (via ccxt),
    puis place un ordre SL de protection sur MEXC.

    Args:
        position: Position active (objet Position)
        delay_seconds: Délai avant placement (défaut: 3 secondes)
    """
    global _pending_sl_tasks
    
    if not position:
        return
    
    symbol = position.symbol if hasattr(position, 'symbol') else position.get('symbol')
    if not symbol:
        return
    
    # Annuler toute tâche précédente pour ce symbole
    if symbol in _pending_sl_tasks:
        old_task = _pending_sl_tasks[symbol]
        if not old_task.done():
            old_task.cancel()
            logger.debug(f"🛑 Tâche SL précédente annulée pour {symbol}")
    
    async def _delayed_sl_placement():
        """Tâche interne qui attend puis place l'ordre SL"""
        try:
            logger.info(f"⏳ Attente {delay_seconds}s avant placement ordre SL sur exchange pour {symbol}...")
            await asyncio.sleep(delay_seconds)
            
            # Vérifier si la position est toujours active
            pos_mgr = state.get_position_manager()
            if not pos_mgr or not pos_mgr.active_position:
                logger.info(f"ℹ️ Position {symbol} déjà fermée, annulation placement SL exchange")
                return
            
            active_pos = pos_mgr.active_position
            if active_pos.symbol != symbol:
                logger.info(f"ℹ️ Symbole actif différent ({active_pos.symbol} vs {symbol}), annulation")
                return
            
            # Récupérer les paramètres actuels de la position
            entry_price = active_pos.entry_fill_price or active_pos.entry
            sl_level = active_pos.sl
            direction = active_pos.direction
            
            if not all([entry_price, sl_level, direction]):
                logger.warning(f"⚠️ Paramètres manquants pour SL exchange: entry={entry_price}, sl={sl_level}, dir={direction}")
                return
            
            # Vérifier si le live_order_manager est disponible et pas en dry-run
            live_ord_mgr = state.get_live_order_manager()
            if not live_ord_mgr:
                logger.debug(f"ℹ️ Pas de live_order_manager, SL exchange non placé")
                return
            
            if live_ord_mgr.dry_run:
                logger.info(
                    f"🛡️ [DRY_RUN] Ordre SL exchange simulé: {symbol} {direction} | "
                    f"Entry={entry_price:.8f} | SL={sl_level:.8f}"
                )
                return
            
            # 🔥 Placer l'ordre SL via bypass
            if hasattr(live_ord_mgr, 'place_stop_loss_order'):
                result = await live_ord_mgr.place_stop_loss_order(
                    symbol=symbol,
                    direction=direction,
                    sl_price=sl_level,
                    entry_price=entry_price
                )
                if result and result.success:
                    logger.info(
                        f"✅ Ordre SL placé sur exchange: {symbol} | "
                        f"SL={sl_level:.8f} | Order ID={result.order_id}"
                    )
                    # Stocker l'ID de l'ordre SL dans la position
                    active_pos.sl_order_id = result.order_id
                else:
                    error_msg = result.error_message if result else "Méthode indisponible"
                    logger.warning(f"⚠️ Échec placement SL exchange: {error_msg}")
            else:
                logger.debug(f"ℹ️ Méthode place_stop_loss_order non disponible")
            
        except asyncio.CancelledError:
            # Tâche SL annulée (position fermée avant le placement)
            logger.info(f"🛑 Tâche SL annulée pour {symbol}")
        except PositionError as e:
            # Erreur position (position inexistante, etc.)
            logger.error(f"❌ Erreur position lors placement SL exchange: {e}", exc_info=True)
        except OrderExecutionError as e:
            # Erreur lors du placement de l'ordre SL
            logger.error(f"❌ Erreur exécution ordre SL exchange: {e}", exc_info=True)
        except NetworkError as e:
            # Erreur réseau lors de la communication avec l'exchange
            logger.warning(f"⚠️ Erreur réseau placement SL exchange: {e}")
        except APIError as e:
            # Erreur API exchange
            logger.error(f"❌ Erreur API placement SL exchange: {e}", exc_info=True)
        except Exception as e:
            # Erreur inattendue
            logger.error(f"❌ Erreur inattendue placement SL exchange: {type(e).__name__}: {e}", exc_info=True)
        finally:
            # Nettoyer la tâche
            if symbol in _pending_sl_tasks:
                del _pending_sl_tasks[symbol]
    
    # Créer et stocker la tâche
    task = asyncio.create_task(_delayed_sl_placement())
    _pending_sl_tasks[symbol] = task
    logger.debug(f"📋 Tâche SL programmée pour {symbol} dans {delay_seconds}s")


def cancel_pending_sl_task(symbol: str) -> None:
    """
    Annule la tâche SL en attente pour un symbole.

    Appelé quand une position se ferme avant que l'ordre SL ne soit placé.

    Args:
        symbol: Symbole de la position fermée
    """
    global _pending_sl_tasks
    
    if symbol in _pending_sl_tasks:
        task = _pending_sl_tasks[symbol]
        if not task.done():
            task.cancel()
            logger.info(f"🛑 Tâche SL annulée pour {symbol} (position fermée)")
        del _pending_sl_tasks[symbol]


# 🔥 JOUR 3: Callbacks pour le scheduler (doivent être définis avant init_instances)

async def scanner_loop_callback() -> None:
    """
    Callback appelé périodiquement par le scheduler pour scanner les opportunités de trading.

    Cette fonction est le cœur du système de scanning automatique. Elle est exécutée
    à intervalle régulier (défini par scan_interval dans config) pour identifier
    des setups de trading sur les paires les plus prometteuses.

    Le processus est le suivant:
    1. Vérifie qu'aucune position n'est active (skip si position active)
    2. Scan initial des top pairs si nécessaire (volume, volatilité)
    3. Analyse technique des top N paires (parallélisé)
    4. Filtrage ML optionnel (winrate prédiction)
    5. Validation finale des setups trouvés
    6. Ouverture de position si setup valide

    Side Effects:
        - Initialise les instances globales
        - Acquiert scanner_lock pour éviter les scans concurrents
        - Met à jour app_state['top_pairs']
        - Démarre les WebSocket pour le suivi des prix
        - Log les résultats dans PostgreSQL
        - Ouvre une position si un setup est trouvé
        - Émet des événements WebSocket vers le frontend

    Note:
        - Ne fait rien si une position est déjà active
        - Utilise un lock global pour éviter les scans multiples en parallèle
        - Le nombre de paires scannées est configurable (top_pairs_limit)
    """
    from config import TRADING_CONFIG  # 🔥 FIX: Import global pour disponibilité dans toute la fonction
    
    init_instances()
    
    # 🔥 FIX: Lock global pour éviter les scans multiples en parallèle
    async with state.lock("scanner"):
        # Ne pas scanner si on a déjà une position active (vérification atomique dans le lock)
        # Cette vérification est faite AVANT de commencer le scan pour éviter de gaspiller des ressources
        pos_mgr = state.get_position_manager()
        
        # 🔧 SELF-HEALING: Si state.active_position est None mais pos_mgr.active_position est encore set,
        # c'est probablement une race condition avec _schedule_position_sync (thread séparé).
        # state.active_position est la source de vérité → on nettoie pos_mgr.active_position stale.
        if not state.active_position and pos_mgr and pos_mgr.active_position:
            try:
                stale_symbol = getattr(pos_mgr.active_position, 'symbol', 'UNKNOWN')
            except Exception:
                stale_symbol = 'UNKNOWN'
            logger.warning(
                f"🔧 Self-healing: pos_mgr.active_position stale détectée ({stale_symbol}) "
                f"→ nettoyage (state.active_position déjà None)"
            )
            pos_mgr.active_position = None
        
        if state.active_position or (pos_mgr and pos_mgr.active_position):
            logger.debug("⏸️ Scanner ignoré : position active")
            return
        
        # 🔥 SPRINT 1: Vérifier Trading Circuit Breaker avant de scanner
        try:
            # TRADING_CONFIG déjà importé au début de la fonction
            if TRADING_CONFIG.get('trading_circuit_breaker_enabled', True):
                from core.trading_circuit_breaker import get_trading_circuit_breaker
                trading_cb = get_trading_circuit_breaker()
                if not trading_cb.can_trade():
                    cb_status = trading_cb.get_status()
                    logger.warning(
                        f"🛑 Scanner ignoré : Circuit Breaker {cb_status['state']} | "
                        f"Raison: {cb_status.get('pause_reason', 'N/A')} | "
                        f"Reprise dans: {cb_status.get('remaining_pause_seconds', '?')}s"
                    )
                    # Émettre l'état au frontend
                    ws_mgr = state.get_ws_manager()
                    if ws_mgr:
                        await ws_mgr.emit('circuit_breaker_trading_update', cb_status)
                    return
        except ImportError as e:
            # Module circuit breaker non disponible
            logger.debug(f"Module circuit breaker non disponible: {e}")
        except ConfigurationError as e:
            # Configuration circuit breaker invalide
            logger.warning(f"⚠️ Configuration circuit breaker invalide: {e}")
        except Exception as e:
            # Erreur non-critique lors de la vérification circuit breaker
            logger.debug(f"⚠️ Erreur vérification Circuit Breaker: {type(e).__name__}: {e}")
        
        # 🔥 JOUR 3: Si on n'a pas de top_pairs, on les scanne d'abord
        scanner_inst = state.get_scanner()
        if not state.top_pairs:
            await add_log('INFO', 'Scanner loop', 'Scan initial des top pairs...')
            if scanner_inst:
                top_pairs = await scanner_inst.scan_top_pairs(20)
                state.set_top_pairs(top_pairs)
                
                # 🔥 OPTIMISATION: Invalider cache quand top_pairs change
                if hasattr(app, '_top_pairs_cache'):
                    app._top_pairs_cache.pop('top_pairs', None)
                
                ws_mgr = state.get_ws_manager()
                if ws_mgr:
                    await ws_mgr.emit('top_pairs_update', {'pairs': top_pairs})
                
                # 🔥 JOUR 3: Démarrer WebSocket pour les top pairs
                price_prov = state.get_price_provider()
                if price_prov and top_pairs:
                    symbols = [p.get('symbol', '') for p in top_pairs[:30] if p.get('symbol')]
                    if symbols:
                        try:
                            await price_prov.start_websocket(symbols)
                            await add_log('INFO', 'WebSocket démarré', f'{len(symbols)} symboles monitorés')
                        except WebSocketError as e:
                            # Erreur WebSocket lors du démarrage
                            logger.warning(f"⚠️ Erreur WebSocket lors du démarrage: {e}")
                        except NetworkError as e:
                            # Erreur réseau lors de la connexion WebSocket
                            logger.warning(f"⚠️ Erreur réseau WebSocket: {e}")
                        except Exception as e:
                            # Erreur inattendue lors du démarrage WebSocket
                            logger.warning(f"⚠️ Erreur inattendue démarrage WebSocket: {type(e).__name__}: {e}")
        
        # 🔥 SPRINT 1: Vérifier et mettre à jour le régime de marché
        top_pairs = state.top_pairs
        if top_pairs and TRADING_CONFIG.get('market_regime_enabled', True):
            try:
                from core.market_regime_selector import get_regime_selector
                regime_selector = get_regime_selector()
                
                # Extraire ATR et ADX des top pairs
                atr_values = []
                atr_5m_values = []
                adx_values = []
                for pair in top_pairs[:10]:
                    atr = pair.get('atr_percent') or pair.get('atr', 0)
                    atr_5m = pair.get('atr_percent_5m')
                    adx = pair.get('adx', 25)
                    if atr and float(atr) > 0:
                        atr_values.append(float(atr))
                        adx_values.append(float(adx))
                        if atr_5m is not None and float(atr_5m) > 0:
                            atr_5m_values.append(float(atr_5m))
                
                if atr_values:
                    # 🔥 FIX: Stocker les échantillons pour l'affichage dans le widget
                    regime_selector.atr_sample_count = len(atr_values)
                    
                    # 🔥 FIX: Forcer la vérification si on a plus de données qu'avant (ex: démarrage progressif)
                    # Si on avait peu d'échantillons (<5) et qu'on en a maintenant beaucoup (>=5), on re-vérifie
                    # sans attendre l'intervalle de 60 minutes.
                    force_check = False
                    old_sample_count = getattr(regime_selector, '_last_sample_count', 0)
                    if old_sample_count < 5 and len(atr_values) >= 5:
                        force_check = True
                        logger.info(f"🔄 Forcing regime check: Samples improved ({old_sample_count} -> {len(atr_values)})")
                    regime_selector._last_sample_count = len(atr_values)

                    new_regime, changed = await regime_selector.check_regime(
                        atr_values=atr_values,
                        atr_5m_values=atr_5m_values,
                        adx_values=adx_values,
                        force=force_check,
                        trigger="auto"
                    )
                    
                    # 🔥 FIX 08/12/2025: NE PLUS modifier TRADING_CONFIG directement!
                    # Utiliser le système effective_config pour séparer base vs effective
                    # Les sliders gardent leurs valeurs, seules les valeurs EFFECTIVES changent
                    active_config = regime_selector.get_active_config()
                    if active_config:
                        from utils.effective_config import set_regime_adjustments
                        set_regime_adjustments(active_config)
                        logger.debug(f"  -> Ajustements régime stockés: {list(active_config.keys())}")
                    
                    if changed:
                        regime_status = regime_selector.get_status()
                        logger.info(
                            f"🌡️ Régime changé: {new_regime.value} | "
                            f"ATR: {regime_status['avg_atr']:.3f}% | ADX: {regime_status['avg_adx']:.0f}"
                        )
                        # Émettre au frontend
                        ws_mgr = state.get_ws_manager()
                        if ws_mgr:
                            await ws_mgr.emit('regime_changed', regime_status)
            except ImportError as e:
                # Module regime selector non disponible
                logger.debug(f"Module regime selector non disponible: {e}")
            except MarketDataError as e:
                # Erreur données marché (ATR, ADX invalides)
                logger.warning(f"⚠️ Erreur données marché pour régime: {e}")
            except ConfigurationError as e:
                # Configuration régime invalide
                logger.warning(f"⚠️ Configuration régime invalide: {e}")
            except Exception as e:
                # Erreur non-critique lors de la vérification du régime
                logger.debug(f"⚠️ Erreur vérification régime: {type(e).__name__}: {e}")
        
        # 🔥 JOUR 3: Scanner plusieurs paires en parallèle (top 20)
        top_pairs = state.top_pairs
        if top_pairs:
            # 🔥 FIX: Scanner top 20 au lieu de top 5 pour plus d'opportunités
            from config import TRADING_CONFIG
            max_pairs = TRADING_CONFIG.get('top_pairs_limit', 20)
            total_available = len(top_pairs)
            top_n = min(max_pairs, total_available)  # Scanner top 20
            pairs_to_scan = top_pairs[:top_n]
            
            # 🔥 DEBUG: Log détaillé pour comprendre
            symbols_list = [p.get('symbol', '') for p in pairs_to_scan if p.get('symbol')]
            await add_log('INFO', 'Scanner loop', 
                f'Analyse {top_n}/{total_available} paires disponibles: {", ".join(symbols_list[:10])}' + 
                (f'... (+{len(symbols_list)-10} autres)' if len(symbols_list) > 10 else ''))
            
            # 🔥 FIX: Ne plus logger de warning si moins de paires que prévu (c'est normal)
            # if total_available < max_pairs:
            #     await add_log('WARNING', 'Paires limitées', 
            #         f'Seulement {total_available} paires disponibles (attendu: {max_pairs})')
            
            # Scanner toutes les paires en parallèle
            scan_tasks = []
            for pair in pairs_to_scan:
                symbol = pair.get('symbol', '')
                if symbol:
                    scan_tasks.append(scan_pair_for_setup(symbol))
            
            if scan_tasks:
                # Exécuter toutes les analyses en parallèle
                results = await asyncio.gather(*scan_tasks, return_exceptions=True)
                
                # Compter les résultats avec détails
                valid_setups = 0
                no_setup = 0
                errors = 0
                rejection_reasons = {}  # Dict pour compter les raisons de rejet
                last_ml_confidence = None  # 🔥 FIX: Initialiser ICI pour qu'il soit disponible dans le logging
                
                # 🔥 FIX: Analyser chaque résultat en détail
                for i, result in enumerate(results):
                    symbol_analyzed = pairs_to_scan[i].get('symbol', 'UNKNOWN') if i < len(pairs_to_scan) else 'UNKNOWN'
                    
                    if isinstance(result, Exception):
                        errors += 1
                        logger.warning(f"❌ Erreur analyse {symbol_analyzed}: {result}")
                    elif result and isinstance(result, dict):
                        # Vérifier si c'est une raison de rejet ou un setup valide
                        if 'reason' in result:
                            # C'est une raison de rejet
                            no_setup += 1
                            reason = result.get('reason', 'Raison inconnue')
                            # Extraire la raison principale (avant le | ou le premier mot)
                            main_reason = reason.split('|')[0].strip() if '|' in reason else reason.split(':')[0].strip() if ':' in reason else reason[:50]
                            rejection_reasons[main_reason] = rejection_reasons.get(main_reason, 0) + 1
                            
                            # 🔥 FIX: Log détaillé pour chaque rejet
                            logger.debug(f"🔍 {symbol_analyzed}: {reason}")
                        elif 'symbol' in result and 'direction' in result:
                            # C'est un setup valide
                            valid_setups += 1
                            logger.info(
                                f"✅ Setup trouvé: {result.get('symbol')} - {result.get('direction')} | "
                                f"Timeframe: {result.get('confirmedBy', 'N/A')} | "
                                f"Conditions: {len(result.get('signals', []))} | "
                                f"Entry: {result.get('price', 'N/A')} | "
                                f"ATR: {result.get('atr', 0):.6f} ({result.get('atr', 0) / result.get('price', 1) * 100 if result.get('price') else 0:.3f}%)"
                            )
                        else:
                            # Résultat inattendu
                            no_setup += 1
                            logger.warning(f"⚠️ Résultat inattendu pour {symbol_analyzed}: {result}")
                    else:
                        # None ou résultat vide
                        no_setup += 1
                        logger.debug(f"🔍 {symbol_analyzed}: Pas de setup (None)")
                
                # 🔥 FIX: Envoyer stats volume au frontend pour mettre à jour le compteur
                total_analyzed = len(results)
                validated_count = valid_setups
                # Émettre événement SocketIO pour mettre à jour les stats côté frontend
                ws_mgr = state.get_ws_manager()
                if ws_mgr:
                    await ws_mgr.emit('volume_stats_update', {
                        'total': total_analyzed,
                        'validated': validated_count,
                        'ratio': (validated_count / total_analyzed * 100) if total_analyzed > 0 else 0
                    })
                
                # 🔥 FIX: Log résumé détaillé avec raisons principales
                summary_parts = [f'{valid_setups} setups valides', f'{no_setup} sans setup']
                if errors > 0:
                    summary_parts.append(f'{errors} erreurs')
                
                summary = ', '.join(summary_parts)
                
                # Ajouter les raisons principales de rejet si aucune setup n'a été trouvé
                if valid_setups == 0 and rejection_reasons:
                    # Trier par fréquence (plus fréquent en premier)
                    sorted_reasons = sorted(rejection_reasons.items(), key=lambda x: x[1], reverse=True)
                    top_reasons = sorted_reasons[:5]  # Top 5 raisons
                    reasons_text = ' | '.join([f"{reason} ({count}x)" for reason, count in top_reasons])
                    summary += f" | Principales raisons: {reasons_text}"
                
                await add_log('INFO', 'Résumé scan', summary)
                
                # 🔥 FIX: Log détaillé dans le logger Python aussi
                logger.info(f"📊 Résumé scan: {summary}")
                
                # Si on a trouvé un setup valide, ouvrir la position
                if valid_setups > 0:
                    logger.info(f"🎯 {valid_setups} setup(s) valide(s) trouvé(s), tentative d'ouverture de position...")
                    for result in results:
                        # 🔥 FIX: Vérifier que result est un setup valide (dict avec 'symbol' et 'direction', pas une raison)
                        if result and not isinstance(result, Exception) and isinstance(result, dict):
                            # Vérifier que ce n'est PAS une raison de rejet
                            if 'reason' in result:
                                continue  # C'est une raison, pas un setup
                            
                            # Vérifier que c'est un setup valide (avec symbol et direction)
                            if 'symbol' not in result or 'direction' not in result:
                                continue  # Ce n'est pas un setup complet
                            
                            # 🔥 FIX: Log détaillé avant tentative d'ouverture
                            symbol = result.get('symbol', 'UNKNOWN')
                            direction = result.get('direction', 'UNKNOWN')
                            logger.info(
                                f"🚀 Tentative d'ouverture position: {symbol} - {direction} | "
                                f"Entry (setup): {result.get('price', 'N/A')} | "
                                f"SL: {result.get('sl', 'N/A')} | TP: {result.get('tp', 'N/A')} | "
                                f"ATR: {result.get('atr', 0):.6f} | "
                                f"Conditions: {len(result.get('signals', []))} | "
                                f"Confirmed by: {result.get('confirmedBy', 'N/A')}"
                            )
                            
                            # 🔥 FIX: Lock pour éviter les ouvertures multiples
                            async with state.lock("position"):
                                pos_mgr = state.get_position_manager()
                                # Vérifier à nouveau qu'on n'a pas déjà une position (double-check après lock)
                                if state.active_position or (pos_mgr and pos_mgr.active_position):
                                    logger.warning(
                                        f"🚫 Position déjà active - Scanner ignoré. "
                                        f"state.active_position={state.active_position is not None}, "
                                        f"position_manager.active_position={pos_mgr.active_position if pos_mgr else None}"
                                    )
                                    await add_log('WARNING', 'Position déjà active', 
                                        'Un setup a été trouvé mais une position est déjà ouverte')
                                    break
                                
                                # 🔥 FIX: Log avant ouverture pour debug
                                logger.info(f"🔓 Lock acquis - Ouverture position pour {symbol}")
                                
                                # 🔥 FIX: Ouvrir position automatiquement
                                setup = result
                                # symbol et direction déjà définis avant le lock
                                # symbol = setup.get('symbol', '')
                                # direction = setup.get('direction', 'LONG')
                                
                                await add_log('INFO', 'Setup trouvé', 
                                    f"{symbol} - {direction} - {len(setup.get('signals', []))} conditions")
                                
                                try:
                                    # Récupérer prix d'entrée
                                    price_prov = state.get_price_provider()
                                    if not price_prov:
                                        logger.warning(f"⚠️ DEBUG: state.get_price_provider() retourne None pour {symbol}")
                                        price_prov = get_price_provider()
                                        logger.info(f"✅ DEBUG: get_price_provider() singleton créé: {type(price_prov)}")
                                    
                                    if not price_prov:
                                        logger.error(f"❌ DEBUG: get_price_provider() singleton AUSSI None pour {symbol}")
                                        await add_log('ERROR', 'PriceProvider indisponible', symbol)
                                        continue
                                    
                                    price_data = await price_prov.get_price(symbol)
                                    if not price_data:
                                        await add_log('ERROR', 'Prix non disponible', symbol)
                                        continue
                                    
                                    entry_price = get_preferred_price(price_data, setup.get('price', 0))
                                    if not entry_price or entry_price == 0:
                                        await add_log('ERROR', 'Prix invalide', f"{symbol}: {entry_price}")
                                        continue
                                    
                                    # 🔥 FIX: Log pour debug - vérifier le prix récupéré
                                    logger.info(
                                        f"💰 Prix récupéré pour {symbol}: refPrice={get_preferred_price(price_data)}, "
                                        f"setup_price={setup.get('price')}, entry_price={entry_price}"
                                    )
                                    
                                    # Calculer taille de position (position sizing)
                                    from config import TRADING_CONFIG, RISK_CONFIG
                                    
                                    # Capital par défaut (peut être modifié via config)
                                    account_size = TRADING_CONFIG.get('account_size', 1000.0)
                                    risk_per_trade = TRADING_CONFIG.get('risk_per_trade', 2.0) / 100  # 2% par défaut
                                    
                                    # Récupérer ATR pour calculer SL%
                                    atr = setup.get('atr', 0)
                                    atr5m = setup.get('atr5m')
                                    
                                    # Calculer SL% selon le mode
                                    tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
                                    # 🔥 PHASE 7: TP_MULTI utilise aussi le calcul ATR
                                    if (tp_sl_mode == 'ATR' or tp_sl_mode == 'TP_MULTI') and atr and entry_price:
                                        sl_percent = (atr / entry_price) * 100
                                        # Clamp selon config
                                        atr_min = TRADING_CONFIG.get('atr_min', 0.15)
                                        atr_max = TRADING_CONFIG.get('atr_max', 1.5)
                                        sl_percent = max(atr_min, min(atr_max, sl_percent))
                                    else:
                                        sl_percent = TRADING_CONFIG.get('sl_percent', 0.25)
                                    
                                    # 🔥 PHASE 2: Position sizing adaptatif
                                    pos_mgr = state.get_position_manager()
                                    position_size = pos_mgr.calculate_position_size(
                                        setup=setup,
                                        capital=account_size
                                    )
                                    
                                    # 🔥 Récupérer le multiplicateur adaptatif pour affichage frontend
                                    adaptive_sizing_mult = 1.0
                                    if TRADING_CONFIG.get('adaptive_sizing_enabled', True):
                                        try:
                                            from core.position.adaptive_sizing import get_adaptive_sizing_manager
                                            adaptive_manager = get_adaptive_sizing_manager()
                                            adaptive_sizing_mult = adaptive_manager.get_size_multiplier(symbol)
                                        except Exception:
                                            pass
                                    
                                    # 🔥 FIX: Log détaillé du calcul de taille pour debug (WARNING pour visibilité)
                                    logger.warning(
                                        f"💰 POSITION SIZE DEBUG: {symbol} | "
                                        f"Capital: {account_size:.2f} USDT | "
                                        f"Risk%: {risk_per_trade*100:.2f}% | "
                                        f"SL%: {sl_percent:.4f}% | "
                                        f"Taille calculée: {position_size:.2f} USDT"
                                    )
                                    
                                    # Récupérer scalability_data pour slippage
                                    scalability_data = None
                                    logger.info(f"💹 DEBUG: Recherche scalability_data pour {symbol} (main.py)")
                                    
                                    top_pairs = state.top_pairs
                                    if top_pairs:
                                        logger.info(f"💹 DEBUG: top_pairs contient {len(top_pairs)} paires")
                                        found_pair = False
                                        for pair in top_pairs:
                                            # 🔥 FIX: Normaliser symboles avant comparaison (BTC/USDT vs BTC/USDT:USDT)
                                            pair_symbol = (pair.get('symbol') or '').split(':')[0]
                                            lookup_symbol = (symbol or '').split(':')[0]
                                            if pair_symbol == lookup_symbol:
                                                found_pair = True
                                                # 🔥 FIX: Utiliser les bonnes clés depuis le scanner (spread, bookDepth, balanceScore, bidVol, askVol)
                                                spread_value = pair.get('spread', 0)
                                                book_depth = pair.get('bookDepth', 0)
                                                balance_score = pair.get('balanceScore', 1.0)
                                                bid_vol = pair.get('bidVol', 0)
                                                ask_vol = pair.get('askVol', 0)
                                                
                                                logger.info(f"💹 DEBUG: Données brutes depuis top_pairs: spread={spread_value}, bookDepth={book_depth}, balanceScore={balance_score}, bidVol={bid_vol}, askVol={ask_vol}")
                                                
                                                # Vérifier si spread est NaN ou invalide
                                                if isinstance(spread_value, float) and (spread_value != spread_value or spread_value == float('nan')):
                                                    logger.warning(f"💹 DEBUG: spread est NaN, remplacement par 0")
                                                    spread_value = 0
                                                
                                                # 🔥 FIX: Si spread ou depth sont à 0, essayer de récupérer depuis setup
                                                if spread_value == 0 and setup.get('spread_pct'):
                                                    spread_value = setup.get('spread_pct', 0)
                                                    logger.info(f"💹 Utilisation spread depuis setup: {spread_value}%")
                                                
                                                # 🔥 FIX: Si depth est à 0, calculer depuis bid_vol + ask_vol
                                                if book_depth == 0 and (bid_vol > 0 or ask_vol > 0):
                                                    book_depth = bid_vol + ask_vol
                                                    logger.info(f"💹 Calcul depth depuis volumes: {book_depth}")
                                                
                                                scalability_data = {
                                                    'spread_pct': spread_value,
                                                    'depth': book_depth,
                                                    'balance': balance_score,
                                                    'bid_vol': bid_vol,
                                                    'ask_vol': ask_vol,
                                                    # 🔥 FIX: Ajouter les paramètres du scan de scalabilité
                                                    'recent_volume': pair.get('recentVolume'),
                                                    'vol5': pair.get('vol5'),
                                                    'vol15': pair.get('vol15'),
                                                    'scalability_score': pair.get('score'),
                                                }
                                                
                                                logger.info(f"💹 Données scalabilité récupérées depuis top_pairs: spread={spread_value}%, depth={book_depth}, balance={balance_score}")
                                                break
                                        
                                        if not found_pair:
                                            logger.warning(f"💹 DEBUG: Paire {symbol} non trouvée dans top_pairs")
                                        
                                        # 🔥 FIX: Si scalability_data est toujours None ou invalide, essayer depuis setup
                                        if not scalability_data or (scalability_data.get('spread_pct', 0) == 0 and scalability_data.get('depth', 0) == 0):
                                            logger.warning(f"💹 Données scalabilité manquantes/invalides dans top_pairs pour {symbol}, tentative depuis setup")
                                            logger.info(f"💹 DEBUG: setup keys: {list(setup.keys())[:15]}")
                                            if setup.get('spread_pct'):
                                                # Essayer de récupérer depth depuis orderbook_check si disponible
                                                orderbook_depth = 0
                                                if 'orderbook_check' in setup:
                                                    orderbook_check = setup['orderbook_check']
                                                    bid_value = orderbook_check.get('bid_value', 0)
                                                    ask_value = orderbook_check.get('ask_value', 0)
                                                    orderbook_depth = bid_value + ask_value
                                                    logger.info(f"💹 DEBUG: Depth calculé depuis orderbook_check: {orderbook_depth}")
                                                elif 'orderbook_bid_value' in setup and 'orderbook_ask_value' in setup:
                                                    bid_value = setup.get('orderbook_bid_value', 0)
                                                    ask_value = setup.get('orderbook_ask_value', 0)
                                                    orderbook_depth = bid_value + ask_value
                                                    logger.info(f"💹 DEBUG: Depth calculé depuis orderbook_bid/ask_value: {orderbook_depth}")
                                                
                                                scalability_data = {
                                                    'spread_pct': setup.get('spread_pct', 0),
                                                    'depth': orderbook_depth or setup.get('orderbook_depth', 0) or (setup.get('bid_vol', 0) + setup.get('ask_vol', 0)),
                                                    'balance': setup.get('orderbook_balance', 1.0) or setup.get('orderbook_check', {}).get('balance', 1.0),
                                                    'bid_vol': setup.get('bid_vol'),
                                                    'ask_vol': setup.get('ask_vol'),
                                                    # 🔥 FIX: Ajouter les paramètres du scan de scalabilité depuis setup si disponibles
                                                    'recent_volume': setup.get('recent_volume') or setup.get('recentVolume'),
                                                    'vol5': setup.get('vol5'),
                                                    'vol15': setup.get('vol15'),
                                                    'scalability_score': setup.get('scalability_score') or setup.get('score'),
                                                }
                                                logger.info(f"💹 Données scalabilité depuis setup: spread={scalability_data.get('spread_pct')}%, depth={scalability_data.get('depth')}")
                                            else:
                                                # ⚠️ Warning non-bloquant: spread_pct manquant (rare, ~1x/4-5h)
                                                logger.warning(f"💹 spread_pct non disponible dans setup pour {symbol} (non-bloquant)")
                                    else:
                                        logger.warning(f"💹 top_pairs non disponible pour récupérer scalability_data pour {symbol}")
                                    
                                    # ✅ Stocker scan_uuid, opportunity_id et setup complet pour Point C
                                    pos_mgr._last_setup_scan_uuid = setup.get('_scan_uuid')
                                    pos_mgr._last_setup_opportunity_id = setup.get('_opportunity_id')
                                    
                                    # 🔥 DEBUG: Vérifier si setup contient les indicateurs avant stockage
                                    logger.info(f"🔍 DEBUG main.py: setup contient indicators_1m: {'indicators_1m' in setup}, indicators_5m: {'indicators_5m' in setup}")
                                    if 'indicators_1m' in setup:
                                        logger.info(f"✅ indicators_1m présent dans setup: {len(setup.get('indicators_1m', {}))} clés")
                                    if 'indicators_5m' in setup:
                                        logger.info(f"✅ indicators_5m présent dans setup: {len(setup.get('indicators_5m', {}))} clés")
                                    
                                    pos_mgr._last_setup = setup  # Stocker setup complet pour récupérer indicateurs
                                    
                                    # 🔥 DEBUG: Vérifier après stockage
                                    logger.info(f"🔍 DEBUG main.py: _last_setup après stockage contient indicators_1m: {'indicators_1m' in pos_mgr._last_setup}, indicators_5m: {'indicators_5m' in pos_mgr._last_setup}")
                                    
                                    # 🔥 FIX: Vérifier slippage et SL avant d'ouvrir la position
                                    setup_price = setup.get('price', entry_price)
                                    slippage_pct = abs((entry_price - setup_price) / setup_price * 100) if setup_price > 0 else 0
                                    max_slippage_pct = TRADING_CONFIG.get('max_slippage_pct', 0.5)  # 0.5% par défaut
                                    
                                    # Calculer SL pour le prix réel
                                    if (tp_sl_mode == 'ATR' or tp_sl_mode == 'TP_MULTI') and atr and entry_price:
                                        calculated_sl = entry_price - (atr * TRADING_CONFIG.get('atr_mult_sl', 1.0)) if direction == 'LONG' else entry_price + (atr * TRADING_CONFIG.get('atr_mult_sl', 1.0))
                                    else:
                                        sl_pct = TRADING_CONFIG.get('sl_percent', 0.25) / 100
                                        calculated_sl = entry_price * (1 - sl_pct) if direction == 'LONG' else entry_price * (1 + sl_pct)
                                    
                                    # Vérifier que le prix réel n'est pas déjà en dessous du SL (pour LONG) ou au-dessus du SL (pour SHORT)
                                    sl_already_hit = False
                                    if direction == 'LONG':
                                        if entry_price <= calculated_sl:
                                            sl_already_hit = True
                                            logger.warning(
                                                f"⚠️ {symbol} - Position LONG rejetée : Prix d'entrée ({entry_price:.6f}) "
                                                f"est déjà en dessous du SL ({calculated_sl:.6f})"
                                            )
                                    else:  # SHORT
                                        if entry_price >= calculated_sl:
                                            sl_already_hit = True
                                            logger.warning(
                                                f"⚠️ {symbol} - Position SHORT rejetée : Prix d'entrée ({entry_price:.6f}) "
                                                f"est déjà au-dessus du SL ({calculated_sl:.6f})"
                                            )
                                    
                                    # Vérifier slippage
                                    if slippage_pct > max_slippage_pct:
                                        logger.warning(
                                            f"⚠️ {symbol} - Position rejetée : Slippage trop élevé "
                                            f"({slippage_pct:.3f}% > {max_slippage_pct:.3f}%) | "
                                            f"Setup: {setup_price:.6f} | Réel: {entry_price:.6f}"
                                        )
                                        await add_log('WARNING', 'Slippage trop élevé', 
                                            f"{symbol}: {slippage_pct:.3f}% > {max_slippage_pct:.3f}%")
                                        continue
                                    
                                    # Rejeter si SL déjà touché
                                    if sl_already_hit:
                                        await add_log('WARNING', 'SL déjà touché', 
                                            f"{symbol}: Prix d'entrée ({entry_price:.6f}) déjà au-delà du SL ({calculated_sl:.6f})")
                                        continue
                                    
                                    # Log validation
                                    if slippage_pct > 0.1:  # Log si slippage > 0.1%
                                        logger.info(
                                            f"⚠️ {symbol} - Slippage détecté : {slippage_pct:.3f}% "
                                            f"(Setup: {setup_price:.6f} → Réel: {entry_price:.6f})"
                                        )
                                    
                                    # 🌳 FILTRE GRADIENTBOOSTING (modèle optimisé)
                                    if TRADING_CONFIG.get('gb_filter_enabled', False):
                                        logger.info(f"🌳 Filtre GradientBoosting activé - Vérification pour {symbol}...")
                                        
                                        try:
                                            from optimization.predictor_optimized import get_predictor
                                            
                                            # Extraire features depuis setup
                                            gb_features = {}
                                            indicators_1m = setup.get('indicators_1m', {})
                                            indicators_5m = setup.get('indicators_5m', {})
                                            
                                            # 🔍 DEBUG: Vérifier contenu du setup
                                            logger.warning(f"🔍 DEBUG setup keys pour {symbol}: {list(setup.keys())}")
                                            logger.warning(f"🔍 DEBUG indicators_1m: {len(indicators_1m)} items: {list(indicators_1m.keys()) if indicators_1m else 'VIDE'}")
                                            logger.warning(f"🔍 DEBUG indicators_5m: {len(indicators_5m)} items: {list(indicators_5m.keys()) if indicators_5m else 'VIDE'}")
                                            
                                            # 🔥 Indicateurs techniques 1m et 5m (TOUS les indicateurs disponibles)
                                            import math
                                            for key, value in indicators_1m.items():
                                                if isinstance(value, (int, float)) and not (isinstance(value, float) and math.isnan(value)):
                                                    gb_features[f"{key}_1m" if not key.endswith('_1m') else key] = value
                                            for key, value in indicators_5m.items():
                                                if isinstance(value, (int, float)) and not (isinstance(value, float) and math.isnan(value)):
                                                    gb_features[f"{key}_5m" if not key.endswith('_5m') else key] = value
                                            
                                            # 🔥 Features depuis la racine du setup (prix, volume, etc.)
                                            setup_direct_features = ['price', 'volume', 'atr', 'spread', 'orderbook_imbalance']
                                            for feat in setup_direct_features:
                                                if feat in setup and isinstance(setup[feat], (int, float)) and not math.isnan(setup[feat]):
                                                    gb_features[feat] = setup[feat]
                                            
                                            # 🔥 Scores et filtres qualité (si disponibles)
                                            scores = setup.get('scores', {})
                                            if scores:
                                                for key, value in scores.items():
                                                    if isinstance(value, (int, float)) and not (isinstance(value, float) and math.isnan(value)):
                                                        gb_features[f"score_{key}"] = value
                                            
                                            # 🔥 Direction (LONG=1, SHORT=0)
                                            gb_features['direction'] = 1 if direction.upper() == 'LONG' else 0
                                            
                                            # 🔥 Setup metrics
                                            gb_features['totalScore'] = setup.get('totalScore', 0)
                                            gb_features['conditions'] = setup.get('conditions', 0)
                                            
                                            # 🔥 Features dérivées calculées à la volée (Bollinger, EMA, etc.)
                                            if indicators_1m and indicators_5m:
                                                # BB Position (feature TOP importance)
                                                bb_lower_1m = indicators_1m.get('bb_lower', 0)
                                                bb_upper_1m = indicators_1m.get('bb_upper', 0)
                                                if bb_upper_1m != bb_lower_1m:
                                                    bb_width_1m = bb_upper_1m - bb_lower_1m
                                                    if bb_width_1m > 0 and 'price' in setup:
                                                        price = setup['price']
                                                        gb_features['bb_position_1m'] = (price - bb_lower_1m) / bb_width_1m
                                                        gb_features['bb_width_1m'] = bb_width_1m / price * 100  # En %
                                                
                                                # EMA divergence 1m/5m
                                                ema_diff_1m = indicators_1m.get('ema_diff_pct', 0)
                                                ema_diff_5m = indicators_5m.get('ema_diff_pct', 0)
                                                if ema_diff_1m != 0 and ema_diff_5m != 0:
                                                    gb_features['ema_divergence'] = abs(ema_diff_1m - ema_diff_5m)
                                                    gb_features['ema_aligned'] = 1 if (ema_diff_1m > 0) == (ema_diff_5m > 0) else 0
                                                
                                                # RSI momentum
                                                rsi_1m = indicators_1m.get('rsi', 50)
                                                rsi_5m = indicators_5m.get('rsi', 50)
                                                gb_features['rsi_divergence'] = abs(rsi_1m - rsi_5m)
                                                gb_features['rsi_distance_50_1m'] = abs(rsi_1m - 50)
                                                
                                                # Volatility ratio
                                                atr_1m = indicators_1m.get('atr_pct', 0)
                                                atr_5m = indicators_5m.get('atr_pct', 0)
                                                if atr_5m > 0:
                                                    gb_features['volatility_ratio'] = atr_1m / atr_5m
                                                
                                                # Volume momentum
                                                vol_ratio_1m = indicators_1m.get('volume_ratio', 1)
                                                vol_ratio_5m = indicators_5m.get('volume_ratio', 1)
                                                gb_features['volume_divergence'] = abs(vol_ratio_1m - vol_ratio_5m)
                                                
                                                # 🔥 NOUVELLES FEATURES MANQUANTES (8/8) pour 100% disponibilité
                                                
                                                # 1-2. RSI précédents (approximation si pas disponible)
                                                gb_features['rsi_prev_1m'] = indicators_1m.get('rsi_prev', rsi_1m - 1.0)  # Approximation
                                                gb_features['rsi_prev_5m'] = indicators_5m.get('rsi_prev', rsi_5m - 1.0)  # Approximation
                                                
                                                # 3. MACD histogram précédent
                                                macd_hist_1m = indicators_1m.get('macd_hist', 0)
                                                gb_features['macd_hist_prev_1m'] = indicators_1m.get('macd_hist_prev', macd_hist_1m - 0.001)  # Approximation
                                                
                                                # 4-7. BB Distances absolues (critiques pour le modèle)
                                                if 'price' in setup and bb_upper_1m and bb_lower_1m:
                                                    price = setup['price']
                                                    gb_features['bb_distance_to_upper_1m'] = max(0, bb_upper_1m - price)
                                                    gb_features['bb_distance_to_lower_1m'] = max(0, price - bb_lower_1m)
                                                
                                                bb_lower_5m = indicators_5m.get('bb_lower', 0)
                                                bb_upper_5m = indicators_5m.get('bb_upper', 0)
                                                if 'price' in setup and bb_upper_5m and bb_lower_5m:
                                                    price = setup['price']
                                                    gb_features['bb_distance_to_upper_5m'] = max(0, bb_upper_5m - price)
                                                    gb_features['bb_distance_to_lower_5m'] = max(0, price - bb_lower_5m)
                                                
                                                # 8. DI minus 5m si pas déjà présent
                                                if 'di_minus' not in gb_features and 'di_minus' in indicators_5m:
                                                    gb_features['di_minus_5m'] = indicators_5m['di_minus']
                                                
                                                # Calculer BB width 5m si pas encore fait
                                                if bb_upper_5m and bb_lower_5m and bb_upper_5m != bb_lower_5m:
                                                    gb_features['bb_width_5m'] = bb_upper_5m - bb_lower_5m
                                            
                                            # 🔥 FEATURES SPÉCIFIQUES MODÈLE OPTIMISÉ (5 manquantes critiques)
                                            
                                            # 1. EMA trend strength (force de tendance EMA)
                                            ema9_1m = indicators_1m.get('ema9', 0)
                                            ema21_1m = indicators_1m.get('ema21', 0)
                                            if ema21_1m > 0:
                                                gb_features['ema_trend_strength_1m'] = abs(ema9_1m - ema21_1m) / ema21_1m
                                            
                                            ema9_5m = indicators_5m.get('ema9', 0)
                                            ema21_5m = indicators_5m.get('ema21', 0)
                                            if ema21_5m > 0:
                                                gb_features['ema_trend_strength_5m'] = abs(ema9_5m - ema21_5m) / ema21_5m
                                            
                                            # 2. RSI change (variation RSI)
                                            rsi_1m = indicators_1m.get('rsi', 50)
                                            rsi_prev_1m = indicators_1m.get('rsi_prev', rsi_1m)
                                            gb_features['rsi_change_1m'] = rsi_1m - rsi_prev_1m
                                            
                                            # 3. Delta volume (différentiel volume 1m vs 5m)
                                            vol_ratio_1m = indicators_1m.get('volume_ratio', 1.0)
                                            vol_ratio_5m = indicators_5m.get('volume_ratio', 1.0)
                                            gb_features['delta_volume'] = vol_ratio_1m - vol_ratio_5m
                                            
                                            # 4. Momentum divergence (approximation MACD/RSI)
                                            macd_1m = indicators_1m.get('macd', 0)
                                            macd_5m = indicators_5m.get('macd', 0)
                                            rsi_div = abs(rsi_1m - indicators_5m.get('rsi', 50))
                                            gb_features['momentum_divergence'] = (abs(macd_1m - macd_5m) * 100) + (rsi_div / 100)
                                            
                                            # 5. Renommer hour_utc → hour (attendu par modèle)
                                            from datetime import datetime, timezone
                                            now = datetime.now(timezone.utc)
                                            gb_features['hour'] = now.hour  # ← Feature exacte attendue
                                            gb_features['session_europe'] = 1 if 8 <= now.hour < 16 else 0
                                            gb_features['session_usa'] = 1 if 13 <= now.hour < 21 else 0
                                            gb_features['high_activity_hours'] = 1 if 13 <= now.hour < 17 else 0
                                            
                                            logger.warning(f"🌳 Features extraites pour {symbol}: {list(gb_features.keys())}")
                                            logger.debug(f"🔍 GB Features total: {len(gb_features)} features")
                                            
                                            if gb_features:
                                                predictor = get_predictor()
                                                if predictor.is_loaded:
                                                    # 🔥 PHASE 2D: Seuil dynamique via Threshold Optimizer
                                                    gb_min_confidence = TRADING_CONFIG.get('gb_min_confidence', 0.55)
                                                    threshold_source = "config"
                                                    
                                                    if TRADING_CONFIG.get('threshold_optimizer_enabled', False):
                                                        try:
                                                            from core.ml import get_threshold_optimizer
                                                            from core.market_regime_selector import get_regime_selector
                                                            from utils.session_detector import get_current_session
                                                            
                                                            # Récupérer le contexte
                                                            regime_selector = get_regime_selector()
                                                            current_regime = regime_selector.current_regime.value if regime_selector.current_regime else 'UNKNOWN'
                                                            session_info = get_current_session()
                                                            current_session = session_info.get('name', 'UNKNOWN') if isinstance(session_info, dict) else 'UNKNOWN'
                                                            current_hour = int(session_info.get('hour_utc', datetime.now(timezone.utc).hour)) if isinstance(session_info, dict) else datetime.now(timezone.utc).hour
                                                            
                                                            # Obtenir le seuil dynamique
                                                            optimizer = get_threshold_optimizer()
                                                            gb_min_confidence = optimizer.get_threshold(
                                                                regime=current_regime,
                                                                session=current_session,
                                                                hour=current_hour
                                                            )
                                                            threshold_source = f"optimizer({current_regime}/{current_session})"
                                                            
                                                            # Stocker le contexte dans le setup pour le feedback loop
                                                            setup['_market_regime'] = current_regime
                                                            setup['_trading_session'] = current_session
                                                            setup['_trade_hour'] = current_hour
                                                        except ImportError as opt_err:
                                                            # Module threshold optimizer non disponible
                                                            logger.debug(f"Module threshold optimizer non disponible: {opt_err}")
                                                        except ConfigurationError as opt_err:
                                                            # Configuration optimizer invalide
                                                            logger.warning(f"⚠️ Configuration threshold optimizer invalide: {opt_err}")
                                                        except Exception as opt_err:
                                                            # Erreur non-critique, utiliser seuil par défaut
                                                            logger.debug(f"⚠️ Threshold optimizer error, using default: {type(opt_err).__name__}: {opt_err}")
                                                    
                                                    should_trade, confidence = predictor.predict(gb_features, threshold=gb_min_confidence)
                                                    
                                                    logger.info(f"🌳 GradientBoosting: should_trade={should_trade}, confidence={confidence*100:.1f}% (seuil: {gb_min_confidence*100:.0f}% [{threshold_source}])")
                                                    
                                                    # 🔥 FIX CRITIQUE: Stocker ml_confidence comme décimal (0.0-1.0), pas pourcentage
                                                    ml_conf_decimal = round(confidence, 4)  # Décimal arrondi à 4 décimales
                                                    ml_conf_pct = round(confidence * 100, 1)
                                                    setup['ml_confidence'] = ml_conf_decimal  
                                                    last_ml_confidence = ml_conf_decimal  # Variable pour le logging
                                                    
                                                    # 🔥 FIX: Mettre à jour ml_confidence dans PostgreSQL (scan déjà loggé)
                                                    # 🔥 FIX: Utiliser version async non-bloquante pour ne pas freeze l'event loop
                                                    pg_logger = None
                                                    try:
                                                        from core.callbacks.scanner_loop import get_pg_datalogger
                                                        pg_logger = get_pg_datalogger()
                                                        if pg_logger and pg_logger.enabled:
                                                            await pg_logger.update_ml_confidence_async(symbol, ml_conf_pct)
                                                    except ImportError as pg_err:
                                                        # Module PostgreSQL non disponible
                                                        logger.debug(f"Module PostgreSQL non disponible: {pg_err}")
                                                    except DatabaseError as pg_err:
                                                        # Erreur database lors de la mise à jour
                                                        logger.debug(f"⚠️ Erreur DB mise à jour ml_confidence: {pg_err}")
                                                    except Exception as pg_err:
                                                        # Erreur inattendue lors de la mise à jour
                                                        logger.debug(f"⚠️ Impossible de mettre à jour ml_confidence: {type(pg_err).__name__}: {pg_err}")
                                                    
                                                    if not should_trade:
                                                        reject_reason = f"ML confidence {confidence*100:.1f}% < seuil {gb_min_confidence*100:.0f}% [{threshold_source}]"
                                                        logger.warning(f"❌ GradientBoosting REJETTE {symbol}: {reject_reason}")
                                                        
                                                        # 🔥 FIX 15/12: Logger le rejet ML dans reject_reason_category
                                                        # Distinguer si le rejet vient d'un seuil statique ou dynamique (Optimizer)
                                                        reject_cat = "ml_threshold_optimizer" if "optimizer" in threshold_source else "ml_gb_confidence"
                                                        
                                                        # 🔥 FIX: Utiliser version async non-bloquante pour ne pas freeze l'event loop
                                                        try:
                                                            if pg_logger and pg_logger.enabled:
                                                                await pg_logger.update_ml_rejection_async(
                                                                    symbol=symbol,
                                                                    reject_reason=reject_reason,
                                                                    reject_category=reject_cat,
                                                                    ml_confidence=ml_conf_pct
                                                                )
                                                        except ImportError as ml_rej_err:
                                                            # Module PostgreSQL non disponible
                                                            logger.debug(f"Module PostgreSQL non disponible: {ml_rej_err}")
                                                        except DatabaseError as ml_rej_err:
                                                            # Erreur database lors du logging du rejet
                                                            logger.debug(f"⚠️ Erreur DB log ML rejection: {ml_rej_err}")
                                                        except Exception as ml_rej_err:
                                                            # Erreur inattendue (non-bloquante)
                                                            logger.debug(f"⚠️ Erreur log ML rejection: {type(ml_rej_err).__name__}: {ml_rej_err}")
                                                        
                                                        continue  # Passer au setup suivant
                                                    else:
                                                        logger.info(f"✅ GradientBoosting APPROUVE {symbol} (confiance: {confidence*100:.1f}%)")
                                                else:
                                                    logger.warning(f"⚠️ Modèle GradientBoosting non chargé, trade autorisé par défaut")
                                            else:
                                                logger.warning(f"⚠️ Pas de features GB pour {symbol}, trade autorisé par défaut")

                                        except ImportError as gb_error:
                                            # Module ML/GradientBoosting non disponible
                                            logger.debug(f"Module GradientBoosting non disponible: {gb_error}")
                                            logger.warning(f"⚠️ Trade autorisé sans filtre GB")
                                        except MarketDataError as gb_error:
                                            # Erreur données marché (features invalides)
                                            logger.error(f"❌ Erreur données marché filtre GB: {gb_error}")
                                            logger.warning(f"⚠️ Trade autorisé malgré erreur données (failsafe)")
                                        except Exception as gb_error:
                                            # Erreur inattendue dans le filtre ML
                                            logger.error(f"❌ Erreur inattendue filtre GradientBoosting: {type(gb_error).__name__}: {gb_error}", exc_info=True)
                                            logger.warning(f"⚠️ Trade autorisé malgré erreur GB (failsafe)")
                                    
                                    # 🔥 SPRINT 1: Appliquer score_boost du Circuit Breaker
                                    if TRADING_CONFIG.get('trading_cb_score_boost_enabled', True):
                                        try:
                                            from core.trading_circuit_breaker import get_trading_circuit_breaker
                                            trading_cb = get_trading_circuit_breaker()
                                            score_boost = trading_cb.get_score_boost()
                                            
                                            if score_boost > 0:
                                                setup_score = setup.get('totalScore', 0) or setup.get('score_1m', 0) or 0
                                                min_score = setup.get('min_score_required', TRADING_CONFIG.get('min_score_required', 7.0))
                                                adjusted_min = min_score + score_boost
                                                
                                                if setup_score < adjusted_min:
                                                    reject_reason_cb = (
                                                        f"Circuit Breaker score boost: Score {setup_score:.1f} < {adjusted_min:.1f} "
                                                        f"(min: {min_score:.1f} + boost: {score_boost:.1f}) | Losses: {trading_cb.consecutive_losses}"
                                                    )
                                                    logger.warning(f"⚠️ {symbol} - {reject_reason_cb}")
                                                    
                                                    # 🔥 FIX 15/12: Logger le rejet CB dans reject_reason_category
                                                    try:
                                                        from core.callbacks.scanner_loop import get_pg_datalogger
                                                        pg_logger_cb = get_pg_datalogger()
                                                        if pg_logger_cb and pg_logger_cb.enabled:
                                                            pg_logger_cb.update_ml_rejection(
                                                                symbol=symbol,
                                                                reject_reason=reject_reason_cb,
                                                                reject_category="circuit_breaker_score_boost"
                                                            )
                                                    except ImportError as cb_rej_err:
                                                        # Module PostgreSQL non disponible
                                                        logger.debug(f"Module PostgreSQL non disponible: {cb_rej_err}")
                                                    except DatabaseError as cb_rej_err:
                                                        # Erreur database lors du logging du rejet
                                                        logger.debug(f"⚠️ Erreur DB log CB rejection: {cb_rej_err}")
                                                    except Exception as cb_rej_err:
                                                        # Erreur inattendue (non-bloquante)
                                                        logger.debug(f"⚠️ Erreur log CB rejection: {type(cb_rej_err).__name__}: {cb_rej_err}")
                                                    
                                                    continue  # Passer au setup suivant
                                                else:
                                                    logger.info(
                                                        f"✅ {symbol} - Score boost appliqué: {setup_score:.1f} >= {adjusted_min:.1f}"
                                                    )
                                        except ImportError as cb_err:
                                            # Module circuit breaker non disponible
                                            logger.debug(f"Module circuit breaker non disponible: {cb_err}")
                                        except ConfigurationError as cb_err:
                                            # Configuration circuit breaker invalide
                                            logger.warning(f"⚠️ Configuration circuit breaker invalide: {cb_err}")
                                        except Exception as cb_err:
                                            # Erreur non-critique lors du score boost
                                            logger.debug(f"⚠️ Erreur score_boost CB: {type(cb_err).__name__}: {cb_err}")
                                    
                                    # Ouvrir la position
                                    condition_types = setup.get('condition_types', [])  # 🔥 PHASE 5: Types de conditions
                                    
                                    # 🌳 ANCIENNE SECTION GB SUPPRIMÉE 
                                    # Le filtre GradientBoosting optimisé (28+ features) est déjà actif plus haut dans le code
                                    # Cette section basique (7 features) était redondante et causait des conflits
                                    
                                    # 🔄 INVERSION DES SIGNAUX (pour diagnostic)
                                    original_direction = direction
                                    if TRADING_CONFIG.get('invert_signals', False):
                                        direction = 'SHORT' if direction == 'LONG' else 'LONG'
                                        logger.warning(
                                            f"🔄 INVERSION DE SIGNAL ACTIVÉE: {symbol} | "
                                            f"Signal original: {original_direction} → Direction inversée: {direction}"
                                        )
                                    
                                    position = pos_mgr.open_position(
                                        symbol=symbol,
                                        direction=direction,
                                        entry=entry_price,
                                        size=position_size,
                                        atr=atr,
                                        atr5m=atr5m,
                                        confirmed_by=setup.get('confirmedBy', 'Scanner auto'),
                                        scalability_data=scalability_data,
                                        condition_types=condition_types,  # 🔥 PHASE 5: Types de conditions
                                        ml_confidence=setup.get('ml_confidence'),  # 🔥 FIX: Passer ml_confidence
                                        adaptive_sizing_multiplier=adaptive_sizing_mult,  # 🔥 Multiplicateur adaptatif
                                        setup_data=setup  # 🔥 CRITICAL: Passer le setup complet pour accès indicators_1m/5m
                                    )
                                    
                                    # 🔥 FIX: Vérifier si position rejetée par calibration
                                    if position is None:
                                        logger.info(f"⏭️ Trade {symbol} {direction} ignoré (rejeté par calibration)")
                                        continue
                                    
                                    # Stocker capital
                                    position.capital = account_size
                                    
                                    # Mettre à jour state AVANT d'émettre l'événement
                                    state.set_active_position(position)

                                    # 🔥 FIX: Vérification finale avant de continuer
                                    if state.active_position != position:
                                        logger.error(f"❌ ERREUR: state.active_position a été modifié pendant l'ouverture !")
                                        break

                                    # 🔥 FIX CRITIQUE: Redémarrer WebSocket UNIQUEMENT sur le symbole de la position
                                    # Ceci garantit que current_price sera mis à jour correctement pendant la position
                                    # PROBLÈME: subscribe_ticker() ajoutait juste le symbole aux symboles existants
                                    # SOLUTION: Redémarrer complètement le WebSocket avec UNIQUEMENT le symbole de la position
                                    if price_prov:
                                        try:
                                            # Arrêter WebSocket actuel
                                            if hasattr(price_prov, 'stop_websocket'):
                                                await price_prov.stop_websocket()
                                                logger.info(f"🔌 WebSocket arrêté avant position")
                                                # Attendre que le WebSocket soit complètement arrêté
                                                await asyncio.sleep(0.5)

                                            # Redémarrer WebSocket uniquement sur le symbole de la position
                                            if hasattr(price_prov, 'start_websocket'):
                                                await price_prov.start_websocket([symbol])
                                                logger.info(f"✅ WebSocket redémarré pour position: {symbol} UNIQUEMENT")

                                            # Configurer callback pour suivre position active
                                            if hasattr(price_prov, 'set_socketio_callback'):
                                                price_prov.set_socketio_callback(None, symbol)
                                                logger.debug(f"📡 WebSocket configuré pour suivre {symbol} (prix en temps réel dans cache)")
                                        except WebSocketError as e:
                                            # Erreur WebSocket lors du redémarrage
                                            logger.error(f"❌ Erreur WebSocket redémarrage pour position {symbol}: {e}", exc_info=True)
                                        except NetworkError as e:
                                            # Erreur réseau lors de la connexion WebSocket
                                            logger.error(f"❌ Erreur réseau WebSocket pour position {symbol}: {e}", exc_info=True)
                                        except Exception as e:
                                            # Erreur inattendue lors du redémarrage WebSocket
                                            logger.error(f"❌ Erreur inattendue redémarrage WebSocket pour position {symbol}: {type(e).__name__}: {e}", exc_info=True)
                                    
                                    # 🔥 FIX SL MISMATCH: Configurer vérification SL temps réel
                                    price_prov = state.get_price_provider()
                                    if price_prov and position:
                                        await setup_realtime_sl_check(position, price_prov)
                                    
                                    # 🔥 FIX SL MISMATCH V2: Planifier placement ordre SL sur exchange après 3s
                                    if position:
                                        await schedule_sl_order_placement(position, delay_seconds=3.0)
                                    
                                    # Logger et notifier (UNE SEULE FOIS)
                                    # 🔥 Afficher le mode de trading clairement
                                    live_mgr = state.get_live_order_manager()
                                    if live_mgr:
                                        mode_str = "🟡 LIVE DRY-RUN" if live_mgr.dry_run else "🔴 LIVE RÉEL"
                                    else:
                                        mode_str = "📝 PAPER"
                                    await add_log('INFO', f'Position ouverte [{mode_str}]', 
                                        f"{direction} {symbol} @ {entry_price:.6f} | Size: {position_size:.2f} USDT")
                                    
                                    # 🔥 FIX: Émettre l'événement UNE SEULE FOIS avec gestion d'erreur pour éviter les déconnexions
                                    try:
                                        ws_mgr = state.get_ws_manager()
                                        if ws_mgr:
                                            await ws_mgr.emit('position_opened', position.to_dict())
                                    except WebSocketError as e:
                                        # Erreur WebSocket lors de l'émission (non-bloquant)
                                        logger.warning(f"⚠️ Erreur WebSocket émission position_opened: {e}")
                                    except Exception as e:
                                        # Erreur inattendue lors de l'émission (non-bloquant)
                                        logger.warning(f"⚠️ Erreur inattendue émission position_opened: {type(e).__name__}: {e}")
                                    
                                    # 🔥 FIX: Émettre immédiatement le prix actuel pour l'affichage frontend avec gestion d'erreur
                                    try:
                                        price_prov = state.get_price_provider()
                                        current_price_data = await price_prov.get_price(symbol) if price_prov else None
                                        if current_price_data:
                                            current_price = get_preferred_price(current_price_data, entry_price)
                                            # 🔥 FIX: Utiliser pnl_calculator au lieu de _calculate_pnl
                                            pnl = pos_mgr.pnl_calculator.calculate_pnl_percent(
                                                entry=position.entry,
                                                current_price=current_price,
                                                direction=position.direction
                                            )
                                            # Calculer PnL USDT
                                            pnl_usdt = pos_mgr.pnl_calculator.calculate_pnl_usdt(
                                                position=position.to_dict(),
                                                current_price=current_price
                                            )
                                            
                                            # 🔥 FIX: Gestion d'erreur pour éviter les déconnexions WebSocket
                                            try:
                                                ws_mgr = state.get_ws_manager()
                                                if ws_mgr:
                                                    await ws_mgr.emit('position_update', {
                                                        'symbol': position.symbol,
                                                        'direction': position.direction,
                                                        'entry': position.entry,
                                                        'current_price': current_price,
                                                        'sl': position.sl,
                                                        'tp': position.tp,
                                                        'pnl': pnl,
                                                        'pnl_usdt': pnl_usdt,
                                                        'size': position.size,
                                                        'break_even_set': position.break_even_set,
                                                        'partial_tp_sold': position.partial_tp_sold,
                                                        'position_size_contracts': getattr(position, 'position_size_contracts', None),
                                                        'size_initial_contracts': getattr(position, 'size_initial_contracts', None),
                                                        'size_remaining_contracts': getattr(position, 'size_remaining_contracts', None),
                                                        # 🔥 FIX: Ajouter tp_sl_mode, opened_at pour affichage ATR
                                                        'tp_sl_mode': TRADING_CONFIG.get('tp_sl_mode', 'FIXE'),
                                                        'opened_at': getattr(position, 'opened_at', None),
                                                        'force_full_tp_for_partial': getattr(position, 'force_full_tp_for_partial', False),
                                                        'leverage_used': getattr(position, 'leverage_used', None),
                                                        'ml_confidence': getattr(position, 'ml_confidence', None),
                                                        'ml_calibrated_winrate': getattr(position, 'ml_calibrated_winrate', None),
                                                        'adaptive_sizing_multiplier': getattr(position, 'adaptive_sizing_multiplier', None),
                                                    })
                                                    logger.debug(f"📡 Prix actuel émis immédiatement: {current_price:.6f} pour {symbol}")
                                            except WebSocketError as e:
                                                # Erreur WebSocket lors de l'émission (non-bloquant)
                                                logger.warning(f"⚠️ Erreur WebSocket émission position_update: {e}")
                                            except Exception as e:
                                                # Erreur inattendue lors de l'émission (non-bloquant)
                                                logger.warning(f"⚠️ Erreur inattendue émission position_update: {type(e).__name__}: {e}")
                                    except MarketDataError as e:
                                        # Erreur récupération prix (API, données invalides)
                                        logger.warning(f"⚠️ Erreur données marché récupération prix initial: {e}")
                                    except NetworkError as e:
                                        # Erreur réseau lors de la récupération du prix
                                        logger.warning(f"⚠️ Erreur réseau récupération prix initial: {e}")
                                    except Exception as e:
                                        # Erreur inattendue lors de la récupération du prix
                                        logger.warning(f"⚠️ Erreur inattendue récupération prix initial: {type(e).__name__}: {e}")
                                    
                                    logger.info(
                                        f"🟢 POSITION OUVERTE (Auto): {direction} {symbol} | "
                                        f"Entry: {entry_price:.6f} | Size: {position_size:.2f} USDT (position.size={position.size:.2f}) | "
                                        f"SL: {position.sl:.6f} | TP: {position.tp:.6f} | "
                                        f"Lock maintenu jusqu'à la fin"
                                    )
                                    
                                    # Ne prendre que le premier setup valide - sortir immédiatement
                                    break

                                except PositionError as e:
                                    # Erreur position spécifique (position déjà active, sizing invalide, etc.)
                                    logger.error(f"❌ Erreur position lors ouverture auto pour {symbol}: {e}", exc_info=True)
                                except OrderExecutionError as e:
                                    # Erreur lors de l'exécution de l'ordre d'ouverture
                                    logger.error(f"❌ Erreur exécution ordre ouverture pour {symbol}: {e}", exc_info=True)
                                except ValidationError as e:
                                    # Erreur validation des paramètres (setup invalide)
                                    logger.error(f"❌ Erreur validation setup pour {symbol}: {e}", exc_info=True)
                                except MarketDataError as e:
                                    # Erreur données marché (prix invalide, ATR manquant, etc.)
                                    logger.error(f"❌ Erreur données marché pour {symbol}: {e}", exc_info=True)
                                except Exception as e:
                                    # Erreur inattendue lors de l'ouverture de position
                                    logger.error(f"❌ Erreur inattendue ouverture position auto pour {symbol}: {type(e).__name__}: {e}", exc_info=True)
                                    await add_log('ERROR', 'Erreur ouverture position', f"{symbol}: {str(e)}")
                                    continue
                else:
                    # 🔥 FIX: Log détaillé quand aucun setup n'est trouvé
                    # Note: rejection_reasons est défini dans le bloc if scan_tasks ci-dessus
                    await add_log('INFO', 'Aucun setup', 
                        'Aucun setup valide trouvé sur les paires analysées')
    
    # 🔥 FIX: Le lock scanner_lock est automatiquement libéré ici (fin du bloc async with)


async def scan_pair_for_setup(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Scanner une paire pour trouver un setup de trading valide.

    Cette fonction effectue une analyse technique complète d'une paire de trading
    en utilisant plusieurs indicateurs (RSI, MACD, ADX, Bollinger Bands, etc.)
    et patterns (breakout, S/R, divergence, chandeliers japonais) pour identifier
    des opportunités de trading.

    Le processus inclut:
    1. Calcul des indicateurs techniques sur 1m et 5m
    2. Analyse de la tendance sur le timeframe configuré
    3. Détection de patterns (breakout, S/R, wicks, divergences)
    4. Détection de patterns chandeliers (engulfing, hammer, doji, etc.)
    5. Scoring pondéré basé sur les conditions validées
    6. Filtrage par corrélation avec positions actives
    7. Logging dans PostgreSQL (via DataLogger)

    Args:
        symbol: Symbole de la paire à analyser (ex: 'BTC/USDT', 'ETH/USDT')

    Returns:
        Dict contenant l'analyse complète si un setup est trouvé:
            - setup_found: bool
            - direction: 'LONG' ou 'SHORT'
            - score: float (score pondéré)
            - conditions_met: int (nombre de conditions validées)
            - indicators_1m/5m: Dict des indicateurs
            - patterns: Dict des patterns détectés
            - entry: float (prix d'entrée recommandé)
            - tp/sl: float (take profit et stop loss)
        None si aucun setup valide n'est trouvé

    Side Effects:
        - Initialise les instances globales si nécessaire
        - Log l'analyse dans PostgreSQL (DataLogger)
        - Peut émettre des warnings si l'analyzer n'est pas disponible

    Note:
        Le filtrage ML n'est pas appliqué ici mais dans le callback appelant
    """
    init_instances()
    
    analyzer_inst = state.get_analyzer()
    if not analyzer_inst:
        logger.warning(f"Analyzer non disponible pour {symbol}")
        return None
    
    # 🔥 PHASE 3: Mesurer la durée du scan
    scan_start_time = time.time()
    
    # 🔥 FIX: Initialiser last_ml_confidence pour le logging PostgreSQL
    # Note: Cette valeur reste None car le filtre ML s'exécute dans le callback APRÈS cette fonction
    last_ml_confidence = None
    
    # 🔥 FIX: Ajouter log pour voir que l'analyse démarre
    logger.info(f"🔍 Analyse {symbol}...")
    
    try:
        # 🔥 FIX: Récupérer paramètres depuis TRADING_CONFIG
        from config import TRADING_CONFIG
        use_confluence = TRADING_CONFIG.get('use_confluence', False)
        volume_multiplier = TRADING_CONFIG.get('volume_multiplier', 1.0)
        trend_timeframe = TRADING_CONFIG.get('trend_timeframe', '15m')
        
        # 🔥 FIX: Calculer trend_data avec le timeframe configuré
        trend_data = await analyzer_inst.calculate_trend_data(symbol, trend_timeframe)
        if trend_data:
            logger.debug(f"📊 {symbol}: Trend {trend_timeframe} = {trend_data['trend']} ({trend_data['strength']}, bonus={trend_data['bonus']})")
        
        # 🔥 PHASE 6: Récupérer positions actives pour Correlation Filter
        pos_mgr = state.get_position_manager()
        active_positions = []
        if pos_mgr and pos_mgr.active_position:
            active_positions = [pos_mgr.active_position.symbol]
        
        # 🔥 FIX: Analyser avec retour de raison si pas de setup + paramètres configurables
        analysis = await analyzer_inst.analyze_pair(
            symbol, 
            trend_data=trend_data,  # 🔥 Utiliser trend_data calculé
            volume_multiplier=volume_multiplier,
            use_confluence=use_confluence,
            return_reason=True,
            active_positions=active_positions,  # 🔥 PHASE 6: Correlation Filter
            position_manager=pos_mgr  # 🔥 PHASE 6: Recovery Mode
        )
        
        # 🔥 FIX: Ajouter indicators_1m et indicators_5m à analysis IMMÉDIATEMENT après analyze_pair
        # pour qu'ils soient disponibles dans _last_setup
        if analysis and isinstance(analysis, dict):
            # Use helper functions to extract indicators (eliminates code duplication)
            from utils.indicators_helpers import build_indicators_from_analysis, count_non_null_values

            # Build indicators for both timeframes
            indicators_1m = build_indicators_from_analysis(analysis, '1m', logger)
            indicators_5m = build_indicators_from_analysis(analysis, '5m', logger)

            # Count non-null values for debugging
            indicators_1m_count = count_non_null_values(indicators_1m)
            indicators_5m_count = count_non_null_values(indicators_5m)

            logger.info(f"✅ Indicateurs extraits pour {symbol}: "
                       f"indicators_1m: {indicators_1m_count}/{len(indicators_1m)} valeurs, "
                       f"indicators_5m: {indicators_5m_count}/{len(indicators_5m)} valeurs")

            # Add indicators to analysis
            analysis['indicators_1m'] = indicators_1m
            analysis['indicators_5m'] = indicators_5m
        
        # Helper function to extract filter metrics
        def _extract_filter_metrics_main(analysis):
            """Extract filter metrics from analysis_1m and analysis_5m with correct suffixes"""
            if not analysis or not isinstance(analysis, dict):
                return {}
            
            filters = {}
            
            # Extract from analysis_1m with _1m suffix
            analysis_1m = analysis.get('analysis_1m', {})
            if analysis_1m and isinstance(analysis_1m, dict):
                filters.update({
                    'volume_filter_passed_1m': analysis_1m.get('volume_filter_passed'),
                    'snr_1m': analysis_1m.get('snr'),
                    'snr_passed_1m': analysis_1m.get('snr_passed'),
                    'breakout_distance_1m': analysis_1m.get('breakout_distance'),
                    'breakout_passed_1m': analysis_1m.get('breakout_passed'),
                    'wick_ratio_1m': analysis_1m.get('wick_ratio'),
                    'wick_passed_1m': analysis_1m.get('wick_passed'),
                    'atr_optimal_passed_1m': analysis_1m.get('atr_optimal_passed')
                })
            
            # Extract from analysis_5m with _5m suffix
            analysis_5m = analysis.get('analysis_5m', {})
            if analysis_5m and isinstance(analysis_5m, dict):
                filters.update({
                    'volume_filter_passed_5m': analysis_5m.get('volume_filter_passed'),
                    'snr_5m': analysis_5m.get('snr'),
                    'snr_passed_5m': analysis_5m.get('snr_passed'),
                    'breakout_distance_5m': analysis_5m.get('breakout_distance'),
                    'breakout_passed_5m': analysis_5m.get('breakout_passed'),
                    'wick_ratio_5m': analysis_5m.get('wick_ratio'),
                    'wick_passed_5m': analysis_5m.get('wick_passed'),
                    'atr_optimal_passed_5m': analysis_5m.get('atr_optimal_passed')
                })
            
            return filters
        
        # 🔥 PHASE 1: Logger le scan dans PostgreSQL si activé (comme dans scanner_loop.py)
        # Note: last_ml_confidence est initialisé plus haut (ligne 984) et mis à jour dans le filtre ML
        try:
            from core.callbacks.scanner_loop import get_pg_datalogger
            pg_datalogger = get_pg_datalogger()
            
            if pg_datalogger and pg_datalogger.enabled:
                # Calculer durée du scan
                scan_duration_ms = int((time.time() - scan_start_time) * 1000)
                eff_volume_multiplier = get_effective_value('volume_multiplier', symbol=symbol)
                if eff_volume_multiplier is None:
                    eff_volume_multiplier = volume_multiplier
                eff_min_score_required = get_effective_value('min_score_required', symbol=symbol)
                if eff_min_score_required is None:
                    eff_min_score_required = TRADING_CONFIG.get('min_score_required', 7.5)
                eff_optimal_atr_min_1m = get_effective_value('optimal_atr_min_1m', symbol=symbol)
                if eff_optimal_atr_min_1m is None:
                    eff_optimal_atr_min_1m = TRADING_CONFIG.get('optimal_atr_min_1m', 0.12)
                eff_optimal_atr_max_1m = get_effective_value('optimal_atr_max_1m', symbol=symbol)
                if eff_optimal_atr_max_1m is None:
                    eff_optimal_atr_max_1m = TRADING_CONFIG.get('optimal_atr_max_1m', 0.75)
                eff_optimal_atr_min_5m = get_effective_value('optimal_atr_min_5m', symbol=symbol)
                if eff_optimal_atr_min_5m is None:
                    eff_optimal_atr_min_5m = TRADING_CONFIG.get('optimal_atr_min_5m', 0.22)
                eff_optimal_atr_max_5m = get_effective_value('optimal_atr_max_5m', symbol=symbol)
                if eff_optimal_atr_max_5m is None:
                    eff_optimal_atr_max_5m = TRADING_CONFIG.get('optimal_atr_max_5m', 1.4)
                
                # Récupérer les données du scan de scalabilité depuis top_pairs
                scalability_data = {}
                # app_state est défini globalement dans main.py
                if app_state and app_state.get('top_pairs'):
                    for pair in app_state.get('top_pairs', []):
                        # 🔥 FIX: Normaliser symboles avant comparaison (BTC/USDT vs BTC/USDT:USDT)
                        pair_symbol = (pair.get('symbol') or '').split(':')[0]
                        lookup_symbol = (symbol or '').split(':')[0]
                        if pair_symbol == lookup_symbol:
                            spread_value = pair.get('spread') or pair.get('spread_pct')
                            book_depth = pair.get('bookDepth')
                            balance_score = pair.get('balanceScore')
                            bid_vol = pair.get('bidVol')
                            ask_vol = pair.get('askVol')
                            if book_depth in (None, 0) and bid_vol and ask_vol:
                                book_depth = bid_vol + ask_vol
                            imbalance = None
                            if bid_vol and ask_vol:
                                try:
                                    imbalance = bid_vol / ask_vol if ask_vol > 0 else None
                                except Exception:
                                    imbalance = None
                            
                            scalability_data = {
                                'spread': spread_value,
                                'spread_pct': spread_value,
                                'bookDepth': book_depth,
                                'book_depth': book_depth,
                                'balanceScore': balance_score,
                                'balance_score': balance_score,
                                'bidVol': bid_vol,
                                'askVol': ask_vol,
                                'orderbook_imbalance_ratio': imbalance,
                                'recent_volume': pair.get('recentVolume'),
                                'recentVolume': pair.get('recentVolume'),  # Alias
                                'vol5': pair.get('vol5'),
                                'vol15': pair.get('vol15'),
                                'scalability_score': pair.get('score'),
                                'score': pair.get('score')
                            }
                            logger.info(f"💹 DEBUG main.py: Scalability data trouvé pour {symbol}: spread={spread_value}, depth={book_depth}")
                            break
                
                # Fallback: utiliser les infos présentes dans l'analyse/best_setup
                if not scalability_data:
                    # DEBUG: Vérifier pourquoi scalability_data est vide
                    debug_info = ""
                    if not app_state:
                        debug_info = "app_state is None"
                    elif not app_state.get('top_pairs'):
                        debug_info = "top_pairs vide"
                    else:
                        debug_info = f"symbole non trouvé dans {len(app_state.get('top_pairs', []))} top_pairs"
                    
                    logger.debug(f"⚠️ DEBUG main.py: scalability_data vide pour {symbol} ({debug_info}), utilisation fallback depuis analysis")
                    analysis_obj = analysis or {}
                    orderbook_check = analysis_obj.get('orderbook_check') or {}
                    bid_value = orderbook_check.get('bid_value') or analysis_obj.get('bid_vol')
                    ask_value = orderbook_check.get('ask_value') or analysis_obj.get('ask_vol')
                    book_depth = None
                    if bid_value or ask_value:
                        bid_value = bid_value or 0
                        ask_value = ask_value or 0
                        book_depth = bid_value + ask_value
                    imbalance = None
                    if bid_value and ask_value:
                        try:
                            imbalance = bid_value / ask_value if ask_value > 0 else None
                        except Exception:
                            imbalance = None

                    scalability_data = {
                        'spread': analysis_obj.get('spread_pct') or analysis_obj.get('spread'),
                        'spread_pct': analysis_obj.get('spread_pct') or analysis_obj.get('spread'),
                        'bookDepth': book_depth,
                        'book_depth': book_depth,
                        'balanceScore': analysis_obj.get('orderbook_balance'),
                        'balance_score': analysis_obj.get('orderbook_balance'),
                        'bidVol': bid_value,
                        'askVol': ask_value,
                        'orderbook_imbalance_ratio': imbalance,
                        'recent_volume': analysis_obj.get('recent_volume'),
                        'recentVolume': analysis_obj.get('recent_volume'),
                        'vol5': analysis_obj.get('vol5'),
                        'vol15': analysis_obj.get('vol15'),
                        'scalability_score': analysis_obj.get('scalability_score'),
                        'score': analysis_obj.get('scalability_score')
                    }
                    logger.info(f"⚠️ DEBUG main.py: Scalability data depuis fallback pour {symbol}: spread={scalability_data.get('spread')}, depth={book_depth}")
                
                # Préparer les données du scan pour PostgreSQL
                # 🔥 FIX: Récupérer le prix avec fallbacks (comme pour SimplePGLogger)
                scan_price = None
                if analysis and isinstance(analysis, dict):
                    scan_price = analysis.get('price')
                
                # Si le prix n'est pas dans analysis, essayer de le récupérer depuis price_provider
                price_prov = state.get_price_provider()
                if scan_price is None and price_prov:
                    try:
                        price_result = await price_prov.get_price(symbol)
                        # FIX: Utiliser analysis au lieu de setup (setup n'est pas toujours défini)
                        scan_price = get_preferred_price(price_result, analysis.get('price') if analysis else None)
                    except MarketDataError as price_error:
                        # Erreur données marché (prix invalide, API)
                        logger.debug(f"⚠️ Erreur données marché pour {symbol}: {price_error}")
                    except NetworkError as price_error:
                        # Erreur réseau lors de la récupération du prix
                        logger.debug(f"⚠️ Erreur réseau récupération prix pour {symbol}: {price_error}")
                    except Exception as price_error:
                        # Erreur inattendue lors de la récupération du prix
                        logger.debug(f"⚠️ Impossible de récupérer le prix pour {symbol}: {type(price_error).__name__}: {price_error}")
                
                # Extraire la valeur numérique si scan_price est un dict
                if isinstance(scan_price, dict):
                    scan_price = get_preferred_price(scan_price)
                
                # Vérifier que scan_price est un nombre
                if scan_price is not None and not isinstance(scan_price, (int, float)):
                    try:
                        scan_price = float(scan_price)
                    except (ValueError, TypeError):
                        logger.warning(f"⚠️ Prix invalide pour {symbol}: {scan_price} (type: {type(scan_price)})")
                        scan_price = None

                ml_confidence_for_scan = last_ml_confidence
                if ml_confidence_for_scan is not None:
                    try:
                        ml_confidence_for_scan = float(ml_confidence_for_scan)
                        if ml_confidence_for_scan <= 1:
                            ml_confidence_for_scan = ml_confidence_for_scan * 100
                        ml_confidence_for_scan = round(ml_confidence_for_scan, 1)
                    except Exception:
                        ml_confidence_for_scan = None
                
                scan_data = {
                    'scan_duration_ms': scan_duration_ms,
                    'market_data': {
                        'price': scan_price,
                        # 🔥 FIX: Utiliser scalability_data au lieu de analysis pour les métriques de scalabilité
                        'spread_pct': scalability_data.get('spread'),
                        'book_depth': scalability_data.get('bookDepth'),
                        'balance_score': scalability_data.get('balanceScore'),
                        'bid_vol': scalability_data.get('bidVol'),
                        'ask_vol': scalability_data.get('askVol'),
                        # Calculer imbalance ratio si bid/ask disponibles
                        'orderbook_imbalance_ratio': (
                            scalability_data.get('bidVol') / scalability_data.get('askVol')
                            if scalability_data.get('askVol') and scalability_data.get('askVol') > 0
                            else None
                        ),
                        # Paramètres du scan de scalabilité
                        'recent_volume': scalability_data.get('recent_volume'),
                        'recentVolume': scalability_data.get('recent_volume'),  # Alias
                        'vol5': scalability_data.get('vol5'),
                        'vol15': scalability_data.get('vol15'),
                        'scalability_score': scalability_data.get('scalability_score'),
                        'score': scalability_data.get('scalability_score'),  # Alias
                    },
                    # Ajouter aussi au niveau racine pour les fallbacks
                    'price': scan_price,  # 🔥 FIX: Ajouter le prix au niveau racine pour les fallbacks
                    'recent_volume': scalability_data.get('recent_volume'),
                    'recentVolume': scalability_data.get('recent_volume'),  # Alias
                    'vol5': scalability_data.get('vol5'),
                    'vol15': scalability_data.get('vol15'),
                    'scalability_score': scalability_data.get('scalability_score'),
                    'score': scalability_data.get('scalability_score'),  # Alias
                    'indicators_1m': analysis.get('indicators_1m', {}) if analysis else {},
                    'indicators_5m': analysis.get('indicators_5m', {}) if analysis else {},
                    'filters': _extract_filter_metrics_main(analysis),
                    'scores': {
                        'score_1m': analysis.get('score_1m') if analysis else None,
                        'score_5m': analysis.get('score_5m') if analysis else None,
                        'score_total': analysis.get('totalScore') or analysis.get('score_total') if analysis else None,
                        'score_long_1m': analysis.get('long_score') if analysis else None,
                        'score_short_1m': analysis.get('short_score') if analysis else None,
                        'score_long_5m': analysis.get('long_score') if analysis else None,
                        'score_short_5m': analysis.get('short_score') if analysis else None,
                    },
                    'patterns': {
                        'pattern_1m': analysis.get('pattern_1m') if analysis else None,
                        'pattern_multi_1m': analysis.get('pattern_multi_1m') if analysis else None,
                        'pattern_5m': analysis.get('pattern_5m') if analysis else None,
                        'pattern_multi_5m': analysis.get('pattern_multi_5m') if analysis else None,
                    },
                    'trend_bonus': analysis.get('trend_bonus') if analysis else 0,
                    'divergence_bonus': analysis.get('divergence_bonus') if analysis else 0,
                    'divergence_detected': analysis.get('divergence_detected') if analysis else False,
                    'divergence_type': analysis.get('divergence_type') if analysis else None,
                    'use_confluence': use_confluence,
                    'confluence_met': analysis.get('confluence_met') if analysis else False,
                    'timeframes_aligned': analysis.get('timeframes_aligned') if analysis else False,
                    'trend_timeframe': trend_timeframe,
                    'trend_direction': trend_data.get('trend') if trend_data else None,  # 'trend' pas 'direction'
                    'trend_strength': None,  # trend_data.get('strength') est une chaîne ('STRONG', 'MODERATE', 'NONE'), pas un FLOAT
                    'reject_reason': analysis.get('reason') if analysis else None,
                    'reject_reason_category': analysis.get('reject_category') if analysis else None,
                    'is_opportunity': bool(analysis and 'direction' in analysis and ('entry' in analysis or 'price' in analysis)),
                    'opportunity_direction': analysis.get('direction') if analysis and 'direction' in analysis else None,
                    # 🔥 ML Confidence: confiance réelle du modèle (si disponible)
                    'ml_confidence': ml_confidence_for_scan,
                    'params_snapshot': {
                        'volume_multiplier': eff_volume_multiplier,
                        'use_confluence': use_confluence,
                        'trend_timeframe': trend_timeframe,
                        'min_score_required': eff_min_score_required,
                        'min_conditions': TRADING_CONFIG.get('min_conditions', 6),
                        'use_weighted_scoring': TRADING_CONFIG.get('use_weighted_scoring', True),
                        'snr_threshold': TRADING_CONFIG.get('snr_threshold', 0.25),
                        'breakout_threshold': TRADING_CONFIG.get('breakout_threshold', 0.35),
                        'wick_ratio_max': TRADING_CONFIG.get('wick_ratio_max', 2.8),
                        'optimal_atr_min_1m': eff_optimal_atr_min_1m,
                        'optimal_atr_max_1m': eff_optimal_atr_max_1m,
                        'optimal_atr_min_5m': eff_optimal_atr_min_5m,
                        'optimal_atr_max_5m': eff_optimal_atr_max_5m,
                        'use_breakout': TRADING_CONFIG.get('use_breakout', True),
                        'use_snr': TRADING_CONFIG.get('use_snr', True),
                        'use_wick': TRADING_CONFIG.get('use_wick', True),
                        'use_divergence': TRADING_CONFIG.get('use_divergence', True),
                        # OPT #15-19 : filtres avancés
                        'use_anti_whipsaw': TRADING_CONFIG.get('use_anti_whipsaw'),
                        'whipsaw_lookback': TRADING_CONFIG.get('whipsaw_lookback'),
                        'whipsaw_threshold_pct': TRADING_CONFIG.get('whipsaw_threshold_pct'),
                        'whipsaw_max_alternations': TRADING_CONFIG.get('whipsaw_max_alternations'),
                        'use_retest_confirmation': TRADING_CONFIG.get('use_retest_confirmation'),
                        'retest_tolerance_pct': TRADING_CONFIG.get('retest_tolerance_pct'),
                        'retest_timeout_seconds': TRADING_CONFIG.get('retest_timeout_seconds'),
                        'use_cooldown': TRADING_CONFIG.get('use_cooldown'),
                        'cooldown_seconds': TRADING_CONFIG.get('cooldown_seconds'),
                        'cooldown_same_symbol': TRADING_CONFIG.get('cooldown_same_symbol'),
                        'use_candle_close': TRADING_CONFIG.get('use_candle_close'),
                        'candle_close_threshold_seconds': TRADING_CONFIG.get('candle_close_threshold_seconds'),
                        'use_momentum_continuity': TRADING_CONFIG.get('use_momentum_continuity'),
                        'momentum_lookback': TRADING_CONFIG.get('momentum_lookback'),
                        'use_micro_confirmation': TRADING_CONFIG.get('use_micro_confirmation'),
                        'micro_confirmation_delay_ms': TRADING_CONFIG.get('micro_confirmation_delay_ms'),
                    }
                }
                
                # 🔥 SPRINT 1: Ajouter le contexte Market Regime au scan
                try:
                    from core.market_regime_selector import get_regime_selector
                    regime_selector = get_regime_selector()
                    regime_status = regime_selector.get_status()
                    scan_data['market_regime'] = regime_status.get('current_regime')
                    scan_data['market_regime_avg_atr'] = regime_status.get('avg_atr')
                    scan_data['market_regime_avg_adx'] = regime_status.get('avg_adx')
                except ImportError as e:
                    # Module regime selector non disponible
                    logger.debug(f"Module regime selector non disponible: {e}")
                except MarketDataError as e:
                    # Erreur données marché (ATR/ADX invalides)
                    logger.debug(f"⚠️ Erreur données marché régime pour scan: {e}")
                except Exception as e:
                    # Erreur inattendue lors de la récupération du régime
                    logger.debug(f"⚠️ Impossible de récupérer régime pour scan: {type(e).__name__}: {e}")
                
                # Logger le scan (mode batch par défaut)
                # 🔥 FIX: Utiliser version async non-bloquante pour ne pas freeze l'event loop
                logger.info(f"📝 Appel log_scan_async() pour {symbol} (main.py)")
                scan_id = await pg_datalogger.log_scan_async(symbol, scan_data, use_batch=True)
                logger.info(f"✅ log_scan_async() terminé pour {symbol} (scan_id={scan_id})")
                
                # Si c'est une opportunité, logger aussi dans opportunities
                if scan_data['is_opportunity'] and analysis:
                    # 🔍 DEBUG: Logger les clés disponibles dans analysis
                    logger.info(f"🔍 DEBUG main.py: analysis keys pour {symbol}: {list(analysis.keys())[:20]}")
                    
                    condition_list = analysis.get('condition_types', []) or analysis.get('signals', [])
                    
                    # 🔥 FIX: Les clés correctes sont 'long_score' et 'short_score', pas 'score_long_1m'
                    score_long = analysis.get('long_score')
                    score_short = analysis.get('short_score')
                    
                    # Fallback: essayer aussi les anciennes clés si les nouvelles ne sont pas présentes
                    if score_long is None:
                        score_long = analysis.get('score_long_1m') or analysis.get('score_long_5m')
                    if score_short is None:
                        score_short = analysis.get('score_short_1m') or analysis.get('score_short_5m')
                    
                    # Fallback: chercher dans scan_data['scores'] si toujours None
                    if score_long is None and 'scores' in scan_data:
                        score_long = scan_data['scores'].get('score_long_1m') or scan_data['scores'].get('score_long_5m')
                    if score_short is None and 'scores' in scan_data:
                        score_short = scan_data['scores'].get('score_short_1m') or scan_data['scores'].get('score_short_5m')
                    
                    min_required = scan_data['params_snapshot'].get('min_score_required')
                    trend_bonus = scan_data.get('trend_bonus')
                    # 🔥 FIX: divergence_bonus et setup_reason sont maintenant dans l'objet analysis
                    divergence_bonus = analysis.get('divergence_bonus')
                    setup_reason = analysis.get('setup_reason')
                    
                    opportunity_data = {
                        'status': 'PENDING',
                        'direction': analysis.get('direction'),
                        'setup_score': analysis.get('score_total') or analysis.get('totalScore'),
                        'score_long': score_long,
                        'score_short': score_short,
                        'score_min_required': min_required,
                        'trend_bonus': trend_bonus,
                        'divergence_bonus': divergence_bonus,
                        'conditions_matched': condition_list,
                        'condition_count': len(condition_list),
                        'setup_reason': setup_reason,
                        'entry_suggested': analysis.get('entry') or analysis.get('price'),
                        'tp_suggested': analysis.get('tp'),
                        'sl_suggested': analysis.get('sl'),
                        'tp_sl_mode': analysis.get('tp_sl_mode', 'FIXE'),
                        # Legacy
                        'entry_price': analysis.get('entry') or analysis.get('price'),
                        'tp_price': analysis.get('tp'),
                        'sl_price': analysis.get('sl'),
                        'size_usdt': None,
                        'risk_usdt': None,
                        'reward_risk_ratio': None,
                    }
                    # 🔥 FIX: Utiliser version async non-bloquante pour ne pas freeze l'event loop
                    logger.info(f"📝 Appel log_opportunity_async() pour {symbol} (main.py)")
                    await pg_datalogger.log_opportunity_async(
                        scan_id or 0,  # 0 = temporaire, sera mis à jour lors du flush
                        symbol, 
                        opportunity_data,
                        use_batch=True
                    )
                    logger.info(f"✅ log_opportunity_async() terminé pour {symbol}")
        except ImportError as e:
            # Module PostgreSQL non disponible
            logger.debug(f"Module PostgreSQL non disponible: {e}")
        except DatabaseError as e:
            # Erreur database lors du logging
            logger.error(f"❌ Erreur DB logging PostgreSQL pour {symbol}: {e}", exc_info=True)
        except ValidationError as e:
            # Erreur validation des données de scan/opportunity
            logger.warning(f"⚠️ Erreur validation données PostgreSQL pour {symbol}: {e}")
        except Exception as e:
            # Erreur inattendue lors du logging PostgreSQL
            logger.error(f"❌ Erreur inattendue logging PostgreSQL pour {symbol}: {type(e).__name__}: {e}", exc_info=True)
        
        # 🔥 FIX: Envoyer événement SocketIO pour mettre à jour le compteur de validation
        # Un setup valide = validé (true), pas de setup = non validé (false)
        is_valid = False
        if analysis:
            if isinstance(analysis, dict) and 'reason' in analysis:
                # C'est une raison de rejet, pas un setup
                reason = analysis.get('reason', 'Inconnu')
                logger.info(f"❌ {symbol}: Pas de setup - {reason}")
                is_valid = False
            else:
                # C'est un vrai setup
                logger.info(f"✅ {symbol}: Setup trouvé - {analysis.get('direction', 'N/A')} - {len(analysis.get('signals', []))} conditions")
                is_valid = True
        else:
            # Si analysis est None, c'est que les deux timeframes ont retourné None
            # 🔥 FIX: Envoyer le warning au frontend via add_log (logger.warning est capturé par WebSocketLogHandler, donc on évite le doublon)
            # 🔥 FIX: Corriger le message dupliqué (le symbole était répété deux fois)
            try:
                await add_log('WARNING', 'Analyse retournée None',
                    f"{symbol}: Analyse retournée None - Vérifier les erreurs dans analyze_timeframe. Vérifier que le prix est disponible et que les indicateurs peuvent être calculés.")
            except WebSocketError as log_err:
                # Erreur WebSocket lors de l'envoi du log
                logger.debug(f"⚠️ Erreur WebSocket envoi log frontend: {log_err}")
            except Exception as log_err:
                # Erreur inattendue lors de l'envoi du log
                logger.debug(f"⚠️ Impossible d'envoyer log au frontend: {type(log_err).__name__}: {log_err}")
            is_valid = False
        
        # Envoyer événement pour mettre à jour le compteur
        ws_mgr = state.get_ws_manager()
        if ws_mgr:
            await ws_mgr.emit('volume_validation_update', {
                'symbol': symbol,
                'valid': is_valid
            })
        
        if analysis and not (isinstance(analysis, dict) and 'reason' in analysis):
            return analysis
        return None

    except MarketDataError as e:
        # Erreur données marché (prix invalide, indicateurs manquants, etc.)
        logger.error(f"❌ Erreur données marché scan {symbol}: {e}", exc_info=True)
    except NetworkError as e:
        # Erreur réseau lors du scan
        logger.error(f"❌ Erreur réseau scan {symbol}: {e}", exc_info=True)
    except ValidationError as e:
        # Erreur validation des paramètres de scan
        logger.error(f"❌ Erreur validation scan {symbol}: {e}", exc_info=True)
    except Exception as e:
        # Erreur inattendue lors du scan
        logger.error(f"❌ Erreur inattendue scan {symbol}: {type(e).__name__}: {e}", exc_info=True)
        # Envoyer événement pour erreur (non validé)
        ws_mgr = state.get_ws_manager()
        if ws_mgr:
            await ws_mgr.emit('volume_validation_update', {
                'symbol': symbol,
                'valid': False
            })
        return None


async def position_check_loop_callback() -> None:
    """
    Callback appelé périodiquement pour surveiller et gérer la position active.

    Cette fonction est le gestionnaire principal des positions ouvertes. Elle est
    exécutée toutes les 2 secondes (check_interval) pour surveiller l'évolution
    de la position et décider si elle doit être fermée.

    Le processus de surveillance inclut:
    1. Vérification de l'existence d'une position active
    2. Récupération du prix actuel en temps réel
    3. Vérification des conditions de sortie:
       - Take Profit (TP) atteint
       - Stop Loss (SL) touché
       - Break-even activé (si configuration)
       - Trailing stop activé (si configuration)
       - Timeout de position
    4. Fermeture automatique si condition validée
    5. Mise à jour des statistiques et logs

    Side Effects:
        - Initialise les instances globales
        - Peut fermer la position active
        - Met à jour app_state['active_position']
        - Log dans PostgreSQL et trade_history
        - Émet des événements WebSocket vers le frontend
        - Met à jour les statistiques de trading

    Note:
        - Ne fait rien si aucune position n'est active
        - Gère les erreurs de connexion au price provider
        - Utilise get_preferred_price() pour gérer les différents formats de prix
    """
    init_instances()
    
    # Vérifier si on a une position active
    pos_mgr = state.get_position_manager()
    if not pos_mgr or not pos_mgr.active_position:
        return
    
    price_prov = state.get_price_provider()
    if not price_prov:
        return
    
    try:
        # 🔥 FIX: Import TRADING_CONFIG pour position_update
        from config import TRADING_CONFIG
        from datetime import datetime  # 🔥 FIX: Import au début du try pour éviter UnboundLocalError
        
        # Récupérer prix actuel
        symbol = pos_mgr.active_position.symbol
        current_price_data = await price_prov.get_price(symbol)

        position_fallback_price = getattr(pos_mgr.active_position, 'current_price', None)
        if position_fallback_price is None or position_fallback_price <= 0:
            position_fallback_price = getattr(pos_mgr.active_position, 'entry', None)

        current_price = get_preferred_price(current_price_data, fallback=position_fallback_price)
        if current_price is None or current_price <= 0:
            logger.warning(f"⚠️ Prix non disponible pour {symbol} - fallback sur entry")
            current_price = float(getattr(pos_mgr.active_position, 'entry', 0) or 0)
            if current_price <= 0:
                return
        
        # Check position (renvoie None ou raison de fermeture)
        close_reason = await pos_mgr.check_position(current_price)

        # 🔥 FIX SL_EXCHANGE: Si le bot détecte un SL interne, vérifier si c'est en fait un SL Exchange
        live_ord_mgr = state.get_live_order_manager()
        if close_reason == 'SL' and live_ord_mgr and hasattr(live_ord_mgr, 'bypass_client') and live_ord_mgr.bypass_client:
            try:
                # Vérifier si un ordre SL a été exécuté récemment sur l'exchange
                from trading.live_order_manager_futures import run_async_safely
                bypass_symbol = pos_mgr.active_position.symbol.replace('/', '_').replace(':USDT', '')
                
                # Récupérer l'historique récent (dernier ordre)
                order_history = run_async_safely(
                    live_ord_mgr.bypass_client.get_order_history(
                        symbol=bypass_symbol,
                        page_size=3  # Juste les derniers ordres
                    )
                )
                
                if order_history and 'data' in order_history:
                    orders = order_history.get('data', [])
                    for order in orders:
                        # Catégorie 2 = SL/TP trigger sur MEXC
                        # Vérifier si c'est un ordre de réduction (close) exécuté récemment (< 30s)
                        is_sl_trigger = order.get('category') == 2 or order.get('type') == 3  # STOP_MARKET
                        state_filled = order.get('state') == 3  # FILLED
                        
                        if is_sl_trigger and state_filled:
                            # Vérifier le timestamp (si dispo) ou assumer que c'est le dernier
                            logger.warning(f"🛑 SL détecté par le bot, mais un ordre SL Exchange a été trouvé ! Correction -> SL_EXCHANGE")
                            close_reason = "SL_EXCHANGE"
                            
                            # Tenter de récupérer le prix de fill réel
                            fill_price = order.get('dealAvgPrice') or order.get('price')
                            if fill_price and float(fill_price) > 0:
                                current_price = float(fill_price) # Utiliser le vrai prix d'exécution
                            break
            except Exception as e:
                logger.debug(f"⚠️ Erreur vérification SL Exchange lors du SL interne: {e}")
        
        # 🔥 NOUVEAU: Vérifier si la position a été fermée par MEXC (SL Exchange)
        # On vérifie toutes les 5 secondes pour réactivité accrue
        live_ord_mgr = state.get_live_order_manager()
        if not close_reason and live_ord_mgr and hasattr(live_ord_mgr, 'bypass_client') and live_ord_mgr.bypass_client:
            import time
            last_mexc_check = getattr(pos_mgr, '_last_mexc_sync_check', 0)
            if time.time() - last_mexc_check > 5:  # Vérifier toutes les 5 secondes
                pos_mgr._last_mexc_sync_check = time.time()
                try:
                    from trading.live_order_manager_futures import run_async_safely
                    bypass_symbol = pos_mgr.active_position.symbol.replace('/', '_').replace(':USDT', '')
                    mexc_positions = run_async_safely(
                        live_ord_mgr.bypass_client.get_open_positions(symbol=bypass_symbol)
                    )
                    
                    # Si aucune position MEXC mais le bot pense en avoir une → Position fermée
                    if mexc_positions is not None and len(mexc_positions) == 0:
                        # 🔥 FIX: Vérifier si c'est vraiment le SL MEXC qui a été touché
                        # en comparant le prix actuel avec le SL MEXC calculé
                        sl_bot = pos_mgr.active_position.sl
                        entry = pos_mgr.active_position.entry
                        direction = pos_mgr.active_position.direction
                        
                        # Calculer le SL MEXC selon le mode TP/SL
                        from config import TRADING_CONFIG
                        tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
                        
                        if tp_sl_mode == 'FIXE':
                            # Mode FIXE : SL MEXC = SL bot - 0.05%
                            SL_MEXC_OFFSET_PCT = 0.05  # 0.05% de marge
                            if direction == 'LONG':
                                sl_mexc = sl_bot * (1 - SL_MEXC_OFFSET_PCT / 100)
                                # SL MEXC touché si prix <= sl_mexc
                                is_sl_mexc_touched = current_price <= sl_mexc
                            else:  # SHORT
                                sl_mexc = sl_bot * (1 + SL_MEXC_OFFSET_PCT / 100)
                                # SL MEXC touché si prix >= sl_mexc
                                is_sl_mexc_touched = current_price >= sl_mexc
                        else:
                            # Mode ATR : SL MEXC = SL bot × 1.1 (10% de marge)
                            SL_MEXC_MARGIN = 1.1
                            if direction == 'LONG':
                                sl_distance_pct = abs(entry - sl_bot) / entry if entry > 0 else 0
                                sl_mexc = entry * (1 - sl_distance_pct * SL_MEXC_MARGIN)
                                # SL MEXC touché si prix <= sl_mexc
                                is_sl_mexc_touched = current_price <= sl_mexc
                            else:  # SHORT
                                sl_distance_pct = abs(sl_bot - entry) / entry if entry > 0 else 0
                                sl_mexc = entry * (1 + sl_distance_pct * SL_MEXC_MARGIN)
                                # SL MEXC touché si prix >= sl_mexc
                                is_sl_mexc_touched = current_price >= sl_mexc
                        
                        if is_sl_mexc_touched:
                            # 🔥 FIX: Récupérer le vrai prix de fill depuis l'historique MEXC
                            try:
                                order_history = run_async_safely(
                                    live_ord_mgr.bypass_client.get_order_history(
                                        symbol=bypass_symbol,
                                        page_size=5
                                    )
                                )
                                if order_history and 'data' in order_history:
                                    orders = order_history.get('data', [])
                                    for order in orders:
                                        # Chercher un ordre SL récent (dans les 60 dernières secondes)
                                        if order.get('category') == 2:  # SL order
                                            fill_price = order.get('dealAvgPrice') or order.get('price')
                                            if fill_price and float(fill_price) > 0:
                                                current_price = float(fill_price)
                                                logger.info(f"📊 Prix de fill SL MEXC récupéré: {current_price}")
                                                break
                            except Exception as hist_err:
                                logger.debug(f"⚠️ Impossible de récupérer historique ordres: {hist_err}")
                            
                            logger.warning(
                                f"🛑 SL MEXC TOUCHÉ: Position {pos_mgr.active_position.symbol} fermée par exchange | "
                                f"Prix fill: {current_price} | SL MEXC: {sl_mexc:.6f}"
                            )
                            close_reason = "SL_EXCHANGE"
                        else:
                            # Position fermée mais pas par SL MEXC → probablement race condition
                            # Le bot a fermé la position mais la vérification arrive après
                            logger.info(
                                f"📋 Position {pos_mgr.active_position.symbol} fermée (sync MEXC) | "
                                f"Prix: {current_price} | SL MEXC: {sl_mexc:.6f} (non touché)"
                            )
                            # Ne pas marquer comme SL_EXCHANGE, laisser le bot gérer normalement
                except Exception as e:
                    logger.debug(f"⚠️ Impossible de vérifier sync MEXC: {e}")
        
        # 🔥 FIX: Émettre position_update même si pas de fermeture (pour affichage frontend)
        if not close_reason:
            # Utiliser _emit_position_update qui inclut next_event
            pos_mgr = state.get_position_manager()
            position = pos_mgr.active_position if pos_mgr else None
            if position:
                try:
                    from core.callbacks.position_check_loop import _emit_position_update
                    await _emit_position_update(position, current_price)
                except Exception as e:
                    logger.error(f"❌ Erreur émission position_update avec next_event: {e}")
        
        if close_reason:
            # Position fermée
            # 🔥 FIX: Utiliser le lock pour synchroniser la fermeture
            pos_lock = state.lock("position")
            async with pos_lock:
                pos_mgr = state.get_position_manager()
                if not pos_mgr or not pos_mgr.active_position:
                    return
                result = pos_mgr.close_position(exit_price=current_price, reason=close_reason)
                state.set_active_position(None)
                # 🔥 FIX: Reset compteur d'échecs après fermeture réussie
                state.reset_close_failure()
                
                # 🔥 PHASE 4: Ajouter à l'historique et sauvegarder
                if result:
                    result['timestamp'] = datetime.now().isoformat()
                    # 🔥 FIX: Utiliser add_trade pour upsert sécurisé
                    state.add_trade(result)
                    save_trade_history()
                
                # 🔥 FIX: Désactiver callback WebSocket si position fermée
                price_prov = state.get_price_provider()
                if price_prov:
                    price_prov.set_socketio_callback(None, None)
                    # 🔥 FIX SL MISMATCH: Désactiver callback SL temps réel
                    price_prov.set_sl_check_callback(None)
                
                # 🔥 FIX SL MISMATCH V2: Annuler tâche SL en attente
                closed_symbol = result.get('symbol') if result else None
                if closed_symbol:
                    cancel_pending_sl_task(closed_symbol)
                
                # 🔥 FIX: Log pour debug
                logger.info(
                    f"🔒 Position fermée avec lock: {close_reason} | "
                    f"state.active_position=None, "
                    f"position_manager.active_position={pos_mgr.active_position}"
                )
            
            await add_log('INFO', 'Position fermée', f"{close_reason} - PnL: {result.get('pnl_usdt', 0):.2f} USDT")
            ws_mgr = state.get_ws_manager()
            if ws_mgr:
                await ws_mgr.emit('position_closed', result)
            
            # 🔥 FIX: Émettre stats_update après fermeture de position pour synchronisation temps réel
            try:
                from core.callbacks.position_check_loop import _emit_stats_update
                await _emit_stats_update()
            except Exception as e:
                logger.error(f"❌ Erreur émission stats_update: {e}")
            
            # 🔥 JOUR 5: Métriques
            if get_metrics_collector:
                metrics = get_metrics_collector()
                if metrics:
                    metrics.positions_closed += 1
                    if result.get('pnl_usdt', 0) > 0:
                        metrics.trades_wins += 1
                    else:
                        metrics.trades_losses += 1
    
    except Exception as e:
        logger.error(f"Erreur dans position check loop: {e}")
        await add_log('ERROR', 'Erreur position check', str(e))
        
        # 🔥 FIX: Compteur d'échecs pour éviter boucle infinie
        # Si même position échoue 5+ fois, forcer fermeture locale
        pos_mgr = state.get_position_manager()
        if pos_mgr and pos_mgr.active_position:
            current_symbol = pos_mgr.active_position.symbol
            if state.close_failure_symbol == current_symbol:
                state.increment_close_failure()
            else:
                state.reset_close_failure()
                state.increment_close_failure(current_symbol)
            
            # Après 5 échecs consécutifs, forcer fermeture locale (paper close)
            if state.close_failure_count >= 5:
                logger.warning(
                    f"⚠️ FORCE CLOSE: {current_symbol} - {state.close_failure_count} échecs consécutifs | "
                    f"Fermeture locale forcée pour éviter boucle infinie"
                )
                try:
                    pos_lock = state.lock("position")
                    async with pos_lock:
                        pos_mgr = state.get_position_manager()
                        if not pos_mgr or not pos_mgr.active_position:
                            return
                        # Forcer fermeture sans ordre (skip_order=True)
                        result = pos_mgr.close_position(
                            exit_price=pos_mgr.active_position.entry,  # Utiliser prix d'entrée comme fallback
                            reason='FORCE_CLOSE',
                            skip_order=True  # Ne pas envoyer d'ordre à MEXC
                        )
                        state.set_active_position(None)
                        state.reset_close_failure()
                        if result:
                            result['timestamp'] = datetime.now().isoformat()
                            # 🔥 FIX: Utiliser add_trade pour upsert sécurisé
                            state.add_trade(result)
                            save_trade_history()
                        logger.info(f"✅ FORCE CLOSE réussi: {current_symbol}")
                        ws_mgr = state.get_ws_manager()
                        if ws_mgr:
                            await ws_mgr.emit('position_closed', result)
                except Exception as force_e:
                    logger.error(f"❌ FORCE CLOSE échoué: {force_e} - Réinitialisation position")
                    pos_mgr = state.get_position_manager()
                    if pos_mgr:
                        pos_mgr.active_position = None
                    state.set_active_position(None)
                    state.reset_close_failure()


async def scalability_refresh_loop_callback():
    """Callback appelé toutes les 90 secondes pour rafraîchir la liste des top pairs"""
    if not state.is_scanning:
        return
    
    # 🔥 FIX: Initialiser avant de vérifier position_manager
    init_instances()
    
    pos_mgr = state.get_position_manager()
    # 🔥 FIX: Ne pas rafraîchir si on a une position active (pour éviter interruption du TP partiel)
    if state.active_position or (pos_mgr and pos_mgr.active_position):
        logger.info("⏸️ Scalability refresh ignoré - Position active en cours")
        return
    
    scanner_inst = state.get_scanner()
    if not scanner_inst:
        return
    
    # 🔥 FIX: Vérifier si le scanner est déjà en cours pour éviter "Scanner déjà en cours"
    if scanner_inst.is_scanning:
        logger.debug("⏸️ Scalability refresh ignoré - Scanner déjà actif")
        return
    
    try:
        logger.info("[%s] INFO: Scalability refresh", datetime.now().strftime('%H:%M:%S'))
        
        top_pairs = await scanner_inst.scan_top_pairs(20)
        state.set_top_pairs(top_pairs)
        
        # 🔥 OPTIMISATION: Invalider cache quand top_pairs change
        if hasattr(app, '_top_pairs_cache'):
            app._top_pairs_cache.pop('top_pairs', None)
        
        logger.info("[%s] INFO: %d paires scalables", datetime.now().strftime('%H:%M:%S'), len(top_pairs))
        ws_mgr = state.get_ws_manager()
        if ws_mgr:
            await ws_mgr.emit('top_pairs_update', {'pairs': top_pairs})

        # 🔥 FIX CRITIQUE: Revérifier si position active APRÈS le scan (protection double)
        # Le scan peut prendre 20+ secondes, pendant lesquelles une position peut s'ouvrir
        # Si une position est ouverte pendant le scan, NE PAS toucher au WebSocket
        if state.active_position or (pos_mgr and pos_mgr.active_position):
            logger.info("⏸️ Mise à jour WebSocket ignorée - Position ouverte pendant le scan de scalabilité")
            return

        # 🔥 JOUR 3: Mettre à jour WebSocket avec les nouvelles top pairs (seulement si pas de position)
        price_prov = state.get_price_provider()
        if price_prov and top_pairs:
            # Arrêter l'ancien WebSocket
            await price_prov.stop_websocket()

            # Démarrer avec les nouvelles paires
            symbols = [p.get('symbol', '') for p in top_pairs[:30] if p.get('symbol')]
            if symbols:
                try:
                    await price_prov.start_websocket(symbols)
                    logger.info("[%s] INFO: WebSocket mis à jour - %d symboles", datetime.now().strftime('%H:%M:%S'), len(symbols))
                except Exception as e:
                    logger.warning(f"Erreur démarrage WebSocket: {e}")
    
    except Exception as e:
        logger.error(f"Erreur scalability refresh: {e}", exc_info=True)
        logger.error("[%s] ERROR: Erreur scalability refresh", datetime.now().strftime('%H:%M:%S'))


def init_instances() -> None:
    """
    Initialiser toutes les instances globales nécessaires au fonctionnement du bot.

    Cette fonction est le point d'initialisation central pour tous les composants
    du système de trading. Elle est appelée au démarrage et peut être rappelée
    pour s'assurer que toutes les instances sont disponibles.

    Composants initialisés:
    1. WebSocket Log Handler - Envoie les logs au frontend
    2. Analytics Database - Stockage PostgreSQL des métriques
    3. Scanner - Identification des paires prometteuses
    4. Analyzer - Analyse technique et détection de setups
    5. PositionManager - Gestion des positions actives
    6. Scheduler - Exécution périodique des tâches
    7. PriceProvider - Récupération des prix (REST + WebSocket)
    8. NotificationManager - Notifications Telegram
    9. LiveOrderManager - Exécution des ordres sur l'exchange
    10. MetricsCollector - Collecte des métriques système

    Side Effects:
        - Crée/initialise des variables globales (scanner, analyzer, etc.)
        - Configure le logger avec WebSocket handler
        - Crée le répertoire data/ si nécessaire
        - Initialise la base de données Analytics (PostgreSQL)
        - Réinitialise les statistiques de session
        - Configure le gestionnaire de notifications Telegram
        - Enregistre les métriques système (CPU, mémoire)

    Note:
        - Utilise des variables globales pour compatibilité legacy
        - Safe à appeler plusieurs fois (vérifie si déjà initialisé)
        - Gère les erreurs d'initialisation individuellement
        - Certains composants sont optionnels (Telegram, ML, etc.)

    Raises:
        Aucune exception n'est propagée - les erreurs sont loggées mais
        ne bloquent pas le démarrage du système
    """
    # 🔥 SPRINT 2.1: Use StateManager instead of global variables
    # No more global declarations - all managed by state
    
    # 🔥 FIX: Configurer le logger avec WebSocket handler pour envoyer les logs au frontend
    try:
        from utils.logger import WebSocketLogHandler
        root_logger = logging.getLogger()
        # Vérifier si le handler WebSocket existe déjà
        has_ws_handler = any(isinstance(h, WebSocketLogHandler) for h in root_logger.handlers)
        ws_mgr = state.get_ws_manager()
        if not has_ws_handler and ws_mgr:
            ws_handler = WebSocketLogHandler()
            ws_handler.set_ws_manager(ws_mgr)
            ws_handler.setLevel(logging.INFO)
            # Ne pas formater (garder le message brut avec emojis)
            ws_handler.setFormatter(logging.Formatter('%(message)s'))
            root_logger.addHandler(ws_handler)
            logger.info("✅ WebSocket log handler configuré")
    except Exception as e:
        logger.debug(f"Impossible de configurer WebSocket log handler: {e}")
    
    # 🔥 ARCHITECTURE V2: Initialiser Analytics DB
    if not state.get_analytics_db() and AnalyticsDatabase:
        from config import ANALYTICS_DB_PATH
        import time
        
        # Créer dossier data/ si nécessaire
        os.makedirs(os.path.dirname(ANALYTICS_DB_PATH) if os.path.dirname(ANALYTICS_DB_PATH) else "data", exist_ok=True)
        
        # 🔥 ARCHITECTURE V2: AnalyticsDatabase s'initialise automatiquement dans __init__
        try:
            # Récupérer port instance pour multi-instances
            port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
            db = AnalyticsDatabase(db_path=ANALYTICS_DB_PATH, instance_port=port)
            state.set_analytics_db(db)
            # La DB est déjà initialisée dans __init__ (via _init_database())
            logger.info(f"✅ Analytics DB prête: {ANALYTICS_DB_PATH}")
            
            # 🔥 FIX: Réinitialiser les stats au démarrage du bot (AVANT le scan)
            if db:
                try:
                    # Vider tous les trades de la base de données pour remettre les stats à zéro
                    db.clear_all_trades()
                    # Réinitialiser state stats
                    state.update_stats(total_trades=0, wins=0, losses=0)
                    state.set_trade_history([])
                    logger.info("✅ Stats réinitialisées au démarrage (base de données vidée)")
                except Exception as e:
                    logger.warning(f"⚠️ Impossible de réinitialiser les stats: {e}")
        except Exception as e:
            logger.error(f"❌ Erreur init Analytics DB: {e}")
            state.set_analytics_db(None)
        
        # Générer session ID unique (déjà géré par StateManager)
        logger.info(f"📝 Session ID: {state.session_id}")
        
        # Injecter Analytics DB dans API routes
        if set_analytics_db and state.get_analytics_db():
            set_analytics_db(state.get_analytics_db())
        
        # 🔥 PHASE 1: Initialiser PostgreSQL DataLogger si activé
        pg_datalogger = None
        try:
            from core.postgresql_datalogger import PostgreSQLDataLogger
            from config import (
                POSTGRES_ENABLED, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB,
                POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_MIN_CONN, POSTGRES_MAX_CONN
            )
            
            if POSTGRES_ENABLED:
                pg_datalogger = PostgreSQLDataLogger(
                    host=POSTGRES_HOST,
                    port=POSTGRES_PORT,
                    database=POSTGRES_DB,
                    user=POSTGRES_USER,
                    password=POSTGRES_PASSWORD,
                    min_conn=POSTGRES_MIN_CONN,
                    max_conn=POSTGRES_MAX_CONN
                )
                
                if pg_datalogger.enabled:
                    logger.info("✅ PostgreSQL DataLogger initialisé")
                    # Injecter dans scanner_loop
                    from core.callbacks.scanner_loop import set_pg_datalogger
                    set_pg_datalogger(pg_datalogger)
                    logger.info("✅ PostgreSQL DataLogger injecté dans scanner_loop")
        except ImportError as e:
            logger.debug(f"ℹ️ PostgreSQL DataLogger non disponible: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Erreur initialisation PostgreSQL DataLogger: {e}")
            pg_datalogger = None
        
        # 🔥 Simple Logger: Initialiser SimplePGLogger pour debugging
        try:
            from core.simple_pg_logger import SimplePGLogger
            simple_logger = SimplePGLogger()
            state.set_simple_logger(simple_logger)
            if simple_logger.enabled:
                logger.info("✅ SimplePGLogger connecté")
            else:
                logger.warning("⚠️ SimplePGLogger désactivé")
        except Exception as e:
            logger.error(f"❌ Erreur initialisation SimplePGLogger: {e}")
            state.set_simple_logger(None)
        
        # 🔥 NOUVEAU: Injecter Position Manager, Notification Manager et instance port
        # Récupérer port instance pour multi-instances
        port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
        
        if set_instance_port:
            set_instance_port(port)
    
    # 🔥 ARCHITECTURE V2: Initialiser Notification Manager
    if not state.get_notification_manager() and create_notification_manager:
        from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED
        from config import NOTIFICATION_BATCHING_ENABLED, NOTIFICATION_THROTTLE_SECONDS
        
        async def websocket_callback(event_type, data):
            """Callback pour envoyer via WebSocket natif"""
            ws_mgr = state.get_ws_manager()
            if ws_mgr:
                await ws_mgr.emit(event_type, data)
        
        # 🔥 NOUVEAU: Récupérer port instance pour multi-instances
        port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
        
        notif_mgr = create_notification_manager(
            telegram_bot_token=TELEGRAM_BOT_TOKEN,
            telegram_chat_id=TELEGRAM_CHAT_ID,
            socketio_callback=websocket_callback,  # 🔥 MIGRATION COMPLÈTE: Utiliser websocket_callback
            enable_batching=NOTIFICATION_BATCHING_ENABLED,
            instance_port=port  # 🔥 NOUVEAU: Passer instance_port
        )
        state.set_notification_manager(notif_mgr)
        
        if TELEGRAM_ENABLED:
            logger.info(f"📱 Notification Manager initialisé (Telegram activé)")
        else:
            logger.info(f"📱 Notification Manager initialisé (Telegram désactivé)")
        
        # 🔥 NOUVEAU: Injecter Notification Manager dans API routes (pour webhook Telegram)
        if set_notification_manager and notif_mgr:
            set_notification_manager(notif_mgr)

        # 🔥 Injecter NotificationManager dans les callbacks (scanner & position check)
        try:
            from core.callbacks.scanner_loop import set_notification_manager as set_scanner_notification_manager
            set_scanner_notification_manager(notif_mgr)
            logger.info("✅ NotificationManager injecté dans scanner_loop")
        except ImportError as e:
            logger.debug(f"ℹ️ Impossible d'injecter NotificationManager dans scanner_loop: {e}")

        try:
            from core.callbacks.position_check_loop import set_notification_manager as set_position_notification_manager
            set_position_notification_manager(notif_mgr)
            logger.info("✅ NotificationManager injecté dans position_check_loop")
        except ImportError as e:
            logger.debug(f"ℹ️ Impossible d'injecter NotificationManager dans position_check_loop: {e}")
    
    if not state.get_scanner() and ScalabilityScanner:
        state.set_scanner(ScalabilityScanner())
    if not state.get_analyzer() and TechnicalAnalyzer:
        state.set_analyzer(TechnicalAnalyzer())
    if not state.get_position_config() and PositionConfig:
        # 🔥 FIX: Initialiser PositionConfig depuis TRADING_CONFIG
        from config import TRADING_CONFIG
        pos_config = PositionConfig()
        
        # Configurer TP/SL mode depuis TRADING_CONFIG
        tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
        # 🔥 PHASE 7: TP_MULTI utilise aussi le mode ATR (pour calculer ATR)
        pos_config.use_atr = (tp_sl_mode == 'ATR' or tp_sl_mode == 'TP_MULTI')
        
        # Configurer valeurs FIXE depuis TRADING_CONFIG
        pos_config.fixed_tp_pct = TRADING_CONFIG.get('tp_percent', 0.25)
        pos_config.fixed_sl_pct = TRADING_CONFIG.get('sl_percent', 0.25)
        pos_config.break_even_trigger = TRADING_CONFIG.get('break_even_trigger', 0.3)
        pos_config.trailing_distance = TRADING_CONFIG.get('trailing_distance', 0.1)
        
        # Configurer valeurs ATR depuis TRADING_CONFIG
        pos_config.atr_mult_tp = TRADING_CONFIG.get('atr_mult_tp', 1.5)
        pos_config.atr_mult_sl = TRADING_CONFIG.get('atr_mult_sl', 1.0)
        pos_config.atr_min = TRADING_CONFIG.get('atr_min', 0.15)
        pos_config.atr_max = TRADING_CONFIG.get('atr_max', 1.5)
        
        # 🔥 FIX: Configurer use_slippage_calculation depuis TRADING_CONFIG
        pos_config.use_slippage_calculation = TRADING_CONFIG.get('use_slippage_calculation', True)
        state.set_position_config(pos_config)
    
    if not state.get_position_manager() and PositionManager and state.get_position_config():
        pos_mgr = PositionManager(state.get_position_config())
        
        # 🔥 ARCHITECTURE V2: Injecter analytics_db, notification_manager, session_id
        if state.get_analytics_db():
            pos_mgr.analytics_db = state.get_analytics_db()
            # 🔥 FIX: Mettre à jour aussi analytics_logger.analytics_db
            if pos_mgr.analytics_logger:
                pos_mgr.analytics_logger.analytics_db = state.get_analytics_db()
            logger.info("💾 Analytics DB injecté dans Position Manager et AnalyticsLogger")
        
        if state.session_id:
            pos_mgr.session_id = state.session_id
            logger.info(f"📝 Session ID injecté dans Position Manager: {state.session_id}")
        
        if state.get_notification_manager():
            pos_mgr.notification_manager = state.get_notification_manager()
            logger.info("📢 Notification Manager injecté dans Position Manager")
        
        state.set_position_manager(pos_mgr)
        
        # 🔥 NOUVEAU: Injecter Position Manager dans API routes (pour webhook Telegram)
        if set_position_manager:
            set_position_manager(state.get_position_manager())

    # 🔥 LIVE TRADING: Initialiser LiveOrderManager si mode LIVE
    logger.info(f"🔍 DEBUG: live_order_manager={state.get_live_order_manager()}, LiveOrderManager disponible={LiveOrderManager is not None}")
    if not state.get_live_order_manager() and LiveOrderManager:
        from api.live_trading_endpoints import load_live_config

        try:
            live_config = load_live_config()
            logger.info(f"🔍 DEBUG: live_config loaded: trading_mode={live_config.get('trading_mode')}, dry_run={live_config.get('dry_run')}")

            if live_config.get('trading_mode') == 'LIVE':
                api_key = live_config.get('api_key_mexc', '')
                api_secret = live_config.get('api_secret_mexc', '')

                if api_key and api_secret:
                    # 🔥 FUTURES: Récupérer levier + token depuis config
                    from config import TRADING_CONFIG
                    default_leverage = live_config.get('default_leverage', TRADING_CONFIG.get('default_leverage', 1))
                    browser_token = TRADING_CONFIG.get('mexc_browser_token') or os.getenv('MEXC_BROWSER_TOKEN', '').strip()
                    use_bypass_mode = TRADING_CONFIG.get('use_bypass_mode', True)

                    if use_bypass_mode and not browser_token:
                        logger.warning("⚠️ Mode BYPASS activé mais aucun browser token fourni (MEXC_BROWSER_TOKEN). Retour en mode CCXT.")

                    # 🔥 v7.3: Récupérer telegram_notifier depuis notification_manager
                    telegram_notif = None
                    notif_mgr = state.get_notification_manager()
                    if notif_mgr and hasattr(notif_mgr, 'telegram_notifier'):
                        telegram_notif = notif_mgr.telegram_notifier

                    live_mgr = LiveOrderManager(
                        api_key=api_key,
                        api_secret=api_secret,
                        browser_token=browser_token if browser_token else None,
                        default_leverage=default_leverage,
                        dry_run=live_config.get('dry_run', True),
                        use_bypass=use_bypass_mode and bool(browser_token),
                        telegram_notifier=telegram_notif,  # 🔥 v7.3: Alertes Telegram
                        enable_circuit_breaker=True,       # 🔥 v7.3: Circuit Breaker actif
                        circuit_breaker_threshold=5        # 🔥 v7.3: 5 échecs → ouverture circuit
                    )
                    state.set_live_order_manager(live_mgr)

                    logger.info(
                        f"✅ LiveOrderManagerFutures initialisé | "
                        f"Mode: {'DRY_RUN' if live_config.get('dry_run') else 'LIVE RÉEL'} | "
                        f"Levier: {default_leverage}x | "
                        f"Bypass: {'ON' if use_bypass_mode and browser_token else 'OFF'}"
                    )

                    # Injecter LiveOrderManager dans PositionManager
                    if state.get_position_manager():
                        state.get_position_manager().live_order_manager = live_mgr
                        logger.info("💾 LiveOrderManager injecté dans Position Manager")
                else:
                    logger.warning(f"⚠️ Mode LIVE activé mais API keys manquantes: api_key={bool(api_key)}, api_secret={bool(api_secret)}")
            else:
                logger.info(f"📝 Mode trading: {live_config.get('trading_mode', 'PAPER')} (LiveOrderManager non initialisé car mode != LIVE)")
        except Exception as e:
            logger.error(f"❌ Erreur initialisation LiveOrderManager: {e}")
            import traceback
            logger.error(traceback.format_exc())
            state.set_live_order_manager(None)
    else:
        if not LiveOrderManager:
            logger.warning("⚠️ LiveOrderManager class non disponible (import failed?)")
        if state.get_live_order_manager():
            logger.info(f"✅ LiveOrderManager déjà initialisé (dry_run={getattr(state.get_live_order_manager(), 'dry_run', '?')})")

    if not state.get_price_provider() and create_price_provider:
        state.set_price_provider(create_price_provider())
    # 🔥 JOUR 3: Initialiser scheduler et configurer les callbacks
    if not state.get_scheduler() and Scheduler:
        sched = Scheduler()
        # Configurer les callbacks (définis après init_instances)
        sched.set_scanner_callback(scanner_loop_callback)
        sched.set_position_check_callback(position_check_loop_callback)
        sched.set_scalability_refresh_callback(scalability_refresh_loop_callback)
        state.set_scheduler(sched)
        
        # 🔥 MIGRATION COMPLÈTE: Injecter ws_manager dans les callbacks
        ws_mgr = state.get_ws_manager()
        try:
            from core.callbacks.scanner_loop import set_websocket_manager
            if set_websocket_manager and ws_mgr:
                set_websocket_manager(ws_mgr)
        except ImportError:
            pass  # Callback module optionnel
        
        # 🔥 FIX: Injecter ws_manager dans position_check_loop
        try:
            from core.callbacks.position_check_loop import set_websocket_manager
            if set_websocket_manager and ws_mgr:
                set_websocket_manager(ws_mgr)
        except ImportError:
            pass  # Callback module optionnel

        # 🔥 FIX BUG #14: Injecter ws_manager dans scalability_refresh
        try:
            from core.callbacks.scalability_refresh import set_websocket_manager
            if set_websocket_manager and ws_mgr:
                set_websocket_manager(ws_mgr)
        except ImportError:
            pass  # Callback module optionnel


# Routes FastAPI

# 🔥 CLEANUP: Routes HTML supprimées - Frontend Svelte gère toute l'interface
# Plus besoin de servir des pages HTML, le frontend Svelte est indépendant

@app.get("/favicon.ico")
async def favicon():
    """Favicon (évite 404)"""
    from fastapi.responses import Response
    # Retourner un favicon vide (1x1 pixel transparent)
    return Response(content=b'', media_type='image/x-icon')


@app.get("/api/status")
async def api_status():
    """État global de l'application"""
    return JSONResponse(app_state.to_dict())


# 🔥 FIX: Endpoints sessions pour compatibilité frontend Svelte
@app.get("/api/sessions")
async def api_get_sessions():
    """
    ⚠️ DEPRECATED: Utiliser WebSocket request 'state' ou événements 'sessions_update' à la place
    Conservé pour compatibilité uniquement
    Liste des sessions (compatibilité frontend Svelte)
    """
    import time
    import sys
    try:
        init_instances()
    except Exception as e:
        logger.error(f"❌ Erreur init_instances dans /api/sessions: {e}", exc_info=True)
    
    try:
        current_port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
        sess_id = state.session_id
        return JSONResponse({
            'sessions': [{
                'id': sess_id or f"live_{int(time.time())}",
                'status': 'running' if app_state.get('is_scanning') else 'stopped',
                'port': current_port,
                'started_at': time.time()
            }] if sess_id else []
        })
    except Exception as e:
        logger.error(f"❌ Erreur /api/sessions: {e}", exc_info=True)
        return JSONResponse({
            'sessions': [],
            'error': str(e)
        }, status_code=200)  # Retourner 200 avec sessions vide


@app.get("/api/sessions/stats/global")
async def api_get_sessions_stats_global():
    """
    ⚠️ DEPRECATED: Utiliser WebSocket request 'state' ou événements 'stats_update' à la place
    Conservé pour compatibilité uniquement
    Stats globales des sessions (compatibilité frontend Svelte)
    """
    import time
    
    try:
        init_instances()
    except Exception as e:
        logger.error(f"❌ Erreur init_instances dans /api/sessions/stats/global: {e}", exc_info=True)
    
    try:
        # Calculer stats depuis app_state ou analytics_db
        stats_dict = {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'winrate': 0.0
        }

        analytics_db = state.get_analytics_db()
        if analytics_db:
            try:
                trades = analytics_db.get_trades(limit=10000)
                if trades:
                    total = len(trades)
                    wins = sum(1 for t in trades if t.get('pnl_usdt', 0) > 0)
                    losses = total - wins
                    winrate = (wins / total * 100) if total > 0 else 0.0
                    stats_dict = {
                        'total_trades': total,
                        'wins': wins,
                        'losses': losses,
                        'winrate': winrate
                    }
            except Exception as e:
                logger.error(f"❌ Erreur récupération stats globales: {e}")
        
        # Fallback: utiliser app_state['trade_history']
        if stats_dict['total_trades'] == 0 and app_state.get('trade_history'):
            try:
                trades = app_state['trade_history']
                if trades:
                    total = len(trades)
                    wins = sum(1 for t in trades if t.get('net_pnl_usdt', 0) > 0 or t.get('netPnlUSDT', 0) > 0)
                    losses = total - wins
                    winrate = (wins / total * 100) if total > 0 else 0.0
                    stats_dict = {
                        'total_trades': total,
                        'wins': wins,
                        'losses': losses,
                        'winrate': winrate
                    }
            except Exception as e:
                logger.error(f"❌ Erreur récupération stats app_state: {e}")
        
        return JSONResponse({
            'total_sessions': 1,
            'active_sessions': 1 if app_state.get('is_scanning') else 0,
            'global_stats': stats_dict
        })
    except Exception as e:
        logger.error(f"❌ Erreur /api/sessions/stats/global: {e}", exc_info=True)
        return JSONResponse({
            'total_sessions': 0,
            'active_sessions': 0,
            'global_stats': {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'winrate': 0.0
            },
            'error': str(e)
        }, status_code=200)  # Retourner 200 avec stats vides


@app.get("/api/state")
async def api_get_complete_state():
    """
    ⚠️ DEPRECATED: Utiliser WebSocket request 'state' à la place
    Conservé pour compatibilité uniquement
    """
    """🔥 NOUVEAU: État complet de l'application (config + UI + position + stats + etc.)"""
    import time
    from config import (
        TELEGRAM_ENABLED,
        TELEGRAM_NOTIFY_POSITION_OPENED, TELEGRAM_NOTIFY_POSITION_CLOSED,
        TELEGRAM_NOTIFY_TP_ESCALIER, TELEGRAM_NOTIFY_EARLY_INVALIDATION,
        TELEGRAM_NOTIFY_ERROR, TELEGRAM_NOTIFY_RECONNECTION,
        TELEGRAM_NOTIFY_DAILY_SUMMARY, TELEGRAM_NOTIFY_RECOVERY_MODE,
        TELEGRAM_NOTIFY_SETUP_REJECTED
    )
    logger.info("🔍 /api/state appelé - Début de la fonction")
    
    # 🔥 FIX: Retourner réponse minimale immédiatement - TOUJOURS retourner 200
    try:
        # Vérifier que app_state existe (sans utiliser globals() qui peut échouer)
        try:
            _ = app_state
        except NameError:
            logger.error("❌ app_state non défini (NameError)")
            return JSONResponse({
                'success': False,
                'error': 'app_state not initialized',
                'session_id': f"live_{int(time.time())}",
                'config': {},
                'scanner': {'is_scanning': False, 'top_pairs': []},
                'position': {'active': False, 'data': None},
                'stats': {'total_trades': 0, 'wins': 0, 'losses': 0, 'winrate': 0.0},
                'trades': [],
                'timestamp': time.time()
            }, status_code=200)
    except Exception as check_error:
        logger.error(f"❌ Erreur vérification app_state: {check_error}", exc_info=True)
        return JSONResponse({
            'success': False,
            'error': f'Initialization check failed: {str(check_error)}',
            'session_id': f"live_{int(time.time())}",
            'config': {},
            'scanner': {'is_scanning': False, 'top_pairs': []},
            'position': {'active': False, 'data': None},
            'stats': {'total_trades': 0, 'wins': 0, 'losses': 0, 'winrate': 0.0},
            'trades': [],
            'timestamp': time.time()
        }, status_code=200)
    
    try:
        # 🔥 FIX: Envelopper init_instances dans try/except pour éviter 503
        try:
            init_instances()
        except Exception as init_error:
            logger.error(f"❌ Erreur init_instances dans /api/state: {init_error}", exc_info=True)
            # Continuer quand même avec les valeurs par défaut
        
        # 🔥 FIX: Envelopper import TRADING_CONFIG dans try/except
        try:
            from config import TRADING_CONFIG
        except Exception as config_error:
            logger.error(f"❌ Erreur import TRADING_CONFIG: {config_error}", exc_info=True)
            # Utiliser valeurs par défaut
            TRADING_CONFIG = {
                'snr_threshold': 0.25,
                'breakout_threshold': 0.35,
                'wick_ratio_max': 2.8,
                'di_gap_min': 4.0,
                'trend_timeframe': '15m',
                'account_size': 1000.0,
                'risk_per_trade': 2.0,
                'use_confluence': False,
                'tp_sl_mode': 'FIXE',
                'tp_percent': 0.25,
                'sl_percent': 0.25,
                'volume_multiplier': 0.95,
                'min_score_required': 7.5
            }
        
        # Récupérer position active
        active_position_dict = None
        pos_mgr = state.get_position_manager()
        if pos_mgr and pos_mgr.active_position:
            try:
                active_position = pos_mgr.active_position
                active_position_dict = active_position.to_dict()
                active_position_dict['timestamp'] = time.time()
            except Exception as e:
                logger.error(f"❌ Erreur récupération position: {e}")
                active_position_dict = None
        
        # Récupérer stats depuis Analytics DB (avec fallback sur app_state)
        stats_dict = {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'winrate': 0.0
        }

        analytics_db = state.get_analytics_db()
        sess_id = state.session_id

        # 🔥 FIX: Utiliser app_state['trade_history'] comme fallback si analytics_db non disponible
        if analytics_db:
            try:
                trades = analytics_db.get_trades(limit=10000)
                if trades:
                    total = len(trades)
                    wins = sum(1 for t in trades if t.get('pnl_usdt', 0) > 0)
                    losses = total - wins
                    winrate = (wins / total * 100) if total > 0 else 0.0
                    stats_dict = {
                        'total_trades': total,
                        'wins': wins,
                        'losses': losses,
                        'winrate': winrate
                    }
            except Exception as e:
                logger.error(f"❌ Erreur récupération stats analytics_db: {e}")
        
        # Fallback: utiliser app_state['trade_history'] si analytics_db non disponible
        if stats_dict['total_trades'] == 0 and app_state.get('trade_history'):
            try:
                trades = app_state['trade_history']
                if trades:
                    total = len(trades)
                    wins = sum(1 for t in trades if t.get('net_pnl_usdt', 0) > 0 or t.get('netPnlUSDT', 0) > 0)
                    losses = total - wins
                    winrate = (wins / total * 100) if total > 0 else 0.0
                    stats_dict = {
                        'total_trades': total,
                        'wins': wins,
                        'losses': losses,
                        'winrate': winrate
                    }
            except Exception as e:
                logger.error(f"❌ Erreur récupération stats app_state: {e}")
        
        # Récupérer historique trades (tous les trades)
        trades_history = []
        if analytics_db:
            try:
                trades_history = analytics_db.get_trades(limit=10000)  # Limite élevée pour récupérer tous les trades
            except Exception as e:
                logger.error(f"❌ Erreur récupération historique analytics_db: {e}")

        # Fallback: utiliser app_state['trade_history']
        if not trades_history and app_state.get('trade_history'):
            trades_history = app_state['trade_history']  # Tous les trades, pas de limite
        
        # 🔥 SESSION-BASED: Filtrer les trades par session_id actuelle (seulement cette session)
        # Stats et historique affichés = session actuelle UNIQUEMENT
        # PostgreSQL conserve TOUS les trades de toutes les sessions
        current_session_trades = []
        if analytics_db and sess_id:
            try:
                # Récupérer seulement les trades de la session actuelle
                all_trades = analytics_db.get_trades(limit=10000)
                current_session_trades = [t for t in all_trades if t.get('session_id') == sess_id]

                # Recalculer stats pour cette session seulement
                if current_session_trades:
                    total = len(current_session_trades)
                    wins = sum(1 for t in current_session_trades if t.get('net_pnl_usdt', 0) > 0)
                    losses = total - wins
                    winrate = (wins / total * 100) if total > 0 else 0.0
                    stats_dict = {
                        'total_trades': total,
                        'wins': wins,
                        'losses': losses,
                        'winrate': winrate
                    }
                else:
                    stats_dict = {
                        'total_trades': 0,
                        'wins': 0,
                        'losses': 0,
                        'winrate': 0.0
                    }
            except Exception as e:
                logger.error(f"❌ Erreur filtrage trades par session: {e}")

        return JSONResponse({
            'success': True,
            'session_id': sess_id or f"live_{int(time.time())}",  # 🔥 FIX: Fallback si session_id None
            'config': {
                # Seuils configurables
                'snr_threshold': TRADING_CONFIG.get('snr_threshold', 0.25),
                'breakout_threshold': TRADING_CONFIG.get('breakout_threshold', 0.35),
                'wick_ratio_max': TRADING_CONFIG.get('wick_ratio_max', 2.8),
                'di_gap_min': TRADING_CONFIG.get('di_gap_min', 4.0),
                # Trend timeframe
                'trend_timeframe': TRADING_CONFIG.get('trend_timeframe', '15m'),
                # Capital
                'account_size': TRADING_CONFIG.get('account_size', 1000.0),
                'risk_per_trade': TRADING_CONFIG.get('risk_per_trade', 2.0),
                # Confluence
                'use_confluence': TRADING_CONFIG.get('use_confluence', False),
                # TP/SL Mode
                'tp_sl_mode': TRADING_CONFIG.get('tp_sl_mode', 'FIXE'),
                'tp_percent': TRADING_CONFIG.get('tp_percent', 0.25),
                'sl_percent': TRADING_CONFIG.get('sl_percent', 0.25),
                # Volume multiplier
                'volume_multiplier': TRADING_CONFIG.get('volume_multiplier', 0.95),
                # Min score
                'min_score_required': TRADING_CONFIG.get('min_score_required', 7.5),
                # 🔥 MIGRATION COMPLÈTE: Exposer statut Telegram
                'telegram_enabled': TELEGRAM_ENABLED,
                # 🔥 NOUVEAU: Exposer les types de notifications Telegram
                'telegram_notify_position_opened': TELEGRAM_NOTIFY_POSITION_OPENED,
                'telegram_notify_position_closed': TELEGRAM_NOTIFY_POSITION_CLOSED,
                'telegram_notify_tp_escalier': TELEGRAM_NOTIFY_TP_ESCALIER,
                'telegram_notify_early_invalidation': TELEGRAM_NOTIFY_EARLY_INVALIDATION,
                'telegram_notify_error': TELEGRAM_NOTIFY_ERROR,
                'telegram_notify_reconnection': TELEGRAM_NOTIFY_RECONNECTION,
                'telegram_notify_daily_summary': TELEGRAM_NOTIFY_DAILY_SUMMARY,
                'telegram_notify_recovery_mode': TELEGRAM_NOTIFY_RECOVERY_MODE,
                'telegram_notify_setup_rejected': TELEGRAM_NOTIFY_SETUP_REJECTED,
            },
            'scanner': {
                'is_scanning': app_state.get('is_scanning', False),
                'top_pairs': app_state.get('top_pairs', [])
            },
            'position': {
                'active': active_position_dict is not None,
                'data': active_position_dict
            },
            'stats': stats_dict,
            'trades': current_session_trades,  # 🔥 SESSION-BASED: Seulement les trades de la session actuelle (pas de fallback)
            'timestamp': time.time()
        })
    except Exception as e:
        logger.error(f"❌ Erreur /api/state: {e}", exc_info=True)
        # 🔥 FIX: Retourner réponse minimale au lieu de 503
        import time
        return JSONResponse({
            'success': False,
            'error': str(e),
            'session_id': state.session_id or f"live_{int(time.time())}",
            'config': {},
            'scanner': {'is_scanning': False, 'top_pairs': []},
            'position': {'active': False, 'data': None},
            'stats': {'total_trades': 0, 'wins': 0, 'losses': 0, 'winrate': 0.0},
            'trades': [],
            'timestamp': time.time()
        }, status_code=200)  # 🔥 FIX: Retourner 200 avec success=False au lieu de 503


@app.post("/api/start")
async def api_start():
    """
    ⚠️ DEPRECATED: Utiliser WebSocket command 'start_scanner' à la place
    Conservé pour compatibilité uniquement
    Démarrer le scanner et le scheduler
    """
    init_instances()
    
    # 🔥 FIX: Émettre scan_started IMMÉDIATEMENT au démarrage (avant le scan)
    ws_mgr = state.get_ws_manager()
    if ws_mgr:
        await ws_mgr.emit('scan_started', {'timestamp': time.time()})
        await ws_mgr.emit('status', {'is_scanning': True})
    state.set_is_scanning(True)
    
    # 🔥 JOUR 3: Si pas de top_pairs, faire un scan initial
    scnr = state.get_scanner()
    if not state.top_pairs and scnr and not scnr.is_scanning:
        await add_log('INFO', 'Scanner démarré', 'Scan initial des top pairs...')
        top_pairs = await scnr.scan_top_pairs(20)
        state.set_top_pairs(top_pairs)
        if ws_mgr:
            await ws_mgr.emit('top_pairs_update', {'pairs': top_pairs})
        
        # Démarrer WebSocket pour les top pairs
        price_prov = state.get_price_provider()
        if price_prov and top_pairs:
            symbols = [p.get('symbol', '') for p in top_pairs[:30] if p.get('symbol')]
            if symbols:
                try:
                    await price_prov.start_websocket(symbols)
                    await add_log('INFO', 'WebSocket démarré', f'{len(symbols)} symboles monitorés')
                except Exception as e:
                    logger.warning(f"Erreur démarrage WebSocket: {e}")
    
    # 🔥 JOUR 3: Démarrer le scheduler
    sched = state.get_scheduler()
    if sched:
        sched.start()
        logger.info("Scanner démarré")
        await add_log('INFO', 'Scanner démarré', 'Boucles automatiques activées')
    else:
        logger.info("Scanner démarré (sans scheduler)")
    
    return JSONResponse({'status': 'started'})


@app.post("/api/stop")
async def api_stop():
    """
    ⚠️ DEPRECATED: Utiliser WebSocket command 'stop_scanner' à la place
    Conservé pour compatibilité uniquement
    Arrêter le scanner et le scheduler
    """
    init_instances()
    
    # 🔥 JOUR 3: Arrêter le scheduler
    sched = state.get_scheduler()
    if sched:
        await sched.stop_async()
        logger.info("Scanner arrêté")
        await add_log('INFO', 'Scanner arrêté', 'Boucles automatiques désactivées')
        # 🔥 FIX: Émettre scan_complete pour mettre à jour le store frontend
        ws_mgr = state.get_ws_manager()
        if ws_mgr:
            await ws_mgr.emit('scan_complete', {'timestamp': time.time()})
            await ws_mgr.emit('status', {'is_scanning': False})
    else:
        state.set_is_scanning(False)
        logger.info("Scanner arrêté (sans scheduler)")
        # 🔥 FIX: Émettre scan_complete pour mettre à jour le store frontend
        ws_mgr = state.get_ws_manager()
        if ws_mgr:
            await ws_mgr.emit('scan_complete', {'timestamp': time.time()})
            await ws_mgr.emit('status', {'is_scanning': False})
    
    return JSONResponse({'status': 'stopped'})


# 🔥 v7.0: Jour 1 - Nouveaux endpoints

@app.get("/api/scanner/top-pairs")
async def api_get_top_pairs():
    """Récupérer les top pairs"""
    return JSONResponse({'pairs': state.top_pairs or []})


@app.post("/api/scanner/start")
async def api_scanner_start(request: Request):
    """
    ⚠️ DEPRECATED: Utiliser WebSocket command 'start_scanner' à la place
    Conservé pour compatibilité uniquement
    Démarrer scanner scalability
    """
    if state.is_scanning:
        return JSONResponse({'error': 'Déjà en cours'}, status_code=400)
    
    init_instances()
    data = await request.json() if hasattr(request, 'json') else {}
    top_n = data.get('top_n', 20) if isinstance(data, dict) else 20
    
    state.set_is_scanning(True)
    await add_log('INFO', 'Scanner démarré', f'Top {top_n} paires')
    
    # Lancer scan asynchrone
    scnr = state.get_scanner()
    if scnr:
        asyncio.create_task(scan_top_pairs_task(top_n))
    
    return JSONResponse({'status': 'started'})


@app.get("/api/price/{symbol}")
async def api_get_price(symbol: str):
    """Récupérer prix depuis WebSocket ou REST avec info de debug"""
    init_instances()
    price_prov = state.get_price_provider()
    if not price_prov:
        return JSONResponse({'error': 'Price provider not available'}, status_code=503)
    
    try:
        import time
        price_data = await price_prov.get_price(symbol)
        if price_data:
            # 🔥 DEBUG: Ajouter info sur la source (WebSocket ou REST)
            is_ws = (price_prov.use_websocket and 
                    price_prov.ws_manager and 
                    price_prov.ws_manager.connected)
            
            async with price_prov.cache_lock:
                from_cache = symbol in price_prov.price_cache
            
            source = "WebSocket" if (is_ws and from_cache) else "REST"
            price_data['_source'] = source
            
            # Calculer l'âge du prix (en secondes)
            if 'timestamp' in price_data:
                age = time.time() - price_data['timestamp']
                price_data['_age_seconds'] = round(age, 2)
            else:
                price_data['timestamp'] = time.time()
                price_data['_age_seconds'] = 0
            
            return JSONResponse(price_data)
        return JSONResponse({'error': 'Price not available'}, status_code=404)
    except Exception as e:
        logger.error(f"Erreur prix {symbol}: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


@app.get("/api/prices/live")
async def api_get_live_prices():
    """
    🔥 TEST: Récupérer tous les prix en cache WebSocket
    Utile pour vérifier que les prix sont bien mis à jour en temps réel
    """
    init_instances()
    
    price_prov = state.get_price_provider()
    if not price_prov:
        return JSONResponse({'error': 'Price provider not available'}, status_code=503)
    
    result = {
        "websocket_connected": False,
        "cache_size": 0,
        "prices": {},
        "timestamp": None
    }
    
    try:
        import time
        
        # Vérifier état WebSocket
        if price_prov.ws_manager:
            result["websocket_connected"] = price_prov.ws_manager.connected
        
        # Récupérer tous les prix du cache
        async with price_prov.cache_lock:
            result["cache_size"] = len(price_prov.price_cache)
            for symbol, price_data in price_prov.price_cache.items():
                age = time.time() - price_data.get('timestamp', time.time())
                result["prices"][symbol] = {
                    "price": price_data.get('referencePrice') or get_preferred_price(price_data),
                    "volume24": price_data.get('volume24', 0),
                    "age_seconds": round(age, 2),
                    "timestamp": price_data.get('timestamp', 0)
                }
        
        result["timestamp"] = time.time()
        
        return JSONResponse(result)
        
    except Exception as e:
        logger.error(f"Erreur récupération prix live: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


@app.post("/api/websocket/start")
async def api_start_websocket():
    """
    🔥 Démarrer manuellement le WebSocket pour les top pairs
    Utile si le WebSocket n'a pas été démarré automatiquement
    """
    init_instances()
    
    price_prov = state.get_price_provider()
    if not price_prov:
        return JSONResponse({'error': 'Price provider not available'}, status_code=503)
    
    top_pairs = state.top_pairs or []
    if not top_pairs:
        return JSONResponse({
            'error': 'Aucune top pair disponible. Lancez d\'abord /api/scanner/start',
            'status': 'no_pairs'
        }, status_code=400)
    
    try:
        # Récupérer les top 30 pairs
        symbols = [p.get('symbol', '') for p in top_pairs[:30] if p.get('symbol')]
        
        if not symbols:
            return JSONResponse({'error': 'Aucun symbole valide trouvé'}, status_code=400)
        
        # Démarrer WebSocket
        await price_prov.start_websocket(symbols)
        
        return JSONResponse({
            'status': 'started',
            'symbols_count': len(symbols),
            'symbols': symbols[:10]  # Afficher les 10 premiers
        })
        
    except Exception as e:
        logger.error(f"Erreur démarrage WebSocket: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


@app.get("/api/analyze/{symbol}")
async def api_analyze_symbol(
    symbol: str, 
    tf: str = Query('1m', description="Timeframe (pour compatibilité)"),
    use_confluence: bool = Query(None, description="True = 1m ET 5m, False = 1m OU 5m"),
    volume_multiplier: float = Query(None, description="Multiplicateur de volume 0.1-2.0"),
    trend_timeframe: str = Query(None, description="Timeframe pour trend_data (5m, 15m, 30m, 1h)")
):
    """
    Analyser un symbole avec paramètres configurables
    
    Args:
        symbol: Symbole de la paire
        tf: Timeframe (1m ou 5m) - pour compatibilité, mais utilise analyze_pair maintenant
        use_confluence: True = 1m ET 5m, False = 1m OU 5m (défaut: depuis TRADING_CONFIG)
        volume_multiplier: Multiplicateur de volume 0.1-2.0 (défaut: depuis TRADING_CONFIG)
        trend_timeframe: Timeframe pour calculer trend_data (défaut: depuis TRADING_CONFIG)
    """
    init_instances()
    anlyzr = state.get_analyzer()
    if not anlyzr:
        return JSONResponse({'error': 'Analyzer not available'}, status_code=503)
    
    try:
        # 🔥 FIX: Récupérer valeurs depuis TRADING_CONFIG si non fournies
        from config import TRADING_CONFIG
        if use_confluence is None:
            use_confluence = TRADING_CONFIG.get('use_confluence', False)
        if volume_multiplier is None:
            volume_multiplier = TRADING_CONFIG.get('volume_multiplier', 1.0)
        if trend_timeframe is None:
            trend_timeframe = TRADING_CONFIG.get('trend_timeframe', '15m')
        
        # 🔥 FIX: Calculer trend_data avec le timeframe fourni ou configuré
        trend_data = await anlyzr.calculate_trend_data(symbol, trend_timeframe)
        
        # 🔥 PHASE 6: Récupérer positions actives pour Correlation Filter
        active_positions = []
        pos_mgr = state.get_position_manager()
        if pos_mgr and pos_mgr.active_position:
            active_positions = [pos_mgr.active_position.symbol]
        
        # 🔥 FIX: Utiliser analyze_pair au lieu de analyze_symbol pour supporter confluence et volume_multiplier
        analysis = await anlyzr.analyze_pair(
            symbol, 
            trend_data=trend_data,  # 🔥 Utiliser trend_data calculé
            volume_multiplier=volume_multiplier,
            use_confluence=use_confluence,
            return_reason=False,
            active_positions=active_positions,  # 🔥 PHASE 6: Correlation Filter
            position_manager=pos_mgr  # 🔥 PHASE 6: Recovery Mode
        )
        
        if analysis:
            return JSONResponse({'analysis': analysis})
        return JSONResponse({'analysis': None})
    except Exception as e:
        logger.error(f"Erreur analyse {symbol}: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)




@app.post("/api/position/open")
async def api_open_position(request: Request):
    """Ouvrir position"""
    init_instances()
    pos_mgr = state.get_position_manager()
    if not pos_mgr:
        return JSONResponse({'error': 'Position manager not available'}, status_code=503)
    
    # 🔥 FIX: Utiliser le même lock que le scanner pour éviter les ouvertures multiples
    pos_lock = state.lock("position")
    position = None
    data = {}
    try:
        async with pos_lock:
            pos_mgr = state.get_position_manager()
            if not pos_mgr:
                return JSONResponse({'error': 'Position manager not available'}, status_code=503)
            # Vérifier qu'on n'a pas déjà une position active
            if state.active_position or (pos_mgr and pos_mgr.active_position):
                return JSONResponse({'error': 'Une position est déjà active'}, status_code=400)

            data = await request.json() if hasattr(request, 'json') else {}
            data = data if isinstance(data, dict) else {}

            # Vérifier données minimales
            if not data or 'symbol' not in data:
                return JSONResponse({'error': 'Missing symbol'}, status_code=400)

            # Double-check après avoir acquis le lock
            if state.active_position or (pos_mgr and pos_mgr.active_position):
                return JSONResponse({'error': 'Une position est déjà active (double-check)'}, status_code=400)

            # 🔥 FIX: Vérifier que entry est fourni et valide
            entry = data.get('entry')
            if not entry or entry <= 0:
                return JSONResponse({
                    'error': f'Entry invalide ou manquant: {entry}. Entry doit être > 0.'
                }, status_code=400)

            # Extraire paramètres avec valeurs par défaut
            condition_types = data.get('condition_types', [])  # 🔥 PHASE 5: Types de conditions

            # 🔥 Calculer le multiplicateur adaptatif si non fourni
            adaptive_mult = data.get('adaptive_sizing_multiplier', 1.0)
            if adaptive_mult == 1.0:
                try:
                    # Import sécurisé de TRADING_CONFIG
                    from config import TRADING_CONFIG
                    if TRADING_CONFIG.get('adaptive_sizing_enabled', True):
                        from core.position.adaptive_sizing import get_adaptive_sizing_manager
                        adaptive_manager = get_adaptive_sizing_manager()
                        adaptive_mult = adaptive_manager.get_size_multiplier(data['symbol'])
                except (ImportError, AttributeError):
                    pass

            # 🔄 INVERSION DES SIGNAUX (pour diagnostic) - API manuelle
            direction = data.get('direction', 'LONG')
            original_direction = direction
            if TRADING_CONFIG.get('invert_signals', False):
                direction = 'SHORT' if direction == 'LONG' else 'LONG'
                logger.warning(
                    f"🔄 INVERSION DE SIGNAL ACTIVÉE (API): {data['symbol']} | "
                    f"Signal original: {original_direction} → Direction inversée: {direction}"
                )

            position = pos_mgr.open_position(
                symbol=data['symbol'],
                direction=direction,
                entry=float(entry),  # 🔥 FIX: S'assurer que c'est un float
                size=data.get('size', 100.0),
                atr=data.get('atr'),
                atr5m=data.get('atr5m'),
                confirmed_by=data.get('confirmed_by', ''),
                scalability_data=data.get('scalability_data'),
                condition_types=condition_types,  # 🔥 PHASE 5: Types de conditions
                ml_confidence=data.get('ml_confidence'),  # 🔥 FIX: Passer ml_confidence
                adaptive_sizing_multiplier=adaptive_mult,  # 🔥 Multiplicateur adaptatif
                setup_data=data
            )

            if position is None:
                return JSONResponse({'error': 'Trade rejeté (calibration ML)'}, status_code=400)

            # 🔥 FIX: Stocker capital si fourni dans data
            if 'capital' in data:
                position.capital = data.get('capital')

            state.set_active_position(position)
    except Exception as e:
        logger.error(f"Erreur ouverture position: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)

    # ⚠️ IMPORTANT: Tout ce qui suit est volontairement hors lock
    # pour éviter de bloquer l'API si un envoi WebSocket se fige.
    try:
        price_prov = state.get_price_provider()
        if price_prov and position:
            await setup_realtime_sl_check(position, price_prov)
    except Exception as e:
        logger.warning(f"⚠️ Erreur setup_realtime_sl_check: {e}")

    try:
        if position:
            await schedule_sl_order_placement(position, delay_seconds=3.0)
    except Exception as e:
        logger.warning(f"⚠️ Erreur schedule_sl_order_placement: {e}")

    try:
        sched = state.get_scheduler()
        logger.info(f"🔍 Scheduler check: sched={sched is not None}, is_running={sched.is_running if sched else 'N/A'}")
        if sched and not sched.is_running:
            logger.info("🚀 Démarrage du scheduler pour position active...")
            sched.start()
            logger.info(f"✅ Scheduler démarré: is_running={sched.is_running}")
        elif sched and sched.is_running:
            logger.info("✅ Scheduler déjà actif")
    except Exception as e:
        logger.warning(f"⚠️ Erreur démarrage scheduler: {e}")

    try:
        asyncio.create_task(add_log('INFO', 'Position ouverte', f"{data.get('direction', 'LONG')} {data.get('symbol', '')}"))
    except Exception:
        pass

    try:
        ws_mgr = state.get_ws_manager()
        if ws_mgr:
            asyncio.create_task(ws_mgr.emit('position_opened', position.to_dict()))
    except Exception:
        pass

    return JSONResponse({'status': 'opened', 'position': position.to_dict()})


@app.get("/api/position/active")
async def api_get_active_position():
    """🔥 FIX: Récupérer position active pour restauration au refresh"""
    init_instances()
    pos_mgr = state.get_position_manager()
    if not pos_mgr or not pos_mgr.active_position:
        return JSONResponse({
            'success': True,
            'active': False,
            'position': None
        })
    
    position = pos_mgr.active_position
    position_dict = position.to_dict()
    
    # Ajouter timestamp pour vérifier fraîcheur
    import time
    position_dict['timestamp'] = time.time()
    
    return JSONResponse({
        'success': True,
        'active': True,
        'position': position_dict
    })


@app.get("/api/position/check")
async def api_check_position():
    """Check position actuelle"""
    init_instances()
    pos_mgr = state.get_position_manager()
    if not pos_mgr or not pos_mgr.active_position:
        return JSONResponse({'status': 'no_position'})
    
    price_prov = state.get_price_provider()
    if not price_prov:
        return JSONResponse({'error': 'Price provider not available'}, status_code=503)
    
    try:
        # Récupérer prix actuel
        price_data = await price_prov.get_price(pos_mgr.active_position.symbol)
        current_price = get_preferred_price(price_data)
        
        if not current_price:
            return JSONResponse({'error': 'Price not available'}, status_code=500)
        
        # Check position (renvoie None ou raison de fermeture)
        result = await pos_mgr.check_position(current_price)
        
        # Construire réponse
        position = pos_mgr.active_position
        # 🔥 FIX: Utiliser pnl_calculator au lieu de _calculate_pnl
        pnl = pos_mgr.pnl_calculator.calculate_pnl_percent(
            entry=position.entry,
            current_price=current_price,
            direction=position.direction
        )
        # Calculer PnL USDT
        pnl_usdt = pos_mgr.pnl_calculator.calculate_pnl_usdt(
            position=position.to_dict(),
            current_price=current_price
        )
        
        response = {
            'status': 'position_active',
            'symbol': position.symbol,
            'current_price': current_price,
            'pnl': pnl,
            'pnl_usdt': pnl_usdt,
            'entry': position.entry,
            'sl': position.sl,
            'tp': position.tp,
            'size': position.size
        }
        
        if result:
            # Position à fermer
            response['close_reason'] = result
        
        ws_mgr = state.get_ws_manager()
        if ws_mgr:
            await ws_mgr.emit('position_update', response)
        return JSONResponse(response)
    except Exception as e:
        logger.error(f"Erreur check position: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


@app.post("/api/position/close")
async def api_close_position():
    """
    ⚠️ DEPRECATED: Utiliser WebSocket command 'close_position' à la place
    Conservé pour compatibilité uniquement
    Clôturer position manuellement
    """
    init_instances()
    
    # 🔥 FIX: Utiliser le lock pour synchroniser la fermeture
    pos_lock = state.lock("position")
    async with pos_lock:
        pos_mgr = state.get_position_manager()
        # Double-check que la position existe AVANT et APRÈS avoir acquis le lock
        if not pos_mgr or not pos_mgr.active_position:
            # Vérifier aussi dans state
            if not state.active_position:
                logger.warning("⚠️ Tentative de fermeture sans position active (position_manager)")
                return JSONResponse({'error': 'No active position'}, status_code=400)
            else:
                # Position dans state mais pas dans position_manager - nettoyer state
                logger.warning("⚠️ Position dans state mais pas dans position_manager - nettoyage")
                state.set_active_position(None)
                return JSONResponse({'error': 'Position state inconsistent'}, status_code=400)
        
        price_prov = state.get_price_provider()
        if not price_prov:
            return JSONResponse({'error': 'Price provider not available'}, status_code=503)
        
        try:
            # Récupérer prix actuel
            price_data = await price_prov.get_price(pos_mgr.active_position.symbol)
            exit_price = get_preferred_price(price_data)
            
            result = pos_mgr.close_position(exit_price=exit_price, reason='MANUAL')
            
            state.set_active_position(None)
            
            # 🔥 PHASE 4: Ajouter à l'historique et sauvegarder
            if result:
                result['timestamp'] = datetime.now().isoformat()
                # 🔥 FIX: Utiliser add_trade pour upsert sécurisé
                state.add_trade(result)
                save_trade_history()
            
            # 🔥 FIX: Désactiver callback WebSocket si position fermée
            if price_prov:
                price_prov.set_socketio_callback(None, None)
                # 🔥 FIX SL MISMATCH: Désactiver callback SL temps réel
                price_prov.set_sl_check_callback(None)
            
            # 🔥 FIX SL MISMATCH V2: Annuler tâche SL en attente
            closed_symbol = result.get('symbol') if result else None
            if closed_symbol:
                cancel_pending_sl_task(closed_symbol)
            
            logger.info(
                f"🔒 Position fermée manuellement avec lock: "
                f"state.active_position=None, "
                f"position_manager.active_position={pos_mgr.active_position}"
            )
            
            # 🔥 Afficher le mode de trading clairement
            live_mgr = state.get_live_order_manager()
            if live_mgr:
                mode_str = "🟡 LIVE DRY-RUN" if live_mgr.dry_run else "🔴 LIVE RÉEL"
            else:
                mode_str = "📝 PAPER"
            await add_log('INFO', f'Position clôturée [{mode_str}]', 'Manuel')
            ws_mgr = state.get_ws_manager()
            if ws_mgr:
                await ws_mgr.emit('position_closed', result)
            
            # 🔥 FIX: Émettre stats_update après fermeture manuelle de position
            try:
                from core.callbacks.position_check_loop import _emit_stats_update
                await _emit_stats_update()
            except Exception as e:
                logger.error(f"❌ Erreur émission stats_update: {e}")
            
            return JSONResponse(result)
        except Exception as e:
            logger.error(f"Erreur clôture position: {e}")
            return JSONResponse({'error': str(e)}, status_code=500)


# Helper async tasks

async def scan_top_pairs_task(n):
    """Tâche asynchrone pour scanner top pairs"""
    scnr = state.get_scanner()
    if not scnr:
        return
    
    # 🔥 FIX: Vérifier si le scanner est déjà en cours
    if scnr.is_scanning:
        logger.debug("⏸️ scan_top_pairs_task ignoré - Scanner déjà actif")
        return
    
    try:
        await add_log('INFO', 'Scan scalability', 'Démarrage...')
        
        top_pairs = await scnr.scan_top_pairs(n)
        state.set_top_pairs(top_pairs)
        
        # 🔥 OPTIMISATION: Invalider cache quand top_pairs change
        if hasattr(app, '_top_pairs_cache'):
            app._top_pairs_cache.pop('top_pairs', None)
        
        await add_log('INFO', 'Scan terminé', f'{len(top_pairs)} paires scalables')
        ws_mgr = state.get_ws_manager()
        if ws_mgr:
            await ws_mgr.emit('top_pairs_update', {'pairs': top_pairs})
        
        # 🔥 SPRINT 1: Mettre à jour et diffuser le régime de marché
        try:
            from core.market_regime_selector import get_regime_selector
            regime_selector = get_regime_selector()
            
            # Extraire ATR et ADX des paires
            atr_values = [p.get('atr_percent', 0) for p in top_pairs if p.get('atr_percent') is not None]
            atr_5m_values = [p.get('atr_percent_5m', 0) for p in top_pairs if p.get('atr_percent_5m') is not None]
            adx_values = [p.get('adx', 0) for p in top_pairs if p.get('adx') is not None]
            
            if atr_values:
                # Forcer la mise à jour pour avoir les métriques fraîches
                regime, changed = await regime_selector.check_regime(
                    atr_values=atr_values,
                    atr_5m_values=atr_5m_values,
                    adx_values=adx_values,
                    force=True,  # On force pour mettre à jour l'affichage
                    trigger="scan"
                )
                
                # Diffuser le nouvel état
                status = regime_selector.get_status()
                # 🔥 FIX: Ajouter l'état enabled depuis TRADING_CONFIG
                from config import TRADING_CONFIG
                status['enabled'] = TRADING_CONFIG.get('market_regime_enabled', True)
                
                ws_mgr = state.get_ws_manager()
                if ws_mgr:
                    await ws_mgr.emit('regime_changed', status)
                
                if changed:
                    logger.info(f"🔄 Régime changé après scan: {regime}")
                    await add_log('INFO', 'Régime changé', f'Nouveau régime: {regime}')
        except Exception as e:
            logger.error(f"Erreur mise à jour régime après scan: {e}")

        # 🔥 JOUR 3: Démarrer WebSocket pour les top pairs après le scan
        price_prov = state.get_price_provider()
        if price_prov and top_pairs:
            symbols = [p.get('symbol', '') for p in top_pairs[:30] if p.get('symbol')]
            if symbols:
                try:
                    await price_prov.start_websocket(symbols)
                    await add_log('INFO', 'WebSocket démarré', f'{len(symbols)} symboles monitorés')
                except Exception as e:
                    logger.warning(f"Erreur démarrage WebSocket: {e}")
        
    except Exception as e:
        logger.error(f"Erreur scan: {e}")
        await add_log('ERROR', 'Erreur scan', str(e))
    finally:
        state.set_is_scanning(False)


# 🔥 MIGRATION COMPLÈTE: Handlers Socket.IO supprimés - WebSocket natif uniquement
# Tous les handlers sont maintenant dans l'endpoint /ws ci-dessous


# 🔥 WebSocket Natif - Endpoint Bidirectionnel
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Endpoint WebSocket bidirectionnel natif"""
    try:
        # 🔥 DEBUG: Trace connexion log
        logger.info(f"🔌 [WS-DEBUG] Nouvelle connexion WebSocket entrante: {websocket.client}")
        
        ws_mgr = state.get_ws_manager()
        if not ws_mgr:
            logger.error("❌ WebSocketManager non trouvé dans le state, fermeture 1011")
            await websocket.close(code=1011)
            return
            
        logger.info("🔌 [WS-DEBUG] Tentative de connexion au manager...")
        await ws_mgr.connect(websocket)
        logger.info("✅ [WS-DEBUG] Connexion au manager réussie")
        
        # 🔥 FIX: Envoyer état initial au client avec gestion d'erreur
        try:
            logger.debug("📦 Préparation données état initial...")
            status_data = app_state.copy()
            if status_data.get('active_position') and hasattr(status_data['active_position'], 'to_dict'):
                try:
                    status_data['active_position'] = status_data['active_position'].to_dict()
                except Exception as e:
                    logger.warning(f"⚠️ Erreur conversion position en dict: {e}")
                    status_data['active_position'] = None
            
            logger.debug("📤 Envoi état initial...")
            await ws_mgr.send_personal_message({
                'type': 'event',
                'event': 'status',
                'data': status_data
            }, websocket)
            logger.debug("✅ État initial envoyé")
        except Exception as e:
            logger.error(f"❌ Erreur envoi état initial: {e}")
        
        # 🔥 FIX: Envoyer les derniers logs avec gestion d'erreur
        try:
            logs = app_state.get('logs', [])[-50:]
            logger.debug(f"📤 Envoi de {len(logs)} logs historiques...")
            for log_entry in logs:
                try:
                    await ws_mgr.send_personal_message({
                        'type': 'event',
                        'event': 'log',
                        'data': log_entry
                    }, websocket)
                except Exception as e:
                    logger.debug(f"⚠️ Erreur envoi log: {e}")
                    break  # Arrêter si erreur
            logger.debug("✅ Logs envoyés")
        except Exception as e:
            logger.error(f"❌ Erreur envoi logs: {e}")
        
        # 🔥 FIX: Émettre reset_session à chaque nouvelle connexion pour réinitialiser le frontend
        try:
            logger.debug("📤 Envoi reset_session...")
            await ws_mgr.send_personal_message({
                'type': 'event',
                'event': 'reset_session',
                'data': {
                    'timestamp': time.time(),
                    'reason': 'new_connection'
                }
            }, websocket)
            logger.debug("✅ Événement reset_session envoyé")
        except Exception as e:
            logger.debug(f"⚠️ Erreur envoi reset_session: {e}")
        
        # Boucle bidirectionnelle : recevoir et traiter messages
        logger.info("🔄 Démarrage boucle de réception messages...")
        try:
            while True:
                # 🔥 FIX: Timeout pour éviter les blocages et permettre heartbeat
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                except asyncio.TimeoutError:
                    # Timeout normal - envoyer ping de maintenance
                    try:
                        await ws_mgr.send_personal_message({
                            'type': 'ping',
                            'timestamp': time.time()
                        }, websocket)
                        continue
                    except Exception as e:
                        logger.warning(f"❌ Connexion fermée pendant le ping: {e}")
                        break
                
                # Parser JSON séparément avec gestion d'erreur
                try:
                    message = json.loads(data)
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ Message JSON invalide reçu: {data[:100] if data else 'N/A'}... - {e}")
                    continue
                
                msg_type = message.get('type')
                
                # Traiter commandes (Frontend → Backend)
                if msg_type == 'command':
                    command = message.get('command')
                    params = message.get('params', {})
                    command_id = message.get('id')
                    
                    logger.info(f"📨 Commande reçue: {command} (ID: {command_id})")
                    
                    try:
                        result = await handle_client_command(command, params)
                        await ws_mgr.send_personal_message({
                            'type': 'command_response',
                            'id': command_id,
                            'command': command,
                            'result': result,
                            'status': 'success',
                            'timestamp': time.time()
                        }, websocket)
                    except Exception as e:
                        logger.error(f"Erreur commande {command}: {e}")
                        await ws_mgr.send_personal_message({
                            'type': 'command_error',
                            'id': command_id,
                            'command': command,
                            'error': str(e),
                            'timestamp': time.time()
                        }, websocket)
                
                # Heartbeat (Frontend ↔ Backend)
                elif msg_type == 'ping':
                    await ws_mgr.send_personal_message({
                        'type': 'pong',
                        'timestamp': time.time()
                    }, websocket)
                
                # Subscription (Frontend → Backend)
                elif msg_type == 'subscribe':
                    channel = message.get('channel', 'all')
                    ws_mgr.subscribe(websocket, channel)
                    await ws_mgr.send_personal_message({
                        'type': 'subscribed',
                        'channel': channel,
                        'timestamp': time.time()
                    }, websocket)
                
                # Unsubscribe (Frontend → Backend)
                elif msg_type == 'unsubscribe':
                    channel = message.get('channel', 'all')
                    ws_mgr = state.get_ws_manager()
                    if ws_mgr:
                        ws_mgr.unsubscribe(websocket, channel)
                        await ws_mgr.send_personal_message({
                            'type': 'unsubscribed',
                            'channel': channel,
                            'timestamp': time.time()
                        }, websocket)
                
                # Request (Frontend → Backend)
                elif msg_type == 'request':
                    request_type = message.get('request_type')
                    request_id = message.get('id')
                    
                    if request_type == 'logs':
                        ws_mgr = state.get_ws_manager()
                        if ws_mgr:
                            await ws_mgr.send_personal_message({
                                'type': 'request_response',
                                'id': request_id,
                                'request_type': request_type,
                                'data': state.logs[-100:]
                            }, websocket)
                    
                    elif request_type == 'position':
                        pos_mgr = state.get_position_manager()
                        pos = pos_mgr.get_active_position() if pos_mgr else None
                        ws_mgr = state.get_ws_manager()
                        if ws_mgr:
                            await ws_mgr.send_personal_message({
                                'type': 'request_response',
                                'id': request_id,
                                'request_type': request_type,
                                'data': pos
                            }, websocket)
                    
                    elif request_type == 'state':
                        # 🔥 NOUVEAU: Handler pour chargement état initial complet via WebSocket
                        try:
                            # Récupérer l'état complet (même logique que /api/state)
                            state_response = await api_get_complete_state()
                            ws_mgr = state.get_ws_manager()
                            if ws_mgr:
                                await ws_mgr.send_personal_message({
                                    'type': 'request_response',
                                    'id': request_id,
                                    'request_type': request_type,
                                    'data': state_response
                                }, websocket)
                        except Exception as state_err:
                            logger.error(f"❌ Erreur récupération state via WebSocket: {state_err}")
                            ws_mgr = state.get_ws_manager()
                            if ws_mgr:
                                await ws_mgr.send_personal_message({
                                    'type': 'request_response',
                                    'id': request_id,
                                    'request_type': request_type,
                                    'error': str(state_err)
                                }, websocket)

        except WebSocketDisconnect:
            logger.info(f"👋 WebSocket déconnecté proprement: {websocket.client}")
            if ws_mgr:
                await ws_mgr.disconnect(websocket)
        except Exception as e:
            logger.error(f"❌ Erreur inattendue boucle WebSocket: {e}", exc_info=True)
            if ws_mgr:
                await ws_mgr.disconnect(websocket)
    
    except Exception as e:
        logger.critical(f"❌ CRITICAL: Erreur fatale dans websocket_endpoint: {e}", exc_info=True)
        try:
            await websocket.close(code=1011)
        except:
            pass


# 🔥 === ENDPOINT /api/state (WEBSOCKET MIGRATION COMPLÈTE) ===
@app.get("/api/state")
async def api_get_complete_state():
    """
    🔥 MIGRATION COMPLÈTE: Endpoint REST maintenu pour compatibilité
    Le frontend utilise désormais WebSocket pour récupérer l'état complet
    """
    try:
        from config import TRADING_CONFIG
        # time est déjà importé au niveau du module
        
        # Récupérer position active
        active_position_dict = None
        pos_mgr = state.get_position_manager()
        if pos_mgr and pos_mgr.active_position:
            try:
                active_position = pos_mgr.active_position
                active_position_dict = active_position.to_dict()
                active_position_dict['timestamp'] = time.time()
            except Exception as e:
                logger.error(f"❌ Erreur récupération position: {e}")
                active_position_dict = None
        
        # Récupérer stats
        stats_dict = {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'winrate': 0.0
        }
        
        # Utiliser state.trade_history comme source principale
        current_session_trades = state.trade_history or []
        
        # Si analytics_db disponible, essayer de récupérer les trades de la session
        analytics_db = state.get_analytics_db()
        sess_id = state.session_id
        if analytics_db and sess_id:
            try:
                # Récupérer seulement les trades de la session actuelle
                all_trades = analytics_db.get_trades(limit=10000)
                db_trades = [t for t in all_trades if t.get('session_id') == sess_id]
                # Utiliser les trades DB si plus complets, sinon garder state
                if len(db_trades) > len(current_session_trades):
                    current_session_trades = db_trades
            except Exception as e:
                logger.error(f"❌ Erreur récupération trades depuis DB: {e}")
        
        # Recalculer stats depuis l'historique
        if current_session_trades:
            total = len(current_session_trades)
            wins = sum(1 for t in current_session_trades if t.get('net_pnl_usdt', 0) > 0 or t.get('netPnlUSDT', 0) > 0)
            losses = total - wins
            winrate = (wins / total * 100) if total > 0 else 0.0
            stats_dict = {
                'total_trades': total,
                'wins': wins,
                'losses': losses,
                'winrate': winrate
            }
        
        # Configuration complète
        from config import (
            TELEGRAM_ENABLED,
            TELEGRAM_NOTIFY_POSITION_OPENED, TELEGRAM_NOTIFY_POSITION_CLOSED,
            TELEGRAM_NOTIFY_TP_ESCALIER, TELEGRAM_NOTIFY_EARLY_INVALIDATION,
            TELEGRAM_NOTIFY_ERROR, TELEGRAM_NOTIFY_RECONNECTION,
            TELEGRAM_NOTIFY_DAILY_SUMMARY, TELEGRAM_NOTIFY_RECOVERY_MODE,
            TELEGRAM_NOTIFY_SETUP_REJECTED
        )
        
        state_data = {
            'success': True,
            'session_id': state.session_id or f"live_{int(time.time())}",
            'config': {
                # Patterns Techniques
                'use_breakout': TRADING_CONFIG.get('use_breakout', True),
                'use_snr': TRADING_CONFIG.get('use_snr', True),
                'use_wick': TRADING_CONFIG.get('use_wick', True),
                'use_divergence': TRADING_CONFIG.get('use_divergence', True),
                # Patterns de Bougies
                'use_engulfing': TRADING_CONFIG.get('use_engulfing', True),
                'use_hammer': TRADING_CONFIG.get('use_hammer', True),
                'use_shooting_star': TRADING_CONFIG.get('use_shooting_star', True),
                'use_doji': TRADING_CONFIG.get('use_doji', True),
                'use_marubozu': TRADING_CONFIG.get('use_marubozu', True),
                'use_morning_star': TRADING_CONFIG.get('use_morning_star', True),
                'use_evening_star': TRADING_CONFIG.get('use_evening_star', True),
                # Configuration complète (TP/SL, Money Management, etc.)
                'tp_sl_mode': TRADING_CONFIG.get('tp_sl_mode', 'FIXE'),
                'tp_percent': TRADING_CONFIG.get('tp_percent', 0.25),
                'sl_percent': TRADING_CONFIG.get('sl_percent', 0.25),
                'account_size': TRADING_CONFIG.get('account_size', 1000.0),
                'risk_per_trade': TRADING_CONFIG.get('risk_per_trade', 2.0),
                'telegram_enabled': TELEGRAM_ENABLED,
            },
            'scanner': {
                'is_scanning': state.is_scanning,
                'top_pairs': state.top_pairs or []
            },
            'position': {
                'active': active_position_dict is not None,
                'data': active_position_dict
            },
            'stats': stats_dict,
            'trade_history': current_session_trades,
            'timestamp': time.time()
        }
        
        return state_data
        
    except Exception as e:
        logger.error(f"❌ Erreur récupération state: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'timestamp': time.time()
        }


# 🔥 Fonction : Traiter commandes du client
async def handle_client_command(command: str, params: dict):
    """Exécuter une commande du client via WebSocket"""
    
    if command == 'start_scanner':
        # 🔥 FIX: Dupliquer la logique de api_start (pas JSONResponse)
        init_instances()
        
        # Émettre scan_started IMMÉDIATEMENT au démarrage (avant le scan)
        ws_mgr = state.get_ws_manager()
        if ws_mgr:
            await ws_mgr.emit('scan_started', {'timestamp': time.time()})
            await ws_mgr.emit('status', {'is_scanning': True})
        app_state['is_scanning'] = True
        
        # Si pas de top_pairs, faire un scan initial
        if not app_state['top_pairs']:
            asyncio.create_task(_run_initial_top_pairs_scan())
        
        # Démarrer le scheduler
        sched = state.get_scheduler()
        if sched:
            sched.start()
            logger.info("Scanner démarré")
            await add_log('INFO', 'Scanner démarré', 'Boucles automatiques activées')
        else:
            logger.info("Scanner démarré (sans scheduler)")
        
        return {'status': 'started', 'is_scanning': True}
    
    elif command == 'stop_scanner':
        # 🔥 FIX: Dupliquer la logique de api_stop (pas JSONResponse)
        init_instances()
        
        # Arrêter le scheduler
        sched = state.get_scheduler()
        if sched:
            await sched.stop_async()
            logger.info("Scanner arrêté")
            await add_log('INFO', 'Scanner arrêté', 'Boucles automatiques désactivées')
            # 🔥 FIX: Émettre scan_complete pour mettre à jour le store frontend
            ws_mgr = state.get_ws_manager()
            if ws_mgr:
                await ws_mgr.emit('scan_complete', {'timestamp': time.time()})
                await ws_mgr.emit('status', {'is_scanning': False})
        else:
            app_state['is_scanning'] = False
            logger.info("Scanner arrêté (sans scheduler)")
            # 🔥 FIX: Émettre scan_complete pour mettre à jour le store frontend
            ws_mgr = state.get_ws_manager()
            if ws_mgr:
                await ws_mgr.emit('scan_complete', {'timestamp': time.time()})
                await ws_mgr.emit('status', {'is_scanning': False})
        
        # Arrêter WebSocket
        price_prov = state.get_price_provider()
        if price_prov:
            try:
                await price_prov.stop_websocket()
                await add_log('INFO', 'WebSocket arrêté', 'Monitoring des prix désactivé')
            except Exception as e:
                logger.warning(f"Erreur arrêt WebSocket: {e}")
        
        return {'status': 'stopped', 'is_scanning': False}
    
    elif command == 'update_config':
        # 🔥 BIDIRECTIONNEL: Mettre à jour config avec validation complète (même logique que /api/config)
        from config import TRADING_CONFIG
        updated = {}
        pos_cfg = state.get_position_config()

        def _coerce_bool(v):
            if isinstance(v, bool):
                return v
            if v is None:
                return False
            if isinstance(v, (int, float)):
                return v != 0
            if isinstance(v, str):
                s = v.strip().lower()
                if s in ('true', '1', 'yes', 'y', 'on'):
                    return True
                if s in ('false', '0', 'no', 'n', 'off', ''):
                    return False
            return bool(v)
        
        # 🔥 Volume multiplier
        if 'volume_multiplier' in params:
            val = float(params['volume_multiplier'])
            val = max(0.1, min(2.0, val))  # Clamp 0.1-2.0
            TRADING_CONFIG['volume_multiplier'] = val
            updated['volume_multiplier'] = val
        
        # 🔥 Confluence
        if 'use_confluence' in params:
            TRADING_CONFIG['use_confluence'] = bool(params['use_confluence'])
            updated['use_confluence'] = TRADING_CONFIG['use_confluence']
        
        # 🔥 TP/SL Mode
        if 'tp_sl_mode' in params:
            mode = str(params['tp_sl_mode']).upper()
            # 🔥 FIX: Accepter aussi 'ESCALIER' comme mode valide
            if mode in ['FIXE', 'ATR', 'TP_MULTI', 'ESCALIER']:
                TRADING_CONFIG['tp_sl_mode'] = mode
                # 🔥 FIX: Ne pas appeler init_instances() car cela réinitialise tout, utiliser directement position_config et position_manager
                if pos_cfg:
                    pos_cfg.use_atr = (mode == 'ATR' or mode == 'TP_MULTI' or mode == 'ESCALIER')
                # 🔥 FIX: Mettre à jour aussi position_manager.config.use_atr si position_manager existe
                pos_mgr = state.get_position_manager()
                if pos_mgr:
                    pos_mgr.config.use_atr = (mode == 'ATR' or mode == 'TP_MULTI' or mode == 'ESCALIER')
                    
                    # 🔥 FIX: Recalculer TP/SL de la position active avec le nouveau mode
                    if pos_mgr.active_position and not pos_mgr.active_position.tp_escalier_enabled:
                        try:
                            from core.tp_sl import calculate_atr_levels, calculate_fixed_levels
                            position = pos_mgr.active_position
                            entry = position.entry
                            direction = position.direction
                            atr = position.atr
                            atr5m = position.atr5m
                            
                            # Recalculer TP/SL selon le nouveau mode
                            use_atr = (mode == 'ATR' or mode == 'TP_MULTI' or mode == 'ESCALIER')
                            if use_atr and atr:
                                sl, tp = calculate_atr_levels(
                                    entry=entry,
                                    atr=atr,
                                    atr5m=atr5m,
                                    direction=direction,
                                    config=pos_mgr.tpsl_config
                                )
                                logger.info(f"🔄 Recalcul TP/SL (mode ATR): TP={tp:.8f}, SL={sl:.8f}")
                            else:
                                sl, tp = calculate_fixed_levels(
                                    entry=entry,
                                    direction=direction,
                                    config=pos_mgr.tpsl_config
                                )
                                logger.info(f"🔄 Recalcul TP/SL (mode FIXE): TP={tp:.8f}, SL={sl:.8f}")
                            
                            # Mettre à jour la position
                            position.tp = tp
                            position.sl = sl
                            logger.info(f"✅ TP/SL recalculés pour position active: {position.symbol} {direction}")
                        except Exception as e:
                            logger.error(f"❌ Erreur recalcul TP/SL: {e}")
                
                updated['tp_sl_mode'] = mode
                logger.info(f"✅ Mode TP/SL mis à jour: {mode} (use_atr={pos_cfg.use_atr if pos_cfg else 'N/A'})")
        
        if 'tp_percent' in params:
            val = float(params['tp_percent'])
            TRADING_CONFIG['tp_percent'] = val
            if pos_cfg:
                pos_cfg.fixed_tp_pct = val
            updated['tp_percent'] = val
        
        if 'sl_percent' in params:
            val = float(params['sl_percent'])
            TRADING_CONFIG['sl_percent'] = val
            if pos_cfg:
                pos_cfg.fixed_sl_pct = val
            updated['sl_percent'] = val
        
        # 🔥 FIX: break_even_trigger
        if 'break_even_trigger' in params:
            val = float(params['break_even_trigger'])
            val = max(0.05, min(2.0, val))  # Clamp 0.05-2.0%
            TRADING_CONFIG['break_even_trigger'] = val
            if pos_cfg:
                pos_cfg.break_even_trigger = val
            updated['break_even_trigger'] = val
            logger.info(f"✅ break_even_trigger mis à jour: {val}%")
        
        # 🔥 FIX: trailing_distance
        if 'trailing_distance' in params:
            val = float(params['trailing_distance'])
            val = max(0.05, min(1.0, val))  # Clamp 0.05-1.0%
            TRADING_CONFIG['trailing_distance'] = val
            if pos_cfg:
                pos_cfg.trailing_distance = val
            updated['trailing_distance'] = val
            logger.info(f"✅ trailing_distance mis à jour: {val}%")
        
        # 🔥 4 seuils configurables
        if 'snr_threshold' in params:
            val = float(params['snr_threshold'])
            val = max(0.0, min(1.0, val))  # Clamp 0.0-1.0
            TRADING_CONFIG['snr_threshold'] = val
            updated['snr_threshold'] = val
        
        if 'breakout_threshold' in params:
            val = float(params['breakout_threshold'])
            val = max(0.0, min(1.0, val))  # Clamp 0.0-1.0
            TRADING_CONFIG['breakout_threshold'] = val
            updated['breakout_threshold'] = val
        
        if 'wick_ratio_max' in params:
            val = float(params['wick_ratio_max'])
            val = max(1.0, min(10.0, val))  # Clamp 1.0-10.0
            TRADING_CONFIG['wick_ratio_max'] = val
            updated['wick_ratio_max'] = val
        
        if 'di_gap_min' in params:
            val = float(params['di_gap_min'])
            val = max(0.0, min(50.0, val))  # Clamp 0.0-50.0
            TRADING_CONFIG['di_gap_min'] = val
            updated['di_gap_min'] = val
        
        if 'di_gap_adx_threshold' in params:
            val = float(params['di_gap_adx_threshold'])
            val = max(0.0, min(100.0, val))  # Clamp 0.0-100.0
            TRADING_CONFIG['di_gap_adx_threshold'] = val
            updated['di_gap_adx_threshold'] = val
        
        # 🔥 Seuils ATR optimal
        if 'optimal_atr_min_1m' in params:
            val = float(params['optimal_atr_min_1m'])
            val = max(0.01, min(1.0, val))  # Clamp 0.01-1.0%
            TRADING_CONFIG['optimal_atr_min_1m'] = val
            updated['optimal_atr_min_1m'] = val
        
        if 'optimal_atr_max_1m' in params:
            val = float(params['optimal_atr_max_1m'])
            val = max(0.1, min(5.0, val))  # Clamp 0.1-5.0%
            TRADING_CONFIG['optimal_atr_max_1m'] = val
            updated['optimal_atr_max_1m'] = val
        
        if 'optimal_atr_min_5m' in params:
            val = float(params['optimal_atr_min_5m'])
            val = max(0.01, min(2.0, val))  # Clamp 0.01-2.0%
            TRADING_CONFIG['optimal_atr_min_5m'] = val
            updated['optimal_atr_min_5m'] = val
        
        if 'optimal_atr_max_5m' in params:
            val = float(params['optimal_atr_max_5m'])
            val = max(0.5, min(10.0, val))  # Clamp 0.5-10.0%
            TRADING_CONFIG['optimal_atr_max_5m'] = val
            updated['optimal_atr_max_5m'] = val
        
        # 🔥 Trend timeframe
        if 'trend_timeframe' in params:
            val = str(params['trend_timeframe']).lower()
            valid_timeframes = ['5m', '15m', '30m', '1h']
            if val in valid_timeframes:
                TRADING_CONFIG['trend_timeframe'] = val
                updated['trend_timeframe'] = val
        
        # 🔥 Account size et risk per trade
        if 'account_size' in params:
            val = float(params['account_size'])
            val = max(100.0, min(100000.0, val))  # Clamp 100-100000
            TRADING_CONFIG['account_size'] = val
            updated['account_size'] = val
        
        if 'risk_per_trade' in params:
            val = float(params['risk_per_trade'])
            val = max(0.5, min(5.0, val))  # Clamp 0.5-5.0%
            TRADING_CONFIG['risk_per_trade'] = val
            updated['risk_per_trade'] = val
        
        # 🔥 Live Trading: default_leverage et max_latency_ms
        if 'default_leverage' in params:
            val = int(params['default_leverage'])
            val = max(1, min(50, val))  # Clamp 1-50x
            TRADING_CONFIG['default_leverage'] = val
            updated['default_leverage'] = val
        
        if 'max_latency_ms' in params:
            val = int(params['max_latency_ms'])
            val = max(100, min(5000, val))  # Clamp 100-5000ms
            TRADING_CONFIG['max_latency_ms'] = val
            updated['max_latency_ms'] = val
        
        # 🔥 FIX: Support min_score_required dans update_config WebSocket
        if 'min_score_required' in params:
            val = float(params['min_score_required'])
            val = max(1.0, min(20.0, val))  # Clamp 1.0-20.0
            TRADING_CONFIG['min_score_required'] = val
            updated['min_score_required'] = val
        
        # 🔥 FIX: Support max_slippage_pct dans update_config WebSocket
        if 'max_slippage_pct' in params:
            val = float(params['max_slippage_pct'])
            val = max(0.0, min(0.20, val))  # Clamp 0.0-0.20%
            TRADING_CONFIG['max_slippage_pct'] = val
            updated['max_slippage_pct'] = val
        
        # 🔥 BIDIRECTIONNEL: Patterns Techniques (use_breakout, use_snr, use_wick, use_divergence)
        if 'use_breakout' in params:
            TRADING_CONFIG['use_breakout'] = bool(params['use_breakout'])
            updated['use_breakout'] = TRADING_CONFIG['use_breakout']
        
        if 'use_snr' in params:
            TRADING_CONFIG['use_snr'] = bool(params['use_snr'])
            updated['use_snr'] = TRADING_CONFIG['use_snr']
        
        if 'use_wick' in params:
            TRADING_CONFIG['use_wick'] = bool(params['use_wick'])
            updated['use_wick'] = TRADING_CONFIG['use_wick']
        
        if 'use_divergence' in params:
            TRADING_CONFIG['use_divergence'] = bool(params['use_divergence'])
            updated['use_divergence'] = TRADING_CONFIG['use_divergence']
        
        # 🔥 BIDIRECTIONNEL: Patterns de Bougies
        if 'use_engulfing' in params:
            TRADING_CONFIG['use_engulfing'] = bool(params['use_engulfing'])
            updated['use_engulfing'] = TRADING_CONFIG['use_engulfing']
        
        if 'use_hammer' in params:
            TRADING_CONFIG['use_hammer'] = bool(params['use_hammer'])
            updated['use_hammer'] = TRADING_CONFIG['use_hammer']
        
        if 'use_shooting_star' in params:
            TRADING_CONFIG['use_shooting_star'] = bool(params['use_shooting_star'])
            updated['use_shooting_star'] = TRADING_CONFIG['use_shooting_star']
        
        if 'use_doji' in params:
            TRADING_CONFIG['use_doji'] = bool(params['use_doji'])
            updated['use_doji'] = TRADING_CONFIG['use_doji']
        
        if 'use_marubozu' in params:
            TRADING_CONFIG['use_marubozu'] = bool(params['use_marubozu'])
            updated['use_marubozu'] = TRADING_CONFIG['use_marubozu']
        
        if 'use_morning_star' in params:
            TRADING_CONFIG['use_morning_star'] = bool(params['use_morning_star'])
            updated['use_morning_star'] = TRADING_CONFIG['use_morning_star']
        
        if 'use_evening_star' in params:
            TRADING_CONFIG['use_evening_star'] = bool(params['use_evening_star'])
            updated['use_evening_star'] = TRADING_CONFIG['use_evening_star']
        
        # 🔥 BIDIRECTIONNEL: Paramètres TP/SL Escalier (TP_MULTI)
        if 'escalier_level1_pnl' in params:
            val = float(params['escalier_level1_pnl'])
            val = max(0.0, min(5.0, val))  # Clamp 0.0-5.0%
            TRADING_CONFIG['escalier_level1_pnl'] = val
            updated['escalier_level1_pnl'] = val
        
        if 'escalier_level1_size' in params:
            val = float(params['escalier_level1_size'])
            val = max(0.0, min(100.0, val))  # Clamp 0-100%
            TRADING_CONFIG['escalier_level1_size'] = val
            updated['escalier_level1_size'] = val
        
        if 'escalier_level2_pnl' in params:
            val = float(params['escalier_level2_pnl'])
            val = max(0.0, min(5.0, val))
            TRADING_CONFIG['escalier_level2_pnl'] = val
            updated['escalier_level2_pnl'] = val
        
        if 'escalier_level2_size' in params:
            val = float(params['escalier_level2_size'])
            val = max(0.0, min(100.0, val))
            TRADING_CONFIG['escalier_level2_size'] = val
            updated['escalier_level2_size'] = val
        
        if 'escalier_level3_pnl' in params:
            val = float(params['escalier_level3_pnl'])
            val = max(0.0, min(5.0, val))
            TRADING_CONFIG['escalier_level3_pnl'] = val
            updated['escalier_level3_pnl'] = val
        
        if 'escalier_level3_size' in params:
            val = float(params['escalier_level3_size'])
            val = max(0.0, min(100.0, val))
            TRADING_CONFIG['escalier_level3_size'] = val
            updated['escalier_level3_size'] = val
        
        if 'escalier_level4_pnl' in params:
            val = float(params['escalier_level4_pnl'])
            val = max(0.0, min(5.0, val))
            TRADING_CONFIG['escalier_level4_pnl'] = val
            updated['escalier_level4_pnl'] = val
        
        if 'escalier_level4_size' in params:
            val = float(params['escalier_level4_size'])
            val = max(0.0, min(100.0, val))
            TRADING_CONFIG['escalier_level4_size'] = val
            updated['escalier_level4_size'] = val
        
        # 🔥 BIDIRECTIONNEL: Trailing Stop
        if 'trailing_enabled' in params:
            TRADING_CONFIG['trailing_enabled'] = bool(params['trailing_enabled'])
            updated['trailing_enabled'] = TRADING_CONFIG['trailing_enabled']
        
        if 'trailing_trigger_pnl' in params:
            val = float(params['trailing_trigger_pnl'])
            val = max(0.0, min(5.0, val))  # Clamp 0.0-5.0%
            TRADING_CONFIG['trailing_trigger_pnl'] = val
            updated['trailing_trigger_pnl'] = val
        
        if 'trailing_atr_multiplier' in params:
            val = float(params['trailing_atr_multiplier'])
            val = max(0.1, min(5.0, val))  # Clamp 0.1-5.0x
            TRADING_CONFIG['trailing_atr_multiplier'] = val
            TRADING_CONFIG['trailing_distance_atr_mult'] = val  # Sync alias
            updated['trailing_atr_multiplier'] = val
        
        # 🔥 NOUVEAU: trailing_distance_atr_mult (alias clair pour trailing_atr_multiplier)
        if 'trailing_distance_atr_mult' in params:
            val = float(params['trailing_distance_atr_mult'])
            val = max(0.3, min(2.0, val))  # Clamp 0.3-2.0x
            TRADING_CONFIG['trailing_distance_atr_mult'] = val
            TRADING_CONFIG['trailing_atr_multiplier'] = val  # Sync avec ancien nom
            updated['trailing_distance_atr_mult'] = val
            updated['trailing_atr_multiplier'] = val  # Aussi notifier l'ancien
        
        if 'trailing_min_distance' in params:
            val = float(params['trailing_min_distance'])
            val = max(0.01, min(1.0, val))  # Clamp 0.01-1.0%
            TRADING_CONFIG['trailing_min_distance'] = val
            updated['trailing_min_distance'] = val
        
        # 🔥 FIX: use_slippage_calculation
        if 'use_slippage_calculation' in params:
            TRADING_CONFIG['use_slippage_calculation'] = bool(params['use_slippage_calculation'])
            # Mettre à jour position_config et position_manager.config directement
            if pos_cfg:
                pos_cfg.use_slippage_calculation = TRADING_CONFIG['use_slippage_calculation']
            pos_mgr = state.get_position_manager()
            if pos_mgr:
                pos_mgr.config.use_slippage_calculation = TRADING_CONFIG['use_slippage_calculation']
            updated['use_slippage_calculation'] = TRADING_CONFIG['use_slippage_calculation']
            logger.info(f"✅ use_slippage_calculation mis à jour: {TRADING_CONFIG['use_slippage_calculation']}")
        
        if 'trailing_max_distance' in params:
            val = float(params['trailing_max_distance'])
            val = max(0.01, min(5.0, val))  # Clamp 0.01-5.0%
            TRADING_CONFIG['trailing_max_distance'] = val
            updated['trailing_max_distance'] = val
        
        # 🔥 FIX: Mettre à jour dynamiquement le trailing_stop manager si paramètres trailing changés
        trailing_keys = ['trailing_enabled', 'trailing_trigger_pnl', 'trailing_atr_multiplier', 
                         'trailing_distance_atr_mult', 'trailing_min_distance', 'trailing_max_distance']
        pos_mgr = state.get_position_manager()
        if any(k in updated for k in trailing_keys) and pos_mgr and hasattr(pos_mgr, 'trailing_stop'):
            from core.position.trailing_stop import TrailingStopConfig
            pos_mgr.trailing_stop.config = TrailingStopConfig(
                enabled=TRADING_CONFIG.get('trailing_enabled', True),
                trigger_pnl=TRADING_CONFIG.get('trailing_trigger_pnl', 0.25),
                atr_multiplier=TRADING_CONFIG.get('trailing_atr_multiplier', 0.4),
                min_distance=TRADING_CONFIG.get('trailing_min_distance', 0.08),
                max_distance=TRADING_CONFIG.get('trailing_max_distance', 0.25)
            )
            logger.info(f"✅ TrailingStop config rechargée dynamiquement")
        
        # 🔥 BIDIRECTIONNEL: Partial TP
        if 'partial_tp_percent' in params:
            val = float(params['partial_tp_percent'])
            val = max(0.0, min(100.0, val))  # Clamp 0-100%
            TRADING_CONFIG['partial_tp_percent'] = val
            updated['partial_tp_percent'] = val
        
        # 🔥 BIDIRECTIONNEL: Paramètres ATR (atr_mult_tp, atr_mult_sl, atr_min, atr_max)
        if 'atr_mult_tp' in params:
            val = float(params['atr_mult_tp'])
            val = max(0.1, min(10.0, val))  # Clamp 0.1-10.0x
            TRADING_CONFIG['atr_mult_tp'] = val
            updated['atr_mult_tp'] = val
            if pos_cfg:
                pos_cfg.atr_mult_tp = val
        
        if 'atr_mult_sl' in params:
            val = float(params['atr_mult_sl'])
            val = max(0.1, min(10.0, val))  # Clamp 0.1-10.0x
            TRADING_CONFIG['atr_mult_sl'] = val
            updated['atr_mult_sl'] = val
            if pos_cfg:
                pos_cfg.atr_mult_sl = val
        
        if 'atr_min' in params:
            val = float(params['atr_min'])
            val = max(0.01, min(5.0, val))  # Clamp 0.01-5.0%
            TRADING_CONFIG['atr_min'] = val
            updated['atr_min'] = val
            if pos_cfg:
                pos_cfg.atr_min = val
        
        if 'atr_max' in params:
            val = float(params['atr_max'])
            val = max(0.1, min(10.0, val))  # Clamp 0.1-10.0%
            TRADING_CONFIG['atr_max'] = val
            updated['atr_max'] = val
            if pos_cfg:
                pos_cfg.atr_max = val
        
        # 🔥 Machine Learning Filter Configuration
        if 'ml_filter_enabled' in params:
            from config import ML_CONFIG
            ML_CONFIG['enabled'] = bool(params['ml_filter_enabled'])
            TRADING_CONFIG['ml_filter_enabled'] = ML_CONFIG['enabled']
            updated['ml_filter_enabled'] = ML_CONFIG['enabled']
            logger.info(f"✅ ML Filter enabled: {ML_CONFIG['enabled']}")
        
        if 'ml_min_confidence' in params:
            from config import ML_CONFIG
            val = float(params['ml_min_confidence'])
            val = max(0.50, min(0.90, val))  # Clamp 0.50-0.90 (50%-90%)
            ML_CONFIG['min_confidence'] = val
            TRADING_CONFIG['ml_min_confidence'] = val
            updated['ml_min_confidence'] = val
            logger.info(f"✅ ML min confidence: {val*100:.0f}%")
        
        # 🔥 ML Mode (STRICT, SOFT, NEGATIVE)
        if 'ml_filter_mode' in params:
            from config import ML_CONFIG
            mode = str(params['ml_filter_mode']).upper()
            if mode in ['STRICT', 'SOFT', 'NEGATIVE']:
                ML_CONFIG['mode'] = mode
                TRADING_CONFIG['ml_filter_mode'] = mode
                updated['ml_filter_mode'] = mode
                logger.info(f"✅ ML filter mode: {mode}")
        
        # 🔥 ML Loss Threshold (pour mode NEGATIVE)
        if 'ml_loss_threshold' in params:
            from config import ML_CONFIG
            val = float(params['ml_loss_threshold'])
            val = max(0.30, min(0.80, val))  # Clamp 0.30-0.80
            ML_CONFIG['loss_threshold'] = val
            TRADING_CONFIG['ml_loss_threshold'] = val
            updated['ml_loss_threshold'] = val
            logger.info(f"✅ ML loss threshold: {val*100:.0f}%")

        # 🔥 ML Hyperparameters (XGBoost)
        if 'ml_max_depth' in params:
            val = int(params['ml_max_depth'])
            val = max(2, min(8, val))  # Clamp 2-8
            TRADING_CONFIG['ml_max_depth'] = val
            updated['ml_max_depth'] = val
            logger.info(f"✅ ML max_depth: {val}")

        if 'ml_min_child_weight' in params:
            val = int(params['ml_min_child_weight'])
            val = max(1, min(15, val))  # Clamp 1-15
            TRADING_CONFIG['ml_min_child_weight'] = val
            updated['ml_min_child_weight'] = val
            logger.info(f"✅ ML min_child_weight: {val}")

        if 'ml_reg_alpha' in params:
            val = float(params['ml_reg_alpha'])
            val = max(0.0, min(5.0, val))  # Clamp 0.0-5.0
            TRADING_CONFIG['ml_reg_alpha'] = val
            updated['ml_reg_alpha'] = val
            logger.info(f"✅ ML reg_alpha (L1): {val}")

        if 'ml_reg_lambda' in params:
            val = float(params['ml_reg_lambda'])
            val = max(0.0, min(10.0, val))  # Clamp 0.0-10.0
            TRADING_CONFIG['ml_reg_lambda'] = val
            updated['ml_reg_lambda'] = val
            logger.info(f"✅ ML reg_lambda (L2): {val}")

        if 'ml_subsample' in params:
            val = float(params['ml_subsample'])
            val = max(0.5, min(1.0, val))  # Clamp 0.5-1.0
            TRADING_CONFIG['ml_subsample'] = val
            updated['ml_subsample'] = val
            logger.info(f"✅ ML subsample: {val*100:.0f}%")

        if 'ml_colsample_bytree' in params:
            val = float(params['ml_colsample_bytree'])
            val = max(0.5, min(1.0, val))  # Clamp 0.5-1.0
            TRADING_CONFIG['ml_colsample_bytree'] = val
            updated['ml_colsample_bytree'] = val
            logger.info(f"✅ ML colsample_bytree: {val*100:.0f}%")

        if 'ml_colsample_bylevel' in params:
            val = float(params['ml_colsample_bylevel'])
            val = max(0.5, min(1.0, val))  # Clamp 0.5-1.0
            TRADING_CONFIG['ml_colsample_bylevel'] = val
            updated['ml_colsample_bylevel'] = val
            logger.info(f"✅ ML colsample_bylevel: {val*100:.0f}%")

        if 'ml_gamma' in params:
            val = float(params['ml_gamma'])
            val = max(0.0, min(5.0, val))  # Clamp 0.0-5.0
            TRADING_CONFIG['ml_gamma'] = val
            updated['ml_gamma'] = val
            logger.info(f"✅ ML gamma: {val}")

        if 'ml_scale_pos_weight' in params:
            val = float(params['ml_scale_pos_weight'])
            # 🔥 Aligné sur le slider frontend (0.5 - 2.0)
            val = max(0.5, min(2.0, val))
            TRADING_CONFIG['ml_scale_pos_weight'] = val
            updated['ml_scale_pos_weight'] = val
            logger.info(f"✅ ML scale_pos_weight: {val}")

        if 'ml_n_estimators' in params:
            val = int(params['ml_n_estimators'])
            val = max(50, min(800, val))  # Clamp 50-800 (aligné avec UI)
            TRADING_CONFIG['ml_n_estimators'] = val
            updated['ml_n_estimators'] = val
            logger.info(f"✅ ML n_estimators: {val}")

        if 'ml_learning_rate' in params:
            val = float(params['ml_learning_rate'])
            # 🔥 Aligné sur le slider frontend (0.001 - 0.2)
            val = max(0.001, min(0.2, val))
            TRADING_CONFIG['ml_learning_rate'] = val
            updated['ml_learning_rate'] = val
            logger.info(f"✅ ML learning_rate: {val}")

        # 🤖🔥 ML V2 (Régression PNL%)
        # --- Filtres / toggles ---
        if 'ml_v2_filter_enabled' in params:
            TRADING_CONFIG['ml_v2_filter_enabled'] = bool(params['ml_v2_filter_enabled'])
            updated['ml_v2_filter_enabled'] = TRADING_CONFIG['ml_v2_filter_enabled']

        if 'ml_v2_filter_marginal_trades' in params:
            TRADING_CONFIG['ml_v2_filter_marginal_trades'] = bool(params['ml_v2_filter_marginal_trades'])
            updated['ml_v2_filter_marginal_trades'] = TRADING_CONFIG['ml_v2_filter_marginal_trades']

        # --- Training params ---
        ml_v2_int_params = {
            'ml_v2_timeframe_days': (30, 730),
            'ml_v2_max_features': (5, 300),
            'ml_v2_n_estimators': (100, 2000),
            'ml_v2_max_depth': (2, 10),
            'ml_v2_min_child_weight': (1, 100)
        }
        for key, (min_val, max_val) in ml_v2_int_params.items():
            if key in params:
                val = int(params[key])
                val = max(min_val, min(max_val, val))
                TRADING_CONFIG[key] = val
                updated[key] = val

        ml_v2_float_params = {
            'ml_v2_min_confidence': (0.0, 1.0),
            'ml_v2_marginal_threshold': (0.01, 2.0),
            'ml_v2_test_size': (0.05, 0.45),
            'ml_v2_validation_size': (0.05, 0.35),
            'ml_v2_learning_rate': (0.0005, 0.5),
            'ml_v2_reg_alpha': (0.0, 10.0),
            'ml_v2_reg_lambda': (0.0, 15.0),
            'ml_v2_subsample': (0.3, 1.0),
            'ml_v2_colsample_bytree': (0.3, 1.0),
            'ml_v2_gamma': (0.0, 5.0)
        }
        for key, (min_val, max_val) in ml_v2_float_params.items():
            if key in params:
                val = float(params[key])
                val = max(min_val, min(max_val, val))
                TRADING_CONFIG[key] = val
                updated[key] = val

        # 🔥 OPT #14-19: Filtres Avancés
        # --- OPT #14: Scan Interval ---
        if 'scan_interval' in params:
            val = int(params['scan_interval'])
            val = max(15, min(120, val))  # Clamp 15-120s
            TRADING_CONFIG['scan_interval'] = val
            updated['scan_interval'] = val
            logger.info(f"✅ scan_interval mis à jour: {val}s")
        
        # --- OPT #15: Anti-Whipsaw ---
        if 'use_anti_whipsaw' in params:
            TRADING_CONFIG['use_anti_whipsaw'] = bool(params['use_anti_whipsaw'])
            updated['use_anti_whipsaw'] = TRADING_CONFIG['use_anti_whipsaw']
        
        if 'whipsaw_lookback' in params:
            val = int(params['whipsaw_lookback'])
            val = max(3, min(10, val))  # Clamp 3-10
            TRADING_CONFIG['whipsaw_lookback'] = val
            updated['whipsaw_lookback'] = val
        
        if 'whipsaw_threshold_pct' in params:
            val = float(params['whipsaw_threshold_pct'])
            val = max(0.1, min(0.5, val))  # Clamp 0.1-0.5%
            TRADING_CONFIG['whipsaw_threshold_pct'] = val
            updated['whipsaw_threshold_pct'] = val
        
        if 'whipsaw_max_alternations' in params:
            val = int(params['whipsaw_max_alternations'])
            val = max(2, min(5, val))  # Clamp 2-5
            TRADING_CONFIG['whipsaw_max_alternations'] = val
            updated['whipsaw_max_alternations'] = val
        
        # --- OPT #16: Retest Breakout Confirmation ---
        if 'use_retest_confirmation' in params:
            TRADING_CONFIG['use_retest_confirmation'] = bool(params['use_retest_confirmation'])
            updated['use_retest_confirmation'] = TRADING_CONFIG['use_retest_confirmation']
        
        if 'retest_tolerance_pct' in params:
            val = float(params['retest_tolerance_pct'])
            val = max(0.05, min(0.5, val))  # Clamp 0.05-0.5%
            TRADING_CONFIG['retest_tolerance_pct'] = val
            updated['retest_tolerance_pct'] = val
        
        if 'retest_timeout_seconds' in params:
            val = int(params['retest_timeout_seconds'])
            val = max(60, min(600, val))  # Clamp 60-600s
            TRADING_CONFIG['retest_timeout_seconds'] = val
            updated['retest_timeout_seconds'] = val
        
        # --- OPT #17: Cooldown Post-Trade ---
        if 'use_cooldown' in params:
            TRADING_CONFIG['use_cooldown'] = bool(params['use_cooldown'])
            updated['use_cooldown'] = TRADING_CONFIG['use_cooldown']
        
        if 'cooldown_seconds' in params:
            val = int(params['cooldown_seconds'])
            val = max(10, min(120, val))  # Clamp 10-120s
            TRADING_CONFIG['cooldown_seconds'] = val
            updated['cooldown_seconds'] = val
        
        if 'cooldown_same_symbol' in params:
            val = int(params['cooldown_same_symbol'])
            val = max(30, min(300, val))  # Clamp 30-300s
            TRADING_CONFIG['cooldown_same_symbol'] = val
            updated['cooldown_same_symbol'] = val
        
        # --- OPT #18: Candle Close Confirmation ---
        if 'use_candle_close' in params:
            TRADING_CONFIG['use_candle_close'] = bool(params['use_candle_close'])
            updated['use_candle_close'] = TRADING_CONFIG['use_candle_close']
        
        if 'candle_close_threshold_seconds' in params:
            val = int(params['candle_close_threshold_seconds'])
            val = max(3, min(15, val))  # Clamp 3-15s
            TRADING_CONFIG['candle_close_threshold_seconds'] = val
            updated['candle_close_threshold_seconds'] = val
        
        # --- OPT #19: Momentum Continuity ---
        if 'use_momentum_continuity' in params:
            TRADING_CONFIG['use_momentum_continuity'] = bool(params['use_momentum_continuity'])
            updated['use_momentum_continuity'] = TRADING_CONFIG['use_momentum_continuity']
        
        if 'momentum_lookback' in params:
            val = int(params['momentum_lookback'])
            val = max(2, min(10, val))  # Clamp 2-10
            TRADING_CONFIG['momentum_lookback'] = val
            updated['momentum_lookback'] = val
        
        # --- OPT #20: Micro-confirmation ---
        if 'use_micro_confirmation' in params:
            TRADING_CONFIG['use_micro_confirmation'] = bool(params['use_micro_confirmation'])
            updated['use_micro_confirmation'] = TRADING_CONFIG['use_micro_confirmation']
            logger.info(f"✅ use_micro_confirmation: {TRADING_CONFIG['use_micro_confirmation']}")
        
        if 'micro_confirmation_delay_ms' in params:
            val = int(params['micro_confirmation_delay_ms'])
            val = max(100, min(1000, val))  # Clamp 100-1000ms
            TRADING_CONFIG['micro_confirmation_delay_ms'] = val
            updated['micro_confirmation_delay_ms'] = val
            logger.info(f"✅ micro_confirmation_delay_ms: {val}ms")
        
        # 🔥 Filtre RSI Final (bloque trades contre-logiques)
        if 'rsi_final_filter_enabled' in params:
            TRADING_CONFIG['rsi_final_filter_enabled'] = bool(params['rsi_final_filter_enabled'])
            updated['rsi_final_filter_enabled'] = TRADING_CONFIG['rsi_final_filter_enabled']
            logger.info(f"✅ rsi_final_filter_enabled: {TRADING_CONFIG['rsi_final_filter_enabled']}")
        
        if 'rsi_final_long_max' in params:
            val = int(params['rsi_final_long_max'])
            val = max(50, min(85, val))  # Clamp 50-85
            TRADING_CONFIG['rsi_final_long_max'] = val
            updated['rsi_final_long_max'] = val
            logger.info(f"✅ rsi_final_long_max: {val}")
        
        if 'rsi_final_short_min' in params:
            val = int(params['rsi_final_short_min'])
            val = max(15, min(50, val))  # Clamp 15-50
            TRADING_CONFIG['rsi_final_short_min'] = val
            updated['rsi_final_short_min'] = val
            logger.info(f"✅ rsi_final_short_min: {val}")

        # 🔥 GradientBoosting (Modèle Optimisé 64-69% accuracy)
        if 'gb_filter_enabled' in params:
            TRADING_CONFIG['gb_filter_enabled'] = bool(params['gb_filter_enabled'])
            updated['gb_filter_enabled'] = TRADING_CONFIG['gb_filter_enabled']
            logger.info(f"✅ GB filter enabled: {TRADING_CONFIG['gb_filter_enabled']}")
        
        if 'gb_min_confidence' in params:
            val = float(params['gb_min_confidence'])
            val = max(0.25, min(0.80, val))  # Clamp 25%-80% (comme le slider frontend)
            TRADING_CONFIG['gb_min_confidence'] = val
            updated['gb_min_confidence'] = val
            logger.info(f"✅ GB min confidence: {val*100:.0f}%")
        
        if 'gb_n_estimators' in params:
            val = int(params['gb_n_estimators'])
            val = max(50, min(500, val))  # Clamp 50-500
            TRADING_CONFIG['gb_n_estimators'] = val
            updated['gb_n_estimators'] = val
            logger.info(f"✅ GB n_estimators: {val}")
        
        if 'gb_max_depth' in params:
            val = int(params['gb_max_depth'])
            val = max(2, min(6, val))  # Clamp 2-6
            TRADING_CONFIG['gb_max_depth'] = val
            updated['gb_max_depth'] = val
            logger.info(f"✅ GB max_depth: {val}")
        
        if 'gb_learning_rate' in params:
            val = float(params['gb_learning_rate'])
            val = max(0.01, min(0.3, val))  # Clamp 0.01-0.3
            TRADING_CONFIG['gb_learning_rate'] = val
            updated['gb_learning_rate'] = val
            logger.info(f"✅ GB learning_rate: {val}")
        
        if 'gb_min_samples_split' in params:
            val = int(params['gb_min_samples_split'])
            val = max(5, min(50, val))  # Clamp 5-50
            TRADING_CONFIG['gb_min_samples_split'] = val
            updated['gb_min_samples_split'] = val
            logger.info(f"✅ GB min_samples_split: {val}")
        
        if 'gb_min_samples_leaf' in params:
            val = int(params['gb_min_samples_leaf'])
            val = max(5, min(50, val))  # Clamp 5-50
            TRADING_CONFIG['gb_min_samples_leaf'] = val
            updated['gb_min_samples_leaf'] = val
            logger.info(f"✅ GB min_samples_leaf: {val}")
        
        if 'gb_subsample' in params:
            val = float(params['gb_subsample'])
            val = max(0.5, min(1.0, val))  # Clamp 0.5-1.0
            TRADING_CONFIG['gb_subsample'] = val
            updated['gb_subsample'] = val
            logger.info(f"✅ GB subsample: {val}")
        
        if 'gb_max_features' in params:
            val = params['gb_max_features']
            # Gérer les valeurs string valides pour GradientBoosting
            if isinstance(val, str):
                if val in ['sqrt', 'log2', 'auto', None]:
                    TRADING_CONFIG['gb_max_features'] = val
                    updated['gb_max_features'] = val
                    logger.info(f"✅ GB max_features: {val}")
                else:
                    logger.warning(f"⚠️ GB max_features invalide: {val}, valeurs valides: sqrt, log2, auto, ou nombre 0.3-1.0")
            else:
                # Valeur numérique (legacy)
                val = float(val)
                val = max(0.3, min(1.0, val))  # Clamp 0.3-1.0
                TRADING_CONFIG['gb_max_features'] = val
                updated['gb_max_features'] = val
                logger.info(f"✅ GB max_features: {val}")
        
        if 'gb_model_type' in params:
            val = str(params['gb_model_type'])
            if val in ['gb', 'histgb']:
                TRADING_CONFIG['gb_model_type'] = val
                updated['gb_model_type'] = val
                logger.info(f"✅ GB model_type: {val} ({'HistGradientBoosting' if val == 'histgb' else 'GradientBoosting'})")

        # 🔥 HistGB Hyperparameters (max_iter, l2_regularization)
        if 'gb_max_iter' in params:
            val = int(params['gb_max_iter'])
            val = max(50, min(500, val))  # Clamp 50-500
            TRADING_CONFIG['gb_max_iter'] = val
            updated['gb_max_iter'] = val
            logger.info(f"✅ GB max_iter: {val}")
        
        if 'gb_l2_regularization' in params:
            val = float(params['gb_l2_regularization'])
            val = max(0.1, min(2.0, val))  # Clamp 0.1-2.0
            TRADING_CONFIG['gb_l2_regularization'] = val
            updated['gb_l2_regularization'] = val
            logger.info(f"✅ GB l2_regularization: {val}")

        # 🔥 ML Calibration
        if 'ml_calibration_enabled' in params:
            TRADING_CONFIG['ml_calibration_enabled'] = bool(params['ml_calibration_enabled'])
            updated['ml_calibration_enabled'] = TRADING_CONFIG['ml_calibration_enabled']
            logger.info(f"✅ ml_calibration_enabled: {TRADING_CONFIG['ml_calibration_enabled']}")
        
        if 'ml_calib_min_winrate' in params:
            val = int(params['ml_calib_min_winrate'])
            val = max(30, min(60, val))  # Clamp 30-60
            TRADING_CONFIG['ml_calib_min_winrate'] = val
            updated['ml_calib_min_winrate'] = val
            logger.info(f"✅ ml_calib_min_winrate: {val}%")
        
        if 'ml_calib_live_weight' in params:
            val = float(params['ml_calib_live_weight'])
            val = max(0.5, min(1.0, val))  # Clamp 0.5-1.0
            TRADING_CONFIG['ml_calib_live_weight'] = val
            updated['ml_calib_live_weight'] = val
            logger.info(f"✅ ml_calib_live_weight: {val}")
        
        if 'ml_calib_dryrun_weight' in params:
            val = float(params['ml_calib_dryrun_weight'])
            val = max(0.0, min(1.0, val))  # Clamp 0.0-1.0
            TRADING_CONFIG['ml_calib_dryrun_weight'] = val
            updated['ml_calib_dryrun_weight'] = val
            logger.info(f"✅ ml_calib_dryrun_weight: {val}")
        
        if 'ml_calib_decay_days' in params:
            val = int(params['ml_calib_decay_days'])
            val = max(7, min(60, val))  # Clamp 7-60
            TRADING_CONFIG['ml_calib_decay_days'] = val
            updated['ml_calib_decay_days'] = val
            logger.info(f"✅ ml_calib_decay_days: {val}j")
        
        if 'ml_calib_min_trades' in params:
            val = int(params['ml_calib_min_trades'])
            val = max(10, min(100, val))  # Clamp 10-100
            TRADING_CONFIG['ml_calib_min_trades'] = val
            updated['ml_calib_min_trades'] = val
            logger.info(f"✅ ml_calib_min_trades: {val}")

        # 🔥 Phase 2D: Threshold Optimizer & Drift Detection
        if 'threshold_optimizer_enabled' in params:
            TRADING_CONFIG['threshold_optimizer_enabled'] = bool(params['threshold_optimizer_enabled'])
            updated['threshold_optimizer_enabled'] = TRADING_CONFIG['threshold_optimizer_enabled']
            logger.info(f"✅ threshold_optimizer_enabled: {TRADING_CONFIG['threshold_optimizer_enabled']}")
        
        if 'threshold_min' in params:
            val = float(params['threshold_min'])
            val = max(0.25, min(0.60, val))  # Clamp 25-60% (aligné avec frontend)
            TRADING_CONFIG['threshold_min'] = val
            updated['threshold_min'] = val
            logger.info(f"✅ threshold_min: {val*100:.0f}%")
            
            # 🔥 Propager à l'instance
            try:
                from core.ml import get_threshold_optimizer
                # Appeler le getter met à jour l'instance avec la nouvelle config
                get_threshold_optimizer()
            except Exception as e:
                logger.warning(f"⚠️ Erreur propagation threshold_min: {e}")
        
        if 'threshold_max' in params:
            val = float(params['threshold_max'])
            val = max(0.40, min(0.80, val))  # Clamp 40-80% (aligné avec frontend)
            TRADING_CONFIG['threshold_max'] = val
            updated['threshold_max'] = val
            logger.info(f"✅ threshold_max: {val*100:.0f}%")

            # 🔥 Propager à l'instance
            try:
                from core.ml import get_threshold_optimizer
                get_threshold_optimizer()
            except Exception as e:
                logger.warning(f"⚠️ Erreur propagation threshold_max: {e}")
        
        if 'drift_detection_enabled' in params:
            TRADING_CONFIG['drift_detection_enabled'] = bool(params['drift_detection_enabled'])
            updated['drift_detection_enabled'] = TRADING_CONFIG['drift_detection_enabled']
            logger.info(f"✅ drift_detection_enabled: {TRADING_CONFIG['drift_detection_enabled']}")

        # 🔥 PHASE 8: Sizing Adaptatif par Paire/Session
        if 'adaptive_sizing_enabled' in params:
            TRADING_CONFIG['adaptive_sizing_enabled'] = bool(params['adaptive_sizing_enabled'])
            updated['adaptive_sizing_enabled'] = TRADING_CONFIG['adaptive_sizing_enabled']
            logger.info(f"✅ adaptive_sizing_enabled: {TRADING_CONFIG['adaptive_sizing_enabled']}")
        
        if 'adaptive_sizing_min_trades' in params:
            val = int(params['adaptive_sizing_min_trades'])
            val = max(2, min(10, val))  # Clamp 2-10
            TRADING_CONFIG['adaptive_sizing_min_trades'] = val
            updated['adaptive_sizing_min_trades'] = val
        
        # Seuils de Win Rate
        adaptive_sizing_wr_params = {
            'adaptive_sizing_excellent_wr': (0.60, 0.95),
            'adaptive_sizing_good_wr': (0.50, 0.80),
            'adaptive_sizing_poor_wr': (0.20, 0.50),
            'adaptive_sizing_very_poor_wr': (0.10, 0.40)
        }
        for key, (min_val, max_val) in adaptive_sizing_wr_params.items():
            if key in params:
                val = float(params[key])
                val = max(min_val, min(max_val, val))
                TRADING_CONFIG[key] = val
                updated[key] = val
        
        # Multiplicateurs de sizing
        adaptive_sizing_mult_params = {
            'adaptive_sizing_excellent_mult': (1.0, 2.0),
            'adaptive_sizing_good_mult': (1.0, 1.75),
            'adaptive_sizing_normal_mult': (0.8, 1.2),
            'adaptive_sizing_poor_mult': (0.3, 1.0),
            'adaptive_sizing_very_poor_mult': (0.2, 0.8),
            'adaptive_sizing_max_mult': (1.0, 3.0),
            'adaptive_sizing_min_mult': (0.1, 1.0)
        }
        for key, (min_val, max_val) in adaptive_sizing_mult_params.items():
            if key in params:
                val = float(params[key])
                val = max(min_val, min(max_val, val))
                TRADING_CONFIG[key] = val
                updated[key] = val
        
        if 'adaptive_sizing_reset_hours' in params:
            val = int(params['adaptive_sizing_reset_hours'])
            val = max(1, min(24, val))  # Clamp 1-24h
            TRADING_CONFIG['adaptive_sizing_reset_hours'] = val
            updated['adaptive_sizing_reset_hours'] = val
        
        if 'adaptive_sizing_reset_big_loss' in params:
            TRADING_CONFIG['adaptive_sizing_reset_big_loss'] = bool(params['adaptive_sizing_reset_big_loss'])
            updated['adaptive_sizing_reset_big_loss'] = TRADING_CONFIG['adaptive_sizing_reset_big_loss']
        
        if 'adaptive_sizing_big_loss_threshold' in params:
            val = float(params['adaptive_sizing_big_loss_threshold'])
            val = max(-10.0, min(-0.5, val))  # Clamp -10% à -0.5%
            TRADING_CONFIG['adaptive_sizing_big_loss_threshold'] = val
            updated['adaptive_sizing_big_loss_threshold'] = val
        
        # 🔥 Si un paramètre adaptive_sizing a changé, recharger la config du manager
        adaptive_sizing_keys = [k for k in updated.keys() if k.startswith('adaptive_sizing_')]
        if adaptive_sizing_keys:
            try:
                from core.position.adaptive_sizing import get_adaptive_sizing_manager
                manager = get_adaptive_sizing_manager()
                manager.reload_config()
                logger.info(f"✅ AdaptiveSizingManager config rechargée: {adaptive_sizing_keys}")
            except Exception as e:
                logger.warning(f"⚠️ Erreur reload AdaptiveSizingManager: {e}")

        # 🔥 HYBRID INTELLIGENT: Break-Even ATR
        if 'break_even_use_atr' in params:
            TRADING_CONFIG['break_even_use_atr'] = bool(params['break_even_use_atr'])
            updated['break_even_use_atr'] = TRADING_CONFIG['break_even_use_atr']
            logger.info(f"✅ break_even_use_atr: {TRADING_CONFIG['break_even_use_atr']}")
        
        if 'break_even_atr_mult' in params:
            val = float(params['break_even_atr_mult'])
            val = max(0.1, min(3.0, val))  # Clamp 0.1-3.0
            TRADING_CONFIG['break_even_atr_mult'] = val
            updated['break_even_atr_mult'] = val
            logger.info(f"✅ break_even_atr_mult: {val}")

        # 🔥 HYBRID INTELLIGENT: Trailing ATR Trigger
        if 'trailing_use_atr_trigger' in params:
            TRADING_CONFIG['trailing_use_atr_trigger'] = bool(params['trailing_use_atr_trigger'])
            updated['trailing_use_atr_trigger'] = TRADING_CONFIG['trailing_use_atr_trigger']
            logger.info(f"✅ trailing_use_atr_trigger: {TRADING_CONFIG['trailing_use_atr_trigger']}")
        
        if 'trailing_trigger_atr_mult' in params:
            val = float(params['trailing_trigger_atr_mult'])
            val = max(0.1, min(5.0, val))  # Clamp 0.1-5.0
            TRADING_CONFIG['trailing_trigger_atr_mult'] = val
            updated['trailing_trigger_atr_mult'] = val
            logger.info(f"✅ trailing_trigger_atr_mult: {val}")

        # 🔥 HYBRID INTELLIGENT: Stagnation Exit (Time Decay)
        if 'stagnation_exit_enabled' in params:
            TRADING_CONFIG['stagnation_exit_enabled'] = bool(params['stagnation_exit_enabled'])
            updated['stagnation_exit_enabled'] = TRADING_CONFIG['stagnation_exit_enabled']
            logger.info(f"✅ stagnation_exit_enabled: {TRADING_CONFIG['stagnation_exit_enabled']}")
        
        if 'stagnation_exit_timeout_seconds' in params:
            val = int(params['stagnation_exit_timeout_seconds'])
            val = max(30, min(600, val))  # Clamp 30s-600s (10min)
            TRADING_CONFIG['stagnation_exit_timeout_seconds'] = val
            updated['stagnation_exit_timeout_seconds'] = val
            logger.info(f"✅ stagnation_exit_timeout_seconds: {val}")
        
        if 'stagnation_exit_min_pnl_to_stay' in params:
            val = float(params['stagnation_exit_min_pnl_to_stay'])
            val = max(0.01, min(1.0, val))  # Clamp 0.01-1.0%
            TRADING_CONFIG['stagnation_exit_min_pnl_to_stay'] = val
            updated['stagnation_exit_min_pnl_to_stay'] = val
            logger.info(f"✅ stagnation_exit_min_pnl_to_stay: {val}")
        
        if 'stagnation_exit_max_loss_to_exit' in params:
            val = float(params['stagnation_exit_max_loss_to_exit'])
            val = max(-1.0, min(0.0, val))  # Clamp -1.0% à 0%
            TRADING_CONFIG['stagnation_exit_max_loss_to_exit'] = val
            updated['stagnation_exit_max_loss_to_exit'] = val
            logger.info(f"✅ stagnation_exit_max_loss_to_exit: {val}")

        # 🔥 STAGNATION POSITIVE EXIT (sortie anticipée en profit)
        if 'stagnation_positive_exit_enabled' in params:
            TRADING_CONFIG['stagnation_positive_exit_enabled'] = bool(params['stagnation_positive_exit_enabled'])
            updated['stagnation_positive_exit_enabled'] = TRADING_CONFIG['stagnation_positive_exit_enabled']
            logger.info(f"✅ stagnation_positive_exit_enabled: {TRADING_CONFIG['stagnation_positive_exit_enabled']}")
        
        if 'stagnation_positive_threshold' in params:
            val = float(params['stagnation_positive_threshold'])
            val = max(0.01, min(0.20, val))  # Clamp 0.01-0.20%
            TRADING_CONFIG['stagnation_positive_threshold'] = val
            updated['stagnation_positive_threshold'] = val
            logger.info(f"✅ stagnation_positive_threshold: {val}%")
        
        if 'stagnation_positive_timeout_seconds' in params:
            val = int(params['stagnation_positive_timeout_seconds'])
            val = max(30, min(120, val))  # Clamp 30s-120s (doit être < timeout normal)
            TRADING_CONFIG['stagnation_positive_timeout_seconds'] = val
            updated['stagnation_positive_timeout_seconds'] = val
            logger.info(f"✅ stagnation_positive_timeout_seconds: {val}s")
        
        if 'stagnation_use_mfe_tracking' in params:
            TRADING_CONFIG['stagnation_use_mfe_tracking'] = bool(params['stagnation_use_mfe_tracking'])
            updated['stagnation_use_mfe_tracking'] = TRADING_CONFIG['stagnation_use_mfe_tracking']
            logger.info(f"✅ stagnation_use_mfe_tracking: {TRADING_CONFIG['stagnation_use_mfe_tracking']}")
        
        if 'stagnation_mfe_pullback_pct' in params:
            val = float(params['stagnation_mfe_pullback_pct'])
            val = max(0.03, min(0.25, val))  # Clamp 0.03-0.25%
            TRADING_CONFIG['stagnation_mfe_pullback_pct'] = val
            updated['stagnation_mfe_pullback_pct'] = val
            logger.info(f"✅ stagnation_mfe_pullback_pct: {val}%")

        # 🎯 TRAILING MFE (SL→BE quand MFE atteint seuil)
        if 'trailing_mfe_enabled' in params:
            TRADING_CONFIG['trailing_mfe_enabled'] = bool(params['trailing_mfe_enabled'])
            updated['trailing_mfe_enabled'] = TRADING_CONFIG['trailing_mfe_enabled']
            logger.info(f"✅ trailing_mfe_enabled: {TRADING_CONFIG['trailing_mfe_enabled']}")

        if 'trailing_mfe_trigger_pct' in params:
            val = float(params['trailing_mfe_trigger_pct'])
            val = max(0.05, min(0.50, val))  # Clamp 0.05-0.50%
            TRADING_CONFIG['trailing_mfe_trigger_pct'] = val
            updated['trailing_mfe_trigger_pct'] = val
            logger.info(f"✅ trailing_mfe_trigger_pct: {val}%")

        if 'trailing_mfe_lock_in_pct' in params:
            val = float(params['trailing_mfe_lock_in_pct'])
            val = max(0.0, min(0.50, val))  # Clamp 0.0-0.50%
            TRADING_CONFIG['trailing_mfe_lock_in_pct'] = val
            updated['trailing_mfe_lock_in_pct'] = val
            logger.info(f"✅ trailing_mfe_lock_in_pct: {val}%")

        if 'partial_tp_be_lock_in_pct' in params:
            val = float(params['partial_tp_be_lock_in_pct'])
            val = max(0.0, min(0.50, val))  # Clamp 0.0-0.50%
            TRADING_CONFIG['partial_tp_be_lock_in_pct'] = val
            updated['partial_tp_be_lock_in_pct'] = val
            logger.info(f"✅ partial_tp_be_lock_in_pct: {val}%")

        # 🔬 ML Calibration Parameters
        if 'ml_calibration_enabled' in params:
            TRADING_CONFIG['ml_calibration_enabled'] = bool(params['ml_calibration_enabled'])
            updated['ml_calibration_enabled'] = TRADING_CONFIG['ml_calibration_enabled']
            logger.info(f"✅ ml_calibration_enabled: {TRADING_CONFIG['ml_calibration_enabled']}")
        
        if 'ml_calib_live_weight' in params:
            val = float(params['ml_calib_live_weight'])
            val = max(0.5, min(1.0, val))  # Clamp 0.5-1.0
            TRADING_CONFIG['ml_calib_live_weight'] = val
            updated['ml_calib_live_weight'] = val
            logger.info(f"✅ ml_calib_live_weight: {val}")
        
        if 'ml_calib_dryrun_weight' in params:
            val = float(params['ml_calib_dryrun_weight'])
            val = max(0.0, min(1.0, val))  # Clamp 0.0-1.0
            TRADING_CONFIG['ml_calib_dryrun_weight'] = val
            updated['ml_calib_dryrun_weight'] = val
            logger.info(f"✅ ml_calib_dryrun_weight: {val}")
        
        if 'ml_calib_decay_days' in params:
            val = int(params['ml_calib_decay_days'])
            val = max(7, min(60, val))  # Clamp 7-60 days
            TRADING_CONFIG['ml_calib_decay_days'] = val
            updated['ml_calib_decay_days'] = val
            logger.info(f"✅ ml_calib_decay_days: {val}")
        
        if 'ml_calib_min_trades' in params:
            val = int(params['ml_calib_min_trades'])
            val = max(10, min(100, val))  # Clamp 10-100
            TRADING_CONFIG['ml_calib_min_trades'] = val
            updated['ml_calib_min_trades'] = val
            logger.info(f"✅ ml_calib_min_trades: {val}")
        
        if 'ml_calib_min_winrate' in params:
            val = float(params['ml_calib_min_winrate'])
            val = max(30.0, min(60.0, val))  # Clamp 30-60%
            TRADING_CONFIG['ml_calib_min_winrate'] = val
            updated['ml_calib_min_winrate'] = val
            logger.info(f"✅ ml_calib_min_winrate: {val}%")
        
        if 'ml_calib_bucket_size' in params:
            val = int(params['ml_calib_bucket_size'])
            val = max(5, min(10, val))  # Clamp 5-10
            TRADING_CONFIG['ml_calib_bucket_size'] = val
            updated['ml_calib_bucket_size'] = val
            logger.info(f"✅ ml_calib_bucket_size: {val}")

        # ============================================================
        # 🛡️ PROTECTION & RÉGIME: Market Regime Selector
        # ============================================================
        if 'market_regime_enabled' in params:
            new_enabled = bool(params['market_regime_enabled'])
            old_enabled = TRADING_CONFIG.get('market_regime_enabled', True)
            TRADING_CONFIG['market_regime_enabled'] = new_enabled
            updated['market_regime_enabled'] = new_enabled
            logger.info(f"✅ market_regime_enabled: {new_enabled}")
            
            # 🔥 FIX 08/12/2025: Si on DÉSACTIVE le régime, effacer les ajustements
            # Les valeurs BASE (sliders) ne changent pas, on efface juste les overrides du régime
            if old_enabled and not new_enabled:
                logger.info("🔄 Régime désactivé -> Effacement des ajustements régime")
                
                # Effacer les ajustements du régime (les valeurs base des sliders restent)
                try:
                    from utils.effective_config import set_regime_adjustments
                    set_regime_adjustments({})  # Effacer les ajustements
                    logger.info("  -> Ajustements régime effacés")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur effacement ajustements: {e}")
                
                # Reset le régime selector à UNKNOWN
                try:
                    from core.market_regime_selector import get_regime_selector, MarketRegime
                    selector = get_regime_selector()
                    selector.current_regime = MarketRegime.UNKNOWN
                    logger.info("  -> Régime reset à UNKNOWN")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur reset régime: {e}")
        
        if 'market_regime_check_interval' in params:
            val = int(params['market_regime_check_interval'])
            val = max(15, min(120, val))  # Clamp 15-120 min
            TRADING_CONFIG['market_regime_check_interval'] = val
            updated['market_regime_check_interval'] = val
            logger.info(f"✅ market_regime_check_interval: {val}min")
            # 🔥 FIX: Propager à l'instance existante
            try:
                from core.market_regime_selector import get_regime_selector
                selector = get_regime_selector()
                selector.check_interval = timedelta(minutes=val)
            except Exception as e:
                logger.warning(f"⚠️ Erreur propagation check_interval: {e}")
        
        if 'market_regime_sample_count' in params:
            val = int(params['market_regime_sample_count'])
            val = max(5, min(20, val))  # Clamp 5-20
            TRADING_CONFIG['market_regime_sample_count'] = val
            updated['market_regime_sample_count'] = val
            logger.info(f"✅ market_regime_sample_count: {val}")
            # 🔥 FIX: Propager à l'instance existante
            try:
                from core.market_regime_selector import get_regime_selector
                selector = get_regime_selector()
                selector.atr_sample_size = val
            except Exception as e:
                logger.warning(f"⚠️ Erreur propagation sample_count: {e}")
        
        if 'market_regime_atr_calme_max' in params:
            val = float(params['market_regime_atr_calme_max'])
            val = max(0.10, min(0.30, val))  # Clamp 0.10-0.30%
            TRADING_CONFIG['market_regime_atr_calme_max'] = val
            updated['market_regime_atr_calme_max'] = val
            logger.info(f"✅ market_regime_atr_calme_max: {val}%")
        
        if 'market_regime_atr_normal_max' in params:
            val = float(params['market_regime_atr_normal_max'])
            val = max(0.25, min(0.60, val))  # Clamp 0.25-0.60%
            TRADING_CONFIG['market_regime_atr_normal_max'] = val
            updated['market_regime_atr_normal_max'] = val
            logger.info(f"✅ market_regime_atr_normal_max: {val}%")
        
        if 'market_regime_adx_choppy' in params:
            val = int(params['market_regime_adx_choppy'])
            val = max(15, min(30, val))  # Clamp 15-30
            TRADING_CONFIG['market_regime_adx_choppy'] = val
            updated['market_regime_adx_choppy'] = val
            logger.info(f"✅ market_regime_adx_choppy: {val}")

        # ============================================================
        # 🛡️ PROTECTION & RÉGIME: Trading Circuit Breaker
        # ============================================================
        if 'trading_circuit_breaker_enabled' in params:
            new_enabled = bool(params['trading_circuit_breaker_enabled'])
            old_enabled = TRADING_CONFIG.get('trading_circuit_breaker_enabled', True)
            TRADING_CONFIG['trading_circuit_breaker_enabled'] = new_enabled
            updated['trading_circuit_breaker_enabled'] = new_enabled
            logger.info(f"✅ trading_circuit_breaker_enabled: {new_enabled}")
            
            # 🔥 FIX 10/12/2025: Si on DÉSACTIVE le CB, reset son état
            # Évite qu'un état accumulé précédemment ne bloque le trading à la réactivation
            if old_enabled and not new_enabled:
                logger.info("🔄 Circuit Breaker désactivé -> Reset de l'état")
                try:
                    from core.trading_circuit_breaker import get_trading_circuit_breaker
                    cb = get_trading_circuit_breaker()
                    cb.reset()  # Reset complet: état ACTIVE, compteurs à 0
                    logger.info("  -> Circuit Breaker reset à ACTIVE")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur reset CB: {e}")
                
                # Effacer les ajustements du CB dans effective_config
                try:
                    from utils.effective_config import set_circuit_breaker_adjustments
                    set_circuit_breaker_adjustments({})
                    logger.info("  -> Ajustements CB effacés")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur effacement ajustements CB: {e}")
        
        if 'trading_cb_max_consecutive_losses' in params:
            val = int(params['trading_cb_max_consecutive_losses'])
            val = max(3, min(10, val))  # Clamp 3-10
            TRADING_CONFIG['trading_cb_max_consecutive_losses'] = val
            updated['trading_cb_max_consecutive_losses'] = val
            logger.info(f"✅ trading_cb_max_consecutive_losses: {val}")
            # 🔥 FIX: Propager à l'instance existante
            try:
                from core.trading_circuit_breaker import get_trading_circuit_breaker
                cb = get_trading_circuit_breaker()
                cb.update_config(max_consecutive_losses=val)
            except Exception as e:
                logger.warning(f"⚠️ Erreur propagation CB: {e}")
        
        if 'trading_cb_daily_drawdown_pause_pct' in params:
            val = float(params['trading_cb_daily_drawdown_pause_pct'])
            val = max(-5.0, min(-1.0, val))  # Clamp -5% à -1%
            TRADING_CONFIG['trading_cb_daily_drawdown_pause_pct'] = val
            updated['trading_cb_daily_drawdown_pause_pct'] = val
            logger.info(f"✅ trading_cb_daily_drawdown_pause_pct: {val}%")
            # 🔥 FIX: Propager à l'instance existante
            try:
                from core.trading_circuit_breaker import get_trading_circuit_breaker
                cb = get_trading_circuit_breaker()
                cb.update_config(daily_drawdown_pause_pct=val)
            except Exception as e:
                logger.warning(f"⚠️ Erreur propagation CB: {e}")
        
        if 'trading_cb_daily_drawdown_stop_pct' in params:
            val = float(params['trading_cb_daily_drawdown_stop_pct'])
            val = max(-10.0, min(-3.0, val))  # Clamp -10% à -3%
            TRADING_CONFIG['trading_cb_daily_drawdown_stop_pct'] = val
            updated['trading_cb_daily_drawdown_stop_pct'] = val
            logger.info(f"✅ trading_cb_daily_drawdown_stop_pct: {val}%")
            # 🔥 FIX: Propager à l'instance existante
            try:
                from core.trading_circuit_breaker import get_trading_circuit_breaker
                cb = get_trading_circuit_breaker()
                cb.update_config(daily_drawdown_stop_pct=val)
            except Exception as e:
                logger.warning(f"⚠️ Erreur propagation CB: {e}")
        
        if 'trading_cb_pause_duration_minutes' in params:
            val = int(params['trading_cb_pause_duration_minutes'])
            val = max(5, min(120, val))  # Clamp 5-120 min
            TRADING_CONFIG['trading_cb_pause_duration_minutes'] = val
            updated['trading_cb_pause_duration_minutes'] = val
            logger.info(f"✅ trading_cb_pause_duration_minutes: {val}min")
            # 🔥 FIX: Propager à l'instance existante
            try:
                from core.trading_circuit_breaker import get_trading_circuit_breaker
                cb = get_trading_circuit_breaker()
                cb.update_config(pause_duration_minutes=val)
            except Exception as e:
                logger.warning(f"⚠️ Erreur propagation CB: {e}")
        
        if 'trading_cb_score_boost_enabled' in params:
            TRADING_CONFIG['trading_cb_score_boost_enabled'] = bool(params['trading_cb_score_boost_enabled'])
            updated['trading_cb_score_boost_enabled'] = TRADING_CONFIG['trading_cb_score_boost_enabled']
            logger.info(f"✅ trading_cb_score_boost_enabled: {TRADING_CONFIG['trading_cb_score_boost_enabled']}")
        
        if 'trading_cb_score_boost_per_loss' in params:
            val = float(params['trading_cb_score_boost_per_loss'])
            val = max(0.25, min(1.5, val))  # Clamp 0.25-1.5
            TRADING_CONFIG['trading_cb_score_boost_per_loss'] = val
            updated['trading_cb_score_boost_per_loss'] = val
            logger.info(f"✅ trading_cb_score_boost_per_loss: +{val}")
            # 🔥 FIX: Propager à l'instance existante
            try:
                from core.trading_circuit_breaker import get_trading_circuit_breaker
                cb = get_trading_circuit_breaker()
                cb.update_config(score_boost_per_loss=val)
            except Exception as e:
                logger.warning(f"⚠️ Erreur propagation CB: {e}")

        # 🔥 SPRINT 2: Pair Scorer - Score Pair Dynamique
        if 'pair_scorer_enabled' in params:
            TRADING_CONFIG['pair_scorer_enabled'] = bool(params['pair_scorer_enabled'])
            updated['pair_scorer_enabled'] = TRADING_CONFIG['pair_scorer_enabled']
            logger.info(f"✅ pair_scorer_enabled: {TRADING_CONFIG['pair_scorer_enabled']}")
            # Propager à l'instance existante
            try:
                from core.pair_scorer import get_pair_scorer
                ps = get_pair_scorer()
                ps.enabled = TRADING_CONFIG['pair_scorer_enabled']
            except Exception as e:
                logger.warning(f"⚠️ Erreur propagation pair_scorer: {e}")
        
        if 'pair_scorer_min_trades' in params:
            val = int(params['pair_scorer_min_trades'])
            val = max(5, min(100, val))  # Clamp 5-100
            TRADING_CONFIG['pair_scorer_min_trades'] = val
            updated['pair_scorer_min_trades'] = val
            logger.info(f"✅ pair_scorer_min_trades: {val}")
            try:
                from core.pair_scorer import get_pair_scorer
                ps = get_pair_scorer()
                ps.min_trades = val
            except Exception as e:
                logger.warning(f"⚠️ Erreur propagation pair_scorer: {e}")
        
        if 'pair_scorer_max_adjustment' in params:
            val = float(params['pair_scorer_max_adjustment'])
            val = max(0.5, min(5.0, val))  # Clamp 0.5-5.0
            TRADING_CONFIG['pair_scorer_max_adjustment'] = val
            updated['pair_scorer_max_adjustment'] = val
            logger.info(f"✅ pair_scorer_max_adjustment: ±{val}")
            try:
                from core.pair_scorer import get_pair_scorer
                ps = get_pair_scorer()
                ps.max_adjustment = val
            except Exception as e:
                logger.warning(f"⚠️ Erreur propagation pair_scorer: {e}")
        
        if 'pair_scorer_lookback_days' in params:
            val = int(params['pair_scorer_lookback_days'])
            val = max(7, min(90, val))  # Clamp 7-90
            TRADING_CONFIG['pair_scorer_lookback_days'] = val
            updated['pair_scorer_lookback_days'] = val
            logger.info(f"✅ pair_scorer_lookback_days: {val} jours")
            try:
                from core.pair_scorer import get_pair_scorer
                ps = get_pair_scorer()
                ps.lookback_days = val
                # Forcer un refresh des stats avec la nouvelle période
                ps.refresh_stats()
            except Exception as e:
                logger.warning(f"⚠️ Erreur propagation pair_scorer: {e}")
        
        if 'pair_scorer_refresh_minutes' in params:
            val = int(params['pair_scorer_refresh_minutes'])
            val = max(15, min(240, val))  # Clamp 15-240
            TRADING_CONFIG['pair_scorer_refresh_minutes'] = val
            updated['pair_scorer_refresh_minutes'] = val
            logger.info(f"✅ pair_scorer_refresh_minutes: {val} min")
            try:
                from core.pair_scorer import get_pair_scorer
                ps = get_pair_scorer()
                ps.refresh_interval = val * 60  # Convertir en secondes
            except Exception as e:
                logger.warning(f"⚠️ Erreur propagation pair_scorer: {e}")

        # 🔥 PHASE 1D: Market Regime V2 - Détection Améliorée
        if 'market_regime_v2_enabled' in params:
            TRADING_CONFIG['market_regime_v2_enabled'] = bool(params['market_regime_v2_enabled'])
            updated['market_regime_v2_enabled'] = TRADING_CONFIG['market_regime_v2_enabled']
            logger.info(f"✅ market_regime_v2_enabled: {TRADING_CONFIG['market_regime_v2_enabled']}")
        
        if 'market_regime_use_median' in params:
            TRADING_CONFIG['market_regime_use_median'] = bool(params['market_regime_use_median'])
            updated['market_regime_use_median'] = TRADING_CONFIG['market_regime_use_median']
            logger.info(f"✅ market_regime_use_median: {TRADING_CONFIG['market_regime_use_median']}")
        
        if 'market_regime_outlier_filter' in params:
            TRADING_CONFIG['market_regime_outlier_filter'] = bool(params['market_regime_outlier_filter'])
            updated['market_regime_outlier_filter'] = TRADING_CONFIG['market_regime_outlier_filter']
            logger.info(f"✅ market_regime_outlier_filter: {TRADING_CONFIG['market_regime_outlier_filter']}")
        
        if 'market_regime_use_hysteresis' in params:
            TRADING_CONFIG['market_regime_use_hysteresis'] = bool(params['market_regime_use_hysteresis'])
            updated['market_regime_use_hysteresis'] = TRADING_CONFIG['market_regime_use_hysteresis']
            logger.info(f"✅ market_regime_use_hysteresis: {TRADING_CONFIG['market_regime_use_hysteresis']}")
        
        if 'market_regime_hysteresis_buffer' in params:
            val = float(params['market_regime_hysteresis_buffer'])
            val = max(0.05, min(0.25, val))  # Clamp 5%-25%
            TRADING_CONFIG['market_regime_hysteresis_buffer'] = val
            updated['market_regime_hysteresis_buffer'] = val
            logger.info(f"✅ market_regime_hysteresis_buffer: {val*100:.0f}%")
        
        if 'market_regime_use_smoothing' in params:
            TRADING_CONFIG['market_regime_use_smoothing'] = bool(params['market_regime_use_smoothing'])
            updated['market_regime_use_smoothing'] = TRADING_CONFIG['market_regime_use_smoothing']
            logger.info(f"✅ market_regime_use_smoothing: {TRADING_CONFIG['market_regime_use_smoothing']}")
        
        if 'market_regime_smoothing_alpha' in params:
            val = float(params['market_regime_smoothing_alpha'])
            val = max(0.1, min(0.5, val))  # Clamp 0.1-0.5
            TRADING_CONFIG['market_regime_smoothing_alpha'] = val
            updated['market_regime_smoothing_alpha'] = val
            logger.info(f"✅ market_regime_smoothing_alpha: {val}")
        
        if 'market_regime_use_atr_5m' in params:
            TRADING_CONFIG['market_regime_use_atr_5m'] = bool(params['market_regime_use_atr_5m'])
            updated['market_regime_use_atr_5m'] = TRADING_CONFIG['market_regime_use_atr_5m']
            logger.info(f"✅ market_regime_use_atr_5m: {TRADING_CONFIG['market_regime_use_atr_5m']}")
        
        if 'market_regime_use_seasonality' in params:
            TRADING_CONFIG['market_regime_use_seasonality'] = bool(params['market_regime_use_seasonality'])
            updated['market_regime_use_seasonality'] = TRADING_CONFIG['market_regime_use_seasonality']
            logger.info(f"✅ market_regime_use_seasonality: {TRADING_CONFIG['market_regime_use_seasonality']}")
        
        if 'market_regime_min_duration_minutes' in params:
            val = int(params['market_regime_min_duration_minutes'])
            val = max(5, min(120, val))  # Clamp 5-120 min
            TRADING_CONFIG['market_regime_min_duration_minutes'] = val
            updated['market_regime_min_duration_minutes'] = val
            logger.info(f"✅ market_regime_min_duration_minutes: {val} min")

        # 🔥 PHASE 1E: Auto-Calibration Seuils ATR
        if 'market_regime_auto_calibration_enabled' in params:
            TRADING_CONFIG['market_regime_auto_calibration_enabled'] = bool(params['market_regime_auto_calibration_enabled'])
            updated['market_regime_auto_calibration_enabled'] = TRADING_CONFIG['market_regime_auto_calibration_enabled']
            logger.info(f"✅ market_regime_auto_calibration_enabled: {TRADING_CONFIG['market_regime_auto_calibration_enabled']}")
        
        if 'market_regime_calibration_lookback_days' in params:
            val = int(params['market_regime_calibration_lookback_days'])
            val = max(3, min(14, val))  # Clamp 3-14
            TRADING_CONFIG['market_regime_calibration_lookback_days'] = val
            updated['market_regime_calibration_lookback_days'] = val
            logger.info(f"✅ market_regime_calibration_lookback_days: {val} jours")
        
        if 'market_regime_calibration_percentile_calme' in params:
            val = int(params['market_regime_calibration_percentile_calme'])
            val = max(10, min(50, val))  # Clamp 10-50
            TRADING_CONFIG['market_regime_calibration_percentile_calme'] = val
            updated['market_regime_calibration_percentile_calme'] = val
            logger.info(f"✅ market_regime_calibration_percentile_calme: P{val}")
        
        if 'market_regime_calibration_percentile_volatile' in params:
            val = int(params['market_regime_calibration_percentile_volatile'])
            val = max(50, min(90, val))  # Clamp 50-90
            TRADING_CONFIG['market_regime_calibration_percentile_volatile'] = val
            updated['market_regime_calibration_percentile_volatile'] = val
            logger.info(f"✅ market_regime_calibration_percentile_volatile: P{val}")
        
        if 'market_regime_calibration_min_samples' in params:
            val = int(params['market_regime_calibration_min_samples'])
            val = max(10, min(200, val))  # Clamp 10-200
            TRADING_CONFIG['market_regime_calibration_min_samples'] = val
            updated['market_regime_calibration_min_samples'] = val
            logger.info(f"✅ market_regime_calibration_min_samples: {val}")
        
        # 🔥 PHASE 1E: BTC Indicator
        if 'market_regime_btc_indicator_enabled' in params:
            TRADING_CONFIG['market_regime_btc_indicator_enabled'] = bool(params['market_regime_btc_indicator_enabled'])
            updated['market_regime_btc_indicator_enabled'] = TRADING_CONFIG['market_regime_btc_indicator_enabled']
            logger.info(f"✅ market_regime_btc_indicator_enabled: {TRADING_CONFIG['market_regime_btc_indicator_enabled']}")
        
        if 'market_regime_btc_volatile_threshold_1h' in params:
            val = float(params['market_regime_btc_volatile_threshold_1h'])
            val = max(0.5, min(10.0, val))  # Clamp 0.5-10.0
            TRADING_CONFIG['market_regime_btc_volatile_threshold_1h'] = val
            updated['market_regime_btc_volatile_threshold_1h'] = val
            logger.info(f"✅ market_regime_btc_volatile_threshold_1h: {val}%")
        
        if 'market_regime_btc_trend_threshold_24h' in params:
            val = float(params['market_regime_btc_trend_threshold_24h'])
            val = max(1.0, min(20.0, val))  # Clamp 1.0-20.0
            TRADING_CONFIG['market_regime_btc_trend_threshold_24h'] = val
            updated['market_regime_btc_trend_threshold_24h'] = val
            logger.info(f"✅ market_regime_btc_trend_threshold_24h: {val}%")
        
        if 'market_regime_btc_force_volatile_enabled' in params:
            TRADING_CONFIG['market_regime_btc_force_volatile_enabled'] = bool(params['market_regime_btc_force_volatile_enabled'])
            updated['market_regime_btc_force_volatile_enabled'] = TRADING_CONFIG['market_regime_btc_force_volatile_enabled']
            logger.info(f"✅ market_regime_btc_force_volatile_enabled: {TRADING_CONFIG['market_regime_btc_force_volatile_enabled']}")
        
        # 🔥 Spread Thresholds (onglet Paires)
        if 'max_spread_pct' in params:
            val = params['max_spread_pct']
            if val is None or val == '' or val == 'null':
                TRADING_CONFIG['max_spread_pct'] = None
                updated['max_spread_pct'] = None
            else:
                val = float(val)
                val = max(0.01, min(1.0, val))  # Clamp 0.01-1.0%
                TRADING_CONFIG['max_spread_pct'] = val
                updated['max_spread_pct'] = val
            logger.info(f"✅ max_spread_pct: {TRADING_CONFIG['max_spread_pct']}")
        
        if 'max_spread_pct_fixe' in params:
            val = float(params['max_spread_pct_fixe'])
            val = max(0.01, min(0.5, val))  # Clamp 0.01-0.5%
            TRADING_CONFIG['max_spread_pct_fixe'] = val
            updated['max_spread_pct_fixe'] = val
            logger.info(f"✅ max_spread_pct_fixe: {val}%")
        
        if 'max_spread_pct_atr' in params:
            val = float(params['max_spread_pct_atr'])
            val = max(0.01, min(0.5, val))  # Clamp 0.01-0.5%
            TRADING_CONFIG['max_spread_pct_atr'] = val
            updated['max_spread_pct_atr'] = val
            logger.info(f"✅ max_spread_pct_atr: {val}%")

        # 🔄 Signal Inversion (onglet TP/SL et position)
        if 'invert_signals' in params:
            TRADING_CONFIG['invert_signals'] = _coerce_bool(params['invert_signals'])
            updated['invert_signals'] = TRADING_CONFIG['invert_signals']
            logger.info(f"✅ invert_signals: {TRADING_CONFIG['invert_signals']}")

        if updated:
            logger.info(f"✅ Config mise à jour via WebSocket: {updated}")
            await add_log('INFO', 'Config mise à jour', str(updated))
            
            # 🔥 FIX: Persister les modifications dans config_overrides.json
            # pour conserver les changements entre redémarrages
            try:
                from utils.config_persistence import save_config_overrides
                if save_config_overrides(updated):
                    logger.info(f"✅ Modifications persistées dans config_overrides.json")
            except Exception as e:
                logger.error(f"❌ Erreur persistence config: {e}")
            
            # 🔥 FIX: Mettre à jour immédiatement toutes les instances qui utilisent la config
            # Mettre à jour position_config si nécessaire (sans réinitialiser complètement)
            pos_cfg = state.get_position_config()
            if pos_cfg:
                from config import TRADING_CONFIG
                # Mettre à jour les valeurs TP/SL si elles ont changé
                if 'tp_sl_mode' in updated:
                    tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
                    # 🔥 FIX: Accepter aussi 'ESCALIER' comme mode valide
                    pos_cfg.use_atr = (tp_sl_mode == 'ATR' or tp_sl_mode == 'TP_MULTI' or tp_sl_mode == 'ESCALIER')
                    # 🔥 FIX: Mettre à jour aussi position_manager.config.use_atr si position_manager existe
                    pos_mgr = state.get_position_manager()
                    if pos_mgr:
                        pos_mgr.config.use_atr = pos_cfg.use_atr
                if 'tp_percent' in updated:
                    pos_cfg.fixed_tp_pct = TRADING_CONFIG.get('tp_percent', 0.6)
                if 'sl_percent' in updated:
                    pos_cfg.fixed_sl_pct = TRADING_CONFIG.get('sl_percent', 0.25)
                if 'atr_mult_tp' in updated:
                    pos_cfg.atr_mult_tp = TRADING_CONFIG.get('atr_mult_tp', 1.5)
                if 'atr_mult_sl' in updated:
                    pos_cfg.atr_mult_sl = TRADING_CONFIG.get('atr_mult_sl', 1.0)
                if 'atr_min' in updated:
                    pos_cfg.atr_min = TRADING_CONFIG.get('atr_min', 0.15)
                if 'atr_max' in updated:
                    pos_cfg.atr_max = TRADING_CONFIG.get('atr_max', 1.5)
            
            # 🔥 FIX: Mettre à jour aussi position_manager.tpsl_config si une position est active
            pos_mgr = state.get_position_manager()
            if pos_mgr and pos_mgr.active_position:
                from config import TRADING_CONFIG
                # Mettre à jour les valeurs TP/SL dans tpsl_config pour les prochaines positions
                if 'tp_percent' in updated:
                    pos_mgr.tpsl_config.fixed_tp_pct = TRADING_CONFIG.get('tp_percent', 0.6)
                if 'sl_percent' in updated:
                    pos_mgr.tpsl_config.fixed_sl_pct = TRADING_CONFIG.get('sl_percent', 0.25)
                if 'atr_mult_tp' in updated:
                    pos_mgr.tpsl_config.atr_mult_tp = TRADING_CONFIG.get('atr_mult_tp', 1.5)
                if 'atr_mult_sl' in updated:
                    pos_mgr.tpsl_config.atr_mult_sl = TRADING_CONFIG.get('atr_mult_sl', 1.0)
                if 'atr_min' in updated:
                    pos_mgr.tpsl_config.atr_min = TRADING_CONFIG.get('atr_min', 0.15)
                if 'atr_max' in updated:
                    pos_mgr.tpsl_config.atr_max = TRADING_CONFIG.get('atr_max', 1.5)
            
            # 🔥 BIDIRECTIONNEL: Émettre événement de mise à jour de config pour synchroniser le frontend
            ws_mgr = state.get_ws_manager()
            if ws_mgr:
                await ws_mgr.emit('config_updated', {
                    'updated': updated,
                    'timestamp': time.time()
                })
        
        return {'updated': updated}
    
    elif command == 'get_status':
        status_data = app_state.copy()
        if status_data.get('active_position') and hasattr(status_data['active_position'], 'to_dict'):
            status_data['active_position'] = status_data['active_position'].to_dict()
        return status_data
    
    elif command == 'close_position':
        pos_mgr = state.get_position_manager()
        if pos_mgr and pos_mgr.active_position:
            # 🔥 FIX: Utiliser la logique de api_close_position directement (pas JSONResponse)
            init_instances()
            
            # Utiliser le lock pour synchroniser la fermeture
            pos_lock = state.lock("position")
            async with pos_lock:
                # Double-check que la position existe
                pos_mgr = state.get_position_manager()
                if not pos_mgr or not pos_mgr.active_position:
                    if not app_state.get('active_position'):
                        raise ValueError('No active position')
                    else:
                        app_state['active_position'] = None
                        raise ValueError('Position state inconsistent')
                
                price_prov = state.get_price_provider()
                if not price_prov:
                    raise ValueError('Price provider not available')
                
                pos_mgr = state.get_position_manager()
                # Récupérer prix actuel
                price_data = await price_prov.get_price(pos_mgr.active_position.symbol)
                exit_price = get_preferred_price(price_data)
                
                # Utiliser exit_price depuis params si fourni
                if params.get('exit_price'):
                    exit_price = float(params['exit_price'])
                
                result = pos_mgr.close_position(exit_price=exit_price, reason=params.get('reason', 'MANUAL'))
                
                app_state['active_position'] = None
                
                # Ajouter à l'historique et sauvegarder
                if result:
                    result['timestamp'] = datetime.now().isoformat()
                    app_state['trade_history'].append(result)
                    # 🔥 FIX: Pas de limite - l'historique persiste tant que le backend tourne
                    save_trade_history()
                
                # Désactiver callback WebSocket
                price_prov = state.get_price_provider()
                if price_prov:
                    price_prov.set_socketio_callback(None, None)
                    # 🔥 FIX SL MISMATCH: Désactiver callback SL temps réel
                    price_prov.set_sl_check_callback(None)
                
                # 🔥 FIX SL MISMATCH V2: Annuler tâche SL en attente
                closed_symbol = result.get('symbol') if result else None
                if closed_symbol:
                    cancel_pending_sl_task(closed_symbol)
                
                # 🔥 Afficher le mode de trading clairement
                live_mgr = state.get_live_order_manager()
                if live_mgr:
                    mode_str = "🟡 LIVE DRY-RUN" if live_mgr.dry_run else "🔴 LIVE RÉEL"
                else:
                    mode_str = "📝 PAPER"
                await add_log('INFO', f'Position clôturée [{mode_str}]', params.get('reason', 'MANUAL'))
                ws_mgr = state.get_ws_manager()
                if ws_mgr:
                    await ws_mgr.emit('position_closed', result)
                
                # Émettre stats_update après fermeture
                try:
                    from core.callbacks.position_check_loop import _emit_stats_update
                    await _emit_stats_update()
                except Exception as e:
                    logger.error(f"❌ Erreur émission stats_update: {e}")
                
                return {'status': 'closed', 'result': result}
        else:
            raise ValueError('Aucune position active')
    
    elif command == 'update_telegram_config':
        # 🔥 NOUVEAU: Mettre à jour la configuration Telegram
        from config import (
            TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED,
            TELEGRAM_NOTIFY_POSITION_OPENED, TELEGRAM_NOTIFY_POSITION_CLOSED,
            TELEGRAM_NOTIFY_TP_ESCALIER, TELEGRAM_NOTIFY_EARLY_INVALIDATION,
            TELEGRAM_NOTIFY_ERROR, TELEGRAM_NOTIFY_RECONNECTION,
            TELEGRAM_NOTIFY_DAILY_SUMMARY, TELEGRAM_NOTIFY_RECOVERY_MODE,
            TELEGRAM_NOTIFY_SETUP_REJECTED
        )
        import os
        updated = {}
        
        # Mettre à jour les types de notifications Telegram
        notify_types = {
            'TELEGRAM_NOTIFY_POSITION_OPENED': 'TELEGRAM_NOTIFY_POSITION_OPENED',
            'TELEGRAM_NOTIFY_POSITION_CLOSED': 'TELEGRAM_NOTIFY_POSITION_CLOSED',
            'TELEGRAM_NOTIFY_TP_ESCALIER': 'TELEGRAM_NOTIFY_TP_ESCALIER',
            'TELEGRAM_NOTIFY_EARLY_INVALIDATION': 'TELEGRAM_NOTIFY_EARLY_INVALIDATION',
            'TELEGRAM_NOTIFY_ERROR': 'TELEGRAM_NOTIFY_ERROR',
            'TELEGRAM_NOTIFY_RECONNECTION': 'TELEGRAM_NOTIFY_RECONNECTION',
            'TELEGRAM_NOTIFY_DAILY_SUMMARY': 'TELEGRAM_NOTIFY_DAILY_SUMMARY',
            'TELEGRAM_NOTIFY_RECOVERY_MODE': 'TELEGRAM_NOTIFY_RECOVERY_MODE',
            'TELEGRAM_NOTIFY_SETUP_REJECTED': 'TELEGRAM_NOTIFY_SETUP_REJECTED'
        }
        
        # Mettre à jour chaque type de notification
        for key, env_key in notify_types.items():
            if key in params:
                value = bool(params[key])
                os.environ[env_key] = 'true' if value else 'false'
                updated[key] = value
                logger.info(f"✅ {key} mis à jour: {value}")
        
        # Mettre à jour notification_manager si disponible
        notif_mgr = state.get_notification_manager()
        if notif_mgr:
            # 🔥 FIX: Mettre à jour directement depuis params (pas besoin de reload config)
            # Les valeurs booléennes arrivent déjà depuis le frontend
            notif_mgr.telegram_notify_settings.update({
                'position_opened': bool(params.get('TELEGRAM_NOTIFY_POSITION_OPENED', True)),
                'position_closed': bool(params.get('TELEGRAM_NOTIFY_POSITION_CLOSED', True)),
                'tp_escalier_level': bool(params.get('TELEGRAM_NOTIFY_TP_ESCALIER', True)),
                'early_invalidation': bool(params.get('TELEGRAM_NOTIFY_EARLY_INVALIDATION', True)),
                'error': bool(params.get('TELEGRAM_NOTIFY_ERROR', True)),
                'reconnection': bool(params.get('TELEGRAM_NOTIFY_RECONNECTION', True)),
                'daily_summary': bool(params.get('TELEGRAM_NOTIFY_DAILY_SUMMARY', False)),
                'recovery_mode': bool(params.get('TELEGRAM_NOTIFY_RECOVERY_MODE', True)),
                'setup_rejected': bool(params.get('TELEGRAM_NOTIFY_SETUP_REJECTED', False))
            })
            logger.info(f"✅ Notification Manager mis à jour: {notif_mgr.telegram_notify_settings}")

        # 🔥 PERSISTANCE: Sauvegarder dans le fichier .env
        try:
            import os
            from pathlib import Path

            env_file = Path('.env')
            if env_file.exists():
                # Lire le fichier .env existant
                with open(env_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                # Mettre à jour les lignes correspondantes
                updated_lines = []
                env_keys_updated = set()

                for line in lines:
                    line_stripped = line.strip()
                    # Vérifier si la ligne correspond à un des paramètres Telegram
                    updated_line = False
                    for key, env_key in notify_types.items():
                        if line_stripped.startswith(f'{env_key}='):
                            if key in params:
                                value = bool(params[key])
                                updated_lines.append(f'{env_key}={"true" if value else "false"}\n')
                                env_keys_updated.add(env_key)
                                updated_line = True
                                break

                    if not updated_line:
                        updated_lines.append(line)

                # Ajouter les clés manquantes à la fin (si elles n'existaient pas)
                for key, env_key in notify_types.items():
                    if env_key not in env_keys_updated and key in params:
                        value = bool(params[key])
                        updated_lines.append(f'{env_key}={"true" if value else "false"}\n')

                # Écrire le fichier .env mis à jour
                with open(env_file, 'w', encoding='utf-8') as f:
                    f.writelines(updated_lines)

                logger.info(f"✅ Fichier .env mis à jour avec {len(updated)} paramètres Telegram")
            else:
                logger.warning("⚠️ Fichier .env introuvable, paramètres non persistés")

        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde .env: {e}")
            # Ne pas faire échouer la requête si la sauvegarde échoue

        return {'updated': updated, 'success': True}
    
    elif command == 'test_telegram':
        # 🔥 NOUVEAU: Envoyer un message de test Telegram
        from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED
        if not TELEGRAM_ENABLED or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            return {'success': False, 'error': 'Telegram non configuré (vérifiez .env)'}
        
        try:
            notif_mgr = state.get_notification_manager()
            if notif_mgr and notif_mgr.telegram_notifier:
                test_message = "🧪 **Test de notification Telegram**\n\nCe message confirme que votre configuration Telegram fonctionne correctement ! ✅"
                success = await notif_mgr.telegram_notifier.send_message(test_message)
                if success:
                    return {'success': True, 'message': 'Message de test envoyé avec succès'}
                else:
                    return {'success': False, 'error': 'Erreur lors de l\'envoi du message'}
            else:
                return {'success': False, 'error': 'Notification manager non disponible'}
        except Exception as e:
            logger.error(f"❌ Erreur test Telegram: {e}")
            return {'success': False, 'error': str(e)}
    
    elif command == 'log_config':
        # 🔥 MIGRATION COMPLÈTE: Logger changement de config via WebSocket
        config_key = params.get('key', 'unknown')
        config_change = params.get('change', 'unknown')
        await add_log('INFO', f'Config modifiée: {config_key}', str(config_change))
        return {'status': 'logged', 'key': config_key, 'change': config_change}
    
    elif command == 'reboot_backend':
        reason = params.get('reason', 'manual')
        return await initiate_backend_reboot(reason=reason)
    
    else:
        # 🔥 LIVE TRADING: Vérifier si la commande est enregistrée via ws_manager
        ws_mgr = state.get_ws_manager()
        if ws_mgr and command in ws_mgr._command_handlers:
            # Exécuter la commande enregistrée (live trading, etc.)
            return await ws_mgr.handle_command(command, params, None)
        else:
            raise ValueError(f"Unknown command: {command}")


# Configuration endpoints

@app.get("/api/config")
async def api_get_config():
    """Récupérer la configuration actuelle (tous les paramètres)"""
    from config import TRADING_CONFIG
    return JSONResponse({
        'volume_multiplier': TRADING_CONFIG.get('volume_multiplier', 0.95),
        'min_score_required': TRADING_CONFIG.get('min_score_required', 7.5),
        'use_confluence': TRADING_CONFIG.get('use_confluence', False),
        'tp_sl_mode': TRADING_CONFIG.get('tp_sl_mode', 'FIXE'),
        'tp_percent': TRADING_CONFIG.get('tp_percent', 0.25),
        'sl_percent': TRADING_CONFIG.get('sl_percent', 0.25),
        'trailing_mfe_enabled': TRADING_CONFIG.get('trailing_mfe_enabled', False),
        'trailing_mfe_trigger_pct': TRADING_CONFIG.get('trailing_mfe_trigger_pct', 0.10),
        'trailing_mfe_lock_in_pct': TRADING_CONFIG.get('trailing_mfe_lock_in_pct', 0.0),
        'partial_tp_be_lock_in_pct': TRADING_CONFIG.get('partial_tp_be_lock_in_pct', 0.0),
        # 4 seuils configurables
        'snr_threshold': TRADING_CONFIG.get('snr_threshold', 0.25),
        'breakout_threshold': TRADING_CONFIG.get('breakout_threshold', 0.35),
        'wick_ratio_max': TRADING_CONFIG.get('wick_ratio_max', 2.8),
        'di_gap_min': TRADING_CONFIG.get('di_gap_min', 4.0),
        'di_gap_adx_threshold': TRADING_CONFIG.get('di_gap_adx_threshold', 25),
        # Seuils ATR optimal
        'optimal_atr_min_1m': TRADING_CONFIG.get('optimal_atr_min_1m', 0.12),
        'optimal_atr_max_1m': TRADING_CONFIG.get('optimal_atr_max_1m', 0.75),
        'optimal_atr_min_5m': TRADING_CONFIG.get('optimal_atr_min_5m', 0.22),
        'optimal_atr_max_5m': TRADING_CONFIG.get('optimal_atr_max_5m', 1.4),
        # Trend timeframe
        'trend_timeframe': TRADING_CONFIG.get('trend_timeframe', '15m'),
        'account_size': TRADING_CONFIG.get('account_size', 1000.0),
        'risk_per_trade': TRADING_CONFIG.get('risk_per_trade', 2.0),
        # 🔥 ML Config - Filtrage GradientBoosting
        'gb_filter_enabled': TRADING_CONFIG.get('gb_filter_enabled', True),
        'gb_min_confidence': TRADING_CONFIG.get('gb_min_confidence', 0.55),
        # 🔥 ML Config - Calibration
        'ml_calibration_enabled': TRADING_CONFIG.get('ml_calibration_enabled', False),
        'ml_calib_min_winrate': TRADING_CONFIG.get('ml_calib_min_winrate', 45),
        'ml_calib_live_weight': TRADING_CONFIG.get('ml_calib_live_weight', 1.0),
        'ml_calib_dryrun_weight': TRADING_CONFIG.get('ml_calib_dryrun_weight', 0.5),
        'ml_calib_decay_days': TRADING_CONFIG.get('ml_calib_decay_days', 30),
        'ml_calib_min_trades': TRADING_CONFIG.get('ml_calib_min_trades', 50),
        # 🔥 ML Config - Threshold Optimizer & Drift Detection
        'threshold_optimizer_enabled': TRADING_CONFIG.get('threshold_optimizer_enabled', False),
        'threshold_min': TRADING_CONFIG.get('threshold_min', 0.45),
        'threshold_max': TRADING_CONFIG.get('threshold_max', 0.70),
        'drift_detection_enabled': TRADING_CONFIG.get('drift_detection_enabled', True),
        # 🔥 ML Config - GradientBoosting Hyperparameters
        'gb_max_iter': TRADING_CONFIG.get('gb_max_iter', 200),
        'gb_max_depth': TRADING_CONFIG.get('gb_max_depth', 5),
        'gb_learning_rate': TRADING_CONFIG.get('gb_learning_rate', 0.1),
        'gb_l2_regularization': TRADING_CONFIG.get('gb_l2_regularization', 0.5),
        # 🔥 Spread Thresholds (onglet Paires)
        'max_spread_pct': TRADING_CONFIG.get('max_spread_pct'),
        'max_spread_pct_fixe': TRADING_CONFIG.get('max_spread_pct_fixe', 0.03),
        'max_spread_pct_atr': TRADING_CONFIG.get('max_spread_pct_atr', 0.06),
        # 🔄 Signal Inversion (onglet TP/SL et position)
        'invert_signals': TRADING_CONFIG.get('invert_signals', False)
    })


@app.get("/api/config/complete")
async def api_get_complete_config():
    """
    🔥 NOUVEAU: Récupérer TOUTES les variables de configuration
    
    Retourne:
    - trading_config: Valeurs BASE (sliders, ne changent jamais automatiquement)
    - effective_config: Valeurs RÉELLES utilisées par le bot (base + ajustements régime/CB)
    - adjustments_summary: Détail des ajustements actifs
    """
    from config import TRADING_CONFIG, RISK_CONFIG, CONDITION_WEIGHTS, TREND_BONUS_CONFIG
    from config import RETRY_CONFIG, CIRCUIT_BREAKER_CONFIG, WEBSOCKET_CONFIG
    
    # 🔥 FIX 08/12/2025: Inclure effective_config pour l'onglet "Variables en cours"
    try:
        from utils.effective_config import get_effective_config, get_config_summary
        effective = get_effective_config()
        summary = get_config_summary()
    except Exception as e:
        logger.warning(f"⚠️ Erreur chargement effective_config: {e}")
        effective = TRADING_CONFIG
        summary = {}
    
    return JSONResponse({
        'trading_config': TRADING_CONFIG,  # Valeurs BASE (pour les sliders)
        'effective_config': effective,      # Valeurs EFFECTIVES (pour "Variables en cours")
        'adjustments_summary': summary,     # Détail des ajustements
        'risk_config': RISK_CONFIG,
        'condition_weights': CONDITION_WEIGHTS,
        'trend_bonus_config': TREND_BONUS_CONFIG,
        'retry_config': RETRY_CONFIG,
        'circuit_breaker_config': CIRCUIT_BREAKER_CONFIG,
        'websocket_config': WEBSOCKET_CONFIG,
        'timestamp': time.time()
    })


@app.get("/api/config/effective")
async def api_get_effective_config():
    """
    🔥 NOUVEAU: Récupérer uniquement les valeurs EFFECTIVES utilisées par le bot.
    Ces valeurs incluent les ajustements du régime, circuit breaker, et pair scorer.
    """
    try:
        from utils.effective_config import get_effective_config, get_config_summary
        effective = get_effective_config()
        summary = get_config_summary()
        
        return JSONResponse({
            'success': True,
            'effective_config': effective,
            'adjustments': summary.get('adjustments', {}),
            'differences': summary.get('differences', {}),
            'regime_enabled': summary.get('regime_enabled', False),
            'cb_enabled': summary.get('cb_enabled', False),
            'timestamp': time.time()
        })
    except Exception as e:
        logger.error(f"❌ Erreur récupération effective_config: {e}")
        from config import TRADING_CONFIG
        return JSONResponse({
            'success': False,
            'error': str(e),
            'effective_config': TRADING_CONFIG,
            'timestamp': time.time()
        })


@app.get("/api/metrics/conditions")
async def get_condition_metrics():
    """Métriques par condition"""
    from core.metrics import condition_metrics
    
    stats = condition_metrics.get_stats_summary()
    return JSONResponse(stats)

@app.post("/api/log/config")
async def api_log_config(request: Request):
    """
    ⚠️ DEPRECATED: Utiliser WebSocket command 'log_config' à la place
    Conservé pour compatibilité uniquement
    """
    try:
        data = await request.json() if hasattr(request, 'json') else {}
        data = data if isinstance(data, dict) else {}
        
        # Logger le changement de config
        config_key = data.get('key', 'unknown')
        config_value = data.get('value', 'unknown')
        await add_log('INFO', f'Config modifiée: {config_key}', str(config_value))
        
        return JSONResponse({'status': 'logged', 'key': config_key, 'value': config_value})
    except Exception as e:
        logger.error(f"Erreur log config: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)

@app.post("/api/config")
@app.post("/api/config/update")  # ⚠️ DEPRECATED: Utiliser WebSocket command 'update_config' à la place
async def api_update_config(request: Request):
    """
    ⚠️ DEPRECATED: Utiliser WebSocket command 'update_config' à la place
    Conservé pour compatibilité uniquement
    Modifier la configuration à la volée (tous les paramètres)
    """
    from config import TRADING_CONFIG
    
    try:
        data = await request.json() if hasattr(request, 'json') else {}
        data = data if isinstance(data, dict) else {}
        
        updated = {}
        
        # 🔥 Volume multiplier
        if 'volume_multiplier' in data:
            val = float(data['volume_multiplier'])
            val = max(0.1, min(2.0, val))  # Clamp 0.1-2.0
            TRADING_CONFIG['volume_multiplier'] = val
            updated['volume_multiplier'] = val
        
        # 🔥 Confluence
        if 'use_confluence' in data:
            TRADING_CONFIG['use_confluence'] = bool(data['use_confluence'])
            updated['use_confluence'] = TRADING_CONFIG['use_confluence']
        
        # 🔥 TP/SL Mode
        if 'tp_sl_mode' in data:
            mode = str(data['tp_sl_mode']).upper()
            if mode in ['FIXE', 'ATR', 'TP_MULTI']:  # 🔥 PHASE 7: TP_MULTI remplace ATR_MULTI
                TRADING_CONFIG['tp_sl_mode'] = mode
                # Mettre à jour PositionConfig si position_manager existe
                init_instances()
                pos_cfg = state.get_position_config()
                if pos_cfg:
                    # 🔥 PHASE 7: TP_MULTI utilise aussi le mode ATR (pour calculer ATR)
                    pos_cfg.use_atr = (mode == 'ATR' or mode == 'TP_MULTI')
                updated['tp_sl_mode'] = mode
        
        if 'tp_percent' in data:
            val = float(data['tp_percent'])
            TRADING_CONFIG['tp_percent'] = val
            pos_cfg = state.get_position_config()
            if pos_cfg:
                pos_cfg.fixed_tp_pct = val
            updated['tp_percent'] = val
        
        if 'sl_percent' in data:
            val = float(data['sl_percent'])
            TRADING_CONFIG['sl_percent'] = val
            pos_cfg = state.get_position_config()
            if pos_cfg:
                pos_cfg.fixed_sl_pct = val
            updated['sl_percent'] = val
        
        # 🔥 FIX: 4 seuils configurables
        if 'snr_threshold' in data:
            val = float(data['snr_threshold'])
            val = max(0.0, min(1.0, val))  # Clamp 0.0-1.0
            TRADING_CONFIG['snr_threshold'] = val
            updated['snr_threshold'] = val
        
        if 'breakout_threshold' in data:
            val = float(data['breakout_threshold'])
            val = max(0.0, min(1.0, val))  # Clamp 0.0-1.0
            TRADING_CONFIG['breakout_threshold'] = val
            updated['breakout_threshold'] = val
        
        if 'wick_ratio_max' in data:
            val = float(data['wick_ratio_max'])
            val = max(1.0, min(10.0, val))  # Clamp 1.0-10.0
            TRADING_CONFIG['wick_ratio_max'] = val
            updated['wick_ratio_max'] = val
        
        if 'di_gap_min' in data:
            val = float(data['di_gap_min'])
            val = max(0.0, min(50.0, val))  # Clamp 0.0-50.0
            TRADING_CONFIG['di_gap_min'] = val
            updated['di_gap_min'] = val
        
        if 'di_gap_adx_threshold' in data:
            val = float(data['di_gap_adx_threshold'])
            val = max(0.0, min(100.0, val))  # Clamp 0.0-100.0
            TRADING_CONFIG['di_gap_adx_threshold'] = val
            updated['di_gap_adx_threshold'] = val
        
        # 🔥 FIX: Permettre modification des seuils ATR optimal
        if 'optimal_atr_min_1m' in data:
            val = float(data['optimal_atr_min_1m'])
            val = max(0.01, min(1.0, val))  # Clamp 0.01-1.0%
            TRADING_CONFIG['optimal_atr_min_1m'] = val
            updated['optimal_atr_min_1m'] = val
        
        if 'optimal_atr_max_1m' in data:
            val = float(data['optimal_atr_max_1m'])
            val = max(0.1, min(5.0, val))  # Clamp 0.1-5.0%
            TRADING_CONFIG['optimal_atr_max_1m'] = val
            updated['optimal_atr_max_1m'] = val
        
        if 'optimal_atr_min_5m' in data:
            val = float(data['optimal_atr_min_5m'])
            val = max(0.01, min(2.0, val))  # Clamp 0.01-2.0%
            TRADING_CONFIG['optimal_atr_min_5m'] = val
            updated['optimal_atr_min_5m'] = val
        
        if 'optimal_atr_max_5m' in data:
            val = float(data['optimal_atr_max_5m'])
            val = max(0.5, min(10.0, val))  # Clamp 0.5-10.0%
            TRADING_CONFIG['optimal_atr_max_5m'] = val
            updated['optimal_atr_max_5m'] = val
        
        # 🔥 FIX: Permettre modification du trend timeframe
        if 'trend_timeframe' in data:
            val = str(data['trend_timeframe']).lower()
            valid_timeframes = ['5m', '15m', '30m', '1h']
            if val in valid_timeframes:
                TRADING_CONFIG['trend_timeframe'] = val
                updated['trend_timeframe'] = val
            else:
                return JSONResponse({'error': f'Timeframe invalide: {val}. Valeurs acceptées: {valid_timeframes}'}, status_code=400)
        
        # 🔥 FIX: Ajouter support pour account_size et risk_per_trade
        if 'account_size' in data:
            val = float(data['account_size'])
            val = max(100.0, min(100000.0, val))  # Clamp 100-100000
            TRADING_CONFIG['account_size'] = val
            updated['account_size'] = val
        
        if 'risk_per_trade' in data:
            val = float(data['risk_per_trade'])
            val = max(0.5, min(5.0, val))  # Clamp 0.5-5.0%
            TRADING_CONFIG['risk_per_trade'] = val
            updated['risk_per_trade'] = val
        
        # 🔥 BIDIRECTIONNEL: Paramètres ATR (atr_mult_tp, atr_mult_sl, atr_min, atr_max)
        if 'atr_mult_tp' in data:
            val = float(data['atr_mult_tp'])
            val = max(0.1, min(10.0, val))  # Clamp 0.1-10.0x
            TRADING_CONFIG['atr_mult_tp'] = val
            updated['atr_mult_tp'] = val
            init_instances()
            pos_cfg = state.get_position_config()
            if pos_cfg:
                pos_cfg.atr_mult_tp = val
        
        if 'atr_mult_sl' in data:
            val = float(data['atr_mult_sl'])
            val = max(0.1, min(10.0, val))  # Clamp 0.1-10.0x
            TRADING_CONFIG['atr_mult_sl'] = val
            updated['atr_mult_sl'] = val
            pos_cfg = state.get_position_config()
            if pos_cfg:
                pos_cfg.atr_mult_sl = val
        
        if 'atr_min' in data:
            val = float(data['atr_min'])
            val = max(0.01, min(5.0, val))  # Clamp 0.01-5.0%
            TRADING_CONFIG['atr_min'] = val
            updated['atr_min'] = val
            pos_cfg = state.get_position_config()
            if pos_cfg:
                pos_cfg.atr_min = val
        
        if 'atr_max' in data:
            val = float(data['atr_max'])
            val = max(0.1, min(10.0, val))  # Clamp 0.1-10.0%
            TRADING_CONFIG['atr_max'] = val
            updated['atr_max'] = val
            pos_cfg = state.get_position_config()
            if pos_cfg:
                pos_cfg.atr_max = val
        
        # 🔥 Filtre RSI Final (bloque trades contre-logiques)
        if 'rsi_final_filter_enabled' in data:
            TRADING_CONFIG['rsi_final_filter_enabled'] = bool(data['rsi_final_filter_enabled'])
            updated['rsi_final_filter_enabled'] = TRADING_CONFIG['rsi_final_filter_enabled']
        
        if 'rsi_final_long_max' in data:
            val = int(data['rsi_final_long_max'])
            val = max(50, min(85, val))  # Clamp 50-85
            TRADING_CONFIG['rsi_final_long_max'] = val
            updated['rsi_final_long_max'] = val
        
        if 'rsi_final_short_min' in data:
            val = int(data['rsi_final_short_min'])
            val = max(15, min(50, val))  # Clamp 15-50
            TRADING_CONFIG['rsi_final_short_min'] = val
            updated['rsi_final_short_min'] = val
        
        if updated:
            logger.info(f"✅ Configuration mise à jour: {updated}")
            await add_log('INFO', 'Config mise à jour', str(updated))
            # 🔥 BIDIRECTIONNEL: Émettre événement de mise à jour de config pour synchroniser le frontend
            ws_mgr = state.get_ws_manager()
            if ws_mgr:
                await ws_mgr.emit('config_updated', {
                    'updated': updated,
                    'timestamp': time.time()
                })
            return JSONResponse({'status': 'updated', 'updated': updated})
        else:
            return JSONResponse({'status': 'no_changes', 'message': 'Aucun paramètre valide fourni'})
    
    except Exception as e:
        logger.error(f"Erreur mise à jour config: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


# Helper functions

async def add_log(level, message, detail=''):
    """Ajouter un log et envoyer via WebSocket natif uniquement avec couleurs ANSI"""
    from datetime import datetime
    
    # 🔥 FIX: Utiliser colorama si disponible, sinon codes ANSI bruts
    if colorama:
        from colorama import Fore, Style
        reset_code = Style.RESET_ALL
    else:
        # Codes ANSI bruts si colorama n'est pas disponible
        class Fore:
            RED = '\x1b[31m'
            YELLOW = '\x1b[33m'
            GREEN = '\x1b[32m'
            CYAN = '\x1b[36m'
        class Style:
            BRIGHT = '\x1b[1m'
            RESET_ALL = '\x1b[0m'
        reset_code = Style.RESET_ALL
    
    # 🔥 FIX: Ajouter couleurs ANSI selon le niveau
    color_codes = {
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT,
        'WARNING': Fore.YELLOW,
        'INFO': Fore.GREEN,
        'DEBUG': Fore.CYAN
    }
    reset_code = Style.RESET_ALL
    color = color_codes.get(level, '')
    
    # Message avec couleur ANSI et emojis préservés
    # 🔥 FIX: Préserver les emojis dans le message (✅📊❌⚠️ etc.)
    colored_message = f"{color}{message}{reset_code}"
    if detail:
        # Ajouter la couleur au détail aussi si nécessaire
        colored_message += f" {color}{detail}{reset_code}"
    
    entry = {
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'level': level,
        'message': colored_message,  # 🔥 FIX: Message avec couleurs ANSI et emojis
        'detail': detail,
        'raw_message': message  # Message sans couleur pour recherche
    }
    app_state['logs'].append(entry)
    
    # Garder seulement les 1000 derniers logs
    if len(app_state['logs']) > 1000:
        app_state['logs'] = app_state['logs'][-1000:]
    
    # 🔥 MIGRATION COMPLÈTE: Envoyer uniquement via WebSocket natif avec couleurs
    ws_mgr = state.get_ws_manager()
    if ws_mgr:
        await ws_mgr.emit('log', entry)
    
    # Logger avec couleur dans la console backend
    logger.info(f"{color}[{entry['timestamp']}] {entry['level']}: {message}{reset_code}")


async def initiate_backend_reboot(reason: str = 'manual') -> Dict:
    """Démarrer le processus de reboot backend (non bloquant)."""
    global backend_reboot_in_progress

    if backend_reboot_in_progress:
        await add_log('INFO', 'Backend reboot', 'Déjà en cours, nouvelle demande ignorée')
        return {'status': 'already_in_progress'}

    backend_reboot_in_progress = True
    info_msg = f"Demande de reboot backend reçue (raison: {reason})"
    await add_log('WARNING', 'Backend reboot', info_msg)

    ws_mgr = state.get_ws_manager()
    if ws_mgr:
        await ws_mgr.emit('backend_reboot', {
            'status': 'pending',
            'reason': reason,
            'timestamp': time.time()
        })

    asyncio.create_task(_perform_backend_reboot(reason))
    return {'status': 'rebooting', 'reason': reason}


async def _perform_backend_reboot(reason: str):
    """Arrêter proprement les services puis relancer le processus."""
    global backend_reboot_in_progress

    try:
        await add_log('INFO', 'Backend reboot', 'Arrêt des services en cours...')
        ws_mgr = state.get_ws_manager()
        if ws_mgr:
            await ws_mgr.emit('backend_reboot', {
                'status': 'shutting_down',
                'reason': reason,
                'timestamp': time.time()
            })

        # Arrêter scheduler
        sched = state.get_scheduler()
        if sched and getattr(sched, 'is_running', False):
            try:
                await sched.stop_async()
                await add_log('INFO', 'Backend reboot', 'Scheduler arrêté')
            except Exception as e:
                logger.warning(f"⚠️ Erreur arrêt scheduler (reboot): {e}")

        # Arrêter price provider websocket
        price_prov = state.get_price_provider()
        if price_prov and hasattr(price_prov, 'stop_websocket'):
            try:
                await price_prov.stop_websocket()
                await add_log('INFO', 'Backend reboot', 'WebSocket prix arrêté')
            except Exception as e:
                logger.warning(f"⚠️ Erreur arrêt price provider (reboot): {e}")

        # Fermer data logger PostgreSQL
        try:
            from core.callbacks.scanner_loop import get_pg_datalogger
            pg_datalogger = get_pg_datalogger()
            if pg_datalogger:
                pg_datalogger.close()
                await add_log('INFO', 'Backend reboot', 'PG DataLogger fermé')
        except Exception as e:
            logger.warning(f"⚠️ Erreur fermeture PG DataLogger (reboot): {e}")

        # Sauvegarder historique avant sortie
        try:
            save_trade_history()
        except Exception as e:
            logger.warning(f"⚠️ Erreur sauvegarde historique avant reboot: {e}")

        await asyncio.sleep(0.5)

        ws_mgr = state.get_ws_manager()
        if ws_mgr:
            await ws_mgr.emit('backend_reboot', {
                'status': 'restarting',
                'reason': reason,
                'timestamp': time.time()
            })

        await add_log('INFO', 'Backend reboot', 'Relance du processus backend...')

        python_cmd = sys.executable or 'python'
        script_path = os.path.abspath(sys.argv[0])
        args = sys.argv[1:]
        env = os.environ.copy()
        env['BACKEND_REBOOT_REASON'] = reason

        subprocess.Popen([python_cmd, script_path, *args], env=env, close_fds=os.name != 'nt')

        await asyncio.sleep(0.5)
        logger.info('♻️ Nouveau processus backend lancé, arrêt de l\'instance actuelle...')
        os._exit(0)

    except Exception as e:
        backend_reboot_in_progress = False
        logger.error(f"❌ Échec reboot backend: {e}")
        await add_log('ERROR', 'Backend reboot échoué', str(e))
        ws_mgr = state.get_ws_manager()
        if ws_mgr:
            await ws_mgr.emit('backend_reboot', {
                'status': 'error',
                'reason': reason,
                'error': str(e),
                'timestamp': time.time()
            })

# Main entry point

# 🔥 PHASE 4: Endpoints Dashboard
def calculate_max_drawdown(trade_history: List[Dict]) -> Dict:
    """
    🔥 PHASE 8: Calculer drawdown maximum historique (peak to trough)
    
    Returns:
        Dict avec max_dd, max_dd_date, current_dd
    """
    if not trade_history:
        return {'max_dd': 0, 'max_dd_date': None, 'current_dd': 0, 'current_peak': 0}
    
    # Calculer equity curve
    equity_curve = []
    cumulative = 0
    dates = []
    
    for trade in trade_history:
        cumulative += trade.get('gross_pnl_pct', 0)
        equity_curve.append(cumulative)
        dates.append(trade.get('timestamp', ''))
    
    # Trouver drawdown maximum
    peak = equity_curve[0] if equity_curve else 0
    peak_idx = 0
    max_dd = 0
    max_dd_idx = 0
    
    for i, equity in enumerate(equity_curve):
        if equity > peak:
            peak = equity
            peak_idx = i
        
        dd = ((equity - peak) / peak * 100) if peak > 0 else 0
        
        if dd < max_dd:
            max_dd = dd
            max_dd_idx = i
    
    # Drawdown actuel
    current_peak = max(equity_curve) if equity_curve else 0
    current_equity = equity_curve[-1] if equity_curve else 0
    current_dd = ((current_equity - current_peak) / current_peak * 100) if current_peak > 0 else 0
    
    return {
        'max_dd': round(max_dd, 2),
        'max_dd_date': dates[max_dd_idx] if max_dd_idx < len(dates) else None,
        'max_dd_from_peak': dates[peak_idx] if peak_idx < len(dates) else None,
        'current_dd': round(current_dd, 2),
        'current_peak': round(current_peak, 2)
    }


@app.post("/api/ml/retrain")
async def api_ml_retrain(request: Request):
    """
    🤖 Réentraîner le modèle ML avec hyperparamètres personnalisés
    """
    try:
        data = await request.json() if hasattr(request, 'json') else {}

        # Récupérer les hyperparamètres (avec valeurs par défaut)
        hyperparams = {
            'max_depth': int(data.get('max_depth', 6)),
            'min_child_weight': int(data.get('min_child_weight', 3)),
            'reg_alpha': float(data.get('reg_alpha', 0.5)),
            'reg_lambda': float(data.get('reg_lambda', 2.0)),
            'subsample': float(data.get('subsample', 0.8)),
            'colsample_bytree': float(data.get('colsample_bytree', 0.8)),
            'n_estimators': int(data.get('n_estimators', 300)),
            'learning_rate': float(data.get('learning_rate', 0.03))
        }

        logger.info(f"🤖 Démarrage réentraînement ML avec hyperparamètres: {hyperparams}")

        # Import du trainer
        from optimization.models.xgboost_trainer import XGBoostTrainer

        # Créer une instance du trainer
        trainer = XGBoostTrainer(model_name='xgboost_v1')

        # Lancer l'entraînement avec les hyperparamètres
        metrics = trainer.train(
            min_trades=100,
            n_estimators=hyperparams['n_estimators'],
            max_depth=hyperparams['max_depth'],
            learning_rate=hyperparams['learning_rate'],
            early_stopping_rounds=20,
            max_features=40,
            min_child_weight=hyperparams['min_child_weight'],
            reg_alpha=hyperparams['reg_alpha'],
            reg_lambda=hyperparams['reg_lambda'],
            subsample=hyperparams['subsample'],
            colsample_bytree=hyperparams['colsample_bytree'],
            gamma=0.1
        )

        if metrics is None:
            logger.error("❌ Échec réentraînement: metrics is None")
            return JSONResponse({'error': 'Échec du réentraînement'}, status_code=500)

        logger.info(f"✅ Réentraînement terminé: {metrics}")

        return JSONResponse({
            'success': True,
            'metrics': metrics,
            'hyperparams': hyperparams,
            'message': 'Modèle réentraîné avec succès'
        })

    except Exception as e:
        logger.error(f"❌ Erreur réentraînement ML: {e}", exc_info=True)
        return JSONResponse({'error': str(e)}, status_code=500)


@app.get("/api/dashboard/summary")
async def get_dashboard_summary():
    """Résumé des statistiques de trading"""
    init_instances()
    
    trades = app_state['trade_history']
    
    # Calculer statistiques
    total_trades = len(trades)
    wins = sum(1 for t in trades if t.get('net_pnl_usdt', 0) > 0)
    losses = total_trades - wins
    winrate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    
    # Profit total et aujourd'hui
    profit_total = sum(t.get('net_pnl_usdt', 0) for t in trades)
    today = datetime.now().date().isoformat()
    profit_today = sum(
        t.get('net_pnl_usdt', 0) 
        for t in trades 
        if t.get('timestamp', '').startswith(today)
    )
    
    # 🔥 PHASE 8: Max Drawdown Tracking (calcul précis)
    max_dd_info = calculate_max_drawdown(trades)
    
    # Equity curve pour graphique (basée sur PnL USDT)
    equity_curve = []
    running_equity = 0.0
    for trade in trades:
        running_equity += trade.get('net_pnl_usdt', 0)
        equity_curve.append(running_equity)
    
    # Win/Loss streaks
    win_streak = 0
    loss_streak = 0
    current_win_streak = 0
    current_loss_streak = 0
    
    for trade in reversed(trades):
        pnl = trade.get('net_pnl_usdt', 0)
        if pnl > 0:
            current_win_streak += 1
            current_loss_streak = 0
            if current_win_streak > win_streak:
                win_streak = current_win_streak
        else:
            current_loss_streak += 1
            current_win_streak = 0
            if current_loss_streak > loss_streak:
                loss_streak = current_loss_streak
    
    # Recovery Mode
    recovery_mode_active = False
    pos_mgr = state.get_position_manager()
    if pos_mgr and pos_mgr.config:
        recovery_mode_active = pos_mgr.config.recovery_mode_active
    
    return JSONResponse({
        'total_trades': total_trades,
        'wins': wins,
        'losses': losses,
        'winrate': round(winrate, 2),
        'profit_total': round(profit_total, 4),
        'profit_today': round(profit_today, 4),
        'drawdown': round(max_dd_info.get('current_dd', 0), 2),  # Drawdown actuel (%)
        'drawdown_max': max_dd_info.get('max_dd', 0),  # Drawdown max historique (%)
        'drawdown_max_date': max_dd_info.get('max_dd_date'),  # Date du max drawdown
        'current_peak': max_dd_info.get('current_peak', 0),  # Pic actuel (%)
        'win_streak': win_streak,
        'loss_streak': loss_streak,
        'recovery_mode_active': recovery_mode_active,
        'equity_curve': equity_curve[-100:]  # Derniers 100 points
    })

@app.get("/api/dashboard/trades-history")
async def get_trades_history(limit: int = 10000):
    """
    🔥 SESSION-BASED: Historique des trades de la session actuelle uniquement

    Les stats et l'historique affichés sont réinitialisés à chaque redémarrage du backend,
    mais TOUS les trades sont conservés dans PostgreSQL de façon permanente.
    """
    # Récupérer les trades de la session actuelle uniquement
    current_session_trades = []
    analytics_db = state.get_analytics_db()
    sess_id = state.session_id
    if analytics_db and sess_id:
        try:
            all_trades = analytics_db.get_trades(limit=limit)
            current_session_trades = [t for t in all_trades if t.get('session_id') == sess_id]
        except Exception as e:
            logger.error(f"❌ Erreur récupération trades session: {e}")

    # Retourner les plus récents en premier
    recent_trades = list(reversed(current_session_trades))
    return JSONResponse(recent_trades)


@app.get("/api/export/trades")
async def export_trades_csv(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    format: str = "csv"
):
    """
    🔥 PHASE 8: Exporter trades en CSV ou JSON
    
    Args:
        start_date: Date début (YYYY-MM-DD)
        end_date: Date fin (YYYY-MM-DD)
        format: csv ou json (défaut: csv)
    """
    trades = app_state['trade_history']
    
    # Filtrer par date si fourni
    if start_date and end_date:
        filtered_trades = [
            t for t in trades
            if start_date <= t.get('date', '') <= end_date
        ]
    else:
        filtered_trades = trades
    
    if format == "json":
        return JSONResponse(filtered_trades)
    
    # Format CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        'timestamp', 'date', 'time', 'symbol', 'direction',
        'entry', 'exit', 'gross_pnl_pct', 'gross_pnl_usdt',
        'net_pnl_pct', 'net_pnl_usdt', 'fees', 'slippage',
        'total_costs', 'reason', 'duration'
    ])
    
    writer.writeheader()
    for trade in filtered_trades:
        writer.writerow({
            'timestamp': trade.get('timestamp', ''),
            'date': trade.get('date', ''),
            'time': trade.get('time', ''),
            'symbol': trade.get('symbol', ''),
            'direction': trade.get('direction', ''),
            'entry': trade.get('entry', 0),
            'exit': trade.get('exit', 0),
            'gross_pnl_pct': trade.get('gross_pnl_pct', 0),
            'gross_pnl_usdt': trade.get('gross_pnl_usdt', 0),
            'net_pnl_pct': trade.get('net_pnl_pct', 0),
            'net_pnl_usdt': trade.get('net_pnl_usdt', 0),
            'fees': trade.get('fees', 0),
            'slippage': trade.get('slippage', 0),
            'total_costs': trade.get('total_costs', 0),
            'reason': trade.get('reason', ''),
            'duration': trade.get('duration', 0)
        })
    
    output.seek(0)
    
    filename = f"trades_{start_date}_{end_date}.csv" if (start_date and end_date) else "trades_all.csv"
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def _get_pg_connection_for_export() -> Tuple[Any, Callable[[], None]]:
    """Obtenir une connexion PostgreSQL même si le bot n'est pas actif."""
    pg_datalogger = None
    try:
        from core.callbacks.scanner_loop import get_pg_datalogger
        pg_datalogger = get_pg_datalogger()
    except Exception:
        pg_datalogger = None

    if pg_datalogger and getattr(pg_datalogger, "enabled", True):
        conn = pg_datalogger._get_connection()
        return conn, lambda: pg_datalogger._return_connection(conn)

    import psycopg2

    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        dbname=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )

    return conn, conn.close


@app.get("/api/datalogger/export/excel")
async def export_datalogger_excel(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50
):
    """
    🔥 Export des données du datalogger en Excel (.xlsx)
    
    Args:
        start_date: Date début (YYYY-MM-DD) - optionnel
        end_date: Date fin (YYYY-MM-DD) - optionnel
        limit: Nombre de lignes par table (défaut: 50, max: 10000)
    
    Returns:
        Fichier Excel (.xlsx) avec plusieurs onglets (scans, opportunities, trades)
    """
    # Valider et limiter le nombre de lignes
    limit = max(1, min(limit, 10000))  # Entre 1 et 10000
    try:
        # Vérifier si openpyxl est installé
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment
            from openpyxl.utils import get_column_letter
        except ImportError:
            return JSONResponse(
                {"error": "openpyxl non installé. Installez-le avec: pip install openpyxl"},
                status_code=500
            )

        try:
            conn, release_conn = _get_pg_connection_for_export()
        except Exception as conn_error:
            logger.error("❌ Impossible de se connecter à PostgreSQL pour l'export: %s", conn_error)
            return JSONResponse(
                {"error": "Impossible de se connecter à PostgreSQL"},
                status_code=503
            )
        
        try:
            from psycopg2.extras import RealDictCursor
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Récupérer toutes les tables du schéma public
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            )
            table_names = [row['table_name'] for row in cursor.fetchall()]

            wb = Workbook()
            summary_sheet = wb.active
            summary_sheet.title = "Summary"
            summary_sheet.append(["Table", "Rows"])

            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF")

            for table_name in table_names:
                ws = wb.create_sheet(table_name[:31])

                # Récupérer les colonnes de la table (pour appliquer les filtres date intelligemment)
                cursor.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = %s
                    """,
                    (table_name,)
                )
                column_names = [row['column_name'] for row in cursor.fetchall()]

                base_query = f"SELECT * FROM {table_name} WHERE 1=1"
                params: List[str] = []

                has_timestamp = 'timestamp' in column_names
                has_timestamp_entry = 'timestamp_entry' in column_names

                if start_date and (has_timestamp or has_timestamp_entry):
                    if has_timestamp and has_timestamp_entry:
                        base_query += " AND (timestamp >= %s OR timestamp_entry >= %s)"
                        params.extend([f"{start_date} 00:00:00", f"{start_date} 00:00:00"])
                    elif has_timestamp:
                        base_query += " AND timestamp >= %s"
                        params.append(f"{start_date} 00:00:00")
                    elif has_timestamp_entry:
                        base_query += " AND timestamp_entry >= %s"
                        params.append(f"{start_date} 00:00:00")

                if end_date and (has_timestamp or has_timestamp_entry):
                    if has_timestamp and has_timestamp_entry:
                        base_query += " AND (timestamp <= %s OR timestamp_entry <= %s)"
                        params.extend([f"{end_date} 23:59:59", f"{end_date} 23:59:59"])
                    elif has_timestamp:
                        base_query += " AND timestamp <= %s"
                        params.append(f"{end_date} 23:59:59")
                    elif has_timestamp_entry:
                        base_query += " AND timestamp_entry <= %s"
                        params.append(f"{end_date} 23:59:59")

                # 🔥 FIX: Limiter TOUTES les tables au nombre de lignes demandé
                if table_name == 'ml_calibration':
                    base_query += f" ORDER BY updated_at DESC LIMIT {limit}"
                elif table_name == 'ml_calibration_history':
                    if 'snapshot_at' in column_names:
                        base_query += f" ORDER BY snapshot_at DESC LIMIT {limit}"
                    elif 'created_at' in column_names:
                        base_query += f" ORDER BY created_at DESC LIMIT {limit}"
                    else:
                        base_query += f" ORDER BY id DESC LIMIT {limit}"
                elif table_name == 'circuit_breaker_events':
                    # 🔥 SPRINT 1: Événements circuit breaker triés par timestamp
                    base_query += f" ORDER BY timestamp DESC LIMIT {limit}"
                elif table_name == 'market_regime_history':
                    # 🔥 SPRINT 1: Historique régime trié par timestamp
                    base_query += f" ORDER BY timestamp DESC LIMIT {limit}"
                elif table_name == 'trade_atr_metrics':
                    # 🔥 FIX 10/12/2025: Trier par created_at DESC (plus récent en haut)
                    base_query += f" ORDER BY created_at DESC LIMIT {limit}"
                elif table_name == 'trades':
                    # 🔥 FIX 10/12/2025: Trier par created_at DESC (plus récent en haut)
                    base_query += f" ORDER BY created_at DESC LIMIT {limit}"
                elif table_name == 'scan_logs':
                    # 🔥 FIX 10/12/2025: Trier par timestamp DESC (plus récent en haut)
                    base_query += f" ORDER BY timestamp DESC LIMIT {limit}"
                elif table_name == 'opportunities':
                    # 🔥 FIX 10/12/2025: Trier par timestamp DESC (plus récent en haut)
                    base_query += f" ORDER BY timestamp DESC LIMIT {limit}"
                elif has_timestamp:
                    base_query += f" ORDER BY timestamp DESC LIMIT {limit}"
                elif has_timestamp_entry:
                    base_query += f" ORDER BY timestamp_entry DESC LIMIT {limit}"
                else:
                    base_query += f" LIMIT {limit}"  # Fallback: limiter aux premières lignes

                cursor.execute(base_query, params)
                rows = cursor.fetchall()
                headers = [desc.name for desc in cursor.description] if cursor.description else []

                # 🔥 FIX: Pour scan_logs, décomposer params_snapshot et masquer reject_reason
                if table_name == 'scan_logs':
                    # Remplacer params_snapshot par colonnes config_* (déjà présentes)
                    # Supprimer params_snapshot et reject_reason des headers
                    headers = [h for h in headers if h not in ['params_snapshot', 'reject_reason']]
                    # S'assurer que reject_reason_category est présent
                    if 'reject_reason_category' not in headers:
                        headers.append('reject_reason_category')
                    # 🔥 SPRINT 1: S'assurer que les colonnes régime sont présentes
                    regime_columns = ['market_regime', 'market_regime_avg_atr', 'market_regime_avg_adx']
                    for col in regime_columns:
                        if col not in headers:
                            headers.append(col)
                # 🔥 FIX: Pour trades, masquer config_snapshot et s'assurer que les colonnes config_* sont présentes
                if table_name == 'trades':
                    headers = [h for h in headers if h != 'config_snapshot']
                    config_columns = [
                        'config_min_score_required', 'config_snr_threshold',
                        'config_optimal_atr_min_1m', 'config_optimal_atr_max_1m',
                        'config_optimal_atr_min_5m', 'config_optimal_atr_max_5m',
                        'config_volume_multiplier', 'config_use_confluence',
                        'config_invert_signals',
                        'config_use_anti_whipsaw', 'config_whipsaw_lookback',
                        'config_whipsaw_threshold_pct', 'config_whipsaw_max_alternations',
                        'config_use_retest_confirmation', 'config_retest_tolerance_pct',
                        'config_retest_timeout_seconds', 'config_use_cooldown',
                        'config_cooldown_seconds', 'config_cooldown_same_symbol',
                        'config_use_candle_close', 'config_candle_close_threshold_seconds',
                        'config_use_momentum_continuity', 'config_momentum_lookback',
                        'delta_volume', 'imbalance_normalized', 'book_depth_ratio',
                        # 🔥 SPRINT 1: Colonnes Market Regime et Circuit Breaker
                        'entry_market_regime', 'entry_market_regime_avg_atr', 'entry_market_regime_avg_adx',
                        'entry_min_score_required', 'entry_atr_mult_sl', 'entry_atr_mult_tp',
                        'entry_cb_state', 'entry_consecutive_losses', 'entry_daily_pnl_pct', 'entry_cb_score_boost'
                    ]

                    # 🛡️ Anti-Giveback / Trailing MFE
                    anti_giveback_columns = [
                        'config_trailing_mfe_enabled',
                        'config_trailing_mfe_trigger_pct',
                        'config_trailing_mfe_lock_in_pct',
                        'config_partial_tp_be_lock_in_pct',
                        'trailing_mfe_triggered',
                        'trailing_mfe_triggered_at',
                        'trailing_mfe_trigger_pnl_pct',
                        'trailing_mfe_trigger_price',
                        'trailing_mfe_new_sl'
                    ]
                    config_columns.extend(anti_giveback_columns)

                    for col in config_columns:
                        if col not in headers:
                            headers.append(col)
                    
                    # 🔥 NOUVEAU: Ajouter colonne "data_complete" pour identifier trades complets
                    if 'data_complete' not in headers:
                        headers.append('data_complete')

                # 🔥 PHASE 0: Pour trade_atr_metrics, s'assurer que les colonnes V2 sont présentes
                if table_name == 'trade_atr_metrics':
                    v2_columns = [
                        # 🔥 ATR Blendé/Clampé (colonnes critiques pour cohérence)
                        'entry_atr_pct_used', 'entry_atr_blended',
                        # Saisonnalité
                        'session_market', 'hour_utc', 'day_of_week', 'is_weekend',
                        # Régime V2 Metadata
                        'regime_detection_method', 'regime_atr_median', 'regime_atr_smoothed',
                        'regime_confidence', 'regime_stability_minutes',
                        # ML Régime
                        'regime_ml_predicted', 'regime_ml_confidence', 'regime_ml_vs_rule_match',
                        # What-If Régime
                        'pnl_if_calme_params', 'pnl_if_normal_params', 'pnl_if_volatile_params',
                        'optimal_regime_retrospective',
                        # Session multiplier
                        'session_atr_multiplier'
                    ]
                    for col in v2_columns:
                        if col not in headers:
                            headers.append(col)

                # 🔥 PHASE 0: Pour scan_logs, ajouter colonnes session/régime
                if table_name == 'scan_logs':
                    scan_v2_columns = ['session_market', 'hour_utc', 'regime_at_scan', 'regime_confidence_at_scan']
                    for col in scan_v2_columns:
                        if col not in headers:
                            headers.append(col)

                # 🔥 PHASE 0: Pour market_regime_history, ajouter colonnes V2
                if table_name == 'market_regime_history':
                    mrh_v2_columns = [
                        'detection_method', 'atr_median', 'atr_smoothed', 
                        'session_market', 'hysteresis_applied', 'outliers_filtered_count', 'ml_confidence'
                    ]
                    for col in mrh_v2_columns:
                        if col not in headers:
                            headers.append(col)

                if headers:
                    ws.append(headers)
                    for cell in ws[1]:
                        cell.fill = header_fill
                        cell.font = header_font
                        cell.alignment = Alignment(horizontal="center")
                for row in rows:
                    # Convertir valeurs complexes (arrays, dicts) en string JSON pour Excel
                    excel_row = []
                    for h in headers:
                        # 🔥 NOUVEAU: Calculer data_complete pour trades
                        if h == 'data_complete' and table_name == 'trades':
                            # Complet si scan_log_id n'est pas NULL
                            is_complete = row.get('scan_log_id') is not None
                            value = '✅ Complet' if is_complete else '⚠️ Incomplet (ancien)'
                        else:
                            value = row.get(h)  # Utiliser .get() car certaines clés peuvent ne pas exister
                        
                        # Convertir types non-supportés par Excel
                        if isinstance(value, (list, dict)):
                            excel_row.append(json.dumps(value, ensure_ascii=False))
                        elif value is None:
                            excel_row.append('')
                        elif isinstance(value, datetime):
                            # Excel ne supporte pas les timezones - convertir en datetime naive
                            excel_row.append(value.replace(tzinfo=None) if value.tzinfo else value)
                        else:
                            excel_row.append(value)
                    ws.append(excel_row)
                for col in range(1, len(headers) + 1):
                    ws.column_dimensions[get_column_letter(col)].width = 15

                summary_sheet.append([table_name, len(rows)])

            cursor.close()
            try:
                release_conn()
            except Exception as conn_err:
                logger.debug(f"Note: Erreur retour connexion (non-critique): {conn_err}")

            from io import BytesIO
            output = BytesIO()
            wb.save(output)
            output.seek(0)

            filename = f"datalogger_export_{start_date}_{end_date}.xlsx" if (start_date and end_date) else f"datalogger_export_all_{datetime.now().strftime('%Y%m%d')}.xlsx"

            return StreamingResponse(
                output,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
            
        except Exception as e:
            try:
                release_conn()
            except Exception:
                pass  # Connexion déjà fermée ou non du pool
            logger.error(f"❌ Erreur export Excel: {e}", exc_info=True)
            return JSONResponse(
                {"error": f"Erreur export Excel: {str(e)}"},
                status_code=500
            )
            
    except Exception as e:
        logger.error(f"❌ Erreur export Excel: {e}", exc_info=True)
        return JSONResponse(
            {"error": f"Erreur export Excel: {str(e)}"},
            status_code=500
        )


def _generate_trading_config_workbook() -> io.BytesIO:
    """Générer un classeur Excel avec la configuration de trading."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
        from openpyxl.workbook.workbook import Workbook as OpenpyxlWorkbook
    except ImportError as exc:
        raise ImportError("openpyxl non installé. Installez-le avec: pip install openpyxl") from exc

    try:
        from config import TRADING_CONFIG, RISK_CONFIG, CONDITION_WEIGHTS, TREND_BONUS_CONFIG
        from config import RETRY_CONFIG, CIRCUIT_BREAKER_CONFIG, WEBSOCKET_CONFIG
    except Exception as exc:
        raise RuntimeError(f"Impossible de charger la configuration: {exc}") from exc

    categories = _organize_trading_config_for_export(TRADING_CONFIG)
    rows = _flatten_trading_config_for_excel(categories)

    wb: OpenpyxlWorkbook = Workbook()
    ws = wb.active
    ws.title = "Trading_Config"

    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    alignment_center = Alignment(horizontal="center")

    headers = ["Catégorie", "Variable", "Valeur"]
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = alignment_center

    for row in rows:
        ws.append([row['category'], row['variable'], row['value']])

    for col_idx in range(1, len(headers) + 1):
        column_letter = get_column_letter(col_idx)
        ws.column_dimensions[column_letter].width = 35 if col_idx == 1 else 28

    summary_sheet = wb.create_sheet("Autres_Config")
    summary_sheet.append(["Section", "Clé", "Valeur"])
    for cell in summary_sheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = alignment_center

    def append_config_block(title: str, config_dict: Dict[str, Any]):
        if not config_dict:
            return
        summary_sheet.append([title, "", ""])
        last_row = summary_sheet.max_row
        for cell in summary_sheet[last_row]:
            cell.font = Font(bold=True)
        for key, value in config_dict.items():
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value, ensure_ascii=False)
            else:
                value_str = value
            summary_sheet.append(["", key, value_str])

    append_config_block("RISK_CONFIG", RISK_CONFIG)
    append_config_block("CONDITION_WEIGHTS", CONDITION_WEIGHTS)
    append_config_block("TREND_BONUS_CONFIG", TREND_BONUS_CONFIG)
    append_config_block("RETRY_CONFIG", RETRY_CONFIG)
    append_config_block("CIRCUIT_BREAKER_CONFIG", CIRCUIT_BREAKER_CONFIG)
    append_config_block("WEBSOCKET_CONFIG", WEBSOCKET_CONFIG)

    for col_idx in range(1, 4):
        summary_sheet.column_dimensions[get_column_letter(col_idx)].width = 35 if col_idx == 1 else 30

    from io import BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return output


async def _export_trading_config_excel(extension: str = "xlsx"):
    media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    try:
        output = _generate_trading_config_workbook()
    except ImportError as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    except RuntimeError as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    filename = f"trading_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}"

    return StreamingResponse(
        output,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/api/config/export-xlsx")
async def export_trading_config_xlsx():
    return await _export_trading_config_excel("xlsx")


@app.get("/api/config/export-xlsm")
async def export_trading_config_xlsm():
    """Alias legacy vers l'export XLSX (compatibilité)."""
    return await _export_trading_config_excel("xlsx")


@app.delete("/api/datalogger/reset")
async def reset_datalogger_db():
    """
    🔥 Reset complet de la base de données PostgreSQL du datalogger
    
    ATTENTION: Cette opération supprime TOUTES les données (scans, opportunities, trades, etc.)
    
    Returns:
        Message de confirmation
    """
    try:
        from core.callbacks.scanner_loop import get_pg_datalogger
        pg_datalogger = get_pg_datalogger()
        
        if not pg_datalogger or not pg_datalogger.enabled:
            return JSONResponse(
                {"error": "PostgreSQL DataLogger non disponible"},
                status_code=503
            )
        
        conn = pg_datalogger._get_connection()
        if not conn:
            return JSONResponse(
                {"error": "Impossible de se connecter à PostgreSQL"},
                status_code=503
            )
        
        try:
            cursor = conn.cursor()
            
            # Supprimer toutes les données (dans l'ordre pour respecter les contraintes FK)
            tables = [
                'trades',
                'opportunities',
                'scan_logs',
                'scan_errors',
                'market_context',
                'config_snapshots',
                'trading_sessions'
            ]
            
            deleted_counts = {}
            for table in tables:
                cursor.execute(f"DELETE FROM {table}")
                deleted_counts[table] = cursor.rowcount
            
            conn.commit()
            cursor.close()
            pg_datalogger._return_connection(conn)
            
            total_deleted = sum(deleted_counts.values())
            logger.warning(f"🗑️  Base de données PostgreSQL resetée: {total_deleted} enregistrements supprimés")
            
            return JSONResponse({
                "success": True,
                "message": f"Base de données resetée avec succès",
                "deleted": deleted_counts,
                "total_deleted": total_deleted
            })
            
        except Exception as e:
            conn.rollback()
            pg_datalogger._return_connection(conn)
            logger.error(f"❌ Erreur reset DB: {e}", exc_info=True)
            return JSONResponse(
                {"error": f"Erreur reset DB: {str(e)}"},
                status_code=500
            )
            
    except Exception as e:
        logger.error(f"❌ Erreur reset DB: {e}", exc_info=True)
        return JSONResponse(
            {"error": f"Erreur reset DB: {str(e)}"},
            status_code=500
        )


if __name__ == '__main__':
    import uvicorn
    import socket
    
    # 🔥 FIX: Ne PAS charger l'historique au démarrage
    # L'historique est réinitialisé à chaque redémarrage du backend
    # mais persiste pendant toute la session tant que le backend tourne
    # load_trade_history()  # Désactivé: reset à chaque démarrage
    app_state['trade_history'] = []
    logger.info("📝 Historique trades réinitialisé (nouvelle session backend)")
    
    # Récupérer le port depuis les arguments (défaut: 5000)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    
    logger.info("🚀 Trade Cursor v7.0 démarré")
    logger.info("📊 FastAPI (async natif) + WebSocket natif")
    logger.info("🔥 Backend API uniquement - Frontend Svelte gère l'interface")
    logger.info("")
    logger.info("=" * 70)
    logger.info("📍 URLs DISPONIBLES (Instance Port: {})".format(port))
    logger.info("=" * 70)
    logger.info(f"💚 API Health check          → http://localhost:{port}/api/health")
    logger.info(f"📡 WebSocket                 → ws://localhost:{port}/ws")
    logger.info(f"📈 API Stats                 → http://localhost:{port}/api/stats")
    logger.info(f"📋 API Trades (filtres)      → http://localhost:{port}/api/trades?limit=10")
    logger.info(f"❌ API Setups rejetés        → http://localhost:{port}/api/setups/rejected")
    logger.info(f"✅ API Setups validés        → http://localhost:{port}/api/setups/validated")
    logger.info(f"📥 API Export (CSV/JSON)     → http://localhost:{port}/api/export?format=csv")
    logger.info(f"📊 API Export Excel (XLSX)   → http://localhost:{port}/api/datalogger/export/excel")
    logger.info(f"🗑️  API Reset DB             → DELETE http://localhost:{port}/api/datalogger/reset")
    logger.info(f"🔄 API Backtest              → POST http://localhost:{port}/api/backtest")
    logger.info(f"🤖 API ML Optimize           → POST http://localhost:{port}/api/optimize")
    logger.info("=" * 70)
    logger.info("")
    
    # 🔥 FIX: Vérifier que le port est disponible avant de démarrer
    def is_port_available(port):
        """Vérifier si le port est disponible"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            result = sock.connect_ex(('127.0.0.1', port))
            return result != 0  # Port disponible si connexion échoue
        finally:
            sock.close()
    
    # 🔥 FIX: Essayer le port demandé, puis chercher un port disponible
    original_port = port
    max_attempts = 10
    attempt = 0
    
    while not is_port_available(port) and attempt < max_attempts:
        logger.warning(f"⚠️ Port {port} déjà utilisé, essai du port {port + 1}...")
        port += 1
        attempt += 1
    
    if not is_port_available(port):
        logger.error(f"❌ Impossible de trouver un port disponible après {max_attempts} tentatives (à partir du port {original_port})")
        sys.exit(1)
    
    if port != original_port:
        logger.info(f"✅ Port changé de {original_port} à {port}")
    
    # 🔥 FIX CRITIQUE: Forcer l'initialisation ICI car le lifespan FastAPI ne s'exécute pas
    # Cette approche garantit que init_instances() est TOUJOURS appelé au démarrage
    print("🚀 INIT FORCÉ: Initialisation de init_instances() AVANT uvicorn.run()...")
    logger.info("🚀 INIT FORCÉ: Initialisation de init_instances() AVANT uvicorn.run()...")
    try:
        init_instances()
        print("✅ INIT FORCÉ: init_instances() terminé avec succès")
        logger.info("✅ INIT FORCÉ: init_instances() terminé avec succès")
        
        # Vérifier que live_order_manager est bien initialisé
        live_mgr = state.get_live_order_manager()
        if live_mgr:
            dry_run_status = getattr(live_mgr, 'dry_run', None)
            mode_str = 'DRY_RUN' if dry_run_status else 'LIVE RÉEL'
            print(f"✅ LiveOrderManager actif | Mode: {mode_str}")
            logger.info(f"✅ LiveOrderManager actif | Mode: {mode_str}")
        else:
            print("📝 LiveOrderManager non initialisé (mode PAPER ou config manquante)")
            logger.info("📝 LiveOrderManager non initialisé (mode PAPER ou config manquante)")
    except Exception as e:
        print(f"❌ INIT FORCÉ: Erreur initialisation: {e}")
        logger.error(f"❌ INIT FORCÉ: Erreur initialisation: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    try:
        # 🔥 MIGRATION COMPLÈTE: Lancer FastAPI avec WebSocket natif uniquement
        uvicorn.run(app, host='0.0.0.0', port=port, log_level="info", lifespan="on")
    except OSError as e:
        logger.error(f"❌ Erreur binding port {port}: {e}")
        logger.error(f"Vérifiez que le port {port} n'est pas déjà utilisé")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Erreur démarrage serveur: {e}", exc_info=True)
        sys.exit(1)
