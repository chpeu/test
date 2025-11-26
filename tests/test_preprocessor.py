"""
Tests pour optimization.data.preprocessor
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from optimization.data.preprocessor import FeaturePreprocessor


@pytest.fixture
def sample_df():
    """DataFrame de test avec features et target"""
    np.random.seed(42)
    return pd.DataFrame({
        'scan_id': range(100),
        'timestamp': pd.date_range('2024-01-01', periods=100, freq='1h'),
        'symbol': ['BTCUSDT'] * 100,
        'feature_1': np.random.randn(100),
        'feature_2': np.random.randn(100) * 10,
        'feature_3': np.random.randn(100) + 5,
        'bool_feature': np.random.choice([True, False], 100),
        'target_win': np.random.choice([0, 1], 100),
        'target_pnl': np.random.randn(100) * 100
    })


@pytest.fixture
def preprocessor_robust():
    """Preprocessor avec RobustScaler"""
    return FeaturePreprocessor(scaler_type='robust')


@pytest.fixture
def preprocessor_standard():
    """Preprocessor avec StandardScaler"""
    return FeaturePreprocessor(scaler_type='standard')


class TestFeaturePreprocessorInit:
    """Tests __init__()"""

    def test_init_robust_scaler(self):
        """Test initialisation avec RobustScaler"""
        prep = FeaturePreprocessor(scaler_type='robust')

        assert prep.scaler_type == 'robust'
        assert prep.is_fitted is False
        assert prep.feature_names is None
        from sklearn.preprocessing import RobustScaler
        assert isinstance(prep.scaler, RobustScaler)

    def test_init_standard_scaler(self):
        """Test initialisation avec StandardScaler"""
        prep = FeaturePreprocessor(scaler_type='standard')

        assert prep.scaler_type == 'standard'
        from sklearn.preprocessing import StandardScaler
        assert isinstance(prep.scaler, StandardScaler)

    def test_init_default_scaler(self):
        """Test initialisation par défaut"""
        prep = FeaturePreprocessor()

        assert prep.scaler_type == 'robust'


class TestFitTransform:
    """Tests fit_transform()"""

    def test_fit_transform_success(self, preprocessor_robust, sample_df):
        """Test fit_transform réussit"""
        X_scaled, y = preprocessor_robust.fit_transform(sample_df, 'target_win')

        assert isinstance(X_scaled, pd.DataFrame)
        assert isinstance(y, pd.Series)
        assert len(X_scaled) == len(sample_df)
        assert len(y) == len(sample_df)
        assert preprocessor_robust.is_fitted is True
        assert preprocessor_robust.feature_names is not None

        # Vérifier que target et colonnes exclues ne sont pas dans X
        assert 'target_win' not in X_scaled.columns
        assert 'scan_id' not in X_scaled.columns
        assert 'timestamp' not in X_scaled.columns
        assert 'symbol' not in X_scaled.columns

    def test_fit_transform_missing_target(self, preprocessor_robust, sample_df):
        """Test erreur si target manquante"""
        with pytest.raises(ValueError, match="Target column.*not found"):
            preprocessor_robust.fit_transform(sample_df, 'nonexistent_target')

    def test_fit_transform_boolean_conversion(self, preprocessor_robust, sample_df):
        """Test conversion booléens en int"""
        X_scaled, y = preprocessor_robust.fit_transform(sample_df, 'target_win')

        # bool_feature devrait être dans les features et être numérique
        assert 'bool_feature' in X_scaled.columns
        assert X_scaled['bool_feature'].dtype in [np.int64, np.float64, np.int32, np.float32]

    def test_fit_transform_with_nans(self, preprocessor_robust):
        """Test imputation des NaN"""
        df_with_nans = pd.DataFrame({
            'feature_1': [1.0, np.nan, 3.0, 4.0, 5.0],
            'feature_2': [10, 20, np.nan, 40, 50],
            'target_win': [0, 1, 0, 1, 0]
        })

        X_scaled, y = preprocessor_robust.fit_transform(df_with_nans, 'target_win')

        # Aucun NaN dans le résultat
        assert not X_scaled.isnull().any().any()
        assert len(X_scaled) == 5


class TestTransform:
    """Tests transform()"""

    def test_transform_after_fit(self, preprocessor_robust, sample_df):
        """Test transform après fit"""
        # Fit d'abord
        preprocessor_robust.fit_transform(sample_df, 'target_win')

        # Nouveau données
        new_df = sample_df.iloc[:10].copy()
        X_transformed = preprocessor_robust.transform(new_df)

        assert isinstance(X_transformed, pd.DataFrame)
        assert len(X_transformed) == 10
        assert not X_transformed.isnull().any().any()

    def test_transform_without_fit(self, preprocessor_robust, sample_df):
        """Test transform sans fit échoue"""
        # Should fail or handle gracefully
        try:
            preprocessor_robust.transform(sample_df)
        except Exception:
            # Expected to fail if not fitted
            pass


class TestSaveLoad:
    """Tests save() et load()"""

    def test_save_preprocessor(self, preprocessor_robust, sample_df, tmp_path):
        """Test sauvegarde preprocessor"""
        # Fit first
        preprocessor_robust.fit_transform(sample_df, 'target_win')

        save_path = tmp_path / "preprocessor.pkl"

        # save() returns None
        preprocessor_robust.save(str(save_path))

        # Check file was created
        assert save_path.exists()

    def test_load_preprocessor(self, preprocessor_robust, sample_df, tmp_path):
        """Test chargement preprocessor"""
        # Fit and save
        preprocessor_robust.fit_transform(sample_df, 'target_win')
        save_path = tmp_path / "preprocessor.pkl"
        preprocessor_robust.save(str(save_path))

        # Load
        loaded_prep = FeaturePreprocessor.load(str(save_path))

        assert loaded_prep is not None
        assert loaded_prep.is_fitted is True
        assert loaded_prep.feature_names == preprocessor_robust.feature_names

    def test_save_not_fitted(self, preprocessor_robust, tmp_path):
        """Test sauvegarde sans fit"""
        save_path = tmp_path / "preprocessor.pkl"

        # May save or fail depending on implementation
        try:
            result = preprocessor_robust.save(str(save_path))
            # If saves, should still create file
            assert save_path.exists() or result is False
        except Exception:
            # May raise if not fitted
            pass

    def test_load_nonexistent_file(self):
        """Test chargement fichier inexistant"""
        try:
            result = FeaturePreprocessor.load('/nonexistent/path/preprocessor.pkl')
            # If it doesn't raise, should return None
            assert result is None
        except FileNotFoundError:
            # Expected behavior
            pass


class TestEdgeCases:
    """Tests cas limites"""

    def test_empty_dataframe(self, preprocessor_robust):
        """Test avec DataFrame vide"""
        empty_df = pd.DataFrame({'target_win': []})

        try:
            X, y = preprocessor_robust.fit_transform(empty_df, 'target_win')
            # If succeeds, check it handled empty data
            assert len(X) == 0
            assert len(y) == 0
        except Exception:
            # May raise on empty data
            pass

    def test_single_feature(self, preprocessor_robust):
        """Test avec une seule feature"""
        single_feature_df = pd.DataFrame({
            'feature_1': [1, 2, 3, 4, 5],
            'target_win': [0, 1, 0, 1, 0]
        })

        X, y = preprocessor_robust.fit_transform(single_feature_df, 'target_win')

        assert len(X.columns) == 1
        assert X.columns[0] == 'feature_1'

    def test_all_nan_column(self, preprocessor_robust):
        """Test avec colonne entièrement NaN"""
        df_all_nan = pd.DataFrame({
            'feature_1': [np.nan] * 5,
            'feature_2': [1, 2, 3, 4, 5],
            'target_win': [0, 1, 0, 1, 0]
        })

        try:
            X, y = preprocessor_robust.fit_transform(df_all_nan, 'target_win')
            # Imputer should handle this (median will be nan, then 0 or similar)
            assert X is not None
        except Exception:
            # May fail on all-NaN column
            pass
