#!/usr/bin/env python3
"""
Tests pour TestablePairFilter - Trade Cursor v7.0 Phase 3
Couverture: core/implementations/testable_pair_filter.py (599 lignes)
Tests adaptés à la structure réelle du code
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
import sys
import os
import math

# Ajout du chemin parent pour imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.implementations.testable_pair_filter import TestablePairFilter
from core.interfaces.scanner_interfaces import (
    MarketData,
    ScoringResult,
    ScoringMetrics,
    FilterConfig,
    PairFilterResult,
    OrderbookData,
    TickerData,
    DataSource,
)


class TestTestablePairFilterInit:
    """Tests d'initialisation de TestablePairFilter"""

    def test_init_default_config(self):
        """Test initialisation avec config par défaut"""
        filter_obj = TestablePairFilter()

        assert filter_obj.config is not None
        assert filter_obj.filter_count == 0
        assert filter_obj.passed_count == 0
        assert filter_obj.failed_count == 0
        assert filter_obj._filter_cache == {}
        assert "spread" in filter_obj.filter_stats
        assert "volume" in filter_obj.filter_stats
        assert "funding" in filter_obj.filter_stats

    def test_init_with_custom_config(self):
        """Test initialisation avec config personnalisée"""
        config = FilterConfig(
            min_spread=0.01,
            max_spread=0.1,
            min_volume=500000,
            max_funding_rate=0.1,
            min_balance_score=0.8,
            require_zero_fees=False,
        )

        filter_obj = TestablePairFilter(config=config)

        assert filter_obj.config.min_spread == 0.01
        assert filter_obj.config.max_spread == 0.1
        assert filter_obj.config.min_volume == 500000
        assert filter_obj.config.max_funding_rate == 0.1
        assert filter_obj.config.min_balance_score == 0.8
        assert filter_obj.config.require_zero_fees is False

    def test_init_custom_filters_empty(self):
        """Test initialisation sans filtres personnalisés"""
        filter_obj = TestablePairFilter()

        assert filter_obj.custom_filters == {}


class TestTestablePairFilterSpread:
    """Tests du filtre de spread"""

    def test_spread_filter_valid(self):
        """Test spread valide"""
        filter_obj = TestablePairFilter()

        market_data = TestablePairFilterHelper._create_market_data(spread_pct=0.03)
        scoring_result = TestablePairFilterHelper._create_scoring_result()

        result = filter_obj.filter_pair("BTC/USDT", market_data, scoring_result)

        assert result.filter_results["spread"] is True
        assert "spread" not in result.rejection_reasons

    def test_spread_filter_too_low(self):
        """Test spread trop bas"""
        filter_obj = TestablePairFilter()

        market_data = TestablePairFilterHelper._create_market_data(
            spread_pct=0.0005
        )  # Trop bas
        scoring_result = TestablePairFilterHelper._create_scoring_result()

        result = filter_obj.filter_pair("BTC/USDT", market_data, scoring_result)

        assert result.filter_results["spread"] is False
        assert any("spread" in reason.lower() for reason in result.rejection_reasons)

    def test_spread_filter_too_high(self):
        """Test spread trop élevé"""
        filter_obj = TestablePairFilter()

        market_data = TestablePairFilterHelper._create_market_data(
            spread_pct=0.5
        )  # Trop haut
        scoring_result = TestablePairFilterHelper._create_scoring_result()

        result = filter_obj.filter_pair("BTC/USDT", market_data, scoring_result)

        assert result.filter_results["spread"] is False
        assert any("spread" in reason.lower() for reason in result.rejection_reasons)

    def test_spread_filter_nan(self):
        """Test spread NaN"""
        filter_obj = TestablePairFilter()

        market_data = TestablePairFilterHelper._create_market_data(
            spread_pct=float("nan")
        )
        scoring_result = TestablePairFilterHelper._create_scoring_result()

        result = filter_obj.filter_pair("BTC/USDT", market_data, scoring_result)

        assert result.filter_results["spread"] is False
        assert any("nan" in reason.lower() for reason in result.rejection_reasons)

    def test_spread_filter_missing_data(self):
        """Test spread données manquantes"""
        filter_obj = TestablePairFilter()

        market_data = TestablePairFilterHelper._create_market_data(spread_pct="missing")
        scoring_result = TestablePairFilterHelper._create_scoring_result()

        result = filter_obj.filter_pair("BTC/USDT", market_data, scoring_result)

        assert result.filter_results["spread"] is False
        assert any("missing" in reason.lower() for reason in result.rejection_reasons)


class TestTestablePairFilterVolume:
    """Tests du filtre de volume"""

    def test_volume_filter_valid(self):
        """Test volume valide"""
        filter_obj = TestablePairFilter()

        market_data = TestablePairFilterHelper._create_market_data()
        scoring_result = TestablePairFilterHelper._create_scoring_result(
            volume_recent=500000
        )

        result = filter_obj.filter_pair("BTC/USDT", market_data, scoring_result)

        assert result.filter_results["volume"] is True

    def test_volume_filter_too_low(self):
        """Test volume trop bas"""
        filter_obj = TestablePairFilter()

        market_data = TestablePairFilterHelper._create_market_data()
        scoring_result = TestablePairFilterHelper._create_scoring_result(
            volume_recent=10000
        )  # Trop bas

        result = filter_obj.filter_pair("BTC/USDT", market_data, scoring_result)

        assert result.filter_results["volume"] is False
        assert any("volume" in reason.lower() for reason in result.rejection_reasons)


class TestTestablePairFilterFunding:
    """Tests du filtre de funding rate"""

    def test_funding_filter_valid(self):
        """Test funding rate valide"""
        filter_obj = TestablePairFilter()

        market_data = TestablePairFilterHelper._create_market_data(funding_rate=0.01)
        scoring_result = TestablePairFilterHelper._create_scoring_result()

        result = filter_obj.filter_pair("BTC/USDT", market_data, scoring_result)

        assert result.filter_results["funding"] is True

    def test_funding_filter_too_high(self):
        """Test funding rate trop élevé"""
        filter_obj = TestablePairFilter()

        market_data = TestablePairFilterHelper._create_market_data(
            funding_rate=0.15
        )  # Trop élevé
        scoring_result = TestablePairFilterHelper._create_scoring_result()

        result = filter_obj.filter_pair("BTC/USDT", market_data, scoring_result)

        assert result.filter_results["funding"] is False
        assert any("funding" in reason.lower() for reason in result.rejection_reasons)

    def test_funding_filter_missing(self):
        """Test funding rate manquant (non bloquant)"""
        filter_obj = TestablePairFilter()

        market_data = TestablePairFilterHelper._create_market_data(funding_rate=None)
        scoring_result = TestablePairFilterHelper._create_scoring_result()

        result = filter_obj.filter_pair("BTC/USDT", market_data, scoring_result)

        # Funding rate manquant n'est pas bloquant
        assert result.filter_results["funding"] is True


class TestTestablePairFilterBalance:
    """Tests du filtre de balance score"""

    def test_balance_filter_valid(self):
        """Test balance score valide"""
        filter_obj = TestablePairFilter()

        market_data = TestablePairFilterHelper._create_market_data(balance_score=0.85)
        scoring_result = TestablePairFilterHelper._create_scoring_result()

        result = filter_obj.filter_pair("BTC/USDT", market_data, scoring_result)

        assert result.filter_results["balance"] is True

    def test_balance_filter_too_low(self):
        """Test balance score trop bas"""
        filter_obj = TestablePairFilter()

        market_data = TestablePairFilterHelper._create_market_data(
            balance_score=0.5
        )  # Trop bas
        scoring_result = TestablePairFilterHelper._create_scoring_result()

        result = filter_obj.filter_pair("BTC/USDT", market_data, scoring_result)

        assert result.filter_results["balance"] is False
        assert any("balance" in reason.lower() for reason in result.rejection_reasons)


class TestTestablePairFilterWhitelist:
    """Tests des filtres whitelist/blacklist"""

    def test_whitelist_include(self):
        """Test whitelist - inclusion"""
        config = FilterConfig(symbol_whitelist=["BTC/USDT", "ETH/USDT"])
        filter_obj = TestablePairFilter(config=config)

        market_data = TestablePairFilterHelper._create_market_data()
        scoring_result = TestablePairFilterHelper._create_scoring_result()

        result = filter_obj.filter_pair("BTC/USDT", market_data, scoring_result)

        assert result.accepted is True

    def test_whitelist_exclude(self):
        """Test whitelist - exclusion"""
        config = FilterConfig(symbol_whitelist=["BTC/USDT", "ETH/USDT"])
        filter_obj = TestablePairFilter(config=config)

        market_data = TestablePairFilterHelper._create_market_data()
        scoring_result = TestablePairFilterHelper._create_scoring_result()

        result = filter_obj.filter_pair("SOL/USDT", market_data, scoring_result)

        assert result.accepted is False
        assert any("whitelist" in reason.lower() for reason in result.rejection_reasons)

    def test_blacklist_exclude(self):
        """Test blacklist - exclusion"""
        config = FilterConfig(symbol_blacklist=["BTC/USDT"])
        filter_obj = TestablePairFilter(config=config)

        market_data = TestablePairFilterHelper._create_market_data()
        scoring_result = TestablePairFilterHelper._create_scoring_result()

        result = filter_obj.filter_pair("BTC/USDT", market_data, scoring_result)

        assert result.accepted is False
        assert any("blacklist" in reason.lower() for reason in result.rejection_reasons)


class TestTestablePairFilterCustom:
    """Tests des filtres personnalisés"""

    def test_add_custom_filter(self):
        """Test ajout filtre personnalisé"""
        filter_obj = TestablePairFilter()

        def custom_filter(symbol, market_data, scoring_result):
            return symbol.startswith("BTC")

        filter_obj.add_custom_filter("btc_only", custom_filter)

        assert "btc_only" in filter_obj.custom_filters

    def test_add_custom_filter_invalid(self):
        """Test ajout filtre invalide"""
        filter_obj = TestablePairFilter()

        with pytest.raises(ValueError):
            filter_obj.add_custom_filter("invalid", "not a function")

    def test_custom_filter_applied(self):
        """Test application filtre personnalisé"""
        filter_obj = TestablePairFilter()

        def reject_all(symbol, market_data, scoring_result):
            return False

        filter_obj.add_custom_filter("reject_all", reject_all)

        market_data = TestablePairFilterHelper._create_market_data()
        scoring_result = TestablePairFilterHelper._create_scoring_result()

        result = filter_obj.filter_pair("BTC/USDT", market_data, scoring_result)

        assert result.accepted is False


class TestTestablePairFilterBatch:
    """Tests du filtrage en batch"""

    def test_batch_filter_empty(self):
        """Test batch vide"""
        filter_obj = TestablePairFilter()

        result = filter_obj.batch_filter({})

        assert result == {}

    def test_batch_filter_multiple(self):
        """Test batch multiple paires"""
        filter_obj = TestablePairFilter()

        data_batch = {
            "BTC/USDT": (
                TestablePairFilterHelper._create_market_data(),
                TestablePairFilterHelper._create_scoring_result(),
            ),
            "ETH/USDT": (
                TestablePairFilterHelper._create_market_data(),
                TestablePairFilterHelper._create_scoring_result(),
            ),
            "SOL/USDT": (
                TestablePairFilterHelper._create_market_data(),
                TestablePairFilterHelper._create_scoring_result(),
            ),
        }

        result = filter_obj.batch_filter(data_batch)

        assert len(result) == 3
        assert "BTC/USDT" in result
        assert "ETH/USDT" in result
        assert "SOL/USDT" in result


class TestTestablePairFilterConfig:
    """Tests de configuration"""

    def test_update_filter_config(self):
        """Test mise à jour configuration"""
        filter_obj = TestablePairFilter()

        new_config = FilterConfig(min_spread=0.02, max_spread=0.2)
        filter_obj.update_filter_config(new_config)

        assert filter_obj.config.min_spread == 0.02
        assert filter_obj.config.max_spread == 0.2

    def test_update_config_clears_cache(self):
        """Test mise à jour configuration vide le cache"""
        filter_obj = TestablePairFilter()

        # Ajouter entrées au cache
        filter_obj._filter_cache["test_key"] = {"result": "test"}

        new_config = FilterConfig()
        filter_obj.update_filter_config(new_config)

        assert len(filter_obj._filter_cache) == 0


class TestTestablePairFilterStats:
    """Tests des statistiques"""

    def test_get_filter_stats_empty(self):
        """Test statistiques vides"""
        filter_obj = TestablePairFilter()

        stats = filter_obj.get_filter_stats()

        assert stats["overall"]["total_filters"] == 0
        assert stats["overall"]["success_rate"] == 0.0
        assert stats["overall"]["average_filter_time_ms"] == 0.0

    def test_get_filter_stats_with_data(self):
        """Test statistiques avec données"""
        filter_obj = TestablePairFilter()

        # Simuler filtrages
        for _ in range(10):
            market_data = TestablePairFilterHelper._create_market_data()
            scoring_result = TestablePairFilterHelper._create_scoring_result()
            filter_obj.filter_pair("BTC/USDT", market_data, scoring_result)

        stats = filter_obj.get_filter_stats()

        assert stats["overall"]["total_filters"] == 10
        assert stats["overall"]["success_rate"] >= 0.0
        assert stats["overall"]["success_rate"] <= 1.0


class TestTestablePairFilterCache:
    """Tests du cache de filtrage"""

    def test_cache_hit(self):
        """Test hit du cache"""
        filter_obj = TestablePairFilter()
        filter_obj._cache_ttl_seconds = 3600  # 1 heure pour test

        market_data = TestablePairFilterHelper._create_market_data()
        scoring_result = TestablePairFilterHelper._create_scoring_result()

        # Premier filtrage
        result1 = filter_obj.filter_pair("BTC/USDT", market_data, scoring_result)

        # Second filtrage (doit utiliser le cache)
        result2 = filter_obj.filter_pair("BTC/USDT", market_data, scoring_result)

        assert result1.accepted == result2.accepted

    def test_cache_size(self):
        """Test taille du cache"""
        filter_obj = TestablePairFilter()

        for i in range(5):
            market_data = TestablePairFilterHelper._create_market_data()
            scoring_result = TestablePairFilterHelper._create_scoring_result()
            filter_obj.filter_pair(f"SYMBOL_{i}", market_data, scoring_result)

        assert len(filter_obj._filter_cache) > 0


class TestTestablePairFilterEdgeCases:
    """Tests de cas limites"""

    def test_filter_exception_handling(self):
        """Test gestion exception"""
        filter_obj = TestablePairFilter()

        # Créer données invalides
        market_data = MarketData(
            symbol="BTC/USDT",
            timestamp=datetime.utcnow(),
            orderbook=None,
            ticker=None,
            source=DataSource.MOCK,
        )
        scoring_result = ScoringResult(
            symbol="BTC/USDT", score=0.0, metrics=ScoringMetrics()
        )

        result = filter_obj.filter_pair("BTC/USDT", market_data, scoring_result)

        # Doit retourner un résultat même en cas d'erreur
        assert result.symbol == "BTC/USDT"
        assert result.timestamp is not None

    def test_filter_all_criteria_fail(self):
        """Test échec tous critères"""
        filter_obj = TestablePairFilter()

        # Données qui échouent tous les filtres
        market_data = TestablePairFilterHelper._create_market_data(
            spread_pct=0.0001,  # Spread trop bas
            balance_score=0.1,  # Balance trop bas
        )
        scoring_result = TestablePairFilterHelper._create_scoring_result(
            volume_recent=1000
        )  # Volume trop bas

        result = filter_obj.filter_pair("BTC/USDT", market_data, scoring_result)

        assert result.accepted is False
        assert len(result.rejection_reasons) > 0


# =============================================================================
# Helpers pour créer des données de test
# =============================================================================


class TestablePairFilterHelper:
    """Helpers pour créer des données de test"""

    @staticmethod
    def _create_market_data(
        spread_pct=0.03, balance_score=0.85, funding_rate=0.01, orderbook=None
    ):
        """Crée MarketData mock"""
        # Gérer le cas où orderbook=None est passé explicitement (données manquantes)
        if orderbook is None and spread_pct == "missing":
            return MarketData(
                symbol="BTC/USDT",
                timestamp=datetime.utcnow(),
                orderbook=None,  # Orderbook manquant
                ticker=TickerData(
                    symbol="BTC/USDT",
                    timestamp=datetime.utcnow(),
                    price=50000.0,
                    volume_24h=1000000.0,
                    funding_rate=funding_rate,
                ),
                source=DataSource.MOCK,
            )

        if orderbook is None:
            import math

            # Gérer le cas NaN explicitement
            if math.isnan(spread_pct):
                # Pour NaN, créer un orderbook avec spread NaN (sans bids/asks pour éviter recalcul)
                orderbook = OrderbookData(
                    symbol="BTC/USDT",
                    timestamp=datetime.utcnow(),
                    bids=[],  # Pas de bids/asks pour éviter recalcul
                    asks=[],
                    spread=float("nan"),
                    spread_pct=float("nan"),
                    balance_score=balance_score,
                )
                return MarketData(
                    symbol="BTC/USDT",
                    timestamp=datetime.utcnow(),
                    orderbook=orderbook,
                    ticker=TickerData(
                        symbol="BTC/USDT",
                        timestamp=datetime.utcnow(),
                        price=50000.0,
                        volume_24h=1000000.0,
                        funding_rate=funding_rate,
                    ),
                    source=DataSource.MOCK,
                )

            # Calculer les prix pour obtenir le spread_pct désiré
            # spread_pct = ((ask - bid) / mid) * 100
            # Pour spread_pct=0.03 et price=50000: ask-bid = 0.03/100 * 50000 = 15
            base_price = 50000.0
            spread_value = (spread_pct / 100) * base_price
            best_bid = base_price - (spread_value / 2)
            best_ask = base_price + (spread_value / 2)

            # Gérer le cas balance_score=0.5 (besoin de ratio 0.75 ou 0.25)
            if balance_score == 0.5:
                # Ratio 0.75: bid_vol=300, ask_vol=100
                bids = [(best_bid, 300), (best_bid - 1, 100)]
                asks = [(best_ask, 100), (best_ask + 1, 50)]
            else:
                # Augmenter volumes pour book_depth > 1000
                bids = [(best_bid, 600), (best_bid - 1, 400)]
                asks = [(best_ask, 600), (best_ask + 1, 400)]  # book_depth = 2000

            orderbook = OrderbookData(
                symbol="BTC/USDT",
                timestamp=datetime.utcnow(),
                bids=bids,
                asks=asks,
                spread=spread_value,
                spread_pct=spread_pct,
                balance_score=balance_score,
            )

        ticker = TickerData(
            symbol="BTC/USDT",
            timestamp=datetime.utcnow(),
            price=50000.0,
            volume_24h=15000000.0,  # > min_volume_24h (10000000)
            funding_rate=funding_rate,
        )

        return MarketData(
            symbol="BTC/USDT",
            timestamp=datetime.utcnow(),
            orderbook=orderbook,
            ticker=ticker,
            source=DataSource.MOCK,
        )

    @staticmethod
    def _create_scoring_result(volume_recent=500000):
        """Crée ScoringResult mock"""
        return ScoringResult(
            symbol="BTC/USDT",
            score=7.5,
            metrics=ScoringMetrics(
                volume_recent=volume_recent,
                volatility_5=1.5,
                volatility_15=1.2,
                volume_24h=1000000.0,
                atr=1.0,
                atr_pct=0.5,
                adx=30.0,
            ),
            scoring_details={"test": "data"},
        )


# Rendre les helpers disponibles dans le scope
_create_market_data = TestablePairFilterHelper._create_market_data
_create_scoring_result = TestablePairFilterHelper._create_scoring_result


if __name__ == "__main__":
    """Exécution des tests avec couverture"""
    import coverage

    print("=" * 60)
    print("TestablePairFilter Tests - Trade Cursor v7.0")
    print("=" * 60)

    # Lancer pytest avec couverture
    cov = coverage.Coverage()
    cov.start()

    pytest_result = pytest.main([__file__, "-v", "--tb=short", "-x"])

    cov.stop()
    cov.save()

    print("\n" + "=" * 60)
    print("Couverture de code:")
    print("=" * 60)
    cov.report(show_missing=True, omit=["*/tests/*", "*/mocks/*"])

    print("\n" + "=" * 60)
    print(f"Résultat: {'SUCCÈS' if pytest_result == 0 else 'ÉCHECS DÉTECTÉS'}")
    print("=" * 60)

    sys.exit(pytest_result)
