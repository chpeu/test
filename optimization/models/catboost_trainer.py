"""
🐱 CATBOOST TRAINER - Modèle ML Moderne pour Trading
Plus performant que XGBoost sur données bruitées et catégorielles.
Gère nativement les overfits.
"""

import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List

import joblib
import pandas as pd
import numpy as np

# Try import CatBoost (user needs to install it)
try:
    from catboost import CatBoostClassifier, Pool
    CATBOOST_AVAILABLE = True
except ImportError:
    CATBOOST_AVAILABLE = False

from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
)
from optimization.ml_pipeline import (
    prepare_training_dataset,
    split_training_dataset
)

logger = logging.getLogger(__name__)

class CatBoostTrainer:
    """
    Entraîneur CatBoost v1
    
    Avantages vs XGBoost:
    1. Meilleure gestion des features catégorielles (symbol, hour, day)
    2. Moins d'overfitting sur petits datasets
    3. Symmetric Trees (plus rapide en inférence)
    """
    
    def __init__(
        self,
        model_dir: str = "optimization/saved_models",
        model_name: str = "catboost_v1",
    ):
        self.model_dir = Path(model_dir)
        self.model_name = model_name
        self.model = None
        
        if not CATBOOST_AVAILABLE:
            logger.warning("⚠️ CatBoost non installé. `pip install catboost` requis.")
            
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
    def train(
        self,
        timeframe_days: int = 120,
        min_trades: int = 100,
        iterations: int = 1000,
        learning_rate: float = 0.03,
        depth: int = 6,
        l2_leaf_reg: float = 3.0,
        early_stopping_rounds: int = 50
    ) -> Dict:
        """
        Entraîner modèle CatBoost
        """
        if not CATBOOST_AVAILABLE:
            logger.warning("⚠️ CatBoost non disponible pour l'entraînement")
            return {'error': 'CatBoost library missing'}
            
        logger.info("🚀 Démarrage entraînement CatBoost")
        
        # 1. Préparation Data
        try:
            dataset = prepare_training_dataset(
                timeframe_days=timeframe_days,
                min_trades=min_trades,
                scaler_type=None # CatBoost n'a pas besoin de scaling!
            )
            
            # 🔥 FIX: Gestion des cas d'erreur de données
            if dataset is None:
                logger.error("❌ Aucun dataset retourné par prepare_training_dataset")
                return {
                    "success": False,
                    "error": "Aucune donnée disponible pour l'entraînement",
                    "train_samples": 0,
                    "test_samples": 0
                }
            
            X = dataset.X
            y = dataset.y
            
            if X is None or y is None or len(X) == 0 or len(y) == 0:
                logger.error("❌ Données X/y vides ou invalides")
                return {
                    "success": False,
                    "error": "Données d'entraînement invalides",
                    "train_samples": 0,
                    "test_samples": 0
                }
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de la préparation des données: {e}")
            return {
                "success": False,
                "error": f"Erreur préparation données: {str(e)}",
                "train_samples": 0,
                "test_samples": 0
            }
        
        # Identifier colonnes catégorielles
        # CatBoost adore les strings/catégories
        cat_features = []
        for col in X.columns:
            if X[col].dtype == 'object' or col in ['symbol', 'day_of_week', 'hour_block']:
                cat_features.append(col)
                # Convertir en string pour CatBoost
                X[col] = X[col].astype(str)
        
        # Split
        X_train, X_test, y_train, y_test = split_training_dataset(X, y)
        
        # Poids des classes (Balanced)
        # CatBoost a un paramètre auto_class_weights='Balanced'
        
        # 2. Configuration Modèle
        self.model = CatBoostClassifier(
            iterations=iterations,
            learning_rate=learning_rate,
            depth=depth,
            l2_leaf_reg=l2_leaf_reg,
            loss_function='Logloss',
            eval_metric='AUC',
            random_seed=42,
            verbose=100,
            auto_class_weights='Balanced',
            allow_writing_files=False
        )
        
        # 3. Entraînement
        train_pool = Pool(X_train, y_train, cat_features=cat_features)
        test_pool = Pool(X_test, y_test, cat_features=cat_features)
        
        self.model.fit(
            train_pool,
            eval_set=test_pool,
            early_stopping_rounds=early_stopping_rounds,
            use_best_model=True
        )
        
        # 4. Évaluation
        preds = self.model.predict(X_test)
        probas = self.model.predict_proba(X_test)[:, 1]
        
        metrics = {
            'accuracy': float(accuracy_score(y_test, preds)),
            'precision': float(precision_score(y_test, preds)),
            'recall': float(recall_score(y_test, preds)),
            'f1': float(f1_score(y_test, preds)),
            'auc': float(roc_auc_score(y_test, probas)),
            'model_type': 'CatBoost'
        }
        
        logger.info(f"✅ CatBoost terminé. AUC: {metrics['auc']:.4f} | F1: {metrics['f1']:.4f}")
        
        # 5. Sauvegarde
        model_path = self.model_dir / f"{self.model_name}.cbm"
        self.model.save_model(str(model_path))
        
        # Metadata
        metadata = {
            'training_date': datetime.now().isoformat(),
            'metrics': metrics,
            'params': self.model.get_params(),
            'feature_names': list(X.columns),
            'cat_features': cat_features
        }
        
        with open(self.model_dir / f"{self.model_name}_metadata.json", 'w') as f:
            json.dump(metadata, f, indent=4)
            
        return metrics
