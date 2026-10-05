#!/usr/bin/env python3
"""
Tests pour TestableMarketDataCollector - Trade Cursor v7.0
Couverture: core/implementations/testable_market_data_collector.py (690 lignes)
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import sys
import os

# Ajout du chemin parent pour imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.implementations.testable_market_data_collector import (
    TestableMarketDataCollector,
)
from core.interfaces.scanner_interfaces import (
    OrderbookData,
    TickerData,
    OHLCVData,
    MarketData,
    DataSource,
)


class TestTestableMarketDataCollectorInit:
    """Tests d'initialisation"""

    def test_init_default(self):
        """Test initialisation avec valeurs par défaut"""
        collector = TestableMarketDataCollector()

        assert collector.cache_ttl_seconds == 30
        assert collector.max_cache_size == 1000
        assert collector.max_retries == 2
        assert collector.retry_delay_ms == 500
        assert collector.collection_count == 0
        assert collector.cache_hits == 0
        assert collector.cache_misses == 0
        assert collector.error_count == 0

    def test_init_custom_config(self):
        """Test initialisation avec configuration personnalisée"""
        collector = TestableMarketDataCollector(
            cache_ttl_seconds=60, max_cache_size=2000
        )

        assert collector.cache_ttl_seconds == 60
        assert collector.max_cache_size == 2000

    def test_init_with_client(self):
        """Test initialisation avec client"""
        mock_client = Mock()
        collector = TestableMarketDataCollector(client=mock_client)

        assert collector.client is mock_client


class TestTestableMarketDataCollectorOrderbook:
    """Tests collecte orderbook"""

    @pytest.mark.asyncio
    async def test_collect_orderbook_success(self):
        """Test collecte orderbook succès"""
        collector = TestableMarketDataCollector()

        # Mock client
        mock_client = AsyncMock()
        mock_client.fetch_order_book = AsyncMock(
            return_value={
                "bids": [[100.0, 1000.0], [99.9, 2000.0], [99.8, 3000.0]],
                "asks": [[100.1, 1500.0], [100.2, 2500.0], [100.3, 3500.0]],
            }
        )
        collector.client = mock_client

        result = await collector.collect_orderbook("BTC/USDT", limit=5)

        assert result is not None
        assert isinstance(result, OrderbookData)
        assert result.symbol == "BTC/USDT"
        assert len(result.bids) == 3
        assert len(result.asks) == 3
        assert collector.collection_count == 1

    @pytest.mark.asyncio
    async def test_collect_orderbook_cache_hit(self):
        """Test collecte orderbook avec cache hit"""
        collector = TestableMarketDataCollector()

        # Mock client
        mock_client = AsyncMock()
        mock_client.fetch_order_book = AsyncMock(
            return_value={"bids": [[100.0, 1000.0]], "asks": [[100.1, 1500.0]]}
        )
        collector.client = mock_client

        # Première collecte (cache miss)
        await collector.collect_orderbook("BTC/USDT", limit=5)

        # Deuxième collecte (cache hit)
        result = await collector.collect_orderbook("BTC/USDT", limit=5)

        assert result is not None
        assert collector.cache_hits == 1
        assert collector.cache_misses == 1

    @pytest.mark.asyncio
    async def test_collect_orderbook_invalid_symbol(self):
        """Test collecte orderbook symbole invalide"""
        collector = TestableMarketDataCollector()

        result = await collector.collect_orderbook("", limit=5)

        assert result is None

    @pytest.mark.asyncio
    async def test_collect_orderbook_no_client(self):
        """Test collecte orderbook sans client"""
        collector = TestableMarketDataCollector()
        collector.client = None

        result = await collector.collect_orderbook("BTC/USDT", limit=5)

        assert result is None


class TestTestableMarketDataCollectorTicker:
    """Tests collecte ticker"""

    @pytest.mark.asyncio
    async def test_collect_ticker_success(self):
        """Test collecte ticker succès"""
        collector = TestableMarketDataCollector()

        # Mock client
        mock_client = AsyncMock()
        mock_client.exchange.fetch_ticker = AsyncMock(
            return_value={
                "last": 50000.0,
                "close": 50000.0,
                "quoteVolume": 1000000.0,
                "baseVolume": 20.0,
                "change": 1000.0,
                "percentage": 2.0,
                "high": 51000.0,
                "low": 49000.0,
            }
        )
        collector.client = mock_client

        result = await collector.collect_ticker("BTC/USDT")

        assert result is not None
        assert isinstance(result, TickerData)
        assert result.symbol == "BTC/USDT"
        assert result.price == 50000.0
        assert result.volume_24h == 1000000.0
        assert collector.collection_count == 1

    @pytest.mark.asyncio
    async def test_collect_ticker_cache_hit(self):
        """Test collecte ticker avec cache hit"""
        collector = TestableMarketDataCollector()

        # Mock client
        mock_client = AsyncMock()
        mock_client.exchange.fetch_ticker = AsyncMock(
            return_value={"last": 50000.0, "quoteVolume": 1000000.0}
        )
        collector.client = mock_client

        # Première collecte (cache miss)
        await collector.collect_ticker("BTC/USDT")

        # Deuxième collecte (cache hit)
        result = await collector.collect_ticker("BTC/USDT")

        assert result is not None
        assert collector.cache_hits == 1

    @pytest.mark.asyncio
    async def test_collect_ticker_invalid_symbol(self):
        """Test collecte ticker symbole invalide"""
        collector = TestableMarketDataCollector()

        result = await collector.collect_ticker("")

        assert result is None

    @pytest.mark.asyncio
    async def test_collect_ticker_no_client(self):
        """Test collecte ticker sans client"""
        collector = TestableMarketDataCollector()
        collector.client = None

        result = await collector.collect_ticker("BTC/USDT")

        assert result is None


class TestTestableMarketDataCollectorOHLCV:
    """Tests collecte OHLCV"""

    @pytest.mark.asyncio
    async def test_collect_ohlcv_success(self):
        """Test collecte OHLCV succès"""
        collector = TestableMarketDataCollector()

        # Mock client
        mock_client = AsyncMock()
        mock_klines = [
            [datetime.utcnow().timestamp() - i * 60, 50000, 50100, 49900, 50050, 1000]
            for i in range(30)
        ]
        mock_client.fetch_ohlcv = AsyncMock(return_value=mock_klines)
        collector.client = mock_client

        result = await collector.collect_ohlcv("BTC/USDT", "1m", limit=30)

        assert result is not None
        assert isinstance(result, OHLCVData)
        assert result.symbol == "BTC/USDT"
        assert result.timeframe == "1m"
        assert len(result.klines) == 30
        assert collector.collection_count == 1

    @pytest.mark.asyncio
    async def test_collect_ohlcv_cache_hit(self):
        """Test collecte OHLCV avec cache hit"""
        collector = TestableMarketDataCollector()

        # Mock client - retourner une liste brute (format attendu par fetch_ohlcv)
        mock_client = AsyncMock()
        now = datetime.utcnow()
        mock_klines = [
            [now.timestamp() - i * 60, 50000, 50100, 49900, 50050, 1000]
            for i in range(30)
        ]
        mock_client.fetch_ohlcv = AsyncMock(return_value=mock_klines)
        collector.client = mock_client

        # Première collecte (cache miss)
        result1 = await collector.collect_ohlcv("BTC/USDT", "1m", limit=30)

        # Deuxième collecte (cache hit)
        result2 = await collector.collect_ohlcv("BTC/USDT", "1m", limit=30)

        assert result1 is not None
        assert result2 is not None
        assert collector.cache_hits == 1

    @pytest.mark.asyncio
    async def test_collect_ohlcv_invalid_timeframe(self):
        """Test collecte OHLCV timeframe invalide"""
        collector = TestableMarketDataCollector()

        result = await collector.collect_ohlcv("BTC/USDT", "invalid", limit=30)

        assert result is None

    @pytest.mark.asyncio
    async def test_collect_ohlcv_invalid_symbol(self):
        """Test collecte OHLCV symbole invalide"""
        collector = TestableMarketDataCollector()

        result = await collector.collect_ohlcv("", "1m", limit=30)

        assert result is None

    @pytest.mark.asyncio
    async def test_collect_ohlcv_insufficient_data(self):
        """Test collecte OHLCV données insuffisantes"""
        collector = TestableMarketDataCollector()

        # Mock client avec peu de données
        mock_client = AsyncMock()
        mock_client.fetch_ohlcv = AsyncMock(
            return_value=[
                [datetime.utcnow().timestamp(), 50000, 50100, 49900, 50050, 1000]
            ]
        )
        collector.client = mock_client

        result = await collector.collect_ohlcv("BTC/USDT", "1m", limit=30)

        assert result is None


class TestTestableMarketDataCollectorFunding:
    """Tests collecte funding rate"""

    @pytest.mark.asyncio
    async def test_collect_funding_rate_success(self):
        """Test collecte funding rate succès"""
        collector = TestableMarketDataCollector()

        # Mock client
        mock_client = AsyncMock()
        mock_client.exchange.fetch_funding_rate = AsyncMock(
            return_value={"fundingRate": 0.0001}
        )
        collector.client = mock_client

        result = await collector.collect_funding_rate("BTC/USDT")

        assert result is not None
        assert isinstance(result, float)
        assert collector.collection_count == 1

    @pytest.mark.asyncio
    async def test_collect_funding_rate_cache_hit(self):
        """Test collecte funding rate avec cache hit"""
        collector = TestableMarketDataCollector()

        # Mock client
        mock_client = AsyncMock()
        mock_client.exchange.fetch_funding_rate = AsyncMock(
            return_value={"fundingRate": 0.0001}
        )
        collector.client = mock_client

        # Première collecte (cache miss)
        await collector.collect_funding_rate("BTC/USDT")

        # Deuxième collecte (cache hit)
        result = await collector.collect_funding_rate("BTC/USDT")

        assert result is not None
        assert collector.cache_hits == 1

    @pytest.mark.asyncio
    async def test_collect_funding_rate_invalid_symbol(self):
        """Test collecte funding rate symbole invalide"""
        collector = TestableMarketDataCollector()

        result = await collector.collect_funding_rate("")

        assert result is None

    @pytest.mark.asyncio
    async def test_collect_funding_rate_no_client(self):
        """Test collecte funding rate sans client"""
        collector = TestableMarketDataCollector()
        collector.client = None

        result = await collector.collect_funding_rate("BTC/USDT")

        assert result is None


class TestTestableMarketDataCollectorComplete:
    """Tests collecte complète"""

    @pytest.mark.asyncio
    async def test_collect_complete_market_data(self):
        """Test collecte complète des données de marché"""
        collector = TestableMarketDataCollector()

        # Mock client
        mock_client = AsyncMock()
        now = datetime.utcnow()
        mock_client.fetch_order_book = AsyncMock(
            return_value={"bids": [[100.0, 1000.0]], "asks": [[100.1, 1500.0]]}
        )
        mock_client.exchange.fetch_ticker = AsyncMock(
            return_value={"last": 100.0, "quoteVolume": 1000000.0}
        )
        # Retourner une liste brute (format attendu par fetch_ohlcv)
        mock_klines_1m = [
            [now.timestamp() - i * 60, 100, 101, 99, 100, 1000] for i in range(30)
        ]
        mock_klines_5m = [
            [now.timestamp() - i * 300, 100, 101, 99, 100, 1000] for i in range(30)
        ]
        mock_client.fetch_ohlcv = AsyncMock(
            side_effect=lambda sym, tf, limit=30: mock_klines_1m
            if tf == "1m"
            else mock_klines_5m
        )
        mock_client.exchange.fetch_funding_rate = AsyncMock(
            return_value={"fundingRate": 0.0001}
        )
        collector.client = mock_client

        result = await collector.collect_complete_market_data("BTC/USDT", ["1m", "5m"])

        assert result is not None
        assert isinstance(result, MarketData)
        assert result.symbol == "BTC/USDT"
        assert result.orderbook is not None
        assert result.ticker is not None
        assert result.ohlcv_1m is not None
        assert result.ohlcv_5m is not None
        assert result.data_quality is not None

    @pytest.mark.asyncio
    async def test_collect_complete_market_data_partial_failure(self):
        """Test collecte complète avec échecs partiels"""
        collector = TestableMarketDataCollector()

        # Mock client qui échoue partiellement
        mock_client = AsyncMock()
        mock_client.fetch_order_book = AsyncMock(
            return_value={"bids": [[100.0, 1000.0]], "asks": [[100.1, 1500.0]]}
        )
        mock_client.exchange.fetch_ticker = AsyncMock(
            side_effect=Exception("Ticker error")
        )
        mock_client.fetch_ohlcv = AsyncMock(
            return_value=[[datetime.utcnow().timestamp(), 100, 101, 99, 100, 1000]]
        )
        mock_client.exchange.fetch_funding_rate = AsyncMock(
            return_value={"fundingRate": 0.0001}
        )
        collector.client = mock_client

        result = await collector.collect_complete_market_data("BTC/USDT", ["1m"])

        assert result is not None
        assert result.symbol == "BTC/USDT"
        assert result.orderbook is not None
        # Ticker peut être None en cas d'erreur


class TestTestableMarketDataCollectorCache:
    """Tests gestion du cache"""

    def test_get_cache_stats(self):
        """Test statistiques du cache"""
        collector = TestableMarketDataCollector()

        stats = collector.get_cache_stats()

        assert "cache_stats" in stats
        assert "cache_sizes" in stats
        assert "performance" in stats
        assert "configuration" in stats
        assert stats["cache_stats"]["total_requests"] == 0
        assert stats["performance"]["total_collections"] == 0

    def test_clear_cache_all(self):
        """Test vidage complet du cache"""
        collector = TestableMarketDataCollector()

        # Ajouter des données au cache
        collector._orderbook_cache["BTC/USDT"] = {
            "data": "mock",
            "timestamp": datetime.utcnow(),
        }
        collector._ticker_cache["BTC/USDT"] = {
            "data": "mock",
            "timestamp": datetime.utcnow(),
        }

        collector.clear_cache()

        assert len(collector._orderbook_cache) == 0
        assert len(collector._ticker_cache) == 0
        assert len(collector._ohlcv_cache) == 0
        assert len(collector._funding_cache) == 0

    def test_clear_cache_symbol(self):
        """Test vidage du cache pour un symbole"""
        collector = TestableMarketDataCollector()

        # Ajouter des données au cache
        collector._orderbook_cache["BTC/USDT"] = {
            "data": "mock",
            "timestamp": datetime.utcnow(),
        }
        collector._orderbook_cache["ETH/USDT"] = {
            "data": "mock",
            "timestamp": datetime.utcnow(),
        }
        collector._ticker_cache["BTC/USDT"] = {
            "data": "mock",
            "timestamp": datetime.utcnow(),
        }

        collector.clear_cache("BTC/USDT")

        assert "BTC/USDT" not in collector._orderbook_cache
        assert "ETH/USDT" in collector._orderbook_cache
        assert "BTC/USDT" not in collector._ticker_cache


class TestTestableMarketDataCollectorEdgeCases:
    """Tests de cas limites"""

    @pytest.mark.asyncio
    async def test_collect_orderbook_empty_bids_asks(self):
        """Test collecte orderbook avec bids/asks vides"""
        collector = TestableMarketDataCollector()

        # Mock client
        mock_client = AsyncMock()
        mock_client.fetch_order_book = AsyncMock(return_value={"bids": [], "asks": []})
        collector.client = mock_client

        result = await collector.collect_orderbook("BTC/USDT", limit=5)

        assert result is not None
        assert len(result.bids) == 0
        assert len(result.asks) == 0

    @pytest.mark.asyncio
    async def test_collect_ticker_missing_fields(self):
        """Test collecte ticker avec champs manquants"""
        collector = TestableMarketDataCollector()

        # Mock client avec données minimales
        mock_client = AsyncMock()
        mock_client.exchange.fetch_ticker = AsyncMock(
            return_value={"last": 100.0, "quoteVolume": 1000000.0}
        )
        collector.client = mock_client

        result = await collector.collect_ticker("BTC/USDT")

        assert result is not None
        assert result.price == 100.0
        assert result.volume_24h == 1000000.0

    @pytest.mark.asyncio
    async def test_collect_ohlcv_few_candles(self):
        """Test collecte OHLCV avec peu de bougies"""
        collector = TestableMarketDataCollector()

        # Mock client avec peu de données
        mock_client = AsyncMock()
        mock_client.fetch_ohlcv = AsyncMock(
            return_value=[[datetime.utcnow().timestamp(), 100, 101, 99, 100, 1000]]
        )
        collector.client = mock_client

        result = await collector.collect_ohlcv("BTC/USDT", "1m", limit=30)

        assert result is None  # Moins de 10 bougies = rejeté

    @pytest.mark.asyncio
    async def test_collection_count_increments(self):
        """Test incrémentation du compteur de collectes"""
        collector = TestableMarketDataCollector()

        # Mock client
        mock_client = AsyncMock()
        mock_client.fetch_order_book = AsyncMock(
            return_value={"bids": [[100.0, 1000.0]], "asks": [[100.1, 1500.0]]}
        )
        collector.client = mock_client

        await collector.collect_orderbook("BTC/USDT")
        assert collector.collection_count == 1

        await collector.collect_orderbook("ETH/USDT")
        assert collector.collection_count == 2

    @pytest.mark.asyncio
    async def test_error_count_increments(self):
        """Test incrémentation du compteur d'erreurs"""
        collector = TestableMarketDataCollector()

        # Mock client qui échoue
        mock_client = AsyncMock()
        mock_client.fetch_order_book = AsyncMock(side_effect=Exception("Test error"))
        collector.client = mock_client

        result = await collector.collect_orderbook("BTC/USDT")

        assert result is None
        assert collector.error_count == 1


class TestTestableMarketDataCollectorCoverage:
    """Tests supplémentaires pour maximiser la couverture"""

    def test_cache_hit_rate_calculation(self):
        """Test calcul du taux de hit du cache"""
        collector = TestableMarketDataCollector()

        # Simuler des hits et misses
        collector.cache_hits = 80
        collector.cache_misses = 20

        stats = collector.get_cache_stats()

        assert stats["cache_stats"]["hit_rate"] == 0.8

    def test_error_rate_calculation(self):
        """Test calcul du taux d'erreur"""
        collector = TestableMarketDataCollector()

        collector.collection_count = 100
        collector.error_count = 5

        stats = collector.get_cache_stats()

        assert stats["performance"]["error_rate"] == 0.05

    def test_average_collection_time_calculation(self):
        """Test calcul du temps moyen de collecte"""
        collector = TestableMarketDataCollector()

        collector.collection_count = 10
        collector.total_collection_time_ms = 500.0

        stats = collector.get_cache_stats()

        assert stats["performance"]["average_collection_time_ms"] == 50.0

    def test_clear_cache_with_ohlcv_keys(self):
        """Test vidage cache avec clés OHLCV"""
        collector = TestableMarketDataCollector()

        # Ajouter des clés OHLCV avec préfixe symbole
        collector._ohlcv_cache["BTC/USDT_1m"] = {
            "data": "mock",
            "timestamp": datetime.utcnow(),
        }
        collector._ohlcv_cache["BTC/USDT_5m"] = {
            "data": "mock",
            "timestamp": datetime.utcnow(),
        }
        collector._ohlcv_cache["ETH/USDT_1m"] = {
            "data": "mock",
            "timestamp": datetime.utcnow(),
        }

        collector.clear_cache("BTC/USDT")

        assert "BTC/USDT_1m" not in collector._ohlcv_cache
        assert "BTC/USDT_5m" not in collector._ohlcv_cache
        assert "ETH/USDT_1m" in collector._ohlcv_cache


if __name__ == "__main__":
    pytest.main(
        [
            __file__,
            "-v",
            "--cov=core.implementations.testable_market_data_collector",
            "--cov-report=term-missing",
        ]
    )
