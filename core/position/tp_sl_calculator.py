#!/usr/bin/env python3
"""
TP/SL Calculator - Trade Cursor v7.0
Calcul des niveaux Take Profit et Stop Loss (modes FIXE et ATR)
"""

import logging
from typing import Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TPSLConfig:
    """Configuration pour calculs TP/SL"""
    # Mode FIXE
    fixed_tp_pct: float = 0.6
    fixed_sl_pct: float = 0.25

    # Mode ATR
    atr_mult_tp: float = 1.5
    atr_mult_sl: float = 1.0
    atr_min: float = 0.15
    atr_max: float = 1.5

    # Streaks (pour ajustement dynamique)
    win_streak: int = 0
    loss_streak: int = 0


def calculate_fixed_levels(
    entry: float,
    direction: str,
    config: TPSLConfig
) -> Tuple[float, float]:
    """
    Calculer TP/SL en mode FIXE

    Args:
        entry: Prix d'entrée
        direction: 'LONG' ou 'SHORT'
        config: Configuration TP/SL

    Returns:
        (sl, tp) : Stop Loss et Take Profit

    Raises:
        ValueError: Si les paramètres sont invalides
    """
    # Validation entry
    if not entry or entry <= 0:
        raise ValueError(f"Entry invalide dans calculate_fixed_levels: {entry}")

    # Validation config
    if config.fixed_sl_pct <= 0 or config.fixed_tp_pct <= 0:
        raise ValueError(
            f"Config invalide: fixed_sl_pct={config.fixed_sl_pct}%, "
            f"fixed_tp_pct={config.fixed_tp_pct}%"
        )

    # 🔥 FIX 18/12: Appliquer sl_max_pct aussi en mode FIXE
    from config import TRADING_CONFIG
    sl_max_pct = TRADING_CONFIG.get('sl_max_pct', 0.50)
    sl_pct = config.fixed_sl_pct
    if sl_pct > sl_max_pct:
        logger.warning(f"⚠️ Mode FIXE: SL capped: {sl_pct:.2f}% → {sl_max_pct}% (max)")
        sl_pct = sl_max_pct

    # Calcul initial
    if direction == 'LONG':
        sl = entry * (1 - sl_pct / 100)
        tp = entry * (1 + config.fixed_tp_pct / 100)
    else:
        sl = entry * (1 + sl_pct / 100)
        tp = entry * (1 - config.fixed_tp_pct / 100)

    # Déterminer précision selon taille du prix
    if entry < 0.001:
        precision = 10
    elif entry < 0.01:
        precision = 9
    else:
        precision = 8

    # Tolérance minimale
    tolerance = max(entry * 0.0001, 0.00000001)

    # Vérifier différence AVANT arrondi
    sl_diff = abs(sl - entry)
    tp_diff = abs(tp - entry)

    if sl_diff < tolerance or tp_diff < tolerance:
        logger.warning(
            f"⚠️ Calcul FIXE: différence trop faible avant arrondi "
            f"(sl_diff={sl_diff:.10f}, tp_diff={tp_diff:.10f}, tolerance={tolerance:.10f})"
        )

    # Arrondir
    sl_rounded = round(sl, precision)
    tp_rounded = round(tp, precision)

    # Vérifier différence APRÈS arrondi
    sl_rounded_diff = abs(sl_rounded - entry)
    tp_rounded_diff = abs(tp_rounded - entry)

    if sl_rounded_diff < tolerance or tp_rounded_diff < tolerance:
        # Recalculer avec pourcentage plus élevé
        min_diff_pct = 0.15 if entry < 0.001 else 0.1
        min_diff_pct = max(min_diff_pct, config.fixed_sl_pct * 1.2)

        if direction == 'LONG':
            sl_rounded = round(entry * (1 - min_diff_pct / 100), precision)
            tp_rounded = round(entry * (1 + min_diff_pct / 100), precision)
        else:
            sl_rounded = round(entry * (1 + min_diff_pct / 100), precision)
            tp_rounded = round(entry * (1 - min_diff_pct / 100), precision)

        # Vérification finale
        final_sl_diff = abs(sl_rounded - entry)
        final_tp_diff = abs(tp_rounded - entry)

        if final_sl_diff < tolerance or final_tp_diff < tolerance:
            # Dernière tentative avec 0.2% minimum
            min_diff_pct = 0.2
            if direction == 'LONG':
                sl_rounded = round(entry * (1 - min_diff_pct / 100), precision)
                tp_rounded = round(entry * (1 + min_diff_pct / 100), precision)
            else:
                sl_rounded = round(entry * (1 + min_diff_pct / 100), precision)
                tp_rounded = round(entry * (1 - min_diff_pct / 100), precision)

            logger.warning(
                f"🔧 Valeurs forcées avec min_diff={min_diff_pct}%: "
                f"sl={sl_rounded:.10f}, tp={tp_rounded:.10f}"
            )
        else:
            logger.debug(
                f"🔧 Valeurs recalculées avec min_diff={min_diff_pct}%: "
                f"sl={sl_rounded:.10f}, tp={tp_rounded:.10f}"
            )

    logger.debug(
        f"📊 Mode FIXE: entry={entry:.8f} | sl={sl_rounded:.8f} (-{config.fixed_sl_pct}%) | "
        f"tp={tp_rounded:.8f} (+{config.fixed_tp_pct}%) | direction={direction}"
    )

    return sl_rounded, tp_rounded


def calculate_atr_levels(
    entry: float,
    atr: float,
    atr5m: Optional[float],
    direction: str,
    config: TPSLConfig,
    return_atr_used: bool = False
) -> Tuple[float, float]:
    """
    Calculer TP/SL en mode ATR (adaptatif)

    Args:
        entry: Prix d'entrée
        atr: ATR timeframe 1m
        atr5m: ATR timeframe 5m (optionnel)
        direction: 'LONG' ou 'SHORT'
        config: Configuration TP/SL
        return_atr_used: Si True, retourne aussi l'ATR% utilisé (clampé) et ATR blended

    Returns:
        (sl, tp) ou (sl, tp, atr_percent_used, atr_blended) si return_atr_used=True

    Raises:
        ValueError: Si ATR invalide, fallback mode FIXE
    """
    # Validation ATR
    if not atr or atr <= 0:
        logger.warning(f"⚠️ ATR invalide ({atr}), fallback mode FIXE")
        return calculate_fixed_levels(entry, direction, config)

    # Validation entry
    if entry <= 0:
        logger.warning(f"⚠️ Entry invalide ({entry}), fallback mode FIXE")
        return calculate_fixed_levels(entry, direction, config)

    # ATR Multi-Timeframe : 70% 1m + 30% 5m
    if atr5m and atr5m > 0:
        atr_blended = (atr * 0.7) + (atr5m * 0.3)
        logger.debug(f"📊 ATR blended: atr1m={atr:.6f}, atr5m={atr5m:.6f}, blended={atr_blended:.6f}")
    else:
        atr_blended = atr

    # ATR en pourcentage du prix
    atr_percent = (atr_blended / entry) * 100

    # Clamp ATR entre min et max
    if atr_percent < config.atr_min:
        logger.debug(f"📊 ATR clamped: {atr_percent:.3f}% → {config.atr_min}% (min)")
        atr_percent = config.atr_min
    elif atr_percent > config.atr_max:
        logger.debug(f"📊 ATR clamped: {atr_percent:.3f}% → {config.atr_max}% (max)")
        atr_percent = config.atr_max

    # Ajustement dynamique selon streaks
    tp_mult = config.atr_mult_tp
    sl_mult = config.atr_mult_sl

    if config.win_streak >= 3:
        # Mode agressif après wins
        tp_mult = 4.0
        sl_mult = 1.2
        logger.info(
            f"⚖️ Mode AGRESSIF (win_streak={config.win_streak}): "
            f"TPx={tp_mult}, SLx={sl_mult}"
        )
    elif config.loss_streak >= 2:
        # Mode prudent après losses
        tp_mult = 1.5
        sl_mult = 1.2
        logger.info(
            f"⚖️ Mode PRUDENT (loss_streak={config.loss_streak}): "
            f"TPx={tp_mult}, SLx={sl_mult}"
        )

    # 🔥 FIX 18/12: Appliquer SL maximum pour limiter les pertes
    from config import TRADING_CONFIG
    sl_max_pct = TRADING_CONFIG.get('sl_max_pct', 0.50)  # Default 0.5%
    sl_pct = atr_percent * sl_mult
    if sl_pct > sl_max_pct:
        logger.warning(f"⚠️ SL capped: {sl_pct:.2f}% → {sl_max_pct}% (max)")
        sl_pct = sl_max_pct
    
    # Calculer TP/SL
    if direction == 'LONG':
        sl = entry * (1 - sl_pct / 100)
        tp = entry * (1 + atr_percent / 100 * tp_mult)
    else:
        sl = entry * (1 + sl_pct / 100)
        tp = entry * (1 - atr_percent / 100 * tp_mult)
    
    # 🔥 DEBUG: Log immédiat après calcul pour tracer le bug SL
    logger.warning(
        f"🔍 TPSL CALC: {direction} | entry={entry:.8f} | sl_pct={sl_pct:.4f}% | "
        f"sl={sl:.8f} | sl {'>' if sl > entry else '<'} entry"
    )

    # 🔥 FIX: Validation de sécurité - détecter et corriger TP/SL inversés
    # Pour LONG: tp > entry > sl | Pour SHORT: sl > entry > tp
    if direction == 'LONG':
        if tp <= entry or sl >= entry:
            logger.error(f"⚠️ TP/SL INVERSÉS détectés pour LONG! tp={tp}, entry={entry}, sl={sl} - Recalcul...")
            sl = entry * (1 - sl_pct / 100)
            tp = entry * (1 + atr_percent / 100 * tp_mult)
    else:  # SHORT
        if tp >= entry or sl <= entry:
            logger.error(f"⚠️ TP/SL INVERSÉS détectés pour SHORT! tp={tp}, entry={entry}, sl={sl} - Recalcul...")
            sl = entry * (1 + sl_pct / 100)
            tp = entry * (1 - atr_percent / 100 * tp_mult)

    # Arrondir selon précision
    if entry < 0.001:
        precision = 10
    elif entry < 0.01:
        precision = 9
    else:
        precision = 8

    sl = round(sl, precision)
    tp = round(tp, precision)

    logger.info(
        f"📊 Mode ATR: ATR%={atr_percent:.3f}% | "
        f"TPx={tp_mult} | SLx={sl_mult} | "
        f"entry={entry:.8f} | sl={sl:.8f} | tp={tp:.8f} | {direction}"
    )

    # 🔥 FIX 29/12: Option pour retourner l'ATR réellement utilisé (blended + clampé)
    if return_atr_used:
        return sl, tp, atr_percent, atr_blended
    return sl, tp


def validate_levels(
    entry: float,
    sl: float,
    tp: float,
    tolerance: float = 0.0001
) -> bool:
    """
    Valider que les niveaux TP/SL sont suffisamment éloignés de entry

    Args:
        entry: Prix d'entrée
        sl: Stop Loss
        tp: Take Profit
        tolerance: Tolérance relative (défaut 0.01%)

    Returns:
        True si valide, False sinon
    """
    if entry <= 0:
        return False

    min_diff = entry * tolerance

    sl_diff = abs(sl - entry)
    tp_diff = abs(tp - entry)

    is_valid = sl_diff >= min_diff and tp_diff >= min_diff

    if not is_valid:
        logger.warning(
            f"⚠️ Niveaux invalides: entry={entry:.8f}, sl={sl:.8f} (diff={sl_diff:.8f}), "
            f"tp={tp:.8f} (diff={tp_diff:.8f}), min_diff={min_diff:.8f}"
        )

    return is_valid
