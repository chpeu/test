import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.btc_indicator import BTCIndicator, BTCStatus, BTCTrend, get_btc_indicator


class _DummyExchange:
    def __init__(self, ticker=None, ohlcv=None, raise_fetch_ohlcv=False):
        self._ticker = ticker
        self._ohlcv = ohlcv
        self._raise_fetch_ohlcv = raise_fetch_ohlcv

    def fetch_ticker(self, symbol):
        return self._ticker

    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None):
        if self._raise_fetch_ohlcv:
            raise RuntimeError("ohlcv failed")
        return self._ohlcv


@pytest.fixture()
def _patched_config(monkeypatch: pytest.MonkeyPatch):
    import utils.config_persistence as cfg

    values = {
        "market_regime_btc_indicator_enabled": True,
        "market_regime_btc_volatile_threshold_1h": 2.0,
        "market_regime_btc_trend_threshold_24h": 5.0,
        "market_regime_btc_force_volatile_enabled": True,
    }

    def _get_config_value(key, default=None):
        return values.get(key, default)

    monkeypatch.setattr(cfg, "get_config_value", _get_config_value)
    return values


@pytest.mark.asyncio
async def test_get_btc_status_returns_none_when_feature_disabled(monkeypatch: pytest.MonkeyPatch):
    import utils.config_persistence as cfg

    monkeypatch.setattr(cfg, "get_config_value", lambda key, default=None: False)

    ind = BTCIndicator()
    ind._exchange = _DummyExchange(ticker={"last": 50000, "percentage": 1.0}, ohlcv=[])
    monkeypatch.setattr(ind, "_run_sync", lambda func, *args: func(*args))

    assert await ind.get_btc_status() is None


@pytest.mark.asyncio
async def test_get_btc_status_computes_pct_1h_and_trend(_patched_config, monkeypatch: pytest.MonkeyPatch):
    ind = BTCIndicator()

    ticker = {"last": 100.0, "percentage": 6.0}
    ohlcv = [
        [0, 0, 0, 0, 90.0, 0],
        [0, 0, 0, 0, 95.0, 0],
    ]
    ind._exchange = _DummyExchange(ticker=ticker, ohlcv=ohlcv)

    async def _run_sync(func, *args):
        return func(*args)

    monkeypatch.setattr(ind, "_run_sync", _run_sync)

    status = await ind.get_btc_status(force_refresh=True)
    assert isinstance(status, BTCStatus)
    assert status.price == 100.0
    assert status.pct_change_24h == 6.0
    assert status.pct_change_1h == pytest.approx(((100.0 - 90.0) / 90.0) * 100, abs=0.05)
    assert status.is_volatile is True
    assert status.trend == BTCTrend.BULLISH

    d = status.to_dict()
    assert d["trend"] == "BULLISH"


@pytest.mark.asyncio
async def test_get_btc_status_falls_back_to_cached_on_fetch_error(_patched_config, monkeypatch: pytest.MonkeyPatch):
    ind = BTCIndicator()

    ind.last_status = BTCStatus(
        price=1.0,
        pct_change_1h=0.0,
        pct_change_24h=0.0,
        is_volatile=False,
        trend=BTCTrend.RANGING,
        timestamp=pytest.importorskip("datetime").datetime.now(),
    )

    async def _boom():
        raise RuntimeError("fetch failed")

    monkeypatch.setattr(ind, "_fetch_btc_data", _boom)

    status = await ind.get_btc_status(force_refresh=True)
    assert status is ind.last_status


@pytest.mark.asyncio
async def test_get_btc_status_uses_cache_when_recent(_patched_config, monkeypatch: pytest.MonkeyPatch):
    from datetime import datetime, timedelta

    ind = BTCIndicator()
    cached = BTCStatus(
        price=100.0,
        pct_change_1h=1.0,
        pct_change_24h=2.0,
        is_volatile=False,
        trend=BTCTrend.RANGING,
        timestamp=datetime.now(),
    )
    ind.last_status = cached
    ind.last_fetch = datetime.now() - timedelta(minutes=1)

    called = {"fetch": 0}

    async def _fetch():
        called["fetch"] += 1
        return None

    monkeypatch.setattr(ind, "_fetch_btc_data", _fetch)

    status = await ind.get_btc_status(force_refresh=False)
    assert status is cached
    assert called["fetch"] == 0


@pytest.mark.asyncio
async def test_get_btc_status_force_refresh_ignores_cache(_patched_config, monkeypatch: pytest.MonkeyPatch):
    from datetime import datetime, timedelta

    ind = BTCIndicator()
    ind.last_status = BTCStatus(
        price=100.0,
        pct_change_1h=0.0,
        pct_change_24h=0.0,
        is_volatile=False,
        trend=BTCTrend.RANGING,
        timestamp=datetime.now(),
    )
    ind.last_fetch = datetime.now() - timedelta(minutes=1)

    new_status = BTCStatus(
        price=101.0,
        pct_change_1h=0.0,
        pct_change_24h=0.0,
        is_volatile=False,
        trend=BTCTrend.RANGING,
        timestamp=datetime.now(),
    )

    async def _fetch():
        return new_status

    monkeypatch.setattr(ind, "_fetch_btc_data", _fetch)

    status = await ind.get_btc_status(force_refresh=True)
    assert status is new_status


def test_should_force_volatile(_patched_config):
    ind = BTCIndicator()
    ind.last_status = BTCStatus(
        price=100.0,
        pct_change_1h=3.0,
        pct_change_24h=0.0,
        is_volatile=True,
        trend=BTCTrend.RANGING,
        timestamp=pytest.importorskip("datetime").datetime.now(),
    )

    assert ind.should_force_volatile("CALME") is True
    assert ind.should_force_volatile("VOLATILE") is False


def test_get_regime_confidence_boost():
    ind = BTCIndicator()

    assert ind.get_regime_confidence_boost("VOLATILE") == 0.0

    ind.last_status = BTCStatus(
        price=100.0,
        pct_change_1h=3.0,
        pct_change_24h=0.0,
        is_volatile=True,
        trend=BTCTrend.RANGING,
        timestamp=pytest.importorskip("datetime").datetime.now(),
    )
    assert ind.get_regime_confidence_boost("VOLATILE") == 0.1
    assert ind.get_regime_confidence_boost("CALME") == -0.15

    ind.last_status = BTCStatus(
        price=100.0,
        pct_change_1h=0.2,
        pct_change_24h=0.0,
        is_volatile=False,
        trend=BTCTrend.RANGING,
        timestamp=pytest.importorskip("datetime").datetime.now(),
    )
    assert ind.get_regime_confidence_boost("CALME") == 0.1


def test_get_btc_indicator_singleton():
    a = get_btc_indicator()
    b = get_btc_indicator()
    assert a is b
