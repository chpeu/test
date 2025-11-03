#!/usr/bin/env python3
"""
Trade Cursor v7.0 - Application FastAPI (async natif)
Interface HTML identique à v5.1 avec backend Python
"""

import sys
import asyncio
import logging
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
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
except ImportError as e:
    logging.error(f"Import error: {e}")
    # Fallback pour les dépendances manquantes
    get_price_provider = None
    ScalabilityScanner = None
    TechnicalAnalyzer = None
    PositionManager = None
    PositionConfig = None
    Scheduler = None
    get_metrics_collector = None

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialisation FastAPI
app = FastAPI(title="Trade Cursor v7.0")
templates = Jinja2Templates(directory="templates")

# SocketIO
# 🔥 FIX: Utiliser async_mode='asgi' pour compatibilité avec Uvicorn
sio = socketio.AsyncServer(cors_allowed_origins="*", async_mode='asgi')
socketio_app = socketio.ASGIApp(sio, app)

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
    'logs': []
}

# 🔥 v7.0: Instances globales (lazy init)
scanner = None
analyzer = None
position_config = None
position_manager = None
price_provider = None
scheduler = None


# 🔥 JOUR 3: Callbacks pour le scheduler (doivent être définis avant init_instances)

async def scanner_loop_callback():
    """Callback appelé toutes les 45 secondes pour scanner les setups"""
    global price_provider  # 🔥 FIX: Utiliser variable globale
    
    init_instances()
    
    # Ne pas scanner si on a déjà une position active
    if app_state['active_position'] or (position_manager and position_manager.active_position):
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
            
            # Compter les résultats
            valid_setups = 0
            no_setup = 0
            errors = 0
            
            for result in results:
                if isinstance(result, Exception):
                    errors += 1
                elif result:
                    valid_setups += 1
                else:
                    no_setup += 1
            
            # 🔥 FIX: Envoyer stats volume au frontend pour mettre à jour le compteur
            total_analyzed = len(results)
            validated_count = valid_setups
            # Émettre événement SocketIO pour mettre à jour les stats côté frontend
            await sio.emit('volume_stats_update', {
                'total': total_analyzed,
                'validated': validated_count,
                'ratio': (validated_count / total_analyzed * 100) if total_analyzed > 0 else 0
            })
            
            # Log résumé
            await add_log('INFO', 'Résumé scan', 
                f'{valid_setups} setups valides, {no_setup} sans setup, {errors} erreurs')
            
            # Si on a trouvé un setup valide, ouvrir la position
            if valid_setups > 0:
                for result in results:
                    if result and not isinstance(result, Exception):
                        # 🔥 FIX: Ouvrir position automatiquement
                        setup = result
                        symbol = setup.get('symbol', '')
                        direction = setup.get('direction', 'LONG')
                        
                        await add_log('INFO', 'Setup trouvé', 
                            f"{symbol} - {direction} - {len(setup.get('signals', []))} conditions")
                        
                        # Vérifier qu'on n'a pas déjà une position
                        if app_state['active_position'] or (position_manager and position_manager.active_position):
                            await add_log('WARNING', 'Position déjà active', 
                                'Un setup a été trouvé mais une position est déjà ouverte')
                            break
                        
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
                            if tp_sl_mode == 'ATR' and atr and entry_price:
                                sl_percent = (atr / entry_price) * 100
                                # Clamp selon config
                                atr_min = TRADING_CONFIG.get('atr_min', 0.15)
                                atr_max = TRADING_CONFIG.get('atr_max', 1.5)
                                sl_percent = max(atr_min, min(atr_max, sl_percent))
                            else:
                                sl_percent = TRADING_CONFIG.get('sl_percent', 0.25)
                            
                            # Position size = Capital × Risk% / SL%
                            if sl_percent > 0:
                                position_size = (account_size * risk_per_trade) / (sl_percent / 100)
                            else:
                                position_size = account_size * risk_per_trade  # Fallback
                            
                            # Récupérer scalability_data pour slippage
                            scalability_data = None
                            if app_state['top_pairs']:
                                for pair in app_state['top_pairs']:
                                    if pair.get('symbol') == symbol:
                                        scalability_data = pair
                                        break
                            
                            # Ouvrir la position
                            position = position_manager.open_position(
                                symbol=symbol,
                                direction=direction,
                                entry=entry_price,
                                size=position_size,
                                atr=atr,
                                atr5m=atr5m,
                                confirmed_by=setup.get('confirmedBy', 'Scanner auto'),
                                scalability_data=scalability_data
                            )
                            
                            # Stocker capital
                            position.capital = account_size
                            
                            # Mettre à jour app_state
                            app_state['active_position'] = position
                            
                            # Logger et notifier
                            await add_log('INFO', 'Position ouverte automatiquement', 
                                f"{direction} {symbol} @ {entry_price:.6f} | Size: {position_size:.2f} USDT")
                            await sio.emit('position_opened', position.to_dict())
                            
                            logger.info(
                                f"🟢 POSITION OUVERTE (Auto): {direction} {symbol} | "
                                f"Entry: {entry_price:.6f} | Size: {position_size:.2f} USDT | "
                                f"SL: {position.sl:.6f} | TP: {position.tp:.6f}"
                            )
                            
                            # Ne prendre que le premier setup valide
                            break
                            
                        except Exception as e:
                            logger.error(f"❌ Erreur ouverture position auto pour {symbol}: {e}")
                            import traceback
                            logger.error(f"Traceback: {traceback.format_exc()}")
                            await add_log('ERROR', 'Erreur ouverture position', f"{symbol}: {str(e)}")
                            continue
            else:
                await add_log('INFO', 'Aucun setup', 
                    'Aucun setup valide trouvé sur les paires analysées')


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
        
        # 🔥 FIX: Analyser avec retour de raison si pas de setup + paramètres configurables
        analysis = await analyzer.analyze_pair(
            symbol, 
            trend_data=None,
            volume_multiplier=volume_multiplier,
            use_confluence=use_confluence,
            return_reason=True
        )
        
        if analysis:
            if isinstance(analysis, dict) and 'reason' in analysis:
                # C'est une raison de rejet, pas un setup
                reason = analysis.get('reason', 'Inconnu')
                logger.info(f"❌ {symbol}: Pas de setup - {reason}")
                return None
            else:
                # C'est un vrai setup
                logger.info(f"✅ {symbol}: Setup trouvé - {analysis.get('direction', 'N/A')} - {len(analysis.get('signals', []))} conditions")
                return analysis
        else:
            # Si analysis est None, c'est que les deux timeframes ont retourné None
            logger.warning(f"⚠️ {symbol}: Analyse retournée None - Vérifier les erreurs dans analyze_timeframe")
            return None
    except Exception as e:
        logger.error(f"❌ Erreur scan {symbol}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
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
        
        if close_reason:
            # Position fermée
            result = position_manager.close_position(close_reason, exit_price=current_price)
            app_state['active_position'] = None
            
            await add_log('INFO', 'Position fermée', f"{close_reason} - PnL: {result.get('pnl_usdt', 0):.2f} USDT")
            await sio.emit('position_closed', result)
            
            # Mettre à jour stats
            if result.get('pnl_usdt', 0) > 0:
                app_state['stats']['wins'] += 1
            else:
                app_state['stats']['losses'] += 1
            app_state['stats']['total_trades'] += 1
            total = app_state['stats']['total_trades']
            if total > 0:
                app_state['stats']['winrate'] = (app_state['stats']['wins'] / total) * 100
            
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
    
    # Ne pas rafraîchir si on a une position active
    if app_state['active_position'] or (position_manager and position_manager.active_position):
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
        position_config.use_atr = (tp_sl_mode == 'ATR')
        
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
    volume_multiplier: float = Query(None, description="Multiplicateur de volume 0.1-2.0")
):
    """
    Analyser un symbole avec paramètres configurables
    
    Args:
        symbol: Symbole de la paire
        tf: Timeframe (1m ou 5m) - pour compatibilité, mais utilise analyze_pair maintenant
        use_confluence: True = 1m ET 5m, False = 1m OU 5m (défaut: depuis TRADING_CONFIG)
        volume_multiplier: Multiplicateur de volume 0.1-2.0 (défaut: depuis TRADING_CONFIG)
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
        
        # 🔥 FIX: Utiliser analyze_pair au lieu de analyze_symbol pour supporter confluence et volume_multiplier
        analysis = await analyzer.analyze_pair(
            symbol, 
            trend_data=None,
            volume_multiplier=volume_multiplier,
            use_confluence=use_confluence,
            return_reason=False
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
    
    try:
        data = await request.json() if hasattr(request, 'json') else {}
        data = data if isinstance(data, dict) else {}
        
        # Vérifier données minimales
        if not data or 'symbol' not in data:
            return JSONResponse({'error': 'Missing symbol'}, status_code=400)
        
        # Extraire paramètres avec valeurs par défaut
        position = position_manager.open_position(
            symbol=data['symbol'],
            direction=data.get('direction', 'LONG'),
            entry=data.get('entry', 0.0),
            size=data.get('size', 100.0),
            atr=data.get('atr'),
            atr5m=data.get('atr5m'),
            confirmed_by=data.get('confirmed_by', ''),
            scalability_data=data.get('scalability_data')
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
        response = {
            'status': 'position_active',
            'symbol': position_manager.active_position.symbol,
            'current_price': current_price,
            'pnl': position_manager._calculate_pnl(current_price)
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
    if not position_manager or not position_manager.active_position:
        return JSONResponse({'error': 'No active position'}, status_code=400)
    
    if not price_provider:
        return JSONResponse({'error': 'Price provider not available'}, status_code=503)
    
    try:
        # Récupérer prix actuel
        price_data = await price_provider.get_price(position_manager.active_position.symbol)
        exit_price = price_data.get('lastPrice') if price_data else None
        
        result = position_manager.close_position('MANUAL', exit_price=exit_price)
        
        app_state['active_position'] = None
        
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
    await sio.emit('status', app_state, room=sid)
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
        'volume_multiplier': TRADING_CONFIG.get('volume_multiplier', 1.0),
        'use_confluence': TRADING_CONFIG.get('use_confluence', False),
        'tp_sl_mode': TRADING_CONFIG.get('tp_sl_mode', 'FIXE'),
        'tp_percent': TRADING_CONFIG.get('tp_percent', 0.25),
        'sl_percent': TRADING_CONFIG.get('sl_percent', 0.25),
        # 🔥 4 seuils configurables
        'snr_threshold': TRADING_CONFIG.get('snr_threshold', 0.3),
        'breakout_threshold': TRADING_CONFIG.get('breakout_threshold', 0.3),
        'wick_ratio_max': TRADING_CONFIG.get('wick_ratio_max', 2.5),
        'di_gap_min': TRADING_CONFIG.get('di_gap_min', 5),
        'di_gap_adx_threshold': TRADING_CONFIG.get('di_gap_adx_threshold', 25)
    })


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
            mode = data['tp_sl_mode']
            if mode in ['FIXE', 'ATR']:
                TRADING_CONFIG['tp_sl_mode'] = mode
                # Mettre à jour PositionConfig si position_manager existe
                init_instances()
                if position_config:
                    position_config.use_atr = (mode == 'ATR')
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

if __name__ == '__main__':
    import uvicorn
    
    # Récupérer le port depuis les arguments (défaut: 5000)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    
    logger.info("🚀 Trade Cursor v7.0 démarré")
    logger.info("📊 FastAPI (async natif) + WebSocket")
    logger.info(f"🌐 Ouvez http://localhost:{port} dans votre navigateur")
    
    # Lancer FastAPI avec SocketIO
    uvicorn.run(socketio_app, host='0.0.0.0', port=port, log_level="info")
