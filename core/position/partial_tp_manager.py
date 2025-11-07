#!/usr/bin/env python3
"""
Partial TP Manager - Trade Cursor v7.0
Gestion du Take Profit partiel (50%)
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class PartialTPManager:
    """Gestionnaire TP Partiel"""

    @staticmethod
    def check_trigger(
        position: Dict[str, Any],
        current_price: float,
        trigger_pct: float = 0.25
    ) -> bool:
        """
        Vérifier si TP partiel doit être déclenché

        Args:
            position: Dict position
            current_price: Prix actuel
            trigger_pct: Seuil déclenchement (défaut +0.25%)

        Returns:
            True si doit vendre 50%
        """
        if position.get('partial_tp_sold', False):
            return False  # Déjà vendu

        entry = position.get('entry', 0)
        direction = position.get('direction', 'LONG')

        if direction == 'LONG':
            pnl_pct = ((current_price - entry) / entry) * 100
        else:
            pnl_pct = ((entry - current_price) / entry) * 100

        return pnl_pct >= trigger_pct

    @staticmethod
    def execute_partial_tp(
        position: Dict[str, Any],
        current_price: float
    ) -> Dict[str, Any]:
        """
        Exécuter TP partiel (vendre 50%)

        Args:
            position: Dict position
            current_price: Prix de vente

        Returns:
            Dict avec détails TP partiel
        """
        entry = position['entry']
        size = position['size']
        direction = position['direction']

        # Vendre 50%
        size_sold = size * 0.5
        size_remaining = size * 0.5

        # Calculer profit
        if direction == 'LONG':
            profit_pct = ((current_price - entry) / entry) * 100
        else:
            profit_pct = ((entry - current_price) / entry) * 100

        profit_usdt = size_sold * (profit_pct / 100)

        # Mettre à jour position
        position['partial_tp_sold'] = True
        position['size_remaining'] = size_remaining
        position['partial_profit_usdt'] = profit_usdt

        logger.info(
            f"💰 TP Partiel {direction} {position.get('symbol', 'N/A')}: "
            f"Vendu {size_sold:.2f} USDT (50%) à {current_price:.8f} | "
            f"Profit: +{profit_usdt:.2f} USDT (+{profit_pct:.2f}%)"
        )

        return {
            'size_sold': size_sold,
            'size_remaining': size_remaining,
            'profit_pct': profit_pct,
            'profit_usdt': profit_usdt,
            'price': current_price
        }

    @staticmethod
    def update_sl_after_partial_tp(position: Dict[str, Any]) -> float:
        """
        Déplacer SL à break-even après TP partiel

        Args:
            position: Dict position

        Returns:
            Nouveau SL (entry)
        """
        entry = position['entry']
        position['sl'] = entry
        position['break_even_set'] = True

        logger.info(f"🛡️ SL déplacé à Break-even après TP partiel: {entry:.8f}")

        return entry
