# -*- coding: utf-8 -*-
"""
Test XGBoost V1 (Classification) et V2 (Regression) avec donnees nettoyees
"""

import sys
import warnings
warnings.filterwarnings('ignore')
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import RobustScaler
from sklearn.feature_selection import SelectKBest, f_classif, mutual_info_classif
from sklearn.metrics import accuracy_score, f1_score, precision_score, mean_absolute_error, r2_score
from xgboost import XGBClassifier, XGBRegressor
from pathlib import Path
from sqlalchemy import create_engine
from urllib.parse import quote_plus

print("=" * 70)
print("  TEST XGBOOST V1/V2 AVEC DONNEES NETTOYEES")
print("=" * 70)

# Connexion
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

# Charger donnees nettoyees
print("\n📊 Chargement des donnees nettoyees...")
try:
    df = pd.read_sql("SELECT * FROM ml_features_clean WHERE target_pnl IS NOT NULL", engine)
    print(f"✅ Donnees nettoyees: {len(df)} samples")
except Exception as e:
    print(f"⚠️ Table ml_features_clean non trouvee, utilisation ml_features")
    df = pd.read_sql("SELECT * FROM ml_features WHERE target_pnl IS NOT NULL", engine)
    print(f"✅ Donnees: {len(df)} samples")

engine.dispose()

# Preparer features
df['target_class'] = (df['target_pnl'] > 0).astype(int)
exclude = ['id', 'timestamp', 'symbol', 'target_pnl', 'target_class', 'scan_id', 
           'is_opportunity', 'target_win', 'reject_reason_category']
feature_cols = [c for c in df.columns if c not in exclude 
                and df[c].dtype in ['float64', 'int64', 'float32', 'int32']
                and df[c].nunique() > 1 
                and not c.startswith('config_')]

X = df[feature_cols].fillna(0).values
y_class = df['target_class'].values
y_pnl = df['target_pnl'].values

print(f"Features: {len(feature_cols)}")
print(f"Positifs: {(y_class==1).sum()} ({(y_class==1).sum()/len(y_class)*100:.1f}%)")

# ======================================
# XGBOOST V1 - CLASSIFICATION
# ======================================
print("\n" + "=" * 70)
print("  XGBOOST V1 - CLASSIFICATION (WIN/LOSS)")
print("=" * 70)

# Feature selection
k = min(25, len(feature_cols))
selector = SelectKBest(f_classif, k=k)
X_sel = selector.fit_transform(X, y_class)
print(f"Features selectionnees: {k}")

# Cross-validation
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
train_accs, test_accs, f1s, precs = [], [], [], []

for fold, (train_idx, test_idx) in enumerate(cv.split(X_sel, y_class)):
    X_train, X_test = X_sel[train_idx], X_sel[test_idx]
    y_train, y_test = y_class[train_idx], y_class[test_idx]
    
    scaler = RobustScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    
    # XGBoost avec regularisation forte
    model = XGBClassifier(
        n_estimators=150,
        max_depth=3,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=1.0,
        reg_lambda=2.0,
        min_child_weight=10,
        scale_pos_weight=(y_train==0).sum() / max(1, (y_train==1).sum()),
        random_state=42,
        verbosity=0
    )
    model.fit(X_train_s, y_train)
    
    y_train_pred = model.predict(X_train_s)
    y_test_pred = model.predict(X_test_s)
    
    train_accs.append(accuracy_score(y_train, y_train_pred))
    test_accs.append(accuracy_score(y_test, y_test_pred))
    f1s.append(f1_score(y_test, y_test_pred, zero_division=0))
    precs.append(precision_score(y_test, y_test_pred, zero_division=0))

v1_acc = np.mean(test_accs)
v1_f1 = np.mean(f1s)
v1_prec = np.mean(precs)
v1_gap = np.mean(train_accs) - v1_acc

print(f"\n📊 Resultats XGBoost V1:")
print(f"  Accuracy:  {v1_acc*100:.1f}% {'✅' if v1_acc >= 0.55 else '❌'}")
print(f"  F1 Score:  {v1_f1:.3f} {'✅' if v1_f1 >= 0.50 else '❌'}")
print(f"  Precision: {v1_prec:.3f} {'✅' if v1_prec >= 0.55 else '❌'}")
print(f"  Gap:       {v1_gap*100:.1f}% {'✅' if v1_gap <= 0.12 else '⚠️'}")

# ======================================
# XGBOOST V2 - REGRESSION (PNL%)
# ======================================
print("\n" + "=" * 70)
print("  XGBOOST V2 - REGRESSION (PNL%)")
print("=" * 70)

# Winsorize target pour reduire outliers
pnl_lower = np.percentile(y_pnl, 1)
pnl_upper = np.percentile(y_pnl, 99)
y_pnl_clip = np.clip(y_pnl, pnl_lower, pnl_upper)
print(f"Target PNL% winsorized: [{pnl_lower:.2f}%, {pnl_upper:.2f}%]")

# Train/test split
X_train, X_test, y_train, y_test = train_test_split(
    X_sel, y_pnl_clip, test_size=0.2, random_state=42
)

scaler = RobustScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s = scaler.transform(X_test)

# XGBoost Regressor avec forte regularisation
model_reg = XGBRegressor(
    n_estimators=100,
    max_depth=2,
    learning_rate=0.02,
    subsample=0.7,
    colsample_bytree=0.7,
    reg_alpha=5.0,
    reg_lambda=8.0,
    min_child_weight=20,
    gamma=2.0,
    random_state=42,
    verbosity=0
)
model_reg.fit(X_train_s, y_train)

y_train_pred = model_reg.predict(X_train_s)
y_test_pred = model_reg.predict(X_test_s)

train_mae = mean_absolute_error(y_train, y_train_pred)
test_mae = mean_absolute_error(y_test, y_test_pred)
train_r2 = r2_score(y_train, y_train_pred)
test_r2 = r2_score(y_test, y_test_pred)

print(f"\n📊 Resultats XGBoost V2:")
print(f"  Train MAE: {train_mae:.3f}%")
print(f"  Test MAE:  {test_mae:.3f}%")
print(f"  Train R2:  {train_r2:.3f}")
print(f"  Test R2:   {test_r2:.3f} {'✅' if test_r2 > 0 else '❌ (negatif = pire que moyenne)'}")

# Classification depuis regression
y_test_class_pred = (y_test_pred > 0).astype(int)
y_test_class_true = (y_test > 0).astype(int)
v2_acc = accuracy_score(y_test_class_true, y_test_class_pred)
v2_f1 = f1_score(y_test_class_true, y_test_class_pred, zero_division=0)
v2_prec = precision_score(y_test_class_true, y_test_class_pred, zero_division=0)

print(f"\n  Classification (PNL > 0):")
print(f"  Accuracy:  {v2_acc*100:.1f}%")
print(f"  F1 Score:  {v2_f1:.3f}")
print(f"  Precision: {v2_prec:.3f}")

# ======================================
# RESUME COMPARATIF
# ======================================
print("\n" + "=" * 70)
print("  RESUME COMPARATIF")
print("=" * 70)
print(f"""
                    XGBoost V1          XGBoost V2          GradientBoosting
                    (Classification)    (Regression)        (Actuel)
  -------------------------------------------------------------------------
  Accuracy:         {v1_acc*100:.1f}%              {v2_acc*100:.1f}%              54.5%
  F1 Score:         {v1_f1:.3f}              {v2_f1:.3f}              0.582
  Precision:        {v1_prec:.3f}              {v2_prec:.3f}              0.640
  Gap/R2:           {v1_gap*100:.1f}%              R2={test_r2:.3f}            15.6%
  
  Recommandation:   {'✅ Bon' if v1_f1 >= 0.5 else '❌ Moyen'}              {'✅ Bon' if test_r2 > 0 else '❌ R2 negatif'}          ✅ Meilleur
""")

print("=" * 70)
