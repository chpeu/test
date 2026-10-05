"""
Tests unitaires pour backtesting/engine.py
"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import numpy as np
import time

from backtesting.engine import BacktestEngine
from core.analytics_database import AnalyticsDatabase
from trading.abstract_trading_manager import TradingPosition
from datetime import datetime


class TestBacktestEngineInit:
    """Tests d'initialisation BacktestEngine"""

    def test_init_default(self):
        """Initialisation avec paramètres par défaut"""
        engine = BacktestEngine()

        assert engine.initial_capital == 1000.0
        assert engine.backtest_id.startswith("bt_")
        assert "backtest_" in engine.session_id
        assert len(engine.equity_curve) == 1
        assert engine.equity_curve[0] == 1000.0

    def test_init_custom_capital(self):
        """Initialisation avec capital personnalisé"""
        engine = BacktestEngine(initial_capital=5000.0)

        assert engine.initial_capital == 5000.0
        assert engine.equity_curve[0] == 5000.0

    def test_init_with_analytics_db(self):
        """Initialisation avec AnalyticsDatabase"""
        mock_db = Mock(spec=AnalyticsDatabase)

        engine = BacktestEngine(analytics_db=mock_db)

        assert engine.analytics_db == mock_db

    def test_init_with_config(self):
        """Initialisation avec configuration personnalisée"""
        custom_config = {"tp_pct": 0.5, "sl_pct": 0.3}

        engine = BacktestEngine(config=custom_config)

        assert engine.config["tp_pct"] == 0.5
        assert engine.config["sl_pct"] == 0.3


class TestGenerateBacktestID:
    """Tests _generate_backtest_id"""

    def test_id_format(self):
        """Format ID backtest"""
        engine = BacktestEngine()

        assert engine.backtest_id.startswith("bt_")
        parts = engine.backtest_id.split("_")
        assert len(parts) == 3
        assert parts[0] == "bt"

    def test_id_includes_hash(self):
        """ID inclut hash configuration"""
        engine = BacktestEngine()

        assert "_" in engine.backtest_id
        assert len(engine.backtest_id.split("_")) == 3


class TestLoadHistoricalData:
    """Tests load_historical_data"""

    def test_load_method_exists(self):
        """Méthode load_historical_data existe"""
        engine = BacktestEngine()

        assert hasattr(engine, "load_historical_data")
        assert callable(engine.load_historical_data)


class TestCalculatePnL:
    """Tests calculate_pnl"""

    def test_calculate_pnl_long(self):
        """Calcul PnL position longue"""
        engine = BacktestEngine()

        position = TradingPosition(
            symbol="BTC/USDT:USDT",
            direction="LONG",
            entry=100.0,
            size=1.0,
            sl=95.0,
            tp=105.0,
        )

        pnl = engine.calculate_pnl(position, 105.0)

        # calculate_pnl retourne gross_pnl_pct (sans fees)
        assert "gross_pnl_pct" in pnl
        assert abs(pnl["gross_pnl_pct"] - 5.0) < 0.01

    def test_calculate_pnl_short(self):
        """Calcul PnL position courte"""
        engine = BacktestEngine()

        position = TradingPosition(
            symbol="BTC/USDT:USDT",
            direction="SHORT",
            entry=105.0,
            size=1.0,
            sl=110.0,
            tp=100.0,
        )

        pnl = engine.calculate_pnl(position, 100.0)

        assert "gross_pnl_pct" in pnl
        assert abs(pnl["gross_pnl_pct"] - 4.76) < 0.01

    def test_calculate_pnl_loss(self):
        """Calcul PnL perte"""
        engine = BacktestEngine()

        position = TradingPosition(
            symbol="BTC/USDT:USDT",
            direction="LONG",
            entry=100.0,
            size=1.0,
            sl=95.0,
            tp=105.0,
        )

        pnl = engine.calculate_pnl(position, 95.0)

        assert "gross_pnl_pct" in pnl
        assert abs(pnl["gross_pnl_pct"] - (-5.0)) < 0.01


class TestCalculatePnLPct:
    """Tests calculate_pnl_pct"""

    def test_calculate_pnl_pct_long(self):
        """Calcul PnL% position longue"""
        engine = BacktestEngine()

        position = TradingPosition(
            symbol="BTC/USDT:USDT",
            direction="LONG",
            entry=100.0,
            size=1.0,
            sl=95.0,
            tp=105.0,
        )

        pnl_pct = engine.calculate_pnl_pct(position, 105.0)

        assert pnl_pct == 5.0

    def test_calculate_pnl_pct_short(self):
        """Calcul PnL% position courte"""
        engine = BacktestEngine()

        position = TradingPosition(
            symbol="BTC/USDT:USDT",
            direction="SHORT",
            entry=105.0,
            size=1.0,
            sl=110.0,
            tp=100.0,
        )

        pnl_pct = engine.calculate_pnl_pct(position, 100.0)

        # (105-100)/105 * 100 = 4.761904761904762
        assert abs(pnl_pct - 4.761904761904762) < 0.001


class TestGetStats:
    """Tests get_stats"""

    def test_get_stats_empty(self):
        """Statistiques vides"""
        engine = BacktestEngine()

        stats = engine.get_stats()

        assert isinstance(stats, dict)
        assert "total_trades" in stats
        assert "winrate" in stats
        assert "total_pnl" in stats


class TestCheckTPSL:
    """Tests check_tp_sl"""

    def test_check_tp_sl_method_exists(self):
        """Méthode check_tp_sl existe"""
        engine = BacktestEngine()

        assert hasattr(engine, "check_tp_sl")
        assert callable(engine.check_tp_sl)


class TestCheckEarlyInvalidation:
    """Tests check_early_invalidation"""

    def test_check_early_invalidation_method_exists(self):
        """Méthode check_early_invalidation existe"""
        engine = BacktestEngine()

        assert hasattr(engine, "check_early_invalidation")
        assert callable(engine.check_early_invalidation)


class TestApplyFeesSlippage:
    """Tests apply_fees_slippage"""

    def test_apply_fees_slippage_exists(self):
        """Méthode apply_fees_slippage existe"""
        engine = BacktestEngine()

        assert hasattr(engine, "apply_fees_slippage")
        assert callable(engine.apply_fees_slippage)


class TestPreloadData:
    """Tests preload_data"""

    def test_preload_data_method_exists(self):
        """Méthode preload_data existe"""
        engine = BacktestEngine()

        assert hasattr(engine, "preload_data")
        assert callable(engine.preload_data)


class TestWalkForwardAnalysis:
    """Tests walk_forward_analysis"""

    def test_walk_forward_analysis_exists(self):
        """Méthode walk_forward_analysis existe"""
        engine = BacktestEngine()

        assert hasattr(engine, "walk_forward_analysis")
        assert callable(engine.walk_forward_analysis)


class TestRunBacktest:
    """Tests run_backtest"""

    def test_run_backtest_method_exists(self):
        """Méthode run_backtest existe"""
        engine = BacktestEngine()

        assert hasattr(engine, "run_backtest")
        assert callable(engine.run_backtest)


class TestPositionManagement:
    """Tests gestion des positions"""

    def test_open_position_method_exists(self):
        """Méthode open_position existe"""
        engine = BacktestEngine()

        assert hasattr(engine, "open_position")
        assert callable(engine.open_position)

    def test_close_position_method_exists(self):
        """Méthode close_position existe"""
        engine = BacktestEngine()

        assert hasattr(engine, "close_position")
        assert callable(engine.close_position)


class TestUpdateMethods:
    """Tests méthodes de mise à jour"""

    def test_update_break_even_exists(self):
        """Méthode update_break_even existe"""
        engine = BacktestEngine()

        assert hasattr(engine, "update_break_even")
        assert callable(engine.update_break_even)

    def test_update_trailing_stop_exists(self):
        """Méthode update_trailing_stop existe"""
        engine = BacktestEngine()

        assert hasattr(engine, "update_trailing_stop")
        assert callable(engine.update_trailing_stop)


class TestEventHandler:
    """Tests événements"""

    def test_on_position_opened_exists(self):
        """Méthode on_position_opened existe"""
        engine = BacktestEngine()

        assert hasattr(engine, "on_position_opened")
        assert callable(engine.on_position_opened)

    def test_on_position_closed_exists(self):
        """Méthode on_position_closed existe"""
        engine = BacktestEngine()

        assert hasattr(engine, "on_position_closed")
        assert callable(engine.on_position_closed)


class TestTickHandler:
    """Tests handler tick"""

    def test_on_tick_exists(self):
        """Méthode on_tick existe"""
        engine = BacktestEngine()

        assert hasattr(engine, "on_tick")
        assert callable(engine.on_tick)


class TestExecuteOrder:
    """Tests exécution d'ordres"""

    def test_execute_order_exists(self):
        """Méthode execute_order existe"""
        engine = BacktestEngine()

        assert hasattr(engine, "execute_order")
        assert callable(engine.execute_order)


class TestGetCurrentPrice:
    """Tests prix courant"""

    def test_get_current_price_exists(self):
        """Méthode get_current_price existe"""
        engine = BacktestEngine()

        assert hasattr(engine, "get_current_price")
        assert callable(engine.get_current_price)


class TestGetCurrentTimestamp:
    """Tests timestamp courant"""

    def test_get_current_timestamp_exists(self):
        """Méthode get_current_timestamp existe"""
        engine = BacktestEngine()

        assert hasattr(engine, "get_current_timestamp")
        assert callable(engine.get_current_timestamp)
