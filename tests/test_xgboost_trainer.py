"""Tests for XGBoost trainer module."""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

from optimization.models.xgboost_trainer import XGBoostTrainer


@pytest.fixture
def mock_training_dataset():
    """Mock training dataset for testing."""
    np.random.seed(42)
    
    # Create synthetic data
    n_samples = 100
    n_features = 10
    
    X = pd.DataFrame(
        np.random.randn(n_samples, n_features),
        columns=[f"feature_{i}" for i in range(n_features)]
    )
    
    y = pd.Series(np.random.randint(0, 2, n_samples), name="target_win")
    
    return X, y


@pytest.fixture
def mock_prepare_training_dataset(mock_training_dataset):
    """Mock prepare_training_dataset to return synthetic data."""
    from sklearn.preprocessing import StandardScaler
    
    X, y = mock_training_dataset
    
    # Create a valid preprocessor mock
    mock_preprocessor = StandardScaler()
    mock_preprocessor.fit(X)
    
    mock_dataset = MagicMock()
    mock_dataset.X = X
    mock_dataset.y = y
    mock_dataset.base_df = pd.DataFrame()
    mock_dataset.engineered_df = pd.DataFrame()
    mock_dataset.preprocessor = mock_preprocessor
    
    return mock_dataset


def test_xgboost_trainer_initialization(tmp_path):
    """Test XGBoostTrainer initialization."""
    trainer = XGBoostTrainer(model_dir=str(tmp_path), model_name="test_model")
    
    assert trainer.model_dir == tmp_path
    assert trainer.model_name == "test_model"
    assert trainer.model is None
    assert trainer.metadata == {}
    assert tmp_path.exists()


@patch("optimization.models.xgboost_trainer.prepare_training_dataset")
def test_xgboost_trainer_train(mock_prepare, mock_prepare_training_dataset, tmp_path):
    """Test XGBoost training pipeline."""
    mock_prepare.return_value = mock_prepare_training_dataset
    
    trainer = XGBoostTrainer(model_dir=str(tmp_path), model_name="test_xgb")
    
    results = trainer.train(
        timeframe_days=30,
        min_trades=10,
        n_estimators=10,  # Small for speed
        max_depth=3,
        early_stopping_rounds=5,
        feature_selection=False,  # Disable for tests
    )
    
    # Check results structure
    assert results["status"] == "success"
    assert results["model_name"] == "test_xgb"
    assert "metrics" in results
    assert "train" in results["metrics"]
    assert "test" in results["metrics"]
    assert "feature_importance" in results
    
    # Check metrics
    assert "accuracy" in results["metrics"]["test"]
    assert "f1" in results["metrics"]["test"]
    assert "roc_auc" in results["metrics"]["test"]
    
    # Check model saved
    assert (tmp_path / "test_xgb.pkl").exists()
    assert (tmp_path / "test_xgb_metadata.json").exists()
    # prepare_training_dataset est mocké, donc le fichier préprocesseur réel
    # n'est pas créé ici. On vérifie simplement que le chemin est renseigné.
    assert trainer.metadata["preprocessor_path"].endswith("test_xgb_preprocessor.pkl")


@patch("optimization.models.xgboost_trainer.prepare_training_dataset")
def test_xgboost_trainer_predict(mock_prepare, mock_prepare_training_dataset, tmp_path):
    """Test XGBoost prediction after training."""
    mock_prepare.return_value = mock_prepare_training_dataset
    
    trainer = XGBoostTrainer(model_dir=str(tmp_path), model_name="test_pred")
    
    # Train first
    trainer.train(
        timeframe_days=30,
        min_trades=10,
        n_estimators=10,
        max_depth=3,
        feature_selection=False,  # Disable for tests
    )
    
    # Predict
    X_test = pd.DataFrame(
        np.random.randn(5, 10),
        columns=[f"feature_{i}" for i in range(10)]
    )
    
    predictions, probabilities = trainer.predict(X_test)
    
    assert len(predictions) == 5
    assert len(probabilities) == 5
    assert all(p in [0, 1] for p in predictions)
    assert all(0 <= p <= 1 for p in probabilities)


def test_xgboost_trainer_load_model_not_found(tmp_path):
    """Test loading non-existent model raises error."""
    with pytest.raises(FileNotFoundError):
        XGBoostTrainer.load_model(model_dir=str(tmp_path), model_name="nonexistent")


@patch("optimization.models.xgboost_trainer.prepare_training_dataset")
def test_xgboost_trainer_load_model(mock_prepare, mock_prepare_training_dataset, tmp_path):
    """Test loading a saved model."""
    mock_prepare.return_value = mock_prepare_training_dataset
    
    # Train and save
    trainer1 = XGBoostTrainer(model_dir=str(tmp_path), model_name="test_load")
    trainer1.train(timeframe_days=30, min_trades=10, n_estimators=10, feature_selection=False)
    
    # Load
    trainer2 = XGBoostTrainer.load_model(model_dir=str(tmp_path), model_name="test_load")
    
    assert trainer2.model is not None
    assert trainer2.metadata["model_name"] == "test_load"
    assert "metrics" in trainer2.metadata


def test_xgboost_trainer_predict_without_training():
    """Test prediction without training raises error."""
    trainer = XGBoostTrainer()
    
    X_test = pd.DataFrame(np.random.randn(5, 10))
    
    with pytest.raises(ValueError, match="Modèle non entraîné"):
        trainer.predict(X_test)
