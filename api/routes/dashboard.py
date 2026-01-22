"""
Routes API pour le dashboard - Gestion du statut et du contrôle de l'application
"""

import asyncio
import logging
from fastapi import APIRouter, Security, Request
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List, Tuple, Callable
import time
from datetime import datetime

from api.auth import verify_api_key

logger = logging.getLogger(__name__)

# Variables globales injectées par main.py
_scheduler = None
_position_manager = None
_app_state = None
_ws_manager = None  # 🔥 MIGRATION COMPLÈTE: WebSocket natif uniquement


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


def set_websocket_manager(ws_manager):
    """🔥 MIGRATION COMPLÈTE: Injecter l'instance WebSocketManager (WebSocket natif uniquement)"""
    global _ws_manager
    _ws_manager = ws_manager


def set_socketio(sio):
    """🔥 LEGACY: Alias pour compatibilité (déprécié - utiliser set_websocket_manager)"""
    global _ws_manager
    # Si c'est un ws_manager, l'utiliser
    _ws_manager = sio if hasattr(sio, 'emit') and not hasattr(sio, 'on') else None


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
        if hasattr(_app_state, 'to_dict'):
            return JSONResponse(_app_state.to_dict())
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
    # 🔥 FIX: Retourner 200 avec success=False au lieu de 503
    # Note: time est déjà importé au niveau du module (ligne 10)
    if not _app_state:
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
                'telegram_enabled': TRADING_CONFIG.get('telegram_enabled', False),
                'use_confluence': TRADING_CONFIG.get('use_confluence', False),
                'invert_signals': TRADING_CONFIG.get('invert_signals', False),
                'break_even_trigger': TRADING_CONFIG.get('break_even_trigger', 0.3),
                'break_even_use_atr': TRADING_CONFIG.get('break_even_use_atr', False),
                'break_even_atr_mult': TRADING_CONFIG.get('break_even_atr_mult', 0.5),
                'partial_tp_percent': TRADING_CONFIG.get('partial_tp_percent', 50.0),
                'trailing_trigger_pnl': TRADING_CONFIG.get('trailing_trigger_pnl', 0.15),
                'trailing_distance': TRADING_CONFIG.get('trailing_distance', 0.15),
                'trailing_use_atr_trigger': TRADING_CONFIG.get('trailing_use_atr_trigger', False),
                'trailing_trigger_atr_mult': TRADING_CONFIG.get('trailing_trigger_atr_mult', 1.5),
                'trailing_distance_atr_mult': TRADING_CONFIG.get('trailing_distance_atr_mult', 1.0),
                'stagnation_exit_enabled': TRADING_CONFIG.get('stagnation_exit_enabled', False),
                'stagnation_exit_timeout_seconds': TRADING_CONFIG.get('stagnation_exit_timeout_seconds', 120),
                'stagnation_exit_min_pnl_to_stay': TRADING_CONFIG.get('stagnation_exit_min_pnl_to_stay', 0.10),
                'stagnation_exit_max_loss_to_exit': TRADING_CONFIG.get('stagnation_exit_max_loss_to_exit', -0.05),
                'stagnation_positive_exit_enabled': TRADING_CONFIG.get('stagnation_positive_exit_enabled', True),
                'stagnation_positive_threshold': TRADING_CONFIG.get('stagnation_positive_threshold', 0.03),
                'stagnation_positive_timeout_seconds': TRADING_CONFIG.get('stagnation_positive_timeout_seconds', 60),
                'stagnation_use_mfe_tracking': TRADING_CONFIG.get('stagnation_use_mfe_tracking', True),
                'stagnation_mfe_pullback_pct': TRADING_CONFIG.get('stagnation_mfe_pullback_pct', 0.08),
                'trailing_mfe_enabled': TRADING_CONFIG.get('trailing_mfe_enabled', False),
                'trailing_mfe_trigger_pct': TRADING_CONFIG.get('trailing_mfe_trigger_pct', 0.10),
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
            # 🔥 FIX: Renvoyer l'historique des trades pour persistance frontend
            'trade_history': _app_state.get('trade_history', []),
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
async def start_scanner(user: dict = Security(verify_api_key)):
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
            # 🔥 FIX: Démarrer le scheduler si disponible
            if _scheduler and not _app_state.get('is_scanning', False):
                _scheduler.start()
                logger.info("✅ Scanner démarré via /api/start")

            if _app_state:
                _app_state['is_scanning'] = True

            # 🔥 MIGRATION COMPLÈTE: Émettre l'état via WebSocket natif uniquement
            if _ws_manager:
                status_data = {
                    'is_scanning': True,
                    'active_position': _app_state.get('active_position'),
                    'stats': _app_state.get('stats', {}),
                    'top_pairs': _app_state.get('top_pairs', [])
                }
                await _ws_manager.emit('status', status_data)
                await _ws_manager.emit('scan_started', {'timestamp': time.time()})

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
async def stop_scanner():
    """
    POST /api/stop
    Arrêter le scanner et le scheduler
    """
    if not _scheduler or not _app_state:
        return JSONResponse({
            'success': False,
            'status': 'error',
            'error': 'Scheduler not available',
            'is_scanning': _app_state.get('is_scanning', False) if _app_state else False
        }, status_code=200)

    try:
        if _scheduler and _app_state.get('is_scanning', False):
            _scheduler.stop()
            logger.info("✅ Scanner arrêté via /api/stop")

        if _app_state:
            _app_state['is_scanning'] = False

        # 🔥 MIGRATION COMPLÈTE: Émettre l'état via WebSocket natif uniquement
        if _ws_manager:
            status_data = {
                'is_scanning': False,
                'active_position': _app_state.get('active_position'),
                'stats': _app_state.get('stats', {}),
                'top_pairs': _app_state.get('top_pairs', [])
            }
            await _ws_manager.emit('status', status_data)
            await _ws_manager.emit('scan_stopped', {'timestamp': time.time()})

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
            'is_scanning': True
        }, status_code=200)


@router.get("/sessions")
async def get_sessions():
    """
    ⚠️ DEPRECATED: Utiliser WebSocket request 'state' ou événements 'sessions_update' à la place
    Liste des sessions (compatibilité frontend Svelte)
    """
    import sys
    try:
        current_port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
        sess_id = _app_state.get('session_id') if _app_state else f"live_{int(time.time())}"
        is_scanning = _app_state.get('is_scanning', False) if _app_state else False
        
        return JSONResponse({
            'sessions': [{
                'id': sess_id,
                'status': 'running' if is_scanning else 'stopped',
                'port': current_port,
                'started_at': time.time()
            }] if sess_id else []
        })
    except Exception as e:
        logger.error(f"❌ Erreur /api/sessions: {e}")
        return JSONResponse({
            'sessions': [],
            'error': str(e)
        }, status_code=200)


@router.get("/dashboard/summary")
async def get_dashboard_summary():
    """Résumé des statistiques de trading"""
    from core.state_manager import get_state_manager
    state = get_state_manager()
    
    # S'assurer que les instances sont prêtes
    try:
        from main import init_instances
        init_instances()
    except ImportError:
        pass

    trades = _app_state.get('trade_history', []) if _app_state else []
    
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
    
    # Max Drawdown Tracking
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
    pos_mgr = _position_manager or state.get_position_manager()
    if pos_mgr and pos_mgr.config:
        recovery_mode_active = getattr(pos_mgr.config, 'recovery_mode_active', False)
    
    return JSONResponse({
        'total_trades': total_trades,
        'wins': wins,
        'losses': losses,
        'winrate': round(winrate, 2),
        'profit_total': round(profit_total, 4),
        'profit_today': round(profit_today, 4),
        'drawdown': round(max_dd_info.get('current_dd', 0), 2),
        'drawdown_max': max_dd_info.get('max_dd', 0),
        'drawdown_max_date': max_dd_info.get('max_dd_date'),
        'current_peak': max_dd_info.get('current_peak', 0),
        'win_streak': win_streak,
        'loss_streak': loss_streak,
        'recovery_mode_active': recovery_mode_active,
        'equity_curve': equity_curve[-100:]
    })


@router.get("/dashboard/trades-history")
async def get_trades_history(limit: int = 10000):
    """
    🔥 SESSION-BASED: Historique des trades de la session actuelle uniquement
    """
    from core.state_manager import get_state_manager
    state = get_state_manager()
    
    current_session_trades = []
    analytics_db = state.get_analytics_db()
    sess_id = state.session_id
    if analytics_db and sess_id:
        try:
            all_trades = analytics_db.get_trades(limit=limit)
            current_session_trades = [t for t in all_trades if t.get('session_id') == sess_id]
        except Exception as e:
            logger.error(f"❌ Erreur récupération trades session: {e}")

    # Retourner les plus récents en premier
    recent_trades = list(reversed(current_session_trades))
    return JSONResponse(recent_trades)


@router.post("/reboot")
async def api_reboot_backend(request: Request):
    """Redémarrer le backend"""
    try:
        data = await request.json() if hasattr(request, 'json') else {}
        reason = data.get('reason', 'manual')
        return await initiate_backend_reboot(reason=reason)
    except Exception as e:
        logger.error(f"Erreur reboot backend: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)

async def initiate_backend_reboot(reason: str = 'manual') -> dict:
    """Logique de redémarrage du backend"""
    from core.state_manager import get_state_manager
    state = get_state_manager()
    from main import add_log
    import os
    import sys
    
    await add_log('WARNING', 'BACKEND REBOOT', f'Raison: {reason}')
    
    # Notification WebSocket avant arrêt
    ws_mgr = state.get_ws_manager()
    if ws_mgr:
        await ws_mgr.emit('backend_rebooting', {
            'reason': reason,
            'timestamp': time.time()
        })
    
    # Arrêt propre des boucles
    try:
        sched = state.get_scheduler()
        if sched:
            await sched.stop_async()
    except Exception: pass
    
    # Planifier le redémarrage (OS dependent)
    # Sur Windows, on peut utiliser os.execv ou simplement laisser un process manager (pm2, etc) redémarrer
    # Ici on simule ou on utilise une méthode standard
    async def delayed_exit():
        await asyncio.sleep(2)
        logger.info(f"🛑 Arrêt du processus pour reboot (raison: {reason})")
        os._exit(0) # Exit brutal pour forcer le restart par pm2/docker/service
    
    asyncio.create_task(delayed_exit())
    
    return {'status': 'rebooting', 'reason': reason}
def calculate_max_drawdown(trade_history: List[Dict]) -> Dict:
    """
    Calculer drawdown maximum historique (peak to trough)
    
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
