#!/usr/bin/env python3
"""
🎯 PREDICTOR OPTIMISÉ - GradientBoosting

Utilise le modèle GradientBoosting optimisé pour filtrer les trades.
Remplace les anciens XGBoost V1/V2.

Usage:
    from optimization.predictor_optimized import OptimizedPredictor
    
    predictor = OptimizedPredictor()
    
    # Prédiction simple
    should_trade, confidence = predictor.predict(features_dict)
    
    # Avec seuil personnalisé
    should_trade, confidence = predictor.predict(features_dict, threshold=0.6)
"""
import logging
import json
import os
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from typing import Dict, Tuple, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

if os.name == 'nt':
    os.environ.setdefault('LOKY_MAX_CPU_COUNT', str(os.cpu_count() or 4))


class OptimizedPredictor:
    """
    Predictor utilisant le modèle GradientBoosting optimisé.
    
    Performance: 64-69% accuracy (vs 50% pour XGBoost V1)
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialiser le predictor.
        
        Args:
            model_path: Chemin vers le modèle (défaut: gradient_boosting_optimized.pkl)
        """
        self.model = None
        self.metadata = None
        self.preprocessor = None  # Scaler + feature_names
        self.feature_cols = None
        self.is_loaded = False
        
        # Charger le modèle
        self._load_model(model_path)
    
    def _load_model(self, model_path: Optional[str] = None):
        """Charger le modèle et metadata"""
        models_dir = Path("optimization/saved_models")
        
        # Essayer plusieurs chemins
        possible_paths = [
            model_path,
            models_dir / "gradient_boosting_optimized.pkl",  # Modèle optimisé avancé
            models_dir / "best_classifier_latest.pkl",
            models_dir / "optimized_classifier_latest.pkl",
        ]
        
        for path in possible_paths:
            if path and Path(path).exists():
                try:
                    self.model = joblib.load(path)
                    logger.info(f"✅ Modèle chargé: {path}")
                    break
                except Exception as e:
                    logger.warning(f"⚠️ Erreur chargement {path}: {e}")
        
        if self.model is None:
            logger.error("❌ Aucun modèle trouvé!")
            return
        
        # Charger preprocessor (scaler)
        for prep_name in ["gradient_boosting_optimized_preprocessor.pkl", "best_classifier_preprocessor.pkl"]:
            prep_path = models_dir / prep_name
            if prep_path.exists():
                try:
                    self.preprocessor = joblib.load(prep_path)
                    # Extraire feature_names du preprocessor
                    if isinstance(self.preprocessor, dict) and 'feature_names' in self.preprocessor:
                        self.feature_cols = list(self.preprocessor['feature_names'])
                    logger.info(f"✅ Preprocessor chargé: {len(self.feature_cols) if self.feature_cols else 'N/A'} features")
                    break
                except Exception as e:
                    logger.warning(f"⚠️ Erreur preprocessor: {e}")
        
        # Charger metadata
        for metadata_name in ["gradient_boosting_optimized_metadata.json", "best_classifier_metadata.json", "optimized_classifier_metadata.json"]:
            metadata_path = models_dir / metadata_name
            if metadata_path.exists():
                try:
                    with open(metadata_path, 'r') as f:
                        self.metadata = json.load(f)
                    # Si feature_cols pas encore défini, utiliser metadata
                    if not self.feature_cols:
                        self.feature_cols = self.metadata.get('feature_names', self.metadata.get('feature_cols', []))
                    logger.info(f"✅ Metadata chargée: {len(self.feature_cols)} features")
                    break
                except Exception as e:
                    logger.warning(f"⚠️ Erreur metadata: {e}")
        
        self.is_loaded = self.model is not None
    
    def predict(
        self, 
        features: Dict, 
        threshold: float = 0.5
    ) -> Tuple[bool, float]:
        """
        Prédire si un trade devrait être pris.
        
        Args:
            features: Dict avec les features (indicateurs techniques)
            threshold: Seuil de confiance minimum (défaut: 0.5)
        
        Returns:
            Tuple (should_trade, confidence)
            - should_trade: True si le modèle recommande le trade
            - confidence: Probabilité de WIN (0.0 à 1.0)
        """
        if not self.is_loaded:
            logger.warning("⚠️ Modèle non chargé, retourne True par défaut")
            return True, 0.5
        
        try:
            # Convertir features en DataFrame
            df = self._prepare_features(features)

            # Appliquer le preprocessor (scaler) si disponible
            if self.preprocessor is not None and isinstance(self.preprocessor, dict):
                scaler = self.preprocessor.get('scaler')
                if scaler is not None:
                    # 🔥 FIX: Utiliser df.values pour éviter sklearn warning sur feature names
                    scaled = scaler.transform(df.values)
                    try:
                        input_data = pd.DataFrame(scaled, columns=df.columns)
                    except Exception:
                        input_data = scaled
                else:
                    input_data = df
            else:
                input_data = df if isinstance(df, pd.DataFrame) else df

            # Prédire
            proba = self.model.predict_proba(input_data)[0, 1]  # Probabilité de WIN
            should_trade = proba >= threshold
            
            # 🔥 Logging détaillé pour debug
            if should_trade:
                logger.info(f"✅ GB ACCEPT: proba={proba*100:.1f}% >= seuil={threshold*100:.0f}%")
            else:
                logger.info(f"❌ GB REJECT: proba={proba*100:.1f}% < seuil={threshold*100:.0f}%")
            
            return should_trade, float(proba)
            
        except Exception as e:
            logger.error(f"❌ Erreur prédiction: {e}")
            return True, 0.5  # Par défaut, accepter le trade
    
    def predict_batch(
        self, 
        features_list: List[Dict], 
        threshold: float = 0.5
    ) -> List[Tuple[bool, float]]:
        """
        Prédire pour plusieurs trades.
        
        Args:
            features_list: Liste de dicts avec features
            threshold: Seuil de confiance
        
        Returns:
            Liste de (should_trade, confidence)
        """
        results = []
        for features in features_list:
            results.append(self.predict(features, threshold))
        return results
    
    def _prepare_features(self, features: Dict) -> pd.DataFrame:
        """Préparer les features pour le modèle"""
        # Créer DataFrame avec une seule ligne
        df = pd.DataFrame([features])
        
        # Ajouter features temporelles si timestamp présent
        if 'timestamp' in df.columns:
            ts = pd.to_datetime(df['timestamp'])
            df['hour'] = ts.dt.hour
            df['day_of_week'] = ts.dt.dayofweek
            df['good_hour'] = df['hour'].isin([2, 12, 16]).astype(int)
            df['bad_hour'] = df['hour'].isin([4, 23, 18]).astype(int)
            df['asian_session'] = df['hour'].isin(range(0, 8)).astype(int)
            df['european_session'] = df['hour'].isin(range(8, 16)).astype(int)
            df['american_session'] = df['hour'].isin(range(16, 24)).astype(int)
        else:
            # Utiliser l'heure actuelle
            now = datetime.now()
            df['hour'] = now.hour
            df['day_of_week'] = now.weekday()
            df['good_hour'] = int(now.hour in [2, 12, 16])
            df['bad_hour'] = int(now.hour in [4, 23, 18])
            df['asian_session'] = int(now.hour in range(0, 8))
            df['european_session'] = int(now.hour in range(8, 16))
            df['american_session'] = int(now.hour in range(16, 24))
        
        # Ajouter features de momentum
        if 'rsi_1m' in df.columns and 'rsi_5m' in df.columns:
            df['rsi_momentum'] = df['rsi_1m'] - df['rsi_5m']
            df['rsi_oversold'] = (df['rsi_1m'] < 30).astype(int)
            df['rsi_overbought'] = (df['rsi_1m'] > 70).astype(int)
        
        if 'macd_hist_1m' in df.columns and 'macd_hist_5m' in df.columns:
            df['macd_momentum'] = df['macd_hist_1m'] - df['macd_hist_5m']
            df['macd_aligned'] = ((df['macd_hist_1m'] > 0) == (df['macd_hist_5m'] > 0)).astype(int)
        
        if 'atr_pct_1m' in df.columns:
            df['high_volatility'] = (df['atr_pct_1m'] > 0.5).astype(int)  # Seuil approximatif
        
        if 'adx_1m' in df.columns:
            df['strong_trend'] = (df['adx_1m'] > 25).astype(int)
            df['weak_trend'] = (df['adx_1m'] < 20).astype(int)
        
        if 'volume_ratio_1m' in df.columns:
            df['volume_spike'] = (df['volume_ratio_1m'] > 1.5).astype(int)

        if 'di_gap_1m' not in df.columns and 'di_plus_1m' in df.columns and 'di_minus_1m' in df.columns:
            df['di_gap_1m'] = df['di_plus_1m'] - df['di_minus_1m']

        if 'di_gap_5m' not in df.columns and 'di_plus_5m' in df.columns and 'di_minus_5m' in df.columns:
            df['di_gap_5m'] = df['di_plus_5m'] - df['di_minus_5m']

        if 'momentum_1m' not in df.columns and 'rsi_1m' in df.columns and 'macd_hist_1m' in df.columns:
            df['momentum_1m'] = (df['rsi_1m'] / 100) * np.tanh(df['macd_hist_1m'])

        if 'momentum_5m' not in df.columns and 'rsi_5m' in df.columns and 'macd_hist_5m' in df.columns:
            df['momentum_5m'] = (df['rsi_5m'] / 100) * np.tanh(df['macd_hist_5m'])

        if 'momentum_divergence' not in df.columns and 'momentum_1m' in df.columns and 'momentum_5m' in df.columns:
            df['momentum_divergence'] = df['momentum_1m'] - df['momentum_5m']

        if 'macd_momentum_1m' not in df.columns and 'macd_hist_1m' in df.columns and 'macd_hist_prev_1m' in df.columns:
            df['macd_momentum_1m'] = df['macd_hist_1m'] - df['macd_hist_prev_1m']

        if 'macd_momentum_5m' not in df.columns and 'macd_hist_5m' in df.columns and 'macd_hist_prev_5m' in df.columns:
            df['macd_momentum_5m'] = df['macd_hist_5m'] - df['macd_hist_prev_5m']

        if 'rsi_change_1m' not in df.columns and 'rsi_1m' in df.columns and 'rsi_prev_1m' in df.columns:
            df['rsi_change_1m'] = df['rsi_1m'] - df['rsi_prev_1m']

        if 'rsi_change_5m' not in df.columns and 'rsi_5m' in df.columns and 'rsi_prev_5m' in df.columns:
            df['rsi_change_5m'] = df['rsi_5m'] - df['rsi_prev_5m']

        if 'rsi_divergence' not in df.columns and 'rsi_1m' in df.columns and 'rsi_5m' in df.columns:
            df['rsi_divergence'] = (df['rsi_1m'] - df['rsi_5m']).abs()

        if 'trend_strength_1m' not in df.columns and 'adx_1m' in df.columns and 'di_gap_1m' in df.columns:
            df['trend_strength_1m'] = df['adx_1m'] * df['di_gap_1m'].abs() / 100

        if 'trend_strength_5m' not in df.columns and 'adx_5m' in df.columns and 'di_gap_5m' in df.columns:
            df['trend_strength_5m'] = df['adx_5m'] * df['di_gap_5m'].abs() / 100

        if 'volume_divergence' not in df.columns and 'volume_ratio_1m' in df.columns and 'volume_ratio_5m' in df.columns:
            df['volume_divergence'] = (df['volume_ratio_1m'] - df['volume_ratio_5m']).abs()

        if 'volatility_ratio' not in df.columns and 'atr_pct_1m' in df.columns and 'atr_pct_5m' in df.columns:
            df['volatility_ratio'] = df['atr_pct_1m'] / (df['atr_pct_5m'] + 1e-8)

        if 'volatility_momentum_product' not in df.columns and 'volatility_ratio' in df.columns and 'momentum_1m' in df.columns:
            df['volatility_momentum_product'] = df['volatility_ratio'] * df['momentum_1m']
        
        # S'assurer que toutes les colonnes requises sont présentes
        if self.feature_cols:
            present_cols = set(df.columns)
            expected_cols = set(self.feature_cols)
            missing_cols = expected_cols - present_cols
            
            # 🔥 DIAGNOSTIC: Logger les features manquantes si significatif
            if len(missing_cols) > len(self.feature_cols) * 0.5:
                logger.warning(f"⚠️ >50% features manquantes ({len(missing_cols)}/{len(self.feature_cols)}) - prédiction peu fiable")
            elif missing_cols:
                logger.debug(f"📊 Features manquantes: {len(missing_cols)}/{len(self.feature_cols)}")
            
            # Remplir les features manquantes avec 0
            for col in missing_cols:
                df[col] = 0
            
            # Garder seulement les colonnes du modèle
            df = df[self.feature_cols]
        
        return df.fillna(0)
    
    def get_model_info(self) -> Dict:
        """Obtenir les infos du modèle"""
        if not self.metadata:
            return {'status': 'not_loaded'}
        
        return {
            'status': 'loaded',
            'model_type': self.metadata.get('best_model', 'unknown'),
            'accuracy': self.metadata.get('metrics', {}).get('test_acc', 0),
            'f1_score': self.metadata.get('metrics', {}).get('test_f1', 0),
            'n_features': len(self.feature_cols) if self.feature_cols else 0,
            'timestamp': self.metadata.get('timestamp', 'unknown')
        }


# Instance globale (singleton)
_predictor_instance: Optional[OptimizedPredictor] = None


def get_predictor() -> OptimizedPredictor:
    """Obtenir l'instance du predictor (singleton)"""
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = OptimizedPredictor()
    return _predictor_instance


def predict_trade(features: Dict, threshold: float = 0.5) -> Tuple[bool, float]:
    """
    Fonction helper pour prédire un trade.
    
    Args:
        features: Dict avec indicateurs techniques
        threshold: Seuil de confiance (défaut: 0.5)
    
    Returns:
        (should_trade, confidence)
    
    Example:
        >>> should_trade, confidence = predict_trade({
        ...     'rsi_1m': 45,
        ...     'macd_hist_1m': 0.002,
        ...     'adx_1m': 28,
        ...     # ... autres indicateurs
        ... })
        >>> if should_trade:
        ...     print(f"Trade recommandé (confiance: {confidence:.1%})")
    """
    predictor = get_predictor()
    return predictor.predict(features, threshold)


# Pour compatibilité avec le code existant
class MLPredictor:
    """Alias pour compatibilité avec l'ancien code"""
    
    def __init__(self):
        self.predictor = get_predictor()
    
    def predict(self, features: Dict) -> Tuple[bool, float]:
        return self.predictor.predict(features)
    
    def get_info(self) -> Dict:
        return self.predictor.get_model_info()
