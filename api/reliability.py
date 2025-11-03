"""
Fiabilisation API: Retry, Circuit Breaker, WebSocket
"""
import asyncio
import logging
from typing import Callable, Any, Optional
from functools import wraps
import time

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from pybreaker import CircuitBreaker

from config import RETRY_CONFIG, CIRCUIT_BREAKER_CONFIG, WEBSOCKET_CONFIG, DEBUG_ENABLED

logger = logging.getLogger(__name__)


# Circuit Breaker global
_api_circuit_breaker = CircuitBreaker(
    fail_max=CIRCUIT_BREAKER_CONFIG['fail_max'],
    reset_timeout=CIRCUIT_BREAKER_CONFIG['reset_timeout']
)


# Callback pour logging circuit breaker
def cb_state_change(failure_counter, state):
    """Callback appelé lors changement d'état circuit breaker"""
    if DEBUG_ENABLED:
        logger.warning(f"🔌 Circuit Breaker: {state.name} (échecs: {failure_counter})")


_api_circuit_breaker.on_state_change = cb_state_change


@retry(
    stop=stop_after_attempt(RETRY_CONFIG['max_attempts']),
    wait=wait_exponential(
        multiplier=RETRY_CONFIG['wait_multiplier'],
        min=RETRY_CONFIG['wait_min'],
        max=RETRY_CONFIG['wait_max']
    ),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, asyncio.TimeoutError))
)
async def fetch_with_retry(func: Callable, *args, **kwargs) -> Any:
    """
    Exécute une fonction avec retry et backoff exponentiel
    
    Args:
        func: Fonction async à exécuter
        *args: Arguments positionnels
        **kwargs: Arguments nommés
        
    Returns:
        Résultat de la fonction
        
    Raises:
        Exception: Si toutes les tentatives échouent
    """
    try:
        return await func(*args, **kwargs)
    except (ConnectionError, TimeoutError, asyncio.TimeoutError) as e:
        if DEBUG_ENABLED:
            logger.warning(f"⚠️ Retry nécessaire: {e}")
        raise
    except Exception as e:
        # Autres erreurs ne sont pas retry
        if DEBUG_ENABLED:
            logger.error(f"❌ Erreur non-recoverable: {e}")
        raise


def with_circuit_breaker(func: Callable) -> Callable:
    """
    Décorateur pour ajouter un circuit breaker à une fonction
    
    Usage:
        @with_circuit_breaker
        async def my_api_call():
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await _api_circuit_breaker.call_async(func, *args, **kwargs)
        except Exception as e:
            if DEBUG_ENABLED:
                logger.error(f"❌ Circuit Breaker ouvert: {e}")
            raise
    return wrapper


# WebSocket Manager
class WebSocketManager:
    """Gestionnaire WebSocket avec reconnexion auto"""
    
    def __init__(self, url: str, callback: Callable[[dict], None]):
        """
        Args:
            url: URL WebSocket
            callback: Fonction appelée pour chaque message reçu
        """
        self.url = url
        self.callback = callback
        self._ws = None
        self._running = False
        self._reconnect_task = None
        
        # 🔥 v6.6.1 Phase 2A: Watchdog pour déconnexion silencieuse
        self._watchdog_task = None
        self.last_message_time = 0
        self._connected = False
        
    async def connect(self):
        """Se connecter au WebSocket"""
        try:
            import websockets
            
            if DEBUG_ENABLED:
                logger.info(f"🔌 Connexion WebSocket: {self.url}")
            
            self._ws = await websockets.connect(
                self.url,
                ping_interval=WEBSOCKET_CONFIG['ping_interval']
            )
            
            self._connected = True
            self.last_message_time = time.time()
            
            if DEBUG_ENABLED:
                logger.info("✅ WebSocket connecté")
                
        except Exception as e:
            self._connected = False
            if DEBUG_ENABLED:
                logger.error(f"❌ Erreur connexion WebSocket: {e}")
            raise
    
    async def disconnect(self):
        """Déconnecter WebSocket"""
        self._running = False
        self._connected = False
        
        if self._reconnect_task:
            self._reconnect_task.cancel()
            
        if self._watchdog_task:
            self._watchdog_task.cancel()
            
        if self._ws:
            await self._ws.close()
            if DEBUG_ENABLED:
                logger.info("🔌 WebSocket déconnecté")
    
    async def _receive_loop(self):
        """Boucle réception messages"""
        while self._running:
            try:
                message = await asyncio.wait_for(
                    self._ws.recv(),
                    timeout=WEBSOCKET_CONFIG['timeout']
                )
                
                # 🔥 v6.6.1 Phase 2A: Mettre à jour last_message_time
                self.last_message_time = time.time()
                
                # Parser et appeler callback
                import json
                data = json.loads(message)
                # 🔥 FIX: Si callback est async, l'appeler directement, sinon via to_thread
                if asyncio.iscoroutinefunction(self.callback):
                    await self.callback(data)
                else:
                    await asyncio.to_thread(self.callback, data)
                
            except asyncio.TimeoutError:
                # Timeout = envoyer ping MEXC
                if DEBUG_ENABLED:
                    logger.debug("📡 WebSocket: Ping timeout, envoi heartbeat MEXC...")
                await self.send_ping()  # Utiliser méthode MEXC ping
                
            except Exception as e:
                if self._running:
                    if DEBUG_ENABLED:
                        logger.error(f"❌ Erreur réception WebSocket: {e}")
                    # Démarrer reconnexion
                    await self._reconnect()
                break
    
    async def _reconnect(self):
        """Reconnexion automatique"""
        if self._reconnect_task and not self._reconnect_task.done():
            return
        
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())
    
    async def _reconnect_loop(self):
        """Boucle de reconnexion"""
        if DEBUG_ENABLED:
            logger.warning("🔄 WebSocket: Tentative reconnexion...")
        
        await asyncio.sleep(WEBSOCKET_CONFIG['reconnect_delay'])
        
        while self._running:
            try:
                await self.disconnect()
                await self.connect()
                
                # Relancer réception
                asyncio.create_task(self._receive_loop())
                
                if DEBUG_ENABLED:
                    logger.info("✅ WebSocket reconnecté")
                break
                
            except Exception as e:
                if DEBUG_ENABLED:
                    logger.error(f"❌ Reconnexion échouée: {e}, nouvelle tentative dans {WEBSOCKET_CONFIG['reconnect_delay']}s")
                await asyncio.sleep(WEBSOCKET_CONFIG['reconnect_delay'])
    
    # 🔥 v6.6.1 Phase 2A: Watchdog pour déconnexion silencieuse
    async def _watchdog(self):
        """Vérifie si on reçoit des messages (déconnexion silencieuse)"""
        while self._running:
            await asyncio.sleep(10)  # Check toutes les 10s
            
            if self._running and self._connected:
                elapsed = time.time() - self.last_message_time
                if elapsed > 60:  # Pas de message depuis 60s
                    if DEBUG_ENABLED:
                        logger.warning(f"⚠️ Pas de message depuis 60s, reconnexion...")
                    await self._reconnect()
    
    async def start(self):
        """Démarrer WebSocket"""
        self._running = True
        await self.connect()
        asyncio.create_task(self._receive_loop())
        # 🔥 v6.6.1 Phase 2A: Démarrer watchdog
        self._watchdog_task = asyncio.create_task(self._watchdog())
    
    async def send(self, message: dict):
        """Envoyer message"""
        if self._ws:
            import json
            await self._ws.send(json.dumps(message))
    
    async def subscribe(self, topic: str):
        """S'abonner à un topic générique (legacy)"""
        message = {
            "method": "sub.depth",
            "param": {
                "symbol": topic,
                "limit": 5
            }
        }
        await self.send(message)
    
    # 🔥 v6.6.1 Phase 2A: Méthodes MEXC spécifiques
    async def subscribe_ticker(self, symbol: str):
        """
        Subscribe to real-time ticker for a MEXC symbol
        
        🔥 FIX: Format symbole MEXC WebSocket
        - ccxt utilise: "WLD/USDT:USDT"
        - MEXC WebSocket attend: "WLD_USDT" (sans les :USDT)
        """
        if not self._ws:
            raise Exception("WebSocket not connected")
        
        # 🔥 FIX: Convertir format ccxt vers format MEXC WebSocket
        # "WLD/USDT:USDT" -> "WLD_USDT"
        mexc_symbol = symbol
        if '/' in symbol and ':' in symbol:
            # Format ccxt: "WLD/USDT:USDT"
            base = symbol.split('/')[0]
            quote = symbol.split(':')[0].split('/')[1]
            mexc_symbol = f"{base}_{quote}"
        elif '/' in symbol:
            # Format: "WLD/USDT"
            mexc_symbol = symbol.replace('/', '_')
        
        message = {
            "method": "sub.ticker",
            "param": {"symbol": mexc_symbol}
        }
        
        await self.send(message)
        if DEBUG_ENABLED:
            logger.info(f"📡 Subscribed to ticker: {symbol} (MEXC format: {mexc_symbol})")
    
    async def subscribe_multiple_tickers(self, symbols: list):
        """Subscribe to multiple tickers (max 30 per connection)"""
        if not self._ws:
            raise Exception("WebSocket not connected")
        
        if len(symbols) > 30:
            logger.warning(f"⚠️ Plus de 30 symboles ({len(symbols)}), utiliser pool de connexions")
        
        for symbol in symbols:
            await self.subscribe_ticker(symbol)
            await asyncio.sleep(0.1)  # Petit délai entre subscriptions
        
        if DEBUG_ENABLED:
            logger.info(f"✅ Subscribed to {len(symbols)} tickers")
    
    async def send_ping(self):
        """Envoyer ping pour heartbeat MEXC"""
        if self._ws:
            await self.send({"method": "ping"})
    
    @property
    def connected(self):
        """Vérifier si WebSocket est connecté"""
        return self._connected


# Exemple d'utilisation combinée
async def fetch_with_all_protections(func: Callable, *args, **kwargs) -> Any:
    """
    Exécute une fonction avec toutes les protections:
    - Retry avec backoff
    - Circuit Breaker
    
    Args:
        func: Fonction async à exécuter
        *args: Arguments positionnels
        **kwargs: Arguments nommés
        
    Returns:
        Résultat de la fonction
    """
    @with_circuit_breaker
    async def protected_call():
        return await fetch_with_retry(func, *args, **kwargs)
    
    return await protected_call()

