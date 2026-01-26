"""
Routes API pour la gestion des positions
"""

import asyncio
import logging
import time
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Variables globales injectées par main.py
_position_manager = None
_app_state = None
_ws_manager = None
_live_order_manager = None
_price_provider = None
_scheduler = None

def set_position_manager(pm):
    global _position_manager
    _position_manager = pm

def set_app_state(as_):
    global _app_state
    _app_state = as_

def set_websocket_manager(wm):
    global _ws_manager
    _ws_manager = wm

def set_live_order_manager(lom):
    global _live_order_manager
    _live_order_manager = lom

def set_price_provider(pp):
    global _price_provider
    _price_provider = pp

def set_scheduler(s):
    global _scheduler
    _scheduler = s

router = APIRouter(prefix="/api/position", tags=["position"])

@router.post("/open")
async def api_open_position(request: Request):
    """Ouvrir position"""
    from core.state_manager import get_state_manager
    state = get_state_manager()
    
    pos_mgr = _position_manager or state.get_position_manager()
    if not pos_mgr:
        return JSONResponse({'error': 'Position manager not available'}, status_code=503)
    
    pos_lock = state.lock("position")
    position = None
    data = {}
    try:
        async with pos_lock:
            # Vérifier qu'on n'a pas déjà une position active
            if state.active_position or (pos_mgr and pos_mgr.active_position):
                return JSONResponse({'error': 'Une position est déjà active'}, status_code=400)

            data = await request.json() if hasattr(request, 'json') else {}
            data = data if isinstance(data, dict) else {}

            if not data or 'symbol' not in data:
                return JSONResponse({'error': 'Missing symbol'}, status_code=400)

            entry = data.get('entry')
            if not entry or entry <= 0:
                return JSONResponse({
                    'error': f'Entry invalide ou manquant: {entry}. Entry doit être > 0.'
                }, status_code=400)

            condition_types = data.get('condition_types', [])
            adaptive_mult = data.get('adaptive_sizing_multiplier', 1.0)
            
            # Recalculer le multiplicateur adaptatif si 1.0
            if adaptive_mult == 1.0:
                try:
                    from config import TRADING_CONFIG
                    if TRADING_CONFIG.get('adaptive_sizing_enabled', True):
                        from core.position.adaptive_sizing import get_adaptive_sizing_manager
                        adaptive_manager = get_adaptive_sizing_manager()
                        adaptive_mult = adaptive_manager.get_size_multiplier(data['symbol'])
                except (ImportError, AttributeError):
                    pass

            direction = data.get('direction', 'LONG')
            from config import TRADING_CONFIG
            if TRADING_CONFIG.get('invert_signals', False):
                direction = 'SHORT' if direction == 'LONG' else 'LONG'
                logger.warning(f"🔄 INVERSION DE SIGNAL (API): {data['symbol']} -> {direction}")

            position = await asyncio.to_thread(
                pos_mgr.open_position,
                symbol=data['symbol'],
                direction=direction,
                entry=float(entry),
                size=data.get('size', 100.0),
                atr=data.get('atr'),
                atr5m=data.get('atr5m'),
                confirmed_by=data.get('confirmed_by', ''),
                scalability_data=data.get('scalability_data'),
                condition_types=condition_types,
                ml_confidence=data.get('ml_confidence'),
                adaptive_sizing_multiplier=adaptive_mult,
                setup_data=data
            )

            if position is None:
                return JSONResponse({'error': 'Trade rejeté (calibration ML)'}, status_code=400)

            if 'capital' in data:
                position.capital = data.get('capital')

            state.set_active_position(position)
    except Exception as e:
        logger.error(f"Erreur ouverture position: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)

    # Post-open tasks (hors lock)
    try:
        pp = _price_provider or state.get_price_provider()
        if pp and position:
            from core.position.sl_services import setup_realtime_sl_check
            await setup_realtime_sl_check(position, pp)
    except Exception as e:
        logger.warning(f"⚠️ Erreur setup_realtime_sl_check: {e}")

    try:
        if position:
            from core.position.sl_services import schedule_sl_order_placement
            await schedule_sl_order_placement(position, delay_seconds=3.0)
    except Exception as e:
        logger.warning(f"⚠️ Erreur schedule_sl_order_placement: {e}")

    try:
        sched = _scheduler or state.get_scheduler()
        if sched and not sched.is_running:
            sched.start()
    except Exception as e:
        logger.warning(f"⚠️ Erreur démarrage scheduler: {e}")

    try:
        from utils.logging_utils import add_log
        asyncio.create_task(add_log('INFO', 'Position ouverte', f"{direction} {data.get('symbol', '')}"))
    except Exception:
        pass

    try:
        wm = _ws_manager or state.get_ws_manager()
        if wm:
            asyncio.create_task(wm.emit('position_opened', position.to_dict()))
    except Exception:
        pass

    return JSONResponse({'status': 'opened', 'position': position.to_dict()})

@router.get("/active")
async def api_get_active_position():
    """Récupérer position active"""
    from core.state_manager import get_state_manager
    state = get_state_manager()
    pos_mgr = _position_manager or state.get_position_manager()
    
    if not pos_mgr or not pos_mgr.active_position:
        return JSONResponse({
            'success': True,
            'active': False,
            'position': None
        })
    
    position = pos_mgr.active_position
    position_dict = position.to_dict()
    position_dict['timestamp'] = time.time()
    
    return JSONResponse({
        'success': True,
        'active': True,
        'position': position_dict
    })

@router.get("/check")
async def api_check_position():
    """Check position actuelle"""
    from core.state_manager import get_state_manager
    state = get_state_manager()
    pos_mgr = _position_manager or state.get_position_manager()
    
    if not pos_mgr or not pos_mgr.active_position:
        return JSONResponse({'status': 'no_position'})
    
    pp = _price_provider or state.get_price_provider()
    if not pp:
        return JSONResponse({'error': 'Price provider not available'}, status_code=503)
    
    try:
        from utils.pricing import get_preferred_price
        price_data = await pp.get_price(pos_mgr.active_position.symbol)
        current_price = get_preferred_price(price_data)
        
        if not current_price:
            return JSONResponse({'error': 'Price not available'}, status_code=500)
        
        result = await pos_mgr.check_position(current_price)
        position = pos_mgr.active_position
        
        pnl = pos_mgr.pnl_calculator.calculate_pnl_percent(
            entry=position.entry,
            current_price=current_price,
            direction=position.direction
        )
        pnl_usdt = pos_mgr.pnl_calculator.calculate_pnl_usdt(
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
            response['close_reason'] = result
        
        wm = _ws_manager or state.get_ws_manager()
        if wm:
            await wm.emit('position_update', response)
        return JSONResponse(response)
    except Exception as e:
        logger.error(f"Erreur check position: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)

@router.post("/close")
async def api_close_position(request: Request):
    """Clôturer position manuellement via API"""
    try:
        data = await request.json() if hasattr(request, 'json') else {}
        reason = data.get('reason', 'MANUAL')
        exit_price = data.get('exit_price')
        result = await perform_close_position(reason=reason, exit_price=exit_price)
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"Erreur clôture position: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


async def perform_close_position(reason: str = 'MANUAL', exit_price: Optional[float] = None) -> dict:
    """Version interne utilisable par WebSocket sans dépendances FastAPI"""
    from core.state_manager import get_state_manager
    state = get_state_manager()
    from core.bootstrap import init_instances
    from utils.history_utils import save_trade_history
    from core.position.sl_services import cancel_pending_sl_task
    from utils.logging_utils import add_log
    from utils.pricing import get_preferred_price
    
    init_instances()
    pos_lock = state.lock("position")
    async with pos_lock:
        pos_mgr = _position_manager or state.get_position_manager()
        if not pos_mgr or not pos_mgr.active_position:
            if not state.active_position:
                raise ValueError('No active position')
            else:
                state.set_active_position(None)
                raise ValueError('Position state inconsistent')
        
        pp = _price_provider or state.get_price_provider()
        if not pp:
            raise ValueError('Price provider not available')
        
        if exit_price is None:
            price_data = await pp.get_price(pos_mgr.active_position.symbol)
            exit_price = get_preferred_price(price_data)
        
        result = await asyncio.to_thread(
            pos_mgr.close_position,
            exit_price=exit_price,
            reason=reason,
        )
        state.set_active_position(None)
        
        if result:
            result['timestamp'] = datetime.now().isoformat()
            state.add_trade(result)
            save_trade_history()
        
        if pp:
            pp.set_socketio_callback(None, None)
            pp.set_sl_check_callback(None)
        
        closed_symbol = result.get('symbol') if result else None
        if closed_symbol:
            cancel_pending_sl_task(closed_symbol)
        
        # 🔥 FIX: Redémarrer le WebSocket pour tous les top_pairs après fermeture
        # (car il avait été restreint au symbole de la position uniquement)
        if pp and state.top_pairs:
            try:
                symbols = [p.get('symbol', '') for p in state.top_pairs[:30] if p.get('symbol')]
                if symbols:
                    # Arrêter d'abord le WebSocket restreint
                    await pp.stop_websocket()
                    # Redémarrer pour tous les symboles
                    await pp.start_websocket(symbols)
                    logger.info(f"🔄 WebSocket redémarré pour {len(symbols)} symboles après fermeture position")
            except Exception as ws_restart_err:
                logger.warning(f"⚠️ Impossible de redémarrer WebSocket global: {ws_restart_err}")

        lom = _live_order_manager or state.get_live_order_manager()
        mode_str = "🟡 LIVE DRY-RUN" if (lom and lom.dry_run) else ("🔴 LIVE RÉEL" if lom else "📝 PAPER")
            
        await add_log('INFO', f'Position clôturée [{mode_str}]', reason)
        wm = _ws_manager or state.get_ws_manager()
        if wm:
            await wm.emit('position_closed', result)
        
        try:
            from core.callbacks.position_check_loop import _emit_stats_update
            await _emit_stats_update()
        except Exception: pass
        
        return result
