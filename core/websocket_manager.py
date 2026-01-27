"""
Gestionnaire WebSocket natif pour Trade Cursor
Remplace Socket.IO pour des performances optimales
"""
import asyncio
import json
import logging
import time
from typing import Dict, Set, Optional
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Gestionnaire WebSocket natif avec :
    - Gestion des connexions multiples
    - Broadcast automatique
    - Reconnexion côté client
    - Performance optimale
    - Support rooms/namespaces
    - Communication bidirectionnelle
    - Système de commandes (handlers)
    """
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.connection_data: Dict[WebSocket, dict] = {}
        self.rooms: Dict[str, Set[WebSocket]] = {}  # Support rooms
        self._lock: Optional[asyncio.Lock] = None  # 🔥 Lazy initialization
        self._connection_counter: int = 0
        # 🔥 LIVE TRADING: Système de commandes WebSocket
        self._command_handlers: Dict[str, callable] = {}
    
    @property
    def lock(self) -> asyncio.Lock:
        """Lazy initialization of the lock to ensure it's in the correct event loop"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock
    
    def command(self, name: str):
        """
        Décorateur pour enregistrer un handler de commande WebSocket
        
        Usage:
            @ws_manager.command('get_live_config')
            async def handle_get_live_config(data: dict, websocket):
                return {'success': True, ...}
        """
        def decorator(func):
            self._command_handlers[name] = func
            logger.debug(f"📡 Commande WebSocket enregistrée: {name}")
            return func
        return decorator
    
    def register_command(self, name: str, handler: callable):
        """Enregistrer un handler de commande programmatiquement"""
        self._command_handlers[name] = handler
        logger.debug(f"📡 Commande WebSocket enregistrée: {name}")
    
    async def handle_command(self, command_name: str, data: dict, websocket: WebSocket) -> dict:
        """
        Exécuter une commande WebSocket et retourner le résultat
        
        Args:
            command_name: Nom de la commande
            data: Données de la commande
            websocket: WebSocket source
            
        Returns:
            Résultat du handler (dict)
        """
        if command_name not in self._command_handlers:
            logger.warning(f"⚠️ Commande WebSocket inconnue: {command_name}")
            return {'success': False, 'error': f'Unknown command: {command_name}'}
        
        try:
            handler = self._command_handlers[command_name]
            # Appeler le handler (peut être async ou sync)
            if asyncio.iscoroutinefunction(handler):
                result = await handler(data, websocket)
            else:
                result = handler(data, websocket)
            
            # Gérer les résultats JSONResponse de FastAPI
            if hasattr(result, 'body'):
                import json
                return json.loads(result.body)
            return result if result else {'success': True}
        except Exception as e:
            logger.error(f"❌ Erreur commande {command_name}: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_registered_commands(self) -> list:
        """Retourner la liste des commandes enregistrées"""
        return list(self._command_handlers.keys())
    
    async def connect(self, websocket: WebSocket):
        """Accepter une nouvelle connexion WebSocket"""
        await websocket.accept()
        async with self.lock:
            self._connection_counter += 1
            connection_id = self._connection_counter
            self.active_connections.add(websocket)
            self.connection_data[websocket] = {
                'connection_id': connection_id,
                'client': getattr(websocket, 'client', None),
                'connected_at': datetime.now().isoformat(),
                'connected_at_ts': time.time(),
                'last_ping': datetime.now().isoformat(),
                'last_message_ts': time.time(),
                'last_message_type': 'connect',
                'message_in_count': 0,
                'message_out_count': 0,
                'bytes_in': 0,
                'bytes_out': 0,
                'server_ping_counter': 0,
                'last_server_ping_id': None,
                'last_server_ping_ts': None,
                'last_server_pong_ts': None,
                'last_server_rtt_ms': None,
                'client_info': None,
                'user_agent': None,
                'origin': None,
            }
        logger.info(
            f"✅ WebSocket connecté (id={connection_id}, client={getattr(websocket, 'client', None)}, total: {len(self.active_connections)})"
        )
    
    async def disconnect(self, websocket: WebSocket):
        """Déconnecter un WebSocket (optimisé)"""
        conn_data = self.connection_data.get(websocket) or {}
        connection_id = conn_data.get('connection_id')
        client = conn_data.get('client') or getattr(websocket, 'client', None)
        connected_at_ts = conn_data.get('connected_at_ts')
        duration_s = None
        if isinstance(connected_at_ts, (int, float)):
            duration_s = round(time.time() - connected_at_ts, 3)
        msg_in = conn_data.get('message_in_count')
        msg_out = conn_data.get('message_out_count')
        bytes_in = conn_data.get('bytes_in')
        bytes_out = conn_data.get('bytes_out')
        last_message_type = conn_data.get('last_message_type')
        last_message_ts = conn_data.get('last_message_ts')
        last_message_age_s = None
        if isinstance(last_message_ts, (int, float)):
            last_message_age_s = round(time.time() - last_message_ts, 3)
        rtt_ms = conn_data.get('last_server_rtt_ms')
        user_agent = conn_data.get('user_agent')
        origin = conn_data.get('origin')
        
        # 🔥 WEBSOCKET-FIX: Logs détaillés pour diagnostiquer les déconnexions
        disconnect_reason = "unknown"
        websocket_state = getattr(websocket, 'client_state', 'unknown')
        try:
            if hasattr(websocket, 'close_code'):
                disconnect_reason = f"close_code_{websocket.close_code}"
            elif hasattr(websocket, 'client_state') and websocket.client_state == 'disconnected':
                disconnect_reason = "client_disconnected"
        except Exception:
            pass
            
        async with self.lock:
            self.active_connections.discard(websocket)
            self.connection_data.pop(websocket, None)
            # 🔥 OPTIMISATION: Nettoyer aussi des rooms en une seule passe
            for room_connections in self.rooms.values():
                room_connections.discard(websocket)
                
        # 🔥 WEBSOCKET-FIX: Log détaillé pour diagnostiquer les déconnexions
        logger.warning(
            f"🔌 [WEBSOCKET-FIX] WebSocket déconnecté: id={connection_id}, client={client}, "
            f"reason={disconnect_reason}, state={websocket_state}, duration_s={duration_s}, "
            f"in={msg_in}, out={msg_out}, bytes_in={bytes_in}, bytes_out={bytes_out}, "
            f"last_msg={last_message_type}, last_msg_age_s={last_message_age_s}, rtt_ms={rtt_ms}, "
            f"ua={user_agent}, origin={origin}, remaining_connections={len(self.active_connections)}"
        )
        
        # 🔥 WEBSOCKET-FIX: Si c'est une déconnexion rapide (< 30s), c'est suspect
        if duration_s and duration_s < 30:
            logger.error(
                f"🚨 [WEBSOCKET-FIX] DÉCONNEXION RAPIDE DÉTECTÉE: {duration_s}s - possible crash backend!"
            )
    
    async def send_personal_message(self, message: dict, websocket: WebSocket, timeout: float = 5.0):
        """Envoyer un message à un WebSocket spécifique"""
        try:
            message_json = json.dumps(message, default=str)
            conn_data = self.connection_data.get(websocket)
            if conn_data is not None:
                conn_data['last_message_ts'] = time.time()
                conn_data['last_message_type'] = f"out:{message.get('type') or 'unknown'}"
                conn_data['message_out_count'] = int(conn_data.get('message_out_count') or 0) + 1
                conn_data['bytes_out'] = int(conn_data.get('bytes_out') or 0) + len(message_json)
            await asyncio.wait_for(websocket.send_text(message_json), timeout=timeout)
        except asyncio.TimeoutError:
            await self.disconnect(websocket)
        except (WebSocketDisconnect, ConnectionError, RuntimeError):
            await self.disconnect(websocket)
        except Exception as e:
            logger.error(f"❌ Erreur envoi message WebSocket: {e}")
            await self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        """Diffuser un message à tous les clients connectés (optimisé pour performances maximales)"""
        if not self.active_connections:
            return
        
        # 🔥 OPTIMISATION: Créer le message JSON une seule fois avec encodeur robuste
        try:
            message_json = json.dumps(message, default=str)
        except Exception as e:
            logger.error(f"❌ Erreur sérialisation JSON broadcast: {e}")
            return
        
        # 🔥 FIX: Créer une copie de la liste pour éviter les modifications pendant l'itération
        connections_to_send = list(self.active_connections)
        if not connections_to_send:
            return

        out_type = f"out:{message.get('type') or 'unknown'}"
        out_ts = time.time()
        
        # 🔥 OPTIMISATION: Envoyer à tous les clients en parallèle avec asyncio.gather
        async def send_to_connection(connection):
            try:
                # 🔥 FIX: Vérifier que la connexion est toujours active
                if connection not in self.active_connections:
                    return None
                conn_data = self.connection_data.get(connection)
                if conn_data is not None:
                    conn_data['last_message_ts'] = out_ts
                    conn_data['last_message_type'] = out_type
                    conn_data['message_out_count'] = int(conn_data.get('message_out_count') or 0) + 1
                    conn_data['bytes_out'] = int(conn_data.get('bytes_out') or 0) + len(message_json)
                await asyncio.wait_for(connection.send_text(message_json), timeout=5.0)
                return None  # Succès
            except asyncio.TimeoutError:
                return connection  # Timeout - nettoyer connexion
            except (WebSocketDisconnect, ConnectionError, RuntimeError) as e:
                # 🔥 FIX: Ignorer les erreurs de déconnexion normales
                return connection  # Échec - retourner connexion à nettoyer
            except Exception as e:
                # 🔥 FIX: Logger seulement les erreurs inattendues
                logger.debug(f"⚠️ Erreur broadcast WebSocket: {e}")
                return connection  # Échec - retourner connexion à nettoyer
        
        # Exécuter tous les envois en parallèle avec protection contre event loop fermée
        try:
            results = await asyncio.gather(
                *[send_to_connection(conn) for conn in connections_to_send],
                return_exceptions=True
            )
        except RuntimeError as e:
            # Event loop fermée pendant l'envoi - ignorer silencieusement
            logger.debug(f"⚠️ Event loop fermée pendant broadcast: {e}")
            return
        
        # 🔥 FIX: Nettoyer les connexions déconnectées (filtrer les exceptions et None)
        disconnected = []
        for i, result in enumerate(results):
            if result is not None and not isinstance(result, Exception):
                # C'est une connexion à nettoyer
                if i < len(connections_to_send):
                    disconnected.append(connections_to_send[i])
            elif isinstance(result, Exception):
                # Exception levée - nettoyer la connexion correspondante
                if i < len(connections_to_send):
                    disconnected.append(connections_to_send[i])
        
        if disconnected:
            async with self.lock:
                for conn in disconnected:
                    self.active_connections.discard(conn)
                    self.connection_data.pop(conn, None)
                    # Nettoyer aussi des rooms
                    for room_connections in self.rooms.values():
                        room_connections.discard(conn)
    
    async def emit(self, event: str, data: any = None):
        """
        Émettre un événement (compatible avec l'API Socket.IO)
        
        Args:
            event: Nom de l'événement
            data: Données à envoyer
        """
        from core.state_manager import get_state_manager
        state = get_state_manager()
        
        message = {
            'type': 'event',
            'event': event,
            'data': data,
            'session_id': state.session_id,  # 🔥 Propager session_id avec chaque événement
            'timestamp': datetime.now().isoformat()
        }
        await self.broadcast(message)
    
    async def send_status(self, status_data: dict):
        """Envoyer un événement status (optimisé)"""
        await self.emit('status', status_data)
    
    async def send_log(self, log_entry: dict):
        """Envoyer un log (optimisé)"""
        await self.emit('log', log_entry)
    
    async def send_position_update(self, position_data: dict):
        """Envoyer une mise à jour de position (optimisé)"""
        await self.emit('position_update', position_data)
    
    async def send_position_opened(self, position_data: dict):
        """Envoyer événement position ouverte (optimisé)"""
        await self.emit('position_opened', position_data)
    
    async def send_position_closed(self, result: dict):
        """Envoyer événement position fermée (optimisé)"""
        await self.emit('position_closed', result)
    
    async def send_stats_update(self, stats_data: dict):
        """Envoyer mise à jour des stats (optimisé)"""
        await self.emit('stats_update', stats_data)
    
    async def send_top_pairs_update(self, pairs: list):
        """Envoyer mise à jour des top pairs (optimisé)"""
        await self.emit('top_pairs_update', {'pairs': pairs})
    
    async def send_config_change(self, config_data: dict):
        """Envoyer changement de config (optimisé)"""
        await self.emit('config_change', config_data)
    
    async def send_scan_started(self, data: dict = None):
        """Envoyer événement scan démarré (optimisé)"""
        await self.emit('scan_started', data or {})
    
    async def send_scan_complete(self, data: dict = None):
        """Envoyer événement scan terminé (optimisé)"""
        await self.emit('scan_complete', data or {})
    
    async def send_scan_progress(self, progress: int):
        """Envoyer progression du scan (optimisé)"""
        await self.emit('scan_progress', {'progress': progress})
    
    def get_connection_count(self) -> int:
        """Retourner le nombre de connexions actives"""
        return len(self.active_connections)

    def get_connection_id(self, websocket: WebSocket) -> Optional[int]:
        """Retourner l'identifiant interne de la connexion"""
        conn_data = self.connection_data.get(websocket)
        if not conn_data:
            return None
        return conn_data.get('connection_id')
    
    async def ping_all(self):
        """Envoyer un ping à tous les clients (keep-alive) avec monitoring amélioré"""
        if not self.active_connections:
            return
        
        now = time.time()
        timestamp_iso = datetime.now().isoformat()
        
        # 🔥 FIX: Vérifier les connexions inactives avant d'envoyer des pings
        inactive_connections = []
        
        for websocket in list(self.active_connections):
            conn_data = self.connection_data.get(websocket)
            if conn_data:
                last_pong_ts = conn_data.get('last_server_pong_ts', 0) or 0
                last_ping_ts = conn_data.get('last_server_ping_ts', 0) or 0
                
                # Identifier les connexions qui ne répondent plus depuis >90s
                if last_ping_ts > 0 and (now - last_ping_ts) > 90.0 and last_pong_ts < last_ping_ts:
                    logger.error(
                        f"🚨 [WEBSOCKET-MONITOR] Connexion inactive détectée: client {conn_data.get('connection_id')} "
                        f"(pas de pong depuis {now - last_pong_ts:.1f}s, dernier ping il y a {now - last_ping_ts:.1f}s)"
                    )
                    inactive_connections.append(websocket)
        
        # Nettoyer les connexions inactives
        if inactive_connections:
            for websocket in inactive_connections:
                try:
                    await websocket.close(code=1000, reason="Ping timeout - connection inactive")
                except Exception:
                    pass
                await self.disconnect(websocket)
        
        # Envoyer ping aux connexions actives restantes
        if self.active_connections:
            message = {
                'type': 'ping',
                'timestamp': timestamp_iso
            }
            logger.debug(f"📡 [WEBSOCKET-MONITOR] Envoi ping keep-alive à {len(self.active_connections)} clients")
            await self.broadcast(message)
    
    def subscribe(self, websocket: WebSocket, room: str):
        """S'abonner à une room"""
        if room not in self.rooms:
            self.rooms[room] = set()
        self.rooms[room].add(websocket)
        logger.debug(f"📡 WebSocket abonné à room: {room}")
    
    def unsubscribe(self, websocket: WebSocket, room: str):
        """Se désabonner d'une room"""
        if room in self.rooms:
            self.rooms[room].discard(websocket)
            logger.debug(f"📡 WebSocket désabonné de room: {room}")
    
    async def emit_to_room(self, event: str, data: any = None, room: str = None):
        """Émettre vers une room spécifique (optimisé pour performances maximales)"""
        if room and room in self.rooms:
            message = {
                'type': 'event',
                'event': event,
                'data': data,
                'timestamp': datetime.now().isoformat()
            }
            message_json = json.dumps(message)
            
            # 🔥 OPTIMISATION: Envoyer en parallèle avec asyncio.gather
            async def send_to_connection(connection):
                try:
                    await connection.send_text(message_json)
                    return None  # Succès
                except Exception as e:
                    logger.warning(f"⚠️ Erreur emit room {room}: {e}")
                    return connection  # Échec
            
            room_connections = list(self.rooms[room])
            if room_connections:
                results = await asyncio.gather(
                    *[send_to_connection(conn) for conn in room_connections],
                    return_exceptions=True
                )
                
                # Nettoyer connexions déconnectées
                disconnected = [conn for conn in results if conn is not None and not isinstance(conn, Exception)]
                if disconnected:
                    async with self.lock:
                        for conn in disconnected:
                            self.rooms[room].discard(conn)
                            self.active_connections.discard(conn)
                            self.connection_data.pop(conn, None)
        else:
            # Si pas de room ou room inexistante, broadcast normal
            await self.emit(event, data)


# Instance globale du gestionnaire WebSocket
_websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Obtenir l'instance globale du gestionnaire WebSocket"""
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    return _websocket_manager


