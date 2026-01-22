"""
SL Services - Real-time Stop Loss management and order scheduling
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from core.state_manager import get_state_manager
from core.exceptions import PositionError, OrderExecutionError, DatabaseError, WebSocketError, NetworkError, APIError

logger = logging.getLogger(__name__)

# Track pending SL tasks globally within this service
_pending_sl_tasks: Dict[str, asyncio.Task] = {}

async def setup_realtime_sl_check(position: Any, price_provider_instance: Any) -> None:
    """
    Configure real-time SL checking via WebSocket.
    
    Args:
        position: Active position (Position object or dict)
        price_provider_instance: HybridPriceProvider instance
    """
    if not position or not price_provider_instance:
        return
    
    state = get_state_manager()
    
    # Extract position parameters
    symbol = position.symbol if hasattr(position, 'symbol') else position.get('symbol')
    direction = position.direction if hasattr(position, 'direction') else position.get('direction')
    sl_level = position.sl if hasattr(position, 'sl') else position.get('sl')
    entry_price = position.entry if hasattr(position, 'entry') else position.get('entry')
    
    if not all([symbol, direction, sl_level, entry_price]):
        logger.warning(f"⚠️ Cannot setup real-time SL: missing parameters for {symbol}")
        return
    
    async def on_sl_triggered(exit_price: float, reason: str):
        """Callback triggered when SL is hit via WebSocket tick"""
        logger.info(f"⚡ Real-time SL triggered: {symbol} @ {exit_price:.8f} | Reason: {reason}")
        
        async with state.lock("position"):
            pos_mgr = state.get_position_manager()
            if not pos_mgr or not pos_mgr.active_position:
                logger.debug("Position already closed, ignoring SL callback")
                return
            
            try:
                # Close the position
                result = pos_mgr.close_position(exit_price=exit_price, reason=reason)
                
                # Update state
                state.set_active_position(None)
                
                # Archive in history
                if result:
                    result['timestamp'] = datetime.now().isoformat()
                    state.add_trade(result)
                    
                    # Persistent save (we'll need a way to call this without main.py)
                    # For now, StateManager handles the in-memory list
                
                # Disable SL callback
                if price_provider_instance:
                    price_provider_instance.set_sl_check_callback(None)
                
                # Cancel any pending exchange SL order placement
                cancel_pending_sl_task(symbol)
                
                # Notify via WebSocket
                ws_mgr = state.get_ws_manager()
                if ws_mgr:
                    await ws_mgr.emit('position_closed', result)
                    await ws_mgr.emit('stats_update', state.stats.to_dict())
                
                logger.info(
                    f"✅ Position closed via real-time SL: {symbol} | "
                    f"PnL: {result.get('pnl_percent', 0):+.2f}% | "
                    f"Reason: {reason}"
                )
                
            except Exception as e:
                logger.error(f"❌ Error during real-time SL closure for {symbol}: {e}", exc_info=True)
    
    # Configure callback in price provider
    price_provider_instance.set_sl_check_callback(
        callback=on_sl_triggered,
        symbol=symbol,
        direction=direction,
        sl_level=sl_level,
        entry_price=entry_price
    )
    
    logger.info(
        f"🛡️ Real-time SL configured: {symbol} {direction} | "
        f"SL={sl_level:.8f} | Entry={entry_price:.8f}"
    )

async def schedule_sl_order_placement(position: Any, delay_seconds: float = 3.0) -> None:
    """
    Schedule SL order placement on exchange after a delay.
    """
    global _pending_sl_tasks
    
    if not position:
        return
    
    state = get_state_manager()
    symbol = position.symbol if hasattr(position, 'symbol') else position.get('symbol')
    if not symbol:
        return
    
    # Cancel previous task for this symbol
    if symbol in _pending_sl_tasks:
        old_task = _pending_sl_tasks[symbol]
        if not old_task.done():
            old_task.cancel()
            logger.debug(f"🛑 Previous SL task cancelled for {symbol}")
    
    async def _delayed_sl_placement():
        try:
            logger.info(f"⏳ Waiting {delay_seconds}s before placing SL order on exchange for {symbol}...")
            await asyncio.sleep(delay_seconds)
            
            pos_mgr = state.get_position_manager()
            if not pos_mgr or not pos_mgr.active_position:
                return
            
            active_pos = pos_mgr.active_position
            if active_pos.symbol != symbol:
                return
            
            entry_price = active_pos.entry_fill_price or active_pos.entry
            sl_level = active_pos.sl
            direction = active_pos.direction
            
            if not all([entry_price, sl_level, direction]):
                logger.warning(f"⚠️ Missing parameters for exchange SL: {symbol}")
                return
            
            live_ord_mgr = state.get_live_order_manager()
            if not live_ord_mgr:
                return
            
            if live_ord_mgr.dry_run:
                logger.info(f"🛡️ [DRY_RUN] Simulated exchange SL order: {symbol} {direction} | SL={sl_level:.8f}")
                return
            
            if hasattr(live_ord_mgr, 'place_stop_loss_order'):
                result = await live_ord_mgr.place_stop_loss_order(
                    symbol=symbol,
                    direction=direction,
                    sl_price=sl_level,
                    entry_price=entry_price
                )
                if result and result.success:
                    logger.info(f"✅ SL order placed on exchange: {symbol} | SL={sl_level:.8f}")
                    active_pos.sl_order_id = result.order_id
                else:
                    logger.warning(f"⚠️ Failed to place exchange SL: {result.error_message if result else 'Unknown error'}")
            
        except asyncio.CancelledError:
            logger.info(f"🛑 SL task cancelled for {symbol}")
        except Exception as e:
            logger.error(f"❌ Unexpected error in SL placement for {symbol}: {e}", exc_info=True)
        finally:
            if symbol in _pending_sl_tasks:
                del _pending_sl_tasks[symbol]
    
    task = asyncio.create_task(_delayed_sl_placement())
    _pending_sl_tasks[symbol] = task

def cancel_pending_sl_task(symbol: str) -> None:
    """Cancel pending SL task for a symbol."""
    global _pending_sl_tasks
    if symbol in _pending_sl_tasks:
        task = _pending_sl_tasks[symbol]
        if not task.done():
            task.cancel()
            logger.info(f"🛑 SL task cancelled for {symbol} (position closed)")
        del _pending_sl_tasks[symbol]
