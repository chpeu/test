#!/usr/bin/env python3
"""
Comprehensive Tests for Indicators Module - Trade Cursor v7.0
Target: 85%+ coverage for indicators.py
Tests: EMA, RSI, MACD, ATR, Bollinger Bands, ADX, Pattern Detection
"""

import pytest
import sys
import os
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.indicators import Indicators


# ============================================================================
# EMA TESTS
# ============================================================================

class TestEMA:
    """Tests pour EMA (Exponential Moving Average)"""

    def test_calculate_ema_basic(self):
        """Test calcul EMA basique"""
        values = [100, 102, 101, 103, 105, 104, 106]
        period = 5

        ema = Indicators.calculate_ema(values, period)

        assert ema > 0
        assert 100 < ema < 110

    def test_calculate_ema_insufficient_data(self):
        """Test EMA avec données insuffisantes"""
        values = [100, 102]
        period = 5

        ema = Indicators.calculate_ema(values, period)

        assert ema == 0.0

    def test_calculate_ema_trending_up(self):
        """Test EMA avec tendance haussière"""
        values = [100, 101, 102, 103, 104, 105, 106, 107]
        period = 5

        ema = Indicators.calculate_ema(values, period)

        # EMA devrait être proche de la fin (107)
        assert ema > values[0]
        assert ema < values[-1] + 5

    def test_calculate_ema_trending_down(self):
        """Test EMA avec tendance baissière"""
        values = [110, 109, 108, 107, 106, 105, 104, 103]
        period = 5

        ema = Indicators.calculate_ema(values, period)

        assert ema < values[0]
        assert ema > values[-1] - 5


# ============================================================================
# RSI TESTS
# ============================================================================

class TestRSI:
    """Tests pour RSI (Relative Strength Index)"""

    def test_calculate_rsi_neutral(self):
        """Test RSI neutre (oscillant)"""
        closes = [100, 101, 100, 101, 100, 101, 100, 101, 100, 101, 100, 101, 100, 101, 100]

        rsi = Indicators.calculate_rsi(closes, period=14)

        # RSI neutre devrait être proche de 50
        assert 40 <= rsi <= 60

    def test_calculate_rsi_overbought(self):
        """Test RSI suracheté (> 70)"""
        closes = [100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160, 165, 170]

        rsi = Indicators.calculate_rsi(closes, period=14)

        # RSI en hausse constante devrait être > 70
        assert rsi > 70

    def test_calculate_rsi_oversold(self):
        """Test RSI survendu (< 30)"""
        closes = [170, 165, 160, 155, 150, 145, 140, 135, 130, 125, 120, 115, 110, 105, 100]

        rsi = Indicators.calculate_rsi(closes, period=14)

        # RSI en baisse constante devrait être < 30
        assert rsi < 30

    def test_calculate_rsi_insufficient_data(self):
        """Test RSI avec données insuffisantes"""
        closes = [100, 102, 101]

        rsi = Indicators.calculate_rsi(closes, period=14)

        # Retourne 50 par défaut
        assert rsi == 50.0

    def test_calculate_rsi_previous(self):
        """Test RSI de la bougie précédente"""
        # Progression mixte pour éviter RSI=100 constant
        closes = [100, 102, 101, 105, 103, 108, 106, 110, 108, 112, 110, 115, 113, 118, 116, 120]

        rsi_current = Indicators.calculate_rsi(closes, period=14)
        rsi_previous = Indicators.calculate_rsi_previous(closes, period=14)

        # RSI précédent devrait être différent
        assert rsi_previous != rsi_current

    def test_calculate_rsi_only_gains(self):
        """Test RSI avec seulement des gains"""
        closes = [100] + [100 + i for i in range(1, 20)]

        rsi = Indicators.calculate_rsi(closes, period=14)

        # RSI devrait être proche de 100
        assert rsi == 100.0


# ============================================================================
# MACD TESTS
# ============================================================================

class TestMACD:
    """Tests pour MACD (Moving Average Convergence Divergence)"""

    def test_calculate_macd_basic(self):
        """Test calcul MACD basique"""
        closes = [100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 111, 110, 112, 114, 113]

        macd_data = Indicators.calculate_macd(closes, fast_period=3, slow_period=10, signal_period=16)

        assert 'macd' in macd_data
        assert 'signal' in macd_data
        assert 'histogram' in macd_data

    def test_calculate_macd_bullish_crossover(self):
        """Test MACD crossover haussier (histogram > 0)"""
        # Tendance haussière forte
        closes = [100 + i * 2 for i in range(30)]

        macd_data = Indicators.calculate_macd(closes, fast_period=3, slow_period=10, signal_period=16)

        # Histogram devrait être positif (MACD > Signal)
        assert macd_data['histogram'] > 0

    def test_calculate_macd_bearish_crossover(self):
        """Test MACD crossover baissier (histogram < 0)"""
        # Tendance baissière forte
        closes = [200 - i * 2 for i in range(30)]

        macd_data = Indicators.calculate_macd(closes, fast_period=3, slow_period=10, signal_period=16)

        # Histogram devrait être négatif (MACD < Signal)
        assert macd_data['histogram'] < 0

    def test_calculate_macd_insufficient_data(self):
        """Test MACD avec données insuffisantes"""
        closes = [100, 102, 101]

        macd_data = Indicators.calculate_macd(closes, fast_period=3, slow_period=10, signal_period=16)

        assert macd_data['macd'] == 0.0
        assert macd_data['signal'] == 0.0
        assert macd_data['histogram'] == 0.0

    def test_calculate_macd_previous(self):
        """Test MACD de la bougie précédente"""
        closes = [100 + i for i in range(30)]

        macd_current = Indicators.calculate_macd(closes, fast_period=3, slow_period=10, signal_period=16)
        macd_previous = Indicators.calculate_macd_previous(closes, fast_period=3, slow_period=10, signal_period=16)

        # MACD précédent devrait être différent
        assert macd_previous['macd'] != macd_current['macd']


# ============================================================================
# ATR TESTS
# ============================================================================

class TestATR:
    """Tests pour ATR (Average True Range)"""

    def test_calculate_atr_basic(self):
        """Test calcul ATR basique"""
        highs = [105, 107, 106, 108, 110, 109, 111, 113, 112, 114, 116, 115, 117, 119, 118]
        lows = [95, 97, 96, 98, 100, 99, 101, 103, 102, 104, 106, 105, 107, 109, 108]
        closes = [100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 111, 110, 112, 114, 113]

        atr = Indicators.calculate_atr(highs, lows, closes, period=14)

        assert atr > 0
        assert atr < 20  # Raisonnable pour ces données

    def test_calculate_atr_high_volatility(self):
        """Test ATR avec forte volatilité"""
        highs = [110, 120, 115, 125, 118, 128]
        lows = [90, 100, 95, 105, 98, 108]
        closes = [100, 110, 105, 115, 108, 118]

        atr = Indicators.calculate_atr(highs, lows, closes, period=5)

        # ATR devrait être élevé
        assert atr > 10

    def test_calculate_atr_low_volatility(self):
        """Test ATR avec faible volatilité"""
        highs = [101, 102, 101.5, 102.5, 101.8, 102.3]
        lows = [99, 100, 99.5, 100.5, 99.8, 100.3]
        closes = [100, 101, 100.5, 101.5, 100.8, 101.3]

        atr = Indicators.calculate_atr(highs, lows, closes, period=5)

        # ATR devrait être faible
        assert atr < 3

    def test_calculate_atr_insufficient_data(self):
        """Test ATR avec données insuffisantes"""
        highs = [105, 107]
        lows = [95, 97]
        closes = [100, 102]

        atr = Indicators.calculate_atr(highs, lows, closes, period=14)

        assert atr == 0.0


# ============================================================================
# BOLLINGER BANDS TESTS
# ============================================================================

class TestBollingerBands:
    """Tests pour Bollinger Bands"""

    def test_calculate_bollinger_bands_basic(self):
        """Test calcul Bollinger Bands basique"""
        closes = [100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 111, 110, 112, 114, 113,
                  115, 117, 116, 118, 120, 119]

        bb = Indicators.calculate_bollinger_bands(closes, period=20, std_dev=2.0)

        assert bb['upper'] > bb['middle']
        assert bb['middle'] > bb['lower']
        assert bb['width'] > 0

    def test_calculate_bollinger_bands_narrow(self):
        """Test Bollinger Bands étroites (faible volatilité)"""
        # Prix stable
        closes = [100 + i * 0.1 for i in range(25)]

        bb = Indicators.calculate_bollinger_bands(closes, period=20, std_dev=2.0)

        # Width devrait être faible
        assert bb['width'] < 0.1

    def test_calculate_bollinger_bands_wide(self):
        """Test Bollinger Bands larges (forte volatilité)"""
        # Prix oscillant
        closes = [100, 110, 95, 115, 90, 120, 85, 125, 80, 130, 75, 135, 70, 140, 65,
                  145, 60, 150, 55, 155, 50]

        bb = Indicators.calculate_bollinger_bands(closes, period=20, std_dev=2.0)

        # Width devrait être élevé
        assert bb['width'] > 0.5

    def test_calculate_bollinger_bands_insufficient_data(self):
        """Test Bollinger Bands avec données insuffisantes"""
        closes = [100, 102, 101]

        bb = Indicators.calculate_bollinger_bands(closes, period=20, std_dev=2.0)

        assert bb['upper'] == 0.0
        assert bb['middle'] == 0.0
        assert bb['lower'] == 0.0


# ============================================================================
# ADX TESTS
# ============================================================================

class TestADX:
    """Tests pour ADX (Average Directional Index)"""

    def test_calculate_adx_basic(self):
        """Test calcul ADX basique"""
        highs = [105, 107, 106, 108, 110, 109, 111, 113, 112, 114, 116, 115, 117, 119, 118]
        lows = [95, 97, 96, 98, 100, 99, 101, 103, 102, 104, 106, 105, 107, 109, 108]
        closes = [100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 111, 110, 112, 114, 113]

        adx_data = Indicators.calculate_adx(highs, lows, closes, period=14)

        assert 'adx' in adx_data
        assert 'diPlus' in adx_data
        assert 'diMinus' in adx_data
        assert adx_data['adx'] >= 0

    def test_calculate_adx_strong_uptrend(self):
        """Test ADX avec forte tendance haussière"""
        highs = [105 + i * 2 for i in range(20)]
        lows = [95 + i * 2 for i in range(20)]
        closes = [100 + i * 2 for i in range(20)]

        adx_data = Indicators.calculate_adx(highs, lows, closes, period=14)

        # DI+ devrait être supérieur à DI-
        assert adx_data['diPlus'] > adx_data['diMinus']

    def test_calculate_adx_strong_downtrend(self):
        """Test ADX avec forte tendance baissière"""
        highs = [125 - i * 2 for i in range(20)]
        lows = [115 - i * 2 for i in range(20)]
        closes = [120 - i * 2 for i in range(20)]

        adx_data = Indicators.calculate_adx(highs, lows, closes, period=14)

        # DI- devrait être supérieur à DI+
        assert adx_data['diMinus'] > adx_data['diPlus']

    def test_calculate_adx_insufficient_data(self):
        """Test ADX avec données insuffisantes"""
        highs = [105, 107]
        lows = [95, 97]
        closes = [100, 102]

        adx_data = Indicators.calculate_adx(highs, lows, closes, period=14)

        assert adx_data['adx'] == 0.0
        assert adx_data['diPlus'] == 0.0
        assert adx_data['diMinus'] == 0.0


# ============================================================================
# PATTERN DETECTION TESTS
# ============================================================================

class TestPatternDetection:
    """Tests pour la détection de patterns chandeliers"""

    def test_detect_pattern_engulfing_bullish(self):
        """Test détection Engulfing Bullish"""
        # Format OHLCV
        candle = [1609459200000, 50000.0, 50800.0, 49900.0, 50750.0, 1000.0]

        pattern = Indicators.detect_pattern(candle)

        assert pattern == 'ENGULFING_BULLISH'

    def test_detect_pattern_engulfing_bearish(self):
        """Test détection Engulfing Bearish"""
        candle = [1609459200000, 50750.0, 50800.0, 50000.0, 50050.0, 1000.0]

        pattern = Indicators.detect_pattern(candle)

        assert pattern == 'ENGULFING_BEARISH'

    def test_detect_pattern_hammer(self):
        """Test détection Hammer"""
        # Hammer: Petit corps, longue mèche basse, petite mèche haute
        # open: 50000, close: 50200 (body=200), low: 49400 (lower_shadow=600), high: 50220 (upper_shadow=20)
        candle = [1609459200000, 50000.0, 50220.0, 49400.0, 50200.0, 1000.0]

        pattern = Indicators.detect_pattern(candle)

        assert pattern == 'HAMMER'

    def test_detect_pattern_shooting_star(self):
        """Test détection Shooting Star"""
        # Shooting Star: Petit corps, longue mèche haute (> body * 2), petite mèche basse (< body * 0.3)
        # open: 50600, close: 50400 (body=200), high: 51100 (upper_shadow=500 > 400), low: 50380 (lower_shadow=20 < 60)
        candle = [1609459200000, 50600.0, 51100.0, 50380.0, 50400.0, 1000.0]

        pattern = Indicators.detect_pattern(candle)

        assert pattern == 'SHOOTING_STAR'

    def test_detect_pattern_none(self):
        """Test pas de pattern détecté"""
        candle = [1609459200000, 50400.0, 50500.0, 50300.0, 50450.0, 1000.0]

        pattern = Indicators.detect_pattern(candle)

        assert pattern == 'NONE'

    def test_detect_pattern_dict_format(self):
        """Test détection pattern avec format dict"""
        candle = {'open': 50000.0, 'high': 50800.0, 'low': 49900.0, 'close': 50750.0}

        pattern = Indicators.detect_pattern(candle)

        assert pattern == 'ENGULFING_BULLISH'

    def test_detect_pattern_invalid_data(self):
        """Test détection pattern avec données invalides"""
        candle = [1609459200000]  # Pas assez de valeurs

        pattern = Indicators.detect_pattern(candle)

        assert pattern == 'NONE'

    def test_detect_pattern_multi_doji(self):
        """Test détection Doji"""
        # Corps très petit (< 10% de la range)
        # open: 50410, close: 50411 (body=1), high: 50420, low: 50400 (range=20)
        # body/range = 1/20 = 5% < 10% ✓
        candles = [
            [1609459200000, 50400.0, 50500.0, 50300.0, 50410.0, 1000.0],
            [1609459260000, 50410.0, 50420.0, 50400.0, 50411.0, 1000.0]
        ]

        pattern = Indicators.detect_pattern_multi(candles)

        assert pattern == 'DOJI'

    def test_detect_pattern_multi_doji_dragonfly(self):
        """Test détection Dragonfly Doji"""
        # Dragonfly Doji: Petit corps, longue mèche basse (> 60% range), petite mèche haute (< 20% range)
        # Current candle: open: 50415, close: 50418 (body=3), high: 50420, low: 50000 (range=420)
        # lower_shadow=415 (99%), upper_shadow=2 (0.5%)
        candles = [
            [1609459200000, 50400.0, 50500.0, 50300.0, 50410.0, 1000.0],
            [1609459260000, 50415.0, 50420.0, 50000.0, 50418.0, 1000.0]
        ]

        pattern = Indicators.detect_pattern_multi(candles)

        assert pattern == 'DOJI_DRAGONFLY'

    def test_detect_pattern_multi_marubozu_bullish(self):
        """Test détection Marubozu Bullish"""
        candles = [
            [1609459200000, 50000.0, 50800.0, 50000.0, 50800.0, 1000.0],
            [1609459260000, 50800.0, 50900.0, 50800.0, 50900.0, 1000.0]
        ]

        pattern = Indicators.detect_pattern_multi(candles)

        assert pattern == 'MARUBOZU_BULLISH'

    def test_detect_pattern_multi_morning_star(self):
        """Test détection Morning Star"""
        candles = [
            [1609459140000, 50800.0, 50900.0, 50400.0, 50450.0, 1000.0],  # Rouge
            [1609459200000, 50450.0, 50480.0, 50420.0, 50460.0, 1000.0],  # Petite
            [1609459260000, 50460.0, 50900.0, 50450.0, 50850.0, 1000.0]   # Verte forte
        ]

        pattern = Indicators.detect_pattern_multi(candles)

        assert pattern == 'MORNING_STAR'

    def test_detect_pattern_multi_insufficient_candles(self):
        """Test détection multi-pattern avec données insuffisantes"""
        candles = [[1609459200000, 50400.0, 50500.0, 50300.0, 50450.0, 1000.0]]

        pattern = Indicators.detect_pattern_multi(candles)

        assert pattern == 'NONE'


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
