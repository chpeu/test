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
    """
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.connection_data: Dict[WebSocket, dict] = {}
        self._lock = asyncio.Lock()
    
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
        """Déconnecter un WebSocket"""
        async with self._lock:
            self.active_connections.discard(websocket)
            self.connection_data.pop(websocket, None)
        logger.info(f"❌ WebSocket déconnecté (total: {len(self.active_connections)})")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Envoyer un message à un WebSocket spécifique"""
        try:
            if websocket in self.active_connections:
                await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"❌ Erreur envoi message WebSocket: {e}")
            await self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        """Diffuser un message à tous les clients connectés"""
        if not self.active_connections:
            return
        
        # Créer le message JSON une seule fois
        message_json = json.dumps(message)
        
        # Envoyer à tous les clients en parallèle
        disconnected = []
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.warning(f"⚠️ Erreur broadcast WebSocket: {e}")
                disconnected.append(connection)
        
        # Nettoyer les connexions déconnectées
        if disconnected:
            async with self._lock:
                for conn in disconnected:
                    self.active_connections.discard(conn)
                    self.connection_data.pop(conn, None)
    
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


# Instance globale du gestionnaire WebSocket
_websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Obtenir l'instance globale du gestionnaire WebSocket"""
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    return _websocket_manager


