"""
TestableScanPipeline - Trade Cursor v7.0 Phase 3
Pipeline de scan modulaire et configurable
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import time

from ..interfaces.scanner_interfaces import (
    IScanPipeline, IScanStep, ScanPipelineStep, ScanPipelineResult, 
    ScanPipelineStepType, ScanResult, ScanStatus
)

logger = logging.getLogger(__name__)


class TestableScanPipeline(IScanPipeline):
    """
    Pipeline de scan modulaire et configurable
    
    Responsabilités:
    - Exécution séquentielle des étapes
    - Gestion des timeouts par étape
    - Retry automatique configurabel
    - Monitoring performance par étape
    - Context sharing entre étapes
    - Circuit breaker intégré
    """
    
    def __init__(self, max_parallel_steps: int = 1, enable_circuit_breaker: bool = True):
        self.max_parallel_steps = max_parallel_steps
        self.enable_circuit_breaker = enable_circuit_breaker
        
        # Pipeline steps (ordre d'exécution)
        self.pipeline_steps: List[IScanStep] = []
        self.step_configs: Dict[str, ScanPipelineStep] = {}
        
        # Métriques de performance
        self.execution_count = 0
        self.successful_executions = 0
        self.failed_executions = 0
        self.total_execution_time_ms = 0.0
        
        # Circuit breaker
        self.circuit_breaker_threshold = 5  # Échecs consécutifs
        self.consecutive_failures = 0
        self.circuit_open = False
        self.circuit_open_time = None
        self.circuit_recovery_time_seconds = 60
        
        # Stats par étape
        self.step_stats: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"✅ TestableScanPipeline initialisé (parallel: {max_parallel_steps}, circuit_breaker: {enable_circuit_breaker})")
    
    async def execute_pipeline(self, symbol: str, config: Optional[Dict[str, Any]] = None) -> ScanPipelineResult:
        """Exécute le pipeline complet pour une paire"""
        try:
            start_time = datetime.utcnow()
            self.execution_count += 1
            
            # Vérifier circuit breaker
            if self._is_circuit_open():
                return self._create_circuit_breaker_result(symbol)
            
            # Initialiser résultat
            result = ScanPipelineResult(
                symbol=symbol,
                timestamp=start_time
            )
            
            # Context partagé entre étapes
            context = {
                'symbol': symbol,
                'pipeline_config': config or {},
                'execution_start': start_time,
                'results': {}
            }
            
            logger.debug(f"🔄 Starting pipeline execution for {symbol} ({len(self.pipeline_steps)} steps)")
            
            # Exécuter chaque étape séquentiellement
            for step in self.pipeline_steps:
                step_start_time = datetime.utcnow()
                step_config = step.get_step_config()
                
                # Vérifier si étape activée
                if not step.is_enabled():
                    logger.debug(f"⏭️ Skipping disabled step: {step_config.name}")
                    result.steps_executed.append(f"{step_config.name} (disabled)")
                    continue
                
                logger.debug(f"🔧 Executing step: {step_config.name} ({step_config.step_type.value})")
                
                try:
                    # Exécuter étape avec timeout
                    step_result = await self._execute_step_with_timeout(step, symbol, context, step_config)
                    
                    # Enregistrer résultat
                    result.step_results[step_config.name] = step_result
                    result.steps_executed.append(step_config.name)
                    
                    # Ajouter au context pour étapes suivantes
                    context['results'][step_config.name] = step_result
                    
                    # Métriques par étape
                    step_time = (datetime.utcnow() - step_start_time).total_seconds() * 1000
                    result.step_timings[step_config.name] = step_time
                    
                    self._update_step_stats(step_config.name, True, step_time)
                    
                    logger.debug(f"✅ Step completed: {step_config.name} ({step_time:.1f}ms)")
                    
                except asyncio.TimeoutError:
                    error_msg = f"Step timeout: {step_config.name} ({step_config.timeout_ms}ms)"
                    result.errors_by_step[step_config.name] = error_msg
                    self._update_step_stats(step_config.name, False, step_config.timeout_ms)
                    logger.warning(f"⏰ {error_msg}")
                    
                    # Décider si continuer ou arrêter
                    if self._should_stop_pipeline_on_step_failure(step_config):
                        break
                    
                except Exception as e:
                    error_msg = f"Step error: {step_config.name}: {str(e)}"
                    result.errors_by_step[step_config.name] = error_msg
                    step_time = (datetime.utcnow() - step_start_time).total_seconds() * 1000
                    self._update_step_stats(step_config.name, False, step_time)
                    logger.error(f"❌ {error_msg}")
                    
                    # Retry si configuré
                    if step_config.retry_attempts > 1:
                        retry_result = await self._retry_step(step, symbol, context, step_config)
                        if retry_result:
                            result.step_results[step_config.name] = retry_result
                            context['results'][step_config.name] = retry_result
                            continue
                    
                    # Décider si continuer ou arrêter
                    if self._should_stop_pipeline_on_step_failure(step_config):
                        break
            
            # Construire résultat final
            result.final_result = self._build_final_scan_result(symbol, context, result)
            
            # Métriques globales
            total_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            result.pipeline_duration_ms = total_time
            self.total_execution_time_ms += total_time
            
            # Évaluer succès
            if len(result.errors_by_step) == 0:
                self.successful_executions += 1
                self.consecutive_failures = 0  # Reset circuit breaker
            else:
                self.failed_executions += 1
                self._handle_pipeline_failure()
            
            logger.info(f"🏁 Pipeline execution completed for {symbol}: "
                       f"{len(result.steps_executed)} steps, {len(result.errors_by_step)} errors, {total_time:.1f}ms")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Pipeline execution failed for {symbol}: {e}")
            self.failed_executions += 1
            self._handle_pipeline_failure()
            
            return ScanPipelineResult(
                symbol=symbol,
                errors_by_step={'pipeline': f"Critical error: {str(e)}"},
                timestamp=datetime.utcnow()
            )
    
    def add_step(self, step: IScanStep) -> None:
        """Ajoute une étape au pipeline"""
        step_config = step.get_step_config()
        
        if step_config.name in self.step_configs:
            logger.warning(f"Step '{step_config.name}' already exists, replacing")
        
        self.pipeline_steps.append(step)
        self.step_configs[step_config.name] = step_config
        
        # Initialiser stats pour cette étape
        if step_config.name not in self.step_stats:
            self.step_stats[step_config.name] = {
                'total_executions': 0,
                'successful_executions': 0,
                'failed_executions': 0,
                'total_time_ms': 0.0,
                'average_time_ms': 0.0
            }
        
        logger.info(f"Step added to pipeline: {step_config.name} ({step_config.step_type.value})")
    
    def remove_step(self, step_name: str) -> None:
        """Supprime une étape du pipeline"""
        # Retirer de la liste
        self.pipeline_steps = [s for s in self.pipeline_steps if s.get_step_config().name != step_name]
        
        # Retirer config
        if step_name in self.step_configs:
            del self.step_configs[step_name]
        
        logger.info(f"Step removed from pipeline: {step_name}")
    
    def configure_step(self, step_name: str, config: Dict[str, Any]) -> None:
        """Configure une étape spécifique"""
        if step_name in self.step_configs:
            # Mettre à jour config de l'étape
            step_config = self.step_configs[step_name]
            step_config.config.update(config)
            logger.info(f"Step configured: {step_name}")
        else:
            logger.warning(f"Step not found for configuration: {step_name}")
    
    def get_pipeline_config(self) -> List[ScanPipelineStep]:
        """Retourne la configuration du pipeline"""
        return list(self.step_configs.values())
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du pipeline"""
        success_rate = 0.0
        if self.execution_count > 0:
            success_rate = self.successful_executions / self.execution_count
        
        avg_execution_time = 0.0
        if self.execution_count > 0:
            avg_execution_time = self.total_execution_time_ms / self.execution_count
        
        return {
            'overall': {
                'total_executions': self.execution_count,
                'successful_executions': self.successful_executions,
                'failed_executions': self.failed_executions,
                'success_rate': success_rate,
                'average_execution_time_ms': avg_execution_time
            },
            'circuit_breaker': {
                'enabled': self.enable_circuit_breaker,
                'is_open': self.circuit_open,
                'consecutive_failures': self.consecutive_failures,
                'threshold': self.circuit_breaker_threshold,
                'recovery_time_seconds': self.circuit_recovery_time_seconds
            },
            'steps': {
                'total_steps': len(self.pipeline_steps),
                'enabled_steps': sum(1 for s in self.pipeline_steps if s.is_enabled()),
                'step_stats': dict(self.step_stats)
            },
            'configuration': {
                'max_parallel_steps': self.max_parallel_steps,
                'pipeline_steps_order': [s.get_step_config().name for s in self.pipeline_steps]
            }
        }
    
    # =============================================================================
    # MÉTHODES PRIVÉES - Exécution des Étapes
    # =============================================================================
    
    async def _execute_step_with_timeout(self, step: IScanStep, symbol: str, context: Dict[str, Any], 
                                        step_config: ScanPipelineStep) -> Any:
        """Exécute une étape avec timeout"""
        try:
            # Exécuter avec timeout
            timeout_seconds = step_config.timeout_ms / 1000.0
            
            result = await asyncio.wait_for(
                step.execute(symbol, context),
                timeout=timeout_seconds
            )
            
            return result
            
        except asyncio.TimeoutError:
            logger.warning(f"Step timeout: {step_config.name} after {step_config.timeout_ms}ms")
            raise
        except Exception as e:
            logger.error(f"Step execution error: {step_config.name}: {e}")
            raise
    
    async def _retry_step(self, step: IScanStep, symbol: str, context: Dict[str, Any], 
                         step_config: ScanPipelineStep) -> Optional[Any]:
        """Retry une étape en cas d'échec"""
        for attempt in range(1, step_config.retry_attempts):
            try:
                logger.debug(f"🔄 Retrying step {step_config.name}: attempt {attempt + 1}/{step_config.retry_attempts}")
                
                # Délai entre retries (backoff)
                delay_ms = 500 * (2 ** (attempt - 1))  # 500ms, 1s, 2s, etc.
                await asyncio.sleep(delay_ms / 1000.0)
                
                # Retry execution
                result = await self._execute_step_with_timeout(step, symbol, context, step_config)
                
                logger.info(f"✅ Step retry successful: {step_config.name} (attempt {attempt + 1})")
                return result
                
            except Exception as e:
                logger.debug(f"❌ Step retry failed: {step_config.name} attempt {attempt + 1}: {e}")
                
                if attempt == step_config.retry_attempts - 1:
                    logger.error(f"❌ All retries exhausted for step: {step_config.name}")
        
        return None
    
    def _should_stop_pipeline_on_step_failure(self, step_config: ScanPipelineStep) -> bool:
        """Détermine si le pipeline doit s'arrêter en cas d'échec d'étape"""
        # Les étapes critiques arrêtent le pipeline
        critical_steps = [
            ScanPipelineStepType.DATA_COLLECTION,
            ScanPipelineStepType.SCORING
        ]
        
        return step_config.step_type in critical_steps
    
    def _build_final_scan_result(self, symbol: str, context: Dict[str, Any], 
                                pipeline_result: ScanPipelineResult) -> ScanResult:
        """Construit le résultat final de scan depuis les résultats du pipeline"""
        try:
            # Créer résultat de scan de base
            scan_result = ScanResult(
                symbol=symbol,
                status=ScanStatus.SUCCESS if len(pipeline_result.errors_by_step) == 0 else ScanStatus.FAILED,
                scan_duration_ms=pipeline_result.pipeline_duration_ms,
                timestamp=pipeline_result.timestamp
            )
            
            # Extraire données depuis les résultats d'étapes
            step_results = pipeline_result.step_results
            
            # Market data depuis étape data collection
            if 'data_collection' in step_results:
                data_result = step_results['data_collection']
                if isinstance(data_result, dict) and 'market_data' in data_result:
                    scan_result.market_data = data_result['market_data']
                    scan_result.data_collection_time_ms = pipeline_result.step_timings.get('data_collection', 0)
            
            # Scoring depuis étape scoring
            if 'scoring' in step_results:
                scoring_result = step_results['scoring']
                if hasattr(scoring_result, 'score') or (isinstance(scoring_result, dict) and 'score' in scoring_result):
                    scan_result.scoring_result = scoring_result
                    scan_result.scoring_time_ms = pipeline_result.step_timings.get('scoring', 0)
            
            # Filter result depuis étape filtering
            if 'filtering' in step_results:
                filter_result = step_results['filtering']
                if hasattr(filter_result, 'accepted') or (isinstance(filter_result, dict) and 'accepted' in filter_result):
                    scan_result.filter_result = filter_result
            
            # Analysis result depuis étape analysis
            if 'analysis' in step_results:
                analysis_result = step_results['analysis']
                scan_result.analysis_result = analysis_result
                scan_result.analysis_time_ms = pipeline_result.step_timings.get('analysis', 0)
            
            # ML prediction depuis étape ML
            if 'ml_prediction' in step_results:
                ml_result = step_results['ml_prediction']
                scan_result.ml_prediction = ml_result
            
            # Logging IDs depuis étape logging
            if 'logging' in step_results:
                logging_result = step_results['logging']
                if isinstance(logging_result, dict):
                    scan_result.scan_id = logging_result.get('scan_id')
                    scan_result.opportunity_id = logging_result.get('opportunity_id')
            
            # Collecter erreurs et warnings
            for step_name, error in pipeline_result.errors_by_step.items():
                scan_result.errors.append(f"Step {step_name}: {error}")
            
            return scan_result
            
        except Exception as e:
            logger.error(f"Error building final scan result: {e}")
            
            return ScanResult(
                symbol=symbol,
                status=ScanStatus.FAILED,
                errors=[f"Result building error: {str(e)}"],
                timestamp=datetime.utcnow()
            )
    
    # =============================================================================
    # MÉTHODES PRIVÉES - Circuit Breaker et Stats
    # =============================================================================
    
    def _is_circuit_open(self) -> bool:
        """Vérifie si le circuit breaker est ouvert"""
        if not self.enable_circuit_breaker:
            return False
        
        if not self.circuit_open:
            return False
        
        # Vérifier si temps de récupération écoulé
        if self.circuit_open_time:
            time_since_open = (datetime.utcnow() - self.circuit_open_time).total_seconds()
            if time_since_open >= self.circuit_recovery_time_seconds:
                self._close_circuit_breaker()
                return False
        
        return True
    
    def _handle_pipeline_failure(self):
        """Gère un échec de pipeline (circuit breaker)"""
        if not self.enable_circuit_breaker:
            return
        
        self.consecutive_failures += 1
        
        if self.consecutive_failures >= self.circuit_breaker_threshold:
            self._open_circuit_breaker()
    
    def _open_circuit_breaker(self):
        """Ouvre le circuit breaker"""
        self.circuit_open = True
        self.circuit_open_time = datetime.utcnow()
        
        logger.warning(f"🔥 Circuit breaker OPENED after {self.consecutive_failures} consecutive failures")
    
    def _close_circuit_breaker(self):
        """Ferme le circuit breaker"""
        self.circuit_open = False
        self.circuit_open_time = None
        self.consecutive_failures = 0
        
        logger.info("✅ Circuit breaker CLOSED - operations resumed")
    
    def _create_circuit_breaker_result(self, symbol: str) -> ScanPipelineResult:
        """Crée un résultat d'échec pour circuit breaker ouvert"""
        return ScanPipelineResult(
            symbol=symbol,
            errors_by_step={'pipeline': 'Circuit breaker is OPEN'},
            timestamp=datetime.utcnow()
        )
    
    def _update_step_stats(self, step_name: str, success: bool, duration_ms: float):
        """Met à jour les statistiques pour une étape"""
        if step_name not in self.step_stats:
            self.step_stats[step_name] = {
                'total_executions': 0,
                'successful_executions': 0,
                'failed_executions': 0,
                'total_time_ms': 0.0,
                'average_time_ms': 0.0
            }
        
        stats = self.step_stats[step_name]
        stats['total_executions'] += 1
        stats['total_time_ms'] += duration_ms
        
        if success:
            stats['successful_executions'] += 1
        else:
            stats['failed_executions'] += 1
        
        # Recalculer moyenne
        stats['average_time_ms'] = stats['total_time_ms'] / stats['total_executions']


# =============================================================================
# ÉTAPES DE PIPELINE PRÉDÉFINIES
# =============================================================================

class DataCollectionStep(IScanStep):
    """Étape de collecte des données de marché"""
    
    def __init__(self, market_data_collector):
        self.market_data_collector = market_data_collector
        self.config = ScanPipelineStep(
            name='data_collection',
            step_type=ScanPipelineStepType.DATA_COLLECTION,
            enabled=True,
            timeout_ms=10000,  # 10s
            retry_attempts=2
        )
    
    async def execute(self, symbol: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Collecte les données de marché"""
        timeframes = context.get('pipeline_config', {}).get('timeframes', ['1m', '5m'])
        
        market_data = await self.market_data_collector.collect_complete_market_data(symbol, timeframes)
        
        return {
            'market_data': market_data,
            'data_quality': market_data.data_quality,
            'collection_source': market_data.source.value
        }
    
    def get_step_config(self) -> ScanPipelineStep:
        return self.config
    
    def is_enabled(self) -> bool:
        return self.config.enabled


class ScoringStep(IScanStep):
    """Étape de scoring de scalabilité"""
    
    def __init__(self, scalability_scorer):
        self.scalability_scorer = scalability_scorer
        self.config = ScanPipelineStep(
            name='scoring',
            step_type=ScanPipelineStepType.SCORING,
            enabled=True,
            timeout_ms=5000,  # 5s
            retry_attempts=1
        )
    
    async def execute(self, symbol: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Calcule le score de scalabilité"""
        market_data = context['results']['data_collection']['market_data']
        
        scoring_result = self.scalability_scorer.calculate_score(market_data)
        
        return {
            'scoring_result': scoring_result,
            'score': scoring_result.score,
            'is_valid': scoring_result.is_valid,
            'rejection_reason': scoring_result.rejection_reason
        }
    
    def get_step_config(self) -> ScanPipelineStep:
        return self.config
    
    def is_enabled(self) -> bool:
        return self.config.enabled


class FilteringStep(IScanStep):
    """Étape de filtrage des paires"""
    
    def __init__(self, pair_filter):
        self.pair_filter = pair_filter
        self.config = ScanPipelineStep(
            name='filtering',
            step_type=ScanPipelineStepType.FILTERING,
            enabled=True,
            timeout_ms=3000,  # 3s
            retry_attempts=1
        )
    
    async def execute(self, symbol: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Filtre la paire selon les critères"""
        market_data = context['results']['data_collection']['market_data']
        scoring_result = context['results']['scoring']['scoring_result']
        
        filter_result = self.pair_filter.filter_pair(symbol, market_data, scoring_result)
        
        return {
            'filter_result': filter_result,
            'accepted': filter_result.accepted,
            'rejection_reasons': filter_result.rejection_reasons
        }
    
    def get_step_config(self) -> ScanPipelineStep:
        return self.config
    
    def is_enabled(self) -> bool:
        return self.config.enabled


class AnalysisStep(IScanStep):
    """Étape d'analyse technique (intégration Phase 2)"""
    
    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.config = ScanPipelineStep(
            name='analysis',
            step_type=ScanPipelineStepType.ANALYSIS,
            enabled=True,
            timeout_ms=15000,  # 15s
            retry_attempts=1
        )
    
    async def execute(self, symbol: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Effectue l'analyse technique"""
        market_data = context['results']['data_collection']['market_data']
        
        # Construire données pour analyzer (format attendu)
        analyzer_data = {
            'ohlcv_1m': market_data.ohlcv_1m.klines if market_data.ohlcv_1m else [],
            'ohlcv_5m': market_data.ohlcv_5m.klines if market_data.ohlcv_5m else [],
            'current_price': market_data.ticker.price if market_data.ticker else 0.0
        }
        
        analysis_result = self.analyzer.analyze_pair(symbol, analyzer_data)
        
        return {
            'analysis_result': analysis_result,
            'is_valid': analysis_result.is_valid if hasattr(analysis_result, 'is_valid') else False,
            'is_opportunity': getattr(analysis_result, 'primary_signal', None) is not None
        }
    
    def get_step_config(self) -> ScanPipelineStep:
        return self.config
    
    def is_enabled(self) -> bool:
        return self.config.enabled


class LoggingStep(IScanStep):
    """Étape de logging PostgreSQL"""
    
    def __init__(self, scan_logger):
        self.scan_logger = scan_logger
        self.config = ScanPipelineStep(
            name='logging',
            step_type=ScanPipelineStepType.LOGGING,
            enabled=True,
            timeout_ms=5000,  # 5s
            retry_attempts=2
        )
    
    async def execute(self, symbol: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Log les résultats de scan"""
        # Construire scan result depuis le context
        scan_result = context['results'].get('analysis', {}).get('analysis_result')
        
        scan_id = None
        opportunity_id = None
        
        if self.scan_logger and scan_result:
            scan_id = await self.scan_logger.log_scan(scan_result)
            
            # Si c'est une opportunité, logger aussi
            if getattr(scan_result, 'is_valid', False):
                opportunity_id = await self.scan_logger.log_opportunity(scan_result)
        
        return {
            'scan_id': scan_id,
            'opportunity_id': opportunity_id,
            'logged': scan_id is not None
        }
    
    def get_step_config(self) -> ScanPipelineStep:
        return self.config
    
    def is_enabled(self) -> bool:
        return self.config.enabled
