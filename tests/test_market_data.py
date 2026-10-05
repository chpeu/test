"""
Tests pour les données de marché
"""
import pytest
from unittest.mock import AsyncMock, MagicMock


class TestMarketData:
    """Tests pour les données de marché"""

    @pytest.mark.asyncio
    async def test_check_spread_valid(self):
        """Test vérification spread - spread valide"""
        from core.analyzer.market_data import check_spread
        
        # Mock client
        client = AsyncMock()
        client.fetch_order_book = AsyncMock(return_value={
            'bids': [[49990, 1.0], [49985, 2.0]],
            'asks': [[50010, 1.0], [50015, 2.0]]
        })
        
        spread_cache = {}
        
        result = await check_spread(
            client=client,
            symbol='BTCUSDT',
            spread_cache=spread_cache
        )
        
        assert 'valid' in result
        assert 'spread_pct' in result

    @pytest.mark.asyncio
    async def test_check_spread_invalid(self):
        """Test vérification spread - spread invalide"""
        from core.analyzer.market_data import check_spread
        
        # Mock client avec spread élevé
        client = AsyncMock()
        client.fetch_order_book = AsyncMock(return_value={
            'bids': [[49000, 1.0]],
            'asks': [[51000, 1.0]]
        })
        
        spread_cache = {}
        
        result = await check_spread(
            client=client,
            symbol='BTCUSDT',
            spread_cache=spread_cache
        )
        
        assert 'valid' in result
        assert 'spread_pct' in result

    @pytest.mark.asyncio
    async def test_check_orderbook_imbalance_long(self):
        """Test vérification orderbook - LONG"""
        from core.analyzer.market_data import check_orderbook_imbalance
        
        # Mock client
        client = AsyncMock()
        client.fetch_order_book = AsyncMock(return_value={
            'bids': [[49990, 10.0], [49985, 8.0], [49980, 6.0]],
            'asks': [[50010, 1.0], [50015, 1.0], [50020, 1.0]]
        })
        
        orderbook_cache = {}
        
        result = await check_orderbook_imbalance(
            client=client,
            symbol='BTCUSDT',
            direction='LONG',
            orderbook_cache=orderbook_cache
        )
        
        assert 'valid' in result
        assert 'ratio' in result

    @pytest.mark.asyncio
    async def test_check_orderbook_imbalance_short(self):
        """Test vérification orderbook - SHORT"""
        from core.analyzer.market_data import check_orderbook_imbalance
        
        # Mock client
        client = AsyncMock()
        client.fetch_order_book = AsyncMock(return_value={
            'bids': [[49990, 1.0], [49985, 1.0], [49980, 1.0]],
            'asks': [[50010, 10.0], [50015, 8.0], [50020, 6.0]]
        })
        
        orderbook_cache = {}
        
        result = await check_orderbook_imbalance(
            client=client,
            symbol='BTCUSDT',
            direction='SHORT',
            orderbook_cache=orderbook_cache
        )
        
        assert 'valid' in result
        assert 'ratio' in result

    @pytest.mark.asyncio
    async def test_check_orderbook_imbalance_none(self):
        """Test vérification orderbook - orderbook None"""
        from core.analyzer.market_data import check_orderbook_imbalance
        
        # Mock client qui retourne None
        client = AsyncMock()
        client.fetch_order_book = AsyncMock(return_value=None)
        
        orderbook_cache = {}
        
        result = await check_orderbook_imbalance(
            client=client,
            symbol='BTCUSDT',
            direction='LONG',
            orderbook_cache=orderbook_cache
        )
        
        assert 'valid' in result
        assert result['valid'] is True

    @pytest.mark.asyncio
    async def test_check_spread_cached(self):
        """Test vérification spread - cache"""
        from core.analyzer.market_data import check_spread
        import time
        
        # Mock client
        client = AsyncMock()
        client.fetch_order_book = AsyncMock(return_value={
            'bids': [[49990, 1.0]],
            'asks': [[50010, 1.0]]
        })
        
        # Pré-remplir le cache
        spread_cache = {
            'BTCUSDT': {
                'timestamp': time.time(),
                'data': {'valid': True, 'spread_pct': 0.04, 'max_allowed': 0.03, 'quality': 'GOOD'}
            }
        }
        
        result = await check_spread(
            client=client,
            symbol='BTCUSDT',
            spread_cache=spread_cache
        )
        
        assert 'valid' in result
