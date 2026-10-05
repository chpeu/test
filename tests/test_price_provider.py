"""
Tests pour api/price_provider.py
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from api.price_provider import HybridPriceProvider, get_price_provider


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch):
    """Provider avec rest_client mocké (évite réseau)."""
    provider = HybridPriceProvider()
    provider.rest_client = AsyncMock()
    provider.rest_client.fetch_ticker = AsyncMock(return_value=None)
    return provider


class TestHybridPriceProvider:
    """Tests pour HybridPriceProvider"""

    def test_init(self):
        """Test initialisation"""
        provider = HybridPriceProvider()
        assert provider.ws_manager is None
        assert provider.use_websocket is True
        assert len(provider.price_cache) == 0
        assert provider.socketio_emit_callback is None
        assert provider.active_position_symbol is None

    def test_handle_mexc_message_pong(self):
        """Test gestion message pong (heartbeat)"""
        provider = HybridPriceProvider()
        message = {"channel": "pong"}

        # Ne devrait pas lever d'exception
        provider._handle_mexc_message(message)

    def test_handle_mexc_message_ticker_update(self):
        """Test gestion mise à jour ticker"""
        provider = HybridPriceProvider()
        message = {
            "channel": "push.ticker",
            "symbol": "WLD_USDT",
            "data": {
                "lastPrice": "1.234",
                "volume24": "1000000",
                "high24": "1.5",
                "low24": "1.0"
            }
        }

        provider._handle_mexc_message(message)

        # Vérifier que le prix est en cache (format ccxt)
        assert "WLD/USDT:USDT" in provider.price_cache
        cached = provider.price_cache["WLD/USDT:USDT"]
        assert cached["lastPrice"] == 1.234
        assert cached["volume24"] == 1000000.0

    @pytest.mark.asyncio
    async def test_handle_mexc_message_ticker_update_async_path_updates_cache(self, provider):
        """Couvre le chemin get_running_loop + create_task(_update_cache)."""
        msg = {
            "channel": "push.ticker",
            "symbol": "BTC_USDT",
            "data": {"lastPrice": "123.4", "volume24": "1", "high24": "2", "low24": "0.5"},
        }

        provider._handle_mexc_message(msg)
        await asyncio.sleep(0)
        assert "BTC/USDT:USDT" in provider.price_cache

    def test_handle_mexc_message_invalid_format(self):
        """Test gestion message format invalide"""
        provider = HybridPriceProvider()
        message = {"channel": "unknown", "data": {}}

        # Ne devrait pas lever d'exception
        provider._handle_mexc_message(message)

    @pytest.mark.asyncio
    async def test_update_cache(self):
        """Test mise à jour thread-safe du cache"""
        provider = HybridPriceProvider()
        symbol = "WLD/USDT:USDT"
        data = {
            "symbol": symbol,
            "lastPrice": 1.234,
            "timestamp": time.time()
        }

        await provider._update_cache(symbol, data)

        assert symbol in provider.price_cache
        assert provider.price_cache[symbol] == data
        assert len(provider.message_buffer) == 1

    def test_ensure_reference_price_adds_fields_when_missing(self, provider, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            'api.price_provider.get_price_with_source',
            lambda d: (111.0, 'markPrice'),
        )
        data = {"symbol": "BTC/USDT:USDT", "markPrice": 111.0}
        out = provider._ensure_reference_price(data)
        assert out["referencePrice"] == 111.0
        assert out["referenceSource"] == 'markPrice'

    def test_ensure_reference_price_keeps_existing_reference(self, provider, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr('api.price_provider.get_price_with_source', lambda d: (999.0, 'lastPrice'))
        data = {"symbol": "BTC/USDT:USDT", "referencePrice": 1.0, "referenceSource": "manual"}
        out = provider._ensure_reference_price(data)
        assert out["referencePrice"] == 1.0
        assert out["referenceSource"] == "manual"

    @pytest.mark.asyncio
    async def test_get_cached_price_returns_copy(self, provider):
        symbol = "BTC/USDT:USDT"
        provider.price_cache[symbol] = {"symbol": symbol, "lastPrice": 1.0, "timestamp": time.time()}
        cached = await provider._get_cached_price(symbol)
        assert cached is not provider.price_cache[symbol]
        cached["lastPrice"] = 2.0
        assert provider.price_cache[symbol]["lastPrice"] == 1.0

    @pytest.mark.asyncio
    async def test_start_websocket_success(self):
        """Test démarrage WebSocket réussi"""
        provider = HybridPriceProvider()
        symbols = ["WLD/USDT:USDT", "BTC/USDT:USDT"]

        # Mock WebSocketManager
        with patch('api.price_provider.WebSocketManager') as mock_ws_class:
            mock_ws_instance = AsyncMock()
            mock_ws_class.return_value = mock_ws_instance

            await provider.start_websocket(symbols)

            # Vérifier que WebSocketManager est créé et démarré
            mock_ws_class.assert_called_once()
            mock_ws_instance.start.assert_called_once()
            assert mock_ws_instance.subscribe_ticker.call_count == len(symbols)

    @pytest.mark.asyncio
    async def test_start_websocket_too_many_symbols(self):
        """Test démarrage WebSocket avec plus de 30 symboles"""
        provider = HybridPriceProvider()
        symbols = [f"SYM{i}/USDT:USDT" for i in range(50)]

        with patch('api.price_provider.WebSocketManager') as mock_ws_class:
            mock_ws_instance = AsyncMock()
            mock_ws_class.return_value = mock_ws_instance

            await provider.start_websocket(symbols)

            # Ne devrait souscrire qu'aux 30 premiers
            assert mock_ws_instance.subscribe_ticker.call_count == 30

    @pytest.mark.asyncio
    async def test_start_websocket_failure(self):
        """Test échec démarrage WebSocket"""
        provider = HybridPriceProvider()
        symbols = ["WLD/USDT:USDT"]

        with patch('api.price_provider.WebSocketManager') as mock_ws_class:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.start.side_effect = ConnectionError("Connection failed")
            mock_ws_class.return_value = mock_ws_instance

            await provider.start_websocket(symbols)

            # Devrait basculer sur REST
            assert provider.use_websocket is False
            assert provider.ws_manager is None

    @pytest.mark.asyncio
    async def test_start_websocket_normal_close(self):
        """Test fermeture normale WebSocket (code 1000)"""
        provider = HybridPriceProvider()
        symbols = ["WLD/USDT:USDT"]

        with patch('api.price_provider.WebSocketManager') as mock_ws_class:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.start.side_effect = ConnectionError("1000 OK")
            mock_ws_class.return_value = mock_ws_instance

            await provider.start_websocket(symbols)

            # Devrait basculer sur REST mais sans erreur critique
            assert provider.use_websocket is False

    @pytest.mark.asyncio
    async def test_stop_websocket(self):
        """Test arrêt WebSocket"""
        provider = HybridPriceProvider()
        mock_ws_manager = AsyncMock()
        provider.ws_manager = mock_ws_manager

        await provider.stop_websocket()

        # 🔥 FIX: Vérifier disconnect avant que ws_manager soit None
        mock_ws_manager.disconnect.assert_called_once()
        assert provider.ws_manager is None

    @pytest.mark.asyncio
    async def test_stop_websocket_no_manager(self):
        """Test arrêt WebSocket sans manager"""
        provider = HybridPriceProvider()
        provider.ws_manager = None

        # Ne devrait pas lever d'exception
        await provider.stop_websocket()

    @pytest.mark.asyncio
    async def test_get_price_from_websocket_cache(self):
        """Test récupération prix depuis cache WebSocket"""
        provider = HybridPriceProvider()
        provider.use_websocket = True
        provider.ws_manager = Mock()
        provider.ws_manager.connected = True

        # Ajouter prix en cache
        symbol = "WLD/USDT:USDT"
        price_data = {
            "symbol": symbol,
            "lastPrice": 1.234,
            "volume24": 1000000,
            "timestamp": time.time()
        }
        provider.price_cache[symbol] = price_data

        result = await provider.get_price(symbol)

        assert result == price_data

    @pytest.mark.asyncio
    async def test_get_price_rest_fallback(self):
        """Test fallback REST quand WebSocket down"""
        provider = HybridPriceProvider()
        provider.use_websocket = False

        # Mock REST client
        mock_ticker = {
            "last": 1.234,
            "quoteVolume": 1000000
        }
        provider.rest_client = AsyncMock()
        provider.rest_client.fetch_ticker = AsyncMock(return_value=mock_ticker)

        symbol = "WLD/USDT:USDT"
        result = await provider.get_price(symbol)

        assert result is not None
        assert result["lastPrice"] == 1.234
        assert result["volume24"] == 1000000

    @pytest.mark.asyncio
    async def test_get_price_rest_invalid_format(self):
        """Test fallback REST avec format invalide"""
        provider = HybridPriceProvider()
        provider.use_websocket = False

        # Mock REST client avec format invalide (liste au lieu de dict)
        provider.rest_client = AsyncMock()
        provider.rest_client.fetch_ticker = AsyncMock(return_value=["invalid"])

        symbol = "WLD/USDT:USDT"
        result = await provider.get_price(symbol)

        # Devrait retourner None
        assert result is None

    @pytest.mark.asyncio
    async def test_get_price_rest_invalid_format_falls_back_to_cache(self, provider):
        provider.use_websocket = False
        symbol = "WLD/USDT:USDT"
        provider.price_cache[symbol] = {"symbol": symbol, "lastPrice": 7.0, "timestamp": time.time()}
        provider.rest_client.fetch_ticker = AsyncMock(return_value=["invalid"])

        result = await provider.get_price(symbol)
        assert result is not None
        assert result["lastPrice"] == 7.0

    @pytest.mark.asyncio
    async def test_get_price_rest_exception(self):
        """Test fallback REST avec exception"""
        provider = HybridPriceProvider()
        provider.use_websocket = False

        # Mock REST client avec exception
        provider.rest_client = AsyncMock()
        provider.rest_client.fetch_ticker = AsyncMock(side_effect=Exception("API error"))

        symbol = "WLD/USDT:USDT"
        result = await provider.get_price(symbol)

        # Devrait retourner None
        assert result is None

    @pytest.mark.asyncio
    async def test_get_price_rest_exception_falls_back_to_cache(self, provider):
        provider.use_websocket = False
        symbol = "WLD/USDT:USDT"
        provider.price_cache[symbol] = {"symbol": symbol, "lastPrice": 8.0, "timestamp": time.time()}
        provider.rest_client.fetch_ticker = AsyncMock(side_effect=Exception("API error"))

        result = await provider.get_price(symbol)
        assert result is not None
        assert result["lastPrice"] == 8.0

    @pytest.mark.asyncio
    async def test_get_price_wait_for_cache(self):
        """Test attente cache WebSocket"""
        provider = HybridPriceProvider()
        provider.use_websocket = True
        provider.ws_manager = Mock()
        provider.ws_manager.connected = True

        symbol = "WLD/USDT:USDT"

        # Ajouter prix en cache après un délai
        async def add_to_cache():
            await asyncio.sleep(0.03)
            price_data = {
                "symbol": symbol,
                "lastPrice": 1.234,
                "timestamp": time.time()
            }
            async with provider.cache_lock:
                provider.price_cache[symbol] = price_data

        # Lancer ajout en parallèle
        task = asyncio.create_task(add_to_cache())

        # Mock REST fallback au cas où
        provider.rest_client = AsyncMock()
        provider.rest_client.fetch_ticker = AsyncMock(return_value={
            "last": 5.678,
            "quoteVolume": 2000000
        })

        result = await provider.get_price(symbol)

        await task  # Attendre fin de la tâche

        # Devrait retourner quelque chose (soit cache, soit REST)
        assert result is not None

    def test_is_websocket_connected_true(self):
        """Test vérification WebSocket connecté"""
        provider = HybridPriceProvider()
        provider.use_websocket = True
        provider.ws_manager = Mock()
        provider.ws_manager.connected = True

        assert provider.is_websocket_connected() is True

    def test_is_websocket_connected_false(self):
        """Test vérification WebSocket déconnecté"""
        provider = HybridPriceProvider()
        provider.use_websocket = False

        assert provider.is_websocket_connected() is False

    def test_is_websocket_connected_no_manager(self):
        """Test vérification WebSocket sans manager"""
        provider = HybridPriceProvider()
        provider.use_websocket = True
        provider.ws_manager = None

        assert provider.is_websocket_connected() is False

    def test_set_socketio_callback(self):
        """Test définition callback SocketIO"""
        provider = HybridPriceProvider()

        async def mock_callback(symbol, price):
            pass

        provider.set_socketio_callback(mock_callback, "WLD/USDT:USDT")

        assert provider.socketio_emit_callback == mock_callback
        assert provider.active_position_symbol == "WLD/USDT:USDT"

    @pytest.mark.asyncio
    async def test_emit_price_update_success(self):
        """Test émission mise à jour prix"""
        provider = HybridPriceProvider()
        called = False

        async def mock_callback(symbol, price):
            nonlocal called
            called = True

        provider.socketio_emit_callback = mock_callback

        await provider._emit_price_update("WLD/USDT:USDT", 1.234)

        assert called is True

    @pytest.mark.asyncio
    async def test_emit_price_update_exception(self):
        """Test émission mise à jour prix avec exception"""
        provider = HybridPriceProvider()

        async def mock_callback(symbol, price):
            raise Exception("Emit failed")

        provider.socketio_emit_callback = mock_callback

        # Ne devrait pas lever d'exception
        await provider._emit_price_update("WLD/USDT:USDT", 1.234)

    @pytest.mark.asyncio
    async def test_emit_price_update_no_callback(self):
        """Test émission mise à jour prix sans callback"""
        provider = HybridPriceProvider()
        provider.socketio_emit_callback = None

        # Ne devrait pas lever d'exception
        await provider._emit_price_update("WLD/USDT:USDT", 1.234)


class TestGetPriceProvider:
    """Tests pour get_price_provider singleton"""

    def test_get_price_provider_singleton(self):
        """Test que get_price_provider retourne toujours la même instance"""
        # Reset global instance pour le test
        import api.price_provider
        api.price_provider._price_provider = None

        provider1 = get_price_provider()
        provider2 = get_price_provider()

        assert provider1 is provider2
        assert isinstance(provider1, HybridPriceProvider)

    def test_get_price_provider_creates_instance(self):
        """Test que get_price_provider crée une instance si nécessaire"""
        # Reset global instance
        import api.price_provider
        api.price_provider._price_provider = None

        provider = get_price_provider()

        assert provider is not None
        assert isinstance(provider, HybridPriceProvider)


class TestWebSocketLifecycleFixes:
    """Tests pour les corrections du lifecycle WebSocket"""

    @pytest.mark.asyncio
    async def test_wait_for_ws_ready_success(self):
        """Test _wait_for_ws_ready avec connexion réussie"""
        provider = HybridPriceProvider()
        
        # Mock WebSocket manager connecté avec les bonnes propriétés
        mock_ws_manager = Mock()
        mock_ws_manager.connected = True
        mock_ws_manager._ws = Mock()  # Simuler connexion WebSocket active
        provider.ws_manager = mock_ws_manager  # Important pour la vérification
        
        # Test avec timeout
        result = await provider._wait_for_ws_ready(mock_ws_manager, timeout=1.0)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_wait_for_ws_ready_timeout(self):
        """Test _wait_for_ws_ready avec timeout"""
        provider = HybridPriceProvider()
        
        # Mock WebSocket manager non connecté
        mock_ws_manager = Mock()
        mock_ws_manager.connected = False
        mock_ws_manager._ws = None
        provider.ws_manager = mock_ws_manager
        
        # Test avec timeout court
        result = await provider._wait_for_ws_ready(mock_ws_manager, timeout=0.1)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_wait_for_ws_ready_connection_during_wait(self):
        """Test _wait_for_ws_ready avec connexion pendant l'attente"""
        provider = HybridPriceProvider()
        
        # Mock WebSocket manager qui se connecte après délai
        mock_ws_manager = Mock()
        mock_ws_manager.connected = False
        mock_ws_manager._ws = None
        provider.ws_manager = mock_ws_manager
        
        async def connect_after_delay():
            await asyncio.sleep(0.05)
            mock_ws_manager.connected = True
            mock_ws_manager._ws = Mock()
        
        # Lancer connexion en parallèle
        asyncio.create_task(connect_after_delay())
        
        # Attendre connexion
        result = await provider._wait_for_ws_ready(mock_ws_manager, timeout=0.2)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_start_websocket_with_lifecycle_lock(self):
        """Test start_websocket avec lifecycle lock"""
        provider = HybridPriceProvider()
        symbols = ["BTC/USDT:USDT", "ETH/USDT:USDT"]
        
        # Mock WebSocketManager
        with patch('api.price_provider.WebSocketManager') as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance._connected = True
            mock_ws_instance.start = AsyncMock()
            mock_ws_instance.subscribe_ticker = AsyncMock()
            mock_ws_instance.connected = True
            MockWS.return_value = mock_ws_instance
            
            # Start WebSocket
            await provider.start_websocket(symbols)
            
            # Vérifier que le WebSocket manager est créé
            assert provider.ws_manager is mock_ws_instance
            assert provider.monitored_symbols == symbols
            assert provider.use_websocket is True
            
            # Vérifier que start et subscribe sont appelés
            mock_ws_instance.start.assert_called_once()
            assert mock_ws_instance.subscribe_ticker.call_count == len(symbols)
    
    @pytest.mark.asyncio
    async def test_start_websocket_cleanup_existing_manager(self):
        """Test start_websocket nettoie l'ancien manager"""
        provider = HybridPriceProvider()
        symbols = ["BTC/USDT:USDT"]
        
        # Créer un ancien manager
        old_manager = AsyncMock()
        old_manager.disconnect = AsyncMock()
        provider.ws_manager = old_manager
        
        # Mock nouveau WebSocketManager
        with patch('api.price_provider.WebSocketManager') as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance._connected = True
            mock_ws_instance.start = AsyncMock()
            mock_ws_instance.subscribe_ticker = AsyncMock()
            mock_ws_instance.connected = True
            MockWS.return_value = mock_ws_instance
            
            # Start WebSocket
            await provider.start_websocket(symbols)
            
            # Vérifier que l'ancien manager est déconnecté
            old_manager.disconnect.assert_called_once()
            # Vérifier que le nouveau manager est assigné
            assert provider.ws_manager is mock_ws_instance
    
    @pytest.mark.asyncio
    async def test_start_websocket_not_ready_warning(self):
        """Test start_websocket avec WebSocket pas prêt"""
        provider = HybridPriceProvider()
        symbols = ["BTC/USDT:USDT"]
        
        # Mock WebSocketManager qui ne se connecte pas
        with patch('api.price_provider.WebSocketManager') as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.connected = False  # Pas connecté
            mock_ws_instance._ws = None  # Pas de connexion WebSocket
            mock_ws_instance.start = AsyncMock()
            MockWS.return_value = mock_ws_instance
            
            # Mock logger pour capturer warning
            with patch('api.price_provider.logger') as mock_logger:
                await provider.start_websocket(symbols)
                
                # Vérifier qu'un warning a été émis (le message peut varier)
                mock_logger.warning.assert_called()
    
    @pytest.mark.asyncio
    async def test_stop_websocket_with_lifecycle_lock(self):
        """Test stop_websocket avec lifecycle lock"""
        provider = HybridPriceProvider()
        
        # Créer un manager actif
        mock_ws_manager = AsyncMock()
        mock_ws_manager.disconnect = AsyncMock()
        provider.ws_manager = mock_ws_manager
        provider.use_websocket = True
        
        # Stop WebSocket
        await provider.stop_websocket()
        
        # Vérifier nettoyage
        mock_ws_manager.disconnect.assert_called_once()
        assert provider.ws_manager is None
        assert provider.use_websocket is True  # use_websocket reste True après stop

    @pytest.mark.asyncio
    async def test_resubscribe_after_reconnect_uses_monitored_symbols(self, provider, monkeypatch: pytest.MonkeyPatch):
        ws_manager = AsyncMock()
        ws_manager.connected = True
        ws_manager._ws = Mock()
        ws_manager.subscribe_ticker = AsyncMock()
        provider.ws_manager = ws_manager
        provider.monitored_symbols = ["BTC/USDT:USDT", "ETH/USDT:USDT"]

        # Eviter imports circulaires dans la méthode
        monkeypatch.setattr('api.price_provider.HybridPriceProvider._wait_for_ws_ready', AsyncMock(return_value=True))

        # main.app_state absent -> doit tomber sur monitored_symbols
        import main
        monkeypatch.setattr(main, 'app_state', None, raising=False)
        monkeypatch.setattr(main, 'position_manager', None, raising=False)

        await provider._resubscribe_after_reconnect()
        assert ws_manager.subscribe_ticker.await_count == 2

    @pytest.mark.asyncio
    async def test_resubscribe_after_reconnect_returns_if_ws_not_ready(self, provider, monkeypatch: pytest.MonkeyPatch):
        ws_manager = AsyncMock()
        ws_manager.connected = True
        ws_manager._ws = Mock()
        ws_manager.subscribe_ticker = AsyncMock()
        provider.ws_manager = ws_manager
        provider.monitored_symbols = ["BTC/USDT:USDT"]
        monkeypatch.setattr('api.price_provider.HybridPriceProvider._wait_for_ws_ready', AsyncMock(return_value=False))

        await provider._resubscribe_after_reconnect()
        ws_manager.subscribe_ticker.assert_not_called()


class TestSlRealtime:
    @pytest.mark.asyncio
    async def test_check_sl_realtime_long_triggers_and_disables_callback(self, provider):
        called = []

        async def cb(price, reason):
            called.append((price, reason))

        provider.set_sl_check_callback(
            cb,
            symbol="BTC/USDT:USDT",
            direction="LONG",
            sl_level=100.0,
            entry_price=200.0,
        )

        # prix <= sl_level => trigger
        await provider._check_sl_realtime(99.0, provider._sl_check_params)
        assert called and called[0][1] == 'SL'
        assert provider._sl_check_callback is None
        assert provider._sl_check_params is None

    @pytest.mark.asyncio
    async def test_check_sl_realtime_short_triggers_ts_when_pnl_positive(self, provider):
        called = []

        async def cb(price, reason):
            called.append((price, reason))

        provider.set_sl_check_callback(
            cb,
            symbol="BTC/USDT:USDT",
            direction="SHORT",
            sl_level=100.0,
            entry_price=200.0,
        )

        # SHORT: trigger if current >= sl_level, here current=150 triggers; pnl positive because price dropped from 200 to 150
        await provider._check_sl_realtime(150.0, provider._sl_check_params)
        assert called and called[0][1] == 'TS'

    def test_update_sl_level_updates_params(self, provider):
        async def cb(price, reason):
            return None

        provider.set_sl_check_callback(
            cb,
            symbol="BTC/USDT:USDT",
            direction="LONG",
            sl_level=100.0,
            entry_price=200.0,
        )

        provider.update_sl_level(120.0)
        assert provider._sl_check_params["sl_level"] == 120.0


# Tests d'intégration
class TestIntegration:
    """Tests d'intégration"""

    @pytest.mark.asyncio
    async def test_websocket_to_rest_fallback_integration(self):
        """Test intégration basculement WebSocket -> REST"""
        provider = HybridPriceProvider()

        # Simuler WebSocket down
        provider.use_websocket = False
        provider.ws_manager = None

        # Mock REST client
        mock_ticker = {
            "last": 1.234,
            "quoteVolume": 1000000
        }
        provider.rest_client = AsyncMock()
        provider.rest_client.fetch_ticker = AsyncMock(return_value=mock_ticker)

        # Récupérer prix
        symbol = "WLD/USDT:USDT"
        result = await provider.get_price(symbol)

        # Devrait utiliser REST
        assert result is not None
        assert result["lastPrice"] == 1.234
        provider.rest_client.fetch_ticker.assert_called_once_with(symbol)
    
    @pytest.mark.asyncio
    async def test_concurrent_websocket_operations(self):
        """Test opérations WebSocket concurrentes (race conditions)"""
        provider = HybridPriceProvider()
        symbols = ["BTC/USDT:USDT", "ETH/USDT:USDT"]
        
        # Mock WebSocketManager
        with patch('api.price_provider.WebSocketManager') as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance._connected = True
            mock_ws_instance.start = AsyncMock()
            mock_ws_instance.subscribe_ticker = AsyncMock()
            mock_ws_instance.disconnect = AsyncMock()
            mock_ws_instance.connected = True
            MockWS.return_value = mock_ws_instance
            
            # Lancer plusieurs opérations en parallèle
            tasks = [
                asyncio.create_task(provider.start_websocket(symbols)),
                asyncio.create_task(provider.start_websocket(symbols)),
                asyncio.create_task(provider.stop_websocket())
            ]
            
            # Attendre toutes les tâches
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Vérifier qu'aucune exception n'est levée
            for result in results:
                assert not isinstance(result, Exception)
