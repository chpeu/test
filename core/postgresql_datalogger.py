#!/usr/bin/env python3
"""
PostgreSQL DataLogger - Trade Cursor v7.0
Logging des scans, opportunités et trades vers PostgreSQL pour ML
"""

import logging
import os
from typing import Dict, Any, Optional, List, Sequence
from datetime import datetime, timezone, date
from decimal import Decimal
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


def _summarize_params(params: Optional[Sequence[Any]], limit: int = 5) -> str:
    """Retourner un aperçu compact des paramètres SQL."""
    if not params:
        return "<no-params>"
    try:
        iterable = list(params)
    except TypeError:
        return f"<{type(params).__name__}>"
    summary = []
    for value in iterable[:limit]:
        summary.append(f"{type(value).__name__}:{str(value)[:30]}")
    if len(iterable) > limit:
        summary.append(f"…(+{len(iterable) - limit})")
    return '[' + ', '.join(summary) + ']'


def _extract_numeric_value(value: Any) -> Optional[float]:
    """
    🔥 FIX: Extraire une valeur numérique depuis un dict ou autre type
    
    Args:
        value: Valeur à extraire (peut être dict, float, int, str, None)
        
    Returns:
        float ou None
    """
    if value is None:
        return None
    
    # Si c'est déjà un nombre
    if isinstance(value, (int, float)):
        return float(value)
    
    # Si c'est un dict, essayer d'extraire une valeur numérique
    if isinstance(value, dict):
        # Essayer plusieurs clés communes
        for key in ['value', 'price', 'score', 'rsi', 'macd', 'adx', 'atr', 'volume', 'spread', 'balance', 'depth', 'vol5', 'vol15']:
            if key in value:
                nested_value = value[key]
                if isinstance(nested_value, (int, float)):
                    return float(nested_value)
                elif isinstance(nested_value, str):
                    try:
                        return float(nested_value)
                    except (ValueError, TypeError):
                        continue
        # Si aucun champ numérique trouvé, retourner None
        return None
    
    # Si c'est une string, essayer de convertir
    if isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    # Autre type non supporté
    return None


def serialize_config_safe(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    🔥 FIX BUG #1: Convertir config en JSON-safe dict
    
    Gère les types non-JSON sérialisables :
    - Fonctions → string
    - datetime/date → ISO format
    - Decimal → float
    - Objets custom → string ou dict si possible
    
    Args:
        config: Dictionnaire de configuration
        
    Returns:
        Dictionnaire JSON-safe
    """
    if not config:
        return {}
    
    serialized = {}
    for key, value in config.items():
        try:
            # Test rapide de sérialisabilité
            json.dumps(value)
            serialized[key] = value
        except (TypeError, ValueError):
            # Gestion par type non-sérialisable
            if callable(value):
                # Fonction → string avec nom
                func_name = getattr(value, '__name__', 'unknown')
                serialized[key] = f"<function:{func_name}>"
                logger.debug(f"🔧 Config key '{key}': fonction convertie en string: {func_name}")
            elif isinstance(value, (datetime, date)):
                # datetime/date → ISO format
                serialized[key] = value.isoformat()
                logger.debug(f"🔧 Config key '{key}': datetime converti en ISO: {value.isoformat()}")
            elif isinstance(value, Decimal):
                # Decimal → float
                serialized[key] = float(value)
                logger.debug(f"🔧 Config key '{key}': Decimal converti en float: {float(value)}")
            elif hasattr(value, '__dict__'):
                # Objet custom → essayer de sérialiser __dict__ récursivement
                try:
                    serialized[key] = serialize_config_safe(value.__dict__)
                    logger.debug(f"🔧 Config key '{key}': objet {type(value).__name__} converti récursivement")
                except Exception as e:
                    # Si échec, convertir en string
                    serialized[key] = f"<{type(value).__name__}>"
                    logger.warning(f"⚠️ Config key '{key}': objet {type(value).__name__} non sérialisable, converti en string: {e}")
            elif isinstance(value, (set, frozenset)):
                # Set → list
                serialized[key] = list(value)
                logger.debug(f"🔧 Config key '{key}': set converti en list")
            else:
                # Dernier recours : convertir en string
                serialized[key] = str(value)
                logger.warning(f"⚠️ Config key '{key}': type {type(value).__name__} non sérialisable, converti en string: {str(value)[:50]}")
    
    return serialized


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
        batch_size: int = 10,
        batch_flush_interval: float = 2.0
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
            batch_size: Taille du buffer pour batch inserts (défaut: 10, réduit de 50 pour flush plus fréquent)
            batch_flush_interval: Intervalle en secondes pour flush automatique (défaut: 2.0, réduit de 5.0 pour flush plus fréquent)
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
        # 🔥 FIX BUG #3: Utiliser timezone.utc pour PostgreSQL TIMESTAMPTZ
        self.last_flush_time = datetime.now(timezone.utc)
    
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
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "SQL exec: %s | params=%s",
                    ' '.join(query.strip().splitlines())[:200],
                    _summarize_params(params)
                )
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
            logger.error(
                "❌ Erreur exécution requête: %s | params=%s",
                e,
                _summarize_params(params)
            )
            logger.debug(f"Query: {query[:400]}...")
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
        # 🔥 FIX BUG #1: Utiliser serialize_config_safe() pour éviter les erreurs de sérialisation
        try:
            from config import (
                TRADING_CONFIG, RISK_CONFIG, CONDITION_WEIGHTS,
                TREND_BONUS_CONFIG, RETRY_CONFIG, CIRCUIT_BREAKER_CONFIG,
                WEBSOCKET_CONFIG
            )
            config_snapshot_dict = {}
            # Copier TRADING_CONFIG avec sérialisation safe
            if TRADING_CONFIG:
                config_snapshot_dict.update(serialize_config_safe(TRADING_CONFIG))
            # Ajouter les variables définies séparément avec sérialisation safe
            config_snapshot_dict['RISK_CONFIG'] = serialize_config_safe(RISK_CONFIG) if RISK_CONFIG else {}
            config_snapshot_dict['CONDITION_WEIGHTS'] = serialize_config_safe(CONDITION_WEIGHTS) if CONDITION_WEIGHTS else {}
            config_snapshot_dict['TREND_BONUS_CONFIG'] = serialize_config_safe(TREND_BONUS_CONFIG) if TREND_BONUS_CONFIG else {}
            config_snapshot_dict['RETRY_CONFIG'] = serialize_config_safe(RETRY_CONFIG) if RETRY_CONFIG else {}
            config_snapshot_dict['CIRCUIT_BREAKER_CONFIG'] = serialize_config_safe(CIRCUIT_BREAKER_CONFIG) if CIRCUIT_BREAKER_CONFIG else {}
            config_snapshot_dict['WEBSOCKET_CONFIG'] = serialize_config_safe(WEBSOCKET_CONFIG) if WEBSOCKET_CONFIG else {}
            # Maintenant json.dumps() est safe
            config_snapshot = json.dumps(config_snapshot_dict)
        except Exception as e:
            logger.error(f"❌ Erreur préparation config_snapshot pour session: {e}", exc_info=True)
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
            logger.warning(f"⚠️ PostgreSQL DataLogger désactivé - scan non loggé pour {symbol}")
            return None
        
        # Obtenir ou créer session
        if not session_id:
            session_id = self.get_or_create_session()
        
        # 🔥 FIX: Vérifier le prix AVANT d'ajouter au buffer (pour éviter les scans invalides)
        market_data = scan_data.get('market_data', {})
        price = market_data.get('price')
        if price is None:
            # Fallback 1: Depuis scan_data directement
            price = scan_data.get('price')
        if price is None:
            # Fallback 2: Depuis analysis_1m ou analysis_5m si disponible
            analysis_1m = scan_data.get('analysis_1m', {})
            if isinstance(analysis_1m, dict):
                price = analysis_1m.get('price')
            if price is None:
                analysis_5m = scan_data.get('analysis_5m', {})
                if isinstance(analysis_5m, dict):
                    price = analysis_5m.get('price')
        # Extraire la valeur numérique si c'est un dict
        if isinstance(price, dict):
            price = price.get('price') or price.get('lastPrice') or price.get('close') or price.get('value')
        # Vérifier que price est un nombre
        if price is not None and not isinstance(price, (int, float)):
            try:
                price = float(price)
            except (ValueError, TypeError):
                logger.warning(f"⚠️ Prix invalide pour {symbol} dans log_scan (batch): {price} (type: {type(price)})")
                price = None
        
        # Si le prix est toujours None, on ne peut pas insérer (contrainte NOT NULL)
        if price is None:
            logger.error(f"❌ Prix manquant pour {symbol} dans log_scan (batch), scan non ajouté au buffer")
            return None
        
        # 🔥 PHASE 3: Utiliser batch insert si activé
        if use_batch:
            with self.buffer_lock:
                self.scan_buffer.append({
                    'session_id': session_id,
                    'symbol': symbol,
                    'scan_data': scan_data
                })
                buffer_size = len(self.scan_buffer)
            logger.info(f"📝 Scan ajouté au buffer pour {symbol} (buffer size: {buffer_size}/{self.batch_size})")
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
                    recent_volume, vol5, vol15, scalability_score,
                    
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
                    %s, %s, %s, %s,
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
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
            """
            
            # 🔥 FIX: Récupérer le prix avec fallbacks multiples (pour éviter NULL)
            price = market_data.get('price')
            if price is None:
                # Fallback 1: Depuis scan_data directement
                price = scan_data.get('price')
            if price is None:
                # Fallback 2: Depuis analysis_1m ou analysis_5m si disponible
                analysis_1m = scan_data.get('analysis_1m', {})
                if isinstance(analysis_1m, dict):
                    price = analysis_1m.get('price')
                if price is None:
                    analysis_5m = scan_data.get('analysis_5m', {})
                    if isinstance(analysis_5m, dict):
                        price = analysis_5m.get('price')
            # Extraire la valeur numérique si c'est un dict
            if isinstance(price, dict):
                price = price.get('price') or price.get('lastPrice') or price.get('close') or price.get('value')
            # Vérifier que price est un nombre
            if price is not None and not isinstance(price, (int, float)):
                try:
                    price = float(price)
                except (ValueError, TypeError):
                    logger.warning(f"⚠️ Prix invalide pour {symbol} dans log_scan: {price} (type: {type(price)})")
                    price = None
            
            # Si le prix est toujours None, on ne peut pas insérer (contrainte NOT NULL)
            if price is None:
                logger.error(f"❌ Prix manquant pour {symbol} dans log_scan, insertion annulée")
                return None
            
            # Préparer les paramètres
            params = (
                session_id, symbol, scan_data.get('scan_duration_ms'),
                price, market_data.get('spread_pct'),
                market_data.get('book_depth'), market_data.get('balance_score'),
                market_data.get('bid_vol'), market_data.get('ask_vol'),
                market_data.get('orderbook_imbalance_ratio'),
                # Paramètres du scan de scalabilité
                market_data.get('recent_volume') or scan_data.get('recent_volume') or scan_data.get('recentVolume'),
                market_data.get('vol5') or scan_data.get('vol5'),
                market_data.get('vol15') or scan_data.get('vol15'),
                market_data.get('scalability_score') or scan_data.get('scalability_score') or scan_data.get('score'),
                
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
            
            # Convertir conditions_matched en liste de strings
            conditions_matched = opportunity_data.get('conditions_matched', [])
            if isinstance(conditions_matched, dict):
                # Si c'est un dict, prendre les clés ou les valeurs selon le cas
                conditions_matched = [str(k) for k in conditions_matched.keys()] if conditions_matched else []
            elif isinstance(conditions_matched, list):
                # S'assurer que tous les éléments sont des strings
                conditions_matched = [str(item) for item in conditions_matched if item is not None]
            else:
                # Autre type (str, int, etc.) -> convertir en liste
                conditions_matched = [str(conditions_matched)] if conditions_matched is not None else []
            
            # Extraire et valider les valeurs (s'assurer qu'elles ne sont pas des dicts)
            entry_price = opportunity_data.get('entry_price') or opportunity_data.get('entry_suggested')
            tp_price = opportunity_data.get('tp_price') or opportunity_data.get('tp_suggested')
            sl_price = opportunity_data.get('sl_price') or opportunity_data.get('sl_suggested')
            tp_sl_mode = opportunity_data.get('tp_sl_mode', 'FIXE')
            setup_score = opportunity_data.get('setup_score')
            direction = opportunity_data.get('direction')
            status = opportunity_data.get('status', 'PENDING')
            
            # S'assurer que les prix sont des nombres, pas des dicts
            entry_price = _extract_numeric_value(entry_price)
            tp_price = _extract_numeric_value(tp_price)
            sl_price = _extract_numeric_value(sl_price)
            if isinstance(tp_sl_mode, dict):
                tp_sl_mode = tp_sl_mode.get('mode') or 'FIXE'
            # S'assurer que setup_score est un nombre, pas un dict
            if isinstance(setup_score, dict):
                setup_score = _extract_numeric_value(setup_score)
            # S'assurer que direction est une string, pas un dict
            if isinstance(direction, dict):
                direction = direction.get('direction') or direction.get('value') or str(direction)
            # S'assurer que status est une string, pas un dict
            if isinstance(status, dict):
                status = status.get('status') or status.get('value') or 'PENDING'
            
            params = (
                scan_id, session_id, symbol,
                str(status) if status else 'PENDING',
                str(direction) if direction else None,
                float(setup_score) if setup_score is not None else None,
                conditions_matched,  # TEXT[] - liste de strings
                float(entry_price) if entry_price is not None else None,  # entry_suggested
                float(tp_price) if tp_price is not None else None,  # tp_suggested
                float(sl_price) if sl_price is not None else None,  # sl_suggested
                str(tp_sl_mode) if tp_sl_mode else 'FIXE'  # tp_sl_mode
            )
            
            if any(isinstance(p, dict) for p in params):
                logger.error(
                    "⚠️ Paramètre dict détecté dans log_opportunity pour %s | types=%s",
                    symbol,
                    [type(p).__name__ for p in params]
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
            session_id: UUID de la session (si non-UUID valide, une nouvelle session sera créée)
        
        Returns:
            ID du trade loggé ou None
        """
        if not self.enabled:
            return None
        
        # Valider que session_id est un UUID valide, sinon créer une nouvelle session
        if session_id:
            # Vérifier si session_id est un UUID valide
            try:
                uuid.UUID(session_id)
                # Si c'est un UUID valide, vérifier qu'il existe dans la base
                query_check = "SELECT id FROM trading_sessions WHERE id = %s"
                result = self._execute_query(query_check, (session_id,), fetch=True)
                if not result:
                    # UUID valide mais n'existe pas, créer une nouvelle session
                    session_id = self.get_or_create_session()
            except (ValueError, AttributeError):
                # session_id n'est pas un UUID valide (ex: 'live_...'), créer une nouvelle session
                session_id = self.get_or_create_session()
        else:
            # Pas de session_id fourni, créer une nouvelle session
            session_id = self.get_or_create_session()
        
        try:
            # 🔥 FIX BUG #3: Utiliser timezone.utc pour PostgreSQL TIMESTAMPTZ
            now = datetime.now(timezone.utc)
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
                    entry_recent_volume, entry_vol5, entry_vol15, entry_scalability_score,
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
                    %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
            """
            
            # Utiliser timestamp_entry pour entry et timestamp_exit pour exit
            # Récupérer timestamp_entry depuis trade_data si disponible, sinon utiliser maintenant
            entry_timestamp = trade_data.get('timestamp_entry') or timestamp_iso
            exit_timestamp = trade_data.get('timestamp_exit') or (timestamp_iso if trade_data.get('exit_price') else None)
            
            # Calculer win (True si net_pnl_usdt > 0)
            net_pnl_usdt_raw = trade_data.get('net_pnl_usdt', 0)
            net_pnl_usdt = _extract_numeric_value(net_pnl_usdt_raw) if net_pnl_usdt_raw is not None else 0
            win = net_pnl_usdt > 0 if net_pnl_usdt is not None else None
            
            # Calculer tp_escalier_profits (somme des profits)
            tp_escalier_levels_hit = trade_data.get('tp_escalier_levels_hit', [])
            # 🔥 FIX: S'assurer que les profits sont des nombres, pas des dicts
            tp_escalier_profits = 0
            if tp_escalier_levels_hit:
                for p in tp_escalier_levels_hit:
                    if isinstance(p, dict):
                        profit_value = _extract_numeric_value(p.get('profit', 0))
                        tp_escalier_profits += profit_value if profit_value is not None else 0
                    elif isinstance(p, (int, float)):
                        tp_escalier_profits += float(p)
            
            # Extraire indicateurs d'entrée
            entry_indicators = trade_data.get('entry_indicators', {}) or {}
            entry_conditions = trade_data.get('entry_conditions', [])
            
            # Extraire indicateurs de sortie
            exit_indicators = trade_data.get('exit_indicators', {}) or {}
            
            # 🔥 FIX: S'assurer que tous les indicateurs sont des valeurs numériques, pas des dicts
            # Créer des copies "nettoyées" des indicateurs
            entry_indicators_clean = {}
            for key, value in entry_indicators.items():
                if isinstance(value, dict):
                    entry_indicators_clean[key] = _extract_numeric_value(value)
                elif isinstance(value, (int, float)):
                    entry_indicators_clean[key] = float(value)
                elif value is None:
                    entry_indicators_clean[key] = None
                else:
                    # Essayer de convertir en float
                    entry_indicators_clean[key] = _extract_numeric_value(value)
            
            exit_indicators_clean = {}
            for key, value in exit_indicators.items():
                if isinstance(value, dict):
                    exit_indicators_clean[key] = _extract_numeric_value(value)
                elif isinstance(value, (int, float)):
                    exit_indicators_clean[key] = float(value)
                elif value is None:
                    exit_indicators_clean[key] = None
                else:
                    # Essayer de convertir en float
                    exit_indicators_clean[key] = _extract_numeric_value(value)
            
            # Utiliser les indicateurs nettoyés
            entry_indicators = entry_indicators_clean
            exit_indicators = exit_indicators_clean
            
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
            
            # 🔥 FIX: Extraire et nettoyer les prix AVANT les calculs (peuvent être des dicts)
            entry_price_raw = trade_data.get('entry_price')
            tp_price_raw = trade_data.get('tp_price')
            sl_price_raw = trade_data.get('sl_price')
            exit_price_raw = trade_data.get('exit_price')
            
            entry_price = _extract_numeric_value(entry_price_raw) if entry_price_raw is not None else None
            tp_price = _extract_numeric_value(tp_price_raw) if tp_price_raw is not None else None
            sl_price = _extract_numeric_value(sl_price_raw) if sl_price_raw is not None else None
            exit_price = _extract_numeric_value(exit_price_raw) if exit_price_raw is not None else None
            
            # Calculer risk_reward_ratio
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
                max_favorable_excursion = _extract_numeric_value(trade_data.get('max_pnl_reached'))
            if max_adverse_excursion is None:
                max_adverse_excursion = _extract_numeric_value(trade_data.get('min_pnl_reached'))
            
            # Extraire scalability data
            entry_scalability = trade_data.get('entry_scalability', {}) or {}
            if not isinstance(entry_scalability, dict):
                entry_scalability = {}
            
            # 🔥 FIX: S'assurer que tous les champs de scalability sont des valeurs numériques, pas des dicts
            entry_scalability_clean = {}
            for key, value in entry_scalability.items():
                if isinstance(value, dict):
                    entry_scalability_clean[key] = _extract_numeric_value(value)
                elif isinstance(value, (int, float)):
                    entry_scalability_clean[key] = float(value)
                elif value is None:
                    entry_scalability_clean[key] = None
                else:
                    # Essayer de convertir en float
                    entry_scalability_clean[key] = _extract_numeric_value(value)
            
            # Utiliser les données de scalabilité nettoyées
            entry_scalability = entry_scalability_clean
            
            # 🔥 FIX: Extraire et nettoyer size_usdt AVANT de calculer slippage_usdt
            size_usdt_raw = trade_data.get('size_usdt')
            size_usdt = _extract_numeric_value(size_usdt_raw) if size_usdt_raw is not None else None
            
            # Calculer slippage_usdt
            slippage_pct_raw = trade_data.get('slippage', 0) or 0
            slippage_pct = _extract_numeric_value(slippage_pct_raw) if slippage_pct_raw is not None else 0
            slippage_usdt = (slippage_pct / 100) * (size_usdt or 0) if slippage_pct and size_usdt else 0
            
            # Extraire config_snapshot
            # 🔥 FIX BUG #1: Utiliser serialize_config_safe() pour éviter les erreurs de sérialisation
            config_snapshot = trade_data.get('config_snapshot', {})
            if config_snapshot:
                try:
                    config_snapshot_safe = serialize_config_safe(config_snapshot)
                    config_snapshot = json.dumps(config_snapshot_safe)
                except Exception as e:
                    logger.error(f"❌ Erreur sérialisation config_snapshot pour trade: {e}", exc_info=True)
                    config_snapshot = None
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
                entry_price,  # entry_price (nettoyé)
                exit_price,  # exit_price (nettoyé)
                size_usdt,  # size_usdt (nettoyé)
                tp_price,  # tp_price (nettoyé)
                sl_price,  # sl_price (nettoyé)
                _extract_numeric_value(trade_data.get('gross_pnl_usdt')) or 0,
                _extract_numeric_value(trade_data.get('gross_pnl_pct')) or 0,  # pnl_pct (gross)
                _extract_numeric_value(trade_data.get('gross_pnl_usdt')) or 0,  # pnl_usdt (gross) - même valeur que gross_pnl_usdt (redondant mais présent dans le schéma)
                _extract_numeric_value(trade_data.get('net_pnl_usdt')) or 0,
                _extract_numeric_value(trade_data.get('net_pnl_pct')) or 0,
                _extract_numeric_value(trade_data.get('fees')) or 0,  # fees_usdt
                _extract_numeric_value(trade_data.get('slippage')) or 0,  # slippage_pct
                slippage_usdt,  # slippage_usdt
                trade_data.get('reason'),  # exit_reason
                _extract_numeric_value(trade_data.get('duration_seconds')),
                trade_data.get('tp_sl_mode'),
                trade_data.get('break_even_triggered', False),  # break_even_set
                trade_data.get('break_even_triggered_at'),  # break_even_triggered_at
                trade_data.get('trailing_stop_triggered', False),  # trailing_stop_activated
                trade_data.get('trailing_stop_triggered_at'),  # trailing_stop_triggered_at
                trade_data.get('partial_tp_triggered', False),  # partial_tp_executed
                trade_data.get('partial_tp_triggered_at'),  # partial_tp_triggered_at
                _extract_numeric_value(trade_data.get('partial_tp_profit')),  # partial_tp_profit
                _extract_numeric_value(trade_data.get('partial_tp_percent')),  # partial_tp_percent
                len(tp_escalier_levels_hit),  # tp_escalier_levels_executed (count)
                _extract_numeric_value(tp_escalier_profits) if tp_escalier_profits is not None else 0,  # tp_escalier_profits (somme)
                # Early Invalidation
                trade_data.get('early_invalidation_triggered', False),  # early_invalidation_triggered
                trade_data.get('early_invalidation_triggered_at'),  # early_invalidation_triggered_at
                _extract_numeric_value(trade_data.get('early_invalidation_threshold')),  # early_invalidation_threshold
                _extract_numeric_value(trade_data.get('early_invalidation_elapsed')),  # early_invalidation_elapsed
                _extract_numeric_value(trade_data.get('early_invalidation_atr_pct')),  # early_invalidation_atr_pct
                _extract_numeric_value(trade_data.get('early_invalidation_pnl_pct')),  # early_invalidation_pnl_pct
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
                _extract_numeric_value(entry_indicators.get('score')),  # entry_score
                _extract_numeric_value(entry_scalability.get('spread_pct')),  # entry_spread_pct
                _extract_numeric_value(entry_scalability.get('balance_score')),  # entry_balance_score
                entry_conditions,  # entry_conditions (TEXT[])
                len(entry_conditions),  # entry_condition_count
                # Métriques temporelles entry
                entry_hour, entry_day,
                # Indicateurs de sortie
                exit_indicators.get('rsi_1m'), exit_indicators.get('rsi_5m'),
                exit_indicators.get('macd_hist_1m'), exit_indicators.get('macd_hist_5m'),
                exit_indicators.get('adx_1m'), exit_indicators.get('adx_5m'),
                exit_indicators.get('atr_pct_1m'), exit_indicators.get('atr_pct_5m'),
                _extract_numeric_value(exit_indicators.get('score')),  # exit_score
                _extract_numeric_value(exit_indicators.get('volume_ratio_1m')), _extract_numeric_value(exit_indicators.get('volume_ratio_5m')),
                _extract_numeric_value(exit_indicators.get('spread_pct')),  # exit_spread_pct
                _extract_numeric_value(exit_indicators.get('balance_score')),  # exit_balance_score
                _extract_numeric_value(entry_to_exit_price_change_pct) if entry_to_exit_price_change_pct is not None else None,
                # Métriques temporelles exit
                exit_hour, exit_day,
                # Métriques de position
                _extract_numeric_value(max_favorable_excursion) if max_favorable_excursion is not None else None,
                _extract_numeric_value(max_adverse_excursion) if max_adverse_excursion is not None else None,
                _extract_numeric_value(max_favorable_excursion_usdt) if max_favorable_excursion_usdt is not None else None,
                _extract_numeric_value(max_adverse_excursion_usdt) if max_adverse_excursion_usdt is not None else None,
                # Métriques de qualité
                _extract_numeric_value(risk_reward_ratio) if risk_reward_ratio is not None else None,
                None,  # profit_factor (non calculé pour l'instant)
                # Métriques de performance additionnelles
                _extract_numeric_value(entry_to_max_profit_price_change_pct) if entry_to_max_profit_price_change_pct is not None else None,
                _extract_numeric_value(entry_to_max_loss_price_change_pct) if entry_to_max_loss_price_change_pct is not None else None,
                _extract_numeric_value(max_drawdown_pct) if max_drawdown_pct is not None else None,
                _extract_numeric_value(max_drawdown_usdt) if max_drawdown_usdt is not None else None,
                # Scalability
                _extract_numeric_value(entry_scalability.get('book_depth')),  # entry_book_depth
                _extract_numeric_value(entry_scalability.get('bid_vol')),  # entry_bid_vol
                _extract_numeric_value(entry_scalability.get('ask_vol')),  # entry_ask_vol
                _extract_numeric_value(entry_scalability.get('orderbook_imbalance')),  # entry_orderbook_imbalance
                # Paramètres du scan de scalabilité
                _extract_numeric_value(entry_scalability.get('recent_volume') or entry_scalability.get('recentVolume')),  # entry_recent_volume
                _extract_numeric_value(entry_scalability.get('vol5')),  # entry_vol5
                _extract_numeric_value(entry_scalability.get('vol15')),  # entry_vol15
                _extract_numeric_value(entry_scalability.get('scalability_score') or entry_scalability.get('score')),  # entry_scalability_score
                # Configuration snapshot
                config_snapshot,
                win
            )
            
            if any(isinstance(p, dict) for p in params):
                logger.error(
                    "⚠️ Paramètre dict détecté dans log_trade pour %s | types=%s",
                    trade_data.get('symbol'),
                    [type(p).__name__ for p in params]
                )
            
            # Vérifier le nombre de paramètres AVANT l'exécution
            param_count = len(params)
            placeholder_count = query.count('%s')
            if param_count != placeholder_count:
                logger.error(f"❌ Déséquilibre paramètres: {param_count} paramètres pour {placeholder_count} placeholders")
                logger.error(f"   Symbol: {trade_data.get('symbol')}")
                logger.error(f"   entry_conditions type: {type(entry_conditions)}, value: {entry_conditions}")
                # Afficher les 20 premiers et derniers paramètres pour debug
                logger.error(f"   Premiers paramètres (20): {params[:20]}")
                logger.error(f"   Derniers paramètres (20): {params[-20:]}")
                # Ne pas logger le trade si déséquilibre
                return None
            else:
                logger.debug(f"✅ Nombre de paramètres OK: {param_count} paramètres pour {placeholder_count} placeholders")
            
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
        
        # 🔥 FIX BUG #3: Utiliser timezone.utc pour PostgreSQL TIMESTAMPTZ
        now = datetime.now(timezone.utc)
        time_since_flush = (now - self.last_flush_time).total_seconds()
        should_flush = force or (
            len(self.scan_buffer) >= self.batch_size or
            len(self.opportunity_buffer) >= self.batch_size or
            time_since_flush >= self.batch_flush_interval
        )
        
        if not should_flush:
            return
        
        with self.buffer_lock:
            scans_count = len(self.scan_buffer)
            opportunities_count = len(self.opportunity_buffer)
            
            # Flush scans
            if self.scan_buffer:
                try:
                    logger.info(f"🔄 Flush {scans_count} scan(s) vers PostgreSQL (force={force})")
                    self._batch_insert_scans(list(self.scan_buffer))
                    self.scan_buffer.clear()
                    logger.info(f"✅ {scans_count} scan(s) flushés avec succès")
                except Exception as e:
                    logger.error(f"❌ Erreur flush scans: {e}")
            
            # Flush opportunities
            if self.opportunity_buffer:
                try:
                    logger.info(f"🔄 Flush {opportunities_count} opportunité(s) vers PostgreSQL (force={force})")
                    self._batch_insert_opportunities(list(self.opportunity_buffer))
                    self.opportunity_buffer.clear()
                    logger.info(f"✅ {opportunities_count} opportunité(s) flushées avec succès")
                except Exception as e:
                    logger.error(f"❌ Erreur flush opportunities: {e}")
            
            if scans_count > 0 or opportunities_count > 0:
                logger.info(f"📊 Flush buffers: {scans_count} scan(s), {opportunities_count} opportunité(s)")
            
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
                
                # 🔥 FIX: Récupérer le prix avec fallbacks multiples (pour éviter NULL)
                price = market_data.get('price')
                if price is None:
                    # Fallback 1: Depuis scan_data directement
                    price = scan_data.get('price')
                if price is None:
                    # Fallback 2: Depuis analysis_1m ou analysis_5m si disponible
                    analysis_1m = scan_data.get('analysis_1m', {})
                    if isinstance(analysis_1m, dict):
                        price = analysis_1m.get('price')
                    if price is None:
                        analysis_5m = scan_data.get('analysis_5m', {})
                        if isinstance(analysis_5m, dict):
                            price = analysis_5m.get('price')
                # Extraire la valeur numérique si c'est un dict
                if isinstance(price, dict):
                    price = price.get('price') or price.get('lastPrice') or price.get('close') or price.get('value')
                # Vérifier que price est un nombre
                if price is not None and not isinstance(price, (int, float)):
                    try:
                        price = float(price)
                    except (ValueError, TypeError):
                        logger.warning(f"⚠️ Prix invalide pour {symbol} dans batch: {price} (type: {type(price)})")
                        price = None
                
                # Si le prix est toujours None, on ne peut pas insérer (contrainte NOT NULL)
                if price is None:
                    logger.error(f"❌ Prix manquant pour {symbol} dans batch insert, scan ignoré")
                    continue
                
                # Construire tuple de valeurs (même ordre que dans log_scan)
                value_tuple = (
                    session_id, symbol, scan_data.get('scan_duration_ms'),
                    price, market_data.get('spread_pct'),
                    market_data.get('book_depth'), market_data.get('balance_score'),
                    market_data.get('bid_vol'), market_data.get('ask_vol'),
                    market_data.get('orderbook_imbalance_ratio'),
                    # Paramètres du scan de scalabilité
                    market_data.get('recent_volume') or scan_data.get('recent_volume') or scan_data.get('recentVolume'),
                    market_data.get('vol5') or scan_data.get('vol5'),
                    market_data.get('vol15') or scan_data.get('vol15'),
                    market_data.get('scalability_score') or scan_data.get('scalability_score') or scan_data.get('score'),
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
                'recent_volume', 'vol5', 'vol15', 'scalability_score',
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
                symbol = opp_item['symbol']
                
                # 🔥 FIX: Si scan_id = 0 (temporaire), essayer de le résoudre depuis scan_logs
                if scan_id == 0 or scan_id is None:
                    # Chercher le scan_log_id correspondant dans scan_logs
                    # en utilisant symbol et timestamp récent (dernières 5 minutes)
                    resolve_query = """
                        SELECT id FROM scan_logs 
                        WHERE symbol = %s 
                          AND is_opportunity = true
                          AND timestamp > NOW() - INTERVAL '5 minutes'
                        ORDER BY timestamp DESC 
                        LIMIT 1
                    """
                    cursor.execute(resolve_query, (symbol,))
                    result = cursor.fetchone()
                    if result:
                        scan_id = result[0]
                        logger.debug(f"✅ scan_id résolu pour {symbol}: {scan_id}")
                    else:
                        logger.warning(f"⚠️ Impossible de résoudre scan_id pour {symbol}, utilisation de 0")
                        scan_id = 0
                
                session_id = opp_item['session_id']
                opp_data = opp_item['opportunity_data']
                
                # Convertir conditions_matched en liste de strings
                conditions_matched = opp_data.get('conditions_matched', [])
                if isinstance(conditions_matched, dict):
                    # Si c'est un dict, prendre les clés ou les valeurs selon le cas
                    conditions_matched = [str(k) for k in conditions_matched.keys()] if conditions_matched else []
                elif isinstance(conditions_matched, list):
                    # S'assurer que tous les éléments sont des strings
                    conditions_matched = [str(item) for item in conditions_matched if item is not None]
                else:
                    # Autre type (str, int, etc.) -> convertir en liste
                    conditions_matched = [str(conditions_matched)] if conditions_matched is not None else []
                
                # Extraire et valider les valeurs (s'assurer qu'elles ne sont pas des dicts)
                entry_price = opp_data.get('entry_price') or opp_data.get('entry_suggested')
                tp_price = opp_data.get('tp_price') or opp_data.get('tp_suggested')
                sl_price = opp_data.get('sl_price') or opp_data.get('sl_suggested')
                tp_sl_mode = opp_data.get('tp_sl_mode', 'FIXE')
                setup_score = opp_data.get('setup_score')
                direction = opp_data.get('direction')
                status = opp_data.get('status', 'PENDING')
                
                # S'assurer que les prix sont des nombres, pas des dicts
                if isinstance(entry_price, dict):
                    entry_price = entry_price.get('price') or entry_price.get('value')
                if isinstance(tp_price, dict):
                    tp_price = tp_price.get('price') or tp_price.get('value')
                if isinstance(sl_price, dict):
                    sl_price = sl_price.get('price') or sl_price.get('value')
                if isinstance(tp_sl_mode, dict):
                    tp_sl_mode = tp_sl_mode.get('mode') or 'FIXE'
                # S'assurer que setup_score est un nombre, pas un dict
                if isinstance(setup_score, dict):
                    setup_score = setup_score.get('score') or setup_score.get('value') or setup_score.get('totalScore')
                # S'assurer que direction est une string, pas un dict
                if isinstance(direction, dict):
                    direction = direction.get('direction') or direction.get('value') or str(direction)
                # S'assurer que status est une string, pas un dict
                if isinstance(status, dict):
                    status = status.get('status') or status.get('value') or 'PENDING'
                
                value_tuple = (
                    scan_id, session_id, symbol,
                    str(status) if status else 'PENDING',
                    str(direction) if direction else None,
                    float(setup_score) if setup_score is not None and not isinstance(setup_score, dict) else None,
                    conditions_matched,  # TEXT[] - liste de strings
                    float(entry_price) if entry_price is not None and not isinstance(entry_price, dict) else None,  # entry_suggested
                    float(tp_price) if tp_price is not None and not isinstance(tp_price, dict) else None,  # tp_suggested
                    float(sl_price) if sl_price is not None and not isinstance(sl_price, dict) else None,  # sl_suggested
                    str(tp_sl_mode) if tp_sl_mode else 'FIXE'  # tp_sl_mode
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
        if not self.enabled:
            return
        
        # Flush final des buffers
        logger.info("🔄 Flush final des buffers PostgreSQL...")
        scans_before = len(self.scan_buffer)
        opportunities_before = len(self.opportunity_buffer)
        
        self._flush_buffers(force=True)
        
        if scans_before > 0 or opportunities_before > 0:
            logger.info(f"✅ Flush final terminé: {scans_before} scan(s) et {opportunities_before} opportunité(s) flushés")
        else:
            logger.info("✅ Flush final terminé: aucun élément en attente")
        
        if self.pool:
            try:
                self.pool.closeall()
                logger.info("✅ Pool PostgreSQL fermé")
            except Exception as e:
                logger.error(f"❌ Erreur fermeture pool: {e}")

