"""
XGBoost V2 Enhanced - Version Ultime
Toutes les optimisations pour maximiser accuracy/ROC-AUC sans overfitting

Optimisations incluses :
1. Features avancées (contexte + historique + interactions)
2. Temporal split + filtrage marginal trades
3. Feature selection dynamique (top-K discriminants)
4. Calibration isotonic des probabilités
5. Ensembling léger (XGBoost + LightGBM)
6. Early stopping intelligent
7. Monitoring overfitting en temps réel
"""
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple

import joblib
import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from sklearn.ensemble import VotingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    log_loss,
    brier_score_loss
)

from optimization.data.feature_loader import load_features_from_postgres
from optimization.data.feature_engineering_advanced import calculate_all_advanced_features
from optimization.data.preprocessor import FeaturePreprocessor, handle_class_imbalance
from optimization.utils.temporal_split import temporal_train_test_split

logger = logging.getLogger(__name__)


def train_xgboost_enhanced(
    timeframe_days: int = 120,
    min_trades: int = 100,
    # Filtrage qualité
    filter_marginal_trades: bool = True,
    marginal_threshold: float = 0.15,
    # Splits
    test_size: float = 0.2,
    validation_size: float = 0.1,
    # Feature selection
    max_features: int = 40,  # Top 40 features (on a + de features maintenant)
    # Ensembling
    use_ensemble: bool = True,
    # Calibration
    calibrate_proba: bool = True,
    # XGBoost hyperparams (optimisés Phase 1)
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
) -> Dict:
    """
    Entraînement XGBoost V2 Enhanced avec toutes les optimisations

    Returns:
        Dict avec modèle, métriques, et diagnostics
    """
    logger.info("=" * 90)
    logger.info("🚀 XGBOOST V2 ENHANCED - Version Ultime (Toutes Optimisations)")
    logger.info("=" * 90)

    start_time = datetime.now()

    # ====================
    # 1. CHARGEMENT DONNÉES
    # ====================
    logger.info(f"\n📥 Chargement données (timeframe={timeframe_days}d, min_trades={min_trades})...")

    base_df = load_features_from_postgres(
        timeframe_days=timeframe_days,
        min_trades=min_trades
    )

    logger.info(f"✅ {len(base_df)} trades bruts chargés")

    # ====================
    # 2. FEATURE ENGINEERING AVANCÉ
    # ====================
    logger.info("\n🔧 Feature engineering avancé (contexte + historique + interactions)...")

    df = calculate_all_advanced_features(base_df)

    logger.info(f"✅ {len(df.columns)} features totales après engineering")

    # ====================
    # 3. FILTRAGE QUALITÉ
    # ====================
    if filter_marginal_trades and 'target_pnl' in df.columns:
        logger.info(f"\n🔍 Filtrage trades marginaux (|PNL| < {marginal_threshold}%)...")

        initial_count = len(df)
        df = df[abs(df['target_pnl']) >= marginal_threshold].copy()
        removed_count = initial_count - len(df)

        logger.info(f"✂️ {removed_count} trades marginaux exclus ({removed_count/initial_count*100:.1f}%)")
        logger.info(f"✅ {len(df)} trades de qualité restants")

    # ====================
    # 4. TEMPORAL SPLIT
    # ====================
    logger.info(f"\n📅 Split TEMPOREL (évite data leakage)...")

    train_df, val_df, test_df = temporal_train_test_split(
        df,
        target_col='target_win',
        test_size=test_size,
        validation_size=validation_size,
        timestamp_col='timestamp'
    )

    # Séparer X, y
    exclude_cols = [
        'scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 'is_opportunity',
        'opportunity_direction'  # Si existe
    ]
    feature_cols = [col for col in train_df.columns if col not in exclude_cols]

    X_train = train_df[feature_cols].copy()
    y_train = train_df['target_win'].copy()

    X_val = val_df[feature_cols].copy()
    y_val = val_df['target_win'].copy()

    X_test = test_df[feature_cols].copy()
    y_test = test_df['target_win'].copy()

    logger.info(f"✅ Train={len(X_train)}, Val={len(X_val)}, Test={len(X_test)}")

    # ====================
    # 5. FEATURE SELECTION DYNAMIQUE
    # ====================
    logger.info(f"\n🔍 Sélection top {max_features} features discriminantes (Mutual Information)...")

    from sklearn.feature_selection import mutual_info_classif

    # Imputer NaN pour MI calculation
    X_train_filled = X_train.fillna(X_train.median())

    mi_scores = mutual_info_classif(
        X_train_filled,
        y_train,
        random_state=random_state
    )

    mi_df = pd.DataFrame({
        'feature': feature_cols,
        'mi_score': mi_scores
    }).sort_values('mi_score', ascending=False)

    selected_features = mi_df.head(max_features)['feature'].tolist()

    logger.info(f"🔝 Top 10 features discriminantes:")
    for i, row in mi_df.head(10).iterrows():
        logger.info(f"  {i+1}. {row['feature']}: {row['mi_score']:.4f}")

    # Filtrer datasets
    X_train = X_train[selected_features]
    X_val = X_val[selected_features]
    X_test = X_test[selected_features]

    # ====================
    # 6. PREPROCESSING
    # ====================
    logger.info("\n🔧 Preprocessing (imputation + RobustScaler)...")

    preprocessor = FeaturePreprocessor(scaler_type='robust')
    X_train_scaled, _ = preprocessor.fit_transform(
        pd.concat([X_train, y_train.rename('target_win')], axis=1),
        target_col='target_win'
    )

    X_val_scaled = preprocessor.transform(X_val)
    X_test_scaled = preprocessor.transform(X_test)

    logger.info(f"✅ Preprocessing terminé: {X_train_scaled.shape[1]} features")

    # ====================
    # 7. CLASS WEIGHTS
    # ====================
    class_weights = handle_class_imbalance(y_train, strategy="balanced")
    scale_pos_weight = class_weights.get(1, 1.0) / class_weights.get(0, 1.0)

    logger.info(f"⚖️ scale_pos_weight={scale_pos_weight:.2f}")

    # ====================
    # 8. ENTRAÎNEMENT MODÈLE(S)
    # ====================
    logger.info(f"\n🎯 Entraînement {'Ensemble (XGBoost + LightGBM)' if use_ensemble else 'XGBoost'}...")

    # XGBoost params
    xgb_params = {
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
    }

    xgb_model = XGBClassifier(**xgb_params)

    if use_ensemble:
        # LightGBM params (similaires mais adaptés)
        lgbm_params = {
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "learning_rate": learning_rate,
            "min_child_weight": min_child_weight,
            "reg_alpha": reg_alpha,
            "reg_lambda": reg_lambda,
            "subsample": subsample,
            "colsample_bytree": colsample_bytree,
            "scale_pos_weight": scale_pos_weight,
            "random_state": random_state,
            "verbose": -1
        }

        lgbm_model = LGBMClassifier(**lgbm_params)

        # Voting ensemble (soft = moyenne probabilités)
        model = VotingClassifier(
            estimators=[
                ('xgb', xgb_model),
                ('lgbm', lgbm_model)
            ],
            voting='soft'
        )

        logger.info("📦 Ensemble XGBoost + LightGBM créé")
    else:
        model = xgb_model
        logger.info("📦 XGBoost seul")

    # Early stopping (sur validation)
    if hasattr(model, 'fit') and use_ensemble:
        # Voting ne supporte pas eval_set, on fit directement
        model.fit(X_train_scaled, y_train)
    else:
        eval_set = [(X_train_scaled, y_train), (X_val_scaled, y_val)]
        model.fit(
            X_train_scaled,
            y_train,
            eval_set=eval_set if not use_ensemble else None,
            early_stopping_rounds=early_stopping_rounds if not use_ensemble else None,
            verbose=False
        )

    logger.info("✅ Entraînement terminé")

    # ====================
    # 9. CALIBRATION PROBABILITÉS
    # ====================
    if calibrate_proba:
        logger.info("\n🎲 Calibration isotonic des probabilités...")

        calibrated_model = CalibratedClassifierCV(
            model,
            method='isotonic',
            cv='prefit'  # Modèle déjà fitté
        )

        calibrated_model.fit(X_val_scaled, y_val)

        logger.info("✅ Calibration terminée")
        final_model = calibrated_model
    else:
        final_model = model

    training_time = (datetime.now() - start_time).total_seconds()

    # ====================
    # 10. ÉVALUATION
    # ====================
    logger.info(f"\n📊 Évaluation complète...")

    metrics = evaluate_model_comprehensive(
        final_model,
        X_train_scaled, X_val_scaled, X_test_scaled,
        y_train, y_val, y_test
    )

    # ====================
    # 11. FEATURE IMPORTANCE
    # ====================
    logger.info("\n📈 Calcul feature importance...")

    if use_ensemble:
        # Moyenne des importances XGB + LGBM
        xgb_importance = model.estimators_[0].feature_importances_
        lgbm_importance = model.estimators_[1].feature_importances_
        avg_importance = (xgb_importance + lgbm_importance) / 2

        feature_importance = [
            {"feature": name, "importance": float(imp)}
            for name, imp in zip(selected_features, avg_importance)
        ]
    else:
        importance = model.feature_importances_
        feature_importance = [
            {"feature": name, "importance": float(imp)}
            for name, imp in zip(selected_features, importance)
        ]

    feature_importance.sort(key=lambda x: x["importance"], reverse=True)

    logger.info("🔝 Top 10 features importantes:")
    for i, feat in enumerate(feature_importance[:10], 1):
        logger.info(f"  {i}. {feat['feature']}: {feat['importance']:.4f}")

    # ====================
    # 12. SAUVEGARDE
    # ====================
    logger.info("\n💾 Sauvegarde modèle et metadata...")

    model_dir = Path("optimization/saved_models")
    model_dir.mkdir(parents=True, exist_ok=True)

    model_name = "xgboost_v2_enhanced"

    # Sauvegarder modèle
    model_path = model_dir / f"{model_name}.pkl"
    joblib.dump(final_model, model_path)

    # Sauvegarder preprocessor
    preprocessor_path = model_dir / f"{model_name}_preprocessor.pkl"
    preprocessor.save(str(preprocessor_path))

    # Metadata
    metadata = {
        "model_name": model_name,
        "model_type": "Ensemble_XGB_LGBM_Calibrated" if use_ensemble and calibrate_proba else "XGBoost_V2_Enhanced",
        "model_path": str(model_path),
        "preprocessor_path": str(preprocessor_path),
        "hyperparams": xgb_params,
        "metrics": metrics,
        "feature_importance": feature_importance,
        "training_info": {
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
            "total_features_engineered": len(df.columns),
            "use_ensemble": use_ensemble,
            "calibrate_proba": calibrate_proba,
        },
        "version": "2.1_enhanced",
    }

    metadata_path = model_dir / f"{model_name}_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    logger.info(f"✅ Modèle sauvegardé: {model_path}")
    logger.info(f"✅ Metadata sauvegardée: {metadata_path}")

    # ====================
    # RÉSUMÉ FINAL
    # ====================
    logger.info("\n" + "=" * 90)
    logger.info("🎉 ENTRAÎNEMENT TERMINÉ")
    logger.info("=" * 90)

    logger.info(f"\n⏱️  Durée: {training_time:.1f}s")
    logger.info(f"📊 Données: {len(df)} trades → {len(X_train)} train / {len(X_val)} val / {len(X_test)} test")
    logger.info(f"🔧 Features: {len(df.columns)} totales → {len(selected_features)} sélectionnées")
    logger.info(f"🎯 Modèle: {'Ensemble XGB+LGBM' if use_ensemble else 'XGBoost'} {'+ Calibration' if calibrate_proba else ''}")

    logger.info(f"\n📈 RÉSULTATS TEST:")
    logger.info(f"  - Accuracy:  {metrics['test']['accuracy']:.3f}")
    logger.info(f"  - ROC-AUC:   {metrics['test']['roc_auc']:.3f}")
    logger.info(f"  - F1 Score:  {metrics['test']['f1']:.3f}")
    logger.info(f"  - Precision: {metrics['test']['precision']:.3f}")
    logger.info(f"  - Recall:    {metrics['test']['recall']:.3f}")

    logger.info(f"\n📊 GAPS (Overfitting Check):")
    logger.info(f"  - Accuracy Gap: {metrics['gaps']['accuracy']:.3f}")
    logger.info(f"  - ROC-AUC Gap:  {metrics['gaps']['roc_auc']:.3f}")

    # Diagnostic
    if metrics['test']['accuracy'] >= 0.70:
        logger.info("\n🎉 OBJECTIF ATTEINT: Test accuracy >= 70% !")
    elif metrics['test']['accuracy'] >= 0.65:
        logger.info("\n✅ BON RÉSULTAT: Test accuracy >= 65%")
    else:
        logger.warning("\n⚠️ Accuracy < 65% - Vérifier données/features")

    if metrics['gaps']['accuracy'] > 0.15:
        logger.warning("⚠️ OVERFITTING: Gap > 15%")
    else:
        logger.info("✅ Pas d'overfitting détecté (gap < 15%)")

    logger.info("=" * 90)

    return {
        "model": final_model,
        "preprocessor": preprocessor,
        "metadata": metadata,
        "selected_features": selected_features,
    }


def evaluate_model_comprehensive(
    model,
    X_train: pd.DataFrame,
    X_val: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: pd.Series,
    y_val: pd.Series,
    y_test: pd.Series,
) -> Dict:
    """Évaluation complète avec toutes les métriques"""

    def compute_all_metrics(y_true, y_pred, y_proba):
        return {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, zero_division=0)),
            "f1": float(f1_score(y_true, y_pred, zero_division=0)),
            "roc_auc": float(roc_auc_score(y_true, y_proba)),
            "log_loss": float(log_loss(y_true, y_proba)),
            "brier_score": float(brier_score_loss(y_true, y_proba)),
        }

    # Prédictions
    y_train_pred = model.predict(X_train)
    y_val_pred = model.predict(X_val)
    y_test_pred = model.predict(X_test)

    y_train_proba = model.predict_proba(X_train)[:, 1]
    y_val_proba = model.predict_proba(X_val)[:, 1]
    y_test_proba = model.predict_proba(X_test)[:, 1]

    # Métriques
    train_metrics = compute_all_metrics(y_train, y_train_pred, y_train_proba)
    val_metrics = compute_all_metrics(y_val, y_val_pred, y_val_proba)
    test_metrics = compute_all_metrics(y_test, y_test_pred, y_test_proba)

    # Gaps
    accuracy_gap = train_metrics['accuracy'] - test_metrics['accuracy']
    roc_gap = train_metrics['roc_auc'] - test_metrics['roc_auc']

    # Confusion matrix
    cm_test = confusion_matrix(y_test, y_test_pred)

    logger.info("\n" + "=" * 80)
    logger.info("📊 MÉTRIQUES DÉTAILLÉES")
    logger.info("=" * 80)

    logger.info(f"\n🎯 TRAIN:")
    logger.info(f"  Accuracy={train_metrics['accuracy']:.3f} | ROC-AUC={train_metrics['roc_auc']:.3f} | F1={train_metrics['f1']:.3f}")

    logger.info(f"\n🎯 VALIDATION:")
    logger.info(f"  Accuracy={val_metrics['accuracy']:.3f} | ROC-AUC={val_metrics['roc_auc']:.3f} | F1={val_metrics['f1']:.3f}")

    logger.info(f"\n🎯 TEST:")
    logger.info(f"  Accuracy={test_metrics['accuracy']:.3f} | ROC-AUC={test_metrics['roc_auc']:.3f} | F1={test_metrics['f1']:.3f}")
    logger.info(f"  Precision={test_metrics['precision']:.3f} | Recall={test_metrics['recall']:.3f}")
    logger.info(f"  Log Loss={test_metrics['log_loss']:.3f} | Brier Score={test_metrics['brier_score']:.3f}")

    logger.info(f"\n📉 GAPS (Train-Test):")
    logger.info(f"  Accuracy: {accuracy_gap:+.3f}")
    logger.info(f"  ROC-AUC:  {roc_gap:+.3f}")

    logger.info(f"\n📋 Confusion Matrix (Test):")
    logger.info(f"  [[TN={cm_test[0][0]}, FP={cm_test[0][1]}],")
    logger.info(f"   [FN={cm_test[1][0]}, TP={cm_test[1][1]}]]")

    logger.info("=" * 80)

    return {
        "train": train_metrics,
        "validation": val_metrics,
        "test": test_metrics,
        "gaps": {
            "accuracy": float(accuracy_gap),
            "roc_auc": float(roc_gap),
        },
        "confusion_matrix": cm_test.tolist(),
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Entraîner avec toutes les optimisations
    results = train_xgboost_enhanced(
        timeframe_days=120,
        min_trades=100,
        filter_marginal_trades=True,
        marginal_threshold=0.15,
        max_features=40,
        use_ensemble=True,
        calibrate_proba=True,
    )

    print(f"\n✅ TERMINÉ !")
    print(f"✅ Test Accuracy: {results['metadata']['metrics']['test']['accuracy']:.3f}")
    print(f"✅ Test ROC-AUC: {results['metadata']['metrics']['test']['roc_auc']:.3f}")
