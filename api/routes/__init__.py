"""
Package routes API - Endpoints FastAPI pour le contrôle de l'application
"""

from .scanner import router as scanner_router
from .dashboard import router as dashboard_router

__all__ = ['scanner_router', 'dashboard_router']
