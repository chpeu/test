"""
Routes API pour le dashboard - Gestion du statut et du contrôle de l'application
"""

import asyncio
import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
import time

logger = logging.getLogger(__name__)

# Variables globales injectées par main.py
_scheduler = None
_position_manager = None
_app_state = None
_sio = None


def set_scheduler(scheduler):
    """Injecter l'instance scheduler"""
    global _scheduler
    _scheduler = scheduler


def set_position_manager(position_manager):
    """Injecter l'instance position_manager"""
    global _position_manager
    _position_manager = position_manager


def set_app_state(app_state):
    """Injecter l'état de l'application"""
    global _app_state
    _app_state = app_state


def set_socketio(sio):
    """Injecter l'instance SocketIO"""
    global _sio
    _sio = sio


# Créer le router
router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/status")
async def get_status():
    """
    GET /api/status
    Récupérer l'état global de l'application

    Response:
    {
        "is_scanning": bool,
        "active_position": bool,
        "stats": {...},
        "top_pairs": [...],
        "logs": [...],
        "trade_history": [...]
    }
    """
    if not _app_state:
        return JSONResponse({'error': 'App state not available'}, status_code=503)

    try:
        return JSONResponse(_app_state)
    except Exception as e:
        logger.error(f"Erreur récupération statut: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


@router.get("/state")
async def get_complete_state():
    """
    GET /api/state
    Récupérer l'état complet de l'application

    Inclut:
    - Configuration de trading
    - Statut du scanner
    - Position active
    - Stats et historique des trades
    - Timestamp de la session
    """
    if not _app_state:
        return JSONResponse({'error': 'App state not available'}, status_code=503)

    try:
        # Récupérer position active
        active_position_dict = None
        if _position_manager and _position_manager.active_position:
            active_position = _position_manager.active_position
            active_position_dict = active_position.to_dict() if hasattr(active_position, 'to_dict') else {}
            active_position_dict['timestamp'] = time.time()

        # Récupérer stats
        stats_dict = {
            'total_trades': _app_state.get('stats', {}).get('total_trades', 0),
            'wins': _app_state.get('stats', {}).get('wins', 0),
            'losses': _app_state.get('stats', {}).get('losses', 0),
            'winrate': _app_state.get('stats', {}).get('winrate', 0.0)
        }

        from config import TRADING_CONFIG

        return JSONResponse({
            'success': True,
            'config': {
                'snr_threshold': TRADING_CONFIG.get('snr_threshold', 0.25),
                'breakout_threshold': TRADING_CONFIG.get('breakout_threshold', 0.35),
                'wick_ratio_max': TRADING_CONFIG.get('wick_ratio_max', 2.8),
                'di_gap_min': TRADING_CONFIG.get('di_gap_min', 4.0),
                'trend_timeframe': TRADING_CONFIG.get('trend_timeframe', '15m'),
                'account_size': TRADING_CONFIG.get('account_size', 1000.0),
                'risk_per_trade': TRADING_CONFIG.get('risk_per_trade', 2.0),
                'use_confluence': TRADING_CONFIG.get('use_confluence', False),
                'tp_sl_mode': TRADING_CONFIG.get('tp_sl_mode', 'FIXE'),
                'tp_percent': TRADING_CONFIG.get('tp_percent', 0.25),
                'sl_percent': TRADING_CONFIG.get('sl_percent', 0.25),
                'volume_multiplier': TRADING_CONFIG.get('volume_multiplier', 0.95),
                'min_score_required': TRADING_CONFIG.get('min_score_required', 7.5),
            },
            'scanner': {
                'is_scanning': _app_state.get('is_scanning', False),
                'top_pairs': _app_state.get('top_pairs', [])
            },
            'position': {
                'active': active_position_dict is not None,
                'data': active_position_dict
            },
            'stats': stats_dict,
            'timestamp': time.time()
        })

    except Exception as e:
        logger.error(f"Erreur récupération état complet: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


@router.post("/start")
async def start_scanner():
    """
    POST /api/start
    Démarrer le scanner et le scheduler

    Procédure:
    1. Effectuer un scan initial des top pairs si nécessaire
    2. Démarrer le scheduler pour les boucles automatiques
    3. Émettre événement SocketIO
    """
    if not _scheduler or not _app_state:
        return JSONResponse({'error': 'Scheduler not available'}, status_code=503)

    try:
        # 🔥 FIX: Démarrer le scheduler si disponible
        if _scheduler and not _app_state.get('is_scanning', False):
            _scheduler.start()
            logger.info("✅ Scanner démarré via /api/start")

        if _app_state:
            _app_state['is_scanning'] = True

        # 🔥 FIX: Émettre l'état via Socket.IO pour synchronisation temps réel
        if _sio:
            status_data = {
                'is_scanning': True,
                'active_position': _app_state.get('active_position'),
                'stats': _app_state.get('stats', {}),
                'top_pairs': _app_state.get('top_pairs', [])
            }
            await _sio.emit('status', status_data)
            await _sio.emit('scan_started', {'timestamp': time.time()})

        return JSONResponse({
            'status': 'started',
            'is_scanning': True
        })

    except Exception as e:
        logger.error(f"Erreur démarrage scanner: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


@router.post("/stop")
async def stop_scanner():
    """
    POST /api/stop
    Arrêter le scanner et le scheduler

    Procédure:
    1. Arrêter le scheduler (arrête les boucles automatiques)
    2. Mise à jour de l'état is_scanning
    3. Émettre événement SocketIO
    """
    if not _scheduler or not _app_state:
        return JSONResponse({'error': 'Scheduler not available'}, status_code=503)

    try:
        # 🔥 FIX: Arrêter le scheduler si disponible
        if _scheduler and _app_state.get('is_scanning', False):
            _scheduler.stop()
            logger.info("⏸️ Scanner arrêté via /api/stop")

        if _app_state:
            _app_state['is_scanning'] = False

        # 🔥 FIX: Émettre l'état via Socket.IO pour synchronisation temps réel
        if _sio:
            status_data = {
                'is_scanning': False,
                'active_position': _app_state.get('active_position'),
                'stats': _app_state.get('stats', {}),
                'top_pairs': _app_state.get('top_pairs', [])
            }
            await _sio.emit('status', status_data)

        return JSONResponse({
            'status': 'stopped',
            'is_scanning': False
        })

    except Exception as e:
        logger.error(f"Erreur arrêt scanner: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)
