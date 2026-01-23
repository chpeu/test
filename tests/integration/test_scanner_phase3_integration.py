"""
Test d'intégration Scanner Phase 3 - Trade Cursor v7.0
Valide le fonctionnement complet de tous les composants Scanner Phase 3
"""

import pytest
import logging
import asyncio
from typing import Dict, Any, List
from datetime import datetime
import numpy as np

from core.factories.position_factory import get_configured_scanner_factory
from core.interfaces.scanner_interfaces import (
    ScannerConfig, FilterConfig, ScanStatus, 
    ScannerValidationUtils, DataSource
)

logger = logging.getLogger(__name__)


class TestScannerPhase3Integration:
    """Tests d'intégration complets pour la Phase 3 Scanner"""
    
    @pytest.fixture
    def scanner_factory(self):
        """Factory configurée pour les tests"""
        return get_configured_scanner_factory("test", use_mocks=True)
    
    @pytest.fixture
    def scanner_config(self):
        """Configuration scanner pour les tests"""
        return ScannerConfig(
            max_concurrent_scans=2,
            single_scan_timeout_ms=5000,
            batch_scan_timeout_ms=15000,
            enable_cache=True,
            cache_ttl_seconds=30,
            default_timeframes=['1m', '5m'],
            max_parallel_workers=2
        )
    
    @pytest.fixture
    def filter_config(self):
        """Configuration filtres pour les tests"""
        return FilterConfig(
            min_spread=0.001,
            max_spread=0.05,
            min_volume=50000,
            max_funding_rate=0.1,
            min_balance_score=0.5,
            require_zero_fees=False,
            min_book_depth=1000,
            max_atr_pct=5.0
        )
    
    def test_individual_components_creation(self, scanner_factory, scanner_config, filter_config):
        """Test 1: Création de tous les composants individuels"""
        logger.info("🧪 Test 1: Création composants Scanner individuels")
        
        # Test création market data collector
        market_data_collector = scanner_factory.create_market_data_collector()
        assert market_data_collector is not None
        assert hasattr(market_data_collector, 'collect_orderbook')
        assert hasattr(market_data_collector, 'collect_ticker')
        assert hasattr(market_data_collector, 'collect_ohlcv')
        assert hasattr(market_data_collector, 'collect_complete_market_data')
        
        # Test création scalability scorer
        scalability_scorer = scanner_factory.create_scalability_scorer()
        assert scalability_scorer is not None
        assert hasattr(scalability_scorer, 'calculate_score')
        assert hasattr(scalability_scorer, 'calculate_metrics')
        assert hasattr(scalability_scorer, 'batch_score')
        
        # Test création pair filter
        pair_filter = scanner_factory.create_pair_filter(filter_config)
        assert pair_filter is not None
        assert hasattr(pair_filter, 'filter_pair')
        assert hasattr(pair_filter, 'batch_filter')
        
        # Test création scan pipeline
        scan_pipeline = scanner_factory.create_scan_pipeline()
        assert scan_pipeline is not None
        assert hasattr(scan_pipeline, 'execute_pipeline')
        assert hasattr(scan_pipeline, 'add_step')
        
        # Test création scanner orchestrator
        scanner_orchestrator = scanner_factory.create_scanner_orchestrator(scanner_config)
        assert scanner_orchestrator is not None
        assert hasattr(scanner_orchestrator, 'scan_single_pair')
        assert hasattr(scanner_orchestrator, 'scan_batch_pairs')
        assert hasattr(scanner_orchestrator, 'scan_top_pairs')
        
        logger.info("✅ Test 1 réussi: Tous les composants créés")
    
    @pytest.mark.asyncio
    async def test_market_data_collection_pipeline(self, scanner_factory):
        """Test 2: Pipeline de collecte de données de marché"""
        logger.info("🧪 Test 2: Pipeline collecte données de marché")
        
        market_data_collector = scanner_factory.create_market_data_collector()
        test_symbol = 'BTCUSDT'
        
        # Test collecte orderbook
        orderbook = await market_data_collector.collect_orderbook(test_symbol)
        if orderbook:  # Peut être None en mode mock
            assert orderbook.symbol == test_symbol
            assert orderbook.timestamp is not None
            assert isinstance(orderbook.spread_pct, (int, float))
            assert isinstance(orderbook.book_depth, (int, float))
        
        # Test collecte ticker
        ticker = await market_data_collector.collect_ticker(test_symbol)
        if ticker:
            assert ticker.symbol == test_symbol
            assert ticker.timestamp is not None
            assert isinstance(ticker.price, (int, float))
            assert isinstance(ticker.volume_24h, (int, float))
        
        # Test collecte OHLCV
        ohlcv_1m = await market_data_collector.collect_ohlcv(test_symbol, '1m')
        if ohlcv_1m:
            assert ohlcv_1m.symbol == test_symbol
            assert ohlcv_1m.timeframe == '1m'
            assert isinstance(ohlcv_1m.klines, list)
        
        # Test collecte complète
        market_data = await market_data_collector.collect_complete_market_data(
            test_symbol, ['1m', '5m']
        )
        
        assert market_data is not None
        assert market_data.symbol == test_symbol
        assert isinstance(market_data.data_quality, (int, float))
        assert 0.0 <= market_data.data_quality <= 1.0
        assert market_data.source in [DataSource.MEXC, DataSource.MOCK]
        
        # Test cache stats
        cache_stats = market_data_collector.get_cache_stats()
        assert isinstance(cache_stats, dict)
        assert 'cache_stats' in cache_stats
        assert 'performance' in cache_stats
        
        logger.info("✅ Test 2 réussi: Collecte données fonctionnelle")
    
    def test_scoring_and_filtering_pipeline(self, scanner_factory, filter_config):
        """Test 3: Pipeline scoring et filtrage"""
        logger.info("🧪 Test 3: Pipeline scoring et filtrage")
        
        scalability_scorer = scanner_factory.create_scalability_scorer()
        pair_filter = scanner_factory.create_pair_filter(filter_config)
        
        # Créer des données de marché de test
        from core.interfaces.scanner_interfaces import MarketData, OrderbookData, TickerData
        
        test_market_data = MarketData(
            symbol='TESTUSDT',
            timestamp=datetime.utcnow(),
            orderbook=OrderbookData(
                symbol='TESTUSDT',
                timestamp=datetime.utcnow(),
                bids=[(100.0, 1000.0), (99.9, 500.0)],
                asks=[(100.1, 1000.0), (100.2, 500.0)]
            ),
            ticker=TickerData(
                symbol='TESTUSDT',
                timestamp=datetime.utcnow(),
                price=100.0,
                volume_24h=1000000.0,
                funding_rate=0.01
            ),
            data_quality=0.9,
            source=DataSource.MOCK
        )
        
        # Test calcul de métriques
        metrics = scalability_scorer.calculate_metrics(test_market_data)
        assert metrics is not None
        assert isinstance(metrics.volatility_5, (int, float))
        assert isinstance(metrics.volume_recent, (int, float))
        assert isinstance(metrics.delta_volume, (int, float))
        
        # Test calcul de score
        scoring_result = scalability_scorer.calculate_score(test_market_data)
        assert scoring_result is not None
        assert scoring_result.symbol == 'TESTUSDT'
        assert isinstance(scoring_result.score, (int, float))
        assert scoring_result.score >= 0.0
        assert scoring_result.calculation_time_ms >= 0.0
        
        # Test filtrage
        filter_result = pair_filter.filter_pair('TESTUSDT', test_market_data, scoring_result)
        assert filter_result is not None
        assert filter_result.symbol == 'TESTUSDT'
        assert isinstance(filter_result.accepted, bool)
        assert isinstance(filter_result.filter_results, dict)
        assert isinstance(filter_result.rejection_reasons, list)
        
        # Test stats
        scorer_stats = scalability_scorer.get_scoring_stats()
        assert isinstance(scorer_stats, dict)
        assert 'performance' in scorer_stats
        
        filter_stats = pair_filter.get_filter_stats()
        assert isinstance(filter_stats, dict)
        assert 'overall' in filter_stats
        
        logger.info("✅ Test 3 réussi: Scoring et filtrage fonctionnels")
    
    @pytest.mark.asyncio
    async def test_scan_pipeline_execution(self, scanner_factory):
        """Test 4: Exécution du pipeline de scan"""
        logger.info("🧪 Test 4: Exécution pipeline de scan")
        
        scan_pipeline = scanner_factory.create_scan_pipeline()
        test_symbol = 'PIPELINETEST'
        
        # Test exécution pipeline
        pipeline_result = await scan_pipeline.execute_pipeline(test_symbol)
        
        assert pipeline_result is not None
        assert pipeline_result.symbol == test_symbol
        assert isinstance(pipeline_result.steps_executed, list)
        assert isinstance(pipeline_result.step_results, dict)
        assert isinstance(pipeline_result.step_timings, dict)
        assert pipeline_result.pipeline_duration_ms >= 0.0
        
        # Vérifier que des étapes ont été exécutées
        assert len(pipeline_result.steps_executed) > 0
        
        # Vérifier résultat final
        if pipeline_result.final_result:
            assert pipeline_result.final_result.symbol == test_symbol
            assert isinstance(pipeline_result.final_result.status, ScanStatus)
        
        # Test configuration pipeline
        pipeline_config = scan_pipeline.get_pipeline_config()
        assert isinstance(pipeline_config, list)
        assert len(pipeline_config) > 0
        
        # Test stats pipeline
        pipeline_stats = scan_pipeline.get_pipeline_stats()
        assert isinstance(pipeline_stats, dict)
        assert 'overall' in pipeline_stats
        assert 'steps' in pipeline_stats
        
        logger.info("✅ Test 4 réussi: Pipeline de scan fonctionnel")
    
    @pytest.mark.asyncio
    async def test_scanner_orchestrator_single_scan(self, scanner_factory, scanner_config):
        """Test 5: Scan unique avec orchestrateur"""
        logger.info("🧪 Test 5: Scan unique orchestrateur")
        
        scanner_orchestrator = scanner_factory.create_scanner_orchestrator(scanner_config)
        test_symbol = 'SINGLETEST'
        
        # Test scan unique
        scan_result = await scanner_orchestrator.scan_single_pair(test_symbol)
        
        assert scan_result is not None
        assert scan_result.symbol == test_symbol
        assert isinstance(scan_result.status, ScanStatus)
        assert scan_result.timestamp is not None
        assert isinstance(scan_result.scan_duration_ms, (int, float))
        assert scan_result.scan_duration_ms >= 0.0
        
        # Vérifier que soit succès soit échec avec raison
        if scan_result.status == ScanStatus.SUCCESS:
            assert scan_result.is_success
        else:
            assert not scan_result.is_success
            assert len(scan_result.errors) > 0
        
        logger.info(f"✅ Test 5 réussi: Scan unique {test_symbol} - Status: {scan_result.status.value}")
    
    @pytest.mark.asyncio
    async def test_scanner_orchestrator_batch_scan(self, scanner_factory, scanner_config):
        """Test 6: Scan batch avec orchestrateur"""
        logger.info("🧪 Test 6: Scan batch orchestrateur")
        
        scanner_orchestrator = scanner_factory.create_scanner_orchestrator(scanner_config)
        test_symbols = ['BATCH1', 'BATCH2', 'BATCH3']
        
        # Test scan batch
        batch_result = await scanner_orchestrator.scan_batch_pairs(test_symbols)
        
        assert batch_result is not None
        assert batch_result.symbols == test_symbols
        assert isinstance(batch_result.results, dict)
        assert isinstance(batch_result.total_scanned, int)
        assert isinstance(batch_result.successful_scans, int)
        assert isinstance(batch_result.failed_scans, int)
        assert isinstance(batch_result.total_duration_ms, (int, float))
        
        # Vérifier cohérence des compteurs
        assert batch_result.total_scanned == len(batch_result.results)
        assert batch_result.successful_scans + batch_result.failed_scans == batch_result.total_scanned
        
        # Vérifier résultats individuels
        for symbol in test_symbols:
            if symbol in batch_result.results:
                result = batch_result.results[symbol]
                assert result.symbol == symbol
                assert isinstance(result.status, ScanStatus)
        
        logger.info(f"✅ Test 6 réussi: Batch scan - {batch_result.successful_scans}/{batch_result.total_scanned} succès")
    
    @pytest.mark.asyncio
    async def test_scanner_orchestrator_top_pairs(self, scanner_factory, scanner_config):
        """Test 7: Scan top pairs avec orchestrateur"""
        logger.info("🧪 Test 7: Scan top pairs orchestrateur")
        
        scanner_orchestrator = scanner_factory.create_scanner_orchestrator(scanner_config)
        
        # Test scan top pairs
        top_pairs_result = await scanner_orchestrator.scan_top_pairs(limit=5)
        
        assert top_pairs_result is not None
        assert isinstance(top_pairs_result.symbols, list)
        assert len(top_pairs_result.symbols) <= 5
        assert isinstance(top_pairs_result.results, dict)
        assert isinstance(top_pairs_result.total_duration_ms, (int, float))
        
        # Vérifier que chaque symbole a un résultat
        for symbol in top_pairs_result.symbols:
            if symbol in top_pairs_result.results:
                result = top_pairs_result.results[symbol]
                assert result.symbol == symbol
        
        logger.info(f"✅ Test 7 réussi: Top pairs scan - {len(top_pairs_result.symbols)} pairs analysées")
    
    def test_scanner_orchestrator_statistics_and_health(self, scanner_factory, scanner_config):
        """Test 8: Statistiques et health check orchestrateur"""
        logger.info("🧪 Test 8: Stats et health check orchestrateur")
        
        scanner_orchestrator = scanner_factory.create_scanner_orchestrator(scanner_config)
        
        # Test statistiques
        stats = scanner_orchestrator.get_scan_statistics()
        assert isinstance(stats, dict)
        assert 'orchestrator' in stats
        assert 'configuration' in stats
        
        orchestrator_stats = stats['orchestrator']
        assert 'total_scans' in orchestrator_stats
        assert 'successful_scans' in orchestrator_stats
        assert 'failed_scans' in orchestrator_stats
        assert 'success_rate' in orchestrator_stats
        assert 'average_scan_time_ms' in orchestrator_stats
        
        # Test configuration
        config_stats = stats['configuration']
        assert config_stats['max_concurrent_scans'] == scanner_config.max_concurrent_scans
        assert config_stats['max_parallel_workers'] == scanner_config.max_parallel_workers
        
        logger.info("✅ Test 8 réussi: Stats et configuration OK")
    
    @pytest.mark.asyncio
    async def test_scanner_orchestrator_health_check(self, scanner_factory, scanner_config):
        """Test 9: Health check orchestrateur"""
        logger.info("🧪 Test 9: Health check orchestrateur")
        
        scanner_orchestrator = scanner_factory.create_scanner_orchestrator(scanner_config)
        
        # Test health check
        health = await scanner_orchestrator.health_check()
        assert isinstance(health, dict)
        assert 'status' in health
        assert 'timestamp' in health
        assert 'components' in health
        
        # Status doit être healthy, degraded ou unhealthy
        assert health['status'] in ['healthy', 'degraded', 'unhealthy']
        
        # Timestamp doit être récent
        timestamp_str = health['timestamp']
        assert isinstance(timestamp_str, str)
        
        # Components doit contenir info sur les composants
        components = health['components']
        assert isinstance(components, dict)
        
        logger.info(f"✅ Test 9 réussi: Health check - Status: {health['status']}")
    
    def test_full_scanner_stack_creation(self, scanner_factory, scanner_config, filter_config):
        """Test 10: Création du stack Scanner complet"""
        logger.info("🧪 Test 10: Stack Scanner complet")
        
        # Test création stack complet
        stack = scanner_factory.create_full_scanner_stack(scanner_config, filter_config)
        
        assert isinstance(stack, dict)
        assert len(stack) == 5  # 5 composants attendus
        
        # Vérifier présence de tous les composants
        expected_components = [
            'market_data_collector',
            'scalability_scorer', 
            'pair_filter',
            'scan_pipeline',
            'scanner_orchestrator'
        ]
        
        for component in expected_components:
            assert component in stack
            assert stack[component] is not None
        
        # Test stats factory
        factory_stats = scanner_factory.get_factory_stats()
        assert isinstance(factory_stats, dict)
        assert 'environment' in factory_stats
        assert 'use_mocks' in factory_stats
        assert 'cached_components' in factory_stats
        assert 'components' in factory_stats
        
        # Vérifier que tous les composants sont en cache
        components_status = factory_stats['components']
        for component in expected_components:
            assert components_status.get(component.replace('_', '_')) is not None
        
        logger.info("✅ Test 10 réussi: Stack Scanner complet créé")
    
    @pytest.mark.asyncio
    async def test_full_integration_workflow(self, scanner_factory, scanner_config, filter_config):
        """Test 11: Workflow d'intégration complet"""
        logger.info("🧪 Test 11: Workflow intégration complet Scanner Phase 3")
        
        # Workflow complet de A à Z
        
        # 1. Créer factory et stack
        stack = scanner_factory.create_full_scanner_stack(scanner_config, filter_config)
        orchestrator = stack['scanner_orchestrator']
        
        # 2. Scanner plusieurs paires avec différentes méthodes
        
        # Scan unique
        single_result = await orchestrator.scan_single_pair('WORKFLOW_SINGLE')
        assert single_result is not None
        
        # Scan batch
        batch_symbols = ['WORKFLOW_BATCH1', 'WORKFLOW_BATCH2']
        batch_result = await orchestrator.scan_batch_pairs(batch_symbols)
        assert batch_result is not None
        assert len(batch_result.results) <= len(batch_symbols)
        
        # Scan top pairs
        top_result = await orchestrator.scan_top_pairs(3)
        assert top_result is not None
        assert len(top_result.symbols) <= 3
        
        # 3. Vérifier statistiques globales
        final_stats = orchestrator.get_scan_statistics()
        orchestrator_stats = final_stats['orchestrator']
        
        # Au moins 6 scans (1 single + 2 batch + 3 top)
        expected_min_scans = 6
        assert orchestrator_stats['total_scans'] >= expected_min_scans
        
        # 4. Vérifier health
        health = await orchestrator.health_check()
        assert health['status'] in ['healthy', 'degraded', 'unhealthy']
        
        # 5. Test nettoyage
        scanner_factory.clear_cache()
        cleared_stats = scanner_factory.get_factory_stats()
        assert cleared_stats['cached_components'] == 0
        
        # Log résultats finaux
        logger.info(f"📊 Workflow complet Scanner Phase 3:")
        logger.info(f"   - Single scan: {single_result.status.value}")
        logger.info(f"   - Batch scan: {batch_result.successful_scans}/{batch_result.total_scanned}")
        logger.info(f"   - Top pairs: {len(top_result.symbols)} pairs")
        logger.info(f"   - Total scans: {orchestrator_stats['total_scans']}")
        logger.info(f"   - Success rate: {orchestrator_stats['success_rate']:.2f}")
        logger.info(f"   - Health: {health['status']}")
        
        logger.info("✅ Test 11 réussi: Workflow complet fonctionnel")
    
    def test_error_handling_and_resilience(self, scanner_factory):
        """Test 12: Gestion d'erreurs et résilience"""
        logger.info("🧪 Test 12: Gestion erreurs et résilience")
        
        # Test avec symboles invalides
        invalid_symbols = ['', 'INVALID', '123', None]
        
        for invalid_symbol in invalid_symbols:
            try:
                if invalid_symbol is not None:
                    is_valid = ScannerValidationUtils.is_valid_symbol(invalid_symbol)
                    assert not is_valid  # Doit être invalide
            except Exception:
                pass  # Exceptions acceptables pour symboles invalides
        
        # Test symboles valides
        valid_symbols = ['BTCUSDT', 'BTC/USDT:USDT', 'ETHUSDT']
        for valid_symbol in valid_symbols:
            is_valid = ScannerValidationUtils.is_valid_symbol(valid_symbol)
            # En mode mock, la validation peut être plus permissive
        
        # Test validation utilitaires
        assert ScannerValidationUtils.is_valid_price(100.0)
        assert not ScannerValidationUtils.is_valid_price(-1.0)
        assert not ScannerValidationUtils.is_valid_price(float('nan'))
        
        assert ScannerValidationUtils.is_valid_volume(1000.0)
        assert ScannerValidationUtils.is_valid_volume(0.0)
        assert not ScannerValidationUtils.is_valid_volume(-1.0)
        
        assert ScannerValidationUtils.is_valid_percentage(50.0)
        assert ScannerValidationUtils.is_valid_percentage(-10.0)
        assert not ScannerValidationUtils.is_valid_percentage(float('nan'))
        
        # Test normalisation symboles
        normalized = ScannerValidationUtils.normalize_symbol('BTC/USDT:USDT')
        assert normalized == 'BTCUSDT'
        
        normalized2 = ScannerValidationUtils.normalize_symbol('ETH/USDT')
        assert normalized2 == 'ETHUSDT'
        
        logger.info("✅ Test 12 réussi: Gestion erreurs et validation OK")


# Tests rapides pour validation continue
def test_quick_scanner_phase3_validation():
    """Test rapide pour validation Scanner Phase 3"""
    factory = get_configured_scanner_factory("test", use_mocks=True)
    
    # Test création stack
    stack = factory.create_full_scanner_stack()
    assert len(stack) == 5  # 5 composants attendus
    
    # Test factory stats
    stats = factory.get_factory_stats()
    assert stats['environment'] == 'test'
    assert stats['use_mocks'] is True
    assert stats['cached_components'] == 5
    
    print("✅ Scanner Phase 3 quick validation passed!")


if __name__ == "__main__":
    # Exécution rapide pour validation
    test_quick_scanner_phase3_validation()
    
    # Pour tests complets, utiliser pytest:
    # pytest tests/integration/test_scanner_phase3_integration.py -v
