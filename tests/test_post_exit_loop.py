import os
import sys
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.callbacks.post_exit_loop as pel


class _DummyPostExitManager:
    def __init__(self, symbols):
        self._symbols = list(symbols)
        self.calls = []
        self._event = None

    def get_active_symbols(self):
        return list(self._symbols)

    def on_price_update_sync(self, symbol, price):
        self.calls.append((symbol, price))
        if self._event is not None:
            self._event.set()


@pytest.fixture(autouse=True)
def _reset_post_exit_loop_globals():
    pel._price_provider = None
    pel._is_running = False
    pel._task = None
    pel._started_event = None
    if hasattr(pel.post_exit_loop, "_iteration_count"):
        delattr(pel.post_exit_loop, "_iteration_count")
    yield
    pel._price_provider = None
    pel._is_running = False
    pel._task = None
    pel._started_event = None


@pytest.mark.asyncio
async def test_post_exit_loop_extracts_price_from_dict(monkeypatch: pytest.MonkeyPatch):
    mgr = _DummyPostExitManager(["BTC/USDT"])
    mgr._event = pel.asyncio.Event()

    import core.post_exit as post_exit

    monkeypatch.setattr(post_exit, "get_post_exit_manager", lambda: mgr)
    monkeypatch.setattr(pel, "POST_EXIT_LOOP_INTERVAL_SEC", 0.0)

    price_provider = AsyncMock()
    price_provider.get_price = AsyncMock(return_value={"lastPrice": "123.45"})
    pel.set_price_provider(price_provider)

    task = pel.asyncio.create_task(pel.post_exit_loop())

    await pel.asyncio.wait_for(mgr._event.wait(), timeout=1.0)

    pel._is_running = False
    await pel.asyncio.sleep(0)

    if not task.done():
        task.cancel()
    try:
        await task
    except pel.asyncio.CancelledError:
        pass

    assert mgr.calls == [("BTC/USDT", 123.45)]


@pytest.mark.asyncio
async def test_post_exit_loop_extracts_price_from_float(monkeypatch: pytest.MonkeyPatch):
    mgr = _DummyPostExitManager(["BTC/USDT"])
    mgr._event = pel.asyncio.Event()

    import core.post_exit as post_exit

    monkeypatch.setattr(post_exit, "get_post_exit_manager", lambda: mgr)
    monkeypatch.setattr(pel, "POST_EXIT_LOOP_INTERVAL_SEC", 0.0)

    price_provider = AsyncMock()
    price_provider.get_price = AsyncMock(return_value=456.0)
    pel.set_price_provider(price_provider)

    task = pel.asyncio.create_task(pel.post_exit_loop())
    await pel.asyncio.wait_for(mgr._event.wait(), timeout=1.0)

    pel._is_running = False
    await pel.asyncio.sleep(0)

    if not task.done():
        task.cancel()
    try:
        await task
    except pel.asyncio.CancelledError:
        pass

    assert mgr.calls == [("BTC/USDT", 456.0)]


@pytest.mark.asyncio
async def test_post_exit_loop_handles_missing_price_provider(monkeypatch: pytest.MonkeyPatch):
    mgr = _DummyPostExitManager(["BTC/USDT"])

    import core.post_exit as post_exit

    monkeypatch.setattr(post_exit, "get_post_exit_manager", lambda: mgr)
    monkeypatch.setattr(pel, "POST_EXIT_LOOP_INTERVAL_SEC", 0.0)

    pel.set_price_provider(None)

    task = pel.asyncio.create_task(pel.post_exit_loop())
    await pel.asyncio.sleep(0)

    pel._is_running = False
    await pel.asyncio.sleep(0)

    if not task.done():
        task.cancel()
    try:
        await task
    except pel.asyncio.CancelledError:
        pass

    assert mgr.calls == []


@pytest.mark.asyncio
async def test_start_and_stop_post_exit_loop(monkeypatch: pytest.MonkeyPatch):
    mgr = _DummyPostExitManager([])

    import core.post_exit as post_exit

    monkeypatch.setattr(post_exit, "get_post_exit_manager", lambda: mgr)
    monkeypatch.setattr(pel, "POST_EXIT_LOOP_INTERVAL_SEC", 0.0)

    price_provider = AsyncMock()
    price_provider.get_price = AsyncMock(return_value=None)
    pel.set_price_provider(price_provider)

    await pel.start_post_exit_loop()
    assert pel.is_running() is True

    await pel.stop_post_exit_loop()
    assert pel.is_running() is False


@pytest.mark.asyncio
async def test_start_post_exit_loop_timeout_does_not_raise(monkeypatch: pytest.MonkeyPatch):
    mgr = _DummyPostExitManager([])

    import core.post_exit as post_exit

    monkeypatch.setattr(post_exit, "get_post_exit_manager", lambda: mgr)
    monkeypatch.setattr(pel, "POST_EXIT_LOOP_INTERVAL_SEC", 0.0)

    async def _fake_wait_for(awaitable, timeout=None):
        raise pel.asyncio.TimeoutError

    monkeypatch.setattr(pel.asyncio, "wait_for", _fake_wait_for)

    price_provider = AsyncMock()
    price_provider.get_price = AsyncMock(return_value=None)
    pel.set_price_provider(price_provider)

    await pel.start_post_exit_loop()
    assert pel._task is not None

    await pel.stop_post_exit_loop()
