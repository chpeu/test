"""ML training pipeline helpers (data loading, preprocessing, splits).

Centralizes the logic shared between manual scripts, API endpoints and
future schedulers so we manipulate the exact same feature engineering+
preprocessing steps everywhere.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Tuple, Dict

import pandas as pd
from sklearn.model_selection import train_test_split

from optimization.data.feature_loader import load_features_from_postgres
from optimization.data.feature_engineering import calculate_derived_features
from optimization.data.preprocessor import (
    preprocess_features,
    FeaturePreprocessor,
    handle_class_imbalance,
)

logger = logging.getLogger(__name__)


@dataclass
class TrainingDataset:
    """Container holding every intermediate artifact for training."""

    base_df: pd.DataFrame
    engineered_df: pd.DataFrame
    X: pd.DataFrame
    y: pd.Series
    preprocessor: Optional[FeaturePreprocessor]


def fetch_training_dataframe(
    timeframe_days: int = 60,
    min_trades: int = 50,
    include_engineered: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load raw features from PostgreSQL and optionally add engineered columns."""

    logger.info(
        "📥 Fetching training dataframe (timeframe_days=%s, min_trades=%s)",
        timeframe_days,
        min_trades,
    )
    base_df = load_features_from_postgres(
        timeframe_days=timeframe_days,
        min_trades=min_trades,
    )

    if base_df.empty:
        raise ValueError("Aucun trade disponible pour l'entraînement")

    engineered_df = (
        calculate_derived_features(base_df) if include_engineered else base_df.copy()
    )

    logger.info(
        "✅ Training dataframe ready: %s rows, %s columns (engineered=%s)",
        len(engineered_df),
        len(engineered_df.columns),
        include_engineered,
    )

    return base_df, engineered_df


def prepare_training_dataset(
    timeframe_days: int = 60,
    min_trades: int = 50,
    scaler_type: str = "robust",
    save_preprocessor: bool = False,
    preprocessor_path: Optional[str] = None,
    include_engineered: bool = True,
) -> TrainingDataset:
    """Load data, run feature engineering + preprocessing, return ready dataset."""

    base_df, engineered_df = fetch_training_dataframe(
        timeframe_days=timeframe_days,
        min_trades=min_trades,
        include_engineered=include_engineered,
    )

    X, y, preprocessor = preprocess_features(
        engineered_df,
        scaler_type=scaler_type,
        save_preprocessor=save_preprocessor,
        preprocessor_path=preprocessor_path,
    )

    logger.info(
        "🎯 Training matrix prepared: %s samples, %s features",
        len(X),
        len(X.columns),
    )

    return TrainingDataset(
        base_df=base_df,
        engineered_df=engineered_df,
        X=X,
        y=y,
        preprocessor=preprocessor,
    )


def split_training_dataset(
    X: pd.DataFrame,
    y: pd.Series,
    test_size: float = 0.2,
    random_state: int = 42,
    stratify: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Perform a reproducible train/test split."""

    # NOTE: some pandas/numpy combinations can crash inside sklearn's
    # train_test_split when it tries to index a RangeIndex with an empty
    # indexer (observed in CI). To make the split robust, we split on
    # numpy arrays then re-wrap the outputs into pandas objects.
    X_values = X.to_numpy(copy=False)
    y_values = y.to_numpy(copy=False)

    stratify_target = y_values if stratify else None

    logger.info(
        "✂️ Splitting dataset (test_size=%s, stratify=%s)", test_size, stratify
    )

    X_train, X_test, y_train, y_test = train_test_split(
        X_values,
        y_values,
        test_size=test_size,
        random_state=random_state,
        stratify=stratify_target,
    )

    X_train_df = pd.DataFrame(X_train, columns=X.columns)
    X_test_df = pd.DataFrame(X_test, columns=X.columns)
    y_train_s = pd.Series(y_train, name=y.name)
    y_test_s = pd.Series(y_test, name=y.name)

    return X_train_df, X_test_df, y_train_s, y_test_s


def compute_class_weights(
    y: pd.Series, strategy: str = "auto"
) -> Dict[int, float]:
    """Wrapper around handle_class_imbalance to keep everything in one place."""

    weights = handle_class_imbalance(y, strategy=strategy)
    logger.info("⚖️ Class weights computed: %s", weights)
    return weights
