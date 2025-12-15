#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📊 COMPARAISON DES MODÈLES SUR TRADES RÉELS
============================================
Compare le modèle original vs le modèle anti-overfitting
sur les derniers trades réels.
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
from datetime import datetime
from pathlib import Path

from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

PROJECT_ROOT = Path(__file__).parent
MODELS_PATH = PROJECT_ROOT / "optimization" / "saved_models"

print("=" * 70)
print("  COMPARAISON MODÈLES SUR TRADES RÉELS")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

# =============================================================================
# 1. CHARGEMENT DES DONNÉES
# =============================================================================
print("\n[1/4] Chargement des données...")

from optimization.data.feature_loader import load_features_from_postgres
from optimization.data.feature_engineering import calculate_derived_features

df = load_features_from_postgres(timeframe_days=180, min_trades=1)
df = calculate_derived_features(df)

print(f"   Total trades: {len(df)}")

# Séparer train (80%) et test récent (20%)
split_idx = int(len(df) * 0.8)
df_test = df.iloc[split_idx:].copy()
print(f"   Trades test récents: {len(df_test)}")

# =============================================================================
# 2. CHARGEMENT DES MODÈLES
# =============================================================================
print("\n[2/4] Chargement des modèles...")

# Modèle anti-overfitting (nouveau)
model_new_path = MODELS_PATH / "gradient_boosting_anti_overfit.pkl"
model_new = None
if model_new_path.exists():
    model_new = joblib.load(model_new_path)
    print(f"   ✅ Modèle ANTI-OVERFIT chargé")
else:
    print(f"   ❌ Modèle anti-overfit non trouvé")

# Charger métadonnées pour features
metadata_new_path = MODELS_PATH / "gradient_boosting_anti_overfit_metadata.json"
if metadata_new_path.exists():
    with open(metadata_new_path) as f:
        metadata_new = json.load(f)
    features_new = metadata_new.get('selected_features', [])
else:
    features_new = []

# Modèle original (backup)
metadata_orig_path = MODELS_PATH / "gradient_boosting_optimized_metadata.json"
if metadata_orig_path.exists():
    with open(metadata_orig_path) as f:
        metadata_orig = json.load(f)
    features_orig = metadata_orig.get('selected_features', [])
else:
    features_orig = features_new

# =============================================================================
# 3. PRÉPARATION DES FEATURES
# =============================================================================
print("\n[3/4] Préparation des features...")

# Target
y_test = df_test['target_win'].astype(int).values

# Features pour le nouveau modèle
X_test_new = df_test[features_new].copy()
X_test_new = X_test_new.replace([np.inf, -np.inf], np.nan)

# Imputer les NaN
from sklearn.impute import SimpleImputer
imputer = SimpleImputer(strategy='median')
X_test_new = pd.DataFrame(
    imputer.fit_transform(X_test_new), 
    columns=X_test_new.columns,
    index=X_test_new.index
)

print(f"   Features: {len(features_new)}")
print(f"   Échantillons test: {len(y_test)}")
print(f"   Win rate réel: {y_test.mean()*100:.1f}%")

# =============================================================================
# 4. PRÉDICTIONS ET COMPARAISON
# =============================================================================
print("\n[4/4] Prédictions et comparaison...")

if model_new is not None:
    # Le modèle est un pipeline (imputer + scaler + classifier)
    try:
        y_pred_new = model_new.predict(X_test_new)
        y_proba_new = model_new.predict_proba(X_test_new)[:, 1]
    except Exception as e:
        print(f"   ⚠️ Erreur prédiction: {e}")
        # Essayer sans pipeline
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_test_new)
        y_pred_new = model_new.predict(X_scaled)
        y_proba_new = model_new.predict_proba(X_scaled)[:, 1]
    
    # Métriques
    acc_new = accuracy_score(y_test, y_pred_new)
    f1_new = f1_score(y_test, y_pred_new)
    prec_new = precision_score(y_test, y_pred_new)
    rec_new = recall_score(y_test, y_pred_new)
    
    print(f"\n   📊 MODÈLE ANTI-OVERFIT (NOUVEAU):")
    print(f"   {'='*50}")
    print(f"   Accuracy:  {acc_new:.1%}")
    print(f"   F1 Score:  {f1_new:.4f}")
    print(f"   Precision: {prec_new:.4f}")
    print(f"   Recall:    {rec_new:.4f}")
    
    # Analyse par niveau de confiance
    print(f"\n   📊 PERFORMANCE PAR CONFIANCE:")
    thresholds = [0.5, 0.55, 0.6, 0.65, 0.7]
    
    for thresh in thresholds:
        mask_accept = y_proba_new >= thresh
        if mask_accept.sum() > 0:
            acc_filtered = accuracy_score(y_test[mask_accept], y_pred_new[mask_accept])
            n_accepted = mask_accept.sum()
            n_rejected = (~mask_accept).sum()
            pct_accepted = n_accepted / len(y_test) * 100
            print(f"   Seuil {thresh:.0%}: Acc={acc_filtered:.1%} | Acceptés: {n_accepted} ({pct_accepted:.0f}%) | Rejetés: {n_rejected}")
    
    # Simulation de l'impact du filtre
    print(f"\n   📊 SIMULATION IMPACT DU FILTRE:")
    
    for thresh in [0.55, 0.6]:
        mask_accept = y_proba_new >= thresh
        
        # Sans filtre
        wins_sans = (y_test == 1).sum()
        total_sans = len(y_test)
        winrate_sans = wins_sans / total_sans * 100
        
        # Avec filtre
        wins_avec = (y_test[mask_accept] == 1).sum()
        total_avec = mask_accept.sum()
        winrate_avec = wins_avec / total_avec * 100 if total_avec > 0 else 0
        
        # Trades rejetés qui étaient des pertes
        mask_reject = ~mask_accept
        losses_rejected = (y_test[mask_reject] == 0).sum()
        wins_rejected = (y_test[mask_reject] == 1).sum()
        
        print(f"\n   Seuil {thresh:.0%}:")
        print(f"      Sans filtre: {winrate_sans:.1f}% WR ({wins_sans}/{total_sans})")
        print(f"      Avec filtre: {winrate_avec:.1f}% WR ({wins_avec}/{total_avec})")
        print(f"      Amélioration: {winrate_avec - winrate_sans:+.1f}% WR")
        print(f"      Trades rejetés: {mask_reject.sum()} ({losses_rejected} LOSS, {wins_rejected} WIN)")
    
    # Verdict
    print("\n" + "=" * 70)
    print("  🎯 VERDICT")
    print("=" * 70)
    
    baseline_wr = y_test.mean() * 100
    
    # Calculer avec seuil 0.55
    mask_055 = y_proba_new >= 0.55
    if mask_055.sum() > 0:
        wr_055 = (y_test[mask_055] == 1).sum() / mask_055.sum() * 100
        improvement = wr_055 - baseline_wr
        
        if improvement > 5:
            print(f"  ✅ FILTRE EFFICACE: +{improvement:.1f}% win rate avec seuil 55%")
            print(f"     Win rate sans filtre: {baseline_wr:.1f}%")
            print(f"     Win rate avec filtre: {wr_055:.1f}%")
            print(f"\n  💡 RECOMMANDATION: Activer gb_filter_enabled=true, gb_min_confidence=0.55")
        elif improvement > 2:
            print(f"  ⚠️ FILTRE LÉGÈREMENT UTILE: +{improvement:.1f}% win rate")
            print(f"     Peut être utile pour réduire les mauvais trades")
            print(f"\n  💡 RECOMMANDATION: Tester avec gb_min_confidence=0.6")
        else:
            print(f"  ❌ FILTRE PEU EFFICACE: {improvement:+.1f}% win rate")
            print(f"     Le modèle n'améliore pas significativement le win rate")
            print(f"\n  💡 RECOMMANDATION: Garder gb_filter_enabled=false ou réentraîner")
    else:
        print("  ❌ Pas assez de trades acceptés avec seuil 55%")
    
    print("\n" + "=" * 70)

else:
    print("   ❌ Impossible de comparer sans modèle")
