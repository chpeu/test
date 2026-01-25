import json
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest
from sklearn.pipeline import Pipeline

from optimization.predictor_optimized import OptimizedPredictor


class _DummyModel:
    def __init__(self, proba: float, feature_names):
        self._proba = proba
        self.feature_names_in_ = np.array(feature_names)

    def predict_proba(self, _x):
        return np.array([[1 - self._proba, self._proba]])


class _IdentityTransformer:
    def __init__(self, should_raise: bool = False):
        self._should_raise = should_raise

    def transform(self, x):
        if self._should_raise:
            raise ValueError("boom")
        return x


class _DummyScalerStep:
    def transform(self, x):
        return x


class _DummyEstimatorStep:
    def __init__(self, proba: float, feature_names):
        self._proba = proba
        self.feature_names_in_ = np.array(feature_names)

    def predict_proba(self, _x):
        return np.array([[1 - self._proba, self._proba]])


def test_predict_returns_default_when_model_not_loaded(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("optimization.predictor_optimized.Path.exists", lambda _self: False)

    predictor = OptimizedPredictor(model_path=str(tmp_path / "missing.pkl"))
    assert predictor.is_loaded is False

    should_trade, confidence = predictor.predict({"rsi_1m": 50}, threshold=0.6)
    assert should_trade is True
    assert confidence == pytest.approx(0.5)


def test_load_model_dict_preprocessor_metadata_and_predict(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    models_dir = tmp_path / "optimization" / "saved_models"
    models_dir.mkdir(parents=True, exist_ok=True)

    feature_cols = [
        "rsi_1m",
        "macd_hist_1m",
        "hour",
        "ema_trend_strength_1m",
        "unknown_feature",
    ]

    model_file = tmp_path / "model.pkl"
    model_file.write_bytes(b"x")

    metadata_file = models_dir / "model_metadata.json"
    metadata_file.write_text(
        json.dumps(
            {
                "best_model": "GradientBoostingClassifier",
                "metrics": {"test_acc": 0.66, "test_f1": 0.61},
                "timestamp": "2025-01-01",
                "feature_names": feature_cols,
            }
        ),
        encoding="utf-8",
    )

    prep_file = models_dir / "model_preprocessor.pkl"
    prep_file.write_bytes(b"x")

    dummy_model = _DummyModel(proba=0.75, feature_names=feature_cols)

    def fake_joblib_load(path):
        path_str = str(path)
        if path_str.endswith("model.pkl"):
            return {"model": dummy_model, "feature_names": feature_cols}
        if path_str.endswith("model_preprocessor.pkl"):
            return {
                "feature_names": feature_cols,
                "imputer": _IdentityTransformer(should_raise=True),
                "scaler": _IdentityTransformer(should_raise=True),
            }
        raise FileNotFoundError(path_str)

    monkeypatch.setattr("optimization.predictor_optimized.joblib.load", fake_joblib_load)

    predictor = OptimizedPredictor(model_path=str(model_file))
    assert predictor.is_loaded is True
    assert predictor.feature_cols == feature_cols
    assert isinstance(predictor.preprocessor, dict)
    assert predictor.metadata is not None

    should_trade, confidence = predictor.predict(
        {
            "timestamp": "2025-01-01T12:00:00Z",
            "rsi_1m": 60.0,
            "macd_hist_1m": 0.05,
            "ema_diff_pct_1m": -0.2,
        },
        threshold=0.6,
    )

    assert bool(should_trade) is True
    assert confidence == pytest.approx(0.75)

    batch = predictor.predict_batch([{"rsi_1m": 60.0, "macd_hist_1m": 0.05}], threshold=0.1)
    assert len(batch) == 1

    info = predictor.get_model_info()
    assert info["status"] == "loaded"
    assert info["n_features"] == len(feature_cols)


def test_predict_pipeline_converts_to_numpy_when_scaler_has_no_feature_names(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    models_dir = tmp_path / "optimization" / "saved_models"
    models_dir.mkdir(parents=True, exist_ok=True)

    feature_cols = ["rsi_1m", "macd_hist_1m"]

    model_file = tmp_path / "pipe.pkl"
    model_file.write_bytes(b"x")

    pipeline = Pipeline(
        steps=[
            ("scaler", _DummyScalerStep()),
            ("clf", _DummyEstimatorStep(proba=0.8, feature_names=feature_cols)),
        ]
    )
    pipeline.predict_proba = Mock(return_value=np.array([[0.2, 0.8]]))

    monkeypatch.setattr("optimization.predictor_optimized.joblib.load", lambda _p: pipeline)

    predictor = OptimizedPredictor(model_path=str(model_file))
    assert predictor.is_loaded is True

    predictor.predict({"rsi_1m": 50.0, "macd_hist_1m": 0.01}, threshold=0.1)

    assert pipeline.predict_proba.call_count == 1
    called_arg = pipeline.predict_proba.call_args[0][0]
    assert isinstance(called_arg, np.ndarray)


def test_prepare_features_fills_missing_expected_and_computes_derived(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    model_file = tmp_path / "model.pkl"
    model_file.write_bytes(b"x")

    feature_cols = [
        'hour',
        'day_of_week',
        'rsi_momentum',
        'macd_momentum',
        'ema_trend_strength_1m',
        'di_gap_1m',
        'momentum_1m',
        'volatility_ratio',
        'missing_feature',
    ]

    dummy_model = _DummyModel(proba=0.6, feature_names=feature_cols)

    monkeypatch.setattr(
        "optimization.predictor_optimized.joblib.load",
        lambda _p: {"model": dummy_model, "feature_names": feature_cols},
    )

    predictor = OptimizedPredictor(model_path=str(model_file))
    assert predictor.is_loaded is True
    assert predictor.feature_cols == feature_cols

    df = predictor._prepare_features(
        {
            'timestamp': '2026-01-25T12:00:00Z',
            'rsi_1m': 55.0,
            'rsi_5m': 50.0,
            'macd_hist_1m': 0.02,
            'macd_hist_5m': -0.01,
            'ema_diff_pct_1m': -0.3,
            'di_plus_1m': 20.0,
            'di_minus_1m': 10.0,
            'atr_pct_1m': 0.4,
            'atr_pct_5m': 0.2,
        }
    )

    # Filtrage strict + remplissage manquants
    assert list(df.columns) == feature_cols
    assert df.shape == (1, len(feature_cols))
    assert float(df.loc[0, 'missing_feature']) == 0.0

    # Vérifier quelques dérivées
    assert float(df.loc[0, 'rsi_momentum']) == pytest.approx(5.0)
    assert float(df.loc[0, 'macd_momentum']) == pytest.approx(0.03)
    assert float(df.loc[0, 'ema_trend_strength_1m']) == pytest.approx(0.3)
    assert float(df.loc[0, 'di_gap_1m']) == pytest.approx(10.0)
    assert float(df.loc[0, 'volatility_ratio']) == pytest.approx(0.4 / (0.2 + 1e-8))


def test_load_model_ignores_mismatching_preprocessor(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    models_dir = tmp_path / "optimization" / "saved_models"
    models_dir.mkdir(parents=True, exist_ok=True)

    model_file = tmp_path / "model.pkl"
    model_file.write_bytes(b"x")

    # Create inferred preprocessor file
    prep_file = models_dir / "model_preprocessor.pkl"
    prep_file.write_bytes(b"x")

    feature_cols = ['a', 'b']
    dummy_model = _DummyModel(proba=0.51, feature_names=feature_cols)

    def fake_joblib_load(path):
        path_str = str(path)
        if path_str.endswith('model.pkl'):
            return {'model': dummy_model, 'feature_names': feature_cols}
        if path_str.endswith('model_preprocessor.pkl'):
            # mismatch features => doit être ignoré
            return {'feature_names': ['a'], 'imputer': _IdentityTransformer(), 'scaler': _IdentityTransformer()}
        raise FileNotFoundError(path_str)

    monkeypatch.setattr('optimization.predictor_optimized.joblib.load', fake_joblib_load)

    predictor = OptimizedPredictor(model_path=str(model_file))
    assert predictor.is_loaded is True
    assert predictor.feature_cols == feature_cols
    assert predictor.preprocessor is None


def test_get_predictor_and_predict_trade_singleton(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    models_dir = tmp_path / "optimization" / "saved_models"
    models_dir.mkdir(parents=True, exist_ok=True)
    model_file = models_dir / "gradient_boosting_optimized.pkl"
    model_file.write_bytes(b"x")

    feature_cols = ['rsi_1m', 'macd_hist_1m']
    dummy_model = _DummyModel(proba=0.9, feature_names=feature_cols)

    def fake_joblib_load(path):
        path_str = str(path)
        if path_str.endswith('gradient_boosting_optimized.pkl'):
            return {'model': dummy_model, 'feature_names': feature_cols}
        raise FileNotFoundError(path_str)

    monkeypatch.setattr('optimization.predictor_optimized.joblib.load', fake_joblib_load)

    # Reset singleton
    import optimization.predictor_optimized as mod
    mod._predictor_instance = None

    p1 = mod.get_predictor()
    p2 = mod.get_predictor()
    assert p2 is p1

    should_trade, confidence = mod.predict_trade({'rsi_1m': 50.0, 'macd_hist_1m': 0.01}, threshold=0.8)
    assert bool(should_trade) is True
    assert confidence == pytest.approx(0.9)


def test_mlpredictor_alias_predict_and_info(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    models_dir = tmp_path / "optimization" / "saved_models"
    models_dir.mkdir(parents=True, exist_ok=True)
    model_file = models_dir / "gradient_boosting_optimized.pkl"
    model_file.write_bytes(b"x")

    feature_cols = ['rsi_1m', 'macd_hist_1m']
    dummy_model = _DummyModel(proba=0.7, feature_names=feature_cols)

    def fake_joblib_load(path):
        path_str = str(path)
        if path_str.endswith('gradient_boosting_optimized.pkl'):
            return {'model': dummy_model, 'feature_names': feature_cols}
        raise FileNotFoundError(path_str)

    monkeypatch.setattr('optimization.predictor_optimized.joblib.load', fake_joblib_load)

    import optimization.predictor_optimized as mod
    mod._predictor_instance = None

    alias = mod.MLPredictor()
    should_trade, confidence = alias.predict({'rsi_1m': 55.0, 'macd_hist_1m': 0.02})
    assert confidence == pytest.approx(0.7)

    info = alias.get_info()
    assert info['status'] in ['loaded', 'not_loaded']
