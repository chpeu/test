#!/usr/bin/env python3
"""
🔬 Script de vérification complète pour GradientBoosting Optuna
Vérifie:
1. Cohérence des paramètres (sliders ↔ config ↔ modèle)
2. Reproductibilité des métriques d'optimisation
3. Validation croisée du modèle actuel
"""

import sys
import os
import json
import pickle
from pathlib import Path

# Fix encoding Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold, train_test_split
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, classification_report

# ========== CONFIGURATION ==========

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PROJECT_ROOT / "config_overrides.json"
MODELS_DIR = PROJECT_ROOT / "optimization" / "saved_models"
RANDOM_STATE = 42

# ========== FONCTIONS UTILITAIRES ==========

def load_config():
    """Charger la configuration actuelle"""
    print("\n" + "="*60)
    print("📋 1. VÉRIFICATION DE LA CONFIGURATION")
    print("="*60)
    
    if not CONFIG_FILE.exists():
        print(f"❌ Fichier config introuvable: {CONFIG_FILE}")
        return None
    
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Extraire les paramètres GB
    gb_params = {
        'n_estimators': config.get('gb_n_estimators', 200),
        'max_depth': config.get('gb_max_depth', 3),
        'learning_rate': config.get('gb_learning_rate', 0.03),
        'min_samples_split': config.get('gb_min_samples_split', 30),
        'min_samples_leaf': config.get('gb_min_samples_leaf', 15),
        'subsample': config.get('gb_subsample', 0.7),
        'max_features': config.get('gb_max_features', 0.5),
    }
    
    model_type = config.get('gb_model_type', 'gb')
    
    print(f"📁 Fichier: {CONFIG_FILE}")
    print(f"🔧 Type de modèle: {model_type}")
    print(f"\n📊 Paramètres GB dans config_overrides.json:")
    for key, value in gb_params.items():
        print(f"   - {key}: {value}")
    
    return gb_params, model_type


def load_training_data(timeframe_days=365):
    """Charger les données d'entraînement"""
    print("\n" + "="*60)
    print("📊 2. CHARGEMENT DES DONNÉES")
    print("="*60)
    
    try:
        # Utiliser le même loader que optuna_gradientboosting.py
        from optimization.data.feature_loader import load_features_from_postgres
        
        MIN_TRADES_REQUIRED = 100
        
        df = load_features_from_postgres(
            min_trades=MIN_TRADES_REQUIRED,
            timeframe_days=timeframe_days,
            include_open_trades=False
        )
        
        print(f"✅ Données chargées depuis DB: {len(df)} lignes")
        
        # Préparer features (exactement comme optuna_gradientboosting.py)
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
        
        return X.values, y.values
    except Exception as e:
        print(f"❌ Erreur chargement données: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def verify_cross_validation(X, y, params, model_type='gb', n_splits=5):
    """Vérifier les métriques par cross-validation"""
    print("\n" + "="*60)
    print("🔬 3. VALIDATION CROISÉE (5-fold stratifiée)")
    print("="*60)
    
    # Créer le modèle selon le type
    if model_type == 'histgb':
        # Convertir les paramètres pour HistGB
        hist_params = {
            'max_iter': params.get('n_estimators', 200),
            'max_depth': params.get('max_depth', 3),
            'learning_rate': params.get('learning_rate', 0.03),
            'min_samples_leaf': params.get('min_samples_leaf', 15),
            'random_state': RANDOM_STATE
        }
        model = HistGradientBoostingClassifier(**hist_params)
        print(f"🚀 Modèle: HistGradientBoostingClassifier")
    else:
        gb_params = {**params, 'random_state': RANDOM_STATE}
        model = GradientBoostingClassifier(**gb_params)
        print(f"🌳 Modèle: GradientBoostingClassifier")
    
    print(f"📊 Paramètres utilisés:")
    for key, value in params.items():
        print(f"   - {key}: {value}")
    
    # Cross-validation
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
    
    print(f"\n⏳ Exécution de la cross-validation {n_splits}-fold...")
    
    # Calculer les scores
    accuracy_scores = cross_val_score(model, X, y, cv=cv, scoring='accuracy')
    f1_scores = cross_val_score(model, X, y, cv=cv, scoring='f1')
    precision_scores = cross_val_score(model, X, y, cv=cv, scoring='precision')
    
    print(f"\n📈 Résultats Cross-Validation:")
    print(f"   - Accuracy: {accuracy_scores.mean()*100:.1f}% ± {accuracy_scores.std()*100:.1f}%")
    print(f"   - F1 Score: {f1_scores.mean():.3f} ± {f1_scores.std():.3f}")
    print(f"   - Precision: {precision_scores.mean():.3f} ± {precision_scores.std():.3f}")
    
    print(f"\n📊 Scores par fold:")
    for i, (acc, f1, prec) in enumerate(zip(accuracy_scores, f1_scores, precision_scores)):
        print(f"   Fold {i+1}: Acc={acc*100:.1f}%, F1={f1:.3f}, Prec={prec:.3f}")
    
    return {
        'cv_accuracy_mean': accuracy_scores.mean(),
        'cv_accuracy_std': accuracy_scores.std(),
        'cv_f1_mean': f1_scores.mean(),
        'cv_f1_std': f1_scores.std(),
        'cv_precision_mean': precision_scores.mean(),
        'cv_scores': accuracy_scores.tolist()
    }


def verify_holdout_validation(X, y, params, model_type='gb', test_size=0.2):
    """Vérifier avec holdout validation (train/test split)"""
    print("\n" + "="*60)
    print("🎯 4. VALIDATION HOLDOUT (80/20 split)")
    print("="*60)
    
    # Split des données
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=RANDOM_STATE, stratify=y
    )
    
    print(f"📊 Split des données:")
    print(f"   - Train: {X_train.shape[0]} samples")
    print(f"   - Test:  {X_test.shape[0]} samples")
    
    # Créer et entraîner le modèle
    if model_type == 'histgb':
        hist_params = {
            'max_iter': params.get('n_estimators', 200),
            'max_depth': params.get('max_depth', 3),
            'learning_rate': params.get('learning_rate', 0.03),
            'min_samples_leaf': params.get('min_samples_leaf', 15),
            'random_state': RANDOM_STATE
        }
        model = HistGradientBoostingClassifier(**hist_params)
    else:
        gb_params = {**params, 'random_state': RANDOM_STATE}
        model = GradientBoostingClassifier(**gb_params)
    
    print(f"\n⏳ Entraînement du modèle...")
    model.fit(X_train, y_train)
    
    # Prédictions
    y_pred_train = model.predict(X_train)
    y_pred_test = model.predict(X_test)
    
    # Métriques train
    train_acc = accuracy_score(y_train, y_pred_train)
    train_f1 = f1_score(y_train, y_pred_train)
    
    # Métriques test
    test_acc = accuracy_score(y_test, y_pred_test)
    test_f1 = f1_score(y_test, y_pred_test)
    test_precision = precision_score(y_test, y_pred_test)
    test_recall = recall_score(y_test, y_pred_test)
    
    # Gap d'overfitting
    overfitting_gap = train_acc - test_acc
    
    print(f"\n📈 Résultats Holdout:")
    print(f"   🏋️ TRAIN:")
    print(f"      - Accuracy: {train_acc*100:.1f}%")
    print(f"      - F1 Score: {train_f1:.3f}")
    print(f"   🎯 TEST (VRAIES MÉTRIQUES):")
    print(f"      - Accuracy: {test_acc*100:.1f}%")
    print(f"      - F1 Score: {test_f1:.3f}")
    print(f"      - Precision: {test_precision:.3f}")
    print(f"      - Recall: {test_recall:.3f}")
    print(f"   ⚠️ Overfitting Gap: {overfitting_gap*100:.1f}%")
    
    if overfitting_gap > 0.15:
        print(f"   🔴 ALERTE: Gap d'overfitting élevé (>15%)")
    elif overfitting_gap > 0.10:
        print(f"   🟡 ATTENTION: Gap d'overfitting modéré (>10%)")
    else:
        print(f"   🟢 OK: Gap d'overfitting acceptable (<10%)")
    
    return {
        'train_accuracy': train_acc,
        'test_accuracy': test_acc,
        'test_f1': test_f1,
        'test_precision': test_precision,
        'test_recall': test_recall,
        'overfitting_gap': overfitting_gap
    }


def compare_with_saved_model():
    """Comparer avec le modèle sauvegardé"""
    print("\n" + "="*60)
    print("📦 5. COMPARAISON AVEC MODÈLE SAUVEGARDÉ")
    print("="*60)
    
    model_path = MODELS_DIR / "optimized_classifier_latest.pkl"
    metadata_path = MODELS_DIR / "optimized_classifier_metadata.json"
    
    if not model_path.exists():
        print(f"⚠️ Modèle sauvegardé introuvable: {model_path}")
        return None
    
    # Charger le modèle
    with open(model_path, 'rb') as f:
        saved_model = pickle.load(f)
    
    print(f"✅ Modèle chargé: {type(saved_model).__name__}")
    
    # Charger les métadonnées
    if metadata_path.exists():
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        print(f"\n📊 Métadonnées du modèle sauvegardé:")
        if 'metrics' in metadata:
            metrics = metadata['metrics']
            print(f"   - Test Accuracy: {metrics.get('test_accuracy', 'N/A')}")
            print(f"   - Test F1: {metrics.get('test_f1', 'N/A')}")
        if 'params' in metadata:
            print(f"\n📊 Paramètres du modèle sauvegardé:")
            for key, value in metadata['params'].items():
                print(f"   - {key}: {value}")
    
    return saved_model


def run_full_verification():
    """Exécuter la vérification complète"""
    print("\n" + "="*80)
    print("🔬 VÉRIFICATION COMPLÈTE GRADIENTBOOSTING OPTUNA")
    print("="*80)
    
    # 1. Charger la config
    result = load_config()
    if result is None:
        return
    
    params, model_type = result
    
    # 2. Charger les données
    X, y = load_training_data(timeframe_days=365)
    if X is None:
        return
    
    # 3. Cross-validation
    cv_results = verify_cross_validation(X, y, params, model_type)
    
    # 4. Holdout validation
    holdout_results = verify_holdout_validation(X, y, params, model_type)
    
    # 5. Comparer avec modèle sauvegardé
    saved_model = compare_with_saved_model()
    
    # 6. Résumé
    print("\n" + "="*80)
    print("📋 RÉSUMÉ DE LA VÉRIFICATION")
    print("="*80)
    
    print(f"\n🎯 MÉTRIQUES ATTENDUES (ce que l'UI devrait afficher):")
    print(f"   - Test Accuracy: {holdout_results['test_accuracy']*100:.1f}%")
    print(f"   - F1 Score: {holdout_results['test_f1']:.3f}")
    print(f"   - Precision: {holdout_results['test_precision']:.3f}")
    print(f"   - Overfitting Gap: {holdout_results['overfitting_gap']*100:.1f}%")
    
    print(f"\n📊 Cross-Validation moyenne:")
    print(f"   - Accuracy: {cv_results['cv_accuracy_mean']*100:.1f}% ± {cv_results['cv_accuracy_std']*100:.1f}%")
    
    # Vérifier la cohérence
    diff = abs(cv_results['cv_accuracy_mean'] - holdout_results['test_accuracy'])
    if diff > 0.05:
        print(f"\n⚠️ ALERTE: Différence importante entre CV et Holdout ({diff*100:.1f}%)")
        print(f"   Cela peut indiquer une variance élevée dans les données.")
    else:
        print(f"\n✅ Cohérence OK: CV et Holdout sont proches (diff={diff*100:.1f}%)")
    
    return {
        'params': params,
        'model_type': model_type,
        'cv_results': cv_results,
        'holdout_results': holdout_results
    }


if __name__ == "__main__":
    results = run_full_verification()
