import os
import sys
import json
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import WebSocketDisconnect

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.state_manager as state_manager
import api.routes.websocket as ws_routes


class _FakeWebSocket:
    def __init__(self, messages):
        self._messages = list(messages)
        self.send_text = AsyncMock()
        self.close = AsyncMock()
        self.client = ("127.0.0.1", 12345)

    async def receive_text(self):
        if not self._messages:
            raise WebSocketDisconnect(code=1000)
        return self._messages.pop(0)


class _DummyState:
    def __init__(self, ws_mgr=None, pos_mgr=None, app_state=None):
        self._ws_mgr = ws_mgr
        self._pos_mgr = pos_mgr
        self._app_state = app_state or {}

    def get_ws_manager(self):
        return self._ws_mgr

    @property
    def app_state(self):
        return self._app_state

    def get_position_manager(self):
        return self._pos_mgr


class _DummyPosition:
    def __init__(self, symbol="BTC/USDT"):
        self.symbol = symbol

    def to_dict(self):
        return {"symbol": self.symbol}


class _BadPosition:
    def to_dict(self):
        raise RuntimeError("to_dict boom")


@pytest.fixture(autouse=True)
def _reset_ws_globals():
    ws_routes._ws_manager = None
    ws_routes._app_state = None
    ws_routes._position_manager = None
    ws_routes._scheduler = None
    ws_routes._price_provider = None
    yield
    ws_routes._ws_manager = None
    ws_routes._app_state = None
    ws_routes._position_manager = None
    ws_routes._scheduler = None
    ws_routes._price_provider = None


@pytest.mark.asyncio
async def test_websocket_endpoint_returns_when_no_ws_manager(monkeypatch: pytest.MonkeyPatch):
    state = _DummyState(ws_mgr=None, app_state={"logs": []})
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    ws = _FakeWebSocket([])
    await ws_routes.websocket_endpoint(ws)

    # Après corrections WebSocket : pas de fermeture agressive code 1011, juste return
    ws.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_websocket_endpoint_handles_messages(monkeypatch: pytest.MonkeyPatch):
    ws_mgr = SimpleNamespace(
        connect=AsyncMock(),
        disconnect=AsyncMock(),
        send_personal_message=AsyncMock(),
        subscribe=lambda websocket, channel: None,
        unsubscribe=lambda websocket, channel: None,
    )

    app_state = {
        "is_scanning": False,
        "logs": [{"level": "INFO", "message": "hello"}],
        "active_position": None,
    }

    state = _DummyState(ws_mgr=ws_mgr, app_state=app_state)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    async def _fake_handle(command, params):
        return {"ok": True, "cmd": command}

    monkeypatch.setattr(ws_routes, "handle_client_command", _fake_handle)

    messages = [
        json.dumps({"type": "ping"}),
        json.dumps({"type": "subscribe", "channel": "all"}),
        json.dumps({"type": "unsubscribe", "channel": "all"}),
        json.dumps({"type": "command", "id": "1", "command": "noop", "params": {}}),
        "not json",
    ]

    ws = _FakeWebSocket(messages)

    await ws_routes.websocket_endpoint(ws)

    ws_mgr.connect.assert_awaited_once_with(ws)
    ws_mgr.disconnect.assert_awaited_once_with(ws)

    assert ws_mgr.send_personal_message.await_count >= 4

    payloads = [c.args[0] for c in ws_mgr.send_personal_message.await_args_list]

    assert any(p.get("event") == "status" for p in payloads if p.get("type") == "event")
    assert any(p.get("event") == "log" for p in payloads if p.get("type") == "event")
    assert any(p.get("type") == "pong" for p in payloads)
    assert any(p.get("type") == "subscribed" for p in payloads)
    assert any(p.get("type") == "unsubscribed" for p in payloads)
    assert any(p.get("type") == "command_response" for p in payloads)


@pytest.mark.asyncio
async def test_websocket_endpoint_timeout_sends_ping_then_continues(monkeypatch: pytest.MonkeyPatch):
    ws_mgr = SimpleNamespace(
        connect=AsyncMock(),
        disconnect=AsyncMock(),
        send_personal_message=AsyncMock(),
        subscribe=lambda websocket, channel: None,
        unsubscribe=lambda websocket, channel: None,
    )

    state = _DummyState(ws_mgr=ws_mgr, app_state={"logs": []})
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    ws = _FakeWebSocket([json.dumps({"type": "ping"})])

    call = {"n": 0}

    async def _fake_wait_for(awaitable, timeout=None):
        call["n"] += 1
        if call["n"] == 1:
            # receive_text() coroutine was created by the caller; close it to avoid "never awaited" warnings
            try:
                awaitable.close()
            except Exception:
                pass
            raise ws_routes.asyncio.TimeoutError
        return await awaitable

    monkeypatch.setattr(ws_routes.asyncio, "wait_for", _fake_wait_for)

    await ws_routes.websocket_endpoint(ws)

    ws.send_text.assert_awaited_once()
    ws_mgr.connect.assert_awaited_once()
    ws_mgr.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_websocket_endpoint_timeout_ping_send_fails_continues(monkeypatch: pytest.MonkeyPatch):
    ws_mgr = SimpleNamespace(
        connect=AsyncMock(),
        disconnect=AsyncMock(),
        send_personal_message=AsyncMock(),
        subscribe=lambda websocket, channel: None,
        unsubscribe=lambda websocket, channel: None,
    )

    state = _DummyState(ws_mgr=ws_mgr, app_state={"logs": []})
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    ws = _FakeWebSocket([])
    ws.send_text = AsyncMock(side_effect=RuntimeError("send failed"))

    # Simuler seulement 2 timeouts pour éviter boucle infinie
    timeout_count = 0
    original_wait_for = ws_routes.asyncio.wait_for
    
    async def _limited_wait_for(awaitable, timeout=None):
        nonlocal timeout_count
        timeout_count += 1
        if timeout_count <= 2:
            try:
                awaitable.close()
            except Exception:
                pass
            raise ws_routes.asyncio.TimeoutError
        # Après 2 timeouts, simuler fermeture naturelle 
        raise ws_routes.WebSocketDisconnect()

    monkeypatch.setattr(ws_routes.asyncio, "wait_for", _limited_wait_for)

    await ws_routes.websocket_endpoint(ws)

    # Avec corrections WebSocket : continue sans fermeture agressive
    ws_mgr.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_websocket_endpoint_requests_and_command_error(monkeypatch: pytest.MonkeyPatch):
    ws_mgr = SimpleNamespace(
        connect=AsyncMock(),
        disconnect=AsyncMock(),
        send_personal_message=AsyncMock(),
        subscribe=lambda websocket, channel: None,
        unsubscribe=lambda websocket, channel: None,
    )

    pos_mgr = SimpleNamespace(active_position=_DummyPosition("BTC/USDT"))
    app_state = {"logs": [{"msg": "a"}], "active_position": None}
    state = _DummyState(ws_mgr=ws_mgr, pos_mgr=pos_mgr, app_state=app_state)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    async def _boom(command, params):
        raise RuntimeError("cmd failed")

    monkeypatch.setattr(ws_routes, "handle_client_command", _boom)

    # Fake dashboard get_complete_state
    _dashboard = types.ModuleType("api.routes.dashboard")

    class _FakeResp:
        def __init__(self):
            self.body = b'{"ok":true}'

    async def _get_complete_state():
        return _FakeResp()

    _dashboard.get_complete_state = _get_complete_state
    monkeypatch.setitem(sys.modules, "api.routes.dashboard", _dashboard)

    # Fake pg datalogger for trade_events
    _pg = types.ModuleType("core.postgresql_datalogger")

    class _Pg:
        def get_trade_events(self, trade_id):
            return [{"id": trade_id}]

    _pg.get_pg_datalogger = lambda: _Pg()
    monkeypatch.setitem(sys.modules, "core.postgresql_datalogger", _pg)

    messages = [
        json.dumps({"type": "request", "request_type": "logs", "id": "r1"}),
        json.dumps({"type": "request", "request_type": "position", "id": "r2"}),
        json.dumps({"type": "request", "request_type": "state", "id": "r3"}),
        json.dumps({"type": "request", "request_type": "trade_events", "id": "r4", "params": {"trade_id": "t1"}}),
        json.dumps({"type": "command", "id": "c1", "command": "x", "params": {}}),
    ]

    ws = _FakeWebSocket(messages)
    await ws_routes.websocket_endpoint(ws)

    payloads = [c.args[0] for c in ws_mgr.send_personal_message.await_args_list]
    assert any(p.get("type") == "request_response" and p.get("id") == "r1" for p in payloads)
    assert any(p.get("type") == "request_response" and p.get("id") == "r2" for p in payloads)
    assert any(p.get("type") == "request_response" and p.get("id") == "r3" for p in payloads)
    assert any(p.get("type") == "request_response" and p.get("id") == "r4" for p in payloads)
    assert any(p.get("type") == "command_error" and p.get("id") == "c1" for p in payloads)


@pytest.mark.asyncio
async def test_websocket_endpoint_trade_events_missing_trade_id(monkeypatch: pytest.MonkeyPatch):
    ws_mgr = SimpleNamespace(
        connect=AsyncMock(),
        disconnect=AsyncMock(),
        send_personal_message=AsyncMock(),
        subscribe=lambda websocket, channel: None,
        unsubscribe=lambda websocket, channel: None,
    )

    state = _DummyState(ws_mgr=ws_mgr, app_state={"logs": []})
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    msg = json.dumps({"type": "request", "request_type": "trade_events", "id": "r1", "params": {}})
    ws = _FakeWebSocket([msg])
    await ws_routes.websocket_endpoint(ws)

    payloads = [c.args[0] for c in ws_mgr.send_personal_message.await_args_list]
    te = next(p for p in payloads if p.get("type") == "request_response" and p.get("id") == "r1")
    assert te["data"]["trade_id"] is None
    assert "manquant" in (te["data"].get("error") or "").lower()


@pytest.mark.asyncio
async def test_websocket_endpoint_trade_events_pg_disabled(monkeypatch: pytest.MonkeyPatch):
    ws_mgr = SimpleNamespace(
        connect=AsyncMock(),
        disconnect=AsyncMock(),
        send_personal_message=AsyncMock(),
        subscribe=lambda websocket, channel: None,
        unsubscribe=lambda websocket, channel: None,
    )

    state = _DummyState(ws_mgr=ws_mgr, app_state={"logs": []})
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    _pg = types.ModuleType("core.postgresql_datalogger")
    _pg.get_pg_datalogger = lambda: None
    monkeypatch.setitem(sys.modules, "core.postgresql_datalogger", _pg)

    msg = json.dumps({"type": "request", "request_type": "trade_events", "id": "r1", "params": {"trade_id": "t1"}})
    ws = _FakeWebSocket([msg])
    await ws_routes.websocket_endpoint(ws)

    payloads = [c.args[0] for c in ws_mgr.send_personal_message.await_args_list]
    te = next(p for p in payloads if p.get("type") == "request_response" and p.get("id") == "r1")
    assert te["data"]["trade_id"] == "t1"
    assert te["data"]["events"] == []
    assert "désactiv" in (te["data"].get("error") or "").lower()


@pytest.mark.asyncio
async def test_websocket_endpoint_trade_events_pg_exception(monkeypatch: pytest.MonkeyPatch):
    ws_mgr = SimpleNamespace(
        connect=AsyncMock(),
        disconnect=AsyncMock(),
        send_personal_message=AsyncMock(),
        subscribe=lambda websocket, channel: None,
        unsubscribe=lambda websocket, channel: None,
    )

    state = _DummyState(ws_mgr=ws_mgr, app_state={"logs": []})
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    _pg = types.ModuleType("core.postgresql_datalogger")

    class _Pg:
        def get_trade_events(self, trade_id):
            raise RuntimeError("pg boom")

    _pg.get_pg_datalogger = lambda: _Pg()
    monkeypatch.setitem(sys.modules, "core.postgresql_datalogger", _pg)

    msg = json.dumps({"type": "request", "request_type": "trade_events", "id": "r1", "params": {"trade_id": "t1"}})
    ws = _FakeWebSocket([msg])
    await ws_routes.websocket_endpoint(ws)

    payloads = [c.args[0] for c in ws_mgr.send_personal_message.await_args_list]
    te = next(p for p in payloads if p.get("type") == "request_response" and p.get("id") == "r1")
    assert te["data"]["trade_id"] == "t1"
    assert te["data"]["events"] == []
    assert "pg boom" in (te["data"].get("error") or "")


@pytest.mark.asyncio
async def test_websocket_endpoint_initial_status_active_position_to_dict_error(monkeypatch: pytest.MonkeyPatch):
    ws_mgr = SimpleNamespace(
        connect=AsyncMock(),
        disconnect=AsyncMock(),
        send_personal_message=AsyncMock(),
        subscribe=lambda websocket, channel: None,
        unsubscribe=lambda websocket, channel: None,
    )

    app_state = {"logs": [], "active_position": _BadPosition()}
    state = _DummyState(ws_mgr=ws_mgr, app_state=app_state)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    ws = _FakeWebSocket([json.dumps({"type": "ping"})])
    await ws_routes.websocket_endpoint(ws)

    payloads = [c.args[0] for c in ws_mgr.send_personal_message.await_args_list]
    status = next(p for p in payloads if p.get("type") == "event" and p.get("event") == "status")
    assert status["data"].get("active_position") is None


@pytest.mark.asyncio
async def test_websocket_endpoint_initial_status_send_error_is_swallowed(monkeypatch: pytest.MonkeyPatch):
    # first status send raises, but loop should continue and still handle later messages
    async def _send_personal_message(payload, websocket):
        if payload.get("event") == "status":
            raise RuntimeError("send boom")

    ws_mgr = SimpleNamespace(
        connect=AsyncMock(),
        disconnect=AsyncMock(),
        send_personal_message=AsyncMock(side_effect=_send_personal_message),
        subscribe=lambda websocket, channel: None,
        unsubscribe=lambda websocket, channel: None,
    )

    state = _DummyState(ws_mgr=ws_mgr, app_state={"logs": []})
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    ws = _FakeWebSocket([json.dumps({"type": "ping"})])
    await ws_routes.websocket_endpoint(ws)

    payloads = [c.args[0] for c in ws_mgr.send_personal_message.await_args_list]
    assert any(p.get("type") == "pong" for p in payloads)


@pytest.mark.asyncio
async def test_websocket_endpoint_state_request_error(monkeypatch: pytest.MonkeyPatch):
    ws_mgr = SimpleNamespace(
        connect=AsyncMock(),
        disconnect=AsyncMock(),
        send_personal_message=AsyncMock(),
        subscribe=lambda websocket, channel: None,
        unsubscribe=lambda websocket, channel: None,
    )

    state = _DummyState(ws_mgr=ws_mgr, app_state={"logs": []})
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    _dashboard = types.ModuleType("api.routes.dashboard")

    async def _get_complete_state():
        raise RuntimeError("boom")

    _dashboard.get_complete_state = _get_complete_state
    monkeypatch.setitem(sys.modules, "api.routes.dashboard", _dashboard)

    msg = json.dumps({"type": "request", "request_type": "state", "id": "r1"})
    ws = _FakeWebSocket([msg])
    await ws_routes.websocket_endpoint(ws)

    payloads = [c.args[0] for c in ws_mgr.send_personal_message.await_args_list]
    st = next(p for p in payloads if p.get("type") == "request_response" and p.get("id") == "r1")
    assert "error" in st
