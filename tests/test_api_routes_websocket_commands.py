import os
import sys
import types
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.state_manager as state_manager
import api.routes.websocket as ws_routes


class _DummyState:
    def __init__(self, ws_mgr=None):
        self._ws_mgr = ws_mgr
        self.top_pairs = []
        self._is_scanning = False
        self._scheduler = None

    def get_ws_manager(self):
        return self._ws_mgr

    def get_scheduler(self):
        return self._scheduler

    def set_is_scanning(self, value: bool):
        self._is_scanning = bool(value)


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


def _install_module(monkeypatch: pytest.MonkeyPatch, name: str, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    monkeypatch.setitem(sys.modules, name, mod)
    return mod


@pytest.mark.asyncio
async def test_handle_client_command_start_scanner_emits_and_sets_scanning(monkeypatch: pytest.MonkeyPatch):
    ws_mgr = types.SimpleNamespace(
        emit=AsyncMock(),
        _command_handlers={},
        handle_command=AsyncMock(),
    )
    state = _DummyState(ws_mgr=ws_mgr)
    state.top_pairs = []

    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    init_instances = AsyncMock()

    async def _run_initial_top_pairs_scan():
        return None

    _install_module(
        monkeypatch,
        "core.bootstrap",
        init_instances=init_instances,
        run_initial_top_pairs_scan=_run_initial_top_pairs_scan,
    )

    _install_module(monkeypatch, "utils.logging_utils", add_log=AsyncMock())

    created = {"called": 0}

    def _fake_create_task(coro):
        created["called"] += 1
        return None

    monkeypatch.setattr(ws_routes.asyncio, "create_task", _fake_create_task)

    out = await ws_routes.handle_client_command("start_scanner", {})

    init_instances.assert_awaited_once()
    assert state._is_scanning is True
    assert ws_mgr.emit.await_count == 2
    assert created["called"] == 1
    assert out["status"] == "started"


@pytest.mark.asyncio
async def test_handle_client_command_stop_scanner(monkeypatch: pytest.MonkeyPatch):
    ws_mgr = types.SimpleNamespace(emit=AsyncMock(), _command_handlers={}, handle_command=AsyncMock())
    state = _DummyState(ws_mgr=ws_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    _install_module(monkeypatch, "core.bootstrap", init_instances=AsyncMock(), run_initial_top_pairs_scan=AsyncMock())
    _install_module(monkeypatch, "utils.logging_utils", add_log=AsyncMock())

    async def _perform_stop_scanner():
        return {"ok": True}

    _install_module(monkeypatch, "api.routes.scanner", perform_stop_scanner=_perform_stop_scanner)

    out = await ws_routes.handle_client_command("stop_scanner", {})
    assert out == {"ok": True}


@pytest.mark.asyncio
async def test_handle_client_command_close_position(monkeypatch: pytest.MonkeyPatch):
    ws_mgr = types.SimpleNamespace(emit=AsyncMock(), _command_handlers={}, handle_command=AsyncMock())
    state = _DummyState(ws_mgr=ws_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    _install_module(monkeypatch, "core.bootstrap", init_instances=AsyncMock(), run_initial_top_pairs_scan=AsyncMock())
    _install_module(monkeypatch, "utils.logging_utils", add_log=AsyncMock())

    async def _perform_close_position(reason="MANUAL", exit_price=None):
        return {"reason": reason, "exit": exit_price}

    _install_module(monkeypatch, "api.routes.position", perform_close_position=_perform_close_position)

    out = await ws_routes.handle_client_command("close_position", {"reason": "MANUAL", "exit_price": 123.0})
    assert out["status"] == "closed"
    assert out["result"]["exit"] == 123.0


@pytest.mark.asyncio
async def test_handle_client_command_update_config(monkeypatch: pytest.MonkeyPatch):
    ws_mgr = types.SimpleNamespace(emit=AsyncMock(), _command_handlers={}, handle_command=AsyncMock())
    state = _DummyState(ws_mgr=ws_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    _install_module(monkeypatch, "core.bootstrap", init_instances=AsyncMock(), run_initial_top_pairs_scan=AsyncMock())
    _install_module(monkeypatch, "utils.logging_utils", add_log=AsyncMock())

    async def _perform_config_update(params):
        return {"x": 1}

    _install_module(monkeypatch, "api.routes.config", perform_config_update=_perform_config_update)

    out = await ws_routes.handle_client_command("update_config", {"any": "thing"})
    assert out == {"status": "success", "updated": {"x": 1}}


@pytest.mark.asyncio
async def test_handle_client_command_update_telegram_and_test(monkeypatch: pytest.MonkeyPatch):
    ws_mgr = types.SimpleNamespace(emit=AsyncMock(), _command_handlers={}, handle_command=AsyncMock())
    state = _DummyState(ws_mgr=ws_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    _install_module(monkeypatch, "core.bootstrap", init_instances=AsyncMock(), run_initial_top_pairs_scan=AsyncMock())
    _install_module(monkeypatch, "utils.logging_utils", add_log=AsyncMock())

    async def _perform_telegram_config_update(params):
        return {"ok": True}

    async def _perform_telegram_test():
        return {"success": True}

    _install_module(
        monkeypatch,
        "api.routes.notifications",
        perform_telegram_config_update=_perform_telegram_config_update,
        perform_telegram_test=_perform_telegram_test,
    )

    out1 = await ws_routes.handle_client_command("update_telegram_config", {"a": 1})
    assert out1 == {"status": "success", "updated": {"ok": True}}

    out2 = await ws_routes.handle_client_command("test_telegram", {})
    assert out2 == {"success": True}


@pytest.mark.asyncio
async def test_handle_client_command_reboot_backend(monkeypatch: pytest.MonkeyPatch):
    ws_mgr = types.SimpleNamespace(emit=AsyncMock(), _command_handlers={}, handle_command=AsyncMock())
    state = _DummyState(ws_mgr=ws_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    _install_module(monkeypatch, "core.bootstrap", init_instances=AsyncMock(), run_initial_top_pairs_scan=AsyncMock())
    _install_module(monkeypatch, "utils.logging_utils", add_log=AsyncMock())

    async def _initiate_backend_reboot(reason="manual"):
        return {"ok": True, "reason": reason}

    _install_module(monkeypatch, "api.routes.dashboard", initiate_backend_reboot=_initiate_backend_reboot)

    out = await ws_routes.handle_client_command("reboot_backend", {"reason": "manual"})
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_handle_client_command_log_config(monkeypatch: pytest.MonkeyPatch):
    ws_mgr = types.SimpleNamespace(emit=AsyncMock(), _command_handlers={}, handle_command=AsyncMock())
    state = _DummyState(ws_mgr=ws_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    _install_module(monkeypatch, "core.bootstrap", init_instances=AsyncMock(), run_initial_top_pairs_scan=AsyncMock())
    add_log = AsyncMock()
    _install_module(monkeypatch, "utils.logging_utils", add_log=add_log)

    out = await ws_routes.handle_client_command("log_config", {"key": "k", "change": "v"})
    assert out["status"] == "logged"
    add_log.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_client_command_dynamic_handler(monkeypatch: pytest.MonkeyPatch):
    ws_mgr = types.SimpleNamespace(
        emit=AsyncMock(),
        _command_handlers={"custom": True},
        handle_command=AsyncMock(return_value={"ok": True}),
    )
    state = _DummyState(ws_mgr=ws_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    _install_module(monkeypatch, "core.bootstrap", init_instances=AsyncMock(), run_initial_top_pairs_scan=AsyncMock())
    _install_module(monkeypatch, "utils.logging_utils", add_log=AsyncMock())

    out = await ws_routes.handle_client_command("custom", {"a": 1})
    ws_mgr.handle_command.assert_awaited_once()
    assert out == {"ok": True}


@pytest.mark.asyncio
async def test_handle_client_command_unknown(monkeypatch: pytest.MonkeyPatch):
    ws_mgr = types.SimpleNamespace(emit=AsyncMock(), _command_handlers={}, handle_command=AsyncMock())
    state = _DummyState(ws_mgr=ws_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: state)

    _install_module(monkeypatch, "core.bootstrap", init_instances=AsyncMock(), run_initial_top_pairs_scan=AsyncMock())
    _install_module(monkeypatch, "utils.logging_utils", add_log=AsyncMock())

    out = await ws_routes.handle_client_command("nope", {})
    assert out["status"] == "error"
