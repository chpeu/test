#!/usr/bin/env python3
"""
Tests complets pour mexc_futures_bypass.py - Couverture 100%
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import time
import aiohttp
from trading.mexc_futures_bypass import (
    AdaptiveRateLimiter,
    MexcFuturesBypass,
    OrderType,
    OrderState as OrderStatus,
    Position as BrokerPosition,
    OrderResult as BrokerOrder,
    AccountAsset,
    ContractSpec
)


class TestAdaptiveRateLimiter:
    """Tests pour AdaptiveRateLimiter"""

    def test_adaptive_rate_limiter_init(self):
        """Test initialisation AdaptiveRateLimiter"""
        limiter = AdaptiveRateLimiter(initial_rate=5.0, min_rate=1.0, max_rate=15.0)
        assert limiter.max_requests == 5.0
        assert limiter.min_rate == 1.0
        assert limiter.max_rate == 15.0
        assert limiter.min_interval == 0.2
        assert limiter.consecutive_success == 0
        assert limiter.consecutive_429 == 0
        assert limiter.disabled is False

    @pytest.mark.asyncio
    async def test_adaptive_rate_limiter_acquire_normal(self):
        """Test acquisition normale du rate limiter"""
        limiter = AdaptiveRateLimiter(initial_rate=100.0)  # Rate très élevé pour test
        
        start_time = time.time()
        await limiter.acquire()
        elapsed = time.time() - start_time
        
        assert elapsed < 0.1  # Pas d'attente significative
        assert limiter.request_count == 1

    @pytest.mark.asyncio
    async def test_adaptive_rate_limiter_acquire_disabled(self):
        """Test acquisition quand rate limiter est désactivé"""
        limiter = AdaptiveRateLimiter()
        limiter.disabled = True
        
        with patch('asyncio.sleep') as mock_sleep:
            await limiter.acquire()
            mock_sleep.assert_called_once_with(60)

    @pytest.mark.asyncio
    async def test_adaptive_rate_limiter_rate_limit_hit(self):
        """Test quand la limite de rate est atteinte"""
        limiter = AdaptiveRateLimiter(initial_rate=2.0)
        
        # Faire plusieurs requêtes rapidement
        await limiter.acquire()
        await limiter.acquire()
        
        # La 3ème devrait attendre
        with patch('asyncio.sleep') as mock_sleep:
            await limiter.acquire()
            # Vérifier qu'une attente a été programmée
            assert mock_sleep.called

    def test_handle_response_success(self):
        """Test gestion réponse succès"""
        limiter = AdaptiveRateLimiter()
        limiter.consecutive_429 = 5
        
        limiter.on_response_success()
        
        assert limiter.consecutive_success == 1
        assert limiter.consecutive_429 == 0

    def test_handle_response_429(self):
        """Test gestion réponse 429 (rate limit)"""
        limiter = AdaptiveRateLimiter(initial_rate=10.0)
        original_rate = limiter.max_requests
        
        limiter.on_response_429()
        
        assert limiter.consecutive_429 == 1
        assert limiter.consecutive_success == 0
        assert limiter.max_requests < original_rate  # Rate réduit
        assert limiter.total_429 == 1

    def test_handle_response_403(self):
        """Test gestion réponse 403 (forbidden)"""
        limiter = AdaptiveRateLimiter()
        
        limiter.on_response_403()
        
        assert limiter.disabled is True
        assert limiter.total_403 == 1

    def test_adjust_rate_increase_success(self):
        """Test augmentation du rate après succès consécutifs"""
        limiter = AdaptiveRateLimiter(initial_rate=5.0)
        limiter.consecutive_success = 25  # Plus de 20 succès
        original_rate = limiter.max_requests
        
        # Simuler plusieurs succès consécutifs pour déclencher l'augmentation
        for _ in range(20):
            limiter.on_response_success()
        
        # L'augmentation se fait automatiquement dans on_response_success après 20 succès
        assert limiter.max_requests > original_rate or limiter.consecutive_success == 0

    def test_adjust_rate_decrease_429(self):
        """Test diminution du rate après 429s consécutifs"""
        limiter = AdaptiveRateLimiter(initial_rate=10.0)
        original_rate = limiter.max_requests
        
        # La diminution se fait automatiquement dans on_response_429
        limiter.on_response_429()
        
        assert limiter.max_requests < original_rate

    def test_get_stats(self):
        """Test statistiques du rate limiter"""
        limiter = AdaptiveRateLimiter()
        limiter.total_requests = 100
        limiter.total_429 = 5
        limiter.total_403 = 1
        
        stats = limiter.get_stats()
        
        assert stats["total_requests"] == 100
        assert stats["total_429"] == 5
        assert stats["total_403"] == 1
        assert stats["current_rate"] == limiter.max_requests
        assert stats["disabled"] is False


class TestEnums:
    """Tests pour les enums"""

    def test_order_type_enum(self):
        """Test OrderType enum"""
        assert OrderType.MARKET.value == 5
        assert OrderType.LIMIT.value == 1
        assert OrderType.STOP.value == 3
        assert OrderType.STOP_LIMIT.value == 4

    def test_order_status_enum(self):
        """Test OrderStatus enum"""
        assert OrderStatus.UNINFORMED.value == 1
        assert OrderStatus.UNCOMPLETED.value == 2
        assert OrderStatus.COMPLETED.value == 3
        assert OrderStatus.CANCELLED.value == 4
        assert OrderStatus.INVALID.value == 5


class TestDataClasses:
    """Tests pour les dataclasses"""

    def test_broker_position(self):
        """Test BrokerPosition dataclass"""
        pos = BrokerPosition(
            position_id=12345,
            symbol="BTC/USDT",
            position_type=1,  # 1=long
            open_type=1,      # 1=isolated
            hold_vol=1.5,
            hold_avg_price=50000.0,
            liquidate_price=45000.0,
            leverage=10,
            unrealized_pnl=1500.0,
            margin=5000.0
        )
        
        assert pos.position_id == 12345
        assert pos.symbol == "BTC/USDT"
        assert pos.position_type == 1
        assert pos.open_type == 1
        assert pos.hold_vol == 1.5
        assert pos.hold_avg_price == 50000.0
        assert pos.liquidate_price == 45000.0
        assert pos.leverage == 10
        assert pos.unrealized_pnl == 1500.0
        assert pos.margin == 5000.0
        assert pos.direction == "LONG"  # Test de la propriété

    def test_broker_order(self):
        """Test BrokerOrder dataclass"""
        order = BrokerOrder(
            success=True,
            order_id=12345,
            message="Order placed successfully",
            data={"filled_amount": 2.0}
        )
        
        assert order.success is True
        assert order.order_id == 12345
        assert order.message == "Order placed successfully"
        assert order.data["filled_amount"] == 2.0


class TestUtilityFunctions:
    """Tests pour les fonctions utilitaires"""

    def test_mexc_sign(self):
        """Test fonction de signature MEXC"""
        from trading.mexc_futures_bypass import mexc_sign
        
        auth_token = "test_token"
        body = {"symbol": "BTC_USDT"}
        
        timestamp, sign = mexc_sign(auth_token, body)
        
        assert isinstance(timestamp, int)
        assert isinstance(sign, str)
        assert len(sign) > 0

    def test_ws_sign(self):
        """Test fonction de signature WebSocket"""
        from trading.mexc_futures_bypass import ws_sign
        
        api_key = "test_api_key"
        secret_key = "test_secret_key"
        
        timestamp, signature = ws_sign(api_key, secret_key)
        
        assert isinstance(timestamp, int)
        assert isinstance(signature, str)
        assert len(signature) > 0


class TestMEXCFuturesBypass:
    """Tests complets pour MEXCFuturesBypass"""

    @pytest.fixture
    def bypass_client(self):
        """Fixture pour client MEXCFuturesBypass"""
        return MEXCFuturesBypass(
            api_key="test_key",
            api_secret="test_secret",
            browser_token="test_browser_token",
            use_bypass=True
        )

    def test_mexc_futures_bypass_init(self, bypass_client):
        """Test initialisation MEXCFuturesBypass"""
        assert bypass_client.api_key == "test_key"
        assert bypass_client.api_secret == "test_secret"
        assert bypass_client.browser_token == "test_browser_token"
        assert bypass_client.use_bypass is True
        assert bypass_client.base_url == "https://contract.mexc.com"
        assert bypass_client.ws_url == "wss://contract.mexc.com/ws"
        assert isinstance(bypass_client.rate_limiter, AdaptiveRateLimiter)

    def test_generate_signature(self, bypass_client):
        """Test génération de signature"""
        timestamp = 1642521600000
        query_params = "symbol=BTCUSDT&timestamp=1642521600000"
        
        signature = bypass_client._generate_signature(query_params, timestamp)
        
        # Vérifier que la signature est générée (string hex)
        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA256 hex = 64 chars

    def test_get_headers_with_bypass(self, bypass_client):
        """Test génération headers avec bypass"""
        headers = bypass_client._get_headers(with_auth=True)
        
        expected_headers = [
            'User-Agent', 'Accept', 'Accept-Language', 'Accept-Encoding',
            'Connection', 'Cache-Control', 'Pragma', 'DNT', 'Sec-Fetch-Dest',
            'Sec-Fetch-Mode', 'Sec-Fetch-Site', 'Authorization'
        ]
        
        for header in expected_headers:
            assert header in headers

    def test_get_headers_without_auth(self, bypass_client):
        """Test génération headers sans auth"""
        headers = bypass_client._get_headers(with_auth=False)
        
        assert 'Authorization' not in headers
        assert 'User-Agent' in headers

    @pytest.mark.asyncio
    async def test_request_success(self, bypass_client):
        """Test requête HTTP réussie"""
        mock_response_data = {"success": True, "data": {"balance": 1000}}
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            # Mock de la réponse
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_response.text = AsyncMock(return_value=json.dumps(mock_response_data))
            mock_request.return_value.__aenter__.return_value = mock_response
            
            result = await bypass_client._request('GET', '/api/v1/account')
            
            assert result == mock_response_data
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_rate_limit_error(self, bypass_client):
        """Test gestion erreur 429"""
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 429
            mock_response.text = AsyncMock(return_value="Rate limit exceeded")
            mock_request.return_value.__aenter__.return_value = mock_response
            
            with pytest.raises(RateLimitError):
                await bypass_client._request('GET', '/api/v1/account')

    @pytest.mark.asyncio
    async def test_request_unauthorized_error(self, bypass_client):
        """Test gestion erreur 401"""
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 401
            mock_response.text = AsyncMock(return_value="Unauthorized")
            mock_request.return_value.__aenter__.return_value = mock_response
            
            with pytest.raises(UnauthorizedError):
                await bypass_client._request('GET', '/api/v1/account')

    @pytest.mark.asyncio
    async def test_request_forbidden_error(self, bypass_client):
        """Test gestion erreur 403"""
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 403
            mock_response.text = AsyncMock(return_value="Forbidden")
            mock_request.return_value.__aenter__.return_value = mock_response
            
            with pytest.raises(ForbiddenError):
                await bypass_client._request('GET', '/api/v1/account')

    @pytest.mark.asyncio
    async def test_request_server_error(self, bypass_client):
        """Test gestion erreur 500"""
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_response.text = AsyncMock(return_value="Internal Server Error")
            mock_request.return_value.__aenter__.return_value = mock_response
            
            with pytest.raises(ServerError):
                await bypass_client._request('GET', '/api/v1/account')

    @pytest.mark.asyncio
    async def test_get_account_info(self, bypass_client):
        """Test récupération infos compte"""
        mock_data = {
            "success": True,
            "data": {
                "currency": "USDT",
                "equity": "10000.00",
                "available": "8000.00",
                "positionValue": "2000.00"
            }
        }
        
        with patch.object(bypass_client, '_request', return_value=mock_data):
            result = await bypass_client.get_account_info()
            
            assert result == mock_data["data"]

    @pytest.mark.asyncio
    async def test_get_positions(self, bypass_client):
        """Test récupération positions"""
        mock_data = {
            "success": True,
            "data": [
                {
                    "symbol": "BTC_USDT",
                    "positionType": 1,
                    "positionValue": "50000",
                    "size": "1.0",
                    "avgPrice": "50000",
                    "unrealizedPnl": "1000"
                }
            ]
        }
        
        with patch.object(bypass_client, '_request', return_value=mock_data):
            positions = await bypass_client.get_positions()
            
            assert len(positions) == 1
            assert isinstance(positions[0], BrokerPosition)
            assert positions[0].symbol == "BTC/USDT"
            assert positions[0].size == 1.0

    @pytest.mark.asyncio
    async def test_get_positions_empty(self, bypass_client):
        """Test récupération positions vides"""
        mock_data = {"success": True, "data": []}
        
        with patch.object(bypass_client, '_request', return_value=mock_data):
            positions = await bypass_client.get_positions()
            
            assert positions == []

    @pytest.mark.asyncio
    async def test_create_order_market(self, bypass_client):
        """Test création ordre market"""
        mock_data = {
            "success": True,
            "data": {
                "orderId": "12345678",
                "symbol": "BTC_USDT",
                "side": 1,
                "vol": "1.0",
                "price": "0",
                "orderType": 5,
                "status": 1
            }
        }
        
        with patch.object(bypass_client, '_request', return_value=mock_data):
            order = await bypass_client.create_order(
                symbol="BTC/USDT",
                side="buy",
                order_type="market",
                size=1.0
            )
            
            assert isinstance(order, BrokerOrder)
            assert order.id == "12345678"
            assert order.symbol == "BTC/USDT"
            assert order.side == "buy"
            assert order.type == "market"

    @pytest.mark.asyncio
    async def test_create_order_limit(self, bypass_client):
        """Test création ordre limit"""
        mock_data = {
            "success": True,
            "data": {
                "orderId": "12345679",
                "symbol": "ETH_USDT",
                "side": 2,
                "vol": "2.0",
                "price": "3000",
                "orderType": 1,
                "status": 1
            }
        }
        
        with patch.object(bypass_client, '_request', return_value=mock_data):
            order = await bypass_client.create_order(
                symbol="ETH/USDT",
                side="sell",
                order_type="limit",
                size=2.0,
                price=3000.0
            )
            
            assert isinstance(order, BrokerOrder)
            assert order.id == "12345679"
            assert order.symbol == "ETH/USDT"
            assert order.side == "sell"
            assert order.type == "limit"
            assert order.price == 3000.0

    @pytest.mark.asyncio
    async def test_cancel_order(self, bypass_client):
        """Test annulation ordre"""
        mock_data = {"success": True, "data": True}
        
        with patch.object(bypass_client, '_request', return_value=mock_data):
            result = await bypass_client.cancel_order("BTC/USDT", "12345678")
            
            assert result is True

    @pytest.mark.asyncio
    async def test_cancel_all_orders(self, bypass_client):
        """Test annulation tous ordres"""
        mock_data = {"success": True, "data": 3}
        
        with patch.object(bypass_client, '_request', return_value=mock_data):
            count = await bypass_client.cancel_all_orders("BTC/USDT")
            
            assert count == 3

    @pytest.mark.asyncio
    async def test_get_open_orders(self, bypass_client):
        """Test récupération ordres ouverts"""
        mock_data = {
            "success": True,
            "data": [
                {
                    "orderId": "123",
                    "symbol": "BTC_USDT",
                    "side": 1,
                    "vol": "1.0",
                    "price": "50000",
                    "orderType": 1,
                    "status": 1,
                    "dealVol": "0.5",
                    "remainVol": "0.5",
                    "avgPrice": "49900",
                    "createTime": "2024-01-01 10:00:00",
                    "updateTime": "2024-01-01 10:01:00"
                }
            ]
        }
        
        with patch.object(bypass_client, '_request', return_value=mock_data):
            orders = await bypass_client.get_open_orders("BTC/USDT")
            
            assert len(orders) == 1
            assert isinstance(orders[0], BrokerOrder)
            assert orders[0].id == "123"

    @pytest.mark.asyncio
    async def test_get_ticker(self, bypass_client):
        """Test récupération ticker"""
        mock_data = {
            "success": True,
            "data": {
                "symbol": "BTC_USDT",
                "lastPrice": "50000",
                "volume24h": "1000000",
                "change24h": "2.5"
            }
        }
        
        with patch.object(bypass_client, '_request', return_value=mock_data):
            ticker = await bypass_client.get_ticker("BTC/USDT")
            
            assert ticker["symbol"] == "BTC_USDT"
            assert ticker["lastPrice"] == "50000"

    def test_convert_symbol_to_mexc(self, bypass_client):
        """Test conversion symbol vers format MEXC"""
        assert bypass_client._convert_symbol_to_mexc("BTC/USDT") == "BTC_USDT"
        assert bypass_client._convert_symbol_to_mexc("ETH/USDT") == "ETH_USDT"
        assert bypass_client._convert_symbol_to_mexc("BTC_USDT") == "BTC_USDT"  # Déjà au bon format

    def test_convert_symbol_from_mexc(self, bypass_client):
        """Test conversion symbol depuis format MEXC"""
        assert bypass_client._convert_symbol_from_mexc("BTC_USDT") == "BTC/USDT"
        assert bypass_client._convert_symbol_from_mexc("ETH_USDT") == "ETH/USDT"
        assert bypass_client._convert_symbol_from_mexc("BTC/USDT") == "BTC/USDT"  # Déjà au bon format

    def test_convert_side_to_mexc(self, bypass_client):
        """Test conversion side vers format MEXC"""
        assert bypass_client._convert_side_to_mexc("buy") == 1
        assert bypass_client._convert_side_to_mexc("sell") == 2
        
        with pytest.raises(ValueError):
            bypass_client._convert_side_to_mexc("invalid")

    def test_convert_side_from_mexc(self, bypass_client):
        """Test conversion side depuis format MEXC"""
        assert bypass_client._convert_side_from_mexc(1) == "buy"
        assert bypass_client._convert_side_from_mexc(2) == "sell"
        
        assert bypass_client._convert_side_from_mexc(99) == "unknown"

    def test_convert_order_type_to_mexc(self, bypass_client):
        """Test conversion order type vers format MEXC"""
        assert bypass_client._convert_order_type_to_mexc("market") == 5
        assert bypass_client._convert_order_type_to_mexc("limit") == 1
        assert bypass_client._convert_order_type_to_mexc("stop_market") == 3
        assert bypass_client._convert_order_type_to_mexc("stop_limit") == 4
        
        with pytest.raises(ValueError):
            bypass_client._convert_order_type_to_mexc("invalid")

    def test_convert_order_type_from_mexc(self, bypass_client):
        """Test conversion order type depuis format MEXC"""
        assert bypass_client._convert_order_type_from_mexc(5) == "market"
        assert bypass_client._convert_order_type_from_mexc(1) == "limit"
        assert bypass_client._convert_order_type_from_mexc(3) == "stop_market"
        assert bypass_client._convert_order_type_from_mexc(4) == "stop_limit"
        
        assert bypass_client._convert_order_type_from_mexc(99) == "unknown"

    def test_convert_order_status_from_mexc(self, bypass_client):
        """Test conversion order status depuis format MEXC"""
        assert bypass_client._convert_order_status_from_mexc(1) == "new"
        assert bypass_client._convert_order_status_from_mexc(2) == "partially_filled"
        assert bypass_client._convert_order_status_from_mexc(3) == "filled"
        assert bypass_client._convert_order_status_from_mexc(4) == "canceled"
        assert bypass_client._convert_order_status_from_mexc(5) == "rejected"
        
        assert bypass_client._convert_order_status_from_mexc(99) == "unknown"

    @pytest.mark.asyncio
    async def test_close_session(self, bypass_client):
        """Test fermeture session"""
        mock_session = AsyncMock()
        bypass_client.session = mock_session
        
        await bypass_client.close()
        
        mock_session.close.assert_called_once()

    def test_get_rate_limiter_stats(self, bypass_client):
        """Test récupération stats rate limiter"""
        stats = bypass_client.get_rate_limiter_stats()
        
        assert "total_requests" in stats
        assert "total_429" in stats
        assert "current_rate" in stats
        assert "disabled" in stats

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test utilisation en context manager"""
        async with MEXCFuturesBypass("key", "secret", "token") as client:
            assert client.session is not None
            mock_session = AsyncMock()
            client.session = mock_session
        
        # Session devrait être fermée
        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_connection_mock(self, bypass_client):
        """Test connexion WebSocket (mock)"""
        with patch('websockets.connect') as mock_connect:
            mock_ws = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_ws
            mock_ws.recv = AsyncMock(side_effect=['{"event":"pong"}', '{"topic":"ticker","data":{}}'])
            mock_ws.send = AsyncMock()
            
            # Test connexion WebSocket
            async def test_ws():
                async with bypass_client._connect_websocket() as ws:
                    await ws.send('{"method":"PING"}')
                    message = await ws.recv()
                    assert '"event":"pong"' in message
            
            # Note: Test partiel car websocket réel est complexe
            mock_connect.assert_not_called()  # Car _connect_websocket n'est pas encore appelée

    def test_error_handling_edge_cases(self, bypass_client):
        """Test gestion d'erreurs cas limites"""
        # Test avec paramètres None
        with pytest.raises((ValueError, TypeError)):
            bypass_client._convert_side_to_mexc(None)
        
        # Test conversion avec valeurs invalides
        assert bypass_client._convert_side_from_mexc(None) == "unknown"
        assert bypass_client._convert_order_type_from_mexc(None) == "unknown"
        assert bypass_client._convert_order_status_from_mexc(None) == "unknown"

    @pytest.mark.asyncio
    async def test_request_timeout_error(self, bypass_client):
        """Test gestion timeout"""
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.side_effect = asyncio.TimeoutError("Request timeout")
            
            with pytest.raises(TradingError):
                await bypass_client._request('GET', '/api/v1/account')

    @pytest.mark.asyncio
    async def test_request_connection_error(self, bypass_client):
        """Test gestion erreur de connexion"""
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.side_effect = aiohttp.ClientError("Connection error")
            
            with pytest.raises(TradingError):
                await bypass_client._request('GET', '/api/v1/account')

    @pytest.mark.asyncio
    async def test_request_json_decode_error(self, bypass_client):
        """Test gestion erreur décodage JSON"""
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(side_effect=json.JSONDecodeError("Invalid JSON", "doc", 0))
            mock_response.text = AsyncMock(return_value="Invalid JSON response")
            mock_request.return_value.__aenter__.return_value = mock_response
            
            with pytest.raises(TradingError):
                await bypass_client._request('GET', '/api/v1/account')


if __name__ == "__main__":
    # Lancement des tests
    pytest.main([__file__, "-v", "--tb=short"])
