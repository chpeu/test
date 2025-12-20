"""
API client pour MEXC Futures
Utilise ccxt pour les appels API directs (pas de proxy CORS nécessaire)
"""
import asyncio
import ccxt.async_support as ccxt
from typing import Dict, List, Optional, Any
import time
import aiohttp

from config import MEXC_FUTURES_URL, DEBUG_ENABLED
from api.reliability import fetch_with_all_protections, WebSocketManager

# 🔥 REFACTORING SPRINT 1.1: Exception Handling System
try:
    from core.exceptions import (
        NetworkError, APIError, RateLimitError, MarketDataError,
        TradeCursorError
    )
except ImportError:
    # Fallback si exceptions custom non disponibles
    NetworkError = APIError = RateLimitError = MarketDataError = TradeCursorError = Exception


class MEXCClient:
    """
    Client API MEXC avec gestion des erreurs et retry

    Utilisation recommandée avec async context manager:
    ```python
    async with MEXCClient() as client:
        ticker = await client.fetch_ticker("BTC/USDT")
        ohlcv = await client.fetch_ohlcv("BTC/USDT", "1m")
    # Connexions automatiquement fermées (HTTP session, WebSocket, exchange)
    ```

    Alternativement (non recommandé):
    ```python
    client = MEXCClient()
    try:
        ticker = await client.fetch_ticker("BTC/USDT")
    finally:
        await client.close()  # Cleanup manuel
    ```
    """

    def __init__(self):
        # 🔥 v6.6: Connection pooling avec aiohttp
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                limit=100,
                ttl_dns_cache=300,
                keepalive_timeout=30
            )
        )
        
        self.exchange = ccxt.mexc({
            'options': {
                'defaultType': 'swap',  # Futures
            },
            'enableRateLimit': True,
            'timeout': 30000,
        })
        self.cache = {}  # Cache pour éviter appels répétés
        self.ws_manager = None  # WebSocket manager
        
    async def fetch_ticker(self, symbol: str) -> Optional[Dict]:
        """Récupère le ticker d'une paire avec retry + circuit breaker"""
        async def _fetch():
            result = await self.exchange.fetch_ticker(symbol)
            if result is None or not isinstance(result, dict):
                raise ValueError(f"Invalid ticker data for {symbol}: {type(result).__name__}")
            return result
        
        try:
            result = await fetch_with_all_protections(_fetch)
            # Double-check que le résultat est bien un dict
            if result is None or not isinstance(result, dict):
                if DEBUG_ENABLED:
                    print(f"⚠️ fetch_ticker {symbol}: Returned None or invalid type")
                return None
            return result
        except RateLimitError as e:
            # Rate limit atteint (retry géré par fetch_with_all_protections)
            if DEBUG_ENABLED:
                print(f"⚠️ Rate limit fetch_ticker {symbol}: {e}")
            return None
        except NetworkError as e:
            # Erreur réseau (timeout, connexion, etc.)
            if DEBUG_ENABLED:
                print(f"⚠️ Erreur réseau fetch_ticker {symbol}: {e}")
            return None
        except APIError as e:
            # Erreur API MEXC (symbole invalide, etc.)
            if DEBUG_ENABLED:
                print(f"❌ Erreur API fetch_ticker {symbol}: {e}")
            return None
        except MarketDataError as e:
            # Données marché invalides
            if DEBUG_ENABLED:
                print(f"❌ Données invalides fetch_ticker {symbol}: {e}")
            return None
        except Exception as e:
            # Erreur inattendue
            if DEBUG_ENABLED:
                print(f"❌ Erreur inattendue fetch_ticker {symbol}: {type(e).__name__}: {e}")
            return None
    
    async def fetch_tickers(self) -> Dict[str, Any]:
        """Récupère tous les tickers avec retry + circuit breaker"""
        async def _fetch():
            return await self.exchange.fetch_tickers()
        
        try:
            return await fetch_with_all_protections(_fetch)
        except RateLimitError as e:
            # Rate limit atteint
            if DEBUG_ENABLED:
                print(f"⚠️ Rate limit fetch_tickers: {e}")
            return {}
        except NetworkError as e:
            # Erreur réseau
            if DEBUG_ENABLED:
                print(f"⚠️ Erreur réseau fetch_tickers: {e}")
            return {}
        except APIError as e:
            # Erreur API MEXC
            if DEBUG_ENABLED:
                print(f"❌ Erreur API fetch_tickers: {e}")
            return {}
        except Exception as e:
            # Erreur inattendue
            if DEBUG_ENABLED:
                print(f"❌ Erreur inattendue fetch_tickers: {type(e).__name__}: {e}")
            return {}
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1m', limit: int = 100) -> List[List]:
        """
        Récupère les chandeliers OHLCV avec retry + circuit breaker
        
        Args:
            symbol: Symbole de la paire (ex: BTC_USDT)
            timeframe: '1m', '5m', '15m', etc.
            limit: Nombre de bougies
            
        Returns:
            Liste de [timestamp, open, high, low, close, volume]
        """
        async def _fetch():
            return await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        try:
            return await fetch_with_all_protections(_fetch)
        except RateLimitError as e:
            # Rate limit atteint
            if DEBUG_ENABLED:
                print(f"⚠️ Rate limit fetch_ohlcv {symbol} {timeframe}: {e}")
            return []
        except NetworkError as e:
            # Erreur réseau
            if DEBUG_ENABLED:
                print(f"⚠️ Erreur réseau fetch_ohlcv {symbol} {timeframe}: {e}")
            return []
        except APIError as e:
            # Erreur API MEXC (symbole invalide, timeframe non supporté, etc.)
            if DEBUG_ENABLED:
                print(f"❌ Erreur API fetch_ohlcv {symbol} {timeframe}: {e}")
            return []
        except MarketDataError as e:
            # Données OHLCV invalides
            if DEBUG_ENABLED:
                print(f"❌ Données OHLCV invalides {symbol} {timeframe}: {e}")
            return []
        except Exception as e:
            # Erreur inattendue
            if DEBUG_ENABLED:
                print(f"❌ Erreur inattendue fetch_ohlcv {symbol} {timeframe}: {type(e).__name__}: {e}")
            return []
    
    async def fetch_order_book(self, symbol: str, limit: int = 20) -> Optional[Dict]:
        """Récupère le carnet d'ordres avec retry + circuit breaker"""
        async def _fetch():
            return await self.exchange.fetch_order_book(symbol, limit=limit)
        
        try:
            return await fetch_with_all_protections(_fetch)
        except RateLimitError as e:
            # Rate limit atteint
            if DEBUG_ENABLED:
                print(f"⚠️ Rate limit fetch_order_book {symbol}: {e}")
            return None
        except NetworkError as e:
            # Erreur réseau
            if DEBUG_ENABLED:
                print(f"⚠️ Erreur réseau fetch_order_book {symbol}: {e}")
            return None
        except APIError as e:
            # Erreur API MEXC (symbole invalide, etc.)
            if DEBUG_ENABLED:
                print(f"❌ Erreur API fetch_order_book {symbol}: {e}")
            return None
        except MarketDataError as e:
            # Carnet d'ordres invalide
            if DEBUG_ENABLED:
                print(f"❌ Order book invalide {symbol}: {e}")
            return None
        except Exception as e:
            # Erreur inattendue
            if DEBUG_ENABLED:
                print(f"❌ Erreur inattendue fetch_order_book {symbol}: {type(e).__name__}: {e}")
            return None
    
    async def fetch_funding_rate(self, symbol: str) -> Optional[float]:
        """Récupère le funding rate"""
        try:
            ticker = await self.fetch_ticker(symbol)
            if ticker:
                return ticker.get('info', {}).get('fundingRate', 0)
            return None
        except RateLimitError as e:
            # Rate limit atteint
            if DEBUG_ENABLED:
                print(f"⚠️ Rate limit fetch_funding_rate {symbol}: {e}")
            return None
        except NetworkError as e:
            # Erreur réseau
            if DEBUG_ENABLED:
                print(f"⚠️ Erreur réseau fetch_funding_rate {symbol}: {e}")
            return None
        except APIError as e:
            # Erreur API MEXC
            if DEBUG_ENABLED:
                print(f"❌ Erreur API fetch_funding_rate {symbol}: {e}")
            return None
        except MarketDataError as e:
            # Funding rate invalide
            if DEBUG_ENABLED:
                print(f"❌ Funding rate invalide {symbol}: {e}")
            return None
        except Exception as e:
            # Erreur inattendue
            if DEBUG_ENABLED:
                print(f"❌ Erreur inattendue fetch_funding_rate {symbol}: {type(e).__name__}: {e}")
            return None
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Async context manager exit avec cleanup automatique

        Args:
            exc_type: Type d'exception si erreur
            exc_val: Valeur exception
            exc_tb: Traceback exception

        Returns:
            False pour propager l'exception (si présente)
        """
        await self.close()
        return False

    async def close(self):
        """Ferme les connexions"""
        if self.ws_manager:
            await self.ws_manager.disconnect()
        await self.session.close()
        await self.exchange.close()

    def __del__(self):
        """Destructeur: ferme les connexions"""
        # 🔥 FIX: Ne pas utiliser asyncio.create_task() dans __del__
        # Les coroutines ne seront jamais attendues et causeront des warnings
        # Les ressources seront fermées proprement par la méthode close() async
        pass


# Instance globale
_mexc_client: Optional[MEXCClient] = None


def get_mexc_client() -> MEXCClient:
    """Singleton pattern pour l'instance API"""
    global _mexc_client
    if _mexc_client is None:
        _mexc_client = MEXCClient()
    return _mexc_client

