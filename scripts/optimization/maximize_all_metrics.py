# -*- coding: utf-8 -*-
"""
Maximiser TOUTES les metriques: Accuracy, F1, Precision
Explorer: Ensemble, Stacking, Features avancees, Calibration
"""

import sys
import warnings
warnings.filterwarnings('ignore')
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.preprocessing import RobustScaler, StandardScaler
from sklearn.feature_selection import SelectKBest, f_classif, mutual_info_classif
from sklearn.ensemble import (
    HistGradientBoostingClassifier, 
    RandomForestClassifier,
    GradientBoostingClassifier,
    AdaBoostClassifier,
    VotingClassifier,
    StackingClassifier
)
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.utils.class_weight import compute_class_weight
from pathlib import Path
from sqlalchemy import create_engine
from urllib.parse import quote_plus
import optuna
from optuna.samplers import TPESampler

print("=" * 70)
print("  MAXIMISER TOUTES LES METRIQUES")
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

print(f"Donnees: {len(df)} samples")

# =============================================================================
# CREATION DE TOUTES LES FEATURES AVANCEES
# =============================================================================
print("\n=== CREATION FEATURES AVANCEES ===")

# Features de base deja creees
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

# NOUVELLES FEATURES POUR ACCURACY
# 1. RSI zones (oversold/overbought)
if 'rsi_1m' in df.columns:
    df['rsi_oversold'] = (df['rsi_1m'] < 30).astype(int)
    df['rsi_overbought'] = (df['rsi_1m'] > 70).astype(int)
    df['rsi_neutral'] = ((df['rsi_1m'] >= 40) & (df['rsi_1m'] <= 60)).astype(int)

# 2. MACD signal
if 'macd_hist_1m' in df.columns:
    df['macd_positive'] = (df['macd_hist_1m'] > 0).astype(int)
    df['macd_strong'] = (abs(df['macd_hist_1m']) > df['macd_hist_1m'].std()).astype(int)

# 3. Trend direction
if 'di_plus_1m' in df.columns and 'di_minus_1m' in df.columns:
    df['di_bullish'] = (df['di_plus_1m'] > df['di_minus_1m']).astype(int)
    df['di_strong_bull'] = ((df['di_plus_1m'] > df['di_minus_1m']) & (df['di_gap_1m'] > 10)).astype(int) if 'di_gap_1m' in df.columns else 0

# 4. Volume confirmation
if 'volume_ratio_1m' in df.columns:
    df['volume_high'] = (df['volume_ratio_1m'] > 1.5).astype(int)
    df['volume_very_high'] = (df['volume_ratio_1m'] > 2.0).astype(int)

# 5. BB position categories
if 'bb_position' in df.columns:
    df['bb_near_lower'] = (df['bb_position'] < 0.3).astype(int)
    df['bb_near_upper'] = (df['bb_position'] > 0.7).astype(int)
    df['bb_middle'] = ((df['bb_position'] >= 0.3) & (df['bb_position'] <= 0.7)).astype(int)

# 6. Multi-timeframe confluence
if 'rsi_1m' in df.columns and 'rsi_5m' in df.columns:
    df['rsi_mtf_bullish'] = ((df['rsi_1m'] > 50) & (df['rsi_5m'] > 50)).astype(int)
    df['rsi_mtf_bearish'] = ((df['rsi_1m'] < 50) & (df['rsi_5m'] < 50)).astype(int)

# 7. Momentum alignment
if 'macd_hist_1m' in df.columns and 'macd_hist_5m' in df.columns:
    df['macd_mtf_aligned'] = (np.sign(df['macd_hist_1m']) == np.sign(df['macd_hist_5m'])).astype(int)

# 8. Strong setup score
df['strong_setup'] = 0
if 'di_bullish' in df.columns:
    df['strong_setup'] += df['di_bullish']
if 'macd_positive' in df.columns:
    df['strong_setup'] += df['macd_positive']
if 'volume_high' in df.columns:
    df['strong_setup'] += df['volume_high']
if 'rsi_mtf_bullish' in df.columns:
    df['strong_setup'] += df['rsi_mtf_bullish']

# 9. Risk indicators
if 'atr_pct_1m' in df.columns:
    df['high_volatility'] = (df['atr_pct_1m'] > df['atr_pct_1m'].quantile(0.75)).astype(int)
    df['low_volatility'] = (df['atr_pct_1m'] < df['atr_pct_1m'].quantile(0.25)).astype(int)

# 10. Interaction features
if 'rsi_1m' in df.columns and 'adx_1m' in df.columns:
    df['rsi_adx_product'] = df['rsi_1m'] * df['adx_1m'] / 100

print(f"Features totales creees: {len([c for c in df.columns if df[c].dtype in ['float64', 'int64', 'float32', 'int32']])}")

# Target
df['target'] = (df['target_pnl'] > 0).astype(int)

# Features
exclude = ['id', 'timestamp', 'symbol', 'target_pnl', 'target', 'scan_id']
feature_cols = [c for c in df.columns if c not in exclude and df[c].dtype in ['float64', 'int64', 'float32', 'int32']]

X = df[feature_cols].fillna(0).values
y = df['target'].values

print(f"Features utilisables: {len(feature_cols)}")
print(f"Distribution: {(y==1).sum()} positifs ({(y==1).sum()/len(y)*100:.1f}%)")

# Class weights
cw = compute_class_weight('balanced', classes=np.unique(y), y=y)

# =============================================================================
# TEST 1: OPTIMISATION POUR ACCURACY + F1 + PRECISION
# =============================================================================
print("\n=== OPTIMISATION MULTI-OBJECTIF ===")

def evaluate_model(model, X, y, name, k=30):
    """Evaluate avec CV"""
    selector = SelectKBest(f_classif, k=min(k, X.shape[1]))
    X_sel = selector.fit_transform(X, y)
    
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    metrics = {'acc': [], 'f1': [], 'prec': [], 'gap': []}
    
    for train_idx, test_idx in cv.split(X_sel, y):
        X_train, X_test = X_sel[train_idx], X_sel[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        sw = np.array([cw[0] if l==0 else cw[1] for l in y_train])
        
        scaler = RobustScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)
        
        try:
            model.fit(X_train_s, y_train, sample_weight=sw)
        except TypeError:
            model.fit(X_train_s, y_train)
        
        y_train_pred = model.predict(X_train_s)
        y_test_pred = model.predict(X_test_s)
        
        metrics['acc'].append(accuracy_score(y_test, y_test_pred))
        metrics['f1'].append(f1_score(y_test, y_test_pred, zero_division=0))
        metrics['prec'].append(precision_score(y_test, y_test_pred, zero_division=0))
        metrics['gap'].append(accuracy_score(y_train, y_train_pred) - accuracy_score(y_test, y_test_pred))
    
    result = {
        'name': name,
        'acc': np.mean(metrics['acc']),
        'f1': np.mean(metrics['f1']),
        'prec': np.mean(metrics['prec']),
        'gap': np.mean(metrics['gap'])
    }
    return result

# Test different k values
print("\n--- Test nombre de features ---")
for k in [25, 30, 35, 40]:
    model = HistGradientBoostingClassifier(max_iter=250, max_depth=4, learning_rate=0.098, min_samples_leaf=40, random_state=42)
    r = evaluate_model(model, X, y, f"k={k}", k=k)
    print(f"k={k}: Acc={r['acc']*100:.1f}%, F1={r['f1']:.3f}, Prec={r['prec']:.3f}, Gap={r['gap']*100:.1f}%")

# =============================================================================
# TEST 2: ENSEMBLE METHODS
# =============================================================================
print("\n=== TEST ENSEMBLE METHODS ===")

# Preparer donnees avec k=30
selector = SelectKBest(f_classif, k=30)
X_sel = selector.fit_transform(X, y)

# 1. Voting Classifier
print("\n--- Voting Classifier ---")
hgb1 = HistGradientBoostingClassifier(max_iter=200, max_depth=3, learning_rate=0.05, random_state=42)
hgb2 = HistGradientBoostingClassifier(max_iter=250, max_depth=4, learning_rate=0.098, random_state=43)
rf = RandomForestClassifier(n_estimators=150, max_depth=6, class_weight='balanced', random_state=42)

voting = VotingClassifier(estimators=[('hgb1', hgb1), ('hgb2', hgb2), ('rf', rf)], voting='soft')
r = evaluate_model(voting, X, y, "Voting", k=30)
print(f"Voting: Acc={r['acc']*100:.1f}%, F1={r['f1']:.3f}, Prec={r['prec']:.3f}, Gap={r['gap']*100:.1f}%")

# 2. Stacking Classifier
print("\n--- Stacking Classifier ---")
estimators = [
    ('hgb', HistGradientBoostingClassifier(max_iter=150, max_depth=3, random_state=42)),
    ('rf', RandomForestClassifier(n_estimators=100, max_depth=5, class_weight='balanced', random_state=42))
]
stacking = StackingClassifier(estimators=estimators, final_estimator=LogisticRegression(class_weight='balanced'), cv=3)
r = evaluate_model(stacking, X, y, "Stacking", k=30)
print(f"Stacking: Acc={r['acc']*100:.1f}%, F1={r['f1']:.3f}, Prec={r['prec']:.3f}, Gap={r['gap']*100:.1f}%")

# =============================================================================
# TEST 3: OPTUNA MULTI-OBJECTIF
# =============================================================================
print("\n=== OPTUNA MULTI-OBJECTIF (100 trials) ===")

def objective_all(trial):
    """Optimiser accuracy + F1 + precision"""
    n_estimators = trial.suggest_int('n_estimators', 150, 350, step=50)
    max_depth = trial.suggest_int('max_depth', 2, 5)
    learning_rate = trial.suggest_float('learning_rate', 0.03, 0.15, log=True)
    min_samples_leaf = trial.suggest_int('min_samples_leaf', 25, 60, step=5)
    l2_reg = trial.suggest_float('l2_regularization', 0.2, 1.2)
    k_features = trial.suggest_int('k_features', 25, 40, step=5)
    
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
            random_state=42, early_stopping=True
        )
        model.fit(X_train_s, y_train, sample_weight=sw)
        
        y_train_pred = model.predict(X_train_s)
        y_test_pred = model.predict(X_test_s)
        
        train_acc = accuracy_score(y_train, y_train_pred)
        test_acc = accuracy_score(y_test, y_test_pred)
        
        accs.append(test_acc)
        f1s.append(f1_score(y_test, y_test_pred, zero_division=0))
        precs.append(precision_score(y_test, y_test_pred, zero_division=0))
        gaps.append(train_acc - test_acc)
    
    acc = np.mean(accs)
    f1 = np.mean(f1s)
    prec = np.mean(precs)
    gap = np.mean(gaps)
    
    # Score composite: 35% acc + 35% f1 + 20% prec + 10% (1-gap)
    score = 0.35 * acc + 0.35 * f1 + 0.20 * prec + 0.10 * (1 - gap)
    
    return score

sampler = TPESampler(seed=42)
study = optuna.create_study(direction='maximize', sampler=sampler)
study.optimize(objective_all, n_trials=100, show_progress_bar=False)

best_params = study.best_params
print(f"\nMeilleurs parametres: {best_params}")

# Evaluer avec les meilleurs parametres
print("\n=== EVALUATION FINALE ===")

selector = SelectKBest(f_classif, k=best_params.get('k_features', 30))
X_sel = selector.fit_transform(X, y)

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
        max_iter=best_params.get('n_estimators', 250),
        max_depth=best_params.get('max_depth', 4),
        learning_rate=best_params.get('learning_rate', 0.098),
        min_samples_leaf=best_params.get('min_samples_leaf', 40),
        l2_regularization=best_params.get('l2_regularization', 0.6),
        random_state=42, early_stopping=True
    )
    model.fit(X_train_s, y_train, sample_weight=sw)
    
    y_train_pred = model.predict(X_train_s)
    y_test_pred = model.predict(X_test_s)
    
    metrics['acc'].append(accuracy_score(y_test, y_test_pred))
    metrics['f1'].append(f1_score(y_test, y_test_pred, zero_division=0))
    metrics['prec'].append(precision_score(y_test, y_test_pred, zero_division=0))
    metrics['gap'].append(accuracy_score(y_train, y_train_pred) - accuracy_score(y_test, y_test_pred))

print("\n" + "=" * 70)
print("  RESULTATS FINAUX OPTIMISES")
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

print(f"    Accuracy >= 62%:   {'✅' if acc_ok else '❌'}")
print(f"    F1 >= 0.50:        {'✅' if f1_ok else '❌'}")
print(f"    Precision >= 0.55: {'✅' if prec_ok else '❌'}")
print(f"    Gap <= 12%:        {'✅' if gap_ok else '❌'}")

print(f"\n  Score total: {sum([acc_ok, f1_ok, prec_ok, gap_ok])}/4")
print("=" * 70)

# Sauvegarder les meilleurs parametres
print("\n  Meilleurs parametres a utiliser:")
for k, v in best_params.items():
    print(f"    {k}: {v}")
