import os
import sys
from datetime import datetime, timedelta
import math
from unittest.mock import AsyncMock, Mock

import pytest

import core.implementations.testable_pair_filter as pair_filter_module

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from core.interfaces.scanner_interfaces import (
    MarketData,
    OrderbookData,
    OHLCVData,
    TickerData,
    ScoringMetrics,
    ScoringResult,
    FilterConfig,
    ScanPipelineStep,
    ScanPipelineStepType,
    ScanPipelineResult,
    ScanResult,
    ScanStatus,
)
from core.implementations.testable_market_data_collector import TestableMarketDataCollector
from core.implementations.testable_pair_filter import TestablePairFilter
from core.implementations.testable_scalability_scorer import TestableScalabilityScorer
from core.implementations.testable_scan_pipeline import TestableScanPipeline
from core.implementations.testable_scanner_orchestrator import TestableScannerOrchestrator


def _make_orderbook(symbol: str, spread_pct: float = 0.01, bid_vol: float = 10.0, ask_vol: float = 10.0) -> OrderbookData:
    bids = [(100.0, bid_vol)]
    asks = [(100.0 * (1 + spread_pct / 100.0), ask_vol)]
    return OrderbookData(symbol=symbol, timestamp=datetime.utcnow(), bids=bids, asks=asks)


def _make_ohlcv(symbol: str, timeframe: str, candles: int, volume: float = 10.0) -> OHLCVData:
    ts = 1000.0
    klines = []
    for i in range(candles):
        klines.append([ts + i * 60_000, 100.0, 101.0, 99.0, 100.0, volume])
    return OHLCVData(symbol=symbol, timeframe=timeframe, timestamp=datetime.utcnow(), klines=klines)


def _make_market_data(symbol: str) -> MarketData:
    return MarketData(
        symbol=symbol,
        timestamp=datetime.utcnow(),
        orderbook=_make_orderbook(symbol),
        ticker=TickerData(symbol=symbol, timestamp=datetime.utcnow(), price=100.0, volume_24h=5_000_000.0),
        ohlcv_1m=_make_ohlcv(symbol, '1m', 20, volume=50_000.0),
        ohlcv_5m=_make_ohlcv(symbol, '5m', 10),
    )


class _Step:
    def __init__(
        self,
        name: str,
        step_type: ScanPipelineStepType,
        execute_fn,
        enabled: bool = True,
        timeout_ms: int = 50,
        retry_attempts: int = 1,
    ):
        self._execute_fn = execute_fn
        self.config = ScanPipelineStep(
            name=name,
            step_type=step_type,
            enabled=enabled,
            timeout_ms=timeout_ms,
            retry_attempts=retry_attempts,
        )

    async def execute(self, symbol: str, context):
        return await self._execute_fn(symbol, context)

    def get_step_config(self):
        return self.config

    def is_enabled(self):
        return self.config.enabled


class TestTestableMarketDataCollector:
    @pytest.mark.asyncio
    async def test_collect_orderbook_cache_hit(self):
        collector = TestableMarketDataCollector(client=None, cache_ttl_seconds=30)
        symbol = 'BTC/USDT:USDT'
        ob = _make_orderbook(symbol)
        collector._orderbook_cache[symbol] = {'data': ob, 'timestamp': datetime.utcnow()}

        result = await collector.collect_orderbook(symbol)
        assert result is ob
        assert collector.cache_hits == 1
        assert collector.cache_misses == 0

    @pytest.mark.asyncio
    async def test_collect_orderbook_invalid_symbol_returns_none(self):
        collector = TestableMarketDataCollector(client=None)
        result = await collector.collect_orderbook('INVALID')
        assert result is None

    @pytest.mark.asyncio
    async def test_collect_with_retry_eventually_succeeds(self, monkeypatch):
        collector = TestableMarketDataCollector(client=None)
        monkeypatch.setattr('asyncio.sleep', AsyncMock())

        calls = {'n': 0}

        async def fn():
            calls['n'] += 1
            if calls['n'] == 1:
                raise RuntimeError('boom')
            return 123

        result = await collector._collect_with_retry(fn)
        assert result == 123
        assert calls['n'] == 2

    @pytest.mark.asyncio
    async def test_collect_with_retry_raises_after_exhaustion(self, monkeypatch):
        collector = TestableMarketDataCollector(client=None)
        collector.max_retries = 1
        monkeypatch.setattr('asyncio.sleep', AsyncMock())

        async def fn():
            raise RuntimeError('boom')

        with pytest.raises(RuntimeError):
            await collector._collect_with_retry(fn)

    def test_get_from_cache_expired_entry_is_removed(self):
        collector = TestableMarketDataCollector(client=None, cache_ttl_seconds=1)
        cache = {'k': {'data': 123, 'timestamp': datetime.utcnow() - timedelta(seconds=5)}}
        assert collector._get_from_cache(cache, 'k') is None
        assert 'k' not in cache

    def test_put_in_cache_triggers_cleanup_when_full(self):
        collector = TestableMarketDataCollector(client=None, max_cache_size=1)
        cache = {'old': {'data': 1, 'timestamp': datetime.utcnow() - timedelta(seconds=10)}}
        collector._put_in_cache(cache, 'new', 2)
        assert 'new' in cache
        assert 'old' not in cache

    def test_calculate_data_quality_bounds_and_freshness(self):
        collector = TestableMarketDataCollector(client=None)
        md = _make_market_data('BTC/USDT:USDT')
        md.timestamp = datetime.utcnow() - timedelta(seconds=10)
        quality = collector._calculate_data_quality(md)
        assert 0.0 <= quality <= 1.0
        assert quality >= 0.8

        md_old = _make_market_data('BTC/USDT:USDT')
        md_old.timestamp = datetime.utcnow() - timedelta(seconds=400)
        quality_old = collector._calculate_data_quality(md_old)
        assert 0.0 <= quality_old <= 1.0
        assert quality_old < quality

    def test_clear_cache_symbol_only(self):
        collector = TestableMarketDataCollector(client=None)
        collector._orderbook_cache['BTC/USDT:USDT'] = {'data': 1, 'timestamp': datetime.utcnow()}
        collector._ticker_cache['BTC/USDT:USDT'] = {'data': 2, 'timestamp': datetime.utcnow()}
        collector._funding_cache['BTC/USDT:USDT'] = {'data': 3, 'timestamp': datetime.utcnow()}
        collector._ohlcv_cache['BTC/USDT:USDT_1m'] = {'data': 4, 'timestamp': datetime.utcnow()}
        collector._ohlcv_cache['ETH/USDT:USDT_1m'] = {'data': 5, 'timestamp': datetime.utcnow()}

        collector.clear_cache('BTC/USDT:USDT')

        assert 'BTC/USDT:USDT' not in collector._orderbook_cache
        assert 'BTC/USDT:USDT' not in collector._ticker_cache
        assert 'BTC/USDT:USDT' not in collector._funding_cache
        assert 'BTC/USDT:USDT_1m' not in collector._ohlcv_cache
        assert 'ETH/USDT:USDT_1m' in collector._ohlcv_cache


class TestTestablePairFilter:
    def test_filter_pair_cache_returns_cached_result(self):
        pf = TestablePairFilter(FilterConfig())
        md = _make_market_data('BTC/USDT:USDT')
        metrics = ScoringMetrics(volume_recent=200000)
        scoring = ScoringResult(symbol=md.symbol, score=1.0, metrics=metrics)

        first = pf.filter_pair(md.symbol, md, scoring)
        second = pf.filter_pair(md.symbol, md, scoring)

        assert second is first
        assert pf.filter_count == 2
        assert pf.passed_count + pf.failed_count == 1

    def test_spread_filter_missing_orderbook_rejects(self):
        pf = TestablePairFilter(FilterConfig())
        md = MarketData(symbol='BTC/USDT:USDT', timestamp=datetime.utcnow())
        metrics = ScoringMetrics(volume_recent=200000)
        scoring = ScoringResult(symbol=md.symbol, score=1.0, metrics=metrics)

        res = pf.filter_pair(md.symbol, md, scoring)
        assert res.accepted is False
        assert any('spread' in r.lower() for r in res.rejection_reasons)

    def test_spread_filter_nan_rejects(self):
        pf = TestablePairFilter(FilterConfig())
        md = _make_market_data('BTC/USDT:USDT')
        md.orderbook.spread_pct = float('nan')
        metrics = ScoringMetrics(volume_recent=200000)
        scoring = ScoringResult(symbol=md.symbol, score=1.0, metrics=metrics)

        res = pf.filter_pair(md.symbol, md, scoring)
        assert res.accepted is False
        assert any('nan' in r.lower() for r in res.rejection_reasons)

    def test_whitelist_blocks_non_whitelisted(self):
        cfg = FilterConfig(symbol_whitelist=['BTC/USDT:USDT'])
        pf = TestablePairFilter(cfg)
        md = _make_market_data('ETH/USDT:USDT')
        metrics = ScoringMetrics(volume_recent=200000)
        scoring = ScoringResult(symbol=md.symbol, score=1.0, metrics=metrics)

        res = pf.filter_pair(md.symbol, md, scoring)
        assert res.accepted is False
        assert any('whitelist' in r.lower() for r in res.rejection_reasons)

    def test_custom_filter_exception_rejects(self):
        pf = TestablePairFilter(FilterConfig())

        def bad_filter(symbol, market_data, scoring_result):
            raise RuntimeError('bad')

        pf.add_custom_filter('bad', bad_filter)

        md = _make_market_data('BTC/USDT:USDT')
        metrics = ScoringMetrics(volume_recent=200000)
        scoring = ScoringResult(symbol=md.symbol, score=1.0, metrics=metrics)

        res = pf.filter_pair(md.symbol, md, scoring)
        assert res.accepted is False
        assert any('custom filter' in r.lower() for r in res.rejection_reasons)

    def test_add_custom_filter_non_callable_raises(self):
        pf = TestablePairFilter(FilterConfig())
        with pytest.raises(ValueError):
            pf.add_custom_filter('x', filter_func=123)

    def test_book_depth_filter_low_rejects(self):
        cfg = FilterConfig(min_book_depth=10_000_000)
        pf = TestablePairFilter(cfg)
        md = _make_market_data('BTC/USDT:USDT')
        metrics = ScoringMetrics(volume_recent=200000)
        scoring = ScoringResult(symbol=md.symbol, score=1.0, metrics=metrics)

        res = pf.filter_pair(md.symbol, md, scoring)
        assert res.accepted is False
        assert any('depth' in r.lower() for r in res.rejection_reasons)

    def test_atr_filter_rejects(self):
        cfg = FilterConfig(max_atr_pct=0.1)
        pf = TestablePairFilter(cfg)
        md = _make_market_data('BTC/USDT:USDT')
        metrics = ScoringMetrics(volume_recent=200000, atr_pct=1.0)
        scoring = ScoringResult(symbol=md.symbol, score=1.0, metrics=metrics)

        res = pf.filter_pair(md.symbol, md, scoring)
        assert res.accepted is False
        assert any('atr' in r.lower() for r in res.rejection_reasons)

    def test_volume_24h_filter_rejects_when_ticker_present(self):
        cfg = FilterConfig(min_volume_24h=10_000_000)
        pf = TestablePairFilter(cfg)
        md = _make_market_data('BTC/USDT:USDT')
        md.ticker.volume_24h = 100.0
        metrics = ScoringMetrics(volume_recent=200000)
        scoring = ScoringResult(symbol=md.symbol, score=1.0, metrics=metrics)

        res = pf.filter_pair(md.symbol, md, scoring)
        assert res.accepted is False
        assert any('24h' in r.lower() for r in res.rejection_reasons)

    def test_market_hours_filter_weekend_rejects_when_avoid_weekends(self, monkeypatch):
        class FakeDatetime:
            @classmethod
            def utcnow(cls):
                return datetime(2025, 1, 4, 12, 0, 0)  # Saturday

        monkeypatch.setattr(pair_filter_module, 'datetime', FakeDatetime)

        cfg = FilterConfig(avoid_weekends=True)
        pf = TestablePairFilter(cfg)
        md = _make_market_data('BTC/USDT:USDT')
        metrics = ScoringMetrics(volume_recent=200000)
        scoring = ScoringResult(symbol=md.symbol, score=1.0, metrics=metrics)

        res = pf.filter_pair(md.symbol, md, scoring)
        assert res.accepted is False
        assert any('weekend' in r.lower() for r in res.rejection_reasons)


class TestTestableScalabilityScorer:
    def test_calculate_score_rejects_on_validation_errors(self):
        scorer = TestableScalabilityScorer()
        md = MarketData(symbol='INVALID', timestamp=datetime.utcnow())

        res = scorer.calculate_score(md)
        assert res.is_valid is False
        assert res.score == 0.0
        assert res.rejection_reason is not None

    def test_calculate_metrics_uses_cache(self):
        scorer = TestableScalabilityScorer()
        md = _make_market_data('BTC/USDT:USDT')

        m1 = scorer.calculate_metrics(md)
        m2 = scorer.calculate_metrics(md)

        assert isinstance(m1, ScoringMetrics)
        assert m2 is m1

    def test_check_basic_filters_book_depth_invalid(self):
        scorer = TestableScalabilityScorer()
        md = _make_market_data('BTC/USDT:USDT')
        md.orderbook.book_depth = 0
        metrics = ScoringMetrics(volume_recent=200000)
        params = scorer._get_effective_scoring_params(md.symbol)

        reason = scorer._check_basic_filters(md, metrics, params)
        assert isinstance(reason, str)
        assert 'depth' in reason.lower()

    def test_check_basic_filters_spread_nan(self):
        scorer = TestableScalabilityScorer()
        md = _make_market_data('BTC/USDT:USDT')
        md.orderbook.spread_pct = float('nan')
        metrics = ScoringMetrics(volume_recent=200000)
        params = scorer._get_effective_scoring_params(md.symbol)

        reason = scorer._check_basic_filters(md, metrics, params)
        assert 'nan' in reason.lower()

    def test_calculate_score_success_path(self, monkeypatch):
        scorer = TestableScalabilityScorer()
        md = _make_market_data('BTC/USDT:USDT')

        monkeypatch.setattr('utils.effective_config.get_effective_value', lambda *args, **kwargs: None)

        res = scorer.calculate_score(md)
        assert res.rejection_reason is None
        assert res.score > 0
        assert res.is_valid

    def test_apply_score_adjustments_handles_error_and_returns_base(self, monkeypatch):
        scorer = TestableScalabilityScorer()
        metrics = ScoringMetrics()
        params = scorer._get_effective_scoring_params('BTC/USDT:USDT')

        def boom(*args, **kwargs):
            raise RuntimeError('boom')

        monkeypatch.setattr(metrics, 'volume_24h', property(lambda self: boom()))

        out = scorer._apply_score_adjustments(1.23, metrics, params)
        assert out == 1.23


class TestTestableScanPipeline:
    @pytest.mark.asyncio
    async def test_execute_pipeline_skips_disabled_step(self):
        pipeline = TestableScanPipeline(enable_circuit_breaker=False)

        async def ok(symbol, context):
            return {'ok': True}

        pipeline.add_step(_Step('s1', ScanPipelineStepType.CUSTOM, ok, enabled=False))
        pipeline.add_step(_Step('s2', ScanPipelineStepType.CUSTOM, ok, enabled=True))

        res = await pipeline.execute_pipeline('BTC/USDT:USDT')
        assert any('s1' in s for s in res.steps_executed)
        assert 's2' in res.step_results

    @pytest.mark.asyncio
    async def test_execute_pipeline_timeout_stops_on_critical_step(self):
        pipeline = TestableScanPipeline(enable_circuit_breaker=False)

        async def slow(symbol, context):
            import asyncio

            await asyncio.sleep(0.2)
            return {'x': 1}

        async def ok(symbol, context):
            return {'ok': True}

        pipeline.add_step(_Step('data_collection', ScanPipelineStepType.DATA_COLLECTION, slow, timeout_ms=10))
        pipeline.add_step(_Step('after', ScanPipelineStepType.CUSTOM, ok))

        res = await pipeline.execute_pipeline('BTC/USDT:USDT')
        assert 'data_collection' in res.errors_by_step
        assert 'after' not in res.step_results

    @pytest.mark.asyncio
    async def test_execute_pipeline_retries_step_success(self, monkeypatch):
        pipeline = TestableScanPipeline(enable_circuit_breaker=False)
        monkeypatch.setattr('asyncio.sleep', AsyncMock())

        calls = {'n': 0}

        async def flaky(symbol, context):
            calls['n'] += 1
            if calls['n'] == 1:
                raise RuntimeError('fail')
            return {'ok': True}

        pipeline.add_step(_Step('custom', ScanPipelineStepType.CUSTOM, flaky, retry_attempts=2, timeout_ms=100))

        res = await pipeline.execute_pipeline('BTC/USDT:USDT')
        assert 'custom' in res.step_results
        assert res.errors_by_step == {}
        assert calls['n'] == 2

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_returns_immediately(self):
        pipeline = TestableScanPipeline(enable_circuit_breaker=True)
        pipeline.circuit_open = True
        pipeline.circuit_open_time = datetime.utcnow()

        res = await pipeline.execute_pipeline('BTC/USDT:USDT')
        assert res.errors_by_step.get('pipeline') == 'Circuit breaker is OPEN'

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovers_after_recovery_time(self):
        pipeline = TestableScanPipeline(enable_circuit_breaker=True)
        pipeline.circuit_open = True
        pipeline.circuit_open_time = datetime.utcnow() - timedelta(seconds=pipeline.circuit_recovery_time_seconds + 1)

        async def ok(symbol, context):
            return {'ok': True}

        pipeline.add_step(_Step('custom', ScanPipelineStepType.CUSTOM, ok))

        res = await pipeline.execute_pipeline('BTC/USDT:USDT')
        assert pipeline.circuit_open is False
        assert 'custom' in res.step_results

    @pytest.mark.asyncio
    async def test_build_final_scan_result_includes_step_errors(self):
        pipeline = TestableScanPipeline(enable_circuit_breaker=False)
        result = ScanPipelineResult(symbol='BTC/USDT:USDT', timestamp=datetime.utcnow())
        result.errors_by_step['x'] = 'err'

        final = pipeline._build_final_scan_result('BTC/USDT:USDT', context={}, pipeline_result=result)
        assert final.status == ScanStatus.FAILED
        assert any('Step x' in e for e in final.errors)

    def test_handle_pipeline_failure_opens_circuit(self):
        pipeline = TestableScanPipeline(enable_circuit_breaker=True)
        pipeline.circuit_breaker_threshold = 1
        pipeline._handle_pipeline_failure()
        assert pipeline.circuit_open is True

    @pytest.mark.asyncio
    async def test_build_final_scan_result_extracts_fields(self):
        pipeline = TestableScanPipeline(enable_circuit_breaker=False)
        md = _make_market_data('BTC/USDT:USDT')
        metrics = ScoringMetrics(volume_recent=250000)
        scoring_obj = ScoringResult(symbol=md.symbol, score=1.0, metrics=metrics)
        filter_obj = TestablePairFilter(FilterConfig()).filter_pair(md.symbol, md, scoring_obj)

        result = ScanPipelineResult(symbol=md.symbol, timestamp=datetime.utcnow())
        result.step_results['data_collection'] = {'market_data': md}
        result.step_timings['data_collection'] = 12.0
        result.step_results['scoring'] = scoring_obj
        result.step_timings['scoring'] = 34.0
        result.step_results['filtering'] = filter_obj
        result.step_results['analysis'] = {'is_valid': True}
        result.step_timings['analysis'] = 56.0
        result.step_results['ml_prediction'] = {'pnl': 1.0}
        result.step_results['logging'] = {'scan_id': 's1', 'opportunity_id': 'o1'}

        final = pipeline._build_final_scan_result(md.symbol, context={'results': {}}, pipeline_result=result)
        assert final.market_data is md
        assert final.scoring_result is scoring_obj
        assert final.filter_result is filter_obj
        assert final.ml_prediction == {'pnl': 1.0}
        assert final.scan_id == 's1'
        assert final.opportunity_id == 'o1'


class TestTestableScannerOrchestrator:
    @pytest.mark.asyncio
    async def test_scan_single_pair_invalid_symbol(self):
        pipeline = AsyncMock()
        pipeline.get_pipeline_stats.return_value = {'overall': {'success_rate': 1.0}, 'circuit_breaker': {'is_open': False}}
        orch = TestableScannerOrchestrator(pipeline)

        res = await orch.scan_single_pair('INVALID')
        assert res.status == ScanStatus.FAILED
        assert any('Invalid symbol format' in e for e in res.errors)

    @pytest.mark.asyncio
    async def test_scan_single_pair_success_uses_pipeline_final_result(self):
        async def exec_pipeline(symbol, config=None):
            final = ScanResult(symbol=symbol, status=ScanStatus.SUCCESS)
            return ScanPipelineResult(symbol=symbol, timestamp=datetime.utcnow(), final_result=final)

        pipeline = AsyncMock()
        pipeline.execute_pipeline.side_effect = exec_pipeline
        pipeline.get_pipeline_stats.return_value = {'overall': {'success_rate': 1.0}, 'circuit_breaker': {'is_open': False}}

        orch = TestableScannerOrchestrator(pipeline)

        res = await orch.scan_single_pair('BTC/USDT:USDT')
        assert res.is_success
        assert orch.total_scans == 1
        assert orch.successful_scans == 1

    @pytest.mark.asyncio
    async def test_scan_batch_pairs_wraps_exceptions(self):
        async def scan_single_pair(symbol, config=None):
            if symbol == 'BAD/USDT:USDT':
                raise RuntimeError('boom')
            return ScanResult(symbol=symbol, status=ScanStatus.SUCCESS)

        pipeline = AsyncMock()
        pipeline.get_pipeline_stats.return_value = {'overall': {'success_rate': 1.0}, 'circuit_breaker': {'is_open': False}}
        orch = TestableScannerOrchestrator(pipeline)
        orch.scan_single_pair = AsyncMock(side_effect=scan_single_pair)

        batch = await orch.scan_batch_pairs(['BTC/USDT:USDT', 'BAD/USDT:USDT'])
        assert 'BTC/USDT:USDT' in batch.results
        assert 'BAD/USDT:USDT' in batch.results
        assert batch.results['BAD/USDT:USDT'].status == ScanStatus.FAILED

    @pytest.mark.asyncio
    async def test_scan_batch_pairs_timeout_marks_all_failed(self, monkeypatch):
        pipeline = AsyncMock()
        pipeline.get_pipeline_stats.return_value = {'overall': {'success_rate': 1.0}, 'circuit_breaker': {'is_open': False}}
        orch = TestableScannerOrchestrator(pipeline)
        orch.scan_single_pair = AsyncMock(return_value=ScanResult(symbol='BTC/USDT:USDT', status=ScanStatus.SUCCESS))

        async def timeout(*args, **kwargs):
            raise TimeoutError()

        monkeypatch.setattr('core.implementations.testable_scanner_orchestrator.asyncio.wait_for', timeout)

        batch = await orch.scan_batch_pairs(['BTC/USDT:USDT', 'ETH/USDT:USDT'])
        assert batch.results['BTC/USDT:USDT'].status == ScanStatus.FAILED
        assert any('timeout' in e.lower() for e in batch.results['BTC/USDT:USDT'].errors)

    @pytest.mark.asyncio
    async def test_health_check_degraded_when_pipeline_degraded(self):
        pipeline = Mock()
        pipeline.get_pipeline_stats.return_value = {'overall': {'success_rate': 0.5}, 'circuit_breaker': {'is_open': False}}
        orch = TestableScannerOrchestrator(pipeline)
        orch.total_scans = 0

        status = await orch.health_check()
        assert status['status'] in ('degraded', 'healthy')

    @pytest.mark.asyncio
    async def test_health_check_missing_pipeline_is_unhealthy(self):
        orch = TestableScannerOrchestrator(scan_pipeline=None)
        status = await orch.health_check()
        assert status['status'] == 'unhealthy'
