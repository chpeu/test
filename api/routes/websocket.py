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

def _resolve_ws_manager(state):
    global _ws_manager
    get_ws_manager = getattr(state, 'get_ws_manager', None)
    set_ws_manager = getattr(state, 'set_ws_manager', None)
    ws_mgr = _ws_manager or (get_ws_manager() if callable(get_ws_manager) else None)
    if ws_mgr is None:
        from core.websocket_manager import get_websocket_manager
        ws_mgr = get_websocket_manager()
        if callable(set_ws_manager):
            set_ws_manager(ws_mgr)
    state_ws = get_ws_manager() if callable(get_ws_manager) else None
    if state_ws is None:
        if callable(set_ws_manager):
            set_ws_manager(ws_mgr)
    elif state_ws is not ws_mgr:
        logger.warning(
            "⚠️ [WS-DIAGNOSTIC] ws_manager mismatch: route=%s state=%s - alignement sur state",
            id(ws_mgr),
            id(state_ws),
        )
        ws_mgr = state_ws
    if _ws_manager is None or _ws_manager is not ws_mgr:
        _ws_manager = ws_mgr
    return ws_mgr

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
    ws_mgr = _resolve_ws_manager(state)
    headers = getattr(websocket, 'headers', None)
    user_agent = None
    origin = None
    if headers is not None:
        try:
            user_agent = headers.get('user-agent')
            origin = headers.get('origin')
        except Exception:
            user_agent = None
            origin = None
    
    try:
        logger.info(
            f"🔌 [WS-DEBUG] Nouvelle connexion WebSocket entrante: client={getattr(websocket, 'client', None)}, ua={user_agent}, origin={origin}"
        )
        
        # 🔥 DIAGNOSTIC: Vérifier ws_mgr
        logger.debug(f"🔍 [WS-DIAGNOSTIC] _ws_manager = {_ws_manager}")
        logger.debug(f"🔍 [WS-DIAGNOSTIC] state.get_ws_manager() = {state.get_ws_manager()}")
        logger.debug(f"🔍 [WS-DIAGNOSTIC] ws_mgr = {ws_mgr}")
        
        if not ws_mgr:
            logger.error("❌ WebSocketManager non trouvé")
            return
        
        logger.debug("🔍 [WS-DIAGNOSTIC] Appel ws_mgr.connect(websocket)...")
        await ws_mgr.connect(websocket)
        logger.debug("🔍 [WS-DIAGNOSTIC] ws_mgr.connect(websocket) terminé avec succès")

        connection_id = None
        try:
            get_conn_id = getattr(ws_mgr, 'get_connection_id', None)
            if callable(get_conn_id):
                connection_id = get_conn_id(websocket)
            else:
                conn_data_map = getattr(ws_mgr, 'connection_data', None)
                if isinstance(conn_data_map, dict) and websocket in conn_data_map:
                    connection_id = (conn_data_map.get(websocket) or {}).get('connection_id')
        except Exception:
            connection_id = None

        try:
            conn_data_map = getattr(ws_mgr, 'connection_data', None)
            if isinstance(conn_data_map, dict) and websocket in conn_data_map:
                conn_data = conn_data_map[websocket]
                if conn_data.get('user_agent') is None and user_agent:
                    conn_data['user_agent'] = user_agent
                if conn_data.get('origin') is None and origin:
                    conn_data['origin'] = origin
        except Exception:
            pass

        logger.debug(
            f"🔌 [WS-DEBUG] WebSocket accepté: id={connection_id}, client={getattr(websocket, 'client', None)}"
        )
        
        # Envoyer état initial
        try:
            status_data = (_app_state or state.app_state).copy()
            if status_data.get('active_position') and hasattr(status_data['active_position'], 'to_dict'):
                try:
                    status_data['active_position'] = status_data['active_position'].to_dict()
                except Exception:
                    status_data['active_position'] = None
            
            logger.debug(
                "� [WS-STATUS] Envoi status initial (keys=%s, active_position=%s)",
                list(status_data.keys()),
                bool(status_data.get('active_position'))
            )
            await ws_mgr.send_personal_message({
                'type': 'event',
                'event': 'status',
                'data': status_data
            }, websocket)
            logger.debug("✅ [WS-STATUS] Status initial envoyé")
        except Exception as e:
            logger.error(f"❌ [BACKEND-DEBUG] ERREUR ENVOI STATUS: {e}")
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
        
        # Envoyer server_hello pour handshake frontend
        try:
            await ws_mgr.send_personal_message({
                'type': 'server_hello',
                'timestamp': time.time(),
                'connection_id': connection_id,
                'session_id': getattr(state, 'session_id', None),
            }, websocket)
            logger.debug(f"👋 server_hello envoyé pour connexion {connection_id}")
            # Envoyer un ping de test pour confirmer que la connexion est bidirectionnelle
            ping_id = 9999
            try:
                conn_data_map = getattr(ws_mgr, 'connection_data', None)
                if isinstance(conn_data_map, dict) and websocket in conn_data_map:
                    conn_data = conn_data_map[websocket]
                    conn_data['server_ping_counter'] = int(conn_data.get('server_ping_counter', 0)) + 1
                    ping_id = conn_data['server_ping_counter']
                    now = time.time()
                    conn_data['last_server_ping_id'] = ping_id
                    conn_data['last_server_ping_ts'] = now
                    conn_data['last_message_type'] = 'out:ping_test'
            except Exception:
                pass
            await ws_mgr.send_personal_message({
                'type': 'ping',
                'timestamp': time.time(),
                'ping_id': ping_id,
            }, websocket)
            logger.debug(f"🏓 ping de test (ping_id={ping_id}) envoyé juste après server_hello")
        except Exception as e:
            logger.error(f"❌ Erreur envoi server_hello: {e}")
        
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
        
        # Boucle de réception avec gestion robuste des ping/pong
        try:
            while True:
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=180.0)
                except asyncio.TimeoutError:
                    # 🔥 FIX: Mécanisme ping simplifié et robuste + gestion surcharge
                    try:
                        now = time.time()
                        conn_data_map = getattr(ws_mgr, 'connection_data', None)
                        conn_data = None
                        if isinstance(conn_data_map, dict) and websocket in conn_data_map:
                            conn_data = conn_data_map[websocket]
                        
                        # Envoyer un ping simple sans vérifications complexes
                        ping_payload = {
                            'type': 'ping', 
                            'timestamp': now
                        }
                        
                        if conn_data:
                            # Incrémenter compteur ping
                            conn_data['server_ping_counter'] = int(conn_data.get('server_ping_counter', 0)) + 1
                            ping_payload['ping_id'] = conn_data['server_ping_counter']
                            
                            # 🔥 FIX CRITIQUE: Stocker ping_id pour validation pong
                            conn_data['last_server_ping_id'] = conn_data['server_ping_counter']
                            
                            # Mettre à jour timestamps
                            conn_data['last_server_ping_ts'] = now
                            conn_data['last_message_ts'] = now
                            conn_data['last_message_type'] = 'out:ping_keepalive'
                            
                            # Log minimal pour débugging
                            logger.debug(
                                f"📡 [WS-PING] Client {conn_data.get('connection_id', 'unknown')} "
                                f"ping #{conn_data['server_ping_counter']}"
                            )                          
                        # Envoyer le ping
                        ping_json = json.dumps(ping_payload, default=str)
                        if conn_data:
                            conn_data['message_out_count'] = int(conn_data.get('message_out_count', 0)) + 1
                            conn_data['bytes_out'] = int(conn_data.get('bytes_out', 0)) + len(ping_json)
                        
                        try:
                            await asyncio.wait_for(websocket.send_text(ping_json), timeout=3.0)
                        except asyncio.TimeoutError:
                            logger.warning("⚠️ [WS-PING-ERROR] Timeout envoi ping (3s) - fermeture connexion")
                            try:
                                await websocket.close(code=1000, reason="Ping send timeout")
                            except Exception:
                                pass
                            break
                        continue
                        
                    except Exception as e:
                        # 🔥 FIX: Gestion d'erreur robuste - éviter fermeture brutale pendant surcharge
                        logger.warning(f"⚠️ [WS-PING-ERROR] Erreur ping (surcharge possible): {e}")
                        # Attendre un peu avant de continuer si le serveur est surchargé
                        await asyncio.sleep(2.0)
                        continue
                
                conn_data_map = getattr(ws_mgr, 'connection_data', None)
                conn_data = None
                if isinstance(conn_data_map, dict):
                    conn_data = conn_data_map.get(websocket)
                if conn_data is not None:
                    conn_data['message_in_count'] = int(conn_data.get('message_in_count') or 0) + 1
                    conn_data['bytes_in'] = int(conn_data.get('bytes_in') or 0) + len(data)
                    conn_data['last_message_ts'] = time.time()

                try:
                    message = json.loads(data)
                    logger.debug(f"🔍 [WS-DEBUG] Message reçu brut: {data}")
                except json.JSONDecodeError:
                    if conn_data is not None:
                        conn_data['last_message_type'] = 'in:invalid_json'
                    logger.warning(f"⚠️ [WS-DEBUG] JSON invalide reçu: {data}")
                    continue
                
                msg_type = message.get('type')
                if conn_data is not None:
                    conn_data['last_message_type'] = f"in:{msg_type or 'unknown'}"
                
                if msg_type == 'command':
                    command = message.get('command')
                    params = message.get('params', {})
                    
                    # 🔍 DIAGNOSTIC: Tracer toutes les commandes reçues
                    connection_id = None
                    client_id = None
                    if conn_data is not None:
                        connection_id = conn_data.get('connection_id')
                        client_id = conn_data.get('client_id')
                    logger.debug(
                        "🔍 [WS-COMMAND] Commande reçue: '%s' params=%s client_id=%s conn_id=%s",
                        command,
                        params,
                        client_id,
                        connection_id
                    )
                    
                    if conn_data is not None:
                        conn_data['last_message_type'] = f"in:command:{command}"
                    
                    try:
                        result = await handle_client_command(command, params)
                        result_status = result.get('status') if isinstance(result, dict) else None
                        logger.debug(
                            "🔍 [WS-COMMAND] Commande '%s' exécutée (status=%s)",
                            command,
                            result_status or 'ok'
                        )
                    except Exception as e:
                        logger.error(f"❌ [WS-COMMAND] Erreur exécution commande '{command}': {e}")
                        result = {'error': str(e), 'status': 'error'}
                    
                    cmd_id = message.get('id')
                    if cmd_id is not None:
                        response_data = {
                            'type': 'command_response',
                            'id': cmd_id,
                            'command': command,
                            'result': result.get('status', 'unknown') if isinstance(result, dict) else result
                        }
                        # Ajouter les clés du result si c'est un dict
                        if isinstance(result, dict):
                            response_data.update(result)
                        
                        await ws_mgr.send_personal_message(response_data, websocket)
                
                elif msg_type == 'ping':
                    ping_id = message.get('ping_id')
                    client_ts = message.get('timestamp')
                    logger.debug(f"🏓 [WS-DEBUG] Ping reçu: ping_id={ping_id}, ts={client_ts}")
                    await ws_mgr.send_personal_message({
                        'type': 'pong',
                        'timestamp': time.time(),
                        'ping_id': ping_id,
                        'client_ts': client_ts,
                    }, websocket)
                    logger.debug(f"🏓 [WS-DEBUG] Pong envoyé en réponse à ping_id={ping_id}")

                elif msg_type == 'pong':
                    if conn_data is None:
                        logger.debug("⚠️ [WS-DEBUG] Pong reçu mais conn_data introuvable - ignoré")
                        continue
                    pong_ping_id = message.get('ping_id')
                    expected_ping_id = conn_data.get('last_server_ping_id')
                    connection_id = conn_data.get('connection_id', 'unknown')
                    now = time.time()
                    if expected_ping_id is None:
                        conn_data['last_server_pong_ts'] = now
                        conn_data['last_server_rtt_ms'] = None
                        logger.debug(
                            f"🏓 [WEBSOCKET-PONG-UNEXPECTED] Client {connection_id} pong#{pong_ping_id} reçu sans ping attendu"
                        )
                        continue
                    
                    if pong_ping_id == expected_ping_id:
                        conn_data['last_server_pong_ts'] = now
                        # Calculer RTT précis
                        last_ping_ts = conn_data.get('last_server_ping_ts')
                        if isinstance(last_ping_ts, (int, float)):
                            rtt_ms = round((now - last_ping_ts) * 1000.0, 2)
                            conn_data['last_server_rtt_ms'] = rtt_ms
                            
                            # ✅ LOG DEBUG: Pong valide reçu
                            logger.debug(
                                f"🏓 [WEBSOCKET-PONG-OK] Client {connection_id} répond: "
                                f"ping#{pong_ping_id} RTT={rtt_ms}ms, health=GOOD"
                            )
                        else:
                            # ⚠️ LOG DEBUG: Pong reçu mais pas de ping timestamp
                            conn_data['last_server_rtt_ms'] = None
                            logger.debug(
                                f"🏓 [WEBSOCKET-PONG-NO-TIMESTAMP] Client {connection_id} pong#{pong_ping_id} "
                                f"reçu mais pas de timestamp ping"
                            )
                    else:
                        # 🚨 LOG CRITIQUE: Pong avec ping_id incorrect - client désynchronisé
                        logger.error(
                            f"⚠️ [WEBSOCKET-PONG-DESYNC] Client {connection_id} DÉSYNCHRONISÉ: "
                            f"pong_id={pong_ping_id}, expected_id={expected_ping_id} - CLIENT PEUT ÊTRE BUGUÉ"
                        )

                elif msg_type == 'client_hello':
                    payload = message.get('context') or {}
                    client_id = message.get('client_id')
                    if conn_data is not None:
                        conn_data['client_info'] = payload
                        if client_id is not None:
                            conn_data['client_id'] = client_id
                        if conn_data.get('user_agent') is None:
                            conn_data['user_agent'] = payload.get('userAgent') or payload.get('user_agent')
                        if conn_data.get('origin') is None:
                            conn_data['origin'] = payload.get('origin')
                    await ws_mgr.send_personal_message({
                        'type': 'server_hello',
                        'timestamp': time.time(),
                        'connection_id': connection_id,
                        'client_id': client_id,
                        'session_id': getattr(state, 'session_id', None),
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

        except WebSocketDisconnect as e:
            close_code = getattr(e, 'code', None)
            close_reason = getattr(e, 'reason', None)
            last_msg_age_s = None
            try:
                conn_data_map = getattr(ws_mgr, 'connection_data', None)
                if isinstance(conn_data_map, dict) and websocket in conn_data_map:
                    last_ts = conn_data_map[websocket].get('last_message_ts')
                    if isinstance(last_ts, (int, float)):
                        last_msg_age_s = round(time.time() - last_ts, 3)
            except Exception:
                pass
            logger.info(
                f"👋 WebSocket déconnecté (id={connection_id}, code={close_code}, reason={close_reason}, client={getattr(websocket, 'client', None)}, last_msg_age_s={last_msg_age_s})"
            )
        except Exception as e:
            logger.error(
                f"❌ Erreur inattendue boucle WebSocket (id={connection_id}): {type(e).__name__}: {e}",
                exc_info=True,
            )
            # Laisser la connexion se fermer naturellement
        finally:
            try:
                await ws_mgr.disconnect(websocket)
            except Exception:
                pass
    
    except Exception as e:
        logger.critical(f"❌ CRITICAL: Erreur fatale dans websocket_endpoint: {e}", exc_info=True)
        # Laisser la connexion se fermer naturellement

async def handle_client_command(command: str, params: dict):
    """Exécuter une commande du client via WebSocket en utilisant les modules dédiés"""
    from core.state_manager import get_state_manager
    state = get_state_manager()
    from core.bootstrap import init_instances, run_initial_top_pairs_scan
    from utils.logging_utils import add_log
    
    if command == 'start_scanner':
        await init_instances()
        ws_mgr = _ws_manager or state.get_ws_manager()
        
        # Démarrer le scheduler si disponible
        sched = state.get_scheduler()
        if sched:
            try:
                sched.start()
                await add_log('INFO', 'Scanner démarré', 'Scheduler et boucles automatiques activées via WebSocket')
            except Exception as e:
                await add_log('ERROR', 'Erreur démarrage scanner', f'Impossible de démarrer le scheduler: {e}')
                return {'status': 'error', 'error': str(e), 'is_scanning': False}
        
        # Mettre à jour l'état
        state.set_is_scanning(True)
        
        # Lancer un scan initial si pas de top pairs
        if not state.top_pairs:
            asyncio.create_task(run_initial_top_pairs_scan())
        
        # Émettre les événements WebSocket
        if ws_mgr:
            await ws_mgr.emit('scan_started', {'timestamp': time.time()})
            await ws_mgr.emit('status', {'is_scanning': True})
        
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
        try:
            return await initiate_backend_reboot(reason=reason, source='ws')
        except TypeError:
            return await initiate_backend_reboot(reason=reason)

    elif command == 'log_config':
        # Simple log pas besoin de modulariser pour l'instant
        config_key = params.get('key', 'unknown')
        config_change = params.get('change', 'unknown')
        await add_log('INFO', f'Config modifiée: {config_key}', str(config_change))
        return {'status': 'logged', 'key': config_key, 'change': config_change}

    elif command == 'set_quiet_mode':
        from utils.logger import apply_quiet_mode, is_quiet_mode
        enabled = params.get('enabled')
        if enabled is None:
            enabled = not is_quiet_mode()
        enabled = bool(enabled)
        apply_quiet_mode(enabled)
        state.set_quiet_mode(enabled)
        if _app_state is not None:
            try:
                _app_state['quiet_mode'] = enabled
            except Exception:
                pass
        await add_log('INFO', 'Quiet mode', 'Activé' if enabled else 'Désactivé')
        ws_mgr = _ws_manager or state.get_ws_manager()
        if ws_mgr:
            await ws_mgr.emit('quiet_mode', {
                'enabled': enabled,
                'timestamp': time.time()
            })
        return {'status': 'success', 'quiet_mode': enabled}
    
    # Vérifier si la commande est enregistrée dynamiquement
    ws_mgr = _ws_manager or state.get_ws_manager()
    if ws_mgr and command in ws_mgr._command_handlers:
        return await ws_mgr.handle_command(command, params, None)
        
    return {'status': 'error', 'message': f'Unknown command: {command}'}
