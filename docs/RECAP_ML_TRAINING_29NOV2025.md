# Récapitulatif Discussion ML Training - 29 Novembre 2025

## 1. Problème Initial

Tu as constaté des incohérences dans les résultats d'entraînement GradientBoosting :
- **Tes paramètres manuels** semblaient meilleurs qu'Optuna
- **Overfitting gap** affiché : 18.4% dans l'UI vs 39.3% dans mon analyse
- **Nombre de trades** : UI montrait 1562 "ML utilisables" mais training utilisait 673

---

## 2. Cause Racine Identifiée

### Le training utilisait une table obsolète

```
Table "ml_features"        → 2938 trades (données complètes, mises à jour)
Table "ml_features_clean"  → 673 trades  (copie figée, JAMAIS mise à jour)
                                ↑
                        Le training utilisait cette table !
```

### Pourquoi l'UI montrait 1562 et le training 673 ?

L'UI calculait à partir de `ml_features` avec filtres :
```
2938 - 128 (manuels) - 1248 (configs différentes) = 1562
```

Le training chargeait directement `ml_features_clean` sans filtre = 673 trades figés.

---

## 3. Corrections Apportées

### 3.1 Training et Optuna utilisent maintenant `ml_features`

```python
# AVANT (bugué)
base_df = load_features_from_postgres(use_clean_data=True)  # → 673 trades

# APRÈS (corrigé)
base_df = load_features_from_postgres(use_clean_data=False)  # → 2938 trades
```

### 3.2 Filtre STRICT sur la config actuelle

Le filtre inclut maintenant **TOUS les paramètres d'entrée** stockés :

| Paramètre | Tolérance |
|-----------|-----------|
| min_score_required | ± 0.1 |
| snr_threshold | ± 0.02 |
| volume_multiplier | ± 0.05 |
| use_confluence | exacte |
| atr_min_1m | ± 0.05 |
| atr_max_1m | ± 0.1 |
| atr_min_5m | ± 0.05 |
| atr_max_5m | ± 0.2 |

### 3.3 Évolution automatique

Chaque nouveau trade exécuté avec la config actuelle sera automatiquement inclus dans les futurs entraînements.

---

## 4. État Actuel des Données

### Répartition par config dans `ml_features`

| Config | Trades |
|--------|--------|
| min_score=6.5, snr=0.15, vol=0.95, confluence=true | **691** |
| min_score=7.5, snr=0.25, vol=0.95, confluence=false | 662 |
| min_score=1.0, snr=0.25, vol=0.5, confluence=false | 59 |
| NULL (anciens trades sans tracking) | 1510 |
| Autres | 16 |
| **TOTAL** | **2938** |

### Avec ta config actuelle

```
min_score_required = 6.5
snr_threshold = 0.15
volume_multiplier = 0.95
use_confluence = true
optimal_atr_min_1m = 0.12
optimal_atr_max_1m = 0.75
optimal_atr_min_5m = 0.22
optimal_atr_max_5m = 1.4

→ 691 trades correspondent exactement
→ WIN: 339 (49.1%) / LOSS: 352 (50.9%)
```

---

## 5. Paramètres TP/SL

### Ce qui est stocké vs ce qui ne l'est pas

| Paramètre | Stocké dans ml_features ? | Affecte |
|-----------|---------------------------|---------|
| min_score_required | ✅ Oui | Entrée |
| snr_threshold | ✅ Oui | Entrée |
| volume_multiplier | ✅ Oui | Entrée |
| use_confluence | ✅ Oui | Entrée |
| atr_min/max | ✅ Oui | Entrée |
| **tp_percent** | ❌ Non | Sortie |
| **sl_percent** | ❌ Non | Sortie |
| **trailing_distance** | ❌ Non | Sortie |

### Explication

- **Paramètres d'entrée** → Décident SI un trade est pris
- **Paramètres de sortie (TP/SL)** → Décident du RÉSULTAT (WIN/LOSS)

Le `target_win` stocké reflète déjà le TP/SL actif au moment de la clôture du trade.

**Question ouverte** : Veux-tu que j'ajoute les colonnes TP/SL pour filtrer aussi sur ces paramètres dans les futurs trades ?

---

## 6. Explication Overfitting Gap

### Pourquoi 18.4% dans l'UI vs 39.3% dans mon test ?

**Modèle actuel (metadata)** :
```
train_acc = 79.8%
test_acc = 61.4%
gap = 18.4%  ← Ce que l'UI affiche
```

Le gap de 18.4% est réel pour CE modèle car :
- HistGradientBoosting avec `early_stopping=True` arrête l'entraînement avant de sur-apprendre
- Train accuracy reste à 79.8% au lieu de 100%

**Ma vérification (paramètres agressifs)** :
```
train_acc = 98.1%
test_acc = 59.0%
gap = 39.1%  ← Sans early stopping
```

---

## 7. Influence Nombre/Qualité des Trades

### Impact sur l'entraînement

| Trades | Risque |
|--------|--------|
| < 500 | ⚠️ Haute variance, overfitting facile |
| 500-1000 | ⚠️ Résultats instables entre runs |
| 1000-2000 | ✅ Bon équilibre |
| > 2000 | ✅ Patterns stables |

### Impact sur Optuna

Avec peu de trades :
- Optuna peut trouver des params qui "marchent par chance"
- Ces params ne généralisent pas en production

Avec plus de trades :
- Optuna trouve des patterns réels
- Params plus robustes

---

## 8. Fichiers Modifiés

### `api/routes/ml.py`

1. **Training GB** : Utilise `ml_features` avec filtre config complet
2. **Optuna** : Même logique de chargement et filtrage
3. **Timeframe** : Configurable via `gb_timeframe_days` (défaut 730 jours)

### `utils/config_persistence.py`

- Accepte les nouvelles clés avec préfixes `gb_`, `ml_`, `xgb_`, `optuna_`

---

## 9. Actions à Faire

### Immédiat
- [ ] Redémarrer le backend pour appliquer les corrections

### À tester
- [ ] Lancer un entraînement GB → Vérifier les logs (devrait montrer 691 trades)
- [ ] Lancer une optimisation Optuna → Même dataset que le training

### À décider
- [ ] Ajouter colonnes TP/SL à la table ml_features ?
- [ ] Faut-il utiliser les trades NULL (1510) ou seulement la config actuelle (691) ?

---

## 10. Résumé Simple

```
AVANT:
- Training utilisait 673 trades figés (table obsolète)
- Optuna et Training utilisaient des données différentes de l'UI
- Pas de filtre sur la config actuelle

APRÈS:
- Training utilise ml_features (table à jour)
- Filtre STRICT sur TOUS les paramètres de config
- Training et Optuna utilisent exactement les mêmes données
- Nombre de trades évolue automatiquement avec les nouveaux trades

→ Avec ta config actuelle : 691 trades
→ WIN rate : 49.1%
```
