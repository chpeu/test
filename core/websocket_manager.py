"""
Gestionnaire WebSocket natif pour Trade Cursor
Remplace Socket.IO pour des performances optimales
"""
import asyncio
import json
import logging
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
        self._lock = asyncio.Lock()
        # 🔥 LIVE TRADING: Système de commandes WebSocket
        self._command_handlers: Dict[str, callable] = {}
    
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
        async with self._lock:
            self.active_connections.add(websocket)
            self.connection_data[websocket] = {
                'connected_at': datetime.now().isoformat(),
                'last_ping': datetime.now().isoformat()
            }
        logger.info(f"✅ WebSocket connecté (total: {len(self.active_connections)})")
    
    async def disconnect(self, websocket: WebSocket):
        """Déconnecter un WebSocket (optimisé)"""
        async with self._lock:
            self.active_connections.discard(websocket)
            self.connection_data.pop(websocket, None)
            # 🔥 OPTIMISATION: Nettoyer aussi des rooms en une seule passe
            for room_connections in self.rooms.values():
                room_connections.discard(websocket)
        logger.info(f"❌ WebSocket déconnecté (total: {len(self.active_connections)})")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Envoyer un message à un WebSocket spécifique"""
        try:
            if websocket in self.active_connections:
                # 🔥 FIX: Utiliser un encodeur JSON personnalisé pour gérer datetime et autres types
                await websocket.send_text(json.dumps(message, default=str))
        except (WebSocketDisconnect, ConnectionError, RuntimeError) as e:
            # 🔥 FIX: Déconnexions normales - nettoyer silencieusement
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
        
        # 🔥 OPTIMISATION: Envoyer à tous les clients en parallèle avec asyncio.gather
        async def send_to_connection(connection):
            try:
                # 🔥 FIX: Vérifier que la connexion est toujours active
                if connection not in self.active_connections:
                    return None
                await asyncio.wait_for(connection.send_text(message_json), timeout=1.0)
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
        
        # Exécuter tous les envois en parallèle
        results = await asyncio.gather(
            *[send_to_connection(conn) for conn in connections_to_send],
            return_exceptions=True
        )
        
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
            async with self._lock:
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
        message = {
            'type': 'event',
            'event': event,
            'data': data,
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
    
    async def ping_all(self):
        """Envoyer un ping à tous les clients (keep-alive)"""
        if not self.active_connections:
            return
        
        message = {
            'type': 'ping',
            'timestamp': datetime.now().isoformat()
        }
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
                    async with self._lock:
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


