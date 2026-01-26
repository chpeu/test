import math

import numpy as np
import pandas as pd
import pytest

from optimization.scanner_ml_integration import (
    calculate_atr,
    calculate_bollinger_bands,
    calculate_macd,
    calculate_rsi,
    calculate_technical_indicators,
)


def _make_prices(n: int = 60, start: float = 100.0, step: float = 0.1) -> pd.Series:
    return pd.Series([start + i * step for i in range(n)], dtype=float)


def test_calculate_rsi_returns_float_and_reasonable_range_for_uptrend():
    prices = _make_prices(80, start=100.0, step=0.2)
    rsi = calculate_rsi(prices, period=14)
    assert isinstance(rsi, float)
    assert 0.0 <= rsi <= 100.0


def test_calculate_rsi_returns_default_on_nan_series():
    prices = pd.Series([np.nan] * 40)
    rsi = calculate_rsi(prices, period=14)
    assert isinstance(rsi, float)
    assert rsi == pytest.approx(50.0)


def test_calculate_macd_returns_dict_with_expected_keys():
    prices = _make_prices(80, start=100.0, step=0.05)
    out = calculate_macd(prices)
    assert set(out.keys()) == {"macd", "signal", "histogram"}
    assert all(isinstance(out[k], float) for k in out)


def test_calculate_bollinger_bands_returns_distances_and_width():
    prices = _make_prices(60, start=100.0, step=0.0)
    out = calculate_bollinger_bands(prices, period=20, std_dev=2)

    assert set(out.keys()) == {
        "upper",
        "middle",
        "lower",
        "width",
        "distance_to_upper",
        "distance_to_lower",
    }
    assert all(isinstance(out[k], float) for k in out)


def test_calculate_atr_returns_float():
    df = pd.DataFrame(
        {
            "high": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24],
            "low": [9, 9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5, 17.5, 18.5, 19.5, 20.5, 21.5, 22.5],
            "close": [9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5, 17.5, 18.5, 19.5, 20.5, 21.5, 22.5, 23.5],
        }
    )

    atr = calculate_atr(df, period=14)
    assert isinstance(atr, float)
    assert atr >= 0.0


def _make_klines(n: int = 60) -> list:
    # [[timestamp, open, high, low, close, volume], ...]
    klines = []
    base_ts = 1700000000000
    price = 100.0
    for i in range(n):
        o = price
        c = price + (0.1 if i % 2 == 0 else -0.05)
        h = max(o, c) + 0.2
        l = min(o, c) - 0.2
        v = 1000 + i
        klines.append([base_ts + i * 60_000, o, h, l, c, v])
        price = c
    return klines


def test_calculate_technical_indicators_returns_features_dict_and_no_nan_inf():
    features = calculate_technical_indicators(_make_klines(60), symbol="TEST/USDT")
    assert isinstance(features, dict)
    assert "rsi_1m" in features
    assert "macd_momentum_1m" in features
    assert "bb_width_1m" in features
    assert "atr_pct_1m" in features
    assert "volume_ratio_5m" in features

    for k, v in features.items():
        assert isinstance(v, (int, float, bool)), f"{k} should be scalar, got {type(v)}"
        if isinstance(v, bool):
            continue
        assert not math.isnan(float(v))
        assert not math.isinf(float(v))


def test_calculate_technical_indicators_returns_none_when_not_enough_klines():
    assert calculate_technical_indicators(_make_klines(10), symbol="TEST/USDT") is None
