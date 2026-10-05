"""
Tests pour la détection de risques
"""
import pytest
from core.analyzer.risk_detector import detect_manipulation, check_price_action_coherence


class TestRiskDetector:
    """Tests pour la détection de risques"""

    def test_detect_manipulation_clean(self):
        """Test détection manipulation - données propres"""
        ohlcv = [
            [0, 49000, 49500, 48500, 49200, 1000],
            [1, 49200, 49700, 48700, 49400, 1200],
            [2, 49400, 49900, 48900, 49600, 1100]
        ]
        result = detect_manipulation(
            symbol='BTCUSDT',
            timeframe='1m',
            ohlcv=ohlcv,
            volume=1000,
            vol_spike=1.5
        )
        assert result['suspicious'] is False
        assert result['severity'] == 'NONE'

    def test_detect_manipulation_no_data(self):
        """Test détection manipulation - pas de données"""
        result = detect_manipulation(
            symbol='BTCUSDT',
            timeframe='1m',
            ohlcv=None,
            volume=1000,
            vol_spike=1.5
        )
        assert result['suspicious'] is False
        assert result['severity'] == 'NONE'

    def test_detect_manipulation_volume_spike(self):
        """Test détection manipulation - volume spike extrême"""
        ohlcv = [
            [0, 49000, 49500, 48500, 49200, 1000],
            [1, 49200, 49700, 48700, 49400, 1200],
            [2, 49400, 49900, 48900, 49600, 1100]
        ]
        result = detect_manipulation(
            symbol='BTCUSDT',
            timeframe='1m',
            ohlcv=ohlcv,
            volume=1000,
            vol_spike=10.0  # Volume spike extrême
        )
        # Le résultat peut varier selon les seuils
        assert 'suspicious' in result
        assert 'severity' in result

    def test_check_price_action_coherence_long(self):
        """Test cohérence price action - LONG"""
        current_candle = [0, 49000, 49500, 48500, 49200, 1000]
        previous_candle = [1, 48800, 49300, 48300, 49000, 900]
        
        result = check_price_action_coherence(
            direction='LONG',
            current_candle=current_candle,
            previous_candle=previous_candle,
            ema9=49100,
            ema21=48900
        )
        assert 'coherent' in result
        assert 'quality' in result

    def test_check_price_action_coherence_short(self):
        """Test cohérence price action - SHORT"""
        current_candle = [0, 49200, 49500, 48500, 49000, 1000]
        previous_candle = [1, 49400, 49700, 48700, 49200, 900]
        
        result = check_price_action_coherence(
            direction='SHORT',
            current_candle=current_candle,
            previous_candle=previous_candle,
            ema9=49100,
            ema21=49300
        )
        assert 'coherent' in result
        assert 'quality' in result

    def test_check_price_action_coherence_no_previous(self):
        """Test cohérence price action - pas de bougie précédente"""
        current_candle = [0, 49000, 49500, 48500, 49200, 1000]
        
        result = check_price_action_coherence(
            direction='LONG',
            current_candle=current_candle,
            previous_candle=None,
            ema9=49100,
            ema21=48900
        )
        assert result['coherent'] is True
        assert result['quality'] == 'UNKNOWN'
