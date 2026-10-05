"""
TestableSignalGenerator - Trade Cursor v7.0
Générateur de signaux techniques découplé et testable
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import numpy as np

from ..interfaces.analyzer_interfaces import (
    ISignalGenerator, SignalResult, SignalType, SignalStrength,
    TechnicalIndicators, MarketContext, AnalyzerConfig, ValidationUtils
)

logger = logging.getLogger(__name__)


class TestableSignalGenerator(ISignalGenerator):
    """
    Générateur de signaux techniques découplé et testable
    
    Responsabilités:
    - Génération signaux basée sur indicateurs techniques
    - Calcul de la force et confiance des signaux
    - Justification détaillée des décisions
    - Signaux primaires et secondaires
    """
    
    def __init__(self, config: AnalyzerConfig):
        self.config = config
        
        # Compteurs de performance
        self.signals_generated = 0
        self.primary_signals = 0
        self.secondary_signals = 0
        
        # Seuils de signaux (configurables)
        self.rsi_oversold = config.rsi_oversold
        self.rsi_overbought = config.rsi_overbought
        self.min_confidence = config.min_signal_confidence
        
        logger.info(f"✅ TestableSignalGenerator initialisé (RSI: {self.rsi_oversold}/{self.rsi_overbought})")
    
    def generate_signal(self, indicators: TechnicalIndicators, market_context: MarketContext) -> SignalResult:
        """Génère un signal principal basé sur les indicateurs"""
        try:
            self.signals_generated += 1
            self.primary_signals += 1
            
            # Analyser indicateurs pour direction
            signal_analysis = self._analyze_indicators_for_signal(indicators, market_context)
            
            # Déterminer type de signal
            signal_type = self._determine_signal_type(signal_analysis)
            
            # Calculer force du signal
            signal_strength = self._calculate_signal_strength(signal_analysis, indicators)
            
            # Calculer confiance
            base_confidence = self._calculate_base_confidence(signal_analysis, indicators, market_context)
            
            # Ajuster confiance selon contexte marché
            adjusted_confidence = self._adjust_confidence_for_market(base_confidence, market_context, indicators)
            
            # Calculer niveaux de prix
            entry_price, target_price, stop_loss_price = self._calculate_price_levels(
                signal_type, market_context, indicators
            )
            
            # Générer justifications
            reasoning = self._generate_signal_reasoning(signal_analysis, indicators, market_context)
            
            # Extraire indicateurs clés
            key_indicators = self._extract_key_indicators(indicators, signal_analysis)
            
            # Créer signal result
            signal_result = SignalResult(
                signal_type=signal_type,
                strength=signal_strength,
                confidence=adjusted_confidence,
                entry_price=entry_price,
                target_price=target_price,
                stop_loss_price=stop_loss_price,
                reasoning=reasoning,
                key_indicators=key_indicators,
                generated_at=datetime.utcnow(),
                valid_until=datetime.utcnow() + timedelta(minutes=5)  # Signal valide 5 min
            )
            
            logger.debug(f"Generated signal: {signal_type.value} {signal_strength.value} (conf: {adjusted_confidence:.3f}) for {market_context.symbol}")
            
            return signal_result
            
        except Exception as e:
            logger.error(f"Signal generation error: {e}")
            # Retourner signal neutre en cas d'erreur
            return SignalResult(
                signal_type=SignalType.HOLD,
                strength=SignalStrength.WEAK,
                confidence=0.1,
                reasoning=[f"Signal generation error: {str(e)}"],
                generated_at=datetime.utcnow()
            )
    
    def generate_secondary_signals(self, indicators: TechnicalIndicators, market_context: MarketContext) -> List[SignalResult]:
        """Génère des signaux secondaires"""
        try:
            secondary_signals = []
            self.secondary_signals += len(secondary_signals) if secondary_signals else 0
            
            # Signal basé sur RSI divergence
            rsi_divergence_signal = self._generate_rsi_divergence_signal(indicators, market_context)
            if rsi_divergence_signal:
                secondary_signals.append(rsi_divergence_signal)
            
            # Signal basé sur MACD crossover
            macd_crossover_signal = self._generate_macd_crossover_signal(indicators, market_context)
            if macd_crossover_signal:
                secondary_signals.append(macd_crossover_signal)
            
            # Signal basé sur EMA trend
            ema_trend_signal = self._generate_ema_trend_signal(indicators, market_context)
            if ema_trend_signal:
                secondary_signals.append(ema_trend_signal)
            
            # Signal basé sur volume
            volume_signal = self._generate_volume_confirmation_signal(indicators, market_context)
            if volume_signal:
                secondary_signals.append(volume_signal)
            
            logger.debug(f"Generated {len(secondary_signals)} secondary signals for {market_context.symbol}")
            
            return secondary_signals
            
        except Exception as e:
            logger.error(f"Secondary signals generation error: {e}")
            return []
    
    def calculate_confidence(self, signal: SignalResult, indicators: TechnicalIndicators) -> float:
        """Calcule la confiance dans un signal"""
        try:
            confidence_factors = {
                'base_confidence': signal.confidence,
                'indicators_alignment': 0.0,
                'signal_strength_bonus': 0.0,
                'technical_confirmation': 0.0
            }
            
            # Facteur alignement indicateurs
            if indicators.is_complete():
                alignment_score = self._calculate_indicators_alignment(signal, indicators)
                confidence_factors['indicators_alignment'] = alignment_score * 0.2  # 20% du poids
            
            # Bonus force du signal
            strength_bonus = {
                SignalStrength.WEAK: 0.0,
                SignalStrength.MODERATE: 0.05,
                SignalStrength.STRONG: 0.1,
                SignalStrength.VERY_STRONG: 0.15
            }.get(signal.strength, 0.0)
            confidence_factors['signal_strength_bonus'] = strength_bonus
            
            # Confirmation technique
            technical_conf = self._calculate_technical_confirmation(signal, indicators)
            confidence_factors['technical_confirmation'] = technical_conf * 0.1  # 10% du poids
            
            # Calculer confiance finale
            final_confidence = sum(confidence_factors.values())
            final_confidence = ValidationUtils.normalize_score(final_confidence, 0.0, 1.0)
            
            logger.debug(f"Confidence calculation: {final_confidence:.3f} (factors: {confidence_factors})")
            
            return final_confidence
            
        except Exception as e:
            logger.error(f"Confidence calculation error: {e}")
            return signal.confidence  # Retourner confiance originale
    
    def _analyze_indicators_for_signal(self, indicators: TechnicalIndicators, market_context: MarketContext) -> Dict[str, Any]:
        """Analyse les indicateurs pour déterminer signal"""
        analysis = {
            'rsi_signal': 'neutral',
            'macd_signal': 'neutral', 
            'ema_signal': 'neutral',
            'volume_signal': 'neutral',
            'overall_bias': 'neutral',
            'strength_score': 0.0,
            'confluence_count': 0
        }
        
        bullish_signals = 0
        bearish_signals = 0
        total_signals = 0
        
        # Analyse RSI
        if indicators.rsi_1m is not None:
            total_signals += 1
            if indicators.rsi_1m <= self.rsi_oversold:
                analysis['rsi_signal'] = 'bullish'
                bullish_signals += 1
            elif indicators.rsi_1m >= self.rsi_overbought:
                analysis['rsi_signal'] = 'bearish'
                bearish_signals += 1
            else:
                analysis['rsi_signal'] = 'neutral'
        
        # Analyse MACD
        if indicators.macd_1m is not None and indicators.macd_signal_1m is not None:
            total_signals += 1
            if indicators.macd_1m > indicators.macd_signal_1m:
                analysis['macd_signal'] = 'bullish'
                bullish_signals += 1
            else:
                analysis['macd_signal'] = 'bearish'
                bearish_signals += 1
        
        # Analyse EMA trend
        if indicators.ema_20_1m is not None and indicators.ema_50_1m is not None:
            total_signals += 1
            if indicators.ema_20_1m > indicators.ema_50_1m:
                analysis['ema_signal'] = 'bullish'
                bullish_signals += 1
            else:
                analysis['ema_signal'] = 'bearish'
                bearish_signals += 1
        
        # Analyse volume
        if indicators.volume_ratio_1m is not None:
            total_signals += 1
            if indicators.volume_ratio_1m >= 1.5:  # Volume élevé
                analysis['volume_signal'] = 'confirming'
            else:
                analysis['volume_signal'] = 'weak'
        
        # Déterminer bias général
        if total_signals > 0:
            bullish_ratio = bullish_signals / total_signals
            bearish_ratio = bearish_signals / total_signals
            
            if bullish_ratio >= 0.6:
                analysis['overall_bias'] = 'bullish'
                analysis['confluence_count'] = bullish_signals
            elif bearish_ratio >= 0.6:
                analysis['overall_bias'] = 'bearish'
                analysis['confluence_count'] = bearish_signals
            else:
                analysis['overall_bias'] = 'neutral'
        
        # Score de force (0-100)
        analysis['strength_score'] = max(bullish_signals, bearish_signals) * 25  # 25 points par signal aligné
        
        return analysis
    
    def _determine_signal_type(self, signal_analysis: Dict[str, Any]) -> SignalType:
        """Détermine le type de signal basé sur l'analyse"""
        bias = signal_analysis.get('overall_bias', 'neutral')
        strength_score = signal_analysis.get('strength_score', 0)
        confluence_count = signal_analysis.get('confluence_count', 0)
        
        if bias == 'bullish':
            if confluence_count >= 3 and strength_score >= 75:
                return SignalType.STRONG_BUY
            else:
                return SignalType.BUY
        elif bias == 'bearish':
            if confluence_count >= 3 and strength_score >= 75:
                return SignalType.STRONG_SELL
            else:
                return SignalType.SELL
        else:
            return SignalType.HOLD
    
    def _calculate_signal_strength(self, signal_analysis: Dict[str, Any], indicators: TechnicalIndicators) -> SignalStrength:
        """Calcule la force du signal"""
        strength_score = signal_analysis.get('strength_score', 0)
        confluence_count = signal_analysis.get('confluence_count', 0)
        
        # Bonus pour indicateurs confirmant
        bonus = 0
        if indicators.volume_ratio_1m and indicators.volume_ratio_1m >= 2.0:
            bonus += 10  # Volume très élevé
        
        if indicators.atr_pct_1m and 0.005 <= indicators.atr_pct_1m <= 0.02:
            bonus += 5  # Volatilité modérée (idéale)
        
        total_strength = strength_score + bonus
        
        # Mapper vers SignalStrength
        if total_strength >= 90 and confluence_count >= 3:
            return SignalStrength.VERY_STRONG
        elif total_strength >= 70 and confluence_count >= 2:
            return SignalStrength.STRONG
        elif total_strength >= 50:
            return SignalStrength.MODERATE
        else:
            return SignalStrength.WEAK
    
    def _calculate_base_confidence(self, signal_analysis: Dict[str, Any], indicators: TechnicalIndicators, market_context: MarketContext) -> float:
        """Calcule confiance de base"""
        base_confidence = 0.5  # Confiance neutre
        
        # Bonus confluence
        confluence_count = signal_analysis.get('confluence_count', 0)
        confluence_bonus = min(0.3, confluence_count * 0.1)  # Max 30% bonus
        
        # Bonus qualité données
        data_quality_bonus = 0.1 if indicators.is_complete() else 0.0
        
        # Bonus contexte marché
        market_bonus = 0.0
        if market_context.market_volatility == 'medium':
            market_bonus = 0.05  # Volatilité idéale
        elif market_context.trading_session in ['european', 'american']:
            market_bonus = 0.03  # Sessions actives
        
        # Pénalité weekend
        weekend_penalty = -0.1 if market_context.is_weekend else 0.0
        
        final_confidence = base_confidence + confluence_bonus + data_quality_bonus + market_bonus + weekend_penalty
        
        return ValidationUtils.normalize_score(final_confidence, 0.0, 1.0)
    
    def _adjust_confidence_for_market(self, base_confidence: float, market_context: MarketContext, indicators: TechnicalIndicators) -> float:
        """Ajuste confiance selon conditions marché"""
        adjusted_confidence = base_confidence
        
        # Ajustement volatilité
        if market_context.market_volatility == 'high':
            adjusted_confidence *= 0.8  # Réduire confiance en haute volatilité
        elif market_context.market_volatility == 'low':
            adjusted_confidence *= 0.9  # Légère réduction en faible volatilité
        
        # Ajustement volume
        if indicators.volume_ratio_1m is not None:
            if indicators.volume_ratio_1m < 1.0:
                adjusted_confidence *= 0.85  # Pénalité volume faible
            elif indicators.volume_ratio_1m >= 2.0:
                adjusted_confidence *= 1.1  # Bonus volume élevé
        
        # Ajustement changement prix 24h
        if market_context.price_change_24h_pct is not None:
            abs_change = abs(market_context.price_change_24h_pct)
            if abs_change > 10:  # Mouvement > 10% en 24h
                adjusted_confidence *= 0.7  # Réduire confiance
        
        return ValidationUtils.normalize_score(adjusted_confidence, 0.0, 1.0)
    
    def _calculate_price_levels(self, signal_type: SignalType, market_context: MarketContext, indicators: TechnicalIndicators) -> tuple:
        """Calcule les niveaux de prix pour le signal"""
        try:
            current_price = market_context.current_price
            
            if signal_type == SignalType.HOLD:
                return None, None, None
            
            # Utiliser ATR pour calculer distances
            atr_pct = indicators.atr_pct_1m or 0.015  # Default 1.5%
            
            # Ajuster selon force du signal
            if signal_type in [SignalType.STRONG_BUY, SignalType.STRONG_SELL]:
                sl_distance = atr_pct * 1.5  # SL plus large pour signaux forts
                tp_distance = atr_pct * 3.0  # TP plus ambitieux
            else:
                sl_distance = atr_pct * 1.0  # SL standard
                tp_distance = atr_pct * 2.0  # TP standard
            
            # Calculer prix selon direction
            entry_price = current_price  # Entry au prix courant
            
            if signal_type in [SignalType.BUY, SignalType.STRONG_BUY]:
                # Position LONG
                stop_loss_price = entry_price * (1 - sl_distance)
                target_price = entry_price * (1 + tp_distance)
            else:
                # Position SHORT
                stop_loss_price = entry_price * (1 + sl_distance)
                target_price = entry_price * (1 - tp_distance)
            
            return (
                round(entry_price, 6),
                round(target_price, 6),
                round(stop_loss_price, 6)
            )
            
        except Exception as e:
            logger.error(f"Price levels calculation error: {e}")
            return None, None, None
    
    def _generate_signal_reasoning(self, signal_analysis: Dict[str, Any], indicators: TechnicalIndicators, market_context: MarketContext) -> List[str]:
        """Génère justifications détaillées du signal"""
        reasoning = []
        
        # Justification RSI
        rsi_signal = signal_analysis.get('rsi_signal')
        if rsi_signal == 'bullish' and indicators.rsi_1m:
            reasoning.append(f"RSI oversold at {indicators.rsi_1m:.1f} suggests potential bounce")
        elif rsi_signal == 'bearish' and indicators.rsi_1m:
            reasoning.append(f"RSI overbought at {indicators.rsi_1m:.1f} suggests potential pullback")
        
        # Justification MACD
        macd_signal = signal_analysis.get('macd_signal')
        if macd_signal == 'bullish' and indicators.macd_1m and indicators.macd_signal_1m:
            reasoning.append(f"MACD bullish crossover ({indicators.macd_1m:.4f} > {indicators.macd_signal_1m:.4f})")
        elif macd_signal == 'bearish' and indicators.macd_1m and indicators.macd_signal_1m:
            reasoning.append(f"MACD bearish crossover ({indicators.macd_1m:.4f} < {indicators.macd_signal_1m:.4f})")
        
        # Justification EMA
        ema_signal = signal_analysis.get('ema_signal')
        if ema_signal == 'bullish' and indicators.ema_20_1m and indicators.ema_50_1m:
            reasoning.append(f"EMA20 above EMA50 confirms uptrend ({indicators.ema_20_1m:.4f} > {indicators.ema_50_1m:.4f})")
        elif ema_signal == 'bearish' and indicators.ema_20_1m and indicators.ema_50_1m:
            reasoning.append(f"EMA20 below EMA50 confirms downtrend ({indicators.ema_20_1m:.4f} < {indicators.ema_50_1m:.4f})")
        
        # Justification volume
        volume_signal = signal_analysis.get('volume_signal')
        if volume_signal == 'confirming' and indicators.volume_ratio_1m:
            reasoning.append(f"High volume confirms move ({indicators.volume_ratio_1m:.1f}x average)")
        elif volume_signal == 'weak' and indicators.volume_ratio_1m:
            reasoning.append(f"Low volume weakens signal ({indicators.volume_ratio_1m:.1f}x average)")
        
        # Confluence
        confluence_count = signal_analysis.get('confluence_count', 0)
        if confluence_count >= 2:
            reasoning.append(f"Strong confluence with {confluence_count} aligned indicators")
        
        # Contexte marché
        if market_context.market_volatility:
            reasoning.append(f"Market volatility: {market_context.market_volatility}")
        
        return reasoning[:5]  # Limiter à 5 raisons max
    
    def _extract_key_indicators(self, indicators: TechnicalIndicators, signal_analysis: Dict[str, Any]) -> Dict[str, float]:
        """Extrait les indicateurs clés du signal"""
        key_indicators = {}
        
        # RSI
        if indicators.rsi_1m is not None:
            key_indicators['rsi_1m'] = indicators.rsi_1m
        if indicators.rsi_5m is not None:
            key_indicators['rsi_5m'] = indicators.rsi_5m
        
        # MACD
        if indicators.macd_1m is not None:
            key_indicators['macd_1m'] = indicators.macd_1m
        if indicators.macd_signal_1m is not None:
            key_indicators['macd_signal_1m'] = indicators.macd_signal_1m
        
        # EMA
        if indicators.ema_20_1m is not None and indicators.ema_50_1m is not None:
            key_indicators['ema_spread_1m'] = indicators.ema_20_1m - indicators.ema_50_1m
        
        # Volume
        if indicators.volume_ratio_1m is not None:
            key_indicators['volume_ratio_1m'] = indicators.volume_ratio_1m
        
        # ATR
        if indicators.atr_pct_1m is not None:
            key_indicators['atr_pct_1m'] = indicators.atr_pct_1m
        
        # Score de force
        strength_score = signal_analysis.get('strength_score', 0)
        key_indicators['signal_strength_score'] = strength_score
        
        return key_indicators
    
    def _generate_rsi_divergence_signal(self, indicators: TechnicalIndicators, market_context: MarketContext) -> Optional[SignalResult]:
        """Génère signal basé sur divergence RSI"""
        # Implémentation simplifiée - nécessiterait historique des prix
        return None
    
    def _generate_macd_crossover_signal(self, indicators: TechnicalIndicators, market_context: MarketContext) -> Optional[SignalResult]:
        """Génère signal basé sur crossover MACD"""
        if not indicators.macd_1m or not indicators.macd_signal_1m:
            return None
        
        # Détecter crossover récent (approximation)
        macd_diff = indicators.macd_1m - indicators.macd_signal_1m
        
        if abs(macd_diff) < 0.001:  # Crossover proche
            signal_type = SignalType.BUY if macd_diff > 0 else SignalType.SELL
            
            return SignalResult(
                signal_type=signal_type,
                strength=SignalStrength.MODERATE,
                confidence=0.6,
                reasoning=[f"MACD crossover detected (diff: {macd_diff:.4f})"],
                key_indicators={'macd_crossover_diff': macd_diff},
                generated_at=datetime.utcnow()
            )
        
        return None
    
    def _generate_ema_trend_signal(self, indicators: TechnicalIndicators, market_context: MarketContext) -> Optional[SignalResult]:
        """Génère signal basé sur trend EMA"""
        if not indicators.ema_20_1m or not indicators.ema_50_1m or not indicators.ema_200_1m:
            return None
        
        # Vérifier alignement EMAs
        bullish_alignment = (indicators.ema_20_1m > indicators.ema_50_1m > indicators.ema_200_1m)
        bearish_alignment = (indicators.ema_20_1m < indicators.ema_50_1m < indicators.ema_200_1m)
        
        if bullish_alignment:
            return SignalResult(
                signal_type=SignalType.BUY,
                strength=SignalStrength.MODERATE,
                confidence=0.7,
                reasoning=["Bullish EMA alignment (20>50>200)"],
                key_indicators={
                    'ema_20_1m': indicators.ema_20_1m,
                    'ema_50_1m': indicators.ema_50_1m,
                    'ema_200_1m': indicators.ema_200_1m
                },
                generated_at=datetime.utcnow()
            )
        elif bearish_alignment:
            return SignalResult(
                signal_type=SignalType.SELL,
                strength=SignalStrength.MODERATE,
                confidence=0.7,
                reasoning=["Bearish EMA alignment (20<50<200)"],
                key_indicators={
                    'ema_20_1m': indicators.ema_20_1m,
                    'ema_50_1m': indicators.ema_50_1m,
                    'ema_200_1m': indicators.ema_200_1m
                },
                generated_at=datetime.utcnow()
            )
        
        return None
    
    def _generate_volume_confirmation_signal(self, indicators: TechnicalIndicators, market_context: MarketContext) -> Optional[SignalResult]:
        """Génère signal basé sur confirmation volume"""
        if not indicators.volume_ratio_1m:
            return None
        
        # Signal si volume exceptionnellement élevé
        if indicators.volume_ratio_1m >= 3.0:  # 3x le volume moyen
            return SignalResult(
                signal_type=SignalType.HOLD,  # Signal de confirmation seulement
                strength=SignalStrength.STRONG,
                confidence=0.8,
                reasoning=[f"Exceptional volume spike ({indicators.volume_ratio_1m:.1f}x average)"],
                key_indicators={'volume_ratio_1m': indicators.volume_ratio_1m},
                generated_at=datetime.utcnow()
            )
        
        return None
    
    def _calculate_indicators_alignment(self, signal: SignalResult, indicators: TechnicalIndicators) -> float:
        """Calcule l'alignement des indicateurs avec le signal"""
        # Implémentation similaire à _analyze_indicators_for_signal
        # mais retourne un score 0-1
        return 0.7  # Placeholder
    
    def _calculate_technical_confirmation(self, signal: SignalResult, indicators: TechnicalIndicators) -> float:
        """Calcule la confirmation technique du signal"""
        # Score basé sur la qualité des indicateurs techniques
        return 0.6  # Placeholder
    
    def get_generation_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de génération"""
        return {
            'total_signals_generated': self.signals_generated,
            'primary_signals': self.primary_signals,
            'secondary_signals': self.secondary_signals,
            'min_confidence_threshold': self.min_confidence
        }
