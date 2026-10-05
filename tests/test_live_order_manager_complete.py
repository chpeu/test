#!/usr/bin/env python3
"""
Tests complets pour trading/live_order_manager.py - Couverture 100%
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import time
from datetime import datetime, timezone
import ccxt
from trading.live_order_manager import (
    OrderResult,
    LiveOrderManager
)


class TestOrderResult:
    """Tests pour la dataclass OrderResult"""

    def test_order_result_default_init(self):
        """Test initialisation OrderResult par défaut"""
        result = OrderResult(success=True)
        
        assert result.success is True
        assert result.order_id is None
        assert result.filled_price is None
        assert result.filled_amount is None
        assert result.actual_pnl_usdt is None
        assert result.actual_fees_usdt is None
        assert result.actual_slippage_pct is None
        assert result.balance_after is None
        assert result.error_message is None
        assert result.latency_ms is None
        assert result.executed_at is None

    def test_order_result_complete_init(self):
        """Test initialisation OrderResult complète"""
        result = OrderResult(
            success=True,
            order_id="12345",
            filled_price=50000.0,
            filled_amount=0.002,
            actual_pnl_usdt=50.0,
            actual_fees_usdt=2.5,
            actual_slippage_pct=0.1,
            balance_after=1050.0,
            error_message=None,
            latency_ms=150.0,
            executed_at="2024-01-01T10:00:00Z"
        )
        
        assert result.success is True
        assert result.order_id == "12345"
        assert result.filled_price == 50000.0
        assert result.filled_amount == 0.002
        assert result.actual_pnl_usdt == 50.0
        assert result.actual_fees_usdt == 2.5
        assert result.actual_slippage_pct == 0.1
        assert result.balance_after == 1050.0
        assert result.error_message is None
        assert result.latency_ms == 150.0
        assert result.executed_at == "2024-01-01T10:00:00Z"

    def test_order_result_failed_init(self):
        """Test initialisation OrderResult échec"""
        result = OrderResult(
            success=False,
            error_message="API Error",
            latency_ms=250.0
        )
        
        assert result.success is False
        assert result.error_message == "API Error"
        assert result.latency_ms == 250.0


class TestLiveOrderManagerInit:
    """Tests pour l'initialisation de LiveOrderManager"""

    @patch('ccxt.mexc')
    def test_live_order_manager_default_init(self, mock_mexc):
        """Test initialisation par défaut"""
        mock_exchange = Mock()
        mock_mexc.return_value = mock_exchange
        
        manager = LiveOrderManager("api_key", "api_secret")
        
        assert manager.dry_run is True  # Default
        assert manager.testnet is False
        assert manager.exchange is mock_exchange
        assert manager.stats['orders_placed'] == 0
        assert manager.stats['orders_filled'] == 0
        assert manager.stats['orders_failed'] == 0
        assert manager.stats['total_latency_ms'] == 0
        assert manager.stats['avg_latency_ms'] == 0
        
        # Vérifier config MEXC
        mock_mexc.assert_called_once_with({
            'apiKey': 'api_key',
            'secret': 'api_secret',
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
            }
        })

    @patch('ccxt.mexc')
    def test_live_order_manager_custom_init(self, mock_mexc):
        """Test initialisation avec paramètres personnalisés"""
        mock_exchange = Mock()
        mock_mexc.return_value = mock_exchange
        
        manager = LiveOrderManager(
            "test_key",
            "test_secret",
            testnet=True,
            dry_run=False
        )
        
        assert manager.dry_run is False
        assert manager.testnet is True
        assert manager.exchange is mock_exchange
        
        # Vérifier sandbox mode activé
        mock_exchange.set_sandbox_mode.assert_called_once_with(True)

    @patch('ccxt.mexc')
    @patch('trading.live_order_manager.logger')
    def test_live_order_manager_testnet_warning(self, mock_logger, mock_mexc):
        """Test warning pour testnet"""
        mock_exchange = Mock()
        mock_mexc.return_value = mock_exchange
        
        manager = LiveOrderManager("key", "secret", testnet=True)
        
        # Vérifier warning loggé
        mock_logger.warning.assert_called_once()
        assert "testnet non disponible" in str(mock_logger.warning.call_args)


class TestOpenPosition:
    """Tests pour open_position"""

    @pytest.fixture
    def mock_manager(self):
        """Manager avec exchange mocké"""
        with patch('ccxt.mexc') as mock_mexc:
            mock_exchange = Mock()
            mock_mexc.return_value = mock_exchange
            manager = LiveOrderManager("key", "secret", dry_run=True)
            return manager

    def test_open_position_dry_run_long(self, mock_manager):
        """Test ouverture position LONG en dry run"""
        result = mock_manager.open_position(
            symbol='BTC/USDT',
            direction='LONG',
            entry_price=50000.0,
            size_usdt=100.0,
            leverage=1
        )
        
        assert result.success is True
        assert result.order_id.startswith("dry_run_")
        assert result.filled_price == 50000.0
        assert result.filled_amount == 0.002  # 100 / 50000
        assert result.actual_pnl_usdt == 0.0
        assert result.actual_fees_usdt == 0.0
        assert result.actual_slippage_pct == 0.0
        assert result.balance_after is None
        assert result.latency_ms is not None
        assert result.executed_at is not None

    def test_open_position_dry_run_short(self, mock_manager):
        """Test ouverture position SHORT en dry run"""
        result = mock_manager.open_position(
            symbol='ETH/USDT',
            direction='SHORT',
            entry_price=3000.0,
            size_usdt=300.0,
            leverage=2
        )
        
        assert result.success is True
        assert result.filled_price == 3000.0
        assert result.filled_amount == 0.1  # 300 / 3000
        assert result.actual_pnl_usdt == 0.0

    def test_open_position_live_success(self):
        """Test ouverture position live réussie"""
        with patch('ccxt.mexc') as mock_mexc:
            mock_exchange = Mock()
            mock_mexc.return_value = mock_exchange
            
            # Mock order response
            mock_exchange.create_order.return_value = {
                'id': 'order_12345',
                'average': 50050.0,  # Slippage
                'filled': 0.001998,
                'price': 50050.0
            }
            
            manager = LiveOrderManager("key", "secret", dry_run=False)
            
            result = manager.open_position(
                symbol='BTC/USDT',
                direction='LONG',
                entry_price=50000.0,
                size_usdt=100.0,
                leverage=1
            )
            
            assert result.success is True
            assert result.order_id == 'order_12345'
            assert result.filled_price == 50050.0
            assert result.filled_amount == 0.001998
            assert result.actual_slippage_pct == 0.1  # (50050-50000)/50000*100
            
            # Vérifier stats mises à jour
            assert manager.stats['orders_placed'] == 1
            assert manager.stats['orders_filled'] == 1
            assert manager.stats['orders_failed'] == 0
            
            # Vérifier appel exchange
            mock_exchange.create_order.assert_called_once_with(
                symbol='BTC/USDT',
                type='market',
                side='buy',  # LONG -> buy
                amount=0.002,  # 100/50000
                params={'leverage': None}  # leverage=1 -> None
            )

    def test_open_position_live_with_leverage(self):
        """Test ouverture position live avec leverage"""
        with patch('ccxt.mexc') as mock_mexc:
            mock_exchange = Mock()
            mock_mexc.return_value = mock_exchange
            mock_exchange.create_order.return_value = {
                'id': 'order_67890',
                'average': 2995.0,
                'filled': 0.1002,
                'price': 2995.0
            }
            
            manager = LiveOrderManager("key", "secret", dry_run=False)
            
            result = manager.open_position(
                symbol='ETH/USDT',
                direction='SHORT',
                entry_price=3000.0,
                size_usdt=300.0,
                leverage=5
            )
            
            # Vérifier appel avec leverage
            mock_exchange.create_order.assert_called_once_with(
                symbol='ETH/USDT',
                type='market',
                side='sell',  # SHORT -> sell
                amount=0.1,  # 300/3000
                params={'leverage': 5}  # leverage > 1
            )

    def test_open_position_live_error(self):
        """Test gestion erreur ouverture position live"""
        with patch('ccxt.mexc') as mock_mexc:
            mock_exchange = Mock()
            mock_mexc.return_value = mock_exchange
            mock_exchange.create_order.side_effect = ccxt.NetworkError("Connection failed")
            
            manager = LiveOrderManager("key", "secret", dry_run=False)
            
            result = manager.open_position(
                symbol='BTC/USDT',
                direction='LONG',
                entry_price=50000.0,
                size_usdt=100.0
            )
            
            assert result.success is False
            assert "Connection failed" in result.error_message
            assert result.latency_ms is not None
            
            # Vérifier stats
            assert manager.stats['orders_placed'] == 0
            assert manager.stats['orders_filled'] == 0
            assert manager.stats['orders_failed'] == 1


class TestClosePosition:
    """Tests pour close_position"""

    @pytest.fixture
    def mock_manager(self):
        """Manager avec exchange mocké"""
        with patch('ccxt.mexc') as mock_mexc:
            mock_exchange = Mock()
            mock_mexc.return_value = mock_exchange
            manager = LiveOrderManager("key", "secret", dry_run=True)
            return manager

    def test_close_position_dry_run_total_long_profit(self, mock_manager):
        """Test fermeture totale position LONG avec profit en dry run"""
        result = mock_manager.close_position(
            symbol='BTC/USDT',
            direction='LONG',
            entry_price=50000.0,
            current_price=51000.0,  # +2% profit
            size_amount=0.002
        )
        
        assert result.success is True
        assert result.order_id.startswith("dry_run_close_")
        assert result.filled_price == 51000.0
        assert result.filled_amount == 0.002
        assert result.actual_pnl_usdt == 2.0  # (51000-50000)*0.002
        assert result.actual_fees_usdt == 0.0
        assert result.actual_slippage_pct == 0.0
        assert result.balance_after is None

    def test_close_position_dry_run_total_short_profit(self, mock_manager):
        """Test fermeture totale position SHORT avec profit en dry run"""
        result = mock_manager.close_position(
            symbol='ETH/USDT',
            direction='SHORT',
            entry_price=3000.0,
            current_price=2900.0,  # Profit pour SHORT
            size_amount=0.1
        )
        
        assert result.success is True
        assert result.filled_amount == 0.1
        assert result.actual_pnl_usdt == 10.0  # (3000-2900)*0.1

    def test_close_position_dry_run_partial(self, mock_manager):
        """Test fermeture partielle en dry run"""
        result = mock_manager.close_position(
            symbol='BTC/USDT',
            direction='LONG',
            entry_price=50000.0,
            current_price=49000.0,  # Loss
            size_amount=0.002,
            partial_pct=50.0  # Fermeture 50%
        )
        
        assert result.success is True
        assert result.filled_amount == 0.001  # 0.002 * 0.5
        assert result.actual_pnl_usdt == -1.0  # (49000-50000)*0.001

    def test_close_position_live_success(self):
        """Test fermeture position live réussie"""
        with patch('ccxt.mexc') as mock_mexc:
            mock_exchange = Mock()
            mock_mexc.return_value = mock_exchange
            
            # Mock order response
            mock_exchange.create_order.return_value = {
                'id': 'close_12345',
                'average': 50950.0,  # Prix de fermeture
                'filled': 0.002,
                'price': 50950.0,
                'fee': {'cost': 2.0}
            }
            
            # Mock balance
            mock_exchange.fetch_balance.return_value = {
                'free': {'USDT': 1050.0}
            }
            
            manager = LiveOrderManager("key", "secret", dry_run=False)
            
            result = manager.close_position(
                symbol='BTC/USDT',
                direction='LONG',
                entry_price=50000.0,
                current_price=51000.0,
                size_amount=0.002
            )
            
            assert result.success is True
            assert result.order_id == 'close_12345'
            assert result.filled_price == 50950.0
            assert result.filled_amount == 0.002
            assert result.actual_pnl_usdt == pytest.approx(1.9, abs=0.001)  # (50950-50000)*0.002
            assert result.actual_fees_usdt == 2.0
            assert result.actual_slippage_pct == pytest.approx(0.098, abs=0.001)  # abs((50950-51000)/51000*100)
            assert result.balance_after == 1050.0
            
            # Vérifier appel exchange
            mock_exchange.create_order.assert_called_once_with(
                symbol='BTC/USDT',
                type='market',
                side='sell',  # Fermeture LONG -> sell
                amount=0.002
            )

    def test_close_position_live_error(self):
        """Test gestion erreur fermeture position live"""
        with patch('ccxt.mexc') as mock_mexc:
            mock_exchange = Mock()
            mock_mexc.return_value = mock_exchange
            mock_exchange.create_order.side_effect = ccxt.InsufficientFunds("Not enough balance")
            
            manager = LiveOrderManager("key", "secret", dry_run=False)
            
            result = manager.close_position(
                symbol='BTC/USDT',
                direction='LONG',
                entry_price=50000.0,
                current_price=51000.0,
                size_amount=0.002
            )
            
            assert result.success is False
            assert "Not enough balance" in result.error_message
            assert result.latency_ms is not None
            
            # Vérifier stats
            assert manager.stats['orders_failed'] == 1


class TestVerifyTradeResult:
    """Tests pour verify_trade_result"""

    @pytest.fixture
    def mock_manager_live(self):
        """Manager live avec exchange mocké"""
        with patch('ccxt.mexc') as mock_mexc:
            mock_exchange = Mock()
            mock_mexc.return_value = mock_exchange
            manager = LiveOrderManager("key", "secret", dry_run=False)
            return manager, mock_exchange

    def test_verify_trade_result_dry_run(self):
        """Test vérification trade en dry run"""
        with patch('ccxt.mexc'):
            manager = LiveOrderManager("key", "secret", dry_run=True)
            
            result = manager.verify_trade_result(
                order_id="dry_run_123",
                expected_pnl=50.0,
                expected_slippage=0.1
            )
            
            assert result['verified'] is True
            assert result['mode'] == 'DRY_RUN'
            assert result['discrepancy_pnl'] == 0.0
            assert result['discrepancy_slippage'] == 0.0

    def test_verify_trade_result_live_success(self, mock_manager_live):
        """Test vérification trade live réussie"""
        manager, mock_exchange = mock_manager_live
        
        # Mock fetch order
        mock_exchange.fetch_order.return_value = {
            'id': 'order_12345',
            'average': 51000.0,
            'filled': 0.002,
            'fee': {'cost': 1.5}
        }
        
        # Mock balance
        mock_exchange.fetch_balance.return_value = {
            'free': {'USDT': 1100.0}
        }
        
        result = manager.verify_trade_result(
            order_id="order_12345",
            expected_pnl=50.0,
            expected_slippage=0.1
        )
        
        assert result['verified'] is True
        assert result['order_id'] == "order_12345"
        assert result['filled_price'] == 51000.0
        assert result['filled_amount'] == 0.002
        assert result['fees'] == 1.5
        assert result['balance'] == 1100.0
        assert result['expected_pnl'] == 50.0
        assert result['expected_slippage'] == 0.1
        
        # Vérifier appels
        mock_exchange.fetch_order.assert_called_once_with("order_12345")
        mock_exchange.fetch_balance.assert_called_once()

    def test_verify_trade_result_live_error(self, mock_manager_live):
        """Test gestion erreur vérification trade live"""
        manager, mock_exchange = mock_manager_live
        mock_exchange.fetch_order.side_effect = ccxt.OrderNotFound("Order not found")
        
        result = manager.verify_trade_result(
            order_id="invalid_order",
            expected_pnl=50.0,
            expected_slippage=0.1
        )
        
        assert result['verified'] is False
        assert "Order not found" in result['error']


class TestGetBalance:
    """Tests pour _get_balance"""

    def test_get_balance_dry_run(self):
        """Test get balance en dry run"""
        with patch('ccxt.mexc'):
            manager = LiveOrderManager("key", "secret", dry_run=True)
            
            balance = manager._get_balance('USDT')
            
            assert balance == 0.0

    def test_get_balance_live_success(self):
        """Test get balance live réussi"""
        with patch('ccxt.mexc') as mock_mexc:
            mock_exchange = Mock()
            mock_mexc.return_value = mock_exchange
            mock_exchange.fetch_balance.return_value = {
                'free': {'USDT': 1500.0, 'BTC': 0.05}
            }
            
            manager = LiveOrderManager("key", "secret", dry_run=False)
            
            balance_usdt = manager._get_balance('USDT')
            balance_btc = manager._get_balance('BTC')
            
            assert balance_usdt == 1500.0
            assert balance_btc == 0.05

    def test_get_balance_live_currency_not_found(self):
        """Test get balance devise non trouvée"""
        with patch('ccxt.mexc') as mock_mexc:
            mock_exchange = Mock()
            mock_mexc.return_value = mock_exchange
            mock_exchange.fetch_balance.return_value = {
                'free': {'USDT': 1000.0}
            }
            
            manager = LiveOrderManager("key", "secret", dry_run=False)
            
            balance = manager._get_balance('ETH')  # Pas dans le balance
            
            assert balance == 0.0

    def test_get_balance_live_error(self):
        """Test gestion erreur get balance live"""
        with patch('ccxt.mexc') as mock_mexc:
            mock_exchange = Mock()
            mock_mexc.return_value = mock_exchange
            mock_exchange.fetch_balance.side_effect = ccxt.NetworkError("Network error")
            
            manager = LiveOrderManager("key", "secret", dry_run=False)
            
            balance = manager._get_balance('USDT')
            
            assert balance == 0.0  # Fallback sur erreur


class TestGetStats:
    """Tests pour get_stats"""

    def test_get_stats_empty(self):
        """Test stats vides"""
        with patch('ccxt.mexc'):
            manager = LiveOrderManager("key", "secret")
            
            stats = manager.get_stats()
            
            assert stats['orders_placed'] == 0
            assert stats['orders_filled'] == 0
            assert stats['orders_failed'] == 0
            assert stats['total_latency_ms'] == 0
            assert stats['avg_latency_ms'] == 0
            assert stats['success_rate'] == 0.0

    def test_get_stats_with_data(self):
        """Test stats avec données"""
        with patch('ccxt.mexc'):
            manager = LiveOrderManager("key", "secret")
            
            # Simuler quelques ordres
            manager.stats['orders_placed'] = 10
            manager.stats['orders_filled'] = 8
            manager.stats['orders_failed'] = 2
            manager.stats['total_latency_ms'] = 1500.0
            manager.stats['avg_latency_ms'] = 150.0
            
            stats = manager.get_stats()
            
            assert stats['orders_placed'] == 10
            assert stats['orders_filled'] == 8
            assert stats['orders_failed'] == 2
            assert stats['total_latency_ms'] == 1500.0
            assert stats['avg_latency_ms'] == 150.0
            assert stats['success_rate'] == 80.0  # 8/10*100

    def test_get_stats_perfect_success(self):
        """Test stats avec succès 100%"""
        with patch('ccxt.mexc'):
            manager = LiveOrderManager("key", "secret")
            
            manager.stats['orders_placed'] = 5
            manager.stats['orders_filled'] = 5
            manager.stats['orders_failed'] = 0
            
            stats = manager.get_stats()
            
            assert stats['success_rate'] == 100.0


class TestMainExecution:
    """Tests pour l'exécution du main"""

    @patch('time.sleep')
    def test_main_execution_dry_run(self, mock_sleep):
        """Test exécution du main en dry run"""
        with patch('ccxt.mexc') as mock_mexc:
            mock_exchange = Mock()
            mock_mexc.return_value = mock_exchange
            
            # Importer et exécuter le main
            from trading.live_order_manager import __name__ as module_name
            
            # Le code main ne s'exécute que si __name__ == "__main__"
            # Pour tester, on peut simuler les calls
            manager = LiveOrderManager("test_key", "test_secret", dry_run=True)
            
            # Simuler ouverture position
            result_open = manager.open_position(
                symbol='BTC/USDT',
                direction='LONG',
                entry_price=50000.0,
                size_usdt=100.0
            )
            
            # Simuler fermeture position
            result_close = manager.close_position(
                symbol='BTC/USDT',
                direction='LONG',
                entry_price=50000.0,
                current_price=50500.0,
                size_amount=0.002
            )
            
            # Vérifier stats
            stats = manager.get_stats()
            
            assert result_open.success is True
            assert result_close.success is True
            assert 'success_rate' in stats


class TestEdgeCases:
    """Tests pour cas limites et edge cases"""

    def test_open_position_zero_price(self):
        """Test ouverture position avec prix zéro"""
        with patch('ccxt.mexc'):
            manager = LiveOrderManager("key", "secret", dry_run=True)
            
            # Division par zéro est gérée et retourne success=False
            result = manager.open_position(
                symbol='BTC/USDT',
                direction='LONG',
                entry_price=0.0,  # Prix invalide - cause division par zéro
                size_usdt=100.0
            )
            
            # Vérifier que l'erreur est gérée correctement
            assert result.success is False
            assert "division by zero" in result.error_message

    def test_close_position_zero_amount(self):
        """Test fermeture position avec quantité zéro"""
        with patch('ccxt.mexc'):
            manager = LiveOrderManager("key", "secret", dry_run=True)
            
            result = manager.close_position(
                symbol='BTC/USDT',
                direction='LONG',
                entry_price=50000.0,
                current_price=51000.0,
                size_amount=0.0  # Quantité zéro
            )
            
            assert result.success is True
            assert result.filled_amount == 0.0
            assert result.actual_pnl_usdt == 0.0

    def test_slippage_calculation_edge_cases(self):
        """Test calculs slippage cas limites"""
        with patch('ccxt.mexc') as mock_mexc:
            mock_exchange = Mock()
            mock_mexc.return_value = mock_exchange
            mock_exchange.create_order.return_value = {
                'id': 'order_123',
                'average': None,  # Prix moyen None
                'price': 50000.0,  # Fallback vers price
                'filled': 0.002
            }
            
            manager = LiveOrderManager("key", "secret", dry_run=False)
            
            result = manager.open_position(
                symbol='BTC/USDT',
                direction='LONG',
                entry_price=50000.0,
                size_usdt=100.0
            )
            
            assert result.success is True
            assert result.filled_price == 50000.0  # Fallback vers price
            assert result.actual_slippage_pct == 0.0  # Pas de slippage

    def test_stats_average_latency_calculation(self):
        """Test calcul latence moyenne dans les stats"""
        with patch('ccxt.mexc') as mock_mexc:
            mock_exchange = Mock()
            mock_mexc.return_value = mock_exchange
            mock_exchange.create_order.return_value = {
                'id': 'test', 'average': 50000.0, 'filled': 0.002
            }
            
            manager = LiveOrderManager("key", "secret", dry_run=False)
            
            # Simuler plusieurs ordres avec latences différentes
            with patch('time.time', side_effect=[0, 0.1, 0.1, 0.3, 0.3, 0.5]):  # 100ms, 200ms
                result1 = manager.open_position('BTC/USDT', 'LONG', 50000.0, 100.0)
                result2 = manager.open_position('ETH/USDT', 'LONG', 3000.0, 300.0)
            
            stats = manager.get_stats()
            
            # Vérifier calcul moyenne: (100 + 200) / 2 = 150
            assert stats['orders_placed'] == 2
            assert stats['avg_latency_ms'] == 150.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
