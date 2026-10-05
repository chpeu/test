"""
TestableScoreCalculator - Trade Cursor v7.0
Calculateur de scores d'analyse découplé et testable
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import numpy as np

from ..interfaces.analyzer_interfaces import (
    IScoreCalculator, TechnicalIndicators, MarketContext, 
    AnalyzerConfig, ValidationUtils
)

logger = logging.getLogger(__name__)


class TestableScoreCalculator(IScoreCalculator):
    """
    Calculateur de scores d'analyse découplé et testable
    
    Responsabilités:
    - Calcul scores basés sur indicateurs 1m et 5m
    - Score combiné avec pondération intelligente
    - Ajustements selon conditions de marché
    - Métriques de qualité et cohérence
    """
    
    def __init__(self, config: AnalyzerConfig):
        self.config = config
        
        # Compteurs de performance
        self.score_calculations = 0
        self.score_adjustments = 0
        
        # Seuils de score
        self.min_score_threshold = config.min_score_threshold
        self.max_score_threshold = config.max_score_threshold
        
        # Poids pour calculs
        self.weights_1m = {
            'rsi': 0.25,
            'macd': 0.30,
            'ema_trend': 0.20,
            'volume': 0.15,
            'volatility': 0.10
        }
        
        self.weights_5m = {
            'rsi': 0.30,
            'macd': 0.25,
            'ema_trend': 0.25,
            'volume': 0.10,
            'volatility': 0.10
        }
        
        logger.info(f"✅ TestableScoreCalculator initialisé (seuils: {self.min_score_threshold}-{self.max_score_threshold})")
    
    def calculate_score_1m(self, indicators: TechnicalIndicators, market_context: MarketContext) -> float:
        """Calcule score basé sur indicateurs 1m"""
        try:
            start_time = datetime.utcnow()
            self.score_calculations += 1
            
            if not indicators.rsi_1m or not indicators.macd_1m:
                logger.debug("Insufficient 1m indicators for score calculation")
                return 0.0
            
            score_components = {
                'rsi_score': 0.0,
                'macd_score': 0.0,
                'ema_score': 0.0,
                'volume_score': 0.0,
                'volatility_score': 0.0
            }
            
            # Score RSI 1m
            score_components['rsi_score'] = self._calculate_rsi_score(
                indicators.rsi_1m, market_context.symbol
            ) * self.weights_1m['rsi']
            
            # Score MACD 1m
            score_components['macd_score'] = self._calculate_macd_score(
                indicators.macd_1m, indicators.macd_signal_1m, indicators.macd_histogram_1m
            ) * self.weights_1m['macd']
            
            # Score EMA trend 1m
            score_components['ema_score'] = self._calculate_ema_trend_score(
                indicators.ema_20_1m, indicators.ema_50_1m, indicators.ema_200_1m
            ) * self.weights_1m['ema_trend']
            
            # Score Volume 1m
            score_components['volume_score'] = self._calculate_volume_score(
                indicators.volume_ratio_1m, indicators.volume_sma_1m
            ) * self.weights_1m['volume']
            
            # Score Volatilité 1m
            score_components['volatility_score'] = self._calculate_volatility_score(
                indicators.atr_pct_1m, market_context
            ) * self.weights_1m['volatility']
            
            # Score total (base 0-10)
            raw_score = sum(score_components.values())
            normalized_score = ValidationUtils.normalize_score(raw_score, 0.0, 10.0)
            
            # Ajustements qualité données
            data_quality_multiplier = self._calculate_data_quality_multiplier(indicators, '1m')
            final_score = normalized_score * data_quality_multiplier
            
            logger.debug(f"Score 1m pour {market_context.symbol}: {final_score:.2f} (components: {score_components})")
            
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.debug(f"Score 1m calculation time: {processing_time:.1f}ms")
            
            return round(final_score, 2)
            
        except Exception as e:
            logger.error(f"Score 1m calculation error: {e}")
            return 0.0
    
    def calculate_score_5m(self, indicators: TechnicalIndicators, market_context: MarketContext) -> float:
        """Calcule score basé sur indicateurs 5m"""
        try:
            start_time = datetime.utcnow()
            self.score_calculations += 1
            
            if not indicators.rsi_5m or not indicators.macd_5m:
                logger.debug("Insufficient 5m indicators for score calculation")
                return 0.0
            
            score_components = {
                'rsi_score': 0.0,
                'macd_score': 0.0,
                'ema_score': 0.0,
                'volume_score': 0.0,
                'volatility_score': 0.0
            }
            
            # Score RSI 5m (poids plus élevé pour timeframe plus long)
            score_components['rsi_score'] = self._calculate_rsi_score(
                indicators.rsi_5m, market_context.symbol
            ) * self.weights_5m['rsi']
            
            # Score MACD 5m
            score_components['macd_score'] = self._calculate_macd_score(
                indicators.macd_5m, indicators.macd_signal_5m, None
            ) * self.weights_5m['macd']
            
            # Score EMA trend 5m
            score_components['ema_score'] = self._calculate_ema_trend_score(
                indicators.ema_20_5m, indicators.ema_50_5m, None
            ) * self.weights_5m['ema_trend']
            
            # Score Volume (utilise données 1m si 5m pas disponible)
            score_components['volume_score'] = self._calculate_volume_score(
                indicators.volume_ratio_1m, indicators.volume_sma_1m
            ) * self.weights_5m['volume']
            
            # Score Volatilité 5m
            score_components['volatility_score'] = self._calculate_volatility_score(
                indicators.atr_pct_5m or indicators.atr_pct_1m, market_context
            ) * self.weights_5m['volatility']
            
            # Score total
            raw_score = sum(score_components.values())
            normalized_score = ValidationUtils.normalize_score(raw_score, 0.0, 10.0)
            
            # Ajustements qualité
            data_quality_multiplier = self._calculate_data_quality_multiplier(indicators, '5m')
            final_score = normalized_score * data_quality_multiplier
            
            logger.debug(f"Score 5m pour {market_context.symbol}: {final_score:.2f} (components: {score_components})")
            
            return round(final_score, 2)
            
        except Exception as e:
            logger.error(f"Score 5m calculation error: {e}")
            return 0.0
    
    def calculate_combined_score(self, score_1m: float, score_5m: float, market_context: MarketContext) -> float:
        """Calcule score combiné avec pondération"""
        try:
            self.score_calculations += 1
            
            # Pondération par défaut: 60% 1m, 40% 5m
            weight_1m = 0.6
            weight_5m = 0.4
            
            # Ajuster pondération selon contexte
            weight_1m, weight_5m = self._adjust_timeframe_weights(
                score_1m, score_5m, market_context, weight_1m, weight_5m
            )
            
            # Score combiné de base
            combined_score = (score_1m * weight_1m) + (score_5m * weight_5m)
            
            # Bonus confluence si scores alignés
            confluence_bonus = self._calculate_confluence_bonus(score_1m, score_5m)
            
            # Score final
            final_combined_score = combined_score + confluence_bonus
            
            # Normaliser dans les limites configurées
            final_combined_score = ValidationUtils.normalize_score(
                final_combined_score, 0.0, self.max_score_threshold
            )
            
            logger.debug(f"Score combiné pour {market_context.symbol}: {final_combined_score:.2f} "
                        f"(1m: {score_1m:.2f}*{weight_1m:.2f}, 5m: {score_5m:.2f}*{weight_5m:.2f}, "
                        f"confluence: +{confluence_bonus:.2f})")
            
            return round(final_combined_score, 2)
            
        except Exception as e:
            logger.error(f"Combined score calculation error: {e}")
            # Retourner moyenne simple en cas d'erreur
            return round((score_1m + score_5m) / 2, 2)
    
    def adjust_score_for_conditions(self, base_score: float, market_context: MarketContext) -> float:
        """Ajuste le score selon les conditions de marché"""
        try:
            self.score_adjustments += 1
            adjusted_score = base_score
            adjustments = []
            
            # Ajustement volatilité
            if market_context.market_volatility:
                if market_context.market_volatility == 'high':
                    adjusted_score *= 0.8  # Réduire score en haute volatilité
                    adjustments.append("high_volatility: -20%")
                elif market_context.market_volatility == 'low':
                    adjusted_score *= 0.9  # Légère réduction en faible volatilité
                    adjustments.append("low_volatility: -10%")
                else:  # medium
                    adjusted_score *= 1.05  # Légère bonification volatilité idéale
                    adjustments.append("medium_volatility: +5%")
            
            # Ajustement session de trading
            if market_context.trading_session:
                if market_context.trading_session in ['european', 'american']:
                    adjusted_score *= 1.03  # Bonus sessions actives
                    adjustments.append(f"{market_context.trading_session}_session: +3%")
                elif market_context.trading_session == 'asian':
                    adjusted_score *= 0.97  # Légère pénalité session moins active
                    adjustments.append("asian_session: -3%")
                elif market_context.trading_session == 'overlap':
                    adjusted_score *= 1.07  # Bonus overlap sessions
                    adjustments.append("session_overlap: +7%")
            
            # Pénalité weekend
            if market_context.is_weekend:
                adjusted_score *= 0.85  # Pénalité significative weekend
                adjustments.append("weekend: -15%")
            
            # Ajustement changement prix 24h
            if market_context.price_change_24h_pct is not None:
                abs_change = abs(market_context.price_change_24h_pct)
                if abs_change > 15:  # Mouvement très important
                    adjusted_score *= 0.7  # Forte pénalité
                    adjustments.append(f"extreme_24h_move: -30% ({abs_change:.1f}%)")
                elif abs_change > 7:  # Mouvement important
                    adjusted_score *= 0.85  # Pénalité modérée
                    adjustments.append(f"high_24h_move: -15% ({abs_change:.1f}%)")
                elif 2 <= abs_change <= 5:  # Mouvement idéal
                    adjusted_score *= 1.05  # Légère bonification
                    adjustments.append(f"ideal_24h_move: +5% ({abs_change:.1f}%)")
            
            # Ajustement volume 24h
            if market_context.volume_24h is not None:
                if market_context.volume_24h < self.config.min_volume_threshold * 0.5:
                    adjusted_score *= 0.75  # Pénalité volume très faible
                    adjustments.append("very_low_24h_volume: -25%")
                elif market_context.volume_24h >= self.config.min_volume_threshold * 2:
                    adjusted_score *= 1.08  # Bonus volume élevé
                    adjustments.append("high_24h_volume: +8%")
            
            # Ajustement trend général
            if market_context.overall_trend:
                if market_context.overall_trend in ['bullish', 'bearish']:
                    adjusted_score *= 1.05  # Bonus trend défini
                    adjustments.append(f"{market_context.overall_trend}_trend: +5%")
                elif market_context.overall_trend == 'sideways':
                    adjusted_score *= 0.95  # Pénalité légère marché latéral
                    adjustments.append("sideways_trend: -5%")
            
            # Limiter ajustements extrêmes (max ±50% du score original)
            min_adjusted = base_score * 0.5
            max_adjusted = base_score * 1.5
            final_score = max(min_adjusted, min(max_adjusted, adjusted_score))
            
            # S'assurer de rester dans les limites globales
            final_score = ValidationUtils.normalize_score(final_score, 0.0, self.max_score_threshold)
            
            if adjustments:
                logger.debug(f"Score adjusted for {market_context.symbol}: {base_score:.2f} → {final_score:.2f} "
                           f"(adjustments: {', '.join(adjustments)})")
            
            return round(final_score, 2)
            
        except Exception as e:
            logger.error(f"Score adjustment error: {e}")
            return base_score
    
    def _calculate_rsi_score(self, rsi: Optional[float], symbol: str) -> float:
        """Calcule score basé sur RSI (0-10)"""
        try:
            if not ValidationUtils.is_valid_rsi(rsi):
                return 0.0
            
            # Courbe de score RSI optimisée
            if rsi <= 25:
                # RSI très oversold = score élevé
                return 9.0 + (25 - rsi) * 0.04  # Max 10.0 pour RSI=0
            elif rsi <= 35:
                # RSI oversold = bon score
                return 7.0 + (35 - rsi) * 0.2  # 7.0-9.0
            elif rsi <= 45:
                # RSI légèrement oversold = score correct
                return 5.0 + (45 - rsi) * 0.2  # 5.0-7.0
            elif rsi <= 55:
                # RSI neutre = score moyen
                return 3.0 + (10 - abs(rsi - 50)) * 0.2  # 3.0-5.0 (peak à RSI=50)
            elif rsi <= 65:
                # RSI légèrement overbought = score correct
                return 2.0 + (65 - rsi) * 0.1  # 2.0-3.0
            elif rsi <= 75:
                # RSI overbought = score faible (pour LONG)
                return 0.5 + (75 - rsi) * 0.15  # 0.5-2.0
            else:
                # RSI très overbought = score très faible
                return max(0.1, 0.5 - (rsi - 75) * 0.02)  # Min 0.1
            
        except Exception as e:
            logger.error(f"RSI score calculation error: {e}")
            return 0.0
    
    def _calculate_macd_score(self, macd: Optional[float], macd_signal: Optional[float], macd_histogram: Optional[float]) -> float:
        """Calcule score basé sur MACD (0-10)"""
        try:
            if macd is None:
                return 0.0
            
            score = 0.0
            
            # Score basé sur MACD vs Signal
            if macd_signal is not None:
                macd_diff = macd - macd_signal
                
                if macd_diff > 0:
                    # MACD au-dessus signal = bullish
                    score += min(5.0, abs(macd_diff) * 10000)  # Normaliser selon magnitude
                else:
                    # MACD sous signal = bearish (score faible pour LONG)
                    score += max(0.0, 1.0 - abs(macd_diff) * 10000)
            else:
                # Pas de signal, utiliser MACD seul
                if macd > 0:
                    score += min(3.0, macd * 5000)
                else:
                    score += max(0.0, 1.0 + macd * 5000)
            
            # Bonus histogramme si disponible
            if macd_histogram is not None:
                if macd_histogram > 0:
                    # Histogramme positif = momentum haussier
                    histogram_bonus = min(2.0, macd_histogram * 8000)
                    score += histogram_bonus
                else:
                    # Histogramme négatif = momentum baissier
                    histogram_penalty = min(1.0, abs(macd_histogram) * 8000)
                    score = max(0.0, score - histogram_penalty)
            
            return min(10.0, score)
            
        except Exception as e:
            logger.error(f"MACD score calculation error: {e}")
            return 0.0
    
    def _calculate_ema_trend_score(self, ema_20: Optional[float], ema_50: Optional[float], ema_200: Optional[float]) -> float:
        """Calcule score basé sur trend EMA (0-10)"""
        try:
            score = 0.0
            
            # Score EMA 20 vs EMA 50
            if ema_20 is not None and ema_50 is not None:
                if ema_20 > ema_50:
                    # Trend haussier court terme
                    ema_diff_pct = (ema_20 - ema_50) / ema_50 * 100
                    score += min(4.0, ema_diff_pct * 20)  # Max 4 points
                else:
                    # Trend baissier court terme
                    ema_diff_pct = (ema_50 - ema_20) / ema_50 * 100
                    score += max(0.0, 1.0 - ema_diff_pct * 20)
            
            # Bonus EMA 50 vs EMA 200 si disponible
            if ema_50 is not None and ema_200 is not None:
                if ema_50 > ema_200:
                    # Trend haussier long terme
                    long_ema_diff_pct = (ema_50 - ema_200) / ema_200 * 100
                    long_term_bonus = min(3.0, long_ema_diff_pct * 15)
                    score += long_term_bonus
                else:
                    # Trend baissier long terme
                    score *= 0.7  # Pénalité trend baissier long terme
            
            # Bonus alignement parfait
            if (ema_20 is not None and ema_50 is not None and ema_200 is not None and
                ema_20 > ema_50 > ema_200):
                score += 2.0  # Bonus alignement bullish parfait
            
            return min(10.0, score)
            
        except Exception as e:
            logger.error(f"EMA trend score calculation error: {e}")
            return 0.0
    
    def _calculate_volume_score(self, volume_ratio: Optional[float], volume_sma: Optional[float]) -> float:
        """Calcule score basé sur volume (0-10)"""
        try:
            if volume_ratio is None:
                return 5.0  # Score neutre si pas de données volume
            
            # Courbe volume optimisée
            if volume_ratio >= 3.0:
                # Volume exceptionnel
                return min(10.0, 7.0 + (volume_ratio - 3.0) * 0.5)
            elif volume_ratio >= 2.0:
                # Volume très élevé
                return 6.0 + (volume_ratio - 2.0) * 1.0  # 6.0-7.0
            elif volume_ratio >= 1.5:
                # Volume élevé
                return 5.0 + (volume_ratio - 1.5) * 2.0  # 5.0-6.0
            elif volume_ratio >= 1.0:
                # Volume normal à élevé
                return 3.0 + (volume_ratio - 1.0) * 4.0  # 3.0-5.0
            elif volume_ratio >= 0.7:
                # Volume légèrement faible
                return 1.0 + (volume_ratio - 0.7) * 6.67  # 1.0-3.0
            else:
                # Volume très faible
                return max(0.0, volume_ratio * 1.43)  # 0.0-1.0
            
        except Exception as e:
            logger.error(f"Volume score calculation error: {e}")
            return 5.0
    
    def _calculate_volatility_score(self, atr_pct: Optional[float], market_context: MarketContext) -> float:
        """Calcule score basé sur volatilité (0-10)"""
        try:
            if atr_pct is None:
                return 5.0  # Score neutre
            
            # Volatilité idéale: 0.5% - 2.0%
            if 0.005 <= atr_pct <= 0.02:
                # Volatilité optimale
                return 8.0 + (1 - abs(atr_pct - 0.0125) / 0.0075) * 2.0  # 8.0-10.0
            elif 0.002 <= atr_pct < 0.005:
                # Volatilité faible mais acceptable
                return 5.0 + (atr_pct - 0.002) / 0.003 * 3.0  # 5.0-8.0
            elif 0.02 < atr_pct <= 0.05:
                # Volatilité élevée mais gérable
                return 6.0 - (atr_pct - 0.02) / 0.03 * 4.0  # 2.0-6.0
            elif atr_pct > 0.05:
                # Volatilité excessive
                return max(0.5, 2.0 - (atr_pct - 0.05) * 10)  # Décroissance rapide
            else:
                # Volatilité trop faible (< 0.2%)
                return max(1.0, atr_pct * 2500)  # Score très faible
            
        except Exception as e:
            logger.error(f"Volatility score calculation error: {e}")
            return 5.0
    
    def _calculate_data_quality_multiplier(self, indicators: TechnicalIndicators, timeframe: str) -> float:
        """Calcule multiplicateur qualité données"""
        try:
            quality_score = 1.0
            
            # Vérifier complétude indicateurs essentiels
            essential_1m = [indicators.rsi_1m, indicators.macd_1m, indicators.ema_20_1m]
            essential_5m = [indicators.rsi_5m, indicators.macd_5m, indicators.ema_20_5m]
            
            if timeframe == '1m':
                missing_count = sum(1 for ind in essential_1m if ind is None)
                quality_score *= max(0.5, 1.0 - (missing_count * 0.15))
            else:  # 5m
                missing_count = sum(1 for ind in essential_5m if ind is None)
                quality_score *= max(0.5, 1.0 - (missing_count * 0.15))
            
            # Bonus indicateurs additionnels
            if indicators.volume_ratio_1m is not None:
                quality_score *= 1.05
            if indicators.atr_pct_1m is not None:
                quality_score *= 1.03
            
            return min(1.2, quality_score)  # Max 20% bonus
            
        except Exception:
            return 0.8  # Pénalité par défaut
    
    def _adjust_timeframe_weights(self, score_1m: float, score_5m: float, market_context: MarketContext, 
                                 weight_1m: float, weight_5m: float) -> tuple:
        """Ajuste pondération timeframes selon contexte"""
        try:
            # Ajustement selon volatilité
            if market_context.market_volatility == 'high':
                # Privilégier 5m en haute volatilité
                weight_1m *= 0.8
                weight_5m *= 1.2
            elif market_context.market_volatility == 'low':
                # Privilégier 1m en faible volatilité
                weight_1m *= 1.1
                weight_5m *= 0.9
            
            # Ajustement selon écart de scores
            score_diff = abs(score_1m - score_5m)
            if score_diff > 3.0:
                # Écart important = privilégier score le plus élevé
                if score_1m > score_5m:
                    weight_1m *= 1.2
                    weight_5m *= 0.8
                else:
                    weight_1m *= 0.8
                    weight_5m *= 1.2
            
            # Normaliser pour que la somme = 1.0
            total_weight = weight_1m + weight_5m
            if total_weight > 0:
                weight_1m /= total_weight
                weight_5m /= total_weight
            
            return round(weight_1m, 3), round(weight_5m, 3)
            
        except Exception as e:
            logger.error(f"Weight adjustment error: {e}")
            return 0.6, 0.4  # Retourner poids par défaut
    
    def _calculate_confluence_bonus(self, score_1m: float, score_5m: float) -> float:
        """Calcule bonus confluence entre timeframes"""
        try:
            # Bonus si scores alignés
            score_diff = abs(score_1m - score_5m)
            
            if score_diff <= 1.0:
                # Scores très proches
                avg_score = (score_1m + score_5m) / 2
                if avg_score >= 7.0:
                    return 1.0  # Bonus fort pour scores élevés alignés
                elif avg_score >= 5.0:
                    return 0.5  # Bonus modéré
                else:
                    return 0.2  # Petit bonus
            elif score_diff <= 2.0:
                # Scores modérément proches
                return 0.3
            else:
                # Scores divergents = pas de bonus
                return 0.0
                
        except Exception:
            return 0.0
    
    def get_calculation_stats(self) -> Dict[str, Any]:
        """Retourne statistiques de calcul"""
        return {
            'total_score_calculations': self.score_calculations,
            'total_score_adjustments': self.score_adjustments,
            'min_score_threshold': self.min_score_threshold,
            'max_score_threshold': self.max_score_threshold,
            'weights_1m': self.weights_1m,
            'weights_5m': self.weights_5m
        }
