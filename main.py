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
import uvicorn
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
# 🔥 IMPORT CRITIQUE: ErrorHistoryManager (obligatoire)
try:
    from utils.error_history import ErrorHistoryManager
except ImportError as e:
    logging.error(f"❌ Import critique ErrorHistoryManager échoué: {e}")
    # Créer une classe fallback minimale
    class ErrorHistoryManager:
        def __init__(self, max_errors=1000):
            self.errors = []
        def add_error(self, level, message, detail="", raw_message=""):
            self.errors.append({"level": level, "message": message, "detail": detail, "raw_message": raw_message})
        def get_errors(self, limit=None):
            return self.errors[-limit:] if limit else self.errors
        def clear_errors(self):
            self.errors.clear()

try:
    from core.analytics_database import AnalyticsDatabase
    from notifications import create_notification_manager
    from utils.logger import setup_logger
    from core.exceptions import TradeCursorError, DatabaseConnectionError, ConfigurationError, NetworkError, NotificationError
    from api.routes import router as api_router, set_analytics_db, set_position_manager, set_notification_manager, set_instance_port, set_app_state, set_websocket_manager as set_websocket_manager_routes
except ImportError as e:
    logging.warning(f"Architecture V2 imports (optionnels): {e}")
    # Définir toutes les variables manquantes comme None
    AnalyticsDatabase = None
    get_notification_manager = None
    create_notification_manager = None
    setup_logger = None
    api_router = None
    set_analytics_db = None
    set_position_manager = None
    set_notification_manager = None
    set_instance_port = None
    set_app_state = None
    set_websocket_manager_routes = None

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

# 🔥 Ajouter handler pour logger les erreurs vers PostgreSQL scan_errors
try:
    from core.error_logger import ErrorLoggerHandler
    error_db_handler = ErrorLoggerHandler(level=logging.ERROR)
    logging.getLogger().addHandler(error_db_handler)
    logger.info("✅ ErrorLoggerHandler ajouté - Les erreurs seront loggées vers scan_errors")
except Exception as e:
    logger.warning(f"⚠️ Impossible d'ajouter ErrorLoggerHandler: {e}")

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

# 🔥 INSTANCE GLOBALE: ErrorHistoryManager pour toute l'application
global_error_history = ErrorHistoryManager(max_errors=1000)
logger.info("✅ ErrorHistoryManager global initialisé")

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
        trailing_max_distance=trading_config.get('trailing_max_distance'),
        trailing_pnl_cap=trading_config.get('trailing_pnl_cap')
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

        # 🔥 POST-EXIT ANALYSIS: Démarrer la boucle de tracking post-exit
        try:
            from core.callbacks.post_exit_loop import start_post_exit_loop, set_price_provider as set_post_exit_price_provider
            set_post_exit_price_provider(state.get_price_provider())
            await start_post_exit_loop()
            logger.info("✅ Post-Exit Loop démarrée")
        except Exception as e:
            logger.warning(f"⚠️ Post-Exit Loop non démarrée (non-bloquant): {e}")

        # 🔥 POST-EXIT PERSISTENCE: Restaurer les trackers actifs après redémarrage
        try:
            from core.post_exit.manager import get_post_exit_manager
            post_exit_mgr = get_post_exit_manager()
            restored_count = await post_exit_mgr.restore_active_trackers()
            if restored_count > 0:
                logger.info(f"🔄 Post-Exit: {restored_count} trackers restaurés depuis DB")
            else:
                logger.info("ℹ️ Post-Exit: Aucun tracker à restaurer")
        except Exception as e:
            logger.warning(f"⚠️ Post-Exit restore échoué (non-bloquant): {e}")

        yield

        logger.info("🟢 LIFESPAN YIELD: Execution principale terminée, début du shutdown")

    finally:
        # 🔥 POST-EXIT PERSISTENCE: Sauvegarder les trackers actifs AVANT shutdown
        try:
            from core.post_exit.manager import get_post_exit_manager
            post_exit_mgr = get_post_exit_manager()
            if post_exit_mgr.get_active_trackers_count() > 0:
                logger.info(f"💾 Post-Exit: Persistance de {post_exit_mgr.get_active_trackers_count()} trackers actifs...")
                await post_exit_mgr.cleanup_and_persist()
        except Exception as e:
            logger.warning(f"⚠️ Post-Exit persist échoué: {e}")

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

                # 🔥 POST-EXIT ANALYSIS: Arrêter la boucle de tracking
                try:
                    from core.callbacks.post_exit_loop import stop_post_exit_loop
                    await stop_post_exit_loop()
                    logger.info("✅ Post-Exit Loop arrêtée proprement")
                except Exception as e:
                    logger.debug(f"Post-Exit Loop arrêt ignoré: {e}")

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
                                    # ATR-based SL only in ATR mode
                                    if tp_sl_mode == 'ATR' and atr and entry_price:
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
                                    if tp_sl_mode == 'ATR' and atr and entry_price:
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
                                                                    ml_confidence=ml_conf_pct,
                                                                    ml_threshold_used=gb_min_confidence * 100
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
                    
                    # 🔥 FIX: Récupérer le contexte Market Regime pour l'opportunity
                    market_regime_data = {}
                    try:
                        from core.market_regime_selector import get_regime_selector
                        regime_selector = get_regime_selector()
                        if regime_selector:
                            regime_status = regime_selector.get_status()
                            market_regime_data = {
                                'market_regime': regime_status.get('current_regime'),
                                'market_regime_score': regime_status.get('avg_atr'),
                                'market_regime_confidence': regime_status.get('confidence', 0.5),
                                'market_regime_reason': regime_status.get('reason'),
                                'market_regime_details': {
                                    'avg_atr': regime_status.get('avg_atr'),
                                    'avg_adx': regime_status.get('avg_adx'),
                                    'sample_count': regime_status.get('atr_sample_count')
                                },
                                'session_context': regime_status.get('session_context'),
                                'market_regime_signal': regime_status.get('signal')
                            }
                    except Exception as e:
                        logger.debug(f"⚠️ Impossible de récupérer régime pour opportunity: {e}")
                    
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
                        # 🔥 FIX: Ajouter les champs Market Regime
                        **market_regime_data
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
    
    🔥 NEW: Inclut le reset de l'historique des erreurs au démarrage

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
    
    # 🔥 NEW: Reset de l'historique des erreurs au démarrage du backend
    try:
        from utils.error_history import reset_error_history
        reset_error_history()
        logger.info("🗑️ Historique des erreurs réinitialisé au démarrage")
    except Exception as e:
        logger.debug(f"Erreur reset historique erreurs: {e}")
    
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
        
        # Injecter ws_manager dans les routes
        if set_websocket_manager_routes:
            set_websocket_manager_routes(state.get_ws_manager())
        
        # Injecter app_state proxy dans les routes
        if set_app_state:
            set_app_state(state.get_legacy_proxy())
    
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
        # ATR mode only when tp_sl_mode == 'ATR'
        pos_config.use_atr = (tp_sl_mode == 'ATR')
        
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
        if set_position_manager and callable(set_position_manager):
            try:
                set_position_manager(state.get_position_manager())
                logger.info("✅ Position Manager injecté dans API routes")
            except Exception as e:
                logger.warning(f"⚠️ Erreur injection Position Manager dans API routes: {e}")

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


# === CORE ROUTES modularisées ===
# Les routes API sont maintenant modularisées dans api/routes/
# et incluses via api_router au début du fichier.
# Les anciens blocs de routes redondants ont été supprimés.

@app.get("/favicon.ico")
async def favicon():
    """Favicon (évite 404)"""
    from fastapi.responses import Response
    return Response(content=b'', media_type='image/x-icon')

# === END OF CORE LOGIC ===

# --- Les fonctions utilitaires (ex: simulate_optimal_performance) sont conservées ---

# --- Fin de la section modularisée ---


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


# 🔥 MIGRATION COMPLÈTE: Endpoint WebSocket modularisé vers api/routes/websocket.py


# 🔥 MIGRATION COMPLÈTE: Endpoint REST /api/state modularisé vers api/routes/dashboard.py


# 🔥 MIGRATION COMPLÈTE: handle_client_command modularisée vers api/routes/websocket.py
# Toute la logique de commande WebSocket est maintenant gérée par les modules dédiés.

# 🔥 MIGRATION COMPLÈTE: Endpoints REST modularisés vers api/routes/
# Les routes /api/config, /api/metrics, /api/dashboard, /api/export, etc. 
# sont maintenant gérées par api_router.

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

if __name__ == '__main__':
    import socket
    
    # 🔥 FIX: Ne PAS charger l'historique au démarrage
    # L'historique est réinitialisé à chaque redémarrage du backend
    # mais persiste pendant toute la session tant que le backend tourne
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
