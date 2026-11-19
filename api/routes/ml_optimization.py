"""
Routes ML - recherche d'hyperparametres (Optuna, XGBoost, GradientBoosting).

Extraite de l'ancien ml_legacy.py le 17/11/2026, logique inchangee.
"""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Query, Request
from fastapi.responses import JSONResponse

# Fichier ou le tour d'optimisation GradientBoosting laisse ses resultats. Nomme
# ici (et pas repete trois fois en dur) pour qu'un test puisse le pointer ailleurs
# sans ecrire dans le depot.
RESULTATS_GB = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'optuna_gb_results.json')

from .ml_common import (
    METRIC_OPTIONS,
    chemin_config_autorise,
    get_metric_runs_snapshot,
    ml_tasks,
    record_metric_run,
)

logger = logging.getLogger(__name__)

# Journal dedie a l'optimisation (logs/optimization_debug.log)
opt_logger = logging.getLogger("optimization_debug")
opt_logger.setLevel(logging.DEBUG)
if not opt_logger.handlers:
    os.makedirs('logs', exist_ok=True)
    fh = logging.FileHandler('logs/optimization_debug.log', encoding='utf-8')
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    opt_logger.addHandler(fh)

optuna_v2_state = {'is_running': False, 'study': None, 'progress': 0, 'current_trial': 0, 'total_trials': 0, 'best_params': None, 'best_value': None, 'run_best_params': None, 'run_best_score': None, 'run_best_trial': None, 'n_trials': 0}

_gb_optuna_task: Dict[str, Any] = {'status': 'idle', 'task_id': None, 'progress': 0, 'current_trial': 0, 'total_trials': 100, 'best_score': 0, 'best_params': None, 'error': None, 'started_at': None, 'completed_at': None}

router = APIRouter(prefix="/api/ml", tags=["ML Optimization"])

@router.get("/optimize/summary")
async def get_metric_summary():
    """Renvoyer la dernière optimisation disponible pour chaque métrique."""
    snapshot = get_metric_runs_snapshot()
    metrics_map = snapshot.get("metrics", {})
    for metric in METRIC_OPTIONS:
        metrics_map.setdefault(metric, {"metric": metric, "last_run": None})
    return {"metrics": metrics_map}

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
        
        logger.info(f"[TRAIN] Optimisation hyperparamètres démarrée (task_id={task_id}, trials={n_trials})")
        
        return {
            'task_id': task_id,
            'status': 'pending',
            'message': f'Optimisation démarrée ({n_trials} trials)',
            'trades_count': trades_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[FAIL] Erreur start_optimization: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

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
        
        logger.info(f"[START] Optimisation en cours (task_id={task_id})")
        
        # Détecter GPU si demandé
        gpu_id = None
        if use_gpu:
            try:
                import torch
                if torch.cuda.is_available():
                    gpu_id = 0
                    logger.info("[GPU] GPU détecté et activé")
            except Exception:
                logger.debug('ml_legacy.py: exception silencieuse (avant: pass)', exc_info=True)
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
        
        logger.info(f"[OK] Optimisation terminée (task_id={task_id}, best_score={tuner.study.best_value:.4f})")
        
        # Préparer les données pour record_metric_run
        run_data = {
            'metric': metric,
            'score': latest_run_trial.value if latest_run_trial is not None else tuner.study.best_value,
            'params': (latest_run_trial.params if latest_run_trial is not None else tuner.study.best_params),
            'trial_number': (latest_run_trial.number if latest_run_trial is not None else tuner.study.best_trial.number),
            'total_trials': len(tuner.study.trials),
            'datetime': datetime.now().isoformat()
        }
        
        logger.info(f"[DATA] Enregistrement métrique '{metric}' avec score={run_data['score']:.4f}, params={list(run_data['params'].keys())}")
        record_metric_run(metric, run_data)
        logger.info(f"[OK] Métrique '{metric}' enregistrée dans optuna_last_runs.json")
        
    except Exception as e:
        logger.error(f"[FAIL] Erreur optimisation: {e}", exc_info=True)
        
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
        logger.error(f"[FAIL] Erreur get_optimization_history: {e}", exc_info=True)
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
        logger.error(f"[FAIL] Erreur get_best_hyperparameters: {e}", exc_info=True)
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
        # premier controle: ou est-ce qu'on va ecrire ?
        chemin_config = chemin_config_autorise(config_file)

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
        if os.path.exists(chemin_config):
            with open(chemin_config, 'r') as f:
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
        
        with open(chemin_config, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"[SAVE] Paramètres sauvegardés dans {chemin_config}")
        
        # Recharger immédiatement les overrides pour mettre à jour TRADING_CONFIG
        try:
            from config import TRADING_CONFIG
            from utils.config_persistence import apply_config_overrides
            apply_config_overrides(TRADING_CONFIG)
            logger.info("[OK] TRADING_CONFIG rechargé avec les paramètres ML")
        except Exception as reload_err:
            logger.error(f"[FAIL] Impossible de recharger TRADING_CONFIG: {reload_err}")
        
        # 🔥 AUTO-RESET CALIBRATION: Réinitialiser la calibration après application de nouveaux params
        try:
            from ml.calibration import get_calibration_manager
            manager = get_calibration_manager()
            # Utiliser un reason explicite pour l'historique
            if manager.reset_calibration(reason="auto_reset_after_optimization"):
                logger.info("✅ Calibration réinitialisée automatiquement après optimisation")
            else:
                logger.warning("⚠️ Echec du reset automatique de la calibration")
        except Exception as calib_err:
            logger.error(f"❌ Erreur lors du reset automatique de calibration: {calib_err}")

        logger.info(f"[OK] Paramètres appliqués à {config_file}")
        
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
        logger.error(f"[FAIL] Erreur apply_best_hyperparameters: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

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
        logger.info(f"[TRAIN] Optimisation {model_name} démarrée{speed_info} (task_id={task_id}, trials={n_trials})")
        
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
        logger.error(f"[FAIL] Erreur start_gb_optimization: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

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
        logger.info(f"[START] Optimisation {model_name}{speed_info} en cours (task_id={task_id})")
        
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
        
        # L'optimiseur conserve lui-même les meilleurs paramètres (optimizer.best_params,
        # lu juste en dessous) : la valeur de retour n'était que stockée deux fois.
        optimizer.optimize(n_trials=n_trials, timeout_minutes=timeout_minutes)
        
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
        results_path = RESULTATS_GB
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
        
        logger.info(f"[SAVE] Résultats sauvegardés: {results_path}")
        
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
        
        logger.info(f"[OK] Optimisation GradientBoosting terminée: test_acc={metrics['test_accuracy']:.4f}, gap={metrics['overfitting_gap']:.4f}")
        
    except Exception as e:
        logger.error(f"[FAIL] Erreur optimisation GradientBoosting: {e}", exc_info=True)
        
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
        # premier controle: ou est-ce qu'on va ecrire ?
        chemin_config = chemin_config_autorise(config_file)

        if not params_to_apply:
            # Charger depuis le dernier résultat sauvegardé
            results_path = RESULTATS_GB
            if os.path.exists(results_path):
                with open(results_path, 'r') as f:
                    results = json.load(f)
                    params_to_apply = results.get('best_params', {})
            else:
                raise HTTPException(400, "Aucun paramètre fourni et aucune optimisation GB trouvée")
        
        # Sauvegarder dans config_overrides.json
        if os.path.exists(chemin_config):
            with open(chemin_config, 'r') as f:
                config = json.load(f)
        else:
            config = {}
        
        # Mapping des paramètres HistGradientBoosting
        gb_mapping = {
            'max_iter': 'gb_max_iter',
            'max_depth': 'gb_max_depth',
            'learning_rate': 'gb_learning_rate',
            'min_samples_leaf': 'gb_min_samples_leaf',
            'l2_regularization': 'gb_l2_regularization'
        }
        
        applied_params = {}
        for param, value in params_to_apply.items():
            if param in gb_mapping:
                config_key = gb_mapping[param]
                config[config_key] = value
                applied_params[config_key] = value
        
        with open(chemin_config, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Recharger config
        try:
            from config import TRADING_CONFIG
            from utils.config_persistence import apply_config_overrides
            apply_config_overrides(TRADING_CONFIG)
            logger.info("[OK] TRADING_CONFIG recharge avec params GradientBoosting")
        except Exception as reload_err:
            logger.warning(f"[WARN] Impossible de recharger TRADING_CONFIG: {reload_err}")
        
        logger.info(f"[OK] Parametres GradientBoosting appliques: {applied_params}")
        
        return {
            'success': True,
            'message': f'Paramètres GradientBoosting appliqués à {config_file}',
            'params': applied_params,
            'config_file': config_file
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[FAIL] Erreur apply_gb_params: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.get("/optimize/gb/results")
async def get_gradientboosting_results():
    """
    Récupérer les résultats de la dernière optimisation GradientBoosting
    
    Returns:
        Meilleurs params, métriques et historique
    """
    try:
        results_path = RESULTATS_GB

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
        logger.error(f"[FAIL] Erreur get_gb_results: {e}", exc_info=True)
        return {
            'found': False,
            'error': str(e)
        }

@router.post("/optimize/auto/start")
async def start_auto_optimization(request: Request):
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
        
        # 🔧 FIX: Utiliser un Thread au lieu de asyncio.create_task
        # asyncio.create_task() peut orpheliner la tâche après le retour de la requête
        import threading
        
        def run_optimization_thread():
            """Wrapper pour exécuter l'optimisation dans un thread"""
            import asyncio
            # Créer une nouvelle event loop pour ce thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    _run_auto_optimization_background(
                        task_id,
                        n_splits,
                        timeframe_days,
                        min_trades
                    )
                )
            finally:
                loop.close()
        
        thread = threading.Thread(target=run_optimization_thread, daemon=True)
        thread.start()
        
        logger.info(f"[START] Auto-optimisation ML demarree dans thread (task_id={task_id})")
        
        return {
            'task_id': task_id,
            'status': 'pending',
            'message': f'Auto-optimisation démarrée ({n_splits} splits)'
        }
        
    except Exception as e:
        logger.error(f"[FAIL] Erreur start_auto_optimization: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

async def _run_auto_optimization_background(
    task_id: str,
    n_splits: int,
    timeframe_days: int,
    min_trades: int
):
    """Exécute l'auto-optimisation en background (NON-BLOQUANT)"""
    import asyncio
    import sys
    import platform
    
    opt_logger.info(f"[START] BACKGROUND TASK STARTED: task_id={task_id}")
    
    try:
        ml_tasks[task_id]['status'] = 'running'
        ml_tasks[task_id]['progress'] = 5
        ml_tasks[task_id]['message'] = 'Démarrage...'
        opt_logger.info(f"[DATA] Task {task_id} status set to 'running'")
        
        # Exécuter le script d'optimisation
        script_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'scripts', 'auto_optimize_ml.py'
        )
        
        ml_tasks[task_id]['progress'] = 10
        ml_tasks[task_id]['message'] = 'Lancement de l\'optimisation...'
        
        opt_logger.info(f"[DATA] Launching script: {script_path}")
        opt_logger.info(f"[DATA] Python executable: {sys.executable}")
        
        # 🔧 FIX: Utiliser asyncio.create_subprocess_exec (non-bloquant)
        # Sur Windows, ajouter creationflags pour éviter les erreurs de pipe asyncio
        subprocess_kwargs = {
            'stdout': asyncio.subprocess.PIPE,
            'stderr': asyncio.subprocess.PIPE
        }
        
        if platform.system() == 'Windows':
            import subprocess as sp
            # CREATE_NO_WINDOW évite les problèmes de console sur Windows
            subprocess_kwargs['creationflags'] = sp.CREATE_NO_WINDOW
        
        process = await asyncio.create_subprocess_exec(
            sys.executable, script_path, 
            '--splits', str(n_splits),
            '--timeframe', str(timeframe_days),
            '--min-trades', str(min_trades),
            **subprocess_kwargs
        )
        
        # 🔧 NOUVEAU: Lire stdout en temps réel pour récupérer la progression
        async def read_progress():
            """Lit stdout en temps réel et met à jour la progression"""
            opt_logger.info(f"[DATA] Démarrage lecture stdout pour task {task_id}")
            try:
                while True:
                    # Utiliser readline() qui est safe avec asyncio.subprocess
                    line_bytes = await process.stdout.readline()
                    if not line_bytes:
                        opt_logger.info(f"[DATA] Fin de stdout pour task {task_id}")
                        break
                        
                    try:
                        # Essayer utf-8 puis cp1252 (windows)
                        line_str = line_bytes.decode('utf-8').strip()
                    except UnicodeDecodeError:
                        line_str = line_bytes.decode('cp1252', errors='ignore').strip()
                    
                    if not line_str:
                        continue

                    # Logger tout pour debug
                    if 'PROGRESS:' in line_str:
                        opt_logger.info(f"[SCRIPT] {line_str}")
                    else:
                        opt_logger.debug(f"[SCRIPT STDOUT] {line_str}")
                    
                    # Parser les lignes PROGRESS:XX:message
                    if line_str.startswith('PROGRESS:'):
                        try:
                            parts = line_str.split(':', 2)
                            if len(parts) >= 3:
                                progress = int(parts[1])
                                message = parts[2]
                                # Mettre à jour la tâche
                                ml_tasks[task_id]['progress'] = progress
                                ml_tasks[task_id]['message'] = message
                                opt_logger.info(f"[DATA] UPDATE TASK {task_id}: {progress}% - {message}")
                        except (ValueError, IndexError) as e:
                            opt_logger.warning(f"[PARSE] Parse error: {e} - line: {line_str}")
                    
                    # Détecter les erreurs Python
                    elif "Traceback" in line_str or "Error:" in line_str:
                        opt_logger.error(f"[SCRIPT ERROR] {line_str}")
                        
            except Exception as e:
                opt_logger.error(f"[READ] Erreur lecture stdout: {e}", exc_info=True)
        
        # Lancer la lecture de progression en parallèle
        progress_task = asyncio.create_task(read_progress())
        
        # Attendre avec timeout (non-bloquant pour le reste de l'app)
        # 🔧 FIX: Augmenter timeout à 60 minutes pour les gros datasets avec grid search
        try:
            # Attendre que le process finisse
            await asyncio.wait_for(process.wait(), timeout=3600)  # 60 minutes max
            # Récupérer stderr pour les erreurs
            stderr_bytes = await process.stderr.read()
            try:
                stderr = stderr_bytes.decode('utf-8')
            except Exception:
                stderr = stderr_bytes.decode('cp1252', errors='ignore')
                
            if stderr:
                opt_logger.warning(f"[SCRIPT STDERR] {stderr}")
                
        except asyncio.TimeoutError as timeout_exc:
            process.kill()
            await process.wait()
            progress_task.cancel()
            opt_logger.error("Timeout: optimisation trop longue (>60 min)")
            raise Exception("Timeout: optimisation trop longue (>60 min)") from timeout_exc
        
        # Annuler la tâche de progression si encore active
        progress_task.cancel()
        
        if process.returncode != 0:
            opt_logger.error(f"Script failed with return code {process.returncode}")
            raise Exception(f"Script failed: {stderr}")
        
        ml_tasks[task_id]['progress'] = 90
        ml_tasks[task_id]['message'] = 'Lecture des résultats...'
        opt_logger.info("Lecture des résultats...")
        
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
                
                # Seuil optimal - utiliser best_balanced pour trading (meilleur compromis precision/recall)
                results['optimal_threshold'] = results['optimal_thresholds'].get('best_balanced', 0.50)
        
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
                        'recall': float(row['recall']),
                        'predicted_wins': int(row.get('predicted_wins', 0)),
                        'total_samples': int(row.get('total_samples', 0))
                    })
            results['threshold_analysis'] = threshold_analysis
        
        ml_tasks[task_id]['status'] = 'completed'
        ml_tasks[task_id]['progress'] = 100
        ml_tasks[task_id]['message'] = 'Optimisation terminée!'
        ml_tasks[task_id]['results'] = results
        
        logger.info(f"[OK] Auto-optimisation terminee (task_id={task_id})")
        
    except Exception as e:
        ml_tasks[task_id]['status'] = 'failed'
        ml_tasks[task_id]['error'] = str(e)
        logger.error(f"[FAIL] Auto-optimisation failed: {e}", exc_info=True)

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
        
        # Mapping des paramètres HistGradientBoosting
        param_mapping = {
            'max_depth': 'gb_max_depth',
            'learning_rate': 'gb_learning_rate',
            'max_iter': 'gb_max_iter',
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
            logger.info("[OK] TRADING_CONFIG recharge avec auto-optimisation")
        except Exception as reload_err:
            logger.warning(f"[WARN] Impossible de recharger TRADING_CONFIG: {reload_err}")
        
        # 🔥 AUTO-RESET CALIBRATION: Réinitialiser la calibration après auto-optimisation
        try:
            from ml.calibration import get_calibration_manager
            manager = get_calibration_manager()
            if manager.reset_calibration(reason="auto_reset_after_auto_optimization"):
                logger.info("[OK] Calibration réinitialisée automatiquement après auto-optimisation")
            else:
                logger.warning("[WARN] Echec du reset automatique de la calibration")
        except Exception as calib_err:
            logger.error(f"[FAIL] Erreur lors du reset automatique de calibration: {calib_err}")

        logger.info(f"[OK] Auto-optimisation appliquee: {applied_params}")
        
        return {
            'success': True,
            'message': 'Paramètres auto-optimisés appliqués',
            'params': applied_params,
            'optimal_threshold': optimal_threshold,
            'metrics': results.get('metrics', {})
        }
        
    except Exception as e:
        logger.error(f"[FAIL] Erreur apply_auto_optimization: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

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
        
        logger.info(f"[TRAIN] Optimisation V2 démarrée ({n_trials} trials)")
        
        return {
            'status': 'started',
            'message': f'Optimisation V2 démarrée ({n_trials} trials)',
            'n_trials': n_trials,
            'trades_count': trades_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[FAIL] Erreur start_optimization_v2: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

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
        
        logger.info("[START] Optimisation V2 en cours")
        
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
        
        logger.info(f"[OK] Optimisation V2 terminée: R²={study.best_value:.3f}")
        
    except Exception as e:
        logger.error(f"[FAIL] Erreur _optimize_v2_background: {e}", exc_info=True)
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
        logger.error(f"[FAIL] Erreur get_optimization_v2_status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

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
        
        logger.info(f"[SAVE] Application params V2: {params_dict}")
        
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
                logger.warning(f"[WARN] Paramètre V2 non-standard ignoré: {param}")
                continue
            config_key = f"ml_v2_{param}"
            config[config_key] = value
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"[SAVE] Paramètres V2 sauvegardés dans {config_file}")
        
        # Recharger TRADING_CONFIG
        try:
            from utils.config_persistence import apply_config_overrides
            apply_config_overrides(TRADING_CONFIG)
            logger.info("[OK] TRADING_CONFIG rechargé avec params V2")
            logger.info(f"[CHECK] Vérification: ml_v2_max_depth = {TRADING_CONFIG.get('ml_v2_max_depth')}")
            logger.info(f"[CHECK] Vérification: ml_v2_learning_rate = {TRADING_CONFIG.get('ml_v2_learning_rate')}")
        except Exception as reload_err:
            logger.error(f"[FAIL] Impossible de recharger TRADING_CONFIG: {reload_err}")
        
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
        logger.error(f"[FAIL] Erreur apply_v2_hyperparameters: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

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
        
        logger.info(f"[OK] Paramètres Optuna appliqués: {updated}")
        
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
        logger.info(f"[CV] Démarrage optimisation Optuna GB (task={task_id})")
        
        from optimization.optuna_gb_tuner import GradientBoostingOptunaOptimizer
        from optimization.data.feature_loader import load_features_from_postgres
        from optimization.data.feature_engineering import calculate_derived_features
        import numpy as np
        
        # 1. Charger les données - MÊME LOGIQUE QUE TRAINING
        _gb_optuna_task['progress'] = 5
        logger.info("[DATA] Chargement des données depuis PostgreSQL...")
        
        # 🔥 FIX: Utiliser ml_features (pas ml_features_clean obsolète) + même filtrage que training
        from config import TRADING_CONFIG
        timeframe = TRADING_CONFIG.get('gb_timeframe_days', 730)  # 2 ans par défaut
        
        base_df = load_features_from_postgres(timeframe_days=timeframe, min_trades=30, use_clean_data=False)
        logger.info(f"[DATA] Données brutes chargées: {len(base_df)} trades (timeframe={timeframe} jours)")
        
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
        logger.info(f"[CONFIG] Config actuelle: min_score={current_config['min_score_required']}, "
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
        
        logger.info(f"[DATA] Données filtrées: {len(base_df)}/{initial_count} trades utilisables")
        
        df = calculate_derived_features(base_df)
        
        if df is None or len(df) < 200:
            raise ValueError(f"Pas assez de trades pour l'optimisation: {len(df) if df is not None else 0}")
        
        # 2. Feature engineering (même que train_gb)
        _gb_optuna_task['progress'] = 15
        logger.info(f"[CONFIG] Feature engineering sur {len(df)} trades...")
        
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
        
        logger.info(f"[OK] Dataset prêt: {X.shape[0]} samples, {X.shape[1]} features")
        
        # 3. Lancer l'optimisation dans un thread séparé pour ne pas bloquer le WebSocket
        _gb_optuna_task['progress'] = 20
        
        # Récupérer le type de modèle depuis la config
        from config import TRADING_CONFIG
        model_type = TRADING_CONFIG.get('gb_model_type', 'gb')
        logger.info(f"[CONFIG] Type de modèle: {model_type} ({'HistGradientBoosting 10x rapide' if model_type == 'histgb' else 'GradientBoosting standard'})")
        
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
        logger.info("[RELOAD] Lancement optimisation dans thread séparé (WebSocket reste actif)...")
        result = await asyncio.to_thread(optimizer.optimize, X, y, progress_callback)
        
        # 4. Mettre à jour le statut
        _gb_optuna_task['progress'] = 95
        
        if result['success']:
            _gb_optuna_task['best_params'] = result['best_params']
            _gb_optuna_task['best_score'] = result['best_score']
            _gb_optuna_task['status'] = 'completed'
            _gb_optuna_task['progress'] = 100
            _gb_optuna_task['completed_at'] = datetime.now().isoformat()
            
            logger.info(f"[OK] Optimisation terminée: Best F1={result['best_score']:.4f}")
            logger.info(f"   Params: {result['best_params']}")
        else:
            raise Exception(result.get('error', 'Erreur inconnue'))
        
    except Exception as e:
        logger.error(f"[FAIL] Erreur optimisation Optuna: {e}", exc_info=True)
        _gb_optuna_task['status'] = 'error'
        _gb_optuna_task['error'] = str(e)
        _gb_optuna_task['completed_at'] = datetime.now().isoformat()
