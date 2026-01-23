#!/usr/bin/env python3
"""
Trailing Stop - Trade Cursor v7.0
Gestion du trailing stop adaptatif basé sur ATR
"""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TrailingStopConfig:
    """Configuration pour trailing stop"""
    enabled: bool = True
    trigger_pnl: float = 0.25  # Déclenchement à +0.25%
    atr_multiplier: float = 0.4  # Distance = ATR × 0.4
    min_distance: float = 0.08  # Distance minimale 0.08%
    max_distance: float = 0.25  # Distance maximale 0.25%
    
    # Legacy compatibility pour tests
    distance_multiplier: Optional[float] = None
    activation_threshold: Optional[float] = None
    enable_partial_trailing: Optional[bool] = None
    
    def __post_init__(self):
        """Conversion legacy vers nouveaux champs"""
        if self.distance_multiplier is not None:
            self.atr_multiplier = self.distance_multiplier
        if self.activation_threshold is not None:
            self.trigger_pnl = self.activation_threshold
        if self.enable_partial_trailing is not None:
            self.enabled = self.enable_partial_trailing


class TrailingStopManager:
    """Gestionnaire de trailing stop adaptatif"""

    def __init__(self, config: Optional[TrailingStopConfig] = None):
        self.config = config or TrailingStopConfig()

    def calculate_trailing_stop(
        self,
        position_data: Dict[str, Any],
        current_price: float
    ) -> Optional[float]:
        """
        Calculer nouveau prix de trailing stop pour compatibility tests
        
        Args:
            position_data: Dict avec entry_price, side, max_price, etc.
            current_price: Prix actuel
            
        Returns:
            Nouveau prix SL ou None si pas triggered
        """
        entry_price = position_data.get('entry_price', 0.0)
        direction = position_data.get('side', 'LONG')
        max_price = position_data.get('max_price', current_price)
        
        if entry_price <= 0:
            return None
            
        # Calculer PnL pour déterminer si trigger
        if direction == 'LONG':
            current_pnl_pct = ((current_price - entry_price) / entry_price) * 100
        else:
            current_pnl_pct = ((entry_price - current_price) / entry_price) * 100
            
        if current_pnl_pct < self.config.trigger_pnl:
            return None
            
        # Distance simple basée sur config
        distance_pct = self.config.min_distance
        
        if direction == 'LONG':
            # SL en-dessous du prix actuel
            return current_price * (1 - distance_pct / 100)
        else:  # SHORT
            # SL au-dessus du prix actuel
            return current_price * (1 + distance_pct / 100)
    
    def update_max_price(self, position_data: Dict[str, Any], new_price: float) -> float:
        """Helper method pour compatibility tests"""
        return new_price

    def calculate_adaptive_distance(
        self,
        atr_percent: float
    ) -> float:
        """
        Calculer distance de trailing adaptative selon ATR

        Args:
            atr_percent: ATR en pourcentage du prix

        Returns:
            Distance trailing en %
        """
        # Distance basée sur ATR
        trailing_distance = atr_percent * self.config.atr_multiplier

        # Appliquer bornes
        trailing_distance = max(
            self.config.min_distance,
            min(self.config.max_distance, trailing_distance)
        )

        return trailing_distance

    def update_trailing_stop(
        self,
        position: Dict[str, Any],
        current_price: float,
        pnl_percent: float,
        custom_distance_pct: Optional[float] = None  # 🔥 SUPPORT ADAPTATIF
    ) -> Optional[float]:
        """
        Mettre à jour trailing stop pour une position

        Args:
            position: Dict position avec entry, atr, sl, direction
            current_price: Prix actuel
            pnl_percent: PnL en pourcentage
            custom_distance_pct: Distance trailing forcée (ex: calculée avec params adaptatifs)

        Returns:
            Nouveau SL si mis à jour, None sinon
        """
        if not self.config.enabled:
            return None

        # Vérifier déclenchement
        if pnl_percent <= self.config.trigger_pnl:
            return None

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
                atr_percent = 0.5  # Fallback

        # Calculer distance trailing adaptative
        if custom_distance_pct is not None:
            trailing_distance = custom_distance_pct
        else:
            trailing_distance = self.calculate_adaptive_distance(atr_percent)

        # Calculer nouveau SL
        direction = position.get('direction', 'LONG')
        current_sl = position.get('sl', 0)

        if direction == 'LONG':
            new_sl = current_price * (1 - trailing_distance / 100)

            # Monter SL uniquement (jamais descendre)
            if new_sl > current_sl:
                new_sl = round(new_sl, 8)

                logger.info(
                    f"🔄 Trailing SL LONG {position.get('symbol', 'N/A')}: "
                    f"{current_sl:.8f} → {new_sl:.8f} (-{trailing_distance:.2f}%) "
                    f"[ATR: {atr_percent:.2f}%]"
                )

                return new_sl

        else:  # SHORT
            new_sl = current_price * (1 + trailing_distance / 100)

            # Descendre SL uniquement (jamais monter)
            if new_sl < current_sl:
                new_sl = round(new_sl, 8)

                logger.info(
                    f"🔄 Trailing SL SHORT {position.get('symbol', 'N/A')}: "
                    f"{current_sl:.8f} → {new_sl:.8f} (+{trailing_distance:.2f}%) "
                    f"[ATR: {atr_percent:.2f}%]"
                )

                return new_sl

        return None

    def should_trigger(self, pnl_percent: float) -> bool:
        """
        Vérifier si trailing stop doit être déclenché

        Args:
            pnl_percent: PnL en pourcentage

        Returns:
            True si PnL > trigger threshold
        """
        return pnl_percent > self.config.trigger_pnl
