"""
🔥 SPRINT 1.5: Code Duplication - Helpers Module

Helpers pour éliminer la duplication de code identifiée dans l'analyse.

Patterns adressés:
- Pattern 2: TRADING_CONFIG.get() (312+ occurrences)
- Pattern 6: Data Logger Integration (300-400 lignes)
- Pattern 4: Price Validation (8+ occurrences)
- Pattern 9: Scalability Data Extraction (6+ occurrences)
- Pattern 12: API Call Protection (6+ occurrences)
- Pattern 13: Stats Calculation (4+ occurrences)
- Pattern 14: Market Validation (4+ occurrences)
"""

from .config_helper import ConfigHelper
from .data_logger_helper import DataLoggerHelper
from .api_helper import APIHelper
from .market_helper import MarketHelper
from .stats_helper import StatsHelper
from .position_helper import PositionHelper, PositionProxy

__all__ = [
    'ConfigHelper',
    'DataLoggerHelper',
    'APIHelper',
    'MarketHelper',
    'StatsHelper',
    'PositionHelper',
    'PositionProxy',
]
