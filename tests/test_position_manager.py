"""
Tests pour le gestionnaire de positions
"""
import time
from unittest.mock import Mock, patch

import pytest
from core.position_manager import PositionManager, PositionConfig, Position


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

    def test_format_price_zero_and_small(self):
        """Test branches _format_price: price==0 and price<0.01"""
        assert PositionManager._format_price(0.0) == '0.0'

        small = PositionManager._format_price(0.000123)
        assert isinstance(small, str)
        assert small.startswith('0.000123')

    def test_log_trade_event_caps_to_50(self):
        """Test _log_trade_event keeps only last 50 events"""
        manager = PositionManager(config=PositionConfig())
        manager.active_position = Position(
            symbol='BTC_USDT',
            direction='LONG',
            entry=100.0,
            size=1000.0,
            sl=99.0,
            tp=101.0,
        )

        for i in range(60):
            manager._log_trade_event('TEST', price=100.0 + i)

        assert len(manager.active_position.position_events) == 50
        assert manager.active_position.position_events[0]['price'] == 110.0
        assert manager.active_position.position_events[-1]['price'] == 159.0

    def test_check_levels_tp_escalier_all_levels_consumed_tp(self):
        """Test _check_levels TP escalier: all levels consumed => TP/TS logic"""
        manager = PositionManager(config=PositionConfig())
        manager.active_position = Position(
            symbol='BTC_USDT',
            direction='LONG',
            entry=100.0,
            size=1000.0,
            sl=95.0,
            tp=110.0,
        )
        manager.active_position.tp_escalier_enabled = True
        manager.active_position.tp_escalier_levels = [{'pnl': 1.0, 'size_pct': 0.5, 'move_sl': 'keep'}]
        manager.active_position.tp_escalier_current_level = 1

        assert manager._check_levels(current_price=110.0) == 'TP'
        assert manager._check_levels(current_price=94.0) == 'TS'

    def test_check_levels_tp_escalier_remaining_levels_sl_vs_ts(self):
        """Test _check_levels TP escalier: remaining levels => SL-only logic (TS vs SL)"""
        manager = PositionManager(config=PositionConfig())
        manager.active_position = Position(
            symbol='BTC_USDT',
            direction='LONG',
            entry=100.0,
            size=1000.0,
            sl=99.0,
            tp=110.0,
        )
        manager.active_position.tp_escalier_enabled = True
        manager.active_position.tp_escalier_levels = [{'pnl': 1.0, 'size_pct': 0.5, 'move_sl': 'keep'}]
        manager.active_position.tp_escalier_current_level = 0
        manager.active_position.tp_escalier_profits = []

        # pnl negative + no profits => SL
        assert manager._check_levels(current_price=98.0) == 'SL'

        # with profits => TS even if pnl negative
        manager.active_position.tp_escalier_profits = [{'profit_usdt': 1.0}]
        assert manager._check_levels(current_price=98.0) == 'TS'

    def test_close_position_raises_when_no_active_position(self):
        manager = PositionManager(config=PositionConfig())
        manager.active_position = None
        with pytest.raises(ValueError):
            manager.close_position(exit_price=100.0, reason='TP')

    def test_close_position_exit_price_fallback_cache(self, monkeypatch):
        manager = PositionManager(config=PositionConfig(use_slippage_calculation=False))
        manager.active_position = Position(
            symbol='BTC_USDT',
            direction='LONG',
            entry=100.0,
            size=1000.0,
            sl=99.0,
            tp=101.0,
        )
        manager.active_position.start_time = time.time() - 100
        manager.update_price_cache('BTC_USDT', 123.45)

        monkeypatch.setattr('core.callbacks.scanner_loop.get_pg_datalogger', lambda: None)
        monkeypatch.setattr('threading.Thread', lambda *args, **kwargs: type('T', (), {'start': lambda self: None})())

        def fake_get_effective_value(key):
            return {
                'fee_per_trade': 0.0,
                'tp_sl_mode': 'FIXE',
            }.get(key)

        monkeypatch.setattr('utils.effective_config.get_effective_value', fake_get_effective_value)

        with patch('time.sleep', lambda *_a, **_k: None):
            out = manager.close_position(exit_price=None, reason='TP')

        assert out['exit_price_source'] == 'cache'
        assert out['exit'] == pytest.approx(123.45)

    def test_close_position_exit_price_fallback_entry_when_no_cache(self, monkeypatch):
        manager = PositionManager(config=PositionConfig(use_slippage_calculation=False))
        manager.active_position = Position(
            symbol='BTC_USDT',
            direction='LONG',
            entry=100.0,
            size=1000.0,
            sl=99.0,
            tp=101.0,
        )
        manager.active_position.start_time = time.time() - 100

        monkeypatch.setattr('core.callbacks.scanner_loop.get_pg_datalogger', lambda: None)
        monkeypatch.setattr('threading.Thread', lambda *args, **kwargs: type('T', (), {'start': lambda self: None})())

        def fake_get_effective_value(key):
            return {
                'fee_per_trade': 0.0,
                'tp_sl_mode': 'FIXE',
            }.get(key)

        monkeypatch.setattr('utils.effective_config.get_effective_value', fake_get_effective_value)

        with patch('time.sleep', lambda *_a, **_k: None):
            out = manager.close_position(exit_price=None, reason='TP')

        assert out['exit_price_source'] == 'entry_fallback'
        assert out['exit'] == pytest.approx(100.0)

    def test_close_position_sl_exchange_skips_live_order(self, monkeypatch):
        manager = PositionManager(config=PositionConfig(use_slippage_calculation=False))
        manager.live_order_manager = Mock()
        manager.live_order_manager.close_position = Mock(side_effect=AssertionError('should not be called'))

        manager.active_position = Position(
            symbol='BTC_USDT',
            direction='LONG',
            entry=100.0,
            size=1000.0,
            sl=99.0,
            tp=101.0,
        )
        manager.active_position.start_time = time.time() - 100

        monkeypatch.setattr('core.callbacks.scanner_loop.get_pg_datalogger', lambda: None)
        monkeypatch.setattr('threading.Thread', lambda *args, **kwargs: type('T', (), {'start': lambda self: None})())

        def fake_get_effective_value(key):
            return {
                'fee_per_trade': 0.0,
                'tp_sl_mode': 'FIXE',
            }.get(key)

        monkeypatch.setattr('utils.effective_config.get_effective_value', fake_get_effective_value)

        out = manager.close_position(exit_price=98.76, reason='SL_EXCHANGE')
        assert out['exit'] == pytest.approx(98.76)
        assert manager.active_position is None

    def test_close_position_forced_full_tp_partial_skips_live_order(self, monkeypatch):
        manager = PositionManager(config=PositionConfig(use_slippage_calculation=False))
        manager.live_order_manager = Mock()
        manager.live_order_manager.close_position = Mock(side_effect=AssertionError('should not be called'))

        manager.active_position = Position(
            symbol='BTC_USDT',
            direction='LONG',
            entry=100.0,
            size=1000.0,
            sl=99.0,
            tp=101.0,
        )
        manager.active_position.start_time = time.time() - 100
        manager.active_position.partial_tp_sold = True
        manager.active_position.size_remaining_contracts = 0

        monkeypatch.setattr('core.callbacks.scanner_loop.get_pg_datalogger', lambda: None)
        monkeypatch.setattr('threading.Thread', lambda *args, **kwargs: type('T', (), {'start': lambda self: None})())

        def fake_get_effective_value(key):
            return {
                'fee_per_trade': 0.0,
                'tp_sl_mode': 'FIXE',
            }.get(key)

        monkeypatch.setattr('utils.effective_config.get_effective_value', fake_get_effective_value)

        out = manager.close_position(exit_price=101.0, reason='TP')
        assert out['exit'] == pytest.approx(101.0)

    def test_close_position_caps_slippage_on_sl_long(self, monkeypatch):
        manager = PositionManager(config=PositionConfig(use_slippage_calculation=False))
        manager.active_position = Position(
            symbol='BTC_USDT',
            direction='LONG',
            entry=100.0,
            size=1000.0,
            sl=99.8,
            tp=101.0,
        )
        manager.active_position.start_time = time.time() - 100

        monkeypatch.setattr('core.callbacks.scanner_loop.get_pg_datalogger', lambda: None)
        monkeypatch.setattr('threading.Thread', lambda *args, **kwargs: type('T', (), {'start': lambda self: None})())

        def fake_get_effective_value(key):
            return {
                'max_slippage_pct': 0.03,
                'fee_per_trade': 0.0,
                'tp_sl_mode': 'FIXE',
            }.get(key)

        monkeypatch.setattr('utils.effective_config.get_effective_value', fake_get_effective_value)

        out = manager.close_position(exit_price=90.0, reason='SL')
        expected_min_exit = 99.8 * (1 - 0.03 / 100)
        assert out['exit'] == pytest.approx(expected_min_exit)

    def test_estimate_slippage_returns_zero_when_spread_or_depth_invalid(self):
        manager = PositionManager(config=PositionConfig())
        assert manager._estimate_slippage(order_size=100.0, spread_pct=0.0, depth=10.0, balance_score=1.0) == 0.0
        assert manager._estimate_slippage(order_size=100.0, spread_pct=0.1, depth=0.0, balance_score=1.0) == 0.0

    def test_estimate_slippage_caps_to_one_percent_and_uses_bid_ask_vol(self):
        manager = PositionManager(config=PositionConfig())
        out = manager._estimate_slippage(
            order_size=1e9,
            spread_pct=0.5,
            depth=1.0,
            balance_score=0.1,
            bid_vol=1.0,
            ask_vol=1.0,
        )
        assert out == 1.0

    def test_get_cached_price_respects_age(self):
        manager = PositionManager(config=PositionConfig())
        manager.update_price_cache('BTC_USDT', 100.0)
        assert manager.get_cached_price('BTC_USDT', max_age_ms=20000) == 100.0

        manager.price_cache['BTC_USDT']['timestamp'] -= 9999999
        assert manager.get_cached_price('BTC_USDT', max_age_ms=1) is None

        assert manager.get_cached_price('BTC_USDT', max_age_ms=0) is None

    def test_close_position_slippage_calculation_from_scalability_data(self, monkeypatch):
        manager = PositionManager(config=PositionConfig(use_slippage_calculation=True))
        manager.active_position = Position(
            symbol='BTC_USDT',
            direction='LONG',
            entry=100.0,
            size=1000.0,
            sl=99.0,
            tp=101.0,
            scalability_data={'spread_pct': 0.1, 'depth': 10000.0, 'balance': 1.0},
        )
        manager.active_position.start_time = time.time() - 100

        monkeypatch.setattr('core.callbacks.scanner_loop.get_pg_datalogger', lambda: None)
        monkeypatch.setattr('threading.Thread', lambda *args, **kwargs: type('T', (), {'start': lambda self: None})())

        def fake_get_effective_value(key):
            return {'fee_per_trade': 0.0, 'tp_sl_mode': 'FIXE'}.get(key)

        monkeypatch.setattr('utils.effective_config.get_effective_value', fake_get_effective_value)

        with patch.object(manager, '_estimate_slippage', return_value=0.5):
            out = manager.close_position(exit_price=101.0, reason='TP')

        assert out['slippage_pct'] == pytest.approx(0.5)
        assert out['slippage_usdt'] == pytest.approx(5.0)
        # fee_per_trade=0.0 est falsy => fallback code à 0.0004 (0.04%)
        # Fees = size * 0.04% * 2 = 0.8 USDT, gross=10 => net(before slippage)=9.2; - slippage 5 => 4.2
        assert out['fees'] == pytest.approx(0.8)
        assert out['net_pnl_usdt'] == pytest.approx(4.2)
        assert out['net_pnl_pct'] == pytest.approx(0.42)

    def test_close_position_uses_mexc_actual_pnl_when_divergent(self, monkeypatch):
        manager = PositionManager(config=PositionConfig(use_slippage_calculation=False))
        manager.active_position = Position(
            symbol='BTC_USDT',
            direction='LONG',
            entry=100.0,
            size=1000.0,
            sl=99.0,
            tp=101.0,
        )
        manager.active_position.start_time = time.time() - 100
        manager.active_position.mexc_actual_pnl_usdt = 20.0
        manager.active_position.exit_fill_price = 101.0

        monkeypatch.setattr('core.callbacks.scanner_loop.get_pg_datalogger', lambda: None)
        monkeypatch.setattr('threading.Thread', lambda *args, **kwargs: type('T', (), {'start': lambda self: None})())

        def fake_get_effective_value(key):
            return {'fee_per_trade': 0.0, 'tp_sl_mode': 'FIXE'}.get(key)

        monkeypatch.setattr('utils.effective_config.get_effective_value', fake_get_effective_value)

        out = manager.close_position(exit_price=101.0, reason='TP')
        assert out['net_pnl_usdt'] == pytest.approx(20.0)
        assert out['net_pnl_pct'] == pytest.approx(2.0)

    def test_close_position_sleep_applies_for_non_sl_reasons(self, monkeypatch):
        manager = PositionManager(config=PositionConfig(use_slippage_calculation=False))
        manager.active_position = Position(
            symbol='BTC_USDT',
            direction='LONG',
            entry=100.0,
            size=1000.0,
            sl=99.0,
            tp=101.0,
        )
        manager.active_position.start_time = time.time() - 1

        monkeypatch.setattr('core.callbacks.scanner_loop.get_pg_datalogger', lambda: None)
        monkeypatch.setattr('threading.Thread', lambda *args, **kwargs: type('T', (), {'start': lambda self: None})())

        def fake_get_effective_value(key):
            return {'fee_per_trade': 0.0, 'tp_sl_mode': 'FIXE'}.get(key)

        monkeypatch.setattr('utils.effective_config.get_effective_value', fake_get_effective_value)

        sleeper = Mock()
        with patch('time.sleep', sleeper):
            manager.close_position(exit_price=101.0, reason='TP')

        assert sleeper.call_count == 1

    def test_close_position_sleep_skipped_for_sl(self, monkeypatch):
        manager = PositionManager(config=PositionConfig(use_slippage_calculation=False))
        manager.active_position = Position(
            symbol='BTC_USDT',
            direction='LONG',
            entry=100.0,
            size=1000.0,
            sl=99.0,
            tp=101.0,
        )
        manager.active_position.start_time = time.time() - 1

        monkeypatch.setattr('core.callbacks.scanner_loop.get_pg_datalogger', lambda: None)
        monkeypatch.setattr('threading.Thread', lambda *args, **kwargs: type('T', (), {'start': lambda self: None})())

        def fake_get_effective_value(key):
            return {'fee_per_trade': 0.0, 'tp_sl_mode': 'FIXE', 'max_slippage_pct': 0.03}.get(key)

        monkeypatch.setattr('utils.effective_config.get_effective_value', fake_get_effective_value)

        sleeper = Mock()
        with patch('time.sleep', sleeper):
            manager.close_position(exit_price=98.0, reason='SL')

        assert sleeper.call_count == 0

    def test_close_position_live_order_success_uses_filled_price_and_pnl(self, monkeypatch):
        manager = PositionManager(config=PositionConfig(use_slippage_calculation=False))
        manager.active_position = Position(
            symbol='BTC_USDT',
            direction='LONG',
            entry=100.0,
            size=1000.0,
            sl=99.0,
            tp=101.0,
        )
        manager.active_position.start_time = time.time() - 100
        manager.active_position.position_size_contracts = 10.0

        order_result = Mock()
        order_result.success = True
        order_result.filled_price = 101.5
        order_result.actual_slippage_pct = 0.1
        order_result.order_id = 'oid'
        order_result.latency_ms = 12
        order_result.executed_at = 'now'
        order_result.actual_fees_usdt = 0.0
        order_result.actual_pnl_usdt = 12.34
        order_result.raw_api_response = {}

        lom = Mock()
        lom.close_position = Mock(return_value=order_result)
        manager.live_order_manager = lom

        monkeypatch.setattr('core.callbacks.scanner_loop.get_pg_datalogger', lambda: None)
        monkeypatch.setattr('threading.Thread', lambda *args, **kwargs: type('T', (), {'start': lambda self: None})())

        def fake_get_effective_value(key):
            return {'fee_per_trade': 0.0, 'tp_sl_mode': 'FIXE'}.get(key)

        monkeypatch.setattr('utils.effective_config.get_effective_value', fake_get_effective_value)

        out = manager.close_position(exit_price=101.0, reason='TP')
        assert out['exit'] == pytest.approx(101.5)
        assert out['net_pnl_usdt'] == pytest.approx(12.34)

    def test_close_position_live_order_error_2009_is_handled(self, monkeypatch):
        manager = PositionManager(config=PositionConfig(use_slippage_calculation=False))
        manager.active_position = Position(
            symbol='BTC_USDT',
            direction='LONG',
            entry=100.0,
            size=1000.0,
            sl=99.0,
            tp=101.0,
        )
        manager.active_position.start_time = time.time() - 100
        manager.active_position.position_size_contracts = 10.0

        order_result = Mock()
        order_result.success = False
        order_result.error_message = '2009 position nonexistent'

        lom = Mock()
        lom.close_position = Mock(return_value=order_result)
        manager.live_order_manager = lom

        monkeypatch.setattr('core.callbacks.scanner_loop.get_pg_datalogger', lambda: None)
        monkeypatch.setattr('threading.Thread', lambda *args, **kwargs: type('T', (), {'start': lambda self: None})())

        def fake_get_effective_value(key):
            return {'fee_per_trade': 0.0, 'tp_sl_mode': 'FIXE'}.get(key)

        monkeypatch.setattr('utils.effective_config.get_effective_value', fake_get_effective_value)

        out = manager.close_position(exit_price=101.0, reason='TP')
        assert out['exit'] == pytest.approx(101.0)

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
