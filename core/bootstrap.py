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

async def init_instances() -> None:
    """
    Initialize all global instances required for the bot to function.
    Separates critical startup from background services to speed up server availability.
    """
    import time
    start_total = time.time()
    state = get_state_manager()
    
    logger.info("🚀 Début de init_instances (async)...")
    
    # --- PHASE 1: CRITICAL STARTUP (Fast) ---
    # Minimal components needed for API routes to not crash
    
    # 1. Reset error history
    start = time.time()
    try:
        from utils.error_history import reset_error_history
        reset_error_history()
        logger.info(f"🗑️ Error history reset at startup ({time.time()-start:.3f}s)")
    except Exception as e:
        logger.debug(f"Error resetting error history: {e}")
    
    # 2. Configure WebSocket log handler
    start = time.time()
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
            logger.info(f"✅ WebSocket log handler configured ({time.time()-start:.3f}s)")
    except Exception as e:
        logger.debug(f"Could not configure WebSocket log handler: {e}")

    # 2b. Initialize TradeDatabase (Legacy SQLite)
    start = time.time()
    if not state.get_trade_db():
        try:
            from core.database import TradeDatabase
            db = TradeDatabase()
            state.set_trade_db(db)
            
            # 🔥 SYNC: Update main module global instance
            try:
                import main
                main.trade_db = db
            except (ImportError, AttributeError):
                pass
                
            # Reset history at startup if needed
            try:
                db.clear_all_trades()
                logger.info(f"✅ Legacy TradeDatabase reset at startup ({time.time()-start:.3f}s)")
            except Exception as e:
                logger.warning(f"⚠️ Could not reset legacy trades: {e}")
                
            logger.info("✅ TradeDatabase (SQLite legacy) ready")
        except Exception as e:
            logger.error(f"❌ Error init TradeDatabase: {e}")

    # 3. Initialize Analytics DB
    start = time.time()
    if not state.get_analytics_db():
        from config import ANALYTICS_DB_PATH
        from core.analytics_database import AnalyticsDatabase
        
        os.makedirs(os.path.dirname(ANALYTICS_DB_PATH) if os.path.dirname(ANALYTICS_DB_PATH) else "data", exist_ok=True)
        
        try:
            port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 5000
            db = AnalyticsDatabase(db_path=ANALYTICS_DB_PATH, instance_port=port)
            state.set_analytics_db(db)
            logger.info(f"✅ Analytics DB ready: {ANALYTICS_DB_PATH} ({time.time()-start:.3f}s)")
            
            # Reset stats at startup
            try:
                db.clear_all_trades()
                state.update_stats(total_trades=0, wins=0, losses=0)
                state.set_trade_history([])
                state.clear_logs()  # 🔥 Clear logs buffer at startup
                logger.info("✅ Stats and logs reset at startup")
            except Exception as e:
                logger.warning(f"⚠️ Could not reset stats: {e}")
        except Exception as e:
            logger.error(f"❌ Error init Analytics DB: {e}")
            state.set_analytics_db(None)

    # 5. Initialize Notification Manager
    start = time.time()
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
        logger.info(f"📱 Notification Manager initialized ({time.time()-start:.3f}s)")

    # 5b. Initialize Core Trading Components (Scanner, Analyzer, PositionManager, PriceProvider)
    start = time.time()
    try:
        from core.scanner import ScalabilityScanner
        from core.analyzer import TechnicalAnalyzer
        from core.position_manager import PositionManager, PositionConfig
        from api.price_provider import get_price_provider
        
        if not state.get_price_provider():
            price_provider = get_price_provider()
            state.set_price_provider(price_provider)
            logger.info("✅ PriceProvider initialized")

        if not state.get_analyzer():
            analyzer = TechnicalAnalyzer()
            state.set_analyzer(analyzer)
            logger.info("✅ TechnicalAnalyzer initialized")

        if not state.get_scanner():
            scanner = ScalabilityScanner()
            state.set_scanner(scanner)
            logger.info("✅ ScalabilityScanner initialized")

        if not state.get_position_manager():
            config = PositionConfig()
            pos_mgr = PositionManager(
                config=config,
                analytics_db=state.get_analytics_db(),
                live_order_manager=state.get_live_order_manager()
            )
            state.set_position_manager(pos_mgr)
            logger.info(f"✅ PositionManager initialized ({time.time()-start:.3f}s)")
            
    except Exception as e:
        logger.error(f"❌ Error initializing core trading components: {e}", exc_info=True)

    # 6. Inject into API routes
    start = time.time()
    try:
        from api.routes import (
            set_analytics_db, set_notification_manager, set_instance_port,
            set_app_state, set_websocket_manager, set_position_manager,
            set_price_provider, set_scheduler, set_live_order_manager
        )
        
        port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 5000
        set_instance_port(port)
        
        if state.get_analytics_db(): set_analytics_db(state.get_analytics_db())
        if state.get_notification_manager(): set_notification_manager(state.get_notification_manager())
        set_app_state(state.get_legacy_proxy())
        if state.get_ws_manager(): set_websocket_manager(state.get_ws_manager())
        if state.get_position_manager(): set_position_manager(state.get_position_manager())
        if state.get_price_provider(): set_price_provider(state.get_price_provider())
        if state.get_live_order_manager(): set_live_order_manager(state.get_live_order_manager())
        
        logger.info(f"✅ Dependencies injected into API routes ({time.time()-start:.3f}s)")
    except (ImportError, AttributeError, NameError) as e:
        logger.warning(f"⚠️ Error injecting dependencies into API routes: {e}")

    # 7. Initialize Scheduler and configure callbacks
    start = time.time()
    if not state.get_scheduler():
        from core.scheduler import Scheduler
        from core.callbacks import (
            scanner_loop_callback,
            position_check_loop_callback,
            scalability_refresh_loop_callback
        )
        
        sched = Scheduler()
        sched.set_scanner_callback(scanner_loop_callback)
        sched.set_position_check_callback(position_check_loop_callback)
        sched.set_scalability_refresh_callback(scalability_refresh_loop_callback)
        state.set_scheduler(sched)
        
        ws_mgr = state.get_ws_manager()
        try:
            from core.callbacks.scanner_loop import (
                set_websocket_manager as set_ws_scanner,
                set_scanner as set_inst_scanner,
                set_analyzer as set_inst_analyzer,
                set_position_manager as set_inst_pos,
                set_price_provider as set_inst_price,
                set_app_state as set_inst_state,
                set_notification_manager as set_inst_notif,
                set_pg_datalogger as set_inst_pg,
                set_scanner_lock as set_lock_scanner_inst
            )
            from core.callbacks.position_check_loop import (
                set_websocket_manager as set_ws_pos,
                set_position_manager as set_inst_pos_check,
                set_price_provider as set_inst_price_check,
                set_app_state as set_inst_state_check,
                set_notification_manager as set_inst_notif_check,
                set_analytics_db as set_inst_analytics_check,
                set_position_lock as set_lock_pos_inst
            )
            from core.callbacks.scalability_refresh import (
                set_websocket_manager as set_ws_scal,
                set_scanner as set_inst_scanner_scal,
                set_position_manager as set_inst_pos_scal,
                set_price_provider as set_inst_price_scal,
                set_app_state as set_inst_state_scal
            )

            if ws_mgr:
                set_ws_scanner(ws_mgr)
                set_ws_pos(ws_mgr)
                set_ws_scal(ws_mgr)

            if state.get_scanner(): set_inst_scanner(state.get_scanner())
            if state.get_analyzer(): set_inst_analyzer(state.get_analyzer())
            if state.get_position_manager(): set_inst_pos(state.get_position_manager())
            if state.get_price_provider(): set_inst_price(state.get_price_provider())
            set_inst_state(state.get_legacy_proxy())
            if state.get_notification_manager(): set_inst_notif(state.get_notification_manager())
            set_lock_scanner_inst(state.lock("scanner"))
            
            if state.get_position_manager(): set_inst_pos_check(state.get_position_manager())
            if state.get_price_provider(): set_inst_price_check(state.get_price_provider())
            set_inst_state_check(state.get_legacy_proxy())
            if state.get_notification_manager(): set_inst_notif_check(state.get_notification_manager())
            if state.get_analytics_db(): set_inst_analytics_check(state.get_analytics_db())
            set_lock_pos_inst(state.lock("position"))

            if state.get_scanner(): set_inst_scanner_scal(state.get_scanner())
            if state.get_position_manager(): set_inst_pos_scal(state.get_position_manager())
            if state.get_price_provider(): set_inst_price_scal(state.get_price_provider())
            set_inst_state_scal(state.get_legacy_proxy())

        except (ImportError, AttributeError) as e:
            logger.warning(f"⚠️ Error injecting dependencies into loops: {e}")
        
        sched.start()
        state.set_is_scanning(True)
        logger.info(f"✅ Scheduler started automatically ({time.time()-start:.3f}s)")
            
    logger.info(f"🏁 init_instances (critical) terminé en {time.time()-start_total:.3f}s")
    
    # Lancer l'initialisation des services lourds en arrière-plan
    asyncio.create_task(init_background_services())


async def init_background_services() -> None:
    """
    Initialize non-critical heavy services in background.
    Allows the API to start responding while these services connect.
    """
    import time
    start_bg = time.time()
    state = get_state_manager()
    logger.info("⏳ Démarrage des services d'arrière-plan (PostgreSQL, Live Trading)...")

    # 4. Initialize PostgreSQL DataLogger
    start = time.time()
    if not state.get_pg_datalogger():
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
                    state.set_pg_datalogger(pg_datalogger)
                    # Inject into scanner loop
                    try:
                        from core.callbacks.scanner_loop import set_pg_datalogger
                        set_pg_datalogger(pg_datalogger)
                    except ImportError: pass
                    logger.info(f"✅ PostgreSQL DataLogger initialized background ({time.time()-start:.3f}s)")
        except Exception as e:
            logger.warning(f"⚠️ Error initializing PostgreSQL DataLogger: {e}")

    # 🔥 SYNC: Initialiser live_order_manager si nécessaire
    start_lom = time.time()
    if not state.get_live_order_manager():
        from api.live_trading_endpoints import load_live_config
        live_config = load_live_config()
        if live_config.get('trading_mode') == 'LIVE' and (live_config.get('api_key_mexc') or live_config.get('browser_token_mexc')):
            try:
                from trading.live_order_manager_futures import LiveOrderManagerFutures
                lom = LiveOrderManagerFutures(
                    api_key=live_config.get('api_key_mexc'),
                    api_secret=live_config.get('api_secret_mexc'),
                    browser_token=live_config.get('browser_token_mexc'),
                    dry_run=live_config.get('dry_run', True),
                    use_bypass=True # Forcer bypass si disponible
                )
                state.set_live_order_manager(lom)
                
                # 🔥 SYNC: Update main module global instance
                try:
                    import main
                    main.live_order_manager = lom
                except (ImportError, AttributeError):
                    pass
                
                # Update position manager
                pos_mgr = state.get_position_manager()
                if pos_mgr:
                    pos_mgr.live_order_manager = lom
                    
                # Update API routes
                try:
                    from api.routes import set_live_order_manager
                    set_live_order_manager(lom)
                except ImportError: pass
                        
                logger.info(f"✅ LiveOrderManager initialized background ({time.time()-start_lom:.3f}s)")
            except Exception as lom_err:
                logger.warning(f"⚠️ Could not init LiveOrderManager: {lom_err}")

    logger.info(f"🏁 Services d'arrière-plan initialisés en {time.time()-start_bg:.3f}s")


async def run_initial_top_pairs_scan() -> None:
    """
    Launch initial top pairs scan in background.
    """
    from utils.logging_utils import add_log
    from core.exceptions import MarketDataError, NetworkError, WebSocketError
    
    # 🔥 REMOVED redundant init_instances() - already done in lifespan
    state = get_state_manager()
    
    # 🔥 Use scanner lock to avoid concurrent scans
    scanner_lock = state.lock("scanner")
    
    logger.info("📡 [DEBUG-SCAN] run_initial_top_pairs_scan: Tentative d'acquisition du lock...")
    async with scanner_lock:
        logger.info("📡 [DEBUG-SCAN] run_initial_top_pairs_scan: Lock acquis")
        if state.top_pairs:
            logger.info("📡 [DEBUG-SCAN] top_pairs déjà présent, skip scan initial")
            return
            
        try:
            await add_log('INFO', 'Scanner started', 'Initial top pairs scan in background...')
            scanner_inst = state.get_scanner()
            if not scanner_inst:
                logger.error("⚠️ [DEBUG-SCAN] Scanner non disponible dans le StateManager")
                return
                
            if scanner_inst.is_scanning:
                logger.warning("⚠️ [DEBUG-SCAN] Scanner est déjà en train de scanner")
                return
                
            logger.info("📡 [DEBUG-SCAN] Appel scanner_inst.scan_top_pairs(20)...")
            top_pairs = await scanner_inst.scan_top_pairs(20)
            if not top_pairs:
                logger.warning("⚠️ [DEBUG-SCAN] Scan initial terminé sans résultats")
                return
                
            logger.info(f"📡 [DEBUG-SCAN] {len(top_pairs)} paires trouvées lors du scan initial")
            state.set_top_pairs(top_pairs)
            
            # 🔥 SPRINT 1: Mettre à jour le Market Regime initial
            try:
                from core.market_regime_selector import get_regime_selector
                regime_selector = get_regime_selector()
                
                atr_values = [p.get('atr_percent') for p in top_pairs if p.get('atr_percent') is not None]
                atr_5m_values = [p.get('atr_percent_5m') for p in top_pairs if p.get('atr_percent_5m') is not None]
                adx_values = [p.get('adx') for p in top_pairs if p.get('adx') is not None]
                
                if atr_values:
                    logger.info(f"🌡️ [DEBUG-SCAN] Initialisation du régime avec {len(atr_values)} samples ATR...")
                    await regime_selector.check_regime(
                        atr_values=atr_values,
                        atr_5m_values=atr_5m_values,
                        adx_values=adx_values,
                        force=True,
                        trigger="auto"
                    )
            except Exception as e:
                logger.warning(f"⚠️ [DEBUG-SCAN] Erreur initialisation régime: {e}")

            ws_mgr = state.get_ws_manager()
            if ws_mgr:
                await ws_mgr.emit('top_pairs_update', {'pairs': top_pairs})
                
            price_prov = state.get_price_provider()
            if price_prov:
                # 🔥 FIX: Extraire les symboles et s'assurer qu'ils sont au format MEXC si nécessaire
                symbols = [p.get('symbol', '') for p in top_pairs[:30] if p.get('symbol')]
                if symbols:
                    try:
                        logger.info(f"📡 [DEBUG-SCAN] Démarrage WebSocket prix pour {len(symbols)} symboles...")
                        # start_websocket gère déjà la conversion de format
                        # 🔥 FIX: Ajouter un timeout pour éviter de bloquer tout le scanner si MEXC est lent
                        await asyncio.wait_for(price_prov.start_websocket(symbols), timeout=15.0)
                        await add_log('INFO', 'WebSocket started', f'{len(symbols)} symbols monitored')
                    except asyncio.TimeoutError:
                        logger.error("❌ [DEBUG-SCAN] Timeout lors du démarrage du WebSocket prix (15s)")
                        await add_log('WARNING', 'Price WebSocket Timeout', 'Using REST fallback')
                    except Exception as e:
                        logger.error(f"❌ [DEBUG-SCAN] Erreur démarrage WebSocket prix: {e}", exc_info=True)
            
            # 🔥 OPT #14: Immediate setup scan after initial top pairs scan
            try:
                from core.callbacks.scanner_loop import scan_pair_for_setup
                from config import TRADING_CONFIG
                
                limit = TRADING_CONFIG.get('top_pairs_limit', 20)
                pairs_to_scan = top_pairs[:limit]
                
                if pairs_to_scan:
                    logger.info(f"🔍 [DEBUG-SCAN] Lancement du premier scan de setups ({len(pairs_to_scan)} paires)...")
                    scan_tasks = [scan_pair_for_setup(p.get('symbol', '')) for p in pairs_to_scan if p.get('symbol')]
                    if scan_tasks:
                        results = await asyncio.gather(*scan_tasks, return_exceptions=True)
                        valid_count = sum(1 for r in results if r and isinstance(r, dict) and 'direction' in r)
                        logger.info(f"✅ [DEBUG-SCAN] Premier scan de setups terminé: {valid_count} setups valides trouvés")
            except Exception as setup_err:
                logger.error(f"❌ [DEBUG-SCAN] Erreur lors du premier scan de setups: {setup_err}", exc_info=True)

        except Exception as e:
            logger.error(f"❌ [DEBUG-SCAN] Erreur critique lors du scan initial: {e}", exc_info=True)
            await add_log('ERROR', 'Initial scan failed', str(e))
                    
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
