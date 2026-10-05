#!/usr/bin/env python3
"""
Tests pour TestableAnalyzerV2 - Trade Cursor v7.0
Couverture: core/implementations/testable_analyzer_v2.py (514 lignes)
Tests adaptés à la structure réelle du code
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys
import os

# Ajout du chemin parent pour imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.implementations.testable_analyzer_v2 import TestableAnalyzerV2
from core.interfaces.analyzer_interfaces import (
    AnalysisResult,
    AnalysisStatus,
    AnalyzerConfig,
    TechnicalIndicators,
    MarketContext,
    SignalResult,
    SignalType,
    SignalStrength,
    IIndicatorCalculator,
    ISignalGenerator,
    IScoreCalculator,
)


class MockIndicatorCalculator(IIndicatorCalculator):
    """Mock pour IIndicatorCalculator"""

    def calculate_rsi(self, prices, period=14):
        return 45.0

    def calculate_macd(self, prices, fast=12, slow=26, signal=9):
        return 10.0, 8.0, 2.0

    def calculate_ema(self, prices, period):
        return 50000.0

    def calculate_atr(self, highs, lows, closes, period=14):
        return 500.0

    def calculate_all_indicators(self, market_data):
        return TechnicalIndicators(
            rsi_1m=45.0,
            rsi_5m=48.0,
            macd_1m=10.0,
            macd_signal_1m=8.0,
            macd_histogram_1m=2.0,
            ema_20_1m=50000.0,
            ema_50_1m=49800.0,
            atr_1m=500.0,
            atr_pct_1m=0.01,
        )


class MockSignalGenerator(ISignalGenerator):
    """Mock pour ISignalGenerator"""

    def generate_signal(self, indicators, market_context):
        return SignalResult(
            signal_type=SignalType.BUY,
            strength=SignalStrength.STRONG,
            confidence=0.85,
            entry_price=50000.0,
            target_price=51000.0,
            stop_loss_price=49500.0,
            reasoning=["RSI neutral", "MACD bullish"],
            generated_at=datetime.utcnow(),
        )

    def generate_secondary_signals(self, indicators, market_context):
        return []

    def calculate_confidence(self, signal, indicators):
        return 0.85


class MockScoreCalculator(IScoreCalculator):
    """Mock pour IScoreCalculator"""

    def calculate_score_1m(self, indicators, market_context):
        return 6.5

    def calculate_score_5m(self, indicators, market_context):
        return 6.0

    def calculate_combined_score(self, score_1m, score_5m, market_context):
        return 6.25

    def adjust_score_for_conditions(self, base_score, market_context):
        return base_score


class TestTestableAnalyzerV2Init:
    """Tests d'initialisation de TestableAnalyzerV2"""

    def test_init_default(self):
        """Test initialisation avec composants"""
        config = AnalyzerConfig(min_signal_confidence=0.6, min_score_threshold=3.0)
        indicator_calc = MockIndicatorCalculator()
        signal_gen = MockSignalGenerator()
        score_calc = MockScoreCalculator()

        analyzer = TestableAnalyzerV2(
            config=config,
            indicator_calculator=indicator_calc,
            signal_generator=signal_gen,
            score_calculator=score_calc,
        )

        assert analyzer.config == config
        assert analyzer.indicator_calculator == indicator_calc
        assert analyzer.signal_generator == signal_gen
        assert analyzer.score_calculator == score_calc
        assert analyzer.analysis_count == 0
        assert analyzer.success_count == 0
        assert analyzer.error_count == 0

    def test_init_default_indicators(self):
        """Test initialisation avec indicateurs par défaut"""
        config = AnalyzerConfig()
        analyzer = TestableAnalyzerV2(
            config=config,
            indicator_calculator=MockIndicatorCalculator(),
            signal_generator=MockSignalGenerator(),
            score_calculator=MockScoreCalculator(),
        )

        assert config.rsi_oversold == 30.0
        assert config.rsi_overbought == 70.0
        assert config.ema_periods == [20, 50, 200]


class TestTestableAnalyzerV2AnalyzePair:
    """Tests de la méthode analyze_pair"""

    def test_analyze_pair_success(self):
        """Test analyse paire succès"""
        config = AnalyzerConfig(min_signal_confidence=0.6, min_score_threshold=3.0)
        analyzer = TestableAnalyzerV2(
            config=config,
            indicator_calculator=MockIndicatorCalculator(),
            signal_generator=MockSignalGenerator(),
            score_calculator=MockScoreCalculator(),
        )

        now = datetime.utcnow()
        market_data = {
            "symbol": "BTC/USDT",
            "current_price": 50000.0,
            "volume_24h": 1000000.0,
            "timestamp": now.timestamp(),
            "ohlcv_1m": [
                [
                    now.timestamp() - i * 60,
                    50000 - i * 10,
                    50100 - i * 10,
                    49900 - i * 10,
                    50050 - i * 5,
                    1000,
                ]
                for i in range(100)
            ],
            "ohlcv_5m": [
                [
                    now.timestamp() - i * 300,
                    50000 - i * 20,
                    50100 - i * 20,
                    49900 - i * 20,
                    50050 - i * 10,
                    5000,
                ]
                for i in range(50)
            ],
        }

        result = analyzer.analyze_pair("BTC/USDT", market_data)

        assert isinstance(result, AnalysisResult)
        assert result.symbol == "BTC/USDT"
        assert result.status == AnalysisStatus.SUCCESS
        assert result.combined_score is not None
        assert result.indicators is not None
        assert result.market_context is not None
        assert analyzer.success_count == 1
        assert analyzer.analysis_count == 1

    def test_analyze_pair_insufficient_data(self):
        """Test analyse données insuffisantes"""
        config = AnalyzerConfig(min_signal_confidence=0.6, min_data_quality=0.9)
        analyzer = TestableAnalyzerV2(
            config=config,
            indicator_calculator=MockIndicatorCalculator(),
            signal_generator=MockSignalGenerator(),
            score_calculator=MockScoreCalculator(),
        )

        market_data = {
            "symbol": "TEST/USDT",
            "price": 100.0,
            # Pas d'ohlcv, pas de volume
        }

        result = analyzer.analyze_pair("TEST/USDT", market_data)

        assert isinstance(result, AnalysisResult)
        assert result.symbol == "TEST/USDT"
        assert result.status in [
            AnalysisStatus.INSUFFICIENT_DATA,
            AnalysisStatus.FAILED,
        ]

    def test_analyze_pair_low_score(self):
        """Test analyse score insuffisant"""
        config = AnalyzerConfig(min_signal_confidence=0.6, min_score_threshold=8.0)

        class LowScoreCalculator(MockScoreCalculator):
            def calculate_combined_score(self, score_1m, score_5m, market_context):
                return 2.0  # Score très bas

        analyzer = TestableAnalyzerV2(
            config=config,
            indicator_calculator=MockIndicatorCalculator(),
            signal_generator=MockSignalGenerator(),
            score_calculator=LowScoreCalculator(),
        )

        now = datetime.utcnow()
        market_data = {
            "symbol": "BTC/USDT",
            "current_price": 50000.0,
            "volume_24h": 1000000.0,
            "timestamp": now.timestamp(),
            "ohlcv_1m": [
                [
                    now.timestamp() - i * 60,
                    50000 - i * 10,
                    50100 - i * 10,
                    49900 - i * 10,
                    50050 - i * 5,
                    1000,
                ]
                for i in range(100)
            ],
            "ohlcv_5m": [
                [
                    now.timestamp() - i * 300,
                    50000 - i * 20,
                    50100 - i * 20,
                    49900 - i * 20,
                    50050 - i * 10,
                    5000,
                ]
                for i in range(50)
            ],
        }

        result = analyzer.analyze_pair("BTC/USDT", market_data)

        assert isinstance(result, AnalysisResult)
        assert result.status == AnalysisStatus.FAILED
        assert "Score below threshold" in result.errors[0]

    def test_analyze_pair_incomplete_indicators(self):
        """Test analyse indicateurs incomplets"""
        config = AnalyzerConfig(min_signal_confidence=0.6)

        class IncompleteIndicatorCalculator(MockIndicatorCalculator):
            def calculate_all_indicators(self, market_data):
                indicators = TechnicalIndicators()
                indicators.rsi_1m = 45.0  # Uniquement RSI
                return indicators

        analyzer = TestableAnalyzerV2(
            config=config,
            indicator_calculator=IncompleteIndicatorCalculator(),
            signal_generator=MockSignalGenerator(),
            score_calculator=MockScoreCalculator(),
        )

        market_data = {"symbol": "BTC/USDT", "price": 50000.0}

        result = analyzer.analyze_pair("BTC/USDT", market_data)

        assert isinstance(result, AnalysisResult)
        assert result.status == AnalysisStatus.INSUFFICIENT_DATA

    def test_analyze_pair_exception(self):
        """Test analyse exception"""
        config = AnalyzerConfig(min_signal_confidence=0.6)

        class FailingSignalGenerator(MockSignalGenerator):
            def generate_signal(self, indicators, market_context):
                raise Exception("Erreur de génération")

        analyzer = TestableAnalyzerV2(
            config=config,
            indicator_calculator=MockIndicatorCalculator(),
            signal_generator=FailingSignalGenerator(),
            score_calculator=MockScoreCalculator(),
        )

        now = datetime.utcnow()
        market_data = {
            "symbol": "BTC/USDT",
            "current_price": 50000.0,
            "volume_24h": 1000000.0,
            "timestamp": now.timestamp(),
            "ohlcv_1m": [
                [
                    now.timestamp() - i * 60,
                    50000 - i * 10,
                    50100 - i * 10,
                    49900 - i * 10,
                    50050 - i * 5,
                    1000,
                ]
                for i in range(100)
            ],
            "ohlcv_5m": [
                [
                    now.timestamp() - i * 300,
                    50000 - i * 20,
                    50100 - i * 20,
                    49900 - i * 20,
                    50050 - i * 10,
                    5000,
                ]
                for i in range(50)
            ],
        }

        result = analyzer.analyze_pair("BTC/USDT", market_data)

        assert isinstance(result, AnalysisResult)
        assert result.status == AnalysisStatus.FAILED
        assert analyzer.error_count == 1

    def test_analyze_pair_empty_symbol(self):
        """Test analyse symbole vide"""
        config = AnalyzerConfig(min_signal_confidence=0.6)
        analyzer = TestableAnalyzerV2(
            config=config,
            indicator_calculator=MockIndicatorCalculator(),
            signal_generator=MockSignalGenerator(),
            score_calculator=MockScoreCalculator(),
        )

        market_data = {"symbol": "", "price": 50000.0}

        result = analyzer.analyze_pair("", market_data)

        assert isinstance(result, AnalysisResult)
        assert result.symbol == ""

    def test_analyze_pair_processing_time(self):
        """Test temps de traitement"""
        config = AnalyzerConfig(min_signal_confidence=0.6)
        analyzer = TestableAnalyzerV2(
            config=config,
            indicator_calculator=MockIndicatorCalculator(),
            signal_generator=MockSignalGenerator(),
            score_calculator=MockScoreCalculator(),
        )

        now = datetime.utcnow()
        market_data = {
            "symbol": "BTC/USDT",
            "current_price": 50000.0,
            "volume_24h": 1000000.0,
            "timestamp": now.timestamp(),
            "ohlcv_1m": [
                [
                    now.timestamp() - i * 60,
                    50000 - i * 10,
                    50100 - i * 10,
                    49900 - i * 10,
                    50050 - i * 5,
                    1000,
                ]
                for i in range(100)
            ],
            "ohlcv_5m": [
                [
                    now.timestamp() - i * 300,
                    50000 - i * 20,
                    50100 - i * 20,
                    49900 - i * 20,
                    50050 - i * 10,
                    5000,
                ]
                for i in range(50)
            ],
        }

        result = analyzer.analyze_pair("BTC/USDT", market_data)

        assert isinstance(result, AnalysisResult)
        assert result.processing_time_ms is not None
        assert result.processing_time_ms >= 0


class TestTestableAnalyzerV2BatchAnalyze:
    """Tests de la méthode batch_analyze"""

    def test_batch_analyze_success(self):
        """Test analyse batch succès"""
        config = AnalyzerConfig(min_signal_confidence=0.6)
        analyzer = TestableAnalyzerV2(
            config=config,
            indicator_calculator=MockIndicatorCalculator(),
            signal_generator=MockSignalGenerator(),
            score_calculator=MockScoreCalculator(),
        )

        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        market_data = {
            "BTC/USDT": {"price": 50000.0, "volume_24h": 1000000.0},
            "ETH/USDT": {"price": 3000.0, "volume_24h": 500000.0},
            "SOL/USDT": {"price": 100.0, "volume_24h": 200000.0},
        }

        results = analyzer.batch_analyze(symbols, market_data)

        assert isinstance(results, dict)
        assert len(results) == 3
        assert "BTC/USDT" in results
        assert "ETH/USDT" in results
        assert "SOL/USDT" in results

    def test_batch_analyze_partial_failure(self):
        """Test analyse batch échec partiel"""
        config = AnalyzerConfig(min_signal_confidence=0.6)

        class FailingIndicatorCalculator(MockIndicatorCalculator):
            def calculate_all_indicators(self, market_data):
                if market_data.get("symbol") == "ETH/USDT":
                    raise Exception("Erreur ETH")
                return super().calculate_all_indicators(market_data)

        analyzer = TestableAnalyzerV2(
            config=config,
            indicator_calculator=FailingIndicatorCalculator(),
            signal_generator=MockSignalGenerator(),
            score_calculator=MockScoreCalculator(),
        )

        symbols = ["BTC/USDT", "ETH/USDT"]
        market_data = {"BTC/USDT": {"price": 50000.0}, "ETH/USDT": {"price": 3000.0}}

        results = analyzer.batch_analyze(symbols, market_data)

        assert isinstance(results, dict)
        assert len(results) == 2

    def test_batch_analyze_empty_symbols(self):
        """Test analyse batch symboles vides"""
        config = AnalyzerConfig(min_signal_confidence=0.6)
        analyzer = TestableAnalyzerV2(
            config=config,
            indicator_calculator=MockIndicatorCalculator(),
            signal_generator=MockSignalGenerator(),
            score_calculator=MockScoreCalculator(),
        )

        results = analyzer.batch_analyze([], {})

        assert isinstance(results, dict)
        assert len(results) == 0


class TestTestableAnalyzerV2PerformanceMetrics:
    """Tests des métriques de performance"""

    def test_update_performance_metrics(self):
        """Test mise à jour métriques performance"""
        config = AnalyzerConfig(min_signal_confidence=0.6)
        analyzer = TestableAnalyzerV2(
            config=config,
            indicator_calculator=MockIndicatorCalculator(),
            signal_generator=MockSignalGenerator(),
            score_calculator=MockScoreCalculator(),
        )

        now = datetime.utcnow()
        # Simuler plusieurs analyses
        for i in range(5):
            market_data = {
                "symbol": f"BTC{i}/USDT",
                "current_price": 50000.0,
                "volume_24h": 1000000.0,
                "timestamp": now.timestamp(),
                "ohlcv_1m": [
                    [
                        now.timestamp() - j * 60,
                        50000 - j * 10,
                        50100 - j * 10,
                        49900 - j * 10,
                        50050 - j * 5,
                        1000,
                    ]
                    for j in range(100)
                ],
                "ohlcv_5m": [
                    [
                        now.timestamp() - j * 300,
                        50000 - j * 20,
                        50100 - j * 20,
                        49900 - j * 20,
                        50050 - j * 10,
                        5000,
                    ]
                    for j in range(50)
                ],
            }
            analyzer.analyze_pair(f"BTC{i}/USDT", market_data)

        assert analyzer.analysis_count == 5
        assert analyzer.success_count == 5
        assert analyzer.average_processing_time_ms >= 0

    def test_analysis_count_increments(self):
        """Test incrémentation compteur analyses"""
        config = AnalyzerConfig(min_signal_confidence=0.6)
        analyzer = TestableAnalyzerV2(
            config=config,
            indicator_calculator=MockIndicatorCalculator(),
            signal_generator=MockSignalGenerator(),
            score_calculator=MockScoreCalculator(),
        )

        now = datetime.utcnow()
        market_data = {
            "symbol": "BTC/USDT",
            "current_price": 50000.0,
            "volume_24h": 1000000.0,
            "timestamp": now.timestamp(),
            "ohlcv_1m": [
                [
                    now.timestamp() - j * 60,
                    50000 - j * 10,
                    50100 - j * 10,
                    49900 - j * 10,
                    50050 - j * 5,
                    1000,
                ]
                for j in range(100)
            ],
            "ohlcv_5m": [
                [
                    now.timestamp() - j * 300,
                    50000 - j * 20,
                    50100 - j * 20,
                    49900 - j * 20,
                    50050 - j * 10,
                    5000,
                ]
                for j in range(50)
            ],
        }

        analyzer.analyze_pair("BTC/USDT", market_data)
        analyzer.analyze_pair("BTC/USDT", market_data)

        assert analyzer.analysis_count == 2


class TestTestableAnalyzerV2Cache:
    """Tests du cache"""

    def test_indicator_cache(self):
        """Test cache indicateurs"""
        config = AnalyzerConfig(min_signal_confidence=0.6)
        analyzer = TestableAnalyzerV2(
            config=config,
            indicator_calculator=MockIndicatorCalculator(),
            signal_generator=MockSignalGenerator(),
            score_calculator=MockScoreCalculator(),
        )

        market_data = {"symbol": "BTC/USDT", "price": 50000.0}

        # Premier appel
        analyzer.analyze_pair("BTC/USDT", market_data)

        # Vérifier que le cache existe
        assert "_indicator_cache" in analyzer.__dict__
        assert isinstance(analyzer._indicator_cache, dict)


class TestTestableAnalyzerV2MarketContext:
    """Tests du contexte marché"""

    def test_create_market_context(self):
        """Test création contexte marché"""
        config = AnalyzerConfig(min_signal_confidence=0.6)
        analyzer = TestableAnalyzerV2(
            config=config,
            indicator_calculator=MockIndicatorCalculator(),
            signal_generator=MockSignalGenerator(),
            score_calculator=MockScoreCalculator(),
        )

        now = datetime.utcnow()
        market_data = {
            "symbol": "BTC/USDT",
            "current_price": 50000.0,
            "price_change_24h_pct": 2.5,
            "volume_24h": 1000000.0,
            "timestamp": now.timestamp(),
            "ohlcv_1m": [
                [
                    now.timestamp() - i * 60,
                    50000 - i * 10,
                    50100 - i * 10,
                    49900 - i * 10,
                    50050 - i * 5,
                    1000,
                ]
                for i in range(100)
            ],
        }

        context = analyzer._create_market_context("BTC/USDT", market_data)

        assert context is not None
        assert context.symbol == "BTC/USDT"
        assert context.current_price == 50000.0
        assert context.price_change_24h_pct == 2.5
        assert context.volume_24h == 1000000.0

    def test_create_market_context_missing_fields(self):
        """Test contexte marché champs manquants"""
        config = AnalyzerConfig(min_signal_confidence=0.6)
        analyzer = TestableAnalyzerV2(
            config=config,
            indicator_calculator=MockIndicatorCalculator(),
            signal_generator=MockSignalGenerator(),
            score_calculator=MockScoreCalculator(),
        )

        market_data = {"symbol": "BTC/USDT", "price": 50000.0}

        context = analyzer._create_market_context("BTC/USDT", market_data)

        assert context is not None
        assert context.price_change_24h_pct is None
        assert context.volume_24h is None


class TestTestableAnalyzerV2DataQuality:
    """Tests de validation qualité données"""

    def test_validate_data_quality_high(self):
        """Test qualité données élevée"""
        config = AnalyzerConfig(min_signal_confidence=0.6)
        analyzer = TestableAnalyzerV2(
            config=config,
            indicator_calculator=MockIndicatorCalculator(),
            signal_generator=MockSignalGenerator(),
            score_calculator=MockScoreCalculator(),
        )

        now = datetime.utcnow()
        market_data = {
            "symbol": "BTC/USDT",
            "current_price": 50000.0,
            "volume_24h": 1000000.0,
            "timestamp": now.timestamp(),
            "ohlcv_1m": [
                [
                    now.timestamp() - i * 60,
                    50000 - i * 10,
                    50100 - i * 10,
                    49900 - i * 10,
                    50050 - i * 5,
                    1000,
                ]
                for i in range(100)
            ],
            "ohlcv_5m": [
                [
                    now.timestamp() - i * 300,
                    50000 - i * 20,
                    50100 - i * 20,
                    49900 - i * 20,
                    50050 - i * 10,
                    5000,
                ]
                for i in range(50)
            ],
        }

        quality = analyzer.validate_data_quality(market_data)

        assert quality >= 0.8
        assert quality <= 1.0

    def test_validate_data_quality_low(self):
        """Test qualité données faible"""
        config = AnalyzerConfig(min_signal_confidence=0.6)
        analyzer = TestableAnalyzerV2(
            config=config,
            indicator_calculator=MockIndicatorCalculator(),
            signal_generator=MockSignalGenerator(),
            score_calculator=MockScoreCalculator(),
        )

        market_data = {
            "symbol": "BTC/USDT",
            "price": 50000.0,
            # Pas d'ohlcv, pas de volume
        }

        quality = analyzer.validate_data_quality(market_data)

        assert quality < 0.8


class TestTestableAnalyzerV2Config:
    """Tests de configuration"""

    def test_config_min_signal_confidence(self):
        """Test configuration min_signal_confidence"""
        config = AnalyzerConfig(min_signal_confidence=0.8)
        analyzer = TestableAnalyzerV2(
            config=config,
            indicator_calculator=MockIndicatorCalculator(),
            signal_generator=MockSignalGenerator(),
            score_calculator=MockScoreCalculator(),
        )

        assert analyzer.config.min_signal_confidence == 0.8

    def test_config_min_score_threshold(self):
        """Test configuration min_score_threshold"""
        config = AnalyzerConfig(min_score_threshold=5.0)
        analyzer = TestableAnalyzerV2(
            config=config,
            indicator_calculator=MockIndicatorCalculator(),
            signal_generator=MockSignalGenerator(),
            score_calculator=MockScoreCalculator(),
        )

        assert analyzer.config.min_score_threshold == 5.0

    def test_config_rsi_periods(self):
        """Test configuration RSI"""
        config = AnalyzerConfig(rsi_oversold=25.0, rsi_overbought=75.0)
        analyzer = TestableAnalyzerV2(
            config=config,
            indicator_calculator=MockIndicatorCalculator(),
            signal_generator=MockSignalGenerator(),
            score_calculator=MockScoreCalculator(),
        )

        assert analyzer.config.rsi_oversold == 25.0
        assert analyzer.config.rsi_overbought == 75.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
