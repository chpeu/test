from datetime import datetime, timedelta, timezone

import pytest

from core.position.adaptive_sizing import (
    AdaptiveSizingConfig,
    AdaptiveSizingManager,
    PairSessionStats,
    get_adaptive_sizing_manager,
    load_adaptive_sizing_config,
    reset_adaptive_sizing_manager,
)


def test_pair_session_stats_properties_when_empty():
    stats = PairSessionStats(symbol="BTC/USDT")
    stats.wins = 0
    stats.losses = 0
    stats.total_pnl_pct = 0.0

    assert stats.total_trades == 0
    assert stats.winrate == 0.0
    assert stats.avg_pnl == 0.0


def test_load_adaptive_sizing_config_reads_trading_config(monkeypatch):
    monkeypatch.setitem(
        __import__("config").TRADING_CONFIG,
        "adaptive_sizing_enabled",
        False,
    )
    monkeypatch.setitem(__import__("config").TRADING_CONFIG, "adaptive_sizing_min_trades", 5)

    cfg = load_adaptive_sizing_config()
    assert cfg.enabled is False
    assert cfg.min_trades_for_adjustment == 5


def test_get_size_multiplier_returns_one_when_disabled():
    manager = AdaptiveSizingManager(config=AdaptiveSizingConfig(enabled=False))
    assert manager.get_size_multiplier("BTC/USDT") == 1.0


def test_get_size_multiplier_returns_normal_when_not_enough_trades():
    config = AdaptiveSizingConfig(enabled=True, min_trades_for_adjustment=3)
    manager = AdaptiveSizingManager(config=config)

    manager.record_trade("BTC/USDT", pnl_pct=0.1, is_win=True)
    manager.record_trade("BTC/USDT", pnl_pct=-0.1, is_win=False)

    assert manager.get_size_multiplier("BTC/USDT") == pytest.approx(1.0)


def test_get_size_multiplier_levels_and_gradual_adjustment_and_clamping():
    config = AdaptiveSizingConfig(
        enabled=True,
        min_trades_for_adjustment=3,
        excellent_wr_threshold=0.75,
        good_wr_threshold=0.60,
        poor_wr_threshold=0.40,
        very_poor_wr_threshold=0.30,
        excellent_multiplier=1.5,
        good_multiplier=1.25,
        normal_multiplier=1.0,
        poor_multiplier=0.70,
        very_poor_multiplier=0.50,
        max_multiplier=1.5,
        min_multiplier=0.5,
        gradual_increase=True,
        increase_step=0.10,
        decrease_step=0.15,
        reset_after_big_loss=False,
    )
    manager = AdaptiveSizingManager(config=config)

    manager.record_trade("BTC/USDT", pnl_pct=0.1, is_win=True)
    manager.record_trade("BTC/USDT", pnl_pct=0.1, is_win=True)
    manager.record_trade("BTC/USDT", pnl_pct=0.1, is_win=True)

    multiplier = manager.get_size_multiplier("BTC/USDT")
    assert multiplier == pytest.approx(1.5)

    manager.reset_pair("BTC/USDT")

    manager.record_trade("BTC/USDT", pnl_pct=-0.1, is_win=False)
    manager.record_trade("BTC/USDT", pnl_pct=-0.1, is_win=False)
    manager.record_trade("BTC/USDT", pnl_pct=-0.1, is_win=False)

    multiplier = manager.get_size_multiplier("BTC/USDT")
    assert multiplier == pytest.approx(0.5)


def test_get_size_multiplier_normal_level_no_gradual_adjustment():
    config = AdaptiveSizingConfig(
        enabled=True,
        min_trades_for_adjustment=3,
        excellent_wr_threshold=0.75,
        good_wr_threshold=0.60,
        poor_wr_threshold=0.40,
        very_poor_wr_threshold=0.30,
        gradual_increase=True,
        reset_after_big_loss=False,
    )
    manager = AdaptiveSizingManager(config=config)

    manager.record_trade("BTC/USDT", pnl_pct=0.1, is_win=True)
    manager.record_trade("BTC/USDT", pnl_pct=-0.1, is_win=False)
    manager.record_trade("BTC/USDT", pnl_pct=0.1, is_win=True)
    manager.record_trade("BTC/USDT", pnl_pct=-0.1, is_win=False)

    assert manager.get_size_multiplier("BTC/USDT") == pytest.approx(1.0)


def test_record_trade_big_loss_resets_pair():
    config = AdaptiveSizingConfig(reset_after_big_loss=True, big_loss_threshold=-2.0)
    manager = AdaptiveSizingManager(config=config)

    manager.record_trade("BTC/USDT", pnl_pct=-2.5, is_win=False)

    stats = manager.pair_stats["BTC/USDT"]
    assert stats.total_trades == 0
    assert manager._consecutive_results["BTC/USDT"] == []


def test_auto_reset_after_inactivity_triggers_reset():
    config = AdaptiveSizingConfig(auto_reset_hours=1, reset_after_big_loss=False)
    manager = AdaptiveSizingManager(config=config)

    manager.record_trade("BTC/USDT", pnl_pct=0.1, is_win=True)

    manager.pair_stats["BTC/USDT"].session_start = datetime.now(timezone.utc) - timedelta(hours=2)

    mult = manager.get_size_multiplier("BTC/USDT")
    assert mult == pytest.approx(1.0)
    assert manager.pair_stats["BTC/USDT"].total_trades == 0


def test_get_all_stats_returns_current_multiplier():
    config = AdaptiveSizingConfig(min_trades_for_adjustment=10, reset_after_big_loss=False)
    manager = AdaptiveSizingManager(config=config)

    manager.record_trade("BTC/USDT", pnl_pct=0.1, is_win=True)

    stats = manager.get_all_stats()
    assert "BTC/USDT" in stats
    assert stats["BTC/USDT"]["total_trades"] == 1
    assert "current_multiplier" in stats["BTC/USDT"]


def test_reload_config_reads_new_values(monkeypatch):
    manager = AdaptiveSizingManager(config=AdaptiveSizingConfig(enabled=True))

    monkeypatch.setitem(__import__("config").TRADING_CONFIG, "adaptive_sizing_enabled", False)
    monkeypatch.setitem(__import__("config").TRADING_CONFIG, "adaptive_sizing_min_trades", 7)

    manager.reload_config()

    assert manager.config.enabled is False
    assert manager.config.min_trades_for_adjustment == 7


def test_get_config_dict_contains_expected_keys():
    manager = AdaptiveSizingManager(config=AdaptiveSizingConfig())
    cfg = manager.get_config_dict()

    assert "enabled" in cfg
    assert "thresholds" in cfg
    assert "multipliers" in cfg
    assert "limits" in cfg
    assert "reset" in cfg


def test_adaptive_sizing_singleton_and_reset():
    reset_adaptive_sizing_manager()
    m1 = get_adaptive_sizing_manager()
    m2 = get_adaptive_sizing_manager()
    assert m1 is m2

    reset_adaptive_sizing_manager()
    m3 = get_adaptive_sizing_manager()
    assert m3 is not m1
