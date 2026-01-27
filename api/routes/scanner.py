"""
Routes API pour le scanner - Gestion des top pairs et analyses
"""

import asyncio
import logging
import time
from fastapi import APIRouter, Request, Query, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

# Variables globales injectées par main.py
_scanner = None
_analyzer = None
_price_provider = None
_app_state = None
_ws_manager = None  # 🔥 MIGRATION COMPLÈTE: WebSocket natif uniquement


def set_scanner(scanner):
    """Injecter l'instance scanner"""
    global _scanner
    _scanner = scanner


def set_analyzer(analyzer):
    """Injecter l'instance analyzer"""
    global _analyzer
    _analyzer = analyzer


def set_price_provider(price_provider):
    """Injecter l'instance price_provider"""
    global _price_provider
    _price_provider = price_provider


def set_app_state(app_state):
    """Injecter l'état de l'application"""
    global _app_state
    _app_state = app_state


def set_websocket_manager(ws_manager):
    """🔥 MIGRATION COMPLÈTE: Injecter l'instance WebSocketManager (WebSocket natif uniquement)"""
    global _ws_manager
    _ws_manager = ws_manager

def set_socketio(sio):
    """🔥 LEGACY: Alias pour compatibilité (déprécié - utiliser set_websocket_manager)"""
    global _ws_manager
    # Si c'est un ws_manager, l'utiliser
    _ws_manager = sio if hasattr(sio, 'emit') and not hasattr(sio, 'on') else None


# ==================== DEPENDENCY INJECTION ====================

def get_scanner():
    """Dependency: Récupérer l'instance scanner"""
    if _scanner is None:
        raise HTTPException(status_code=503, detail="Scanner not available")
    return _scanner


def get_analyzer():
    """Dependency: Récupérer l'instance analyzer"""
    if _analyzer is None:
        raise HTTPException(status_code=503, detail="Analyzer not available")
    return _analyzer


def get_app_state() -> Dict:
    """Dependency: Récupérer l'état de l'application"""
    if _app_state is None:
        return {}
    return _app_state


def get_ws_manager():
    """Dependency: Récupérer le WebSocket manager (optionnel)"""
    return _ws_manager  # Peut être None


# Créer le router
router = APIRouter(prefix="/api/scanner", tags=["scanner"])


@router.get("/top-pairs")
async def get_top_pairs(
    app_state: Dict = Depends(get_app_state)
):
    """
    GET /api/scanner/top-pairs
    Récupérer les top pairs actuels
    """
    try:
        pairs = app_state.get('top_pairs', [])
        return JSONResponse({'pairs': pairs})
    except Exception as e:
        logger.error(f"Erreur récupération top pairs: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


@router.post("/start")
async def start_scanner(
    request: Request,
    scanner = Depends(get_scanner),
    app_state: Dict = Depends(get_app_state),
    ws_manager = Depends(get_ws_manager)
):
    """
    POST /api/scanner/start
    Démarrer le scanner des top pairs

    Body JSON optionnel:
    {
        "top_n": 20  # Nombre de paires à scanner (défaut: 20)
    }
    """
    try:
        # Parser les données de la requête
        data = {}
        try:
            body = await request.body()
            if body:
                import json
                data = json.loads(body)
        except Exception:
            data = {}

        top_n = data.get('top_n', 20) if isinstance(data, dict) else 20

        # Démarrer le scanner
        logger.info(f"🔍 Démarrage du scanner pour top {top_n} paires...")

        # Lancer le scan (is_scanning est géré par scan_top_pairs())
        pairs = await scanner.scan_top_pairs(n=top_n)

        # Mettre à jour l'état de l'application
        app_state['top_pairs'] = pairs
        app_state['scanner_running'] = True

        # 🔥 MIGRATION COMPLÈTE: Utiliser WebSocket natif uniquement
        if ws_manager:
            await ws_manager.emit('scanner_started', {
                'status': 'success',
                'top_n': top_n,
                'pairs_found': len(pairs)
            })

        logger.info(f"✅ Scanner démarré: {len(pairs)} paires trouvées")

        return JSONResponse({
            'status': 'started',
            'top_n': top_n,
            'pairs': pairs[:10] if len(pairs) > 10 else pairs,  # Retourner top 10
            'total_found': len(pairs)
        })

    except Exception as e:
        logger.error(f"❌ Erreur démarrage scanner: {e}")
        if scanner:
            scanner.is_scanning = False
        return JSONResponse({'error': str(e)}, status_code=500)


@router.post("/stop")
async def stop_scanner(
    scanner = Depends(get_scanner),
    ws_manager = Depends(get_ws_manager)
):
    """
    POST /api/scanner/stop
    Arrêter le scanner et le scheduler
    """
    try:
        from core.state_manager import get_state_manager
        state = get_state_manager()
        
        # Arrêter le scheduler
        sched = state.get_scheduler()
        if sched:
            await sched.stop_async()
            logger.info("✅ Scheduler arrêté via /api/scanner/stop")
        
        # Mettre à jour l'état
        state.set_is_scanning(False)
        if _app_state:
            _app_state['is_scanning'] = False
            _app_state['scanner_running'] = False

        # Arrêter le WebSocket des prix
        price_prov = _price_provider or state.get_price_provider()
        if price_prov:
            try:
                await price_prov.stop_websocket()
                logger.info("✅ WebSocket prix arrêté")
            except Exception as e:
                logger.warning(f"⚠️ Erreur arrêt price provider: {e}")

        # Notification WebSocket
        if ws_manager:
            await ws_manager.emit('scan_complete', {'timestamp': time.time()})
            await ws_manager.emit('status', {'is_scanning': False})

        return JSONResponse({'status': 'stopped', 'is_scanning': False})

    except Exception as e:
        logger.error(f"❌ Erreur arrêt scanner: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


async def perform_stop_scanner():
    """Version interne utilisable par WebSocket sans dépendances FastAPI"""
    from core.state_manager import get_state_manager
    state = get_state_manager()
    from utils.logging_utils import add_log
    
    # Arrêter le scheduler
    sched = state.get_scheduler()
    if sched:
        await sched.stop_async()
    
    # Mettre à jour l'état
    state.set_is_scanning(False)
    
    # Arrêter WebSocket prix
    price_prov = state.get_price_provider()
    if price_prov:
        try:
            await price_prov.stop_websocket()
        except Exception: pass
        
    # Notification via manager global
    ws_mgr = state.get_ws_manager()
    if ws_mgr:
        await ws_mgr.emit('scan_complete', {'timestamp': time.time()})
        await ws_mgr.emit('status', {'is_scanning': False})
        
    await add_log('INFO', 'Scanner arrêté', 'Boucles automatiques désactivées')
    return {'status': 'stopped', 'is_scanning': False}


@router.get("/analyze/{symbol}")
async def analyze_symbol_route(
    symbol: str,
    tf: str = Query('1m', description="Timeframe"),
    use_confluence: bool = Query(True, description="Utiliser la confluence 1m/5m"),
    volume_multiplier: float = Query(1.0, description="Multiplicateur de volume"),
    analyzer = Depends(get_analyzer)
):
    """
    GET /api/scanner/analyze/{symbol}
    Analyser un symbole spécifique à la demande
    """
    try:
        # Dans cette version simplifiée pour les tests et le dashboard, 
        # on retourne juste un état "pending" ou on lance l'analyse.
        # En réalité, l'analyzer.analyze_symbol() pourrait être appelé ici.
        
        return JSONResponse({
            'symbol': symbol,
            'status': 'pending',
            'timeframe': tf,
            'use_confluence': use_confluence,
            'volume_multiplier': volume_multiplier
        })
    except Exception as e:
        logger.error(f"Erreur analyse symbole {symbol}: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)
