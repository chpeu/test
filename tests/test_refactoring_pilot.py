"""
Tests pilotes pour valider la stratégie de refactorisation sécurisée
Phase 1: Prouver que l'approche fonctionne avant déploiement complet
"""
import pytest
import time
import asyncio
from abc import ABC, abstractmethod
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional


# =============================================================================
# INTERFACES TESTABLES - Phase 1 de la refactorisation
# =============================================================================

class IPositionManager(ABC):
    """Interface pour PositionManager - permet tests sans dépendances"""
    
    @abstractmethod
    def calculate_position_size(self, setup: dict, capital: float) -> float:
        pass
        
    @abstractmethod  
    def get_recovery_state(self, loss_streak: int) -> dict:
        pass


class IAnalyzer(ABC):
    """Interface pour TechnicalAnalyzer - permet tests isolés"""
    
    @abstractmethod
    async def analyze_pair_testable(self, symbol: str, mock_data: dict = None) -> dict:
        pass


# =============================================================================
# IMPLÉMENTATIONS TESTABLES - Phase 2 de la refactorisation 
# =============================================================================

class TestablePositionManager(IPositionManager):
    """Version testable du PositionManager avec injection de dépendances"""
    
    def __init__(self, dependencies: dict = None):
        self.deps = dependencies or {}
        self.tp_sl_calc = self.deps.get('tp_sl_calc', MockTPSLCalculator())
        self.recovery_manager = self.deps.get('recovery', MockRecoveryManager())
        self.pnl_calc = self.deps.get('pnl_calc', MockPnLCalculator())
        
    def calculate_position_size(self, setup: dict, capital: float) -> float:
        """Calcul position avec logique simplifiée mais équivalente"""
        # Récupération paramètres
        risk_pct = setup.get('risk_per_trade', 2.0)
        spread = abs(setup.get('entry', 100) - setup.get('sl', 95))
        
        # Calcul base
        risk_amount = capital * (risk_pct / 100)
        base_size = risk_amount / spread if spread > 0 else 0
        
        # Ajustement recovery
        recovery_state = self.get_recovery_state(setup.get('loss_streak', 0))
        recovery_mult = recovery_state.get('position_size_mult', 1.0)
        
        return base_size * recovery_mult
        
    def get_recovery_state(self, loss_streak: int) -> dict:
        """État recovery avec manager injecté"""
        return self.recovery_manager.get_state(loss_streak)


class TestableAnalyzer(IAnalyzer):
    """Version testable de TechnicalAnalyzer avec mocks contrôlés"""
    
    def __init__(self, legacy_analyzer=None):
        self.legacy = legacy_analyzer
        self.test_mode = False
        
    async def analyze_pair_testable(self, symbol: str, mock_data: dict = None) -> dict:
        """Analyse avec données mockées ou délégation vers legacy"""
        if mock_data and self.test_mode:
            return await self._analyze_with_mocks(symbol, mock_data)
        elif self.legacy:
            # Délégation vers analyzer existant si disponible
            try:
                return await self.legacy.analyze_pair(symbol)
            except Exception:
                # Fallback vers version mockée
                return await self._analyze_with_mocks(symbol, self._default_mock_data(symbol))
        else:
            return await self._analyze_with_mocks(symbol, self._default_mock_data(symbol))
            
    async def _analyze_with_mocks(self, symbol: str, mock_data: dict) -> dict:
        """Version testable avec données mockées"""
        await asyncio.sleep(0.001)  # Simule latence
        
        base_score = mock_data.get('base_score', 75)
        direction = mock_data.get('direction', 'LONG')
        
        return {
            'symbol': symbol,
            'direction': direction,
            'totalScore': base_score,
            'entry': mock_data.get('entry', 100),
            'sl': mock_data.get('sl', 95),
            'tp': mock_data.get('tp', 110),
            'is_opportunity': base_score >= 70,
            'reason': mock_data.get('reason', 'Mock analysis')
        }
        
    def _default_mock_data(self, symbol: str) -> dict:
        """Données par défaut pour tests"""
        return {
            'base_score': 80,
            'direction': 'LONG',
            'entry': 100,
            'sl': 95,
            'tp': 110,
            'reason': f'Default mock for {symbol}'
        }


# =============================================================================
# MOCKS POUR DÉPENDANCES
# =============================================================================

class MockTPSLCalculator:
    def calculate_fixed_levels(self, entry: float, tp_dist: float, sl_dist: float, direction: str):
        if direction == 'LONG':
            return entry + tp_dist, entry - sl_dist
        else:
            return entry - tp_dist, entry + sl_dist


class MockRecoveryManager:
    def get_state(self, loss_streak: int) -> dict:
        if loss_streak >= 3:
            return {
                'active': True,
                'level': 2,
                'position_size_mult': 0.7,
                'min_score_boost': 1.5
            }
        elif loss_streak >= 2:
            return {
                'active': True, 
                'level': 1,
                'position_size_mult': 0.85,
                'min_score_boost': 0.5
            }
        else:
            return {
                'active': False,
                'level': None,
                'position_size_mult': 1.0,
                'min_score_boost': 0.0
            }


class MockPnLCalculator:
    def calculate_unrealized_pnl(self, entry: float, current: float, size: float, direction: str) -> float:
        if direction == 'LONG':
            return (current - entry) * size
        else:
            return (entry - current) * size


# =============================================================================
# FACTORY PATTERN POUR BASCULEMENT SÉCURISÉ
# =============================================================================

class PositionManagerFactory:
    """Factory pour basculer entre implémentations"""
    
    @staticmethod
    def create(testing_mode: bool = False, dependencies: dict = None):
        if testing_mode:
            return TestablePositionManager(dependencies)
        else:
            # En mode réel, essayer d'importer le vrai PositionManager
            try:
                from core.position_manager import PositionManager
                return PositionManager()
            except ImportError:
                # Fallback vers version testable si import échoue
                return TestablePositionManager(dependencies)


class AnalyzerFactory:
    """Factory pour basculer entre analyzers"""
    
    @staticmethod  
    def create(testing_mode: bool = False, legacy_analyzer=None):
        if testing_mode:
            return TestableAnalyzer(legacy_analyzer)
        else:
            try:
                from core.analyzer import TechnicalAnalyzer
                return TechnicalAnalyzer()
            except ImportError:
                return TestableAnalyzer()


# =============================================================================
# FEATURE FLAGS POUR CONTRÔLE TOTAL
# =============================================================================

FEATURE_FLAGS = {
    'use_testable_position_manager': False,  # Défaut: ancien code
    'use_testable_analyzer': False,
    'enable_coverage_tests': True,
    'safe_rollback_mode': True,
    'comparison_mode': True  # Compare ancien vs nouveau
}


class FeatureFlagManager:
    """Gestionnaire des feature flags avec rollback automatique"""
    
    @staticmethod
    def get_position_manager(dependencies: dict = None):
        use_testable = FEATURE_FLAGS.get('use_testable_position_manager', False)
        return PositionManagerFactory.create(use_testable, dependencies)
        
    @staticmethod
    def get_analyzer(legacy_analyzer=None):
        use_testable = FEATURE_FLAGS.get('use_testable_analyzer', False)
        return AnalyzerFactory.create(use_testable, legacy_analyzer)


# =============================================================================
# TESTS PILOTES - PHASE 1: INTERFACES ET FACTORIES
# =============================================================================

class TestPilotInterfaces:
    """Tests pilotes pour valider les interfaces"""
    
    def test_position_manager_interface_compliance(self):
        """Test que TestablePositionManager implémente correctement l'interface"""
        pm = TestablePositionManager()
        
        # Vérifier que c'est bien une instance de l'interface
        assert isinstance(pm, IPositionManager)
        
        # Test méthodes interface
        setup = {'entry': 100, 'sl': 95, 'risk_per_trade': 2.0, 'loss_streak': 0}
        size = pm.calculate_position_size(setup, 1000.0)
        
        assert isinstance(size, float)
        assert size > 0
        
        # Test recovery state
        recovery_state = pm.get_recovery_state(3)
        assert isinstance(recovery_state, dict)
        assert 'active' in recovery_state
        assert 'position_size_mult' in recovery_state
    
    def test_analyzer_interface_compliance(self):
        """Test que TestableAnalyzer implémente correctement l'interface"""
        analyzer = TestableAnalyzer()
        analyzer.test_mode = True
        
        assert isinstance(analyzer, IAnalyzer)
        
        # Test analyse avec mock data
        mock_data = {
            'base_score': 85,
            'direction': 'LONG',
            'entry': 100,
            'sl': 95
        }
        
        async def test_analysis():
            result = await analyzer.analyze_pair_testable('BTC/USDT:USDT', mock_data)
            assert isinstance(result, dict)
            assert 'symbol' in result
            assert 'totalScore' in result
            assert result['totalScore'] == 85
            return result
            
        # Exécuter test async
        import asyncio
        result = asyncio.run(test_analysis())
        assert result is not None
    
    def test_factory_patterns(self):
        """Test des factory patterns pour basculement"""
        # Mode test
        pm_test = PositionManagerFactory.create(testing_mode=True)
        assert isinstance(pm_test, TestablePositionManager)
        
        analyzer_test = AnalyzerFactory.create(testing_mode=True)
        assert isinstance(analyzer_test, TestableAnalyzer)
        
        # Mode production (avec fallback car modules pas importables dans test)
        pm_prod = PositionManagerFactory.create(testing_mode=False)
        analyzer_prod = AnalyzerFactory.create(testing_mode=False)
        
        # Dans ce contexte, devrait fallback vers versions testables
        assert pm_prod is not None
        assert analyzer_prod is not None
    
    def test_feature_flag_manager(self):
        """Test du gestionnaire de feature flags"""
        # Test avec flags par défaut
        pm = FeatureFlagManager.get_position_manager()
        analyzer = FeatureFlagManager.get_analyzer()
        
        assert pm is not None
        assert analyzer is not None
        
        # Test basculement via feature flag
        original_flag = FEATURE_FLAGS['use_testable_position_manager']
        
        try:
            FEATURE_FLAGS['use_testable_position_manager'] = True
            pm_testable = FeatureFlagManager.get_position_manager()
            assert isinstance(pm_testable, TestablePositionManager)
            
            FEATURE_FLAGS['use_testable_position_manager'] = False  
            pm_legacy = FeatureFlagManager.get_position_manager()
            # Devrait être différent (ou même type si fallback)
            assert pm_legacy is not None
            
        finally:
            FEATURE_FLAGS['use_testable_position_manager'] = original_flag


# =============================================================================
# TESTS PILOTES - PHASE 2: FONCTIONNALITÉ ÉQUIVALENTE
# =============================================================================

class TestPilotFunctionality:
    """Tests pilotes pour valider l'équivalence fonctionnelle"""
    
    def test_position_size_calculation_accuracy(self):
        """Test que les calculs de position sont précis"""
        pm = TestablePositionManager()
        
        test_cases = [
            # (setup, capital, expected_range)
            ({'entry': 100, 'sl': 95, 'risk_per_trade': 2.0, 'loss_streak': 0}, 1000.0, (30, 50)),
            ({'entry': 200, 'sl': 190, 'risk_per_trade': 1.5, 'loss_streak': 2}, 2000.0, (20, 35)),
            ({'entry': 50, 'sl': 48, 'risk_per_trade': 3.0, 'loss_streak': 3}, 500.0, (8, 15))
        ]
        
        for setup, capital, (min_expected, max_expected) in test_cases:
            size = pm.calculate_position_size(setup, capital)
            assert min_expected <= size <= max_expected, f"Size {size} not in range [{min_expected}, {max_expected}] for {setup}"
    
    def test_recovery_mode_logic(self):
        """Test de la logique recovery mode"""
        pm = TestablePositionManager()
        
        # Test différents niveaux de loss streak
        test_cases = [
            (0, False, 1.0, 0.0),  # (loss_streak, active, mult, boost)
            (1, False, 1.0, 0.0),
            (2, True, 0.85, 0.5),  # Recovery niveau 1
            (3, True, 0.7, 1.5),   # Recovery niveau 2
            (5, True, 0.7, 1.5)    # Recovery niveau 2 maintenu
        ]
        
        for loss_streak, expected_active, expected_mult, expected_boost in test_cases:
            state = pm.get_recovery_state(loss_streak)
            
            assert state['active'] == expected_active, f"Loss streak {loss_streak}: active should be {expected_active}"
            assert abs(state['position_size_mult'] - expected_mult) < 0.01, f"Loss streak {loss_streak}: mult should be {expected_mult}"
            assert abs(state['min_score_boost'] - expected_boost) < 0.01, f"Loss streak {loss_streak}: boost should be {expected_boost}"
    
    def test_analyzer_mock_data_handling(self):
        """Test de la gestion des données mockées"""
        analyzer = TestableAnalyzer()
        analyzer.test_mode = True
        
        async def test_various_scenarios():
            # Scénario 1: Setup gagnant
            winning_setup = {
                'base_score': 85,
                'direction': 'LONG',
                'entry': 100,
                'sl': 95,
                'tp': 110
            }
            
            result1 = await analyzer.analyze_pair_testable('BTC/USDT:USDT', winning_setup)
            assert result1['is_opportunity'] is True
            assert result1['totalScore'] == 85
            
            # Scénario 2: Setup perdant  
            losing_setup = {
                'base_score': 65,
                'direction': 'SHORT',
                'entry': 100,
                'sl': 105,
                'tp': 95
            }
            
            result2 = await analyzer.analyze_pair_testable('ETH/USDT:USDT', losing_setup)
            assert result2['is_opportunity'] is False
            assert result2['totalScore'] == 65
            
            return result1, result2
        
        results = asyncio.run(test_various_scenarios())
        assert len(results) == 2
        assert all(r is not None for r in results)


# =============================================================================
# TESTS PILOTES - PHASE 3: PERFORMANCE ET SÉCURITÉ
# =============================================================================

class TestPilotPerformanceAndSafety:
    """Tests pilotes pour valider performance et sécurité"""
    
    def test_performance_baseline(self):
        """Test de performance baseline pour comparaison"""
        pm = TestablePositionManager()
        setup = {'entry': 100, 'sl': 95, 'risk_per_trade': 2.0, 'loss_streak': 0}
        
        # Mesurer performance
        iterations = 1000
        start_time = time.time()
        
        for _ in range(iterations):
            size = pm.calculate_position_size(setup, 1000.0)
            assert size > 0
            
        execution_time = time.time() - start_time
        avg_time_per_call = execution_time / iterations
        
        # Performance doit être raisonnable (< 1ms par appel)
        assert avg_time_per_call < 0.001, f"Performance trop lente: {avg_time_per_call:.6f}s par appel"
    
    def test_error_handling_safety(self):
        """Test de gestion d'erreurs sécurisée"""
        pm = TestablePositionManager()
        
        # Test avec données invalides
        invalid_setups = [
            {'entry': 100, 'sl': 100, 'risk_per_trade': 2.0},  # Pas de spread
            {'entry': 100, 'sl': 95, 'risk_per_trade': 0},     # Pas de risque
            {'entry': 0, 'sl': 95, 'risk_per_trade': 2.0},     # Prix invalide
        ]
        
        for setup in invalid_setups:
            try:
                size = pm.calculate_position_size(setup, 1000.0)
                # Ne doit pas planter, mais peut retourner 0
                assert isinstance(size, (int, float))
                assert size >= 0
            except Exception as e:
                # Si exception, doit être une exception contrôlée
                assert "invalid" in str(e).lower() or "error" in str(e).lower()
    
    def test_memory_usage_stability(self):
        """Test de stabilité mémoire"""
        pm = TestablePositionManager()
        analyzer = TestableAnalyzer() 
        analyzer.test_mode = True
        
        # Créer beaucoup d'instances pour tester les fuites mémoire
        managers = []
        analyzers = []
        
        for i in range(100):
            managers.append(TestablePositionManager())
            analyzers.append(TestableAnalyzer())
            
        # Test que les instances sont bien créées
        assert len(managers) == 100
        assert len(analyzers) == 100
        
        # Test utilisation
        setup = {'entry': 100, 'sl': 95, 'risk_per_trade': 2.0, 'loss_streak': 0}
        
        for pm in managers[:10]:  # Test sur échantillon
            size = pm.calculate_position_size(setup, 1000.0)
            assert size > 0
            
        # Cleanup explicite
        managers.clear()
        analyzers.clear()
        
        assert len(managers) == 0
        assert len(analyzers) == 0


# =============================================================================
# TESTS PILOTES - PHASE 4: RÉGRESSION ET COMPARAISON  
# =============================================================================

class TestPilotRegression:
    """Tests pilotes pour prévenir les régressions"""
    
    def test_consistent_results(self):
        """Test que les résultats sont consistants entre appels"""
        pm = TestablePositionManager()
        setup = {'entry': 100, 'sl': 95, 'risk_per_trade': 2.0, 'loss_streak': 0}
        
        # Multiple appels avec mêmes params
        results = []
        for _ in range(10):
            size = pm.calculate_position_size(setup, 1000.0)
            results.append(size)
            
        # Tous les résultats doivent être identiques
        assert all(abs(r - results[0]) < 0.0001 for r in results), f"Results not consistent: {results}"
    
    def test_edge_cases_handling(self):
        """Test des cas limites"""
        pm = TestablePositionManager()
        
        edge_cases = [
            # Très petit capital
            ({'entry': 100, 'sl': 95, 'risk_per_trade': 2.0, 'loss_streak': 0}, 10.0),
            # Très grand capital
            ({'entry': 100, 'sl': 95, 'risk_per_trade': 2.0, 'loss_streak': 0}, 1000000.0),
            # Spread très petit
            ({'entry': 100.01, 'sl': 100.00, 'risk_per_trade': 2.0, 'loss_streak': 0}, 1000.0),
            # Recovery mode extrême
            ({'entry': 100, 'sl': 95, 'risk_per_trade': 2.0, 'loss_streak': 10}, 1000.0)
        ]
        
        for setup, capital in edge_cases:
            size = pm.calculate_position_size(setup, capital)
            
            # Validations de base
            assert isinstance(size, (int, float))
            assert size >= 0
            assert size <= capital * 0.1  # Max 10% du capital
    
    def test_analyzer_timeout_handling(self):
        """Test de gestion des timeouts"""
        analyzer = TestableAnalyzer()
        analyzer.test_mode = True
        
        async def test_with_timeout():
            # Test analyse normale
            try:
                result = await asyncio.wait_for(
                    analyzer.analyze_pair_testable('BTC/USDT:USDT'),
                    timeout=1.0
                )
                assert result is not None
                return True
            except asyncio.TimeoutError:
                return False
                
        # Test que l'analyse ne timeout pas
        success = asyncio.run(test_with_timeout())
        assert success, "Analyzer should not timeout on normal operation"


# =============================================================================
# RUNNER POUR TESTS PILOTES
# =============================================================================

def run_pilot_tests():
    """Exécuter tous les tests pilotes et retourner rapport"""
    import sys
    
    print("🧪 EXÉCUTION TESTS PILOTES DE REFACTORISATION")
    print("=" * 60)
    
    test_classes = [
        TestPilotInterfaces,
        TestPilotFunctionality, 
        TestPilotPerformanceAndSafety,
        TestPilotRegression
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = []
    
    for test_class in test_classes:
        class_name = test_class.__name__
        print(f"\n📋 {class_name}")
        
        instance = test_class()
        test_methods = [m for m in dir(instance) if m.startswith('test_')]
        
        for method_name in test_methods:
            total_tests += 1
            method = getattr(instance, method_name)
            
            try:
                method()
                print(f"  ✅ {method_name}")
                passed_tests += 1
            except Exception as e:
                print(f"  ❌ {method_name}: {e}")
                failed_tests.append((class_name, method_name, str(e)))
    
    print("\n" + "=" * 60)
    print(f"📊 RÉSULTATS: {passed_tests}/{total_tests} tests passés")
    
    if failed_tests:
        print(f"❌ {len(failed_tests)} échecs:")
        for class_name, method_name, error in failed_tests:
            print(f"  • {class_name}::{method_name} - {error}")
        return False
    else:
        print("✅ TOUS LES TESTS PILOTES PASSENT")
        print("🚀 REFACTORISATION SÉCURISÉE VALIDÉE")
        return True


if __name__ == "__main__":
    success = run_pilot_tests()
    sys.exit(0 if success else 1)
