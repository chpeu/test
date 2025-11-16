"""
Scanner ML Integration - Calcul de features et prédictions pour les opportunités scannées
"""

import logging
from typing import Dict, Optional, List
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def calculate_technical_indicators(klines: List, symbol: str) -> Optional[Dict]:
    """
    Calcule tous les indicateurs techniques nécessaires pour la prédiction ML
    depuis les klines du scanner
    
    Args:
        klines: Liste des klines OHLCV [[timestamp, open, high, low, close, volume], ...]
        symbol: Symbole de la paire
        
    Returns:
        Dict avec toutes les features ou None si erreur
    """
    try:
        if not klines or len(klines) < 30:
            logger.warning(f"Pas assez de klines pour {symbol}")
            return None
        
        # Convertir en DataFrame
        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Calculer RSI
        rsi_1m = calculate_rsi(df['close'], period=14)
        rsi_5m_values = calculate_rsi(df['close'].iloc[::5], period=14)  # Simuler 5m
        rsi_5m = rsi_5m_values.iloc[-1] if len(rsi_5m_values) > 0 else 50
        
        # Calculer MACD
        macd_1m = calculate_macd(df['close'])
        macd_5m = calculate_macd(df['close'].iloc[::5])  # Simuler 5m
        
        # Calculer Bollinger Bands
        bb_1m = calculate_bollinger_bands(df['close'], period=20)
        bb_5m = calculate_bollinger_bands(df['close'].iloc[::5], period=20)
        
        # Calculer EMA
        ema9_1m = df['close'].ewm(span=9, adjust=False).mean().iloc[-1]
        ema21_1m = df['close'].ewm(span=21, adjust=False).mean().iloc[-1]
        ema_diff_pct_1m = ((ema9_1m - ema21_1m) / ema21_1m) * 100 if ema21_1m > 0 else 0
        
        close_5m = df['close'].iloc[::5]
        ema9_5m = close_5m.ewm(span=9, adjust=False).mean().iloc[-1] if len(close_5m) >= 9 else df['close'].iloc[-1]
        ema21_5m = close_5m.ewm(span=21, adjust=False).mean().iloc[-1] if len(close_5m) >= 21 else df['close'].iloc[-1]
        ema_diff_pct_5m = ((ema9_5m - ema21_5m) / ema21_5m) * 100 if ema21_5m > 0 else 0
        
        # Calculer ATR
        atr_1m = calculate_atr(df)
        atr_pct_1m = (atr_1m / df['close'].iloc[-1]) * 100 if df['close'].iloc[-1] > 0 else 0
        
        df_5m = df.iloc[::5].copy()
        atr_5m = calculate_atr(df_5m) if len(df_5m) >= 14 else atr_1m
        atr_pct_5m = (atr_5m / df['close'].iloc[-1]) * 100 if df['close'].iloc[-1] > 0 else 0
        
        # Volume features
        volumes = df['volume'].values
        vol_ma_1m = np.mean(volumes[-10:]) if len(volumes) >= 10 else volumes[-1]
        vol_ratio_1m = volumes[-1] / vol_ma_1m if vol_ma_1m > 0 else 1.0
        
        vol_5m = np.sum(volumes[-5:]) if len(volumes) >= 5 else volumes[-1]
        vol_ma_5m = np.mean([np.sum(volumes[i:i+5]) for i in range(0, len(volumes)-5, 5)][-10:]) if len(volumes) >= 50 else vol_5m
        vol_ratio_5m = vol_5m / vol_ma_5m if vol_ma_5m > 0 else 1.0
        
        # Divergences cross-timeframe
        rsi_divergence = abs(rsi_1m - rsi_5m)
        macd_divergence = macd_1m['histogram'] - macd_5m['histogram']
        volume_divergence = (vol_ratio_1m - vol_ratio_5m) * 10
        
        # Regime features
        volatility_regime = atr_pct_1m / 1.0  # Normalized
        trend_strength = abs(ema_diff_pct_1m) / 0.5  # Normalized
        market_condition = 1 if ema_diff_pct_1m > 0 else 0
        
        # Construire features dict
        features = {
            # Features 1m
            'rsi_1m': rsi_1m,
            'rsi_change_1m': 0,  # Pas de previous dans le scanner simple
            'macd_1m': macd_1m['macd'],
            'macd_signal_1m': macd_1m['signal'],
            'macd_momentum_1m': macd_1m['histogram'],
            'bb_upper_1m': bb_1m['upper'],
            'bb_middle_1m': bb_1m['middle'],
            'bb_lower_1m': bb_1m['lower'],
            'bb_width_1m': bb_1m['width'],
            'bb_distance_to_upper_1m': bb_1m['distance_to_upper'],
            'bb_distance_to_lower_1m': bb_1m['distance_to_lower'],
            'ema_9_1m': ema9_1m,
            'ema_21_1m': ema21_1m,
            'ema_diff_pct_1m': ema_diff_pct_1m,
            'atr_1m': atr_1m,
            'atr_pct_1m': atr_pct_1m,
            'volume_1m': volumes[-1],
            'volume_ma_1m': vol_ma_1m,
            'volume_ratio_1m': vol_ratio_1m,
            
            # Features 5m
            'rsi_5m': rsi_5m,
            'rsi_change_5m': 0,
            'macd_5m': macd_5m['macd'],
            'macd_signal_5m': macd_5m['signal'],
            'macd_momentum_5m': macd_5m['histogram'],
            'bb_upper_5m': bb_5m['upper'],
            'bb_middle_5m': bb_5m['middle'],
            'bb_lower_5m': bb_5m['lower'],
            'bb_width_5m': bb_5m['width'],
            'bb_distance_to_upper_5m': bb_5m['distance_to_upper'],
            'bb_distance_to_lower_5m': bb_5m['distance_to_lower'],
            'ema_9_5m': ema9_5m,
            'ema_21_5m': ema21_5m,
            'ema_diff_pct_5m': ema_diff_pct_5m,
            'atr_5m': atr_5m,
            'atr_pct_5m': atr_pct_5m,
            'volume_5m': vol_5m,
            'volume_ma_5m': vol_ma_5m,
            'volume_ratio_5m': vol_ratio_5m,
            
            # Divergences
            'rsi_divergence': rsi_divergence,
            'macd_divergence': macd_divergence,
            'volume_divergence': volume_divergence,
            
            # Regime
            'volatility_regime': volatility_regime,
            'trend_strength': trend_strength,
            'market_condition': market_condition,
        }
        
        # Remplacer inf/nan par 0
        for key, value in features.items():
            if pd.isna(value) or np.isinf(value):
                features[key] = 0
        
        return features
        
    except Exception as e:
        logger.error(f"❌ Erreur calculate_technical_indicators pour {symbol}: {e}", exc_info=True)
        return None


def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
    """Calcule RSI"""
    try:
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
    except:
        return 50.0


def calculate_macd(prices: pd.Series, fast=12, slow=26, signal=9) -> Dict:
    """Calcule MACD"""
    try:
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return {
            'macd': float(macd_line.iloc[-1]) if not pd.isna(macd_line.iloc[-1]) else 0.0,
            'signal': float(signal_line.iloc[-1]) if not pd.isna(signal_line.iloc[-1]) else 0.0,
            'histogram': float(histogram.iloc[-1]) if not pd.isna(histogram.iloc[-1]) else 0.0
        }
    except:
        return {'macd': 0.0, 'signal': 0.0, 'histogram': 0.0}


def calculate_bollinger_bands(prices: pd.Series, period=20, std_dev=2) -> Dict:
    """Calcule Bollinger Bands"""
    try:
        middle = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        current_price = prices.iloc[-1]
        middle_val = middle.iloc[-1]
        upper_val = upper.iloc[-1]
        lower_val = lower.iloc[-1]
        
        width = ((upper_val - lower_val) / middle_val) * 100 if middle_val > 0 else 0
        distance_to_upper = upper_val - current_price
        distance_to_lower = current_price - lower_val
        
        return {
            'upper': float(upper_val) if not pd.isna(upper_val) else current_price,
            'middle': float(middle_val) if not pd.isna(middle_val) else current_price,
            'lower': float(lower_val) if not pd.isna(lower_val) else current_price,
            'width': float(width) if not pd.isna(width) else 0.0,
            'distance_to_upper': float(distance_to_upper) if not pd.isna(distance_to_upper) else 0.0,
            'distance_to_lower': float(distance_to_lower) if not pd.isna(distance_to_lower) else 0.0,
        }
    except:
        current = float(prices.iloc[-1])
        return {
            'upper': current,
            'middle': current,
            'lower': current,
            'width': 0.0,
            'distance_to_upper': 0.0,
            'distance_to_lower': 0.0,
        }


def calculate_atr(df: pd.DataFrame, period=14) -> float:
    """Calcule ATR (Average True Range)"""
    try:
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0.0
    except:
        return 0.0


async def get_ml_prediction_for_opportunity(
    klines: List,
    symbol: str,
    scan_id: Optional[int] = None,
    model_name: str = "xgboost_v1"
) -> Optional[Dict]:
    """
    Obtenir une prédiction ML pour une opportunité du scanner
    
    Args:
        klines: Klines de l'opportunité
        symbol: Symbole
        scan_id: ID du scan
        model_name: Modèle à utiliser
        
    Returns:
        Prédiction ML ou None
    """
    try:
        # Calculer features
        features = calculate_technical_indicators(klines, symbol)
        if not features:
            return None
        
        # Faire prédiction
        from optimization.predictor import predict_opportunity
        
        prediction = predict_opportunity(
            features=features,
            model_name=model_name,
            symbol=symbol,
            scan_id=scan_id,
            log_to_db=True  # Logger automatiquement
        )
        
        return prediction
        
    except Exception as e:
        logger.error(f"❌ Erreur get_ml_prediction_for_opportunity: {e}", exc_info=True)
        return None
