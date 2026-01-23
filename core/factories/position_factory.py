"""
PositionFactory et AnalyzerFactory - Trade Cursor v7.0
Factory patterns pour injection de dépendances et basculement feature flags
"""

import logging
from typing import Dict, Any, Optional, Type
from core.feature_flags import get_effective_value
from core.interfaces.position_interfaces import (
    IPositionCalculator, IPositionValidator, IPositionExecutor, 
    IPositionRepository, IPositionOrchestrator
)
from core.interfaces.analyzer_interfaces import (
    IAnalyzer, IIndicatorCalculator, ISignalGenerator, ISignalValidator,
    IScoreCalculator, IAnalysisOrchestrator, AnalyzerConfig
)
from core.interfaces.position_interfaces import PositionConfig
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
            raise
    
    def _create_testable_calculator(self, config: PositionConfig) -> IPositionCalculator:
        """Créer calculateur testable"""
        from ..implementations.testable_position_calculator import TestablePositionCalculator
        return TestablePositionCalculator(config or PositionConfig())
    
    def _create_legacy_calculator(self, config: PositionConfig) -> IPositionCalculator:
        """Créer calculateur legacy wrappé"""
        from ..implementations.legacy_position_wrapper import LegacyPositionCalculatorWrapper
        return LegacyPositionCalculatorWrapper(config or PositionConfig())
    
    def _create_testable_validator(self, config: Dict[str, Any]) -> IPositionValidator:
        """Créer validateur testable"""
        from ..implementations.testable_position_validator import TestablePositionValidator
        return TestablePositionValidator(config or {})
    
    def _create_legacy_validator(self, config: Dict[str, Any]) -> IPositionValidator:
        """Créer validateur legacy wrappé"""
        from ..implementations.legacy_position_wrapper import LegacyPositionValidatorWrapper
        return LegacyPositionValidatorWrapper(config or {})
    
    def _create_testable_executor(self, config: Dict[str, Any]) -> IPositionExecutor:
        """Créer exécuteur testable"""
        from ..implementations.testable_position_executor import TestablePositionExecutor
        return TestablePositionExecutor(config or {})
    
    def _create_legacy_executor(self, config: Dict[str, Any]) -> IPositionExecutor:
        """Créer exécuteur legacy wrappé"""
        from ..implementations.legacy_position_wrapper import LegacyPositionExecutorWrapper
        return LegacyPositionExecutorWrapper(config or {})
    
    def _create_mock_executor(self, config: Dict[str, Any]) -> IPositionExecutor:
        """Créer mock exécuteur pour tests"""
        from ..implementations.mock_position_components import MockPositionExecutor
        return MockPositionExecutor(config or {})
    
    def _create_database_repository(self, config: Dict[str, Any]) -> IPositionRepository:
        """Créer repository base de données"""
        from ..implementations.database_position_repository import DatabasePositionRepository
        return DatabasePositionRepository(config or {})
    
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
    
    def _create_testable_analyzer_with_components(self, 
                                                config: AnalyzerConfig,
                                                indicator_calculator: IIndicatorCalculator,
                                                signal_generator: ISignalGenerator,
                                                score_calculator: IScoreCalculator) -> IAnalyzer:
        """Créer analyzer avec injection composants"""
        from ..implementations.testable_analyzer_v2 import TestableAnalyzerV2
        return TestableAnalyzerV2(config, indicator_calculator, signal_generator, score_calculator)
    
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
    
    def _create_testable_orchestrator(self, calculator, validator, executor, repository) -> IPositionOrchestrator:
        """Créer orchestrateur testable"""
        from ..implementations.testable_position_orchestrator import TestablePositionOrchestrator
        return TestablePositionOrchestrator(calculator, validator, executor, repository)
    
    def _create_legacy_orchestrator(self, calculator, validator, executor, repository) -> IPositionOrchestrator:
        """Créer orchestrateur legacy wrappé"""
        from ..implementations.legacy_position_wrapper import LegacyPositionOrchestratorWrapper
        return LegacyPositionOrchestratorWrapper(calculator, validator, executor, repository)


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


class AnalyzerFactory:
    """Factory pour composants Analyzer refactorisés"""
    
    def __init__(self, config: FactoryConfig = None):
        self.config = config or FactoryConfig()
        self.feature_flags = get_feature_flags_manager()
        
        logger.info(f"✅ AnalyzerFactory initialisée")
    
    def create_data_normalizer(self):
        """Créer normalisateur de données"""
        if self.feature_flags.is_enabled('use_testable_analyzer'):
            from ..implementations.data_normalization_stage import DataNormalizationStage
            return DataNormalizationStage()
        else:
            from ..implementations.legacy_analyzer_wrapper import LegacyDataNormalizerWrapper
            return LegacyDataNormalizerWrapper()
    
    def create_indicator_calculator(self):
        """Créer calculateur d'indicateurs"""
        if self.feature_flags.is_enabled('use_testable_analyzer'):
            from ..implementations.indicator_calculation_stage import IndicatorCalculationStage
            from ..implementations.indicator_factory import IndicatorFactory
            return IndicatorCalculationStage(IndicatorFactory())
        else:
            from ..implementations.legacy_analyzer_wrapper import LegacyIndicatorCalculatorWrapper
            return LegacyIndicatorCalculatorWrapper()
    
    def create_analysis_pipeline(self):
        """Créer pipeline d'analyse complet"""
        if self.feature_flags.is_enabled('use_testable_analyzer'):
            from ..implementations.analysis_pipeline import AnalysisPipeline
            pipeline = AnalysisPipeline()
            
            # Ajouter stages
            pipeline.add_stage(self.create_data_normalizer())
            pipeline.add_stage(self.create_indicator_calculator())
            
            return pipeline
        else:
            from ..implementations.legacy_analyzer_wrapper import LegacyAnalyzerWrapper
            return LegacyAnalyzerWrapper()


# Factory globale analyzer
_analyzer_factory = None

def get_analyzer_factory(config: FactoryConfig = None) -> AnalyzerFactory:
    """Obtenir instance globale analyzer factory"""
    global _analyzer_factory
    if _analyzer_factory is None or config is not None:
        _analyzer_factory = AnalyzerFactory(config)
    return _analyzer_factory
