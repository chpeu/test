"""
TestableAnalysisOrchestrator - Trade Cursor v7.0
Orchestrateur d'analyse pour coordination complète des composants
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from ..interfaces.analyzer_interfaces import (
    IAnalysisOrchestrator, IAnalyzer, ISignalValidator,
    AnalysisResult, AnalysisStatus, SignalResult, SignalStrength,
    ValidationUtils
)

logger = logging.getLogger(__name__)


class TestableAnalysisOrchestrator(IAnalysisOrchestrator):
    """
    Orchestrateur d'analyse découplé et testable
    
    Responsabilités:
    - Coordination analyse multi-symboles
    - Filtrage et classement opportunités
    - Gestion parallélisation et timeouts
    - Métriques et monitoring global
    - Gestion des erreurs et fallbacks
    """
    
    def __init__(self, analyzer: IAnalyzer, validator: ISignalValidator, max_workers: int = 4):
        self.analyzer = analyzer
        self.validator = validator
        self.max_workers = max_workers
        
        # Thread pool pour analyses parallèles
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Métriques globales
        self.total_orchestrations = 0
        self.successful_orchestrations = 0
        self.failed_orchestrations = 0
        self.total_symbols_analyzed = 0
        self.total_opportunities_found = 0
        
        # Cache et optimisations
        self._analysis_cache = {}
        self._cache_ttl_seconds = 60  # Cache 1 minute
        
        # Timeouts
        self.analysis_timeout_seconds = 30
        self.batch_timeout_seconds = 120
        
        # Lock pour thread safety
        self._stats_lock = threading.Lock()
        
        logger.info(f"✅ TestableAnalysisOrchestrator initialisé (workers: {max_workers})")
    
    def coordinate_analysis(self, symbols: List[str], market_data: Dict[str, Dict[str, Any]]) -> Dict[str, AnalysisResult]:
        """Coordonne l'analyse de plusieurs symboles"""
        try:
            start_time = datetime.utcnow()
            self.total_orchestrations += 1
            
            logger.info(f"🎯 Starting orchestrated analysis for {len(symbols)} symbols")
            
            # Validation des entrées
            if not symbols:
                logger.warning("No symbols provided for analysis")
                return {}
            
            # Préparer tâches d'analyse
            analysis_tasks = []
            for symbol in symbols:
                symbol_market_data = market_data.get(symbol, {})
                if not symbol_market_data:
                    logger.warning(f"No market data for {symbol}, skipping")
                    continue
                
                # Vérifier cache d'abord
                cached_result = self._get_cached_analysis(symbol, symbol_market_data)
                if cached_result:
                    analysis_tasks.append((symbol, cached_result))
                    continue
                
                analysis_tasks.append((symbol, None))  # Marqueur pour analyse nécessaire
            
            # Séparer analyses cachées et nouvelles
            cached_results = {symbol: result for symbol, result in analysis_tasks if result is not None}
            symbols_to_analyze = [symbol for symbol, result in analysis_tasks if result is None]
            
            logger.debug(f"Using {len(cached_results)} cached results, analyzing {len(symbols_to_analyze)} new symbols")
            
            # Analyser symboles manquants
            new_results = {}
            if symbols_to_analyze:
                if len(symbols_to_analyze) == 1:
                    # Analyse simple pour un seul symbole
                    symbol = symbols_to_analyze[0]
                    result = self._analyze_single_symbol_safe(symbol, market_data[symbol])
                    new_results[symbol] = result
                else:
                    # Analyse parallèle pour plusieurs symboles
                    new_results = self._analyze_symbols_parallel(symbols_to_analyze, market_data)
            
            # Combiner résultats cachés et nouveaux
            all_results = {**cached_results, **new_results}
            
            # Mettre à jour cache
            self._update_analysis_cache(new_results)
            
            # Mettre à jour statistiques
            with self._stats_lock:
                self.total_symbols_analyzed += len(symbols_to_analyze)
                
                # Compter opportunités
                opportunities = sum(1 for result in all_results.values() if result.is_valid)
                self.total_opportunities_found += opportunities
                
                if len(all_results) > 0:
                    self.successful_orchestrations += 1
                else:
                    self.failed_orchestrations += 1
            
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            logger.info(f"✅ Orchestrated analysis completed: {len(all_results)}/{len(symbols)} symbols, "
                       f"{opportunities} opportunities in {processing_time:.1f}ms")
            
            return all_results
            
        except Exception as e:
            logger.error(f"❌ Orchestrated analysis failed: {e}")
            with self._stats_lock:
                self.failed_orchestrations += 1
            return {}
    
    def filter_opportunities(self, analysis_results: Dict[str, AnalysisResult], filters: Dict[str, Any]) -> Dict[str, AnalysisResult]:
        """Filtre les opportunités selon des critères"""
        try:
            logger.debug(f"🔍 Filtering {len(analysis_results)} analysis results")
            
            filtered_results = {}
            
            for symbol, result in analysis_results.items():
                # Filtre de base: only valid analyses
                if not result.is_valid:
                    continue
                
                # Filtre score minimum
                min_score = filters.get('min_combined_score', 0.0)
                if result.combined_score and result.combined_score < min_score:
                    logger.debug(f"Filtered {symbol}: score {result.combined_score:.2f} < {min_score}")
                    continue
                
                # Filtre confiance signal minimum
                min_confidence = filters.get('min_signal_confidence', 0.0)
                if (result.primary_signal and 
                    result.primary_signal.confidence < min_confidence):
                    logger.debug(f"Filtered {symbol}: confidence {result.primary_signal.confidence:.3f} < {min_confidence}")
                    continue
                
                # Filtre force signal minimum
                min_strength = filters.get('min_signal_strength')
                if min_strength and result.primary_signal:
                    strength_values = {
                        'weak': 1, 'moderate': 2, 'strong': 3, 'very_strong': 4
                    }
                    signal_strength_val = strength_values.get(result.primary_signal.strength.value, 0)
                    min_strength_val = strength_values.get(min_strength, 0)
                    
                    if signal_strength_val < min_strength_val:
                        logger.debug(f"Filtered {symbol}: strength {result.primary_signal.strength.value} < {min_strength}")
                        continue
                
                # Filtre qualité données minimum
                min_data_quality = filters.get('min_data_quality', 0.0)
                if result.data_quality_score < min_data_quality:
                    logger.debug(f"Filtered {symbol}: data quality {result.data_quality_score:.3f} < {min_data_quality}")
                    continue
                
                # Filtre timeframes spécifiques
                required_timeframes = filters.get('required_timeframes', [])
                if required_timeframes:
                    has_required = False
                    for tf in required_timeframes:
                        if tf == '1m' and result.score_1m and result.score_1m > 0:
                            has_required = True
                        elif tf == '5m' and result.score_5m and result.score_5m > 0:
                            has_required = True
                    
                    if not has_required:
                        logger.debug(f"Filtered {symbol}: missing required timeframes {required_timeframes}")
                        continue
                
                # Filtre validation signal
                validate_signals = filters.get('validate_signals', False)
                if validate_signals and result.primary_signal and result.market_context:
                    if not self.validator.validate_signal(result.primary_signal, result.market_context):
                        logger.debug(f"Filtered {symbol}: signal validation failed")
                        continue
                
                # Filtre conditions marché
                validate_market = filters.get('validate_market_conditions', False)
                if validate_market and result.market_context:
                    if not self.validator.validate_market_conditions(result.market_context):
                        logger.debug(f"Filtered {symbol}: market conditions validation failed")
                        continue
                
                # Filtre symbols spécifiques (whitelist/blacklist)
                symbol_whitelist = filters.get('symbol_whitelist', [])
                if symbol_whitelist and symbol not in symbol_whitelist:
                    continue
                
                symbol_blacklist = filters.get('symbol_blacklist', [])
                if symbol_blacklist and symbol in symbol_blacklist:
                    continue
                
                # Si tous filtres passés, garder le résultat
                filtered_results[symbol] = result
            
            logger.info(f"✅ Filtering completed: {len(filtered_results)}/{len(analysis_results)} opportunities passed")
            
            return filtered_results
            
        except Exception as e:
            logger.error(f"❌ Filtering failed: {e}")
            return analysis_results  # Retourner résultats non filtrés en cas d'erreur
    
    def rank_opportunities(self, opportunities: Dict[str, AnalysisResult]) -> List[Tuple[str, AnalysisResult]]:
        """Classe les opportunités par pertinence"""
        try:
            logger.debug(f"📊 Ranking {len(opportunities)} opportunities")
            
            if not opportunities:
                return []
            
            # Fonction de scoring pour classement
            def calculate_ranking_score(symbol: str, result: AnalysisResult) -> float:
                score = 0.0
                
                # Score combiné (40% du poids)
                if result.combined_score:
                    normalized_score = ValidationUtils.normalize_score(result.combined_score, 0.0, 10.0)
                    score += normalized_score * 0.4
                
                # Confiance signal (30% du poids)
                if result.primary_signal:
                    score += result.primary_signal.confidence * 0.3
                
                # Force signal (20% du poids)
                if result.primary_signal:
                    strength_weights = {
                        'weak': 0.25, 'moderate': 0.5, 'strong': 0.75, 'very_strong': 1.0
                    }
                    strength_weight = strength_weights.get(result.primary_signal.strength.value, 0.5)
                    score += strength_weight * 0.2
                
                # Qualité données (10% du poids)
                score += result.data_quality_score * 0.1
                
                # Bonus signaux secondaires
                if result.secondary_signals:
                    supporting_signals = sum(1 for s in result.secondary_signals 
                                           if s.signal_type == result.primary_signal.signal_type)
                    signal_bonus = min(0.1, supporting_signals * 0.02)  # Max 5 signaux = 10% bonus
                    score += signal_bonus
                
                # Bonus confluence timeframes
                if (result.score_1m and result.score_5m and 
                    abs(result.score_1m - result.score_5m) < 2.0):
                    score += 0.05  # Bonus confluence
                
                # Pénalité warnings
                if result.has_warnings:
                    score *= 0.95
                
                # Bonus performance de traitement (analyse rapide = bonus)
                if result.processing_time_ms and result.processing_time_ms < 1000:  # < 1s
                    speed_bonus = (1000 - result.processing_time_ms) / 10000  # Max 10% bonus
                    score += min(0.1, speed_bonus)
                
                return score
            
            # Calculer scores et trier
            scored_opportunities = []
            for symbol, result in opportunities.items():
                ranking_score = calculate_ranking_score(symbol, result)
                scored_opportunities.append((symbol, result, ranking_score))
            
            # Trier par score décroissant
            scored_opportunities.sort(key=lambda x: x[2], reverse=True)
            
            # Retourner sans le score de ranking (juste symbol, result)
            ranked_opportunities = [(symbol, result) for symbol, result, _ in scored_opportunities]
            
            # Log top 5
            top_5 = ranked_opportunities[:5]
            for i, (symbol, result) in enumerate(top_5, 1):
                score_info = f"{result.combined_score:.1f}" if result.combined_score else "N/A"
                signal_info = result.primary_signal.signal_type.value if result.primary_signal else "None"
                logger.info(f"#{i} {symbol}: score={score_info}, signal={signal_info}")
            
            logger.info(f"✅ Ranking completed: {len(ranked_opportunities)} opportunities ranked")
            
            return ranked_opportunities
            
        except Exception as e:
            logger.error(f"❌ Ranking failed: {e}")
            # Retourner liste non triée en cas d'erreur
            return list(opportunities.items())
    
    def get_analysis_summary(self, analysis_results: Dict[str, AnalysisResult]) -> Dict[str, Any]:
        """Résumé des analyses effectuées"""
        try:
            if not analysis_results:
                return {
                    'total_analyzed': 0,
                    'valid_opportunities': 0,
                    'failed_analyses': 0,
                    'average_score': 0.0,
                    'signal_distribution': {},
                    'error_summary': {}
                }
            
            # Statistiques de base
            total_analyzed = len(analysis_results)
            valid_opportunities = sum(1 for r in analysis_results.values() if r.is_valid)
            failed_analyses = sum(1 for r in analysis_results.values() if not r.is_valid)
            
            # Scores moyens
            valid_results = [r for r in analysis_results.values() if r.is_valid and r.combined_score]
            average_score = 0.0
            if valid_results:
                average_score = sum(r.combined_score for r in valid_results) / len(valid_results)
            
            # Distribution des signaux
            signal_distribution = {}
            for result in analysis_results.values():
                if result.primary_signal:
                    signal_type = result.primary_signal.signal_type.value
                    signal_distribution[signal_type] = signal_distribution.get(signal_type, 0) + 1
            
            # Résumé des erreurs
            error_summary = {}
            for result in analysis_results.values():
                if result.errors:
                    for error in result.errors:
                        error_key = error[:50] + "..." if len(error) > 50 else error
                        error_summary[error_key] = error_summary.get(error_key, 0) + 1
            
            # Métriques de performance
            processing_times = [r.processing_time_ms for r in analysis_results.values() 
                              if r.processing_time_ms is not None]
            
            performance_metrics = {}
            if processing_times:
                performance_metrics = {
                    'average_processing_time_ms': sum(processing_times) / len(processing_times),
                    'min_processing_time_ms': min(processing_times),
                    'max_processing_time_ms': max(processing_times)
                }
            
            # Métriques qualité
            data_quality_scores = [r.data_quality_score for r in analysis_results.values() 
                                 if r.data_quality_score > 0]
            
            quality_metrics = {}
            if data_quality_scores:
                quality_metrics = {
                    'average_data_quality': sum(data_quality_scores) / len(data_quality_scores),
                    'min_data_quality': min(data_quality_scores),
                    'max_data_quality': max(data_quality_scores)
                }
            
            summary = {
                'total_analyzed': total_analyzed,
                'valid_opportunities': valid_opportunities,
                'failed_analyses': failed_analyses,
                'success_rate': valid_opportunities / total_analyzed if total_analyzed > 0 else 0,
                'average_score': round(average_score, 2),
                'signal_distribution': signal_distribution,
                'error_summary': error_summary,
                'performance_metrics': performance_metrics,
                'quality_metrics': quality_metrics,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logger.debug(f"📋 Analysis summary: {valid_opportunities}/{total_analyzed} opportunities, "
                        f"avg score: {average_score:.2f}")
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Analysis summary failed: {e}")
            return {'error': str(e), 'timestamp': datetime.utcnow().isoformat()}
    
    def _analyze_single_symbol_safe(self, symbol: str, market_data: Dict[str, Any]) -> AnalysisResult:
        """Analyse sécurisée d'un seul symbole avec timeout"""
        try:
            # Analyser avec timeout
            start_time = datetime.utcnow()
            
            result = self.analyzer.analyze_pair(symbol, market_data)
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Vérifier timeout
            if processing_time > self.analysis_timeout_seconds:
                logger.warning(f"Analysis timeout for {symbol}: {processing_time:.1f}s")
                result.warnings.append(f"Analysis took {processing_time:.1f}s (timeout: {self.analysis_timeout_seconds}s)")
            
            return result
            
        except Exception as e:
            logger.error(f"Safe analysis failed for {symbol}: {e}")
            
            # Retourner résultat d'échec
            failed_result = AnalysisResult(
                symbol=symbol,
                status=AnalysisStatus.FAILED,
                timestamp=datetime.utcnow()
            )
            failed_result.errors.append(f"Analysis exception: {str(e)}")
            
            return failed_result
    
    def _analyze_symbols_parallel(self, symbols: List[str], market_data: Dict[str, Dict[str, Any]]) -> Dict[str, AnalysisResult]:
        """Analyse parallèle de plusieurs symboles"""
        try:
            results = {}
            
            # Créer futures pour exécution parallèle
            future_to_symbol = {}
            
            for symbol in symbols:
                symbol_market_data = market_data.get(symbol, {})
                if not symbol_market_data:
                    continue
                
                future = self.executor.submit(self._analyze_single_symbol_safe, symbol, symbol_market_data)
                future_to_symbol[future] = symbol
            
            # Attendre résultats avec timeout global
            try:
                for future in as_completed(future_to_symbol, timeout=self.batch_timeout_seconds):
                    symbol = future_to_symbol[future]
                    try:
                        result = future.result(timeout=self.analysis_timeout_seconds)
                        results[symbol] = result
                    except Exception as e:
                        logger.error(f"Future result failed for {symbol}: {e}")
                        
                        # Créer résultat d'échec
                        failed_result = AnalysisResult(
                            symbol=symbol,
                            status=AnalysisStatus.FAILED,
                            timestamp=datetime.utcnow()
                        )
                        failed_result.errors.append(f"Future execution failed: {str(e)}")
                        results[symbol] = failed_result
                        
            except TimeoutError:
                logger.error(f"Batch analysis timeout after {self.batch_timeout_seconds}s")
                
                # Annuler futures restantes
                for future in future_to_symbol:
                    if not future.done():
                        future.cancel()
            
            logger.info(f"Parallel analysis completed: {len(results)}/{len(symbols)} symbols")
            
            return results
            
        except Exception as e:
            logger.error(f"Parallel analysis failed: {e}")
            return {}
    
    def _get_cached_analysis(self, symbol: str, market_data: Dict[str, Any]) -> Optional[AnalysisResult]:
        """Récupère analyse depuis le cache si valide"""
        try:
            cache_key = f"{symbol}_{hash(str(market_data.get('timestamp', '')))}_{hash(str(market_data.get('current_price', 0)))}"
            
            if cache_key in self._analysis_cache:
                cache_entry = self._analysis_cache[cache_key]
                age_seconds = (datetime.utcnow() - cache_entry['timestamp']).total_seconds()
                
                if age_seconds <= self._cache_ttl_seconds:
                    logger.debug(f"Using cached analysis for {symbol} (age: {age_seconds:.1f}s)")
                    return cache_entry['result']
                else:
                    # Supprimer entrée expirée
                    del self._analysis_cache[cache_key]
            
            return None
            
        except Exception as e:
            logger.error(f"Cache retrieval failed for {symbol}: {e}")
            return None
    
    def _update_analysis_cache(self, new_results: Dict[str, AnalysisResult]):
        """Met à jour le cache avec nouveaux résultats"""
        try:
            current_time = datetime.utcnow()
            
            for symbol, result in new_results.items():
                # Clé basée sur symbole et données (approximation)
                cache_key = f"{symbol}_{current_time.timestamp()}"
                
                self._analysis_cache[cache_key] = {
                    'result': result,
                    'timestamp': current_time
                }
            
            # Nettoyage cache si trop grand
            if len(self._analysis_cache) > 200:
                self._cleanup_cache()
                
        except Exception as e:
            logger.error(f"Cache update failed: {e}")
    
    def _cleanup_cache(self):
        """Nettoie le cache des analyses expirées"""
        try:
            current_time = datetime.utcnow()
            expired_keys = []
            
            for cache_key, cache_entry in self._analysis_cache.items():
                age_seconds = (current_time - cache_entry['timestamp']).total_seconds()
                if age_seconds > self._cache_ttl_seconds:
                    expired_keys.append(cache_key)
            
            for key in expired_keys:
                del self._analysis_cache[key]
            
            logger.debug(f"Cleaned {len(expired_keys)} expired cache entries")
            
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
    
    def get_orchestrator_stats(self) -> Dict[str, Any]:
        """Retourne statistiques de l'orchestrateur"""
        with self._stats_lock:
            success_rate = 0.0
            if self.total_orchestrations > 0:
                success_rate = self.successful_orchestrations / self.total_orchestrations
            
            avg_symbols_per_orchestration = 0.0
            if self.total_orchestrations > 0:
                avg_symbols_per_orchestration = self.total_symbols_analyzed / self.total_orchestrations
            
            opportunity_rate = 0.0
            if self.total_symbols_analyzed > 0:
                opportunity_rate = self.total_opportunities_found / self.total_symbols_analyzed
            
            return {
                'total_orchestrations': self.total_orchestrations,
                'successful_orchestrations': self.successful_orchestrations,
                'failed_orchestrations': self.failed_orchestrations,
                'success_rate': success_rate,
                'total_symbols_analyzed': self.total_symbols_analyzed,
                'total_opportunities_found': self.total_opportunities_found,
                'opportunity_rate': opportunity_rate,
                'average_symbols_per_orchestration': avg_symbols_per_orchestration,
                'cache_size': len(self._analysis_cache),
                'max_workers': self.max_workers,
                'analysis_timeout_seconds': self.analysis_timeout_seconds,
                'batch_timeout_seconds': self.batch_timeout_seconds
            }
    
    def clear_cache(self):
        """Vide le cache d'analyse"""
        self._analysis_cache.clear()
        logger.info("Analysis cache cleared")
    
    def shutdown(self):
        """Arrêt propre de l'orchestrateur"""
        try:
            self.executor.shutdown(wait=True)
            self.clear_cache()
            logger.info("TestableAnalysisOrchestrator shutdown completed")
        except Exception as e:
            logger.error(f"Orchestrator shutdown failed: {e}")
    
    def __del__(self):
        """Destructeur pour nettoyage automatique"""
        try:
            self.shutdown()
        except Exception:
            pass  # Ignorer erreurs pendant destruction
