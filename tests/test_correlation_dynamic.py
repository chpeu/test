"""
Tests pour core/correlation_dynamic.py
"""
import pytest
from unittest.mock import Mock, patch
from collections import deque


class TestDynamicCorrelationFilter:
    """Tests pour DynamicCorrelationFilter"""

    def test_init_default_params(self):
        """Test initialisation avec paramètres par défaut"""
        from core.correlation_dynamic import DynamicCorrelationFilter

        filter = DynamicCorrelationFilter()
        assert filter.period == 50
        assert filter.threshold == 0.7
        assert filter.price_history == {}

    def test_init_custom_params(self):
        """Test initialisation avec paramètres personnalisés"""
        from core.correlation_dynamic import DynamicCorrelationFilter

        filter = DynamicCorrelationFilter(period=100, threshold=0.8)
        assert filter.period == 100
        assert filter.threshold == 0.8

    def test_update_price_new_symbol(self):
        """Test mise à jour prix pour nouveau symbole"""
        from core.correlation_dynamic import DynamicCorrelationFilter

        filter = DynamicCorrelationFilter()
        filter.update_price('BTC/USDT', 50000.0)

        assert 'BTC/USDT' in filter.price_history
        assert len(filter.price_history['BTC/USDT']) == 1
        assert list(filter.price_history['BTC/USDT'])[0] == 50000.0

    def test_update_price_existing_symbol(self):
        """Test mise à jour prix pour symbole existant"""
        from core.correlation_dynamic import DynamicCorrelationFilter

        filter = DynamicCorrelationFilter()
        filter.update_price('BTC/USDT', 50000.0)
        filter.update_price('BTC/USDT', 51000.0)
        filter.update_price('BTC/USDT', 52000.0)

        assert len(filter.price_history['BTC/USDT']) == 3
        prices = list(filter.price_history['BTC/USDT'])
        assert prices == [50000.0, 51000.0, 52000.0]

    def test_update_price_deque_max_length(self):
        """Test que deque respecte maxlen"""
        from core.correlation_dynamic import DynamicCorrelationFilter

        filter = DynamicCorrelationFilter(period=5)

        # Ajouter 10 prix (deque devrait garder seulement les 5 derniers)
        for i in range(10):
            filter.update_price('BTC/USDT', 50000.0 + i * 100)

        assert len(filter.price_history['BTC/USDT']) == 5
        prices = list(filter.price_history['BTC/USDT'])
        # Devrait avoir les 5 derniers (5, 6, 7, 8, 9)
        assert prices == [50500.0, 50600.0, 50700.0, 50800.0, 50900.0]

    def test_calculate_correlation_numpy_not_available(self):
        """Test calculate_correlation quand numpy n'est pas disponible"""
        from core.correlation_dynamic import DynamicCorrelationFilter

        with patch('core.correlation_dynamic.NUMPY_AVAILABLE', False):
            filter = DynamicCorrelationFilter()

            # Ajouter des prix
            for i in range(30):
                filter.update_price('BTC/USDT', 50000.0 + i * 100)
                filter.update_price('ETH/USDT', 3000.0 + i * 10)

            corr = filter.calculate_correlation('BTC/USDT', 'ETH/USDT')
            assert corr == 0.0

    def test_calculate_correlation_missing_symbol(self):
        """Test calculate_correlation avec symbole manquant"""
        from core.correlation_dynamic import DynamicCorrelationFilter

        filter = DynamicCorrelationFilter()

        # Ajouter prix seulement pour BTC
        for i in range(30):
            filter.update_price('BTC/USDT', 50000.0 + i * 100)

        # ETH n'existe pas
        corr = filter.calculate_correlation('BTC/USDT', 'ETH/USDT')
        assert corr == 0.0

    def test_calculate_correlation_insufficient_data(self):
        """Test calculate_correlation avec données insuffisantes (< 20)"""
        from core.correlation_dynamic import DynamicCorrelationFilter

        filter = DynamicCorrelationFilter()

        # Ajouter seulement 15 prix (< 20 requis)
        for i in range(15):
            filter.update_price('BTC/USDT', 50000.0 + i * 100)
            filter.update_price('ETH/USDT', 3000.0 + i * 10)

        corr = filter.calculate_correlation('BTC/USDT', 'ETH/USDT')
        assert corr == 0.0

    def test_calculate_correlation_perfect_positive(self):
        """Test calculate_correlation avec corrélation positive parfaite"""
        from core.correlation_dynamic import DynamicCorrelationFilter
        import core.correlation_dynamic

        if not core.correlation_dynamic.NUMPY_AVAILABLE:
            pytest.skip("numpy not available")

        filter = DynamicCorrelationFilter()

        # Deux symboles avec mouvement identique
        for i in range(30):
            price = 50000.0 + i * 100
            filter.update_price('BTC/USDT', price)
            filter.update_price('BTC2/USDT', price)  # Même mouvement

        corr = filter.calculate_correlation('BTC/USDT', 'BTC2/USDT')
        # Corrélation devrait être proche de 1.0
        assert corr > 0.9

    def test_calculate_correlation_uncorrelated(self):
        """Test calculate_correlation avec pattern non corrélé"""
        from core.correlation_dynamic import DynamicCorrelationFilter
        import core.correlation_dynamic

        if not core.correlation_dynamic.NUMPY_AVAILABLE:
            pytest.skip("numpy not available")

        filter = DynamicCorrelationFilter()

        # Un symbole avec mouvement constant, l'autre avec variations aléatoires
        import random
        random.seed(42)  # Pour reproductibilité
        for i in range(30):
            filter.update_price('BTC/USDT', 50000.0 + i * 100)  # Tendance constante
            filter.update_price('RANDOM/USDT', 3000.0 + random.uniform(-100, 100))  # Aléatoire

        corr = filter.calculate_correlation('BTC/USDT', 'RANDOM/USDT')
        # Corrélation devrait être faible (proche de 0)
        assert abs(corr) < 0.9  # Pas de forte corrélation

    def test_calculate_correlation_different_lengths(self):
        """Test calculate_correlation avec historiques de longueurs différentes"""
        from core.correlation_dynamic import DynamicCorrelationFilter
        import core.correlation_dynamic

        if not core.correlation_dynamic.NUMPY_AVAILABLE:
            pytest.skip("numpy not available")

        filter = DynamicCorrelationFilter()

        # BTC: 40 prix
        for i in range(40):
            filter.update_price('BTC/USDT', 50000.0 + i * 100)

        # ETH: 25 prix
        for i in range(25):
            filter.update_price('ETH/USDT', 3000.0 + i * 10)

        # Devrait aligner sur la longueur minimale
        corr = filter.calculate_correlation('BTC/USDT', 'ETH/USDT')
        assert isinstance(corr, float)
        assert -1.0 <= corr <= 1.0

    def test_check_correlation_no_positions(self):
        """Test check_correlation sans positions actives"""
        from core.correlation_dynamic import DynamicCorrelationFilter

        filter = DynamicCorrelationFilter()
        result = filter.check_correlation('BTC/USDT', [])

        assert result['valid'] is True
        assert result['penalty'] == 0
        assert result['correlation'] == 0

    def test_check_correlation_below_threshold(self):
        """Test check_correlation avec corrélation sous seuil"""
        from core.correlation_dynamic import DynamicCorrelationFilter
        import core.correlation_dynamic

        if not core.correlation_dynamic.NUMPY_AVAILABLE:
            pytest.skip("numpy not available")

        filter = DynamicCorrelationFilter(threshold=0.7)

        # Ajouter prix avec faible corrélation
        for i in range(30):
            filter.update_price('BTC/USDT', 50000.0 + i * 100)
            filter.update_price('ETH/USDT', 3000.0 + (i % 5) * 50)  # Pattern différent

        mock_position = Mock()
        mock_position.symbol = 'ETH/USDT'

        result = filter.check_correlation('BTC/USDT', [mock_position])

        assert result['valid'] is True
        # Corrélation faible = pas de pénalité
        assert result['penalty'] == 0

    def test_check_correlation_above_threshold(self):
        """Test check_correlation avec corrélation au-dessus du seuil"""
        from core.correlation_dynamic import DynamicCorrelationFilter
        import core.correlation_dynamic

        if not core.correlation_dynamic.NUMPY_AVAILABLE:
            pytest.skip("numpy not available")

        filter = DynamicCorrelationFilter(threshold=0.5)

        # Ajouter prix avec forte corrélation
        for i in range(30):
            price_btc = 50000.0 + i * 100
            price_eth = 3000.0 + i * 6  # Mouvement similaire
            filter.update_price('BTC/USDT', price_btc)
            filter.update_price('ETH/USDT', price_eth)

        mock_position = Mock()
        mock_position.symbol = 'ETH/USDT'

        result = filter.check_correlation('BTC/USDT', [mock_position])

        assert result['valid'] is True  # Mode SOFT
        assert result['penalty'] < 0  # Devrait avoir une pénalité
        assert result['penalty'] >= -3.0  # Max penalty
        assert result['correlated_with'] == 'ETH/USDT'
        assert abs(result['correlation']) > 0.5

    def test_check_correlation_penalty_calculation(self):
        """Test calcul de la pénalité"""
        from core.correlation_dynamic import DynamicCorrelationFilter
        import core.correlation_dynamic

        if not core.correlation_dynamic.NUMPY_AVAILABLE:
            pytest.skip("numpy not available")

        filter = DynamicCorrelationFilter(threshold=0.6)

        # Créer une corrélation très forte (proche de 1.0)
        for i in range(30):
            price = 50000.0 + i * 100
            filter.update_price('BTC/USDT', price)
            filter.update_price('BTC2/USDT', price + 10)  # Quasi identique

        mock_position = Mock()
        mock_position.symbol = 'BTC2/USDT'

        result = filter.check_correlation('BTC/USDT', [mock_position])

        # Forte corrélation = pénalité importante
        assert result['penalty'] < -1.0
        # Mais limitée à -3.0
        assert result['penalty'] >= -3.0

    def test_check_correlation_multiple_positions(self):
        """Test check_correlation avec plusieurs positions"""
        from core.correlation_dynamic import DynamicCorrelationFilter
        import core.correlation_dynamic

        if not core.correlation_dynamic.NUMPY_AVAILABLE:
            pytest.skip("numpy not available")

        filter = DynamicCorrelationFilter(threshold=0.6)

        # Ajouter prix pour 3 symboles
        for i in range(30):
            filter.update_price('NEW/USDT', 1000.0 + i * 10)
            filter.update_price('ETH/USDT', 3000.0 + i * 5)  # Faible corrélation
            filter.update_price('CORR/USDT', 1000.0 + i * 10)  # Forte corrélation avec NEW

        mock_pos1 = Mock()
        mock_pos1.symbol = 'ETH/USDT'

        mock_pos2 = Mock()
        mock_pos2.symbol = 'CORR/USDT'

        result = filter.check_correlation('NEW/USDT', [mock_pos1, mock_pos2])

        # Devrait détecter la forte corrélation avec CORR/USDT
        assert result['correlated_with'] == 'CORR/USDT'
        assert abs(result['correlation']) > 0.6

    def test_check_correlation_same_symbol(self):
        """Test check_correlation ignore le même symbole"""
        from core.correlation_dynamic import DynamicCorrelationFilter
        import core.correlation_dynamic

        if not core.correlation_dynamic.NUMPY_AVAILABLE:
            pytest.skip("numpy not available")

        filter = DynamicCorrelationFilter()

        for i in range(30):
            filter.update_price('BTC/USDT', 50000.0 + i * 100)

        mock_position = Mock()
        mock_position.symbol = 'BTC/USDT'  # Même symbole

        result = filter.check_correlation('BTC/USDT', [mock_position])

        # Ne devrait pas se comparer avec lui-même
        assert result['penalty'] == 0
        assert result['correlation'] == 0

    def test_check_correlation_position_without_symbol(self):
        """Test check_correlation avec position sans symbole"""
        from core.correlation_dynamic import DynamicCorrelationFilter

        filter = DynamicCorrelationFilter()

        mock_position = Mock()
        mock_position.symbol = None  # Pas de symbole

        result = filter.check_correlation('BTC/USDT', [mock_position])

        assert result['valid'] is True
        assert result['penalty'] == 0


class TestNumpyImport:
    """Tests pour la gestion de l'import numpy"""

    def test_numpy_available_flag(self):
        """Test que NUMPY_AVAILABLE est défini"""
        from core.correlation_dynamic import NUMPY_AVAILABLE

        assert isinstance(NUMPY_AVAILABLE, bool)

    def test_module_works_without_numpy(self):
        """Test que le module fonctionne sans numpy"""
        with patch('core.correlation_dynamic.NUMPY_AVAILABLE', False):
            from core.correlation_dynamic import DynamicCorrelationFilter

            filter = DynamicCorrelationFilter()
            filter.update_price('BTC/USDT', 50000.0)

            # Devrait fonctionner mais retourner 0
            corr = filter.calculate_correlation('BTC/USDT', 'ETH/USDT')
            assert corr == 0.0


class TestIntegration:
    """Tests d'intégration"""

    def test_full_workflow(self):
        """Test workflow complet"""
        from core.correlation_dynamic import DynamicCorrelationFilter
        import core.correlation_dynamic

        if not core.correlation_dynamic.NUMPY_AVAILABLE:
            pytest.skip("numpy not available")

        filter = DynamicCorrelationFilter(period=50, threshold=0.7)

        # Simuler 100 ticks de prix pour BTC et ETH (mouvement similaire)
        for i in range(100):
            btc_price = 50000.0 + i * 100
            eth_price = 3000.0 + i * 6
            filter.update_price('BTC/USDT', btc_price)
            filter.update_price('ETH/USDT', eth_price)

        # Calculer corrélation
        corr = filter.calculate_correlation('BTC/USDT', 'ETH/USDT')
        assert abs(corr) > 0  # Devrait avoir une corrélation détectable

        # Vérifier corrélation avec position active
        mock_position = Mock()
        mock_position.symbol = 'ETH/USDT'

        result = filter.check_correlation('BTC/USDT', [mock_position])

        assert result['valid'] is True
        # Avec une forte corrélation, devrait avoir une pénalité
        if abs(corr) > 0.7:
            assert result['penalty'] < 0
