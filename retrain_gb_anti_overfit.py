#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔧 RÉENTRAÎNEMENT GRADIENTBOOSTING ANTI-OVERFITTING
====================================================
Corrections appliquées:
1. Réduction max_depth: 6 → 4
2. Augmentation min_samples_leaf: 38 → 60
3. Réduction n_estimators: 271 → 150
4. Augmentation min_samples_split: 48 → 80
5. Validation croisée rigoureuse
"""

import sys
import warnings
warnings.filterwarnings('ignore')

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import os
import json
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path

from sklearn.model_selection import cross_val_score, StratifiedKFold, train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, 
    roc_auc_score, confusion_matrix, classification_report
)

import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)

# Seed pour reproductibilité
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

PROJECT_ROOT = Path(__file__).parent
MODELS_PATH = PROJECT_ROOT / "optimization" / "saved_models"

print("=" * 70)
print("  RÉENTRAÎNEMENT GRADIENTBOOSTING ANTI-OVERFITTING")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

# =============================================================================
# 1. CHARGEMENT DES DONNÉES
# =============================================================================
print("\n[1/5] Chargement des données...")

from optimization.data.feature_loader import load_features_from_postgres
from optimization.data.feature_engineering import calculate_derived_features

df = load_features_from_postgres(timeframe_days=180, min_trades=1)
print(f"   Trades chargés: {len(df)}")

df = calculate_derived_features(df)

# Features sélectionnées (les 28 du modèle optimisé)
SELECTED_FEATURES = [
    "di_plus_1m", "bb_distance_to_upper_5m", "ema_diff_pct_1m", "rsi_1m",
    "di_plus_5m", "ema_diff_pct_5m", "bb_distance_to_upper_1m", "bb_distance_to_lower_1m",
    "atr_pct_1m", "rsi_5m", "bb_width_5m", "bb_distance_to_lower_5m",
    "macd_momentum_5m", "trend_strength_1m", "rsi_prev_5m", "volatility_momentum_product",
    "di_gap_1m", "macd_hist_prev_1m", "rsi_prev_1m", "macd_hist_1m",
    "trend_strength_5m", "momentum_divergence", "bb_width_1m", "di_minus_5m",
    "momentum_5m", "momentum_1m", "volume_divergence", "adx_5m"
]

# Filtrer features disponibles
available_features = [f for f in SELECTED_FEATURES if f in df.columns]
print(f"   Features disponibles: {len(available_features)}/{len(SELECTED_FEATURES)}")

X = df[available_features].copy()
y = df['target_win'].astype(int).copy()

# Nettoyer
X = X.replace([np.inf, -np.inf], np.nan)
imputer = SimpleImputer(strategy='median')
X = pd.DataFrame(imputer.fit_transform(X), columns=X.columns, index=X.index)

print(f"   Win rate: {y.mean()*100:.1f}%")

# =============================================================================
# 2. SPLIT TEMPOREL
# =============================================================================
print("\n[2/5] Split temporel 80/20...")

split_idx = int(len(df) * 0.8)
X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

print(f"   Train: {len(X_train)} | Test: {len(X_test)}")

# Scaler
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# =============================================================================
# 3. OPTIMISATION HYPERPARAMÈTRES ANTI-OVERFITTING
# =============================================================================
print("\n[3/5] Optimisation anti-overfitting (50 trials)...")

def objective(trial):
    """Objectif Optuna avec forte régularisation"""
    params = {
        # 🔧 Paramètres avec FORTE régularisation
        'n_estimators': trial.suggest_int('n_estimators', 50, 200),  # Réduit de 271
        'max_depth': trial.suggest_int('max_depth', 2, 5),  # Réduit de 6
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.15),  # Réduit
        'min_samples_split': trial.suggest_int('min_samples_split', 50, 150),  # Augmenté
        'min_samples_leaf': trial.suggest_int('min_samples_leaf', 40, 100),  # Augmenté
        'subsample': trial.suggest_float('subsample', 0.5, 0.8),
        'max_features': trial.suggest_categorical('max_features', ['sqrt', 'log2', 0.5]),
        'random_state': RANDOM_SEED
    }
    
    model = GradientBoostingClassifier(**params)
    
    # CV 5-fold stratifié
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
    scores = cross_val_score(model, X_train_scaled, y_train, cv=cv, scoring='f1')
    
    # Pénaliser overfitting
    model.fit(X_train_scaled, y_train)
    train_acc = accuracy_score(y_train, model.predict(X_train_scaled))
    cv_acc = scores.mean()
    
    # Si gap train-CV trop grand, pénaliser
    gap = train_acc - cv_acc
    if gap > 0.15:
        return scores.mean() - (gap - 0.15) * 0.5  # Pénalité
    
    return scores.mean()

study = optuna.create_study(direction='maximize', sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED))
study.optimize(objective, n_trials=50, show_progress_bar=True)

best_params = study.best_params
print(f"\n   Meilleurs paramètres:")
for k, v in best_params.items():
    print(f"      {k}: {v}")
print(f"   Meilleur F1 CV: {study.best_value:.4f}")

# =============================================================================
# 4. ENTRAÎNEMENT FINAL ET ÉVALUATION
# =============================================================================
print("\n[4/5] Entraînement final et évaluation...")

final_model = GradientBoostingClassifier(**best_params, random_state=RANDOM_SEED)
final_model.fit(X_train_scaled, y_train)

# Métriques
train_pred = final_model.predict(X_train_scaled)
test_pred = final_model.predict(X_test_scaled)
test_proba = final_model.predict_proba(X_test_scaled)[:, 1]

train_acc = accuracy_score(y_train, train_pred)
test_acc = accuracy_score(y_test, test_pred)
test_f1 = f1_score(y_test, test_pred)
test_precision = precision_score(y_test, test_pred)
test_recall = recall_score(y_test, test_pred)
test_auc = roc_auc_score(y_test, test_proba)

print(f"\n   📊 RÉSULTATS:")
print(f"   {'='*50}")
print(f"   Train Accuracy: {train_acc:.1%}")
print(f"   Test Accuracy:  {test_acc:.1%}")
print(f"   Gap (Train-Test): {train_acc - test_acc:.1%}")
print(f"   {'='*50}")
print(f"   Test F1:        {test_f1:.4f}")
print(f"   Test Precision: {test_precision:.4f}")
print(f"   Test Recall:    {test_recall:.4f}")
print(f"   Test ROC AUC:   {test_auc:.4f}")

# CV finale sur toutes les données
print("\n   📊 VALIDATION CROISÉE FINALE (5-fold):")
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
X_all_scaled = scaler.fit_transform(X)
cv_acc = cross_val_score(final_model, X_all_scaled, y, cv=cv, scoring='accuracy')
cv_f1 = cross_val_score(final_model, X_all_scaled, y, cv=cv, scoring='f1')
cv_auc = cross_val_score(final_model, X_all_scaled, y, cv=cv, scoring='roc_auc')

print(f"   CV Accuracy: {cv_acc.mean():.4f} ± {cv_acc.std():.4f}")
print(f"   CV F1:       {cv_f1.mean():.4f} ± {cv_f1.std():.4f}")
print(f"   CV ROC AUC:  {cv_auc.mean():.4f} ± {cv_auc.std():.4f}")

# Matrice de confusion
print("\n   📊 MATRICE DE CONFUSION (Test):")
cm = confusion_matrix(y_test, test_pred)
print(f"                 Prédit LOSS  Prédit WIN")
print(f"   Réel LOSS     {cm[0,0]:>10}  {cm[0,1]:>10}")
print(f"   Réel WIN      {cm[1,0]:>10}  {cm[1,1]:>10}")

# =============================================================================
# 5. SAUVEGARDE
# =============================================================================
print("\n[5/5] Sauvegarde du modèle corrigé...")

# Créer pipeline complet
from sklearn.pipeline import Pipeline

pipeline = Pipeline([
    ('imputer', imputer),
    ('scaler', scaler),
    ('classifier', final_model)
])

# Sauvegarder
model_file = MODELS_PATH / "gradient_boosting_anti_overfit.pkl"
joblib.dump(pipeline, model_file)
print(f"   ✅ Modèle: {model_file}")

# Métadonnées
metadata = {
    "model_name": "gradient_boosting_anti_overfit",
    "model_type": "classification",
    "trained_at": datetime.now().isoformat(),
    "random_seed": RANDOM_SEED,
    "n_samples": len(df),
    "n_features": len(available_features),
    "selected_features": available_features,
    "hyperparameters": best_params,
    "metrics": {
        "train_accuracy": float(train_acc),
        "test_accuracy": float(test_acc),
        "gap_train_test": float(train_acc - test_acc),
        "cv_accuracy": float(cv_acc.mean()),
        "cv_accuracy_std": float(cv_acc.std()),
        "cv_f1": float(cv_f1.mean()),
        "cv_f1_std": float(cv_f1.std()),
        "cv_roc_auc": float(cv_auc.mean()),
        "test_f1": float(test_f1),
        "test_precision": float(test_precision),
        "test_recall": float(test_recall),
        "test_roc_auc": float(test_auc)
    },
    "anti_overfit_measures": [
        "max_depth réduit (2-5 au lieu de 6)",
        "min_samples_leaf augmenté (40-100 au lieu de 38)",
        "min_samples_split augmenté (50-150 au lieu de 48)",
        "n_estimators réduit (50-200 au lieu de 271)",
        "Pénalité overfitting dans Optuna"
    ]
}

metadata_file = MODELS_PATH / "gradient_boosting_anti_overfit_metadata.json"
with open(metadata_file, 'w') as f:
    json.dump(metadata, f, indent=2)
print(f"   ✅ Métadonnées: {metadata_file}")

# =============================================================================
# VERDICT
# =============================================================================
print("\n" + "=" * 70)
print("  🎯 VERDICT")
print("=" * 70)

gap = train_acc - test_acc
if gap < 0.10:
    print(f"  ✅ OVERFITTING CORRIGÉ! Gap: {gap:.1%} < 10%")
elif gap < 0.20:
    print(f"  ⚠️ Overfitting réduit mais présent. Gap: {gap:.1%}")
else:
    print(f"  ❌ Overfitting encore trop élevé. Gap: {gap:.1%}")

if cv_acc.mean() > 0.58:
    print(f"  ✅ PERFORMANCE ACCEPTABLE: CV Accuracy {cv_acc.mean():.1%} > 58%")
else:
    print(f"  ⚠️ Performance limitée: CV Accuracy {cv_acc.mean():.1%}")

baseline = 0.5
improvement = (cv_acc.mean() - baseline) / baseline * 100
print(f"  📈 Amélioration vs hasard: +{improvement:.1f}%")

print("\n  💡 RECOMMANDATIONS:")
if cv_acc.mean() > 0.58 and gap < 0.15:
    print("     - Activer gb_filter_enabled = true")
    print(f"     - Utiliser gb_min_confidence = 0.55-0.60")
    print("     - Le modèle apporte une vraie valeur ajoutée")
else:
    print("     - Considérer de désactiver le filtre ML")
    print("     - Ou collecter plus de données (>1500 trades)")
    print("     - Ou essayer d'autres algorithmes (RandomForest, LightGBM)")

print("\n" + "=" * 70)
