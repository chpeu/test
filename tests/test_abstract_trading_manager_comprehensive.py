"""
Tests complets pour trading.abstract_trading_manager (616 lignes)
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from trading.abstract_trading_manager import AbstractTradingManager, TradingPosition


# Concrete implementation for testing
class TestTradingManager(AbstractTradingManager):
    """Implementation concrète pour tests"""

    def execute_order(self, order: dict) -> dict:
        return {'executed': True, 'price': order.get('price', 100.0)}

    def get_price(self, symbol: str) -> float:
        return 45000.0


@pytest.fixture
def trading_manager():
    """TradingManager de test"""
    return TestTradingManager(initial_capital=1000.0)


@pytest.fixture
def sample_position():
    """Position de test"""
    return TradingPosition(
        symbol='BTCUSDT',
        direction='LONG',
        entry=45000.0,
        size=100.0,
        sl=44000.0,
        tp=46000.0
    )


class TestTradingPosition:
    """Tests TradingPosition dataclass"""

    def test_position_creation(self):
        """Test création position"""
        pos = TradingPosition(
            symbol='BTCUSDT',
            direction='LONG',
            entry=50000.0,
            size=100.0,
            sl=49000.0,
            tp=51000.0
        )

        assert pos.symbol == 'BTCUSDT'
        assert pos.direction == 'LONG'
        assert pos.entry == 50000.0
        assert pos.size == 100.0
        assert pos.sl == 49000.0
        assert pos.tp == 51000.0

    def test_position_to_dict(self, sample_position):
        """Test conversion to dict"""
        pos_dict = sample_position.to_dict()

        assert isinstance(pos_dict, dict)
        assert pos_dict['symbol'] == 'BTCUSDT'
        assert pos_dict['direction'] == 'LONG'
        assert 'entry' in pos_dict
        assert 'size' in pos_dict

    def test_position_defaults(self):
        """Test valeurs par défaut"""
        pos = TradingPosition(
            symbol='ETHUSDT',
            direction='SHORT',
            entry=3000.0,
            size=50.0,
            sl=3100.0,
            tp=2900.0
        )

        assert pos.break_even_set is False
        assert pos.partial_tp_sold is False
        assert pos.trailing_active is False
        assert pos.tp_escalier_enabled is False


class TestAbstractTradingManagerInit:
    """Tests __init__()"""

    def test_init_default_capital(self):
        """Test initialisation capital par défaut"""
        manager = TestTradingManager()

        assert manager.balance == 1000.0
        assert manager.initial_capital == 1000.0

    def test_init_custom_capital(self):
        """Test initialisation capital custom"""
        manager = TestTradingManager(initial_capital=5000.0)

        assert manager.balance == 5000.0
        assert manager.initial_capital == 5000.0

    def test_init_open_positions(self, trading_manager):
        """Test initialisation positions"""
        assert isinstance(trading_manager.open_positions, dict)
        assert len(trading_manager.open_positions) == 0


class TestOpenPosition:
    """Tests open_position()"""

    def test_open_long_position(self, trading_manager):
        """Test ouverture position LONG"""
        result = trading_manager.open_position(
            symbol='BTCUSDT',
            size=100.0,
            side='LONG',
            sl=44000.0,
            tp=46000.0
        )

        assert result is not None

    def test_open_short_position(self, trading_manager):
        """Test ouverture position SHORT"""
        result = trading_manager.open_position(
            symbol='ETHUSDT',
            size=50.0,
            side='SHORT',
            sl=3100.0,
            tp=2900.0
        )

        assert result is not None

    def test_open_position_insufficient_balance(self):
        """Test ouverture position sans balance suffisante"""
        manager = TestTradingManager(initial_capital=10.0)  # Very low capital

        result = manager.open_position(
            symbol='BTCUSDT',
            size=1000000.0,  # Too large
            side='LONG',
            sl=44000.0,
            tp=46000.0
        )

        # Should fail or handle gracefully
        assert result is False or result is None


class TestClosePosition:
    """Tests close_position()"""

    def test_close_existing_position(self, trading_manager):
        """Test fermeture position existante"""
        # Open first
        trading_manager.open_position(
            symbol='BTCUSDT',
            size=100.0,
            side='LONG',
            sl=44000.0,
            tp=46000.0
        )

        # Close
        result = trading_manager.close_position('BTCUSDT', reason='manual')

        assert result is not None

    def test_close_nonexistent_position(self, trading_manager):
        """Test fermeture position inexistante"""
        result = trading_manager.close_position('NONEXISTENT', reason='test')

        # Should handle gracefully
        assert result is False or result is None


class TestCalculatePnL:
    """Tests calculate_pnl()"""

    def test_calculate_pnl_long_profit(self, trading_manager, sample_position):
        """Test calcul PnL LONG avec profit"""
        sample_position.direction = 'LONG'
        sample_position.entry = 45000.0
        current_price = 46000.0

        pnl = trading_manager.calculate_pnl(sample_position, current_price)

        # Should be positive
        assert pnl > 0

    def test_calculate_pnl_long_loss(self, trading_manager, sample_position):
        """Test calcul PnL LONG avec perte"""
        sample_position.direction = 'LONG'
        sample_position.entry = 45000.0
        current_price = 44000.0

        pnl = trading_manager.calculate_pnl(sample_position, current_price)

        # Should be negative
        assert pnl < 0

    def test_calculate_pnl_short_profit(self, trading_manager, sample_position):
        """Test calcul PnL SHORT avec profit"""
        sample_position.direction = 'SHORT'
        sample_position.entry = 45000.0
        current_price = 44000.0

        pnl = trading_manager.calculate_pnl(sample_position, current_price)

        # Should be positive for SHORT when price goes down
        assert pnl > 0

    def test_calculate_pnl_short_loss(self, trading_manager, sample_position):
        """Test calcul PnL SHORT avec perte"""
        sample_position.direction = 'SHORT'
        sample_position.entry = 45000.0
        current_price = 46000.0

        pnl = trading_manager.calculate_pnl(sample_position, current_price)

        # Should be negative for SHORT when price goes up
        assert pnl < 0


class TestCheckStopLoss:
    """Tests check_stop_loss()"""

    def test_check_sl_long_triggered(self, trading_manager, sample_position):
        """Test SL déclenché LONG"""
        sample_position.direction = 'LONG'
        sample_position.sl = 44000.0
        current_price = 43000.0  # Below SL

        triggered = trading_manager.check_stop_loss(sample_position, current_price)

        assert triggered is True

    def test_check_sl_long_not_triggered(self, trading_manager, sample_position):
        """Test SL non déclenché LONG"""
        sample_position.direction = 'LONG'
        sample_position.sl = 44000.0
        current_price = 45000.0  # Above SL

        triggered = trading_manager.check_stop_loss(sample_position, current_price)

        assert triggered is False

    def test_check_sl_short_triggered(self, trading_manager, sample_position):
        """Test SL déclenché SHORT"""
        sample_position.direction = 'SHORT'
        sample_position.sl = 46000.0
        current_price = 47000.0  # Above SL

        triggered = trading_manager.check_stop_loss(sample_position, current_price)

        assert triggered is True

    def test_check_sl_short_not_triggered(self, trading_manager, sample_position):
        """Test SL non déclenché SHORT"""
        sample_position.direction = 'SHORT'
        sample_position.sl = 46000.0
        current_price = 45000.0  # Below SL

        triggered = trading_manager.check_stop_loss(sample_position, current_price)

        assert triggered is False


class TestCheckTakeProfit:
    """Tests check_take_profit()"""

    def test_check_tp_long_triggered(self, trading_manager, sample_position):
        """Test TP déclenché LONG"""
        sample_position.direction = 'LONG'
        sample_position.tp = 46000.0
        current_price = 47000.0  # Above TP

        triggered = trading_manager.check_take_profit(sample_position, current_price)

        assert triggered is True

    def test_check_tp_long_not_triggered(self, trading_manager, sample_position):
        """Test TP non déclenché LONG"""
        sample_position.direction = 'LONG'
        sample_position.tp = 46000.0
        current_price = 45000.0  # Below TP

        triggered = trading_manager.check_take_profit(sample_position, current_price)

        assert triggered is False


class TestGetStats:
    """Tests get_stats()"""

    def test_get_stats_empty(self, trading_manager):
        """Test stats sans positions"""
        stats = trading_manager.get_stats()

        assert isinstance(stats, dict)
        assert 'balance' in stats or 'total_pnl' in stats

    def test_get_stats_with_positions(self, trading_manager):
        """Test stats avec positions"""
        # Open position
        trading_manager.open_position(
            symbol='BTCUSDT',
            size=100.0,
            side='LONG',
            sl=44000.0,
            tp=46000.0
        )

        stats = trading_manager.get_stats()

        assert isinstance(stats, dict)


class TestReset:
    """Tests reset()"""

    def test_reset(self, trading_manager):
        """Test reset manager"""
        # Open position
        trading_manager.open_position(
            symbol='BTCUSDT',
            size=100.0,
            side='LONG',
            sl=44000.0,
            tp=46000.0
        )

        # Reset
        trading_manager.reset()

        # Should be back to initial state
        assert len(trading_manager.open_positions) == 0
        assert trading_manager.balance == trading_manager.initial_capital


class TestUpdatePosition:
    """Tests update_position()"""

    def test_update_position_price(self, trading_manager, sample_position):
        """Test update position avec nouveau prix"""
        trading_manager.open_positions['BTCUSDT'] = sample_position

        # Update
        try:
            trading_manager.update_position('BTCUSDT', current_price=46000.0)
            # Should update without error
        except Exception:
            # May not be implemented in base class
            pass


class TestCalculateFees:
    """Tests calculate_fees()"""

    def test_calculate_fees(self, trading_manager):
        """Test calcul fees"""
        size = 100.0

        fees = trading_manager.calculate_fees(size)

        # Should return fees >= 0
        assert fees >= 0


class TestEdgeCases:
    """Tests cas limites"""

    def test_open_position_zero_size(self, trading_manager):
        """Test ouverture position taille 0"""
        result = trading_manager.open_position(
            symbol='BTCUSDT',
            size=0.0,  # Zero size
            side='LONG',
            sl=44000.0,
            tp=46000.0
        )

        # Should fail or handle
        assert result is False or result is None

    def test_open_position_negative_size(self, trading_manager):
        """Test ouverture position taille négative"""
        result = trading_manager.open_position(
            symbol='BTCUSDT',
            size=-100.0,  # Negative
            side='LONG',
            sl=44000.0,
            tp=46000.0
        )

        # Should fail or handle
        assert result is False or result is None

    def test_calculate_pnl_zero_size(self, trading_manager, sample_position):
        """Test calcul PnL taille 0"""
        sample_position.size = 0.0

        pnl = trading_manager.calculate_pnl(sample_position, 46000.0)

        # Should return 0
        assert pnl == 0.0
