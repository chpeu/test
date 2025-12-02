# -*- coding: utf-8 -*-
"""
Advanced ML Optimizer - Exploration complete de toutes les pistes
pour depasser les objectifs ML
"""

import sys
import os
import time
import json
import warnings
warnings.filterwarnings('ignore')

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Setup env
os.environ['POSTGRES_PASSWORD'] = 'Goldorak8!'
os.environ['POSTGRES_DB'] = 'trades_db'

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import RobustScaler, StandardScaler
from sklearn.feature_selection import SelectKBest, f_classif, mutual_info_classif, RFE
from sklearn.ensemble import (
    GradientBoostingClassifier, 
    HistGradientBoostingClassifier,
    RandomForestClassifier,
    AdaBoostClassifier,
    BaggingClassifier,
    VotingClassifier,
    StackingClassifier
)
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.utils.class_weight import compute_class_weight
import optuna
from optuna.samplers import TPESampler

print("=" * 70)
print("  ADVANCED ML OPTIMIZER - Exploration complete")
print("=" * 70)

# Objectifs
TARGET_ACCURACY = 0.62
TARGET_F1 = 0.50
TARGET_PRECISION = 0.55
TARGET_MAX_GAP = 0.12

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def load_data():
    """Charge les donnees depuis le modele existant"""
    log("Chargement des donnees via API backend...")
    try:
        import requests
        import joblib
        from pathlib import Path
        
        # Charger les donnees via le backend qui tourne deja
        # Alternative: charger directement depuis les fichiers sauvegardes
        
        # Essayer de charger le dataset depuis les fichiers caches
        cache_dir = Path(__file__).parent / "optimization" / "data"
        
        # Utiliser le feature loader du backend (qui fonctionne)
        # En appelant l'API de training qui charge les donnees
        log("Chargement via module interne...")
        
        # Import du module qui fonctionne dans le backend
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        
        from sqlalchemy import create_engine
        from urllib.parse import quote_plus
        
        # Lire le .env manuellement
        env_path = Path(__file__).parent / ".env"
        env_vars = {}
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
        
        password = env_vars.get('POSTGRES_PASSWORD', '')
        password_encoded = quote_plus(password)
        host = env_vars.get('POSTGRES_HOST', 'localhost')
        port = env_vars.get('POSTGRES_PORT', '5432')
        database = env_vars.get('POSTGRES_DB', 'trade_cursor_ml')
        user = env_vars.get('POSTGRES_USER', 'postgres')
        
        connection_string = f"postgresql://{user}:{password_encoded}@{host}:{port}/{database}"
        engine = create_engine(connection_string)
        
        # Utiliser la table ml_features qui contient les donnees ML
        query = "SELECT * FROM ml_features WHERE target_pnl IS NOT NULL LIMIT 5000"
        df = pd.read_sql(query, engine)
        engine.dispose()
        
        log(f"Table ml_features: {len(df)} lignes")
        
        if df is None or len(df) == 0:
            log("Erreur: pas de donnees")
            return None, None, None
        
        log(f"Donnees chargees: {len(df)} lignes, {len(df.columns)} colonnes")
        
        # Trouver la colonne target
        target_col = None
        # Chercher une colonne qui pourrait etre le target
        for col in ['target_pnl', 'is_profitable', 'profitable', 'result_pnl_pct', 'pnl_pct', 'pnl']:
            if col in df.columns:
                target_col = col
                log(f"Target trouve: {col}")
                break
        
        if target_col is None or target_col not in df.columns:
            log(f"Colonnes disponibles: {df.columns.tolist()[:20]}...")
            log("Erreur: colonne target non trouvee")
            return None, None, None
        
        # Si target est numerique (pnl%), convertir en binaire
        if df[target_col].dtype in ['float64', 'float32', 'int64', 'int32']:
            df['target'] = (df[target_col] > 0).astype(int)
            target_col = 'target'
            log(f"Target converti en binaire (pnl > 0)")
        
        # Colonnes a exclure
        exclude_cols = ['id', 'created_at', 'timestamp', 'symbol', 'timeframe', 
                       'is_profitable', 'pnl_pct', 'trade_id', 'direction',
                       'target_pnl', 'target', 'scan_id']
        
        feature_cols = [c for c in df.columns if c not in exclude_cols 
                       and df[c].dtype in ['float64', 'int64', 'float32', 'int32']]
        
        X = df[feature_cols].fillna(0).values
        y = df[target_col].astype(int).values
        
        log(f"Donnees chargees: {X.shape[0]} samples, {X.shape[1]} features")
        log(f"Distribution: {(y==1).sum()} positifs ({(y==1).sum()/len(y)*100:.1f}%), {(y==0).sum()} negatifs")
        
        return X, y, feature_cols
    except Exception as e:
        log(f"Erreur chargement: {e}")
        return None, None, None

def evaluate_model(model, X, y, name="Model"):
    """Evalue un modele avec CV"""
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    # Class weights
    class_weights = compute_class_weight('balanced', classes=np.unique(y), y=y)
    sample_weights = np.array([class_weights[0] if label == 0 else class_weights[1] for label in y])
    
    # CV manuelle pour utiliser sample_weight
    train_accs, test_accs, f1s, precs = [], [], [], []
    
    for train_idx, test_idx in cv.split(X, y):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        sw_train = sample_weights[train_idx]
        
        # Scale
        scaler = RobustScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)
        
        # Fit
        try:
            model.fit(X_train_s, y_train, sample_weight=sw_train)
        except TypeError:
            model.fit(X_train_s, y_train)
        
        # Predict
        y_train_pred = model.predict(X_train_s)
        y_test_pred = model.predict(X_test_s)
        
        train_accs.append(accuracy_score(y_train, y_train_pred))
        test_accs.append(accuracy_score(y_test, y_test_pred))
        f1s.append(f1_score(y_test, y_test_pred, zero_division=0))
        precs.append(precision_score(y_test, y_test_pred, zero_division=0))
    
    result = {
        'name': name,
        'train_acc': np.mean(train_accs),
        'test_acc': np.mean(test_accs),
        'f1': np.mean(f1s),
        'precision': np.mean(precs),
        'gap': np.mean(train_accs) - np.mean(test_accs)
    }
    
    return result

def test_feature_selection_methods(X, y):
    """Teste differentes methodes de selection de features"""
    log("\n=== TEST SELECTION DE FEATURES ===")
    results = []
    
    # Differents nombres de features
    for k in [15, 20, 25, 30, 40]:
        if k > X.shape[1]:
            continue
            
        # SelectKBest avec f_classif
        selector = SelectKBest(f_classif, k=k)
        X_sel = selector.fit_transform(X, y)
        
        model = HistGradientBoostingClassifier(
            max_iter=150, max_depth=3, learning_rate=0.03,
            min_samples_leaf=30, l2_regularization=0.5,
            random_state=42, early_stopping=True
        )
        
        result = evaluate_model(model, X_sel, y, f"SelectKBest k={k}")
        results.append(result)
        log(f"  k={k}: Acc={result['test_acc']*100:.1f}%, F1={result['f1']:.3f}, Gap={result['gap']*100:.1f}%")
    
    return results

def test_different_models(X, y, k_features=25):
    """Teste differents algorithmes"""
    log("\n=== TEST DIFFERENTS MODELES ===")
    
    # Selection features
    selector = SelectKBest(f_classif, k=min(k_features, X.shape[1]))
    X_sel = selector.fit_transform(X, y)
    log(f"Features selectionnees: {X_sel.shape[1]}")
    
    models = {
        'HistGradientBoosting': HistGradientBoostingClassifier(
            max_iter=200, max_depth=3, learning_rate=0.03,
            min_samples_leaf=30, l2_regularization=0.5,
            random_state=42, early_stopping=True
        ),
        'GradientBoosting': GradientBoostingClassifier(
            n_estimators=150, max_depth=3, learning_rate=0.03,
            min_samples_leaf=30, subsample=0.8,
            random_state=42
        ),
        'RandomForest': RandomForestClassifier(
            n_estimators=200, max_depth=5, min_samples_leaf=20,
            class_weight='balanced', random_state=42, n_jobs=-1
        ),
        'AdaBoost': AdaBoostClassifier(
            n_estimators=100, learning_rate=0.1, random_state=42
        ),
        'Bagging_GB': BaggingClassifier(
            estimator=GradientBoostingClassifier(n_estimators=50, max_depth=3, random_state=42),
            n_estimators=10, random_state=42, n_jobs=-1
        ),
    }
    
    results = []
    for name, model in models.items():
        log(f"  Testing {name}...")
        result = evaluate_model(model, X_sel, y, name)
        results.append(result)
        log(f"    Acc={result['test_acc']*100:.1f}%, F1={result['f1']:.3f}, Prec={result['precision']:.3f}, Gap={result['gap']*100:.1f}%")
    
    return results

def test_ensemble_models(X, y, k_features=25):
    """Teste des ensembles de modeles"""
    log("\n=== TEST ENSEMBLE MODELS ===")
    
    # Selection features
    selector = SelectKBest(f_classif, k=min(k_features, X.shape[1]))
    X_sel = selector.fit_transform(X, y)
    
    # Voting Classifier
    estimators = [
        ('gb', GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42)),
        ('rf', RandomForestClassifier(n_estimators=100, max_depth=5, class_weight='balanced', random_state=42)),
        ('hgb', HistGradientBoostingClassifier(max_iter=100, max_depth=3, random_state=42))
    ]
    
    results = []
    
    # Soft voting
    voting_soft = VotingClassifier(estimators=estimators, voting='soft')
    result = evaluate_model(voting_soft, X_sel, y, "VotingClassifier (soft)")
    results.append(result)
    log(f"  Voting (soft): Acc={result['test_acc']*100:.1f}%, F1={result['f1']:.3f}, Gap={result['gap']*100:.1f}%")
    
    # Hard voting
    voting_hard = VotingClassifier(estimators=estimators, voting='hard')
    result = evaluate_model(voting_hard, X_sel, y, "VotingClassifier (hard)")
    results.append(result)
    log(f"  Voting (hard): Acc={result['test_acc']*100:.1f}%, F1={result['f1']:.3f}, Gap={result['gap']*100:.1f}%")
    
    return results

def optimize_best_model(X, y, k_features=25, n_trials=150):
    """Optimise le meilleur modele avec Optuna"""
    log(f"\n=== OPTIMISATION OPTUNA ({n_trials} trials) ===")
    
    # Selection features
    selector = SelectKBest(f_classif, k=min(k_features, X.shape[1]))
    X_sel = selector.fit_transform(X, y)
    
    # Class weights
    class_weights = compute_class_weight('balanced', classes=np.unique(y), y=y)
    sample_weights = np.array([class_weights[0] if label == 0 else class_weights[1] for label in y])
    
    def objective(trial):
        # Hyperparametres
        n_estimators = trial.suggest_int('n_estimators', 100, 300, step=50)
        max_depth = trial.suggest_int('max_depth', 2, 4)
        learning_rate = trial.suggest_float('learning_rate', 0.01, 0.1, log=True)
        min_samples_leaf = trial.suggest_int('min_samples_leaf', 20, 50, step=5)
        l2_reg = trial.suggest_float('l2_regularization', 0.1, 1.0)
        
        model = HistGradientBoostingClassifier(
            max_iter=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            min_samples_leaf=min_samples_leaf,
            l2_regularization=l2_reg,
            random_state=42,
            early_stopping=True,
            n_iter_no_change=15,
            validation_fraction=0.15
        )
        
        # CV
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        scores = []
        gaps = []
        
        for train_idx, test_idx in cv.split(X_sel, y):
            X_train, X_test = X_sel[train_idx], X_sel[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]
            sw_train = sample_weights[train_idx]
            
            scaler = RobustScaler()
            X_train_s = scaler.fit_transform(X_train)
            X_test_s = scaler.transform(X_test)
            
            model.fit(X_train_s, y_train, sample_weight=sw_train)
            
            y_train_pred = model.predict(X_train_s)
            y_test_pred = model.predict(X_test_s)
            
            train_acc = accuracy_score(y_train, y_train_pred)
            test_acc = accuracy_score(y_test, y_test_pred)
            f1 = f1_score(y_test, y_test_pred, zero_division=0)
            prec = precision_score(y_test, y_test_pred, zero_division=0)
            
            # Score composite: precision + f1 - penalite gap
            gap = train_acc - test_acc
            score = 0.4 * prec + 0.4 * f1 + 0.2 * test_acc - 0.5 * max(0, gap - 0.1)
            scores.append(score)
            gaps.append(gap)
        
        return np.mean(scores)
    
    # Optimisation
    sampler = TPESampler(seed=42)
    study = optuna.create_study(direction='maximize', sampler=sampler)
    
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False, 
                   callbacks=[lambda study, trial: log(f"  Trial {trial.number}: {trial.value:.4f}") if trial.number % 30 == 0 else None])
    
    log(f"\nMeilleurs parametres: {study.best_params}")
    log(f"Meilleur score: {study.best_value:.4f}")
    
    return study.best_params

def train_final_model(X, y, params, k_features=25):
    """Entraine le modele final avec les meilleurs parametres"""
    log("\n=== ENTRAINEMENT MODELE FINAL ===")
    
    # Selection features
    selector = SelectKBest(f_classif, k=min(k_features, X.shape[1]))
    X_sel = selector.fit_transform(X, y)
    
    model = HistGradientBoostingClassifier(
        max_iter=params.get('n_estimators', 200),
        max_depth=params.get('max_depth', 3),
        learning_rate=params.get('learning_rate', 0.03),
        min_samples_leaf=params.get('min_samples_leaf', 30),
        l2_regularization=params.get('l2_regularization', 0.5),
        random_state=42,
        early_stopping=True,
        n_iter_no_change=15,
        validation_fraction=0.15
    )
    
    result = evaluate_model(model, X_sel, y, "Final Model")
    
    print("\n" + "=" * 60)
    print("  RESULTATS FINAUX")
    print("=" * 60)
    print(f"  Test Accuracy:  {result['test_acc']*100:.1f}%  (objectif: {TARGET_ACCURACY*100:.0f}%)")
    print(f"  F1 Score:       {result['f1']:.3f}    (objectif: {TARGET_F1:.2f})")
    print(f"  Precision:      {result['precision']:.3f}    (objectif: {TARGET_PRECISION:.2f})")
    print(f"  Overfitting Gap: {result['gap']*100:.1f}%   (objectif: <{TARGET_MAX_GAP*100:.0f}%)")
    print("=" * 60)
    
    # Check objectifs
    passed = []
    failed = []
    if result['test_acc'] >= TARGET_ACCURACY:
        passed.append(f"Accuracy {result['test_acc']*100:.1f}% >= {TARGET_ACCURACY*100:.0f}%")
    else:
        failed.append(f"Accuracy {result['test_acc']*100:.1f}% < {TARGET_ACCURACY*100:.0f}%")
    
    if result['f1'] >= TARGET_F1:
        passed.append(f"F1 {result['f1']:.3f} >= {TARGET_F1:.2f}")
    else:
        failed.append(f"F1 {result['f1']:.3f} < {TARGET_F1:.2f}")
    
    if result['precision'] >= TARGET_PRECISION:
        passed.append(f"Precision {result['precision']:.3f} >= {TARGET_PRECISION:.2f}")
    else:
        failed.append(f"Precision {result['precision']:.3f} < {TARGET_PRECISION:.2f}")
    
    if result['gap'] <= TARGET_MAX_GAP:
        passed.append(f"Gap {result['gap']*100:.1f}% <= {TARGET_MAX_GAP*100:.0f}%")
    else:
        failed.append(f"Gap {result['gap']*100:.1f}% > {TARGET_MAX_GAP*100:.0f}%")
    
    print(f"\n  Objectifs atteints: {len(passed)}/4")
    for p in passed:
        print(f"    [OK] {p}")
    for f in failed:
        print(f"    [X]  {f}")
    
    return result, params

def main():
    # Charger les donnees
    X, y, feature_names = load_data()
    if X is None:
        return
    
    all_results = []
    
    # 1. Test selection de features
    results = test_feature_selection_methods(X, y)
    all_results.extend(results)
    
    # Trouver le meilleur k
    best_k_result = max(results, key=lambda r: r['f1'] - r['gap'] * 0.5)
    best_k = int(best_k_result['name'].split('=')[1])
    log(f"\nMeilleur nombre de features: {best_k}")
    
    # 2. Test differents modeles
    results = test_different_models(X, y, best_k)
    all_results.extend(results)
    
    # 3. Test ensembles
    results = test_ensemble_models(X, y, best_k)
    all_results.extend(results)
    
    # 4. Optimisation Optuna
    best_params = optimize_best_model(X, y, best_k, n_trials=150)
    
    # 5. Entrainement final
    final_result, params = train_final_model(X, y, best_params, best_k)
    
    # Resume de tous les tests
    print("\n" + "=" * 70)
    print("  RESUME DE TOUS LES TESTS")
    print("=" * 70)
    all_results.append(final_result)
    
    # Trier par score composite
    all_results_sorted = sorted(all_results, 
                                key=lambda r: r['f1'] + r['precision'] - r['gap'],
                                reverse=True)
    
    print(f"{'Model':<30} {'Acc':>8} {'F1':>8} {'Prec':>8} {'Gap':>8}")
    print("-" * 70)
    for r in all_results_sorted[:10]:
        print(f"{r['name']:<30} {r['test_acc']*100:>7.1f}% {r['f1']:>8.3f} {r['precision']:>8.3f} {r['gap']*100:>7.1f}%")
    
    print("\n" + "=" * 70)
    print("  MEILLEUR MODELE TROUVE:")
    best = all_results_sorted[0]
    print(f"  {best['name']}")
    print(f"  Accuracy: {best['test_acc']*100:.1f}%, F1: {best['f1']:.3f}, Precision: {best['precision']:.3f}, Gap: {best['gap']*100:.1f}%")
    print("=" * 70)

if __name__ == "__main__":
    main()
