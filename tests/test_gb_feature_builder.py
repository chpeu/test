import math
from types import SimpleNamespace

import pytest

from optimization import gb_feature_builder


def test_build_gb_features_returns_all_expected_keys():
    features = gb_feature_builder.build_gb_features(best_setup={}, analysis={}, scalability_data={})
    assert isinstance(features, dict)
    assert set(features.keys()) == set(gb_feature_builder.GB_FEATURE_NAMES)
    assert len(features) == len(gb_feature_builder.GB_FEATURE_NAMES)

    # Valeurs: floats et jamais NaN/inf
    for value in features.values():
        assert isinstance(value, float)
        assert not math.isnan(value)
        assert not math.isinf(value)


def test_build_gb_features_computes_fallbacks_and_derivations():
    # Prix + BB
    best_setup = {
        "price": 100.0,
        "indicators_1m": {
            "di_plus": 30.0,
            "di_minus": 10.0,
            "rsi": 55.0,
            "rsi_prev": 50.0,
            "bb_lower": 90.0,
            "bb_upper": 110.0,
            "ema9": 101.0,
            "ema21": 100.0,
        },
        "indicators_5m": {
            "bb_lower": 80.0,
            "bb_upper": 120.0,
            "macd_hist": 0.1,
            "atr_pct": 0.25,
            "di_plus": 22.0,
            "di_minus": 12.0,
            "volume_ratio": 1.7,
        },
    }

    scalability_data = {
        "bid_vol": 120.0,
        "ask_vol": 100.0,
    }

    features = gb_feature_builder.build_gb_features(best_setup=best_setup, analysis={}, scalability_data=scalability_data)

    # DI gap 1m dérivé de di_plus - di_minus
    assert features.get("di_minus_1m") == pytest.approx(10.0)
    assert features.get("di_gap_1m") == pytest.approx(20.0)

    # BB distances 5m dérivées (price=100)
    # distance_to_lower = 100 - 80 = 20
    # distance_to_upper = 120 - 100 = 20
    assert features.get("bb_distance_to_lower_5m") == pytest.approx(20.0)
    assert features.get("bb_distance_to_upper_5m") == pytest.approx(20.0)

    # EMA diff pct 1m dérivé de ema9/ema21 * 100
    assert features.get("ema_diff_pct_1m") == pytest.approx(1.0)

    # EMA trend strength 1m fallback abs(ema_diff_pct_1m)
    assert features.get("ema_trend_strength_1m") == pytest.approx(1.0)

    # RSI prev + RSI change
    assert features.get("rsi_prev_1m") == pytest.approx(50.0)
    assert features.get("rsi_change_1m") == pytest.approx(5.0)

    # delta volume dérivé bid - ask
    assert features.get("delta_volume") == pytest.approx(20.0)


def test_build_gb_features_handles_non_dict_inputs():
    # Doit être robuste même si on passe n'importe quoi
    features = gb_feature_builder.build_gb_features(best_setup=None, analysis=None, scalability_data=None)
    assert isinstance(features, dict)
    assert set(features.keys()) == set(gb_feature_builder.GB_FEATURE_NAMES)
