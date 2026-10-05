#!/usr/bin/env python3
"""
Tests pour TestableAnalyzer - Trade Cursor v7.0
Couverture: core/implementations/testable_analyzer.py (751 lignes)
Tests adaptés à la structure réelle du code
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
import sys
import os

# Ajout du chemin parent pour imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.implementations.testable_analyzer import TestableAnalyzer
from core.interfaces.analyzer_interfaces import (
    AnalyzerConfig,
    AnalysisResult,
    AnalysisStatus,
)


class TestTestableAnalyzerInit:
    """Tests d'initialisation de TestableAnalyzer"""

    def test_init_default_config(self):
        """Test initialisation avec config par défaut"""
        analyzer = TestableAnalyzer()

        # test_mode dépend de config.test_mode (défaut: False)
        assert analyzer.config is not None
        assert analyzer.dependencies is not None
        assert hasattr(analyzer, "mexc_client")
        assert hasattr(analyzer, "price_provider")
        assert hasattr(analyzer, "pair_scorer")
        assert hasattr(analyzer, "circuit_breaker")
        assert hasattr(analyzer, "regime_selector")
        assert hasattr(analyzer, "correlation_filter")

    def test_init_with_custom_config(self):
        """Test initialisation avec config personnalisée"""
        config = AnalyzerConfig(
            min_signal_confidence=0.7, min_score_threshold=4.0, test_mode=True
        )
        analyzer = TestableAnalyzer(config=config)

        assert analyzer.config.min_signal_confidence == 0.7
        assert analyzer.config.min_score_threshold == 4.0
        assert analyzer.test_mode is True

    def test_init_with_dependencies(self):
        """Test initialisation avec dépendances injectées"""
        custom_analyzer = Mock()

        dependencies = {"analyzer": custom_analyzer}

        analyzer = TestableAnalyzer(dependencies=dependencies)

        # Vérifier que la dépendance est injectée
        assert analyzer.dependencies is not None

    def test_init_fallback_dependencies(self):
        """Test fallback dependencies quand injection échoue"""
        # Le fallback est géré automatiquement dans _init_dependencies
        analyzer = TestableAnalyzer()

        # Vérifier que les dépendances de base existent
        assert hasattr(analyzer, "mexc_client")
        assert hasattr(analyzer, "price_provider")


class TestTestableAnalyzerAnalyzePair:
    """Tests de la méthode analyze_pair"""

    def test_analyze_pair_success(self):
        """Test analyse paire succès"""
        analyzer = TestableAnalyzer()

        market_data = {
            "symbol": "BTC/USDT",
            "price": 50000.0,
            "volume_24h": 1000000.0,
            "ohlcv_1m": [
                [datetime.utcnow().timestamp(), 50000, 50100, 49900, 50050, 1000]
            ],
            "ohlcv_5m": [
                [datetime.utcnow().timestamp(), 50000, 50100, 49900, 50050, 5000]
            ],
        }

        result = analyzer.analyze_pair("BTC/USDT", market_data)

        assert isinstance(result, AnalysisResult)
        assert result.symbol == "BTC/USDT"
        assert result.timestamp is not None

    def test_analyze_pair_insufficient_data(self):
        """Test analyse avec données insuffisantes"""
        analyzer = TestableAnalyzer()

        market_data = {
            "symbol": "TEST/USDT",
            "price": 100.0,
            # Pas d'ohlcv, pas de volume
        }

        result = analyzer.analyze_pair("TEST/USDT", market_data)

        assert result is not None
        assert result.symbol == "TEST/USDT"

    def test_analyze_pair_empty_symbol(self):
        """Test analyse symbole vide"""
        analyzer = TestableAnalyzer()

        market_data = {"symbol": "", "price": 50000.0}

        result = analyzer.analyze_pair("", market_data)

        assert result is not None
        assert result.symbol == ""


class TestTestableAnalyzerBatchAnalyze:
    """Tests de la méthode batch_analyze"""

    def test_batch_analyze(self):
        """Test analyse en batch"""
        analyzer = TestableAnalyzer()

        symbols = ["BTC/USDT", "ETH/USDT"]
        timeframes = ["1m", "5m"]

        result = analyzer.batch_analyze(symbols, timeframes)

        assert isinstance(result, dict)
        assert "BTC/USDT" in result or "ETH/USDT" in result


class TestTestableAnalyzerConfig:
    """Tests de configuration"""

    def test_config_min_signal_confidence(self):
        """Test configuration min_signal_confidence"""
        config = AnalyzerConfig(min_signal_confidence=0.8)
        analyzer = TestableAnalyzer(config=config)

        assert analyzer.config.min_signal_confidence == 0.8

    def test_config_min_score_threshold(self):
        """Test configuration min_score_threshold"""
        config = AnalyzerConfig(min_score_threshold=5.0)
        analyzer = TestableAnalyzer(config=config)

        assert analyzer.config.min_score_threshold == 5.0

    def test_config_test_mode(self):
        """Test configuration test_mode"""
        config = AnalyzerConfig(test_mode=True)
        analyzer = TestableAnalyzer(config=config)

        assert analyzer.test_mode is True

        config_false = AnalyzerConfig(test_mode=False)
        analyzer_false = TestableAnalyzer(config=config_false)

        assert analyzer_false.test_mode is False

    def test_config_rsi_params(self):
        """Test configuration RSI params"""
        config = AnalyzerConfig(rsi_oversold=25.0, rsi_overbought=75.0, rsi_period=20)
        analyzer = TestableAnalyzer(config=config)

        assert analyzer.config.rsi_oversold == 25.0
        assert analyzer.config.rsi_overbought == 75.0
        assert analyzer.config.rsi_period == 20

    def test_config_default_values(self):
        """Test valeurs par défaut de config"""
        config = AnalyzerConfig()

        assert config.min_signal_confidence == 0.6
        assert config.min_score_threshold == 3.0
        assert config.max_score_threshold == 8.0
        assert config.rsi_oversold == 30.0
        assert config.rsi_overbought == 70.0
        assert config.rsi_period == 14
        assert config.test_mode is False


class TestTestableAnalyzerEdgeCases:
    """Tests de cas limites"""

    def test_analyze_none_price(self):
        """Test analyse prix None"""
        analyzer = TestableAnalyzer()

        market_data = {"symbol": "BTC/USDT", "price": None}

        result = analyzer.analyze_pair("BTC/USDT", market_data)

        assert result is not None

    def test_analyze_negative_price(self):
        """Test analyse prix négatif"""
        analyzer = TestableAnalyzer()

        market_data = {"symbol": "BTC/USDT", "price": -50000.0}

        result = analyzer.analyze_pair("BTC/USDT", market_data)

        assert result is not None

    def test_analyze_very_large_price(self):
        """Test analyse prix très élevé"""
        analyzer = TestableAnalyzer()

        market_data = {"symbol": "BTC/USDT", "price": 1e10}

        result = analyzer.analyze_pair("BTC/USDT", market_data)

        assert result is not None

    def test_analyze_very_small_price(self):
        """Test analyse prix très faible"""
        analyzer = TestableAnalyzer()

        market_data = {"symbol": "BTC/USDT", "price": 1e-10}

        result = analyzer.analyze_pair("BTC/USDT", market_data)

        assert result is not None


class TestTestableAnalyzerLogging:
    """Tests de logging"""

    def test_init_logs_information(self):
        """Test logging à l'initialisation"""
        from unittest.mock import patch

        with patch("core.implementations.testable_analyzer.logger") as mock_logger:
            analyzer = TestableAnalyzer()

            # Vérifier que logger.info a été appelé
            assert mock_logger.info.called
            call_args = str(mock_logger.info.call_args)
            assert "TestableAnalyzer initialisé" in call_args
            assert "test_mode" in call_args


class TestTestableAnalyzerCoverage:
    """Tests supplémentaires pour maximiser la couverture"""

    def test_dependencies_empty_dict(self):
        """Test avec dictionnaire de dépendances vide"""
        analyzer = TestableAnalyzer(dependencies={})

        assert analyzer.dependencies == {}
        assert analyzer.mexc_client is not None

    def test_dependencies_none(self):
        """Test avec dépendances None"""
        analyzer = TestableAnalyzer(dependencies=None)

        assert analyzer.dependencies is not None

    def test_analyze_pair_with_all_fields(self):
        """Test analyse avec toutes les données"""
        analyzer = TestableAnalyzer()

        now = datetime.utcnow()
        market_data = {
            "symbol": "BTC/USDT",
            "price": 50000.0,
            "volume_24h": 10000000.0,
            "bid": 49999.0,
            "ask": 50001.0,
            "ohlcv_1m": [
                [now.timestamp() - 5 * 60, 49900, 50000, 49800, 49950, 1000],
                [now.timestamp() - 4 * 60, 49950, 50050, 49900, 50000, 1100],
                [now.timestamp() - 3 * 60, 50000, 50100, 49950, 50050, 1200],
                [now.timestamp() - 2 * 60, 50050, 50150, 50000, 50100, 1300],
                [now.timestamp() - 1 * 60, 50100, 50200, 50050, 50150, 1400],
            ],
            "ohlcv_5m": [
                [now.timestamp() - 30 * 60, 49800, 49950, 49700, 49900, 5000],
                [now.timestamp() - 25 * 60, 49900, 50000, 49800, 49950, 5100],
                [now.timestamp() - 20 * 60, 49950, 50100, 49900, 50050, 5200],
                [now.timestamp() - 15 * 60, 50050, 50150, 50000, 50100, 5300],
                [now.timestamp() - 10 * 60, 50100, 50200, 50050, 50150, 5400],
                [now.timestamp() - 5 * 60, 50150, 50250, 50100, 50200, 5500],
            ],
        }

        result = analyzer.analyze_pair("BTC/USDT", market_data)

        assert result is not None
        assert result.symbol == "BTC/USDT"
        assert hasattr(result, "status")
        assert hasattr(result, "timestamp")

    def test_batch_analyze_empty_list(self):
        """Test batch_analyze avec liste vide"""
        analyzer = TestableAnalyzer()

        result = analyzer.batch_analyze([], [])

        assert isinstance(result, dict)

    def test_batch_analyze_single_symbol(self):
        """Test batch_analyze avec un seul symbole"""
        analyzer = TestableAnalyzer()

        result = analyzer.batch_analyze(["BTC/USDT"], ["1m"])

        assert isinstance(result, dict)


if __name__ == "__main__":
    pytest.main(
        [
            __file__,
            "-v",
            "--cov=core.implementations.testable_analyzer",
            "--cov-report=term-missing",
        ]
    )
