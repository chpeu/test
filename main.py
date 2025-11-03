#!/usr/bin/env python3
"""
Trade Cursor v6.0 - Application Flask
Interface HTML identique à v5.1 avec backend Python
"""

import sys
import asyncio
import logging
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import json
from datetime import datetime
from pathlib import Path

# 🔥 v6.6.1 Phase 2A: Import HybridPriceProvider
from api.price_provider import get_price_provider

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialisation Flask + SocketIO
app = Flask(__name__)
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

# Routes Flask

@app.route('/')
def index():
    """Page principale - HTML copié de v5.1"""
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    """État global de l'application"""
    return jsonify(app_state)


@app.route('/api/start', methods=['POST'])
def api_start():
    """Démarrer le scanner"""
    if app_state['is_scanning']:
        return jsonify({'error': 'Déjà en cours'}), 400
    
    app_state['is_scanning'] = True
    logger.info("Scanner démarré")
    socketio.emit('status', {'is_scanning': True})
    
    # TODO: Lancer le scanner asynchrone
    # asyncio.create_task(start_scanner())
    
    return jsonify({'status': 'started'})


@app.route('/api/stop', methods=['POST'])
def api_stop():
    """Arrêter le scanner"""
    app_state['is_scanning'] = False
    logger.info("Scanner arrêté")
    socketio.emit('status', {'is_scanning': False})
    return jsonify({'status': 'stopped'})


# WebSocket Handlers

@socketio.on('connect')
def handle_connect():
    """Connexion WebSocket"""
    logger.info("Client connecté")
    emit('status', app_state)
    # Envoyer les derniers logs
    for log_entry in app_state['logs'][-50:]:
        emit('log', log_entry)


@socketio.on('disconnect')
def handle_disconnect():
    """Déconnexion WebSocket"""
    logger.info("Client déconnecté")


@socketio.on('request_logs')
def handle_logs_request():
    """Demander les logs"""
    emit('logs', app_state['logs'][-100:])


# Helper functions

def add_log(level, message, detail=''):
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
    socketio.emit('log', entry)
    logger.info(f"[{entry['timestamp']}] {entry['level']}: {entry['message']}")


# Main entry point

if __name__ == '__main__':
    # Récupérer le port depuis les arguments (défaut: 5000)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    
    logger.info("🚀 Trade Cursor v6.0 démarré")
    logger.info("📊 Interface HTML identique à v5.1")
    logger.info(f"🌐 Ouvez http://localhost:{port} dans votre navigateur")
    
    # Lancer Flask + SocketIO
    socketio.run(app, host='0.0.0.0', port=port, debug=True)

