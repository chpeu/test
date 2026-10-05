"""
TestableIndicatorCalculator - Trade Cursor v7.0
Calculateur d'indicateurs techniques découplé et testable
"""

import logging
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from ..interfaces.analyzer_interfaces import (
    IIndicatorCalculator, TechnicalIndicators, ValidationUtils
)

logger = logging.getLogger(__name__)


class TestableIndicatorCalculator(IIndicatorCalculator):
    """
    Calculateur d'indicateurs techniques découplé et testable
    
    Caractéristiques:
    - Calculs purs et déterministes
    - Validation robuste des données d'entrée
    - Gestion des cas limites et erreurs
    - Métriques de performance intégrées
    """
    
    def __init__(self):
        # Compteurs de performance
        self.calculation_count = 0
        self.error_count = 0
        self.total_calculation_time = 0.0
        
        # Cache pour éviter recalculs
        self._calculation_cache = {}
        
        logger.info("✅ TestableIndicatorCalculator initialisé")
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        """Calcule RSI (Relative Strength Index)"""
        try:
            start_time = datetime.utcnow()
            
            if not self._validate_price_data(prices, min_length=period + 1):
                return None
            
            # Convertir en numpy pour efficacité
            prices_array = np.array(prices)
            
            # Calculer les changements de prix
            deltas = np.diff(prices_array)
            
            # Séparer gains et pertes
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            
            # Moyennes mobiles exponentielles
            avg_gains = self._calculate_ema(gains, period)
            avg_losses = self._calculate_ema(losses, period)
            
            # Éviter division par zéro
            if avg_losses == 0:
                rsi = 100.0
            else:
                rs = avg_gains / avg_losses
                rsi = 100 - (100 / (1 + rs))
            
            # Validation du résultat
            if not ValidationUtils.is_valid_rsi(rsi):
                logger.warning(f"Invalid RSI calculated: {rsi}")
                return None
            
            self._update_performance_metrics(start_time)
            return round(rsi, 2)
            
        except Exception as e:
            logger.error(f"RSI calculation error: {e}")
            self.error_count += 1
            return None
    
    def calculate_macd(self, prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Calcule MACD, ligne de signal et histogramme"""
        try:
            start_time = datetime.utcnow()
            
            if not self._validate_price_data(prices, min_length=slow + signal):
                return None, None, None
            
            prices_array = np.array(prices)
            
            # Calculer EMAs
            ema_fast = self._calculate_ema_array(prices_array, fast)
            ema_slow = self._calculate_ema_array(prices_array, slow)
            
            if ema_fast is None or ema_slow is None:
                return None, None, None
            
            # MACD = EMA rapide - EMA lente
            macd_line = ema_fast[-1] - ema_slow[-1]
            
            # Calculer ligne de signal (EMA du MACD)
            macd_values = ema_fast - ema_slow
            valid_macd = macd_values[~np.isnan(macd_values)]
            
            if len(valid_macd) < signal:
                return macd_line, None, None
            
            signal_line = self._calculate_ema(valid_macd, signal)
            
            # Histogramme = MACD - Signal
            histogram = macd_line - signal_line if signal_line is not None else None
            
            self._update_performance_metrics(start_time)
            
            return (
                round(macd_line, 4) if macd_line is not None else None,
                round(signal_line, 4) if signal_line is not None else None,
                round(histogram, 4) if histogram is not None else None
            )
            
        except Exception as e:
            logger.error(f"MACD calculation error: {e}")
            self.error_count += 1
            return None, None, None
    
    def calculate_ema(self, prices: List[float], period: int) -> Optional[float]:
        """Calcule EMA (Exponential Moving Average)"""
        try:
            start_time = datetime.utcnow()
            
            if not self._validate_price_data(prices, min_length=period):
                return None
            
            ema_value = self._calculate_ema(np.array(prices), period)
            
            self._update_performance_metrics(start_time)
            
            return round(ema_value, 4) if ema_value is not None else None
            
        except Exception as e:
            logger.error(f"EMA calculation error: {e}")
            self.error_count += 1
            return None
    
    def calculate_atr(self, highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
        """Calcule ATR (Average True Range)"""
        try:
            start_time = datetime.utcnow()
            
            if not (self._validate_price_data(highs, min_length=period + 1) and
                    self._validate_price_data(lows, min_length=period + 1) and
                    self._validate_price_data(closes, min_length=period + 1)):
                return None
            
            if len(highs) != len(lows) or len(lows) != len(closes):
                logger.warning("ATR: Mismatched array lengths")
                return None
            
            highs_array = np.array(highs)
            lows_array = np.array(lows)
            closes_array = np.array(closes)
            
            # Calculer True Range pour chaque période
            true_ranges = []
            
            for i in range(1, len(closes_array)):
                # TR = max(High - Low, |High - Previous Close|, |Low - Previous Close|)
                tr1 = highs_array[i] - lows_array[i]
                tr2 = abs(highs_array[i] - closes_array[i-1])
                tr3 = abs(lows_array[i] - closes_array[i-1])
                
                true_range = max(tr1, tr2, tr3)
                true_ranges.append(true_range)
            
            if len(true_ranges) < period:
                return None
            
            # ATR = EMA des True Ranges
            atr = self._calculate_ema(np.array(true_ranges), period)
            
            self._update_performance_metrics(start_time)
            
            return round(atr, 6) if atr is not None else None
            
        except Exception as e:
            logger.error(f"ATR calculation error: {e}")
            self.error_count += 1
            return None
    
    def calculate_all_indicators(self, market_data: Dict[str, Any]) -> TechnicalIndicators:
        """Calcule tous les indicateurs pour des données de marché"""
        try:
            start_time = datetime.utcnow()
            
            # Extraire données OHLCV
            ohlcv_1m = market_data.get('ohlcv_1m', [])
            ohlcv_5m = market_data.get('ohlcv_5m', [])
            ohlcv_15m = market_data.get('ohlcv_15m', [])
            
            indicators = TechnicalIndicators()
            
            # Calculer indicateurs 1m
            if ohlcv_1m:
                closes_1m = [candle[4] for candle in ohlcv_1m]  # Close prices
                highs_1m = [candle[2] for candle in ohlcv_1m]   # High prices
                lows_1m = [candle[3] for candle in ohlcv_1m]    # Low prices
                volumes_1m = [candle[5] for candle in ohlcv_1m] # Volumes
                
                # RSI 1m
                indicators.rsi_1m = self.calculate_rsi(closes_1m, 14)
                
                # MACD 1m
                macd_1m, macd_signal_1m, macd_hist_1m = self.calculate_macd(closes_1m)
                indicators.macd_1m = macd_1m
                indicators.macd_signal_1m = macd_signal_1m
                indicators.macd_histogram_1m = macd_hist_1m
                
                # EMAs 1m
                indicators.ema_20_1m = self.calculate_ema(closes_1m, 20)
                indicators.ema_50_1m = self.calculate_ema(closes_1m, 50)
                indicators.ema_200_1m = self.calculate_ema(closes_1m, 200)
                
                # ATR 1m
                indicators.atr_1m = self.calculate_atr(highs_1m, lows_1m, closes_1m, 14)
                if indicators.atr_1m and closes_1m:
                    indicators.atr_pct_1m = (indicators.atr_1m / closes_1m[-1]) * 100
                
                # Volume indicators 1m
                if len(volumes_1m) >= 20:
                    indicators.volume_sma_1m = np.mean(volumes_1m[-20:])
                    if indicators.volume_sma_1m > 0:
                        indicators.volume_ratio_1m = volumes_1m[-1] / indicators.volume_sma_1m
                
                # ADX 1m (approximation simplifiée)
                indicators.adx_1m = self._calculate_adx_approximation(highs_1m, lows_1m, closes_1m)
                
                # Stochastic 1m
                stoch_k, stoch_d = self._calculate_stochastic(highs_1m, lows_1m, closes_1m)
                indicators.stoch_k_1m = stoch_k
                indicators.stoch_d_1m = stoch_d
            
            # Calculer indicateurs 5m
            if ohlcv_5m:
                closes_5m = [candle[4] for candle in ohlcv_5m]
                highs_5m = [candle[2] for candle in ohlcv_5m]
                lows_5m = [candle[3] for candle in ohlcv_5m]
                
                # RSI 5m
                indicators.rsi_5m = self.calculate_rsi(closes_5m, 14)
                
                # MACD 5m
                macd_5m, macd_signal_5m, _ = self.calculate_macd(closes_5m)
                indicators.macd_5m = macd_5m
                indicators.macd_signal_5m = macd_signal_5m
                
                # EMAs 5m
                indicators.ema_20_5m = self.calculate_ema(closes_5m, 20)
                indicators.ema_50_5m = self.calculate_ema(closes_5m, 50)
                
                # ATR 5m
                indicators.atr_5m = self.calculate_atr(highs_5m, lows_5m, closes_5m, 14)
                if indicators.atr_5m and closes_5m:
                    indicators.atr_pct_5m = (indicators.atr_5m / closes_5m[-1]) * 100
                
                # ADX 5m
                indicators.adx_5m = self._calculate_adx_approximation(highs_5m, lows_5m, closes_5m)
            
            # Calculer indicateurs 15m
            if ohlcv_15m:
                closes_15m = [candle[4] for candle in ohlcv_15m]
                indicators.rsi_15m = self.calculate_rsi(closes_15m, 14)
            
            self._update_performance_metrics(start_time)
            
            logger.debug(f"Calculated indicators - RSI: 1m={indicators.rsi_1m}, 5m={indicators.rsi_5m}, MACD: {indicators.macd_1m}")
            
            return indicators
            
        except Exception as e:
            logger.error(f"All indicators calculation error: {e}")
            self.error_count += 1
            return TechnicalIndicators()
    
    def _validate_price_data(self, prices: List[float], min_length: int = 1) -> bool:
        """Valide les données de prix"""
        try:
            if not prices or len(prices) < min_length:
                return False
            
            # Vérifier que tous les prix sont valides
            for price in prices:
                if not ValidationUtils.is_valid_price(price):
                    return False
            
            # Vérifier qu'il n'y a pas trop de prix identiques consécutifs (marché gelé)
            if len(prices) >= 5:
                identical_count = 0
                for i in range(1, len(prices)):
                    if prices[i] == prices[i-1]:
                        identical_count += 1
                        if identical_count >= 4:  # 5 prix identiques consécutifs
                            logger.warning("Too many identical consecutive prices")
                            return False
                    else:
                        identical_count = 0
            
            return True
            
        except Exception:
            return False
    
    def _calculate_ema(self, values: np.ndarray, period: int) -> Optional[float]:
        """Calcule EMA pour un array numpy"""
        try:
            if len(values) < period:
                return None
            
            # Facteur de lissage
            alpha = 2.0 / (period + 1)
            
            # Initialiser avec SMA des premières valeurs
            ema = np.mean(values[:period])
            
            # Calculer EMA pour le reste
            for i in range(period, len(values)):
                ema = alpha * values[i] + (1 - alpha) * ema
            
            return ema
            
        except Exception:
            return None
    
    def _calculate_ema_array(self, values: np.ndarray, period: int) -> Optional[np.ndarray]:
        """Calcule EMA pour un array complet"""
        try:
            if len(values) < period:
                return None
            
            alpha = 2.0 / (period + 1)
            ema_array = np.zeros_like(values)
            
            # Initialiser avec SMA
            ema_array[:period-1] = np.nan
            ema_array[period-1] = np.mean(values[:period])
            
            # Calculer EMA pour le reste
            for i in range(period, len(values)):
                ema_array[i] = alpha * values[i] + (1 - alpha) * ema_array[i-1]
            
            return ema_array
            
        except Exception:
            return None
    
    def _calculate_adx_approximation(self, highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
        """Calcule approximation ADX (simplifiée)"""
        try:
            if len(highs) < period + 1 or len(lows) < period + 1 or len(closes) < period + 1:
                return None
            
            # Calculer directional movements
            dm_plus = []
            dm_minus = []
            
            for i in range(1, len(highs)):
                move_up = highs[i] - highs[i-1]
                move_down = lows[i-1] - lows[i]
                
                dm_plus.append(move_up if move_up > move_down and move_up > 0 else 0)
                dm_minus.append(move_down if move_down > move_up and move_down > 0 else 0)
            
            # Calculer True Range
            true_ranges = []
            for i in range(1, len(closes)):
                tr1 = highs[i] - lows[i]
                tr2 = abs(highs[i] - closes[i-1])
                tr3 = abs(lows[i] - closes[i-1])
                true_ranges.append(max(tr1, tr2, tr3))
            
            if len(dm_plus) < period or len(true_ranges) < period:
                return None
            
            # Moyennes mobiles
            avg_dm_plus = np.mean(dm_plus[-period:])
            avg_dm_minus = np.mean(dm_minus[-period:])
            avg_tr = np.mean(true_ranges[-period:])
            
            if avg_tr == 0:
                return None
            
            # Directional Indicators
            di_plus = (avg_dm_plus / avg_tr) * 100
            di_minus = (avg_dm_minus / avg_tr) * 100
            
            # ADX approximation
            dx = abs(di_plus - di_minus) / (di_plus + di_minus) * 100 if (di_plus + di_minus) > 0 else 0
            
            return round(dx, 2)
            
        except Exception as e:
            logger.error(f"ADX calculation error: {e}")
            return None
    
    def _calculate_stochastic(self, highs: List[float], lows: List[float], closes: List[float], k_period: int = 14, d_period: int = 3) -> Tuple[Optional[float], Optional[float]]:
        """Calcule Stochastic %K et %D"""
        try:
            if len(highs) < k_period or len(lows) < k_period or len(closes) < k_period:
                return None, None
            
            # %K = (Current Close - Lowest Low) / (Highest High - Lowest Low) * 100
            recent_highs = highs[-k_period:]
            recent_lows = lows[-k_period:]
            current_close = closes[-1]
            
            highest_high = max(recent_highs)
            lowest_low = min(recent_lows)
            
            if highest_high == lowest_low:
                stoch_k = 50.0  # Neutral si pas de range
            else:
                stoch_k = ((current_close - lowest_low) / (highest_high - lowest_low)) * 100
            
            # %D = SMA de %K sur d_period (approximation)
            if len(closes) >= k_period + d_period - 1:
                k_values = []
                for i in range(d_period):
                    idx = -(d_period - i)
                    period_highs = highs[idx-k_period+1:idx+1]
                    period_lows = lows[idx-k_period+1:idx+1]
                    period_close = closes[idx]
                    
                    if len(period_highs) == k_period and len(period_lows) == k_period:
                        ph_max = max(period_highs)
                        pl_min = min(period_lows)
                        
                        if ph_max != pl_min:
                            k_val = ((period_close - pl_min) / (ph_max - pl_min)) * 100
                            k_values.append(k_val)
                
                stoch_d = np.mean(k_values) if k_values else stoch_k
            else:
                stoch_d = stoch_k
            
            return round(stoch_k, 2), round(stoch_d, 2)
            
        except Exception as e:
            logger.error(f"Stochastic calculation error: {e}")
            return None, None
    
    def _update_performance_metrics(self, start_time: datetime):
        """Met à jour les métriques de performance"""
        self.calculation_count += 1
        duration = (datetime.utcnow() - start_time).total_seconds() * 1000
        self.total_calculation_time += duration
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de performance"""
        avg_calculation_time = 0.0
        if self.calculation_count > 0:
            avg_calculation_time = self.total_calculation_time / self.calculation_count
        
        error_rate = 0.0
        if self.calculation_count > 0:
            error_rate = self.error_count / self.calculation_count
        
        return {
            'total_calculations': self.calculation_count,
            'total_errors': self.error_count,
            'error_rate': error_rate,
            'average_calculation_time_ms': avg_calculation_time,
            'total_calculation_time_ms': self.total_calculation_time
        }
    
    def clear_cache(self):
        """Vide le cache de calcul"""
        self._calculation_cache.clear()
        logger.debug("Indicator calculation cache cleared")
