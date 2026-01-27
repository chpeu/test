import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import api.routes.position as pos_routes
import core.state_manager as state_manager


class _AsyncLock:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _DummyState:
    def __init__(self, pos_mgr=None, pp=None, ws_mgr=None, lom=None):
        self._pos_mgr = pos_mgr
        self._pp = pp
        self._ws_mgr = ws_mgr
        self._lom = lom
        self._lock = _AsyncLock()
        self.active_position = None
        self.top_pairs = []
        self.trades = []

    def lock(self, name: str):
        return self._lock

    def get_position_manager(self):
        return self._pos_mgr

    def get_price_provider(self):
        return self._pp

    def get_ws_manager(self):
        return self._ws_mgr

    def get_live_order_manager(self):
        return self._lom

    def set_active_position(self, position):
        self.active_position = position

    def add_trade(self, trade):
        self.trades.append(trade)


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


@pytest.fixture()
def _patched_deps(monkeypatch: pytest.MonkeyPatch):
    # core.bootstrap.init_instances()
    monkeypatch.setitem(sys.modules, "core.bootstrap", SimpleNamespace(init_instances=lambda: None))

    # utils.history_utils.save_trade_history()
    monkeypatch.setitem(sys.modules, "utils.history_utils", SimpleNamespace(save_trade_history=lambda: None))

    # core.position.sl_services.cancel_pending_sl_task
    monkeypatch.setitem(
        sys.modules,
        "core.position.sl_services",
        SimpleNamespace(cancel_pending_sl_task=lambda symbol: None),
    )

    add_log = AsyncMock()
    monkeypatch.setitem(sys.modules, "utils.logging_utils", SimpleNamespace(add_log=add_log))

    # utils.pricing.get_preferred_price
    monkeypatch.setitem(sys.modules, "utils.pricing", SimpleNamespace(get_preferred_price=lambda d: d.get("price")))

    # core.callbacks.position_check_loop._emit_stats_update
    monkeypatch.setitem(
        sys.modules,
        "core.callbacks.position_check_loop",
        SimpleNamespace(_emit_stats_update=AsyncMock()),
    )

    async def _to_thread(func, **kwargs):
        return func(**kwargs)

    monkeypatch.setattr(pos_routes.asyncio, "to_thread", _to_thread)

    return add_log


@pytest.mark.asyncio
async def test_perform_close_position_no_active_position_raises(monkeypatch: pytest.MonkeyPatch, _patched_deps):
    state = _DummyState(pos_mgr=SimpleNamespace(active_position=None))
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    with pytest.raises(ValueError, match="No active position"):
        await pos_routes.perform_close_position(reason="MANUAL", exit_price=100.0)


@pytest.mark.asyncio
async def test_perform_close_position_inconsistent_state_clears_active(monkeypatch: pytest.MonkeyPatch, _patched_deps):
    # No pos_mgr active position, but state.active_position is set
    state = _DummyState(pos_mgr=SimpleNamespace(active_position=None))
    state.active_position = {"symbol": "BTC/USDT"}
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    with pytest.raises(ValueError, match="Position state inconsistent"):
        await pos_routes.perform_close_position(reason="MANUAL", exit_price=100.0)

    assert state.active_position is None


@pytest.mark.asyncio
async def test_perform_close_position_success_fetches_exit_price_and_restarts_ws(monkeypatch: pytest.MonkeyPatch, _patched_deps):
    add_log = _patched_deps

    active_pos = SimpleNamespace(symbol="BTC/USDT")

    close_result = {"symbol": "BTC/USDT", "net_pnl_usdt": 1.0}

    pos_mgr = SimpleNamespace(active_position=active_pos, close_position=Mock(return_value=close_result))

    pp = SimpleNamespace(
        get_price=AsyncMock(return_value={"price": 101.0, "timestamp": 123}),
        set_socketio_callback=Mock(),
        set_sl_check_callback=Mock(),
        stop_websocket=AsyncMock(),
        start_websocket=AsyncMock(),
    )

    ws_mgr = SimpleNamespace(emit=AsyncMock())
    lom = SimpleNamespace(dry_run=True)

    state = _DummyState(pos_mgr=pos_mgr, pp=pp, ws_mgr=ws_mgr, lom=lom)
    state.top_pairs = [{"symbol": "BTC/USDT"}, {"symbol": "ETH/USDT"}]

    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    out = await pos_routes.perform_close_position(reason="MANUAL", exit_price=None)

    assert out["symbol"] == "BTC/USDT"
    assert "timestamp" in out

    assert state.active_position is None
    assert len(state.trades) == 1

    pp.set_socketio_callback.assert_called_once_with(None, None)
    pp.set_sl_check_callback.assert_called_once_with(None)

    pp.stop_websocket.assert_awaited_once()
    pp.start_websocket.assert_awaited_once()

    add_log.assert_awaited_once()


@pytest.mark.asyncio
async def test_perform_close_position_missing_price_provider_raises(monkeypatch: pytest.MonkeyPatch, _patched_deps):
    active_pos = SimpleNamespace(symbol="BTC/USDT")
    pos_mgr = SimpleNamespace(active_position=active_pos)
    state = _DummyState(pos_mgr=pos_mgr, pp=None, ws_mgr=None, lom=None)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    with pytest.raises(ValueError, match="Price provider not available"):
        await pos_routes.perform_close_position(reason="MANUAL", exit_price=None)


@pytest.mark.asyncio
async def test_perform_close_position_exit_price_resolution_none_still_calls_close(monkeypatch: pytest.MonkeyPatch, _patched_deps):
    add_log = _patched_deps

    active_pos = SimpleNamespace(symbol="BTC/USDT")
    close_position = Mock(return_value={"symbol": "BTC/USDT"})
    pos_mgr = SimpleNamespace(active_position=active_pos, close_position=close_position)

    pp = SimpleNamespace(
        get_price=AsyncMock(return_value={"price": None}),
        set_socketio_callback=Mock(),
        set_sl_check_callback=Mock(),
        stop_websocket=AsyncMock(),
        start_websocket=AsyncMock(),
    )

    # Force get_preferred_price to return None
    sys.modules["utils.pricing"].get_preferred_price = lambda d: None

    state = _DummyState(pos_mgr=pos_mgr, pp=pp, ws_mgr=None, lom=None)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    out = await pos_routes.perform_close_position(reason="MANUAL", exit_price=None)
    assert out["symbol"] == "BTC/USDT"
    close_position.assert_called_once()
    add_log.assert_awaited_once()


@pytest.mark.asyncio
async def test_perform_close_position_close_returns_none(monkeypatch: pytest.MonkeyPatch, _patched_deps):
    add_log = _patched_deps

    active_pos = SimpleNamespace(symbol="BTC/USDT")
    pos_mgr = SimpleNamespace(active_position=active_pos, close_position=Mock(return_value=None))

    pp = SimpleNamespace(
        get_price=AsyncMock(return_value={"price": 101.0}),
        set_socketio_callback=Mock(),
        set_sl_check_callback=Mock(),
        stop_websocket=AsyncMock(),
        start_websocket=AsyncMock(),
    )

    state = _DummyState(pos_mgr=pos_mgr, pp=pp, ws_mgr=None, lom=None)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    out = await pos_routes.perform_close_position(reason="MANUAL", exit_price=99.0)
    assert out is None
    assert state.active_position is None
    assert state.trades == []
    add_log.assert_awaited_once()


@pytest.mark.asyncio
async def test_perform_close_position_restart_ws_error_is_swallowed(monkeypatch: pytest.MonkeyPatch, _patched_deps):
    add_log = _patched_deps

    active_pos = SimpleNamespace(symbol="BTC/USDT")
    close_result = {"symbol": "BTC/USDT"}
    pos_mgr = SimpleNamespace(active_position=active_pos, close_position=Mock(return_value=close_result))

    pp = SimpleNamespace(
        get_price=AsyncMock(return_value={"price": 101.0}),
        set_socketio_callback=Mock(),
        set_sl_check_callback=Mock(),
        stop_websocket=AsyncMock(side_effect=RuntimeError("stop boom")),
        start_websocket=AsyncMock(),
    )

    ws_mgr = SimpleNamespace(emit=AsyncMock())

    state = _DummyState(pos_mgr=pos_mgr, pp=pp, ws_mgr=ws_mgr, lom=None)
    state.top_pairs = [{"symbol": "BTC/USDT"}]
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    out = await pos_routes.perform_close_position(reason="MANUAL", exit_price=None)
    assert out["symbol"] == "BTC/USDT"
    add_log.assert_awaited_once()
    ws_mgr.emit.assert_awaited()


@pytest.mark.asyncio
async def test_perform_close_position_success_with_exit_price_no_restart(monkeypatch: pytest.MonkeyPatch, _patched_deps):
    add_log = _patched_deps

    active_pos = SimpleNamespace(symbol="BTC/USDT")

    close_result = {"symbol": "BTC/USDT", "net_pnl_usdt": -1.0}

    pos_mgr = SimpleNamespace(active_position=active_pos, close_position=Mock(return_value=close_result))

    pp = SimpleNamespace(
        get_price=AsyncMock(),
        set_socketio_callback=Mock(),
        set_sl_check_callback=Mock(),
        stop_websocket=AsyncMock(),
        start_websocket=AsyncMock(),
    )

    ws_mgr = SimpleNamespace(emit=AsyncMock())
    lom = None

    state = _DummyState(pos_mgr=pos_mgr, pp=pp, ws_mgr=ws_mgr, lom=lom)
    state.top_pairs = []

    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    out = await pos_routes.perform_close_position(reason="MANUAL", exit_price=99.0)

    assert out["symbol"] == "BTC/USDT"
    assert state.active_position is None

    pp.get_price.assert_not_called()
    pp.stop_websocket.assert_not_called()
    pp.start_websocket.assert_not_called()

    add_log.assert_awaited_once()
