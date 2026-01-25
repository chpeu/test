import numpy as np
import pytest

from core.ml.threshold_optimizer import (
    ContextStats,
    ContextualThresholdOptimizer,
    get_threshold_optimizer,
    reset_threshold_optimizer,
)


def test_get_threshold_disabled_returns_default(tmp_path):
    optimizer = ContextualThresholdOptimizer(persistence_path=str(tmp_path / "state.json"))
    optimizer.enabled = False

    threshold = optimizer.get_threshold("CALME", "EUROPE", 10)
    assert threshold == pytest.approx(optimizer.default_threshold)


def test_get_threshold_low_trades_sampling_is_clamped(monkeypatch, tmp_path):
    optimizer = ContextualThresholdOptimizer(
        min_threshold=0.45,
        max_threshold=0.70,
        default_threshold=0.65,
        exploration_bonus=0.20,
        persistence_path=str(tmp_path / "state.json"),
    )

    monkeypatch.setattr(np.random, "uniform", lambda *_args, **_kwargs: 0.20)

    threshold = optimizer.get_threshold("CALME", "EUROPE", 1, use_sampling=True)
    assert threshold == pytest.approx(0.70)


def test_get_threshold_low_trades_no_sampling_uses_default(monkeypatch, tmp_path):
    optimizer = ContextualThresholdOptimizer(
        min_threshold=0.45,
        max_threshold=0.70,
        default_threshold=0.55,
        exploration_bonus=0.20,
        persistence_path=str(tmp_path / "state.json"),
    )

    def _boom(*_args, **_kwargs):
        raise AssertionError("np.random.uniform should not be called when use_sampling=False")

    monkeypatch.setattr(np.random, "uniform", _boom)

    threshold = optimizer.get_threshold("CALME", "EUROPE", 1, use_sampling=False)
    assert threshold == pytest.approx(optimizer.default_threshold)


def test_get_threshold_high_trades_sampling_beta_mapping(monkeypatch, tmp_path):
    optimizer = ContextualThresholdOptimizer(
        min_threshold=0.45,
        max_threshold=0.70,
        default_threshold=0.55,
        persistence_path=str(tmp_path / "state.json"),
    )

    context_key = optimizer._get_context_key("VOLATILE", "EUROPE", 14)
    stats = optimizer._context_stats[context_key]
    stats.total_trades = 10
    stats.alpha = 5.0
    stats.beta = 2.0

    monkeypatch.setattr(np.random, "beta", lambda *_args, **_kwargs: 1.0)

    threshold = optimizer.get_threshold("VOLATILE", "EUROPE", 14, use_sampling=True)
    assert threshold == pytest.approx(optimizer.min_threshold)


def test_get_threshold_high_trades_mean_no_sampling(tmp_path):
    optimizer = ContextualThresholdOptimizer(
        min_threshold=0.45,
        max_threshold=0.70,
        default_threshold=0.55,
        persistence_path=str(tmp_path / "state.json"),
    )

    context_key = optimizer._get_context_key("CALME", "EUROPE_OPEN", 10)
    stats = optimizer._context_stats[context_key]
    stats.total_trades = 10
    stats.alpha = 3.0
    stats.beta = 1.0

    sample = stats.alpha / (stats.alpha + stats.beta)
    expected = optimizer.max_threshold - sample * (optimizer.max_threshold - optimizer.min_threshold)

    threshold = optimizer.get_threshold("CALME", "EUROPE_OPEN", 10, use_sampling=False)
    assert threshold == pytest.approx(expected)


def test_should_explore_disabled(tmp_path):
    optimizer = ContextualThresholdOptimizer(exploration_rate=0.0, persistence_path=str(tmp_path / "state.json"))

    should_explore, reason = optimizer.should_explore(
        regime="CALME",
        session="EUROPE",
        hour=10,
        ml_confidence=0.40,
        threshold=0.55,
    )

    assert should_explore is False
    assert reason == "exploration_disabled"


def test_should_explore_above_threshold(tmp_path):
    optimizer = ContextualThresholdOptimizer(exploration_rate=0.5, persistence_path=str(tmp_path / "state.json"))

    should_explore, reason = optimizer.should_explore(
        regime="CALME",
        session="EUROPE",
        hour=10,
        ml_confidence=0.60,
        threshold=0.55,
    )

    assert should_explore is False
    assert reason == "above_threshold"


def test_should_explore_selected(monkeypatch, tmp_path):
    optimizer = ContextualThresholdOptimizer(exploration_rate=0.5, persistence_path=str(tmp_path / "state.json"))

    monkeypatch.setattr(np.random, "random", lambda: 0.10)

    should_explore, reason = optimizer.should_explore(
        regime="CALME",
        session="EUROPE",
        hour=10,
        ml_confidence=0.40,
        threshold=0.55,
    )

    assert should_explore is True
    assert reason == "exploration_selected"


def test_should_explore_not_selected(monkeypatch, tmp_path):
    optimizer = ContextualThresholdOptimizer(exploration_rate=0.1, persistence_path=str(tmp_path / "state.json"))

    monkeypatch.setattr(np.random, "random", lambda: 0.50)

    should_explore, reason = optimizer.should_explore(
        regime="CALME",
        session="EUROPE",
        hour=10,
        ml_confidence=0.40,
        threshold=0.55,
    )

    assert should_explore is False
    assert reason == "exploration_not_selected"


def test_update_updates_stats_and_calls_save(monkeypatch, tmp_path):
    optimizer = ContextualThresholdOptimizer(persistence_path=str(tmp_path / "state.json"))

    monkeypatch.setattr(optimizer, "_save_state", lambda: None)

    optimizer.update(
        regime="CALME",
        session="EUROPE",
        hour=10,
        win=True,
        pnl=0.12,
        is_exploration=True,
    )

    context_key = optimizer._get_context_key("CALME", "EUROPE", 10)
    stats = optimizer._context_stats[context_key]

    assert stats.total_trades == 1
    assert stats.total_wins == 1
    assert stats.alpha == pytest.approx(2.0)
    assert stats.beta == pytest.approx(1.0)
    assert stats.exploration_trades == 1
    assert stats.exploration_wins == 1
    assert stats.total_pnl == pytest.approx(0.12)
    assert stats.last_update is not None

    assert optimizer.total_updates == 1


def test_persistence_roundtrip(tmp_path):
    state_path = tmp_path / "state.json"

    optimizer = ContextualThresholdOptimizer(persistence_path=str(state_path))
    optimizer.update("CALME", "EUROPE", 10, win=True, pnl=0.1)

    assert state_path.exists()

    optimizer_2 = ContextualThresholdOptimizer(persistence_path=str(state_path))

    assert optimizer_2.total_updates == 1
    context_key = optimizer_2._get_context_key("CALME", "EUROPE", 10)
    assert optimizer_2._context_stats[context_key].total_trades == 1


def test_get_all_thresholds_parses_session_with_underscore(tmp_path):
    optimizer = ContextualThresholdOptimizer(
        min_threshold=0.45,
        max_threshold=0.70,
        default_threshold=0.55,
        persistence_path=str(tmp_path / "state.json"),
    )

    optimizer._context_stats["VOLATILE_EUROPE_OPEN_2"] = ContextStats(
        alpha=3.0,
        beta=1.0,
        total_trades=5,
        total_wins=4,
        total_pnl=1.0,
    )
    optimizer._context_stats["VOLATILE_EUROPE_X"] = ContextStats(total_trades=10, total_wins=5)

    thresholds = optimizer.get_all_thresholds()

    assert "VOLATILE_EUROPE_OPEN_2" in thresholds
    assert thresholds["VOLATILE_EUROPE_OPEN_2"]["session"] == "EUROPE_OPEN"
    assert thresholds["VOLATILE_EUROPE_OPEN_2"]["hour_group"] == 2
    assert "VOLATILE_EUROPE_X" not in thresholds


def test_get_recommendations_increase_and_decrease(tmp_path):
    optimizer = ContextualThresholdOptimizer(
        min_threshold=0.45,
        max_threshold=0.70,
        default_threshold=0.55,
        persistence_path=str(tmp_path / "state.json"),
    )

    optimizer._context_stats["NORMAL_EUROPE_1"] = ContextStats(
        alpha=4.0,
        beta=8.0,
        total_trades=10,
        total_wins=3,
        total_pnl=-0.5,
    )
    optimizer._context_stats["NORMAL_US_2"] = ContextStats(
        alpha=14.0,
        beta=8.0,
        total_trades=20,
        total_wins=13,
        total_pnl=1.2,
    )

    recs = optimizer.get_recommendations(min_trades=10)

    assert len(recs) == 2
    assert recs[0]["context"] == "NORMAL_US_2"
    assert recs[0]["action"] == "decrease_threshold"
    assert recs[1]["context"] == "NORMAL_EUROPE_1"
    assert recs[1]["action"] == "increase_threshold"


def test_reset_all_clears_contexts_and_saves(monkeypatch, tmp_path):
    optimizer = ContextualThresholdOptimizer(persistence_path=str(tmp_path / "state.json"))
    optimizer._context_stats["NORMAL_EUROPE_0"] = ContextStats(total_trades=1, total_wins=1)
    optimizer.total_updates = 5

    called = {"count": 0}

    def _save():
        called["count"] += 1

    monkeypatch.setattr(optimizer, "_save_state", _save)

    optimizer.reset_all()

    assert len(optimizer._context_stats) == 0
    assert optimizer.total_updates == 0
    assert called["count"] == 1


def test_get_threshold_optimizer_singleton_reads_config(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    reset_threshold_optimizer()

    values = {
        "threshold_min": 0.40,
        "threshold_max": 0.60,
        "gb_min_confidence": 0.52,
        "threshold_exploration_bonus": 0.01,
        "threshold_exploration_rate": 0.50,
        "threshold_optimizer_enabled": True,
    }

    def fake_get_config_value(key, default=None):
        return values.get(key, default)

    monkeypatch.setattr("utils.config_persistence.get_config_value", fake_get_config_value)

    opt_1 = get_threshold_optimizer()
    assert opt_1.enabled is True
    assert opt_1.min_threshold == pytest.approx(0.40)
    assert opt_1.max_threshold == pytest.approx(0.60)
    assert opt_1.default_threshold == pytest.approx(0.52)
    assert opt_1.exploration_bonus == pytest.approx(0.01)
    assert opt_1.exploration_rate == pytest.approx(0.50)

    values["threshold_min"] = 0.42
    opt_2 = get_threshold_optimizer()

    assert opt_2 is opt_1
    assert opt_2.min_threshold == pytest.approx(0.42)

    reset_threshold_optimizer()


def test_get_threshold_optimizer_swaps_min_max_when_inverted(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    reset_threshold_optimizer()

    values = {
        "threshold_min": 0.70,
        "threshold_max": 0.40,
        "gb_min_confidence": 0.52,
        "threshold_exploration_bonus": 0.01,
        "threshold_exploration_rate": 0.02,
        "threshold_optimizer_enabled": True,
    }

    def fake_get_config_value(key, default=None):
        return values.get(key, default)

    monkeypatch.setattr("utils.config_persistence.get_config_value", fake_get_config_value)

    opt = get_threshold_optimizer()
    assert opt.min_threshold == pytest.approx(0.40)
    assert opt.max_threshold == pytest.approx(0.70)

    reset_threshold_optimizer()


def test_reset_context_removes_specific_context(tmp_path):
    optimizer = ContextualThresholdOptimizer(persistence_path=str(tmp_path / "state.json"))
    optimizer._context_stats["CALME_EUROPE_2"] = ContextStats(total_trades=5, total_wins=3)
    optimizer._context_stats["CALME_US_2"] = ContextStats(total_trades=5, total_wins=3)

    optimizer.reset_context("CALME", "EUROPE", 8)

    assert "CALME_EUROPE_2" not in optimizer._context_stats
    assert "CALME_US_2" in optimizer._context_stats


def test_get_status_includes_exploration_stats(tmp_path):
    optimizer = ContextualThresholdOptimizer(persistence_path=str(tmp_path / "state.json"))

    # Create a context with exploration trades
    key = optimizer._get_context_key("CALME", "EUROPE", 10)
    stats = optimizer._context_stats[key]
    stats.total_trades = 10
    stats.total_wins = 6
    stats.exploration_trades = 4
    stats.exploration_wins = 3

    status = optimizer.get_status()
    assert status["total_contexts"] >= 1
    assert status["contexts_with_data"] >= 1
    assert status["exploration_trades"] == 4
    assert status["exploration_wins"] == 3
    assert status["exploration_winrate"] == pytest.approx(3 / 4)
