#!/usr/bin/env python3
import sys
import os
import asyncio
import unittest
from unittest.mock import Mock, AsyncMock, patch

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_full_position_lifecycle():
    """Test cycle complet: scanner trouve setup → position ouverte → position fermée"""
    try:
        from core.callbacks import scanner_loop, position_check_loop

        # Mock analyzer qui trouve un setup
        mock_analyzer = AsyncMock()
        mock_analyzer.calculate_trend_data = AsyncMock(return_value={})
        mock_analyzer.analyze_pair = AsyncMock(return_value={
            "symbol": "BTC/USDT:USDT",
            "direction": "LONG",
            "entry": 50000.0,
            "price": 50000.0,
            "atr": 500.0,
            "atr5m": 250.0,
            "condition_types": ["EMA_CROSS"],
            "tp": 52000.0,
            "sl": 48000.0,
            "tp_sl_mode": "ATR",
            "score": 85,
            "indicators_1m": {"rsi": 60, "adx": 25, "ema9": 50100, "ema21": 49900},
            "indicators_5m": {"rsi": 58, "adx": 24, "ema9": 50050, "ema21": 49950}
        })

        # Mock position_manager
        mock_position = Mock()
        mock_position.symbol = "BTC/USDT:USDT"
        mock_position.entry = 50000.0
        mock_position.direction = "LONG"
        mock_position.sl = 49500.0
        mock_position.tp = 51000.0
        mock_position.size = 100.0
        mock_position.to_dict = Mock(return_value={
            "symbol": "BTC/USDT:USDT",
            "direction": "LONG",
            "entry": 50000.0
        })

        mock_pm = Mock()
        mock_pm.active_position = None
        mock_pm.calculate_position_size = Mock(return_value=100.0)
        mock_pm.open_position = Mock(return_value=mock_position)

        # Mock scanner avec scan_pair_for_setup qui retourne le setup
        mock_scanner = AsyncMock()
        mock_scanner.scan_top_pairs = AsyncMock(return_value=[
            {"symbol": "BTC/USDT:USDT", "score": 90}
        ])
        
        # Mock scan_pair_for_setup pour retourner le setup complet
        async def mock_scan_pair_for_setup(symbol):
            if symbol == "BTC/USDT:USDT":
                return {
                    "symbol": "BTC/USDT:USDT",
                    "direction": "LONG",
                    "entry": 50000.0,
                    "price": 50000.0,
                    "tp": 52000.0,
                    "sl": 48000.0,
                    "tp_sl_mode": "ATR",
                    "score": 85,
                    "atr": 500.0,
                    "indicators_1m": {"rsi": 60, "adx": 25, "ema9": 50100, "ema21": 49900},
                    "indicators_5m": {"rsi": 58, "adx": 24, "ema9": 50050, "ema21": 49950},
                    "condition_types": ["EMA_CROSS"],
                    "conditions": 1,
                    "totalScore": 85,
                    "timeframe": "1m"
                }
            return None

        # Mock ws_manager
        mock_ws = AsyncMock()

        mock_state = {
            "top_pairs": [{"symbol": "BTC/USDT:USDT"}],
            "active_position": None
        }
        mock_lock = asyncio.Lock()

        scanner_loop._scanner = mock_scanner
        scanner_loop._analyzer = mock_analyzer
        scanner_loop._position_manager = mock_pm
        scanner_loop._app_state = mock_state
        scanner_loop._scanner_lock = mock_lock
        scanner_loop._ws_manager = mock_ws

        # Mock TRADING_CONFIG, ML_CONFIG, advanced filters et scan_pair_for_setup
        with patch('config.TRADING_CONFIG', {
            'top_pairs_limit': 20,
            'use_confluence': False,
            'volume_multiplier': 1.0,
            'trend_timeframe': '15m',
            'account_size': 1000.0,
            'gb_filter_enabled': False
        }), \
        patch('config.ML_CONFIG', {'enabled': False}), \
        patch('core.callbacks.scanner_loop.check_whipsaw_filter', return_value=None), \
        patch('core.callbacks.scanner_loop.check_candle_close_filter', return_value=None), \
        patch('core.callbacks.scanner_loop.check_momentum_continuity', return_value=None):
            with patch('core.callbacks.scanner_loop.scan_pair_for_setup', side_effect=mock_scan_pair_for_setup):
                print("About to call scanner_loop_callback...")
                await scanner_loop.scanner_loop_callback()
                print("scanner_loop_callback completed")

        # Vérifier qu'une position a été ouverte
        print(f"open_position call count: {mock_pm.open_position.call_count}")
        print(f"mock_state['active_position']: {mock_state['active_position']}")
        
        if mock_pm.open_position.call_count == 0:
            print("ERROR: open_position was never called")
        else:
            print("SUCCESS: Position was opened")
            
        if mock_state['active_position'] is None:
            print("ERROR: active_position is still None")
        else:
            print("SUCCESS: active_position was set")

    except Exception as e:
        print(f"Exception occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_full_position_lifecycle())
