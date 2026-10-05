import os
import sys
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.callbacks.position_check_loop as pcl


class _DummyAnalyticsDB:
    def __init__(self, trades):
        self._trades = trades

    def get_trades(self, limit=10000):
        return list(self._trades)


@pytest.fixture(autouse=True)
def _reset_globals():
    pcl._ws_manager = None
    pcl._app_state = None
    pcl._analytics_db = None
    yield
    pcl._ws_manager = None
    pcl._app_state = None
    pcl._analytics_db = None


@pytest.mark.asyncio
async def test_emit_stats_update_uses_analytics_db(monkeypatch: pytest.MonkeyPatch):
    ws_mgr = type("_WM", (), {"emit": AsyncMock()})()
    pcl._ws_manager = ws_mgr
    pcl._app_state = {"trade_history": []}

    trades = [
        {"net_pnl_usdt": 1.5, "net_pnl_pct": 0.1, "duration_seconds": 10},
        {"net_pnl_usdt": -0.5, "net_pnl_pct": -0.05, "duration_seconds": 20},
    ]
    pcl._analytics_db = _DummyAnalyticsDB(trades)

    await pcl._emit_stats_update()

    ws_mgr.emit.assert_awaited_once()
    event, stats = ws_mgr.emit.await_args.args
    assert event == "stats_update"
    assert stats["total_trades"] == 2
    assert stats["wins"] == 1
    assert stats["losses"] == 1


@pytest.mark.asyncio
async def test_emit_stats_update_fallbacks_to_app_state_trade_history(monkeypatch: pytest.MonkeyPatch):
    ws_mgr = type("_WM", (), {"emit": AsyncMock()})()
    pcl._ws_manager = ws_mgr

    pcl._analytics_db = None
    pcl._app_state = {
        "trade_history": [
            {"net_pnl_usdt": 2.0, "net_pnl_pct": 0.2},
            {"net_pnl_usdt": -1.0, "net_pnl_pct": -0.1},
        ]
    }

    await pcl._emit_stats_update()

    event, stats = ws_mgr.emit.await_args.args
    assert stats["total_trades"] == 2
    assert stats["wins"] == 1
    assert stats["losses"] == 1


def test_update_session_stats_updates_app_state_counts():
    pcl._app_state = {"stats": {"total_trades": 0, "wins": 0, "losses": 0, "winrate": 0.0}}

    pcl._update_session_stats({"net_pnl_usdt": 1.0})
    assert pcl._app_state["stats"]["total_trades"] == 1
    assert pcl._app_state["stats"]["wins"] == 1
    assert pcl._app_state["stats"]["losses"] == 0

    pcl._update_session_stats({"net_pnl_usdt": -0.1})
    assert pcl._app_state["stats"]["total_trades"] == 2
    assert pcl._app_state["stats"]["wins"] == 1
    assert pcl._app_state["stats"]["losses"] == 1


def test_calculate_next_event_escalier_and_priorities():
    class _Pos:
        symbol = "TEST/USDT"
        direction = "LONG"
        entry = 100.0
        tp = 120.0
        sl = 90.0
        tp_escalier_levels = [{"pct": 2.0}, {"pct": 4.0}]
        current_tp_level = 0
        tp_sl_mode = "ESCALIER"
        partial_tp_sold = False
        break_even_triggered = False
        trailing_activated = False

    pos = _Pos()

    out = pcl._calculate_next_event(
        position=pos,
        current_price=101.0,
        pnl_pct=0.01,
        atr_percent=1.0,
        break_even_trigger_pct=2.0,
        trailing_trigger_pct=3.0,
        effective_config={},
        trading_config={"tp_sl_mode": "ESCALIER"},
    )

    assert out["next_sl"]["type"] == "SL"
    assert out["next_tp"]["type"].startswith("TP")
    assert out["next_event"] is not None
    # priority ordering: SL (0) should be selected even if farther
    assert out["next_event"]["type"] == "SL"
