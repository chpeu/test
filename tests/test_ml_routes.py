"""Tests covering the ML API endpoints to boost coverage."""

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.ml import router as ml_router
import optimization.data.feature_loader as feature_loader


def _test_client() -> TestClient:
    """Create a FastAPI test client mounting the ML router."""
    app = FastAPI()
    app.include_router(ml_router)
    return TestClient(app)


def test_ml_dashboard_stats(monkeypatch):
    """/api/ml/dashboard/stats returns readiness when data loaders succeed."""

    monkeypatch.setattr(feature_loader, "get_trades_count", lambda completed_only=True: 120)
    monkeypatch.setattr(
        feature_loader,
        "get_ml_readiness",
        lambda: {
            "xgboost": {"ready": True, "confidence": "medium"},
            "gru": {"ready": False},
        },
    )
    monkeypatch.setattr(
        feature_loader,
        "get_feature_statistics",
        lambda timeframe_days=30: {
            "total_scans": 100,
            "completed_trades": 80,
            "win_rate": 0.55,
        },
    )

    client = _test_client()
    response = client.get("/api/ml/dashboard/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trades_count"] == 120
    assert payload["readiness"]["xgboost"]["ready"] is True
    assert payload["feature_stats"]["total_scans"] == 100


def test_ml_data_quality(monkeypatch):
    """/api/ml/dashboard/data_quality handles dataframe stats."""

    monkeypatch.setattr(feature_loader, "get_trades_count", lambda completed_only=True: 20)

    sample_df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=5, freq="H"),
            "symbol": ["BTC"] * 5,
            "target_win": [True, False, True, True, False],
            "target_pnl": [0.5, -0.2, 0.3, 0.4, -0.1],
        }
    )

    monkeypatch.setattr(
        feature_loader,
        "load_features_from_postgres",
        lambda min_trades=10, timeframe_days=30, **kwargs: sample_df,
    )

    client = _test_client()
    response = client.get("/api/ml/dashboard/data_quality")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trades_count"] == len(sample_df)
    assert payload["status"] in {"good", "acceptable", "poor"}
