# Scripts mis de côté le 17/11/2026

90 scripts qui traînaient à la racine du dépôt, déplacés ici tels quels
(arithmétique : 139 scripts à la racine avant, 49 après).

## Pourquoi

Un comptage automatique a cherché, pour chaque script, son nom comme mot entier
dans tout le code qui tourne (`api`, `core`, `trading`, `ml`, `optimization`,
`utils`, `database`, `notifications`, `main.py`) et dans les tests. Résultat :
**90 scripts que plus personne n'appelle**, soit 11 954 lignes.

Ce sont pour la plupart des outils d'un jour : une analyse d'un trade précis
(`analyze_last_13.py`, `analyze_jelly_trade.py`), une correction ponctuelle en
base (`fix_trade_duplicates_complete.py`), une vérification d'une session
(`final_ml_verification.py`, `verify_ui_fixes.py`). Ils décrivent des épisodes
clos, et leur présence à la racine donnait au projet l'air d'un chantier permanent.

## Ce qui a été gardé à la racine, et pourquoi

- 5 scripts appelés par le code qui tourne (`config.py`, `main.py`, et 3 autres) ;
- 44 scripts cités par des tests ou par `verification/` — gardés pour l'instant,
  parce que les retirer oblige aussi à retirer les tests qui les exécutent sans
  rien affirmer. C'est le chantier suivant, pas celui-ci.

## Rien n'est perdu

Les fichiers sont intacts ici. `git log --follow archive/2026-11-racine/<nom>.py`
donne leur historique complet, y compris leur ancien emplacement à la racine.
