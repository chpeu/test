from __future__ import annotations

import argparse
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import psycopg2
import requests
from psycopg2.extras import RealDictCursor
from urllib.parse import quote_plus


def _num(v: Any) -> Optional[float]:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return float(v)
    except Exception:
        return None


def _str(v: Any) -> Optional[str]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    return s if s else None


def _to_utc_ts(v: Any) -> Optional[float]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        if v > 1e12:
            return float(v) / 1000.0
        if v > 1e10:
            return float(v)
        return float(v)
    if isinstance(v, datetime):
        dt = v
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    s = str(v).strip()
    if not s:
        return None
    try:
        dt = pd.to_datetime(s, utc=True, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.to_pydatetime().timestamp()
    except Exception:
        return None


def _clean_text(s: Any) -> Optional[str]:
    v = _str(s)
    if not v:
        return None
    v = v.replace("\u200e", "").replace("\u200f", "")
    v = v.replace("\xa0", " ")
    return v.strip()


def _normalize_symbol(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = s.strip().upper()
    s = _clean_text(s) or s
    s = s.replace("\n", " ").replace("\r", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s*(PERPÉTUEL|PERPETUEL|PERPETUAL|PERP)\s*$", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"\s+", "", s)
    if ":" in s:
        s = s.split(":", 1)[0]
    s = s.replace("/", "_").replace("-", "_")
    if s.endswith("USDT") and not s.endswith("_USDT"):
        s = s[: -4] + "_USDT"
    s = re.sub(r"_+", "_", s)
    return s


def _normalize_side_to_direction(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    v = s.strip().upper()
    mapping = {
        "LONG": "LONG",
        "SHORT": "SHORT",
        "BUY": "LONG",
        "SELL": "SHORT",
        "OPEN_LONG": "LONG",
        "OPEN_SHORT": "SHORT",
        "ACHETER": "LONG",
        "VENDRE": "SHORT",
    }
    return mapping.get(v, v)


def _get_reliable_size_usdt(trade: Dict[str, Any]) -> float:
    def n(x: Any) -> float:
        try:
            if x is None:
                return 0.0
            return float(x)
        except Exception:
            return 0.0

    initial_size = n(trade.get("size_initial_usdt"))
    executed_size = n(
        trade.get("size_executed_usdt")
        or trade.get("size")
        or trade.get("filled_size_usdt")
        or trade.get("position_size_usdt")
        or trade.get("size_usdt")
    )

    pnl_usdt = n(trade.get("net_pnl_usdt") or trade.get("pnl_usdt"))
    pnl_pct = n(trade.get("net_pnl_pct") or trade.get("pnl_percent") or trade.get("pnl_pct"))

    calculated_size = 0.0
    if pnl_pct != 0 and abs(pnl_pct) > 0.001:
        calculated_size = abs(pnl_usdt / (pnl_pct / 100.0))

    size = executed_size

    if initial_size > 0 and executed_size > 3 * initial_size:
        size = calculated_size if calculated_size > 0 else initial_size
    elif calculated_size > 0 and executed_size > 0 and abs(calculated_size - executed_size) > executed_size * 0.5:
        size = calculated_size
    elif size <= 0 and initial_size > 0:
        size = initial_size
    elif size <= 0 and calculated_size > 0:
        size = calculated_size

    return float(size) if size and size > 0 else 0.0


def load_frontend_trade_history(state_url: str) -> List[Dict[str, Any]]:
    r = requests.get(state_url, timeout=15)
    r.raise_for_status()
    payload = r.json()
    for key in ("trade_history", "trades", "tradeHistory"):
        v = payload.get(key)
        if isinstance(v, list):
            return [t for t in v if isinstance(t, dict)]
    return []


def load_db_trades(conn) -> List[Dict[str, Any]]:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        SELECT
            t.id::text AS id,
            t.symbol,
            t.direction,
            t.timestamp_entry,
            t.timestamp_exit,
            t.entry_price,
            t.exit_price,
            t.size_usdt,
            t.net_pnl_usdt,
            t.net_pnl_pct,
            t.fees_usdt,
            t.exit_reason
        FROM trades t
        WHERE t.timestamp_exit IS NOT NULL
        ORDER BY t.timestamp_exit DESC
        LIMIT 5000
        """
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows


def detect_time_offset_seconds(
    df: pd.DataFrame,
    db: List[Dict[str, Any]],
    max_abs_offset_seconds: int = 86400,
    bin_seconds: int = 60,
) -> Tuple[int, Dict[str, Any]]:
    deltas: List[float] = []
    for _, row in df.iterrows():
        sym = row.get("_symbol")
        direction = row.get("_direction")
        close_ts = row.get("_close_ts")
        if sym is None or direction is None or close_ts is None:
            continue
        cands = [t for t in db if t.get("_symbol") == sym and t.get("_direction") == direction and t.get("_exit_ts") is not None]
        if not cands:
            continue
        best = min(cands, key=lambda t: abs(float(t["_exit_ts"]) - float(close_ts)))
        delta = float(best["_exit_ts"]) - float(close_ts)
        if abs(delta) <= float(max_abs_offset_seconds):
            deltas.append(delta)

    if not deltas:
        return 0, {"total": 0, "best_bin_count": 0, "best_bin_seconds": None}

    bins: Dict[int, List[float]] = {}
    for d in deltas:
        b = int(round(d / float(bin_seconds))) * int(bin_seconds)
        bins.setdefault(b, []).append(d)

    best_bin = max(bins.items(), key=lambda kv: len(kv[1]))[0]
    best_vals = bins[best_bin]
    best_vals_sorted = sorted(best_vals)
    mid = len(best_vals_sorted) // 2
    if len(best_vals_sorted) % 2 == 1:
        offset = best_vals_sorted[mid]
    else:
        offset = 0.5 * (best_vals_sorted[mid - 1] + best_vals_sorted[mid])

    return int(round(offset)), {"total": len(deltas), "best_bin_count": len(best_vals), "best_bin_seconds": best_bin}


def reconcile(frontend_trades: List[Dict[str, Any]], db_trades: List[Dict[str, Any]], args) -> None:
    rows = []
    for t in frontend_trades:
        sym = _normalize_symbol(_str(t.get("symbol")))
        direction = _normalize_side_to_direction(_str(t.get("direction")))
        close_ts = _to_utc_ts(t.get("closed_at") or t.get("timestamp_exit") or t.get("timestamp") or t.get("closedAt"))
        open_ts = _to_utc_ts(t.get("opened_at") or t.get("timestamp_entry") or t.get("openedAt"))
        pnl_usdt = _num(t.get("net_pnl_usdt") or t.get("pnl_usdt"))
        size_usdt = _get_reliable_size_usdt(t)
        exit_reason = _str(t.get("exit_reason") or t.get("reason") or t.get("close_reason"))

        if not sym or not direction or close_ts is None:
            continue

        rows.append(
            {
                "_symbol": sym,
                "_direction": direction,
                "_close_ts": close_ts,
                "_open_ts": open_ts,
                "_pnl_usdt": pnl_usdt,
                "_size_usdt": float(size_usdt) if size_usdt is not None else None,
                "_exit_reason": exit_reason,
                "raw": t,
            }
        )

    df2 = pd.DataFrame(rows)

    db = []
    for t in db_trades:
        db.append(
            {
                **t,
                "_symbol": _normalize_symbol(_str(t.get("symbol"))),
                "_direction": _normalize_side_to_direction(_str(t.get("direction"))),
                "_exit_ts": _to_utc_ts(t.get("timestamp_exit")),
                "_entry_ts": _to_utc_ts(t.get("timestamp_entry")),
                "_size_usdt": _num(t.get("size_usdt")),
                "_pnl_usdt": _num(t.get("net_pnl_usdt")),
            }
        )

    if args.auto_time_offset:
        offset_s, stats = detect_time_offset_seconds(
            df2,
            db,
            max_abs_offset_seconds=args.auto_time_offset_max_seconds,
            bin_seconds=args.auto_time_offset_bin_seconds,
        )
        args.time_offset_seconds = offset_s
        print(
            "\nAuto time offset detected (seconds):",
            int(offset_s),
            "| samples:",
            int(stats.get("total", 0)),
            "| best_bin_count:",
            int(stats.get("best_bin_count", 0)),
            "| best_bin_seconds:",
            stats.get("best_bin_seconds"),
        )

    offset_s = int(args.time_offset_seconds or 0)
    if offset_s and not df2.empty:
        df2["_close_ts"] = df2["_close_ts"].map(lambda v: (v + offset_s) if v is not None and not (isinstance(v, float) and pd.isna(v)) else v)
        df2["_open_ts"] = df2["_open_ts"].map(lambda v: (v + offset_s) if v is not None and not (isinstance(v, float) and pd.isna(v)) else v)

    time_tol = args.time_tolerance_seconds

    matches = []
    used_db: set[str] = set()

    for idx, row in df2.iterrows():
        sym = row.get("_symbol")
        direction = row.get("_direction")
        close_ts = row.get("_close_ts")
        open_ts = row.get("_open_ts")

        candidates = []
        for t in db:
            if t["id"] in used_db:
                continue
            if t.get("_symbol") != sym:
                continue
            if direction and t.get("_direction") and t.get("_direction") != direction:
                continue

            exit_ts = t.get("_exit_ts")
            if close_ts is not None and exit_ts is not None:
                dt = abs(exit_ts - close_ts)
                if dt > time_tol:
                    continue
            elif open_ts is not None and t.get("_entry_ts") is not None:
                dt = abs(t["_entry_ts"] - open_ts)
                if dt > time_tol:
                    continue
            else:
                continue

            size_diff_ratio = None
            if row.get("_size_usdt") is not None and t.get("_size_usdt") is not None and t.get("_size_usdt"):
                size_diff_ratio = abs(float(row["_size_usdt"]) - float(t["_size_usdt"])) / max(float(t["_size_usdt"]), 1e-9)

            score = float(dt) + float((size_diff_ratio or 0.0) * 1000.0)
            candidates.append((score, float(dt), size_diff_ratio, t))

        if not candidates:
            continue

        candidates.sort(key=lambda x: x[0])
        score, dt, size_diff_ratio, best = candidates[0]
        used_db.add(best["id"])

        pnl_diff_usdt = None
        if row.get("_pnl_usdt") is not None and best.get("_pnl_usdt") is not None:
            pnl_diff_usdt = float(row["_pnl_usdt"]) - float(best["_pnl_usdt"])

        matches.append(
            {
                "frontend_idx": int(idx),
                "db_id": best["id"],
                "score": float(score),
                "time_diff_s": float(dt),
                "size_diff_ratio": size_diff_ratio,
                "pnl_diff_usdt": pnl_diff_usdt,
                "frontend_symbol": sym,
                "frontend_direction": direction,
                "frontend_exit_reason": row.get("_exit_reason"),
                "db_exit_reason": best.get("exit_reason"),
            }
        )

    matched_df = pd.DataFrame(matches)

    print("=" * 110)
    print("Reconcile Frontend trade_history ↔ DB")
    print("frontend_rows:", len(df2))
    print("db_rows_loaded:", len(db))
    print("matched:", len(matched_df))

    if matched_df.empty:
        print("⚠️ Aucun match trouvé. Augmente --time-tolerance-seconds ou vérifie les timestamps.")
        return

    exch_pnl = df2.loc[matched_df["frontend_idx"].values, "_pnl_usdt"].reset_index(drop=True)
    db_by_id = {t["id"]: t for t in db}
    db_pnl = []
    for _, r in matched_df.iterrows():
        t = db_by_id.get(r["db_id"])
        db_pnl.append(t.get("_pnl_usdt") if t else None)
    db_pnl_s = pd.Series(db_pnl)

    if exch_pnl.notna().sum() >= 5 and db_pnl_s.notna().sum() >= 5:
        corr = pd.concat([exch_pnl, db_pnl_s], axis=1).corr().iloc[0, 1]
        print("\nPnL correlation (frontend vs db):", float(corr) if corr == corr else None)
        diffs = (exch_pnl - db_pnl_s).dropna()
        if not diffs.empty:
            print("PnL diff stats (USDT):")
            print(" mean", float(diffs.mean()), "median", float(diffs.median()), "p95_abs", float(diffs.abs().quantile(0.95)))

    pnl_thr = args.pnl_diff_usdt_threshold
    size_thr = args.size_diff_ratio_threshold
    time_thr = args.time_diff_seconds_threshold

    def _abs(v: Any) -> Optional[float]:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return abs(float(v))

    flagged = matched_df.copy()
    flagged["abs_pnl_diff_usdt"] = flagged["pnl_diff_usdt"].map(_abs)
    flagged["abs_size_diff_ratio"] = flagged["size_diff_ratio"].map(_abs)

    problems = flagged[
        (flagged["time_diff_s"] >= time_thr)
        | (flagged["abs_pnl_diff_usdt"].fillna(0) >= pnl_thr)
        | (flagged["abs_size_diff_ratio"].fillna(0) >= size_thr)
    ].sort_values(by=["abs_pnl_diff_usdt", "abs_size_diff_ratio", "time_diff_s"], ascending=False)

    print("\nThresholds:")
    print(" time_diff_s >=", time_thr)
    print(" abs_pnl_diff_usdt >=", pnl_thr)
    print(" abs_size_diff_ratio >=", size_thr)

    print("\nTop mismatches (up to 30):")
    cols = [
        "frontend_idx",
        "db_id",
        "frontend_symbol",
        "frontend_direction",
        "time_diff_s",
        "pnl_diff_usdt",
        "size_diff_ratio",
        "frontend_exit_reason",
        "db_exit_reason",
    ]
    print(problems[cols].head(30).to_string(index=False))

    if args.output_csv:
        problems.to_csv(args.output_csv, index=False)
        print("\nSaved:", args.output_csv)

    print("=" * 110)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-url", default="http://127.0.0.1:3000/api/state")

    ap.add_argument("--time-tolerance-seconds", type=int, default=300)
    ap.add_argument("--time-diff-seconds-threshold", type=int, default=60)
    ap.add_argument("--pnl-diff-usdt-threshold", type=float, default=0.20)
    ap.add_argument("--size-diff-ratio-threshold", type=float, default=0.05)

    ap.add_argument("--time-offset-seconds", type=int, default=0)
    ap.add_argument("--auto-time-offset", action="store_true")
    ap.add_argument("--auto-time-offset-max-seconds", type=int, default=86400)
    ap.add_argument("--auto-time-offset-bin-seconds", type=int, default=60)

    ap.add_argument("--output-csv", default="verification/reconcile_frontend_vs_db.csv")

    args = ap.parse_args()

    frontend_trades = load_frontend_trade_history(args.state_url)

    password = os.environ.get("POSTGRES_PASSWORD") or "@Cmtr1di12345"
    password = quote_plus(password)
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    dbname = os.environ.get("POSTGRES_DB", "trade_cursor_ml")
    user = os.environ.get("POSTGRES_USER", "postgres")

    conn = psycopg2.connect(f"postgresql://{user}:{password}@{host}:{port}/{dbname}")
    try:
        db_trades = load_db_trades(conn)
    finally:
        conn.close()

    reconcile(frontend_trades, db_trades, args)


if __name__ == "__main__":
    main()
