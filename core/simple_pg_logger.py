"""
Simple PostgreSQL Logger - Version Complète
Logger TOUTES les colonnes de scan_logs
"""
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import json

try:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extras import Json, RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

logger = logging.getLogger(__name__)

class SimplePGLogger:
    """Logger PostgreSQL complet - Insère TOUTES les colonnes de scan_logs"""

    def __init__(self):
        if not PSYCOPG2_AVAILABLE:
            self.enabled = False
            logger.warning("⚠️ psycopg2 non disponible")
            return

        self.enabled = True
        try:
            self.conn = psycopg2.connect(
                host=os.getenv('POSTGRES_HOST', 'localhost'),
                port=int(os.getenv('POSTGRES_PORT', '5432')),
                dbname=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
                user=os.getenv('POSTGRES_USER', 'postgres'),
                password=os.getenv('POSTGRES_PASSWORD', '')
            )
            logger.info("✅ SimplePGLogger connecté")
        except Exception as e:
            logger.error(f"❌ Erreur connexion: {e}")
            self.enabled = False

    def _safe_get(self, data: Dict, *keys: str, default=None):
        """Récupérer une valeur avec plusieurs fallback keys"""
        for key in keys:
            if key in data and data[key] is not None:
                return data[key]
        return default

    def _extract_from_nested(self, scan_data: Dict, keys_path: List[str], default=None):
        """Extraire une valeur depuis une structure imbriquée"""
        current = scan_data
        for key in keys_path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    def _safe_float(self, value, default=None):
        """Convertir en float de manière sécurisée"""
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def _safe_bool(self, value, default=False):
        """Convertir en boolean de manière sécurisée"""
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return default

    def _safe_json(self, value):
        """Convertir en JSON pour PostgreSQL (gère dicts et arrays)"""
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return Json(value)
        # Si c'est déjà une string JSON, la parser puis convertir
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return Json(parsed)
            except:
                return Json(value)
        return Json(value)

    def log_scan_simple(self, symbol: str, scan_data: Dict[str, Any]) -> bool:
        """Logger un scan complet - Insère TOUTES les colonnes disponibles"""
        if not self.enabled:
            return False

        try:
            # Vérifier que la connexion est toujours active
            if self.conn.closed:
                logger.error(f"❌ Connexion PostgreSQL fermée pour {symbol}")
                self.enabled = False
                return False

            cursor = self.conn.cursor()

            # ========================================
            # EXTRACTION DES DONNÉES
            # ========================================

            # Récupérer les sous-dictionnaires
            market_data = scan_data.get('market_data', {}) or {}
            indicators_1m = scan_data.get('indicators_1m', {}) or {}
            indicators_5m = scan_data.get('indicators_5m', {}) or {}
            filters = scan_data.get('filters', {}) or {}
            scores = scan_data.get('scores', {}) or {}
            confluence = scan_data.get('confluence', {}) or {}
            patterns = scan_data.get('patterns', {}) or {}
            trend_data = scan_data.get('trend', {}) or {}
            divergence = scan_data.get('divergence', {}) or {}

            # session_id (peut être None)
            session_id = scan_data.get('session_id')

            # scan_duration_ms
            scan_duration_ms = self._safe_float(scan_data.get('scan_duration_ms'))

            # ========================================
            # Données marché
            # ========================================
            price = market_data.get('price') or market_data.get('lastPrice') or market_data.get('close')
            if isinstance(price, dict):
                price = price.get('price') or price.get('lastPrice') or price.get('close')
            price = self._safe_float(price)

            if price is None:
                logger.warning(f"⚠️ Prix manquant pour {symbol}, scan non loggé")
                cursor.close()
                return False

            spread_pct = self._safe_float(market_data.get('spread_pct'))
            book_depth = self._safe_float(market_data.get('book_depth'))
            balance_score = self._safe_float(market_data.get('balance_score'))
            bid_vol = self._safe_float(market_data.get('bid_vol'))
            ask_vol = self._safe_float(market_data.get('ask_vol'))
            orderbook_imbalance_ratio = self._safe_float(market_data.get('orderbook_imbalance_ratio'))

            # ========================================
            # Indicateurs 1m
            # ========================================
            ema9_1m = self._safe_float(indicators_1m.get('ema9'))
            ema21_1m = self._safe_float(indicators_1m.get('ema21'))
            ema_diff_pct_1m = self._safe_float(indicators_1m.get('ema_diff_pct'))

            rsi_1m = self._safe_float(indicators_1m.get('rsi'))
            rsi_prev_1m = self._safe_float(indicators_1m.get('rsi_prev'))

            macd_1m = self._safe_float(indicators_1m.get('macd'))
            macd_signal_1m = self._safe_float(indicators_1m.get('macd_signal'))
            macd_hist_1m = self._safe_float(indicators_1m.get('macd_hist'))
            macd_hist_prev_1m = self._safe_float(indicators_1m.get('macd_hist_prev'))

            adx_1m = self._safe_float(indicators_1m.get('adx'))
            di_plus_1m = self._safe_float(indicators_1m.get('di_plus'))
            di_minus_1m = self._safe_float(indicators_1m.get('di_minus'))
            di_gap_1m = self._safe_float(indicators_1m.get('di_gap'))

            atr_1m = self._safe_float(indicators_1m.get('atr'))
            atr_pct_1m = self._safe_float(indicators_1m.get('atr_pct'))

            bb_upper_1m = self._safe_float(indicators_1m.get('bb_upper'))
            bb_middle_1m = self._safe_float(indicators_1m.get('bb_middle'))
            bb_lower_1m = self._safe_float(indicators_1m.get('bb_lower'))
            bb_width_1m = self._safe_float(indicators_1m.get('bb_width'))
            bb_distance_to_lower_1m = self._safe_float(indicators_1m.get('bb_distance_to_lower'))
            bb_distance_to_upper_1m = self._safe_float(indicators_1m.get('bb_distance_to_upper'))

            volume_1m = self._safe_float(indicators_1m.get('volume'))
            volume_avg_1m = self._safe_float(indicators_1m.get('volume_avg'))
            volume_ratio_1m = self._safe_float(indicators_1m.get('volume_ratio'))
            volume_spike_1m = self._safe_float(indicators_1m.get('volume_spike'))

            # ========================================
            # Indicateurs 5m
            # ========================================
            ema9_5m = self._safe_float(indicators_5m.get('ema9'))
            ema21_5m = self._safe_float(indicators_5m.get('ema21'))
            ema_diff_pct_5m = self._safe_float(indicators_5m.get('ema_diff_pct'))

            rsi_5m = self._safe_float(indicators_5m.get('rsi'))
            rsi_prev_5m = self._safe_float(indicators_5m.get('rsi_prev'))

            macd_5m = self._safe_float(indicators_5m.get('macd'))
            macd_signal_5m = self._safe_float(indicators_5m.get('macd_signal'))
            macd_hist_5m = self._safe_float(indicators_5m.get('macd_hist'))
            macd_hist_prev_5m = self._safe_float(indicators_5m.get('macd_hist_prev'))

            adx_5m = self._safe_float(indicators_5m.get('adx'))
            di_plus_5m = self._safe_float(indicators_5m.get('di_plus'))
            di_minus_5m = self._safe_float(indicators_5m.get('di_minus'))
            di_gap_5m = self._safe_float(indicators_5m.get('di_gap'))

            atr_5m = self._safe_float(indicators_5m.get('atr'))
            atr_pct_5m = self._safe_float(indicators_5m.get('atr_pct'))

            bb_upper_5m = self._safe_float(indicators_5m.get('bb_upper'))
            bb_middle_5m = self._safe_float(indicators_5m.get('bb_middle'))
            bb_lower_5m = self._safe_float(indicators_5m.get('bb_lower'))
            bb_width_5m = self._safe_float(indicators_5m.get('bb_width'))
            bb_distance_to_lower_5m = self._safe_float(indicators_5m.get('bb_distance_to_lower'))
            bb_distance_to_upper_5m = self._safe_float(indicators_5m.get('bb_distance_to_upper'))

            volume_5m = self._safe_float(indicators_5m.get('volume'))
            volume_avg_5m = self._safe_float(indicators_5m.get('volume_avg'))
            volume_ratio_5m = self._safe_float(indicators_5m.get('volume_ratio'))
            volume_spike_5m = self._safe_float(indicators_5m.get('volume_spike'))

            # ========================================
            # Filtres de Qualité
            # ========================================
            snr_1m = self._safe_float(filters.get('snr_1m'))
            snr_5m = self._safe_float(filters.get('snr_5m'))
            snr_passed_1m = self._safe_bool(filters.get('snr_passed_1m'))
            snr_passed_5m = self._safe_bool(filters.get('snr_passed_5m'))

            breakout_distance_1m = self._safe_float(filters.get('breakout_distance_1m'))
            breakout_distance_5m = self._safe_float(filters.get('breakout_distance_5m'))
            breakout_passed_1m = self._safe_bool(filters.get('breakout_passed_1m'))
            breakout_passed_5m = self._safe_bool(filters.get('breakout_passed_5m'))

            wick_ratio_1m = self._safe_float(filters.get('wick_ratio_1m'))
            wick_ratio_5m = self._safe_float(filters.get('wick_ratio_5m'))
            wick_passed_1m = self._safe_bool(filters.get('wick_passed_1m'))
            wick_passed_5m = self._safe_bool(filters.get('wick_passed_5m'))

            atr_optimal_passed_1m = self._safe_bool(filters.get('atr_optimal_passed_1m'))
            atr_optimal_passed_5m = self._safe_bool(filters.get('atr_optimal_passed_5m'))

            volume_filter_passed_1m = self._safe_bool(filters.get('volume_filter_passed_1m'))
            volume_filter_passed_5m = self._safe_bool(filters.get('volume_filter_passed_5m'))

            # ========================================
            # Confluence
            # ========================================
            use_confluence = self._safe_bool(confluence.get('enabled') or scores.get('use_confluence'))
            confluence_met = self._safe_bool(confluence.get('met'))

            score_1m = self._safe_float(scores.get('score_1m'))
            score_5m = self._safe_float(scores.get('score_5m'))
            score_total = self._safe_float(scores.get('score_total') or scores.get('totalScore') or scores.get('score'))
            score_long_1m = self._safe_float(scores.get('score_long_1m'))
            score_short_1m = self._safe_float(scores.get('score_short_1m'))
            score_long_5m = self._safe_float(scores.get('score_long_5m'))
            score_short_5m = self._safe_float(scores.get('score_short_5m'))
            timeframes_aligned = self._safe_bool(confluence.get('timeframes_aligned'))

            # ========================================
            # Patterns (🔥 FIX: peuvent être des listes, convertir en JSON string pour VARCHAR)
            # ========================================
            def _pattern_to_string(value):
                """Convertir pattern (peut être liste) en string pour VARCHAR(50)"""
                if value is None:
                    return None
                if isinstance(value, list):
                    # Si c'est une liste, la joindre avec virgules (plus lisible qu'un JSON)
                    return ', '.join(str(v) for v in value)[:50]  # Tronquer à 50 chars
                return str(value)[:50]  # Tronquer à 50 chars

            pattern_1m = _pattern_to_string(patterns.get('pattern_1m'))
            pattern_multi_1m = _pattern_to_string(patterns.get('pattern_multi_1m'))
            pattern_5m = _pattern_to_string(patterns.get('pattern_5m'))
            pattern_multi_5m = _pattern_to_string(patterns.get('pattern_multi_5m'))

            # ========================================
            # Trend
            # ========================================
            trend_timeframe = trend_data.get('timeframe', '15m')
            trend_direction = trend_data.get('direction')
            trend_strength = self._safe_float(trend_data.get('strength'))
            trend_bonus = self._safe_float(trend_data.get('bonus'))

            # ========================================
            # Divergence
            # ========================================
            divergence_detected = self._safe_bool(divergence.get('detected'))
            divergence_type = divergence.get('type')
            divergence_bonus = self._safe_float(divergence.get('bonus'))

            # ========================================
            # Décision (LABELS ML)
            # ========================================
            is_opportunity = self._safe_bool(scan_data.get('is_opportunity'))
            opportunity_direction = scan_data.get('opportunity_direction') or scan_data.get('direction')
            reject_reason = scan_data.get('reject_reason')
            reject_reason_category = scan_data.get('reject_reason_category')

            # ========================================
            # Paramètres snapshot (JSONB)
            # ========================================
            params_snapshot = self._safe_json(scan_data.get('params_snapshot'))

            # ========================================
            # CONSTRUCTION DE LA REQUÊTE SQL
            # ========================================

            query = """
                INSERT INTO scan_logs (
                    timestamp, session_id, symbol, scan_duration_ms,
                    price, spread_pct, book_depth, balance_score, bid_vol, ask_vol, orderbook_imbalance_ratio,
                    ema9_1m, ema21_1m, ema_diff_pct_1m,
                    rsi_1m, rsi_prev_1m,
                    macd_1m, macd_signal_1m, macd_hist_1m, macd_hist_prev_1m,
                    adx_1m, di_plus_1m, di_minus_1m, di_gap_1m,
                    atr_1m, atr_pct_1m,
                    bb_upper_1m, bb_middle_1m, bb_lower_1m, bb_width_1m, bb_distance_to_lower_1m, bb_distance_to_upper_1m,
                    volume_1m, volume_avg_1m, volume_ratio_1m, volume_spike_1m,
                    ema9_5m, ema21_5m, ema_diff_pct_5m,
                    rsi_5m, rsi_prev_5m,
                    macd_5m, macd_signal_5m, macd_hist_5m, macd_hist_prev_5m,
                    adx_5m, di_plus_5m, di_minus_5m, di_gap_5m,
                    atr_5m, atr_pct_5m,
                    bb_upper_5m, bb_middle_5m, bb_lower_5m, bb_width_5m, bb_distance_to_lower_5m, bb_distance_to_upper_5m,
                    volume_5m, volume_avg_5m, volume_ratio_5m, volume_spike_5m,
                    snr_1m, snr_5m, snr_passed_1m, snr_passed_5m,
                    breakout_distance_1m, breakout_distance_5m, breakout_passed_1m, breakout_passed_5m,
                    wick_ratio_1m, wick_ratio_5m, wick_passed_1m, wick_passed_5m,
                    atr_optimal_passed_1m, atr_optimal_passed_5m,
                    volume_filter_passed_1m, volume_filter_passed_5m,
                    use_confluence, confluence_met,
                    score_1m, score_5m, score_total,
                    score_long_1m, score_short_1m, score_long_5m, score_short_5m,
                    timeframes_aligned,
                    pattern_1m, pattern_multi_1m, pattern_5m, pattern_multi_5m,
                    trend_timeframe, trend_direction, trend_strength, trend_bonus,
                    divergence_detected, divergence_type, divergence_bonus,
                    is_opportunity, opportunity_direction, reject_reason, reject_reason_category,
                    params_snapshot
                )
                VALUES (
                    NOW(), %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s
                )
            """

            params = (
                session_id, symbol, scan_duration_ms,
                price, spread_pct, book_depth, balance_score, bid_vol, ask_vol, orderbook_imbalance_ratio,
                ema9_1m, ema21_1m, ema_diff_pct_1m,
                rsi_1m, rsi_prev_1m,
                macd_1m, macd_signal_1m, macd_hist_1m, macd_hist_prev_1m,
                adx_1m, di_plus_1m, di_minus_1m, di_gap_1m,
                atr_1m, atr_pct_1m,
                bb_upper_1m, bb_middle_1m, bb_lower_1m, bb_width_1m, bb_distance_to_lower_1m, bb_distance_to_upper_1m,
                volume_1m, volume_avg_1m, volume_ratio_1m, volume_spike_1m,
                ema9_5m, ema21_5m, ema_diff_pct_5m,
                rsi_5m, rsi_prev_5m,
                macd_5m, macd_signal_5m, macd_hist_5m, macd_hist_prev_5m,
                adx_5m, di_plus_5m, di_minus_5m, di_gap_5m,
                atr_5m, atr_pct_5m,
                bb_upper_5m, bb_middle_5m, bb_lower_5m, bb_width_5m, bb_distance_to_lower_5m, bb_distance_to_upper_5m,
                volume_5m, volume_avg_5m, volume_ratio_5m, volume_spike_5m,
                snr_1m, snr_5m, snr_passed_1m, snr_passed_5m,
                breakout_distance_1m, breakout_distance_5m, breakout_passed_1m, breakout_passed_5m,
                wick_ratio_1m, wick_ratio_5m, wick_passed_1m, wick_passed_5m,
                atr_optimal_passed_1m, atr_optimal_passed_5m,
                volume_filter_passed_1m, volume_filter_passed_5m,
                use_confluence, confluence_met,
                score_1m, score_5m, score_total,
                score_long_1m, score_short_1m, score_long_5m, score_short_5m,
                timeframes_aligned,
                pattern_1m, pattern_multi_1m, pattern_5m, pattern_multi_5m,
                trend_timeframe, trend_direction, trend_strength, trend_bonus,
                divergence_detected, divergence_type, divergence_bonus,
                is_opportunity, opportunity_direction, reject_reason, reject_reason_category,
                params_snapshot
            )

            cursor.execute(query, params)
            self.conn.commit()
            cursor.close()

            logger.info(f"✅ Scan loggé (complet): {symbol}")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur log_scan pour {symbol}: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")

            # Rollback en cas d'erreur
            try:
                if hasattr(self, 'conn') and not self.conn.closed:
                    self.conn.rollback()
            except Exception as rollback_error:
                logger.error(f"❌ Erreur rollback: {rollback_error}")

            # Essayer de reconnecter si la connexion est fermée
            try:
                if hasattr(self, 'conn') and (self.conn.closed if hasattr(self.conn, 'closed') else False):
                    logger.info("🔄 Tentative de reconnexion...")
                    self.conn = psycopg2.connect(
                        host=os.getenv('POSTGRES_HOST', 'localhost'),
                        port=int(os.getenv('POSTGRES_PORT', '5432')),
                        dbname=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
                        user=os.getenv('POSTGRES_USER', 'postgres'),
                        password=os.getenv('POSTGRES_PASSWORD', '')
                    )
                    logger.info("✅ Reconnexion réussie")
            except Exception as reconnect_error:
                logger.error(f"❌ Erreur reconnexion: {reconnect_error}")
                self.enabled = False

            return False
