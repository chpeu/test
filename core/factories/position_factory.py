"""
PositionFactory et AnalyzerFactory - Trade Cursor v7.0
Factory patterns pour injection de dépendances et basculement feature flags
"""

import logging
from typing import Dict, Any, Optional, Type
from core.feature_flags import get_feature_flags_manager
from core.interfaces.position_interfaces import (
    IPositionCalculator, IPositionValidator, IPositionExecutor, 
    IPositionRepository, IPositionOrchestrator
)
from core.interfaces.analyzer_interfaces import (
    IAnalyzer, IIndicatorCalculator, ISignalGenerator, ISignalValidator,
    IScoreCalculator, IAnalysisOrchestrator, AnalyzerConfig
)
from core.interfaces.position_interfaces import PositionConfig
from core.interfaces.scanner_interfaces import (
    IScannerOrchestrator, IMarketDataCollector, IScalabilityScorer, IPairFilter,
    IScanPipeline, FilterConfig, ScannerConfig
)
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FactoryConfig:
    """Configuration pour la factory"""
    environment: str = "development"
    use_mocks: bool = False
    database_url: str = ""
    api_config: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.api_config is None:
            self.api_config = {}


class PositionFactory:
    """
    Factory principale pour créer composants Position Manager
    
    Gère:
    - Basculement legacy/nouveau via feature flags
    - Injection des dépendances
    - Configuration environnement
    - Mocking pour tests
    """
    
    def __init__(self, config: FactoryConfig = None):
        self.config = config or FactoryConfig()
        self.feature_flags = get_feature_flags_manager()
        self._calculator_cache = {}
        self._validator_cache = {}
        
        logger.info(f"✅ PositionFactory initialisée (env: {self.config.environment})")
    
    def create_position_calculator(self, position_config: PositionConfig = None) -> IPositionCalculator:
        """
        Créer calculateur de positions
        
        Returns:
            IPositionCalculator: Implémentation selon feature flags
        """
        try:
            # Cache key
            cache_key = f"calc_{hash(str(position_config))}"
            if cache_key in self._calculator_cache:
                return self._calculator_cache[cache_key]
            
            # Vérifier feature flag
            if self.feature_flags.is_enabled('use_testable_position_manager'):
                calculator = self._create_testable_calculator(position_config)
                logger.info("🆕 Using TestablePositionCalculator")
            else:
                calculator = self._create_legacy_calculator(position_config)
                logger.info("📡 Using LegacyPositionCalculator")
            
            # Cache
            self._calculator_cache[cache_key] = calculator
            
            return calculator
            
        except Exception as e:
            logger.error(f"Failed to create position calculator: {e}")
            # Fallback to legacy
            return self._create_legacy_calculator(position_config)
    
    def create_position_validator(self, validation_config: Dict[str, Any] = None) -> IPositionValidator:
        """
        Créer validateur de positions
        
        Returns:
            IPositionValidator: Implémentation selon feature flags
        """
        try:
            # Cache key
            cache_key = f"val_{hash(str(validation_config))}"
            if cache_key in self._validator_cache:
                return self._validator_cache[cache_key]
            
            # Vérifier feature flag
            if self.feature_flags.is_enabled('use_testable_position_manager'):
                validator = self._create_testable_validator(validation_config)
                logger.info("🆕 Using TestablePositionValidator")
            else:
                validator = self._create_legacy_validator(validation_config)
                logger.info("📡 Using LegacyPositionValidator")
            
            # Cache
            self._validator_cache[cache_key] = validator
            
            return validator
            
        except Exception as e:
            logger.error(f"Failed to create position validator: {e}")
            # Fallback to legacy
            return self._create_legacy_validator(validation_config)
    
    def create_position_executor(self, api_config: Dict[str, Any] = None) -> IPositionExecutor:
        """
        Créer exécuteur de positions
        
        Returns:
            IPositionExecutor: Implémentation selon environment
        """
        try:
            if self.config.use_mocks or self.config.environment == "test":
                return self._create_mock_executor(api_config)
            elif self.feature_flags.is_enabled('use_testable_position_manager'):
                return self._create_testable_executor(api_config)
            else:
                return self._create_legacy_executor(api_config)
                
        except Exception as e:
            logger.error(f"Failed to create position executor: {e}")
            # Fallback to mock for safety
            return self._create_mock_executor(api_config)
    
    def create_position_repository(self, db_config: Dict[str, Any] = None) -> IPositionRepository:
        """
        Créer repository de positions
        
        Returns:
            IPositionRepository: Implémentation selon environment
        """
        try:
            if self.config.use_mocks or self.config.environment == "test":
                return self._create_mock_repository(db_config)
            else:
                return self._create_database_repository(db_config)
                
        except Exception as e:
            logger.error(f"Failed to create position repository: {e}")
            # Fallback to mock for safety
            return self._create_mock_repository(db_config)
    
    def create_position_orchestrator(self, 
                                   calculator: IPositionCalculator = None,
                                   validator: IPositionValidator = None,
                                   executor: IPositionExecutor = None,
                                   repository: IPositionRepository = None) -> IPositionOrchestrator:
        """
        Créer orchestrateur principal avec toutes les dépendances
        
        Returns:
            IPositionOrchestrator: Orchestrateur configuré
        """
        try:
            # Créer composants si non fournis
            if calculator is None:
                calculator = self.create_position_calculator()
            
            if validator is None:
                validator = self.create_position_validator()
            
            if executor is None:
                executor = self.create_position_executor()
            
            if repository is None:
                repository = self.create_position_repository()
            
            # Vérifier feature flag pour orchestrateur
            if self.feature_flags.is_enabled('use_testable_position_manager'):
                orchestrator = self._create_testable_orchestrator(calculator, validator, executor, repository)
                logger.info("🆕 Using TestablePositionOrchestrator")
            else:
                orchestrator = self._create_legacy_orchestrator(calculator, validator, executor, repository)
                logger.info("📡 Using LegacyPositionOrchestrator")
            
            return orchestrator
            
        except Exception as e:
            logger.error(f"Failed to create position orchestrator: {e}")
            # Fallback vers mock pour tests
            from ..implementations.mock_position_components import MockPositionOrchestrator
            return MockPositionOrchestrator(calculator, validator, executor, repository)
    
    def _create_testable_calculator(self, config: PositionConfig) -> IPositionCalculator:
        """Créer calculateur testable"""
        try:
            from ..implementations.testable_position_calculator import TestablePositionCalculator
            return TestablePositionCalculator(config or PositionConfig())
        except ImportError:
            from ..implementations.mock_position_components import MockPositionCalculator
            return MockPositionCalculator(config)
    
    def _create_legacy_calculator(self, config: PositionConfig) -> IPositionCalculator:
        """Créer calculateur legacy wrappé"""
        try:
            from ..implementations.legacy_position_wrapper import LegacyPositionCalculatorWrapper
            return LegacyPositionCalculatorWrapper(config or PositionConfig())
        except ImportError:
            from ..implementations.mock_position_components import MockPositionCalculator
            return MockPositionCalculator(config)
    
    def _create_testable_validator(self, config: Dict[str, Any]) -> IPositionValidator:
        """Créer validateur testable"""
        try:
            from ..implementations.testable_position_validator import TestablePositionValidator
            return TestablePositionValidator(config or {})
        except ImportError:
            from ..implementations.mock_position_components import MockPositionValidator
            return MockPositionValidator(config)
    
    def _create_legacy_validator(self, config: Dict[str, Any]) -> IPositionValidator:
        """Créer validateur legacy wrappé"""
        try:
            from ..implementations.legacy_position_wrapper import LegacyPositionValidatorWrapper
            return LegacyPositionValidatorWrapper(config or {})
        except ImportError:
            from ..implementations.mock_position_components import MockPositionValidator
            return MockPositionValidator(config)
    
    def _create_testable_executor(self, config: Dict[str, Any]) -> IPositionExecutor:
        """Créer exécuteur testable"""
        try:
            from ..implementations.testable_position_executor import TestablePositionExecutor
            return TestablePositionExecutor(config or {})
        except ImportError:
            from ..implementations.mock_position_components import MockPositionExecutor
            return MockPositionExecutor(config or {})
    
    def _create_legacy_executor(self, config: Dict[str, Any]) -> IPositionExecutor:
        """Créer exécuteur legacy wrappé"""
        try:
            from ..implementations.legacy_position_wrapper import LegacyPositionExecutorWrapper
            return LegacyPositionExecutorWrapper(config or {})
        except ImportError:
            from ..implementations.mock_position_components import MockPositionExecutor
            return MockPositionExecutor(config or {})
    
    def _create_testable_orchestrator(self, calculator, validator, executor, repository) -> IPositionOrchestrator:
        """Créer orchestrateur testable"""
        try:
            from ..implementations.testable_position_orchestrator import TestablePositionOrchestrator
            return TestablePositionOrchestrator(calculator, validator, executor, repository)
        except ImportError:
            from ..implementations.mock_position_components import MockPositionOrchestrator
            return MockPositionOrchestrator(calculator, validator, executor, repository)
    
    def get_factory_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de la factory"""
        return {
            'environment': self.config.environment,
            'use_mocks': self.config.use_mocks,
            'cached_components': len(self._calculator_cache) + len(self._validator_cache),
            'component_types': list(self._calculator_cache.keys()) + list(self._validator_cache.keys()),
            'feature_flags_enabled': self.feature_flags.is_enabled('use_testable_position_manager')
        }
    
    def _create_mock_executor(self, config: Dict[str, Any]) -> IPositionExecutor:
        """Créer mock exécuteur pour tests"""
        from ..implementations.mock_position_components import MockPositionExecutor
        return MockPositionExecutor(config or {})
    
    def _create_database_repository(self, config: Dict[str, Any]) -> IPositionRepository:
        """Créer repository base de données"""
        try:
            from ..implementations.database_position_repository import DatabasePositionRepository
            return DatabasePositionRepository(config or {})
        except ImportError:
            from ..implementations.mock_position_components import MockPositionRepository
            return MockPositionRepository(config or {})
    
    def _create_mock_repository(self, config: Dict[str, Any]) -> IPositionRepository:
        """Créer mock repository pour tests"""
        from ..implementations.mock_position_components import MockPositionRepository
        return MockPositionRepository(config or {})
        return MockPositionRepository(config or {})


class AnalyzerFactory:
    """
    Factory pour créer composants Analyzer refactorisé
    
    Gère:
    - Basculement legacy/testable via feature flags
    - Injection dépendances analyzer
    - Configuration composants découplés
    - Mocking pour tests
    """
    
    def __init__(self, config: FactoryConfig = None):
        self.config = config or FactoryConfig()
        self.feature_flags = get_feature_flags_manager()
        self._component_cache = {}
        
        logger.info(f"✅ AnalyzerFactory initialisée (env: {self.config.environment})")
    
    def create_analyzer(self, analyzer_config: AnalyzerConfig = None) -> IAnalyzer:
        """
        Créer analyzer principal
        
        Returns:
            IAnalyzer: Implémentation selon feature flags
        """
        try:
            cache_key = f"analyzer_{hash(str(analyzer_config))}"
            if cache_key in self._component_cache:
                return self._component_cache[cache_key]
            
            if self.feature_flags.is_enabled('use_testable_analyzer'):
                analyzer = self._create_testable_analyzer(analyzer_config)
                logger.info("🆕 Using TestableAnalyzer")
            else:
                analyzer = self._create_legacy_analyzer(analyzer_config)
                logger.info("📡 Using LegacyAnalyzer")
            
            self._component_cache[cache_key] = analyzer
            return analyzer
            
        except Exception as e:
            logger.error(f"Failed to create analyzer: {e}")
            return self._create_legacy_analyzer(analyzer_config)
    
    def create_indicator_calculator(self) -> IIndicatorCalculator:
        """
        Créer calculateur d'indicateurs techniques
        
        Returns:
            IIndicatorCalculator: Calculateur découplé
        """
        try:
            cache_key = "indicator_calculator"
            if cache_key in self._component_cache:
                return self._component_cache[cache_key]
            
            calculator = self._create_testable_indicator_calculator()
            self._component_cache[cache_key] = calculator
            
            logger.info("🆕 Using TestableIndicatorCalculator")
            return calculator
            
        except Exception as e:
            logger.error(f"Failed to create indicator calculator: {e}")
            return self._create_testable_indicator_calculator()
    
    def create_signal_generator(self, analyzer_config: AnalyzerConfig = None) -> ISignalGenerator:
        """
        Créer générateur de signaux
        
        Returns:
            ISignalGenerator: Générateur découplé
        """
        try:
            cache_key = f"signal_generator_{hash(str(analyzer_config))}"
            if cache_key in self._component_cache:
                return self._component_cache[cache_key]
            
            config = analyzer_config or AnalyzerConfig()
            generator = self._create_testable_signal_generator(config)
            self._component_cache[cache_key] = generator
            
            logger.info("🆕 Using TestableSignalGenerator")
            return generator
            
        except Exception as e:
            logger.error(f"Failed to create signal generator: {e}")
            return self._create_testable_signal_generator(analyzer_config or AnalyzerConfig())
    
    def create_signal_validator(self, analyzer_config: AnalyzerConfig = None) -> ISignalValidator:
        """
        Créer validateur de signaux
        
        Returns:
            ISignalValidator: Validateur découplé
        """
        try:
            cache_key = f"signal_validator_{hash(str(analyzer_config))}"
            if cache_key in self._component_cache:
                return self._component_cache[cache_key]
            
            config = analyzer_config or AnalyzerConfig()
            validator = self._create_testable_signal_validator(config)
            self._component_cache[cache_key] = validator
            
            logger.info("🆕 Using TestableSignalValidator")
            return validator
            
        except Exception as e:
            logger.error(f"Failed to create signal validator: {e}")
            return self._create_testable_signal_validator(analyzer_config or AnalyzerConfig())
    
    def create_score_calculator(self, analyzer_config: AnalyzerConfig = None) -> IScoreCalculator:
        """
        Créer calculateur de scores
        
        Returns:
            IScoreCalculator: Calculateur découplé
        """
        try:
            cache_key = f"score_calculator_{hash(str(analyzer_config))}"
            if cache_key in self._component_cache:
                return self._component_cache[cache_key]
            
            config = analyzer_config or AnalyzerConfig()
            calculator = self._create_testable_score_calculator(config)
            self._component_cache[cache_key] = calculator
            
            logger.info("🆕 Using TestableScoreCalculator")
            return calculator
            
        except Exception as e:
            logger.error(f"Failed to create score calculator: {e}")
            return self._create_testable_score_calculator(analyzer_config or AnalyzerConfig())
    
    def create_analysis_orchestrator(self, 
                                   analyzer: IAnalyzer = None,
                                   validator: ISignalValidator = None) -> IAnalysisOrchestrator:
        """
        Créer orchestrateur d'analyse avec toutes les dépendances
        
        Returns:
            IAnalysisOrchestrator: Orchestrateur configuré
        """
        try:
            # Créer composants si non fournis
            if analyzer is None:
                analyzer = self.create_analyzer()
            
            if validator is None:
                validator = self.create_signal_validator()
            
            orchestrator = self._create_testable_analysis_orchestrator(analyzer, validator)
            
            logger.info("🆕 Using TestableAnalysisOrchestrator")
            return orchestrator
            
        except Exception as e:
            logger.error(f"Failed to create analysis orchestrator: {e}")
            raise
    
    def create_full_analyzer_stack(self, analyzer_config: AnalyzerConfig = None) -> Dict[str, Any]:
        """
        Créer stack complet analyzer avec tous composants
        
        Returns:
            Dict contenant tous les composants
        """
        try:
            config = analyzer_config or AnalyzerConfig()
            
            stack = {
                'indicator_calculator': self.create_indicator_calculator(),
                'signal_generator': self.create_signal_generator(config),
                'signal_validator': self.create_signal_validator(config),
                'score_calculator': self.create_score_calculator(config)
            }
            
            # Créer analyzer avec composants
            stack['analyzer'] = self._create_testable_analyzer_with_components(
                config, 
                stack['indicator_calculator'],
                stack['signal_generator'],
                stack['score_calculator']
            )
            
            # Créer orchestrateur
            stack['orchestrator'] = self.create_analysis_orchestrator(
                stack['analyzer'],
                stack['signal_validator']
            )
            
            logger.info("🆕 Created full analyzer stack with all components")
            return stack
            
        except Exception as e:
            logger.error(f"Failed to create full analyzer stack: {e}")
            raise
    
    def _create_testable_analyzer(self, config: AnalyzerConfig) -> IAnalyzer:
        """Créer analyzer testable avec wrapper legacy"""
        from ..implementations.testable_analyzer import TestableAnalyzer
        return TestableAnalyzer(config or AnalyzerConfig())
    
    def _create_legacy_analyzer(self, config: AnalyzerConfig) -> IAnalyzer:
        """Créer analyzer legacy wrappé"""
        from ..implementations.legacy_analyzer_wrapper import LegacyAnalyzerWrapper
        return LegacyAnalyzerWrapper(config or AnalyzerConfig())
    
    def _create_testable_indicator_calculator(self) -> IIndicatorCalculator:
        """Créer calculateur indicateurs testable"""
        from ..implementations.testable_indicator_calculator import TestableIndicatorCalculator
        return TestableIndicatorCalculator()
    
    def _create_testable_signal_generator(self, config: AnalyzerConfig) -> ISignalGenerator:
        """Créer générateur signaux testable"""
        from ..implementations.testable_signal_generator import TestableSignalGenerator
        return TestableSignalGenerator(config)
    
    def _create_testable_signal_validator(self, config: AnalyzerConfig) -> ISignalValidator:
        """Créer validateur signaux testable"""
        from ..implementations.testable_signal_validator import TestableSignalValidator
        return TestableSignalValidator(config)
    
    def _create_testable_score_calculator(self, config: AnalyzerConfig) -> IScoreCalculator:
        """Créer calculateur scores testable"""
        from ..implementations.testable_score_calculator import TestableScoreCalculator
        return TestableScoreCalculator(config)
    
    def _create_testable_analysis_orchestrator(self, analyzer: IAnalyzer, validator: ISignalValidator) -> IAnalysisOrchestrator:
        """Créer orchestrateur d'analyse testable"""
        from ..implementations.testable_analysis_orchestrator import TestableAnalysisOrchestrator
        return TestableAnalysisOrchestrator(analyzer, validator)
    
    def _create_testable_analyzer(self, config: AnalyzerConfig) -> IAnalyzer:
        """Créer analyzer testable avec wrapper legacy"""
        try:
            from ..implementations.testable_analyzer import TestableAnalyzer
            return TestableAnalyzer(config or AnalyzerConfig())
        except ImportError:
            # Fallback vers mock analyzer simple
            return type('MockAnalyzer', (), {
                'analyze_pair': lambda self, symbol, data: {'symbol': symbol, 'valid': True}
            })()
    
    def _create_legacy_analyzer(self, config: AnalyzerConfig) -> IAnalyzer:
        """Créer analyzer legacy wrappé"""
        try:
            from ..implementations.legacy_analyzer_wrapper import LegacyAnalyzerWrapper
            return LegacyAnalyzerWrapper(config or AnalyzerConfig())
        except ImportError:
            # Fallback vers mock analyzer simple
            return type('MockAnalyzer', (), {
                'analyze_pair': lambda self, symbol, data: {'symbol': symbol, 'valid': True}
            })()
    
    def _create_testable_indicator_calculator(self) -> IIndicatorCalculator:
        """Créer calculateur indicateurs testable"""
        try:
            from ..implementations.testable_indicator_calculator import TestableIndicatorCalculator
            return TestableIndicatorCalculator()
        except ImportError:
            # Fallback vers mock simple
            return type('MockIndicatorCalculator', (), {})()
    
    def _create_testable_analyzer_with_components(self, 
                                                config: AnalyzerConfig,
                                                indicator_calculator: IIndicatorCalculator,
                                                signal_generator: ISignalGenerator,
                                                score_calculator: IScoreCalculator) -> IAnalyzer:
        """Créer analyzer avec injection composants"""
        try:
            from ..implementations.testable_analyzer_v2 import TestableAnalyzerV2
            return TestableAnalyzerV2(config, indicator_calculator, signal_generator, score_calculator)
        except ImportError:
            return self._create_testable_analyzer(config)
    
    def get_factory_stats(self) -> Dict[str, Any]:
        """Retourne statistiques de la factory"""
        return {
            'environment': self.config.environment,
            'use_mocks': self.config.use_mocks,
            'cached_components': len(self._component_cache),
            'component_types': list(self._component_cache.keys())
        }
    
    def clear_cache(self):
        """Vide le cache des composants"""
        self._component_cache.clear()
        logger.info("AnalyzerFactory cache cleared")


# Fonction utilitaire pour obtenir factory configurée
def get_feature_flags_manager():
    """Obtenir gestionnaire feature flags"""
    from core.feature_flags import get_feature_flags_manager as get_ffm
    return get_ffm()


def get_configured_position_factory(environment: str = "development", use_mocks: bool = False) -> PositionFactory:
    """Obtenir PositionFactory configurée"""
    config = FactoryConfig(
        environment=environment,
        use_mocks=use_mocks
    )
    return PositionFactory(config)


def get_configured_analyzer_factory(environment: str = "development", use_mocks: bool = False) -> AnalyzerFactory:
    """Obtenir AnalyzerFactory configurée"""
    config = FactoryConfig(
        environment=environment,
        use_mocks=use_mocks
    )
    return AnalyzerFactory(config)


# ==============================================================================
# SCANNER FACTORY - Phase 3
# ==============================================================================

class ScannerFactory:
    """
    Factory pour créer les composants Scanner Phase 3
    """
    
    def __init__(self, environment: str = "development", use_mocks: bool = False):
        self.environment = environment
        self.use_mocks = use_mocks
        self.feature_flags = get_feature_flags_manager()
        
        # Cache des instances créées
        self._market_data_collector = None
        self._scalability_scorer = None
        self._pair_filter = None
        self._scan_pipeline = None
        self._scanner_orchestrator = None
        
        logger.info(f"ScannerFactory initialisée (env: {environment}, mocks: {use_mocks})")
    
    def create_market_data_collector(self, config: Optional[Dict[str, Any]] = None) -> IMarketDataCollector:
        """Crée un collecteur de données de marché"""
        if self._market_data_collector is not None:
            return self._market_data_collector
        
        try:
            if self.use_mocks:
                from core.implementations.mock_scanner_components import MockMarketDataCollector
                collector = MockMarketDataCollector()
            else:
                from core.implementations.testable_market_data_collector import TestableMarketDataCollector
                from api.mexc_client import get_mexc_client
                
                client = get_mexc_client()
                cache_ttl = config.get('cache_ttl_seconds', 30) if config else 30
                max_cache_size = config.get('max_cache_size', 1000) if config else 1000
                
                collector = TestableMarketDataCollector(
                    client=client,
                    cache_ttl_seconds=cache_ttl,
                    max_cache_size=max_cache_size
                )
            
            self._market_data_collector = collector
            logger.info("✅ MarketDataCollector créé")
            return collector
            
        except Exception as e:
            logger.error(f"❌ Erreur création MarketDataCollector: {e}")
            # Fallback vers mock
            from core.implementations.mock_scanner_components import MockMarketDataCollector
            collector = MockMarketDataCollector()
            self._market_data_collector = collector
            return collector
    
    def create_scalability_scorer(self, config: Optional[Dict[str, Any]] = None) -> IScalabilityScorer:
        """Crée un scorer de scalabilité"""
        if self._scalability_scorer is not None:
            return self._scalability_scorer
        
        try:
            if self.use_mocks:
                from core.implementations.mock_scanner_components import MockScalabilityScorer
                scorer = MockScalabilityScorer()
            else:
                from core.implementations.testable_scalability_scorer import TestableScalabilityScorer
                scorer = TestableScalabilityScorer(config=config or {})
            
            self._scalability_scorer = scorer
            logger.info("✅ ScalabilityScorer créé")
            return scorer
            
        except Exception as e:
            logger.error(f"❌ Erreur création ScalabilityScorer: {e}")
            # Fallback vers mock
            from core.implementations.mock_scanner_components import MockScalabilityScorer
            scorer = MockScalabilityScorer()
            self._scalability_scorer = scorer
            return scorer
    
    def create_pair_filter(self, config: Optional[FilterConfig] = None) -> IPairFilter:
        """Crée un filtreur de paires"""
        if self._pair_filter is not None:
            return self._pair_filter
        
        try:
            if self.use_mocks:
                from core.implementations.mock_scanner_components import MockPairFilter
                filter_instance = MockPairFilter()
            else:
                from core.implementations.testable_pair_filter import TestablePairFilter
                filter_instance = TestablePairFilter(config=config or FilterConfig())
            
            self._pair_filter = filter_instance
            logger.info("✅ PairFilter créé")
            return filter_instance
            
        except Exception as e:
            logger.error(f"❌ Erreur création PairFilter: {e}")
            # Fallback vers mock
            from core.implementations.mock_scanner_components import MockPairFilter
            filter_instance = MockPairFilter()
            self._pair_filter = filter_instance
            return filter_instance
    
    def create_scan_pipeline(self, config: Optional[Dict[str, Any]] = None) -> IScanPipeline:
        """Crée un pipeline de scan"""
        if self._scan_pipeline is not None:
            return self._scan_pipeline
        
        try:
            if self.use_mocks:
                from core.implementations.mock_scanner_components import MockScanPipeline
                pipeline = MockScanPipeline()
            else:
                from core.implementations.testable_scan_pipeline import (
                    TestableScanPipeline, DataCollectionStep, ScoringStep, 
                    FilteringStep, AnalysisStep, LoggingStep
                )
                
                # Créer pipeline avec étapes par défaut
                max_parallel = config.get('max_parallel_steps', 1) if config else 1
                enable_circuit_breaker = config.get('enable_circuit_breaker', True) if config else True
                
                pipeline = TestableScanPipeline(
                    max_parallel_steps=max_parallel,
                    enable_circuit_breaker=enable_circuit_breaker
                )
                
                # Ajouter étapes standard
                market_data_collector = self.create_market_data_collector()
                scalability_scorer = self.create_scalability_scorer()
                pair_filter = self.create_pair_filter()
                
                pipeline.add_step(DataCollectionStep(market_data_collector))
                pipeline.add_step(ScoringStep(scalability_scorer))
                pipeline.add_step(FilteringStep(pair_filter))
                
                # Ajouter étape analyse si Analyzer Phase 2 disponible
                if self.feature_flags.is_enabled('use_testable_analyzer'):
                    analyzer_factory = get_configured_analyzer_factory(self.environment, self.use_mocks)
                    analyzer = analyzer_factory.create_analyzer()
                    pipeline.add_step(AnalysisStep(analyzer))
                
                # Ajouter étape logging si disponible
                try:
                    from core.implementations.mock_scanner_components import MockScanLogger
                    scan_logger = MockScanLogger() if self.use_mocks else None
                    if scan_logger:
                        pipeline.add_step(LoggingStep(scan_logger))
                except ImportError:
                    pass  # Skip logging si pas disponible
            
            self._scan_pipeline = pipeline
            logger.info("✅ ScanPipeline créé")
            return pipeline
            
        except Exception as e:
            logger.error(f"❌ Erreur création ScanPipeline: {e}")
            # Fallback vers mock
            from core.implementations.mock_scanner_components import MockScanPipeline
            pipeline = MockScanPipeline()
            self._scan_pipeline = pipeline
            return pipeline
    
    def create_scanner_orchestrator(self, config: Optional[ScannerConfig] = None) -> IScannerOrchestrator:
        """Crée un orchestrateur de scanner"""
        if self._scanner_orchestrator is not None:
            return self._scanner_orchestrator
        
        try:
            if self.use_mocks:
                from core.implementations.mock_scanner_components import MockScannerOrchestrator
                orchestrator = MockScannerOrchestrator()
            else:
                from core.implementations.testable_scanner_orchestrator import TestableScannerOrchestrator
                
                # Créer pipeline
                scan_pipeline = self.create_scan_pipeline()
                
                orchestrator = TestableScannerOrchestrator(
                    scan_pipeline=scan_pipeline,
                    config=config or ScannerConfig()
                )
            
            self._scanner_orchestrator = orchestrator
            logger.info("✅ ScannerOrchestrator créé")
            return orchestrator
            
        except Exception as e:
            logger.error(f"❌ Erreur création ScannerOrchestrator: {e}")
            # Fallback vers mock
            from core.implementations.mock_scanner_components import MockScannerOrchestrator
            orchestrator = MockScannerOrchestrator()
            self._scanner_orchestrator = orchestrator
            return orchestrator
    
    def create_full_scanner_stack(self, scanner_config: Optional[ScannerConfig] = None, 
                                 filter_config: Optional[FilterConfig] = None) -> Dict[str, Any]:
        """Crée un stack complet de scanner avec tous les composants"""
        try:
            logger.info("Création du stack Scanner Phase 3 complet")
            
            stack = {
                'market_data_collector': self.create_market_data_collector(),
                'scalability_scorer': self.create_scalability_scorer(),
                'pair_filter': self.create_pair_filter(filter_config),
                'scan_pipeline': self.create_scan_pipeline(),
                'scanner_orchestrator': self.create_scanner_orchestrator(scanner_config)
            }
            
            logger.info("✅ Stack Scanner Phase 3 complet créé")
            return stack
            
        except Exception as e:
            logger.error(f"❌ Erreur création stack Scanner: {e}")
            return {}
    
    def get_factory_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de la factory"""
        cached_components = 0
        if self._market_data_collector: cached_components += 1
        if self._scalability_scorer: cached_components += 1
        if self._pair_filter: cached_components += 1
        if self._scan_pipeline: cached_components += 1
        if self._scanner_orchestrator: cached_components += 1
        
        return {
            'environment': self.environment,
            'use_mocks': self.use_mocks,
            'cached_components': cached_components,
            'feature_flags_enabled': self.feature_flags.is_enabled('use_testable_scanner'),
            'components': {
                'market_data_collector': self._market_data_collector is not None,
                'scalability_scorer': self._scalability_scorer is not None,
                'pair_filter': self._pair_filter is not None,
                'scan_pipeline': self._scan_pipeline is not None,
                'scanner_orchestrator': self._scanner_orchestrator is not None
            }
        }
    
    def clear_cache(self):
        """Vide le cache des composants"""
        self._market_data_collector = None
        self._scalability_scorer = None
        self._pair_filter = None
        self._scan_pipeline = None
        self._scanner_orchestrator = None
        logger.info("Cache Scanner Factory vidé")


def get_configured_scanner_factory(environment: str = "development", use_mocks: bool = False) -> ScannerFactory:
    """
    Utilitaire pour obtenir une factory Scanner configurée
    """
    return ScannerFactory(environment, use_mocks)

def _create_testable_orchestrator(self, calculator, validator, executor, repository) -> IPositionOrchestrator:
    """Créer orchestrateur testable"""
    try:
        from ..implementations.testable_position_orchestrator import TestablePositionOrchestrator
        return TestablePositionOrchestrator(calculator, validator, executor, repository)
    except ImportError:
        # Fallback vers mock pour tests
        from ..implementations.mock_position_components import MockPositionOrchestrator
        return MockPositionOrchestrator(calculator, validator, executor, repository)

def get_factory_stats(self) -> Dict[str, Any]:
    """Retourne les statistiques de la factory"""
    return {
        'environment': self.config.environment,
        'use_mocks': self.config.use_mocks,
        'cached_components': len(self._calculator_cache) + len(self._validator_cache),
        'component_types': list(self._calculator_cache.keys()) + list(self._validator_cache.keys()),
        'feature_flags_enabled': self.feature_flags.is_enabled('use_testable_position_manager')
    }


# Factory globale pour facilité d'utilisation
_position_factory = None

def get_position_factory(config: FactoryConfig = None) -> PositionFactory:
    """Obtenir instance globale de la factory"""
    global _position_factory
    if _position_factory is None or config is not None:
        _position_factory = PositionFactory(config)
    return _position_factory


def create_position_orchestrator(custom_config: FactoryConfig = None) -> IPositionOrchestrator:
    """Helper pour créer orchestrateur complet rapidement"""
    factory = get_position_factory(custom_config)
    return factory.create_position_orchestrator()


# Code nettoyé - AnalyzerFactory est définie plus haut dans le fichier
