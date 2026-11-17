# Audit : pourquoi c'est si compliqué, et comment aller vers du simple

Date : 17/11/2026 · Branch `claude2` · mesuré sur le dépôt réel (outils + comptages, pas des impressions)

---

## 1. En deux phrases

Le programme fait **190 601 lignes** pour une idée simple : « chercher une paire qui monte ou descend fort, acheter petit, sortir vite ».
La décision elle-même tient dans **une seule fonction de 3 394 lignes avec 310 embranchements** (`core/analyzer.py` → `analyze_pair`) : c'est ça que tu ressens comme de la complexité.

---

## 2. Le chemin réel d'un trade (entrée → sortie)

| Étape | Fichier | Ce qui se passe réellement | Cadence |
|---|---|---|---|
| 1. Choisir les paires | `core/top_pairs_scalability.py` + `core/callbacks/scanner_loop.py` | On demande à MEXC toutes les paires, on en garde ~17 sur 101 (rejets : volume 24 h, funding, spread, score de scalabilité = 0) | toutes les 90 s |
| 2. Récupérer les prix | `api/price_provider.py` | Bougies 1 minute et 5 minutes, carnet d'ordres, spread | en continu (WebSocket) |
| 3. Décider | `core/analyzer.py` (`analyze_pair`, 310 branches) | Notes séparées 1 m et 5 m sur 9.0, seuils, filtres (whipsaw, cooldown, RSI, micro-confirmation, 6 figures de bougies, breakouts, divergences), régimes de marché, circuit breaker | toutes les 45 s |
| 4. Calculer la taille | `core/position_manager.py` (`open_position`, 257 branches) | Mise de départ, sizing adaptatif, levier, confiance ML (46 fois mentionnée) | à l'entrée |
| 5. Exécuter | `trading/live_order_manager_futures.py` (3 276 lignes) | Un seul type d'ordre : **market**. TP/SL en deux modes : `FIXE` (pourcentages) ou `ATR` (distance fonction de la volatilité) | à l'entrée |
| 6. Surveiller et sortir | `core/position_manager.py` (`check_position` 157 branches, `close_position` 212) | Trailing stop, sorties partielles, invalidation, stagnation, timeout | toutes les **2 s** |
| 7. Noter | `core/postgresql_datalogger.py` (3 535 lignes) + `core/simple_pg_logger.py` | Chaque scan et chaque trade sont écrits en base | à chaque événement |

Il y a donc **7 endroits différents** où une paire peut être refusée, et chacun a ses propres réglages.

---

## 3. D'où vient la complexité (chiffré)

**a) Deux chemins pour faire la même chose.** Le projet garde en parallèle une version « d'origine » et une version « testable » :

| Version d'origine | Version parallèle | Comment on choisit |
|---|---|---|
| `core/analyzer.py` (3 394 l.) | `core/implementations/testable_analyzer.py` (749 l.) | drapeau `use_testable_analyzer` |
| `core/position_manager.py` (6 221 l.) | `core/implementations/testable_position_manager.py` (496 l.) | drapeau `use_testable_position_manager` |
| `trading/live_order_manager.py` (533 l.) | `trading/live_order_manager_futures.py` (3 276 l.) | le second écrase le premier |
| `core/postgresql_datalogger.py` (3 535 l.) | `core/simple_pg_logger.py` (273 l.) + `backend/ml/data_logger.py` (72 l.) | selon l'humeur du démarrage |

Neuf drapeaux (`core/feature_flags.json`) servent à basculer entre ces jumeaux, dont `comparison_mode` et `safe_rollback_mode`. **Conséquence :** pour lire une règle, il faut d'abord savoir dans quelle copie on est.

**b) Un panneau de réglages énorme.** Un seul fichier d'interface de **8 023 lignes** avec **239 champs de saisie** et 16 blocs : Système de validation, Patterns techniques, Patterns de bougies, Filtres avancés, Timeframes & ATR, Money Management, Sizing adaptatif, Live Trading, Take Profit / Stop Loss, Trailing stop, Protection & Régime, Market Regime V2, Seuils de spread, Adaptations ML… C'est l'interface qui donne la sensation de usine à gaz, pas le trading.

**c) Des paramètres redondants.** 5 régimes de marché (CALME, NORMAL, VOLATILE, CHOPPY, UNKNOWN) × ~21 paramètres chacun = le même filtre peut avoir un seuil différent selon le régime, et le régime se change tout seul toutes les 15 minutes.

**d) Des fonctions trop longues.** Les pires, mesurées (nombre de chemins internes) : `analyze_pair` 310, `open_position` 257, `close_position` 212, `scan_pair_for_setup` 200, `check_position` 157, `analyze_timeframe` 154. Une fonction à 300 chemins ne se relit pas, donc on n'y touche plus, donc elle grossit.

**e) DuLegacy qui reste.** `api/routes/ml_legacy.py` : 4 780 lignes de routes « legacy » encore montées.

**f) La documentation a grossi avec le code.** `docs/` contient **73 fichiers**, dont 15 visiblement périmés (notes de séance de décembre 2024 / 2025). Deux plans de simplification existent déjà (dont `PLAN_REFACTORISATION_COVERAGE.md` du 20/12/2025) et n'ont jamais été appliqués. Le problème est diagnostiqué depuis 11 mois.

---

## 4. Ce qui existe déjà pour l'IA (bonne nouvelle)

Tu n'as pas besoin d'acheter une IA : le projet a déjà les briques, mais elles ne décident pas.

| Brique | Fichier | État |
|---|---|---|
| Modèle de confiance par trade | `optimization/predictor_v2.py`, `predictor_optimized.py` | sert seulement à **filtrer** (46 mentions dans `position_manager`), jamais à choisir |
| Calibration (la confiance est-elle honnête ?) | `ml/calibration.py` (1 062 l.) | en place |
| Optimisation des réglages par performance | `optimization/optuna_v2_tuner.py`, `core/ml/threshold_optimizer.py` | en place, **déclenchée à la main** depuis l'interface |
| Modèles par paire | `optimization/per_symbol_models.py` | en place |
| Détection de dérive (le marché a changé) | `core/ml/drift_detector.py` | en place, alerte seulement |
| Analyse après sortie (ce qui a marché) | `core/analysis/what_if_simulator.py`, module post-exit | en place |

Le trou : la note ML n'entre **pas** dans le calcul du score (`core/analyzer/scoring.py` : 0 mention), et aucun des optimiseurs ne se déclenche tout seul sur la performance observée.

---

## 5. La cible simple que je propose

Cinq boîtes, une seule direction :

1. **Entrées** — prix + carnet (déjà bon, ne rien changer) + 2 signes de marché en plus (voir §6).
2. **Caractéristiques** — un tableau propre d'environ 20 colonnes par paire (score 1 m, score 5 m, spread, volume relatif, ATR, distance aux extrêmes, funding, tendance 5 m). Une seule fonction, ~200 lignes.
3. **Décision** — un seul module, ~300 lignes : le modèle dit *GO / NO GO* + la taille, avec 4 garde-fous non négociables (risque max par trade, nombre max de trades par jour, arrêt sur perte quotidienne, interdiction hors horaires choisis).
4. **Exécution** — le fichier qui parle à MEXC, inchangé (il est correct, il est juste gros).
5. **Journal + revue** — chaque décision enregistrée avec sa raison en une phrase ; chaque semaine, recalcul des seuils sur les trades réels, **puis ton accord** avant d'appliquer.

À comparer : aujourd'hui ~2 500 lignes et 25 réglages remplacent difficilement ~24 700 lignes et 239 champs.

### Dans quel ordre (du moins risqué au plus risqué)

| Étape | Ce qu'on fait | Risque | Gain |
|---|---|---|---|
| 1 | Supprimer les jumeaux et le legacy (une seule version de chaque, les 9 drapeaux sautent) | faible — les 3 336 tests verts servent de filet | le code devient lisible |
| 2 | Extraire la décision de `analyze_pair` dans un module « une entrée, une sortie, une raison » | moyen — on déplace sans rien changer de plus | on peut enfin lire la règle |
| 3 | **Mode fantôme** : le modèle décide en parallèle, rien n'est exécuté, on compare 2 à 4 semaines | zéro — on ne touche pas à l'argent | tu vois s'il aurait fait mieux |
| 4 | Le modèle a le droit de **vetoer** et de **dimensionner**, les garde-fous restent humains | contrôlé | la performance pilote enfin les réglages |

---

## 6. « Analyser le marché actuel » : ce qui est sérieux, et ce qui ne l'est pas

Ton robot garde des positions quelques minutes. Pour cette échelle de temps :

**Utile, gratuit ou presque, et déjà à portée de main :**
- **Funding et intérêts ouverts (open interest)** MEXC : déjà accessibles, disent qui pousse le prix et à quel prix ça fait mal. Le plus prédictif sur quelques minutes.
- **Liquidations** (flux de positions forcées) : explique et annonce les mèches.
- **Fear & Greed index** (alternative.me, sans clé, un appel par jour) : utile pour *réduire* l'exposition les jours de panique, pas pour choisir une entrée.

**Moyennement utile :** titres **CryptoPanic** (API gratuite avec clé) — un signal de news de 5 minutes suffit à justifier une pause du robot.

**Peu sérieux pour du 1 minute :** Reddit et X. L'accès X est payant, et l'attention sociale bouge en heures, pas en minutes : sur ton horizon ça ajoute du bruit, et ça se prête mal à être testé. Mon avis : on commence par funding + intérêts ouverts + liquidations, et on ne met les réseaux sociaux que comme *interrupteur* (coupe le robot sur une nouvelle majeure), jamais comme motif d'entrée.

---

## 7. Ce que je te demande de choisir

1. Étape 1 tout de suite (ménage des jumeaux + legacy) ou d'abord le mode fantôme ?
2. Combien de réglages tu acceptes de garder à la main : je propose **25 ou moins**, tout le reste calculé.
3. Les garde-fous : risque max par trade, nb max de trades/jour, perte max/jour — tu me donnes les 3 chiffres, je les écris en dur dans le code (et plus dans 239 champs).
