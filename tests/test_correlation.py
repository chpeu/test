"""
Tests pour la vérification de corrélation
"""
import pytest
from unittest.mock import MagicMock


class TestCorrelation:
    """Tests pour la vérification de corrélation"""

    def test_check_static_correlation_no_positions(self):
        """Test corrélation statique - pas de positions actives"""
        from core.analyzer.correlation import check_static_correlation
        
        result = check_static_correlation(
            symbol='BTCUSDT',
            active_positions=None
        )
        
        assert 'valid' in result
        assert result['valid'] is True

    def test_check_static_correlation_empty_positions(self):
        """Test corrélation statique - positions vides"""
        from core.analyzer.correlation import check_static_correlation
        
        result = check_static_correlation(
            symbol='BTCUSDT',
            active_positions=[]
        )
        
        assert 'valid' in result
        assert result['valid'] is True

    def test_check_static_correlation_with_positions(self):
        """Test corrélation statique - avec positions actives"""
        from core.analyzer.correlation import check_static_correlation
        
        result = check_static_correlation(
            symbol='BTCUSDT',
            active_positions=['ETHUSDT']
        )
        
        assert 'valid' in result
        assert 'penalty' in result

    def test_check_dynamic_correlation_no_filter(self):
        """Test corrélation dynamique - pas de filtre"""
        from core.analyzer.correlation import check_dynamic_correlation
        
        result = check_dynamic_correlation(
            correlation_filter=None,
            symbol='BTCUSDT',
            current_price=50000.0,
            active_positions=[]
        )
        
        assert result is None

    def test_check_dynamic_correlation_with_filter(self):
        """Test corrélation dynamique - avec filtre"""
        from core.analyzer.correlation import check_dynamic_correlation
        
        # Mock filter
        mock_filter = MagicMock()
        mock_filter.check_correlation = MagicMock(return_value={
            'correlated': False,
            'correlated_with': None,
            'correlation': 0.0
        })
        
        result = check_dynamic_correlation(
            correlation_filter=mock_filter,
            symbol='BTCUSDT',
            current_price=50000.0,
            active_positions=[]
        )
        
        assert result is None
