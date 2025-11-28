"""Tests pour les endpoints de prédictions ML."""
import pytest

from fastapi.testclient import TestClient

import optimization.prediction_logger as prediction_logger


@pytest.fixture
def predictions_data():
    return {
        "analytics": {
            "total_predictions": 42,
            "evaluated": 30,
            "accuracy_pct": 66.6,
        },
        "best_symbols": [
            {"symbol": "BTCUSDT", "accuracy_pct": 70.0},
            {"symbol": "ETHUSDT", "accuracy_pct": 65.0},
        ],
    }


def test_get_predictions_analytics(client: TestClient, monkeypatch, predictions_data):
    """Vérifie que l'endpoint /predictions/analytics renvoie les données formatées."""

    def fake_get_prediction_analytics(model_name, days):
        # S'assurer que la route transmet bien les paramètres
        assert model_name == "xgboost_v1"
        assert days == 10
        return predictions_data["analytics"]

    def fake_get_best_symbols_for_ml(min_predictions):
        assert min_predictions == 3
        return predictions_data["best_symbols"]

    monkeypatch.setattr(
        prediction_logger,
        "get_prediction_analytics",
        fake_get_prediction_analytics,
    )
    monkeypatch.setattr(
        prediction_logger,
        "get_best_symbols_for_ml",
        fake_get_best_symbols_for_ml,
    )

    response = client.get("/api/ml/predictions/analytics", params={"model_name": "xgboost_v1", "days": 10})

    assert response.status_code == 200

    payload = response.json()
    assert payload["model_name"] == "xgboost_v1"
    assert payload["period_days"] == 10
    assert payload["analytics"] == predictions_data["analytics"]
    assert payload["best_symbols"] == predictions_data["best_symbols"]


def test_get_predictions_recent(client: TestClient, monkeypatch):
    """Vérifie que l'endpoint /predictions/recent renvoie les résultats mockés."""

    fake_recent = [
        {
            "id": 1,
            "symbol": "BTCUSDT",
            "prediction": "win",
            "confidence_pct": 72.5,
        },
        {
            "id": 2,
            "symbol": "ETHUSDT",
            "prediction": "loss",
            "confidence_pct": 60.0,
        },
    ]

    def fake_get_recent(limit):
        assert limit == 5
        return fake_recent

    monkeypatch.setattr(
        prediction_logger,
        "get_recent_predictions",
        fake_get_recent,
    )

    response = client.get("/api/ml/predictions/recent", params={"limit": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == len(fake_recent)
    assert payload["predictions"] == fake_recent


def test_get_alerts_history(client: TestClient, monkeypatch):
    """Vérifie que l'endpoint /alerts/history renvoie l'historique formaté."""

    fake_history = [
        {"symbol": "BTCUSDT", "prediction": "win"},
        {"symbol": "ETHUSDT", "prediction": "loss"},
    ]

    class FakeAlertManager:
        def get_alert_history(self, limit):
            assert limit == 3
            return fake_history

    def fake_get_alert_manager():
        return FakeAlertManager()

    import optimization.ml_alerts as ml_alerts

    monkeypatch.setattr(ml_alerts, "get_alert_manager", fake_get_alert_manager)

    response = client.get("/api/ml/alerts/history", params={"limit": 3})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == len(fake_history)
    assert payload["alerts"] == fake_history


def test_reload_predictor(client: TestClient, monkeypatch):
    """Vérifie que l'endpoint /predictor/reload appelle correctement le predictor."""

    class FakePredictor:
        def __init__(self):
            self.loaded = True
            self.feature_names = ["f1", "f2"]

    def fake_get_predictor(model_name):
        assert model_name == "xgboost_v2"
        return FakePredictor()

    import optimization.predictor as opt_predictor

    monkeypatch.setattr(opt_predictor, "_predictor_instance", None, raising=False)
    monkeypatch.setattr(opt_predictor, "get_predictor", fake_get_predictor)

    response = client.post("/api/ml/predictor/reload", params={"model_name": "xgboost_v2"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["features_count"] == 2


def test_alerts_test_endpoint(client: TestClient, monkeypatch):
    """Teste l'endpoint /alerts/test en mockant send_ml_alert."""

    def fake_send_ml_alert(prediction, symbol, scan_id, min_confidence, channels):
        assert symbol == "SOLUSDT"
        assert channels == ["console", "webhook"]
        return {"status": "success", "symbol": symbol}

    import optimization.ml_alerts as ml_alerts

    monkeypatch.setattr(ml_alerts, "send_ml_alert", fake_send_ml_alert)

    response = client.post(
        "/api/ml/alerts/test",
        params={"symbol": "SOLUSDT", "channels": ["console", "webhook"]}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["result"]["status"] == "success"


def test_predict_batch_endpoint(client: TestClient, monkeypatch):
    """Vérifie que /predict/batch appelle le predictor et filtre les None."""

    class FakePredictor:
        def batch_predict(self, opportunities):
            assert len(opportunities) == 2
            return [
                {"prediction": "win", "confidence": 0.8},
                None,  # Doit être filtré
            ]

    def fake_get_predictor(model_name):
        assert model_name == "xgboost_v1"
        return FakePredictor()

    import optimization.predictor as opt_predictor

    monkeypatch.setattr(opt_predictor, "get_predictor", fake_get_predictor)

    payload = {
        "opportunities": [
            {"symbol": "BTCUSDT"},
            {"symbol": "ETHUSDT"},
        ]
    }

    response = client.post(
        "/api/ml/predict/batch",
        params={"model_name": "xgboost_v1"},
        json=payload["opportunities"],
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["successful"] == 1
    assert data["failed"] == 1
    assert len(data["predictions"]) == 1


def test_retrain_check_endpoint(client: TestClient, monkeypatch):
    """Teste l'endpoint /retrain/check en mockant auto_retrain."""

    fake_check = {"retrain_needed": True, "reason": "no_model"}
    fake_schedule = {"status": "ready"}

    import optimization.auto_retrain as auto_retrain

    monkeypatch.setattr(auto_retrain, "check_retrain_needed", lambda: fake_check)
    monkeypatch.setattr(auto_retrain, "get_retrain_schedule_info", lambda: fake_schedule)

    response = client.get("/api/ml/retrain/check")

    assert response.status_code == 200
    payload = response.json()
    assert payload["retrain_check"] == fake_check
    assert payload["schedule_info"] == fake_schedule
