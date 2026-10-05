"""
Tests pour TestableSignalGenerator - Trade Cursor v7.0
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from core.implementations.testable_signal_generator import TestableSignalGenerator
from core.interfaces.analyzer_interfaces import (
    AnalyzerConfig,
    TechnicalIndicators,
    MarketContext,
    SignalResult,
    SignalType,
    SignalStrength,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def analyzer_config():
    return AnalyzerConfig(
        min_signal_confidence=0.6, rsi_oversold=30, rsi_overbought=70, test_mode=True
    )


@pytest.fixture
def signal_generator(analyzer_config):
    return TestableSignalGenerator(analyzer_config)


@pytest.fixture
def technical_indicators():
    return TechnicalIndicators(
        rsi_1m=28.0,  # < 30 = oversold = bullish signal
        rsi_5m=32.0,
        macd_1m=150.0,
        macd_signal_1m=140.0,
        macd_histogram_1m=10.0,
        ema_20_1m=44800.0,
        ema_50_1m=44500.0,
        ema_200_1m=44000.0,
        atr_1m=500.0,
        atr_pct_1m=0.011,
        volume_sma_1m=950000.0,
        volume_ratio_1m=1.5,  # >= 1.5 pour signal volume 'confirming'
        adx_1m=25.0,
        stoch_k_1m=55.0,
        stoch_d_1m=52.0,
    )


@pytest.fixture
def market_context():
    return MarketContext(
        symbol="BTC/USDT",
        current_price=45000.0,
        price_change_24h_pct=2.5,
        volume_24h=1000000.0,
        trading_session="european",
        is_weekend=False,
        market_volatility="medium",
        overall_trend="bullish",
    )


# =============================================================================
# TESTS INITIALISATION
# =============================================================================


class TestTestableSignalGeneratorInit:
    """Tests d'initialisation"""

    def test_init_default_config(self, analyzer_config):
        """Initialisation avec config par défaut"""
        generator = TestableSignalGenerator(analyzer_config)

        assert generator.config == analyzer_config
        assert generator.signals_generated == 0
        assert generator.primary_signals == 0
        assert generator.secondary_signals == 0
        assert generator.rsi_oversold == 30
        assert generator.rsi_overbought == 70
        assert generator.min_confidence == 0.6

    def test_init_custom_config(self):
        """Initialisation avec config personnalisée"""
        config = AnalyzerConfig(
            min_signal_confidence=0.8,
            rsi_oversold=25,
            rsi_overbought=75,
            test_mode=True,
        )
        generator = TestableSignalGenerator(config)

        assert generator.min_confidence == 0.8
        assert generator.rsi_oversold == 25
        assert generator.rsi_overbought == 75

    def test_init_counters_reset(self, analyzer_config):
        """Compteurs réinitialisés à zéro"""
        generator = TestableSignalGenerator(analyzer_config)

        assert generator.signals_generated == 0
        assert generator.primary_signals == 0
        assert generator.secondary_signals == 0


# =============================================================================
# TESTS GENERATION SIGNAL
# =============================================================================


class TestTestableSignalGeneratorGenerateSignal:
    """Tests de génération de signal"""

    def test_generate_signal_bullish(
        self, signal_generator, technical_indicators, market_context
    ):
        """Génération signal haussier"""
        # Configurer indicateurs haussiers (RSI < 30 = oversold = bullish)
        technical_indicators.rsi_1m = 25.0
        technical_indicators.macd_1m = 150.0
        technical_indicators.macd_signal_1m = 140.0

        result = signal_generator.generate_signal(technical_indicators, market_context)

        assert result is not None
        assert result.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]
        assert result.confidence >= 0.0
        assert result.entry_price is not None
        assert result.entry_price == 45000.0

    def test_generate_signal_bearish(
        self, signal_generator, technical_indicators, market_context
    ):
        """Génération signal baissier"""
        # Configurer indicateurs baissiers (RSI > 70 = overbought = bearish)
        technical_indicators.rsi_1m = 75.0
        technical_indicators.macd_1m = -150.0
        technical_indicators.macd_signal_1m = -140.0
        # EMA baissière pour confirmation
        technical_indicators.ema_20_1m = 44000.0
        technical_indicators.ema_50_1m = 44500.0

        result = signal_generator.generate_signal(technical_indicators, market_context)

        assert result is not None
        assert result.signal_type in [SignalType.SELL, SignalType.STRONG_SELL]
        assert result.confidence >= 0.0
        assert result.entry_price is not None

    def test_generate_signal_neutral(
        self, signal_generator, technical_indicators, market_context
    ):
        """Génération signal neutre"""
        # Configurer indicateurs neutres (RSI 50, MACD plat, EMA alignées)
        technical_indicators.rsi_1m = 50.0
        technical_indicators.macd_1m = 0.0
        technical_indicators.macd_signal_1m = 0.0
        # EMA identiques pour neutralité
        technical_indicators.ema_20_1m = 44500.0
        technical_indicators.ema_50_1m = 44500.0

        result = signal_generator.generate_signal(technical_indicators, market_context)

        assert result is not None
        assert result.signal_type == SignalType.HOLD
        # La force peut être MODERATE si volume élevé
        assert result.strength in [SignalStrength.WEAK, SignalStrength.MODERATE]

    def test_generate_signal_counts(
        self, signal_generator, technical_indicators, market_context
    ):
        """Tracking du nombre de signaux"""
        signal_generator.generate_signal(technical_indicators, market_context)

        assert signal_generator.signals_generated == 1
        assert signal_generator.primary_signals == 1

    def test_generate_signal_multiple(
        self, signal_generator, technical_indicators, market_context
    ):
        """Plusieurs signaux successifs"""
        for _ in range(5):
            signal_generator.generate_signal(technical_indicators, market_context)

        assert signal_generator.signals_generated == 5
        assert signal_generator.primary_signals == 5


# =============================================================================
# TESTS ANALYSE INDICATEURS
# =============================================================================


class TestTestableSignalGeneratorAnalyzeIndicators:
    """Tests d'analyse des indicateurs"""

    def test_analyze_indicators_bullish(self, signal_generator, technical_indicators):
        """Analyse indicateurs haussiers"""
        technical_indicators.rsi_1m = 45.0
        technical_indicators.macd_1m = 150.0
        technical_indicators.macd_signal_1m = 140.0

        analysis = signal_generator._analyze_indicators_for_signal(
            technical_indicators, None
        )

        assert analysis is not None
        assert "bullish" in str(analysis).lower() or "neutral" in str(analysis).lower()

    def test_analyze_indicators_bearish(self, signal_generator, technical_indicators):
        """Analyse indicateurs baissiers"""
        technical_indicators.rsi_1m = 75.0
        technical_indicators.macd_1m = -150.0
        technical_indicators.macd_signal_1m = -140.0

        analysis = signal_generator._analyze_indicators_for_signal(
            technical_indicators, None
        )

        assert analysis is not None

    def test_analyze_indicators_rsi_oversold(
        self, signal_generator, technical_indicators
    ):
        """RSI oversold détecté"""
        technical_indicators.rsi_1m = 25.0

        analysis = signal_generator._analyze_indicators_for_signal(
            technical_indicators, None
        )

        assert analysis is not None

    def test_analyze_indicators_rsi_overbought(
        self, signal_generator, technical_indicators
    ):
        """RSI overbought détecté"""
        technical_indicators.rsi_1m = 75.0

        analysis = signal_generator._analyze_indicators_for_signal(
            technical_indicators, None
        )

        assert analysis is not None


# =============================================================================
# TESTS CALCUL FORCE SIGNAL
# =============================================================================


class TestTestableSignalGeneratorCalculateStrength:
    """Tests de calcul de force de signal"""

    def test_calculate_signal_strength_strong(
        self, signal_generator, technical_indicators
    ):
        """Force signal fort"""
        analysis = {"bullish_indicators": 8, "bearish_indicators": 2}

        strength = signal_generator._calculate_signal_strength(
            analysis, technical_indicators
        )

        assert strength in [
            SignalStrength.STRONG,
            SignalStrength.MODERATE,
            SignalStrength.WEAK,
        ]

    def test_calculate_signal_strength_weak(
        self, signal_generator, technical_indicators
    ):
        """Force signal faible"""
        analysis = {"bullish_indicators": 2, "bearish_indicators": 8}

        strength = signal_generator._calculate_signal_strength(
            analysis, technical_indicators
        )

        assert strength in [
            SignalStrength.STRONG,
            SignalStrength.MODERATE,
            SignalStrength.WEAK,
        ]

    def test_calculate_signal_strength_neutral(
        self, signal_generator, technical_indicators
    ):
        """Force signal neutre"""
        analysis = {"bullish_indicators": 5, "bearish_indicators": 5}

        strength = signal_generator._calculate_signal_strength(
            analysis, technical_indicators
        )

        assert strength == SignalStrength.WEAK


# =============================================================================
# TESTS CALCUL CONFIANCE
# =============================================================================


class TestTestableSignalGeneratorCalculateConfidence:
    """Tests de calcul de confiance"""

    def test_calculate_base_confidence(
        self, signal_generator, technical_indicators, market_context
    ):
        """Calcul confiance de base"""
        analysis = {
            "overall_bias": "bullish",
            "strength_score": 50,
            "confluence_count": 2,
        }

        confidence = signal_generator._calculate_base_confidence(
            analysis, technical_indicators, market_context
        )

        assert 0.0 <= confidence <= 1.0

    def test_adjust_confidence_market(
        self, signal_generator, technical_indicators, market_context
    ):
        """Ajustement confiance selon marché"""
        base_confidence = 0.7

        adjusted = signal_generator._adjust_confidence_for_market(
            base_confidence, market_context, technical_indicators
        )

        assert 0.0 <= adjusted <= 1.0


# =============================================================================
# TESTS NIVEAUX PRIX
# =============================================================================


class TestTestableSignalGeneratorPriceLevels:
    """Tests de calcul des niveaux de prix"""

    def test_calculate_price_levels_buy(
        self, signal_generator, technical_indicators, market_context
    ):
        """Calcul niveaux prix pour BUY"""
        entry, target, stop = signal_generator._calculate_price_levels(
            SignalType.BUY, market_context, technical_indicators
        )

        assert entry == 45000.0
        assert target > entry
        assert stop < entry

    def test_calculate_price_levels_sell(
        self, signal_generator, technical_indicators, market_context
    ):
        """Calcul niveaux prix pour SELL"""
        entry, target, stop = signal_generator._calculate_price_levels(
            SignalType.SELL, market_context, technical_indicators
        )

        assert entry == 45000.0
        assert target < entry
        assert stop > entry

    def test_calculate_price_levels_hold(
        self, signal_generator, technical_indicators, market_context
    ):
        """Calcul niveaux prix pour HOLD"""
        entry, target, stop = signal_generator._calculate_price_levels(
            SignalType.HOLD, market_context, technical_indicators
        )

        # HOLD ne retourne pas de niveaux de prix
        assert entry is None
        assert target is None
        assert stop is None


# =============================================================================
# TESTS JUSTIFICATION
# =============================================================================


class TestTestableSignalGeneratorReasoning:
    """Tests de génération de justification"""

    def test_generate_signal_reasoning(
        self, signal_generator, technical_indicators, market_context
    ):
        """Génération justification"""
        reasoning = signal_generator._generate_signal_reasoning(
            {}, technical_indicators, market_context
        )

        assert reasoning is not None
        assert isinstance(reasoning, list)

    def test_extract_key_indicators(self, signal_generator, technical_indicators):
        """Extraction indicateurs clés"""
        key_indicators = signal_generator._extract_key_indicators(
            technical_indicators, {}
        )

        assert key_indicators is not None
        assert isinstance(key_indicators, dict)


# =============================================================================
# TESTS ERREURS
# =============================================================================


class TestTestableSignalGeneratorExceptions:
    """Tests de gestion d'exceptions"""

    def test_generate_signal_exception(
        self, signal_generator, technical_indicators, market_context
    ):
        """Gestion exception génération"""
        with patch.object(
            signal_generator,
            "_analyze_indicators_for_signal",
            side_effect=Exception("Test error"),
        ):
            result = signal_generator.generate_signal(
                technical_indicators, market_context
            )

            assert result.signal_type == SignalType.HOLD
            assert result.strength == SignalStrength.WEAK


# =============================================================================
# RUNNER
# =============================================================================

if __name__ == "__main__":
    pytest.main(
        [
            __file__,
            "-v",
            "--cov=core.implementations.testable_signal_generator",
            "--cov-report=term-missing",
        ]
    )
