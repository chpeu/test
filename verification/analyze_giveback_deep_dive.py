"""Analyse détaillée du giveback (gestion/exits) sur les trades affichés dans le frontend.

- Source des trades: /api/state (instance en cours)
- Enrichissement DB: trades + trade_atr_metrics

Sorties:
- buckets de max_pnl_reached (distribution + giveback rate)
- giveback rate par exit_reason
- giveback rate par trailing_activated / be_triggered (si colonnes dispo)
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import psycopg2
import requests
from psycopg2.extras import RealDictCursor
from urllib.parse import quote_plus

API_STATE_URL = "http://127.0.0.1:3000/api/state"


def _num(v: Any) -> float:
    try:
        if v is None:
            return 0.0
        return float(v)
    except Exception:
        return 0.0


def _get_trade_id(t: Dict[str, Any]) -> Optional[str]:
    for k in ("id", "trade_id", "closure_id"):
        v = t.get(k)
        if v:
            return str(v)
    return None


def _looks_like_uuid(s: str) -> bool:
    # Quick heuristic (uuid string length usually 36 with hyphens)
    return isinstance(s, str) and len(s) >= 32


def fetch_trade_ids() -> List[str]:
    payload = requests.get(API_STATE_URL, timeout=10).json()
    trades = payload.get("trade_history") or payload.get("trades") or []
    ids: List[str] = []
    for t in trades:
        if not isinstance(t, dict):
            continue
        tid = _get_trade_id(t)
        if tid and _looks_like_uuid(tid):
            ids.append(tid)
    # dedup
    return list(dict.fromkeys(ids))


def get_available_columns(cur, table: str, wanted: List[str]) -> List[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
    """,
        (table,),
    )
    available = {r["column_name"] for r in cur.fetchall()}
    return [c for c in wanted if c in available]


def pick_first_available(cur, table: str, candidates: List[str]) -> Optional[str]:
    cols = get_available_columns(cur, table, candidates)
    return cols[0] if cols else None


@dataclass
class Bucket:
    name: str
    lo: Optional[float]
    hi: Optional[float]

    def match(self, v: float) -> bool:
        if self.lo is not None and v < self.lo:
            return False
        if self.hi is not None and v >= self.hi:
            return False
        return True


BUCKETS = [
    Bucket("<0", None, 0.0),
    Bucket("0-0.05", 0.0, 0.05),
    Bucket("0.05-0.10", 0.05, 0.10),
    Bucket("0.10-0.20", 0.10, 0.20),
    Bucket("0.20-0.40", 0.20, 0.40),
    Bucket(">=0.40", 0.40, None),
]


def pick_bucket(v: float) -> str:
    for b in BUCKETS:
        if b.match(v):
            return b.name
    return "unknown"


def main() -> None:
    trade_ids = fetch_trade_ids()
    print("=" * 110)
    print("🔍 Giveback deep-dive")
    print(f"API source: {API_STATE_URL}")
    print(f"Trades UUID dans payload: {len(trade_ids)}")

    if not trade_ids:
        print("⚠️ Aucun trade_id exploitable (UUID) dans payload. Stop.")
        return

    password = quote_plus("@Cmtr1di12345")
    conn = psycopg2.connect(f"postgresql://postgres:{password}@localhost:5432/trade_cursor_ml")
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Choisir colonnes disponibles
    reason_col = pick_first_available(cur, "trades", ["exit_reason", "close_reason", "reason"])
    atm_cols = get_available_columns(
        cur,
        "trade_atr_metrics",
        ["trade_id", "max_pnl_reached", "trailing_activated", "be_triggered", "mfe_pct", "mae_pct", "stagnation_detected"],
    )

    # Query
    # Note: t.id est uuid, on compare via ANY(text[]) avec cast
    select_atm = ", ".join([f"atm.{c}" for c in atm_cols if c != "trade_id"])
    if select_atm:
        select_atm = ", " + select_atm

    reason_expr = f"t.{reason_col}::text" if reason_col else "NULL"
    cur.execute(
        f"""
        SELECT
            t.id::text AS id,
            t.symbol,
            t.direction,
            {reason_expr} AS exit_reason,
            t.net_pnl_usdt,
            t.net_pnl_pct,
            t.size_usdt
            {select_atm}
        FROM trades t
        LEFT JOIN trade_atr_metrics atm
          ON t.id = atm.trade_id
        WHERE t.id::text = ANY(%s)
    """,
        (trade_ids,),
    )
    rows = [dict(r) for r in cur.fetchall()]

    cur.close()
    conn.close()

    print(f"Trades trouvés en DB: {len(rows)}")
    if not rows:
        return

    # Metrics
    giveback_rows = []
    by_bucket = defaultdict(list)
    by_reason = defaultdict(list)
    by_flag = defaultdict(list)

    for r in rows:
        net_u = _num(r.get("net_pnl_usdt"))
        reason = r.get("exit_reason") or "N/A"
        max_pnl = r.get("max_pnl_reached")
        max_pnl_v = None if max_pnl is None else _num(max_pnl)

        # Bucket only if we have max_pnl_reached
        if max_pnl_v is not None:
            b = pick_bucket(max_pnl_v)
            by_bucket[b].append(r)

        by_reason[str(reason)].append(r)

        # Flags
        for flag in ("trailing_activated", "be_triggered", "stagnation_detected"):
            if flag in r and r.get(flag) is not None:
                key = f"{flag}={bool(r.get(flag))}"
                by_flag[key].append(r)

        if max_pnl_v is not None and max_pnl_v > 0 and net_u < 0:
            giveback_rows.append(r)

    def summarize(group: List[Dict[str, Any]]) -> Tuple[int, float, float, float]:
        if not group:
            return (0, 0.0, 0.0, 0.0)
        pnls = [_num(x.get("net_pnl_usdt")) for x in group]
        wins = sum(1 for p in pnls if p > 0)
        losses = sum(1 for p in pnls if p < 0)
        return (len(group), sum(pnls), wins / len(group) * 100.0, losses / len(group) * 100.0)

    print("\n🧨 Giveback global (max_pnl_reached>0 mais fin rouge)")
    print(f"- giveback_trades: {len(giveback_rows)} / {len(rows)}")

    # Buckets
    print("\n📦 Buckets max_pnl_reached → giveback rate")
    for b in [bk.name for bk in BUCKETS]:
        group = by_bucket.get(b, [])
        if not group:
            continue
        givebacks = 0
        for r in group:
            mp = r.get("max_pnl_reached")
            if mp is None:
                continue
            if _num(mp) > 0 and _num(r.get("net_pnl_usdt")) < 0:
                givebacks += 1
        n, pnl_sum, wr, lr = summarize(group)
        print(f"- {b:<9} | n={n:>2} | pnl_sum={pnl_sum:+.4f} | winrate={wr:>5.1f}% | giveback={givebacks:>2} ({givebacks/n*100:>5.1f}%)")

    # Reasons
    print("\n🏁 Par exit_reason → pnl & giveback")
    for reason, group in sorted(by_reason.items(), key=lambda kv: len(kv[1]), reverse=True):
        givebacks = 0
        for r in group:
            mp = r.get("max_pnl_reached")
            if mp is None:
                continue
            if _num(mp) > 0 and _num(r.get("net_pnl_usdt")) < 0:
                givebacks += 1
        n, pnl_sum, wr, lr = summarize(group)
        gb_pct = (givebacks / n * 100.0) if n else 0.0
        print(f"- {reason:<14} | n={n:>2} | pnl_sum={pnl_sum:+.4f} | winrate={wr:>5.1f}% | giveback={givebacks:>2} ({gb_pct:>5.1f}%)")

    # Flags (if present)
    if by_flag:
        print("\n🚩 Par flags (si dispo) → pnl & giveback")
        for flag, group in sorted(by_flag.items(), key=lambda kv: len(kv[1]), reverse=True):
            givebacks = 0
            for r in group:
                mp = r.get("max_pnl_reached")
                if mp is None:
                    continue
                if _num(mp) > 0 and _num(r.get("net_pnl_usdt")) < 0:
                    givebacks += 1
            n, pnl_sum, wr, lr = summarize(group)
            gb_pct = (givebacks / n * 100.0) if n else 0.0
            print(f"- {flag:<24} | n={n:>2} | pnl_sum={pnl_sum:+.4f} | winrate={wr:>5.1f}% | giveback={givebacks:>2} ({gb_pct:>5.1f}%)")

    print("=" * 110)


if __name__ == "__main__":
    main()
