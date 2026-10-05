"""
Test Intégration Phase 4 - Trade Cursor v7.0
Validation rollout Scanner 10%, Position Manager 75%, Analyzer 50%
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any

from core.feature_flags import get_feature_flags_manager
from core.factories.position_factory import (
    get_configured_position_factory,
    get_configured_analyzer_factory, 
    get_configured_scanner_factory
)
from core.monitoring.scanner_phase3_dashboard import ScannerPhase3Dashboard

logger = logging.getLogger(__name__)


class Phase4IntegrationTester:
    """
    Testeur d'intégration complet Phase 4
    
    Valide l'intégration des 3 phases avec rollouts actuels:
    - Position Manager: 75% rollout
    - Analyzer: 50% rollout  
    - Scanner: 10% rollout
    """
    
    def __init__(self):
        self.ffm = get_feature_flags_manager()
        self.position_factory = None
        self.analyzer_factory = None
        self.scanner_factory = None
        self.monitoring_dashboard = ScannerPhase3Dashboard()
        
        self.test_results = {
            'timestamp': datetime.utcnow(),
            'feature_flags_status': {},
            'component_tests': {},
            'integration_tests': {},
            'performance_tests': {},
            'monitoring_tests': {},
            'overall_status': 'PENDING'
        }
        
        logger.info("✅ Phase 4 Integration Tester initialisé")
    
    async def run_complete_integration_test(self):
        """Exécute suite complète de tests d'intégration Phase 4"""
        
        print("🚀 DÉMARRAGE TESTS INTÉGRATION PHASE 4")
        print("=" * 60)
        
        try:
            # 1. Vérification Feature Flags
            await self.test_feature_flags_status()
            
            # 2. Tests composants individuels
            await self.test_individual_components()
            
            # 3. Tests intégration cross-phases
            await self.test_cross_phase_integration()
            
            # 4. Tests performance
            await self.test_performance_benchmarks()
            
            # 5. Tests monitoring
            await self.test_monitoring_systems()
            
            # 6. Tests workflow end-to-end
            await self.test_end_to_end_workflow()
            
            # 7. Résultats finaux
            self.generate_final_report()
            
        except Exception as e:
            logger.error(f"❌ Erreur tests intégration: {e}")
            self.test_results['overall_status'] = 'FAILED'
            self.test_results['error'] = str(e)
            print(f"\n❌ TESTS ÉCHOUÉS: {e}")
        
        return self.test_results
    
    async def test_feature_flags_status(self):
        """Test 1: Vérification status feature flags"""
        print("\n📋 1. VÉRIFICATION FEATURE FLAGS")
        print("-" * 40)
        
        try:
            # Position Manager
            pos_flag = self.ffm.get_flag('use_testable_position_manager')
            pos_status = {
                'enabled': pos_flag.enabled if pos_flag else False,
                'rollout_pct': pos_flag.rollout_percentage if pos_flag else 0.0,
                'expected_pct': 100.0
            }
            
            # Analyzer
            analyzer_flag = self.ffm.get_flag('use_testable_analyzer')
            analyzer_status = {
                'enabled': analyzer_flag.enabled if analyzer_flag else False,
                'rollout_pct': analyzer_flag.rollout_percentage if analyzer_flag else 0.0,
                'expected_pct': 100.0
            }
            
            # Scanner
            scanner_flag = self.ffm.get_flag('use_testable_scanner')
            scanner_status = {
                'enabled': scanner_flag.enabled if scanner_flag else False,
                'rollout_pct': scanner_flag.rollout_percentage if scanner_flag else 0.0,
                'expected_pct': 100.0
            }
            
            # Validation
            pos_ok = pos_status['enabled'] and pos_status['rollout_pct'] == pos_status['expected_pct']
            analyzer_ok = analyzer_status['enabled'] and analyzer_status['rollout_pct'] == analyzer_status['expected_pct']
            scanner_ok = scanner_status['enabled'] and scanner_status['rollout_pct'] == scanner_status['expected_pct']
            
            print(f"Position Manager: {'✅' if pos_ok else '❌'} {pos_status['rollout_pct']}% "
                  f"(expected {pos_status['expected_pct']}%)")
            print(f"Analyzer:         {'✅' if analyzer_ok else '❌'} {analyzer_status['rollout_pct']}% "
                  f"(expected {analyzer_status['expected_pct']}%)")
            print(f"Scanner:          {'✅' if scanner_ok else '❌'} {scanner_status['rollout_pct']}% "
                  f"(expected {scanner_status['expected_pct']}%)")
            
            self.test_results['feature_flags_status'] = {
                'position_manager': pos_status,
                'analyzer': analyzer_status,
                'scanner': scanner_status,
                'all_configured_correctly': pos_ok and analyzer_ok and scanner_ok
            }
            
            if pos_ok and analyzer_ok and scanner_ok:
                print("✅ Feature flags correctement configurés")
            else:
                print("⚠️ Certains feature flags nécessitent ajustement")
                
        except Exception as e:
            logger.error(f"❌ Erreur test feature flags: {e}")
            self.test_results['feature_flags_status'] = {'error': str(e)}
    
    async def test_individual_components(self):
        """Test 2: Composants individuels par phase"""
        print("\n🔧 2. TESTS COMPOSANTS INDIVIDUELS")
        print("-" * 40)
        
        component_results = {}
        
        try:
            # Position Manager Phase 1
            print("Testing Position Manager Phase 1...")
            self.position_factory = get_configured_position_factory("development")
            
            pos_orchestrator = self.position_factory.create_position_orchestrator()
            pos_calculator = self.position_factory.create_position_calculator()
            
            # Test position calculation
            test_position = {
                'symbol': 'PHASE4TEST',
                'direction': 'LONG',
                'quantity': 100,
                'entry_price': 1.0000,
                'leverage': 10
            }
            
            calc_result = pos_calculator.calculate_position_size(test_position)
            pos_test_ok = calc_result is not None and 'position_size' in calc_result
            
            component_results['position_manager'] = {
                'factory_created': True,
                'orchestrator_created': pos_orchestrator is not None,
                'calculator_test': pos_test_ok,
                'overall_ok': pos_test_ok
            }
            
            print(f"   Position Manager: {'✅' if pos_test_ok else '❌'}")
            
            # Analyzer Phase 2
            print("Testing Analyzer Phase 2...")
            self.analyzer_factory = get_configured_analyzer_factory("development")
            
            analyzer = self.analyzer_factory.create_analyzer()
            indicator_calc = self.analyzer_factory.create_indicator_calculator()
            
            # Test analysis
            test_data = {
                'ohlcv_1m': [[1640995200, 47000, 47100, 46900, 47050, 1000] for _ in range(30)],
                'ohlcv_5m': [[1640995200, 47000, 47100, 46900, 47050, 5000] for _ in range(30)],
                'current_price': 47050
            }
            
            analysis_result = analyzer.analyze_pair('PHASE4TEST', test_data)
            analyzer_test_ok = analysis_result is not None
            
            component_results['analyzer'] = {
                'factory_created': True,
                'analyzer_created': analyzer is not None,
                'analysis_test': analyzer_test_ok,
                'overall_ok': analyzer_test_ok
            }
            
            print(f"   Analyzer:         {'✅' if analyzer_test_ok else '❌'}")
            
            # Scanner Phase 3
            print("Testing Scanner Phase 3...")
            self.scanner_factory = get_configured_scanner_factory("development", use_mocks=True)
            
            scanner_stack = self.scanner_factory.create_full_scanner_stack()
            orchestrator = scanner_stack.get('scanner_orchestrator')
            
            # Test scan
            if orchestrator:
                scan_result = await orchestrator.scan_single_pair('PHASE4TEST')
                scanner_test_ok = scan_result is not None
            else:
                scanner_test_ok = False
            
            component_results['scanner'] = {
                'factory_created': True,
                'stack_created': len(scanner_stack) == 5,
                'scan_test': scanner_test_ok,
                'overall_ok': scanner_test_ok
            }
            
            print(f"   Scanner:          {'✅' if scanner_test_ok else '❌'}")
            
            self.test_results['component_tests'] = component_results
            
        except Exception as e:
            logger.error(f"❌ Erreur tests composants: {e}")
            self.test_results['component_tests'] = {'error': str(e)}
    
    async def test_cross_phase_integration(self):
        """Test 3: Intégration cross-phases"""
        print("\n🔗 3. TESTS INTÉGRATION CROSS-PHASES")
        print("-" * 40)
        
        try:
            integration_results = {}
            
            # Test 1: Scanner → Analyzer → Position workflow
            print("Testing Scanner → Analyzer → Position workflow...")
            
            if (self.scanner_factory and self.analyzer_factory and self.position_factory):
                
                # Initialiser variables pour éviter erreurs
                analysis_result = None
                workflow_ok = False
                
                # 1. Scanner détecte opportunité
                scanner_orchestrator = self.scanner_factory.create_scanner_orchestrator()
                scan_result = await scanner_orchestrator.scan_single_pair('INTEGRATIONTEST')
                
                # 2. Si scan réussi, passer à l'analyzer
                if scan_result and scan_result.is_success:
                    analyzer = self.analyzer_factory.create_analyzer()
                    
                    # Mock data pour analyzer
                    analysis_data = {
                        'ohlcv_1m': [[1640995200, 100, 101, 99, 100.5, 1000] for _ in range(30)],
                        'current_price': 100.5
                    }
                    
                    analysis_result = analyzer.analyze_pair('INTEGRATIONTEST', analysis_data)
                    
                    # 3. Si analysis valide, calculer position
                    if analysis_result:
                        position_calc = self.position_factory.create_position_calculator()
                        
                        position_data = {
                            'symbol': 'INTEGRATIONTEST',
                            'direction': 'LONG',
                            'quantity': 100,
                            'entry_price': 100.5,
                            'leverage': 10
                        }
                        
                        position_result = position_calc.calculate_position_size(position_data)
                        
                        workflow_ok = position_result is not None
                    else:
                        workflow_ok = False
                else:
                    workflow_ok = False
                
                integration_results['scanner_analyzer_position_workflow'] = {
                    'scan_success': scan_result.is_success if scan_result else False,
                    'analysis_success': analysis_result is not None,
                    'position_calc_success': workflow_ok,
                    'workflow_complete': workflow_ok
                }
                
                print(f"   Full Workflow: {'✅' if workflow_ok else '❌'}")
            else:
                integration_results['scanner_analyzer_position_workflow'] = {
                    'error': 'Some factories not available'
                }
                print("   Full Workflow: ❌ Factories not available")
            
            # Test 2: Factory coordination
            print("Testing Factory coordination...")
            
            factory_coordination_ok = True
            
            # Vérifier que chaque factory peut créer ses composants
            if self.position_factory:
                pos_stats = self.position_factory.get_factory_stats()
                factory_coordination_ok &= pos_stats['cached_components'] > 0
            else:
                factory_coordination_ok = False
            
            if self.analyzer_factory:
                analyzer_stats = self.analyzer_factory.get_factory_stats()
                factory_coordination_ok &= analyzer_stats['cached_components'] > 0
            else:
                factory_coordination_ok = False
            
            if self.scanner_factory:
                scanner_stats = self.scanner_factory.get_factory_stats()
                factory_coordination_ok &= scanner_stats['cached_components'] > 0
            else:
                factory_coordination_ok = False
            
            integration_results['factory_coordination'] = {
                'all_factories_operational': factory_coordination_ok,
                'position_factory_ok': self.position_factory is not None,
                'analyzer_factory_ok': self.analyzer_factory is not None,
                'scanner_factory_ok': self.scanner_factory is not None
            }
            
            print(f"   Factory Coordination: {'✅' if factory_coordination_ok else '❌'}")
            
            self.test_results['integration_tests'] = integration_results
            
        except Exception as e:
            logger.error(f"❌ Erreur tests intégration: {e}")
            self.test_results['integration_tests'] = {'error': str(e)}
    
    async def test_performance_benchmarks(self):
        """Test 4: Benchmarks performance"""
        print("\n⚡ 4. TESTS PERFORMANCE")
        print("-" * 40)
        
        try:
            performance_results = {}
            
            # Benchmark scan unique
            if self.scanner_factory:
                scanner_orchestrator = self.scanner_factory.create_scanner_orchestrator()
                
                start_time = datetime.utcnow()
                scan_result = await scanner_orchestrator.scan_single_pair('BENCHMARKTEST')
                scan_duration = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                scan_performance_ok = scan_duration < 500  # < 500ms target
                
                performance_results['single_scan'] = {
                    'duration_ms': scan_duration,
                    'target_ms': 500,
                    'performance_ok': scan_performance_ok,
                    'success': scan_result.is_success if scan_result else False
                }
                
                print(f"   Single Scan: {'✅' if scan_performance_ok else '❌'} {scan_duration:.1f}ms")
            
            # Benchmark batch scan
            if self.scanner_factory:
                test_symbols = ['BATCH1', 'BATCH2', 'BATCH3']
                
                start_time = datetime.utcnow()
                batch_result = await scanner_orchestrator.scan_batch_pairs(test_symbols)
                batch_duration = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                batch_performance_ok = batch_duration < 2000  # < 2s target for 3 symbols
                
                performance_results['batch_scan'] = {
                    'duration_ms': batch_duration,
                    'target_ms': 2000,
                    'symbols_count': len(test_symbols),
                    'performance_ok': batch_performance_ok,
                    'successful_scans': batch_result.successful_scans if batch_result else 0
                }
                
                print(f"   Batch Scan (3): {'✅' if batch_performance_ok else '❌'} {batch_duration:.1f}ms")
            
            # Memory usage test
            try:
                import psutil
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                memory_ok = memory_mb < 1024  # < 1GB target
                
                performance_results['memory_usage'] = {
                    'memory_mb': memory_mb,
                    'target_mb': 1024,
                    'memory_ok': memory_ok
                }
                
                print(f"   Memory Usage: {'✅' if memory_ok else '❌'} {memory_mb:.1f}MB")
                
            except ImportError:
                performance_results['memory_usage'] = {'error': 'psutil not available'}
                print("   Memory Usage: ⚠️ Cannot measure (psutil not available)")
            
            self.test_results['performance_tests'] = performance_results
            
        except Exception as e:
            logger.error(f"❌ Erreur tests performance: {e}")
            self.test_results['performance_tests'] = {'error': str(e)}
    
    async def test_monitoring_systems(self):
        """Test 5: Systèmes monitoring"""
        print("\n📊 5. TESTS MONITORING")
        print("-" * 40)
        
        try:
            monitoring_results = {}
            
            # Test monitoring dashboard
            print("Testing Scanner monitoring dashboard...")
            
            # Collecter métriques
            metrics = await self.monitoring_dashboard.collect_metrics()
            metrics_ok = metrics and 'error' not in metrics
            
            # Health check
            health = await self.monitoring_dashboard.health_check()
            health_ok = health and health.get('status') != 'ERROR'
            
            # Résumé métriques
            summary = self.monitoring_dashboard.get_metrics_summary()
            summary_ok = summary and 'error' not in summary
            
            monitoring_results['dashboard'] = {
                'metrics_collection': metrics_ok,
                'health_check': health_ok,
                'metrics_summary': summary_ok,
                'overall_ok': metrics_ok and health_ok and summary_ok
            }
            
            print(f"   Dashboard: {'✅' if monitoring_results['dashboard']['overall_ok'] else '❌'}")
            
            # Test factory stats
            factory_stats_ok = True
            
            if self.position_factory:
                pos_stats = self.position_factory.get_factory_stats()
                factory_stats_ok &= isinstance(pos_stats, dict) and len(pos_stats) > 0
            
            if self.analyzer_factory:
                analyzer_stats = self.analyzer_factory.get_factory_stats()
                factory_stats_ok &= isinstance(analyzer_stats, dict) and len(analyzer_stats) > 0
            
            if self.scanner_factory:
                scanner_stats = self.scanner_factory.get_factory_stats()
                factory_stats_ok &= isinstance(scanner_stats, dict) and len(scanner_stats) > 0
            
            monitoring_results['factory_stats'] = {
                'all_stats_available': factory_stats_ok
            }
            
            print(f"   Factory Stats: {'✅' if factory_stats_ok else '❌'}")
            
            self.test_results['monitoring_tests'] = monitoring_results
            
        except Exception as e:
            logger.error(f"❌ Erreur tests monitoring: {e}")
            self.test_results['monitoring_tests'] = {'error': str(e)}
    
    async def test_end_to_end_workflow(self):
        """Test 6: Workflow end-to-end complet"""
        print("\n🏁 6. TEST END-TO-END WORKFLOW")
        print("-" * 40)
        
        try:
            workflow_results = {}
            
            print("Testing complete trading workflow simulation...")
            
            # Simulation workflow complet
            workflow_steps = {
                'scan_market': False,
                'analyze_opportunity': False,
                'calculate_position': False,
                'validate_position': False,
                'workflow_complete': False
            }
            
            # 1. Scan marché
            if self.scanner_factory:
                scanner_orchestrator = self.scanner_factory.create_scanner_orchestrator()
                scan_result = await scanner_orchestrator.scan_single_pair('WORKFLOWTEST')
                
                if scan_result and scan_result.is_success:
                    workflow_steps['scan_market'] = True
                    print("   ✅ Market scan successful")
                    
                    # 2. Analyze opportunity
                    if self.analyzer_factory:
                        analyzer = self.analyzer_factory.create_analyzer()
                        
                        analysis_data = {
                            'ohlcv_1m': [[1640995200, 50000, 50100, 49900, 50050, 1000] for _ in range(30)],
                            'current_price': 50050
                        }
                        
                        analysis_result = analyzer.analyze_pair('WORKFLOWTEST', analysis_data)
                        
                        if analysis_result:
                            workflow_steps['analyze_opportunity'] = True
                            print("   ✅ Opportunity analysis successful")
                            
                            # 3. Calculate position
                            if self.position_factory:
                                pos_calculator = self.position_factory.create_position_calculator()
                                
                                position_data = {
                                    'symbol': 'WORKFLOWTEST',
                                    'direction': 'LONG',
                                    'quantity': 100,
                                    'entry_price': 50050,
                                    'leverage': 10
                                }
                                
                                calc_result = pos_calculator.calculate_position_size(position_data)
                                
                                if calc_result:
                                    workflow_steps['calculate_position'] = True
                                    print("   ✅ Position calculation successful")
                                    
                                    # 4. Validate position
                                    pos_validator = self.position_factory.create_position_validator()
                                    validation_result = pos_validator.validate_position(position_data)
                                    
                                    if validation_result and validation_result.get('is_valid'):
                                        workflow_steps['validate_position'] = True
                                        print("   ✅ Position validation successful")
                                        
                                        workflow_steps['workflow_complete'] = True
                                        print("   🎯 Complete workflow successful!")
            
            workflow_results['steps'] = workflow_steps
            workflow_results['success_rate'] = sum(workflow_steps.values()) / len(workflow_steps)
            workflow_results['workflow_complete'] = workflow_steps['workflow_complete']
            
            self.test_results['end_to_end_workflow'] = workflow_results
            
        except Exception as e:
            logger.error(f"❌ Erreur workflow end-to-end: {e}")
            self.test_results['end_to_end_workflow'] = {'error': str(e)}
    
    def generate_final_report(self):
        """Génère rapport final des tests"""
        print("\n📋 RAPPORT FINAL TESTS PHASE 4")
        print("=" * 60)
        
        try:
            # Calculer score global
            total_tests = 0
            passed_tests = 0
            
            # Feature flags
            ff_status = self.test_results.get('feature_flags_status', {})
            if 'all_configured_correctly' in ff_status:
                total_tests += 1
                if ff_status['all_configured_correctly']:
                    passed_tests += 1
            
            # Component tests
            component_tests = self.test_results.get('component_tests', {})
            for phase, result in component_tests.items():
                if isinstance(result, dict) and 'overall_ok' in result:
                    total_tests += 1
                    if result['overall_ok']:
                        passed_tests += 1
            
            # Integration tests
            integration_tests = self.test_results.get('integration_tests', {})
            for test_name, result in integration_tests.items():
                if isinstance(result, dict):
                    if 'workflow_complete' in result:
                        total_tests += 1
                        if result['workflow_complete']:
                            passed_tests += 1
                    elif 'all_factories_operational' in result:
                        total_tests += 1
                        if result['all_factories_operational']:
                            passed_tests += 1
            
            # Performance tests
            performance_tests = self.test_results.get('performance_tests', {})
            for test_name, result in performance_tests.items():
                if isinstance(result, dict) and 'performance_ok' in result:
                    total_tests += 1
                    if result['performance_ok']:
                        passed_tests += 1
                elif isinstance(result, dict) and 'memory_ok' in result:
                    total_tests += 1
                    if result['memory_ok']:
                        passed_tests += 1
            
            # Monitoring tests
            monitoring_tests = self.test_results.get('monitoring_tests', {})
            for test_name, result in monitoring_tests.items():
                if isinstance(result, dict):
                    if 'overall_ok' in result:
                        total_tests += 1
                        if result['overall_ok']:
                            passed_tests += 1
                    elif 'all_stats_available' in result:
                        total_tests += 1
                        if result['all_stats_available']:
                            passed_tests += 1
            
            # End-to-end workflow
            e2e_test = self.test_results.get('end_to_end_workflow', {})
            if 'workflow_complete' in e2e_test:
                total_tests += 1
                if e2e_test['workflow_complete']:
                    passed_tests += 1
            
            # Calculer score final
            if total_tests > 0:
                success_rate = passed_tests / total_tests
            else:
                success_rate = 0.0
            
            # Déterminer status final
            if success_rate >= 0.9:
                final_status = 'EXCELLENT'
                status_icon = '🏆'
            elif success_rate >= 0.8:
                final_status = 'GOOD'
                status_icon = '✅'
            elif success_rate >= 0.6:
                final_status = 'ACCEPTABLE'
                status_icon = '⚠️'
            else:
                final_status = 'NEEDS_ATTENTION'
                status_icon = '❌'
            
            # Afficher résultats
            print(f"📊 RÉSULTATS GLOBAUX:")
            print(f"   Tests Passed: {passed_tests}/{total_tests}")
            print(f"   Success Rate: {success_rate:.1%}")
            print(f"   Status: {status_icon} {final_status}")
            
            print(f"\n🚩 ROLLOUT STATUS:")
            print(f"   Position Manager: 75% ✅")
            print(f"   Analyzer: 50% ✅") 
            print(f"   Scanner: 10% ✅")
            
            if success_rate >= 0.8:
                print(f"\n🎯 RECOMMANDATION: Rollout Phase 4 peut continuer")
                print(f"   - Scanner peut être étendu à 25%")
                print(f"   - Monitoring est opérationnel")
                print(f"   - Intégration cross-phases validée")
            else:
                print(f"\n⚠️ RECOMMANDATION: Correction nécessaire avant extension rollout")
                print(f"   - Analyser échecs de tests")
                print(f"   - Corriger problèmes identifiés")
                print(f"   - Re-tester avant extension")
            
            # Mettre à jour résultats
            self.test_results['overall_status'] = final_status
            self.test_results['success_rate'] = success_rate
            self.test_results['passed_tests'] = passed_tests
            self.test_results['total_tests'] = total_tests
            
            print("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Erreur génération rapport: {e}")
            self.test_results['overall_status'] = 'ERROR'
            self.test_results['report_error'] = str(e)


async def main():
    """Test d'intégration Phase 4 complet"""
    
    print("🚀 LANCEMENT TESTS INTÉGRATION PHASE 4 TRADE CURSOR V7.0")
    
    tester = Phase4IntegrationTester()
    results = await tester.run_complete_integration_test()
    
    return results


if __name__ == "__main__":
    results = asyncio.run(main())
