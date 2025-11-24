"""
XGBoost Trainer V2 - Version améliorée avec split temporel et filtrage qualité

Améliorations vs V1:
1. Split temporel (pas random) - Évite data leakage
2. Filtrage trades marginaux (bruit)
3. Features top-K seulement (features discriminantes)
4. Walk-forward validation option
5. Analyse distribution temporelle win/loss
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

from optimization.data.feature_loader import load_features_from_postgres
from optimization.data.feature_engineering import calculate_derived_features
from optimization.data.preprocessor import FeaturePreprocessor
from optimization.utils.temporal_split import temporal_train_test_split

logger = logging.getLogger(__name__)


class XGBoostTrainerV2:
    """
    XGBoost Trainer V2 avec split temporel et filtrage qualité
    """

    def __init__(
        self,
        model_dir: str = "optimization/saved_models",
        model_name: str = "xgboost_v2",
    ):
        self.model_dir = Path(model_dir)
        self.model_name = model_name
        self.model: Optional[XGBClassifier] = None
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
        marginal_threshold: float = 0.15,  # Exclure |PNL| < 0.15%
        # Feature selection
        feature_selection: bool = True,
        max_features: int = 30,  # Top 30 features seulement
        # XGBoost params (meilleures valeurs)
        n_estimators: int = 500,
        max_depth: int = 5,
        learning_rate: float = 0.05,
        min_child_weight: int = 3,
        reg_alpha: float = 0.5,
        reg_lambda: float = 2.0,
        subsample: float = 0.8,
        colsample_bytree: float = 0.75,
        gamma: float = 0.3,
        early_stopping_rounds: int = 30,
        random_state: int = 42,
        **xgb_params,
    ) -> Dict:
        """
        Entraîner XGBoost avec split temporel et filtrage

        Args:
            filter_marginal_trades: Exclure trades avec faible PNL (bruit)
            marginal_threshold: Seuil PNL% pour filtrage
            ... (autres params)

        Returns:
            Dict avec métriques et diagnostic
        """
        logger.info("=" * 80)
        logger.info("🚀 XGBOOST TRAINER V2 - Temporal Split + Quality Filtering")
        logger.info("=" * 80)

        start_time = datetime.now()

        # 1. Charger données
        logger.info(f"📥 Chargement données (timeframe={timeframe_days}d, min_trades={min_trades})...")

        base_df = load_features_from_postgres(
            timeframe_days=timeframe_days,
            min_trades=min_trades
        )

        df = calculate_derived_features(base_df)

        logger.info(f"✅ {len(df)} trades chargés")

        # 2. Filtrer trades marginaux (bruit)
        if filter_marginal_trades and 'target_pnl' in df.columns:
            logger.info(f"\n🔍 Filtrage trades marginaux (|PNL| < {marginal_threshold}%)...")

            initial_count = len(df)
            df = df[abs(df['target_pnl']) >= marginal_threshold].copy()
            removed_count = initial_count - len(df)

            logger.info(f"✂️ {removed_count} trades marginaux exclus ({removed_count/initial_count*100:.1f}%)")
            logger.info(f"✅ {len(df)} trades de qualité restants")

        # 3. Split TEMPOREL (critique pour trading)
        logger.info(f"\n📅 Split TEMPOREL (train/val/test = {1-test_size-validation_size:.0%}/{validation_size:.0%}/{test_size:.0%})...")

        train_df, val_df, test_df = temporal_train_test_split(
            df,
            target_col='target_win',
            test_size=test_size,
            validation_size=validation_size,
            timestamp_col='timestamp'
        )

        # Séparer X, y
        exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 'is_opportunity']
        feature_cols = [col for col in train_df.columns if col not in exclude_cols]

        X_train = train_df[feature_cols].copy()
        y_train = train_df['target_win'].copy()

        X_val = val_df[feature_cols].copy()
        y_val = val_df['target_win'].copy()

        X_test = test_df[feature_cols].copy()
        y_test = test_df['target_win'].copy()

        # 4. Feature selection (top-K discriminantes)
        selected_features = None
        if feature_selection:
            logger.info(f"\n🔍 Sélection top {max_features} features discriminantes...")

            from sklearn.feature_selection import mutual_info_classif

            # Mutual information sur train set
            mi_scores = mutual_info_classif(
                X_train.fillna(0),
                y_train,
                random_state=random_state
            )

            # Trier et sélectionner top-K
            mi_df = pd.DataFrame({
                'feature': feature_cols,
                'mi_score': mi_scores
            }).sort_values('mi_score', ascending=False)

            selected_features = mi_df.head(max_features)['feature'].tolist()

            logger.info(f"✅ Top 10 features:")
            for i, row in mi_df.head(10).iterrows():
                logger.info(f"  {i+1}. {row['feature']}: {row['mi_score']:.4f}")

            # Filtrer datasets
            X_train = X_train[selected_features]
            X_val = X_val[selected_features]
            X_test = X_test[selected_features]

        # 5. Preprocessing
        logger.info("\n🔧 Preprocessing (imputation + scaling)...")

        preprocessor = FeaturePreprocessor(scaler_type='robust')
        X_train_scaled, _ = preprocessor.fit_transform(
            pd.concat([X_train, y_train.rename('target_win')], axis=1),
            target_col='target_win'
        )

        X_val_scaled = preprocessor.transform(X_val)
        X_test_scaled = preprocessor.transform(X_test)

        # 6. Class weights
        from optimization.data.preprocessor import handle_class_imbalance
        class_weights = handle_class_imbalance(y_train, strategy="balanced")
        scale_pos_weight = class_weights.get(1, 1.0) / class_weights.get(0, 1.0)

        logger.info(f"⚖️ Class weights: {class_weights} | scale_pos_weight={scale_pos_weight:.2f}")

        # 7. Entraîner modèle
        logger.info(f"\n🎯 Entraînement XGBoost...")

        model_params = {
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "learning_rate": learning_rate,
            "min_child_weight": min_child_weight,
            "reg_alpha": reg_alpha,
            "reg_lambda": reg_lambda,
            "subsample": subsample,
            "colsample_bytree": colsample_bytree,
            "gamma": gamma,
            "scale_pos_weight": scale_pos_weight,
            "random_state": random_state,
            "eval_metric": "logloss",
            "use_label_encoder": False,
            **xgb_params,
        }

        self.model = XGBClassifier(**model_params)

        # Early stopping sur validation set
        eval_set = [(X_train_scaled, y_train), (X_val_scaled, y_val)]

        self.model.fit(
            X_train_scaled,
            y_train,
            eval_set=eval_set,
            early_stopping_rounds=early_stopping_rounds,
            verbose=False
        )

        training_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"✅ Entraînement terminé en {training_time:.2f}s")

        # 8. Évaluation
        metrics = self._evaluate_model(
            X_train_scaled, X_val_scaled, X_test_scaled,
            y_train, y_val, y_test
        )

        # 9. Feature importance
        feature_importance = self._get_feature_importance(
            selected_features if selected_features else feature_cols
        )

        # 10. Sauvegarder
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
                "marginal_threshold": marginal_threshold,
                "split_type": "temporal",
                "selected_features": selected_features,
            },
            preprocessor=preprocessor
        )

        logger.info(f"\n💾 Modèle et metadata sauvegardés")
        
        # 11. Logger dans PostgreSQL
        try:
            from optimization.models.model_logger import log_model_to_db
            
            model_id = log_model_to_db(
                model_name=self.model_name,
                model_type="XGBClassifier_V2_Temporal",
                version="2.0",
                model_path=str(self.model_dir / f"{self.model_name}.pkl"),
                preprocessor_path=str(self.model_dir / f"{self.model_name}_preprocessor.pkl"),
                metrics=metrics,
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
                    "marginal_threshold": marginal_threshold,
                    "split_type": "temporal",
                    "max_features": len(selected_features) if selected_features else None,
                },
                model_params=model_params,
                feature_importance=feature_importance,
                is_active=False  # Ne pas activer automatiquement
            )
            
            if model_id:
                logger.info(f"✅ Modèle enregistré dans PostgreSQL (ID={model_id})")
        except Exception as e:
            logger.warning(f"⚠️ Impossible d'enregistrer dans PostgreSQL: {e}")
        
        logger.info("=" * 80)

        return {
            "status": "success",
            "model_name": self.model_name,
            "metrics": metrics,
            "feature_importance": feature_importance[:10],
            "training_info": self.metadata["training_info"],
        }

    def _evaluate_model(
        self,
        X_train: pd.DataFrame,
        X_val: pd.DataFrame,
        X_test: pd.DataFrame,
        y_train: pd.Series,
        y_val: pd.Series,
        y_test: pd.Series,
    ) -> Dict:
        """Évaluer sur train/val/test avec diagnostic temporel"""

        logger.info("\n📊 Évaluation modèle...")

        # Prédictions
        y_train_pred = self.model.predict(X_train)
        y_val_pred = self.model.predict(X_val)
        y_test_pred = self.model.predict(X_test)

        y_train_proba = self.model.predict_proba(X_train)[:, 1]
        y_val_proba = self.model.predict_proba(X_val)[:, 1]
        y_test_proba = self.model.predict_proba(X_test)[:, 1]

        # Métriques
        def compute_metrics(y_true, y_pred, y_proba):
            return {
                "accuracy": float(accuracy_score(y_true, y_pred)),
                "precision": float(precision_score(y_true, y_pred, zero_division=0)),
                "recall": float(recall_score(y_true, y_pred, zero_division=0)),
                "f1": float(f1_score(y_true, y_pred, zero_division=0)),
                "roc_auc": float(roc_auc_score(y_true, y_proba)),
            }

        train_metrics = compute_metrics(y_train, y_train_pred, y_train_proba)
        val_metrics = compute_metrics(y_val, y_val_pred, y_val_proba)
        test_metrics = compute_metrics(y_test, y_test_pred, y_test_proba)

        # Gaps (overfitting indicators)
        accuracy_gap = train_metrics['accuracy'] - test_metrics['accuracy']
        roc_gap = train_metrics['roc_auc'] - test_metrics['roc_auc']

        # Log résultats
        logger.info("\n" + "=" * 80)
        logger.info("RÉSULTATS (Temporal Split)")
        logger.info("=" * 80)

        logger.info(f"\n📈 TRAIN:      Accuracy={train_metrics['accuracy']:.3f} | ROC-AUC={train_metrics['roc_auc']:.3f}")
        logger.info(f"📈 VALIDATION: Accuracy={val_metrics['accuracy']:.3f} | ROC-AUC={val_metrics['roc_auc']:.3f}")
        logger.info(f"📈 TEST:       Accuracy={test_metrics['accuracy']:.3f} | ROC-AUC={test_metrics['roc_auc']:.3f}")

        logger.info(f"\n📊 GAPS:")
        logger.info(f"  - Accuracy Gap (train-test): {accuracy_gap:.3f}")
        logger.info(f"  - ROC-AUC Gap (train-test):  {roc_gap:.3f}")

        # Diagnostic
        if accuracy_gap > 0.15:
            logger.warning("⚠️ OVERFITTING: Gap > 15% - Augmenter régularisation")
        elif accuracy_gap < 0.05 and test_metrics['accuracy'] < 0.60:
            logger.warning("⚠️ UNDERFITTING: Gap < 5% et accuracy < 60%")
        elif test_metrics['accuracy'] >= 0.70:
            logger.info("🎉 EXCELLENT: Test accuracy >= 70% !")
        elif test_metrics['accuracy'] >= 0.65:
            logger.info("✅ BON: Test accuracy >= 65%")
        else:
            logger.warning("⚠️ PERFORMANCE FAIBLE: Test accuracy < 65%")

        # Confusion matrix
        cm = confusion_matrix(y_test, y_test_pred)
        logger.info(f"\n📋 Confusion Matrix (Test):")
        logger.info(f"  TN={cm[0][0]}, FP={cm[0][1]}")
        logger.info(f"  FN={cm[1][0]}, TP={cm[1][1]}")

        logger.info("=" * 80)

        return {
            "train": train_metrics,
            "validation": val_metrics,
            "test": test_metrics,
            "gaps": {
                "accuracy": float(accuracy_gap),
                "roc_auc": float(roc_gap),
            },
            "confusion_matrix": cm.tolist(),
        }

    def _get_feature_importance(self, feature_names: list) -> list:
        """Feature importance triée"""

        importance = self.model.feature_importances_

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
        """Sauvegarder modèle + preprocessor + metadata"""

        # Modèle
        model_path = self.model_dir / f"{self.model_name}.pkl"
        joblib.dump(self.model, model_path)

        # Preprocessor
        preprocessor_path = self.model_dir / f"{self.model_name}_preprocessor.pkl"
        preprocessor.save(str(preprocessor_path))

        # Metadata
        self.metadata = {
            "model_name": self.model_name,
            "model_type": "XGBClassifier_V2_Temporal",
            "model_path": str(model_path),
            "preprocessor_path": str(preprocessor_path),
            "model_params": model_params,
            "metrics": metrics,
            "feature_importance": feature_importance,
            "training_info": training_info,
            "version": "2.0",
        }

        metadata_path = self.model_dir / f"{self.model_name}_metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    trainer = XGBoostTrainerV2(model_name="xgboost_v2_temporal")

    results = trainer.train(
        timeframe_days=120,
        min_trades=100,
        filter_marginal_trades=True,
        marginal_threshold=0.15,
        max_features=30
    )

    print(f"\n✅ Test Accuracy: {results['metrics']['test']['accuracy']:.3f}")
    print(f"✅ Test ROC-AUC: {results['metrics']['test']['roc_auc']:.3f}")
