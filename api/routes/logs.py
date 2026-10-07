from fastapi import APIRouter
from fastapi.responses import JSONResponse
import logging
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
async def api_get_errors(limit: int = 50, offset: int = 0, source: str = "memory"):
    """Récupérer les erreurs avec pagination.

    source='memory' (défaut) : ErrorHistoryManager en mémoire.
    source='pg' : table scan_errors de PostgreSQL (historique persistant).
    """
    if source == "pg":
        pg_result = await _get_pg_errors(limit=limit, offset=offset)
        if pg_result is not None:
            return pg_result
        # PG indisponible → repli sur la mémoire
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


async def _get_pg_errors(limit: int, offset: int):
    """Erreurs persistées en PostgreSQL (scan_errors). None si PG indisponible."""
    try:
        from core.callbacks.scanner_loop import get_pg_datalogger
        pg_datalogger = get_pg_datalogger()
        if not pg_datalogger or not getattr(pg_datalogger, "enabled", False):
            return None
        conn = pg_datalogger._get_connection()
        if not conn:
            return None
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM scan_errors WHERE error_type IN ('ERROR', 'CRITICAL')")
            total_count = cursor.fetchone()[0]
            cursor.execute(
                "SELECT timestamp, error_type, error_message, error_stack "
                "FROM scan_errors WHERE error_type IN ('ERROR', 'CRITICAL') "
                "ORDER BY timestamp DESC LIMIT %s OFFSET %s",
                (limit, offset),
            )
            errors = [
                {
                    "id": f"error_{row[0].timestamp()}_{hash(row[2])}",
                    "timestamp": row[0].isoformat(),
                    "level": row[1],
                    "message": row[2],
                    "detail": row[3],
                }
                for row in cursor.fetchall()
            ]
            return {"success": True, "errors": errors, "total_count": total_count}
        finally:
            cursor.close()
            pg_datalogger._return_connection(conn)
    except Exception as e:
        logger.debug(f"PG logs indisponible, repli mémoire: {e}")
        return None

@router.get('/errors/recent')
async def api_get_recent_errors(limit: int = 50):
    """Récupérer les erreurs récentes"""
    return await api_get_errors(limit=limit, offset=0)

@router.post('/errors/clear')
async def api_clear_errors(source: str = "memory"):
    """Vider l'historique d'erreurs (memory, ou pg = table scan_errors)."""
    if source == "pg":
        try:
            from core.callbacks.scanner_loop import get_pg_datalogger
            pg_datalogger = get_pg_datalogger()
            if pg_datalogger and getattr(pg_datalogger, "enabled", False):
                conn = pg_datalogger._get_connection()
                if conn:
                    cursor = conn.cursor()
                    try:
                        cursor.execute("DELETE FROM scan_errors WHERE error_type IN ('ERROR', 'CRITICAL')")
                        deleted = cursor.rowcount
                        conn.commit()
                        return {"success": True, "message": f"{deleted} erreurs supprimées"}
                    finally:
                        cursor.close()
                        pg_datalogger._return_connection(conn)
        except Exception as e:
            logger.error(f"❌ Erreur suppression PG: {e}")
            return JSONResponse({"success": False, "error": str(e)})
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
