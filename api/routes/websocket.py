"""
Native WebSocket Endpoint - Bidirectional native WebSocket
"""

import asyncio
import logging
import json
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Variables globales injectées par main.py
_ws_manager = None
_app_state = None
_position_manager = None
_scheduler = None
_price_provider = None

def set_websocket_manager(wm):
    global _ws_manager
    _ws_manager = wm

def set_app_state(as_):
    global _app_state
    _app_state = as_

def set_position_manager(pm):
    global _position_manager
    _position_manager = pm

def set_scheduler(s):
    global _scheduler
    _scheduler = s

def set_price_provider(pp):
    global _price_provider
    _price_provider = pp

router = APIRouter(tags=["websocket"])

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Endpoint WebSocket bidirectionnel natif"""
    from core.state_manager import get_state_manager
    state = get_state_manager()
    ws_mgr = _ws_manager or state.get_ws_manager()
    
    try:
        logger.info(f"🔌 [WS-DEBUG] Nouvelle connexion WebSocket entrante: {websocket.client}")
        
        if not ws_mgr:
            logger.error("❌ WebSocketManager non trouvé, fermeture 1011")
            await websocket.close(code=1011)
            return
            
        await ws_mgr.connect(websocket)
        
        # Envoyer état initial
        try:
            status_data = (_app_state or state.app_state).copy()
            if status_data.get('active_position') and hasattr(status_data['active_position'], 'to_dict'):
                try:
                    status_data['active_position'] = status_data['active_position'].to_dict()
                except Exception:
                    status_data['active_position'] = None
            
            await ws_mgr.send_personal_message({
                'type': 'event',
                'event': 'status',
                'data': status_data
            }, websocket)
        except Exception as e:
            logger.error(f"❌ Erreur envoi état initial: {e}")
        
        # Envoyer les derniers logs
        try:
            logs = (_app_state or state.app_state).get('logs', [])[-50:]
            for log_entry in logs:
                await ws_mgr.send_personal_message({
                    'type': 'event',
                    'event': 'log',
                    'data': log_entry
                }, websocket)
        except Exception:
            pass
        
        # Reset session frontend - 🔥 REMOVED: Should not clear history on every new connection
        # only on real backend startup/reboot via lifespan or command.
        # try:
        #     await ws_mgr.send_personal_message({
        #         'type': 'event',
        #         'event': 'reset_session',
        #         'data': {
        #             'timestamp': time.time(),
        #             'reason': 'new_connection'
        #         }
        #     }, websocket)
        # except Exception:
        #     pass
        
        # Boucle de réception
        try:
            while True:
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                except asyncio.TimeoutError:
                    try:
                        await ws_mgr.send_personal_message({
                            'type': 'ping',
                            'timestamp': time.time()
                        }, websocket)
                        continue
                    except Exception:
                        break
                
                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    continue
                
                msg_type = message.get('type')
                
                if msg_type == 'command':
                    command = message.get('command')
                    params = message.get('params', {})
                    command_id = message.get('id')
                    
                    try:
                        result = await handle_client_command(command, params)
                        await ws_mgr.send_personal_message({
                            'type': 'command_response',
                            'id': command_id,
                            'command': command,
                            'result': result,
                            'status': 'success',
                            'timestamp': time.time()
                        }, websocket)
                    except Exception as e:
                        logger.error(f"Erreur commande {command}: {e}")
                        await ws_mgr.send_personal_message({
                            'type': 'command_error',
                            'id': command_id,
                            'command': command,
                            'error': str(e),
                            'timestamp': time.time()
                        }, websocket)
                
                elif msg_type == 'ping':
                    await ws_mgr.send_personal_message({
                        'type': 'pong',
                        'timestamp': time.time()
                    }, websocket)
                
                elif msg_type == 'subscribe':
                    channel = message.get('channel', 'all')
                    ws_mgr.subscribe(websocket, channel)
                    await ws_mgr.send_personal_message({
                        'type': 'subscribed',
                        'channel': channel,
                        'timestamp': time.time()
                    }, websocket)
                
                elif msg_type == 'unsubscribe':
                    channel = message.get('channel', 'all')
                    ws_mgr.unsubscribe(websocket, channel)
                    await ws_mgr.send_personal_message({
                        'type': 'unsubscribed',
                        'channel': channel,
                        'timestamp': time.time()
                    }, websocket)
                
                elif msg_type == 'request':
                    request_type = message.get('request_type')
                    request_id = message.get('id')
                    
                    if request_type == 'logs':
                        await ws_mgr.send_personal_message({
                            'type': 'request_response',
                            'id': request_id,
                            'request_type': request_type,
                            'data': (_app_state or state.app_state).get('logs', [])[-100:]
                        }, websocket)
                    
                    elif request_type == 'position':
                        pm = _position_manager or state.get_position_manager()
                        pos = pm.active_position if pm else None
                        await ws_mgr.send_personal_message({
                            'type': 'request_response',
                            'id': request_id,
                            'request_type': request_type,
                            'data': pos.to_dict() if pos else None
                        }, websocket)

                    elif request_type == 'trade_events':
                        trade_id = (message.get('params') or {}).get('trade_id')
                        events = []
                        error_msg = None
                        if trade_id:
                            try:
                                from core.postgresql_datalogger import get_pg_datalogger
                                pg_logger = get_pg_datalogger()
                                if pg_logger:
                                    events = await asyncio.to_thread(pg_logger.get_trade_events, trade_id)
                                else:
                                    error_msg = 'PostgreSQL logger désactivé'
                            except Exception as trade_events_err:
                                error_msg = str(trade_events_err)
                        else:
                            error_msg = 'trade_id manquant'

                        await ws_mgr.send_personal_message({
                            'type': 'request_response',
                            'id': request_id,
                            'request_type': request_type,
                            'data': {
                                'trade_id': trade_id,
                                'events': events,
                                'error': error_msg
                            }
                        }, websocket)
                    
                    elif request_type == 'state':
                        try:
                            from api.routes.dashboard import get_complete_state
                            state_response = await get_complete_state()
                            # Extraire les données de JSONResponse
                            if hasattr(state_response, 'body'):
                                state_data = json.loads(state_response.body.decode())
                            else:
                                state_data = state_response
                                
                            await ws_mgr.send_personal_message({
                                'type': 'request_response',
                                'id': request_id,
                                'request_type': request_type,
                                'data': state_data
                            }, websocket)
                        except Exception as state_err:
                            logger.error(f"❌ Erreur récupération state via WebSocket: {state_err}")
                            await ws_mgr.send_personal_message({
                                'type': 'request_response',
                                'id': request_id,
                                'request_type': request_type,
                                'error': str(state_err)
                            }, websocket)

        except WebSocketDisconnect:
            logger.info(f"👋 WebSocket déconnecté proprement: {websocket.client}")
            await ws_mgr.disconnect(websocket)
        except Exception as e:
            logger.error(f"❌ Erreur inattendue boucle WebSocket: {e}", exc_info=True)
            await ws_mgr.disconnect(websocket)
    
    except Exception as e:
        logger.critical(f"❌ CRITICAL: Erreur fatale dans websocket_endpoint: {e}", exc_info=True)
        try:
            await websocket.close(code=1011)
        except:
            pass

async def handle_client_command(command: str, params: dict):
    """Exécuter une commande du client via WebSocket en utilisant les modules dédiés"""
    from core.state_manager import get_state_manager
    state = get_state_manager()
    from core.bootstrap import init_instances, run_initial_top_pairs_scan
    from utils.logging_utils import add_log
    
    if command == 'start_scanner':
        await init_instances()
        ws_mgr = _ws_manager or state.get_ws_manager()
        if ws_mgr:
            await ws_mgr.emit('scan_started', {'timestamp': time.time()})
            await ws_mgr.emit('status', {'is_scanning': True})
        
        state.set_is_scanning(True)
        
        if not state.top_pairs:
            asyncio.create_task(run_initial_top_pairs_scan())
        
        # sched = _scheduler or state.get_scheduler()
        # if sched:
        #     sched.start()
        #     await add_log('INFO', 'Scanner démarré', 'Boucles automatiques activées')
        
        return {'status': 'started', 'is_scanning': True}
    
    elif command == 'stop_scanner':
        from api.routes.scanner import perform_stop_scanner
        return await perform_stop_scanner()
    
    elif command == 'close_position':
        from api.routes.position import perform_close_position
        reason = params.get('reason', 'MANUAL')
        exit_price = params.get('exit_price')
        result = await perform_close_position(reason=reason, exit_price=exit_price)
        return {'status': 'closed', 'result': result}

    elif command == 'update_config':
        from api.routes.config import perform_config_update
        updated = await perform_config_update(params)
        return {'status': 'success', 'updated': updated}

    elif command == 'update_telegram_config':
        from api.routes.notifications import perform_telegram_config_update
        updated = await perform_telegram_config_update(params)
        return {'status': 'success', 'updated': updated}

    elif command == 'test_telegram':
        from api.routes.notifications import perform_telegram_test
        return await perform_telegram_test()

    elif command == 'reboot_backend':
        from api.routes.dashboard import initiate_backend_reboot
        reason = params.get('reason', 'manual')
        return await initiate_backend_reboot(reason=reason)

    elif command == 'log_config':
        # Simple log pas besoin de modulariser pour l'instant
        config_key = params.get('key', 'unknown')
        config_change = params.get('change', 'unknown')
        await add_log('INFO', f'Config modifiée: {config_key}', str(config_change))
        return {'status': 'logged', 'key': config_key, 'change': config_change}
    
    # Vérifier si la commande est enregistrée dynamiquement
    ws_mgr = _ws_manager or state.get_ws_manager()
    if ws_mgr and command in ws_mgr._command_handlers:
        return await ws_mgr.handle_command(command, params, None)
        
    return {'status': 'error', 'message': f'Unknown command: {command}'}
