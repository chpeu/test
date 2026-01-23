"""
Détection des risques de marché
Manipulation, pump & dump, incohérences de price action
"""

from typing import Dict, Optional, List
from utils.logger import get_logger


# Logger will be initialized lazily to avoid blocking during module import
logger = None


def _get_logger():
    """Get or initialize logger lazily to avoid blocking during import"""
    global logger
    if logger is None:
        logger = get_logger()
    return logger


def detect_manipulation(
    symbol: str,
    timeframe: str,
    ohlcv: Optional[List],
    volume: float,
    vol_spike: float
) -> Dict:
    """
    Détecter pump & dump / manipulation (version permissive)

    Args:
        symbol: Symbole de la paire
        timeframe: Timeframe
        ohlcv: Données OHLCV
        volume: Volume actuel
        vol_spike: Ratio volume spike

    Returns:
        Dict avec suspicious, reason, severity
    """
    # Si pas de données OHLCV, on ne peut pas détecter
    if not ohlcv or len(ohlcv) < 3:
        return {'suspicious': False, 'reason': 'Pas de données OHLCV', 'severity': 'NONE'}

    suspicion_score = 0

    # 1. Volume spike extrême (>8x) sans news
    if vol_spike > 8.0:
        suspicion_score += 2

    # 2. Wicks extrêmes (manipulation visible)
    current_candle = ohlcv[-1]
    if len(current_candle) >= 5:
        open_price, high, low, close = current_candle[1:5]

        body = abs(close - open_price)
        upper_wick = high - max(open_price, close)
        lower_wick = min(open_price, close) - low
        candle_range = high - low

        if candle_range > 0:
            wick_ratio = (upper_wick + lower_wick) / candle_range

            # Wicks > 90% du range = manipulation
            if wick_ratio > 0.9:
                suspicion_score += 1

    # 3. Prix en dehors de 4 écarts-types
    try:
        closes = [c[4] for c in ohlcv[-20:] if len(c) >= 5]
        if len(closes) >= 10:
            mean_price = sum(closes) / len(closes)
            variance = sum((c - mean_price) ** 2 for c in closes) / len(closes)
            std_price = variance ** 0.5 if variance > 0 else 0

            if std_price > 0 and len(current_candle) >= 5:
                z_score = abs(current_candle[4] - mean_price) / std_price

                if z_score > 4:
                    suspicion_score += 2
    except:
        pass

    # 4. Mouvement > 5% en 1 minute (trop rapide)
    if timeframe == '1m' and len(current_candle) >= 5:
        open_price = current_candle[1]
        close = current_candle[4]
        price_change = abs(close - open_price) / open_price * 100 if open_price > 0 else 0

        if price_change > 5:
            suspicion_score += 2

    # 5. Pattern pump & dump classique
    if len(ohlcv) >= 3:
        candle_1 = ohlcv[-3]
        candle_2 = ohlcv[-2]
        candle_3 = ohlcv[-1]

        if len(candle_1) >= 5 and len(candle_2) >= 5 and len(candle_3) >= 5:
            close_1 = candle_1[4]
            close_2 = candle_2[4]
            close_3 = candle_3[4]

            # Pump : +3% en 1 bougie
            pump = (close_2 - close_1) / close_1 * 100 if close_1 > 0 else 0
            # Dump : -2% en 1 bougie après pump
            dump = (close_3 - close_2) / close_2 * 100 if close_2 > 0 else 0

            if pump > 3 and dump < -2:
                suspicion_score += 3

    # Rejeter seulement si score élevé (≥4)
    if suspicion_score >= 4:
        reasons = []
        if vol_spike > 8.0:
            reasons.append(f'Volume spike extrême ({vol_spike:.1f}x)')
        if suspicion_score >= 3:
            reasons.append('Pattern pump & dump')
        reason = ' | '.join(reasons) if reasons else 'Manipulation suspectée'

        return {
            'suspicious': True,
            'reason': reason,
            'severity': 'HIGH' if suspicion_score >= 5 else 'MEDIUM'
        }

    # Pas de manipulation détectée
    return {'suspicious': False, 'reason': 'Clean', 'severity': 'NONE'}


def check_price_action_coherence(
    direction: str,
    current_candle: list,
    previous_candle: Optional[list],
    ema9: float,
    ema21: float
) -> Dict:
    """
    Vérifier cohérence price action avec direction

    Args:
        direction: 'LONG' ou 'SHORT'
        current_candle: [timestamp, open, high, low, close, volume]
        previous_candle: Bougie précédente (optionnel)
        ema9: EMA 9
        ema21: EMA 21

    Returns:
        Dict avec coherent, reason, quality
    """
    if not previous_candle:
        return {'coherent': True, 'reason': 'Pas de bougie précédente', 'quality': 'UNKNOWN'}

    open_price, high, low, close = current_candle[1:5]
    prev_open, prev_high, prev_low, prev_close = previous_candle[1:5]

    body = abs(close - open_price)
    candle_range = high - low

    if candle_range == 0:
        return {'coherent': False, 'reason': 'Range nul', 'quality': 'POOR'}

    body_ratio = body / candle_range if candle_range > 0 else 0

    if direction == 'LONG':
        # LONG : Vérifier que bougie actuelle est haussière
        is_bullish = close > open_price
        momentum_ok = close > prev_close
        above_ema9 = close > ema9

        # Vérifier wicks
        upper_wick = high - max(open_price, close)
        lower_wick = min(open_price, close) - low
        wick_imbalance = upper_wick > lower_wick * 2 if lower_wick > 0 else False

        # Plus tolérant pour doji/indécision
        if body_ratio < 0.2:  # Doji (très petit corps)
            quality = 'ACCEPTABLE'
            return {'coherent': True, 'reason': 'Doji/indécision', 'quality': quality}

        # Si bougie actuelle bearish MAIS précédente très bullish
        if not is_bullish and prev_close > prev_open and (prev_close - prev_open) > body * 2:
            quality = 'ACCEPTABLE'
            return {'coherent': True, 'reason': 'Momentum précédent fort', 'quality': quality}

        # Validation stricte seulement si contradiction majeure
        if not is_bullish and body_ratio > 0.5:  # Bearish avec corps significatif
            return {
                'coherent': False,
                'reason': 'Bougie baissière (close < open)',
                'quality': 'POOR'
            }

        if wick_imbalance and body_ratio < 0.5:  # Upper wick suspect
            return {
                'coherent': False,
                'reason': 'Upper wick suspect (rejection)',
                'quality': 'POOR'
            }

        # Quality scoring
        if is_bullish and momentum_ok and above_ema9 and body_ratio > 0.6:
            quality = 'EXCELLENT'
        elif is_bullish and momentum_ok:
            quality = 'GOOD'
        else:
            quality = 'ACCEPTABLE'

        return {'coherent': True, 'reason': 'Cohérente', 'quality': quality}

    else:  # SHORT
        is_bearish = close < open_price
        momentum_ok = close < prev_close
        below_ema9 = close < ema9

        upper_wick = high - max(open_price, close)
        lower_wick = min(open_price, close) - low
        wick_imbalance = lower_wick > upper_wick * 2 if upper_wick > 0 else False

        # Plus tolérant pour doji/indécision
        if body_ratio < 0.2:
            quality = 'ACCEPTABLE'
            return {'coherent': True, 'reason': 'Doji/indécision', 'quality': quality}

        # Si bougie actuelle bullish MAIS précédente très bearish
        if not is_bearish and prev_close < prev_open and (prev_open - prev_close) > body * 2:
            quality = 'ACCEPTABLE'
            return {'coherent': True, 'reason': 'Momentum précédent fort', 'quality': quality}

        # Validation stricte seulement si contradiction majeure
        if not is_bearish and body_ratio > 0.5:
            return {
                'coherent': False,
                'reason': 'Bougie haussière (close > open)',
                'quality': 'POOR'
            }

        if wick_imbalance and body_ratio < 0.5:
            return {
                'coherent': False,
                'reason': 'Lower wick suspect (rejection)',
                'quality': 'POOR'
            }

        if is_bearish and momentum_ok and below_ema9 and body_ratio > 0.6:
            quality = 'EXCELLENT'
        elif is_bearish and momentum_ok:
            quality = 'GOOD'
        else:
            quality = 'ACCEPTABLE'

        return {'coherent': True, 'reason': 'Cohérente', 'quality': quality}
