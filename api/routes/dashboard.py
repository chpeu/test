"""
Routes API pour le dashboard - Gestion du statut et du contrôle de l'application
"""

import asyncio
import logging
from fastapi import APIRouter, Depends, Security
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
import time

from api.auth import verify_api_key
from app.dependencies import get_app_state as dependency_app_state, get_ws_manager as dependency_ws_manager

logger = logging.getLogger(__name__)

# Variables globales injectées (scheduler/position manager)
_scheduler = None
_position_manager = None

# Overrides pour compatibilité historique (sinon dependencies.py fournit les singletons)
_app_state_override = None
_ws_manager_override = None


def set_scheduler(scheduler):
    """Injecter l'instance scheduler"""
    global _scheduler
    _scheduler = scheduler


def set_position_manager(position_manager):
    """Injecter l'instance position_manager"""
    global _position_manager
    _position_manager = position_manager


def set_app_state(app_state):
    """Injecter l'état de l'application (legacy)"""
    global _app_state_override
    _app_state_override = app_state


def set_websocket_manager(ws_manager):
    """Injecter l'instance WebSocketManager (legacy)"""
    global _ws_manager_override
    _ws_manager_override = ws_manager


def set_socketio(sio):
    """🔥 LEGACY: Alias pour compatibilité (déprécié - utiliser set_websocket_manager)"""
    global _ws_manager_override
    # Si c'est un ws_manager, l'utiliser
    _ws_manager_override = sio if hasattr(sio, 'emit') and not hasattr(sio, 'on') else None


def _get_app_state_dependency(app_state: Dict = Depends(dependency_app_state)) -> Dict:
    return _app_state_override or app_state


def _get_ws_manager_dependency(ws=Depends(dependency_ws_manager)):
    return _ws_manager_override or ws


# Créer le router
router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/status")
async def get_status(app_state: Dict = Depends(_get_app_state_dependency)):
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
    if not app_state:
        return JSONResponse({'error': 'App state not available'}, status_code=503)

    try:
        return JSONResponse(dict(app_state))
    except Exception as e:
        logger.error(f"Erreur récupération statut: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


@router.get("/state")
async def get_complete_state(app_state: Dict = Depends(_get_app_state_dependency)):
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
    # 🔥 FIX: Retourner 200 avec success=False au lieu de 503
    # Note: time est déjà importé au niveau du module (ligne 10)
    if not app_state:
        return JSONResponse({
            'success': False,
            'error': 'App state not available',
            'session_id': f"live_{int(time.time())}",
            'config': {},
            'scanner': {'is_scanning': False, 'top_pairs': []},
            'position': {'active': False, 'data': None},
            'stats': {'total_trades': 0, 'wins': 0, 'losses': 0, 'winrate': 0.0},
            'trades': [],
            'timestamp': time.time()
        }, status_code=200)

    try:
        # Récupérer position active
        active_position_dict = None
        if _position_manager and _position_manager.active_position:
            active_position = _position_manager.active_position
            active_position_dict = active_position.to_dict() if hasattr(active_position, 'to_dict') else {}
            active_position_dict['timestamp'] = time.time()

        # Récupérer stats
        stats_dict = {
            'total_trades': app_state.get('stats', {}).get('total_trades', 0),
            'wins': app_state.get('stats', {}).get('wins', 0),
            'losses': app_state.get('stats', {}).get('losses', 0),
            'winrate': app_state.get('stats', {}).get('winrate', 0.0)
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
                'is_scanning': app_state.get('is_scanning', False),
                'top_pairs': app_state.get('top_pairs', [])
            },
            'position': {
                'active': active_position_dict is not None,
                'data': active_position_dict
            },
            'stats': stats_dict,
            'timestamp': time.time()
        })

    except Exception as e:
        logger.error(f"Erreur récupération état complet: {e}", exc_info=True)
        # 🔥 FIX: Retourner 200 avec success=False au lieu de 500
        return JSONResponse({
            'success': False,
            'error': str(e),
            'session_id': f"live_{int(time.time())}",
            'config': {},
            'scanner': {'is_scanning': False, 'top_pairs': []},
            'position': {'active': False, 'data': None},
            'stats': {'total_trades': 0, 'wins': 0, 'losses': 0, 'winrate': 0.0},
            'trades': [],
            'timestamp': time.time()
        }, status_code=200)  # Retourner 200 avec success=False au lieu de 500


@router.post("/start")
async def start_scanner(
    user: dict = Security(verify_api_key),
    app_state: Dict = Depends(_get_app_state_dependency),
    ws_manager=Depends(_get_ws_manager_dependency),
):
    """
    POST /api/start
    Démarrer le scanner et le scheduler

    Nécessite authentification (X-API-Key header)

    Procédure:
    1. Effectuer un scan initial des top pairs si nécessaire
    2. Démarrer le scheduler pour les boucles automatiques
    3. Émettre événement SocketIO
    """
    # 🔥 FIX: Initialiser les instances si nécessaire
    try:
        if not _scheduler or not app_state:
            # Essayer d'initialiser les instances
            try:
                from main import init_instances
                init_instances()
            except Exception as e:
                logger.warning(f"Impossible d'initialiser les instances: {e}")
        
        # 🔥 FIX: Retourner 200 avec success=False au lieu de 503
        if not _scheduler or not app_state:
            return JSONResponse({
                'success': False,
                'status': 'error',
                'error': 'Scheduler not available',
                'is_scanning': False
            }, status_code=200)

        try:
            # 🔥 FIX: Démarrer le scheduler si disponible
            if _scheduler and not app_state.get('is_scanning', False):
                _scheduler.start()
                logger.info("✅ Scanner démarré via /api/start")

            app_state['is_scanning'] = True

            # 🔥 MIGRATION COMPLÈTE: Émettre l'état via WebSocket natif uniquement
            if ws_manager:
                status_data = {
                    'is_scanning': True,
                    'active_position': app_state.get('active_position'),
                    'stats': app_state.get('stats', {}),
                    'top_pairs': app_state.get('top_pairs', [])
                }
                await ws_manager.emit('status', status_data)
                await ws_manager.emit('scan_started', {'timestamp': time.time()})

            return JSONResponse({
                'success': True,
                'status': 'started',
                'is_scanning': True
            })

        except Exception as e:
            logger.error(f"Erreur démarrage scanner: {e}", exc_info=True)
            return JSONResponse({
                'success': False,
                'status': 'error',
                'error': str(e),
                'is_scanning': False
            }, status_code=200)  # 🔥 FIX: Retourner 200 avec success=False au lieu de 500
    except Exception as e:
        logger.error(f"Erreur critique démarrage scanner: {e}", exc_info=True)
        return JSONResponse({
            'success': False,
            'status': 'error',
            'error': str(e),
            'is_scanning': False
        }, status_code=200)  # 🔥 FIX: Retourner 200 avec success=False au lieu de 500


@router.post("/stop")
async def stop_scanner(
    user: dict = Security(verify_api_key),
    app_state: Dict = Depends(_get_app_state_dependency),
    ws_manager=Depends(_get_ws_manager_dependency),
):
    """
    POST /api/stop
    Arrêter le scanner et le scheduler

    Nécessite authentification (X-API-Key header)

    Procédure:
    1. Arrêter le scheduler (arrête les boucles automatiques)
    2. Mise à jour de l'état is_scanning
    3. Émettre événement SocketIO
    """
    # 🔥 FIX: Initialiser les instances si nécessaire
    try:
        if not _scheduler or not _app_state:
            # Essayer d'initialiser les instances
            try:
                from main import init_instances
                init_instances()
            except Exception as e:
                logger.warning(f"Impossible d'initialiser les instances: {e}")
        
        # 🔥 FIX: Retourner 200 avec success=False au lieu de 503
        if not _scheduler or not _app_state:
            return JSONResponse({
                'success': False,
                'status': 'error',
                'error': 'Scheduler not available',
                'is_scanning': False
            }, status_code=200)

        try:
            # 🔥 FIX: Arrêter le scheduler si disponible
            if _scheduler and app_state.get('is_scanning', False):
                _scheduler.stop()
                logger.info("⏸️ Scanner arrêté via /api/stop")

            app_state['is_scanning'] = False

            # 🔥 MIGRATION COMPLÈTE: Émettre l'état via WebSocket natif uniquement
            if ws_manager:
                status_data = {
                    'is_scanning': False,
                    'active_position': app_state.get('active_position'),
                    'stats': app_state.get('stats', {}),
                    'top_pairs': app_state.get('top_pairs', [])
                }
                await ws_manager.emit('status', status_data)

            return JSONResponse({
                'success': True,
                'status': 'stopped',
                'is_scanning': False
            })

        except Exception as e:
            logger.error(f"Erreur arrêt scanner: {e}", exc_info=True)
            return JSONResponse({
                'success': False,
                'status': 'error',
                'error': str(e),
                'is_scanning': False
            }, status_code=200)  # 🔥 FIX: Retourner 200 avec success=False au lieu de 500
    except Exception as e:
        logger.error(f"Erreur critique arrêt scanner: {e}", exc_info=True)
        return JSONResponse({
            'success': False,
            'status': 'error',
            'error': str(e),
            'is_scanning': False
        }, status_code=200)  # 🔥 FIX: Retourner 200 avec success=False au lieu de 500
