#!/usr/bin/env python3
"""
Trade Cursor v7.0 - Application Quart (async Flask)
Interface HTML identique à v5.1 avec backend Python
"""

import sys
import asyncio
import logging
from quart import Quart, render_template, jsonify, request
from quart_socketio import SocketIO, emit
import json
from datetime import datetime
from pathlib import Path

# 🔥 v7.0: Imports complets
from api.price_provider import get_price_provider
from core.scanner import ScalabilityScanner
from core.analyzer import TechnicalAnalyzer
from core.position_manager import PositionManager, PositionConfig

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 🔥 v7.0: Instances globales
scanner = ScalabilityScanner()
analyzer = TechnicalAnalyzer()
position_config = PositionConfig()
position_manager = PositionManager(position_config)
price_provider = get_price_provider()

# Initialisation Quart + SocketIO
app = Quart(__name__)
app.config['SECRET_KEY'] = 'trade-cursor-secret-key-2024'
socketio = SocketIO(app, cors_allowed_origins="*")

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

# Routes Quart

@app.route('/')
async def index():
    """Page principale - HTML copié de v5.1"""
    return await render_template('index.html')


@app.route('/api/status')
async def api_status():
    """État global de l'application"""
    return jsonify(app_state)


@app.route('/api/start', methods=['POST'])
async def api_start():
    """Démarrer le scanner"""
    if app_state['is_scanning']:
        return jsonify({'error': 'Déjà en cours'}), 400
    
    app_state['is_scanning'] = True
    logger.info("Scanner démarré")
    await socketio.emit('status', {'is_scanning': True})
    
    # TODO: Lancer le scanner asynchrone
    # asyncio.create_task(start_scanner())
    
    return jsonify({'status': 'started'})


@app.route('/api/stop', methods=['POST'])
async def api_stop():
    """Arrêter le scanner"""
    app_state['is_scanning'] = False
    logger.info("Scanner arrêté")
    await socketio.emit('status', {'is_scanning': False})
    return jsonify({'status': 'stopped'})


# 🔥 v7.0: Jour 1 - Nouveaux endpoints

@app.route('/api/scanner/top-pairs', methods=['GET'])
async def api_get_top_pairs():
    """Récupérer les top pairs"""
    return jsonify({'pairs': app_state['top_pairs']})


@app.route('/api/scanner/start', methods=['POST'])
async def api_scanner_start():
    """Démarrer scanner scalability"""
    if app_state['is_scanning']:
        return jsonify({'error': 'Déjà en cours'}), 400
    
    data = await request.get_json() or {}
    top_n = data.get('top_n', 20)
    
    app_state['is_scanning'] = True
    await add_log('INFO', 'Scanner démarré', f'Top {top_n} paires')
    
    # Lancer scan asynchrone
    asyncio.create_task(scan_top_pairs_task(top_n))
    
    return jsonify({'status': 'started'})


@app.route('/api/price/<symbol>', methods=['GET'])
async def api_get_price(symbol):
    """Récupérer prix depuis WebSocket ou REST"""
    try:
        price_data = await price_provider.get_price(symbol)
        if price_data:
            return jsonify(price_data)
        return jsonify({'error': 'Price not available'}), 404
    except Exception as e:
        logger.error(f"Erreur prix {symbol}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyze/<symbol>', methods=['GET'])
async def api_analyze_symbol(symbol):
    """Analyser un symbole"""
    try:
        timeframe = request.args.get('tf', '1m')
        analysis = await analyzer.analyze_symbol(symbol, timeframe)
        
        if analysis:
            return jsonify({'analysis': analysis})
        return jsonify({'analysis': None})
    except Exception as e:
        logger.error(f"Erreur analyse {symbol}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/position/open', methods=['POST'])
async def api_open_position():
    """Ouvrir position"""
    try:
        data = await request.get_json()
        
        # Vérifier données minimales
        if not data or 'symbol' not in data:
            return jsonify({'error': 'Missing symbol'}), 400
        
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
        
        await add_log('INFO', 'Position ouverte', f"{data['direction']} {data['symbol']}")
        await socketio.emit('position_opened', position.to_dict())
        
        return jsonify({'status': 'opened', 'position': position.to_dict()})
    except Exception as e:
        logger.error(f"Erreur ouverture position: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/position/check', methods=['GET'])
async def api_check_position():
    """Check position actuelle"""
    if not position_manager.active_position:
        return jsonify({'status': 'no_position'})
    
    try:
        # Récupérer prix actuel
        price_data = await price_provider.get_price(position_manager.active_position.symbol)
        current_price = price_data.get('lastPrice') if price_data else None
        
        if not current_price:
            return jsonify({'error': 'Price not available'}), 500
        
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
        
        await socketio.emit('position_update', response)
        return jsonify(response)
    except Exception as e:
        logger.error(f"Erreur check position: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/position/close', methods=['POST'])
async def api_close_position():
    """Clôturer position manuellement"""
    if not position_manager.active_position:
        return jsonify({'error': 'No active position'}), 400
    
    try:
        # Récupérer prix actuel
        price_data = await price_provider.get_price(position_manager.active_position.symbol)
        exit_price = price_data.get('lastPrice') if price_data else None
        
        result = position_manager.close_position('MANUAL', exit_price=exit_price)
        
        app_state['active_position'] = None
        
        await add_log('INFO', 'Position clôturée', 'Manuel')
        await socketio.emit('position_closed', result)
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Erreur clôture position: {e}")
        return jsonify({'error': str(e)}), 500


# Helper async tasks

async def scan_top_pairs_task(n):
    """Tâche asynchrone pour scanner top pairs"""
    try:
        await add_log('INFO', 'Scan scalability', 'Démarrage...')
        
        top_pairs = await scanner.scan_top_pairs(n)
        app_state['top_pairs'] = top_pairs
        
        await add_log('INFO', 'Scan terminé', f'{len(top_pairs)} paires scalables')
        await socketio.emit('top_pairs_update', {'pairs': top_pairs})
        
    except Exception as e:
        logger.error(f"Erreur scan: {e}")
        await add_log('ERROR', 'Erreur scan', str(e))
    finally:
        app_state['is_scanning'] = False


# WebSocket Handlers

@socketio.on('connect')
async def handle_connect():
    """Connexion WebSocket"""
    logger.info("Client connecté")
    await emit('status', app_state)
    # Envoyer les derniers logs
    for log_entry in app_state['logs'][-50:]:
        await emit('log', log_entry)


@socketio.on('disconnect')
async def handle_disconnect():
    """Déconnexion WebSocket"""
    logger.info("Client déconnecté")


@socketio.on('request_logs')
async def handle_logs_request():
    """Demander les logs"""
    await emit('logs', app_state['logs'][-100:])


# Helper functions

async def add_log(level, message, detail=''):
    """Ajouter un log et envoyer via SocketIO"""
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
    await socketio.emit('log', entry)
    logger.info(f"[{entry['timestamp']}] {entry['level']}: {entry['message']}")


# Main entry point

if __name__ == '__main__':
    # Récupérer le port depuis les arguments (défaut: 5000)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    
    logger.info("🚀 Trade Cursor v7.0 démarré")
    logger.info("📊 Quart (async Flask) + WebSocket")
    logger.info(f"🌐 Ouvez http://localhost:{port} dans votre navigateur")
    
    # Lancer Quart + SocketIO
    app.run(host='0.0.0.0', port=port, debug=True)

