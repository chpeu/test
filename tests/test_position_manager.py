"""
Tests pour le gestionnaire de positions
"""
import pytest
from core.position_manager import PositionManager, PositionConfig


class TestPositionManager:
    """Tests pour le gestionnaire de positions"""

    def test_position_config_creation(self):
        """Test création de configuration de position"""
        config = PositionConfig()
        assert config is not None

    def test_position_config_with_params(self):
        """Test configuration de position avec paramètres"""
        config = PositionConfig(
            use_atr=True,
            fixed_tp_pct=0.6,
            fixed_sl_pct=0.25,
            win_streak=3,
            loss_streak=2
        )
        assert config.use_atr is True
        assert config.fixed_tp_pct == 0.6
        assert config.fixed_sl_pct == 0.25
        assert config.win_streak == 3
        assert config.loss_streak == 2

    def test_position_manager_creation(self):
        """Test création du gestionnaire de positions"""
        config = PositionConfig()
        manager = PositionManager(config=config)
        assert manager is not None
        assert manager.config == config

    def test_format_price(self):
        """Test formatage de prix"""
        price = PositionManager._format_price(50000.123456)
        assert isinstance(price, str)
        assert '50000' in price

    def test_format_price_decimals(self):
        """Test formatage de prix avec décimales"""
        price = PositionManager._format_price(50000.123456, min_decimals=2, max_decimals=4)
        assert isinstance(price, str)
        assert '50000' in price

    def test_open_position_sends_notification_without_event_loop(self, monkeypatch):
        from unittest.mock import AsyncMock
        import asyncio

        config = PositionConfig(use_atr=False, fixed_tp_pct=0.6, fixed_sl_pct=0.25)
        manager = PositionManager(config=config)

        notification_manager = type('NotificationManager', (), {})()
        notification_manager.notify = AsyncMock()
        manager.notification_manager = notification_manager

        def fake_get_running_loop():
            raise RuntimeError('no running event loop')

        called = {}

        def fake_run(coro):
            called['ran'] = True
            coro.close()
            return None

        monkeypatch.setattr(asyncio, 'get_running_loop', fake_get_running_loop)
        monkeypatch.setattr(asyncio, 'run', fake_run)

        position = manager.open_position(
            symbol="BTC_USDT",
            direction="LONG",
            entry=50000.0,
            size=100.0,
            confirmed_by="Test",
        )

        assert position is not None
        assert called.get('ran') is True
        assert notification_manager.notify.call_count == 1
        args, kwargs = notification_manager.notify.call_args
        assert args[0] == 'position_opened'
        assert kwargs.get('priority') == 'info'

    def test_open_position_integration_sends_telegram_message(self, monkeypatch):
        import asyncio
        from notifications.notification_manager import NotificationManager
        from notifications.telegram_notifier import TelegramNotifier

        config = PositionConfig(use_atr=False, fixed_tp_pct=0.6, fixed_sl_pct=0.25)
        manager = PositionManager(config=config)

        telegram = TelegramNotifier(bot_token='token', chat_id='123', enabled=True)
        sent = {}

        async def fake_send_message(message: str, parse_mode: str = 'Markdown', bypass_throttle: bool = False) -> bool:
            sent['message'] = message
            return True

        monkeypatch.setattr(telegram, 'send_message', fake_send_message)
        # éviter throttling/sleep
        telegram.throttle_seconds = 0

        notif_mgr = NotificationManager(
            telegram_notifier=telegram,
            enable_batching=False,
            telegram_notify_settings={'position_opened': True}
        )
        manager.notification_manager = notif_mgr

        def fake_get_running_loop():
            raise RuntimeError('no running event loop')

        def fake_run(coro):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

        monkeypatch.setattr(asyncio, 'get_running_loop', fake_get_running_loop)
        monkeypatch.setattr(asyncio, 'run', fake_run)

        position = manager.open_position(
            symbol='BTC_USDT',
            direction='LONG',
            entry=50000.0,
            size=100.0,
            confirmed_by='Test',
            condition_types=['cond1', 'cond2'],
        )

        assert position is not None
        assert 'message' in sent
