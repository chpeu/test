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
    """Configure safe logging for tests - avoid file handlers that cause I/O errors"""
    # Remove all existing handlers and configure simple console-only logging
    root_logger = logging.getLogger()
    
    # Clear all existing handlers
    for handler in root_logger.handlers[:]:
        try:
            root_logger.removeHandler(handler)
            handler.close()
        except Exception:
            pass
    
    # Add simple console handler without file operations
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)  # Only warnings/errors in tests
    
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.WARNING)
    
    # Configure specific loggers used by test modules
    test_loggers = [
        'core.implementations.testable_position_validator',
        'core.implementations.testable_scanner_modules',
        'core.implementations.testable_pair_filter',
        'core.implementations.testable_market_data_collector',
        'core.implementations.testable_scalability_scorer',
        'core.implementations.testable_scan_pipeline'
    ]
    
    for logger_name in test_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.CRITICAL)  # Only critical errors
        # Remove any existing handlers
        for handler in logger.handlers[:]:
            try:
                logger.removeHandler(handler)
                handler.close()
            except Exception:
                pass


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
