"""
Filtres de validation pour l'analyse technique
Filtre les setups selon volume, SNR, breakout, wicks, et ATR
"""

from typing import Dict, Optional
from config import TRADING_CONFIG, DEBUG_ENABLED
from utils.logger import get_logger
from utils.effective_config import get_effective_value  # 🔥 NOUVEAU


logger = get_logger()


def check_volume_filter(
    vol_spike: float,
    min_vol_ratio: float,
    symbol: str,
    timeframe: str,
    atr_percent: float,
    volume_multiplier: float,
    return_reason: bool = False
) -> Optional[Dict]:
    """
    Filtre les setups avec volume insuffisant

    Args:
        vol_spike: Ratio volume spike actuel
        min_vol_ratio: Ratio minimum requis
        symbol: Symbole de la paire
        timeframe: Timeframe
        atr_percent: ATR en pourcentage
        volume_multiplier: Multiplicateur de volume
        return_reason: Si True, retourner raison du rejet

    Returns:
        None si valide, Dict avec raison si rejeté
    """
    # Min volume ratio adaptatif
    base_min_vol = 1.0 if atr_percent > 1.0 else (0.6 if atr_percent < 0.3 else 0.8)
    min_vol_ratio = base_min_vol * volume_multiplier
    min_vol_ratio = max(0.4, min(1.5, min_vol_ratio))

    logger.debug(
        f"📊 {symbol} {timeframe}: Volume | "
        f"ATR%: {atr_percent:.3f} | "
        f"Base min_vol: {base_min_vol:.2f}x | "
        f"Volume multiplier: {volume_multiplier:.2f} | "
        f"Min requis: {min_vol_ratio:.2f}x | "
        f"Vol actuel: {vol_spike:.2f}x"
    )

    if vol_spike < min_vol_ratio:
        reason = (
            f"Volume insuffisant: {vol_spike:.2f}x < {min_vol_ratio:.2f}x requis "
            f"(base: {base_min_vol:.2f}x × mult: {volume_multiplier:.2f})"
        )
        if return_reason:
            return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe}
        logger.debug(f"{symbol} {timeframe}: {reason}")
        return {'rejected': True, 'reason': reason}

    return None


def check_snr_filter(
    price: float,
    ema21: float,
    atr: float,
    symbol: str,
    timeframe: str,
    return_reason: bool = False
) -> Optional[Dict]:
    """
    Filtre SNR (Signal-to-Noise Ratio)
    Rejette les signaux plats ou trop proches de l'EMA21

    Args:
        price: Prix actuel
        ema21: EMA 21
        atr: ATR
        symbol: Symbole de la paire
        timeframe: Timeframe
        return_reason: Si True, retourner raison du rejet

    Returns:
        None si valide, Dict avec raison si rejeté
    """
    # ✅ Vérifier si le filtre SNR est activé
    use_snr = TRADING_CONFIG.get('use_snr', True)
    if not use_snr:
        return None  # Filtre désactivé, toujours valide
    
    snr = abs(price - ema21) / atr if atr > 0 else 0
    snr_threshold = TRADING_CONFIG.get('snr_threshold', 0.3)

    logger.debug(
        f"📊 {symbol} {timeframe}: SNR | "
        f"Price: {price:.6f} | EMA21: {ema21:.6f} | Diff: {abs(price - ema21):.6f} | "
        f"ATR: {atr:.6f} | SNR: {snr:.3f} | Seuil: {snr_threshold}"
    )

    if snr < snr_threshold:
        reason = f"SNR trop faible: {snr:.3f} < {snr_threshold} (signal plat)"
        if return_reason:
            return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe}
        logger.debug(f"{symbol} {timeframe}: {reason}")
        return {'rejected': True, 'reason': reason}

    return None


def check_breakout_filter(
    price: float,
    ema21: float,
    atr: float,
    symbol: str,
    timeframe: str,
    return_reason: bool = False
) -> Optional[Dict]:
    """
    Filtre Breakout - Rejette si prix dans range EMA21 ± ATR

    Args:
        price: Prix actuel
        ema21: EMA 21
        atr: ATR
        symbol: Symbole de la paire
        timeframe: Timeframe
        return_reason: Si True, retourner raison du rejet

    Returns:
        None si valide, Dict avec raison si rejeté
    """
    # ✅ Vérifier si le filtre breakout est activé
    use_breakout = TRADING_CONFIG.get('use_breakout', True)
    if not use_breakout:
        return None  # Filtre désactivé, toujours valide
    
    breakout_mult = TRADING_CONFIG.get('breakout_threshold', 0.3)
    breakout_threshold = atr * breakout_mult

    if price < ema21 + breakout_threshold and price > ema21 - breakout_threshold:
        reason = f"Pas de breakout: prix dans range ±ATR*{breakout_mult} autour de EMA21"
        if return_reason:
            return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe}
        if DEBUG_ENABLED:
            logger.debug(f"{symbol} {timeframe}: {reason}")
        return {'rejected': True, 'reason': reason}

    return None


def check_wick_filter(
    current_candle: list,
    symbol: str,
    timeframe: str,
    return_reason: bool = False
) -> Optional[Dict]:
    """
    Filtre Wick Ratio - Détecte manipulation via wicks excessifs

    Args:
        current_candle: [timestamp, open, high, low, close, volume]
        symbol: Symbole de la paire
        timeframe: Timeframe
        return_reason: Si True, retourner raison du rejet

    Returns:
        None si valide, Dict avec raison si rejeté
    """
    # ✅ Vérifier si le filtre wick est activé
    use_wick = TRADING_CONFIG.get('use_wick', True)
    if not use_wick:
        return None  # Filtre désactivé, toujours valide
    
    body = abs(current_candle[1] - current_candle[4])  # open - close
    if body == 0:
        body = 0.0001  # Éviter division par 0

    wick_ratio = (current_candle[2] - current_candle[3]) / body  # (high - low) / body
    wick_max = TRADING_CONFIG.get('wick_ratio_max', 2.5)

    if wick_ratio > wick_max:
        reason = f"Wicks suspects: ratio={wick_ratio:.2f} > {wick_max} (possible manipulation)"
        if return_reason:
            return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe}
        if DEBUG_ENABLED:
            logger.debug(f"{symbol} {timeframe}: {reason}")
        return {'rejected': True, 'reason': reason}

    return None


def check_atr_filter(
    atr_percent: float,
    timeframe: str,
    symbol: str,
    return_reason: bool = False
) -> Optional[Dict]:
    """
    Filtre ATR optimal - Rejette si ATR trop bas ou trop élevé
    
    Args:
        atr_percent: ATR en pourcentage
        timeframe: '1m' ou '5m'
        symbol: Symbole de la paire
        return_reason: Si True, retourner raison du rejet
        
    Returns:
        None si valide, Dict avec raison si rejeté
    """
    if timeframe == '1m':
        # 🔥 Utiliser valeurs dynamiques du régime si disponibles
        optimal_atr_min = get_effective_value('optimal_atr_min_1m')
        optimal_atr_max = get_effective_value('optimal_atr_max_1m')
        
        # Fallback si None (ne devrait pas arriver avec config par défaut)
        if optimal_atr_min is None: optimal_atr_min = TRADING_CONFIG['optimal_atr_min_1m']
        if optimal_atr_max is None: optimal_atr_max = TRADING_CONFIG['optimal_atr_max_1m']
    else:
        # 🔥 FIX: Utiliser valeurs dynamiques du régime pour 5m aussi
        optimal_atr_min = get_effective_value('optimal_atr_min_5m')
        optimal_atr_max = get_effective_value('optimal_atr_max_5m')
        
        # Fallback si None
        if optimal_atr_min is None: optimal_atr_min = TRADING_CONFIG['optimal_atr_min_5m']
        if optimal_atr_max is None: optimal_atr_max = TRADING_CONFIG['optimal_atr_max_5m']

    if atr_percent < optimal_atr_min or atr_percent > optimal_atr_max:
        atr_status = 'trop bas' if atr_percent < optimal_atr_min else 'trop élevé'
        reason = f"ATR sous-optimal: {atr_percent:.3f}% ({atr_status}, optimal: {optimal_atr_min}-{optimal_atr_max}%)"
        if return_reason:
            return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe}
        if DEBUG_ENABLED:
            logger.debug(f"{symbol} {timeframe}: {reason}")
        return {'rejected': True, 'reason': reason}

    return None
