
import unittest
import sys
import os
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

# Add root path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.analyzer import TechnicalAnalyzer
from config import TRADING_CONFIG
from utils.effective_config import clear_all_adjustments

class TestRSIBehavior(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.original_config = TRADING_CONFIG.copy()
        clear_all_adjustments()
        
        self.client_mock = MagicMock()
        self.price_provider_mock = MagicMock()
        self.price_provider_mock.get_price = AsyncMock(return_value={'lastPrice': '100.0'})
        
        with patch('api.mexc.get_mexc_client', return_value=self.client_mock), \
             patch('api.price_provider.get_price_provider', return_value=self.price_provider_mock):
            self.analyzer = TechnicalAnalyzer()
            
        self.analyzer.client = self.client_mock
        self.analyzer.price_provider = self.price_provider_mock
        
        self.analyzer.pair_scorer = MagicMock()
        self.analyzer.pair_scorer.evaluate_pair = AsyncMock(return_value={'score_adjustment': 0.0, 'effective_min_score': 8.0})
        self.analyzer.pair_scorer.get_score_adjustment = MagicMock(return_value=0.0)
        
        self.analyzer.circuit_breaker = MagicMock()
        self.analyzer.circuit_breaker.can_trade.return_value = True
        self.analyzer.circuit_breaker.is_symbol_paused.return_value = False
        self.analyzer.circuit_breaker.get_score_boost.return_value = 0.0
        
        self.analyzer.regime_selector = MagicMock()
        self.analyzer.regime_selector.get_active_config.return_value = {}
        self.analyzer.regime_selector.check_regime = AsyncMock(return_value=('NORMAL', False))
        
        self.analyzer_globals = TechnicalAnalyzer.__init__.__globals__
        self.analyzer.calculate_trend_data = AsyncMock(return_value={'trend': 'NEUTRAL', 'strength': 0, 'bonus': 0})

    def tearDown(self):
        TRADING_CONFIG.update(self.original_config)
        clear_all_adjustments()

    async def test_rsi_final_filter_disabled(self):
        print("Starting test_rsi_final_filter_disabled...")
        TRADING_CONFIG['rsi_final_filter_enabled'] = False
        TRADING_CONFIG['use_confluence'] = False
        
        indicators_1m = {'rsi': 75, 'adx': 25, 'atr': 1.0}
        setup_1m = {'direction': 'LONG', 'rsi': 75, 'signals': ['mock'], 'timeframe': '1m', 'entry': 100, 'sl': 90, 'tp': 110, 'atr': 1.0, 'score': 10, 'indicators': indicators_1m, 'symbol': 'BTC/USDT', 'condition_types': ['RSI_TEST']}
        setup_5m = None
        
        mock_check_spread = AsyncMock(return_value={'valid': True, 'spread_pct': 0.01, 'max_allowed': 0.05, 'quality': 'GOOD'})
        mock_calculate_trend = AsyncMock(return_value={'trend': 'NEUTRAL', 'strength': 0, 'bonus': 0})
        mock_orderbook = AsyncMock(return_value={'valid': True, 'ratio': 1.2, 'quality': 'GOOD', 'bid_value': 1000, 'ask_value': 800})
        mock_detect_manipulation = MagicMock(return_value={'suspicious': False, 'reason': None})
        mock_correlation = AsyncMock(return_value={'valid': True, 'reason': None})
        
        patches = {
            'check_spread': mock_check_spread, 
            'calculate_trend_data': mock_calculate_trend,
            'check_orderbook_imbalance': mock_orderbook,
            'detect_manipulation': mock_detect_manipulation,
            'check_static_correlation': mock_correlation
        }
        
        with patch.object(self.analyzer, 'analyze_timeframe', side_effect=[setup_1m, setup_5m]):
            with patch.dict(self.analyzer_globals, patches):
                try:
                    result = await self.analyzer.analyze_pair('BTC/USDT')
                    print(f"Result: {result}")
                except Exception as e:
                    print(f"Caught exception in test: {e}")
                    import traceback
                    traceback.print_exc()
                    result = None
        
        if result is None:
            print("FAILURE: result is None")
        else:
            print("SUCCESS: result is not None")

if __name__ == '__main__':
    unittest.main()
