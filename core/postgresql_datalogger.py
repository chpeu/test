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

from utils.pricing import get_preferred_price

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
        for key in ['value', 'price', 'referencePrice', 'lastPrice', 'score', 'rsi', 'macd', 'adx', 'atr', 'volume', 'spread', 'balance', 'depth', 'vol5', 'vol15']:
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
            self.pool = None
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
        price = get_preferred_price(market_data, None)
        if price is None:
            price = get_preferred_price(scan_data.get('price'), None)
        if price is None:
            analysis_1m = scan_data.get('analysis_1m', {})
            if isinstance(analysis_1m, dict):
                price = get_preferred_price(analysis_1m, None)
        if price is None:
            analysis_5m = scan_data.get('analysis_5m', {})
            if isinstance(analysis_5m, dict):
                price = get_preferred_price(analysis_5m, None)

        # Si le prix est toujours None, utiliser 0 comme fallback et logger warning
        if price is None or price == 0:
            if price is None:
                price = 0.0
                logger.warning(f"⚠️ Prix manquant pour {symbol} dans log_scan (batch), utilisation price=0")
            # Continuer le logging avec price=0 pour ne pas bloquer l'analyse ML
        
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
            # 🔥 FIX: Assurer des dicts non-vides avec defaults explicites
            indicators_1m = scan_data.get('indicators_1m') or {}
            indicators_5m = scan_data.get('indicators_5m') or {}
            filters = scan_data.get('filters') or {}
            scores = scan_data.get('scores') or {}
            patterns = scan_data.get('patterns') or {}
            market_data = scan_data.get('market_data') or {}
            
            # Requête d'insertion
            query = """
                INSERT INTO scan_logs (
                    timestamp, session_id, symbol, scan_duration_ms,
                    price, spread_pct, book_depth, balance_score,
                    bid_vol, ask_vol, orderbook_imbalance_ratio,
                    recent_volume, vol5, vol15, scalability_score,
                    -- 🔥 ORDER FLOW: 6 nouvelles métriques
                    delta_volume, imbalance_normalized, spread_volatility_5,
                    book_depth_ratio, volume_acceleration, price_momentum_5,
                    
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
                    
                    -- 🔥 ML Confidence (confiance réelle du modèle)
                    ml_confidence,
                    
                    -- Params snapshot
                    params_snapshot,
                    
                    -- Config extracted from params
                    config_min_score_required, config_snr_threshold,
                    config_atr_min_1m, config_atr_max_1m,
                    config_atr_min_5m, config_atr_max_5m,
                    config_volume_multiplier, config_use_confluence,
                    config_use_anti_whipsaw, config_whipsaw_lookback,
                    config_whipsaw_threshold_pct, config_whipsaw_max_alternations,
                    config_use_retest_confirmation, config_retest_tolerance_pct,
                    config_retest_timeout_seconds, config_use_cooldown,
                    config_cooldown_seconds, config_cooldown_same_symbol,
                    config_use_candle_close, config_candle_close_threshold_seconds,
                    config_use_momentum_continuity, config_momentum_lookback
                )
                VALUES (
                    NOW(), %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s,
                    %s,
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
            """
            
            # 🔥 FIX: Récupérer le prix avec fallbacks multiples (pour éviter NULL)
            price = get_preferred_price(market_data, None)
            if price is None:
                price = get_preferred_price(scan_data.get('price'), None)
            if price is None:
                analysis_1m = scan_data.get('analysis_1m', {})
                if isinstance(analysis_1m, dict):
                    price = get_preferred_price(analysis_1m, None)
            if price is None:
                analysis_5m = scan_data.get('analysis_5m', {})
                if isinstance(analysis_5m, dict):
                    price = get_preferred_price(analysis_5m, None)
            if price is not None and not isinstance(price, (int, float)):
                try:
                    price = float(price)
                except (ValueError, TypeError):
                    logger.warning(f"⚠️ Prix invalide pour {symbol} dans log_scan: {price} (type: {type(price)})")
                    price = None
            
            # Si le prix est toujours None, utiliser 0 comme fallback et logger warning
            if price is None or price == 0:
                if price is None:
                    price = 0.0
                    logger.warning(f"⚠️ Prix manquant pour {symbol} dans log_scan, utilisation price=0")
                # Continuer le logging avec price=0 pour ne pas bloquer l'analyse ML
            
            # 🔥 FIX: Assurer des valeurs par défaut pour éviter les NULL critiques
            scan_duration = scan_data.get('scan_duration_ms')
            if scan_duration is None:
                scan_duration = 0.0  # Défaut si non fourni
            
            # Assurer params_snapshot sérialisable (même si vide)
            params_snap = scan_data.get('params_snapshot')
            if not params_snap or not isinstance(params_snap, dict):
                params_snap = {}
            
            # 🔥 ORDER FLOW: Calcul automatique si manquant
            bid_vol = market_data.get('bid_vol') or market_data.get('bidVol') or scan_data.get('bid_vol') or scan_data.get('bidVol')
            ask_vol = market_data.get('ask_vol') or market_data.get('askVol') or scan_data.get('ask_vol') or scan_data.get('askVol')
            
            delta_volume = market_data.get('delta_volume') or scan_data.get('delta_volume')
            imbalance_normalized = market_data.get('imbalance_normalized') or scan_data.get('imbalance_normalized')
            book_depth_ratio = market_data.get('book_depth_ratio') or scan_data.get('book_depth_ratio')
            
            # Calculer automatiquement si manquant et bid/ask disponibles
            if delta_volume is None and bid_vol and ask_vol:
                delta_volume = float(bid_vol) - float(ask_vol)
            if imbalance_normalized is None and bid_vol and ask_vol:
                total = float(bid_vol) + float(ask_vol)
                imbalance_normalized = (float(bid_vol) - float(ask_vol)) / total if total > 0 else 0.0
            if book_depth_ratio is None and bid_vol and ask_vol and float(ask_vol) > 0:
                book_depth_ratio = float(bid_vol) / float(ask_vol)
            
            # Préparer les paramètres
            params = (
                session_id, symbol, scan_duration,
                price, market_data.get('spread_pct'),
                market_data.get('book_depth'), market_data.get('balance_score'),
                bid_vol, ask_vol,
                market_data.get('orderbook_imbalance_ratio'),
                # Paramètres du scan de scalabilité
                market_data.get('recent_volume') or scan_data.get('recent_volume') or scan_data.get('recentVolume'),
                market_data.get('vol5') or scan_data.get('vol5'),
                market_data.get('vol15') or scan_data.get('vol15'),
                market_data.get('scalability_score') or scan_data.get('scalability_score') or scan_data.get('score'),
                
                # 🔥 ORDER FLOW: 6 métriques (calculées auto si manquantes)
                delta_volume,
                imbalance_normalized,
                market_data.get('spread_volatility_5') or scan_data.get('spread_volatility_5'),
                book_depth_ratio,
                market_data.get('volume_acceleration') or scan_data.get('volume_acceleration'),
                market_data.get('price_momentum_5') or scan_data.get('price_momentum_5'),
                
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
                
                # Filtres (avec defaults pour booléens False si absent)
                filters.get('snr_1m'), filters.get('snr_5m'),
                filters.get('snr_passed_1m', False), filters.get('snr_passed_5m', False),
                filters.get('breakout_distance_1m'), filters.get('breakout_distance_5m'),
                filters.get('breakout_passed_1m', False), filters.get('breakout_passed_5m', False),
                filters.get('wick_ratio_1m'), filters.get('wick_ratio_5m'),
                filters.get('wick_passed_1m', False), filters.get('wick_passed_5m', False),
                filters.get('atr_optimal_passed_1m', False), filters.get('atr_optimal_passed_5m', False),
                filters.get('volume_filter_passed_1m', False), filters.get('volume_filter_passed_5m', False),
                
                # Confluence
                scan_data.get('use_confluence'), scan_data.get('confluence_met', False),
                scores.get('score_1m'), scores.get('score_5m'), scores.get('score_total'),
                scores.get('score_long_1m', 0), scores.get('score_short_1m', 0),
                scores.get('score_long_5m', 0), scores.get('score_short_5m', 0),
                scan_data.get('timeframes_aligned', False),
                
                # Patterns
                patterns.get('pattern_1m'), patterns.get('pattern_multi_1m'),
                patterns.get('pattern_5m'), patterns.get('pattern_multi_5m'),
                
                # Trend
                scan_data.get('trend_timeframe', '15m'),
                scan_data.get('trend_direction'), scan_data.get('trend_strength'),
                scan_data.get('trend_bonus', 0),
                
                # Divergence
                scan_data.get('divergence_detected', False),
                scan_data.get('divergence_type'), scan_data.get('divergence_bonus', 0),
                
                # Décision
                scan_data.get('is_opportunity', False),
                scan_data.get('opportunity_direction'),
                scan_data.get('reject_reason'), scan_data.get('reject_reason_category'),
                
                # 🔥 ML Confidence (confiance réelle du modèle, si disponible)
                scan_data.get('ml_confidence'),
                
                # Params
                json.dumps(params_snap),
                
                # Config extracted
                params_snap.get('min_score_required'),
                params_snap.get('snr_threshold'),
                params_snap.get('optimal_atr_min_1m'),
                params_snap.get('optimal_atr_max_1m'),
                params_snap.get('optimal_atr_min_5m'),
                params_snap.get('optimal_atr_max_5m'),
                params_snap.get('volume_multiplier'),
                params_snap.get('use_confluence'),
                params_snap.get('use_anti_whipsaw'),
                params_snap.get('whipsaw_lookback'),
                params_snap.get('whipsaw_threshold_pct'),
                params_snap.get('whipsaw_max_alternations'),
                params_snap.get('use_retest_confirmation'),
                params_snap.get('retest_tolerance_pct'),
                params_snap.get('retest_timeout_seconds'),
                params_snap.get('use_cooldown'),
                params_snap.get('cooldown_seconds'),
                params_snap.get('cooldown_same_symbol'),
                params_snap.get('use_candle_close'),
                params_snap.get('candle_close_threshold_seconds'),
                params_snap.get('use_momentum_continuity'),
                params_snap.get('momentum_lookback')
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
    
    def update_ml_confidence(
        self,
        symbol: str,
        ml_confidence: float,
        minutes_ago: int = 5
    ) -> bool:
        """
        🔥 FIX: Mettre à jour ml_confidence pour le scan le plus récent d'un symbole
        
        Cette méthode est appelée APRÈS la prédiction ML pour mettre à jour
        le scan_log qui a été créé AVANT la prédiction.
        
        Args:
            symbol: Symbole de la paire
            ml_confidence: Confiance ML en pourcentage (ex: 34.7)
            minutes_ago: Chercher dans les N dernières minutes (défaut: 5)
        
        Returns:
            True si mise à jour réussie, False sinon
        """
        if not self.enabled:
            return False
        
        try:
            # Mettre à jour le scan le plus récent pour ce symbole
            query = """
                UPDATE scan_logs 
                SET ml_confidence = %s
                WHERE symbol = %s 
                AND timestamp > NOW() - INTERVAL '%s minutes'
                AND ml_confidence IS NULL
                ORDER BY timestamp DESC
                LIMIT 1
            """
            # Note: PostgreSQL ne supporte pas LIMIT dans UPDATE directement
            # On utilise une sous-requête
            query = """
                UPDATE scan_logs 
                SET ml_confidence = %s
                WHERE id = (
                    SELECT id FROM scan_logs 
                    WHERE symbol = %s 
                    AND timestamp > NOW() - INTERVAL '%s minutes'
                    AND ml_confidence IS NULL
                    ORDER BY timestamp DESC
                    LIMIT 1
                )
            """
            
            result = self._execute_query(query, (ml_confidence, symbol, minutes_ago))
            if result is not None:
                logger.info(f"✅ ml_confidence mis à jour pour {symbol}: {ml_confidence:.1f}%")
                return True
            return False
            
        except Exception as e:
            logger.error(f"❌ Erreur update ml_confidence pour {symbol}: {e}")
            return False
    
    def get_ml_confidence_for_symbol(
        self,
        symbol: str,
        minutes_ago: int = 60
    ) -> Optional[float]:
        """
        🔥 FIX: Récupérer ml_confidence depuis PostgreSQL pour un symbole
        
        Cette méthode est utilisée pour charger ml_confidence si la position
        a été ouverte avant que le fix soit en place.
        
        Args:
            symbol: Symbole de la paire (ex: 'SHIB/USDT')
            minutes_ago: Chercher dans les N dernières minutes (défaut: 60)
        
        Returns:
            ml_confidence en pourcentage ou None si non trouvé
        """
        if not self.enabled:
            return None
        
        try:
            query = """
                SELECT ml_confidence FROM scan_logs 
                WHERE symbol = %s 
                AND timestamp > NOW() - (INTERVAL '1 minute' * %s)
                AND ml_confidence IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 1
            """
            
            result = self._execute_query(query, (symbol, minutes_ago), fetch=True)
            if result and len(result) > 0 and result[0][0] is not None:
                ml_conf = float(result[0][0])
                logger.debug(f"📊 ml_confidence récupéré pour {symbol}: {ml_conf:.1f}%")
                return round(ml_conf, 1)  # Arrondir au dixième
            return None
            
        except Exception as e:
            logger.error(f"❌ Erreur get ml_confidence pour {symbol}: {e}")
            return None
    
    def get_adaptive_sizing_for_symbol(
        self,
        symbol: str,
        minutes_ago: int = 60
    ) -> Optional[float]:
        """
        🔥 FIX: Récupérer adaptive_sizing_multiplier depuis PostgreSQL
        
        Args:
            symbol: Symbole de la paire
            minutes_ago: Chercher dans les N dernières minutes
        
        Returns:
            adaptive_sizing_multiplier ou None
        """
        if not self.enabled:
            return None
        
        try:
            query = """
                SELECT adaptive_sizing_multiplier FROM trades 
                WHERE symbol = %s 
                AND timestamp_entry > NOW() - (INTERVAL '1 minute' * %s)
                AND adaptive_sizing_multiplier IS NOT NULL
                ORDER BY timestamp_entry DESC
                LIMIT 1
            """
            
            result = self._execute_query(query, (symbol, minutes_ago), fetch=True)
            if result and len(result) > 0 and result[0][0] is not None:
                sizing = float(result[0][0])
                logger.debug(f"📊 sizing_multiplier récupéré pour {symbol}: {sizing:.2f}x")
                return sizing
            return None
            
        except Exception as e:
            logger.error(f"❌ Erreur get sizing_multiplier pour {symbol}: {e}")
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
                    score_long, score_short, score_min_required,
                    trend_bonus, divergence_bonus,
                    conditions_matched, condition_count,
                    entry_suggested, tp_suggested, sl_suggested,
                    tp_sl_mode, setup_reason
                )
                VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            
            # 🔥 FIX: Extraire les nouveaux champs
            score_long = opportunity_data.get('score_long')
            score_short = opportunity_data.get('score_short')
            score_min_required = opportunity_data.get('score_min_required')
            trend_bonus = opportunity_data.get('trend_bonus')
            divergence_bonus = opportunity_data.get('divergence_bonus')
            condition_count = opportunity_data.get('condition_count', len(conditions_matched))
            setup_reason = opportunity_data.get('setup_reason')
            
            params = (
                scan_id, session_id, symbol,
                str(status) if status else 'PENDING',
                str(direction) if direction else None,
                float(setup_score) if setup_score is not None else None,
                # Nouveaux champs
                float(score_long) if score_long is not None else None,
                float(score_short) if score_short is not None else None,
                float(score_min_required) if score_min_required is not None else None,
                float(trend_bonus) if trend_bonus is not None else None,
                float(divergence_bonus) if divergence_bonus is not None else None,
                # Conditions
                conditions_matched,  # TEXT[] - liste de strings
                int(condition_count) if condition_count is not None else len(conditions_matched),
                # Prix
                float(entry_price) if entry_price is not None else None,  # entry_suggested
                float(tp_price) if tp_price is not None else None,  # tp_suggested
                float(sl_price) if sl_price is not None else None,  # sl_suggested
                str(tp_sl_mode) if tp_sl_mode else 'FIXE',  # tp_sl_mode
                str(setup_reason) if setup_reason else None  # setup_reason
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
            
            # 🔥 FIX: Extraire config_snapshot + colonnes config_*
            config_snapshot_raw = trade_data.get('config_snapshot') or {}
            config_snapshot_dict: Dict[str, Any] = {}
            if isinstance(config_snapshot_raw, str):
                try:
                    config_snapshot_dict = json.loads(config_snapshot_raw)
                except Exception:
                    config_snapshot_dict = {}
            elif isinstance(config_snapshot_raw, dict):
                config_snapshot_dict = config_snapshot_raw

            config_min_score_required = _extract_numeric_value(config_snapshot_dict.get('min_score_required'))
            config_snr_threshold = _extract_numeric_value(config_snapshot_dict.get('snr_threshold'))
            config_optimal_atr_min_1m = _extract_numeric_value(config_snapshot_dict.get('optimal_atr_min_1m'))
            config_optimal_atr_max_1m = _extract_numeric_value(config_snapshot_dict.get('optimal_atr_max_1m'))
            config_optimal_atr_min_5m = _extract_numeric_value(config_snapshot_dict.get('optimal_atr_min_5m'))
            config_optimal_atr_max_5m = _extract_numeric_value(config_snapshot_dict.get('optimal_atr_max_5m'))
            config_volume_multiplier = _extract_numeric_value(config_snapshot_dict.get('volume_multiplier'))
            config_use_confluence = config_snapshot_dict.get('use_confluence')
            config_use_anti_whipsaw = config_snapshot_dict.get('use_anti_whipsaw')
            config_whipsaw_lookback = _extract_numeric_value(config_snapshot_dict.get('whipsaw_lookback'))
            config_whipsaw_threshold_pct = _extract_numeric_value(config_snapshot_dict.get('whipsaw_threshold_pct'))
            config_whipsaw_max_alternations = _extract_numeric_value(config_snapshot_dict.get('whipsaw_max_alternations'))
            config_use_retest_confirmation = config_snapshot_dict.get('use_retest_confirmation')
            config_retest_tolerance_pct = _extract_numeric_value(config_snapshot_dict.get('retest_tolerance_pct'))
            config_retest_timeout_seconds = _extract_numeric_value(config_snapshot_dict.get('retest_timeout_seconds'))
            config_use_cooldown = config_snapshot_dict.get('use_cooldown')
            config_cooldown_seconds = _extract_numeric_value(config_snapshot_dict.get('cooldown_seconds'))
            config_cooldown_same_symbol = _extract_numeric_value(config_snapshot_dict.get('cooldown_same_symbol'))
            config_use_candle_close = config_snapshot_dict.get('use_candle_close')
            config_candle_close_threshold_seconds = _extract_numeric_value(config_snapshot_dict.get('candle_close_threshold_seconds'))
            config_use_momentum_continuity = config_snapshot_dict.get('use_momentum_continuity')
            config_momentum_lookback = _extract_numeric_value(config_snapshot_dict.get('momentum_lookback'))

            def _normalize_bool(val):
                if isinstance(val, str):
                    return val.lower() in ('true', '1', 'yes')
                return bool(val) if val is not None else None

            config_use_confluence = _normalize_bool(config_use_confluence)
            config_use_anti_whipsaw = _normalize_bool(config_use_anti_whipsaw)
            config_use_retest_confirmation = _normalize_bool(config_use_retest_confirmation)
            config_use_cooldown = _normalize_bool(config_use_cooldown)
            config_use_candle_close = _normalize_bool(config_use_candle_close)
            config_use_momentum_continuity = _normalize_bool(config_use_momentum_continuity)
            if isinstance(config_use_confluence, str):
                config_use_confluence = config_use_confluence.lower() in ('true', '1', 'yes')
            elif config_use_confluence is None:
                config_use_confluence = None

            config_snapshot = None
            if config_snapshot_dict:
                try:
                    config_snapshot_safe = serialize_config_safe(config_snapshot_dict)
                    config_snapshot = json.dumps(config_snapshot_safe)
                except Exception as e:
                    logger.error(f"❌ Erreur sérialisation config_snapshot pour trade: {e}", exc_info=True)
                    config_snapshot = None
            
            # Convertir entry_conditions en liste de strings pour PostgreSQL TEXT[]
            # (doit être fait avant de créer params)
            if isinstance(entry_conditions, dict):
                entry_conditions = [str(k) for k in entry_conditions.keys()] if entry_conditions else []
            elif isinstance(entry_conditions, list):
                entry_conditions = [str(c) for c in entry_conditions if c]  # Convertir en strings
            else:
                entry_conditions = [str(entry_conditions)] if entry_conditions else []
            
            gross_pnl_usdt = _extract_numeric_value(trade_data.get('gross_pnl_usdt')) or 0
            gross_pnl_pct = _extract_numeric_value(trade_data.get('gross_pnl_pct')) or 0
            net_pnl_usdt_value = _extract_numeric_value(trade_data.get('net_pnl_usdt')) or 0
            net_pnl_pct_value = _extract_numeric_value(trade_data.get('net_pnl_pct')) or 0
            fees_usdt = _extract_numeric_value(trade_data.get('fees')) or 0
            slippage_pct_value = _extract_numeric_value(trade_data.get('slippage')) or 0
            duration_seconds = _extract_numeric_value(trade_data.get('duration_seconds'))
            partial_tp_profit = _extract_numeric_value(trade_data.get('partial_tp_profit'))
            partial_tp_percent = _extract_numeric_value(trade_data.get('partial_tp_percent'))
            early_invalidation_threshold = _extract_numeric_value(trade_data.get('early_invalidation_threshold'))
            early_invalidation_elapsed = _extract_numeric_value(trade_data.get('early_invalidation_elapsed'))
            early_invalidation_atr_pct = _extract_numeric_value(trade_data.get('early_invalidation_atr_pct'))
            early_invalidation_pnl_pct = _extract_numeric_value(trade_data.get('early_invalidation_pnl_pct'))
            exit_score = _extract_numeric_value(exit_indicators.get('score'))
            exit_volume_ratio_1m = _extract_numeric_value(exit_indicators.get('volume_ratio_1m'))
            exit_volume_ratio_5m = _extract_numeric_value(exit_indicators.get('volume_ratio_5m'))
            exit_spread_pct = _extract_numeric_value(exit_indicators.get('spread_pct'))
            exit_balance_score = _extract_numeric_value(exit_indicators.get('balance_score'))
            exit_recent_volume = _extract_numeric_value(exit_indicators.get('recent_volume') or exit_indicators.get('recentVolume'))
            exit_vol5 = _extract_numeric_value(exit_indicators.get('vol5'))
            exit_vol15 = _extract_numeric_value(exit_indicators.get('vol15'))
            entry_score_value = _extract_numeric_value(entry_indicators.get('score'))
            entry_spread_pct = _extract_numeric_value(
                entry_scalability.get('spread_pct') or entry_scalability.get('spread')
            )
            # 🔥 FIX: Chercher balance_score avec plusieurs aliases
            entry_balance_score = _extract_numeric_value(
                entry_scalability.get('balance_score') 
                or entry_scalability.get('balanceScore') 
                or entry_scalability.get('balance')
            )
            entry_book_depth = _extract_numeric_value(
                entry_scalability.get('book_depth') 
                or entry_scalability.get('bookDepth') 
                or entry_scalability.get('depth')
            )
            entry_bid_vol = _extract_numeric_value(
                entry_scalability.get('bid_vol') or entry_scalability.get('bidVol')
            )
            entry_ask_vol = _extract_numeric_value(
                entry_scalability.get('ask_vol') or entry_scalability.get('askVol')
            )
            # 🔥 FIX: Calculer orderbook_imbalance si non fourni
            entry_orderbook_imbalance = _extract_numeric_value(entry_scalability.get('orderbook_imbalance'))
            if entry_orderbook_imbalance is None and entry_bid_vol and entry_ask_vol:
                total_vol = entry_bid_vol + entry_ask_vol
                if total_vol > 0:
                    entry_orderbook_imbalance = (entry_bid_vol - entry_ask_vol) / total_vol
            
            entry_recent_volume = _extract_numeric_value(
                entry_scalability.get('recent_volume') or entry_scalability.get('recentVolume')
            )
            entry_vol5 = _extract_numeric_value(entry_scalability.get('vol5'))
            entry_vol15 = _extract_numeric_value(entry_scalability.get('vol15'))
            entry_scalability_score = _extract_numeric_value(
                entry_scalability.get('scalability_score') or entry_scalability.get('score')
            )
            
            # 🔥 FIX: Colonnes market_* depuis entry_scalability ou entry_indicators
            market_volatility_entry = _extract_numeric_value(
                entry_indicators.get('volatility') or entry_scalability.get('vol5')
            )
            spread_at_entry_pct = entry_spread_pct
            volume_24h_at_entry = _extract_numeric_value(
                entry_scalability.get('volume_24h') or entry_scalability.get('volume24h')
            )
            orderbook_imbalance_entry = entry_orderbook_imbalance
            atr_at_entry = _extract_numeric_value(entry_indicators.get('atr_1m'))

            # 🔥 FIX: Extraire adaptive_sizing_multiplier
            adaptive_sizing_multiplier = _extract_numeric_value(trade_data.get('adaptive_sizing_multiplier'))
            
            fields = []
            fields.extend([
                ('timestamp_entry', entry_timestamp),
                ('timestamp_exit', exit_timestamp),
                ('session_id', session_id),
                ('opportunity_id', opportunity_id),
                ('scan_log_id', scan_log_id),
                ('symbol', trade_data.get('symbol')),
                ('direction', trade_data.get('direction')),
                ('entry_price', entry_price),
                ('exit_price', exit_price),
                ('size_usdt', size_usdt),
                ('tp_price', tp_price),
                ('sl_price', sl_price),
                ('adaptive_sizing_multiplier', adaptive_sizing_multiplier),
                ('gross_pnl_usdt', gross_pnl_usdt),
                ('pnl_pct', gross_pnl_pct),
                ('pnl_usdt', gross_pnl_usdt),
                ('net_pnl_usdt', net_pnl_usdt_value),
                ('net_pnl_pct', net_pnl_pct_value),
                ('fees_usdt', fees_usdt),
                ('slippage_pct', slippage_pct_value),
                ('slippage_usdt', slippage_usdt),
                ('exit_reason', trade_data.get('reason')),
                ('duration_seconds', duration_seconds),
                ('tp_sl_mode', trade_data.get('tp_sl_mode')),
                ('break_even_set', trade_data.get('break_even_triggered', False)),
                ('break_even_triggered_at', trade_data.get('break_even_triggered_at')),
                ('trailing_stop_activated', trade_data.get('trailing_stop_triggered', False)),
                ('trailing_stop_triggered_at', trade_data.get('trailing_stop_triggered_at')),
                ('partial_tp_executed', trade_data.get('partial_tp_triggered', False)),
                ('partial_tp_triggered_at', trade_data.get('partial_tp_triggered_at')),
                ('partial_tp_profit', partial_tp_profit),
                ('partial_tp_percent', partial_tp_percent),
                ('tp_escalier_levels_executed', len(tp_escalier_levels_hit)),
                ('tp_escalier_profits', tp_escalier_profits or 0),
                ('early_invalidation_triggered', trade_data.get('early_invalidation_triggered', False)),
                ('early_invalidation_triggered_at', trade_data.get('early_invalidation_triggered_at')),
                ('early_invalidation_threshold', early_invalidation_threshold),
                ('early_invalidation_elapsed', early_invalidation_elapsed),
                ('early_invalidation_atr_pct', early_invalidation_atr_pct),
                ('early_invalidation_pnl_pct', early_invalidation_pnl_pct),
                ('entry_rsi_1m', entry_indicators.get('rsi_1m')),
                ('entry_rsi_5m', entry_indicators.get('rsi_5m')),
                ('entry_rsi_prev_1m', entry_indicators.get('rsi_prev_1m')),
                ('entry_rsi_prev_5m', entry_indicators.get('rsi_prev_5m')),
                ('entry_macd_1m', entry_indicators.get('macd_1m')),
                ('entry_macd_signal_1m', entry_indicators.get('macd_signal_1m')),
                ('entry_macd_hist_1m', entry_indicators.get('macd_hist_1m')),
                ('entry_macd_hist_prev_1m', entry_indicators.get('macd_hist_prev_1m')),
                ('entry_macd_5m', entry_indicators.get('macd_5m')),
                ('entry_macd_signal_5m', entry_indicators.get('macd_signal_5m')),
                ('entry_macd_hist_5m', entry_indicators.get('macd_hist_5m')),
                ('entry_macd_hist_prev_5m', entry_indicators.get('macd_hist_prev_5m')),
                ('entry_adx_1m', entry_indicators.get('adx_1m')),
                ('entry_adx_5m', entry_indicators.get('adx_5m')),
                ('entry_di_plus_1m', entry_indicators.get('di_plus_1m')),
                ('entry_di_minus_1m', entry_indicators.get('di_minus_1m')),
                ('entry_di_gap_1m', entry_indicators.get('di_gap_1m')),
                ('entry_di_plus_5m', entry_indicators.get('di_plus_5m')),
                ('entry_di_minus_5m', entry_indicators.get('di_minus_5m')),
                ('entry_di_gap_5m', entry_indicators.get('di_gap_5m')),
                ('entry_ema9_1m', entry_indicators.get('ema9_1m')),
                ('entry_ema21_1m', entry_indicators.get('ema21_1m')),
                ('entry_ema_diff_pct_1m', entry_indicators.get('ema_diff_pct_1m')),
                ('entry_ema9_5m', entry_indicators.get('ema9_5m')),
                ('entry_ema21_5m', entry_indicators.get('ema21_5m')),
                ('entry_ema_diff_pct_5m', entry_indicators.get('ema_diff_pct_5m')),
                ('entry_atr_1m', entry_indicators.get('atr_1m')),
                ('entry_atr_pct_1m', entry_indicators.get('atr_pct_1m')),
                ('entry_atr_5m', entry_indicators.get('atr_5m')),
                ('entry_atr_pct_5m', entry_indicators.get('atr_pct_5m')),
                ('entry_bb_upper_1m', entry_indicators.get('bb_upper_1m')),
                ('entry_bb_middle_1m', entry_indicators.get('bb_middle_1m')),
                ('entry_bb_lower_1m', entry_indicators.get('bb_lower_1m')),
                ('entry_bb_width_1m', entry_indicators.get('bb_width_1m')),
                ('entry_bb_distance_to_lower_1m', entry_indicators.get('bb_distance_to_lower_1m')),
                ('entry_bb_distance_to_upper_1m', entry_indicators.get('bb_distance_to_upper_1m')),
                ('entry_bb_upper_5m', entry_indicators.get('bb_upper_5m')),
                ('entry_bb_middle_5m', entry_indicators.get('bb_middle_5m')),
                ('entry_bb_lower_5m', entry_indicators.get('bb_lower_5m')),
                ('entry_bb_width_5m', entry_indicators.get('bb_width_5m')),
                ('entry_bb_distance_to_lower_5m', entry_indicators.get('bb_distance_to_lower_5m')),
                ('entry_bb_distance_to_upper_5m', entry_indicators.get('bb_distance_to_upper_5m')),
                ('entry_volume_1m', entry_indicators.get('volume_1m')),
                ('entry_volume_avg_1m', entry_indicators.get('volume_avg_1m')),
                ('entry_volume_ratio_1m', entry_indicators.get('volume_ratio_1m')),
                ('entry_volume_spike_1m', entry_indicators.get('volume_spike_1m')),
                ('entry_volume_5m', entry_indicators.get('volume_5m')),
                ('entry_volume_avg_5m', entry_indicators.get('volume_avg_5m')),
                ('entry_volume_ratio_5m', entry_indicators.get('volume_ratio_5m')),
                ('entry_volume_spike_5m', entry_indicators.get('volume_spike_5m')),
                ('entry_score', entry_score_value),
                ('entry_spread_pct', entry_spread_pct),
                ('entry_balance_score', entry_balance_score),
                ('entry_conditions', entry_conditions),
                ('entry_condition_count', len(entry_conditions)),
                ('entry_hour_of_day', entry_hour),
                ('entry_day_of_week', entry_day),
                # 🔥 FIX: exit_indicators avec fallback sur entry si vide (mieux que NULL)
                ('exit_rsi_1m', exit_indicators.get('rsi_1m') or entry_indicators.get('rsi_1m')),
                ('exit_rsi_5m', exit_indicators.get('rsi_5m') or entry_indicators.get('rsi_5m')),
                ('exit_macd_hist_1m', exit_indicators.get('macd_hist_1m') or entry_indicators.get('macd_hist_1m')),
                ('exit_macd_hist_5m', exit_indicators.get('macd_hist_5m') or entry_indicators.get('macd_hist_5m')),
                ('exit_adx_1m', exit_indicators.get('adx_1m') or entry_indicators.get('adx_1m')),
                ('exit_adx_5m', exit_indicators.get('adx_5m') or entry_indicators.get('adx_5m')),
                ('exit_atr_pct_1m', exit_indicators.get('atr_pct_1m') or entry_indicators.get('atr_pct_1m')),
                ('exit_atr_pct_5m', exit_indicators.get('atr_pct_5m') or entry_indicators.get('atr_pct_5m')),
                ('exit_score', exit_score),
                # 🔥 FIX: Fallback sur entry values si exit vide
                ('exit_volume_ratio_1m', exit_volume_ratio_1m or entry_indicators.get('volume_ratio_1m')),
                ('exit_volume_ratio_5m', exit_volume_ratio_5m or entry_indicators.get('volume_ratio_5m')),
                ('exit_spread_pct', exit_spread_pct or entry_spread_pct),
                ('exit_balance_score', exit_balance_score or entry_balance_score),
                ('entry_to_exit_price_change_pct', entry_to_exit_price_change_pct),
                ('exit_hour_of_day', exit_hour),
                ('exit_day_of_week', exit_day),
                ('max_favorable_excursion', max_favorable_excursion),
                ('max_adverse_excursion', max_adverse_excursion),
                ('max_favorable_excursion_usdt', max_favorable_excursion_usdt),
                ('max_adverse_excursion_usdt', max_adverse_excursion_usdt),
                ('risk_reward_ratio', risk_reward_ratio),
                ('profit_factor', None),
                ('entry_to_max_profit_price_change_pct', entry_to_max_profit_price_change_pct),
                ('entry_to_max_loss_price_change_pct', entry_to_max_loss_price_change_pct),
                ('max_drawdown_pct', max_drawdown_pct),
                ('max_drawdown_usdt', max_drawdown_usdt),
                ('entry_book_depth', entry_book_depth),
                ('entry_bid_vol', entry_bid_vol),
                ('entry_ask_vol', entry_ask_vol),
                ('entry_orderbook_imbalance', entry_orderbook_imbalance),
                ('entry_recent_volume', entry_recent_volume),
                ('entry_vol5', entry_vol5),
                ('entry_vol15', entry_vol15),
                ('entry_scalability_score', entry_scalability_score),
                # 🔥 FIX: Ajouter market conditions columns
                ('market_volatility_entry', market_volatility_entry),
                ('spread_at_entry_pct', spread_at_entry_pct),
                ('volume_24h_at_entry', volume_24h_at_entry),
                ('orderbook_imbalance_entry', orderbook_imbalance_entry),
                ('atr_at_entry', atr_at_entry),
                # Exit market conditions (même valeurs car short-term trade)
                ('market_volatility_exit', market_volatility_entry),
                ('spread_at_exit_pct', exit_spread_pct or spread_at_entry_pct),
                ('volume_24h_at_exit', volume_24h_at_entry),
                ('orderbook_imbalance_exit', entry_orderbook_imbalance),
                ('atr_at_exit', atr_at_entry),
                # Technical indicators at entry/exit (simplified)
                ('rsi_at_entry', entry_indicators.get('rsi_1m')),
                ('macd_at_entry', entry_indicators.get('macd_hist_1m')),
                ('adx_at_entry', entry_indicators.get('adx_1m')),
                ('di_plus_entry', entry_indicators.get('di_plus_1m')),
                ('di_minus_entry', entry_indicators.get('di_minus_1m')),
                ('rsi_at_exit', exit_indicators.get('rsi_1m') or entry_indicators.get('rsi_1m')),
                ('macd_at_exit', exit_indicators.get('macd_hist_1m') or entry_indicators.get('macd_hist_1m')),
                ('adx_at_exit', exit_indicators.get('adx_1m') or entry_indicators.get('adx_1m')),
                ('di_plus_exit', exit_indicators.get('di_plus_1m') or entry_indicators.get('di_plus_1m')),
                ('di_minus_exit', exit_indicators.get('di_minus_1m') or entry_indicators.get('di_minus_1m')),
                # Risk/reward
                ('risk_reward_planned', risk_reward_ratio),
                ('risk_reward_actual', (net_pnl_pct_value / abs(max_adverse_excursion)) if max_adverse_excursion and max_adverse_excursion != 0 else None),
                # Config snapshot décomposé
                ('config_min_score_required', config_min_score_required),
                ('config_snr_threshold', config_snr_threshold),
                ('config_optimal_atr_min_1m', config_optimal_atr_min_1m),
                ('config_optimal_atr_max_1m', config_optimal_atr_max_1m),
                ('config_optimal_atr_min_5m', config_optimal_atr_min_5m),
                ('config_optimal_atr_max_5m', config_optimal_atr_max_5m),
                ('config_volume_multiplier', config_volume_multiplier),
                ('config_use_confluence', config_use_confluence),
                ('config_use_anti_whipsaw', config_use_anti_whipsaw),
                ('config_whipsaw_lookback', config_whipsaw_lookback),
                ('config_whipsaw_threshold_pct', config_whipsaw_threshold_pct),
                ('config_whipsaw_max_alternations', config_whipsaw_max_alternations),
                ('config_use_retest_confirmation', config_use_retest_confirmation),
                ('config_retest_tolerance_pct', config_retest_tolerance_pct),
                ('config_retest_timeout_seconds', config_retest_timeout_seconds),
                ('config_use_cooldown', config_use_cooldown),
                ('config_cooldown_seconds', config_cooldown_seconds),
                ('config_cooldown_same_symbol', config_cooldown_same_symbol),
                ('config_use_candle_close', config_use_candle_close),
                ('config_candle_close_threshold_seconds', config_candle_close_threshold_seconds),
                ('config_use_momentum_continuity', config_use_momentum_continuity),
                ('config_momentum_lookback', config_momentum_lookback),
                ('config_snapshot', config_snapshot),
                # 🔥 SPRINT 1: Market Regime & Circuit Breaker context
                ('entry_market_regime', trade_data.get('entry_market_regime')),
                ('entry_market_regime_avg_atr', _extract_numeric_value(trade_data.get('entry_market_regime_avg_atr'))),
                ('entry_market_regime_avg_adx', _extract_numeric_value(trade_data.get('entry_market_regime_avg_adx'))),
                ('entry_min_score_required', _extract_numeric_value(trade_data.get('entry_min_score_required'))),
                ('entry_atr_mult_sl', _extract_numeric_value(trade_data.get('entry_atr_mult_sl'))),
                ('entry_atr_mult_tp', _extract_numeric_value(trade_data.get('entry_atr_mult_tp'))),
                ('entry_cb_state', trade_data.get('entry_cb_state')),
                ('entry_consecutive_losses', trade_data.get('entry_consecutive_losses', 0)),
                ('entry_daily_pnl_pct', _extract_numeric_value(trade_data.get('entry_daily_pnl_pct'))),
                ('entry_cb_score_boost', _extract_numeric_value(trade_data.get('entry_cb_score_boost'))),
                # 🔥 SPRINT 2: Pair Scorer context
                ('entry_pair_score_adjustment', _extract_numeric_value(trade_data.get('entry_pair_score_adjustment'))),
                ('entry_effective_min_score', _extract_numeric_value(trade_data.get('entry_effective_min_score'))),
                ('win', win),
                # 🔥 FIX: ml_confidence toujours loggé (pas seulement pour live trades)
                ('ml_confidence', _extract_numeric_value(trade_data.get('ml_confidence')))
            ])
            
            # 🔥 LIVE TRADING COLUMNS (ajoutées conditionnellement si présentes)
            if trade_data.get('is_live_trade') is not None:
                fields.extend([
                    ('is_live_trade', trade_data.get('is_live_trade', False)),
                    ('is_dry_run', trade_data.get('is_dry_run', True)),
                    ('live_execution_mode', trade_data.get('live_execution_mode')),
                    # Ordre d'entrée
                    ('entry_order_id', trade_data.get('entry_order_id')),
                    ('entry_order_type', trade_data.get('entry_order_type')),
                    ('entry_requested_price', _extract_numeric_value(trade_data.get('entry_requested_price'))),
                    ('entry_fill_price', _extract_numeric_value(trade_data.get('entry_fill_price'))),
                    ('entry_slippage_pct', _extract_numeric_value(trade_data.get('entry_slippage_pct'))),
                    ('entry_latency_ms', trade_data.get('entry_latency_ms')),
                    # Ordre de sortie
                    ('exit_order_id', trade_data.get('exit_order_id')),
                    ('exit_order_type', trade_data.get('exit_order_type')),
                    ('exit_requested_price', _extract_numeric_value(trade_data.get('exit_requested_price'))),
                    ('exit_fill_price', _extract_numeric_value(trade_data.get('exit_fill_price'))),
                    ('exit_slippage_pct', _extract_numeric_value(trade_data.get('exit_slippage_pct'))),
                    ('exit_latency_ms', trade_data.get('exit_latency_ms')),
                    # Timestamps LIVE & API responses
                    ('entry_timestamp_live', trade_data.get('entry_timestamp')),
                    ('exit_timestamp_live', trade_data.get('exit_timestamp')),
                    ('entry_api_response', json.dumps(trade_data.get('entry_api_response')) if trade_data.get('entry_api_response') else None),
                    ('exit_api_response', json.dumps(trade_data.get('exit_api_response')) if trade_data.get('exit_api_response') else None),
                    # Futures / Levier
                    ('leverage_used', trade_data.get('leverage_used', 1)),
                    ('margin_mode', trade_data.get('margin_mode', 'isolated')),
                    ('position_size_contracts', _extract_numeric_value(trade_data.get('position_size_contracts'))),
                    ('liquidation_price', _extract_numeric_value(trade_data.get('liquidation_price'))),
                    ('margin_used', _extract_numeric_value(trade_data.get('margin_used'))),
                    # Frais détaillés
                    ('maker_fee_rate', _extract_numeric_value(trade_data.get('maker_fee_rate'))),
                    ('taker_fee_rate', _extract_numeric_value(trade_data.get('taker_fee_rate'))),
                    ('entry_fee_usdt', _extract_numeric_value(trade_data.get('entry_fee_usdt'))),
                    ('exit_fee_usdt', _extract_numeric_value(trade_data.get('exit_fee_usdt'))),
                    ('total_fees_usdt', _extract_numeric_value(trade_data.get('total_fees_usdt'))),
                    ('funding_rate_at_entry', _extract_numeric_value(trade_data.get('funding_rate_at_entry'))),
                    ('funding_rate_at_exit', _extract_numeric_value(trade_data.get('funding_rate_at_exit'))),
                    ('funding_paid_usdt', _extract_numeric_value(trade_data.get('funding_paid_usdt'))),
                    # Performance temps réel
                    ('time_to_fill_entry_ms', trade_data.get('time_to_fill_entry_ms')),
                    ('time_to_fill_exit_ms', trade_data.get('time_to_fill_exit_ms')),
                    ('price_at_signal', _extract_numeric_value(trade_data.get('price_at_signal'))),
                    ('signal_to_fill_slippage_pct', _extract_numeric_value(trade_data.get('signal_to_fill_slippage_pct'))),
                    # API & Réseau
                    ('api_errors', json.dumps(trade_data.get('api_errors', []))),
                    ('retry_count', trade_data.get('retry_count', 0)),
                    ('exchange_latency_ms', trade_data.get('exchange_latency_ms')),
                    ('ws_latency_ms', trade_data.get('ws_latency_ms')),
                    # Score & ML
                    ('setup_score', _extract_numeric_value(trade_data.get('setup_score'))),
                    # ml_confidence déplacé dans fields principaux
                    ('ml_prediction', trade_data.get('ml_prediction')),
                    # Analyse post-trade (risk_reward déjà ajoutés plus haut)
                    # Notes & Tags
                    ('trade_notes', trade_data.get('trade_notes')),
                    ('trade_tags', json.dumps(trade_data.get('trade_tags', []))),
                    ('user_rating', trade_data.get('user_rating'))
                ])

            columns_sql = ',\n                    '.join(name for name, _ in fields)
            placeholders_sql = ', '.join(['%s'] * len(fields))
            query = f"""
                INSERT INTO trades (
                    {columns_sql}
                ) VALUES (
                    {placeholders_sql}
                )
                RETURNING id
            """

            params = [value for _, value in fields]

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
    
    def _batch_insert_scans(self, cursor, scan_items: List[Dict[str, Any]]) -> None:
        """Insérer en batch les scans accumulés dans scan_buffer."""
        if not scan_items:
            return

        values: List[tuple] = []

        for item in scan_items:
            session_id = item.get('session_id')
            symbol = item.get('symbol')
            scan_data = item.get('scan_data') or {}

            if not symbol or not isinstance(scan_data, dict):
                continue

            market_data = scan_data.get('market_data') or {}
            indicators_1m = scan_data.get('indicators_1m') or {}
            indicators_5m = scan_data.get('indicators_5m') or {}
            filters = scan_data.get('filters') or {}
            scores = scan_data.get('scores') or {}
            patterns = scan_data.get('patterns') or {}

            # Prix via get_preferred_price avec fallbacks
            price = get_preferred_price(market_data, None)
            if price is None:
                price = get_preferred_price(scan_data.get('price'), None)
            if price is None:
                analysis_1m = scan_data.get('analysis_1m', {})
                if isinstance(analysis_1m, dict):
                    price = get_preferred_price(analysis_1m, None)
            if price is None:
                analysis_5m = scan_data.get('analysis_5m', {})
                if isinstance(analysis_5m, dict):
                    price = get_preferred_price(analysis_5m, None)

            if price is not None and not isinstance(price, (int, float)):
                try:
                    price = float(price)
                except (ValueError, TypeError):
                    logger.warning(
                        f"⚠️ Prix invalide pour {symbol} dans batch: {price} (type: {type(price)})"
                    )
                    price = None

            if price is None or price == 0:
                if price is None:
                    price = 0.0
                    logger.warning(
                        f"⚠️ Prix manquant pour {symbol} dans log_scan (batch), utilisation price=0"
                    )

            scan_duration = scan_data.get('scan_duration_ms')
            if scan_duration is None:
                scan_duration = 0.0

            params_snap = scan_data.get('params_snapshot')
            if not params_snap or not isinstance(params_snap, dict):
                params_snap = {}

            # 🔥 ORDER FLOW: Calcul automatique si manquant
            bid_vol = market_data.get('bid_vol') or market_data.get('bidVol') or scan_data.get('bid_vol') or scan_data.get('bidVol')
            ask_vol = market_data.get('ask_vol') or market_data.get('askVol') or scan_data.get('ask_vol') or scan_data.get('askVol')
            
            delta_volume = market_data.get('delta_volume') or scan_data.get('delta_volume')
            imbalance_normalized = market_data.get('imbalance_normalized') or scan_data.get('imbalance_normalized')
            book_depth_ratio = market_data.get('book_depth_ratio') or scan_data.get('book_depth_ratio')
            
            # Calculer automatiquement si manquant et bid/ask disponibles
            if delta_volume is None and bid_vol and ask_vol:
                delta_volume = float(bid_vol) - float(ask_vol)
            if imbalance_normalized is None and bid_vol and ask_vol:
                total = float(bid_vol) + float(ask_vol)
                imbalance_normalized = (float(bid_vol) - float(ask_vol)) / total if total > 0 else 0.0
            if book_depth_ratio is None and bid_vol and ask_vol and float(ask_vol) > 0:
                book_depth_ratio = float(bid_vol) / float(ask_vol)

            value_tuple = (
                # En-tête
                session_id, symbol, scan_duration,
                price, market_data.get('spread_pct'),
                market_data.get('book_depth'), market_data.get('balance_score'),
                bid_vol, ask_vol,
                market_data.get('orderbook_imbalance_ratio'),
                # Scalability
                market_data.get('recent_volume') or scan_data.get('recent_volume') or scan_data.get('recentVolume'),
                market_data.get('vol5') or scan_data.get('vol5'),
                market_data.get('vol15') or scan_data.get('vol15'),
                market_data.get('scalability_score') or scan_data.get('scalability_score') or scan_data.get('score'),
                # 🔥 ORDER FLOW: 6 métriques (calculées auto si manquantes)
                delta_volume,
                imbalance_normalized,
                market_data.get('spread_volatility_5') or scan_data.get('spread_volatility_5'),
                book_depth_ratio,
                market_data.get('volume_acceleration') or scan_data.get('volume_acceleration'),
                market_data.get('price_momentum_5') or scan_data.get('price_momentum_5'),
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
                filters.get('snr_passed_1m', False), filters.get('snr_passed_5m', False),
                filters.get('breakout_distance_1m'), filters.get('breakout_distance_5m'),
                filters.get('breakout_passed_1m', False), filters.get('breakout_passed_5m', False),
                filters.get('wick_ratio_1m'), filters.get('wick_ratio_5m'),
                filters.get('wick_passed_1m', False), filters.get('wick_passed_5m', False),
                filters.get('atr_optimal_passed_1m', False), filters.get('atr_optimal_passed_5m', False),
                filters.get('volume_filter_passed_1m', False), filters.get('volume_filter_passed_5m', False),
                # Confluence
                scan_data.get('use_confluence'), scan_data.get('confluence_met', False),
                scores.get('score_1m'), scores.get('score_5m'), scores.get('score_total'),
                scores.get('score_long_1m', 0), scores.get('score_short_1m', 0),
                scores.get('score_long_5m', 0), scores.get('score_short_5m', 0),
                scan_data.get('timeframes_aligned', False),
                # Patterns
                patterns.get('pattern_1m'), patterns.get('pattern_multi_1m'),
                patterns.get('pattern_5m'), patterns.get('pattern_multi_5m'),
                # Trend
                scan_data.get('trend_timeframe', '15m'),
                scan_data.get('trend_direction'), scan_data.get('trend_strength'),
                scan_data.get('trend_bonus', 0),
                # Divergence
                scan_data.get('divergence_detected', False),
                scan_data.get('divergence_type'), scan_data.get('divergence_bonus', 0),
                # Decision
                scan_data.get('is_opportunity', False),
                scan_data.get('opportunity_direction'),
                scan_data.get('reject_reason'), scan_data.get('reject_reason_category'),
                # 🔥 ML Confidence (confiance réelle du modèle)
                scan_data.get('ml_confidence'),
                # Params
                json.dumps(params_snap),
                # Config
                params_snap.get('min_score_required'),
                params_snap.get('snr_threshold'),
                params_snap.get('optimal_atr_min_1m'),
                params_snap.get('optimal_atr_max_1m'),
                params_snap.get('optimal_atr_min_5m'),
                params_snap.get('optimal_atr_max_5m'),
                params_snap.get('volume_multiplier'),
                params_snap.get('use_confluence'),
                # 🔥 FIX: Ajouter les nouvelles colonnes config_* (OPT #15-19)
                params_snap.get('use_anti_whipsaw'),
                params_snap.get('whipsaw_lookback'),
                params_snap.get('whipsaw_threshold_pct'),
                params_snap.get('whipsaw_max_alternations'),
                params_snap.get('use_retest_confirmation'),
                params_snap.get('retest_tolerance_pct'),
                params_snap.get('retest_timeout_seconds'),
                params_snap.get('use_cooldown'),
                params_snap.get('cooldown_seconds'),
                params_snap.get('cooldown_same_symbol'),
                params_snap.get('use_candle_close'),
                params_snap.get('candle_close_threshold_seconds'),
                params_snap.get('use_momentum_continuity'),
                params_snap.get('momentum_lookback'),
                # 🔥 SPRINT 1: Market Regime context
                scan_data.get('market_regime'),
                scan_data.get('market_regime_avg_atr'),
                scan_data.get('market_regime_avg_adx')
            )

            values.append(value_tuple)

        if not values:
            logger.warning("⚠️ Aucun scan valide à insérer dans _batch_insert_scans (tous sans prix)")
            return

        columns = (
            'session_id', 'symbol', 'scan_duration_ms',
            'price', 'spread_pct', 'book_depth', 'balance_score',
            'bid_vol', 'ask_vol', 'orderbook_imbalance_ratio',
            'recent_volume', 'vol5', 'vol15', 'scalability_score',
            # 🔥 ORDER FLOW: 6 nouvelles colonnes
            'delta_volume', 'imbalance_normalized', 'spread_volatility_5',
            'book_depth_ratio', 'volume_acceleration', 'price_momentum_5',
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
            # 🔥 ML Confidence (confiance réelle du modèle)
            'ml_confidence',
            'params_snapshot',
            'config_min_score_required', 'config_snr_threshold',
            'config_atr_min_1m', 'config_atr_max_1m',
            'config_atr_min_5m', 'config_atr_max_5m',
            'config_volume_multiplier', 'config_use_confluence',
            # 🔥 FIX: Ajouter les nouvelles colonnes config_* (OPT #15-19)
            'config_use_anti_whipsaw', 'config_whipsaw_lookback',
            'config_whipsaw_threshold_pct', 'config_whipsaw_max_alternations',
            'config_use_retest_confirmation', 'config_retest_tolerance_pct',
            'config_retest_timeout_seconds', 'config_use_cooldown',
            'config_cooldown_seconds', 'config_cooldown_same_symbol',
            'config_use_candle_close', 'config_candle_close_threshold_seconds',
            'config_use_momentum_continuity', 'config_momentum_lookback',
            # 🔥 SPRINT 1: Market Regime context
            'market_regime', 'market_regime_avg_atr', 'market_regime_avg_adx'
        )

        execute_values(
            cursor,
            f"INSERT INTO scan_logs (timestamp, {', '.join(columns)}) VALUES %s",
            values,
            template=f"(NOW(), {', '.join(['%s'] * len(columns))})",
            page_size=len(values)
        )

    def _flush_buffers(self, force: bool = False):
        """Flush les buffers de scans et d'opportunités vers PostgreSQL."""
        if not self.enabled:
            return

        now = datetime.now(timezone.utc)
        time_since_flush = (now - self.last_flush_time).total_seconds()
        should_flush = force or (
            len(self.scan_buffer) >= self.batch_size or
            len(self.opportunity_buffer) >= self.batch_size or
            time_since_flush >= self.batch_flush_interval
        )

        if not should_flush:
            return

        self.last_flush_time = now

        conn = self._get_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()

            with self.buffer_lock:
                scan_items = list(self.scan_buffer)
                self.scan_buffer.clear()
                opportunity_items = list(self.opportunity_buffer)
                self.opportunity_buffer.clear()

            if scan_items:
                self._batch_insert_scans(cursor, scan_items)

            # Opportunités : pour l'instant, utiliser log_opportunity en mode direct
            for item in opportunity_items:
                try:
                    self.log_opportunity(
                        scan_id=item.get('scan_id'),
                        symbol=item.get('symbol'),
                        opportunity_data=item.get('opportunity_data') or {},
                        session_id=item.get('session_id'),
                        use_batch=False
                    )
                except Exception as e:
                    logger.error(f"❌ Erreur batch insert opportunity pour {item.get('symbol')}: {e}")

            conn.commit()
            cursor.close()
            self._return_connection(conn)
        except Exception as e:
            logger.error(f"❌ Erreur lors du flush des buffers PostgreSQL: {e}")
            if conn:
                conn.rollback()
                self._return_connection(conn)

    def close(self):
        """
        Fermer le pool de connexions PostgreSQL

        Cette méthode doit être appelée avant de quitter l'application
        pour libérer proprement les ressources.
        """
        if not self.enabled or not self.pool:
            return

        try:
            # Flush les buffers avant de fermer
            self._flush_buffers()

            # Fermer toutes les connexions du pool
            self.pool.closeall()
            logger.info("✅ Pool de connexions PostgreSQL fermé")
        except Exception as e:
            logger.error(f"❌ Erreur lors de la fermeture du pool PostgreSQL: {e}")


# ============================================================================
# Singleton global pour accès facile
# ============================================================================
_pg_datalogger_instance = None


def get_pg_datalogger():
    """
    Récupérer l'instance singleton PostgreSQLDataLogger
    
    Returns:
        PostgreSQLDataLogger ou None si non initialisé/désactivé
    """
    global _pg_datalogger_instance
    
    # Si une instance existe déjà, la retourner
    if _pg_datalogger_instance is not None:
        return _pg_datalogger_instance
    
    # Sinon, tenter de créer une nouvelle instance avec config par défaut
    if not PSYCOPG2_AVAILABLE:
        logger.warning("⚠️ psycopg2 non disponible, PostgreSQL DataLogger désactivé")
        return None
    
    try:
        # Charger config depuis variables d'environnement
        import os
        from dotenv import load_dotenv
        from pathlib import Path
        
        env_path = Path(__file__).parent.parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
        
        enabled = os.getenv('POSTGRES_ENABLED', 'true').lower() == 'true'
        
        if not enabled:
            logger.info("ℹ️ PostgreSQL DataLogger désactivé dans .env")
            return None
        
        _pg_datalogger_instance = PostgreSQLDataLogger(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', '5432')),
            database=os.getenv('POSTGRES_DB', 'tradebot'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', ''),
            min_conn=int(os.getenv('POSTGRES_MIN_CONN', '2')),
            max_conn=int(os.getenv('POSTGRES_MAX_CONN', '10'))
        )
        
        if _pg_datalogger_instance and _pg_datalogger_instance.enabled:
            logger.info("✅ PostgreSQL DataLogger singleton créé")
        else:
            logger.warning("⚠️ PostgreSQL DataLogger créé mais désactivé")
        
        return _pg_datalogger_instance
        
    except Exception as e:
        logger.error(f"❌ Erreur création PostgreSQL DataLogger singleton: {e}")
        return None


def set_pg_datalogger(instance):
    """
    Définir manuellement l'instance singleton PostgreSQLDataLogger
    
    Args:
        instance: Instance de PostgreSQLDataLogger
    """
    global _pg_datalogger_instance
    _pg_datalogger_instance = instance
    logger.info("✅ Instance PostgreSQL DataLogger définie manuellement")
