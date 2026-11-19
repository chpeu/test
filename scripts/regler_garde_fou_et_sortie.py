#!/usr/bin/env python3
"""Met la config vivante en accord avec le garde-fou et la sortie décidés le 19/11/2026.

Trois choses étaient fausses dans `config_overrides.json` — le fichier qui a la
priorité sur `config.py` (210 réglages, écrit par l'interface et les optimiseurs) :

  1. `trading_circuit_breaker_enabled: false` : tout le pare-feu (pause après une
     série de pertes, pause à -2 %, arrêt à -5 % de perte sur la journée) était
     éteint. Le 18/11, il a été branché sur l'ouverture des positions — mais il
     ne tournait pas. Les bornies live étaient en plus très lâches (10 pertes,
     -4,5 %, -10 %).
  2. `ml_calib_dryrun_weight: 0.0` : un trade en essai à blanc pesait **zéro**
     dans l'apprentissage. Avec la correction du 19/11 (la barrière
     d'apprentissage compte les trades, pas le total pondéré), un poids nul
     laisserait le pourcentage de réussite calculé à 0 — donc le robot
     rejetterait tout. Mis à 0,5 : un essai vaut la moitié d'un trade réel.
  3. La rampe de sortie était poussée très loin par l'override :
     distance 0,15 % → 0,40 %, avec un palier à +1,45 %. Concrètement le stop
     suiveur ne se resserrait presque jamais, et les trades gagnants rendaient
     0,30 point en moyenne (mesure sur 94 trades fermés). Ramené à
     0,12 % → 0,22 % avec palier à +0,80 %.

Sont aussi retirés : `test_key: "test_value"` et `number: 42`, restes de tests
qui écrivaient dans la config vivante (le démarrage grondait « Override ignoré
(clé inconnue) » à chaque lancement).

Usage :
    PYTHONPATH=. .venv/bin/python scripts/regler_garde_fou_et_sortie.py [--secher]
"""

import argparse
import json

from utils.config_persistence import CONFIG_OVERRIDES_FILE, load_config_overrides

VALEURS = {
    # Garde-fou en marche, avec les bornies du code (pas les versions lâches)
    "trading_circuit_breaker_enabled": True,
    "trading_cb_max_consecutive_losses": 5,
    "trading_cb_daily_drawdown_pause_pct": -2.0,
    "trading_cb_daily_drawdown_stop_pct": -5.0,
    "trading_cb_score_boost_enabled": True,
    # Un essai à blanc compte, à moitié
    "ml_calib_dryrun_weight": 0.5,
    # Rampe de sortie resserrée
    "trailing_min_distance": 0.12,
    "trailing_max_distance": 0.22,
    "trailing_pnl_cap": 0.80,
}

DECHETS = ["test_key", "number"]


def main() -> int:
    arg = argparse.ArgumentParser()
    arg.add_argument("--secher", action="store_true", help="montre sans écrire")
    opts = arg.parse_args()

    overrides = load_config_overrides()
    print(f"config vivante : {len(overrides)} réglages")

    for cle, valeur in VALEURS.items():
        avant = overrides.get(cle, "(absent)")
        print(f"  {cle:<42} {avant}  →  {valeur}")

    for cle in DECHETS:
        if cle in overrides:
            print(f"  {cle:<42} {overrides[cle]}  →  supprimé")

    if opts.secher:
        print("\nà sec : rien n'a été écrit.")
        return 0

    overrides.update(VALEURS)
    for cle in DECHETS:
        overrides.pop(cle, None)

    # Écriture directe : `save_config_overrides()` relit le fichier et le fusionne
    # avec ce qu'on lui donne. Il peut donc ajouter et modifier, jamais retirer —
    # les déchets de tests (test_key, number) ressurgiraient immédiatement.
    try:
        with open(CONFIG_OVERRIDES_FILE, "w", encoding="utf-8") as f:
            json.dump(overrides, f, indent=2, ensure_ascii=False)
    except OSError as exc:
        print(f"échec de l'écriture : {exc}")
        return 1

    relu = load_config_overrides()
    manque = [c for c in VALEURS if relu.get(c) != VALEURS[c]]
    dechet_reste = [c for c in DECHETS if c in relu]
    print(f"\nrelu après écriture : {len(relu)} réglages")
    print(" clés manquantes :", manque or "aucune", "· déchets restants :", dechet_reste or "aucun")
    return 0 if not manque and not dechet_reste else 1


if __name__ == "__main__":
    raise SystemExit(main())
