"""
Analytics routes - Endpoints for general data analytics
"""

import logging
from fastapi import APIRouter
from .ml_dashboard import api_post_exit_analyze

logger = logging.getLogger(__name__)

# Router for general analytics (accessible via /api/analytics)
router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

# Re-expose the post-exit analyze endpoint under /api/analytics/post-exit/analyze
@router.post("/post-exit/analyze")
async def post_exit_analyze_alias(min_trades: int = 10, force: bool = False):
    """
    Alias pour l'analyse post-exit (supporte /api/analytics/post-exit/analyze)
    """
    return await api_post_exit_analyze(min_trades=min_trades, force=force)
