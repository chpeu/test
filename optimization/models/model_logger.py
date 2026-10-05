"""
Model Logger - Enregistre les métadonnées des modèles ML dans PostgreSQL
"""
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime

try:
    from psycopg2.extras import RealDictCursor
except ImportError:
    RealDictCursor = None

logger = logging.getLogger(__name__)


def log_model_to_db(
    model_name: str,
    model_type: str,
    version: str,
    model_path: str,
    preprocessor_path: Optional[str],
    metrics: Dict[str, Any],
    training_info: Dict[str, Any],
    model_params: Dict[str, Any],
    feature_importance: list,
    is_active: bool = False
) -> Optional[int]:
    """
    Enregistre un modèle ML dans la table ml_models
    
    Args:
        model_name: Nom unique (xgboost_v1, xgboost_v2)
        model_type: Type de modèle (XGBClassifier, etc.)
        version: Version (1.0, 2.0)
        model_path: Chemin vers .pkl
        preprocessor_path: Chemin vers preprocessor
        metrics: Dict avec train/test/val metrics
        training_info: Dict avec timeframe_days, samples, etc.
        model_params: Hyperparamètres du modèle
        feature_importance: Top features
        is_active: Si TRUE, désactive les autres modèles actifs
        
    Returns:
        ID du modèle créé ou None si erreur
    """
    try:
        from core.postgresql_datalogger import get_pg_datalogger
        
        pg = get_pg_datalogger()
        if not pg or not pg.enabled:
            logger.warning("⚠️ PostgreSQL non disponible, skip log_model_to_db")
            return None
        
        # Extraire métriques
        train_metrics = metrics.get('train', {})
        test_metrics = metrics.get('test', {})
        val_metrics = metrics.get('validation', {})  # V2 uniquement
        gaps = metrics.get('gaps', {})
        
        # Si is_active=True, désactiver les autres modèles actifs
        if is_active:
            update_query = "UPDATE ml_models SET is_active = FALSE WHERE is_active = TRUE"
            pg._execute_query(update_query)
        
        # Insérer le nouveau modèle
        insert_query = """
            INSERT INTO ml_models (
                model_name, model_type, version, model_path, preprocessor_path,
                train_accuracy, train_roc_auc, test_accuracy, test_roc_auc,
                val_accuracy, val_roc_auc,
                accuracy_gap, roc_auc_gap,
                timeframe_days, min_trades, total_samples, train_samples, test_samples, val_samples,
                training_time_seconds,
                filter_marginal_trades, marginal_threshold, split_type, max_features,
                model_params, feature_importance,
                is_active, trained_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s,
                %s, %s, %s, %s,
                %s, %s,
                %s, %s
            )
            ON CONFLICT (model_name) DO UPDATE SET
                model_type = EXCLUDED.model_type,
                version = EXCLUDED.version,
                model_path = EXCLUDED.model_path,
                preprocessor_path = EXCLUDED.preprocessor_path,
                train_accuracy = EXCLUDED.train_accuracy,
                train_roc_auc = EXCLUDED.train_roc_auc,
                test_accuracy = EXCLUDED.test_accuracy,
                test_roc_auc = EXCLUDED.test_roc_auc,
                val_accuracy = EXCLUDED.val_accuracy,
                val_roc_auc = EXCLUDED.val_roc_auc,
                accuracy_gap = EXCLUDED.accuracy_gap,
                roc_auc_gap = EXCLUDED.roc_auc_gap,
                timeframe_days = EXCLUDED.timeframe_days,
                min_trades = EXCLUDED.min_trades,
                total_samples = EXCLUDED.total_samples,
                train_samples = EXCLUDED.train_samples,
                test_samples = EXCLUDED.test_samples,
                val_samples = EXCLUDED.val_samples,
                training_time_seconds = EXCLUDED.training_time_seconds,
                filter_marginal_trades = EXCLUDED.filter_marginal_trades,
                marginal_threshold = EXCLUDED.marginal_threshold,
                split_type = EXCLUDED.split_type,
                max_features = EXCLUDED.max_features,
                model_params = EXCLUDED.model_params,
                feature_importance = EXCLUDED.feature_importance,
                is_active = EXCLUDED.is_active,
                trained_at = EXCLUDED.trained_at,
                updated_at = NOW()
            RETURNING id
        """
        
        params = (
            model_name, model_type, version, model_path, preprocessor_path,
            train_metrics.get('accuracy'), train_metrics.get('roc_auc'),
            test_metrics.get('accuracy'), test_metrics.get('roc_auc'),
            val_metrics.get('accuracy'), val_metrics.get('roc_auc'),
            gaps.get('accuracy'), gaps.get('roc_auc'),
            training_info.get('timeframe_days'), training_info.get('min_trades'),
            training_info.get('total_samples'), training_info.get('train_samples'),
            training_info.get('test_samples'), training_info.get('val_samples'),
            training_info.get('training_time_seconds'),
            training_info.get('filter_marginal_trades'), training_info.get('marginal_threshold'),
            training_info.get('split_type'), training_info.get('max_features'),
            json.dumps(model_params), json.dumps(feature_importance[:10]),
            is_active, datetime.fromisoformat(training_info['trained_at'])
        )
        
        result = pg._execute_query(insert_query, params, fetch=True, cursor_factory=RealDictCursor)
        
        if result:
            model_id = result[0]['id']
            logger.info(f"✅ Modèle {model_name} enregistré dans PostgreSQL (ID={model_id})")
            return model_id
        else:
            logger.warning(f"⚠️ Impossible d'enregistrer le modèle {model_name}")
            return None
    
    except Exception as e:
        logger.error(f"❌ Erreur log_model_to_db: {e}", exc_info=True)
        return None


def get_active_model() -> Optional[Dict[str, Any]]:
    """Récupère le modèle actif depuis PostgreSQL"""
    try:
        from core.postgresql_datalogger import get_pg_datalogger
        
        pg = get_pg_datalogger()
        if not pg or not pg.enabled:
            return None
        
        query = "SELECT * FROM ml_models WHERE is_active = TRUE LIMIT 1"
        result = pg._execute_query(query, fetch=True, cursor_factory=RealDictCursor)
        
        if result:
            return dict(result[0])
        return None
    
    except Exception as e:
        logger.error(f"❌ Erreur get_active_model: {e}")
        return None


def list_all_models(limit: int = 10) -> list:
    """Liste tous les modèles enregistrés (triés par date)"""
    try:
        from core.postgresql_datalogger import get_pg_datalogger
        
        pg = get_pg_datalogger()
        if not pg or not pg.enabled:
            return []
        
        query = f"""
            SELECT
                id, model_name, model_type, version,
                test_accuracy, test_roc_auc, val_accuracy,
                accuracy_gap, total_samples, trained_at, is_active
            FROM ml_models
            ORDER BY trained_at DESC
            LIMIT {limit}
        """
        
        result = pg._execute_query(query, fetch=True, cursor_factory=RealDictCursor)
        
        return [dict(row) for row in result] if result else []
    
    except Exception as e:
        logger.error(f"❌ Erreur list_all_models: {e}")
        return []


def set_active_model(model_name: str) -> bool:
    """Active un modèle et désactive les autres"""
    try:
        from core.postgresql_datalogger import get_pg_datalogger
        
        pg = get_pg_datalogger()
        if not pg or not pg.enabled:
            return False
        
        # Désactiver tous
        pg._execute_query("UPDATE ml_models SET is_active = FALSE WHERE is_active = TRUE")
        
        # Activer le modèle demandé
        query = "UPDATE ml_models SET is_active = TRUE WHERE model_name = %s"
        pg._execute_query(query, (model_name,))
        
        logger.info(f"✅ Modèle {model_name} défini comme actif")
        return True
    
    except Exception as e:
        logger.error(f"❌ Erreur set_active_model: {e}")
        return False
