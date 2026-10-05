import argparse
import os
import re
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
TF_RE = re.compile(r"\((1m|5m)\)")


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
            import json

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


def infer_timeframe(setup_reason: str | None) -> str | None:
    if not setup_reason:
        return None
    m = TF_RE.search(setup_reason)
    if not m:
        return None
    return m.group(1)


def rsi_violation(direction: str, rsi: float | None, long_max: float | None, short_min: float | None) -> float | None:
    if rsi is None:
        return None

    d = (direction or "").upper()
    if d == "LONG" and long_max is not None:
        return rsi - long_max
    if d == "SHORT" and short_min is not None:
        return short_min - rsi
    return None


def passes_rsi_filter(direction: str, rsi: float | None, long_max: float | None, short_min: float | None) -> bool | None:
    v = rsi_violation(direction=direction, rsi=rsi, long_max=long_max, short_min=short_min)
    if v is None:
        return None
    return v <= 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recent-pool", type=int, default=5000)
    parser.add_argument("--only-closed", action="store_true", default=True)
    parser.add_argument("--max-print", type=int, default=50)
    args = parser.parse_args()

    regime_thresholds = load_regime_rsi_thresholds()

    closed_clause = "AND exit_price IS NOT NULL AND net_pnl_usdt IS NOT NULL" if args.only_closed else ""

    query = f"""
WITH recent AS (
    SELECT *
    FROM trades
    WHERE is_live_trade = true
      {closed_clause}
    ORDER BY timestamp_entry DESC
    LIMIT {args.recent_pool}
)
SELECT
    t.id,
    t.timestamp_entry,
    t.symbol,
    t.direction,
    COALESCE(t.entry_market_regime, 'UNKNOWN') AS regime,
    t.entry_rsi_1m,
    t.entry_rsi_5m,
    t.config_rsi_long_max,
    t.config_rsi_short_min,
    t.net_pnl_usdt,
    COALESCE(t.exit_reason, 'UNKNOWN') AS exit_reason,
    o.setup_reason
FROM recent t
LEFT JOIN opportunities o ON o.id = t.opportunity_id
WHERE t.config_rsi_filter_enabled = true
  AND t.entry_rsi_1m IS NOT NULL
  AND (
        (t.direction = 'LONG' AND t.entry_rsi_1m > t.config_rsi_long_max)
     OR (t.direction = 'SHORT' AND t.entry_rsi_1m < t.config_rsi_short_min)
  )
ORDER BY t.timestamp_entry DESC;
"""

    rows = run_sql(query)
    cols = [
        "id",
        "timestamp_entry",
        "symbol",
        "direction",
        "regime",
        "entry_rsi_1m",
        "entry_rsi_5m",
        "config_rsi_long_max",
        "config_rsi_short_min",
        "net_pnl_usdt",
        "exit_reason",
        "setup_reason",
    ]

    trades = []
    for r in rows:
        t = {}
        for i, c in enumerate(cols):
            v = r[i] if i < len(r) else None
            if c in (
                "entry_rsi_1m",
                "entry_rsi_5m",
                "config_rsi_long_max",
                "config_rsi_short_min",
                "net_pnl_usdt",
            ):
                t[c] = to_float(v)
            else:
                t[c] = v

        t["timeframe_inferred"] = infer_timeframe(t.get("setup_reason")) or "UNKNOWN"
        t["viol_1m"] = rsi_violation(
            direction=t.get("direction") or "",
            rsi=t.get("entry_rsi_1m"),
            long_max=t.get("config_rsi_long_max"),
            short_min=t.get("config_rsi_short_min"),
        )
        t["viol_5m"] = rsi_violation(
            direction=t.get("direction") or "",
            rsi=t.get("entry_rsi_5m"),
            long_max=t.get("config_rsi_long_max"),
            short_min=t.get("config_rsi_short_min"),
        )
        t["pass_5m"] = passes_rsi_filter(
            direction=t.get("direction") or "",
            rsi=t.get("entry_rsi_5m"),
            long_max=t.get("config_rsi_long_max"),
            short_min=t.get("config_rsi_short_min"),
        )

        reg = (t.get("regime") or "UNKNOWN").upper()
        reg_long_max, reg_short_min = regime_thresholds.get(reg, regime_thresholds["UNKNOWN"])
        t["regime_rsi_long_max"] = reg_long_max
        t["regime_rsi_short_min"] = reg_short_min
        t["viol_1m_regime"] = rsi_violation(
            direction=t.get("direction") or "",
            rsi=t.get("entry_rsi_1m"),
            long_max=reg_long_max,
            short_min=reg_short_min,
        )
        t["viol_5m_regime"] = rsi_violation(
            direction=t.get("direction") or "",
            rsi=t.get("entry_rsi_5m"),
            long_max=reg_long_max,
            short_min=reg_short_min,
        )
        t["pass_1m_regime"] = passes_rsi_filter(
            direction=t.get("direction") or "",
            rsi=t.get("entry_rsi_1m"),
            long_max=reg_long_max,
            short_min=reg_short_min,
        )
        t["pass_5m_regime"] = passes_rsi_filter(
            direction=t.get("direction") or "",
            rsi=t.get("entry_rsi_5m"),
            long_max=reg_long_max,
            short_min=reg_short_min,
        )

        trades.append(t)

    print("=" * 80)
    print("DIAGNOSTIC RSI FINAL FILTER: trades où entry_rsi_1m viole les seuils config")
    print("=" * 80)
    print(f"Pool analysé (plus récents): {args.recent_pool}")
    print(f"Violations trouvées: {len(trades)}")

    if not trades:
        return 0

    by_tf = defaultdict(lambda: {"count": 0, "pnl": 0.0})
    by_regime = defaultdict(lambda: {"count": 0, "pnl": 0.0})
    by_tf_and_pass5m = defaultdict(lambda: {"count": 0, "pnl": 0.0})
    by_regime_and_pass_any = defaultdict(lambda: {"count": 0, "pnl": 0.0})

    for t in trades:
        pnl = t.get("net_pnl_usdt") or 0.0
        tf = t.get("timeframe_inferred") or "UNKNOWN"
        reg = t.get("regime") or "UNKNOWN"
        by_tf[tf]["count"] += 1
        by_tf[tf]["pnl"] += pnl
        by_regime[reg]["count"] += 1
        by_regime[reg]["pnl"] += pnl

        pass5m = t.get("pass_5m")
        pass5m_label = "5m_pass" if pass5m is True else ("5m_fail" if pass5m is False else "5m_null")
        by_tf_and_pass5m[(tf, pass5m_label)]["count"] += 1
        by_tf_and_pass5m[(tf, pass5m_label)]["pnl"] += pnl

        pass_any_regime = (t.get("pass_1m_regime") is True) or (t.get("pass_5m_regime") is True)
        pass_any_label = "regime_any_pass" if pass_any_regime else "regime_both_fail"
        by_regime_and_pass_any[(reg, pass_any_label)]["count"] += 1
        by_regime_and_pass_any[(reg, pass_any_label)]["pnl"] += pnl

    print("\nRépartition par timeframe (inféré via opportunities.setup_reason):")
    for tf, s in sorted(by_tf.items(), key=lambda kv: kv[1]["count"], reverse=True):
        avg = s["pnl"] / s["count"] if s["count"] else 0.0
        print(f"  {tf:<7} count={s['count']:<4} pnl={s['pnl']:<10.2f} avg={avg:<8.2f}")

    print("\nRépartition par régime:")
    for reg, s in sorted(by_regime.items(), key=lambda kv: kv[1]["count"], reverse=True):
        avg = s["pnl"] / s["count"] if s["count"] else 0.0
        print(f"  {reg:<10} count={s['count']:<4} pnl={s['pnl']:<10.2f} avg={avg:<8.2f}")

    print("\nTimeframe vs est-ce que entry_rsi_5m aurait PASSÉ le filtre:")
    for (tf, label), s in sorted(by_tf_and_pass5m.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        avg = s["pnl"] / s["count"] if s["count"] else 0.0
        print(f"  {tf:<7} {label:<7} count={s['count']:<4} pnl={s['pnl']:<10.2f} avg={avg:<8.2f}")

    print("\nRégime vs est-ce que (RSI 1m OU RSI 5m) passe les seuils du régime:")
    for (reg, label), s in sorted(by_regime_and_pass_any.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        avg = s["pnl"] / s["count"] if s["count"] else 0.0
        print(f"  {reg:<10} {label:<16} count={s['count']:<4} pnl={s['pnl']:<10.2f} avg={avg:<8.2f}")

    print("\nDétails (max-print):")
    for t in trades[: args.max_print]:
        print(
            "  "
            f"{t.get('timestamp_entry')} "
            f"id={t.get('id')} "
            f"{t.get('symbol')} "
            f"{t.get('direction')} "
            f"reg={t.get('regime')} "
            f"tf={t.get('timeframe_inferred')} "
            f"rsi1m={t.get('entry_rsi_1m')} rsi5m={t.get('entry_rsi_5m')} "
            f"thrL={t.get('config_rsi_long_max')} thrS={t.get('config_rsi_short_min')} "
            f"viol1m={t.get('viol_1m')} viol5m={t.get('viol_5m')} "
            f"5m_pass={t.get('pass_5m')} "
            f"regThrL={t.get('regime_rsi_long_max')} regThrS={t.get('regime_rsi_short_min')} "
            f"reg_pass_1m={t.get('pass_1m_regime')} reg_pass_5m={t.get('pass_5m_regime')} "
            f"pnl={t.get('net_pnl_usdt')} "
            f"reason={t.get('exit_reason')}"
        )

    if len(trades) > args.max_print:
        print(f"\n... {len(trades) - args.max_print} autres trades non affichés")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
