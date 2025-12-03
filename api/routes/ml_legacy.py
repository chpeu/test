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
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Body, Request
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

def _get_task_from_store(task_id: str) -> Dict:
    """Récupère status d'une tâche ML depuis le store"""
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


@router.get("/dashboard/ml_trades_count")
async def get_ml_trades_count():
    """
    🔢 Retourne le nombre de trades utilisables pour ML après filtrage COMPLET:
    - Exclure trades manuels (exit_reason = 'MANUAL')
    - Exclure trades avec configs différentes de la CONFIG ACTUELLE
    
    🔥 FILTRE EXHAUSTIF sur TOUS les paramètres influençant:
    - Validation des setups (min_score, snr, volume, confluence, ATR, patterns, etc.)
    - Prise de position (filtres additionnels)
    - Clôture (TP/SL via config_snapshot JSONB)
    
    Le compteur se met à jour dynamiquement quand l'utilisateur change les paramètres.
    """
    try:
        from optimization.data.feature_loader import get_sqlalchemy_engine
        from config import TRADING_CONFIG
        import pandas as pd
        
        engine = get_sqlalchemy_engine()
        
        # ═══════════════════════════════════════════════════════════════════
        # 1. LIRE TOUS LES PARAMÈTRES DE LA CONFIG ACTUELLE
        # ═══════════════════════════════════════════════════════════════════
        
        # Paramètres de validation des setups (colonnes config_*)
        current_config = {
            # Paramètres de base (validation setup)
            'min_score': float(TRADING_CONFIG.get('min_score_required', 6.5)),
            'snr_threshold': float(TRADING_CONFIG.get('snr_threshold', 0.15)),
            'volume_mult': float(TRADING_CONFIG.get('volume_multiplier', 0.95)),
            'use_confluence': bool(TRADING_CONFIG.get('use_confluence', False)),
            
            # ATR optimal
            'atr_min_1m': float(TRADING_CONFIG.get('optimal_atr_min_1m', 0.12)),
            'atr_max_1m': float(TRADING_CONFIG.get('optimal_atr_max_1m', 0.75)),
            'atr_min_5m': float(TRADING_CONFIG.get('optimal_atr_min_5m', 0.22)),
            'atr_max_5m': float(TRADING_CONFIG.get('optimal_atr_max_5m', 1.4)),
            
            # Filtres additionnels (si colonnes remplies)
            'use_anti_whipsaw': bool(TRADING_CONFIG.get('use_anti_whipsaw', False)),
            'use_candle_close': bool(TRADING_CONFIG.get('use_candle_close', False)),
            'use_cooldown': bool(TRADING_CONFIG.get('use_cooldown', False)),
            'use_momentum_continuity': bool(TRADING_CONFIG.get('use_momentum_continuity', False)),
            'use_retest_confirmation': bool(TRADING_CONFIG.get('use_retest_confirmation', False)),
            
            # TP/SL (depuis config_snapshot JSONB)
            'tp_sl_mode': str(TRADING_CONFIG.get('tp_sl_mode', 'FIXE')),
            'tp_percent': float(TRADING_CONFIG.get('tp_percent', 0.5)),
            'sl_percent': float(TRADING_CONFIG.get('sl_percent', 0.2)),
            
            # Patterns techniques (depuis config_snapshot JSONB) - flags + seuils
            'use_breakout': bool(TRADING_CONFIG.get('use_breakout', True)),
            'breakout_threshold': float(TRADING_CONFIG.get('breakout_threshold', 0.25)),
            'use_snr': bool(TRADING_CONFIG.get('use_snr', True)),
            'snr_threshold': float(TRADING_CONFIG.get('snr_threshold', 0.15)),
            'use_wick': bool(TRADING_CONFIG.get('use_wick', False)),
            'wick_ratio_max': float(TRADING_CONFIG.get('wick_ratio_max', 4.5)),
            'use_divergence': bool(TRADING_CONFIG.get('use_divergence', True)),
            'di_gap_min': float(TRADING_CONFIG.get('di_gap_min', 4.0)),
            'di_gap_adx_threshold': float(TRADING_CONFIG.get('di_gap_adx_threshold', 25.0)),
        }
        
        # ═══════════════════════════════════════════════════════════════════
        # 2. COMPTER TOUS LES TRADES
        # ═══════════════════════════════════════════════════════════════════
        total_trades = int(pd.read_sql("SELECT COUNT(*) as cnt FROM trades", engine).iloc[0]['cnt'])
        
        # ═══════════════════════════════════════════════════════════════════
        # 3. COMPTER TRADES NON-MANUELS
        # ═══════════════════════════════════════════════════════════════════
        non_manual = int(pd.read_sql("""
            SELECT COUNT(*) as cnt FROM trades 
            WHERE exit_reason IS NULL OR exit_reason != 'MANUAL'
        """, engine).iloc[0]['cnt'])
        
        # ═══════════════════════════════════════════════════════════════════
        # 4. CONSTRUIRE LE FILTRE COMPLET (identique à l'entraînement ML)
        # ═══════════════════════════════════════════════════════════════════
        # 🔥 Utiliser la fonction centralisée pour garantir la cohérence
        from optimization.data.feature_loader import build_config_filter_conditions
        # Note: On utilise la table trades directement, donc inclure exit_reason
        conditions = build_config_filter_conditions(for_trades_table=True)
        
        clean_query = f"SELECT COUNT(*) as cnt FROM trades WHERE {' AND '.join(conditions)}"
        clean_count = int(pd.read_sql(clean_query, engine).iloc[0]['cnt'])
        
        # ═══════════════════════════════════════════════════════════════════
        # 5. BREAKDOWN PAR CONFIG (pour debug)
        # ═══════════════════════════════════════════════════════════════════
        config_query = """
            SELECT 
                config_min_score_required,
                config_snr_threshold,
                config_volume_multiplier,
                config_use_confluence,
                COUNT(*) as cnt
            FROM trades
            WHERE exit_reason IS NULL OR exit_reason != 'MANUAL'
            GROUP BY config_min_score_required, config_snr_threshold, config_volume_multiplier, config_use_confluence
            ORDER BY cnt DESC
            LIMIT 5
        """
        config_df = pd.read_sql(config_query, engine)
        
        config_breakdown = []
        if len(config_df) > 0:
            for _, row in config_df.iterrows():
                min_score = row['config_min_score_required']
                snr_thresh = row['config_snr_threshold']
                vol_mult = row['config_volume_multiplier']
                confluence = row['config_use_confluence']
                
                is_current = (
                    pd.notna(min_score) and abs(float(min_score) - current_config['min_score']) < 0.1 and
                    pd.notna(snr_thresh) and abs(float(snr_thresh) - current_config['snr_threshold']) < 0.02 and
                    pd.notna(vol_mult) and abs(float(vol_mult) - current_config['volume_mult']) < 0.05 and
                    pd.notna(confluence) and confluence == current_config['use_confluence']
                )
                
                config_breakdown.append({
                    'min_score': float(min_score) if pd.notna(min_score) else None,
                    'snr_threshold': float(snr_thresh) if pd.notna(snr_thresh) else None,
                    'volume_mult': float(vol_mult) if pd.notna(vol_mult) else None,
                    'confluence': bool(confluence) if pd.notna(confluence) else None,
                    'count': int(row['cnt']),
                    'is_current': bool(is_current)
                })
        
        engine.dispose()
        
        # ═══════════════════════════════════════════════════════════════════
        # 6. RETOURNER LE RÉSULTAT
        # ═══════════════════════════════════════════════════════════════════
        return {
            'total_trades': total_trades,
            'manual_excluded': total_trades - non_manual,
            'non_manual_trades': non_manual,
            'config_filtered_trades': clean_count,
            'different_config_excluded': non_manual - clean_count,
            'current_config': current_config,
            'config_breakdown': config_breakdown,
            'filters_applied': {
                'setup_validation': ['min_score', 'snr_threshold', 'volume_mult', 'confluence', 'atr_1m', 'atr_5m'],
                'additional_filters': ['anti_whipsaw', 'candle_close', 'cooldown', 'momentum', 'retest'],
                'tp_sl': ['tp_sl_mode', 'tp_percent', 'sl_percent'],
                'patterns_techniques': ['use_breakout', 'breakout_threshold', 'use_snr', 'snr_threshold', 'use_wick', 'wick_ratio_max', 'use_divergence', 'di_gap_min', 'di_gap_adx_threshold']
            },
            'message': f"✅ {clean_count} trades avec config actuelle (sur {total_trades} total)"
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_ml_trades_count: {e}", exc_info=True)
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


# ========== V2 PREDICTIONS (REGRESSION PNL%) ==========

@router.post("/predict_v2")
async def predict_pnl_v2(
    features: Dict[str, Any],
    model_name: str = Query('xgboost_v2_latest'),
):
    """
    Faire une prédiction PNL% (V2 Régression) sur une opportunité
    
    Args:
        features: Dictionnaire avec toutes les features (RSI, MACD, BB, etc.)
        model_name: Nom du modèle V2 à utiliser (défaut: xgboost_v2_latest)
        
    Returns:
        Prédiction avec PNL% prédit, classification WIN/LOSS, et metadata
    """
    try:
        from optimization.predictor_v2 import predict_pnl
        
        # Faire prédiction V2
        prediction = predict_pnl(features, model_name)
        
        if prediction is None:
            raise HTTPException(
                status_code=404,
                detail=f"Modèle V2 '{model_name}' non disponible. Entraînez d'abord le modèle V2."
            )
        
        return prediction
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur predict_pnl_v2: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict_v2/batch")
async def predict_pnl_v2_batch(
    opportunities: List[Dict[str, Any]],
    model_name: str = Query('xgboost_v2_latest'),
):
    """
    Faire des prédictions PNL% V2 en batch sur plusieurs opportunités
    
    Args:
        opportunities: Liste de dictionnaires de features
        model_name: Nom du modèle V2 à utiliser
        
    Returns:
        Liste de prédictions PNL%
    """
    try:
        from optimization.predictor_v2 import get_predictor_v2
        
        predictor = get_predictor_v2(model_name)
        predictions = predictor.batch_predict(opportunities)
        
        # Filtrer les None
        results = [p for p in predictions if p is not None]
        
        # Statistiques
        predicted_pnls = [p['predicted_pnl'] for p in results]
        avg_pnl = sum(predicted_pnls) / len(predicted_pnls) if predicted_pnls else 0
        profitable_count = sum(1 for pnl in predicted_pnls if pnl > 0)
        
        return {
            'predictions': results,
            'total': len(opportunities),
            'successful': len(results),
            'failed': len(opportunities) - len(results),
            'stats': {
                'avg_predicted_pnl': round(avg_pnl, 3),
                'profitable_count': profitable_count,
                'loss_count': len(predicted_pnls) - profitable_count,
                'profitable_pct': round((profitable_count / len(predicted_pnls) * 100), 1) if predicted_pnls else 0
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur predict_pnl_v2_batch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict_v2/filter")
async def filter_setup_with_v2(
    features: Dict[str, Any],
    min_expected_pnl: float = Query(0.3, ge=0.0, le=10.0)
):
    """
    Vérifier si un setup doit être filtré basé sur le PNL% prédit V2
    
    Args:
        features: Dictionnaire avec toutes les features
        min_expected_pnl: PNL minimum requis (%) pour accepter le trade
        
    Returns:
        Résultat du filtrage avec prédiction
    """
    try:
        from optimization.predictor_v2 import get_predictor_v2
        
        predictor = get_predictor_v2()
        should_reject, predicted_pnl, reason = predictor.should_reject_trade(
            features=features,
            min_expected_pnl=min_expected_pnl
        )
        
        return {
            'should_reject': should_reject,
            'predicted_pnl': predicted_pnl,
            'predicted_pnl_formatted': f"{predicted_pnl:+.2f}%" if predicted_pnl else None,
            'reason': reason,
            'min_expected_pnl': min_expected_pnl,
            'recommendation': 'reject' if should_reject else 'accept'
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur filter_setup_with_v2: {e}", exc_info=True)
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
        
        # Vérifier données suffisantes (warning sans bloquer)
        trades_count = get_trades_count()
        
        if trades_count < min_trades:
            logger.warning(f"⚠️ Données limitées: {trades_count}/{min_trades} trades - entraînement peut être sous-optimal")
            # Ne PAS bloquer, continuer avec les données disponibles
        
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
    task_data = _get_task_from_store(task_id)
    
    # 🔥 FIX: Nettoyer les données non-sérialisables (coroutines, objets, etc.)
    clean_data = {}
    for key, value in task_data.items():
        if value is None:
            clean_data[key] = None
        elif isinstance(value, (str, int, float, bool)):
            clean_data[key] = value
        elif isinstance(value, dict):
            clean_data[key] = {
                k: str(v) if not isinstance(v, (str, int, float, bool, type(None), list, dict)) else v 
                for k, v in value.items()
            }
        elif isinstance(value, list):
            clean_data[key] = [
                str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v 
                for v in value
            ]
        else:
            clean_data[key] = str(value)
    
    return clean_data


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


# ========== GRADIENTBOOSTING OPTIMIZATION ==========

@router.post("/optimize/gb/start")
async def start_gradientboosting_optimization(
    background_tasks: BackgroundTasks,
    n_trials: int = Query(100, ge=10, le=500),
    timeout_minutes: int = Query(30, ge=5, le=120),
    timeframe_days: int = Query(365, ge=30, le=730),
    use_histgb: bool = Query(False, description="Utiliser HistGradientBoosting (10x plus rapide)")
):
    """
    Démarrer optimisation hyperparamètres GradientBoosting
    
    Caractéristiques:
    - Cross-validation 5-fold stratifiée
    - Holdout test set 20% (jamais vu pendant l'optimisation)
    - Score composite pénalisant l'overfitting
    - Métriques fiables et répétables
    
    Args:
        n_trials: Nombre de trials (10-500)
        timeout_minutes: Timeout en minutes (5-120)
        timeframe_days: Nombre de jours de données (30-730)
        
    Returns:
        task_id pour suivre progression
    """
    try:
        from optimization.data.feature_loader import get_trades_count
        
        # Vérifier données suffisantes
        trades_count = get_trades_count()
        
        if trades_count < 100:
            raise HTTPException(
                400,
                f"Pas assez de données: {trades_count}/100 trades minimum requis"
            )
        
        # Créer task ID
        task_id = str(uuid.uuid4())
        
        # Initialiser task status
        model_name = 'HistGradientBoosting' if use_histgb else 'GradientBoosting'
        ml_tasks[task_id] = {
            'task_id': task_id,
            'status': 'pending',
            'action': 'gb_optimization',
            'model_type': model_name,
            'use_histgb': use_histgb,
            'n_trials': n_trials,
            'timeout_minutes': timeout_minutes,
            'timeframe_days': timeframe_days,
            'created_at': datetime.now().isoformat(),
            'progress': 0,
            'current_trial': 0,
            'best_score': None,
            'best_params': None
        }
        
        # Lancer optimisation en background
        background_tasks.add_task(
            _optimize_gradientboosting_background,
            task_id,
            n_trials,
            timeout_minutes,
            timeframe_days,
            use_histgb
        )
        
        speed_info = " (⚡ 10x plus rapide)" if use_histgb else ""
        logger.info(f"🎯 Optimisation {model_name} démarrée{speed_info} (task_id={task_id}, trials={n_trials})")
        
        return {
            'task_id': task_id,
            'status': 'pending',
            'message': f'Optimisation {model_name} démarrée ({n_trials} trials, timeout={timeout_minutes}min){speed_info}',
            'trades_count': trades_count,
            'model_type': model_name,
            'use_histgb': use_histgb
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur start_gb_optimization: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _optimize_gradientboosting_background(
    task_id: str,
    n_trials: int,
    timeout_minutes: int,
    timeframe_days: int,
    use_histgb: bool = False
):
    """Fonction background pour optimisation GradientBoosting"""
    try:
        from optimization.optuna_gradientboosting import GradientBoostingOptimizer
        
        # Update status
        model_name = 'HistGradientBoosting' if use_histgb else 'GradientBoosting'
        ml_tasks[task_id]['status'] = 'running'
        ml_tasks[task_id]['progress'] = 5
        ml_tasks[task_id]['stage'] = 'initializing'
        
        speed_info = " (⚡ rapide)" if use_histgb else ""
        logger.info(f"🚀 Optimisation {model_name}{speed_info} en cours (task_id={task_id})")
        
        # Créer optimizer
        optimizer = GradientBoostingOptimizer(
            n_trials=n_trials,
            timeout_minutes=timeout_minutes,
            use_histgb=use_histgb
        )
        
        # Charger données
        ml_tasks[task_id]['progress'] = 10
        ml_tasks[task_id]['stage'] = 'loading_data'
        
        n_samples = optimizer.load_data(timeframe_days=timeframe_days)
        ml_tasks[task_id]['n_samples'] = n_samples
        
        # Optimiser
        ml_tasks[task_id]['progress'] = 15
        ml_tasks[task_id]['stage'] = 'optimizing'
        
        best_params = optimizer.optimize(n_trials=n_trials, timeout_minutes=timeout_minutes)
        
        # Mettre à jour pendant l'optimisation
        if optimizer.study:
            ml_tasks[task_id].update({
                'progress': 85,
                'current_trial': len(optimizer.study.trials),
                'best_score': optimizer.study.best_value,
                'best_params': optimizer.best_params
            })
        
        # Validation finale sur holdout
        ml_tasks[task_id]['progress'] = 90
        ml_tasks[task_id]['stage'] = 'validating_holdout'
        
        metrics = optimizer.validate_on_holdout()
        
        # Résumé final
        results = optimizer.get_results_summary()
        
        # 🔥 SAUVEGARDER dans optuna_gb_results.json pour persistence
        results_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'data', 'optuna_gb_results.json'
        )
        os.makedirs(os.path.dirname(results_path), exist_ok=True)
        
        save_data = {
            'status': 'completed',
            'timestamp': datetime.now().isoformat(),
            'best_params': optimizer.best_params,
            'best_score_composite': results.get('best_score_composite', metrics.get('test_accuracy', 0)),
            'metrics_holdout': metrics,
            'n_trials_completed': len(optimizer.study.trials) if optimizer.study else 0,
            'n_trials_pruned': results.get('n_trials_pruned', 0),
            'top_5_trials': results.get('top_5_trials', [])
        }
        
        with open(results_path, 'w') as f:
            json.dump(save_data, f, indent=2)
        
        logger.info(f"💾 Résultats sauvegardés: {results_path}")
        
        # Mettre à jour task
        ml_tasks[task_id].update({
            'status': 'completed',
            'progress': 100,
            'stage': 'completed',
            'best_params': optimizer.best_params,
            'metrics_holdout': metrics,
            'results': results,
            'completed_at': datetime.now().isoformat()
        })
        
        # Sauvegarder dans optuna_last_runs.json avec clé spécifique
        run_data = {
            'metric': 'gb_composite',
            'model_type': 'GradientBoosting',
            'score': metrics['test_accuracy'],
            'params': optimizer.best_params,
            'metrics': metrics,
            'trial_number': len(optimizer.study.trials) if optimizer.study else 0,
            'total_trials': n_trials,
            'datetime': datetime.now().isoformat()
        }
        record_metric_run('gb_composite', run_data)
        
        logger.info(f"✅ Optimisation GradientBoosting terminée: test_acc={metrics['test_accuracy']:.4f}, gap={metrics['overfitting_gap']:.4f}")
        
    except Exception as e:
        logger.error(f"❌ Erreur optimisation GradientBoosting: {e}", exc_info=True)
        
        ml_tasks[task_id].update({
            'status': 'failed',
            'error': str(e),
            'failed_at': datetime.now().isoformat()
        })


@router.post("/optimize/gb/apply")
async def apply_gradientboosting_params(
    params_to_apply: Optional[Dict[str, Any]] = Body(None),
    config_file: str = Query('config_overrides.json')
):
    """
    Appliquer hyperparamètres GradientBoosting à config_overrides.json
    
    Args:
        params_to_apply: Paramètres à appliquer
        config_file: Fichier de config à écrire
    
    Returns:
        Confirmation et params appliqués
    """
    try:
        if not params_to_apply:
            # Charger depuis le dernier résultat sauvegardé
            results_path = os.path.join(
                os.path.dirname(__file__), '..', '..', 'data', 'optuna_gb_results.json'
            )
            if os.path.exists(results_path):
                with open(results_path, 'r') as f:
                    results = json.load(f)
                    params_to_apply = results.get('best_params', {})
            else:
                raise HTTPException(400, "Aucun paramètre fourni et aucune optimisation GB trouvée")
        
        # Sauvegarder dans config_overrides.json
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
        else:
            config = {}
        
        # Mapping des paramètres GradientBoosting
        gb_mapping = {
            'n_estimators': 'gb_n_estimators',
            'max_depth': 'gb_max_depth',
            'learning_rate': 'gb_learning_rate',
            'min_samples_split': 'gb_min_samples_split',
            'min_samples_leaf': 'gb_min_samples_leaf',
            'subsample': 'gb_subsample',
            'max_features': 'gb_max_features',
            'l2_regularization': 'gb_l2_regularization'  # Pour HistGB
        }
        
        applied_params = {}
        for param, value in params_to_apply.items():
            if param in gb_mapping:
                config_key = gb_mapping[param]
                config[config_key] = value
                applied_params[config_key] = value
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Recharger config
        try:
            from config import TRADING_CONFIG
            from utils.config_persistence import apply_config_overrides
            apply_config_overrides(TRADING_CONFIG)
            logger.info("✅ TRADING_CONFIG rechargé avec params GradientBoosting")
        except Exception as reload_err:
            logger.warning(f"⚠️ Impossible de recharger TRADING_CONFIG: {reload_err}")
        
        logger.info(f"✅ Paramètres GradientBoosting appliqués: {applied_params}")
        
        return {
            'success': True,
            'message': f'Paramètres GradientBoosting appliqués à {config_file}',
            'params': applied_params,
            'config_file': config_file
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur apply_gb_params: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/optimize/gb/results")
async def get_gradientboosting_results():
    """
    Récupérer les résultats de la dernière optimisation GradientBoosting
    
    Returns:
        Meilleurs params, métriques et historique
    """
    try:
        results_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'data', 'optuna_gb_results.json'
        )
        
        if not os.path.exists(results_path):
            return {
                'found': False,
                'message': 'Aucune optimisation GradientBoosting trouvée'
            }
        
        with open(results_path, 'r') as f:
            results = json.load(f)
        
        return {
            'found': True,
            **results
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_gb_results: {e}", exc_info=True)
        return {
            'found': False,
            'error': str(e)
        }


# ========== AUTO-OPTIMISATION COMPLETE ==========

@router.post("/optimize/auto/start")
async def start_auto_optimization(
    background_tasks: BackgroundTasks,
    request: Request
):
    """
    Démarrer l'optimisation automatique complète ML
    
    - Sélection de features (RF importance)
    - Grid search hyperparamètres
    - Analyse des seuils de confiance
    - Cross-validation
    - Comparaison ancien/nouveau modèle
    """
    try:
        body = await request.json()
        n_splits = body.get('n_splits', 15)
        timeframe_days = body.get('timeframe_days', 365)
        min_trades = body.get('min_trades', 100)
        
        # Créer task ID
        task_id = str(uuid.uuid4())
        
        # Initialiser task status
        ml_tasks[task_id] = {
            'task_id': task_id,
            'status': 'pending',
            'action': 'auto_optimization',
            'created_at': datetime.now().isoformat(),
            'progress': 0,
            'message': 'Initialisation...',
            'n_splits': n_splits,
            'timeframe_days': timeframe_days,
            'min_trades': min_trades
        }
        
        # Lancer optimisation en background
        background_tasks.add_task(
            _run_auto_optimization_background,
            task_id,
            n_splits,
            timeframe_days,
            min_trades
        )
        
        logger.info(f"🚀 Auto-optimisation ML démarrée (task_id={task_id})")
        
        return {
            'task_id': task_id,
            'status': 'pending',
            'message': f'Auto-optimisation démarrée ({n_splits} splits)'
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur start_auto_optimization: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _run_auto_optimization_background(
    task_id: str,
    n_splits: int,
    timeframe_days: int,
    min_trades: int
):
    """Exécute l'auto-optimisation en background (NON-BLOQUANT)"""
    import asyncio
    import sys
    
    try:
        ml_tasks[task_id]['status'] = 'running'
        ml_tasks[task_id]['progress'] = 5
        ml_tasks[task_id]['message'] = 'Chargement des données...'
        
        # Exécuter le script d'optimisation
        script_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'scripts', 'auto_optimize_ml.py'
        )
        
        ml_tasks[task_id]['progress'] = 10
        ml_tasks[task_id]['message'] = 'Lancement de l\'optimisation...'
        
        # 🔧 FIX: Utiliser asyncio.create_subprocess_exec (non-bloquant)
        process = await asyncio.create_subprocess_exec(
            sys.executable, script_path, 
            '--splits', str(n_splits),
            '--timeframe', str(timeframe_days),
            '--min-trades', str(min_trades),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # 🔧 NOUVEAU: Lire stdout en temps réel pour récupérer la progression
        async def read_progress():
            """Lit stdout en temps réel et met à jour la progression"""
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                    
                line_str = line.decode('utf-8', errors='ignore').strip()
                
                # Parser les lignes PROGRESS:XX:message
                if line_str.startswith('PROGRESS:'):
                    try:
                        parts = line_str.split(':', 2)
                        if len(parts) >= 3:
                            progress = int(parts[1])
                            message = parts[2]
                            ml_tasks[task_id]['progress'] = progress
                            ml_tasks[task_id]['message'] = message
                            logger.info(f"📊 Optimisation progress: {progress}% - {message}")
                    except (ValueError, IndexError):
                        pass
                else:
                    # Logger les autres lignes pour debug
                    if line_str:
                        logger.debug(f"[auto_optimize_ml] {line_str}")
        
        # Lancer la lecture de progression en parallèle
        progress_task = asyncio.create_task(read_progress())
        
        # Attendre avec timeout (non-bloquant pour le reste de l'app)
        # 🔧 FIX: Augmenter timeout à 30 minutes pour les gros datasets
        try:
            # Attendre que le process finisse
            await asyncio.wait_for(process.wait(), timeout=1800)  # 30 minutes max
            # Récupérer stderr pour les erreurs
            stderr = await process.stderr.read()
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            progress_task.cancel()
            raise Exception("Timeout: optimisation trop longue (>30 min)")
        
        # Annuler la tâche de progression si encore active
        progress_task.cancel()
        
        if process.returncode != 0:
            raise Exception(f"Script failed: {stderr.decode()}")
        
        ml_tasks[task_id]['progress'] = 90
        ml_tasks[task_id]['message'] = 'Lecture des résultats...'
        
        # Charger les résultats
        metadata_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 
            'optimization', 'saved_models', 'best_classifier_metadata.json'
        )
        
        threshold_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 
            'optimization', 'saved_models', 'threshold_analysis.csv'
        )
        
        results = {}
        
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                results['params'] = metadata.get('params', {})
                results['metrics'] = metadata.get('metrics', {})
                results['feature_names'] = metadata.get('feature_names', [])
                results['n_features'] = metadata.get('n_features', 20)
                results['optimal_thresholds'] = metadata.get('optimal_thresholds', {})
                
                # Baseline pour comparaison
                results['baseline'] = {
                    'accuracy': 0.6193,
                    'f1': 0.5654,
                    'roc_auc': 0.6466,
                    'overfitting': 0.077
                }
                
                # Seuil optimal
                results['optimal_threshold'] = results['optimal_thresholds'].get('best_f1', 0.45)
        
        # Charger l'analyse des seuils
        if os.path.exists(threshold_path):
            import csv
            threshold_analysis = []
            with open(threshold_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    threshold_analysis.append({
                        'threshold': float(row['threshold']),
                        'accuracy': float(row['accuracy']),
                        'f1_score': float(row['f1_score']),
                        'precision': float(row['precision']),
                        'recall': float(row['recall'])
                    })
            results['threshold_analysis'] = threshold_analysis
        
        ml_tasks[task_id]['status'] = 'completed'
        ml_tasks[task_id]['progress'] = 100
        ml_tasks[task_id]['message'] = 'Optimisation terminée!'
        ml_tasks[task_id]['results'] = results
        
        logger.info(f"✅ Auto-optimisation terminée (task_id={task_id})")
        
    except Exception as e:
        ml_tasks[task_id]['status'] = 'failed'
        ml_tasks[task_id]['error'] = str(e)
        logger.error(f"❌ Auto-optimisation failed: {e}", exc_info=True)


@router.post("/optimize/auto/apply")
async def apply_auto_optimization_results(request: Request):
    """
    Appliquer les résultats de l'auto-optimisation
    
    Met à jour:
    - config_overrides.json avec les nouveaux hyperparamètres
    - Le seuil de confiance optimal
    """
    try:
        results = await request.json()
        
        config_file = os.path.join(
            os.path.dirname(__file__), '..', '..', 'config_overrides.json'
        )
        
        # Charger config existante
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
        else:
            config = {}
        
        params = results.get('params', {})
        optimal_threshold = results.get('optimal_threshold', 0.45)
        n_features = results.get('n_features', 20)
        
        # Mapping des paramètres
        param_mapping = {
            'max_depth': 'gb_max_depth',
            'learning_rate': 'gb_learning_rate',
            'max_iter': 'gb_n_estimators',
            'min_samples_leaf': 'gb_min_samples_leaf',
            'l2_regularization': 'gb_l2_regularization'
        }
        
        applied_params = {}
        for key, value in params.items():
            if key in param_mapping:
                config_key = param_mapping[key]
                config[config_key] = value
                applied_params[config_key] = value
        
        # Appliquer le seuil optimal
        config['gb_min_confidence'] = optimal_threshold
        applied_params['gb_min_confidence'] = optimal_threshold
        
        # Appliquer le nombre de features
        config['gb_n_features'] = n_features
        applied_params['gb_n_features'] = n_features
        
        # Sauvegarder
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Recharger config
        try:
            from config import TRADING_CONFIG
            from utils.config_persistence import apply_config_overrides
            apply_config_overrides(TRADING_CONFIG)
            logger.info("✅ TRADING_CONFIG rechargé avec auto-optimisation")
        except Exception as reload_err:
            logger.warning(f"⚠️ Impossible de recharger TRADING_CONFIG: {reload_err}")
        
        logger.info(f"✅ Auto-optimisation appliquée: {applied_params}")
        
        return {
            'success': True,
            'message': 'Paramètres auto-optimisés appliqués',
            'params': applied_params,
            'optimal_threshold': optimal_threshold,
            'metrics': results.get('metrics', {})
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur apply_auto_optimization: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


"""
Endpoints ML V2 - À ajouter à api/routes/ml.py
XGBoost V2 (Régression PNL%)
"""

# ========== V2: TRAIN REGRESSION MODEL ==========

@router.post("/train_v2")
async def train_xgboost_v2_model(
    background_tasks: BackgroundTasks,
    force: bool = Query(False)
):
    """
    Entraîner XGBoost V2 (Régression PNL%)
    
    Args:
        force: Forcer réentraînement même si modèle récent existe
        
    Returns:
        task_id pour suivre progression ou résultats si terminé
    """
    try:
        from config import TRADING_CONFIG
        
        # Créer task ID
        task_id = str(uuid.uuid4())
        
        # Initialiser task status
        ml_tasks[task_id] = {
            'task_id': task_id,
            'status': 'pending',
            'action': 'train_v2',
            'created_at': datetime.now().isoformat(),
            'progress': 0
        }
        
        # Lancer entraînement en background
        background_tasks.add_task(
            _train_xgboost_v2_background,
            task_id,
            force
        )
        
        logger.info(f"🚀 Entraînement XGBoost V2 démarré (task_id={task_id})")
        
        return {
            'task_id': task_id,
            'status': 'pending',
            'message': 'Entraînement V2 démarré'
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur train_v2: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task/{task_id}")
async def get_ml_task_status(task_id: str):
    """
    Récupérer le statut d'une tâche ML (entraînement, optimisation, etc.)
    
    Args:
        task_id: ID de la tâche
        
    Returns:
        Status et données de la tâche
    """
    try:
        if task_id not in ml_tasks:
            raise HTTPException(status_code=404, detail=f"Task {task_id} introuvable")
        
        task_data = ml_tasks[task_id]
        
        # 🔥 FIX: Nettoyer les données non-sérialisables (coroutines, objets, etc.)
        clean_data = {}
        for key, value in task_data.items():
            if value is None:
                clean_data[key] = None
            elif isinstance(value, (str, int, float, bool)):
                clean_data[key] = value
            elif isinstance(value, dict):
                # Nettoyer récursivement les dicts
                clean_data[key] = {
                    k: str(v) if not isinstance(v, (str, int, float, bool, type(None), list, dict)) else v 
                    for k, v in value.items()
                }
            elif isinstance(value, list):
                clean_data[key] = [
                    str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v 
                    for v in value
                ]
            else:
                # Convertir tout objet non-standard en string
                clean_data[key] = str(value)
        
        return clean_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur get_ml_task_status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _train_xgboost_v2_background(task_id: str, force: bool):
    """Fonction background pour entraînement V2"""
    try:
        from config import TRADING_CONFIG
        from optimization.data.feature_loader import load_features_from_postgres
        from optimization.data.feature_engineering import calculate_derived_features
        from optimization.utils.temporal_split import temporal_train_test_split
        from optimization.data.preprocessor import FeaturePreprocessor
        from xgboost import XGBRegressor
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, accuracy_score, f1_score
        from sklearn.feature_selection import mutual_info_regression
        import numpy as np
        import pandas as pd
        import json
        
        # Update status
        ml_tasks[task_id]['status'] = 'running'
        ml_tasks[task_id]['progress'] = 5
        ml_tasks[task_id]['stage'] = 'loading_data'
        
        logger.info(f"🚀 Entraînement V2 en cours (task_id={task_id})")
        
        # Charger params depuis config
        timeframe_days = TRADING_CONFIG.get('ml_v2_timeframe_days', 270)
        max_features = TRADING_CONFIG.get('ml_v2_max_features', 40)
        marginal_threshold = TRADING_CONFIG.get('ml_v2_marginal_threshold', 0.20)
        filter_marginal = TRADING_CONFIG.get('ml_v2_filter_marginal_trades', True)
        test_size = TRADING_CONFIG.get('ml_v2_test_size', 0.2)
        validation_size = TRADING_CONFIG.get('ml_v2_validation_size', 0.1)
        
        # Hyperparams - 🔥 V2.1: Défauts plus régularisés pour éviter overfitting
        n_estimators = TRADING_CONFIG.get('ml_v2_n_estimators', 300)
        max_depth = TRADING_CONFIG.get('ml_v2_max_depth', 3)      # Réduit de 4 à 3
        learning_rate = TRADING_CONFIG.get('ml_v2_learning_rate', 0.02)  # Réduit
        min_child_weight = TRADING_CONFIG.get('ml_v2_min_child_weight', 15)  # Augmenté
        reg_alpha = TRADING_CONFIG.get('ml_v2_reg_alpha', 5.0)    # Augmenté de 1 à 5
        reg_lambda = TRADING_CONFIG.get('ml_v2_reg_lambda', 8.0)  # Augmenté de 3 à 8
        subsample = TRADING_CONFIG.get('ml_v2_subsample', 0.6)    # Réduit
        colsample_bytree = TRADING_CONFIG.get('ml_v2_colsample_bytree', 0.6)  # Réduit
        gamma = TRADING_CONFIG.get('ml_v2_gamma', 2.0)            # Augmenté de 0.5 à 2
        
        logger.info(f"📊 Params V2: timeframe={timeframe_days}d, max_features={max_features}, filter_marginal={filter_marginal}")
        
        # Charger données nettoyées (meme filtre que XGBoost V1)
        ml_tasks[task_id]['progress'] = 10
        base_df = load_features_from_postgres(
            timeframe_days=timeframe_days,
            min_trades=50,
            use_clean_data=True
        )
        
        df = calculate_derived_features(base_df)
        logger.info(f"✅ {len(df)} trades chargés")
        
        # Filtrer invalides
        ml_tasks[task_id]['progress'] = 15
        ml_tasks[task_id]['stage'] = 'filtering'
        
        initial_count = len(df)
        
        if 'price' in df.columns:
            df = df[df['price'] > 0].copy()
        
        if filter_marginal and 'target_pnl' in df.columns:
            df = df[abs(df['target_pnl']) >= marginal_threshold].copy()
        
        # 🔥 FIX V2.1: Clipper les outliers de target_pnl pour éviter R² négatif
        if 'target_pnl' in df.columns:
            pnl_before = df['target_pnl'].describe()
            
            # Winsorization: utiliser percentiles 5% et 95% (plus agressif pour éviter R² négatif)
            lower_bound = df['target_pnl'].quantile(0.05)
            upper_bound = df['target_pnl'].quantile(0.95)
            
            # Clipper entre les percentiles (généralement ±3-5%)
            df['target_pnl'] = df['target_pnl'].clip(lower=lower_bound, upper=upper_bound)
            
            pnl_after = df['target_pnl'].describe()
            logger.info(f"📊 Target PNL clippé: [{lower_bound:.2f}%, {upper_bound:.2f}%]")
            logger.info(f"📊 Avant: std={pnl_before['std']:.3f}%, range=[{pnl_before['min']:.2f}%, {pnl_before['max']:.2f}%]")
            logger.info(f"📊 Après: std={pnl_after['std']:.3f}%, range=[{pnl_after['min']:.2f}%, {pnl_after['max']:.2f}%]")
        
        logger.info(f"✅ {len(df)} trades après filtrage ({len(df)/initial_count*100:.1f}%)")
        
        if len(df) < 100:
            raise Exception(f"Dataset trop petit: {len(df)} trades (minimum 100)")
        
        # Split temporel
        ml_tasks[task_id]['progress'] = 20
        ml_tasks[task_id]['stage'] = 'splitting'
        
        train_df, val_df, test_df = temporal_train_test_split(
            df,
            target_col='target_pnl',
            test_size=test_size,
            validation_size=validation_size,
            timestamp_col='timestamp'
        )
        
        # Séparer X, y
        exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 'is_opportunity']
        feature_cols = [col for col in train_df.columns if col not in exclude_cols]
        
        X_train = train_df[feature_cols].copy()
        y_train = train_df['target_pnl'].copy()
        
        X_val = val_df[feature_cols].copy()
        y_val = val_df['target_pnl'].copy()
        
        X_test = test_df[feature_cols].copy()
        y_test = test_df['target_pnl'].copy()
        
        logger.info(f"✅ Split: Train={len(X_train)}, Val={len(X_val)}, Test={len(X_test)}")
        
        # Feature selection
        ml_tasks[task_id]['progress'] = 30
        ml_tasks[task_id]['stage'] = 'feature_selection'
        
        mi_scores = mutual_info_regression(
            X_train.fillna(0),
            y_train,
            random_state=42
        )
        
        mi_df = pd.DataFrame({
            'feature': feature_cols,
            'mi_score': mi_scores
        }).sort_values('mi_score', ascending=False)
        
        selected_features = mi_df.head(max_features)['feature'].tolist()
        
        X_train = X_train[selected_features]
        X_val = X_val[selected_features]
        X_test = X_test[selected_features]
        
        logger.info(f"✅ {max_features} features sélectionnées (top mutual info)")
        
        # Preprocessing
        ml_tasks[task_id]['progress'] = 40
        ml_tasks[task_id]['stage'] = 'preprocessing'
        
        preprocessor = FeaturePreprocessor(scaler_type='robust')
        X_train_scaled, _ = preprocessor.fit_transform(
            pd.concat([X_train, y_train.rename('target_pnl')], axis=1),
            target_col='target_pnl'
        )
        
        X_val_scaled = preprocessor.transform(X_val)
        X_test_scaled = preprocessor.transform(X_test)
        
        # Entraîner modèle
        ml_tasks[task_id]['progress'] = 50
        ml_tasks[task_id]['stage'] = 'training'
        
        model = XGBRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            min_child_weight=min_child_weight,
            reg_alpha=reg_alpha,
            reg_lambda=reg_lambda,
            subsample=subsample,
            colsample_bytree=colsample_bytree,
            gamma=gamma,
            random_state=42,
            objective='reg:squarederror',
            eval_metric='mae',
            n_jobs=-1
        )
        
        eval_set = [(X_val_scaled, y_val)]
        
        model.fit(
            X_train_scaled,
            y_train,
            eval_set=eval_set,
            early_stopping_rounds=50,
            verbose=False
        )
        
        logger.info("✅ Entraînement terminé")
        
        # Évaluation régression
        ml_tasks[task_id]['progress'] = 80
        ml_tasks[task_id]['stage'] = 'evaluation'
        
        y_train_pred = model.predict(X_train_scaled)
        y_val_pred = model.predict(X_val_scaled)
        y_test_pred = model.predict(X_test_scaled)
        
        # Métriques régression
        train_mae = mean_absolute_error(y_train, y_train_pred)
        train_r2 = r2_score(y_train, y_train_pred)
        
        val_mae = mean_absolute_error(y_val, y_val_pred)
        val_r2 = r2_score(y_val, y_val_pred)
        
        test_mae = mean_absolute_error(y_test, y_test_pred)
        test_r2 = r2_score(y_test, y_test_pred)
        
        # 🔥 DIAGNOSTIC R² négatif
        if test_r2 < -1.0:
            logger.warning(f"⚠️ R² très négatif ({test_r2:.1f}): variance train={y_train.var():.4f}, test={y_test.var():.4f}")
            logger.warning(f"⚠️ Predictions: mean={y_test_pred.mean():.3f}, std={y_test_pred.std():.3f}")
            logger.warning(f"⚠️ Actuals: mean={y_test.mean():.3f}, std={y_test.std():.3f}")
            # Clipper R² pour affichage (le modèle reste le même)
            test_r2_display = max(-1.0, test_r2)
        else:
            test_r2_display = test_r2
        
        # Classification avec seuil
        threshold = 0.0
        y_test_class = (y_test > threshold).astype(int)
        y_test_pred_class = (y_test_pred > threshold).astype(int)
        
        test_f1 = f1_score(y_test_class, y_test_pred_class, zero_division=0)
        test_accuracy = accuracy_score(y_test_class, y_test_pred_class)
        
        logger.info(f"📊 R² Test: {test_r2_display:.3f} (raw: {test_r2:.1f}), MAE Test: {test_mae:.3f}%, F1: {test_f1:.3f}")
        
        # ========== SAUVEGARDE MODÈLE V2 ==========
        ml_tasks[task_id]['progress'] = 90
        ml_tasks[task_id]['stage'] = 'saving_files'
        
        import joblib
        from pathlib import Path
        from datetime import datetime
        
        # Créer dossier si nécessaire
        models_dir = Path("optimization/saved_models")
        models_dir.mkdir(parents=True, exist_ok=True)
        
        # Timestamp pour version
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_name = f"xgboost_v2_{timestamp}"
        
        # Sauvegarder modèle
        model_path = models_dir / f"{model_name}.pkl"
        joblib.dump(model, model_path)
        logger.info(f"💾 Modèle sauvegardé: {model_path}")
        
        # Sauvegarder preprocessor
        preprocessor_path = models_dir / f"{model_name}_preprocessor.pkl"
        joblib.dump(preprocessor, preprocessor_path)
        logger.info(f"💾 Preprocessor sauvegardé: {preprocessor_path}")
        
        # Sauvegarder aussi comme "latest"
        latest_model_path = models_dir / "xgboost_v2_latest.pkl"
        latest_preprocessor_path = models_dir / "xgboost_v2_latest_preprocessor.pkl"
        joblib.dump(model, latest_model_path)
        joblib.dump(preprocessor, latest_preprocessor_path)
        
        # ========== SAUVEGARDE POSTGRESQL ==========
        ml_tasks[task_id]['progress'] = 95
        ml_tasks[task_id]['stage'] = 'saving_database'
        
        try:
            from database.db_manager import DatabaseManager
            db = DatabaseManager()
            
            # Désactiver anciens modèles V2
            await db.execute("""
                UPDATE ml_models 
                SET is_active = FALSE 
                WHERE model_name LIKE 'xgboost_v2%'
            """)
            
            # Préparer hyperparamètres
            model_params = {
                'n_estimators': n_estimators,
                'max_depth': max_depth,
                'learning_rate': learning_rate,
                'min_child_weight': min_child_weight,
                'reg_alpha': reg_alpha,
                'reg_lambda': reg_lambda,
                'subsample': subsample,
                'colsample_bytree': colsample_bytree,
                'gamma': gamma,
                'objective': 'reg:squarederror',
                'eval_metric': 'mae'
            }
            
            # Feature importance (top 20)
            feature_importance = dict(zip(
                selected_features[:20],
                model.feature_importances_[:20].tolist()
            ))
            
            # Scores de sélection (top 20)
            feature_selection_scores = mi_df.head(20).set_index('feature')['mi_score'].to_dict()
            
            # Insérer nouveau modèle
            await db.execute("""
                INSERT INTO ml_models (
                    model_name, model_type, version, model_path, preprocessor_path,
                    train_r2, val_r2, test_r2,
                    train_mae, val_mae, test_mae,
                    train_mse, val_mse, test_mse,
                    test_f1, test_accuracy,
                    timeframe_days, min_trades,
                    total_samples, train_samples, val_samples, test_samples,
                    filter_marginal_trades, marginal_threshold,
                    split_type, max_features,
                    model_params, feature_importance,
                    selected_features, feature_selection_scores,
                    is_active, trained_at
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7, $8,
                    $9, $10, $11,
                    $12, $13, $14,
                    $15, $16,
                    $17, $18,
                    $19, $20, $21, $22,
                    $23, $24,
                    $25, $26,
                    $27, $28,
                    $29, $30,
                    $31, $32
                )
            """,
                model_name,                           # $1
                'XGBRegressor',                       # $2
                '2.0',                                # $3
                str(model_path),                      # $4
                str(preprocessor_path),               # $5
                train_r2, val_r2, test_r2,           # $6-$8
                train_mae, val_mae, test_mae,        # $9-$11
                mean_squared_error(y_train, y_train_pred),  # $12
                mean_squared_error(y_val, y_val_pred),      # $13
                mean_squared_error(y_test, y_test_pred),    # $14
                test_f1, test_accuracy,              # $15-$16
                timeframe_days, 50,                  # $17-$18
                len(df), len(X_train), len(X_val), len(X_test),  # $19-$22
                filter_marginal, marginal_threshold, # $23-$24
                'temporal', max_features,            # $25-$26
                json.dumps(model_params),            # $27
                json.dumps(feature_importance),      # $28
                json.dumps(selected_features),       # $29
                json.dumps(feature_selection_scores),# $30
                True,                                # $31 (is_active)
                datetime.now()                       # $32
            )
            
            logger.info(f"✅ Modèle V2 sauvegardé dans PostgreSQL: {model_name}")
            
        except Exception as db_error:
            logger.error(f"❌ Erreur sauvegarde PostgreSQL: {db_error}", exc_info=True)
            # Continuer même si erreur DB (fichiers .pkl sont sauvegardés)
        
        # Success
        ml_tasks[task_id].update({
            'status': 'completed',
            'progress': 100,
            'stage': 'completed',
            'model_name': model_name,
            'model_path': str(model_path),
            'preprocessor_path': str(preprocessor_path),
            'metrics': {
                'train': {'mae': train_mae, 'r2': train_r2},
                'val': {'mae': val_mae, 'r2': val_r2},
                'test': {'mae': test_mae, 'r2': test_r2, 'f1': test_f1, 'accuracy': test_accuracy}
            },
            'test_mae': test_mae,
            'test_r2': test_r2,
            'test_f1': test_f1,
            'total_samples': len(df),
            'completed_at': datetime.now().isoformat()
        })
        
        logger.info(f"✅ Entraînement V2 terminé (task_id={task_id})")
        
    except Exception as e:
        logger.error(f"❌ Erreur _train_xgboost_v2_background: {e}", exc_info=True)
        ml_tasks[task_id].update({
            'status': 'error',
            'error': str(e),
            'failed_at': datetime.now().isoformat()
        })


# ========== V2: HYPERPARAMETER OPTIMIZATION ==========

# State global pour Optuna V2
optuna_v2_state = {
    'is_running': False,
    'study': None,
    'progress': 0,
    'current_trial': 0,
    'total_trials': 0,
    'best_params': None,
    'best_value': None,
    'run_best_params': None,
    'run_best_score': None,
    'run_best_trial': None,
    'n_trials': 0
}

@router.post("/optimize_v2/start")
async def start_hyperparameter_optimization_v2(
    background_tasks: BackgroundTasks,
    n_trials: int = Query(50, ge=10, le=200)
):
    """
    Démarrer optimisation hyperparamètres V2 (Régression)
    
    Args:
        n_trials: Nombre de trials (10-200)
        
    Returns:
        Status de l'optimisation
    """
    try:
        if optuna_v2_state['is_running']:
            return {
                'status': 'already_running',
                'message': 'Optimisation V2 déjà en cours',
                'progress': optuna_v2_state['progress']
            }
        
        # Vérifier données suffisantes
        from optimization.data.feature_loader import get_trades_count
        trades_count = get_trades_count()
        
        if trades_count < 500:
            raise HTTPException(
                400,
                f"Pas assez de données: {trades_count}/500 trades minimum requis"
            )
        
        # Reset state
        optuna_v2_state.update({
            'is_running': True,
            'progress': 0,
            'current_trial': 0,
            'total_trials': n_trials,
            'best_params': None,
            'best_value': None,
            'run_best_params': None,
            'run_best_score': None,
            'run_best_trial': None
        })
        
        # Lancer optimisation en background
        background_tasks.add_task(
            _optimize_hyperparameters_v2_background,
            n_trials
        )
        
        logger.info(f"🎯 Optimisation V2 démarrée ({n_trials} trials)")
        
        return {
            'status': 'started',
            'message': f'Optimisation V2 démarrée ({n_trials} trials)',
            'n_trials': n_trials,
            'trades_count': trades_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur start_optimization_v2: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _optimize_hyperparameters_v2_background(n_trials: int):
    """Fonction background pour optimisation V2"""
    try:
        import optuna
        from optuna.samplers import TPESampler
        from config import TRADING_CONFIG
        from optimization.data.feature_loader import load_features_from_postgres
        from optimization.data.feature_engineering import calculate_derived_features
        from optimization.utils.temporal_split import temporal_train_test_split
        from optimization.data.preprocessor import FeaturePreprocessor
        from xgboost import XGBRegressor
        from sklearn.metrics import r2_score
        from sklearn.feature_selection import mutual_info_regression
        import pandas as pd
        
        logger.info(f"🚀 Optimisation V2 en cours")
        
        # Charger données
        optuna_v2_state['progress'] = 5
        
        timeframe_days = TRADING_CONFIG.get('ml_v2_timeframe_days', 270)
        base_df = load_features_from_postgres(timeframe_days=timeframe_days, min_trades=50, use_clean_data=True)
        df = calculate_derived_features(base_df)
        
        # Filtrer
        if 'price' in df.columns:
            df = df[df['price'] > 0].copy()
        
        marginal_threshold = TRADING_CONFIG.get('ml_v2_marginal_threshold', 0.20)
        if 'target_pnl' in df.columns:
            df = df[abs(df['target_pnl']) >= marginal_threshold].copy()
        
        # Split
        train_df, val_df, test_df = temporal_train_test_split(
            df,
            target_col='target_pnl',
            test_size=0.2,
            validation_size=0.1,
            timestamp_col='timestamp'
        )
        
        exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 'is_opportunity']
        feature_cols = [col for col in train_df.columns if col not in exclude_cols]
        
        X_train = train_df[feature_cols].copy()
        y_train = train_df['target_pnl'].copy()
        X_val = val_df[feature_cols].copy()
        y_val = val_df['target_pnl'].copy()
        
        # Feature selection (top 40)
        mi_scores = mutual_info_regression(X_train.fillna(0), y_train, random_state=42)
        mi_df = pd.DataFrame({'feature': feature_cols, 'mi_score': mi_scores}).sort_values('mi_score', ascending=False)
        selected_features = mi_df.head(40)['feature'].tolist()
        
        X_train = X_train[selected_features]
        X_val = X_val[selected_features]
        
        # Preprocessing
        preprocessor = FeaturePreprocessor(scaler_type='robust')
        X_train_scaled, _ = preprocessor.fit_transform(
            pd.concat([X_train, y_train.rename('target_pnl')], axis=1),
            target_col='target_pnl'
        )
        X_val_scaled = preprocessor.transform(X_val)
        
        optuna_v2_state['progress'] = 15
        
        # Créer étude Optuna
        study_name = 'xgboost_v2_regression'
        storage = 'sqlite:///data/optuna_v2.db'
        
        study = optuna.create_study(
            study_name=study_name,
            direction='maximize',
            sampler=TPESampler(seed=42),
            storage=storage,
            load_if_exists=True
        )
        
        optuna_v2_state['study'] = study
        initial_trial_count = len(study.trials)
        
        # Objective function
        def objective(trial):
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 100, 1000, step=50),
                'max_depth': trial.suggest_int('max_depth', 2, 6),
                'learning_rate': trial.suggest_float('learning_rate', 0.001, 0.3, log=True),
                'min_child_weight': trial.suggest_int('min_child_weight', 1, 20),
                'reg_alpha': trial.suggest_float('reg_alpha', 0.0, 10.0),
                'reg_lambda': trial.suggest_float('reg_lambda', 0.0, 10.0),
                'subsample': trial.suggest_float('subsample', 0.5, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
                'gamma': trial.suggest_float('gamma', 0.0, 5.0)
            }
            
            model = XGBRegressor(
                **params,
                random_state=42,
                objective='reg:squarederror',
                eval_metric='mae',
                n_jobs=-1
            )
            
            model.fit(
                X_train_scaled,
                y_train,
                eval_set=[(X_val_scaled, y_val)],
                early_stopping_rounds=50,
                verbose=False
            )
            
            y_val_pred = model.predict(X_val_scaled)
            score = r2_score(y_val, y_val_pred)
            
            # Update progress
            optuna_v2_state['current_trial'] = trial.number + 1
            optuna_v2_state['progress'] = min(95, 15 + (trial.number / n_trials) * 80)
            
            return score
        
        # Callback pour tracker run best
        run_best_trial = {'trial': None}
        
        def trial_callback(study, trial):
            if trial.state == optuna.trial.TrialState.COMPLETE:
                if trial.number >= initial_trial_count:
                    current_best = run_best_trial['trial']
                    if current_best is None or (trial.value is not None and trial.value > current_best.value):
                        run_best_trial['trial'] = trial
                        optuna_v2_state['run_best_params'] = trial.params
                        optuna_v2_state['run_best_score'] = trial.value
                        optuna_v2_state['run_best_trial'] = trial.number
        
        # Optimiser
        study.optimize(
            objective,
            n_trials=n_trials,
            callbacks=[trial_callback],
            show_progress_bar=False
        )
        
        # Success
        optuna_v2_state.update({
            'is_running': False,
            'progress': 100,
            'best_params': study.best_params,
            'best_value': study.best_value,
            'n_trials': len(study.trials)
        })
        
        logger.info(f"✅ Optimisation V2 terminée: R²={study.best_value:.3f}")
        
    except Exception as e:
        logger.error(f"❌ Erreur _optimize_v2_background: {e}", exc_info=True)
        optuna_v2_state.update({
            'is_running': False,
            'error': str(e)
        })


@router.get("/optimize_v2/status")
async def get_optimization_v2_status():
    """Status optimisation V2"""
    try:
        return {
            'is_running': optuna_v2_state['is_running'],
            'progress': optuna_v2_state['progress'],
            'current_trial': optuna_v2_state['current_trial'],
            'total_trials': optuna_v2_state['total_trials'],
            'best_params': optuna_v2_state['best_params'],
            'best_value': optuna_v2_state['best_value'],
            'run_best_params': optuna_v2_state['run_best_params'],
            'run_best_score': optuna_v2_state['run_best_score'],
            'run_best_trial': optuna_v2_state['run_best_trial'],
            'n_trials': optuna_v2_state['n_trials'],
            'study_name': 'xgboost_v2_regression'
        }
    except Exception as e:
        logger.error(f"❌ Erreur get_optimization_v2_status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize_v2/apply")
async def apply_best_hyperparameters_v2(params_dict: Dict[str, Any] = Body(None)):
    """
    Appliquer meilleurs hyperparamètres V2
    
    Args:
        params_dict: Paramètres à appliquer (ou None pour global best)
        
    Returns:
        Confirmation application
    """
    try:
        from config import TRADING_CONFIG
        
        # Si params fournis, les utiliser, sinon prendre global best
        if params_dict is None:
            if optuna_v2_state['best_params'] is None:
                raise HTTPException(400, "Aucun paramètre disponible")
            params_dict = optuna_v2_state['best_params']
            score = optuna_v2_state['best_value']
        else:
            score = params_dict.pop('score', None) if isinstance(params_dict, dict) else None
        
        logger.info(f"💾 Application params V2: {params_dict}")
        
        # Utiliser le même fichier que config_persistence.py
        from utils.config_persistence import CONFIG_OVERRIDES_FILE
        config_file = CONFIG_OVERRIDES_FILE
        
        # Charger config existante et nettoyer les clés parasites
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
            # Nettoyer les anciennes clés parasites (ex: ml_params_to_apply)
            parasites = ['ml_params_to_apply', 'params_to_apply']
            for key in parasites:
                if key in config:
                    del config[key]
                    logger.info(f"🧹 Clé parasite supprimée: {key}")
        else:
            config = {}
        
        # Whitelist des paramètres XGBoost V2 valides
        valid_v2_params = {
            'n_estimators', 'max_depth', 'learning_rate', 'min_child_weight',
            'reg_alpha', 'reg_lambda', 'gamma', 'subsample', 'colsample_bytree'
        }
        
        # Ajouter params V2 avec préfixe ml_v2_ (seulement les params valides)
        for param, value in params_dict.items():
            if param in ['score', 'source']:
                continue
            if param not in valid_v2_params:
                logger.warning(f"⚠️ Paramètre V2 non-standard ignoré: {param}")
                continue
            config_key = f"ml_v2_{param}"
            config[config_key] = value
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"💾 Paramètres V2 sauvegardés dans {config_file}")
        
        # Recharger TRADING_CONFIG
        try:
            from utils.config_persistence import apply_config_overrides
            apply_config_overrides(TRADING_CONFIG)
            logger.info("✅ TRADING_CONFIG rechargé avec params V2")
            logger.info(f"🔍 Vérification: ml_v2_max_depth = {TRADING_CONFIG.get('ml_v2_max_depth')}")
            logger.info(f"🔍 Vérification: ml_v2_learning_rate = {TRADING_CONFIG.get('ml_v2_learning_rate')}")
        except Exception as reload_err:
            logger.error(f"❌ Impossible de recharger TRADING_CONFIG: {reload_err}")
        
        return {
            'success': True,
            'message': f'Paramètres V2 appliqués à {config_file}',
            'params': params_dict,
            'score': score,
            'config_file': str(config_file),
            'warning': 'Relancer entraînement V2 pour appliquer les changements'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur apply_v2_hyperparameters: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== GRADIENTBOOSTING: TRAIN OPTIMIZED MODEL ==========

@router.post("/train_gb")
async def train_gradientboosting_model(
    background_tasks: BackgroundTasks,
    n_estimators: Optional[int] = Query(None),
    max_depth: Optional[int] = Query(None),
    learning_rate: Optional[float] = Query(None),
    min_samples_split: Optional[int] = Query(None),
    min_samples_leaf: Optional[int] = Query(None),
    subsample: Optional[float] = Query(None),
    max_features: Optional[float] = Query(None)
):
    """
    Entraîner le modèle GradientBoosting optimisé (64-69% accuracy).
    Ce modèle est meilleur que XGBoost V1 (~50%) et V2 (R² négatif).
    
    🔥 Les hyperparamètres sont chargés depuis config_overrides.json (TRADING_CONFIG)
    sauf si explicitement fournis dans la requête.
    """
    try:
        from config import TRADING_CONFIG
        from utils.config_persistence import load_config_overrides
        
        # 🔥 FIX CRITIQUE: Recharger les overrides depuis le fichier pour prendre en compte les modifications
        overrides = load_config_overrides()
        for key, value in overrides.items():
            if key.startswith('gb_'):
                TRADING_CONFIG[key] = value
        
        task_id = f"train_gb_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 🔥 FIX: Charger les hyperparamètres depuis TRADING_CONFIG si non fournis
        final_n_estimators = n_estimators if n_estimators is not None else TRADING_CONFIG.get('gb_n_estimators', 200)
        final_max_depth = max_depth if max_depth is not None else TRADING_CONFIG.get('gb_max_depth', 3)
        final_learning_rate = learning_rate if learning_rate is not None else TRADING_CONFIG.get('gb_learning_rate', 0.03)
        final_min_samples_split = min_samples_split if min_samples_split is not None else TRADING_CONFIG.get('gb_min_samples_split', 30)
        final_min_samples_leaf = min_samples_leaf if min_samples_leaf is not None else TRADING_CONFIG.get('gb_min_samples_leaf', 15)
        final_subsample = subsample if subsample is not None else TRADING_CONFIG.get('gb_subsample', 0.7)
        final_max_features = max_features if max_features is not None else TRADING_CONFIG.get('gb_max_features', 0.5)
        final_l2_regularization = TRADING_CONFIG.get('gb_l2_regularization', 0.3)  # Pour HistGB
        
        logger.info(
            f"🎯 Hyperparamètres GB depuis config: n_estimators={final_n_estimators}, "
            f"max_depth={final_max_depth}, learning_rate={final_learning_rate:.6f}, "
            f"min_samples_split={final_min_samples_split}, min_samples_leaf={final_min_samples_leaf}"
        )
        
        # Stocker les hyperparamètres dans la tâche
        ml_tasks[task_id] = {
            'task_id': task_id,
            'status': 'pending',
            'action': 'train_gb',
            'created_at': datetime.now().isoformat(),
            'progress': 0,
            'params': {
                'n_estimators': final_n_estimators,
                'max_depth': final_max_depth,
                'learning_rate': final_learning_rate,
                'min_samples_split': final_min_samples_split,
                'min_samples_leaf': final_min_samples_leaf,
                'subsample': final_subsample,
                'max_features': final_max_features,
                'l2_regularization': final_l2_regularization  # Pour HistGB
            }
        }
        
        # Lancer en background
        background_tasks.add_task(_train_gradientboosting_background, task_id)
        
        logger.info(f"🎯 Entraînement GradientBoosting démarré (task_id={task_id})")
        
        return {
            'task_id': task_id,
            'status': 'pending',
            'message': 'Entraînement GradientBoosting démarré'
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur train_gb: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify_gb")
async def verify_gradientboosting_model():
    """
    Vérifier que le modèle GradientBoosting fonctionne correctement.
    Teste sur les données récentes et retourne les métriques.
    """
    try:
        import json
        from pathlib import Path
        import joblib
        
        models_dir = Path("optimization/saved_models")
        
        # Vérifier que le modèle existe
        model_paths = [
            models_dir / "best_classifier_latest.pkl",
            models_dir / "optimized_classifier_latest.pkl"
        ]
        
        model_path = None
        for p in model_paths:
            if p.exists():
                model_path = p
                break
        
        if not model_path:
            return {
                'status': 'FAIL',
                'message': 'Modèle GradientBoosting non trouvé. Lancez l\'entraînement.',
                'accuracy': 0
            }
        
        # Charger modèle
        pipeline = joblib.load(model_path)
        
        # Charger metadata si disponible
        metadata_paths = [
            models_dir / "best_classifier_metadata.json",
            models_dir / "optimized_classifier_metadata.json"
        ]
        
        metadata = None
        for mp in metadata_paths:
            if mp.exists():
                with open(mp, 'r') as f:
                    metadata = json.load(f)
                break
        
        if metadata:
            acc = metadata.get('metrics', {}).get('test_acc', 0)
            f1 = metadata.get('metrics', {}).get('test_f1', 0)
            
            status = 'PASS' if acc >= 0.55 else 'WARN'
            
            return {
                'status': status,
                'accuracy': acc,
                'f1': f1,
                'model_type': metadata.get('best_model', 'GradientBoosting'),
                'n_features': len(metadata.get('feature_cols', [])),
                'message': f'Modèle valide - Accuracy: {acc*100:.1f}%' if status == 'PASS' else f'Accuracy faible: {acc*100:.1f}%'
            }
        
        return {
            'status': 'WARN',
            'message': 'Modèle chargé mais metadata non trouvée',
            'accuracy': 0
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur verify_gb: {e}", exc_info=True)
        return {
            'status': 'error',
            'message': str(e),
            'accuracy': 0
        }


async def _train_gradientboosting_background(task_id: str):
    """Fonction background pour entraînement GradientBoosting"""
    try:
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.preprocessing import RobustScaler
        from sklearn.metrics import accuracy_score, f1_score, precision_score
        from sklearn.pipeline import Pipeline
        from optimization.data.feature_loader import load_features_from_postgres
        from optimization.data.feature_engineering import calculate_derived_features
        import numpy as np
        import pandas as pd
        import joblib
        import json
        from pathlib import Path
        
        # Get params from task
        params = ml_tasks[task_id].get('params', {})
        
        # 🔥 LOG: Afficher les hyperparamètres utilisés
        logger.info(
            f"📋 Hyperparamètres GradientBoosting: n_estimators={params.get('n_estimators')}, "
            f"max_depth={params.get('max_depth')}, learning_rate={params.get('learning_rate')}, "
            f"min_samples_split={params.get('min_samples_split')}, min_samples_leaf={params.get('min_samples_leaf')}, "
            f"subsample={params.get('subsample')}, max_features={params.get('max_features')}"
        )
        
        # Update status
        ml_tasks[task_id]['status'] = 'running'
        ml_tasks[task_id]['progress'] = 5
        ml_tasks[task_id]['stage'] = 'loading_data'
        
        logger.info(f"🎯 Entraînement GradientBoosting en cours (task_id={task_id})")
        
        # 🔥 FIX: Utiliser ml_features (pas ml_features_clean qui est obsolète)
        # Charger TOUTES les données puis filtrer comme l'UI
        from config import TRADING_CONFIG
        timeframe = TRADING_CONFIG.get('gb_timeframe_days', 730)  # 2 ans par défaut
        
        # Charger depuis ml_features (table complète)
        base_df = load_features_from_postgres(timeframe_days=timeframe, min_trades=30, use_clean_data=False)
        logger.info(f"📊 Données brutes chargées: {len(base_df)} trades (timeframe={timeframe} jours)")
        
        # 🔥 ALIGNÉ AVEC OPTUNA: Utiliser TOUTES les données (pas de filtrage par config)
        # Le filtrage strict réduisait le dataset et causait des différences de métriques
        initial_count = len(base_df)
        
        # Filtrer les trades manuels uniquement (si colonne existe)
        if 'is_manual' in base_df.columns:
            base_df = base_df[base_df['is_manual'] != True]
            logger.info(f"   Après exclusion manuels: {len(base_df)} trades")
        
        # 🔥 DÉSACTIVÉ: Filtrage strict par config (causait écart Optuna vs UI)
        # Pour réactiver, passer use_config_filter=True
        use_config_filter = False  # Aligné avec Optuna
        
        # 🔥 ALIGNÉ AVEC OPTUNA: Pas de filtrage par config
        logger.info(f"📊 Données utilisées: {len(base_df)}/{initial_count} trades (aligné Optuna)")
        df = calculate_derived_features(base_df)
        
        ml_tasks[task_id]['progress'] = 20
        ml_tasks[task_id]['stage'] = 'feature_engineering'
        
        # Feature engineering
        if 'timestamp' in df.columns:
            ts = pd.to_datetime(df['timestamp'])
            df['hour'] = ts.dt.hour
            df['day_of_week'] = ts.dt.dayofweek
            df['good_hour'] = df['hour'].isin([2, 12, 16]).astype(int)
            df['bad_hour'] = df['hour'].isin([4, 23, 18]).astype(int)
        
        if 'rsi_1m' in df.columns and 'rsi_5m' in df.columns:
            df['rsi_momentum'] = df['rsi_1m'] - df['rsi_5m']
        
        if 'macd_hist_1m' in df.columns and 'macd_hist_5m' in df.columns:
            df['macd_momentum'] = df['macd_hist_1m'] - df['macd_hist_5m']
        
        if 'adx_1m' in df.columns:
            df['strong_trend'] = (df['adx_1m'] > 25).astype(int)
        
        # 🔥 NOUVELLES FEATURES OPTIMISEES (découvertes par analyse RF)
        # 1. Position prix dans Bollinger Bands (TOP 1 feature!)
        if 'bb_distance_to_lower_1m' in df.columns and 'bb_distance_to_upper_1m' in df.columns:
            df['bb_position'] = df['bb_distance_to_lower_1m'] / (df['bb_distance_to_lower_1m'] + df['bb_distance_to_upper_1m'] + 1e-6)
        
        # 2. Momentum combine (RSI x MACD normalise)
        if 'macd_hist_1m' in df.columns and 'rsi_1m' in df.columns:
            df['momentum_combined'] = (df['macd_hist_1m'] / (abs(df['macd_hist_1m']).max() + 1e-6)) * ((df['rsi_1m'] - 50) / 50)
        
        # 3. MACD acceleration
        if 'macd_hist_1m' in df.columns and 'macd_hist_prev_1m' in df.columns:
            df['macd_acceleration'] = df['macd_hist_1m'] - df['macd_hist_prev_1m']
        
        # 4. Distance RSI au neutre (50)
        if 'rsi_1m' in df.columns:
            df['rsi_distance_50_1m'] = abs(df['rsi_1m'] - 50)
        if 'rsi_5m' in df.columns:
            df['rsi_distance_50_5m'] = abs(df['rsi_5m'] - 50)
        
        # 5. Volatilite ratio
        if 'atr_pct_1m' in df.columns and 'atr_pct_5m' in df.columns:
            df['volatility_ratio'] = df['atr_pct_1m'] / (df['atr_pct_5m'] + 1e-6)
        
        # 6. Trend strength
        if 'adx_1m' in df.columns and 'di_gap_1m' in df.columns:
            df['trend_strength'] = df['adx_1m'] * abs(df['di_gap_1m'])
        
        # 7. Volume pressure
        if 'volume_ratio_1m' in df.columns and 'volume_spike_1m' in df.columns:
            df['volume_pressure'] = df['volume_ratio_1m'] * df['volume_spike_1m']
        
        # 8. BB squeeze
        if 'bb_width_1m' in df.columns:
            df['bb_squeeze'] = 1 / (df['bb_width_1m'] + 1e-6)
        
        # 9. RSI acceleration
        if 'rsi_1m' in df.columns and 'rsi_prev_1m' in df.columns:
            df['rsi_accel'] = df['rsi_1m'] - df['rsi_prev_1m']
        
        # 10. EMA trend aligned (multi-timeframe)
        if 'ema_diff_pct_1m' in df.columns and 'ema_diff_pct_5m' in df.columns:
            df['ema_trend_aligned'] = np.sign(df['ema_diff_pct_1m']) * np.sign(df['ema_diff_pct_5m'])
        
        logger.info(f"📊 Nouvelles features créées: bb_position, momentum_combined, macd_acceleration, etc.")
        
        # Préparer features
        exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 'is_opportunity', 'date']
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        feature_cols = [c for c in numeric_cols if c not in exclude_cols]
        
        # Supprimer colonnes constantes
        feature_cols = [c for c in feature_cols if df[c].nunique() > 1]
        
        # Supprimer colonnes avec trop de NULL
        feature_cols = [c for c in feature_cols if df[c].isnull().sum() / len(df) <= 0.3]
        
        ml_tasks[task_id]['progress'] = 40
        ml_tasks[task_id]['stage'] = 'training'
        
        X = df[feature_cols].fillna(0).values
        y = df['target_win'].astype(int).values
        
        # 🔥 FIX: Split temporel 80/20 (train/test) - PAS de données perdues
        n = len(df)
        train_end = int(n * 0.8)  # 80% train, 20% test
        
        if 'timestamp' in df.columns:
            sort_idx = df['timestamp'].argsort().values
            X = X[sort_idx]
            y = y[sort_idx]
            logger.info(f"📊 Split temporel: données triées par timestamp")
        
        X_train, X_test = X[:train_end], X[train_end:]
        y_train, y_test = y[:train_end], y[train_end:]
        
        logger.info(f"📊 Split: Train={len(y_train)} ({len(y_train)/n*100:.0f}%), Test={len(y_test)} ({len(y_test)/n*100:.0f}%)")
        
        # 🔥 OPTIMISE: Utiliser les 28 features pré-sélectionnées si disponibles
        optimized_metadata_path = Path('optimization/saved_models/gradient_boosting_optimized_metadata.json')
        use_optimized_features = False
        
        if optimized_metadata_path.exists():
            try:
                with open(optimized_metadata_path, 'r') as f:
                    opt_metadata = json.load(f)
                selected_features = opt_metadata.get('selected_features', [])
                
                if selected_features:
                    # Vérifier que toutes les features optimisées sont disponibles
                    available = set(feature_cols)
                    needed = set(selected_features)
                    missing = needed - available
                    
                    if len(missing) <= 3:  # Tolérance de 3 features manquantes
                        # Utiliser les features optimisées
                        valid_features = [f for f in selected_features if f in available]
                        feature_cols = valid_features
                        X = df[feature_cols].fillna(0).values
                        y = df['target_win'].astype(int).values  # 🔥 FIX: Recalculer y aussi
                        
                        # Re-split avec les nouvelles features ET les labels
                        if 'timestamp' in df.columns:
                            sort_idx = df['timestamp'].argsort().values
                            X = X[sort_idx]
                            y = y[sort_idx]  # 🔥 FIX: Trier y aussi !
                        
                        X_train, X_test = X[:train_end], X[train_end:]
                        y_train, y_test = y[:train_end], y[train_end:]  # 🔥 FIX: Re-split y aussi
                        
                        use_optimized_features = True
                        logger.info(f"⭐ Utilisation des {len(valid_features)} features OPTIMISEES (68.5% accuracy)")
                        logger.info(f"📋 Features: {valid_features[:5]}...")
                    else:
                        logger.warning(f"⚠️ {len(missing)} features optimisées manquantes, fallback SelectKBest")
            except Exception as e:
                logger.warning(f"⚠️ Erreur chargement features optimisées: {e}")
        
        if not use_optimized_features:
            # Fallback: Sélection dynamique avec SelectKBest
            from sklearn.feature_selection import SelectKBest, f_classif
            
            n_samples = X_train.shape[0]
            n_features_original = X_train.shape[1]
            optimal_k = max(25, min(n_samples // 80, n_features_original))
            
            if n_features_original > optimal_k:
                logger.info(f"📊 Sélection features dynamique: {n_features_original} → {optimal_k}")
                selector = SelectKBest(f_classif, k=optimal_k)
                X_train = selector.fit_transform(X_train, y_train)
                X_test = selector.transform(X_test)
                
                selected_mask = selector.get_support()
                feature_cols = [feature_cols[i] for i in range(len(feature_cols)) if selected_mask[i]]
                logger.info(f"📋 Features sélectionnées: {feature_cols[:5]}...")
        
        # 🔥 OPTIMISE: Utiliser StandardScaler (comme l'optimisation avancée)
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # 🔥 FIX: Calculer sample_weights pour gérer le déséquilibre des classes
        from sklearn.utils.class_weight import compute_class_weight
        class_weights = compute_class_weight('balanced', classes=np.unique(y_train), y=y_train)
        class_weight_dict = dict(zip(np.unique(y_train), class_weights))
        sample_weights = np.array([class_weight_dict[label] for label in y_train])
        
        # Log la distribution des classes
        n_pos = np.sum(y_train == 1)
        n_neg = np.sum(y_train == 0)
        logger.info(f"📊 Distribution classes: positifs={n_pos} ({n_pos/len(y_train)*100:.1f}%), négatifs={n_neg} ({n_neg/len(y_train)*100:.1f}%)")
        logger.info(f"📊 Class weights: {class_weight_dict}")
        
        # Choisir le type de modèle (GB standard ou HistGB 10x plus rapide)
        from config import TRADING_CONFIG
        model_type = TRADING_CONFIG.get('gb_model_type', 'gb')
        
        if model_type == 'histgb':
            # HistGradientBoosting - 10x plus rapide
            from sklearn.ensemble import HistGradientBoostingClassifier
            logger.info(f"🔥 Utilisation de HistGradientBoostingClassifier (10x plus rapide)")
            
            # 🔥 FIX: Utiliser les paramètres optimisés sans les écraser
            model = HistGradientBoostingClassifier(
                max_iter=params.get('n_estimators', 300),
                max_depth=params.get('max_depth', 2),
                learning_rate=params.get('learning_rate', 0.089),
                min_samples_leaf=params.get('min_samples_leaf', 50),
                l2_regularization=params.get('l2_regularization', 0.9),
                max_bins=255,
                random_state=42,
                early_stopping=True,
                n_iter_no_change=15,
                validation_fraction=0.15
            )
            # 🔥 FIX: HistGB utilise sample_weight dans fit()
            model.fit(X_train_scaled, y_train, sample_weight=sample_weights)
        else:
            # GradientBoosting standard - IDENTIQUE à optimize_gradientboosting_advanced.py
            logger.info(f"🌳 Utilisation de GradientBoostingClassifier (standard - mode optimisé)")
            
            # 🔥 EXACT COMME L'OPTIMISATION: pas de validation_fraction, pas de n_iter_no_change
            model = GradientBoostingClassifier(
                n_estimators=params.get('n_estimators', 271),
                max_depth=params.get('max_depth', 6),
                learning_rate=params.get('learning_rate', 0.217),
                min_samples_split=params.get('min_samples_split', 48),
                min_samples_leaf=params.get('min_samples_leaf', 38),
                subsample=params.get('subsample', 0.734),
                max_features=params.get('max_features', 'sqrt'),
                random_state=42
            )
            # 🔥 EXACT COMME L'OPTIMISATION: pas de sample_weight
            model.fit(X_train_scaled, y_train)
            logger.info(f"✅ GB standard entraîné (mode optimisé - sans sample_weights)")
        
        ml_tasks[task_id]['progress'] = 75
        ml_tasks[task_id]['stage'] = 'cross_validation'
        
        # 🔬 CROSS-VALIDATION 5-fold pour métriques fiables
        from sklearn.model_selection import cross_val_score, StratifiedKFold
        
        logger.info("🔬 Calcul des métriques par Cross-Validation 5-fold...")
        
        # Créer un nouveau modèle pour CV (sur données complètes)
        X_all = np.vstack([X_train_scaled, X_test_scaled])
        y_all = np.concatenate([y_train, y_test])
        
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        
        if model_type == 'histgb':
            cv_model = HistGradientBoostingClassifier(
                max_iter=params.get('n_estimators', 300),
                max_depth=params.get('max_depth', 2),
                learning_rate=params.get('learning_rate', 0.089),
                min_samples_leaf=params.get('min_samples_leaf', 50),
                random_state=42
            )
        else:
            cv_model = GradientBoostingClassifier(
                n_estimators=params.get('n_estimators', 271),
                max_depth=params.get('max_depth', 6),
                learning_rate=params.get('learning_rate', 0.217),
                min_samples_split=params.get('min_samples_split', 48),
                min_samples_leaf=params.get('min_samples_leaf', 38),
                subsample=params.get('subsample', 0.734),
                max_features=params.get('max_features', 'sqrt'),
                random_state=42
            )
        
        cv_accuracy = cross_val_score(cv_model, X_all, y_all, cv=cv, scoring='accuracy')
        cv_f1 = cross_val_score(cv_model, X_all, y_all, cv=cv, scoring='f1')
        
        cv_acc_mean = cv_accuracy.mean()
        cv_acc_std = cv_accuracy.std()
        cv_f1_mean = cv_f1.mean()
        
        logger.info(f"📊 CV Accuracy: {cv_acc_mean*100:.1f}% ± {cv_acc_std*100:.1f}%")
        logger.info(f"📊 CV F1 Score: {cv_f1_mean:.3f}")
        
        ml_tasks[task_id]['progress'] = 85
        ml_tasks[task_id]['stage'] = 'evaluating'
        
        # Évaluer sur holdout (pour comparaison)
        y_train_pred = model.predict(X_train_scaled)
        y_test_pred = model.predict(X_test_scaled)
        
        train_acc = accuracy_score(y_train, y_train_pred)
        test_acc = accuracy_score(y_test, y_test_pred)
        test_f1 = f1_score(y_test, y_test_pred, zero_division=0)
        test_prec = precision_score(y_test, y_test_pred, zero_division=0)
        gap = train_acc - test_acc
        
        # Sauvegarder
        models_dir = Path("optimization/saved_models")
        models_dir.mkdir(parents=True, exist_ok=True)
        
        pipeline = Pipeline([
            ('scaler', scaler),
            ('model', model)
        ])
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = models_dir / f"best_classifier_{timestamp}.pkl"
        latest_path = models_dir / "best_classifier_latest.pkl"
        
        joblib.dump(pipeline, model_path)
        joblib.dump(pipeline, latest_path)
        
        model_name = 'HistGradientBoostingClassifier' if model_type == 'histgb' else 'GradientBoostingClassifier'
        
        metadata = {
            'timestamp': timestamp,
            'best_model': model_name,
            'model_type': model_type,
            'n_samples': len(df),
            'n_train': X_train.shape[0],
            'n_test': X_test.shape[0],
            'n_features': X_train.shape[1],
            'metrics': {
                # 🔬 MÉTRIQUES CROSS-VALIDATION (les plus fiables!)
                'cv_accuracy': float(cv_acc_mean),
                'cv_accuracy_std': float(cv_acc_std),
                'cv_f1': float(cv_f1_mean),
                # Métriques holdout (pour référence)
                'train_acc': float(train_acc),
                'test_acc': float(test_acc),
                'test_f1': float(test_f1),
                'test_precision': float(test_prec),
                'gap': float(gap)
            },
            'feature_cols': feature_cols,
            'params': params
        }
        
        with open(models_dir / "best_classifier_metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        ml_tasks[task_id]['progress'] = 100
        ml_tasks[task_id]['status'] = 'completed'
        ml_tasks[task_id]['accuracy'] = float(test_acc)
        ml_tasks[task_id]['f1'] = float(test_f1)
        ml_tasks[task_id]['gap'] = float(gap)
        ml_tasks[task_id]['metrics'] = metadata['metrics']
        ml_tasks[task_id]['model_type'] = model_type
        
        logger.info(f"✅ {model_name} entraîné: Accuracy={test_acc:.1%}, F1={test_f1:.3f}, Gap={gap:.1%}")
        
    except Exception as e:
        logger.error(f"❌ Erreur _train_gradientboosting_background: {e}", exc_info=True)
        ml_tasks[task_id]['status'] = 'error'
        ml_tasks[task_id]['error'] = str(e)


# ========== OPTUNA OPTIMIZATION POUR GRADIENTBOOSTING ==========

# État global de l'optimisation
_gb_optuna_task: Dict[str, Any] = {
    'status': 'idle',  # idle, running, completed, error
    'task_id': None,
    'progress': 0,
    'current_trial': 0,
    'total_trials': 100,
    'best_score': 0,
    'best_params': None,
    'error': None,
    'started_at': None,
    'completed_at': None
}


@router.post("/optimize_gb")
async def start_gb_optuna_optimization(
    background_tasks: BackgroundTasks,
    n_trials: int = Query(100, ge=20, le=300),
    timeout_minutes: int = Query(30, ge=5, le=120)
):
    """
    🔬 Démarre l'optimisation Optuna pour GradientBoosting
    
    Args:
        n_trials: Nombre de trials (20-300)
        timeout_minutes: Timeout en minutes (5-120)
    """
    global _gb_optuna_task
    
    if _gb_optuna_task['status'] == 'running':
        return JSONResponse({
            'success': False,
            'error': 'Optimisation déjà en cours',
            'current_progress': _gb_optuna_task['progress']
        }, status_code=409)
    
    task_id = f"gb_optuna_{uuid.uuid4().hex[:8]}"
    
    _gb_optuna_task = {
        'status': 'running',
        'task_id': task_id,
        'progress': 0,
        'current_trial': 0,
        'total_trials': n_trials,
        'best_score': 0,
        'best_params': None,
        'error': None,
        'started_at': datetime.now().isoformat(),
        'completed_at': None
    }
    
    background_tasks.add_task(
        _run_gb_optuna_optimization,
        task_id,
        n_trials,
        timeout_minutes
    )
    
    return {
        'success': True,
        'task_id': task_id,
        'message': f'Optimisation Optuna démarrée ({n_trials} trials, timeout {timeout_minutes}min)',
        'status_url': '/api/ml/optimize_gb/status'
    }


@router.get("/optimize_gb/status")
async def get_gb_optuna_status():
    """
    📊 Retourne le statut de l'optimisation Optuna en cours
    """
    return _gb_optuna_task


@router.post("/optimize_gb/apply")
async def apply_gb_optuna_params():
    """
    ✅ Applique les meilleurs paramètres trouvés par Optuna dans TRADING_CONFIG
    """
    global _gb_optuna_task
    
    if not _gb_optuna_task['best_params']:
        return JSONResponse({
            'success': False,
            'error': 'Aucun paramètre optimal disponible. Lancer une optimisation d\'abord.'
        }, status_code=400)
    
    try:
        from config import TRADING_CONFIG
        from utils.config_persistence import save_config_overrides, load_config_overrides
        
        best_params = _gb_optuna_task['best_params']
        
        # Mapper les paramètres Optuna vers TRADING_CONFIG
        param_mapping = {
            'n_estimators': 'gb_n_estimators',
            'max_depth': 'gb_max_depth',
            'learning_rate': 'gb_learning_rate',
            'min_samples_split': 'gb_min_samples_split',
            'min_samples_leaf': 'gb_min_samples_leaf',
            'subsample': 'gb_subsample',
            'max_features': 'gb_max_features'
        }
        
        updated = {}
        for optuna_key, config_key in param_mapping.items():
            if optuna_key in best_params:
                value = best_params[optuna_key]
                TRADING_CONFIG[config_key] = value
                updated[config_key] = value
        
        # Persister
        overrides = load_config_overrides()
        overrides.update(updated)
        save_config_overrides(overrides)
        
        logger.info(f"✅ Paramètres Optuna appliqués: {updated}")
        
        return {
            'success': True,
            'applied_params': updated,
            'best_score': _gb_optuna_task['best_score'],
            'message': f'{len(updated)} paramètres appliqués et persistés'
        }
        
    except Exception as e:
        logger.error(f"Erreur application params Optuna: {e}", exc_info=True)
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=500)


@router.get("/optimize_gb/history")
async def get_gb_optuna_history():
    """
    📈 Retourne l'historique des optimisations Optuna
    """
    try:
        from optimization.optuna_gb_tuner import load_last_optimization_results
        
        results = load_last_optimization_results()
        if results:
            return {
                'success': True,
                'last_optimization': results
            }
        else:
            return {
                'success': True,
                'last_optimization': None,
                'message': 'Aucune optimisation précédente trouvée'
            }
            
    except Exception as e:
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=500)


async def _run_gb_optuna_optimization(task_id: str, n_trials: int, timeout_minutes: int):
    """Background task pour l'optimisation Optuna - Non bloquant pour WebSocket"""
    global _gb_optuna_task
    
    import asyncio
    
    try:
        logger.info(f"🔬 Démarrage optimisation Optuna GB (task={task_id})")
        
        from optimization.optuna_gb_tuner import GradientBoostingOptunaOptimizer
        from optimization.data.feature_loader import load_features_from_postgres
        from optimization.data.feature_engineering import calculate_derived_features
        import numpy as np
        
        # 1. Charger les données - MÊME LOGIQUE QUE TRAINING
        _gb_optuna_task['progress'] = 5
        logger.info("📊 Chargement des données depuis PostgreSQL...")
        
        # 🔥 FIX: Utiliser ml_features (pas ml_features_clean obsolète) + même filtrage que training
        from config import TRADING_CONFIG
        timeframe = TRADING_CONFIG.get('gb_timeframe_days', 730)  # 2 ans par défaut
        
        base_df = load_features_from_postgres(timeframe_days=timeframe, min_trades=30, use_clean_data=False)
        logger.info(f"📊 Données brutes chargées: {len(base_df)} trades (timeframe={timeframe} jours)")
        
        # 🔥 FILTRE STRICT: Seulement trades avec TOUS les paramètres config identiques
        initial_count = len(base_df)
        current_config = {
            # Paramètres d'entrée
            'min_score_required': TRADING_CONFIG.get('min_score_required', 6.5),
            'snr_threshold': TRADING_CONFIG.get('snr_threshold', 0.15),
            'volume_multiplier': TRADING_CONFIG.get('volume_multiplier', 0.95),
            'use_confluence': TRADING_CONFIG.get('use_confluence', True),
            'atr_min_1m': TRADING_CONFIG.get('optimal_atr_min_1m', 0.12),
            'atr_max_1m': TRADING_CONFIG.get('optimal_atr_max_1m', 0.75),
            'atr_min_5m': TRADING_CONFIG.get('optimal_atr_min_5m', 0.22),
            'atr_max_5m': TRADING_CONFIG.get('optimal_atr_max_5m', 1.4),
        }
        logger.info(f"🔧 Config actuelle: min_score={current_config['min_score_required']}, "
                   f"snr={current_config['snr_threshold']}, vol={current_config['volume_multiplier']}, "
                   f"confluence={current_config['use_confluence']}")
        
        # Construire le masque pour TOUS les paramètres
        mask = pd.Series([True] * len(base_df), index=base_df.index)
        
        if 'config_min_score_required' in base_df.columns:
            mask &= abs(base_df['config_min_score_required'] - current_config['min_score_required']) < 0.1
        
        if 'config_snr_threshold' in base_df.columns:
            mask &= abs(base_df['config_snr_threshold'] - current_config['snr_threshold']) < 0.02
        
        if 'config_volume_multiplier' in base_df.columns:
            mask &= abs(base_df['config_volume_multiplier'] - current_config['volume_multiplier']) < 0.05
        
        if 'config_use_confluence' in base_df.columns:
            mask &= base_df['config_use_confluence'] == current_config['use_confluence']
        
        # Filtres ATR
        if 'config_atr_min_1m' in base_df.columns:
            mask &= abs(base_df['config_atr_min_1m'] - current_config['atr_min_1m']) < 0.05
        
        if 'config_atr_max_1m' in base_df.columns:
            mask &= abs(base_df['config_atr_max_1m'] - current_config['atr_max_1m']) < 0.1
        
        if 'config_atr_min_5m' in base_df.columns:
            mask &= abs(base_df['config_atr_min_5m'] - current_config['atr_min_5m']) < 0.05
        
        if 'config_atr_max_5m' in base_df.columns:
            mask &= abs(base_df['config_atr_max_5m'] - current_config['atr_max_5m']) < 0.2
        
        base_df = base_df[mask]
        logger.info(f"   Après filtre config COMPLET: {len(base_df)} trades")
        
        logger.info(f"📊 Données filtrées: {len(base_df)}/{initial_count} trades utilisables")
        
        df = calculate_derived_features(base_df)
        
        if df is None or len(df) < 200:
            raise ValueError(f"Pas assez de trades pour l'optimisation: {len(df) if df is not None else 0}")
        
        # 2. Feature engineering (même que train_gb)
        _gb_optuna_task['progress'] = 15
        logger.info(f"🔧 Feature engineering sur {len(df)} trades...")
        
        # Features temporelles
        if 'timestamp' in df.columns:
            ts = pd.to_datetime(df['timestamp'])
            df['hour'] = ts.dt.hour
            df['day_of_week'] = ts.dt.dayofweek
            df['good_hour'] = df['hour'].isin([2, 12, 16]).astype(int)
            df['bad_hour'] = df['hour'].isin([4, 23, 18]).astype(int)
        
        if 'rsi_1m' in df.columns and 'rsi_5m' in df.columns:
            df['rsi_momentum'] = df['rsi_1m'] - df['rsi_5m']
        
        if 'macd_hist_1m' in df.columns and 'macd_hist_5m' in df.columns:
            df['macd_momentum'] = df['macd_hist_1m'] - df['macd_hist_5m']
        
        if 'adx_1m' in df.columns:
            df['strong_trend'] = (df['adx_1m'] > 25).astype(int)
        
        # Préparer features
        exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 'is_opportunity', 'date']
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        feature_cols = [c for c in numeric_cols if c not in exclude_cols]
        
        # Supprimer colonnes constantes et avec trop de NULL
        feature_cols = [c for c in feature_cols if df[c].nunique() > 1]
        feature_cols = [c for c in feature_cols if df[c].isnull().sum() / len(df) <= 0.3]
        
        X = df[feature_cols].fillna(0).values
        y = df['target_win'].astype(int).values
        
        if len(X) < 200:
            raise ValueError(f"Pas assez d'échantillons après feature engineering: {len(X)}")
        
        logger.info(f"✅ Dataset prêt: {X.shape[0]} samples, {X.shape[1]} features")
        
        # 3. Lancer l'optimisation dans un thread séparé pour ne pas bloquer le WebSocket
        _gb_optuna_task['progress'] = 20
        
        # Récupérer le type de modèle depuis la config
        from config import TRADING_CONFIG
        model_type = TRADING_CONFIG.get('gb_model_type', 'gb')
        logger.info(f"🔧 Type de modèle: {model_type} ({'HistGradientBoosting 10x rapide' if model_type == 'histgb' else 'GradientBoosting standard'})")
        
        optimizer = GradientBoostingOptunaOptimizer(
            n_trials=n_trials,
            timeout_minutes=timeout_minutes,
            cv_folds=5,
            model_type=model_type
        )
        
        def progress_callback(trial_num, total, score):
            _gb_optuna_task['current_trial'] = trial_num
            _gb_optuna_task['progress'] = 20 + int((trial_num / total) * 70)
            if score and score > _gb_optuna_task['best_score']:
                _gb_optuna_task['best_score'] = score
        
        # 🔥 Exécuter dans un thread séparé pour libérer l'event loop (WebSocket reste actif)
        logger.info("🔄 Lancement optimisation dans thread séparé (WebSocket reste actif)...")
        result = await asyncio.to_thread(optimizer.optimize, X, y, progress_callback)
        
        # 4. Mettre à jour le statut
        _gb_optuna_task['progress'] = 95
        
        if result['success']:
            _gb_optuna_task['best_params'] = result['best_params']
            _gb_optuna_task['best_score'] = result['best_score']
            _gb_optuna_task['status'] = 'completed'
            _gb_optuna_task['progress'] = 100
            _gb_optuna_task['completed_at'] = datetime.now().isoformat()
            
            logger.info(f"✅ Optimisation terminée: Best F1={result['best_score']:.4f}")
            logger.info(f"   Params: {result['best_params']}")
        else:
            raise Exception(result.get('error', 'Erreur inconnue'))
        
    except Exception as e:
        logger.error(f"❌ Erreur optimisation Optuna: {e}", exc_info=True)
        _gb_optuna_task['status'] = 'error'
        _gb_optuna_task['error'] = str(e)
        _gb_optuna_task['completed_at'] = datetime.now().isoformat()


# ========== BOUCLE DE VÉRIFICATION COMPLÈTE ==========

@router.get("/verify_gb/complete")
async def verify_gb_complete():
    """
    🔍 Boucle de vérification complète du système GradientBoosting
    Vérifie:
    - Configuration (TRADING_CONFIG)
    - Fichier modèle (.pkl)
    - Métadonnées modèle
    - Cohérence paramètres
    - Capacité de prédiction
    """
    verification_results = {
        'timestamp': datetime.now().isoformat(),
        'checks': [],
        'overall_status': 'OK',
        'warnings': [],
        'errors': []
    }
    
    def add_check(name: str, status: str, details: str = "", value: Any = None):
        verification_results['checks'].append({
            'name': name,
            'status': status,  # OK, WARNING, ERROR
            'details': details,
            'value': value
        })
        if status == 'ERROR':
            verification_results['errors'].append(f"{name}: {details}")
            verification_results['overall_status'] = 'ERROR'
        elif status == 'WARNING' and verification_results['overall_status'] != 'ERROR':
            verification_results['warnings'].append(f"{name}: {details}")
            verification_results['overall_status'] = 'WARNING'
    
    try:
        # 1. Vérifier TRADING_CONFIG
        from config import TRADING_CONFIG
        
        gb_params = {
            'gb_filter_enabled': TRADING_CONFIG.get('gb_filter_enabled'),
            'gb_min_confidence': TRADING_CONFIG.get('gb_min_confidence'),
            'gb_n_estimators': TRADING_CONFIG.get('gb_n_estimators'),
            'gb_max_depth': TRADING_CONFIG.get('gb_max_depth'),
            'gb_learning_rate': TRADING_CONFIG.get('gb_learning_rate'),
            'gb_min_samples_split': TRADING_CONFIG.get('gb_min_samples_split'),
            'gb_min_samples_leaf': TRADING_CONFIG.get('gb_min_samples_leaf'),
            'gb_subsample': TRADING_CONFIG.get('gb_subsample'),
            'gb_max_features': TRADING_CONFIG.get('gb_max_features'),
        }
        
        missing_params = [k for k, v in gb_params.items() if v is None]
        if missing_params:
            add_check('TRADING_CONFIG', 'ERROR', f'Paramètres manquants: {missing_params}')
        else:
            add_check('TRADING_CONFIG', 'OK', 'Tous les paramètres GB présents', gb_params)
        
        # 2. Vérifier config_overrides.json
        from utils.config_persistence import load_config_overrides
        overrides = load_config_overrides()
        
        gb_overrides = {k: v for k, v in overrides.items() if k.startswith('gb_')}
        if gb_overrides:
            add_check('config_overrides.json', 'OK', f'{len(gb_overrides)} paramètres GB persistés', gb_overrides)
        else:
            add_check('config_overrides.json', 'WARNING', 'Aucun paramètre GB persisté (valeurs par défaut)')
        
        # 3. Vérifier le fichier modèle
        from pathlib import Path
        models_dir = Path("optimization/saved_models")
        
        model_files = list(models_dir.glob("*classifier*.pkl")) + list(models_dir.glob("best_classifier*.pkl"))
        
        if model_files:
            latest_model = max(model_files, key=lambda p: p.stat().st_mtime)
            model_age_hours = (datetime.now().timestamp() - latest_model.stat().st_mtime) / 3600
            
            if model_age_hours > 168:  # Plus d'une semaine
                add_check('Fichier modèle', 'WARNING', f'Modèle ancien ({model_age_hours:.0f}h)', str(latest_model))
            else:
                add_check('Fichier modèle', 'OK', f'Modèle trouvé ({model_age_hours:.1f}h)', str(latest_model))
        else:
            add_check('Fichier modèle', 'ERROR', 'Aucun fichier modèle trouvé')
        
        # 4. Vérifier les métadonnées
        metadata_file = models_dir / "best_classifier_metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            metrics = metadata.get('metrics', {})
            test_acc = metrics.get('test_acc', 0)
            gap = metrics.get('gap', 1)
            
            if test_acc < 0.55:
                add_check('Métriques modèle', 'WARNING', f'Accuracy faible: {test_acc:.1%}', metrics)
            elif gap > 0.15:
                add_check('Métriques modèle', 'WARNING', f'Overfitting élevé: {gap:.1%}', metrics)
            else:
                add_check('Métriques modèle', 'OK', f'Accuracy={test_acc:.1%}, Gap={gap:.1%}', metrics)
        else:
            add_check('Métadonnées modèle', 'WARNING', 'Fichier metadata non trouvé')
        
        # 5. Vérifier la capacité de prédiction
        try:
            import joblib
            if model_files:
                latest_model = max(model_files, key=lambda p: p.stat().st_mtime)
                model = joblib.load(latest_model)
                
                # Déterminer le nombre de features depuis le modèle
                import numpy as np
                
                # Essayer de récupérer n_features du scaler (Pipeline) ou du modèle
                try:
                    if hasattr(model, 'named_steps') and 'scaler' in model.named_steps:
                        n_features = model.named_steps['scaler'].n_features_in_
                    elif hasattr(model, 'n_features_in_'):
                        n_features = model.n_features_in_
                    else:
                        # Charger depuis metadata
                        meta_file = models_dir / "best_classifier_metadata.json"
                        if meta_file.exists():
                            with open(meta_file, 'r') as f:
                                meta = json.load(f)
                            n_features = len(meta.get('feature_cols', [])) or 92
                        else:
                            n_features = 92  # Fallback
                except:
                    n_features = 92
                
                test_input = np.random.randn(1, n_features)
                
                try:
                    prediction = model.predict(test_input)
                    proba = model.predict_proba(test_input)
                    add_check('Capacité prédiction', 'OK', f'Prédiction OK ({n_features} features): pred={prediction[0]}')
                except Exception as pred_err:
                    add_check('Capacité prédiction', 'ERROR', f'Erreur prédiction: {pred_err}')
        except Exception as load_err:
            add_check('Chargement modèle', 'ERROR', f'Impossible de charger: {load_err}')
        
        # 6. Vérifier cohérence avec Optuna
        optuna_results = models_dir / "gb_optuna_results.json"
        if optuna_results.exists():
            with open(optuna_results, 'r') as f:
                optuna_data = json.load(f)
            
            optuna_params = optuna_data.get('best_params', {})
            
            # Comparer avec TRADING_CONFIG
            mismatches = []
            param_mapping = {
                'n_estimators': 'gb_n_estimators',
                'max_depth': 'gb_max_depth',
                'learning_rate': 'gb_learning_rate',
            }
            
            for optuna_key, config_key in param_mapping.items():
                optuna_val = optuna_params.get(optuna_key)
                config_val = gb_params.get(config_key)
                if optuna_val and config_val and optuna_val != config_val:
                    mismatches.append(f"{config_key}: config={config_val} vs optuna={optuna_val}")
            
            if mismatches:
                add_check('Cohérence Optuna', 'WARNING', f'Params différents: {mismatches}', {
                    'optuna_params': optuna_params,
                    'config_params': gb_params
                })
            else:
                add_check('Cohérence Optuna', 'OK', 'Paramètres cohérents avec Optuna')
        else:
            add_check('Résultats Optuna', 'OK', 'Pas d\'optimisation Optuna précédente (optionnel)')
        
        # Résumé
        n_ok = len([c for c in verification_results['checks'] if c['status'] == 'OK'])
        n_warn = len([c for c in verification_results['checks'] if c['status'] == 'WARNING'])
        n_err = len([c for c in verification_results['checks'] if c['status'] == 'ERROR'])
        
        verification_results['summary'] = {
            'total_checks': len(verification_results['checks']),
            'ok': n_ok,
            'warnings': n_warn,
            'errors': n_err
        }
        
        return verification_results
        
    except Exception as e:
        logger.error(f"Erreur vérification GB: {e}", exc_info=True)
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=500)
