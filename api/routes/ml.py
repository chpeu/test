"""
API Routes ML - Endpoints pour Machine Learning
Dashboard, Features, Models, Backtesting, Live Predictions
"""

import asyncio
import copy
import json
import logging
import os
import threading
from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Body
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
import pandas as pd
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

# Router ML
router = APIRouter(prefix="/api/ml", tags=["ML"])


@router.get("/optimize/summary")
async def get_metric_summary():
    """Renvoyer la dernière optimisation disponible pour chaque métrique."""
    snapshot = get_metric_runs_snapshot()
    metrics_map = snapshot.get("metrics", {})
    for metric in METRIC_OPTIONS:
        metrics_map.setdefault(metric, {"metric": metric, "last_run": None})
    return {"metrics": metrics_map}

# State global pour tracking tasks
ml_tasks = {}

METRIC_OPTIONS = ["trading_composite", "f1_score", "accuracy", "roc_auc"]

LAST_RUNS_FILE = Path("data/optuna_last_runs.json")
_metric_cache_lock = threading.Lock()
metric_runs_cache = {"metrics": {}}


def _load_metric_runs_cache():
    global metric_runs_cache
    if LAST_RUNS_FILE.exists():
        try:
            with LAST_RUNS_FILE.open('r') as f:
                metric_runs_cache = json.load(f)
        except Exception as e:
            logger.warning(f"⚠️ Impossible de charger {LAST_RUNS_FILE}: {e}")
            metric_runs_cache = {"metrics": {}}
    else:
        metric_runs_cache = {"metrics": {}}


def _save_metric_runs_cache():
    LAST_RUNS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LAST_RUNS_FILE.open('w') as f:
        json.dump(metric_runs_cache, f, indent=2)


def record_metric_run(metric: str, run_data: Dict[str, Any]):
    """Enregistrer la dernière optimisation et le record global pour chaque métrique."""
    if not metric:
        return
    with _metric_cache_lock:
        metrics_map = metric_runs_cache.setdefault("metrics", {})
        metrics_map[metric] = {
            'metric': metric,
            'last_run': {**run_data, 'metric': metric, 'source': 'latest'}
        }
        _save_metric_runs_cache()


def get_metric_runs_snapshot() -> Dict[str, Any]:
    with _metric_cache_lock:
        return copy.deepcopy(metric_runs_cache)


_load_metric_runs_cache()


# ========== HELPERS ==========

def get_ml_task_status(task_id: str) -> Dict:
    """Récupère status d'une tâche ML"""
    return ml_tasks.get(task_id, {'status': 'unknown', 'task_id': task_id})


# ========== DASHBOARD ==========

@router.get("/dashboard/stats")
async def get_ml_dashboard_stats():
    """
    Stats globales ML pour dashboard
    - Progression collecte données
    - Qualité données
    - Modèles débloqués
    """
    try:
        from optimization.data.feature_loader import get_trades_count, get_ml_readiness, get_feature_statistics
        
        # Compter trades
        trades_count = get_trades_count(completed_only=True)
        
        # Readiness pour chaque modèle
        readiness = get_ml_readiness()
        
        # Stats features
        feature_stats = get_feature_statistics(timeframe_days=30)
        
        # Calculer progression
        milestones = {
            'exploratory': 10,
            'features': 30,
            'xgboost': 50,
            'gru': 200,
            'ppo': 500
        }
        
        # Next milestone
        next_milestone = None
        for name, threshold in milestones.items():
            if trades_count < threshold:
                next_milestone = {
                    'name': name,
                    'threshold': threshold,
                    'remaining': threshold - trades_count,
                    'progress_pct': (trades_count / threshold) * 100
                }
                break
        
        if next_milestone is None:
            next_milestone = {
                'name': 'production',
                'threshold': 1000,
                'remaining': max(0, 1000 - trades_count),
                'progress_pct': min(100, (trades_count / 1000) * 100)
            }
        
        return {
            'trades_count': trades_count,
            'target_trades': 500,
            'progress_pct': min(100, (trades_count / 500) * 100),
            'readiness': readiness,
            'next_milestone': next_milestone,
            'feature_stats': feature_stats,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_ml_dashboard_stats: {e}", exc_info=True)
        return JSONResponse({
            'error': str(e),
            'trades_count': 0,
            'readiness': {}
        }, status_code=500)


@router.get("/dashboard/data_quality")
async def get_data_quality():
    """
    Analyse qualité des données
    - Complétude
    - Distribution win/loss
    - Missing values
    """
    try:
        from optimization.data.feature_loader import load_features_from_postgres, get_trades_count
        
        trades_count = get_trades_count()
        
        if trades_count < 10:
            return {
                'status': 'insufficient_data',
                'trades_count': trades_count,
                'message': 'Minimum 10 trades requis pour analyse qualité'
            }
        
        # Charger features
        df = load_features_from_postgres(min_trades=10, timeframe_days=30)
        
        # Distribution win/loss
        win_count = (df['target_win'] == True).sum()
        loss_count = (df['target_win'] == False).sum()
        win_rate = win_count / (win_count + loss_count) if (win_count + loss_count) > 0 else 0
        
        # 🔥 FIX: Exclure IDs, métadonnées et config de l'analyse de qualité
        exclude_from_quality = [
            'scan_id', 'timestamp', 'symbol',  # IDs et métadonnées
            'opportunity_direction', 'reject_reason_category',  # Catégorielles (non-numériques)
            'target_win', 'target_pnl', 'is_opportunity',  # Targets (pas des features)
            # Config parameters (variance nulle intentionnelle - paramètres fixes)
            'config_min_score_required', 'config_snr_threshold',
            'config_atr_min_1m', 'config_atr_max_1m',
            'config_atr_min_5m', 'config_atr_max_5m',
            'config_volume_multiplier', 'config_use_confluence',
            # Filtres booléens (variance naturellement faible - 0/1 seulement)
            'snr_passed_1m', 'snr_passed_5m',
            'breakout_passed_1m', 'breakout_passed_5m',
            'wick_passed_1m', 'wick_passed_5m',
            'atr_optimal_passed_1m', 'atr_optimal_passed_5m',
            'volume_filter_passed_1m', 'volume_filter_passed_5m',
        ]
        
        # Missing values (features uniquement)
        feature_cols = [col for col in df.columns if col not in exclude_from_quality]
        missing_pct = (df[feature_cols].isnull().sum() / len(df) * 100).to_dict()
        high_missing = {k: v for k, v in missing_pct.items() if v > 10}
        
        # Features avec variance (features uniquement)
        numeric_cols = [col for col in df.select_dtypes(include=['float64', 'int64']).columns 
                       if col not in exclude_from_quality]
        low_variance = []
        for col in numeric_cols:
            if df[col].std() < 0.01:
                low_variance.append(col)
        
        quality_score = 100
        if high_missing:
            quality_score -= len(high_missing) * 5
        if win_rate < 0.3 or win_rate > 0.7:
            quality_score -= 10
        if low_variance:
            quality_score -= len(low_variance) * 2
        
        return {
            'trades_count': len(df),
            'win_loss_distribution': {
                'wins': int(win_count),
                'losses': int(loss_count),
                'win_rate': float(win_rate),
                'balanced': bool(0.4 <= win_rate <= 0.6)
            },
            'missing_values': {
                'high_missing_features': high_missing,
                'total_features_with_missing': len([v for v in missing_pct.values() if v > 0])
            },
            'variance': {
                'low_variance_features': low_variance,
                'count': len(low_variance)
            },
            'quality_score': max(0, min(100, quality_score)),
            'status': 'good' if quality_score >= 80 else 'acceptable' if quality_score >= 60 else 'poor'
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_data_quality: {e}", exc_info=True)
        return JSONResponse({'error': str(e)}, status_code=500)


# ========== EXPLORATORY ==========

@router.get("/exploratory/performance")
async def get_performance_analysis(
    group_by: str = Query('hour', regex='^(hour|day|symbol|direction)$'),
    timeframe_days: int = 30
):
    """
    Analyse performance par contexte
    - Par heure de la journée
    - Par jour de la semaine
    - Par symbole
    - Par direction
    """
    try:
        from optimization.data.feature_loader import load_features_from_postgres
        
        df = load_features_from_postgres(min_trades=10, timeframe_days=timeframe_days)
        
        # Ajouter colonnes temporelles si pas déjà présentes
        if 'timestamp' in df.columns:
            df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
            df['day_of_week'] = pd.to_datetime(df['timestamp']).dt.day_name()
        
        # Grouper selon paramètre
        if group_by == 'hour' and 'hour' in df.columns:
            grouped = df.groupby('hour')['target_win'].agg(['sum', 'count', 'mean'])
            grouped.columns = ['wins', 'total', 'win_rate']
            results = grouped.to_dict('index')
            
        elif group_by == 'day' and 'day_of_week' in df.columns:
            grouped = df.groupby('day_of_week')['target_win'].agg(['sum', 'count', 'mean'])
            grouped.columns = ['wins', 'total', 'win_rate']
            results = grouped.to_dict('index')
            
        elif group_by == 'symbol' and 'symbol' in df.columns:
            grouped = df.groupby('symbol')['target_win'].agg(['sum', 'count', 'mean'])
            grouped.columns = ['wins', 'total', 'win_rate']
            results = grouped.to_dict('index')
            
        else:
            results = {}
        
        return {
            'group_by': group_by,
            'timeframe_days': timeframe_days,
            'results': results,
            'total_trades': len(df)
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_performance_analysis: {e}", exc_info=True)
        return JSONResponse({'error': str(e)}, status_code=500)


# ========== MODELS ==========

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
        
        return {
            'models': models,
            'total_models': len(models),
            'active_model': 'xgboost_v1' if models[0]['is_active'] else None,
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
        feature_importance = metadata.get('feature_importance', [])
        training_info = metadata.get('training_info', {})
        
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

@router.get("/predictions/analytics")
async def get_predictions_analytics(
    model_name: Optional[str] = None,
    days: int = Query(30, ge=1, le=365)
):
    """
    Récupérer analytics des prédictions ML
    
    Args:
        model_name: Filtrer par modèle (optionnel)
        days: Nombre de jours à analyser
        
    Returns:
        Analytics: accuracy, trades exécutés, PnL moyen, etc.
    """
    try:
        from optimization.prediction_logger import get_prediction_analytics, get_best_symbols_for_ml
        
        analytics = get_prediction_analytics(model_name, days)
        best_symbols = get_best_symbols_for_ml(min_predictions=3)
        
        return {
            'analytics': analytics,
            'best_symbols': best_symbols,
            'period_days': days,
            'model_name': model_name
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_predictions_analytics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/predictions/recent")
async def get_recent_predictions(limit: int = Query(20, ge=1, le=100)):
    """
    Récupérer les prédictions récentes avec leur statut
    
    Args:
        limit: Nombre de prédictions à retourner
        
    Returns:
        Liste des prédictions récentes
    """
    try:
        from optimization.prediction_logger import get_recent_predictions as get_recent
        
        predictions = get_recent(limit)
        
        return {
            'predictions': predictions,
            'total': len(predictions)
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_recent_predictions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predictor/reload")
async def reload_predictor(model_name: str = Query('xgboost_v1')):
    """
    Recharger le predictor (utile après ré-entraînement)
    
    Args:
        model_name: Nom du modèle à recharger
        
    Returns:
        Statut du rechargement
    """
    try:
        from optimization import predictor
        
        # Reset singleton
        predictor._predictor_instance = None
        
        # Recharger
        new_predictor = predictor.get_predictor(model_name)
        
        if new_predictor.loaded:
            return {
                'status': 'success',
                'message': f'Predictor {model_name} rechargé',
                'features_count': len(new_predictor.feature_names) if new_predictor.feature_names else 0
            }
        else:
            raise HTTPException(status_code=500, detail='Échec du rechargement')
            
    except Exception as e:
        logger.error(f"❌ Erreur reload_predictor: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict")
async def predict_opportunity(
    features: Dict[str, Any],
    model_name: str = Query('xgboost_v1'),
):
    """
    Faire une prédiction ML sur une opportunité
    
    Args:
        features: Dictionnaire avec toutes les features (RSI, MACD, BB, etc.)
        model_name: Nom du modèle à utiliser (défaut: xgboost_v1)
        
    Returns:
        Prédiction avec probabilité et confiance
    """
    try:
        from optimization.predictor import predict_opportunity as predict_opp
        
        # Faire prédiction
        prediction = predict_opp(features, model_name)
        
        if prediction is None:
            raise HTTPException(
                status_code=404,
                detail=f"Modèle '{model_name}' non disponible. Entraînez d'abord le modèle."
            )
        
        return prediction
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur predict_opportunity: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict/batch")
async def predict_batch(
    opportunities: List[Dict[str, Any]],
    model_name: str = Query('xgboost_v1'),
):
    """
    Faire des prédictions ML en batch sur plusieurs opportunités
    
    Args:
        opportunities: Liste de dictionnaires de features
        model_name: Nom du modèle à utiliser
        
    Returns:
        Liste de prédictions
    """
    try:
        from optimization.predictor import get_predictor
        
        predictor = get_predictor(model_name)
        predictions = predictor.batch_predict(opportunities)
        
        # Filtrer les None
        results = [p for p in predictions if p is not None]
        
        return {
            'predictions': results,
            'total': len(opportunities),
            'successful': len(results),
            'failed': len(opportunities) - len(results)
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur predict_batch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== ALERTS ==========

@router.get("/alerts/history")
async def get_alerts_history(limit: int = Query(20, ge=1, le=100)):
    """
    Récupérer l'historique des alertes ML
    
    Args:
        limit: Nombre d'alertes à retourner
        
    Returns:
        Historique des alertes
    """
    try:
        from optimization.ml_alerts import get_alert_manager
        
        manager = get_alert_manager()
        history = manager.get_alert_history(limit)
        
        return {
            'alerts': history,
            'total': len(history)
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_alerts_history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/test")
async def test_alert(
    symbol: str = Query('BTCUSDT'),
    channels: List[str] = Query(['console'])
):
    """
    Tester le système d'alertes avec une prédiction fictive
    
    Args:
        symbol: Symbole pour le test
        channels: Canaux à tester
        
    Returns:
        Résultat du test
    """
    try:
        from optimization.ml_alerts import send_ml_alert
        
        # Créer prédiction fictive
        test_prediction = {
            'prediction': 'win',
            'win_probability': 0.85,
            'loss_probability': 0.15,
            'confidence': 0.85,
            'model_name': 'xgboost_v1_test',
            'top_features': [
                {'feature': 'bb_distance_to_upper_1m', 'importance': 15.6},
                {'feature': 'macd_momentum_5m', 'importance': 11.0},
                {'feature': 'rsi_divergence', 'importance': 7.2}
            ]
        }
        
        result = send_ml_alert(
            prediction=test_prediction,
            symbol=symbol,
            scan_id=None,
            min_confidence=0.7,
            channels=channels
        )
        
        return {
            'status': 'success',
            'message': 'Alerte test envoyée',
            'result': result
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur test_alert: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== TRAINING ==========

@router.get("/retrain/check")
async def check_retrain_status():
    """
    Vérifier si le modèle doit être ré-entraîné
    
    Returns:
        Statut et raisons pour ré-entraînement
    """
    try:
        from optimization.auto_retrain import check_retrain_needed, get_retrain_schedule_info
        
        check = check_retrain_needed()
        schedule = get_retrain_schedule_info()
        
        return {
            'retrain_check': check,
            'schedule_info': schedule
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur check_retrain_status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retrain")
async def trigger_retrain(
    background_tasks: BackgroundTasks,
    force: bool = Query(False),
):
    """
    Déclencher ré-entraînement automatique du modèle
    
    Args:
        force: Forcer le ré-entraînement même si pas nécessaire
        
    Returns:
        Task ID pour suivre progression
    """
    try:
        from optimization.auto_retrain import auto_retrain_if_needed
        
        # Vérifier si nécessaire (sauf si force)
        if not force:
            from optimization.auto_retrain import check_retrain_needed
            check = check_retrain_needed()
            
            if not check['retrain_needed']:
                return {
                    'status': 'skipped',
                    'message': check['message'],
                    'details': check.get('details')
                }
        
        # Créer task ID
        task_id = str(uuid.uuid4())
        
        # Initialiser task status
        ml_tasks[task_id] = {
            'task_id': task_id,
            'status': 'pending',
            'model_type': 'xgboost',
            'action': 'retrain',
            'created_at': datetime.now().isoformat(),
            'progress': 0,
        }
        
        # Lancer ré-entraînement en background
        async def _retrain_background():
            try:
                ml_tasks[task_id]['status'] = 'running'
                ml_tasks[task_id]['progress'] = 10
                
                result = await auto_retrain_if_needed(force=force)
                
                if result['status'] == 'success':
                    ml_tasks[task_id].update({
                        'status': 'completed',
                        'progress': 100,
                        'result': result['result'],
                        'completed_at': datetime.now().isoformat()
                    })
                else:
                    ml_tasks[task_id].update({
                        'status': 'error',
                        'error': result['message'],
                        'completed_at': datetime.now().isoformat()
                    })
                    
            except Exception as e:
                ml_tasks[task_id].update({
                    'status': 'error',
                    'error': str(e),
                    'completed_at': datetime.now().isoformat()
                })
        
        background_tasks.add_task(_retrain_background)
        
        logger.info(f"🚀 Ré-entraînement déclenché (task_id={task_id})")
        
        return {
            'task_id': task_id,
            'status': 'pending',
            'message': 'Ré-entraînement démarré'
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur trigger_retrain: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train")
async def train_model(
    background_tasks: BackgroundTasks,
    model_type: str = Query('xgboost', regex='^(xgboost)$'),
    timeframe_days: int = 60,
    min_trades: int = 50,
):
    """
    Déclencher entraînement modèle ML
    
    Args:
        model_type: Type de modèle (xgboost pour l'instant)
        timeframe_days: Fenêtre temporelle données
        min_trades: Minimum trades requis
        
    Returns:
        task_id pour suivre progression
    """
    try:
        from optimization.data.feature_loader import get_trades_count
        
        # Vérifier données suffisantes
        trades_count = get_trades_count()
        
        if trades_count < min_trades:
            raise HTTPException(
                400,
                f"Pas assez de données: {trades_count}/{min_trades} trades requis"
            )
        
        # Créer task ID
        task_id = str(uuid.uuid4())
        
        # Initialiser task status
        ml_tasks[task_id] = {
            'task_id': task_id,
            'status': 'pending',
            'model_type': model_type,
            'timeframe_days': timeframe_days,
            'min_trades': min_trades,
            'created_at': datetime.now().isoformat(),
            'progress': 0,
        }
        
        # Lancer entraînement en background
        if model_type == 'xgboost':
            background_tasks.add_task(
                _train_xgboost_background,
                task_id,
                timeframe_days,
                min_trades,
            )
        
        logger.info(f"🚀 Entraînement {model_type} démarré (task_id={task_id})")
        
        return {
            'task_id': task_id,
            'status': 'pending',
            'message': f'Entraînement {model_type} démarré',
            'trades_count': trades_count,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur train_model: {e}", exc_info=True)
        return JSONResponse({'error': str(e)}, status_code=500)


async def _train_xgboost_background(task_id: str, timeframe_days: int, min_trades: int):
    """Fonction background pour entraînement XGBoost"""
    try:
        from optimization.models.xgboost_trainer import XGBoostTrainer
        
        # Update status
        ml_tasks[task_id]['status'] = 'running'
        ml_tasks[task_id]['progress'] = 10
        
        logger.info(f"🎯 Entraînement XGBoost en cours (task_id={task_id})")
        
        # Entraîner
        trainer = XGBoostTrainer()
        
        ml_tasks[task_id]['progress'] = 30
        
        results = trainer.train(
            timeframe_days=timeframe_days,
            min_trades=min_trades,
        )
        
        # Success
        ml_tasks[task_id].update({
            'status': 'completed',
            'progress': 100,
            'results': results,
            'completed_at': datetime.now().isoformat(),
        })
        
        logger.info(f"✅ Entraînement XGBoost terminé (task_id={task_id})")
        
        # Recharger automatiquement le predictor avec le nouveau modèle
        try:
            from optimization.predictor import get_predictor
            predictor = get_predictor('xgboost_v1')
            predictor.loaded = False  # Force reload
            predictor.load_model()
            logger.info("🔄 Predictor rechargé automatiquement avec le nouveau modèle")
        except Exception as reload_err:
            logger.warning(f"⚠️ Impossible de recharger le predictor: {reload_err}")
        
    except Exception as e:
        logger.error(f"❌ Erreur entraînement XGBoost: {e}", exc_info=True)
        
        ml_tasks[task_id].update({
            'status': 'failed',
            'error': str(e),
            'failed_at': datetime.now().isoformat(),
        })


# ========== TASKS ==========

@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    Status d'une tâche ML (training, backtest, etc.)
    """
    task_info = get_ml_task_status(task_id)
    return task_info


# ========== HYPERPARAMETER OPTIMIZATION ==========

@router.post("/optimize/start")
async def start_hyperparameter_optimization(
    background_tasks: BackgroundTasks,
    n_trials: int = Query(100, ge=10, le=1000),
    timeout: Optional[int] = Query(None, ge=60),
    metric: str = Query('trading_composite', regex='^(' + '|'.join(METRIC_OPTIONS) + ')$'),
    use_gpu: bool = Query(False),
    max_samples: Optional[int] = Query(None, ge=100)
):
    """
    Démarrer optimisation hyperparamètres
    
    Args:
        n_trials: Nombre de trials (10-1000)
        timeout: Timeout en secondes (optionnel)
        metric: Métrique à optimiser
        use_gpu: Utiliser GPU si disponible
        max_samples: Limiter nombre de samples pour rapidité
        
    Returns:
        task_id pour suivre progression
    """
    try:
        from optimization.data.feature_loader import get_trades_count
        
        # Vérifier données suffisantes
        trades_count = get_trades_count()
        
        if trades_count < 1000:
            raise HTTPException(
                400,
                f"Pas assez de données: {trades_count}/1000 trades minimum requis pour optimisation"
            )
        
        # Créer task ID
        task_id = str(uuid.uuid4())
        
        # Initialiser task status
        ml_tasks[task_id] = {
            'task_id': task_id,
            'status': 'pending',
            'action': 'hyperparameter_optimization',
            'n_trials': n_trials,
            'metric': metric,
            'use_gpu': use_gpu,
            'created_at': datetime.now().isoformat(),
            'progress': 0,
            'current_trial': 0,
            'best_score': None,
            'best_params': None
        }
        
        # Lancer optimisation en background
        background_tasks.add_task(
            _optimize_hyperparameters_background,
            task_id,
            n_trials,
            timeout,
            metric,
            use_gpu,
            max_samples
        )
        
        logger.info(f"🎯 Optimisation hyperparamètres démarrée (task_id={task_id}, trials={n_trials})")
        
        return {
            'task_id': task_id,
            'status': 'pending',
            'message': f'Optimisation démarrée ({n_trials} trials)',
            'trades_count': trades_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur start_optimization: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _optimize_hyperparameters_background(
    task_id: str,
    n_trials: int,
    timeout: Optional[int],
    metric: str,
    use_gpu: bool,
    max_samples: Optional[int]
):
    """Fonction background pour optimisation hyperparamètres"""
    try:
        from ml.hyperparameter_tuning import HyperparameterTuner
        
        # Update status
        ml_tasks[task_id]['status'] = 'running'
        ml_tasks[task_id]['progress'] = 5
        
        logger.info(f"🚀 Optimisation en cours (task_id={task_id})")
        
        # Détecter GPU si demandé
        gpu_id = None
        if use_gpu:
            try:
                import torch
                if torch.cuda.is_available():
                    gpu_id = 0
                    logger.info("🎮 GPU détecté et activé")
            except:
                pass
        
        # Charger et préparer données
        ml_tasks[task_id]['progress'] = 10
        ml_tasks[task_id]['stage'] = 'loading_data'
        
        X, y, feature_names = HyperparameterTuner.load_and_prepare_data(
            max_samples=max_samples
        )
        
        # Créer tuner
        ml_tasks[task_id]['progress'] = 15
        ml_tasks[task_id]['stage'] = 'initializing'
        
        tuner = HyperparameterTuner(
            n_trials=n_trials,
            timeout=timeout,
            n_jobs=-1,  # Utiliser tous les CPU
            gpu_id=gpu_id,
            metric=metric,
            cv_folds=5,
            pruning=True
        )
        initial_trial_count = len(tuner.study.trials)
        run_best_trial: Dict[str, Any] = {'trial': None}
        
        # Callback pour mettre à jour progression
        def trial_callback(study, trial):
            if trial.state == optuna.trial.TrialState.COMPLETE:
                progress = min(95, 15 + (trial.number / n_trials) * 80)
                ml_tasks[task_id].update({
                    'progress': int(progress),
                    'current_trial': trial.number + 1,
                    'best_score': study.best_value,
                    'best_params': study.best_params,
                    'stage': f'trial_{trial.number + 1}/{n_trials}'
                })
                if trial.number >= initial_trial_count:
                    current_best = run_best_trial['trial']
                    if current_best is None or (trial.value is not None and trial.value > current_best.value):
                        run_best_trial['trial'] = trial
                    if run_best_trial['trial'] is not None:
                        ml_tasks[task_id].update({
                            'run_best_score': run_best_trial['trial'].value,
                            'run_best_params': run_best_trial['trial'].params,
                            'run_best_trial': run_best_trial['trial'].number
                        })
        
        # Optimiser avec callback
        ml_tasks[task_id]['stage'] = 'optimizing'
        
        import optuna
        tuner.study.optimize(
            lambda trial: tuner._objective(trial, X, y),
            n_trials=n_trials,
            timeout=timeout,
            callbacks=[trial_callback],
            show_progress_bar=False
        )
        
        # Sauvegarder meilleurs params
        ml_tasks[task_id]['progress'] = 95
        ml_tasks[task_id]['stage'] = 'saving'
        
        tuner.save_best_params()
        
        # Success
        latest_run_trial = run_best_trial['trial']
        if latest_run_trial is None:
            # Aucun trial du run n'a dépassé les performances précédentes
            # -> prendre le dernier trial exécuté pendant ce run pour représenter "last_run"
            new_trials = [t for t in tuner.study.trials if t.number >= initial_trial_count]
            if new_trials:
                latest_run_trial = new_trials[-1]

        ml_tasks[task_id].update({
            'status': 'completed',
            'progress': 100,
            'stage': 'completed',
            'best_score': tuner.study.best_value,
            'best_params': tuner.study.best_params,
            'run_best_score': latest_run_trial.value if latest_run_trial is not None else None,
            'run_best_params': latest_run_trial.params if latest_run_trial is not None else None,
            'run_best_trial': latest_run_trial.number if latest_run_trial is not None else None,
            'n_trials_completed': len([t for t in tuner.study.trials if t.state == optuna.trial.TrialState.COMPLETE]),
            'n_trials_pruned': len([t for t in tuner.study.trials if t.state == optuna.trial.TrialState.PRUNED]),
            'completed_at': datetime.now().isoformat()
        })
        
        logger.info(f"✅ Optimisation terminée (task_id={task_id}, best_score={tuner.study.best_value:.4f})")
        
        # Préparer les données pour record_metric_run
        run_data = {
            'metric': metric,
            'score': latest_run_trial.value if latest_run_trial is not None else tuner.study.best_value,
            'params': (latest_run_trial.params if latest_run_trial is not None else tuner.study.best_params),
            'trial_number': (latest_run_trial.number if latest_run_trial is not None else tuner.study.best_trial.number),
            'total_trials': len(tuner.study.trials),
            'datetime': datetime.now().isoformat()
        }
        
        logger.info(f"📊 Enregistrement métrique '{metric}' avec score={run_data['score']:.4f}, params={list(run_data['params'].keys())}")
        record_metric_run(metric, run_data)
        logger.info(f"✅ Métrique '{metric}' enregistrée dans optuna_last_runs.json")
        
    except Exception as e:
        logger.error(f"❌ Erreur optimisation: {e}", exc_info=True)
        
        ml_tasks[task_id].update({
            'status': 'failed',
            'error': str(e),
            'failed_at': datetime.now().isoformat()
        })


@router.get("/optimize/history")
async def get_optimization_history(
    limit: int = Query(50, ge=1, le=500),
    study_name: str = Query('xgboost_trading_optimization')
):
    """
    Récupérer historique des trials d'optimisation
    
    Args:
        limit: Nombre de trials à retourner
        study_name: Nom de l'étude Optuna
        
    Returns:
        Liste des trials avec params et scores
    """
    try:
        from ml.hyperparameter_tuning import HyperparameterTuner
        
        # Charger étude
        tuner = HyperparameterTuner(
            study_name=study_name,
            n_trials=1  # Juste pour charger l'étude
        )
        
        if len(tuner.study.trials) == 0:
            return {
                'trials': [],
                'best_trial': None,
                'total_trials': 0
            }
        
        # Récupérer historique
        history = tuner.get_optimization_history()
        
        # Filtrer trials complétés et trier par score
        completed_trials = [
            h for h in history 
            if h['state'] == 'COMPLETE' and h['value'] is not None
        ]
        completed_trials.sort(key=lambda x: x['value'], reverse=True)
        
        # Limiter
        limited_trials = completed_trials[:limit]
        
        # Best trial
        best_trial = None
        if tuner.study.best_trial:
            best_trial = {
                'number': tuner.study.best_trial.number,
                'value': tuner.study.best_trial.value,
                'params': tuner.study.best_trial.params,
                'datetime': tuner.study.best_trial.datetime_start.isoformat() if tuner.study.best_trial.datetime_start else None
            }
        
        return {
            'trials': limited_trials,
            'best_trial': best_trial,
            'total_trials': len(tuner.study.trials),
            'completed_trials': len(completed_trials),
            'pruned_trials': len([t for t in tuner.study.trials if t.state.name == 'PRUNED'])
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_optimization_history: {e}", exc_info=True)
        return {
            'trials': [],
            'best_trial': None,
            'total_trials': 0,
            'error': str(e)
        }


@router.get("/optimize/best")
async def get_best_hyperparameters(
    study_name: str = Query('xgboost_trading_optimization')
):
    """
    Récupérer meilleurs hyperparamètres trouvés
    
    Returns:
        Meilleurs params et score
    """
    try:
        from ml.hyperparameter_tuning import HyperparameterTuner
        
        # Charger étude
        tuner = HyperparameterTuner(
            study_name=study_name,
            n_trials=1
        )
        
        if len(tuner.study.trials) == 0:
            return {
                'found': False,
                'message': 'Aucune optimisation trouvée'
            }
        
        best_trial = tuner.study.best_trial
        
        return {
            'found': True,
            'trial_number': best_trial.number,
            'score': best_trial.value,
            'params': best_trial.params,
            'datetime': best_trial.datetime_start.isoformat() if best_trial.datetime_start else None,
            'total_trials': len(tuner.study.trials)
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_best_hyperparameters: {e}", exc_info=True)
        return {
            'found': False,
            'error': str(e)
        }


@router.post("/optimize/apply")
async def apply_best_hyperparameters(
    params_to_apply: Optional[Dict[str, Any]] = Body(None),
    config_file: str = Query('config_overrides.json')
):
    """
    Appliquer hyperparamètres spécifiques à config_overrides.json
    
    Args:
        params_to_apply: Paramètres à appliquer (si None, utilise best global Optuna)
        config_file: Fichier de config à écrire
    
    Returns:
        Confirmation et params appliqués
    """
    try:
        # Si params fournis directement, les utiliser
        if params_to_apply:
            params_dict = params_to_apply
            score = None
            logger.info(f"📝 Application de paramètres fournis par le frontend: {params_dict}")
        else:
            # Fallback: utiliser le best global d'Optuna
            from ml.hyperparameter_tuning import HyperparameterTuner
            
            tuner = HyperparameterTuner(
                study_name='xgboost_trading_optimization',
                n_trials=1
            )
            
            if len(tuner.study.trials) == 0:
                raise HTTPException(400, "Aucune optimisation trouvée et aucun paramètre fourni")
            
            params_dict = tuner.study.best_params
            score = tuner.study.best_value
            logger.info(f"📝 Application du meilleur global Optuna: {params_dict}")
        
        # Sauvegarder dans config_overrides.json
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
        else:
            config = {}
        
        # Ajouter params avec préfixe ml_ (filtrer les metadata _source et _metric)
        for param, value in params_dict.items():
            # Ignorer les clés metadata du frontend
            if param.startswith('_'):
                continue
            config_key = f"ml_{param}"
            config[config_key] = value
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"💾 Paramètres sauvegardés dans {config_file}")
        
        # Recharger immédiatement les overrides pour mettre à jour TRADING_CONFIG
        try:
            from config import TRADING_CONFIG
            from utils.config_persistence import apply_config_overrides
            apply_config_overrides(TRADING_CONFIG)
            logger.info("✅ TRADING_CONFIG rechargé avec les paramètres ML")
        except Exception as reload_err:
            logger.error(f"❌ Impossible de recharger TRADING_CONFIG: {reload_err}")
        
        logger.info(f"✅ Paramètres appliqués à {config_file}")
        
        return {
            'success': True,
            'message': f'Paramètres appliqués à {config_file}',
            'params': params_dict,
            'score': score,
            'config_file': config_file,
            'warning': 'Relancer entraînement du modèle pour appliquer les changements'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur apply_best_hyperparameters: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
