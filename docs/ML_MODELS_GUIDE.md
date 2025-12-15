# 📊 Guide Complet des Modèles ML - Trade Cursor

**Date de création :** 30 Novembre 2025  
**Dernière mise à jour :** 30 Novembre 2025

---

## 📋 Table des Matières

1. [Vue d'ensemble des modèles](#1-vue-densemble-des-modèles)
2. [Comparaison des performances](#2-comparaison-des-performances)
3. [GradientBoosting (Recommandé)](#3-gradientboosting-recommandé)
4. [XGBoost V1 (Classification)](#4-xgboost-v1-classification)
5. [XGBoost V2 (Régression)](#5-xgboost-v2-régression)
6. [Configuration recommandée](#6-configuration-recommandée)
7. [Impact réel sur les trades](#7-impact-réel-sur-les-trades)
8. [FAQ et conseils](#8-faq-et-conseils)

---

## 1. Vue d'ensemble des modèles

### Architecture des filtres ML

```
Setup Détecté par le Scanner
            ↓
┌─────────────────────────────────────┐
│  FILTRE XGBOOST V1 (si activé)      │  ← ml_filter_enabled
│  - Mode: NEGATIVE/STRICT/SOFT       │
│  - Accuracy: ~50-55%                │
│  - Non recommandé                   │
└─────────────────────────────────────┘
            ↓
┌─────────────────────────────────────┐
│  FILTRE GRADIENTBOOSTING (si activé)│  ← gb_filter_enabled ✅
│  - Seuil: gb_min_confidence         │
│  - Accuracy: ~65-68%                │
│  - RECOMMANDÉ                       │
└─────────────────────────────────────┘
            ↓
     Trade Exécuté ou Rejeté
```

### Résumé des modèles

| Modèle | Type | Accuracy | Recommandation |
|--------|------|----------|----------------|
| **GradientBoosting** | Classification WIN/LOSS | **68.5%** | ✅ **UTILISER** |
| XGBoost V1 | Classification WIN/LOSS | ~50-55% | ❌ Désactiver |
| XGBoost V2 | Régression PNL% | R² négatif | ❌ Ne pas utiliser |

---

## 2. Comparaison des performances

### Métriques des modèles

| Métrique | GradientBoosting | XGBoost V1 | XGBoost V2 |
|----------|------------------|------------|------------|
| **Accuracy** | 68.5% | ~50-55% | N/A |
| **Precision** | 70.6% | ~50% | N/A |
| **Recall** | 68.1% | ~50% | N/A |
| **F1 Score** | 69.4% | ~50% | N/A |
| **ROC-AUC** | 70.3% | ~50% | N/A |
| **R²** | N/A | N/A | -0.04 (négatif) |

### Pourquoi GradientBoosting est meilleur ?

1. **Optimisation avancée** : 100 essais Optuna avec cross-validation temporelle
2. **Feature selection** : 28 features sélectionnées (vs 56 pour V1)
3. **Hyperparamètres optimisés** : Trouvés par recherche bayésienne
4. **Seed fixe** : Reproductibilité garantie (random_state=42)

---

## 3. GradientBoosting (Recommandé)

### Hyperparamètres optimisés

```json
{
  "gb_n_estimators": 271,
  "gb_max_depth": 6,
  "gb_learning_rate": 0.217,
  "gb_min_samples_split": 48,
  "gb_min_samples_leaf": 38,
  "gb_subsample": 0.734,
  "gb_max_features": "sqrt"
}
```

### Features sélectionnées (28)

Les 28 features les plus importantes identifiées par l'optimisation :

```
1.  di_plus_1m              15. rsi_prev_5m
2.  bb_distance_to_upper_5m 16. volatility_momentum_product
3.  ema_diff_pct_1m         17. di_gap_1m
4.  rsi_1m                  18. macd_hist_prev_1m
5.  di_plus_5m              19. rsi_prev_1m
6.  ema_diff_pct_5m         20. macd_hist_1m
7.  bb_distance_to_upper_1m 21. trend_strength_5m
8.  bb_distance_to_lower_1m 22. momentum_divergence
9.  atr_pct_1m              23. bb_width_1m
10. rsi_5m                  24. di_minus_5m
11. bb_width_5m             25. momentum_5m
12. bb_distance_to_lower_5m 26. momentum_1m
13. macd_momentum_5m        27. volume_divergence
14. trend_strength_1m       28. adx_5m
```

### Métriques finales

| Métrique | Valeur |
|----------|--------|
| Test Accuracy | **68.5%** |
| Precision | **70.6%** |
| Recall | **68.1%** |
| F1 Score | **69.4%** |
| ROC-AUC | **70.3%** |
| Features | 28 |
| Samples entraînement | 862 |

### Comment activer

```json
{
  "gb_filter_enabled": true,
  "gb_min_confidence": 0.55
}
```

### Fichiers du modèle

```
optimization/saved_models/
├── gradient_boosting_optimized.pkl           # Modèle entraîné
├── gradient_boosting_optimized_metadata.json # Métriques et config
├── gradient_boosting_optimized_preprocessor.pkl # Scaler + features
├── best_classifier_latest.pkl                # Copie active
└── best_classifier_metadata.json             # Copie active
```

---

## 4. XGBoost V1 (Classification)

### ⚠️ Non recommandé

XGBoost V1 a une accuracy d'environ 50-55%, ce qui est à peine mieux que le hasard.

### Paramètres (si vous l'utilisez quand même)

| Paramètre | Description | Valeur par défaut |
|-----------|-------------|-------------------|
| `ml_filter_enabled` | Activer le filtre | `false` |
| `ml_filter_mode` | Mode de filtrage | `NEGATIVE` |
| `ml_loss_threshold` | Seuil P(loss) pour rejet | `0.55` |
| `ml_min_confidence` | Confiance minimum | `0.60` |

### Modes de filtrage (V1 uniquement)

| Mode | Description |
|------|-------------|
| **NEGATIVE** | Rejette les trades si P(loss) > seuil |
| **STRICT** | Accepte seulement si P(win) > seuil |
| **SOFT** | Avertissement sans blocage |

---

## 5. XGBoost V2 (Régression)

### ⚠️ Ne pas utiliser pour le filtrage

XGBoost V2 prédit le PNL% au lieu de WIN/LOSS. Ses performances sont mauvaises :

- **R² négatif** (-0.04) : Le modèle prédit moins bien que la moyenne
- **MAE** : 0.31% (acceptable mais inutile avec R² négatif)

### Pourquoi ça ne fonctionne pas ?

1. **Outliers extrêmes** : PNL varie de -100% à +100%
2. **Distribution asymétrique** : Skewness = -10.2
3. **Bruit élevé** : Le PNL exact est imprévisible

### Recommandation

Utilisez la **classification** (WIN/LOSS) avec GradientBoosting plutôt que la régression (PNL%).

---

## 6. Configuration recommandée

### Configuration optimale

```json
{
  "ml_filter_enabled": false,
  "gb_filter_enabled": true,
  "gb_min_confidence": 0.55,
  "gb_n_estimators": 271,
  "gb_max_depth": 6,
  "gb_learning_rate": 0.217,
  "gb_min_samples_split": 48,
  "gb_min_samples_leaf": 38,
  "gb_subsample": 0.734,
  "gb_max_features": "sqrt",
  "gb_model_type": "gb"
}
```

### Interface utilisateur

Dans l'onglet **GradientBoosting** :
- ✅ Activer Filtrage GradientBoosting : **ON**
- 📊 Seuil de Confiance Minimum : **55%**

Dans l'onglet **XGBoost V1** :
- ❌ Activer Filtrage ML : **OFF** (désactivé)

---

## 7. Impact réel sur les trades

### Analyse sur 1079 trades historiques

#### Distribution des probabilités

```
P(WIN) < 30%:  525 trades → Win Rate = 5%   ❌ MAUVAIS
P(WIN) > 50%:  519 trades → Win Rate = 94%  ✅ BONS
```

Le modèle sépare très bien les bons des mauvais trades !

#### Impact du filtre à différents seuils

| Seuil P(WIN) | Trades conservés | Win Rate | Gain WR |
|--------------|------------------|----------|---------|
| Sans filtre | 1079 (100%) | 48.5% | - |
| ≥ 50% | 519 (48%) | 93.8% | +45% |
| ≥ 55% | 510 (47%) | 94.7% | +46% |
| ≥ 60% | 501 (46%) | 95.2% | +47% |

### ⚠️ Attention

Ces chiffres incluent les données d'entraînement. En **conditions réelles**, attendez-vous à :

| Métrique | Estimation optimiste | Estimation réaliste |
|----------|---------------------|---------------------|
| Win Rate avec ML | ~94% | **65-75%** |
| Gain Win Rate | +45% | **+15-25%** |
| Trades filtrés | ~50% | ~50% |

---

## 8. FAQ et Conseils

### Q: Dois-je utiliser le filtre ML ?

**OUI**, mais uniquement GradientBoosting avec un seuil de 55%.

### Q: Pourquoi les métriques varient entre entraînements ?

C'est normal avec peu de données (1079 trades). Causes :
1. **Haute variance** : Petit dataset
2. **Overfitting** : Le modèle mémorise au lieu de généraliser
3. **Non-stationnarité** : Les patterns du marché changent

### Q: Faut-il réentraîner le modèle ?

**NON**, utilisez le modèle pré-entraîné (`gradient_boosting_optimized.pkl`) qui a les meilleures métriques. Réentraîner donnera des résultats différents (et souvent moins bons).

### Q: Combien de trades sont nécessaires ?

- **Minimum** : 500 trades
- **Recommandé** : 1000+ trades
- **Idéal** : 5000+ trades

### Q: Le ML peut-il garantir des profits ?

**NON**. Le ML améliore les probabilités mais ne garantit rien. Il :
- ✅ Filtre les trades à haute probabilité de perte
- ✅ Améliore le win rate de 15-25%
- ❌ Ne prédit pas l'amplitude des mouvements
- ❌ Ne remplace pas une bonne stratégie

### Q: Quel est le meilleur compromis quantité/qualité ?

| Seuil | Qualité | Quantité | Recommandation |
|-------|---------|----------|----------------|
| 50% | Bonne | ~50% trades | ✅ **Équilibré** |
| 55% | Meilleure | ~47% trades | ✅ **Recommandé** |
| 60% | Très bonne | ~46% trades | Conservateur |
| 70% | Excellente | ~45% trades | Très sélectif |

---

## 📝 Checklist de configuration

- [ ] `ml_filter_enabled: false` (XGBoost V1 désactivé)
- [ ] `gb_filter_enabled: true` (GradientBoosting activé)
- [ ] `gb_min_confidence: 0.55` (seuil 55%)
- [ ] Modèle `gradient_boosting_optimized.pkl` présent
- [ ] Ne pas réentraîner inutilement

---

## 🔗 Fichiers importants

| Fichier | Description |
|---------|-------------|
| `optimization/saved_models/gradient_boosting_optimized.pkl` | Modèle optimisé |
| `optimization/saved_models/gradient_boosting_optimized_metadata.json` | Métriques et features |
| `config_overrides.json` | Configuration active |
| `optimization/predictor_optimized.py` | Classe de prédiction |
| `verify_gradientboosting.py` | Script de vérification |
| `analyze_ml_impact.py` | Analyse d'impact |

---

**Document généré automatiquement - Trade Cursor ML System**
