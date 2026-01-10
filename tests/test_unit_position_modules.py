#!/usr/bin/env python3
"""
Comprehensive Unit Tests for Position Modules - Trade Cursor v7.0
Target: 95% coverage for all position modules
"""

import pytest
import unittest
import sys
import os
import math
from unittest.mock import patch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.position import (
    TPSLConfig,
    calculate_fixed_levels,
    calculate_atr_levels,
    validate_levels,
    PartialTPManager,
    TPEscalierManager,
    TrailingStopManager,
    TrailingStopConfig,
    EarlyInvalidationChecker,
    EarlyInvalidationConfig,
    RecoveryModeManager,
    RecoveryModeConfig,
    PnLCalculator,
    AnalyticsLogger
)


# ============================================================================
# TP/SL Calculator Tests
# ============================================================================

class TestTPSLCalculator:
    """Tests for TP/SL calculation functions"""

    def test_tpsl_config_default(self):
        """Test TPSLConfig with default values"""
        config = TPSLConfig()
        assert config.fixed_tp_pct > 0
        assert config.fixed_sl_pct > 0
        assert config.atr_mult_tp > 0
        assert config.atr_mult_sl > 0

    def test_tpsl_config_custom(self):
        """Test TPSLConfig with custom values"""
        config = TPSLConfig(fixed_tp_pct=1.0, fixed_sl_pct=0.5, atr_mult_tp=2.5, atr_mult_sl=1.5)
        assert config.fixed_tp_pct == 1.0
        assert config.fixed_sl_pct == 0.5
        assert config.atr_mult_tp == 2.5
        assert config.atr_mult_sl == 1.5

    def test_calculate_fixed_levels_long(self):
        """Test calculate_fixed_levels for LONG position"""
        config = TPSLConfig(fixed_tp_pct=0.6, fixed_sl_pct=0.25)
        sl, tp = calculate_fixed_levels(entry=50000.0, direction="LONG", config=config)

        assert sl < 50000.0, "SL should be below entry for LONG"
        assert tp > 50000.0, "TP should be above entry for LONG"

        # Verify percentages
        sl_pct = abs((50000.0 - sl) / 50000.0 * 100)
        tp_pct = abs((tp - 50000.0) / 50000.0 * 100)
        assert abs(sl_pct - 0.25) < 0.01
        assert abs(tp_pct - 0.6) < 0.01

    def test_calculate_fixed_levels_short(self):
        """Test calculate_fixed_levels for SHORT position"""
        config = TPSLConfig(fixed_tp_pct=0.6, fixed_sl_pct=0.25)
        sl, tp = calculate_fixed_levels(entry=50000.0, direction="SHORT", config=config)

        assert sl > 50000.0, "SL should be above entry for SHORT"
        assert tp < 50000.0, "TP should be below entry for SHORT"

    def test_calculate_atr_levels_long(self):
        """Test calculate_atr_levels for LONG position"""
        config = TPSLConfig(atr_mult_tp=2.5, atr_mult_sl=1.5, atr_min=0.15, atr_max=1.5)
        sl, tp = calculate_atr_levels(
            entry=50000.0,
            atr=200.0,
            atr5m=None,
            direction="LONG",
            config=config
        )

        assert sl < 50000.0
        assert tp > 50000.0

        # ATR percent = (200/50000)*100 = 0.4%
        # Clamp to atr_min (0.15%) - atr_max (1.5%) → 0.4%
        # expected_sl = 50000 * (1 - 0.4/100 * 1.5) = 50000 * 0.994 = 49700
        # expected_tp = 50000 * (1 + 0.4/100 * 2.5) = 50000 * 1.01 = 50500

    def test_calculate_atr_levels_short(self):
        """Test calculate_atr_levels for SHORT position"""
        config = TPSLConfig(atr_mult_tp=2.5, atr_mult_sl=1.5)
        sl, tp = calculate_atr_levels(
            entry=50000.0,
            atr=200.0,
            atr5m=None,
            direction="SHORT",
            config=config
        )

        assert sl > 50000.0
        assert tp < 50000.0

    def test_validate_levels_valid(self):
        """Test validate_levels with valid levels"""
        # validate_levels only checks if levels are different enough from entry
        # It doesn't check direction logic
        result = validate_levels(
            entry=50000.0,
            sl=49500.0,
            tp=50600.0,
            tolerance=0.0001
        )
        assert result is True

    def test_validate_levels_invalid_too_close(self):
        """Test validate_levels with levels too close to entry"""
        # Levels too close to entry (less than tolerance)
        result = validate_levels(
            entry=50000.0,
            sl=50000.0,  # Same as entry
            tp=50600.0,
            tolerance=0.0001
        )
        assert result is False

    def test_validate_levels_valid_large_tolerance(self):
        """Test validate_levels with larger tolerance"""
        result = validate_levels(
            entry=50000.0,
            sl=49750.0,  # 0.5% away
            tp=50250.0,  # 0.5% away
            tolerance=0.001  # 0.1% tolerance
        )
        assert result is True


# ============================================================================
# PnL Calculator Tests
# ============================================================================

class TestPnLCalculator:
    """Tests for PnL calculation"""

    def test_calculate_pnl_percent_long_profit(self):
        """Test PnL calculation for profitable LONG"""
        calc = PnLCalculator()
        pnl = calc.calculate_pnl_percent(
            entry=50000.0,
            current_price=50500.0,
            direction="LONG"
        )
        assert abs(pnl - 1.0) < 0.01  # ~1% profit

    def test_calculate_pnl_percent_long_loss(self):
        """Test PnL calculation for losing LONG"""
        calc = PnLCalculator()
        pnl = calc.calculate_pnl_percent(
            entry=50000.0,
            current_price=49500.0,
            direction="LONG"
        )
        assert abs(pnl - (-1.0)) < 0.01  # ~-1% loss

    def test_calculate_pnl_percent_short_profit(self):
        """Test PnL calculation for profitable SHORT"""
        calc = PnLCalculator()
        pnl = calc.calculate_pnl_percent(
            entry=50000.0,
            current_price=49500.0,
            direction="SHORT"
        )
        assert abs(pnl - 1.0) < 0.01  # ~1% profit

    def test_calculate_pnl_percent_short_loss(self):
        """Test PnL calculation for losing SHORT"""
        calc = PnLCalculator()
        pnl = calc.calculate_pnl_percent(
            entry=50000.0,
            current_price=50500.0,
            direction="SHORT"
        )
        assert abs(pnl - (-1.0)) < 0.01  # ~-1% loss

    def test_calculate_pnl_usdt(self):
        """Test PnL calculation in USDT"""
        calc = PnLCalculator()
        position = {
            'entry': 50000.0,
            'size': 1000.0,
            'direction': 'LONG',
            'partial_tp_sold': False
        }
        # 2% profit: current_price = 51000 (50000 * 1.02)
        pnl_usdt = calc.calculate_pnl_usdt(position, current_price=51000.0)
        # PnL = size * (price_diff / entry) = 1000 * (1000 / 50000) = 1000 * 0.02 = 20
        assert abs(pnl_usdt - 20.0) < 0.01

    def test_calculate_realized_pnl_with_fees(self):
        """Test realized PnL calculation with fees"""
        calc = PnLCalculator()
        position = {
            'entry': 50000.0,
            'size': 1000.0,
            'direction': 'LONG',
            'partial_tp_sold': False,
            'partial_profit_usdt': 0.0
        }
        # Exit at +2% = 51000
        result = calc.calculate_realized_pnl(
            position=position,
            exit_price=51000.0,
            fees_percent=0.04  # 0.04% fees
        )

        assert 'net_pnl' in result
        assert 'fees' in result
        assert 'pnl_pct' in result

        # Fees = size * (fees_percent/100) * 2 = 1000 * 0.0004 * 2 = 0.8 USDT
        expected_fees = 1000.0 * 0.04 / 100 * 2
        assert abs(result['fees'] - expected_fees) < 0.01

        # PnL = 2% = 1000 * 0.02 = 20 USDT
        # Net = 20 - 0.8 = 19.2
        assert abs(result['net_pnl'] - 19.2) < 0.1

    def test_calculate_realized_pnl_loss(self):
        """Test realized PnL calculation with loss"""
        calc = PnLCalculator()
        position = {
            'entry': 50000.0,
            'size': 1000.0,
            'direction': 'LONG',
            'partial_tp_sold': False,
            'partial_profit_usdt': 0.0
        }
        # Exit at -1% = 49500
        result = calc.calculate_realized_pnl(
            position=position,
            exit_price=49500.0,
            fees_percent=0.04
        )

        # Loss = -1% = -10 USDT, fees = 0.8, total = -10.8
        assert result['net_pnl'] < -10.0


# ============================================================================
# Early Invalidation Checker Tests
# ============================================================================

class TestEarlyInvalidationChecker:
    """Tests for early invalidation logic"""

    def test_early_invalidation_config_default(self):
        """Test EarlyInvalidationConfig defaults"""
        config = EarlyInvalidationConfig()
        assert config.enabled is True
        assert config.threshold_15s < 0  # Negative threshold
        assert config.threshold_30s < 0
        assert config.adaptive_enabled is True

    def test_should_check_time_window(self):
        """Test should_check for early invalidation time window"""
        checker = EarlyInvalidationChecker()

        # Before window (< 10s)
        assert checker.should_check(5) is False

        # Within window (10-30s)
        assert checker.should_check(15) is True
        assert checker.should_check(25) is True

        # After window (> 30s)
        assert checker.should_check(35) is False

    def test_check_invalidation_not_in_window(self):
        """Test no invalidation when outside time window"""
        checker = EarlyInvalidationChecker()
        import time

        position = {
            'entry': 50000.0,
            'direction': 'LONG',
            'start_time': time.time() - 5,  # 5s ago
            'atr': 200.0
        }

        result = checker.check_invalidation(
            position=position,
            current_price=49900.0,
            pnl_percent=-0.2
        )

        assert result is None  # Too early

    def test_check_invalidation_long_below_threshold(self):
        """Test invalidation for LONG when PnL below threshold"""
        checker = EarlyInvalidationChecker()
        import time

        position = {
            'entry': 50000.0,
            'direction': 'LONG',
            'start_time': time.time() - 15,  # 15s ago
            'atr': 200.0,  # 0.4% of entry
            'symbol': 'BTC/USDT'
        }

        # PnL = -0.15% (below default threshold_15s of -0.12%)
        result = checker.check_invalidation(
            position=position,
            current_price=49925.0,
            pnl_percent=-0.15
        )

        assert result == 'EARLY_INVALIDATION'

    def test_get_adaptive_threshold_low_vol(self):
        """Test adaptive threshold with low volatility"""
        checker = EarlyInvalidationChecker()
        config = EarlyInvalidationConfig(
            threshold_15s=-0.12,
            adaptive_enabled=True,
            low_vol_multiplier=0.7
        )
        checker.config = config

        # Low ATR (< 0.3%) - less strict
        threshold = checker.get_adaptive_threshold(elapsed=12, atr_percent=0.2)
        # Expected: -0.12 * 0.7 = -0.084, clamped to [-0.15, -0.05]
        assert -0.09 < threshold < -0.08

    def test_get_adaptive_threshold_high_vol(self):
        """Test adaptive threshold with high volatility"""
        checker = EarlyInvalidationChecker()
        config = EarlyInvalidationConfig(
            threshold_15s=-0.12,
            adaptive_enabled=True,
            high_vol_multiplier=1.3
        )
        checker.config = config

        # High ATR (> 0.8%) - more strict
        threshold = checker.get_adaptive_threshold(elapsed=12, atr_percent=1.0)
        # Expected: -0.12 * 1.3 = -0.156, clamped to -0.15
        assert threshold <= -0.15


# ============================================================================
# Recovery Mode Manager Tests
# ============================================================================

class TestRecoveryModeManager:
    """Tests for recovery mode logic"""

    def test_recovery_mode_config_default(self):
        """Test RecoveryModeConfig defaults"""
        config = RecoveryModeConfig()
        assert len(config.levels) == 3
        assert all('trigger_loss_streak' in level for level in config.levels)
        assert config.mode == 'PROGRESSIVE'

    def test_get_recovery_level_no_streak(self):
        """Test no recovery mode when no loss streak"""
        manager = RecoveryModeManager()
        level = manager.get_recovery_level(loss_streak=0)
        assert level is None

    def test_get_recovery_level_1(self):
        """Test recovery level 1 activation"""
        manager = RecoveryModeManager()
        level = manager.get_recovery_level(loss_streak=2)

        assert level is not None
        assert level['level'] == 1
        assert 'min_score_boost' in level
        assert 'position_size_reduction' in level

    def test_get_recovery_level_2(self):
        """Test recovery level 2 activation"""
        manager = RecoveryModeManager()
        level = manager.get_recovery_level(loss_streak=3)

        assert level is not None
        assert level['level'] >= 2

    def test_get_recovery_level_3_max(self):
        """Test recovery level 3 (max) activation"""
        manager = RecoveryModeManager()
        level = manager.get_recovery_level(loss_streak=5)

        assert level is not None
        assert level['level'] == 3

    def test_get_position_size_multiplier(self):
        """Test position size multiplier based on loss streak"""
        manager = RecoveryModeManager()

        # No streak - no reduction
        mult = manager.get_position_size_multiplier(loss_streak=0)
        assert mult == 1.0

        # Level 1 (loss_streak=2) - 15% reduction
        mult = manager.get_position_size_multiplier(loss_streak=2)
        assert mult == 0.85

        # Level 3 (loss_streak=5) - 50% reduction
        mult = manager.get_position_size_multiplier(loss_streak=5)
        assert mult == 0.5

    def test_activate_and_deactivate(self):
        """Test activating and deactivating recovery mode"""
        manager = RecoveryModeManager()

        # Activate
        level = manager.activate(loss_streak=3)
        assert manager.active is True
        assert manager.remaining_trades == level['duration_trades']

        # Update after win - should deactivate
        manager.update_after_trade(is_win=True)
        assert manager.active is False


# ============================================================================
# Trailing Stop Manager Tests
# ============================================================================

class TestTrailingStopManager:
    """Tests for trailing stop logic"""

    def test_trailing_stop_config_default(self):
        """Test TrailingStopConfig defaults"""
        config = TrailingStopConfig()
        assert config.trigger_pnl > 0
        assert config.atr_multiplier > 0
        assert config.min_distance > 0
        assert config.max_distance > 0

    def test_should_trigger(self):
        """Test should_trigger method"""
        manager = TrailingStopManager()
        config = TrailingStopConfig(trigger_pnl=0.25)
        manager.config = config

        # Below trigger
        assert manager.should_trigger(pnl_percent=0.2) is False

        # Above trigger
        assert manager.should_trigger(pnl_percent=0.3) is True

    def test_calculate_adaptive_distance(self):
        """Test adaptive distance calculation based on ATR"""
        manager = TrailingStopManager()
        config = TrailingStopConfig(
            atr_multiplier=0.4,
            min_distance=0.08,
            max_distance=0.25
        )
        manager.config = config

        # Low ATR - should clamp to min_distance
        distance = manager.calculate_adaptive_distance(atr_percent=0.1)
        assert distance == 0.08

        # Normal ATR
        distance = manager.calculate_adaptive_distance(atr_percent=0.5)
        # 0.5 * 0.4 = 0.2
        assert abs(distance - 0.2) < 0.01

        # High ATR - should clamp to max_distance
        distance = manager.calculate_adaptive_distance(atr_percent=1.5)
        assert distance == 0.25

    def test_update_trailing_stop_long_activation(self):
        """Test trailing stop activation for LONG"""
        manager = TrailingStopManager()

        position = {
            'entry': 50000.0,
            'sl': 49750.0,
            'direction': 'LONG',
            'atr': 200.0,  # 0.4% of entry
            'symbol': 'BTC/USDT'
        }

        # PnL = +0.3% (above trigger_pnl of 0.25%)
        new_sl = manager.update_trailing_stop(
            position=position,
            current_price=50150.0,
            pnl_percent=0.3
        )

        # Should return new SL (trailing activated)
        assert new_sl is not None
        assert new_sl > 49750.0  # SL moved up

    def test_update_trailing_stop_not_activated(self):
        """Test trailing stop before activation threshold"""
        manager = TrailingStopManager()

        position = {
            'entry': 50000.0,
            'sl': 49750.0,
            'direction': 'LONG',
            'atr': 200.0
        }

        # PnL = +0.2% (below trigger_pnl of 0.25%)
        new_sl = manager.update_trailing_stop(
            position=position,
            current_price=50100.0,
            pnl_percent=0.2
        )

        # Should not activate
        assert new_sl is None

    def test_update_trailing_stop_short(self):
        """Test trailing stop for SHORT"""
        manager = TrailingStopManager()

        position = {
            'entry': 50000.0,
            'sl': 50250.0,
            'direction': 'SHORT',
            'atr': 200.0,
            'symbol': 'BTC/USDT'
        }

        # PnL = +0.3% (price down 0.3%)
        new_sl = manager.update_trailing_stop(
            position=position,
            current_price=49850.0,
            pnl_percent=0.3
        )

        # Should return new SL (moved down)
        assert new_sl is not None
        assert new_sl < 50250.0


# ============================================================================
# Partial TP Manager Tests
# ============================================================================

class TestPartialTPManager:
    """Tests for partial take profit logic"""

    def test_check_trigger_long_profit(self):
        """Test partial TP trigger for LONG with profit"""
        manager = PartialTPManager()

        position = {
            'entry': 50000.0,
            'direction': 'LONG',
            'partial_tp_sold': False
        }

        # Price up 0.3% (above 0.25% trigger)
        should_trigger = manager.check_trigger(
            position=position,
            current_price=50150.0,
            trigger_pct=0.25
        )

        assert should_trigger is True

    def test_check_trigger_already_sold(self):
        """Test no re-trigger when already sold"""
        manager = PartialTPManager()

        position = {
            'entry': 50000.0,
            'direction': 'LONG',
            'partial_tp_sold': True  # Already sold
        }

        should_trigger = manager.check_trigger(
            position=position,
            current_price=50600.0,
            trigger_pct=0.25
        )

        assert should_trigger is False

    def test_check_trigger_not_reached(self):
        """Test no trigger when profit threshold not reached"""
        manager = PartialTPManager()

        position = {
            'entry': 50000.0,
            'direction': 'LONG',
            'partial_tp_sold': False
        }

        # Price up only 0.1% (below 0.25% trigger)
        should_trigger = manager.check_trigger(
            position=position,
            current_price=50050.0,
            trigger_pct=0.25
        )

        assert should_trigger is False

    def test_execute_partial_tp_long(self):
        """Test executing partial TP for LONG"""
        manager = PartialTPManager()

        position = {
            'symbol': 'BTCUSDT',
            'entry': 50000.0,
            'size': 1000.0,
            'direction': 'LONG'
        }

        # 🔥 FIX: Mocker TRADING_CONFIG directement dans config.py
        with patch('config.TRADING_CONFIG', {'partial_tp_percent': 65.0}):
            result = manager.execute_partial_tp(
                position=position,
                current_price=50150.0  # +0.3%
            )

        assert result is not None
        assert 'size_sold' in result
        assert 'profit_usdt' in result
        assert 'size_remaining' in result

        # partial_tp_percent from config (currently 65%) of size should be sold
        # 1000.0 * 0.65 = 650.0 sold, 350.0 remaining
        assert abs(result['size_sold'] - 650.0) < 0.1
        assert abs(result['size_remaining'] - 350.0) < 0.1

    def test_update_sl_after_partial_tp(self):
        """Test SL moved to break-even after partial TP"""
        manager = PartialTPManager()

        position = {
            'entry': 50000.0,
            'sl': 49750.0,
            'direction': 'LONG'
        }

        # Forcer lock-in à 0% pour garantir un BE exact (indépendant de config_overrides.json)
        with patch.dict('config.TRADING_CONFIG', {'partial_tp_be_lock_in_pct': 0.0}, clear=False):
            new_sl = manager.update_sl_after_partial_tp(position)

        # SL should be at entry (break-even)
        assert new_sl == 50000.0
        assert position['sl'] == 50000.0
        assert position['break_even_set'] is True

# ============================================================================
# TP Escalier Manager Tests
# ============================================================================

class TestTPEscalierManager:
    """Tests for TP escalier (multi-level TP) logic"""

    def test_initialize_levels(self):
        """Test TP escalier initialization"""
        manager = TPEscalierManager()

        position = {'symbol': 'BTCUSDT', 'entry': 50000.0, 'size': 1000.0}
        levels_config = [
            {'pnl': 0.5, 'size_pct': 0.3, 'move_sl': 'entry'},
            {'pnl': 1.0, 'size_pct': 0.3, 'move_sl': 'entry'},
            {'pnl': 1.5, 'size_pct': 0.4, 'move_sl': 'keep'}
        ]

        manager.initialize_levels(position, levels_config)

        assert position['tp_escalier_enabled'] is True
        assert len(position['tp_escalier_levels']) == 3
        assert position['tp_escalier_current_level'] == 0
        assert position['tp_escalier_size_remaining'] == 1.0

    def test_check_and_execute_levels_long(self):
        """Test TP escalier level execution for LONG"""
        manager = TPEscalierManager()

        position = {
            'symbol': 'BTCUSDT',
            'entry': 50000.0,
            'size': 1000.0,
            'direction': 'LONG',
            'sl': 49750.0,
            'tp_escalier_enabled': True,
            'tp_escalier_levels': [
                {'pnl': 0.5, 'size_pct': 0.3, 'move_sl': 'entry'},
                {'pnl': 1.0, 'size_pct': 0.3, 'move_sl': 'entry'}
            ],
            'tp_escalier_current_level': 0,
            'tp_escalier_size_remaining': 1.0,
            'tp_escalier_profits': []
        }

        # Price reaches first level (+0.5%)
        current_price = 50250.0  # +0.5%
        result = manager.check_and_execute_levels(position, current_price)

        assert result is not None
        assert result['level'] == 1
        assert abs(result['size_pct'] - 0.3) < 0.01

        # Check position updated
        assert position['tp_escalier_current_level'] == 1
        assert abs(position['tp_escalier_size_remaining'] - 0.7) < 0.01
        assert position['sl'] == 50000.0  # Moved to entry (breakeven)

    def test_check_and_execute_levels_multiple(self):
        """Test multiple TP escalier levels"""
        manager = TPEscalierManager()

        position = {
            'entry': 50000.0,
            'size': 1000.0,
            'direction': 'LONG',
            'sl': 49750.0,
            'tp_escalier_enabled': True,
            'tp_escalier_levels': [
                {'pnl': 0.5, 'size_pct': 0.3, 'move_sl': 'entry'},
                {'pnl': 1.0, 'size_pct': 0.3, 'move_sl': 'entry'},
                {'pnl': 1.5, 'size_pct': 0.4, 'move_sl': 'keep'}
            ],
            'tp_escalier_current_level': 0,
            'tp_escalier_size_remaining': 1.0,
            'tp_escalier_profits': []
        }

        # Execute level 1
        manager.check_and_execute_levels(position, 50250.0)
        assert len(position['tp_escalier_profits']) == 1

        # Execute level 2
        manager.check_and_execute_levels(position, 50500.0)
        assert len(position['tp_escalier_profits']) == 2

        # Execute level 3
        manager.check_and_execute_levels(position, 50750.0)
        assert len(position['tp_escalier_profits']) == 3

        # All levels consumed
        assert position['tp_escalier_current_level'] == 3

    def test_get_total_profit(self):
        """Test total profit calculation"""
        manager = TPEscalierManager()

        position = {
            'tp_escalier_profits': [
                {'profit_usdt': 15.0},
                {'profit_usdt': 30.0},
                {'profit_usdt': 60.0}
            ]
        }

        total = manager.get_total_profit(position)
        assert abs(total - 105.0) < 0.01


# ============================================================================
# Analytics Logger Tests
# ============================================================================

class TestAnalyticsLogger:
    """Tests for analytics logging"""

    def test_log_trade_no_db(self):
        """Test logging when no DB available"""
        logger = AnalyticsLogger(analytics_db=None)

        # Should not raise exception
        logger.log_trade(
            position={'symbol': 'BTCUSDT', 'entry': 50000.0},
            exit_price=50500.0,
            reason='TP_HIT',
            pnl_data={'pnl_pct': 1.0, 'net_pnl': 10.0, 'fees': 0.8}
        )

    def test_log_trade_with_mock_db(self):
        """Test logging with mock DB"""
        class MockDB:
            def __init__(self):
                self.trades = []

            def insert_trade(self, trade_data):
                self.trades.append(trade_data)
                return len(self.trades)  # Return row ID like real DB

        mock_db = MockDB()
        logger = AnalyticsLogger(analytics_db=mock_db)

        logger.log_trade(
            position={
                'symbol': 'BTCUSDT',
                'entry': 50000.0,
                'direction': 'LONG',
                'size': 1000.0
            },
            exit_price=50500.0,
            reason='TP_HIT',
            pnl_data={'pnl_pct': 1.0, 'net_pnl': 10.0, 'fees': 0.8},
            mode='PAPER'
        )

        assert len(mock_db.trades) == 1
        assert mock_db.trades[0]['symbol'] == 'BTCUSDT'
        assert mock_db.trades[0]['trading_mode'] == 'PAPER'

    def test_log_setup_rejected(self):
        """Test logging rejected setups"""
        class MockDB:
            def __init__(self):
                self.rejected = []

            def log_setup_rejected(self, symbol, reasons, details):
                self.rejected.append({'symbol': symbol, 'reasons': reasons})

        mock_db = MockDB()
        logger = AnalyticsLogger(analytics_db=mock_db)

        logger.log_setup_rejected(
            symbol='BTCUSDT',
            reasons=['LOW_VOLUME', 'WEAK_SIGNAL'],
            details={'volume': 0.5}
        )

        assert len(mock_db.rejected) == 1
        assert mock_db.rejected[0]['symbol'] == 'BTCUSDT'

    def test_log_setup_validated(self):
        """Test logging validated setups"""
        class MockDB:
            def __init__(self):
                self.validated = []

            def log_setup_validated(self, symbol, direction, score, conditions):
                self.validated.append({
                    'symbol': symbol,
                    'direction': direction,
                    'score': score
                })

        mock_db = MockDB()
        logger = AnalyticsLogger(analytics_db=mock_db)

        logger.log_setup_validated(
            symbol='BTCUSDT',
            direction='LONG',
            score=8.5,
            conditions=['EMAs', 'RSI', 'MACD']
        )

        assert len(mock_db.validated) == 1
        assert mock_db.validated[0]['score'] == 8.5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
