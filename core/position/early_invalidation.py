#!/usr/bin/env python3
"""
Early Invalidation - Trade Cursor v7.0
Invalidation précoce des positions (30 premières secondes)
"""

import logging
import time
from typing import Optional, Dict, Any
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


class EarlyInvalidationChecker:
    """Gestionnaire d'invalidation précoce"""

    def __init__(self, config: Optional[EarlyInvalidationConfig] = None):
        self.config = config or EarlyInvalidationConfig()

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

    def check_invalidation(
        self,
        position: Dict[str, Any],
        current_price: float,
        pnl_percent: float
    ) -> Optional[str]:
        """
        Vérifier si position doit être invalidée précocement

        Args:
            position: Dict position avec start_time, entry, atr, etc.
            current_price: Prix actuel
            pnl_percent: PnL en pourcentage

        Returns:
            'EARLY_INVALIDATION' si doit être fermée, None sinon
        """
        if not self.config.enabled:
            return None

        # Calculer temps écoulé
        elapsed = time.time() - position.get('start_time', 0)

        # Fenêtre 10-30 secondes
        if elapsed < 10 or elapsed > 30:
            return None

        # Calculer ATR en pourcentage
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
