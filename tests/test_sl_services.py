import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import core.position.sl_services as sl_services


class _DummyStats:
    def to_dict(self):
        return {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'winrate': 0.0,
        }


class _DummyState:
    def __init__(self, pos_mgr=None, live_order_mgr=None, ws_mgr=None):
        self._lock = asyncio.Lock()
        self._pos_mgr = pos_mgr
        self._live_order_mgr = live_order_mgr
        self._ws_mgr = ws_mgr
        self.active_position = None
        self.stats = _DummyStats()
        self.trades = []

    def lock(self, name: str):
        return self._lock

    def get_position_manager(self):
        return self._pos_mgr

    def set_active_position(self, position):
        self.active_position = position

    def add_trade(self, trade):
        self.trades.append(trade)

    def get_ws_manager(self):
        return self._ws_mgr

    def get_live_order_manager(self):
        return self._live_order_mgr


@pytest.fixture(autouse=True)
def _clear_pending_sl_tasks():
    sl_services._pending_sl_tasks.clear()
    yield
    for task in list(sl_services._pending_sl_tasks.values()):
        try:
            if hasattr(task, 'cancel'):
                task.cancel()
        except Exception:
            pass
    sl_services._pending_sl_tasks.clear()


@pytest.mark.asyncio
async def test_setup_realtime_sl_check_missing_params_returns(monkeypatch):
    state = _DummyState(pos_mgr=Mock(), ws_mgr=AsyncMock())
    monkeypatch.setattr(sl_services, 'get_state_manager', lambda: state)

    price_provider = Mock()
    position = {'symbol': 'BTCUSDT', 'direction': 'LONG', 'entry': 100.0}

    await sl_services.setup_realtime_sl_check(position, price_provider)

    price_provider.set_sl_check_callback.assert_not_called()


@pytest.mark.asyncio
async def test_setup_realtime_sl_check_callback_closes_position(monkeypatch):
    ws_mgr = AsyncMock()
    ws_mgr.emit = AsyncMock()

    pos_mgr = Mock()
    pos_mgr.active_position = object()
    pos_mgr.close_position = Mock(return_value={'symbol': 'BTCUSDT', 'pnl_percent': -0.5})

    state = _DummyState(pos_mgr=pos_mgr, ws_mgr=ws_mgr)
    state.active_position = {'symbol': 'BTCUSDT'}

    monkeypatch.setattr(sl_services, 'get_state_manager', lambda: state)

    price_provider = Mock()
    position = {'symbol': 'BTCUSDT', 'direction': 'LONG', 'sl': 99.0, 'entry': 100.0}

    await sl_services.setup_realtime_sl_check(position, price_provider)

    callback = price_provider.set_sl_check_callback.call_args.kwargs['callback']
    await callback(exit_price=99.0, reason='SL_HIT')

    pos_mgr.close_position.assert_called_once_with(exit_price=99.0, reason='SL_HIT')
    assert state.active_position is None
    assert len(state.trades) == 1
    assert 'timestamp' in state.trades[0]

    assert ws_mgr.emit.await_count == 2
    ws_mgr.emit.assert_any_await('position_closed', state.trades[0])
    ws_mgr.emit.assert_any_await('stats_update', state.stats.to_dict())

    assert price_provider.set_sl_check_callback.call_count == 2
    assert price_provider.set_sl_check_callback.call_args_list[1].args == (None,)


@pytest.mark.asyncio
async def test_setup_realtime_sl_check_callback_handles_close_error(monkeypatch):
    ws_mgr = AsyncMock()
    ws_mgr.emit = AsyncMock()

    pos_mgr = Mock()
    pos_mgr.active_position = object()
    pos_mgr.close_position = Mock(side_effect=RuntimeError('close failed'))

    state = _DummyState(pos_mgr=pos_mgr, ws_mgr=ws_mgr)
    monkeypatch.setattr(sl_services, 'get_state_manager', lambda: state)

    price_provider = Mock()
    position = {'symbol': 'BTCUSDT', 'direction': 'LONG', 'sl': 99.0, 'entry': 100.0}

    await sl_services.setup_realtime_sl_check(position, price_provider)

    callback = price_provider.set_sl_check_callback.call_args.kwargs['callback']
    await callback(exit_price=99.0, reason='SL_HIT')

    pos_mgr.close_position.assert_called_once()


@pytest.mark.asyncio
async def test_schedule_sl_order_placement_dry_run(monkeypatch):
    active_pos = SimpleNamespace(
        symbol='BTCUSDT',
        entry_fill_price=None,
        entry=100.0,
        sl=99.0,
        direction='LONG',
        sl_order_id=None,
    )
    pos_mgr = SimpleNamespace(active_position=active_pos)

    live_order_mgr = SimpleNamespace(dry_run=True)

    state = _DummyState(pos_mgr=pos_mgr, live_order_mgr=live_order_mgr)
    monkeypatch.setattr(sl_services, 'get_state_manager', lambda: state)

    await sl_services.schedule_sl_order_placement({'symbol': 'BTCUSDT'}, delay_seconds=0)

    task = sl_services._pending_sl_tasks['BTCUSDT']
    await task

    assert 'BTCUSDT' not in sl_services._pending_sl_tasks
    assert active_pos.sl_order_id is None


@pytest.mark.asyncio
async def test_schedule_sl_order_placement_success_sets_order_id(monkeypatch):
    active_pos = SimpleNamespace(
        symbol='BTCUSDT',
        entry_fill_price=101.0,
        entry=100.0,
        sl=99.0,
        direction='LONG',
        sl_order_id=None,
    )
    pos_mgr = SimpleNamespace(active_position=active_pos)

    result = SimpleNamespace(success=True, order_id='order-123', error_message=None)
    live_order_mgr = SimpleNamespace(dry_run=False, place_stop_loss_order=AsyncMock(return_value=result))

    state = _DummyState(pos_mgr=pos_mgr, live_order_mgr=live_order_mgr)
    monkeypatch.setattr(sl_services, 'get_state_manager', lambda: state)

    await sl_services.schedule_sl_order_placement({'symbol': 'BTCUSDT'}, delay_seconds=0)

    task = sl_services._pending_sl_tasks['BTCUSDT']
    await task

    live_order_mgr.place_stop_loss_order.assert_awaited_once_with(
        symbol='BTCUSDT',
        direction='LONG',
        sl_price=99.0,
        entry_price=101.0,
    )
    assert active_pos.sl_order_id == 'order-123'
    assert 'BTCUSDT' not in sl_services._pending_sl_tasks


@pytest.mark.asyncio
async def test_schedule_sl_order_placement_cancels_existing_task(monkeypatch):
    class _FakeTask:
        def __init__(self):
            self.cancel_called = False

        def done(self):
            return False

        def cancel(self):
            self.cancel_called = True

    fake_task = _FakeTask()
    sl_services._pending_sl_tasks['BTCUSDT'] = fake_task

    active_pos = SimpleNamespace(
        symbol='BTCUSDT',
        entry_fill_price=None,
        entry=100.0,
        sl=99.0,
        direction='LONG',
        sl_order_id=None,
    )
    pos_mgr = SimpleNamespace(active_position=active_pos)
    live_order_mgr = SimpleNamespace(dry_run=True)

    state = _DummyState(pos_mgr=pos_mgr, live_order_mgr=live_order_mgr)
    monkeypatch.setattr(sl_services, 'get_state_manager', lambda: state)

    await sl_services.schedule_sl_order_placement({'symbol': 'BTCUSDT'}, delay_seconds=0)

    assert fake_task.cancel_called is True

    task = sl_services._pending_sl_tasks['BTCUSDT']
    await task


@pytest.mark.asyncio
async def test_cancel_pending_sl_task_cancels_and_removes():
    started = asyncio.Event()

    async def _run():
        started.set()
        await asyncio.sleep(10)

    task = asyncio.create_task(_run())
    await started.wait()

    sl_services._pending_sl_tasks['BTCUSDT'] = task

    sl_services.cancel_pending_sl_task('BTCUSDT')

    assert 'BTCUSDT' not in sl_services._pending_sl_tasks

    with pytest.raises(asyncio.CancelledError):
        await task
