"""
Tests pour core/position/analytics_logger.py
"""
import pytest
from unittest.mock import Mock
from datetime import datetime
from core.position.analytics_logger import AnalyticsLogger


class TestAnalyticsLogger:
    """Tests pour AnalyticsLogger"""

    def test_init_with_db(self):
        """Test initialisation avec DB"""
        mock_db = Mock()
        logger = AnalyticsLogger(mock_db)
        assert logger.analytics_db == mock_db

    def test_init_without_db(self):
        """Test initialisation sans DB"""
        logger = AnalyticsLogger()
        assert logger.analytics_db is None

    def test_log_trade_no_db(self):
        """Test log_trade sans DB"""
        logger = AnalyticsLogger()

        position = {'symbol': 'BTC/USDT:USDT', 'entry': 50000}
        pnl_data = {'pnl_pct': 1.0, 'net_pnl': 100}

        # Ne devrait pas lever d'exception
        logger.log_trade(position, 50500, 'TP_HIT', pnl_data)

    def test_log_trade_success(self):
        """Test log_trade réussi"""
        mock_db = Mock()
        logger = AnalyticsLogger(mock_db)

        position = {
            'symbol': 'BTC/USDT:USDT',
            'direction': 'LONG',
            'entry': 50000,
            'opened_at': datetime.now().isoformat(),
            'confirmed_by': 'EMA_CROSS',
            'tp_sl_mode': 'FIXE',
            'break_even_triggered': False,
            'trailing_stop_triggered': False,
            'partial_tp_sold': False,
            'tp_escalier_enabled': False,
            'tp_escalier_levels_hit': [],
            'tp_escalier_profits': [],
            'max_pnl_reached': 2.0,
            'min_pnl_reached': -0.5,
            'session_id': 'test-session'
        }

        pnl_data = {
            'pnl_pct': 1.0,
            'gross_pnl': 100,
            'net_pnl': 95,
            'fees': 3,
            'slippage': 2
        }

        logger.log_trade(position, 50500, 'TP_HIT', pnl_data, mode='LIVE')

        mock_db.insert_trade.assert_called_once()
        call_args = mock_db.insert_trade.call_args[0][0]

        assert call_args['symbol'] == 'BTC/USDT:USDT'
        assert call_args['direction'] == 'LONG'
        assert call_args['entry'] == 50000
        assert call_args['exit'] == 50500
        assert call_args['gross_pnl_pct'] == 1.0
        assert call_args['net_pnl_usdt'] == 95
        assert call_args['fees'] == 3
        assert call_args['slippage'] == 2
        assert call_args['total_costs'] == 5
        assert call_args['reason'] == 'TP_HIT'
        assert call_args['trading_mode'] == 'LIVE'

    def test_log_trade_invalid_exit_price(self):
        """Test log_trade avec exit price invalide"""
        mock_db = Mock()
        logger = AnalyticsLogger(mock_db)

        position = {
            'symbol': 'BTC/USDT:USDT',
            'entry': 50000
        }

        pnl_data = {
            'pnl_pct': 0,
            'net_pnl': 0,
            'fees': 0
        }

        # Exit price = 0 (invalide)
        logger.log_trade(position, 0, 'ERROR', pnl_data)

        mock_db.insert_trade.assert_called_once()
        call_args = mock_db.insert_trade.call_args[0][0]

        # Devrait utiliser entry price
        assert call_args['exit'] == 50000

    def test_log_trade_negative_exit_price(self):
        """Test log_trade avec exit price négatif"""
        mock_db = Mock()
        logger = AnalyticsLogger(mock_db)

        position = {
            'symbol': 'BTC/USDT:USDT',
            'entry': 50000
        }

        pnl_data = {
            'pnl_pct': 0,
            'net_pnl': 0
        }

        # Exit price négatif
        logger.log_trade(position, -100, 'ERROR', pnl_data)

        call_args = mock_db.insert_trade.call_args[0][0]
        # Devrait utiliser entry price
        assert call_args['exit'] == 50000

    def test_log_trade_duration_calculation(self):
        """Test calcul durée avec opened_at"""
        mock_db = Mock()
        logger = AnalyticsLogger(mock_db)

        # Créer une position ouverte il y a 60 secondes
        opened_at = datetime.now()
        opened_at = opened_at.replace(second=opened_at.second - 60 if opened_at.second >= 60 else 0)

        position = {
            'symbol': 'BTC/USDT:USDT',
            'entry': 50000,
            'opened_at': opened_at.isoformat()
        }

        pnl_data = {'pnl_pct': 1.0, 'net_pnl': 100}

        logger.log_trade(position, 50500, 'TP_HIT', pnl_data)

        call_args = mock_db.insert_trade.call_args[0][0]
        # Duration devrait être environ 60 secondes
        assert call_args['duration'] is not None
        assert isinstance(call_args['duration'], int)

    def test_log_trade_duration_with_datetime_object(self):
        """Test calcul durée avec datetime object"""
        mock_db = Mock()
        logger = AnalyticsLogger(mock_db)

        opened_at = datetime.now()

        position = {
            'symbol': 'BTC/USDT:USDT',
            'entry': 50000,
            'opened_at': opened_at  # datetime object
        }

        pnl_data = {'pnl_pct': 1.0, 'net_pnl': 100}

        logger.log_trade(position, 50500, 'TP_HIT', pnl_data)

        call_args = mock_db.insert_trade.call_args[0][0]
        assert call_args['duration'] is not None

    def test_log_trade_duration_invalid_opened_at(self):
        """Test calcul durée avec opened_at invalide"""
        mock_db = Mock()
        logger = AnalyticsLogger(mock_db)

        position = {
            'symbol': 'BTC/USDT:USDT',
            'entry': 50000,
            'opened_at': 'invalid-date'
        }

        pnl_data = {'pnl_pct': 1.0, 'net_pnl': 100}

        # Ne devrait pas lever d'exception
        logger.log_trade(position, 50500, 'TP_HIT', pnl_data)

        call_args = mock_db.insert_trade.call_args[0][0]
        # Duration devrait être None
        assert call_args['duration'] is None

    def test_log_trade_no_opened_at(self):
        """Test log_trade sans opened_at"""
        mock_db = Mock()
        logger = AnalyticsLogger(mock_db)

        position = {
            'symbol': 'BTC/USDT:USDT',
            'entry': 50000
        }

        pnl_data = {'pnl_pct': 1.0, 'net_pnl': 100}

        logger.log_trade(position, 50500, 'TP_HIT', pnl_data)

        call_args = mock_db.insert_trade.call_args[0][0]
        assert call_args['duration'] is None

    def test_log_trade_backtest_mode(self):
        """Test log_trade en mode BACKTEST"""
        mock_db = Mock()
        logger = AnalyticsLogger(mock_db)

        position = {'symbol': 'BTC/USDT:USDT', 'entry': 50000}
        pnl_data = {'pnl_pct': 1.0, 'net_pnl': 100}

        logger.log_trade(position, 50500, 'TP_HIT', pnl_data, mode='BACKTEST')

        call_args = mock_db.insert_trade.call_args[0][0]
        assert call_args['trading_mode'] == 'BACKTEST'
        assert call_args['is_backtest'] is True

    def test_log_trade_paper_mode(self):
        """Test log_trade en mode PAPER"""
        mock_db = Mock()
        logger = AnalyticsLogger(mock_db)

        position = {'symbol': 'BTC/USDT:USDT', 'entry': 50000}
        pnl_data = {'pnl_pct': 1.0, 'net_pnl': 100}

        logger.log_trade(position, 50500, 'TP_HIT', pnl_data, mode='PAPER')

        call_args = mock_db.insert_trade.call_args[0][0]
        assert call_args['trading_mode'] == 'PAPER'
        assert call_args['is_backtest'] is False

    def test_log_trade_exception(self):
        """Test log_trade avec exception dans insert_trade"""
        mock_db = Mock()
        mock_db.insert_trade.side_effect = Exception("DB error")
        logger = AnalyticsLogger(mock_db)

        position = {'symbol': 'BTC/USDT:USDT', 'entry': 50000}
        pnl_data = {'pnl_pct': 1.0, 'net_pnl': 100}

        # Ne devrait pas lever d'exception
        logger.log_trade(position, 50500, 'TP_HIT', pnl_data)

    def test_log_setup_rejected_no_db(self):
        """Test log_setup_rejected sans DB"""
        logger = AnalyticsLogger()

        # Ne devrait pas lever d'exception
        logger.log_setup_rejected('BTC/USDT:USDT', ['CORRELATION'], {'score': 5.0})

    def test_log_setup_rejected_success(self):
        """Test log_setup_rejected réussi"""
        mock_db = Mock()
        logger = AnalyticsLogger(mock_db)

        logger.log_setup_rejected('BTC/USDT:USDT', ['CORRELATION', 'LOW_SCORE'], {'score': 5.0})

        mock_db.log_setup_rejected.assert_called_once_with(
            'BTC/USDT:USDT',
            ['CORRELATION', 'LOW_SCORE'],
            {'score': 5.0}
        )

    def test_log_setup_rejected_no_details(self):
        """Test log_setup_rejected sans details"""
        mock_db = Mock()
        logger = AnalyticsLogger(mock_db)

        logger.log_setup_rejected('BTC/USDT:USDT', ['CORRELATION'])

        mock_db.log_setup_rejected.assert_called_once_with(
            'BTC/USDT:USDT',
            ['CORRELATION'],
            {}
        )

    def test_log_setup_rejected_exception(self):
        """Test log_setup_rejected avec exception"""
        mock_db = Mock()
        mock_db.log_setup_rejected.side_effect = Exception("DB error")
        logger = AnalyticsLogger(mock_db)

        # Ne devrait pas lever d'exception
        logger.log_setup_rejected('BTC/USDT:USDT', ['CORRELATION'], {'score': 5.0})

    def test_log_setup_validated_no_db(self):
        """Test log_setup_validated sans DB"""
        logger = AnalyticsLogger()

        # Ne devrait pas lever d'exception
        logger.log_setup_validated('BTC/USDT:USDT', 'LONG', 8.5, ['EMA_CROSS', 'RSI_OVERSOLD'])

    def test_log_setup_validated_success(self):
        """Test log_setup_validated réussi"""
        mock_db = Mock()
        logger = AnalyticsLogger(mock_db)

        logger.log_setup_validated('BTC/USDT:USDT', 'LONG', 8.5, ['EMA_CROSS', 'RSI_OVERSOLD'])

        mock_db.log_setup_validated.assert_called_once_with(
            'BTC/USDT:USDT',
            'LONG',
            8.5,
            ['EMA_CROSS', 'RSI_OVERSOLD']
        )

    def test_log_setup_validated_exception(self):
        """Test log_setup_validated avec exception"""
        mock_db = Mock()
        mock_db.log_setup_validated.side_effect = Exception("DB error")
        logger = AnalyticsLogger(mock_db)

        # Ne devrait pas lever d'exception
        logger.log_setup_validated('BTC/USDT:USDT', 'LONG', 8.5, ['EMA_CROSS'])


class TestIntegration:
    """Tests d'intégration"""

    def test_full_workflow(self):
        """Test workflow complet"""
        mock_db = Mock()
        logger = AnalyticsLogger(mock_db)

        # 1. Log setup validé
        logger.log_setup_validated('BTC/USDT:USDT', 'LONG', 8.5, ['EMA_CROSS'])
        assert mock_db.log_setup_validated.call_count == 1

        # 2. Log trade
        position = {
            'symbol': 'BTC/USDT:USDT',
            'direction': 'LONG',
            'entry': 50000,
            'opened_at': datetime.now().isoformat(),
            'confirmed_by': 'EMA_CROSS'
        }
        pnl_data = {'pnl_pct': 1.0, 'net_pnl': 100, 'fees': 2}

        logger.log_trade(position, 50500, 'TP_HIT', pnl_data)
        assert mock_db.insert_trade.call_count == 1

    def test_rejected_then_validated(self):
        """Test rejet puis validation"""
        mock_db = Mock()
        logger = AnalyticsLogger(mock_db)

        # Rejeter pour corrélation
        logger.log_setup_rejected('BTC/USDT:USDT', ['CORRELATION'])
        assert mock_db.log_setup_rejected.call_count == 1

        # Valider après
        logger.log_setup_validated('ETH/USDT:USDT', 'SHORT', 7.0, ['MACD'])
        assert mock_db.log_setup_validated.call_count == 1
