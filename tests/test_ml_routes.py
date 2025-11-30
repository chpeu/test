"""Tests covering the ML API endpoints to boost coverage."""

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.ml import router as ml_router
import api.routes.ml as ml_routes
import optimization.data.feature_loader as feature_loader
from optimization.data import feature_engineering


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


def test_ml_feature_importance(monkeypatch):
    """/api/ml/features/importance returns computed scores."""

    monkeypatch.setattr(feature_loader, "get_trades_count", lambda completed_only=True: 50)

    base_df = pd.DataFrame(
        {
            "target_win": [1, 0, 1, 0],
            "feat1": [0.1, 0.2, 0.3, 0.4],
            "feat2": [1.0, 2.0, 3.0, 4.0],
        }
    )

    monkeypatch.setattr(
        feature_loader,
        "load_features_from_postgres",
        lambda min_trades=30, timeframe_days=30, **_: base_df,
    )
    monkeypatch.setattr(
        feature_engineering,
        "calculate_derived_features",
        lambda df: df,
    )
    monkeypatch.setattr(
        feature_engineering,
        "select_top_features",
        lambda df, target_col="target_win", n_features=1, method="correlation": ["feat1"],
    )

    client = _test_client()
    response = client.get("/api/ml/features/importance?method=correlation&n_features=1&min_trades=30")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trades_count"] == len(base_df)
    assert payload["features"][0]["name"] == "feat1"


def test_ml_train_endpoint_background_task(monkeypatch):
    """/api/ml/train schedules background task when enough data."""

    monkeypatch.setattr(feature_loader, "get_trades_count", lambda completed_only=True: 60)

    recorded_tasks = []

    async def fake_bg(task_id, timeframe_days, min_trades):
        recorded_tasks.append({
            "task_id": task_id,
            "timeframe": timeframe_days,
            "min_trades": min_trades,
        })

    def fake_add_task(self, func, *args, **kwargs):
        recorded_tasks.append((func, args, kwargs))

    monkeypatch.setattr(ml_routes, "_train_xgboost_background", fake_bg)
    monkeypatch.setattr(ml_routes.BackgroundTasks, "add_task", fake_add_task, raising=False)

    client = _test_client()
    response = client.post("/api/ml/train?model_type=xgboost&timeframe_days=60&min_trades=30")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pending"
    assert payload["trades_count"] == 60
    assert recorded_tasks, "Background task should be scheduled"


def test_ml_train_endpoint_insufficient_data(monkeypatch):
    """/api/ml/train returns 200 with warning when not enough trades (non-blocking)."""

    monkeypatch.setattr(feature_loader, "get_trades_count", lambda completed_only=True: 10)

    client = _test_client()
    response = client.post("/api/ml/train?model_type=xgboost&timeframe_days=60&min_trades=30")

    # Changed behavior: now returns 200 with warning instead of blocking with 400
    # Training continues but logs a warning about limited data
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") in ["started", "pending", "running"] or "task_id" in data
