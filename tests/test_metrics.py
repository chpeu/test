"""
Tests pour core/metrics.py
"""
import pytest
from core.metrics import ConditionMetrics, MetricsCollector, get_metrics_collector, condition_metrics


class TestConditionMetrics:
    """Tests pour ConditionMetrics"""

    def setup_method(self):
        """Setup avant chaque test"""
        self.metrics = ConditionMetrics()

    def test_init(self):
        """Test initialisation"""
        metrics = ConditionMetrics()
        assert metrics.condition_stats == {}
        assert metrics.combination_stats == {}

    def test_record_trade_empty_conditions(self):
        """Test record_trade avec liste vide"""
        self.metrics.record_trade([], True)
        assert len(self.metrics.condition_stats) == 0

    def test_record_trade_single_condition_win(self):
        """Test enregistrement trade gagnant avec 1 condition"""
        self.metrics.record_trade(['EMA_CROSS'], True)

        assert 'EMA_CROSS' in self.metrics.condition_stats
        stats = self.metrics.condition_stats['EMA_CROSS']
        assert stats['wins'] == 1
        assert stats['losses'] == 0
        assert stats['total'] == 1
        assert stats['winrate'] == 100.0

    def test_record_trade_single_condition_loss(self):
        """Test enregistrement trade perdant avec 1 condition"""
        self.metrics.record_trade(['RSI_OVERSOLD'], False)

        assert 'RSI_OVERSOLD' in self.metrics.condition_stats
        stats = self.metrics.condition_stats['RSI_OVERSOLD']
        assert stats['wins'] == 0
        assert stats['losses'] == 1
        assert stats['total'] == 1
        assert stats['winrate'] == 0.0

    def test_record_trade_multiple_conditions(self):
        """Test enregistrement trade avec plusieurs conditions"""
        self.metrics.record_trade(['EMA_CROSS', 'RSI_OVERSOLD', 'VOLUME_SPIKE'], True)

        assert len(self.metrics.condition_stats) == 3
        assert 'EMA_CROSS' in self.metrics.condition_stats
        assert 'RSI_OVERSOLD' in self.metrics.condition_stats
        assert 'VOLUME_SPIKE' in self.metrics.condition_stats

        # Toutes devraient avoir les mêmes stats
        for condition in ['EMA_CROSS', 'RSI_OVERSOLD', 'VOLUME_SPIKE']:
            stats = self.metrics.condition_stats[condition]
            assert stats['wins'] == 1
            assert stats['losses'] == 0
            assert stats['total'] == 1

    def test_record_trade_updates_existing_condition(self):
        """Test mise à jour condition existante"""
        # Premier trade - win
        self.metrics.record_trade(['EMA_CROSS'], True)

        # Deuxième trade - loss
        self.metrics.record_trade(['EMA_CROSS'], False)

        stats = self.metrics.condition_stats['EMA_CROSS']
        assert stats['wins'] == 1
        assert stats['losses'] == 1
        assert stats['total'] == 2
        assert stats['winrate'] == 50.0

    def test_record_trade_winrate_calculation(self):
        """Test calcul winrate correct"""
        # 3 wins, 1 loss = 75% winrate
        self.metrics.record_trade(['MACD'], True)
        self.metrics.record_trade(['MACD'], True)
        self.metrics.record_trade(['MACD'], True)
        self.metrics.record_trade(['MACD'], False)

        stats = self.metrics.condition_stats['MACD']
        assert stats['wins'] == 3
        assert stats['losses'] == 1
        assert stats['total'] == 4
        assert stats['winrate'] == 75.0

    def test_record_trade_combinations_two_conditions(self):
        """Test enregistrement combinaisons avec 2 conditions"""
        self.metrics.record_trade(['EMA_CROSS', 'RSI_OVERSOLD'], True)

        # Devrait créer 1 combo (2 conditions = 1 paire)
        assert len(self.metrics.combination_stats) == 1

        # Combo devrait être triée alphabétiquement
        combo = tuple(sorted(['EMA_CROSS', 'RSI_OVERSOLD']))
        assert combo in self.metrics.combination_stats
        assert self.metrics.combination_stats[combo]['wins'] == 1

    def test_record_trade_combinations_three_conditions(self):
        """Test enregistrement combinaisons avec 3 conditions"""
        self.metrics.record_trade(['A', 'B', 'C'], True)

        # 3 conditions = C(3,2) = 3 paires: (A,B), (A,C), (B,C)
        assert len(self.metrics.combination_stats) == 3

        expected_combos = [('A', 'B'), ('A', 'C'), ('B', 'C')]
        for combo in expected_combos:
            assert combo in self.metrics.combination_stats

    def test_record_trade_combinations_sorting(self):
        """Test tri alphabétique des combinaisons"""
        self.metrics.record_trade(['Z_CONDITION', 'A_CONDITION'], True)

        # Combo devrait être ('A_CONDITION', 'Z_CONDITION')
        assert ('A_CONDITION', 'Z_CONDITION') in self.metrics.combination_stats
        assert ('Z_CONDITION', 'A_CONDITION') not in self.metrics.combination_stats

    def test_get_best_conditions_empty(self):
        """Test get_best_conditions avec stats vides"""
        results = self.metrics.get_best_conditions()
        assert results == []

    def test_get_best_conditions_below_min_samples(self):
        """Test get_best_conditions avec échantillons < min_samples"""
        # 5 trades (< 10 par défaut)
        for _ in range(5):
            self.metrics.record_trade(['CONDITION_A'], True)

        results = self.metrics.get_best_conditions(min_samples=10)
        assert results == []

    def test_get_best_conditions_with_data(self):
        """Test get_best_conditions avec données"""
        # Condition A: 15 trades, 12 wins = 80%
        for _ in range(12):
            self.metrics.record_trade(['CONDITION_A'], True)
        for _ in range(3):
            self.metrics.record_trade(['CONDITION_A'], False)

        # Condition B: 10 trades, 6 wins = 60%
        for _ in range(6):
            self.metrics.record_trade(['CONDITION_B'], True)
        for _ in range(4):
            self.metrics.record_trade(['CONDITION_B'], False)

        results = self.metrics.get_best_conditions(min_samples=10)
        assert len(results) == 2

        # Devrait être trié par winrate (A avant B)
        assert results[0]['condition'] == 'CONDITION_A'
        assert results[0]['winrate'] == 80.0
        assert results[0]['total'] == 15

        assert results[1]['condition'] == 'CONDITION_B'
        assert results[1]['winrate'] == 60.0
        assert results[1]['total'] == 10

    def test_get_worst_conditions(self):
        """Test get_worst_conditions"""
        # Condition A: 80% winrate
        for _ in range(8):
            self.metrics.record_trade(['CONDITION_A'], True)
        for _ in range(2):
            self.metrics.record_trade(['CONDITION_A'], False)

        # Condition B: 30% winrate
        for _ in range(3):
            self.metrics.record_trade(['CONDITION_B'], True)
        for _ in range(7):
            self.metrics.record_trade(['CONDITION_B'], False)

        results = self.metrics.get_worst_conditions(min_samples=10)
        assert len(results) == 2

        # Devrait être trié par winrate croissant (B avant A)
        assert results[0]['condition'] == 'CONDITION_B'
        assert results[0]['winrate'] == 30.0

        assert results[1]['condition'] == 'CONDITION_A'
        assert results[1]['winrate'] == 80.0

    def test_get_best_combinations_empty(self):
        """Test get_best_combinations avec stats vides"""
        results = self.metrics.get_best_combinations()
        assert results == []

    def test_get_best_combinations_with_data(self):
        """Test get_best_combinations avec données"""
        # Combo A+B: 10 trades, 8 wins = 80%
        for _ in range(8):
            self.metrics.record_trade(['A', 'B'], True)
        for _ in range(2):
            self.metrics.record_trade(['A', 'B'], False)

        # Combo C+D: 5 trades, 3 wins = 60%
        for _ in range(3):
            self.metrics.record_trade(['C', 'D'], True)
        for _ in range(2):
            self.metrics.record_trade(['C', 'D'], False)

        results = self.metrics.get_best_combinations(min_samples=5)
        assert len(results) == 2

        # Devrait être trié par winrate
        assert results[0]['combination'] == 'A + B'
        assert results[0]['winrate'] == 80.0

        assert results[1]['combination'] == 'C + D'
        assert results[1]['winrate'] == 60.0

    def test_get_stats_summary(self):
        """Test get_stats_summary"""
        # Ajouter quelques trades
        for _ in range(10):
            self.metrics.record_trade(['CONDITION_A'], True)

        for _ in range(5):
            self.metrics.record_trade(['CONDITION_B', 'CONDITION_C'], True)

        summary = self.metrics.get_stats_summary()

        assert 'best_conditions' in summary
        assert 'worst_conditions' in summary
        assert 'best_combinations' in summary
        assert 'all_conditions' in summary
        assert 'all_combinations' in summary

        # Vérifier que all_conditions contient les bonnes clés
        assert 'CONDITION_A' in summary['all_conditions']

    def test_reset(self):
        """Test reset des statistiques"""
        # Ajouter des trades
        self.metrics.record_trade(['CONDITION_A'], True)
        self.metrics.record_trade(['CONDITION_B', 'CONDITION_C'], False)

        assert len(self.metrics.condition_stats) > 0
        assert len(self.metrics.combination_stats) > 0

        # Reset
        self.metrics.reset()

        assert len(self.metrics.condition_stats) == 0
        assert len(self.metrics.combination_stats) == 0


class TestMetricsCollector:
    """Tests pour MetricsCollector"""

    def test_init(self):
        """Test initialisation"""
        collector = MetricsCollector()
        assert collector.condition_metrics == condition_metrics
        assert collector.ws_connected is False
        assert collector.ws_price_count == 0
        assert collector.rest_price_count == 0
        assert collector.ws_rest_fallback_count == 0
        assert collector.positions_closed == 0
        assert collector.trades_wins == 0
        assert collector.trades_losses == 0

    def test_record_trade(self):
        """Test record_trade alias"""
        collector = MetricsCollector()

        # Reset condition_metrics pour test isolé
        condition_metrics.reset()

        collector.record_trade(['EMA_CROSS'], True)

        # Devrait utiliser condition_metrics global
        assert 'EMA_CROSS' in condition_metrics.condition_stats

    def test_get_stats(self):
        """Test get_stats alias"""
        collector = MetricsCollector()

        # Reset et ajouter données
        condition_metrics.reset()
        for _ in range(10):
            condition_metrics.record_trade(['TEST_CONDITION'], True)

        stats = collector.get_stats()

        assert 'best_conditions' in stats
        assert 'worst_conditions' in stats


class TestGetMetricsCollector:
    """Tests pour get_metrics_collector singleton"""

    def test_returns_instance(self):
        """Test retourne une instance de MetricsCollector"""
        collector = get_metrics_collector()
        assert isinstance(collector, MetricsCollector)

    def test_returns_same_instance(self):
        """Test retourne toujours la même instance (singleton)"""
        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()
        assert collector1 is collector2


class TestIntegration:
    """Tests d'intégration"""

    def test_full_workflow(self):
        """Test workflow complet"""
        metrics = ConditionMetrics()

        # Simuler 100 trades avec différentes conditions
        trades = [
            (['EMA_CROSS'], True),
            (['EMA_CROSS'], True),
            (['EMA_CROSS'], False),
            (['RSI_OVERSOLD'], True),
            (['RSI_OVERSOLD'], False),
            (['RSI_OVERSOLD'], False),
            (['EMA_CROSS', 'RSI_OVERSOLD'], True),
            (['EMA_CROSS', 'RSI_OVERSOLD'], True),
            (['EMA_CROSS', 'VOLUME_SPIKE'], True),
            (['VOLUME_SPIKE'], False),
        ]

        # Ajouter 10 trades pour chaque combo pour atteindre min_samples
        for _ in range(10):
            for conditions, won in trades:
                metrics.record_trade(conditions, won)

        # Vérifier statistiques
        summary = metrics.get_stats_summary()

        assert len(summary['best_conditions']) > 0
        assert len(summary['best_combinations']) > 0

        # EMA_CROSS devrait avoir des trades (apparaît dans plusieurs combos)
        ema_stats = metrics.condition_stats['EMA_CROSS']
        assert ema_stats['total'] > 0  # Devrait avoir des trades enregistrés

        # Reset devrait tout nettoyer
        metrics.reset()
        assert len(metrics.condition_stats) == 0
