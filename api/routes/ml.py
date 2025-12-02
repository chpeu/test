"""
API Routes ML - Machine Learning Endpoints
Refactored structure with modular organization

Phase 4 Migration Status:
- ✅ ml_common.py: Shared utilities extracted
- ✅ ml_tasks.py: Task tracking and alerts (4 routes)
- 🚧 Legacy routes: Still in ml_legacy.py (40 routes)

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
from fastapi import APIRouter

# Import modular routers
from .ml_tasks import router as tasks_router

# Import legacy routes (to be migrated)
from .ml_legacy import router as legacy_router

logger = logging.getLogger(__name__)

# Main ML router - combines all sub-routers
router = APIRouter()

# Include modular routers (migrated)
router.include_router(tasks_router, tags=["ML Tasks & Alerts"])

# Include legacy router (to be progressively removed)
# Note: This includes all 40 remaining routes that haven't been migrated yet
router.include_router(legacy_router, tags=["ML Legacy"])

logger.info("✅ ML router initialized (modular + legacy)")
logger.info("   - Migrated: 4 routes (ml_tasks.py)")
logger.info("   - Legacy: 40 routes (ml_legacy.py)")
logger.info("   - Total: 44 routes")
