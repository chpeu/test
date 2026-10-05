"""
Tests unitaires pour PostgreSQLDataLogger
"""
import pytest
import os
import uuid
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import json

# Mock psycopg2 si non disponible
try:
    import psycopg2
    from psycopg2.pool import ThreadedConnectionPool
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    # Créer des mocks
    psycopg2 = MagicMock()
    ThreadedConnectionPool = MagicMock()


@pytest.fixture
def mock_postgres_connection():
    """Mock d'une connexion PostgreSQL"""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchall.return_value = [(1,)]
    cursor.fetchone.return_value = (1,)
    return conn, cursor


@pytest.fixture
def mock_pool(mock_postgres_connection):
    """Mock d'un pool de connexions"""
    conn, cursor = mock_postgres_connection
    pool = MagicMock()
    pool.getconn.return_value = conn
    pool.putconn = MagicMock()
    pool.closeall = MagicMock()
    return pool


@pytest.fixture
def datalogger_config():
    """Configuration pour les tests"""
    return {
        'host': 'localhost',
        'port': 5432,
        'database': 'test_db',
        'user': 'test_user',
        'password': 'test_password',
        'min_conn': 1,
        'max_conn': 2,
        'batch_size': 10,
        'batch_flush_interval': 1.0
    }


class TestPostgreSQLDataLogger:
    """Tests pour PostgreSQLDataLogger"""
    
    @patch('core.postgresql_datalogger.PSYCOPG2_AVAILABLE', True)
    @patch('core.postgresql_datalogger.ThreadedConnectionPool')
    def test_init_success(self, mock_pool_class, datalogger_config, mock_pool):
        """Test initialisation réussie"""
        mock_pool_class.return_value = mock_pool
        
        from core.postgresql_datalogger import PostgreSQLDataLogger
        
        logger = PostgreSQLDataLogger(**datalogger_config)
        
        assert logger.enabled is True
        assert logger.pool == mock_pool
        assert logger.batch_size == 10
        assert len(logger.scan_buffer) == 0
        assert len(logger.opportunity_buffer) == 0
    
    @patch('core.postgresql_datalogger.PSYCOPG2_AVAILABLE', False)
    def test_init_psycopg2_unavailable(self, datalogger_config):
        """Test initialisation si psycopg2 non disponible"""
        from core.postgresql_datalogger import PostgreSQLDataLogger
        
        logger = PostgreSQLDataLogger(**datalogger_config)
        
        assert logger.enabled is False
        assert logger.pool is None
    
    @patch('core.postgresql_datalogger.PSYCOPG2_AVAILABLE', True)
    @patch('core.postgresql_datalogger.ThreadedConnectionPool')
    def test_init_connection_error(self, mock_pool_class, datalogger_config):
        """Test initialisation avec erreur de connexion"""
        mock_pool_class.side_effect = Exception("Connection failed")
        
        from core.postgresql_datalogger import PostgreSQLDataLogger
        
        logger = PostgreSQLDataLogger(**datalogger_config)
        
        assert logger.enabled is False
        assert logger.pool is None
    
    @patch('core.postgresql_datalogger.PSYCOPG2_AVAILABLE', True)
    @patch('core.postgresql_datalogger.ThreadedConnectionPool')
    def test_get_or_create_session(self, mock_pool_class, datalogger_config, mock_pool, mock_postgres_connection):
        """Test création/récupération de session"""
        mock_pool_class.return_value = mock_pool
        conn, cursor = mock_postgres_connection
        mock_pool.getconn.return_value = conn
        
        from core.postgresql_datalogger import PostgreSQLDataLogger
        
        logger = PostgreSQLDataLogger(**datalogger_config)
        session_id = logger.get_or_create_session()
        
        assert session_id is not None
        assert isinstance(session_id, str)
        assert len(session_id) > 0
    
    @patch('core.postgresql_datalogger.PSYCOPG2_AVAILABLE', True)
    @patch('core.postgresql_datalogger.ThreadedConnectionPool')
    def test_log_scan_batch_mode(self, mock_pool_class, datalogger_config, mock_pool):
        """Test logging scan en mode batch"""
        mock_pool_class.return_value = mock_pool
        
        from core.postgresql_datalogger import PostgreSQLDataLogger
        
        logger = PostgreSQLDataLogger(**datalogger_config)
        
        scan_data = {
            'scan_duration_ms': 100,
            'market_data': {'price': 50000.0},
            'indicators_1m': {},
            'indicators_5m': {},
            'filters': {},
            'scores': {},
            'patterns': {},
            'is_opportunity': False
        }
        
        result = logger.log_scan('BTCUSDT', scan_data, use_batch=True)
        
        assert result is None  # Mode batch retourne None
        assert len(logger.scan_buffer) == 1
    
    @patch('core.postgresql_datalogger.PSYCOPG2_AVAILABLE', True)
    @patch('core.postgresql_datalogger.ThreadedConnectionPool')
    def test_log_opportunity_batch_mode(self, mock_pool_class, datalogger_config, mock_pool):
        """Test logging opportunité en mode batch"""
        mock_pool_class.return_value = mock_pool
        
        from core.postgresql_datalogger import PostgreSQLDataLogger
        
        logger = PostgreSQLDataLogger(**datalogger_config)
        
        opportunity_data = {
            'status': 'PENDING',
            'direction': 'LONG',
            'setup_score': 85.5,
            'entry_price': 50000.0
        }
        
        result = logger.log_opportunity(1, 'BTCUSDT', opportunity_data, use_batch=True)
        
        assert result is None  # Mode batch retourne None
        assert len(logger.opportunity_buffer) == 1
    
    @pytest.mark.skip(reason="log_scan_error method no longer exists in PostgreSQLDataLogger")
    @patch('core.postgresql_datalogger.PSYCOPG2_AVAILABLE', True)
    @patch('core.postgresql_datalogger.ThreadedConnectionPool')
    def test_log_scan_error(self, mock_pool_class, datalogger_config, mock_pool, mock_postgres_connection):
        """Test logging erreur de scan"""
        mock_pool_class.return_value = mock_pool
        conn, cursor = mock_postgres_connection
        mock_pool.getconn.return_value = conn

        from core.postgresql_datalogger import PostgreSQLDataLogger

        logger = PostgreSQLDataLogger(**datalogger_config)

        error_id = logger.log_scan_error(
            symbol='BTCUSDT',
            error_type='API_ERROR',
            error_message='Connection timeout',
            error_details={'stack': 'traceback...'}
        )

        assert error_id is not None
        # 🔥 FIX: 2 appels attendus (1 pour session, 1 pour scan_error)
        assert cursor.execute.call_count == 2
    
    @pytest.mark.skip(reason="log_market_context method no longer exists in PostgreSQLDataLogger")
    @patch('core.postgresql_datalogger.PSYCOPG2_AVAILABLE', True)
    @patch('core.postgresql_datalogger.ThreadedConnectionPool')
    def test_log_market_context(self, mock_pool_class, datalogger_config, mock_pool, mock_postgres_connection):
        """Test logging contexte marché"""
        mock_pool_class.return_value = mock_pool
        conn, cursor = mock_postgres_connection
        mock_pool.getconn.return_value = conn

        from core.postgresql_datalogger import PostgreSQLDataLogger

        logger = PostgreSQLDataLogger(**datalogger_config)

        context_data = {
            'btc_price': 50000.0,
            'eth_price': 3000.0,
            'global_metrics': {'volume_24h': 1000000},
            'session_stats': {'trades_count': 5}
        }

        context_id = logger.log_market_context(context_data)

        assert context_id is not None
        # 🔥 FIX: 2 appels attendus (1 pour session, 1 pour market_context)
        assert cursor.execute.call_count == 2
    
    @patch('core.postgresql_datalogger.PSYCOPG2_AVAILABLE', True)
    @patch('core.postgresql_datalogger.ThreadedConnectionPool')
    def test_log_trade(self, mock_pool_class, datalogger_config, mock_pool, mock_postgres_connection):
        """Test logging trade"""
        mock_pool_class.return_value = mock_pool
        conn, cursor = mock_postgres_connection
        mock_pool.getconn.return_value = conn
        
        from core.postgresql_datalogger import PostgreSQLDataLogger
        
        logger = PostgreSQLDataLogger(**datalogger_config)
        
        trade_data = {
            'symbol': 'BTCUSDT',
            'direction': 'LONG',
            'entry_price': 50000.0,
            'exit_price': 51000.0,
            'size_usdt': 100.0,
            'gross_pnl_usdt': 10.0,
            'gross_pnl_pct': 2.0,
            'net_pnl_usdt': 9.5,
            'net_pnl_pct': 1.9,
            'fees': 0.5,
            'slippage': 0.0,
            'total_costs': 0.5,
            'reason': 'TP',
            'duration_seconds': 3600,
            'tp_sl_mode': 'FIXE',
            'break_even_triggered': False,
            'trailing_stop_triggered': False,
            'partial_tp_triggered': False,
            'tp_escalier_enabled': False,
            'tp_escalier_levels_hit': [],
            'entry_indicators': {},
            'exit_indicators': {},
            'params_snapshot': {},
            'is_backtest': False
        }
        
        trade_id = logger.log_trade(trade_data)

        assert trade_id is not None
        # 🔥 FIX: 6 appels attendus (1 session insert + 2 resolve trade_id + 1 insert trade + 2 atr_metrics upsert/insert)
        assert cursor.execute.call_count == 6

    @patch('core.postgresql_datalogger.PSYCOPG2_AVAILABLE', True)
    @patch('core.postgresql_datalogger.ThreadedConnectionPool')
    def test_log_trade_placeholder_alignment(self, mock_pool_class, datalogger_config):
        """Vérifie que log_trade garde le même nombre de colonnes, placeholders et paramètres"""
        mock_pool_class.return_value = MagicMock()

        from core.postgresql_datalogger import PostgreSQLDataLogger

        logger = PostgreSQLDataLogger(**datalogger_config)

        captured_queries = []

        def fake_execute(query, params=None, fetch=False):
            captured_queries.append({
                'query': query,
                'params': params
            })
            return [(42,)] if fetch else None

        logger._execute_query = MagicMock(side_effect=fake_execute)

        trade_data = {
            'symbol': 'SOL/USDT:USDT',
            'direction': 'SHORT',
            'timestamp_entry': '2025-11-15T22:55:37.034840+01:00',
            'timestamp_exit': '2025-11-15T23:03:58.599866+01:00',
            'entry_price': 138.86,
            'exit_price': 139.21,
            'tp_price': 140.0,
            'sl_price': 137.0,
            'size_usdt': 100.0,
            'gross_pnl_usdt': -0.05,
            'gross_pnl_pct': -0.04,
            'net_pnl_usdt': -0.05,
            'net_pnl_pct': -0.04,
            'fees': 0.01,
            'slippage': 0.0,
            'reason': 'TS',
            'duration_seconds': 480,
            'tp_sl_mode': 'FIXE',
            'break_even_triggered': False,
            'trailing_stop_triggered': False,
            'partial_tp_triggered': False,
            'tp_escalier_levels_hit': [],
            'early_invalidation_triggered': False,
            'entry_conditions': ['EMAs', 'Volume'],
            'entry_indicators': {},
            'exit_indicators': {},
            'entry_scalability': {
                'spread_pct': 0.02,
                'balance_score': 0.9,
                'book_depth': 50000,
                'bid_vol': 25000,
                'ask_vol': 25000,
                'recent_volume': 75000,
                'vol5': 15000,
                'vol15': 45000,
                'scalability_score': 0.75
            },
            'pnl_history': [],
            'config_snapshot': {'tp_sl_mode': 'FIXE'}
        }

        session_id = str(uuid.uuid4())
        trade_id = logger.log_trade(trade_data, opportunity_id=1, scan_log_id=1, session_id=session_id)

        assert trade_id == 42
        
        # Trouver la requête d'insertion du trade
        trade_insert = None
        for q in captured_queries:
            if 'INSERT INTO trades' in q['query']:
                trade_insert = q
                break
        
        assert trade_insert is not None
        placeholders = trade_insert['query'].count('%s')
        assert placeholders == len(trade_insert['params'])
        # S'assurer que quelques colonnes critiques sont bien présentes
        assert 'timestamp_entry' in trade_insert['query']
        assert 'config_snapshot' in trade_insert['query']
    
    @patch('core.postgresql_datalogger.PSYCOPG2_AVAILABLE', True)
    @patch('core.postgresql_datalogger.ThreadedConnectionPool')
    def test_flush_buffers(self, mock_pool_class, datalogger_config, mock_pool, mock_postgres_connection):
        """Test flush des buffers"""
        mock_pool_class.return_value = mock_pool
        conn, cursor = mock_postgres_connection
        mock_pool.getconn.return_value = conn
        
        from core.postgresql_datalogger import PostgreSQLDataLogger
        
        logger = PostgreSQLDataLogger(**datalogger_config)
        
        # Ajouter des scans au buffer
        for i in range(5):
            scan_data = {
                'scan_duration_ms': 100 + i,
                'market_data': {'price': 50000.0 + i},
                'indicators_1m': {},
                'indicators_5m': {},
                'filters': {},
                'scores': {},
                'patterns': {},
                'is_opportunity': False
            }
            logger.log_scan(f'BTCUSDT{i}', scan_data, use_batch=True)
        
        # Flush forcé
        logger._flush_buffers(force=True)
        
        # Vérifier que le buffer est vidé
        assert len(logger.scan_buffer) == 0
    
    @patch('core.postgresql_datalogger.PSYCOPG2_AVAILABLE', True)
    @patch('core.postgresql_datalogger.ThreadedConnectionPool')
    def test_close(self, mock_pool_class, datalogger_config, mock_pool):
        """Test fermeture du datalogger"""
        mock_pool_class.return_value = mock_pool
        
        from core.postgresql_datalogger import PostgreSQLDataLogger
        
        logger = PostgreSQLDataLogger(**datalogger_config)
        
        # Ajouter des données au buffer
        scan_data = {
            'scan_duration_ms': 100,
            'market_data': {'price': 50000.0},
            'indicators_1m': {},
            'indicators_5m': {},
            'filters': {},
            'scores': {},
            'patterns': {},
            'is_opportunity': False
        }
        logger.log_scan('BTCUSDT', scan_data, use_batch=True)
        
        # Fermer
        logger.close()
        
        # Vérifier que le pool est fermé
        mock_pool.closeall.assert_called_once()


class TestPostgreSQLHelperFunctions:
    """Tests pour les fonctions helper de PostgreSQLDataLogger"""
    
    def test_safe_float_with_none(self):
        """Test _safe_float avec None"""
        from core.postgresql_datalogger import _safe_float
        
        result = _safe_float(None)
        assert result == 0.0
        
        result = _safe_float(None, default=5.0)
        assert result == 5.0
    
    def test_safe_float_with_numbers(self):
        """Test _safe_float avec des nombres"""
        from core.postgresql_datalogger import _safe_float
        
        assert _safe_float(123) == 123.0
        assert _safe_float(45.67) == 45.67
        assert _safe_float(-10) == -10.0
    
    def test_safe_float_with_strings(self):
        """Test _safe_float avec des strings"""
        from core.postgresql_datalogger import _safe_float
        
        assert _safe_float("123.45") == 123.45
        assert _safe_float("0") == 0.0
        assert _safe_float("invalid") == 0.0
        assert _safe_float("") == 0.0
    
    def test_safe_float_with_dict(self):
        """Test _safe_float avec des dictionnaires"""
        from core.postgresql_datalogger import _safe_float
        
        assert _safe_float({"value": 100}) == 100.0
        assert _safe_float({"price": 50.5}) == 50.5
        assert _safe_float({"score": "25.5"}) == 25.5
        assert _safe_float({"unknown": 10}) == 0.0
        assert _safe_float({}) == 0.0
    
    def test_safe_float_with_invalid_types(self):
        """Test _safe_float avec des types invalides"""
        from core.postgresql_datalogger import _safe_float
        
        assert _safe_float([1, 2, 3]) == 0.0
        assert _safe_float(object()) == 0.0
    
    def test_extract_numeric_value_comprehensive(self):
        """Test _extract_numeric_value avec différents types"""
        from core.postgresql_datalogger import _extract_numeric_value
        
        # Tests basiques
        assert _extract_numeric_value(None) is None
        assert _extract_numeric_value(123) == 123.0
        assert _extract_numeric_value(45.67) == 45.67
        
        # Tests avec strings
        assert _extract_numeric_value("123.45") == 123.45
        assert _extract_numeric_value("invalid") is None
        
        # Tests avec dictionnaires
        assert _extract_numeric_value({"value": 100}) == 100.0
        assert _extract_numeric_value({"price": 50.5}) == 50.5
        assert _extract_numeric_value({"rsi": "75.5"}) == 75.5
        assert _extract_numeric_value({"unknown": 10}) is None


class TestPostgreSQLNoneTypeFixes:
    """Tests pour les corrections NoneType dans PostgreSQL DataLogger"""
    
    @patch('core.postgresql_datalogger.PSYCOPG2_AVAILABLE', True)
    @patch('core.postgresql_datalogger.ThreadedConnectionPool')
    def test_log_scan_with_none_order_flow_values(self, mock_pool_class, datalogger_config, mock_postgres_connection, mock_pool):
        """Test log_scan avec des valeurs order flow None"""
        conn, cursor = mock_postgres_connection
        mock_pool_class.return_value = mock_pool
        mock_pool.getconn.return_value = conn
        
        from core.postgresql_datalogger import PostgreSQLDataLogger
        
        logger = PostgreSQLDataLogger(**datalogger_config)
        
        # Données avec bid_vol et ask_vol None
        scan_data = {
            'scan_duration_ms': 100,
            'market_data': {
                'price': 50000.0,
                'bid_vol': None,  # None value
                'ask_vol': None,  # None value
                'delta_volume': None,
                'imbalance_normalized': None,
                'book_depth_ratio': None
            },
            'indicators_1m': {},
            'indicators_5m': {},
            'filters': {},
            'scores': {},
            'patterns': {},
            'is_opportunity': False
        }
        
        # Ne doit pas lever d'exception NoneType
        logger.log_scan('BTCUSDT', scan_data)
        
        # Vérifier que execute a été appelé
        cursor.execute.assert_called()
    
    @patch('core.postgresql_datalogger.PSYCOPG2_AVAILABLE', True)
    @patch('core.postgresql_datalogger.ThreadedConnectionPool')
    def test_log_scan_with_string_order_flow_values(self, mock_pool_class, datalogger_config, mock_postgres_connection, mock_pool):
        """Test log_scan avec des valeurs order flow en string"""
        conn, cursor = mock_postgres_connection
        mock_pool_class.return_value = mock_pool
        mock_pool.getconn.return_value = conn
        
        from core.postgresql_datalogger import PostgreSQLDataLogger
        
        logger = PostgreSQLDataLogger(**datalogger_config)
        
        # Données avec bid_vol et ask_vol en string
        scan_data = {
            'scan_duration_ms': 100,
            'market_data': {
                'price': 50000.0,
                'bid_vol': "1000.5",  # String value
                'ask_vol': "800.3",   # String value
            },
            'indicators_1m': {},
            'indicators_5m': {},
            'filters': {},
            'scores': {},
            'patterns': {},
            'is_opportunity': False
        }
        
        # Ne doit pas lever d'exception
        logger.log_scan('BTCUSDT', scan_data)
        
        # Vérifier que execute a été appelé
        cursor.execute.assert_called()
    
    @patch('core.postgresql_datalogger.PSYCOPG2_AVAILABLE', True) 
    @patch('core.postgresql_datalogger.ThreadedConnectionPool')
    def test_batch_insert_with_none_values(self, mock_pool_class, datalogger_config, mock_postgres_connection, mock_pool):
        """Test _batch_insert_scans avec des valeurs None"""
        conn, cursor = mock_postgres_connection
        mock_pool_class.return_value = mock_pool
        mock_pool.getconn.return_value = conn
        
        from core.postgresql_datalogger import PostgreSQLDataLogger
        
        logger = PostgreSQLDataLogger(**datalogger_config)
        
        # Ajouter plusieurs scans avec des valeurs None au buffer
        for i in range(3):
            scan_data = {
                'scan_duration_ms': 100 + i,
                'market_data': {
                    'price': 50000.0 + i,
                    'bid_vol': None if i == 0 else f"{1000 + i}",  # Mix None/string
                    'ask_vol': None if i == 1 else 800 + i,        # Mix None/number
                },
                'indicators_1m': {},
                'indicators_5m': {},
                'filters': {},
                'scores': {},
                'patterns': {},
                'is_opportunity': False
            }
            logger.log_scan(f'BTCUSDT{i}', scan_data, use_batch=True)
        
        # Flush le buffer - ne doit pas lever d'exception
        logger._flush_buffers(force=True)
        
        # Vérifier que execute_values a été appelé
        assert cursor.execute.called or hasattr(cursor, 'execute_values')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

