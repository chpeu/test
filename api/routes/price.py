"""
Routes API pour la récupération des prix
"""

import logging
import time
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Variables globales injectées par main.py
_price_provider = None
_app_state = None

def set_price_provider(pp):
    global _price_provider
    _price_provider = pp

def set_app_state(as_):
    global _app_state
    _app_state = as_

router = APIRouter(prefix="/api", tags=["price"])

@router.get("/price/{symbol}")
async def api_get_price(symbol: str):
    """Récupérer prix depuis WebSocket ou REST avec info de debug"""
    from core.state_manager import get_state_manager
    state = get_state_manager()
    pp = _price_provider or state.get_price_provider()
    
    if not pp:
        return JSONResponse({'error': 'Price provider not available'}, status_code=503)
    
    try:
        price_data = await pp.get_price(symbol)
        if price_data:
            is_ws = (pp.use_websocket and 
                    pp.ws_manager and 
                    pp.ws_manager.connected)
            
            async with pp.cache_lock:
                from_cache = symbol in pp.price_cache
            
            source = "WebSocket" if (is_ws and from_cache) else "REST"
            price_data['_source'] = source
            
            if 'timestamp' in price_data:
                age = time.time() - price_data['timestamp']
                price_data['_age_seconds'] = round(age, 2)
            else:
                price_data['timestamp'] = time.time()
                price_data['_age_seconds'] = 0
            
            return JSONResponse(price_data)
        return JSONResponse({'error': 'Price not available'}, status_code=404)
    except Exception as e:
        logger.error(f"Erreur prix {symbol}: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)

@router.get("/prices/live")
async def api_get_live_prices():
    """Récupérer tous les prix en cache WebSocket"""
    from core.state_manager import get_state_manager
    state = get_state_manager()
    pp = _price_provider or state.get_price_provider()
    
    if not pp:
        return JSONResponse({'error': 'Price provider not available'}, status_code=503)
    
    result = {
        "websocket_connected": False,
        "cache_size": 0,
        "prices": {},
        "timestamp": None
    }
    
    try:
        from main import get_preferred_price
        if pp.ws_manager:
            result["websocket_connected"] = pp.ws_manager.connected
        
        async with pp.cache_lock:
            result["cache_size"] = len(pp.price_cache)
            for symbol, price_data in pp.price_cache.items():
                age = time.time() - price_data.get('timestamp', time.time())
                result["prices"][symbol] = {
                    "price": price_data.get('referencePrice') or get_preferred_price(price_data),
                    "volume24": price_data.get('volume24', 0),
                    "age_seconds": round(age, 2),
                    "timestamp": price_data.get('timestamp', 0)
                }
        
        result["timestamp"] = time.time()
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"Erreur récupération prix live: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)

@router.post("/websocket/start")
async def api_start_websocket():
    """Démarrer manuellement le WebSocket pour les top pairs"""
    from core.state_manager import get_state_manager
    state = get_state_manager()
    pp = _price_provider or state.get_price_provider()
    
    if not pp:
        return JSONResponse({'error': 'Price provider not available'}, status_code=503)
    
    top_pairs = state.top_pairs or []
    if not top_pairs:
        return JSONResponse({
            'error': 'Aucune top pair disponible. Lancez d\'abord /api/scanner/start',
            'status': 'no_pairs'
        }, status_code=400)
    
    try:
        symbols = [p.get('symbol', '') for p in top_pairs[:30] if p.get('symbol')]
        if not symbols:
            return JSONResponse({'error': 'Aucun symbole valide trouvé'}, status_code=400)
        
        await pp.start_websocket(symbols)
        return JSONResponse({
            'status': 'started',
            'symbols_count': len(symbols),
            'symbols': symbols[:10]
        })
    except Exception as e:
        logger.error(f"Erreur démarrage WebSocket: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)
