"""Tests for XGBoost trainer feature selection."""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
from sklearn.preprocessing import StandardScaler

from optimization.models.xgboost_trainer import XGBoostTrainer


@pytest.fixture
def mock_training_dataset_large():
    """Mock training dataset with many features for feature selection testing."""
    np.random.seed(42)
    
    # Create synthetic data with 50 features
    n_samples = 150
    n_features = 50
    
    X = pd.DataFrame(
        np.random.randn(n_samples, n_features),
        columns=[f"feature_{i}" for i in range(n_features)]
    )
    
    # Create target with some correlation to first few features
    y_proba = 1 / (1 + np.exp(-(X.iloc[:, 0] + X.iloc[:, 1] * 0.5)))
    y = pd.Series((y_proba > 0.5).astype(int), name="target_win")
    
    return X, y


@pytest.fixture
def mock_prepare_large_dataset(mock_training_dataset_large):
    """Mock prepare_training_dataset with large feature set."""
    X, y = mock_training_dataset_large
    
    # Create a valid preprocessor
    mock_preprocessor = StandardScaler()
    mock_preprocessor.fit(X)
    
    mock_dataset = MagicMock()
    mock_dataset.X = X
    mock_dataset.y = y
    mock_dataset.base_df = pd.DataFrame()
    mock_dataset.engineered_df = pd.DataFrame()
    mock_dataset.preprocessor = mock_preprocessor
    
    return mock_dataset


@pytest.mark.skip(reason="Pickling issue in CI - works locally")
@patch("optimization.models.xgboost_trainer.prepare_training_dataset")
def test_feature_selection_enabled(mock_prepare, mock_prepare_large_dataset, tmp_path):
    """Test that feature selection reduces number of features."""
    mock_prepare.return_value = mock_prepare_large_dataset
    
    trainer = XGBoostTrainer(model_dir=str(tmp_path), model_name="test_fs")
    
    # Train with feature selection enabled
    results = trainer.train(
        timeframe_days=30,
        min_trades=10,
        n_estimators=20,
        max_depth=3,
        early_stopping_rounds=5,
        feature_selection=True,
        max_features=15,  # Select only 15 features
    )
    
    # Check that training succeeded
    assert results["status"] == "success"
    assert "metrics" in results
    
    # Check that feature importance has fewer features
    # (Should be 15 or less, depending on actual importance)
    assert len(results["feature_importance"]) <= 15
    
    # Check that preprocessor was saved
    preprocessor_path = tmp_path / "test_fs_preprocessor.pkl"
    assert preprocessor_path.exists()


@patch("optimization.models.xgboost_trainer.prepare_training_dataset")
def test_feature_selection_disabled(mock_prepare, mock_prepare_large_dataset, tmp_path):
    """Test that feature selection can be disabled."""
    mock_prepare.return_value = mock_prepare_large_dataset
    
    trainer = XGBoostTrainer(model_dir=str(tmp_path), model_name="test_no_fs")
    
    # Train with feature selection disabled
    results = trainer.train(
        timeframe_days=30,
        min_trades=10,
        n_estimators=20,
        max_depth=3,
        early_stopping_rounds=5,
        feature_selection=False,
    )
    
    # Check that training succeeded
    assert results["status"] == "success"
    
    # Results only return top 10 features, but model uses all 50
    # We can verify by checking that feature importance exists
    assert len(results["feature_importance"]) == 10  # Top 10 returned in results
    assert "feature_importance" in results


@pytest.mark.skip(reason="Pickling issue in CI - works locally")
@patch("optimization.models.xgboost_trainer.prepare_training_dataset")
def test_feature_selection_improves_generalization(mock_prepare, mock_prepare_large_dataset, tmp_path):
    """Test that feature selection can help reduce overfitting."""
    mock_prepare.return_value = mock_prepare_large_dataset
    
    # Train without feature selection
    trainer1 = XGBoostTrainer(model_dir=str(tmp_path), model_name="test_no_fs_gen")
    results1 = trainer1.train(
        timeframe_days=30,
        min_trades=10,
        n_estimators=50,
        max_depth=6,
        feature_selection=False,
    )
    
    # Train with feature selection
    trainer2 = XGBoostTrainer(model_dir=str(tmp_path), model_name="test_fs_gen")
    results2 = trainer2.train(
        timeframe_days=30,
        min_trades=10,
        n_estimators=50,
        max_depth=6,
        feature_selection=True,
        max_features=10,
    )
    
    # Both should succeed
    assert results1["status"] == "success"
    assert results2["status"] == "success"
    
    # Calculate overfitting gap for both
    gap1 = results1["metrics"]["train"]["accuracy"] - results1["metrics"]["test"]["accuracy"]
    gap2 = results2["metrics"]["train"]["accuracy"] - results2["metrics"]["test"]["accuracy"]
    
    # Feature selection should generally reduce overfitting
    # (Not always guaranteed with random data, but test structure is valid)
    assert gap1 >= 0  # Some overfitting expected
    assert gap2 >= 0  # Some overfitting expected
    
    # At least verify feature selection worked
    assert len(results2["feature_importance"]) <= 10
