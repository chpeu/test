"""
XGBoost Trainer - Entraînement modèle baseline pour classification win/loss
"""
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple

import joblib
import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
)

from optimization.ml_pipeline import (
    prepare_training_dataset,
    split_training_dataset,
    compute_class_weights,
)

logger = logging.getLogger(__name__)


class XGBoostTrainer:
    """
    Entraîneur XGBoost pour prédiction win/loss
    
    Features:
    - Train/test split stratifié
    - Class weights automatiques
    - Early stopping
    - Sauvegarde modèle + metadata
    - Métriques complètes
    """
    
    def __init__(
        self,
        model_dir: str = "optimization/saved_models",
        model_name: str = "xgboost_v1",
    ):
        self.model_dir = Path(model_dir)
        self.model_name = model_name
        self.model: Optional[XGBClassifier] = None
        self.metadata: Dict = {}
        
        # Créer dossier si nécessaire
        self.model_dir.mkdir(parents=True, exist_ok=True)
    
    def train(
        self,
        timeframe_days: int = 60,
        min_trades: int = 50,
        test_size: float = 0.2,
        n_estimators: int = 150,
        max_depth: int = 4,  # Reduced from 6 to reduce overfitting
        learning_rate: float = 0.05,  # Reduced for better generalization
        early_stopping_rounds: int = 15,
        random_state: int = 42,
        feature_selection: bool = True,
        max_features: int = 30,  # Keep only top 30 features
        **xgb_params,
    ) -> Dict:
        """
        Entraîner modèle XGBoost
        
        Args:
            timeframe_days: Fenêtre temporelle données
            min_trades: Minimum trades requis
            test_size: Proportion test set
            n_estimators: Nombre arbres
            max_depth: Profondeur max arbres
            learning_rate: Taux apprentissage
            early_stopping_rounds: Rounds avant arrêt si pas amélioration
            random_state: Seed reproductibilité
            **xgb_params: Paramètres XGBoost additionnels
            
        Returns:
            Dict avec métriques et infos entraînement
        """
        logger.info("🚀 Démarrage entraînement XGBoost")
        logger.info(f"📊 Paramètres: timeframe={timeframe_days}d, min_trades={min_trades}")
        
        start_time = datetime.now()
        
        # 1. Charger et préparer données
        logger.info("📥 Chargement et preprocessing des données...")
        dataset = prepare_training_dataset(
            timeframe_days=timeframe_days,
            min_trades=min_trades,
            scaler_type="robust",
            save_preprocessor=True,
            preprocessor_path=str(self.model_dir / f"{self.model_name}_preprocessor.pkl"),
        )
        
        # 2. Split train/test
        X_train, X_test, y_train, y_test = split_training_dataset(
            dataset.X,
            dataset.y,
            test_size=test_size,
            random_state=random_state,
            stratify=True,
        )
        
        logger.info(f"✂️ Split: {len(X_train)} train, {len(X_test)} test")
        
        # 3. Calculer class weights
        class_weights = compute_class_weights(y_train, strategy="balanced")
        scale_pos_weight = class_weights.get(1, 1.0) / class_weights.get(0, 1.0)
        
        # 4. Configurer modèle
        model_params = {
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "learning_rate": learning_rate,
            "scale_pos_weight": scale_pos_weight,
            "random_state": random_state,
            "eval_metric": "logloss",
            "use_label_encoder": False,
            **xgb_params,
        }
        
        self.model = XGBClassifier(**model_params)
        
        logger.info(f"🔧 Modèle configuré: {model_params}")
        
        # 5. Feature selection (si activé)
        selected_features = None
        if feature_selection:
            logger.info(f"🔍 Feature selection: training initial model to identify top {max_features} features...")
            
            # Train initial model to get feature importances
            initial_model = XGBClassifier(**model_params)
            initial_model.fit(X_train, y_train, verbose=False)
            
            # Get feature importances
            importances = initial_model.feature_importances_
            feature_names = dataset.X.columns
            
            # Select top N features
            indices = np.argsort(importances)[::-1][:max_features]
            selected_features = feature_names[indices].tolist()
            
            logger.info(f"✂️ Selected {len(selected_features)} features")
            logger.info(f"Top 5: {selected_features[:5]}")
            
            # Re-filter datasets with selected features
            X_train = X_train[selected_features]
            X_test = X_test[selected_features]
            
            # Create a wrapper preprocessor that filters features
            from sklearn.pipeline import Pipeline
            from sklearn.preprocessing import FunctionTransformer
            
            def select_features(X):
                """Select only the chosen features"""
                if isinstance(X, pd.DataFrame):
                    return X[selected_features]
                return X
            
            # Create new pipeline with feature selection
            feature_selector = FunctionTransformer(select_features, validate=False)
            new_preprocessor = Pipeline([
                ('feature_selector', feature_selector),
                ('scaler', dataset.preprocessor)
            ])
            
            # Save the new preprocessor
            joblib.dump(
                new_preprocessor,
                str(self.model_dir / f"{self.model_name}_preprocessor.pkl")
            )
            
            logger.info(f"💾 Preprocessor with feature selection saved")
        
        # 6. Entraîner avec early stopping (sur features sélectionnées)
        logger.info("🎯 Entraînement du modèle final...")
        
        eval_set = [(X_train, y_train), (X_test, y_test)]
        
        self.model.fit(
            X_train,
            y_train,
            eval_set=eval_set,
            early_stopping_rounds=early_stopping_rounds,
            verbose=False,
        )
        
        training_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"✅ Entraînement terminé en {training_time:.2f}s")
        
        # 7. Évaluer modèle
        metrics = self._evaluate_model(X_train, X_test, y_train, y_test)
        
        # 8. Feature importance
        if selected_features:
            feature_importance = self._get_feature_importance(selected_features)
        else:
            feature_importance = self._get_feature_importance(dataset.X.columns)
        
        # 8. Sauvegarder modèle et metadata
        self._save_model_and_metadata(
            model_params=model_params,
            metrics=metrics,
            feature_importance=feature_importance,
            training_info={
                "timeframe_days": timeframe_days,
                "min_trades": min_trades,
                "total_samples": len(dataset.X),
                "train_samples": len(X_train),
                "test_samples": len(X_test),
                "training_time_seconds": training_time,
                "trained_at": start_time.isoformat(),
            },
        )
        
        logger.info("💾 Modèle et metadata sauvegardés")
        
        return {
            "status": "success",
            "model_name": self.model_name,
            "metrics": metrics,
            "feature_importance": feature_importance[:10],  # Top 10
            "training_info": self.metadata["training_info"],
        }
    
    def _evaluate_model(
        self,
        X_train: pd.DataFrame,
        X_test: pd.DataFrame,
        y_train: pd.Series,
        y_test: pd.Series,
    ) -> Dict:
        """Calculer métriques complètes"""
        
        logger.info("📊 Évaluation du modèle...")
        
        # Prédictions
        y_train_pred = self.model.predict(X_train)
        y_test_pred = self.model.predict(X_test)
        
        y_train_proba = self.model.predict_proba(X_train)[:, 1]
        y_test_proba = self.model.predict_proba(X_test)[:, 1]
        
        # Métriques train
        train_metrics = {
            "accuracy": float(accuracy_score(y_train, y_train_pred)),
            "precision": float(precision_score(y_train, y_train_pred, zero_division=0)),
            "recall": float(recall_score(y_train, y_train_pred, zero_division=0)),
            "f1": float(f1_score(y_train, y_train_pred, zero_division=0)),
            "roc_auc": float(roc_auc_score(y_train, y_train_proba)),
        }
        
        # Métriques test
        test_metrics = {
            "accuracy": float(accuracy_score(y_test, y_test_pred)),
            "precision": float(precision_score(y_test, y_test_pred, zero_division=0)),
            "recall": float(recall_score(y_test, y_test_pred, zero_division=0)),
            "f1": float(f1_score(y_test, y_test_pred, zero_division=0)),
            "roc_auc": float(roc_auc_score(y_test, y_test_proba)),
        }
        
        # Confusion matrix
        cm = confusion_matrix(y_test, y_test_pred)
        
        # Classification report
        report = classification_report(y_test, y_test_pred, output_dict=True)
        
        logger.info(f"✅ Test Accuracy: {test_metrics['accuracy']:.3f}")
        logger.info(f"✅ Test F1: {test_metrics['f1']:.3f}")
        logger.info(f"✅ Test ROC-AUC: {test_metrics['roc_auc']:.3f}")
        
        return {
            "train": train_metrics,
            "test": test_metrics,
            "confusion_matrix": cm.tolist(),
            "classification_report": report,
        }
    
    def _get_feature_importance(self, feature_names: pd.Index) -> list:
        """Extraire feature importance triée"""
        
        importance = self.model.feature_importances_
        
        feature_importance = [
            {"feature": name, "importance": float(imp)}
            for name, imp in zip(feature_names, importance)
        ]
        
        # Trier par importance décroissante
        feature_importance.sort(key=lambda x: x["importance"], reverse=True)
        
        logger.info(f"🔝 Top 5 features: {[f['feature'] for f in feature_importance[:5]]}")
        
        return feature_importance
    
    def _save_model_and_metadata(
        self,
        model_params: Dict,
        metrics: Dict,
        feature_importance: list,
        training_info: Dict,
    ):
        """Sauvegarder modèle + fichier metadata JSON"""
        
        # Sauvegarder modèle
        model_path = self.model_dir / f"{self.model_name}.pkl"
        joblib.dump(self.model, model_path)
        logger.info(f"💾 Modèle sauvegardé: {model_path}")
        
        # Metadata
        self.metadata = {
            "model_name": self.model_name,
            "model_type": "XGBClassifier",
            "model_path": str(model_path),
            "preprocessor_path": str(self.model_dir / f"{self.model_name}_preprocessor.pkl"),
            "model_params": model_params,
            "metrics": metrics,
            "feature_importance": feature_importance,
            "training_info": training_info,
            "version": "1.0",
        }
        
        # Sauvegarder metadata JSON
        metadata_path = self.model_dir / f"{self.model_name}_metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 Metadata sauvegardée: {metadata_path}")
    
    @classmethod
    def load_model(cls, model_dir: str = "optimization/saved_models", model_name: str = "xgboost_v1"):
        """Charger modèle + metadata existant"""
        
        model_path = Path(model_dir) / f"{model_name}.pkl"
        metadata_path = Path(model_dir) / f"{model_name}_metadata.json"
        
        if not model_path.exists():
            raise FileNotFoundError(f"Modèle introuvable: {model_path}")
        
        trainer = cls(model_dir=model_dir, model_name=model_name)
        trainer.model = joblib.load(model_path)
        
        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                trainer.metadata = json.load(f)
        
        logger.info(f"📂 Modèle chargé: {model_path}")
        
        return trainer
    
    def predict(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prédire win/loss + probabilités
        
        Args:
            X: Features (déjà preprocessées)
            
        Returns:
            (predictions, probabilities)
        """
        if self.model is None:
            raise ValueError("Modèle non entraîné. Appelez train() ou load_model() d'abord.")
        
        predictions = self.model.predict(X)
        probabilities = self.model.predict_proba(X)[:, 1]
        
        return predictions, probabilities


# ========== CLI HELPER ==========

def train_xgboost_cli(
    timeframe_days: int = 60,
    min_trades: int = 50,
    n_estimators: int = 100,
    max_depth: int = 6,
    learning_rate: float = 0.1,
):
    """Helper pour entraînement CLI"""
    
    trainer = XGBoostTrainer()
    
    results = trainer.train(
        timeframe_days=timeframe_days,
        min_trades=min_trades,
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
    )
    
    print("\n" + "=" * 60)
    print("🎯 ENTRAÎNEMENT XGBOOST TERMINÉ")
    print("=" * 60)
    print(f"\n📊 Métriques Test:")
    print(f"  - Accuracy:  {results['metrics']['test']['accuracy']:.3f}")
    print(f"  - Precision: {results['metrics']['test']['precision']:.3f}")
    print(f"  - Recall:    {results['metrics']['test']['recall']:.3f}")
    print(f"  - F1 Score:  {results['metrics']['test']['f1']:.3f}")
    print(f"  - ROC-AUC:   {results['metrics']['test']['roc_auc']:.3f}")
    
    print(f"\n🔝 Top 10 Features:")
    for i, feat in enumerate(results['feature_importance'], 1):
        print(f"  {i}. {feat['feature']}: {feat['importance']:.4f}")
    
    print(f"\n💾 Modèle sauvegardé: {results['model_name']}")
    print("=" * 60 + "\n")
    
    return results


if __name__ == "__main__":
    # Test rapide
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    # Parse args basiques
    timeframe = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    min_trades = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    
    train_xgboost_cli(timeframe_days=timeframe, min_trades=min_trades)
