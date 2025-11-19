"""
Auto Retrain - Système de ré-entraînement automatique du modèle ML
"""

import os
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

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


def check_retrain_needed(
    model_name: str = "xgboost_v1",
    min_new_trades: int = 100,
    min_days_since_training: int = 7
) -> Dict:
    """
    Vérifier si le modèle doit être réentraîné
    
    Critères:
    - Au moins X nouveaux trades depuis dernier entraînement
    - Au moins Y jours depuis dernier entraînement
    
    Args:
        model_name: Nom du modèle
        min_new_trades: Minimum de nouveaux trades requis
        min_days_since_training: Minimum de jours depuis dernier training
        
    Returns:
        Dict avec statut et infos
    """
    try:
        # Charger metadata du modèle
        metadata_path = f"optimization/saved_models/{model_name}_metadata.json"
        if not os.path.exists(metadata_path):
            return {
                'retrain_needed': True,
                'reason': 'no_model',
                'message': 'Aucun modèle existant'
            }
        
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        last_training_date_str = metadata.get('training_info', {}).get('trained_at')
        if not last_training_date_str:
            return {
                'retrain_needed': True,
                'reason': 'unknown_date',
                'message': 'Date d\'entraînement inconnue'
            }
        
        last_training_date = datetime.fromisoformat(last_training_date_str.replace('Z', '+00:00'))
        days_since_training = (datetime.now() - last_training_date).days
        
        # Vérifier nombre de nouveaux trades
        conn = get_postgres_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT COUNT(*) as new_trades
            FROM trades
            WHERE timestamp_exit IS NOT NULL
            AND timestamp_exit > %s
        """, (last_training_date,))
        
        result = cur.fetchone()
        new_trades_count = result['new_trades'] if result else 0
        
        cur.close()
        conn.close()
        
        # Décision de ré-entraînement
        reasons = []
        
        if new_trades_count >= min_new_trades:
            reasons.append(f"{new_trades_count} nouveaux trades (>= {min_new_trades})")
        
        if days_since_training >= min_days_since_training:
            reasons.append(f"{days_since_training} jours depuis dernier training (>= {min_days_since_training})")
        
        retrain_needed = len(reasons) > 0
        
        return {
            'retrain_needed': retrain_needed,
            'reason': 'criteria_met' if retrain_needed else 'no_criteria',
            'message': ' ET '.join(reasons) if retrain_needed else 'Pas besoin de ré-entraîner',
            'details': {
                'last_training_date': last_training_date_str,
                'days_since_training': days_since_training,
                'new_trades_count': new_trades_count,
                'min_new_trades_required': min_new_trades,
                'min_days_required': min_days_since_training
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur check_retrain_needed: {e}", exc_info=True)
        return {
            'retrain_needed': False,
            'reason': 'error',
            'message': f'Erreur: {str(e)}'
        }


async def auto_retrain_if_needed(
    model_name: str = "xgboost_v1",
    min_new_trades: int = 100,
    min_days_since_training: int = 7,
    force: bool = False
) -> Dict:
    """
    Vérifier et lancer ré-entraînement automatique si nécessaire
    
    Args:
        model_name: Nom du modèle
        min_new_trades: Minimum nouveaux trades
        min_days_since_training: Minimum jours depuis dernier training
        force: Forcer le ré-entraînement
        
    Returns:
        Dict avec résultat
    """
    try:
        if not force:
            # Vérifier si nécessaire
            check = check_retrain_needed(model_name, min_new_trades, min_days_since_training)
            
            if not check['retrain_needed']:
                logger.info(f"ℹ️ Pas de ré-entraînement nécessaire: {check['message']}")
                return {
                    'status': 'skipped',
                    'message': check['message'],
                    'details': check.get('details')
                }
        
        # Lancer ré-entraînement
        logger.info(f"🚀 Lancement ré-entraînement automatique du modèle {model_name}")
        
        from optimization.models.xgboost_trainer import XGBoostTrainer
        
        trainer = XGBoostTrainer(model_name=model_name)
        
        # Ré-entraîner avec paramètres optimisés
        result = trainer.train(
            timeframe_days=90,  # Plus de données
            min_trades=50,
            feature_selection=True,
            max_features=30,
            max_depth=4,  # Réduit pour moins d'overfitting
            learning_rate=0.05,
            n_estimators=150
        )
        
        logger.info(f"✅ Ré-entraînement terminé avec succès")
        
        return {
            'status': 'success',
            'message': 'Modèle ré-entraîné avec succès',
            'result': result
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur auto_retrain_if_needed: {e}", exc_info=True)
        return {
            'status': 'error',
            'message': f'Erreur: {str(e)}'
        }


def get_retrain_schedule_info() -> Dict:
    """
    Récupérer infos sur le prochain ré-entraînement planifié
    
    Returns:
        Dict avec infos planning
    """
    try:
        check = check_retrain_needed()
        
        if check['retrain_needed']:
            return {
                'status': 'ready',
                'message': 'Ré-entraînement recommandé maintenant',
                'details': check.get('details')
            }
        
        details = check.get('details', {})
        new_trades = details.get('new_trades_count', 0)
        min_required = details.get('min_new_trades_required', 100)
        remaining_trades = max(0, min_required - new_trades)
        
        days_since = details.get('days_since_training', 0)
        min_days = details.get('min_days_required', 7)
        remaining_days = max(0, min_days - days_since)
        
        return {
            'status': 'scheduled',
            'message': f'Ré-entraînement dans ~{remaining_days} jours ou {remaining_trades} trades',
            'details': {
                'remaining_trades': remaining_trades,
                'remaining_days': remaining_days,
                'current_new_trades': new_trades,
                'days_since_training': days_since
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_retrain_schedule_info: {e}", exc_info=True)
        return {
            'status': 'unknown',
            'message': 'Impossible de récupérer les informations'
        }
