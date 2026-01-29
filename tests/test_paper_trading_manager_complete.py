#!/usr/bin/env python3
"""
Tests complets pour trading/paper_trading_manager.py - Couverture 100%
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import time
from trading.paper_trading_manager import (
    PaperTradingManager,
    create_paper_trading_manager
)
from trading.abstract_trading_manager import TradingPosition


class TestPaperTradingManagerInit:
    """Tests pour l'initialisation de PaperTradingManager"""

    def test_paper_trading_manager_default_init(self):
        """Test initialisation par défaut"""
        manager = PaperTradingManager()
        
        assert manager.capital == 1000.0
        assert manager.price_provider is None
        assert manager.analytics_db is None
        assert manager.analytics_logger is None
        assert manager.simulate_latency is False
        assert manager.latency_ms == 100
        assert manager.config['taker_fee'] == 0.0004
        assert manager.config['slippage_pct'] == 0.05
        assert manager.price_cache == {}

    def test_paper_trading_manager_custom_init(self):
        """Test initialisation avec paramètres personnalisés"""
        mock_provider = Mock()
        mock_db = Mock()
        mock_logger = Mock()
        
        manager = PaperTradingManager(
            initial_capital=5000.0,
            price_provider=mock_provider,
            analytics_db=mock_db,
            analytics_logger=mock_logger,
            simulate_latency=True,
            latency_ms=200
        )
        
        assert manager.capital == 5000.0
        assert manager.price_provider is mock_provider
        assert manager.analytics_db is mock_db
        assert manager.analytics_logger is mock_logger
        assert manager.simulate_latency is True
        assert manager.latency_ms == 200


class TestExecuteOrder:
    """Tests pour execute_order"""

    @pytest.fixture
    def manager(self):
        """Fixture manager avec mock price provider"""
        mock_provider = Mock()
        mock_provider.get_price.return_value = 50000.0
        return PaperTradingManager(price_provider=mock_provider)

    def test_execute_order_buy(self, manager):
        """Test exécution ordre BUY"""
        order = {
            'type': 'BUY',
            'symbol': 'BTC/USDT:USDT',
            'size': 100.0
        }
        
        with patch.object(manager, 'apply_fees_slippage', return_value=50025.0):
            result = manager.execute_order(order)
        
        assert result['executed'] is True
        assert result['price'] == 50025.0
        assert result['simulated'] is True
        assert result['latency_ms'] == 0
        assert 'timestamp' in result

    def test_execute_order_sell(self, manager):
        """Test exécution ordre SELL"""
        order = {
            'type': 'SELL',
            'symbol': 'ETH/USDT:USDT',
            'size': 200.0
        }
        
        manager.price_provider.get_price.return_value = 3000.0
        
        with patch.object(manager, 'apply_fees_slippage', return_value=2985.0):
            result = manager.execute_order(order)
        
        assert result['executed'] is True
        assert result['price'] == 2985.0
        assert result['simulated'] is True

    def test_execute_order_with_latency(self):
        """Test exécution ordre avec simulation latence"""
        manager = PaperTradingManager(
            simulate_latency=True,
            latency_ms=50
        )
        manager.price_cache['BTC/USDT:USDT'] = 45000.0
        
        order = {'type': 'BUY', 'symbol': 'BTC/USDT:USDT', 'size': 100.0}
        
        with patch('time.sleep') as mock_sleep, \
             patch.object(manager, 'apply_fees_slippage', return_value=45022.5):
            result = manager.execute_order(order)
        
        mock_sleep.assert_called_once_with(0.05)  # 50ms
        assert result['latency_ms'] == 50


class TestGetCurrentPrice:
    """Tests pour get_current_price"""

    def test_get_current_price_from_provider(self):
        """Test obtention prix depuis price provider"""
        mock_provider = Mock()
        mock_provider.get_price.return_value = 42000.0
        
        manager = PaperTradingManager(price_provider=mock_provider)
        
        price = manager.get_current_price('BTC/USDT:USDT')
        
        assert price == 42000.0
        assert manager.price_cache['BTC/USDT:USDT'] == 42000.0
        mock_provider.get_price.assert_called_once_with('BTC/USDT:USDT')

    def test_get_current_price_provider_error(self):
        """Test gestion erreur price provider"""
        mock_provider = Mock()
        mock_provider.get_price.side_effect = Exception("Provider error")
        
        manager = PaperTradingManager(price_provider=mock_provider)
        manager.price_cache['BTC/USDT:USDT'] = 41000.0
        
        price = manager.get_current_price('BTC/USDT:USDT')
        
        # Doit fallback vers cache
        assert price == 41000.0

    def test_get_current_price_invalid_price(self):
        """Test gestion prix invalide du provider"""
        mock_provider = Mock()
        mock_provider.get_price.return_value = 0.0  # Prix invalide
        
        manager = PaperTradingManager(price_provider=mock_provider)
        manager.price_cache['BTC/USDT:USDT'] = 40000.0
        
        price = manager.get_current_price('BTC/USDT:USDT')
        
        # Doit fallback vers cache
        assert price == 40000.0

    def test_get_current_price_from_cache(self):
        """Test obtention prix depuis cache"""
        manager = PaperTradingManager()
        manager.price_cache['ETH/USDT:USDT'] = 3200.0
        
        price = manager.get_current_price('ETH/USDT:USDT')
        
        assert price == 3200.0

    def test_get_current_price_no_source(self):
        """Test quand aucune source de prix disponible"""
        manager = PaperTradingManager()
        
        price = manager.get_current_price('UNKNOWN/USDT:USDT')
        
        assert price == 0.0

    def test_update_price_cache(self):
        """Test mise à jour cache prix"""
        manager = PaperTradingManager()
        
        manager.update_price_cache('BTC/USDT:USDT', 48000.0)
        
        assert manager.price_cache['BTC/USDT:USDT'] == 48000.0


class TestHooks:
    """Tests pour les hooks on_position_opened et on_position_closed"""

    @pytest.fixture
    def manager_with_analytics(self):
        """Manager avec analytics DB et logger"""
        mock_db = Mock()
        mock_logger = Mock()
        return PaperTradingManager(
            analytics_db=mock_db,
            analytics_logger=mock_logger
        )

    @pytest.fixture
    def sample_position(self):
        """Position de test"""
        return TradingPosition(
            symbol='BTC/USDT:USDT',
            direction='LONG',
            entry=50000.0,
            sl=49000.0,
            tp=52000.0,
            size=100.0,
            capital=1000.0,
            condition_types=['RSI_OVERSOLD'],
            tp_escalier_enabled=True,
            tp_escalier_levels=[51000.0, 52000.0]
        )

    def test_on_position_opened_with_db(self, manager_with_analytics, sample_position):
        """Test hook ouverture position avec DB"""
        manager_with_analytics.analytics_db.insert_validated_setup.return_value = 'setup_123'
        
        manager_with_analytics.on_position_opened(sample_position)
        
        # Vérifier appel analytics DB
        args, _ = manager_with_analytics.analytics_db.insert_validated_setup.call_args
        setup_data = args[0]
        
        assert setup_data['symbol'] == 'BTC/USDT:USDT'
        assert setup_data['direction'] == 'LONG'
        assert setup_data['price'] == 50000.0
        assert setup_data['metadata']['trading_mode'] == 'PAPER'
        assert sample_position.setup_id == 'setup_123'

    def test_on_position_opened_db_error(self, manager_with_analytics, sample_position):
        """Test hook ouverture position avec erreur DB"""
        manager_with_analytics.analytics_db.insert_validated_setup.side_effect = Exception("DB Error")
        
        # Ne doit pas planter
        manager_with_analytics.on_position_opened(sample_position)

    def test_on_position_opened_no_db(self, sample_position):
        """Test hook ouverture position sans DB"""
        manager = PaperTradingManager()
        
        # Ne doit pas planter
        manager.on_position_opened(sample_position)

    def test_on_position_closed_with_analytics_logger(self, manager_with_analytics, sample_position):
        """Test hook fermeture position avec analytics logger"""
        result = {
            'exit': 51500.0,
            'reason': 'TP_HIT',
            'gross_pnl_pct': 3.0,
            'net_pnl_usdt': 150.0,
            'fees': 5.0,
            'slippage': 2.0
        }
        
        sample_position.setup_id = 'setup_123'
        sample_position.session_id = 'session_456'
        
        manager_with_analytics.on_position_closed(sample_position, result)
        
        # Vérifier appel analytics logger
        manager_with_analytics.analytics_logger.log_trade.assert_called_once()
        args, kwargs = manager_with_analytics.analytics_logger.log_trade.call_args
        
        assert kwargs['exit_price'] == 51500.0
        assert kwargs['reason'] == 'TP_HIT'
        assert kwargs['mode'] == 'PAPER'
        assert kwargs['pnl_data']['pnl_pct'] == 3.0

    def test_on_position_closed_logger_error(self, manager_with_analytics, sample_position):
        """Test hook fermeture position avec erreur logger"""
        manager_with_analytics.analytics_logger.log_trade.side_effect = Exception("Logger Error")
        
        result = {'exit': 49500.0, 'reason': 'SL_HIT'}
        
        # Ne doit pas planter
        manager_with_analytics.on_position_closed(sample_position, result)

    def test_on_position_closed_fallback_db(self, sample_position):
        """Test hook fermeture position avec fallback DB"""
        mock_db = Mock()
        manager = PaperTradingManager(analytics_db=mock_db)
        # analytics_logger n'est pas défini, doit fallback
        
        result = {'exit': 48000.0, 'reason': 'SL_HIT'}
        
        manager.on_position_closed(sample_position, result)
        
        # Pas d'appel à la DB (warning seulement)
        mock_db.insert_trade.assert_not_called()


class TestCheckActivePosition:
    """Tests pour check_active_position"""

    @pytest.fixture
    def manager_with_position(self):
        """Manager avec position active"""
        manager = PaperTradingManager()
        manager.price_cache['BTC/USDT:USDT'] = 50000.0
        
        # Créer position active
        position = TradingPosition(
            symbol='BTC/USDT:USDT',
            direction='LONG',
            entry=49000.0,
            sl=47000.0,
            tp=52000.0,
            size=100.0,
            capital=1000.0
        )
        position.start_time = time.time() - 60  # Position vieille de 1 minute
        manager.active_position = position
        
        return manager

    @pytest.mark.asyncio
    async def test_check_active_position_no_position(self):
        """Test check sans position active"""
        manager = PaperTradingManager()
        
        # Ne doit pas planter
        await manager.check_active_position()

    @pytest.mark.asyncio
    async def test_check_active_position_invalid_price(self, manager_with_position):
        """Test check avec prix invalide"""
        manager_with_position.price_cache.clear()  # Pas de prix
        
        await manager_with_position.check_active_position()
        
        # Position doit rester active
        assert manager_with_position.active_position is not None

    @pytest.mark.asyncio
    async def test_check_active_position_early_invalidation(self):
        """Test early invalidation"""
        manager = PaperTradingManager()
        manager.price_cache['BTC/USDT:USDT'] = 47500.0  # Prix défavorable
        
        position = TradingPosition(
            symbol='BTC/USDT:USDT',
            direction='LONG',
            entry=49000.0,
            sl=47000.0,
            tp=52000.0,
            size=100.0,
            capital=1000.0
        )
        position.start_time = time.time() - 15  # Position récente (15s)
        manager.active_position = position
        
        with patch.object(manager, 'check_early_invalidation', return_value=True), \
             patch.object(manager, 'close_position') as mock_close:
            
            await manager.check_active_position()
            
            mock_close.assert_called_once_with('EARLY_INVALIDATION', 47500.0)

    @pytest.mark.asyncio
    async def test_check_active_position_break_even(self, manager_with_position):
        """Test mise à jour break-even"""
        manager_with_position.price_cache['BTC/USDT:USDT'] = 50500.0  # Prix favorable
        
        with patch.object(manager_with_position, 'update_break_even') as mock_be, \
             patch.object(manager_with_position, 'check_tp_sl', return_value=None):
            
            await manager_with_position.check_active_position()
            
            mock_be.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_active_position_trailing_stop(self, manager_with_position):
        """Test trailing stop"""
        manager_with_position.price_cache['BTC/USDT:USDT'] = 49200.0  # +0.4% PnL
        
        with patch.object(manager_with_position, 'calculate_pnl_pct', return_value=0.4), \
             patch.object(manager_with_position, 'update_trailing_stop') as mock_trail, \
             patch.object(manager_with_position, 'check_tp_sl', return_value=None):
            
            await manager_with_position.check_active_position()
            
            mock_trail.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_active_position_tp_hit(self, manager_with_position):
        """Test TP atteint"""
        manager_with_position.price_cache['BTC/USDT:USDT'] = 52500.0  # Au-dessus TP
        
        with patch.object(manager_with_position, 'check_tp_sl', return_value='TP_HIT'), \
             patch.object(manager_with_position, 'close_position') as mock_close:
            
            await manager_with_position.check_active_position()
            
            mock_close.assert_called_once_with('TP_HIT', 52500.0)


class TestGetPortfolioSummary:
    """Tests pour get_portfolio_summary"""

    def test_get_portfolio_summary_basic(self):
        """Test résumé portefeuille basique"""
        manager = PaperTradingManager(initial_capital=2000.0)
        
        # Mock stats
        with patch.object(manager, 'get_stats', return_value={
            'roi': 15.5,
            'total_trades': 25,
            'winrate': 68.0,
            'profit_factor': 1.85
        }):
            summary = manager.get_portfolio_summary()
        
        assert summary['mode'] == 'PAPER'
        assert summary['capital'] == 2000.0
        assert summary['roi'] == 15.5
        assert summary['total_trades'] == 25
        assert summary['winrate'] == 68.0
        assert summary['profit_factor'] == 1.85
        assert summary['active_position'] is None
        assert summary['recent_trades'] == []

    def test_get_portfolio_summary_with_position(self):
        """Test résumé avec position active"""
        manager = PaperTradingManager()
        
        # Position active
        position = TradingPosition(
            symbol='ETH/USDT:USDT',
            direction='SHORT',
            entry=3000.0,
            sl=3150.0,
            tp=2800.0,
            size=200.0,
            capital=1000.0
        )
        manager.active_position = position
        
        with patch.object(manager, 'get_stats', return_value={
            'roi': 5.2, 'total_trades': 10, 'winrate': 70.0, 'profit_factor': 1.6
        }):
            summary = manager.get_portfolio_summary()
        
        assert summary['active_position'] is not None
        assert summary['active_position']['symbol'] == 'ETH/USDT:USDT'
        assert summary['active_position']['direction'] == 'SHORT'

    def test_get_portfolio_summary_with_recent_trades(self):
        """Test résumé avec trades récents"""
        manager = PaperTradingManager()
        
        # Simuler trades fermés
        manager.closed_trades = [f'trade_{i}' for i in range(15)]
        
        with patch.object(manager, 'get_stats', return_value={
            'roi': 8.3, 'total_trades': 15, 'winrate': 73.3, 'profit_factor': 2.1
        }):
            summary = manager.get_portfolio_summary()
        
        # Doit retourner seulement les 10 derniers
        assert len(summary['recent_trades']) == 10
        assert summary['recent_trades'][-1] == 'trade_14'


class TestCreatePaperTradingManager:
    """Tests pour la factory function"""

    def test_create_paper_trading_manager_default(self):
        """Test factory avec paramètres par défaut"""
        manager = create_paper_trading_manager()
        
        assert isinstance(manager, PaperTradingManager)
        assert manager.capital == 1000.0
        assert manager.price_provider is None
        assert manager.analytics_db is None
        assert manager.analytics_logger is None

    def test_create_paper_trading_manager_custom(self):
        """Test factory avec paramètres personnalisés"""
        mock_provider = Mock()
        mock_db = Mock()
        mock_logger = Mock()
        
        manager = create_paper_trading_manager(
            initial_capital=3000.0,
            price_provider=mock_provider,
            analytics_db=mock_db,
            analytics_logger=mock_logger
        )
        
        assert isinstance(manager, PaperTradingManager)
        assert manager.capital == 3000.0
        assert manager.price_provider is mock_provider
        assert manager.analytics_db is mock_db
        assert manager.analytics_logger is mock_logger


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
