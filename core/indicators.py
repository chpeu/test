"""
Calcul des indicateurs techniques
RSI, EMA, MACD, ATR, Bollinger Bands, ADX, Patterns
"""
import numpy as np
from typing import List, Dict, Tuple, Optional


class Indicators:
    """Classe pour calculer les indicateurs techniques"""
    
    @staticmethod
    def calculate_ema(values: List[float], period: int) -> float:
        """
        Calcul EMA (Exponential Moving Average)
        
        Args:
            values: Liste des prix
            period: Période de l'EMA
            
        Returns:
            Valeur de l'EMA
        """
        if len(values) < period:
            return 0.0
        
        k = 2 / (period + 1)
        ema = values[0]
        for i in range(1, len(values)):
            ema = values[i] * k + ema * (1 - k)
        
        return ema
    
    @staticmethod
    def calculate_rsi(closes: List[float], period: int = 14) -> float:
        """
        Calcul RSI (Relative Strength Index)
        
        Args:
            closes: Liste des prix de clôture
            period: Période du RSI
            
        Returns:
            Valeur du RSI (0-100)
        """
        if len(closes) < period + 1:
            return 50.0
        
        gains = 0.0
        losses = 0.0
        
        for i in range(1, period + 1):
            diff = closes[-i] - closes[-i - 1]
            if diff > 0:
                gains += diff
            else:
                losses -= diff
        
        avg_gain = gains / period
        avg_loss = losses / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def calculate_rsi_previous(closes: List[float], period: int = 14) -> float:
        """Calcul RSI de la bougie précédente"""
        if len(closes) < period + 1:
            return 50.0
        
        prev_closes = closes[:-1]
        return Indicators.calculate_rsi(prev_closes, period)
    
    @staticmethod
    def calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """
        Calcul ATR (Average True Range)
        
        Args:
            highs: Liste des prix hauts
            lows: Liste des prix bas
            closes: Liste des prix de clôture
            period: Période ATR
            
        Returns:
            Valeur ATR
        """
        if len(highs) < period + 1:
            return 0.0
        
        tr_array = []
        for i in range(1, len(highs)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            tr_array.append(tr)
        
        return sum(tr_array[-period:]) / period
    
    @staticmethod
    def calculate_macd(closes: List[float], fast_period: int = 3, slow_period: int = 10, signal_period: int = 16) -> Dict:
        """
        Calcul MACD (Moving Average Convergence Divergence)
        
        Args:
            closes: Liste des prix de clôture
            fast_period: Période EMA rapide
            slow_period: Période EMA lente
            signal_period: Période signal line
            
        Returns:
            Dict avec macd, signal, histogram
        """
        if len(closes) < slow_period + signal_period:
            return {'macd': 0.0, 'signal': 0.0, 'histogram': 0.0}
        
        ema_fast = Indicators.calculate_ema(closes, fast_period)
        ema_slow = Indicators.calculate_ema(closes, slow_period)
        macd = ema_fast - ema_slow
        
        # Calculer signal line
        macd_values = []
        for i in range(slow_period, len(closes)):
            ema_f = Indicators.calculate_ema(closes[:i+1], fast_period)
            ema_s = Indicators.calculate_ema(closes[:i+1], slow_period)
            macd_values.append(ema_f - ema_s)
        
        signal = Indicators.calculate_ema(macd_values, signal_period) if len(macd_values) >= signal_period else 0.0
        histogram = macd - signal
        
        return {'macd': macd, 'signal': signal, 'histogram': histogram}
    
    @staticmethod
    def calculate_macd_previous(closes: List[float], fast_period: int = 3, slow_period: int = 10, signal_period: int = 16) -> Dict:
        """Calcul MACD de la bougie précédente"""
        if len(closes) < slow_period + signal_period + 1:
            return {'macd': 0.0, 'signal': 0.0, 'histogram': 0.0}
        
        prev_closes = closes[:-1]
        return Indicators.calculate_macd(prev_closes, fast_period, slow_period, signal_period)
    
    @staticmethod
    def calculate_bollinger_bands(closes: List[float], period: int = 20, std_dev: float = 2.0) -> Dict:
        """
        Calcul Bollinger Bands
        
        Args:
            closes: Liste des prix de clôture
            period: Période SMA
            std_dev: Déviation standard
            
        Returns:
            Dict avec upper, middle, lower, width
        """
        if len(closes) < period:
            return {'upper': 0.0, 'middle': 0.0, 'lower': 0.0, 'width': 0.0}
        
        recent_closes = closes[-period:]
        sma = sum(recent_closes) / period
        
        variance = sum((val - sma) ** 2 for val in recent_closes) / period
        deviation = np.sqrt(variance)
        
        upper = sma + (deviation * std_dev)
        lower = sma - (deviation * std_dev)
        width = (upper - lower) / sma
        
        return {'upper': upper, 'middle': sma, 'lower': lower, 'width': width}
    
    @staticmethod
    def calculate_adx(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Dict:
        """
        Calcul ADX (Average Directional Index)
        
        Args:
            highs: Liste des prix hauts
            lows: Liste des prix bas
            closes: Liste des prix de clôture
            period: Période ADX
            
        Returns:
            Dict avec adx, diPlus, diMinus
        """
        if len(highs) < period + 1:
            return {'adx': 0.0, 'diPlus': 0.0, 'diMinus': 0.0}
        
        plus_dm = []
        minus_dm = []
        tr_array = []
        
        # Calculer +DM, -DM et TR
        for i in range(1, len(highs)):
            up_move = highs[i] - highs[i-1]
            down_move = lows[i-1] - lows[i]
            
            plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
            minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)
            
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            tr_array.append(tr)
        
        # Moyennes
        recent_plus_dm = plus_dm[-period:]
        recent_minus_dm = minus_dm[-period:]
        recent_tr = tr_array[-period:]
        
        avg_plus_dm = sum(recent_plus_dm) / period
        avg_minus_dm = sum(recent_minus_dm) / period
        avg_tr = sum(recent_tr) / period
        
        if avg_tr == 0:
            return {'adx': 0.0, 'diPlus': 0.0, 'diMinus': 0.0}
        
        di_plus = 100 * (avg_plus_dm / avg_tr)
        di_minus = 100 * (avg_minus_dm / avg_tr)
        dx = 100 * abs(di_plus - di_minus) / (di_plus + di_minus)
        
        return {'adx': dx, 'diPlus': di_plus, 'diMinus': di_minus}
    
    @staticmethod
    def detect_pattern(candle: Dict) -> str:
        """
        Détecte les patterns chandeliers
        
        Args:
            candle: Dict avec open, high, low, close
            
        Returns:
            Nom du pattern (ENGULFING_BULLISH, HAMMER, etc.)
        """
        open_price = candle.get('open', candle.get('o', 0))
        high = candle.get('high', candle.get('h', 0))
        low = candle.get('low', candle.get('l', 0))
        close = candle.get('close', candle.get('c', 0))
        
        body = abs(close - open_price)
        upper_shadow = high - max(open_price, close)
        lower_shadow = min(open_price, close) - low
        range_price = high - low
        
        if range_price == 0:
            return 'NONE'
        
        # Engulfing bullish
        if open_price < close and body > range_price * 0.7:
            return 'ENGULFING_BULLISH'
        
        # Engulfing bearish
        if open_price > close and body > range_price * 0.7:
            return 'ENGULFING_BEARISH'
        
        # Hammer
        if lower_shadow > body * 2 and upper_shadow < body * 0.3:
            return 'HAMMER'
        
        # Shooting star
        if upper_shadow > body * 2 and lower_shadow < body * 0.3:
            return 'SHOOTING_STAR'
        
        return 'NONE'

