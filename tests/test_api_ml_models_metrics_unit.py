import json

import pytest

from api.routes.ml_models import get_model_metrics


@pytest.mark.asyncio
async def test_get_model_metrics_404_when_missing(monkeypatch):
    # Force os.path.exists -> False
    monkeypatch.setattr("os.path.exists", lambda _p: False, raising=False)

    with pytest.raises(Exception) as exc:
        await get_model_metrics("missing_model")

    assert getattr(exc.value, "status_code", None) == 404


@pytest.mark.asyncio
async def test_get_model_metrics_builds_default_feature_importance_when_missing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    models_dir = tmp_path / "optimization" / "saved_models"
    models_dir.mkdir(parents=True, exist_ok=True)

    metadata_path = models_dir / "xgboost_v1_metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "model_type": "XGBClassifier",
                "version": "1.0",
                "training_info": {
                    "trained_at": "2025-01-01",
                    "total_samples": 50,
                    "train_samples": 40,
                    "test_samples": 10,
                    "timeframe_days": 10,
                    "training_time_seconds": 12.34,
                },
                "metrics": {"train": {"accuracy": 0.8}, "test": {"accuracy": 0.6}},
                "feature_names": ["f1", "f2", "f3"],
            }
        ),
        encoding="utf-8",
    )

    # Ensure existence check returns True for our file
    monkeypatch.setattr("os.path.exists", lambda p: str(p).endswith("xgboost_v1_metadata.json"), raising=False)

    out = await get_model_metrics("xgboost_v1")
    assert out["model_name"] == "xgboost_v1"
    assert isinstance(out["top_features"], list)
    assert len(out["top_features"]) > 0
    assert out["top_features"][0]["feature"] in {"f1", "f2", "f3"}

    # Recommendations should exist
    assert isinstance(out["recommendations"], list)
    assert len(out["recommendations"]) > 0
