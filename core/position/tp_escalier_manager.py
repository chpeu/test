#!/usr/bin/env python3
"""
TP Escalier Manager - Trade Cursor v7.0
Gestion du Take Profit multi-niveaux (escalier)
"""

import logging
import time
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class TPEscalierManager:
    """Gestionnaire TP Escalier (Multi-Level TP)"""

    @staticmethod
    def initialize_levels(
        position: Dict[str, Any],
        levels_config: List[Dict]
    ) -> None:
        """
        Initialiser TP Escalier pour une position

        Args:
            position: Dict position
            levels_config: Liste config niveaux
        """
        position['tp_escalier_enabled'] = True
        position['tp_escalier_levels'] = levels_config
        position['tp_escalier_current_level'] = 0
        position['tp_escalier_size_remaining'] = 1.0
        position['tp_escalier_profits'] = []

        logger.info(
            f"🎯 TP Escalier activé: {len(levels_config)} niveaux "
            f"({position.get('symbol', 'N/A')})"
        )

    @staticmethod
    def check_and_execute_levels(
        position: Dict[str, Any],
        current_price: float
    ) -> Optional[Dict]:
        """
        Vérifier et exécuter niveaux TP Escalier

        Args:
            position: Dict position
            current_price: Prix actuel

        Returns:
            Dict info niveau si exécuté, None sinon
        """
        if not position.get('tp_escalier_enabled', False):
            return None

        levels = position.get('tp_escalier_levels', [])
        current_level_idx = position.get('tp_escalier_current_level', 0)

        # Vérifier si tous niveaux passés
        if current_level_idx >= len(levels):
            return None

        # Vérifier niveau actuel
        level_config = levels[current_level_idx]
        entry = position['entry']
        direction = position['direction']

        # Calculer prix TP pour ce niveau
        pnl_target = level_config['pnl']
        if direction == 'LONG':
            tp_price = entry * (1 + pnl_target / 100)
            tp_hit = current_price >= tp_price
        else:
            tp_price = entry * (1 - pnl_target / 100)
            tp_hit = current_price <= tp_price

        if tp_hit:
            # Exécuter niveau
            size_pct = level_config['size_pct']
            size_sold_usdt = position['size'] * size_pct

            # Calculer profit
            if direction == 'LONG':
                profit_pct = ((tp_price - entry) / entry) * 100
            else:
                profit_pct = ((entry - tp_price) / entry) * 100

            profit_usdt = size_sold_usdt * (profit_pct / 100)

            # Mettre à jour position
            position['tp_escalier_current_level'] += 1
            position['tp_escalier_size_remaining'] -= size_pct

            profit_record = {
                'level': current_level_idx + 1,
                'price': tp_price,
                'size_pct': size_pct,
                'size_usdt': size_sold_usdt,
                'profit_pct': profit_pct,
                'profit_usdt': profit_usdt,
                'timestamp': time.time()
            }
            position['tp_escalier_profits'].append(profit_record)
            position['partial_profit_usdt'] = position.get('partial_profit_usdt', 0) + profit_usdt

            logger.info(
                f"🎯 TP Escalier Niveau {current_level_idx + 1}/{len(levels)} atteint! "
                f"Prix: {tp_price:.8f} | Vendu: {size_sold_usdt:.2f} USDT ({size_pct*100:.0f}%) | "
                f"Profit: +{profit_usdt:.2f} USDT (+{profit_pct:.2f}%) | "
                f"Restant: {position['tp_escalier_size_remaining']*100:.0f}%"
            )

            # Déplacer SL selon config
            move_sl = level_config.get('move_sl', 'entry')
            if move_sl in ['entry', 'breakeven']:
                position['sl'] = entry
                position['break_even_set'] = True
                logger.info(f"🛡️ SL → Breakeven ({entry:.8f})")

            return profit_record

        return None

    @staticmethod
    def get_total_profit(position: Dict[str, Any]) -> float:
        """
        Obtenir profit total cumulé TP Escalier

        Args:
            position: Dict position

        Returns:
            Total profit USDT
        """
        profits = position.get('tp_escalier_profits', [])
        return sum(p['profit_usdt'] for p in profits)
