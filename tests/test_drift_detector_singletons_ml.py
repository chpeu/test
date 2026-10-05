import pytest

from core.ml.drift_detector import get_drift_detector, reset_drift_detector


def test_get_drift_detector_reads_config_and_is_singleton(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    reset_drift_detector()

    values = {
        'drift_pnl_delta': 0.01,
        'drift_winrate_delta': 0.02,
        'drift_min_window': 5,
        'drift_alert_cooldown': 7,
        'drift_detection_enabled': False,
    }

    def fake_get_config_value(key, default=None):
        return values.get(key, default)

    monkeypatch.setattr('utils.config_persistence.get_config_value', fake_get_config_value)

    d1 = get_drift_detector()
    assert d1 is not None
    assert d1.enabled is False
    assert d1.alert_cooldown == 7
    assert d1.pnl_detector.delta == pytest.approx(0.01)
    assert d1.winrate_detector.delta == pytest.approx(0.02)
    assert d1.pnl_detector.min_window == 5
    assert d1.winrate_detector.min_window == 5

    # singleton
    d2 = get_drift_detector()
    assert d2 is d1

    reset_drift_detector()


def test_get_drift_detector_fallback_on_config_exception(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    reset_drift_detector()

    def boom(*_args, **_kwargs):
        raise RuntimeError('config failed')

    monkeypatch.setattr('utils.config_persistence.get_config_value', boom)

    d = get_drift_detector()
    assert d is not None
    assert d.enabled is True

    reset_drift_detector()
