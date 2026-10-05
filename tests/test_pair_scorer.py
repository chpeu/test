"""
Tests pour PairScorer - Augmentation de couverture
"""

import pytest
from datetime import datetime, timedelta
from core.pair_scorer import PairScorer, PairStats


class TestPairScorer:
    """Tests pour PairScorer"""

    def test_init_default(self):
        """Test initialisation avec valeurs par défaut"""
        scorer = PairScorer()
        assert scorer.enabled is True
        assert scorer.min_trades == 15
        assert scorer.max_adjustment == 2.0
        assert scorer.lookback_days == 30
        assert scorer._stats_cache == {}
        assert scorer._last_refresh is None

    def test_init_custom_params(self):
        """Test initialisation avec paramètres personnalisés"""
        scorer = PairScorer(
            enabled=False,
            min_trades=20,
            max_adjustment=3.0,
            lookback_days=60,
            refresh_minutes=120
        )
        assert scorer.enabled is False
        assert scorer.min_trades == 20
        assert scorer.max_adjustment == 3.0
        assert scorer.lookback_days == 60

    def test_update_config(self):
        """Test mise à jour de configuration"""
        scorer = PairScorer()
        scorer.update_config(
            enabled=False,
            min_trades=25,
            max_adjustment=2.5
        )
        assert scorer.enabled is False
        assert scorer.min_trades == 25
        assert scorer.max_adjustment == 2.5

    def test_calculate_adjustment_insufficient_trades(self):
        """Test calcul ajustement avec trades insuffisants"""
        scorer = PairScorer(min_trades=15)
        adjustment, wr_comp, pnl_comp = scorer.calculate_adjustment(
            winrate=60.0,
            avg_pnl_pct=0.5,
            total_trades=10
        )
        assert adjustment == 0.0
        assert wr_comp == 0.0
        assert pnl_comp == 0.0

    def test_calculate_adjustment_sufficient_trades(self):
        """Test calcul ajustement avec trades suffisants"""
        scorer = PairScorer(min_trades=15)
        adjustment, wr_comp, pnl_comp = scorer.calculate_adjustment(
            winrate=60.0,
            avg_pnl_pct=0.5,
            total_trades=20
        )
        # wr_component = (60 - 50) / 10 * 0.6 = 0.6
        # pnl_component = (0.5 / 0.1) * 0.4 = 2.0
        # total = 2.6, borné à max_adjustment=2.0
        assert wr_comp == pytest.approx(0.6)
        assert pnl_comp == pytest.approx(2.0)
        assert adjustment == pytest.approx(2.0)

    def test_calculate_adjustment_negative(self):
        """Test calcul ajustement négatif"""
        scorer = PairScorer(min_trades=15)
        adjustment, wr_comp, pnl_comp = scorer.calculate_adjustment(
            winrate=40.0,
            avg_pnl_pct=-0.5,
            total_trades=20
        )
        # wr_component = (40 - 50) / 10 * 0.6 = -0.6
        # pnl_component = (-0.5 / 0.1) * 0.4 = -2.0
        # total = -2.6, borné à -max_adjustment=-2.0
        assert wr_comp == pytest.approx(-0.6)
        assert pnl_comp == pytest.approx(-2.0)
        assert adjustment == pytest.approx(-2.0)

    def test_get_pair_stats_none(self):
        """Test récupération stats inexistantes"""
        scorer = PairScorer()
        stats = scorer.get_pair_stats("BTC/USDT:USDT")
        assert stats is None

    def test_get_all_stats_empty(self):
        """Test récupération toutes les stats quand vide"""
        scorer = PairScorer()
        stats = scorer.get_all_stats()
        assert stats == {}

    def test_pair_stats_to_dict(self):
        """Test conversion PairStats en dict"""
        stats = PairStats(
            symbol="BTC/USDT:USDT",
            total_trades=100,
            wins=60,
            losses=40,
            winrate=60.0,
            avg_pnl_pct=0.5,
            score_adjustment=1.0
        )
        stats_dict = stats.to_dict()
        assert stats_dict["symbol"] == "BTC/USDT:USDT"
        assert stats_dict["total_trades"] == 100
        assert stats_dict["wins"] == 60
        assert stats_dict["losses"] == 40
        assert stats_dict["winrate"] == 60.0
        assert stats_dict["avg_pnl_pct"] == 0.5
        assert stats_dict["score_adjustment"] == 1.0

    def test_pair_stats_to_dict_with_timestamp(self):
        """Test conversion PairStats avec timestamp"""
        now = datetime.now()
        stats = PairStats(
            symbol="BTC/USDT:USDT",
            total_trades=100,
            last_updated=now
        )
        stats_dict = stats.to_dict()
        assert stats_dict["last_updated"] == now.isoformat()

    def test_pair_stats_to_dict_without_timestamp(self):
        """Test conversion PairStats sans timestamp"""
        stats = PairStats(
            symbol="BTC/USDT:USDT",
            total_trades=100
        )
        stats_dict = stats.to_dict()
        assert stats_dict["last_updated"] is None

    def test_calculate_adjustment_boundary_max(self):
        """Test calcul ajustement à la limite max"""
        scorer = PairScorer(min_trades=15, max_adjustment=2.0)
        adjustment, wr_comp, pnl_comp = scorer.calculate_adjustment(
            winrate=100.0,
            avg_pnl_pct=10.0,
            total_trades=20
        )
        assert adjustment == pytest.approx(2.0)

    def test_calculate_adjustment_boundary_min(self):
        """Test calcul ajustement à la limite min"""
        scorer = PairScorer(min_trades=15, max_adjustment=2.0)
        adjustment, wr_comp, pnl_comp = scorer.calculate_adjustment(
            winrate=0.0,
            avg_pnl_pct=-10.0,
            total_trades=20
        )
        assert adjustment == pytest.approx(-2.0)

    def test_calculate_adjustment_zero_values(self):
        """Test calcul ajustement avec valeurs zéro"""
        scorer = PairScorer(min_trades=15)
        adjustment, wr_comp, pnl_comp = scorer.calculate_adjustment(
            winrate=50.0,
            avg_pnl_pct=0.0,
            total_trades=20
        )
        assert adjustment == pytest.approx(0.0)
        assert wr_comp == pytest.approx(0.0)
        assert pnl_comp == pytest.approx(0.0)

    def test_get_pair_stats_cached(self):
        """Test récupération stats en cache"""
        scorer = PairScorer()
        stats = PairStats(
            symbol="BTC/USDT:USDT",
            total_trades=100,
            wins=60
        )
        scorer._stats_cache["BTC/USDT:USDT"] = stats
        retrieved = scorer.get_pair_stats("BTC/USDT:USDT")
        assert retrieved is not None
        assert retrieved.symbol == "BTC/USDT:USDT"
        assert retrieved.total_trades == 100

    def test_get_all_stats_with_cache(self):
        """Test récupération toutes les stats avec cache"""
        scorer = PairScorer()
        stats1 = PairStats(symbol="BTC/USDT:USDT", total_trades=100)
        stats2 = PairStats(symbol="ETH/USDT:USDT", total_trades=50)
        scorer._stats_cache["BTC/USDT:USDT"] = stats1
        scorer._stats_cache["ETH/USDT:USDT"] = stats2
        all_stats = scorer.get_all_stats()
        assert len(all_stats) == 2
        assert "BTC/USDT:USDT" in all_stats
        assert "ETH/USDT:USDT" in all_stats

    def test_get_all_stats_returns_dict(self):
        """Test que get_all_stats retourne un dict"""
        scorer = PairScorer()
        stats = PairStats(symbol="BTC/USDT:USDT", total_trades=100)
        scorer._stats_cache["BTC/USDT:USDT"] = stats
        all_stats = scorer.get_all_stats()
        assert isinstance(all_stats, dict)

    def test_update_config_partial(self):
        """Test mise à jour partielle de configuration"""
        scorer = PairScorer()
        original_max = scorer.max_adjustment
        scorer.update_config(min_trades=30)
        assert scorer.min_trades == 30
        assert scorer.max_adjustment == original_max

    def test_refresh_interval_calculation(self):
        """Test calcul intervalle de refresh"""
        scorer = PairScorer(refresh_minutes=120)
        assert scorer.refresh_interval == timedelta(minutes=120)

    def test_thread_safety_lock(self):
        """Test que le lock est initialisé"""
        scorer = PairScorer()
        assert scorer._lock is not None

    def test_callbacks_list_initialized(self):
        """Test que la liste de callbacks est initialisée"""
        scorer = PairScorer()
        assert isinstance(scorer._on_stats_updated_callbacks, list)
