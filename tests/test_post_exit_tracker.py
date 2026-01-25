from datetime import datetime, timedelta, timezone

import pytest

from core.post_exit.tracker import PostExitTracker


def _make_tracker(**overrides):
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    params = {
        "trade_id": 1,
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "exit_price": 100.0,
        "exit_timestamp": base,
        "exit_reason": "CLOSE",
        "realized_pnl_pct": 0.5,
        "realized_pnl_usdt": 50.0,
        "original_sl": 95.0,
        "original_tp": 110.0,
        "entry_price": 100.0,
        "used_sl_pct": 0.3,
        "used_tp_pct": 0.8,
        "used_be_trigger": 0.2,
        "used_trailing_trigger": 0.2,
        "used_trailing_min_distance": 0.10,
        "used_partial_tp_pct": None,
        "tracking_duration_sec": 600,
        "sample_interval_ms": 2000,
        "start_time": base.timestamp(),
        "last_sample_time": 0.0,
    }
    params.update(overrides)
    return PostExitTracker(**params), base


def test_add_sample_interval_mfe_mae_and_flags_long():
    tracker, base = _make_tracker(sample_interval_ms=2000)

    assert tracker.add_sample(102.0, timestamp=base) is True
    assert len(tracker.samples) == 1
    assert tracker.post_exit_mfe_pct == pytest.approx(2.0)
    assert tracker.post_exit_mae_pct == pytest.approx(0.0)
    assert tracker.would_have_hit_original_tp is False

    assert tracker.add_sample(101.0, timestamp=base + timedelta(milliseconds=1000)) is False
    assert len(tracker.samples) == 1

    assert tracker.add_sample(94.0, timestamp=base + timedelta(milliseconds=2500)) is True
    assert len(tracker.samples) == 2
    assert tracker.would_have_hit_original_sl is True
    assert tracker.post_exit_mae_pct == pytest.approx(6.0)

    assert tracker.add_sample(100.04, timestamp=base + timedelta(milliseconds=5000)) is True
    assert tracker.price_returned_to_entry is True


def test_add_sample_short_sets_tp_sl_flags():
    tracker, base = _make_tracker(
        direction="SHORT",
        original_tp=90.0,
        original_sl=105.0,
        symbol="ETHUSDT",
    )

    assert tracker.add_sample(98.0, timestamp=base) is True
    assert tracker.post_exit_mfe_pct == pytest.approx(2.0)

    assert tracker.add_sample(89.0, timestamp=base + timedelta(milliseconds=2500)) is True
    assert tracker.would_have_hit_original_tp is True

    assert tracker.add_sample(106.0, timestamp=base + timedelta(milliseconds=5000)) is True
    assert tracker.would_have_hit_original_sl is True


def test_add_sample_stops_after_duration():
    tracker, base = _make_tracker(tracking_duration_sec=1, sample_interval_ms=0)

    assert tracker.add_sample(100.0, timestamp=base + timedelta(seconds=2)) is True
    assert tracker.is_active is False

    assert tracker.add_sample(101.0, timestamp=base + timedelta(seconds=3)) is False


def test_compute_final_metrics_empty_returns_empty_dict():
    tracker, _base = _make_tracker()
    tracker.samples.clear()

    assert tracker.compute_final_metrics() == {}


def test_compute_final_metrics_winning_trade_targets_and_regret():
    tracker, base = _make_tracker(
        realized_pnl_pct=1.0,
        realized_pnl_usdt=100.0,
        sample_interval_ms=0,
        entry_price=99.0,
    )

    prices = [100.02, 100.05, 100.08, 100.12, 100.20]
    for i, price in enumerate(prices):
        assert tracker.add_sample(price, timestamp=base + timedelta(seconds=5 + i)) is True

    metrics = tracker.compute_final_metrics()

    assert metrics["sample_count"] == 5
    assert metrics["post_exit_mfe_pct"] == pytest.approx(0.2)
    assert metrics["exit_efficiency_pct"] == pytest.approx(83.33, rel=1e-2)
    assert metrics["exit_timing_grade"] == "A"
    assert metrics["regret_usdt"] == pytest.approx(20.0)

    assert metrics["ml_optimal_trailing_trigger"] == pytest.approx(0.7)
    assert metrics["ml_optimal_be_trigger"] == pytest.approx(0.26)
    assert metrics["ml_optimal_trailing_distance"] == pytest.approx(0.03)


def test_compute_final_metrics_losing_trade_efficiency_can_be_100():
    tracker, base = _make_tracker(realized_pnl_pct=-0.2, realized_pnl_usdt=-20.0, sample_interval_ms=0)

    assert tracker.add_sample(97.0, timestamp=base) is True

    metrics = tracker.compute_final_metrics()

    assert metrics["exit_efficiency_pct"] == pytest.approx(100.0)
    assert metrics["exit_timing_grade"] == "A+"
