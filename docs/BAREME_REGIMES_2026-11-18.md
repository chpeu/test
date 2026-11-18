# Le barème qui compte est dans `config/regimes/` — 18/11/2026

## Ce que les codes par défaut ne disent pas

Le fichier `core/market_regime_selector.py` contient un barème par ambiance
(`DEFAULT_REGIME_CONFIGS`) : en CALME, il demande un ATR 5 min d'au moins 0,10 %.
**Ce n'est pas ce que le robot utilise.** Au démarrage, le sélecteur charge
`config/regimes/{calme,normal,volatile,choppy}.json`, et ces fichiers ont été
réglés au fil des optimisations :

| Ambiance | score minimum | ATR 5 min minimum | multiplicateur de volume |
|---|---|---|---|
| calme | 9,0 | 0,35 % | ×0,9 |
| normal | 7,5 | 0,35 % | ×0,8 |
| volatile | 7,0 | 0,50 % | ×1,2 |
| choppy | 10,0 | 0,35 % | ×0,7 |

Le 18/11/2026, une analyse faite sur les valeurs par défaut du code a donc donné
un faux diagnostic (« le robot demande 0,10 %, on lui impose 0,35 % »). Les
chiffres réels du terrain sont dans le tableau ci-dessus. Leçon : **toujours lire
le fichier vivant avant de parler d'un réglage.**

## Deux fils coupés trouvés en chemin (corrigés)

1. `utils/effective_config.py` : quand le mode TP/SL est « FIXE », la règle
   écartait **tous** les réglages liés à l'ATR venus du régime — les stops (c'était
   l'intention) **et** les planchers des filtres d'entrée (dommage). Le plancher
   1 min du régime ne remontait jamais. Corrigé et verrouillé par
   `tests/test_regime_filtres_entree.py` (5 cas).
2. `core/callbacks/scanner_loop.py` : le multiplicateur de volume était lu dans
   `TRADING_CONFIG` (valeur globale 1,2) au lieu de la configuration efficace.
   En marché CALME, le barème demande ×0,9 : il ne l'obtenait jamais. Corrigé
   (commit `f3afbb0`) — après redémarrage, la formule du seuil affiche
   « base: 0.60x × mult: 0,80 » pour le régime NORMAL, ce qu'on ne voyait pas
   avant.

## Ce que ça change, mesuré

Fenêtre de 9 minutes après le branchement des deux fils :

- détections en 1 min parvenues à la re-vérification 5 min : **86** (14 sur la
  fenêtre précédente de 10 minutes) ;
- 2 tentatives d'ouverture, **1 position ouverte** ;
- porte qui bloque le plus maintenant : le volume (28 rejets) puis l'ATR
  (27 rejets).

## Ce qui reste à décider

Les valeurs du fichier vivant datent d'une époque où **aucun trade fermé n'était
enregistré** (le journal fuyait — voir `docs/MISE_EN_PLACE_BD_2026-11-18.md`).
Elles n'ont donc jamais été corrigées avec de vraies statistiques. Deux chemins :

- **laisser apprendre** : la calibration ML attend 30 trades fermés
  (`ml_calib_min_trades`) avant de proposer ses propres seuils, et le score par
  paire lit l'historique de chaque paire ; il faut donc accumuler des trades ;
- ** desserrer tout de suite** : baisser dans `config/regimes/calme.json` le
  score de 9,0 vers 7,5 et l'ATR 5 min de 0,35 % vers 0,20 % — mais sans mesure
  en face, c'est un pari.

Dans les deux cas, avant d'ouvrir la vanne : les plafonds de dégâts (risque par
trade, nombre de trades par jour, perte quotidienne maximale) n'existent pas
encore dans le code.
