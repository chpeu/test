from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
import logging
from typing import Optional, Dict, List
import time
from utils.error_history import get_error_history

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/logs", tags=["logs"])


def get_recent_logs(limit: int = 50):
    """Compatibilité tests: retourner liste d'erreurs récentes."""
    try:
        error_history = get_error_history()
        errors = error_history.get_errors()
        return errors[:limit]
    except Exception:
        return []

@router.get('/errors')
async def api_get_errors(limit: int = 50, offset: int = 0):
    """Récupérer les erreurs avec pagination depuis ErrorHistoryManager (en mémoire)"""
    try:
        error_history = get_error_history()
        errors = error_history.get_errors()
        
        # Pagination
        paged_errors = errors[offset:offset+limit]
        
        return {
            "success": True,
            "errors": paged_errors,
            "total_count": len(errors),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"❌ Erreur api_get_errors: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@router.get('/errors/recent')
async def api_get_recent_errors(limit: int = 50):
    """Récupérer les erreurs récentes"""
    return await api_get_errors(limit=limit, offset=0)

@router.post('/errors/clear')
async def api_clear_errors():
    """Vider toutes les erreurs du gestionnaire en mémoire"""
    try:
        error_history = get_error_history()
        error_history.clear_errors()
        return {"success": True, "message": "Historique des erreurs vidé"}
    except Exception as e:
        logger.error(f"❌ Erreur api_clear_errors: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@router.post("/test/trigger-error")
async def api_trigger_test_error(error_type: str = "test", message: str = "Erreur de test pour vérifier la persistance"):
    """🧪 ENDPOINT DE TEST: Déclencher une erreur fictive"""
    try:
        from utils.logging_utils import add_log
        await add_log('ERROR', f"Test Error: {error_type}", message)
        return {"success": True, "message": f"Erreur de test '{error_type}' déclenchée"}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})
