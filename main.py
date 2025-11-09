#!/usr/bin/env python3
"""
Trade Cursor v7.0 - Application FastAPI (async natif) - VERSION REFACTORIS├ëE
Interface HTML identique ├á v5.1 avec backend Python

­ƒöÑ REFACTORISATION: Callbacks et routes API d├®plac├®s dans des modules s├®par├®s
- api/routes/scanner.py - Routes scanner (/api/scanner/*)
- api/routes/dashboard.py - Routes dashboard (/api/status, /api/state, etc.)
- core/callbacks/scanner_loop.py - scanner_loop_callback(), scan_pair_for_setup()
- core/callbacks/position_check_loop.py - position_check_loop_callback()
- core/callbacks/scalability_refresh.py - scalability_refresh_loop_callback()
"""

import sys
import asyncio
import logging
import json
import os
import csv
import io
from datetime import datetime
from typing import Optional, List, Dict
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import socketio

# ­ƒöÑ v7.0: Imports complets
try:
    from api.price_provider import get_price_provider
    from core.scanner import ScalabilityScanner
    from core.analyzer import TechnicalAnalyzer
    from core.position_manager import PositionManager, PositionConfig
    from core.scheduler import Scheduler
    from core.metrics import get_metrics_collector
    from core.database import TradeDatabase  # ­ƒöÑ PHASE 8: SQLite (legacy)
except ImportError as e:
    logging.error(f"Import error: {e}")
    # Fallback pour les d├®pendances manquantes
    get_price_provider = None
    TradeDatabase = None
    ScalabilityScanner = None
    TechnicalAnalyzer = None
    PositionManager = None
    PositionConfig = None
    Scheduler = None
    get_metrics_collector = None

# ­ƒöÑ ARCHITECTURE V2: Nouveaux imports
try:
    from core.analytics_database import AnalyticsDatabase
    from notifications import create_notification_manager
    from api.routes import router as api_router, set_analytics_db, set_position_manager, set_notification_manager, set_instance_port
except ImportError as e:
    logging.warning(f"Architecture V2 imports (optionnels): {e}")
    AnalyticsDatabase = None
    create_notification_manager = None
    api_router = None
    set_analytics_db = None

# ­ƒöÑ REFACTORISATION: Imports des modules refactoris├®s
try:
    from api.routes.scanner import router as scanner_router
    from api.routes.scanner import (
        set_scanner as set_scanner_router,
        set_analyzer as set_analyzer_router,
        set_price_provider as set_price_provider_router,
        set_app_state as set_app_state_scanner,
        set_socketio as set_socketio_scanner
    )
except ImportError as e:
    logging.warning(f"Scanner router import: {e}")
    scanner_router = None

try:
    from api.routes.dashboard import router as dashboard_router
    from api.routes.dashboard import (
        set_scheduler as set_scheduler_dashboard,
        set_position_manager as set_position_manager_dashboard,
        set_app_state as set_app_state_dashboard,
        set_socketio as set_socketio_dashboard
    )
except ImportError as e:
    logging.warning(f"Dashboard router import: {e}")
    dashboard_router = None

try:
    from core.callbacks.scanner_loop import (
        scanner_loop_callback,
        scan_pair_for_setup,
        set_scanner as set_scanner_callback,
        set_analyzer as set_analyzer_callback,
        set_position_manager as set_position_manager_scanner,
        set_price_provider as set_price_provider_scanner,
        set_app_state as set_app_state_scanner_callback,
        set_socketio as set_socketio_scanner_callback,
        set_scanner_lock
    )
except ImportError as e:
    logging.warning(f"Scanner callback import: {e}")
    scanner_loop_callback = None
    scan_pair_for_setup = None

try:
    from core.callbacks.position_check_loop import (
        position_check_loop_callback,
        set_position_manager as set_position_manager_position_check,
        set_price_provider as set_price_provider_position_check,
        set_app_state as set_app_state_position_check,
        set_socketio as set_socketio_position_check,
        set_position_lock as set_position_lock_callback,
        set_analytics_db as set_analytics_db_position_check
    )
except ImportError as e:
    logging.warning(f"Position check callback import: {e}")
    position_check_loop_callback = None

try:
    from core.callbacks.scalability_refresh import (
        scalability_refresh_loop_callback,
        set_scanner as set_scanner_scalability,
        set_position_manager as set_position_manager_scalability,
        set_price_provider as set_price_provider_scalability,
        set_app_state as set_app_state_scalability,
        set_socketio as set_socketio_scalability
    )
except ImportError as e:
    logging.warning(f"Scalability refresh callback import: {e}")
    scalability_refresh_loop_callback = None

# Configuration logging avec couleurs
try:
    import colorama
    from colorama import Fore, Style, init
    init(autoreset=True)  # Auto-reset apr├¿s chaque print
    
    # Formatter personnalis├® avec couleurs
    class ColoredFormatter(logging.Formatter):
        COLORS = {
            'DEBUG': Fore.CYAN,
            'INFO': Fore.GREEN,
            'WARNING': Fore.YELLOW,
            'ERROR': Fore.RED,
            'CRITICAL': Fore.RED + Style.BRIGHT
        }
        
        def format(self, record):
            log_color = self.COLORS.get(record.levelname, '')
            original_msg = record.getMessage()
            
            # Colorier les emojis et messages sp├®ciaux
            colored_msg = original_msg
            colored_msg = colored_msg.replace('Ô£à', f'{Fore.GREEN}Ô£à{Style.RESET_ALL}')
            colored_msg = colored_msg.replace('ÔØî', f'{Fore.RED}ÔØî{Style.RESET_ALL}')
            colored_msg = colored_msg.replace('ÔÜá´©Å', f'{Fore.YELLOW}ÔÜá´©Å{Style.RESET_ALL}')
            colored_msg = colored_msg.replace('­ƒöÑ', f'{Fore.MAGENTA}­ƒöÑ{Style.RESET_ALL}')
            colored_msg = colored_msg.replace('­ƒôè', f'{Fore.CYAN}­ƒôè{Style.RESET_ALL}')
            colored_msg = colored_msg.replace('­ƒôØ', f'{Fore.BLUE}­ƒôØ{Style.RESET_ALL}')
            colored_msg = colored_msg.replace('­ƒÜÇ', f'{Fore.CYAN}­ƒÜÇ{Style.RESET_ALL}')
            
            # Appliquer couleur au levelname
            colored_level = f"{log_color}{record.levelname}{Style.RESET_ALL}"
            
            # Cr├®er un nouveau record avec le message color├®
            record.msg = colored_msg
            record.levelname = colored_level
            return super().format(record)
    
    handler = logging.StreamHandler()
    handler.setFormatter(ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    USE_COLORS = True
except ImportError:
    # Fallback sans couleurs si colorama pas install├®
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    USE_COLORS = False

logger = logging.getLogger(__name__)

# Initialisation FastAPI
app = FastAPI(title="Trade Cursor v7.0")

# ­ƒöÑ FIX: Ajouter headers CORS pour Safari et autres navigateurs
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production, sp├®cifier les origines autoris├®es
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
templates = Jinja2Templates(directory="templates")

# ­ƒöÑ Handler personnalis├® pour ├®mettre tous les logs via WebSocket
class SocketIOHandler(logging.Handler):
    """Handler qui ├®met tous les logs vers le frontend via SocketIO"""
    def __init__(self):
        super().__init__()
        self.sio = None

    def set_sio(self, sio_instance):
        """Configurer l'instance SocketIO"""
        self.sio = sio_instance

    def emit(self, record):
        """├ëmettre le log via SocketIO"""
        if self.sio is None:
            return

        try:
            # Cr├®er l'entr├®e de log
            log_entry = {
                'timestamp': datetime.now().strftime('%H:%M:%S.%f')[:-3],
                'level': record.levelname,
                'message': record.getMessage(),
                'detail': ''
            }

            # ├ëmettre via WebSocket (m├®thode synchrone car emit() de Handler est sync)
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.sio.emit('log', log_entry))
                else:
                    loop.run_until_complete(self.sio.emit('log', log_entry))
            except RuntimeError:
                # Pas de loop actif, cr├®er une task quand m├¬me
                asyncio.create_task(self.sio.emit('log', log_entry))

        except Exception as e:
            # Ne pas bloquer si erreur d'├®mission
            pass

# Cr├®er et ajouter le handler SocketIO
socketio_handler = SocketIOHandler()
socketio_handler.setLevel(logging.DEBUG)  # ­ƒöÑ FIX: Capturer DEBUG et plus (inclut ERROR, WARNING, CRITICAL)
logging.getLogger().addHandler(socketio_handler)

# ­ƒöÑ ARCHITECTURE V2: Monter fichiers statiques
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    logger.info("Ô£à Fichiers statiques mont├®s: /static")
except Exception as e:
    logger.warning(f"ÔÜá´©Å Fichiers statiques non mont├®s: {e}")

# ­ƒöÑ FIX: Servir le frontend SvelteKit build si disponible
frontend_build_path = None
for build_path in ["frontend/build", "frontend/.svelte-kit/output", "frontend/dist"]:
    if os.path.exists(build_path):
        frontend_build_path = build_path
        break

if frontend_build_path:
    try:
        # Servir les fichiers statiques du frontend
        static_path = os.path.join(frontend_build_path, "client")
        if os.path.exists(static_path):
            app.mount("/_app", StaticFiles(directory=static_path), name="frontend_static")
            logger.info(f"Ô£à Frontend SvelteKit mont├®: /_app depuis {static_path}")
        
        # Servir les assets du frontend
        assets_path = os.path.join(frontend_build_path, "client")
        if os.path.exists(assets_path):
            # Les assets sont d├®j├á servis via /_app
            logger.info(f"Ô£à Assets frontend disponibles via /_app")
    except Exception as e:
        logger.warning(f"ÔÜá´©Å Frontend SvelteKit non mont├®: {e}")
else:
    logger.info("Ôä╣´©Å Frontend SvelteKit non build - servez-le s├®par├®ment avec 'npm run dev' dans frontend/")

# ­ƒöÑ ARCHITECTURE V2: Inclure API router (api/routes/__init__.py)
if api_router:
    app.include_router(api_router)
    logger.info("Ô£à API REST routes incluses: /api/*")

# ­ƒöÑ REFACTORISATION: Inclure les nouveaux routers
if scanner_router:
    app.include_router(scanner_router)
    logger.info("Ô£à Scanner router inclus: /api/scanner/*")

if dashboard_router:
    app.include_router(dashboard_router)
    logger.info("Ô£à Dashboard router inclus: /api/status, /api/state, /api/start, /api/stop")

# ­ƒöÑ FIX: ├ëv├®nement de d├®marrage pour initialiser les d├®pendances
@app.on_event("startup")
async def startup_event():
    """Initialiser toutes les d├®pendances au d├®marrage de l'application"""
    logger.info("­ƒÜÇ Initialisation des d├®pendances au d├®marrage...")

    # Ô£à FIX: Charger la configuration persistante
    from config import TRADING_CONFIG
    from core.config_manager import get_config_manager

    config_manager = get_config_manager()
    overrides = config_manager.get_overrides()
    if overrides:
        TRADING_CONFIG.update(overrides)
        logger.info(f"­ƒôä Configuration charg├®e depuis config_overrides.json ({len(overrides)} overrides)")

    init_instances()
    logger.info("Ô£à D├®pendances initialis├®es")

    # ­ƒöÑ FIX: D├®marrer le scheduler pour les boucles de scan
    global scheduler
    if scheduler:
        logger.info("ÔÅ░ D├®marrage du scheduler (scan loop, position check, scalability refresh)...")
        scheduler.start()
        logger.info("Ô£à Scheduler d├®marr├®")

# SocketIO
# ­ƒöÑ FIX: Utiliser async_mode='asgi' pour compatibilit├® avec Uvicorn
sio = socketio.AsyncServer(cors_allowed_origins="*", async_mode='asgi')
socketio_app = socketio.ASGIApp(sio, app)

# ­ƒöÑ Configurer le handler SocketIO avec l'instance sio
socketio_handler.set_sio(sio)

# ­ƒöÑ PHASE 4: Fichier de persistance pour trade history
# ­ƒöÑ FIX: Fichier historique par instance pour ├®viter conflits multi-instances
# Utiliser le port comme identifiant d'instance (d├®faut: 5000)
def get_trade_history_file():
    """Retourner le nom du fichier historique selon le port de l'instance"""
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    return f"trade_history_instance_{port}.json"

TRADE_HISTORY_FILE = None  # Sera initialis├® au d├®marrage

# ­ƒöÑ PHASE 8: Instance globale TradeDatabase
trade_db = None

def init_trade_database():
    """Initialiser base de donn├®es SQLite"""
    global trade_db
    if TradeDatabase and not trade_db:
        try:
            trade_db = TradeDatabase()
            logger.info("Ô£à Base de donn├®es SQLite initialis├®e")
        except Exception as e:
            logger.error(f"ÔØî Erreur initialisation DB: {e}")
            trade_db = None

def save_trade_history():
    """Sauvegarder l'historique des trades dans un fichier JSON et SQLite"""
    global TRADE_HISTORY_FILE, trade_db

    if TRADE_HISTORY_FILE is None:
        TRADE_HISTORY_FILE = get_trade_history_file()

    try:
        # ­ƒöÑ FIX: ├ëcriture atomique avec fichier temporaire puis rename
        temp_file = TRADE_HISTORY_FILE + ".tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(app_state['trade_history'], f, indent=2, ensure_ascii=False)
        # Renommer atomiquement (Windows supporte cette op├®ration)
        if os.path.exists(TRADE_HISTORY_FILE):
            os.replace(temp_file, TRADE_HISTORY_FILE)
        else:
            os.rename(temp_file, TRADE_HISTORY_FILE)
        logger.debug(f"Ô£à Historique sauvegard├®: {len(app_state['trade_history'])} trades (fichier: {TRADE_HISTORY_FILE})")
    except Exception as e:
        logger.error(f"ÔØî Erreur sauvegarde historique JSON: {e}")
        # Nettoyer fichier temporaire en cas d'erreur
        temp_file = TRADE_HISTORY_FILE + ".tmp"
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass

    # ­ƒöÑ PHASE 8: Sauvegarder aussi en SQLite (si activ├®)
    if trade_db and app_state['trade_history']:
        try:
            # Sauvegarder uniquement le dernier trade (├®viter doublons)
            last_trade = app_state['trade_history'][0] if app_state['trade_history'] else None
            if last_trade:
                # V├®rifier si d├®j├á en DB (par timestamp)
                existing = trade_db.get_trades_by_date_range(
                    last_trade.get('date', ''),
                    last_trade.get('date', '')
                )
                # Si pas d├®j├á pr├®sent, ins├®rer
                if not any(t.get('timestamp') == last_trade.get('timestamp') for t in existing):
                    trade_db.insert_trade(last_trade)
                    logger.debug(f"Ô£à Trade sauvegard├® en DB: {last_trade.get('symbol')}")
        except Exception as e:
            logger.error(f"ÔØî Erreur sauvegarde DB: {e}")

def load_trade_history():
    """Charger l'historique des trades depuis un fichier JSON et/ou SQLite"""
    global TRADE_HISTORY_FILE, trade_db

    if TRADE_HISTORY_FILE is None:
        TRADE_HISTORY_FILE = get_trade_history_file()

    # ­ƒöÑ PHASE 8: Charger depuis SQLite si disponible (priorit├®)
    if trade_db:
        try:
            db_trades = trade_db.get_all_trades()
            if db_trades:
                app_state['trade_history'] = db_trades
                logger.info(f"Ô£à Historique charg├® depuis DB: {len(db_trades)} trades")
                # Sauvegarder aussi en JSON (backup)
                save_trade_history()
                return
        except Exception as e:
            logger.error(f"ÔØî Erreur chargement DB: {e}")

    # Fallback: Charger depuis JSON
    try:
        if os.path.exists(TRADE_HISTORY_FILE):
            with open(TRADE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                app_state['trade_history'] = json.load(f)
            logger.info(f"Ô£à Historique charg├®: {len(app_state['trade_history'])} trades (fichier: {TRADE_HISTORY_FILE})")

            # ­ƒöÑ PHASE 8: Migrer JSON ÔåÆ SQLite si DB disponible
            if trade_db and app_state['trade_history']:
                try:
                    for trade in app_state['trade_history']:
                        # V├®rifier si d├®j├á en DB
                        existing = trade_db.get_trades_by_date_range(
                            trade.get('date', ''),
                            trade.get('date', '')
                        )
                        if not any(t.get('timestamp') == trade.get('timestamp') for t in existing):
                            trade_db.insert_trade(trade)
                    logger.info(f"Ô£à Migration JSON ÔåÆ SQLite: {len(app_state['trade_history'])} trades")
                except Exception as e:
                    logger.error(f"ÔØî Erreur migration DB: {e}")
        else:
            app_state['trade_history'] = []
            logger.info(f"­ƒôØ Nouveau fichier historique cr├®├®: {TRADE_HISTORY_FILE}")
    except Exception as e:
        logger.error(f"ÔØî Erreur chargement historique: {e}")
        app_state['trade_history'] = []

# Global state
app_state = {
    'is_scanning': False,
    'active_position': None,
    'stats': {
        'total_trades': 0,
        'wins': 0,
        'losses': 0,
        'winrate': 0.0
    },
    'top_pairs': [],
    'logs': [],
    'trade_history': []  # ­ƒöÑ PHASE 4: Historique des trades
}


def update_session_stats(result: dict):
    """
    Mettre ├á jour les statistiques de session apr├¿s fermeture d'une position

    Args:
        result: Dictionnaire retourn├® par position_manager.close_position()
    """
    if not result:
        return

    # Incr├®menter total trades
    app_state['stats']['total_trades'] += 1

    # D├®terminer si win ou loss bas├® sur net_pnl_usdt
    net_pnl = result.get('net_pnl_usdt', result.get('pnl_usdt', 0))

    if net_pnl > 0:
        app_state['stats']['wins'] += 1
    else:
        app_state['stats']['losses'] += 1

    # Calculer winrate
    total = app_state['stats']['total_trades']
    wins = app_state['stats']['wins']
    app_state['stats']['winrate'] = round((wins / total * 100), 2) if total > 0 else 0.0

    logger.info(
        f"­ƒôè Stats session mises ├á jour: "
        f"{wins}W/{app_state['stats']['losses']}L "
        f"({app_state['stats']['winrate']:.1f}% WR) "
        f"- Total: {total}"
    )


# ­ƒöÑ v7.0: Instances globales (lazy init)
scanner = None
analyzer = None
position_config = None
position_manager = None
price_provider = None
scheduler = None

# ­ƒöÑ ARCHITECTURE V2: Nouvelles instances
analytics_db = None
notification_manager = None
session_id = None  # ID unique de cette session

# ­ƒöÑ FIX: Lock pour ├®viter les ouvertures multiples de positions
position_lock = asyncio.Lock()

# ­ƒöÑ FIX: Lock pour ├®viter les scans multiples en parall├¿le
scanner_lock = asyncio.Lock()


def init_instances():
    """Initialiser les instances et injecter les d├®pendances dans les modules"""
    global scanner, analyzer, position_config, position_manager, price_provider, scheduler
    global analytics_db, notification_manager, session_id

    # ­ƒöÑ ARCHITECTURE V2: Initialiser Analytics DB
    if not analytics_db and AnalyticsDatabase:
        from config import ANALYTICS_DB_PATH
        import time

        # Cr├®er dossier data/ si n├®cessaire
        os.makedirs(os.path.dirname(ANALYTICS_DB_PATH) if os.path.dirname(ANALYTICS_DB_PATH) else "data", exist_ok=True)

        # ­ƒöÑ ARCHITECTURE V2: AnalyticsDatabase s'initialise automatiquement dans __init__
        try:
            # R├®cup├®rer port instance pour multi-instances
            port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
            analytics_db = AnalyticsDatabase(db_path=ANALYTICS_DB_PATH, instance_port=port)
            # La DB est d├®j├á initialis├®e dans __init__ (via _init_database())
            logger.info(f"Ô£à Analytics DB pr├¬te: {ANALYTICS_DB_PATH}")
        except Exception as e:
            logger.error(f"ÔØî Erreur init Analytics DB: {e}")
            analytics_db = None

        # G├®n├®rer session ID unique
        if not session_id:
            session_id = f"live_{int(time.time())}"
            logger.info(f"­ƒôØ Session ID: {session_id}")

        # Injecter Analytics DB dans API routes
        if set_analytics_db and analytics_db:
            set_analytics_db(analytics_db)

        # ­ƒöÑ NOUVEAU: Injecter Position Manager, Notification Manager et instance port
        # R├®cup├®rer port instance pour multi-instances
        port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000

        if set_instance_port:
            set_instance_port(port)

    # ­ƒöÑ ARCHITECTURE V2: Initialiser Notification Manager
    if not notification_manager and create_notification_manager:
        from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED
        from config import NOTIFICATION_BATCHING_ENABLED, NOTIFICATION_THROTTLE_SECONDS

        async def socketio_callback(event_type, data):
            """Callback pour envoyer via SocketIO"""
            await sio.emit(event_type, data)

        # ­ƒöÑ NOUVEAU: R├®cup├®rer port instance pour multi-instances
        port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000

        notification_manager = create_notification_manager(
            telegram_bot_token=TELEGRAM_BOT_TOKEN,
            telegram_chat_id=TELEGRAM_CHAT_ID,
            socketio_callback=socketio_callback,
            enable_batching=NOTIFICATION_BATCHING_ENABLED,
            instance_port=port  # ­ƒöÑ NOUVEAU: Passer instance_port
        )

        if TELEGRAM_ENABLED:
            logger.info(f"­ƒô▒ Notification Manager initialis├® (Telegram activ├®)")
        else:
            logger.info(f"­ƒô▒ Notification Manager initialis├® (Telegram d├®sactiv├®)")

        # ­ƒöÑ NOUVEAU: Injecter Notification Manager dans API routes (pour webhook Telegram)
        if set_notification_manager and notification_manager:
            set_notification_manager(notification_manager)

    if not scanner and ScalabilityScanner:
        scanner = ScalabilityScanner()
    if not analyzer and TechnicalAnalyzer:
        analyzer = TechnicalAnalyzer()
    if not position_config and PositionConfig:
        # ­ƒöÑ FIX: Initialiser PositionConfig depuis TRADING_CONFIG
        from config import TRADING_CONFIG
        position_config = PositionConfig()

        # Configurer TP/SL mode depuis TRADING_CONFIG
        tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
        # ­ƒöÑ PHASE 7: TP_MULTI utilise aussi le mode ATR (pour calculer ATR)
        position_config.use_atr = (tp_sl_mode == 'ATR' or tp_sl_mode == 'TP_MULTI')

        # Configurer valeurs FIXE depuis TRADING_CONFIG
        position_config.fixed_tp_pct = TRADING_CONFIG.get('tp_percent', 0.25)
        position_config.fixed_sl_pct = TRADING_CONFIG.get('sl_percent', 0.25)
        position_config.break_even_trigger = TRADING_CONFIG.get('break_even_trigger', 0.3)
        position_config.trailing_distance = TRADING_CONFIG.get('trailing_distance', 0.1)

        # Configurer valeurs ATR depuis TRADING_CONFIG
        position_config.atr_mult_tp = TRADING_CONFIG.get('atr_mult_tp', 1.5)
        position_config.atr_mult_sl = TRADING_CONFIG.get('atr_mult_sl', 1.0)
        position_config.atr_min = TRADING_CONFIG.get('atr_min', 0.15)
        position_config.atr_max = TRADING_CONFIG.get('atr_max', 1.5)

    if not position_manager and PositionManager and position_config:
        position_manager = PositionManager(position_config)

        # ­ƒöÑ ARCHITECTURE V2: Injecter analytics_db, notification_manager, session_id
        if analytics_db:
            position_manager.analytics_db = analytics_db
            position_manager.analytics_logger.analytics_db = analytics_db  # FIX: Mettre ├á jour analytics_logger aussi
            logger.info("­ƒÆ¥ Analytics DB inject├® dans Position Manager")

        if session_id:
            position_manager.session_id = session_id
            logger.info(f"­ƒôØ Session ID inject├® dans Position Manager: {session_id}")

        if notification_manager:
            position_manager.notification_manager = notification_manager
            logger.info("­ƒôó Notification Manager inject├® dans Position Manager")

        # ­ƒöÑ NOUVEAU: Injecter Position Manager dans API routes (pour webhook Telegram)
        if set_position_manager and position_manager:
            set_position_manager(position_manager)

    if not price_provider and get_price_provider:
        price_provider = get_price_provider()

    # ­ƒöÑ REFACTORISATION: Injecter les d├®pendances dans les modules
    # Scanner router
    if scanner_router:
        if scanner and set_scanner_router:
            set_scanner_router(scanner)
        if analyzer and set_analyzer_router:
            set_analyzer_router(analyzer)
        if price_provider and set_price_provider_router:
            set_price_provider_router(price_provider)
        if set_app_state_scanner:
            set_app_state_scanner(app_state)
        if set_socketio_scanner:
            set_socketio_scanner(sio)

    # Dashboard router
    if dashboard_router:
        if scheduler and set_scheduler_dashboard:
            set_scheduler_dashboard(scheduler)
        if position_manager and set_position_manager_dashboard:
            set_position_manager_dashboard(position_manager)
        if set_app_state_dashboard:
            set_app_state_dashboard(app_state)
        if set_socketio_dashboard:
            set_socketio_dashboard(sio)

    # Scanner loop callback
    if scanner_loop_callback:
        if scanner and set_scanner_callback:
            set_scanner_callback(scanner)
        if analyzer and set_analyzer_callback:
            set_analyzer_callback(analyzer)
        if position_manager and set_position_manager_scanner:
            set_position_manager_scanner(position_manager)
        if price_provider and set_price_provider_scanner:
            set_price_provider_scanner(price_provider)
        if set_app_state_scanner_callback:
            set_app_state_scanner_callback(app_state)
        if set_socketio_scanner_callback:
            set_socketio_scanner_callback(sio)
        if set_scanner_lock:
            set_scanner_lock(scanner_lock)

    # Position check loop callback
    if position_check_loop_callback:
        if position_manager and set_position_manager_position_check:
            set_position_manager_position_check(position_manager)
        if price_provider and set_price_provider_position_check:
            set_price_provider_position_check(price_provider)
        if set_app_state_position_check:
            set_app_state_position_check(app_state)
        if set_socketio_position_check:
            set_socketio_position_check(sio)
        if set_position_lock_callback:
            set_position_lock_callback(position_lock)
        if analytics_db and set_analytics_db_position_check:
            set_analytics_db_position_check(analytics_db)

    # Scalability refresh callback
    if scalability_refresh_loop_callback:
        if scanner and set_scanner_scalability:
            set_scanner_scalability(scanner)
        if position_manager and set_position_manager_scalability:
            set_position_manager_scalability(position_manager)
        if price_provider and set_price_provider_scalability:
            set_price_provider_scalability(price_provider)
        if set_app_state_scalability:
            set_app_state_scalability(app_state)
        if set_socketio_scalability:
            set_socketio_scalability(sio)

    # ­ƒöÑ JOUR 3: Initialiser scheduler et configurer les callbacks
    if not scheduler and Scheduler:
        scheduler = Scheduler()
        # Configurer les callbacks (import├®s depuis les modules)
        if scanner_loop_callback:
            scheduler.set_scanner_callback(scanner_loop_callback)
        if position_check_loop_callback:
            scheduler.set_position_check_callback(position_check_loop_callback)
        if scalability_refresh_loop_callback:
            scheduler.set_scalability_refresh_callback(scalability_refresh_loop_callback)


# Routes FastAPI - Pages HTML

@app.get("/")
async def index(request: Request):
    """Page principale - Servir frontend SvelteKit ou fallback HTML"""
    # ­ƒöÑ FIX: Essayer de servir le frontend SvelteKit build
    frontend_index = None
    for build_path in ["frontend/build/client/index.html", 
                       "frontend/.svelte-kit/output/client/index.html",
                       "frontend/dist/index.html"]:
        if os.path.exists(build_path):
            frontend_index = build_path
            break
    
    if frontend_index:
        try:
            with open(frontend_index, 'r', encoding='utf-8') as f:
                html_content = f.read()
            # ­ƒöÑ FIX: Remplacer les chemins relatifs pour fonctionner avec FastAPI
            # SvelteKit utilise des chemins absolus, on doit les adapter
            html_content = html_content.replace('href="/', 'href="/_app/')
            html_content = html_content.replace('src="/', 'src="/_app/')
            return HTMLResponse(content=html_content)
        except Exception as e:
            logger.warning(f"ÔÜá´©Å Erreur chargement frontend SvelteKit: {e}")
    
    # Fallback: servir template HTML basique
    try:
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception:
        # Si pas de template, retourner message simple
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Trade Cursor v7.0</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body>
            <h1>Trade Cursor v7.0 - Backend API</h1>
            <p>Le frontend SvelteKit n'est pas disponible.</p>
            <p>Pour lancer le frontend:</p>
            <ol>
                <li>Ouvrir un terminal dans le dossier <code>frontend/</code></li>
                <li>Ex├®cuter <code>npm install</code> puis <code>npm run dev</code></li>
                <li>Acc├®der ├á <code>http://localhost:3000</code></li>
            </ol>
            <p>Ou build le frontend avec <code>npm run build</code> et red├®marrer ce serveur.</p>
            <hr>
            <p><a href="/api/health">API Health Check</a></p>
            <p><a href="/api/state">API State</a></p>
        </body>
        </html>
        """)


@app.get("/favicon.ico")
async def favicon():
    """Favicon (├®vite 404)"""
    from fastapi.responses import Response
    # Retourner un favicon vide (1x1 pixel transparent)
    # En production, tu peux ajouter un vrai favicon.ico dans static/
    return Response(content=b'', media_type='image/x-icon')


@app.get("/dashboard/charts", response_class=HTMLResponse)
async def dashboard_charts(request: Request):
    """­ƒöÑ ARCHITECTURE V2: Dashboard graphiques avec Chart.js"""
    try:
        return templates.TemplateResponse("dashboard_charts.html", {"request": request})
    except Exception as e:
        logger.error(f"ÔØî Erreur dashboard: {e}")
        return HTMLResponse(f"<h1>Erreur</h1><p>{e}</p>", status_code=500)


@app.get("/backtest", response_class=HTMLResponse)
async def backtest(request: Request):
    """Page backtest"""
    try:
        return templates.TemplateResponse("backtest.html", {"request": request})
    except Exception as e:
        logger.error(f"ÔØî Erreur backtest page: {e}")
        return HTMLResponse(f"<h1>Erreur</h1><p>{e}</p>", status_code=500)


@app.get("/optimize", response_class=HTMLResponse)
async def optimize(request: Request):
    """Page optimisation ML"""
    try:
        return templates.TemplateResponse("optimize.html", {"request": request})
    except Exception as e:
        logger.error(f"ÔØî Erreur optimize page: {e}")
        return HTMLResponse(f"<h1>Erreur</h1><p>{e}</p>", status_code=500)


@app.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request):
    """Page analytics & stats"""
    try:
        return templates.TemplateResponse("analytics.html", {"request": request})
    except Exception as e:
        logger.error(f"ÔØî Erreur analytics page: {e}")
        return HTMLResponse(f"<h1>Erreur</h1><p>{e}</p>", status_code=500)


@app.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    """Page param├¿tres"""
    try:
        return templates.TemplateResponse("settings.html", {"request": request})
    except Exception as e:
        logger.error(f"ÔØî Erreur settings page: {e}")
        return HTMLResponse(f"<h1>Erreur</h1><p>{e}</p>", status_code=500)


# Routes API - Health Check & Price & WebSocket

@app.get("/api/health")
async def api_health():
    """Health check endpoint pour monitoring"""
    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "7.0.0",
        "backend": "FastAPI",
        "websocket": "Socket.IO"
    })


@app.get("/api/price/{symbol}")
async def api_get_price(symbol: str):
    """R├®cup├®rer prix depuis WebSocket ou REST avec info de debug"""
    init_instances()
    if not price_provider:
        return JSONResponse({'error': 'Price provider not available'}, status_code=503)

    try:
        import time
        price_data = await price_provider.get_price(symbol)
        if price_data:
            # ­ƒöÑ DEBUG: Ajouter info sur la source (WebSocket ou REST)
            is_ws = (price_provider.use_websocket and
                    price_provider.ws_manager and
                    price_provider.ws_manager.connected)

            async with price_provider.cache_lock:
                from_cache = symbol in price_provider.price_cache

            source = "WebSocket" if (is_ws and from_cache) else "REST"
            price_data['_source'] = source

            # Calculer l'├óge du prix (en secondes)
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
    ­ƒöÑ TEST: R├®cup├®rer tous les prix en cache WebSocket
    Utile pour v├®rifier que les prix sont bien mis ├á jour en temps r├®el
    """
    init_instances()

    if not price_provider:
        return JSONResponse({'error': 'Price provider not available'}, status_code=503)

    result = {
        "websocket_connected": False,
        "cache_size": 0,
        "prices": {},
        "timestamp": None
    }

    try:
        import time

        # V├®rifier ├®tat WebSocket
        if price_provider.ws_manager:
            result["websocket_connected"] = price_provider.ws_manager.connected

        # R├®cup├®rer tous les prix du cache
        async with price_provider.cache_lock:
            result["cache_size"] = len(price_provider.price_cache)
            for symbol, price_data in price_provider.price_cache.items():
                age = time.time() - price_data.get('timestamp', time.time())
                result["prices"][symbol] = {
                    "price": price_data.get('lastPrice', 0),
                    "volume24": price_data.get('volume24', 0),
                    "age_seconds": round(age, 2),
                    "timestamp": price_data.get('timestamp', 0)
                }

        result["timestamp"] = time.time()

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"Erreur r├®cup├®ration prix live: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


@app.post("/api/websocket/start")
async def api_start_websocket():
    """
    ­ƒöÑ D├®marrer manuellement le WebSocket pour les top pairs
    Utile si le WebSocket n'a pas ├®t├® d├®marr├® automatiquement
    """
    init_instances()

    if not price_provider:
        return JSONResponse({'error': 'Price provider not available'}, status_code=503)

    if not app_state['top_pairs']:
        return JSONResponse({
            'error': 'Aucune top pair disponible. Lancez d\'abord /api/scanner/start',
            'status': 'no_pairs'
        }, status_code=400)

    try:
        # R├®cup├®rer les top 30 pairs
        symbols = [p.get('symbol', '') for p in app_state['top_pairs'][:30] if p.get('symbol')]

        if not symbols:
            return JSONResponse({'error': 'Aucun symbole valide trouv├®'}, status_code=400)

        # D├®marrer WebSocket
        await price_provider.start_websocket(symbols)

        return JSONResponse({
            'status': 'started',
            'symbols_count': len(symbols),
            'symbols': symbols[:10]  # Afficher les 10 premiers
        })

    except Exception as e:
        # Code 1000 = fermeture normale WebSocket (pas une vraie erreur)
        error_msg = str(e)
        if "1000" in error_msg and ("OK" in error_msg or "Normal" in error_msg):
            logger.info(f"Ôä╣´©Å WebSocket ferm├® normalement: {e}")
            return JSONResponse({'status': 'closed_normally', 'message': str(e)})
        else:
            logger.error(f"Erreur d├®marrage WebSocket: {e}")
            return JSONResponse({'error': str(e)}, status_code=500)


# Routes API - Analyze

@app.get("/api/analyze/{symbol}")
async def api_analyze_symbol(
    symbol: str,
    tf: str = Query('1m', description="Timeframe (pour compatibilit├®)"),
    use_confluence: bool = Query(None, description="True = 1m ET 5m, False = 1m OU 5m"),
    volume_multiplier: float = Query(None, description="Multiplicateur de volume 0.1-2.0"),
    trend_timeframe: str = Query(None, description="Timeframe pour trend_data (5m, 15m, 30m, 1h)")
):
    """
    Analyser un symbole avec param├¿tres configurables

    Args:
        symbol: Symbole de la paire
        tf: Timeframe (1m ou 5m) - pour compatibilit├®, mais utilise analyze_pair maintenant
        use_confluence: True = 1m ET 5m, False = 1m OU 5m (d├®faut: depuis TRADING_CONFIG)
        volume_multiplier: Multiplicateur de volume 0.1-2.0 (d├®faut: depuis TRADING_CONFIG)
        trend_timeframe: Timeframe pour calculer trend_data (d├®faut: depuis TRADING_CONFIG)
    """
    init_instances()
    if not analyzer:
        return JSONResponse({'error': 'Analyzer not available'}, status_code=503)

    try:
        # ­ƒöÑ FIX: R├®cup├®rer valeurs depuis TRADING_CONFIG si non fournies
        from config import TRADING_CONFIG
        if use_confluence is None:
            use_confluence = TRADING_CONFIG.get('use_confluence', False)
        if volume_multiplier is None:
            volume_multiplier = TRADING_CONFIG.get('volume_multiplier', 1.0)
        if trend_timeframe is None:
            trend_timeframe = TRADING_CONFIG.get('trend_timeframe', '15m')

        # ­ƒöÑ FIX: Calculer trend_data avec le timeframe fourni ou configur├®
        trend_data = await analyzer.calculate_trend_data(symbol, trend_timeframe)

        # ­ƒöÑ PHASE 6: R├®cup├®rer positions actives pour Correlation Filter
        active_positions = []
        if position_manager and position_manager.active_position:
            active_positions = [position_manager.active_position.symbol]

        # ­ƒöÑ FIX: Utiliser analyze_pair au lieu de analyze_symbol pour supporter confluence et volume_multiplier
        analysis = await analyzer.analyze_pair(
            symbol,
            trend_data=trend_data,  # ­ƒöÑ Utiliser trend_data calcul├®
            volume_multiplier=volume_multiplier,
            use_confluence=use_confluence,
            return_reason=False,
            active_positions=active_positions,  # ­ƒöÑ PHASE 6: Correlation Filter
            position_manager=position_manager  # ­ƒöÑ PHASE 6: Recovery Mode
        )

        if analysis:
            return JSONResponse({'analysis': analysis})
        return JSONResponse({'analysis': None})
    except Exception as e:
        logger.error(f"Erreur analyse {symbol}: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


# Routes API - Position Management

@app.post("/api/position/open")
async def api_open_position(request: Request):
    """Ouvrir position"""
    init_instances()
    if not position_manager:
        return JSONResponse({'error': 'Position manager not available'}, status_code=503)

    # ­ƒöÑ FIX: Utiliser le m├¬me lock que le scanner pour ├®viter les ouvertures multiples
    async with position_lock:
        # V├®rifier qu'on n'a pas d├®j├á une position active
        if app_state['active_position'] or (position_manager and position_manager.active_position):
            return JSONResponse({'error': 'Une position est d├®j├á active'}, status_code=400)

        try:
            data = await request.json() if hasattr(request, 'json') else {}
            data = data if isinstance(data, dict) else {}

            # V├®rifier donn├®es minimales
            if not data or 'symbol' not in data:
                return JSONResponse({'error': 'Missing symbol'}, status_code=400)

            # Double-check apr├¿s avoir acquis le lock
            if app_state['active_position'] or (position_manager and position_manager.active_position):
                return JSONResponse({'error': 'Une position est d├®j├á active (double-check)'}, status_code=400)

            # ­ƒöÑ FIX: V├®rifier que entry est fourni et valide
            entry = data.get('entry')
            if not entry or entry <= 0:
                return JSONResponse({
                    'error': f'Entry invalide ou manquant: {entry}. Entry doit ├¬tre > 0.'
                }, status_code=400)

            # Extraire param├¿tres avec valeurs par d├®faut
            condition_types = data.get('condition_types', [])  # ­ƒöÑ PHASE 5: Types de conditions
            position = position_manager.open_position(
                symbol=data['symbol'],
                direction=data.get('direction', 'LONG'),
                entry=float(entry),  # ­ƒöÑ FIX: S'assurer que c'est un float
                size=data.get('size', 100.0),
                atr=data.get('atr'),
                atr5m=data.get('atr5m'),
                confirmed_by=data.get('confirmed_by', ''),
                scalability_data=data.get('scalability_data'),
                condition_types=condition_types  # ­ƒöÑ PHASE 5: Types de conditions
            )

            # ­ƒöÑ FIX: Stocker capital si fourni dans data
            if 'capital' in data:
                position.capital = data.get('capital')

            app_state['active_position'] = position

            await add_log('INFO', 'Position ouverte', f"{data.get('direction', 'LONG')} {data['symbol']}")
            await sio.emit('position_opened', position.to_dict())
            
            # ­ƒöÑ FIX: ├ëmettre l'├®tat mis ├á jour pour synchronisation temps r├®el
            status_data = {
                'is_scanning': app_state.get('is_scanning', False),
                'active_position': position.to_dict(),
                'stats': app_state.get('stats', {}),
                'top_pairs': app_state.get('top_pairs', [])
            }
            await sio.emit('status', status_data)

            return JSONResponse({'status': 'opened', 'position': position.to_dict()})
        except Exception as e:
            logger.error(f"Erreur ouverture position: {e}")
            return JSONResponse({'error': str(e)}, status_code=500)


@app.get("/api/position/active")
async def api_get_active_position():
    """­ƒöÑ FIX: R├®cup├®rer position active pour restauration au refresh"""
    init_instances()
    if not position_manager or not position_manager.active_position:
        return JSONResponse({
            'success': True,
            'active': False,
            'position': None
        })

    position = position_manager.active_position
    position_dict = position.to_dict()

    # Ajouter timestamp pour v├®rifier fra├«cheur
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
    if not position_manager or not position_manager.active_position:
        return JSONResponse({'status': 'no_position'})

    if not price_provider:
        return JSONResponse({'error': 'Price provider not available'}, status_code=503)

    try:
        # R├®cup├®rer prix actuel
        price_data = await price_provider.get_price(position_manager.active_position.symbol)
        current_price = price_data.get('lastPrice') if price_data else None

        if not current_price:
            return JSONResponse({'error': 'Price not available'}, status_code=500)

        # Check position (renvoie None ou raison de fermeture)
        result = await position_manager.check_position(current_price)

        # Construire r├®ponse
        position = position_manager.active_position
        # BUG #10 FIX: utiliser pnl_calculator au lieu de _calculate_pnl
        pnl = position_manager.pnl_calculator.calculate_pnl_percent(
            entry=position.entry,
            current_price=current_price,
            direction=position.direction
        )
        pnl_pct = pnl / 100
        pnl_usdt = position.size * pnl_pct * (current_price / position.entry)

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
            # Position ├á fermer
            response['close_reason'] = result

        await sio.emit('position_update', response)
        return JSONResponse(response)
    except Exception as e:
        logger.error(f"Erreur check position: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


@app.post("/api/position/close")
async def api_close_position():
    """Cl├┤turer position manuellement"""
    init_instances()

    # ­ƒöÑ FIX: Utiliser le lock pour synchroniser la fermeture
    async with position_lock:
        # Double-check que la position existe AVANT et APR├êS avoir acquis le lock
        if not position_manager or not position_manager.active_position:
            # V├®rifier aussi dans app_state
            if not app_state.get('active_position'):
                logger.warning("ÔÜá´©Å Tentative de fermeture sans position active (position_manager)")
                return JSONResponse({'error': 'No active position'}, status_code=400)
            else:
                # Position dans app_state mais pas dans position_manager - nettoyer app_state
                logger.warning("ÔÜá´©Å Position dans app_state mais pas dans position_manager - nettoyage")
                app_state['active_position'] = None
                return JSONResponse({'error': 'Position state inconsistent'}, status_code=400)

        if not price_provider:
            return JSONResponse({'error': 'Price provider not available'}, status_code=503)

        try:
            # R├®cup├®rer prix actuel
            price_data = await price_provider.get_price(position_manager.active_position.symbol)
            exit_price = price_data.get('lastPrice') if price_data else None

            # Ô£à FIX: Logger et utiliser fallback si prix invalide
            if not exit_price or exit_price <= 0:
                logger.error(
                    f"ÔØî Prix de sortie invalide pour {position_manager.active_position.symbol}: "
                    f"price_data={price_data}, exit_price={exit_price}"
                )
                # Utiliser le dernier prix connu ou entry
                if hasattr(position_manager, 'get_cached_price'):
                    cached_price = position_manager.get_cached_price(
                        position_manager.active_position.symbol
                    )
                    if cached_price and cached_price > 0:
                        exit_price = cached_price
                        logger.info(f"Ô£à Utilisation prix en cache: {exit_price}")
                    else:
                        exit_price = position_manager.active_position.entry
                        logger.warning(f"ÔÜá´©Å Utilisation prix d'entr├®e: {exit_price}")
                else:
                    exit_price = position_manager.active_position.entry
                    logger.warning(f"ÔÜá´©Å Utilisation prix d'entr├®e: {exit_price}")

            # FIX: Ordre correct des param├¿tres (exit_price, reason)
            result = position_manager.close_position(exit_price=exit_price, reason='MANUAL')

            app_state['active_position'] = None

            # ­ƒöÑ FIX: ├ëmettre IMM├ëDIATEMENT les ├®v├®nements Socket.IO AVANT les op├®rations lourdes
            # pour synchronisation instantan├®e du frontend
            status_data = {
                'is_scanning': app_state.get('is_scanning', False),
                'active_position': None,
                'stats': app_state.get('stats', {}),
                'top_pairs': app_state.get('top_pairs', []),
                'trade_history': list(reversed(app_state.get('trade_history', [])[-20:]))
            }
            await sio.emit('status', status_data)
            
            # ├ëmettre position_closed imm├®diatement pour que le frontend mette ├á jour l'historique
            if result:
                await sio.emit('position_closed', result)

            # ­ƒöÑ FIX: Faire les op├®rations lourdes APR├êS l'├®mission Socket.IO (en arri├¿re-plan)
            if result:
                result['timestamp'] = datetime.now().isoformat()
                app_state['trade_history'].append(result)
                if len(app_state['trade_history']) > 1000:
                    app_state['trade_history'] = app_state['trade_history'][-1000:]
                
                # FIX: Mettre ├á jour les stats de session
                update_session_stats(result)
                
                # ­ƒöÑ FIX: ├ëmettre stats_update via Socket.IO pour synchronisation temps r├®el
                if app_state.get('stats'):
                    await sio.emit('stats_update', app_state.get('stats'))
                
                # Sauvegarder l'historique en arri├¿re-plan (ne bloque pas la r├®ponse)
                save_trade_history()

            # ­ƒöÑ FIX: D├®sactiver callback WebSocket si position ferm├®e
            if price_provider:
                price_provider.set_socketio_callback(None, None)

            logger.info(
                f"­ƒöÆ Position ferm├®e manuellement avec lock: "
                f"app_state['active_position']=None, "
                f"position_manager.active_position={position_manager.active_position}"
            )

            await add_log('INFO', 'Position cl├┤tur├®e', 'Manuel')

            return JSONResponse(result)
        except Exception as e:
            logger.error(f"Erreur cl├┤ture position: {e}")
            return JSONResponse({'error': str(e)}, status_code=500)


# Helper async tasks

async def scan_top_pairs_task(n):
    """T├óche asynchrone pour scanner top pairs"""
    if not scanner:
        return

    try:
        await add_log('INFO', 'Scan scalability', 'D├®marrage...')

        top_pairs = await scanner.scan_top_pairs(n)
        app_state['top_pairs'] = top_pairs

        # ­ƒöÑ OPTIMISATION: Invalider cache quand top_pairs change
        if hasattr(app, '_top_pairs_cache'):
            app._top_pairs_cache.pop('top_pairs', None)

        await add_log('INFO', 'Scan termin├®', f'{len(top_pairs)} paires scalables')
        await sio.emit('top_pairs_update', {'pairs': top_pairs})

        # ­ƒöÑ JOUR 3: D├®marrer WebSocket pour les top pairs apr├¿s le scan
        if price_provider and top_pairs:
            symbols = [p.get('symbol', '') for p in top_pairs[:30] if p.get('symbol')]
            if symbols:
                try:
                    await price_provider.start_websocket(symbols)
                    await add_log('INFO', 'WebSocket d├®marr├®', f'{len(symbols)} symboles monitor├®s')
                except Exception as e:
                    logger.warning(f"Erreur d├®marrage WebSocket: {e}")

    except Exception as e:
        logger.error(f"Erreur scan: {e}")
        await add_log('ERROR', 'Erreur scan', str(e))
    finally:
        app_state['is_scanning'] = False
        # ­ƒöÑ FIX: ├ëmettre l'├®tat mis ├á jour via Socket.IO pour synchronisation temps r├®el
        status_data = {
            'is_scanning': False,
            'active_position': app_state.get('active_position'),
            'stats': app_state.get('stats', {}),
            'top_pairs': app_state.get('top_pairs', [])
        }
        await sio.emit('status', status_data)


# SocketIO Handlers

@sio.on('connect')
async def handle_connect(sid, environ):
    """Connexion WebSocket"""
    logger.info("Client connect├®")
    # ­ƒöÑ FIX: Convertir active_position en dict pour s├®rialisation JSON
    status_data = app_state.copy()
    if status_data.get('active_position') and hasattr(status_data['active_position'], 'to_dict'):
        status_data['active_position'] = status_data['active_position'].to_dict()
    await sio.emit('status', status_data, room=sid)
    # Envoyer les derniers logs
    for log_entry in app_state['logs'][-50:]:
        await sio.emit('log', log_entry, room=sid)


@sio.on('disconnect')
async def handle_disconnect(sid):
    """D├®connexion WebSocket"""
    logger.info("Client d├®connect├®")


@sio.on('request_logs')
async def handle_logs_request(sid):
    """Demander les logs"""
    await sio.emit('logs', app_state['logs'][-100:], room=sid)


# Configuration endpoints

@app.get("/api/state")
async def api_get_state():
    """
    ├ëtat complet de l'application (stats, position active, logs, config)

    Utilis├® par le frontend pour synchroniser l'affichage
    """
    init_instances()

    # Position active (si existe)
    active_position_dict = None
    if position_manager and position_manager.active_position:
        active_position_dict = position_manager.active_position.to_dict()
    elif app_state.get('active_position'):
        active_position_dict = app_state['active_position']

    # Ô£à FIX: Inclure la configuration compl├¿te pour le frontend
    from config import TRADING_CONFIG
    from core.config_manager import get_config_manager

    config_manager = get_config_manager()
    full_config = config_manager.get_config(TRADING_CONFIG)

    return JSONResponse({
        'is_scanning': app_state.get('is_scanning', False),
        'active_position': active_position_dict,
        'stats': app_state.get('stats', {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'winrate': 0.0
        }),
        'top_pairs': app_state.get('top_pairs', []),
        'logs': app_state.get('logs', [])[-50:],  # Derniers 50 logs
        'trade_history': list(reversed(app_state.get('trade_history', [])[-20:])),  # Derniers 20 trades
        # Ô£à FIX: Ajouter la config compl├¿te
        'config': full_config
    })


@app.get("/api/config")
async def api_get_config():
    """R├®cup├®rer la configuration actuelle (tous les param├¿tres)"""
    from config import TRADING_CONFIG, TELEGRAM_ENABLED
    return JSONResponse({
        'volume_multiplier': TRADING_CONFIG.get('volume_multiplier', 0.95),  # ­ƒöÑ Valeur mise ├á jour
        'min_score_required': TRADING_CONFIG.get('min_score_required', 7.5),  # ­ƒöÑ PHASE 6: Score minimum
        'use_confluence': TRADING_CONFIG.get('use_confluence', False),
        'tp_sl_mode': TRADING_CONFIG.get('tp_sl_mode', 'FIXE'),
        'tp_percent': TRADING_CONFIG.get('tp_percent', 0.25),
        'sl_percent': TRADING_CONFIG.get('sl_percent', 0.25),
        # ­ƒöÑ FIX: Ajouter statut Telegram
        'telegram_enabled': TELEGRAM_ENABLED,
        # ­ƒöÑ 4 seuils configurables - Valeurs mises ├á jour
        'snr_threshold': TRADING_CONFIG.get('snr_threshold', 0.25),
        'breakout_threshold': TRADING_CONFIG.get('breakout_threshold', 0.35),
        'wick_ratio_max': TRADING_CONFIG.get('wick_ratio_max', 2.8),
        'di_gap_min': TRADING_CONFIG.get('di_gap_min', 4.0),
        'di_gap_adx_threshold': TRADING_CONFIG.get('di_gap_adx_threshold', 25),
        # ­ƒöÑ Seuils ATR optimal - Valeurs mises ├á jour
        'optimal_atr_min_1m': TRADING_CONFIG.get('optimal_atr_min_1m', 0.12),
        'optimal_atr_max_1m': TRADING_CONFIG.get('optimal_atr_max_1m', 0.75),
        'optimal_atr_min_5m': TRADING_CONFIG.get('optimal_atr_min_5m', 0.22),
        'optimal_atr_max_5m': TRADING_CONFIG.get('optimal_atr_max_5m', 1.4),
        # ­ƒöÑ Trend timeframe
        'trend_timeframe': TRADING_CONFIG.get('trend_timeframe', '15m'),
        'account_size': TRADING_CONFIG.get('account_size', 1000.0),
        'risk_per_trade': TRADING_CONFIG.get('risk_per_trade', 2.0)
    })


@app.get("/api/config/verify")
async def api_verify_config():
    """
    ­ƒöÑ NOUVEAU: Endpoint de v├®rification - Retourne TOUS les param├¿tres avec leurs valeurs actuelles dans TRADING_CONFIG
    Utile pour v├®rifier que les modifications frontend sont bien appliqu├®es
    """
    from config import TRADING_CONFIG
    from core.config_manager import get_config_manager
    
    config_manager = get_config_manager()
    overrides = config_manager.get_overrides()
    
    # Retourner tous les param├¿tres configurables avec leurs valeurs actuelles
    all_params = {
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
        # Indicateurs Techniques
        'snr_threshold': TRADING_CONFIG.get('snr_threshold', 0.25),
        'breakout_threshold': TRADING_CONFIG.get('breakout_threshold', 0.35),
        'wick_ratio_max': TRADING_CONFIG.get('wick_ratio_max', 2.8),
        'di_gap_min': TRADING_CONFIG.get('di_gap_min', 4.0),
        'di_gap_adx_threshold': TRADING_CONFIG.get('di_gap_adx_threshold', 25),
        'trend_timeframe': TRADING_CONFIG.get('trend_timeframe', '15m'),
        'optimal_atr_min_1m': TRADING_CONFIG.get('optimal_atr_min_1m', 0.12),
        'optimal_atr_max_1m': TRADING_CONFIG.get('optimal_atr_max_1m', 0.75),
        'optimal_atr_min_5m': TRADING_CONFIG.get('optimal_atr_min_5m', 0.22),
        'optimal_atr_max_5m': TRADING_CONFIG.get('optimal_atr_max_5m', 1.4),
        # Validation Setups
        'use_confluence': TRADING_CONFIG.get('use_confluence', False),
        'volume_multiplier': TRADING_CONFIG.get('volume_multiplier', 0.95),
        'min_score_required': TRADING_CONFIG.get('min_score_required', 7.5),
        # Money Management
        'account_size': TRADING_CONFIG.get('account_size', 1000.0),
        'risk_per_trade': TRADING_CONFIG.get('risk_per_trade', 2.0),
        # TP/SL Mode
        'tp_sl_mode': TRADING_CONFIG.get('tp_sl_mode', 'FIXE'),
        # Mode FIXE
        'tp_percent': TRADING_CONFIG.get('tp_percent', 0.6),
        'sl_percent': TRADING_CONFIG.get('sl_percent', 0.25),
        'partial_tp_percent': TRADING_CONFIG.get('partial_tp_percent', 50.0),
        # Mode ATR
        'atr_mult_tp': TRADING_CONFIG.get('atr_mult_tp', 1.5),
        'atr_mult_sl': TRADING_CONFIG.get('atr_mult_sl', 1.0),
        'atr_min': TRADING_CONFIG.get('atr_min', 0.15),
        'atr_max': TRADING_CONFIG.get('atr_max', 1.5),
        # Mode ESCALIER
        'escalier_level1_pnl': TRADING_CONFIG.get('escalier_level1_pnl', 0.2),
        'escalier_level1_size': TRADING_CONFIG.get('escalier_level1_size', 25.0),
        'escalier_level2_pnl': TRADING_CONFIG.get('escalier_level2_pnl', 0.35),
        'escalier_level2_size': TRADING_CONFIG.get('escalier_level2_size', 25.0),
        'escalier_level3_pnl': TRADING_CONFIG.get('escalier_level3_pnl', 0.5),
        'escalier_level3_size': TRADING_CONFIG.get('escalier_level3_size', 25.0),
        'escalier_level4_pnl': TRADING_CONFIG.get('escalier_level4_pnl', 0.8),
        'escalier_level4_size': TRADING_CONFIG.get('escalier_level4_size', 25.0),
        # Trailing Stop
        'trailing_enabled': TRADING_CONFIG.get('trailing_enabled', True),
        'trailing_trigger_pnl': TRADING_CONFIG.get('trailing_trigger_pnl', 0.25),
        'trailing_atr_multiplier': TRADING_CONFIG.get('trailing_atr_multiplier', 0.4),
        'trailing_min_distance': TRADING_CONFIG.get('trailing_min_distance', 0.08),
        'trailing_max_distance': TRADING_CONFIG.get('trailing_max_distance', 0.25),
    }
    
    return JSONResponse({
        'success': True,
        'timestamp': datetime.now().isoformat(),
        'params': all_params,
        'overrides_count': len(overrides),
        'message': f'Ô£à {len(all_params)} param├¿tres v├®rifi├®s depuis TRADING_CONFIG'
    })


@app.get("/api/metrics/conditions")
async def get_condition_metrics():
    """M├®triques par condition"""
    from core.metrics import condition_metrics

    stats = condition_metrics.get_stats_summary()
    return JSONResponse(stats)


@app.post("/api/config")
async def api_update_config(request: Request):
    """Modifier la configuration ├á la vol├®e (tous les param├¿tres)"""
    from config import TRADING_CONFIG

    try:
        data = await request.json() if hasattr(request, 'json') else {}
        data = data if isinstance(data, dict) else {}

        updated = {}

        # ­ƒöÑ Volume multiplier
        if 'volume_multiplier' in data:
            val = float(data['volume_multiplier'])
            val = max(0.1, min(2.0, val))  # Clamp 0.1-2.0
            TRADING_CONFIG['volume_multiplier'] = val
            updated['volume_multiplier'] = val

        # ­ƒöÑ Confluence
        if 'use_confluence' in data:
            TRADING_CONFIG['use_confluence'] = bool(data['use_confluence'])
            updated['use_confluence'] = TRADING_CONFIG['use_confluence']

        # ­ƒöÑ TP/SL Mode
        if 'tp_sl_mode' in data:
            mode = str(data['tp_sl_mode']).upper()
            if mode in ['FIXE', 'ATR', 'TP_MULTI']:  # ­ƒöÑ PHASE 7: TP_MULTI remplace ATR_MULTI
                TRADING_CONFIG['tp_sl_mode'] = mode
                # Mettre ├á jour PositionConfig si position_manager existe
                init_instances()
                if position_config:
                    # ­ƒöÑ PHASE 7: TP_MULTI utilise aussi le mode ATR (pour calculer ATR)
                    position_config.use_atr = (mode == 'ATR' or mode == 'TP_MULTI')
                updated['tp_sl_mode'] = mode

        if 'tp_percent' in data:
            val = float(data['tp_percent'])
            TRADING_CONFIG['tp_percent'] = val
            if position_config:
                position_config.fixed_tp_pct = val
            updated['tp_percent'] = val

        if 'sl_percent' in data:
            val = float(data['sl_percent'])
            TRADING_CONFIG['sl_percent'] = val
            if position_config:
                position_config.fixed_sl_pct = val
            updated['sl_percent'] = val

        # ­ƒöÑ FIX: 4 seuils configurables
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

        # ­ƒöÑ FIX: Permettre modification des seuils ATR optimal
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

        # ­ƒöÑ FIX: Permettre modification du trend timeframe
        if 'trend_timeframe' in data:
            val = str(data['trend_timeframe']).lower()
            valid_timeframes = ['5m', '15m', '30m', '1h']
            if val in valid_timeframes:
                TRADING_CONFIG['trend_timeframe'] = val
                updated['trend_timeframe'] = val
            else:
                return JSONResponse({'error': f'Timeframe invalide: {val}. Valeurs accept├®es: {valid_timeframes}'}, status_code=400)

        # ­ƒöÑ FIX: Ajouter support pour account_size et risk_per_trade
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

        if updated:
            logger.info(f"Ô£à Configuration mise ├á jour: {updated}")
            await add_log('INFO', 'Config mise ├á jour', str(updated))
            return JSONResponse({'status': 'updated', 'updated': updated})
        else:
            return JSONResponse({'status': 'no_changes', 'message': 'Aucun param├¿tre valide fourni'})

    except Exception as e:
        logger.error(f"Erreur mise ├á jour config: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


@app.post("/api/config/update")
async def api_config_update(request: Request):
    """
    Ô£à NOUVEAU: Mettre ├á jour la configuration compl├¿te avec sauvegarde persistante

    Accepte TOUTES les variables du frontend (patterns, TP/SL, money management, etc.)
    et les sauvegarde dans config_overrides.json pour persistance
    """
    try:
        data = await request.json() if hasattr(request, 'json') else {}
        if not isinstance(data, dict):
            return JSONResponse({'error': 'Invalid request body'}, status_code=400)

        from config import TRADING_CONFIG
        from core.config_manager import get_config_manager

        config_manager = get_config_manager()

        # Ô£à Validation et mise ├á jour de toutes les variables
        validated_updates = {}

        # Patterns Techniques
        for key in ['use_breakout', 'use_snr', 'use_wick', 'use_divergence']:
            if key in data:
                validated_updates[key] = bool(data[key])

        # Patterns de Bougies
        for key in ['use_engulfing', 'use_hammer', 'use_shooting_star', 'use_doji',
                    'use_marubozu', 'use_morning_star', 'use_evening_star']:
            if key in data:
                validated_updates[key] = bool(data[key])

        # Indicateurs num├®riques
        numeric_params = {
            'snr_threshold': (0.0, 1.0),
            'breakout_threshold': (0.0, 1.0),
            'wick_ratio_max': (1.0, 10.0),
            'di_gap_min': (0.0, 50.0),
            'di_gap_adx_threshold': (0.0, 100.0),
            'optimal_atr_min_1m': (0.01, 1.0),
            'optimal_atr_max_1m': (0.1, 5.0),
            'optimal_atr_min_5m': (0.01, 2.0),
            'optimal_atr_max_5m': (0.5, 10.0),
            'volume_multiplier': (0.5, 2.0),
            'min_score_required': (0.0, 20.0),
            'account_size': (100.0, 100000.0),
            'risk_per_trade': (0.1, 10.0),
            'tp_percent': (0.05, 5.0),
            'sl_percent': (0.05, 5.0),
            'partial_tp_percent': (0, 100),
            'atr_mult_tp': (0.5, 5.0),
            'atr_mult_sl': (0.5, 3.0),
            'atr_min': (0.05, 1.0),
            'atr_max': (0.5, 5.0),
            # TP Escalier (4 niveaux)
            'escalier_level1_pnl': (0.1, 2.0),
            'escalier_level1_size': (0, 100),
            'escalier_level2_pnl': (0.1, 2.0),
            'escalier_level2_size': (0, 100),
            'escalier_level3_pnl': (0.1, 2.0),
            'escalier_level3_size': (0, 100),
            'escalier_level4_pnl': (0.1, 3.0),
            'escalier_level4_size': (0, 100),
            # Trailing Stop
            'trailing_trigger_pnl': (0.1, 3.0),
            'trailing_atr_multiplier': (0.1, 2.0),
            'trailing_min_distance': (0.05, 0.5),
            'trailing_max_distance': (0.1, 2.0),
        }

        for key, (min_val, max_val) in numeric_params.items():
            if key in data:
                try:
                    val = float(data[key])
                    # Clamp dans les limites
                    val = max(min_val, min(max_val, val))
                    validated_updates[key] = val
                except (ValueError, TypeError):
                    logger.warning(f"ÔÜá´©Å Valeur invalide pour {key}: {data[key]}")

        # Boolean params
        for key in ['use_confluence', 'trailing_enabled']:
            if key in data:
                validated_updates[key] = bool(data[key])

        # String params
        if 'trend_timeframe' in data:
            val = str(data['trend_timeframe']).lower()
            if val in ['5m', '15m', '30m', '1h']:
                validated_updates['trend_timeframe'] = val

        if 'tp_sl_mode' in data:
            mode = str(data['tp_sl_mode']).upper()
            if mode in ['FIXE', 'ATR', 'ESCALIER', 'TP_MULTI']:
                # TP_MULTI est l'ancien nom pour ESCALIER
                if mode == 'ESCALIER':
                    mode = 'TP_MULTI'
                validated_updates['tp_sl_mode'] = mode

        # Ô£à Mettre ├á jour TRADING_CONFIG en m├®moire
        TRADING_CONFIG.update(validated_updates)
        
        # ­ƒöÑ AM├ëLIORATION: Logger TOUS les param├¿tres modifi├®s avec leurs valeurs
        logger.info(f"­ƒôØ D├ëTAIL DES MODIFICATIONS ({len(validated_updates)} param├¿tres):")
        for key, value in validated_updates.items():
            logger.info(f"   Ô£à {key} = {value} (v├®rifi├®: TRADING_CONFIG['{key}'] = {TRADING_CONFIG.get(key)})")
        
        # ­ƒöÑ FIX: Logger les valeurs importantes pour debug
        if 'min_score_required' in validated_updates:
            logger.info(f"Ô£à min_score_required mis ├á jour: {validated_updates['min_score_required']} (v├®rification: TRADING_CONFIG['min_score_required'] = {TRADING_CONFIG.get('min_score_required')})")
        
        # ­ƒöÑ FIX: Logger sp├®cifiquement les patterns techniques pour confirmation
        pattern_keys = ['use_breakout', 'use_snr', 'use_wick', 'use_divergence']
        updated_patterns = {k: validated_updates[k] for k in pattern_keys if k in validated_updates}
        if updated_patterns:
            logger.info(f"­ƒÄ» PATTERNS TECHNIQUES MIS ├Ç JOUR ({len(updated_patterns)} patterns):")
            for key, value in updated_patterns.items():
                status = "Ô£à ACTIV├ë" if value else "ÔØî D├ëSACTIV├ë"
                logger.info(f"   {status}: {key} = {value} (v├®rifi├®: TRADING_CONFIG['{key}'] = {TRADING_CONFIG.get(key)})")

        # Ô£à Sauvegarder de mani├¿re persistante dans config_overrides.json
        config_manager.update_config(validated_updates)

        # Ô£à Mettre ├á jour PositionConfig si n├®cessaire
        init_instances()
        if position_config and 'tp_sl_mode' in validated_updates:
            mode = validated_updates['tp_sl_mode']
            position_config.use_atr = (mode == 'ATR' or mode == 'TP_MULTI')

        if position_config:
            if 'tp_percent' in validated_updates:
                position_config.fixed_tp_pct = validated_updates['tp_percent']
            if 'sl_percent' in validated_updates:
                position_config.fixed_sl_pct = validated_updates['sl_percent']
            # Ô£à Mettre ├á jour param├¿tres ATR
            if 'atr_mult_tp' in validated_updates:
                position_config.atr_mult_tp = validated_updates['atr_mult_tp']
            if 'atr_mult_sl' in validated_updates:
                position_config.atr_mult_sl = validated_updates['atr_mult_sl']
            if 'atr_min' in validated_updates:
                position_config.atr_min = validated_updates['atr_min']
            if 'atr_max' in validated_updates:
                position_config.atr_max = validated_updates['atr_max']
        
        # Ô£à Mettre ├á jour TrailingStopManager si n├®cessaire
        if position_manager and position_manager.trailing_stop:
            trailing_params = ['trailing_enabled', 'trailing_trigger_pnl', 'trailing_atr_multiplier', 
                             'trailing_min_distance', 'trailing_max_distance']
            if any(param in validated_updates for param in trailing_params):
                from core.position.trailing_stop import TrailingStopConfig
                position_manager.trailing_stop.config = TrailingStopConfig(
                    enabled=TRADING_CONFIG.get('trailing_enabled', True),
                    trigger_pnl=TRADING_CONFIG.get('trailing_trigger_pnl', 0.25),
                    atr_multiplier=TRADING_CONFIG.get('trailing_atr_multiplier', 0.4),
                    min_distance=TRADING_CONFIG.get('trailing_min_distance', 0.08),
                    max_distance=TRADING_CONFIG.get('trailing_max_distance', 0.25)
                )
                logger.info("Ô£à TrailingStopManager mis ├á jour avec nouvelles valeurs")

                logger.info(f"­ƒÆ¥ Configuration sauvegard├®e: {len(validated_updates)} param├¿tres mis ├á jour")
                
                # ­ƒöÑ FIX: ├ëmettre l'├®tat mis ├á jour via Socket.IO pour synchronisation temps r├®el
                status_data = {
                    'is_scanning': app_state.get('is_scanning', False),
                    'active_position': app_state.get('active_position'),
                    'stats': app_state.get('stats', {}),
                    'top_pairs': app_state.get('top_pairs', []),
                    'config': {k: TRADING_CONFIG.get(k) for k in validated_updates.keys()}
                }
                await sio.emit('status', status_data)
                await sio.emit('config_change', {
                    'timestamp': datetime.now().isoformat(),
                    'changes': validated_updates
                })
        
        # ­ƒöÑ AM├ëLIORATION: Log d├®taill├® pour chaque param├¿tre modifi├®
        updated_summary = ", ".join([f"{k}={v}" for k, v in validated_updates.items()])
        await add_log('INFO', 'Config sauvegard├®e', f"{len(validated_updates)} param├¿tres: {updated_summary}")

        return JSONResponse({
            'success': True,
            'message': f'{len(validated_updates)} param├¿tres sauvegard├®s',
            'updated': validated_updates,
            'verified': {k: TRADING_CONFIG.get(k) for k in validated_updates.keys()}  # ­ƒöÑ Retourner les valeurs v├®rifi├®es
        })

    except Exception as e:
        logger.error(f"ÔØî Erreur update config: {e}", exc_info=True)
        return JSONResponse({'error': str(e)}, status_code=500)


# Helper functions

async def add_log(level, message, detail=''):
    """Ajouter un log et envoyer via SocketIO"""
    from datetime import datetime

    entry = {
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'level': level,
        'message': message,
        'detail': detail
    }
    app_state['logs'].append(entry)

    # Garder seulement les 1000 derniers logs
    if len(app_state['logs']) > 1000:
        app_state['logs'] = app_state['logs'][-1000:]

    # Envoyer via WebSocket
    await sio.emit('log', entry)
    logger.info(f"[{entry['timestamp']}] {entry['level']}: {entry['message']}")


@app.post("/api/log/config")
async def log_config_change(request: Request):
    """
    Endpoint pour logger les modifications de configuration
    Re├ºoit les changements de variables depuis le frontend et les ├®met via WebSocket
    """
    try:
        data = await request.json()

        # Cr├®er l'entr├®e de log de configuration
        config_log_entry = {
            'timestamp': datetime.now().strftime('%H:%M:%S.%f')[:-3],
            'key': data.get('key', ''),
            'change': data.get('change', ''),
            'iso_timestamp': data.get('timestamp', datetime.now().isoformat())
        }

        # ├ëmettre via WebSocket avec ├®v├®nement sp├®cifique 'config_change'
        await sio.emit('config_change', config_log_entry)

        # Logger ├®galement dans les logs normaux pour tra├ºabilit├®
        logger.info(f"Config change: {config_log_entry['key']} ÔåÆ {config_log_entry['change']}")

        return JSONResponse({
            'status': 'success',
            'message': 'Config change logged',
            'data': config_log_entry
        })

    except Exception as e:
        logger.error(f"Error logging config change: {e}")
        return JSONResponse({
            'status': 'error',
            'message': str(e)
        }, status_code=500)


# Dashboard endpoints

def calculate_max_drawdown(trade_history: List[Dict]) -> Dict:
    """
    ­ƒöÑ PHASE 8: Calculer drawdown maximum historique (peak to trough)

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


@app.get("/api/dashboard/summary")
async def get_dashboard_summary():
    """R├®sum├® des statistiques de trading"""
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

    # ­ƒöÑ PHASE 8: Max Drawdown Tracking (calcul pr├®cis)
    max_dd_info = calculate_max_drawdown(trades)

    # Equity curve pour graphique (bas├®e sur PnL USDT)
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
    if position_manager and position_manager.config:
        recovery_mode_active = position_manager.config.recovery_mode_active

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
async def get_trades_history(limit: int = 50):
    """Historique des trades r├®cents"""
    trades = app_state['trade_history']
    # Retourner les plus r├®cents en premier
    recent_trades = list(reversed(trades[-limit:]))
    return JSONResponse(recent_trades)


@app.get("/api/export/trades")
async def export_trades_csv(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    format: str = "csv"
):
    """
    ­ƒöÑ PHASE 8: Exporter trades en CSV ou JSON

    Args:
        start_date: Date d├®but (YYYY-MM-DD)
        end_date: Date fin (YYYY-MM-DD)
        format: csv ou json (d├®faut: csv)
    """
    trades = app_state['trade_history']

    # Filtrer par dates si fourni
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


# ============================================================================
# ­ƒöÑ MULTI-SESSIONS API ENDPOINTS
# ============================================================================

try:
    from session_manager import session_manager
except ImportError:
    logger.warning("session_manager not available - multi-sessions disabled")
    session_manager = None


@app.post("/api/sessions/create")
async def create_session(request: Request):
    """Cr├®er une nouvelle session"""
    if not session_manager:
        return JSONResponse({"error": "Multi-sessions not available"}, status_code=503)

    try:
        data = await request.json()
        session = session_manager.create_session(
            session_id=data['session_id'],
            name=data['name'],
            pairs=data['pairs'],
            strategy=data.get('strategy', 'scalping'),
            config=data.get('config', {})
        )
        return JSONResponse({"status": "success", "session": session.to_dict()})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/sessions/{session_id}/start")
async def start_session(session_id: str):
    """D├®marrer une session"""
    if not session_manager:
        return JSONResponse({"error": "Multi-sessions not available"}, status_code=503)

    try:
        await session_manager.start_session(session_id)
        return JSONResponse({"status": "started", "session_id": session_id})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"Error starting session: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    """Arr├¬ter une session"""
    if not session_manager:
        return JSONResponse({"error": "Multi-sessions not available"}, status_code=503)

    try:
        await session_manager.stop_session(session_id)
        return JSONResponse({"status": "stopped", "session_id": session_id})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"Error stopping session: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/sessions/{session_id}/pause")
async def pause_session(session_id: str):
    """Mettre en pause une session"""
    if not session_manager:
        return JSONResponse({"error": "Multi-sessions not available"}, status_code=503)

    try:
        await session_manager.pause_session(session_id)
        return JSONResponse({"status": "paused", "session_id": session_id})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.post("/api/sessions/{session_id}/resume")
async def resume_session(session_id: str):
    """Reprendre une session"""
    if not session_manager:
        return JSONResponse({"error": "Multi-sessions not available"}, status_code=503)

    try:
        await session_manager.resume_session(session_id)
        return JSONResponse({"status": "resumed", "session_id": session_id})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Supprimer une session"""
    if not session_manager:
        return JSONResponse({"error": "Multi-sessions not available"}, status_code=503)

    try:
        session_manager.delete_session(session_id)
        return JSONResponse({"status": "deleted", "session_id": session_id})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.get("/api/sessions")
async def get_sessions():
    """Lister toutes les sessions"""
    if not session_manager:
        return JSONResponse({"error": "Multi-sessions not available"}, status_code=503)

    sessions = session_manager.get_all_sessions()
    return JSONResponse({"sessions": sessions})


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Obtenir une session sp├®cifique"""
    if not session_manager:
        return JSONResponse({"error": "Multi-sessions not available"}, status_code=503)

    session = session_manager.get_session(session_id)
    if session:
        return JSONResponse({"session": session})
    else:
        return JSONResponse({"error": "Session not found"}, status_code=404)


@app.get("/api/sessions/stats/global")
async def get_global_stats():
    """Stats globales de toutes les sessions"""
    if not session_manager:
        return JSONResponse({"error": "Multi-sessions not available"}, status_code=503)

    stats = session_manager.get_global_stats()
    return JSONResponse(stats)


if __name__ == '__main__':
    import uvicorn
    import socket

    # ­ƒöÑ PHASE 4: Charger l'historique au d├®marrage
    load_trade_history()

    # R├®cup├®rer le port depuis les arguments (d├®faut: 5000)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000

    # ­ƒöÑ FIX: Obtenir l'IP locale et Tailscale pour affichage
    def get_local_ip():
        """Obtenir l'IP locale du serveur (r├®seau Wi-Fi/Ethernet)"""
        try:
            # Se connecter ├á un serveur distant pour obtenir l'IP locale
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            try:
                # Fallback: utiliser hostname
                hostname = socket.gethostname()
                ip = socket.gethostbyname(hostname)
                return ip
            except Exception:
                return None

    def get_tailscale_ip():
        """Obtenir l'IP Tailscale du serveur"""
        try:
            import subprocess
            import os
            from pathlib import Path
            
            # Chercher tailscale.exe dans les emplacements Windows courants
            tailscale_paths = [
                "tailscale",  # Dans le PATH
                r"C:\Program Files\Tailscale\tailscale.exe",
                r"C:\Program Files (x86)\Tailscale\tailscale.exe",
                os.path.expanduser(r"~\AppData\Local\Programs\Tailscale\tailscale.exe"),
            ]
            
            tailscale_cmd = None
            for path in tailscale_paths:
                if path == "tailscale":
                    # V├®rifier si tailscale est dans le PATH
                    try:
                        result = subprocess.run(
                            ["where", "tailscale"],
                            capture_output=True,
                            text=True,
                            timeout=1
                        )
                        if result.returncode == 0 and result.stdout.strip():
                            tailscale_cmd = "tailscale"
                            break
                    except:
                        pass
                else:
                    # V├®rifier si le fichier existe
                    if Path(path).exists():
                        tailscale_cmd = path
                        break
            
            if not tailscale_cmd:
                return None
            
            # Ex├®cuter tailscale ip pour obtenir l'IP Tailscale
            result = subprocess.run(
                [tailscale_cmd, "ip"],
                capture_output=True,
                text=True,
                timeout=3
            )
            
            if result.returncode == 0 and result.stdout.strip():
                # tailscale ip peut retourner plusieurs IPs (IPv4 et IPv6)
                # On prend la premi├¿re IPv4 (format x.x.x.x)
                ips = result.stdout.strip().split('\n')
                for ip in ips:
                    ip = ip.strip()
                    # V├®rifier si c'est une IPv4 (format x.x.x.x)
                    parts = ip.split('.')
                    if len(parts) == 4 and all(part.isdigit() for part in parts):
                        return ip
                # Si pas d'IPv4, retourner la premi├¿re
                return ips[0].strip() if ips else None
            return None
        except FileNotFoundError:
            # Tailscale CLI non trouv├®
            return None
        except Exception:
            # Autre erreur (timeout, etc.)
            return None

    local_ip = get_local_ip()
    tailscale_ip = get_tailscale_ip()

    logger.info("­ƒÜÇ Trade Cursor v7.0 d├®marr├® (VERSION REFACTORIS├ëE)")
    logger.info("­ƒôè FastAPI (async natif) + WebSocket")
    logger.info("")
    logger.info("=" * 70)
    logger.info("­ƒôì URLs DISPONIBLES (Instance Port: {})".format(port))
    logger.info("=" * 70)
    logger.info("")
    logger.info("­ƒûÑ´©Å  ACC├êS LOCAL (m├¬me machine):")
    logger.info(f"   ÔåÆ http://localhost:{port}/")
    logger.info("")
    
    # Afficher IP locale (r├®seau Wi-Fi/Ethernet)
    if local_ip:
        logger.info("­ƒô▒ ACC├êS R├ëSEAU LOCAL (m├¬me Wi-Fi/Ethernet):")
        logger.info(f"   ÔåÆ http://{local_ip}:{port}/")
        logger.info("")
    
    # Afficher IP Tailscale (acc├¿s depuis l'ext├®rieur)
    if tailscale_ip:
        logger.info("­ƒîÉ ACC├êS TAILSCALE (depuis l'ext├®rieur via VPN):")
        logger.info(f"   ÔåÆ http://{tailscale_ip}:{port}/")
        logger.info("")
        logger.info("   Ô£à Tailscale d├®tect├®! Vous pouvez vous connecter depuis:")
        logger.info("      - Votre iPhone (via l'app Tailscale)")
        logger.info("      - N'importe o├╣ dans le monde (si connect├® ├á Tailscale)")
        logger.info("")
    else:
        logger.info("ÔÜá´©Å  Tailscale non d├®tect├®")
        logger.info("   Pour acc├¿s depuis l'ext├®rieur, installez Tailscale:")
        logger.info("   https://tailscale.com/download")
        logger.info("")
    
    logger.info("­ƒîÉ URLs COMPL├êTES:")
    if tailscale_ip:
        logger.info(f"   ­ƒÅá Interface principale      ÔåÆ http://{tailscale_ip}:{port}/")
        logger.info(f"   ­ƒôè Dashboard graphiques      ÔåÆ http://{tailscale_ip}:{port}/dashboard/charts")
        logger.info(f"   ­ƒôê Analytics & Stats         ÔåÆ http://{tailscale_ip}:{port}/analytics")
        logger.info(f"   ­ƒöä Backtesting               ÔåÆ http://{tailscale_ip}:{port}/backtest")
        logger.info(f"   ­ƒñû ML Optimization           ÔåÆ http://{tailscale_ip}:{port}/optimize")
        logger.info(f"   ÔÜÖ´©Å Param├¿tres               ÔåÆ http://{tailscale_ip}:{port}/settings")
        logger.info(f"   ­ƒÆÜ API Health check          ÔåÆ http://{tailscale_ip}:{port}/api/health")
    elif local_ip:
        logger.info(f"   ­ƒÅá Interface principale      ÔåÆ http://{local_ip}:{port}/")
        logger.info(f"   ­ƒôè Dashboard graphiques      ÔåÆ http://{local_ip}:{port}/dashboard/charts")
        logger.info(f"   ­ƒôê Analytics & Stats         ÔåÆ http://{local_ip}:{port}/analytics")
        logger.info(f"   ­ƒöä Backtesting               ÔåÆ http://{local_ip}:{port}/backtest")
        logger.info(f"   ­ƒñû ML Optimization           ÔåÆ http://{local_ip}:{port}/optimize")
        logger.info(f"   ÔÜÖ´©Å Param├¿tres               ÔåÆ http://{local_ip}:{port}/settings")
        logger.info(f"   ­ƒÆÜ API Health check          ÔåÆ http://{local_ip}:{port}/api/health")
    logger.info("")
    
    if tailscale_ip:
        logger.info("ÔÜá´©Å  IMPORTANT (Tailscale):")
        logger.info("   1. Votre iPhone doit ├¬tre connect├® ├á Tailscale")
        logger.info("   2. Le PC doit appara├«tre en vert dans l'app Tailscale iPhone")
        logger.info("   3. Utilisez l'IP Tailscale: {}".format(tailscale_ip))
        logger.info("   4. Le firewall Windows doit autoriser le port {}".format(port))
    elif local_ip:
        logger.info("ÔÜá´©Å  IMPORTANT (R├®seau local):")
        logger.info("   1. Votre iPhone est sur le m├¬me r├®seau Wi-Fi")
        logger.info("   2. Le firewall Windows autorise le port {}".format(port))
        logger.info("   3. Vous utilisez l'IP: {}".format(local_ip))
    logger.info("=" * 70)
    logger.info("")
    logger.info("­ƒöÑ REFACTORISATION:")
    logger.info("  Ô£à Callbacks d├®plac├®s dans core/callbacks/")
    logger.info("  Ô£à Routes scanner d├®plac├®es dans api/routes/scanner.py")
    logger.info("  Ô£à Routes dashboard d├®plac├®es dans api/routes/dashboard.py")
    logger.info("  Ô£à Injection de d├®pendances via set_*()")
    logger.info("  Ô£à Routers inclus avec app.include_router()")
    logger.info("")

    # Lancer FastAPI avec SocketIO - ├ëcouter sur toutes les interfaces (0.0.0.0)
    logger.info(f"­ƒîÉ Serveur d├®marr├® sur 0.0.0.0:{port} (accessible depuis le r├®seau)")
    uvicorn.run(socketio_app, host='0.0.0.0', port=port, log_level="info")
