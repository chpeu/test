"""
TestableScannerOrchestrator - Trade Cursor v7.0 Phase 3
Orchestrateur principal du Scanner découplé
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import time

from ..interfaces.scanner_interfaces import (
    IScannerOrchestrator, ScanResult, ScanBatchResult, ScannerConfig,
    ScanStatus, ScannerValidationUtils
)

logger = logging.getLogger(__name__)


class TestableScannerOrchestrator(IScannerOrchestrator):
    """
    Orchestrateur principal du Scanner découplé
    
    Responsabilités:
    - Coordination scan multi-symboles
    - Integration avec Analyzer Phase 2
    - ML predictions integration
    - PostgreSQL logging coordination
    - Cache management global
    - Statistics & monitoring
    """
    
    def __init__(self, scan_pipeline, config: Optional[ScannerConfig] = None):
        self.scan_pipeline = scan_pipeline
        self.config = config or ScannerConfig()
        
        # Métriques globales
        self.total_scans = 0
        self.successful_scans = 0
        self.failed_scans = 0
        self.total_scan_time_ms = 0.0
        
        # Cache des résultats
        self._scan_cache: Dict[str, Dict] = {}
        
        # Semaphore pour limitation concurrence
        self.scan_semaphore = asyncio.Semaphore(self.config.max_concurrent_scans)
        
        logger.info(f"✅ TestableScannerOrchestrator initialisé (max_concurrent: {self.config.max_concurrent_scans})")
    
    async def scan_single_pair(self, symbol: str, config: Optional[ScannerConfig] = None) -> ScanResult:
        """Scanne une seule paire"""
        try:
            start_time = datetime.utcnow()
            self.total_scans += 1
            
            # Configuration effective
            effective_config = config or self.config
            
            # Validation symbol
            if not ScannerValidationUtils.is_valid_symbol(symbol):
                return self._create_failed_result(symbol, "Invalid symbol format", start_time)
            
            # Limiter concurrence
            async with self.scan_semaphore:
                logger.debug(f"🔍 Starting single scan for {symbol}")
                
                # Exécuter pipeline
                pipeline_result = await self.scan_pipeline.execute_pipeline(
                    symbol, 
                    {'timeframes': effective_config.default_timeframes}
                )
                
                # Convertir en ScanResult
                scan_result = pipeline_result.final_result or self._build_scan_result_from_pipeline(
                    symbol, pipeline_result, start_time
                )
                
                # Métriques
                scan_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                scan_result.scan_duration_ms = scan_time
                self.total_scan_time_ms += scan_time
                
                if scan_result.is_success:
                    self.successful_scans += 1
                    logger.info(f"✅ Single scan successful: {symbol} ({scan_time:.1f}ms)")
                else:
                    self.failed_scans += 1
                    logger.warning(f"❌ Single scan failed: {symbol} - {scan_result.errors}")
                
                return scan_result
                
        except Exception as e:
            logger.error(f"❌ Single scan error for {symbol}: {e}")
            self.failed_scans += 1
            return self._create_failed_result(symbol, f"Scan error: {str(e)}", start_time)
    
    async def scan_batch_pairs(self, symbols: List[str], config: Optional[ScannerConfig] = None) -> ScanBatchResult:
        """Scanne plusieurs paires en parallèle"""
        try:
            start_time = datetime.utcnow()
            effective_config = config or self.config
            
            logger.info(f"🔍 Starting batch scan: {len(symbols)} symbols")
            
            # Limiter nombre de workers parallèles
            max_workers = min(len(symbols), effective_config.max_parallel_workers)
            
            # Créer tâches de scan
            scan_tasks = []
            for symbol in symbols:
                task = self.scan_single_pair(symbol, effective_config)
                scan_tasks.append(task)
            
            # Exécuter avec timeout global
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*scan_tasks, return_exceptions=True),
                    timeout=effective_config.batch_scan_timeout_ms / 1000.0
                )
            except asyncio.TimeoutError:
                logger.error(f"❌ Batch scan timeout after {effective_config.batch_scan_timeout_ms}ms")
                results = [self._create_failed_result(s, "Batch timeout", start_time) for s in symbols]
            
            # Traiter résultats
            batch_result = ScanBatchResult(
                symbols=symbols,
                batch_id=f"batch_{int(time.time())}",
                parallel_workers=max_workers
            )
            
            for i, symbol in enumerate(symbols):
                if i < len(results):
                    result = results[i]
                    if isinstance(result, ScanResult):
                        batch_result.results[symbol] = result
                    elif isinstance(result, Exception):
                        failed_result = self._create_failed_result(symbol, str(result), start_time)
                        batch_result.results[symbol] = failed_result
            
            # Calculer métriques batch
            total_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            batch_result.total_duration_ms = total_time
            
            logger.info(f"✅ Batch scan completed: {batch_result.successful_scans}/{len(symbols)} successful, "
                       f"{batch_result.opportunities_found} opportunities, {total_time:.1f}ms")
            
            return batch_result
            
        except Exception as e:
            logger.error(f"❌ Batch scan error: {e}")
            return ScanBatchResult(symbols=symbols)
    
    async def scan_top_pairs(self, limit: int = 20, config: Optional[ScannerConfig] = None) -> ScanBatchResult:
        """Scanne les meilleures paires selon les critères"""
        try:
            # Pour l'instant, utilise une liste prédéfinie
            # En production, cela viendrait de la collecte des paires par volume/activité
            top_symbols = [
                'BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT', 'MATIC/USDT:USDT',
                'ADA/USDT:USDT', 'DOT/USDT:USDT', 'LINK/USDT:USDT', 'AVAX/USDT:USDT',
                'UNI/USDT:USDT', 'LTC/USDT:USDT', 'BCH/USDT:USDT', 'XRP/USDT:USDT',
                'ATOM/USDT:USDT', 'NEAR/USDT:USDT', 'FIL/USDT:USDT', 'ALGO/USDT:USDT',
                'VET/USDT:USDT', 'THETA/USDT:USDT', 'ICP/USDT:USDT', 'SAND/USDT:USDT'
            ]
            
            selected_symbols = top_symbols[:limit]
            
            logger.info(f"🔍 Scanning top {len(selected_symbols)} pairs")
            
            return await self.scan_batch_pairs(selected_symbols, config)
            
        except Exception as e:
            logger.error(f"❌ Top pairs scan error: {e}")
            return ScanBatchResult(symbols=[])
    
    def get_scan_statistics(self) -> Dict[str, Any]:
        """Retourne les statistiques globales de scan"""
        success_rate = 0.0
        if self.total_scans > 0:
            success_rate = self.successful_scans / self.total_scans
        
        avg_scan_time = 0.0
        if self.total_scans > 0:
            avg_scan_time = self.total_scan_time_ms / self.total_scans
        
        # Stats pipeline
        pipeline_stats = self.scan_pipeline.get_pipeline_stats() if self.scan_pipeline else {}
        
        return {
            'orchestrator': {
                'total_scans': self.total_scans,
                'successful_scans': self.successful_scans,
                'failed_scans': self.failed_scans,
                'success_rate': success_rate,
                'average_scan_time_ms': avg_scan_time
            },
            'pipeline': pipeline_stats,
            'cache': {
                'cache_size': len(self._scan_cache),
                'cache_enabled': self.config.enable_cache
            },
            'configuration': {
                'max_concurrent_scans': self.config.max_concurrent_scans,
                'max_parallel_workers': self.config.max_parallel_workers,
                'single_scan_timeout_ms': self.config.single_scan_timeout_ms,
                'batch_scan_timeout_ms': self.config.batch_scan_timeout_ms,
                'default_timeframes': self.config.default_timeframes
            }
        }
    
    def configure_scanner(self, config: ScannerConfig) -> None:
        """Configure le scanner"""
        self.config = config
        
        # Recréer semaphore si max_concurrent a changé
        if hasattr(self, 'scan_semaphore'):
            self.scan_semaphore = asyncio.Semaphore(config.max_concurrent_scans)
        
        logger.info("Scanner configuration updated")
    
    async def health_check(self) -> Dict[str, Any]:
        """Vérifie la santé du scanner"""
        try:
            health_status = {
                'status': 'healthy',
                'timestamp': datetime.utcnow().isoformat(),
                'components': {}
            }
            
            # Vérifier pipeline
            if self.scan_pipeline:
                pipeline_stats = self.scan_pipeline.get_pipeline_stats()
                pipeline_health = 'healthy' if pipeline_stats['overall']['success_rate'] > 0.8 else 'degraded'
                health_status['components']['pipeline'] = {
                    'status': pipeline_health,
                    'success_rate': pipeline_stats['overall']['success_rate']
                }
            else:
                health_status['components']['pipeline'] = {'status': 'missing'}
                health_status['status'] = 'unhealthy'
            
            # Vérifier circuit breaker
            if self.scan_pipeline and pipeline_stats.get('circuit_breaker', {}).get('is_open'):
                health_status['status'] = 'degraded'
                health_status['components']['circuit_breaker'] = {'status': 'open'}
            else:
                health_status['components']['circuit_breaker'] = {'status': 'closed'}
            
            # Vérifier taux de succès récent
            if self.total_scans > 10:  # Suffisamment d'échantillons
                recent_success_rate = self.successful_scans / self.total_scans
                if recent_success_rate < 0.5:
                    health_status['status'] = 'unhealthy'
                elif recent_success_rate < 0.8:
                    health_status['status'] = 'degraded'
            
            return health_status
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    # =============================================================================
    # MÉTHODES PRIVÉES
    # =============================================================================
    
    def _create_failed_result(self, symbol: str, error_msg: str, start_time: datetime) -> ScanResult:
        """Crée un résultat d'échec"""
        scan_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return ScanResult(
            symbol=symbol,
            status=ScanStatus.FAILED,
            errors=[error_msg],
            scan_duration_ms=scan_time,
            timestamp=datetime.utcnow()
        )
    
    def _build_scan_result_from_pipeline(self, symbol: str, pipeline_result, start_time: datetime) -> ScanResult:
        """Construit un ScanResult depuis un résultat de pipeline"""
        scan_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Déterminer statut
        status = ScanStatus.SUCCESS if len(pipeline_result.errors_by_step) == 0 else ScanStatus.FAILED
        
        # Collecter erreurs
        errors = []
        for step_name, error in pipeline_result.errors_by_step.items():
            errors.append(f"Step {step_name}: {error}")
        
        return ScanResult(
            symbol=symbol,
            status=status,
            errors=errors,
            scan_duration_ms=scan_time,
            timestamp=datetime.utcnow()
        )
