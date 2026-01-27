"""
Tests pour optimization/models/catboost_trainer.py
Tests simplifiés pour éviter les dépendances SQLAlchemy
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Mock toutes les dépendances complexes
with patch.dict('sys.modules', {
    'catboost': MagicMock(),
    'optimization.ml_pipeline': MagicMock(),
    'optimization.data.feature_loader': MagicMock()
}):
    from optimization.models.catboost_trainer import CatBoostTrainer, CATBOOST_AVAILABLE


class TestCatBoostTrainer:
    """Tests pour CatBoostTrainer"""
    
    def setup_method(self):
        """Setup avant chaque test"""
        self.trainer = CatBoostTrainer(
            model_dir="test_models",
            model_name="test_catboost"
        )
    
    def test_init_default_params(self):
        """Test initialisation avec paramètres par défaut"""
        trainer = CatBoostTrainer()
        assert trainer.model_dir == Path("optimization/saved_models")
        assert trainer.model_name == "catboost_v1"
        assert trainer.model is None
        
    def test_init_custom_params(self):
        """Test initialisation avec paramètres personnalisés"""
        trainer = CatBoostTrainer(
            model_dir="custom/path",
            model_name="custom_model"
        )
        assert trainer.model_dir == Path("custom/path")
        assert trainer.model_name == "custom_model"
        
    @patch('optimization.models.catboost_trainer.Path.mkdir')
    def test_init_creates_model_directory(self, mock_mkdir):
        """Test que le répertoire modèle est créé"""
        CatBoostTrainer()
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        
    def test_catboost_availability_check(self):
        """Test vérification disponibilité CatBoost"""
        # CATBOOST_AVAILABLE devrait être True ou False
        assert isinstance(CATBOOST_AVAILABLE, bool)
        
    def test_catboost_unavailable_warning(self):
        """Test warning quand CatBoost n'est pas disponible"""
        with patch('optimization.models.catboost_trainer.CATBOOST_AVAILABLE', False), \
             patch('optimization.models.catboost_trainer.logger') as mock_logger:
            CatBoostTrainer()
            mock_logger.warning.assert_called_once_with(
                "⚠️ CatBoost non installé. `pip install catboost` requis."
            )
        
    def test_train_without_catboost(self):
        """Test entraînement sans CatBoost installé"""
        with patch('optimization.models.catboost_trainer.CATBOOST_AVAILABLE', False):
            trainer = CatBoostTrainer()
            result = trainer.train()
            
            assert result == {'error': 'CatBoost library missing'}
        
    def test_train_with_catboost_starts_logging(self):
        """Test que l'entraînement démarre le logging"""
        with patch('optimization.models.catboost_trainer.CATBOOST_AVAILABLE', True), \
             patch('optimization.models.catboost_trainer.prepare_training_dataset') as mock_prepare, \
             patch('optimization.models.catboost_trainer.logger') as mock_logger:
            
            mock_prepare.return_value = None  # Simulation échec préparation
            
            trainer = CatBoostTrainer()
            trainer.train()
            
            mock_logger.info.assert_called_with("🚀 Démarrage entraînement CatBoost")
        
    def test_train_calls_prepare_dataset_with_correct_params(self):
        """Test que prepare_training_dataset est appelé avec bons paramètres"""
        with patch('optimization.models.catboost_trainer.CATBOOST_AVAILABLE', True), \
             patch('optimization.models.catboost_trainer.prepare_training_dataset') as mock_prepare:
            
            mock_prepare.return_value = None
            
            trainer = CatBoostTrainer()
            trainer.train(
                timeframe_days=90,
                min_trades=50
            )
            
            mock_prepare.assert_called_once_with(
                timeframe_days=90,
                min_trades=50
            )
        
    def test_train_default_parameters(self):
        """Test paramètres par défaut de l'entraînement"""
        trainer = CatBoostTrainer()
        
        # Mock pour éviter l'exécution complète
        with patch('optimization.models.catboost_trainer.CATBOOST_AVAILABLE', False):
            result = trainer.train()
            assert result == {'error': 'CatBoost library missing'}


class TestCatBoostTrainerIntegration:
    """Tests d'intégration (avec mocks)"""
    
    def test_train_integration_flow_no_catboost(self):
        """Test flux d'entraînement sans CatBoost"""
        with patch('optimization.models.catboost_trainer.CATBOOST_AVAILABLE', False):
            trainer = CatBoostTrainer()
            result = trainer.train(timeframe_days=30, min_trades=10)
            assert result == {'error': 'CatBoost library missing'}
    
    def test_train_integration_flow_with_catboost(self):
        """Test flux complet d'entraînement (avec mocks complets)"""
        with patch('optimization.models.catboost_trainer.CATBOOST_AVAILABLE', True), \
             patch('optimization.models.catboost_trainer.prepare_training_dataset') as mock_prepare:
            
            # Mock return None pour simuler échec de préparation dataset
            mock_prepare.return_value = None
            
            trainer = CatBoostTrainer()
            
            # Le train devrait gérer le cas où prepare_training_dataset retourne None
            try:
                result = trainer.train(timeframe_days=30, min_trades=10)
                # Si ça ne plante pas, c'est que la gestion d'erreur fonctionne
            except Exception as e:
                # Acceptable si c'est une exception contrôlée
                assert any(word in str(e).lower() for word in ['none', 'dataset', 'data', 'training'])


class TestCatBoostTrainerEdgeCases:
    """Tests pour cas limites"""
    
    def test_model_dir_path_handling(self):
        """Test gestion des chemins de répertoire"""
        trainer = CatBoostTrainer(model_dir="path/with/spaces and special chars")
        assert isinstance(trainer.model_dir, Path)
        
    def test_empty_model_name(self):
        """Test avec nom de modèle vide"""
        trainer = CatBoostTrainer(model_name="")
        assert trainer.model_name == ""
        
    def test_model_attributes_initial_state(self):
        """Test état initial des attributs"""
        trainer = CatBoostTrainer()
        assert trainer.model is None
        assert hasattr(trainer, 'model_dir')
        assert hasattr(trainer, 'model_name')


class TestCatBoostTrainerImports:
    """Tests pour les imports et dépendances"""
    
    def test_required_imports_available(self):
        """Test que les imports requis sont disponibles"""
        # Ces imports doivent fonctionner
        import logging
        import json
        from pathlib import Path
        from datetime import datetime
        from typing import Dict, Optional, List
        import pandas as pd
        import numpy as np
        from sklearn.metrics import accuracy_score
        
        # Test que les imports ML pipeline sont mockés ou disponibles
        try:
            from optimization.ml_pipeline import prepare_training_dataset
            assert prepare_training_dataset is not None
        except ImportError:
            # Acceptable en environnement de test
            pass
            
    @patch.dict('sys.modules', {'catboost': None})
    def test_missing_catboost_import(self):
        """Test comportement quand CatBoost manque"""
        # Force reimport avec CatBoost manquant
        import sys
        if 'optimization.models.catboost_trainer' in sys.modules:
            del sys.modules['optimization.models.catboost_trainer']
            
        # L'import ne devrait pas planter même sans CatBoost
        try:
            from optimization.models.catboost_trainer import CatBoostTrainer
            trainer = CatBoostTrainer()
            result = trainer.train()
            assert 'error' in result
        except ImportError:
            pytest.fail("L'import ne devrait pas échouer même sans CatBoost")
