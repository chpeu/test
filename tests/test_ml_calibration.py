import types
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

import ml.calibration as calib


class _FakeCursor:
    def __init__(self, fetchone_side_effect=None, fetchall_return=None, rowcount=0):
        self._fetchone_side_effect = list(fetchone_side_effect or [])
        self._fetchall_return = fetchall_return
        self.rowcount = rowcount
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((query.strip(), params))

    def fetchone(self):
        if self._fetchone_side_effect:
            return self._fetchone_side_effect.pop(0)
        return None

    def fetchall(self):
        return self._fetchall_return or []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self, cursor: _FakeCursor):
        self._cursor = cursor
        self.committed = 0
        self.rolled_back = 0

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1


class _FakePool:
    def __init__(self, conn: _FakeConn):
        self._conn = conn
        self.getconn_calls = 0
        self.putconn_calls = 0

    def getconn(self):
        self.getconn_calls += 1
        return self._conn

    def putconn(self, _conn):
        self.putconn_calls += 1


class _FakePGLogger:
    def __init__(self, pool: _FakePool):
        self.pool = pool


@pytest.fixture
def manager():
    return calib.MLCalibrationManager(db_pool=None)


def test_exit_reason_helpers():
    assert calib.is_valid_exit_for_calibration('TP') is True
    assert calib.is_valid_exit_for_calibration('tp') is True
    assert calib.is_valid_exit_for_calibration('manual') is False
    assert calib.is_valid_exit_for_calibration('') is False
    assert calib.is_valid_exit_for_calibration(None) is False

    assert calib.is_excluded_exit('MANUAL') is True
    assert calib.is_excluded_exit('tp') is False
    assert calib.is_excluded_exit('') is True
    assert calib.is_excluded_exit(None) is True


def test_calibration_stats_ev_bounds_and_variance():
    s = calib.CalibrationStats(
        direction='LONG',
        confidence_bucket='40-45',
        weighted_wins=0.0,
        weighted_total=0.0,
        total_trades=1,
        actual_winrate=None,
        avg_pnl_pct=0.2,
        total_pnl_usdt=10.0,
        sum_pnl_pct=0.2,
        sum_pnl_pct_sq=0.04,
    )
    assert s.var_pnl_pct == 0.0
    assert s.std_pnl_pct == 0.0
    assert s.ev_estimate == pytest.approx(0.2)
    assert s.ev_lower_bound == -999.0

    s.total_trades = 10
    s.sum_pnl_pct = 1.0
    s.sum_pnl_pct_sq = 2.0
    assert s.var_pnl_pct >= 0.0
    assert s.ev_lower_bound > -999.0


def test_normalize_confidence_pct(manager):
    assert manager._normalize_confidence_pct(None) is None
    assert manager._normalize_confidence_pct(0.55) == pytest.approx(55.0)
    assert manager._normalize_confidence_pct(55.0) == pytest.approx(55.0)
    assert manager._normalize_confidence_pct('nope') is None


def test_get_confidence_bucket(manager):
    assert manager.get_confidence_bucket(50.0, bucket_size=5) == '50+'
    assert manager.get_confidence_bucket(49.9, bucket_size=5) == '45-50'
    assert manager.get_confidence_bucket(30.0, bucket_size=5) == '30-35'


def test_get_config_exception_fallback(monkeypatch, manager):
    import sys
    # Simule un module config avec TRADING_CONFIG invalide pour forcer l'exception
    monkeypatch.setitem(sys.modules, 'config', types.SimpleNamespace(TRADING_CONFIG=None))
    cfg = manager._get_config()
    assert cfg['enabled'] is True
    assert cfg['live_weight'] == pytest.approx(1.0)


def test_get_db_pool_paths(monkeypatch):
    # 1) db_pool fourni
    dummy = object()
    m = calib.MLCalibrationManager(db_pool=dummy)
    assert m._get_db_pool() is dummy

    # 2) import ok mais logger disabled => None
    class DummyPG:
        def __init__(self):
            self.enabled = False
            self.pool = None

    monkeypatch.setattr('core.postgresql_datalogger.PostgreSQLDataLogger', DummyPG)
    m2 = calib.MLCalibrationManager(db_pool=None)
    assert m2._get_db_pool() is None

    # 3) import/instanciation échoue => None
    monkeypatch.setattr('core.postgresql_datalogger.PostgreSQLDataLogger', lambda: (_ for _ in ()).throw(RuntimeError('boom')))
    m3 = calib.MLCalibrationManager(db_pool=None)
    assert m3._get_db_pool() is None


def test_calculate_trade_weight_live_vs_dryrun_and_decay(manager, monkeypatch):
    manager._get_config = lambda: {
        'enabled': True,
        'live_weight': 1.0,
        'dryrun_weight': 0.5,
        'decay_days': 10,
        'min_trades': 30,
        'min_winrate': 40.0,
        'bucket_size': 5,
        'auto_reset_on_retrain': True,
    }

    now = datetime.now(timezone.utc)
    w_live_now = manager.calculate_trade_weight(True, False, now)
    w_dry_now = manager.calculate_trade_weight(False, True, now)
    assert w_live_now > w_dry_now

    w_live_old = manager.calculate_trade_weight(True, False, now - timedelta(days=10))
    assert w_live_old < w_live_now


def test_update_calibration_rejects_when_disabled(manager):
    manager._get_config = lambda: {'enabled': False}
    ok = manager.update_calibration(
        direction='LONG',
        ml_confidence=55.0,
        win=True,
        pnl_pct=0.1,
        pnl_usdt=1.0,
        is_live=True,
        is_dry_run=False,
        trade_timestamp=datetime.now(timezone.utc),
        exit_reason='TP'
    )
    assert ok is False


def test_update_calibration_rejects_low_confidence(manager):
    manager._get_config = lambda: {'enabled': True, 'bucket_size': 5}
    ok = manager.update_calibration(
        direction='LONG',
        ml_confidence=0.20,
        win=True,
        pnl_pct=0.1,
        pnl_usdt=1.0,
        is_live=True,
        is_dry_run=False,
        trade_timestamp=datetime.now(timezone.utc),
        exit_reason='TP'
    )
    assert ok is False


def test_update_calibration_excludes_exit_reason(manager):
    manager._get_config = lambda: {'enabled': True, 'bucket_size': 5}
    ok = manager.update_calibration(
        direction='LONG',
        ml_confidence=55.0,
        win=True,
        pnl_pct=0.1,
        pnl_usdt=1.0,
        is_live=True,
        is_dry_run=False,
        trade_timestamp=datetime.now(timezone.utc),
        exit_reason='MANUAL'
    )
    assert ok is False


def test_update_calibration_returns_false_without_db(manager):
    manager._get_config = lambda: {
        'enabled': True,
        'bucket_size': 5,
        'min_trades': 30,
        'live_weight': 1.0,
        'dryrun_weight': 0.5,
        'decay_days': 14,
        'min_winrate': 40.0,
        'auto_reset_on_retrain': True,
    }
    manager._get_db_pool = lambda: None

    ok = manager.update_calibration(
        direction='LONG',
        ml_confidence=55.0,
        win=True,
        pnl_pct=0.1,
        pnl_usdt=1.0,
        is_live=True,
        is_dry_run=False,
        trade_timestamp=datetime.now(timezone.utc),
        exit_reason='TP'
    )
    assert ok is False


def test_update_calibration_success_logs_history_first_trade(manager):
    manager._get_config = lambda: {
        'enabled': True,
        'bucket_size': 5,
        'min_trades': 30,
        'live_weight': 1.0,
        'dryrun_weight': 0.5,
        'decay_days': 14,
        'min_winrate': 40.0,
        'auto_reset_on_retrain': True,
    }

    # row1: before update (no row)
    # row2: after update -> new trades 1
    cur = _FakeCursor(fetchone_side_effect=[None, (55.0, 1, 1.0)])
    conn = _FakeConn(cur)
    pool = _FakePool(conn)
    manager._get_db_pool = lambda: _FakePGLogger(pool)

    called = {'count': 0, 'args': None}

    def fake_log(*args, **kwargs):
        called['count'] += 1
        called['args'] = (args, kwargs)
        return True

    manager._log_to_history = fake_log

    ok = manager.update_calibration(
        direction='LONG',
        ml_confidence=55.0,
        win=True,
        pnl_pct=0.2,
        pnl_usdt=2.0,
        is_live=True,
        is_dry_run=False,
        trade_timestamp=datetime.now(timezone.utc),
        exit_reason='TP'
    )

    assert ok is True
    assert conn.committed >= 1
    assert called['count'] == 1


def test_update_calibration_logs_phase_active_significant_snapshot(manager):
    manager._get_config = lambda: {
        'enabled': True,
        'bucket_size': 5,
        'min_trades': 30,
        'live_weight': 1.0,
        'dryrun_weight': 0.5,
        'decay_days': 14,
        'min_winrate': 40.0,
        'auto_reset_on_retrain': True,
    }

    # Sequence: (old_winrate, old_trades, old_weighted_total) then after update
    # A) phase_active (29 -> 30)
    cur = _FakeCursor(fetchone_side_effect=[(50.0, 29, 29.0), (52.0, 30, 30.0)])
    conn = _FakeConn(cur)
    pool = _FakePool(conn)
    manager._get_db_pool = lambda: _FakePGLogger(pool)

    reasons = []
    manager._log_to_history = lambda *_a, **_k: reasons.append(_a[-1]) or True

    assert manager.update_calibration(
        direction='LONG',
        ml_confidence=55.0,
        win=True,
        pnl_pct=0.2,
        pnl_usdt=2.0,
        is_live=True,
        is_dry_run=False,
        trade_timestamp=datetime.now(timezone.utc),
        exit_reason='TP'
    ) is True

    # B) significant_change (delta >= 5)
    cur2 = _FakeCursor(fetchone_side_effect=[(50.0, 10, 10.0), (60.0, 11, 11.0)])
    conn2 = _FakeConn(cur2)
    pool2 = _FakePool(conn2)
    manager._get_db_pool = lambda: _FakePGLogger(pool2)
    assert manager.update_calibration(
        direction='LONG',
        ml_confidence=55.0,
        win=True,
        pnl_pct=0.2,
        pnl_usdt=2.0,
        is_live=True,
        is_dry_run=False,
        trade_timestamp=datetime.now(timezone.utc),
        exit_reason='TP'
    ) is True

    # C) snapshot (new_trades % 10 == 0)
    cur3 = _FakeCursor(fetchone_side_effect=[(50.0, 19, 19.0), (52.0, 20, 20.0)])
    conn3 = _FakeConn(cur3)
    pool3 = _FakePool(conn3)
    manager._get_db_pool = lambda: _FakePGLogger(pool3)
    assert manager.update_calibration(
        direction='LONG',
        ml_confidence=55.0,
        win=True,
        pnl_pct=0.2,
        pnl_usdt=2.0,
        is_live=True,
        is_dry_run=False,
        trade_timestamp=datetime.now(timezone.utc),
        exit_reason='TP'
    ) is True

    assert any('phase_active' in r for r in reasons)
    assert any('significant_change' in r for r in reasons)
    assert any('snapshot_' in r for r in reasons)


def test_update_calibration_db_exception_returns_false(manager):
    manager._get_config = lambda: {
        'enabled': True,
        'bucket_size': 5,
        'min_trades': 30,
        'live_weight': 1.0,
        'dryrun_weight': 0.5,
        'decay_days': 14,
        'min_winrate': 40.0,
        'auto_reset_on_retrain': True,
    }

    class BoomPool:
        def getconn(self):
            raise RuntimeError('db down')

        def putconn(self, _conn):
            return None

    manager._get_db_pool = lambda: types.SimpleNamespace(pool=BoomPool())
    ok = manager.update_calibration(
        direction='LONG',
        ml_confidence=55.0,
        win=True,
        pnl_pct=0.1,
        pnl_usdt=1.0,
        is_live=True,
        is_dry_run=False,
        trade_timestamp=datetime.now(timezone.utc),
        exit_reason='TP'
    )
    assert ok is False


def test_detect_history_schema_caches(manager):
    cur = _FakeCursor(fetchall_return=[('actual_winrate',)])
    assert manager._detect_history_schema(cur) == 'v2'
    # cached
    cur2 = _FakeCursor(fetchall_return=[])
    assert manager._detect_history_schema(cur2) == 'v2'


def test_detect_history_schema_exception_sets_unknown(manager):
    class BadCursor:
        def execute(self, *_a, **_k):
            raise RuntimeError('boom')

        def fetchall(self):
            return []

    manager._history_schema = None
    assert manager._detect_history_schema(BadCursor()) == 'unknown'


def test_get_calibrated_winrate_learning_phase_when_not_enough_weight(manager):
    manager._get_config = lambda: {'bucket_size': 5, 'min_trades': 30}
    manager._refresh_cache_if_needed = lambda: None

    manager._cache = {
        ('LONG', '50+'): calib.CalibrationStats(
            direction='LONG',
            confidence_bucket='50+',
            weighted_wins=10.0,
            weighted_total=10.0,
            total_trades=10,
            actual_winrate=55.0,
            avg_pnl_pct=0.1,
            total_pnl_usdt=5.0,
        )
    }

    assert manager.get_calibrated_winrate('LONG', 55.0) is None


def test_get_calibrated_winrate_invalid_confidence_or_missing_stats(manager):
    manager._get_config = lambda: {'bucket_size': 5, 'min_trades': 5}
    manager._refresh_cache_if_needed = lambda: None
    manager._cache = {}
    assert manager.get_calibrated_winrate('LONG', None) is None
    assert manager.get_calibrated_winrate('LONG', 55.0) is None


def test_get_calibrated_winrate_returns_when_enough_weight(manager):
    manager._get_config = lambda: {'bucket_size': 5, 'min_trades': 5}
    manager._refresh_cache_if_needed = lambda: None

    manager._cache = {
        ('LONG', '50+'): calib.CalibrationStats(
            direction='LONG',
            confidence_bucket='50+',
            weighted_wins=10.0,
            weighted_total=10.0,
            total_trades=10,
            actual_winrate=55.0,
            avg_pnl_pct=0.1,
            total_pnl_usdt=5.0,
        )
    }

    assert manager.get_calibrated_winrate('LONG', 55.0) == pytest.approx(55.0)


def test_should_take_trade_disabled(manager):
    manager.check_model_change_and_auto_reset = lambda: False
    manager._get_config = lambda: {'enabled': False}
    ok, wr, reason = manager.should_take_trade('LONG', 55.0)
    assert ok is True
    assert wr is None
    assert reason == 'calibration_disabled'


def test_should_take_trade_auto_reset_exception_is_ignored(manager):
    def boom():
        raise RuntimeError('boom')

    manager.check_model_change_and_auto_reset = boom
    manager._get_config = lambda: {'enabled': True, 'bucket_size': 5, 'min_winrate': 40.0}
    manager.get_calibrated_winrate = lambda _d, _c: None

    ok, wr, reason = manager.should_take_trade('LONG', 55.0)
    assert ok is True
    assert reason == 'learning_phase'


def test_should_take_trade_no_ml_confidence(manager):
    manager.check_model_change_and_auto_reset = lambda: False
    manager._get_config = lambda: {'enabled': True, 'bucket_size': 5, 'min_winrate': 40.0}
    ok, wr, reason = manager.should_take_trade('LONG', 10.0)
    assert ok is True
    assert wr is None
    assert reason == 'no_ml_confidence'


def test_should_take_trade_learning_phase(manager):
    manager.check_model_change_and_auto_reset = lambda: False
    manager._get_config = lambda: {'enabled': True, 'bucket_size': 5, 'min_winrate': 40.0}
    manager.get_calibrated_winrate = lambda _d, _c: None

    ok, wr, reason = manager.should_take_trade('LONG', 55.0)
    assert ok is True
    assert wr is None
    assert reason == 'learning_phase'


def test_should_take_trade_reject_low_winrate(manager):
    manager.check_model_change_and_auto_reset = lambda: False
    manager._get_config = lambda: {'enabled': True, 'bucket_size': 5, 'min_winrate': 60.0}
    manager.get_calibrated_winrate = lambda _d, _c: 55.0

    ok, wr, reason = manager.should_take_trade('LONG', 55.0)
    assert ok is False
    assert wr == pytest.approx(55.0)
    assert reason == 'rejected_low_winrate'


def test_should_take_trade_accept(manager):
    manager.check_model_change_and_auto_reset = lambda: False
    manager._get_config = lambda: {'enabled': True, 'bucket_size': 5, 'min_winrate': 50.0}
    manager.get_calibrated_winrate = lambda _d, _c: 55.0

    ok, wr, reason = manager.should_take_trade('LONG', 55.0)
    assert ok is True
    assert wr == pytest.approx(55.0)
    assert reason == 'accepted'


def test_check_model_change_and_auto_reset_first_time(manager):
    manager._get_config = lambda: {'auto_reset_on_retrain': True}
    manager.get_current_model_info = lambda: {'timestamp': 't1'}
    manager.get_last_calibration_model_version = lambda: None

    called = {'ver': None}

    def fake_update(ver):
        called['ver'] = ver
        return True

    manager._update_calibration_model_version = fake_update

    assert manager.check_model_change_and_auto_reset() is False


def test_check_model_change_and_auto_reset_disabled(manager):
    manager._get_config = lambda: {'auto_reset_on_retrain': False}
    assert manager.check_model_change_and_auto_reset() is False


def test_check_model_change_and_auto_reset_unknown_model_timestamp(manager):
    manager._get_config = lambda: {'auto_reset_on_retrain': True}
    manager.get_current_model_info = lambda: {'timestamp': 'unknown'}
    assert manager.check_model_change_and_auto_reset() is False

    manager.get_current_model_info = lambda: {'timestamp': 't2'}
    manager.get_last_calibration_model_version = lambda: 't1'

    manager.reset_calibration = lambda reason: False
    manager.get_last_calibration_model_version = lambda: 't1'

    manager.reset_calibration = lambda reason: True
    called = {'ver': None}
    manager._update_calibration_model_version = lambda ver: called.__setitem__('ver', ver) or True

    assert manager.check_model_change_and_auto_reset() is True
    assert called['ver'] == 't2'


def test_check_model_change_and_auto_reset_no_change(manager):
    manager._get_config = lambda: {'auto_reset_on_retrain': True}
    manager.get_current_model_info = lambda: {'timestamp': 't1'}
    manager.get_last_calibration_model_version = lambda: 't1'

    assert manager.check_model_change_and_auto_reset() is False


def test_get_calibration_manager_singleton():
    calib._calibration_manager = None
    m1 = calib.get_calibration_manager()
    m2 = calib.get_calibration_manager()
    assert m2 is m1


def test_refresh_cache_uses_ttl_and_populates_cache(manager):
    # Cache fresh => early return
    manager._cache_timestamp = datetime.now(timezone.utc)
    manager._cache_ttl_seconds = 999
    manager._get_db_pool = lambda: None
    manager._refresh_cache_if_needed()

    # Expire cache => populate from DB
    manager._cache_timestamp = None
    cur = _FakeCursor(fetchall_return=[
        ('LONG', '50+', 1.0, 10.0, 10, 55.0, 0.1, 5.0),
        ('SHORT', '45-50', 2.0, 20.0, 20, 60.0, 0.2, 10.0),
    ])
    conn = _FakeConn(cur)
    pool = _FakePool(conn)
    manager._get_db_pool = lambda: _FakePGLogger(pool)

    manager._refresh_cache_if_needed()
    assert ('LONG', '50+') in manager._cache
    assert manager._cache_timestamp is not None


def test_log_to_history_v2_and_v1_and_unknown(manager):
    # v2 schema
    cur = _FakeCursor(fetchall_return=[('actual_winrate',)])
    conn = _FakeConn(cur)
    pool = _FakePool(conn)
    manager._get_db_pool = lambda: _FakePGLogger(pool)

    assert manager._log_to_history('LONG', '50+', None, 55.0, 10, 10.0, 'update') is True
    assert conn.committed >= 1

    # v1 schema
    manager._history_schema = None
    cur2 = _FakeCursor(fetchall_return=[('new_winrate',)])
    conn2 = _FakeConn(cur2)
    pool2 = _FakePool(conn2)
    manager._get_db_pool = lambda: _FakePGLogger(pool2)

    assert manager._log_to_history('LONG', '50+', 50.0, 55.0, 10, 10.0, 'update') is True

    # unknown schema => returns False
    manager._history_schema = None
    cur3 = _FakeCursor(fetchall_return=[('something_else',)])
    conn3 = _FakeConn(cur3)
    pool3 = _FakePool(conn3)
    manager._get_db_pool = lambda: _FakePGLogger(pool3)

    assert manager._log_to_history('LONG', '50+', 50.0, 55.0, 10, 10.0, 'update') is False


def test_reset_calibration_success_and_failure(manager):
    # success path
    manager._detect_history_schema = lambda _cur: 'v2'
    cur = _FakeCursor(fetchall_return=[('actual_winrate',)], rowcount=3)
    conn = _FakeConn(cur)
    pool = _FakePool(conn)
    manager._get_db_pool = lambda: _FakePGLogger(pool)
    manager._cache = {('LONG', '50+'): object()}
    manager._cache_timestamp = datetime.now(timezone.utc)

    assert manager.reset_calibration(reason='manual') is True
    assert manager._cache == {}
    assert manager._cache_timestamp is None

    # failure when no db
    manager._get_db_pool = lambda: None
    assert manager.reset_calibration(reason='manual') is False

    # failure on DB exception
    class BadPool:
        def getconn(self):
            raise RuntimeError('boom')

        def putconn(self, _conn):
            return None

    manager._get_db_pool = lambda: types.SimpleNamespace(pool=BadPool())
    assert manager.reset_calibration(reason='manual') is False


def test_reset_calibration_v1_history_branch_and_history_error(manager):
    # v1 schema branch
    manager._detect_history_schema = lambda _cur: 'v1'
    cur = _FakeCursor(fetchall_return=[('new_winrate',)], rowcount=1)
    conn = _FakeConn(cur)
    pool = _FakePool(conn)
    manager._get_db_pool = lambda: _FakePGLogger(pool)
    assert manager.reset_calibration(reason='manual') is True

    # history log exception path should still allow reset
    def bad_detect(_cur):
        raise RuntimeError('boom')

    manager._detect_history_schema = bad_detect
    cur2 = _FakeCursor(fetchall_return=[('new_winrate',)], rowcount=1)
    conn2 = _FakeConn(cur2)
    pool2 = _FakePool(conn2)
    manager._get_db_pool = lambda: _FakePGLogger(pool2)
    assert manager.reset_calibration(reason='manual') is True


def test_get_current_model_info_success_and_error(manager, monkeypatch):
    class DummyPredictor:
        def __init__(self):
            self.metadata = {
                'timestamp': 't1',
                'model_type': 'gb',
                'n_features': 2,
                'feature_names': ['a', 'b'],
                'metrics': {'acc': 0.6},
            }

    monkeypatch.setattr('optimization.predictor_optimized.OptimizedPredictor', DummyPredictor)
    info = manager.get_current_model_info()
    assert info['timestamp'] == 't1'

    def boom():
        raise RuntimeError('boom')

    monkeypatch.setattr('optimization.predictor_optimized.OptimizedPredictor', boom)
    info2 = manager.get_current_model_info()
    assert info2['timestamp'] == 'unknown'

    # no metadata
    class DummyPredictor2:
        def __init__(self):
            self.metadata = None

    monkeypatch.setattr('optimization.predictor_optimized.OptimizedPredictor', DummyPredictor2)
    info3 = manager.get_current_model_info()
    assert info3['timestamp'] == 'unknown'


def test_get_last_calibration_model_version(manager):
    # no db
    manager._get_db_pool = lambda: None
    assert manager.get_last_calibration_model_version() is None

    # with db
    cur = _FakeCursor(fetchone_side_effect=[('t1',)])
    conn = _FakeConn(cur)
    pool = _FakePool(conn)
    manager._get_db_pool = lambda: _FakePGLogger(pool)
    assert manager.get_last_calibration_model_version() == 't1'

    # exception path
    class BadPool:
        def getconn(self):
            raise RuntimeError('boom')

        def putconn(self, _conn):
            return None

    manager._get_db_pool = lambda: types.SimpleNamespace(pool=BadPool())
    assert manager.get_last_calibration_model_version() is None


def test_update_calibration_model_version(manager):
    manager._get_db_pool = lambda: None
    assert manager._update_calibration_model_version('t1') is False

    cur = _FakeCursor(rowcount=2)
    conn = _FakeConn(cur)
    pool = _FakePool(conn)
    manager._get_db_pool = lambda: _FakePGLogger(pool)
    assert manager._update_calibration_model_version('t2') is True

    # exception
    class BadCursor:
        rowcount = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, *_a, **_k):
            raise RuntimeError('boom')

    class BadConn:
        def cursor(self):
            return BadCursor()

        def commit(self):
            return None

    manager._get_db_pool = lambda: types.SimpleNamespace(pool=types.SimpleNamespace(getconn=lambda: BadConn(), putconn=lambda _c: None))
    assert manager._update_calibration_model_version('t3') is False


def test_seed_from_historical_and_last_n_trades(manager):
    # no db
    manager._get_db_pool = lambda: None
    assert manager.seed_from_historical_trades(days=1) == 0
    assert manager.seed_from_last_n_trades(n_trades=10) == 0

    rows = [
        ('LONG', 55.0, True, 0.1, 2.0, True, False, datetime.now(timezone.utc)),
        ('SHORT', 0.55, False, -0.1, -2.0, False, True, datetime.now(timezone.utc)),
    ]
    cur = _FakeCursor(fetchall_return=rows)
    conn = _FakeConn(cur)
    pool = _FakePool(conn)
    manager._get_db_pool = lambda: _FakePGLogger(pool)

    called = {'n': 0}
    manager.update_calibration = lambda **kwargs: called.__setitem__('n', called['n'] + 1) or True

    assert manager.seed_from_historical_trades(days=1) == 2
    assert called['n'] >= 2

    # exception path: cursor.execute fails
    class BadCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, *_a, **_k):
            raise RuntimeError('boom')

        def fetchall(self):
            return []

    class BadConn:
        def cursor(self):
            return BadCursor()

    manager._get_db_pool = lambda: types.SimpleNamespace(pool=types.SimpleNamespace(getconn=lambda: BadConn(), putconn=lambda _c: None))
    assert manager.seed_from_historical_trades(days=1) == 0


def test_seed_from_last_n_trades_db_path_and_exception(manager):
    rows = [
        ('LONG', 55.0, True, 0.1, 2.0, True, False, datetime.now(timezone.utc)),
    ]
    cur = _FakeCursor(fetchall_return=rows)
    conn = _FakeConn(cur)
    pool = _FakePool(conn)
    manager._get_db_pool = lambda: _FakePGLogger(pool)
    manager.update_calibration = lambda **kwargs: True
    assert manager.seed_from_last_n_trades(n_trades=1) == 1

    class BadCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, *_a, **_k):
            raise RuntimeError('boom')

        def fetchall(self):
            return []

    class BadConn:
        def cursor(self):
            return BadCursor()

    manager._get_db_pool = lambda: types.SimpleNamespace(pool=types.SimpleNamespace(getconn=lambda: BadConn(), putconn=lambda _c: None))
    assert manager.seed_from_last_n_trades(n_trades=1) == 0


def test_get_db_pool_with_existing_pg_logger(manager):
    # Ligne 136: return self._pg_logger quand il existe déjà
    fake_pg = types.SimpleNamespace(enabled=True, pool=types.SimpleNamespace())
    manager._pg_logger = fake_pg
    assert manager._get_db_pool() is fake_pg


def test_calculate_trade_weight_paper_trading_and_naive_timezone(manager):
    manager._get_config = lambda: {'live_weight': 1.0, 'dryrun_weight': 0.5, 'decay_days': 7}
    
    # Ligne 222: type_weight = 0.2 pour paper trading (ni live ni dry_run)
    weight = manager.calculate_trade_weight(
        is_live=False, 
        is_dry_run=False, 
        trade_timestamp=datetime.now()
    )
    # Le poids de base est 0.2 * age_weight
    assert 0 < weight < 0.25  # age_weight appliqué
    
    # Ligne 227: trade_timestamp naive -> replace(tzinfo=timezone.utc)
    naive_ts = datetime(2024, 1, 1, 12, 0, 0)  # Sans timezone
    weight2 = manager.calculate_trade_weight(
        is_live=True,
        is_dry_run=False,
        trade_timestamp=naive_ts
    )
    assert weight2 > 0


def test_log_to_history_db_exception_paths(manager):
    # Ligne 411: return False quand pas de db_pool
    manager._get_db_pool = lambda: None
    assert manager._log_to_history('LONG', '50+', None, 55.0, 10, 10.0, 'test') is False
    
    # Lignes 447-449: exception dans _log_to_history -> return False
    class BadPool:
        def getconn(self):
            raise RuntimeError('boom')
        def putconn(self, _c):
            pass
    
    manager._get_db_pool = lambda: types.SimpleNamespace(pool=BadPool())
    assert manager._log_to_history('LONG', '50+', None, 55.0, 10, 10.0, 'test') is False
    
    # Lignes 439-440: rollback exception dans unknown schema
    class BadConn:
        def cursor(self):
            return self
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def execute(self, *_a, **_k):
            pass
        def fetchall(self):
            return [('unknown_col',)]  # Schema unknown
        def rollback(self):
            raise RuntimeError('rollback failed')  # Exception dans rollback
    
    manager._history_schema = None
    manager._get_db_pool = lambda: types.SimpleNamespace(pool=types.SimpleNamespace(getconn=lambda: BadConn(), putconn=lambda _c: None))
    result = manager._log_to_history('LONG', '50+', None, 55.0, 10, 10.0, 'test')
    assert result is False


def test_refresh_cache_if_needed_no_db_and_exception(manager):
    # Ligne 575: early return si pas de db_pool
    manager._cache_timestamp = None
    manager._get_db_pool = lambda: None
    manager._refresh_cache_if_needed()
    # Cache reste vide
    assert manager._cache == {}
    
    # Lignes 608-609: exception dans _refresh_cache_if_needed
    class BadPool:
        def getconn(self):
            raise RuntimeError('db error')
        def putconn(self, _c):
            pass
    
    manager._cache_timestamp = None
    manager._get_db_pool = lambda: types.SimpleNamespace(pool=BadPool())
    manager._refresh_cache_if_needed()
    # Exception gérée, cache reste vide


def test_get_all_stats_structure(manager):
    # Lignes 618, 620-622, 624: get_all_stats structure
    manager._refresh_cache_if_needed = lambda: None
    manager._cache = {
        ('LONG', '50+'): calib.CalibrationStats('LONG', '50+', 1.0, 2.0, 10, 50.0, 0.1, 5.0),
        ('SHORT', '45-50'): calib.CalibrationStats('SHORT', '45-50', 2.0, 4.0, 20, 55.0, 0.2, 10.0),
    }
    
    stats = manager.get_all_stats()
    assert 'LONG' in stats
    assert 'SHORT' in stats
    assert '50+' in stats['LONG']
    assert '45-50' in stats['SHORT']
    assert stats['LONG']['50+'].total_trades == 10
    assert stats['SHORT']['45-50'].total_trades == 20


def test_check_model_change_and_auto_reset_exceptions(manager):
    # Lignes 868-870: exception dans check_model_change_and_auto_reset
    manager._get_config = lambda: {'auto_reset_on_retrain': True}
    
    def boom():
        raise RuntimeError('model info failed')
    
    manager.get_current_model_info = boom
    assert manager.check_model_change_and_auto_reset() is False
    
    # Lignes 862-863: reset_success = False branch
    manager.get_current_model_info = lambda: {'timestamp': 't2'}
    manager.get_last_calibration_model_version = lambda: 't1'
    manager.reset_calibration = lambda reason: False  # Échec
    
    result = manager.check_model_change_and_auto_reset()
    assert result is False
