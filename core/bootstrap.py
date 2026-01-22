"""
Bootstrap Service - Initializing application components and services
"""

import os
import sys
import logging
import asyncio
from datetime import datetime
from typing import Any, Optional, List, Dict

# Core imports
from core.state_manager import get_state_manager
from core.websocket_manager import get_websocket_manager

# Note: Many imports are done inside functions to avoid circular dependencies

logger = logging.getLogger(__name__)

def init_instances() -> None:
    """
    Initialize all global instances required for the bot to function.
    """
    state = get_state_manager()
    
    # 1. Reset error history
    try:
        from utils.error_history import reset_error_history
        reset_error_history()
        logger.info("🗑️ Error history reset at startup")
    except Exception as e:
        logger.debug(f"Error resetting error history: {e}")
    
    # 2. Configure WebSocket log handler
    try:
        from utils.logger import WebSocketLogHandler
        root_logger = logging.getLogger()
        has_ws_handler = any(isinstance(h, WebSocketLogHandler) for h in root_logger.handlers)
        ws_mgr = state.get_ws_manager()
        if not has_ws_handler and ws_mgr:
            ws_handler = WebSocketLogHandler()
            ws_handler.set_ws_manager(ws_mgr)
            ws_handler.setLevel(logging.INFO)
            ws_handler.setFormatter(logging.Formatter('%(message)s'))
            root_logger.addHandler(ws_handler)
            logger.info("✅ WebSocket log handler configured")
    except Exception as e:
        logger.debug(f"Could not configure WebSocket log handler: {e}")
    
    # 3. Initialize Analytics DB
    if not state.get_analytics_db():
        from config import ANALYTICS_DB_PATH
        from core.analytics_database import AnalyticsDatabase
        
        os.makedirs(os.path.dirname(ANALYTICS_DB_PATH) if os.path.dirname(ANALYTICS_DB_PATH) else "data", exist_ok=True)
        
        try:
            port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 5000
            db = AnalyticsDatabase(db_path=ANALYTICS_DB_PATH, instance_port=port)
            state.set_analytics_db(db)
            logger.info(f"✅ Analytics DB ready: {ANALYTICS_DB_PATH}")
            
            # Reset stats at startup
            try:
                db.clear_all_trades()
                state.update_stats(total_trades=0, wins=0, losses=0)
                state.set_trade_history([])
                logger.info("✅ Stats reset at startup")
            except Exception as e:
                logger.warning(f"⚠️ Could not reset stats: {e}")
        except Exception as e:
            logger.error(f"❌ Error init Analytics DB: {e}")
            state.set_analytics_db(None)
            
    # 4. Initialize PostgreSQL DataLogger
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
                logger.info("✅ PostgreSQL DataLogger initialized")
                # Inject into scanner_loop callback if needed
                # (This is usually done via module-level setters)
    except Exception as e:
        logger.warning(f"⚠️ Error initializing PostgreSQL DataLogger: {e}")
        
    # 5. Initialize Notification Manager
    if not state.get_notification_manager():
        from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED
        from config import NOTIFICATION_BATCHING_ENABLED
        from notifications import create_notification_manager
        
        async def websocket_callback(event_type, data):
            ws_mgr = state.get_ws_manager()
            if ws_mgr:
                await ws_mgr.emit(event_type, data)
        
        port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 5000
        
        notif_mgr = create_notification_manager(
            telegram_bot_token=TELEGRAM_BOT_TOKEN,
            telegram_chat_id=TELEGRAM_CHAT_ID,
            socketio_callback=websocket_callback,
            enable_batching=NOTIFICATION_BATCHING_ENABLED,
            instance_port=port
        )
        state.set_notification_manager(notif_mgr)
        logger.info(f"📱 Notification Manager initialized (Telegram: {'ENABLED' if TELEGRAM_ENABLED else 'DISABLED'})")

    # 6. Inject into API routes
    try:
        from api.routes import (
            set_analytics_db, set_notification_manager, set_instance_port,
            set_app_state, set_websocket_manager, set_position_manager,
            set_price_provider, set_scheduler
        )
        
        port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 5000
        set_instance_port(port)
        
        if state.get_analytics_db():
            set_analytics_db(state.get_analytics_db())
        if state.get_notification_manager():
            set_notification_manager(state.get_notification_manager())
        if state.get_ws_manager():
            set_websocket_manager(state.get_ws_manager())
            
        set_app_state(state.get_legacy_proxy())
        
        if state.get_position_manager():
            set_position_manager(state.get_position_manager())
        if state.get_price_provider():
            set_price_provider(state.get_price_provider())
        if state.get_scheduler():
            set_scheduler(state.get_scheduler())
            
        logger.info("✅ Dependencies injected into API routes")
    except Exception as e:
        logger.warning(f"⚠️ Error injecting dependencies into API routes: {e}")

    # 7. Initialize Scheduler and configure callbacks
    if not state.get_scheduler():
        from core.scheduler import Scheduler
        from core.callbacks import (
            scanner_loop_callback,
            position_check_loop_callback,
            scalability_refresh_loop_callback
        )
        
        sched = Scheduler()
        # Set callbacks from core.callbacks package
        sched.set_scanner_callback(scanner_loop_callback)
        sched.set_position_check_callback(position_check_loop_callback)
        sched.set_scalability_refresh_callback(scalability_refresh_loop_callback)
        state.set_scheduler(sched)
        
        ws_mgr = state.get_ws_manager()
        # Inject ws_manager into callback modules if they have setters
        try:
            from core.callbacks.scanner_loop import set_websocket_manager as set_ws_scanner
            if ws_mgr: set_ws_scanner(ws_mgr)
        except (ImportError, AttributeError): pass
        
        try:
            from core.callbacks.position_check_loop import set_websocket_manager as set_ws_pos
            if ws_mgr: set_ws_pos(ws_mgr)
        except (ImportError, AttributeError): pass

        try:
            from core.callbacks.scalability_refresh import set_websocket_manager as set_ws_scal
            if ws_mgr: set_ws_scal(ws_mgr)
        except (ImportError, AttributeError): pass
            
        logger.info("✅ Scheduler initialized with callbacks")

async def run_initial_top_pairs_scan() -> None:
    """
    Launch initial top pairs scan in background.
    """
    from utils.logging_utils import add_log
    from core.exceptions import MarketDataError, NetworkError, WebSocketError
    
    init_instances()
    state = get_state_manager()
    
    if state.top_pairs:
        return
        
    try:
        await add_log('INFO', 'Scanner started', 'Initial top pairs scan in background...')
        scanner_inst = state.get_scanner()
        if not scanner_inst:
            logger.warning("⚠️ Scanner not available")
            return
            
        if scanner_inst.is_scanning:
            return
            
        top_pairs = await scanner_inst.scan_top_pairs(20)
        if not top_pairs:
            logger.warning("⚠️ Initial scan finished with no results")
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
                    await add_log('INFO', 'WebSocket started', f'{len(symbols)} symbols monitored')
                except Exception as e:
                    logger.warning(f"⚠️ Error starting WebSocket: {e}")
    except Exception as e:
        logger.error(f"❌ Error during initial top pairs scan: {e}")
                    
async def perform_backend_reboot(reason: str = 'manual'):
    """
    Arrêter proprement les services puis relancer le processus backend.
    """
    from utils.logging_utils import add_log
    from utils.history_utils import save_trade_history
    import time
    import subprocess
    
    state = get_state_manager()
    
    # Marquer le reboot comme étant en cours dans l'état global
    state.set_backend_reboot(True)

    try:
        await add_log('INFO', 'Backend reboot', 'Arrêt des services en cours...')
        ws_mgr = state.get_ws_manager()
        if ws_mgr:
            await ws_mgr.emit('backend_reboot', {
                'status': 'shutting_down',
                'reason': reason,
                'timestamp': time.time()
            })

        # Arrêter le scheduler
        sched = state.get_scheduler()
        if sched:
            try:
                await sched.stop_async()
                await add_log('INFO', 'Backend reboot', 'Scheduler arrêté')
            except Exception as e:
                logger.warning(f"⚠️ Erreur arrêt scheduler (reboot): {e}")

        # Arrêter le price provider websocket
        price_prov = state.get_price_provider()
        if price_prov and hasattr(price_prov, 'stop_websocket'):
            try:
                await price_prov.stop_websocket()
                await add_log('INFO', 'Backend reboot', 'WebSocket prix arrêté')
            except Exception as e:
                logger.warning(f"⚠️ Erreur arrêt price provider (reboot): {e}")

        # Fermer le data logger PostgreSQL
        try:
            from core.callbacks.scanner_loop import get_pg_datalogger
            pg_datalogger = get_pg_datalogger()
            if pg_datalogger:
                pg_datalogger.close()
                await add_log('INFO', 'Backend reboot', 'PG DataLogger fermé')
        except Exception as e:
            logger.warning(f"⚠️ Erreur fermeture PG DataLogger (reboot): {e}")

        # Sauvegarder l'historique avant la sortie
        try:
            save_trade_history()
        except Exception as e:
            logger.warning(f"⚠️ Erreur sauvegarde historique avant reboot: {e}")

        await asyncio.sleep(0.5)

        if ws_mgr:
            await ws_mgr.emit('backend_reboot', {
                'status': 'restarting',
                'reason': reason,
                'timestamp': time.time()
            })

        await add_log('INFO', 'Backend reboot', 'Relance du processus backend...')

        # Effectuer le redémarrage système
        python_cmd = sys.executable or 'python'
        script_path = os.path.abspath(sys.argv[0])
        args = sys.argv[1:]
        env = os.environ.copy()
        env['BACKEND_REBOOT_REASON'] = reason

        # Lancer le nouveau processus
        subprocess.Popen([python_cmd, script_path, *args], env=env, close_fds=os.name != 'nt')

        await asyncio.sleep(0.5)
        logger.info('♻️ Nouveau processus backend lancé, arrêt de l\'instance actuelle...')
        os._exit(0)

    except Exception as e:
        state.set_backend_reboot(False)
        logger.error(f"❌ Échec reboot backend: {e}", exc_info=True)
        await add_log('ERROR', 'Backend reboot échoué', str(e))
        ws_mgr = state.get_ws_manager()
        if ws_mgr:
            await ws_mgr.emit('backend_reboot', {
                'status': 'error',
                'reason': reason,
                'error': str(e),
                'timestamp': time.time()
            })
