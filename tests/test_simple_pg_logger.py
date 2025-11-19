"""
Tests for core/simple_pg_logger.py
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import os
from core.simple_pg_logger import SimplePGLogger, PSYCOPG2_AVAILABLE


class TestSimplePGLogger:
    """Test cases for SimplePGLogger"""

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', False)
    def test_init_without_psycopg2(self):
        """Test initialization when psycopg2 is not available"""
        logger = SimplePGLogger()
        assert logger.enabled is False

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_init_with_psycopg2_success(self, mock_psycopg2):
        """Test successful initialization with psycopg2"""
        mock_conn = Mock()
        mock_psycopg2.connect.return_value = mock_conn

        with patch.dict(os.environ, {
            'POSTGRES_HOST': 'testhost',
            'POSTGRES_PORT': '5433',
            'POSTGRES_DB': 'testdb',
            'POSTGRES_USER': 'testuser',
            'POSTGRES_PASSWORD': 'testpass'
        }):
            logger = SimplePGLogger()

            assert logger.enabled is True
            assert logger.conn == mock_conn
            mock_psycopg2.connect.assert_called_once_with(
                host='testhost',
                port=5433,
                dbname='testdb',
                user='testuser',
                password='testpass',
                client_encoding='utf8'
            )

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_init_with_default_env(self, mock_psycopg2):
        """Test initialization with default environment variables"""
        mock_conn = Mock()
        mock_psycopg2.connect.return_value = mock_conn

        with patch.dict(os.environ, {}, clear=True):
            logger = SimplePGLogger()

            mock_psycopg2.connect.assert_called_once_with(
                host='localhost',
                port=5432,
                dbname='trade_cursor_ml',
                user='postgres',
                password='',
                client_encoding='utf8'
            )

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_init_connection_failure(self, mock_psycopg2):
        """Test initialization when connection fails"""
        mock_psycopg2.connect.side_effect = Exception("Connection failed")

        logger = SimplePGLogger()
        assert logger.enabled is False

    def test_log_scan_simple_disabled(self):
        """Test log_scan_simple when logger is disabled"""
        with patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', False):
            logger = SimplePGLogger()
            result = logger.log_scan_simple("BTC_USDT", {})
            assert result is False

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_log_scan_simple_connection_closed(self, mock_psycopg2):
        """Test log_scan_simple when connection is closed"""
        mock_conn = Mock()
        mock_conn.closed = True
        mock_psycopg2.connect.return_value = mock_conn

        logger = SimplePGLogger()
        scan_data = {'market_data': {'price': 50000}}
        result = logger.log_scan_simple("BTC_USDT", scan_data)

        assert result is False
        assert logger.enabled is False

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_log_scan_simple_missing_price(self, mock_psycopg2):
        """Test log_scan_simple when price is missing"""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        logger = SimplePGLogger()
        scan_data = {'market_data': {}}
        result = logger.log_scan_simple("BTC_USDT", scan_data)

        assert result is False
        mock_cursor.close.assert_called_once()

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_log_scan_simple_price_dict_extraction(self, mock_psycopg2):
        """Test price extraction from dict"""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        logger = SimplePGLogger()

        # Test with price as dict
        scan_data = {
            'market_data': {'price': {'price': 50000}},
            'is_opportunity': True
        }
        result = logger.log_scan_simple("BTC_USDT", scan_data)

        assert result is True
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_log_scan_simple_price_dict_lastPrice(self, mock_psycopg2):
        """Test price extraction from dict with lastPrice key"""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        logger = SimplePGLogger()
        scan_data = {
            'market_data': {'price': {'lastPrice': 45000}}
        }
        result = logger.log_scan_simple("ETH_USDT", scan_data)

        assert result is True

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_log_scan_simple_invalid_price_string(self, mock_psycopg2):
        """Test with invalid price string that can't be converted"""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        logger = SimplePGLogger()
        scan_data = {
            'market_data': {'price': 'invalid_price'}
        }
        result = logger.log_scan_simple("BTC_USDT", scan_data)

        assert result is False

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_log_scan_simple_valid_price_string(self, mock_psycopg2):
        """Test with valid price string that can be converted"""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        logger = SimplePGLogger()
        scan_data = {
            'market_data': {'price': '50000.5'}
        }
        result = logger.log_scan_simple("BTC_USDT", scan_data)

        assert result is True

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_log_scan_simple_with_rsi_from_indicators(self, mock_psycopg2):
        """Test RSI extraction from indicators_1m"""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        logger = SimplePGLogger()
        scan_data = {
            'market_data': {'price': 50000},
            'indicators_1m': {'rsi': 65.5}
        }
        result = logger.log_scan_simple("BTC_USDT", scan_data)

        assert result is True
        # Verify RSI was passed correctly
        call_args = mock_cursor.execute.call_args[0]
        assert 65.5 in call_args[1]

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_log_scan_simple_rsi_fallback_scan_data(self, mock_psycopg2):
        """Test RSI fallback from scan_data directly"""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        logger = SimplePGLogger()
        scan_data = {
            'market_data': {'price': 50000},
            'rsi': 70.0
        }
        result = logger.log_scan_simple("BTC_USDT", scan_data)

        assert result is True

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_log_scan_simple_rsi_fallback_market_data(self, mock_psycopg2):
        """Test RSI fallback from market_data"""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        logger = SimplePGLogger()
        scan_data = {
            'market_data': {'price': 50000, 'rsi': 55.0}
        }
        result = logger.log_scan_simple("BTC_USDT", scan_data)

        assert result is True

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_log_scan_simple_rsi_fallback_analysis_1m(self, mock_psycopg2):
        """Test RSI fallback from analysis_1m"""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        logger = SimplePGLogger()
        scan_data = {
            'market_data': {'price': 50000},
            'analysis_1m': {'rsi': 45.0}
        }
        result = logger.log_scan_simple("BTC_USDT", scan_data)

        assert result is True

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_log_scan_simple_score_from_scores(self, mock_psycopg2):
        """Test score_total extraction from scores"""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        logger = SimplePGLogger()
        scan_data = {
            'market_data': {'price': 50000},
            'scores': {'score_total': 85.0}
        }
        result = logger.log_scan_simple("BTC_USDT", scan_data)

        assert result is True

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_log_scan_simple_score_totalScore_fallback(self, mock_psycopg2):
        """Test score fallback to totalScore"""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        logger = SimplePGLogger()
        scan_data = {
            'market_data': {'price': 50000},
            'scores': {'totalScore': 90.0}
        }
        result = logger.log_scan_simple("BTC_USDT", scan_data)

        assert result is True

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_log_scan_simple_score_from_scan_data(self, mock_psycopg2):
        """Test score fallback from scan_data directly"""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        logger = SimplePGLogger()
        scan_data = {
            'market_data': {'price': 50000},
            'score_total': 75.0
        }
        result = logger.log_scan_simple("BTC_USDT", scan_data)

        assert result is True

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_log_scan_simple_score_from_long_short(self, mock_psycopg2):
        """Test score extraction from long_score/short_score"""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        logger = SimplePGLogger()
        scan_data = {
            'market_data': {'price': 50000},
            'long_score': 80.0,
            'short_score': 60.0
        }
        result = logger.log_scan_simple("BTC_USDT", scan_data)

        assert result is True
        # Should use max of long_score and short_score
        call_args = mock_cursor.execute.call_args[0]
        assert 80.0 in call_args[1]

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_log_scan_simple_score_from_analysis_1m_long_short(self, mock_psycopg2):
        """Test score from analysis_1m long_score/short_score"""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        logger = SimplePGLogger()
        scan_data = {
            'market_data': {'price': 50000},
            'analysis_1m': {
                'long_score': 70.0,
                'short_score': 85.0
            }
        }
        result = logger.log_scan_simple("BTC_USDT", scan_data)

        assert result is True

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_log_scan_simple_score_from_analysis_5m(self, mock_psycopg2):
        """Test score from analysis_5m"""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        logger = SimplePGLogger()
        scan_data = {
            'market_data': {'price': 50000},
            'analysis_5m': {
                'long_score': 65.0
            }
        }
        result = logger.log_scan_simple("BTC_USDT", scan_data)

        assert result is True

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_log_scan_simple_execute_exception(self, mock_psycopg2):
        """Test exception during execute"""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = Exception("Database error")
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        logger = SimplePGLogger()
        scan_data = {
            'market_data': {'price': 50000}
        }
        result = logger.log_scan_simple("BTC_USDT", scan_data)

        assert result is False
        mock_conn.rollback.assert_called_once()

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_log_scan_simple_rollback_exception(self, mock_psycopg2):
        """Test exception during rollback"""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = Exception("Database error")
        mock_conn.rollback.side_effect = Exception("Rollback error")
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        logger = SimplePGLogger()
        scan_data = {
            'market_data': {'price': 50000}
        }
        result = logger.log_scan_simple("BTC_USDT", scan_data)

        assert result is False

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_log_scan_simple_reconnect_on_closed_connection(self, mock_psycopg2):
        """Test reconnection when connection is closed after error"""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_cursor = Mock()

        # Simulate connection becoming closed after execute error
        def execute_with_connection_close(*args, **kwargs):
            mock_conn.closed = True  # Connection closes due to error
            raise Exception("Database error")

        mock_cursor.execute.side_effect = execute_with_connection_close
        mock_conn.cursor.return_value = mock_cursor

        # First call returns mock_conn, second call returns new connection
        mock_new_conn = Mock()
        mock_psycopg2.connect.side_effect = [mock_conn, mock_new_conn]

        logger = SimplePGLogger()

        scan_data = {
            'market_data': {'price': 50000}
        }
        result = logger.log_scan_simple("BTC_USDT", scan_data)

        assert result is False
        # Should attempt reconnection
        assert mock_psycopg2.connect.call_count == 2

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_log_scan_simple_reconnect_failure(self, mock_psycopg2):
        """Test failed reconnection attempt"""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = Exception("Database error")
        mock_conn.cursor.return_value = mock_cursor

        # First call succeeds, reconnection fails
        mock_psycopg2.connect.side_effect = [
            mock_conn,
            Exception("Reconnection failed")
        ]

        logger = SimplePGLogger()
        mock_conn.closed = True  # Simulate connection closed after error

        scan_data = {
            'market_data': {'price': 50000}
        }
        result = logger.log_scan_simple("BTC_USDT", scan_data)

        assert result is False
        assert logger.enabled is False

    @patch('core.simple_pg_logger.PSYCOPG2_AVAILABLE', True)
    @patch('core.simple_pg_logger.psycopg2')
    def test_log_scan_simple_complete_flow(self, mock_psycopg2):
        """Test complete successful flow with all data"""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        logger = SimplePGLogger()
        scan_data = {
            'market_data': {'price': 50000.50},
            'indicators_1m': {'rsi': 65.5},
            'scores': {'score_total': 85.0},
            'is_opportunity': True
        }
        result = logger.log_scan_simple("BTC_USDT", scan_data)

        assert result is True
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()

        # Verify parameters
        call_args = mock_cursor.execute.call_args[0]
        params = call_args[1]
        assert params[0] == "BTC_USDT"
        assert params[1] == 50000.50
        assert params[2] == 65.5
        assert params[3] == 85.0
        assert params[4] is True
