"""
ML Predictor V2 - Service de prédiction PNL% (Régression)
Charge les modèles XGBoost V2 entraînés et prédit le PNL% exact
"""

import os
import logging
import pickle
import json
from typing import Dict, Optional, List, Tuple
import pandas as pd
import numpy as np
from datetime import datetime
import joblib

# Imports pour feature engineering et logging
from optimization.data.feature_engineering import calculate_derived_features
from optimization.prediction_logger import log_prediction

logger = logging.getLogger(__name__)


class MLPredictorV2:
    """Service de prédiction ML V2 (Régression PNL%)"""
    
    def __init__(self, model_name: str = "xgboost_v2_latest"):
        self.model_name = model_name
        self.model = None
        self.preprocessor = None
        self.metadata = None
        self.feature_names = None
        self.selected_features = None
        self.loaded = False
        
    def load_model(self) -> bool:
        """Charge le modèle et le preprocessor depuis les fichiers sauvegardés"""
        try:
            models_dir = "optimization/saved_models"
            
            # Charger modèle
            model_path = f"{models_dir}/{self.model_name}.pkl"
            if not os.path.exists(model_path):
                logger.warning(f"Modèle {self.model_name} non trouvé à {model_path}")
                return False
            
            self.model = joblib.load(model_path)
            logger.info(f"✅ Modèle V2 chargé: {model_path}")
            
            # Charger preprocessor
            preprocessor_path = f"{models_dir}/{self.model_name}_preprocessor.pkl"
            if not os.path.exists(preprocessor_path):
                logger.warning(f"Preprocessor non trouvé à {preprocessor_path}")
                return False
            
            self.preprocessor = joblib.load(preprocessor_path)
            logger.info(f"✅ Preprocessor V2 chargé: {preprocessor_path}")

            # Charger metadata (optionnel, peut venir de PostgreSQL)
            metadata_path = f"{models_dir}/{self.model_name}_metadata.json"
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, 'r') as f:
                        self.metadata = json.load(f)
                    logger.info(f"✅ Metadata V2 chargée")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur chargement metadata (non bloquant): {e}")
                    self.metadata = None

            # Récupérer features sélectionnées
            if self.metadata and 'selected_features' in self.metadata:
                self.selected_features = self.metadata['selected_features']
                self.feature_names = self.selected_features
            elif isinstance(self.preprocessor, dict) and 'feature_names' in self.preprocessor:
                # Format dictionnaire avec feature_names
                self.feature_names = list(self.preprocessor['feature_names'])
                self.selected_features = self.feature_names
            elif hasattr(self.preprocessor, 'feature_names_in_'):
                self.feature_names = list(self.preprocessor.feature_names_in_)
            else:
                logger.warning("⚠️ Impossible de déterminer les features du modèle")
                self.feature_names = []

            self.loaded = True
            logger.info(f"✅ Modèle V2 {self.model_name} prêt ({len(self.feature_names)} features)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur chargement modèle V2 {self.model_name}: {e}", exc_info=True)
            return False
    
    def load_from_postgres(self, model_id: Optional[int] = None) -> bool:
        """
        Charge le modèle depuis PostgreSQL (modèle actif ou ID spécifique)
        
        Args:
            model_id: ID du modèle, ou None pour charger le modèle actif
            
        Returns:
            True si succès, False sinon
        """
        try:
            from core.simple_pg_logger import SimplePGLogger
            
            pg = SimplePGLogger()
            if not pg.enabled:
                logger.warning("PostgreSQL non disponible, utilisation fichiers .pkl")
                return self.load_model()
            
            # Requête pour récupérer modèle actif ou spécifique
            if model_id:
                query = "SELECT * FROM ml_models WHERE id = %s"
                params = (model_id,)
            else:
                query = """
                    SELECT * FROM ml_models 
                    WHERE model_name LIKE 'xgboost_v2%' 
                      AND is_active = TRUE 
                    ORDER BY trained_at DESC 
                    LIMIT 1
                """
                params = None
            
            cursor = pg.conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            row = cursor.fetchone()
            cursor.close()
            
            if not row:
                logger.warning("Aucun modèle V2 actif trouvé dans PostgreSQL")
                return self.load_model()
            
            # Extraire infos du modèle
            cols = [desc[0] for desc in cursor.description]
            model_data = dict(zip(cols, row))
            
            # Charger depuis les paths
            model_path = model_data['model_path']
            preprocessor_path = model_data['preprocessor_path']
            
            if not os.path.exists(model_path) or not os.path.exists(preprocessor_path):
                logger.error(f"Fichiers modèle introuvables: {model_path}")
                return False
            
            self.model = joblib.load(model_path)
            self.preprocessor = joblib.load(preprocessor_path)
            
            # Construire metadata depuis PostgreSQL
            self.metadata = {
                'model_name': model_data['model_name'],
                'model_type': model_data['model_type'],
                'version': model_data['version'],
                'trained_at': model_data['trained_at'].isoformat() if model_data['trained_at'] else None,
                'metrics': {
                    'train': {
                        'r2': model_data.get('train_r2'),
                        'mae': model_data.get('train_mae')
                    },
                    'val': {
                        'r2': model_data.get('val_r2'),
                        'mae': model_data.get('val_mae')
                    },
                    'test': {
                        'r2': model_data.get('test_r2'),
                        'mae': model_data.get('test_mae'),
                        'f1': model_data.get('test_f1')
                    }
                },
                'model_params': json.loads(model_data['model_params']) if model_data.get('model_params') else {},
                'selected_features': json.loads(model_data['selected_features']) if model_data.get('selected_features') else []
            }
            
            self.selected_features = self.metadata.get('selected_features', [])
            self.feature_names = self.selected_features
            self.loaded = True
            
            logger.info(f"✅ Modèle V2 chargé depuis PostgreSQL: {self.metadata['model_name']}")
            logger.info(f"   Test R²={self.metadata['metrics']['test']['r2']:.3f}, MAE={self.metadata['metrics']['test']['mae']:.3f}%")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur chargement depuis PostgreSQL: {e}", exc_info=True)
            return self.load_model()
    
    def predict(self, features: Dict, return_classification: bool = True) -> Optional[Dict]:
        """
        Fait une prédiction de PNL% sur une opportunité
        
        Args:
            features: Dictionnaire avec toutes les features nécessaires
            return_classification: Si True, ajoute classification WIN/LOSS avec seuil 0
            
        Returns:
            Dict avec prédiction PNL%, classification optionnelle, et metadata
        """
        try:
            # Charger modèle si pas déjà fait
            if not self.loaded:
                # Essayer PostgreSQL d'abord, fallback sur fichiers
                if not self.load_from_postgres():
                    return None
            
            # Feature engineering pour obtenir toutes les features dérivées
            try:
                from optimization.data.feature_engineering import calculate_derived_features
                df_features = pd.DataFrame([features])
                df_engineered = calculate_derived_features(df_features)
                engineered_features = df_engineered.iloc[0].to_dict()
            except Exception as e:
                logger.warning(f"⚠️ Feature engineering échoué, features brutes: {e}")
                engineered_features = features
            
            # Convertir en DataFrame
            df = pd.DataFrame([engineered_features])
            
            # Vérifier features manquantes
            if self.feature_names:
                missing_features = set(self.feature_names) - set(df.columns)
                if missing_features:
                    logger.warning(f"Features manquantes: {len(missing_features)}/{len(self.feature_names)}")
                    for feat in missing_features:
                        df[feat] = 0
                
                # Garder seulement les features du modèle dans le bon ordre
                df = df[self.feature_names]
            
            # Remplacer NaN/inf
            df = df.replace([np.inf, -np.inf], 0)
            df = df.fillna(0)
            
            # Preprocesser - gérer différents formats
            if isinstance(self.preprocessor, dict):
                # Format dictionnaire: extraire scaler et imputer
                scaler = self.preprocessor.get('scaler')
                imputer = self.preprocessor.get('imputer')
                
                if imputer is not None:
                    df = pd.DataFrame(imputer.transform(df), columns=df.columns)
                if scaler is not None:
                    X = scaler.transform(df)
                else:
                    X = df.values
            elif hasattr(self.preprocessor, 'transform'):
                # Format sklearn standard
                X = self.preprocessor.transform(df)
            else:
                # Pas de preprocessor, utiliser directement
                X = df.values
            
            # Prédiction PNL%
            predicted_pnl = float(self.model.predict(X)[0])
            
            # Classification WIN/LOSS avec seuil 0
            predicted_class = 'win' if predicted_pnl > 0 else 'loss'
            predicted_class_value = 1 if predicted_pnl > 0 else 0
            
            # Feature importance pour cette prédiction (si XGBoost)
            top_features = None
            if hasattr(self.model, 'get_booster'):
                try:
                    feature_importance = self.model.get_booster().get_score(importance_type='gain')
                    top_features = [
                        {'feature': k, 'importance': float(v)}
                        for k, v in sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:5]
                    ]
                except:
                    pass
            
            # Construire résultat
            result = {
                'predicted_pnl': predicted_pnl,
                'predicted_pnl_formatted': f"{predicted_pnl:+.2f}%",
                'model_name': self.model_name,
                'model_type': 'regression',
                'predicted_at': datetime.now().isoformat(),
                'top_features': top_features
            }
            
            # Ajouter classification si demandé
            if return_classification:
                result.update({
                    'classification': predicted_class,
                    'classification_value': predicted_class_value,
                    'is_profitable': predicted_pnl > 0
                })
            
            # Ajouter infos du metadata si disponible
            if self.metadata:
                result['model_version'] = self.metadata.get('version')
                result['model_trained_at'] = self.metadata.get('trained_at')
                result['model_performance'] = {
                    'test_r2': self.metadata.get('metrics', {}).get('test', {}).get('r2'),
                    'test_mae': self.metadata.get('metrics', {}).get('test', {}).get('mae'),
                    'test_f1': self.metadata.get('metrics', {}).get('test', {}).get('f1')
                }
            
            logger.info(f"✅ Prédiction V2: PNL={predicted_pnl:+.2f}% ({predicted_class.upper()})")
            return result
            
        except Exception as e:
            logger.error(f"❌ Erreur prédiction V2: {e}", exc_info=True)
            return None
    
    def should_reject_trade(
        self, 
        features: Dict, 
        min_expected_pnl: float = 0.3
    ) -> Tuple[bool, Optional[float], Optional[str]]:
        """
        Détermine si un trade doit être rejeté basé sur le PNL prédit
        
        Args:
            features: Features de l'opportunité
            min_expected_pnl: PNL minimum requis (%)
            
        Returns:
            (should_reject, predicted_pnl, reason)
        """
        try:
            prediction = self.predict(features, return_classification=True)
            
            if not prediction:
                return (False, None, "ML V2 indisponible")
            
            predicted_pnl = prediction['predicted_pnl']
            
            # Rejeter si PNL prédit < minimum requis
            if predicted_pnl < min_expected_pnl:
                reason = f"ML V2: PNL prédit {predicted_pnl:+.2f}% < minimum {min_expected_pnl:+.2f}%"
                logger.info(f"🚫 {reason}")
                return (True, predicted_pnl, reason)
            
            # Accepter
            logger.info(f"✅ ML V2: PNL prédit {predicted_pnl:+.2f}% ≥ minimum {min_expected_pnl:+.2f}%")
            return (False, predicted_pnl, None)
            
        except Exception as e:
            logger.error(f"❌ Erreur should_reject_trade V2: {e}")
            return (False, None, "Erreur ML V2")
    
    def batch_predict(self, features_list: List[Dict]) -> List[Optional[Dict]]:
        """
        Fait des prédictions en batch
        
        Args:
            features_list: Liste de dictionnaires de features
            
        Returns:
            Liste de prédictions
        """
        return [self.predict(features) for features in features_list]
    
    def get_confidence_interval(
        self, 
        features: Dict, 
        confidence_level: float = 0.95
    ) -> Optional[Tuple[float, float]]:
        """
        Calcule un intervalle de confiance pour la prédiction (approximatif)
        
        Args:
            features: Features de l'opportunité
            confidence_level: Niveau de confiance (0.95 = 95%)
            
        Returns:
            (lower_bound, upper_bound) ou None
        """
        try:
            prediction = self.predict(features, return_classification=False)
            if not prediction:
                return None
            
            predicted_pnl = prediction['predicted_pnl']
            
            # Approximation: utiliser MAE du modèle comme mesure d'incertitude
            if self.metadata:
                mae = self.metadata.get('metrics', {}).get('test', {}).get('mae', 0.5)
            else:
                mae = 0.5  # Default
            
            # Intervalle approximatif basé sur MAE
            # Facteur de confiance (1.96 pour 95%, 2.576 pour 99%)
            z_score = 1.96 if confidence_level == 0.95 else 2.576
            margin = mae * z_score
            
            lower_bound = predicted_pnl - margin
            upper_bound = predicted_pnl + margin
            
            logger.info(f"📊 Intervalle {confidence_level*100:.0f}%: [{lower_bound:+.2f}%, {upper_bound:+.2f}%]")
            return (lower_bound, upper_bound)
            
        except Exception as e:
            logger.error(f"❌ Erreur confidence_interval: {e}")
            return None


# Singleton pour éviter de recharger le modèle à chaque fois
_predictor_v2_instance: Optional[MLPredictorV2] = None


def get_predictor_v2(model_name: str = "xgboost_v2_latest") -> MLPredictorV2:
    """Récupère ou crée l'instance singleton du predictor V2"""
    global _predictor_v2_instance
    
    if _predictor_v2_instance is None or _predictor_v2_instance.model_name != model_name:
        _predictor_v2_instance = MLPredictorV2(model_name)
        _predictor_v2_instance.load_from_postgres()  # Essayer PostgreSQL d'abord
    
    return _predictor_v2_instance


def predict_pnl(
    features: Dict,
    model_name: str = "xgboost_v2_latest",
    symbol: Optional[str] = None,
    scan_id: Optional[int] = None,
    log_to_db: bool = False
) -> Optional[Dict]:
    """
    Helper function pour faire une prédiction PNL% rapide
    
    Args:
        features: Features de l'opportunité
        model_name: Nom du modèle à utiliser
        symbol: Symbole de l'opportunité (pour logging)
        scan_id: ID du scan (pour logging)
        log_to_db: Si True, log la prédiction dans PostgreSQL
        
    Returns:
        Prédiction ou None si erreur
    """
    predictor = get_predictor_v2(model_name)
    prediction = predictor.predict(features, return_classification=True)
    
    # Logger dans DB si demandé
    if prediction and log_to_db and symbol:
        try:
            # Adapter format pour prediction_logger
            prediction_adapted = {
                **prediction,
                'prediction': prediction['classification'],
                'prediction_value': prediction['classification_value'],
                'confidence': abs(prediction['predicted_pnl']) / 5.0  # Pseudo-confidence basée sur magnitude
            }

            prediction_id = log_prediction(
                prediction_data=prediction_adapted,
                symbol=symbol,
                scan_id=scan_id,
                opportunity_timestamp=datetime.now(),
                metadata={'model_type': 'v2_regression'}
            )

            if prediction_id:
                prediction['prediction_id'] = prediction_id
                logger.info(f"✅ Prédiction V2 loggée: ID={prediction_id}")
        except Exception as e:
            logger.warning(f"⚠️ Impossible de logger prédiction V2: {e}")
    
    return prediction
