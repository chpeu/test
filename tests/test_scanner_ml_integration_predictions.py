import pytest

from optimization import scanner_ml_integration


def _make_klines(n: int = 60) -> list:
    klines = []
    base_ts = 1700000000000
    price = 100.0
    for i in range(n):
        o = price
        c = price + 0.1
        h = c + 0.2
        l = o - 0.2
        v = 1000 + i
        klines.append([base_ts + i * 60_000, o, h, l, c, v])
        price = c
    return klines


@pytest.mark.asyncio
async def test_get_ml_prediction_for_opportunity_returns_none_when_no_features(monkeypatch):
    monkeypatch.setattr(scanner_ml_integration, "calculate_technical_indicators", lambda _k, _s: None)
    out = await scanner_ml_integration.get_ml_prediction_for_opportunity(_make_klines(60), "TEST/USDT")
    assert out is None


@pytest.mark.asyncio
async def test_get_ml_prediction_for_opportunity_uses_optimized_path(monkeypatch):
    # Provide deterministic features
    monkeypatch.setattr(
        scanner_ml_integration,
        "calculate_technical_indicators",
        lambda _k, _s: {"price": 100.0, "indicators_1m": {}, "indicators_5m": {}},
    )

    # Patch imports inside function by patching the module attributes after import
    class _FakePredictorOptimized:
        @staticmethod
        def predict_trade(_features, threshold=0.5):
            return True, 0.77

    class _FakeGBFeatureBuilder:
        @staticmethod
        def build_gb_features(best_setup=None, analysis=None, scalability_data=None):
            return {"x": 1.0}

    monkeypatch.setattr("optimization.predictor_optimized.predict_trade", _FakePredictorOptimized.predict_trade, raising=False)
    monkeypatch.setattr("optimization.gb_feature_builder.build_gb_features", _FakeGBFeatureBuilder.build_gb_features, raising=False)

    out = await scanner_ml_integration.get_ml_prediction_for_opportunity(
        _make_klines(60),
        "TEST/USDT",
        scan_id=123,
        model_name="optimized",
    )

    assert out is not None
    assert out["prediction"] == "win"
    assert out["confidence"] == pytest.approx(0.77)
    assert out["model"] == "GradientBoosting_Optimized"
    assert out["symbol"] == "TEST/USDT"
    assert out["scan_id"] == 123
    assert isinstance(out["features"], dict)


def test_should_filter_setup_with_ml_v2_returns_false_when_no_features(monkeypatch):
    monkeypatch.setattr(scanner_ml_integration, "calculate_technical_indicators", lambda _k, _s: None)
    should_reject, reason = scanner_ml_integration.should_filter_setup_with_ml_v2(_make_klines(60), "TEST/USDT")
    assert should_reject is False
    assert reason is None


def test_should_filter_setup_with_ml_v2_uses_predictor(monkeypatch):
    monkeypatch.setattr(
        scanner_ml_integration,
        "calculate_technical_indicators",
        lambda _k, _s: {"rsi_1m": 50.0},
    )

    class _FakePredictor:
        def should_reject_trade(self, features, min_expected_pnl=0.3):
            assert isinstance(features, dict)
            return True, 0.1, "too_low"

    monkeypatch.setattr("optimization.predictor_v2.get_predictor_v2", lambda: _FakePredictor(), raising=False)

    should_reject, reason = scanner_ml_integration.should_filter_setup_with_ml_v2(
        _make_klines(60),
        "TEST/USDT",
        min_expected_pnl=0.3,
    )

    assert should_reject is True
    assert reason == "too_low"
