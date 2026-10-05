"""
Tests complets pour PerSymbolModelManager
"""

import pytest
from unittest.mock import Mock, patch, mock_open
import pandas as pd
import numpy as np


class TestSymbolModelConfig:
    def test_config_default(self):
        from optimization.per_symbol_models import SymbolModelConfig

        config = SymbolModelConfig(symbol="BTC/USDT")
        assert config.symbol == "BTC/USDT"
        assert config.enabled is True
        assert config.min_confidence == 0.55

    def test_config_custom(self):
        from optimization.per_symbol_models import SymbolModelConfig

        config = SymbolModelConfig(
            symbol="ETH/USDT",
            enabled=False,
            min_confidence=0.65,
            hyperparameters={"n_estimators": 200, "max_depth": 4},
        )
        assert config.symbol == "ETH/USDT"
        assert config.enabled is False


class TestSymbolModelMetrics:
    def test_metrics_default(self):
        from optimization.per_symbol_models import SymbolModelMetrics

        metrics = SymbolModelMetrics(symbol="BTC/USDT")
        assert metrics.symbol == "BTC/USDT"
        assert metrics.n_trades == 0
        assert metrics.test_accuracy == 0.0

    def test_metrics_with_values(self):
        from optimization.per_symbol_models import SymbolModelMetrics

        metrics = SymbolModelMetrics(
            symbol="ETH/USDT",
            n_trades=150,
            test_accuracy=0.68,
            cv_f1=0.65,
            optimal_threshold=0.60,
            trained_at="2025-12-10T15:30:00",
        )
        assert metrics.n_trades == 150
        assert metrics.test_accuracy == 0.68


class TestPerSymbolModelManagerInit:
    def test_init_empty(self):
        from optimization.per_symbol_models import PerSymbolModelManager

        with patch(
            "optimization.per_symbol_models.PerSymbolModelManager._load_existing_models"
        ):
            manager = PerSymbolModelManager()
            assert manager.models == {}
            assert manager.global_model is None
            assert manager.global_threshold == 0.55

    def test_init_loads_existing_models(self):
        from optimization.per_symbol_models import PerSymbolModelManager

        with patch.object(PerSymbolModelManager, "_load_existing_models") as mock_load:
            manager = PerSymbolModelManager()
            mock_load.assert_called_once()


class TestPerSymbolModelManagerLoadModels:
    def test_load_existing_models_no_global(self):
        from optimization.per_symbol_models import PerSymbolModelManager

        with (
            patch("pathlib.Path.exists") as mock_exists,
            patch("pathlib.Path.glob") as mock_glob,
            patch("joblib.load"),
            patch("builtins.open", mock_open()),
        ):
            mock_exists.return_value = False
            mock_glob.return_value = []
            manager = PerSymbolModelManager()
            assert manager.global_model is None

    def test_load_existing_models_with_global(self):
        from optimization.per_symbol_models import PerSymbolModelManager

        manager = PerSymbolModelManager()
        with (
            patch("pathlib.Path.exists") as mock_exists,
            patch("joblib.load") as mock_load,
            patch(
                "builtins.open",
                mock_open(
                    read_data='{"selected_features": ["f1", "f2"], "optimal_threshold": 0.60}'
                ),
            ),
            patch("pathlib.Path.with_suffix"),
        ):
            mock_exists.return_value = True
            mock_load.return_value = Mock()
            manager._load_existing_models()
            assert manager.global_model is not None
            assert manager.feature_names == ["f1", "f2"]


class TestPerSymbolModelManagerGetTopSymbols:
    def test_get_top_symbols_success(self):
        from optimization.per_symbol_models import PerSymbolModelManager

        manager = PerSymbolModelManager()
        df = pd.DataFrame({"symbol": ["BTC/USDT"] * 200 + ["ETH/USDT"] * 150})
        with patch(
            "optimization.data.feature_loader.load_features_from_postgres"
        ) as mock_load:
            mock_load.return_value = df
            top_symbols = manager.get_top_symbols(min_trades=80)
            assert len(top_symbols) > 0
            assert ("BTC/USDT", 200) in top_symbols

    def test_get_top_symbols_no_symbol_column(self):
        from optimization.per_symbol_models import PerSymbolModelManager

        manager = PerSymbolModelManager()
        df = pd.DataFrame({"other_col": [1, 2, 3]})
        with patch(
            "optimization.data.feature_loader.load_features_from_postgres"
        ) as mock_load:
            mock_load.return_value = df
            top_symbols = manager.get_top_symbols(min_trades=80)
            assert top_symbols == []

    def test_get_top_symbols_exception(self):
        from optimization.per_symbol_models import PerSymbolModelManager

        manager = PerSymbolModelManager()
        with patch(
            "optimization.data.feature_loader.load_features_from_postgres"
        ) as mock_load:
            mock_load.side_effect = Exception("Database error")
            top_symbols = manager.get_top_symbols(min_trades=80)
            assert top_symbols == []


class TestPerSymbolModelManagerTrainSymbolModel:
    def test_train_symbol_model_insufficient_trades(self):
        from optimization.per_symbol_models import (
            PerSymbolModelManager,
            MIN_TRADES_FOR_INDIVIDUAL_MODEL,
        )

        manager = PerSymbolModelManager()
        n_samples = MIN_TRADES_FOR_INDIVIDUAL_MODEL - 10
        df = pd.DataFrame(
            {
                "symbol": ["BTC/USDT"] * n_samples,
                "target_win": [1] * (n_samples // 2)
                + [0] * (n_samples - n_samples // 2),
            }
        )
        with (
            patch(
                "optimization.data.feature_loader.load_features_from_postgres"
            ) as mock_load,
            patch(
                "optimization.data.feature_engineering.calculate_derived_features"
            ) as mock_engineering,
        ):
            mock_load.return_value = df
            mock_engineering.return_value = df
            result = manager.train_symbol_model("BTC/USDT")
            assert result is None

    def test_train_symbol_model_success(self):
        from optimization.per_symbol_models import PerSymbolModelManager

        manager = PerSymbolModelManager.__new__(PerSymbolModelManager)
        manager.models = {}
        manager.configs = {}
        manager.metrics = {}
        manager.global_model = None
        manager.global_threshold = 0.55
        manager.feature_names = [
            "di_plus_1m",
            "bb_distance_to_upper_5m",
            "ema_diff_pct_1m",
            "rsi_1m",
            "di_plus_5m",
            "ema_diff_pct_5m",
            "bb_distance_to_upper_1m",
            "bb_distance_to_lower_1m",
            "atr_pct_1m",
            "rsi_5m",
            "bb_width_5m",
            "bb_distance_to_lower_5m",
            "macd_momentum_5m",
            "trend_strength_1m",
            "rsi_prev_5m",
            "volatility_momentum_product",
            "di_gap_1m",
            "macd_hist_prev_1m",
            "rsi_prev_1m",
            "macd_hist_1m",
            "trend_strength_5m",
            "momentum_divergence",
            "bb_width_1m",
            "di_minus_5m",
            "momentum_5m",
            "momentum_1m",
            "volume_divergence",
            "adx_5m",
        ]

        n_samples = 200
        df_data = {
            "symbol": ["BTC/USDT"] * n_samples,
            "target_win": [1] * 100 + [0] * 100,
        }
        # Créer TOUTES les features nécessaires
        for f in manager.feature_names:
            df_data[f] = np.random.randn(n_samples)
        df = pd.DataFrame(df_data)
        with (
            patch(
                "optimization.data.feature_loader.load_features_from_postgres"
            ) as mock_load,
            patch(
                "optimization.data.feature_engineering.calculate_derived_features"
            ) as mock_engineering,
            patch("optimization.per_symbol_models.joblib.dump"),
            patch("builtins.open", mock_open()),
        ):
            mock_load.return_value = df
            mock_engineering.return_value = df
            result = manager.train_symbol_model("BTC/USDT")
            assert result is not None
            assert result.symbol == "BTC/USDT"


class TestPerSymbolModelManagerOptimizeHyperparams:
    def test_optimize_hyperparams_success(self):
        from optimization.per_symbol_models import PerSymbolModelManager, RANDOM_SEED

        manager = PerSymbolModelManager()
        X_train = pd.DataFrame({"f1": np.random.randn(100), "f2": np.random.randn(100)})
        y_train = pd.Series([1] * 50 + [0] * 50)
        with patch("optuna.create_study") as mock_create_study:
            mock_study = Mock()
            mock_study.bes
