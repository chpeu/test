"""
Tests unitaires pour trading/live_order_manager.py
Coverage target: 80%+
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from trading.live_order_manager import (
    LiveOrderManager,
    OrderResult
)


@pytest.fixture
def mock_exchange():
    """Mock CCXT exchange"""
    exchange = Mock()
    exchange.create_order = Mock(return_value={
        'id': 'order_123',
        'symbol': 'BTC/USDT',
        'side': 'buy',
        'price': 42000,
        'amount': 0.1,
        'filled': 0.1,
        'average': 42010,
        'cost': 4201,
        'fee': {'cost': 4.201, 'currency': 'USDT'},
        'timestamp': int(time.time() * 1000)
    })
    exchange.fetch_order = Mock(return_value={
        'id': 'order_123',
        'filled': 0.1,
        'average': 42010,
        'cost': 4201,
        'fee': {'cost': 4.201, 'currency': 'USDT'}
    })
    exchange.fetch_balance = Mock(return_value={
        'USDT': {'free': 1000, 'used': 0, 'total': 1000}
    })
    return exchange


@pytest.fixture
def live_manager_dry_run():
    """LiveOrderManager en mode dry_run"""
    with patch('trading.live_order_manager.ccxt.mexc') as mock_mexc:
        mock_mexc.return_value = Mock()
        manager = LiveOrderManager(
            api_key='test_key',
            api_secret='test_secret',
            dry_run=True
        )
        return manager


@pytest.fixture
def live_manager_live(mock_exchange):
    """LiveOrderManager en mode LIVE"""
    with patch('trading.live_order_manager.ccxt.mexc') as mock_mexc:
        mock_mexc.return_value = mock_exchange
        manager = LiveOrderManager(
            api_key='test_key',
            api_secret='test_secret',
            dry_run=False
        )
        manager.exchange = mock_exchange
        return manager


class TestOrderResult:
    """Tests OrderResult dataclass"""

    def test_order_result_success(self):
        """Test OrderResult avec succès"""
        result = OrderResult(
            success=True,
            order_id='123',
            filled_price=42000.0,
            filled_amount=0.1
        )

        assert result.success is True
        assert result.order_id == '123'
        assert result.filled_price == 42000.0

    def test_order_result_failure(self):
        """Test OrderResult avec échec"""
        result = OrderResult(
            success=False,
            error_message='Insufficient balance'
        )

        assert result.success is False
        assert result.error_message == 'Insufficient balance'
        assert result.order_id is None


class TestLiveOrderManagerInit:
    """Tests initialisation"""

    @patch('trading.live_order_manager.ccxt.mexc')
    def test_init_dry_run(self, mock_mexc):
        """Test init en mode dry_run"""
        mock_exchange = Mock()
        mock_mexc.return_value = mock_exchange

        manager = LiveOrderManager(
            api_key='test_key',
            api_secret='test_secret',
            dry_run=True
        )

        assert manager.dry_run is True
        assert manager.testnet is False
        assert manager.stats['orders_placed'] == 0

    @patch('trading.live_order_manager.ccxt.mexc')
    def test_init_live_mode(self, mock_mexc):
        """Test init en mode LIVE"""
        mock_exchange = Mock()
        mock_mexc.return_value = mock_exchange

        manager = LiveOrderManager(
            api_key='test_key',
            api_secret='test_secret',
            dry_run=False
        )

        assert manager.dry_run is False
        mock_exchange.set_sandbox_mode.assert_not_called()

    @patch('trading.live_order_manager.ccxt.mexc')
    def test_init_testnet(self, mock_mexc):
        """Test init en mode testnet"""
        mock_exchange = Mock()
        mock_mexc.return_value = mock_exchange

        manager = LiveOrderManager(
            api_key='test_key',
            api_secret='test_secret',
            testnet=True,
            dry_run=True
        )

        assert manager.testnet is True
        mock_exchange.set_sandbox_mode.assert_called_once_with(True)


class TestOpenPosition:
    """Tests open_position()"""

    def test_open_position_dry_run(self, live_manager_dry_run):
        """Test ouverture position en dry_run"""
        result = live_manager_dry_run.open_position(
            symbol='BTC/USDT',
            direction='LONG',
            entry_price=42000,
            size_usdt=100
        )

        assert result.success is True
        assert result.filled_price == 42000
        assert result.filled_amount > 0
        assert 'dry_run' in result.order_id
        assert result.latency_ms is not None

    def test_open_position_live_success(self, live_manager_live):
        """Test ouverture position en LIVE réussi"""
        result = live_manager_live.open_position(
            symbol='BTC/USDT',
            direction='LONG',
            entry_price=42000,
            size_usdt=100
        )

        assert result.success is True
        assert result.order_id == 'order_123'
        assert result.filled_price == 42010
        assert result.actual_slippage_pct is not None
        assert live_manager_live.stats['orders_placed'] == 1

    def test_open_position_live_short(self, live_manager_live):
        """Test ouverture position SHORT"""
        result = live_manager_live.open_position(
            symbol='BTC/USDT',
            direction='SHORT',
            entry_price=42000,
            size_usdt=100
        )

        assert result.success is True
        live_manager_live.exchange.create_order.assert_called()
        call_args = live_manager_live.exchange.create_order.call_args
        assert call_args[0][2] == 'sell'  # side='sell' pour SHORT

    def test_open_position_api_error(self, live_manager_live):
        """Test erreur API lors ouverture"""
        live_manager_live.exchange.create_order.side_effect = Exception("API Error")

        result = live_manager_live.open_position(
            symbol='BTC/USDT',
            direction='LONG',
            entry_price=42000,
            size_usdt=100
        )

        assert result.success is False
        assert 'API Error' in result.error_message
        assert live_manager_live.stats['orders_failed'] == 1

    def test_open_position_with_leverage(self, live_manager_dry_run):
        """Test ouverture avec levier"""
        result = live_manager_dry_run.open_position(
            symbol='BTC/USDT',
            direction='LONG',
            entry_price=42000,
            size_usdt=100,
            leverage=10
        )

        assert result.success is True


class TestClosePosition:
    """Tests close_position()"""

    def test_close_position_dry_run(self, live_manager_dry_run):
        """Test fermeture position en dry_run"""
        result = live_manager_dry_run.close_position(
            symbol='BTC/USDT',
            direction='LONG',
            entry_price=42000,
            current_price=43000,
            size_amount=0.1
        )

        assert result.success is True
        assert result.filled_price == 43000
        assert result.actual_pnl_usdt is not None
        assert result.actual_pnl_usdt > 0  # Profit car 43000 > 42000

    def test_close_position_live_success(self, live_manager_live):
        """Test fermeture position en LIVE réussi"""
        result = live_manager_live.close_position(
            symbol='BTC/USDT',
            direction='LONG',
            entry_price=42000,
            current_price=43000,
            size_amount=0.1
        )

        assert result.success is True
        assert result.order_id == 'order_123'
        assert result.actual_pnl_usdt is not None

    def test_close_position_short(self, live_manager_dry_run):
        """Test fermeture position SHORT"""
        result = live_manager_dry_run.close_position(
            symbol='BTC/USDT',
            direction='SHORT',
            entry_price=42000,
            current_price=41000,  # Prix baisse = profit pour SHORT
            size_amount=0.1
        )

        assert result.success is True
        assert result.actual_pnl_usdt > 0  # Profit car prix a baissé

    def test_close_position_partial(self, live_manager_dry_run):
        """Test fermeture partielle"""
        result = live_manager_dry_run.close_position(
            symbol='BTC/USDT',
            direction='LONG',
            entry_price=42000,
            current_price=43000,
            size_amount=0.1,
            partial_pct=50  # Fermer 50%
        )

        assert result.success is True
        assert result.filled_amount < 0.1  # Moins que total

    def test_close_position_api_error(self, live_manager_live):
        """Test erreur API lors fermeture"""
        live_manager_live.exchange.create_order.side_effect = Exception("API Error")

        result = live_manager_live.close_position(
            symbol='BTC/USDT',
            direction='LONG',
            entry_price=42000,
            current_price=43000,
            size_amount=0.1
        )

        assert result.success is False
        assert 'API Error' in result.error_message


class TestVerifyTradeResult:
    """Tests verify_trade_result()"""

    def test_verify_all_ok(self, live_manager_dry_run):
        """Test vérification réussie"""
        result = live_manager_dry_run.verify_trade_result(
            expected_pnl_pct=2.0,
            actual_pnl_pct=2.1,
            expected_slippage_pct=0.1,
            actual_slippage_pct=0.05
        )

        assert result['all_ok'] is True
        assert len(result['warnings']) == 0

    def test_verify_pnl_discrepancy(self, live_manager_dry_run):
        """Test discordance PNL"""
        result = live_manager_dry_run.verify_trade_result(
            expected_pnl_pct=2.0,
            actual_pnl_pct=1.0,  # Grande différence
            expected_slippage_pct=0.1,
            actual_slippage_pct=0.05
        )

        assert result['all_ok'] is False
        assert any('PNL' in w for w in result['warnings'])

    def test_verify_high_slippage(self, live_manager_dry_run):
        """Test slippage élevé"""
        result = live_manager_dry_run.verify_trade_result(
            expected_pnl_pct=2.0,
            actual_pnl_pct=2.0,
            expected_slippage_pct=0.1,
            actual_slippage_pct=0.5  # Slippage élevé
        )

        assert result['all_ok'] is False
        assert any('slippage' in w.lower() for w in result['warnings'])

    def test_verify_negative_actual_pnl(self, live_manager_dry_run):
        """Test PNL négatif inattendu"""
        result = live_manager_dry_run.verify_trade_result(
            expected_pnl_pct=2.0,
            actual_pnl_pct=-1.0,  # Négatif alors que positif attendu
            expected_slippage_pct=0.1,
            actual_slippage_pct=0.05
        )

        assert result['all_ok'] is False
        assert any('négatif' in w.lower() for w in result['warnings'])


class TestGetBalance:
    """Tests _get_balance()"""

    def test_get_balance_usdt(self, live_manager_live):
        """Test récupération balance USDT"""
        balance = live_manager_live._get_balance('USDT')

        assert balance == 1000
        live_manager_live.exchange.fetch_balance.assert_called_once()

    def test_get_balance_other_currency(self, live_manager_live):
        """Test récupération autre devise"""
        live_manager_live.exchange.fetch_balance.return_value = {
            'BTC': {'free': 0.5, 'used': 0, 'total': 0.5}
        }

        balance = live_manager_live._get_balance('BTC')

        assert balance == 0.5

    def test_get_balance_error(self, live_manager_live):
        """Test erreur récupération balance"""
        live_manager_live.exchange.fetch_balance.side_effect = Exception("API Error")

        balance = live_manager_live._get_balance('USDT')

        assert balance == 0.0  # Retourne 0 en cas d'erreur


class TestGetStats:
    """Tests get_stats()"""

    def test_get_stats_initial(self, live_manager_dry_run):
        """Test stats initiales"""
        stats = live_manager_dry_run.get_stats()

        assert stats['orders_placed'] == 0
        assert stats['orders_filled'] == 0
        assert stats['success_rate'] == 0.0

    def test_get_stats_after_orders(self, live_manager_dry_run):
        """Test stats après ordres"""
        # Simuler quelques ordres
        live_manager_dry_run.open_position('BTC/USDT', 'LONG', 42000, 100)
        live_manager_dry_run.close_position('BTC/USDT', 'LONG', 42000, 43000, 0.1)

        stats = live_manager_dry_run.get_stats()

        assert stats['orders_placed'] == 2
        assert stats['success_rate'] == 100.0

    def test_get_stats_with_failures(self, live_manager_live):
        """Test stats avec échecs"""
        # Forcer un échec
        live_manager_live.exchange.create_order.side_effect = Exception("Error")
        live_manager_live.open_position('BTC/USDT', 'LONG', 42000, 100)

        stats = live_manager_live.get_stats()

        assert stats['orders_failed'] == 1
        assert stats['success_rate'] == 0.0


class TestSlippageCalculation:
    """Tests calcul slippage"""

    def test_slippage_long_positive(self, live_manager_dry_run):
        """Test slippage LONG positif (prix plus élevé)"""
        result = live_manager_dry_run.open_position(
            symbol='BTC/USDT',
            direction='LONG',
            entry_price=42000,
            size_usdt=100
        )

        # En dry_run, slippage est simulé
        assert result.actual_slippage_pct is not None

    def test_slippage_short_negative(self, live_manager_dry_run):
        """Test slippage SHORT"""
        result = live_manager_dry_run.open_position(
            symbol='BTC/USDT',
            direction='SHORT',
            entry_price=42000,
            size_usdt=100
        )

        assert result.actual_slippage_pct is not None


class TestEdgeCases:
    """Tests cas limites"""

    def test_zero_size(self, live_manager_dry_run):
        """Test taille nulle"""
        result = live_manager_dry_run.open_position(
            symbol='BTC/USDT',
            direction='LONG',
            entry_price=42000,
            size_usdt=0
        )

        # Devrait gérer gracieusement
        assert result is not None

    def test_very_high_leverage(self, live_manager_dry_run):
        """Test levier très élevé"""
        result = live_manager_dry_run.open_position(
            symbol='BTC/USDT',
            direction='LONG',
            entry_price=42000,
            size_usdt=100,
            leverage=125  # Max MEXC
        )

        assert result.success is True

    def test_close_with_no_open(self, live_manager_dry_run):
        """Test fermeture sans position ouverte"""
        result = live_manager_dry_run.close_position(
            symbol='BTC/USDT',
            direction='LONG',
            entry_price=42000,
            current_price=43000,
            size_amount=0.1
        )

        # Devrait fonctionner (dry_run simule toujours)
        assert result.success is True
