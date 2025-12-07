# Scripts Directory

Cette structure organise tous les scripts auxiliaires du projet par catégorie fonctionnelle.

## Structure

```
scripts/
├── analysis/       # Scripts d'analyse de données et trades
├── training/       # Scripts d'entraînement de modèles ML
├── optimization/   # Scripts d'optimisation et tuning
├── data_cleaning/  # Scripts de nettoyage de données
├── utilities/      # Outils et utilitaires (check, debug, fix)
└── verification/   # Scripts de validation et audit
```

## Catégories

### 📊 Analysis (`analysis/`)
Scripts pour analyser les données, logs, et performances de trading.

- `analyze_data_quality.py` - Analyse de la qualité des données
- `analyze_ml_impact.py` - Impact des prédictions ML
- `analyze_trades.py` - Analyse des trades
- `analyze_trades_per_symbol.py` - Analyse par symbole
- `analyze_win_loss.py` - Analyse win/loss ratio

### 🎓 Training (`training/`)
Scripts d'entraînement de modèles de machine learning.

- `train_xgboost.py` - Entraînement XGBoost
- `train_xgboost_optimized.py` - Version optimisée
- `train_regression_v2.py` - Entraînement régression
- `train_final_optimized.py` - Configuration finale optimisée

### ⚡ Optimization (`optimization/`)
Scripts d'optimisation de modèles et hyperparamètres.

- `optimize_advanced.py` - Optimisation avancée
- `optimize_all_models.py` - Optimisation de tous les modèles
- `maximize_all_metrics.py` - Maximisation des métriques
- `anti_overfit_optimize.py` - Anti-overfitting

### 🧹 Data Cleaning (`data_cleaning/`)
Scripts de nettoyage et préparation des données.

- `clean_ml_data.py` - Nettoyage données ML
- `clean_ml_data_final.py` - Version finale

### 🔧 Utilities (`utilities/`)
Outils de debugging, vérification, et correction.

- `check_*.py` - Scripts de vérification
- `debug_*.py` - Scripts de debugging
- `fix_*.py` - Scripts de correction
- `find_*.py` - Scripts de recherche

### ✅ Verification (`verification/`)
Scripts de validation, audit, et comparaison.

- `validate_*.py` - Validation de modèles
- `audit_*.py` - Audit de composants
- `compare_*.py` - Comparaison de résultats
- `evaluate_*.py` - Évaluation de performances

## Usage

Tous les scripts peuvent être exécutés depuis la racine du projet :

```bash
# Analyse
python scripts/analysis/analyze_trades.py

# Entraînement
python scripts/training/train_xgboost_optimized.py

# Optimisation
python scripts/optimization/optimize_advanced.py
```

## Notes

- Anciennement à la racine, maintenant organisés par fonction
- Conserve l'historique git via `git mv`
- Facilite la navigation et la maintenance
