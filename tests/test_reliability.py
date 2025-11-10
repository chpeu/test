"""
Tests pour api/reliability.py
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from api.reliability import (
    AdaptiveCircuitBreaker,
    fetch_with_retry,
    with_circuit_breaker,
    fetch_with_all_protections,
    WebSocketManager,
    _adaptive_circuit_breaker
)


class TestAdaptiveCircuitBreaker:
    """Tests pour AdaptiveCircuitBreaker"""

    def test_init_default_values(self):
        """Test initialisation avec valeurs par défaut"""
        cb = AdaptiveCircuitBreaker()
        assert cb.base_fail_max == 5
        assert cb.base_timeout == 60
        assert cb.error_rate == 0.0
        assert cb.success_count == 0
        assert cb.error_count == 0

    def test_init_custom_values(self):
        """Test initialisation avec valeurs personnalisées"""
        cb = AdaptiveCircuitBreaker(base_fail_max=10, base_timeout=120)
        assert cb.base_fail_max == 10
        assert cb.base_timeout == 120

    def test_record_success(self):
        """Test enregistrement succès"""
        cb = AdaptiveCircuitBreaker()
        initial_count = cb.success_count
        cb.record_success()
        assert cb.success_count == initial_count + 1

    def test_record_failure(self):
        """Test enregistrement échec"""
        cb = AdaptiveCircuitBreaker()
        initial_count = cb.error_count
        cb.record_failure()
        assert cb.error_count == initial_count + 1

    def test_update_metrics_insufficient_data(self):
        """Test mise à jour métriques avec données insuffisantes"""
        cb = AdaptiveCircuitBreaker(base_fail_max=5, base_timeout=60)
        # Moins de 10 requêtes total
        for _ in range(5):
            cb.record_success()

        # Les seuils ne devraient pas changer
        assert cb.failure_threshold == 5
        assert cb.timeout_duration == 60

    def test_update_metrics_low_error_rate(self):
        """Test adaptation avec taux d'erreur faible (<5%)"""
        cb = AdaptiveCircuitBreaker(base_fail_max=5, base_timeout=60)

        # 100 succès, 2 erreurs = 2% erreurs
        for _ in range(100):
            cb.record_success()
        for _ in range(2):
            cb.record_failure()

        # Devrait être plus tolérant
        assert cb.failure_threshold == 10  # 5 * 2
        assert cb.timeout_duration == 30   # 60 // 2

    def test_update_metrics_medium_error_rate(self):
        """Test adaptation avec taux d'erreur moyen (5-15%)"""
        cb = AdaptiveCircuitBreaker(base_fail_max=5, base_timeout=60)

        # 90 succès, 10 erreurs = 10% erreurs
        for _ in range(90):
            cb.record_success()
        for _ in range(10):
            cb.record_failure()

        # Devrait rester normal
        assert cb.failure_threshold == 5
        assert cb.timeout_duration == 60

    def test_update_metrics_high_error_rate(self):
        """Test adaptation avec taux d'erreur élevé (>15%)"""
        cb = AdaptiveCircuitBreaker(base_fail_max=5, base_timeout=60)

        # 80 succès, 20 erreurs = 20% erreurs
        for _ in range(80):
            cb.record_success()
        for _ in range(20):
            cb.record_failure()

        # Devrait être plus strict
        assert cb.failure_threshold == 3  # max(3, 5 // 2)
        assert cb.timeout_duration == 120  # 60 * 2

    def test_partial_reset_after_100_requests(self):
        """Test reset partiel compteurs après 100 requêtes"""
        cb = AdaptiveCircuitBreaker()

        # Faire 100 requêtes
        for _ in range(60):
            cb.record_success()
        for _ in range(40):
            cb.record_failure()

        # Les compteurs devraient être réduits de moitié
        assert cb.success_count == 30  # 60 * 0.5
        assert cb.error_count == 20    # 40 * 0.5

    @pytest.mark.asyncio
    async def test_call_async_success(self):
        """Test appel async avec succès"""
        cb = AdaptiveCircuitBreaker()

        async def test_func():
            return "success"

        result = await cb.call_async(test_func)
        assert result == "success"
        assert cb.success_count == 1
        assert cb.error_count == 0

    @pytest.mark.asyncio
    async def test_call_async_failure(self):
        """Test appel async avec échec"""
        cb = AdaptiveCircuitBreaker()

        async def test_func():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            await cb.call_async(test_func)

        assert cb.success_count == 0
        assert cb.error_count == 1


class TestFetchWithRetry:
    """Tests pour fetch_with_retry"""

    @pytest.mark.asyncio
    async def test_fetch_success_first_try(self):
        """Test fetch réussit du premier coup"""
        async def mock_func():
            return "success"

        result = await fetch_with_retry(mock_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_fetch_connection_error_retry(self):
        """Test retry sur ConnectionError"""
        call_count = 0

        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Connection failed")
            return "success"

        result = await fetch_with_retry(mock_func)
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_timeout_error_retry(self):
        """Test retry sur TimeoutError"""
        call_count = 0

        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("Timeout")
            return "success"

        result = await fetch_with_retry(mock_func)
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_max_attempts_exceeded(self):
        """Test échec après max tentatives"""
        async def mock_func():
            raise ConnectionError("Connection failed")

        with pytest.raises(ConnectionError):
            await fetch_with_retry(mock_func)

    @pytest.mark.asyncio
    async def test_fetch_non_retryable_error(self):
        """Test erreur non-retryable ne déclenche pas retry"""
        call_count = 0

        async def mock_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Non-retryable error")

        with pytest.raises(ValueError):
            await fetch_with_retry(mock_func)

        # Devrait échouer immédiatement sans retry
        assert call_count == 1


class TestWithCircuitBreaker:
    """Tests pour décorateur with_circuit_breaker"""

    @pytest.mark.asyncio
    async def test_decorated_function_success(self):
        """Test fonction décorée réussit"""
        @with_circuit_breaker
        async def test_func():
            return "success"

        result = await test_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_decorated_function_failure(self):
        """Test fonction décorée échoue"""
        @with_circuit_breaker
        async def test_func():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            await test_func()


class TestFetchWithAllProtections:
    """Tests pour fetch_with_all_protections"""

    @pytest.mark.asyncio
    async def test_fetch_all_protections_success(self):
        """Test fetch avec toutes protections réussit"""
        async def mock_func():
            return "success"

        result = await fetch_with_all_protections(mock_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_fetch_all_protections_with_retry(self):
        """Test fetch avec retry automatique"""
        call_count = 0

        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Connection failed")
            return "success"

        result = await fetch_with_all_protections(mock_func)
        assert result == "success"
        assert call_count == 2


class TestWebSocketManager:
    """Tests pour WebSocketManager"""

    def test_init(self):
        """Test initialisation WebSocketManager"""
        def mock_callback(data):
            pass

        ws = WebSocketManager("wss://test.com", mock_callback)
        assert ws.url == "wss://test.com"
        assert ws.callback == mock_callback
        assert ws._ws is None
        assert ws._running is False
        assert ws._connected is False
        assert ws._reconnecting is False

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test connexion WebSocket réussie"""
        def mock_callback(data):
            pass

        ws = WebSocketManager("wss://test.com", mock_callback)

        # Mock websockets.connect
        mock_ws_conn = AsyncMock()
        with patch('api.reliability.websockets.connect', return_value=mock_ws_conn):
            await ws.connect()
            assert ws._connected is True
            assert ws._ws == mock_ws_conn

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test échec connexion WebSocket"""
        def mock_callback(data):
            pass

        ws = WebSocketManager("wss://test.com", mock_callback)

        # Mock websockets.connect avec exception
        with patch('api.reliability.websockets.connect', side_effect=ConnectionError("Connection failed")):
            with pytest.raises(ConnectionError):
                await ws.connect()
            assert ws._connected is False

    @pytest.mark.asyncio
    async def test_disconnect_full_stop(self):
        """Test déconnexion complète"""
        def mock_callback(data):
            pass

        ws = WebSocketManager("wss://test.com", mock_callback)
        ws._running = True
        ws._connected = True
        ws._ws = AsyncMock()

        await ws.disconnect(stop_running=True)

        assert ws._running is False
        assert ws._connected is False
        ws._ws.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_for_reconnect(self):
        """Test déconnexion pour reconnexion (sans arrêter _running)"""
        def mock_callback(data):
            pass

        ws = WebSocketManager("wss://test.com", mock_callback)
        ws._running = True
        ws._connected = True
        ws._ws = AsyncMock()

        await ws.disconnect(stop_running=False)

        # _running devrait rester True pour permettre reconnexion
        assert ws._running is True
        assert ws._connected is False
        ws._ws.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message(self):
        """Test envoi message"""
        def mock_callback(data):
            pass

        ws = WebSocketManager("wss://test.com", mock_callback)
        ws._ws = AsyncMock()

        message = {"test": "data"}
        await ws.send(message)

        ws._ws.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscribe_ticker_ccxt_format(self):
        """Test souscription ticker format ccxt"""
        def mock_callback(data):
            pass

        ws = WebSocketManager("wss://test.com", mock_callback)
        ws._ws = AsyncMock()

        await ws.subscribe_ticker("WLD/USDT:USDT")

        # Devrait convertir en format MEXC
        ws._ws.send.assert_called_once()
        call_args = ws._ws.send.call_args[0][0]
        import json
        sent_message = json.loads(call_args)
        assert sent_message["param"]["symbol"] == "WLD_USDT"

    @pytest.mark.asyncio
    async def test_subscribe_ticker_simple_format(self):
        """Test souscription ticker format simple"""
        def mock_callback(data):
            pass

        ws = WebSocketManager("wss://test.com", mock_callback)
        ws._ws = AsyncMock()

        await ws.subscribe_ticker("WLD/USDT")

        ws._ws.send.assert_called_once()
        call_args = ws._ws.send.call_args[0][0]
        import json
        sent_message = json.loads(call_args)
        assert sent_message["param"]["symbol"] == "WLD_USDT"

    @pytest.mark.asyncio
    async def test_send_ping(self):
        """Test envoi ping"""
        def mock_callback(data):
            pass

        ws = WebSocketManager("wss://test.com", mock_callback)
        ws._ws = AsyncMock()

        await ws.send_ping()

        ws._ws.send.assert_called_once()

    def test_connected_property(self):
        """Test propriété connected"""
        def mock_callback(data):
            pass

        ws = WebSocketManager("wss://test.com", mock_callback)
        assert ws.connected is False

        ws._connected = True
        assert ws.connected is True

    @pytest.mark.asyncio
    async def test_reconnect_already_reconnecting(self):
        """Test reconnect ignoré si déjà en cours"""
        def mock_callback(data):
            pass

        ws = WebSocketManager("wss://test.com", mock_callback)
        ws._reconnecting = True

        # Ne devrait rien faire
        await ws._reconnect()

        # _reconnect_task ne devrait pas être créée
        assert ws._reconnect_task is None

    def test_adaptive_circuit_breaker_singleton(self):
        """Test que le circuit breaker adaptatif est bien une instance globale"""
        assert _adaptive_circuit_breaker is not None
        assert isinstance(_adaptive_circuit_breaker, AdaptiveCircuitBreaker)


# Tests d'intégration
class TestIntegration:
    """Tests d'intégration"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_websocket(self):
        """Test intégration circuit breaker avec WebSocket"""
        call_count = 0

        def mock_callback(data):
            nonlocal call_count
            call_count += 1

        ws = WebSocketManager("wss://test.com", mock_callback)

        # Vérifier que l'instance est créée correctement
        assert ws._ws is None
        assert not ws.connected
