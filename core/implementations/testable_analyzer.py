#!/usr/bin/env python3
"""
TestableAnalyzer - Trade Cursor v7.0
Version testable du TechnicalAnalyzer avec wrapper pattern
ZÉRO RISQUE - Code existant inchangé, wrapper testable à côté
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from core.interfaces.analyzer_interface import (
    IAnalyzer, 
    AnalysisSetup, 
    AnalysisResult, 
    AnalyzerConfig,
    setup_from_legacy_dict,
    result_from_legacy_dict,
    setup_to_legacy_dict
)

logger = logging.getLogger(__name__)


class TestableAnalyzer(IAnalyzer):
    """
    TechnicalAnalyzer testable avec wrapper pattern
    
    Approche:
    - Mode test: Utilise données mockées
    - Mode legacy: Délègue vers TechnicalAnalyzer existant
    - Même interface pour les deux modes
    - ZÉRO RISQUE - code existant inchangé
    """
    
    def __init__(self, config: AnalyzerConfig, legacy_analyzer=None, dependencies: Optional[Dict[str, Any]] = None):
        self.config = config
        self.dependencies = dependencies or {}
        self.test_mode = config.test_mode
        
        # Analyzer legacy pour délégation
        self._legacy_analyzer = legacy_analyzer
        
        # Dépendances injectées avec fallbacks
        self._init_dependencies()
        
        logger.info(f"✅ TestableAnalyzer initialisé (test_mode: {self.test_mode})")
    
    def _init_dependencies(self):
        """Initialiser dépendances avec fallbacks"""
        try:
            # Client MEXC
            if 'mexc_client' in self.dependencies:
                self.mexc_client = self.dependencies['mexc_client']
            else:
                self.mexc_client = MockMEXCClient()
            
            # Price Provider
            if 'price_provider' in self.dependencies:
                self.price_provider = self.dependencies['price_provider']
            else:
                self.price_provider = MockPriceProvider()
                
            # Pair Scorer
            if 'pair_scorer' in self.dependencies:
                self.pair_scorer = self.dependencies['pair_scorer']
            else:
                self.pair_scorer = MockPairScorer()
                
            # Circuit Breaker
            if 'circuit_breaker' in self.dependencies:
                self.circuit_breaker = self.dependencies['circuit_breaker']
            else:
                self.circuit_breaker = MockCircuitBreaker()
                
            # Regime Selector
            if 'regime_selector' in self.dependencies:
                self.regime_selector = self.dependencies['regime_selector']
            else:
                self.regime_selector = MockRegimeSelector()
                
            # Correlation Filter
            if 'correlation_filter' in self.dependencies:
                self.correlation_filter = self.dependencies['correlation_filter']
            else:
                self.correlation_filter = MockCorrelationFilter()
                
        except Exception as e:
            logger.error(f"Dependency initialization failed: {e}")
            self._init_fallback_dependencies()
    
    def _init_fallback_dependencies(self):
        """Fallbacks d'urgence"""
        logger.warning("🔧 Utilisation analyzer dependencies fallback")
        self.mexc_client = MockMEXCClient()
        self.price_provider = MockPriceProvider()
        self.pair_scorer = MockPairScorer()
        self.circuit_breaker = MockCircuitBreaker()
        self.regime_selector = MockRegimeSelector()
        self.correlation_filter = MockCorrelationFilter()
    
    async def analyze_pair_testable(
        self, 
        symbol: str, 
        mock_data: Optional[Dict[str, Any]] = None,
        use_confluence: bool = True,
        return_reason: bool = False,
        position_manager=None
    ) -> AnalysisResult:
        """
        Analyser paire - version testable ou délégation vers legacy
        """
        try:
            logger.debug(f"Analyzing {symbol} (test_mode: {self.test_mode})")
            
            if self.test_mode or mock_data:
                # Mode test avec données mockées
                return await self._analyze_with_mocks(symbol, mock_data, use_confluence, position_manager)
            
            elif self._legacy_analyzer:
                # Délégation vers analyzer existant
                return await self._analyze_with_legacy(symbol, use_confluence, return_reason, position_manager)
            
            else:
                # Fallback vers mode test
                logger.warning("No legacy analyzer, falling back to mock analysis")
                return await self._analyze_with_mocks(symbol, mock_data, use_confluence, position_manager)
                
        except Exception as e:
            logger.error(f"Analyze pair failed: {e}")
            return AnalysisResult(
                False, None, f"Analysis error: {e}", 
                reject_category="analysis_error"
            )
    
    async def _analyze_with_legacy(
        self, 
        symbol: str, 
        use_confluence: bool, 
        return_reason: bool, 
        position_manager
    ) -> AnalysisResult:
        """Analyser via legacy analyzer avec conversion"""
        try:
            # Appel legacy method
            legacy_result = await self._legacy_analyzer.analyze_pair(
                symbol, 
                use_confluence=use_confluence,
                return_reason=return_reason,
                position_manager=position_manager
            )
            
            # Convertir résultat legacy
            if legacy_result is None:
                return AnalysisResult(
                    False, None, "No opportunity found",
                    reject_category="no_opportunity"
                )
            
            # Legacy retourne setup directement ou dict avec reason
            if isinstance(legacy_result, dict) and 'reason' in legacy_result:
                return AnalysisResult(
                    False, None, 
                    legacy_result.get('reason', 'Rejected by legacy'),
                    reject_category=legacy_result.get('reject_category', 'legacy_reject')
                )
            
            # Convertir setup legacy en AnalysisResult
            setup = setup_from_legacy_dict(legacy_result)
            return AnalysisResult(
                True, setup, "Legacy analysis successful",
                is_opportunity=True
            )
            
        except Exception as e:
            logger.error(f"Legacy analysis failed: {e}")
            # Fallback vers mock
            return await self._analyze_with_mocks(symbol, None, use_confluence, position_manager)
    
    async def _analyze_with_mocks(
        self, 
        symbol: str, 
        mock_data: Optional[Dict[str, Any]],
        use_confluence: bool,
        position_manager
    ) -> AnalysisResult:
        """Analyser avec données mockées pour tests"""
        try:
            logger.debug(f"Mock analysis for {symbol}")
            
            # Données par défaut ou fournies
            if not mock_data:
                mock_data = self._generate_default_mock_data(symbol)
            
            # Simuler délai d'analyse
            await asyncio.sleep(0.001)
            
            # Analyser timeframes
            setup_1m = await self.analyze_timeframe(symbol, '1m', mock_data)
            setup_5m = await self.analyze_timeframe(symbol, '5m', mock_data) if use_confluence else None
            
            # Vérifier si opportunity
            if not setup_1m:
                return AnalysisResult(
                    False, None, "No setup found on 1m",
                    reject_category="no_setup_1m"
                )
            
            # Calculer confluence si requis
            if use_confluence and setup_5m:
                confluence_data = await self.calculate_confluence_score(setup_1m, setup_5m, symbol)
                if not confluence_data.get('valid', False):
                    return AnalysisResult(
                        False, None, f"Confluence failed: {confluence_data.get('reason')}",
                        reject_category="confluence_failed"
                    )
                setup_1m.total_score = confluence_data.get('final_score', setup_1m.total_score)
            
            # Appliquer filtres
            filters_result = await self.apply_filters(symbol, setup_1m, mock_data)
            if not filters_result.get('all_passed', True):
                failed_filters = [f for f, passed in filters_result.get('results', {}).items() if not passed]
                return AnalysisResult(
                    False, None, f"Filters failed: {', '.join(failed_filters)}",
                    reject_category="filters_failed",
                    filters_passed=filters_result.get('results', {})
                )
            
            # Vérifier score minimum
            recovery_state = position_manager.get_recovery_state(mock_data.get('loss_streak', 0)) if position_manager else {}
            min_score = self.get_min_score_required(symbol, recovery_state)
            
            if setup_1m.total_score < min_score:
                return AnalysisResult(
                    False, None, f"Score insuffisant ({setup_1m.total_score:.1f} < {min_score:.1f})",
                    reject_category="score_insufficient"
                )
            
            # Validation market conditions
            market_validation = await self.validate_market_conditions(symbol, mock_data)
            if not market_validation.get('valid', True):
                return AnalysisResult(
                    False, None, f"Market conditions: {market_validation.get('reason')}",
                    reject_category="market_conditions"
                )
            
            # Success - retourner setup
            return AnalysisResult(
                True, setup_1m, "Mock analysis successful",
                is_opportunity=True,
                final_score=setup_1m.total_score,
                filters_passed=filters_result.get('results', {})
            )
            
        except Exception as e:
            logger.error(f"Mock analysis failed: {e}")
            return AnalysisResult(
                False, None, f"Mock analysis error: {e}",
                reject_category="mock_error"
            )
    
    async def analyze_timeframe(
        self, 
        symbol: str, 
        timeframe: str,
        market_data: Optional[Dict[str, Any]] = None
    ) -> Optional[AnalysisSetup]:
        """Analyser timeframe spécifique"""
        try:
            await asyncio.sleep(0.001)  # Simule latence
            
            if not market_data:
                market_data = self._generate_default_mock_data(symbol)
            
            # Récupérer données timeframe
            tf_data = market_data.get(f'data_{timeframe}', market_data)
            
            # Vérifier si setup détecté
            base_score = tf_data.get('base_score', 75.0)
            direction = tf_data.get('direction', 'LONG')
            
            # Score trop faible = pas d'opportunity
            if base_score < 60.0:
                return None
            
            # Créer setup
            entry_price = tf_data.get('entry_price', 100.0)
            atr = tf_data.get('atr', 1.0)
            
            setup = AnalysisSetup(
                symbol=symbol,
                direction=direction,
                timeframe=timeframe,
                entry_price=entry_price,
                sl_price=tf_data.get('sl_price', entry_price - atr),
                tp_price=tf_data.get('tp_price', entry_price + atr * 2),
                atr=atr,
                total_score=base_score,
                long_score=base_score if direction == 'LONG' else 0,
                short_score=base_score if direction == 'SHORT' else 0,
                signals=[f'{timeframe}_signal'],
                rsi_1m=tf_data.get('rsi_1m', 35.0),
                rsi_5m=tf_data.get('rsi_5m', 32.0),
                macd_1m=tf_data.get('macd_1m', 0.15),
                macd_5m=tf_data.get('macd_5m', 0.12),
                volume_spike=tf_data.get('volume_spike', 1.2)
            )
            
            return setup
            
        except Exception as e:
            logger.error(f"Analyze timeframe {timeframe} failed: {e}")
            return None
    
    async def calculate_confluence_score(
        self,
        setup_1m: Optional[AnalysisSetup],
        setup_5m: Optional[AnalysisSetup],
        symbol: str
    ) -> Dict[str, Any]:
        """Calculer confluence entre timeframes"""
        try:
            if not setup_1m or not setup_5m:
                return {'valid': False, 'reason': 'Missing setups'}
            
            # Vérifier direction identique
            if setup_1m.direction != setup_5m.direction:
                return {'valid': False, 'reason': 'Direction mismatch'}
            
            # Calculer score confluence (moyenne pondérée)
            confluence_score = (setup_1m.total_score * 0.6) + (setup_5m.total_score * 0.4)
            
            # Bonus si scores proches
            score_diff = abs(setup_1m.total_score - setup_5m.total_score)
            if score_diff < 10:
                confluence_score += 5  # Bonus cohérence
            
            return {
                'valid': True,
                'confluence_score': confluence_score,
                'final_score': confluence_score,
                'score_1m': setup_1m.total_score,
                'score_5m': setup_5m.total_score,
                'direction_match': True
            }
            
        except Exception as e:
            logger.error(f"Calculate confluence failed: {e}")
            return {'valid': False, 'reason': f'Error: {e}'}
    
    async def apply_filters(
        self,
        symbol: str,
        setup: AnalysisSetup,
        market_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Appliquer filtres de validation"""
        try:
            results = {}
            
            # Filtre spread
            if self.config.spread_filter_enabled:
                spread_pct = market_data.get('spread_pct', 0.02)
                results['spread'] = spread_pct <= self.config.max_spread_pct
            else:
                results['spread'] = True
            
            # Filtre volume
            if self.config.volume_filter_enabled:
                volume_ratio = market_data.get('volume_ratio', 2.0)
                results['volume'] = volume_ratio >= self.config.min_volume_ratio
            else:
                results['volume'] = True
            
            # Filtre corrélation
            if self.config.correlation_filter_enabled:
                correlation_check = await self.correlation_filter.check_correlation(symbol, market_data)
                results['correlation'] = correlation_check.get('valid', True)
            else:
                results['correlation'] = True
            
            # Filtre RSI final
            if self.config.rsi_final_filter_enabled:
                rsi = setup.rsi_1m or 50
                if setup.direction == 'LONG':
                    results['rsi'] = rsi <= self.config.rsi_oversold_threshold
                else:
                    results['rsi'] = rsi >= self.config.rsi_overbought_threshold
            else:
                results['rsi'] = True
            
            all_passed = all(results.values())
            
            return {
                'all_passed': all_passed,
                'results': results,
                'failed_filters': [f for f, passed in results.items() if not passed]
            }
            
        except Exception as e:
            logger.error(f"Apply filters failed: {e}")
            return {'all_passed': False, 'error': str(e)}
    
    def calculate_score_adjustments(
        self,
        base_score: float,
        symbol: str,
        loss_streak: int = 0,
        market_conditions: Optional[Dict[str, Any]] = None
    ) -> Dict[str, float]:
        """Calculer ajustements score"""
        try:
            adjustments = {
                'base_score': base_score,
                'recovery_boost': 0.0,
                'circuit_breaker_penalty': 0.0,
                'regime_adjustment': 0.0,
                'final_score': base_score
            }
            
            # Recovery boost
            if loss_streak >= 2:
                if loss_streak >= 5:
                    adjustments['recovery_boost'] = 2.5
                elif loss_streak >= 3:
                    adjustments['recovery_boost'] = 1.5
                else:
                    adjustments['recovery_boost'] = 0.5
            
            # Circuit breaker penalty
            cb_penalty = self.circuit_breaker.get_penalty(symbol)
            adjustments['circuit_breaker_penalty'] = cb_penalty
            
            # Regime adjustment
            regime_data = self.regime_selector.get_adjustment(symbol, market_conditions or {})
            adjustments['regime_adjustment'] = regime_data.get('score_adjustment', 0.0)
            
            # Score final
            final_score = base_score + adjustments['recovery_boost'] - adjustments['circuit_breaker_penalty'] + adjustments['regime_adjustment']
            adjustments['final_score'] = max(0, final_score)
            
            return adjustments
            
        except Exception as e:
            logger.error(f"Calculate score adjustments failed: {e}")
            return {'base_score': base_score, 'final_score': base_score, 'error': str(e)}
    
    def get_min_score_required(
        self,
        symbol: str,
        recovery_state: Optional[Dict[str, Any]] = None,
        market_regime: Optional[str] = None
    ) -> float:
        """Obtenir score minimum requis"""
        try:
            base_min_score = self.config.min_score_base
            
            # Ajustement recovery
            recovery_boost = 0.0
            if recovery_state and recovery_state.get('active', False):
                recovery_boost = recovery_state.get('min_score_boost', 0.0)
            
            # Ajustement régime
            regime_adjustment = 0.0
            if market_regime == 'VOLATILE':
                regime_adjustment = 5.0  # Score plus élevé requis
            elif market_regime == 'STABLE':
                regime_adjustment = -2.0  # Score plus bas accepté
            
            min_score = base_min_score + recovery_boost + regime_adjustment
            return max(60.0, min_score)  # Minimum absolu 60
            
        except Exception as e:
            logger.error(f"Get min score failed: {e}")
            return self.config.min_score_base
    
    async def validate_market_conditions(
        self,
        symbol: str,
        market_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Valider conditions marché"""
        try:
            await asyncio.sleep(0.001)  # Simule vérification
            
            # Vérifier manipulation
            manipulation_score = market_data.get('manipulation_score', 0.1)
            if manipulation_score > 0.8:
                return {
                    'valid': False, 
                    'reason': f'Manipulation suspected: {manipulation_score:.2f}'
                }
            
            # Vérifier liquidité
            liquidity_ratio = market_data.get('liquidity_ratio', 2.0)
            if liquidity_ratio < 1.0:
                return {
                    'valid': False,
                    'reason': f'Low liquidity: {liquidity_ratio:.2f}'
                }
            
            # Vérifier volatilité excessive
            volatility_1h = market_data.get('volatility_1h', 0.02)
            if volatility_1h > 0.10:  # 10% volatilité horaire max
                return {
                    'valid': False,
                    'reason': f'Excessive volatility: {volatility_1h:.3f}'
                }
            
            return {
                'valid': True,
                'checks_passed': ['manipulation', 'liquidity', 'volatility']
            }
            
        except Exception as e:
            logger.error(f"Validate market conditions failed: {e}")
            return {'valid': True}  # Default pass on error
    
    def _generate_default_mock_data(self, symbol: str) -> Dict[str, Any]:
        """Générer données par défaut pour tests"""
        base_price = 100.0
        if 'BTC' in symbol:
            base_price = 45000.0
        elif 'ETH' in symbol:
            base_price = 3000.0
        
        return {
            'base_score': 80.0,
            'direction': 'LONG',
            'entry_price': base_price,
            'sl_price': base_price * 0.98,
            'tp_price': base_price * 1.03,
            'atr': base_price * 0.015,
            'rsi_1m': 35.0,
            'rsi_5m': 32.0,
            'macd_1m': 0.15,
            'macd_5m': 0.12,
            'volume_spike': 1.5,
            'spread_pct': 0.01,
            'volume_ratio': 2.0,
            'manipulation_score': 0.1,
            'liquidity_ratio': 2.5,
            'volatility_1h': 0.02,
            'loss_streak': 0
        }


# =============================================================================
# MOCKS POUR DÉPENDANCES ANALYZER
# =============================================================================

class MockMEXCClient:
    """Mock client MEXC pour tests"""
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100):
        """Mock fetch OHLCV"""
        await asyncio.sleep(0.001)
        return [[1609459200000, 100, 101, 99, 100.5, 1000] for _ in range(limit)]
    
    async def fetch_ticker(self, symbol: str):
        """Mock fetch ticker"""
        await asyncio.sleep(0.001)
        return {'last': 100.0, 'bid': 99.9, 'ask': 100.1, 'baseVolume': 1000000}


class MockPriceProvider:
    """Mock price provider pour tests"""
    
    async def get_price(self, symbol: str):
        """Mock get price"""
        await asyncio.sleep(0.001)
        return {'lastPrice': '100.0', 'bidPrice': '99.9', 'askPrice': '100.1'}


class MockPairScorer:
    """Mock pair scorer pour tests"""
    
    async def evaluate_pair(self, symbol: str):
        """Mock evaluate pair"""
        await asyncio.sleep(0.001)
        return {'score_adjustment': 0.0, 'effective_min_score': 75.0}
    
    def get_score_adjustment(self, symbol: str):
        """Mock get score adjustment"""
        return 0.0


class MockCircuitBreaker:
    """Mock circuit breaker pour tests"""
    
    def can_trade(self, symbol: str):
        """Mock can trade"""
        return True
    
    def is_symbol_paused(self, symbol: str):
        """Mock is paused"""
        return False
    
    def get_penalty(self, symbol: str):
        """Mock get penalty"""
        return 0.0


class MockRegimeSelector:
    """Mock regime selector pour tests"""
    
    def get_active_config(self):
        """Mock get active config"""
        return {}
    
    async def check_regime(self, market_data: Dict):
        """Mock check regime"""
        await asyncio.sleep(0.001)
        return ('NORMAL', False)
    
    def get_adjustment(self, symbol: str, market_data: Dict):
        """Mock get adjustment"""
        return {'score_adjustment': 0.0}


class MockCorrelationFilter:
    """Mock correlation filter pour tests"""
    
    async def check_correlation(self, symbol: str, market_data: Dict):
        """Mock check correlation"""
        await asyncio.sleep(0.001)
        return {'valid': True, 'correlation': 0.5}
