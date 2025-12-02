"""
ML Tasks & Alerts - Task tracking and ML alerting
Extracted from ml.py for better maintainability
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import List

from .ml_common import ml_tasks, _get_task_from_store

logger = logging.getLogger(__name__)

# Router for tasks and alerts
router = APIRouter(prefix="/api/ml", tags=["ML Tasks"])


# ========== TASK ENDPOINTS ==========

@router.get("/tasks/{task_id}")
async def get_task_status_plural(task_id: str):
    """
    Récupérer le statut d'une tâche ML (plural endpoint).

    Args:
        task_id: Identifiant de la tâche

    Returns:
        Statut de la tâche
    """
    task = _get_task_from_store(task_id)
    return task


@router.get("/task/{task_id}")
async def get_task_status_singular(task_id: str):
    """
    Récupérer le statut d'une tâche ML (singular endpoint).

    Args:
        task_id: Identifiant de la tâche

    Returns:
        Statut de la tâche
    """
    task = _get_task_from_store(task_id)
    return task


# ========== ALERTS ENDPOINTS ==========

@router.get("/alerts/history")
async def get_alerts_history(limit: int = Query(20, ge=1, le=100)):
    """
    Récupérer l'historique des alertes ML.

    Args:
        limit: Nombre d'alertes à retourner

    Returns:
        Historique des alertes
    """
    try:
        from optimization.ml_alerts import get_alert_manager

        manager = get_alert_manager()
        history = manager.get_alert_history(limit)

        return {
            'alerts': history,
            'total': len(history)
        }

    except Exception as e:
        logger.error(f"❌ Erreur get_alerts_history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/test")
async def test_alert(
    symbol: str = Query('BTCUSDT'),
    channels: List[str] = Query(['console'])
):
    """
    Tester le système d'alertes avec une prédiction fictive.

    Args:
        symbol: Symbole pour le test
        channels: Canaux à tester

    Returns:
        Résultat du test
    """
    try:
        from optimization.ml_alerts import send_ml_alert

        # Créer prédiction fictive
        test_prediction = {
            'prediction': 'win',
            'confidence': 0.85,
            'symbol': symbol,
            'direction': 'LONG',
            'entry_price': 50000.0,
            'model': 'test_model'
        }

        # Envoyer alert avec tous les paramètres requis
        result = send_ml_alert(
            prediction=test_prediction,
            symbol=symbol,
            scan_id=None,
            min_confidence=0.0,  # Accept any confidence for test
            channels=channels
        )

        return {
            'success': True,
            'status': 'success',
            'test_prediction': test_prediction,
            'channels': channels,
            'result': result or {'status': 'success', 'symbol': symbol}
        }

    except Exception as e:
        logger.error(f"❌ Erreur test_alert: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


logger.info("✅ ML tasks router initialized (4 routes)")
