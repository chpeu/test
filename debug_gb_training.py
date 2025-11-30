# -*- coding: utf-8 -*-
"""
Debug: Comparer entrainement frontend vs optimisation avancee
"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, f1_score, precision_score

print("=" * 60)
print("  DEBUG: POURQUOI LES METRIQUES DIFFERENT?")
print("=" * 60)

# 1. Charger les données exactement comme l'optimisation avancée
print("\n[1/4] Chargement donnees...")
from optimization.data.feature_loader import load_features_from_postgres
from optimization.data.feature_engineering import calculate_derived_features
from sklearn.impute import SimpleImputer

df = load_features_from_postgres(timeframe_days=180, min_trades=1)
print(f"   Trades bruts: {len(df)}")

df = calculate_derived_features(df)

# 2. Charger les features optimisees
print("\n[2/4] Chargement features optimisees...")
with open('optimization/saved_models/gradient_boosting_optimized_metadata.json') as f:
    meta = json.load(f)

selected_features = meta.get('selected_features', [])
print(f"   Features optimisees: {len(selected_features)}")

# Verifier disponibilite
available = set(df.columns)
missing = set(selected_features) - available
print(f"   Features manquantes: {len(missing)}")
if missing:
    print(f"   -> {list(missing)[:5]}...")

# Filtrer les features disponibles
valid_features = [f for f in selected_features if f in available]
print(f"   Features utilisables: {len(valid_features)}")

# 3. Preparer les donnees exactement comme l'optimisation
print("\n[3/4] Preparation donnees...")

exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 
                'is_opportunity', 'reject_reason_category']

X = df[valid_features].copy()
y = df['target_win'].astype(int).copy()

# Nettoyer
X = X.replace([np.inf, -np.inf], np.nan)

# Imputer
imputer = SimpleImputer(strategy='median')
X_imputed = pd.DataFrame(imputer.fit_transform(X), columns=X.columns, index=X.index)

# Split temporel 80/20
split_idx = int(len(df) * 0.8)
X_train = X_imputed.iloc[:split_idx]
X_test = X_imputed.iloc[split_idx:]
y_train = y.iloc[:split_idx]
y_test = y.iloc[split_idx:]

print(f"   Train: {len(X_train)}, Test: {len(X_test)}")
print(f"   Win rate train: {y_train.mean()*100:.1f}%")
print(f"   Win rate test: {y_test.mean()*100:.1f}%")

# Scaler
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# 4. Entrainer avec les MEMES hyperparametres
print("\n[4/4] Entrainement avec hyperparametres optimises...")

model = GradientBoostingClassifier(
    n_estimators=271,
    max_depth=6,
    learning_rate=0.217,
    min_samples_split=48,
    min_samples_leaf=38,
    subsample=0.734,
    max_features='sqrt',
    random_state=42
)

model.fit(X_train_scaled, y_train)

# Evaluer
y_pred = model.predict(X_test_scaled)
y_train_pred = model.predict(X_train_scaled)

train_acc = accuracy_score(y_train, y_train_pred)
test_acc = accuracy_score(y_test, y_pred)
test_f1 = f1_score(y_test, y_pred)
test_prec = precision_score(y_test, y_pred)

print(f"\n{'='*60}")
print(f"  RESULTATS DEBUG")
print(f"{'='*60}")
print(f"   Train Accuracy: {train_acc*100:.1f}%")
print(f"   Test Accuracy:  {test_acc*100:.1f}%")
print(f"   F1 Score:       {test_f1:.3f}")
print(f"   Precision:      {test_prec:.3f}")
print(f"   Overfitting:    {(train_acc-test_acc)*100:.1f}%")

print(f"\n   ATTENDU (optimisation avancee):")
print(f"   Test Accuracy:  68.5%")
print(f"   F1 Score:       0.694")
print(f"   Precision:      0.706")

if abs(test_acc - 0.685) < 0.02:
    print(f"\n   ✅ METRIQUES COHERENTES!")
else:
    print(f"\n   ❌ ECART DETECTE - Cause probable:")
    print(f"      Le frontend n'utilise pas le meme split/features/preprocessing")
