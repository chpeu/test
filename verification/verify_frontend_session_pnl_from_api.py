"""Vérifie le calcul PnL Session (USDT + %) tel que fait par le frontend.

- Source: payload live de l'instance (GET http://127.0.0.1:3000/api/state)
- Calcul USDT: somme de net_pnl_usdt
- Calcul %: (somme net_pnl_usdt) / (somme size_usdt fiable) * 100

Le but est d'expliquer un cas du type: -0.34 USDT mais -0.05%.
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional, Tuple

import requests

BASE_URL = "http://127.0.0.1:3000"
STATE_URL = f"{BASE_URL}/api/state"


def _num(v: Any) -> float:
    try:
        if v is None:
            return 0.0
        return float(v)
    except Exception:
        return 0.0


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


def find_trades(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("trade_history", "trades", "tradeHistory"):
        v = payload.get(key)
        if isinstance(v, list):
            return [t for t in v if isinstance(t, dict)]
    return []


def main() -> None:
    r = requests.get(STATE_URL, timeout=10)
    r.raise_for_status()
    payload = r.json()

    trades = find_trades(payload)

    print("=" * 90)
    print(f"🔎 Frontend PnL Session - source: {STATE_URL}")
    print("=" * 90)
    print(f"Trades dans payload: {len(trades)}")

    # Reproduire les filtres possibles: le frontend utilise sortedTrades dérivé de tradeHistory
    # donc on somme tout ce qui est dans la liste.
    pnl_usdt_values = [
        _num(t.get("net_pnl_usdt"))
        for t in trades
    ]
    sum_pnl_usdt = sum(pnl_usdt_values)

    sizes = [get_reliable_size_usdt(t) for t in trades]
    sum_size = sum(sizes)

    session_pct = (sum_pnl_usdt / sum_size * 100.0) if sum_size else 0.0

    print("\n📊 Résultats (réplique frontend):")
    print(f"- Σ net_pnl_usdt: {sum_pnl_usdt:+.6f} USDT")
    print(f"- Σ size_usdt (fiable): {sum_size:.6f} USDT")
    print(f"- PnL session % (pondéré): {session_pct:+.6f}%")

    # Aides au diagnostic: distribution des sizes
    sizes_nonzero = [s for s in sizes if s > 0]
    if sizes_nonzero:
        sizes_sorted = sorted(sizes_nonzero)
        print("\n📐 Distribution size_usdt (fiable):")
        print(f"- min: {sizes_sorted[0]:.4f}")
        print(f"- median: {statistics.median(sizes_sorted):.4f}")
        print(f"- mean: {statistics.mean(sizes_sorted):.4f}")
        print(f"- max: {sizes_sorted[-1]:.4f}")

    # Montrer les plus grosses tailles (pour détecter dénominateur gonflé)
    biggest: List[Tuple[float, Dict[str, Any]]] = sorted(
        ((sizes[i], trades[i]) for i in range(len(trades))),
        key=lambda x: x[0],
        reverse=True,
    )[:10]

    print("\n🔝 Top 10 tailles (fiables) - pour détecter un dénominateur anormal:")
    for s, t in biggest:
        ts = t.get("closed_at") or t.get("timestamp") or t.get("timestamp_exit")
        symbol = t.get("symbol")
        direction = t.get("direction")
        pnl_u = _num(t.get("net_pnl_usdt"))
        pnl_p = _num(t.get("net_pnl_pct"))
        raw_size = t.get("size_executed_usdt") or t.get("size") or t.get("filled_size_usdt") or t.get("position_size_usdt")
        init_size = t.get("size_initial_usdt")
        print(f"- size={s:>8.2f} | pnl={pnl_u:+.4f} USDT | pct={pnl_p:+.3f}% | raw_size={raw_size} | init={init_size} | {symbol} {direction} | {ts}")

    # Explication simple du -0.34 USDT vs -0.05%
    if sum_size:
        implied_pct = (sum_pnl_usdt / sum_size) * 100.0
        print("\n🧠 Interprétation:")
        print(f"- Si tu as ~{sum_size:.0f} USDT de notionnel cumulé sur la période, alors {sum_pnl_usdt:+.2f} USDT ⇒ {implied_pct:+.2f}%")
        print("  => Donc un % très petit est normal si la somme des tailles est élevée.")

    print("=" * 90)


if __name__ == "__main__":
    main()
