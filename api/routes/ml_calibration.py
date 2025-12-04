"""
API Routes for ML Auto-Calibration System
==========================================

Endpoints pour gérer et consulter la calibration ML.
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml/calibration", tags=["ML Calibration"])


class CalibrationStatsResponse(BaseModel):
    """Réponse avec les statistiques de calibration"""
    enabled: bool
    min_trades: int
    min_winrate: float
    stats: Dict[str, Dict[str, Any]]  # {direction: {bucket: stats}}
    total_trades: int
    learning_phase: bool


class CalibrationConfigUpdate(BaseModel):
    """Mise à jour de la configuration de calibration"""
    ml_calibration_enabled: Optional[bool] = None
    ml_calib_live_weight: Optional[float] = None
    ml_calib_dryrun_weight: Optional[float] = None
    ml_calib_decay_days: Optional[int] = None
    ml_calib_min_trades: Optional[int] = None
    ml_calib_min_winrate: Optional[float] = None


class SeedRequest(BaseModel):
    """Requête pour seeder la calibration"""
    days: int = 30


@router.get("/stats", response_model=CalibrationStatsResponse)
async def get_calibration_stats():
    """
    Récupère les statistiques de calibration ML.
    
    Returns:
        Statistiques par direction et bucket de confiance
    """
    try:
        from ml.calibration import get_calibration_manager
        from config import TRADING_CONFIG
        
        calib_manager = get_calibration_manager()
        all_stats = calib_manager.get_all_stats()
        
        # Convertir en format JSON serializable
        stats_json = {}
        total_trades = 0
        
        for direction, buckets in all_stats.items():
            stats_json[direction] = {}
            for bucket, stats in buckets.items():
                stats_json[direction][bucket] = {
                    'weighted_wins': stats.weighted_wins,
                    'weighted_total': stats.weighted_total,
                    'total_trades': stats.total_trades,
                    'actual_winrate': stats.actual_winrate,
                    'avg_pnl_pct': stats.avg_pnl_pct,
                    'total_pnl_usdt': stats.total_pnl_usdt,
                }
                total_trades += stats.total_trades
        
        min_trades = TRADING_CONFIG.get('ml_calib_min_trades', 30)
        
        return CalibrationStatsResponse(
            enabled=TRADING_CONFIG.get('ml_calibration_enabled', True),
            min_trades=min_trades,
            min_winrate=TRADING_CONFIG.get('ml_calib_min_winrate', 40.0),
            stats=stats_json,
            total_trades=total_trades,
            learning_phase=total_trades < min_trades
        )
        
    except Exception as e:
        logger.error(f"Erreur récupération stats calibration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
async def reset_calibration(reason: str = "manual_reset"):
    """
    Remet à zéro les statistiques de calibration.
    
    À utiliser après une ré-optimisation du modèle ML.
    """
    try:
        from ml.calibration import get_calibration_manager
        
        calib_manager = get_calibration_manager()
        success = calib_manager.reset_calibration(reason=reason)
        
        if success:
            return {"status": "success", "message": f"Calibration resetée ({reason})"}
        else:
            raise HTTPException(status_code=500, detail="Échec reset calibration")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur reset calibration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/seed")
async def seed_calibration(request: SeedRequest):
    """
    Initialise la calibration à partir des trades historiques.
    
    Args:
        days: Nombre de jours d'historique à utiliser
        
    Returns:
        Nombre de trades traités
    """
    try:
        from ml.calibration import get_calibration_manager
        
        calib_manager = get_calibration_manager()
        
        # Reset d'abord
        calib_manager.reset_calibration(reason="seed_from_history")
        
        # Seed avec historique
        count = calib_manager.seed_from_historical_trades(days=request.days)
        
        return {
            "status": "success",
            "trades_processed": count,
            "days": request.days
        }
        
    except Exception as e:
        logger.error(f"Erreur seed calibration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config")
async def update_calibration_config(config: CalibrationConfigUpdate):
    """
    Met à jour la configuration de calibration.
    """
    try:
        from config import TRADING_CONFIG
        from utils.config_persistence import save_config_overrides
        
        updates = {}
        
        if config.ml_calibration_enabled is not None:
            updates['ml_calibration_enabled'] = config.ml_calibration_enabled
            TRADING_CONFIG['ml_calibration_enabled'] = config.ml_calibration_enabled
            
        if config.ml_calib_live_weight is not None:
            updates['ml_calib_live_weight'] = config.ml_calib_live_weight
            TRADING_CONFIG['ml_calib_live_weight'] = config.ml_calib_live_weight
            
        if config.ml_calib_dryrun_weight is not None:
            updates['ml_calib_dryrun_weight'] = config.ml_calib_dryrun_weight
            TRADING_CONFIG['ml_calib_dryrun_weight'] = config.ml_calib_dryrun_weight
            
        if config.ml_calib_decay_days is not None:
            updates['ml_calib_decay_days'] = config.ml_calib_decay_days
            TRADING_CONFIG['ml_calib_decay_days'] = config.ml_calib_decay_days
            
        if config.ml_calib_min_trades is not None:
            updates['ml_calib_min_trades'] = config.ml_calib_min_trades
            TRADING_CONFIG['ml_calib_min_trades'] = config.ml_calib_min_trades
            
        if config.ml_calib_min_winrate is not None:
            updates['ml_calib_min_winrate'] = config.ml_calib_min_winrate
            TRADING_CONFIG['ml_calib_min_winrate'] = config.ml_calib_min_winrate
        
        if updates:
            save_config_overrides(updates)
            logger.info(f"✅ Config calibration mise à jour: {updates}")
        
        return {
            "status": "success",
            "updated": updates
        }
        
    except Exception as e:
        logger.error(f"Erreur update config calibration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check/{direction}/{confidence}")
async def check_trade_eligibility(direction: str, confidence: float):
    """
    Vérifie si un trade serait accepté par la calibration.
    
    Utile pour tester avant d'exécuter un trade.
    """
    try:
        from ml.calibration import get_calibration_manager
        
        calib_manager = get_calibration_manager()
        should_take, calibrated_wr, reason = calib_manager.should_take_trade(
            direction=direction.upper(),
            ml_confidence=confidence
        )
        
        bucket = calib_manager.get_confidence_bucket(confidence)
        
        return {
            "direction": direction.upper(),
            "ml_confidence": confidence,
            "bucket": bucket,
            "would_take_trade": should_take,
            "calibrated_winrate": calibrated_wr,
            "reason": reason
        }
        
    except Exception as e:
        logger.error(f"Erreur check eligibility: {e}")
        raise HTTPException(status_code=500, detail=str(e))
