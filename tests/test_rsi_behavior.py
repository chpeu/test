
import sys
import os
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import inspect

# Ajouter le chemin racine
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.analyzer import TechnicalAnalyzer
from config import TRADING_CONFIG
from utils.effective_config import clear_all_adjustments, set_regime_adjustments

class TestRSIBehavior(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Reset config avant chaque test
        self.original_config = TRADING_CONFIG.copy()
        clear_all_adjustments()
        
        # Mock dependencies
        self.client_mock = MagicMock()
        self.price_provider_mock = MagicMock()
        self.price_provider_mock.get_price = AsyncMock(return_value={'lastPrice': '100.0'})
        
        # Patch les sources originales des fonctions pour l'instanciation
        with patch('api.mexc.get_mexc_client', return_value=self.client_mock), \
             patch('api.price_provider.get_price_provider', return_value=self.price_provider_mock):
            
            self.analyzer = TechnicalAnalyzer()
            
        # Assurer que les attributs sont bien nos mocks
        self.analyzer.client = self.client_mock
        self.analyzer.price_provider = self.price_provider_mock
        
        # Mocker les composants qui pourraient bloquer analyze_pair
        self.analyzer.pair_scorer = MagicMock()
        # evaluate_pair est async
        self.analyzer.pair_scorer.evaluate_pair = AsyncMock(return_value={'score_adjustment': 0.0, 'effective_min_score': 8.0})
        self.analyzer.pair_scorer.get_score_adjustment = MagicMock(return_value=0.0)
        
        self.analyzer.circuit_breaker = MagicMock()
        self.analyzer.circuit_breaker.can_trade.return_value = True
        self.analyzer.circuit_breaker.is_symbol_paused.return_value = False
        self.analyzer.circuit_breaker.get_score_boost.return_value = 0.0
        
        self.analyzer.regime_selector = MagicMock()
        self.analyzer.regime_selector.get_active_config.return_value = {}
        # check_regime est async
        self.analyzer.regime_selector.check_regime = AsyncMock(return_value=('NORMAL', False))
        
        # Récupérer les globales du module pour patcher check_spread et autres
        self.analyzer_globals = TechnicalAnalyzer.__init__.__globals__
        
        # Mock calculate_trend_data sur l'instance pour éviter les warnings
        self.analyzer.calculate_trend_data = AsyncMock(return_value={'trend': 'NEUTRAL', 'strength': 0, 'bonus': 0})
        
    def tearDown(self):
        TRADING_CONFIG.update(self.original_config)
        clear_all_adjustments()

    async def test_rsi_final_filter_disabled(self):
        """Test 1: RSI Final désactivé -> Tout passe (Setup 5m = None)"""
        TRADING_CONFIG['rsi_final_filter_enabled'] = False
        TRADING_CONFIG['use_confluence'] = False
        
        # Setup LONG avec RSI extrême (75)
        indicators_1m = {'rsi': 75, 'adx': 25, 'atr': 1.0}
        setup_1m = {'direction': 'LONG', 'rsi': 75, 'signals': ['mock'], 'timeframe': '1m', 'entry': 100, 'sl': 90, 'tp': 110, 'atr': 1.0, 'score': 10, 'indicators': indicators_1m, 'symbol': 'BTC/USDT', 'condition_types': ['RSI_TEST']}
        setup_5m = None
        
        # Mock check_spread et check_orderbook_imbalance (AsyncMock car await)
        mock_check_spread = AsyncMock(return_value={'valid': True, 'spread_pct': 0.01, 'max_allowed': 0.05, 'quality': 'GOOD'})
        mock_calculate_trend = AsyncMock(return_value={'trend': 'NEUTRAL', 'strength': 0, 'bonus': 0})
        mock_orderbook = AsyncMock(return_value={'valid': True, 'ratio': 1.2, 'quality': 'GOOD', 'bid_value': 1000, 'ask_value': 800})
        
        patches = {
            'check_spread': mock_check_spread, 
            'calculate_trend_data': mock_calculate_trend,
            'check_orderbook_imbalance': mock_orderbook
        }
        
        with patch.object(self.analyzer, 'analyze_timeframe', side_effect=[setup_1m, setup_5m]):
            with patch.dict(self.analyzer_globals, patches):
                result = await self.analyzer.analyze_pair('BTC/USDT')
        
        self.assertIsNotNone(result)
        self.assertEqual(result.get('rsi'), 75)

    async def test_rsi_final_filter_disabled_dual(self):
        """Test 1b: RSI Final désactivé -> Tout passe (Setup 5m présent)"""
        TRADING_CONFIG['rsi_final_filter_enabled'] = False
        TRADING_CONFIG['use_confluence'] = False
        
        indicators_1m = {'rsi': 75, 'adx': 25, 'atr': 1.0}
        indicators_5m = {'rsi': 70, 'adx': 25, 'atr': 1.0}
        
        setup_1m = {'direction': 'LONG', 'rsi': 75, 'signals': ['mock'], 'timeframe': '1m', 'entry': 100, 'sl': 90, 'tp': 110, 'atr': 1.0, 'score': 10, 'indicators': indicators_1m, 'symbol': 'BTC/USDT', 'condition_types': ['RSI_TEST']}
        setup_5m = {'direction': 'LONG', 'rsi': 70, 'signals': ['mock'], 'timeframe': '5m', 'entry': 100, 'sl': 90, 'tp': 110, 'atr': 1.0, 'score': 10, 'indicators': indicators_5m, 'symbol': 'BTC/USDT', 'condition_types': ['RSI_TEST']}
        
        mock_check_spread = AsyncMock(return_value={'valid': True, 'spread_pct': 0.01, 'max_allowed': 0.05, 'quality': 'GOOD'})
        mock_calculate_trend = AsyncMock(return_value={'trend': 'NEUTRAL', 'strength': 0, 'bonus': 0})
        mock_orderbook = AsyncMock(return_value={'valid': True, 'ratio': 1.2, 'quality': 'GOOD', 'bid_value': 1000, 'ask_value': 800})
        
        patches = {
            'check_spread': mock_check_spread, 
            'calculate_trend_data': mock_calculate_trend,
            'check_orderbook_imbalance': mock_orderbook
        }
        
        with patch.object(self.analyzer, 'analyze_timeframe', side_effect=[setup_1m, setup_5m]):
            with patch.dict(self.analyzer_globals, patches):
                result = await self.analyzer.analyze_pair('BTC/USDT')
        
        self.assertIsNotNone(result)
        self.assertTrue(result.get('rsi') in [70, 75])

    async def test_rsi_final_filter_short_blocking(self):
        """Test: RSI Final bloque SHORT avec RSI trop bas"""
        TRADING_CONFIG['rsi_final_filter_enabled'] = True
        TRADING_CONFIG['rsi_final_short_min'] = 35
        TRADING_CONFIG['use_confluence'] = False
        
        # Setup SHORT avec RSI trop bas (25) - Doit être bloqué
        setup_1m = {'direction': 'SHORT', 'rsi': 25, 'signals': ['mock'], 'timeframe': '1m', 'entry': 100, 'sl': 110, 'tp': 90, 'atr': 1.0, 'score': 10, 'symbol': 'BTC/USDT', 'condition_types': ['RSI_TEST'], 'indicators': {'rsi': 25, 'adx': 25, 'atr': 1.0}}
        setup_5m = None
        
        mock_check_spread = AsyncMock(return_value={'valid': True})
        
        with patch.object(self.analyzer, 'analyze_timeframe', side_effect=[setup_1m, setup_5m]):
            with patch.dict(self.analyzer_globals, {'check_spread': mock_check_spread}):
                result = await self.analyzer.analyze_pair('BTC/USDT')
        
        self.assertIsNone(result)

    async def test_rsi_final_filter_enabled_blocking(self):
        """Test 2: RSI Final activé -> Bloque RSI extrême LONG"""
        TRADING_CONFIG['rsi_final_filter_enabled'] = True
        TRADING_CONFIG['rsi_final_long_max'] = 65
        TRADING_CONFIG['use_confluence'] = False
        
        # Setup LONG avec RSI extrême (75) - Doit être bloqué
        setup_1m = {'direction': 'LONG', 'rsi': 75, 'signals': ['mock'], 'timeframe': '1m', 'entry': 100, 'sl': 90, 'tp': 110, 'atr': 1.0, 'score': 10, 'symbol': 'BTC/USDT', 'condition_types': ['RSI_TEST'], 'indicators': {'rsi': 75, 'adx': 25, 'atr': 1.0}}
        setup_5m = None 
        
        mock_check_spread = AsyncMock(return_value={'valid': True})
        
        with patch.object(self.analyzer, 'analyze_timeframe', side_effect=[setup_1m, setup_5m]):
             with patch.dict(self.analyzer_globals, {'check_spread': mock_check_spread}):
                result = await self.analyzer.analyze_pair('BTC/USDT')
        
        self.assertIsNone(result)

    async def test_rsi_final_filter_enabled_passing(self):
        """Test 3: RSI Final activé -> Laisse passer RSI valide"""
        TRADING_CONFIG['rsi_final_filter_enabled'] = True
        TRADING_CONFIG['rsi_final_long_max'] = 65
        TRADING_CONFIG['use_confluence'] = False
        
        # Setup LONG avec RSI valide (55)
        setup_1m = {'direction': 'LONG', 'rsi': 55, 'signals': ['mock'], 'timeframe': '1m', 'entry': 100, 'sl': 90, 'tp': 110, 'atr': 1.0, 'score': 10}
        setup_5m = None
        
        mock_check_spread = AsyncMock(return_value={'valid': True, 'spread_pct': 0.01, 'max_allowed': 0.05, 'quality': 'GOOD'})
        mock_orderbook = AsyncMock(return_value={'valid': True, 'ratio': 1.2, 'quality': 'GOOD', 'bid_value': 1000, 'ask_value': 800})
        
        patches = {
            'check_spread': mock_check_spread,
            'check_orderbook_imbalance': mock_orderbook
        }
        
        with patch.object(self.analyzer, 'analyze_timeframe', side_effect=[setup_1m, setup_5m]):
             with patch.dict(self.analyzer_globals, patches):
                result = await self.analyzer.analyze_pair('BTC/USDT')
        
        self.assertIsNotNone(result)
        self.assertEqual(result['rsi'], 55)

    async def test_regime_interaction(self):
        """Test 4: Interaction Régime + RSI Final"""
        TRADING_CONFIG['rsi_final_filter_enabled'] = True
        TRADING_CONFIG['rsi_final_long_max'] = 65
        TRADING_CONFIG['market_regime_enabled'] = True
        
        # Activer un régime
        set_regime_adjustments({'min_score_required': 8.0})
        
        setup_1m = {'direction': 'LONG', 'rsi': 70, 'signals': ['mock'], 'timeframe': '1m', 'entry': 100, 'sl': 90, 'tp': 110, 'atr': 1.0, 'score': 10}
        
        mock_check_spread = AsyncMock(return_value={'valid': True})
        
        with patch.object(self.analyzer, 'analyze_timeframe', side_effect=[setup_1m, None]):
             with patch.dict(self.analyzer_globals, {'check_spread': mock_check_spread}):
                result = await self.analyzer.analyze_pair('BTC/USDT')
        
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
