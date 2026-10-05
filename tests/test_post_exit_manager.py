import asyncio
import json
import sys
import types
from datetime import datetime, timezone

import pytest

from core.post_exit.manager import PostExitManager, get_post_exit_manager
from core.post_exit.tracker import PostExitTracker


class _DummyCursor:
    def __init__(self, rows=None):
        self._rows = rows or []
        self.rowcount = 0
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return False

    def execute(self, query, _params=None):
        self.executed.append(str(query))
        q = str(query).upper()
        if q.lstrip().startswith("DELETE") and "RETURNING" in q:
            self.rowcount = 0

    def fetchall(self):
        return self._rows


class _DummyConn:
    def __init__(self, rows=None):
        self._cursor = _DummyCursor(rows=rows)
        self.committed = False
        self.rolled_back = False

    def cursor(self, *args, **kwargs):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class _DummyDataLogger:
    def __init__(self, enabled=True, conn=None):
        self.enabled = enabled
        self._conn = conn

    def _get_connection(self):
        return self._conn

    def _return_connection(self, _conn):
        return None


def _make_tracker(trade_id=1, symbol="BTCUSDT"):
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    tracker = PostExitTracker(
        trade_id=trade_id,
        symbol=symbol,
        direction="LONG",
        exit_price=100.0,
        exit_timestamp=base,
        exit_reason="CLOSE",
        realized_pnl_pct=0.1,
        realized_pnl_usdt=10.0,
        original_sl=99.0,
        original_tp=101.0,
        entry_price=100.0,
        sample_interval_ms=0,
    )
    tracker.start_time = base.timestamp()
    tracker.add_sample(100.0, timestamp=base)
    metrics = tracker.compute_final_metrics()
    return tracker, metrics


def test_get_post_exit_manager_is_singleton():
    m1 = get_post_exit_manager()
    m2 = get_post_exit_manager()
    assert m1 is m2


@pytest.mark.asyncio
async def test_start_tracking_disabled_returns_none():
    manager = PostExitManager(config={"enabled": False})

    tracker = await manager.start_tracking(
        trade_id=1,
        symbol="BTCUSDT",
        direction="LONG",
        exit_price=100.0,
        exit_reason="CLOSE",
        realized_pnl_pct=0.1,
        realized_pnl_usdt=10.0,
        original_sl=99.0,
        original_tp=101.0,
        entry_price=100.0,
    )

    assert tracker is None


@pytest.mark.asyncio
async def test_start_tracking_adaptive_duration_and_used_params_applied():
    manager = PostExitManager(
        config={
            "tracking_duration_seconds": 15,
            "sample_interval_ms": 111,
            "adaptive_duration": True,
            "min_duration_seconds": 10,
            "max_duration_seconds": 20,
            "duration_multiplier": 2.0,
        }
    )

    tracker = await manager.start_tracking(
        trade_id=1,
        symbol="BTCUSDT",
        direction="LONG",
        exit_price=100.0,
        exit_reason="CLOSE",
        realized_pnl_pct=0.1,
        realized_pnl_usdt=10.0,
        original_sl=99.0,
        original_tp=101.0,
        entry_price=100.0,
        trade_duration_sec=3,
        used_params={
            "sl_pct": 0.3,
            "tp_pct": 0.8,
            "be_trigger": 0.2,
            "trailing_trigger": 0.25,
            "trailing_min_distance": 0.1,
            "partial_tp_pct": 0.4,
        },
    )

    assert tracker is not None
    assert tracker.tracking_duration_sec == 10
    assert tracker.sample_interval_ms == 111
    assert tracker.used_sl_pct == pytest.approx(0.3)
    assert tracker.used_trailing_trigger == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_start_tracking_completes_existing_same_symbol(monkeypatch):
    manager = PostExitManager(config={"max_concurrent_trackers": 10})

    existing, _metrics = _make_tracker(trade_id=1, symbol="BTCUSDT")
    manager.active_trackers["BTCUSDT"] = existing

    calls = []

    async def fake_complete(symbol: str, reason: str = "complete"):
        calls.append((symbol, reason))
        manager.active_trackers.pop(symbol, None)
        return {"trade_id": 1}

    monkeypatch.setattr(manager, "_complete_tracker", fake_complete)

    tracker = await manager.start_tracking(
        trade_id=2,
        symbol="BTCUSDT",
        direction="LONG",
        exit_price=100.0,
        exit_reason="CLOSE",
        realized_pnl_pct=0.1,
        realized_pnl_usdt=10.0,
        original_sl=99.0,
        original_tp=101.0,
        entry_price=100.0,
    )

    assert calls == [("BTCUSDT", "new_trade_same_symbol")]
    assert tracker is not None
    assert manager.active_trackers["BTCUSDT"].trade_id == 2


@pytest.mark.asyncio
async def test_start_tracking_enforces_max_concurrent_trackers(monkeypatch):
    manager = PostExitManager(config={"max_concurrent_trackers": 1, "sample_interval_ms": 0})

    old, _metrics = _make_tracker(trade_id=1, symbol="ETHUSDT")
    old.start_time = 0.0
    manager.active_trackers["ETHUSDT"] = old

    async def fake_save(_tracker, _metrics):
        return True

    monkeypatch.setattr(manager, "_save_to_database", fake_save)

    tracker = await manager.start_tracking(
        trade_id=2,
        symbol="BTCUSDT",
        direction="LONG",
        exit_price=100.0,
        exit_reason="CLOSE",
        realized_pnl_pct=0.1,
        realized_pnl_usdt=10.0,
        original_sl=99.0,
        original_tp=101.0,
        entry_price=100.0,
    )

    assert tracker is not None
    assert "ETHUSDT" not in manager.active_trackers
    assert "BTCUSDT" in manager.active_trackers
    assert 1 in manager.completed_metrics


@pytest.mark.asyncio
async def test_on_price_update_completes_tracker_when_duration_is_zero(monkeypatch):
    manager = PostExitManager(config={"tracking_duration_seconds": 0, "adaptive_duration": False, "sample_interval_ms": 0})

    async def fake_save(_tracker, _metrics):
        return True

    monkeypatch.setattr(manager, "_save_to_database", fake_save)

    tracker = await manager.start_tracking(
        trade_id=1,
        symbol="BTCUSDT",
        direction="LONG",
        exit_price=100.0,
        exit_reason="CLOSE",
        realized_pnl_pct=0.1,
        realized_pnl_usdt=10.0,
        original_sl=99.0,
        original_tp=101.0,
        entry_price=100.0,
    )
    assert tracker is not None
    assert manager.is_tracking("BTCUSDT") is True

    await manager.on_price_update("BTCUSDT", 100.0)

    assert manager.is_tracking("BTCUSDT") is False
    assert 1 in manager.completed_metrics


def test_start_tracking_sync_creates_new_loop_and_returns_tracker():
    manager = PostExitManager(config={"adaptive_duration": False, "sample_interval_ms": 0})

    tracker = manager.start_tracking_sync(
        trade_id=1,
        symbol="BTCUSDT",
        direction="LONG",
        exit_price=100.0,
        exit_reason="CLOSE",
        realized_pnl_pct=0.1,
        realized_pnl_usdt=10.0,
        original_sl=99.0,
        original_tp=101.0,
        entry_price=100.0,
    )

    assert tracker is not None
    assert manager.is_tracking("BTCUSDT") is True


def test_start_tracking_sync_running_loop_schedules_and_returns_none(monkeypatch):
    manager = PostExitManager(config={"adaptive_duration": False, "sample_interval_ms": 0})

    dummy_loop = object()

    monkeypatch.setattr(asyncio, "get_running_loop", lambda: dummy_loop)

    calls = []

    def fake_run_coroutine_threadsafe(coro, loop):
        calls.append(loop)
        assert loop is dummy_loop
        assert hasattr(coro, "send")
        return object()

    monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", fake_run_coroutine_threadsafe)

    res = manager.start_tracking_sync(
        trade_id=1,
        symbol="BTCUSDT",
        direction="LONG",
        exit_price=100.0,
        exit_reason="CLOSE",
        realized_pnl_pct=0.1,
        realized_pnl_usdt=10.0,
        original_sl=99.0,
        original_tp=101.0,
        entry_price=100.0,
    )

    assert res is None
    assert calls == [dummy_loop]


def test_on_price_update_sync_spawns_completion_thread(monkeypatch):
    manager = PostExitManager(config={"tracking_duration_seconds": 0, "adaptive_duration": False, "sample_interval_ms": 0})

    async def fake_save(_tracker, _metrics):
        return True

    monkeypatch.setattr(manager, "_save_to_database", fake_save)

    tracker = manager.start_tracking_sync(
        trade_id=1,
        symbol="BTCUSDT",
        direction="LONG",
        exit_price=100.0,
        exit_reason="CLOSE",
        realized_pnl_pct=0.1,
        realized_pnl_usdt=10.0,
        original_sl=99.0,
        original_tp=101.0,
        entry_price=100.0,
    )
    assert tracker is not None

    class _ImmediateThread:
        def __init__(self, target=None, args=(), kwargs=None, daemon=None):
            self._target = target
            self._args = args
            self._kwargs = kwargs or {}

        def start(self):
            self._target(*self._args, **self._kwargs)

    monkeypatch.setattr("core.post_exit.manager.threading.Thread", _ImmediateThread)

    manager.on_price_update_sync("BTCUSDT", 100.0)

    assert manager.is_tracking("BTCUSDT") is False
    assert 1 in manager.completed_metrics


@pytest.mark.asyncio
async def test_save_to_database_returns_false_when_datalogger_missing(monkeypatch):
    manager = PostExitManager(config={"store_raw_samples": False})
    tracker, metrics = _make_tracker(trade_id=1, symbol="BTCUSDT")

    fake_mod = types.SimpleNamespace(get_pg_datalogger=lambda: None)
    monkeypatch.setitem(sys.modules, "core.postgresql_datalogger", fake_mod)

    ok = await manager._save_to_database(tracker, metrics)
    assert ok is False


@pytest.mark.asyncio
async def test_save_to_database_returns_true_when_connection_available(monkeypatch):
    manager = PostExitManager(config={"store_raw_samples": False})
    tracker, metrics = _make_tracker(trade_id=1, symbol="BTCUSDT")

    conn = _DummyConn()
    datalogger = _DummyDataLogger(enabled=True, conn=conn)
    fake_mod = types.SimpleNamespace(get_pg_datalogger=lambda: datalogger)
    monkeypatch.setitem(sys.modules, "core.postgresql_datalogger", fake_mod)

    ok = await manager._save_to_database(tracker, metrics)
    assert ok is True
    assert conn.committed is True


@pytest.mark.asyncio
async def test_persist_and_restore_roundtrip(monkeypatch):
    manager = PostExitManager(config={"sample_interval_ms": 0})

    tracker, _metrics = _make_tracker(trade_id=1, symbol="BTCUSDT")
    manager.active_trackers["BTCUSDT"] = tracker

    conn = _DummyConn(rows=[])
    datalogger = _DummyDataLogger(enabled=True, conn=conn)
    fake_mod = types.SimpleNamespace(get_pg_datalogger=lambda: datalogger)
    monkeypatch.setitem(sys.modules, "core.postgresql_datalogger", fake_mod)

    persisted = await manager.persist_active_trackers()
    assert persisted == 1
    assert conn.committed is True

    sample_ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
    samples_json = json.dumps([
        {"ts": sample_ts.isoformat(), "p": 100.0, "pnl": 0.0, "mfe": 0.0, "mae": 0.0}
    ])

    row = {
        "trade_id": "2",
        "symbol": "ETHUSDT",
        "direction": "LONG",
        "exit_price": 100.0,
        "exit_timestamp": sample_ts,
        "exit_reason": "CLOSE",
        "realized_pnl_pct": 0.1,
        "realized_pnl_usdt": 10.0,
        "original_sl": 99.0,
        "original_tp": 101.0,
        "entry_price": 100.0,
        "tracking_duration_sec": 600,
        "sample_interval_ms": 2000,
        "used_sl_pct": None,
        "used_tp_pct": None,
        "used_be_trigger": None,
        "used_trailing_trigger": None,
        "used_trailing_min_distance": None,
        "used_partial_tp_pct": None,
        "start_time": sample_ts,
        "post_exit_mfe_pct": 0.0,
        "post_exit_mfe_price": None,
        "post_exit_mfe_timestamp": None,
        "post_exit_mae_pct": 0.0,
        "post_exit_mae_price": None,
        "post_exit_mae_timestamp": None,
        "would_have_hit_original_tp": False,
        "would_have_hit_original_sl": False,
        "price_returned_to_entry": False,
        "samples_json": samples_json,
    }

    conn_2 = _DummyConn(rows=[row])
    datalogger_2 = _DummyDataLogger(enabled=True, conn=conn_2)
    fake_mod_2 = types.SimpleNamespace(get_pg_datalogger=lambda: datalogger_2)
    monkeypatch.setitem(sys.modules, "core.postgresql_datalogger", fake_mod_2)

    restored_manager = PostExitManager(config={"sample_interval_ms": 0})
    restored = await restored_manager.restore_active_trackers()

    assert restored == 1
    assert "ETHUSDT" in restored_manager.active_trackers
    assert len(restored_manager.active_trackers["ETHUSDT"].samples) == 1
