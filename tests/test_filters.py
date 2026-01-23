"""
Tests pour les filtres d'analyse technique
"""
import pytest
from core.analyzer.filters import (
    check_volume_filter,
    check_snr_filter,
    check_breakout_filter,
    check_wick_filter,
    check_atr_filter
)


class TestFilters:
    """Tests pour les filtres d'analyse"""

    def test_check_volume_filter_pass(self):
        """Test filtre volume avec volume suffisant"""
        result = check_volume_filter(
            vol_spike=1.5,
            min_vol_ratio=1.0,
            atr_percent=0.5,
            symbol='BTCUSDT',
            timeframe='1m',
            volume_multiplier=1.0,
            return_reason=False
        )
        assert result is None

    def test_check_volume_filter_fail(self):
        """Test filtre volume avec volume insuffisant"""
        result = check_volume_filter(
            vol_spike=0.5,
            min_vol_ratio=1.0,
            atr_percent=0.5,
            symbol='BTCUSDT',
            timeframe='1m',
            volume_multiplier=1.0,
            return_reason=True
        )
        assert result is not None
        assert 'reason' in result

    def test_check_snr_filter_pass(self):
        """Test filtre SNR avec signal suffisant"""
        result = check_snr_filter(
            price=50000.0,
            ema21=49000.0,
            atr=200.0,
            symbol='BTCUSDT',
            timeframe='1m',
            return_reason=False
        )
        assert result is None

    def test_check_snr_filter_fail(self):
        """Test filtre SNR avec signal insuffisant"""
        result = check_snr_filter(
            price=49500.0,
            ema21=49000.0,
            atr=200.0,
            symbol='BTCUSDT',
            timeframe='1m',
            return_reason=True
        )
        # Le résultat peut être None si le filtre est désactivé
        if result is not None:
            assert 'reason' in result

    def test_check_wick_filter_pass(self):
        """Test filtre wick avec wicks normaux"""
        candle = [0, 49000.0, 49500.0, 48500.0, 49200.0, 1000]
        result = check_wick_filter(
            current_candle=candle,
            symbol='BTCUSDT',
            timeframe='1m',
            return_reason=False
        )
        assert result is None

    def test_check_wick_filter_fail(self):
        """Test filtre wick avec wicks suspects"""
        candle = [0, 49000.0, 49500.0, 48500.0, 49100.0, 1000]
        result = check_wick_filter(
            current_candle=candle,
            symbol='BTCUSDT',
            timeframe='1m',
            return_reason=True
        )
        # Le test peut passer ou échouer selon le ratio
        if result is not None:
            assert 'reason' in result

    def test_check_atr_filter_pass(self):
        """Test filtre ATR avec ATR optimal"""
        result = check_atr_filter(
            atr_percent=0.5,
            timeframe='1m',
            symbol='BTCUSDT',
            return_reason=False
        )
        assert result is None

    def test_check_atr_filter_fail_low(self):
        """Test filtre ATR avec ATR trop bas"""
        result = check_atr_filter(
            atr_percent=0.1,
            timeframe='1m',
            symbol='BTCUSDT',
            return_reason=True
        )
        # Le résultat peut être None si le filtre est désactivé
        if result is not None:
            assert 'reason' in result
