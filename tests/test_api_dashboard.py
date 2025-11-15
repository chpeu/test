"""Async tests for dashboard endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from main import app
from api.routes.dashboard import _get_app_state_dependency as dependency_app_state


@pytest.fixture
def fake_app_state():
    return {
        "is_scanning": True,
        "active_position": {"symbol": "BTC/USDT"},
        "stats": {"total_trades": 5, "wins": 3, "losses": 2, "winrate": 60.0},
        "top_pairs": [{"symbol": "BTC/USDT"}],
        "logs": [],
        "trade_history": [
            {
                "timestamp": "2025-11-15T12:00:00",
                "net_pnl_usdt": 5,
                "net_pnl_pct": 0.5,
                "gross_pnl_pct": 0.6,
            }
        ],
    }


@pytest.fixture(autouse=True)
def override_app_state(fake_app_state):
    app.dependency_overrides[dependency_app_state] = lambda: fake_app_state
    yield
    app.dependency_overrides.pop(dependency_app_state, None)


@pytest.mark.asyncio
async def test_status_endpoint_returns_app_state(fake_app_state):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["is_scanning"] == fake_app_state["is_scanning"]


@pytest.mark.asyncio
async def test_state_endpoint_includes_config_and_stats(fake_app_state):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/state")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["scanner"]["is_scanning"] == fake_app_state["is_scanning"]
    assert payload["stats"]["total_trades"] == fake_app_state["stats"]["total_trades"]
