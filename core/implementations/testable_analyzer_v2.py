"""
TestableAnalyzerV2 - Trade Cursor v7.0  
Analyzer technique utilisant les nouvelles interfaces découplées
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import asyncio

from ..interfaces.analyzer_interfaces import (
    IAnalyzer, IIndicatorCalculator, ISignalGenerator, IScoreCalculator,
    AnalysisResult, TechnicalIndicators, MarketContext, SignalResult,
    AnalysisStatus, AnalyzerConfig
)

logger = logging.getLogger(__name__)


class TestableAnalyzerV2(IAnalyzer):
    """
    Analyzer technique V2 utilisant les interfaces découplées
    
    Caractéristiques:
    - Injection de dépendances pour tous composants
    - Logique d'analyse complètement découplée
    - Parallélisation des calculs
    - Métriques et monitoring détaillés
    - Mode batch pour performance
    """
    
    def __init__(self,
                 config: AnalyzerConfig,
                 indicator_calculator: IIndicatorCalculator,
                 signal_generator: ISignalGenerator,
                 score_calculator: IScoreCalculator):
        
        self.config = config
        
        # Composants injectés
        self.indicator_calculator = indicator_calculator
        self.signal_generator = signal_generator
        self.score_calculator = score_calculator
        
        # Métriques de performance
        self.analysis_count = 0
        self.success_count = 0
        self.error_count = 0
        self.total_processing_time_ms = 0.0
        self.average_processing_time_ms = 0.0
        
        # Cache pour optimisation
        self._indicator_cache = {}
        self._cache_max_age_seconds = 30
        
        logger.info(f"✅ TestableAnalyzerV2 initialisé avec composants injectés")
    
    def analyze_pair(self, symbol: str, market_data: Dict[str, Any]) -> AnalysisResult:
        """Analyse complète d'une paire"""
        start_time = datetime.utcnow()
        
        try:
            self.analysis_count += 1
            
            # Valider données d'entrée
            data_quality = self.validate_data_quality(market_data)
            if data_quality < self.config.min_data_quality:
                return self._create_failed_result(
                    symbol, f"Data quality insufficient: {data_quality:.2f}", 
                    AnalysisStatus.INSUFFICIENT_DATA
                )
            
            # Créer contexte marché
            market_context = self._create_market_context(symbol, market_data)
            
            # Calculer indicateurs techniques
            indicators = self._calculate_indicators_with_cache(symbol, market_data)
            if not indicators.is_complete():
                return self._create_failed_result(
                    symbol, "Incomplete technical indicators",
                    AnalysisStatus.INSUFFICIENT_DATA
                )
            
            # Calculer scores
            score_1m = self.score_calculator.calculate_score_1m(indicators, market_context)
            score_5m = self.score_calculator.calculate_score_5m(indicators, market_context)
            combined_score = self.score_calculator.calculate_combined_score(
                score_1m, score_5m, market_context
            )
            
            # Ajuster score selon conditions
            final_score = self.score_calculator.adjust_score_for_conditions(
                combined_score, market_context
            )
            
            # Vérifier si score minimum atteint
            if final_score < self.config.min_score_threshold:
                return self._create_failed_result(
                    symbol, f"Score below threshold: {final_score:.2f} < {self.config.min_score_threshold}",
                    AnalysisStatus.FAILED,
                    score_1m=score_1m, score_5m=score_5m, combined_score=final_score,
                    indicators=indicators, market_context=market_context
                )
            
            # Générer signaux
            primary_signal = self.signal_generator.generate_signal(indicators, market_context)
            secondary_signals = self.signal_generator.generate_secondary_signals(indicators, market_context)
            
            # Créer résultat de succès
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            result = AnalysisResult(
                symbol=symbol,
                status=AnalysisStatus.SUCCESS,
                primary_signal=primary_signal,
                secondary_signals=secondary_signals,
                score_1m=score_1m,
                score_5m=score_5m,
                combined_score=final_score,
                indicators=indicators,
                market_context=market_context,
                data_quality_score=data_quality,
                processing_time_ms=processing_time,
                timestamp=datetime.utcnow()
            )
            
            self.success_count += 1
            self._update_performance_metrics(processing_time)
            
            logger.debug(f"✅ Analysis successful for {symbol}: score={final_score:.2f}, "
                        f"signal={primary_signal.signal_type.value if primary_signal else 'None'}")
            
            return result
            
        except Exception as e:
            self.error_count += 1
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._update_performance_metrics(processing_time)
            
            logger.error(f"❌ Analysis failed for {symbol}: {e}")
            
            return self._create_failed_result(
                symbol, f"Analysis error: {str(e)}", AnalysisStatus.FAILED
            )
    
    def batch_analyze(self, symbols: List[str], market_data: Dict[str, Dict[str, Any]]) -> Dict[str, AnalysisResult]:
        """Analyse en batch de plusieurs paires"""
        try:
            start_time = datetime.utcnow()
            results = {}
            
            logger.info(f"🔄 Starting batch analysis for {len(symbols)} symbols")
            
            # Mode séquentiel pour éviter surcharge
            for symbol in symbols:
                symbol_data = market_data.get(symbol, {})
                if not symbol_data:
                    results[symbol] = self._create_failed_result(
                        symbol, "No market data provided", AnalysisStatus.INSUFFICIENT_DATA
                    )
                    continue
                
                result = self.analyze_pair(symbol, symbol_data)
                results[symbol] = result
                
                # Pause courte entre analyses
                if len(results) % 10 == 0:
                    logger.debug(f"Processed {len(results)}/{len(symbols)} symbols")
            
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            success_count = sum(1 for r in results.values() if r.is_valid)
            
            logger.info(f"✅ Batch analysis completed: {success_count}/{len(symbols)} successful "
                       f"in {processing_time:.1f}ms")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Batch analysis failed: {e}")
            # Retourner résultats partiels si disponibles
            return results if 'results' in locals() else {}
    
    def quick_score(self, symbol: str, market_data: Dict[str, Any]) -> Tuple[float, float]:
        """Calcul rapide des scores 1m et 5m seulement"""
        try:
            # Validation minimale
            if not market_data:
                return 0.0, 0.0
            
            # Créer contexte marché simplifié
            market_context = self._create_market_context(symbol, market_data)
            
            # Calculer indicateurs (cache si possible)
            indicators = self._calculate_indicators_with_cache(symbol, market_data)
            
            # Calculer scores uniquement
            score_1m = self.score_calculator.calculate_score_1m(indicators, market_context)
            score_5m = self.score_calculator.calculate_score_5m(indicators, market_context)
            
            logger.debug(f"Quick score for {symbol}: 1m={score_1m:.2f}, 5m={score_5m:.2f}")
            
            return score_1m, score_5m
            
        except Exception as e:
            logger.error(f"Quick score failed for {symbol}: {e}")
            return 0.0, 0.0
    
    def validate_data_quality(self, market_data: Dict[str, Any]) -> float:
        """Évalue la qualité des données de marché (0.0 - 1.0)"""
        try:
            quality_score = 0.0
            max_score = 5.0
            
            # 1. Présence OHLCV 1m (20%)
            ohlcv_1m = market_data.get('ohlcv_1m', [])
            if ohlcv_1m and len(ohlcv_1m) >= 100:
                quality_score += 1.0
            elif ohlcv_1m and len(ohlcv_1m) >= 50:
                quality_score += 0.7
            elif ohlcv_1m and len(ohlcv_1m) >= 20:
                quality_score += 0.4
            
            # 2. Présence OHLCV 5m (20%)
            ohlcv_5m = market_data.get('ohlcv_5m', [])
            if ohlcv_5m and len(ohlcv_5m) >= 50:
                quality_score += 1.0
            elif ohlcv_5m and len(ohlcv_5m) >= 20:
                quality_score += 0.7
            elif ohlcv_5m and len(ohlcv_5m) >= 10:
                quality_score += 0.4
            
            # 3. Cohérence des prix (20%)
            if ohlcv_1m:
                try:
                    prices = [float(candle[4]) for candle in ohlcv_1m[-10:]]  # Last 10 closes
                    if all(p > 0 for p in prices):
                        # Vérifier variabilité raisonnable
                        price_std = np.std(prices) if len(prices) > 1 else 0
                        price_mean = np.mean(prices)
                        cv = price_std / price_mean if price_mean > 0 else 0
                        
                        if 0.001 <= cv <= 0.05:  # Coefficient de variation raisonnable
                            quality_score += 1.0
                        elif cv <= 0.1:
                            quality_score += 0.6
                        else:
                            quality_score += 0.3
                    else:
                        quality_score += 0.1
                except Exception:
                    quality_score += 0.1
            
            # 4. Données ticker récentes (20%)
            current_price = market_data.get('current_price')
            if current_price and float(current_price) > 0:
                quality_score += 1.0
            
            # 5. Métadonnées complètes (20%)
            required_fields = ['symbol', 'timestamp']
            present_fields = sum(1 for field in required_fields if field in market_data)
            quality_score += present_fields / len(required_fields)
            
            # Normaliser sur [0, 1]
            normalized_quality = min(1.0, quality_score / max_score)
            
            logger.debug(f"Data quality score: {normalized_quality:.3f}")
            
            return normalized_quality
            
        except Exception as e:
            logger.error(f"Data quality validation failed: {e}")
            return 0.5  # Score neutre en cas d'erreur
    
    def _create_market_context(self, symbol: str, market_data: Dict[str, Any]) -> MarketContext:
        """Crée le contexte de marché à partir des données"""
        try:
            # Prix courant
            current_price = float(market_data.get('current_price', 0))
            if current_price == 0 and market_data.get('ohlcv_1m'):
                # Fallback: dernier close
                current_price = float(market_data['ohlcv_1m'][-1][4])
            
            # Changement 24h
            price_change_24h_pct = market_data.get('price_change_24h_pct')
            if price_change_24h_pct is not None:
                price_change_24h_pct = float(price_change_24h_pct)
            
            # Volume 24h
            volume_24h = market_data.get('volume_24h')
            if volume_24h is not None:
                volume_24h = float(volume_24h)
            
            # Déterminer session de trading (approximation basée sur l'heure UTC)
            now_hour = datetime.utcnow().hour
            trading_session = self._determine_trading_session(now_hour)
            
            # Weekend
            is_weekend = datetime.utcnow().weekday() >= 5
            
            # Volatilité du marché (basée sur ATR si disponible)
            market_volatility = self._determine_market_volatility(market_data)
            
            # Trend général (basé sur changement prix 24h)
            overall_trend = self._determine_overall_trend(price_change_24h_pct)
            
            return MarketContext(
                symbol=symbol,
                current_price=current_price,
                price_change_24h_pct=price_change_24h_pct,
                volume_24h=volume_24h,
                trading_session=trading_session,
                is_weekend=is_weekend,
                market_volatility=market_volatility,
                overall_trend=overall_trend
            )
            
        except Exception as e:
            logger.error(f"Market context creation failed: {e}")
            # Contexte minimal
            return MarketContext(
                symbol=symbol,
                current_price=100.0,  # Fallback
            )
    
    def _calculate_indicators_with_cache(self, symbol: str, market_data: Dict[str, Any]) -> TechnicalIndicators:
        """Calcule les indicateurs avec mise en cache"""
        try:
            # Clé de cache basée sur timestamp des données
            cache_key = f"{symbol}_{hash(str(market_data.get('timestamp', datetime.utcnow().timestamp())))}"
            
            # Vérifier cache
            if cache_key in self._indicator_cache:
                cache_entry = self._indicator_cache[cache_key]
                age_seconds = (datetime.utcnow() - cache_entry['timestamp']).total_seconds()
                
                if age_seconds <= self._cache_max_age_seconds:
                    logger.debug(f"Using cached indicators for {symbol} (age: {age_seconds:.1f}s)")
                    return cache_entry['indicators']
                else:
                    # Supprimer entrée expirée
                    del self._indicator_cache[cache_key]
            
            # Calculer indicateurs
            indicators = self.indicator_calculator.calculate_all_indicators(market_data)
            
            # Mettre en cache
            self._indicator_cache[cache_key] = {
                'indicators': indicators,
                'timestamp': datetime.utcnow()
            }
            
            # Nettoyage cache si trop grand
            if len(self._indicator_cache) > 100:
                self._cleanup_cache()
            
            return indicators
            
        except Exception as e:
            logger.error(f"Indicator calculation with cache failed: {e}")
            return TechnicalIndicators()
    
    def _determine_trading_session(self, hour_utc: int) -> str:
        """Détermine la session de trading basée sur l'heure UTC"""
        if 0 <= hour_utc < 8:
            return 'asian'
        elif 8 <= hour_utc < 16:
            return 'european'
        elif 16 <= hour_utc < 22:
            return 'american'
        else:  # 22-24
            return 'overlap'  # Début session asiatique
    
    def _determine_market_volatility(self, market_data: Dict[str, Any]) -> str:
        """Détermine le niveau de volatilité du marché"""
        try:
            # Méthode 1: ATR percentage si disponible
            if market_data.get('atr_pct_1m'):
                atr_pct = float(market_data['atr_pct_1m'])
                if atr_pct >= 0.03:  # > 3%
                    return 'high'
                elif atr_pct >= 0.01:  # 1-3%
                    return 'medium'
                else:  # < 1%
                    return 'low'
            
            # Méthode 2: Changement prix 24h
            if market_data.get('price_change_24h_pct'):
                change_pct = abs(float(market_data['price_change_24h_pct']))
                if change_pct >= 10:
                    return 'high'
                elif change_pct >= 3:
                    return 'medium'
                else:
                    return 'low'
            
            # Méthode 3: Analyse range prix récent
            if market_data.get('ohlcv_1m'):
                recent_candles = market_data['ohlcv_1m'][-20:]  # 20 dernières bougies
                if len(recent_candles) >= 10:
                    highs = [float(c[2]) for c in recent_candles]
                    lows = [float(c[3]) for c in recent_candles]
                    closes = [float(c[4]) for c in recent_candles]
                    
                    avg_close = sum(closes) / len(closes)
                    range_pct = (max(highs) - min(lows)) / avg_close * 100
                    
                    if range_pct >= 5:
                        return 'high'
                    elif range_pct >= 2:
                        return 'medium'
                    else:
                        return 'low'
            
            return 'medium'  # Défaut
            
        except Exception:
            return 'medium'
    
    def _determine_overall_trend(self, price_change_24h_pct: Optional[float]) -> str:
        """Détermine la tendance générale du marché"""
        if price_change_24h_pct is None:
            return 'sideways'
        
        if price_change_24h_pct >= 2:
            return 'bullish'
        elif price_change_24h_pct <= -2:
            return 'bearish'
        else:
            return 'sideways'
    
    def _create_failed_result(self, symbol: str, reason: str, status: AnalysisStatus, **kwargs) -> AnalysisResult:
        """Crée un résultat d'analyse échoué"""
        result = AnalysisResult(
            symbol=symbol,
            status=status,
            timestamp=datetime.utcnow()
        )
        
        result.errors.append(reason)
        
        # Ajouter kwargs optionnels
        for key, value in kwargs.items():
            if hasattr(result, key):
                setattr(result, key, value)
        
        return result
    
    def _update_performance_metrics(self, processing_time_ms: float):
        """Met à jour les métriques de performance"""
        self.total_processing_time_ms += processing_time_ms
        
        if self.analysis_count > 0:
            self.average_processing_time_ms = self.total_processing_time_ms / self.analysis_count
    
    def _cleanup_cache(self):
        """Nettoie le cache des indicateurs expirés"""
        try:
            now = datetime.utcnow()
            expired_keys = []
            
            for key, entry in self._indicator_cache.items():
                age_seconds = (now - entry['timestamp']).total_seconds()
                if age_seconds > self._cache_max_age_seconds:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._indicator_cache[key]
            
            logger.debug(f"Cleaned {len(expired_keys)} expired cache entries")
            
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de performance"""
        success_rate = 0.0
        if self.analysis_count > 0:
            success_rate = self.success_count / self.analysis_count
        
        return {
            'total_analyses': self.analysis_count,
            'successful_analyses': self.success_count,
            'failed_analyses': self.error_count,
            'success_rate': success_rate,
            'average_processing_time_ms': self.average_processing_time_ms,
            'total_processing_time_ms': self.total_processing_time_ms,
            'cache_size': len(self._indicator_cache),
            'cache_max_age_seconds': self._cache_max_age_seconds
        }
    
    def clear_cache(self):
        """Vide le cache des indicateurs"""
        self._indicator_cache.clear()
        logger.info("Indicator cache cleared")
    
    def get_component_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques des composants injectés"""
        stats = {
            'analyzer_v2': self.get_performance_stats()
        }
        
        # Stats calculateur indicateurs
        if hasattr(self.indicator_calculator, 'get_performance_stats'):
            stats['indicator_calculator'] = self.indicator_calculator.get_performance_stats()
        
        # Stats générateur signaux
        if hasattr(self.signal_generator, 'get_generation_stats'):
            stats['signal_generator'] = self.signal_generator.get_generation_stats()
        
        # Stats calculateur scores
        if hasattr(self.score_calculator, 'get_calculation_stats'):
            stats['score_calculator'] = self.score_calculator.get_calculation_stats()
        
        return stats
