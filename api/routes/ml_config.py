"""
ML Configuration API - Phase 2D
================================
Endpoints pour configurer et monitorer le système ML adaptatif.

Endpoints:
- GET  /api/ml/status - Statut global du système ML
- GET  /api/ml/config - Configuration actuelle
- POST /api/ml/config - Modifier la configuration
- GET  /api/ml/thresholds - Seuils par contexte
- GET  /api/ml/drift - Historique des drifts
- POST /api/ml/reset - Réinitialiser les optimiseurs

Auteur: Cascade AI
Date: 11/12/2025
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List

from config import TRADING_CONFIG

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ml", tags=["ML Configuration"])


class MLConfigUpdate(BaseModel):
    """Modèle pour mise à jour de la configuration ML."""
    gb_filter_enabled: Optional[bool] = None
    gb_min_confidence: Optional[float] = None
    threshold_optimizer_enabled: Optional[bool] = None
    threshold_min: Optional[float] = None
    threshold_max: Optional[float] = None
    drift_detection_enabled: Optional[bool] = None
    drift_pnl_delta: Optional[float] = None
    drift_winrate_delta: Optional[float] = None


@router.get("/status")
async def get_ml_status():
    """
    Retourne le statut global du système ML.
    
    Inclut:
    - État des modules (activé/désactivé)
    - Statistiques des optimiseurs
    - Alertes de drift
    """
    try:
        status = {
            "timestamp": datetime.now().isoformat(),
            "modules": {}
        }
        
        # GradientBoosting Filter
        status["modules"]["trade_filter"] = {
            "name": "GradientBoosting Trade Filter",
            "enabled": TRADING_CONFIG.get('gb_filter_enabled', True),
            "min_confidence": TRADING_CONFIG.get('gb_min_confidence', 0.55)
        }
        
        try:
            from optimization.predictor_optimized import get_predictor
            predictor = get_predictor()
            status["modules"]["trade_filter"]["model_loaded"] = predictor.is_loaded
        except:
            status["modules"]["trade_filter"]["model_loaded"] = False
        
        # Threshold Optimizer
        status["modules"]["threshold_optimizer"] = {
            "name": "Contextual Threshold Optimizer",
            "enabled": TRADING_CONFIG.get('threshold_optimizer_enabled', False),
            "phase": "2D"
        }
        
        try:
            from core.ml import get_threshold_optimizer
            optimizer = get_threshold_optimizer()
            opt_status = optimizer.get_status()
            status["modules"]["threshold_optimizer"].update(opt_status)
        except Exception as e:
            status["modules"]["threshold_optimizer"]["error"] = str(e)
        
        # Drift Detector
        status["modules"]["drift_detector"] = {
            "name": "Market Drift Detector",
            "enabled": TRADING_CONFIG.get('drift_detection_enabled', True),
            "phase": "2D"
        }
        
        try:
            from core.ml import get_drift_detector
            detector = get_drift_detector()
            det_status = detector.get_status()
            status["modules"]["drift_detector"].update(det_status)
        except Exception as e:
            status["modules"]["drift_detector"]["error"] = str(e)
        
        # Modules Phase 3 (à venir)
        status["modules"]["regime_classifier"] = {
            "name": "ML Regime Classifier",
            "enabled": False,
            "phase": "3A",
            "status": "not_implemented"
        }
        
        status["modules"]["sltp_predictor"] = {
            "name": "Dynamic SL/TP Predictor",
            "enabled": False,
            "phase": "3B",
            "status": "not_implemented"
        }
        
        status["modules"]["online_learning"] = {
            "name": "Online Learning",
            "enabled": False,
            "phase": "3C",
            "status": "not_implemented"
        }
        
        return status
        
    except Exception as e:
        logger.error(f"Erreur get_ml_status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_ml_config():
    """Retourne la configuration ML actuelle."""
    return {
        "gb_filter_enabled": TRADING_CONFIG.get('gb_filter_enabled', True),
        "gb_min_confidence": TRADING_CONFIG.get('gb_min_confidence', 0.55),
        "threshold_optimizer_enabled": TRADING_CONFIG.get('threshold_optimizer_enabled', False),
        "threshold_min": TRADING_CONFIG.get('threshold_min', 0.45),
        "threshold_max": TRADING_CONFIG.get('threshold_max', 0.70),
        "drift_detection_enabled": TRADING_CONFIG.get('drift_detection_enabled', True),
        "drift_pnl_delta": TRADING_CONFIG.get('drift_pnl_delta', 0.002),
        "drift_winrate_delta": TRADING_CONFIG.get('drift_winrate_delta', 0.005)
    }


@router.post("/config")
async def update_ml_config(config: MLConfigUpdate):
    """Met à jour la configuration ML."""
    updated = {}
    
    try:
        if config.gb_filter_enabled is not None:
            TRADING_CONFIG['gb_filter_enabled'] = config.gb_filter_enabled
            updated['gb_filter_enabled'] = config.gb_filter_enabled
        
        if config.gb_min_confidence is not None:
            val = max(0.25, min(0.80, config.gb_min_confidence))
            TRADING_CONFIG['gb_min_confidence'] = val
            updated['gb_min_confidence'] = val
        
        if config.threshold_optimizer_enabled is not None:
            TRADING_CONFIG['threshold_optimizer_enabled'] = config.threshold_optimizer_enabled
            updated['threshold_optimizer_enabled'] = config.threshold_optimizer_enabled
            logger.info(f"✅ Threshold optimizer {'activé' if config.threshold_optimizer_enabled else 'désactivé'}")
        
        if config.threshold_min is not None:
            val = max(0.30, min(0.60, config.threshold_min))
            TRADING_CONFIG['threshold_min'] = val
            updated['threshold_min'] = val
        
        if config.threshold_max is not None:
            val = max(0.50, min(0.80, config.threshold_max))
            TRADING_CONFIG['threshold_max'] = val
            updated['threshold_max'] = val
        
        if config.drift_detection_enabled is not None:
            TRADING_CONFIG['drift_detection_enabled'] = config.drift_detection_enabled
            updated['drift_detection_enabled'] = config.drift_detection_enabled
            
            # Mettre à jour le détecteur
            try:
                from core.ml import get_drift_detector
                detector = get_drift_detector()
                detector.enabled = config.drift_detection_enabled
            except:
                pass
        
        return {
            "success": True,
            "updated": updated,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur update_ml_config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/thresholds")
async def get_thresholds():
    """Retourne tous les seuils par contexte."""
    try:
        from core.ml import get_threshold_optimizer
        optimizer = get_threshold_optimizer()
        
        return {
            "enabled": optimizer.enabled,
            "status": optimizer.get_status(),
            "thresholds": optimizer.get_all_thresholds(),
            "recommendations": optimizer.get_recommendations(min_trades=10)
        }
    except Exception as e:
        logger.error(f"Erreur get_thresholds: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drift")
async def get_drift_history():
    """Retourne l'historique des drifts détectés."""
    try:
        from core.ml import get_drift_detector
        detector = get_drift_detector()
        
        return {
            "status": detector.get_status(),
            "history": detector.get_history(limit=20)
        }
    except Exception as e:
        logger.error(f"Erreur get_drift_history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
async def reset_optimizers(target: str = "all"):
    """
    Réinitialise les optimiseurs ML.
    
    Args:
        target: "threshold", "drift", ou "all"
    """
    try:
        reset_results = {}
        
        if target in ["threshold", "all"]:
            from core.ml import get_threshold_optimizer
            optimizer = get_threshold_optimizer()
            optimizer.reset_all()
            reset_results["threshold_optimizer"] = "reset"
        
        if target in ["drift", "all"]:
            from core.ml import get_drift_detector
            detector = get_drift_detector()
            detector.reset()
            reset_results["drift_detector"] = "reset"
        
        return {
            "success": True,
            "reset": reset_results,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur reset_optimizers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/context")
async def get_performance_by_context():
    """Retourne les performances par contexte (régime, session)."""
    try:
        from core.ml import get_threshold_optimizer
        optimizer = get_threshold_optimizer()
        
        thresholds = optimizer.get_all_thresholds()
        
        # Formater pour le frontend
        by_context = []
        for context_key, data in thresholds.items():
            by_context.append({
                "context": context_key,
                "regime": data.get('regime', 'UNKNOWN'),
                "session": data.get('session', 'UNKNOWN'),
                "hour_group": data.get('hour_group', 0),
                "trades": data.get('trades', 0),
                "wins": data.get('wins', 0),
                "winrate": data.get('winrate', 0.5),
                "pnl": data.get('pnl', 0),
                "threshold": data.get('threshold', 0.55)
            })
        
        # Trier par nombre de trades
        by_context.sort(key=lambda x: x['trades'], reverse=True)
        
        return {
            "by_context": by_context,
            "recommendations": optimizer.get_recommendations(min_trades=10),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur get_performance_by_context: {e}")
        raise HTTPException(status_code=500, detail=str(e))
