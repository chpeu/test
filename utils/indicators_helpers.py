"""
Indicator extraction helpers to avoid code duplication.
"""
from typing import Dict, Any, Optional, List


# Standard indicator field names for 1m timeframe
INDICATOR_FIELDS_1M = [
    'rsi', 'rsi_prev', 'macd', 'macd_signal', 'macd_hist', 'macd_hist_prev',
    'adx', 'di_plus', 'di_minus', 'di_gap',
    'ema9', 'ema21', 'ema_diff_pct',
    'atr', 'atr_pct',
    'bb_upper', 'bb_middle', 'bb_lower', 'bb_width',
    'bb_distance_to_lower', 'bb_distance_to_upper',
    'volume', 'volume_avg', 'volume_ratio', 'volume_spike'
]

# Standard indicator field names for 5m timeframe (with _5m suffix)
INDICATOR_FIELDS_5M_SUFFIXES = [
    ('rsi', 'rsi_5m'),
    ('rsi_prev', 'rsi_prev_5m'),
    ('macd', 'macd_5m'),
    ('macd_signal', 'macd_signal_5m'),
    ('macd_hist', 'macd_hist_5m'),
    ('macd_hist_prev', 'macd_hist_prev_5m'),
    ('adx', 'adx_5m'),
    ('di_plus', 'di_plus_5m'),
    ('di_minus', 'di_minus_5m'),
    ('di_gap', 'di_gap_5m'),
    ('ema9', 'ema9_5m'),
    ('ema21', 'ema21_5m'),
    ('ema_diff_pct', 'ema_diff_pct_5m'),
    ('atr', ['atr5m', 'atr_5m']),  # Multiple possible keys
    ('atr_pct', 'atr_pct_5m'),
    ('bb_upper', 'bb_upper_5m'),
    ('bb_middle', 'bb_middle_5m'),
    ('bb_lower', 'bb_lower_5m'),
    ('bb_width', 'bb_width_5m'),
    ('bb_distance_to_lower', 'bb_distance_to_lower_5m'),
    ('bb_distance_to_upper', 'bb_distance_to_upper_5m'),
    ('volume', 'volume_5m'),
    ('volume_avg', 'volume_avg_5m'),
    ('volume_ratio', 'volume_ratio_5m'),
    ('volume_spike', 'volume_spike_5m'),
]


def extract_indicators_1m(source: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract 1m timeframe indicators from a source dictionary.

    Args:
        source: Dictionary containing indicator data (can be analysis, analysis_1m, etc.)

    Returns:
        Dictionary with standardized indicator field names
    """
    indicators = {}

    for field in INDICATOR_FIELDS_1M:
        value = source.get(field)

        # Special handling for volume_ratio with fallback to volumeSpike
        if field == 'volume_ratio' and value is None:
            value = source.get('volumeSpike')

        indicators[field] = value

    return indicators


def extract_indicators_5m(source: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract 5m timeframe indicators from a source dictionary.

    Args:
        source: Dictionary containing indicator data with _5m suffixes

    Returns:
        Dictionary with standardized indicator field names (without _5m suffix)
    """
    indicators = {}

    for target_field, source_field in INDICATOR_FIELDS_5M_SUFFIXES:
        value = None

        # Handle multiple possible source keys
        if isinstance(source_field, list):
            for key in source_field:
                value = source.get(key)
                if value is not None:
                    break
        else:
            value = source.get(source_field)

        indicators[target_field] = value

    return indicators


def build_indicators_from_analysis(
    analysis: Dict[str, Any],
    timeframe: str = '1m',
    logger: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Build indicators dict from analysis data, trying multiple sources.

    This function handles both cases:
    1. When analysis contains analysis_1m/analysis_5m (no setup found)
    2. When analysis contains indicators directly (setup found)

    Args:
        analysis: Analysis dictionary from analyzer.analyze_pair()
        timeframe: Either '1m' or '5m'
        logger: Optional logger for debug messages

    Returns:
        Dictionary with extracted indicators
    """
    if not isinstance(analysis, dict):
        return {}

    # Priority 1: Check if indicators are already present
    indicators_key = f'indicators_{timeframe}'
    if indicators_key in analysis:
        existing = analysis.get(indicators_key, {})
        if isinstance(existing, dict) and existing:
            if logger:
                logger.debug(f"Using existing {indicators_key} from analysis")
            return existing

    # Priority 2: Try to extract from analysis_1m/analysis_5m
    analysis_key = f'analysis_{timeframe}'
    nested_analysis = analysis.get(analysis_key, {})

    if isinstance(nested_analysis, dict) and nested_analysis:
        if logger:
            logger.debug(f"Extracting {indicators_key} from {analysis_key}")

        if timeframe == '1m':
            return extract_indicators_1m(nested_analysis)
        elif timeframe == '5m':
            return extract_indicators_5m(nested_analysis)

    # Priority 3: Extract directly from analysis (for valid setups)
    if logger:
        logger.debug(f"Extracting {indicators_key} directly from analysis")

    if timeframe == '1m':
        return extract_indicators_1m(analysis)
    elif timeframe == '5m':
        return extract_indicators_5m(analysis)

    return {}


def count_non_null_values(indicators: Dict[str, Any]) -> int:
    """
    Count number of non-null values in indicators dictionary.

    Args:
        indicators: Dictionary of indicator values

    Returns:
        Count of non-null values
    """
    return len([v for v in indicators.values() if v is not None])
