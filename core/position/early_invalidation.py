#!/usr/bin/env python3
"""
Early Invalidation - Trade Cursor v7.0
Invalidation précoce des positions (30 premières secondes)

Améliorations contextuelles:
- Seuils ATR adaptatifs
- Détection momentum inverse
- Détection volume spike contraire
- Détection spread explosion
"""

import logging
import time
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EarlyInvalidationConfig:
    """Configuration pour invalidation précoce"""
    enabled: bool = True
    threshold_15s: float = -0.12  # Seuil pour 10-15s
    threshold_30s: float = -0.08  # Seuil pour 15-30s

    # Seuils adaptatifs ATR
    adaptive_enabled: bool = True
    low_vol_multiplier: float = 0.7   # ATR < 0.3%
    high_vol_multiplier: float = 1.3  # ATR > 0.8%
    
    # 🔥 CONDITIONS CONTEXTUELLES (nouvelles)
    contextual_enabled: bool = True
    
    # Momentum inverse (RSI cross contre la position)
    momentum_check_enabled: bool = True
    rsi_overbought: float = 70.0       # RSI > 70 pour LONG = danger
    rsi_oversold: float = 30.0         # RSI < 30 pour SHORT = danger
    
    # Volume spike contraire (volume anormal dans la mauvaise direction)
    volume_spike_enabled: bool = True
    volume_spike_multiplier: float = 2.0  # Volume > 2x moyenne = spike
    
    # Spread explosion (liquidité disparaît)
    spread_check_enabled: bool = True
    spread_danger_threshold: float = 0.08  # Spread > 0.08% = danger
    
    # Legacy compatibility pour tests
    max_adverse_move_pct: Optional[float] = None
    min_time_seconds: Optional[int] = None
    enable_volume_check: Optional[bool] = None
    
    def __post_init__(self):
        """Conversion legacy vers nouveaux champs"""
        if self.max_adverse_move_pct is not None:
            self.threshold_15s = -abs(self.max_adverse_move_pct)
            self.threshold_30s = -abs(self.max_adverse_move_pct) * 0.7
        if self.min_time_seconds is not None:
            # min_time_seconds était probablement utilisé pour définir les seuils temporels
            pass  # Déjà définis par défaut
        if self.enable_volume_check is not None:
            self.volume_spike_enabled = self.enable_volume_check


class EarlyInvalidationChecker:
    """Gestionnaire d'invalidation précoce"""

    def __init__(self, config: Optional[EarlyInvalidationConfig] = None):
        self.config = config or EarlyInvalidationConfig()

    def should_invalidate(
        self,
        position_data: Dict[str, Any],
        current_price: float,
        current_time: float,
        current_volume: float = None
    ) -> bool:
        """
        Déterminer si position doit être invalidée pour compatibility tests
        
        Args:
            position_data: Dict avec entry_price, side, entry_time, etc.
            current_price: Prix actuel
            current_time: Timestamp actuel
            current_volume: Volume actuel (optionnel)
            
        Returns:
            True si position doit être invalidée
        """
        if not self.config.enabled:
            return False
            
        entry_price = position_data.get('entry_price', 0.0)
        direction = position_data.get('side', 'LONG')
        entry_time = position_data.get('entry_time', current_time)
        
        if entry_price <= 0:
            return False
            
        # Calculer temps écoulé
        elapsed_seconds = int(current_time - entry_time)
        
        # Calculer PnL
        if direction == 'LONG':
            current_pnl_pct = ((current_price - entry_price) / entry_price) * 100
        else:  # SHORT
            current_pnl_pct = ((entry_price - current_price) / entry_price) * 100
        
        # Seuils temporels - utiliser max_adverse_move_pct si fourni via legacy config
        if hasattr(self.config, 'max_adverse_move_pct') and self.config.max_adverse_move_pct is not None:
            # Mode legacy: utiliser max_adverse_move_pct comme seuil global
            threshold = -abs(self.config.max_adverse_move_pct)
            return current_pnl_pct <= threshold
        else:
            # Mode normal avec seuils temporels
            if elapsed_seconds <= 15:
                return current_pnl_pct <= self.config.threshold_15s
            elif elapsed_seconds <= 30:
                return current_pnl_pct <= self.config.threshold_30s
            else:
                return False  # Après 30s, plus d'early invalidation

    def get_adaptive_threshold(
        self,
        elapsed: float,
        atr_percent: float
    ) -> float:
        """
        Calculer seuil adaptatif selon ATR

        Args:
            elapsed: Temps écoulé en secondes
            atr_percent: ATR en pourcentage du prix

        Returns:
            Seuil PnL adaptatif (négatif)
        """
        # Seuil de base selon temps écoulé
        if elapsed <= 15:
            base_threshold = self.config.threshold_15s
        else:
            base_threshold = self.config.threshold_30s

        # Si adaptatif désactivé, retourner base
        if not self.config.adaptive_enabled:
            return base_threshold

        # Ajuster selon volatilité ATR
        if atr_percent < 0.3:
            # Faible volatilité : moins strict
            multiplier = self.config.low_vol_multiplier
        elif atr_percent > 0.8:
            # Haute volatilité : plus strict
            multiplier = self.config.high_vol_multiplier
        else:
            # Volatilité normale
            multiplier = 1.0

        adaptive_threshold = base_threshold * multiplier

        # Bornes de sécurité : -0.15% à -0.05%
        adaptive_threshold = max(-0.15, min(-0.05, adaptive_threshold))

        logger.debug(
            f"🎯 Seuil Early adaptatif: {adaptive_threshold:.3f}% "
            f"(base: {base_threshold:.2f}%, ATR: {atr_percent:.2f}%, "
            f"mult: {multiplier:.2f})"
        )

        return adaptive_threshold

    def check_contextual_exit(
        self,
        position: Dict[str, Any],
        market_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Vérifier les conditions contextuelles de sortie précoce
        
        Args:
            position: Dict position avec direction, etc.
            market_data: Données de marché actuelles (rsi, volume, spread, etc.)
            
        Returns:
            Tuple (should_exit, reason)
        """
        if not self.config.contextual_enabled or not market_data:
            return False, None
        
        direction = position.get('direction', 'LONG')
        reasons = []
        
        # 1. Vérification momentum inverse (RSI)
        if self.config.momentum_check_enabled:
            rsi = market_data.get('rsi_1m') or market_data.get('rsi')
            if rsi is not None:
                if direction == 'LONG' and rsi > self.config.rsi_overbought:
                    reasons.append(f"RSI overbought ({rsi:.1f})")
                elif direction == 'SHORT' and rsi < self.config.rsi_oversold:
                    reasons.append(f"RSI oversold ({rsi:.1f})")
        
        # 2. Vérification volume spike
        if self.config.volume_spike_enabled:
            volume = market_data.get('volume_1m') or market_data.get('volume')
            volume_avg = market_data.get('volume_avg_1m') or market_data.get('volume_avg')
            if volume and volume_avg and volume_avg > 0:
                volume_ratio = volume / volume_avg
                if volume_ratio > self.config.volume_spike_multiplier:
                    # Vérifier si le spike est dans la mauvaise direction
                    price_change = market_data.get('price_change_pct', 0)
                    if (direction == 'LONG' and price_change < -0.05) or \
                       (direction == 'SHORT' and price_change > 0.05):
                        reasons.append(f"Volume spike contraire ({volume_ratio:.1f}x)")
        
        # 3. Vérification spread explosion
        if self.config.spread_check_enabled:
            spread = market_data.get('spread_pct') or market_data.get('spread')
            if spread is not None and spread > self.config.spread_danger_threshold:
                reasons.append(f"Spread explosé ({spread:.3f}%)")
        
        if reasons:
            combined_reason = " + ".join(reasons)
            logger.warning(f"⚠️ Early exit contextuel {direction}: {combined_reason}")
            return True, f"CONTEXTUAL_EXIT: {combined_reason}"
        
        return False, None

    def check_invalidation(
        self,
        position: Dict[str, Any],
        current_price: float,
        pnl_percent: float,
        market_data: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Vérifier si position doit être invalidée précocement
        
        Vérifie:
        1. Seuil PnL adaptatif (ATR)
        2. Conditions contextuelles (RSI, volume spike, spread)

        Args:
            position: Dict position avec start_time, entry, atr, etc.
            current_price: Prix actuel
            pnl_percent: PnL en pourcentage
            market_data: Données de marché optionnelles pour vérifications contextuelles

        Returns:
            'EARLY_INVALIDATION' ou 'CONTEXTUAL_EXIT: ...' si doit être fermée, None sinon
        """
        if not self.config.enabled:
            return None

        # Calculer temps écoulé
        elapsed = time.time() - position.get('start_time', 0)

        # Fenêtre 10-30 secondes pour invalidation PnL
        in_pnl_window = 10 <= elapsed <= 30
        
        # Fenêtre 0-60 secondes pour conditions contextuelles
        in_contextual_window = elapsed <= 60

        # 1. Vérification PnL (fenêtre 10-30s)
        if in_pnl_window:
            # Calculer ATR en pourcentage
            atr_pct_used = position.get('atr_pct_used')
            if isinstance(atr_pct_used, (int, float)) and atr_pct_used > 0:
                atr_percent = float(atr_pct_used)
            else:
                entry = position.get('entry', 0)
                atr = position.get('atr', 0)

                if entry > 0 and atr > 0:
                    atr_percent = (atr / entry) * 100
                else:
                    atr_percent = 0.5  # Valeur par défaut

            # Obtenir seuil adaptatif
            invalidation_threshold = self.get_adaptive_threshold(elapsed, atr_percent)

            # Vérifier si PnL en-dessous du seuil
            if pnl_percent <= invalidation_threshold:
                symbol = position.get('symbol', 'N/A')
                direction = position.get('direction', 'N/A')

                logger.warning(
                    f"⚠️ Invalidation précoce {direction} {symbol}: "
                    f"P&L {pnl_percent:.2f}% après {elapsed:.0f}s "
                    f"(seuil adaptatif: {invalidation_threshold:.2f}%, "
                    f"ATR: {atr_percent:.2f}%)"
                )

                return 'EARLY_INVALIDATION'
        
        # 2. Vérification contextuelle (fenêtre 0-60s)
        if in_contextual_window and market_data:
            should_exit, reason = self.check_contextual_exit(position, market_data)
            if should_exit:
                return reason

        # Setup réagit correctement
        return None

    @staticmethod
    def should_check(elapsed: float) -> bool:
        """
        Vérifier si on est dans la fenêtre d'invalidation précoce

        Args:
            elapsed: Temps écoulé en secondes

        Returns:
            True si dans la fenêtre 10-30s
        """
        return 10 <= elapsed <= 30
