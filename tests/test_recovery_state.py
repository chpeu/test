import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.position.recovery_mode import RecoveryModeManager, RecoveryModeConfig


def test_get_state_progressive_level():
    manager = RecoveryModeManager()

    state = manager.get_state(loss_streak=2, use_active_flag=False)

    assert state.active is True
    assert state.level == 1
    assert state.min_score_boost == 0.5
    assert state.position_size_mult == 0.85
    assert state.confluence_forced is False


def test_get_state_simple_mode():
    config = RecoveryModeConfig(
        mode='SIMPLE',
        trigger_loss_streak=3,
        min_score_boost=1.2,
        position_size_reduction=0.6,
        confluence_forced=True,
        duration_trades=4
    )
    manager = RecoveryModeManager(config)

    state = manager.get_state(loss_streak=3, use_active_flag=False)

    assert state.active is True
    assert state.level == 1
    assert state.min_score_boost == 1.2
    assert state.position_size_mult == 0.6
    assert state.confluence_forced is True


def test_get_state_disabled():
    config = RecoveryModeConfig(enabled=False)
    manager = RecoveryModeManager(config)

    state = manager.get_state(loss_streak=5, use_active_flag=False)

    assert state.active is False
    assert state.level is None
    assert state.position_size_mult == 1.0
    assert state.min_score_boost == 0.0


def test_get_state_remaining_trades_when_active():
    manager = RecoveryModeManager()
    manager.activate(loss_streak=3)

    state = manager.get_state(loss_streak=3)

    assert state.active is True
    assert state.remaining_trades == manager.remaining_trades
