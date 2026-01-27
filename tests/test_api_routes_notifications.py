import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.state_manager as state_manager
import api.routes.notifications as notif_routes
from api.routes.notifications import perform_telegram_config_update, perform_telegram_test


class _DummyNotifMgr:
    def __init__(self):
        self.telegram_notify_settings = {}
        self.telegram_notifier = None


class _DummyState:
    def __init__(self, notif_mgr=None):
        self._notif_mgr = notif_mgr

    def get_notification_manager(self):
        return self._notif_mgr


class _DummyRequest:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_perform_telegram_config_update_updates_env_and_persists_env_file(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)

    (tmp_path / ".env").write_text(
        "TELEGRAM_NOTIFY_POSITION_OPENED=false\nTELEGRAM_NOTIFY_ERROR=true\n",
        encoding="utf-8",
    )

    notif_mgr = _DummyNotifMgr()
    dummy_state = _DummyState(notif_mgr=notif_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: dummy_state)

    params = {
        "TELEGRAM_NOTIFY_POSITION_OPENED": True,
        "TELEGRAM_NOTIFY_ERROR": False,
        "TELEGRAM_NOTIFY_DAILY_SUMMARY": True,
    }

    updated = await perform_telegram_config_update(params)

    assert updated["TELEGRAM_NOTIFY_POSITION_OPENED"] is True
    assert updated["TELEGRAM_NOTIFY_ERROR"] is False
    assert updated["TELEGRAM_NOTIFY_DAILY_SUMMARY"] is True

    assert os.environ["TELEGRAM_NOTIFY_POSITION_OPENED"] == "true"
    assert os.environ["TELEGRAM_NOTIFY_ERROR"] == "false"
    assert os.environ["TELEGRAM_NOTIFY_DAILY_SUMMARY"] == "true"

    assert notif_mgr.telegram_notify_settings["position_opened"] is True
    assert notif_mgr.telegram_notify_settings["error"] is False
    assert notif_mgr.telegram_notify_settings["daily_summary"] is True

    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "TELEGRAM_NOTIFY_POSITION_OPENED=true" in env_text
    assert "TELEGRAM_NOTIFY_ERROR=false" in env_text
    assert "TELEGRAM_NOTIFY_DAILY_SUMMARY=true" in env_text


@pytest.mark.asyncio
async def test_perform_telegram_config_update_without_notification_manager(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("", encoding="utf-8")

    dummy_state = _DummyState(notif_mgr=None)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: dummy_state)

    updated = await perform_telegram_config_update({"TELEGRAM_NOTIFY_ERROR": True})
    assert updated["TELEGRAM_NOTIFY_ERROR"] is True


@pytest.mark.asyncio
async def test_perform_telegram_test_returns_not_configured(monkeypatch: pytest.MonkeyPatch):
    import config as config_module

    monkeypatch.setattr(config_module, "TELEGRAM_ENABLED", False, raising=False)
    monkeypatch.setattr(config_module, "TELEGRAM_BOT_TOKEN", "", raising=False)
    monkeypatch.setattr(config_module, "TELEGRAM_CHAT_ID", "", raising=False)

    res = await perform_telegram_test()
    assert res["success"] is False
    assert "Telegram non configuré" in res["error"]


@pytest.mark.asyncio
async def test_perform_telegram_test_sends_message(monkeypatch: pytest.MonkeyPatch):
    import config as config_module

    monkeypatch.setattr(config_module, "TELEGRAM_ENABLED", True, raising=False)
    monkeypatch.setattr(config_module, "TELEGRAM_BOT_TOKEN", "x", raising=False)
    monkeypatch.setattr(config_module, "TELEGRAM_CHAT_ID", "y", raising=False)

    telegram_notifier = SimpleNamespace(send_message=AsyncMock(return_value=True))
    notif_mgr = _DummyNotifMgr()
    notif_mgr.telegram_notifier = telegram_notifier

    dummy_state = _DummyState(notif_mgr=notif_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: dummy_state)

    res = await perform_telegram_test()
    assert res["success"] is True
    telegram_notifier.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_perform_telegram_test_send_fails(monkeypatch: pytest.MonkeyPatch):
    import config as config_module

    monkeypatch.setattr(config_module, "TELEGRAM_ENABLED", True, raising=False)
    monkeypatch.setattr(config_module, "TELEGRAM_BOT_TOKEN", "x", raising=False)
    monkeypatch.setattr(config_module, "TELEGRAM_CHAT_ID", "y", raising=False)

    telegram_notifier = SimpleNamespace(send_message=AsyncMock(return_value=False))
    notif_mgr = _DummyNotifMgr()
    notif_mgr.telegram_notifier = telegram_notifier

    dummy_state = _DummyState(notif_mgr=notif_mgr)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: dummy_state)

    res = await perform_telegram_test()
    assert res["success"] is False
    assert "Erreur lors de l'envoi" in res["error"]


@pytest.mark.asyncio
async def test_perform_telegram_test_no_manager(monkeypatch: pytest.MonkeyPatch):
    import config as config_module

    monkeypatch.setattr(config_module, "TELEGRAM_ENABLED", True, raising=False)
    monkeypatch.setattr(config_module, "TELEGRAM_BOT_TOKEN", "x", raising=False)
    monkeypatch.setattr(config_module, "TELEGRAM_CHAT_ID", "y", raising=False)

    dummy_state = _DummyState(notif_mgr=None)
    monkeypatch.setattr(state_manager, "get_state_manager", lambda: dummy_state)

    res = await perform_telegram_test()
    assert res["success"] is False
    assert "Notification manager" in res["error"]


@pytest.mark.asyncio
async def test_api_update_telegram_config_success(monkeypatch: pytest.MonkeyPatch):
    async def _fake_update(params):
        return {"TELEGRAM_NOTIFY_ERROR": True}

    monkeypatch.setattr(notif_routes, "perform_telegram_config_update", _fake_update)
    req = _DummyRequest({"TELEGRAM_NOTIFY_ERROR": True})

    resp = await notif_routes.api_update_telegram_config(req)
    assert resp.status_code == 200
    body = resp.body.decode("utf-8")
    assert '"success":true' in body
    assert '"TELEGRAM_NOTIFY_ERROR":true' in body


@pytest.mark.asyncio
async def test_api_update_telegram_config_error(monkeypatch: pytest.MonkeyPatch):
    async def _fake_update(params):
        raise RuntimeError("boom")

    monkeypatch.setattr(notif_routes, "perform_telegram_config_update", _fake_update)
    req = _DummyRequest({"TELEGRAM_NOTIFY_ERROR": True})

    resp = await notif_routes.api_update_telegram_config(req)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_api_test_telegram_success(monkeypatch: pytest.MonkeyPatch):
    async def _fake_test():
        return {"success": True}

    monkeypatch.setattr(notif_routes, "perform_telegram_test", _fake_test)

    resp = await notif_routes.api_test_telegram()
    assert resp.status_code == 200
    assert resp.body.decode("utf-8") == '{"success":true}'


@pytest.mark.asyncio
async def test_api_test_telegram_error(monkeypatch: pytest.MonkeyPatch):
    async def _fake_test():
        raise RuntimeError("boom")

    monkeypatch.setattr(notif_routes, "perform_telegram_test", _fake_test)

    resp = await notif_routes.api_test_telegram()
    assert resp.status_code == 500
