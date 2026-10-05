"""
ML EV Analysis - Endpoint for EV-based threshold analysis
"""

import logging
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ml", tags=["ML EV Analysis"])


@router.get("/ev-analysis")
async def get_ev_analysis(
    days: int = Query(default=180, ge=7, le=365, description="Fenêtre en jours"),
    test_ratio: float = Query(default=0.30, ge=0.1, le=0.5, description="Ratio test (split temporel)"),
    step: int = Query(default=5, ge=1, le=20, description="Pas des seuils en %"),
    training_filter: bool = Query(default=True, description="Appliquer filtre training (LIVE+ATR+exit_reason)")
):
    """
    Analyse EV net par ml_confidence.
    Retourne les meilleurs seuils, la table des seuils, et les buckets.
    """
    try:
        from scripts.analyze_ml_thresholds import run_ev_analysis
        
        result = run_ev_analysis(
            timeframe_days=days,
            test_ratio=test_ratio,
            step=step,
            use_training_filter=training_filter
        )
        
        if 'error' in result:
            return JSONResponse(
                content={'success': False, 'error': result['error']},
                status_code=400
            )
        
        return {
            'success': True,
            'data': result
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur ev-analysis: {e}", exc_info=True)
        return JSONResponse(
            content={'success': False, 'error': str(e)},
            status_code=500
        )
