"""Async tests for datalogger endpoints."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Dict, List, Sequence

import pytest
from httpx import AsyncClient, ASGITransport

from main import app


class FakeCursor:
    """Simple cursor stub supporting SELECT and DELETE statements."""

    def __init__(
        self,
        *,
        select_results: Sequence[List[Dict]] | None = None,
        delete_rowcounts: Dict[str, int] | None = None,
    ) -> None:
        self._select_results = list(select_results or [])
        self._delete_rowcounts = delete_rowcounts or {}
        self._select_index = -1
        self._current_rows: List[Dict] = []
        self.rowcount = 0

    def execute(self, query: str, params=None) -> None:  # pragma: no cover - trivial
        normalized = query.strip().upper()
        if normalized.startswith("SELECT"):
            self._select_index += 1
            if self._select_index < len(self._select_results):
                self._current_rows = self._select_results[self._select_index]
            else:
                self._current_rows = []
            self.rowcount = len(self._current_rows)
        elif normalized.startswith("DELETE FROM"):
            table = query.split()[2]
            self.rowcount = self._delete_rowcounts.get(table, 0)
            self._current_rows = []
        else:
            self._current_rows = []
            self.rowcount = 0

    def fetchall(self) -> List[Dict]:  # pragma: no cover - trivial
        return list(self._current_rows)


def patch_get_cursor(monkeypatch, *, select_results=None, delete_rowcounts=None):
    @contextmanager
    def fake_get_cursor(dict_cursor: bool = False):  # pylint: disable=unused-argument
        cursor = FakeCursor(
            select_results=select_results,
            delete_rowcounts=delete_rowcounts,
        )
        yield cursor

    monkeypatch.setattr("api.routes.datalogger.get_cursor", fake_get_cursor)


@pytest.mark.asyncio
async def test_export_excel_returns_workbook(monkeypatch):
    select_rows = [
        [
            {
                "timestamp": "2025-11-15T12:00:00",
                "symbol": "BTC/USDT",
                "price": 36000,
                "scan_duration_ms": 120,
                "rsi_1m": 55,
                "rsi_5m": 60,
                "score_total": 10,
                "is_opportunity": True,
                "opportunity_direction": "LONG",
                "reject_reason": None,
                "trend_direction": "UP",
                "trend_strength": "STRONG",
            }
        ],
        [
            {
                "timestamp": "2025-11-15T12:00:05",
                "symbol": "BTC/USDT",
                "direction": "LONG",
                "setup_score": 10,
                "entry_price": 36000,
                "tp_price": 36100,
                "sl_price": 35900,
                "conditions_matched": ["RSI", "Breakout"],
                "confirmed_by": "5m",
            }
        ],
        [
            {
                "timestamp_entry": "2025-11-15T12:01:00",
                "timestamp_exit": "2025-11-15T12:02:30",
                "symbol": "BTC/USDT",
                "direction": "LONG",
                "entry_price": 36000,
                "exit_price": 36080,
                "size_usdt": 100,
                "gross_pnl_usdt": 8,
                "net_pnl_usdt": 7.5,
                "net_pnl_pct": 0.75,
                "exit_reason": "TP",
                "duration_seconds": 90,
                "win": True,
            }
        ],
    ]

    patch_get_cursor(monkeypatch, select_results=select_rows)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/datalogger/export/excel")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats"
    )
    assert response.content[:2] == b"PK"  # XLSX files are zipped archives


@pytest.mark.asyncio
async def test_reset_datalogger_returns_counts(monkeypatch):
    delete_counts = {
        'trades': 2,
        'opportunities': 5,
        'scan_logs': 10,
        'scan_errors': 1,
        'market_context': 0,
        'config_snapshots': 3,
        'trading_sessions': 4,
    }

    patch_get_cursor(monkeypatch, delete_rowcounts=delete_counts)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/api/datalogger/reset")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["deleted"] == delete_counts
    assert payload["total_deleted"] == sum(delete_counts.values())
