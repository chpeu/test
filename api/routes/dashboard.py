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


def get_dashboard_stats() -> Dict[str, Any]:
    """Compatibilité tests: stats synthétiques du dashboard."""
    try:
        if _app_state is None:
            return {"status": "unavailable", "stats": {}}
        if hasattr(_app_state, "get"):
            return _app_state.get("stats", {}) or {}
        if hasattr(_app_state, "stats"):
            return getattr(_app_state, "stats") or {}
    except Exception:
        return {}


async def initiate_backend_reboot(
    reason: str = 'manual',
    source: str = 'http',
    request: Optional[Request] = None
) -> Dict[str, Any]:
    """Déclencher un reboot backend avec logs détaillés."""
    client_host = None
    user_agent = None
    if request is not None:
        try:
            client_host = getattr(request.client, 'host', None)
        except Exception:
            client_host = None
        try:
            user_agent = request.headers.get('user-agent')
        except Exception:
            user_agent = None

    logger.warning(
        "♻️ Reboot backend demandé",
        extra={
            "reason": reason,
            "source": source,
            "client_host": client_host,
            "user_agent": user_agent
        }
    )

    from core.bootstrap import perform_backend_reboot
    asyncio.create_task(perform_backend_reboot(reason=reason))
    return {
        'status': 'rebooting',
        'reason': reason,
        'source': source
    }


# Créer le router
router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/status")
async def get_status():
    """
    GET /api/status
    Récupérer l'état global de l'application
    """
    if not _app_state:
        return JSONResponse({'error': 'App state not available'}, status_code=503)

    try:
        # 🔥 FIX: Utiliser _app_state injecté au lieu de get_state_manager() pour cohérence et tests
        if hasattr(_app_state, 'to_dict'):
            status_data = _app_state.to_dict()
        else:
            # Fallback pour les tests ou si c'est un dict
            status_data = dict(_app_state)
            
        return JSONResponse(status_data)
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
            'quiet_mode': False,
            'log_mode': 'logs',
            'config': {},
            'scanner': {'is_scanning': False, 'top_pairs': []},
            'position': {'active': False, 'data': None},
            'stats': {'total_trades': 0, 'wins': 0, 'losses': 0, 'winrate': 0.0},
            'trades': [],
            'timestamp': time.time()
        }, status_code=200)

    try:
        from utils.effective_config import get_effective_config
        effective_cfg = get_effective_config()
        
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

        return JSONResponse({
            'success': True,
            'session_id': _app_state.get('session_id'),
            'quiet_mode': _app_state.get('quiet_mode', False),
            'log_mode': _app_state.get('log_mode', 'logs'),
            'config': {
                'snr_threshold': effective_cfg.get('snr_threshold', 0.25),
                'break_even_trigger': effective_cfg.get('break_even_trigger', 0.3),
                'break_even_use_atr': effective_cfg.get('break_even_use_atr', False),
                'break_even_atr_mult': effective_cfg.get('break_even_atr_mult', 0.5),
                'partial_tp_percent': effective_cfg.get('partial_tp_percent', 50.0),
                'trailing_trigger_pnl': effective_cfg.get('trailing_trigger_pnl', 0.15),
                'trailing_distance': effective_cfg.get('trailing_distance', 0.15),
                'trailing_use_atr_trigger': effective_cfg.get('trailing_use_atr_trigger', False),
                'trailing_trigger_atr_mult': effective_cfg.get('trailing_trigger_atr_mult', 1.5),
                'trailing_distance_atr_mult': effective_cfg.get('trailing_distance_atr_mult', 1.0),
                'stagnation_exit_enabled': effective_cfg.get('stagnation_exit_enabled', False),
                'stagnation_exit_timeout_seconds': effective_cfg.get('stagnation_exit_timeout_seconds', 120),
                'stagnation_exit_min_pnl_to_stay': effective_cfg.get('stagnation_exit_min_pnl_to_stay', 0.10),
                'stagnation_exit_max_loss_to_exit': effective_cfg.get('stagnation_exit_max_loss_to_exit', -0.05),
                'stagnation_positive_exit_enabled': effective_cfg.get('stagnation_positive_exit_enabled', True),
                'stagnation_positive_threshold': effective_cfg.get('stagnation_positive_threshold', 0.03),
                'stagnation_positive_timeout_seconds': effective_cfg.get('stagnation_positive_timeout_seconds', 60),
                'stagnation_use_mfe_tracking': effective_cfg.get('stagnation_use_mfe_tracking', True),
                'stagnation_mfe_pullback_pct': effective_cfg.get('stagnation_mfe_pullback_pct', 0.08),
                'trailing_mfe_enabled': effective_cfg.get('trailing_mfe_enabled', False),
                'trailing_mfe_trigger_pct': effective_cfg.get('trailing_mfe_trigger_pct', 0.10),
                'tp_sl_mode': effective_cfg.get('tp_sl_mode', 'FIXE'),
                'tp_percent': effective_cfg.get('tp_percent', 0.25),
                'sl_percent': effective_cfg.get('sl_percent', 0.25),
                'volume_multiplier': effective_cfg.get('volume_multiplier', 0.95),
                'min_score_required': effective_cfg.get('min_score_required', 7.5),
                # 🔥 AJOUT: Paramètres ATR dynamiques
                'atr_mult_sl': effective_cfg.get('atr_mult_sl'),
                'atr_mult_tp': effective_cfg.get('atr_mult_tp'),
                'optimal_atr_min_1m': effective_cfg.get('optimal_atr_min_1m'),
                'optimal_atr_max_1m': effective_cfg.get('optimal_atr_max_1m')
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
                from core.bootstrap import init_instances
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
        from core.bootstrap import init_instances
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
        result = await initiate_backend_reboot(reason=reason, source='http', request=request)
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"Erreur reboot backend: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


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
