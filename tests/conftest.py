"""
Configuration pytest - Fixtures globales
"""

import asyncio
import logging
import sys

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def configure_test_logging():
    """Configure safe logging for ALL tests - completely disable file operations"""
    import logging
    
    # GLOBAL: Disable all existing loggers and handlers
    root_logger = logging.getLogger()
    
    # Remove ALL handlers from root logger
    for handler in root_logger.handlers[:]:
        try:
            root_logger.removeHandler(handler)
            handler.close()
        except Exception:
            pass
    
    # Disable propagation and set high level to minimize noise
    root_logger.setLevel(logging.CRITICAL)
    root_logger.propagate = False
    
    # Get all existing loggers and clean them
    existing_loggers = [logging.getLogger(name) for name in logging.Logger.manager.loggerDict]
    for logger in existing_loggers:
        logger.setLevel(logging.CRITICAL)
        logger.propagate = False
        # Remove all handlers
        for handler in logger.handlers[:]:
            try:
                logger.removeHandler(handler)
                handler.close()
            except Exception:
                pass
    
    # Add single null handler to root to prevent any output
    null_handler = logging.NullHandler()
    root_logger.addHandler(null_handler)
    
    # Override any future logger creation to be safe
    def safe_getLogger(name=None):
        logger = original_getLogger(name) if name else original_getLogger()
        logger.setLevel(logging.CRITICAL)
        logger.propagate = False
        # Remove any handlers that might get added
        for handler in logger.handlers[:]:
            if not isinstance(handler, logging.NullHandler):
                try:
                    logger.removeHandler(handler)
                    handler.close()
                except Exception:
                    pass
        if not logger.handlers:
            logger.addHandler(logging.NullHandler())
        return logger
    
    # Store original before monkey patching
    original_getLogger = logging.getLogger
    # Monkey patch logging.getLogger to always return safe logger
    logging.getLogger = safe_getLogger
    
    # Store original for cleanup
    configure_test_logging._original_getLogger = original_getLogger


@pytest.fixture
def client():
    """Fixture TestClient FastAPI"""
    from main import app
    return TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def _close_global_singletons():
    yield

    # ⚠️ Seulement fermer les ressources async, PAS remettre les singletons à None
    # car l'app backend peut encore tourner après les tests
    try:
        from api import price_provider as price_provider_mod

        provider = getattr(price_provider_mod, "_price_provider", None)
        if provider is not None:
            try:
                asyncio.run(provider.stop_websocket())
            except RuntimeError:
                pass

        # ❌ NE PAS faire: price_provider_mod._price_provider = None
        # L'app backend utilise encore ce singleton après les tests
    except Exception:
        pass

    try:
        from api import mexc as mexc_mod

        mexc_client = getattr(mexc_mod, "_mexc_client", None)
        if mexc_client is not None:
            try:
                asyncio.run(mexc_client.close())
            except RuntimeError:
                pass

        # ❌ NE PAS faire: mexc_mod._mexc_client = None
        # L'app backend utilise encore ce singleton après les tests
    except Exception:
        pass
