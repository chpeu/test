"""
Volet HTTP du verrou de visite.

La logique (et le motif affiché) vit dans `utils/visit_lock.py` pour que `core/`
puisse l'utiliser sans importer FastAPI. Ce module-ci ajoute seulement la
réponse de refus et remet les noms déjà employés par les routes.
"""

from fastapi.responses import JSONResponse

from utils.visit_lock import RAISON, log_refus, scan_lock_active

__all__ = ["RAISON", "lock_response", "log_refus", "scan_lock_active"]


def lock_response() -> JSONResponse:
    """Refus HTTP : 403 + motif lisible par l'interface."""
    return JSONResponse({"success": False, "locked": True, "error": RAISON}, status_code=403)
