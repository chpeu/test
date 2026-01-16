import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.analyzer import TechnicalAnalyzer
from core.position.recovery_mode import RecoveryModeManager
from config import TRADING_CONFIG
from utils.effective_config import clear_all_adjustments


class DummyPositionManager:
    def __init__(self, loss_streak: int):
        self.config = SimpleNamespace(recovery_mode_active=True, loss_streak=loss_streak)
        self.recovery_mode = RecoveryModeManager()

    def get_recovery_level(self, loss_streak: int):
        return self.recovery_mode.get_recovery_level(loss_streak)


class TestRecoveryGating(unittest.IsolatedAsyncioTestCase):
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

        self.analyzer.calculate_trend_data = AsyncMock(return_value={'trend': 'NEUTRAL', 'strength': 0, 'bonus': 0})
        self.analyzer_globals = TechnicalAnalyzer.__init__.__globals__

    def tearDown(self):
        TRADING_CONFIG.update(self.original_config)
        clear_all_adjustments()

    async def test_recovery_confluence_forced_refactor(self):
        TRADING_CONFIG['use_confluence'] = False
        TRADING_CONFIG['rsi_final_filter_enabled'] = False
        TRADING_CONFIG['recovery_refactor_enabled'] = True
        TRADING_CONFIG['recovery_shadow_compare'] = False
        TRADING_CONFIG['recovery_mode'] = {**TRADING_CONFIG.get('recovery_mode', {}), 'enabled': True}

        setup_1m = {
            'direction': 'LONG',
            'signals': ['mock'],
            'timeframe': '1m',
            'entry': 100,
            'sl': 90,
            'tp': 110,
            'atr': 1.0,
            'totalScore': 8.0,
            'long_score': 8.0,
            'short_score': 0.0,
            'price': 100,
            'volumeSpike': 1.2,
            'rsi': 50,
            'symbol': 'BTC/USDT'
        }
        setup_5m = None

        patches = {
            'check_spread': AsyncMock(return_value={'valid': True, 'spread_pct': 0.01, 'max_allowed': 0.05, 'quality': 'GOOD'}),
            'check_orderbook_imbalance': AsyncMock(return_value={'valid': True, 'ratio': 1.2, 'quality': 'GOOD', 'bid_value': 1000, 'ask_value': 800}),
            'detect_manipulation': MagicMock(return_value={'suspicious': False, 'reason': None}),
            'check_static_correlation': AsyncMock(return_value={'valid': True, 'reason': None})
        }

        with patch.object(self.analyzer, 'analyze_timeframe', side_effect=[setup_1m, setup_5m]):
            with patch.dict(self.analyzer_globals, patches):
                with patch('utils.helpers.DataLoggerHelper.is_available', return_value=False):
                    result = await self.analyzer.analyze_pair(
                        'BTC/USDT',
                        use_confluence=False,
                        return_reason=True,
                        position_manager=DummyPositionManager(loss_streak=5)
                    )

        self.assertIsNotNone(result)
        self.assertEqual(result.get('reject_category'), 'recovery_mode')
        self.assertIn('Confluence requise', result.get('reason', ''))
