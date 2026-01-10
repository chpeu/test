#!/usr/bin/env python3
import json
import os
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv


def _load_expected_thresholds(repo_root: str) -> Tuple[Optional[float], Optional[float]]:
    """Returns (sl_percent, sl_exchange_percent) from config_overrides.json if present."""
    overrides_path = os.path.join(repo_root, "config_overrides.json")
    try:
        with open(overrides_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        sl_percent = data.get("sl_percent")
        sl_exch = data.get("sl_exchange_percent")
        # Some configs name it entry_sl_exchange_percent; if so, treat it as threshold too.
        if sl_exch is None:
            sl_exch = data.get("entry_sl_exchange_percent")
        return (float(sl_percent) if sl_percent is not None else None,
                float(sl_exch) if sl_exch is not None else None)
    except Exception:
        return (None, None)


def _get_pg_conn():
    load_dotenv()
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        database=os.getenv("POSTGRES_DB", "trade_cursor_ml"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def _existing_columns(cursor, table: str, candidates: List[str]) -> List[str]:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table,),
    )
    rows = cursor.fetchall()
    # RealDictCursor returns dict rows; default cursor returns tuples.
    cols = set()
    for row in rows:
        if isinstance(row, dict):
            cols.add(row.get('column_name'))
        else:
            cols.add(row[0])
    return [c for c in candidates if c in cols]


def _pick_first(d: Dict[str, Any], keys: List[str]) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _calc_sl_distance_pct(direction: str, entry_price: float, sl_price: float) -> Optional[float]:
    if entry_price is None or sl_price is None:
        return None
    try:
        entry_price = float(entry_price)
        sl_price = float(sl_price)
        if entry_price <= 0:
            return None
        if direction == "LONG":
            return max(0.0, (entry_price - sl_price) / entry_price * 100.0)
        if direction == "SHORT":
            return max(0.0, (sl_price - entry_price) / entry_price * 100.0)
        return None
    except Exception:
        return None


def main(limit: int = 50, expected_sl_exchange_percent: Optional[float] = None):
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    expected_sl_percent, expected_sl_exchange_percent_file = _load_expected_thresholds(repo_root)

    # Fallback: user mentioned ~0.30% from memory; use it only if nothing else is available.
    if expected_sl_exchange_percent is None:
        expected_sl_exchange_percent = expected_sl_exchange_percent_file
    if expected_sl_exchange_percent is None:
        expected_sl_exchange_percent = 0.30

    print("🔎 Analyse SL sur trades récents")
    print("=" * 70)
    if expected_sl_percent is not None:
        print(f"Seuil attendu sl_percent (config_overrides.json): {expected_sl_percent:.4f}%")
    else:
        print("Seuil attendu sl_percent: N/A (non trouvé dans config_overrides.json)")

    print(f"Seuil attendu sl_exchange_percent: {expected_sl_exchange_percent:.4f}%")

    conn = _get_pg_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Candidate columns in trades table
        sl_price_candidates = [
            "sl_price",
            "stop_loss_price",
            "stop_price",
            "sl",
            "entry_sl_price",
            "entry_stop_loss_price",
            "initial_sl_price",
        ]
        sl_pct_candidates = [
            "sl_percent",
            "config_sl_percent",
            "entry_sl_percent",
            "param_sl_percent",
            "calculated_sl_pct",
        ]
        sl_exch_pct_candidates = [
            "sl_exchange_percent",
            "entry_sl_exchange_percent",
            "config_sl_exchange_percent",
        ]

        # Often useful to spot actual SL drift vs entry (not necessarily initial SL)
        entry_to_max_loss_candidates = [
            "entry_to_max_loss_price_change_pct",
            "entry_to_max_loss_price_change_percent",
        ]

        existing_sl_price_cols = _existing_columns(cur, "trades", sl_price_candidates)
        existing_sl_pct_cols = _existing_columns(cur, "trades", sl_pct_candidates)
        existing_sl_exch_pct_cols = _existing_columns(cur, "trades", sl_exch_pct_candidates)
        existing_entry_to_max_loss_cols = _existing_columns(cur, "trades", entry_to_max_loss_candidates)

        print("\nColonnes SL détectées dans `trades`: ")
        print(f"- sl_price candidates: {existing_sl_price_cols or 'Aucune'}")
        print(f"- sl_pct candidates: {existing_sl_pct_cols or 'Aucune'}")
        print(f"- sl_exchange_pct candidates: {existing_sl_exch_pct_cols or 'Aucune'}")
        print(f"- entry_to_max_loss_pct candidates: {existing_entry_to_max_loss_cols or 'Aucune'}")

        select_cols = [
            "id",
            "symbol",
            "direction",
            "created_at",
            "entry_price",
            "exit_price",
            "exit_reason",
            "pnl_pct",
        ]
        select_cols += existing_sl_price_cols
        select_cols += existing_sl_pct_cols
        select_cols += existing_sl_exch_pct_cols
        select_cols += existing_entry_to_max_loss_cols

        cur.execute(
            f"""
            SELECT {', '.join(select_cols)}
            FROM trades
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        trades = cur.fetchall()
        if not trades:
            print("\n❌ Aucun trade trouvé")
            return

        examples_low_sl: List[Dict[str, Any]] = []
        examples_low_exch: List[Dict[str, Any]] = []

        # thresholds for 'tres en dessous'
        sl_floor = None
        if expected_sl_percent is not None:
            # Flag anything < 70% of expected (ex: 0.175 if expected 0.25)
            sl_floor = expected_sl_percent * 0.70

        exch_floor = expected_sl_exchange_percent * 0.70

        for t in trades:
            direction = (t.get("direction") or "").upper()
            entry_price = t.get("entry_price")
            sl_price = _pick_first(t, existing_sl_price_cols)
            sl_dist_pct = None
            if sl_price is not None and entry_price is not None:
                sl_dist_pct = _calc_sl_distance_pct(direction, entry_price, sl_price)

            sl_pct_logged = _pick_first(t, existing_sl_pct_cols)
            sl_exch_pct_logged = _pick_first(t, existing_sl_exch_pct_cols)

            # Normalize exchange pct to float if possible
            try:
                if sl_exch_pct_logged is not None:
                    sl_exch_pct_logged = float(sl_exch_pct_logged)
            except Exception:
                sl_exch_pct_logged = None

            # Decide which SL pct to compare: prefer computed from sl_price, else logged
            effective_sl_pct = sl_dist_pct
            if effective_sl_pct is None:
                try:
                    effective_sl_pct = float(sl_pct_logged) if sl_pct_logged is not None else None
                except Exception:
                    effective_sl_pct = None

            if sl_floor is not None and effective_sl_pct is not None and effective_sl_pct < sl_floor:
                examples_low_sl.append(
                    {
                        "symbol": t.get("symbol"),
                        "direction": direction,
                        "created_at": t.get("created_at"),
                        "exit_reason": t.get("exit_reason"),
                        "pnl_pct": t.get("pnl_pct"),
                        "entry_price": entry_price,
                        "sl_price": sl_price,
                        "sl_dist_pct": sl_dist_pct,
                        "sl_pct_logged": sl_pct_logged,
                        "effective_sl_pct": effective_sl_pct,
                    }
                )

            if sl_exch_pct_logged is not None and sl_exch_pct_logged < exch_floor:
                examples_low_exch.append(
                    {
                        "symbol": t.get("symbol"),
                        "direction": direction,
                        "created_at": t.get("created_at"),
                        "exit_reason": t.get("exit_reason"),
                        "pnl_pct": t.get("pnl_pct"),
                        "sl_exch_pct_logged": sl_exch_pct_logged,
                    }
                )

        print("\n" + "=" * 70)
        print(f"📉 Trades avec SL trop petit (sur {len(trades)} derniers)" + (f" (< {sl_floor:.4f}%)" if sl_floor is not None else ""))
        if sl_floor is None:
            print("(Impossible de comparer: sl_percent attendu non trouvé dans config_overrides.json)")
        else:
            print(f"Trouvés: {len(examples_low_sl)}")
            for ex in examples_low_sl[:10]:
                eff = ex["effective_sl_pct"]
                dist = ex["sl_dist_pct"]
                logged = ex["sl_pct_logged"]
                src = "calc(sl_price)" if dist is not None else "logged"
                print(
                    f"- {ex['created_at']} | {ex['symbol']} {ex['direction']} | {ex['exit_reason']} | pnl={ex['pnl_pct']}% | SL%={eff:.4f} ({src}) | entry={ex['entry_price']} sl={ex['sl_price']} logged_sl%={logged}"
                )

        print("\n" + "=" * 70)
        print(f"📉 Trades avec entry_sl_exchange_percent trop petit (sur {len(trades)} derniers) (< {exch_floor:.4f}%)")
        print(f"Trouvés: {len(examples_low_exch)}")
        for ex in examples_low_exch[:10]:
            print(
                f"- {ex['created_at']} | {ex['symbol']} {ex['direction']} | {ex['exit_reason']} | pnl={ex['pnl_pct']}% | entry_sl_exchange_percent={ex['sl_exch_pct_logged']:.4f}%"
            )

    finally:
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Analyse SL (distance vs seuils) sur derniers trades")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    main(limit=args.limit)
