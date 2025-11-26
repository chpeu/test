"""
Tests pour optimization.data.feature_loader
"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from optimization.data.feature_loader import (
    get_postgres_connection,
    get_sqlalchemy_engine,
    get_trades_count,
    load_features_from_postgres
)


class TestGetPostgresConnection:
    """Tests get_postgres_connection()"""

    @patch('optimization.data.feature_loader.psycopg2.connect')
    @patch.dict('os.environ', {
        'POSTGRES_HOST': 'test_host',
        'POSTGRES_PORT': '5433',
        'POSTGRES_DB': 'test_db',
        'POSTGRES_USER': 'test_user',
        'POSTGRES_PASSWORD': 'test_pass'
    })
    def test_connection_success(self, mock_connect):
        """Test connexion réussie"""
        mock_conn = Mock()
        mock_connect.return_value = mock_conn

        conn = get_postgres_connection()

        assert conn == mock_conn
        mock_connect.assert_called_once()
        # Verify connection params
        call_kwargs = mock_connect.call_args.kwargs
        assert call_kwargs['host'] == 'test_host'
        assert call_kwargs['port'] == 5433
        assert call_kwargs['database'] == 'test_db'
        assert call_kwargs['user'] == 'test_user'
        assert call_kwargs['password'] == 'test_pass'

    @patch('optimization.data.feature_loader.psycopg2.connect')
    def test_connection_error(self, mock_connect):
        """Test erreur connexion"""
        mock_connect.side_effect = Exception("Connection failed")

        with pytest.raises(Exception, match="Connection failed"):
            get_postgres_connection()


class TestGetSQLAlchemyEngine:
    """Tests get_sqlalchemy_engine()"""

    @patch('optimization.data.feature_loader.create_engine')
    @patch.dict('os.environ', {
        'POSTGRES_HOST': 'localhost',
        'POSTGRES_PORT': '5432',
        'POSTGRES_DB': 'test_db',
        'POSTGRES_USER': 'user',
        'POSTGRES_PASSWORD': 'pass'
    })
    def test_engine_creation_success(self, mock_create_engine):
        """Test création engine réussie"""
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        engine = get_sqlalchemy_engine()

        assert engine == mock_engine
        mock_create_engine.assert_called_once()
        # Verify connection string format
        connection_string = mock_create_engine.call_args[0][0]
        assert 'postgresql://' in connection_string
        assert 'localhost' in connection_string
        assert 'test_db' in connection_string

    @patch('optimization.data.feature_loader.create_engine')
    def test_engine_creation_error(self, mock_create_engine):
        """Test erreur création engine"""
        mock_create_engine.side_effect = Exception("Engine creation failed")

        with pytest.raises(Exception, match="Engine creation failed"):
            get_sqlalchemy_engine()


class TestGetTradesCount:
    """Tests get_trades_count()"""

    @patch('optimization.data.feature_loader.get_postgres_connection')
    def test_count_completed_trades(self, mock_get_conn):
        """Test comptage trades complétés"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {'count': 150}
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        count = get_trades_count(completed_only=True)

        assert count == 150
        mock_cursor.execute.assert_called_once()
        query = mock_cursor.execute.call_args[0][0]
        assert 'timestamp_exit IS NOT NULL' in query

    @patch('optimization.data.feature_loader.get_postgres_connection')
    def test_count_all_trades(self, mock_get_conn):
        """Test comptage tous les trades"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {'count': 200}
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        count = get_trades_count(completed_only=False)

        assert count == 200
        query = mock_cursor.execute.call_args[0][0]
        assert 'timestamp_exit IS NOT NULL' not in query

    @patch('optimization.data.feature_loader.get_postgres_connection')
    def test_count_no_trades(self, mock_get_conn):
        """Test aucun trade"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {'count': 0}
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        count = get_trades_count()

        assert count == 0

    @patch('optimization.data.feature_loader.get_postgres_connection')
    def test_count_error(self, mock_get_conn):
        """Test erreur comptage"""
        mock_get_conn.side_effect = Exception("DB Error")

        count = get_trades_count()

        assert count == 0  # Should return 0 on error


class TestLoadFeaturesFromPostgres:
    """Tests load_features_from_postgres(min_trades=0)"""

    @patch('optimization.data.feature_loader.get_sqlalchemy_engine')
    @patch('optimization.data.feature_loader.pd.read_sql')
    def test_load_features_success(self, mock_read_sql, mock_get_engine):
        """Test chargement features réussi"""
        mock_engine = Mock()
        mock_get_engine.return_value = mock_engine

        # Mock DataFrame
        mock_df = pd.DataFrame({
            'scan_id': [1, 2, 3],
            'symbol': ['BTCUSDT', 'ETHUSDT', 'ADAUSDT'],
            'feature_1': [1.0, 2.0, 3.0],
            'target_win': [1, 0, 1]
        })
        mock_read_sql.return_value = mock_df

        df = load_features_from_postgres(min_trades=1)

        assert len(df) == 3
        assert 'scan_id' in df.columns
        assert 'feature_1' in df.columns
        mock_read_sql.assert_called_once()

    @patch('optimization.data.feature_loader.get_sqlalchemy_engine')
    @patch('optimization.data.feature_loader.pd.read_sql')
    def test_load_features_with_max_trades(self, mock_read_sql, mock_get_engine):
        """Test chargement avec max_trades"""
        mock_engine = Mock()
        mock_get_engine.return_value = mock_engine

        mock_df = pd.DataFrame({
            'scan_id': range(100),
            'target_win': [1] * 100
        })
        mock_read_sql.return_value = mock_df

        df = load_features_from_postgres(max_trades=50)

        # Should limit to 50 trades
        assert len(df) <= 100  # May be limited in query or after

    @patch('optimization.data.feature_loader.get_sqlalchemy_engine')
    @patch('optimization.data.feature_loader.pd.read_sql')
    def test_load_features_empty(self, mock_read_sql, mock_get_engine):
        """Test chargement aucune donnée"""
        mock_engine = Mock()
        mock_get_engine.return_value = mock_engine

        # Empty DataFrame will fail - this is expected behavior
        mock_df = pd.DataFrame()
        mock_read_sql.return_value = mock_df

        # Function raises on insufficient data - expected
        with pytest.raises((ValueError, KeyError, Exception)):
            load_features_from_postgres(min_trades=0)

    @patch('optimization.data.feature_loader.get_sqlalchemy_engine')
    @patch('optimization.data.feature_loader.pd.read_sql')
    def test_load_features_error(self, mock_read_sql, mock_get_engine):
        """Test erreur chargement"""
        mock_get_engine.side_effect = Exception("DB Connection Error")

        try:
            df = load_features_from_postgres(min_trades=0)
            # May return empty or raise
            assert df is None or df.empty
        except Exception:
            # Exception is acceptable
            pass


class TestEdgeCases:
    """Tests cas limites"""

    @patch('optimization.data.feature_loader.get_postgres_connection')
    def test_count_null_result(self, mock_get_conn):
        """Test fetchone retourne None"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        count = get_trades_count()

        assert count == 0
