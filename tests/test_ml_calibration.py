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


def test_detect_history_schema_caches(manager):
    cur = _FakeCursor(fetchall_return=[('actual_winrate',)])
    assert manager._detect_history_schema(cur) == 'v2'
    # cached
    cur2 = _FakeCursor(fetchall_return=[])
    assert manager._detect_history_schema(cur2) == 'v2'


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
    assert called['ver'] == 't1'


def test_check_model_change_and_auto_reset_detects_change_and_resets(manager):
    manager._get_config = lambda: {'auto_reset_on_retrain': True}
    manager.get_current_model_info = lambda: {'timestamp': 't2'}
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
