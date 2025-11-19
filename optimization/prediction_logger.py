"""
Prediction Logger - Service pour logger les prédictions ML et leurs résultats
"""

import os
import logging
import json
from typing import Dict, Optional
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor, Json

logger = logging.getLogger(__name__)


def get_postgres_connection():
    """Connexion PostgreSQL depuis variables d'environnement"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', 5432)),
            database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', ''),
            cursor_factory=RealDictCursor,
            client_encoding='utf8'
        )
        return conn
    except Exception as e:
        logger.error(f"❌ Erreur connexion PostgreSQL: {e}")
        raise


def log_prediction(
    prediction_data: Dict,
    symbol: str,
    scan_id: Optional[int] = None,
    opportunity_timestamp: Optional[datetime] = None,
    metadata: Optional[Dict] = None
) -> Optional[int]:
    """
    Logger une prédiction ML dans la base de données
    
    Args:
        prediction_data: Résultat de la prédiction (from predictor.predict())
        symbol: Symbole de l'opportunité
        scan_id: ID du scan qui a généré l'opportunité
        opportunity_timestamp: Timestamp de l'opportunité
        metadata: Métadonnées additionnelles
        
    Returns:
        ID de la prédiction loggée ou None si erreur
    """
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        
        # Extraire données de la prédiction
        prediction = prediction_data.get('prediction')
        win_prob = prediction_data.get('win_probability', 0)
        loss_prob = prediction_data.get('loss_probability', 0)
        confidence = prediction_data.get('confidence', 0)
        model_name = prediction_data.get('model_name', 'unknown')
        model_version = prediction_data.get('model_version')
        top_features = prediction_data.get('top_features')
        
        # Performance du modèle
        model_perf = prediction_data.get('model_performance', {})
        test_accuracy = model_perf.get('test_accuracy')
        test_f1 = model_perf.get('test_f1')
        
        # Insert
        cur.execute("""
            INSERT INTO predictions_log (
                timestamp,
                model_name,
                model_version,
                scan_id,
                symbol,
                opportunity_timestamp,
                prediction,
                win_probability,
                loss_probability,
                confidence,
                top_features,
                model_test_accuracy,
                model_test_f1,
                metadata
            ) VALUES (
                NOW(),
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s
            )
            RETURNING id
        """, (
            model_name,
            model_version,
            scan_id,
            symbol,
            opportunity_timestamp,
            prediction,
            win_prob,
            loss_prob,
            confidence,
            Json(top_features) if top_features else None,
            test_accuracy,
            test_f1,
            Json(metadata) if metadata else None
        ))
        
        prediction_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"✅ Prédiction loggée: ID={prediction_id}, {symbol}, {prediction} ({confidence:.1%})")
        return prediction_id
        
    except Exception as e:
        logger.error(f"❌ Erreur log_prediction: {e}", exc_info=True)
        return None


def link_prediction_to_trade(prediction_id: int, trade_id: int) -> bool:
    """
    Lier une prédiction à un trade exécuté
    
    Args:
        prediction_id: ID de la prédiction
        trade_id: ID du trade
        
    Returns:
        True si succès
    """
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE predictions_log
            SET trade_id = %s,
                trade_executed = TRUE
            WHERE id = %s
        """, (trade_id, prediction_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"✅ Prédiction {prediction_id} liée au trade {trade_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur link_prediction_to_trade: {e}", exc_info=True)
        return False


def update_prediction_result(trade_id: int) -> bool:
    """
    Mettre à jour le résultat d'une prédiction après fermeture du trade
    
    Args:
        trade_id: ID du trade fermé
        
    Returns:
        True si succès
    """
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        
        # Récupérer infos du trade
        cur.execute("""
            SELECT win, pnl, pnl_percent, timestamp_exit
            FROM trades
            WHERE id = %s AND timestamp_exit IS NOT NULL
        """, (trade_id,))
        
        trade = cur.fetchone()
        if not trade:
            logger.warning(f"Trade {trade_id} non trouvé ou pas fermé")
            return False
        
        actual_result = 'win' if trade['win'] else 'loss'
        
        # Mettre à jour prédiction
        cur.execute("""
            UPDATE predictions_log
            SET actual_result = %s,
                actual_pnl = %s,
                actual_pnl_pct = %s,
                trade_closed_at = %s,
                correct_prediction = (prediction = %s),
                confidence_calibrated = (
                    CASE 
                        WHEN prediction = %s AND confidence >= 0.7 THEN TRUE
                        WHEN prediction != %s AND confidence < 0.6 THEN TRUE
                        ELSE FALSE
                    END
                )
            WHERE trade_id = %s
        """, (
            actual_result,
            trade['pnl'],
            trade['pnl_percent'],
            trade['timestamp_exit'],
            actual_result,
            actual_result,
            actual_result,
            trade_id
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"✅ Résultat prédiction mis à jour pour trade {trade_id}: {actual_result}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur update_prediction_result: {e}", exc_info=True)
        return False


def get_prediction_analytics(model_name: Optional[str] = None, days: int = 30) -> Dict:
    """
    Récupérer analytics des prédictions
    
    Args:
        model_name: Filtrer par modèle (None = tous)
        days: Nombre de jours à analyser
        
    Returns:
        Dict avec analytics
    """
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        
        where_clause = "WHERE timestamp > NOW() - INTERVAL '%s days'" % days
        if model_name:
            where_clause += f" AND model_name = '{model_name}'"
        
        cur.execute(f"""
            SELECT 
                COUNT(*) as total_predictions,
                COUNT(CASE WHEN actual_result IS NOT NULL THEN 1 END) as evaluated,
                COUNT(CASE WHEN correct_prediction = TRUE THEN 1 END) as correct,
                ROUND(AVG(CASE WHEN correct_prediction = TRUE THEN 1.0 ELSE 0.0 END) * 100, 2) as accuracy_pct,
                ROUND(AVG(confidence) * 100, 2) as avg_confidence_pct,
                COUNT(CASE WHEN trade_executed = TRUE THEN 1 END) as trades_executed,
                ROUND(AVG(CASE WHEN trade_executed = TRUE THEN actual_pnl_pct END), 2) as avg_pnl_pct,
                COUNT(CASE WHEN prediction = 'win' AND confidence >= 0.7 THEN 1 END) as high_confidence_wins,
                COUNT(CASE WHEN prediction = 'win' AND confidence >= 0.7 AND correct_prediction = TRUE THEN 1 END) as high_confidence_correct
            FROM predictions_log
            {where_clause}
        """)
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        return dict(result) if result else {}
        
    except Exception as e:
        logger.error(f"❌ Erreur get_prediction_analytics: {e}", exc_info=True)
        return {}


def get_recent_predictions(limit: int = 20) -> list:
    """
    Récupérer les prédictions récentes
    
    Args:
        limit: Nombre de prédictions à retourner
        
    Returns:
        Liste de prédictions
    """
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT * FROM recent_predictions
            LIMIT %s
        """, (limit,))
        
        predictions = cur.fetchall()
        cur.close()
        conn.close()
        
        return [dict(p) for p in predictions]
        
    except Exception as e:
        logger.error(f"❌ Erreur get_recent_predictions: {e}", exc_info=True)
        return []


def get_best_symbols_for_ml(min_predictions: int = 5) -> list:
    """
    Récupérer les symboles avec les meilleures performances ML
    
    Args:
        min_predictions: Minimum de prédictions pour être inclus
        
    Returns:
        Liste de symboles triés par accuracy
    """
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                symbol,
                total_predictions,
                accuracy_pct,
                avg_confidence_pct,
                win_predictions,
                actual_wins
            FROM predictions_by_symbol
            WHERE total_predictions >= %s
            ORDER BY accuracy_pct DESC, total_predictions DESC
            LIMIT 20
        """, (min_predictions,))
        
        symbols = cur.fetchall()
        cur.close()
        conn.close()
        
        return [dict(s) for s in symbols]
        
    except Exception as e:
        logger.error(f"❌ Erreur get_best_symbols_for_ml: {e}", exc_info=True)
        return []
