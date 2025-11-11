"""
Tests pour core/analyzer/filters.py
"""
import pytest
from unittest.mock import patch
from core.analyzer.filters import (
    check_volume_filter,
    check_snr_filter,
    check_breakout_filter,
    check_wick_filter,
    check_atr_filter
)


class TestCheckVolumeFilter:
    """Tests pour check_volume_filter"""

    def test_volume_sufficient(self):
        """Test volume suffisant"""
        result = check_volume_filter(
            vol_spike=1.5,
            min_vol_ratio=1.0,
            symbol='BTC/USDT:USDT',
            timeframe='1m',
            atr_percent=0.5,
            volume_multiplier=1.0,
            return_reason=False
        )
        assert result is None

    def test_volume_insufficient_return_reason(self):
        """Test volume insuffisant avec return_reason=True"""
        result = check_volume_filter(
            vol_spike=0.5,
            min_vol_ratio=1.0,
            symbol='BTC/USDT:USDT',
            timeframe='1m',
            atr_percent=0.5,
            volume_multiplier=1.0,
            return_reason=True
        )
        assert result is not None
        assert 'reason' in result
        assert 'Volume insuffisant' in result['reason']
        assert result['symbol'] == 'BTC/USDT:USDT'

    def test_volume_insufficient_no_return_reason(self):
        """Test volume insuffisant avec return_reason=False"""
        result = check_volume_filter(
            vol_spike=0.5,
            min_vol_ratio=1.0,
            symbol='BTC/USDT:USDT',
            timeframe='1m',
            atr_percent=0.5,
            volume_multiplier=1.0,
            return_reason=False
        )
        assert result is not None
        assert result['rejected'] is True

    def test_volume_adaptive_high_atr(self):
        """Test calcul adaptatif avec ATR élevé"""
        # ATR > 1.0 → base_min_vol = 1.0
        result = check_volume_filter(
            vol_spike=1.2,
            min_vol_ratio=1.0,
            symbol='BTC/USDT:USDT',
            timeframe='1m',
            atr_percent=1.5,  # > 1.0
            volume_multiplier=1.0,
            return_reason=False
        )
        # Vol spike 1.2 devrait être suffisant car base = 1.0
        assert result is None

    def test_volume_adaptive_low_atr(self):
        """Test calcul adaptatif avec ATR faible"""
        # ATR < 0.3 → base_min_vol = 0.6
        result = check_volume_filter(
            vol_spike=0.7,
            min_vol_ratio=0.6,
            symbol='BTC/USDT:USDT',
            timeframe='1m',
            atr_percent=0.2,  # < 0.3
            volume_multiplier=1.0,
            return_reason=False
        )
        # Vol spike 0.7 devrait être suffisant car base = 0.6
        assert result is None

    def test_volume_multiplier_effect(self):
        """Test effet du volume_multiplier"""
        # Avec multiplier = 2.0, min_vol_ratio sera plus élevé
        result = check_volume_filter(
            vol_spike=1.0,
            min_vol_ratio=1.0,
            symbol='BTC/USDT:USDT',
            timeframe='1m',
            atr_percent=0.5,
            volume_multiplier=2.0,  # Double les requis
            return_reason=False
        )
        # Vol spike 1.0 pourrait être insuffisant avec multiplier = 2.0
        # Dépend du calcul adaptatif


class TestCheckSNRFilter:
    """Tests pour check_snr_filter"""

    @patch('core.analyzer.filters.TRADING_CONFIG', {'use_snr': False})
    def test_snr_disabled(self):
        """Test SNR filtre désactivé"""
        result = check_snr_filter(
            price=50000,
            ema21=49900,
            atr=50,
            symbol='BTC/USDT:USDT',
            timeframe='1m',
            return_reason=False
        )
        assert result is None

    @patch('core.analyzer.filters.TRADING_CONFIG', {'use_snr': True, 'snr_threshold': 0.3})
    def test_snr_sufficient(self):
        """Test SNR suffisant"""
        result = check_snr_filter(
            price=50000,
            ema21=49500,  # Diff = 500
            atr=100,  # SNR = 500/100 = 5.0 > 0.3
            symbol='BTC/USDT:USDT',
            timeframe='1m',
            return_reason=False
        )
        assert result is None

    @patch('core.analyzer.filters.TRADING_CONFIG', {'use_snr': True, 'snr_threshold': 0.3})
    def test_snr_too_low_return_reason(self):
        """Test SNR trop faible avec return_reason=True"""
        result = check_snr_filter(
            price=50000,
            ema21=49980,  # Diff = 20
            atr=100,  # SNR = 20/100 = 0.2 < 0.3
            symbol='BTC/USDT:USDT',
            timeframe='1m',
            return_reason=True
        )
        assert result is not None
        assert 'SNR trop faible' in result['reason']

    @patch('core.analyzer.filters.TRADING_CONFIG', {'use_snr': True, 'snr_threshold': 0.3})
    def test_snr_too_low_no_return_reason(self):
        """Test SNR trop faible avec return_reason=False"""
        result = check_snr_filter(
            price=50000,
            ema21=49980,
            atr=100,
            symbol='BTC/USDT:USDT',
            timeframe='1m',
            return_reason=False
        )
        assert result is not None
        assert result['rejected'] is True

    @patch('core.analyzer.filters.TRADING_CONFIG', {'use_snr': True, 'snr_threshold': 0.3})
    def test_snr_zero_atr(self):
        """Test SNR avec ATR = 0"""
        result = check_snr_filter(
            price=50000,
            ema21=49900,
            atr=0,  # Division par 0
            symbol='BTC/USDT:USDT',
            timeframe='1m',
            return_reason=False
        )
        # SNR = 0 → rejeté
        assert result is not None


class TestCheckBreakoutFilter:
    """Tests pour check_breakout_filter"""

    @patch('core.analyzer.filters.TRADING_CONFIG', {'use_breakout': False})
    def test_breakout_disabled(self):
        """Test breakout filtre désactivé"""
        result = check_breakout_filter(
            price=50000,
            ema21=50000,
            atr=100,
            symbol='BTC/USDT:USDT',
            timeframe='1m',
            return_reason=False
        )
        assert result is None

    @patch('core.analyzer.filters.TRADING_CONFIG', {'use_breakout': True, 'breakout_threshold': 0.3})
    def test_breakout_valid(self):
        """Test breakout valide (hors range)"""
        result = check_breakout_filter(
            price=50000,
            ema21=49500,  # Diff = 500
            atr=100,  # Threshold = 30 (100 * 0.3)
            symbol='BTC/USDT:USDT',
            timeframe='1m',
            return_reason=False
        )
        # Price = 50000 est bien au-dessus de 49500 + 30
        assert result is None

    @patch('core.analyzer.filters.TRADING_CONFIG', {'use_breakout': True, 'breakout_threshold': 0.3})
    @patch('core.analyzer.filters.DEBUG_ENABLED', True)
    def test_breakout_in_range_return_reason(self):
        """Test pas de breakout (dans range) avec return_reason=True"""
        result = check_breakout_filter(
            price=50000,
            ema21=50000,  # Prix = EMA
            atr=100,  # Threshold = 30
            symbol='BTC/USDT:USDT',
            timeframe='1m',
            return_reason=True
        )
        # Prix dans range [49970, 50030]
        assert result is not None
        assert 'Pas de breakout' in result['reason']

    @patch('core.analyzer.filters.TRADING_CONFIG', {'use_breakout': True, 'breakout_threshold': 0.3})
    @patch('core.analyzer.filters.DEBUG_ENABLED', True)
    def test_breakout_in_range_no_return_reason(self):
        """Test pas de breakout avec return_reason=False"""
        result = check_breakout_filter(
            price=50000,
            ema21=50000,
            atr=100,
            symbol='BTC/USDT:USDT',
            timeframe='1m',
            return_reason=False
        )
        assert result is not None
        assert result['rejected'] is True


class TestCheckWickFilter:
    """Tests pour check_wick_filter"""

    @patch('core.analyzer.filters.TRADING_CONFIG', {'use_wick': False})
    def test_wick_disabled(self):
        """Test wick filtre désactivé"""
        candle = [1234567890, 50000, 51000, 49000, 50500, 1000]
        result = check_wick_filter(
            current_candle=candle,
            symbol='BTC/USDT:USDT',
            timeframe='1m',
            return_reason=False
        )
        assert result is None

    @patch('core.analyzer.filters.TRADING_CONFIG', {'use_wick': True, 'wick_ratio_max': 2.5})
    def test_wick_normal(self):
        """Test wick normal (pas de manipulation)"""
        # Open=50000, Close=50500, High=50600, Low=49900
        # Body = 500, Range = 700, Ratio = 700/500 = 1.4 < 2.5
        candle = [1234567890, 50000, 50600, 49900, 50500, 1000]
        result = check_wick_filter(
            current_candle=candle,
            symbol='BTC/USDT:USDT',
            timeframe='1m',
            return_reason=False
        )
        assert result is None

    @patch('core.analyzer.filters.TRADING_CONFIG', {'use_wick': True, 'wick_ratio_max': 2.5})
    @patch('core.analyzer.filters.DEBUG_ENABLED', True)
    def test_wick_excessive_return_reason(self):
        """Test wick excessif avec return_reason=True"""
        # Open=50000, Close=50100, High=51000, Low=49000
        # Body = 100, Range = 2000, Ratio = 2000/100 = 20 > 2.5
        candle = [1234567890, 50000, 51000, 49000, 50100, 1000]
        result = check_wick_filter(
            current_candle=candle,
            symbol='BTC/USDT:USDT',
            timeframe='1m',
            return_reason=True
        )
        assert result is not None
        assert 'Wicks suspects' in result['reason']

    @patch('core.analyzer.filters.TRADING_CONFIG', {'use_wick': True, 'wick_ratio_max': 2.5})
    @patch('core.analyzer.filters.DEBUG_ENABLED', True)
    def test_wick_excessive_no_return_reason(self):
        """Test wick excessif avec return_reason=False"""
        candle = [1234567890, 50000, 51000, 49000, 50100, 1000]
        result = check_wick_filter(
            current_candle=candle,
            symbol='BTC/USDT:USDT',
            timeframe='1m',
            return_reason=False
        )
        assert result is not None
        assert result['rejected'] is True

    @patch('core.analyzer.filters.TRADING_CONFIG', {'use_wick': True, 'wick_ratio_max': 2.5})
    def test_wick_zero_body(self):
        """Test wick avec body = 0 (doji)"""
        # Open=Close=50000 → body = 0 → utilise 0.0001
        candle = [1234567890, 50000, 50500, 49500, 50000, 1000]
        result = check_wick_filter(
            current_candle=candle,
            symbol='BTC/USDT:USDT',
            timeframe='1m',
            return_reason=False
        )
        # Range = 1000, Body = 0.0001, Ratio = 10000000 >> 2.5
        # Devrait rejeter
        assert result is not None


class TestCheckATRFilter:
    """Tests pour check_atr_filter"""

    @patch('core.analyzer.filters.TRADING_CONFIG', {
        'optimal_atr_min_1m': 0.3,
        'optimal_atr_max_1m': 1.5,
        'optimal_atr_min_5m': 0.4,
        'optimal_atr_max_5m': 2.0
    })
    def test_atr_optimal_1m(self):
        """Test ATR optimal pour 1m"""
        result = check_atr_filter(
            atr_percent=0.8,  # Dans [0.3, 1.5]
            timeframe='1m',
            symbol='BTC/USDT:USDT',
            return_reason=False
        )
        assert result is None

    @patch('core.analyzer.filters.TRADING_CONFIG', {
        'optimal_atr_min_1m': 0.3,
        'optimal_atr_max_1m': 1.5,
        'optimal_atr_min_5m': 0.4,
        'optimal_atr_max_5m': 2.0
    })
    def test_atr_optimal_5m(self):
        """Test ATR optimal pour 5m"""
        result = check_atr_filter(
            atr_percent=1.0,  # Dans [0.4, 2.0]
            timeframe='5m',
            symbol='BTC/USDT:USDT',
            return_reason=False
        )
        assert result is None

    @patch('core.analyzer.filters.TRADING_CONFIG', {
        'optimal_atr_min_1m': 0.3,
        'optimal_atr_max_1m': 1.5
    })
    @patch('core.analyzer.filters.DEBUG_ENABLED', True)
    def test_atr_too_low_return_reason(self):
        """Test ATR trop bas avec return_reason=True"""
        result = check_atr_filter(
            atr_percent=0.1,  # < 0.3
            timeframe='1m',
            symbol='BTC/USDT:USDT',
            return_reason=True
        )
        assert result is not None
        assert 'ATR sous-optimal' in result['reason']
        assert 'trop bas' in result['reason']

    @patch('core.analyzer.filters.TRADING_CONFIG', {
        'optimal_atr_min_1m': 0.3,
        'optimal_atr_max_1m': 1.5
    })
    @patch('core.analyzer.filters.DEBUG_ENABLED', True)
    def test_atr_too_high_return_reason(self):
        """Test ATR trop élevé avec return_reason=True"""
        result = check_atr_filter(
            atr_percent=2.0,  # > 1.5
            timeframe='1m',
            symbol='BTC/USDT:USDT',
            return_reason=True
        )
        assert result is not None
        assert 'ATR sous-optimal' in result['reason']
        assert 'trop élevé' in result['reason']

    @patch('core.analyzer.filters.TRADING_CONFIG', {
        'optimal_atr_min_1m': 0.3,
        'optimal_atr_max_1m': 1.5
    })
    @patch('core.analyzer.filters.DEBUG_ENABLED', True)
    def test_atr_too_low_no_return_reason(self):
        """Test ATR trop bas avec return_reason=False"""
        result = check_atr_filter(
            atr_percent=0.1,
            timeframe='1m',
            symbol='BTC/USDT:USDT',
            return_reason=False
        )
        assert result is not None
        assert result['rejected'] is True


class TestIntegration:
    """Tests d'intégration"""

    @patch('core.analyzer.filters.TRADING_CONFIG', {
        'use_snr': True,
        'snr_threshold': 0.3,
        'use_breakout': True,
        'breakout_threshold': 0.3,
        'use_wick': True,
        'wick_ratio_max': 2.5,
        'optimal_atr_min_1m': 0.3,
        'optimal_atr_max_1m': 1.5
    })
    def test_all_filters_pass(self):
        """Test tous les filtres passent"""
        # Volume
        vol_result = check_volume_filter(2.0, 1.0, 'BTC/USDT:USDT', '1m', 0.8, 1.0)
        assert vol_result is None

        # SNR
        snr_result = check_snr_filter(50000, 49500, 100, 'BTC/USDT:USDT', '1m')
        assert snr_result is None

        # Breakout
        breakout_result = check_breakout_filter(50000, 49500, 100, 'BTC/USDT:USDT', '1m')
        assert breakout_result is None

        # Wick
        candle = [1234567890, 50000, 50600, 49900, 50500, 1000]
        wick_result = check_wick_filter(candle, 'BTC/USDT:USDT', '1m')
        assert wick_result is None

        # ATR
        atr_result = check_atr_filter(0.8, '1m', 'BTC/USDT:USDT')
        assert atr_result is None
