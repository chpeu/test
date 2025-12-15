# 🚀 Guide Déploiement Complet - XGBoost V2 Enhanced

## 📋 Table des Matières

1. [Prérequis](#1-prérequis)
2. [Installation Dépendances](#2-installation-dépendances)
3. [Configuration PostgreSQL](#3-configuration-postgresql)
4. [Tests de Validation](#4-tests-de-validation)
5. [Entraînement Modèle V2 Enhanced](#5-entraînement-modèle-v2-enhanced)
6. [Optimisation Optuna](#6-optimisation-optuna)
7. [Déploiement Production](#7-déploiement-production)
8. [Monitoring & Maintenance](#8-monitoring--maintenance)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Prérequis

### 1.1 Environnement Système

```bash
# Vérifier Python version (≥ 3.9)
python --version  # Python 3.9+

# Vérifier PostgreSQL (≥ 12)
psql --version  # PostgreSQL 12+

# Vérifier espace disque (≥ 2GB libre)
df -h

# Vérifier RAM (≥ 4GB recommandé)
free -h
```

### 1.2 Base de Code

**Branche actuelle** : `claude/xgboost-improvements-01GTr3rvY76jSmsNyHN94zvE`

```bash
# Vérifier branche
git branch --show-current

# Si pas sur la bonne branche:
git checkout claude/xgboost-improvements-01GTr3rvY76jSmsNyHN94zvE

# Pull latest
git pull origin claude/xgboost-improvements-01GTr3rvY76jSmsNyHN94zvE
```

### 1.3 Données Minimales

**Requirement** : ≥ 100 trades fermés dans PostgreSQL

```sql
-- Vérifier nombre de trades
SELECT COUNT(*) FROM trades WHERE timestamp_exit IS NOT NULL AND win IS NOT NULL;
-- Résultat attendu: ≥ 100

-- Vérifier vue ml_features
SELECT COUNT(*) FROM ml_features;
-- Résultat attendu: ≥ 100
```

---

## 2. Installation Dépendances

### 2.1 Environnement Virtuel (Recommandé)

```bash
# Créer venv
python -m venv venv_ml

# Activer
# Linux/Mac:
source venv_ml/bin/activate
# Windows:
venv_ml\Scripts\activate
```

### 2.2 Installer Packages ML

```bash
# Installer dépendances ML
pip install -r requirements_ml.txt

# Vérifier installations
python -c "import pandas, numpy, sklearn, xgboost, lightgbm, optuna; print('✅ All ML packages installed')"
```

**Contenu `requirements_ml.txt`** :
```
pandas>=2.0.0
numpy>=1.24.0
scikit-learn>=1.3.0
xgboost>=2.0.0
lightgbm>=4.0.0
joblib>=1.3.0
psycopg2-binary>=2.9.0
sqlalchemy>=2.0.0
optuna>=3.0.0
matplotlib>=3.7.0  # optionnel
seaborn>=0.12.0     # optionnel
scipy>=1.11.0
```

### 2.3 Vérifier Imports

```bash
python <<EOF
import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
import optuna
import psycopg2
from sqlalchemy import create_engine

print("✅ Tous les imports fonctionnent")
EOF
```

---

## 3. Configuration PostgreSQL

### 3.1 Variables d'Environnement

Créer fichier `.env` à la racine :

```bash
# .env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=trade_cursor_ml
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password_here
```

```bash
# Tester connexion
python <<EOF
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv('POSTGRES_HOST'),
    port=os.getenv('POSTGRES_PORT'),
    database=os.getenv('POSTGRES_DB'),
    user=os.getenv('POSTGRES_USER'),
    password=os.getenv('POSTGRES_PASSWORD')
)
print("✅ Connexion PostgreSQL réussie")
conn.close()
EOF
```

### 3.2 Vérifier Vue ml_features

```sql
-- Depuis psql ou pgAdmin
SELECT * FROM ml_features LIMIT 5;

-- Vérifier colonnes critiques
SELECT
    COUNT(*) AS total_rows,
    COUNT(target_win) AS rows_with_label,
    COUNT(rsi_1m) AS rows_with_rsi,
    COUNT(timestamp) AS rows_with_timestamp
FROM ml_features;
```

**Attendu** :
- `total_rows` ≥ 100
- `rows_with_label` ≥ 100
- `rows_with_rsi` ≥ 100
- `rows_with_timestamp` ≥ 100

### 3.3 Créer Vue si Absente

```bash
# Si vue ml_features n'existe pas
psql -U postgres -d trade_cursor_ml -f database/create_ml_view.sql
```

---

## 4. Tests de Validation

### 4.1 Test Chargement Données

```bash
python <<EOF
from optimization.data.feature_loader import load_features_from_postgres

df = load_features_from_postgres(min_trades=50, timeframe_days=90)
print(f"✅ {len(df)} trades chargés")
print(f"✅ {len(df.columns)} colonnes")
print(f"✅ Colonnes: {list(df.columns[:10])}")
EOF
```

**Attendu** :
- ≥ 50 trades chargés
- ≥ 50 colonnes
- Pas d'erreur

### 4.2 Test Feature Engineering

```bash
python <<EOF
from optimization.data.feature_loader import load_features_from_postgres
from optimization.data.feature_engineering_advanced import calculate_all_advanced_features

base_df = load_features_from_postgres(min_trades=50, timeframe_days=90)
df_enhanced = calculate_all_advanced_features(base_df)

print(f"✅ Features base: {len(base_df.columns)}")
print(f"✅ Features enhanced: {len(df_enhanced.columns)}")
print(f"✅ Nouvelles features ajoutées: {len(df_enhanced.columns) - len(base_df.columns)}")
EOF
```

**Attendu** :
- Features enhanced ≥ 150
- Nouvelles features ≥ 60
- Pas d'erreur

### 4.3 Test Temporal Split

```bash
python <<EOF
from optimization.data.feature_loader import load_features_from_postgres
from optimization.utils.temporal_split import temporal_train_test_split

df = load_features_from_postgres(min_trades=50, timeframe_days=90)
train, val, test = temporal_train_test_split(df, test_size=0.2, validation_size=0.1)

print(f"✅ Train: {len(train)} samples")
print(f"✅ Val: {len(val)} samples")
print(f"✅ Test: {len(test)} samples")
print(f"✅ Total: {len(train) + len(val) + len(test)}")
EOF
```

**Attendu** :
- Train ≥ 35 samples (70%)
- Val ≥ 5 samples (10%)
- Test ≥ 10 samples (20%)
- Total = nombre initial

---

## 5. Entraînement Modèle V2 Enhanced

### 5.1 Entraînement Complet

```bash
# Mode simple (defaults)
python optimization/models/train_enhanced.py
```

**Durée estimée** : 3-5 minutes

**Sortie attendue** :
```
🚀 XGBOOST V2 ENHANCED - Version Ultime
✅ 1395 trades de qualité
✅ 200+ features → 40 sélectionnées
📈 RÉSULTATS TEST:
  - Accuracy:  0.705  🎉
  - ROC-AUC:   0.753  🎉
  - F1 Score:  0.681  ✅
📊 GAPS: Accuracy=0.018 ✅
💾 Modèle sauvegardé: xgboost_v2_enhanced.pkl
```

### 5.2 Vérifier Fichiers Générés

```bash
ls -lh optimization/saved_models/xgboost_v2_enhanced*

# Attendu:
# xgboost_v2_enhanced.pkl              (modèle)
# xgboost_v2_enhanced_preprocessor.pkl (preprocessor)
# xgboost_v2_enhanced_metadata.json    (metadata)
```

### 5.3 Analyser Résultats

```bash
# Voir métriques
cat optimization/saved_models/xgboost_v2_enhanced_metadata.json | jq '.metrics'

# Voir top features
cat optimization/saved_models/xgboost_v2_enhanced_metadata.json | jq '.feature_importance[:10]'
```

### 5.4 Critères de Succès

| Métrique | Seuil Min | Seuil Optimal | Votre Résultat |
|----------|-----------|---------------|----------------|
| **Test Accuracy** | ≥ 60% | ≥ 70% | ____% |
| **Test ROC-AUC** | ≥ 65% | ≥ 75% | ____% |
| **Gap Train-Test** | < 15% | < 5% | ____% |
| **F1 Score** | ≥ 60% | ≥ 68% | ____% |

✅ **Si Test Accuracy ≥ 70%** → Succès ! Passer à l'étape 6

⚠️ **Si Test Accuracy < 65%** → Voir [Section 9 Troubleshooting](#9-troubleshooting)

---

## 6. Optimisation Optuna

### 6.1 Optuna V2 Enhanced (Recommandé)

**Utilise temporal split + toutes améliorations V2**

```bash
# 50 trials (rapide, ~15-30 min)
python <<EOF
from optimization.optuna_v2_tuner import run_optuna_v2_optimization

results = run_optuna_v2_optimization(
    n_trials=50,
    max_features=40,
    save_config=True
)

print(f"✅ Best score: {results['best_score']:.4f}")
print(f"✅ Meilleurs params sauvegardés dans config_overrides.json")
EOF
```

**Durée** : 15-30 minutes (50 trials)

### 6.2 Optuna V1 (Legacy, non recommandé)

**Attention** : Utilise StratifiedKFold (data leakage temporel)

```bash
# Seulement si vous voulez comparer avec ancien système
python <<EOF
from ml.hyperparameter_tuning import run_optimization

results = run_optimization(
    n_trials=50,
    max_samples=None,
    save_config=False  # Ne pas écraser V2
)
EOF
```

### 6.3 Vérifier Paramètres Sauvegardés

```bash
# Voir section ml_params_to_apply
cat config_overrides.json | jq '.ml_params_to_apply'
```

**Exemple** :
```json
{
  "max_depth": 5,
  "min_child_weight": 3,
  "reg_alpha": 0.8,
  "reg_lambda": 2.5,
  "learning_rate": 0.045,
  "n_estimators": 400,
  "_source": "optuna_v2_enhanced",
  "_metric": "trading_composite",
  "_optimized_at": "2025-11-24T12:00:00"
}
```

### 6.4 Réentraîner avec Meilleurs Params

```bash
# Le modèle V2 Enhanced charge automatiquement depuis config_overrides.json
python optimization/models/train_enhanced.py
```

---

## 7. Déploiement Production

### 7.1 Checklist Pré-Déploiement

- [ ] Test Accuracy ≥ 70%
- [ ] Gap Train-Test < 15%
- [ ] Fichiers modèle présents (`.pkl` + `_metadata.json`)
- [ ] Tests de validation passés (sections 4.1-4.3)
- [ ] Backup de l'ancien modèle (si existant)

### 7.2 Backup Ancien Modèle

```bash
# Si modèle existant
if [ -f optimization/saved_models/xgboost_v1.pkl ]; then
    mkdir -p optimization/saved_models/backups
    cp optimization/saved_models/xgboost_v1* optimization/saved_models/backups/
    echo "✅ Backup ancien modèle créé"
fi
```

### 7.3 Déployer Nouveau Modèle

**Option A : Remplacer modèle V1**

```bash
# Renommer V2 Enhanced → V1 (pour compatibilité API existante)
cp optimization/saved_models/xgboost_v2_enhanced.pkl \
   optimization/saved_models/xgboost_v1.pkl

cp optimization/saved_models/xgboost_v2_enhanced_preprocessor.pkl \
   optimization/saved_models/xgboost_v1_preprocessor.pkl

cp optimization/saved_models/xgboost_v2_enhanced_metadata.json \
   optimization/saved_models/xgboost_v1_metadata.json

echo "✅ Modèle V2 Enhanced déployé comme V1"
```

**Option B : Utiliser V2 directement**

Modifier code API pour charger `xgboost_v2_enhanced` au lieu de `xgboost_v1`

### 7.4 Test Post-Déploiement

```bash
# Test chargement modèle
python <<EOF
import joblib

model = joblib.load('optimization/saved_models/xgboost_v1.pkl')
preprocessor = joblib.load('optimization/saved_models/xgboost_v1_preprocessor.pkl')

print("✅ Modèle chargé avec succès")
print(f"✅ Type modèle: {type(model)}")
EOF
```

### 7.5 Redémarrer Services

```bash
# Si serveur API
# systemctl restart trading_api  # Adapter selon votre setup

# Ou
# docker-compose restart api

# Vérifier logs
tail -f logs/api.log  # Adapter selon votre setup
```

---

## 8. Monitoring & Maintenance

### 8.1 Métriques à Surveiller

**En Production** :

| Métrique | Fréquence | Alerte Si |
|----------|-----------|-----------|
| **Accuracy Réelle** | Hebdo | < 60% |
| **Win Rate** | Quotidien | < 45% |
| **Avg PNL** | Quotidien | < 0% |
| **Nombre Trades** | Quotidien | < 5/jour |

### 8.2 Réentraînement Périodique

**Recommandation** : Réentraîner tous les **30 jours** (market drift)

```bash
# Créer cron job (Linux/Mac)
crontab -e

# Ajouter ligne:
# 0 2 1 * * cd /path/to/project && /path/to/venv/bin/python optimization/models/train_enhanced.py >> logs/retrain.log 2>&1
```

### 8.3 Logs d'Entraînement

```bash
# Sauvegarder logs
python optimization/models/train_enhanced.py 2>&1 | tee logs/training_$(date +%Y%m%d).log
```

### 8.4 Monitoring Dashboard (Optionnel)

Créer dashboard avec :
- Accuracy historique
- Distribution prédictions
- Feature importance evolution
- Gap train-test

---

## 9. Troubleshooting

### 9.1 Accuracy < 65%

**Causes possibles** :
1. Pas assez de données (< 100 trades)
2. Labels bruités (trades marginaux)
3. Features non-discriminantes
4. Overfitting (gap > 15%)

**Actions** :

```bash
# 1. Lancer EDA pour diagnostic
python -m optimization.analysis.eda_trading

# 2. Augmenter filtrage marginal trades
# Éditer train_enhanced.py ligne 434:
# marginal_threshold=0.20  # Au lieu de 0.15

# 3. Réduire features si overfitting
# Éditer train_enhanced.py ligne 436:
# max_features=30  # Au lieu de 40
```

### 9.2 Overfitting (Gap > 15%)

```bash
# Augmenter régularisation dans config_overrides.json
{
  "ml_reg_alpha": 2.0,  # Au lieu de 0.5
  "ml_reg_lambda": 5.0,  # Au lieu de 2.0
  "ml_max_depth": 4,     # Au lieu de 5
}

# Réentraîner
python optimization/models/train_enhanced.py
```

### 9.3 Erreur Imports

```bash
# ModuleNotFoundError: No module named 'xxx'
pip install xxx

# Si persiste, réinstaller tout
pip install -r requirements_ml.txt --force-reinstall
```

### 9.4 Erreur PostgreSQL

```bash
# Connexion refusée
# 1. Vérifier PostgreSQL en cours
sudo systemctl status postgresql

# 2. Vérifier .env
cat .env

# 3. Tester connexion manuelle
psql -U postgres -d trade_cursor_ml -h localhost

# 4. Vérifier vue ml_features
psql -U postgres -d trade_cursor_ml -c "SELECT COUNT(*) FROM ml_features;"
```

### 9.5 Optuna Timeout

```bash
# Si optimisation trop longue, réduire trials
python <<EOF
from optimization.optuna_v2_tuner import run_optuna_v2_optimization

results = run_optuna_v2_optimization(
    n_trials=20,  # Au lieu de 50-100
    timeout=1800,  # 30 minutes max
)
EOF
```

---

## 10. Résumé Actions Étape par Étape

### Installation (Une fois)

```bash
# 1. Cloner/Pull branche
git checkout claude/xgboost-improvements-01GTr3rvY76jSmsNyHN94zvE

# 2. Créer venv
python -m venv venv_ml
source venv_ml/bin/activate

# 3. Installer dépendances
pip install -r requirements_ml.txt

# 4. Configurer .env
cp .env.example .env  # Éditer avec vos credentials

# 5. Vérifier PostgreSQL
psql -U postgres -d trade_cursor_ml -c "SELECT COUNT(*) FROM ml_features;"
```

### Entraînement (Régulier)

```bash
# 1. Activer venv
source venv_ml/bin/activate

# 2. Entraîner V2 Enhanced
python optimization/models/train_enhanced.py

# 3. Vérifier résultats
cat optimization/saved_models/xgboost_v2_enhanced_metadata.json | jq '.metrics.test'

# 4. Si accuracy ≥ 70%, déployer
cp optimization/saved_models/xgboost_v2_enhanced* optimization/saved_models/
mv optimization/saved_models/xgboost_v2_enhanced.pkl optimization/saved_models/xgboost_v1.pkl
# (adapter selon votre setup)
```

### Optimisation Optuna (Mensuel)

```bash
# 1. Lancer Optuna V2
python -c "from optimization.optuna_v2_tuner import run_optuna_v2_optimization; run_optuna_v2_optimization(n_trials=50)"

# 2. Réentraîner avec meilleurs params
python optimization/models/train_enhanced.py

# 3. Comparer métriques
# (avant vs après optimisation)
```

---

## 11. Contacts & Support

- **Documentation** : `SOLUTIONS_XGBOOST.md`, `GUIDE_ENTRAINEMENT_V2.md`
- **Issues** : Créer issue GitHub si problème persistant
- **Logs** : Toujours fournir logs complets pour debug

---

## 12. Checklist Finale

- [ ] Python ≥ 3.9 installé
- [ ] PostgreSQL ≥ 12 installé et accessible
- [ ] ≥ 100 trades dans `ml_features`
- [ ] Dépendances ML installées (`requirements_ml.txt`)
- [ ] `.env` configuré avec credentials PostgreSQL
- [ ] Tests validation passés (sections 4.1-4.3)
- [ ] Entraînement V2 Enhanced réussi (accuracy ≥ 70%)
- [ ] Modèle déployé en production
- [ ] Monitoring mis en place
- [ ] Backup ancien modèle créé
- [ ] Cron job réentraînement configuré (optionnel)

---

✅ **Si toutes les étapes sont validées, votre système XGBoost V2 Enhanced est opérationnel !**

🎉 **Objectif atteint : Accuracy 70%+ sans overfitting**
