#!/usr/bin/env python3
"""Lit le carnet fantôme : qu'ont donné les dossiers que le robot a refusés ?

Usage :
    PYTHONPATH=. .venv/bin/python scripts/lire_carnet_fantome.py [--heures 24]

Répond famille de refus par famille : combien de dossiers, combien jugés, combien
auraient atteint l'objectif avant le stop. C'est la réponse à « est-ce que ce
filtre fait perdre de l'argent ? » — la question que le journal de trading seul ne
peut pas poser, puisqu'il ne contient que les prises acceptées.

Sortie type :

    famille                 notes  jugés  gagnés  perdus  neutres  % atteint  sommet moyen
    volume_filter              412    180      61      74       45      33,9 %      0,51 %
    atr_filter                 288     95      38      40       17      40,0 %      0,47 %
"""

import argparse

from core.postgresql_datalogger import connexion_journal

PAR_FAMILLE = """
    select reject_category as famille,
           count(*) as notes,
           count(*) filter (where statut <> 'EN_ATTENTE') as juges,
           count(*) filter (where statut = 'GAGNE') as gagnes,
           count(*) filter (where statut = 'PERDU') as perdus,
           count(*) filter (where statut = 'NEUTRE') as neutres,
           round(100.0 * nullif(count(*) filter (where statut = 'GAGNE'), 0)
                 / nullif(count(*) filter (where statut in ('GAGNE','PERDU','NEUTRE')), 0), 1)
             as pct_atteint,
           round(avg(gain_max_pct)::numeric, 3) as sommet_moyen
    from ghost_setups
    where timestamp_scan >= now() - (%s || ' hours')::interval
    group by 1
    order by notes desc
"""


def main() -> int:
    arg = argparse.ArgumentParser()
    arg.add_argument("--heures", default=24, help="fenêtre en heures (défaut 24)")
    opts = arg.parse_args()

    with connexion_journal() as cnx:
        if cnx is None:
            print("Journal indisponible : POSTGRES_ENABLED=false ou base éteinte.")
            return 1
        with cnx.cursor() as cur:
            cur.execute(PAR_FAMILLE, (opts.heures,))
            lignes = cur.fetchall()

    if not lignes:
        print(
            f"Aucun dossier dans le carnet sur les {opts.heures} dernières heures.\n"
            "Le carnet note les signaux trouvés en 1 minute puis refusés à la "
            "re-vérification 5 minutes : s'il est vide, c'est que le robot ne "
            "s'arrête plus à cette porte-là."
        )
        return 0

    print(f"carnet fantôme — {opts.heures} dernières heures")
    print(
        f"  {'famille':<22} {'notes':>6} {'jugés':>6} {'gagnés':>7} {'perdus':>7}"
        f" {'neutres':>8} {'% atteint':>10} {'sommet moyen':>13}"
    )
    for famille, notes, juges, gagnes, perdus, neutres, pct, sommet in lignes:
        print(
            f"  {(famille or '?'):<22} {notes:>6} {juges:>6} {gagnes:>7} {perdus:>7}"
            f" {neutres:>8} {str(pct or 0):>10} {str(sommet or 0):>13}"
        )

    total_juges = sum(l[2] for l in lignes)
    if total_juges < 30:
        print(
            f"\n Prudence : {total_juges} dossiers jugés seulement. En dessous de ~100, "
            "une famille ne se juge pas encore — laisser tourner."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
