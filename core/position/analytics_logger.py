#!/usr/bin/env python3
"""
Analytics Logger - Trade Cursor v7.0
Logging des trades vers Analytics Database
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AnalyticsLogger:
    """Gestionnaire logging vers Analytics DB"""

    def __init__(self, analytics_db=None):
        self.analytics_db = analytics_db

    def log_trade(
        self,
        position: Dict[str, Any],
        exit_price: float,
        reason: str,
        pnl_data: Dict[str, float],
        mode: str = 'LIVE'
    ) -> None:
        """
        Logger trade dans Analytics DB

        Args:
            position: Dict position
            exit_price: Prix sortie
            reason: Raison fermeture
            pnl_data: Dict avec pnl_pct, net_pnl, fees
            mode: LIVE, PAPER ou BACKTEST
        """
        if not self.analytics_db:
            logger.warning("Analytics DB non disponible")
            return

        try:
            trade_data = {
                'symbol': position.get('symbol', 'N/A'),
                'direction': position.get('direction', 'LONG'),
                'entry_price': position.get('entry', 0),
                'exit_price': exit_price,
                'size_usdt': position.get('size', 0),
                'pnl_percent': pnl_data.get('pnl_pct', 0),
                'pnl_usdt': pnl_data.get('net_pnl', 0),
                'fees': pnl_data.get('fees', 0),
                'reason': reason,
                'mode': mode,
                'timestamp': datetime.now().isoformat(),
                'atr': position.get('atr'),
                'confirmed_by': position.get('confirmed_by', ''),
                'partial_tp_sold': position.get('partial_tp_sold', False),
                'tp_escalier_enabled': position.get('tp_escalier_enabled', False)
            }

            self.analytics_db.insert_trade(trade_data)

            logger.debug(f"📊 Trade loggé dans Analytics DB: {trade_data['symbol']}")

        except Exception as e:
            logger.error(f"❌ Erreur logging Analytics DB: {e}")

    def log_setup_rejected(
        self,
        symbol: str,
        reasons: list,
        details: Optional[Dict] = None
    ) -> None:
        """
        Logger setup rejeté

        Args:
            symbol: Symbole
            reasons: Liste raisons rejet
            details: Détails optionnels
        """
        if not self.analytics_db:
            return

        try:
            self.analytics_db.log_setup_rejected(symbol, reasons, details or {})
            logger.debug(f"📊 Setup rejeté loggé: {symbol} - {reasons}")
        except Exception as e:
            logger.error(f"❌ Erreur logging setup rejeté: {e}")

    def log_setup_validated(
        self,
        symbol: str,
        direction: str,
        score: float,
        conditions: list
    ) -> None:
        """
        Logger setup validé

        Args:
            symbol: Symbole
            direction: LONG/SHORT
            score: Score total
            conditions: Liste conditions validées
        """
        if not self.analytics_db:
            return

        try:
            self.analytics_db.log_setup_validated(symbol, direction, score, conditions)
            logger.debug(f"📊 Setup validé loggé: {symbol} {direction} (score: {score})")
        except Exception as e:
            logger.error(f"❌ Erreur logging setup validé: {e}")
