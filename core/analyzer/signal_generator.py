"""
Générateur de signaux LONG/SHORT
Analyse les conditions techniques pour générer des signaux de trading
"""

from typing import List, Tuple, Dict
from config import TRADING_CONFIG


def check_ema_condition(ema9: float, ema21: float, direction: str) -> Tuple[bool, str, float]:
    """
    Vérifie condition EMA

    Args:
        ema9: EMA 9
        ema21: EMA 21
        direction: 'LONG' ou 'SHORT'

    Returns:
        (condition_met, description, diff_percent)
    """
    if direction == 'LONG':
        ema_diff_percent = ((ema9 - ema21) / ema21) * 100
        if ema9 > ema21 and ema_diff_percent > 0.05:
            return True, f"EMAs Up ({ema_diff_percent:.3f}%)", ema_diff_percent
    else:  # SHORT
        ema_diff_percent = ((ema21 - ema9) / ema21) * 100
        if ema9 < ema21 and ema_diff_percent > 0.05:
            return True, f"EMAs Down ({ema_diff_percent:.3f}%)", ema_diff_percent

    return False, "", 0.0


def check_rsi_condition(
    rsi: float,
    rsi_prev: float,
    adx: Dict,
    macd: Dict,
    direction: str
) -> Tuple[bool, str]:
    """
    Vérifie condition RSI (rebound/pullback pour LONG, overbought/rejection pour SHORT)

    Args:
        rsi: RSI actuel
        rsi_prev: RSI précédent
        adx: Dict ADX avec 'adx', 'diPlus', 'diMinus'
        macd: Dict MACD avec 'histogram'
        direction: 'LONG' ou 'SHORT'

    Returns:
        (condition_met, description)
    """
    if direction == 'LONG':
        # RSI Rebound (oversold recovery)
        rsi_rebound = rsi >= 30 and rsi <= 40 and adx['adx'] < 20 and rsi > rsi_prev
        # RSI Pullback (healthy correction in uptrend)
        rsi_pullback = rsi >= 45 and rsi <= 55 and macd['histogram'] > 0 and adx['adx'] > 25 and rsi > rsi_prev

        if rsi_rebound:
            return True, f"RSI Rebound↑ (ADX<{adx['adx']:.1f})"
        elif rsi_pullback:
            return True, f"RSI Pullback↑ (ADX>{adx['adx']:.1f})"

    else:  # SHORT
        # RSI Overbought
        rsi_overbought = rsi >= 60 and rsi <= 70 and adx['adx'] < 20 and rsi < rsi_prev
        # RSI Rejection (rejection from resistance)
        rsi_rejection = rsi >= 45 and rsi <= 55 and macd['histogram'] < 0 and adx['adx'] > 25 and rsi < rsi_prev

        if rsi_overbought:
            return True, f"RSI Overbought↓ (ADX<{adx['adx']:.1f})"
        elif rsi_rejection:
            return True, f"RSI Rejection↓ (ADX>{adx['adx']:.1f})"

    return False, ""


def check_macd_condition(
    macd: Dict,
    macd_prev: Dict,
    direction: str
) -> Tuple[bool, str]:
    """
    Vérifie condition MACD (bullish/bearish + momentum)

    Args:
        macd: Dict MACD actuel avec 'macd', 'signal', 'histogram'
        macd_prev: Dict MACD précédent
        direction: 'LONG' ou 'SHORT'

    Returns:
        (condition_met, description)
    """
    if direction == 'LONG':
        macd_bullish = macd['macd'] > macd['signal'] or macd['histogram'] > 0
        macd_momentum = macd['histogram'] > macd_prev['histogram']

        if macd_bullish and macd_momentum:
            return True, "MACD+↑ (momentum)"
        elif macd_bullish:
            return True, "MACD+"

    else:  # SHORT
        macd_bearish = macd['macd'] < macd['signal'] or macd['histogram'] < 0
        macd_momentum_down = macd['histogram'] < macd_prev['histogram']

        if macd_bearish and macd_momentum_down:
            return True, "MACD-↓ (momentum)"
        elif macd_bearish:
            return True, "MACD-"

    return False, ""


def check_bollinger_condition(
    price: float,
    bb: Dict,
    atr_percent: float,
    direction: str
) -> Tuple[bool, str]:
    """
    Vérifie condition Bollinger Bands

    Args:
        price: Prix actuel
        bb: Dict Bollinger avec 'upper', 'lower', 'middle'
        atr_percent: ATR en pourcentage
        direction: 'LONG' ou 'SHORT'

    Returns:
        (condition_met, description)
    """
    bb_threshold = max(0.3, atr_percent * 0.5)

    if direction == 'LONG':
        dist_to_lower = ((price - bb['lower']) / bb['lower']) * 100 if bb['lower'] > 0 else 999
        if dist_to_lower < bb_threshold:
            return True, "BB Lower"

    else:  # SHORT
        dist_to_upper = ((bb['upper'] - price) / price) * 100 if bb['upper'] > 0 else 999
        if dist_to_upper < bb_threshold:
            return True, "BB Upper"

    return False, ""


def check_adx_di_condition(adx: Dict, direction: str) -> Tuple[bool, str]:
    """
    Vérifie condition ADX + DI Gap

    Args:
        adx: Dict ADX avec 'adx', 'diPlus', 'diMinus'
        direction: 'LONG' ou 'SHORT'

    Returns:
        (condition_met, description)
    """
    di_gap_min = TRADING_CONFIG.get('di_gap_min', 5)
    di_gap_adx_threshold = TRADING_CONFIG.get('di_gap_adx_threshold', 25)

    if direction == 'LONG':
        di_gap = adx['diPlus'] - adx['diMinus']

        if adx['adx'] > di_gap_adx_threshold and adx['diPlus'] > adx['diMinus'] and abs(di_gap) > di_gap_min:
            return True, "ADX+ + DI Gap>" + str(abs(di_gap))
        elif adx['adx'] > 30 and adx['diPlus'] > adx['diMinus']:
            return True, "ADX+ (>30)"

    else:  # SHORT
        di_gap_short = adx['diMinus'] - adx['diPlus']

        if adx['adx'] > di_gap_adx_threshold and adx['diMinus'] > adx['diPlus'] and abs(di_gap_short) > di_gap_min:
            return True, "ADX- + DI Gap>" + str(abs(di_gap_short))
        elif adx['adx'] > 30 and adx['diMinus'] > adx['diPlus']:
            return True, "ADX- (>30)"

    return False, ""


def check_pattern_condition(pattern: str, direction: str) -> Tuple[bool, str]:
    """
    Vérifie condition Pattern candlestick

    Args:
        pattern: Pattern détecté
        direction: 'LONG' ou 'SHORT'

    Returns:
        (condition_met, description)
    """
    if direction == 'LONG':
        long_patterns = [
            'ENGULFING_BULLISH', 'HAMMER',
            'DOJI_DRAGONFLY', 'MARUBOZU_BULLISH',
            'MORNING_STAR', 'DOJI'
        ]
        if pattern in long_patterns:
            return True, f"Pattern: {pattern}"

    else:  # SHORT
        short_patterns = [
            'ENGULFING_BEARISH', 'SHOOTING_STAR',
            'DOJI_GRAVESTONE', 'MARUBOZU_BEARISH',
            'EVENING_STAR'
        ]
        if pattern in short_patterns:
            return True, f"Pattern: {pattern}"

    return False, ""


def generate_long_conditions(
    ema9: float,
    ema21: float,
    rsi: float,
    rsi_prev: float,
    vol_spike: float,
    min_vol_ratio: float,
    macd: Dict,
    macd_prev: Dict,
    price: float,
    bb: Dict,
    atr_percent: float,
    adx: Dict,
    pattern: str
) -> Tuple[List[str], List[str]]:
    """
    Génère les conditions LONG

    Returns:
        (conditions_list, condition_types_list)
    """
    conditions = []
    condition_types = []

    # 1. EMAs
    ema_met, ema_desc, _ = check_ema_condition(ema9, ema21, 'LONG')
    if ema_met:
        conditions.append(ema_desc)
        condition_types.append('EMAs')

    # 2. RSI
    rsi_met, rsi_desc = check_rsi_condition(rsi, rsi_prev, adx, macd, 'LONG')
    if rsi_met:
        conditions.append(rsi_desc)
        condition_types.append('RSI')

    # 3. Volume
    if vol_spike > 1.5:
        conditions.append(f"Vol >>{vol_spike:.1f}x")
    else:
        conditions.append(f"Vol >{min_vol_ratio:.1f}x")
    condition_types.append('Volume')

    # 4. MACD
    macd_met, macd_desc = check_macd_condition(macd, macd_prev, 'LONG')
    if macd_met:
        conditions.append(macd_desc)
        condition_types.append('MACD')

    # 5. Bollinger
    bb_met, bb_desc = check_bollinger_condition(price, bb, atr_percent, 'LONG')
    if bb_met:
        conditions.append(bb_desc)
        condition_types.append('Bollinger')

    # 6. ADX + DI
    adx_met, adx_desc = check_adx_di_condition(adx, 'LONG')
    if adx_met:
        conditions.append(adx_desc)
        condition_types.append('ADX_DI')

    # 7. Pattern
    pattern_met, pattern_desc = check_pattern_condition(pattern, 'LONG')
    if pattern_met:
        conditions.append(pattern_desc)
        condition_types.append('Pattern')

    return conditions, condition_types


def generate_short_conditions(
    ema9: float,
    ema21: float,
    rsi: float,
    rsi_prev: float,
    vol_spike: float,
    min_vol_ratio: float,
    macd: Dict,
    macd_prev: Dict,
    price: float,
    bb: Dict,
    atr_percent: float,
    adx: Dict,
    pattern: str
) -> Tuple[List[str], List[str]]:
    """
    Génère les conditions SHORT

    Returns:
        (conditions_list, condition_types_list)
    """
    conditions = []
    condition_types = []

    # 1. EMAs
    ema_met, ema_desc, _ = check_ema_condition(ema9, ema21, 'SHORT')
    if ema_met:
        conditions.append(ema_desc)
        condition_types.append('EMAs')

    # 2. RSI
    rsi_met, rsi_desc = check_rsi_condition(rsi, rsi_prev, adx, macd, 'SHORT')
    if rsi_met:
        conditions.append(rsi_desc)
        condition_types.append('RSI')

    # 3. Volume
    if vol_spike > 1.5:
        conditions.append(f"Vol >>{vol_spike:.1f}x")
    else:
        conditions.append(f"Vol >{min_vol_ratio:.1f}x")
    condition_types.append('Volume')

    # 4. MACD
    macd_met, macd_desc = check_macd_condition(macd, macd_prev, 'SHORT')
    if macd_met:
        conditions.append(macd_desc)
        condition_types.append('MACD')

    # 5. Bollinger
    bb_met, bb_desc = check_bollinger_condition(price, bb, atr_percent, 'SHORT')
    if bb_met:
        conditions.append(bb_desc)
        condition_types.append('Bollinger')

    # 6. ADX + DI
    adx_met, adx_desc = check_adx_di_condition(adx, 'SHORT')
    if adx_met:
        conditions.append(adx_desc)
        condition_types.append('ADX_DI')

    # 7. Pattern
    pattern_met, pattern_desc = check_pattern_condition(pattern, 'SHORT')
    if pattern_met:
        conditions.append(pattern_desc)
        condition_types.append('Pattern')

    return conditions, condition_types
