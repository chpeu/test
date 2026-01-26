import json

import pytest

from api.routes.ml_models import get_models_overview


@pytest.mark.asyncio
async def test_get_models_overview_returns_inactive_when_no_files(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    out = await get_models_overview()
    assert isinstance(out, dict)
    assert out["total_models"] >= 1
    assert any(m["name"] == "xgboost_v1" for m in out["models"])

    xgb = next(m for m in out["models"] if m["name"] == "xgboost_v1")
    assert xgb["is_active"] is False


@pytest.mark.asyncio
async def test_get_models_overview_reads_xgb_and_gb_metadata(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    models_dir = tmp_path / "optimization" / "saved_models"
    models_dir.mkdir(parents=True, exist_ok=True)

    (models_dir / "xgboost_v1_metadata.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "timestamp": "2025-01-01T00:00:00",
                "metrics": {"train": {"accuracy": 0.9}, "test": {"accuracy": 0.8}},
                "dataset_info": {"total_samples": 1000, "train_samples": 800, "test_samples": 200},
                "hyperparameters": {"max_depth": 3},
                "n_features": 42,
            }
        ),
        encoding="utf-8",
    )

    (models_dir / "best_classifier_metadata.json").write_text(
        json.dumps(
            {
                "timestamp": "2025-01-02T00:00:00",
                "model_type": "GradientBoostingClassifier",
                "n_samples": 500,
                "n_features": 20,
                "feature_names": ["f" + str(i) for i in range(20)],
                "metrics": {
                    "train_accuracy": 0.88,
                    "test_accuracy": 0.84,
                    "cv_accuracy_mean": 0.83,
                    "cv_accuracy_std": 0.02,
                    "cv_f1_mean": 0.81,
                    "f1_score": 0.82,
                    "precision": 0.79,
                    "overfitting": 0.04,
                },
                "params": {"n_estimators": 200},
            }
        ),
        encoding="utf-8",
    )

    out = await get_models_overview()
    assert isinstance(out, dict)
    assert out["total_models"] >= 2

    names = [m["name"] for m in out["models"]]
    assert "xgboost_v1" in names
    assert "best_classifier" in names

    gb = next(m for m in out["models"] if m["name"] == "best_classifier")
    assert gb["is_active"] is True
    assert gb["feature_count"] == 20
    assert gb["metrics"]["test"]["accuracy"] == pytest.approx(0.84)
    assert gb["metrics"]["train"]["accuracy"] == pytest.approx(0.88)

    # Active model should prefer GB when present
    assert out["active_model"] == "best_classifier"
