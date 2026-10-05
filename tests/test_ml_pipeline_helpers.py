import pandas as pd
import pytest

from optimization import ml_pipeline


def test_split_training_dataset_stratify_preserves_class_ratio():
    X = pd.DataFrame({"a": range(100), "b": range(100, 200)})
    # 30% positives
    y = pd.Series(([1] * 30) + ([0] * 70))

    X_train, X_test, y_train, y_test = ml_pipeline.split_training_dataset(
        X,
        y,
        test_size=0.25,
        random_state=123,
        stratify=True,
    )

    assert len(X_train) + len(X_test) == len(X)
    assert len(y_train) + len(y_test) == len(y)

    # ratio approx preserved
    assert y_test.mean() == pytest.approx(y.mean(), abs=0.05)
    assert y_train.mean() == pytest.approx(y.mean(), abs=0.05)


def test_split_training_dataset_no_stratify_runs():
    X = pd.DataFrame({"a": range(20)})
    y = pd.Series([0, 1] * 10)

    X_train, X_test, y_train, y_test = ml_pipeline.split_training_dataset(
        X,
        y,
        test_size=0.3,
        random_state=0,
        stratify=False,
    )

    assert len(X_train) == len(y_train)
    assert len(X_test) == len(y_test)


def test_compute_class_weights_calls_handle_class_imbalance(monkeypatch):
    calls = {}

    def _fake_handle(y, strategy="auto"):
        calls["strategy"] = strategy
        calls["len"] = len(y)
        return {0: 1.0, 1: 2.5}

    monkeypatch.setattr(ml_pipeline, "handle_class_imbalance", _fake_handle)

    y = pd.Series([0, 1, 0, 0, 1, 1, 0])
    weights = ml_pipeline.compute_class_weights(y, strategy="balanced")

    assert weights == {0: 1.0, 1: 2.5}
    assert calls["strategy"] == "balanced"
    assert calls["len"] == len(y)
