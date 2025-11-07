"""
Routes API pour le scanner - Gestion des top pairs et analyses
"""

import asyncio
import logging
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

# Variables globales injectées par main.py
_scanner = None
_analyzer = None
_price_provider = None
_app_state = None
_sio = None


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


def set_socketio(sio):
    """Injecter l'instance SocketIO"""
    global _sio
    _sio = sio


# Créer le router
router = APIRouter(prefix="/api/scanner", tags=["scanner"])


@router.get("/top-pairs")
async def get_top_pairs():
    """
    GET /api/scanner/top-pairs
    Récupérer les top pairs actuels
    """
    if not _app_state:
        return JSONResponse({'pairs': []})

    try:
        pairs = _app_state.get('top_pairs', [])
        return JSONResponse({'pairs': pairs})
    except Exception as e:
        logger.error(f"Erreur récupération top pairs: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


@router.post("/start")
async def start_scanner(request: Request):
    """
    POST /api/scanner/start
    Démarrer le scanner des top pairs

    Body JSON optionnel:
    {
        "top_n": 20  # Nombre de paires à scanner (défaut: 20)
    }
    """
    if not _scanner or not _app_state:
        return JSONResponse({'error': 'Scanner not available'}, status_code=503)

    try:
        # Parser les données de la requête
        data = {}
        if hasattr(request, 'json'):
            data = await request.json()
        elif hasattr(request, 'body'):
            import json
            body = await request.body()
            if body:
                data = json.loads(body)

        top_n = data.get('top_n', 20) if isinstance(data, dict) else 20

        # Implémenter la logique du scanner
        # Cette fonction sera implémentée depuis main.py

        return JSONResponse({'status': 'started', 'top_n': top_n})

    except Exception as e:
        logger.error(f"Erreur démarrage scanner: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


@router.get("/analyze/{symbol}")
async def analyze_symbol(
    symbol: str,
    tf: str = Query('1m', description="Timeframe (1m ou 5m)"),
    use_confluence: Optional[bool] = Query(None, description="True = 1m ET 5m, False = 1m OU 5m"),
    volume_multiplier: Optional[float] = Query(None, description="Multiplicateur de volume 0.1-2.0"),
    trend_timeframe: Optional[str] = Query(None, description="Timeframe pour trend_data (5m, 15m, 30m, 1h)")
):
    """
    GET /api/analyze/{symbol}
    Analyser un symbole spécifique avec paramètres configurables

    Args:
        symbol: Symbole de la paire (ex: BTCUSDT)
        tf: Timeframe (1m ou 5m)
        use_confluence: True = combiner 1m ET 5m, False = utiliser 1m OU 5m
        volume_multiplier: Multiplicateur de volume (0.1-2.0)
        trend_timeframe: Timeframe pour trend_data (5m, 15m, 30m, 1h)
    """
    if not _analyzer:
        return JSONResponse({'error': 'Analyzer not available'}, status_code=503)

    try:
        # Récupérer valeurs depuis TRADING_CONFIG si non fournies
        from config import TRADING_CONFIG

        if use_confluence is None:
            use_confluence = TRADING_CONFIG.get('use_confluence', False)
        if volume_multiplier is None:
            volume_multiplier = TRADING_CONFIG.get('volume_multiplier', 1.0)
        if trend_timeframe is None:
            trend_timeframe = TRADING_CONFIG.get('trend_timeframe', '15m')

        # Implémenter la logique d'analyse
        # Cette fonction sera implémentée depuis main.py

        return JSONResponse({
            'symbol': symbol,
            'analysis': None,  # À implémenter
            'status': 'pending'
        })

    except Exception as e:
        logger.error(f"Erreur analyse {symbol}: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)
