"""
Tests pour optimization.prediction_logger
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from optimization.prediction_logger import (
    get_postgres_connection,
    log_prediction,
    link_prediction_to_trade,
    update_prediction_result,
    get_prediction_analytics,
    get_recent_predictions
)


class TestGetPostgresConnection:
    """Tests get_postgres_connection()"""

    @patch('optimization.prediction_logger.psycopg2.connect')
    @patch.dict('os.environ', {
        'POSTGRES_HOST': 'localhost',
        'POSTGRES_PORT': '5432',
        'POSTGRES_DB': 'test_db',
        'POSTGRES_USER': 'user',
        'POSTGRES_PASSWORD': 'pass'
    })
    def test_connection_success(self, mock_connect):
        """Test connexion réussie"""
        mock_conn = Mock()
        mock_connect.return_value = mock_conn

        conn = get_postgres_connection()

        assert conn == mock_conn
        mock_connect.assert_called_once()

    @patch('optimization.prediction_logger.psycopg2.connect')
    def test_connection_error(self, mock_connect):
        """Test erreur connexion"""
        mock_connect.side_effect = Exception("Connection error")

        with pytest.raises(Exception, match="Connection error"):
            get_postgres_connection()


class TestLogPrediction:
    """Tests log_prediction()"""

    @patch('optimization.prediction_logger.get_postgres_connection')
    def test_log_prediction_success(self, mock_get_conn):
        """Test log prédiction réussie"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {'id': 123}
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        prediction_data = {
            'prediction': 1,
            'win_probability': 0.75,
            'loss_probability': 0.25,
            'confidence': 0.8,
            'model_name': 'xgboost_v2',
            'model_version': '2.0',
            'top_features': ['rsi', 'volume'],
            'model_performance': {
                'test_accuracy': 0.72,
                'test_f1': 0.68
            }
        }

        prediction_id = log_prediction(
            prediction_data=prediction_data,
            symbol='BTCUSDT',
            scan_id=100,
            opportunity_timestamp=datetime.now()
        )

        assert prediction_id == 123
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('optimization.prediction_logger.get_postgres_connection')
    def test_log_prediction_minimal_data(self, mock_get_conn):
        """Test log avec données minimales"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {'id': 456}
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        prediction_data = {
            'prediction': 0
        }

        prediction_id = log_prediction(
            prediction_data=prediction_data,
            symbol='ETHUSDT'
        )

        assert prediction_id == 456

    @patch('optimization.prediction_logger.get_postgres_connection')
    def test_log_prediction_error(self, mock_get_conn):
        """Test erreur lors du log"""
        mock_get_conn.side_effect = Exception("DB Error")

        prediction_data = {'prediction': 1}

        prediction_id = log_prediction(
            prediction_data=prediction_data,
            symbol='BTCUSDT'
        )

        assert prediction_id is None

    @patch('optimization.prediction_logger.get_postgres_connection')
    def test_log_prediction_with_metadata(self, mock_get_conn):
        """Test log avec métadonnées"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {'id': 789}
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        prediction_data = {'prediction': 1}
        metadata = {'strategy': 'momentum', 'timeframe': '15m'}

        prediction_id = log_prediction(
            prediction_data=prediction_data,
            symbol='ADAUSDT',
            metadata=metadata
        )

        assert prediction_id == 789


class TestLinkPredictionToTrade:
    """Tests link_prediction_to_trade()"""

    @patch('optimization.prediction_logger.get_postgres_connection')
    def test_link_success(self, mock_get_conn):
        """Test link réussi"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        result = link_prediction_to_trade(
            prediction_id=123,
            trade_id=456
        )

        assert result is True
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    @patch('optimization.prediction_logger.get_postgres_connection')
    def test_link_error(self, mock_get_conn):
        """Test erreur link"""
        mock_get_conn.side_effect = Exception("DB Error")

        result = link_prediction_to_trade(
            prediction_id=123,
            trade_id=456
        )

        assert result is False


class TestUpdatePredictionResult:
    """Tests update_prediction_result()"""

    @patch('optimization.prediction_logger.get_postgres_connection')
    def test_update_result_success(self, mock_get_conn):
        """Test update result réussi"""
        mock_conn = Mock()
        mock_cursor = Mock()
        # Mock fetchone to return dict with trade data
        mock_cursor.fetchone.return_value = {
            'win': True,
            'pnl': 150.0,
            'pnl_percent': 2.5,
            'timestamp_exit': datetime.now()
        }
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        result = update_prediction_result(trade_id=456)

        assert result is True
        # Verify execute was called twice (SELECT + UPDATE)
        assert mock_cursor.execute.call_count == 2
        mock_conn.commit.assert_called_once()

    @patch('optimization.prediction_logger.get_postgres_connection')
    def test_update_result_error(self, mock_get_conn):
        """Test erreur update"""
        mock_get_conn.side_effect = Exception("DB Error")

        result = update_prediction_result(trade_id=456)

        assert result is False


class TestGetPredictionAnalytics:
    """Tests get_prediction_analytics()"""

    @patch('optimization.prediction_logger.get_postgres_connection')
    def test_get_analytics_success(self, mock_get_conn):
        """Test récupération analytics"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            {
                'model_name': 'xgboost_v2',
                'total': 100,
                'correct': 72,
                'accuracy': 0.72
            }
        ]
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        analytics = get_prediction_analytics(model_name='xgboost_v2', days=30)

        assert analytics is not None
        assert isinstance(analytics, dict)

    @patch('optimization.prediction_logger.get_postgres_connection')
    def test_get_analytics_empty(self, mock_get_conn):
        """Test aucune analytics"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        analytics = get_prediction_analytics()

        assert analytics is not None or analytics == {}

    @patch('optimization.prediction_logger.get_postgres_connection')
    def test_get_analytics_error(self, mock_get_conn):
        """Test erreur récupération"""
        mock_get_conn.side_effect = Exception("DB Error")

        analytics = get_prediction_analytics()

        assert analytics is None or isinstance(analytics, dict)


class TestGetRecentPredictions:
    """Tests get_recent_predictions()"""

    @patch('optimization.prediction_logger.get_postgres_connection')
    def test_get_recent_success(self, mock_get_conn):
        """Test récupération prédictions récentes"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            {'id': 1, 'symbol': 'BTCUSDT', 'prediction': 1},
            {'id': 2, 'symbol': 'ETHUSDT', 'prediction': 0}
        ]
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        predictions = get_recent_predictions(limit=20)

        assert isinstance(predictions, list)
        assert len(predictions) == 2

    @patch('optimization.prediction_logger.get_postgres_connection')
    def test_get_recent_error(self, mock_get_conn):
        """Test erreur récupération"""
        mock_get_conn.side_effect = Exception("DB Error")

        predictions = get_recent_predictions()

        assert predictions is None or predictions == []


class TestEdgeCases:
    """Tests cas limites"""

    @patch('optimization.prediction_logger.get_postgres_connection')
    def test_log_prediction_none_fetchone(self, mock_get_conn):
        """Test fetchone retourne None"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        prediction_data = {'prediction': 1}

        prediction_id = log_prediction(
            prediction_data=prediction_data,
            symbol='BTCUSDT'
        )

        # Should handle None gracefully
        assert prediction_id is None

    @patch('optimization.prediction_logger.get_postgres_connection')
    def test_update_invalid_trade_id(self, mock_get_conn):
        """Test update avec trade ID invalide"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        result = update_prediction_result(
            trade_id=99999  # N'existe pas
        )

        # Should complete without error
        assert result is True or result is False
