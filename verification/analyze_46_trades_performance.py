"""Analyse la performance des trades actuellement affichés dans le frontend.

Source = payload live de l'instance (GET /api/state).

Objectifs:
- stats performance (winrate, PF, expectancy)
- répartition par raison de sortie et direction
- diagnostic "setups vs gestion":
  - si beaucoup de trades ont un max_pnl_reached positif mais finissent rouges => gestion/exits

Si DB dispo, on enrichit avec trades table + trade_atr_metrics.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import requests
from psycopg2.extras import RealDictCursor
from urllib.parse import quote_plus

BASE_URL = "http://127.0.0.1:3000"
STATE_URL = f"{BASE_URL}/api/state"


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


def find_trades(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("trade_history", "trades", "tradeHistory"):
        v = payload.get(key)
        if isinstance(v, list):
            return [t for t in v if isinstance(t, dict)]
    return []


def get_reliable_size_usdt(trade: Dict[str, Any]) -> float:
    initial_size = _num(trade.get("size_initial_usdt"))
    executed_size = _num(
        trade.get("size_executed_usdt")
        or trade.get("size")
        or trade.get("filled_size_usdt")
        or trade.get("position_size_usdt")
    )

    pnl_usdt = _num(trade.get("net_pnl_usdt"))
    pnl_pct = _num(trade.get("net_pnl_pct"))

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

    return size if size > 0 else 0.0


def summarize_values(pnls: List[float]) -> Dict[str, float]:
    if not pnls:
        return {"min": 0.0, "max": 0.0, "mean": 0.0}
    return {
        "min": min(pnls),
        "max": max(pnls),
        "mean": sum(pnls) / len(pnls),
    }


def main() -> None:
    r = requests.get(STATE_URL, timeout=10)
    r.raise_for_status()
    payload = r.json()

    trades = find_trades(payload)
    config = payload.get("config") or {}

    invert_signals = None
    if isinstance(config, dict):
        invert_signals = config.get("invert_signals")

    print("=" * 100)
    print("📊 Analyse performance - trades du frontend")
    print(f"Source: {STATE_URL}")
    print("=" * 100)
    print(f"Trades: {len(trades)}")
    if invert_signals is not None:
        print(f"Config invert_signals: {invert_signals}")

    if not trades:
        return

    # --- Stats frontend (net) ---
    pnls_usdt = [_num(t.get("net_pnl_usdt")) for t in trades]
    pnls_pct = [_num(t.get("net_pnl_pct")) for t in trades]
    sizes = [get_reliable_size_usdt(t) for t in trades]

    wins = [p for p in pnls_usdt if p > 0]
    losses = [p for p in pnls_usdt if p < 0]

    sum_pnl = sum(pnls_usdt)
    sum_win = sum(wins)
    sum_loss = sum(losses)

    winrate = (len(wins) / len(pnls_usdt) * 100.0) if pnls_usdt else 0.0
    avg_win = (sum_win / len(wins)) if wins else 0.0
    avg_loss = (sum_loss / len(losses)) if losses else 0.0

    profit_factor = (sum_win / abs(sum_loss)) if sum_loss < 0 else float("inf")

    total_size = sum(sizes)
    weighted_pct = (sum_pnl / total_size * 100.0) if total_size else 0.0

    # Somme brute des % (pour comprendre ce que ça donnerait)
    sum_pct_raw = sum(pnls_pct)

    print("\n✅ Performance (net, comme UI)")
    print(f"- PnL total: {sum_pnl:+.4f} USDT")
    print(f"- Winrate: {winrate:.1f}% (wins={len(wins)} / losses={len(losses)} / total={len(pnls_usdt)})")
    print(f"- Avg win: {avg_win:+.4f} USDT | Avg loss: {avg_loss:+.4f} USDT")
    print(f"- Profit Factor: {profit_factor:.3f}")
    print(f"- Notionnel cumulé (Σ size fiable): {total_size:.2f} USDT")
    print(f"- % session pondéré: {weighted_pct:+.4f}%")
    print(f"- Somme brute des % (ancien affichage): {sum_pct_raw:+.4f}%")

    # --- Répartition raisons / directions ---
    reasons = Counter((t.get("reason") or t.get("exit_reason") or t.get("close_reason") or "N/A") for t in trades)
    dirs = Counter((t.get("direction") or "N/A") for t in trades)

    print("\n🏁 Répartition raisons de sortie (frontend)")
    for k, v in reasons.most_common():
        print(f"- {k}: {v}")

    print("\n🧭 Répartition directions (frontend)")
    for k, v in dirs.most_common():
        print(f"- {k}: {v}")

    # --- Diagnostic gestion vs setups via DB ---
    trade_ids = [_get_trade_id(t) for t in trades]
    trade_ids = [tid for tid in trade_ids if tid]

    # Si les ids ne sont pas des UUID (fallback id frontend), on ne peut pas enrichir.
    uuid_like = [tid for tid in trade_ids if len(tid) >= 32]

    if not uuid_like:
        print("\nℹ️ Pas d'IDs UUID exploitables dans payload → skip enrichissement DB")
        return

    try:
        password = quote_plus("@Cmtr1di12345")
        conn = psycopg2.connect(f"postgresql://postgres:{password}@localhost:5432/trade_cursor_ml")
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # On ne prend que les UUID plausibles
        ids_tuple = tuple(uuid_like)

        # Colonnes utiles dans trade_atr_metrics: tenter de les lire si présentes
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name='trade_atr_metrics'
              AND column_name IN (
                'trade_id',
                'max_pnl_reached',
                'trailing_activated',
                'be_triggered',
                'mfe_pct',
                'mae_pct',
                'stagnation_detected'
              )
            """
        )
        available = {r["column_name"] for r in cur.fetchall()}

        select_cols = ["trade_id"]
        for c in ["max_pnl_reached", "trailing_activated", "be_triggered", "mfe_pct", "mae_pct", "stagnation_detected"]:
            if c in available:
                select_cols.append(c)

        # récupérer trades + metrics
        query = f"""
            SELECT
                t.id::text as id,
                t.symbol,
                t.direction,
                t.exit_reason,
                t.net_pnl_usdt,
                t.net_pnl_pct,
                t.size_usdt,
                m.{', m.'.join(select_cols) if select_cols else 'trade_id'}
            FROM trades t
            LEFT JOIN trade_atr_metrics m ON t.id = m.trade_id::uuid
            WHERE t.id::text = ANY(%s)
        """

        cur.execute(query, (list(ids_tuple),))
        rows = [dict(r) for r in cur.fetchall()]

        # Heuristique: gestion problématique si max_pnl_reached > 0 alors que net_pnl_usdt < 0
        management_giveback = 0
        max_pnls = []
        for row in rows:
            net_u = _num(row.get("net_pnl_usdt"))
            mp = row.get("max_pnl_reached")
            if mp is not None:
                mp_val = _num(mp)
                max_pnls.append(mp_val)
                if mp_val > 0 and net_u < 0:
                    management_giveback += 1

        if max_pnls:
            s = summarize_values(max_pnls)
            print("\n📌 Diagnostic DB (trade_atr_metrics)")
            print(f"- Trades avec max_pnl_reached dispo: {len(max_pnls)}")
            print(f"- max_pnl_reached min/mean/max: {s['min']:.4f} / {s['mean']:.4f} / {s['max']:.4f}")
            print(f"- Giveback (max_pnl_reached>0 mais fin rouge): {management_giveback} trades")
            print("  => Si ce chiffre est élevé: problème plutôt gestion/exits que setup.")
        else:
            print("\nℹ️ Colonnes max_pnl_reached non dispo (ou null) → skip giveback diagnostic")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"\n⚠️ Enrichissement DB échoué: {e}")


if __name__ == "__main__":
    main()
