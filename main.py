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
    from core.bootstrap import init_instances, run_initial_top_pairs_scan
    from utils.logging_utils import add_log
    from utils.history_utils import get_trade_history_file, save_trade_history, load_trade_history
    from core.position.sl_services import setup_realtime_sl_check, schedule_sl_order_placement, cancel_pending_sl_task
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

# 🔥 LIVE TRADING: Enregistrer les commandes WebSocket pour live trading
try:
    ws_mgr = state.get_ws_manager()
    register_websocket_commands(ws_mgr)
    logger.info("✅ Commandes WebSocket live trading enregistrées")
except (ImportError, AttributeError, TypeError) as e:
    # Dépendances manquantes ou configuration incorrecte (non-critique)
    logger.warning(f"⚠️ Impossible d'enregistrer commandes WebSocket live trading: {e}")
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

        # Charger l'historique des trades
        from utils.history_utils import load_trade_history
        load_trade_history()
        
        # Initialiser les instances
        from core.bootstrap import init_instances
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
except (ImportError, ConfigurationError) as e:
    logger.debug(f"Module regime trading non disponible ou erreur config: {e}")

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
    
    # 🔥 FIX CRITIQUE: Forcer l'initialisation via bootstrap
    print("🚀 INIT: Initialisation via core.bootstrap...")
    try:
        from core.bootstrap import init_instances
        init_instances()
        print("✅ INIT: bootstrap terminé avec succès")
    except Exception as e:
        print(f"❌ INIT: Erreur initialisation: {e}")
        logger.error(f"❌ INIT: Erreur initialisation: {e}", exc_info=True)
    
    try:
        # 🔥 MIGRATION COMPLÈTE: Lancer FastAPI avec WebSocket natif uniquement
        uvicorn.run(app, host='0.0.0.0', port=port, log_level="info", lifespan="on")
    except OSError as e:
        logger.error(f"❌ Erreur binding port {port}: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Erreur démarrage serveur: {e}", exc_info=True)
        sys.exit(1)
