"""
API client pour MEXC Futures
Utilise ccxt pour les appels API directs (pas de proxy CORS nécessaire)
"""
import asyncio
import ccxt.async_support as ccxt
from typing import Dict, List, Optional, Any
import time

from config import MEXC_FUTURES_URL, DEBUG_ENABLED


class MEXCClient:
    """Client API MEXC avec gestion des erreurs et retry"""
    
    def __init__(self):
        self.exchange = ccxt.mexc({
            'options': {
                'defaultType': 'swap',  # Futures
            },
            'enableRateLimit': True,
            'timeout': 30000,
        })
        self.cache = {}  # Cache pour éviter appels répétés
        
    async def fetch_ticker(self, symbol: str) -> Optional[Dict]:
        """Récupère le ticker d'une paire"""
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return ticker
        except Exception as e:
            if DEBUG_ENABLED:
                print(f"❌ Erreur fetch_ticker {symbol}: {e}")
            return None
    
    async def fetch_tickers(self) -> Dict[str, Any]:
        """Récupère tous les tickers"""
        try:
            tickers = await self.exchange.fetch_tickers()
            return tickers
        except Exception as e:
            if DEBUG_ENABLED:
                print(f"❌ Erreur fetch_tickers: {e}")
            return {}
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1m', limit: int = 100) -> List[List]:
        """
        Récupère les chandeliers OHLCV
        
        Args:
            symbol: Symbole de la paire (ex: BTC_USDT)
            timeframe: '1m', '5m', '15m', etc.
            limit: Nombre de bougies
            
        Returns:
            Liste de [timestamp, open, high, low, close, volume]
        """
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            if DEBUG_ENABLED:
                print(f"❌ Erreur fetch_ohlcv {symbol} {timeframe}: {e}")
            return []
    
    async def fetch_order_book(self, symbol: str, limit: int = 20) -> Optional[Dict]:
        """Récupère le carnet d'ordres"""
        try:
            orderbook = await self.exchange.fetch_order_book(symbol, limit=limit)
            return orderbook
        except Exception as e:
            if DEBUG_ENABLED:
                print(f"❌ Erreur fetch_order_book {symbol}: {e}")
            return None
    
    async def fetch_funding_rate(self, symbol: str) -> Optional[float]:
        """Récupère le funding rate"""
        try:
            ticker = await self.fetch_ticker(symbol)
            if ticker:
                return ticker.get('info', {}).get('fundingRate', 0)
            return None
        except Exception as e:
            if DEBUG_ENABLED:
                print(f"❌ Erreur fetch_funding_rate {symbol}: {e}")
            return None
    
    async def close(self):
        """Ferme les connexions"""
        await self.exchange.close()
    
    def __del__(self):
        """Destructeur: ferme les connexions"""
        if hasattr(self, 'exchange'):
            try:
                asyncio.create_task(self.exchange.close())
            except:
                pass


# Instance globale
_mexc_client: Optional[MEXCClient] = None


def get_mexc_client() -> MEXCClient:
    """Singleton pattern pour l'instance API"""
    global _mexc_client
    if _mexc_client is None:
        _mexc_client = MEXCClient()
    return _mexc_client

