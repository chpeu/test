# 💾 Guide Sauvegarde Modèle XGBoost V2

## 📋 Vue d'Ensemble

Le système de sauvegarde du modèle V2 a été **entièrement implémenté**. Désormais, chaque entraînement V2 :

1. ✅ **Sauvegarde le modèle** dans `optimization/saved_models/xgboost_v2_{timestamp}.pkl`
2. ✅ **Sauvegarde le preprocessor** dans `optimization/saved_models/xgboost_v2_{timestamp}_preprocessor.pkl`
3. ✅ **Sauvegarde une copie "latest"** pour faciliter le chargement
4. ✅ **Enregistre dans PostgreSQL** toutes les métadonnées (métriques, hyperparamètres, features sélectionnées)

---

## 🔧 Ce qui a été Modifié

### 1. Migration SQL

**Fichier:** `database/migration_add_v2_regression_metrics.sql`

**Colonnes ajoutées à `ml_models`:**
```sql
-- Métriques R² (coefficient de détermination)
train_r2, val_r2, test_r2

-- Métriques MAE (Mean Absolute Error)
train_mae, val_mae, test_mae

-- Métriques MSE (Mean Squared Error)
train_mse, val_mse, test_mse

-- Métriques classification binaire
test_f1

-- Features sélectionnées
selected_features JSONB
feature_selection_scores JSONB
```

### 2. Code Python

**Fichier:** `api/routes/ml.py`

**Fonction modifiée:** `_train_xgboost_v2_background()`

**Ajouts:**
1. Import de `joblib`, `json`, `datetime`, `Path`
2. Sauvegarde fichiers `.pkl` (modèle + preprocessor)
3. Sauvegarde double: timestamp + "latest"
4. Insertion PostgreSQL avec **toutes** les métadonnées

---

## 📦 Structure Sauvegarde

### Fichiers Créés par Entraînement

```
optimization/saved_models/
├── xgboost_v2_20251125_191530.pkl              # Modèle avec timestamp
├── xgboost_v2_20251125_191530_preprocessor.pkl # Preprocessor avec timestamp
├── xgboost_v2_latest.pkl                       # Modèle "latest"
└── xgboost_v2_latest_preprocessor.pkl          # Preprocessor "latest"
```

### Base de Données PostgreSQL

**Table:** `ml_models`

**Exemple enregistrement:**
```sql
model_name:              xgboost_v2_20251125_191530
model_type:              XGBRegressor
version:                 2.0
model_path:              optimization/saved_models/xgboost_v2_20251125_191530.pkl
preprocessor_path:       optimization/saved_models/xgboost_v2_20251125_191530_preprocessor.pkl

-- Métriques Régression
train_r2:                0.387
val_r2:                  0.256
test_r2:                 0.234
train_mae:               0.32
val_mae:                 0.41
test_mae:                0.45
train_mse:               0.18
val_mse:                 0.24
test_mse:                0.27

-- Métriques Classification Binaire (seuil 0)
test_f1:                 0.623
test_accuracy:           0.654

-- Infos Dataset
total_samples:           1240
train_samples:           868
val_samples:             124
test_samples:            248
timeframe_days:          365
filter_marginal_trades:  TRUE
marginal_threshold:      0.20
split_type:              temporal

-- Hyperparamètres
model_params:            {"n_estimators": 600, "max_depth": 4, ...}

-- Features
max_features:            40
selected_features:       ["rsi_1m", "macd_1m", "bb_width_1m", ...]
feature_selection_scores: {"rsi_1m": 0.082, "macd_1m": 0.071, ...}
feature_importance:      {"rsi_1m": 0.125, "macd_1m": 0.098, ...}

-- Status
is_active:               TRUE
trained_at:              2025-11-25 19:15:30
```

---

## 🚀 Installation et Test

### Étape 1: Appliquer la Migration SQL

**Option A: Via Python**
```bash
python apply_migration_v2.py
```

**Option B: Via psql**
```bash
psql -d trading_db -U postgres -f database/migration_add_v2_regression_metrics.sql
```

**Vérification:**
```sql
SELECT column_name, data_type 
FROM information_schema.columns
WHERE table_name = 'ml_models'
  AND column_name LIKE '%r2%' OR column_name LIKE '%mae%'
ORDER BY column_name;
```

**Résultat attendu:**
```
 column_name | data_type
-------------+-----------
 test_f1     | double precision
 test_mae    | double precision
 test_mse    | double precision
 test_r2     | double precision
 train_mae   | double precision
 train_mse   | double precision
 train_r2    | double precision
 val_mae     | double precision
 val_mse     | double precision
 val_r2      | double precision
```

### Étape 2: Augmenter le Dataset

**Problème actuel:** Dataset trop petit (59 trades après filtrage)

**Solution:** Augmenter `timeframe_days`

```python
# Via UI: Variables V2 → Timeframe Days
ml_v2_timeframe_days = 365  # au lieu de 270
```

**Ou via `config.py`:**
```python
TRADING_CONFIG['ml_v2_timeframe_days'] = 365
```

### Étape 3: Lancer Entraînement V2

**Via UI:**
1. Aller dans **ML Dashboard V2**
2. Section **Variables ML V2**
3. Cliquer **🔄 Réentraîner Modèle V2**
4. Attendre polling (1-2 minutes)

**Via API:**
```bash
curl -X POST http://localhost:8000/api/ml/train_v2
```

**Logs attendus:**
```
🚀 Entraînement V2 en cours (task_id=abc-123)
✅ 1240 trades chargés
✅ 1240 trades après filtrage (100.0%)
✅ Split: Train=868, Val=124, Test=248
✅ 40 features sélectionnées (top mutual info)
✅ Entraînement terminé
📊 R² Test: 0.234, MAE Test: 0.450%, F1: 0.623
💾 Modèle sauvegardé: optimization/saved_models/xgboost_v2_20251125_191530.pkl
💾 Preprocessor sauvegardé: optimization/saved_models/xgboost_v2_20251125_191530_preprocessor.pkl
✅ Modèle V2 sauvegardé dans PostgreSQL: xgboost_v2_20251125_191530
✅ Entraînement V2 terminé (task_id=abc-123)
```

### Étape 4: Vérifier Sauvegarde

**Fichiers:**
```bash
ls -lh optimization/saved_models/xgboost_v2_*
```

**Résultat attendu:**
```
xgboost_v2_20251125_191530.pkl              # ~80 KB
xgboost_v2_20251125_191530_preprocessor.pkl # ~5 KB
xgboost_v2_latest.pkl                       # ~80 KB
xgboost_v2_latest_preprocessor.pkl          # ~5 KB
```

**PostgreSQL:**
```sql
SELECT 
    model_name, 
    version,
    test_r2, 
    test_mae, 
    test_f1,
    total_samples,
    is_active,
    trained_at
FROM ml_models
WHERE model_name LIKE 'xgboost_v2%'
ORDER BY trained_at DESC
LIMIT 5;
```

**Résultat attendu:**
```
 model_name                | version | test_r2 | test_mae | test_f1 | total_samples | is_active | trained_at
---------------------------+---------+---------+----------+---------+---------------+-----------+-------------------
 xgboost_v2_20251125_191530| 2.0     | 0.234   | 0.450    | 0.623   | 1240          | t         | 2025-11-25 19:15:30
```

---

## 🔍 Debugging

### Problème 1: Dataset trop petit

**Erreur:**
```
Dataset trop petit: 59 trades (minimum 100)
```

**Solution:**
```python
# Augmenter timeframe
ml_v2_timeframe_days = 365  # ou 540

# OU réduire filtrage
ml_v2_marginal_threshold = 0.10  # au lieu de 0.20

# OU désactiver filtrage temporairement
ml_v2_filter_marginal_trades = False
```

### Problème 2: Erreur PostgreSQL

**Erreur:**
```
❌ Erreur sauvegarde PostgreSQL: column "test_r2" does not exist
```

**Solution:**
```bash
# Migration non appliquée
python apply_migration_v2.py
```

### Problème 3: Table ml_models n'existe pas

**Erreur:**
```
relation "ml_models" does not exist
```

**Solution:**
```bash
psql -d trading_db -U postgres -f database/create_ml_models_table.sql
```

### Problème 4: Fichiers .pkl non créés

**Erreur:**
```
FileNotFoundError: optimization/saved_models/
```

**Solution:**
```bash
mkdir -p optimization/saved_models
```

---

## 📊 Métriques Sauvegardées

### Régression (Objectif Principal)

| Métrique | Description | Bon Score | Interprétation |
|----------|-------------|-----------|----------------|
| **R²** | % variance expliquée | > 0.20 | 0.23 = modèle explique 23% variance PNL |
| **MAE** | Erreur moyenne absolue | < 0.50% | 0.45 = erreur moyenne 0.45% sur PNL |
| **MSE** | Erreur quadratique moyenne | < 0.30 | 0.27 = pénalise gros écarts |

### Classification (Secondaire)

| Métrique | Description | Bon Score | Interprétation |
|----------|-------------|-----------|----------------|
| **F1** | Équilibre Precision/Recall | > 0.60 | 0.62 = bon compromis WIN/LOSS |
| **Accuracy** | % prédictions correctes | > 0.60 | 0.65 = 65% de trades bien classés |

### Dataset

| Métrique | Description |
|----------|-------------|
| **total_samples** | Nombre total de trades |
| **train_samples** | Trades entraînement (70%) |
| **val_samples** | Trades validation (10%) |
| **test_samples** | Trades test (20%) |

---

## 🎯 Prochaines Étapes

### Priorité 1: Predictor V2 (URGENT)

**Objectif:** Charger le modèle sauvegardé pour faire des prédictions en live

**Fichier:** `optimization/predictor_v2.py` (à créer)

**Fonctionnalités:**
```python
class MLPredictorV2:
    def load_model(self):
        """Charger latest model depuis saved_models/"""
        
    def predict(self, features: pd.DataFrame) -> float:
        """Prédire PNL% pour un setup"""
        
    def should_filter(self, features: pd.DataFrame) -> bool:
        """TRUE si PNL prédit < seuil minimum"""
```

**Usage:**
```python
# core/position_manager.py
predictor_v2 = MLPredictorV2()
predicted_pnl = predictor_v2.predict(features)

if predicted_pnl < TRADING_CONFIG['ml_v2_min_expected_pnl']:
    return "ML V2: PNL prédit trop faible"
```

### Priorité 2: UI Indicateurs

**Dashboard ML V2:**
- Badge "Modèle V2 Actif" / "Aucun Modèle V2"
- Nom du modèle actuel: `xgboost_v2_20251125_191530`
- Date entraînement: `2025-11-25 19:15:30`
- Métriques: R² = 0.234, MAE = 0.45%
- Nombre features: 40/81

### Priorité 3: Versioning

**Historique Modèles:**
```sql
SELECT 
    model_name,
    version,
    test_r2,
    test_mae,
    total_samples,
    trained_at,
    is_active
FROM ml_models
WHERE model_name LIKE 'xgboost_v2%'
ORDER BY trained_at DESC;
```

**UI:** Permettre de réactiver un ancien modèle si meilleur

---

## 💡 FAQ

### Q: Pourquoi sauvegarder 2 fois (timestamp + latest) ?

**R:** 
- **Timestamp:** Versioning, historique, comparaison
- **Latest:** Facilite chargement (pas besoin chercher le dernier)

### Q: Pourquoi PostgreSQL ET fichiers .pkl ?

**R:**
- **Fichiers .pkl:** Modèle réel (poids, structure)
- **PostgreSQL:** Métadonnées (métriques, features, comparaison)

### Q: Que se passe-t-il si erreur PostgreSQL ?

**R:** Les fichiers .pkl sont quand même sauvegardés. Le modèle est utilisable, mais les métadonnées manquent.

### Q: Comment charger un modèle ancien ?

**R:**
```python
import joblib

model = joblib.load('optimization/saved_models/xgboost_v2_20251125_191530.pkl')
preprocessor = joblib.load('optimization/saved_models/xgboost_v2_20251125_191530_preprocessor.pkl')
```

### Q: Pourquoi `is_active = TRUE` pour un seul modèle ?

**R:** Garantit qu'un seul modèle V2 est utilisé pour les prédictions à la fois.

---

## ✅ Checklist Validation

- [ ] Migration SQL appliquée
- [ ] Colonnes V2 (test_r2, test_mae, etc.) créées
- [ ] Dataset >= 100 trades (`ml_v2_timeframe_days = 365`)
- [ ] Entraînement V2 lancé avec succès
- [ ] Fichiers .pkl créés dans `saved_models/`
- [ ] Modèle enregistré dans PostgreSQL (`SELECT * FROM ml_models`)
- [ ] Métriques visibles: R² > 0.20, MAE < 0.50%
- [ ] Logs "✅ Modèle V2 sauvegardé dans PostgreSQL"
- [ ] Frontend affiche métriques après polling

---

**Dernière mise à jour:** 25 novembre 2025, 19:30 UTC+01:00  
**Auteur:** Cascade AI  
**Version:** 1.0
