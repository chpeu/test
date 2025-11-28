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
        mode: str = 'LIVE',
        is_dry_run: Optional[bool] = None
    ) -> None:
        """
        Logger trade dans Analytics DB

        Args:
            position: Dict position
            exit_price: Prix sortie
            reason: Raison fermeture
            pnl_data: Dict avec pnl_pct, net_pnl, fees
            mode: LIVE, PAPER ou BACKTEST
            is_dry_run: True si mode DRY_RUN (simulation), False si réel, None pour auto-detect
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
                'net_pnl_pct': pnl_data.get('net_pnl_pct', pnl_data.get('pnl_pct', 0)),
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
                'setup_id': position.get('setup_id'),
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
                'max_drawdown_intra': position.get('max_drawdown_intra'),
                'early_invalidation_threshold': position.get('early_invalidation_threshold'),
                'early_invalidation_elapsed': position.get('early_invalidation_elapsed'),
                'trailing_stop_updates': position.get('trailing_stop_updates', []),

                # Metadata
                'session_id': position.get('session_id'),
                'is_backtest': mode == 'BACKTEST',
                'backtest_id': position.get('backtest_id'),
                'config_hash': position.get('config_hash'),
                
                # 🔥 LIVE TRADING: Déterminer is_live_trade et is_dry_run
                # is_live_trade = True si mode LIVE (vs PAPER/BACKTEST)
                # is_dry_run = True si simulation (vs ordres réels)
                'is_live_trade': position.get('is_live_trade', mode == 'LIVE'),
                'is_dry_run': position.get('is_dry_run', is_dry_run if is_dry_run is not None else (mode != 'LIVE')),
                'live_execution_mode': position.get('live_execution_mode'),
                'entry_order_id': position.get('entry_order_id'),
                'entry_order_type': position.get('entry_order_type'),
                'entry_requested_price': position.get('entry_requested_price'),
                'entry_fill_price': position.get('entry_fill_price'),
                'entry_slippage_pct': position.get('entry_slippage_pct'),
                'entry_latency_ms': position.get('entry_latency_ms'),
                'entry_timestamp': position.get('entry_timestamp'),
                'entry_api_response': position.get('entry_api_response'),
                'exit_order_id': position.get('exit_order_id'),
                'exit_order_type': position.get('exit_order_type'),
                'exit_requested_price': position.get('exit_requested_price'),
                'exit_fill_price': position.get('exit_fill_price'),
                'exit_slippage_pct': position.get('exit_slippage_pct'),
                'exit_latency_ms': position.get('exit_latency_ms'),
                'exit_timestamp': position.get('exit_timestamp'),
                'exit_api_response': position.get('exit_api_response'),
                'leverage_used': position.get('leverage_used', 1),
                'margin_mode': position.get('margin_mode', 'isolated'),
                'position_size_usdt': position.get('position_size_usdt'),
                'position_size_contracts': position.get('position_size_contracts'),
                'liquidation_price': position.get('liquidation_price'),
                'margin_used': position.get('margin_used'),
                'maker_fee_rate': position.get('maker_fee_rate'),
                'taker_fee_rate': position.get('taker_fee_rate'),
                'entry_fee_usdt': position.get('entry_fee_usdt'),
                'exit_fee_usdt': position.get('exit_fee_usdt'),
                'total_fees_usdt': position.get('total_fees_usdt'),
                'funding_rate_at_entry': position.get('funding_rate_at_entry'),
                'funding_rate_at_exit': position.get('funding_rate_at_exit'),
                'funding_paid_usdt': position.get('funding_paid_usdt'),
                'time_to_fill_entry_ms': position.get('time_to_fill_entry_ms'),
                'time_to_fill_exit_ms': position.get('time_to_fill_exit_ms'),
                'price_at_signal': position.get('price_at_signal'),
                'price_at_order_sent': position.get('price_at_order_sent'),
                'signal_to_fill_slippage_pct': position.get('signal_to_fill_slippage_pct'),
                'api_errors': position.get('api_errors'),
                'retry_count': position.get('retry_count', 0),
                'exchange_latency_ms': position.get('exchange_latency_ms'),
                'ws_latency_ms': position.get('ws_latency_ms'),
                'market_volatility_entry': position.get('market_volatility_entry'),
                'spread_at_entry_pct': position.get('spread_at_entry_pct'),
                'volume_24h_at_entry': position.get('volume_24h_at_entry'),
                'orderbook_imbalance_entry': position.get('orderbook_imbalance_entry'),
                'atr_at_entry': position.get('atr_at_entry'),
                'market_volatility_exit': position.get('market_volatility_exit'),
                'spread_at_exit_pct': position.get('spread_at_exit_pct'),
                'volume_24h_at_exit': position.get('volume_24h_at_exit'),
                'orderbook_imbalance_exit': position.get('orderbook_imbalance_exit'),
                'atr_at_exit': position.get('atr_at_exit'),
                'rsi_at_entry': position.get('rsi_at_entry'),
                'macd_at_entry': position.get('macd_at_entry'),
                'bb_position_entry': position.get('bb_position_entry'),
                'adx_at_entry': position.get('adx_at_entry'),
                'di_plus_entry': position.get('di_plus_entry'),
                'di_minus_entry': position.get('di_minus_entry'),
                'rsi_at_exit': position.get('rsi_at_exit'),
                'macd_at_exit': position.get('macd_at_exit'),
                'bb_position_exit': position.get('bb_position_exit'),
                'adx_at_exit': position.get('adx_at_exit'),
                'di_plus_exit': position.get('di_plus_exit'),
                'di_minus_exit': position.get('di_minus_exit'),
                'setup_score': position.get('setup_score'),
                'ml_confidence': position.get('ml_confidence'),
                'ml_prediction': position.get('ml_prediction'),
                'ml_features': position.get('ml_features'),
                'optimal_exit_price': position.get('optimal_exit_price'),
                'optimal_exit_time': position.get('optimal_exit_time'),
                'missed_profit_pct': position.get('missed_profit_pct'),
                'risk_reward_actual': position.get('risk_reward_actual'),
                'risk_reward_planned': position.get('risk_reward_planned'),
                'trade_notes': position.get('trade_notes'),
                'trade_tags': position.get('trade_tags', []),
                'user_rating': position.get('user_rating'),
                'metadata': position.get('metadata', {})
                # instance_port est ajouté automatiquement par analytics_database.py
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
