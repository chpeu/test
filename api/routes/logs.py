"""
Routes API pour la gestion des logs et erreurs
"""
from fastapi import APIRouter, Query
import logging
from utils.error_history import get_error_history

logger = logging.getLogger(__name__)
logs_router = APIRouter()

@logs_router.get('/errors')
def get_errors(
    limit: int = Query(None, description="Limite du nombre d'erreurs à retourner"),
    offset: int = Query(0, description="Décalage pour la pagination")
):
    """Récupérer l'historique complet des erreurs"""
    try:
        error_history = get_error_history()
        
        all_errors = error_history.get_errors()
        total_count = len(all_errors)
        
        # Pagination
        if limit:
            start_idx = offset
            end_idx = start_idx + limit
            errors = all_errors[start_idx:end_idx]
        else:
            errors = all_errors
            
        return {
            'success': True,
            'errors': errors,
            'total_count': total_count,
            'returned_count': len(errors)
        }
    except Exception as e:
        logger.error(f"Erreur récupération erreurs: {e}")
        return {
            'success': False,
            'error': str(e)
        }

@logs_router.get('/errors/count')
def get_error_count():
    """Récupérer le nombre total d'erreurs"""
    try:
        error_history = get_error_history()
        count = error_history.get_error_count()
        
        return {
            'success': True,
            'count': count
        }
    except Exception as e:
        logger.error(f"Erreur récupération nombre erreurs: {e}")
        return {
            'success': False,
            'error': str(e)
        }

@logs_router.get('/errors/recent')
def get_recent_errors(
    limit: int = Query(50, description="Limite du nombre d'erreurs récentes")
):
    """Récupérer les erreurs récentes (pour compatibilité WebSocket)"""
    try:
        error_history = get_error_history()
        errors = error_history.get_recent_errors(limit=limit)
        
        return {
            'success': True,
            'errors': errors
        }
    except Exception as e:
        logger.error(f"Erreur récupération erreurs récentes: {e}")
        return {
            'success': False,
            'error': str(e)
        }

@logs_router.post('/errors/clear')
def clear_errors():
    """Vider l'historique des erreurs"""
    try:
        error_history = get_error_history()
        error_history.clear_errors()
        
        return {
            'success': True,
            'message': 'Historique des erreurs vidé'
        }
    except Exception as e:
        logger.error(f"Erreur vidage erreurs: {e}")
        return {
            'success': False,
            'error': str(e)
        }
