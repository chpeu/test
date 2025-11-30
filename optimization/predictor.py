"""
ML Predictor - Service de prédiction en temps réel
Charge les modèles entraînés et fait des prédictions sur de nouvelles opportunités
"""

import os
import logging
import pickle
import json
from typing import Dict, Optional, List
import pandas as pd
import numpy as np
from datetime import datetime
import joblib

logger = logging.getLogger(__name__)


class MLPredictor:
    """Service de prédiction ML avec modèles pré-entraînés"""
    
    def __init__(self, model_name: str = "xgboost_v1"):
        self.model_name = model_name
        self.model = None
        self.preprocessor = None
        self.metadata = None
        self.feature_names = None
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
            
            with open(model_path, 'rb') as f:
                self.model = pickle.load(f)
            
            # Charger preprocessor
            preprocessor_path = f"{models_dir}/{self.model_name}_preprocessor.pkl"
            if not os.path.exists(preprocessor_path):
                logger.warning(f"Preprocessor non trouvé à {preprocessor_path}")
                return False
            
            try:
                self.preprocessor = joblib.load(preprocessor_path)
            except Exception:
                with open(preprocessor_path, 'rb') as f:
                    self.preprocessor = pickle.load(f)
            
            # Charger metadata
            metadata_path = f"{models_dir}/{self.model_name}_metadata.json"
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    self.metadata = json.load(f)
            
            # Extraire feature names du preprocessor
            # Pour un Pipeline avec feature selection, le scaler contient features APRÈS sélection
            # Il faut récupérer les features AVANT sélection depuis le metadata
            if self.metadata and 'feature_names' in self.metadata:
                # Meilleure source: metadata contient les features complètes
                self.feature_names = list(self.metadata['feature_names'])
            elif self.metadata and 'feature_names' in self.metadata.get('training_info', {}):
                self.feature_names = list(self.metadata['training_info']['feature_names'])
            elif isinstance(self.preprocessor, dict) and 'feature_names' in self.preprocessor:
                # Format dictionnaire avec feature_names
                self.feature_names = list(self.preprocessor['feature_names'])
            elif hasattr(self.preprocessor, 'named_steps'):
                # Pipeline: essayer d'extraire du scaler
                scaler_step = self.preprocessor.named_steps.get('scaler')
                if scaler_step and hasattr(scaler_step, 'feature_names'):
                    self.feature_names = list(scaler_step.feature_names)
                elif scaler_step and hasattr(scaler_step, 'feature_names_in_'):
                    self.feature_names = list(scaler_step.feature_names_in_)
                else:
                    self.feature_names = []
            elif hasattr(self.preprocessor, 'feature_names_in_'):
                self.feature_names = list(self.preprocessor.feature_names_in_)
            elif hasattr(self.preprocessor, 'feature_names'):
                self.feature_names = list(self.preprocessor.feature_names)
            else:
                logger.warning("Preprocessor n'a pas d'information de features")
                self.feature_names = []
            
            self.loaded = True
            logger.info(f"✅ Modèle {self.model_name} chargé avec succès ({len(self.feature_names)} features)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur chargement modèle {self.model_name}: {e}", exc_info=True)
            return False
    
    def predict(self, features: Dict) -> Optional[Dict]:
        """
        Fait une prédiction sur une opportunité
        
        Args:
            features: Dictionnaire avec toutes les features nécessaires
            
        Returns:
            Dict avec prédiction, probabilité, et metadata
        """
        try:
            # Charger modèle si pas déjà fait
            if not self.loaded:
                if not self.load_model():
                    return None
            
            # Convertir features en DataFrame
            df = pd.DataFrame([features])
            
            # Vérifier features manquantes
            missing_features = set(self.feature_names) - set(df.columns)
            if missing_features:
                logger.warning(f"Features manquantes: {missing_features}")
                # Ajouter features manquantes avec 0
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
            
            # Prédiction
            prediction = int(self.model.predict(X)[0])
            
            # Probabilités
            if hasattr(self.model, 'predict_proba'):
                proba = self.model.predict_proba(X)[0]
                confidence = float(max(proba))
                win_probability = float(proba[1] if len(proba) > 1 else proba[0])
            else:
                confidence = 0.5
                win_probability = 0.5
            
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
            
            result = {
                'prediction': 'win' if prediction == 1 else 'loss',
                'prediction_value': prediction,
                'win_probability': win_probability,
                'loss_probability': 1 - win_probability,
                'confidence': confidence,
                'model_name': self.model_name,
                'predicted_at': datetime.now().isoformat(),
                'top_features': top_features
            }
            
            # Ajouter infos du metadata si disponible
            if self.metadata:
                result['model_version'] = self.metadata.get('version')
                result['model_performance'] = {
                    'test_accuracy': self.metadata.get('metrics', {}).get('test', {}).get('accuracy'),
                    'test_f1': self.metadata.get('metrics', {}).get('test', {}).get('f1')
                }
            
            logger.info(f"✅ Prédiction: {result['prediction']} (confidence: {confidence:.2%})")
            return result
            
        except Exception as e:
            logger.error(f"❌ Erreur prédiction: {e}", exc_info=True)
            return None
    
    def batch_predict(self, features_list: List[Dict]) -> List[Optional[Dict]]:
        """
        Fait des prédictions en batch
        
        Args:
            features_list: Liste de dictionnaires de features
            
        Returns:
            Liste de prédictions
        """
        return [self.predict(features) for features in features_list]


# Singleton pour éviter de recharger le modèle à chaque fois
_predictor_instance: Optional[MLPredictor] = None


def get_predictor(model_name: str = "xgboost_v1") -> MLPredictor:
    """Récupère ou crée l'instance singleton du predictor"""
    global _predictor_instance
    
    if _predictor_instance is None or _predictor_instance.model_name != model_name:
        _predictor_instance = MLPredictor(model_name)
        _predictor_instance.load_model()
    
    return _predictor_instance


def predict_opportunity(
    features: Dict, 
    model_name: str = "xgboost_v1",
    symbol: Optional[str] = None,
    scan_id: Optional[int] = None,
    log_to_db: bool = True
) -> Optional[Dict]:
    """
    Helper function pour faire une prédiction rapide
    
    Args:
        features: Features de l'opportunité
        model_name: Nom du modèle à utiliser
        symbol: Symbole de l'opportunité (pour logging)
        scan_id: ID du scan (pour logging)
        log_to_db: Si True, log la prédiction dans PostgreSQL
        
    Returns:
        Prédiction ou None si erreur
    """
    # Appliquer feature engineering pour obtenir toutes les features dérivées
    try:
        from optimization.data.feature_engineering import calculate_derived_features
        
        # Convertir en DataFrame pour feature engineering
        df_features = pd.DataFrame([features])
        df_engineered = calculate_derived_features(df_features)
        
        # Reconvertir en dict
        engineered_features = df_engineered.iloc[0].to_dict()
    except Exception as e:
        logger.warning(f"⚠️ Erreur feature engineering, utilisation features brutes: {e}")
        engineered_features = features
    
    predictor = get_predictor(model_name)
    prediction = predictor.predict(engineered_features)
    
    # Logger dans DB si demandé
    if prediction and log_to_db and symbol:
        try:
            from optimization.prediction_logger import log_prediction
            
            prediction_id = log_prediction(
                prediction_data=prediction,
                symbol=symbol,
                scan_id=scan_id,
                opportunity_timestamp=datetime.now(),
                metadata={'features_count': len(features)}
            )
            
            if prediction_id:
                prediction['prediction_id'] = prediction_id
                logger.info(f"✅ Prédiction loggée: ID={prediction_id}")
        except Exception as e:
            logger.warning(f"⚠️ Impossible de logger prédiction: {e}")
    
    # Envoyer alerte si haute confiance
    if prediction and symbol:
        try:
            from optimization.ml_alerts import send_ml_alert
            
            alert_result = send_ml_alert(
                prediction=prediction,
                symbol=symbol,
                scan_id=scan_id,
                min_confidence=0.75,  # Alerte seulement si confiance >= 75%
                channels=['console']  # Par défaut console, configurable via env
            )
            
            if alert_result:
                logger.info(f"🔔 Alerte ML envoyée pour {symbol}")
        except Exception as e:
            logger.warning(f"⚠️ Impossible d'envoyer alerte: {e}")
    
    return prediction
