#!/usr/bin/env python3
"""
Position Management Package - Trade Cursor v7.0
Modules de gestion des positions (TP/SL, Trailing, Invalidation, etc.)
"""

from .tp_sl_calculator import (
    TPSLConfig,
    calculate_fixed_levels,
    calculate_atr_levels,
    validate_levels
)

from .partial_tp_manager import PartialTPManager
from .tp_escalier_manager import TPEscalierManager
from .trailing_stop import TrailingStopManager, TrailingStopConfig
from .early_invalidation import EarlyInvalidationChecker, EarlyInvalidationConfig
from .recovery_mode import RecoveryModeManager, RecoveryModeConfig
from .pnl_calculator import PnLCalculator
from .analytics_logger import AnalyticsLogger

__all__ = [
    # TP/SL Calculator
    'TPSLConfig',
    'calculate_fixed_levels',
    'calculate_atr_levels',
    'validate_levels',

    # Managers
    'PartialTPManager',
    'TPEscalierManager',
    'TrailingStopManager',
    'EarlyInvalidationChecker',
    'RecoveryModeManager',
    'PnLCalculator',
    'AnalyticsLogger',

    # Configs
    'TrailingStopConfig',
    'EarlyInvalidationConfig',
    'RecoveryModeConfig',
]
