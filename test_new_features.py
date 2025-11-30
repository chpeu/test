# -*- coding: utf-8 -*-
"""Test rapide des nouvelles features"""

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
print("  TEST NOUVELLES FEATURES")
print("=" * 60)

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

print(f"Donnees: {len(df)} samples")

# Create new features
print("\nCreation des nouvelles features...")

# 1. BB Position (TOP 1!)
if 'bb_distance_to_lower_1m' in df.columns and 'bb_distance_to_upper_1m' in df.columns:
    df['bb_position'] = df['bb_distance_to_lower_1m'] / (df['bb_distance_to_lower_1m'] + df['bb_distance_to_upper_1m'] + 1e-6)

# 2. Momentum combined
if 'macd_hist_1m' in df.columns and 'rsi_1m' in df.columns:
    df['momentum_combined'] = (df['macd_hist_1m'] / (abs(df['macd_hist_1m']).max() + 1e-6)) * ((df['rsi_1m'] - 50) / 50)

# 3. MACD acceleration
if 'macd_hist_1m' in df.columns and 'macd_hist_prev_1m' in df.columns:
    df['macd_acceleration'] = df['macd_hist_1m'] - df['macd_hist_prev_1m']

# 4. RSI distance to 50
if 'rsi_1m' in df.columns:
    df['rsi_distance_50_1m'] = abs(df['rsi_1m'] - 50)
if 'rsi_5m' in df.columns:
    df['rsi_distance_50_5m'] = abs(df['rsi_5m'] - 50)

# 5. Volatility ratio
if 'atr_pct_1m' in df.columns and 'atr_pct_5m' in df.columns:
    df['volatility_ratio'] = df['atr_pct_1m'] / (df['atr_pct_5m'] + 1e-6)

# 6. Trend strength
if 'adx_1m' in df.columns and 'di_gap_1m' in df.columns:
    df['trend_strength'] = df['adx_1m'] * abs(df['di_gap_1m'])

# 7. Volume pressure
if 'volume_ratio_1m' in df.columns and 'volume_spike_1m' in df.columns:
    df['volume_pressure'] = df['volume_ratio_1m'] * df['volume_spike_1m']

# 8. BB squeeze
if 'bb_width_1m' in df.columns:
    df['bb_squeeze'] = 1 / (df['bb_width_1m'] + 1e-6)

# 9. RSI accel
if 'rsi_1m' in df.columns and 'rsi_prev_1m' in df.columns:
    df['rsi_accel'] = df['rsi_1m'] - df['rsi_prev_1m']

# 10. EMA trend aligned
if 'ema_diff_pct_1m' in df.columns and 'ema_diff_pct_5m' in df.columns:
    df['ema_trend_aligned'] = np.sign(df['ema_diff_pct_1m']) * np.sign(df['ema_diff_pct_5m'])

# Target
df['target'] = (df['target_pnl'] > 0).astype(int)

# Features
exclude = ['id', 'timestamp', 'symbol', 'target_pnl', 'target', 'scan_id']
feature_cols = [c for c in df.columns if c not in exclude and df[c].dtype in ['float64', 'int64', 'float32', 'int32']]

X = df[feature_cols].fillna(0).values
y = df['target'].values

print(f"Features totales: {len(feature_cols)}")
print(f"Distribution: {(y==1).sum()} positifs ({(y==1).sum()/len(y)*100:.1f}%)")

# Evaluate
cw = compute_class_weight('balanced', classes=np.unique(y), y=y)

def evaluate(X, y, k, name):
    selector = SelectKBest(f_classif, k=min(k, X.shape[1]))
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
            max_iter=300, max_depth=2, learning_rate=0.089,
            min_samples_leaf=50, l2_regularization=0.9,
            random_state=42, early_stopping=True
        )
        model.fit(X_train_s, y_train, sample_weight=sw)
        
        train_accs.append(accuracy_score(y_train, model.predict(X_train_s)))
        test_accs.append(accuracy_score(y_test, model.predict(X_test_s)))
        f1s.append(f1_score(y_test, model.predict(X_test_s), zero_division=0))
        precs.append(precision_score(y_test, model.predict(X_test_s), zero_division=0))
    
    print(f"\n{name} (k={k}):")
    print(f"  Accuracy: {np.mean(test_accs)*100:.1f}%")
    print(f"  F1 Score: {np.mean(f1s):.3f}")
    print(f"  Precision: {np.mean(precs):.3f}")
    print(f"  Gap: {(np.mean(train_accs) - np.mean(test_accs))*100:.1f}%")
    
    return np.mean(f1s), np.mean(precs), np.mean(train_accs) - np.mean(test_accs)

# Test different k values
print("\n" + "=" * 60)
results = []
for k in [20, 25, 30]:
    f1, prec, gap = evaluate(X, y, k, f"Test k={k}")
    results.append((k, f1, prec, gap))

# Best
best = max(results, key=lambda x: x[1] + x[2] - x[3]*0.5)
print("\n" + "=" * 60)
print(f"MEILLEUR: k={best[0]} avec F1={best[1]:.3f}, Precision={best[2]:.3f}, Gap={best[3]*100:.1f}%")
print("=" * 60)

# Objectifs
print("\nVS OBJECTIFS:")
print(f"  F1: {best[1]:.3f} {'✅' if best[1] >= 0.50 else '❌'} (objectif: 0.50)")
print(f"  Precision: {best[2]:.3f} {'✅' if best[2] >= 0.55 else '❌'} (objectif: 0.55)")
print(f"  Gap: {best[3]*100:.1f}% {'✅' if best[3] <= 0.12 else '❌'} (objectif: <=12%)")
