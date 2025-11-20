"""
Tests pour l'endpoint de métriques ML
"""

import pytest
import json
from fastapi.testclient import TestClient


def test_get_model_metrics_xgboost(client):
    """Test récupération métriques XGBoost"""
    response = client.get("/api/ml/models/metrics/xgboost_v1")
    
    assert response.status_code == 200
    data = response.json()
    
    # Vérifier structure
    assert 'model_name' in data
    assert 'model_type' in data
    assert 'performance' in data
    assert 'top_features' in data
    assert 'quality_assessment' in data
    assert 'recommendations' in data
    
    # Vérifier métriques
    assert 'train' in data['performance']
    assert 'test' in data['performance']
    assert 'overfitting_gap' in data['performance']
    
    # Vérifier top features
    assert isinstance(data['top_features'], list)
    assert len(data['top_features']) > 0
    
    # Vérifier recommendations
    assert isinstance(data['recommendations'], list)
    assert len(data['recommendations']) > 0


def test_get_model_metrics_not_found(client):
    """Test modèle inexistant"""
    response = client.get("/api/ml/models/metrics/nonexistent_model")
    
    assert response.status_code == 404
    assert 'detail' in response.json()


def test_model_metrics_structure(client):
    """Test structure complète des métriques"""
    response = client.get("/api/ml/models/metrics/xgboost_v1")
    
    if response.status_code == 200:
        data = response.json()
        
        # Training info
        assert 'training_info' in data
        assert 'total_samples' in data['training_info']
        assert 'train_samples' in data['training_info']
        assert 'test_samples' in data['training_info']
        
        # Performance metrics
        perf = data['performance']
        assert 'accuracy' in perf['test']
        assert 'precision' in perf['test']
        assert 'recall' in perf['test']
        assert 'f1' in perf['test']
        assert 'roc_auc' in perf['test']
        
        # Quality assessment
        qa = data['quality_assessment']
        assert 'overfitting' in qa
        assert 'test_performance' in qa
        assert 'data_sufficiency' in qa
        
        # Recommendations
        for rec in data['recommendations']:
            assert 'type' in rec
            assert 'priority' in rec
            assert 'message' in rec
