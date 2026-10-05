"""
Utilities for Trade Cursor

🔥 SPRINT 1.5: Code Duplication - Helpers & Decorators ajoutés
"""
from .logger import setup_logger
from .indicators_helpers import (
    extract_indicators_1m,
    extract_indicators_5m,
    build_indicators_from_analysis,
    count_non_null_values,
    INDICATOR_FIELDS_1M,
    INDICATOR_FIELDS_5M_SUFFIXES
)

# 🔥 Sprint 1.5: Helpers
from .helpers import (
    ConfigHelper,
    DataLoggerHelper,
    APIHelper,
    MarketHelper,
    StatsHelper,
    PositionHelper,
)

# 🔥 Sprint 1.5: Decorators
from .decorators import (
    async_safe,
    log_errors,
    suppress_errors,
)

__all__ = [
    # Existing
    'setup_logger',
    'extract_indicators_1m',
    'extract_indicators_5m',
    'build_indicators_from_analysis',
    'count_non_null_values',
    'INDICATOR_FIELDS_1M',
    'INDICATOR_FIELDS_5M_SUFFIXES',
    # Sprint 1.5: Helpers
    'ConfigHelper',
    'DataLoggerHelper',
    'APIHelper',
    'MarketHelper',
    'StatsHelper',
    'PositionHelper',
    # Sprint 1.5: Decorators
    'async_safe',
    'log_errors',
    'suppress_errors',
]

