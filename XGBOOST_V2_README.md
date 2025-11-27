# 🚀 XGBoost V2 - Machine Learning Amélioré

**Date** : 24 novembre 2025  
**Objectif** : Éliminer le data leakage et améliorer la généralisation du modèle ML  
**Gain estimé** : +10-20% accuracy, meilleure robustesse en production  

---

## 📋 Différences V1 vs V2

| Feature | V1 (Baseline) | V2 (Amélioré) |
|---------|--------------|---------------|
| **Split dataset** | ❌ Random (70/30) | ✅ Temporel (70/10/20) |
| **Data leakage** | ⚠️ Possible | ✅ Éliminé |
| **Validation set** | ❌ Non | ✅ Oui (10%) |
| **Filtrage trades** | ❌ Aucun | ✅ Marginal trades exclus |
| **Feature selection** | ❌ Toutes (81) | ✅ Top-K discriminantes (30) |
| **Overfitting** | ⚠️ Risque élevé | ✅ Réduit (regularization) |
| **Tracking DB** | ❌ JSON seulement | ✅ PostgreSQL + JSON |

---

## 🎯 Problèmes résolus par V2

### 1. ❌ Data Leakage (V1)
**Problème** : Le split random mélange les données passées et futures.
- Trade du 10 nov → Train set
- Trade du 8 nov → Test set  
→ Le modèle "voit" l'avenir pendant l'entraînement !

**Solution V2** : Split temporel
- Train: 1er sept → 28 oct (70%)
- Val: 29 oct → 7 nov (10%)
- Test: 8 nov → 20 nov (20%)  
→ Le modèle ne prédit que le futur inconnu ✅

---

### 2. ⚠️ Bruit dans les données (V1)
**Problème** : Trades marginaux (PNL proche de 0%) sont du bruit.
- WIN: +0.05% → Classé "WIN" mais quasi-aléatoire
- LOSS: -0.08% → Classé "LOSS" mais quasi-aléatoire  
→ Le modèle apprend du bruit au lieu du signal !

**Solution V2** : Filtrage marginal trades
- Exclure |PNL| < 0.15% (configurable)
- Garder seulement les trades "clairs"
  - WIN: +0.50% et plus
  - LOSS: -0.25% et plus  
→ Signal vs bruit amélioré ✅

---

### 3. 🔥 Overfitting (V1)
**Problème** : Trop de features (81) → Le modèle mémorise au lieu de généraliser.
- Train accuracy: 75% ✅
- Test accuracy: 51% ❌ (quasi-aléatoire)  
→ Gap de 24% = Overfitting sévère !

**Solution V2** : Feature selection + Regularization
- Sélectionner top 30 features discriminantes (Mutual Information)
- Hyperparamètres anti-overfitting :
  - `max_depth=5` (au lieu de 6)
  - `reg_alpha=0.5`, `reg_lambda=2.0`
  - `gamma=0.3` (split gain minimum)  
→ Généralisation améliorée ✅

---

## 🛠️ Comment utiliser XGBoost V2

### Méthode 1 : API REST

#### Entraîner un nouveau modèle V2
```bash
curl -X POST http://localhost:5000/api/ml/train_v2 \
  -H "Content-Type: application/json" \
  -d '{
    "timeframe_days": 120,
    "min_trades": 100,
    "filter_marginal_trades": true,
    "marginal_threshold": 0.15,
    "max_features": 30
  }'
```

**Réponse** :
```json
{
  "task_id": "train_v2_1732445123456",
  "message": "Entraînement XGBoost V2 démarré en arrière-plan",
  "params": {
    "timeframe_days": 120,
    "min_trades": 100,
    "filter_marginal_trades": true,
    "marginal_threshold": 0.15,
    "max_features": 30
  }
}
```

#### Vérifier le statut
```bash
curl http://localhost:5000/api/ml/tasks/train_v2_1732445123456
```

**Réponse** :
```json
{
  "status": "completed",
  "progress": 100,
  "results": {
    "metrics": {
      "train": {"accuracy": 0.723, "roc_auc": 0.780},
      "validation": {"accuracy": 0.687, "roc_auc": 0.745},
      "test": {"accuracy": 0.702, "roc_auc": 0.758},
      "gaps": {"accuracy": 0.021, "roc_auc": 0.022}
    }
  }
}
```

---

### Méthode 2 : CLI Python

```bash
cd c:/Users/sebta/Documents/clone\ github/test/test
python -c "
from optimization.models.xgboost_trainer_v2 import XGBoostTrainerV2

trainer = XGBoostTrainerV2(model_name='xgboost_v2')
results = trainer.train(
    timeframe_days=120,
    min_trades=100,
    filter_marginal_trades=True,
    marginal_threshold=0.15,
    max_features=30
)
print(results)
"
```

---

## 📊 Métriques à analyser

### ✅ Bonnes métriques (objectifs V2)

| Métrique | V1 (Baseline) | V2 (Objectif) |
|----------|--------------|---------------|
| **Test Accuracy** | 51% | 65-70% |
| **Test ROC-AUC** | 0.52 | 0.70-0.75 |
| **Accuracy Gap** | 24% | <10% |
| **Val Accuracy** | N/A | 65-68% |

### 🚨 Diagnostic Overfitting

**Scenario 1 : Overfitting sévère**
```
Train: 75% | Val: 60% | Test: 51%
Gap: 24% ❌
→ Action: Augmenter régularisation (reg_alpha, reg_lambda, max_depth)
```

**Scenario 2 : Underfitting**
```
Train: 58% | Val: 57% | Test: 56%
Gap: 2% ⚠️
→ Action: Réduire régularisation, augmenter max_depth
```

**Scenario 3 : Bon équilibre** ✅
```
Train: 72% | Val: 68% | Test: 70%
Gap: 2-5% ✅
→ Modèle prêt pour production !
```

---

## 🗄️ Base de données

### Table `ml_models`

Après l'entraînement, le modèle est automatiquement enregistré dans PostgreSQL :

```sql
SELECT
    model_name,
    version,
    test_accuracy,
    test_roc_auc,
    accuracy_gap,
    split_type,
    filter_marginal_trades,
    trained_at,
    is_active
FROM ml_models
ORDER BY trained_at DESC;
```

**Exemple de résultat** :
```
model_name    | version | test_accuracy | test_roc_auc | accuracy_gap | split_type | filter_marginal_trades | trained_at          | is_active
xgboost_v2    | 2.0     | 0.702         | 0.758        | 0.021        | temporal   | true                   | 2025-11-24 19:15:00 | false
xgboost_v1    | 1.0     | 0.514         | 0.520        | 0.241        | random     | false                  | 2025-11-20 14:30:00 | true
```

---

## 🎨 Activer le modèle V2

### Option 1 : Via Python

```python
from optimization.models.model_logger import set_active_model

set_active_model('xgboost_v2')
```

### Option 2 : Via SQL

```sql
-- Désactiver tous les modèles
UPDATE ml_models SET is_active = FALSE WHERE is_active = TRUE;

-- Activer V2
UPDATE ml_models SET is_active = TRUE WHERE model_name = 'xgboost_v2';
```

### Option 3 : Via API (TODO)

```bash
curl -X POST http://localhost:5000/api/ml/models/xgboost_v2/activate
```

---

## 🔧 Paramètres recommandés

### Configuration par défaut (équilibrée)
```python
{
    "timeframe_days": 120,           # 4 mois de données
    "min_trades": 100,                # Minimum 100 trades
    "filter_marginal_trades": True,   # Filtrer bruit
    "marginal_threshold": 0.15,       # |PNL| < 0.15% exclu
    "max_features": 30,               # Top 30 features
    "n_estimators": 500,              # 500 arbres
    "max_depth": 5,                   # Profondeur 5
    "learning_rate": 0.05,            # Taux 0.05
    "reg_alpha": 0.5,                 # L1 regularization
    "reg_lambda": 2.0,                # L2 regularization
    "gamma": 0.3                      # Min split gain
}
```

### Configuration conservatrice (anti-overfitting)
```python
{
    "max_depth": 3,                   # Très shallow
    "reg_alpha": 1.0,                 # Régularisation forte
    "reg_lambda": 5.0,
    "gamma": 0.5,
    "max_features": 20                # Moins de features
}
```

### Configuration aggressive (performance max)
```python
{
    "max_depth": 7,                   # Plus profond
    "reg_alpha": 0.1,                 # Régularisation faible
    "reg_lambda": 0.5,
    "gamma": 0.1,
    "max_features": 50,               # Plus de features
    "n_estimators": 1000              # Plus d'arbres
}
```

---

## 📈 Top Features (exemple)

Après l'entraînement, V2 affiche les features les plus discriminantes :

```
Top 10 features (Mutual Information):
  1. rsi_1m: 0.0421
  2. macd_hist_1m: 0.0389
  3. adx_1m: 0.0357
  4. di_gap_1m: 0.0331
  5. volume_ratio_1m: 0.0298
  6. bb_distance_to_lower_1m: 0.0276
  7. rsi_5m: 0.0254
  8. atr_pct_1m: 0.0231
  9. ema_diff_pct_1m: 0.0209
  10. config_min_score_required: 0.0187
```

→ **Insights** :
- RSI 1m est la feature la plus discriminante
- Indicateurs 1m > 5m (scalping rapide)
- Config parameters aussi importants !

---

## ⚠️ Migration V1 → V2

### Tester V2 sans impacter V1

1. **Entraîner V2** (ne pas activer) :
   ```python
   trainer = XGBoostTrainerV2(model_name='xgboost_v2')
   trainer.train(...)
   ```

2. **Comparer métriques** :
   ```sql
   SELECT
       model_name,
       test_accuracy,
       test_roc_auc,
       accuracy_gap
   FROM ml_models
   WHERE model_name IN ('xgboost_v1', 'xgboost_v2');
   ```

3. **Si V2 meilleur** :
   - Activer V2 : `set_active_model('xgboost_v2')`
   - Recharger predictor : `get_predictor('xgboost_v2')`

4. **Rollback si problème** :
   - Réactiver V1 : `set_active_model('xgboost_v1')`

---

## 🚀 Prochaines étapes

### Phase 1 : Validation (maintenant)
- ✅ Entraîner V2 avec données actuelles
- ✅ Comparer accuracy V1 vs V2
- ✅ Vérifier gap train-test < 10%

### Phase 2 : Production (si accuracy > 65%)
- Activer V2 dans le bot
- Surveiller prédictions en live
- Analyser impact sur winrate

### Phase 3 : Optimisation Optuna (si nécessaire)
- Tuner hyperparamètres avec `OptunaV2Tuner`
- Objectif : accuracy > 70%

---

## 📝 Checklist avant activation

- [ ] Test accuracy > 65% ✅
- [ ] Accuracy gap < 10% ✅
- [ ] Val accuracy proche de test accuracy ✅
- [ ] Feature importance cohérente ✅
- [ ] Modèle enregistré dans PostgreSQL ✅
- [ ] Predictor rechargé avec V2 ✅
- [ ] `is_active = TRUE` pour V2 ✅

**Prêt pour production ! 🎉**

---

## 🆘 Troubleshooting

### Erreur : "Table ml_models does not exist"
```bash
# Exécuter le script SQL
psql -U postgres -d tradebot -f database/create_ml_models_table.sql
```

### Erreur : "XGBoostTrainerV2 not found"
```bash
# Vérifier imports
python -c "from optimization.models.xgboost_trainer_v2 import XGBoostTrainerV2; print('OK')"
```

### Accuracy < 60%
- Augmenter `timeframe_days` (120 → 180)
- Réduire `marginal_threshold` (0.15 → 0.10)
- Vérifier qualité des données (`ml_features` vue)

---

**🎯 Objectif final** : Accuracy > 70%, Gap < 5%, Modèle robuste en production !
