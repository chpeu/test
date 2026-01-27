import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.state_manager as state_manager
from api.routes import price as price_routes


class _AsyncLock:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _DummyPriceProvider:
    def __init__(self):
        self.use_websocket = True
        self.ws_manager = SimpleNamespace(connected=True)
        self.cache_lock = _AsyncLock()
        self.price_cache = {}
        self.get_price = AsyncMock()
        self.start_websocket = AsyncMock()


class _DummyState:
    def __init__(self, pp=None, top_pairs=None):
        self._pp = pp
        self.top_pairs = top_pairs or []

    def get_price_provider(self):
        return self._pp


@pytest.fixture(autouse=True)
def _reset_route_globals():
    price_routes._price_provider = None
    price_routes._app_state = None
    yield
    price_routes._price_provider = None
    price_routes._app_state = None


@pytest.mark.asyncio
async def test_api_get_price_no_provider(monkeypatch: pytest.MonkeyPatch):
    dummy_state = _DummyState(pp=None)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: dummy_state)

    resp = await price_routes.api_get_price("BTC/USDT")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_api_get_price_returns_rest_source_when_not_from_cache(monkeypatch: pytest.MonkeyPatch):
    pp = _DummyPriceProvider()
    pp.price_cache = {}
    pp.get_price = AsyncMock(return_value={"price": 100.0, "timestamp": 1000.0})

    dummy_state = _DummyState(pp=pp)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: dummy_state)

    resp = await price_routes.api_get_price("BTC/USDT")
    assert resp.status_code == 200
    body = resp.body.decode("utf-8")
    assert '"_source":"REST"' in body
    assert '"_age_seconds"' in body


@pytest.mark.asyncio
async def test_api_get_price_returns_websocket_source_when_cached(monkeypatch: pytest.MonkeyPatch):
    pp = _DummyPriceProvider()
    pp.price_cache = {"BTC/USDT": {"timestamp": 1000.0, "price": 100.0}}
    pp.get_price = AsyncMock(return_value={"price": 100.0, "timestamp": 1000.0})

    dummy_state = _DummyState(pp=pp)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: dummy_state)

    resp = await price_routes.api_get_price("BTC/USDT")
    assert resp.status_code == 200
    body = resp.body.decode("utf-8")
    assert '"_source":"WebSocket"' in body


@pytest.mark.asyncio
async def test_api_get_price_404_when_no_price(monkeypatch: pytest.MonkeyPatch):
    pp = _DummyPriceProvider()
    pp.get_price = AsyncMock(return_value=None)

    dummy_state = _DummyState(pp=pp)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: dummy_state)

    resp = await price_routes.api_get_price("BTC/USDT")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_get_live_prices_returns_cache(monkeypatch: pytest.MonkeyPatch):
    pp = _DummyPriceProvider()
    pp.ws_manager.connected = True
    pp.price_cache = {
        "BTC/USDT": {"price": 100.0, "timestamp": 1000.0, "volume24": 123},
        "ETH/USDT": {"referencePrice": 200.0, "timestamp": 1000.0, "volume24": 456},
    }

    dummy_state = _DummyState(pp=pp)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: dummy_state)

    resp = await price_routes.api_get_live_prices()
    assert resp.status_code == 200
    body = resp.body.decode("utf-8")
    assert '"websocket_connected":true' in body
    assert '"cache_size":2' in body
    assert '"BTC/USDT"' in body
    assert '"ETH/USDT"' in body


@pytest.mark.asyncio
async def test_api_start_websocket_requires_top_pairs(monkeypatch: pytest.MonkeyPatch):
    pp = _DummyPriceProvider()
    dummy_state = _DummyState(pp=pp, top_pairs=[])
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: dummy_state)

    resp = await price_routes.api_start_websocket()
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_api_start_websocket_starts_with_valid_symbols(monkeypatch: pytest.MonkeyPatch):
    pp = _DummyPriceProvider()
    top_pairs = [{"symbol": "BTC/USDT"}, {"symbol": ""}, {"symbol": "ETH/USDT"}]
    dummy_state = _DummyState(pp=pp, top_pairs=top_pairs)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: dummy_state)

    resp = await price_routes.api_start_websocket()
    assert resp.status_code == 200
    pp.start_websocket.assert_awaited_once()


@pytest.mark.asyncio
async def test_api_start_websocket_handles_error(monkeypatch: pytest.MonkeyPatch):
    pp = _DummyPriceProvider()
    pp.start_websocket = AsyncMock(side_effect=RuntimeError("boom"))

    dummy_state = _DummyState(pp=pp, top_pairs=[{"symbol": "BTC/USDT"}])
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: dummy_state)

    resp = await price_routes.api_start_websocket()
    assert resp.status_code == 500
