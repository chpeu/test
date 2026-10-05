"""
Mock Scanner Components - Trade Cursor v7.0 Phase 3
Composants mock pour tests et développement Scanner
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import random
import asyncio

from ..interfaces.scanner_interfaces import (
    IMarketDataCollector, IScalabilityScorer, IPairFilter, IScanPipeline,
    IScannerOrchestrator, IScanLogger, OrderbookData, TickerData, OHLCVData,
    MarketData, ScoringResult, ScoringMetrics, PairFilterResult, FilterConfig,
    ScanResult, ScanBatchResult, ScanPipelineResult, ScannerConfig,
    ScanStatus, DataSource, ScanPipelineStepType
)

logger = logging.getLogger(__name__)


class MockMarketDataCollector(IMarketDataCollector):
    """Mock collecteur de données de marché pour tests"""
    
    def __init__(self):
        self.collection_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
    
    async def collect_orderbook(self, symbol: str, limit: int = 5) -> Optional[OrderbookData]:
        """Mock collecte orderbook"""
        await asyncio.sleep(0.01)  # Simule latence réseau
        self.collection_count += 1
        
        # Générer données mock réalistes
        mid_price = 100 + random.uniform(-10, 10)
        spread_pct = random.uniform(0.01, 0.1)
        spread = mid_price * spread_pct / 100
        
        bids = [(mid_price - spread/2 - i*0.01, random.uniform(100, 1000)) for i in range(limit)]
        asks = [(mid_price + spread/2 + i*0.01, random.uniform(100, 1000)) for i in range(limit)]
        
        return OrderbookData(
            symbol=symbol,
            timestamp=datetime.utcnow(),
            bids=bids,
            asks=asks
        )
    
    async def collect_ticker(self, symbol: str) -> Optional[TickerData]:
        """Mock collecte ticker"""
        await asyncio.sleep(0.01)
        self.collection_count += 1
        
        price = 100 + random.uniform(-20, 20)
        volume_24h = random.uniform(500000, 5000000)
        
        return TickerData(
            symbol=symbol,
            timestamp=datetime.utcnow(),
            price=price,
            volume_24h=volume_24h,
            price_change_24h_pct=random.uniform(-5, 5),
            funding_rate=random.uniform(-0.05, 0.05)
        )
    
    async def collect_ohlcv(self, symbol: str, timeframe: str, limit: int = 30) -> Optional[OHLCVData]:
        """Mock collecte OHLCV"""
        await asyncio.sleep(0.01)
        self.collection_count += 1
        
        # Générer klines mock
        base_price = 100 + random.uniform(-10, 10)
        klines = []
        
        for i in range(limit):
            timestamp = datetime.utcnow().timestamp() - (limit - i) * 60
            open_price = base_price + random.uniform(-2, 2)
            high_price = open_price + random.uniform(0, 1)
            low_price = open_price - random.uniform(0, 1)
            close_price = open_price + random.uniform(-0.5, 0.5)
            volume = random.uniform(1000, 10000)
            
            klines.append([timestamp, open_price, high_price, low_price, close_price, volume])
            base_price = close_price
        
        return OHLCVData(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=datetime.utcnow(),
            klines=klines
        )
    
    async def collect_funding_rate(self, symbol: str) -> Optional[float]:
        """Mock collecte funding rate"""
        await asyncio.sleep(0.01)
        self.collection_count += 1
        return random.uniform(-0.05, 0.05)
    
    async def collect_complete_market_data(self, symbol: str, timeframes: List[str]) -> MarketData:
        """Mock collecte complète"""
        orderbook = await self.collect_orderbook(symbol)
        ticker = await self.collect_ticker(symbol)
        
        ohlcv_data = {}
        for tf in timeframes:
            ohlcv_data[tf] = await self.collect_ohlcv(symbol, tf)
        
        market_data = MarketData(
            symbol=symbol,
            timestamp=datetime.utcnow(),
            orderbook=orderbook,
            ticker=ticker,
            source=DataSource.MOCK,
            data_quality=random.uniform(0.8, 1.0)
        )
        
        # Ajouter OHLCV par timeframe
        if '1m' in ohlcv_data:
            market_data.ohlcv_1m = ohlcv_data['1m']
        if '5m' in ohlcv_data:
            market_data.ohlcv_5m = ohlcv_data['5m']
        if '15m' in ohlcv_data:
            market_data.ohlcv_15m = ohlcv_data['15m']
        
        return market_data
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Mock stats cache"""
        return {
            'cache_stats': {
                'hits': self.cache_hits,
                'misses': self.cache_misses,
                'hit_rate': 0.8,
                'total_requests': self.collection_count
            },
            'cache_sizes': {
                'orderbook': 10,
                'ticker': 10,
                'ohlcv': 20,
                'funding': 5,
                'total': 45
            },
            'performance': {
                'total_collections': self.collection_count,
                'total_errors': 0,
                'error_rate': 0.0,
                'average_collection_time_ms': 15.0
            },
            'configuration': {
                'cache_ttl_seconds': 30,
                'max_cache_size': 1000,
                'max_retries': 2
            }
        }
    
    def clear_cache(self, symbol: Optional[str] = None) -> None:
        """Mock clear cache"""
        logger.debug(f"Mock cache cleared{'for ' + symbol if symbol else ''}")


class MockScalabilityScorer(IScalabilityScorer):
    """Mock scorer de scalabilité pour tests"""
    
    def __init__(self):
        self.scoring_count = 0
        self.successful_scores = 0
        self.rejected_scores = 0
    
    def calculate_score(self, market_data: MarketData, config: Optional[Dict[str, Any]] = None) -> ScoringResult:
        """Mock calcul score"""
        self.scoring_count += 1
        
        # Simuler rejet aléatoire
        if random.random() < 0.2:  # 20% chance de rejet
            self.rejected_scores += 1
            return ScoringResult(
                symbol=market_data.symbol,
                score=0.0,
                metrics=ScoringMetrics(),
                rejection_reason="Mock rejection for testing",
                calculation_time_ms=random.uniform(5, 15)
            )
        
        # Score valide
        self.successful_scores += 1
        score = random.uniform(0.5, 5.0)
        
        metrics = ScoringMetrics(
            volatility_5=random.uniform(0.5, 3.0),
            volatility_15=random.uniform(0.3, 2.5),
            volume_recent=random.uniform(50000, 500000),
            volume_24h=market_data.ticker.volume_24h if market_data.ticker else random.uniform(1000000, 10000000),
            atr=random.uniform(0.5, 2.0),
            atr_pct=random.uniform(0.3, 1.5),
            adx=random.uniform(15, 45),
            delta_volume=random.uniform(-1000, 1000),
            imbalance_normalized=random.uniform(-0.3, 0.3),
            spread_volatility_5=random.uniform(0.0001, 0.01),
            book_depth_ratio=random.uniform(0.8, 1.2),
            volume_acceleration=random.uniform(-0.2, 0.5),
            price_momentum_5=random.uniform(-1.0, 1.0)
        )
        
        return ScoringResult(
            symbol=market_data.symbol,
            score=score,
            metrics=metrics,
            scoring_details={
                'spread_pct': market_data.orderbook.spread_pct if market_data.orderbook else 0.02,
                'vol_spread_ratio': score * 10,
                'volume_factor': 1.2,
                'balance_factor': 0.9
            },
            calculation_time_ms=random.uniform(8, 25)
        )
    
    def calculate_metrics(self, market_data: MarketData) -> ScoringMetrics:
        """Mock calcul métriques"""
        return ScoringMetrics(
            volatility_5=random.uniform(0.5, 3.0),
            volatility_15=random.uniform(0.3, 2.5),
            volume_recent=random.uniform(50000, 500000),
            volume_24h=random.uniform(1000000, 10000000),
            atr=random.uniform(0.5, 2.0),
            atr_pct=random.uniform(0.3, 1.5),
            adx=random.uniform(15, 45)
        )
    
    def batch_score(self, market_data_batch: Dict[str, MarketData]) -> Dict[str, ScoringResult]:
        """Mock batch scoring"""
        results = {}
        for symbol, market_data in market_data_batch.items():
            results[symbol] = self.calculate_score(market_data)
        return results
    
    def get_scoring_stats(self) -> Dict[str, Any]:
        """Mock stats scoring"""
        success_rate = self.successful_scores / self.scoring_count if self.scoring_count > 0 else 0.0
        
        return {
            'performance': {
                'total_scorings': self.scoring_count,
                'successful_scorings': self.successful_scores,
                'rejected_scorings': self.rejected_scores,
                'success_rate': success_rate,
                'average_scoring_time_ms': 12.5
            },
            'rejection_analytics': {
                'rejection_reasons': {'Mock rejection for testing': self.rejected_scores},
                'last_rejection': 'Mock rejection for testing' if self.rejected_scores > 0 else None,
                'total_rejections': self.rejected_scores
            },
            'cache_stats': {
                'cache_size': 0,
                'cache_ttl_seconds': 60
            }
        }
    
    def update_scoring_config(self, config: Dict[str, Any]) -> None:
        """Mock update config"""
        logger.debug("Mock scoring config updated")


class MockPairFilter(IPairFilter):
    """Mock filtreur de paires pour tests"""
    
    def __init__(self):
        self.filter_count = 0
        self.passed_count = 0
        self.failed_count = 0
    
    def filter_pair(self, symbol: str, market_data: MarketData, scoring_result: ScoringResult) -> PairFilterResult:
        """Mock filtrage paire"""
        self.filter_count += 1
        
        # Simuler filtrage aléatoire
        accepted = random.random() > 0.3  # 70% passent
        
        if accepted:
            self.passed_count += 1
        else:
            self.failed_count += 1
        
        rejection_reasons = [] if accepted else ["Mock filter rejection"]
        
        return PairFilterResult(
            symbol=symbol,
            accepted=accepted,
            filter_results={
                'spread': True,
                'volume': accepted,
                'funding': True,
                'balance': accepted,
                'fees': True
            },
            rejection_reasons=rejection_reasons,
            filter_details={
                'spread_value': random.uniform(0.01, 0.05),
                'volume_value': random.uniform(100000, 1000000),
                'balance_score': random.uniform(0.5, 1.0)
            },
            processing_time_ms=random.uniform(2, 8)
        )
    
    def batch_filter(self, data_batch: Dict[str, Tuple[MarketData, ScoringResult]]) -> Dict[str, PairFilterResult]:
        """Mock batch filtering"""
        results = {}
        for symbol, (market_data, scoring_result) in data_batch.items():
            results[symbol] = self.filter_pair(symbol, market_data, scoring_result)
        return results
    
    def update_filter_config(self, config: FilterConfig) -> None:
        """Mock update filter config"""
        logger.debug("Mock filter config updated")
    
    def add_custom_filter(self, name: str, filter_func) -> None:
        """Mock add custom filter"""
        logger.debug(f"Mock custom filter '{name}' added")
    
    def get_filter_stats(self) -> Dict[str, Any]:
        """Mock filter stats"""
        success_rate = self.passed_count / self.filter_count if self.filter_count > 0 else 0.0
        
        return {
            'overall': {
                'total_filters': self.filter_count,
                'passed_filters': self.passed_count,
                'failed_filters': self.failed_count,
                'success_rate': success_rate,
                'average_filter_time_ms': 4.5
            },
            'by_filter_type': {
                'spread': {'total': self.filter_count, 'passed': self.filter_count, 'failed': 0, 'pass_rate': 1.0},
                'volume': {'total': self.filter_count, 'passed': self.passed_count, 'failed': self.failed_count, 'pass_rate': success_rate}
            },
            'custom_filters': [],
            'cache_stats': {
                'cache_size': 0,
                'cache_ttl_seconds': 60
            },
            'current_config': {
                'min_spread': 0.001,
                'max_spread': 0.05,
                'min_volume': 100000,
                'max_funding_rate': 0.05,
                'require_zero_fees': True
            }
        }


class MockScanPipeline(IScanPipeline):
    """Mock pipeline de scan pour tests"""
    
    def __init__(self):
        self.execution_count = 0
        self.successful_executions = 0
        self.failed_executions = 0
    
    async def execute_pipeline(self, symbol: str, config: Optional[Dict[str, Any]] = None) -> ScanPipelineResult:
        """Mock exécution pipeline"""
        await asyncio.sleep(0.05)  # Simule traitement
        self.execution_count += 1
        
        # Simuler succès/échec
        success = random.random() > 0.1  # 90% succès
        
        if success:
            self.successful_executions += 1
            steps_executed = ['data_collection', 'scoring', 'filtering']
            step_results = {
                'data_collection': {'market_data': None, 'data_quality': 0.9},
                'scoring': {'score': random.uniform(1.0, 4.0), 'is_valid': True},
                'filtering': {'accepted': True, 'rejection_reasons': []}
            }
            step_timings = {
                'data_collection': random.uniform(10, 30),
                'scoring': random.uniform(5, 15),
                'filtering': random.uniform(2, 8)
            }
            errors = {}
        else:
            self.failed_executions += 1
            steps_executed = ['data_collection']
            step_results = {'data_collection': {'error': 'Mock pipeline failure'}}
            step_timings = {'data_collection': random.uniform(10, 30)}
            errors = {'data_collection': 'Mock pipeline failure for testing'}
        
        # Créer résultat final
        final_result = ScanResult(
            symbol=symbol,
            status=ScanStatus.SUCCESS if success else ScanStatus.FAILED,
            errors=list(errors.values()),
            scan_duration_ms=sum(step_timings.values()),
            timestamp=datetime.utcnow()
        )
        
        return ScanPipelineResult(
            symbol=symbol,
            steps_executed=steps_executed,
            step_results=step_results,
            step_timings=step_timings,
            final_result=final_result,
            pipeline_duration_ms=sum(step_timings.values()),
            errors_by_step=errors,
            timestamp=datetime.utcnow()
        )
    
    def add_step(self, step) -> None:
        """Mock add step"""
        logger.debug("Mock step added to pipeline")
    
    def remove_step(self, step_name: str) -> None:
        """Mock remove step"""
        logger.debug(f"Mock step '{step_name}' removed from pipeline")
    
    def configure_step(self, step_name: str, config: Dict[str, Any]) -> None:
        """Mock configure step"""
        logger.debug(f"Mock step '{step_name}' configured")
    
    def get_pipeline_config(self) -> List:
        """Mock get pipeline config"""
        return [
            {'name': 'data_collection', 'type': ScanPipelineStepType.DATA_COLLECTION, 'enabled': True},
            {'name': 'scoring', 'type': ScanPipelineStepType.SCORING, 'enabled': True},
            {'name': 'filtering', 'type': ScanPipelineStepType.FILTERING, 'enabled': True}
        ]
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Mock pipeline stats"""
        success_rate = self.successful_executions / self.execution_count if self.execution_count > 0 else 0.0
        
        return {
            'overall': {
                'total_executions': self.execution_count,
                'successful_executions': self.successful_executions,
                'failed_executions': self.failed_executions,
                'success_rate': success_rate,
                'average_execution_time_ms': 45.0
            },
            'circuit_breaker': {
                'enabled': True,
                'is_open': False,
                'consecutive_failures': 0,
                'threshold': 5,
                'recovery_time_seconds': 60
            },
            'steps': {
                'total_steps': 3,
                'enabled_steps': 3,
                'step_stats': {
                    'data_collection': {'total_executions': self.execution_count, 'successful_executions': self.execution_count, 'failed_executions': 0, 'average_time_ms': 20.0},
                    'scoring': {'total_executions': self.successful_executions, 'successful_executions': self.successful_executions, 'failed_executions': 0, 'average_time_ms': 10.0},
                    'filtering': {'total_executions': self.successful_executions, 'successful_executions': self.successful_executions, 'failed_executions': 0, 'average_time_ms': 5.0}
                }
            }
        }


class MockScannerOrchestrator(IScannerOrchestrator):
    """Mock orchestrateur scanner pour tests"""
    
    def __init__(self):
        self.total_scans = 0
        self.successful_scans = 0
        self.failed_scans = 0
    
    async def scan_single_pair(self, symbol: str, config: Optional[ScannerConfig] = None) -> ScanResult:
        """Mock scan single"""
        await asyncio.sleep(0.1)  # Simule scan
        self.total_scans += 1
        
        # Simuler succès/échec
        success = random.random() > 0.15  # 85% succès
        
        if success:
            self.successful_scans += 1
            status = ScanStatus.SUCCESS
            errors = []
        else:
            self.failed_scans += 1
            status = ScanStatus.FAILED
            errors = ["Mock scan failure for testing"]
        
        return ScanResult(
            symbol=symbol,
            status=status,
            errors=errors,
            scan_duration_ms=random.uniform(80, 150),
            timestamp=datetime.utcnow()
        )
    
    async def scan_batch_pairs(self, symbols: List[str], config: Optional[ScannerConfig] = None) -> ScanBatchResult:
        """Mock scan batch"""
        results = {}
        
        # Scanner chaque symbole
        for symbol in symbols:
            results[symbol] = await self.scan_single_pair(symbol, config)
        
        # Calculer stats
        successful_count = sum(1 for r in results.values() if r.status == ScanStatus.SUCCESS)
        failed_count = len(results) - successful_count
        
        return ScanBatchResult(
            symbols=symbols,
            results=results,
            batch_id=f"mock_batch_{int(datetime.utcnow().timestamp())}",
            total_duration_ms=random.uniform(200, 500),
            parallel_workers=min(len(symbols), 4)
        )
    
    async def scan_top_pairs(self, limit: int = 20, config: Optional[ScannerConfig] = None) -> ScanBatchResult:
        """Mock scan top pairs"""
        # Mock top pairs
        top_symbols = [f"MOCK{i}USDT" for i in range(1, limit + 1)]
        return await self.scan_batch_pairs(top_symbols, config)
    
    def get_scan_statistics(self) -> Dict[str, Any]:
        """Mock scan statistics"""
        success_rate = self.successful_scans / self.total_scans if self.total_scans > 0 else 0.0
        
        return {
            'orchestrator': {
                'total_scans': self.total_scans,
                'successful_scans': self.successful_scans,
                'failed_scans': self.failed_scans,
                'success_rate': success_rate,
                'average_scan_time_ms': 100.0
            },
            'pipeline': {
                'overall': {
                    'success_rate': 0.9,
                    'average_execution_time_ms': 45.0
                }
            },
            'cache': {
                'cache_size': 50,
                'cache_enabled': True
            },
            'configuration': {
                'max_concurrent_scans': 10,
                'max_parallel_workers': 4,
                'single_scan_timeout_ms': 5000,
                'batch_scan_timeout_ms': 30000,
                'default_timeframes': ['1m', '5m']
            }
        }
    
    def configure_scanner(self, config: ScannerConfig) -> None:
        """Mock configure scanner"""
        logger.debug("Mock scanner configuration updated")
    
    async def health_check(self) -> Dict[str, Any]:
        """Mock health check"""
        await asyncio.sleep(0.01)
        
        success_rate = self.successful_scans / self.total_scans if self.total_scans > 0 else 1.0
        
        if success_rate > 0.8:
            status = 'healthy'
        elif success_rate > 0.5:
            status = 'degraded'
        else:
            status = 'unhealthy'
        
        return {
            'status': status,
            'timestamp': datetime.utcnow().isoformat(),
            'components': {
                'pipeline': {'status': 'healthy', 'success_rate': 0.9},
                'circuit_breaker': {'status': 'closed'}
            }
        }


class MockScanLogger(IScanLogger):
    """Mock logger de scans pour tests"""
    
    def __init__(self):
        self.logged_scans = 0
        self.logged_opportunities = 0
    
    async def log_scan(self, scan_result: ScanResult) -> Optional[str]:
        """Mock log scan"""
        await asyncio.sleep(0.01)
        self.logged_scans += 1
        return f"mock_scan_id_{self.logged_scans}"
    
    async def log_opportunity(self, scan_result: ScanResult) -> Optional[str]:
        """Mock log opportunity"""
        await asyncio.sleep(0.01)
        self.logged_opportunities += 1
        return f"mock_opp_id_{self.logged_opportunities}"
    
    async def log_batch_scan(self, batch_result: ScanBatchResult) -> None:
        """Mock log batch"""
        await asyncio.sleep(0.01)
        logger.debug(f"Mock logged batch scan: {len(batch_result.symbols)} symbols")
    
    def get_logging_stats(self) -> Dict[str, Any]:
        """Mock logging stats"""
        return {
            'total_scans_logged': self.logged_scans,
            'total_opportunities_logged': self.logged_opportunities,
            'logging_success_rate': 1.0,
            'average_log_time_ms': 5.0
        }
