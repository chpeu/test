"""
Preprocessor - Normalisation et préparation features pour ML
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional, Dict
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.impute import SimpleImputer
import logging
import joblib
from pathlib import Path

logger = logging.getLogger(__name__)


class FeaturePreprocessor:
    """
    Préprocesseur de features pour ML
    - Imputation valeurs manquantes
    - Normalisation
    - Encoding catégoriel
    - Sauvegarde scalers pour production
    """
    
    def __init__(self, scaler_type: str = 'robust'):
        """
        Args:
            scaler_type: 'standard' ou 'robust' (robust meilleur avec outliers)
        """
        self.scaler_type = scaler_type
        self.scaler = RobustScaler() if scaler_type == 'robust' else StandardScaler()
        self.imputer = SimpleImputer(strategy='median')
        self.feature_names = None
        self.is_fitted = False
        
    def fit_transform(
        self, 
        df: pd.DataFrame, 
        target_col: str = 'target_win'
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Fit et transform features
        
        Args:
            df: DataFrame avec features
            target_col: Nom colonne target
            
        Returns:
            X_scaled, y
        """
        # Séparer features et target
        if target_col not in df.columns:
            raise ValueError(f"Target column '{target_col}' not found")
        
        y = df[target_col]
        
        # Colonnes à exclure
        exclude_cols = [
            'scan_id', 'timestamp', 'symbol', 
            target_col, 'target_pnl', 'is_opportunity'
        ]
        
        feature_cols = [col for col in df.columns if col not in exclude_cols]
        X = df[feature_cols].copy()
        
        self.feature_names = feature_cols
        
        logger.info(f"📊 Preprocessing {len(X)} samples, {len(feature_cols)} features")
        
        # Convertir booléens en int
        bool_cols = X.select_dtypes(include=['bool']).columns
        X[bool_cols] = X[bool_cols].astype(int)
        
        # Imputation
        X_imputed = pd.DataFrame(
            self.imputer.fit_transform(X),
            columns=feature_cols,
            index=X.index
        )
        
        # Normalisation
        X_scaled = pd.DataFrame(
            self.scaler.fit_transform(X_imputed),
            columns=feature_cols,
            index=X.index
        )
        
        self.is_fitted = True
        logger.info(f"✅ Preprocessing complete - {self.scaler_type} scaler fitted")
        
        return X_scaled, y
    
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform uniquement (sans fit) - pour production
        
        Args:
            df: DataFrame avec features
            
        Returns:
            X_scaled
        """
        if not self.is_fitted:
            raise ValueError("Preprocessor not fitted. Call fit_transform first.")
        
        # Même logique mais sans fit
        exclude_cols = [
            'scan_id', 'timestamp', 'symbol', 
            'target_win', 'target_pnl', 'is_opportunity'
        ]
        
        feature_cols = [col for col in df.columns if col not in exclude_cols and col in self.feature_names]
        X = df[feature_cols].copy()
        
        # Convertir booléens
        bool_cols = X.select_dtypes(include=['bool']).columns
        X[bool_cols] = X[bool_cols].astype(int)
        
        # Imputation et normalisation
        X_imputed = pd.DataFrame(
            self.imputer.transform(X),
            columns=feature_cols,
            index=X.index
        )
        
        X_scaled = pd.DataFrame(
            self.scaler.transform(X_imputed),
            columns=feature_cols,
            index=X.index
        )
        
        return X_scaled
    
    def save(self, filepath: str):
        """Sauvegarder scaler et imputer"""
        if not self.is_fitted:
            raise ValueError("Cannot save unfitted preprocessor")
        
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        joblib.dump({
            'scaler': self.scaler,
            'imputer': self.imputer,
            'feature_names': self.feature_names,
            'scaler_type': self.scaler_type
        }, filepath)
        
        logger.info(f"💾 Preprocessor saved to {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> 'FeaturePreprocessor':
        """Charger scaler et imputer"""
        data = joblib.load(filepath)
        
        preprocessor = cls(scaler_type=data['scaler_type'])
        preprocessor.scaler = data['scaler']
        preprocessor.imputer = data['imputer']
        preprocessor.feature_names = data['feature_names']
        preprocessor.is_fitted = True
        
        logger.info(f"📂 Preprocessor loaded from {filepath}")
        return preprocessor


def preprocess_features(
    df: pd.DataFrame,
    target_col: str = 'target_win',
    scaler_type: str = 'robust',
    save_preprocessor: bool = False,
    preprocessor_path: Optional[str] = None
) -> Tuple[pd.DataFrame, pd.Series, Optional[FeaturePreprocessor]]:
    """
    Helper function pour preprocessing rapide
    
    Args:
        df: DataFrame features
        target_col: Colonne target
        scaler_type: Type de scaler
        save_preprocessor: Sauvegarder pour production
        preprocessor_path: Chemin sauvegarde
        
    Returns:
        X_scaled, y, preprocessor (si save_preprocessor=True)
    """
    preprocessor = FeaturePreprocessor(scaler_type=scaler_type)
    X_scaled, y = preprocessor.fit_transform(df, target_col=target_col)
    
    if save_preprocessor:
        if preprocessor_path is None:
            preprocessor_path = "optimization/saved_models/preprocessor.pkl"
        preprocessor.save(preprocessor_path)
    
    return X_scaled, y, preprocessor if save_preprocessor else None


def handle_class_imbalance(y: pd.Series, strategy: str = 'auto') -> Dict:
    """
    Calculer class weights pour gérer déséquilibre
    
    Args:
        y: Target series
        strategy: 'balanced' ou 'auto'
        
    Returns:
        Dict avec class weights
    """
    from sklearn.utils.class_weight import compute_class_weight
    
    classes = np.unique(y)
    weights = compute_class_weight(
        class_weight=strategy,
        classes=classes,
        y=y
    )
    
    class_weights = {cls: weight for cls, weight in zip(classes, weights)}
    
    # Log ratio
    win_count = (y == 1).sum()
    loss_count = (y == 0).sum()
    ratio = win_count / loss_count if loss_count > 0 else 1.0
    
    logger.info(f"📊 Class distribution: Win={win_count}, Loss={loss_count}, Ratio={ratio:.2f}")
    logger.info(f"⚖️ Class weights: {class_weights}")
    
    return class_weights
