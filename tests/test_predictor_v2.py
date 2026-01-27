"""
Tests unitaires pour MLPredictorV2 (Régression PNL%)
Coverage target: 70%+
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
import joblib
import json
from pathlib import Path

from optimization.predictor_v2 import (
    MLPredictorV2,
    get_predictor_v2,
    predict_pnl
)


@pytest.fixture
def mock_features():
    """Features de test pour prédictions"""
    return {
        'rsi_1m': 65.3,
        'macd_1m': 0.12,
        'bb_lower_1m': 42150,
        'bb_upper_1m': 42850,
        'bb_width_1m': 0.016,
        'price': 42500,
        'atr_1m': 125.0,
        'volume_ratio_1m': 1.5,
        'ema_diff_pct_1m': 0.35,
        'rsi_5m': 58.2,
        'macd_5m': 0.08,
        'trend_strength': 2.1,
        'volatility_regime': 1.8
    }


@pytest.fixture
def mock_model():
    """Mock XGBoost model"""
    model = Mock()
    model.predict = Mock(return_value=np.array([2.34]))
    model.feature_importances_ = np.array([0.125, 0.098, 0.075, 0.062, 0.045])
    
    # Mock get_booster for feature importance
    booster = Mock()
    booster.get_score = Mock(return_value={
        'rsi_1m': 0.125,
        'macd_1m': 0.098,
        'bb_width_1m': 0.075
    })
    model.get_booster = Mock(return_value=booster)
    
    return model


@pytest.fixture
def mock_preprocessor():
    """Mock preprocessor"""
    preprocessor = Mock()
    preprocessor.transform = Mock(return_value=np.array([[0.5, 0.3, 0.2, 0.1, 0.05]]))
    preprocessor.feature_names_in_ = ['rsi_1m', 'macd_1m', 'bb_width_1m', 'price', 'atr_1m']
    return preprocessor


@pytest.fixture
def mock_metadata():
    """Mock metadata"""
    return {
        'model_name': 'xgboost_v2_test',
        'model_type': 'XGBRegressor',
        'version': '2.0',
        'trained_at': '2025-11-25T19:00:00',
        'metrics': {
            'train': {'r2': 0.387, 'mae': 0.32},
            'val': {'r2': 0.256, 'mae': 0.41},
            'test': {'r2': 0.234, 'mae': 0.450, 'f1': 0.623}
        },
        'selected_features': ['rsi_1m', 'macd_1m', 'bb_width_1m', 'price', 'atr_1m']
    }


class TestMLPredictorV2Init:
    """Tests d'initialisation"""
    
    def test_init_default(self):
        """Test initialisation par défaut"""
        predictor = MLPredictorV2()
        
        assert predictor.model_name == 'xgboost_v2_latest'
        assert predictor.model is None
        assert predictor.preprocessor is None
        assert predictor.metadata is None
        assert predictor.loaded is False
    
    def test_init_custom_model(self):
        """Test initialisation avec nom custom"""
        predictor = MLPredictorV2(model_name='xgboost_v2_custom')
        
        assert predictor.model_name == 'xgboost_v2_custom'
        assert predictor.loaded is False


class TestMLPredictorV2LoadModel:
    """Tests chargement modèle depuis fichiers"""
    
    @patch('optimization.predictor_v2.joblib.load')
    @patch('optimization.predictor_v2.os.path.exists')
    def test_load_model_success(self, mock_exists, mock_joblib, mock_model, mock_preprocessor):
        """Test chargement réussi"""
        mock_exists.return_value = True
        mock_joblib.side_effect = [mock_model, mock_preprocessor]
        
        predictor = MLPredictorV2()
        result = predictor.load_model()
        
        assert result is True
        assert predictor.loaded is True
        assert predictor.model == mock_model
        assert predictor.preprocessor == mock_preprocessor
    
    @patch('optimization.predictor_v2.os.path.exists')
    def test_load_model_file_not_found(self, mock_exists):
        """Test modèle non trouvé"""
        mock_exists.return_value = False
        
        predictor = MLPredictorV2()
        result = predictor.load_model()
        
        assert result is False
        assert predictor.loaded is False
    
    @patch('optimization.predictor_v2.joblib.load')
    @patch('optimization.predictor_v2.os.path.exists')
    def test_load_model_with_metadata(self, mock_exists, mock_joblib, mock_model, mock_preprocessor, mock_metadata):
        """Test chargement avec metadata"""
        mock_exists.return_value = True
        mock_joblib.side_effect = [mock_model, mock_preprocessor]
        
        # Mock open pour metadata
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_metadata)
            
            predictor = MLPredictorV2()
            result = predictor.load_model()
        
        assert result is True
        assert predictor.metadata is not None

    @patch('optimization.predictor_v2.joblib.load')
    @patch('optimization.predictor_v2.os.path.exists')
    def test_load_model_metadata_parse_error_is_non_blocking(self, mock_exists, mock_joblib, mock_model, mock_preprocessor):
        """Couvre l'erreur metadata (non bloquant)"""
        mock_exists.return_value = True
        mock_joblib.side_effect = [mock_model, mock_preprocessor]

        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = '{invalid json'

            predictor = MLPredictorV2()
            assert predictor.load_model() is True
            assert predictor.loaded is True
            assert predictor.metadata is None

    @patch('optimization.predictor_v2.joblib.load')
    @patch('optimization.predictor_v2.os.path.exists')
    def test_load_model_feature_names_from_preprocessor_dict(self, mock_exists, mock_joblib, mock_model):
        """Couvre feature_names via preprocessor dict['feature_names']"""
        def _exists(path):
            return not str(path).endswith('_metadata.json')

        mock_exists.side_effect = _exists
        preprocessor = {'feature_names': ['a', 'b', 'c']}
        mock_joblib.side_effect = [mock_model, preprocessor]

        predictor = MLPredictorV2()
        assert predictor.load_model() is True
        assert predictor.feature_names == ['a', 'b', 'c']

    @patch('optimization.predictor_v2.joblib.load')
    @patch('optimization.predictor_v2.os.path.exists')
    def test_load_model_feature_names_from_feature_names_in(self, mock_exists, mock_joblib, mock_model):
        """Couvre feature_names via preprocessor.feature_names_in_"""
        def _exists(path):
            return not str(path).endswith('_metadata.json')

        mock_exists.side_effect = _exists

        class _Prep:
            feature_names_in_ = ['x', 'y']

            def transform(self, df):
                return df.values

        mock_joblib.side_effect = [mock_model, _Prep()]

        predictor = MLPredictorV2()
        assert predictor.load_model() is True
        assert predictor.feature_names == ['x', 'y']

    @patch('optimization.predictor_v2.joblib.load')
    @patch('optimization.predictor_v2.os.path.exists')
    def test_load_model_feature_names_unknown_defaults_to_empty(self, mock_exists, mock_joblib, mock_model):
        """Couvre le fallback feature_names=[]"""
        def _exists(path):
            return not str(path).endswith('_metadata.json')

        mock_exists.side_effect = _exists
        mock_joblib.side_effect = [mock_model, object()]

        predictor = MLPredictorV2()
        assert predictor.load_model() is True
        assert predictor.feature_names == []


class TestMLPredictorV2Predict:
    """Tests prédiction"""
    
    def test_predict_success(self, mock_features, mock_model, mock_preprocessor, mock_metadata):
        """Test prédiction réussie"""
        predictor = MLPredictorV2()
        predictor.model = mock_model
        predictor.preprocessor = mock_preprocessor
        predictor.metadata = mock_metadata
        predictor.feature_names = mock_metadata['selected_features']
        predictor.loaded = True
        
        with patch('optimization.predictor_v2.calculate_derived_features') as mock_fe:
            mock_fe.return_value = pd.DataFrame([mock_features])
            
            prediction = predictor.predict(mock_features, return_classification=True)
        
        assert prediction is not None
        assert 'predicted_pnl' in prediction
        assert prediction['predicted_pnl'] == 2.34
        assert 'classification' in prediction
        assert prediction['classification'] == 'win'
        assert prediction['is_profitable'] is True
    
    def test_predict_negative_pnl(self, mock_features, mock_model, mock_preprocessor):
        """Test prédiction PNL négatif"""
        mock_model.predict = Mock(return_value=np.array([-1.25]))
        
        predictor = MLPredictorV2()
        predictor.model = mock_model
        predictor.preprocessor = mock_preprocessor
        predictor.feature_names = ['rsi_1m', 'macd_1m']
        predictor.loaded = True
        
        with patch('optimization.predictor_v2.calculate_derived_features') as mock_fe:
            mock_fe.return_value = pd.DataFrame([mock_features])
            
            prediction = predictor.predict(mock_features)
        
        assert prediction['predicted_pnl'] == -1.25
        assert prediction['classification'] == 'loss'
        assert prediction['is_profitable'] is False
    
    def test_predict_without_classification(self, mock_features, mock_model, mock_preprocessor):
        """Test prédiction sans classification"""
        predictor = MLPredictorV2()
        predictor.model = mock_model
        predictor.preprocessor = mock_preprocessor
        predictor.feature_names = ['rsi_1m']
        predictor.loaded = True
        
        with patch('optimization.predictor_v2.calculate_derived_features') as mock_fe:
            mock_fe.return_value = pd.DataFrame([mock_features])
            
            prediction = predictor.predict(mock_features, return_classification=False)
        
        assert 'predicted_pnl' in prediction
        assert 'classification' not in prediction
    
    def test_predict_with_missing_features(self, mock_model, mock_preprocessor):
        """Test prédiction avec features manquantes"""
        incomplete_features = {'rsi_1m': 65.3}
        
        predictor = MLPredictorV2()
        predictor.model = mock_model
        predictor.preprocessor = mock_preprocessor
        predictor.feature_names = ['rsi_1m', 'macd_1m', 'price']
        predictor.loaded = True
        
        with patch('optimization.predictor_v2.calculate_derived_features') as mock_fe:
            mock_fe.return_value = pd.DataFrame([incomplete_features])
            
            prediction = predictor.predict(incomplete_features)
        
        # Doit réussir en ajoutant 0 pour features manquantes
        assert prediction is not None
    
    def test_predict_handles_nan_inf(self, mock_features, mock_model, mock_preprocessor):
        """Test gestion NaN et Inf"""
        mock_features['rsi_1m'] = np.nan
        mock_features['macd_1m'] = np.inf
        
        predictor = MLPredictorV2()
        predictor.model = mock_model
        predictor.preprocessor = mock_preprocessor
        predictor.feature_names = ['rsi_1m', 'macd_1m']
        predictor.loaded = True
        
        with patch('optimization.predictor_v2.calculate_derived_features') as mock_fe:
            mock_fe.return_value = pd.DataFrame([mock_features])
            
            prediction = predictor.predict(mock_features)
        
        # Doit réussir en remplaçant NaN/Inf par 0
        assert prediction is not None

    def test_predict_with_dict_preprocessor_imputer_and_scaler(self, mock_features, mock_model):
        """Couvre la branche preprocessor dict (imputer + scaler)."""
        predictor = MLPredictorV2()
        predictor.model = mock_model
        predictor.feature_names = ['rsi_1m', 'macd_1m']
        predictor.loaded = True

        mock_imputer = Mock()
        mock_imputer.transform = Mock(return_value=np.array([[1.0, 2.0]]))

        mock_scaler = Mock()
        mock_scaler.transform = Mock(return_value=np.array([[10.0, 20.0]]))

        predictor.preprocessor = {
            'imputer': mock_imputer,
            'scaler': mock_scaler,
        }

        with patch('optimization.predictor_v2.calculate_derived_features') as mock_fe:
            mock_fe.return_value = pd.DataFrame([mock_features])
            prediction = predictor.predict(mock_features)

        assert prediction is not None
        mock_imputer.transform.assert_called_once()
        mock_scaler.transform.assert_called_once()
        mock_model.predict.assert_called_once()

    def test_predict_with_dict_preprocessor_no_scaler_uses_values(self, mock_features, mock_model):
        """Couvre la branche preprocessor dict avec scaler=None => df.values."""
        predictor = MLPredictorV2()
        predictor.model = mock_model
        predictor.feature_names = ['rsi_1m', 'macd_1m']
        predictor.loaded = True

        mock_imputer = Mock()
        mock_imputer.transform = Mock(return_value=np.array([[1.0, 2.0]]))

        predictor.preprocessor = {
            'imputer': mock_imputer,
            'scaler': None,
        }

        with patch('optimization.predictor_v2.calculate_derived_features') as mock_fe:
            mock_fe.return_value = pd.DataFrame([mock_features])
            prediction = predictor.predict(mock_features)

        assert prediction is not None
        mock_imputer.transform.assert_called_once()
        mock_model.predict.assert_called_once()

    def test_predict_without_preprocessor_uses_raw_values(self, mock_features, mock_model):
        """Couvre la branche sans preprocessor (X=df.values)."""
        predictor = MLPredictorV2()
        predictor.model = mock_model
        predictor.preprocessor = None
        predictor.feature_names = ['rsi_1m', 'macd_1m']
        predictor.loaded = True

        with patch('optimization.predictor_v2.calculate_derived_features') as mock_fe:
            mock_fe.return_value = pd.DataFrame([mock_features])
            prediction = predictor.predict(mock_features)

        assert prediction is not None
        mock_model.predict.assert_called_once()

    def test_predict_feature_engineering_exception_fallback_to_raw(self, mock_features, mock_model, mock_preprocessor):
        """Couvre le fallback quand calculate_derived_features lève."""
        predictor = MLPredictorV2()
        predictor.model = mock_model
        predictor.preprocessor = mock_preprocessor
        predictor.feature_names = ['rsi_1m']
        predictor.loaded = True

        with patch('optimization.predictor_v2.calculate_derived_features', side_effect=Exception('boom')):
            prediction = predictor.predict(mock_features)

        assert prediction is not None


class TestMLPredictorV2ShouldReject:
    """Tests filtrage trades"""
    
    def test_should_reject_low_pnl(self, mock_features, mock_model, mock_preprocessor):
        """Test rejet si PNL < seuil"""
        mock_model.predict = Mock(return_value=np.array([0.2]))  # +0.2%
        
        predictor = MLPredictorV2()
        predictor.model = mock_model
        predictor.preprocessor = mock_preprocessor
        predictor.feature_names = ['rsi_1m']
        predictor.loaded = True
        
        with patch('optimization.predictor_v2.calculate_derived_features') as mock_fe:
            mock_fe.return_value = pd.DataFrame([mock_features])
            
            should_reject, predicted_pnl, reason = predictor.should_reject_trade(
                mock_features,
                min_expected_pnl=0.5
            )
        
        assert should_reject is True
        assert predicted_pnl == 0.2
        assert 'PNL prédit +0.20%' in reason
        assert 'minimum +0.50%' in reason
    
    def test_should_accept_high_pnl(self, mock_features, mock_model, mock_preprocessor):
        """Test acceptation si PNL >= seuil"""
        mock_model.predict = Mock(return_value=np.array([2.5]))  # +2.5%
        
        predictor = MLPredictorV2()
        predictor.model = mock_model
        predictor.preprocessor = mock_preprocessor
        predictor.feature_names = ['rsi_1m']
        predictor.loaded = True
        
        with patch('optimization.predictor_v2.calculate_derived_features') as mock_fe:
            mock_fe.return_value = pd.DataFrame([mock_features])
            
            should_reject, predicted_pnl, reason = predictor.should_reject_trade(
                mock_features,
                min_expected_pnl=0.5
            )
        
        assert should_reject is False
        assert predicted_pnl == 2.5
        assert reason is None
    
    def test_should_reject_negative_pnl(self, mock_features, mock_model, mock_preprocessor):
        """Test rejet si PNL négatif"""
        mock_model.predict = Mock(return_value=np.array([-1.2]))  # -1.2%
        
        predictor = MLPredictorV2()
        predictor.model = mock_model
        predictor.preprocessor = mock_preprocessor
        predictor.feature_names = ['rsi_1m']
        predictor.loaded = True
        
        with patch('optimization.predictor_v2.calculate_derived_features') as mock_fe:
            mock_fe.return_value = pd.DataFrame([mock_features])
            
            should_reject, predicted_pnl, reason = predictor.should_reject_trade(
                mock_features,
                min_expected_pnl=0.3
            )
        
        assert should_reject is True
        assert predicted_pnl == -1.2

    def test_should_reject_trade_exception_returns_safe_default(self, mock_features):
        predictor = MLPredictorV2()
        with patch.object(predictor, 'predict', side_effect=RuntimeError('boom')):
            should_reject, predicted_pnl, reason = predictor.should_reject_trade(mock_features)

        assert should_reject is False
        assert predicted_pnl is None
        assert reason == 'Erreur ML V2'

    def test_should_reject_trade_prediction_none_returns_not_reject(self, mock_features):
        predictor = MLPredictorV2()
        with patch.object(predictor, 'predict', return_value=None):
            should_reject, predicted_pnl, reason = predictor.should_reject_trade(mock_features)

        assert should_reject is False
        assert predicted_pnl is None
        assert reason == 'ML V2 indisponible'


class TestMLPredictorV2ConfidenceInterval:
    """Tests intervalles de confiance"""
    
    def test_confidence_interval_with_metadata(self, mock_features, mock_model, mock_preprocessor, mock_metadata):
        """Test intervalle avec metadata"""
        predictor = MLPredictorV2()
        predictor.model = mock_model
        predictor.preprocessor = mock_preprocessor
        predictor.metadata = mock_metadata
        predictor.feature_names = ['rsi_1m']
        predictor.loaded = True
        
        with patch('optimization.predictor_v2.calculate_derived_features') as mock_fe:
            mock_fe.return_value = pd.DataFrame([mock_features])
            
            interval = predictor.get_confidence_interval(mock_features, confidence_level=0.95)
        
        assert interval is not None

    def test_confidence_interval_returns_none_when_prediction_none(self, mock_features):
        predictor = MLPredictorV2()
        with patch.object(predictor, 'predict', return_value=None):
            assert predictor.get_confidence_interval(mock_features) is None

    def test_confidence_interval_returns_none_when_predict_raises(self, mock_features):
        predictor = MLPredictorV2()
        with patch.object(predictor, 'predict', side_effect=RuntimeError('boom')):
            assert predictor.get_confidence_interval(mock_features) is None
    
    def test_confidence_interval_without_metadata(self, mock_features, mock_model, mock_preprocessor):
        """Test intervalle sans metadata (MAE par défaut)"""
        predictor = MLPredictorV2()
        predictor.model = mock_model
        predictor.preprocessor = mock_preprocessor
        predictor.feature_names = ['rsi_1m']
        predictor.loaded = True
        
        with patch('optimization.predictor_v2.calculate_derived_features') as mock_fe:
            mock_fe.return_value = pd.DataFrame([mock_features])
            
            interval = predictor.get_confidence_interval(mock_features)
        
        assert interval is not None


class TestMLPredictorV2BatchPredict:
    """Tests prédictions batch"""
    
    def test_batch_predict_success(self, mock_features, mock_model, mock_preprocessor):
        """Test batch réussi"""
        predictor = MLPredictorV2()
        predictor.model = mock_model
        predictor.preprocessor = mock_preprocessor
        predictor.feature_names = ['rsi_1m']
        predictor.loaded = True
        
        features_list = [mock_features, mock_features, mock_features]
        
        with patch('optimization.predictor_v2.calculate_derived_features') as mock_fe:
            mock_fe.return_value = pd.DataFrame([mock_features])
            
            predictions = predictor.batch_predict(features_list)
        
        assert len(predictions) == 3
        assert all(p is not None for p in predictions)
        assert all('predicted_pnl' in p for p in predictions)


class TestMLPredictorV2LoadFromPostgres:
    def test_load_from_postgres_falls_back_when_pg_disabled(self, mock_model, mock_preprocessor):
        predictor = MLPredictorV2()

        class _FakePG:
            enabled = False

        with patch('core.simple_pg_logger.SimplePGLogger', return_value=_FakePG()):
            with patch.object(predictor, 'load_model', return_value=True) as mock_load:
                assert predictor.load_from_postgres() is True
                mock_load.assert_called_once()

    def test_load_from_postgres_falls_back_when_no_row(self, mock_model, mock_preprocessor):
        predictor = MLPredictorV2()

        class _Cursor:
            description = [('id',), ('model_path',), ('preprocessor_path',)]

            def execute(self, *_args, **_kwargs):
                return None

            def fetchone(self):
                return None

            def close(self):
                return None

        class _Conn:
            def cursor(self):
                return _Cursor()

        class _FakePG:
            enabled = True
            conn = _Conn()

        with patch('core.simple_pg_logger.SimplePGLogger', return_value=_FakePG()):
            with patch.object(predictor, 'load_model', return_value=True) as mock_load:
                assert predictor.load_from_postgres() is True
                mock_load.assert_called_once()

    def test_load_from_postgres_success_sets_metadata_and_features(self, tmp_path, mock_model, mock_preprocessor):
        predictor = MLPredictorV2()

        model_path = str(tmp_path / 'm.pkl')
        prep_path = str(tmp_path / 'p.pkl')

        class _Cursor:
            description = [
                ('model_name',),
                ('model_type',),
                ('version',),
                ('trained_at',),
                ('train_r2',),
                ('train_mae',),
                ('val_r2',),
                ('val_mae',),
                ('test_r2',),
                ('test_mae',),
                ('test_f1',),
                ('model_params',),
                ('selected_features',),
                ('model_path',),
                ('preprocessor_path',),
            ]

            def execute(self, *_args, **_kwargs):
                return None

            def fetchone(self):
                from datetime import datetime
                return (
                    'xgboost_v2_from_pg',
                    'XGBRegressor',
                    '2.0',
                    datetime.utcnow(),
                    0.1,
                    0.2,
                    0.1,
                    0.2,
                    0.1,
                    0.2,
                    0.3,
                    '{"a": 1}',
                    '["rsi_1m", "macd_1m"]',
                    model_path,
                    prep_path,
                )

            def close(self):
                return None

        class _Conn:
            def cursor(self):
                return _Cursor()

        class _FakePG:
            enabled = True
            conn = _Conn()

        with patch('core.simple_pg_logger.SimplePGLogger', return_value=_FakePG()):
            with patch('optimization.predictor_v2.os.path.exists', return_value=True):
                def _load(path):
                    if str(path) == model_path:
                        return mock_model
                    if str(path) == prep_path:
                        return mock_preprocessor
                    raise FileNotFoundError(str(path))

                with patch('optimization.predictor_v2.joblib.load', side_effect=_load):
                    assert predictor.load_from_postgres(model_id=1) is True
                    assert predictor.loaded is True
                    assert predictor.metadata is not None
                    assert predictor.feature_names == ['rsi_1m', 'macd_1m']



class TestGetPredictorV2:
    """Tests fonction singleton"""
    
    def test_get_predictor_v2_creates_instance(self):
        """Test création instance"""
        with patch.object(MLPredictorV2, 'load_from_postgres', return_value=True):
            predictor = get_predictor_v2()
            
            assert isinstance(predictor, MLPredictorV2)
            assert predictor.model_name == 'xgboost_v2_latest'
    
    def test_get_predictor_v2_singleton(self):
        """Test comportement singleton"""
        with patch.object(MLPredictorV2, 'load_from_postgres', return_value=True):
            predictor1 = get_predictor_v2()
            predictor2 = get_predictor_v2()
            
            # Devrait retourner la même instance
            assert predictor1 is predictor2

    def test_get_predictor_v2_recreates_when_model_name_changes(self):
        import optimization.predictor_v2 as mod
        mod._predictor_v2_instance = None

        with patch.object(MLPredictorV2, 'load_from_postgres', return_value=True):
            p1 = get_predictor_v2(model_name='xgboost_v2_latest')
            p2 = get_predictor_v2(model_name='xgboost_v2_other')
            assert p2 is not p1
            assert p2.model_name == 'xgboost_v2_other'


class TestPredictPNL:
    """Tests helper function"""
    
    def test_predict_pnl_success(self, mock_features):
        """Test prédiction rapide"""
        with patch('optimization.predictor_v2.get_predictor_v2') as mock_get:
            mock_predictor = Mock()
            mock_predictor.predict = Mock(return_value={
                'predicted_pnl': 2.34,
                'classification': 'win'
            })
            mock_get.return_value = mock_predictor
            
            prediction = predict_pnl(mock_features)
            
            assert prediction is not None
            assert prediction['predicted_pnl'] == 2.34
    
    def test_predict_pnl_with_logging(self, mock_features):
        """Test avec logging PostgreSQL"""
        with patch('optimization.predictor_v2.get_predictor_v2') as mock_get:
            mock_predictor = Mock()
            mock_predictor.predict = Mock(return_value={
                'predicted_pnl': 2.34,
                'classification': 'win',
                'classification_value': 1
            })
            mock_get.return_value = mock_predictor
            
            with patch('optimization.predictor_v2.log_prediction') as mock_log:
                mock_log.return_value = 12345
                
                prediction = predict_pnl(
                    mock_features,
                    symbol='BTCUSDT',
                    scan_id=76543,
                    log_to_db=True
                )
                
                assert prediction['prediction_id'] == 12345
                mock_log.assert_called_once()

    def test_predict_pnl_logging_exception_is_swallowed(self, mock_features):
        with patch('optimization.predictor_v2.get_predictor_v2') as mock_get:
            mock_predictor = Mock()
            mock_predictor.predict = Mock(return_value={
                'predicted_pnl': 2.34,
                'classification': 'win',
                'classification_value': 1
            })
            mock_get.return_value = mock_predictor

            with patch('optimization.predictor_v2.log_prediction', side_effect=RuntimeError('boom')):
                prediction = predict_pnl(
                    mock_features,
                    symbol='BTCUSDT',
                    scan_id=1,
                    log_to_db=True,
                )

        assert prediction is not None
        assert prediction.get('prediction_id') is None


class TestEdgeCases:
    """Tests cas limites"""
    
    def test_predict_with_zero_pnl(self, mock_features, mock_model, mock_preprocessor):
        """Test PNL exactement 0"""
        mock_model.predict = Mock(return_value=np.array([0.0]))
        
        predictor = MLPredictorV2()
        predictor.model = mock_model
        predictor.preprocessor = mock_preprocessor
        predictor.feature_names = ['rsi_1m']
        predictor.loaded = True
        
        with patch('optimization.predictor_v2.calculate_derived_features') as mock_fe:
            mock_fe.return_value = pd.DataFrame([mock_features])
            
            prediction = predictor.predict(mock_features)
        
        assert prediction['predicted_pnl'] == 0.0
        assert prediction['classification'] == 'loss'  # Seuil à 0, donc = 0 → loss
    
    def test_predict_very_high_pnl(self, mock_features, mock_model, mock_preprocessor):
        """Test PNL très élevé"""
        mock_model.predict = Mock(return_value=np.array([15.5]))
        
        predictor = MLPredictorV2()
        predictor.model = mock_model
        predictor.preprocessor = mock_preprocessor
        predictor.feature_names = ['rsi_1m']
        predictor.loaded = True
        
        with patch('optimization.predictor_v2.calculate_derived_features') as mock_fe:
            mock_fe.return_value = pd.DataFrame([mock_features])
            
            prediction = predictor.predict(mock_features)
        
        assert prediction['predicted_pnl'] == 15.5
        assert prediction['classification'] == 'win'
    
    def test_predict_very_negative_pnl(self, mock_features, mock_model, mock_preprocessor):
        """Test PNL très négatif"""
        mock_model.predict = Mock(return_value=np.array([-8.2]))
        
        predictor = MLPredictorV2()
        predictor.model = mock_model
        predictor.preprocessor = mock_preprocessor
        predictor.feature_names = ['rsi_1m']
        predictor.loaded = True
        
        with patch('optimization.predictor_v2.calculate_derived_features') as mock_fe:
            mock_fe.return_value = pd.DataFrame([mock_features])
            
            prediction = predictor.predict(mock_features)
        
        assert prediction['predicted_pnl'] == -8.2
        assert prediction['is_profitable'] is False

    def test_predict_returns_none_when_model_predict_raises(self, mock_features, mock_preprocessor):
        predictor = MLPredictorV2()

        bad_model = Mock()
        bad_model.predict = Mock(side_effect=RuntimeError('boom'))
        predictor.model = bad_model
        predictor.preprocessor = mock_preprocessor
        predictor.feature_names = ['rsi_1m']
        predictor.loaded = True

        with patch('optimization.predictor_v2.calculate_derived_features') as mock_fe:
            mock_fe.return_value = pd.DataFrame([mock_features])
            assert predictor.predict(mock_features) is None

    def test_predict_top_features_none_when_booster_fails(self, mock_features, mock_preprocessor):
        predictor = MLPredictorV2()

        model = Mock()
        model.predict = Mock(return_value=np.array([1.0]))
        model.get_booster = Mock(side_effect=RuntimeError('boom'))
        predictor.model = model
        predictor.preprocessor = mock_preprocessor
        predictor.feature_names = ['rsi_1m']
        predictor.loaded = True

        with patch('optimization.predictor_v2.calculate_derived_features') as mock_fe:
            mock_fe.return_value = pd.DataFrame([mock_features])
            out = predictor.predict(mock_features)

        assert out is not None
        assert out.get('top_features') is None

    def test_predict_returns_none_when_autoload_fails(self, mock_features):
        predictor = MLPredictorV2()
        predictor.loaded = False
        with patch.object(predictor, 'load_from_postgres', return_value=False):
            assert predictor.predict(mock_features) is None

    def test_predict_extracts_top_features_when_booster_available(self, mock_features, mock_model, mock_preprocessor):
        predictor = MLPredictorV2()
        predictor.model = mock_model
        predictor.preprocessor = mock_preprocessor
        predictor.feature_names = ['rsi_1m']
        predictor.loaded = True

        with patch('optimization.predictor_v2.calculate_derived_features') as mock_fe:
            mock_fe.return_value = pd.DataFrame([mock_features])
            out = predictor.predict(mock_features)

        assert out is not None
        assert 'top_features' in out
        assert out['top_features'] is not None
        assert len(out['top_features']) >= 1

    def test_confidence_interval_uses_99pct_z_score(self, mock_features, mock_model, mock_preprocessor, mock_metadata):
        predictor = MLPredictorV2()
        predictor.model = mock_model
        predictor.preprocessor = mock_preprocessor
        predictor.metadata = mock_metadata
        predictor.feature_names = ['rsi_1m']
        predictor.loaded = True

        with patch('optimization.predictor_v2.calculate_derived_features') as mock_fe:
            mock_fe.return_value = pd.DataFrame([mock_features])
            interval_95 = predictor.get_confidence_interval(mock_features, confidence_level=0.95)
            interval_99 = predictor.get_confidence_interval(mock_features, confidence_level=0.99)

        assert interval_95 is not None
        assert interval_99 is not None
        width_95 = interval_95[1] - interval_95[0]
        width_99 = interval_99[1] - interval_99[0]
        assert width_99 > width_95


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=optimization.predictor_v2", "--cov-report=term-missing"])
