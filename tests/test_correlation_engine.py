"""
Tests pour CorrelationEngine - Augmentation de couverture
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from core.analysis.correlation_engine import (
    CorrelationEngine,
    CorrelationResult,
    OptimizationSuggestion
)


class TestCorrelationEngine:
    """Tests pour CorrelationEngine"""

    def test_init_default(self):
        """Test initialisation avec valeurs par défaut"""
        engine = CorrelationEngine()
        assert engine.db_connection is None
        assert engine._cache == {}
        assert engine._cache_ttl == 300
        assert engine._last_cache_update is None

    def test_init_with_connection(self):
        """Test initialisation avec connexion"""
        mock_conn = Mock()
        engine = CorrelationEngine(db_connection=mock_conn)
        assert engine.db_connection == mock_conn

    def test_get_db_connection_with_provided(self):
        """Test récupération connexion avec connexion fournie"""
        mock_conn = Mock()
        engine = CorrelationEngine(db_connection=mock_conn)
        conn = engine._get_db_connection()
        assert conn == mock_conn

    @patch('core.analysis.correlation_engine.psycopg2.connect')
    def test_get_db_connection_with_database_url(self, mock_connect):
        """Test récupération connexion avec DATABASE_URL"""
        mock_conn = Mock()
        mock_connect.return_value = mock_conn
        
        with patch('core.analysis.correlation_engine.os.getenv') as mock_getenv:
            mock_getenv.return_value = "postgresql://user:pass@localhost/db"
            engine = CorrelationEngine()
            conn = engine._get_db_connection()
            assert conn == mock_conn

    @patch('core.analysis.correlation_engine.psycopg2.connect')
    def test_get_db_connection_with_postgres_vars(self, mock_connect):
        """Test récupération connexion avec variables POSTGRES_*"""
        mock_conn = Mock()
        mock_connect.return_value = mock_conn
        
        with patch('core.analysis.correlation_engine.os.getenv') as mock_getenv:
            def getenv_side_effect(key, default=None):
                env_vars = {
                    'DATABASE_URL': None,
                    'POSTGRES_HOST': 'localhost',
                    'POSTGRES_PORT': '5432',
                    'POSTGRES_DB': 'test_db',
                    'POSTGRES_USER': 'test_user',
                    'POSTGRES_PASSWORD': 'test_pass'
                }
                return env_vars.get(key, default)
            mock_getenv.side_effect = getenv_side_effect
            
            engine = CorrelationEngine()
            conn = engine._get_db_connection()
            assert conn == mock_conn

    def test_release_connection_with_provided(self):
        """Test libération connexion avec connexion fournie"""
        mock_conn = Mock()
        engine = CorrelationEngine(db_connection=mock_conn)
        engine._release_connection(mock_conn)
        mock_conn.close.assert_not_called()

    def test_release_connection_without_provided(self):
        """Test libération connexion sans connexion fournie"""
        mock_conn = Mock()
        engine = CorrelationEngine()
        engine._release_connection(mock_conn)
        mock_conn.close.assert_called_once()

    def test_release_connection_none(self):
        """Test libération connexion None"""
        engine = CorrelationEngine()
        engine._release_connection(None)

    def test_cache_initialization(self):
        """Test initialisation du cache"""
        engine = CorrelationEngine()
        assert engine._cache == {}

    def test_cache_ttl_default(self):
        """Test TTL cache par défaut"""
        engine = CorrelationEngine()
        assert engine._cache_ttl == 300

    def test_last_cache_update_none_initially(self):
        """Test last_cache_update None initialement"""
        engine = CorrelationEngine()
        assert engine._last_cache_update is None

    def test_correlation_result_creation(self):
        """Test création CorrelationResult"""
        result = CorrelationResult(
            dimension="session",
            value="ASIA",
            trades=100,
            wins=60,
            winrate=60.0,
            total_pnl=1500.0,
            avg_pnl=15.0,
            recommendation="FAVOR"
        )
        assert result.dimension == "session"
        assert result.value == "ASIA"
        assert result.trades == 100
        assert result.winrate == 60.0
        assert result.recommendation == "FAVOR"

    def test_correlation_result_fields(self):
        """Test tous les champs CorrelationResult"""
        result = CorrelationResult(
            dimension="regime",
            value="LOW",
            trades=50,
            wins=30,
            winrate=60.0,
            total_pnl=750.0,
            avg_pnl=15.0,
            recommendation="NEUTRAL"
        )
        assert result.dimension == "regime"
        assert result.value == "LOW"
        assert result.trades == 50
        assert result.wins == 30
        assert result.winrate == 60.0
        assert result.total_pnl == 750.0
        assert result.avg_pnl == 15.0
        assert result.recommendation == "NEUTRAL"

    def test_optimization_suggestion_creation(self):
        """Test création OptimizationSuggestion"""
        suggestion = OptimizationSuggestion(
            parameter="min_score",
            current_value=2.0,
            suggested_value=1.5,
            expected_improvement="+5% winrate",
            confidence="HIGH",
            based_on_trades=200
        )
        assert suggestion.parameter == "min_score"
        assert suggestion.current_value == 2.0
        assert suggestion.suggested_value == 1.5
        assert suggestion.expected_improvement == "+5% winrate"
        assert suggestion.confidence == "HIGH"
        assert suggestion.based_on_trades == 200

    def test_optimization_suggestion_confidence_levels(self):
        """Test niveaux de confiance OptimizationSuggestion"""
        for confidence in ["LOW", "MEDIUM", "HIGH"]:
            suggestion = OptimizationSuggestion(
                parameter="test",
                current_value=1.0,
                suggested_value=2.0,
                expected_improvement="test",
                confidence=confidence,
                based_on_trades=100
            )
            assert suggestion.confidence == confidence

    def test_correlation_result_recommendation_types(self):
        """Test types de recommandation CorrelationResult"""
        recommendations = ["AVOID", "NEUTRAL", "FAVOR"]
        for rec in recommendations:
            result = CorrelationResult(
                dimension="test",
                value="test",
                trades=10,
                wins=5,
                winrate=50.0,
                total_pnl=100.0,
                avg_pnl=10.0,
                recommendation=rec
            )
            assert result.recommendation == rec

    def test_correlation_result_dimension_types(self):
        """Test types de dimension CorrelationResult"""
        dimensions = ["session", "regime", "hour", "parameter"]
        for dim in dimensions:
            result = CorrelationResult(
                dimension=dim,
                value="test",
                trades=10,
                wins=5,
                winrate=50.0,
                total_pnl=100.0,
                avg_pnl=10.0,
                recommendation="NEUTRAL"
            )
            assert result.dimension == dim

    def test_correlation_result_numeric_fields(self):
        """Test champs numériques CorrelationResult"""
        result = CorrelationResult(
            dimension="test",
            value="test",
            trades=100,
            wins=60,
            winrate=60.0,
            total_pnl=1500.0,
            avg_pnl=15.0,
            recommendation="FAVOR"
        )
        assert isinstance(result.trades, int)
        assert isinstance(result.wins, int)
        assert isinstance(result.winrate, float)
        assert isinstance(result.total_pnl, float)
        assert isinstance(result.avg_pnl, float)

    def test_optimization_suggestion_creation(self):
        """Test création OptimizationSuggestion"""
        suggestion = OptimizationSuggestion(
            parameter="test",
            current_value=1.5,
            suggested_value=2.5,
            expected_improvement="test",
            confidence="HIGH",
            based_on_trades=200
        )
        assert suggestion.parameter == "test"
        assert suggestion.current_value == 1.5
        assert suggestion.suggested_value == 2.5
        assert suggestion.expected_improvement == "test"
        assert suggestion.confidence == "HIGH"
        assert suggestion.based_on_trades == 200

    def test_optimization_suggestion_numeric_fields(self):
        """Test champs numériques OptimizationSuggestion"""
        suggestion = OptimizationSuggestion(
            parameter="test",
            current_value=1.5,
            suggested_value=2.5,
            expected_improvement="test",
            confidence="HIGH",
            based_on_trades=200
        )
        assert isinstance(suggestion.current_value, float)
        assert isinstance(suggestion.suggested_value, float)
        assert isinstance(suggestion.based_on_trades, int)

    def test_correlation_result_string_fields(self):
        """Test champs string CorrelationResult"""
        result = CorrelationResult(
            dimension="session",
            value="ASIA",
            trades=10,
            wins=5,
            winrate=50.0,
            total_pnl=100.0,
            avg_pnl=10.0,
            recommendation="NEUTRAL"
        )
        assert isinstance(result.dimension, str)
        assert isinstance(result.value, str)
        assert isinstance(result.recommendation, str)

    def test_optimization_suggestion_string_fields(self):
        """Test champs string OptimizationSuggestion"""
        suggestion = OptimizationSuggestion(
            parameter="min_score",
            current_value=2.0,
            suggested_value=1.5,
            expected_improvement="+5% winrate",
            confidence="MEDIUM",
            based_on_trades=100
        )
        assert isinstance(suggestion.parameter, str)
        assert isinstance(suggestion.expected_improvement, str)
        assert isinstance(suggestion.confidence, str)

    def test_correlation_result_zero_trades(self):
        """Test CorrelationResult avec zéro trades"""
        result = CorrelationResult(
            dimension="test",
            value="test",
            trades=0,
            wins=0,
            winrate=0.0,
            total_pnl=0.0,
            avg_pnl=0.0,
            recommendation="NEUTRAL"
        )
        assert result.trades == 0
        assert result.wins == 0

    def test_correlation_result_all_wins(self):
        """Test CorrelationResult 100% wins"""
        result = CorrelationResult(
            dimension="test",
            value="test",
            trades=100,
            wins=100,
            winrate=100.0,
            total_pnl=2000.0,
            avg_pnl=20.0,
            recommendation="FAVOR"
        )
        assert result.winrate == 100.0

    def test_correlation_result_all_losses(self):
        """Test CorrelationResult 0% wins"""
        result = CorrelationResult(
            dimension="test",
            value="test",
            trades=100,
            wins=0,
            winrate=0.0,
            total_pnl=-1000.0,
            avg_pnl=-10.0,
            recommendation="AVOID"
        )
        assert result.winrate == 0.0

    def test_cache_dict_type(self):
        """Test type dict cache"""
        engine = CorrelationEngine()
        assert isinstance(engine._cache, dict)

    def test_cache_ttl_type(self):
        """Test type TTL cache"""
        engine = CorrelationEngine()
        assert isinstance(engine._cache_ttl, int)

    def test_db_connection_attribute(self):
        """Test attribut db_connection"""
        engine = CorrelationEngine()
        assert hasattr(engine, 'db_connection')

    def test_cache_attribute(self):
        """Test attribut cache"""
        engine = CorrelationEngine()
        assert hasattr(engine, '_cache')

    def test_cache_ttl_attribute(self):
        """Test attribut cache_ttl"""
        engine = CorrelationEngine()
        assert hasattr(engine, '_cache_ttl')

    def test_last_cache_update_attribute(self):
        """Test attribut last_cache_update"""
        engine = CorrelationEngine()
        assert hasattr(engine, '_last_cache_update')

    def test_correlation_result_dataclass(self):
        """Test CorrelationResult est dataclass"""
        result = CorrelationResult(
            dimension="test",
            value="test",
            trades=10,
            wins=5,
            winrate=50.0,
            total_pnl=100.0,
            avg_pnl=10.0,
            recommendation="NEUTRAL"
        )
        assert hasattr(result, '__dataclass_fields__')

    def test_optimization_suggestion_dataclass(self):
        """Test OptimizationSuggestion est dataclass"""
        suggestion = OptimizationSuggestion(
            parameter="test",
            current_value=1.0,
            suggested_value=2.0,
            expected_improvement="test",
            confidence="MEDIUM",
            based_on_trades=100
        )
        assert hasattr(suggestion, '__dataclass_fields__')

    def test_correlation_engine_class_methods(self):
        """Test méthodes de classe CorrelationEngine"""
        engine = CorrelationEngine()
        assert hasattr(engine, '_get_db_connection')
        assert hasattr(engine, '_release_connection')

    def test_correlation_result_all_fields_present(self):
        """Test tous les champs présents CorrelationResult"""
        result = CorrelationResult(
            dimension="test",
            value="test",
            trades=10,
            wins=5,
            winrate=50.0,
            total_pnl=100.0,
            avg_pnl=10.0,
            recommendation="NEUTRAL"
        )
        fields = ['dimension', 'value', 'trades', 'wins', 'winrate', 
                  'total_pnl', 'avg_pnl', 'recommendation']
        for field in fields:
            assert hasattr(result, field)

    def test_optimization_suggestion_all_fields_present(self):
        """Test tous les champs présents OptimizationSuggestion"""
        suggestion = OptimizationSuggestion(
            parameter="test",
            current_value=1.0,
            suggested_value=2.0,
            expected_improvement="test",
            confidence="MEDIUM",
            based_on_trades=100
        )
        fields = ['parameter', 'current_value', 'suggested_value', 
                  'expected_improvement', 'confidence', 'based_on_trades']
        for field in fields:
            assert hasattr(suggestion, field)

    def test_correlation_result_numeric_fields(self):
        """Test champs numériques CorrelationResult"""
        result = CorrelationResult(
            dimension="test",
            value="test",
            trades=100,
            wins=60,
            winrate=60.0,
            total_pnl=1500.0,
            avg_pnl=15.0,
            recommendation="FAVOR"
        )
        assert isinstance(result.trades, int)
        assert isinstance(result.wins, int)
        assert isinstance(result.winrate, float)
        assert isinstance(result.total_pnl, float)
        assert isinstance(result.avg_pnl, float)

    def test_optimization_suggestion_numeric_fields(self):
        """Test champs numériques OptimizationSuggestion"""
        suggestion = OptimizationSuggestion(
            parameter="test",
            current_value=1.5,
            suggested_value=2.5,
            expected_improvement="test",
            confidence="HIGH",
            based_on_trades=200
        )
        assert isinstance(suggestion.current_value, float)
        assert isinstance(suggestion.suggested_value, float)
        assert isinstance(suggestion.based_on_trades, int)

    def test_correlation_result_string_fields(self):
        """Test champs string CorrelationResult"""
        result = CorrelationResult(
            dimension="session",
            value="ASIA",
            trades=10,
            wins=5,
            winrate=50.0,
            total_pnl=100.0,
            avg_pnl=10.0,
            recommendation="NEUTRAL"
        )
        assert isinstance(result.dimension, str)
        assert isinstance(result.value, str)
        assert isinstance(result.recommendation, str)

    def test_optimization_suggestion_string_fields(self):
        """Test champs string OptimizationSuggestion"""
        suggestion = OptimizationSuggestion(
            parameter="min_score",
            current_value=2.0,
            suggested_value=1.5,
            expected_improvement="+5% winrate",
            confidence="MEDIUM",
            based_on_trades=100
        )
        assert isinstance(suggestion.parameter, str)
        assert isinstance(suggestion.expected_improvement, str)
        assert isinstance(suggestion.confidence, str)
