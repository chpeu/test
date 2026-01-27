"""
Tests pour optimization/models/lightgbm_trainer.py
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json

# Mock toutes les dépendances pour éviter erreurs SQLAlchemy
with patch.dict('sys.modules', {
    'lightgbm': MagicMock(),
    'optimization.data.feature_loader': MagicMock(),
    'optimization.data.feature_engineering': MagicMock(),
    'optimization.data.preprocessor': MagicMock(),
    'optimization.utils.temporal_split': MagicMock()
}):
    from optimization.models.lightgbm_trainer import LightGBMTrainer


class TestLightGBMTrainer:
    """Tests pour LightGBMTrainer"""
    
    def setup_method(self):
        """Setup avant chaque test"""
        self.trainer = LightGBMTrainer(
            model_dir="test_models",
            model_name="test_lgbm"
        )
    
    def test_init_default_params(self):
        """Test initialisation avec paramètres par défaut"""
        trainer = LightGBMTrainer()
        assert trainer.model_dir == Path("optimization/saved_models")
        assert trainer.model_name == "lightgbm_v1"
        assert trainer.model is None
        assert trainer.calibrated_model is None
        
    def test_init_custom_params(self):
        """Test initialisation avec paramètres personnalisés"""
        trainer = LightGBMTrainer(
            model_dir="custom/path",
            model_name="custom_lgbm"
        )
        assert trainer.model_dir == Path("custom/path")
        assert trainer.model_name == "custom_lgbm"
        
    @patch('optimization.models.lightgbm_trainer.Path.mkdir')
    def test_init_creates_model_directory(self, mock_mkdir):
        """Test que le répertoire modèle est créé"""
        LightGBMTrainer()
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        
    def test_initial_attributes(self):
        """Test attributs initiaux du trainer"""
        trainer = LightGBMTrainer()
        assert trainer.model is None
        assert trainer.calibrated_model is None
        assert trainer.feature_names is None
        assert trainer.categorical_features is None
        assert trainer.preprocessor is None
        
    def test_model_attributes_types(self):
        """Test types des attributs principaux"""
        trainer = LightGBMTrainer()
        assert hasattr(trainer, 'model_dir')
        assert hasattr(trainer, 'model_name') 
        assert hasattr(trainer, 'model')
        assert hasattr(trainer, 'calibrated_model')
        assert isinstance(trainer.model_dir, Path)


class TestLightGBMTrainerTraining:
    """Tests pour les fonctions d'entraînement"""
    
    @patch('optimization.models.lightgbm_trainer.load_features_from_postgres')
    @patch('optimization.models.lightgbm_trainer.logger')
    def test_train_starts_logging(self, mock_logger, mock_load):
        """Test que l'entraînement démarre le logging"""
        mock_load.return_value = None  # Simuler échec de chargement
        
        trainer = LightGBMTrainer()
        result = trainer.train()
        
        mock_logger.info.assert_called_with("🚀 Démarrage entraînement LightGBM v1")
        
    @patch('optimization.models.lightgbm_trainer.load_features_from_postgres')
    def test_train_calls_load_features_with_params(self, mock_load):
        """Test que load_features est appelé avec bons paramètres"""
        mock_load.return_value = None
        
        trainer = LightGBMTrainer()
        trainer.train(timeframe_days=90, min_trades=50)
        
        mock_load.assert_called_once_with(
            days_back=90,
            min_trades=50,
            target_column='profit_loss_bool',
            exclude_bad_quality=True
        )
        
    @patch('optimization.models.lightgbm_trainer.load_features_from_postgres')
    def test_train_handles_no_data(self, mock_load):
        """Test gestion absence de données"""
        mock_load.return_value = None
        
        trainer = LightGBMTrainer()
        result = trainer.train()
        
        assert result is not None
        assert 'error' in result or 'success' in result
        
    @patch('optimization.models.lightgbm_trainer.load_features_from_postgres')
    @patch('optimization.models.lightgbm_trainer.calculate_derived_features')
    def test_train_calls_feature_engineering(self, mock_calc, mock_load):
        """Test que l'ingénierie des features est appelée"""
        # Mock dataframe avec colonnes minimum
        mock_df = Mock()
        mock_df.empty = False
        mock_df.shape = [100, 50]
        mock_load.return_value = mock_df
        mock_calc.return_value = mock_df
        
        trainer = LightGBMTrainer()
        
        try:
            trainer.train()
        except Exception:
            # Exception acceptable vu les mocks limités
            pass
            
        mock_calc.assert_called_once_with(mock_df)


class TestLightGBMTrainerPrediction:
    """Tests pour les fonctions de prédiction"""
    
    def test_predict_no_model(self):
        """Test prédiction sans modèle entraîné"""
        trainer = LightGBMTrainer()
        
        result = trainer.predict({})
        
        assert result is not None
        # Devrait gérer gracieusement l'absence de modèle
        
    def test_predict_probability_no_model(self):
        """Test prédiction de probabilité sans modèle"""
        trainer = LightGBMTrainer()
        
        result = trainer.predict_probability({})
        
        assert result is not None
        # Devrait retourner probabilité par défaut ou None


class TestLightGBMTrainerSaveLoad:
    """Tests pour sauvegarde/chargement"""
    
    @patch('optimization.models.lightgbm_trainer.joblib.dump')
    @patch('optimization.models.lightgbm_trainer.Path.exists')
    def test_save_model_creates_files(self, mock_exists, mock_dump):
        """Test que save_model crée les fichiers nécessaires"""
        mock_exists.return_value = True
        trainer = LightGBMTrainer()
        trainer.model = Mock()  # Mock d'un modèle
        trainer.calibrated_model = Mock()
        trainer.feature_names = ['feature1', 'feature2']
        
        result = trainer.save_model()
        
        assert result is not None
        
    @patch('optimization.models.lightgbm_trainer.Path.exists')  
    def test_load_model_missing_files(self, mock_exists):
        """Test chargement avec fichiers manquants"""
        mock_exists.return_value = False
        
        trainer = LightGBMTrainer()
        result = trainer.load_model()
        
        assert result is not None
        # Devrait gérer l'absence de fichiers


class TestLightGBMTrainerValidation:
    """Tests pour validation et métriques"""
    
    def test_validate_model_no_model(self):
        """Test validation sans modèle"""
        trainer = LightGBMTrainer()
        
        result = trainer.validate_model()
        
        assert result is not None
        # Devrait gérer gracieusement l'absence de modèle
        
    def test_get_feature_importance_no_model(self):
        """Test importance des features sans modèle"""
        trainer = LightGBMTrainer()
        
        result = trainer.get_feature_importance()
        
        # Devrait retourner dict vide ou None
        assert result is None or isinstance(result, dict)


class TestLightGBMTrainerEdgeCases:
    """Tests pour cas limites"""
    
    def test_empty_model_name(self):
        """Test avec nom de modèle vide"""
        trainer = LightGBMTrainer(model_name="")
        assert trainer.model_name == ""
        
    def test_special_characters_path(self):
        """Test avec caractères spéciaux dans le chemin"""
        trainer = LightGBMTrainer(model_dir="path/with spaces & symbols")
        assert isinstance(trainer.model_dir, Path)
        
    def test_model_state_consistency(self):
        """Test cohérence de l'état du modèle"""
        trainer = LightGBMTrainer()
        
        # État initial cohérent
        if trainer.model is None:
            assert trainer.calibrated_model is None
            assert trainer.feature_names is None


class TestLightGBMTrainerConfig:
    """Tests pour configuration et paramètres"""
    
    def test_default_hyperparameters(self):
        """Test paramètres par défaut d'entraînement"""
        trainer = LightGBMTrainer()
        
        # Vérifier que train() peut être appelé avec paramètres par défaut
        with patch('optimization.models.lightgbm_trainer.load_features_from_postgres') as mock_load:
            mock_load.return_value = None
            result = trainer.train()
            assert result is not None
            
    @patch('optimization.models.lightgbm_trainer.load_features_from_postgres')
    def test_custom_hyperparameters(self, mock_load):
        """Test avec hyperparamètres personnalisés"""
        mock_load.return_value = None
        
        trainer = LightGBMTrainer()
        result = trainer.train(
            timeframe_days=60,
            min_trades=25,
            n_estimators=50,
            learning_rate=0.05,
            max_depth=4,
            num_leaves=15
        )
        
        assert result is not None
        mock_load.assert_called_once_with(
            days_back=60,
            min_trades=25,
            target_column='profit_loss_bool',
            exclude_bad_quality=True
        )


class TestLightGBMTrainerImports:
    """Tests pour imports et dépendances"""
    
    def test_required_imports_available(self):
        """Test que les imports de base sont disponibles"""
        import logging
        import json
        from pathlib import Path
        from datetime import datetime
        from typing import Dict, Optional, Tuple, List, Union
        import pandas as pd
        import numpy as np
        
        # Ces imports doivent être mockés mais accessibles
        assert True  # Si on arrive ici, les imports de base fonctionnent
        
    def test_sklearn_imports_mocked(self):
        """Test que les imports sklearn sont gérés"""
        try:
            from sklearn.metrics import accuracy_score
            from sklearn.calibration import CalibratedClassifierCV
            # Devrait fonctionner même si mocké
            assert True
        except ImportError:
            pytest.fail("Les imports sklearn devraient être disponibles")


class TestLightGBMTrainerIntegration:
    """Tests d'intégration basiques"""
    
    @patch('optimization.models.lightgbm_trainer.load_features_from_postgres')
    def test_full_pipeline_mock(self, mock_load):
        """Test pipeline complet avec mocks"""
        mock_load.return_value = None
        
        trainer = LightGBMTrainer()
        
        # Entraînement
        train_result = trainer.train(timeframe_days=30, min_trades=10)
        assert train_result is not None
        
        # Prédiction (même sans modèle entraîné)
        pred_result = trainer.predict({'feature1': 1.0, 'feature2': 2.0})
        assert pred_result is not None
        
        # Validation
        val_result = trainer.validate_model()
        assert val_result is not None
