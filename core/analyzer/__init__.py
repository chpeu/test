"""
Package analyzer - Modules de refactorisation de l'analyseur technique
"""

# Import TechnicalAnalyzer depuis le fichier analyzer.py (parent)
import importlib.util
import os

# Charger TechnicalAnalyzer depuis analyzer.py (fichier, pas package)
_analyzer_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'analyzer.py')
if os.path.exists(_analyzer_file):
    _spec = importlib.util.spec_from_file_location("core.analyzer_file", _analyzer_file)
    _analyzer_module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_analyzer_module)
    TechnicalAnalyzer = _analyzer_module.TechnicalAnalyzer
else:
    TechnicalAnalyzer = None

from .filters import (
    check_volume_filter,
    check_snr_filter,
    check_breakout_filter,
    check_wick_filter,
    check_atr_filter
)

from .signal_generator import (
    generate_long_conditions,
    generate_short_conditions,
    check_ema_condition,
    check_rsi_condition,
    check_macd_condition,
    check_bollinger_condition,
    check_adx_di_condition,
    check_pattern_condition
)

from .scoring import (
    calculate_weighted_score,
    get_min_score_required,
    apply_trend_bonus,
    apply_divergence_bonus
)

from .market_data import (
    check_spread,
    check_orderbook_imbalance
)

from .risk_detector import (
    detect_manipulation,
    check_price_action_coherence
)

from .correlation import (
    check_static_correlation,
    check_dynamic_correlation
)

from .trend_calculator import (
    calculate_trend_data
)

__all__ = [
    # Main Class
    'TechnicalAnalyzer',
    # Filters
    'check_volume_filter',
    'check_snr_filter',
    'check_breakout_filter',
    'check_wick_filter',
    'check_atr_filter',
    # Signal Generator
    'generate_long_conditions',
    'generate_short_conditions',
    'check_ema_condition',
    'check_rsi_condition',
    'check_macd_condition',
    'check_bollinger_condition',
    'check_adx_di_condition',
    'check_pattern_condition',
    # Scoring
    'calculate_weighted_score',
    'get_min_score_required',
    'apply_trend_bonus',
    'apply_divergence_bonus',
    # Market Data
    'check_spread',
    'check_orderbook_imbalance',
    # Risk Detector
    'detect_manipulation',
    'check_price_action_coherence',
    # Correlation
    'check_static_correlation',
    'check_dynamic_correlation',
    # Trend Calculator
    'calculate_trend_data'
]
