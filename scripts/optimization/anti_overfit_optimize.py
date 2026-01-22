# -*- coding: utf-8 -*-
"""
Anti-overfitting + Maximiser accuracy et precision
"""

import sys
import warnings
warnings.filterwarnings('ignore')
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import RobustScaler
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.ensemble import HistGradientBoostingClassifier, GradientBoostingClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score
from sklearn.utils.class_weight import compute_class_weight
from pathlib import Path
from sqlalchemy import create_engine
from urllib.parse import quote_plus
import optuna
from optuna.samplers import TPESampler

print("=" * 70)
print("  ANTI-OVERFITTING + MAXIMISER ACCURACY/PRECISION")
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

# Features essentielles uniquement (moins = moins d'overfitting)
print("\n=== CREATION FEATURES ESSENTIELLES SEULEMENT ===")

# Features de base
if 'bb_distance_to_lower_1m' in df.columns and 'bb_distance_to_upper_1m' in df.columns:
    df['bb_position'] = df['bb_distance_to_lower_1m'] / (df['bb_distance_to_lower_1m'] + df['bb_distance_to_upper_1m'] + 1e-6)
if 'macd_hist_1m' in df.columns and 'rsi_1m' in df.columns:
    df['momentum_combined'] = (df['macd_hist_1m'] / (abs(df['macd_hist_1m']).max() + 1e-6)) * ((df['rsi_1m'] - 50) / 50)
if 'macd_hist_1m' in df.columns and 'macd_hist_prev_1m' in df.columns:
    df['macd_acceleration'] = df['macd_hist_1m'] - df['macd_hist_prev_1m']
if 'rsi_1m' in df.columns:
    df['rsi_distance_50'] = abs(df['rsi_1m'] - 50)
if 'atr_pct_1m' in df.columns and 'atr_pct_5m' in df.columns:
    df['volatility_ratio'] = df['atr_pct_1m'] / (df['atr_pct_5m'] + 1e-6)

df['target'] = (df['target_pnl'] > 0).astype(int)

exclude = ['id', 'timestamp', 'symbol', 'target_pnl', 'target', 'scan_id']
feature_cols = [c for c in df.columns if c not in exclude and df[c].dtype in ['float64', 'int64', 'float32', 'int32']]

X = df[feature_cols].fillna(0).values
y = df['target'].values

print(f"Donnees: {len(y)} samples, {len(feature_cols)} features")

cw = compute_class_weight('balanced', classes=np.unique(y), y=y)

# =============================================================================
# OPTUNA AVEC FORTE REGULARISATION
# =============================================================================
print("\n=== OPTUNA ANTI-OVERFITTING (150 trials) ===")

def objective_anti_overfit(trial):
    """Optimiser accuracy/precision SANS overfitting"""
    # Parametres TRES conservateurs
    n_estimators = trial.suggest_int('n_estimators', 80, 200, step=20)
    max_depth = trial.suggest_int('max_depth', 2, 3)  # Max 3!
    learning_rate = trial.suggest_float('learning_rate', 0.01, 0.06)  # Lent
    min_samples_leaf = trial.suggest_int('min_samples_leaf', 40, 80, step=10)  # Haut
    l2_reg = trial.suggest_float('l2_regularization', 0.8, 2.0)  # Fort
    k_features = trial.suggest_int('k_features', 15, 25, step=5)  # Peu
    
    selector = SelectKBest(f_classif, k=k_features)
    X_sel = selector.fit_transform(X, y)
    
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    accs, f1s, precs, gaps = [], [], [], []
    
    for train_idx, test_idx in cv.split(X_sel, y):
        X_train, X_test = X_sel[train_idx], X_sel[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        sw = np.array([cw[0] if l==0 else cw[1] for l in y_train])
        
        scaler = RobustScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)
        
        model = HistGradientBoostingClassifier(
            max_iter=n_estimators, max_depth=max_depth, learning_rate=learning_rate,
            min_samples_leaf=min_samples_leaf, l2_regularization=l2_reg,
            random_state=42, early_stopping=True, n_iter_no_change=20,
            validation_fraction=0.2  # Plus de validation
        )
        model.fit(X_train_s, y_train, sample_weight=sw)
        
        y_train_pred = model.predict(X_train_s)
        y_test_pred = model.predict(X_test_s)
        
        train_acc = accuracy_score(y_train, y_train_pred)
        test_acc = accuracy_score(y_test, y_test_pred)
        gap = train_acc - test_acc
        
        accs.append(test_acc)
        f1s.append(f1_score(y_test, y_test_pred, zero_division=0))
        precs.append(precision_score(y_test, y_test_pred, zero_division=0))
        gaps.append(gap)
    
    acc = np.mean(accs)
    f1 = np.mean(f1s)
    prec = np.mean(precs)
    gap = np.mean(gaps)
    
    # PENALISER FORTEMENT l'overfitting
    if gap > 0.15:
        return 0.0  # Rejeter si gap > 15%
    
    # Score: accuracy prioritaire, puis precision, puis f1, bonus pour gap faible
    score = 0.40 * acc + 0.30 * prec + 0.20 * f1 + 0.10 * (1 - gap * 2)
    
    return score

sampler = TPESampler(seed=42)
study = optuna.create_study(direction='maximize', sampler=sampler)
study.optimize(objective_anti_overfit, n_trials=150, show_progress_bar=False)

best_params = study.best_params
print(f"\nMeilleurs parametres: {best_params}")

# =============================================================================
# EVALUATION FINALE
# =============================================================================
print("\n=== EVALUATION FINALE ===")

selector = SelectKBest(f_classif, k=best_params.get('k_features', 20))
X_sel = selector.fit_transform(X, y)
selected_features = [feature_cols[i] for i in selector.get_support(indices=True)]

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
metrics = {'acc': [], 'f1': [], 'prec': [], 'gap': []}

for train_idx, test_idx in cv.split(X_sel, y):
    X_train, X_test = X_sel[train_idx], X_sel[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]
    sw = np.array([cw[0] if l==0 else cw[1] for l in y_train])
    
    scaler = RobustScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    
    model = HistGradientBoostingClassifier(
        max_iter=best_params.get('n_estimators', 150),
        max_depth=best_params.get('max_depth', 2),
        learning_rate=best_params.get('learning_rate', 0.04),
        min_samples_leaf=best_params.get('min_samples_leaf', 50),
        l2_regularization=best_params.get('l2_regularization', 1.0),
        random_state=42, early_stopping=True, n_iter_no_change=20,
        validation_fraction=0.2
    )
    model.fit(X_train_s, y_train, sample_weight=sw)
    
    y_train_pred = model.predict(X_train_s)
    y_test_pred = model.predict(X_test_s)
    
    metrics['acc'].append(accuracy_score(y_test, y_test_pred))
    metrics['f1'].append(f1_score(y_test, y_test_pred, zero_division=0))
    metrics['prec'].append(precision_score(y_test, y_test_pred, zero_division=0))
    metrics['gap'].append(accuracy_score(y_train, y_train_pred) - accuracy_score(y_test, y_test_pred))

print("\n" + "=" * 70)
print("  RESULTATS ANTI-OVERFITTING")
print("=" * 70)
print(f"\n  Accuracy:   {np.mean(metrics['acc'])*100:.1f}%  (objectif: 62%)")
print(f"  F1 Score:   {np.mean(metrics['f1']):.3f}    (objectif: 0.50)")
print(f"  Precision:  {np.mean(metrics['prec']):.3f}    (objectif: 0.55)")
print(f"  Gap:        {np.mean(metrics['gap'])*100:.1f}%    (objectif: <12%)")

print("\n  Objectifs:")
acc_ok = np.mean(metrics['acc']) >= 0.62
f1_ok = np.mean(metrics['f1']) >= 0.50
prec_ok = np.mean(metrics['prec']) >= 0.55
gap_ok = np.mean(metrics['gap']) <= 0.12

print(f"    Accuracy >= 62%:   {'✅' if acc_ok else '❌'} ({np.mean(metrics['acc'])*100:.1f}%)")
print(f"    F1 >= 0.50:        {'✅' if f1_ok else '❌'} ({np.mean(metrics['f1']):.3f})")
print(f"    Precision >= 0.55: {'✅' if prec_ok else '❌'} ({np.mean(metrics['prec']):.3f})")
print(f"    Gap <= 12%:        {'✅' if gap_ok else '❌'} ({np.mean(metrics['gap'])*100:.1f}%)")

print(f"\n  Score total: {sum([acc_ok, f1_ok, prec_ok, gap_ok])}/4")

print("\n  Features selectionnees:")
for f in selected_features[:10]:
    print(f"    - {f}")
if len(selected_features) > 10:
    print(f"    ... et {len(selected_features) - 10} autres")

print("\n  Parametres optimaux:")
for k, v in best_params.items():
    print(f"    {k}: {v}")

print("=" * 70)

# Test avec seuils de decision
print("\n=== TEST SEUILS DE DECISION ===")

from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(X_sel, y, test_size=0.2, stratify=y, random_state=42)
sw = np.array([cw[0] if l==0 else cw[1] for l in y_train])

scaler = RobustScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s = scaler.transform(X_test)

model = HistGradientBoostingClassifier(
    max_iter=best_params.get('n_estimators', 150),
    max_depth=best_params.get('max_depth', 2),
    learning_rate=best_params.get('learning_rate', 0.04),
    min_samples_leaf=best_params.get('min_samples_leaf', 50),
    l2_regularization=best_params.get('l2_regularization', 1.0),
    random_state=42, early_stopping=True
)
model.fit(X_train_s, y_train, sample_weight=sw)

y_proba = model.predict_proba(X_test_s)[:, 1]

print(f"\n{'Seuil':<10} {'Acc':<10} {'F1':<10} {'Prec':<10} {'Trades':<10}")
print("-" * 55)

best = {'threshold': 0.5, 'score': 0}

for threshold in [0.40, 0.45, 0.50, 0.55, 0.60]:
    y_pred = (y_proba >= threshold).astype(int)
    
    acc = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    prec = precision_score(y_test, y_pred, zero_division=0)
    n_trades = y_pred.sum()
    
    print(f"{threshold:<10} {acc*100:<10.1f}% {f1:<10.3f} {prec:<10.3f} {n_trades:<10}")
    
    # Score equilibre
    score = 0.4 * acc + 0.3 * f1 + 0.3 * prec
    if score > best['score']:
        best = {'threshold': threshold, 'score': score, 'acc': acc, 'f1': f1, 'prec': prec}

print(f"\nMeilleur seuil: {best['threshold']}")
print(f"  Acc={best['acc']*100:.1f}%, F1={best['f1']:.3f}, Prec={best['prec']:.3f}")
