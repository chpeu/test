"""
API routes pour les statistiques WebSocket
"""
import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from typing import Dict, Any

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# Variables globales injectées par main.py
_ws_manager = None

def set_websocket_manager(wm):
    global _ws_manager
    _ws_manager = wm

@router.get("/api/websocket/stats")
async def get_websocket_stats():
    """Récupérer les statistiques des connexions WebSocket"""
    try:
        ws_manager = _ws_manager
        if ws_manager is None:
            try:
                from core.state_manager import get_state_manager
                ws_manager = get_state_manager().get_ws_manager()
            except Exception:
                ws_manager = None
        if not ws_manager:
            return JSONResponse({
                "active_connections": 0,
                "error": "WebSocket manager not available",
                "status": "error"
            }, status_code=503)
        
        # Statistiques de base
        active_count = ws_manager.get_connection_count()
        
        # Statistiques détaillées si disponible
        detailed_stats = {}
        if hasattr(ws_manager, 'connection_data') and ws_manager.connection_data:
            connections = []
            total_msg_in = 0
            total_msg_out = 0
            total_bytes_in = 0
            total_bytes_out = 0
            
            for websocket, conn_data in ws_manager.connection_data.items():
                conn_info = {
                    "connection_id": conn_data.get('connection_id'),
                    "connected_at": conn_data.get('connected_at'),
                    "client": str(getattr(websocket, 'client', None)),
                    "user_agent": conn_data.get('user_agent'),
                    "origin": conn_data.get('origin'),
                    "message_in_count": conn_data.get('message_in_count', 0),
                    "message_out_count": conn_data.get('message_out_count', 0),
                    "bytes_in": conn_data.get('bytes_in', 0),
                    "bytes_out": conn_data.get('bytes_out', 0),
                    "last_message_type": conn_data.get('last_message_type'),
                    "last_server_rtt_ms": conn_data.get('last_server_rtt_ms')
                }
                connections.append(conn_info)
                
                total_msg_in += conn_data.get('message_in_count', 0)
                total_msg_out += conn_data.get('message_out_count', 0)
                total_bytes_in += conn_data.get('bytes_in', 0)
                total_bytes_out += conn_data.get('bytes_out', 0)
            
            detailed_stats = {
                "connections": connections,
                "totals": {
                    "messages_in": total_msg_in,
                    "messages_out": total_msg_out,
                    "bytes_in": total_bytes_in,
                    "bytes_out": total_bytes_out
                }
            }
        
        # Statistiques des rooms si disponible
        rooms_stats = {}
        if hasattr(ws_manager, 'rooms') and ws_manager.rooms:
            for room_name, room_connections in ws_manager.rooms.items():
                rooms_stats[room_name] = len(room_connections)
        
        # Commandes WebSocket enregistrées
        registered_commands = []
        if hasattr(ws_manager, 'get_registered_commands'):
            registered_commands = ws_manager.get_registered_commands()
        
        return JSONResponse({
            "active_connections": active_count,
            "rooms": rooms_stats,
            "registered_commands": registered_commands,
            "detailed_stats": detailed_stats,
            "status": "healthy" if active_count > 0 else "no_connections"
        })
        
    except Exception as e:
        logger.error(f"❌ Erreur récupération stats WebSocket: {e}")
        return JSONResponse({
            "active_connections": 0,
            "error": str(e),
            "status": "error"
        }, status_code=500)

@router.get("/api/health")
async def health_check():
    """Point de contrôle de santé du backend"""
    try:
        from core.state_manager import get_state_manager
        state = get_state_manager()
        
        # Vérifier les composants critiques
        components = {
            "websocket_manager": _ws_manager is not None,
            "state_manager": state is not None,
            "position_manager": state.get_position_manager() is not None if state else False,
            "scanner": state.get_scanner() is not None if state else False,
        }
        
        # Statut global
        all_healthy = all(components.values())
        status = "healthy" if all_healthy else "degraded"
        
        # Stats WebSocket
        ws_connections = 0
        if _ws_manager:
            ws_connections = _ws_manager.get_connection_count()
        
        return JSONResponse({
            "status": status,
            "timestamp": __import__('time').time(),
            "components": components,
            "websocket_connections": ws_connections,
            "uptime_info": {
                "session_id": getattr(state, 'session_id', None) if state else None,
                "is_scanning": getattr(state, 'is_scanning', False) if state else False
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Erreur health check: {e}")
        return JSONResponse({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": __import__('time').time()
        }, status_code=500)
