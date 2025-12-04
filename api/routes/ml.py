"""
API Routes ML - Machine Learning Endpoints
Refactored structure with modular organization

Phase 4-5 Migration Status:
- ✅ ml_common.py: Shared utilities extracted
- ✅ ml_tasks.py: Task tracking and alerts (4 routes)
- ✅ ml_dashboard.py: Dashboard and analytics (4 routes)
- ✅ ml_predictions.py: Predictions and filtering (8 routes)
- ✅ ml_models.py: Model management and features (6 routes)
- 🚧 Legacy routes: Still in ml_legacy.py (22 routes)

Migration Strategy:
Routes are being progressively migrated from ml_legacy.py to focused modules:
- ml_dashboard.py (4 routes) - Dashboard & analytics
- ml_models.py (6 routes) - Model management & features
- ml_predictions.py (8 routes) - Predictions & filtering
- ml_training.py (7 routes) - Training & verification
- ml_optimization.py (14 routes) - Hyperparameter tuning
- ml_tasks.py (4 routes) - Task management & alerts ✅

This file serves as the main router aggregator.
"""

import logging
from fastapi import APIRouter, BackgroundTasks

# Import modular routers
from .ml_tasks import router as tasks_router
from .ml_dashboard import router as dashboard_router
from .ml_predictions import router as predictions_router
from .ml_models import router as models_router

# Import legacy routes (to be migrated)
from .ml_legacy import router as legacy_router

# Re-export common utilities for backward compatibility with tests
from .ml_common import (
    ml_tasks,
    METRIC_OPTIONS,
    LAST_RUNS_FILE,
    metric_runs_cache,
    _load_metric_runs_cache,
    _save_metric_runs_cache,
    record_metric_run,
    get_metric_runs_snapshot,
    _get_task_from_store,
    update_task_status,
    create_task,
)

# Re-export legacy functions for backward compatibility with tests
from .ml_legacy import (
    _train_xgboost_background,
)

# Alias for test compatibility
def get_ml_task_status(task_id: str):
    """Alias for _get_task_from_store for test compatibility."""
    return _get_task_from_store(task_id)

logger = logging.getLogger(__name__)

# Main ML router - combines all sub-routers
router = APIRouter()

# Include modular routers (migrated)
router.include_router(tasks_router, tags=["ML Tasks & Alerts"])
router.include_router(dashboard_router, tags=["ML Dashboard & Analytics"])
router.include_router(predictions_router, tags=["ML Predictions"])
router.include_router(models_router, tags=["ML Models & Features"])

# Include legacy router (to be progressively removed)
# Note: This includes all 22 remaining routes that haven't been migrated yet
router.include_router(legacy_router, tags=["ML Legacy"])

logger.info("✅ ML router initialized (modular + legacy)")
logger.info("   - Migrated: 22 routes (tasks + dashboard + predictions + models)")
logger.info("   - Legacy: 22 routes (ml_legacy.py)")
logger.info("   - Total: 44 routes")
