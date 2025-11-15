"""
Tests for api/mexc.py
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import asyncio
from api.mexc import MEXCClient, get_mexc_client


class TestMEXCClient:
    """Test cases for MEXCClient"""

    @pytest.mark.asyncio
    async def test_init(self):
        """Test MEXCClient initialization"""
        client = MEXCClient()

        assert client.session is not None
        assert client.exchange is not None
        assert client.cache == {}
        assert client.ws_manager is None

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_ticker_success(self):
        """Test successful ticker fetch"""
        client = MEXCClient()

        mock_ticker = {
            'symbol': 'BTC/USDT',
            'last': 50000,
            'bid': 49999,
            'ask': 50001
        }

        with patch('api.mexc.fetch_with_all_protections', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_ticker

            result = await client.fetch_ticker('BTC/USDT')

            assert result == mock_ticker
            mock_fetch.assert_called_once()

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_ticker_failure(self):
        """Test ticker fetch with exception"""
        client = MEXCClient()

        with patch('api.mexc.fetch_with_all_protections', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("API Error")

            result = await client.fetch_ticker('BTC/USDT')

            assert result is None

        await client.close()

    @pytest.mark.asyncio
    @patch('api.mexc.DEBUG_ENABLED', True)
    async def test_fetch_ticker_failure_debug(self):
        """Test ticker fetch failure with debug enabled"""
        client = MEXCClient()

        with patch('api.mexc.fetch_with_all_protections', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("API Error")

            result = await client.fetch_ticker('BTC/USDT')

            assert result is None

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_tickers_success(self):
        """Test successful tickers fetch"""
        client = MEXCClient()

        mock_tickers = {
            'BTC/USDT': {'last': 50000},
            'ETH/USDT': {'last': 3000}
        }

        with patch('api.mexc.fetch_with_all_protections', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_tickers

            result = await client.fetch_tickers()

            assert result == mock_tickers

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_tickers_failure(self):
        """Test tickers fetch with exception"""
        client = MEXCClient()

        with patch('api.mexc.fetch_with_all_protections', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("API Error")

            result = await client.fetch_tickers()

            assert result == {}

        await client.close()

    @pytest.mark.asyncio
    @patch('api.mexc.DEBUG_ENABLED', True)
    async def test_fetch_tickers_failure_debug(self):
        """Test tickers fetch failure with debug enabled"""
        client = MEXCClient()

        with patch('api.mexc.fetch_with_all_protections', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("API Error")

            result = await client.fetch_tickers()

            assert result == {}

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_success(self):
        """Test successful OHLCV fetch"""
        client = MEXCClient()

        mock_ohlcv = [
            [1234567890, 50000, 51000, 49000, 50500, 100],
            [1234567900, 50500, 51500, 50000, 51000, 150]
        ]

        with patch('api.mexc.fetch_with_all_protections', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_ohlcv

            result = await client.fetch_ohlcv('BTC/USDT', '1m', 100)

            assert result == mock_ohlcv

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_failure(self):
        """Test OHLCV fetch with exception"""
        client = MEXCClient()

        with patch('api.mexc.fetch_with_all_protections', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("API Error")

            result = await client.fetch_ohlcv('BTC/USDT', '5m', 50)

            assert result == []

        await client.close()

    @pytest.mark.asyncio
    @patch('api.mexc.DEBUG_ENABLED', True)
    async def test_fetch_ohlcv_failure_debug(self):
        """Test OHLCV fetch failure with debug enabled"""
        client = MEXCClient()

        with patch('api.mexc.fetch_with_all_protections', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("API Error")

            result = await client.fetch_ohlcv('ETH/USDT', '15m', 200)

            assert result == []

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_order_book_success(self):
        """Test successful order book fetch"""
        client = MEXCClient()

        mock_order_book = {
            'bids': [[50000, 1.5], [49999, 2.0]],
            'asks': [[50001, 1.2], [50002, 1.8]]
        }

        with patch('api.mexc.fetch_with_all_protections', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_order_book

            result = await client.fetch_order_book('BTC/USDT', 20)

            assert result == mock_order_book

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_order_book_failure(self):
        """Test order book fetch with exception"""
        client = MEXCClient()

        with patch('api.mexc.fetch_with_all_protections', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("API Error")

            result = await client.fetch_order_book('BTC/USDT')

            assert result is None

        await client.close()

    @pytest.mark.asyncio
    @patch('api.mexc.DEBUG_ENABLED', True)
    async def test_fetch_order_book_failure_debug(self):
        """Test order book fetch failure with debug enabled"""
        client = MEXCClient()

        with patch('api.mexc.fetch_with_all_protections', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("API Error")

            result = await client.fetch_order_book('ETH/USDT', 50)

            assert result is None

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_funding_rate_success(self):
        """Test successful funding rate fetch"""
        client = MEXCClient()

        mock_ticker = {
            'info': {'fundingRate': 0.0001}
        }

        with patch('api.mexc.fetch_with_all_protections', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_ticker

            result = await client.fetch_funding_rate('BTC/USDT')

            assert result == 0.0001

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_funding_rate_no_ticker(self):
        """Test funding rate fetch when ticker is None"""
        client = MEXCClient()

        with patch('api.mexc.fetch_with_all_protections', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None

            result = await client.fetch_funding_rate('BTC/USDT')

            assert result is None

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_funding_rate_no_funding_info(self):
        """Test funding rate fetch with ticker but no funding rate"""
        client = MEXCClient()

        mock_ticker = {
            'info': {}
        }

        with patch('api.mexc.fetch_with_all_protections', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_ticker

            result = await client.fetch_funding_rate('BTC/USDT')

            assert result == 0

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_funding_rate_exception(self):
        """Test funding rate fetch with exception"""
        client = MEXCClient()

        with patch('api.mexc.fetch_with_all_protections', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("API Error")

            result = await client.fetch_funding_rate('BTC/USDT')

            assert result is None

        await client.close()

    @pytest.mark.asyncio
    @patch('api.mexc.DEBUG_ENABLED', True)
    async def test_fetch_funding_rate_exception_debug(self):
        """Test funding rate fetch exception with debug enabled"""
        client = MEXCClient()

        with patch('api.mexc.fetch_with_all_protections', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("API Error")

            result = await client.fetch_funding_rate('ETH/USDT')

            assert result is None

        await client.close()

    @pytest.mark.asyncio
    async def test_close(self):
        """Test close method"""
        client = MEXCClient()

        # Mock session and exchange
        client.session = AsyncMock()
        client.exchange = AsyncMock()

        await client.close()

        client.session.close.assert_called_once()
        client.exchange.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_with_ws_manager(self):
        """Test close method with WebSocket manager"""
        client = MEXCClient()

        # Mock session, exchange and ws_manager
        client.session = AsyncMock()
        client.exchange = AsyncMock()
        client.ws_manager = AsyncMock()

        await client.close()

        client.ws_manager.disconnect.assert_called_once()
        client.session.close.assert_called_once()
        client.exchange.close.assert_called_once()

    def test_destructor(self):
        """Test __del__ method doesn't raise exceptions"""
        client = MEXCClient()
        # Just verify __del__ doesn't crash
        del client

    def test_get_mexc_client_singleton(self):
        """Test get_mexc_client returns singleton"""
        # Reset global client
        import api.mexc
        api.mexc._mexc_client = None

        client1 = get_mexc_client()
        client2 = get_mexc_client()

        assert client1 is client2
        assert client1 is not None

    def test_get_mexc_client_creates_new_if_none(self):
        """Test get_mexc_client creates new instance if None"""
        import api.mexc
        api.mexc._mexc_client = None

        client = get_mexc_client()

        assert client is not None
        assert isinstance(client, MEXCClient)
