import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.routes import config as config_routes


@pytest.mark.asyncio
async def test_update_mexc_token_persists_and_status_reads(tmp_path, monkeypatch: pytest.MonkeyPatch):
    creds = tmp_path / "credentials.json"
    monkeypatch.setattr(config_routes, "CREDENTIALS_FILE", str(creds))

    token = "x" * 30
    resp = await config_routes.update_mexc_token(config_routes.MexcTokenRequest(token=token))

    assert resp.success is True
    assert "Token mis à jour" in resp.message
    assert resp.updated_at is not None

    assert creds.exists()
    data = json.loads(creds.read_text(encoding="utf-8"))
    assert data["mexc_web_token"] == token
    assert "mexc_web_token_updated_at" in data

    status = await config_routes.get_mexc_token_status()
    assert status["has_token"] is True
    assert status["token_length"] == len(token)
    assert status["token_preview"].startswith(token[:10])


@pytest.mark.asyncio
async def test_update_mexc_token_rejects_empty(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(config_routes, "CREDENTIALS_FILE", str(tmp_path / "credentials.json"))

    with pytest.raises(Exception) as exc:
        await config_routes.update_mexc_token(config_routes.MexcTokenRequest(token=""))
    assert getattr(exc.value, "detail", "") == "Token vide"


@pytest.mark.asyncio
async def test_update_mexc_token_rejects_too_short(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(config_routes, "CREDENTIALS_FILE", str(tmp_path / "credentials.json"))

    with pytest.raises(Exception) as exc:
        await config_routes.update_mexc_token(config_routes.MexcTokenRequest(token="short"))
    assert "Token trop court" in getattr(exc.value, "detail", "")


@pytest.mark.asyncio
async def test_get_mexc_token_status_no_file(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(config_routes, "CREDENTIALS_FILE", str(tmp_path / "missing.json"))

    status = await config_routes.get_mexc_token_status()
    assert status["has_token"] is False


@pytest.mark.asyncio
async def test_get_mexc_token_status_corrupted_file(tmp_path, monkeypatch: pytest.MonkeyPatch):
    creds = tmp_path / "credentials.json"
    creds.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(config_routes, "CREDENTIALS_FILE", str(creds))

    token = "y" * 30
    resp = await config_routes.update_mexc_token(config_routes.MexcTokenRequest(token=token))
    assert resp.success is True

    status = await config_routes.get_mexc_token_status()
    assert status["has_token"] is True
