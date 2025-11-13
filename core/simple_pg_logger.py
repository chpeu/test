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
            
            # Insert MINIMAL pour test
            query = """
                INSERT INTO scan_logs (
                    timestamp, symbol, price,
                    rsi_1m, score_total, is_opportunity
                )
                VALUES (NOW(), %s, %s, %s, %s, %s)
            """
            
            indicators_1m = scan_data.get('indicators_1m', {})
            
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
            
            params = (
                symbol,
                price,
                indicators_1m.get('rsi'),
                scan_data.get('scores', {}).get('score_total'),
                scan_data.get('is_opportunity', False)
            )
            
            logger.debug(f"🔍 SimplePGLogger: Insert pour {symbol} avec params: {params}")
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

