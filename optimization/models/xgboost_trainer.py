"""
XGBoost Trainer - Entraînement modèle baseline pour classification win/loss
"""
import logging
import os
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
from sklearn.base import BaseEstimator, TransformerMixin

logger = logging.getLogger(__name__)


class FeatureSelector(BaseEstimator, TransformerMixin):
    """Select specific features by name - used for feature selection in XGBoost"""
    
    def __init__(self, feature_names):
        self.feature_names = feature_names
    
    def fit(self, X, y=None):
        return self
    
    def transform(self, X):
        if isinstance(X, pd.DataFrame):
            return X[self.feature_names]
        return X


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
        timeframe_days: int = 120,
        min_trades: int = 100,  # 🔥 Augmenté: Plus de données pour meilleur apprentissage
        test_size: float = 0.2,
        n_estimators: Optional[int] = None,
        max_depth: Optional[int] = None,
        learning_rate: Optional[float] = None,
        early_stopping_rounds: int = 30,  # 🔥 Augmenté: Plus de patience avant arrêt
        random_state: int = 42,
        feature_selection: bool = True,
        max_features: int = 50,  # 🔥 Augmenté: Plus de features avec nouvelles discriminantes
        min_child_weight: Optional[int] = None,
        reg_alpha: Optional[float] = None,
        reg_lambda: Optional[float] = None,
        subsample: Optional[float] = None,
        colsample_bytree: Optional[float] = None,
        colsample_bylevel: Optional[float] = None,
        gamma: Optional[float] = None,
        scale_pos_weight: Optional[float] = None,
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
        
        # Charger hyperparamètres depuis TRADING_CONFIG si non fournis
        from config import TRADING_CONFIG
        n_estimators = n_estimators or TRADING_CONFIG.get('ml_n_estimators', 300)
        max_depth = max_depth or TRADING_CONFIG.get('ml_max_depth', 6)
        learning_rate = learning_rate or TRADING_CONFIG.get('ml_learning_rate', 0.03)
        min_child_weight = min_child_weight or TRADING_CONFIG.get('ml_min_child_weight', 3)
        reg_alpha = reg_alpha or TRADING_CONFIG.get('ml_reg_alpha', 0.5)
        reg_lambda = reg_lambda or TRADING_CONFIG.get('ml_reg_lambda', 2.0)
        subsample = subsample or TRADING_CONFIG.get('ml_subsample', 0.8)
        colsample_bytree = colsample_bytree or TRADING_CONFIG.get('ml_colsample_bytree', 0.8)
        colsample_bylevel = colsample_bylevel or TRADING_CONFIG.get('ml_colsample_bylevel', 0.8)
        gamma = gamma or TRADING_CONFIG.get('ml_gamma', 0.1)
        scale_pos_weight = scale_pos_weight or TRADING_CONFIG.get('ml_scale_pos_weight', 1.0)
        
        logger.info(
            f"🎯 Hyperparamètres ML: n_estimators={n_estimators}, max_depth={max_depth}, "
            f"lr={learning_rate:.4f}, min_child_weight={min_child_weight}, "
            f"reg_alpha={reg_alpha}, reg_lambda={reg_lambda}"
        )
        
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
        
        win_pct_train = (y_train == 1).mean() * 100
        win_pct_test = (y_test == 1).mean() * 100
        logger.info(
            "✂️ Split: %s train / %s test | Win%% train=%.1f%% | Win%% test=%.1f%%",
            len(X_train),
            len(X_test),
            win_pct_train,
            win_pct_test
        )
        logger.info(
            "📊 Distribution y_train: %s",
            y_train.value_counts().to_dict()
        )
        logger.info(
            "📊 Distribution y_test: %s",
            y_test.value_counts().to_dict()
        )
        
        # 3. Calculer class weights
        class_weights = compute_class_weights(y_train, strategy="balanced")
        scale_pos_weight = class_weights.get(1, 1.0) / class_weights.get(0, 1.0)
        logger.info("⚖️ Class weights: %s | scale_pos_weight=%.2f", class_weights, scale_pos_weight)

        # 4. Configurer modèle avec hyperparamètres optimisés et régularisation
        model_params = {
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "learning_rate": learning_rate,
            "early_stopping_rounds": early_stopping_rounds,
            "min_child_weight": min_child_weight,  # Anti-overfitting
            "reg_alpha": reg_alpha,  # Régularisation L1 (Lasso)
            "reg_lambda": reg_lambda,  # Régularisation L2 (Ridge)
            "subsample": subsample,  # Bagging
            "colsample_bytree": colsample_bytree,  # Feature sampling per tree
            "colsample_bylevel": colsample_bylevel,  # Feature sampling per level
            "gamma": gamma,  # Régularisation min split gain
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
            initial_model_params = {
                key: value
                for key, value in model_params.items()
                if key != "early_stopping_rounds"
            }
            initial_model = XGBClassifier(**initial_model_params)
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
            
            # Re-fit preprocessor on selected features only
            from sklearn.preprocessing import RobustScaler
            from sklearn.impute import SimpleImputer
            
            # Create scaler and imputer for selected features
            imputer = SimpleImputer(strategy='median')
            scaler = RobustScaler()
            
            # Fit and transform
            X_train_imputed = imputer.fit_transform(X_train)
            X_train_scaled = scaler.fit_transform(X_train_imputed)
            
            X_test_imputed = imputer.transform(X_test)
            X_test_scaled = scaler.transform(X_test_imputed)
            
            # Convert back to DataFrame
            X_train = pd.DataFrame(X_train_scaled, columns=selected_features, index=X_train.index)
            X_test = pd.DataFrame(X_test_scaled, columns=selected_features, index=X_test.index)
            
            # Create a simple preprocessor wrapper for the pipeline
            from optimization.data.preprocessor import FeaturePreprocessor
            selected_preprocessor = FeaturePreprocessor(scaler_type="robust")
            selected_preprocessor.imputer = imputer
            selected_preprocessor.scaler = scaler
            selected_preprocessor.feature_names = selected_features
            selected_preprocessor.is_fitted = True
            
            # Create a wrapper preprocessor that filters features then scales
            from sklearn.pipeline import Pipeline
            
            # Create new pipeline with feature selection (FeatureSelector is at module level)
            feature_selector = FeatureSelector(selected_features)
            new_preprocessor = Pipeline([
                ('feature_selector', feature_selector),
                ('scaler', selected_preprocessor)
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
            verbose=False,
        )

        training_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"✅ Entraînement terminé en {training_time:.2f}s")

        # 6.5. Cross-validation pour validation de stabilité
        logger.info("🔄 Validation croisée (5-fold CV)...")
        from sklearn.model_selection import cross_val_score

        # Créer un modèle temporaire pour CV (même hyperparams)
        cv_model_params = {
            key: value
            for key, value in model_params.items()
            if key != "early_stopping_rounds"
        }
        cv_model = XGBClassifier(**cv_model_params)

        # Cross-validation sur données combinées (train + test)
        X_full = pd.concat([X_train, X_test])
        y_full = pd.concat([y_train, y_test])

        cv_n_jobs = 1 if os.getenv("PYTEST_CURRENT_TEST") else -1
        try:
            cv_scores_accuracy = cross_val_score(
                cv_model, X_full, y_full,
                cv=5, scoring='accuracy', n_jobs=cv_n_jobs
            )
            cv_scores_roc_auc = cross_val_score(
                cv_model, X_full, y_full,
                cv=5, scoring='roc_auc', n_jobs=cv_n_jobs
            )
        except Exception as exc:
            logger.warning(f"⚠️ Cross-validation skipped: {exc}")
            cv_scores_accuracy = None
            cv_scores_roc_auc = None

        if cv_scores_accuracy is not None and len(cv_scores_accuracy) > 0:
            logger.info(
                f"📊 CV Accuracy: {cv_scores_accuracy.mean():.3f} (+/- {cv_scores_accuracy.std() * 2:.3f})"
            )
            logger.info(
                f"📊 CV ROC-AUC: {cv_scores_roc_auc.mean():.3f} (+/- {cv_scores_roc_auc.std() * 2:.3f})"
            )
            cv_metrics = {
                'accuracy_mean': float(cv_scores_accuracy.mean()),
                'accuracy_std': float(cv_scores_accuracy.std()),
                'roc_auc_mean': float(cv_scores_roc_auc.mean()),
                'roc_auc_std': float(cv_scores_roc_auc.std()),
            }
        else:
            cv_metrics = {
                'accuracy_mean': None,
                'accuracy_std': None,
                'roc_auc_mean': None,
                'roc_auc_std': None,
            }

        # 7. Évaluer modèle
        metrics = self._evaluate_model(X_train, X_test, y_train, y_test)
        metrics['cross_validation'] = cv_metrics
        
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
                "feature_names": list(dataset.X.columns),  # Pour predictor
            },
        )
        
        if feature_importance:
            top_features = feature_importance[:10]
            logger.info(
                "📈 Top features (importance): %s",
                {item['feature']: round(item['importance'], 4) for item in top_features}
            )
            logger.info(
                "📈 Importance moyenne=%.4f | max=%.4f",
                np.mean([item['importance'] for item in feature_importance]),
                max([item['importance'] for item in feature_importance]) if feature_importance else 0.0
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
        
        # Calculer écart train-test (overfitting indicator)
        accuracy_gap = train_metrics['accuracy'] - test_metrics['accuracy']
        roc_auc_gap = train_metrics['roc_auc'] - test_metrics['roc_auc']

        logger.info(f"✅ Train Accuracy: {train_metrics['accuracy']:.3f}")
        logger.info(f"✅ Test Accuracy: {test_metrics['accuracy']:.3f}")
        logger.info(f"📊 Accuracy Gap (train-test): {accuracy_gap:.3f}")

        logger.info(f"✅ Train ROC-AUC: {train_metrics['roc_auc']:.3f}")
        logger.info(f"✅ Test ROC-AUC: {test_metrics['roc_auc']:.3f}")
        logger.info(f"📊 ROC-AUC Gap (train-test): {roc_auc_gap:.3f}")

        logger.info(f"✅ Test F1: {test_metrics['f1']:.3f}")
        logger.info(f"✅ Test Precision: {test_metrics['precision']:.3f}")
        logger.info(f"✅ Test Recall: {test_metrics['recall']:.3f}")

        # Alertes de diagnostic
        if accuracy_gap > 0.15:
            logger.warning("⚠️ OVERFITTING DÉTECTÉ: Gap train-test > 15% - Augmenter régularisation")
        elif accuracy_gap < 0.05 and test_metrics['accuracy'] < 0.60:
            logger.warning("⚠️ UNDERFITTING DÉTECTÉ: Gap < 5% et accuracy < 60% - Réduire régularisation")
        elif test_metrics['accuracy'] >= 0.70:
            logger.info("🎉 EXCELLENT: Test accuracy >= 70% - Objectif atteint!")
        elif test_metrics['accuracy'] >= 0.65:
            logger.info("✅ BON: Test accuracy >= 65% - Performance satisfaisante")

        return {
            "train": train_metrics,
            "test": test_metrics,
            "gaps": {
                "accuracy": float(accuracy_gap),
                "roc_auc": float(roc_auc_gap),
            },
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
    n_estimators: int = 50,  # Optimisé: 50 au lieu de 100
    max_depth: int = 2,  # Optimisé: 2 au lieu de 6
    learning_rate: float = 0.05,  # Optimisé: 0.05 au lieu de 0.1
):
    """Helper pour entraînement CLI avec paramètres optimisés"""

    trainer = XGBoostTrainer()

    results = trainer.train(
        timeframe_days=timeframe_days,
        min_trades=min_trades,
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
    )
    
    print("\n" + "=" * 70)
    print("🎯 ENTRAÎNEMENT XGBOOST TERMINÉ")
    print("=" * 70)

    print(f"\n📊 Métriques Test:")
    print(f"  - Accuracy:  {results['metrics']['test']['accuracy']:.3f}")
    print(f"  - Precision: {results['metrics']['test']['precision']:.3f}")
    print(f"  - Recall:    {results['metrics']['test']['recall']:.3f}")
    print(f"  - F1 Score:  {results['metrics']['test']['f1']:.3f}")
    print(f"  - ROC-AUC:   {results['metrics']['test']['roc_auc']:.3f}")

    if 'gaps' in results['metrics']:
        print(f"\n📈 Gaps Train-Test (Overfitting Indicators):")
        print(f"  - Accuracy Gap: {results['metrics']['gaps']['accuracy']:.3f}")
        print(f"  - ROC-AUC Gap:  {results['metrics']['gaps']['roc_auc']:.3f}")

    if 'cross_validation' in results['metrics']:
        cv = results['metrics']['cross_validation']
        print(f"\n🔄 Cross-Validation (5-fold):")
        print(f"  - Accuracy: {cv['accuracy_mean']:.3f} (+/- {cv['accuracy_std'] * 2:.3f})")
        print(f"  - ROC-AUC:  {cv['roc_auc_mean']:.3f} (+/- {cv['roc_auc_std'] * 2:.3f})")

    print(f"\n🔝 Top 10 Features:")
    for i, feat in enumerate(results['feature_importance'], 1):
        print(f"  {i}. {feat['feature']}: {feat['importance']:.4f}")

    print(f"\n💾 Modèle sauvegardé: {results['model_name']}")
    print("=" * 70 + "\n")
    
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
