"""FastAPI application factory and middleware setup."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

from app.runtime import app_state, ws_manager

try:  # Optional routes package
    from api.routes import (
        router as api_router,
        set_app_state as set_app_state_routes,
        set_websocket_manager as set_websocket_manager_routes,
    )
except ImportError:  # pragma: no cover
    api_router = None
    set_app_state_routes = None
    set_websocket_manager_routes = None

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        import time

        start_time = time.time()
        path = request.url.path
        logger.info("📥 Requête entrante: %s %s", request.method, path)

        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            logger.info(
                "📤 Réponse: %s %s - %s (%.3fs)",
                request.method,
                path,
                response.status_code,
                process_time,
            )
            return response
        except Exception:
            process_time = time.time() - start_time
            logger.exception("❌ Exception dans middleware pour %s (%.3fs)", path, process_time)
            raise


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdn.socket.io; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "connect-src 'self' ws: wss:; "
            "font-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


def create_app() -> FastAPI:
    """Instantiate and configure the FastAPI application."""
    app = FastAPI(title="Trade Cursor v7.0")
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    if api_router:
        app.include_router(api_router)
        logger.info("✅ API REST routes incluses: /api/*")

    if set_websocket_manager_routes:
        set_websocket_manager_routes(ws_manager)
        logger.info("✅ ws_manager injecté dans API routes")

    if set_app_state_routes:
        set_app_state_routes(app_state)
        logger.info("✅ app_state injecté dans API routes")

    @app.get("/health", tags=["system"])
    async def healthcheck():  # pragma: no cover - trivial endpoint
        return JSONResponse({"status": "ok"})

    return app


__all__ = ["create_app"]
