import os
import sys
import time

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.position.early_invalidation import EarlyInvalidationChecker, EarlyInvalidationConfig
from core.position.pnl_calculator import PnLCalculator
from core.position.recovery_mode import RecoveryModeManager, RecoveryModeConfig
from core.position.tp_escalier_manager import TPEscalierManager
from core.position.trailing_stop import TrailingStopManager, TrailingStopConfig


def test_early_should_invalidate_disabled_returns_false():
    checker = EarlyInvalidationChecker(EarlyInvalidationConfig(enabled=False))
    position_data = {'entry_price': 100.0, 'side': 'LONG', 'entry_time': 0.0}
    assert checker.should_invalidate(position_data, current_price=99.0, current_time=20.0) is False


def test_early_should_invalidate_invalid_entry_returns_false():
    checker = EarlyInvalidationChecker()
    position_data = {'entry_price': 0.0, 'side': 'LONG', 'entry_time': 0.0}
    assert checker.should_invalidate(position_data, current_price=99.0, current_time=20.0) is False


def test_early_should_invalidate_short_legacy_mode_uses_short_pnl():
    checker = EarlyInvalidationChecker(EarlyInvalidationConfig(max_adverse_move_pct=0.5))
    position_data = {'entry_price': 100.0, 'side': 'SHORT', 'entry_time': 0.0}
    assert checker.should_invalidate(position_data, current_price=101.0, current_time=20.0) is True


def test_early_should_invalidate_normal_mode_time_threshold_15s():
    checker = EarlyInvalidationChecker(EarlyInvalidationConfig(threshold_15s=-0.12, threshold_30s=-0.08))
    position_data = {'entry_price': 100.0, 'side': 'LONG', 'entry_time': 0.0}
    assert checker.should_invalidate(position_data, current_price=99.8, current_time=10.0) is True


def test_early_should_invalidate_normal_mode_time_threshold_30s():
    checker = EarlyInvalidationChecker(EarlyInvalidationConfig(threshold_15s=-0.12, threshold_30s=-0.08))
    position_data = {'entry_price': 100.0, 'side': 'LONG', 'entry_time': 0.0}
    assert checker.should_invalidate(position_data, current_price=99.9, current_time=20.0) is True


def test_early_should_invalidate_normal_mode_after_30s_returns_false():
    checker = EarlyInvalidationChecker(EarlyInvalidationConfig(threshold_15s=-0.12, threshold_30s=-0.08))
    position_data = {'entry_price': 100.0, 'side': 'LONG', 'entry_time': 0.0}
    assert checker.should_invalidate(position_data, current_price=50.0, current_time=35.0) is False


def test_get_adaptive_threshold_elapsed_over_15_uses_threshold_30s():
    checker = EarlyInvalidationChecker(EarlyInvalidationConfig(threshold_15s=-0.12, threshold_30s=-0.08))
    threshold = checker.get_adaptive_threshold(elapsed=20.0, atr_percent=0.5)
    assert threshold == pytest.approx(-0.08, abs=1e-6)


def test_get_adaptive_threshold_adaptive_disabled_returns_base_threshold():
    checker = EarlyInvalidationChecker(EarlyInvalidationConfig(adaptive_enabled=False, threshold_30s=-0.08))
    threshold = checker.get_adaptive_threshold(elapsed=20.0, atr_percent=1.0)
    assert threshold == pytest.approx(-0.08, abs=1e-6)


def test_check_contextual_exit_no_market_data_returns_false_none():
    checker = EarlyInvalidationChecker()
    should_exit, reason = checker.check_contextual_exit(position={'direction': 'LONG'}, market_data=None)
    assert should_exit is False
    assert reason is None


def test_check_contextual_exit_long_combines_reasons():
    checker = EarlyInvalidationChecker()
    position = {'direction': 'LONG'}
    market_data = {
        'rsi_1m': 80.0,
        'volume_1m': 200.0,
        'volume_avg_1m': 50.0,
        'price_change_pct': -0.1,
        'spread_pct': 0.1,
    }
    should_exit, reason = checker.check_contextual_exit(position=position, market_data=market_data)
    assert should_exit is True
    assert isinstance(reason, str)
    assert reason.startswith('CONTEXTUAL_EXIT:')
    assert 'RSI overbought' in reason
    assert 'Volume spike' in reason
    assert 'Spread' in reason


def test_check_contextual_exit_short_hits_short_specific_conditions():
    checker = EarlyInvalidationChecker()
    position = {'direction': 'SHORT'}
    market_data = {
        'rsi': 20.0,
        'volume': 300.0,
        'volume_avg': 100.0,
        'price_change_pct': 0.1,
        'spread': 0.1,
    }
    should_exit, reason = checker.check_contextual_exit(position=position, market_data=market_data)
    assert should_exit is True
    assert isinstance(reason, str)
    assert 'RSI oversold' in reason


def test_check_contextual_exit_market_data_but_no_reason_returns_false_none():
    checker = EarlyInvalidationChecker()
    position = {'direction': 'LONG'}
    market_data = {
        'rsi': 50.0,
        'volume': 100.0,
        'volume_avg': 100.0,
        'price_change_pct': 0.0,
        'spread': 0.01,
    }
    should_exit, reason = checker.check_contextual_exit(position=position, market_data=market_data)
    assert should_exit is False
    assert reason is None


def test_check_invalidation_disabled_returns_none():
    checker = EarlyInvalidationChecker(EarlyInvalidationConfig(enabled=False))
    position = {
        'start_time': time.time() - 12.0,
        'entry': 100.0,
        'atr': 1.0,
        'direction': 'LONG',
        'symbol': 'BTC/USDT',
    }
    assert checker.check_invalidation(position, current_price=99.0, pnl_percent=-0.5) is None


def test_check_invalidation_uses_atr_pct_used_path():
    checker = EarlyInvalidationChecker()
    position = {
        'start_time': time.time() - 12.0,
        'entry': 100.0,
        'atr_pct_used': 1.0,
        'direction': 'LONG',
        'symbol': 'BTC/USDT',
    }
    assert checker.check_invalidation(position, current_price=99.0, pnl_percent=-0.2) == 'EARLY_INVALIDATION'


def test_check_invalidation_fallback_atr_percent_default_when_missing_data():
    checker = EarlyInvalidationChecker()
    position = {
        'start_time': time.time() - 12.0,
        'entry': 0.0,
        'atr': 0.0,
        'direction': 'LONG',
        'symbol': 'BTC/USDT',
    }
    assert checker.check_invalidation(position, current_price=100.0, pnl_percent=0.0) is None


def test_check_invalidation_returns_contextual_exit_reason():
    checker = EarlyInvalidationChecker()
    position = {
        'start_time': time.time() - 5.0,
        'entry': 100.0,
        'atr': 1.0,
        'direction': 'LONG',
        'symbol': 'BTC/USDT',
    }
    market_data = {
        'rsi': 80.0,
        'volume': 200.0,
        'volume_avg': 50.0,
        'price_change_pct': -0.1,
        'spread': 0.1,
    }
    reason = checker.check_invalidation(position, current_price=99.0, pnl_percent=-0.01, market_data=market_data)
    assert isinstance(reason, str)
    assert reason.startswith('CONTEXTUAL_EXIT:')


def test_pnl_calculator_calculate_pnl_usdt_invalid_returns_zero():
    assert PnLCalculator.calculate_pnl_usdt({'entry': 0.0, 'size': 100.0}, current_price=1.0) == 0.0
    assert PnLCalculator.calculate_pnl_usdt({'entry': 100.0, 'size': 0.0}, current_price=1.0) == 0.0


def test_pnl_calculator_calculate_pnl_usdt_short_branch():
    pnl = PnLCalculator.calculate_pnl_usdt(
        position={'entry': 100.0, 'size': 1000.0, 'direction': 'SHORT'},
        current_price=90.0,
    )
    assert pnl > 0


def test_pnl_calculator_realized_pnl_partial_tp_fallback_size_remaining_none():
    result = PnLCalculator.calculate_realized_pnl(
        position={
            'symbol': 'BTC/USDT',
            'entry': 100.0,
            'direction': 'LONG',
            'size': 1000.0,
            'partial_tp_sold': True,
            'partial_profit_usdt': 20.0,
        },
        exit_price=110.0,
        fees_percent=0.0,
    )

    assert result['pnl_usdt_gross'] == pytest.approx(70.0, abs=1e-6)
    assert result['pnl_pct'] == pytest.approx(7.0, abs=1e-6)


def test_pnl_calculator_realized_pnl_size_zero_returns_zero_percent():
    result = PnLCalculator.calculate_realized_pnl(
        position={'symbol': 'BTC/USDT', 'entry': 100.0, 'direction': 'LONG', 'size': 0.0},
        exit_price=110.0,
    )
    assert result['pnl_pct'] == 0.0
    assert result['net_pnl_pct'] == 0.0


def test_pnl_calculator_format_pnl_display_covers_lines():
    text = PnLCalculator.format_pnl_display(pnl_pct=-0.5, pnl_usdt=-10.0)
    assert '🔴' in text


def test_recovery_mode_get_recovery_level_simple_below_trigger_returns_none():
    config = RecoveryModeConfig(mode='SIMPLE', trigger_loss_streak=3)
    manager = RecoveryModeManager(config)
    assert manager.get_recovery_level(loss_streak=2) is None


def test_recovery_mode_activate_returns_none_when_already_active():
    manager = RecoveryModeManager()
    assert manager.activate(loss_streak=3) is not None
    assert manager.activate(loss_streak=3) is None


def test_recovery_mode_update_after_trade_when_not_active_noop():
    manager = RecoveryModeManager()
    manager.update_after_trade(is_win=True)
    assert manager.active is False


def test_recovery_mode_get_min_score_boost_covers_branches():
    manager = RecoveryModeManager()
    assert manager.get_min_score_boost(loss_streak=0) == 0.0
    assert manager.get_min_score_boost(loss_streak=3) > 0.0


def test_tp_escalier_check_and_execute_returns_none_when_not_enabled():
    position = {'entry': 100.0, 'direction': 'LONG', 'size': 1000.0}
    assert TPEscalierManager.check_and_execute_levels(position, current_price=200.0) is None


def test_tp_escalier_check_and_execute_returns_none_when_all_levels_done():
    position = {
        'tp_escalier_enabled': True,
        'tp_escalier_levels': [{'pnl': 1.0, 'size_pct': 0.5}],
        'tp_escalier_current_level': 1,
        'entry': 100.0,
        'direction': 'LONG',
        'size': 1000.0,
    }
    assert TPEscalierManager.check_and_execute_levels(position, current_price=200.0) is None


def test_tp_escalier_check_and_execute_short_branch_hits_tp_and_moves_sl():
    position = {
        'tp_escalier_enabled': True,
        'tp_escalier_levels': [{'pnl': 1.0, 'size_pct': 0.5, 'move_sl': 'breakeven'}],
        'tp_escalier_current_level': 0,
        'tp_escalier_size_remaining': 1.0,
        'tp_escalier_profits': [],
        'entry': 100.0,
        'direction': 'SHORT',
        'size': 1000.0,
        'partial_profit_usdt': 0.0,
        'sl': 110.0,
    }

    record = TPEscalierManager.check_and_execute_levels(position, current_price=98.0)

    assert record is not None
    assert record['profit_pct'] == pytest.approx(1.0, abs=1e-6)
    assert position['sl'] == pytest.approx(100.0, abs=1e-9)


def test_tp_escalier_check_and_execute_returns_none_when_tp_not_hit():
    position = {
        'tp_escalier_enabled': True,
        'tp_escalier_levels': [{'pnl': 1.0, 'size_pct': 0.5}],
        'tp_escalier_current_level': 0,
        'tp_escalier_size_remaining': 1.0,
        'tp_escalier_profits': [],
        'entry': 100.0,
        'direction': 'LONG',
        'size': 1000.0,
    }
    assert TPEscalierManager.check_and_execute_levels(position, current_price=100.5) is None


def test_trailing_stop_calculate_trailing_stop_entry_price_invalid_returns_none():
    manager = TrailingStopManager()
    assert manager.calculate_trailing_stop({'entry_price': 0.0, 'side': 'LONG'}, current_price=100.0) is None


def test_trailing_stop_calculate_trailing_stop_short_not_triggered_returns_none():
    manager = TrailingStopManager(TrailingStopConfig(trigger_pnl=0.25))
    position_data = {'entry_price': 100.0, 'side': 'SHORT'}
    assert manager.calculate_trailing_stop(position_data, current_price=99.9) is None


def test_trailing_stop_calculate_trailing_stop_short_triggered_returns_sl():
    manager = TrailingStopManager(TrailingStopConfig(trigger_pnl=0.25, min_distance=0.08))
    position_data = {'entry_price': 100.0, 'side': 'SHORT'}
    sl = manager.calculate_trailing_stop(position_data, current_price=99.0)
    assert sl is not None
    assert sl > 99.0


def test_trailing_stop_update_trailing_stop_disabled_returns_none():
    manager = TrailingStopManager(TrailingStopConfig(enabled=False))
    position = {'entry': 100.0, 'atr': 1.0, 'sl': 90.0, 'direction': 'LONG'}
    assert manager.update_trailing_stop(position, current_price=110.0, pnl_percent=1.0) is None


def test_trailing_stop_update_trailing_stop_uses_atr_pct_used_and_custom_distance():
    manager = TrailingStopManager()
    position = {
        'symbol': 'BTC/USDT',
        'entry': 100.0,
        'atr': 1.0,
        'atr_pct_used': 1.0,
        'sl': 100.0,
        'direction': 'LONG',
    }
    new_sl = manager.update_trailing_stop(position, current_price=110.0, pnl_percent=1.0, custom_distance_pct=0.1)
    assert new_sl is not None
    assert new_sl > 100.0


def test_trailing_stop_update_trailing_stop_fallback_atr_percent_when_missing_data():
    manager = TrailingStopManager(TrailingStopConfig(trigger_pnl=0.25, atr_multiplier=0.4, min_distance=0.08))
    position = {
        'symbol': 'BTC/USDT',
        'entry': 0.0,
        'atr': 0.0,
        'sl': 100.0,
        'direction': 'LONG',
    }
    new_sl = manager.update_trailing_stop(position, current_price=110.0, pnl_percent=1.0)
    assert new_sl is not None


def test_trailing_stop_update_trailing_stop_no_update_returns_none():
    manager = TrailingStopManager(TrailingStopConfig(trigger_pnl=0.25, min_distance=0.08))
    position = {
        'symbol': 'BTC/USDT',
        'entry': 100.0,
        'atr_pct_used': 1.0,
        'sl': 200.0,
        'direction': 'LONG',
    }
    assert manager.update_trailing_stop(position, current_price=110.0, pnl_percent=1.0, custom_distance_pct=0.1) is None
