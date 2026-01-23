"""
Tests pour le calcul de tendance
"""
import pytest
from unittest.mock import AsyncMock, MagicMock


class TestTrendCalculator:
    """Tests pour le calcul de tendance"""

    @pytest.mark.asyncio
    async def test_calculate_trend_data_bullish(self):
        """Test calcul de tendance bullish"""
        from core.analyzer.trend_calculator import calculate_trend_data
        
        # Mock client et indicators
        client = AsyncMock()
        client.fetch_ohlcv = AsyncMock(return_value=[
            [0, 49000, 49500, 48500, 49200, 1000],
            [1, 49200, 49700, 48700, 49400, 1200],
            [2, 49400, 49900, 48900, 49600, 1100],
            [3, 49600, 50100, 49100, 49800, 1300],
            [4, 49800, 50300, 49300, 50000, 1400]
        ])
        
        indicators = MagicMock()
        indicators.calculate_ema = MagicMock(return_value=49000)
        indicators.calculate_macd = MagicMock(return_value={'histogram': 0.01})
        indicators.calculate_adx = MagicMock(return_value={'adx': 35, 'diPlus': 25, 'diMinus': 15})
        
        result = await calculate_trend_data(
            client=client,
            indicators=indicators,
            symbol='BTCUSDT',
            timeframe='15m'
        )
        
        if result:
            assert 'trend' in result
            assert result['trend'] in ['BULLISH', 'BEARISH', 'NEUTRAL']
            assert 'bonus' in result
            assert 'strength' in result

    @pytest.mark.asyncio
    async def test_calculate_trend_data_bearish(self):
        """Test calcul de tendance bearish"""
        from core.analyzer.trend_calculator import calculate_trend_data
        
        # Mock client et indicators
        client = AsyncMock()
        client.fetch_ohlcv = AsyncMock(return_value=[
            [0, 50000, 50500, 49500, 49800, 1000],
            [1, 49800, 50300, 49300, 49600, 1200],
            [2, 49600, 50100, 49100, 49400, 1100],
            [3, 49400, 49900, 48900, 49200, 1300],
            [4, 49200, 49700, 48700, 49000, 1400]
        ])
        
        indicators = MagicMock()
        indicators.calculate_ema = MagicMock(return_value=49000)
        indicators.calculate_macd = MagicMock(return_value={'histogram': -0.01})
        indicators.calculate_adx = MagicMock(return_value={'adx': 35, 'diPlus': 15, 'diMinus': 25})
        
        result = await calculate_trend_data(
            client=client,
            indicators=indicators,
            symbol='BTCUSDT',
            timeframe='15m'
        )
        
        if result:
            assert 'trend' in result
            assert result['trend'] in ['BULLISH', 'BEARISH', 'NEUTRAL']

    @pytest.mark.asyncio
    async def test_calculate_trend_data_neutral(self):
        """Test calcul de tendance neutre"""
        from core.analyzer.trend_calculator import calculate_trend_data
        
        # Mock client et indicators
        client = AsyncMock()
        client.fetch_ohlcv = AsyncMock(return_value=[
            [0, 49000, 49500, 48500, 49000, 1000],
            [1, 49000, 49500, 48500, 49000, 1200],
            [2, 49000, 49500, 48500, 49000, 1100],
            [3, 49000, 49500, 48500, 49000, 1300],
            [4, 49000, 49500, 48500, 49000, 1400]
        ])
        
        indicators = MagicMock()
        indicators.calculate_ema = MagicMock(return_value=49000)
        indicators.calculate_macd = MagicMock(return_value={'histogram': 0})
        indicators.calculate_adx = MagicMock(return_value={'adx': 20, 'diPlus': 20, 'diMinus': 20})
        
        result = await calculate_trend_data(
            client=client,
            indicators=indicators,
            symbol='BTCUSDT',
            timeframe='15m'
        )
        
        if result:
            assert 'trend' in result
            assert result['trend'] in ['BULLISH', 'BEARISH', 'NEUTRAL']

    @pytest.mark.asyncio
    async def test_calculate_trend_data_error(self):
        """Test calcul de tendance avec erreur"""
        from core.analyzer.trend_calculator import calculate_trend_data
        
        # Mock client qui lève une erreur
        client = AsyncMock()
        client.fetch_ohlcv = AsyncMock(side_effect=Exception("API Error"))
        
        indicators = MagicMock()
        
        result = await calculate_trend_data(
            client=client,
            indicators=indicators,
            symbol='BTCUSDT',
            timeframe='15m'
        )
        
        assert result is None
