"""
Unit tests for utils/indicators_helpers.py
"""
import pytest
from utils.indicators_helpers import (
    extract_indicators_1m,
    extract_indicators_5m,
    build_indicators_from_analysis,
    count_non_null_values,
    INDICATOR_FIELDS_1M
)


class TestExtractIndicators1m:
    """Tests for extract_indicators_1m function."""

    def test_extract_basic_indicators(self):
        """Test extraction of basic 1m indicators."""
        source = {
            'rsi': 65.5,
            'macd': 0.015,
            'adx': 28.3,
            'ema9': 50000.0,
            'volume': 1000000,
        }

        result = extract_indicators_1m(source)

        assert result['rsi'] == 65.5
        assert result['macd'] == 0.015
        assert result['adx'] == 28.3
        assert result['ema9'] == 50000.0
        assert result['volume'] == 1000000

    def test_extract_with_missing_fields(self):
        """Test extraction when some fields are missing."""
        source = {
            'rsi': 65.5,
            # macd missing
            'adx': 28.3,
        }

        result = extract_indicators_1m(source)

        assert result['rsi'] == 65.5
        assert result['macd'] is None
        assert result['adx'] == 28.3

    def test_extract_all_fields_present(self):
        """Test extraction when all fields are present."""
        source = {field: float(i) for i, field in enumerate(INDICATOR_FIELDS_1M)}

        result = extract_indicators_1m(source)

        # All fields should be present
        assert len(result) == len(INDICATOR_FIELDS_1M)
        # Check specific values
        for i, field in enumerate(INDICATOR_FIELDS_1M):
            assert result[field] == float(i)

    def test_volume_ratio_fallback_to_volumeSpike(self):
        """Test that volume_ratio falls back to volumeSpike."""
        source = {
            'volumeSpike': 2.5,
            # volume_ratio not present
        }

        result = extract_indicators_1m(source)

        assert result['volume_ratio'] == 2.5

    def test_volume_ratio_prefers_volume_ratio(self):
        """Test that volume_ratio is preferred over volumeSpike."""
        source = {
            'volume_ratio': 3.0,
            'volumeSpike': 2.5,
        }

        result = extract_indicators_1m(source)

        assert result['volume_ratio'] == 3.0

    def test_empty_source(self):
        """Test extraction from empty source."""
        result = extract_indicators_1m({})

        # All values should be None
        for field in INDICATOR_FIELDS_1M:
            assert result[field] is None


class TestExtractIndicators5m:
    """Tests for extract_indicators_5m function."""

    def test_extract_basic_indicators_with_suffix(self):
        """Test extraction of 5m indicators with _5m suffix."""
        source = {
            'rsi_5m': 68.2,
            'macd_5m': 0.020,
            'adx_5m': 32.1,
            'ema9_5m': 51000.0,
            'volume_5m': 2000000,
        }

        result = extract_indicators_5m(source)

        # Result should have keys without _5m suffix
        assert result['rsi'] == 68.2
        assert result['macd'] == 0.020
        assert result['adx'] == 32.1
        assert result['ema9'] == 51000.0
        assert result['volume'] == 2000000

    def test_atr_with_multiple_possible_keys(self):
        """Test ATR extraction with multiple possible key names."""
        # Test with atr5m
        source1 = {'atr5m': 0.5}
        result1 = extract_indicators_5m(source1)
        assert result1['atr'] == 0.5

        # Test with atr_5m
        source2 = {'atr_5m': 0.6}
        result2 = extract_indicators_5m(source2)
        assert result2['atr'] == 0.6

        # Test with both (should prefer first in list)
        source3 = {'atr5m': 0.5, 'atr_5m': 0.6}
        result3 = extract_indicators_5m(source3)
        assert result3['atr'] == 0.5

    def test_extract_with_missing_fields(self):
        """Test extraction when some 5m fields are missing."""
        source = {
            'rsi_5m': 68.2,
            # macd_5m missing
            'adx_5m': 32.1,
        }

        result = extract_indicators_5m(source)

        assert result['rsi'] == 68.2
        assert result['macd'] is None
        assert result['adx'] == 32.1

    def test_empty_source(self):
        """Test extraction from empty source."""
        result = extract_indicators_5m({})

        # All values should be None
        assert all(value is None for value in result.values())


class TestBuildIndicatorsFromAnalysis:
    """Tests for build_indicators_from_analysis function."""

    def test_build_1m_from_analysis_1m(self):
        """Test building 1m indicators from analysis_1m nested dict."""
        analysis = {
            'symbol': 'BTC/USDT',
            'analysis_1m': {
                'rsi': 65.5,
                'macd': 0.015,
                'adx': 28.3,
            }
        }

        result = build_indicators_from_analysis(analysis, '1m')

        assert result['rsi'] == 65.5
        assert result['macd'] == 0.015
        assert result['adx'] == 28.3

    def test_build_1m_from_direct_analysis(self):
        """Test building 1m indicators from analysis root level."""
        analysis = {
            'symbol': 'BTC/USDT',
            'rsi': 65.5,
            'macd': 0.015,
            'adx': 28.3,
        }

        result = build_indicators_from_analysis(analysis, '1m')

        assert result['rsi'] == 65.5
        assert result['macd'] == 0.015
        assert result['adx'] == 28.3

    def test_build_5m_from_analysis_5m(self):
        """Test building 5m indicators from analysis_5m nested dict."""
        analysis = {
            'symbol': 'BTC/USDT',
            'analysis_5m': {
                'rsi': 68.2,
                'macd': 0.020,
                'adx': 32.1,
            }
        }

        result = build_indicators_from_analysis(analysis, '5m')

        assert result['rsi'] == 68.2
        assert result['macd'] == 0.020
        assert result['adx'] == 32.1

    def test_build_5m_from_direct_analysis_with_suffix(self):
        """Test building 5m indicators from analysis root with _5m suffix."""
        analysis = {
            'symbol': 'BTC/USDT',
            'rsi_5m': 68.2,
            'macd_5m': 0.020,
            'adx_5m': 32.1,
        }

        result = build_indicators_from_analysis(analysis, '5m')

        assert result['rsi'] == 68.2
        assert result['macd'] == 0.020
        assert result['adx'] == 32.1

    def test_use_existing_indicators_if_present(self):
        """Test that existing indicators_Xm are returned if present."""
        analysis = {
            'symbol': 'BTC/USDT',
            'indicators_1m': {
                'rsi': 70.0,  # Pre-built indicators
                'macd': 0.025,
            },
            'analysis_1m': {
                'rsi': 65.5,  # Should be ignored
                'macd': 0.015,
            }
        }

        result = build_indicators_from_analysis(analysis, '1m')

        # Should use pre-built indicators
        assert result['rsi'] == 70.0
        assert result['macd'] == 0.025

    def test_invalid_analysis_type(self):
        """Test with invalid analysis type."""
        result = build_indicators_from_analysis(None, '1m')
        assert result == {}

        result = build_indicators_from_analysis("invalid", '1m')
        assert result == {}

    def test_empty_analysis(self):
        """Test with empty analysis dict."""
        result = build_indicators_from_analysis({}, '1m')

        # Should return dict with all None values
        assert all(value is None for value in result.values())


class TestCountNonNullValues:
    """Tests for count_non_null_values function."""

    def test_count_all_non_null(self):
        """Test counting when all values are non-null."""
        indicators = {
            'rsi': 65.5,
            'macd': 0.015,
            'adx': 28.3,
            'volume': 1000000,
        }

        count = count_non_null_values(indicators)
        assert count == 4

    def test_count_mixed_null_and_non_null(self):
        """Test counting when some values are null."""
        indicators = {
            'rsi': 65.5,
            'macd': None,
            'adx': 28.3,
            'volume': None,
            'ema9': 50000.0,
        }

        count = count_non_null_values(indicators)
        assert count == 3

    def test_count_all_null(self):
        """Test counting when all values are null."""
        indicators = {
            'rsi': None,
            'macd': None,
            'adx': None,
        }

        count = count_non_null_values(indicators)
        assert count == 0

    def test_count_empty_dict(self):
        """Test counting with empty dict."""
        count = count_non_null_values({})
        assert count == 0

    def test_count_with_zero_and_false_values(self):
        """Test that 0 and False are counted as non-null."""
        indicators = {
            'value1': 0,  # Should be counted
            'value2': False,  # Should be counted
            'value3': None,  # Should not be counted
            'value4': '',  # Should be counted (empty string is not None)
        }

        count = count_non_null_values(indicators)
        assert count == 3  # 0, False, and '' are counted


class TestIntegration:
    """Integration tests using realistic data."""

    def test_realistic_analysis_flow(self):
        """Test realistic flow of extracting indicators from analysis."""
        # Simulate analysis returned by analyzer.analyze_pair()
        analysis = {
            'symbol': 'BTC/USDT',
            'direction': 'LONG',
            'entry': 50000.0,
            'sl': 49500.0,
            'tp': 50500.0,
            'analysis_1m': {
                'rsi': 65.5,
                'rsi_prev': 60.2,
                'macd': 0.015,
                'macd_signal': 0.012,
                'adx': 28.3,
                'ema9': 49900.0,
                'ema21': 49500.0,
                'volume': 1000000,
                'volume_avg': 800000,
                'volume_ratio': 1.25,
            },
            'analysis_5m': {
                'rsi': 68.2,
                'rsi_prev': 65.1,
                'macd': 0.020,
                'macd_signal': 0.018,
                'adx': 32.1,
                'ema9': 50100.0,
                'ema21': 49800.0,
                'volume': 5000000,
                'volume_avg': 4000000,
                'volume_ratio': 1.25,
            }
        }

        # Extract 1m indicators
        indicators_1m = build_indicators_from_analysis(analysis, '1m')
        assert indicators_1m['rsi'] == 65.5
        assert indicators_1m['adx'] == 28.3
        assert indicators_1m['volume_ratio'] == 1.25
        assert count_non_null_values(indicators_1m) == 10

        # Extract 5m indicators
        indicators_5m = build_indicators_from_analysis(analysis, '5m')
        assert indicators_5m['rsi'] == 68.2
        assert indicators_5m['adx'] == 32.1
        assert indicators_5m['volume_ratio'] == 1.25
        assert count_non_null_values(indicators_5m) == 10

    def test_analysis_without_setup(self):
        """Test analysis when no setup is found (typical no-trade scenario)."""
        analysis = {
            'symbol': 'ETH/USDT',
            'reason': 'Insufficient volume',
            'analysis_1m': {
                'rsi': 45.0,
                'adx': 15.0,
                'volume_ratio': 0.5,
            },
            'analysis_5m': {
                'rsi': 48.0,
                'adx': 18.0,
                'volume_ratio': 0.6,
            }
        }

        indicators_1m = build_indicators_from_analysis(analysis, '1m')
        assert indicators_1m['rsi'] == 45.0
        assert indicators_1m['adx'] == 15.0

        indicators_5m = build_indicators_from_analysis(analysis, '5m')
        assert indicators_5m['rsi'] == 48.0
        assert indicators_5m['adx'] == 18.0
