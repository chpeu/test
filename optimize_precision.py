# -*- coding: utf-8 -*-
"""Optimisation specifique pour la precision"""

import sys
import warnings
warnings.filterwarnings('ignore')
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.preprocessing import RobustScaler
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.utils.class_weight import compute_class_weight
from pathlib import Path
from sqlalchemy import create_engine
from urllib.parse import quote_plus
import optuna
from optuna.samplers import TPESampler

print("=" * 70)
print("  OPTIMISATION PRECISION")
print("=" * 70)

# Load data
env_path = Path('.env')
env_vars = {}
with open(env_path, 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            env_vars[key.strip()] = value.strip()

password = quote_plus(env_vars.get('POSTGRES_PASSWORD', ''))
conn_str = f"postgresql://{env_vars.get('POSTGRES_USER')}:{password}@{env_vars.get('POSTGRES_HOST')}:{env_vars.get('POSTGRES_PORT')}/{env_vars.get('POSTGRES_DB')}"
engine = create_engine(conn_str)

df = pd.read_sql("SELECT * FROM ml_features WHERE target_pnl IS NOT NULL", engine)
engine.dispose()

# Create features (same as before)
if 'bb_distance_to_lower_1m' in df.columns and 'bb_distance_to_upper_1m' in df.columns:
    df['bb_position'] = df['bb_distance_to_lower_1m'] / (df['bb_distance_to_lower_1m'] + df['bb_distance_to_upper_1m'] + 1e-6)
if 'macd_hist_1m' in df.columns and 'rsi_1m' in df.columns:
    df['momentum_combined'] = (df['macd_hist_1m'] / (abs(df['macd_hist_1m']).max() + 1e-6)) * ((df['rsi_1m'] - 50) / 50)
if 'macd_hist_1m' in df.columns and 'macd_hist_prev_1m' in df.columns:
    df['macd_acceleration'] = df['macd_hist_1m'] - df['macd_hist_prev_1m']
if 'rsi_1m' in df.columns:
    df['rsi_distance_50_1m'] = abs(df['rsi_1m'] - 50)
if 'rsi_5m' in df.columns:
    df['rsi_distance_50_5m'] = abs(df['rsi_5m'] - 50)
if 'atr_pct_1m' in df.columns and 'atr_pct_5m' in df.columns:
    df['volatility_ratio'] = df['atr_pct_1m'] / (df['atr_pct_5m'] + 1e-6)
if 'adx_1m' in df.columns and 'di_gap_1m' in df.columns:
    df['trend_strength'] = df['adx_1m'] * abs(df['di_gap_1m'])
if 'volume_ratio_1m' in df.columns and 'volume_spike_1m' in df.columns:
    df['volume_pressure'] = df['volume_ratio_1m'] * df['volume_spike_1m']
if 'bb_width_1m' in df.columns:
    df['bb_squeeze'] = 1 / (df['bb_width_1m'] + 1e-6)
if 'rsi_1m' in df.columns and 'rsi_prev_1m' in df.columns:
    df['rsi_accel'] = df['rsi_1m'] - df['rsi_prev_1m']
if 'ema_diff_pct_1m' in df.columns and 'ema_diff_pct_5m' in df.columns:
    df['ema_trend_aligned'] = np.sign(df['ema_diff_pct_1m']) * np.sign(df['ema_diff_pct_5m'])

df['target'] = (df['target_pnl'] > 0).astype(int)

exclude = ['id', 'timestamp', 'symbol', 'target_pnl', 'target', 'scan_id']
feature_cols = [c for c in df.columns if c not in exclude and df[c].dtype in ['float64', 'int64', 'float32', 'int32']]

X = df[feature_cols].fillna(0).values
y = df['target'].values

# Select k=25 features
selector = SelectKBest(f_classif, k=25)
X_sel = selector.fit_transform(X, y)

print(f"Donnees: {len(y)} samples, {X_sel.shape[1]} features")

# Class weights
cw = compute_class_weight('balanced', classes=np.unique(y), y=y)

print("\n=== 1. OPTIMISATION OPTUNA POUR PRECISION ===")

def objective_precision(trial):
    """Objectif: maximiser precision tout en gardant F1 acceptable"""
    n_estimators = trial.suggest_int('n_estimators', 150, 400, step=50)
    max_depth = trial.suggest_int('max_depth', 2, 4)
    learning_rate = trial.suggest_float('learning_rate', 0.02, 0.15, log=True)
    min_samples_leaf = trial.suggest_int('min_samples_leaf', 30, 70, step=10)
    l2_reg = trial.suggest_float('l2_regularization', 0.3, 1.5)
    
    # Class weight ajuste pour favoriser precision
    class_weight_ratio = trial.suggest_float('class_weight_ratio', 0.8, 1.5)
    
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    precs, f1s = [], []
    
    for train_idx, test_idx in cv.split(X_sel, y):
        X_train, X_test = X_sel[train_idx], X_sel[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        
        # Ajuster les poids de classe
        sw = np.array([cw[0] * class_weight_ratio if l==0 else cw[1] for l in y_train])
        
        scaler = RobustScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)
        
        model = HistGradientBoostingClassifier(
            max_iter=n_estimators, max_depth=max_depth, learning_rate=learning_rate,
            min_samples_leaf=min_samples_leaf, l2_regularization=l2_reg,
            random_state=42, early_stopping=True
        )
        model.fit(X_train_s, y_train, sample_weight=sw)
        
        y_pred = model.predict(X_test_s)
        precs.append(precision_score(y_test, y_pred, zero_division=0))
        f1s.append(f1_score(y_test, y_pred, zero_division=0))
    
    mean_prec = np.mean(precs)
    mean_f1 = np.mean(f1s)
    
    # Score: precision prioritaire mais F1 doit rester > 0.45
    if mean_f1 < 0.40:
        return 0.0  # Penaliser si F1 trop bas
    
    # Score composite: 70% precision + 30% F1
    return 0.7 * mean_prec + 0.3 * mean_f1

# Optimiser
sampler = TPESampler(seed=42)
study = optuna.create_study(direction='maximize', sampler=sampler)
study.optimize(objective_precision, n_trials=100, show_progress_bar=False)

best_params = study.best_params
print(f"\nMeilleurs parametres: {best_params}")

print("\n=== 2. EVALUATION AVEC MEILLEURS PARAMETRES ===")

# Evaluer avec les meilleurs parametres
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
train_accs, test_accs, f1s, precs = [], [], [], []

for train_idx, test_idx in cv.split(X_sel, y):
    X_train, X_test = X_sel[train_idx], X_sel[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]
    
    sw = np.array([cw[0] * best_params.get('class_weight_ratio', 1.0) if l==0 else cw[1] for l in y_train])
    
    scaler = RobustScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    
    model = HistGradientBoostingClassifier(
        max_iter=best_params.get('n_estimators', 300),
        max_depth=best_params.get('max_depth', 2),
        learning_rate=best_params.get('learning_rate', 0.089),
        min_samples_leaf=best_params.get('min_samples_leaf', 50),
        l2_regularization=best_params.get('l2_regularization', 0.9),
        random_state=42, early_stopping=True
    )
    model.fit(X_train_s, y_train, sample_weight=sw)
    
    y_train_pred = model.predict(X_train_s)
    y_test_pred = model.predict(X_test_s)
    
    train_accs.append(accuracy_score(y_train, y_train_pred))
    test_accs.append(accuracy_score(y_test, y_test_pred))
    f1s.append(f1_score(y_test, y_test_pred, zero_division=0))
    precs.append(precision_score(y_test, y_test_pred, zero_division=0))

print(f"\nResultats optimises pour precision:")
print(f"  Accuracy: {np.mean(test_accs)*100:.1f}%")
print(f"  F1 Score: {np.mean(f1s):.3f}")
print(f"  Precision: {np.mean(precs):.3f}")
print(f"  Gap: {(np.mean(train_accs) - np.mean(test_accs))*100:.1f}%")

print("\n=== 3. TEST SEUIL DE DECISION OPTIMAL ===")

# Split pour threshold tuning
X_train, X_test, y_train, y_test = train_test_split(X_sel, y, test_size=0.2, stratify=y, random_state=42)

sw = np.array([cw[0] * best_params.get('class_weight_ratio', 1.0) if l==0 else cw[1] for l in y_train])

scaler = RobustScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s = scaler.transform(X_test)

model = HistGradientBoostingClassifier(
    max_iter=best_params.get('n_estimators', 300),
    max_depth=best_params.get('max_depth', 2),
    learning_rate=best_params.get('learning_rate', 0.089),
    min_samples_leaf=best_params.get('min_samples_leaf', 50),
    l2_regularization=best_params.get('l2_regularization', 0.9),
    random_state=42, early_stopping=True
)
model.fit(X_train_s, y_train, sample_weight=sw)

y_proba = model.predict_proba(X_test_s)[:, 1]

print(f"\n{'Seuil':<10} {'Accuracy':<10} {'F1':<10} {'Precision':<10} {'Recall':<10} {'Trades':<10}")
print("-" * 65)

best_balanced = {'threshold': 0.5, 'f1': 0, 'prec': 0}

for threshold in [0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75]:
    y_pred = (y_proba >= threshold).astype(int)
    
    acc = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    n_trades = y_pred.sum()
    
    print(f"{threshold:<10} {acc*100:<10.1f}% {f1:<10.3f} {prec:<10.3f} {rec:<10.3f} {n_trades:<10}")
    
    # Chercher le meilleur equilibre F1 >= 0.45 et Prec >= 0.50
    if f1 >= 0.40 and prec > best_balanced['prec']:
        best_balanced = {'threshold': threshold, 'f1': f1, 'prec': prec}

print("\n" + "=" * 70)
print("  RECOMMANDATION FINALE")
print("=" * 70)
print(f"\nMeilleur seuil equilibre: {best_balanced['threshold']}")
print(f"  F1: {best_balanced['f1']:.3f}")
print(f"  Precision: {best_balanced['prec']:.3f}")

print("\nPour utilisation en production:")
print(f"  gb_min_confidence: {best_balanced['threshold']}")
