from api.routes.ml_models import _generate_recommendations


def test_generate_recommendations_success_when_everything_good():
    recs = _generate_recommendations(test_acc=0.9, overfitting_gap=0.01, total_samples=500, zero_importance_count=0)
    assert isinstance(recs, list)
    assert recs
    assert recs[0]["type"] in {"success", "data", "model", "performance", "features"}


def test_generate_recommendations_flags_small_dataset():
    recs = _generate_recommendations(test_acc=0.9, overfitting_gap=0.01, total_samples=50, zero_importance_count=0)
    assert any(r["type"] == "data" for r in recs)


def test_generate_recommendations_flags_overfitting():
    recs = _generate_recommendations(test_acc=0.9, overfitting_gap=0.25, total_samples=500, zero_importance_count=0)
    assert any(r["type"] == "model" for r in recs)


def test_generate_recommendations_flags_low_performance():
    recs = _generate_recommendations(test_acc=0.5, overfitting_gap=0.01, total_samples=500, zero_importance_count=0)
    assert any(r["type"] == "performance" for r in recs)


def test_generate_recommendations_flags_many_zero_importance_features():
    recs = _generate_recommendations(test_acc=0.9, overfitting_gap=0.01, total_samples=500, zero_importance_count=100)
    assert any(r["type"] == "features" for r in recs)
