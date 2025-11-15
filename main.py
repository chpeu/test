#!/usr/bin/env python3
"""
Trade Cursor v7.0 - Application FastAPI (async natif)
Interface HTML identique à v5.1 avec backend Python
"""

# ⚠️ IMPORTANT : Charger .env AVANT tout autre import
from dotenv import load_dotenv
load_dotenv()

import sys
import asyncio
import logging
import json
import os
import csv
import io
from datetime import datetime
from typing import Optional, List, Dict
from fastapi import FastAPI, Request, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
# 🔥 CLEANUP: HTMLResponse, StaticFiles et Jinja2Templates supprimés - Frontend Svelte gère l'interface
# 🔥 MIGRATION COMPLÈTE: socketio supprimé - WebSocket natif uniquement
from app.factory import create_app
from app.runtime import app_state, ws_manager
from app.schemas import DashboardSummary, DataloggerResetResponse
from database.pg import get_cursor
from core.websocket_manager import get_websocket_manager
import time
# 🔥 FIX: Import colorama pour les couleurs dans les logs
try:
    import colorama
    colorama.init()  # Initialiser colorama
except ImportError:
    colorama = None

# 🔥 v7.0: Imports complets
try:
    from api.price_provider import get_price_provider
    from core.scanner import ScalabilityScanner
    from core.analyzer import TechnicalAnalyzer
    from core.position_manager import PositionManager, PositionConfig
    from core.scheduler import Scheduler
    from core.metrics import get_metrics_collector
    from core.database import TradeDatabase  # 🔥 PHASE 8: SQLite (legacy)
except ImportError as e:
    logging.error(f"Import error: {e}")
    # Fallback pour les dépendances manquantes
    get_price_provider = None
    TradeDatabase = None
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

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 🔥 FIX: Configurer le logger avec WebSocket handler après l'initialisation de ws_manager
# (sera fait dans init_instances ou après l'initialisation de ws_manager)

# Initialisation FastAPI
app = create_app()


# 🔥 FIX: Exception handler global pour éviter 503 sur /api/state
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
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
            session_id_value = session_id if 'session_id' in globals() and session_id else f"live_{int(time.time())}"
        except:
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

# middlewares & router handled in app.factory

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    data_logger = None
    try:
        try:
            from backend.ml.data_logger import DataLogger
            data_logger = DataLogger()
            await data_logger.initialize()
            app.state.data_logger = data_logger
            logger.info("✅ DataLogger initialisé")
        except Exception as e:
            logger.warning(f"⚠️ Erreur initialisation DataLogger: {e}")
            app.state.data_logger = None

        init_instances()

        try:
            await asyncio.wait_for(asyncio.sleep(1.0), timeout=2.0)
        except asyncio.TimeoutError:
            logger.warning("⚠️ Timeout lors de l'initialisation WebSocket")

        if ws_manager:
            await ws_manager.emit('reset_session', {
                'timestamp': time.time(),
                'reason': 'backend_startup'
            })
            logger.info("✅ Événement reset_session émis au démarrage (AVANT le scan)")

        yield

    finally:
        try:
            if hasattr(app.state, 'data_logger') and app.state.data_logger:
                try:
                    await app.state.data_logger.shutdown()
                    logger.info("✅ DataLogger arrêté proprement")
                except Exception as e:
                    logger.error(f"❌ Erreur arrêt DataLogger: {e}")

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
            logger.warning(f"⚠️ Erreur lors du shutdown: {e}")


app.router.lifespan_context = lifespan

# 🔥 PHASE 4: Fichier de persistance pour trade history
# 🔥 FIX: Fichier historique par instance pour éviter conflits multi-instances
# Utiliser le port comme identifiant d'instance (défaut: 5000)
def get_trade_history_file():
    """Retourner le nom du fichier historique selon le port de l'instance"""
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    return f"trade_history_instance_{port}.json"

TRADE_HISTORY_FILE = None  # Sera initialisé au démarrage

# 🔥 PHASE 8: Instance globale TradeDatabase
trade_db = None

def init_trade_database():
    """Initialiser base de données SQLite"""
    global trade_db
    if TradeDatabase and not trade_db:
        try:
            trade_db = TradeDatabase()
            logger.info("✅ Base de données SQLite initialisée")
        except Exception as e:
            logger.error(f"❌ Erreur initialisation DB: {e}")
            trade_db = None

def save_trade_history():
    """Sauvegarder l'historique des trades dans un fichier JSON et SQLite"""
    global TRADE_HISTORY_FILE, trade_db
    
    if TRADE_HISTORY_FILE is None:
        TRADE_HISTORY_FILE = get_trade_history_file()
    
    try:
        # 🔥 FIX: Écriture atomique avec fichier temporaire puis rename
        temp_file = TRADE_HISTORY_FILE + ".tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(app_state['trade_history'], f, indent=2, ensure_ascii=False)
        # Renommer atomiquement (Windows supporte cette opération)
        if os.path.exists(TRADE_HISTORY_FILE):
            os.replace(temp_file, TRADE_HISTORY_FILE)
        else:
            os.rename(temp_file, TRADE_HISTORY_FILE)
        logger.debug(f"✅ Historique sauvegardé: {len(app_state['trade_history'])} trades (fichier: {TRADE_HISTORY_FILE})")
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde historique JSON: {e}")
        # Nettoyer fichier temporaire en cas d'erreur
        temp_file = TRADE_HISTORY_FILE + ".tmp"
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass
    
    # 🔥 PHASE 8: Sauvegarder aussi en SQLite (si activé)
    if trade_db and app_state['trade_history']:
        try:
            # Sauvegarder uniquement le dernier trade (éviter doublons)
            last_trade = app_state['trade_history'][0] if app_state['trade_history'] else None
            if last_trade:
                # Vérifier si déjà en DB (par timestamp)
                existing = trade_db.get_trades_by_date_range(
                    last_trade.get('date', ''),
                    last_trade.get('date', '')
                )
                # Si pas déjà présent, insérer
                if not any(t.get('timestamp') == last_trade.get('timestamp') for t in existing):
                    trade_db.insert_trade(last_trade)
                    logger.debug(f"✅ Trade sauvegardé en DB: {last_trade.get('symbol')}")
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde DB: {e}")

def load_trade_history():
    """Charger l'historique des trades depuis un fichier JSON et/ou SQLite"""
    global TRADE_HISTORY_FILE, trade_db
    
    if TRADE_HISTORY_FILE is None:
        TRADE_HISTORY_FILE = get_trade_history_file()
    
    # 🔥 PHASE 8: Charger depuis SQLite si disponible (priorité)
    if trade_db:
        try:
            db_trades = trade_db.get_all_trades()
            if db_trades:
                app_state['trade_history'] = db_trades
                logger.info(f"✅ Historique chargé depuis DB: {len(db_trades)} trades")
                # Sauvegarder aussi en JSON (backup)
                save_trade_history()
                return
        except Exception as e:
            logger.error(f"❌ Erreur chargement DB: {e}")
    
    # Fallback: Charger depuis JSON
    try:
        if os.path.exists(TRADE_HISTORY_FILE):
            with open(TRADE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                app_state['trade_history'] = json.load(f)
            logger.info(f"✅ Historique chargé: {len(app_state['trade_history'])} trades (fichier: {TRADE_HISTORY_FILE})")
            
            # 🔥 PHASE 8: Migrer JSON → SQLite si DB disponible
            if trade_db and app_state['trade_history']:
                try:
                    for trade in app_state['trade_history']:
                        # Vérifier si déjà en DB
                        existing = trade_db.get_trades_by_date_range(
                            trade.get('date', ''),
                            trade.get('date', '')
                        )
                        if not any(t.get('timestamp') == trade.get('timestamp') for t in existing):
                            trade_db.insert_trade(trade)
                    logger.info(f"✅ Migration JSON → SQLite: {len(app_state['trade_history'])} trades")
                except Exception as e:
                    logger.error(f"❌ Erreur migration DB: {e}")
        else:
            app_state['trade_history'] = []
            logger.info(f"📝 Nouveau fichier historique créé: {TRADE_HISTORY_FILE}")
    except Exception as e:
        logger.error(f"❌ Erreur chargement historique: {e}")
        app_state['trade_history'] = []

async def _run_initial_top_pairs_scan():
    """Lancer le scan initial sans bloquer la boucle d'événements"""
    init_instances()

    if app_state.get('top_pairs'):
        return  # Scan déjà effectué

    if not scanner:
        logger.warning("⚠️ Impossible de lancer le scan initial: scanner indisponible")
        return

    try:
        await add_log('INFO', 'Scanner démarré', 'Scan initial des top pairs en arrière-plan...')
        top_pairs = await scanner.scan_top_pairs(20)

        if not top_pairs:
            logger.warning("⚠️ Scan initial terminé sans résultats")
            return

        app_state['top_pairs'] = top_pairs

        if ws_manager:
            await ws_manager.emit('top_pairs_update', {'pairs': top_pairs})

        if price_provider:
            symbols = [p.get('symbol', '') for p in top_pairs[:30] if p.get('symbol')]
            if symbols:
                try:
                    await price_provider.start_websocket(symbols)
                    await add_log('INFO', 'WebSocket démarré', f'{len(symbols)} symboles monitorés')
                except Exception as e:
                    logger.warning(f"Erreur démarrage WebSocket: {e}")

    except Exception as e:
        logger.error(f"❌ Erreur scan initial en arrière-plan: {e}", exc_info=True)

# 🔥 FIX: Injecter app_state dans le router APRÈS définition
if api_router and set_app_state:
    set_app_state(app_state)
    logger.info("✅ app_state injecté dans API routes")

# 🔥 MIGRATION COMPLÈTE: ws_manager injecté dans les routes (fait après création de ws_manager)

# 🔥 v7.0: Instances globales (lazy init)
scanner = None
analyzer = None
position_config = None
position_manager = None
price_provider = None
scheduler = None

# 🔥 ARCHITECTURE V2: Nouvelles instances
analytics_db = None
notification_manager = None
session_id = None  # ID unique de cette session

# 🔥 Simple Logger: Logger ultra-simple sans batch pour debugging
_simple_logger = None

# 🔥 FIX: Lock pour éviter les ouvertures multiples de positions
position_lock = asyncio.Lock()

# 🔥 FIX: Lock pour éviter les scans multiples en parallèle
scanner_lock = asyncio.Lock()


# 🔥 JOUR 3: Callbacks pour le scheduler (doivent être définis avant init_instances)

async def scanner_loop_callback():
    """Callback appelé toutes les 45 secondes pour scanner les setups"""
    global price_provider  # 🔥 FIX: Utiliser variable globale
    
    init_instances()
    
    # 🔥 FIX: Lock global pour éviter les scans multiples en parallèle
    async with scanner_lock:
        # Ne pas scanner si on a déjà une position active (vérification atomique dans le lock)
        # Cette vérification est faite AVANT de commencer le scan pour éviter de gaspiller des ressources
        if app_state['active_position'] or (position_manager and position_manager.active_position):
            logger.debug("⏸️ Scanner ignoré : position active")
            return
        
        # 🔥 JOUR 3: Si on n'a pas de top_pairs, on les scanne d'abord
        if not app_state['top_pairs']:
            await add_log('INFO', 'Scanner loop', 'Scan initial des top pairs...')
            if scanner:
                top_pairs = await scanner.scan_top_pairs(20)
                app_state['top_pairs'] = top_pairs
                
                # 🔥 OPTIMISATION: Invalider cache quand top_pairs change
                if hasattr(app, '_top_pairs_cache'):
                    app._top_pairs_cache.pop('top_pairs', None)
                
                await ws_manager.emit('top_pairs_update', {'pairs': top_pairs})
                
                # 🔥 JOUR 3: Démarrer WebSocket pour les top pairs
                if price_provider and top_pairs:
                    symbols = [p.get('symbol', '') for p in top_pairs[:30] if p.get('symbol')]
                    if symbols:
                        try:
                            await price_provider.start_websocket(symbols)
                            await add_log('INFO', 'WebSocket démarré', f'{len(symbols)} symboles monitorés')
                        except Exception as e:
                            logger.warning(f"Erreur démarrage WebSocket: {e}")
        
        # 🔥 JOUR 3: Scanner plusieurs paires en parallèle (top 20)
        if app_state['top_pairs']:
            # 🔥 FIX: Scanner top 20 au lieu de top 5 pour plus d'opportunités
            from config import TRADING_CONFIG
            max_pairs = TRADING_CONFIG.get('top_pairs_limit', 20)
            total_available = len(app_state['top_pairs'])
            top_n = min(max_pairs, total_available)  # Scanner top 20
            pairs_to_scan = app_state['top_pairs'][:top_n]
            
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
                await ws_manager.emit('volume_stats_update', {
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
                            async with position_lock:
                                # Vérifier à nouveau qu'on n'a pas déjà une position (double-check après lock)
                                if app_state['active_position'] or (position_manager and position_manager.active_position):
                                    logger.warning(
                                        f"🚫 Position déjà active - Scanner ignoré. "
                                        f"app_state['active_position']={app_state['active_position'] is not None}, "
                                        f"position_manager.active_position={position_manager.active_position if position_manager else None}"
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
                                    if not price_provider:
                                        price_provider = get_price_provider()
                                    
                                    price_data = await price_provider.get_price(symbol)
                                    if not price_data:
                                        await add_log('ERROR', 'Prix non disponible', symbol)
                                        continue
                                    
                                    entry_price = price_data.get('lastPrice', setup.get('price', 0))
                                    if not entry_price or entry_price == 0:
                                        await add_log('ERROR', 'Prix invalide', f"{symbol}: {entry_price}")
                                        continue
                                    
                                    # 🔥 FIX: Log pour debug - vérifier le prix récupéré
                                    logger.info(
                                        f"💰 Prix récupéré pour {symbol}: lastPrice={price_data.get('lastPrice')}, "
                                        f"setup.get('price')={setup.get('price')}, entry_price={entry_price}"
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
                                    position_size = position_manager.calculate_position_size(
                                        setup=setup,
                                        capital=account_size
                                    )
                                    
                                    # 🔥 FIX: Log détaillé du calcul de taille pour debug
                                    logger.info(
                                        f"💰 Calcul taille position adaptative: {symbol} | "
                                        f"Capital: {account_size:.2f} USDT | "
                                        f"Risk%: {risk_per_trade*100:.2f}% | "
                                        f"SL%: {sl_percent:.4f}% | "
                                        f"Taille calculée: {position_size:.2f} USDT"
                                    )
                                    
                                    # Récupérer scalability_data pour slippage
                                    scalability_data = None
                                    logger.info(f"💹 DEBUG: Recherche scalability_data pour {symbol} (main.py)")
                                    
                                    if app_state.get('top_pairs'):
                                        logger.info(f"💹 DEBUG: top_pairs contient {len(app_state['top_pairs'])} paires")
                                        found_pair = False
                                        for pair in app_state['top_pairs']:
                                            if pair.get('symbol') == symbol:
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
                                                logger.error(f"💹 ERREUR: Impossible de récupérer spread_pct depuis setup pour {symbol}")
                                    else:
                                        logger.warning(f"💹 top_pairs non disponible pour récupérer scalability_data pour {symbol}")
                                    
                                    # ✅ Stocker scan_uuid, opportunity_id et setup complet pour Point C
                                    position_manager._last_setup_scan_uuid = setup.get('_scan_uuid')
                                    position_manager._last_setup_opportunity_id = setup.get('_opportunity_id')
                                    
                                    # 🔥 DEBUG: Vérifier si setup contient les indicateurs avant stockage
                                    logger.info(f"🔍 DEBUG main.py: setup contient indicators_1m: {'indicators_1m' in setup}, indicators_5m: {'indicators_5m' in setup}")
                                    if 'indicators_1m' in setup:
                                        logger.info(f"✅ indicators_1m présent dans setup: {len(setup.get('indicators_1m', {}))} clés")
                                    if 'indicators_5m' in setup:
                                        logger.info(f"✅ indicators_5m présent dans setup: {len(setup.get('indicators_5m', {}))} clés")
                                    
                                    position_manager._last_setup = setup  # Stocker setup complet pour récupérer indicateurs
                                    
                                    # 🔥 DEBUG: Vérifier après stockage
                                    logger.info(f"🔍 DEBUG main.py: _last_setup après stockage contient indicators_1m: {'indicators_1m' in position_manager._last_setup}, indicators_5m: {'indicators_5m' in position_manager._last_setup}")
                                    
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
                                    
                                    # Ouvrir la position
                                    condition_types = setup.get('condition_types', [])  # 🔥 PHASE 5: Types de conditions
                                    position = position_manager.open_position(
                                        symbol=symbol,
                                        direction=direction,
                                        entry=entry_price,
                                        size=position_size,
                                        atr=atr,
                                        atr5m=atr5m,
                                        confirmed_by=setup.get('confirmedBy', 'Scanner auto'),
                                        scalability_data=scalability_data,
                                        condition_types=condition_types  # 🔥 PHASE 5: Types de conditions
                                    )
                                    
                                    # Stocker capital
                                    position.capital = account_size
                                    
                                    # Mettre à jour app_state AVANT d'émettre l'événement
                                    app_state['active_position'] = position
                                    
                                    # 🔥 FIX: Vérification finale avant de continuer
                                    if app_state['active_position'] != position:
                                        logger.error(f"❌ ERREUR: app_state['active_position'] a été modifié pendant l'ouverture !")
                                        break
                                    
                                    # 🔥 FIX: S'abonner au WebSocket pour prix en temps réel
                                    if price_provider and price_provider.ws_manager and price_provider.ws_manager.connected:
                                        try:
                                            await price_provider.ws_manager.subscribe_ticker(symbol)
                                            logger.debug(f"📡 WebSocket: Abonné à {symbol} pour prix temps réel")
                                            
                                            # 🔥 FIX: Configurer callback pour suivre position active
                                            # Le WebSocket met à jour le cache en temps réel
                                            # La boucle de check à 0.5s récupère le prix du cache et émet position_update
                                            price_provider.set_socketio_callback(None, symbol)
                                            logger.debug(f"📡 WebSocket configuré pour suivre {symbol} (prix en temps réel dans cache)")
                                        except Exception as e:
                                            logger.warning(f"⚠️ Erreur abonnement WebSocket {symbol}: {e}")
                                    
                                    # Logger et notifier (UNE SEULE FOIS)
                                    await add_log('INFO', 'Position ouverte automatiquement', 
                                        f"{direction} {symbol} @ {entry_price:.6f} | Size: {position_size:.2f} USDT")
                                    
                                    # 🔥 FIX: Émettre l'événement UNE SEULE FOIS avec gestion d'erreur pour éviter les déconnexions
                                    try:
                                        await ws_manager.emit('position_opened', position.to_dict())
                                    except Exception as e:
                                        logger.warning(f"⚠️ Erreur émission position_opened: {e}")
                                    
                                    # 🔥 FIX: Émettre immédiatement le prix actuel pour l'affichage frontend avec gestion d'erreur
                                    try:
                                        current_price_data = await price_provider.get_price(symbol)
                                        if current_price_data:
                                            current_price = current_price_data.get('lastPrice', entry_price) if isinstance(current_price_data, dict) else entry_price
                                            # 🔥 FIX: Utiliser pnl_calculator au lieu de _calculate_pnl
                                            pnl = position_manager.pnl_calculator.calculate_pnl_percent(
                                                entry=position.entry,
                                                current_price=current_price,
                                                direction=position.direction
                                            )
                                            # Calculer PnL USDT
                                            pnl_usdt = position_manager.pnl_calculator.calculate_pnl_usdt(
                                                position=position.to_dict(),
                                                current_price=current_price
                                            )
                                            
                                            # 🔥 FIX: Gestion d'erreur pour éviter les déconnexions WebSocket
                                            try:
                                                await ws_manager.emit('position_update', {
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
                                                    'partial_tp_sold': position.partial_tp_sold
                                                })
                                                logger.debug(f"📡 Prix actuel émis immédiatement: {current_price:.6f} pour {symbol}")
                                            except Exception as e:
                                                logger.warning(f"⚠️ Erreur émission position_update: {e}")
                                    except Exception as e:
                                        logger.warning(f"⚠️ Erreur récupération prix initial: {e}")
                                    
                                    logger.info(
                                        f"🟢 POSITION OUVERTE (Auto): {direction} {symbol} | "
                                        f"Entry: {entry_price:.6f} | Size: {position_size:.2f} USDT (position.size={position.size:.2f}) | "
                                        f"SL: {position.sl:.6f} | TP: {position.tp:.6f} | "
                                        f"Lock maintenu jusqu'à la fin"
                                    )
                                    
                                    # Ne prendre que le premier setup valide - sortir immédiatement
                                    break
                                    
                                except Exception as e:
                                    logger.error(f"❌ Erreur ouverture position auto pour {symbol}: {e}")
                                    import traceback
                                    logger.error(f"Traceback: {traceback.format_exc()}")
                                    await add_log('ERROR', 'Erreur ouverture position', f"{symbol}: {str(e)}")
                                    continue
                else:
                    # 🔥 FIX: Log détaillé quand aucun setup n'est trouvé
                    # Note: rejection_reasons est défini dans le bloc if scan_tasks ci-dessus
                    await add_log('INFO', 'Aucun setup', 
                        'Aucun setup valide trouvé sur les paires analysées')
    
    # 🔥 FIX: Le lock scanner_lock est automatiquement libéré ici (fin du bloc async with)


async def scan_pair_for_setup(symbol: str):
    """Scanner une paire pour trouver un setup"""
    global _simple_logger  # 🔥 Simple Logger: Accès à la variable globale
    init_instances()
    
    if not analyzer:
        logger.warning(f"Analyzer non disponible pour {symbol}")
        return None
    
    # 🔥 PHASE 3: Mesurer la durée du scan
    scan_start_time = time.time()
    
    # 🔥 FIX: Ajouter log pour voir que l'analyse démarre
    logger.info(f"🔍 Analyse {symbol}...")
    
    try:
        # 🔥 FIX: Récupérer paramètres depuis TRADING_CONFIG
        from config import TRADING_CONFIG
        use_confluence = TRADING_CONFIG.get('use_confluence', False)
        volume_multiplier = TRADING_CONFIG.get('volume_multiplier', 1.0)
        trend_timeframe = TRADING_CONFIG.get('trend_timeframe', '15m')
        
        # 🔥 FIX: Calculer trend_data avec le timeframe configuré
        trend_data = await analyzer.calculate_trend_data(symbol, trend_timeframe)
        if trend_data:
            logger.debug(f"📊 {symbol}: Trend {trend_timeframe} = {trend_data['trend']} ({trend_data['strength']}, bonus={trend_data['bonus']})")
        
        # 🔥 PHASE 6: Récupérer positions actives pour Correlation Filter
        active_positions = []
        if position_manager and position_manager.active_position:
            active_positions = [position_manager.active_position.symbol]
        
        # 🔥 FIX: Analyser avec retour de raison si pas de setup + paramètres configurables
        analysis = await analyzer.analyze_pair(
            symbol, 
            trend_data=trend_data,  # 🔥 Utiliser trend_data calculé
            volume_multiplier=volume_multiplier,
            use_confluence=use_confluence,
            return_reason=True,
            active_positions=active_positions,  # 🔥 PHASE 6: Correlation Filter
            position_manager=position_manager  # 🔥 PHASE 6: Recovery Mode
        )
        
        # 🔥 FIX: Ajouter indicators_1m et indicators_5m à analysis IMMÉDIATEMENT après analyze_pair
        # pour qu'ils soient disponibles dans _last_setup
        if analysis and isinstance(analysis, dict):
            # Extraire les indicateurs depuis analysis si disponibles
            indicators_1m = analysis.get('indicators_1m', {})
            indicators_5m = analysis.get('indicators_5m', {})
            
            logger.info(f"🔍 DEBUG scan_pair_for_setup({symbol}): indicators_1m présent: {bool(indicators_1m)}, indicators_5m présent: {bool(indicators_5m)}")
            
            # Si les indicateurs ne sont pas présents, essayer de les construire depuis les données disponibles
            if not indicators_1m:
                logger.info(f"🔧 Construction indicators_1m depuis analysis pour {symbol}")
                # 🔥 DEBUG: Vérifier quelles données sont disponibles dans analysis
                available_keys = [k for k in analysis.keys() if k not in ['symbol', 'direction', 'entry', 'sl', 'tp', 'price', 'signals', 'condition_types', 'totalScore', 'reason', 'reject_category']]
                logger.info(f"🔍 DEBUG analysis keys disponibles pour indicators_1m: {available_keys[:20]}")
                
                # 🔥 PRIORITÉ 1: Vérifier si analysis contient analysis_1m (retourné par analyze_pair quand aucun setup n'est trouvé)
                analysis_1m = analysis.get('analysis_1m', {})
                if isinstance(analysis_1m, dict) and analysis_1m:
                    # Extraire les indicateurs depuis analysis_1m
                    indicators_1m = {
                        'rsi': analysis_1m.get('rsi'),
                        'rsi_prev': analysis_1m.get('rsi_prev'),
                        'macd': analysis_1m.get('macd'),
                        'macd_signal': analysis_1m.get('macd_signal'),
                        'macd_hist': analysis_1m.get('macd_hist'),
                        'macd_hist_prev': analysis_1m.get('macd_hist_prev'),
                        'adx': analysis_1m.get('adx'),
                        'di_plus': analysis_1m.get('di_plus'),
                        'di_minus': analysis_1m.get('di_minus'),
                        'di_gap': analysis_1m.get('di_gap'),
                        'ema9': analysis_1m.get('ema9'),
                        'ema21': analysis_1m.get('ema21'),
                        'ema_diff_pct': analysis_1m.get('ema_diff_pct'),
                        'atr': analysis_1m.get('atr'),
                        'atr_pct': analysis_1m.get('atr_pct'),
                        'bb_upper': analysis_1m.get('bb_upper'),
                        'bb_middle': analysis_1m.get('bb_middle'),
                        'bb_lower': analysis_1m.get('bb_lower'),
                        'bb_width': analysis_1m.get('bb_width'),
                        'bb_distance_to_lower': analysis_1m.get('bb_distance_to_lower'),
                        'bb_distance_to_upper': analysis_1m.get('bb_distance_to_upper'),
                        'volume': analysis_1m.get('volume'),
                        'volume_avg': analysis_1m.get('volume_avg'),
                        'volume_ratio': analysis_1m.get('volume_ratio') or analysis_1m.get('volumeSpike'),
                        'volume_spike': analysis_1m.get('volume_spike'),
                    }
                    logger.debug(f"🔍 DEBUG {symbol}: indicators_1m construit depuis analysis_1m")
                else:
                    # 🔥 PRIORITÉ 2: Chercher directement dans analysis (pour les setups valides)
                    indicators_1m = {
                        'rsi': analysis.get('rsi'),
                        'rsi_prev': analysis.get('rsi_prev'),
                        'macd': analysis.get('macd'),
                        'macd_signal': analysis.get('macd_signal'),
                        'macd_hist': analysis.get('macd_hist'),
                        'macd_hist_prev': analysis.get('macd_hist_prev'),
                        'adx': analysis.get('adx'),
                        'di_plus': analysis.get('di_plus'),
                        'di_minus': analysis.get('di_minus'),
                        'di_gap': analysis.get('di_gap'),
                        'ema9': analysis.get('ema9'),
                        'ema21': analysis.get('ema21'),
                        'ema_diff_pct': analysis.get('ema_diff_pct'),
                        'atr': analysis.get('atr'),
                        'atr_pct': analysis.get('atr_pct'),
                        'bb_upper': analysis.get('bb_upper'),
                        'bb_middle': analysis.get('bb_middle'),
                        'bb_lower': analysis.get('bb_lower'),
                        'bb_width': analysis.get('bb_width'),
                        'bb_distance_to_lower': analysis.get('bb_distance_to_lower'),
                        'bb_distance_to_upper': analysis.get('bb_distance_to_upper'),
                        'volume': analysis.get('volume'),
                        'volume_avg': analysis.get('volume_avg'),
                        'volume_ratio': analysis.get('volume_ratio') or analysis.get('volumeSpike'),
                        'volume_spike': analysis.get('volume_spike'),
                    }
                    logger.debug(f"🔍 DEBUG {symbol}: indicators_1m construit depuis analysis directement")
                
                # 🔥 DEBUG: Compter les valeurs non-null
                indicators_1m_non_null = len([v for v in indicators_1m.values() if v is not None])
                logger.info(f"🔍 DEBUG indicators_1m construit: {indicators_1m_non_null}/{len(indicators_1m)} valeurs non-null")
            
            if not indicators_5m:
                logger.info(f"🔧 Construction indicators_5m depuis analysis pour {symbol}")
                
                # 🔥 PRIORITÉ 1: Vérifier si analysis contient analysis_5m (retourné par analyze_pair quand aucun setup n'est trouvé)
                analysis_5m = analysis.get('analysis_5m', {})
                if isinstance(analysis_5m, dict) and analysis_5m:
                    # Extraire les indicateurs depuis analysis_5m
                    indicators_5m = {
                        'rsi': analysis_5m.get('rsi'),
                        'rsi_prev': analysis_5m.get('rsi_prev'),
                        'macd': analysis_5m.get('macd'),
                        'macd_signal': analysis_5m.get('macd_signal'),
                        'macd_hist': analysis_5m.get('macd_hist'),
                        'macd_hist_prev': analysis_5m.get('macd_hist_prev'),
                        'adx': analysis_5m.get('adx'),
                        'di_plus': analysis_5m.get('di_plus'),
                        'di_minus': analysis_5m.get('di_minus'),
                        'di_gap': analysis_5m.get('di_gap'),
                        'ema9': analysis_5m.get('ema9'),
                        'ema21': analysis_5m.get('ema21'),
                        'ema_diff_pct': analysis_5m.get('ema_diff_pct'),
                        'atr': analysis_5m.get('atr'),
                        'atr_pct': analysis_5m.get('atr_pct'),
                        'bb_upper': analysis_5m.get('bb_upper'),
                        'bb_middle': analysis_5m.get('bb_middle'),
                        'bb_lower': analysis_5m.get('bb_lower'),
                        'bb_width': analysis_5m.get('bb_width'),
                        'bb_distance_to_lower': analysis_5m.get('bb_distance_to_lower'),
                        'bb_distance_to_upper': analysis_5m.get('bb_distance_to_upper'),
                        'volume': analysis_5m.get('volume'),
                        'volume_avg': analysis_5m.get('volume_avg'),
                        'volume_ratio': analysis_5m.get('volume_ratio') or analysis_5m.get('volumeSpike'),
                        'volume_spike': analysis_5m.get('volume_spike'),
                    }
                    logger.debug(f"🔍 DEBUG {symbol}: indicators_5m construit depuis analysis_5m")
                else:
                    # 🔥 PRIORITÉ 2: Chercher directement dans analysis (pour les setups valides)
                    indicators_5m = {
                        'rsi': analysis.get('rsi_5m'),
                        'rsi_prev': analysis.get('rsi_prev_5m'),
                        'macd': analysis.get('macd_5m'),
                        'macd_signal': analysis.get('macd_signal_5m'),
                        'macd_hist': analysis.get('macd_hist_5m'),
                        'macd_hist_prev': analysis.get('macd_hist_prev_5m'),
                        'adx': analysis.get('adx_5m'),
                        'di_plus': analysis.get('di_plus_5m'),
                        'di_minus': analysis.get('di_minus_5m'),
                        'di_gap': analysis.get('di_gap_5m'),
                        'ema9': analysis.get('ema9_5m'),
                        'ema21': analysis.get('ema21_5m'),
                        'ema_diff_pct': analysis.get('ema_diff_pct_5m'),
                        'atr': analysis.get('atr5m') or analysis.get('atr_5m'),
                        'atr_pct': analysis.get('atr_pct_5m'),
                        'bb_upper': analysis.get('bb_upper_5m'),
                        'bb_middle': analysis.get('bb_middle_5m'),
                        'bb_lower': analysis.get('bb_lower_5m'),
                        'bb_width': analysis.get('bb_width_5m'),
                        'bb_distance_to_lower': analysis.get('bb_distance_to_lower_5m'),
                        'bb_distance_to_upper': analysis.get('bb_distance_to_upper_5m'),
                        'volume': analysis.get('volume_5m'),
                        'volume_avg': analysis.get('volume_avg_5m'),
                        'volume_ratio': analysis.get('volume_ratio_5m'),
                        'volume_spike': analysis.get('volume_spike_5m'),
                    }
                    logger.debug(f"🔍 DEBUG {symbol}: indicators_5m construit depuis analysis directement")
                
                # 🔥 DEBUG: Compter les valeurs non-null
                indicators_5m_non_null = len([v for v in indicators_5m.values() if v is not None])
                logger.info(f"🔍 DEBUG indicators_5m construit: {indicators_5m_non_null}/{len(indicators_5m)} valeurs non-null")
            
            # Ajouter les indicateurs à analysis
            analysis['indicators_1m'] = indicators_1m
            analysis['indicators_5m'] = indicators_5m
            logger.info(f"✅ Indicateurs ajoutés à analysis pour {symbol}: indicators_1m keys: {len(indicators_1m)}, indicators_5m keys: {len(indicators_5m)}")
        
        # 🔥 Simple Logger: Logger ultra-simple sans batch pour debugging
        try:
            if _simple_logger and hasattr(_simple_logger, 'enabled') and _simple_logger.enabled:
                logger.info(f"🔍 DEBUG Simple Logger pour {symbol}: enabled={_simple_logger.enabled}")
                
                # Récupérer le prix depuis analysis ou price_provider
                scan_price = None
                if analysis and isinstance(analysis, dict):
                    scan_price = analysis.get('price')
                
                # Si le prix n'est pas dans analysis, essayer de le récupérer depuis price_provider
                if scan_price is None and price_provider:
                    try:
                        price_result = await price_provider.get_price(symbol)
                        # Extraire la valeur numérique si c'est un dict
                        if isinstance(price_result, dict):
                            scan_price = price_result.get('price') or price_result.get('lastPrice') or price_result.get('close')
                        else:
                            scan_price = price_result
                    except Exception as price_error:
                        logger.debug(f"⚠️ Impossible de récupérer le prix pour {symbol}: {price_error}")
                
                # Extraire la valeur numérique si scan_price est un dict
                if isinstance(scan_price, dict):
                    scan_price = scan_price.get('price') or scan_price.get('lastPrice') or scan_price.get('close') or scan_price.get('value')
                
                # Vérifier que scan_price est un nombre
                if scan_price is not None and not isinstance(scan_price, (int, float)):
                    try:
                        scan_price = float(scan_price)
                    except (ValueError, TypeError):
                        logger.warning(f"⚠️ Prix invalide pour {symbol}: {scan_price} (type: {type(scan_price)})")
                        scan_price = None
                
                # Construire indicators_1m avec fallbacks
                indicators_1m = {}
                score_total = None
                
                if analysis:
                    # Priorité 1: indicators_1m depuis analysis
                    indicators_1m = analysis.get('indicators_1m', {}) or {}
                    
                    # Récupérer score_total avec fallbacks
                    # Priorité 1: score_total directement
                    score_total = analysis.get('score_total')
                    # Priorité 2: totalScore (nom utilisé dans analyzer.py)
                    if score_total is None:
                        score_total = analysis.get('totalScore')
                    # Priorité 3: score (nom alternatif)
                    if score_total is None:
                        score_total = analysis.get('score')
                    
                    # 🔥 AMÉLIORATION: Récupérer analysis_1m et analysis_5m une seule fois
                    analysis_1m = analysis.get('analysis_1m', {})
                    analysis_5m = analysis.get('analysis_5m', {})
                    
                    # Fallback 1: Essayer depuis analysis_1m pour score_total
                    if score_total is None and isinstance(analysis_1m, dict) and analysis_1m:
                        score_total = analysis_1m.get('score_total') or analysis_1m.get('totalScore') or analysis_1m.get('score')
                        # Si toujours None, essayer long_score ou short_score (utilisés dans analyzer.py pour les analyses rejetées)
                        if score_total is None:
                            # Prendre le maximum entre long_score et short_score, ou le premier non-None
                            long_score = analysis_1m.get('long_score')
                            short_score = analysis_1m.get('short_score')
                            if long_score is not None or short_score is not None:
                                score_total = max(long_score or 0, short_score or 0) if (long_score is not None and short_score is not None) else (long_score or short_score)
                    # Fallback 2: Essayer depuis analysis_5m pour score_total
                    if score_total is None and isinstance(analysis_5m, dict) and analysis_5m:
                        score_total = analysis_5m.get('score_total') or analysis_5m.get('totalScore') or analysis_5m.get('score')
                        # Si toujours None, essayer long_score ou short_score
                        if score_total is None:
                            long_score = analysis_5m.get('long_score')
                            short_score = analysis_5m.get('short_score')
                            if long_score is not None or short_score is not None:
                                score_total = max(long_score or 0, short_score or 0) if (long_score is not None and short_score is not None) else (long_score or short_score)
                    
                    # 🔥 AMÉLIORATION: Compléter indicators_1m avec les valeurs de analysis_1m si elles sont None
                    if isinstance(analysis_1m, dict) and analysis_1m:
                        # Log de debug pour voir ce qui est dans analysis_1m
                        rsi_in_analysis_1m = analysis_1m.get('rsi')
                        logger.debug(f"🔍 DEBUG {symbol}: analysis_1m contient rsi={rsi_in_analysis_1m}, keys: {list(analysis_1m.keys())[:15]}")
                        
                        # Liste des indicateurs clés à vérifier
                        indicator_keys = ['rsi', 'rsi_prev', 'macd', 'macd_signal', 'macd_hist', 'macd_hist_prev',
                                        'adx', 'di_plus', 'di_minus', 'di_gap', 'ema9', 'ema21', 'ema_diff_pct',
                                        'atr', 'atr_pct', 'bb_upper', 'bb_middle', 'bb_lower', 'bb_width',
                                        'bb_distance_to_lower', 'bb_distance_to_upper', 'volume', 'volume_avg',
                                        'volume_ratio', 'volume_spike']
                        
                        rsi_found_count = 0
                        for key in indicator_keys:
                            # Si l'indicateur n'existe pas dans indicators_1m ou est None, essayer de le récupérer depuis analysis_1m
                            if key not in indicators_1m or indicators_1m.get(key) is None:
                                value = analysis_1m.get(key)
                                if value is not None:
                                    indicators_1m[key] = value
                                    if key == 'rsi':
                                        rsi_found_count += 1
                                        logger.info(f"✅ DEBUG {symbol}: RSI récupéré depuis analysis_1m: {value}")
                        
                        if rsi_found_count == 0 and rsi_in_analysis_1m is None:
                            logger.debug(f"⚠️ DEBUG {symbol}: RSI est None dans analysis_1m. analysis_1m contient 'reason': {analysis_1m.get('reason', 'N/A')[:50] if analysis_1m.get('reason') else 'N/A'}")
                    
                    # Priorité 3: Essayer depuis analysis directement (champs de haut niveau) si RSI toujours manquant
                    if not indicators_1m.get('rsi'):
                        if 'rsi' in analysis and analysis.get('rsi') is not None:
                            indicators_1m['rsi'] = analysis.get('rsi')
                            logger.debug(f"🔍 DEBUG {symbol}: RSI récupéré depuis analysis (rsi): {indicators_1m.get('rsi')}")
                        elif 'rsi_1m' in analysis and analysis.get('rsi_1m') is not None:
                            indicators_1m['rsi'] = analysis.get('rsi_1m')
                            logger.debug(f"🔍 DEBUG {symbol}: RSI récupéré depuis analysis (rsi_1m): {indicators_1m.get('rsi')}")
                    
                    # Log de debug si RSI toujours manquant
                    if not indicators_1m.get('rsi'):
                        logger.debug(f"⚠️ DEBUG {symbol}: RSI non trouvé. analysis keys: {list(analysis.keys())[:10] if analysis else 'None'}, "
                                   f"indicators_1m keys: {list(indicators_1m.keys()) if indicators_1m else 'None'}, "
                                   f"analysis_1m type: {type(analysis.get('analysis_1m'))}, "
                                   f"analysis_1m rsi: {analysis_1m.get('rsi') if isinstance(analysis_1m, dict) else 'N/A'}")
                
                logger.info(f"📝 Tentative log_scan_simple pour {symbol} (prix: {scan_price}, RSI: {indicators_1m.get('rsi', 'N/A')}, Score: {score_total or 'N/A'})")
                # Construire scan_data avec tous les fallbacks possibles
                scan_data_dict = {
                    'market_data': {'price': scan_price},
                    'indicators_1m': indicators_1m,
                    'scores': {'score_total': score_total},
                    'is_opportunity': bool(analysis and 'direction' in analysis and ('entry' in analysis or 'price' in analysis)) if analysis else False
                }
                # Ajouter analysis_1m et analysis_5m si disponibles (pour les fallbacks dans SimplePGLogger)
                if analysis and isinstance(analysis, dict):
                    if 'analysis_1m' in analysis:
                        scan_data_dict['analysis_1m'] = analysis.get('analysis_1m')
                    if 'analysis_5m' in analysis:
                        scan_data_dict['analysis_5m'] = analysis.get('analysis_5m')
                    # Ajouter aussi totalScore directement si disponible
                    if 'totalScore' in analysis:
                        scan_data_dict['totalScore'] = analysis.get('totalScore')
                    # Ajouter long_score et short_score si disponibles (pour les fallbacks dans SimplePGLogger)
                    if 'long_score' in analysis:
                        scan_data_dict['long_score'] = analysis.get('long_score')
                    if 'short_score' in analysis:
                        scan_data_dict['short_score'] = analysis.get('short_score')
                result = _simple_logger.log_scan_simple(symbol, scan_data_dict)
                logger.info(f"📝 Résultat log_scan_simple pour {symbol}: {result}")
            else:
                logger.warning(f"⚠️ Simple Logger désactivé pour {symbol}")
        except Exception as e:
            logger.error(f"❌ Erreur Simple Logger pour {symbol}: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
        
        # 🔥 PHASE 1: Logger le scan dans PostgreSQL si activé (comme dans scanner_loop.py)
        try:
            from core.callbacks.scanner_loop import get_pg_datalogger
            pg_datalogger = get_pg_datalogger()
            
            if pg_datalogger and pg_datalogger.enabled:
                # Calculer durée du scan
                scan_duration_ms = int((time.time() - scan_start_time) * 1000)
                
                # Récupérer les données du scan de scalabilité depuis top_pairs
                scalability_data = {}
                # app_state est défini globalement dans main.py
                if app_state and app_state.get('top_pairs'):
                    for pair in app_state.get('top_pairs', []):
                        if pair.get('symbol') == symbol:
                            scalability_data = {
                                'recent_volume': pair.get('recentVolume'),
                                'vol5': pair.get('vol5'),
                                'vol15': pair.get('vol15'),
                                'scalability_score': pair.get('score'),
                            }
                            break
                
                # Préparer les données du scan pour PostgreSQL
                # 🔥 FIX: Récupérer le prix avec fallbacks (comme pour SimplePGLogger)
                scan_price = None
                if analysis and isinstance(analysis, dict):
                    scan_price = analysis.get('price')
                
                # Si le prix n'est pas dans analysis, essayer de le récupérer depuis price_provider
                if scan_price is None and price_provider:
                    try:
                        price_result = await price_provider.get_price(symbol)
                        # Extraire la valeur numérique si c'est un dict
                        if isinstance(price_result, dict):
                            scan_price = price_result.get('price') or price_result.get('lastPrice') or price_result.get('close')
                        else:
                            scan_price = price_result
                    except Exception as price_error:
                        logger.debug(f"⚠️ Impossible de récupérer le prix pour {symbol}: {price_error}")
                
                # Extraire la valeur numérique si scan_price est un dict
                if isinstance(scan_price, dict):
                    scan_price = scan_price.get('price') or scan_price.get('lastPrice') or scan_price.get('close') or scan_price.get('value')
                
                # Vérifier que scan_price est un nombre
                if scan_price is not None and not isinstance(scan_price, (int, float)):
                    try:
                        scan_price = float(scan_price)
                    except (ValueError, TypeError):
                        logger.warning(f"⚠️ Prix invalide pour {symbol}: {scan_price} (type: {type(scan_price)})")
                        scan_price = None
                
                scan_data = {
                    'scan_duration_ms': scan_duration_ms,
                    'market_data': {
                        'price': scan_price,
                        'spread_pct': analysis.get('spread_pct') if analysis else None,
                        'book_depth': analysis.get('book_depth') if analysis else None,
                        'balance_score': analysis.get('balance_score') if analysis else None,
                        'bid_vol': analysis.get('bid_vol') if analysis else None,
                        'ask_vol': analysis.get('ask_vol') if analysis else None,
                        'orderbook_imbalance_ratio': analysis.get('orderbook_imbalance_ratio') if analysis else None,
                        # Paramètres du scan de scalabilité
                        'recent_volume': scalability_data.get('recent_volume'),
                        'vol5': scalability_data.get('vol5'),
                        'vol15': scalability_data.get('vol15'),
                        'scalability_score': scalability_data.get('scalability_score'),
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
                    'filters': analysis.get('filters', {}) if analysis else {},
                    'scores': {
                        'score_1m': analysis.get('score_1m') if analysis else None,
                        'score_5m': analysis.get('score_5m') if analysis else None,
                        'score_total': analysis.get('score_total') if analysis else None,
                        'score_long_1m': analysis.get('score_long_1m') if analysis else None,
                        'score_short_1m': analysis.get('score_short_1m') if analysis else None,
                        'score_long_5m': analysis.get('score_long_5m') if analysis else None,
                        'score_short_5m': analysis.get('score_short_5m') if analysis else None,
                    },
                    'patterns': {
                        'pattern_1m': analysis.get('pattern_1m') if analysis else None,
                        'pattern_multi_1m': analysis.get('pattern_multi_1m') if analysis else None,
                        'pattern_5m': analysis.get('pattern_5m') if analysis else None,
                        'pattern_multi_5m': analysis.get('pattern_multi_5m') if analysis else None,
                    },
                    'use_confluence': use_confluence,
                    'confluence_met': analysis.get('confluence_met') if analysis else False,
                    'timeframes_aligned': analysis.get('timeframes_aligned') if analysis else False,
                    'trend_timeframe': trend_timeframe,
                    'trend_direction': trend_data.get('trend') if trend_data else None,  # 'trend' pas 'direction'
                    'trend_strength': None,  # trend_data.get('strength') est une chaîne ('STRONG', 'MODERATE', 'NONE'), pas un FLOAT
                    'trend_bonus': trend_data.get('bonus') if trend_data else None,
                    'divergence_detected': analysis.get('divergence_detected') if analysis else False,
                    'divergence_type': analysis.get('divergence_type') if analysis else None,
                    'divergence_bonus': analysis.get('divergence_bonus') if analysis else 0,
                    'is_opportunity': bool(analysis and 'direction' in analysis and ('entry' in analysis or 'price' in analysis)),
                    'opportunity_direction': analysis.get('direction') if analysis and 'direction' in analysis else None,
                    'reject_reason': analysis.get('reason') if analysis and 'reason' in analysis else None,
                    'reject_reason_category': analysis.get('reject_category') if analysis else None,
                    'params_snapshot': {
                        'volume_multiplier': volume_multiplier,
                        'use_confluence': use_confluence,
                        'trend_timeframe': trend_timeframe,
                        'min_score_required': TRADING_CONFIG.get('min_score_required', 7.5),
                        'min_conditions': TRADING_CONFIG.get('min_conditions', 6),
                        'use_weighted_scoring': TRADING_CONFIG.get('use_weighted_scoring', True),
                        'snr_threshold': TRADING_CONFIG.get('snr_threshold', 0.25),
                        'breakout_threshold': TRADING_CONFIG.get('breakout_threshold', 0.35),
                        'wick_ratio_max': TRADING_CONFIG.get('wick_ratio_max', 2.8),
                        'optimal_atr_min_1m': TRADING_CONFIG.get('optimal_atr_min_1m', 0.12),
                        'optimal_atr_max_1m': TRADING_CONFIG.get('optimal_atr_max_1m', 0.75),
                        'optimal_atr_min_5m': TRADING_CONFIG.get('optimal_atr_min_5m', 0.22),
                        'optimal_atr_max_5m': TRADING_CONFIG.get('optimal_atr_max_5m', 1.4),
                        'use_breakout': TRADING_CONFIG.get('use_breakout', True),
                        'use_snr': TRADING_CONFIG.get('use_snr', True),
                        'use_wick': TRADING_CONFIG.get('use_wick', True),
                        'use_divergence': TRADING_CONFIG.get('use_divergence', True),
                    }
                }
                
                # Logger le scan (mode batch par défaut)
                logger.info(f"📝 Appel log_scan() pour {symbol} (main.py)")
                scan_id = pg_datalogger.log_scan(symbol, scan_data, use_batch=True)
                logger.info(f"✅ log_scan() terminé pour {symbol} (scan_id={scan_id})")
                
                # Si c'est une opportunité, logger aussi dans opportunities
                if scan_data['is_opportunity'] and analysis:
                    opportunity_data = {
                        'status': 'PENDING',
                        'direction': analysis.get('direction'),
                        'setup_score': analysis.get('score_total') or analysis.get('totalScore'),
                        'conditions_matched': analysis.get('condition_types', []) or analysis.get('signals', []),
                        'entry_price': analysis.get('entry') or analysis.get('price'),
                        'tp_price': analysis.get('tp'),
                        'sl_price': analysis.get('sl'),
                        'tp_sl_mode': TRADING_CONFIG.get('tp_sl_mode', 'FIXE'),
                        'size_usdt': None,
                        'risk_usdt': None,
                        'reward_risk_ratio': None,
                    }
                    logger.info(f"📝 Appel log_opportunity() pour {symbol} (main.py)")
                    pg_datalogger.log_opportunity(
                        scan_id or 0,  # 0 = temporaire, sera mis à jour lors du flush
                        symbol, 
                        opportunity_data,
                        use_batch=True
                    )
                    logger.info(f"✅ log_opportunity() terminé pour {symbol}")
        except Exception as e:
            logger.error(f"❌ Erreur logging PostgreSQL pour {symbol} (main.py): {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
        
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
            except Exception as log_err:
                logger.debug(f"Impossible d'envoyer log au frontend: {log_err}")
            is_valid = False
        
        # Envoyer événement pour mettre à jour le compteur
        await ws_manager.emit('volume_validation_update', {
            'symbol': symbol,
            'valid': is_valid
        })
        
        if analysis and not (isinstance(analysis, dict) and 'reason' in analysis):
            return analysis
        return None
        
    except Exception as e:
        logger.error(f"❌ Erreur scan {symbol}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Envoyer événement pour erreur (non validé)
        await ws_manager.emit('volume_validation_update', {
            'symbol': symbol,
            'valid': False
        })
        return None


async def position_check_loop_callback():
    """Callback appelé toutes les 2 secondes pour vérifier la position"""
    init_instances()
    
    # Vérifier si on a une position active
    if not position_manager or not position_manager.active_position:
        return
    
    if not price_provider:
        return
    
    try:
        # Récupérer prix actuel
        current_price_data = await price_provider.get_price(position_manager.active_position.symbol)
        if not current_price_data:
            return
        
        current_price = current_price_data.get('lastPrice', 0) if isinstance(current_price_data, dict) else current_price_data
        
        # Check position (renvoie None ou raison de fermeture)
        close_reason = await position_manager.check_position(current_price)
        
        # 🔥 FIX: Émettre position_update même si pas de fermeture (pour affichage frontend)
        if not close_reason:
            # Calculer PnL pour affichage
            position = position_manager.active_position
            if position:
                # 🔥 FIX: Vérifier que position est un objet Position valide
                # active_position ne doit JAMAIS être une string ou dict - c'est toujours un objet Position
                if not hasattr(position, 'symbol') or not hasattr(position, 'entry'):
                    logger.error(f"❌ Position invalide: type={type(position)}, attendu Position object")
                    return
                
                if isinstance(position, dict):
                    # Si position est déjà un dict, utiliser directement
                    pnl = position_manager.pnl_calculator.calculate_pnl_percent(
                        entry=position.get('entry', 0),
                        current_price=current_price,
                        direction=position.get('direction', 'LONG')
                    )
                    pnl_usdt = position_manager.pnl_calculator.calculate_pnl_usdt(
                        position=position,
                        current_price=current_price
                    )
                    # Créer un objet position-like pour le reste du code
                    class PositionProxy:
                        def __init__(self, d):
                            self.symbol = d.get('symbol', '')
                            self.direction = d.get('direction', 'LONG')
                            self.entry = d.get('entry', 0)
                            self.sl = d.get('sl', 0)
                            self.tp = d.get('tp', 0)
                            self.size = d.get('size', 0)
                            self.break_even_set = d.get('break_even_set', False)
                            self.partial_tp_sold = d.get('partial_tp_sold', False)
                    position = PositionProxy(position)
                else:
                    # Position est un objet Position normal
                    pnl = position_manager.pnl_calculator.calculate_pnl_percent(
                        entry=position.entry,
                        current_price=current_price,
                        direction=position.direction
                    )
                    # 🔥 FIX: Calculer PnL USDT avec pnl_calculator (incluant TP partiel automatiquement)
                    position_dict = position.to_dict() if hasattr(position, 'to_dict') else {}
                    pnl_usdt = position_manager.pnl_calculator.calculate_pnl_usdt(
                        position=position_dict,
                        current_price=current_price
                    )
                
                # 🔥 FIX: Log détaillé pour debug
                logger.debug(
                    f"📊 Position check: {position.symbol} {position.direction} | "
                    f"Entry={position.entry:.6f} | Prix={current_price:.6f} | "
                    f"PnL={pnl:.2f}% | PnL USDT={pnl_usdt:.4f} | "
                    f"SL={position.sl:.6f} | TP={position.tp:.6f}"
                )
                
                # Émettre update pour le frontend
                update_data = {
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
                    'partial_tp_sold': position.partial_tp_sold
                }
                await ws_manager.emit('position_update', update_data)
                
                # 🔥 FIX: Log pour vérifier que le prix est bien émis
                logger.debug(
                    f"📡 position_update émis: {position.symbol} | "
                    f"Prix actuel: {current_price:.6f} | "
                    f"Size: {position.size:.2f} USDT | "
                    f"PnL: {pnl:.2f}% ({pnl_usdt:.2f} USDT)"
                )
        
        if close_reason:
            # Position fermée
            # 🔥 FIX: Utiliser le lock pour synchroniser la fermeture
            async with position_lock:
                result = position_manager.close_position(exit_price=current_price, reason=close_reason)
                app_state['active_position'] = None
                
                # 🔥 PHASE 4: Ajouter à l'historique et sauvegarder
                if result:
                    result['timestamp'] = datetime.now().isoformat()
                    app_state['trade_history'].append(result)
                    if len(app_state['trade_history']) > 1000:
                        app_state['trade_history'] = app_state['trade_history'][-1000:]
                    save_trade_history()
                
                # 🔥 FIX: Désactiver callback WebSocket si position fermée
                if price_provider:
                    price_provider.set_socketio_callback(None, None)
                
                # 🔥 FIX: Log pour debug
                logger.info(
                    f"🔒 Position fermée avec lock: {close_reason} | "
                    f"app_state['active_position']=None, "
                    f"position_manager.active_position={position_manager.active_position}"
                )
            
            await add_log('INFO', 'Position fermée', f"{close_reason} - PnL: {result.get('pnl_usdt', 0):.2f} USDT")
            await ws_manager.emit('position_closed', result)
            
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


async def scalability_refresh_loop_callback():
    """Callback appelé toutes les 90 secondes pour rafraîchir la liste des top pairs"""
    if not app_state['is_scanning']:
        return
    
    # 🔥 FIX: Initialiser avant de vérifier position_manager
    init_instances()
    
    # 🔥 FIX: Ne pas rafraîchir si on a une position active (pour éviter interruption du TP partiel)
    if app_state['active_position'] or (position_manager and position_manager.active_position):
        logger.info("⏸️ Scalability refresh ignoré - Position active en cours")
        return
    
    if not scanner:
        return
    
    try:
        await add_log('INFO', 'Scalability refresh', 'Rafraîchissement des top pairs...')
        
        top_pairs = await scanner.scan_top_pairs(20)
        app_state['top_pairs'] = top_pairs
        
        # 🔥 OPTIMISATION: Invalider cache quand top_pairs change
        if hasattr(app, '_top_pairs_cache'):
            app._top_pairs_cache.pop('top_pairs', None)
        
        await add_log('INFO', 'Scalability refresh', f'{len(top_pairs)} paires scalables')
        await ws_manager.emit('top_pairs_update', {'pairs': top_pairs})
        
        # 🔥 JOUR 3: Mettre à jour WebSocket avec les nouvelles top pairs
        if price_provider and top_pairs:
            # Arrêter l'ancien WebSocket
            await price_provider.stop_websocket()
            
            # Démarrer avec les nouvelles paires
            symbols = [p.get('symbol', '') for p in top_pairs[:30] if p.get('symbol')]
            if symbols:
                try:
                    await price_provider.start_websocket(symbols)
                    await add_log('INFO', 'WebSocket mis à jour', f'{len(symbols)} symboles')
                except Exception as e:
                    logger.warning(f"Erreur démarrage WebSocket: {e}")
    
    except Exception as e:
        logger.error(f"Erreur scalability refresh: {e}")
        await add_log('ERROR', 'Erreur scalability refresh', str(e))


def init_instances():
    """Initialiser les instances (après import)"""
    global scanner, analyzer, position_config, position_manager, price_provider, scheduler
    global analytics_db, notification_manager, session_id
    
    # 🔥 FIX: Configurer le logger avec WebSocket handler pour envoyer les logs au frontend
    try:
        from utils.logger import WebSocketLogHandler
        root_logger = logging.getLogger()
        # Vérifier si le handler WebSocket existe déjà
        has_ws_handler = any(isinstance(h, WebSocketLogHandler) for h in root_logger.handlers)
        if not has_ws_handler and ws_manager:
            ws_handler = WebSocketLogHandler()
            ws_handler.set_ws_manager(ws_manager)
            ws_handler.setLevel(logging.INFO)
            # Ne pas formater (garder le message brut avec emojis)
            ws_handler.setFormatter(logging.Formatter('%(message)s'))
            root_logger.addHandler(ws_handler)
            logger.info("✅ WebSocket log handler configuré")
    except Exception as e:
        logger.debug(f"Impossible de configurer WebSocket log handler: {e}")
    
    # 🔥 ARCHITECTURE V2: Initialiser Analytics DB
    if not analytics_db and AnalyticsDatabase:
        from config import ANALYTICS_DB_PATH
        import time
        
        # Créer dossier data/ si nécessaire
        os.makedirs(os.path.dirname(ANALYTICS_DB_PATH) if os.path.dirname(ANALYTICS_DB_PATH) else "data", exist_ok=True)
        
        # 🔥 ARCHITECTURE V2: AnalyticsDatabase s'initialise automatiquement dans __init__
        try:
            # Récupérer port instance pour multi-instances
            port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
            analytics_db = AnalyticsDatabase(db_path=ANALYTICS_DB_PATH, instance_port=port)
            # La DB est déjà initialisée dans __init__ (via _init_database())
            logger.info(f"✅ Analytics DB prête: {ANALYTICS_DB_PATH}")
            
            # 🔥 FIX: Réinitialiser les stats au démarrage du bot (AVANT le scan)
            if analytics_db:
                try:
                    # Vider tous les trades de la base de données pour remettre les stats à zéro
                    analytics_db.clear_all_trades()
                    # Réinitialiser aussi app_state['trade_history'] et app_state['stats']
                    app_state['trade_history'] = []
                    app_state['stats'] = {
                        'total_trades': 0,
                        'wins': 0,
                        'losses': 0,
                        'winrate': 0.0
                    }
                    logger.info("✅ Stats réinitialisées au démarrage (base de données vidée)")
                except Exception as e:
                    logger.warning(f"⚠️ Impossible de réinitialiser les stats: {e}")
        except Exception as e:
            logger.error(f"❌ Erreur init Analytics DB: {e}")
            analytics_db = None
        
        # Générer session ID unique
        if not session_id:
            session_id = f"live_{int(time.time())}"
            logger.info(f"📝 Session ID: {session_id}")
        
        # Injecter Analytics DB dans API routes
        if set_analytics_db and analytics_db:
            set_analytics_db(analytics_db)
        
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
        
        # 🔥 PHASE 3: Créer tâche périodique pour logging contexte marché
        if pg_datalogger and pg_datalogger.enabled:
            async def log_market_context_periodic():
                """Tâche périodique pour logger le contexte marché"""
                while True:
                    try:
                        await asyncio.sleep(300)  # Toutes les 5 minutes
                        if pg_datalogger and pg_datalogger.enabled:
                            try:
                                # Récupérer prix BTC/ETH
                                from api.price_provider import get_price_provider
                                price_provider = get_price_provider()
                                
                                context_data = {
                                    'btc_price': None,
                                    'eth_price': None,
                                    'global_metrics': {},
                                    'session_stats': {},
                                    'market_trend': None,
                                    'market_volatility': None,
                                    'fear_greed_index': None
                                }
                                
                                if price_provider:
                                    try:
                                        btc_price = await price_provider.get_price('BTCUSDT')
                                        eth_price = await price_provider.get_price('ETHUSDT')
                                        context_data['btc_price'] = btc_price
                                        context_data['eth_price'] = eth_price
                                    except Exception:
                                        pass
                                
                                # Récupérer stats session si disponibles
                                if hasattr(app_state, 'get'):
                                    context_data['session_stats'] = {
                                        'total_trades': app_state.get('total_trades', 0),
                                        'win_rate': app_state.get('win_rate', 0),
                                        'total_pnl': app_state.get('total_pnl', 0)
                                    }
                                
                                pg_datalogger.log_market_context(context_data)
                            except Exception as e:
                                logger.debug(f"Erreur logging contexte marché périodique: {e}")
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.warning(f"Erreur tâche contexte marché: {e}")
                        await asyncio.sleep(60)  # Attendre avant de réessayer
            
            # Démarrer la tâche périodique
            asyncio.create_task(log_market_context_periodic())
            logger.info("✅ Tâche périodique contexte marché démarrée")
            
            # 🔥 PHASE 3: Tâche périodique pour flush forcé des buffers
            async def flush_buffers_periodic():
                """Tâche périodique pour forcer le flush des buffers toutes les 30 secondes"""
                while True:
                    try:
                        await asyncio.sleep(30)  # Toutes les 30 secondes
                        if pg_datalogger and pg_datalogger.enabled:
                            try:
                                # Forcer le flush même si buffer pas plein
                                pg_datalogger._flush_buffers(force=True)
                            except Exception as e:
                                logger.debug(f"Erreur flush périodique: {e}")
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.warning(f"Erreur tâche flush périodique: {e}")
                        await asyncio.sleep(30)  # Attendre avant de réessayer
            
            # Démarrer la tâche de flush périodique
            asyncio.create_task(flush_buffers_periodic())
            logger.info("✅ Tâche périodique flush buffers démarrée (toutes les 30s)")
        
        # 🔥 Simple Logger: Initialiser SimplePGLogger pour debugging
        global _simple_logger
        try:
            from core.simple_pg_logger import SimplePGLogger
            _simple_logger = SimplePGLogger()
            if _simple_logger.enabled:
                logger.info("✅ SimplePGLogger connecté")
            else:
                logger.warning("⚠️ SimplePGLogger désactivé")
        except Exception as e:
            logger.error(f"❌ Erreur initialisation SimplePGLogger: {e}")
            _simple_logger = None
        
        # 🔥 NOUVEAU: Injecter Position Manager, Notification Manager et instance port
        # Récupérer port instance pour multi-instances
        port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
        
        if set_instance_port:
            set_instance_port(port)
    
    # 🔥 ARCHITECTURE V2: Initialiser Notification Manager
    if not notification_manager and create_notification_manager:
        from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED
        from config import NOTIFICATION_BATCHING_ENABLED, NOTIFICATION_THROTTLE_SECONDS
        
        async def websocket_callback(event_type, data):
            """Callback pour envoyer via WebSocket natif"""
            await ws_manager.emit(event_type, data)
        
        # 🔥 NOUVEAU: Récupérer port instance pour multi-instances
        port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
        
        notification_manager = create_notification_manager(
            telegram_bot_token=TELEGRAM_BOT_TOKEN,
            telegram_chat_id=TELEGRAM_CHAT_ID,
            socketio_callback=websocket_callback,  # 🔥 MIGRATION COMPLÈTE: Utiliser websocket_callback
            enable_batching=NOTIFICATION_BATCHING_ENABLED,
            instance_port=port  # 🔥 NOUVEAU: Passer instance_port
        )
        
        if TELEGRAM_ENABLED:
            logger.info(f"📱 Notification Manager initialisé (Telegram activé)")
        else:
            logger.info(f"📱 Notification Manager initialisé (Telegram désactivé)")
        
        # 🔥 NOUVEAU: Injecter Notification Manager dans API routes (pour webhook Telegram)
        if set_notification_manager and notification_manager:
            set_notification_manager(notification_manager)
    
    if not scanner and ScalabilityScanner:
        scanner = ScalabilityScanner()
    if not analyzer and TechnicalAnalyzer:
        analyzer = TechnicalAnalyzer()
    if not position_config and PositionConfig:
        # 🔥 FIX: Initialiser PositionConfig depuis TRADING_CONFIG
        from config import TRADING_CONFIG
        position_config = PositionConfig()
        
        # Configurer TP/SL mode depuis TRADING_CONFIG
        tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
        # 🔥 PHASE 7: TP_MULTI utilise aussi le mode ATR (pour calculer ATR)
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
        
        # 🔥 FIX: Configurer use_slippage_calculation depuis TRADING_CONFIG
        position_config.use_slippage_calculation = TRADING_CONFIG.get('use_slippage_calculation', True)
    
    if not position_manager and PositionManager and position_config:
        position_manager = PositionManager(position_config)
        
        # 🔥 ARCHITECTURE V2: Injecter analytics_db, notification_manager, session_id
        if analytics_db:
            position_manager.analytics_db = analytics_db
            # 🔥 FIX: Mettre à jour aussi analytics_logger.analytics_db
            if position_manager.analytics_logger:
                position_manager.analytics_logger.analytics_db = analytics_db
            logger.info("💾 Analytics DB injecté dans Position Manager et AnalyticsLogger")
        
        if session_id:
            position_manager.session_id = session_id
            logger.info(f"📝 Session ID injecté dans Position Manager: {session_id}")
        
        if notification_manager:
            position_manager.notification_manager = notification_manager
            logger.info("📢 Notification Manager injecté dans Position Manager")
        
        # 🔥 NOUVEAU: Injecter Position Manager dans API routes (pour webhook Telegram)
        if set_position_manager and position_manager:
            set_position_manager(position_manager)
    if not price_provider and get_price_provider:
        price_provider = get_price_provider()
    # 🔥 JOUR 3: Initialiser scheduler et configurer les callbacks
    if not scheduler and Scheduler:
        scheduler = Scheduler()
        # Configurer les callbacks (définis après init_instances)
        scheduler.set_scanner_callback(scanner_loop_callback)
        scheduler.set_position_check_callback(position_check_loop_callback)
        scheduler.set_scalability_refresh_callback(scalability_refresh_loop_callback)
        
        # 🔥 MIGRATION COMPLÈTE: Injecter ws_manager dans les callbacks
        try:
            from core.callbacks.scanner_loop import set_websocket_manager
            if set_websocket_manager:
                set_websocket_manager(ws_manager)
        except ImportError:
            pass  # Callback module optionnel
        
        # 🔥 FIX: Injecter ws_manager dans position_check_loop
        try:
            from core.callbacks.position_check_loop import set_websocket_manager
            if set_websocket_manager:
                set_websocket_manager(ws_manager)
        except ImportError:
            pass  # Callback module optionnel

        # 🔥 FIX BUG #14: Injecter ws_manager dans scalability_refresh
        try:
            from core.callbacks.scalability_refresh import set_websocket_manager
            if set_websocket_manager:
                set_websocket_manager(ws_manager)
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
    return JSONResponse(app_state)


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
        return JSONResponse({
            'sessions': [{
                'id': session_id or f"live_{int(time.time())}",
                'status': 'running' if app_state.get('is_scanning') else 'stopped',
                'port': current_port,
                'started_at': time.time()
            }] if session_id else []
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
        if position_manager and position_manager.active_position:
            try:
                active_position = position_manager.active_position
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
        
        # Récupérer historique trades
        trades_history = []
        if analytics_db:
            try:
                trades_history = analytics_db.get_trades(limit=50)
            except Exception as e:
                logger.error(f"❌ Erreur récupération historique analytics_db: {e}")
        
        # Fallback: utiliser app_state['trade_history']
        if not trades_history and app_state.get('trade_history'):
            trades_history = app_state['trade_history'][:50]
        
        # 🔥 NOUVEAU: Filtrer les trades par session_id actuelle (seulement cette session)
        current_session_trades = []
        if analytics_db and session_id:
            try:
                # Récupérer seulement les trades de la session actuelle
                all_trades = analytics_db.get_trades(limit=10000)
                current_session_trades = [t for t in all_trades if t.get('session_id') == session_id]
                
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
            'session_id': session_id or f"live_{int(time.time())}",  # 🔥 FIX: Fallback si session_id None
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
            'trades': current_session_trades[:50] if current_session_trades else trades_history[:50],  # 🔥 NOUVEAU: Utiliser trades de la session actuelle
            'timestamp': time.time()
        })
    except Exception as e:
        logger.error(f"❌ Erreur /api/state: {e}", exc_info=True)
        # 🔥 FIX: Retourner réponse minimale au lieu de 503
        import time
        return JSONResponse({
            'success': False,
            'error': str(e),
            'session_id': session_id or f"live_{int(time.time())}",
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
    await ws_manager.emit('scan_started', {'timestamp': time.time()})
    await ws_manager.emit('status', {'is_scanning': True})
    app_state['is_scanning'] = True
    
    # 🔥 JOUR 3: Si pas de top_pairs, faire un scan initial
    if not app_state['top_pairs']:
        await add_log('INFO', 'Scanner démarré', 'Scan initial des top pairs...')
        if scanner:
            top_pairs = await scanner.scan_top_pairs(20)
            app_state['top_pairs'] = top_pairs
            await ws_manager.emit('top_pairs_update', {'pairs': top_pairs})
            
            # Démarrer WebSocket pour les top pairs
            if price_provider and top_pairs:
                symbols = [p.get('symbol', '') for p in top_pairs[:30] if p.get('symbol')]
                if symbols:
                    try:
                        await price_provider.start_websocket(symbols)
                        await add_log('INFO', 'WebSocket démarré', f'{len(symbols)} symboles monitorés')
                    except Exception as e:
                        logger.warning(f"Erreur démarrage WebSocket: {e}")
    
    # 🔥 JOUR 3: Démarrer le scheduler
    if scheduler:
        scheduler.start()
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
    if scheduler:
        await scheduler.stop_async()
        logger.info("Scanner arrêté")
        await add_log('INFO', 'Scanner arrêté', 'Boucles automatiques désactivées')
        # 🔥 FIX: Émettre scan_complete pour mettre à jour le store frontend
        await ws_manager.emit('scan_complete', {'timestamp': time.time()})
        await ws_manager.emit('status', {'is_scanning': False})
    else:
        app_state['is_scanning'] = False
        logger.info("Scanner arrêté (sans scheduler)")
        # 🔥 FIX: Émettre scan_complete pour mettre à jour le store frontend
        await ws_manager.emit('scan_complete', {'timestamp': time.time()})
        await ws_manager.emit('status', {'is_scanning': False})
    
    return JSONResponse({'status': 'stopped'})


# 🔥 v7.0: Jour 1 - Nouveaux endpoints

@app.get("/api/scanner/top-pairs")
async def api_get_top_pairs():
    """Récupérer les top pairs"""
    return JSONResponse({'pairs': app_state['top_pairs']})


@app.post("/api/scanner/start")
async def api_scanner_start(request: Request):
    """
    ⚠️ DEPRECATED: Utiliser WebSocket command 'start_scanner' à la place
    Conservé pour compatibilité uniquement
    Démarrer scanner scalability
    """
    if app_state['is_scanning']:
        return JSONResponse({'error': 'Déjà en cours'}, status_code=400)
    
    init_instances()
    data = await request.json() if hasattr(request, 'json') else {}
    top_n = data.get('top_n', 20) if isinstance(data, dict) else 20
    
    app_state['is_scanning'] = True
    await add_log('INFO', 'Scanner démarré', f'Top {top_n} paires')
    
    # Lancer scan asynchrone
    if scanner:
        asyncio.create_task(scan_top_pairs_task(top_n))
    
    return JSONResponse({'status': 'started'})


@app.get("/api/price/{symbol}")
async def api_get_price(symbol: str):
    """Récupérer prix depuis WebSocket ou REST avec info de debug"""
    init_instances()
    if not price_provider:
        return JSONResponse({'error': 'Price provider not available'}, status_code=503)
    
    try:
        import time
        price_data = await price_provider.get_price(symbol)
        if price_data:
            # 🔥 DEBUG: Ajouter info sur la source (WebSocket ou REST)
            is_ws = (price_provider.use_websocket and 
                    price_provider.ws_manager and 
                    price_provider.ws_manager.connected)
            
            async with price_provider.cache_lock:
                from_cache = symbol in price_provider.price_cache
            
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
        
        # Vérifier état WebSocket
        if price_provider.ws_manager:
            result["websocket_connected"] = price_provider.ws_manager.connected
        
        # Récupérer tous les prix du cache
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
        logger.error(f"Erreur récupération prix live: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


@app.post("/api/websocket/start")
async def api_start_websocket():
    """
    🔥 Démarrer manuellement le WebSocket pour les top pairs
    Utile si le WebSocket n'a pas été démarré automatiquement
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
        # Récupérer les top 30 pairs
        symbols = [p.get('symbol', '') for p in app_state['top_pairs'][:30] if p.get('symbol')]
        
        if not symbols:
            return JSONResponse({'error': 'Aucun symbole valide trouvé'}, status_code=400)
        
        # Démarrer WebSocket
        await price_provider.start_websocket(symbols)
        
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
    if not analyzer:
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
        trend_data = await analyzer.calculate_trend_data(symbol, trend_timeframe)
        
        # 🔥 PHASE 6: Récupérer positions actives pour Correlation Filter
        active_positions = []
        if position_manager and position_manager.active_position:
            active_positions = [position_manager.active_position.symbol]
        
        # 🔥 FIX: Utiliser analyze_pair au lieu de analyze_symbol pour supporter confluence et volume_multiplier
        analysis = await analyzer.analyze_pair(
            symbol, 
            trend_data=trend_data,  # 🔥 Utiliser trend_data calculé
            volume_multiplier=volume_multiplier,
            use_confluence=use_confluence,
            return_reason=False,
            active_positions=active_positions,  # 🔥 PHASE 6: Correlation Filter
            position_manager=position_manager  # 🔥 PHASE 6: Recovery Mode
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
    if not position_manager:
        return JSONResponse({'error': 'Position manager not available'}, status_code=503)
    
    # 🔥 FIX: Utiliser le même lock que le scanner pour éviter les ouvertures multiples
    async with position_lock:
        # Vérifier qu'on n'a pas déjà une position active
        if app_state['active_position'] or (position_manager and position_manager.active_position):
            return JSONResponse({'error': 'Une position est déjà active'}, status_code=400)
        
        try:
            data = await request.json() if hasattr(request, 'json') else {}
            data = data if isinstance(data, dict) else {}
            
            # Vérifier données minimales
            if not data or 'symbol' not in data:
                return JSONResponse({'error': 'Missing symbol'}, status_code=400)
            
            # Double-check après avoir acquis le lock
            if app_state['active_position'] or (position_manager and position_manager.active_position):
                return JSONResponse({'error': 'Une position est déjà active (double-check)'}, status_code=400)
            
            # 🔥 FIX: Vérifier que entry est fourni et valide
            entry = data.get('entry')
            if not entry or entry <= 0:
                return JSONResponse({
                    'error': f'Entry invalide ou manquant: {entry}. Entry doit être > 0.'
                }, status_code=400)
            
            # Extraire paramètres avec valeurs par défaut
            condition_types = data.get('condition_types', [])  # 🔥 PHASE 5: Types de conditions
            position = position_manager.open_position(
                symbol=data['symbol'],
                direction=data.get('direction', 'LONG'),
                entry=float(entry),  # 🔥 FIX: S'assurer que c'est un float
                size=data.get('size', 100.0),
                atr=data.get('atr'),
                atr5m=data.get('atr5m'),
                confirmed_by=data.get('confirmed_by', ''),
                scalability_data=data.get('scalability_data'),
                condition_types=condition_types  # 🔥 PHASE 5: Types de conditions
            )
            
            # 🔥 FIX: Stocker capital si fourni dans data
            if 'capital' in data:
                position.capital = data.get('capital')
            
            app_state['active_position'] = position
            
            await add_log('INFO', 'Position ouverte', f"{data.get('direction', 'LONG')} {data['symbol']}")
            await ws_manager.emit('position_opened', position.to_dict())
            
            return JSONResponse({'status': 'opened', 'position': position.to_dict()})
        except Exception as e:
            logger.error(f"Erreur ouverture position: {e}")
            return JSONResponse({'error': str(e)}, status_code=500)


@app.get("/api/position/active")
async def api_get_active_position():
    """🔥 FIX: Récupérer position active pour restauration au refresh"""
    init_instances()
    if not position_manager or not position_manager.active_position:
        return JSONResponse({
            'success': True,
            'active': False,
            'position': None
        })
    
    position = position_manager.active_position
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
    if not position_manager or not position_manager.active_position:
        return JSONResponse({'status': 'no_position'})
    
    if not price_provider:
        return JSONResponse({'error': 'Price provider not available'}, status_code=503)
    
    try:
        # Récupérer prix actuel
        price_data = await price_provider.get_price(position_manager.active_position.symbol)
        current_price = price_data.get('lastPrice') if price_data else None
        
        if not current_price:
            return JSONResponse({'error': 'Price not available'}, status_code=500)
        
        # Check position (renvoie None ou raison de fermeture)
        result = await position_manager.check_position(current_price)
        
        # Construire réponse
        position = position_manager.active_position
        # 🔥 FIX: Utiliser pnl_calculator au lieu de _calculate_pnl
        pnl = position_manager.pnl_calculator.calculate_pnl_percent(
            entry=position.entry,
            current_price=current_price,
            direction=position.direction
        )
        # Calculer PnL USDT
        pnl_usdt = position_manager.pnl_calculator.calculate_pnl_usdt(
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
        
        await ws_manager.emit('position_update', response)
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
    async with position_lock:
        # Double-check que la position existe AVANT et APRÈS avoir acquis le lock
        if not position_manager or not position_manager.active_position:
            # Vérifier aussi dans app_state
            if not app_state.get('active_position'):
                logger.warning("⚠️ Tentative de fermeture sans position active (position_manager)")
                return JSONResponse({'error': 'No active position'}, status_code=400)
            else:
                # Position dans app_state mais pas dans position_manager - nettoyer app_state
                logger.warning("⚠️ Position dans app_state mais pas dans position_manager - nettoyage")
                app_state['active_position'] = None
                return JSONResponse({'error': 'Position state inconsistent'}, status_code=400)
        
        if not price_provider:
            return JSONResponse({'error': 'Price provider not available'}, status_code=503)
        
        try:
            # Récupérer prix actuel
            price_data = await price_provider.get_price(position_manager.active_position.symbol)
            exit_price = price_data.get('lastPrice') if price_data else None
            
            result = position_manager.close_position(exit_price=exit_price, reason='MANUAL')
            
            app_state['active_position'] = None
            
            # 🔥 PHASE 4: Ajouter à l'historique et sauvegarder
            if result:
                result['timestamp'] = datetime.now().isoformat()
                app_state['trade_history'].append(result)
                if len(app_state['trade_history']) > 1000:
                    app_state['trade_history'] = app_state['trade_history'][-1000:]
                save_trade_history()
            
            # 🔥 FIX: Désactiver callback WebSocket si position fermée
            if price_provider:
                price_provider.set_socketio_callback(None, None)
            
            logger.info(
                f"🔒 Position fermée manuellement avec lock: "
                f"app_state['active_position']=None, "
                f"position_manager.active_position={position_manager.active_position}"
            )
            
            await add_log('INFO', 'Position clôturée', 'Manuel')
            await ws_manager.emit('position_closed', result)
            
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
    if not scanner:
        return
    
    try:
        await add_log('INFO', 'Scan scalability', 'Démarrage...')
        
        top_pairs = await scanner.scan_top_pairs(n)
        app_state['top_pairs'] = top_pairs
        
        # 🔥 OPTIMISATION: Invalider cache quand top_pairs change
        if hasattr(app, '_top_pairs_cache'):
            app._top_pairs_cache.pop('top_pairs', None)
        
        await add_log('INFO', 'Scan terminé', f'{len(top_pairs)} paires scalables')
        await ws_manager.emit('top_pairs_update', {'pairs': top_pairs})
        
        # 🔥 JOUR 3: Démarrer WebSocket pour les top pairs après le scan
        if price_provider and top_pairs:
            symbols = [p.get('symbol', '') for p in top_pairs[:30] if p.get('symbol')]
            if symbols:
                try:
                    await price_provider.start_websocket(symbols)
                    await add_log('INFO', 'WebSocket démarré', f'{len(symbols)} symboles monitorés')
                except Exception as e:
                    logger.warning(f"Erreur démarrage WebSocket: {e}")
        
    except Exception as e:
        logger.error(f"Erreur scan: {e}")
        await add_log('ERROR', 'Erreur scan', str(e))
    finally:
        app_state['is_scanning'] = False


# 🔥 MIGRATION COMPLÈTE: Handlers Socket.IO supprimés - WebSocket natif uniquement
# Tous les handlers sont maintenant dans l'endpoint /ws ci-dessous


# 🔥 WebSocket Natif - Endpoint Bidirectionnel
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Endpoint WebSocket bidirectionnel natif"""
    try:
        await ws_manager.connect(websocket)
        
        # 🔥 FIX: Envoyer état initial au client avec gestion d'erreur
        try:
            status_data = app_state.copy()
            if status_data.get('active_position') and hasattr(status_data['active_position'], 'to_dict'):
                try:
                    status_data['active_position'] = status_data['active_position'].to_dict()
                except Exception as e:
                    logger.warning(f"⚠️ Erreur conversion position en dict: {e}")
                    status_data['active_position'] = None
            
            await ws_manager.send_personal_message({
                'type': 'event',
                'event': 'status',
                'data': status_data
            }, websocket)
        except Exception as e:
            logger.error(f"❌ Erreur envoi état initial: {e}")
        
        # 🔥 FIX: Envoyer les derniers logs avec gestion d'erreur
        try:
            for log_entry in app_state.get('logs', [])[-50:]:
                try:
                    await ws_manager.send_personal_message({
                        'type': 'event',
                        'event': 'log',
                        'data': log_entry
                    }, websocket)
                except Exception as e:
                    logger.debug(f"⚠️ Erreur envoi log: {e}")
                    break  # Arrêter si erreur
        except Exception as e:
            logger.error(f"❌ Erreur envoi logs: {e}")
        
        # 🔥 FIX: Émettre reset_session à chaque nouvelle connexion pour réinitialiser le frontend
        # (en plus de l'événement startup, pour les clients qui se connectent après le démarrage)
        # Toujours émettre pour s'assurer que le frontend est réinitialisé même si connecté après le démarrage
        try:
            await ws_manager.send_personal_message({
                'type': 'event',
                'event': 'reset_session',
                'data': {
                    'timestamp': time.time(),
                    'reason': 'new_connection'
                }
            }, websocket)
            logger.debug("✅ Événement reset_session envoyé à la nouvelle connexion")
        except Exception as e:
            logger.debug(f"⚠️ Erreur envoi reset_session: {e}")
        
        # Boucle bidirectionnelle : recevoir et traiter messages
        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                msg_type = message.get('type')
                
                # Traiter commandes (Frontend → Backend)
                if msg_type == 'command':
                    command = message.get('command')
                    params = message.get('params', {})
                    command_id = message.get('id')
                    
                    logger.info(f"📨 Commande reçue: {command} (ID: {command_id})")
                    
                    try:
                        result = await handle_client_command(command, params)
                        await ws_manager.send_personal_message({
                            'type': 'command_response',
                            'id': command_id,
                            'command': command,
                            'result': result,
                            'status': 'success',
                            'timestamp': time.time()
                        }, websocket)
                    except Exception as e:
                        logger.error(f"Erreur commande {command}: {e}")
                        await ws_manager.send_personal_message({
                            'type': 'command_error',
                            'id': command_id,
                            'command': command,
                            'error': str(e),
                            'timestamp': time.time()
                        }, websocket)
                
                # Heartbeat (Frontend ↔ Backend)
                elif msg_type == 'ping':
                    await ws_manager.send_personal_message({
                        'type': 'pong',
                        'timestamp': time.time()
                    }, websocket)
                
                # Subscription (Frontend → Backend)
                elif msg_type == 'subscribe':
                    channel = message.get('channel', 'all')
                    ws_manager.subscribe(websocket, channel)
                    await ws_manager.send_personal_message({
                        'type': 'subscribed',
                        'channel': channel,
                        'timestamp': time.time()
                    }, websocket)
                
                # Unsubscribe (Frontend → Backend)
                elif msg_type == 'unsubscribe':
                    channel = message.get('channel', 'all')
                    ws_manager.unsubscribe(websocket, channel)
                    await ws_manager.send_personal_message({
                        'type': 'unsubscribed',
                        'channel': channel,
                        'timestamp': time.time()
                    }, websocket)
                
                # Request (Frontend → Backend)
                elif msg_type == 'request':
                    request_type = message.get('request_type')
                    request_id = message.get('id')
                    
                    if request_type == 'logs':
                        await ws_manager.send_personal_message({
                            'type': 'request_response',
                            'id': request_id,
                            'request_type': request_type,
                            'data': app_state['logs'][-100:]
                        }, websocket)
                    
                    elif request_type == 'position':
                        if position_manager and position_manager.active_position:
                            await ws_manager.send_personal_message({
                                'type': 'request_response',
                                'id': request_id,
                                'request_type': request_type,
                                'data': position_manager.active_position.to_dict()
                            }, websocket)
                        else:
                            await ws_manager.send_personal_message({
                                'type': 'request_response',
                                'id': request_id,
                                'request_type': request_type,
                                'data': None
                            }, websocket)
                    
                    elif request_type == 'state':
                        # 🔥 MIGRATION COMPLÈTE: Récupérer état complet via WebSocket (remplace fetch('/api/state'))
                        try:
                            # Utiliser la même logique que api_get_complete_state
                            from config import TRADING_CONFIG
                            # time est déjà importé au niveau du module
                            
                            # Récupérer position active
                            active_position_dict = None
                            if position_manager and position_manager.active_position:
                                try:
                                    active_position = position_manager.active_position
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
                                    logger.error(f"❌ Erreur récupération stats: {e}")
                            
                            # Fallback app_state
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
                            
                            # Récupérer historique trades
                            trades_history = []
                            if analytics_db:
                                try:
                                    trades_history = analytics_db.get_trades(limit=50)
                                except Exception as e:
                                    logger.error(f"❌ Erreur récupération historique: {e}")
                            
                            if not trades_history and app_state.get('trade_history'):
                                trades_history = app_state['trade_history'][:50]
                            
                            # 🔥 MIGRATION COMPLÈTE: Ajouter telegram_enabled dans state
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
                                'session_id': session_id or f"live_{int(time.time())}",
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
                                    # Validation Setups
                                    'use_confluence': TRADING_CONFIG.get('use_confluence', False),
                                    'volume_multiplier': TRADING_CONFIG.get('volume_multiplier', 0.95),
                                    'min_score_required': TRADING_CONFIG.get('min_score_required', 7.5),
                                    'max_slippage_pct': TRADING_CONFIG.get('max_slippage_pct', 0.03),
                                    # TP/SL Configuration
                                    'tp_sl_mode': TRADING_CONFIG.get('tp_sl_mode', 'FIXE'),
                                    'tp_percent': TRADING_CONFIG.get('tp_percent', 0.25),
                                    'sl_percent': TRADING_CONFIG.get('sl_percent', 0.25),
                                    'break_even_trigger': TRADING_CONFIG.get('break_even_trigger', 0.3),
                                    'trailing_distance': TRADING_CONFIG.get('trailing_distance', 0.15),
                                    # Seuils & Filtres
                                    'snr_threshold': TRADING_CONFIG.get('snr_threshold', 0.25),
                                    'breakout_threshold': TRADING_CONFIG.get('breakout_threshold', 0.35),
                                    'wick_ratio_max': TRADING_CONFIG.get('wick_ratio_max', 2.8),
                                    'di_gap_min': TRADING_CONFIG.get('di_gap_min', 4.0),
                                    'di_gap_adx_threshold': TRADING_CONFIG.get('di_gap_adx_threshold', 25),
                                    'optimal_atr_min_1m': TRADING_CONFIG.get('optimal_atr_min_1m', 0.12),
                                    'optimal_atr_max_1m': TRADING_CONFIG.get('optimal_atr_max_1m', 0.75),
                                    'optimal_atr_min_5m': TRADING_CONFIG.get('optimal_atr_min_5m', 0.22),
                                    'optimal_atr_max_5m': TRADING_CONFIG.get('optimal_atr_max_5m', 1.4),
                                    'trend_timeframe': TRADING_CONFIG.get('trend_timeframe', '15m'),
                                    # Money Management
                                    'account_size': TRADING_CONFIG.get('account_size', 1000.0),
                                    'risk_per_trade': TRADING_CONFIG.get('risk_per_trade', 2.0),
                                    # Mode ATR
                                    'atr_mult_tp': TRADING_CONFIG.get('atr_mult_tp', 1.5),
                                    'atr_mult_sl': TRADING_CONFIG.get('atr_mult_sl', 1.0),
                                    'atr_min': TRADING_CONFIG.get('atr_min', 0.15),
                                    'atr_max': TRADING_CONFIG.get('atr_max', 1.5),
                                    # Mode ESCALIER
                                    'partial_tp_percent': TRADING_CONFIG.get('partial_tp_percent', 50),
                                    'escalier_level1_pnl': TRADING_CONFIG.get('escalier_level1_pnl', 0.20),
                                    'escalier_level1_size': TRADING_CONFIG.get('escalier_level1_size', 25),
                                    'escalier_level2_pnl': TRADING_CONFIG.get('escalier_level2_pnl', 0.35),
                                    'escalier_level2_size': TRADING_CONFIG.get('escalier_level2_size', 25),
                                    'escalier_level3_pnl': TRADING_CONFIG.get('escalier_level3_pnl', 0.50),
                                    'escalier_level3_size': TRADING_CONFIG.get('escalier_level3_size', 25),
                                    'escalier_level4_pnl': TRADING_CONFIG.get('escalier_level4_pnl', 0.80),
                                    'escalier_level4_size': TRADING_CONFIG.get('escalier_level4_size', 25),
                                    # Trailing Stop
                                    'trailing_enabled': TRADING_CONFIG.get('trailing_enabled', True),
                                    'trailing_trigger_pnl': TRADING_CONFIG.get('trailing_trigger_pnl', 0.25),
                                    'trailing_atr_multiplier': TRADING_CONFIG.get('trailing_atr_multiplier', 0.4),
                                    'trailing_min_distance': TRADING_CONFIG.get('trailing_min_distance', 0.08),
                                    'trailing_max_distance': TRADING_CONFIG.get('trailing_max_distance', 0.25),
                                    # Scanner
                                    'top_pairs_limit': TRADING_CONFIG.get('top_pairs_limit', 20),
                                    'balance_score_min': TRADING_CONFIG.get('balance_score_min', 0.0),
                                    # Général
                                    'use_slippage_calculation': TRADING_CONFIG.get('use_slippage_calculation', True),
                                    'position_timeout': TRADING_CONFIG.get('position_timeout', 300),
                                    'check_interval': TRADING_CONFIG.get('check_interval', 0.1),
                                    'scan_interval': TRADING_CONFIG.get('scan_interval', 45),
                                    'scalability_interval': TRADING_CONFIG.get('scalability_interval', 90),
                                    # Autres
                                    'telegram_enabled': TELEGRAM_ENABLED,  # 🔥 MIGRATION COMPLÈTE: Exposer statut Telegram
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
                                'trade_history': trades_history,
                                'timestamp': time.time()
                            }
                            
                            await ws_manager.send_personal_message({
                                'type': 'request_response',
                                'id': request_id,
                                'request_type': request_type,
                                'data': state_data
                            }, websocket)
                        except Exception as e:
                            logger.error(f"❌ Erreur récupération state via WebSocket: {e}", exc_info=True)
                            await ws_manager.send_personal_message({
                                'type': 'request_response',
                                'id': request_id,
                                'request_type': request_type,
                                'data': {
                                    'success': False,
                                    'error': str(e)
                                }
                            }, websocket)
        
        except WebSocketDisconnect:
            await ws_manager.disconnect(websocket)
        except Exception as e:
            logger.error(f"Erreur WebSocket: {e}")
            await ws_manager.disconnect(websocket)
    
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Erreur WebSocket globale: {e}")
        await ws_manager.disconnect(websocket)


# 🔥 Fonction : Traiter commandes du client
async def handle_client_command(command: str, params: dict):
    """Exécuter une commande du client via WebSocket"""
    
    if command == 'start_scanner':
        # 🔥 FIX: Dupliquer la logique de api_start (pas JSONResponse)
        init_instances()
        
        # Émettre scan_started IMMÉDIATEMENT au démarrage (avant le scan)
        await ws_manager.emit('scan_started', {'timestamp': time.time()})
        await ws_manager.emit('status', {'is_scanning': True})
        app_state['is_scanning'] = True
        
        # Si pas de top_pairs, faire un scan initial
        if not app_state['top_pairs']:
            asyncio.create_task(_run_initial_top_pairs_scan())
        
        # Démarrer le scheduler
        if scheduler:
            scheduler.start()
            logger.info("Scanner démarré")
            await add_log('INFO', 'Scanner démarré', 'Boucles automatiques activées')
        else:
            logger.info("Scanner démarré (sans scheduler)")
        
        return {'status': 'started', 'is_scanning': True}
    
    elif command == 'stop_scanner':
        # 🔥 FIX: Dupliquer la logique de api_stop (pas JSONResponse)
        init_instances()
        
        # Arrêter le scheduler
        if scheduler:
            await scheduler.stop_async()
            logger.info("Scanner arrêté")
            await add_log('INFO', 'Scanner arrêté', 'Boucles automatiques désactivées')
            # 🔥 FIX: Émettre scan_complete pour mettre à jour le store frontend
            await ws_manager.emit('scan_complete', {'timestamp': time.time()})
            await ws_manager.emit('status', {'is_scanning': False})
        else:
            app_state['is_scanning'] = False
            logger.info("Scanner arrêté (sans scheduler)")
            # 🔥 FIX: Émettre scan_complete pour mettre à jour le store frontend
            await ws_manager.emit('scan_complete', {'timestamp': time.time()})
            await ws_manager.emit('status', {'is_scanning': False})
        
        # Arrêter WebSocket
        if price_provider:
            try:
                await price_provider.stop_websocket()
                await add_log('INFO', 'WebSocket arrêté', 'Monitoring des prix désactivé')
            except Exception as e:
                logger.warning(f"Erreur arrêt WebSocket: {e}")
        
        return {'status': 'stopped', 'is_scanning': False}
    
    elif command == 'update_config':
        # 🔥 BIDIRECTIONNEL: Mettre à jour config avec validation complète (même logique que /api/config)
        from config import TRADING_CONFIG
        updated = {}
        
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
                if position_config:
                    position_config.use_atr = (mode == 'ATR' or mode == 'TP_MULTI' or mode == 'ESCALIER')
                # 🔥 FIX: Mettre à jour aussi position_manager.config.use_atr si position_manager existe
                if position_manager:
                    position_manager.config.use_atr = (mode == 'ATR' or mode == 'TP_MULTI' or mode == 'ESCALIER')
                updated['tp_sl_mode'] = mode
                logger.info(f"✅ Mode TP/SL mis à jour: {mode} (use_atr={position_config.use_atr if position_config else 'N/A'})")
        
        if 'tp_percent' in params:
            val = float(params['tp_percent'])
            TRADING_CONFIG['tp_percent'] = val
            if position_config:
                position_config.fixed_tp_pct = val
            updated['tp_percent'] = val
        
        if 'sl_percent' in params:
            val = float(params['sl_percent'])
            TRADING_CONFIG['sl_percent'] = val
            if position_config:
                position_config.fixed_sl_pct = val
            updated['sl_percent'] = val
        
        # 🔥 FIX: break_even_trigger
        if 'break_even_trigger' in params:
            val = float(params['break_even_trigger'])
            val = max(0.05, min(2.0, val))  # Clamp 0.05-2.0%
            TRADING_CONFIG['break_even_trigger'] = val
            if position_config:
                position_config.break_even_trigger = val
            updated['break_even_trigger'] = val
            logger.info(f"✅ break_even_trigger mis à jour: {val}%")
        
        # 🔥 FIX: trailing_distance
        if 'trailing_distance' in params:
            val = float(params['trailing_distance'])
            val = max(0.05, min(1.0, val))  # Clamp 0.05-1.0%
            TRADING_CONFIG['trailing_distance'] = val
            if position_config:
                position_config.trailing_distance = val
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
            updated['trailing_atr_multiplier'] = val
        
        if 'trailing_min_distance' in params:
            val = float(params['trailing_min_distance'])
            val = max(0.01, min(1.0, val))  # Clamp 0.01-1.0%
            TRADING_CONFIG['trailing_min_distance'] = val
            updated['trailing_min_distance'] = val
        
        # 🔥 FIX: use_slippage_calculation
        if 'use_slippage_calculation' in params:
            TRADING_CONFIG['use_slippage_calculation'] = bool(params['use_slippage_calculation'])
            # Mettre à jour position_config et position_manager.config directement
            if position_config:
                position_config.use_slippage_calculation = TRADING_CONFIG['use_slippage_calculation']
            if position_manager:
                position_manager.config.use_slippage_calculation = TRADING_CONFIG['use_slippage_calculation']
            updated['use_slippage_calculation'] = TRADING_CONFIG['use_slippage_calculation']
            logger.info(f"✅ use_slippage_calculation mis à jour: {TRADING_CONFIG['use_slippage_calculation']}")
        
        if 'trailing_max_distance' in params:
            val = float(params['trailing_max_distance'])
            val = max(0.01, min(5.0, val))  # Clamp 0.01-5.0%
            TRADING_CONFIG['trailing_max_distance'] = val
            updated['trailing_max_distance'] = val
        
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
            if position_config:
                position_config.atr_mult_tp = val
        
        if 'atr_mult_sl' in params:
            val = float(params['atr_mult_sl'])
            val = max(0.1, min(10.0, val))  # Clamp 0.1-10.0x
            TRADING_CONFIG['atr_mult_sl'] = val
            updated['atr_mult_sl'] = val
            if position_config:
                position_config.atr_mult_sl = val
        
        if 'atr_min' in params:
            val = float(params['atr_min'])
            val = max(0.01, min(5.0, val))  # Clamp 0.01-5.0%
            TRADING_CONFIG['atr_min'] = val
            updated['atr_min'] = val
            if position_config:
                position_config.atr_min = val
        
        if 'atr_max' in params:
            val = float(params['atr_max'])
            val = max(0.1, min(10.0, val))  # Clamp 0.1-10.0%
            TRADING_CONFIG['atr_max'] = val
            updated['atr_max'] = val
            if position_config:
                position_config.atr_max = val
        
        if updated:
            logger.info(f"✅ Config mise à jour via WebSocket: {updated}")
            await add_log('INFO', 'Config mise à jour', str(updated))
            
            # 🔥 FIX: Mettre à jour immédiatement toutes les instances qui utilisent la config
            # Mettre à jour position_config si nécessaire (sans réinitialiser complètement)
            if position_config:
                from config import TRADING_CONFIG
                # Mettre à jour les valeurs TP/SL si elles ont changé
                if 'tp_sl_mode' in updated:
                    tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
                    # 🔥 FIX: Accepter aussi 'ESCALIER' comme mode valide
                    position_config.use_atr = (tp_sl_mode == 'ATR' or tp_sl_mode == 'TP_MULTI' or tp_sl_mode == 'ESCALIER')
                    # 🔥 FIX: Mettre à jour aussi position_manager.config.use_atr si position_manager existe
                    if position_manager:
                        position_manager.config.use_atr = position_config.use_atr
                if 'tp_percent' in updated:
                    position_config.fixed_tp_pct = TRADING_CONFIG.get('tp_percent', 0.6)
                if 'sl_percent' in updated:
                    position_config.fixed_sl_pct = TRADING_CONFIG.get('sl_percent', 0.25)
                if 'atr_mult_tp' in updated:
                    position_config.atr_mult_tp = TRADING_CONFIG.get('atr_mult_tp', 1.5)
                if 'atr_mult_sl' in updated:
                    position_config.atr_mult_sl = TRADING_CONFIG.get('atr_mult_sl', 1.0)
                if 'atr_min' in updated:
                    position_config.atr_min = TRADING_CONFIG.get('atr_min', 0.15)
                if 'atr_max' in updated:
                    position_config.atr_max = TRADING_CONFIG.get('atr_max', 1.5)
            
            # 🔥 FIX: Mettre à jour aussi position_manager.tpsl_config si une position est active
            if position_manager and position_manager.active_position:
                from config import TRADING_CONFIG
                # Mettre à jour les valeurs TP/SL dans tpsl_config pour les prochaines positions
                if 'tp_percent' in updated:
                    position_manager.tpsl_config.fixed_tp_pct = TRADING_CONFIG.get('tp_percent', 0.6)
                if 'sl_percent' in updated:
                    position_manager.tpsl_config.fixed_sl_pct = TRADING_CONFIG.get('sl_percent', 0.25)
                if 'atr_mult_tp' in updated:
                    position_manager.tpsl_config.atr_mult_tp = TRADING_CONFIG.get('atr_mult_tp', 1.5)
                if 'atr_mult_sl' in updated:
                    position_manager.tpsl_config.atr_mult_sl = TRADING_CONFIG.get('atr_mult_sl', 1.0)
                if 'atr_min' in updated:
                    position_manager.tpsl_config.atr_min = TRADING_CONFIG.get('atr_min', 0.15)
                if 'atr_max' in updated:
                    position_manager.tpsl_config.atr_max = TRADING_CONFIG.get('atr_max', 1.5)
            
            # 🔥 BIDIRECTIONNEL: Émettre événement de mise à jour de config pour synchroniser le frontend
            await ws_manager.emit('config_updated', {
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
        if position_manager and position_manager.active_position:
            # 🔥 FIX: Utiliser la logique de api_close_position directement (pas JSONResponse)
            init_instances()
            
            # Utiliser le lock pour synchroniser la fermeture
            async with position_lock:
                # Double-check que la position existe
                if not position_manager or not position_manager.active_position:
                    if not app_state.get('active_position'):
                        raise ValueError('No active position')
                    else:
                        app_state['active_position'] = None
                        raise ValueError('Position state inconsistent')
                
                if not price_provider:
                    raise ValueError('Price provider not available')
                
                # Récupérer prix actuel
                price_data = await price_provider.get_price(position_manager.active_position.symbol)
                exit_price = price_data.get('lastPrice') if price_data else None
                
                # Utiliser exit_price depuis params si fourni
                if params.get('exit_price'):
                    exit_price = float(params['exit_price'])
                
                result = position_manager.close_position(exit_price=exit_price, reason=params.get('reason', 'MANUAL'))
                
                app_state['active_position'] = None
                
                # Ajouter à l'historique et sauvegarder
                if result:
                    result['timestamp'] = datetime.now().isoformat()
                    app_state['trade_history'].append(result)
                    if len(app_state['trade_history']) > 1000:
                        app_state['trade_history'] = app_state['trade_history'][-1000:]
                    save_trade_history()
                
                # Désactiver callback WebSocket
                if price_provider:
                    price_provider.set_socketio_callback(None, None)
                
                await add_log('INFO', 'Position clôturée', params.get('reason', 'MANUAL'))
                await ws_manager.emit('position_closed', result)
                
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
        
        # Recharger la config depuis les variables d'environnement
        from importlib import reload
        import config
        reload(config)
        
        # Mettre à jour notification_manager si disponible
        if notification_manager:
            from config import (
                TELEGRAM_NOTIFY_POSITION_OPENED, TELEGRAM_NOTIFY_POSITION_CLOSED,
                TELEGRAM_NOTIFY_TP_ESCALIER, TELEGRAM_NOTIFY_EARLY_INVALIDATION,
                TELEGRAM_NOTIFY_ERROR, TELEGRAM_NOTIFY_RECONNECTION,
                TELEGRAM_NOTIFY_DAILY_SUMMARY, TELEGRAM_NOTIFY_RECOVERY_MODE,
                TELEGRAM_NOTIFY_SETUP_REJECTED
            )
            # 🔥 FIX: Mettre à jour les paramètres avec les nouvelles valeurs depuis params
            notification_manager.telegram_notify_settings.update({
                'position_opened': params.get('TELEGRAM_NOTIFY_POSITION_OPENED', TELEGRAM_NOTIFY_POSITION_OPENED),
                'position_closed': params.get('TELEGRAM_NOTIFY_POSITION_CLOSED', TELEGRAM_NOTIFY_POSITION_CLOSED),
                'tp_escalier_level': params.get('TELEGRAM_NOTIFY_TP_ESCALIER', TELEGRAM_NOTIFY_TP_ESCALIER),
                'early_invalidation': params.get('TELEGRAM_NOTIFY_EARLY_INVALIDATION', TELEGRAM_NOTIFY_EARLY_INVALIDATION),
                'error': params.get('TELEGRAM_NOTIFY_ERROR', TELEGRAM_NOTIFY_ERROR),
                'reconnection': params.get('TELEGRAM_NOTIFY_RECONNECTION', TELEGRAM_NOTIFY_RECONNECTION),
                'daily_summary': params.get('TELEGRAM_NOTIFY_DAILY_SUMMARY', TELEGRAM_NOTIFY_DAILY_SUMMARY),
                'recovery_mode': params.get('TELEGRAM_NOTIFY_RECOVERY_MODE', TELEGRAM_NOTIFY_RECOVERY_MODE),
                'setup_rejected': params.get('TELEGRAM_NOTIFY_SETUP_REJECTED', TELEGRAM_NOTIFY_SETUP_REJECTED)
            })
            logger.info(f"✅ Notification Manager mis à jour: {notification_manager.telegram_notify_settings}")
        
        return {'updated': updated, 'success': True}
    
    elif command == 'test_telegram':
        # 🔥 NOUVEAU: Envoyer un message de test Telegram
        from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED
        if not TELEGRAM_ENABLED or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            return {'success': False, 'error': 'Telegram non configuré (vérifiez .env)'}
        
        try:
            if notification_manager and notification_manager.telegram_notifier:
                test_message = "🧪 **Test de notification Telegram**\n\nCe message confirme que votre configuration Telegram fonctionne correctement ! ✅"
                success = await notification_manager.telegram_notifier.send_message(test_message)
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
    
    else:
        raise ValueError(f'Commande inconnue: {command}')


# Configuration endpoints

@app.get("/api/config")
async def api_get_config():
    """Récupérer la configuration actuelle (tous les paramètres)"""
    from config import TRADING_CONFIG
    return JSONResponse({
        'volume_multiplier': TRADING_CONFIG.get('volume_multiplier', 0.95),  # 🔥 Valeur mise à jour
        'min_score_required': TRADING_CONFIG.get('min_score_required', 7.5),  # 🔥 PHASE 6: Score minimum
        'use_confluence': TRADING_CONFIG.get('use_confluence', False),
        'tp_sl_mode': TRADING_CONFIG.get('tp_sl_mode', 'FIXE'),
        'tp_percent': TRADING_CONFIG.get('tp_percent', 0.25),
        'sl_percent': TRADING_CONFIG.get('sl_percent', 0.25),
        # 🔥 4 seuils configurables - Valeurs mises à jour
        'snr_threshold': TRADING_CONFIG.get('snr_threshold', 0.25),
        'breakout_threshold': TRADING_CONFIG.get('breakout_threshold', 0.35),
        'wick_ratio_max': TRADING_CONFIG.get('wick_ratio_max', 2.8),
        'di_gap_min': TRADING_CONFIG.get('di_gap_min', 4.0),
        'di_gap_adx_threshold': TRADING_CONFIG.get('di_gap_adx_threshold', 25),
        # 🔥 Seuils ATR optimal - Valeurs mises à jour
        'optimal_atr_min_1m': TRADING_CONFIG.get('optimal_atr_min_1m', 0.12),
        'optimal_atr_max_1m': TRADING_CONFIG.get('optimal_atr_max_1m', 0.75),
        'optimal_atr_min_5m': TRADING_CONFIG.get('optimal_atr_min_5m', 0.22),
        'optimal_atr_max_5m': TRADING_CONFIG.get('optimal_atr_max_5m', 1.4),
        # 🔥 Trend timeframe
        'trend_timeframe': TRADING_CONFIG.get('trend_timeframe', '15m'),
        'account_size': TRADING_CONFIG.get('account_size', 1000.0),
        'risk_per_trade': TRADING_CONFIG.get('risk_per_trade', 2.0)
    })


@app.get("/api/config/complete")
async def api_get_complete_config():
    """
    🔥 NOUVEAU: Récupérer TOUTES les variables de configuration (TRADING_CONFIG complet)
    Utile pour vérifier toutes les variables prises en compte par le bot
    """
    from config import TRADING_CONFIG, RISK_CONFIG, CONDITION_WEIGHTS, TREND_BONUS_CONFIG
    from config import RETRY_CONFIG, CIRCUIT_BREAKER_CONFIG, WEBSOCKET_CONFIG
    
    return JSONResponse({
        'trading_config': TRADING_CONFIG,
        'risk_config': RISK_CONFIG,
        'condition_weights': CONDITION_WEIGHTS,
        'trend_bonus_config': TREND_BONUS_CONFIG,
        'retry_config': RETRY_CONFIG,
        'circuit_breaker_config': CIRCUIT_BREAKER_CONFIG,
        'websocket_config': WEBSOCKET_CONFIG,
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
                if position_config:
                    # 🔥 PHASE 7: TP_MULTI utilise aussi le mode ATR (pour calculer ATR)
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
            if position_config:
                position_config.atr_mult_tp = val
        
        if 'atr_mult_sl' in data:
            val = float(data['atr_mult_sl'])
            val = max(0.1, min(10.0, val))  # Clamp 0.1-10.0x
            TRADING_CONFIG['atr_mult_sl'] = val
            updated['atr_mult_sl'] = val
            if position_config:
                position_config.atr_mult_sl = val
        
        if 'atr_min' in data:
            val = float(data['atr_min'])
            val = max(0.01, min(5.0, val))  # Clamp 0.01-5.0%
            TRADING_CONFIG['atr_min'] = val
            updated['atr_min'] = val
            if position_config:
                position_config.atr_min = val
        
        if 'atr_max' in data:
            val = float(data['atr_max'])
            val = max(0.1, min(10.0, val))  # Clamp 0.1-10.0%
            TRADING_CONFIG['atr_max'] = val
            updated['atr_max'] = val
            if position_config:
                position_config.atr_max = val
        
        if updated:
            logger.info(f"✅ Configuration mise à jour: {updated}")
            await add_log('INFO', 'Config mise à jour', str(updated))
            # 🔥 BIDIRECTIONNEL: Émettre événement de mise à jour de config pour synchroniser le frontend
            await ws_manager.emit('config_updated', {
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
    await ws_manager.emit('log', entry)
    
    # Logger avec couleur dans la console backend
    logger.info(f"{color}[{entry['timestamp']}] {entry['level']}: {message}{reset_code}")


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
    if position_manager and position_manager.config:
        recovery_mode_active = position_manager.config.recovery_mode_active
    
    summary = DashboardSummary(
        total_trades=total_trades,
        wins=wins,
        losses=losses,
        winrate=round(winrate, 2),
        profit_total=round(profit_total, 4),
        profit_today=round(profit_today, 4),
        drawdown=round(max_dd_info.get('current_dd', 0), 2),
        drawdown_max=max_dd_info.get('max_dd', 0),
        drawdown_max_date=max_dd_info.get('max_dd_date'),
        current_peak=max_dd_info.get('current_peak', 0),
        win_streak=win_streak,
        loss_streak=loss_streak,
        recovery_mode_active=recovery_mode_active,
        equity_curve=equity_curve[-100:],
    )

    return JSONResponse(summary.model_dump())

@app.get("/api/dashboard/trades-history")
async def get_trades_history(limit: int = 50):
    """Historique des trades récents"""
    trades = app_state['trade_history']
    # Retourner les plus récents en premier
    recent_trades = list(reversed(trades[-limit:]))
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
if __name__ == '__main__':
    import uvicorn
    import socket
    
    # 🔥 PHASE 4: Charger l'historique au démarrage
    load_trade_history()
    
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
    
    try:
        # 🔥 MIGRATION COMPLÈTE: Lancer FastAPI avec WebSocket natif uniquement
        uvicorn.run(app, host='0.0.0.0', port=port, log_level="info")
    except OSError as e:
        logger.error(f"❌ Erreur binding port {port}: {e}")
        logger.error(f"Vérifiez que le port {port} n'est pas déjà utilisé")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Erreur démarrage serveur: {e}", exc_info=True)
        sys.exit(1)
