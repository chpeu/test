"""
API Routes ML - Endpoints pour Machine Learning
Dashboard, Features, Models, Backtesting, Live Predictions
"""

import asyncio
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
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
                'balanced': 0.4 <= win_rate <= 0.6
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


# ========== TASKS ==========

@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    Status d'une tâche ML (training, backtest, etc.)
    """
    task_info = get_ml_task_status(task_id)
    return task_info
