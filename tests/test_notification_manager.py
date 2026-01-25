import pytest


@pytest.mark.asyncio
async def test_send_telegram_ignores_unconfigured_event(monkeypatch):
    from notifications.notification_manager import NotificationManager
    from unittest.mock import AsyncMock

    telegram = type('Telegram', (), {})()
    telegram.send_message = AsyncMock(return_value=True)

    mgr = NotificationManager(
        telegram_notifier=telegram,
        enable_batching=False,
        telegram_notify_settings={'position_opened': True}
    )

    await mgr._send_telegram('unknown_event', {'a': 1}, 'info')
    assert telegram.send_message.call_count == 0


def test_init_loads_default_settings_from_config(monkeypatch):
    import sys
    from notifications.notification_manager import NotificationManager

    fake_config = type('config', (), {})()
    fake_config.TELEGRAM_NOTIFY_POSITION_OPENED = True
    fake_config.TELEGRAM_NOTIFY_POSITION_CLOSED = True
    fake_config.TELEGRAM_NOTIFY_TP_ESCALIER = True
    fake_config.TELEGRAM_NOTIFY_EARLY_INVALIDATION = True
    fake_config.TELEGRAM_NOTIFY_ERROR = True
    fake_config.TELEGRAM_NOTIFY_RECONNECTION = True
    fake_config.TELEGRAM_NOTIFY_DAILY_SUMMARY = False
    fake_config.TELEGRAM_NOTIFY_RECOVERY_MODE = True
    fake_config.TELEGRAM_NOTIFY_SETUP_REJECTED = False

    monkeypatch.setitem(sys.modules, 'config', fake_config)

    mgr = NotificationManager(telegram_notifier=None, enable_batching=False, telegram_notify_settings=None)
    assert mgr.telegram_notify_settings['position_opened'] is True
    assert mgr.telegram_notify_settings['daily_summary'] is False


@pytest.mark.asyncio
async def test_send_telegram_ignores_disabled_event(monkeypatch):
    from notifications.notification_manager import NotificationManager
    from unittest.mock import AsyncMock

    telegram = type('Telegram', (), {})()
    telegram.send_message = AsyncMock(return_value=True)

    mgr = NotificationManager(
        telegram_notifier=telegram,
        enable_batching=False,
        telegram_notify_settings={'position_opened': False}
    )

    await mgr._send_telegram('position_opened', {'a': 1}, 'info')
    assert telegram.send_message.call_count == 0


@pytest.mark.asyncio
async def test_send_telegram_position_opened_calls_specific_method():
    from notifications.notification_manager import NotificationManager
    from unittest.mock import AsyncMock

    telegram = type('Telegram', (), {})()
    telegram.notify_position_opened = AsyncMock(return_value=None)

    mgr = NotificationManager(
        telegram_notifier=telegram,
        enable_batching=False,
        telegram_notify_settings={'position_opened': True}
    )

    data = {'symbol': 'BTC_USDT', 'direction': 'LONG', 'entry': 1.0, 'size': 10.0, 'tp': 1.1, 'sl': 0.9}
    await mgr._send_telegram('position_opened', data, 'info')
    telegram.notify_position_opened.assert_awaited_once()
    assert mgr.stats['telegram_sent'] == 1


@pytest.mark.asyncio
async def test_send_telegram_generic_event_uses_send_message():
    from notifications.notification_manager import NotificationManager
    from unittest.mock import AsyncMock

    telegram = type('Telegram', (), {})()
    telegram.send_message = AsyncMock(return_value=True)

    mgr = NotificationManager(
        telegram_notifier=telegram,
        enable_batching=False,
        telegram_notify_settings={'custom_event': True}
    )

    await mgr._send_telegram('custom_event', {'hello': 'world'}, 'info')
    telegram.send_message.assert_awaited_once()
    assert mgr.stats['telegram_sent'] == 1


@pytest.mark.asyncio
async def test_send_notification_calls_telegram_and_socketio():
    from notifications.notification_manager import NotificationManager
    from unittest.mock import AsyncMock

    telegram = type('Telegram', (), {})()
    telegram.notify_position_opened = AsyncMock(return_value=None)

    socket_called = {}

    async def socketio_cb(event_type, data):
        socket_called['event_type'] = event_type
        socket_called['data'] = data

    mgr = NotificationManager(
        telegram_notifier=telegram,
        socketio_callback=socketio_cb,
        enable_batching=False,
        telegram_notify_settings={'position_opened': True}
    )

    await mgr._send_notification('position_opened', {'symbol': 'BTC_USDT'}, 'info', ['telegram', 'socketio'])
    telegram.notify_position_opened.assert_awaited_once()
    assert socket_called['event_type'] == 'position_opened'
    assert mgr.stats['total_sent'] == 1


@pytest.mark.asyncio
async def test_send_telegram_logs_error_on_exception(monkeypatch):
    from notifications.notification_manager import NotificationManager
    from unittest.mock import AsyncMock

    telegram = type('Telegram', (), {})()
    telegram.notify_position_opened = AsyncMock(side_effect=RuntimeError('boom'))

    mgr = NotificationManager(
        telegram_notifier=telegram,
        enable_batching=False,
        telegram_notify_settings={'position_opened': True}
    )

    await mgr._send_telegram('position_opened', {'symbol': 'BTC_USDT'}, 'info')
    assert mgr.stats['telegram_sent'] == 0


@pytest.mark.asyncio
async def test_send_telegram_other_event_types(monkeypatch):
    from notifications.notification_manager import NotificationManager
    from unittest.mock import AsyncMock

    telegram = type('Telegram', (), {})()
    telegram.notify_position_closed = AsyncMock(return_value=None)
    telegram.notify_tp_escalier_level = AsyncMock(return_value=None)
    telegram.notify_early_invalidation = AsyncMock(return_value=None)
    telegram.notify_error = AsyncMock(return_value=None)
    telegram.notify_reconnection = AsyncMock(return_value=None)
    telegram.notify_daily_summary = AsyncMock(return_value=None)
    telegram.notify_recovery_mode = AsyncMock(return_value=None)

    mgr = NotificationManager(
        telegram_notifier=telegram,
        enable_batching=False,
        telegram_notify_settings={
            'position_closed': True,
            'tp_escalier_level': True,
            'early_invalidation': True,
            'error': True,
            'reconnection': True,
            'daily_summary': True,
            'recovery_mode': True,
        }
    )

    await mgr._send_telegram('position_closed', {'result': {'exit_reason': 'TP'}}, 'info')
    await mgr._send_telegram('tp_escalier_level', {'symbol': 'BTC_USDT'}, 'info')
    await mgr._send_telegram('early_invalidation', {'symbol': 'BTC_USDT'}, 'info')
    await mgr._send_telegram('error', {'error_type': 'E', 'details': 'D'}, 'error')
    await mgr._send_telegram('reconnection', {'service': 'WS'}, 'info')
    await mgr._send_telegram('daily_summary', {'stats': {'total_trades': 1}}, 'info')
    await mgr._send_telegram('recovery_mode', {'level': 2, 'pause_duration': 120}, 'warning')

    assert telegram.notify_position_closed.await_count == 1
    assert telegram.notify_tp_escalier_level.await_count == 1
    assert telegram.notify_early_invalidation.await_count == 1
    assert telegram.notify_error.await_count == 1
    assert telegram.notify_reconnection.await_count == 1
    assert telegram.notify_daily_summary.await_count == 1
    assert telegram.notify_recovery_mode.await_count == 1


def test_get_stats_and_recent_notifications():
    from notifications.notification_manager import NotificationManager

    mgr = NotificationManager(telegram_notifier=None, enable_batching=False, telegram_notify_settings={})
    stats = mgr.get_stats()
    assert 'total_sent' in stats
    assert 'history_size' in stats

    recent = mgr.get_recent_notifications(limit=10)
    assert isinstance(recent, list)


@pytest.mark.asyncio
async def test_send_socketio_success_increments_stats():
    from notifications.notification_manager import NotificationManager

    called = {}

    async def socketio_cb(event_type, data):
        called['event_type'] = event_type
        called['data'] = data

    mgr = NotificationManager(
        telegram_notifier=None,
        socketio_callback=socketio_cb,
        enable_batching=False,
        telegram_notify_settings={}
    )

    await mgr._send_socketio('position_opened', {'x': 1})
    assert called['event_type'] == 'position_opened'
    assert mgr.stats['socketio_sent'] == 1


@pytest.mark.asyncio
async def test_send_socketio_error_does_not_raise(monkeypatch):
    from notifications.notification_manager import NotificationManager

    async def socketio_cb(event_type, data):
        raise RuntimeError('socketio down')

    mgr = NotificationManager(
        telegram_notifier=None,
        socketio_callback=socketio_cb,
        enable_batching=False,
        telegram_notify_settings={}
    )

    await mgr._send_socketio('position_opened', {'x': 1})
    assert mgr.stats['socketio_sent'] == 0


@pytest.mark.asyncio
async def test_notify_batches_setup_rejected_and_flushes(monkeypatch):
    from notifications.notification_manager import NotificationManager

    telegram = type('Telegram', (), {})()

    sent = {}

    async def fake_send_message(message: str):
        sent['message'] = message
        return True

    telegram.send_message = fake_send_message

    mgr = NotificationManager(
        telegram_notifier=telegram,
        enable_batching=True,
        batch_interval=0,
        telegram_notify_settings={'setup_rejected': True}
    )

    # 6 symboles pour couvrir la branche "+N autres"
    for sym in ['BTC_USDT', 'ETH_USDT', 'XRP_USDT', 'SOL_USDT', 'ADA_USDT', 'DOT_USDT']:
        await mgr.notify('setup_rejected', {'symbol': sym, 'rejection_reason': 'R1'}, priority='info')

    assert 'SETUPS REJETÉS' in sent.get('message', '')
    assert mgr.stats['telegram_sent'] >= 1
    assert mgr.stats['batched'] >= 1


@pytest.mark.asyncio
async def test_flush_batch_includes_plus_n_others(monkeypatch):
    from notifications.notification_manager import NotificationManager
    import time

    telegram = type('Telegram', (), {})()
    sent = {}

    async def fake_send_message(message: str):
        sent['message'] = message
        return True

    telegram.send_message = fake_send_message

    mgr = NotificationManager(
        telegram_notifier=telegram,
        enable_batching=True,
        batch_interval=999,
        telegram_notify_settings={'setup_rejected': True}
    )

    # Empêcher le flush auto: sinon last_batch_send=0 => elapsed énorme => flush immédiat
    mgr.last_batch_send['setup_rejected'] = time.time()

    # Construire un batch > 5 symboles sans flush auto
    for sym in ['BTC_USDT', 'ETH_USDT', 'XRP_USDT', 'SOL_USDT', 'ADA_USDT', 'DOT_USDT']:
        await mgr._add_to_batch('setup_rejected', {'symbol': sym, 'rejection_reason': 'R1'}, ['telegram'])

    await mgr._flush_batch('setup_rejected')
    assert '+1 autres' in sent.get('message', '')


@pytest.mark.asyncio
async def test_notify_non_batch_calls_send_notification(monkeypatch):
    from notifications.notification_manager import NotificationManager

    mgr = NotificationManager(telegram_notifier=None, enable_batching=True, telegram_notify_settings={})

    called = {}

    async def fake_send_notification(event_type, data, priority, channels):
        called['event_type'] = event_type
        called['priority'] = priority
        called['channels'] = channels

    monkeypatch.setattr(mgr, '_send_notification', fake_send_notification)

    await mgr.notify('position_opened', {'symbol': 'BTC_USDT'}, priority='warning')
    assert called['event_type'] == 'position_opened'
    assert called['priority'] == 'warning'


def test_create_notification_manager_factory(monkeypatch):
    import sys
    from notifications.notification_manager import create_notification_manager

    created = {}

    def fake_create_telegram_notifier(bot_token=None, chat_id=None, enabled=True, instance_port=None):
        created['bot_token'] = bot_token
        created['chat_id'] = chat_id
        created['enabled'] = enabled
        created['instance_port'] = instance_port
        return 'TN'

    fake_tn_mod = type('tn_mod', (), {})()
    fake_tn_mod.create_telegram_notifier = fake_create_telegram_notifier
    monkeypatch.setitem(sys.modules, 'notifications.telegram_notifier', fake_tn_mod)

    mgr = create_notification_manager(
        telegram_bot_token='t',
        telegram_chat_id='1',
        socketio_callback=None,
        enable_batching=False,
        telegram_notify_settings={'position_opened': True},
        instance_port=5001,
    )
    assert mgr.telegram_notifier == 'TN'
    assert created['bot_token'] == 't'
    assert created['chat_id'] == '1'
    assert created['instance_port'] == 5001

    mgr2 = create_notification_manager(telegram_bot_token=None, telegram_chat_id=None, enable_batching=False)
    assert mgr2.telegram_notifier is None


@pytest.mark.asyncio
async def test_flush_all_batches_calls_flush(monkeypatch):
    from notifications.notification_manager import NotificationManager

    telegram = type('Telegram', (), {})()

    async def fake_send_message(message: str):
        return True

    telegram.send_message = fake_send_message

    mgr = NotificationManager(
        telegram_notifier=telegram,
        enable_batching=True,
        batch_interval=999,
        telegram_notify_settings={'setup_rejected': True}
    )

    await mgr._add_to_batch('setup_rejected', {'symbol': 'BTC_USDT', 'rejection_reason': 'R1'}, ['telegram'])
    await mgr.flush_all_batches()

    assert mgr.pending_batches['setup_rejected'] == []
