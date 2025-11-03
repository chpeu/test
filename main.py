#!/usr/bin/env python3
"""
Trade Cursor v7.0 - Application FastAPI (async natif)
Interface HTML identique à v5.1 avec backend Python
"""

import sys
import asyncio
import logging
from fastapi import FastAPI, Request
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
except ImportError as e:
    logging.error(f"Import error: {e}")
    # Fallback pour les dépendances manquantes
    get_price_provider = None
    ScalabilityScanner = None
    TechnicalAnalyzer = None
    PositionManager = None
    PositionConfig = None

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
sio = socketio.AsyncServer(cors_allowed_origins="*")
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


def init_instances():
    """Initialiser les instances (après import)"""
    global scanner, analyzer, position_config, position_manager, price_provider
    if not scanner and ScalabilityScanner:
        scanner = ScalabilityScanner()
    if not analyzer and TechnicalAnalyzer:
        analyzer = TechnicalAnalyzer()
    if not position_config and PositionConfig:
        position_config = PositionConfig()
    if not position_manager and PositionManager and position_config:
        position_manager = PositionManager(position_config)
    if not price_provider and get_price_provider:
        price_provider = get_price_provider()


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
    """Démarrer le scanner"""
    if app_state['is_scanning']:
        return JSONResponse({'error': 'Déjà en cours'}, status_code=400)
    
    app_state['is_scanning'] = True
    logger.info("Scanner démarré")
    await sio.emit('status', {'is_scanning': True})
    
    return JSONResponse({'status': 'started'})


@app.post("/api/stop")
async def api_stop():
    """Arrêter le scanner"""
    app_state['is_scanning'] = False
    logger.info("Scanner arrêté")
    await sio.emit('status', {'is_scanning': False})
    return JSONResponse({'status': 'stopped'})


# 🔥 v7.0: Jour 1 - Nouveaux endpoints

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
    """Récupérer prix depuis WebSocket ou REST"""
    init_instances()
    if not price_provider:
        return JSONResponse({'error': 'Price provider not available'}, status_code=503)
    
    try:
        price_data = await price_provider.get_price(symbol)
        if price_data:
            return JSONResponse(price_data)
        return JSONResponse({'error': 'Price not available'}, status_code=404)
    except Exception as e:
        logger.error(f"Erreur prix {symbol}: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


@app.get("/api/analyze/{symbol}")
async def api_analyze_symbol(symbol: str, tf: str = '1m'):
    """Analyser un symbole"""
    init_instances()
    if not analyzer:
        return JSONResponse({'error': 'Analyzer not available'}, status_code=503)
    
    try:
        analysis = await analyzer.analyze_symbol(symbol, tf)
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
        
        await add_log('INFO', 'Scan terminé', f'{len(top_pairs)} paires scalables')
        await sio.emit('top_pairs_update', {'pairs': top_pairs})
        
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
