import datetime as _dt

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.trading_circuit_breaker import (
    CircuitBreakerState,
    TradingCircuitBreaker,
    get_trading_circuit_breaker,
    init_trading_circuit_breaker,
)


@pytest.fixture()
def cb(monkeypatch: pytest.MonkeyPatch) -> TradingCircuitBreaker:
    monkeypatch.setattr(TradingCircuitBreaker, "_log_event_to_db", lambda self, event: None)
    return TradingCircuitBreaker(
        max_consecutive_losses=2,
        daily_drawdown_pause_pct=-2.0,
        daily_drawdown_stop_pct=-5.0,
        pause_duration_minutes=0,
        score_boost_per_loss=0.5,
        max_score_boost=2.0,
    )


def test_initial_state(cb: TradingCircuitBreaker):
    assert cb.state == CircuitBreakerState.ACTIVE
    assert cb.can_trade() is True
    assert cb.get_score_boost() == 0.0
    status = cb.get_status()
    assert status["state"] == "ACTIVE"
    assert status["can_trade"] is True
    assert status["consecutive_losses"] == 0


def test_pause_after_consecutive_losses_and_auto_resume(cb: TradingCircuitBreaker):
    assert cb.record_trade("TEST/USDT", pnl_pct=-0.5, pnl_usdt=-5.0) is True
    assert cb.state == CircuitBreakerState.ACTIVE
    assert cb.consecutive_losses == 1
    assert cb.get_score_boost() == 0.5

    assert cb.record_trade("TEST/USDT", pnl_pct=-0.5, pnl_usdt=-5.0) is False
    assert cb.state == CircuitBreakerState.PAUSED
    assert cb.consecutive_losses == 2
    assert cb.get_score_boost() == 1.0
    assert cb.paused_until is not None
    assert cb.pause_reason is not None

    assert cb.can_trade() is True
    assert cb.state == CircuitBreakerState.ACTIVE
    assert cb.paused_until is None
    assert cb.pause_reason is None
    assert cb.get_score_boost() == 1.0


def test_pause_on_daily_drawdown(cb: TradingCircuitBreaker):
    cb.max_consecutive_losses = 999
    assert cb.record_trade("TEST/USDT", pnl_pct=-2.5, pnl_usdt=-25.0) is False
    assert cb.state == CircuitBreakerState.PAUSED
    assert cb.pause_reason is not None
    assert "drawdown" in cb.pause_reason.lower()
    assert cb.can_trade() is True
    assert cb.state == CircuitBreakerState.ACTIVE


def test_stop_on_critical_daily_drawdown(cb: TradingCircuitBreaker):
    cb.max_consecutive_losses = 999
    assert cb.record_trade("TEST/USDT", pnl_pct=-6.0, pnl_usdt=-60.0) is False
    assert cb.state == CircuitBreakerState.STOPPED
    assert cb.can_trade() is False


def test_reset_clears_pause_and_losses(cb: TradingCircuitBreaker):
    cb.record_trade("TEST/USDT", pnl_pct=-0.5, pnl_usdt=-5.0)
    cb.record_trade("TEST/USDT", pnl_pct=-0.5, pnl_usdt=-5.0)
    assert cb.state == CircuitBreakerState.PAUSED
    assert cb.consecutive_losses == 2

    cb.reset(manual=True)
    assert cb.state == CircuitBreakerState.ACTIVE
    assert cb.consecutive_losses == 0
    assert cb.paused_until is None
    assert cb.pause_reason is None
    assert cb.can_trade() is True


def test_get_score_boost_is_capped(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(TradingCircuitBreaker, "_log_event_to_db", lambda self, event: None)
    cb2 = TradingCircuitBreaker(
        max_consecutive_losses=999,
        daily_drawdown_pause_pct=-999.0,
        daily_drawdown_stop_pct=-9999.0,
        pause_duration_minutes=0,
        score_boost_per_loss=0.5,
        max_score_boost=1.0,
    )
    cb2.record_trade("TEST/USDT", pnl_pct=-0.1, pnl_usdt=-1.0)
    cb2.record_trade("TEST/USDT", pnl_pct=-0.1, pnl_usdt=-1.0)
    cb2.record_trade("TEST/USDT", pnl_pct=-0.1, pnl_usdt=-1.0)
    assert cb2.consecutive_losses == 3
    assert cb2.get_score_boost() == 1.0


def test_update_config_updates_fields(cb: TradingCircuitBreaker):
    cb.update_config(
        max_consecutive_losses=7,
        daily_drawdown_pause_pct=-3.0,
        daily_drawdown_stop_pct=-8.0,
        pause_duration_minutes=42,
        score_boost_per_loss=0.25,
    )
    assert cb.max_consecutive_losses == 7
    assert cb.daily_drawdown_pause_pct == -3.0
    assert cb.daily_drawdown_stop_pct == -8.0
    assert cb.pause_duration.total_seconds() == 42 * 60
    assert cb.score_boost_per_loss == 0.25


def test_day_reset_resets_daily_stats_and_resumes_drawdown_pause(cb: TradingCircuitBreaker):
    cb.daily_pnl_pct = -2.5
    cb.daily_pnl_usdt = -25.0
    cb.daily_trades = 10
    cb.daily_wins = 1
    cb.daily_losses = 9
    cb.trade_history = []
    cb.state = CircuitBreakerState.PAUSED
    cb.pause_reason = "Drawdown journalier: -2.50%"
    cb.paused_until = _dt.datetime.now() + _dt.timedelta(minutes=10)
    cb.day_start = (_dt.datetime.utcnow() - _dt.timedelta(days=1)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    assert cb.can_trade() is True
    assert cb.state == CircuitBreakerState.ACTIVE
    assert cb.daily_pnl_pct == 0.0
    assert cb.daily_pnl_usdt == 0.0
    assert cb.daily_trades == 0
    assert cb.daily_wins == 0
    assert cb.daily_losses == 0


def test_global_instance_initializer(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(TradingCircuitBreaker, "_log_event_to_db", lambda self, event: None)
    cb_global = init_trading_circuit_breaker(max_consecutive_losses=3, pause_duration_minutes=0)
    assert cb_global.max_consecutive_losses == 3
    cb_back = get_trading_circuit_breaker()
    assert cb_back is cb_global
