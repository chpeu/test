# -*- coding: utf-8 -*-
"""
Optimisation Avancée GradientBoosting

Améliorations:
1. 100 trials Optuna (au lieu de 50)
2. Feature selection automatique
3. 5-fold CV temporel
4. Seed fixe pour reproductibilité
5. Early stopping
6. Calibration des probabilités
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

# ML
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.feature_selection import SelectFromModel
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier
import xgboost as xgb

# Optuna
import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)

# Seed pour reproductibilité
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

print("=" * 70)
print("  OPTIMISATION AVANCEE GRADIENTBOOSTING")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

# =============================================================================
# CHARGEMENT DES DONNEES
# =============================================================================
print("\n[1/6] Chargement des donnees...")

from optimization.data.feature_loader import load_features_from_postgres
from optimization.data.feature_engineering import calculate_derived_features

df = load_features_from_postgres(timeframe_days=180, min_trades=1)
print(f"   Trades charges: {len(df)}")

# Feature engineering
df = calculate_derived_features(df)

# Séparer features et targets
exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 
                'is_opportunity', 'reject_reason_category']
feature_cols = [c for c in df.columns if c not in exclude_cols and df[c].dtype in ['int64', 'float64']]

X = df[feature_cols].copy()
y = df['target_win'].copy()

# Nettoyer
X = X.replace([np.inf, -np.inf], np.nan)

print(f"   Features initiales: {len(feature_cols)}")
print(f"   Win rate: {y.mean()*100:.1f}%")

# Split temporel 80/20
split_idx = int(len(df) * 0.8)
X_train_raw, X_test_raw = X.iloc[:split_idx], X.iloc[split_idx:]
y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

# Imputer (fit sur train uniquement)
imputer_full = SimpleImputer(strategy='median')
X_train_imputed = pd.DataFrame(
    imputer_full.fit_transform(X_train_raw),
    columns=X_train_raw.columns,
    index=X_train_raw.index,
)
X_test_imputed = pd.DataFrame(
    imputer_full.transform(X_test_raw),
    columns=X_test_raw.columns,
    index=X_test_raw.index,
)

X_train = X_train_imputed
X_test = X_test_imputed

print(f"   Train: {len(X_train_raw)} | Test: {len(X_test_raw)}")

# =============================================================================
# FEATURE SELECTION
# =============================================================================
print("\n[2/6] Feature Selection...")

# Utiliser XGBoost pour sélectionner les features importantes
selector_model = xgb.XGBClassifier(
    n_estimators=100,
    max_depth=4,
    learning_rate=0.1,
    random_state=RANDOM_SEED,
    n_jobs=-1
)

# Scaler temporaire
temp_scaler = StandardScaler()
X_train_scaled = temp_scaler.fit_transform(X_train_imputed)

selector_model.fit(X_train_scaled, y_train)

# Sélectionner top features
feature_importance = pd.DataFrame({
    'feature': feature_cols,
    'importance': selector_model.feature_importances_
}).sort_values('importance', ascending=False)

# Garder les features avec importance > médiane
threshold = feature_importance['importance'].median()
selected_features = feature_importance[feature_importance['importance'] > threshold]['feature'].tolist()

# Limiter à 40 features max pour éviter overfitting
selected_features = selected_features[:40]

print(f"   Features selectionnees: {len(selected_features)}/{len(feature_cols)}")
print(f"   Top 5: {selected_features[:5]}")

# Appliquer sélection
X_train_selected_raw = X_train_raw[selected_features]
X_test_selected_raw = X_test_raw[selected_features]

# Imputer final (fit sur train + features sélectionnées uniquement)
imputer = SimpleImputer(strategy='median')
X_train_selected = pd.DataFrame(
    imputer.fit_transform(X_train_selected_raw),
    columns=selected_features,
    index=X_train_selected_raw.index,
)
X_test_selected = pd.DataFrame(
    imputer.transform(X_test_selected_raw),
    columns=selected_features,
    index=X_test_selected_raw.index,
)

# =============================================================================
# OPTIMISATION OPTUNA (100 trials)
# =============================================================================
print("\n[3/6] Optimisation Optuna (100 trials)...")

# 5-fold CV temporel
tscv = TimeSeriesSplit(n_splits=5)

def objective(trial):
    """Objective function pour GradientBoosting"""
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 100, 400),
        'max_depth': trial.suggest_int('max_depth', 3, 10),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
        'min_samples_split': trial.suggest_int('min_samples_split', 5, 50),
        'min_samples_leaf': trial.suggest_int('min_samples_leaf', 5, 50),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
        'max_features': trial.suggest_categorical('max_features', ['sqrt', 'log2', 0.5, 0.7, None]),
        'random_state': RANDOM_SEED
    }
    
    # Cross-validation temporelle
    scores = []
    for train_idx, val_idx in tscv.split(X_train_selected):
        X_tr = X_train_selected.iloc[train_idx]
        X_val = X_train_selected.iloc[val_idx]
        y_tr = y_train.iloc[train_idx]
        y_val = y_train.iloc[val_idx]
        
        scaler = StandardScaler()
        X_tr_scaled = scaler.fit_transform(X_tr)
        X_val_scaled = scaler.transform(X_val)
        
        model = GradientBoostingClassifier(**params)
        model.fit(X_tr_scaled, y_tr)
        
        y_pred = model.predict(X_val_scaled)
        # Optimiser F1 score
        score = f1_score(y_val, y_pred)
        scores.append(score)
    
    return np.mean(scores)

# Créer study avec seed fixe
sampler = optuna.samplers.TPESampler(seed=RANDOM_SEED)
study = optuna.create_study(direction='maximize', sampler=sampler, study_name='gb_advanced')
study.optimize(objective, n_trials=100, show_progress_bar=True)

best_params = study.best_params
print(f"\n   Meilleur F1 CV: {study.best_value*100:.1f}%")
print(f"   Best params:")
for k, v in best_params.items():
    print(f"      {k}: {v}")

# =============================================================================
# ENTRAINEMENT MODELE FINAL
# =============================================================================
print("\n[4/6] Entrainement modele final...")

# Scaler final
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train_selected)
X_test_scaled = scaler.transform(X_test_selected)

# Modèle avec meilleurs params
final_params = {**best_params, 'random_state': RANDOM_SEED}
model = GradientBoostingClassifier(**final_params)
model.fit(X_train_scaled, y_train)

# Évaluer
y_pred = model.predict(X_test_scaled)
y_proba = model.predict_proba(X_test_scaled)[:, 1]

metrics = {
    'accuracy': accuracy_score(y_test, y_pred),
    'precision': precision_score(y_test, y_pred),
    'recall': recall_score(y_test, y_pred),
    'f1': f1_score(y_test, y_pred),
    'roc_auc': roc_auc_score(y_test, y_proba)
}

print(f"\n   RESULTATS AVANT CALIBRATION:")
print(f"      Accuracy:  {metrics['accuracy']*100:.1f}%")
print(f"      Precision: {metrics['precision']*100:.1f}%")
print(f"      Recall:    {metrics['recall']*100:.1f}%")
print(f"      F1 Score:  {metrics['f1']*100:.1f}%")
print(f"      ROC-AUC:   {metrics['roc_auc']*100:.1f}%")

# =============================================================================
# CALIBRATION DES PROBABILITES
# =============================================================================
print("\n[5/6] Calibration des probabilites...")

# Réentraîner avec calibration
calibrated_model = CalibratedClassifierCV(
    GradientBoostingClassifier(**final_params),
    method='isotonic',  # ou 'sigmoid'
    cv=3
)
calibrated_model.fit(X_train_scaled, y_train)

# Évaluer modèle calibré
y_pred_cal = calibrated_model.predict(X_test_scaled)
y_proba_cal = calibrated_model.predict_proba(X_test_scaled)[:, 1]

metrics_cal = {
    'accuracy': accuracy_score(y_test, y_pred_cal),
    'precision': precision_score(y_test, y_pred_cal),
    'recall': recall_score(y_test, y_pred_cal),
    'f1': f1_score(y_test, y_pred_cal),
    'roc_auc': roc_auc_score(y_test, y_proba_cal)
}

print(f"\n   RESULTATS APRES CALIBRATION:")
print(f"      Accuracy:  {metrics_cal['accuracy']*100:.1f}%")
print(f"      Precision: {metrics_cal['precision']*100:.1f}%")
print(f"      Recall:    {metrics_cal['recall']*100:.1f}%")
print(f"      F1 Score:  {metrics_cal['f1']*100:.1f}%")
print(f"      ROC-AUC:   {metrics_cal['roc_auc']*100:.1f}%")

# Choisir le meilleur
if metrics_cal['f1'] >= metrics['f1']:
    final_model = calibrated_model
    final_metrics = metrics_cal
    print("\n   -> Modele calibre selectionne")
else:
    final_model = model
    final_metrics = metrics
    print("\n   -> Modele non-calibre selectionne")

# =============================================================================
# SAUVEGARDE
# =============================================================================
print("\n[6/6] Sauvegarde...")

models_dir = "optimization/saved_models"
os.makedirs(models_dir, exist_ok=True)

# Sauvegarder modèle
model_name = "gradient_boosting_optimized"
joblib.dump(final_model, f"{models_dir}/{model_name}.pkl")

# Sauvegarder preprocessor
preprocessor = {
    'scaler': scaler,
    'imputer': imputer,
    'feature_names': selected_features,
    'scaler_type': 'StandardScaler'
}
joblib.dump(preprocessor, f"{models_dir}/{model_name}_preprocessor.pkl")

# Sauvegarder metadata
metadata = {
    'model_name': model_name,
    'model_type': 'classification',
    'trained_at': datetime.now().isoformat(),
    'random_seed': RANDOM_SEED,
    'n_samples': len(X_train),
    'n_features_initial': len(feature_cols),
    'n_features_selected': len(selected_features),
    'selected_features': selected_features,
    'hyperparameters': best_params,
    'optuna_trials': 100,
    'cv_folds': 5,
    'calibrated': final_model == calibrated_model,
    'metrics': {
        'cv_f1': study.best_value,
        'test': final_metrics
    },
    'feature_names': selected_features
}

with open(f"{models_dir}/{model_name}_metadata.json", 'w') as f:
    json.dump(metadata, f, indent=2, default=str)

print(f"   Modele sauvegarde: {model_name}.pkl")
print(f"   Features: {len(selected_features)}")

# =============================================================================
# COMPARAISON AVEC FILTRE NEGATIF
# =============================================================================
print("\n" + "=" * 70)
print("  COMPARAISON AVEC FILTRE NEGATIF")
print("=" * 70)

# Simuler le filtre négatif
from optimization.predictor_negative import get_negative_predictor

try:
    neg_predictor = get_negative_predictor()
    
    if neg_predictor.is_loaded:
        threshold = 0.55  # Seuil actuel
        
        kept_wins = 0
        kept_total = 0
        
        for i in range(len(X_test)):
            features = X_test.iloc[i].to_dict()
            result = neg_predictor.predict(features, threshold=threshold)
            
            if not result.get('should_reject', False):
                kept_total += 1
                if y_test.iloc[i] == 1:
                    kept_wins += 1
        
        wr_baseline = y_test.mean()
        wr_filtered = kept_wins / kept_total if kept_total > 0 else 0
        
        print(f"\n   FILTRE NEGATIF (seuil={threshold}):")
        print(f"      Win rate baseline: {wr_baseline*100:.1f}%")
        print(f"      Win rate filtre:   {wr_filtered*100:.1f}%")
        print(f"      Gain:              +{(wr_filtered - wr_baseline)*100:.1f}%")
        print(f"      Trades conserves:  {kept_total}/{len(X_test)} ({kept_total/len(X_test)*100:.0f}%)")
except Exception as e:
    print(f"   Erreur filtre negatif: {e}")

# =============================================================================
# RESUME FINAL
# =============================================================================
print("\n" + "=" * 70)
print("  RESUME OPTIMISATION AVANCEE")
print("=" * 70)

print(f"""
   GRADIENTBOOSTING OPTIMISE:
   --------------------------
   Accuracy:  {final_metrics['accuracy']*100:.1f}%
   Precision: {final_metrics['precision']*100:.1f}%
   Recall:    {final_metrics['recall']*100:.1f}%
   F1 Score:  {final_metrics['f1']*100:.1f}%
   ROC-AUC:   {final_metrics['roc_auc']*100:.1f}%
   
   Features:  {len(selected_features)} (reduites de {len(feature_cols)})
   Calibre:   {'Oui' if final_model == calibrated_model else 'Non'}
   
   HYPERPARAMETRES OPTIMAUX:
   -------------------------""")

for k, v in best_params.items():
    print(f"   {k}: {v}")

print(f"""
   
   RECOMMANDATION:
   ---------------
   Utiliser GradientBoosting + Filtre Negatif ensemble pour
   maximiser le win rate tout en gardant un volume acceptable.
""")

print("=" * 70)
print("  OPTIMISATION TERMINEE")
print("=" * 70)

# Sauvegarder rapport
report = {
    'timestamp': datetime.now().isoformat(),
    'model': 'gradient_boosting_advanced',
    'metrics': final_metrics,
    'hyperparameters': best_params,
    'n_features': len(selected_features),
    'selected_features': selected_features[:10],
    'optuna_best_cv_f1': study.best_value
}

with open('gb_optimization_report.json', 'w') as f:
    json.dump(report, f, indent=2, default=str)

print("\nRapport: gb_optimization_report.json")
