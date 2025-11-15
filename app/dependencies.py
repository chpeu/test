"""Dependency helpers for FastAPI routes."""
from __future__ import annotations

from typing import Dict

from app.runtime import app_state, ws_manager


def get_app_state() -> Dict:
    return app_state


def get_ws_manager():
    return ws_manager


__all__ = ["get_app_state", "get_ws_manager"]
