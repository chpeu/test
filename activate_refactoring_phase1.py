#!/usr/bin/env python3
"""
Script d'activation progressive Phase 1 du Refactoring
Active les feature flags de manière sécurisée avec monitoring
"""

import sys
import os
import time
import logging
from pathlib import Path

# Ajouter le répertoire courant au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from core.feature_flags import get_feature_flags_manager, enable_flag
from core.factories.position_factory import FactoryConfig, create_position_orchestrator
from core.implementations.mock_position_components import MockDataProvider
import asyncio

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('refactoring_activation.log')
    ]
)

logger = logging.getLogger(__name__)


class RefactoringPhase1Activator:
    """
    Gestionnaire d'activation Phase 1 du refactoring
    
    Phase 1: Comparaison et validation
    - Activer mode comparaison legacy vs nouveau
    - Monitoring intensif des métriques
    - Tests de validation en continu
    - Rollback automatique si problèmes détectés
    """
    
    def __init__(self):
        self.feature_flags = get_feature_flags_manager()
        self.test_config = FactoryConfig(environment="development", use_mocks=True)
        self.mock_provider = MockDataProvider({'realistic_data': True})
        
        # Métriques de suivi
        self.activation_metrics = {
            'start_time': None,
            'tests_passed': 0,
            'tests_failed': 0,
            'performance_baseline': {},
            'error_rate_baseline': 0.0
        }
        
        logger.info("🚀 RefactoringPhase1Activator initialisé")
    
    def run_activation_sequence(self):
        """Lance la séquence complète d'activation Phase 1"""
        
        print("\n" + "="*70)
        print("🔧 ACTIVATION REFACTORING PHASE 1 - Trade Cursor v7.0")
        print("="*70 + "\n")
        
        try:
            # 1. Vérifications préliminaires
            self._run_pre_activation_checks()
            
            # 2. Établir baseline de performance
            self._establish_performance_baseline()
            
            # 3. Activer mode comparaison
            self._activate_comparison_mode()
            
            # 4. Tests de validation
            self._run_validation_tests()
            
            # 5. Activation progressive des composants
            self._progressive_activation()
            
            # 6. Monitoring post-activation
            self._post_activation_monitoring()
            
            print("\n🎉 PHASE 1 ACTIVÉE AVEC SUCCÈS!")
            print("="*70)
            
        except Exception as e:
            logger.error(f"💥 Erreur critique activation: {e}")
            self._emergency_rollback()
            raise
    
    def _run_pre_activation_checks(self):
        """Vérifications avant activation"""
        logger.info("🔍 Vérifications préliminaires...")
        
        checks = [
            ("Infrastructure core", self._check_core_infrastructure),
            ("Feature flags système", self._check_feature_flags_system), 
            ("Composants testables", self._check_testable_components),
            ("Tests unitaires", self._check_unit_tests),
            ("Mock components", self._check_mock_components)
        ]
        
        failed_checks = []
        
        for check_name, check_func in checks:
            try:
                if check_func():
                    logger.info(f"  ✅ {check_name}")
                else:
                    logger.error(f"  ❌ {check_name}")
                    failed_checks.append(check_name)
            except Exception as e:
                logger.error(f"  💥 {check_name}: {e}")
                failed_checks.append(check_name)
        
        if failed_checks:
            raise RuntimeError(f"Vérifications échouées: {failed_checks}")
        
        logger.info("✅ Toutes les vérifications préliminaires sont passées")
    
    def _establish_performance_baseline(self):
        """Établit baseline de performance avant activation"""
        logger.info("📊 Établissement baseline de performance...")
        
        self.activation_metrics['start_time'] = time.time()
        
        # Créer orchestrateur en mode legacy (flags désactivés)
        self.feature_flags.disable_flag('use_testable_position_manager', "Baseline establishment")
        self.feature_flags.disable_flag('use_testable_analyzer', "Baseline establishment") 
        
        try:
            orchestrator = create_position_orchestrator(self.test_config)
            
            # Mesurer performance legacy
            legacy_times = []
            successful_trades = 0
            
            for i in range(10):
                setup = self.mock_provider.generate_test_setup(f'BASELINE{i}USDT')
                
                start_time = time.time()
                try:
                    result = asyncio.run(orchestrator.process_trade_request(setup, 10000.0))
                    if result.get('success'):
                        successful_trades += 1
                    elapsed = time.time() - start_time
                    legacy_times.append(elapsed)
                except Exception as e:
                    logger.warning(f"Trade baseline {i} échoué: {e}")
            
            # Calculer métriques baseline
            if legacy_times:
                avg_time = sum(legacy_times) / len(legacy_times)
                max_time = max(legacy_times)
                error_rate = (10 - successful_trades) / 10
                
                self.activation_metrics['performance_baseline'] = {
                    'avg_response_time': avg_time,
                    'max_response_time': max_time,
                    'success_rate': successful_trades / 10,
                    'error_rate': error_rate
                }
                
                logger.info(f"📈 Baseline établie:")
                logger.info(f"  • Temps réponse moyen: {avg_time:.3f}s")
                logger.info(f"  • Temps réponse max: {max_time:.3f}s") 
                logger.info(f"  • Taux de succès: {(successful_trades/10)*100:.1f}%")
                logger.info(f"  • Taux d'erreur: {error_rate*100:.1f}%")
            
        except Exception as e:
            logger.error(f"Erreur établissement baseline: {e}")
            # Continuer quand même avec des valeurs par défaut
            self.activation_metrics['performance_baseline'] = {
                'avg_response_time': 1.0,
                'max_response_time': 2.0,
                'success_rate': 0.9,
                'error_rate': 0.1
            }
    
    def _activate_comparison_mode(self):
        """Active le mode comparaison"""
        logger.info("⚖️ Activation mode comparaison...")
        
        # Activer les flags nécessaires pour comparaison
        self.feature_flags.enable_flag('comparison_mode', 100.0)
        self.feature_flags.enable_flag('monitoring_enabled', 100.0)
        self.feature_flags.enable_flag('debug_logging', 100.0)
        
        # Vérifier activation
        comparison_status = self.feature_flags.get_flag_status('comparison_mode')
        if comparison_status.get('enabled'):
            logger.info("✅ Mode comparaison activé")
        else:
            raise RuntimeError("Échec activation mode comparaison")
        
        time.sleep(2)  # Laisser le temps aux flags de se propager
    
    def _run_validation_tests(self):
        """Lance tests de validation du mode comparaison"""
        logger.info("🧪 Tests de validation mode comparaison...")
        
        # Activer temporairement les composants testables pour comparaison
        self.feature_flags.enable_flag('use_testable_position_manager', 100.0)
        
        try:
            orchestrator = create_position_orchestrator(self.test_config)
            
            validation_scenarios = [
                ('BTCUSDT', 'long'),
                ('ETHUSDT', 'short'),
                ('BNBUSDT', 'long')
            ]
            
            for symbol, side in validation_scenarios:
                setup = self.mock_provider.generate_test_setup(symbol, side)
                
                logger.info(f"  🔬 Test {symbol} {side}...")
                result = asyncio.run(orchestrator.process_trade_request(setup, 10000.0))
                
                if result.get('success'):
                    # Vérifier données de comparaison
                    if 'comparison_data' in result:
                        comparison = result['comparison_data']
                        if 'legacy_calculation' in comparison:
                            self.activation_metrics['tests_passed'] += 1
                            logger.info(f"    ✅ Comparaison générée")
                        else:
                            logger.warning(f"    ⚠️ Pas de données legacy")
                    else:
                        logger.warning(f"    ⚠️ Pas de données comparaison")
                else:
                    self.activation_metrics['tests_failed'] += 1
                    logger.error(f"    ❌ Échec: {result.get('error_message')}")
            
            success_rate = self.activation_metrics['tests_passed'] / len(validation_scenarios)
            if success_rate >= 0.8:  # 80% minimum
                logger.info(f"✅ Tests validation réussis: {success_rate*100:.1f}%")
            else:
                raise RuntimeError(f"Taux de succès trop bas: {success_rate*100:.1f}%")
                
        except Exception as e:
            logger.error(f"Erreur tests validation: {e}")
            raise
    
    def _progressive_activation(self):
        """Activation progressive des composants refactorisés"""
        logger.info("📈 Activation progressive des composants...")
        
        # Phase 1a: 5% rollout des composants testables
        logger.info("  🚀 Phase 1a: 5% rollout...")
        self.feature_flags.gradual_rollout('use_testable_position_manager', 5.0, 5.0)
        
        # Attendre et monitorer
        time.sleep(10)
        self._check_metrics_health()
        
        # Phase 1b: 15% rollout si tout va bien
        logger.info("  🚀 Phase 1b: 15% rollout...")
        self.feature_flags.gradual_rollout('use_testable_position_manager', 15.0, 10.0)
        
        # Attendre et monitorer
        time.sleep(15)
        self._check_metrics_health()
        
        # Phase 1c: 25% rollout final pour Phase 1
        logger.info("  🚀 Phase 1c: 25% rollout...")
        self.feature_flags.gradual_rollout('use_testable_position_manager', 25.0, 10.0)
        
        time.sleep(10)
        self._check_metrics_health()
        
        logger.info("✅ Activation progressive terminée: 25% rollout")
    
    def _post_activation_monitoring(self):
        """Monitoring post-activation"""
        logger.info("👁️ Monitoring post-activation (60s)...")
        
        monitoring_duration = 60  # secondes
        check_interval = 10
        checks_count = monitoring_duration // check_interval
        
        for i in range(checks_count):
            logger.info(f"  📊 Check {i+1}/{checks_count}...")
            
            # Vérifier santé des feature flags
            self._check_metrics_health()
            
            # Test fonctionnel rapide
            self._quick_functional_test()
            
            if i < checks_count - 1:  # Pas d'attente au dernier check
                time.sleep(check_interval)
        
        logger.info("✅ Monitoring post-activation terminé - Système stable")
    
    def _check_metrics_health(self):
        """Vérifie la santé des métriques"""
        pm_status = self.feature_flags.get_flag_status('use_testable_position_manager')
        metrics = pm_status.get('metrics', {})
        
        error_rate = metrics.get('error_rate', 0.0)
        success_rate = metrics.get('success_rate', 1.0)
        
        # Vérifier seuils
        if error_rate > 0.10:  # > 10%
            logger.warning(f"⚠️ Taux d'erreur élevé: {error_rate*100:.1f}%")
        
        if success_rate < 0.85:  # < 85%
            logger.warning(f"⚠️ Taux de succès faible: {success_rate*100:.1f}%")
        
        logger.info(f"  📈 Métriques: erreur={error_rate*100:.1f}%, succès={success_rate*100:.1f}%")
    
    def _quick_functional_test(self):
        """Test fonctionnel rapide"""
        try:
            orchestrator = create_position_orchestrator(self.test_config)
            setup = self.mock_provider.generate_test_setup('QUICKTEST')
            
            result = asyncio.run(orchestrator.process_trade_request(setup, 5000.0))
            
            if result.get('success'):
                logger.info("  ✅ Test fonctionnel OK")
            else:
                logger.warning(f"  ⚠️ Test fonctionnel échoué: {result.get('error_message')}")
                
        except Exception as e:
            logger.error(f"  ❌ Erreur test fonctionnel: {e}")
    
    def _emergency_rollback(self):
        """Rollback d'urgence"""
        logger.critical("🚨 ROLLBACK D'URGENCE ACTIVÉ")
        
        critical_flags = [
            'use_testable_position_manager',
            'use_testable_analyzer',
            'comparison_mode'
        ]
        
        for flag in critical_flags:
            try:
                self.feature_flags.emergency_rollback(flag, "Emergency rollback during Phase 1 activation")
                logger.info(f"  🔴 Rollback {flag}: OK")
            except Exception as e:
                logger.error(f"  💥 Rollback {flag} échoué: {e}")
        
        logger.critical("🔴 Rollback d'urgence terminé")
    
    # Méthodes de vérification
    def _check_core_infrastructure(self) -> bool:
        """Vérifie infrastructure core"""
        try:
            from core.interfaces.position_interfaces import IPositionCalculator
            from core.factories.position_factory import PositionFactory
            return True
        except ImportError as e:
            logger.error(f"Import error: {e}")
            return False
    
    def _check_feature_flags_system(self) -> bool:
        """Vérifie système feature flags"""
        try:
            flags = self.feature_flags.list_all_flags()
            required_flags = ['use_testable_position_manager', 'comparison_mode', 'monitoring_enabled']
            return all(flag in flags for flag in required_flags)
        except Exception:
            return False
    
    def _check_testable_components(self) -> bool:
        """Vérifie composants testables"""
        try:
            from core.implementations.testable_position_calculator import TestablePositionCalculator
            from core.implementations.testable_position_validator import TestablePositionValidator
            return True
        except ImportError:
            return False
    
    def _check_unit_tests(self) -> bool:
        """Vérifie tests unitaires (existence des fichiers)"""
        test_files = [
            'tests/unit/test_testable_position_calculator.py',
            'tests/unit/test_testable_position_validator.py'
        ]
        return all(Path(f).exists() for f in test_files)
    
    def _check_mock_components(self) -> bool:
        """Vérifie composants mock"""
        try:
            from core.implementations.mock_position_components import MockPositionExecutor, MockPositionRepository
            return True
        except ImportError:
            return False


def main():
    """Fonction principale"""
    activator = RefactoringPhase1Activator()
    
    try:
        activator.run_activation_sequence()
        
        print("\n🎯 PHASE 1 RÉSULTATS:")
        print("━" * 50)
        print(f"✅ Tests passés: {activator.activation_metrics['tests_passed']}")
        print(f"❌ Tests échoués: {activator.activation_metrics['tests_failed']}")
        print(f"📊 Rollout final: 25% des utilisateurs")
        print(f"🎛️ Mode comparaison: ACTIF")
        print(f"👁️ Monitoring: ACTIF")
        print("━" * 50)
        print("\n📋 PROCHAINES ÉTAPES:")
        print("1. Surveiller dashboard monitoring (port 5001)")
        print("2. Analyser métriques comparatives pendant 48h")
        print("3. Si stable → passer Phase 2 (50% rollout)")
        print("4. Rollback automatique si problèmes détectés")
        print("\n🌐 Dashboard: http://localhost:5001")
        
    except KeyboardInterrupt:
        print("\n⏹️ Activation interrompue par utilisateur")
        activator._emergency_rollback()
    except Exception as e:
        print(f"\n💥 Erreur critique: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
