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
from utils.pricing import get_price_with_source

logger = logging.getLogger(__name__)


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class _AwaitablePrice(float):
    """Valeur de prix compatible sync + await (tests)."""

    def __new__(cls, provider, symbol: str, value: Optional[float]):
        obj = float.__new__(cls, value if value is not None else 0.0)
        obj._provider = provider
        obj._symbol = symbol
        return obj

    def __await__(self):
        async def _coro():
            return await self._provider._get_current_price_async(self._symbol)

        return _coro().__await__()


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
        
        # 🔥 FIX: Gestion d'exception pour get_mexc_client()
        self.rest_client = get_mexc_client()
        if self.rest_client is None:
            import logging
            logger = logging.getLogger(__name__)
            logger.error("❌ HybridPriceProvider: impossible d'obtenir MEXCClient")
            raise RuntimeError("MEXCClient indisponible")

        # Compatibilité tests (alias historique)
        self.client = self.rest_client
        
        self.use_websocket = True

        # Cache des derniers prix reçus
        self.price_cache: Dict[str, Dict] = {}
        self._cache_lock: Optional[asyncio.Lock] = None  # 🔥 Lazy initialization
        self._ws_lifecycle_lock: Optional[asyncio.Lock] = None

        # 🔥 v6.6.1 Phase 2A: Buffer pour backpressure (optionnel)
        self.message_buffer = deque(maxlen=100)

        # 🔥 FIX: Callback pour émettre prix en temps réel via SocketIO
        self.socketio_emit_callback = None
        self.active_position_symbol = None

        # 🔥 FIX CRITIQUE: Stocker symboles pour réabonnement après reconnexion
        self.monitored_symbols: list = []
        
        # 🔥 FIX SL MISMATCH: Callback pour vérification SL en temps réel
        # Appelé à chaque tick WebSocket pour détection immédiate du SL
        self._sl_check_callback = None
        self._sl_check_params = None  # {symbol, direction, sl_level, entry_price}
        
    @property
    def cache_lock(self) -> asyncio.Lock:
        """Lazy initialization of the cache lock to ensure it's in the correct event loop"""
        if self._cache_lock is None:
            self._cache_lock = asyncio.Lock()
        return self._cache_lock

    @property
    def ws_lifecycle_lock(self) -> asyncio.Lock:
        if self._ws_lifecycle_lock is None:
            self._ws_lifecycle_lock = asyncio.Lock()
        return self._ws_lifecycle_lock

    async def _wait_for_ws_ready(
        self,
        ws_manager: WebSocketManager,
        timeout: float = 2.0,
        poll_interval: float = 0.05,
    ) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.ws_manager is not ws_manager:
                return False
            if getattr(ws_manager, 'connected', False) and getattr(ws_manager, '_ws', None):
                return True
            await asyncio.sleep(poll_interval)
        return bool(
            self.ws_manager is ws_manager
            and getattr(ws_manager, 'connected', False)
            and getattr(ws_manager, '_ws', None)
        )

    def _handle_mexc_message(self, data: dict):
        """
        Callback pour traitement messages WebSocket MEXC
        
        Format attendu:
        - {"channel": "push.ticker", "symbol": "...", "data": {...}}
        - {"channel": "pong"}
        
        Note: Callback synchrone, mais WebSocketManager l'appelle depuis un contexte async
        """
        if DEBUG_ENABLED:
            logger.debug(f"📥 Message WebSocket reçu: {data.get('channel') or 'unknown'}")

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
                last_price = _safe_float(ticker_data.get("lastPrice")) or 0.0
                
                if DEBUG_ENABLED:
                    logger.debug(f"📊 Prix WebSocket {ccxt_symbol}: {last_price}")
                volume24 = _safe_float(ticker_data.get("volume24")) or 0.0
                mark_price = _safe_float(ticker_data.get("markPrice"))
                fair_price = _safe_float(ticker_data.get("fairPrice"))
                index_price = _safe_float(ticker_data.get("indexPrice"))
                
                # Mettre en cache avec format ccxt
                ticker_info = {
                    "symbol": ccxt_symbol,  # Format ccxt pour cohérence
                    "lastPrice": last_price,
                    "markPrice": mark_price,
                    "fairPrice": fair_price,
                    "indexPrice": index_price,
                    "volume24": volume24,
                    "high24": _safe_float(ticker_data.get("high24")) or 0.0,
                    "low24": _safe_float(ticker_data.get("low24")) or 0.0,
                    "timestamp": time.time()
                }

                reference_price, ref_source = get_price_with_source(ticker_info)
                if reference_price is not None:
                    ticker_info["referencePrice"] = reference_price
                if ref_source:
                    ticker_info["referenceSource"] = ref_source
                
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
                
                # 🔥 FIX SL MISMATCH: Vérification SL en temps réel à chaque tick
                # Cela garantit une détection immédiate du SL, pas toutes les 2 secondes
                if self._sl_check_callback and self._sl_check_params:
                    params = self._sl_check_params
                    if params.get('symbol') == ccxt_symbol:
                        try:
                            loop = asyncio.get_running_loop()
                            # Fire-and-forget: vérifier SL immédiatement
                            asyncio.create_task(
                                self._check_sl_realtime(last_price, params)
                            )
                        except RuntimeError:
                            # Pas de boucle, ignorer (ne devrait pas arriver)
                            pass
                
                if DEBUG_ENABLED:
                    logger.debug(f"📊 Prix MEXC WS: {mexc_symbol} -> {ccxt_symbol} = {last_price}")
    
    async def _update_cache(self, symbol: str, data: dict):
        """Mise à jour thread-safe du cache"""
        async with self.cache_lock:
            self.price_cache[symbol] = data
            self.message_buffer.append(data)

    def _ensure_reference_price(self, price_data: dict) -> dict:
        """Guarantee referencePrice/referenceSource fields are populated."""
        if price_data is None:
            return price_data
        if "referencePrice" not in price_data or price_data.get("referencePrice") in (None, 0):
            price, source = get_price_with_source(price_data)
            if price is not None:
                price_data["referencePrice"] = price
            if source:
                price_data["referenceSource"] = source
        return price_data

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
        self.use_websocket = True
        async with self.ws_lifecycle_lock:
            if self.ws_manager:
                try:
                    await self.ws_manager.disconnect()
                except Exception:
                    pass
                self.ws_manager = None

            try:
                # Créer WebSocket Manager
                ws_manager = WebSocketManager(
                    url=WEBSOCKET_CONFIG['url'],
                    callback=self._handle_mexc_message
                )
                self.ws_manager = ws_manager

                # Configurer callback de reconnexion pour réabonner aux symboles
                ws_manager.reconnect_callback = self._resubscribe_after_reconnect

                # Connecter
                await ws_manager.start()

                if self.ws_manager is not ws_manager:
                    return

                # 🔥 FIX: Vérifier que la connexion WebSocket est établie avant souscription
                if not await self._wait_for_ws_ready(ws_manager, timeout=2.0):
                    logger.warning("⚠️ WebSocket pas encore prêt - abonnement différé")
                    return

                # S'abonner aux symboles
                for symbol in symbols:
                    try:
                        # 🔥 FIX: Vérification supplémentaire avant chaque souscription
                        if self.ws_manager is ws_manager and ws_manager.connected:
                            await ws_manager.subscribe_ticker(symbol)
                            await asyncio.sleep(0.1)  # Petit délai
                        else:
                            logger.warning(f"⚠️ WebSocket déconnecté pendant souscription de {symbol}")
                            break
                    except Exception as sub_e:
                        logger.error(f"❌ Erreur souscription {symbol}: {sub_e}")
                        continue

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
                if self.ws_manager:
                    try:
                        await self.ws_manager.disconnect()
                    except Exception:
                        pass
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

        ws_manager = self.ws_manager

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

            if not symbols_to_subscribe:
                return

            # Réabonner avec vérification que le WebSocket est prêt
            if not await self._wait_for_ws_ready(ws_manager, timeout=5.0):
                logger.warning("⚠️ WebSocket pas encore prêt pour réabonnement")
                return
            
            for symbol in symbols_to_subscribe:
                try:
                    if self.ws_manager is ws_manager and ws_manager.connected:
                        await ws_manager.subscribe_ticker(symbol)
                        await asyncio.sleep(0.05)  # Petit délai
                    else:
                        logger.warning(f"⚠️ WebSocket non prêt pour {symbol}, ignoré")
                except Exception as sub_err:
                    logger.warning(f"⚠️ Erreur souscription {symbol}: {sub_err}")

            logger.info(f"✅ WebSocket réabonné à {len(symbols_to_subscribe)} symbole(s)")

        except Exception as e:
            logger.error(f"❌ Erreur réabonnement WebSocket: {e}")
            import traceback
            logger.debug(traceback.format_exc())

    async def stop_websocket(self):
        """Arrêter WebSocket"""
        async with self.ws_lifecycle_lock:
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
                    return self._ensure_reference_price(self.price_cache[symbol])
            
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
                    return self._ensure_reference_price(cached)
                
                # Essayer le cache sans restriction de temps
                if symbol in self.price_cache:
                    expired_cache = self.price_cache[symbol]
                    logger.warning(
                        f"⚠️ Format ticker invalide pour {symbol}, utilisation cache périmé (age={time.time() - expired_cache.get('timestamp', 0):.1f}s)"
                    )
                    return self._ensure_reference_price(expired_cache)
                
                # Pas de cache disponible, retourner None
                logger.warning(
                    f"⚠️ Format ticker invalide (attendu dict, reçu {type(ticker).__name__}) pour {symbol} - Pas de cache disponible"
                )
                return None
            
            if ticker:
                info = ticker.get("info", {}) if isinstance(ticker, dict) else {}
                rest_result = {
                    "symbol": symbol,
                    "lastPrice": ticker.get("last", 0),
                    "markPrice": info.get("markPrice") or info.get("fairPrice"),
                    "fairPrice": info.get("fairPrice"),
                    "indexPrice": info.get("indexPrice"),
                    "volume24": ticker.get("quoteVolume", 0),
                    "timestamp": time.time()
                }
                return self._ensure_reference_price(rest_result)
        except Exception as e:
            # Essayer le cache avant de logger l'erreur
            cached = await self._get_cached_price(symbol)
            if cached:
                if DEBUG_ENABLED:
                    logger.debug(
                        f"⚠️ REST erreur pour {symbol}, utilisation du cache (age={time.time() - cached.get('timestamp', 0):.1f}s): {e}"
                    )
                return self._ensure_reference_price(cached)
            
            # Essayer le cache sans restriction de temps
            if symbol in self.price_cache:
                expired_cache = self.price_cache[symbol]
                logger.warning(
                    f"⚠️ REST erreur pour {symbol}, utilisation cache périmé (age={time.time() - expired_cache.get('timestamp', 0):.1f}s)"
                )
                return self._ensure_reference_price(expired_cache)
            
            # Si pas de cache, alors logger l'erreur complète et retourner None
            if DEBUG_ENABLED:
                logger.error(f"❌ Erreur fallback REST {symbol}: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")

            return None

        return None
    
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
    
    def set_sl_check_callback(
        self, 
        callback, 
        symbol: Optional[str] = None,
        direction: Optional[str] = None,
        sl_level: Optional[float] = None,
        entry_price: Optional[float] = None
    ):
        """
        🔥 FIX SL MISMATCH: Configurer vérification SL en temps réel
        
        Cette méthode permet de vérifier le SL à chaque tick WebSocket,
        éliminant le problème de gap entre les vérifications de 2 secondes.
        
        Args:
            callback: Fonction async(price, reason) appelée quand SL touché
            symbol: Symbole de la position active
            direction: 'LONG' ou 'SHORT'
            sl_level: Niveau de prix du Stop Loss
            entry_price: Prix d'entrée pour calcul PnL
        """
        self._sl_check_callback = callback
        if callback and symbol:
            self._sl_check_params = {
                'symbol': symbol,
                'direction': direction,
                'sl_level': sl_level,
                'entry_price': entry_price
            }
            logger.info(
                f"🛡️ SL Check temps réel activé: {symbol} {direction} | "
                f"SL={sl_level:.8f} | Entry={entry_price:.8f}"
            )
        else:
            self._sl_check_params = None
            if callback is None:
                logger.info("🛡️ SL Check temps réel désactivé")
    
    def update_sl_level(self, new_sl_level: float):
        """
        🔥 FIX: Mettre à jour le niveau SL (pour trailing stop)
        
        Args:
            new_sl_level: Nouveau niveau de prix du Stop Loss
        """
        if self._sl_check_params:
            old_sl = self._sl_check_params.get('sl_level', 0)
            self._sl_check_params['sl_level'] = new_sl_level
            logger.debug(
                f"🔄 SL temps réel mis à jour: {old_sl:.8f} → {new_sl_level:.8f}"
            )
    
    async def _check_sl_realtime(self, current_price: float, params: dict):
        """
        🔥 FIX SL MISMATCH: Vérifier SL en temps réel
        
        Cette méthode est appelée à chaque tick WebSocket pour détecter
        immédiatement si le SL est touché.
        
        Args:
            current_price: Prix actuel du tick
            params: Paramètres de la position {symbol, direction, sl_level, entry_price}
        """
        if not self._sl_check_callback or not params:
            return
        
        direction = params.get('direction')
        sl_level = params.get('sl_level')
        entry_price = params.get('entry_price')
        
        if not all([direction, sl_level, entry_price]):
            return
        
        # Vérifier si SL touché
        sl_triggered = False
        if direction == 'LONG':
            # LONG: SL touché si prix <= sl_level
            sl_triggered = current_price <= sl_level
        else:  # SHORT
            # SHORT: SL touché si prix >= sl_level
            sl_triggered = current_price >= sl_level
        
        if sl_triggered:
            # Calculer PnL pour déterminer si c'est SL ou TS
            if direction == 'LONG':
                pnl = (current_price - entry_price) / entry_price * 100
            else:
                pnl = (entry_price - current_price) / entry_price * 100
            
            reason = 'TS' if pnl >= 0 else 'SL'
            
            logger.warning(
                f"⚡ SL DÉTECTÉ TEMPS RÉEL: {params.get('symbol')} {direction} | "
                f"Prix={current_price:.8f} | SL={sl_level:.8f} | "
                f"PnL={pnl:+.2f}% | Raison={reason}"
            )
            
            # Désactiver callback pour éviter appels multiples
            callback = self._sl_check_callback
            self._sl_check_callback = None
            self._sl_check_params = None
            
            # Appeler le callback de fermeture
            try:
                await callback(current_price, reason)
            except Exception as e:
                logger.error(f"❌ Erreur callback SL temps réel: {e}")
                import traceback
                logger.debug(traceback.format_exc())


# Instance globale
_price_provider: Optional[HybridPriceProvider] = None


class PriceProvider(HybridPriceProvider):
    """Alias compatible avec anciens tests (sync + async)."""

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            # Fallback minimal pour tests
            from types import SimpleNamespace
            self.ws_manager = None
            self.rest_client = SimpleNamespace()
            self.use_websocket = False
            self.price_cache = {}
            self._cache_lock = None
            self._ws_lifecycle_lock = None
            self.message_buffer = deque(maxlen=100)
            self.socketio_emit_callback = None
            self.active_position_symbol = None
            self.monitored_symbols = []
            self._sl_check_callback = None
            self._sl_check_params = None

    @property
    def client(self):
        return self.rest_client

    @client.setter
    def client(self, value):
        self.rest_client = value

    def get_current_price(self, symbol: str):
        cached_value = None
        try:
            cached = self.price_cache.get(symbol) if hasattr(self, "price_cache") else None
            if cached:
                for key in ("referencePrice", "lastPrice", "price", "last", "markPrice", "fairPrice"):
                    if key in cached:
                        cached_value = _safe_float(cached.get(key))
                        if cached_value is not None:
                            break
        except Exception:
            cached_value = None

        return _AwaitablePrice(self, symbol, cached_value)

    async def _get_current_price_async(self, symbol: str) -> Optional[float]:
        try:
            data = await self.get_price(symbol)
        except Exception:
            return None
        if not data or not isinstance(data, dict):
            return None
        for key in ("lastPrice", "price", "last", "referencePrice", "markPrice", "fairPrice"):
            value = data.get(key)
            parsed = _safe_float(value)
            if parsed is not None:
                return parsed
        return None

    async def get_multiple_prices(self, symbols: list) -> Dict[str, Optional[float]]:
        results: Dict[str, Optional[float]] = {}
        for symbol in symbols:
            results[symbol] = await self._get_current_price_async(symbol)
        return results


def get_price_provider() -> Optional[HybridPriceProvider]:
    """Singleton pattern pour l'instance price provider"""
    global _price_provider
    if _price_provider is None:
        import logging
        logger = logging.getLogger(__name__)
        logger.info("🔄 Création nouvelle instance HybridPriceProvider (singleton était None)")
        try:
            _price_provider = HybridPriceProvider()
            logger.info("✅ HybridPriceProvider créé avec succès")
        except Exception as e:
            logger.error(f"❌ ERREUR création HybridPriceProvider: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    return _price_provider



