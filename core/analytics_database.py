"""
🏗️ ANALYTICS DATABASE - Base de données complète pour monitoring et optimisation
Architecture proposée par l'utilisateur - Implémentation complète

Base de TOUT le système :
- Setups rejetés (comprendre pourquoi aucun trade)
- Setups validés (critères détaillés)
- Trades (extension table existante)
- Trade behavior (évolution seconde par seconde)

Multi-instances compatible
"""

import sqlite3
import json
import logging
import sys
import hashlib
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class AnalyticsDatabase:
    """
    Base de données analytics complète
    
    Tables :
    - setups_rejected : Tous les setups rejetés avec raisons
    - setups_validated : Tous les setups validés avec critères
    - trades : Trades (extension de l'existant)
    - trade_behavior : Évolution du trade (snapshots)
    """
    
    def __init__(self, db_path: Optional[str] = None, instance_port: Optional[int] = None):
        """
        Initialiser Analytics DB
        
        Args:
            db_path: Chemin DB (si None, auto-détecte instance)
            instance_port: Port instance (pour multi-instances)
        """
        if db_path is None:
            # Auto-détection port instance
            if instance_port is None:
                instance_port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
            db_path = f"analytics_instance_{instance_port}.db"
        
        self.db_path = db_path
        self.instance_port = instance_port or 5000
        self.conn = None
        self._init_database()
        
        logger.info(f"✅ Analytics DB initialisée: {self.db_path} (instance {self.instance_port})")
    
    def _init_database(self):
        """Initialiser base de données et toutes les tables"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Retourner dict
        
        cursor = self.conn.cursor()
        
        # ==================== TABLE 1: SETUPS REJECTED ====================
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS setups_rejected (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT,
                
                -- Raisons de rejet
                rejection_reason TEXT NOT NULL,
                rejection_category TEXT NOT NULL,
                rejection_details TEXT,
                
                -- Prix & Volume
                price REAL,
                volume_24h REAL,
                
                -- Indicateurs techniques
                ema_fast REAL,
                ema_slow REAL,
                rsi REAL,
                macd REAL,
                macd_signal REAL,
                macd_histogram REAL,
                atr REAL,
                atr5m REAL,
                adx REAL,
                di_plus REAL,
                di_minus REAL,
                
                -- Bollinger
                bb_upper REAL,
                bb_middle REAL,
                bb_lower REAL,
                bb_width REAL,
                
                -- Scores
                total_score REAL,
                min_score_required REAL,
                ema_score REAL,
                rsi_score REAL,
                macd_score REAL,
                adx_score REAL,
                volume_score REAL,
                pattern_score REAL,
                
                -- Seuils & Filtres
                spread REAL,
                spread_threshold REAL,
                orderbook_ratio REAL,
                orderbook_threshold REAL,
                
                -- Confluence
                confluence_1m BOOLEAN,
                confluence_5m BOOLEAN,
                confluence_required BOOLEAN,
                
                -- Corrélation
                correlation_detected BOOLEAN,
                correlation_group TEXT,
                correlation_penalty REAL,
                
                -- Recovery Mode
                recovery_mode_active BOOLEAN,
                loss_streak INTEGER,
                recovery_level INTEGER,
                
                -- Scalability
                scalability_score REAL,
                scalability_data TEXT,
                
                -- Metadata
                config_hash TEXT,
                instance_port INTEGER,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Index pour performances
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rejected_symbol ON setups_rejected(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rejected_reason ON setups_rejected(rejection_reason)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rejected_category ON setups_rejected(rejection_category)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rejected_timestamp ON setups_rejected(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rejected_config ON setups_rejected(config_hash)')
        
        # ==================== TABLE 2: SETUPS VALIDATED ====================
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS setups_validated (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                
                -- Prix & Entry
                price REAL NOT NULL,
                entry REAL NOT NULL,
                sl REAL NOT NULL,
                tp REAL NOT NULL,
                
                -- Position
                position_size REAL NOT NULL,
                capital REAL,
                
                -- Indicateurs (mêmes que setups_rejected)
                ema_fast REAL,
                ema_slow REAL,
                rsi REAL,
                macd REAL,
                macd_signal REAL,
                macd_histogram REAL,
                atr REAL,
                atr5m REAL,
                adx REAL,
                di_plus REAL,
                di_minus REAL,
                bb_upper REAL,
                bb_middle REAL,
                bb_lower REAL,
                
                -- Scores détaillés
                total_score REAL NOT NULL,
                ema_score REAL,
                rsi_score REAL,
                macd_score REAL,
                adx_score REAL,
                volume_score REAL,
                pattern_score REAL,
                
                -- Config TP/SL
                tp_sl_mode TEXT,
                fixed_tp_pct REAL,
                fixed_sl_pct REAL,
                atr_mult_tp REAL,
                atr_mult_sl REAL,
                
                -- TP Escalier
                tp_escalier_enabled BOOLEAN,
                tp_escalier_levels TEXT,
                
                -- Confluence
                confluence_1m BOOLEAN,
                confluence_5m BOOLEAN,
                
                -- Conditions détectées
                condition_types TEXT,
                
                -- Recovery Mode
                recovery_mode_active BOOLEAN,
                loss_streak INTEGER,
                recovery_level INTEGER,
                position_size_reduction REAL,
                
                -- Scalability
                scalability_score REAL,
                spread REAL,
                orderbook_ratio REAL,
                scalability_data TEXT,
                
                -- Metadata
                config_hash TEXT,
                instance_port INTEGER,
                trade_id INTEGER,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Index
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_validated_symbol ON setups_validated(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_validated_timestamp ON setups_validated(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_validated_trade_id ON setups_validated(trade_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_validated_config ON setups_validated(config_hash)')
        
        # ==================== TABLE 3: TRADES (Extension existante + LIVE TRADING) ====================
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry REAL NOT NULL,
                exit REAL NOT NULL,
                gross_pnl_pct REAL NOT NULL,
                gross_pnl_usdt REAL NOT NULL,
                net_pnl_pct REAL NOT NULL,
                net_pnl_usdt REAL NOT NULL,
                fees REAL DEFAULT 0,
                slippage REAL DEFAULT 0,
                total_costs REAL DEFAULT 0,
                reason TEXT,
                duration INTEGER,
                condition_types TEXT,
                
                -- Extensions proposées
                trading_mode TEXT,
                setup_id INTEGER,
                tp_sl_mode TEXT,
                break_even_triggered BOOLEAN,
                trailing_stop_triggered BOOLEAN,
                partial_tp_triggered BOOLEAN,
                
                -- TP Escalier
                tp_escalier_enabled BOOLEAN,
                tp_escalier_levels_hit TEXT,
                tp_escalier_profits TEXT,
                
                -- Comportement trade
                max_pnl_reached REAL,
                min_pnl_reached REAL,
                max_drawdown_intra REAL,
                
                -- Early Invalidation
                early_invalidation_threshold REAL,
                early_invalidation_elapsed REAL,
                
                -- Trailing Stop
                trailing_stop_updates TEXT,
                
                -- Backtesting & ML
                is_backtest BOOLEAN DEFAULT FALSE,
                backtest_id TEXT,
                config_hash TEXT,
                session_id TEXT,
                
                -- ==================== 🔥 LIVE TRADING COLUMNS ====================
                -- Mode & Type
                is_live_trade BOOLEAN DEFAULT FALSE,
                is_dry_run BOOLEAN DEFAULT TRUE,
                live_execution_mode TEXT,
                
                -- Ordre d'entrée
                entry_order_id TEXT,
                entry_order_type TEXT,
                entry_requested_price REAL,
                entry_fill_price REAL,
                entry_slippage_pct REAL,
                entry_latency_ms INTEGER,
                entry_timestamp TEXT,
                entry_api_response TEXT,
                
                -- Ordre de sortie
                exit_order_id TEXT,
                exit_order_type TEXT,
                exit_requested_price REAL,
                exit_fill_price REAL,
                exit_slippage_pct REAL,
                exit_latency_ms INTEGER,
                exit_timestamp TEXT,
                exit_api_response TEXT,
                
                -- Futures / Levier
                leverage_used INTEGER DEFAULT 1,
                margin_mode TEXT DEFAULT 'isolated',
                position_size_usdt REAL,
                position_size_contracts REAL,
                liquidation_price REAL,
                margin_used REAL,
                
                -- Frais détaillés
                maker_fee_rate REAL,
                taker_fee_rate REAL,
                entry_fee_usdt REAL,
                exit_fee_usdt REAL,
                total_fees_usdt REAL,
                funding_rate_at_entry REAL,
                funding_rate_at_exit REAL,
                funding_paid_usdt REAL,
                
                -- Performance temps réel
                time_to_fill_entry_ms INTEGER,
                time_to_fill_exit_ms INTEGER,
                price_at_signal REAL,
                price_at_order_sent REAL,
                signal_to_fill_slippage_pct REAL,
                
                -- API & Réseau
                api_errors TEXT,
                retry_count INTEGER DEFAULT 0,
                exchange_latency_ms INTEGER,
                ws_latency_ms INTEGER,
                
                -- Contexte marché à l'entrée
                market_volatility_entry REAL,
                spread_at_entry_pct REAL,
                volume_24h_at_entry REAL,
                orderbook_imbalance_entry REAL,
                atr_at_entry REAL,
                
                -- Contexte marché à la sortie
                market_volatility_exit REAL,
                spread_at_exit_pct REAL,
                volume_24h_at_exit REAL,
                orderbook_imbalance_exit REAL,
                atr_at_exit REAL,
                
                -- Indicateurs techniques à l'entrée
                rsi_at_entry REAL,
                macd_at_entry REAL,
                bb_position_entry REAL,
                adx_at_entry REAL,
                di_plus_entry REAL,
                di_minus_entry REAL,
                
                -- Indicateurs techniques à la sortie
                rsi_at_exit REAL,
                macd_at_exit REAL,
                bb_position_exit REAL,
                adx_at_exit REAL,
                di_plus_exit REAL,
                di_minus_exit REAL,
                
                -- Score & ML
                setup_score REAL,
                ml_confidence REAL,
                ml_prediction TEXT,
                ml_features TEXT,
                
                -- Analyse post-trade
                optimal_exit_price REAL,
                optimal_exit_time TEXT,
                missed_profit_pct REAL,
                risk_reward_actual REAL,
                risk_reward_planned REAL,
                
                -- Notes & Tags
                trade_notes TEXT,
                trade_tags TEXT,
                user_rating INTEGER,
                
                -- ==================== END LIVE TRADING ====================
                
                -- Metadata
                instance_port INTEGER,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 🔥 MIGRATION: Assurer compatibilité avec anciennes DB (ajout colonnes manquantes)
        # (CREATE TABLE IF NOT EXISTS ne modifie pas un schéma existant)
        try:
            cursor.execute("PRAGMA table_info(trades)")
            existing_cols = {row['name'] for row in cursor.fetchall()}

            if 'is_live_trade' not in existing_cols:
                cursor.execute("ALTER TABLE trades ADD COLUMN is_live_trade BOOLEAN DEFAULT 0")
            if 'is_dry_run' not in existing_cols:
                cursor.execute("ALTER TABLE trades ADD COLUMN is_dry_run BOOLEAN DEFAULT 1")
            if 'leverage_used' not in existing_cols:
                cursor.execute("ALTER TABLE trades ADD COLUMN leverage_used INTEGER DEFAULT 1")
            if 'entry_order_id' not in existing_cols:
                cursor.execute("ALTER TABLE trades ADD COLUMN entry_order_id TEXT")
        except Exception as e:
            logger.debug(f"Migration schéma trades ignorée (non bloquant): {e}")
        
        # Index
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_mode ON trades(trading_mode)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_backtest ON trades(backtest_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_config ON trades(config_hash)')
        # 🔥 Index pour live trading
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_is_live ON trades(is_live_trade)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_is_dry_run ON trades(is_dry_run)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_leverage ON trades(leverage_used)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_entry_order ON trades(entry_order_id)')
        
        # ==================== TABLE 4: TRADE BEHAVIOR ====================
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_behavior (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id INTEGER NOT NULL,
                
                -- Timestamp
                timestamp TEXT NOT NULL,
                elapsed_seconds INTEGER NOT NULL,
                
                -- Prix & PnL
                current_price REAL NOT NULL,
                pnl_pct REAL NOT NULL,
                pnl_usdt REAL NOT NULL,
                
                -- SL/TP actuel
                current_sl REAL NOT NULL,
                current_tp REAL NOT NULL,
                
                -- États
                break_even_set BOOLEAN,
                trailing_active BOOLEAN,
                partial_tp_sold BOOLEAN,
                
                -- TP Escalier
                tp_escalier_current_level INTEGER,
                tp_escalier_size_remaining REAL,
                
                -- Metadata
                instance_port INTEGER,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (trade_id) REFERENCES trades(id)
            )
        ''')
        
        # Index
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_behavior_trade_id ON trade_behavior(trade_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_behavior_timestamp ON trade_behavior(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_behavior_elapsed ON trade_behavior(elapsed_seconds)')
        
        self.conn.commit()
    
    def _calculate_config_hash(self, config: Dict) -> str:
        """Calculer hash de configuration (pour comparer configs)"""
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()[:16]
    
    # ==================== SETUPS REJECTED ====================
    
    def insert_rejected_setup(self, setup: Dict) -> int:
        """
        Insérer un setup rejeté
        
        Args:
            setup: Dictionnaire avec tous les champs
        
        Returns:
            ID du setup inséré
        """
        cursor = self.conn.cursor()
        
        # Calculer config hash si config fournie
        config_hash = None
        if 'config' in setup:
            config_hash = self._calculate_config_hash(setup['config'])
        
        metadata_json = json.dumps(setup.get('metadata', {}))
        scalability_data_json = json.dumps(setup.get('scalability_data', {}))
        
        cursor.execute('''
            INSERT INTO setups_rejected (
                timestamp, symbol, direction, rejection_reason, rejection_category, rejection_details,
                price, volume_24h,
                ema_fast, ema_slow, rsi, macd, macd_signal, macd_histogram,
                atr, atr5m, adx, di_plus, di_minus,
                bb_upper, bb_middle, bb_lower, bb_width,
                total_score, min_score_required, ema_score, rsi_score, macd_score, adx_score, volume_score, pattern_score,
                spread, spread_threshold, orderbook_ratio, orderbook_threshold,
                confluence_1m, confluence_5m, confluence_required,
                correlation_detected, correlation_group, correlation_penalty,
                recovery_mode_active, loss_streak, recovery_level,
                scalability_score, scalability_data,
                config_hash, instance_port, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            setup.get('timestamp', datetime.now().isoformat()),
            setup.get('symbol'),
            setup.get('direction'),
            setup.get('rejection_reason'),
            setup.get('rejection_category'),
            setup.get('rejection_details'),
            setup.get('price'),
            setup.get('volume_24h'),
            setup.get('ema_fast'),
            setup.get('ema_slow'),
            setup.get('rsi'),
            setup.get('macd'),
            setup.get('macd_signal'),
            setup.get('macd_histogram'),
            setup.get('atr'),
            setup.get('atr5m'),
            setup.get('adx'),
            setup.get('di_plus'),
            setup.get('di_minus'),
            setup.get('bb_upper'),
            setup.get('bb_middle'),
            setup.get('bb_lower'),
            setup.get('bb_width'),
            setup.get('total_score'),
            setup.get('min_score_required'),
            setup.get('ema_score'),
            setup.get('rsi_score'),
            setup.get('macd_score'),
            setup.get('adx_score'),
            setup.get('volume_score'),
            setup.get('pattern_score'),
            setup.get('spread'),
            setup.get('spread_threshold'),
            setup.get('orderbook_ratio'),
            setup.get('orderbook_threshold'),
            setup.get('confluence_1m'),
            setup.get('confluence_5m'),
            setup.get('confluence_required'),
            setup.get('correlation_detected'),
            setup.get('correlation_group'),
            setup.get('correlation_penalty'),
            setup.get('recovery_mode_active'),
            setup.get('loss_streak'),
            setup.get('recovery_level'),
            setup.get('scalability_score'),
            scalability_data_json,
            config_hash,
            self.instance_port,
            metadata_json
        ))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def get_rejected_setups(
        self, 
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        rejection_category: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Récupérer setups rejetés avec filtres"""
        cursor = self.conn.cursor()
        
        query = "SELECT * FROM setups_rejected WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if start_date:
            query += " AND date(timestamp) >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date(timestamp) <= ?"
            params.append(end_date)
        if rejection_category:
            query += " AND rejection_category = ?"
            params.append(rejection_category)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_rejection_summary(self) -> Dict:
        """Statistiques globales rejets"""
        cursor = self.conn.cursor()
        
        # Total par catégorie
        cursor.execute('''
            SELECT rejection_category, COUNT(*) as count
            FROM setups_rejected
            GROUP BY rejection_category
            ORDER BY count DESC
        ''')
        by_category = {row['rejection_category']: row['count'] for row in cursor.fetchall()}
        
        # Top 10 raisons
        cursor.execute('''
            SELECT rejection_reason, COUNT(*) as count
            FROM setups_rejected
            GROUP BY rejection_reason
            ORDER BY count DESC
            LIMIT 10
        ''')
        by_reason = {row['rejection_reason']: row['count'] for row in cursor.fetchall()}
        
        # Top 10 symboles
        cursor.execute('''
            SELECT symbol, COUNT(*) as count
            FROM setups_rejected
            GROUP BY symbol
            ORDER BY count DESC
            LIMIT 10
        ''')
        by_symbol = {row['symbol']: row['count'] for row in cursor.fetchall()}
        
        return {
            'by_category': by_category,
            'by_reason': by_reason,
            'by_symbol': by_symbol
        }
    
    # ==================== SETUPS VALIDATED ====================
    
    def insert_validated_setup(self, setup: Dict) -> int:
        """Insérer un setup validé"""
        cursor = self.conn.cursor()
        
        config_hash = None
        if 'config' in setup:
            config_hash = self._calculate_config_hash(setup['config'])
        
        condition_types_json = json.dumps(setup.get('condition_types', []))
        tp_escalier_levels_json = json.dumps(setup.get('tp_escalier_levels', []))
        scalability_data_json = json.dumps(setup.get('scalability_data', {}))
        metadata_json = json.dumps(setup.get('metadata', {}))
        
        cursor.execute('''
            INSERT INTO setups_validated (
                timestamp, symbol, direction, price, entry, sl, tp,
                position_size, capital,
                ema_fast, ema_slow, rsi, macd, macd_signal, macd_histogram, atr, atr5m, adx,
                di_plus, di_minus, bb_upper, bb_middle, bb_lower,
                total_score, ema_score, rsi_score, macd_score, adx_score, volume_score, pattern_score,
                tp_sl_mode, fixed_tp_pct, fixed_sl_pct, atr_mult_tp, atr_mult_sl,
                tp_escalier_enabled, tp_escalier_levels,
                confluence_1m, confluence_5m, condition_types,
                recovery_mode_active, loss_streak, recovery_level, position_size_reduction,
                scalability_score, spread, orderbook_ratio, scalability_data,
                config_hash, instance_port, trade_id, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            setup.get('timestamp', datetime.now().isoformat()),
            setup.get('symbol'),
            setup.get('direction'),
            setup.get('price'),
            setup.get('entry'),
            setup.get('sl'),
            setup.get('tp'),
            setup.get('position_size'),
            setup.get('capital'),
            setup.get('ema_fast'),
            setup.get('ema_slow'),
            setup.get('rsi'),
            setup.get('macd'),
            setup.get('macd_signal'),
            setup.get('macd_histogram'),
            setup.get('atr'),
            setup.get('atr5m'),
            setup.get('adx'),
            setup.get('di_plus'),
            setup.get('di_minus'),
            setup.get('bb_upper'),
            setup.get('bb_middle'),
            setup.get('bb_lower'),
            setup.get('total_score'),
            setup.get('ema_score'),
            setup.get('rsi_score'),
            setup.get('macd_score'),
            setup.get('adx_score'),
            setup.get('volume_score'),
            setup.get('pattern_score'),
            setup.get('tp_sl_mode'),
            setup.get('fixed_tp_pct'),
            setup.get('fixed_sl_pct'),
            setup.get('atr_mult_tp'),
            setup.get('atr_mult_sl'),
            setup.get('tp_escalier_enabled'),
            tp_escalier_levels_json,
            setup.get('confluence_1m'),
            setup.get('confluence_5m'),
            condition_types_json,
            setup.get('recovery_mode_active'),
            setup.get('loss_streak'),
            setup.get('recovery_level'),
            setup.get('position_size_reduction'),
            setup.get('scalability_score'),
            setup.get('spread'),
            setup.get('orderbook_ratio'),
            scalability_data_json,
            config_hash,
            self.instance_port,
            setup.get('trade_id'),
            metadata_json
        ))
        
        self.conn.commit()
        return cursor.lastrowid
    
    # ==================== TRADES ====================
    
    def insert_trade(self, trade: Dict) -> int:
        """Insérer un trade (extension table existante + LIVE TRADING)"""
        cursor = self.conn.cursor()
        
        config_hash = None
        if 'config' in trade:
            config_hash = self._calculate_config_hash(trade['config'])
        
        # JSON fields
        condition_types_json = json.dumps(trade.get('condition_types', []))
        tp_escalier_levels_hit_json = json.dumps(trade.get('tp_escalier_levels_hit', []))
        tp_escalier_profits_json = json.dumps(trade.get('tp_escalier_profits', []))
        trailing_stop_updates_json = json.dumps(trade.get('trailing_stop_updates', []))
        metadata_json = json.dumps(trade.get('metadata', {}))
        # 🔥 Live trading JSON fields
        entry_api_response_json = json.dumps(trade.get('entry_api_response', {}))
        exit_api_response_json = json.dumps(trade.get('exit_api_response', {}))
        api_errors_json = json.dumps(trade.get('api_errors', []))
        ml_features_json = json.dumps(trade.get('ml_features', {}))
        trade_tags_json = json.dumps(trade.get('trade_tags', []))
        
        cursor.execute('''
            INSERT INTO trades (
                timestamp, date, time, symbol, direction, entry, exit,
                gross_pnl_pct, gross_pnl_usdt, net_pnl_pct, net_pnl_usdt,
                fees, slippage, total_costs, reason, duration, condition_types,
                trading_mode, setup_id, tp_sl_mode,
                break_even_triggered, trailing_stop_triggered, partial_tp_triggered,
                tp_escalier_enabled, tp_escalier_levels_hit, tp_escalier_profits,
                max_pnl_reached, min_pnl_reached, max_drawdown_intra,
                early_invalidation_threshold, early_invalidation_elapsed,
                trailing_stop_updates,
                is_backtest, backtest_id, config_hash, session_id,
                -- 🔥 LIVE TRADING COLUMNS
                is_live_trade, is_dry_run, live_execution_mode,
                entry_order_id, entry_order_type, entry_requested_price, entry_fill_price,
                entry_slippage_pct, entry_latency_ms, entry_timestamp, entry_api_response,
                exit_order_id, exit_order_type, exit_requested_price, exit_fill_price,
                exit_slippage_pct, exit_latency_ms, exit_timestamp, exit_api_response,
                leverage_used, margin_mode, position_size_usdt, position_size_contracts,
                liquidation_price, margin_used,
                maker_fee_rate, taker_fee_rate, entry_fee_usdt, exit_fee_usdt, total_fees_usdt,
                funding_rate_at_entry, funding_rate_at_exit, funding_paid_usdt,
                time_to_fill_entry_ms, time_to_fill_exit_ms, price_at_signal, price_at_order_sent,
                signal_to_fill_slippage_pct, api_errors, retry_count, exchange_latency_ms, ws_latency_ms,
                market_volatility_entry, spread_at_entry_pct, volume_24h_at_entry, orderbook_imbalance_entry, atr_at_entry,
                market_volatility_exit, spread_at_exit_pct, volume_24h_at_exit, orderbook_imbalance_exit, atr_at_exit,
                rsi_at_entry, macd_at_entry, bb_position_entry, adx_at_entry, di_plus_entry, di_minus_entry,
                rsi_at_exit, macd_at_exit, bb_position_exit, adx_at_exit, di_plus_exit, di_minus_exit,
                setup_score, ml_confidence, ml_prediction, ml_features,
                optimal_exit_price, optimal_exit_time, missed_profit_pct, risk_reward_actual, risk_reward_planned,
                trade_notes, trade_tags, user_rating,
                instance_port, metadata
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        ''', (
            # Base columns
            trade.get('timestamp'),
            trade.get('date'),
            trade.get('time'),
            trade.get('symbol'),
            trade.get('direction'),
            trade.get('entry'),
            trade.get('exit'),
            trade.get('gross_pnl_pct'),
            trade.get('gross_pnl_usdt'),
            trade.get('net_pnl_pct'),
            trade.get('net_pnl_usdt'),
            trade.get('fees', 0),
            trade.get('slippage', 0),
            trade.get('total_costs', 0),
            trade.get('reason'),
            trade.get('duration'),
            condition_types_json,
            trade.get('trading_mode', 'LIVE'),
            trade.get('setup_id'),
            trade.get('tp_sl_mode'),
            trade.get('break_even_triggered'),
            trade.get('trailing_stop_triggered'),
            trade.get('partial_tp_triggered'),
            trade.get('tp_escalier_enabled'),
            tp_escalier_levels_hit_json,
            tp_escalier_profits_json,
            trade.get('max_pnl_reached'),
            trade.get('min_pnl_reached'),
            trade.get('max_drawdown_intra'),
            trade.get('early_invalidation_threshold'),
            trade.get('early_invalidation_elapsed'),
            trailing_stop_updates_json,
            trade.get('is_backtest', False),
            trade.get('backtest_id'),
            config_hash,
            trade.get('session_id'),
            # 🔥 LIVE TRADING VALUES
            trade.get('is_live_trade', False),
            trade.get('is_dry_run', True),
            trade.get('live_execution_mode'),
            trade.get('entry_order_id'),
            trade.get('entry_order_type'),
            trade.get('entry_requested_price'),
            trade.get('entry_fill_price'),
            trade.get('entry_slippage_pct'),
            trade.get('entry_latency_ms'),
            trade.get('entry_timestamp'),
            entry_api_response_json,
            trade.get('exit_order_id'),
            trade.get('exit_order_type'),
            trade.get('exit_requested_price'),
            trade.get('exit_fill_price'),
            trade.get('exit_slippage_pct'),
            trade.get('exit_latency_ms'),
            trade.get('exit_timestamp'),
            exit_api_response_json,
            trade.get('leverage_used', 1),
            trade.get('margin_mode', 'isolated'),
            trade.get('position_size_usdt'),
            trade.get('position_size_contracts'),
            trade.get('liquidation_price'),
            trade.get('margin_used'),
            trade.get('maker_fee_rate'),
            trade.get('taker_fee_rate'),
            trade.get('entry_fee_usdt'),
            trade.get('exit_fee_usdt'),
            trade.get('total_fees_usdt'),
            trade.get('funding_rate_at_entry'),
            trade.get('funding_rate_at_exit'),
            trade.get('funding_paid_usdt'),
            trade.get('time_to_fill_entry_ms'),
            trade.get('time_to_fill_exit_ms'),
            trade.get('price_at_signal'),
            trade.get('price_at_order_sent'),
            trade.get('signal_to_fill_slippage_pct'),
            api_errors_json,
            trade.get('retry_count', 0),
            trade.get('exchange_latency_ms'),
            trade.get('ws_latency_ms'),
            trade.get('market_volatility_entry'),
            trade.get('spread_at_entry_pct'),
            trade.get('volume_24h_at_entry'),
            trade.get('orderbook_imbalance_entry'),
            trade.get('atr_at_entry'),
            trade.get('market_volatility_exit'),
            trade.get('spread_at_exit_pct'),
            trade.get('volume_24h_at_exit'),
            trade.get('orderbook_imbalance_exit'),
            trade.get('atr_at_exit'),
            trade.get('rsi_at_entry'),
            trade.get('macd_at_entry'),
            trade.get('bb_position_entry'),
            trade.get('adx_at_entry'),
            trade.get('di_plus_entry'),
            trade.get('di_minus_entry'),
            trade.get('rsi_at_exit'),
            trade.get('macd_at_exit'),
            trade.get('bb_position_exit'),
            trade.get('adx_at_exit'),
            trade.get('di_plus_exit'),
            trade.get('di_minus_exit'),
            trade.get('setup_score'),
            trade.get('ml_confidence'),
            trade.get('ml_prediction'),
            ml_features_json,
            trade.get('optimal_exit_price'),
            trade.get('optimal_exit_time'),
            trade.get('missed_profit_pct'),
            trade.get('risk_reward_actual'),
            trade.get('risk_reward_planned'),
            trade.get('trade_notes'),
            trade_tags_json,
            trade.get('user_rating'),
            self.instance_port,
            metadata_json
        ))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def get_trades(
        self,
        trading_mode: Optional[str] = None,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        backtest_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Récupérer trades avec filtres"""
        cursor = self.conn.cursor()
        
        query = "SELECT * FROM trades WHERE 1=1"
        params = []
        
        if trading_mode:
            query += " AND trading_mode = ?"
            params.append(trading_mode)
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        if backtest_id:
            query += " AND backtest_id = ?"
            params.append(backtest_id)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        trades = []
        for row in cursor.fetchall():
            trade = dict(row)
            # 🔥 FIX: S'assurer que duration_seconds est présent si duration existe
            if 'duration' in trade and trade.get('duration') is not None and 'duration_seconds' not in trade:
                trade['duration_seconds'] = trade['duration']
            trades.append(trade)
        return trades
    
    def clear_all_trades(self):
        """Vider tous les trades de la base de données (pour réinitialiser les stats au démarrage)"""
        cursor = self.conn.cursor()
        try:
            # Supprimer tous les trades
            cursor.execute('DELETE FROM trades')
            # Supprimer aussi les comportements de trades associés
            cursor.execute('DELETE FROM trade_behavior')
            # Supprimer les setups validés associés
            cursor.execute('DELETE FROM setups_validated WHERE trade_id IS NOT NULL')
            self.conn.commit()
            logger.info("✅ Tous les trades ont été supprimés de la base de données")
        except Exception as e:
            logger.error(f"❌ Erreur lors de la suppression des trades: {e}")
            self.conn.rollback()
            raise
    
    # ==================== TRADE BEHAVIOR ====================
    
    def insert_trade_behavior(self, behavior: Dict) -> int:
        """Insérer snapshot comportement trade"""
        cursor = self.conn.cursor()
        
        metadata_json = json.dumps(behavior.get('metadata', {}))
        
        cursor.execute('''
            INSERT INTO trade_behavior (
                trade_id, timestamp, elapsed_seconds,
                current_price, pnl_pct, pnl_usdt,
                current_sl, current_tp,
                break_even_set, trailing_active, partial_tp_sold,
                tp_escalier_current_level, tp_escalier_size_remaining,
                instance_port, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            behavior.get('trade_id'),
            behavior.get('timestamp', datetime.now().isoformat()),
            behavior.get('elapsed_seconds'),
            behavior.get('current_price'),
            behavior.get('pnl_pct'),
            behavior.get('pnl_usdt'),
            behavior.get('current_sl'),
            behavior.get('current_tp'),
            behavior.get('break_even_set'),
            behavior.get('trailing_active'),
            behavior.get('partial_tp_sold'),
            behavior.get('tp_escalier_current_level'),
            behavior.get('tp_escalier_size_remaining'),
            self.instance_port,
            metadata_json
        ))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def get_trade_behavior(self, trade_id: int) -> List[Dict]:
        """Récupérer tous les snapshots d'un trade"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            SELECT * FROM trade_behavior
            WHERE trade_id = ?
            ORDER BY elapsed_seconds ASC
        ''', (trade_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_trade_behavior_summary(self, trade_id: int) -> Dict:
        """Résumé comportement trade avec métriques"""
        snapshots = self.get_trade_behavior(trade_id)
        
        if not snapshots:
            return {}
        
        pnls = [s['pnl_pct'] for s in snapshots]
        max_pnl = max(pnls)
        min_pnl = min(pnls)
        max_drawdown = max_pnl - min_pnl if max_pnl > 0 else 0
        
        return {
            'snapshots': snapshots,
            'total_snapshots': len(snapshots),
            'max_pnl': max_pnl,
            'min_pnl': min_pnl,
            'max_drawdown_intra': max_drawdown,
            'avg_pnl': sum(pnls) / len(pnls) if pnls else 0
        }
    
    # ==================== ANALYTICS & STATS ====================
    
    def get_global_stats(self) -> Dict:
        """Statistiques globales toutes tables"""
        cursor = self.conn.cursor()
        
        # Count par table
        cursor.execute("SELECT COUNT(*) as count FROM setups_rejected")
        total_rejected = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM setups_validated")
        total_validated = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM trades")
        total_trades = cursor.fetchone()['count']
        
        # Taux validation
        total_setups = total_rejected + total_validated
        validation_rate = (total_validated / total_setups * 100) if total_setups > 0 else 0
        
        # Winrate
        cursor.execute("SELECT COUNT(*) as count FROM trades WHERE net_pnl_pct > 0")
        wins = cursor.fetchone()['count']
        winrate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        return {
            'total_rejected': total_rejected,
            'total_validated': total_validated,
            'total_trades': total_trades,
            'validation_rate': validation_rate,
            'winrate': winrate
        }
    
    def close(self):
        """Fermer connexion DB"""
        if self.conn:
            self.conn.close()
            logger.info(f"🔒 Analytics DB fermée: {self.db_path}")


# ==================== FONCTIONS HELPER ====================

def get_analytics_db(instance_port: Optional[int] = None) -> AnalyticsDatabase:
    """
    Helper pour obtenir instance Analytics DB
    
    Args:
        instance_port: Port instance (auto-détecte si None)
    
    Returns:
        Instance AnalyticsDatabase
    """
    return AnalyticsDatabase(instance_port=instance_port)

