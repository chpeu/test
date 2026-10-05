"""
TestableScalabilityScorer - Trade Cursor v7.0 Phase 3
Calculateur de scores de scalabilité découplé et testable
"""

import logging
import math
from typing import Dict, Any, List, Optional
from datetime import datetime
import numpy as np

from ..interfaces.scanner_interfaces import (
    IScalabilityScorer, MarketData, ScoringResult, ScoringMetrics,
    ScannerValidationUtils
)
from utils.effective_config import get_effective_value

logger = logging.getLogger(__name__)


class TestableScalabilityScorer(IScalabilityScorer):
    """
    Calculateur de scores de scalabilité découplé et testable
    
    Responsabilités:
    - Calcul du score de scalabilité basé sur volatilité/spread
    - Métriques techniques (ATR, volatility, ADX)
    - Order flow metrics avancées
    - Scoring configurable par régime
    - Analytics de rejet avec tracking
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Compteurs de performance
        self.scoring_count = 0
        self.successful_scores = 0
        self.rejected_scores = 0
        self.total_scoring_time_ms = 0.0
        
        # Analytics de rejet
        self.rejection_reasons = {}
        self.last_rejection_reason = None
        
        # Cache des calculs techniques
        self._technical_cache = {}
        self._cache_ttl_seconds = 60
        
        logger.info("✅ TestableScalabilityScorer initialisé")
    
    def calculate_score(self, market_data: MarketData, config: Optional[Dict[str, Any]] = None) -> ScoringResult:
        """Calcule le score de scalabilité pour une paire"""
        try:
            start_time = datetime.utcnow()
            self.scoring_count += 1
            
            # Configuration effective (local override ou globale)
            effective_config = {**self.config, **(config or {})}
            
            # Valider données d'entrée
            validation_errors = ScannerValidationUtils.validate_market_data(market_data)
            if validation_errors:
                return self._create_rejected_result(
                    market_data.symbol, 
                    f"Data validation failed: {', '.join(validation_errors)}",
                    start_time
                )
            
            # Calculer métriques techniques
            metrics = self.calculate_metrics(market_data)
            
            # Récupération paramètres dynamiques du régime
            scoring_params = self._get_effective_scoring_params(market_data.symbol)
            
            # Vérifier filtres de base
            rejection_reason = self._check_basic_filters(market_data, metrics, scoring_params)
            if rejection_reason:
                return self._create_rejected_result(
                    market_data.symbol, rejection_reason, start_time, metrics
                )
            
            # Calculer score de base
            base_score = self._calculate_base_score(market_data, metrics, scoring_params)
            
            # Appliquer bonus et ajustements
            adjusted_score = self._apply_score_adjustments(base_score, metrics, scoring_params)
            
            # Calculer détails de scoring
            scoring_details = self._calculate_scoring_details(market_data, metrics, scoring_params)
            
            # Métriques de performance
            scoring_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self.total_scoring_time_ms += scoring_time
            self.successful_scores += 1
            
            # Créer résultat final
            result = ScoringResult(
                symbol=market_data.symbol,
                score=round(adjusted_score, 2),
                metrics=metrics,
                scoring_details=scoring_details,
                calculation_time_ms=scoring_time,
                timestamp=datetime.utcnow()
            )
            
            logger.debug(f"✅ Scoring successful for {market_data.symbol}: {result.score:.2f} "
                        f"(volatility: {metrics.volatility_5:.2f}%, spread: {market_data.orderbook.spread_pct:.4f}%)")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Scoring failed for {market_data.symbol}: {e}")
            self.rejected_scores += 1
            return self._create_rejected_result(
                market_data.symbol, f"Calculation error: {str(e)}", start_time
            )
    
    def calculate_metrics(self, market_data: MarketData) -> ScoringMetrics:
        """Calcule les métriques techniques pour une paire"""
        try:
            symbol = market_data.symbol
            
            # Vérifier cache
            cache_key = f"{symbol}_{market_data.timestamp.timestamp()}"
            cached_metrics = self._get_cached_metrics(cache_key)
            if cached_metrics:
                return cached_metrics
            
            metrics = ScoringMetrics()
            
            # Calculer volatilités
            if market_data.ohlcv_1m and market_data.ohlcv_1m.klines:
                closes = market_data.ohlcv_1m.get_closes()
                volumes = market_data.ohlcv_1m.get_volumes()
                
                # Volatilité récente (5 périodes)
                if len(closes) >= 5:
                    metrics.volatility_5 = self._calculate_volatility(closes, 5)
                
                # Volatilité long terme (15 périodes)
                if len(closes) >= 15:
                    metrics.volatility_15 = self._calculate_volatility(closes, 15)
                
                # Volume récent (5 dernières bougies)
                if len(volumes) >= 5:
                    metrics.volume_recent = sum(volumes[-5:])
                
                # ATR calculation
                if len(closes) >= 14:
                    highs = market_data.ohlcv_1m.get_highs()
                    lows = market_data.ohlcv_1m.get_lows()
                    
                    metrics.atr = self._calculate_atr(highs, lows, closes)
                    if closes[-1] > 0:
                        metrics.atr_pct = (metrics.atr / closes[-1]) * 100
                
                # ADX calculation
                if len(closes) >= 20:
                    highs = market_data.ohlcv_1m.get_highs()
                    lows = market_data.ohlcv_1m.get_lows()
                    metrics.adx = self._calculate_adx(highs, lows, closes)
                
                # Volume acceleration
                metrics.volume_acceleration = self._calculate_volume_acceleration(volumes)
                
                # Price momentum 5
                if len(closes) >= 5:
                    metrics.price_momentum_5 = ((closes[-1] - closes[-5]) / closes[-5]) * 100 if closes[-5] > 0 else 0.0
            
            # Volume 24h depuis ticker
            if market_data.ticker:
                metrics.volume_24h = market_data.ticker.volume_24h
            
            # Order flow metrics depuis orderbook
            if market_data.orderbook and market_data.orderbook.bid_vol > 0 and market_data.orderbook.ask_vol > 0:
                metrics.delta_volume = market_data.orderbook.bid_vol - market_data.orderbook.ask_vol
                
                total_vol = market_data.orderbook.bid_vol + market_data.orderbook.ask_vol
                metrics.imbalance_normalized = (
                    (market_data.orderbook.bid_vol - market_data.orderbook.ask_vol) / total_vol 
                    if total_vol > 0 else 0.0
                )
                
                metrics.book_depth_ratio = (
                    market_data.orderbook.bid_vol / market_data.orderbook.ask_vol 
                    if market_data.orderbook.ask_vol > 0 else 1.0
                )
                
                # Spread volatility (nécessite historique - approximation)
                metrics.spread_volatility_5 = self._estimate_spread_volatility(market_data.orderbook.spread_pct)
            
            # Cache les métriques
            self._cache_metrics(cache_key, metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Metrics calculation failed for {market_data.symbol}: {e}")
            return ScoringMetrics()  # Retourner métriques vides
    
    def batch_score(self, market_data_batch: Dict[str, MarketData]) -> Dict[str, ScoringResult]:
        """Score plusieurs paires en batch"""
        try:
            results = {}
            
            for symbol, market_data in market_data_batch.items():
                results[symbol] = self.calculate_score(market_data)
            
            successful_count = sum(1 for r in results.values() if r.is_valid)
            
            logger.info(f"✅ Batch scoring completed: {successful_count}/{len(market_data_batch)} successful")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Batch scoring failed: {e}")
            return {}
    
    def get_scoring_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de scoring"""
        success_rate = 0.0
        if self.scoring_count > 0:
            success_rate = self.successful_scores / self.scoring_count
        
        avg_scoring_time = 0.0
        if self.scoring_count > 0:
            avg_scoring_time = self.total_scoring_time_ms / self.scoring_count
        
        return {
            'performance': {
                'total_scorings': self.scoring_count,
                'successful_scorings': self.successful_scores,
                'rejected_scorings': self.rejected_scores,
                'success_rate': success_rate,
                'average_scoring_time_ms': avg_scoring_time
            },
            'rejection_analytics': {
                'rejection_reasons': dict(self.rejection_reasons),
                'last_rejection': self.last_rejection_reason,
                'total_rejections': sum(self.rejection_reasons.values())
            },
            'cache_stats': {
                'cache_size': len(self._technical_cache),
                'cache_ttl_seconds': self._cache_ttl_seconds
            }
        }
    
    def update_scoring_config(self, config: Dict[str, Any]) -> None:
        """Met à jour la configuration de scoring"""
        self.config.update(config)
        logger.info(f"Scoring configuration updated: {len(config)} parameters")
    
    # =============================================================================
    # MÉTHODES PRIVÉES - Paramètres et Configuration
    # =============================================================================
    
    def _get_effective_scoring_params(self, symbol: str) -> Dict[str, Any]:
        """Récupère les paramètres effectifs du régime de marché"""
        return {
            # Filtres de base
            'spread_min': get_effective_value('scalability_spread_min', symbol=symbol) or 0.001,
            'spread_max': get_effective_value('scalability_spread_max', symbol=symbol) or 0.05,
            'volume_min': get_effective_value('scalability_volume_min', symbol=symbol) or 100000,
            'funding_max': get_effective_value('scalability_funding_rate_max', symbol=symbol) or 0.05,
            'balance_min': get_effective_value('balance_score_min', symbol=symbol) or 0.7,
            
            # Bonus et multiplicateurs
            'adx_threshold': get_effective_value('scalability_adx_bonus_threshold', symbol=symbol) or 25,
            'adx_multiplier': get_effective_value('scalability_adx_bonus_multiplier', symbol=symbol) or 1.2,
            'volume_bonus_threshold': get_effective_value('scalability_volume_bonus_threshold', symbol=symbol) or 2000000,
            'volatility_optimal_min': get_effective_value('scalability_volatility_optimal_min', symbol=symbol) or 0.5,
            'volatility_optimal_max': get_effective_value('scalability_volatility_optimal_max', symbol=symbol) or 3.0,
            
            # Poids dans le calcul du score
            'weight_vol_spread_ratio': 0.4,
            'weight_volume_norm': 0.25,
            'weight_balance': 0.15,
            'weight_adx_bonus': 0.10,
            'weight_order_flow': 0.10
        }
    
    def _check_basic_filters(self, market_data: MarketData, metrics: ScoringMetrics, params: Dict[str, Any]) -> Optional[str]:
        """Vérifie les filtres de base et retourne la raison de rejet si applicable"""
        
        if not market_data.orderbook or not market_data.orderbook.spread_pct:
            return "Missing orderbook data"
        
        spread = market_data.orderbook.spread_pct
        
        # Filtre spread
        if math.isnan(spread):
            return "Invalid spread (NaN)"
        
        if spread <= params['spread_min']:
            return f"Spread too low: {spread:.4f}% <= {params['spread_min']}%"
        
        if spread > params['spread_max']:
            return f"Spread too high: {spread:.4f}% > {params['spread_max']}%"
        
        # Filtre volume
        if metrics.volume_recent < params['volume_min']:
            return f"Volume too low: {metrics.volume_recent:.0f} < {params['volume_min']}"
        
        # Filtre balance orderbook
        if market_data.orderbook.balance_score < params['balance_min']:
            return f"Balance score too low: {market_data.orderbook.balance_score:.2f} < {params['balance_min']}"
        
        # Filtre funding rate (si disponible)
        if (market_data.ticker and market_data.ticker.funding_rate is not None and 
            abs(market_data.ticker.funding_rate) > params['funding_max']):
            return f"Funding rate too high: {market_data.ticker.funding_rate:.3f}% > {params['funding_max']}%"
        
        # Filtre book depth
        if market_data.orderbook.book_depth <= 0:
            return "Book depth is zero or negative"
        
        return None  # Tous les filtres passés
    
    def _calculate_base_score(self, market_data: MarketData, metrics: ScoringMetrics, params: Dict[str, Any]) -> float:
        """Calcule le score de base de scalabilité"""
        try:
            spread = market_data.orderbook.spread_pct
            
            # 1. Ratio volatilité/spread (plus élevé = mieux)
            vol_spread_ratio = 0.0
            if spread > 0 and not math.isnan(spread) and metrics.volatility_5 > 0:
                vol_spread_ratio = metrics.volatility_5 / spread
            
            # 2. Facteur de normalisation volume
            volume_norm_factor = 0.0
            if metrics.volume_recent > 0:
                # Utiliser log pour éviter que les très gros volumes dominent
                volume_norm_factor = math.log10(metrics.volume_recent + 1) / 10.0  # Normaliser sur ~0-1
            
            # 3. Score balance orderbook
            balance_score = market_data.orderbook.balance_score
            
            # 4. Bonus ADX si trend fort
            adx_bonus = 1.0
            if metrics.adx > params['adx_threshold']:
                adx_bonus = params['adx_multiplier']
            
            # 5. Score order flow
            order_flow_score = self._calculate_order_flow_score(metrics)
            
            # Score final pondéré
            base_score = (
                vol_spread_ratio * params['weight_vol_spread_ratio'] +
                volume_norm_factor * params['weight_volume_norm'] +
                balance_score * params['weight_balance'] +
                (adx_bonus - 1.0) * params['weight_adx_bonus'] +  # Normaliser bonus ADX
                order_flow_score * params['weight_order_flow']
            )
            
            return max(0.0, base_score)
            
        except Exception as e:
            logger.error(f"Base score calculation error: {e}")
            return 0.0
    
    def _apply_score_adjustments(self, base_score: float, metrics: ScoringMetrics, params: Dict[str, Any]) -> float:
        """Applique les ajustements et bonus au score de base"""
        try:
            adjusted_score = base_score
            
            # Bonus volume élevé
            if metrics.volume_24h > params['volume_bonus_threshold']:
                volume_bonus = 1.0 + (metrics.volume_24h / params['volume_bonus_threshold'] - 1.0) * 0.1
                adjusted_score *= min(1.5, volume_bonus)  # Max 50% bonus
            
            # Bonus volatilité optimale
            if params['volatility_optimal_min'] <= metrics.volatility_5 <= params['volatility_optimal_max']:
                adjusted_score *= 1.1  # 10% bonus pour volatilité optimale
            
            # Bonus ATR optimal (0.5% - 2.0%)
            if 0.5 <= metrics.atr_pct <= 2.0:
                adjusted_score *= 1.05  # 5% bonus pour ATR optimal
            
            # Pénalité volatilité extrême
            if metrics.volatility_5 > 5.0:  # > 5%
                adjusted_score *= 0.8  # 20% pénalité
            
            # Bonus momentum prix positif
            if metrics.price_momentum_5 > 0:
                momentum_bonus = min(0.1, abs(metrics.price_momentum_5) / 100)  # Max 10% bonus
                adjusted_score *= (1.0 + momentum_bonus)
            
            # Bonus accélération volume
            if metrics.volume_acceleration > 0.2:  # 20% d'accélération
                adjusted_score *= 1.08  # 8% bonus
            
            return adjusted_score
            
        except Exception as e:
            logger.error(f"Score adjustment error: {e}")
            return base_score
    
    def _calculate_order_flow_score(self, metrics: ScoringMetrics) -> float:
        """Calcule un score basé sur les métriques order flow"""
        try:
            score = 0.5  # Score neutre de base
            
            # Bonus imbalance modérée (0.1 - 0.3)
            abs_imbalance = abs(metrics.imbalance_normalized)
            if 0.1 <= abs_imbalance <= 0.3:
                score += 0.2  # Bonne directionnalité
            elif abs_imbalance > 0.5:
                score -= 0.1  # Trop déséquilibré
            
            # Bonus book depth ratio raisonnable (0.7 - 1.3)
            if 0.7 <= metrics.book_depth_ratio <= 1.3:
                score += 0.2
            elif metrics.book_depth_ratio < 0.5 or metrics.book_depth_ratio > 2.0:
                score -= 0.1  # Trop déséquilibré
            
            # Bonus spread volatility faible (stabilité)
            if metrics.spread_volatility_5 < 0.001:  # < 0.1%
                score += 0.1
            
            return max(0.0, min(1.0, score))
            
        except Exception as e:
            logger.error(f"Order flow score calculation error: {e}")
            return 0.5
    
    def _calculate_scoring_details(self, market_data: MarketData, metrics: ScoringMetrics, params: Dict[str, Any]) -> Dict[str, float]:
        """Calcule les détails de scoring pour debug/analytics"""
        try:
            spread = market_data.orderbook.spread_pct
            vol_spread_ratio = metrics.volatility_5 / spread if spread > 0 else 0.0
            
            return {
                'spread_pct': spread,
                'volatility_5': metrics.volatility_5,
                'vol_spread_ratio': vol_spread_ratio,
                'volume_recent': metrics.volume_recent,
                'volume_24h': metrics.volume_24h,
                'balance_score': market_data.orderbook.balance_score,
                'book_depth': market_data.orderbook.book_depth,
                'atr_pct': metrics.atr_pct,
                'adx': metrics.adx,
                'delta_volume': metrics.delta_volume,
                'imbalance_normalized': metrics.imbalance_normalized,
                'volume_acceleration': metrics.volume_acceleration,
                'price_momentum_5': metrics.price_momentum_5,
                'funding_rate': market_data.ticker.funding_rate if market_data.ticker else None
            }
            
        except Exception as e:
            logger.error(f"Scoring details calculation error: {e}")
            return {}
    
    # =============================================================================
    # MÉTHODES PRIVÉES - Calculs Techniques
    # =============================================================================
    
    def _calculate_volatility(self, closes: List[float], period: int) -> float:
        """Calcule la volatilité (écart-type normalisé)"""
        try:
            if len(closes) < period:
                return 0.0
            
            recent_closes = closes[-period:]
            mean = sum(recent_closes) / len(recent_closes)
            
            if mean <= 0:
                return 0.0
            
            variance = sum((v - mean) ** 2 for v in recent_closes) / len(recent_closes)
            std = math.sqrt(variance)
            
            return (std / mean) * 100  # En pourcentage
            
        except Exception:
            return 0.0
    
    def _calculate_atr(self, highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """Calcule l'Average True Range"""
        try:
            if len(closes) < period + 1 or len(highs) < period + 1 or len(lows) < period + 1:
                return 0.0
            
            true_ranges = []
            for i in range(1, len(closes)):
                high = highs[i]
                low = lows[i]
                prev_close = closes[i - 1]
                
                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                true_ranges.append(tr)
            
            if len(true_ranges) < period:
                return 0.0
            
            # ATR = moyenne des True Ranges
            recent_tr = true_ranges[-period:]
            return sum(recent_tr) / len(recent_tr)
            
        except Exception:
            return 0.0
    
    def _calculate_adx(self, highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """Calcule l'ADX (approximation simplifiée)"""
        try:
            if len(closes) < period + 1:
                return 0.0
            
            # Calcul directional movements
            dm_plus = []
            dm_minus = []
            true_ranges = []
            
            for i in range(1, len(closes)):
                move_up = highs[i] - highs[i-1]
                move_down = lows[i-1] - lows[i]
                
                dm_plus.append(move_up if move_up > move_down and move_up > 0 else 0)
                dm_minus.append(move_down if move_down > move_up and move_down > 0 else 0)
                
                # True Range
                tr = max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i-1]),
                    abs(lows[i] - closes[i-1])
                )
                true_ranges.append(tr)
            
            if len(dm_plus) < period or len(true_ranges) < period:
                return 0.0
            
            # Moyennes mobiles
            avg_dm_plus = sum(dm_plus[-period:]) / period
            avg_dm_minus = sum(dm_minus[-period:]) / period
            avg_tr = sum(true_ranges[-period:]) / period
            
            if avg_tr == 0:
                return 0.0
            
            # Directional Indicators
            di_plus = (avg_dm_plus / avg_tr) * 100
            di_minus = (avg_dm_minus / avg_tr) * 100
            
            # DX (simplified ADX)
            total_di = di_plus + di_minus
            if total_di == 0:
                return 0.0
            
            dx = abs(di_plus - di_minus) / total_di * 100
            
            return round(dx, 2)
            
        except Exception:
            return 0.0
    
    def _calculate_volume_acceleration(self, volumes: List[float]) -> float:
        """Calcule l'accélération du volume"""
        try:
            if len(volumes) < 6:
                return 0.0
            
            # Moyenne 3 dernières vs 3 précédentes
            vol_recent = sum(volumes[-3:]) / 3
            vol_previous = sum(volumes[-6:-3]) / 3
            
            if vol_previous == 0:
                return 0.0
            
            acceleration = (vol_recent - vol_previous) / vol_previous
            return round(acceleration, 4)
            
        except Exception:
            return 0.0
    
    def _estimate_spread_volatility(self, current_spread: float) -> float:
        """Estime la volatilité du spread (approximation sans historique)"""
        try:
            # Approximation basée sur le spread courant
            # En réalité, nécessiterait un historique des spreads
            if current_spread <= 0.01:  # 1%
                return 0.0001  # Très stable
            elif current_spread <= 0.02:  # 2%
                return 0.0003  # Modérément stable
            else:
                return 0.001  # Plus volatil
                
        except Exception:
            return 0.0005  # Valeur par défaut
    
    # =============================================================================
    # MÉTHODES PRIVÉES - Cache et Utils
    # =============================================================================
    
    def _get_cached_metrics(self, cache_key: str) -> Optional[ScoringMetrics]:
        """Récupère les métriques depuis le cache"""
        if cache_key not in self._technical_cache:
            return None
        
        cache_entry = self._technical_cache[cache_key]
        age_seconds = (datetime.utcnow() - cache_entry['timestamp']).total_seconds()
        
        if age_seconds > self._cache_ttl_seconds:
            del self._technical_cache[cache_key]
            return None
        
        return cache_entry['metrics']
    
    def _cache_metrics(self, cache_key: str, metrics: ScoringMetrics):
        """Met les métriques en cache"""
        self._technical_cache[cache_key] = {
            'metrics': metrics,
            'timestamp': datetime.utcnow()
        }
        
        # Cleanup si cache trop grand
        if len(self._technical_cache) > 500:
            self._cleanup_technical_cache()
    
    def _cleanup_technical_cache(self):
        """Nettoie le cache technique"""
        try:
            now = datetime.utcnow()
            expired_keys = [
                key for key, entry in self._technical_cache.items()
                if (now - entry['timestamp']).total_seconds() > self._cache_ttl_seconds
            ]
            
            for key in expired_keys:
                del self._technical_cache[key]
            
            logger.debug(f"Technical cache cleaned: removed {len(expired_keys)} expired entries")
            
        except Exception as e:
            logger.error(f"Technical cache cleanup failed: {e}")
    
    def _create_rejected_result(self, symbol: str, reason: str, start_time: datetime, 
                              metrics: Optional[ScoringMetrics] = None) -> ScoringResult:
        """Crée un résultat de scoring rejeté"""
        
        # Analytics de rejet
        self.last_rejection_reason = reason
        self.rejection_reasons[reason] = self.rejection_reasons.get(reason, 0) + 1
        self.rejected_scores += 1
        
        # Métriques de temps
        scoring_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        self.total_scoring_time_ms += scoring_time
        
        result = ScoringResult(
            symbol=symbol,
            score=0.0,
            metrics=metrics or ScoringMetrics(),
            rejection_reason=reason,
            calculation_time_ms=scoring_time,
            timestamp=datetime.utcnow()
        )
        
        logger.debug(f"❌ Scoring rejected for {symbol}: {reason}")
        
        return result
