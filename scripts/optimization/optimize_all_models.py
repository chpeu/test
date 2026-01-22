# -*- coding: utf-8 -*-
"""
Optimisation des Hyperparamètres - 3 Modèles ML

Ce script optimise avec Optuna puis entraîne:
1. XGBoost V1 (Classification WIN/LOSS)
2. XGBoost V2 (Régression PNL%)
3. GradientBoosting (Classification)

Avec validation croisée temporelle pour éviter le surfit.
"""

import sys
import warnings
warnings.filterwarnings('ignore')

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import os
import json
import pickle
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Tuple, List

# ML
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
import xgboost as xgb
from sklearn.ensemble import GradientBoostingClassifier

# Optuna pour optimisation
import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)

print("=" * 70)
print("  OPTIMISATION DES 3 MODELES ML")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

# =============================================================================
# CHARGEMENT DES DONNEES
# =============================================================================
print("\n[1/5] Chargement des donnees...")

from optimization.data.feature_loader import load_features_from_postgres
from optimization.data.feature_engineering import calculate_derived_features

# Charger plus de données pour l'optimisation
df = load_features_from_postgres(timeframe_days=180, min_trades=1)
print(f"   Trades charges: {len(df)}")

# Feature engineering
df = calculate_derived_features(df)
print(f"   Features apres engineering: {len(df.columns)}")

# Séparer features et targets
exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 
                'is_opportunity', 'reject_reason_category']
feature_cols = [c for c in df.columns if c not in exclude_cols and df[c].dtype in ['int64', 'float64']]

X = df[feature_cols].copy()
y_class = df['target_win'].copy()  # Pour classification
y_reg = df['target_pnl'].copy() if 'target_pnl' in df.columns else y_class  # Pour régression

# Nettoyer
X = X.replace([np.inf, -np.inf], np.nan)

# Imputer les NaN
imputer = SimpleImputer(strategy='median')
X_imputed = pd.DataFrame(imputer.fit_transform(X), columns=X.columns, index=X.index)

print(f"   Features finales: {len(feature_cols)}")
print(f"   Win rate: {y_class.mean()*100:.1f}%")

# Split temporel 80/20
split_idx = int(len(df) * 0.8)
X_train, X_test = X_imputed.iloc[:split_idx], X_imputed.iloc[split_idx:]
y_train_class, y_test_class = y_class.iloc[:split_idx], y_class.iloc[split_idx:]
y_train_reg, y_test_reg = y_reg.iloc[:split_idx], y_reg.iloc[split_idx:]

print(f"   Train: {len(X_train)} | Test: {len(X_test)}")

# TimeSeriesSplit pour validation croisée
tscv = TimeSeriesSplit(n_splits=3)

# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def save_model(model, preprocessor, metadata, model_name: str, models_dir: str = "optimization/saved_models"):
    """Sauvegarde modèle, preprocessor et metadata"""
    os.makedirs(models_dir, exist_ok=True)
    
    # Modèle
    model_path = f"{models_dir}/{model_name}.pkl"
    joblib.dump(model, model_path)
    
    # Preprocessor
    prep_path = f"{models_dir}/{model_name}_preprocessor.pkl"
    joblib.dump(preprocessor, prep_path)
    
    # Metadata
    meta_path = f"{models_dir}/{model_name}_metadata.json"
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2, default=str)
    
    print(f"   Sauvegarde: {model_name}")
    return model_path, prep_path, meta_path


# =============================================================================
# OPTIMISATION XGBOOST V1 (Classification)
# =============================================================================
print("\n" + "=" * 70)
print("[2/5] OPTIMISATION XGBOOST V1 (Classification)")
print("=" * 70)

def objective_xgb_v1(trial):
    """Fonction objectif pour Optuna - XGBoost V1"""
    params = {
        'max_depth': trial.suggest_int('max_depth', 2, 8),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
        'n_estimators': trial.suggest_int('n_estimators', 50, 500),
        'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
        'reg_alpha': trial.suggest_float('reg_alpha', 0.01, 10, log=True),
        'reg_lambda': trial.suggest_float('reg_lambda', 0.01, 10, log=True),
        'gamma': trial.suggest_float('gamma', 0, 5),
        'objective': 'binary:logistic',
        'eval_metric': 'logloss',
        'use_label_encoder': False,
        'random_state': 42,
        'n_jobs': -1
    }
    
    # Validation croisée temporelle
    scores = []
    for train_idx, val_idx in tscv.split(X_train):
        X_tr, X_val = X_train.iloc[train_idx], X_train.iloc[val_idx]
        y_tr, y_val = y_train_class.iloc[train_idx], y_train_class.iloc[val_idx]
        
        # Normalisation
        scaler = StandardScaler()
        X_tr_scaled = scaler.fit_transform(X_tr)
        X_val_scaled = scaler.transform(X_val)
        
        model = xgb.XGBClassifier(**params)
        model.fit(X_tr_scaled, y_tr, verbose=False)
        
        y_pred = model.predict(X_val_scaled)
        score = f1_score(y_val, y_pred)
        scores.append(score)
    
    return np.mean(scores)

print("   Optimisation Optuna (50 essais)...")
study_v1 = optuna.create_study(direction='maximize', study_name='xgboost_v1')
study_v1.optimize(objective_xgb_v1, n_trials=50, show_progress_bar=True)

best_params_v1 = study_v1.best_params
print(f"   Meilleur F1: {study_v1.best_value*100:.1f}%")
print(f"   Params: max_depth={best_params_v1['max_depth']}, lr={best_params_v1['learning_rate']:.3f}")

# Entraîner le modèle final
print("   Entrainement du modele final...")
scaler_v1 = StandardScaler()
X_train_scaled = scaler_v1.fit_transform(X_train)
X_test_scaled = scaler_v1.transform(X_test)

final_params_v1 = {
    **best_params_v1,
    'objective': 'binary:logistic',
    'eval_metric': 'logloss',
    'use_label_encoder': False,
    'random_state': 42,
    'n_jobs': -1
}

model_v1 = xgb.XGBClassifier(**final_params_v1)
model_v1.fit(X_train_scaled, y_train_class, verbose=False)

# Évaluation
y_pred_v1 = model_v1.predict(X_test_scaled)
y_proba_v1 = model_v1.predict_proba(X_test_scaled)[:, 1]

metrics_v1 = {
    'accuracy': accuracy_score(y_test_class, y_pred_v1),
    'precision': precision_score(y_test_class, y_pred_v1),
    'recall': recall_score(y_test_class, y_pred_v1),
    'f1': f1_score(y_test_class, y_pred_v1),
    'roc_auc': roc_auc_score(y_test_class, y_proba_v1)
}

print(f"\n   RESULTATS XGBOOST V1:")
print(f"      Accuracy:  {metrics_v1['accuracy']*100:.1f}%")
print(f"      Precision: {metrics_v1['precision']*100:.1f}%")
print(f"      Recall:    {metrics_v1['recall']*100:.1f}%")
print(f"      F1 Score:  {metrics_v1['f1']*100:.1f}%")
print(f"      ROC-AUC:   {metrics_v1['roc_auc']*100:.1f}%")

# Sauvegarde
preprocessor_v1 = {
    'scaler': scaler_v1,
    'imputer': imputer,
    'feature_names': list(feature_cols),
    'scaler_type': 'StandardScaler'
}

metadata_v1 = {
    'model_name': 'xgboost_v1_optimized',
    'model_type': 'classification',
    'trained_at': datetime.now().isoformat(),
    'n_samples': len(X_train),
    'n_features': len(feature_cols),
    'hyperparameters': best_params_v1,
    'metrics': {
        'test': metrics_v1,
        'cv_f1': study_v1.best_value
    },
    'feature_names': list(feature_cols)
}

save_model(model_v1, preprocessor_v1, metadata_v1, 'xgboost_v1_optimized')

# =============================================================================
# OPTIMISATION XGBOOST V2 (Régression)
# =============================================================================
print("\n" + "=" * 70)
print("[3/5] OPTIMISATION XGBOOST V2 (Regression PNL%)")
print("=" * 70)

# Winsorisation de la cible pour éviter les valeurs aberrantes extrêmes
y_train_reg_clipped = y_train_reg.clip(
    lower=y_train_reg.quantile(0.01),
    upper=y_train_reg.quantile(0.99)
)

def objective_xgb_v2(trial):
    """Fonction objectif pour Optuna - XGBoost V2 Régression"""
    params = {
        'max_depth': trial.suggest_int('max_depth', 2, 6),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.2, log=True),
        'n_estimators': trial.suggest_int('n_estimators', 100, 600),
        'min_child_weight': trial.suggest_int('min_child_weight', 3, 15),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
        'reg_alpha': trial.suggest_float('reg_alpha', 1, 20, log=True),
        'reg_lambda': trial.suggest_float('reg_lambda', 1, 20, log=True),
        'gamma': trial.suggest_float('gamma', 0.5, 5),
        'objective': 'reg:squarederror',
        'random_state': 42,
        'n_jobs': -1
    }
    
    # Validation croisée temporelle
    scores = []
    for train_idx, val_idx in tscv.split(X_train):
        X_tr, X_val = X_train.iloc[train_idx], X_train.iloc[val_idx]
        y_tr, y_val = y_train_reg_clipped.iloc[train_idx], y_train_reg.iloc[val_idx]
        
        scaler = StandardScaler()
        X_tr_scaled = scaler.fit_transform(X_tr)
        X_val_scaled = scaler.transform(X_val)
        
        model = xgb.XGBRegressor(**params)
        model.fit(X_tr_scaled, y_tr, verbose=False)
        
        y_pred = model.predict(X_val_scaled)
        # Utilisation du MAE négatif (à maximiser)
        score = -mean_absolute_error(y_val, y_pred)
        scores.append(score)
    
    return np.mean(scores)

print("   Optimisation Optuna (50 essais)...")
study_v2 = optuna.create_study(direction='maximize', study_name='xgboost_v2')
study_v2.optimize(objective_xgb_v2, n_trials=50, show_progress_bar=True)

best_params_v2 = study_v2.best_params
print(f"   Meilleur MAE: {-study_v2.best_value:.3f}%")
print(f"   Params: max_depth={best_params_v2['max_depth']}, lr={best_params_v2['learning_rate']:.3f}")

# Entraîner le modèle final
print("   Entrainement du modele final...")
scaler_v2 = StandardScaler()
X_train_scaled_v2 = scaler_v2.fit_transform(X_train)
X_test_scaled_v2 = scaler_v2.transform(X_test)

final_params_v2 = {
    **best_params_v2,
    'objective': 'reg:squarederror',
    'random_state': 42,
    'n_jobs': -1
}

model_v2 = xgb.XGBRegressor(**final_params_v2)
model_v2.fit(X_train_scaled_v2, y_train_reg_clipped, verbose=False)

# Évaluation
y_pred_v2 = model_v2.predict(X_test_scaled_v2)

metrics_v2 = {
    'mae': mean_absolute_error(y_test_reg, y_pred_v2),
    'r2': r2_score(y_test_reg, y_pred_v2),
    # Classification dérivée (seuil à 0)
    'accuracy': accuracy_score(y_test_class, (y_pred_v2 > 0).astype(int)),
    'f1': f1_score(y_test_class, (y_pred_v2 > 0).astype(int))
}

print(f"\n   RESULTATS XGBOOST V2:")
print(f"      MAE:       {metrics_v2['mae']:.3f}%")
print(f"      R2:        {metrics_v2['r2']:.3f}")
print(f"      Accuracy:  {metrics_v2['accuracy']*100:.1f}% (classification derivee)")
print(f"      F1 Score:  {metrics_v2['f1']*100:.1f}%")

# Sauvegarde
preprocessor_v2 = {
    'scaler': scaler_v2,
    'imputer': imputer,
    'feature_names': list(feature_cols),
    'scaler_type': 'StandardScaler'
}

metadata_v2 = {
    'model_name': 'xgboost_v2_optimized',
    'model_type': 'regression',
    'trained_at': datetime.now().isoformat(),
    'n_samples': len(X_train),
    'n_features': len(feature_cols),
    'hyperparameters': best_params_v2,
    'metrics': {
        'test': metrics_v2,
        'cv_mae': -study_v2.best_value
    },
    'feature_names': list(feature_cols),
    'selected_features': list(feature_cols)
}

save_model(model_v2, preprocessor_v2, metadata_v2, 'xgboost_v2_optimized')

# =============================================================================
# OPTIMISATION GRADIENTBOOSTING
# =============================================================================
print("\n" + "=" * 70)
print("[4/5] OPTIMISATION GRADIENTBOOSTING")
print("=" * 70)

gb_feature_names = list(feature_cols)
try:
    gb_meta_path = "optimization/saved_models/gradient_boosting_optimized_metadata.json"
    if os.path.exists(gb_meta_path):
        with open(gb_meta_path, 'r', encoding='utf-8') as f:
            gb_meta = json.load(f)
        candidate = gb_meta.get('selected_features') or gb_meta.get('feature_names')
        if candidate:
            gb_feature_names = [c for c in candidate if c in X_train.columns]
            missing = [c for c in candidate if c not in X_train.columns]
            print(f"   Features GB depuis metadata: {len(gb_feature_names)}")
            if missing:
                print(f"   ⚠️ Features manquantes ignorees: {len(missing)}")
except Exception:
    pass

X_train_gb = X_train[gb_feature_names]
X_test_gb = X_test[gb_feature_names]

imputer_gb = SimpleImputer(strategy='median')
imputer_gb.fit(X_train_gb)

def objective_gb(trial):
    """Fonction objectif pour Optuna - GradientBoosting"""
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 50, 300),
        'max_depth': trial.suggest_int('max_depth', 2, 8),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
        'min_samples_split': trial.suggest_int('min_samples_split', 5, 30),
        'min_samples_leaf': trial.suggest_int('min_samples_leaf', 5, 30),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
        'max_features': trial.suggest_categorical('max_features', ['sqrt', 'log2', None]),
        'random_state': 42
    }
    
    # Validation croisée temporelle
    scores = []
    for train_idx, val_idx in tscv.split(X_train):
        X_tr, X_val = X_train.iloc[train_idx], X_train.iloc[val_idx]
        y_tr, y_val = y_train_class.iloc[train_idx], y_train_class.iloc[val_idx]
        
        scaler = StandardScaler()
        X_tr_scaled = scaler.fit_transform(X_tr)
        X_val_scaled = scaler.transform(X_val)
        
        model = GradientBoostingClassifier(**params)
        model.fit(X_tr_scaled, y_tr)
        
        y_pred = model.predict(X_val_scaled)
        score = f1_score(y_val, y_pred)
        scores.append(score)
    
    return np.mean(scores)

print("   Optimisation Optuna (50 essais)...")
study_gb = optuna.create_study(direction='maximize', study_name='gradient_boosting')
study_gb.optimize(objective_gb, n_trials=50, show_progress_bar=True)

best_params_gb = study_gb.best_params
print(f"   Meilleur F1: {study_gb.best_value*100:.1f}%")
print(f"   Params: max_depth={best_params_gb['max_depth']}, lr={best_params_gb['learning_rate']:.3f}")

# Entraîner le modèle final
print("   Entrainement du modele final...")
scaler_gb = StandardScaler()
X_train_scaled_gb = scaler_gb.fit_transform(X_train_gb)
X_test_scaled_gb = scaler_gb.transform(X_test_gb)

final_params_gb = {
    **best_params_gb,
    'random_state': 42
}

model_gb = GradientBoostingClassifier(**final_params_gb)
model_gb.fit(X_train_scaled_gb, y_train_class)

# Évaluation
y_pred_gb = model_gb.predict(X_test_scaled_gb)
y_proba_gb = model_gb.predict_proba(X_test_scaled_gb)[:, 1]

metrics_gb = {
    'accuracy': accuracy_score(y_test_class, y_pred_gb),
    'precision': precision_score(y_test_class, y_pred_gb),
    'recall': recall_score(y_test_class, y_pred_gb),
    'f1': f1_score(y_test_class, y_pred_gb),
    'roc_auc': roc_auc_score(y_test_class, y_proba_gb)
}

print(f"\n   RESULTATS GRADIENTBOOSTING:")
print(f"      Accuracy:  {metrics_gb['accuracy']*100:.1f}%")
print(f"      Precision: {metrics_gb['precision']*100:.1f}%")
print(f"      Recall:    {metrics_gb['recall']*100:.1f}%")
print(f"      F1 Score:  {metrics_gb['f1']*100:.1f}%")
print(f"      ROC-AUC:   {metrics_gb['roc_auc']*100:.1f}%")

# Sauvegarde
preprocessor_gb = {
    'scaler': scaler_gb,
    'imputer': imputer_gb,
    'feature_names': list(gb_feature_names),
    'scaler_type': 'StandardScaler'
}

metadata_gb = {
    'model_name': 'gradient_boosting_optimized',
    'model_type': 'classification',
    'trained_at': datetime.now().isoformat(),
    'n_samples': len(X_train),
    'n_features': len(gb_feature_names),
    'hyperparameters': best_params_gb,
    'metrics': {
        'test': metrics_gb,
        'cv_f1': study_gb.best_value
    },
    'feature_names': list(gb_feature_names)
}

save_model(model_gb, preprocessor_gb, metadata_gb, 'gradient_boosting_optimized')

# =============================================================================
# MISE A JOUR DES MODELES "LATEST"
# =============================================================================
print("\n" + "=" * 70)
print("[5/5] MISE A JOUR MODELES LATEST")
print("=" * 70)

import shutil
models_dir = "optimization/saved_models"

# Copie vers les noms "latest" utilisés par les prédicteurs
copies = [
    ('xgboost_v1_optimized', 'xgboost_v1'),
    ('xgboost_v2_optimized', 'xgboost_v2_latest'),
]

for src, dst in copies:
    for ext in ['.pkl', '_preprocessor.pkl', '_metadata.json']:
        src_path = f"{models_dir}/{src}{ext}"
        dst_path = f"{models_dir}/{dst}{ext}"
        if os.path.exists(src_path) and src_path != dst_path:
            shutil.copy(src_path, dst_path)
            print(f"   {src}{ext} -> {dst}{ext}")

# =============================================================================
# RESUME FINAL
# =============================================================================
print("\n" + "=" * 70)
print("  RESUME OPTIMISATION")
print("=" * 70)

print(f"""
   MODELE              ACCURACY    PRECISION   RECALL      F1          AUC
   -------------------------------------------------------------------------
   XGBoost V1          {metrics_v1['accuracy']*100:5.1f}%      {metrics_v1['precision']*100:5.1f}%      {metrics_v1['recall']*100:5.1f}%      {metrics_v1['f1']*100:5.1f}%      {metrics_v1['roc_auc']*100:5.1f}%
   XGBoost V2          {metrics_v2['accuracy']*100:5.1f}%      N/A         N/A         {metrics_v2['f1']*100:5.1f}%      N/A
   GradientBoosting    {metrics_gb['accuracy']*100:5.1f}%      {metrics_gb['precision']*100:5.1f}%      {metrics_gb['recall']*100:5.1f}%      {metrics_gb['f1']*100:5.1f}%      {metrics_gb['roc_auc']*100:5.1f}%
   
   MEILLEURS HYPERPARAMETRES:
   --------------------------
   XGBoost V1: max_depth={best_params_v1['max_depth']}, lr={best_params_v1['learning_rate']:.3f}, n_est={best_params_v1['n_estimators']}
   XGBoost V2: max_depth={best_params_v2['max_depth']}, lr={best_params_v2['learning_rate']:.3f}, n_est={best_params_v2['n_estimators']}
   GradientBoosting: max_depth={best_params_gb['max_depth']}, lr={best_params_gb['learning_rate']:.3f}, n_est={best_params_gb['n_estimators']}
   
   MODELES SAUVEGARDES:
   --------------------
   - xgboost_v1_optimized.pkl (-> xgboost_v1.pkl)
   - xgboost_v2_optimized.pkl (-> xgboost_v2_latest.pkl)
   - gradient_boosting_optimized.pkl
""")

# Sauvegarde du rapport
report = {
    'timestamp': datetime.now().isoformat(),
    'n_samples': len(df),
    'n_features': len(feature_cols),
    'models': {
        'xgboost_v1': {
            'best_params': best_params_v1,
            'metrics': metrics_v1,
            'cv_score': study_v1.best_value
        },
        'xgboost_v2': {
            'best_params': best_params_v2,
            'metrics': metrics_v2,
            'cv_score': -study_v2.best_value
        },
        'gradient_boosting': {
            'best_params': best_params_gb,
            'metrics': metrics_gb,
            'cv_score': study_gb.best_value
        }
    }
}

with open('optimization_report.json', 'w') as f:
    json.dump(report, f, indent=2, default=str)

print("   Rapport: optimization_report.json")
print("=" * 70)
print("  OPTIMISATION TERMINEE")
print("=" * 70)
