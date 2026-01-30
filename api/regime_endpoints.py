"""
API Endpoints pour Market Regime et Trading Circuit Breaker - Sprint 1

Auteur: Cascade AI
Date: 07/12/2025
"""

import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Router FastAPI
router = APIRouter(prefix="/api", tags=["regime", "circuit-breaker"])


def get_current_regime():
    """Compatibilité tests: retourner le régime courant ou UNKNOWN."""
    try:
        from core.market_regime_selector import get_regime_selector
        selector = get_regime_selector()
        status = selector.get_status()
        return status.get("current_regime", "UNKNOWN")
    except Exception:
        return "UNKNOWN"


# ==============================================================================
# MARKET REGIME ENDPOINTS
# ==============================================================================

@router.get("/regime/status")
async def get_regime_status():
    """
    Récupérer le statut actuel du régime de marché.
    
    Returns:
        JSONResponse avec:
        - enabled: Fonctionnalité activée ou non
        - current_regime: CALME, NORMAL, VOLATILE, CHOPPY, UNKNOWN
        - avg_atr: ATR moyen calculé
        - avg_adx: ADX moyen
        - last_check: Dernière vérification
        - next_check: Prochaine vérification prévue
        - config_active: Configuration active pour ce régime
    """
    try:
        from config import TRADING_CONFIG
        from core.market_regime_selector import get_regime_selector
        
        # 🔥 FIX: Inclure l'état enabled pour le frontend
        enabled = TRADING_CONFIG.get('market_regime_enabled', True)
        tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
        
        selector = get_regime_selector()
        status = selector.get_status()
        
        return JSONResponse({
            "success": True,
            "enabled": enabled,
            "tp_sl_mode": tp_sl_mode,
            **status
        })
    except Exception as e:
        logger.error(f"❌ Erreur récupération statut régime: {e}")
        return JSONResponse({
            "success": False,
            "enabled": False,
            "error": str(e),
            "current_regime": "UNKNOWN",
            "avg_atr": 0,
            "avg_adx": 0
        }, status_code=500)


@router.post("/regime/force-check")
async def force_regime_check():
    """
    Forcer une vérification immédiate du régime de marché.
    
    Calcule l'ATR moyen sur les top pairs et met à jour le régime.
    
    Returns:
        JSONResponse avec le nouveau statut du régime
    """
    try:
        from config import TRADING_CONFIG
        from core.market_regime_selector import get_regime_selector
        
        selector = get_regime_selector()
        
        # Récupérer les ATR depuis le scanner ou une source de données
        atr_values = []
        adx_values = []
        
        try:
            # Essayer de récupérer depuis le scanner actif via StateManager
            from core.state_manager import get_state_manager
            state = get_state_manager()
            top_pairs = state.top_pairs
            
            if top_pairs:
                for pair_data in top_pairs[:10]:
                    if isinstance(pair_data, dict):
                        atr = pair_data.get('atr_percent') or pair_data.get('atr', 0)
                        adx = pair_data.get('adx', 25)
                        if atr and atr > 0:
                            atr_values.append(float(atr))
                            adx_values.append(float(adx))
        except Exception as e:
            logger.warning(f"⚠️ Impossible de récupérer ATR depuis scanner: {e}")
        
        # Si pas de données, utiliser des valeurs par défaut mais signaler le problème
        using_defaults = False
        if not atr_values:
            logger.warning("⚠️ Pas de données ATR disponibles, utilisation valeurs par défaut")
            atr_values = [0.25]  # Valeur moyenne par défaut
            adx_values = [25.0]
            using_defaults = True
        
        # 🔥 FIX: Logger le nombre de samples pour debug
        logger.info(f"🔍 Force check avec {len(atr_values)} samples (defaults={using_defaults})")
        
        # Forcer la vérification
        new_regime, changed = await selector.check_regime(
            atr_values=atr_values,
            adx_values=adx_values,
            force=True,
            trigger="manual"
        )
        
        status = selector.get_status()
        
        # 🔥 FIX: Ajouter info sur les defaults dans la réponse
        if using_defaults:
            status['warning'] = "Données ATR non disponibles, valeurs par défaut utilisées"
        
        return JSONResponse({
            "success": True,
            "changed": changed,
            "message": f"Régime vérifié: {new_regime.value}" + (" (changement)" if changed else ""),
            "tp_sl_mode": TRADING_CONFIG.get('tp_sl_mode', 'FIXE'),
            **status
        })
        
    except Exception as e:
        logger.error(f"❌ Erreur force check régime: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@router.get("/regime/history")
async def get_regime_history(limit: int = 20):
    """
    Récupérer l'historique des changements de régime.
    
    Args:
        limit: Nombre maximum d'entrées (défaut: 20)
    
    Returns:
        JSONResponse avec liste des changements
    """
    try:
        from core.market_regime_selector import get_regime_selector
        
        selector = get_regime_selector()
        history = selector.get_history(limit=limit)
        
        return JSONResponse({
            "success": True,
            "count": len(history),
            "history": history
        })
    except Exception as e:
        logger.error(f"❌ Erreur récupération historique régime: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e),
            "history": []
        }, status_code=500)


@router.get("/regime/thresholds")
async def get_regime_thresholds():
    """
    Récupérer les seuils de configuration par régime.
    
    Returns:
        JSONResponse avec les seuils ATR/ADX/score pour chaque régime
    """
    try:
        from core.market_regime_selector import get_regime_selector
        
        selector = get_regime_selector()
        thresholds = selector.get_regime_thresholds()
        
        return JSONResponse({
            "success": True,
            "thresholds": thresholds
        })
    except Exception as e:
        logger.error(f"❌ Erreur récupération seuils régime: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@router.post("/regime/thresholds")
async def update_regime_thresholds(data: Dict[str, Any]):
    """
    Mettre à jour les seuils d'un régime.
    
    Args:
        data: {
            "regime": "CALME" | "NORMAL" | "VOLATILE" | "CHOPPY",
            "atr_min": float (optionnel),
            "atr_max": float (optionnel),
            "min_score": float (optionnel)
        }
    
    Returns:
        JSONResponse avec succès/échec
    """
    try:
        from core.market_regime_selector import get_regime_selector
        
        regime_name = data.get("regime", "").upper()
        if not regime_name:
            raise HTTPException(status_code=400, detail="Paramètre 'regime' requis")
        
        selector = get_regime_selector()
        success = selector.update_regime_threshold(
            regime_name=regime_name,
            atr_min=data.get("atr_min"),
            atr_max=data.get("atr_max"),
            min_score=data.get("min_score")
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=f"Régime inconnu: {regime_name}")
        
        return JSONResponse({
            "success": True,
            "message": f"Seuils du régime {regime_name} mis à jour"
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur mise à jour seuils régime: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


# ==============================================================================
# TRADING CIRCUIT BREAKER ENDPOINTS
# ==============================================================================

@router.get("/circuit-breaker/trading/status")
async def get_trading_cb_status():
    """
    Récupérer le statut du Circuit Breaker Trading.
    
    Returns:
        JSONResponse avec:
        - enabled: Fonctionnalité activée ou non
        - can_trade: True si trading autorisé
        - state: ACTIVE, PAUSED, STOPPED
        - consecutive_losses: Nombre de pertes consécutives
        - daily_pnl_pct: PnL journalier en %
        - score_boost: Boost appliqué au score minimum
        - paused_until: Date/heure de fin de pause (si applicable)
        - thresholds: Configuration des seuils
    """
    try:
        from config import TRADING_CONFIG
        from core.trading_circuit_breaker import get_trading_circuit_breaker
        
        # 🔥 FIX: Inclure l'état enabled pour le frontend
        enabled = TRADING_CONFIG.get('trading_circuit_breaker_enabled', True)
        
        cb = get_trading_circuit_breaker()
        status = cb.get_status()
        
        return JSONResponse({
            "success": True,
            "enabled": enabled,
            **status
        })
    except Exception as e:
        logger.error(f"❌ Erreur récupération statut CB trading: {e}")
        return JSONResponse({
            "success": False,
            "enabled": False,
            "error": str(e),
            "can_trade": True,
            "state": "UNKNOWN",
            "consecutive_losses": 0,
            "daily_pnl_pct": 0
        }, status_code=500)


@router.post("/circuit-breaker/trading/reset")
async def reset_trading_cb():
    """
    Réinitialiser manuellement le Circuit Breaker Trading.
    
    Utilisé pour reprendre le trading après une pause ou un arrêt.
    
    Returns:
        JSONResponse avec le nouveau statut
    """
    try:
        from core.trading_circuit_breaker import get_trading_circuit_breaker
        
        cb = get_trading_circuit_breaker()
        
        # Récupérer l'état avant reset
        status_before = cb.get_status()
        
        # Reset
        cb.reset(manual=True)
        
        # Récupérer l'état après reset
        status_after = cb.get_status()
        
        logger.info(
            f"🔄 Trading Circuit Breaker réinitialisé | "
            f"État avant: {status_before['state']} | "
            f"État après: {status_after['state']}"
        )
        
        return JSONResponse({
            "success": True,
            "message": "Circuit Breaker Trading réinitialisé",
            "status_before": status_before,
            "status_after": status_after
        })
    except Exception as e:
        logger.error(f"❌ Erreur reset CB trading: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@router.get("/circuit-breaker/trading/events")
async def get_trading_cb_events(limit: int = 20):
    """
    Récupérer l'historique des événements du Circuit Breaker Trading.
    
    Args:
        limit: Nombre maximum d'événements (défaut: 20)
    
    Returns:
        JSONResponse avec liste des événements (pause, resume, stop, reset)
    """
    try:
        from core.trading_circuit_breaker import get_trading_circuit_breaker
        
        cb = get_trading_circuit_breaker()
        events = cb.get_events(limit=limit)
        
        return JSONResponse({
            "success": True,
            "count": len(events),
            "events": events
        })
    except Exception as e:
        logger.error(f"❌ Erreur récupération événements CB: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e),
            "events": []
        }, status_code=500)


@router.post("/circuit-breaker/trading/config")
async def update_trading_cb_config(data: Dict[str, Any]):
    """
    Mettre à jour la configuration du Circuit Breaker Trading.
    
    Args:
        data: {
            "max_consecutive_losses": int (optionnel),
            "daily_drawdown_pause_pct": float (optionnel),
            "daily_drawdown_stop_pct": float (optionnel),
            "pause_duration_minutes": int (optionnel),
            "score_boost_per_loss": float (optionnel)
        }
    
    Returns:
        JSONResponse avec le nouveau statut
    """
    try:
        from core.trading_circuit_breaker import get_trading_circuit_breaker
        
        cb = get_trading_circuit_breaker()
        
        cb.update_config(
            max_consecutive_losses=data.get("max_consecutive_losses"),
            daily_drawdown_pause_pct=data.get("daily_drawdown_pause_pct"),
            daily_drawdown_stop_pct=data.get("daily_drawdown_stop_pct"),
            pause_duration_minutes=data.get("pause_duration_minutes"),
            score_boost_per_loss=data.get("score_boost_per_loss")
        )
        
        return JSONResponse({
            "success": True,
            "message": "Configuration mise à jour",
            "status": cb.get_status()
        })
    except Exception as e:
        logger.error(f"❌ Erreur mise à jour config CB: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


# ==============================================================================
# WEBSOCKET COMMANDS REGISTRATION
# ==============================================================================

def register_websocket_commands(ws_manager):
    """
    Enregistrer les commandes WebSocket pour régime et circuit breaker.
    
    Args:
        ws_manager: Instance du WebSocketManager
    """
    
    @ws_manager.command('get_regime_status')
    async def handle_get_regime_status(data: Dict, websocket):
        """Récupérer statut régime via WebSocket"""
        try:
            result = await get_regime_status()
            return result.body.decode() if hasattr(result, 'body') else result
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @ws_manager.command('force_regime_check')
    async def handle_force_regime_check(data: Dict, websocket):
        """Forcer vérification régime via WebSocket"""
        try:
            result = await force_regime_check()
            return result.body.decode() if hasattr(result, 'body') else result
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @ws_manager.command('get_trading_cb_status')
    async def handle_get_trading_cb_status(data: Dict, websocket):
        """Récupérer statut CB trading via WebSocket"""
        try:
            result = await get_trading_cb_status()
            return result.body.decode() if hasattr(result, 'body') else result
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @ws_manager.command('reset_trading_cb')
    async def handle_reset_trading_cb(data: Dict, websocket):
        """Reset CB trading via WebSocket"""
        try:
            result = await reset_trading_cb()
            return result.body.decode() if hasattr(result, 'body') else result
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    logger.info("✅ Commandes WebSocket régime & CB trading enregistrées")
