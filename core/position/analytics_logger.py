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
            # Timestamp actuel
            now = datetime.now()
            timestamp_iso = now.isoformat()
            date_str = now.strftime('%Y-%m-%d')
            time_str = now.strftime('%H:%M:%S')

            # Calculer durée
            opened_at = position.get('opened_at')
            duration = None
            if opened_at:
                try:
                    if isinstance(opened_at, str):
                        opened_dt = datetime.fromisoformat(opened_at.replace('Z', '+00:00'))
                    else:
                        opened_dt = opened_at
                    duration = int((now - opened_dt).total_seconds())
                except Exception as e:
                    logger.debug(f"Erreur calcul duration: {e}")

            # ✅ FIX: Validation exit_price (double sécurité)
            if not exit_price or exit_price <= 0:
                logger.warning(
                    f"⚠️ Analytics Logger: Exit price invalide pour {position.get('symbol')}: {exit_price}, "
                    f"utilisation entry price"
                )
                exit_price = position.get('entry', 0)

            trade_data = {
                # Champs obligatoires NOT NULL
                'timestamp': timestamp_iso,
                'date': date_str,
                'time': time_str,
                'symbol': position.get('symbol', 'N/A'),
                'direction': position.get('direction', 'LONG'),
                'entry': position.get('entry', 0),
                'exit': exit_price,

                # PnL (obligatoires NOT NULL)
                'gross_pnl_pct': pnl_data.get('pnl_pct', 0),
                'gross_pnl_usdt': pnl_data.get('gross_pnl', pnl_data.get('net_pnl', 0)),
                'net_pnl_pct': pnl_data.get('pnl_pct', 0),
                'net_pnl_usdt': pnl_data.get('net_pnl', 0),

                # Coûts
                'fees': pnl_data.get('fees', 0),
                'slippage': pnl_data.get('slippage', 0),
                'total_costs': pnl_data.get('fees', 0) + pnl_data.get('slippage', 0),

                # Infos trade
                'reason': reason,
                'duration': duration,
                'condition_types': position.get('confirmed_by', ''),

                # Mode & Config
                'trading_mode': mode,
                'tp_sl_mode': position.get('tp_sl_mode'),

                # États
                'break_even_triggered': position.get('break_even_triggered', False),
                'trailing_stop_triggered': position.get('trailing_stop_triggered', False),
                'partial_tp_triggered': position.get('partial_tp_sold', False),

                # TP Escalier
                'tp_escalier_enabled': position.get('tp_escalier_enabled', False),
                'tp_escalier_levels_hit': position.get('tp_escalier_levels_hit', []),
                'tp_escalier_profits': position.get('tp_escalier_profits', []),

                # Métriques
                'max_pnl_reached': position.get('max_pnl_reached'),
                'min_pnl_reached': position.get('min_pnl_reached'),

                # Metadata
                'session_id': position.get('session_id'),
                'is_backtest': mode == 'BACKTEST'
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
