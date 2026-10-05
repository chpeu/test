import os
import sys

import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.position_manager import PositionConfig, PositionManager
from config import TRADING_CONFIG


def test_position_sizing_recovery_refactor_enabled():
    with patch.dict('config.TRADING_CONFIG', {
        'risk_per_trade': 2.0,
        'min_risk_per_trade': 1.0,
        'max_risk_per_trade': 3.0,
        'recovery_refactor_enabled': True,
        'recovery_shadow_compare': False,
        'adaptive_sizing_enabled': False,
        'recovery_mode': {
            'enabled': True,
            'mode': 'PROGRESSIVE',
            'levels': [
                {'trigger_loss_streak': 2, 'min_score_boost': 0.5, 'position_size_reduction': 0.85, 'duration_trades': 3},
                {'trigger_loss_streak': 3, 'min_score_boost': 1.5, 'position_size_reduction': 0.7, 'duration_trades': 5}
            ]
        }
    }, clear=False):
        config = PositionConfig(loss_streak=3, win_streak=0)
        pm = PositionManager(config)
        size = pm.calculate_position_size({'symbol': 'BTC/USDT', 'score': 10.0}, capital=1000.0)

    # base size = 2% of 1000 = 20, recovery level 2 -> 0.7 multiplier
    assert size == pytest.approx(14.0, rel=1e-3)


def test_position_sizing_recovery_refactor_disabled():
    with patch.dict('config.TRADING_CONFIG', {
        'risk_per_trade': 2.0,
        'min_risk_per_trade': 1.0,
        'max_risk_per_trade': 3.0,
        'recovery_refactor_enabled': False,
        'recovery_shadow_compare': False,
        'adaptive_sizing_enabled': False,
        'recovery_mode': {
            'enabled': True,
            'mode': 'PROGRESSIVE',
            'levels': [
                {'trigger_loss_streak': 2, 'min_score_boost': 0.5, 'position_size_reduction': 0.85, 'duration_trades': 3},
                {'trigger_loss_streak': 3, 'min_score_boost': 1.5, 'position_size_reduction': 0.7, 'duration_trades': 5}
            ]
        }
    }, clear=False):
        config = PositionConfig(loss_streak=3, win_streak=0)
        pm = PositionManager(config)
        size = pm.calculate_position_size({'symbol': 'BTC/USDT', 'score': 10.0}, capital=1000.0)

    assert size == pytest.approx(14.0, rel=1e-3)
