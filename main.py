#!/usr/bin/env python3
"""
Trade Cursor v7.0 - Application FastAPI (async natif)
Interface HTML identique à v5.1 avec backend Python
"""

# ⚠️ IMPORTANT : Charger .env AVANT tout autre import
from dotenv import load_dotenv
load_dotenv()

import sys
import atexit
import asyncio
import logging
import json
import os
import time
import threading
import traceback
import uvicorn
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple, Callable
from collections import OrderedDict

# 🔥 SPRINT 2.1: StateManager for centralized state management
from core.state_manager import get_state_manager

# FastAPI imports
from fastapi import FastAPI, Request, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError

# 🔥 v7.0: Imports complets
try:
    from core.bootstrap import init_instances, run_initial_top_pairs_scan
    from utils.logging_utils import add_log
    from core.websocket_manager import get_websocket_manager
    from core.shutdown import GracefulShutdown
except ImportError as e:
    logging.error(f"❌ Erreur imports critiques: {e}")
    sys.exit(1)

# 🔥 ARCHITECTURE V2: Nouveaux imports
try:
    from core.analytics_database import AnalyticsDatabase
    from notifications import create_notification_manager
    from utils.logger import setup_logger
    from api.routes import (
        router as api_router, 
        set_analytics_db, 
        set_position_manager, 
        set_notification_manager, 
        set_instance_port, 
        set_app_state, 
        set_websocket_manager as set_websocket_manager_routes,
        set_live_order_manager
    )
    from utils.error_history import ErrorHistoryManager
    from api.live_trading_endpoints import router as live_router, register_websocket_commands
    from api.regime_endpoints import router as regime_router
    from api.routes.websocket_stats import router as websocket_stats_router, set_websocket_manager as set_websocket_manager_stats
    from api.routes.websocket import router as websocket_router
except ImportError as e:
    logging.warning(f"⚠️ Architecture V2 imports (optionnels): {e}")
    AnalyticsDatabase = None
    create_notification_manager = None
    setup_logger = None
    api_router = None
    set_position_manager = None
    set_notification_manager = None
    set_instance_port = None
    set_app_state = None
    set_websocket_manager_routes = None
    set_live_order_manager = None
    live_router = None
    regime_router = None
    websocket_stats_router = None
    set_websocket_manager_stats = None
    websocket_router = None
    register_websocket_commands = lambda x: None
    
    class ErrorHistoryManager:
        def __init__(self, max_errors=1000): self.errors = []
        def add_error(self, *args, **kwargs): pass
        def get_errors(self, *args, **kwargs): return []
        def clear_errors(self): pass

# 🔥 REFACTORING SPRINT 1.1: Exception Handling System
try:
    from core.error_handling import (
        handle_errors,
        log_errors,
        suppress_errors,
        ErrorContext,
    )
except ImportError as e:
    logging.warning(f"⚠️ Exception handling system (Sprint 1.1) non trouvé: {e}")
    handle_errors = lambda **kwargs: lambda f: f

# 🔥 FIX: Import colorama pour les couleurs dans les logs
try:
    import colorama
    colorama.init()
except ImportError:
    colorama = None

# 🔥 INSTANCES GLOBALES (Maintenues pour compatibilité descendante via StateManager)
live_order_manager = None
trade_db = None

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 🔥 Logging fichier pour capturer les crashs/backends en arrière-plan
try:
    from utils.logger import SafeRotatingFileHandler
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    root_logger = logging.getLogger()
    if not any(isinstance(h, SafeRotatingFileHandler) for h in root_logger.handlers):
        file_handler = SafeRotatingFileHandler(
            os.path.join(log_dir, "app.log"),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
            delay=True,
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(
            "[%(asctime)s] %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root_logger.addHandler(file_handler)
        logger.info("✅ File logging activé: %s", os.path.join(log_dir, "app.log"))
except Exception as e:
    logger.warning("⚠️ Impossible d'activer file logging: %s", e)

_faulthandler_file = None
try:
    import faulthandler
    crash_log_path = os.path.join(os.path.dirname(__file__), "logs", "faulthandler.log")
    _faulthandler_file = open(crash_log_path, "a", encoding="utf-8")
    faulthandler.enable(file=_faulthandler_file)
    logger.info("✅ Faulthandler activé: %s", crash_log_path)
except Exception as e:
    logger.debug("⚠️ Faulthandler non activé: %s", e)

# 🔥 Ajouter handler pour logger les erreurs vers PostgreSQL scan_errors
try:
    from core.error_logger import ErrorLoggerHandler
    error_db_handler = ErrorLoggerHandler(level=logging.ERROR)
    logging.getLogger().addHandler(error_db_handler)
    logger.info("✅ ErrorLoggerHandler ajouté - Les erreurs seront loggées vers scan_errors")
except Exception as e:
    logger.warning(f"⚠️ Impossible d'ajouter ErrorLoggerHandler: {e}")

logger.info(
    "🧭 Process info: pid=%s ppid=%s argv=%s",
    os.getpid(),
    os.getppid(),
    sys.argv,
)
reboot_reason = os.getenv("BACKEND_REBOOT_REASON")
if reboot_reason:
    logger.warning("♻️ Backend redémarré (reason=%s)", reboot_reason)


def _log_uncaught_exception(exc_type, exc, tb):
    logger.critical(
        "💥 Exception non gérée (pid=%s)",
        os.getpid(),
        exc_info=(exc_type, exc, tb),
    )
    try:
        state_snapshot = get_state_manager()
        logger.critical(
            "💥 Etat backend au crash: reboot_in_progress=%s session_id=%s",
            state_snapshot.backend_reboot_in_progress,
            state_snapshot.session_id,
        )
    except Exception:
        pass


sys.excepthook = _log_uncaught_exception

def _log_thread_exception(args):
    logger.critical(
        "💥 Exception non gérée dans thread %s (pid=%s)",
        getattr(args.thread, "name", "unknown"),
        os.getpid(),
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )

if hasattr(threading, "excepthook"):
    threading.excepthook = _log_thread_exception


def _log_process_exit():
    reboot_flag = None
    session_id = None
    try:
        state_snapshot = get_state_manager()
        reboot_flag = state_snapshot.backend_reboot_in_progress
        session_id = state_snapshot.session_id
    except Exception:
        pass
    logger.warning(
        "⚠️ Backend process exiting (pid=%s reboot_in_progress=%s session_id=%s)",
        os.getpid(),
        reboot_flag,
        session_id,
    )


atexit.register(_log_process_exit)

_asyncio_exception_handler_installed = False
_prev_asyncio_exception_handler = None


def _asyncio_exception_handler(loop, context):
    message = context.get("message")
    exception = context.get("exception")
    if exception:
        logger.error("❌ Asyncio exception: %s", message, exc_info=exception)
    else:
        logger.error("❌ Asyncio exception: %s context=%s", message, context)

    if _prev_asyncio_exception_handler and _prev_asyncio_exception_handler is not _asyncio_exception_handler:
        try:
            _prev_asyncio_exception_handler(loop, context)
        except Exception as handler_err:
            logger.debug("Asyncio exception handler chain failed: %s", handler_err)

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
ws_mgr = get_websocket_manager()
state.set_ws_manager(ws_mgr)
print(f"🔍 [DEBUG] WebSocketManager created: {ws_mgr is not None}, type={type(ws_mgr).__name__}")

# 🔥 Legacy App State Proxy for compatibility with routes
app_state = state.get_legacy_proxy()

# 🔥 INSTANCE GLOBALE: ErrorHistoryManager pour toute l'application
global_error_history = ErrorHistoryManager(max_errors=1000)
logger.info("✅ ErrorHistoryManager global initialisé")

# Fonctions de support (importées des modules dédiés)
from core.bootstrap import init_instances, run_initial_top_pairs_scan
from utils.logging_utils import add_log
from utils.history_utils import get_trade_history_file, save_trade_history, load_trade_history
from core.position.sl_services import setup_realtime_sl_check, schedule_sl_order_placement, cancel_pending_sl_task

# 🔥 FIX: Injecter app_state dans le router APRÈS définition
if api_router and set_app_state:
    set_app_state(app_state)
    logger.info("✅ app_state injecté dans API routes")

# 🔥 WEBSOCKET-FIX: Injecter le WebSocket manager dans les routes API
try:
    if set_websocket_manager_routes:
        ws_mgr = state.get_ws_manager()
        set_websocket_manager_routes(ws_mgr)
        logger.info("✅ WebSocket manager injecté dans API routes")
except Exception as e:
    logger.debug(f"Injection WebSocket manager routes non disponible: {e}")

# 🔥 LIVE TRADING: Enregistrer les commandes WebSocket pour live trading
try:
    ws_mgr = state.get_ws_manager()
    register_websocket_commands(ws_mgr)
    logger.info("✅ Commandes WebSocket live trading enregistrées")
except (ImportError, AttributeError, TypeError) as e:
    logger.debug(f"Commandes WebSocket live trading non disponibles: {e}")
except Exception as e:
    logger.critical(
        f"❌ ERREUR CRITIQUE lors de l'enregistrement WebSocket: {type(e).__name__}: {e}",
        exc_info=True
    )
    raise

# 🔥 WEBSOCKET-FIX: Injecter le WebSocket manager dans les routes stats
try:
    if set_websocket_manager_stats:
        ws_mgr = state.get_ws_manager()
        set_websocket_manager_stats(ws_mgr)
        logger.info("✅ WebSocket manager injecté dans websocket_stats")
except Exception as e:
    logger.debug(f"Injection WebSocket manager stats non disponible: {e}")

from contextlib import asynccontextmanager
from contextlib import suppress


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager pour initialiser et fermer proprement les ressources"""
    logger.info("🚀 LIFESPAN ENTER: Début du context manager (avant initialisation)")
    
    # 🔥 SPRINT 2.1: StateManager for centralized state management
    state = get_state_manager()
    global _asyncio_exception_handler_installed, _prev_asyncio_exception_handler
    try:
        loop = asyncio.get_running_loop()
        if not _asyncio_exception_handler_installed:
            _prev_asyncio_exception_handler = loop.get_exception_handler()
            loop.set_exception_handler(_asyncio_exception_handler)
            _asyncio_exception_handler_installed = True
            logger.info("✅ Asyncio exception handler installé")
    except Exception as e:
        logger.debug(f"⚠️ Installation exception handler asyncio échouée: {e}")

    status_task = None

    async def _status_broadcast_loop():
        last_log_ts = 0.0
        last_conn_count = 0
        while True:
            try:
                await asyncio.sleep(1.0)
                ws_mgr = state.get_ws_manager()
                if not ws_mgr:
                    continue

                conn_count = 0
                try:
                    conn_count = ws_mgr.get_connection_count()
                except Exception:
                    conn_count = 0

                if conn_count == 0:
                    last_conn_count = 0
                    continue

                now_ts = time.time()
                if last_conn_count == 0:
                    logger.info(f"📡 [STATUS-BROADCAST] Client(s) détecté(s) via WS: {conn_count} - démarrage push status")
                    last_log_ts = now_ts
                elif (now_ts - last_log_ts) >= 30.0:
                    logger.info(f"📡 [STATUS-BROADCAST] Push status actif (clients={conn_count})")
                    last_log_ts = now_ts

                last_conn_count = conn_count

                status_payload = None
                try:
                    status_payload = app_state.copy() if app_state else None
                except Exception:
                    status_payload = None
                if not isinstance(status_payload, dict):
                    try:
                        status_payload = state.get_legacy_proxy().copy()
                    except Exception:
                        status_payload = None
                if not isinstance(status_payload, dict):
                    continue
                status_payload.pop('logs', None)
                status_payload.pop('trade_history', None)
                await ws_mgr.send_status(status_payload)
            except asyncio.CancelledError:
                break
            except Exception:
                continue
    
    # 🔥 RESET SESSION: Notifier le frontend immédiatement pour nettoyer son état
    # Note: On essaiera d'émettre dès que ws_manager est prêt
    
    logger.info("🚀 LIFESPAN STARTUP: Initialisation...")

    # 🔥 SPRINT 1.3: Graceful shutdown manager
    shutdown_manager = GracefulShutdown(timeout=30.0) if GracefulShutdown else None
    if shutdown_manager:
        try:
            from core.shutdown import set_shutdown_manager
            set_shutdown_manager(shutdown_manager)
        except Exception:
            pass

        try:
            loop_for_signals = None
            try:
                loop_for_signals = asyncio.get_running_loop()
            except RuntimeError:
                loop_for_signals = None
            shutdown_manager.install_signal_handlers(loop_for_signals)
            logger.info("✅ GracefulShutdown handlers installés")
        except Exception as e:
            logger.warning("⚠️ Impossible d'installer les handlers de shutdown: %s", e)

        try:
            from utils.logger import drain_websocket_log_handlers
            shutdown_manager.register(
                "WebSocketLogHandler",
                lambda: drain_websocket_log_handlers(timeout=1.0),
                async_cleanup=True,
                priority=90
            )
        except Exception:
            pass
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

        # Initialiser les instances (Phase 1 critique)
        from core.bootstrap import init_instances, run_initial_top_pairs_scan
        await init_instances()
        
        # 🔥 FIX: Injection manuelle du session_id dans ws_manager pour garantir la cohérence
        ws_mgr = state.get_ws_manager()
        if ws_mgr:
            ws_mgr.session_id = state.session_id
            await ws_mgr.emit('reset_session', {
                'timestamp': time.time(),
                'reason': 'backend_startup',
                'session_id': state.session_id
            })
            logger.info(f"✅ Événement reset_session émis (session_id: {state.session_id})")

        status_task = asyncio.create_task(_status_broadcast_loop())

        # --- DÉMARRAGE DES SERVICES D'ARRIÈRE-PLAN ---
        # On lance tout ce qui n'est pas critique pour l'acceptation des premières requêtes HTTP
        
        # 1. Scan initial des top pairs
        asyncio.create_task(run_initial_top_pairs_scan())

        # 2. Tâche d'initialisation différée (ML, Calibration, Post-Exit)
        async def delayed_init():
            # Attendre un peu que le serveur soit bien UP
            await asyncio.sleep(2.0)
            
            # 🔬 Vérification système HistGradientBoosting
            try:
                from verification.verify_histgb_system import verify_config_overrides, verify_model_file
                config_result = verify_config_overrides(auto_fix=True)
                model_result = verify_model_file()
                if config_result.passed and model_result.passed:
                    logger.info("✅ HISTGB: Système ML vérifié et fonctionnel")
            except Exception as e:
                logger.warning(f"⚠️ Vérification ML différée échouée: {e}")

            # 🔥 AUTO-SEED CALIBRATION
            try:
                from config import TRADING_CONFIG
                if TRADING_CONFIG.get('ml_calibration_enabled', True):
                    from ml.calibration import get_calibration_manager
                    calib_manager = get_calibration_manager()
                    decay_days = TRADING_CONFIG.get('ml_calib_decay_days', 14)
                    seeded_count = calib_manager.seed_from_historical_trades(days=decay_days)
                    if seeded_count > 0:
                        logger.info(f"✅ CALIBRATION: Auto-seed avec {seeded_count} trades")
            except Exception as e:
                logger.warning(f"⚠️ Auto-seed calibration différé échoué: {e}")

            # 🔥 POST-EXIT ANALYSIS
            try:
                logger.info("🔄 Initialisation Post-Exit Analysis...")
                from core.callbacks.post_exit_loop import start_post_exit_loop, set_price_provider, is_running
                
                # Diagnostic PriceProvider
                price_provider = state.get_price_provider()
                logger.warning(f"📊 PostExit: PriceProvider disponible = {price_provider is not None}")
                
                if price_provider is None:
                    logger.error("❌ PostExit: PriceProvider manquant - tentative création forcée")
                    try:
                        from api.price_provider import get_price_provider
                        price_provider = get_price_provider()
                        if price_provider:
                            state.set_price_provider(price_provider)
                            logger.warning("✅ PostExit: PriceProvider créé et injecté en urgence")
                        else:
                            logger.error("❌ PostExit: Impossible de créer PriceProvider - Loop ne démarrera pas")
                    except Exception as force_e:
                        logger.error(f"❌ PostExit: Échec création forcée PriceProvider: {force_e}")
                
                # Injection PriceProvider dans PostExitLoop
                set_post_exit_price_provider = set_price_provider # Alias local
                set_post_exit_price_provider(state.get_price_provider())
                
                # Démarrage PostExitLoop
                await start_post_exit_loop()
                
                # Vérification démarrage
                loop_status = is_running()
                logger.warning(f"📊 PostExit: Loop démarrée = {loop_status}")
                
                if not loop_status:
                    logger.error("❌ PostExit: Loop n'a pas démarré - Prix ne seront pas collectés")
                
                from core.post_exit.manager import get_post_exit_manager
                post_exit_mgr = get_post_exit_manager()
                manager_status = post_exit_mgr.get_tracker_status()
                logger.info(f"📊 PostExit Manager: enabled={manager_status['enabled']}")
                
                restored_count = await post_exit_mgr.restore_active_trackers()
                if restored_count > 0:
                    logger.info(f"🔄 Post-Exit: {restored_count} trackers restaurés")
                    
                logger.info("✅ Post-Exit Analysis initialisé")
            except Exception as e:
                logger.error(f"❌ Post-Exit init différé échoué: {e}")
                import traceback
                logger.debug(traceback.format_exc())

        asyncio.create_task(delayed_init())

        yield

        logger.info("🟢 LIFESPAN YIELD: Execution principale terminée, début du shutdown")

    finally:
        logger.warning(
            "🟡 LIFESPAN shutdown start (pid=%s reboot_in_progress=%s)",
            os.getpid(),
            getattr(state, "backend_reboot_in_progress", None),
        )
        if status_task:
            status_task.cancel()
            with suppress(asyncio.CancelledError):
                await status_task

        # 🔥 RESET SESSION: Notifier le frontend de l'arrêt
        ws_mgr = state.get_ws_manager()
        if ws_mgr:
            try:
                await ws_mgr.emit('reset_session', {
                    'timestamp': time.time(),
                    'reason': 'backend_shutdown'
                })
                logger.info("✅ Événement reset_session émis avant le shutdown")
                await asyncio.sleep(0.2) # Laisser le temps à l'émission
            except: pass

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

            try:
                from core.shutdown import set_shutdown_manager
                set_shutdown_manager(None)
            except Exception:
                pass

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

                try:
                    from utils.logger import drain_websocket_log_handlers
                    await drain_websocket_log_handlers(timeout=1.0)
                except Exception:
                    pass

            except Exception as e:
                logger.warning(f"⚠️ Erreur shutdown legacy: {e}", exc_info=True)

        try:
            from core.shutdown import set_shutdown_manager
            set_shutdown_manager(None)
        except Exception:
            pass

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
except (ImportError, ConfigurationError) as e:
    logger.debug(f"Module regime trading non disponible ou erreur config: {e}")

# 🔥 WEBSOCKET-FIX: Inclure le router WebSocket principal (/ws endpoint)
logger.info(f"🔍 [DIAGNOSTIC] websocket_router = {websocket_router}")
logger.info(f"🔍 [DIAGNOSTIC] type(websocket_router) = {type(websocket_router)}")
try:
    if websocket_router:
        logger.info("🔍 [DIAGNOSTIC] Appel app.include_router(websocket_router)...")
        app.include_router(websocket_router)
        logger.info("✅ Router WebSocket principal inclus: /ws")
    else:
        logger.error("❌ websocket_router est None - import probablement échoué")
except Exception as e:
    logger.error(f"❌ Erreur inclusion router WebSocket: {e}", exc_info=True)

# 🔥 WEBSOCKET-FIX: Inclure les routes WebSocket stats pour surveillance
try:
    if websocket_stats_router:
        app.include_router(websocket_stats_router)
        logger.info("✅ WebSocket stats routes incluses: /api/websocket/*, /api/health")
except Exception as e:
    logger.debug(f"Module websocket stats non disponible: {e}")

# L'endpoint /api/health est maintenant fourni par websocket_stats_router

@app.get("/favicon.ico")
async def favicon():
    """Favicon (évite 404)"""
    from fastapi.responses import Response
    return Response(content=b'', media_type='image/x-icon')

# Main entry point

if __name__ == '__main__':
    import socket
    
    # Récupérer le port depuis les arguments (défaut: 5000)
    port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 5000
    
    logger.info("🚀 Trade Cursor v7.0 démarré")
    logger.info("📊 FastAPI (async natif) + WebSocket natif")
    
    # 🔥 FIX: Vérifier que le port est disponible avant de démarrer
    def is_port_available(port):
        """Vérifier si le port est disponible"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            result = sock.connect_ex(('127.0.0.1', port))
            return result != 0  # Port disponible si connexion échoue
        finally:
            sock.close()
    
    def kill_process_on_port(port):
        """Tenter de tuer le processus occupant le port spécifié (Windows uniquement)"""
        if os.name != 'nt':
            return False
        
        try:
            import subprocess
            # Trouver le PID utilisant le port
            cmd = f"netstat -ano | findstr :{port}"
            try:
                output = subprocess.check_output(cmd, shell=True).decode('utf-8', errors='ignore')
            except subprocess.CalledProcessError:
                return False # Port non trouvé ou erreur commande

            for line in output.strip().split('\n'):
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    pid = parts[-1]
                    if pid and pid.isdigit() and pid != "0":
                        logger.warning(f"⚠️ Port {port} occupé par PID {pid}. Tentative de fermeture...")
                        try:
                            subprocess.run(f"taskkill /F /PID {pid}", shell=True, check=True, capture_output=True)
                            return True
                        except subprocess.CalledProcessError as e:
                            logger.error(f"❌ Erreur taskkill PID {pid}: {e.stderr.decode('utf-8', errors='ignore')}")
        except Exception as e:
            logger.error(f"❌ Impossible de libérer le port {port}: {e}")
        return False

    # 🔥 FIX: Essayer le port demandé, puis chercher un port disponible
    original_port = port
    
    if not is_port_available(port):
        logger.warning(f"⚠️ Port {port} déjà utilisé.")
        if kill_process_on_port(port):
            logger.info(f"✅ Port {port} libéré avec succès.")
            time.sleep(1.0) # Laisser le temps à l'OS
    
    max_attempts = 10
    attempt = 0
    
    while not is_port_available(port) and attempt < max_attempts:
        logger.warning(f"⚠️ Port {port} toujours occupé, essai du port {port + 1}...")
        port += 1
        attempt += 1
    
    if not is_port_available(port):
        logger.error(f"❌ Impossible de trouver un port disponible après {max_attempts} tentatives (à partir du port {original_port})")
        sys.exit(1)
    
    if port != original_port:
        logger.info(f"✅ Port changé de {original_port} à {port}")
    
    try:
        # 🔥 MIGRATION COMPLÈTE: Lancer FastAPI avec WebSocket natif uniquement
        # L'initialisation se fera via le lifespan (init_instances)
        uvicorn.run(app, host='0.0.0.0', port=port, log_level="info", lifespan="on")
        logger.warning("⚠️ uvicorn.run terminé (pid=%s)", os.getpid())
    except OSError as e:
        logger.error(f"❌ Erreur binding port {port}: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Erreur démarrage serveur: {e}", exc_info=True)
        sys.exit(1)
