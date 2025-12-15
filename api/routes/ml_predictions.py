"""
ML Predictions - Prediction and filtering endpoints
Migrated from ml_legacy.py as part of Phase 5 modularization
"""

import logging
from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Router for predictions and filtering
router = APIRouter(prefix="/api/ml", tags=["ML Predictions"])


@router.get("/predictions/analytics")
async def get_predictions_analytics(
    model_name: Optional[str] = None,
    days: int = Query(30, ge=1, le=365)
):
    """
    Récupérer analytics des prédictions ML
    
    Args:
        model_name: Filtrer par modèle (optionnel)
        days: Nombre de jours à analyser
        
    Returns:
        Analytics: accuracy, trades exécutés, PnL moyen, etc.
    """
    try:
        from optimization.prediction_logger import get_prediction_analytics, get_best_symbols_for_ml
        
        analytics = get_prediction_analytics(model_name, days)
        best_symbols = get_best_symbols_for_ml(min_predictions=3)
        
        return {
            'analytics': analytics,
            'best_symbols': best_symbols,
            'period_days': days,
            'model_name': model_name
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_predictions_analytics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/predictions/recent")
async def get_recent_predictions(limit: int = Query(20, ge=1, le=100)):
    """
    Récupérer les prédictions récentes avec leur statut
    
    Args:
        limit: Nombre de prédictions à retourner
        
    Returns:
        Liste des prédictions récentes
    """
    try:
        from optimization.prediction_logger import get_recent_predictions as get_recent
        
        predictions = get_recent(limit)
        
        return {
            'predictions': predictions,
            'total': len(predictions)
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_recent_predictions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predictor/reload")
async def reload_predictor(model_name: str = Query('xgboost_v1')):
    """
    Recharger le predictor (utile après ré-entraînement)
    
    Args:
        model_name: Nom du modèle à recharger
        
    Returns:
        Statut du rechargement
    """
    try:
        from optimization import predictor
        
        # Reset singleton
        predictor._predictor_instance = None
        
        # Recharger
        new_predictor = predictor.get_predictor(model_name)
        
        if new_predictor.loaded:
            return {
                'status': 'success',
                'message': f'Predictor {model_name} rechargé',
                'features_count': len(new_predictor.feature_names) if new_predictor.feature_names else 0
            }
        else:
            raise HTTPException(status_code=500, detail='Échec du rechargement')
            
    except Exception as e:
        logger.error(f"❌ Erreur reload_predictor: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict")
async def predict_opportunity(
    features: Dict[str, Any],
    model_name: str = Query('xgboost_v1'),
):
    """
    Faire une prédiction ML sur une opportunité
    
    Args:
        features: Dictionnaire avec toutes les features (RSI, MACD, BB, etc.)
        model_name: Nom du modèle à utiliser (défaut: xgboost_v1)
        
    Returns:
        Prédiction avec probabilité et confiance
    """
    try:
        from optimization.predictor import predict_opportunity as predict_opp
        
        # Faire prédiction
        prediction = predict_opp(features, model_name)
        
        if prediction is None:
            raise HTTPException(
                status_code=404,
                detail=f"Modèle '{model_name}' non disponible. Entraînez d'abord le modèle."
            )
        
        return prediction
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur predict_opportunity: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict/batch")
async def predict_batch(
    opportunities: List[Dict[str, Any]],
    model_name: str = Query('xgboost_v1'),
):
    """
    Faire des prédictions ML en batch sur plusieurs opportunités
    
    Args:
        opportunities: Liste de dictionnaires de features
        model_name: Nom du modèle à utiliser
        
    Returns:
        Liste de prédictions
    """
    try:
        from optimization.predictor import get_predictor
        
        predictor = get_predictor(model_name)
        predictions = predictor.batch_predict(opportunities)
        
        # Filtrer les None
        results = [p for p in predictions if p is not None]
        
        return {
            'predictions': results,
            'total': len(opportunities),
            'successful': len(results),
            'failed': len(opportunities) - len(results)
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur predict_batch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== V2 PREDICTIONS (REGRESSION PNL%) ==========

@router.post("/predict_v2")
async def predict_pnl_v2(
    features: Dict[str, Any],
    model_name: str = Query('xgboost_v2_latest'),
):
    """
    Faire une prédiction PNL% (V2 Régression) sur une opportunité
    
    Args:
        features: Dictionnaire avec toutes les features (RSI, MACD, BB, etc.)
        model_name: Nom du modèle V2 à utiliser (défaut: xgboost_v2_latest)
        
    Returns:
        Prédiction avec PNL% prédit, classification WIN/LOSS, et metadata
    """
    try:
        from optimization.predictor_v2 import predict_pnl
        
        # Faire prédiction V2
        prediction = predict_pnl(features, model_name)
        
        if prediction is None:
            raise HTTPException(
                status_code=404,
                detail=f"Modèle V2 '{model_name}' non disponible. Entraînez d'abord le modèle V2."
            )
        
        return prediction
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur predict_pnl_v2: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict_v2/batch")
async def predict_pnl_v2_batch(
    opportunities: List[Dict[str, Any]],
    model_name: str = Query('xgboost_v2_latest'),
):
    """
    Faire des prédictions PNL% V2 en batch sur plusieurs opportunités
    
    Args:
        opportunities: Liste de dictionnaires de features
        model_name: Nom du modèle V2 à utiliser
        
    Returns:
        Liste de prédictions PNL%
    """
    try:
        from optimization.predictor_v2 import get_predictor_v2
        
        predictor = get_predictor_v2(model_name)
        predictions = predictor.batch_predict(opportunities)
        
        # Filtrer les None
        results = [p for p in predictions if p is not None]
        
        # Statistiques
        predicted_pnls = [p['predicted_pnl'] for p in results]
        avg_pnl = sum(predicted_pnls) / len(predicted_pnls) if predicted_pnls else 0
        profitable_count = sum(1 for pnl in predicted_pnls if pnl > 0)
        
        return {
            'predictions': results,
            'total': len(opportunities),
            'successful': len(results),
            'failed': len(opportunities) - len(results),
            'stats': {
                'avg_predicted_pnl': round(avg_pnl, 3),
                'profitable_count': profitable_count,
                'loss_count': len(predicted_pnls) - profitable_count,
                'profitable_pct': round((profitable_count / len(predicted_pnls) * 100), 1) if predicted_pnls else 0
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur predict_pnl_v2_batch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict_v2/filter")
async def filter_setup_with_v2(
    features: Dict[str, Any],
    min_expected_pnl: float = Query(0.3, ge=0.0, le=10.0)
):
    """
    Vérifier si un setup doit être filtré basé sur le PNL% prédit V2
    
    Args:
        features: Dictionnaire avec toutes les features
        min_expected_pnl: PNL minimum requis (%) pour accepter le trade
        
    Returns:
        Résultat du filtrage avec prédiction
    """
    try:
        from optimization.predictor_v2 import get_predictor_v2
        
        predictor = get_predictor_v2()
        should_reject, predicted_pnl, reason = predictor.should_reject_trade(
            features=features,
            min_expected_pnl=min_expected_pnl
        )
        
        return {
            'should_reject': should_reject,
            'predicted_pnl': predicted_pnl,
            'predicted_pnl_formatted': f"{predicted_pnl:+.2f}%" if predicted_pnl else None,
            'reason': reason,
            'min_expected_pnl': min_expected_pnl,
            'recommendation': 'reject' if should_reject else 'accept'
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur filter_setup_with_v2: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== ALERTS ==========


logger.info("✅ ML predictions router initialized (8 routes)")
