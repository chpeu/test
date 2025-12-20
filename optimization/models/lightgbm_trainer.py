"""
LightGBM Trainer - Version alignée avec XGBoost V2.1 (Temporal Split, Quality Filtering)

Caractéristiques:
1. Split temporel pour éviter data leakage
2. Filtrage des trades marginaux (bruit)
3. Support natif des catégories
4. Calibration des probabilités
5. Intégration Optuna
"""
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple, List, Union

import joblib
import pandas as pd
import numpy as np
import lightgbm as lgb
from lightgbm import LGBMClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    brier_score_loss,
)
from sklearn.calibration import CalibratedClassifierCV

from optimization.data.feature_loader import load_features_from_postgres
from optimization.data.feature_engineering import calculate_derived_features
from optimization.data.preprocessor import FeaturePreprocessor
from optimization.utils.temporal_split import temporal_train_test_split

logger = logging.getLogger(__name__)


class LightGBMTrainer:
    """
    LightGBM Trainer avec split temporel et filtrage qualité
    """

    def __init__(
        self,
        model_dir: str = "optimization/saved_models",
        model_name: str = "lightgbm_v1",
    ):
        self.model_dir = Path(model_dir)
        self.model_name = model_name
        self.model: Optional[LGBMClassifier] = None
        self.calibrated_model: Optional[CalibratedClassifierCV] = None
        self.metadata: Dict = {}
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def train(
        self,
        timeframe_days: int = 120,
        min_trades: int = 100,
        test_size: float = 0.2,
        validation_size: float = 0.1,
        # Filtrage qualité
        filter_marginal_trades: bool = True,
        marginal_threshold: float = 0.15,
        # Feature selection
        feature_selection: bool = True,
        max_features: int = 30,
        # Validation
        walk_forward: bool = False,
        walk_forward_splits: int = 5,
        # Calibration
        calibrate_probabilities: bool = True,
        # Optuna
        load_optuna_params: bool = True,
        # LGBM params (défauts)
        n_estimators: int = 500,
        max_depth: int = -1,  # -1 = no limit
        learning_rate: float = 0.05,
        num_leaves: int = 31,
        min_child_samples: int = 20,
        reg_alpha: float = 0.0,
        reg_lambda: float = 0.0,
        subsample: float = 1.0,
        colsample_bytree: float = 1.0,
        random_state: int = 42,
        **lgbm_params,
    ) -> Dict:
        """
        Entraîner LightGBM avec split temporel et filtrage
        """
        logger.info("=" * 80)
        logger.info("🚀 LIGHTGBM TRAINER - Temporal Split + Quality Filtering")
        logger.info("=" * 80)

        start_time = datetime.now()
        
        # 1. Charger hyperparamètres
        if load_optuna_params:
            optuna_params = self._load_optuna_params()
            if optuna_params:
                logger.info(f"🎯 Hyperparamètres Optuna chargés: {len(optuna_params)} params")
                n_estimators = optuna_params.get('n_estimators', n_estimators)
                max_depth = optuna_params.get('max_depth', max_depth)
                learning_rate = optuna_params.get('learning_rate', learning_rate)
                num_leaves = optuna_params.get('num_leaves', num_leaves)
                min_child_samples = optuna_params.get('min_child_samples', min_child_samples)
                reg_alpha = optuna_params.get('reg_alpha', reg_alpha)
                reg_lambda = optuna_params.get('reg_lambda', reg_lambda)
                subsample = optuna_params.get('subsample', subsample)
                colsample_bytree = optuna_params.get('colsample_bytree', colsample_bytree)
                
                # Autres params
                lgbm_params.update({
                    k: v for k, v in optuna_params.items() 
                    if k not in ['n_estimators', 'max_depth', 'learning_rate', 
                                 'num_leaves', 'min_child_samples', 'reg_alpha', 
                                 'reg_lambda', 'subsample', 'colsample_bytree']
                })

        # 2. Charger données
        logger.info(f"📥 Chargement données (timeframe={timeframe_days}d, min_trades={min_trades})...")
        base_df = load_features_from_postgres(
            timeframe_days=timeframe_days,
            min_trades=min_trades
        )
        df = calculate_derived_features(base_df)
        logger.info(f"✅ {len(df)} trades chargés")

        # 3. Filtrer trades marginaux
        if filter_marginal_trades and 'target_pnl' in df.columns:
            logger.info(f"\n🔍 Filtrage trades marginaux (|PNL| < {marginal_threshold}%)...")
            initial_count = len(df)
            df = df[abs(df['target_pnl']) >= marginal_threshold].copy()
            removed_count = initial_count - len(df)
            logger.info(f"✂️ {removed_count} trades marginaux exclus ({removed_count/initial_count*100:.1f}%)")

        # 4. Split TEMPOREL
        logger.info(f"\n📅 Split TEMPOREL (train/val/test = {1-test_size-validation_size:.0%}/{validation_size:.0%}/{test_size:.0%})...")
        train_df, val_df, test_df = temporal_train_test_split(
            df,
            target_col='target_win',
            test_size=test_size,
            validation_size=validation_size,
            timestamp_col='timestamp'
        )

        exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 'is_opportunity']
        feature_cols = [col for col in train_df.columns if col not in exclude_cols]

        X_train = train_df[feature_cols].copy()
        y_train = train_df['target_win'].copy()
        X_val = val_df[feature_cols].copy()
        y_val = val_df['target_win'].copy()
        X_test = test_df[feature_cols].copy()
        y_test = test_df['target_win'].copy()

        # 5. Feature selection
        selected_features = None
        if feature_selection:
            logger.info(f"\n🔍 Sélection top {max_features} features discriminantes...")
            from sklearn.feature_selection import mutual_info_classif
            mi_scores = mutual_info_classif(
                X_train.fillna(0),
                y_train,
                random_state=random_state
            )
            mi_df = pd.DataFrame({
                'feature': feature_cols,
                'mi_score': mi_scores
            }).sort_values('mi_score', ascending=False)
            selected_features = mi_df.head(max_features)['feature'].tolist()
            
            X_train = X_train[selected_features]
            X_val = X_val[selected_features]
            X_test = X_test[selected_features]
            logger.info(f"✅ {max_features} features sélectionnées")

        # 6. Preprocessing
        logger.info("\n🔧 Preprocessing (imputation + scaling)...")
        preprocessor = FeaturePreprocessor(scaler_type='robust')
        X_train_scaled, _ = preprocessor.fit_transform(
            pd.concat([X_train, y_train.rename('target_win')], axis=1),
            target_col='target_win'
        )
        X_val_scaled = preprocessor.transform(X_val)
        X_test_scaled = preprocessor.transform(X_test)

        # 7. Class weights
        from optimization.data.preprocessor import handle_class_imbalance
        class_weights = handle_class_imbalance(y_train, strategy="balanced")
        scale_pos_weight = class_weights.get(1, 1.0) / class_weights.get(0, 1.0)
        logger.info(f"⚖️ Scale pos weight: {scale_pos_weight:.2f}")

        # 8. Entraînement
        logger.info(f"\n🎯 Entraînement LightGBM...")
        
        model_params = {
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "learning_rate": learning_rate,
            "num_leaves": num_leaves,
            "min_child_samples": min_child_samples,
            "reg_alpha": reg_alpha,
            "reg_lambda": reg_lambda,
            "subsample": subsample,
            "colsample_bytree": colsample_bytree,
            "scale_pos_weight": scale_pos_weight,
            "random_state": random_state,
            "objective": "binary",
            "metric": "binary_logloss",
            "verbose": -1,
            **lgbm_params,
        }

        self.model = LGBMClassifier(**model_params)
        
        callbacks = [
            lgb.early_stopping(stopping_rounds=30, verbose=False),
            lgb.log_evaluation(period=0)  # Silence logging
        ]

        self.model.fit(
            X_train_scaled,
            y_train,
            eval_set=[(X_val_scaled, y_val)],
            callbacks=callbacks
        )

        # Walk-forward
        walk_forward_results = None
        if walk_forward:
            walk_forward_results = self._walk_forward_validation(
                df, feature_cols if not feature_selection else selected_features,
                walk_forward_splits, model_params
            )

        # Calibration
        if calibrate_probabilities:
            logger.info("\n🎯 Calibration des probabilités (isotonic)...")
            try:
                self.calibrated_model = CalibratedClassifierCV(
                    self.model, method='isotonic', cv='prefit'
                )
                self.calibrated_model.fit(X_val_scaled, y_val)
                logger.info("✅ Modèle calibré")
            except Exception as e:
                logger.warning(f"⚠️ Calibration échouée: {e}")

        training_time = (datetime.now() - start_time).total_seconds()

        # 9. Évaluation
        metrics = self._evaluate_model(
            X_train_scaled, X_val_scaled, X_test_scaled,
            y_train, y_val, y_test
        )

        # 10. Feature Importance
        feature_importance = self._get_feature_importance(
            selected_features if selected_features else feature_cols
        )

        # 11. Sauvegarde
        self._save_model_and_metadata(
            model_params=model_params,
            metrics=metrics,
            feature_importance=feature_importance,
            training_info={
                "timeframe_days": timeframe_days,
                "min_trades": min_trades,
                "total_samples": len(df),
                "train_samples": len(X_train),
                "val_samples": len(X_val),
                "test_samples": len(X_test),
                "training_time_seconds": training_time,
                "trained_at": start_time.isoformat(),
                "filter_marginal_trades": filter_marginal_trades,
                "selected_features": selected_features,
            },
            preprocessor=preprocessor
        )

        # 12. Log PostgreSQL
        try:
            from optimization.models.model_logger import log_model_to_db
            model_id = log_model_to_db(
                model_name=self.model_name,
                model_type="LightGBM_Temporal",
                version="1.0",
                model_path=str(self.model_dir / f"{self.model_name}.pkl"),
                preprocessor_path=str(self.model_dir / f"{self.model_name}_preprocessor.pkl"),
                metrics=metrics,
                training_info=self.metadata["training_info"],
                model_params=model_params,
                feature_importance=feature_importance,
                is_active=False
            )
            if model_id:
                logger.info(f"✅ Modèle enregistré dans PostgreSQL (ID={model_id})")
        except Exception as e:
            logger.warning(f"⚠️ Erreur log DB: {e}")

        return {
            "status": "success",
            "model_name": self.model_name,
            "metrics": metrics,
            "feature_importance": feature_importance[:10],
        }

    def _evaluate_model(
        self,
        X_train, X_val, X_test,
        y_train, y_val, y_test
    ) -> Dict:
        """Évaluer sur train/val/test"""
        
        def compute_metrics(y_true, y_pred, y_proba):
            return {
                "accuracy": float(accuracy_score(y_true, y_pred)),
                "precision": float(precision_score(y_true, y_pred, zero_division=0)),
                "recall": float(recall_score(y_true, y_pred, zero_division=0)),
                "f1": float(f1_score(y_true, y_pred, zero_division=0)),
                "roc_auc": float(roc_auc_score(y_true, y_proba)),
                "brier": float(brier_score_loss(y_true, y_proba))
            }

        # Predict
        model = self.calibrated_model if self.calibrated_model else self.model
        
        train_metrics = compute_metrics(y_train, model.predict(X_train), model.predict_proba(X_train)[:, 1])
        val_metrics = compute_metrics(y_val, model.predict(X_val), model.predict_proba(X_val)[:, 1])
        test_metrics = compute_metrics(y_test, model.predict(X_test), model.predict_proba(X_test)[:, 1])
        
        logger.info(f"\n📈 TEST: Accuracy={test_metrics['accuracy']:.3f} | ROC-AUC={test_metrics['roc_auc']:.3f} | F1={test_metrics['f1']:.3f}")
        
        return {
            "train": train_metrics,
            "validation": val_metrics,
            "test": test_metrics,
            "gaps": {
                "accuracy": train_metrics['accuracy'] - test_metrics['accuracy'],
                "roc_auc": train_metrics['roc_auc'] - test_metrics['roc_auc']
            }
        }

    def _get_feature_importance(self, feature_names: list) -> list:
        """Feature importance"""
        if not self.model:
            return []
            
        importance = self.model.feature_importances_
        # Normalize
        importance = importance / importance.sum()
        
        feature_importance = [
            {"feature": name, "importance": float(imp)}
            for name, imp in zip(feature_names, importance)
        ]
        feature_importance.sort(key=lambda x: x["importance"], reverse=True)
        return feature_importance

    def _save_model_and_metadata(
        self,
        model_params: Dict,
        metrics: Dict,
        feature_importance: list,
        training_info: Dict,
        preprocessor: FeaturePreprocessor
    ):
        """Sauvegarder modèle et artifacts"""
        # Save model
        model_path = self.model_dir / f"{self.model_name}.pkl"
        joblib.dump(self.model, model_path)
        
        # Save calibrated if exists
        if self.calibrated_model:
            joblib.dump(self.calibrated_model, self.model_dir / f"{self.model_name}_calibrated.pkl")

        # Save preprocessor
        preprocessor_path = self.model_dir / f"{self.model_name}_preprocessor.pkl"
        preprocessor.save(str(preprocessor_path))

        # Metadata
        self.metadata = {
            "model_name": self.model_name,
            "model_type": "LightGBM_Temporal",
            "version": "1.0",
            "model_params": model_params,
            "metrics": metrics,
            "feature_importance": feature_importance,
            "training_info": training_info,
            "paths": {
                "model": str(model_path),
                "preprocessor": str(preprocessor_path)
            }
        }
        
        with open(self.model_dir / f"{self.model_name}_metadata.json", "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)

    def _load_optuna_params(self) -> Optional[Dict]:
        """Charger params optimisés"""
        # Tenter de charger depuis config_overrides.json (ml_lgbm_*)
        try:
            config_path = Path("config_overrides.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                lgbm_params = {}
                for key, value in config.items():
                    if key.startswith('ml_lgbm_'):
                        lgbm_params[key[8:]] = value
                
                if lgbm_params:
                    return lgbm_params
        except Exception:
            pass
        return None

    def _walk_forward_validation(self, df, feature_cols, n_splits, model_params):
        """Placeholder pour walk-forward (similaire à XGBoost)"""
        # Implémentation simplifiée pour le moment
        return {"mean_score": 0.0, "std_score": 0.0}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    trainer = LightGBMTrainer()
    trainer.train(timeframe_days=120)
