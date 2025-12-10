# -*- coding: utf-8 -*-
"""Quick optimize pour reduire le Gap"""

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
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score
from sklearn.utils.class_weight import compute_class_weight
from pathlib import Path
from sqlalchemy import create_engine
from urllib.parse import quote_plus

print("=" * 60)
print("  OPTIMISATION RAPIDE - REDUIRE LE GAP")
print("=" * 60)

# Load clean data
env_vars = {}
with open('.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env_vars[k.strip()] = v.strip()

password = quote_plus(env_vars.get('POSTGRES_PASSWORD', ''))
conn_str = f"postgresql://{env_vars.get('POSTGRES_USER')}:{password}@{env_vars.get('POSTGRES_HOST')}:{env_vars.get('POSTGRES_PORT')}/{env_vars.get('POSTGRES_DB')}"
engine = create_engine(conn_str)

df = pd.read_sql("SELECT * FROM ml_features_clean WHERE target_pnl IS NOT NULL", engine)
engine.dispose()

print(f"Donnees nettoyees: {len(df)} samples")

# Features
df['target'] = (df['target_pnl'] > 0).astype(int)
exclude = ['id', 'timestamp', 'symbol', 'target_pnl', 'target', 'scan_id', 'is_opportunity', 'target_win', 'reject_reason_category']
feature_cols = [c for c in df.columns if c not in exclude and df[c].dtype in ['float64', 'int64', 'float32', 'int32']]
feature_cols = [c for c in feature_cols if df[c].nunique() > 1 and not c.startswith('config_')]

X = df[feature_cols].fillna(0).values
y = df['target'].values

print(f"Features: {len(feature_cols)}")
print(f"Positifs: {(y==1).sum()} ({(y==1).sum()/len(y)*100:.1f}%)")

cw = compute_class_weight('balanced', classes=np.unique(y), y=y)

# Test configs anti-overfitting
configs = [
    {'k': 10, 'n_est': 100, 'depth': 2, 'lr': 0.02, 'leaf': 100, 'l2': 3.0},
    {'k': 12, 'n_est': 120, 'depth': 2, 'lr': 0.03, 'leaf': 80, 'l2': 2.5},
    {'k': 15, 'n_est': 150, 'depth': 2, 'lr': 0.03, 'leaf': 70, 'l2': 2.0},
    {'k': 10, 'n_est': 80, 'depth': 2, 'lr': 0.02, 'leaf': 120, 'l2': 4.0},
]

print("\n" + "-" * 60)
print(f"{'Config':<10} {'Acc':<8} {'F1':<8} {'Prec':<8} {'Gap':<8}")
print("-" * 60)

best = None
best_score = 0

for i, cfg in enumerate(configs):
    selector = SelectKBest(f_classif, k=cfg['k'])
    X_sel = selector.fit_transform(X, y)
    
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    train_accs, test_accs, f1s, precs = [], [], [], []
    
    for train_idx, test_idx in cv.split(X_sel, y):
        X_train, X_test = X_sel[train_idx], X_sel[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        sw = np.array([cw[0] if l==0 else cw[1] for l in y_train])
        
        scaler = RobustScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)
        
        model = HistGradientBoostingClassifier(
            max_iter=cfg['n_est'], max_depth=cfg['depth'],
            learning_rate=cfg['lr'], min_samples_leaf=cfg['leaf'],
            l2_regularization=cfg['l2'], random_state=42,
            early_stopping=True, validation_fraction=0.2
        )
        model.fit(X_train_s, y_train, sample_weight=sw)
        
        train_accs.append(accuracy_score(y_train, model.predict(X_train_s)))
        test_accs.append(accuracy_score(y_test, model.predict(X_test_s)))
        f1s.append(f1_score(y_test, model.predict(X_test_s), zero_division=0))
        precs.append(precision_score(y_test, model.predict(X_test_s), zero_division=0))
    
    acc = np.mean(test_accs)
    f1 = np.mean(f1s)
    prec = np.mean(precs)
    gap = np.mean(train_accs) - acc
    
    print(f"Config {i+1:<3} {acc*100:<8.1f} {f1:<8.3f} {prec:<8.3f} {gap*100:<8.1f}")
    
    # Score: F1 + Precision prioritaires, penaliser gap > 12%
    score = f1 + prec - max(0, gap - 0.12) * 2
    if score > best_score:
        best_score = score
        best = {'config': cfg, 'acc': acc, 'f1': f1, 'prec': prec, 'gap': gap}

print("-" * 60)
print(f"\nMEILLEURE CONFIG: k={best['config']['k']}, depth={best['config']['depth']}, lr={best['config']['lr']}")
print(f"  Accuracy:  {best['acc']*100:.1f}%")
print(f"  F1:        {best['f1']:.3f} {'✅' if best['f1'] >= 0.50 else '❌'}")
print(f"  Precision: {best['prec']:.3f} {'✅' if best['prec'] >= 0.55 else '❌'}")
print(f"  Gap:       {best['gap']*100:.1f}% {'✅' if best['gap'] <= 0.12 else '❌'}")

print("\nPour appliquer, mettre dans config_overrides.json:")
print(f"  gb_k_features: {best['config']['k']}")
print(f"  gb_n_estimators: {best['config']['n_est']}")
print(f"  gb_max_depth: {best['config']['depth']}")
print(f"  gb_learning_rate: {best['config']['lr']}")
print(f"  gb_min_samples_leaf: {best['config']['leaf']}")
print(f"  gb_l2_regularization: {best['config']['l2']}")
