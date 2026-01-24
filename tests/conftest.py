"""
Configuration pytest - Fixtures globales
"""

import asyncio
import logging
import sys

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def _prevent_pytest_capture_stream_close():
    class _NonClosingStream:
        def __init__(self, stream):
            self._stream = stream

        def close(self):
            return None

        def __getattr__(self, name):
            return getattr(self._stream, name)

        def write(self, s):
            try:
                return self._stream.write(s)
            except ValueError:
                # Si un code tiers a fermé le flux sous-jacent (FD fermé),
                # ne pas faire planter pytest en fin de session.
                return 0

        def flush(self):
            try:
                return self._stream.flush()
            except ValueError:
                return None

    sys.stdout = _NonClosingStream(sys.stdout)
    sys.stderr = _NonClosingStream(sys.stderr)

    try:
        from colorama.ansitowin32 import AnsiToWin32

        original_colorama_write = AnsiToWin32.write

        def safe_colorama_write(self, text):
            try:
                return original_colorama_write(self, text)
            except ValueError:
                return 0

        AnsiToWin32.write = safe_colorama_write
    except Exception:
        pass

    def non_closing_close(self):
        try:
            self.flush()
        except Exception:
            pass
        logging.Handler.close(self)

    logging.StreamHandler.close = non_closing_close
    yield


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
