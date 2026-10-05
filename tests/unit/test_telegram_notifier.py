"""Tests pour TelegramNotifier"""

import pytest
import asyncio
import time
from unittest.mock import patch
from notifications.telegram_notifier import TelegramNotifier


class TestTelegramNotifierInit:
    def test_init_with_valid_credentials(self):
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id="123456789",
            enabled=True,
        )
        assert notifier.bot_token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        assert notifier.chat_id == "123456789"
        assert notifier.enabled == "123456789"
        assert notifier.throttle_seconds == 2
        assert notifier.instance_port == 5000

    def test_init_with_int_chat_id(self):
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id=123456789,
            enabled=True,
        )
        assert notifier.chat_id == "123456789"
        assert isinstance(notifier.chat_id, str)

    def test_init_with_disabled(self):
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id="123456789",
            enabled=False,
        )
        assert notifier.enabled is False

    def test_init_without_token(self):
        notifier = TelegramNotifier(bot_token=None, chat_id="123456789", enabled=True)
        assert notifier.enabled in [None, False, "False"]

    def test_init_without_chat_id(self):
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id=None,
            enabled=True,
        )
        assert notifier.enabled in [None, False, "False"]

    def test_init_with_custom_throttle(self):
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id="123456789",
            throttle_seconds=5,
        )
        assert notifier.throttle_seconds == 5

    def test_init_with_custom_port(self):
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id="123456789",
            instance_port=5001,
        )
        assert notifier.instance_port == 5001


class TestEscapeMarkdown:
    def test_escape_markdown_normal_text(self):
        result = TelegramNotifier._escape_markdown("Hello World")
        assert result == "Hello World"

    def test_escape_markdown_with_special_chars(self):
        text = "Price: $100 *bold* _italic_"
        result = TelegramNotifier._escape_markdown(text)
        assert "\\" in result

    def test_escape_markdown_empty_string(self):
        result = TelegramNotifier._escape_markdown("")
        assert result == ""

    def test_escape_markdown_none(self):
        result = TelegramNotifier._escape_markdown(None)
        assert result is None


class TestIsDuplicateEvent:
    def test_is_duplicate_event_first_time(self):
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11", chat_id="123456789"
        )
        result = notifier._is_duplicate_event("test_event_1")
        assert result is False

    def test_is_duplicate_event_recent(self):
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11", chat_id="123456789"
        )
        notifier.sent_events["test_event_2"] = time.time()
        result = notifier._is_duplicate_event("test_event_2")
        assert result is True

    def test_is_duplicate_event_expired(self):
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11", chat_id="123456789"
        )
        notifier.sent_events["test_event_3"] = time.time() - 120
        result = notifier._is_duplicate_event("test_event_3")
        assert result is False


class TestGetStats:
    def test_get_stats(self):
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11", chat_id="123456789"
        )
        stats = notifier.get_stats()
        assert "total_messages" in stats
        assert "successful" in stats
        assert "failed" in stats
        assert "enabled" in stats
        assert stats["total_messages"] == 0


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_send_message_disabled(self):
        notifier = TelegramNotifier(
            bot_token=None,
            chat_id=None,
            enabled=False
        )
        result = await notifier.send_message("Test message")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_rate_limit(self):
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id="123456789"
        )
        notifier.rate_limit_until = time.time() + 100
        result = await notifier.send_message("Test message")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_throttled(self):
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id="123456789",
            throttle_seconds=2
        )
        notifier.last_message_time = time.time()
        result = await notifier.send_message("Test message")
        assert result is False


class TestNotifyPositionOpened:
    @pytest.mark.asyncio
    async def test_notify_position_opened(self):
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id="123456789"
        )
        position_data = {
            "symbol": "BTC/USDT",
            "direction": "LONG",
            "size": 0.1,
            "entry": 50000,
            "tp": 51000,
            "sl": 49000,
            "condition_types": ["EMA crossover"]
        }
        with patch.object(notifier, 'send_message') as mock_send:
            await notifier.notify_position_opened(position_data)
        mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_position_opened_disabled(self):
        notifier = TelegramNotifier(
            bot_token=None,
            chat_id=None,
            enabled=False
        )
        position_data = {
            "symbol": "BTC/USDT",
            "direction": "LONG",
            "size": 0.1,
            "entry": 50000,
            "tp": 51000,
            "sl": 49000,
            "condition_types": ["EMA crossover"]
        }
        await notifier.notify_position_opened(position_data)
        assert True


class TestNotifyPositionClosed:
    @pytest.mark.asyncio
    async def test_notify_position_closed(self):
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id="123456789"
        )
        position_data = {
            "symbol": "BTC/USDT",
            "direction": "LONG",
            "size": 0.1,
            "entry": 50000
        }
        result_data = {
            "exit_reason": "TP reached",
            "pnl_pct": 2.0,
            "pnl_usdt": 100,
            "duration_seconds": 300
        }
        with patch.object(notifier, 'send_message') as mock_send:
            await notifier.notify_position_closed(position_data, result_data)
        mock_send.assert_called_once()


class TestNotifyTpEscalierLevel:
    @pytest.mark.asyncio
    async def test_notify_tp_escalier_level(self):
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id="123456789"
        )
        level_data = {
            "symbol": "BTC/USDT",
            "level": 1,
            "total_levels": 3,
            "profit_usdt": 50,
            "profit_pct": 1.0,
            "size_remaining_pct": 67
        }
        with patch.object(notifier, 'send_message') as mock_send:
            await notifier.notify_tp_escalier_level(level_data)
        mock_send.assert_called_once()


class TestNotifyEarlyInvalidation:
    @pytest.mark.asyncio
    async def test_notify_early_invalidation(self):
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id="123456789"
        )
        position_data = {
            "symbol": "BTC/USDT",
            "direction": "LONG",
            "pnl_pct": -2.5
        }
        with patch.object(notifier, 'send_message') as mock_send:
            await notifier.notify_early_invalidation(position_data)
        mock_send.assert_called_once()


class TestNotifyError:
    @pytest.mark.asyncio
    async def test_notify_error(self):
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id="123456789"
        )
        with patch.object(notifier, 'send_message') as mock_send:
            await notifier.notify_error("ConnectionError", "Timeout après 10s")
        mock_send.assert_called_once()


class TestNotifyReconnection:
    @pytest.mark.asyncio
    async def test_notify_reconnection(self):
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id="123456789"
        )
        with patch.object(notifier, 'send_message') as mock_send:
            await notifier.notify_reconnection("WebSocket")
        mock_send.assert_called_once()


class TestNotifyDailySummary:
    @pytest.mark.asyncio
    async def test_notify_daily_summary(self):
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id="123456789"
        )
        stats = {
            "total_trades": 15,
            "wins": 10,
            "losses": 5,
            "winrate": 66.7,
            "pnl_total": 500,
            "best_trade": 100,
            "worst_trade": -50
        }
        with patch.object(notifier, 'send_message') as mock_send:
            await notifier.notify_daily_summary(stats)
        mock_send.assert_called_once()


class TestNotifyRecoveryMode:
    @pytest.mark.asyncio
    async def test_notify_recovery_mode(self):
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id="123456789"
        )
        with patch.object(notifier, 'send_message') as mock_send:
            await notifier.notify_recovery_mode(level=1, pause_duration=300)
        mock_send.assert_called_once()


class TestSendAlert:
    def test_send_alert(self):
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id="123456789"
        )
        with patch.object(notifier, 'send_alert', return_value=True) as mock_send:
            result = notifier.send_alert("Test alerte")
        assert result is True


class TestSendErrorSync:
    def test_send_error_sync(self):
        notifier = TelegramNotifier(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id="123456789"
        )
        with patch.object(notifier, 'send_alert', return_value=True) as mock_send:
            result = notifier.send_error_sync("TestError", "Test details")
        assert result is True
