import builtins
import sys
import time

import pytest


class _AsyncCM:
    def __init__(self, obj):
        self._obj = obj

    async def __aenter__(self):
        return self._obj

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeResponse:
    def __init__(self, status: int, body: str = ""):
        self.status = status
        self._body = body

    async def text(self):
        return self._body


class _FakeSession:
    def __init__(self, response: _FakeResponse, should_raise: bool = False):
        self._response = response
        self._should_raise = should_raise
        self.last_post = None

    def post(self, url, json=None, timeout=None):
        if self._should_raise:
            raise RuntimeError("network down")
        self.last_post = {'url': url, 'json': json, 'timeout': timeout}
        return _AsyncCM(self._response)


class _FakeClientSessionFactory:
    def __init__(self, response: _FakeResponse, should_raise: bool = False):
        self._response = response
        self._should_raise = should_raise
        self.session = None

    def __call__(self):
        self.session = _FakeSession(self._response, should_raise=self._should_raise)
        return _AsyncCM(self.session)


class _FakeClientTimeout:
    def __init__(self, total: int = 10):
        self.total = total


@pytest.mark.asyncio
async def test_send_message_returns_false_when_disabled():
    from notifications.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier(bot_token=None, chat_id=None, enabled=True)
    out = await notifier.send_message("hello")
    assert out is False


@pytest.mark.asyncio
async def test_send_message_chat_id_parsing_branches(monkeypatch):
    from notifications.telegram_notifier import TelegramNotifier

    # chat_id None branch (force enabled True to reach send_message)
    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)
    notifier.throttle_seconds = 0
    notifier.chat_id = None
    notifier.enabled = True

    factory1 = _FakeClientSessionFactory(_FakeResponse(200, "ok"))
    fake_aiohttp1 = type("aiohttp", (), {})()
    fake_aiohttp1.ClientTimeout = _FakeClientTimeout
    fake_aiohttp1.ClientSession = factory1
    monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp1)

    out = await notifier.send_message("hello")
    assert out is True
    assert factory1.session.last_post['json']['chat_id'] is None

    # chat_id int branch
    notifier2 = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)
    notifier2.throttle_seconds = 0
    notifier2.chat_id = 123
    notifier2.enabled = True

    factory2 = _FakeClientSessionFactory(_FakeResponse(200, "ok"))
    fake_aiohttp2 = type("aiohttp", (), {})()
    fake_aiohttp2.ClientTimeout = _FakeClientTimeout
    fake_aiohttp2.ClientSession = factory2
    monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp2)

    out2 = await notifier2.send_message("hello")
    assert out2 is True
    assert factory2.session.last_post['json']['chat_id'] == 123

    # conversion fail branch: keep string
    notifier3 = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)
    notifier3.throttle_seconds = 0
    notifier3.chat_id = "@my_channel"
    notifier3.enabled = True

    factory3 = _FakeClientSessionFactory(_FakeResponse(200, "ok"))
    fake_aiohttp3 = type("aiohttp", (), {})()
    fake_aiohttp3.ClientTimeout = _FakeClientTimeout
    fake_aiohttp3.ClientSession = factory3
    monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp3)

    out3 = await notifier3.send_message("hello")
    assert out3 is True
    assert factory3.session.last_post['json']['chat_id'] == "@my_channel"


@pytest.mark.asyncio
async def test_send_message_rate_limit_short_circuits(monkeypatch):
    from notifications.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)
    notifier.rate_limit_until = time.time() + 999

    out = await notifier.send_message("hello")
    assert out is False


@pytest.mark.asyncio
async def test_send_message_success_200(monkeypatch):
    from notifications.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)
    notifier.throttle_seconds = 0

    fake_aiohttp = type("aiohttp", (), {})()
    fake_aiohttp.ClientTimeout = _FakeClientTimeout
    fake_aiohttp.ClientSession = _FakeClientSessionFactory(_FakeResponse(200, "ok"))
    monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp)

    out = await notifier.send_message("hello")
    assert out is True
    assert len(notifier.message_queue) == 1


@pytest.mark.asyncio
async def test_send_message_throttling_sleeps(monkeypatch):
    from notifications.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)
    notifier.throttle_seconds = 10
    notifier.last_message_time = time.time()

    slept = {}

    async def fake_sleep(duration):
        slept['duration'] = duration

    monkeypatch.setattr(sys.modules['asyncio'], 'sleep', fake_sleep)

    fake_aiohttp = type("aiohttp", (), {})()
    fake_aiohttp.ClientTimeout = _FakeClientTimeout
    fake_aiohttp.ClientSession = _FakeClientSessionFactory(_FakeResponse(200, "ok"))
    monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp)

    out = await notifier.send_message("hello")
    assert out is True
    assert slept.get('duration', 0) > 0


@pytest.mark.asyncio
async def test_send_message_429_sets_rate_limit(monkeypatch):
    from notifications.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)
    notifier.throttle_seconds = 0

    fake_aiohttp = type("aiohttp", (), {})()
    fake_aiohttp.ClientTimeout = _FakeClientTimeout
    fake_aiohttp.ClientSession = _FakeClientSessionFactory(
        _FakeResponse(429, '{"parameters": {"retry_after": 2}}')
    )
    monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp)

    out = await notifier.send_message("hello")
    assert out is False
    assert notifier.rate_limit_until > time.time()


@pytest.mark.asyncio
async def test_send_message_429_invalid_json_uses_fallback(monkeypatch):
    from notifications.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)
    notifier.throttle_seconds = 0

    fake_aiohttp = type("aiohttp", (), {})()
    fake_aiohttp.ClientTimeout = _FakeClientTimeout
    fake_aiohttp.ClientSession = _FakeClientSessionFactory(_FakeResponse(429, 'not-json'))
    monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp)

    out = await notifier.send_message("hello")
    assert out is False
    assert notifier.rate_limit_until > time.time()


@pytest.mark.asyncio
async def test_send_message_non_200_logs_error(monkeypatch):
    from notifications.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)
    notifier.throttle_seconds = 0

    fake_aiohttp = type("aiohttp", (), {})()
    fake_aiohttp.ClientTimeout = _FakeClientTimeout
    fake_aiohttp.ClientSession = _FakeClientSessionFactory(_FakeResponse(500, "boom"))
    monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp)

    out = await notifier.send_message("hello")
    assert out is False


@pytest.mark.asyncio
async def test_send_message_import_error_disables_notifier(monkeypatch):
    from notifications.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "aiohttp":
            raise ImportError("no aiohttp")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    out = await notifier.send_message("hello")
    assert out is False
    assert notifier.enabled is False


@pytest.mark.asyncio
async def test_send_message_handles_exception(monkeypatch):
    from notifications.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)
    notifier.throttle_seconds = 0

    fake_aiohttp = type("aiohttp", (), {})()
    fake_aiohttp.ClientTimeout = _FakeClientTimeout
    fake_aiohttp.ClientSession = _FakeClientSessionFactory(_FakeResponse(200, "ok"), should_raise=True)
    monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp)

    out = await notifier.send_message("hello")
    assert out is False


def test_escape_markdown_escapes_special_chars():
    from notifications.telegram_notifier import TelegramNotifier

    s = TelegramNotifier._escape_markdown("A*B_C")
    assert "\\*" in s
    assert "\\_" in s


def test_escape_markdown_returns_input_when_empty_or_none():
    from notifications.telegram_notifier import TelegramNotifier

    assert TelegramNotifier._escape_markdown("") == ""
    assert TelegramNotifier._escape_markdown(None) is None


@pytest.mark.asyncio
async def test_notify_position_closed_variants(monkeypatch):
    from notifications.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)

    sent = {}

    async def fake_send_message(message: str, parse_mode: str = 'Markdown', bypass_throttle: bool = False):
        sent['message'] = message
        return True

    monkeypatch.setattr(notifier, "send_message", fake_send_message)

    await notifier.notify_position_closed(
        {'symbol': 'BTC_USDT', 'direction': 'LONG'},
        {'exit_reason': 'TP', 'pnl_pct': 1.2, 'pnl_usdt': 5.0, 'duration_seconds': 30}
    )
    assert 'POSITION FERMÉE' in sent.get('message', '')

    # pnl negative branch + duration minutes branch
    await notifier.notify_position_closed(
        {'symbol': 'BTC_USDT', 'direction': 'LONG'},
        {'exit_reason': 'SL', 'pnl_pct': -1.0, 'pnl_usdt': -2.0, 'duration_seconds': 120}
    )
    assert 'SL' in sent.get('message', '')

    # pnl zero branch + duration hours branch
    await notifier.notify_position_closed(
        {'symbol': 'BTC_USDT', 'direction': 'LONG'},
        {'exit_reason': 'BE', 'pnl_pct': 0.0, 'pnl_usdt': 0.0, 'duration_seconds': 4000}
    )
    assert 'BE' in sent.get('message', '')


@pytest.mark.asyncio
async def test_notify_tp_escalier_level(monkeypatch):
    from notifications.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)

    sent = {}

    async def fake_send_message(message: str, parse_mode: str = 'Markdown', bypass_throttle: bool = False):
        sent['message'] = message
        return True

    monkeypatch.setattr(notifier, "send_message", fake_send_message)

    await notifier.notify_tp_escalier_level({'symbol': 'BTC_USDT', 'level': 1, 'total_levels': 3, 'profit_usdt': 1.0, 'profit_pct': 0.5, 'size_remaining_pct': 80})
    assert 'TP ESCALIER' in sent.get('message', '')


@pytest.mark.asyncio
async def test_notify_early_invalidation_and_error_and_reconnection(monkeypatch):
    from notifications.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)

    sent_messages = []

    async def fake_send_message(message: str, parse_mode: str = 'Markdown', bypass_throttle: bool = False):
        sent_messages.append((message, bypass_throttle))
        return True

    monkeypatch.setattr(notifier, "send_message", fake_send_message)

    await notifier.notify_early_invalidation({'symbol': 'BTC_USDT', 'direction': 'LONG', 'pnl_pct': -0.1})
    await notifier.notify_error('TypeX', 'Details * unsafe _ chars')
    await notifier.notify_reconnection('WS')

    assert any('EARLY INVALIDATION' in m[0] for m in sent_messages)
    assert any('ERREUR SYSTÈME' in m[0] and m[1] is True for m in sent_messages)
    assert any('RECONNEXION' in m[0] for m in sent_messages)


@pytest.mark.asyncio
async def test_notify_daily_summary_and_recovery_mode(monkeypatch):
    from notifications.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)
    sent = {}

    async def fake_send_message(message: str, parse_mode: str = 'Markdown', bypass_throttle: bool = False):
        sent['message'] = message
        return True

    monkeypatch.setattr(notifier, "send_message", fake_send_message)

    await notifier.notify_daily_summary({'total_trades': 2, 'wins': 1, 'losses': 1, 'winrate': 50.0, 'pnl_total': 1.5, 'best_trade': 2.0, 'worst_trade': -0.5})
    assert 'RÉSUMÉ JOURNALIER' in sent.get('message', '')

    await notifier.notify_recovery_mode(2, 120)
    assert 'RECOVERY MODE' in sent.get('message', '')


def test_get_stats_counts_successful():
    from notifications.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)
    notifier.message_queue.append({'message': 'a', 'timestamp': 1, 'success': True})
    notifier.message_queue.append({'message': 'b', 'timestamp': 2, 'success': False})

    stats = notifier.get_stats()
    assert stats['total_messages'] == 2
    assert stats['successful'] == 1
    assert stats['failed'] == 1


def test_create_telegram_notifier_factory():
    from notifications.telegram_notifier import create_telegram_notifier

    notifier = create_telegram_notifier(bot_token='t', chat_id=123, enabled=True, instance_port=5001)
    assert notifier.bot_token == 't'
    assert notifier.chat_id == '123'
    assert notifier.instance_port == 5001


def test_send_alert_sync_paths(monkeypatch):
    from notifications.telegram_notifier import TelegramNotifier
    import asyncio

    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)

    async def fake_send_message(message: str, parse_mode: str = 'Markdown', bypass_throttle: bool = False):
        return True

    monkeypatch.setattr(notifier, "send_message", fake_send_message)

    def fake_get_running_loop():
        raise RuntimeError('no loop')

    def fake_run(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    monkeypatch.setattr(asyncio, 'get_running_loop', fake_get_running_loop)
    monkeypatch.setattr(asyncio, 'run', fake_run)

    assert notifier.send_alert('hi') is True


def test_send_error_sync_builds_message(monkeypatch):
    from notifications.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)

    called = {}

    def fake_send_alert(message: str) -> bool:
        called['message'] = message
        return True

    monkeypatch.setattr(notifier, 'send_alert', fake_send_alert)

    out = notifier.send_error_sync('ERR', 'details')
    assert out is True
    assert 'ERREUR SYSTÈME' in called.get('message', '')


def test_is_duplicate_event_caches_and_expires(monkeypatch):
    from notifications.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)
    notifier.dedup_cooldown_seconds = 1

    now = 1000.0

    def fake_time():
        return now

    monkeypatch.setattr(time, "time", fake_time)

    assert notifier._is_duplicate_event("k") is False
    assert notifier._is_duplicate_event("k") is True

    now = 1002.0
    assert notifier._is_duplicate_event("k") is False


@pytest.mark.asyncio
async def test_notify_position_opened_calls_send_message(monkeypatch):
    from notifications.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)

    sent = {}

    async def fake_send_message(message: str, parse_mode: str = 'Markdown', bypass_throttle: bool = False):
        sent['message'] = message
        return True

    monkeypatch.setattr(notifier, "send_message", fake_send_message)

    await notifier.notify_position_opened({
        'symbol': 'ASTER/USDT:USDT',
        'direction': 'LONG',
        'entry': 1.0,
        'size': 10.0,
        'tp': 1.1,
        'sl': 0.9,
        'condition_types': ['A', 'B'],
    })

    assert 'POSITION OUVERTE' in sent.get('message', '')


@pytest.mark.asyncio
async def test_notify_position_opened_short_branch(monkeypatch):
    from notifications.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)
    sent = {}

    async def fake_send_message(message: str, parse_mode: str = 'Markdown', bypass_throttle: bool = False):
        sent['message'] = message
        return True

    monkeypatch.setattr(notifier, "send_message", fake_send_message)

    await notifier.notify_position_opened({
        'symbol': 'BTC_USDT',
        'direction': 'SHORT',
        'entry': 100.0,
        'size': 10.0,
        'tp': 90.0,
        'sl': 110.0,
        'condition_types': [],
    })

    assert 'POSITION OUVERTE' in sent.get('message', '')


@pytest.mark.asyncio
async def test_notify_position_opened_dedup_skips_second(monkeypatch):
    from notifications.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)

    calls = {'n': 0}

    async def fake_send_message(message: str, parse_mode: str = 'Markdown', bypass_throttle: bool = False):
        calls['n'] += 1
        return True

    monkeypatch.setattr(notifier, "send_message", fake_send_message)

    data = {
        'symbol': 'BTC_USDT',
        'direction': 'LONG',
        'entry': 1.0,
        'size': 10.0,
        'tp': 1.1,
        'sl': 0.9,
        'condition_types': [],
    }

    await notifier.notify_position_opened(data)
    await notifier.notify_position_opened(data)

    assert calls['n'] == 1


@pytest.mark.asyncio
async def test_notify_methods_skip_on_duplicate(monkeypatch):
    from notifications.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)

    async def boom(*args, **kwargs):
        raise AssertionError('send_message should not be called')

    monkeypatch.setattr(notifier, 'send_message', boom)
    monkeypatch.setattr(notifier, '_is_duplicate_event', lambda key: True)

    await notifier.notify_position_closed({'symbol': 'BTC_USDT'}, {'exit_reason': 'TP'})
    await notifier.notify_tp_escalier_level({'symbol': 'BTC_USDT', 'level': 1})
    await notifier.notify_early_invalidation({'symbol': 'BTC_USDT'})
    await notifier.notify_error('E', 'D')
    await notifier.notify_reconnection('WS')
    await notifier.notify_recovery_mode(1, 60)


def test_send_alert_disabled_returns_true():
    from notifications.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier(bot_token=None, chat_id=None, enabled=True)
    assert notifier.send_alert('hello') is True


def test_send_alert_running_loop_uses_ensure_future(monkeypatch):
    from notifications.telegram_notifier import TelegramNotifier
    import asyncio

    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)

    async def fake_send_message(message: str, parse_mode: str = 'Markdown', bypass_throttle: bool = False):
        return True

    monkeypatch.setattr(notifier, 'send_message', fake_send_message)

    class _Loop:
        pass

    called = {}

    def fake_get_running_loop():
        return _Loop()

    def fake_ensure_future(coro):
        called['scheduled'] = True
        coro.close()
        return None

    monkeypatch.setattr(asyncio, 'get_running_loop', fake_get_running_loop)
    monkeypatch.setattr(asyncio, 'ensure_future', fake_ensure_future)

    assert notifier.send_alert('hello') is True
    assert called.get('scheduled') is True


def test_send_alert_exception_returns_false(monkeypatch):
    from notifications.telegram_notifier import TelegramNotifier
    import asyncio

    notifier = TelegramNotifier(bot_token="t", chat_id="1", enabled=True)

    async def fake_send_message(message: str, parse_mode: str = 'Markdown', bypass_throttle: bool = False):
        return True

    monkeypatch.setattr(notifier, 'send_message', fake_send_message)

    def fake_get_running_loop():
        raise RuntimeError('no loop')

    def fake_run(coro):
        coro.close()
        raise RuntimeError('run failed')

    monkeypatch.setattr(asyncio, 'get_running_loop', fake_get_running_loop)
    monkeypatch.setattr(asyncio, 'run', fake_run)

    assert notifier.send_alert('hello') is False
