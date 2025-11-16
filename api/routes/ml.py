"""
API Routes ML - Endpoints pour Machine Learning
Dashboard, Features, Models, Backtesting, Live Predictions
"""

import asyncio
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
import pandas as pd
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

# Router ML
router = APIRouter(prefix="/api/ml", tags=["ML"])

# State global pour tracking tasks
ml_tasks = {}


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
        
        # Missing values
        missing_pct = (df.isnull().sum() / len(df) * 100).to_dict()
        high_missing = {k: v for k, v in missing_pct.items() if v > 10}
        
        # Features avec variance
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
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
