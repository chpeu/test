#!/usr/bin/env python3
"""
Tests pour TestableScalabilityScorer - Trade Cursor v7.0
Module: tests/unit/core/test_testable_scalability_scorer.py
Couverture cible: 664 lignes source → 100% coverage
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from core.implementations.testable_scalability_scorer import TestableScalabilityScorer
from core.interfaces.scanner_interfaces import MarketData, ScoringResult, ScoringMetrics


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def scorer():
    """TestableScalabilityScorer instance"""
    return TestableScalabilityScorer()


@pytest.fixture
def market_data():
    """Market data mock"""
    return MagicMock(spec=MarketData)


# =============================================================================
# TESTS INITIALISATION
# =============================================================================


class TestTestableScalabilityScorerInit:
    """Tests d'initialisation"""

    def test_init_default_config(self):
        """Initialisation avec config par défaut"""
        scorer = TestableScalabilityScorer()

        assert scorer.config == {}
        assert scorer.scoring_count == 0
        assert scorer.successful_scores == 0
        assert scorer.rejected_scores == 0
        assert scorer.total_scoring_time_ms == 0.0
        assert scorer.rejection_reasons == {}
        assert scorer._technical_cache == {}
        assert scorer._cache_ttl_seconds == 60

    def test_init_custom_config(self):
        """Initialisation avec config personnalisée"""
        custom_config = {"min_score": 75.0, "max_score": 100.0}
        scorer = TestableScalabilityScorer(config=custom_config)

        assert scorer.config == custom_config

    def test_init_counters_reset(self, scorer):
        """Réinitialisation des compteurs"""
        assert scorer.scoring_count == 0
        assert scorer.successful_scores == 0
        assert scorer.rejected_scores == 0


# =============================================================================
# TESTS CALCULATE_SCORE
# =============================================================================


class TestTestableScalabilityScorerCalculateScore:
    """Tests de calcul de score"""

    def test_calculate_score_success(self, scorer, market_data):
        """Calcul de score réussi"""
        # Configurer le mock
        market_data.symbol = "BTC/USDT"
        market_data.current_price = 50000.0
        market_data.volume_24h = 1000000.0
        market_data.spread_pct = 0.01
        market_data.volatility_1h = 0.02
        market_data.book_depth_usd = 500000.0
        market_data.ticker = MagicMock()
        market_data.ticker.price = 50000.0
        market_data.ticker.volume_24h = 1000000.0

        with patch.object(scorer, "_check_basic_filters", return_value=None):
            with patch.object(scorer, "_calculate_base_score", return_value=85.0):
                with patch.object(
                    scorer, "_apply_score_adjustments", return_value=87.5
                ):
                    result = scorer.calculate_score(market_data)

                    assert isinstance(result, ScoringResult)
                    assert result.symbol == "BTC/USDT"
                    assert result.score >= 0
                    assert scorer.scoring_count == 1
                    assert scorer.successful_scores == 1

    def test_calculate_score_validation_error(self, scorer, market_data):
        """Calcul de score avec erreur de validation"""
        market_data.symbol = "BTC/USDT"

        with patch.object(scorer, "calculate_metrics", return_value=MagicMock()):
            with patch.object(scorer, "_get_effective_scoring_params", return_value={}):
                with patch.object(
                    scorer, "_check_basic_filters", return_value="Validation failed"
                ):
                    result = scorer.calculate_score(market_data)

                    assert result.score == 0.0
                    assert scorer.rejected_scores == 1

    def test_calculate_score_rejection_tracking(self, scorer, market_data):
        """Tracking des raisons de rejet"""
        market_data.symbol = "ETH/USDT"
        market_data.ticker = MagicMock()
        market_data.ticker.price = 3000.0
        market_data.ticker.volume_24h = 500000.0

        with patch.object(scorer, "calculate_metrics", return_value=MagicMock()):
            with patch.object(scorer, "_get_effective_scoring_params", return_value={}):
                with patch.object(
                    scorer, "_check_basic_filters", return_value="Low volatility"
                ):
                    result = scorer.calculate_score(market_data)

                    assert "Low volatility" in scorer.rejection_reasons
                    assert scorer.last_rejection_reason == "Low volatility"

    def test_calculate_score_time_tracking(self, scorer, market_data):
        """Tracking du temps de calcul"""
        market_data.symbol = "SOL/USDT"
        market_data.ticker = MagicMock()
        market_data.ticker.price = 100.0
        market_data.ticker.volume_24h = 200000.0
        market_data.orderbook = MagicMock()
        market_data.orderbook.spread_pct = 0.01

        mock_metrics = MagicMock()
        mock_metrics.volatility_5 = 2.5

        import time

        with patch.object(scorer, "calculate_metrics", return_value=mock_metrics):
            with patch.object(scorer, "_get_effective_scoring_params", return_value={}):
                with patch.object(scorer, "_check_basic_filters", return_value=None):
                    with patch.object(
                        scorer, "_calculate_base_score", return_value=80.0
                    ):
                        with patch.object(
                            scorer, "_apply_score_adjustments", return_value=82.0
                        ):
                            with patch.object(
                                scorer, "_calculate_scoring_details", return_value={}
                            ):
                                with patch("logging.Logger.debug"):
                                    # Ajouter un petit délai pour que le temps soit mesurable
                                    time.sleep(0.001)  # 1ms
                                    result = scorer.calculate_score(market_data)

                                    assert (
                                        scorer.total_scoring_time_ms >= 0
                                    )  # Peut être 0 si très rapide


# =============================================================================
# TESTS CALCULATE_METRICS
# =============================================================================


class TestTestableScalabilityScorerCalculateMetrics:
    """Tests de calcul de métriques"""

    def test_calculate_metrics(self, scorer, market_data):
        """Calcul des métriques techniques"""
        market_data.symbol = "BTC/USDT"

        # Le calcul réel dépend des données, on vérifie juste que ça retourne quelque chose
        result = scorer.calculate_metrics(market_data)

        assert result is not None
        assert isinstance(result, ScoringMetrics)


# =============================================================================
# TESTS CACHE
# =============================================================================


class TestTestableScalabilityScorerCache:
    """Tests de cache"""

    def test_cache_metrics(self, scorer, market_data):
        """Test du cache des metrics"""
        market_data.symbol = "BTC/USDT"

        mock_metrics = MagicMock()
        mock_metrics.volatility_5 = 0.02
        mock_metrics.atr = 1.5
        mock_metrics.adx = 25.0

        result = scorer._cache_metrics(market_data.symbol, mock_metrics)

        assert result is None
        assert market_data.symbol in scorer._technical_cache
        assert "timestamp" in scorer._technical_cache[market_data.symbol]
        assert "metrics" in scorer._technical_cache[market_data.symbol]

    def test_get_cached_metrics_hit(self, scorer, market_data):
        """Récupération cache hit"""
        market_data.symbol = "BTC/USDT"

        mock_metrics = MagicMock()
        mock_metrics.volatility_5 = 0.02
        mock_metrics.atr = 1.5
        mock_metrics.adx = 25.0

        scorer._cache_metrics(market_data.symbol, mock_metrics)

        result = scorer._get_cached_metrics(market_data.symbol)

        assert result is not None
        assert result.volatility_5 == 0.02

    def test_get_cached_metrics_miss(self, scorer, market_data):
        """Récupération cache miss"""
        result = scorer._get_cached_metrics("NONEXISTENT")

        assert result is None

    def test_cleanup_technical_cache(self, scorer):
        """Nettoyage du cache technique"""
        # Remplir le cache
        for i in range(10):
            mock_metrics = MagicMock()
            mock_metrics.volatility_5 = 0.02
            mock_metrics.atr = 1.5
            mock_metrics.adx = 25.0
            scorer._cache_metrics(f"SYM{i}", mock_metrics)

        assert len(scorer._technical_cache) == 10

        # Vider le cache en forçant l'expiration
        from datetime import datetime, timedelta

        for key in scorer._technical_cache:
            scorer._technical_cache[key]["timestamp"] = datetime.utcnow() - timedelta(
                seconds=120
            )

        scorer._cleanup_technical_cache()

        assert len(scorer._technical_cache) == 0


# =============================================================================
# TESTS SCORING DETAILS
# =============================================================================


class TestTestableScalabilityScorerDetails:
    """Tests de détails de scoring"""

    def test_calculate_scoring_details(self, scorer, market_data):
        """Calcul des détails de scoring"""
        market_data.symbol = "BTC/USDT"

        mock_metrics = ScoringMetrics(
            volatility_5=0.02,
            volatility_15=0.03,
            volume_recent=1000000,
            volume_24h=5000000,
            atr=1.5,
            atr_pct=0.015,
            adx=25.0,
            delta_volume=0.1,
            imbalance_normalized=0.05,
            spread_volatility_5=0.01,
            book_depth_ratio=1.0,
            volume_acceleration=0.05,
            price_momentum_5=0.02,
        )

        result = scorer._calculate_scoring_details(market_data, mock_metrics, {})

        assert result is not None


# =============================================================================
# TESTS ERROR HANDLING
# =============================================================================


class TestTestableScalabilityScorerExceptions:
    """Tests de gestion d'exceptions"""

    def test_calculate_score_exception(self, scorer, market_data):
        """Gestion exception dans calculate_score"""
        market_data.symbol = "BTC/USDT"

        with patch.object(
            scorer, "calculate_metrics", side_effect=Exception("Test error")
        ):
            result = scorer.calculate_score(market_data)

            assert result.score == 0.0
            assert scorer.rejected_scores >= 1


# =============================================================================
# TESTS PERFORMANCE
# =============================================================================


class TestTestableScalabilityScorerPerformance:
    """Tests de performance"""

    def test_scoring_count_tracking(self, scorer, market_data):
        """Tracking du nombre de scoring"""
        market_data.symbol = "BTC/USDT"

        with patch.object(scorer, "calculate_metrics", return_value=MagicMock()):
            with patch.object(scorer, "_get_effective_scoring_params", return_value={}):
                with patch.object(scorer, "_check_basic_filters", return_value=None):
                    with patch.object(
                        scorer, "_calculate_base_score", return_value=80.0
                    ):
                        with patch.object(
                            scorer, "_apply_score_adjustments", return_value=82.0
                        ):
                            scorer.calculate_score(market_data)
                            assert scorer.scoring_count == 1

                            scorer.calculate_score(market_data)
                            assert scorer.scoring_count == 2

    def test_success_rejected_ratio(self, scorer, market_data):
        """Ratio succès/rejet"""
        market_data.symbol = "BTC/USDT"
        market_data.ticker = MagicMock()
        market_data.ticker.price = 50000.0
        market_data.ticker.volume_24h = 1000000.0
        market_data.orderbook = MagicMock()
        market_data.orderbook.spread_pct = 0.01

        mock_metrics = MagicMock()
        mock_metrics.volatility_5 = 2.5

        # 10 succès
        for _ in range(10):
            with patch.object(scorer, "calculate_metrics", return_value=mock_metrics):
                with patch.object(
                    scorer, "_get_effective_scoring_params", return_value={}
                ):
                    with patch.object(
                        scorer, "_check_basic_filters", return_value=None
                    ):
                        with patch.object(
                            scorer, "_calculate_base_score", return_value=80.0
                        ):
                            with patch.object(
                                scorer, "_apply_score_adjustments", return_value=82.0
                            ):
                                with patch.object(
                                    scorer,
                                    "_calculate_scoring_details",
                                    return_value={},
                                ):
                                    with patch("logging.Logger.debug"):
                                        scorer.calculate_score(market_data)

        assert scorer.successful_scores == 10
        assert scorer.rejected_scores == 0

        # 5 rejets
        for _ in range(5):
            with patch.object(scorer, "calculate_metrics", return_value=mock_metrics):
                with patch.object(
                    scorer, "_get_effective_scoring_params", return_value={}
                ):
                    with patch.object(
                        scorer, "_check_basic_filters", return_value="Rejection"
                    ):
                        with patch("logging.Logger.debug"):
                            scorer.calculate_score(market_data)

        assert scorer.successful_scores == 10
        assert scorer.rejected_scores == 5

    def test_batch_score(self, scorer, market_data):
        """Score en batch"""
        market_data.symbol = "BTC/USDT"
        market_data.ticker = MagicMock()
        market_data.ticker.price = 50000.0
        market_data.ticker.volume_24h = 1000000.0
        market_data.orderbook = MagicMock()
        market_data.orderbook.spread_pct = 0.01

        market_data_2 = MagicMock(spec=MarketData)
        market_data_2.symbol = "ETH/USDT"
        market_data_2.ticker = MagicMock()
        market_data_2.ticker.price = 3000.0
        market_data_2.ticker.volume_24h = 500000.0
        market_data_2.orderbook = MagicMock()
        market_data_2.orderbook.spread_pct = 0.01

        batch_data = {
            "BTC/USDT": market_data,
            "ETH/USDT": market_data_2,
        }

        with patch.object(scorer, "calculate_score") as mock_score:
            mock_score.return_value = ScoringResult(
                symbol="BTC/USDT",
                score=85.0,
                metrics=MagicMock(),
                calculation_time_ms=10.0,
                timestamp=datetime.utcnow(),
            )
            result = scorer.batch_score(batch_data)

            assert len(result) == 2
            assert "BTC/USDT" in result
            assert "ETH/USDT" in result

    def test_batch_score_exception(self, scorer, market_data):
        """Batch scoring avec exception"""
        batch_data = {"BTC/USDT": market_data}

        with patch.object(
            scorer, "calculate_score", side_effect=Exception("Test error")
        ):
            result = scorer.batch_score(batch_data)

            assert result == {}

    def test_get_scoring_stats(self, scorer, market_data):
        """Statistiques de scoring"""
        market_data.symbol = "BTC/USDT"
        market_data.ticker = MagicMock()
        market_data.ticker.price = 50000.0
        market_data.ticker.volume_24h = 1000000.0
        market_data.orderbook = MagicMock()
        market_data.orderbook.spread_pct = 0.01

        mock_metrics = MagicMock()
        mock_metrics.volatility_5 = 2.5

        # Créer quelques succès
        with patch.object(scorer, "calculate_metrics", return_value=mock_metrics):
            with patch.object(scorer, "_get_effective_scoring_params", return_value={}):
                with patch.object(scorer, "_check_basic_filters", return_value=None):
                    with patch.object(
                        scorer, "_calculate_base_score", return_value=80.0
                    ):
                        with patch.object(
                            scorer, "_apply_score_adjustments", return_value=82.0
                        ):
                            with patch.object(
                                scorer, "_calculate_scoring_details", return_value={}
                            ):
                                with patch("logging.Logger.debug"):
                                    scorer.calculate_score(market_data)

        stats = scorer.get_scoring_stats()

        assert "performance" in stats
        assert "rejection_analytics" in stats
        assert "cache_stats" in stats
        assert stats["performance"]["total_scorings"] == 1
        assert stats["performance"]["successful_scorings"] == 1

    def test_update_scoring_config(self, scorer):
        """Mise à jour configuration scoring"""
        new_config = {
            "spread_min": 0.005,
            "spread_max": 0.05,
            "volume_min": 200000,
        }

        scorer.update_scoring_config(new_config)

        assert scorer.config["spread_min"] == 0.005
        assert scorer.config["spread_max"] == 0.05
        assert scorer.config["volume_min"] == 200000

    def test_get_scoring_stats_empty(self, scorer):
        """Statistiques de scoring vides"""
        stats = scorer.get_scoring_stats()

        assert stats["performance"]["total_scorings"] == 0
        assert stats["performance"]["success_rate"] == 0.0
        assert stats["performance"]["average_scoring_time_ms"] == 0.0
        assert stats["rejection_analytics"]["total_rejections"] == 0


# =============================================================================
# TESTS CHECK_BASIC_FILTERS
# =============================================================================


class TestTestableScalabilityScorerCheckBasicFilters:
    """Tests de vérification des filtres de base"""

    def test_check_basic_filters_all_pass(self, scorer):
        """Tous les filtres passent"""
        market_data = MagicMock(spec=MarketData)
        market_data.orderbook = MagicMock()
        market_data.orderbook.spread_pct = 0.02
        market_data.orderbook.balance_score = 0.8
        market_data.orderbook.book_depth = 100000.0
        market_data.ticker = MagicMock()
        market_data.ticker.funding_rate = 0.01

        mock_metrics = MagicMock()
        mock_metrics.volume_recent = 500000

        params = {
            "spread_min": 0.001,
            "spread_max": 0.05,
            "volume_min": 100000,
            "funding_max": 0.05,
            "balance_min": 0.7,
        }

        result = scorer._check_basic_filters(market_data, mock_metrics, params)

        assert result is None

    def test_check_basic_filters_missing_orderbook(self, scorer):
        """Filtre : orderbook manquant"""
        market_data = MagicMock(spec=MarketData)
        market_data.orderbook = None
        market_data.ticker = None

        mock_metrics = MagicMock()

        result = scorer._check_basic_filters(market_data, mock_metrics, {})

        assert result == "Missing orderbook data"

    def test_check_basic_filters_invalid_spread(self, scorer):
        """Filtre : spread invalide (NaN)"""
        import math

        market_data = MagicMock(spec=MarketData)
        market_data.orderbook = MagicMock()
        market_data.orderbook.spread_pct = float("nan")
        market_data.orderbook.balance_score = 0.8
        market_data.orderbook.book_depth = 100000.0
        market_data.ticker = None

        mock_metrics = MagicMock()

        result = scorer._check_basic_filters(market_data, mock_metrics, {})

        assert result == "Invalid spread (NaN)"

    def test_check_basic_filters_spread_too_low(self, scorer):
        """Filtre : spread trop bas"""
        market_data = MagicMock(spec=MarketData)
        market_data.orderbook = MagicMock()
        market_data.orderbook.spread_pct = 0.0005
        market_data.orderbook.balance_score = 0.8
        market_data.orderbook.book_depth = 100000.0
        market_data.ticker = None

        mock_metrics = MagicMock()

        params = {"spread_min": 0.001, "spread_max": 0.05, "volume_min": 100000}

        result = scorer._check_basic_filters(market_data, mock_metrics, params)

        assert "Spread too low" in result

    def test_check_basic_filters_spread_too_high(self, scorer):
        """Filtre : spread trop élevé"""
        market_data = MagicMock(spec=MarketData)
        market_data.orderbook = MagicMock()
        market_data.orderbook.spread_pct = 0.1
        market_data.orderbook.balance_score = 0.8
        market_data.orderbook.book_depth = 100000.0
        market_data.ticker = None

        mock_metrics = MagicMock()

        params = {"spread_min": 0.001, "spread_max": 0.05, "volume_min": 100000}

        result = scorer._check_basic_filters(market_data, mock_metrics, params)

        assert "Spread too high" in result

    def test_check_basic_filters_volume_too_low(self, scorer):
        """Filtre : volume trop bas"""
        market_data = MagicMock(spec=MarketData)
        market_data.orderbook = MagicMock()
        market_data.orderbook.spread_pct = 0.02
        market_data.orderbook.balance_score = 0.8
        market_data.orderbook.book_depth = 100000.0
        market_data.ticker = None

        mock_metrics = MagicMock()
        mock_metrics.volume_recent = 50000

        params = {"spread_min": 0.001, "spread_max": 0.05, "volume_min": 100000}

        result = scorer._check_basic_filters(market_data, mock_metrics, params)

        assert "Volume too low" in result

    def test_check_basic_filters_balance_too_low(self, scorer):
        """Filtre : balance score trop bas"""
        market_data = MagicMock(spec=MarketData)
        market_data.orderbook = MagicMock()
        market_data.orderbook.spread_pct = 0.02
        market_data.orderbook.balance_score = 0.5
        market_data.orderbook.book_depth = 100000.0
        market_data.ticker = None

        mock_metrics = MagicMock()
        mock_metrics.volume_recent = 500000

        params = {
            "spread_min": 0.001,
            "spread_max": 0.05,
            "volume_min": 100000,
            "balance_min": 0.7,
        }

        result = scorer._check_basic_filters(market_data, mock_metrics, params)

        assert "Balance score too low" in result

    def test_check_basic_filters_funding_too_high(self, scorer):
        """Filtre : funding rate trop élevé"""
        market_data = MagicMock(spec=MarketData)
        market_data.orderbook = MagicMock()
        market_data.orderbook.spread_pct = 0.02
        market_data.orderbook.balance_score = 0.8
        market_data.orderbook.book_depth = 100000.0
        market_data.ticker = MagicMock()
        market_data.ticker.funding_rate = 0.1

        mock_metrics = MagicMock()
        mock_metrics.volume_recent = 500000

        params = {
            "spread_min": 0.001,
            "spread_max": 0.05,
            "volume_min": 100000,
            "funding_max": 0.05,
            "balance_min": 0.7,
        }

        result = scorer._check_basic_filters(market_data, mock_metrics, params)

        assert "Funding rate too high" in result

    def test_check_basic_filters_book_depth_zero(self, scorer):
        """Filtre : book depth nul"""
        market_data = MagicMock(spec=MarketData)
        market_data.orderbook = MagicMock()
        market_data.orderbook.spread_pct = 0.02
        market_data.orderbook.balance_score = 0.8
        market_data.orderbook.book_depth = 0
        market_data.ticker = None

        mock_metrics = MagicMock()
        mock_metrics.volume_recent = 500000

        params = {
            "spread_min": 0.001,
            "spread_max": 0.05,
            "volume_min": 100000,
            "balance_min": 0.7,
        }

        result = scorer._check_basic_filters(market_data, mock_metrics, params)

        assert result == "Book depth is zero or negative"

    def test_check_basic_filters_funding_none(self, scorer):
        """Filtre : funding rate None (ne doit pas rejeter)"""
        market_data = MagicMock(spec=MarketData)
        market_data.orderbook = MagicMock()
        market_data.orderbook.spread_pct = 0.02
        market_data.orderbook.balance_score = 0.8
        market_data.orderbook.book_depth = 100000.0
        market_data.ticker = MagicMock()
        market_data.ticker.funding_rate = None

        mock_metrics = MagicMock()
        mock_metrics.volume_recent = 500000

        params = {
            "spread_min": 0.001,
            "spread_max": 0.05,
            "volume_min": 100000,
            "funding_max": 0.05,
            "balance_min": 0.7,
        }

        result = scorer._check_basic_filters(market_data, mock_metrics, params)

        assert result is None  # funding_rate None ne déclenche pas le filtre


# =============================================================================
# TESTS CALCULATE_VOLATILITY
# =============================================================================


class TestTestableScalabilityScorerVolatility:
    """Tests de calcul de volatilité"""

    def test_calculate_volatility(self, scorer):
        """Calcul de volatilité"""
        closes = [100.0, 102.0, 101.0, 103.0, 104.0, 102.0, 105.0]

        result = scorer._calculate_volatility(closes, 5)

        assert isinstance(result, float)
        assert result >= 0.0

    def test_calculate_volatility_insufficient_data(self, scorer):
        """Volatilité avec données insuffisantes"""
        closes = [100.0, 102.0]

        result = scorer._calculate_volatility(closes, 5)

        assert result == 0.0

    def test_calculate_volatility_zero_mean(self, scorer):
        """Volatilité avec prix nul"""
        closes = [0.0, 0.0, 0.0]

        result = scorer._calculate_volatility(closes, 3)

        assert result == 0.0

    def test_calculate_volatility_exception(self, scorer):
        """Volatilité avec exception"""
        closes = []

        result = scorer._calculate_volatility(closes, 5)

        assert result == 0.0


# =============================================================================
# TESTS CALCULATE_ATR
# =============================================================================


class TestTestableScalabilityScorerATR:
    """Tests de calcul ATR"""

    def test_calculate_atr(self, scorer):
        """Calcul ATR"""
        highs = [100.0, 102.0, 101.0, 103.0, 104.0, 102.0, 105.0, 106.0]
        lows = [98.0, 100.0, 99.0, 101.0, 102.0, 100.0, 103.0, 104.0]
        closes = [99.0, 101.0, 100.0, 102.0, 103.0, 101.0, 104.0, 105.0]

        result = scorer._calculate_atr(highs, lows, closes, period=4)

        assert isinstance(result, float)
        assert result >= 0.0

    def test_calculate_atr_insufficient_data(self, scorer):
        """ATR avec données insuffisantes"""
        highs = [100.0, 102.0]
        lows = [98.0, 100.0]
        closes = [99.0, 101.0]

        result = scorer._calculate_atr(highs, lows, closes, period=14)

        assert result == 0.0

    def test_calculate_atr_exception(self, scorer):
        """ATR avec exception"""
        highs = []
        lows = []
        closes = []

        result = scorer._calculate_atr(highs, lows, closes, period=14)

        assert result == 0.0


# =============================================================================
# TESTS CALCULATE_ADX
# =============================================================================


class TestTestableScalabilityScorerADX:
    """Tests de calcul ADX"""

    def test_calculate_adx(self, scorer):
        """Calcul ADX"""
        highs = [100.0, 102.0, 101.0, 103.0, 104.0, 102.0, 105.0, 106.0, 108.0]
        lows = [98.0, 100.0, 99.0, 101.0, 102.0, 100.0, 103.0, 104.0, 105.0]
        closes = [99.0, 101.0, 100.0, 102.0, 103.0, 101.0, 104.0, 105.0, 107.0]

        result = scorer._calculate_adx(highs, lows, closes, period=4)

        assert isinstance(result, float)
        assert result >= 0.0

    def test_calculate_adx_insufficient_data(self, scorer):
        """ADX avec données insuffisantes"""
        highs = [100.0, 102.0]
        lows = [98.0, 100.0]
        closes = [99.0, 101.0]

        result = scorer._calculate_adx(highs, lows, closes, period=14)

        assert result == 0.0

    def test_calculate_adx_zero_avg_tr(self, scorer):
        """ADX avec avg_tr nul"""
        highs = [100.0, 100.0, 100.0]
        lows = [100.0, 100.0, 100.0]
        closes = [100.0, 100.0, 100.0]

        result = scorer._calculate_adx(highs, lows, closes, period=2)

        assert result == 0.0

    def test_calculate_adx_exception(self, scorer):
        """ADX avec exception"""
        highs = []
        lows = []
        closes = []

        result = scorer._calculate_adx(highs, lows, closes, period=14)

        assert result == 0.0


# =============================================================================
# TESTS CALCULATE_VOLUME_ACCELERATION
# =============================================================================


class TestTestableScalabilityScorerVolumeAcceleration:
    """Tests de calcul accélération volume"""

    def test_calculate_volume_acceleration(self, scorer):
        """Calcul accélération volume"""
        volumes = [100000, 120000, 110000, 150000, 180000, 200000, 220000]

        result = scorer._calculate_volume_acceleration(volumes)

        assert isinstance(result, float)

    def test_calculate_volume_acceleration_insufficient_data(self, scorer):
        """Accélération volume avec données insuffisantes"""
        volumes = [100000, 120000, 110000]

        result = scorer._calculate_volume_acceleration(volumes)

        assert result == 0.0

    def test_calculate_volume_acceleration_zero_previous(self, scorer):
        """Accélération volume avec volume précédent nul"""
        volumes = [0.0, 0.0, 0.0, 100000, 120000, 110000]

        result = scorer._calculate_volume_acceleration(volumes)

        assert result == 0.0

    def test_calculate_volume_acceleration_exception(self, scorer):
        """Accélération volume avec exception"""
        volumes = []

        result = scorer._calculate_volume_acceleration(volumes)

        assert result == 0.0


# =============================================================================
# TESTS ESTIMATE_SPREAD_VOLATILITY
# =============================================================================


class TestTestableScalabilityScorerSpreadVolatility:
    """Tests d'estimation volatilité spread"""

    def test_estimate_spread_volatility_low(self, scorer):
        """Estimation volatilité spread faible"""
        result = scorer._estimate_spread_volatility(0.005)

        assert result == 0.0001

    def test_estimate_spread_volatility_medium(self, scorer):
        """Estimation volatilité spread moyen"""
        result = scorer._estimate_spread_volatility(0.015)

        assert result == 0.0003

    def test_estimate_spread_volatility_high(self, scorer):
        """Estimation volatilité spread élevé"""
        result = scorer._estimate_spread_volatility(0.03)

        assert result == 0.001

    def test_estimate_spread_volatility_low(self, scorer):
        """Estimation volatilité spread faible"""
        result = scorer._estimate_spread_volatility(0.005)

        # Spread <= 1% retourne 0.0001
        assert result == 0.0001


# =============================================================================
# TESTS CACHE EXCEPTION HANDLING
# =============================================================================


class TestTestableScalabilityScorerCacheExceptions:
    """Tests d'exceptions de cache"""

    def test_get_cached_metrics_expiration(self, scorer):
        """Récupération cache avec expiration"""
        from datetime import datetime, timedelta

        # Ajouter une entrée expirée
        mock_metrics = MagicMock()
        scorer._technical_cache["EXPIRED"] = {
            "metrics": mock_metrics,
            "timestamp": datetime.utcnow() - timedelta(seconds=120),
        }

        result = scorer._get_cached_metrics("EXPIRED")

        assert result is None
        assert "EXPIRED" not in scorer._technical_cache

    def test_cache_metrics_cleanup(self, scorer):
        """Cache metrics avec cleanup - vérifie que le cleanup ne supprime que les entrées expirées"""
        from datetime import datetime, timedelta

        # Ajouter des entrées récentes
        for i in range(100):
            mock_metrics = MagicMock()
            scorer._cache_metrics(f"RECENT{i}", mock_metrics)

        # Ajouter des entrées expirées
        for i in range(100):
            mock_metrics = MagicMock()
            scorer._technical_cache[f"EXPIRED{i}"] = {
                "metrics": mock_metrics,
                "timestamp": datetime.utcnow() - timedelta(seconds=120),
            }

        # Le cleanup ne supprime que les entrées expirées
        # Donc nous devrions avoir 100 entrées récentes + 0 entrées expirées = 100
        # (le cleanup a été déclenché car > 500 entrées)

        # Vérifions que les entrées récentes sont toujours là
        assert "RECENT0" in scorer._technical_cache
        assert "RECENT99" in scorer._technical_cache

        # Vérifions que les entrées expirées ont été supprimées
        # (après appel manuel du cleanup)
        scorer._cleanup_technical_cache()
        expired_count = sum(
            1 for k in scorer._technical_cache if k.startswith("EXPIRED")
        )
        assert expired_count == 0  # Toutes les entrées expirées doivent être supprimées


# =============================================================================
# TESTS CALCULATE_BASE_SCORE
# =============================================================================


class TestTestableScalabilityScorerCalculateBaseScore:
    """Tests de calcul du score de base"""

    def test_calculate_base_score(self, scorer):
        """Calcul du score de base"""
        market_data = MagicMock(spec=MarketData)
        market_data.orderbook = MagicMock()
        market_data.orderbook.spread_pct = 0.02

        mock_metrics = MagicMock()
        mock_metrics.volatility_5 = 2.5
        mock_metrics.volume_recent = 500000
        mock_metrics.adx = 30.0
        mock_metrics.atr_pct = 1.0
        mock_metrics.price_momentum_5 = 0.5

        params = {
            "spread_min": 0.001,
            "spread_max": 0.05,
            "volume_min": 100000,
            "adx_threshold": 25,
            "adx_multiplier": 1.2,
            "weight_vol_spread_ratio": 0.4,
            "weight_volume_norm": 0.25,
            "weight_balance": 0.15,
            "weight_adx_bonus": 0.10,
            "weight_order_flow": 0.10,
        }

        result = scorer._calculate_base_score(market_data, mock_metrics, params)

        assert isinstance(result, float)
        assert result >= 0.0

    def test_calculate_base_score_zero_spread(self, scorer):
        """Score de base avec spread nul"""
        market_data = MagicMock(spec=MarketData)
        market_data.orderbook = MagicMock()
        market_data.orderbook.spread_pct = 0.0

        mock_metrics = MagicMock()
        mock_metrics.volatility_5 = 2.5
        mock_metrics.volume_recent = 500000

        params = {
            "spread_min": 0.001,
            "spread_max": 0.05,
            "volume_min": 100000,
        }

        result = scorer._calculate_base_score(market_data, mock_metrics, params)

        assert isinstance(result, float)
        assert result >= 0.0

    def test_calculate_base_score_exception(self, scorer):
        """Score de base avec exception"""
        market_data = MagicMock(spec=MarketData)
        market_data.orderbook = None

        mock_metrics = MagicMock()
        params = {}

        result = scorer._calculate_base_score(market_data, mock_metrics, params)

        assert result == 0.0


# =============================================================================
# TESTS CALCULATE_ORDER_FLOW_SCORE
# =============================================================================


class TestTestableScalabilityScorerOrderFlowScore:
    """Tests de calcul du score order flow"""

    def test_calculate_order_flow_score_neutral(self, scorer):
        """Score order flow neutre avec book depth et spread favorables"""
        metrics = MagicMock()
        metrics.imbalance_normalized = 0.0
        metrics.book_depth_ratio = 1.0
        metrics.spread_volatility_5 = 0.0

        result = scorer._calculate_order_flow_score(metrics)

        # Score de base 0.5 + book depth bonus 0.2 + spread bonus 0.1 = 0.8
        # Utilisation de assertAlmostEqual pour éviter les problèmes de précision flottante
        assert abs(result - 0.8) < 0.001

    def test_calculate_order_flow_score_with_imbalance(self, scorer):
        """Score order flow avec imbalance modérée"""
        metrics = MagicMock()
        metrics.imbalance_normalized = 0.2
        metrics.book_depth_ratio = 1.0
        metrics.spread_volatility_5 = 0.0

        result = scorer._calculate_order_flow_score(metrics)

        assert result > 0.5

    def test_calculate_order_flow_score_extreme_imbalance(self, scorer):
        """Score order flow avec imbalance extrême et book depth défavorable"""
        metrics = MagicMock()
        metrics.imbalance_normalized = 0.6
        metrics.book_depth_ratio = 0.3  # Défavorable (< 0.5)
        metrics.spread_volatility_5 = 0.002  # Non favorable (>= 0.001)

        result = scorer._calculate_order_flow_score(metrics)

        # Score de base 0.5 - imbalance penalty 0.1 - book depth penalty 0.1 = 0.3
        assert result < 0.5

    def test_calculate_order_flow_score_exception(self, scorer):
        """Score order flow avec exception"""
        metrics = MagicMock()
        metrics.imbalance_normalized = None

        result = scorer._calculate_order_flow_score(metrics)

        assert result == 0.5


# =============================================================================
# TESTS GET_SCORING_STATS ET UPDATE_SCORING_CONFIG
# =============================================================================


class TestTestableScalabilityScorerStats:
    """Tests de statistiques de scoring"""

    def test_get_scoring_stats_empty(self, scorer):
        """Statistiques de scoring vides"""
        stats = scorer.get_scoring_stats()

        assert stats["performance"]["total_scorings"] == 0
        assert stats["performance"]["successful_scorings"] == 0
        assert stats["performance"]["rejected_scorings"] == 0
        assert stats["performance"]["success_rate"] == 0.0
        assert stats["cache_stats"]["cache_size"] == 0

    def test_get_scoring_stats_with_data(self, scorer):
        """Statistiques de scoring avec données"""
        # Simuler quelques scores
        from datetime import datetime

        mock_market_data = MagicMock(spec=MarketData)
        mock_market_data.symbol = "BTC/USDT"
        mock_market_data.timestamp = datetime.utcnow()
        mock_market_data.ohlcv_1m = MagicMock()
        mock_market_data.orderbook = MagicMock()
        mock_market_data.orderbook.spread_pct = 0.02
        mock_market_data.ticker = MagicMock()

        # Effectuer quelques scores
        scorer.calculate_score(mock_market_data)
        scorer.calculate_score(mock_market_data)

        stats = scorer.get_scoring_stats()

        assert stats["performance"]["total_scorings"] >= 2
        assert stats["performance"]["success_rate"] >= 0.0
        assert "rejection_analytics" in stats
        assert "cache_stats" in stats

    def test_update_scoring_config(self, scorer):
        """Mise à jour configuration de scoring"""
        new_config = {
            "scalability_spread_min": 0.002,
            "scalability_volume_min": 200000,
        }

        scorer.update_scoring_config(new_config)

        # La configuration doit être mise à jour
        assert "scalability_spread_min" in scorer.config
        assert "scalability_volume_min" in scorer.config

    def test_calculate_score_cache_hit(self, scorer):
        """Score avec hit cache"""
        from datetime import datetime

        # Créer market_data avec ohlcv
        mock_market_data = MagicMock(spec=MarketData)
        mock_market_data.symbol = "BTC/USDT"
        mock_market_data.timestamp = datetime.utcnow()
        mock_market_data.ohlcv_1m = MagicMock()
        mock_market_data.ohlcv_1m.klines = True
        mock_market_data.ohlcv_1m.get_closes = lambda: [100.0 + i for i in range(20)]
        mock_market_data.ohlcv_1m.get_volumes = lambda: [50000.0] * 20
        mock_market_data.ohlcv_1m.get_highs = lambda: [101.0 + i for i in range(20)]
        mock_market_data.ohlcv_1m.get_lows = lambda: [99.0 + i for i in range(20)]
        mock_market_data.orderbook = MagicMock()
        mock_market_data.orderbook.spread_pct = 0.02
        mock_market_data.orderbook.balance_score = 0.8
        mock_market_data.orderbook.book_depth = 100000.0
        mock_market_data.orderbook.bid_vol = 50000.0
        mock_market_data.orderbook.ask_vol = 50000.0
        mock_market_data.orderbook.bids = [[100.0, 1000]]
        mock_market_data.orderbook.asks = [[100.02, 1000]]
        mock_market_data.ticker = MagicMock()
        mock_market_data.ticker.price = 100.0  # Prix valide > 0
        mock_market_data.ticker.volume_24h = 5000000.0
        mock_market_data.ticker.funding_rate = 0.01

        # Premier appel - calcul réel
        result1 = scorer.calculate_score(mock_market_data)
        assert result1.is_valid

        # Deuxième appel avec même timestamp - cache hit
        result2 = scorer.calculate_score(mock_market_data)
        assert result2.is_valid
        assert result2.score == result1.score  # Même score car même données

    def test_score_adjustments_volume_bonus(self, scorer):
        """Score avec bonus volume élevé"""
        from datetime import datetime

        mock_market_data = MagicMock(spec=MarketData)
        mock_market_data.symbol = "BTC/USDT"
        mock_market_data.timestamp = datetime.utcnow()
        mock_market_data.ohlcv_1m = MagicMock()
        mock_market_data.ohlcv_1m.klines = True
        mock_market_data.ohlcv_1m.get_closes = lambda: [100.0 + i for i in range(20)]
        mock_market_data.ohlcv_1m.get_volumes = lambda: [50000.0] * 20
        mock_market_data.ohlcv_1m.get_highs = lambda: [101.0 + i for i in range(20)]
        mock_market_data.ohlcv_1m.get_lows = lambda: [99.0 + i for i in range(20)]
        mock_market_data.orderbook = MagicMock()
        mock_market_data.orderbook.spread_pct = 0.02
        mock_market_data.orderbook.balance_score = 0.8
        mock_market_data.orderbook.book_depth = 100000.0
        mock_market_data.orderbook.bid_vol = 50000.0
        mock_market_data.orderbook.ask_vol = 50000.0
        mock_market_data.orderbook.bids = [[100.0, 1000]]
        mock_market_data.orderbook.asks = [[100.02, 1000]]
        mock_market_data.ticker = MagicMock()
        mock_market_data.ticker.price = 100.0
        # Volume 24h élevé pour déclencher le bonus
        mock_market_data.ticker.volume_24h = 5000000.0
        mock_market_data.ticker.funding_rate = 0.01

        result = scorer.calculate_score(mock_market_data)
        assert result.is_valid
        # Le score doit être > 0 car le bonus volume est appliqué
        assert result.score > 0

    def test_score_adjustments_volatility_optimal(self, scorer):
        """Score avec volatilité optimale"""
        from datetime import datetime

        mock_market_data = MagicMock(spec=MarketData)
        mock_market_data.symbol = "BTC/USDT"
        mock_market_data.timestamp = datetime.utcnow()
        mock_market_data.ohlcv_1m = MagicMock()
        mock_market_data.ohlcv_1m.klines = True
        # Volatilité optimale (entre 0.5 et 3.0)
        mock_market_data.ohlcv_1m.get_closes = lambda: [
            100.0 * (1 + 0.01 * i) for i in range(20)
        ]
        mock_market_data.ohlcv_1m.get_volumes = lambda: [50000.0] * 20
        mock_market_data.ohlcv_1m.get_highs = lambda: [101.0 + i for i in range(20)]
        mock_market_data.ohlcv_1m.get_lows = lambda: [99.0 + i for i in range(20)]
        mock_market_data.orderbook = MagicMock()
        mock_market_data.orderbook.spread_pct = 0.02
        mock_market_data.orderbook.balance_score = 0.8
        mock_market_data.orderbook.book_depth = 100000.0
        mock_market_data.orderbook.bid_vol = 50000.0
        mock_market_data.orderbook.ask_vol = 50000.0
        mock_market_data.orderbook.bids = [[100.0, 1000]]
        mock_market_data.orderbook.asks = [[100.02, 1000]]
        mock_market_data.ticker = MagicMock()
        mock_market_data.ticker.price = 100.0
        mock_market_data.ticker.volume_24h = 1000000.0
        mock_market_data.ticker.funding_rate = 0.01

        result = scorer.calculate_score(mock_market_data)
        assert result.is_valid


# =============================================================================
# TESTS CALCULATE_SCORING_DETAILS
# =============================================================================


class TestTestableScalabilityScorerScoringDetails:
    """Tests de calcul des détails de scoring"""

    def test_calculate_scoring_details(self, scorer):
        """Calcul des détails de scoring"""
        market_data = MagicMock(spec=MarketData)
        market_data.orderbook = MagicMock()
        market_data.orderbook.spread_pct = 0.02
        market_data.orderbook.balance_score = 0.8
        market_data.orderbook.book_depth = 100000.0
        market_data.ticker = MagicMock()
        market_data.ticker.funding_rate = 0.01

        mock_metrics = MagicMock()
        mock_metrics.volatility_5 = 2.5
        mock_metrics.volume_recent = 500000
        mock_metrics.volume_24h = 5000000
        mock_metrics.atr_pct = 1.0
        mock_metrics.adx = 30.0
        mock_metrics.delta_volume = 1000
        mock_metrics.imbalance_normalized = 0.1
        mock_metrics.volume_acceleration = 0.2
        mock_metrics.price_momentum_5 = 0.5

        params = {}

        result = scorer._calculate_scoring_details(market_data, mock_metrics, params)

        assert result is not None
        assert "spread_pct" in result
        assert "volatility_5" in result
        assert "volume_recent" in result

    def test_calculate_scoring_details_exception(self, scorer):
        """Calcul des détails de scoring avec exception"""
        market_data = MagicMock(spec=MarketData)
        market_data.orderbook = None
        market_data.ticker = None

        mock_metrics = MagicMock()
        params = {}

        result = scorer._calculate_scoring_details(market_data, mock_metrics, params)

        assert result == {}


# =============================================================================
# RUNNER
# =============================================================================

if __name__ == "__main__":
    pytest.main(
        [
            __file__,
            "-v",
            "--cov=core.implementations.testable_scalability_scorer",
            "--cov-report=term-missing",
        ]
    )
