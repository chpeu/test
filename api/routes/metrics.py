"""
Routes API pour les métriques
"""

import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/metrics", tags=["metrics"])

@router.get("/conditions")
async def get_condition_metrics():
    """Métriques par condition"""
    from core.metrics import condition_metrics
    stats = condition_metrics.get_stats_summary()
    return JSONResponse(stats)
