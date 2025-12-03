"""
ML Models - Model management, features analysis, and experiments
Migrated from ml_legacy.py as part of Phase 5 modularization
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)

# Router for models and features
router = APIRouter(prefix="/api/ml", tags=["ML Models"])


@router.get("/models/overview")
async def get_models_overview():
    """
    Vue d'ensemble des modèles ML disponibles avec leurs métriques
    """
    try:
        import json
        from pathlib import Path
        
        models_dir = Path("optimization/saved_models")
        models = []
        
        # Charger les métadonnées du modèle xgboost_v1
        metadata_file = models_dir / "xgboost_v1_metadata.json"
        
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            # Calculer overfitting gap
            metrics = metadata.get('metrics', {})
            train_acc = metrics.get('train', {}).get('accuracy', 0)
            test_acc = metrics.get('test', {}).get('accuracy', 0)
            overfitting_gap = (train_acc - test_acc) * 100 if train_acc and test_acc else 0

            # Quelques anciennes metadata n'ont pas dataset_info, on retombe sur training_info
            dataset_info = metadata.get('dataset_info') or {}
            if not dataset_info:
                training_info = metadata.get('training_info', {})
                dataset_info = {
                    'total_samples': training_info.get('total_samples'),
                    'train_samples': training_info.get('train_samples'),
                    'test_samples': training_info.get('test_samples'),
                    'timeframe_days': training_info.get('timeframe_days')
                }
            
            models.append({
                'name': 'xgboost_v1',
                'type': 'XGBoost Classifier',
                'version': metadata.get('version', '1.0'),
                'trained_at': metadata.get('timestamp') or metadata.get('training_info', {}).get('trained_at'),
                'metrics': metrics,
                'overfitting_gap': round(overfitting_gap, 1),
                'dataset_info': dataset_info,
                'hyperparameters': metadata.get('hyperparameters', {}),
                'feature_count': metadata.get('n_features', 0),
                'is_active': True
            })
        else:
            # Pas de modèle entraîné
            models.append({
                'name': 'xgboost_v1',
                'type': 'XGBoost Classifier',
                'version': '1.0',
                'trained_at': None,
                'metrics': {
                    'test': {'accuracy': 0, 'roc_auc': 0},
                    'train': {'accuracy': 0}
                },
                'overfitting_gap': 0,
                'dataset_info': {'total_samples': 0},
                'hyperparameters': {},
                'feature_count': 0,
                'is_active': False
            })
        
        # 🔥 FIX: Charger aussi le modèle GradientBoosting
        gb_metadata_file = models_dir / "best_classifier_metadata.json"
        
        if gb_metadata_file.exists():
            with open(gb_metadata_file, 'r') as f:
                gb_metadata = json.load(f)
            
            # Extraire les métriques avec les bons noms de clés
            gb_metrics = gb_metadata.get('metrics', {})
            
            # 🔧 Utiliser les clés correctes du fichier metadata
            train_acc = gb_metrics.get('train_accuracy', 0)
            test_acc = gb_metrics.get('test_accuracy', 0)
            
            # Overfitting déjà calculé ou recalculer
            overfitting_gap = gb_metrics.get('overfitting', 0)
            if overfitting_gap == 0 and train_acc and test_acc:
                overfitting_gap = train_acc - test_acc
            overfitting_gap_pct = overfitting_gap * 100 if overfitting_gap < 1 else overfitting_gap
            
            # 🔬 Utiliser les métriques test (CV si disponible)
            cv_accuracy = gb_metrics.get('cv_accuracy_mean', test_acc)
            cv_f1 = gb_metrics.get('cv_f1_mean', gb_metrics.get('f1_score', 0))
            cv_std = gb_metrics.get('cv_accuracy_std', 0)
            
            # Métriques directes
            f1_score = gb_metrics.get('f1_score', cv_f1)
            precision = gb_metrics.get('precision', 0)
            
            # Convertir au format attendu par le frontend
            models.append({
                'name': 'best_classifier',  # Nom cherché par le frontend
                'type': gb_metadata.get('model_type', 'GradientBoostingClassifier'),
                'model_type': gb_metadata.get('model_type', 'gb'),
                'version': '2.0',
                'trained_at': gb_metadata.get('timestamp'),
                'metrics': {
                    'test': {
                        # Métriques principales (holdout test)
                        'accuracy': test_acc,
                        'accuracy_std': cv_std,
                        'f1_score': f1_score,
                        'precision': precision,
                        # CV pour référence
                        'cv_accuracy': cv_accuracy,
                        'cv_f1': cv_f1
                    },
                    'train': {
                        'accuracy': train_acc
                    }
                },
                'overfitting_gap': round(overfitting_gap_pct, 1),
                'dataset_info': {
                    'total_samples': gb_metadata.get('n_samples', 0) or gb_metadata.get('comparison_vs_baseline', {}).get('n_samples', 1328),
                    'n_features': gb_metadata.get('n_features', 20)
                },
                'hyperparameters': gb_metadata.get('params', {}),
                'feature_count': gb_metadata.get('n_features', 20),
                'feature_names': gb_metadata.get('feature_names', []),
                'is_active': True
            })
        
        # Déterminer le modèle actif (préférer GB s'il existe)
        active_model = None
        for m in models:
            if m.get('is_active'):
                active_model = m['name']
                if m['name'] == 'best_classifier':
                    break  # Préférer GB
        
        return {
            'models': models,
            'total_models': len(models),
            'active_model': active_model,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_models_overview: {e}", exc_info=True)
        return JSONResponse({'error': str(e)}, status_code=500)


# ========== FEATURES ==========

@router.get("/features/importance")
async def get_feature_importance(
    method: str = Query('correlation', regex='^(correlation|mutual_info)$'),
    n_features: int = 20,
    min_trades: int = 30
):
    """
    Feature importance
    - Corrélation avec target
    - Mutual information
    """
    try:
        from optimization.data.feature_loader import load_features_from_postgres, get_trades_count
        from optimization.data.feature_engineering import calculate_derived_features, select_top_features
        
        trades_count = get_trades_count()
        
        if trades_count < min_trades:
            raise HTTPException(
                400, 
                f"Pas assez de données: {trades_count}/{min_trades} trades requis"
            )
        
        # Charger et engineer features
        df = load_features_from_postgres(min_trades=min_trades)
        df_eng = calculate_derived_features(df)
        
        # Sélectionner top features
        top_features = select_top_features(
            df_eng,
            target_col='target_win',
            n_features=n_features,
            method=method
        )
        
        # Calculer scores
        feature_scores = []
        for i, feature_name in enumerate(top_features):
            if method == 'correlation':
                score = abs(df_eng[feature_name].corr(df_eng['target_win']))
            else:
                score = 0.0  # mutual_info calculé dans select_top_features
            
            feature_scores.append({
                'rank': i + 1,
                'name': feature_name,
                'importance': float(score) if not pd.isna(score) else 0.0
            })
        
        return {
            'method': method,
            'trades_count': len(df),
            'confidence': 'low' if len(df) < 100 else 'medium' if len(df) < 200 else 'high',
            'features': feature_scores,
            'timestamp': datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur get_feature_importance: {e}", exc_info=True)
        return JSONResponse({'error': str(e)}, status_code=500)


@router.get("/features/correlation_matrix")
async def get_correlation_matrix(
    n_features: int = 15,
    min_trades: int = 30
):
    """
    Matrice de corrélation entre top features
    """
    try:
        from optimization.data.feature_loader import load_features_from_postgres
        from optimization.data.feature_engineering import calculate_derived_features, select_top_features
        
        df = load_features_from_postgres(min_trades=min_trades)
        df_eng = calculate_derived_features(df)
        
        # Top features
        top_features = select_top_features(df_eng, n_features=n_features, method='correlation')
        
        # Matrice corrélation
        corr_matrix = df_eng[top_features].corr()
        
        # Convertir en format JSON
        matrix_data = []
        for i, feat1 in enumerate(top_features):
            for j, feat2 in enumerate(top_features):
                matrix_data.append({
                    'feature1': feat1,
                    'feature2': feat2,
                    'correlation': float(corr_matrix.iloc[i, j])
                })
        
        return {
            'features': top_features,
            'matrix': matrix_data,
            'trades_count': len(df)
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_correlation_matrix: {e}", exc_info=True)
        return JSONResponse({'error': str(e)}, status_code=500)


# ========== MODELS ==========

@router.get("/models/status")
async def get_models_status():
    """
    État de tous les modèles ML
    """
    try:
        import os
        from optimization.data.feature_loader import get_ml_readiness
        
        readiness = get_ml_readiness()
        
        # Vérifier fichiers modèles
        models_dir = "optimization/saved_models"
        
        models_status = {
            'xgboost': {
                **readiness['xgboost'],
                'trained': os.path.exists(f"{models_dir}/xgboost_v1.pkl"),
                'model_file': f"{models_dir}/xgboost_v1.pkl"
            },
            'gru': {
                **readiness['gru'],
                'trained': os.path.exists(f"{models_dir}/gru_v1.h5"),
                'model_file': f"{models_dir}/gru_v1.h5"
            },
            'ppo': {
                **readiness['ppo'],
                'trained': os.path.exists(f"{models_dir}/ppo_v1.zip"),
                'model_file': f"{models_dir}/ppo_v1.zip"
            }
        }
        
        return {
            'models': models_status,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_models_status: {e}", exc_info=True)
        return JSONResponse({'error': str(e)}, status_code=500)


@router.get("/models/metrics/{model_name}")
async def get_model_metrics(model_name: str):
    """
    Récupère les métriques détaillées d'un modèle entraîné
    
    Args:
        model_name: Nom du modèle (ex: xgboost_v1, gru_v1)
    
    Returns:
        Métriques complètes: train/test performance, feature importance, confusion matrix
    """
    try:
        import os
        import json
        
        # Chemin vers metadata
        metadata_path = f"optimization/saved_models/{model_name}_metadata.json"
        
        if not os.path.exists(metadata_path):
            raise HTTPException(
                status_code=404,
                detail=f"Modèle '{model_name}' non trouvé. Entraînez d'abord le modèle."
            )
        
        # Charger metadata
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        # Extraire métriques clés
        metrics = metadata.get('metrics', {})
        feature_importance = metadata.get('feature_importance') or []
        training_info = metadata.get('training_info', {})

        # Fallback: si aucune importance n'est stockée, utiliser feature_names
        if not feature_importance:
            feature_names = metadata.get('feature_names') or metadata.get('selected_features') or []
            if feature_names:
                default_weight = 1 / len(feature_names)
                feature_importance = [
                    {
                        'feature': name,
                        'importance': default_weight
                    }
                    for name in feature_names
                ]

        # Top features (limiter à 10)
        top_features = [
            {
                'feature': f['feature'],
                'importance': round(f['importance'] * 100, 2)  # En pourcentage
            }
            for f in feature_importance[:10]
            if f['importance'] > 0
        ]
        
        # Calculer overfitting score
        train_acc = metrics.get('train', {}).get('accuracy', 0)
        test_acc = metrics.get('test', {}).get('accuracy', 0)
        overfitting_gap = train_acc - test_acc
        
        # Évaluation qualité
        quality_assessment = {
            'overfitting': 'high' if overfitting_gap > 0.2 else 'moderate' if overfitting_gap > 0.1 else 'low',
            'test_performance': 'good' if test_acc > 0.7 else 'acceptable' if test_acc > 0.6 else 'poor',
            'data_sufficiency': 'sufficient' if training_info.get('total_samples', 0) > 200 else 'limited'
        }
        
        return {
            'model_name': model_name,
            'model_type': metadata.get('model_type'),
            'version': metadata.get('version'),
            'trained_at': training_info.get('trained_at'),
            'training_info': {
                'total_samples': training_info.get('total_samples'),
                'train_samples': training_info.get('train_samples'),
                'test_samples': training_info.get('test_samples'),
                'timeframe_days': training_info.get('timeframe_days'),
                'training_time_seconds': round(training_info.get('training_time_seconds', 0), 2)
            },
            'performance': {
                'train': {
                    'accuracy': round(metrics.get('train', {}).get('accuracy', 0), 3),
                    'f1': round(metrics.get('train', {}).get('f1', 0), 3),
                    'roc_auc': round(metrics.get('train', {}).get('roc_auc', 0), 3)
                },
                'test': {
                    'accuracy': round(metrics.get('test', {}).get('accuracy', 0), 3),
                    'precision': round(metrics.get('test', {}).get('precision', 0), 3),
                    'recall': round(metrics.get('test', {}).get('recall', 0), 3),
                    'f1': round(metrics.get('test', {}).get('f1', 0), 3),
                    'roc_auc': round(metrics.get('test', {}).get('roc_auc', 0), 3)
                },
                'overfitting_gap': round(overfitting_gap, 3)
            },
            'confusion_matrix': metrics.get('confusion_matrix'),
            'top_features': top_features,
            'quality_assessment': quality_assessment,
            'recommendations': _generate_recommendations(
                test_acc, 
                overfitting_gap, 
                training_info.get('total_samples', 0),
                len([f for f in feature_importance if f['importance'] == 0])
            )
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur get_model_metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _generate_recommendations(test_acc: float, overfitting_gap: float, total_samples: int, zero_importance_count: int) -> list:
    """Génère recommandations basées sur métriques"""
    recommendations = []
    
    if total_samples < 100:
        recommendations.append({
            'type': 'data',
            'priority': 'high',
            'message': f'Dataset trop petit ({total_samples} samples). Collectez au moins 200 trades pour améliorer la généralisation.'
        })
    
    if overfitting_gap > 0.2:
        recommendations.append({
            'type': 'model',
            'priority': 'high',
            'message': f'Overfitting détecté (gap: {overfitting_gap:.1%}). Réduisez max_depth ou augmentez les données.'
        })
    
    if test_acc < 0.65:
        recommendations.append({
            'type': 'performance',
            'priority': 'medium',
            'message': f'Performance test faible ({test_acc:.1%}). Essayez feature engineering ou plus de données.'
        })
    
    if zero_importance_count > 50:
        recommendations.append({
            'type': 'features',
            'priority': 'low',
            'message': f'{zero_importance_count} features inutiles. Implémentez feature selection pour accélérer l\'entraînement.'
        })
    
    if not recommendations:
        recommendations.append({
            'type': 'success',
            'priority': 'info',
            'message': 'Modèle en bonne santé. Continuez à collecter des données pour améliorer.'
        })
    
    return recommendations


@router.get("/models/experiments")
async def get_experiments(limit: int = 10):
    """
    Liste des expériences ML (tracking)
    """
    try:
        # TODO: Implémenter table experiments dans PostgreSQL
        # Pour l'instant, retour mock
        return {
            'experiments': [],
            'total': 0,
            'message': 'Experiments tracking coming soon'
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_experiments: {e}", exc_info=True)
        return JSONResponse({'error': str(e)}, status_code=500)


# ========== PREDICTIONS ==========


logger.info("✅ ML models router initialized (6 routes)")
