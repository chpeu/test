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


# 🔥 Circuit Breaker Adaptatif
class AdaptiveCircuitBreaker:
    """Circuit breaker qui s'adapte au taux d'erreur"""
    
    def __init__(self, base_fail_max: int = 5, base_timeout: int = 60):
        self.base_fail_max = base_fail_max
        self.base_timeout = base_timeout
        
        # Métriques dynamiques
        self.error_rate = 0.0
        self.success_count = 0
        self.error_count = 0
        
        # Seuils adaptatifs
        self.failure_threshold = base_fail_max
        self.timeout_duration = base_timeout
        
        # Circuit breaker actuel
        self._circuit_breaker = CircuitBreaker(
            fail_max=self.failure_threshold,
            reset_timeout=self.timeout_duration
        )
        
        # Callback pour logging
        self._circuit_breaker.on_state_change = self._on_state_change
        
        logger.info(f"🔄 Circuit Breaker Adaptatif initialisé: Threshold={self.failure_threshold}, Timeout={self.timeout_duration}s")
    
    def _on_state_change(self, failure_counter, state):
        """Callback appelé lors changement d'état circuit breaker"""
        if DEBUG_ENABLED:
            logger.warning(f"🔌 Circuit Breaker: {state.name} (échecs: {failure_counter}, threshold={self.failure_threshold})")
    
    def record_success(self):
        """Enregistrer un succès"""
        self.success_count += 1
        self._update_metrics()
    
    def record_failure(self):
        """Enregistrer un échec"""
        self.error_count += 1
        self._update_metrics()
    
    def _update_metrics(self):
        """Mettre à jour métriques et ajuster seuils"""
        total = self.success_count + self.error_count
        if total < 10:
            return  # Pas assez de données
        
        # Calculer taux d'erreur
        self.error_rate = self.error_count / total
        
        # Adapter seuils selon taux d'erreur
        old_threshold = self.failure_threshold
        old_timeout = self.timeout_duration
        
        if self.error_rate < 0.05:  # <5% erreurs
            self.failure_threshold = self.base_fail_max * 2  # Plus tolérant
            self.timeout_duration = self.base_timeout // 2  # Timeout court
        elif self.error_rate < 0.15:  # 5-15% erreurs
            self.failure_threshold = self.base_fail_max  # Normal
            self.timeout_duration = self.base_timeout
        else:  # >15% erreurs
            self.failure_threshold = max(3, self.base_fail_max // 2)  # Strict
            self.timeout_duration = self.base_timeout * 2  # Timeout long
        
        # Si seuils changés, recréer circuit breaker
        if old_threshold != self.failure_threshold or old_timeout != self.timeout_duration:
            self._circuit_breaker = CircuitBreaker(
                fail_max=self.failure_threshold,
                reset_timeout=self.timeout_duration
            )
            self._circuit_breaker.on_state_change = self._on_state_change
            
            if DEBUG_ENABLED:
                logger.info(
                    f"🔄 Circuit breaker adapté: "
                    f"Threshold={self.failure_threshold} (was {old_threshold}), "
                    f"Timeout={self.timeout_duration}s (was {old_timeout}), "
                    f"Error rate={self.error_rate*100:.1f}%"
                )
        
        # Reset compteurs toutes les 100 requêtes (fenêtre glissante)
        if total >= 100:
            self.success_count = int(self.success_count * 0.5)
            self.error_count = int(self.error_count * 0.5)
            if DEBUG_ENABLED:
                logger.debug(f"🔄 Reset partiel compteurs: Success={self.success_count}, Error={self.error_count}")
    
    async def call_async(self, func, *args, **kwargs):
        """Appeler fonction avec circuit breaker adaptatif"""
        try:
            result = await self._circuit_breaker.call_async(func, *args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise


# Circuit Breaker adaptatif global
_adaptive_circuit_breaker = AdaptiveCircuitBreaker(
    base_fail_max=CIRCUIT_BREAKER_CONFIG['fail_max'],
    base_timeout=CIRCUIT_BREAKER_CONFIG['reset_timeout']
)


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
    Décorateur pour ajouter un circuit breaker adaptatif à une fonction
    
    Usage:
        @with_circuit_breaker
        async def my_api_call():
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await _adaptive_circuit_breaker.call_async(func, *args, **kwargs)
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
        self._receive_task = None  # 🔥 FIX: Stocker la tâche de réception

        # 🔥 PHASE 2: Watchdog WebSocket amélioré
        self._watchdog_task = None
        self.last_message_time = 0
        self._connected = False
        self._reconnecting = False  # Flag pour éviter reconnexions multiples
        self.watchdog_timeout = WEBSOCKET_CONFIG.get('watchdog_timeout', 30)  # 30s pour scalping

        # 🔥 FIX CRITIQUE: Callback appelé après reconnexion réussie pour réabonner aux symboles
        self.reconnect_callback: Optional[Callable] = None
        
    async def connect(self):
        """Se connecter au WebSocket"""
        try:
            import websockets
            import ssl

            if DEBUG_ENABLED:
                logger.info(f"🔌 Connexion WebSocket: {self.url}")

            # Créer contexte SSL pour vérification des certificats
            ssl_context = None
            if self.url.startswith('wss://'):
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = True
                ssl_context.verify_mode = ssl.CERT_REQUIRED

            self._ws = await websockets.connect(
                self.url,
                ping_interval=WEBSOCKET_CONFIG['ping_interval'],
                ssl=ssl_context
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
    
    async def disconnect(self, stop_running: bool = True):
        """
        Déconnecter WebSocket

        Args:
            stop_running: Si True, arrête complètement le WebSocket.
                         Si False, permet la reconnexion (utilisé dans _reconnect_loop)
        """
        if stop_running:
            self._running = False
        self._connected = False

        # 🔥 FIX: Annuler et attendre les tâches proprement (vérifier qu'elles sont actives)
        if self._reconnect_task and isinstance(self._reconnect_task, asyncio.Task):
            if not self._reconnect_task.done():
                self._reconnect_task.cancel()
                try:
                    await self._reconnect_task
                except asyncio.CancelledError:
                    pass
            self._reconnect_task = None

        if self._watchdog_task and isinstance(self._watchdog_task, asyncio.Task):
            if not self._watchdog_task.done():
                self._watchdog_task.cancel()
                try:
                    await self._watchdog_task
                except asyncio.CancelledError:
                    pass
            self._watchdog_task = None
        
        # 🔥 FIX: Annuler et attendre la tâche de réception
        if self._receive_task and isinstance(self._receive_task, asyncio.Task):
            if not self._receive_task.done():
                self._receive_task.cancel()
                try:
                    await self._receive_task
                except asyncio.CancelledError:
                    pass
            self._receive_task = None

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
                
                # 🔥 PHASE 2: Mettre à jour timestamp (critique pour watchdog)
                self.last_message_time = time.time()
                
                # Parser et appeler callback
                import json
                data = json.loads(message)
                # 🔥 FIX: Le callback peut être sync ou async
                # Si async, l'appeler directement, sinon via to_thread
                try:
                    if asyncio.iscoroutinefunction(self.callback):
                        await self.callback(data)
                    else:
                        # Callback synchrone - l'exécuter dans un thread pour ne pas bloquer
                        # ⚠️ IMPORTANT: Le callback synchrone ne doit pas accéder à des données partagées
                        # sans synchronisation appropriée (locks, queues, etc.)
                        await asyncio.to_thread(self.callback, data)
                except Exception as callback_err:
                    # 🔥 FIX: Capturer les erreurs du callback sans arrêter la boucle
                    if DEBUG_ENABLED:
                        logger.error(f"❌ Erreur dans callback WebSocket: {callback_err}")
                    # Continuer la boucle pour recevoir les prochains messages
                
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
        # Vérifier si une reconnexion est déjà en cours (thread-safe)
        if self._reconnecting:
            return

        self._reconnecting = True

        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnecting = False
            return

        try:
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())
        except Exception as e:
            self._reconnecting = False
            if DEBUG_ENABLED:
                logger.error(f"❌ Erreur création tâche reconnexion: {e}")
    
    async def _reconnect_loop(self):
        """Boucle de reconnexion avec backoff exponentiel"""
        if DEBUG_ENABLED:
            logger.warning("🔄 WebSocket: Tentative reconnexion...")

        reconnect_delay = WEBSOCKET_CONFIG['reconnect_delay']
        max_delay = 30  # Maximum 30 secondes
        attempt = 0

        # Stocker les tâches pour éviter garbage collection
        receive_task = None
        watchdog_task = None

        try:
            while self._running:
                try:
                    # 🔥 FIX: Ne pas arrêter _running pendant la reconnexion
                    await self.disconnect(stop_running=False)
                    await asyncio.sleep(reconnect_delay)
                    await self.connect()

                    # Relancer réception et stocker la tâche
                    receive_task = asyncio.create_task(self._receive_loop())

                    # Relancer watchdog et stocker la tâche
                    if self._watchdog_task:
                        self._watchdog_task.cancel()
                    watchdog_task = asyncio.create_task(self._watchdog_loop())
                    self._watchdog_task = watchdog_task

                    if DEBUG_ENABLED:
                        logger.info("✅ WebSocket reconnecté")

                    # 🔥 FIX CRITIQUE: Appeler callback de reconnexion pour réabonner aux symboles
                    if self.reconnect_callback:
                        try:
                            await self.reconnect_callback()
                        except Exception as e:
                            logger.error(f"❌ Erreur callback reconnexion: {e}")

                    break

                except Exception as e:
                    attempt += 1
                    # Backoff exponentiel
                    reconnect_delay = min(reconnect_delay * 1.5, max_delay)
                    if DEBUG_ENABLED:
                        logger.error(f"❌ Reconnexion échouée (tentative {attempt}): {e}, nouvelle tentative dans {reconnect_delay:.1f}s")
                    await asyncio.sleep(reconnect_delay)
        finally:
            self._reconnecting = False
    
    # 🔥 PHASE 2: Watchdog WebSocket amélioré
    async def _watchdog_loop(self):
        """Surveiller activité WebSocket avec détection précoce"""
        while self._running:
            try:
                await asyncio.sleep(15)  # Check toutes les 15s
                
                if not self._running or not self._connected:
                    continue
                
                time_since_last = time.time() - self.last_message_time
                
                if time_since_last > self.watchdog_timeout:
                    logger.error(
                        f"🐕 Watchdog: WebSocket silencieux depuis {time_since_last:.0f}s "
                        f"(timeout: {self.watchdog_timeout}s)"
                    )

                    # Reconnexion automatique (si pas déjà en cours)
                    if not self._reconnecting:
                        logger.warning("🔄 Reconnexion forcée par watchdog...")
                        # 🔥 FIX: _reconnect() n'est pas async, elle crée juste une tâche
                        await self._reconnect()
                
                elif time_since_last > 20:  # Avertissement précoce
                    logger.warning(
                        f"🐕 Watchdog: WebSocket lent ({time_since_last:.0f}s depuis dernier message)"
                    )
            
            except asyncio.CancelledError:
                logger.info("🐕 Watchdog arrêté")
                break
            except Exception as e:
                logger.error(f"❌ Erreur watchdog: {e}")
                await asyncio.sleep(5)
    
    async def start(self):
        """Démarrer WebSocket"""
        self._running = True
        await self.connect()

        # 🔥 FIX: Stocker les tâches pour éviter garbage collection
        self._receive_task = asyncio.create_task(self._receive_loop())

        # 🔥 PHASE 2: Démarrer watchdog amélioré
        self._watchdog_task = asyncio.create_task(self._watchdog_loop())
        logger.info(f"🐕 Watchdog WebSocket démarré (timeout: {self.watchdog_timeout}s)")
    
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
    - Circuit Breaker Adaptatif
    
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


# Export pour compatibilité
_api_circuit_breaker = _adaptive_circuit_breaker._circuit_breaker

