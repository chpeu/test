# -*- coding: utf-8 -*-
"""
Optimisation Avancée des Modèles ML

Techniques appliquées:
1. SMOTE pour équilibrage des classes
2. Optimisation du seuil de décision
3. Feature engineering avancé
4. Ensemble Voting
5. Hyperparameter tuning avec Optuna
"""

import sys
import os
import warnings
warnings.filterwarnings('ignore')

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json
import time
import pickle
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

# ML imports
from sklearn.ensemble import (
    GradientBoostingClassifier, RandomForestClassifier, 
    VotingClassifier, AdaBoostClassifier
)
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score,
    roc_auc_score, classification_report, precision_recall_curve
)
import xgboost as xgb

# SMOTE pour équilibrage
try:
    from imblearn.over_sampling import SMOTE
    SMOTE_AVAILABLE = True
except ImportError:
    SMOTE_AVAILABLE = False
    print("⚠️  imblearn non installé - SMOTE désactivé")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 90)
print("  OPTIMISATION AVANCÉE DES MODÈLES ML")
print("  Techniques: SMOTE | Seuil Optimal | Ensemble Voting")
print("=" * 90)

# =============================================================================
# CONFIGURATION
# =============================================================================
CONFIG = {
    'timeframe_days': 365,
    'min_trades': 50,
    'test_size': 0.2,
    'validation_size': 0.2,
    'max_features': 40,
    'use_smote': True,
    'optimize_threshold': True,
    'use_ensemble': True,
    'random_state': 42,
    'models_dir': 'optimization/saved_models'
}

# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def load_and_prepare_data():
    """Charge et prépare les données"""
    from optimization.data.feature_loader import load_features_from_postgres
    from optimization.data.feature_engineering import calculate_derived_features
    from optimization.utils.temporal_split import temporal_train_test_split
    
    print("\n" + "-" * 60)
    print("1. CHARGEMENT ET PRÉPARATION")
    print("-" * 60)
    
    # Charger
    df = load_features_from_postgres(
        timeframe_days=CONFIG['timeframe_days'],
        min_trades=CONFIG['min_trades'],
        include_open_trades=False
    )
    print(f"   ✅ {len(df)} trades chargés")
    
    # Feature engineering
    df = calculate_derived_features(df)
    
    # Ajouter features temporelles
    if 'timestamp' in df.columns:
        df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
        df['day_of_week'] = pd.to_datetime(df['timestamp']).dt.dayofweek
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        # Heures favorables (basé sur analyse précédente)
        df['is_favorable_hour'] = df['hour'].isin([2, 12, 16]).astype(int)
    
    # Colonnes à exclure
    exclude_cols = [
        'scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 
        'is_opportunity', 'reject_reason_category', 'opportunity_direction'
    ]
    config_cols = [col for col in df.columns if col.startswith('config_')]
    exclude_cols.extend(config_cols)
    
    feature_cols = [col for col in df.columns if col not in exclude_cols]
    
    # Nettoyer
    X = df[feature_cols].copy()
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.median())
    
    # Supprimer colonnes constantes
    constant_cols = [col for col in X.columns if X[col].std() == 0]
    if constant_cols:
        X = X.drop(columns=constant_cols)
        feature_cols = [col for col in feature_cols if col not in constant_cols]
    
    print(f"   ✅ {len(feature_cols)} features préparées")
    
    # Split temporel
    train_df, val_df, test_df = temporal_train_test_split(
        df,
        target_col='target_win',
        test_size=CONFIG['test_size'],
        validation_size=CONFIG['validation_size']
    )
    
    def get_xy(split_df):
        X = split_df[feature_cols].copy()
        X = X.replace([np.inf, -np.inf], np.nan)
        X = X.fillna(X.median())
        y = split_df['target_win'].values
        return X, y
    
    X_train, y_train = get_xy(train_df)
    X_val, y_val = get_xy(val_df)
    X_test, y_test = get_xy(test_df)
    
    print(f"   Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}")
    
    return X_train, y_train, X_val, y_val, X_test, y_test, feature_cols


def select_features(X_train, y_train, feature_cols, max_features=40):
    """Sélection de features par mutual information"""
    from sklearn.feature_selection import mutual_info_classif
    
    mi_scores = mutual_info_classif(X_train, y_train, random_state=CONFIG['random_state'])
    mi_df = pd.DataFrame({
        'feature': feature_cols,
        'mi_score': mi_scores
    }).sort_values('mi_score', ascending=False)
    
    selected = mi_df.head(max_features)['feature'].tolist()
    return selected


def apply_smote(X_train, y_train):
    """Applique SMOTE pour équilibrer les classes"""
    if not SMOTE_AVAILABLE or not CONFIG['use_smote']:
        return X_train, y_train
    
    print("\n   🔄 Application SMOTE...")
    
    # Vérifier le déséquilibre
    class_counts = np.bincount(y_train.astype(int))
    ratio = min(class_counts) / max(class_counts)
    
    if ratio > 0.8:
        print(f"   ℹ️  Classes déjà équilibrées (ratio={ratio:.2f})")
        return X_train, y_train
    
    smote = SMOTE(random_state=CONFIG['random_state'])
    X_resampled, y_resampled = smote.fit_resample(X_train, y_train)
    
    print(f"   ✅ SMOTE: {len(X_train)} → {len(X_resampled)} samples")
    
    return X_resampled, y_resampled


def find_optimal_threshold(model, X_val, y_val):
    """Trouve le seuil optimal pour maximiser F1"""
    if not CONFIG['optimize_threshold']:
        return 0.5
    
    y_proba = model.predict_proba(X_val)[:, 1]
    
    precisions, recalls, thresholds = precision_recall_curve(y_val, y_proba)
    
    # Calculer F1 pour chaque seuil
    f1_scores = 2 * (precisions * recalls) / (precisions + recalls + 1e-10)
    
    # Trouver le meilleur seuil
    best_idx = np.argmax(f1_scores[:-1])  # Exclure le dernier (seuil=1)
    best_threshold = thresholds[best_idx]
    
    return best_threshold


def evaluate_with_threshold(model, X_test, y_test, threshold=0.5):
    """Évalue avec un seuil personnalisé"""
    y_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_proba >= threshold).astype(int)
    
    return {
        'accuracy': accuracy_score(y_test, y_pred),
        'f1': f1_score(y_test, y_pred),
        'precision': precision_score(y_test, y_pred),
        'recall': recall_score(y_test, y_pred),
        'roc_auc': roc_auc_score(y_test, y_proba),
        'threshold': threshold
    }


# =============================================================================
# ENTRAÎNEMENT AVANCÉ
# =============================================================================

def train_optimized_gb(X_train, y_train, X_val, y_val, X_test, y_test, selected_features):
    """GradientBoosting avec optimisation complète"""
    print("\n" + "=" * 60)
    print("  GRADIENT BOOSTING OPTIMISÉ")
    print("=" * 60)
    
    X_train_sel = X_train[selected_features]
    X_val_sel = X_val[selected_features]
    X_test_sel = X_test[selected_features]
    
    # SMOTE
    X_train_bal, y_train_bal = apply_smote(X_train_sel, y_train)
    
    # Entraînement avec early stopping simulé via validation
    params = {
        'n_estimators': 300,
        'max_depth': 4,
        'learning_rate': 0.02,
        'min_samples_split': 20,
        'min_samples_leaf': 10,
        'subsample': 0.8,
        'max_features': 0.6,
        'random_state': CONFIG['random_state'],
        'validation_fraction': 0.1,
        'n_iter_no_change': 20
    }
    
    print(f"\n   📊 Entraînement...")
    model = GradientBoostingClassifier(**params)
    model.fit(X_train_bal, y_train_bal)
    
    # Trouver seuil optimal
    threshold = find_optimal_threshold(model, X_val_sel, y_val)
    print(f"   🎯 Seuil optimal: {threshold:.3f}")
    
    # Évaluation
    metrics = evaluate_with_threshold(model, X_test_sel, y_test, threshold)
    
    print(f"\n   📈 Résultats (seuil={threshold:.2f}):")
    print(f"      Accuracy: {metrics['accuracy']:.1%}")
    print(f"      F1: {metrics['f1']:.3f}")
    print(f"      Precision: {metrics['precision']:.1%}")
    print(f"      Recall: {metrics['recall']:.1%}")
    print(f"      ROC AUC: {metrics['roc_auc']:.3f}")
    
    return model, metrics, selected_features


def train_optimized_xgb(X_train, y_train, X_val, y_val, X_test, y_test, selected_features):
    """XGBoost avec optimisation complète"""
    print("\n" + "=" * 60)
    print("  XGBOOST OPTIMISÉ")
    print("=" * 60)
    
    X_train_sel = X_train[selected_features]
    X_val_sel = X_val[selected_features]
    X_test_sel = X_test[selected_features]
    
    # SMOTE
    X_train_bal, y_train_bal = apply_smote(X_train_sel, y_train)
    
    # Calculer scale_pos_weight
    neg_count = (y_train_bal == 0).sum()
    pos_count = (y_train_bal == 1).sum()
    scale_pos_weight = neg_count / pos_count if pos_count > 0 else 1.0
    
    params = {
        'n_estimators': 200,
        'max_depth': 4,
        'learning_rate': 0.03,
        'min_child_weight': 5,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'reg_alpha': 0.1,
        'reg_lambda': 1.0,
        'gamma': 0.05,
        'scale_pos_weight': scale_pos_weight,
        'random_state': CONFIG['random_state'],
        'use_label_encoder': False,
        'eval_metric': 'auc',
        'early_stopping_rounds': 30
    }
    
    print(f"\n   📊 Entraînement...")
    model = xgb.XGBClassifier(**params)
    model.fit(
        X_train_bal, y_train_bal,
        eval_set=[(X_val_sel, y_val)],
        verbose=False
    )
    
    # Trouver seuil optimal
    threshold = find_optimal_threshold(model, X_val_sel, y_val)
    print(f"   🎯 Seuil optimal: {threshold:.3f}")
    
    # Évaluation
    metrics = evaluate_with_threshold(model, X_test_sel, y_test, threshold)
    
    print(f"\n   📈 Résultats (seuil={threshold:.2f}):")
    print(f"      Accuracy: {metrics['accuracy']:.1%}")
    print(f"      F1: {metrics['f1']:.3f}")
    print(f"      Precision: {metrics['precision']:.1%}")
    print(f"      Recall: {metrics['recall']:.1%}")
    print(f"      ROC AUC: {metrics['roc_auc']:.3f}")
    
    return model, metrics, selected_features


def train_ensemble(X_train, y_train, X_val, y_val, X_test, y_test, selected_features):
    """Ensemble Voting de plusieurs modèles"""
    if not CONFIG['use_ensemble']:
        return None, None, None
    
    print("\n" + "=" * 60)
    print("  ENSEMBLE VOTING")
    print("=" * 60)
    
    X_train_sel = X_train[selected_features]
    X_val_sel = X_val[selected_features]
    X_test_sel = X_test[selected_features]
    
    # SMOTE
    X_train_bal, y_train_bal = apply_smote(X_train_sel, y_train)
    
    # Modèles de base
    estimators = [
        ('gb', GradientBoostingClassifier(
            n_estimators=150, max_depth=3, learning_rate=0.03,
            random_state=CONFIG['random_state']
        )),
        ('xgb', xgb.XGBClassifier(
            n_estimators=150, max_depth=3, learning_rate=0.03,
            use_label_encoder=False, eval_metric='logloss',
            random_state=CONFIG['random_state']
        )),
        ('rf', RandomForestClassifier(
            n_estimators=150, max_depth=5, min_samples_leaf=10,
            random_state=CONFIG['random_state']
        )),
        ('lr', LogisticRegression(
            max_iter=1000, random_state=CONFIG['random_state']
        ))
    ]
    
    print(f"\n   📊 Entraînement de {len(estimators)} modèles...")
    
    # Voting classifier
    ensemble = VotingClassifier(
        estimators=estimators,
        voting='soft'  # Moyenne des probabilités
    )
    
    ensemble.fit(X_train_bal, y_train_bal)
    
    # Trouver seuil optimal
    threshold = find_optimal_threshold(ensemble, X_val_sel, y_val)
    print(f"   🎯 Seuil optimal: {threshold:.3f}")
    
    # Évaluation
    metrics = evaluate_with_threshold(ensemble, X_test_sel, y_test, threshold)
    
    print(f"\n   📈 Résultats Ensemble (seuil={threshold:.2f}):")
    print(f"      Accuracy: {metrics['accuracy']:.1%}")
    print(f"      F1: {metrics['f1']:.3f}")
    print(f"      Precision: {metrics['precision']:.1%}")
    print(f"      Recall: {metrics['recall']:.1%}")
    print(f"      ROC AUC: {metrics['roc_auc']:.3f}")
    
    return ensemble, metrics, selected_features


def train_high_precision(X_train, y_train, X_val, y_val, X_test, y_test, selected_features):
    """Modèle optimisé pour haute précision (moins de faux positifs)"""
    print("\n" + "=" * 60)
    print("  MODÈLE HAUTE PRÉCISION")
    print("=" * 60)
    
    X_train_sel = X_train[selected_features]
    X_val_sel = X_val[selected_features]
    X_test_sel = X_test[selected_features]
    
    # Pas de SMOTE - on veut des prédictions conservatrices
    
    params = {
        'n_estimators': 200,
        'max_depth': 3,
        'learning_rate': 0.02,
        'min_child_weight': 10,
        'subsample': 0.7,
        'colsample_bytree': 0.6,
        'reg_alpha': 0.5,
        'reg_lambda': 2.0,
        'gamma': 0.2,
        'random_state': CONFIG['random_state'],
        'use_label_encoder': False,
        'eval_metric': 'auc'
    }
    
    print(f"\n   📊 Entraînement (mode conservateur)...")
    model = xgb.XGBClassifier(**params)
    model.fit(X_train_sel, y_train, verbose=False)
    
    # Seuil élevé pour haute précision
    y_proba = model.predict_proba(X_val_sel)[:, 1]
    
    # Trouver le seuil qui donne précision >= 60%
    for threshold in np.arange(0.5, 0.9, 0.05):
        y_pred = (y_proba >= threshold).astype(int)
        if y_pred.sum() > 0:
            prec = precision_score(y_val, y_pred)
            if prec >= 0.55:
                break
    
    print(f"   🎯 Seuil haute précision: {threshold:.2f}")
    
    # Évaluation
    metrics = evaluate_with_threshold(model, X_test_sel, y_test, threshold)
    
    print(f"\n   📈 Résultats (seuil={threshold:.2f}):")
    print(f"      Accuracy: {metrics['accuracy']:.1%}")
    print(f"      F1: {metrics['f1']:.3f}")
    print(f"      Precision: {metrics['precision']:.1%}")
    print(f"      Recall: {metrics['recall']:.1%}")
    print(f"      ROC AUC: {metrics['roc_auc']:.3f}")
    
    # Calculer les stats de trading
    y_proba_test = model.predict_proba(X_test_sel)[:, 1]
    y_pred_test = (y_proba_test >= threshold).astype(int)
    n_trades = y_pred_test.sum()
    if n_trades > 0:
        win_rate = y_test[y_pred_test == 1].mean()
        print(f"\n   💰 Stats Trading:")
        print(f"      Trades signalés: {n_trades}/{len(y_test)} ({n_trades/len(y_test)*100:.1f}%)")
        print(f"      Win rate sur trades signalés: {win_rate:.1%}")
    
    return model, metrics, selected_features


# =============================================================================
# SAUVEGARDE
# =============================================================================

def save_best_model(model, metrics, features, model_name):
    """Sauvegarde le meilleur modèle"""
    models_dir = CONFIG['models_dir']
    os.makedirs(models_dir, exist_ok=True)
    
    # Modèle
    model_path = os.path.join(models_dir, f"{model_name}_best.pkl")
    with open(model_path, 'wb') as f:
        pickle.dump({
            'model': model,
            'threshold': metrics.get('threshold', 0.5),
            'features': features
        }, f)
    
    # Métadonnées
    meta = {
        'model_name': model_name,
        'trained_at': datetime.now().isoformat(),
        'metrics': metrics,
        'n_features': len(features),
        'features': features[:10]  # Top 10 seulement
    }
    
    meta_path = os.path.join(models_dir, f"{model_name}_best_metadata.json")
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2, default=str)
    
    print(f"   💾 Sauvegardé: {model_path}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    start_time = time.time()
    
    try:
        # 1. Charger et préparer
        X_train, y_train, X_val, y_val, X_test, y_test, feature_cols = load_and_prepare_data()
        
        # 2. Sélection features
        print("\n" + "-" * 60)
        print("2. SÉLECTION DES FEATURES")
        print("-" * 60)
        selected_features = select_features(X_train, y_train, feature_cols, CONFIG['max_features'])
        print(f"   ✅ {len(selected_features)} features sélectionnées")
        
        results = {}
        
        # 3. Entraîner les modèles
        
        # GradientBoosting optimisé
        gb_model, gb_metrics, _ = train_optimized_gb(
            X_train, y_train, X_val, y_val, X_test, y_test, selected_features
        )
        results['GradientBoosting'] = gb_metrics
        save_best_model(gb_model, gb_metrics, selected_features, 'gradient_boosting')
        
        # XGBoost optimisé
        xgb_model, xgb_metrics, _ = train_optimized_xgb(
            X_train, y_train, X_val, y_val, X_test, y_test, selected_features
        )
        results['XGBoost'] = xgb_metrics
        save_best_model(xgb_model, xgb_metrics, selected_features, 'xgboost')
        
        # Ensemble
        ens_model, ens_metrics, _ = train_ensemble(
            X_train, y_train, X_val, y_val, X_test, y_test, selected_features
        )
        if ens_model:
            results['Ensemble'] = ens_metrics
            save_best_model(ens_model, ens_metrics, selected_features, 'ensemble')
        
        # Haute précision
        hp_model, hp_metrics, _ = train_high_precision(
            X_train, y_train, X_val, y_val, X_test, y_test, selected_features
        )
        results['HighPrecision'] = hp_metrics
        save_best_model(hp_model, hp_metrics, selected_features, 'high_precision')
        
        # 4. Comparaison finale
        print("\n" + "=" * 90)
        print("  COMPARAISON FINALE")
        print("=" * 90)
        
        print(f"\n   {'Modèle':<20} {'Accuracy':<12} {'F1':<10} {'Precision':<12} {'Recall':<10} {'AUC':<10}")
        print("-" * 85)
        
        best_model = None
        best_f1 = 0
        
        for name, metrics in results.items():
            print(f"   {name:<20} {metrics['accuracy']:.1%}{'':>4} {metrics['f1']:.3f}{'':>4} {metrics['precision']:.1%}{'':>4} {metrics['recall']:.1%}{'':>4} {metrics['roc_auc']:.3f}")
            
            if metrics['f1'] > best_f1:
                best_f1 = metrics['f1']
                best_model = name
        
        print(f"\n   🏆 Meilleur modèle: {best_model} (F1={best_f1:.3f})")
        
        # 5. Recommandations
        print("\n" + "=" * 90)
        print("  RECOMMANDATIONS")
        print("=" * 90)
        
        best_precision_model = max(results.items(), key=lambda x: x[1]['precision'])
        best_recall_model = max(results.items(), key=lambda x: x[1]['recall'])
        
        print(f"""
   📋 Utilisation recommandée:
   
   1. Pour MINIMISER les faux positifs (précision):
      → Utiliser {best_precision_model[0]} (Précision={best_precision_model[1]['precision']:.1%})
      
   2. Pour NE PAS RATER d'opportunités (recall):
      → Utiliser {best_recall_model[0]} (Recall={best_recall_model[1]['recall']:.1%})
      
   3. Pour un ÉQUILIBRE (F1):
      → Utiliser {best_model} (F1={best_f1:.3f})
      
   💡 Conseil: Avec seulement {len(X_train)} trades d'entraînement,
      les performances sont limitées. Continuer à collecter des données.
""")
        
        total_time = time.time() - start_time
        print(f"\n   ⏱️  Temps total: {total_time:.1f}s")
        
        return results
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    results = main()
