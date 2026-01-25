import json
import os
import tempfile

import pytest

from core.ml.drift_detector import ADWINDetector, MarketDriftDetector


def test_adwin_detector_detects_large_shift():
    detector = ADWINDetector(delta=0.9, min_window=2)

    # Phase stable
    assert bool(detector.update(0.0)) is False
    assert bool(detector.update(0.0)) is False
    assert bool(detector.update(0.0)) is False
    assert bool(detector.update(0.0)) is False

    # Phase shift brutal
    drift = bool(detector.update(10.0))
    # selon la taille de fenêtre, drift peut arriver immédiatement ou après 1-2 points
    if not drift:
        drift = bool(detector.update(10.0))

    assert drift is True


def test_market_drift_detector_disabled_returns_fast():
    detector = MarketDriftDetector(min_window=2, alert_cooldown=1)
    detector.enabled = False

    result = detector.update(pnl=0.1, win=True)
    assert result == {'drift_detected': False, 'enabled': False}


def test_market_drift_detector_cooldown_blocks_drift_flags():
    # cooldown élevé pour forcer blocage
    detector = MarketDriftDetector(pnl_delta=0.9, winrate_delta=0.9, min_window=2, alert_cooldown=999)

    # Alimenter assez de données pour que les ADWIN internes puissent détecter
    for _ in range(10):
        out = detector.update(pnl=0.0, win=True)
        assert bool(out['drift_detected']) is False

    # Changement brutal
    out = detector.update(pnl=10.0, win=False)

    # Drift doit rester false à cause du cooldown
    assert bool(out['drift_detected']) is False
    assert bool(out['pnl_drift']) is False
    assert bool(out['winrate_drift']) is False


def test_market_drift_detector_persistence_save_and_load_state():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'drift_state.json')

        detector = MarketDriftDetector(
            pnl_delta=0.9,
            winrate_delta=0.9,
            min_window=2,
            alert_cooldown=1,
            persistence_path=path,
        )

        # Forcer un save via le cycle périodique (%10)
        for i in range(10):
            detector.update(pnl=float(i) / 100.0, win=(i % 2 == 0))

        assert os.path.exists(path)

        # Recréer un nouveau detector et vérifier qu'il charge
        detector2 = MarketDriftDetector(
            pnl_delta=0.9,
            winrate_delta=0.9,
            min_window=2,
            alert_cooldown=1,
            persistence_path=path,
        )

        assert detector2.total_trades == detector.total_trades
        assert detector2.trades_since_alert == detector.trades_since_alert
        assert detector2.pnl_detector.width == detector.pnl_detector.width
        assert detector2.winrate_detector.width == detector.winrate_detector.width


def test_market_drift_detector_load_state_handles_none_values_in_windows():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'drift_state.json')

        state = {
            'total_trades': 7,
            'trades_since_alert': 3,
            'pnl_window': [0.01, None, 0.02],
            'winrate_window': [1.0, 0.0, None, 1.0],
            'drift_history': [],
            'saved_at': '2026-01-25T00:00:00'
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(state, f)

        detector = MarketDriftDetector(
            pnl_delta=0.9,
            winrate_delta=0.9,
            min_window=2,
            alert_cooldown=1,
            persistence_path=path,
        )

        assert detector.total_trades == 7
        assert detector.trades_since_alert == 3
        # None doivent être filtrés
        assert list(detector.pnl_detector.window) == [0.01, 0.02]
        assert list(detector.winrate_detector.window) == [1.0, 0.0, 1.0]


def test_market_drift_detector_reset_clears_windows_and_counters():
    detector = MarketDriftDetector(pnl_delta=0.9, winrate_delta=0.9, min_window=2, alert_cooldown=1)

    detector.update(pnl=0.01, win=True)
    detector.update(pnl=0.02, win=False)

    assert detector.pnl_detector.width > 0
    assert detector.winrate_detector.width > 0

    detector.reset()

    assert detector.pnl_detector.width == 0
    assert detector.winrate_detector.width == 0
    assert detector.trades_since_alert == 0
