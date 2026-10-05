#!/usr/bin/env python3
"""Runtime verification loop

Checks (Phase 1B/1E/2D):
- scan_logs filling (market regime context present)
- market_regime_history activity + V2 metadata columns
- trades context columns (when trades exist)
- ML state files persistence (threshold optimizer + drift detector)
- backend API health (optional)

Usage:
  python verification/verify_runtime_loop.py

Optional:
  python verification/verify_runtime_loop.py --interval 15 --loops 40
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure repo root import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import psycopg2
from dotenv import load_dotenv

load_dotenv()

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


DEFAULT_BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:5000')


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')


def _print_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(f"{title}")
    print("=" * 80)


def _print_kv(key: str, value: Any) -> None:
    print(f"- {key}: {value}")


def _safe_read_json(path: Path) -> Optional[dict]:
    try:
        if not path.exists():
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _get_db_conn():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        dbname=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )


def _fetch_backend_json(url: str, timeout: float = 5.0) -> Optional[dict]:
    if not requests:
        return None
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def check_scan_logs(conn) -> Dict[str, Any]:
    cur = conn.cursor()

    cur.execute("""
        SELECT
            COUNT(*) AS total,
            COUNT(market_regime) AS with_regime,
            COUNT(atr_pct_1m) AS with_atr_1m,
            COUNT(atr_pct_5m) AS with_atr_5m
        FROM scan_logs
        WHERE timestamp > NOW() - INTERVAL '10 minutes'
    """)
    total, with_regime, with_atr_1m, with_atr_5m = cur.fetchone()

    cur.execute("""
        SELECT symbol, timestamp, market_regime, market_regime_avg_atr, market_regime_avg_adx,
               atr_pct_1m, atr_pct_5m
        FROM scan_logs
        ORDER BY timestamp DESC
        LIMIT 1
    """)
    last = cur.fetchone()

    cur.close()

    return {
        'total_10m': total,
        'with_regime_10m': with_regime,
        'with_atr_1m_10m': with_atr_1m,
        'with_atr_5m_10m': with_atr_5m,
        'last_row': last,
    }


def check_market_regime_history(conn) -> Dict[str, Any]:
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM market_regime_history
        WHERE timestamp > NOW() - INTERVAL '24 hours'
    """)
    total_24h = cur.fetchone()[0]

    cur.execute("""
        SELECT timestamp, old_regime, new_regime, avg_atr, avg_adx,
               detection_method, atr_median, atr_smoothed, hysteresis_applied, outliers_filtered_count
        FROM market_regime_history
        ORDER BY timestamp DESC
        LIMIT 1
    """)
    last = cur.fetchone()

    cur.close()

    return {
        'total_24h': total_24h,
        'last_row': last,
    }


def check_trades(conn) -> Dict[str, Any]:
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM trades
        WHERE timestamp_entry > NOW() - INTERVAL '24 hours'
    """)
    total_24h = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM trades
        WHERE timestamp_entry > NOW() - INTERVAL '24 hours'
          AND entry_market_regime IS NOT NULL
    """)
    with_regime_24h = cur.fetchone()[0]

    cur.execute("""
        SELECT symbol, timestamp_entry, entry_market_regime, entry_market_regime_avg_atr,
               entry_cb_state, pnl_pct, net_pnl_pct
        FROM trades
        ORDER BY timestamp_entry DESC
        LIMIT 1
    """)
    last = cur.fetchone()

    cur.close()

    return {
        'total_24h': total_24h,
        'with_regime_24h': with_regime_24h,
        'last_row': last,
    }


def check_ml_state_files(repo_root: Path) -> Dict[str, Any]:
    threshold_path = repo_root / 'data' / 'ml' / 'threshold_optimizer_state.json'
    drift_path = repo_root / 'data' / 'ml' / 'drift_detector_state.json'

    threshold_state = _safe_read_json(threshold_path)
    drift_state = _safe_read_json(drift_path)

    def file_info(p: Path) -> Dict[str, Any]:
        if not p.exists():
            return {'exists': False}
        st = p.stat()
        return {
            'exists': True,
            'size': st.st_size,
            'mtime_utc': datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
        }

    info = {
        'threshold_file': file_info(threshold_path),
        'drift_file': file_info(drift_path),
        'threshold_state': None,
        'drift_state': None,
    }

    if isinstance(threshold_state, dict):
        contexts = threshold_state.get('contexts', {})
        info['threshold_state'] = {
            'total_updates': threshold_state.get('total_updates'),
            'contexts': len(contexts) if isinstance(contexts, dict) else None,
            'saved_at': threshold_state.get('saved_at')
        }

    if isinstance(drift_state, dict):
        pnl_window = drift_state.get('pnl_window', [])
        winrate_window = drift_state.get('winrate_window', [])
        info['drift_state'] = {
            'total_trades': drift_state.get('total_trades'),
            'trades_since_alert': drift_state.get('trades_since_alert'),
            'pnl_window_len': len(pnl_window) if isinstance(pnl_window, list) else None,
            'winrate_window_len': len(winrate_window) if isinstance(winrate_window, list) else None,
            'saved_at': drift_state.get('saved_at')
        }

    return info


def check_config_overrides(repo_root: Path) -> Dict[str, Any]:
    overrides_path = repo_root / 'config_overrides.json'
    overrides = _safe_read_json(overrides_path)

    if not isinstance(overrides, dict):
        return {'exists': overrides_path.exists(), 'keys': 0, 'important': {}}

    important_keys = [
        'market_regime_v2_enabled',
        'market_regime_use_atr_5m',
        'market_regime_use_hysteresis',
        'market_regime_use_smoothing',
        'market_regime_use_median',
        'market_regime_outlier_filter',
        'market_regime_auto_calibration_enabled',
        'market_regime_btc_indicator_enabled',
        'threshold_optimizer_enabled',
        'threshold_min',
        'threshold_max',
        'drift_detection_enabled'
    ]

    return {
        'exists': True,
        'keys': len(overrides),
        'important': {k: overrides.get(k) for k in important_keys if k in overrides}
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--interval', type=int, default=10, help='Seconds between checks')
    parser.add_argument('--loops', type=int, default=0, help='Number of iterations (0 = infinite)')
    parser.add_argument('--backend-url', type=str, default=DEFAULT_BACKEND_URL)
    args = parser.parse_args()

    repo_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    loop_count = 0
    while True:
        loop_count += 1
        _print_header(f"RUNTIME VERIFICATION LOOP | {_now_str()} | Iteration {loop_count}")

        # Backend API (optional)
        if args.backend_url and requests:
            regime_status = _fetch_backend_json(f"{args.backend_url}/api/regime/status")
            ml_status = _fetch_backend_json(f"{args.backend_url}/api/ml/status")
            _print_header("Backend API")
            _print_kv('backend_url', args.backend_url)
            _print_kv('regime_status_ok', bool(regime_status))
            if regime_status:
                _print_kv('current_regime', regime_status.get('current_regime'))
                _print_kv('avg_atr', regime_status.get('avg_atr'))
                _print_kv('avg_adx', regime_status.get('avg_adx'))
                _print_kv('atr_sample_count', regime_status.get('atr_sample_count'))
                _print_kv('check_interval_minutes', regime_status.get('check_interval_minutes'))
            _print_kv('ml_status_ok', bool(ml_status))
            if ml_status:
                modules = ml_status.get('modules', {}) if isinstance(ml_status, dict) else {}
                thr = modules.get('threshold_optimizer', {}) if isinstance(modules, dict) else {}
                drift = modules.get('drift_detector', {}) if isinstance(modules, dict) else {}
                _print_kv('threshold_optimizer_enabled', thr.get('enabled'))
                _print_kv('threshold_optimizer_contexts', thr.get('total_contexts'))
                _print_kv('drift_detector_enabled', drift.get('enabled'))
                _print_kv('drift_total_trades', drift.get('total_trades'))

        # Files
        _print_header("Local persistence files")
        overrides_info = check_config_overrides(repo_root)
        _print_kv('config_overrides', overrides_info)

        ml_files = check_ml_state_files(repo_root)
        _print_kv('threshold_file', ml_files.get('threshold_file'))
        _print_kv('threshold_state', ml_files.get('threshold_state'))
        _print_kv('drift_file', ml_files.get('drift_file'))
        _print_kv('drift_state', ml_files.get('drift_state'))

        # Database
        try:
            conn = _get_db_conn()
        except Exception as e:
            _print_header('PostgreSQL')
            _print_kv('connection_ok', False)
            _print_kv('error', str(e))
            conn = None

        scans_ok = False
        trades_ok = False
        regime_history_ok = False

        if conn:
            try:
                _print_header('PostgreSQL')
                _print_kv('connection_ok', True)

                scan_stats = check_scan_logs(conn)
                hist_stats = check_market_regime_history(conn)
                trade_stats = check_trades(conn)

                _print_header('scan_logs (last 10 minutes)')
                _print_kv('total', scan_stats['total_10m'])
                _print_kv('with_market_regime', scan_stats['with_regime_10m'])
                _print_kv('with_atr_pct_1m', scan_stats['with_atr_1m_10m'])
                _print_kv('with_atr_pct_5m', scan_stats['with_atr_5m_10m'])
                _print_kv('last_row', scan_stats['last_row'])

                _print_header('market_regime_history (last 24 hours)')
                _print_kv('total_24h', hist_stats['total_24h'])
                _print_kv('last_row', hist_stats['last_row'])

                _print_header('trades (last 24 hours)')
                _print_kv('total_24h', trade_stats['total_24h'])
                _print_kv('with_entry_market_regime_24h', trade_stats['with_regime_24h'])
                _print_kv('last_row', trade_stats['last_row'])

                scans_ok = scan_stats['total_10m'] > 0 and scan_stats['with_regime_10m'] > 0
                regime_history_ok = hist_stats['total_24h'] > 0

                if trade_stats['total_24h'] == 0:
                    trades_ok = True
                else:
                    trades_ok = trade_stats['with_regime_24h'] > 0

            finally:
                try:
                    conn.close()
                except Exception:
                    pass

        _print_header('Summary')
        _print_kv('scans_ok', scans_ok)
        _print_kv('regime_history_ok', regime_history_ok)
        _print_kv('trades_ok', trades_ok)

        all_ok = scans_ok and trades_ok
        if all_ok:
            print("\n✅ OK: runtime signals look consistent.")
            return 0

        if args.loops and loop_count >= args.loops:
            print("\n⏹️ Stop: max loops reached.")
            return 2

        time.sleep(max(1, args.interval))


if __name__ == '__main__':
    raise SystemExit(main())
