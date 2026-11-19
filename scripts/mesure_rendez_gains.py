#!/usr/bin/env python3
"""Compare ce que le robot garde à ce que ses trades lui présentaient.

Usage :
    PYTHONPATH=. .venv/bin/python scripts/mesure_rendez_gains.py [--jours 7]

Lit le journal PostgreSQL et répond à une question simple : entre le sommet
atteint par un trade gagnant et sa sortie réelle, combien de points ont été
rendus ? C'est la sonde qui accompagne le réglage `trailing_max_distance`
(distance du stop suiveur) : sans elle, régler une sortie est une opinion.

Le script donne aussi la **borne haute** de ce que rapporterait une distance plus
courte : ce qu'on aurait gardé en plus si le stop avait suivi de plus près, en
supposant que le prix a reflué d'un seul tenant (hypothèse optimiste — le prix
aurait pu repartir après une sortie plus précoce, et rien dans le journal ne le
dit).
"""

import argparse

from config import TRADING_CONFIG
from core.postgresql_datalogger import connexion_journal

PAR_PERIODES = """
    with x as (
        select t.id,
               date_trunc('day', t.timestamp_exit) as jour,
               t.net_pnl_pct,
               max(m.max_pnl_reached) as sommet
        from trades t
        join trade_atr_metrics m on m.trade_id = t.id
        where t.timestamp_exit >= now() - (%s || ' days')::interval
          and t.net_pnl_pct > 0
        group by 1, 2, 3
    )
    select jour::date as jour,
           count(*) as prises,
           round(avg(net_pnl_pct)::numeric, 3) as empoché,
           round(avg(sommet)::numeric, 3) as sommet,
           round(avg(sommet - net_pnl_pct)::numeric, 3) as rendu,
           round(sum(net_pnl_pct)::numeric, 2) as total
    from x
    group by 1
    order by 1
"""

BORNE_HAUTE = """
    with base as (
        select t.id,
               t.net_pnl_pct,
               max(m.max_pnl_reached) as sommet
        from trades t
        join trade_atr_metrics m on m.trade_id = t.id
        where t.timestamp_exit >= now() - (%s || ' days')::interval
          and t.net_pnl_pct > 0
        group by 1, 2
    ), x as (
        select sommet - net_pnl_pct as rendu from base
    )
    select count(*) filter (where rendu > %s) as rendaient_plus,
           round(sum(greatest(rendu - %s, 0))::numeric, 2) as gain_max_potentiel,
           round(percentile_cont(0.5) within group (order by rendu)::numeric, 3) as rendu_median
    from x
"""


def main() -> int:
    arg = argparse.ArgumentParser()
    arg.add_argument("--jours", default=7, help="fenêtre en jours (défaut 7)")
    opts = arg.parse_args()

    distance = float(TRADING_CONFIG.get("trailing_max_distance", 0.30))

    with connexion_journal() as cnx:
        if cnx is None:
            print("Journal indisponible : POSTGRES_ENABLED=false ou base éteinte.")
            return 1
        with cnx.cursor() as cur:
            cur.execute(PAR_PERIODES, (opts.jours,))
            jours = cur.fetchall()
            cur.execute(BORNE_HAUTE, (opts.jours, distance, distance))
            note = cur.fetchone()

    if not jours:
        print(f"Aucun trade gagnant fermé dans les {opts.jours} derniers jours.")
        return 0

    print(f" trades gagnants fermés — distance actuelle du stop suiveur : {distance} %")
    for jour, prises, empoch, sommet, rendu, total in jours:
        print(
            f"  {jour} {prises:>4} prises · empoché {empoch:>6} % · "
            f"sommet {sommet:>6} % · rendu {rendu:>6} % · total {total:>7} %"
        )

    rendaient_plus, gain_max, rendu_median = note
    print(
        f"\n {rendaient_plus} prises sur {sum(p for _, p, *_ in jours)} ont rendu plus de "
        f"{distance} % ; rendu médian {rendu_median} %."
    )
    print(
        f" Borne haute si le stop avait suivi à {distance} % : +{gain_max} % de plus "
        "sur la période (hypothèse optimiste : le prix n'est jamais reparti après "
        "une sortie plus précoce)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
