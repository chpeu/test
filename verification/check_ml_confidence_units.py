import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, List, Tuple


def _enable_utf8_stdout() -> None:
    if sys.platform != 'win32':
        return
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def _load_env() -> None:
    root_dir = Path(__file__).resolve().parents[1]
    try:
        from dotenv import load_dotenv

        load_dotenv(root_dir / '.env')
    except Exception:
        pass


def _get_db_config() -> Dict[str, Any]:
    return {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'database': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', ''),
    }


def _connect():
    import psycopg2

    return psycopg2.connect(**_get_db_config())


def _fetchone(conn, query: str, params: Optional[Tuple[Any, ...]] = None) -> Optional[Dict[str, Any]]:
    from psycopg2.extras import RealDictCursor

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None


def _fetchall(conn, query: str, params: Optional[Tuple[Any, ...]] = None) -> List[Dict[str, Any]]:
    from psycopg2.extras import RealDictCursor

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
        return [dict(r) for r in rows] if rows else []


def _print_kv(titre: str, valeur: Any) -> None:
    print(f"{titre}: {valeur}")


def _infer_units(stats: Dict[str, Any]) -> str:
    n = int(stats.get('n') or 0)
    if n == 0:
        return 'aucune_donnee'

    max_v = stats.get('max')
    le1 = int(stats.get('le1') or 0)
    gt1_le100 = int(stats.get('gt1_le100') or 0)
    gt100 = int(stats.get('gt100') or 0)

    if gt100 > 0:
        return 'invalide_gt100'

    if le1 > 0 and gt1_le100 > 0:
        return 'mixte_decimal_et_pourcent'

    if max_v is None:
        return 'inconnu'

    try:
        max_v = float(max_v)
    except Exception:
        return 'inconnu'

    if max_v <= 1.5:
        return 'decimal_0_1'
    if max_v <= 100.0:
        return 'pourcent_0_100'
    return 'inconnu'


def _norm_to_percent(v: Optional[float]) -> Optional[float]:
    if v is None:
        return None
    try:
        fv = float(v)
    except Exception:
        return None

    return fv * 100.0 if fv <= 1.0 else fv


def _stats_from_subquery(conn, subquery_sql: str) -> Dict[str, Any]:
    query = f"""
        SELECT
            COUNT(*) AS n,
            MIN(ml_confidence) AS min,
            MAX(ml_confidence) AS max,
            AVG(ml_confidence) AS avg,
            PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY ml_confidence) AS p10,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY ml_confidence) AS p50,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY ml_confidence) AS p90,
            COUNT(*) FILTER (WHERE ml_confidence <= 1.0) AS le1,
            COUNT(*) FILTER (WHERE ml_confidence > 1.0 AND ml_confidence <= 100.0) AS gt1_le100,
            COUNT(*) FILTER (WHERE ml_confidence > 100.0) AS gt100
        FROM (
            {subquery_sql}
        ) x
        WHERE ml_confidence IS NOT NULL
    """
    row = _fetchone(conn, query)
    return row or {'n': 0}


def _print_stats_block(label: str, stats: Dict[str, Any]) -> None:
    print("\n" + "=" * 80)
    print(label)
    print("=" * 80)

    unit = _infer_units(stats)
    _print_kv('n', int(stats.get('n') or 0))
    _print_kv('min', stats.get('min'))
    _print_kv('p10', stats.get('p10'))
    _print_kv('p50', stats.get('p50'))
    _print_kv('p90', stats.get('p90'))
    _print_kv('max', stats.get('max'))
    _print_kv('moy', stats.get('avg'))
    _print_kv('compte<=1', int(stats.get('le1') or 0))
    _print_kv('compte(1..100]', int(stats.get('gt1_le100') or 0))
    _print_kv('compte>100', int(stats.get('gt100') or 0))
    _print_kv('unites_inferees', unit)


def _print_schema(conn) -> None:
    print("\n" + "=" * 80)
    print("SCHEMA")
    print("=" * 80)

    for table in ['trades', 'scan_logs']:
        row = _fetchone(
            conn,
            """
                SELECT column_name, data_type, numeric_precision, numeric_scale, is_nullable
                FROM information_schema.columns
                WHERE table_name = %s AND column_name = 'ml_confidence'
            """,
            (table,),
        )
        if not row:
            print(f"{table}.ml_confidence: NON TROUVE")
            continue
        print(
            f"{table}.ml_confidence: type={row.get('data_type')}, "
            f"precision={row.get('numeric_precision')}, scale={row.get('numeric_scale')}, "
            f"nullable={row.get('is_nullable')}"
        )


def _analyze_last_trades(conn, limit: int = 100) -> None:
    rows = _fetchall(
        conn,
        f"""
            SELECT
                t.id,
                t.symbol,
                t.direction,
                t.timestamp_entry,
                t.timestamp_exit,
                t.exit_reason,
                t.net_pnl_usdt,
                t.net_pnl_pct,
                COALESCE(t.ml_confidence, s.ml_confidence) AS ml_confidence
            FROM trades t
            LEFT JOIN scan_logs s ON t.scan_log_id = s.id
            WHERE t.timestamp_entry IS NOT NULL
            ORDER BY t.timestamp_entry DESC
            LIMIT {int(limit)}
        """,
    )

    ml_vals_raw: List[float] = []
    ml_vals_pct: List[float] = []
    wins_pct: List[float] = []
    losses_pct: List[float] = []

    missing = 0
    for r in rows:
        v_raw = r.get('ml_confidence')
        v_pct = _norm_to_percent(v_raw)
        if v_raw is None:
            missing += 1
        else:
            try:
                ml_vals_raw.append(float(v_raw))
            except Exception:
                pass
        if v_pct is not None:
            ml_vals_pct.append(v_pct)

        pnl_usdt = r.get('net_pnl_usdt')
        pnl_pct = r.get('net_pnl_pct')

        win: Optional[bool] = None
        if pnl_usdt is not None:
            try:
                win = float(pnl_usdt) > 0
            except Exception:
                win = None
        if win is None and pnl_pct is not None:
            try:
                win = float(pnl_pct) > 0
            except Exception:
                win = None

        if v_pct is not None and win is not None:
            if win:
                wins_pct.append(v_pct)
            else:
                losses_pct.append(v_pct)

    print("\n" + "=" * 80)
    print(f"DERNIERS {len(rows)} TRADES (COALESCE trades.ml_confidence, scan_logs.ml_confidence)")
    print("=" * 80)

    _print_kv('lignes', len(rows))
    _print_kv('ml_confidence_manquant', missing)

    if ml_vals_raw:
        _print_kv('brut_min', min(ml_vals_raw))
        _print_kv('brut_max', max(ml_vals_raw))
    if ml_vals_pct:
        _print_kv('pct_min', min(ml_vals_pct))
        _print_kv('pct_max', max(ml_vals_pct))

    def _avg(values: List[float]) -> Optional[float]:
        return (sum(values) / len(values)) if values else None

    _print_kv('moy_pct_tous', _avg(ml_vals_pct))
    _print_kv('moy_pct_gagnants', _avg(wins_pct))
    _print_kv('moy_pct_perdants', _avg(losses_pct))

    if ml_vals_pct:
        le1 = sum(1 for x in ml_vals_raw if x <= 1.0) if ml_vals_raw else 0
        gt1 = sum(1 for x in ml_vals_raw if x > 1.0) if ml_vals_raw else 0
        _print_kv('brut_compte<=1', le1)
        _print_kv('brut_compte>1', gt1)


def main() -> int:
    _enable_utf8_stdout()
    _load_env()

    cfg = _get_db_config()
    print("=" * 80)
    print("VERIFICATION ML_CONFIDENCE DB")
    print("=" * 80)
    print(f"host={cfg['host']} port={cfg['port']} db={cfg['database']} user={cfg['user']}")

    try:
        conn = _connect()
    except Exception as e:
        print(f"[ERREUR] echec_connexion: {type(e).__name__}: {e}")
        return 1

    try:
        _print_schema(conn)

        trades_all = _stats_from_subquery(conn, "SELECT ml_confidence FROM trades")
        _print_stats_block('TRADES ml_confidence (TOUS)', trades_all)

        trades_recent = _stats_from_subquery(
            conn,
            "SELECT ml_confidence FROM trades WHERE ml_confidence IS NOT NULL ORDER BY timestamp_entry DESC LIMIT 500",
        )
        _print_stats_block('TRADES ml_confidence (500 DERNIERS non-null)', trades_recent)

        scan_all = _stats_from_subquery(conn, "SELECT ml_confidence FROM scan_logs")
        _print_stats_block('SCAN_LOGS ml_confidence (TOUS)', scan_all)

        scan_recent = _stats_from_subquery(
            conn,
            "SELECT ml_confidence FROM scan_logs WHERE ml_confidence IS NOT NULL ORDER BY timestamp DESC LIMIT 2000",
        )
        _print_stats_block('SCAN_LOGS ml_confidence (2000 DERNIERS non-null)', scan_recent)

        _analyze_last_trades(conn, limit=100)

        print("\n" + "=" * 80)
        print("TERMINE")
        print("=" * 80)
        return 0

    except Exception as e:
        print(f"[ERREUR] echec: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return 1

    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    raise SystemExit(main())
