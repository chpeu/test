"""Tests pour TelegramCommandHandler"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from notifications.telegram_commands import (
    TelegramCommandHandler,
    create_telegram_command_handler,
)
from datetime import datetime


class TestTelegramCommandHandlerInit:
    def test_init_with_all_dependencies(self):
        analytics_db = Mock()
        position_manager = Mock()
        notification_manager = Mock()
        handler = TelegramCommandHandler(
            analytics_db=analytics_db,
            position_manager=position_manager,
            notification_manager=notification_manager,
            instance_port=5001,
        )
        assert handler.analytics_db == analytics_db
        assert handler.position_manager == position_manager
        assert handler.notification_manager == notification_manager
        assert handler.instance_port == 5001
        assert "/stats" in handler.commands
        assert "/help" in handler.commands

    def test_init_minimal(self):
        handler = TelegramCommandHandler()
        assert handler.analytics_db is None
        assert handler.position_manager is None
        assert handler.commands["/help"] is not None


class TestHandleCommand:
    @pytest.mark.asyncio
    async def test_handle_stats_command(self):
        analytics_db = Mock()
        analytics_db.get_trades = Mock(return_value=[])
        handler = TelegramCommandHandler(analytics_db=analytics_db)
        response = await handler.handle_command("/stats", 123456)
        assert "STATISTIQUES" in response
        assert "Aucun trade" in response

    @pytest.mark.asyncio
    async def test_handle_unknown_command(self):
        handler = TelegramCommandHandler()
        response = await handler.handle_command("/unknown", 123456)
        assert "inconnue" in response.lower()
        assert "/help" in response

    @pytest.mark.asyncio
    async def test_handle_command_with_bot_name(self):
        analytics_db = Mock()
        analytics_db.get_trades = Mock(return_value=[])
        handler = TelegramCommandHandler(analytics_db=analytics_db)
        response = await handler.handle_command("/stats@mybot", 123456)
        assert "STATISTIQUES" in response

    @pytest.mark.asyncio
    async def test_handle_command_error_handling(self):
        analytics_db = Mock()
        analytics_db.get_trades = Mock(side_effect=Exception("DB error"))
        handler = TelegramCommandHandler(analytics_db=analytics_db)
        response = await handler.handle_command("/stats", 123456)
        assert "Erreur" in response


class TestHandleStats:
    @pytest.mark.asyncio
    async def test_handle_stats_no_trades(self):
        analytics_db = Mock()
        analytics_db.get_trades = Mock(return_value=[])
        handler = TelegramCommandHandler(analytics_db=analytics_db, instance_port=5000)
        response = await handler.handle_stats(123456)
        assert "STATISTIQUES" in response
        assert "Aucun trade" in response

    @pytest.mark.asyncio
    async def test_handle_stats_with_trades(self):
        analytics_db = Mock()
        trades = [
            {
                "net_pnl_usdt": 10.0,
                "net_pnl_pct": 5.0,
                "date": "2026-03-29",
                "time": "10:00:00",
            },
            {
                "net_pnl_usdt": -5.0,
                "net_pnl_pct": -2.5,
                "date": "2026-03-29",
                "time": "11:00:00",
            },
            {
                "net_pnl_usdt": 20.0,
                "net_pnl_pct": 10.0,
                "date": "2026-03-29",
                "time": "12:00:00",
            },
        ]
        analytics_db.get_trades = Mock(return_value=trades)
        handler = TelegramCommandHandler(analytics_db=analytics_db, instance_port=5000)
        response = await handler.handle_stats(123456)
        assert "STATISTIQUES" in response
        assert "**Total Trades**: 3" in response
        assert "✅ **Wins**: 2" in response
        assert "❌ **Losses**: 1" in response
        assert "🎯 **Winrate**: 66.7%" in response
        assert "+25.00 USDT" in response

    @pytest.mark.asyncio
    async def test_handle_stats_error(self):
        analytics_db = Mock()
        analytics_db.get_trades = Mock(side_effect=Exception("Database error"))
        handler = TelegramCommandHandler(analytics_db=analytics_db)
        response = await handler.handle_stats(123456)
        assert "Erreur" in response


class TestHandleReport:
    @pytest.mark.asyncio
    async def test_handle_report_no_trades(self):
        analytics_db = Mock()
        analytics_db.get_trades = Mock(return_value=[])
        handler = TelegramCommandHandler(analytics_db=analytics_db, instance_port=5000)
        response = await handler.handle_report(123456)
        assert "RAPPORT" in response

    @pytest.mark.asyncio
    async def test_handle_report_with_trades(self):
        analytics_db = Mock()
        trades = [
            {
                "net_pnl_usdt": 10.0,
                "net_pnl_pct": 5.0,
                "direction": "LONG",
                "reason": "TP",
                "duration_seconds": 300,
            },
            {
                "net_pnl_usdt": -5.0,
                "net_pnl_pct": -2.5,
                "direction": "SHORT",
                "reason": "SL",
                "duration_seconds": 600,
            },
        ]
        analytics_db.get_trades = Mock(return_value=trades)
        handler = TelegramCommandHandler(analytics_db=analytics_db, instance_port=5000)
        response = await handler.handle_report(123456)
        assert "RAPPORT" in response
        assert "GLOBAL" in response

    @pytest.mark.asyncio
    async def test_handle_report_error(self):
        analytics_db = Mock()
        analytics_db.get_trades = Mock(side_effect=Exception("Error"))
        handler = TelegramCommandHandler(analytics_db=analytics_db)
        response = await handler.handle_report(123456)
        assert "Erreur" in response


class TestHandleStatus:
    @pytest.mark.asyncio
    async def test_handle_status_no_position(self):
        position_manager = Mock()
        position_manager.active_position = None
        handler = TelegramCommandHandler(
            position_manager=position_manager, instance_port=5000
        )
        response = await handler.handle_status(123456)
        assert "STATUT" in response
        assert "Aucune position active" in response

    @pytest.mark.asyncio
    async def test_handle_status_with_position(self):
        position_manager = Mock()
        active_position = Mock()
        active_position.symbol = "BTC/USDT"
        active_position.direction = "LONG"
        active_position.entry = 50000.0
        active_position.tp = 51000.0
        active_position.sl = 49000.0
        active_position.size = 100.0
        active_position.start_time = datetime.now().timestamp() - 300
        position_manager.active_position = active_position
        handler = TelegramCommandHandler(
            position_manager=position_manager, instance_port=5000
        )
        response = await handler.handle_status(123456)
        assert "STATUT" in response
        assert "POSITION ACTIVE" in response
        assert "BTC/USDT" in response

    @pytest.mark.asyncio
    async def test_handle_status_error(self):
        position_manager = Mock()
        position_manager.active_position = Mock(side_effect=Exception("Error"))
        handler = TelegramCommandHandler(position_manager=position_manager)
        response = await handler.handle_status(123456)
        assert "Erreur" in response


class TestHandleTrades:
    @pytest.mark.asyncio
    async def test_handle_trades_no_trades(self):
        analytics_db = Mock()
        analytics_db.get_trades = Mock(return_value=[])
        handler = TelegramCommandHandler(analytics_db=analytics_db, instance_port=5000)
        response = await handler.handle_trades(123456)
        assert "DERNIERS TRADES" in response
        assert "Aucun trade" in response

    @pytest.mark.asyncio
    async def test_handle_trades_with_trades(self):
        analytics_db = Mock()
        trades = [
            {
                "net_pnl_usdt": 10.0,
                "net_pnl_pct": 5.0,
                "symbol": "BTC/USDT",
                "direction": "LONG",
                "reason": "TP",
                "date": "2026-03-29",
                "time": "10:00:00",
            },
            {
                "net_pnl_usdt": -5.0,
                "net_pnl_pct": -2.5,
                "symbol": "ETH/USDT",
                "direction": "SHORT",
                "reason": "SL",
                "date": "2026-03-29",
                "time": "11:00:00",
            },
        ]
        analytics_db.get_trades = Mock(return_value=trades)
        handler = TelegramCommandHandler(analytics_db=analytics_db, instance_port=5000)
        response = await handler.handle_trades(123456)
        assert "DERNIERS 10 TRADES" in response
