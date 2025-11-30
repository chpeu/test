# -*- coding: utf-8 -*-
"""
DERNIERE TENTATIVE - Push maximum pour atteindre les objectifs
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
from sklearn.feature_selection import SelectKBest, f_classif, mutual_info_classif
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier, VotingClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.utils.class_weight import compute_class_weight
from pathlib import Path
from sqlalchemy import create_engine
from urllib.parse import quote_plus
import optuna
from optuna.samplers import TPESampler

print("=" * 70)
print("  FINAL PUSH - OBJECTIF: 62% ACC, 0.50 F1, 0.55 PREC")
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

print(f"Donnees brutes: {len(df)} samples")

# =============================================================================
# FEATURE ENGINEERING AVANCE
# =============================================================================
print("\n=== FEATURE ENGINEERING AVANCE ===")

# Features de base
if 'bb_distance_to_lower_1m' in df.columns and 'bb_distance_to_upper_1m' in df.columns:
    df['bb_position'] = df['bb_distance_to_lower_1m'] / (df['bb_distance_to_lower_1m'] + df['bb_distance_to_upper_1m'] + 1e-6)

# PATTERN FEATURES
# 1. RSI divergence pattern
if 'rsi_1m' in df.columns and 'rsi_prev_1m' in df.columns:
    df['rsi_rising'] = (df['rsi_1m'] > df['rsi_prev_1m']).astype(int)
    df['rsi_momentum'] = df['rsi_1m'] - df['rsi_prev_1m']

# 2. MACD crossover signal
if 'macd_hist_1m' in df.columns and 'macd_hist_prev_1m' in df.columns:
    df['macd_cross_up'] = ((df['macd_hist_1m'] > 0) & (df['macd_hist_prev_1m'] <= 0)).astype(int)
    df['macd_cross_down'] = ((df['macd_hist_1m'] < 0) & (df['macd_hist_prev_1m'] >= 0)).astype(int)
    df['macd_accel'] = df['macd_hist_1m'] - df['macd_hist_prev_1m']

# 3. Volume confirmation
if 'volume_ratio_1m' in df.columns:
    df['volume_confirm'] = (df['volume_ratio_1m'] > 1.2).astype(int)

# 4. Trend strength
if 'adx_1m' in df.columns:
    df['trend_strong'] = (df['adx_1m'] > 25).astype(int)
    df['trend_weak'] = (df['adx_1m'] < 15).astype(int)

# 5. BB squeeze breakout
if 'bb_width_1m' in df.columns:
    bb_mean = df['bb_width_1m'].mean()
    df['bb_squeeze'] = (df['bb_width_1m'] < bb_mean * 0.8).astype(int)

# 6. Multi-timeframe alignment
if 'rsi_1m' in df.columns and 'rsi_5m' in df.columns:
    df['rsi_aligned_bull'] = ((df['rsi_1m'] > 50) & (df['rsi_5m'] > 50)).astype(int)
    df['rsi_aligned_bear'] = ((df['rsi_1m'] < 50) & (df['rsi_5m'] < 50)).astype(int)

# 7. Quality score composite
df['quality'] = 0
if 'trend_strong' in df.columns:
    df['quality'] += df['trend_strong']
if 'volume_confirm' in df.columns:
    df['quality'] += df['volume_confirm']
if 'rsi_aligned_bull' in df.columns:
    df['quality'] += df['rsi_aligned_bull']

# 8. Risk score
if 'atr_pct_1m' in df.columns:
    atr_75 = df['atr_pct_1m'].quantile(0.75)
    df['high_risk'] = (df['atr_pct_1m'] > atr_75).astype(int)

# Target
df['target'] = (df['target_pnl'] > 0).astype(int)

# Features
exclude = ['id', 'timestamp', 'symbol', 'target_pnl', 'target', 'scan_id']
feature_cols = [c for c in df.columns if c not in exclude and df[c].dtype in ['float64', 'int64', 'float32', 'int32']]

# Supprimer features constantes
feature_cols = [c for c in feature_cols if df[c].nunique() > 1]

X = df[feature_cols].fillna(0).values
y = df['target'].values

print(f"Features: {len(feature_cols)}")
print(f"Positifs: {(y==1).sum()} ({(y==1).sum()/len(y)*100:.1f}%)")

cw = compute_class_weight('balanced', classes=np.unique(y), y=y)

# =============================================================================
# STRATEGIE 1: Optuna avec focus sur ACCURACY
# =============================================================================
print("\n=== STRATEGIE 1: FOCUS ACCURACY (100 trials) ===")

def objective_accuracy(trial):
    n_est = trial.suggest_int('n_estimators', 100, 300, step=50)
    max_d = trial.suggest_int('max_depth', 2, 4)
    lr = trial.suggest_float('learning_rate', 0.02, 0.1)
    min_leaf = trial.suggest_int('min_samples_leaf', 30, 70, step=10)
    l2 = trial.suggest_float('l2_regularization', 0.5, 2.0)
    k = trial.suggest_int('k_features', 15, 30, step=5)
    
    selector = SelectKBest(f_classif, k=k)
    X_sel = selector.fit_transform(X, y)
    
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    accs, gaps = [], []
    
    for train_idx, test_idx in cv.split(X_sel, y):
        X_train, X_test = X_sel[train_idx], X_sel[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        sw = np.array([cw[0] if l==0 else cw[1] for l in y_train])
        
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
        
        accs.append(test_acc)
        gaps.append(train_acc - test_acc)
    
    acc = np.mean(accs)
    gap = np.mean(gaps)
    
    if gap > 0.15:
        return 0.0
    
    return acc - gap * 0.3  # Accuracy prioritaire

sampler = TPESampler(seed=42)
study1 = optuna.create_study(direction='maximize', sampler=sampler)
study1.optimize(objective_accuracy, n_trials=100, show_progress_bar=False)

best1 = study1.best_params
print(f"Meilleurs params: {best1}")

# Evaluer
selector = SelectKBest(f_classif, k=best1['k_features'])
X_sel = selector.fit_transform(X, y)

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
m1 = {'acc': [], 'f1': [], 'prec': [], 'gap': []}

for train_idx, test_idx in cv.split(X_sel, y):
    X_train, X_test = X_sel[train_idx], X_sel[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]
    sw = np.array([cw[0] if l==0 else cw[1] for l in y_train])
    
    scaler = RobustScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    
    model = HistGradientBoostingClassifier(
        max_iter=best1['n_estimators'], max_depth=best1['max_depth'],
        learning_rate=best1['learning_rate'], min_samples_leaf=best1['min_samples_leaf'],
        l2_regularization=best1['l2_regularization'], random_state=42, early_stopping=True
    )
    model.fit(X_train_s, y_train, sample_weight=sw)
    
    train_pred = model.predict(X_train_s)
    test_pred = model.predict(X_test_s)
    
    m1['acc'].append(accuracy_score(y_test, test_pred))
    m1['f1'].append(f1_score(y_test, test_pred, zero_division=0))
    m1['prec'].append(precision_score(y_test, test_pred, zero_division=0))
    m1['gap'].append(accuracy_score(y_train, train_pred) - accuracy_score(y_test, test_pred))

print(f"Resultats: Acc={np.mean(m1['acc'])*100:.1f}%, F1={np.mean(m1['f1']):.3f}, Prec={np.mean(m1['prec']):.3f}, Gap={np.mean(m1['gap'])*100:.1f}%")

# =============================================================================
# STRATEGIE 2: Ensemble Voting optimise
# =============================================================================
print("\n=== STRATEGIE 2: ENSEMBLE VOTING ===")

selector = SelectKBest(f_classif, k=25)
X_sel = selector.fit_transform(X, y)

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
m2 = {'acc': [], 'f1': [], 'prec': [], 'gap': []}

for train_idx, test_idx in cv.split(X_sel, y):
    X_train, X_test = X_sel[train_idx], X_sel[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]
    
    scaler = RobustScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    
    # Ensemble de 3 modeles
    hgb1 = HistGradientBoostingClassifier(max_iter=150, max_depth=2, learning_rate=0.05, min_samples_leaf=50, random_state=42)
    hgb2 = HistGradientBoostingClassifier(max_iter=200, max_depth=3, learning_rate=0.03, min_samples_leaf=40, random_state=43)
    rf = RandomForestClassifier(n_estimators=100, max_depth=5, min_samples_leaf=30, class_weight='balanced', random_state=44)
    
    voting = VotingClassifier(estimators=[('hgb1', hgb1), ('hgb2', hgb2), ('rf', rf)], voting='soft')
    voting.fit(X_train_s, y_train)
    
    train_pred = voting.predict(X_train_s)
    test_pred = voting.predict(X_test_s)
    
    m2['acc'].append(accuracy_score(y_test, test_pred))
    m2['f1'].append(f1_score(y_test, test_pred, zero_division=0))
    m2['prec'].append(precision_score(y_test, test_pred, zero_division=0))
    m2['gap'].append(accuracy_score(y_train, train_pred) - accuracy_score(y_test, test_pred))

print(f"Resultats: Acc={np.mean(m2['acc'])*100:.1f}%, F1={np.mean(m2['f1']):.3f}, Prec={np.mean(m2['prec']):.3f}, Gap={np.mean(m2['gap'])*100:.1f}%")

# =============================================================================
# STRATEGIE 3: Mutual Information features
# =============================================================================
print("\n=== STRATEGIE 3: MUTUAL INFORMATION FEATURES ===")

selector_mi = SelectKBest(mutual_info_classif, k=25)
X_sel_mi = selector_mi.fit_transform(X, y)

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
m3 = {'acc': [], 'f1': [], 'prec': [], 'gap': []}

for train_idx, test_idx in cv.split(X_sel_mi, y):
    X_train, X_test = X_sel_mi[train_idx], X_sel_mi[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]
    sw = np.array([cw[0] if l==0 else cw[1] for l in y_train])
    
    scaler = RobustScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    
    model = HistGradientBoostingClassifier(
        max_iter=200, max_depth=2, learning_rate=0.05,
        min_samples_leaf=50, l2_regularization=1.0,
        random_state=42, early_stopping=True
    )
    model.fit(X_train_s, y_train, sample_weight=sw)
    
    train_pred = model.predict(X_train_s)
    test_pred = model.predict(X_test_s)
    
    m3['acc'].append(accuracy_score(y_test, test_pred))
    m3['f1'].append(f1_score(y_test, test_pred, zero_division=0))
    m3['prec'].append(precision_score(y_test, test_pred, zero_division=0))
    m3['gap'].append(accuracy_score(y_train, train_pred) - accuracy_score(y_test, test_pred))

print(f"Resultats: Acc={np.mean(m3['acc'])*100:.1f}%, F1={np.mean(m3['f1']):.3f}, Prec={np.mean(m3['prec']):.3f}, Gap={np.mean(m3['gap'])*100:.1f}%")

# =============================================================================
# RESUME FINAL
# =============================================================================
print("\n" + "=" * 70)
print("  RESUME FINAL - TOUTES STRATEGIES")
print("=" * 70)

results = [
    ("Focus Accuracy", np.mean(m1['acc']), np.mean(m1['f1']), np.mean(m1['prec']), np.mean(m1['gap'])),
    ("Ensemble Voting", np.mean(m2['acc']), np.mean(m2['f1']), np.mean(m2['prec']), np.mean(m2['gap'])),
    ("Mutual Info", np.mean(m3['acc']), np.mean(m3['f1']), np.mean(m3['prec']), np.mean(m3['gap'])),
]

print(f"\n{'Strategie':<20} {'Acc':<10} {'F1':<10} {'Prec':<10} {'Gap':<10}")
print("-" * 60)
for name, acc, f1, prec, gap in results:
    print(f"{name:<20} {acc*100:<10.1f}% {f1:<10.3f} {prec:<10.3f} {gap*100:<10.1f}%")

# Trouver le meilleur
best_strat = max(results, key=lambda x: 0.35*x[1] + 0.30*x[2] + 0.25*x[3] - 0.10*x[4])
print(f"\nMeilleure strategie: {best_strat[0]}")
print(f"  Accuracy:  {best_strat[1]*100:.1f}% {'✅' if best_strat[1]>=0.62 else '❌'}")
print(f"  F1:        {best_strat[2]:.3f} {'✅' if best_strat[2]>=0.50 else '❌'}")
print(f"  Precision: {best_strat[3]:.3f} {'✅' if best_strat[3]>=0.55 else '❌'}")
print(f"  Gap:       {best_strat[4]*100:.1f}% {'✅' if best_strat[4]<=0.12 else '❌'}")

objectives = [
    best_strat[1] >= 0.62,
    best_strat[2] >= 0.50,
    best_strat[3] >= 0.55,
    best_strat[4] <= 0.12
]
print(f"\n  OBJECTIFS ATTEINTS: {sum(objectives)}/4")
print("=" * 70)

# Sauvegarder les meilleurs parametres
if best_strat[0] == "Focus Accuracy":
    print("\n  Parametres a utiliser:")
    for k, v in best1.items():
        print(f"    {k}: {v}")
