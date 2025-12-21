"""
Configuration pytest - Fixtures globales
"""

import asyncio

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Fixture TestClient FastAPI"""
    from main import app
    return TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def _close_global_singletons():
    yield

    try:
        from api import price_provider as price_provider_mod

        provider = getattr(price_provider_mod, "_price_provider", None)
        if provider is not None:
            try:
                asyncio.run(provider.stop_websocket())
            except RuntimeError:
                pass

        price_provider_mod._price_provider = None
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

        mexc_mod._mexc_client = None
    except Exception:
        pass
