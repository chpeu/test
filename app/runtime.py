"""Runtime context shared across the FastAPI application."""
from __future__ import annotations

from app.state import ApplicationState
from core.websocket_manager import get_websocket_manager

app_state = ApplicationState()
ws_manager = get_websocket_manager()

__all__ = ["app_state", "ws_manager"]
