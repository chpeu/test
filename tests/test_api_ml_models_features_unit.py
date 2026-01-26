import pytest
import pandas as pd

from api.routes import ml_models


@pytest.mark.asyncio
async def test_get_feature_importance_returns_400_when_not_enough_trades(monkeypatch):
    def _fake_get_trades_count():
        return 10

    monkeypatch.setattr(ml_models, "pd", pd)
    monkeypatch.setattr(
        "optimization.data.feature_loader.get_trades_count", _fake_get_trades_count, raising=False
    )

    # load_features_from_postgres / calculate_derived_features never called due to early HTTPException
    with pytest.raises(Exception) as exc:
        await ml_models.get_feature_importance(method="correlation", n_features=5, min_trades=30)

    # FastAPI HTTPException type
    assert getattr(exc.value, "status_code", None) == 400


@pytest.mark.asyncio
async def test_get_feature_importance_correlation_happy_path(monkeypatch):
    def _fake_get_trades_count():
        return 200

    def _fake_load_features_from_postgres(min_trades=30):
        return pd.DataFrame(
            {
                "target_win": [0, 1, 0, 1, 1],
                "f1": [1, 2, 3, 4, 5],
                "f2": [5, 4, 3, 2, 1],
            }
        )

    def _fake_calculate_derived_features(df):
        return df

    def _fake_select_top_features(df, target_col="target_win", n_features=20, method="correlation"):
        return ["f1", "f2"]

    monkeypatch.setattr("optimization.data.feature_loader.get_trades_count", _fake_get_trades_count, raising=False)
    monkeypatch.setattr("optimization.data.feature_loader.load_features_from_postgres", _fake_load_features_from_postgres, raising=False)
    monkeypatch.setattr("optimization.data.feature_engineering.calculate_derived_features", _fake_calculate_derived_features, raising=False)
    monkeypatch.setattr("optimization.data.feature_engineering.select_top_features", _fake_select_top_features, raising=False)

    out = await ml_models.get_feature_importance(method="correlation", n_features=2, min_trades=30)
    assert out["method"] == "correlation"
    assert out["trades_count"] == 5
    assert isinstance(out["features"], list)
    assert len(out["features"]) == 2
    assert out["features"][0]["rank"] == 1
    assert out["features"][0]["name"] in {"f1", "f2"}


@pytest.mark.asyncio
async def test_get_feature_importance_mutual_info_sets_importance_zero(monkeypatch):
    def _fake_get_trades_count():
        return 200

    def _fake_load_features_from_postgres(min_trades=30):
        return pd.DataFrame(
            {
                "target_win": [0, 1, 0, 1, 1],
                "f1": [1, 2, 3, 4, 5],
                "f2": [5, 4, 3, 2, 1],
            }
        )

    def _fake_calculate_derived_features(df):
        return df

    def _fake_select_top_features(df, target_col="target_win", n_features=20, method="correlation"):
        return ["f1"]

    monkeypatch.setattr("optimization.data.feature_loader.get_trades_count", _fake_get_trades_count, raising=False)
    monkeypatch.setattr("optimization.data.feature_loader.load_features_from_postgres", _fake_load_features_from_postgres, raising=False)
    monkeypatch.setattr("optimization.data.feature_engineering.calculate_derived_features", _fake_calculate_derived_features, raising=False)
    monkeypatch.setattr("optimization.data.feature_engineering.select_top_features", _fake_select_top_features, raising=False)

    out = await ml_models.get_feature_importance(method="mutual_info", n_features=1, min_trades=30)
    assert out["method"] == "mutual_info"
    assert out["features"][0]["importance"] == 0.0


@pytest.mark.asyncio
async def test_get_correlation_matrix_happy_path(monkeypatch):
    def _fake_load_features_from_postgres(min_trades=30):
        return pd.DataFrame(
            {
                "target_win": [0, 1, 0, 1, 1],
                "f1": [1, 2, 3, 4, 5],
                "f2": [5, 4, 3, 2, 1],
                "f3": [2, 2, 2, 2, 2],
            }
        )

    def _fake_calculate_derived_features(df):
        return df

    def _fake_select_top_features(df, n_features=15, method="correlation"):
        return ["f1", "f2"]

    monkeypatch.setattr("optimization.data.feature_loader.load_features_from_postgres", _fake_load_features_from_postgres, raising=False)
    monkeypatch.setattr("optimization.data.feature_engineering.calculate_derived_features", _fake_calculate_derived_features, raising=False)
    monkeypatch.setattr("optimization.data.feature_engineering.select_top_features", _fake_select_top_features, raising=False)

    out = await ml_models.get_correlation_matrix(n_features=2, min_trades=30)
    assert out["features"] == ["f1", "f2"]
    assert out["trades_count"] == 5
    assert isinstance(out["matrix"], list)
    # 2x2 matrix => 4 entries
    assert len(out["matrix"]) == 4
