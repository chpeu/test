import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict


try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


SEP = "|"


def run_sql(query: str):
    env = os.environ.copy()
    env["PGCLIENTENCODING"] = "UTF8"

    if env.get("POSTGRES_PASSWORD"):
        env["PGPASSWORD"] = env["POSTGRES_PASSWORD"]

    host = env.get("POSTGRES_HOST", "localhost")
    user = env.get("POSTGRES_USER", "postgres")
    db = env.get("POSTGRES_DB", "trade_cursor_ml")

    result = subprocess.run(
        [
            "psql",
            "-h",
            host,
            "-U",
            user,
            "-d",
            db,
            "-t",
            "-A",
            "-F",
            SEP,
            "-c",
            query,
        ],
        capture_output=True,
        text=True,
        env=env,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        print("SQL Error:")
        print(result.stderr)
        return []

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return [line.split(SEP) for line in lines]


def to_float(x):
    if x is None:
        return None
    s = str(x).strip()
    if not s or s.lower() == "null":
        return None
    try:
        return float(s)
    except Exception:
        return None


def to_bool(x):
    if x is None:
        return None
    s = str(x).strip().lower()
    if s in ("t", "true", "1", "yes"):
        return True
    if s in ("f", "false", "0", "no"):
        return False
    return None


def rsi_bucket(direction: str, rsi: float | None) -> str:
    if rsi is None:
        return "NULL"

    if direction == "LONG":
        if rsi < 40:
            return "<40"
        if rsi < 50:
            return "40-50"
        if rsi < 55:
            return "50-55"
        if rsi < 60:
            return "55-60"
        if rsi < 65:
            return "60-65"
        if rsi < 70:
            return "65-70"
        return ">=70"

    if rsi > 60:
        return ">60"
    if rsi > 50:
        return "50-60"
    if rsi > 45:
        return "45-50"
    if rsi > 40:
        return "40-45"
    if rsi > 35:
        return "35-40"
    if rsi > 30:
        return "30-35"
    return "<=30"


def atr_bucket(atr_pct: float | None) -> str:
    if atr_pct is None:
        return "NULL"
    if atr_pct < 0.5:
        return "<0.5%"
    if atr_pct < 1.0:
        return "0.5-1.0%"
    if atr_pct < 1.5:
        return "1.0-1.5%"
    if atr_pct < 2.0:
        return "1.5-2.0%"
    return ">=2.0%"


def adx_bucket(adx: float | None) -> str:
    if adx is None:
        return "NULL"
    if adx < 20:
        return "<20"
    if adx < 25:
        return "20-25"
    if adx < 30:
        return "25-30"
    if adx < 35:
        return "30-35"
    return ">=35"


def vol_bucket(vr: float | None) -> str:
    if vr is None:
        return "NULL"
    if vr < 0.8:
        return "<0.8"
    if vr < 1.0:
        return "0.8-1.0"
    if vr < 1.2:
        return "1.0-1.2"
    if vr < 1.5:
        return "1.2-1.5"
    return ">=1.5"


def load_regime_rsi_thresholds() -> dict:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mapping = {
        "CALME": "calme.json",
        "NORMAL": "normal.json",
        "VOLATILE": "volatile.json",
        "CHOPPY": "choppy.json",
    }
    thresholds = {}
    for regime, fname in mapping.items():
        path = os.path.join(root, "config", "regimes", fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            thresholds[regime] = (
                float(data.get("rsi_final_long_max", 65.0)),
                float(data.get("rsi_final_short_min", 35.0)),
            )
        except Exception:
            thresholds[regime] = (65.0, 35.0)

    thresholds["UNKNOWN"] = (65.0, 35.0)
    return thresholds


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--recent-pool", type=int, default=2000)
    parser.add_argument("--sort", choices=["net_pnl_usdt", "net_pnl_pct"], default="net_pnl_usdt")
    args = parser.parse_args()

    query = f"""
WITH recent AS (
    SELECT *
    FROM trades
    WHERE is_live_trade = true
      AND exit_price IS NOT NULL
      AND net_pnl_usdt IS NOT NULL
    ORDER BY timestamp_entry DESC
    LIMIT {args.recent_pool}
)
SELECT
    t.id,
    t.symbol,
    t.direction,
    t.net_pnl_usdt,
    t.net_pnl_pct,
    COALESCE(t.entry_market_regime, 'UNKNOWN') AS regime,
    COALESCE(t.exit_reason, 'UNKNOWN') AS exit_reason,
    t.entry_rsi_1m,
    t.entry_adx_1m,
    t.entry_volume_ratio_1m,
    t.entry_score,
    t.entry_effective_min_score,
    tam.entry_atr_pct_used,
    tam.entry_atr_blended,
    s.atr_optimal_passed_1m AS atr_optimal_passed,
    s.snr_passed_1m AS snr_passed,
    s.breakout_passed_1m AS breakout_passed,
    s.wick_passed_1m AS wick_passed
FROM recent t
LEFT JOIN trade_atr_metrics tam ON tam.trade_id = t.id
LEFT JOIN scan_logs s ON t.scan_log_id = s.id
ORDER BY t.{args.sort} ASC
LIMIT {args.limit}
"""

    rows = run_sql(query)

    cols = [
        "id",
        "symbol",
        "direction",
        "net_pnl_usdt",
        "net_pnl_pct",
        "regime",
        "exit_reason",
        "entry_rsi_1m",
        "entry_adx_1m",
        "entry_volume_ratio_1m",
        "entry_score",
        "entry_effective_min_score",
        "entry_atr_pct_used",
        "entry_atr_blended",
        "atr_optimal_passed",
        "snr_passed",
        "breakout_passed",
        "wick_passed",
    ]

    trades = []
    for r in rows:
        t = {}
        for i, c in enumerate(cols):
            v = r[i] if i < len(r) else None
            if c in (
                "net_pnl_usdt",
                "net_pnl_pct",
                "entry_rsi_1m",
                "entry_adx_1m",
                "entry_volume_ratio_1m",
                "entry_score",
                "entry_effective_min_score",
                "entry_atr_pct_used",
                "entry_atr_blended",
            ):
                t[c] = to_float(v)
            elif c in ("atr_optimal_passed", "snr_passed", "breakout_passed", "wick_passed"):
                t[c] = to_bool(v)
            else:
                t[c] = v
        trades.append(t)

    print("=" * 80)
    print(f"ANALYSE {len(trades)} PIRES TRADES (dans les {args.recent_pool} plus récents)")
    print("=" * 80)

    if not trades:
        print("Aucun trade trouvé (vérifie DB/psql/env).")
        return 1

    total_pnl = sum((t["net_pnl_usdt"] or 0.0) for t in trades)
    print(f"PnL total (ces trades): {total_pnl:.2f} USDT")

    print("\nTop 10 pires trades:")
    for t in trades[:10]:
        print(
            f"  id={t['id']} {t['symbol']} {t['direction']} pnl={t['net_pnl_usdt']:.2f} "
            f"reg={t['regime']} reason={t['exit_reason']} rsi={t['entry_rsi_1m']} adx={t['entry_adx_1m']} "
            f"atr%={t['entry_atr_pct_used']}"
        )

    print("\nPnL par (regime, direction):")
    reg_dir = defaultdict(lambda: {"count": 0, "pnl": 0.0})
    for t in trades:
        key = (t["regime"], t["direction"])
        reg_dir[key]["count"] += 1
        reg_dir[key]["pnl"] += (t["net_pnl_usdt"] or 0.0)

    for (reg, d), s in sorted(reg_dir.items(), key=lambda kv: kv[1]["pnl"]):
        avg = s["pnl"] / s["count"] if s["count"] else 0.0
        print(f"  {reg:<10} {d:<5} count={s['count']:<4} pnl={s['pnl']:<10.2f} avg={avg:<8.2f}")

    print("\nExit reasons (top 10 par count):")
    ex = defaultdict(lambda: {"count": 0, "pnl": 0.0})
    for t in trades:
        r = t["exit_reason"] or "UNKNOWN"
        ex[r]["count"] += 1
        ex[r]["pnl"] += (t["net_pnl_usdt"] or 0.0)

    for reason, s in sorted(ex.items(), key=lambda kv: kv[1]["count"], reverse=True)[:10]:
        print(f"  {reason:<25} count={s['count']:<4} pnl={s['pnl']:<10.2f}")

    print("\nSymbols (top 15 pires par pnl):")
    sym = defaultdict(lambda: {"count": 0, "pnl": 0.0})
    for t in trades:
        k = t["symbol"] or "UNKNOWN"
        sym[k]["count"] += 1
        sym[k]["pnl"] += (t["net_pnl_usdt"] or 0.0)

    for symbol, s in sorted(sym.items(), key=lambda kv: kv[1]["pnl"])[:15]:
        print(f"  {symbol:<15} count={s['count']:<4} pnl={s['pnl']:<10.2f}")

    print("\nFiltres (pass/fail):")
    for col in ("atr_optimal_passed", "snr_passed", "breakout_passed", "wick_passed"):
        passed = [t for t in trades if t[col] is True]
        failed = [t for t in trades if t[col] is False]
        pnl_passed = sum((t["net_pnl_usdt"] or 0.0) for t in passed)
        pnl_failed = sum((t["net_pnl_usdt"] or 0.0) for t in failed)
        print(
            f"  {col:<20} passed={len(passed):<4} pnl={pnl_passed:<10.2f} "
            f"failed={len(failed):<4} pnl={pnl_failed:<10.2f}"
        )

    print("\nRSI buckets:")
    rsi_stats = defaultdict(lambda: {"count": 0, "pnl": 0.0})
    for t in trades:
        b = (t["direction"], rsi_bucket(t["direction"], t["entry_rsi_1m"]))
        rsi_stats[b]["count"] += 1
        rsi_stats[b]["pnl"] += (t["net_pnl_usdt"] or 0.0)

    for (direction, bucket), s in sorted(rsi_stats.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        print(f"  {direction:<5} rsi={bucket:<7} count={s['count']:<4} pnl={s['pnl']:<10.2f}")

    print("\nScore vs effective_min_score:")
    score_cat = defaultdict(lambda: {"count": 0, "pnl": 0.0})
    for t in trades:
        score = t["entry_score"]
        eff = t["entry_effective_min_score"]
        pnl = t["net_pnl_usdt"] or 0.0
        if score is None or eff is None:
            cat = "NULL"
        elif score < eff:
            cat = "score < eff_min"
        elif score < eff + 1.0:
            cat = "eff_min <= score < eff_min+1"
        else:
            cat = "score >= eff_min+1"
        score_cat[cat]["count"] += 1
        score_cat[cat]["pnl"] += pnl

    for cat, s in score_cat.items():
        print(f"  {cat:<30} count={s['count']:<4} pnl={s['pnl']:<10.2f}")

    print("\nATR% buckets (entry_atr_pct_used):")
    atr_stats = defaultdict(lambda: {"count": 0, "pnl": 0.0})
    for t in trades:
        b = atr_bucket(t["entry_atr_pct_used"])
        atr_stats[b]["count"] += 1
        atr_stats[b]["pnl"] += (t["net_pnl_usdt"] or 0.0)

    for bucket, s in sorted(atr_stats.items(), key=lambda kv: kv[0]):
        print(f"  atr={bucket:<9} count={s['count']:<4} pnl={s['pnl']:<10.2f}")

    print("\nADX buckets:")
    adx_stats = defaultdict(lambda: {"count": 0, "pnl": 0.0})
    for t in trades:
        b = adx_bucket(t["entry_adx_1m"])
        adx_stats[b]["count"] += 1
        adx_stats[b]["pnl"] += (t["net_pnl_usdt"] or 0.0)

    for bucket, s in sorted(adx_stats.items(), key=lambda kv: kv[0]):
        print(f"  adx={bucket:<5} count={s['count']:<4} pnl={s['pnl']:<10.2f}")

    print("\nVolume ratio buckets:")
    vr_stats = defaultdict(lambda: {"count": 0, "pnl": 0.0})
    for t in trades:
        b = vol_bucket(t["entry_volume_ratio_1m"])
        vr_stats[b]["count"] += 1
        vr_stats[b]["pnl"] += (t["net_pnl_usdt"] or 0.0)

    for bucket, s in sorted(vr_stats.items(), key=lambda kv: kv[0]):
        print(f"  vr={bucket:<7} count={s['count']:<4} pnl={s['pnl']:<10.2f}")

    recent_query = f"""
WITH recent AS (
    SELECT *
    FROM trades
    WHERE is_live_trade = true
      AND exit_price IS NOT NULL
      AND net_pnl_usdt IS NOT NULL
    ORDER BY timestamp_entry DESC
    LIMIT {args.recent_pool}
)
SELECT
    symbol,
    COALESCE(entry_market_regime, 'UNKNOWN') AS regime,
    direction,
    entry_rsi_1m,
    entry_score,
    entry_effective_min_score,
    net_pnl_usdt
FROM recent
"""

    recent_rows = run_sql(recent_query)
    recent_trades = []
    for r in recent_rows:
        if len(r) < 7:
            continue
        recent_trades.append(
            {
                "symbol": r[0],
                "regime": r[1],
                "direction": r[2],
                "rsi": to_float(r[3]),
                "score": to_float(r[4]),
                "eff_min_score": to_float(r[5]),
                "pnl": to_float(r[6]) or 0.0,
            }
        )

    base_thr = load_regime_rsi_thresholds()
    scenarios = []
    scenarios.append(("CURRENT", dict(base_thr)))

    thr_mild = dict(base_thr)
    thr_mild["VOLATILE"] = (68.0, 32.0)
    scenarios.append(("VOLATILE_TIGHT", thr_mild))

    thr_strict_unknown = dict(base_thr)
    thr_strict_unknown["UNKNOWN"] = (60.0, 40.0)
    scenarios.append(("UNKNOWN_STRICT", thr_strict_unknown))

    thr_global_70_30 = {k: (70.0, 30.0) for k in base_thr.keys()}
    scenarios.append(("GLOBAL_70_30", thr_global_70_30))

    thr_global_75_25 = {k: (75.0, 25.0) for k in base_thr.keys()}
    scenarios.append(("GLOBAL_75_25", thr_global_75_25))

    thr_global_80_20 = {k: (80.0, 20.0) for k in base_thr.keys()}
    scenarios.append(("GLOBAL_80_20", thr_global_80_20))

    pool_total = len(recent_trades)
    pool_with_rsi = sum(1 for t in recent_trades if t.get("rsi") is not None)
    pool_pnl = sum((t.get("pnl") or 0.0) for t in recent_trades)

    print("\nRSI what-if sur le pool recent (approx volume impact):")
    print(
        f"  pool_total={pool_total} pool_with_rsi={pool_with_rsi} (sur {args.recent_pool} trades recents) "
        f"pool_pnl={pool_pnl:.2f}"
    )
    for name, thr in scenarios:
        kept = 0
        blocked = 0
        pnl_kept = 0.0
        pnl_blocked = 0.0

        for t in recent_trades:
            rsi = t.get("rsi")
            if rsi is None:
                continue
            regime = t.get("regime") or "UNKNOWN"
            direction = t.get("direction")
            pnl = t.get("pnl") or 0.0

            long_max, short_min = thr.get(regime, thr.get("UNKNOWN", (65.0, 35.0)))
            ok = True
            if direction == "LONG":
                ok = rsi <= long_max
            elif direction == "SHORT":
                ok = rsi >= short_min

            if ok:
                kept += 1
                pnl_kept += pnl
            else:
                blocked += 1
                pnl_blocked += pnl

        total = kept + blocked
        pct = (100.0 * kept / total) if total else 0.0
        print(
            f"  {name:<14} kept={kept:<4} blocked={blocked:<4} kept%={pct:>5.1f} "
            f"pnl_kept={pnl_kept:>8.2f} pnl_blocked={pnl_blocked:>8.2f}"
        )

    print("\nScore what-if sur le pool recent (simule min_score plus strict):")
    score_scenarios = [
        ("MARGIN>=0.0", 0.0),
        ("MARGIN>=0.5", 0.5),
        ("MARGIN>=1.0", 1.0),
    ]
    for name, delta in score_scenarios:
        kept = 0
        removed = 0
        pnl_kept = 0.0
        pnl_removed = 0.0
        null = 0
        for t in recent_trades:
            score = t.get("score")
            eff = t.get("eff_min_score")
            pnl = t.get("pnl") or 0.0
            if score is None or eff is None:
                null += 1
                continue
            if score >= eff + delta:
                kept += 1
                pnl_kept += pnl
            else:
                removed += 1
                pnl_removed += pnl

        total = kept + removed
        kept_pct = 100.0 * kept / total if total else 0.0
        print(
            f"  {name:<12} kept={kept:<4} removed={removed:<4} kept%={kept_pct:>5.1f} "
            f"pnl_kept={pnl_kept:>8.2f} pnl_removed={pnl_removed:>8.2f} null={null}"
        )

    print("\nSymbols sur le pool recent:")
    sym_stats = defaultdict(lambda: {"count": 0, "pnl": 0.0})
    for t in recent_trades:
        s = t.get("symbol") or "UNKNOWN"
        sym_stats[s]["count"] += 1
        sym_stats[s]["pnl"] += (t.get("pnl") or 0.0)

    print("  Top 10 par count:")
    for symbol, s in sorted(sym_stats.items(), key=lambda kv: kv[1]["count"], reverse=True)[:10]:
        pct = 100.0 * s["count"] / pool_total if pool_total else 0.0
        print(f"    {symbol:<18} count={s['count']:<4} ({pct:>5.1f}%) pnl={s['pnl']:<10.2f}")

    print("  Pires 15 par pnl:")
    for symbol, s in sorted(sym_stats.items(), key=lambda kv: kv[1]["pnl"])[:15]:
        pct = 100.0 * s["count"] / pool_total if pool_total else 0.0
        print(f"    {symbol:<18} count={s['count']:<4} ({pct:>5.1f}%) pnl={s['pnl']:<10.2f}")

    exclusions = []
    exclusions.append(("EXCL_ZEC", {"ZEC/USDT:USDT"}))
    exclusions.append(("EXCL_ZEC_SUI", {"ZEC/USDT:USDT", "SUI/USDT:USDT"}))
    exclusions.append(
        (
            "EXCL_TOP4_WORST",
            {
                "ZEC/USDT:USDT",
                "SUI/USDT:USDT",
                "SOL/USDT:USDT",
                "JELLYJELLY/USDT:USDT",
            },
        )
    )

    print("\nWhat-if exclusion symboles (config excluded_symbols):")
    for name, excl in exclusions:
        kept = 0
        removed = 0
        pnl_kept = 0.0
        pnl_removed = 0.0
        for t in recent_trades:
            symbol = t.get("symbol")
            pnl = t.get("pnl") or 0.0
            if symbol in excl:
                removed += 1
                pnl_removed += pnl
            else:
                kept += 1
                pnl_kept += pnl

        total = kept + removed
        kept_pct = 100.0 * kept / total if total else 0.0
        print(
            f"  {name:<16} kept={kept:<4} removed={removed:<4} kept%={kept_pct:>5.1f} "
            f"pnl_kept={pnl_kept:>8.2f} pnl_removed={pnl_removed:>8.2f}"
        )

    # === ANALYSE SIZING ===
    print("\n" + "=" * 70)
    print("ANALYSE SIZING (size_usdt)")
    print("=" * 70)

    sizing_query = f"""
    WITH recent AS (
        SELECT size_usdt, net_pnl_usdt
        FROM trades
        WHERE is_live_trade = true AND exit_price IS NOT NULL AND size_usdt IS NOT NULL
        ORDER BY timestamp_entry DESC
        LIMIT {args.recent_pool}
    )
    SELECT
        ROUND(AVG(size_usdt)::numeric, 2) AS avg_size,
        ROUND(STDDEV(size_usdt)::numeric, 2) AS std_size,
        ROUND(MIN(size_usdt)::numeric, 2) AS min_size,
        ROUND(MAX(size_usdt)::numeric, 2) AS max_size,
        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY size_usdt)::numeric, 2) AS median,
        ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY size_usdt)::numeric, 2) AS p95,
        ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY size_usdt)::numeric, 2) AS p99
    FROM recent;
    """
    sizing_rows = run_sql(sizing_query)
    if sizing_rows:
        parts = sizing_rows[0]  # Already a list
        if len(parts) >= 7:
            print(f"  Moyenne: {parts[0]} USDT")
            print(f"  Ecart-type: {parts[1]} USDT")
            print(f"  Min: {parts[2]} USDT | Max: {parts[3]} USDT")
            print(f"  Mediane: {parts[4]} USDT | P95: {parts[5]} USDT | P99: {parts[6]} USDT")

    # Sizing buckets
    bucket_query = f"""
    WITH recent AS (
        SELECT size_usdt, net_pnl_usdt
        FROM trades
        WHERE is_live_trade = true AND exit_price IS NOT NULL AND size_usdt IS NOT NULL
        ORDER BY timestamp_entry DESC
        LIMIT {args.recent_pool}
    )
    SELECT
        CASE
            WHEN size_usdt < 8 THEN '<8'
            WHEN size_usdt < 10 THEN '8-10'
            WHEN size_usdt < 12 THEN '10-12'
            WHEN size_usdt < 15 THEN '12-15'
            WHEN size_usdt < 20 THEN '15-20'
            WHEN size_usdt < 30 THEN '20-30'
            ELSE '>=30'
        END AS bucket,
        COUNT(*) AS cnt,
        ROUND(SUM(net_pnl_usdt)::numeric, 2) AS pnl,
        ROUND(AVG(net_pnl_usdt)::numeric, 4) AS avg_pnl
    FROM recent
    GROUP BY bucket
    ORDER BY MIN(size_usdt);
    """
    bucket_rows = run_sql(bucket_query)
    print("\nDistribution par bucket de taille:")
    print(f"  {'bucket':8} {'count':>6} {'pnl':>10} {'avg_pnl':>10}")
    for parts in bucket_rows:
        if len(parts) >= 4:
            print(f"  {parts[0]:8} {parts[1]:>6} {parts[2]:>10} {parts[3]:>10}")

    # What-if cap sizing
    cap_query = f"""
    WITH recent AS (
        SELECT size_usdt, net_pnl_usdt
        FROM trades
        WHERE is_live_trade = true AND exit_price IS NOT NULL AND size_usdt IS NOT NULL
        ORDER BY timestamp_entry DESC
        LIMIT {args.recent_pool}
    )
    SELECT
        'CAP_15' AS scenario,
        COUNT(*) FILTER (WHERE size_usdt <= 15) AS kept,
        COUNT(*) FILTER (WHERE size_usdt > 15) AS removed,
        ROUND(SUM(net_pnl_usdt) FILTER (WHERE size_usdt <= 15)::numeric, 2) AS pnl_kept,
        ROUND(SUM(net_pnl_usdt) FILTER (WHERE size_usdt > 15)::numeric, 2) AS pnl_removed
    FROM recent
    UNION ALL
    SELECT 'CAP_20', COUNT(*) FILTER (WHERE size_usdt <= 20), COUNT(*) FILTER (WHERE size_usdt > 20),
        ROUND(SUM(net_pnl_usdt) FILTER (WHERE size_usdt <= 20)::numeric, 2),
        ROUND(SUM(net_pnl_usdt) FILTER (WHERE size_usdt > 20)::numeric, 2)
    FROM recent
    UNION ALL
    SELECT 'CAP_25', COUNT(*) FILTER (WHERE size_usdt <= 25), COUNT(*) FILTER (WHERE size_usdt > 25),
        ROUND(SUM(net_pnl_usdt) FILTER (WHERE size_usdt <= 25)::numeric, 2),
        ROUND(SUM(net_pnl_usdt) FILTER (WHERE size_usdt > 25)::numeric, 2)
    FROM recent;
    """
    cap_rows = run_sql(cap_query)
    print("\nWhat-if cap sizing:")
    print(f"  {'scenario':10} {'kept':>6} {'removed':>7} {'pnl_kept':>10} {'pnl_removed':>12}")
    for parts in cap_rows:
        if len(parts) >= 5:
            print(f"  {parts[0]:10} {parts[1]:>6} {parts[2]:>7} {parts[3]:>10} {parts[4]:>12}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
