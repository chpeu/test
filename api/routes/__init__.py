"""
Package routes API - Endpoints FastAPI pour le contrôle de l'application
"""

from fastapi import APIRouter
from .scanner import (
    router as scanner_router,
    set_scanner,
    set_analyzer,
    set_price_provider,
    set_app_state as set_app_state_scanner,
    set_socketio as set_socketio_scanner
)
from .dashboard import (
    router as dashboard_router,
    set_scheduler,
    set_position_manager,
    set_app_state as set_app_state_dashboard,
    set_socketio as set_socketio_dashboard,
    set_websocket_manager as set_websocket_manager_dashboard
)

# Créer un router combiné pour compatibilité avec main.py
router = APIRouter()
router.include_router(scanner_router)
router.include_router(dashboard_router)

# Variables pour les dépendances injectées
_analytics_db = None
_notification_manager = None
_instance_port = None

def set_analytics_db(analytics_db):
    """Injecter l'instance AnalyticsDatabase"""
    global _analytics_db
    _analytics_db = analytics_db

def set_notification_manager(notification_manager):
    """Injecter le gestionnaire de notifications"""
    global _notification_manager
    _notification_manager = notification_manager

def set_instance_port(port: int):
    """Définir le port de l'instance"""
    global _instance_port
    _instance_port = port

# Export pour compatibilité
def set_app_state(app_state):
    """Injecter l'état de l'app (propage aux deux modules)"""
    set_app_state_scanner(app_state)
    set_app_state_dashboard(app_state)

def set_socketio(sio):
    """Injecter SocketIO (propage aux deux modules)"""
    set_socketio_scanner(sio)
    set_socketio_dashboard(sio)

def set_websocket_manager(ws_manager):
    """Injecter WebSocketManager (propage aux deux modules)"""
    # 🔥 MIGRATION COMPLÈTE: Injecter ws_manager dans dashboard
    if set_websocket_manager_dashboard:
        set_websocket_manager_dashboard(ws_manager)
    # Scanner utilise set_socketio pour compatibilité
    if set_socketio_scanner:
        set_socketio_scanner(ws_manager)

__all__ = [
    'router',
    'scanner_router',
    'dashboard_router',
    'set_scanner',
    'set_analyzer',
    'set_price_provider',
    'set_scheduler',
    'set_position_manager',
    'set_analytics_db',
    'set_notification_manager',
    'set_instance_port',
    'set_app_state',
    'set_socketio',
    'set_websocket_manager'
]
