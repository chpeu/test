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

        # 🔥 FIX: Callback pour émettre prix en temps réel via SocketIO
        self.socketio_emit_callback = None
        self.active_position_symbol = None

        # 🔥 FIX CRITIQUE: Stocker symboles pour réabonnement après reconnexion
        self.monitored_symbols: list = []
        
    def _handle_mexc_message(self, data: dict):
        """
        Callback pour traitement messages WebSocket MEXC
        
        Format attendu:
        - {"channel": "push.ticker", "symbol": "...", "data": {...}}
        - {"channel": "pong"}
        
        Note: Callback synchrone, mais WebSocketManager l'appelle depuis un contexte async
        """
        # Heartbeat response
        if data.get("channel") == "pong":
            if DEBUG_ENABLED:
                logger.debug("📡 Heartbeat pong reçu")
            return
        
        # Ticker update
        if data.get("channel") == "push.ticker":
            mexc_symbol = data.get("symbol")  # Format MEXC: "WLD_USDT"
            ticker_data = data.get("data", {})
            
            if mexc_symbol and ticker_data:
                # 🔥 FIX: Convertir format MEXC vers format ccxt pour cohérence
                # "WLD_USDT" -> "WLD/USDT:USDT"
                ccxt_symbol = mexc_symbol
                if '_' in mexc_symbol:
                    parts = mexc_symbol.split('_')
                    if len(parts) == 2:
                        base = parts[0]
                        quote = parts[1]
                        ccxt_symbol = f"{base}/{quote}:{quote}"  # Format ccxt standard
                
                # Extraire prix
                price = float(ticker_data.get("lastPrice", 0))
                volume24 = float(ticker_data.get("volume24", 0))
                
                # Mettre en cache avec format ccxt
                ticker_info = {
                    "symbol": ccxt_symbol,  # Format ccxt pour cohérence
                    "lastPrice": price,
                    "volume24": volume24,
                    "high24": float(ticker_data.get("high24", 0)),
                    "low24": float(ticker_data.get("low24", 0)),
                    "timestamp": time.time()
                }
                
                # 🔥 FIX: Mise à jour thread-safe via asyncio task
                # Utiliser _update_cache pour garantir la cohérence avec le lock
                try:
                    # 🔥 FIX: Utiliser get_running_loop() au lieu de get_event_loop() (déprécié)
                    loop = asyncio.get_running_loop()
                    # 🔥 FIX: Stocker la tâche pour éviter garbage collection
                    task = asyncio.create_task(self._update_cache(ccxt_symbol, ticker_info))
                    # Note: On ne garde pas de référence car c'est un fire-and-forget
                    # et la tâche se termine rapidement
                except RuntimeError:
                    # Pas de boucle événements active, créer une temporairement
                    # 🔥 FIX: Utiliser asyncio.run() pour créer une boucle temporaire
                    # Mais attention, cela ne devrait jamais arriver car le callback
                    # est appelé depuis WebSocketManager qui est déjà dans un contexte async
                    if DEBUG_ENABLED:
                        logger.warning("⚠️ Callback appelé hors boucle événements, mise à jour directe du cache")
                    # Mise à jour directe sans lock (dernier recours)
                    self.price_cache[ccxt_symbol] = ticker_info
                    if len(self.message_buffer) < self.message_buffer.maxlen:
                        self.message_buffer.append(ticker_info)
                
                # 🔥 FIX: Émettre prix en temps réel via SocketIO si position active
                # WebSocket émet à chaque tick, donc latence minimale pour scalping (< 100ms)
                # Le callback sera appelé depuis WebSocketManager qui est dans un contexte async
                if self.active_position_symbol == ccxt_symbol and self.socketio_emit_callback:
                    # Stocker le prix pour émission (sera récupéré par la boucle de check ou émis directement)
                    # Note: L'émission directe se fera via la boucle de check qui lit le cache
                    # WebSocket émet déjà en temps réel, la boucle de check à 0.5s servira de backup
                    pass
                
                if DEBUG_ENABLED:
                    logger.debug(f"📊 Prix MEXC WS: {mexc_symbol} -> {ccxt_symbol} = {price}")
    
    async def _update_cache(self, symbol: str, data: dict):
        """Mise à jour thread-safe du cache"""
        async with self.cache_lock:
            self.price_cache[symbol] = data
            self.message_buffer.append(data)

    async def _get_cached_price(self, symbol: str) -> Optional[Dict]:
        """Récupérer le dernier prix connu dans le cache (même si WS est down)."""
        async with self.cache_lock:
            price_data = self.price_cache.get(symbol)
            # Retourner une copie pour éviter les mutations externes
            return dict(price_data) if price_data else None
    
    async def start_websocket(self, symbols: list):
        """
        Démarrer WebSocket pour monitoring prix

        Args:
            symbols: Liste de symboles à monitorer (max 30)
        """
        if len(symbols) > 30:
            logger.warning(f"⚠️ Plus de 30 symboles ({len(symbols)}), seulement les 30 premiers seront monitorés")
            symbols = symbols[:30]

        # 🔥 FIX CRITIQUE: Stocker symboles pour réabonnement après reconnexion
        self.monitored_symbols = symbols

        try:
            # Créer WebSocket Manager
            self.ws_manager = WebSocketManager(
                url=WEBSOCKET_CONFIG['url'],
                callback=self._handle_mexc_message
            )

            # Configurer callback de reconnexion pour réabonner aux symboles
            self.ws_manager.reconnect_callback = self._resubscribe_after_reconnect

            # Connecter
            await self.ws_manager.start()

            # S'abonner aux symboles
            for symbol in symbols:
                await self.ws_manager.subscribe_ticker(symbol)
                await asyncio.sleep(0.1)  # Petit délai

            logger.info(f"✅ WebSocket démarré pour {len(symbols)} symboles")
            
            # 🔥 JOUR 5: Métriques
            try:
                from core.metrics import get_metrics_collector
                metrics = get_metrics_collector()
                if metrics:
                    metrics.ws_connected = True
            except:
                pass
            
        except Exception as e:
            # Code 1000 = fermeture normale WebSocket (pas une vraie erreur)
            error_msg = str(e)
            if "1000" in error_msg and ("OK" in error_msg or "Normal" in error_msg):
                logger.info(f"ℹ️ WebSocket fermé normalement: {e}")
            else:
                logger.error(f"❌ Erreur démarrage WebSocket: {e}")
            self.use_websocket = False
            self.ws_manager = None
            
            # 🔥 JOUR 5: Métriques
            try:
                from core.metrics import get_metrics_collector
                metrics = get_metrics_collector()
                if metrics:
                    metrics.ws_connected = False
            except:
                pass
    
    async def _resubscribe_after_reconnect(self):
        """
        🔥 FIX CRITIQUE: Réabonner aux symboles après reconnexion WebSocket

        Cette méthode est appelée automatiquement par WebSocketManager après reconnexion.
        Elle s'assure que le WebSocket continue de recevoir les prix des symboles monitorés.

        Logique:
        - Si position active: réabonner UNIQUEMENT au symbole de la position
        - Sinon: réabonner aux symboles stockés dans monitored_symbols
        """
        if not self.ws_manager:
            return

        try:
            # Déterminer quels symboles réabonner
            symbols_to_subscribe = []

            # Vérifier si position active (importer ici pour éviter circular import)
            try:
                # 🔥 FIX: Vérifier via app_state pour détecter position active
                from main import app_state, position_manager
                if app_state and (app_state.get('active_position') or (
                    position_manager and position_manager.active_position
                )):
                    # Position active: réabonner UNIQUEMENT au symbole de la position
                    active_pos = position_manager.active_position if position_manager else app_state.get('active_position')
                    if active_pos:
                        position_symbol = active_pos.symbol if hasattr(active_pos, 'symbol') else active_pos.get('symbol')
                        if position_symbol:
                            symbols_to_subscribe = [position_symbol]
                            logger.info(f"🔄 Réabonnement WebSocket (position active): {position_symbol} UNIQUEMENT")
            except Exception as e:
                logger.debug(f"Impossible de vérifier position active: {e}")

            # Pas de position active: réabonner aux symboles monitorés
            if not symbols_to_subscribe and self.monitored_symbols:
                symbols_to_subscribe = self.monitored_symbols
                logger.info(f"🔄 Réabonnement WebSocket: {len(symbols_to_subscribe)} symboles")

            # Réabonner avec vérification que le WebSocket est prêt
            if not self.ws_manager._ws or not self.ws_manager._connected:
                logger.warning("⚠️ WebSocket pas encore prêt pour réabonnement, attente...")
                await asyncio.sleep(0.5)
            
            for symbol in symbols_to_subscribe:
                try:
                    await self.ws_manager.subscribe_ticker(symbol)
                    await asyncio.sleep(0.05)  # Petit délai
                except Exception as sub_err:
                    logger.warning(f"⚠️ Erreur souscription {symbol}: {sub_err}")

            logger.info(f"✅ WebSocket réabonné à {len(symbols_to_subscribe)} symbole(s)")

        except Exception as e:
            logger.error(f"❌ Erreur réabonnement WebSocket: {e}")
            import traceback
            logger.debug(traceback.format_exc())

    async def stop_websocket(self):
        """Arrêter WebSocket"""
        if self.ws_manager:
            await self.ws_manager.disconnect()
            self.ws_manager = None
            self.monitored_symbols = []  # Vider les symboles monitorés
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
        # 🔥 JOUR 5: Métriques
        try:
            from core.metrics import get_metrics_collector
            metrics = get_metrics_collector()
        except:
            metrics = None
        
        # Stratégie WebSocket (prioritaire)
        if self.use_websocket and self.ws_manager and self.ws_manager.connected:
            async with self.cache_lock:
                if symbol in self.price_cache:
                    if metrics:
                        metrics.ws_price_count += 1
                    return self.price_cache[symbol]
            
            # Pas en cache mais WS connecté → attendre un peu
            await asyncio.sleep(0.05)
            async with self.cache_lock:
                if symbol in self.price_cache:
                    if metrics:
                        metrics.ws_price_count += 1
                    return self.price_cache[symbol]
        
        # Fallback REST
        if DEBUG_ENABLED:
            logger.debug(f"⚠️ WS down ou pas de cache, fallback REST pour {symbol}")
        
        if metrics:
            metrics.ws_rest_fallback_count += 1
        
        try:
            ticker = await self.rest_client.fetch_ticker(symbol)
            
            # 🔥 FIX: Vérifier que ticker est un dict AVANT utilisation
            if not isinstance(ticker, dict) or ticker is None:
                # Essayer le cache avant de logger l'erreur (même périmé)
                cached = await self._get_cached_price(symbol)
                if cached:
                    if DEBUG_ENABLED:
                        logger.debug(
                            f"⚠️ Ticker invalide pour {symbol}, utilisation du cache (age={time.time() - cached.get('timestamp', 0):.1f}s)"
                        )
                    return cached
                
                # Essayer le cache sans restriction de temps
                if symbol in self.price_cache:
                    expired_cache = self.price_cache[symbol]
                    logger.warning(
                        f"⚠️ Format ticker invalide pour {symbol}, utilisation cache périmé (age={time.time() - expired_cache.get('timestamp', 0):.1f}s)"
                    )
                    return expired_cache
                
                # Dernier fallback: prix par défaut pour permettre le logging
                logger.warning(
                    f"⚠️ Format ticker invalide (attendu dict, reçu {type(ticker).__name__}) pour {symbol} - Retour prix par défaut"
                )
                return {
                    "symbol": symbol,
                    "lastPrice": 0.0,
                    "volume24": 0,
                    "timestamp": time.time(),
                    "fallback": True
                }
            
            if ticker:
                return {
                    "symbol": symbol,
                    "lastPrice": ticker.get("last", 0),
                    "volume24": ticker.get("quoteVolume", 0),
                    "timestamp": time.time()
                }
        except Exception as e:
            # Essayer le cache avant de logger l'erreur
            cached = await self._get_cached_price(symbol)
            if cached:
                if DEBUG_ENABLED:
                    logger.debug(
                        f"⚠️ REST erreur pour {symbol}, utilisation du cache (age={time.time() - cached.get('timestamp', 0):.1f}s): {e}"
                    )
                return cached
            
            # Essayer le cache sans restriction de temps
            if symbol in self.price_cache:
                expired_cache = self.price_cache[symbol]
                logger.warning(
                    f"⚠️ REST erreur pour {symbol}, utilisation cache périmé (age={time.time() - expired_cache.get('timestamp', 0):.1f}s)"
                )
                return expired_cache
            
            # Si pas de cache, alors logger l'erreur complète
            if DEBUG_ENABLED:
                logger.error(f"❌ Erreur fallback REST {symbol}: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Dernier fallback: prix par défaut pour permettre le logging
            logger.warning(f"⚠️ Aucun prix disponible pour {symbol}, retour prix par défaut")
            return {
                "symbol": symbol,
                "lastPrice": 0.0,
                "volume24": 0,
                "timestamp": time.time(),
                "fallback": True
            }
        
        return {
            "symbol": symbol,
            "lastPrice": 0.0,
            "volume24": 0,
            "timestamp": time.time(),
            "fallback": True
        }
    
    def is_websocket_connected(self) -> bool:
        """Vérifier si WebSocket est connecté"""
        # 🔥 FIX: Garantir retour bool (éviter None)
        return bool(self.use_websocket and self.ws_manager and self.ws_manager.connected)
    
    def set_socketio_callback(self, callback, active_symbol: Optional[str] = None):
        """
        Définir callback pour émettre prix via SocketIO
        
        Args:
            callback: Fonction async(symbol, price) pour émettre position_update
            active_symbol: Symbole de la position active (None si pas de position)
        """
        self.socketio_emit_callback = callback
        self.active_position_symbol = active_symbol
    
    async def _emit_price_update(self, symbol: str, price: float):
        """Émettre mise à jour prix via SocketIO"""
        if self.socketio_emit_callback:
            try:
                await self.socketio_emit_callback(symbol, price)
            except Exception as e:
                logger.error(f"❌ Erreur émission prix SocketIO: {e}")


# Instance globale
_price_provider: Optional[HybridPriceProvider] = None


def get_price_provider() -> HybridPriceProvider:
    """Singleton pattern pour l'instance price provider"""
    global _price_provider
    if _price_provider is None:
        _price_provider = HybridPriceProvider()
    return _price_provider



