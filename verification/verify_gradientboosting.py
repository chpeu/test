# -*- coding: utf-8 -*-
"""
Vérification Performance GradientBoosting Optimisé
Avec feature engineering complet et les 28 features sélectionnées
"""

import sys
import warnings
warnings.filterwarnings('ignore')

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

print("=" * 70)
print("  VERIFICATION GRADIENTBOOSTING OPTIMISE")
print("=" * 70)

# =============================================================================
# CHARGER MODELE ET CONFIG
# =============================================================================
print("\n[1/3] Chargement modele et config...")

models_dir = "optimization/saved_models"

# Charger modèle
model = joblib.load(f"{models_dir}/gradient_boosting_optimized.pkl")
print(f"   Modele charge")

# Charger preprocessor
preprocessor = joblib.load(f"{models_dir}/gradient_boosting_optimized_preprocessor.pkl")
feature_names = preprocessor.get('feature_names', [])
scaler = preprocessor.get('scaler')
print(f"   Features: {len(feature_names)}")

# Charger metadata
with open(f"{models_dir}/gradient_boosting_optimized_metadata.json") as f:
    metadata = json.load(f)

print(f"   Metrics attendues:")
test_metrics = metadata.get('metrics', {}).get('test', {})
for k, v in test_metrics.items():
    if isinstance(v, float):
        print(f"      {k}: {v*100:.1f}%")

# =============================================================================
# CHARGER DONNEES TEST (memes que lors de l'entrainement)
# =============================================================================
print("\n[2/3] Chargement donnees test...")

from optimization.data.feature_loader import load_features_from_postgres
from optimization.data.feature_engineering import calculate_derived_features
from sklearn.impute import SimpleImputer

# Charger données
df = load_features_from_postgres(timeframe_days=180, min_trades=1)
print(f"   Trades charges: {len(df)}")

# Feature engineering
df = calculate_derived_features(df)

# Séparer features et targets
exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 
                'is_opportunity', 'reject_reason_category']
all_feature_cols = [c for c in df.columns if c not in exclude_cols and df[c].dtype in ['int64', 'float64']]

X = df[all_feature_cols].copy()
y = df['target_win'].copy()

# Nettoyer
X = X.replace([np.inf, -np.inf], np.nan)

# Imputer
imputer = SimpleImputer(strategy='median')
X_imputed = pd.DataFrame(imputer.fit_transform(X), columns=X.columns, index=X.index)

# Split temporel 80/20 (meme que lors de l'entrainement)
split_idx = int(len(df) * 0.8)
X_test = X_imputed.iloc[split_idx:]
y_test = y.iloc[split_idx:]

print(f"   Test set: {len(X_test)} trades")
print(f"   Win rate baseline: {y_test.mean()*100:.1f}%")

# =============================================================================
# EVALUER AVEC LES BONNES FEATURES
# =============================================================================
print("\n[3/3] Evaluation performance...")

# Vérifier features disponibles
available = set(X_test.columns)
required = set(feature_names)
missing = required - available

if missing:
    print(f"   [!] Features manquantes: {len(missing)}")
    # Ajouter features manquantes avec 0
    for f in missing:
        X_test[f] = 0

# Sélectionner uniquement les features du modèle
X_test_selected = X_test[feature_names].copy()

# Appliquer scaler
if scaler is not None:
    X_test_scaled = scaler.transform(X_test_selected)
else:
    X_test_scaled = X_test_selected.values

# Prédire
y_pred = model.predict(X_test_scaled)
y_proba = model.predict_proba(X_test_scaled)[:, 1]

# Calculer métriques
metrics = {
    'Accuracy': accuracy_score(y_test, y_pred),
    'Precision': precision_score(y_test, y_pred),
    'Recall': recall_score(y_test, y_pred),
    'F1 Score': f1_score(y_test, y_pred),
    'ROC-AUC': roc_auc_score(y_test, y_proba)
}

print(f"\n   RESULTATS GRADIENTBOOSTING OPTIMISE:")
print(f"   " + "-" * 40)
for name, value in metrics.items():
    print(f"   {name:12}: {value*100:.1f}%")

# =============================================================================
# COMPARAISON AVEC OBJECTIF
# =============================================================================
print(f"\n   COMPARAISON AVEC OBJECTIF:")
print(f"   " + "-" * 40)
print(f"   {'Metrique':<12} {'Obtenu':>10} {'Attendu':>10} {'Diff':>10}")

for name, value in metrics.items():
    expected = test_metrics.get(name.lower().replace(' ', '_').replace('-', '_'), 0)
    if expected:
        diff = (value - expected) * 100
        status = "✓" if abs(diff) < 2 else "≈" if abs(diff) < 5 else "!"
        print(f"   {name:<12} {value*100:>9.1f}% {expected*100:>9.1f}% {diff:>+9.1f}% {status}")

print(f"\n   [OK] Verification terminee")
print("=" * 70)
