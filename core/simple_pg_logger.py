"""
Simple PostgreSQL Logger - Sans batch, sans complexity
"""
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional
import json

try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

logger = logging.getLogger(__name__)

class SimplePGLogger:
    """Logger PostgreSQL ultra-simple - Insert direct"""
    
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
    
    def log_scan_simple(self, symbol: str, scan_data: Dict[str, Any]) -> bool:
        """Logger un scan - Insert direct, pas de batch"""
        if not self.enabled:
            logger.warning(f"⚠️ SimplePGLogger désactivé pour {symbol}")
            return False
        
        try:
            # Vérifier que la connexion est toujours active
            if self.conn.closed:
                logger.error(f"❌ Connexion PostgreSQL fermée pour {symbol}")
                self.enabled = False
                return False
            
            cursor = self.conn.cursor()
            
            # Insert MINIMAL pour test - 🔥 Enrichi avec colonnes essentielles
            query = """
                INSERT INTO scan_logs (
                    timestamp, symbol, price,
                    rsi_1m, score_total, is_opportunity,
                    score_1m, score_5m,
                    reject_reason_category,
                    config_min_score_required, config_snr_threshold, config_volume_multiplier
                )
                VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            indicators_1m = scan_data.get('indicators_1m', {}) or {}
            
            # Vérifier que le prix n'est pas None (contrainte NOT NULL)
            price = scan_data.get('market_data', {}).get('price')
            
            # Extraire la valeur numérique si price est un dict
            if isinstance(price, dict):
                price = price.get('price') or price.get('lastPrice') or price.get('close') or price.get('value')
            
            # Vérifier que price est un nombre
            if price is not None and not isinstance(price, (int, float)):
                try:
                    price = float(price)
                except (ValueError, TypeError):
                    logger.warning(f"⚠️ Prix invalide pour {symbol}: {price} (type: {type(price)})")
                    price = None
            
            if price is None:
                logger.warning(f"⚠️ Prix manquant pour {symbol}, scan non loggé")
                cursor.close()
                return False
            
            # Récupérer RSI avec fallbacks multiples
            rsi_1m = indicators_1m.get('rsi')
            if rsi_1m is None:
                # Fallback 1: Essayer depuis scan_data directement
                rsi_1m = scan_data.get('rsi') or scan_data.get('rsi_1m')
                if rsi_1m is not None:
                    logger.debug(f"🔍 DEBUG SimplePGLogger {symbol}: RSI récupéré depuis scan_data: {rsi_1m}")
                # Fallback 2: Essayer depuis market_data
                if rsi_1m is None:
                    market_data = scan_data.get('market_data', {})
                    if isinstance(market_data, dict):
                        rsi_1m = market_data.get('rsi') or market_data.get('rsi_1m')
                        if rsi_1m is not None:
                            logger.debug(f"🔍 DEBUG SimplePGLogger {symbol}: RSI récupéré depuis market_data: {rsi_1m}")
                # Fallback 3: Essayer depuis analysis_1m dans scan_data (si analysis a été passé)
                if rsi_1m is None:
                    # Vérifier si scan_data contient analysis_1m (structure retournée par analyze_pair)
                    analysis_1m = scan_data.get('analysis_1m', {})
                    if isinstance(analysis_1m, dict) and analysis_1m:
                        rsi_1m = analysis_1m.get('rsi')
                        if rsi_1m is not None:
                            logger.debug(f"🔍 DEBUG SimplePGLogger {symbol}: RSI récupéré depuis analysis_1m: {rsi_1m}")
            
            # Log de debug si RSI toujours manquant
            if rsi_1m is None:
                logger.debug(f"⚠️ DEBUG SimplePGLogger {symbol}: RSI non trouvé après tous les fallbacks. "
                           f"indicators_1m keys: {list(indicators_1m.keys()) if indicators_1m else 'None'}, "
                           f"scan_data keys: {list(scan_data.keys())[:10] if scan_data else 'None'}")
            
            # Récupérer score_total avec fallbacks
            scores = scan_data.get('scores', {}) or {}
            score_total = scores.get('score_total')
            # Priorité 2: totalScore (nom utilisé dans analyzer.py)
            if score_total is None:
                score_total = scores.get('totalScore') or scan_data.get('totalScore')
            # Priorité 3: score (nom alternatif)
            if score_total is None:
                score_total = scores.get('score') or scan_data.get('score')
            # Fallback 1: Essayer depuis scan_data directement
            if score_total is None:
                score_total = scan_data.get('score_total') or scan_data.get('totalScore') or scan_data.get('score')
                if score_total is not None:
                    logger.debug(f"🔍 DEBUG SimplePGLogger {symbol}: score_total récupéré depuis scan_data: {score_total}")
                # Fallback 2: Essayer depuis market_data
                if score_total is None:
                    market_data = scan_data.get('market_data', {})
                    if isinstance(market_data, dict):
                        score_total = market_data.get('score_total') or market_data.get('totalScore') or market_data.get('score')
                        if score_total is not None:
                            logger.debug(f"🔍 DEBUG SimplePGLogger {symbol}: score_total récupéré depuis market_data: {score_total}")
                # Fallback 3: Essayer depuis analysis_1m dans scan_data (si analysis a été passé)
                if score_total is None:
                    analysis_1m = scan_data.get('analysis_1m', {})
                    if isinstance(analysis_1m, dict) and analysis_1m:
                        score_total = analysis_1m.get('score_total') or analysis_1m.get('totalScore') or analysis_1m.get('score')
                        if score_total is not None:
                            logger.debug(f"🔍 DEBUG SimplePGLogger {symbol}: score_total récupéré depuis analysis_1m: {score_total}")
                    # Fallback 4: Essayer depuis analysis_5m
                    if score_total is None:
                        analysis_5m = scan_data.get('analysis_5m', {})
                        if isinstance(analysis_5m, dict) and analysis_5m:
                            score_total = analysis_5m.get('score_total') or analysis_5m.get('totalScore') or analysis_5m.get('score')
                            if score_total is not None:
                                logger.debug(f"🔍 DEBUG SimplePGLogger {symbol}: score_total récupéré depuis analysis_5m: {score_total}")
            
            # Fallback 5: Essayer long_score ou short_score depuis scan_data (retournés par analyzer.py pour les rejets)
            if score_total is None:
                long_score = scan_data.get('long_score')
                short_score = scan_data.get('short_score')
                # Utiliser le score le plus élevé, ou celui qui est disponible
                if long_score is not None and short_score is not None:
                    score_total = max(long_score, short_score)
                elif long_score is not None:
                    score_total = long_score
                elif short_score is not None:
                    score_total = short_score
                if score_total is not None:
                    logger.debug(f"🔍 DEBUG SimplePGLogger {symbol}: score_total récupéré depuis long_score/short_score: {score_total}")
            
            # Fallback 6: Essayer long_score ou short_score depuis analysis_1m ou analysis_5m
            if score_total is None:
                analysis_1m = scan_data.get('analysis_1m', {})
                analysis_5m = scan_data.get('analysis_5m', {})
                if isinstance(analysis_1m, dict) and analysis_1m:
                    long_score = analysis_1m.get('long_score')
                    short_score = analysis_1m.get('short_score')
                    if long_score is not None and short_score is not None:
                        score_total = max(long_score, short_score)
                    elif long_score is not None:
                        score_total = long_score
                    elif short_score is not None:
                        score_total = short_score
                if score_total is None and isinstance(analysis_5m, dict) and analysis_5m:
                    long_score = analysis_5m.get('long_score')
                    short_score = analysis_5m.get('short_score')
                    if long_score is not None and short_score is not None:
                        score_total = max(long_score, short_score)
                    elif long_score is not None:
                        score_total = long_score
                    elif short_score is not None:
                        score_total = short_score
                if score_total is not None:
                    logger.debug(f"🔍 DEBUG SimplePGLogger {symbol}: score_total récupéré depuis long_score/short_score dans analysis_1m/5m: {score_total}")
            
            # Log de debug si score_total toujours manquant
            if score_total is None:
                logger.debug(f"⚠️ DEBUG SimplePGLogger {symbol}: score_total non trouvé après tous les fallbacks. "
                           f"scores keys: {list(scores.keys()) if scores else 'None'}, "
                           f"scan_data keys: {list(scan_data.keys())[:15] if scan_data else 'None'}")
            
            # 🔥 Extraire score_1m et score_5m depuis scores ou analysis
            score_1m = scores.get('score_1m')
            if score_1m is None:
                analysis_1m = scan_data.get('analysis_1m', {})
                if isinstance(analysis_1m, dict):
                    score_1m = analysis_1m.get('totalScore') or analysis_1m.get('score_1m')
            
            score_5m = scores.get('score_5m')
            if score_5m is None:
                analysis_5m = scan_data.get('analysis_5m', {})
                if isinstance(analysis_5m, dict):
                    score_5m = analysis_5m.get('totalScore') or analysis_5m.get('score_5m')
            
            # 🔥 Extraire reject_reason_category
            reject_reason_category = scan_data.get('reject_reason_category')
            if reject_reason_category is None:
                reject_reason_category = scan_data.get('reject_category')
            
            # 🔥 Extraire config_* depuis params_snapshot
            params_snapshot = scan_data.get('params_snapshot', {}) or {}
            config_min_score = params_snapshot.get('min_score_required')
            config_snr = params_snapshot.get('snr_threshold')
            config_vol_mult = params_snapshot.get('volume_multiplier')
            
            params = (
                symbol,
                price,
                rsi_1m,  # Peut être None, ce qui est acceptable pour la base de données
                score_total,  # Peut être None, ce qui est acceptable pour la base de données
                scan_data.get('is_opportunity', False),
                # 🔥 Nouvelles colonnes
                score_1m,
                score_5m,
                reject_reason_category,
                config_min_score,
                config_snr,
                config_vol_mult
            )
            
            logger.debug(f"🔍 SimplePGLogger: Insert pour {symbol} avec params: (symbol={symbol}, price={price}, rsi_1m={rsi_1m}, score_total={score_total}, is_opportunity={scan_data.get('is_opportunity', False)}, score_1m={score_1m}, score_5m={score_5m}, reject_cat={reject_reason_category})")
            cursor.execute(query, params)
            
            self.conn.commit()
            cursor.close()
            
            logger.info(f"✅ Scan loggé: {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur log_scan pour {symbol}: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            # 🔥 FIX: Rollback en cas d'erreur pour éviter que la transaction reste en état d'erreur
            try:
                if hasattr(self, 'conn') and not self.conn.closed:
                    self.conn.rollback()
                    logger.debug(f"🔄 Rollback effectué pour {symbol}")
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

