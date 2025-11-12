#!/usr/bin/env python3
"""
PostgreSQL DataLogger - Trade Cursor v7.0
Logging des scans, opportunités et trades vers PostgreSQL pour ML
"""

import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import uuid

try:
    import psycopg2
    from psycopg2.extras import execute_values, RealDictCursor
    from psycopg2.pool import ThreadedConnectionPool
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("⚠️ psycopg2 non installé - PostgreSQL DataLogger désactivé")

logger = logging.getLogger(__name__)


class PostgreSQLDataLogger:
    """
    DataLogger pour PostgreSQL
    
    Logge tous les scans, opportunités et trades dans PostgreSQL
    pour l'analyse ML et l'optimisation des paramètres.
    """
    
    def __init__(
        self,
        connection_string: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        min_conn: int = 1,
        max_conn: int = 5
    ):
        """
        Initialiser PostgreSQL DataLogger
        
        Args:
            connection_string: String de connexion PostgreSQL complète
            host: Host PostgreSQL (si connection_string non fourni)
            port: Port PostgreSQL (si connection_string non fourni)
            database: Nom de la base (si connection_string non fourni)
            user: Utilisateur (si connection_string non fourni)
            password: Mot de passe (si connection_string non fourni)
            min_conn: Nombre minimum de connexions dans le pool
            max_conn: Nombre maximum de connexions dans le pool
        """
        if not PSYCOPG2_AVAILABLE:
            logger.error("❌ psycopg2 non disponible - PostgreSQL DataLogger désactivé")
            self.enabled = False
            return
        
        self.enabled = True
        
        # Construire connection string si non fourni
        if connection_string:
            self.connection_string = connection_string
        else:
            # Utiliser variables d'environnement ou paramètres
            host = host or os.getenv('POSTGRES_HOST', 'localhost')
            port = port or int(os.getenv('POSTGRES_PORT', '5432'))
            database = database or os.getenv('POSTGRES_DB', 'trade_cursor_ml')
            user = user or os.getenv('POSTGRES_USER', 'postgres')
            password = password or os.getenv('POSTGRES_PASSWORD', '')
            
            self.connection_string = (
                f"host={host} port={port} dbname={database} "
                f"user={user} password={password}"
            )
        
        # Pool de connexions
        try:
            self.pool = ThreadedConnectionPool(
                min_conn, max_conn, self.connection_string
            )
            logger.info(f"✅ PostgreSQL DataLogger initialisé: {database}@{host}:{port}")
        except Exception as e:
            logger.error(f"❌ Erreur connexion PostgreSQL: {e}")
            self.enabled = False
            self.pool = None
    
    def _get_connection(self):
        """Obtenir une connexion du pool"""
        if not self.enabled or not self.pool:
            return None
        try:
            return self.pool.getconn()
        except Exception as e:
            logger.error(f"❌ Erreur obtention connexion: {e}")
            return None
    
    def _return_connection(self, conn):
        """Retourner une connexion au pool"""
        if self.pool and conn:
            try:
                self.pool.putconn(conn)
            except Exception as e:
                logger.error(f"❌ Erreur retour connexion: {e}")
    
    def _execute_query(self, query: str, params: tuple = None, fetch: bool = False):
        """
        Exécuter une requête SQL
        
        Args:
            query: Requête SQL
            params: Paramètres (tuple)
            fetch: Si True, retourner les résultats
        
        Returns:
            Résultats si fetch=True, sinon None
        """
        if not self.enabled:
            return None
        
        conn = self._get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            if fetch:
                results = cursor.fetchall()
                cursor.close()
                conn.commit()
                self._return_connection(conn)
                return results
            else:
                conn.commit()
                cursor.close()
                self._return_connection(conn)
                return True
        except Exception as e:
            logger.error(f"❌ Erreur exécution requête: {e}")
            logger.debug(f"Query: {query[:200]}...")
            if conn:
                conn.rollback()
                self._return_connection(conn)
            return None
    
    def get_or_create_session(self, session_id: Optional[str] = None) -> Optional[str]:
        """
        Obtenir ou créer une session de trading
        
        Args:
            session_id: UUID de session existante (optionnel)
        
        Returns:
            UUID de la session
        """
        if not self.enabled:
            return None
        
        # Si session_id fourni, vérifier qu'elle existe
        if session_id:
            query = "SELECT id FROM trading_sessions WHERE id = %s"
            result = self._execute_query(query, (session_id,), fetch=True)
            if result:
                return session_id
        
        # Créer nouvelle session
        new_session_id = str(uuid.uuid4())
        query = """
            INSERT INTO trading_sessions (id, start_time, config_snapshot)
            VALUES (%s, NOW(), %s)
            ON CONFLICT (id) DO NOTHING
            RETURNING id
        """
        config_snapshot = json.dumps({})  # TODO: Ajouter config réelle
        result = self._execute_query(query, (new_session_id, config_snapshot), fetch=True)
        
        if result:
            logger.debug(f"📊 Session créée: {new_session_id}")
            return new_session_id
        return None
    
    def log_scan(
        self,
        symbol: str,
        scan_data: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> Optional[int]:
        """
        Logger un scan dans scan_logs
        
        Args:
            symbol: Symbole de la paire
            scan_data: Données du scan (indicateurs, scores, etc.)
            session_id: UUID de la session (optionnel)
        
        Returns:
            ID du scan loggé ou None
        """
        if not self.enabled:
            return None
        
        # Obtenir ou créer session
        if not session_id:
            session_id = self.get_or_create_session()
        
        try:
            # Extraire les données du scan
            indicators_1m = scan_data.get('indicators_1m', {})
            indicators_5m = scan_data.get('indicators_5m', {})
            filters = scan_data.get('filters', {})
            scores = scan_data.get('scores', {})
            patterns = scan_data.get('patterns', {})
            market_data = scan_data.get('market_data', {})
            
            # Requête d'insertion
            query = """
                INSERT INTO scan_logs (
                    timestamp, session_id, symbol, scan_duration_ms,
                    price, spread_pct, book_depth, balance_score,
                    bid_vol, ask_vol, orderbook_imbalance_ratio,
                    
                    -- Indicateurs 1m
                    ema9_1m, ema21_1m, ema_diff_pct_1m,
                    rsi_1m, rsi_prev_1m,
                    macd_1m, macd_signal_1m, macd_hist_1m, macd_hist_prev_1m,
                    adx_1m, di_plus_1m, di_minus_1m, di_gap_1m,
                    atr_1m, atr_pct_1m,
                    bb_upper_1m, bb_middle_1m, bb_lower_1m, bb_width_1m,
                    bb_distance_to_lower_1m, bb_distance_to_upper_1m,
                    volume_1m, volume_avg_1m, volume_ratio_1m, volume_spike_1m,
                    
                    -- Indicateurs 5m
                    ema9_5m, ema21_5m, ema_diff_pct_5m,
                    rsi_5m, rsi_prev_5m,
                    macd_5m, macd_signal_5m, macd_hist_5m, macd_hist_prev_5m,
                    adx_5m, di_plus_5m, di_minus_5m, di_gap_5m,
                    atr_5m, atr_pct_5m,
                    bb_upper_5m, bb_middle_5m, bb_lower_5m, bb_width_5m,
                    bb_distance_to_lower_5m, bb_distance_to_upper_5m,
                    volume_5m, volume_avg_5m, volume_ratio_5m, volume_spike_5m,
                    
                    -- Filtres
                    snr_1m, snr_5m, snr_passed_1m, snr_passed_5m,
                    breakout_distance_1m, breakout_distance_5m,
                    breakout_passed_1m, breakout_passed_5m,
                    wick_ratio_1m, wick_ratio_5m, wick_passed_1m, wick_passed_5m,
                    atr_optimal_passed_1m, atr_optimal_passed_5m,
                    volume_filter_passed_1m, volume_filter_passed_5m,
                    
                    -- Confluence
                    use_confluence, confluence_met,
                    score_1m, score_5m, score_total,
                    score_long_1m, score_short_1m, score_long_5m, score_short_5m,
                    timeframes_aligned,
                    
                    -- Patterns
                    pattern_1m, pattern_multi_1m, pattern_5m, pattern_multi_5m,
                    
                    -- Trend
                    trend_timeframe, trend_direction, trend_strength, trend_bonus,
                    
                    -- Divergence
                    divergence_detected, divergence_type, divergence_bonus,
                    
                    -- Décision ML
                    is_opportunity, opportunity_direction, reject_reason, reject_reason_category,
                    
                    -- Params snapshot
                    params_snapshot
                )
                VALUES (
                    NOW(), %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
            """
            
            # Préparer les paramètres
            params = (
                session_id, symbol, scan_data.get('scan_duration_ms'),
                market_data.get('price'), market_data.get('spread_pct'),
                market_data.get('book_depth'), market_data.get('balance_score'),
                market_data.get('bid_vol'), market_data.get('ask_vol'),
                market_data.get('orderbook_imbalance_ratio'),
                
                # 1m
                indicators_1m.get('ema9'), indicators_1m.get('ema21'),
                indicators_1m.get('ema_diff_pct'),
                indicators_1m.get('rsi'), indicators_1m.get('rsi_prev'),
                indicators_1m.get('macd'), indicators_1m.get('macd_signal'),
                indicators_1m.get('macd_hist'), indicators_1m.get('macd_hist_prev'),
                indicators_1m.get('adx'), indicators_1m.get('di_plus'),
                indicators_1m.get('di_minus'), indicators_1m.get('di_gap'),
                indicators_1m.get('atr'), indicators_1m.get('atr_pct'),
                indicators_1m.get('bb_upper'), indicators_1m.get('bb_middle'),
                indicators_1m.get('bb_lower'), indicators_1m.get('bb_width'),
                indicators_1m.get('bb_distance_to_lower'), indicators_1m.get('bb_distance_to_upper'),
                indicators_1m.get('volume'), indicators_1m.get('volume_avg'),
                indicators_1m.get('volume_ratio'), indicators_1m.get('volume_spike'),
                
                # 5m
                indicators_5m.get('ema9'), indicators_5m.get('ema21'),
                indicators_5m.get('ema_diff_pct'),
                indicators_5m.get('rsi'), indicators_5m.get('rsi_prev'),
                indicators_5m.get('macd'), indicators_5m.get('macd_signal'),
                indicators_5m.get('macd_hist'), indicators_5m.get('macd_hist_prev'),
                indicators_5m.get('adx'), indicators_5m.get('di_plus'),
                indicators_5m.get('di_minus'), indicators_5m.get('di_gap'),
                indicators_5m.get('atr'), indicators_5m.get('atr_pct'),
                indicators_5m.get('bb_upper'), indicators_5m.get('bb_middle'),
                indicators_5m.get('bb_lower'), indicators_5m.get('bb_width'),
                indicators_5m.get('bb_distance_to_lower'), indicators_5m.get('bb_distance_to_upper'),
                indicators_5m.get('volume'), indicators_5m.get('volume_avg'),
                indicators_5m.get('volume_ratio'), indicators_5m.get('volume_spike'),
                
                # Filtres
                filters.get('snr_1m'), filters.get('snr_5m'),
                filters.get('snr_passed_1m'), filters.get('snr_passed_5m'),
                filters.get('breakout_distance_1m'), filters.get('breakout_distance_5m'),
                filters.get('breakout_passed_1m'), filters.get('breakout_passed_5m'),
                filters.get('wick_ratio_1m'), filters.get('wick_ratio_5m'),
                filters.get('wick_passed_1m'), filters.get('wick_passed_5m'),
                filters.get('atr_optimal_passed_1m'), filters.get('atr_optimal_passed_5m'),
                filters.get('volume_filter_passed_1m'), filters.get('volume_filter_passed_5m'),
                
                # Confluence
                scan_data.get('use_confluence'), scan_data.get('confluence_met'),
                scores.get('score_1m'), scores.get('score_5m'), scores.get('score_total'),
                scores.get('score_long_1m'), scores.get('score_short_1m'),
                scores.get('score_long_5m'), scores.get('score_short_5m'),
                scan_data.get('timeframes_aligned'),
                
                # Patterns
                patterns.get('pattern_1m'), patterns.get('pattern_multi_1m'),
                patterns.get('pattern_5m'), patterns.get('pattern_multi_5m'),
                
                # Trend
                scan_data.get('trend_timeframe', '15m'),
                scan_data.get('trend_direction'), scan_data.get('trend_strength'),
                scan_data.get('trend_bonus'),
                
                # Divergence
                scan_data.get('divergence_detected', False),
                scan_data.get('divergence_type'), scan_data.get('divergence_bonus', 0),
                
                # Décision
                scan_data.get('is_opportunity', False),
                scan_data.get('opportunity_direction'),
                scan_data.get('reject_reason'), scan_data.get('reject_reason_category'),
                
                # Params
                json.dumps(scan_data.get('params_snapshot', {}))
            )
            
            result = self._execute_query(query, params, fetch=True)
            if result:
                scan_id = result[0][0]
                logger.debug(f"📊 Scan loggé: {symbol} (ID: {scan_id})")
                return scan_id
            return None
            
        except Exception as e:
            logger.error(f"❌ Erreur logging scan {symbol}: {e}")
            return None
    
    def log_opportunity(
        self,
        scan_id: int,
        symbol: str,
        opportunity_data: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> Optional[int]:
        """
        Logger une opportunité dans opportunities
        
        Args:
            scan_id: ID du scan associé
            symbol: Symbole de la paire
            opportunity_data: Données de l'opportunité
            session_id: UUID de la session
        
        Returns:
            ID de l'opportunité loggée ou None
        """
        if not self.enabled:
            return None
        
        if not session_id:
            session_id = self.get_or_create_session()
        
        try:
            query = """
                INSERT INTO opportunities (
                    scan_log_id, session_id, symbol, timestamp,
                    status, direction, setup_score,
                    conditions_matched, entry_price, tp_price, sl_price,
                    size_usdt, risk_usdt, reward_risk_ratio
                )
                VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            
            params = (
                scan_id, session_id, symbol,
                opportunity_data.get('status', 'PENDING'),
                opportunity_data.get('direction'),
                opportunity_data.get('setup_score'),
                opportunity_data.get('conditions_matched', []),
                opportunity_data.get('entry_price'),
                opportunity_data.get('tp_price'),
                opportunity_data.get('sl_price'),
                opportunity_data.get('size_usdt'),
                opportunity_data.get('risk_usdt'),
                opportunity_data.get('reward_risk_ratio')
            )
            
            result = self._execute_query(query, params, fetch=True)
            if result:
                opp_id = result[0][0]
                logger.debug(f"📊 Opportunité loggée: {symbol} (ID: {opp_id})")
                return opp_id
            return None
            
        except Exception as e:
            logger.error(f"❌ Erreur logging opportunité {symbol}: {e}")
            return None
    
    def log_scan_error(
        self,
        symbol: str,
        error_type: str,
        error_message: str,
        error_details: Optional[Dict] = None,
        session_id: Optional[str] = None
    ) -> Optional[int]:
        """
        Logger une erreur de scan dans scan_errors
        
        Args:
            symbol: Symbole de la paire
            error_type: Type d'erreur (API_ERROR, TIMEOUT, etc.)
            error_message: Message d'erreur
            error_details: Détails supplémentaires (optionnel)
            session_id: UUID de la session
        
        Returns:
            ID de l'erreur loggée ou None
        """
        if not self.enabled:
            return None
        
        if not session_id:
            session_id = self.get_or_create_session()
        
        try:
            query = """
                INSERT INTO scan_errors (
                    timestamp, session_id, symbol,
                    error_type, error_message, error_stack, scan_context
                )
                VALUES (NOW(), %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            
            # Extraire stack trace si disponible
            error_stack = None
            if error_details:
                error_stack = error_details.get('stack') or error_details.get('error_stack')
            
            params = (
                session_id, symbol,
                error_type, error_message,
                error_stack,
                json.dumps(error_details or {})
            )
            
            result = self._execute_query(query, params, fetch=True)
            if result:
                error_id = result[0][0]
                logger.debug(f"📊 Erreur loggée: {symbol} - {error_type} (ID: {error_id})")
                return error_id
            return None
            
        except Exception as e:
            logger.error(f"❌ Erreur logging erreur scan {symbol}: {e}")
            return None
    
    def log_market_context(
        self,
        context_data: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> Optional[int]:
        """
        Logger le contexte marché dans market_context
        
        Args:
            context_data: Données du contexte marché
            session_id: UUID de la session
        
        Returns:
            ID du contexte loggé ou None
        """
        if not self.enabled:
            return None
        
        if not session_id:
            session_id = self.get_or_create_session()
        
        try:
            query = """
                INSERT INTO market_context (
                    timestamp, session_id,
                    hour_of_day, day_of_week,
                    btc_price, eth_price,
                    global_metrics, session_stats,
                    market_trend, market_volatility, fear_greed_index
                )
                VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            
            now = datetime.now()
            params = (
                session_id,
                now.hour,
                now.weekday(),
                context_data.get('btc_price'),
                context_data.get('eth_price'),
                json.dumps(context_data.get('global_metrics', {})),
                json.dumps(context_data.get('session_stats', {})),
                context_data.get('market_trend'),
                context_data.get('market_volatility'),
                context_data.get('fear_greed_index')
            )
            
            result = self._execute_query(query, params, fetch=True)
            if result:
                context_id = result[0][0]
                logger.debug(f"📊 Contexte marché loggé (ID: {context_id})")
                return context_id
            return None
            
        except Exception as e:
            logger.error(f"❌ Erreur logging contexte marché: {e}")
            return None
    
    def log_trade(
        self,
        trade_data: Dict[str, Any],
        opportunity_id: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> Optional[int]:
        """
        Logger un trade dans trades
        
        Args:
            trade_data: Données du trade
            opportunity_id: ID de l'opportunité associée (optionnel)
            session_id: UUID de la session
        
        Returns:
            ID du trade loggé ou None
        """
        if not self.enabled:
            return None
        
        if not session_id:
            session_id = self.get_or_create_session()
        
        try:
            now = datetime.now()
            timestamp_iso = now.isoformat()
            
            query = """
                INSERT INTO trades (
                    timestamp, session_id, opportunity_id, symbol,
                    direction, entry_price, exit_price,
                    size_usdt, gross_pnl_usdt, gross_pnl_pct,
                    net_pnl_usdt, net_pnl_pct,
                    fees, slippage, total_costs,
                    reason, duration_seconds,
                    tp_sl_mode, break_even_triggered,
                    trailing_stop_triggered, partial_tp_triggered,
                    tp_escalier_enabled, tp_escalier_levels_hit,
                    max_pnl_reached, min_pnl_reached,
                    entry_indicators_snapshot, exit_indicators_snapshot,
                    params_snapshot, is_backtest
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
            """
            
            params = (
                timestamp_iso, session_id, opportunity_id,
                trade_data.get('symbol'),
                trade_data.get('direction'),
                trade_data.get('entry_price'),
                trade_data.get('exit_price'),
                trade_data.get('size_usdt'),
                trade_data.get('gross_pnl_usdt', 0),
                trade_data.get('gross_pnl_pct', 0),
                trade_data.get('net_pnl_usdt', 0),
                trade_data.get('net_pnl_pct', 0),
                trade_data.get('fees', 0),
                trade_data.get('slippage', 0),
                trade_data.get('total_costs', 0),
                trade_data.get('reason'),
                trade_data.get('duration_seconds'),
                trade_data.get('tp_sl_mode'),
                trade_data.get('break_even_triggered', False),
                trade_data.get('trailing_stop_triggered', False),
                trade_data.get('partial_tp_triggered', False),
                trade_data.get('tp_escalier_enabled', False),
                trade_data.get('tp_escalier_levels_hit', []),
                trade_data.get('max_pnl_reached'),
                trade_data.get('min_pnl_reached'),
                json.dumps(trade_data.get('entry_indicators', {})),
                json.dumps(trade_data.get('exit_indicators', {})),
                json.dumps(trade_data.get('params_snapshot', {})),
                trade_data.get('is_backtest', False)
            )
            
            result = self._execute_query(query, params, fetch=True)
            if result:
                trade_id = result[0][0]
                logger.debug(f"📊 Trade loggé: {trade_data.get('symbol')} (ID: {trade_id})")
                return trade_id
            return None
            
        except Exception as e:
            logger.error(f"❌ Erreur logging trade {trade_data.get('symbol')}: {e}")
            return None
    
    def close(self):
        """Fermer le pool de connexions"""
        if self.pool:
            try:
                self.pool.closeall()
                logger.info("✅ Pool PostgreSQL fermé")
            except Exception as e:
                logger.error(f"❌ Erreur fermeture pool: {e}")

