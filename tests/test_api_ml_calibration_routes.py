import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    from api.routes import ml_calibration

    app = FastAPI()
    app.include_router(ml_calibration.router, prefix="/api/ml/calibration")
    return app


def test_get_calibration_stats_success(monkeypatch, app):
    from api.routes import ml_calibration

    # Fake TRADING_CONFIG
    cfg_mod = types.SimpleNamespace(TRADING_CONFIG={
        'ml_calibration_enabled': True,
        'ml_calib_min_trades': 30,
        'ml_calib_min_winrate': 40.0,
    })
    monkeypatch.setitem(__import__('sys').modules, 'config', cfg_mod)

    class _Stats:
        def __init__(self, trades):
            self.weighted_wins = 1.0
            self.weighted_total = 2.0
            self.total_trades = trades
            self.actual_winrate = 55.0
            self.avg_pnl_pct = 0.1
            self.total_pnl_usdt = 10.0

    fake_mgr = types.SimpleNamespace(
        get_all_stats=lambda: {
            'LONG': {'50+': _Stats(10)},
            'SHORT': {},
        }
    )

    monkeypatch.setattr(ml_calibration, 'logger', types.SimpleNamespace(error=lambda *_a, **_k: None))
    monkeypatch.setattr('ml.calibration.get_calibration_manager', lambda: fake_mgr)

    client = TestClient(app)
    resp = client.get('/api/ml/calibration/stats')
    assert resp.status_code == 200
    data = resp.json()
    assert data['enabled'] is True
    assert data['min_trades'] == 30
    assert data['learning_phase'] is True
    assert data['total_trades'] == 10
    assert 'LONG' in data['stats']


def test_get_calibration_stats_exception(monkeypatch, app):
    from api.routes import ml_calibration

    cfg_mod = types.SimpleNamespace(TRADING_CONFIG={})
    monkeypatch.setitem(__import__('sys').modules, 'config', cfg_mod)

    monkeypatch.setattr('ml.calibration.get_calibration_manager', lambda: (_ for _ in ()).throw(RuntimeError('boom')))

    client = TestClient(app)
    resp = client.get('/api/ml/calibration/stats')
    assert resp.status_code == 500


def test_reset_calibration_success(monkeypatch, app):
    fake_mgr = types.SimpleNamespace(reset_calibration=lambda reason: True)
    monkeypatch.setattr('ml.calibration.get_calibration_manager', lambda: fake_mgr)

    client = TestClient(app)
    resp = client.post('/api/ml/calibration/reset?reason=test')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'success'


def test_reset_calibration_failure(monkeypatch, app):
    fake_mgr = types.SimpleNamespace(reset_calibration=lambda reason: False)
    monkeypatch.setattr('ml.calibration.get_calibration_manager', lambda: fake_mgr)

    client = TestClient(app)
    resp = client.post('/api/ml/calibration/reset?reason=test')
    assert resp.status_code == 500


def test_seed_calibration_success(monkeypatch, app):
    calls = {'reset': 0, 'seed': 0}

    def reset_calibration(reason):
        calls['reset'] += 1
        return True

    def seed_from_historical_trades(days):
        calls['seed'] += 1
        return 42

    fake_mgr = types.SimpleNamespace(
        reset_calibration=reset_calibration,
        seed_from_historical_trades=seed_from_historical_trades,
    )
    monkeypatch.setattr('ml.calibration.get_calibration_manager', lambda: fake_mgr)

    client = TestClient(app)
    resp = client.post('/api/ml/calibration/seed', json={'days': 7})
    assert resp.status_code == 200
    assert resp.json()['trades_processed'] == 42
    assert calls['reset'] == 1
    assert calls['seed'] == 1


def test_seed_calibration_exception(monkeypatch, app):
    fake_mgr = types.SimpleNamespace(
        reset_calibration=lambda reason: True,
        seed_from_historical_trades=lambda days: (_ for _ in ()).throw(RuntimeError('boom')),
    )
    monkeypatch.setattr('ml.calibration.get_calibration_manager', lambda: fake_mgr)

    client = TestClient(app)
    resp = client.post('/api/ml/calibration/seed', json={'days': 7})
    assert resp.status_code == 500


def test_update_calibration_config_no_updates(monkeypatch, app):
    from api.routes import ml_calibration

    cfg_mod = types.SimpleNamespace(TRADING_CONFIG={})
    monkeypatch.setitem(__import__('sys').modules, 'config', cfg_mod)

    saved = {'called': 0}

    def save_config_overrides(updates):
        saved['called'] += 1

    monkeypatch.setattr('utils.config_persistence.save_config_overrides', save_config_overrides)

    client = TestClient(app)
    resp = client.post('/api/ml/calibration/config', json={})
    assert resp.status_code == 200
    assert resp.json()['updated'] == {}
    assert saved['called'] == 0


def test_update_calibration_config_with_updates(monkeypatch, app):
    cfg = {
        'ml_calibration_enabled': True,
        'ml_calib_live_weight': 1.0,
        'ml_calib_dryrun_weight': 0.5,
        'ml_calib_decay_days': 14,
        'ml_calib_min_trades': 30,
        'ml_calib_min_winrate': 40.0,
    }
    cfg_mod = types.SimpleNamespace(TRADING_CONFIG=cfg)
    monkeypatch.setitem(__import__('sys').modules, 'config', cfg_mod)

    saved = {}

    def save_config_overrides(updates):
        saved.update(updates)

    monkeypatch.setattr('utils.config_persistence.save_config_overrides', save_config_overrides)

    client = TestClient(app)
    resp = client.post(
        '/api/ml/calibration/config',
        json={
            'ml_calibration_enabled': False,
            'ml_calib_live_weight': 2.0,
            'ml_calib_min_trades': 50,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data['updated']['ml_calibration_enabled'] is False
    assert data['updated']['ml_calib_live_weight'] == 2.0
    assert data['updated']['ml_calib_min_trades'] == 50
    assert saved['ml_calibration_enabled'] is False


def test_update_calibration_config_updates_all_fields(monkeypatch, app):
    cfg = {}
    cfg_mod = types.SimpleNamespace(TRADING_CONFIG=cfg)
    monkeypatch.setitem(__import__('sys').modules, 'config', cfg_mod)

    saved = {}

    def save_config_overrides(updates):
        saved.update(updates)

    monkeypatch.setattr('utils.config_persistence.save_config_overrides', save_config_overrides)

    client = TestClient(app)
    resp = client.post(
        '/api/ml/calibration/config',
        json={
            'ml_calibration_enabled': True,
            'ml_calib_live_weight': 1.2,
            'ml_calib_dryrun_weight': 0.6,
            'ml_calib_decay_days': 9,
            'ml_calib_min_trades': 33,
            'ml_calib_min_winrate': 44.0,
        },
    )
    assert resp.status_code == 200
    assert cfg['ml_calibration_enabled'] is True
    assert cfg['ml_calib_live_weight'] == pytest.approx(1.2)
    assert cfg['ml_calib_dryrun_weight'] == pytest.approx(0.6)
    assert cfg['ml_calib_decay_days'] == 9
    assert cfg['ml_calib_min_trades'] == 33
    assert cfg['ml_calib_min_winrate'] == pytest.approx(44.0)
    assert saved['ml_calib_min_trades'] == 33


def test_update_calibration_config_exception(monkeypatch, app):
    cfg_mod = types.SimpleNamespace(TRADING_CONFIG={})
    monkeypatch.setitem(__import__('sys').modules, 'config', cfg_mod)

    def boom(_updates):
        raise RuntimeError('boom')

    monkeypatch.setattr('utils.config_persistence.save_config_overrides', boom)

    client = TestClient(app)
    resp = client.post('/api/ml/calibration/config', json={'ml_calibration_enabled': True})
    assert resp.status_code == 500


def test_reset_calibration_exception(monkeypatch, app):
    fake_mgr = types.SimpleNamespace(reset_calibration=lambda reason: (_ for _ in ()).throw(RuntimeError('boom')))
    monkeypatch.setattr('ml.calibration.get_calibration_manager', lambda: fake_mgr)

    client = TestClient(app)
    resp = client.post('/api/ml/calibration/reset?reason=test')
    assert resp.status_code == 500


def test_check_trade_eligibility_uses_bucket(monkeypatch, app):
    fake_mgr = types.SimpleNamespace(
        should_take_trade=lambda direction, ml_confidence: (True, 66.0, 'accepted'),
        get_confidence_bucket=lambda confidence: '45-50',
    )
    monkeypatch.setattr('ml.calibration.get_calibration_manager', lambda: fake_mgr)

    client = TestClient(app)
    resp = client.get('/api/ml/calibration/check/short/49.9')
    assert resp.status_code == 200
    data = resp.json()
    assert data['direction'] == 'SHORT'
    assert data['bucket'] == '45-50'


def test_check_trade_eligibility(monkeypatch, app):
    fake_mgr = types.SimpleNamespace(
        should_take_trade=lambda direction, ml_confidence: (False, 55.0, 'rejected_low_winrate'),
        get_confidence_bucket=lambda confidence: '50+',
    )
    monkeypatch.setattr('ml.calibration.get_calibration_manager', lambda: fake_mgr)

    client = TestClient(app)
    resp = client.get('/api/ml/calibration/check/long/55')
    assert resp.status_code == 200
    data = resp.json()
    assert data['direction'] == 'LONG'
    assert data['bucket'] == '50+'
    assert data['would_take_trade'] is False


def test_check_trade_eligibility_exception(monkeypatch, app):
    monkeypatch.setattr('ml.calibration.get_calibration_manager', lambda: (_ for _ in ()).throw(RuntimeError('boom')))

    client = TestClient(app)
    resp = client.get('/api/ml/calibration/check/long/55')
    assert resp.status_code == 500
