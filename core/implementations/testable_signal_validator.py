"""
TestableSignalValidator - Trade Cursor v7.0
Validation découplée et testable des signaux d'analyse technique
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from ..interfaces.analyzer_interfaces import (
    ISignalValidator, SignalResult, SignalType, SignalStrength,
    TechnicalIndicators, MarketContext, ValidationUtils, AnalyzerConfig
)

logger = logging.getLogger(__name__)


class TestableSignalValidator(ISignalValidator):
    """
    Validateur de signaux découplé et testable
    
    Responsabilités:
    - Validation de la qualité des signaux
    - Vérification cohérence entre signaux
    - Validation conditions de marché
    - Métriques de qualité et confiance
    """
    
    def __init__(self, config: AnalyzerConfig):
        self.config = config
        
        # Compteurs de validation
        self.total_validations = 0
        self.passed_validations = 0
        self.failed_validations = 0
        
        # Seuils de validation
        self.min_confidence_threshold = config.min_signal_confidence
        self.quality_thresholds = {
            'excellent': 0.9,
            'good': 0.7,
            'acceptable': 0.6,
            'poor': 0.4
        }
        
        logger.info(f"✅ TestableSignalValidator initialisé (min_confidence: {self.min_confidence_threshold})")
    
    def validate_signal(self, signal: SignalResult, market_context: MarketContext) -> bool:
        """Valide un signal généré"""
        try:
            self.total_validations += 1
            
            # Validations de base
            if not self._validate_signal_structure(signal):
                logger.debug(f"❌ Signal structure invalid for {market_context.symbol}")
                self.failed_validations += 1
                return False
            
            # Validation confiance minimum
            if signal.confidence < self.min_confidence_threshold:
                logger.debug(f"❌ Signal confidence too low: {signal.confidence:.3f} < {self.min_confidence_threshold}")
                self.failed_validations += 1
                return False
            
            # Validation prix cohérents
            if not self._validate_price_levels(signal, market_context):
                logger.debug(f"❌ Invalid price levels for {market_context.symbol}")
                self.failed_validations += 1
                return False
            
            # Validation timing
            if not self._validate_signal_timing(signal):
                logger.debug(f"❌ Signal timing invalid for {market_context.symbol}")
                self.failed_validations += 1
                return False
            
            # Validation conditions marché
            if not self._validate_market_suitability(signal, market_context):
                logger.debug(f"❌ Market conditions unsuitable for {market_context.symbol}")
                self.failed_validations += 1
                return False
            
            self.passed_validations += 1
            logger.debug(f"✅ Signal validated for {market_context.symbol} ({signal.signal_type.value}, conf: {signal.confidence:.3f})")
            return True
            
        except Exception as e:
            logger.error(f"Signal validation error: {e}")
            self.failed_validations += 1
            return False
    
    def validate_signal_quality(self, signal: SignalResult, indicators: TechnicalIndicators) -> float:
        """Évalue la qualité d'un signal (0.0 - 1.0)"""
        try:
            quality_score = 0.0
            max_score = 5.0
            
            # 1. Confiance du signal (20%)
            confidence_score = signal.confidence
            quality_score += confidence_score
            
            # 2. Cohérence indicateurs (20%)
            indicators_score = self._evaluate_indicators_consistency(signal, indicators)
            quality_score += indicators_score
            
            # 3. Force du signal (20%)
            strength_score = self._evaluate_signal_strength(signal)
            quality_score += strength_score
            
            # 4. Justification qualité (20%)
            reasoning_score = self._evaluate_reasoning_quality(signal)
            quality_score += reasoning_score
            
            # 5. Métriques techniques (20%)
            technical_score = self._evaluate_technical_metrics(signal, indicators)
            quality_score += technical_score
            
            # Normaliser sur [0, 1]
            normalized_quality = min(1.0, quality_score / max_score)
            
            logger.debug(f"Signal quality: {normalized_quality:.3f} (conf: {confidence_score:.2f}, ind: {indicators_score:.2f}, str: {strength_score:.2f})")
            return normalized_quality
            
        except Exception as e:
            logger.error(f"Quality evaluation error: {e}")
            return 0.5  # Qualité neutre en cas d'erreur
    
    def check_signal_consistency(self, primary: SignalResult, secondary: List[SignalResult]) -> bool:
        """Vérifie la cohérence entre signaux"""
        try:
            if not secondary:
                return True  # Pas de signaux secondaires = cohérent
            
            # Vérifier direction principale
            primary_direction = self._get_signal_direction(primary.signal_type)
            
            conflicting_signals = 0
            supporting_signals = 0
            
            for sec_signal in secondary:
                sec_direction = self._get_signal_direction(sec_signal.signal_type)
                
                if sec_direction == primary_direction:
                    supporting_signals += 1
                elif sec_direction != 'neutral':
                    conflicting_signals += 1
            
            # Au moins 70% des signaux doivent supporter la direction principale
            total_directional = supporting_signals + conflicting_signals
            if total_directional == 0:
                return True  # Tous neutres = cohérent
            
            support_ratio = supporting_signals / total_directional
            is_consistent = support_ratio >= 0.7
            
            logger.debug(f"Signal consistency: {support_ratio:.2f} (support: {supporting_signals}, conflict: {conflicting_signals})")
            return is_consistent
            
        except Exception as e:
            logger.error(f"Consistency check error: {e}")
            return True  # Default: cohérent en cas d'erreur
    
    def validate_market_conditions(self, market_context: MarketContext) -> bool:
        """Valide les conditions de marché pour trading"""
        try:
            # Vérifier données de base
            if not ValidationUtils.is_valid_price(market_context.current_price):
                logger.debug("❌ Invalid current price")
                return False
            
            # Vérifier changement de prix 24h raisonnable
            if market_context.price_change_24h_pct is not None:
                if not ValidationUtils.is_valid_percentage(market_context.price_change_24h_pct):
                    logger.debug(f"❌ Invalid 24h price change: {market_context.price_change_24h_pct}")
                    return False
                
                # Éviter trading pendant volatilité extrême (>±30%)
                if abs(market_context.price_change_24h_pct) > 30:
                    logger.debug(f"❌ Extreme 24h volatility: {market_context.price_change_24h_pct:.1f}%")
                    return False
            
            # Vérifier volume minimum
            if market_context.volume_24h is not None:
                if market_context.volume_24h < self.config.min_volume_threshold:
                    logger.debug(f"❌ Volume too low: {market_context.volume_24h}")
                    return False
            
            # Éviter weekend si configuré
            if self.config.avoid_weekend_trading and market_context.is_weekend:
                logger.debug("❌ Weekend trading disabled")
                return False
            
            # Vérifier régime de volatilité
            if market_context.market_volatility == 'high' and not self.config.allow_high_volatility_trading:
                logger.debug("❌ High volatility trading disabled")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Market conditions validation error: {e}")
            return False
    
    def _validate_signal_structure(self, signal: SignalResult) -> bool:
        """Valide la structure du signal"""
        try:
            # Vérifications de base
            if not isinstance(signal.signal_type, SignalType):
                return False
            
            if not isinstance(signal.strength, SignalStrength):
                return False
            
            if not ValidationUtils.is_valid_confidence(signal.confidence):
                return False
            
            # Vérifier prix si fournis
            if signal.entry_price is not None:
                if not ValidationUtils.is_valid_price(signal.entry_price):
                    return False
            
            if signal.target_price is not None:
                if not ValidationUtils.is_valid_price(signal.target_price):
                    return False
            
            if signal.stop_loss_price is not None:
                if not ValidationUtils.is_valid_price(signal.stop_loss_price):
                    return False
            
            return True
            
        except Exception:
            return False
    
    def _validate_price_levels(self, signal: SignalResult, market_context: MarketContext) -> bool:
        """Valide la cohérence des niveaux de prix"""
        try:
            if not signal.entry_price or not signal.stop_loss_price:
                return True  # Pas de prix = pas de validation nécessaire
            
            current_price = market_context.current_price
            entry_price = signal.entry_price
            sl_price = signal.stop_loss_price
            tp_price = signal.target_price
            
            # Vérifier que entry est proche du prix courant (±5%)
            price_diff_pct = abs(entry_price - current_price) / current_price * 100
            if price_diff_pct > 5.0:
                logger.debug(f"❌ Entry price too far from current: {price_diff_pct:.2f}%")
                return False
            
            # Vérifier logique SL selon direction
            if signal.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]:
                # LONG: SL < entry_price
                if sl_price >= entry_price:
                    logger.debug(f"❌ LONG SL ({sl_price}) >= entry ({entry_price})")
                    return False
                
                # TP > entry_price si fourni
                if tp_price and tp_price <= entry_price:
                    logger.debug(f"❌ LONG TP ({tp_price}) <= entry ({entry_price})")
                    return False
                    
            elif signal.signal_type in [SignalType.SELL, SignalType.STRONG_SELL]:
                # SHORT: SL > entry_price
                if sl_price <= entry_price:
                    logger.debug(f"❌ SHORT SL ({sl_price}) <= entry ({entry_price})")
                    return False
                
                # TP < entry_price si fourni
                if tp_price and tp_price >= entry_price:
                    logger.debug(f"❌ SHORT TP ({tp_price}) >= entry ({entry_price})")
                    return False
            
            # Vérifier distances raisonnables (0.1% - 10%)
            sl_distance_pct = abs(sl_price - entry_price) / entry_price * 100
            if sl_distance_pct < 0.1 or sl_distance_pct > 10.0:
                logger.debug(f"❌ SL distance unreasonable: {sl_distance_pct:.2f}%")
                return False
            
            if tp_price:
                tp_distance_pct = abs(tp_price - entry_price) / entry_price * 100
                if tp_distance_pct < 0.2 or tp_distance_pct > 15.0:
                    logger.debug(f"❌ TP distance unreasonable: {tp_distance_pct:.2f}%")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Price validation error: {e}")
            return False
    
    def _validate_signal_timing(self, signal: SignalResult) -> bool:
        """Valide le timing du signal"""
        try:
            now = datetime.utcnow()
            
            # Signal pas trop vieux (max 5 minutes)
            if signal.generated_at:
                age_seconds = (now - signal.generated_at).total_seconds()
                if age_seconds > 300:  # 5 minutes
                    logger.debug(f"❌ Signal too old: {age_seconds:.0f}s")
                    return False
            
            # Signal pas expiré
            if signal.valid_until:
                if now > signal.valid_until:
                    logger.debug("❌ Signal expired")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Timing validation error: {e}")
            return True  # Default: timing OK
    
    def _validate_market_suitability(self, signal: SignalResult, market_context: MarketContext) -> bool:
        """Valide la pertinence du signal selon le marché"""
        try:
            # Éviter signaux faibles pendant haute volatilité
            if (market_context.market_volatility == 'high' and 
                signal.strength in [SignalStrength.WEAK, SignalStrength.MODERATE]):
                logger.debug("❌ Weak signal during high volatility")
                return False
            
            # Éviter STRONG signals pendant low volatility (peut être faux signal)
            if (market_context.market_volatility == 'low' and 
                signal.strength == SignalStrength.VERY_STRONG and
                signal.confidence < 0.9):
                logger.debug("❌ Very strong signal with low confidence during low volatility")
                return False
            
            # Vérifier cohérence avec trend général
            if (market_context.overall_trend == 'bullish' and 
                signal.signal_type in [SignalType.SELL, SignalType.STRONG_SELL] and
                signal.strength in [SignalStrength.STRONG, SignalStrength.VERY_STRONG]):
                logger.debug("❌ Strong SELL signal during bullish trend")
                return False
            
            if (market_context.overall_trend == 'bearish' and 
                signal.signal_type in [SignalType.BUY, SignalType.STRONG_BUY] and
                signal.strength in [SignalStrength.STRONG, SignalStrength.VERY_STRONG]):
                logger.debug("❌ Strong BUY signal during bearish trend")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Market suitability error: {e}")
            return True  # Default: suitable
    
    def _evaluate_indicators_consistency(self, signal: SignalResult, indicators: TechnicalIndicators) -> float:
        """Évalue la cohérence avec les indicateurs (0-1)"""
        try:
            if not indicators.is_complete():
                return 0.5  # Données incomplètes = score neutre
            
            score = 0.0
            checks = 0
            
            # RSI cohérence
            if indicators.rsi_1m is not None:
                if signal.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]:
                    # BUY signal: RSI devrait être oversold/neutral
                    if indicators.rsi_1m <= 40:
                        score += 1.0
                    elif indicators.rsi_1m <= 60:
                        score += 0.5
                else:
                    # SELL signal: RSI devrait être overbought/neutral  
                    if indicators.rsi_1m >= 60:
                        score += 1.0
                    elif indicators.rsi_1m >= 40:
                        score += 0.5
                checks += 1
            
            # MACD cohérence
            if indicators.macd_1m is not None and indicators.macd_signal_1m is not None:
                macd_bullish = indicators.macd_1m > indicators.macd_signal_1m
                signal_bullish = signal.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]
                
                if macd_bullish == signal_bullish:
                    score += 1.0
                else:
                    score += 0.0
                checks += 1
            
            # EMA trend cohérence
            if indicators.ema_20_1m is not None and indicators.ema_50_1m is not None:
                ema_bullish = indicators.ema_20_1m > indicators.ema_50_1m
                signal_bullish = signal.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]
                
                if ema_bullish == signal_bullish:
                    score += 1.0
                else:
                    score += 0.0
                checks += 1
            
            return score / max(1, checks) if checks > 0 else 0.5
            
        except Exception as e:
            logger.error(f"Indicators consistency error: {e}")
            return 0.5
    
    def _evaluate_signal_strength(self, signal: SignalResult) -> float:
        """Évalue la force du signal (0-1)"""
        strength_scores = {
            SignalStrength.WEAK: 0.2,
            SignalStrength.MODERATE: 0.5,
            SignalStrength.STRONG: 0.8,
            SignalStrength.VERY_STRONG: 1.0
        }
        return strength_scores.get(signal.strength, 0.5)
    
    def _evaluate_reasoning_quality(self, signal: SignalResult) -> float:
        """Évalue la qualité de la justification (0-1)"""
        if not signal.reasoning:
            return 0.3  # Pas de reasoning = score faible
        
        # Score basé sur nombre et qualité des raisons
        num_reasons = len(signal.reasoning)
        if num_reasons >= 3:
            return 1.0
        elif num_reasons == 2:
            return 0.7
        elif num_reasons == 1:
            return 0.4
        else:
            return 0.1
    
    def _evaluate_technical_metrics(self, signal: SignalResult, indicators: TechnicalIndicators) -> float:
        """Évalue les métriques techniques (0-1)"""
        try:
            score = 0.0
            
            # Présence d'indicateurs clés
            if signal.key_indicators:
                score += min(0.5, len(signal.key_indicators) * 0.1)
            
            # ATR pour volatilité
            if indicators.atr_pct_1m is not None:
                # ATR modéré = bon (0.5% - 2.0%)
                if 0.005 <= indicators.atr_pct_1m <= 0.02:
                    score += 0.3
                else:
                    score += 0.1
            
            # Volume si disponible
            if indicators.volume_ratio_1m is not None:
                # Volume élevé = bon (>1.5x moyenne)
                if indicators.volume_ratio_1m >= 1.5:
                    score += 0.2
                else:
                    score += 0.1
            
            return min(1.0, score)
            
        except Exception as e:
            logger.error(f"Technical metrics error: {e}")
            return 0.5
    
    def _get_signal_direction(self, signal_type: SignalType) -> str:
        """Obtient la direction du signal"""
        if signal_type in [SignalType.BUY, SignalType.STRONG_BUY]:
            return 'bullish'
        elif signal_type in [SignalType.SELL, SignalType.STRONG_SELL]:
            return 'bearish'
        else:
            return 'neutral'
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de validation"""
        success_rate = self.passed_validations / max(1, self.total_validations)
        
        return {
            'total_validations': self.total_validations,
            'passed_validations': self.passed_validations,
            'failed_validations': self.failed_validations,
            'success_rate': success_rate,
            'min_confidence_threshold': self.min_confidence_threshold
        }
