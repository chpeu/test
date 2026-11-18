"""Sonde : le robot arrive-t-il vraiment a ecrire un trade ferme en base ?

Pourquoi ce fichier existe : le 18/11/2026 au soir, le journal de marche
affichait « 🔴 POSITION FERMÉE … PnL net: -0.34 % », et la table `trades`
restait vide — l'ecriture echouait sur des colonnes que la base ne connaissait
pas. Rien a l'interface ne le disait : Historique, Correlations et le bilan IA
annoncaient tranquillement « 0 trade ferme ».

Usage (depuis la racine du projet) :

    .venv/bin/python database/sonde_ecriture_trade.py

Ce qu'elle fait : ecrit UN trade factice par le vrai chemin du code
(`log_trade`), le relit immediatement, puis le supprime. Elle ne touche donc
jamais aux vrais trades et laisse la base dans son etat d'avant.

Ce qu'elle prouve : que chaque colonne que le code ecrit existe bien en base, et
que la contrainte d'unicite attendue est la. Elle ne prouve pas que le robot
ouvre des trades — seulement que, quand il en ferme un, la note est gardee.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from core.postgresql_datalogger import get_pg_datalogger  # noqa: E402

TRADE_FABRICE = {
    "symbol": "SONDE/USDT:USDT",
    "direction": "LONG",
    "status": "CLOSED",
    "entry_price": 1.0,
    "exit_price": 0.99,
    "tp_price": 1.02,
    "sl_price": 0.985,
    "size_usdt": 15.0,
    "pnl_pct": -1.0,
    "pnl_usdt": -0.15,
    "net_pnl_pct": -1.34,
    "net_pnl_usdt": -0.20,
    "exit_reason": "SONDE",
    "setup_score": 12.6,
    # des colonnes que la base oubliait le 18/11/2026 :
    "adaptive_sizing_multiplier": 1.0,
    "config_min_score_required": 8.0,
    "config_use_micro_confirmation": True,
    "config_micro_confirmation_delay_ms": 400,
    "entry_volume_multiplier": 0.7,
    "entry_rsi_filter_mode": "NORMAL",
    "entry_position_timeout": 900.0,
    "entry_optimal_atr_max_1m": 0.26,
    "entry_sl_exchange_percent": 0.5,
}


def main() -> int:
    scribe = get_pg_datalogger()
    if not scribe or not scribe.enabled or not scribe.pool:
        print("Journal PostgreSQL indisponible : rien a tester (POSTGRES_ENABLED ?)")
        return 1

    ident = scribe.log_trade(TRADE_FABRICE)
    if not ident:
        print("❌ Le robot n'arrive pas a ecrire un trade : voir les lignes ERROR ci-dessus")
        return 1

    conn = scribe.pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT symbol, net_pnl_pct, adaptive_sizing_multiplier, entry_rsi_filter_mode "
                "FROM trades WHERE id = %s",
                (ident,),
            )
            relu = cur.fetchone()
            cur.execute("DELETE FROM trades WHERE id = %s", (ident,))
            conn.commit()
            cur.execute("SELECT count(*) FROM trades")
            reste = cur.fetchone()[0]
    finally:
        scribe.pool.putconn(conn)

    print(f"✅ trade écrit (id {ident[:8]}), relu : {relu}")
    print(f"✅ preuve effacée, trades restés en base : {reste}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
