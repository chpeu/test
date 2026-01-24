# Analyse du Mode TP/SL Fixe

Ce document présente une analyse détaillée du mode de trading avec Take Profit (TP) et Stop Loss (SL) fixes, à la recherche de bugs potentiels et de points d'amélioration.

## Overview of Current Implementation

### `core/position/tp_sl_calculator.py`
Ce fichier contient la logique principale de calcul des niveaux de Take Profit et Stop Loss.
- **`TPSLConfig`**: Définit les pourcentages fixes `fixed_tp_pct` (défaut 0.6) et `fixed_sl_pct` (défaut 0.25).
- **`calculate_fixed_levels(entry, direction, config)`**:
    - Valide que `entry > 0` et que les pourcentages `fixed_sl_pct`/`fixed_tp_pct` sont `> 0`.
    - Calcule les niveaux initiaux de `sl` et `tp` en se basant sur les pourcentages fixes par rapport au prix d'entrée (`entry`).
        - Pour `LONG`: `sl = entry * (1 - sl_pct / 100)`, `tp = entry * (1 + tp_pct / 100)`
        - Pour `SHORT`: `sl = entry * (1 + sl_pct / 100)`, `tp = entry * (1 - tp_pct / 100)`
    - Ajuste la précision des arrondis (`precision`) en fonction de la magnitude du prix d'entrée.
    - Effectue des vérifications de tolérance avant et après l'arrondi pour s'assurer que les niveaux ne sont pas trop proches du prix d'entrée.
    - **"FIX" (lignes 111-125)**: Une section tente de garantir que le SL arrondi n'est jamais "plus large" (moins protecteur) que le SL configuré, en ajustant le `sl_rounded` si nécessaire pour le rapprocher de l'entrée.
    - **Recalcul Post-Arrondi (lignes 130-167)**: Si après l'arrondi, la différence entre SL/TP et l'entrée est trop faible, le système recalcule les niveaux en forçant une `min_diff_pct` plus élevée (0.1%, 0.15% ou 0.2%), ce qui peut modifier les pourcentages fixes initialement configurés.

### `core/position_manager.py`
Ce fichier est le gestionnaire de positions qui intègre le calcul TP/SL et gère le cycle de vie d'une position.
- **`PositionConfig`**: Contient également `fixed_tp_pct` et `fixed_sl_pct`.
- **`_init_modules`**: Initialise le `TPSLConfig` pour `tp_sl_calculator` en utilisant les valeurs de `PositionConfig`.
- **`open_position`**:
    - Valide les pourcentages fixes de la configuration de position.
    - Détermine le `tp_sl_mode` (FIXE, ATR, ESCALIER) à partir de la configuration effective.
    - Si `tp_sl_mode` est `FIXE`, il appelle `calculate_fixed_levels`.
    - **`_enforce_fixe_sl_not_wider`**: Cette méthode est appelée après la création de l'objet `Position`. Elle vérifie si la distance actuelle du SL (en pourcentage) est devenue plus large que `sl_percent_at_entry` et, si oui, ajuste le SL pour le resserrer.
    - **Recalcul après exécution Live**: Si le prix d'entrée réel (`entry_fill_price`) dans le trading live diffère du prix d'entrée initial, les niveaux TP/SL sont recalculés via `calculate_fixed_levels` pour s'adapter au prix d'exécution réel. `_enforce_fixe_sl_not_wider` est appelé à nouveau.

### `scripts/utilities/debug_tpsl.py`
Un script de débogage qui teste directement la fonction `calculate_fixed_levels` et compare les pourcentages réels de SL/TP calculés aux pourcentages configurés, avec une tolérance de 0.01%.

## Identified Potential Issues/Bugs

1.  **Ajustement Dynamique des Pourcentages "Fixes"**:
    -   **Localisation**: `core/position/tp_sl_calculator.py`, lignes 130-167.
    -   **Problème**: La logique de recalcul post-arrondi peut forcer un `min_diff_pct` plus élevé si les niveaux calculés sont trop proches de l'entrée. Cela signifie que le `fixed_sl_pct` et `fixed_tp_pct` configurés par l'utilisateur peuvent être augmentés dynamiquement. Bien que cela prévienne des niveaux TP/SL invalides (trop proches de l'entrée), le terme "fixe" peut être trompeur si les pourcentages réels sont ajustés sans information claire à l'utilisateur.
    -   **Exemple**: Un utilisateur configure `fixed_sl_pct = 0.05%`. Le système pourrait le transformer en un SL de 0.1% ou 0.2% si la `entry` est trop petite ou à cause de la précision.

2.  **Redondance et Comportement du `_enforce_fixe_sl_not_wider`**:
    -   **Localisation**: `core/position_manager.py`, méthode `_enforce_fixe_sl_not_wider` et ses appels.
    -   **Problème**: La fonction `calculate_fixed_levels` inclut déjà une logique pour empêcher le SL d'être plus large que configuré (`tp_sl_calculator.py`, lignes 111-125). Le fait que `_enforce_fixe_sl_not_wider` soit nécessaire dans `PositionManager` suggère soit que la première correction est insuffisante, soit que le SL peut être modifié entre ces deux appels.
    -   Un ajustement du `desired_sl` pour éviter qu'il ne croise le `current_price` (lignes 304-309 de `position_manager.py`) pourrait, dans certains cas extrêmes (quand `current_price` est très proche de l'entrée et de l'SL initial), rapprocher le SL encore plus de l'entrée, ce qui augmenterait le risque au lieu de le réduire.

3.  **Initialisation Potentiellement Incorrecte de `sl_percent_at_entry`**:
    -   **Localisation**: `core/position_manager.py`, ligne 881: `sl_percent_at_entry = float(trading_params.get('sl_percent'))`.
    -   **Problème**: La variable `trading_params` n'est pas clairement définie dans ce contexte, ce qui pourrait entraîner une valeur `None` ou une erreur si `sl_percent` n'est pas trouvé. Si `sl_percent_at_entry` est mal initialisé, la logique de `_enforce_fixe_sl_not_wider` qui s'y réfère pourrait être défaillante ou utiliser une valeur incorrecte.

## Recommendations (Non-Code-Modifying)

1.  **Clarifier le Comportement "Fixe"**:
    -   **Action**: Mettre à jour la documentation (ex: dans un README.md ou section pertinente) pour expliquer que les pourcentages TP/SL fixes peuvent être dynamiquement ajustés à la hausse par le système pour garantir une distance minimale de l'entrée, en particulier pour des pourcentages très faibles ou des actifs à forte valeur unitaire. Cela devrait informer l'utilisateur des limites du mode "fixe".
    -   **Considération**: Ajouter une option de configuration (`strict_fixed_mode: bool`) qui, si activée, lèverait une erreur ou une alerte au lieu d'ajuster automatiquement les pourcentages, laissant la décision à l'utilisateur.

2.  **Audit de la Redondance et du Comportement de `_enforce_fixe_sl_not_wider`**:
    -   **Action**: Ajouter des logs plus granulaires dans `tp_sl_calculator.py` (autour des lignes 111-125) pour tracer les valeurs du SL avant et après l'ajustement anti-élargissement.
    -   **Action**: Ajouter des logs dans `PositionManager.open_position` pour afficher la valeur du SL et de `sl_percent_at_entry` juste avant l'appel à `_enforce_fixe_sl_not_wider` et si cette fonction apporte des modifications.
    -   **Analyse**: Utiliser ces logs pour déterminer si le SL est réellement modifié entre les deux points d'application de la logique anti-élargissement, et identifier les scénarios qui déclenchent ces modifications. Simplifier ou fusionner ces logiques si possible pour une meilleure clarté et moins de points d'erreur.

3.  **Fiabiliser l'Initialisation de `sl_percent_at_entry`**:
    -   **Action**: Recommander de s'assurer que `sl_percent_at_entry` est toujours initialisé avec la valeur `self.tpsl_config.fixed_sl_pct` (qui est déjà configurée et validée) lorsque le mode `FIXE` est actif. Cela garantirait que `_enforce_fixe_sl_not_wider` utilise la référence correcte.

4.  **Améliorer le Logging Général**:
    -   **Action**: Ajouter des messages de log de niveau INFO/WARNING dans `calculate_fixed_levels` chaque fois qu'un ajustement est effectué (précision, `min_diff_pct` forcé, SL ajusté anti-élargissement). Ces logs devraient clairement indiquer la valeur configurée et la valeur finale utilisée, ainsi que la raison de l'ajustement.
    -   **Action**: Étendre le script `debug_tpsl.py` pour tester plus de cas limites, notamment avec de très petites `fixed_sl_pct` et `fixed_tp_pct` pour des `entry` prices très différents (petits, grands).
