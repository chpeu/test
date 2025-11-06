#!/usr/bin/env python3
"""
Trade Cursor v7.0 - Application FastAPI (async natif)
Interface HTML identique à v5.1 avec backend Python
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
    from api.routes import router as api_router, set_analytics_db
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

# Initialisation FastAPI
app = FastAPI(title="Trade Cursor v7.0")
templates = Jinja2Templates(directory="templates")

# 🔥 ARCHITECTURE V2: Monter fichiers statiques et inclure routes API
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    logger.info("✅ Fichiers statiques montés: /static")
except Exception as e:
    logger.warning(f"⚠️ Fichiers statiques non montés: {e}")

if api_router:
    app.include_router(api_router)
    logger.info("✅ API REST routes incluses: /api/*")

# SocketIO
# 🔥 FIX: Utiliser async_mode='asgi' pour compatibilité avec Uvicorn
sio = socketio.AsyncServer(cors_allowed_origins="*", async_mode='asgi')
socketio_app = socketio.ASGIApp(sio, app)

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
    'trade_history': []  # 🔥 PHASE 4: Historique des trades
}

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
                
                await sio.emit('top_pairs_update', {'pairs': top_pairs})
                
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
            
            # 🔥 WARNING si moins de paires que prévu
            if total_available < max_pairs:
                await add_log('WARNING', 'Paires limitées', 
                    f'Seulement {total_available} paires disponibles (attendu: {max_pairs})')
            
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
                await sio.emit('volume_stats_update', {
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
                                    position_size = position_manager.calculate_adaptive_position_size(
                                        setup=setup,
                                        capital=account_size,
                                        sl_percent=sl_percent
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
                                    if app_state['top_pairs']:
                                        for pair in app_state['top_pairs']:
                                            if pair.get('symbol') == symbol:
                                                scalability_data = pair
                                                break
                                    
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
                                    
                                    # 🔥 FIX: Émettre l'événement UNE SEULE FOIS
                                    await sio.emit('position_opened', position.to_dict())
                                    
                                    # 🔥 FIX: Émettre immédiatement le prix actuel pour l'affichage frontend
                                    try:
                                        current_price_data = await price_provider.get_price(symbol)
                                        if current_price_data:
                                            current_price = current_price_data.get('lastPrice', entry_price) if isinstance(current_price_data, dict) else entry_price
                                            pnl = position_manager._calculate_pnl(current_price)
                                            pnl_pct = pnl / 100
                                            pnl_usdt = position.size * pnl_pct * (current_price / position.entry)
                                            
                                            await sio.emit('position_update', {
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
                                        logger.warning(f"⚠️ Erreur émission prix initial: {e}")
                                    
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
    init_instances()
    
    if not analyzer:
        logger.warning(f"Analyzer non disponible pour {symbol}")
        return None
    
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
            logger.warning(f"⚠️ {symbol}: Analyse retournée None - Vérifier les erreurs dans analyze_timeframe")
            is_valid = False
        
        # Envoyer événement pour mettre à jour le compteur
        await sio.emit('volume_validation_update', {
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
        await sio.emit('volume_validation_update', {
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
                pnl = position_manager._calculate_pnl(current_price)
                # 🔥 FIX: Calculer PnL USDT correctement selon direction (incluant TP partiel)
                pnl_pct = pnl / 100  # Convertir % en décimal
                
                # Taille de position à considérer (50% si TP partiel vendu)
                size_to_consider = position.size
                partial_profit_usdt = 0.0
                if hasattr(position, 'partial_tp_sold') and position.partial_tp_sold:
                    size_to_consider = getattr(position, 'size_remaining', position.size * 0.5)
                    partial_profit_usdt = getattr(position, 'partial_profit_usdt', 0.0)
                
                # 🔥 FIX: Calculer PnL USDT correctement (comme dans position_manager)
                if position.direction == 'LONG':
                    # LONG: profit quand prix monte
                    price_diff = current_price - position.entry
                    pnl_usdt = size_to_consider * (price_diff / position.entry)
                else:  # SHORT
                    # SHORT: profit quand prix baisse
                    price_diff = position.entry - current_price
                    pnl_usdt = size_to_consider * (price_diff / position.entry)
                
                # Ajouter le profit du TP partiel si vendu
                pnl_usdt += partial_profit_usdt
                
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
                await sio.emit('position_update', update_data)
                
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
                result = position_manager.close_position(close_reason, exit_price=current_price)
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
            await sio.emit('position_closed', result)
            
            # 🔥 FIX: Ne PAS mettre à jour les stats ici - elles sont gérées dans le frontend
            # pour éviter le double comptage. Le frontend reçoit position_closed et incrémente les stats.
            # Les stats backend (app_state['stats']) sont utilisées pour autre chose si nécessaire.
            
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
        await sio.emit('top_pairs_update', {'pairs': top_pairs})
        
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
    
    # 🔥 ARCHITECTURE V2: Initialiser Notification Manager
    if not notification_manager and create_notification_manager:
        from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED
        from config import NOTIFICATION_BATCHING_ENABLED, NOTIFICATION_THROTTLE_SECONDS
        
        async def socketio_callback(event_type, data):
            """Callback pour envoyer via SocketIO"""
            await sio.emit(event_type, data)
        
        notification_manager = create_notification_manager(
            telegram_bot_token=TELEGRAM_BOT_TOKEN,
            telegram_chat_id=TELEGRAM_CHAT_ID,
            socketio_callback=socketio_callback,
            enable_batching=NOTIFICATION_BATCHING_ENABLED
        )
        
        if TELEGRAM_ENABLED:
            logger.info(f"📱 Notification Manager initialisé (Telegram activé)")
        else:
            logger.info(f"📱 Notification Manager initialisé (Telegram désactivé)")
    
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
    
    if not position_manager and PositionManager and position_config:
        position_manager = PositionManager(position_config)
        
        # 🔥 ARCHITECTURE V2: Injecter analytics_db, notification_manager, session_id
        if analytics_db:
            position_manager.analytics_db = analytics_db
            logger.info("💾 Analytics DB injecté dans Position Manager")
        
        if session_id:
            position_manager.session_id = session_id
            logger.info(f"📝 Session ID injecté dans Position Manager: {session_id}")
        
        if notification_manager:
            position_manager.notification_manager = notification_manager
            logger.info("📢 Notification Manager injecté dans Position Manager")
    if not price_provider and get_price_provider:
        price_provider = get_price_provider()
    # 🔥 JOUR 3: Initialiser scheduler et configurer les callbacks
    if not scheduler and Scheduler:
        scheduler = Scheduler()
        # Configurer les callbacks (définis après init_instances)
        scheduler.set_scanner_callback(scanner_loop_callback)
        scheduler.set_position_check_callback(position_check_loop_callback)
        scheduler.set_scalability_refresh_callback(scalability_refresh_loop_callback)


# Routes FastAPI

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Page principale - HTML copié de v5.1"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/favicon.ico")
async def favicon():
    """Favicon (évite 404)"""
    from fastapi.responses import Response
    # Retourner un favicon vide (1x1 pixel transparent)
    # En production, tu peux ajouter un vrai favicon.ico dans static/
    return Response(content=b'', media_type='image/x-icon')


@app.get("/dashboard/charts", response_class=HTMLResponse)
async def dashboard_charts(request: Request):
    """🔥 ARCHITECTURE V2: Dashboard graphiques avec Chart.js"""
    try:
        return templates.TemplateResponse("dashboard_charts.html", {"request": request})
    except Exception as e:
        logger.error(f"❌ Erreur dashboard: {e}")
        return HTMLResponse(f"<h1>Erreur</h1><p>{e}</p>", status_code=500)


@app.get("/api/status")
async def api_status():
    """État global de l'application"""
    return JSONResponse(app_state)


@app.post("/api/start")
async def api_start():
    """Démarrer le scanner et le scheduler"""
    init_instances()
    
    # 🔥 JOUR 3: Si pas de top_pairs, faire un scan initial
    if not app_state['top_pairs']:
        await add_log('INFO', 'Scanner démarré', 'Scan initial des top pairs...')
        if scanner:
            top_pairs = await scanner.scan_top_pairs(20)
            app_state['top_pairs'] = top_pairs
            await sio.emit('top_pairs_update', {'pairs': top_pairs})
            
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
        await sio.emit('status', {'is_scanning': True})
    else:
        app_state['is_scanning'] = True
        logger.info("Scanner démarré (sans scheduler)")
        await sio.emit('status', {'is_scanning': True})
    
    return JSONResponse({'status': 'started'})


@app.post("/api/stop")
async def api_stop():
    """Arrêter le scanner et le scheduler"""
    init_instances()
    
    # 🔥 JOUR 3: Arrêter le scheduler
    if scheduler:
        await scheduler.stop_async()
        logger.info("Scanner arrêté")
    
    app_state['is_scanning'] = False
    await sio.emit('status', {'is_scanning': False})
    return JSONResponse({'status': 'stopped'})


# 🔥 v7.0: Jour 1 - Nouveaux endpoints

@app.get("/api/state")
async def api_get_state():
    """Récupérer l'état complet de l'application"""
    return JSONResponse(app_state)


@app.get("/api/scanner/top-pairs")
async def api_get_top_pairs():
    """Récupérer les top pairs"""
    return JSONResponse({'pairs': app_state['top_pairs']})


@app.post("/api/scanner/start")
async def api_scanner_start(request: Request):
    """Démarrer scanner scalability"""
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
            await sio.emit('position_opened', position.to_dict())
            
            return JSONResponse({'status': 'opened', 'position': position.to_dict()})
        except Exception as e:
            logger.error(f"Erreur ouverture position: {e}")
            return JSONResponse({'error': str(e)}, status_code=500)


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
        pnl = position_manager._calculate_pnl(current_price)
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
            # Position à fermer
            response['close_reason'] = result
        
        await sio.emit('position_update', response)
        return JSONResponse(response)
    except Exception as e:
        logger.error(f"Erreur check position: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


@app.post("/api/position/close")
async def api_close_position():
    """Clôturer position manuellement"""
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
            
            result = position_manager.close_position('MANUAL', exit_price=exit_price)
            
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
            await sio.emit('position_closed', result)
            
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
        await sio.emit('top_pairs_update', {'pairs': top_pairs})
        
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


# SocketIO Handlers

@sio.on('connect')
async def handle_connect(sid, environ):
    """Connexion WebSocket"""
    logger.info("Client connecté")
    # 🔥 FIX: Convertir active_position en dict pour sérialisation JSON
    status_data = app_state.copy()
    if status_data.get('active_position') and hasattr(status_data['active_position'], 'to_dict'):
        status_data['active_position'] = status_data['active_position'].to_dict()
    await sio.emit('status', status_data, room=sid)
    # Envoyer les derniers logs
    for log_entry in app_state['logs'][-50:]:
        await sio.emit('log', log_entry, room=sid)


@sio.on('disconnect')
async def handle_disconnect(sid):
    """Déconnexion WebSocket"""
    logger.info("Client déconnecté")


@sio.on('request_logs')
async def handle_logs_request(sid):
    """Demander les logs"""
    await sio.emit('logs', app_state['logs'][-100:], room=sid)


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


@app.get("/api/metrics/conditions")
async def get_condition_metrics():
    """Métriques par condition"""
    from core.metrics import condition_metrics
    
    stats = condition_metrics.get_stats_summary()
    return JSONResponse(stats)

@app.post("/api/config")
async def api_update_config(request: Request):
    """Modifier la configuration à la volée (tous les paramètres)"""
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
        
        if updated:
            logger.info(f"✅ Configuration mise à jour: {updated}")
            await add_log('INFO', 'Config mise à jour', str(updated))
            return JSONResponse({'status': 'updated', 'updated': updated})
        else:
            return JSONResponse({'status': 'no_changes', 'message': 'Aucun paramètre valide fourni'})
    
    except Exception as e:
        logger.error(f"Erreur mise à jour config: {e}")
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
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

if __name__ == '__main__':
    import uvicorn
    
    # 🔥 PHASE 4: Charger l'historique au démarrage
    load_trade_history()
    
    # Récupérer le port depuis les arguments (défaut: 5000)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    
    logger.info("🚀 Trade Cursor v7.0 démarré")
    logger.info("📊 FastAPI (async natif) + WebSocket")
    logger.info("")
    logger.info("=" * 70)
    logger.info("📍 URLs DISPONIBLES (Instance Port: {})".format(port))
    logger.info("=" * 70)
    logger.info(f"🏠 Interface principale      → http://localhost:{port}/")
    logger.info(f"📊 Dashboard graphiques      → http://localhost:{port}/dashboard/charts")
    logger.info(f"💚 API Health check          → http://localhost:{port}/api/health")
    logger.info(f"📈 API Stats                 → http://localhost:{port}/api/stats")
    logger.info(f"📋 API Trades (filtres)      → http://localhost:{port}/api/trades?limit=10")
    logger.info(f"❌ API Setups rejetés        → http://localhost:{port}/api/setups/rejected")
    logger.info(f"✅ API Setups validés        → http://localhost:{port}/api/setups/validated")
    logger.info(f"📥 API Export (CSV/JSON)     → http://localhost:{port}/api/export?format=csv")
    logger.info(f"🔄 API Backtest              → POST http://localhost:{port}/api/backtest")
    logger.info(f"🤖 API ML Optimize           → POST http://localhost:{port}/api/optimize")
    logger.info("=" * 70)
    logger.info("")
    
    # Lancer FastAPI avec SocketIO
    uvicorn.run(socketio_app, host='0.0.0.0', port=port, log_level="info")
