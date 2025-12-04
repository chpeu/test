"""
ML Common - Shared utilities and state for ML routes
Extracted from ml.py for better maintainability
"""

import copy
import json
import logging
import threading
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

# ========== GLOBAL STATE ==========

# Task tracking for async ML operations
ml_tasks: Dict[str, Dict[str, Any]] = {}

# Metric optimization tracking
METRIC_OPTIONS = ["trading_composite", "f1_score", "accuracy", "roc_auc"]
LAST_RUNS_FILE = Path("data/optuna_last_runs.json")
_metric_cache_lock = threading.Lock()
metric_runs_cache: Dict[str, Any] = {"metrics": {}}


# ========== CACHE MANAGEMENT ==========

def _load_metric_runs_cache() -> None:
    """Load metric runs cache from disk."""
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


def _save_metric_runs_cache() -> None:
    """Save metric runs cache to disk."""
    LAST_RUNS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LAST_RUNS_FILE.open('w') as f:
        json.dump(metric_runs_cache, f, indent=2)


def record_metric_run(metric: str, run_data: Dict[str, Any]) -> None:
    """
    Enregistrer la dernière optimisation et le record global pour chaque métrique.

    Args:
        metric: Nom de la métrique
        run_data: Données de l'optimisation
    """
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
    """
    Obtenir un snapshot thread-safe du cache des métriques.

    Returns:
        Copie profonde du cache de métriques
    """
    with _metric_cache_lock:
        return copy.deepcopy(metric_runs_cache)


# ========== TASK MANAGEMENT ==========

def _get_task_from_store(task_id: str) -> Dict[str, Any]:
    """
    Récupère le statut d'une tâche ML depuis le store.

    Args:
        task_id: Identifiant de la tâche

    Returns:
        Dictionnaire avec le statut de la tâche
    """
    return ml_tasks.get(task_id, {'status': 'unknown', 'task_id': task_id})


def update_task_status(task_id: str, status: str, **kwargs) -> None:
    """
    Met à jour le statut d'une tâche ML.

    Args:
        task_id: Identifiant de la tâche
        status: Nouveau statut
        **kwargs: Données supplémentaires à ajouter
    """
    if task_id in ml_tasks:
        ml_tasks[task_id]['status'] = status
        ml_tasks[task_id].update(kwargs)


def create_task(task_id: str = None, **initial_data) -> str:
    """
    Crée une nouvelle tâche ML et retourne son ID.

    Args:
        task_id: ID optionnel (généré si non fourni)
        **initial_data: Données initiales de la tâche

    Returns:
        ID de la tâche créée
    """
    import uuid
    if task_id is None:
        task_id = str(uuid.uuid4())

    ml_tasks[task_id] = {
        'task_id': task_id,
        'status': 'created',
        **initial_data
    }
    return task_id


# ========== INITIALIZATION ==========

# Load cache at module import
_load_metric_runs_cache()

logger.info("✅ ML common utilities initialized")
