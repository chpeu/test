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
from .position import (
    router as position_router,
    set_position_manager as set_position_manager_pos,
    set_app_state as set_app_state_pos,
    set_websocket_manager as set_websocket_manager_pos,
    set_live_order_manager,
    set_price_provider as set_price_provider_pos,
    set_scheduler as set_scheduler_pos
)
from .price import (
    router as price_router,
    set_price_provider as set_price_provider_price,
    set_app_state as set_app_state_price
)
from .websocket import (
    router as websocket_router,
    set_websocket_manager as set_websocket_manager_ws,
    set_app_state as set_app_state_ws,
    set_position_manager as set_position_manager_ws,
    set_scheduler as set_scheduler_ws,
    set_price_provider as set_price_provider_ws
)
from .export import (
    router as export_router,
    set_app_state as set_app_state_export
)
from .metrics import router as metrics_router
from .ml import router as ml_router
from .config import (
    router as config_router,
    perform_config_update,
    set_app_state as set_app_state_config
)
from .ml_calibration import router as ml_calibration_router  # 🆕 Routes ML Calibration
from .ml_models import router as ml_models_router
from .ml_config import router as ml_config_router
from .logs import router as logs_router
from .test_errors import router as test_errors_router
from .notifications import (
    router as notifications_router,
    perform_telegram_config_update,
    perform_telegram_test
)

# Créer un router combiné pour compatibilité avec main.py
router = APIRouter()
router.include_router(scanner_router)
router.include_router(dashboard_router)
router.include_router(position_router)
router.include_router(price_router)
router.include_router(websocket_router)
router.include_router(export_router)
router.include_router(metrics_router)
router.include_router(ml_router)
router.include_router(ml_models_router)
router.include_router(config_router)
router.include_router(ml_calibration_router)
router.include_router(ml_config_router)
router.include_router(logs_router, prefix="/logs")
router.include_router(notifications_router)
router.include_router(test_errors_router, prefix="/test/errors")

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
    """Injecter l'état de l'app (propage aux modules)"""
    set_app_state_scanner(app_state)
    set_app_state_dashboard(app_state)
    set_app_state_pos(app_state)
    set_app_state_price(app_state)
    set_app_state_ws(app_state)
    set_app_state_export(app_state)
    set_app_state_config(app_state)

def set_socketio(sio):
    """Injecter SocketIO"""
    set_socketio_scanner(sio)
    set_socketio_dashboard(sio)

def set_websocket_manager(ws_manager):
    """Injecter WebSocketManager (propage aux deux modules)"""
    # MIGRATION COMPLÈTE: Injecter ws_manager dans dashboard
    if set_websocket_manager_dashboard:
        set_websocket_manager_dashboard(ws_manager)
    if set_websocket_manager_pos:
        set_websocket_manager_pos(ws_manager)
    if set_websocket_manager_ws:
        set_websocket_manager_ws(ws_manager)
    # Scanner utilise set_socketio pour compatibilité
    if set_socketio_scanner:
        set_socketio_scanner(ws_manager)

def set_position_manager(pm):
    """Injecter position manager"""
    from .dashboard import set_position_manager as set_pm_dash
    set_pm_dash(pm)
    set_position_manager_pos(pm)
    set_position_manager_ws(pm)

def set_price_provider(pp):
    """Injecter price provider"""
    from .scanner import set_price_provider as set_pp_scan
    set_pp_dash = set_pp_scan # Scanner and dashboard use same instance usually
    set_pp_scan(pp)
    set_price_provider_pos(pp)
    set_price_provider_price(pp)
    set_price_provider_ws(pp)

def set_scheduler(s):
    """Injecter scheduler"""
    from .dashboard import set_scheduler as set_s_dash
    set_s_dash(s)
    set_scheduler_pos(s)
    set_scheduler_ws(s)

__all__ = [
    'router',
    'scanner_router',
    'dashboard_router',
    'position_router',
    'price_router',
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
    'set_websocket_manager',
    'set_live_order_manager'
]
