"""
Verification des resultats GradientBoosting
Objectif: S'assurer que les metriques ne sont pas trompeuses
"""
import sys
sys.path.insert(0, '.')
import warnings
warnings.filterwarnings('ignore')

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold, train_test_split
from sklearn.metrics import accuracy_score, f1_score, precision_score, classification_report
from optimization.data.feature_loader import load_features_from_postgres
from optimization.data.feature_engineering import calculate_derived_features
import numpy as np
import pandas as pd

print("=" * 60)
print("  VERIFICATION RESULTATS GRADIENTBOOSTING")
print("=" * 60)

# 1. Charger donnees - UTILISER ml_features (pas ml_features_clean obsolète)
print("\n[1/4] Chargement des donnees...")
df = load_features_from_postgres(timeframe_days=730, min_trades=30, use_clean_data=False)
print(f"   Données brutes: {len(df)} trades")

# Appliquer même filtrage que l'UI
from config import TRADING_CONFIG
current_min_score = TRADING_CONFIG.get('min_score_required', 6.5)
if 'config_min_score_required' in df.columns:
    mask = (abs(df['config_min_score_required'] - current_min_score) < 0.1) | (df['config_min_score_required'].isna())
    df = df[mask]
    print(f"   Après filtre config (min_score={current_min_score}): {len(df)} trades")

df = calculate_derived_features(df)

# Preparer X, y
exclude = ['trade_id', 'timestamp', 'target_win', 'target_pnl', 'symbol', 'direction', 
           'entry_price', 'exit_price', 'pnl_pct', 'pnl_usdt']
feature_cols = [c for c in df.columns if c not in exclude and df[c].dtype in ['float64', 'int64', 'float32', 'int32']]
X = df[feature_cols].fillna(0)
y = df['target_win'].map({'t':1,'f':0,True:1,False:0,1:1,0:0})

print(f"   Dataset: {len(X)} samples, {len(feature_cols)} features")
print(f"   Distribution: WIN={y.sum()} ({y.mean():.1%}), LOSS={len(y)-y.sum()} ({1-y.mean():.1%})")

# 2. Cross-validation 5-fold
print("\n[2/4] Validation croisee 5-fold...")
model = HistGradientBoostingClassifier(
    max_iter=150,
    max_depth=5,
    learning_rate=0.08,
    min_samples_leaf=20,
    l2_regularization=0.1,
    random_state=42
)

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
scores = cross_val_score(model, X, y, cv=cv, scoring='accuracy')

print(f"   Scores par fold: {[f'{s:.1%}' for s in scores]}")
print(f"   Moyenne: {scores.mean():.1%} (+/- {scores.std()*2:.1%})")
print(f"   Min: {scores.min():.1%}, Max: {scores.max():.1%}")

# 3. Test sur donnees recentes (derniers 20%)
print("\n[3/4] Test sur donnees recentes (split temporel)...")
if 'timestamp' in df.columns:
    df_sorted = df.sort_values('timestamp')
    X_sorted = df_sorted[feature_cols].fillna(0)
    y_sorted = df_sorted['target_win'].map({'t':1,'f':0,True:1,False:0,1:1,0:0})
    
    # Derniers 20% comme test
    split_idx = int(len(X_sorted) * 0.8)
    X_train, X_test = X_sorted.iloc[:split_idx], X_sorted.iloc[split_idx:]
    y_train, y_test = y_sorted.iloc[:split_idx], y_sorted.iloc[split_idx:]
    
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    
    recent_acc = accuracy_score(y_test, y_pred)
    recent_f1 = f1_score(y_test, y_pred)
    recent_prec = precision_score(y_test, y_pred)
    train_acc = accuracy_score(y_train, model.predict(X_train))
    
    print(f"   Train (80% anciens): {train_acc:.1%}")
    print(f"   Test (20% recents): {recent_acc:.1%}")
    print(f"   Overfitting gap: {(train_acc - recent_acc)*100:.1f}%")
    print(f"   F1 recents: {recent_f1:.3f}")
    print(f"   Precision recents: {recent_prec:.3f}")
else:
    print("   [SKIP] Pas de colonne timestamp")
    recent_acc = scores.mean()

# 4. Analyse
print("\n[4/4] ANALYSE DES RESULTATS")
print("-" * 60)

# Verdict
issues = []
if scores.std() > 0.05:
    issues.append(f"Haute variance CV ({scores.std():.1%}) - resultats instables")
if scores.mean() < 0.55:
    issues.append(f"Accuracy moyenne faible ({scores.mean():.1%})")
if 'recent_acc' in dir() and recent_acc < scores.mean() - 0.05:
    issues.append(f"Performance degradee sur donnees recentes ({recent_acc:.1%} vs {scores.mean():.1%})")
if 'train_acc' in dir() and (train_acc - recent_acc) > 0.20:
    issues.append(f"Overfitting severe ({(train_acc - recent_acc)*100:.0f}% gap)")

if issues:
    print("PROBLEMES DETECTES:")
    for issue in issues:
        print(f"   - {issue}")
else:
    print("OK: Resultats semblent fiables")

print("\n" + "=" * 60)
print("RESUME")
print("=" * 60)
print(f"  CV Accuracy moyenne: {scores.mean():.1%}")
print(f"  CV Variance: {scores.std():.1%} ({'OK' if scores.std() < 0.05 else 'ATTENTION'})")
if 'recent_acc' in dir():
    print(f"  Accuracy donnees recentes: {recent_acc:.1%}")
    print(f"  Overfitting gap: {(train_acc - recent_acc)*100:.1f}%")

# Recommandation
print("\n" + "=" * 60)
print("RECOMMANDATION")
print("=" * 60)
if scores.mean() >= 0.60 and scores.std() < 0.05:
    print("  [OK] Modele utilisable en production")
    print("  Conseil: Surveiller les performances en live")
elif scores.mean() >= 0.55:
    print("  [ATTENTION] Modele a surveiller de pres")
    print("  Conseil: Reduire max_depth ou learning_rate pour moins d'overfitting")
else:
    print("  [WARNING] Modele peu fiable")
    print("  Conseil: Collecter plus de donnees ou simplifier le modele")
