#!/usr/bin/env python3
"""
🔥 RÉENTRAÎNEMENT ALIGNÉ avec Optuna
====================================
Ce script entraîne le modèle GradientBoosting avec EXACTEMENT
les mêmes données et paramètres que l'optimisation Optuna.

Garantit que les métriques affichées = métriques réelles.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import joblib

# ========== CONFIGURATION ==========
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PROJECT_ROOT / "config_overrides.json"
MODELS_DIR = PROJECT_ROOT / "optimization" / "saved_models"
RANDOM_STATE = 42
CV_FOLDS = 5
TEST_SIZE = 0.2

# ========== FONCTIONS ==========

def load_config():
    """Charger les paramètres depuis config_overrides.json"""
    print("\n" + "="*60)
    print("📋 1. CHARGEMENT CONFIGURATION")
    print("="*60)
    
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    params = {
        'n_estimators': config.get('gb_n_estimators', 200),
        'max_depth': config.get('gb_max_depth', 3),
        'learning_rate': config.get('gb_learning_rate', 0.03),
        'min_samples_split': config.get('gb_min_samples_split', 30),
        'min_samples_leaf': config.get('gb_min_samples_leaf', 15),
        'subsample': config.get('gb_subsample', 0.7),
        'max_features': config.get('gb_max_features', 0.5),
    }
    
    model_type = config.get('gb_model_type', 'gb')
    timeframe = config.get('gb_timeframe_days', 365)
    
    print(f"🔧 Type de modèle: {model_type}")
    print(f"📅 Timeframe: {timeframe} jours")
    print(f"📊 Paramètres:")
    for key, value in params.items():
        print(f"   - {key}: {value}")
    
    return params, model_type, timeframe


def load_data_aligned(timeframe_days=365):
    """Charger les données EXACTEMENT comme Optuna"""
    print("\n" + "="*60)
    print("📊 2. CHARGEMENT DONNÉES (aligné Optuna)")
    print("="*60)
    
    from optimization.data.feature_loader import load_features_from_postgres
    
    MIN_TRADES = 100
    
    # 🔥 IDENTIQUE à optuna_gradientboosting.py - PAS de filtrage par config!
    df = load_features_from_postgres(
        min_trades=MIN_TRADES,
        timeframe_days=timeframe_days,
        include_open_trades=False
    )
    
    print(f"✅ Données brutes: {len(df)} trades")
    
    # Préparer features (IDENTIQUE à Optuna)
    exclude_cols = [
        'scan_id', 'timestamp', 'symbol', 'opportunity_direction',
        'target_win', 'target_pnl', 'is_opportunity',
        'reject_reason_category'
    ]
    
    feature_cols = [col for col in df.columns 
                    if col not in exclude_cols 
                    and df[col].dtype in ['float64', 'int64', 'float32', 'int32']]
    
    X = df[feature_cols].fillna(0)
    y = df['target_win'].dropna().astype(int)
    
    # Aligner X et y
    valid_idx = y.index
    X = X.loc[valid_idx]
    
    print(f"✅ Features: {len(feature_cols)} colonnes")
    print(f"   - Classe 0 (loss): {(y == 0).sum()} ({(y == 0).mean()*100:.1f}%)")
    print(f"   - Classe 1 (win): {(y == 1).sum()} ({(y == 1).mean()*100:.1f}%)")
    
    return X.values, y.values, feature_cols


def train_and_evaluate(X, y, params, model_type='gb'):
    """Entraîner et évaluer le modèle"""
    print("\n" + "="*60)
    print("🎯 3. ENTRAÎNEMENT ET ÉVALUATION")
    print("="*60)
    
    # Split train/test (IDENTIQUE à Optuna)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )
    
    print(f"📊 Split: Train={len(X_train)}, Test={len(X_test)}")
    
    # Scaling
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Créer le modèle
    if model_type == 'histgb':
        print(f"🚀 Modèle: HistGradientBoostingClassifier")
        model = HistGradientBoostingClassifier(
            max_iter=params.get('n_estimators', 200),
            max_depth=params.get('max_depth', 3),
            learning_rate=params.get('learning_rate', 0.03),
            min_samples_leaf=params.get('min_samples_leaf', 15),
            random_state=RANDOM_STATE,
            early_stopping=True,
            n_iter_no_change=15,
            validation_fraction=0.15
        )
    else:
        print(f"🌳 Modèle: GradientBoostingClassifier")
        model = GradientBoostingClassifier(
            n_estimators=params.get('n_estimators', 200),
            max_depth=params.get('max_depth', 3),
            learning_rate=params.get('learning_rate', 0.03),
            min_samples_split=params.get('min_samples_split', 30),
            min_samples_leaf=params.get('min_samples_leaf', 15),
            subsample=params.get('subsample', 0.7),
            max_features=params.get('max_features', 0.5),
            random_state=RANDOM_STATE
        )
    
    # Entraîner
    print(f"⏳ Entraînement en cours...")
    model.fit(X_train_scaled, y_train)
    
    # Évaluer
    y_pred_train = model.predict(X_train_scaled)
    y_pred_test = model.predict(X_test_scaled)
    
    train_acc = accuracy_score(y_train, y_pred_train)
    test_acc = accuracy_score(y_test, y_pred_test)
    test_f1 = f1_score(y_test, y_pred_test)
    test_prec = precision_score(y_test, y_pred_test)
    test_recall = recall_score(y_test, y_pred_test)
    gap = train_acc - test_acc
    
    print(f"\n📈 RÉSULTATS:")
    print(f"   🏋️ Train Accuracy: {train_acc*100:.1f}%")
    print(f"   🎯 Test Accuracy:  {test_acc*100:.1f}%")
    print(f"   📊 F1 Score:       {test_f1:.3f}")
    print(f"   🎯 Precision:      {test_prec:.3f}")
    print(f"   📈 Recall:         {test_recall:.3f}")
    print(f"   ⚠️ Overfitting Gap: {gap*100:.1f}%")
    
    return {
        'model': model,
        'scaler': scaler,
        'train_acc': train_acc,
        'test_acc': test_acc,
        'test_f1': test_f1,
        'test_prec': test_prec,
        'test_recall': test_recall,
        'gap': gap
    }, X_train, X_test, y_train, y_test


def cross_validate(X, y, params, model_type='gb'):
    """Cross-validation pour vérifier la stabilité"""
    print("\n" + "="*60)
    print("🔬 4. CROSS-VALIDATION (vérification)")
    print("="*60)
    
    if model_type == 'histgb':
        model = HistGradientBoostingClassifier(
            max_iter=params.get('n_estimators', 200),
            max_depth=params.get('max_depth', 3),
            learning_rate=params.get('learning_rate', 0.03),
            min_samples_leaf=params.get('min_samples_leaf', 15),
            random_state=RANDOM_STATE
        )
    else:
        model = GradientBoostingClassifier(
            n_estimators=params.get('n_estimators', 200),
            max_depth=params.get('max_depth', 3),
            learning_rate=params.get('learning_rate', 0.03),
            min_samples_split=params.get('min_samples_split', 30),
            min_samples_leaf=params.get('min_samples_leaf', 15),
            subsample=params.get('subsample', 0.7),
            max_features=params.get('max_features', 0.5),
            random_state=RANDOM_STATE
        )
    
    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    scores = cross_val_score(model, X, y, cv=cv, scoring='accuracy')
    
    print(f"📊 CV {CV_FOLDS}-fold Accuracy: {scores.mean()*100:.1f}% ± {scores.std()*100:.1f}%")
    print(f"   Scores: {[f'{s*100:.1f}%' for s in scores]}")
    
    return scores


def save_model(results, params, feature_cols, model_type, cv_scores):
    """Sauvegarder le modèle et les métadonnées"""
    print("\n" + "="*60)
    print("💾 5. SAUVEGARDE")
    print("="*60)
    
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Créer pipeline
    pipeline = Pipeline([
        ('scaler', results['scaler']),
        ('model', results['model'])
    ])
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Sauvegarder modèle
    model_path = MODELS_DIR / f"best_classifier_{timestamp}.pkl"
    latest_path = MODELS_DIR / "best_classifier_latest.pkl"
    
    joblib.dump(pipeline, model_path)
    joblib.dump(pipeline, latest_path)
    
    print(f"✅ Modèle sauvegardé: {model_path}")
    print(f"✅ Modèle latest: {latest_path}")
    
    # Sauvegarder métadonnées
    model_name = 'HistGradientBoostingClassifier' if model_type == 'histgb' else 'GradientBoostingClassifier'
    
    metadata = {
        'timestamp': timestamp,
        'best_model': model_name,
        'model_type': model_type,
        'metrics': {
            # 🔬 MÉTRIQUES CV (les plus fiables!)
            'cv_accuracy': float(cv_scores.mean()),
            'cv_accuracy_std': float(cv_scores.std()),
            'cv_f1': float(results['test_f1']),  # Approximation
            # Métriques holdout
            'train_acc': float(results['train_acc']),
            'test_acc': float(results['test_acc']),
            'test_f1': float(results['test_f1']),
            'test_precision': float(results['test_prec']),
            'gap': float(results['gap'])
        },
        'params': params,
        'n_features': len(feature_cols),
        'feature_cols': feature_cols
    }
    
    with open(MODELS_DIR / "best_classifier_metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✅ Métadonnées sauvegardées")
    
    return metadata


def main():
    """Exécution principale"""
    print("\n" + "="*80)
    print("🔥 RÉENTRAÎNEMENT ALIGNÉ AVEC OPTUNA")
    print("="*80)
    
    # 1. Charger config
    params, model_type, timeframe = load_config()
    
    # 2. Charger données (aligné Optuna)
    X, y, feature_cols = load_data_aligned(timeframe)
    
    # 3. Entraîner et évaluer
    results, X_train, X_test, y_train, y_test = train_and_evaluate(X, y, params, model_type)
    
    # 4. Cross-validation
    cv_scores = cross_validate(X, y, params, model_type)
    
    # 5. Sauvegarder
    metadata = save_model(results, params, feature_cols, model_type, cv_scores)
    
    # Résumé final
    print("\n" + "="*80)
    print("✅ RÉSUMÉ")
    print("="*80)
    print(f"""
🎯 MÉTRIQUES FINALES (ce que l'UI devrait afficher):
   - Test Accuracy: {results['test_acc']*100:.1f}%
   - F1 Score:      {results['test_f1']:.3f}
   - Precision:     {results['test_prec']:.3f}
   - Overfitting:   {results['gap']*100:.1f}%
   
📊 Cross-Validation:
   - Accuracy:      {cv_scores.mean()*100:.1f}% ± {cv_scores.std()*100:.1f}%
   
💾 Fichiers créés:
   - {MODELS_DIR}/best_classifier_latest.pkl
   - {MODELS_DIR}/best_classifier_metadata.json
   
⚠️  Rechargez la page pour voir les nouvelles métriques dans l'UI.
""")
    
    return metadata


if __name__ == "__main__":
    main()
