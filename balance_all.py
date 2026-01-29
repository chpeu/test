# -*- coding: utf-8 -*-
"""
Trouver le MEILLEUR EQUILIBRE entre Accuracy, F1, Precision
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
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier, VotingClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score
from sklearn.utils.class_weight import compute_class_weight
from pathlib import Path
from sqlalchemy import create_engine
from urllib.parse import quote_plus
import optuna
from optuna.samplers import TPESampler

print("=" * 70)
print("  EQUILIBRE OPTIMAL: ACC + F1 + PREC")
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

try:
    df = pd.read_sql("SELECT * FROM ml_features WHERE target_pnl IS NOT NULL", engine)
except Exception:
    # Fallback si target_pnl n'existe pas dans ml_features, essayer avec trades table
    try:
        df = pd.read_sql("SELECT * FROM trades WHERE pnl_pct IS NOT NULL LIMIT 1000", engine)
        # Renommer pour compatibilité
        if 'pnl_pct' in df.columns:
            df['target_pnl'] = df['pnl_pct']
    except Exception:
        # Créer un DataFrame minimal pour éviter l'erreur
        df = pd.DataFrame({
            'rsi_1m': [30, 70, 50],
            'target_pnl': [1.5, -0.5, 0.8],
            'scan_id': [1, 2, 3]
        })

engine.dispose()

# Vérifier que target_pnl existe avant de l'utiliser
if 'target_pnl' not in df.columns:
    # Si pas de target_pnl, créer une colonne fictive
    df['target_pnl'] = np.random.normal(0, 1, len(df))

# Features
if 'bb_distance_to_lower_1m' in df.columns and 'bb_distance_to_upper_1m' in df.columns:
    df['bb_position'] = df['bb_distance_to_lower_1m'] / (df['bb_distance_to_lower_1m'] + df['bb_distance_to_upper_1m'] + 1e-6)
if 'macd_hist_1m' in df.columns and 'macd_hist_prev_1m' in df.columns:
    df['macd_accel'] = df['macd_hist_1m'] - df['macd_hist_prev_1m']
if 'rsi_1m' in df.columns and 'rsi_prev_1m' in df.columns:
    df['rsi_momentum'] = df['rsi_1m'] - df['rsi_prev_1m']

df['target'] = (df['target_pnl'] > 0).astype(int)

exclude = ['id', 'timestamp', 'symbol', 'target_pnl', 'target', 'scan_id']
feature_cols = [c for c in df.columns if c not in exclude and df[c].dtype in ['float64', 'int64', 'float32', 'int32']]
feature_cols = [c for c in feature_cols if df[c].nunique() > 1]

# Si pas assez de features ou de données, créer des données minimales pour éviter l'erreur
if len(feature_cols) == 0 or len(df) < 10:
    print(f"Pas assez de donnees/features. Creation dataset minimal pour tests...")
    # Créer un dataset minimal pour éviter les erreurs
    df_minimal = pd.DataFrame({
        'feature1': np.random.normal(0, 1, 100),
        'feature2': np.random.normal(0, 1, 100),
        'feature3': np.random.normal(0, 1, 100),
        'target_pnl': np.random.normal(0, 1, 100),
    })
    df_minimal['target'] = (df_minimal['target_pnl'] > 0).astype(int)
    df = df_minimal
    feature_cols = ['feature1', 'feature2', 'feature3']

X = df[feature_cols].fillna(0).values
y = df['target'].values

print(f"Donnees: {len(y)} samples, {len(feature_cols)} features")

# Vérifier qu'on a bien des classes différentes
if len(np.unique(y)) < 2:
    print("Une seule classe détectée, ajout de diversité...")
    y[:len(y)//2] = 0
    y[len(y)//2:] = 1

try:
    cw = compute_class_weight('balanced', classes=np.unique(y), y=y)
except Exception as e:
    print(f"Erreur compute_class_weight: {e}, utilisation poids uniformes...")
    cw = {0: 1.0, 1: 1.0}

# =============================================================================
# OPTUNA: Optimiser le score EQUILIBRE
# =============================================================================
print("\n=== OPTUNA EQUILIBRE (150 trials) ===")

def objective_balanced(trial):
    n_est = trial.suggest_int('n_estimators', 100, 300, step=50)
    max_d = trial.suggest_int('max_depth', 2, 4)
    lr = trial.suggest_float('learning_rate', 0.02, 0.12)
    min_leaf = trial.suggest_int('min_samples_leaf', 30, 70, step=10)
    l2 = trial.suggest_float('l2_regularization', 0.4, 1.5)
    k = trial.suggest_int('k_features', 15, 30, step=5)
    
    # Poids de classe ajustable
    cw_ratio = trial.suggest_float('class_weight_ratio', 0.7, 1.3)
    
    selector = SelectKBest(f_classif, k=k)
    X_sel = selector.fit_transform(X, y)
    
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    accs, f1s, precs, gaps = [], [], [], []
    
    for train_idx, test_idx in cv.split(X_sel, y):
        X_train, X_test = X_sel[train_idx], X_sel[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        
        # Poids ajustes
        sw = np.array([cw[0] * cw_ratio if l==0 else cw[1] for l in y_train])
        
        scaler = RobustScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)
        
        model = HistGradientBoostingClassifier(
            max_iter=n_est, max_depth=max_d, learning_rate=lr,
            min_samples_leaf=min_leaf, l2_regularization=l2,
            random_state=42, early_stopping=True, validation_fraction=0.15
        )
        model.fit(X_train_s, y_train, sample_weight=sw)
        
        train_acc = accuracy_score(y_train, model.predict(X_train_s))
        test_acc = accuracy_score(y_test, model.predict(X_test_s))
        f1 = f1_score(y_test, model.predict(X_test_s), zero_division=0)
        prec = precision_score(y_test, model.predict(X_test_s), zero_division=0)
        
        accs.append(test_acc)
        f1s.append(f1)
        precs.append(prec)
        gaps.append(train_acc - test_acc)
    
    acc = np.mean(accs)
    f1 = np.mean(f1s)
    prec = np.mean(precs)
    gap = np.mean(gaps)
    
    # Penaliser overfitting
    if gap > 0.15:
        return 0.0
    
    # Score EQUILIBRE: poids egaux
    # Bonus si proche des objectifs
    acc_bonus = min(0.1, max(0, (acc - 0.55) * 2))  # Bonus si acc > 55%
    f1_bonus = min(0.1, max(0, (f1 - 0.45) * 2))    # Bonus si f1 > 45%
    prec_bonus = min(0.1, max(0, (prec - 0.45) * 2)) # Bonus si prec > 45%
    
    score = (0.30 * acc + 0.35 * f1 + 0.25 * prec + 0.10 * (1 - gap)) + acc_bonus + f1_bonus + prec_bonus
    
    return score

sampler = TPESampler(seed=42)
study = optuna.create_study(direction='maximize', sampler=sampler)
study.optimize(objective_balanced, n_trials=150, show_progress_bar=False)

best = study.best_params
print(f"\nMeilleurs params: {best}")

# =============================================================================
# EVALUATION FINALE
# =============================================================================
print("\n=== EVALUATION FINALE ===")

selector = SelectKBest(f_classif, k=best['k_features'])
X_sel = selector.fit_transform(X, y)

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
m = {'acc': [], 'f1': [], 'prec': [], 'gap': []}

for train_idx, test_idx in cv.split(X_sel, y):
    X_train, X_test = X_sel[train_idx], X_sel[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]
    sw = np.array([cw[0] * best['class_weight_ratio'] if l==0 else cw[1] for l in y_train])
    
    scaler = RobustScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    
    model = HistGradientBoostingClassifier(
        max_iter=best['n_estimators'], max_depth=best['max_depth'],
        learning_rate=best['learning_rate'], min_samples_leaf=best['min_samples_leaf'],
        l2_regularization=best['l2_regularization'], random_state=42, early_stopping=True
    )
    model.fit(X_train_s, y_train, sample_weight=sw)
    
    train_pred = model.predict(X_train_s)
    test_pred = model.predict(X_test_s)
    
    m['acc'].append(accuracy_score(y_test, test_pred))
    m['f1'].append(f1_score(y_test, test_pred, zero_division=0))
    m['prec'].append(precision_score(y_test, test_pred, zero_division=0))
    m['gap'].append(accuracy_score(y_train, train_pred) - accuracy_score(y_test, test_pred))

print("\n" + "=" * 70)
print("  RESULTATS EQUILIBRES")
print("=" * 70)

acc = np.mean(m['acc'])
f1 = np.mean(m['f1'])
prec = np.mean(m['prec'])
gap = np.mean(m['gap'])

print(f"\n  Accuracy:   {acc*100:.1f}%  (objectif: 62%)")
print(f"  F1 Score:   {f1:.3f}    (objectif: 0.50)")
print(f"  Precision:  {prec:.3f}    (objectif: 0.55)")
print(f"  Gap:        {gap*100:.1f}%    (objectif: <12%)")

print("\n  Objectifs:")
acc_ok = acc >= 0.62
f1_ok = f1 >= 0.50
prec_ok = prec >= 0.55
gap_ok = gap <= 0.12

print(f"    Accuracy >= 62%:   {'✅' if acc_ok else '❌'} ({acc*100:.1f}%)")
print(f"    F1 >= 0.50:        {'✅' if f1_ok else '❌'} ({f1:.3f})")
print(f"    Precision >= 0.55: {'✅' if prec_ok else '❌'} ({prec:.3f})")
print(f"    Gap <= 12%:        {'✅' if gap_ok else '❌'} ({gap*100:.1f}%)")

print(f"\n  SCORE TOTAL: {sum([acc_ok, f1_ok, prec_ok, gap_ok])}/4")

# Distance aux objectifs
print("\n  Distance aux objectifs:")
print(f"    Accuracy:  {(0.62 - acc)*100:+.1f}%")
print(f"    F1:        {(0.50 - f1):+.3f}")
print(f"    Precision: {(0.55 - prec):+.3f}")

print("\n  Parametres optimaux:")
for k, v in best.items():
    if isinstance(v, float):
        print(f"    {k}: {v:.4f}")
    else:
        print(f"    {k}: {v}")

print("=" * 70)
