"""
Tests pour api/price_provider.py
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from api.price_provider import HybridPriceProvider, get_price_provider


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

        # 🔥 FIX: Vérifier disconnect mais ws_manager n'est plus mis à None (réutilisation)
        mock_ws_manager.disconnect.assert_called_once()
        # ws_manager n'est plus mis à None pour permettre la réutilisation
        assert provider.ws_manager is not None

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
