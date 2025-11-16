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
