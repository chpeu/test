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
        rsi_5m = calculate_rsi(df['close'].iloc[::5], period=14)  # Simuler 5m
        
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

        # 🔥 NOUVELLES FEATURES DISCRIMINANTES (pour améliorer performances ML)

        # 1. Price momentum ratio (1m vs 5m) - Cohérence cross-timeframe
        price_momentum_ratio_1m_5m = (macd_1m['histogram'] / macd_5m['histogram']) if macd_5m['histogram'] != 0 else 1.0

        # 2. Volume-Price Correlation (14 dernières bougies)
        if len(df) >= 14:
            recent_prices = df['close'].iloc[-14:].values
            recent_volumes = df['volume'].iloc[-14:].values
            volume_price_correlation = np.corrcoef(recent_prices, recent_volumes)[0, 1] if len(recent_prices) > 1 else 0
        else:
            volume_price_correlation = 0

        # 3. Bollinger Squeeze (compression avant explosion)
        bb_squeeze_1m = 1 if bb_1m['width'] < 0.002 else 0  # Squeeze si BB width < 0.2%
        bb_squeeze_5m = 1 if bb_5m['width'] < 0.003 else 0  # Squeeze si BB width < 0.3%

        # 4. RSI Divergence Strength (normalisé par volatilité)
        rsi_divergence_strength = rsi_divergence / (atr_pct_1m + 0.01) if atr_pct_1m > 0 else 0

        # 5. MACD Cross Strength (force du croisement)
        macd_cross_strength_1m = abs(macd_1m['histogram']) / (atr_1m + 0.0001) if atr_1m > 0 else 0
        macd_cross_strength_5m = abs(macd_5m['histogram']) / (atr_5m + 0.0001) if atr_5m > 0 else 0

        # 6. ADX Trend Quality (ADX élevé + gap DI significatif)
        di_gap_1m_val = abs(rsi_1m - 50) / 25  # Proxy DI gap si pas disponible
        di_gap_5m_val = abs(rsi_5m - 50) / 25
        adx_trend_quality_1m = (di_gap_1m_val * 25) if rsi_1m > 55 or rsi_1m < 45 else 0  # Proxy ADX
        adx_trend_quality_5m = (di_gap_5m_val * 25) if rsi_5m > 55 or rsi_5m < 45 else 0

        # 7. EMA Alignment Score (cohérence EMA 1m et 5m)
        ema_alignment_1m = 1 if ema9_1m > ema21_1m else -1
        ema_alignment_5m = 1 if ema9_5m > ema21_5m else -1
        ema_alignment_score = 1 if ema_alignment_1m == ema_alignment_5m else 0  # 1 si alignés, 0 sinon

        # 8. Confluence Score Weighted (pondération 1m=60%, 5m=40%)
        # Score basé sur conditions techniques
        confluence_1m = (
            (1 if rsi_1m > 50 and rsi_1m < 70 else 0) +
            (1 if macd_1m['histogram'] > 0 else 0) +
            (1 if ema9_1m > ema21_1m else 0) +
            (1 if vol_ratio_1m > 1.0 else 0)
        ) / 4.0  # Score 0-1

        confluence_5m = (
            (1 if rsi_5m > 50 and rsi_5m < 70 else 0) +
            (1 if macd_5m['histogram'] > 0 else 0) +
            (1 if ema9_5m > ema21_5m else 0) +
            (1 if vol_ratio_5m > 1.0 else 0)
        ) / 4.0  # Score 0-1

        confluence_score_weighted = (confluence_1m * 0.6) + (confluence_5m * 0.4)

        # 9. Volume Momentum (changement volume récent)
        volume_momentum_1m = (volumes[-1] - vol_ma_1m) / (vol_ma_1m + 1) if vol_ma_1m > 0 else 0

        # 10. Price Distance from EMA21 (% distance)
        price_distance_ema21_1m = ((df['close'].iloc[-1] - ema21_1m) / ema21_1m) * 100 if ema21_1m > 0 else 0
        price_distance_ema21_5m = ((df['close'].iloc[-1] - ema21_5m) / ema21_5m) * 100 if ema21_5m > 0 else 0

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

            # 🔥 Nouvelles features discriminantes
            'price_momentum_ratio_1m_5m': price_momentum_ratio_1m_5m,
            'volume_price_correlation': volume_price_correlation,
            'bb_squeeze_1m': bb_squeeze_1m,
            'bb_squeeze_5m': bb_squeeze_5m,
            'rsi_divergence_strength': rsi_divergence_strength,
            'macd_cross_strength_1m': macd_cross_strength_1m,
            'macd_cross_strength_5m': macd_cross_strength_5m,
            'adx_trend_quality_1m': adx_trend_quality_1m,
            'adx_trend_quality_5m': adx_trend_quality_5m,
            'ema_alignment_score': ema_alignment_score,
            'confluence_score_weighted': confluence_score_weighted,
            'volume_momentum_1m': volume_momentum_1m,
            'price_distance_ema21_1m': price_distance_ema21_1m,
            'price_distance_ema21_5m': price_distance_ema21_5m,
        }
        
        # Remplacer inf/nan par 0
        for key, value in features.items():
            if pd.isna(value) or np.isinf(value):
                features[key] = 0
            elif isinstance(value, (np.integer, np.floating)):
                features[key] = value.item()
            elif isinstance(value, np.bool_):
                features[key] = bool(value)
        
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
    model_name: str = "optimized"  # 🔥 CHANGÉ: utiliser optimized par défaut
) -> Optional[Dict]:
    """
    Obtenir une prédiction ML pour une opportunité du scanner
    
    Args:
        klines: Klines de l'opportunité
        symbol: Symbole
        scan_id: ID du scan
        model_name: Modèle à utiliser ("optimized", "xgboost_v1", etc.)
        
    Returns:
        Prédiction ML ou None
    """
    try:
        # Calculer features
        features = calculate_technical_indicators(klines, symbol)
        if not features:
            return None
        
        # 🔥 NOUVEAU: Utiliser le predictor optimisé (GradientBoosting 64-69% accuracy)
        if model_name in ["optimized", "gradientboosting", "best"]:
            from optimization.predictor_optimized import predict_trade
            
            should_trade, confidence = predict_trade(features, threshold=0.5)
            
            return {
                'prediction': 'win' if should_trade else 'loss',
                'confidence': confidence,
                'model': 'GradientBoosting_Optimized',
                'symbol': symbol,
                'scan_id': scan_id,
                'features': features
            }
        
        # Fallback: ancien predictor XGBoost V1
        from optimization.predictor import predict_opportunity
        
        prediction = predict_opportunity(
            features=features,
            model_name=model_name,
            symbol=symbol,
            scan_id=scan_id,
            log_to_db=True
        )

        if isinstance(prediction, dict) and 'features' not in prediction:
            prediction['features'] = features

        return prediction
        
    except Exception as e:
        logger.error(f"❌ Erreur get_ml_prediction_for_opportunity: {e}", exc_info=True)
        return None


async def get_ml_v2_prediction_for_opportunity(
    klines: List,
    symbol: str,
    scan_id: Optional[int] = None,
    model_name: str = "xgboost_v2_latest"
) -> Optional[Dict]:
    """
    Obtenir une prédiction PNL% (V2 Régression) pour une opportunité du scanner
    
    Args:
        klines: Klines de l'opportunité
        symbol: Symbole
        scan_id: ID du scan
        model_name: Modèle V2 à utiliser
        
    Returns:
        Prédiction V2 (PNL% prédit) ou None
    """
    try:
        # Calculer features
        features = calculate_technical_indicators(klines, symbol)
        if not features:
            return None
        
        # Faire prédiction V2
        from optimization.predictor_v2 import predict_pnl
        
        prediction = predict_pnl(
            features=features,
            model_name=model_name,
            symbol=symbol,
            scan_id=scan_id,
            log_to_db=True  # Logger automatiquement
        )
        
        return prediction
        
    except Exception as e:
        logger.error(f"❌ Erreur get_ml_v2_prediction_for_opportunity: {e}", exc_info=True)
        return None


def should_filter_setup_with_ml_v2(
    klines: List,
    symbol: str,
    min_expected_pnl: float = 0.3
) -> tuple[bool, Optional[str]]:
    """
    Filtrer un setup basé sur la prédiction PNL% V2
    
    Args:
        klines: Klines de l'opportunité
        symbol: Symbole
        min_expected_pnl: PNL minimum requis (%)
        
    Returns:
        (should_reject, reason)
    """
    try:
        # Calculer features
        features = calculate_technical_indicators(klines, symbol)
        if not features:
            return (False, None)
        
        # Vérifier avec predictor V2
        from optimization.predictor_v2 import get_predictor_v2
        
        predictor = get_predictor_v2()
        should_reject, predicted_pnl, reason = predictor.should_reject_trade(
            features=features,
            min_expected_pnl=min_expected_pnl
        )
        
        return (should_reject, reason)
        
    except Exception as e:
        logger.error(f"❌ Erreur should_filter_setup_with_ml_v2: {e}")
        return (False, None)
