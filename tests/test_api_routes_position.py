import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.state_manager as state_manager
import api.routes.position as pos_routes


class _AsyncLock:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _DummyRequest:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload


class _DummyState:
    def __init__(self, pos_mgr=None, pp=None, ws_mgr=None):
        self._pos_mgr = pos_mgr
        self._pp = pp
        self._ws_mgr = ws_mgr
        self._lock = _AsyncLock()
        self.active_position = None

    def lock(self, name: str):
        return self._lock

    def get_position_manager(self):
        return self._pos_mgr

    def get_price_provider(self):
        return self._pp

    def get_ws_manager(self):
        return self._ws_mgr

    def get_scheduler(self):
        return None

    def set_active_position(self, position):
        self.active_position = position


class _DummyPosition:
    def __init__(self, symbol="BTC/USDT", direction="LONG", entry=100.0, size=100.0):
        self.symbol = symbol
        self.direction = direction
        self.entry = entry
        self.size = size
        self.sl = 90.0
        self.tp = 110.0

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "entry": self.entry,
            "size": self.size,
            "sl": self.sl,
            "tp": self.tp,
        }


@pytest.fixture(autouse=True)
def _reset_route_globals():
    pos_routes._position_manager = None
    pos_routes._app_state = None
    pos_routes._ws_manager = None
    pos_routes._live_order_manager = None
    pos_routes._price_provider = None
    pos_routes._scheduler = None
    yield
    pos_routes._position_manager = None
    pos_routes._app_state = None
    pos_routes._ws_manager = None
    pos_routes._live_order_manager = None
    pos_routes._price_provider = None
    pos_routes._scheduler = None


@pytest.mark.asyncio
async def test_api_open_position_missing_symbol(monkeypatch: pytest.MonkeyPatch):
    pos_mgr = SimpleNamespace(active_position=None, open_position=Mock(return_value=_DummyPosition()))
    state = _DummyState(pos_mgr=pos_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    req = _DummyRequest({"entry": 100.0})
    resp = await pos_routes.api_open_position(req)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_api_open_position_invalid_entry(monkeypatch: pytest.MonkeyPatch):
    pos_mgr = SimpleNamespace(active_position=None, open_position=Mock(return_value=_DummyPosition()))
    state = _DummyState(pos_mgr=pos_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    req = _DummyRequest({"symbol": "BTC/USDT", "entry": 0})
    resp = await pos_routes.api_open_position(req)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_api_open_position_rejects_when_already_active(monkeypatch: pytest.MonkeyPatch):
    pos_mgr = SimpleNamespace(active_position=object(), open_position=Mock())
    state = _DummyState(pos_mgr=pos_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    req = _DummyRequest({"symbol": "BTC/USDT", "entry": 100.0})
    resp = await pos_routes.api_open_position(req)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_api_open_position_calibration_reject(monkeypatch: pytest.MonkeyPatch):
    pos_mgr = SimpleNamespace(active_position=None, open_position=Mock(return_value=None))
    state = _DummyState(pos_mgr=pos_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    async def _to_thread(func, **kwargs):
        return func(**kwargs)

    monkeypatch.setattr(pos_routes.asyncio, "to_thread", _to_thread)

    req = _DummyRequest({"symbol": "BTC/USDT", "entry": 100.0})
    resp = await pos_routes.api_open_position(req)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_api_open_position_success_and_invert_signals(monkeypatch: pytest.MonkeyPatch):
    pos = _DummyPosition(symbol="BTC/USDT", direction="SHORT", entry=100.0)

    def _open_position(**kwargs):
        pos.direction = kwargs.get("direction")
        return pos

    pos_mgr = SimpleNamespace(active_position=None, open_position=Mock(side_effect=lambda **kw: _open_position(**kw)))
    ws_mgr = SimpleNamespace(emit=AsyncMock())
    state = _DummyState(pos_mgr=pos_mgr, pp=None, ws_mgr=ws_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    import config as config_module

    monkeypatch.setattr(config_module, "TRADING_CONFIG", {"invert_signals": True, "adaptive_sizing_enabled": False}, raising=False)

    async def _to_thread(func, **kwargs):
        return func(**kwargs)

    monkeypatch.setattr(pos_routes.asyncio, "to_thread", _to_thread)

    monkeypatch.setattr(pos_routes, "_ws_manager", ws_mgr)

    import core.position.sl_services as sl_services

    monkeypatch.setattr(sl_services, "setup_realtime_sl_check", AsyncMock())
    monkeypatch.setattr(sl_services, "schedule_sl_order_placement", AsyncMock())

    req = _DummyRequest({"symbol": "BTC/USDT", "entry": 100.0, "direction": "LONG", "size": 10})
    resp = await pos_routes.api_open_position(req)
    assert resp.status_code == 200
    assert state.active_position is pos
    assert pos.direction == "SHORT"


@pytest.mark.asyncio
async def test_api_open_position_post_open_tasks_errors_do_not_fail(monkeypatch: pytest.MonkeyPatch):
    pos = _DummyPosition(symbol="BTC/USDT", direction="LONG", entry=100.0)

    pos_mgr = SimpleNamespace(active_position=None, open_position=Mock(return_value=pos))
    ws_mgr = SimpleNamespace(emit=AsyncMock())

    state = _DummyState(pos_mgr=pos_mgr, pp=SimpleNamespace(), ws_mgr=ws_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    import config as config_module

    monkeypatch.setattr(config_module, "TRADING_CONFIG", {"invert_signals": False, "adaptive_sizing_enabled": False}, raising=False)

    async def _to_thread(func, **kwargs):
        return func(**kwargs)

    monkeypatch.setattr(pos_routes.asyncio, "to_thread", _to_thread)

    # Force post-open helpers to raise (should be swallowed)
    import core.position.sl_services as sl_services

    async def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(sl_services, "setup_realtime_sl_check", _boom)
    monkeypatch.setattr(sl_services, "schedule_sl_order_placement", _boom)

    # scheduler start error should not fail request
    sched = SimpleNamespace(is_running=False, start=Mock(side_effect=RuntimeError("sched boom")))
    state.get_scheduler = lambda: sched

    req = _DummyRequest({"symbol": "BTC/USDT", "entry": 100.0, "direction": "LONG", "size": 10})
    resp = await pos_routes.api_open_position(req)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_api_get_active_position_false(monkeypatch: pytest.MonkeyPatch):
    pos_mgr = SimpleNamespace(active_position=None)
    state = _DummyState(pos_mgr=pos_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    resp = await pos_routes.api_get_active_position()
    assert resp.status_code == 200
    assert '"active":false' in resp.body.decode("utf-8")


@pytest.mark.asyncio
async def test_api_get_active_position_true(monkeypatch: pytest.MonkeyPatch):
    pos = _DummyPosition()
    pos_mgr = SimpleNamespace(active_position=pos)
    state = _DummyState(pos_mgr=pos_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    resp = await pos_routes.api_get_active_position()
    assert resp.status_code == 200
    body = resp.body.decode("utf-8")
    assert '"active":true' in body
    assert '"timestamp"' in body


@pytest.mark.asyncio
async def test_api_check_position_no_position(monkeypatch: pytest.MonkeyPatch):
    pos_mgr = SimpleNamespace(active_position=None)
    state = _DummyState(pos_mgr=pos_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    resp = await pos_routes.api_check_position()
    assert resp.status_code == 200
    assert resp.body.decode("utf-8") == '{"status":"no_position"}'


@pytest.mark.asyncio
async def test_api_check_position_no_price_provider(monkeypatch: pytest.MonkeyPatch):
    pos = _DummyPosition()
    pos_mgr = SimpleNamespace(active_position=pos)
    state = _DummyState(pos_mgr=pos_mgr, pp=None)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    resp = await pos_routes.api_check_position()
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_api_check_position_price_not_available(monkeypatch: pytest.MonkeyPatch):
    pos = _DummyPosition()
    pnl_calc = SimpleNamespace(calculate_pnl_percent=Mock(return_value=0.0), calculate_pnl_usdt=Mock(return_value=0.0))
    pos_mgr = SimpleNamespace(active_position=pos, pnl_calculator=pnl_calc, check_position=AsyncMock(return_value=None))

    pp = SimpleNamespace(get_price=AsyncMock(return_value={"price": None}), set_socketio_callback=Mock(), set_sl_check_callback=Mock())

    state = _DummyState(pos_mgr=pos_mgr, pp=pp, ws_mgr=None)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    import utils.pricing as pricing

    monkeypatch.setattr(pricing, "get_preferred_price", lambda d: None)

    resp = await pos_routes.api_check_position()
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_api_check_position_includes_close_reason(monkeypatch: pytest.MonkeyPatch):
    pos = _DummyPosition()
    pnl_calc = SimpleNamespace(calculate_pnl_percent=Mock(return_value=1.0), calculate_pnl_usdt=Mock(return_value=2.0))
    pos_mgr = SimpleNamespace(active_position=pos, pnl_calculator=pnl_calc, check_position=AsyncMock(return_value="SL"))

    pp = SimpleNamespace(get_price=AsyncMock(return_value={"price": 105.0}), set_socketio_callback=Mock(), set_sl_check_callback=Mock())
    ws_mgr = SimpleNamespace(emit=AsyncMock())

    state = _DummyState(pos_mgr=pos_mgr, pp=pp, ws_mgr=ws_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    import utils.pricing as pricing

    monkeypatch.setattr(pricing, "get_preferred_price", lambda d: 105.0)

    resp = await pos_routes.api_check_position()
    assert resp.status_code == 200
    assert '"close_reason":"SL"' in resp.body.decode("utf-8")


@pytest.mark.asyncio
async def test_api_check_position_success_emits_ws(monkeypatch: pytest.MonkeyPatch):
    pos = _DummyPosition()
    pnl_calc = SimpleNamespace(
        calculate_pnl_percent=Mock(return_value=1.23),
        calculate_pnl_usdt=Mock(return_value=4.56),
    )
    pos_mgr = SimpleNamespace(active_position=pos, pnl_calculator=pnl_calc, check_position=AsyncMock(return_value=None))

    pp = SimpleNamespace(get_price=AsyncMock(return_value={"price": 105.0}), set_socketio_callback=Mock(), set_sl_check_callback=Mock())

    async def _emit(event, data):
        return None

    ws_mgr = SimpleNamespace(emit=AsyncMock(side_effect=_emit))

    state = _DummyState(pos_mgr=pos_mgr, pp=pp, ws_mgr=ws_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    import utils.pricing as pricing

    monkeypatch.setattr(pricing, "get_preferred_price", lambda d: 105.0)

    resp = await pos_routes.api_check_position()
    assert resp.status_code == 200
    ws_mgr.emit.assert_awaited()


@pytest.mark.asyncio
async def test_api_close_position_wraps_perform_close(monkeypatch: pytest.MonkeyPatch):
    async def _fake_close(reason="MANUAL", exit_price=None):
        return {"ok": True, "reason": reason, "exit": exit_price}

    monkeypatch.setattr(pos_routes, "perform_close_position", _fake_close)

    req = _DummyRequest({"reason": "MANUAL", "exit_price": 123.0})
    resp = await pos_routes.api_close_position(req)
    assert resp.status_code == 200
    assert '"ok":true' in resp.body.decode("utf-8")


@pytest.mark.asyncio
async def test_api_close_position_handles_request_error(monkeypatch: pytest.MonkeyPatch):
    class _BadReq:
        async def json(self):
            raise RuntimeError("bad json")

    resp = await pos_routes.api_close_position(_BadReq())
    assert resp.status_code == 500
