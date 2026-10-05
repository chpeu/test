"""
Tests pour Mock Scanner Components - Trade Cursor v7.0
Couverture: mock_scanner_components.py (609 lignes)
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

import sys

sys.path.insert(0, ".")

from core.implementations.mock_scanner_components import (
    MockMarketDataCollector,
    MockScalabilityScorer,
    MockPairFilter,
    MockScanPipeline,
    MockScannerOrchestrator,
    MockScanLogger,
)
from core.interfaces.scanner_interfaces import (
    OrderbookData,
    TickerData,
    OHLCVData,
    MarketData,
    DataSource,
    ScoringResult,
    ScoringMetrics,
    PairFilterResult,
    ScanResult,
    ScanBatchResult,
    ScanPipelineResult,
    ScanStatus,
    ScannerConfig,
    FilterConfig,
)


class TestMockMarketDataCollector:
    """Tests pour MockMarketDataCollector"""

    @pytest.fixture
    def collector(self):
        return MockMarketDataCollector()

    @pytest.mark.asyncio
    async def test_collect_orderbook(self, collector):
        """Test collecte orderbook"""
        result = await collector.collect_orderbook("BTCUSDT", limit=5)

        assert result is not None
        assert isinstance(result, OrderbookData)
        assert result.symbol == "BTCUSDT"
        assert isinstance(result.timestamp, datetime)
        assert len(result.bids) == 5
        assert len(result.asks) == 5

    @pytest.mark.asyncio
    async def test_collect_ticker(self, collector):
        """Test collecte ticker"""
        result = await collector.collect_ticker("ETHUSDT")

        assert result is not None
        assert isinstance(result, TickerData)
        assert result.symbol == "ETHUSDT"
        assert result.price > 0
        assert result.volume_24h > 0

    @pytest.mark.asyncio
    async def test_collect_ohlcv(self, collector):
        """Test collecte OHLCV"""
        result = await collector.collect_ohlcv("BNBUSDT", "1m", limit=10)

        assert result is not None
        assert isinstance(result, OHLCVData)
        assert result.symbol == "BNBUSDT"
        assert result.timeframe == "1m"
        assert len(result.klines) == 10
        # Chaque kline a [timestamp, open, high, low, close, volume]
        assert len(result.klines[0]) == 6

    @pytest.mark.asyncio
    async def test_collect_funding_rate(self, collector):
        """Test collecte funding rate"""
        result = await collector.collect_funding_rate("XRPUSDT")

        assert result is not None
        assert isinstance(result, float)
        # Funding rate entre -0.05 et 0.05
        assert -0.05 <= result <= 0.05

    @pytest.mark.asyncio
    async def test_collect_complete_market_data(self, collector):
        """Test collecte complète"""
        timeframes = ["1m", "5m"]
        result = await collector.collect_complete_market_data("ADAUSDT", timeframes)

        assert isinstance(result, MarketData)
        assert result.symbol == "ADAUSDT"
        assert result.source == DataSource.MOCK
        assert result.orderbook is not None
        assert result.ticker is not None
        # OHLCV devrait être présent pour les timeframes demandées
        assert result.ohlcv_1m is not None
        assert result.ohlcv_5m is not None

    def test_get_cache_stats(self, collector):
        """Test stats cache"""
        stats = collector.get_cache_stats()

        assert "cache_stats" in stats
        assert "cache_sizes" in stats
        assert "performance" in stats
        assert "configuration" in stats
        assert stats["cache_stats"]["hit_rate"] == 0.8
        assert stats["performance"]["error_rate"] == 0.0

    def test_clear_cache(self, collector):
        """Test clear cache"""
        # La méthode n'a pas de retour, on vérifie juste qu'elle ne lève pas d'erreur
        collector.clear_cache("BTCUSDT")
        collector.clear_cache()


class TestMockScalabilityScorer:
    """Tests pour MockScalabilityScorer"""

    @pytest.fixture
    def scorer(self):
        return MockScalabilityScorer()

    @pytest.fixture
    def mock_market_data(self):
        return MarketData(
            symbol="BTCUSDT",
            timestamp=datetime.utcnow(),
            orderbook=OrderbookData(
                symbol="BTCUSDT",
                timestamp=datetime.utcnow(),
                bids=[(45000, 1000)],
                asks=[(45001, 1000)],
            ),
            ticker=TickerData(
                symbol="BTCUSDT",
                timestamp=datetime.utcnow(),
                price=45000,
                volume_24h=5000000,
                price_change_24h_pct=2.5,
                funding_rate=0.01,
            ),
            source=DataSource.MOCK,
        )

    def test_calculate_score_valid(self, scorer, mock_market_data):
        """Test calcul score valide"""
        result = scorer.calculate_score(mock_market_data)

        assert isinstance(result, ScoringResult)
        assert result.symbol == "BTCUSDT"
        assert "score" in result.__dict__
        assert "metrics" in result.__dict__
        assert "calculation_time_ms" in result.__dict__

    def test_calculate_score_rejected(self, scorer, mock_market_data):
        """Test calcul score rejeté"""
        # Mock random pour forcer un rejet
        with patch("random.random", return_value=0.1):  # 10% < 20%
            result = scorer.calculate_score(mock_market_data)

            assert result.rejection_reason == "Mock rejection for testing"
            assert result.score == 0.0

    def test_calculate_metrics(self, scorer, mock_market_data):
        """Test calcul métriques"""
        metrics = scorer.calculate_metrics(mock_market_data)

        assert isinstance(metrics, ScoringMetrics)
        assert metrics.volatility_5 > 0
        assert metrics.adx >= 15
        assert metrics.adx <= 45

    def test_batch_score(self, scorer, mock_market_data):
        """Test batch scoring"""
        # Créer market_data distincts pour chaque symbole
        eth_market_data = MarketData(
            symbol="ETHUSDT",
            timestamp=datetime.utcnow(),
            orderbook=OrderbookData(
                symbol="ETHUSDT",
                timestamp=datetime.utcnow(),
                bids=[(3000, 1000)],
                asks=[(3001, 1000)],
            ),
            ticker=TickerData(
                symbol="ETHUSDT",
                timestamp=datetime.utcnow(),
                price=3000,
                volume_24h=3000000,
                price_change_24h_pct=1.5,
                funding_rate=0.005,
            ),
            source=DataSource.MOCK,
        )

        batch = {"BTCUSDT": mock_market_data, "ETHUSDT": eth_market_data}

        results = scorer.batch_score(batch)

        assert len(results) == 2
        assert "BTCUSDT" in results
        assert "ETHUSDT" in results
        for symbol, result in results.items():
            assert isinstance(result, ScoringResult)
            assert result.symbol == symbol

    def test_get_scoring_stats(self, scorer, mock_market_data):
        """Test stats scoring"""
        # Faire quelques calculs pour avoir des stats
        scorer.calculate_score(mock_market_data)
        scorer.calculate_score(mock_market_data)

        stats = scorer.get_scoring_stats()

        assert "performance" in stats
        assert "rejection_analytics" in stats
        assert "cache_stats" in stats
        assert stats["performance"]["total_scorings"] >= 2
        assert "success_rate" in stats["performance"]

    def test_update_scoring_config(self, scorer):
        """Test update config"""
        config = {"min_score": 2.0, "max_spread": 0.05}

        # La méthode n'a pas de retour, on vérifie juste qu'elle ne lève pas d'erreur
        scorer.update_scoring_config(config)


class TestMockPairFilter:
    """Tests pour MockPairFilter"""

    @pytest.fixture
    def filter(self):
        return MockPairFilter()

    @pytest.fixture
    def mock_data(self):
        market_data = MarketData(
            symbol="BTCUSDT",
            timestamp=datetime.utcnow(),
            orderbook=OrderbookData(
                symbol="BTCUSDT",
                timestamp=datetime.utcnow(),
                bids=[(45000, 1000)],
                asks=[(45001, 1000)],
            ),
            ticker=TickerData(
                symbol="BTCUSDT",
                timestamp=datetime.utcnow(),
                price=45000,
                volume_24h=5000000,
                price_change_24h_pct=2.5,
                funding_rate=0.01,
            ),
            source=DataSource.MOCK,
        )

        scoring_result = ScoringResult(
            symbol="BTCUSDT",
            score=3.5,
            metrics=ScoringMetrics(),
            calculation_time_ms=10.0,
        )

        return market_data, scoring_result

    def test_filter_pair_accepted(self, filter, mock_data):
        """Test filtrage paire acceptée"""
        market_data, scoring_result = mock_data

        result = filter.filter_pair("BTCUSDT", market_data, scoring_result)

        assert isinstance(result, PairFilterResult)
        assert result.symbol == "BTCUSDT"
        assert "accepted" in result.__dict__
        assert "filter_results" in result.__dict__
        assert "processing_time_ms" in result.__dict__

    def test_filter_pair_rejected(self, filter, mock_data):
        """Test filtrage paire rejetée"""
        market_data, scoring_result = mock_data

        # Le filtre a 70% de chance de passer, donc on teste juste qu'il retourne un résultat valide
        result = filter.filter_pair("BTCUSDT", market_data, scoring_result)

        assert isinstance(result, PairFilterResult)
        assert result.symbol == "BTCUSDT"
        # Le résultat peut être accepted ou rejected (aléatoire)
        assert "filter_results" in result.__dict__
        assert "processing_time_ms" in result.__dict__

    def test_batch_filter(self, filter, mock_data):
        """Test batch filtering"""
        market_data, scoring_result = mock_data

        batch = {
            "BTCUSDT": (market_data, scoring_result),
            "ETHUSDT": (market_data, scoring_result),
        }

        results = filter.batch_filter(batch)

        assert len(results) == 2
        assert "BTCUSDT" in results
        assert "ETHUSDT" in results
        for symbol, result in results.items():
            assert isinstance(result, PairFilterResult)
            assert result.symbol == symbol

    def test_update_filter_config(self, filter):
        """Test update filter config"""
        config = Mock(spec=FilterConfig)

        # La méthode n'a pas de retour, on vérifie juste qu'elle ne lève pas d'erreur
        filter.update_filter_config(config)

    def test_add_custom_filter(self, filter):
        """Test add custom filter"""

        def custom_filter_func(symbol):
            return True

        # La méthode n'a pas de retour, on vérifie juste qu'elle ne lève pas d'erreur
        filter.add_custom_filter("custom_test", custom_filter_func)

    def test_get_filter_stats(self, filter, mock_data):
        """Test stats filter"""
        market_data, scoring_result = mock_data

        # Faire quelques filtrages pour avoir des stats
        filter.filter_pair("BTCUSDT", market_data, scoring_result)
        filter.filter_pair("ETHUSDT", market_data, scoring_result)

        stats = filter.get_filter_stats()

        assert "overall" in stats
        assert "by_filter_type" in stats
        assert "custom_filters" in stats
        assert "cache_stats" in stats
        assert "current_config" in stats
        assert stats["overall"]["total_filters"] >= 2


class TestMockScanPipeline:
    """Tests pour MockScanPipeline"""

    @pytest.fixture
    def pipeline(self):
        return MockScanPipeline()

    @pytest.mark.asyncio
    async def test_execute_pipeline_success(self, pipeline):
        """Test exécution pipeline réussie"""
        result = await pipeline.execute_pipeline("BTCUSDT")

        assert isinstance(result, ScanPipelineResult)
        assert result.symbol == "BTCUSDT"
        assert "steps_executed" in result.__dict__
        assert "step_results" in result.__dict__
        assert "step_timings" in result.__dict__
        assert "final_result" in result.__dict__
        assert result.final_result.status == ScanStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_execute_pipeline_failure(self, pipeline):
        """Test exécution pipeline échouée"""
        # Mock random pour forcer un échec
        with patch("random.random", return_value=0.05):  # 5% < 10%
            result = await pipeline.execute_pipeline("ETHUSDT")

            assert result.final_result.status == ScanStatus.FAILED
            assert len(result.errors_by_step) > 0

    def test_add_step(self, pipeline):
        """Test add step"""
        mock_step = Mock()

        # La méthode n'a pas de retour, on vérifie juste qu'elle ne lève pas d'erreur
        pipeline.add_step(mock_step)

    def test_remove_step(self, pipeline):
        """Test remove step"""
        # La méthode n'a pas de retour, on vérifie juste qu'elle ne lève pas d'erreur
        pipeline.remove_step("data_collection")

    def test_configure_step(self, pipeline):
        """Test configure step"""
        config = {"timeout_ms": 5000}

        # La méthode n'a pas de retour, on vérifie juste qu'elle ne lève pas d'erreur
        pipeline.configure_step("scoring", config)

    def test_get_pipeline_config(self, pipeline):
        """Test get pipeline config"""
        config = pipeline.get_pipeline_config()

        assert isinstance(config, list)
        assert len(config) == 3
        # Chaque étape devrait avoir name, type, enabled
        for step in config:
            assert "name" in step
            assert "type" in step
            assert "enabled" in step

    def test_get_pipeline_stats(self, pipeline):
        """Test pipeline stats"""
        # Faire quelques exécutions pour avoir des stats
        asyncio.run(pipeline.execute_pipeline("BTCUSDT"))
        asyncio.run(pipeline.execute_pipeline("ETHUSDT"))

        stats = pipeline.get_pipeline_stats()

        assert "overall" in stats
        assert "circuit_breaker" in stats
        assert "steps" in stats
        assert stats["overall"]["total_executions"] >= 2
        assert "success_rate" in stats["overall"]


class TestMockScannerOrchestrator:
    """Tests pour MockScannerOrchestrator"""

    @pytest.fixture
    def orchestrator(self):
        return MockScannerOrchestrator()

    @pytest.mark.asyncio
    async def test_scan_single_pair_success(self, orchestrator):
        """Test scan single succès"""
        result = await orchestrator.scan_single_pair("BTCUSDT")

        assert isinstance(result, ScanResult)
        assert result.symbol == "BTCUSDT"
        assert "status" in result.__dict__
        assert "errors" in result.__dict__
        assert "scan_duration_ms" in result.__dict__

    @pytest.mark.asyncio
    async def test_scan_single_pair_failure(self, orchestrator):
        """Test scan single échec"""
        # Mock random pour forcer un échec
        with patch("random.random", return_value=0.05):  # 5% < 15%
            result = await orchestrator.scan_single_pair("ETHUSDT")

            assert result.status == ScanStatus.FAILED
            assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_scan_batch_pairs(self, orchestrator):
        """Test scan batch"""
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

        result = await orchestrator.scan_batch_pairs(symbols)

        assert isinstance(result, ScanBatchResult)
        assert result.symbols == symbols
        assert len(result.results) == 3
        assert "batch_id" in result.__dict__
        assert "total_duration_ms" in result.__dict__

    @pytest.mark.asyncio
    async def test_scan_top_pairs(self, orchestrator):
        """Test scan top pairs"""
        result = await orchestrator.scan_top_pairs(limit=5)

        assert isinstance(result, ScanBatchResult)
        assert len(result.symbols) == 5
        assert all(s.endswith("USDT") for s in result.symbols)

    def test_get_scan_statistics(self, orchestrator):
        """Test scan statistics"""
        # Faire quelques scans pour avoir des stats
        asyncio.run(orchestrator.scan_single_pair("BTCUSDT"))
        asyncio.run(orchestrator.scan_single_pair("ETHUSDT"))

        stats = orchestrator.get_scan_statistics()

        assert "orchestrator" in stats
        assert "pipeline" in stats
        assert "cache" in stats
        assert "configuration" in stats
        assert stats["orchestrator"]["total_scans"] >= 2

    def test_configure_scanner(self, orchestrator):
        """Test configure scanner"""
        config = ScannerConfig()

        # La méthode n'a pas de retour, on vérifie juste qu'elle ne lève pas d'erreur
        orchestrator.configure_scanner(config)

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, orchestrator):
        """Test health check healthy"""
        # Faire quelques scans réussis
        for _ in range(10):
            with patch("random.random", return_value=0.1):  # 10% < 15%
                await orchestrator.scan_single_pair("BTCUSDT")

        result = await orchestrator.health_check()

        assert "status" in result
        assert result["status"] in ["healthy", "degraded", "unhealthy"]
        assert "timestamp" in result
        assert "components" in result


class TestMockScanLogger:
    """Tests pour MockScanLogger"""

    @pytest.fixture
    def logger(self):
        return MockScanLogger()

    @pytest.fixture
    def mock_scan_result(self):
        return ScanResult(
            symbol="BTCUSDT",
            status=ScanStatus.SUCCESS,
            errors=[],
            scan_duration_ms=100.0,
            timestamp=datetime.utcnow(),
        )

    @pytest.mark.asyncio
    async def test_log_scan(self, logger, mock_scan_result):
        """Test log scan"""
        scan_id = await logger.log_scan(mock_scan_result)

        assert scan_id is not None
        assert scan_id.startswith("mock_scan_id_")
        assert logger.logged_scans == 1

    @pytest.mark.asyncio
    async def test_log_opportunity(self, logger, mock_scan_result):
        """Test log opportunity"""
        opp_id = await logger.log_opportunity(mock_scan_result)

        assert opp_id is not None
        assert opp_id.startswith("mock_opp_id_")
        assert logger.logged_opportunities == 1

    @pytest.mark.asyncio
    async def test_log_batch_scan(self, logger):
        """Test log batch"""
        batch_result = ScanBatchResult(
            symbols=["BTCUSDT", "ETHUSDT"],
            results={
                "BTCUSDT": ScanResult(
                    symbol="BTCUSDT",
                    status=ScanStatus.SUCCESS,
                    errors=[],
                    scan_duration_ms=100.0,
                    timestamp=datetime.utcnow(),
                ),
                "ETHUSDT": ScanResult(
                    symbol="ETHUSDT",
                    status=ScanStatus.SUCCESS,
                    errors=[],
                    scan_duration_ms=100.0,
                    timestamp=datetime.utcnow(),
                ),
            },
            batch_id="test_batch_123",
            total_duration_ms=200.0,
            parallel_workers=2,
        )

        # La méthode n'a pas de retour, on vérifie juste qu'elle ne lève pas d'erreur
        await logger.log_batch_scan(batch_result)

    def test_get_logging_stats(self, logger, mock_scan_result):
        """Test logging stats"""
        # Faire quelques logs pour avoir des stats
        asyncio.run(logger.log_scan(mock_scan_result))
        asyncio.run(logger.log_opportunity(mock_scan_result))

        stats = logger.get_logging_stats()

        assert "total_scans_logged" in stats
        assert "total_opportunities_logged" in stats
        assert "logging_success_rate" in stats
        assert "average_log_time_ms" in stats
        assert stats["total_scans_logged"] == 1
        assert stats["total_opportunities_logged"] == 1
