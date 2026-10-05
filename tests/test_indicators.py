"""
Tests pour les indicateurs techniques
"""
import pytest
from core.indicators import Indicators


class TestIndicators:
    """Tests pour les indicateurs techniques"""

    def test_indicators_creation(self):
        """Test création des indicateurs"""
        indicators = Indicators()
        assert indicators is not None

    def test_calculate_ema(self):
        """Test calcul EMA"""
        values = [49000, 49100, 49200, 49300, 49400]
        ema = Indicators.calculate_ema(values, period=5)
        assert ema is not None
        assert isinstance(ema, float)

    def test_calculate_ema_single_value(self):
        """Test calcul EMA avec une seule valeur"""
        values = [49000]
        ema = Indicators.calculate_ema(values, period=5)
        assert ema is not None

    def test_calculate_macd(self):
        """Test calcul MACD"""
        closes = [49000, 49100, 49200, 49300, 49400, 49500, 49600, 49700, 49800, 49900]
        macd = Indicators.calculate_macd(closes)
        assert macd is not None
        assert 'histogram' in macd
        assert 'macd' in macd
        assert 'signal' in macd

    def test_calculate_rsi(self):
        """Test calcul RSI"""
        closes = [49000, 49100, 49200, 49300, 49400, 49500, 49600, 49700, 49800, 49900, 50000]
        rsi = Indicators.calculate_rsi(closes, period=14)
        assert rsi is not None
        assert 0 <= rsi <= 100

    def test_calculate_rsi_short_period(self):
        """Test calcul RSI avec période courte"""
        closes = [49000, 49100, 49200, 49300, 49400, 49500, 49600, 49700, 49800, 49900, 50000]
        rsi = Indicators.calculate_rsi(closes, period=7)
        assert rsi is not None
        assert 0 <= rsi <= 100

    def test_calculate_adx(self):
        """Test calcul ADX"""
        highs = [49500, 49700, 49900, 50100, 50300]
        lows = [48500, 48700, 48900, 49100, 49300]
        closes = [49000, 49200, 49400, 49600, 49800]
        adx = Indicators.calculate_adx(highs, lows, closes, period=14)
        assert adx is not None
        assert 'adx' in adx
        assert 'diPlus' in adx
        assert 'diMinus' in adx

    def test_calculate_atr(self):
        """Test calcul ATR"""
        highs = [49500, 49700, 49900, 50100, 50300]
        lows = [48500, 48700, 48900, 49100, 49300]
        closes = [49000, 49200, 49400, 49600, 49800]
        atr = Indicators.calculate_atr(highs, lows, closes, period=5)
        assert atr is not None
        assert atr >= 0  # Peut être 0 si pas assez de données

    def test_calculate_bollinger_bands(self):
        """Test calcul bandes de Bollinger"""
        closes = [49000, 49100, 49200, 49300, 49400, 49500, 49600, 49700, 49800, 49900, 50000, 50100, 50200, 50300, 50400, 50500, 50600, 50700, 50800, 50900]
        bb = Indicators.calculate_bollinger_bands(closes, period=20)
        assert bb is not None
        assert 'upper' in bb
        assert 'middle' in bb
        assert 'lower' in bb
        # Vérifier que les bandes sont dans le bon ordre
        if bb['upper'] is not None and bb['lower'] is not None:
            assert bb['upper'] >= bb['middle']
            assert bb['middle'] >= bb['lower']
