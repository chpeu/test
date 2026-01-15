#!/usr/bin/env python3
"""
PnL Calculator - Trade Cursor v7.0
Calcul des profits et pertes (réalisés et non réalisés)
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class PnLCalculator:
    """Calculateur de Profit & Loss"""

    @staticmethod
    def calculate_pnl_percent(
        entry: float,
        current_price: float,
        direction: str
    ) -> float:
        """
        Calculer PnL en pourcentage

        Args:
            entry: Prix d'entrée
            current_price: Prix actuel
            direction: 'LONG' ou 'SHORT'

        Returns:
            PnL en pourcentage
        """
        if entry <= 0:
            return 0.0

        pnl = ((current_price - entry) / entry) * 100

        if direction == 'SHORT':
            pnl = -pnl

        return pnl

    @staticmethod
    def calculate_pnl_usdt(
        position: Dict[str, Any],
        current_price: float
    ) -> float:
        """
        Calculer PnL en USDT (incluant TP partiel si applicable)

        Args:
            position: Dict avec entry, size, direction, etc.
            current_price: Prix actuel

        Returns:
            PnL en USDT
        """
        entry = position.get('entry', 0)
        direction = position.get('direction', 'LONG')
        size = position.get('size', 0)

        if entry <= 0 or size <= 0:
            return 0.0

        # Taille à considérer (peut être réduite si TP partiel)
        size_to_consider = size
        partial_tp_sold = position.get('partial_tp_sold', False)

        if partial_tp_sold:
            size_remaining = position.get('size_remaining')
            if size_remaining is not None:
                size_to_consider = size_remaining
            else:
                # Fallback : 50% restants
                size_to_consider = size * 0.5

        # Calculer PnL USDT non réalisé
        if direction == 'LONG':
            price_diff = current_price - entry
            pnl_usdt = size_to_consider * (price_diff / entry)
        else:  # SHORT
            price_diff = entry - current_price
            pnl_usdt = size_to_consider * (price_diff / entry)

        # Ajouter profit TP partiel si déjà vendu
        if partial_tp_sold:
            partial_profit = position.get('partial_profit_usdt', 0.0)
            pnl_usdt += partial_profit

        return pnl_usdt

    @staticmethod
    def calculate_realized_pnl(
        position: Dict[str, Any],
        exit_price: float,
        fees_percent: float = 0.04
    ) -> Dict[str, float]:
        """
        Calculer PnL réalisé à la clôture

        Args:
            position: Dict position
            exit_price: Prix de sortie
            fees_percent: Frais en % (par défaut 0.04%)

        Returns:
            Dict avec pnl_pct, pnl_usdt, fees, net_pnl
        """
        entry = position.get('entry', 0)
        direction = position.get('direction', 'LONG')
        size = position.get('size', 0)

        # Taille à clôturer
        partial_tp_sold = position.get('partial_tp_sold', False)
        size_remaining = position.get('size_remaining')
        
        if partial_tp_sold:
            if size_remaining is None:
                size_remaining = size * 0.5
        else:
            size_remaining = size

        # PnL % basé sur la performance réelle (incluant profits partiels)
        if direction == 'LONG':
            price_diff = exit_price - entry
        else:  # SHORT
            price_diff = entry - exit_price

        # PnL USDT brut (partie non encore vendue)
        pnl_usdt_unrealized = size_remaining * (price_diff / entry) if entry else 0.0

        # 🔥 FIX: Les frais doivent être calculés sur toute la durée du trade
        # 1. Frais d'entrée sur toute la position
        # 2. Frais de sortie sur la partie TP partiel
        # 3. Frais de sortie sur la partie finale
        # Simplement : size_totale * fees * 2
        total_fees = size * (fees_percent / 100) * 2

        # PnL USDT net
        pnl_usdt_partial = position.get('partial_profit_usdt', 0.0)
        
        # 🔥 FIX CRITIQUE: Si partial_tp_sold est False, on ne doit PAS ajouter pnl_usdt_partial
        # car cela signifierait qu'on double-compte ou qu'on ajoute un profit fantôme.
        if not partial_tp_sold:
            pnl_usdt_partial = 0.0
            
        total_gross_usdt = pnl_usdt_unrealized + pnl_usdt_partial
        net_pnl = total_gross_usdt - total_fees

        # Calculer PnL % réel (sur la taille totale initiale)
        if size > 0:
            pnl_pct = (total_gross_usdt / size) * 100
            net_pnl_pct = (net_pnl / size) * 100
        else:
            pnl_pct = 0.0
            net_pnl_pct = 0.0

        # Debug log interne
        logger.debug(
            f"📊 [REALIZED PNL] {position.get('symbol')} | "
            f"Size: {size} | Remaining: {size_remaining} | "
            f"Partial: {pnl_usdt_partial} | Unrealized: {pnl_usdt_unrealized} | "
            f"Gross: {total_gross_usdt} | Net: {net_pnl}"
        )

        return {
            'pnl_pct': round(pnl_pct, 6),
            'pnl_usdt_gross': round(total_gross_usdt, 4),
            'fees': round(total_fees, 4),
            'net_pnl': round(net_pnl, 4),
            'net_pnl_pct': round(net_pnl_pct, 6)
        }

    @staticmethod
    def calculate_costs(
        position: Dict[str, Any],
        fees_percent: float = 0.04,
        slippage_percent: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculer coûts de trading

        Args:
            position: Dict position
            fees_percent: Frais en % (défaut 0.04%)
            slippage_percent: Slippage estimé en % (optionnel)

        Returns:
            Dict avec fees, slippage, total_cost
        """
        size = position.get('size', 0)

        # Frais : entrée + sortie
        fees = size * (fees_percent / 100) * 2

        # Slippage (si fourni)
        if slippage_percent is not None and slippage_percent > 0:
            slippage = size * (slippage_percent / 100)
        else:
            slippage = 0.0

        total_cost = fees + slippage

        return {
            'fees': round(fees, 4),
            'slippage': round(slippage, 4),
            'total_cost': round(total_cost, 4)
        }

    @staticmethod
    def format_pnl_display(pnl_pct: float, pnl_usdt: float) -> str:
        """
        Formater PnL pour affichage

        Args:
            pnl_pct: PnL en %
            pnl_usdt: PnL en USDT

        Returns:
            String formaté avec couleur emoji
        """
        sign = '+' if pnl_pct >= 0 else ''
        emoji = '🟢' if pnl_pct >= 0 else '🔴'

        return f"{emoji} {sign}{pnl_pct:.2f}% ({sign}{pnl_usdt:.2f} USDT)"
