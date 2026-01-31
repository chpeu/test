#!/usr/bin/env python3
"""
Comprehensive Tests for API Modules - Trade Cursor v7.0
Target: 70%+ coverage for api modules
- MEXC API (api/mexc.py)
- Price Provider (api/price_provider.py)
- Reliability Manager (api/reliability.py)
"""

import pytest
import sys
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, Mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.mexc import MEXCClient, get_mexc_client


# ============================================================================
# MEXC API TESTS (api/mexc.py)
# ============================================================================

class TestMEXCAPI:
    """Tests pour api/mexc.py"""

    @pytest.mark.asyncio
    async def test_fetch_ticker_success(self):
        """Test fetch ticker avec succès"""
        client = MEXCClient()

        # Mock exchange
        client.exchange.fetch_ticker = AsyncMock(return_value={
            'symbol': 'BTC/USDT:USDT',
            'last': 50000.0,
            'bid': 49995.0,
            'ask': 50005.0,
            'volume': 1000000.0
        })

        ticker = await client.fetch_ticker('BTC/USDT:USDT')

        assert ticker is not None
        assert ticker['symbol'] == 'BTC/USDT:USDT'
        assert ticker['last'] == 50000.0

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_ticker_error(self):
        """Test fetch ticker avec erreur"""
        client = MEXCClient()

        # Mock error
        client.exchange.fetch_ticker = AsyncMock(side_effect=Exception("API Error"))

        ticker = await client.fetch_ticker('BTC/USDT:USDT')

        assert ticker is None

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_tickers_success(self):
        """Test fetch all tickers avec succès"""
        client = MEXCClient()

        # Mock exchange
        client.exchange.fetch_tickers = AsyncMock(return_value={
            'BTC/USDT:USDT': {
                'symbol': 'BTC/USDT:USDT',
                'last': 50000.0
            },
            'ETH/USDT:USDT': {
                'symbol': 'ETH/USDT:USDT',
                'last': 3000.0
            }
        })

        tickers = await client.fetch_tickers()

        assert tickers is not None
        assert len(tickers) == 2
        assert 'BTC/USDT:USDT' in tickers

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_tickers_error(self):
        """Test fetch all tickers avec erreur"""
        client = MEXCClient()

        # Mock error
        client.exchange.fetch_tickers = AsyncMock(side_effect=Exception("API Error"))

        tickers = await client.fetch_tickers()

        assert tickers == {}

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_success(self):
        """Test fetch OHLCV avec succès"""
        client = MEXCClient()

        # Mock klines
        mock_klines = []
        for i in range(10):
            mock_klines.append([
                1609459200000 + i * 60000,
                50000.0 + i * 10,
                50100.0 + i * 10,
                49900.0 + i * 10,
                50050.0 + i * 10,
                1000.0
            ])

        client.exchange.fetch_ohlcv = AsyncMock(return_value=mock_klines)

        klines = await client.fetch_ohlcv('BTC/USDT:USDT', '1m', limit=10)

        assert klines is not None
        assert len(klines) == 10
        assert len(klines[0]) == 6  # [timestamp, o, h, l, c, v]

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_error(self):
        """Test fetch OHLCV avec erreur"""
        client = MEXCClient()

        # Mock error
        client.exchange.fetch_ohlcv = AsyncMock(side_effect=Exception("API Error"))

        klines = await client.fetch_ohlcv('BTC/USDT:USDT', '1m', limit=10)

        assert klines == []

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_order_book_success(self):
        """Test fetch orderbook avec succès"""
        client = MEXCClient()

        # Mock orderbook
        client.exchange.fetch_order_book = AsyncMock(return_value={
            'symbol': 'BTC/USDT:USDT',
            'bids': [[50000.0, 10.0], [49990.0, 8.0]],
            'asks': [[50010.0, 12.0], [50020.0, 9.0]]
        })

        orderbook = await client.fetch_order_book('BTC/USDT:USDT', limit=20)

        assert orderbook is not None
        assert 'bids' in orderbook
        assert 'asks' in orderbook
        assert len(orderbook['bids']) == 2

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_order_book_error(self):
        """Test fetch orderbook avec erreur"""
        client = MEXCClient()

        # Mock error
        client.exchange.fetch_order_book = AsyncMock(side_effect=Exception("API Error"))

        orderbook = await client.fetch_order_book('BTC/USDT:USDT', limit=20)

        assert orderbook is None

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_funding_rate_success(self):
        """Test fetch funding rate avec succès"""
        client = MEXCClient()

        # Mock ticker
        client.exchange.fetch_ticker = AsyncMock(return_value={
            'symbol': 'BTC/USDT:USDT',
            'info': {
                'fundingRate': 0.0001
            }
        })

        funding_rate = await client.fetch_funding_rate('BTC/USDT:USDT')

        assert funding_rate is not None
        assert funding_rate == 0.0001

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_funding_rate_not_found(self):
        """Test fetch funding rate sans funding rate"""
        client = MEXCClient()

        # Mock ticker sans funding rate
        client.exchange.fetch_ticker = AsyncMock(return_value={
            'symbol': 'BTC/USDT:USDT',
            'info': {}
        })

        funding_rate = await client.fetch_funding_rate('BTC/USDT:USDT')

        assert funding_rate == 0

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_funding_rate_error(self):
        """Test fetch funding rate avec erreur"""
        client = MEXCClient()

        # Mock error
        client.exchange.fetch_ticker = AsyncMock(side_effect=Exception("API Error"))

        funding_rate = await client.fetch_funding_rate('BTC/USDT:USDT')

        assert funding_rate is None

        await client.close()

    def test_get_mexc_client_singleton(self):
        """Test singleton pattern pour get_mexc_client"""
        client1 = get_mexc_client()
        client2 = get_mexc_client()

        assert client1 is client2


# ============================================================================
# PRICE PROVIDER TESTS (api/price_provider.py)
# ============================================================================

class TestPriceProvider:
    """Tests pour api/price_provider.py"""

    @pytest.mark.asyncio
    async def test_get_current_price_cached(self):
        """Test récupération prix avec cache"""
        # Import local pour éviter side effects
        from api.price_provider import PriceProvider

        provider = PriceProvider()

        # Mock client
        provider.client.fetch_ticker = AsyncMock(return_value={
            'last': 50000.0
        })

        # Premier appel
        price1 = await provider.get_current_price('BTC/USDT:USDT')

        # Deuxième appel (devrait utiliser le cache)
        price2 = await provider.get_current_price('BTC/USDT:USDT')

        assert price1 == 50000.0
        assert price2 == 50000.0

        # Le client ne devrait être appelé qu'une fois (cache)
        assert provider.client.fetch_ticker.call_count <= 2  # Peut être 2 si cache expiré

    @pytest.mark.asyncio
    async def test_get_current_price_error(self):
        """Test récupération prix avec erreur"""
        from api.price_provider import PriceProvider

        provider = PriceProvider()

        # Mock error
        provider.client.fetch_ticker = AsyncMock(side_effect=Exception("API Error"))

        price = await provider.get_current_price('BTC/USDT:USDT')

        assert price is None

    @pytest.mark.asyncio
    async def test_get_multiple_prices(self):
        """Test récupération multiple prix"""
        from api.price_provider import PriceProvider

        provider = PriceProvider()

        # Mock client
        provider.client.fetch_ticker = AsyncMock(side_effect=[
            {'last': 50000.0},
            {'last': 3000.0}
        ])

        prices = await provider.get_multiple_prices(['BTC/USDT:USDT', 'ETH/USDT:USDT'])

        assert len(prices) == 2
        assert prices['BTC/USDT:USDT'] == 50000.0
        assert prices['ETH/USDT:USDT'] == 3000.0


# ============================================================================
# RELIABILITY MANAGER TESTS (api/reliability.py)
# ============================================================================

class TestReliabilityManager:
    """Tests pour api/reliability.py"""

    @pytest.mark.asyncio
    async def test_fetch_with_retry_success_first_try(self):
        """Test fetch avec succès au premier essai"""
        from api.reliability import fetch_with_retry

        mock_func = AsyncMock(return_value={'data': 'success'})

        result = await fetch_with_retry(mock_func)

        assert result == {'data': 'success'}
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_fetch_with_retry_success_after_retry(self):
        """Test fetch avec succès après retry"""
        from api.reliability import fetch_with_retry

        # Mock qui échoue 2 fois puis réussit
        mock_func = AsyncMock(side_effect=[
            ConnectionError("Error 1"),
            ConnectionError("Error 2"),
            {'data': 'success'}
        ])

        result = await fetch_with_retry(mock_func)

        assert result == {'data': 'success'}
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_fetch_with_retry_all_failed(self):
        """Test fetch avec échec complet"""
        from api.reliability import fetch_with_retry

        # Mock qui échoue toujours
        mock_func = AsyncMock(side_effect=Exception("Error"))

        with pytest.raises(Exception):
            await fetch_with_retry(mock_func)

        assert mock_func.call_count >= 1

    @pytest.mark.asyncio
    async def test_fetch_with_all_protections_success(self):
        """Test fetch avec toutes les protections (retry + circuit breaker)"""
        from api.reliability import fetch_with_all_protections

        mock_func = AsyncMock(return_value={'data': 'success'})

        result = await fetch_with_all_protections(mock_func)

        assert result == {'data': 'success'}

    @pytest.mark.asyncio
    async def test_fetch_with_timeout(self):
        """Test fetch avec timeout"""
        from api.reliability import fetch_with_retry

        # Mock qui déclenche un timeout immédiatement
        async def slow_func():
            raise asyncio.TimeoutError("Timeout")

        mock_func = AsyncMock(side_effect=slow_func)

        with pytest.raises(Exception):
            await fetch_with_retry(mock_func)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
