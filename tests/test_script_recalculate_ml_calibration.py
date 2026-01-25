import importlib.util
import sys
import types
from pathlib import Path

import pytest


class _Cursor:
    def __init__(self, trades=None, results=None):
        self._trades = trades or []
        self._results = results or []
        self._last_query = None

    def execute(self, query, params=None):
        self._last_query = query

    def fetchall(self):
        q = (self._last_query or '').lower()
        if 'from trades' in q:
            return list(self._trades)
        if 'from ml_calibration' in q:
            return list(self._results)
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Conn:
    def __init__(self, cursor):
        self._cursor = cursor
        self.commits = 0

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commits += 1


class _Pool:
    def __init__(self, conn):
        self._conn = conn

    def getconn(self):
        return self._conn

    def putconn(self, _conn):
        return None


def _load_script_module(tmp_path):
    script_path = Path(__file__).resolve().parents[1] / 'scripts' / 'recalculate_ml_calibration.py'
    assert script_path.exists()

    # Importer sous le nom exact du module pour que coverage le reconnaisse
    # (sinon warning: module-not-imported)
    if 'scripts' not in sys.modules:
        pkg = types.ModuleType('scripts')
        pkg.__path__ = [str(script_path.parent)]
        sys.modules['scripts'] = pkg

    spec = importlib.util.spec_from_file_location('scripts.recalculate_ml_calibration', str(script_path))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_recalculate_ml_calibration_postgres_unavailable(monkeypatch, tmp_path):
    mod = _load_script_module(tmp_path)

    fake_pg_mod = types.SimpleNamespace(
        PostgreSQLDataLogger=lambda: types.SimpleNamespace(enabled=False, pool=None)
    )
    monkeypatch.setitem(sys.modules, 'core.postgresql_datalogger', fake_pg_mod)

    rc = mod.main()
    assert rc == 1


def test_recalculate_ml_calibration_no_trades(monkeypatch, tmp_path):
    mod = _load_script_module(tmp_path)

    cursor = _Cursor(trades=[], results=[])
    conn = _Conn(cursor)
    pool = _Pool(conn)

    fake_pg = types.SimpleNamespace(enabled=True, pool=pool)
    fake_pg_mod = types.SimpleNamespace(PostgreSQLDataLogger=lambda: fake_pg)
    monkeypatch.setitem(sys.modules, 'core.postgresql_datalogger', fake_pg_mod)

    # MLCalibrationManager dummy
    class DummyCalib:
        def __init__(self):
            self.calls = 0

        def update_calibration(self, **kwargs):
            self.calls += 1
            return True

    fake_calib_mod = types.SimpleNamespace(
        MLCalibrationManager=DummyCalib,
        VALID_EXIT_REASONS_CALIBRATION={'TP', 'SL'}
    )
    monkeypatch.setitem(sys.modules, 'ml.calibration', fake_calib_mod)

    rc = mod.main()
    assert rc == 0


def test_recalculate_ml_calibration_process_trades_and_results(monkeypatch, tmp_path):
    mod = _load_script_module(tmp_path)

    # trades rows: (id, symbol, direction, ml_confidence, net_pnl_usdt, pnl_pct, exit_reason, is_live, created_at)
    trades = [
        (1, 'BTC', 'LONG', 0.55, 10.0, 0.1, 'TP', True, None),
        (2, 'ETH', 'SHORT', 0.10, -5.0, -0.1, 'SL', True, None),  # skipped_conf (<30%)
        (3, 'XRP', 'LONG', 0.80, 3.0, 0.05, 'MANUAL', True, None),  # skipped_exit
        (4, 'SOL', 'LONG', 55.0, None, None, 'TP', False, None),
    ]

    results = [
        ('LONG', '50+', 1.0, 2.0, 2, 55.0),
    ]

    cursor = _Cursor(trades=trades, results=results)
    conn = _Conn(cursor)
    pool = _Pool(conn)

    fake_pg = types.SimpleNamespace(enabled=True, pool=pool)
    fake_pg_mod = types.SimpleNamespace(PostgreSQLDataLogger=lambda: fake_pg)
    monkeypatch.setitem(sys.modules, 'core.postgresql_datalogger', fake_pg_mod)

    class DummyCalib:
        def __init__(self):
            self.calls = 0

        def update_calibration(self, **kwargs):
            self.calls += 1
            if kwargs.get('ml_confidence') == 55.0 and kwargs.get('direction') == 'LONG':
                # raise once to cover exception print path
                raise RuntimeError('boom')
            return True

    fake_calib_mod = types.SimpleNamespace(
        MLCalibrationManager=DummyCalib,
        VALID_EXIT_REASONS_CALIBRATION={'TP', 'SL'}
    )
    monkeypatch.setitem(sys.modules, 'ml.calibration', fake_calib_mod)

    rc = mod.main()
    assert rc == 0


def test_recalculate_ml_calibration_general_exception(monkeypatch, tmp_path):
    """Test pour couvrir les lignes 164-168: exception générale dans main()"""
    mod = _load_script_module(tmp_path)
    
    # Mock qui force une exception dans PostgreSQLDataLogger.__init__
    def boom_pg():
        raise RuntimeError('General error in script')
    
    fake_pg_mod = types.SimpleNamespace(PostgreSQLDataLogger=boom_pg)
    monkeypatch.setitem(sys.modules, 'core.postgresql_datalogger', fake_pg_mod)
    
    rc = mod.main()
    assert rc == 1


def test_recalculate_ml_calibration_covers_missing_lines(monkeypatch, tmp_path):
    """Test pour couvrir les lignes 88, 155, 171"""
    mod = _load_script_module(tmp_path)
    
    # Ligne 88: ml_conf_pct = None quand ml_conf_raw est None
    trades_with_none_confidence = [
        (1, 'BTCUSDT', 'LONG', None, 100.0, 0.5, 'TP', True, '2024-01-01 12:00:00'),  # ml_confidence=None
    ]
    
    # Ligne 155: print warning quand aucun bucket avec trades (results vide)
    results_empty = []  # Pas de buckets
    
    cursor = _Cursor(trades=trades_with_none_confidence, results=results_empty)
    conn = _Conn(cursor)
    pool = _Pool(conn)
    
    fake_pg_mod = types.SimpleNamespace(
        PostgreSQLDataLogger=lambda: types.SimpleNamespace(enabled=True, pool=pool)
    )
    monkeypatch.setitem(sys.modules, 'core.postgresql_datalogger', fake_pg_mod)
    
    # Le script importe MLCalibrationManager directement
    class DummyCalib:
        def reset_calibration(self, reason):
            return True
        def update_calibration(self, **kwargs):
            return True
    
    fake_calib_mod = types.SimpleNamespace(
        MLCalibrationManager=DummyCalib,
        VALID_EXIT_REASONS_CALIBRATION=['TP', 'SL'],
    )
    monkeypatch.setitem(sys.modules, 'ml.calibration', fake_calib_mod)
    
    rc = mod.main()
    assert rc == 0


def test_recalculate_ml_calibration_main_execution(monkeypatch, tmp_path):
    """Test pour couvrir ligne 171: if __name__ == '__main__': sys.exit(main())"""
    mod = _load_script_module(tmp_path)
    
    # Mock sys.exit pour capturer l'appel
    exit_called = {'code': None}
    def fake_exit(code):
        exit_called['code'] = code
        
    monkeypatch.setattr('sys.exit', fake_exit)
    
    # Mock main() pour retourner 0
    monkeypatch.setattr(mod, 'main', lambda: 0)
    
    # Simuler l'exécution comme script principal
    mod.__name__ = '__main__'
    
    # Exécuter le code __main__ en important le module comme script
    exec(compile(open(mod.__file__).read(), mod.__file__, 'exec'), {'__name__': '__main__'})
    
    # Vérifier que sys.exit a été appelé avec le bon code
    assert exit_called['code'] == 0
