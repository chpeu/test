# -*- coding: utf-8 -*-
"""
Exploration avancee pour ameliorer les metriques ML
Teste: SMOTE, Ensemble, Threshold tuning, etc.
"""

import sys
import os
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
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.utils.class_weight import compute_class_weight
from pathlib import Path
from sqlalchemy import create_engine
from urllib.parse import quote_plus
from imblearn.over_sampling import SMOTE
from imblearn.combine import SMOTETomek

print("=" * 70)
print("  EXPLORATION AVANCEE ML")
print("=" * 70)

def load_data():
    """Charge les donnees"""
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
    
    df = pd.read_sql("SELECT * FROM ml_features WHERE target_pnl IS NOT NULL LIMIT 5000", engine)
    engine.dispose()
    
    # Target binaire
    df['target'] = (df['target_pnl'] > 0).astype(int)
    
    # Features numeriques
    exclude = ['id', 'timestamp', 'symbol', 'target_pnl', 'target', 'scan_id']
    feature_cols = [c for c in df.columns if c not in exclude and df[c].dtype in ['float64', 'int64', 'float32', 'int32']]
    
    X = df[feature_cols].fillna(0).values
    y = df['target'].values
    
    print(f"Donnees: {X.shape[0]} samples, {X.shape[1]} features")
    print(f"Distribution: {(y==1).sum()} positifs ({(y==1).sum()/len(y)*100:.1f}%)")
    
    return X, y, feature_cols

def evaluate(model, X, y, name="Model", use_smote=False):
    """Evaluate avec CV"""
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    train_accs, test_accs, f1s, precs, recs = [], [], [], [], []
    
    for train_idx, test_idx in cv.split(X, y):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        
        # SMOTE si demande
        if use_smote:
            try:
                smote = SMOTE(random_state=42)
                X_train, y_train = smote.fit_resample(X_train, y_train)
            except:
                pass
        
        # Scale
        scaler = RobustScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)
        
        # Class weights
        cw = compute_class_weight('balanced', classes=np.unique(y_train), y=y_train)
        sw = np.array([cw[0] if l==0 else cw[1] for l in y_train])
        
        # Fit
        try:
            model.fit(X_train_s, y_train, sample_weight=sw)
        except TypeError:
            model.fit(X_train_s, y_train)
        
        y_train_pred = model.predict(X_train_s)
        y_test_pred = model.predict(X_test_s)
        
        train_accs.append(accuracy_score(y_train, y_train_pred))
        test_accs.append(accuracy_score(y_test, y_test_pred))
        f1s.append(f1_score(y_test, y_test_pred, zero_division=0))
        precs.append(precision_score(y_test, y_test_pred, zero_division=0))
        recs.append(recall_score(y_test, y_test_pred, zero_division=0))
    
    return {
        'name': name,
        'train_acc': np.mean(train_accs),
        'test_acc': np.mean(test_accs),
        'f1': np.mean(f1s),
        'precision': np.mean(precs),
        'recall': np.mean(recs),
        'gap': np.mean(train_accs) - np.mean(test_accs)
    }

def test_threshold_tuning(X, y, k=20):
    """Teste differents seuils de decision"""
    print("\n=== TEST THRESHOLD TUNING ===")
    
    # Selection features
    selector = SelectKBest(f_classif, k=k)
    X_sel = selector.fit_transform(X, y)
    
    # Split
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(X_sel, y, test_size=0.2, stratify=y, random_state=42)
    
    # Scale
    scaler = RobustScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    
    # Class weights
    cw = compute_class_weight('balanced', classes=np.unique(y_train), y=y_train)
    sw = np.array([cw[0] if l==0 else cw[1] for l in y_train])
    
    # Model
    model = HistGradientBoostingClassifier(
        max_iter=300, max_depth=2, learning_rate=0.089,
        min_samples_leaf=50, l2_regularization=0.9,
        random_state=42, early_stopping=True
    )
    model.fit(X_train_s, y_train, sample_weight=sw)
    
    # Probabilites
    y_proba = model.predict_proba(X_test_s)[:, 1]
    
    # Tester differents seuils
    best_f1 = 0
    best_threshold = 0.5
    best_result = None
    
    print(f"{'Threshold':<12} {'Accuracy':<10} {'F1':<10} {'Precision':<10} {'Recall':<10}")
    print("-" * 55)
    
    for threshold in [0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7]:
        y_pred = (y_proba >= threshold).astype(int)
        
        acc = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)
        
        print(f"{threshold:<12} {acc*100:<10.1f}% {f1:<10.3f} {prec:<10.3f} {rec:<10.3f}")
        
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = threshold
            best_result = {'acc': acc, 'f1': f1, 'prec': prec, 'rec': rec}
    
    print(f"\nMeilleur seuil: {best_threshold} avec F1={best_f1:.3f}")
    return best_threshold, best_result

def test_smote(X, y, k=20):
    """Teste SMOTE pour equilibrer les classes"""
    print("\n=== TEST SMOTE ===")
    
    # Selection features
    selector = SelectKBest(f_classif, k=k)
    X_sel = selector.fit_transform(X, y)
    
    model = HistGradientBoostingClassifier(
        max_iter=300, max_depth=2, learning_rate=0.089,
        min_samples_leaf=50, l2_regularization=0.9,
        random_state=42, early_stopping=True
    )
    
    # Sans SMOTE
    result_no_smote = evaluate(model, X_sel, y, "Sans SMOTE", use_smote=False)
    print(f"Sans SMOTE: Acc={result_no_smote['test_acc']*100:.1f}%, F1={result_no_smote['f1']:.3f}, Prec={result_no_smote['precision']:.3f}")
    
    # Avec SMOTE
    model2 = HistGradientBoostingClassifier(
        max_iter=300, max_depth=2, learning_rate=0.089,
        min_samples_leaf=50, l2_regularization=0.9,
        random_state=42, early_stopping=True
    )
    result_smote = evaluate(model2, X_sel, y, "Avec SMOTE", use_smote=True)
    print(f"Avec SMOTE: Acc={result_smote['test_acc']*100:.1f}%, F1={result_smote['f1']:.3f}, Prec={result_smote['precision']:.3f}")
    
    return result_no_smote, result_smote

def test_ensemble_advanced(X, y, k=20):
    """Teste ensemble voting avance"""
    print("\n=== TEST ENSEMBLE VOTING ===")
    
    # Selection features
    selector = SelectKBest(f_classif, k=k)
    X_sel = selector.fit_transform(X, y)
    
    # Modeles
    hgb = HistGradientBoostingClassifier(max_iter=200, max_depth=2, learning_rate=0.05, random_state=42)
    rf = RandomForestClassifier(n_estimators=150, max_depth=5, min_samples_leaf=20, class_weight='balanced', random_state=42)
    hgb2 = HistGradientBoostingClassifier(max_iter=150, max_depth=3, learning_rate=0.03, random_state=43)
    
    # Voting soft
    voting = VotingClassifier(
        estimators=[('hgb', hgb), ('rf', rf), ('hgb2', hgb2)],
        voting='soft'
    )
    
    result = evaluate(voting, X_sel, y, "Ensemble Voting (soft)")
    print(f"Ensemble Voting: Acc={result['test_acc']*100:.1f}%, F1={result['f1']:.3f}, Prec={result['precision']:.3f}, Gap={result['gap']*100:.1f}%")
    
    return result

def test_different_k(X, y):
    """Teste differents nombres de features"""
    print("\n=== TEST NOMBRE DE FEATURES ===")
    
    results = []
    for k in [15, 20, 25, 30, 35, 40]:
        selector = SelectKBest(f_classif, k=k)
        X_sel = selector.fit_transform(X, y)
        
        model = HistGradientBoostingClassifier(
            max_iter=300, max_depth=2, learning_rate=0.089,
            min_samples_leaf=50, l2_regularization=0.9,
            random_state=42, early_stopping=True
        )
        
        result = evaluate(model, X_sel, y, f"k={k}")
        results.append(result)
        print(f"k={k}: Acc={result['test_acc']*100:.1f}%, F1={result['f1']:.3f}, Prec={result['precision']:.3f}, Gap={result['gap']*100:.1f}%")
    
    # Trouver le meilleur
    best = max(results, key=lambda r: r['f1'] + r['precision'] - r['gap']*0.5)
    print(f"\nMeilleur: {best['name']} avec F1={best['f1']:.3f}")
    
    return results

def main():
    X, y, feature_cols = load_data()
    
    # Test 1: Nombre de features
    results_k = test_different_k(X, y)
    best_k = int(max(results_k, key=lambda r: r['f1'])['name'].split('=')[1])
    
    # Test 2: SMOTE
    result_no_smote, result_smote = test_smote(X, y, k=best_k)
    
    # Test 3: Threshold tuning
    best_threshold, best_result = test_threshold_tuning(X, y, k=best_k)
    
    # Test 4: Ensemble
    result_ensemble = test_ensemble_advanced(X, y, k=best_k)
    
    # Resume
    print("\n" + "=" * 70)
    print("  RESUME DES RESULTATS")
    print("=" * 70)
    
    all_results = [
        {'name': f'HistGB k={best_k}', **result_no_smote},
        {'name': f'HistGB+SMOTE k={best_k}', **result_smote},
        {'name': f'Ensemble Voting k={best_k}', **result_ensemble},
    ]
    
    print(f"{'Methode':<30} {'Acc':<10} {'F1':<10} {'Prec':<10} {'Gap':<10}")
    print("-" * 70)
    for r in all_results:
        print(f"{r['name']:<30} {r['test_acc']*100:<10.1f}% {r['f1']:<10.3f} {r['precision']:<10.3f} {r['gap']*100:<10.1f}%")
    
    print(f"\nMeilleur seuil de decision: {best_threshold}")
    print(f"Avec ce seuil: F1={best_result['f1']:.3f}, Precision={best_result['prec']:.3f}")
    
    # Recommandation
    print("\n" + "=" * 70)
    print("  RECOMMANDATION")
    print("=" * 70)
    best = max(all_results, key=lambda r: r['f1'] + r['precision'] - r['gap']*0.3)
    print(f"Meilleure approche: {best['name']}")
    print(f"  Accuracy: {best['test_acc']*100:.1f}%")
    print(f"  F1 Score: {best['f1']:.3f}")
    print(f"  Precision: {best['precision']:.3f}")
    print(f"  Gap: {best['gap']*100:.1f}%")

if __name__ == "__main__":
    main()
