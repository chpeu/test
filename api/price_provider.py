"""
Hybrid Price Provider: WebSocket + REST fallback
"""
import asyncio
import logging
import time
from typing import Dict, Optional
from collections import deque

from api.reliability import WebSocketManager
from api.mexc import get_mexc_client
from config import WEBSOCKET_CONFIG, DEBUG_ENABLED

logger = logging.getLogger(__name__)


class HybridPriceProvider:
    """
    Provider de prix avec bascule automatique entre WebSocket et REST
    
    Avantages:
    - Latence ultra-faible en WebSocket (50ms)
    - Fiabilité maximale avec fallback REST
    - Transition transparente
    """
    
    def __init__(self):
        self.ws_manager: Optional[WebSocketManager] = None
        self.rest_client = get_mexc_client()
        self.use_websocket = True
        
        # Cache des derniers prix reçus
        self.price_cache: Dict[str, Dict] = {}
        self.cache_lock = asyncio.Lock()
        
        # 🔥 v6.6.1 Phase 2A: Buffer pour backpressure (optionnel)
        self.message_buffer = deque(maxlen=100)
        
    def _handle_mexc_message(self, data: dict):
        """
        Callback pour traitement messages WebSocket MEXC
        
        Format attendu:
        - {"channel": "push.ticker", "symbol": "...", "data": {...}}
        - {"channel": "pong"}
        """
        # Heartbeat response
        if data.get("channel") == "pong":
            if DEBUG_ENABLED:
                logger.debug("📡 Heartbeat pong reçu")
            return
        
        # Ticker update
        if data.get("channel") == "push.ticker":
            symbol = data.get("symbol")
            ticker_data = data.get("data", {})
            
            if symbol and ticker_data:
                # Extraire prix
                price = float(ticker_data.get("lastPrice", 0))
                volume24 = float(ticker_data.get("volume24", 0))
                
                # Mettre en cache
                ticker_info = {
                    "symbol": symbol,
                    "lastPrice": price,
                    "volume24": volume24,
                    "high24": float(ticker_data.get("high24", 0)),
                    "low24": float(ticker_data.get("low24", 0)),
                    "timestamp": time.time()
                }
                
                # Thread-safe update
                asyncio.create_task(self._update_cache(symbol, ticker_info))
                
                if DEBUG_ENABLED:
                    logger.debug(f"📊 Prix MEXC WS: {symbol} = {price}")
    
    async def _update_cache(self, symbol: str, data: dict):
        """Mise à jour thread-safe du cache"""
        async with self.cache_lock:
            self.price_cache[symbol] = data
            self.message_buffer.append(data)
    
    async def start_websocket(self, symbols: list):
        """
        Démarrer WebSocket pour monitoring prix
        
        Args:
            symbols: Liste de symboles à monitorer (max 30)
        """
        if len(symbols) > 30:
            logger.warning(f"⚠️ Plus de 30 symboles ({len(symbols)}), seulement les 30 premiers seront monitorés")
            symbols = symbols[:30]
        
        try:
            # Créer WebSocket Manager
            self.ws_manager = WebSocketManager(
                url=WEBSOCKET_CONFIG['url'],
                callback=self._handle_mexc_message
            )
            
            # Connecter
            await self.ws_manager.start()
            
            # S'abonner aux symboles
            for symbol in symbols:
                await self.ws_manager.subscribe_ticker(symbol)
                await asyncio.sleep(0.1)  # Petit délai
            
            logger.info(f"✅ WebSocket démarré pour {len(symbols)} symboles")
            
        except Exception as e:
            logger.error(f"❌ Erreur démarrage WebSocket: {e}")
            self.use_websocket = False
            self.ws_manager = None
    
    async def stop_websocket(self):
        """Arrêter WebSocket"""
        if self.ws_manager:
            await self.ws_manager.disconnect()
            self.ws_manager = None
            logger.info("🔌 WebSocket arrêté")
    
    async def get_price(self, symbol: str) -> Optional[Dict]:
        """
        Récupérer le prix d'un symbole
        
        Stratégie:
        1. Si WebSocket connecté → utiliser cache
        2. Sinon → fallback REST
        
        Args:
            symbol: Symbole de la paire
            
        Returns:
            Dictionnaire avec prix et métadonnées, ou None si erreur
        """
        # Stratégie WebSocket (prioritaire)
        if self.use_websocket and self.ws_manager and self.ws_manager.connected:
            async with self.cache_lock:
                if symbol in self.price_cache:
                    return self.price_cache[symbol]
            
            # Pas en cache mais WS connecté → attendre un peu
            await asyncio.sleep(0.05)
            async with self.cache_lock:
                if symbol in self.price_cache:
                    return self.price_cache[symbol]
        
        # Fallback REST
        if DEBUG_ENABLED:
            logger.debug(f"⚠️ WS down ou pas de cache, fallback REST pour {symbol}")
        
        try:
            ticker = await self.rest_client.fetch_ticker(symbol)
            if ticker:
                return {
                    "symbol": symbol,
                    "lastPrice": ticker.get("last", 0),
                    "volume24": ticker.get("quoteVolume", 0),
                    "timestamp": time.time()
                }
        except Exception as e:
            if DEBUG_ENABLED:
                logger.error(f"❌ Erreur fallback REST {symbol}: {e}")
        
        return None
    
    def is_websocket_connected(self) -> bool:
        """Vérifier si WebSocket est connecté"""
        return self.use_websocket and self.ws_manager and self.ws_manager.connected


# Instance globale
_price_provider: Optional[HybridPriceProvider] = None


def get_price_provider() -> HybridPriceProvider:
    """Singleton pattern pour l'instance price provider"""
    global _price_provider
    if _price_provider is None:
        _price_provider = HybridPriceProvider()
    return _price_provider

