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
from collections import deque
import threading

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
        max_conn: int = 5,
        batch_size: int = 50,
        batch_flush_interval: float = 5.0
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
            batch_size: Taille du buffer pour batch inserts (défaut: 50)
            batch_flush_interval: Intervalle en secondes pour flush automatique (défaut: 5.0)
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
            return
        
        # 🔥 PHASE 3: Batch inserts - Buffers pour optimiser les insertions
        self.batch_size = batch_size
        self.batch_flush_interval = batch_flush_interval
        self.scan_buffer: deque = deque(maxlen=batch_size * 2)  # Buffer pour scans
        self.opportunity_buffer: deque = deque(maxlen=batch_size * 2)  # Buffer pour opportunités
        self.buffer_lock = threading.Lock()
        self.last_flush_time = datetime.now()
    
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
        # Préparer config_snapshot complet (toutes les variables de configuration)
        try:
            from config import (
                TRADING_CONFIG, RISK_CONFIG, CONDITION_WEIGHTS,
                TREND_BONUS_CONFIG, RETRY_CONFIG, CIRCUIT_BREAKER_CONFIG,
                WEBSOCKET_CONFIG
            )
            config_snapshot_dict = {}
            # Copier TRADING_CONFIG
            if TRADING_CONFIG:
                config_snapshot_dict.update(TRADING_CONFIG.copy())
            # Ajouter les variables définies séparément
            config_snapshot_dict['RISK_CONFIG'] = RISK_CONFIG
            config_snapshot_dict['CONDITION_WEIGHTS'] = CONDITION_WEIGHTS
            config_snapshot_dict['TREND_BONUS_CONFIG'] = TREND_BONUS_CONFIG
            config_snapshot_dict['RETRY_CONFIG'] = RETRY_CONFIG
            config_snapshot_dict['CIRCUIT_BREAKER_CONFIG'] = CIRCUIT_BREAKER_CONFIG
            config_snapshot_dict['WEBSOCKET_CONFIG'] = WEBSOCKET_CONFIG
            config_snapshot = json.dumps(config_snapshot_dict)
        except Exception as e:
            logger.warning(f"⚠️ Erreur préparation config_snapshot pour session: {e}")
            config_snapshot = json.dumps({})
        result = self._execute_query(query, (new_session_id, config_snapshot), fetch=True)
        
        if result:
            logger.debug(f"📊 Session créée: {new_session_id}")
            return new_session_id
        return None
    
    def log_scan(
        self,
        symbol: str,
        scan_data: Dict[str, Any],
        session_id: Optional[str] = None,
        use_batch: bool = True
    ) -> Optional[int]:
        """
        Logger un scan dans scan_logs
        
        Args:
            symbol: Symbole de la paire
            scan_data: Données du scan (indicateurs, scores, etc.)
            session_id: UUID de la session (optionnel)
            use_batch: Si True, utiliser batch insert (défaut: True)
        
        Returns:
            ID du scan loggé ou None (None si batch mode)
        """
        if not self.enabled:
            return None
        
        # Obtenir ou créer session
        if not session_id:
            session_id = self.get_or_create_session()
        
        # 🔥 PHASE 3: Utiliser batch insert si activé
        if use_batch:
            with self.buffer_lock:
                self.scan_buffer.append({
                    'session_id': session_id,
                    'symbol': symbol,
                    'scan_data': scan_data
                })
            # Flush si buffer plein
            self._flush_buffers()
            return None  # Pas d'ID immédiat en mode batch
        
        # Mode direct (fallback)
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
        session_id: Optional[str] = None,
        use_batch: bool = True
    ) -> Optional[int]:
        """
        Logger une opportunité dans opportunities
        
        Args:
            scan_id: ID du scan associé
            symbol: Symbole de la paire
            opportunity_data: Données de l'opportunité
            session_id: UUID de la session
            use_batch: Si True, utiliser batch insert (défaut: True)
        
        Returns:
            ID de l'opportunité loggée ou None (None si batch mode)
        """
        if not self.enabled:
            return None
        
        if not session_id:
            session_id = self.get_or_create_session()
        
        # 🔥 PHASE 3: Utiliser batch insert si activé
        if use_batch:
            with self.buffer_lock:
                self.opportunity_buffer.append({
                    'scan_id': scan_id,
                    'session_id': session_id,
                    'symbol': symbol,
                    'opportunity_data': opportunity_data
                })
            # Flush si buffer plein
            self._flush_buffers()
            return None  # Pas d'ID immédiat en mode batch
        
        # Mode direct (fallback)
        try:
            query = """
                INSERT INTO opportunities (
                    scan_log_id, session_id, symbol, timestamp,
                    status, direction, setup_score,
                    conditions_matched, entry_suggested, tp_suggested, sl_suggested,
                    tp_sl_mode
                )
                VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            
            # Convertir conditions_matched en liste si nécessaire
            conditions_matched = opportunity_data.get('conditions_matched', [])
            if isinstance(conditions_matched, dict):
                conditions_matched = list(conditions_matched.keys()) if conditions_matched else []
            elif not isinstance(conditions_matched, list):
                conditions_matched = [str(conditions_matched)] if conditions_matched else []
            
            params = (
                scan_id, session_id, symbol,
                opportunity_data.get('status', 'PENDING'),
                opportunity_data.get('direction'),
                opportunity_data.get('setup_score'),
                conditions_matched,  # TEXT[] - liste de strings
                opportunity_data.get('entry_price'),  # entry_suggested
                opportunity_data.get('tp_price'),  # tp_suggested
                opportunity_data.get('sl_price'),  # sl_suggested
                opportunity_data.get('tp_sl_mode', 'FIXE')  # tp_sl_mode
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
        scan_log_id: Optional[int] = None,
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
                    timestamp_entry, timestamp_exit, session_id, opportunity_id, scan_log_id, symbol,
                    direction, entry_price, exit_price,
                    size_usdt, tp_price, sl_price, gross_pnl_usdt, pnl_pct, pnl_usdt,
                    net_pnl_usdt, net_pnl_pct,
                    fees_usdt, slippage_pct, slippage_usdt,
                    exit_reason, duration_seconds,
                    tp_sl_mode, break_even_set,
                    break_even_triggered_at,
                    trailing_stop_activated, trailing_stop_triggered_at,
                    partial_tp_executed, partial_tp_triggered_at,
                    partial_tp_profit, partial_tp_percent,
                    tp_escalier_levels_executed, tp_escalier_profits,
                    early_invalidation_triggered, early_invalidation_triggered_at,
                    early_invalidation_threshold, early_invalidation_elapsed,
                    early_invalidation_atr_pct, early_invalidation_pnl_pct,
                    -- Indicateurs d'entrée (pour ML) - RSI
                    entry_rsi_1m, entry_rsi_5m, entry_rsi_prev_1m, entry_rsi_prev_5m,
                    -- Indicateurs d'entrée - MACD
                    entry_macd_1m, entry_macd_signal_1m, entry_macd_hist_1m, entry_macd_hist_prev_1m,
                    entry_macd_5m, entry_macd_signal_5m, entry_macd_hist_5m, entry_macd_hist_prev_5m,
                    -- Indicateurs d'entrée - ADX
                    entry_adx_1m, entry_adx_5m,
                    entry_di_plus_1m, entry_di_minus_1m, entry_di_gap_1m,
                    entry_di_plus_5m, entry_di_minus_5m, entry_di_gap_5m,
                    -- Indicateurs d'entrée - EMA
                    entry_ema9_1m, entry_ema21_1m, entry_ema_diff_pct_1m,
                    entry_ema9_5m, entry_ema21_5m, entry_ema_diff_pct_5m,
                    -- Indicateurs d'entrée - ATR
                    entry_atr_1m, entry_atr_pct_1m, entry_atr_5m, entry_atr_pct_5m,
                    -- Indicateurs d'entrée - Bollinger Bands
                    entry_bb_upper_1m, entry_bb_middle_1m, entry_bb_lower_1m,
                    entry_bb_width_1m, entry_bb_distance_to_lower_1m, entry_bb_distance_to_upper_1m,
                    entry_bb_upper_5m, entry_bb_middle_5m, entry_bb_lower_5m,
                    entry_bb_width_5m, entry_bb_distance_to_lower_5m, entry_bb_distance_to_upper_5m,
                    -- Indicateurs d'entrée - Volume
                    entry_volume_1m, entry_volume_avg_1m, entry_volume_ratio_1m, entry_volume_spike_1m,
                    entry_volume_5m, entry_volume_avg_5m, entry_volume_ratio_5m, entry_volume_spike_5m,
                    -- Indicateurs d'entrée - Score et autres
                    entry_score, entry_spread_pct, entry_balance_score,
                    entry_conditions, entry_condition_count,
                    -- Métriques temporelles entry
                    entry_hour_of_day, entry_day_of_week,
                    -- Indicateurs de sortie
                    exit_rsi_1m, exit_rsi_5m,
                    exit_macd_hist_1m, exit_macd_hist_5m,
                    exit_adx_1m, exit_adx_5m,
                    exit_atr_pct_1m, exit_atr_pct_5m,
                    exit_score, exit_volume_ratio_1m, exit_volume_ratio_5m,
                    exit_spread_pct, exit_balance_score,
                    entry_to_exit_price_change_pct,
                    -- Métriques temporelles exit
                    exit_hour_of_day, exit_day_of_week,
                    -- Métriques de position
                    max_favorable_excursion, max_adverse_excursion,
                    max_favorable_excursion_usdt, max_adverse_excursion_usdt,
                    -- Métriques de qualité
                    risk_reward_ratio,
                    profit_factor,
                    -- Métriques de performance additionnelles
                    entry_to_max_profit_price_change_pct, entry_to_max_loss_price_change_pct,
                    max_drawdown_pct, max_drawdown_usdt,
                    -- Scalability
                    entry_book_depth, entry_bid_vol, entry_ask_vol, entry_orderbook_imbalance,
                    -- Configuration snapshot
                    config_snapshot,
                    win
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s, %s,
                    %s
                )
                RETURNING id
            """
            
            # Utiliser timestamp_entry pour entry et timestamp_exit pour exit
            # Récupérer timestamp_entry depuis trade_data si disponible, sinon utiliser maintenant
            entry_timestamp = trade_data.get('timestamp_entry') or timestamp_iso
            exit_timestamp = trade_data.get('timestamp_exit') or (timestamp_iso if trade_data.get('exit_price') else None)
            
            # Calculer win (True si net_pnl_usdt > 0)
            net_pnl_usdt = trade_data.get('net_pnl_usdt', 0)
            win = net_pnl_usdt > 0 if net_pnl_usdt is not None else None
            
            # Calculer tp_escalier_profits (somme des profits)
            tp_escalier_levels_hit = trade_data.get('tp_escalier_levels_hit', [])
            tp_escalier_profits = sum(p.get('profit', 0) for p in tp_escalier_levels_hit) if tp_escalier_levels_hit else 0
            
            # Extraire indicateurs d'entrée
            entry_indicators = trade_data.get('entry_indicators', {}) or {}
            entry_conditions = trade_data.get('entry_conditions', [])
            
            # Extraire indicateurs de sortie
            exit_indicators = trade_data.get('exit_indicators', {}) or {}
            
            # Calculer métriques temporelles
            try:
                if isinstance(entry_timestamp, str):
                    # Parser timestamp ISO
                    if entry_timestamp.endswith('Z'):
                        entry_timestamp = entry_timestamp.replace('Z', '+00:00')
                    entry_datetime = datetime.fromisoformat(entry_timestamp)
                elif isinstance(entry_timestamp, datetime):
                    entry_datetime = entry_timestamp
                else:
                    entry_datetime = now
                entry_hour = entry_datetime.hour
                entry_day = entry_datetime.weekday()  # 0=Lundi, 6=Dimanche
            except Exception:
                entry_hour = now.hour
                entry_day = now.weekday()
            
            try:
                if exit_timestamp:
                    if isinstance(exit_timestamp, str):
                        if exit_timestamp.endswith('Z'):
                            exit_timestamp = exit_timestamp.replace('Z', '+00:00')
                        exit_datetime = datetime.fromisoformat(exit_timestamp)
                    elif isinstance(exit_timestamp, datetime):
                        exit_datetime = exit_timestamp
                    else:
                        exit_datetime = now
                    exit_hour = exit_datetime.hour
                    exit_day = exit_datetime.weekday()
                else:
                    exit_hour = None
                    exit_day = None
            except Exception:
                exit_hour = None
                exit_day = None
            
            # Calculer risk_reward_ratio
            entry_price = trade_data.get('entry_price')
            tp_price = trade_data.get('tp_price')
            sl_price = trade_data.get('sl_price')
            exit_price = trade_data.get('exit_price')
            risk_reward_ratio = None
            if entry_price and tp_price and sl_price:
                if trade_data.get('direction') == 'LONG':
                    profit = tp_price - entry_price
                    risk = entry_price - sl_price
                else:  # SHORT
                    profit = entry_price - tp_price
                    risk = sl_price - entry_price
                if risk > 0:
                    risk_reward_ratio = profit / risk
            
            # Calculer entry_to_exit_price_change_pct
            entry_to_exit_price_change_pct = None
            if entry_price and exit_price:
                if trade_data.get('direction') == 'LONG':
                    entry_to_exit_price_change_pct = ((exit_price - entry_price) / entry_price) * 100
                else:  # SHORT
                    entry_to_exit_price_change_pct = ((entry_price - exit_price) / entry_price) * 100
            
            # Calculer max_favorable_excursion et max_adverse_excursion depuis pnl_history
            pnl_history = trade_data.get('pnl_history', []) or []
            max_favorable_excursion = None
            max_adverse_excursion = None
            max_favorable_excursion_usdt = None
            max_adverse_excursion_usdt = None
            entry_to_max_profit_price_change_pct = None
            entry_to_max_loss_price_change_pct = None
            max_drawdown_pct = None
            max_drawdown_usdt = None
            
            if pnl_history:
                pnl_pcts = [p.get('pnl_pct', 0) for p in pnl_history if p.get('pnl_pct') is not None]
                pnl_usdts = [p.get('pnl_usdt', 0) for p in pnl_history if p.get('pnl_usdt') is not None]
                if pnl_pcts:
                    max_favorable_excursion = max(pnl_pcts)
                    max_adverse_excursion = min(pnl_pcts)
                    # Calculer entry_to_max_profit_price_change_pct et entry_to_max_loss_price_change_pct
                    if entry_price:
                        if trade_data.get('direction') == 'LONG':
                            max_profit_price = entry_price * (1 + max_favorable_excursion / 100) if max_favorable_excursion else None
                            max_loss_price = entry_price * (1 + max_adverse_excursion / 100) if max_adverse_excursion else None
                        else:  # SHORT
                            max_profit_price = entry_price * (1 - max_favorable_excursion / 100) if max_favorable_excursion else None
                            max_loss_price = entry_price * (1 - max_adverse_excursion / 100) if max_adverse_excursion else None
                        
                        if max_profit_price:
                            entry_to_max_profit_price_change_pct = ((max_profit_price - entry_price) / entry_price) * 100
                        if max_loss_price:
                            entry_to_max_loss_price_change_pct = ((max_loss_price - entry_price) / entry_price) * 100
                    
                    # Calculer max_drawdown (drawdown depuis le profit max)
                    if max_favorable_excursion and max_adverse_excursion:
                        max_drawdown_pct = max_favorable_excursion - max_adverse_excursion if max_favorable_excursion > 0 else abs(max_adverse_excursion)
                
                if pnl_usdts:
                    max_favorable_excursion_usdt = max(pnl_usdts)
                    max_adverse_excursion_usdt = min(pnl_usdts)
                    if max_favorable_excursion_usdt and max_adverse_excursion_usdt:
                        max_drawdown_usdt = max_favorable_excursion_usdt - max_adverse_excursion_usdt if max_favorable_excursion_usdt > 0 else abs(max_adverse_excursion_usdt)
            
            # Fallback sur max_pnl_reached / min_pnl_reached si pnl_history non disponible
            if max_favorable_excursion is None:
                max_favorable_excursion = trade_data.get('max_pnl_reached')
            if max_adverse_excursion is None:
                max_adverse_excursion = trade_data.get('min_pnl_reached')
            
            # Extraire scalability data
            entry_scalability = trade_data.get('entry_scalability', {}) or {}
            if not isinstance(entry_scalability, dict):
                entry_scalability = {}
            
            # Calculer slippage_usdt
            slippage_pct = trade_data.get('slippage', 0) or 0
            size_usdt = trade_data.get('size_usdt', 0) or 0
            slippage_usdt = (slippage_pct / 100) * size_usdt if slippage_pct and size_usdt else 0
            
            # Extraire config_snapshot
            config_snapshot = trade_data.get('config_snapshot', {})
            if config_snapshot:
                config_snapshot = json.dumps(config_snapshot)
            else:
                config_snapshot = None
            
            # Convertir entry_conditions en liste de strings pour PostgreSQL TEXT[]
            # (doit être fait avant de créer params)
            if isinstance(entry_conditions, dict):
                entry_conditions = [str(k) for k in entry_conditions.keys()] if entry_conditions else []
            elif isinstance(entry_conditions, list):
                entry_conditions = [str(c) for c in entry_conditions if c]  # Convertir en strings
            else:
                entry_conditions = [str(entry_conditions)] if entry_conditions else []
            
            params = (
                entry_timestamp, exit_timestamp, session_id, opportunity_id, scan_log_id,
                trade_data.get('symbol'),
                trade_data.get('direction'),
                trade_data.get('entry_price'),
                trade_data.get('exit_price'),
                trade_data.get('size_usdt'),
                trade_data.get('tp_price'),  # tp_price
                trade_data.get('sl_price'),  # sl_price
                trade_data.get('gross_pnl_usdt', 0),
                trade_data.get('gross_pnl_pct', 0),  # pnl_pct (gross)
                trade_data.get('gross_pnl_usdt', 0),  # pnl_usdt (gross)
                trade_data.get('net_pnl_usdt', 0),
                trade_data.get('net_pnl_pct', 0),
                trade_data.get('fees', 0),  # fees_usdt
                trade_data.get('slippage', 0),  # slippage_pct
                slippage_usdt,  # slippage_usdt
                trade_data.get('reason'),  # exit_reason
                trade_data.get('duration_seconds'),
                trade_data.get('tp_sl_mode'),
                trade_data.get('break_even_triggered', False),  # break_even_set
                trade_data.get('break_even_triggered_at'),  # break_even_triggered_at
                trade_data.get('trailing_stop_triggered', False),  # trailing_stop_activated
                trade_data.get('trailing_stop_triggered_at'),  # trailing_stop_triggered_at
                trade_data.get('partial_tp_triggered', False),  # partial_tp_executed
                trade_data.get('partial_tp_triggered_at'),  # partial_tp_triggered_at
                trade_data.get('partial_tp_profit'),  # partial_tp_profit
                trade_data.get('partial_tp_percent'),  # partial_tp_percent
                len(tp_escalier_levels_hit),  # tp_escalier_levels_executed (count)
                tp_escalier_profits,  # tp_escalier_profits (somme)
                # Early Invalidation
                trade_data.get('early_invalidation_triggered', False),  # early_invalidation_triggered
                trade_data.get('early_invalidation_triggered_at'),  # early_invalidation_triggered_at
                trade_data.get('early_invalidation_threshold'),  # early_invalidation_threshold
                trade_data.get('early_invalidation_elapsed'),  # early_invalidation_elapsed
                trade_data.get('early_invalidation_atr_pct'),  # early_invalidation_atr_pct
                trade_data.get('early_invalidation_pnl_pct'),  # early_invalidation_pnl_pct
                # Indicateurs d'entrée - RSI
                entry_indicators.get('rsi_1m'), entry_indicators.get('rsi_5m'),
                entry_indicators.get('rsi_prev_1m'), entry_indicators.get('rsi_prev_5m'),
                # Indicateurs d'entrée - MACD
                entry_indicators.get('macd_1m'), entry_indicators.get('macd_signal_1m'),
                entry_indicators.get('macd_hist_1m'), entry_indicators.get('macd_hist_prev_1m'),
                entry_indicators.get('macd_5m'), entry_indicators.get('macd_signal_5m'),
                entry_indicators.get('macd_hist_5m'), entry_indicators.get('macd_hist_prev_5m'),
                # Indicateurs d'entrée - ADX
                entry_indicators.get('adx_1m'), entry_indicators.get('adx_5m'),
                entry_indicators.get('di_plus_1m'), entry_indicators.get('di_minus_1m'), entry_indicators.get('di_gap_1m'),
                entry_indicators.get('di_plus_5m'), entry_indicators.get('di_minus_5m'), entry_indicators.get('di_gap_5m'),
                # Indicateurs d'entrée - EMA
                entry_indicators.get('ema9_1m'), entry_indicators.get('ema21_1m'), entry_indicators.get('ema_diff_pct_1m'),
                entry_indicators.get('ema9_5m'), entry_indicators.get('ema21_5m'), entry_indicators.get('ema_diff_pct_5m'),
                # Indicateurs d'entrée - ATR
                entry_indicators.get('atr_1m'), entry_indicators.get('atr_pct_1m'),
                entry_indicators.get('atr_5m'), entry_indicators.get('atr_pct_5m'),
                # Indicateurs d'entrée - Bollinger Bands
                entry_indicators.get('bb_upper_1m'), entry_indicators.get('bb_middle_1m'), entry_indicators.get('bb_lower_1m'),
                entry_indicators.get('bb_width_1m'), entry_indicators.get('bb_distance_to_lower_1m'), entry_indicators.get('bb_distance_to_upper_1m'),
                entry_indicators.get('bb_upper_5m'), entry_indicators.get('bb_middle_5m'), entry_indicators.get('bb_lower_5m'),
                entry_indicators.get('bb_width_5m'), entry_indicators.get('bb_distance_to_lower_5m'), entry_indicators.get('bb_distance_to_upper_5m'),
                # Indicateurs d'entrée - Volume
                entry_indicators.get('volume_1m'), entry_indicators.get('volume_avg_1m'),
                entry_indicators.get('volume_ratio_1m'), entry_indicators.get('volume_spike_1m'),
                entry_indicators.get('volume_5m'), entry_indicators.get('volume_avg_5m'),
                entry_indicators.get('volume_ratio_5m'), entry_indicators.get('volume_spike_5m'),
                # Indicateurs d'entrée - Score et autres
                entry_indicators.get('score'),  # entry_score
                entry_scalability.get('spread_pct'),  # entry_spread_pct
                entry_scalability.get('balance_score'),  # entry_balance_score
                entry_conditions,  # entry_conditions (TEXT[])
                len(entry_conditions),  # entry_condition_count
                # Métriques temporelles entry
                entry_hour, entry_day,
                # Indicateurs de sortie
                exit_indicators.get('rsi_1m'), exit_indicators.get('rsi_5m'),
                exit_indicators.get('macd_hist_1m'), exit_indicators.get('macd_hist_5m'),
                exit_indicators.get('adx_1m'), exit_indicators.get('adx_5m'),
                exit_indicators.get('atr_pct_1m'), exit_indicators.get('atr_pct_5m'),
                exit_indicators.get('score'),  # exit_score
                exit_indicators.get('volume_ratio_1m'), exit_indicators.get('volume_ratio_5m'),
                exit_indicators.get('spread_pct'),  # exit_spread_pct
                exit_indicators.get('balance_score'),  # exit_balance_score
                entry_to_exit_price_change_pct,
                # Métriques temporelles exit
                exit_hour, exit_day,
                # Métriques de position
                max_favorable_excursion, max_adverse_excursion,
                max_favorable_excursion_usdt, max_adverse_excursion_usdt,
                # Métriques de qualité
                risk_reward_ratio,
                None,  # profit_factor (non calculé pour l'instant)
                # Métriques de performance additionnelles
                entry_to_max_profit_price_change_pct, entry_to_max_loss_price_change_pct,
                max_drawdown_pct, max_drawdown_usdt,
                # Scalability
                entry_scalability.get('book_depth'),  # entry_book_depth
                entry_scalability.get('bid_vol'),  # entry_bid_vol
                entry_scalability.get('ask_vol'),  # entry_ask_vol
                entry_scalability.get('orderbook_imbalance'),  # entry_orderbook_imbalance
                # Configuration snapshot
                config_snapshot,
                win
            )
            
            # Vérifier le nombre de paramètres AVANT l'exécution
            param_count = len(params)
            placeholder_count = query.count('%s')
            if param_count != placeholder_count:
                logger.error(f"❌ Déséquilibre paramètres: {param_count} paramètres pour {placeholder_count} placeholders")
                logger.error(f"   Symbol: {trade_data.get('symbol')}")
                logger.error(f"   entry_conditions type: {type(entry_conditions)}, value: {entry_conditions}")
                # Ne pas logger le trade si déséquilibre
                return None
            
            result = self._execute_query(query, params, fetch=True)
            if result:
                trade_id = result[0][0]
                logger.debug(f"📊 Trade loggé: {trade_data.get('symbol')} (ID: {trade_id})")
                return trade_id
            return None
            
        except Exception as e:
            logger.error(f"❌ Erreur logging trade {trade_data.get('symbol')}: {e}")
            return None
    
    def _flush_buffers(self, force: bool = False):
        """
        🔥 PHASE 3: Flush les buffers vers PostgreSQL
        
        Args:
            force: Si True, flush même si buffer pas plein
        """
        if not self.enabled:
            return
        
        now = datetime.now()
        time_since_flush = (now - self.last_flush_time).total_seconds()
        should_flush = force or (
            len(self.scan_buffer) >= self.batch_size or
            len(self.opportunity_buffer) >= self.batch_size or
            time_since_flush >= self.batch_flush_interval
        )
        
        if not should_flush:
            return
        
        with self.buffer_lock:
            # Flush scans
            if self.scan_buffer:
                try:
                    self._batch_insert_scans(list(self.scan_buffer))
                    self.scan_buffer.clear()
                except Exception as e:
                    logger.error(f"❌ Erreur flush scans: {e}")
            
            # Flush opportunities
            if self.opportunity_buffer:
                try:
                    self._batch_insert_opportunities(list(self.opportunity_buffer))
                    self.opportunity_buffer.clear()
                except Exception as e:
                    logger.error(f"❌ Erreur flush opportunities: {e}")
            
            self.last_flush_time = now
    
    def _batch_insert_scans(self, scans: List[Dict[str, Any]]):
        """
        🔥 PHASE 3: Insert batch de scans avec execute_values
        
        Args:
            scans: Liste de dicts avec (session_id, symbol, scan_data)
        """
        if not scans:
            return
        
        conn = self._get_connection()
        if not conn:
            return
        
        try:
            cursor = conn.cursor()
            
            # Préparer les valeurs pour execute_values
            values = []
            for scan_item in scans:
                session_id = scan_item['session_id']
                symbol = scan_item['symbol']
                scan_data = scan_item['scan_data']
                
                indicators_1m = scan_data.get('indicators_1m', {})
                indicators_5m = scan_data.get('indicators_5m', {})
                filters = scan_data.get('filters', {})
                scores = scan_data.get('scores', {})
                patterns = scan_data.get('patterns', {})
                market_data = scan_data.get('market_data', {})
                
                # Construire tuple de valeurs (même ordre que dans log_scan)
                value_tuple = (
                    session_id, symbol, scan_data.get('scan_duration_ms'),
                    market_data.get('price'), market_data.get('spread_pct'),
                    market_data.get('book_depth'), market_data.get('balance_score'),
                    market_data.get('bid_vol'), market_data.get('ask_vol'),
                    market_data.get('orderbook_imbalance_ratio'),
                    # 1m indicators
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
                    # 5m indicators
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
                    # Filters
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
                    # Decision
                    scan_data.get('is_opportunity', False),
                    scan_data.get('opportunity_direction'),
                    scan_data.get('reject_reason'), scan_data.get('reject_reason_category'),
                    # Params
                    json.dumps(scan_data.get('params_snapshot', {}))
                )
                values.append(value_tuple)
            
            # Colonnes pour execute_values (même ordre que dans log_scan)
            columns = (
                'session_id', 'symbol', 'scan_duration_ms',
                'price', 'spread_pct', 'book_depth', 'balance_score',
                'bid_vol', 'ask_vol', 'orderbook_imbalance_ratio',
                'ema9_1m', 'ema21_1m', 'ema_diff_pct_1m',
                'rsi_1m', 'rsi_prev_1m',
                'macd_1m', 'macd_signal_1m', 'macd_hist_1m', 'macd_hist_prev_1m',
                'adx_1m', 'di_plus_1m', 'di_minus_1m', 'di_gap_1m',
                'atr_1m', 'atr_pct_1m',
                'bb_upper_1m', 'bb_middle_1m', 'bb_lower_1m', 'bb_width_1m',
                'bb_distance_to_lower_1m', 'bb_distance_to_upper_1m',
                'volume_1m', 'volume_avg_1m', 'volume_ratio_1m', 'volume_spike_1m',
                'ema9_5m', 'ema21_5m', 'ema_diff_pct_5m',
                'rsi_5m', 'rsi_prev_5m',
                'macd_5m', 'macd_signal_5m', 'macd_hist_5m', 'macd_hist_prev_5m',
                'adx_5m', 'di_plus_5m', 'di_minus_5m', 'di_gap_5m',
                'atr_5m', 'atr_pct_5m',
                'bb_upper_5m', 'bb_middle_5m', 'bb_lower_5m', 'bb_width_5m',
                'bb_distance_to_lower_5m', 'bb_distance_to_upper_5m',
                'volume_5m', 'volume_avg_5m', 'volume_ratio_5m', 'volume_spike_5m',
                'snr_1m', 'snr_5m', 'snr_passed_1m', 'snr_passed_5m',
                'breakout_distance_1m', 'breakout_distance_5m',
                'breakout_passed_1m', 'breakout_passed_5m',
                'wick_ratio_1m', 'wick_ratio_5m', 'wick_passed_1m', 'wick_passed_5m',
                'atr_optimal_passed_1m', 'atr_optimal_passed_5m',
                'volume_filter_passed_1m', 'volume_filter_passed_5m',
                'use_confluence', 'confluence_met',
                'score_1m', 'score_5m', 'score_total',
                'score_long_1m', 'score_short_1m', 'score_long_5m', 'score_short_5m',
                'timeframes_aligned',
                'pattern_1m', 'pattern_multi_1m', 'pattern_5m', 'pattern_multi_5m',
                'trend_timeframe', 'trend_direction', 'trend_strength', 'trend_bonus',
                'divergence_detected', 'divergence_type', 'divergence_bonus',
                'is_opportunity', 'opportunity_direction', 'reject_reason', 'reject_reason_category',
                'params_snapshot'
            )
            
            # Utiliser execute_values pour batch insert
            execute_values(
                cursor,
                f"INSERT INTO scan_logs (timestamp, {', '.join(columns)}) VALUES %s",
                values,
                template=f"(NOW(), {', '.join(['%s'] * len(columns))})",
                page_size=len(values)
            )
            
            conn.commit()
            cursor.close()
            logger.debug(f"📊 Batch insert: {len(scans)} scans insérés")
            
        except Exception as e:
            logger.error(f"❌ Erreur batch insert scans: {e}")
            if conn:
                conn.rollback()
        finally:
            self._return_connection(conn)
    
    def _batch_insert_opportunities(self, opportunities: List[Dict[str, Any]]):
        """
        🔥 PHASE 3: Insert batch d'opportunités avec execute_values
        
        Args:
            opportunities: Liste de dicts avec (scan_id, session_id, symbol, opportunity_data)
        """
        if not opportunities:
            return
        
        conn = self._get_connection()
        if not conn:
            return
        
        try:
            cursor = conn.cursor()
            
            values = []
            for opp_item in opportunities:
                scan_id = opp_item['scan_id']
                session_id = opp_item['session_id']
                symbol = opp_item['symbol']
                opp_data = opp_item['opportunity_data']
                
                # Convertir conditions_matched en liste si c'est un dict ou autre
                conditions_matched = opp_data.get('conditions_matched', [])
                if isinstance(conditions_matched, dict):
                    conditions_matched = list(conditions_matched.keys()) if conditions_matched else []
                elif not isinstance(conditions_matched, list):
                    conditions_matched = [str(conditions_matched)] if conditions_matched else []
                
                value_tuple = (
                    scan_id, session_id, symbol,
                    opp_data.get('status', 'PENDING'),
                    opp_data.get('direction'),
                    opp_data.get('setup_score'),
                    conditions_matched,  # TEXT[] - liste de strings
                    opp_data.get('entry_price'),  # entry_suggested
                    opp_data.get('tp_price'),  # tp_suggested
                    opp_data.get('sl_price'),  # sl_suggested
                    opp_data.get('tp_sl_mode', 'FIXE')  # tp_sl_mode
                )
                values.append(value_tuple)
            
            columns = (
                'scan_log_id', 'session_id', 'symbol',
                'status', 'direction', 'setup_score',
                'conditions_matched', 'entry_suggested', 'tp_suggested', 'sl_suggested',
                'tp_sl_mode'
            )
            
            execute_values(
                cursor,
                f"INSERT INTO opportunities (timestamp, {', '.join(columns)}) VALUES %s",
                values,
                template=f"(NOW(), {', '.join(['%s'] * len(columns))})",
                page_size=len(values)
            )
            
            conn.commit()
            cursor.close()
            logger.debug(f"📊 Batch insert: {len(opportunities)} opportunités insérées")
            
        except Exception as e:
            logger.error(f"❌ Erreur batch insert opportunities: {e}")
            if conn:
                conn.rollback()
        finally:
            self._return_connection(conn)
    
    def close(self):
        """Fermer le pool de connexions et flush les buffers"""
        # Flush final des buffers
        if self.enabled:
            self._flush_buffers(force=True)
        
        if self.pool:
            try:
                self.pool.closeall()
                logger.info("✅ Pool PostgreSQL fermé")
            except Exception as e:
                logger.error(f"❌ Erreur fermeture pool: {e}")

