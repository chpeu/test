"""
Feature Engineering - Création features dérivées pour ML
"""

import pandas as pd
import numpy as np
import logging
from typing import List

logger = logging.getLogger(__name__)


def calculate_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule features dérivées depuis features de base
    
    Features créées:
    - Momentum composite (1m/5m)
    - Volatility ratios
    - Cross-timeframe divergences
    - Volume anomalies
    - Trend strength composites
    
    Args:
        df: DataFrame avec features de base
        
    Returns:
        DataFrame avec features originales + dérivées
    """
    logger.info(f"🔧 Feature engineering sur {len(df)} rows")
    
    df_eng = df.copy()
    
    # ========== MOMENTUM COMPOSITES ==========
    # Momentum 1m (RSI * MACD normalized)
    df_eng['momentum_1m'] = (
        (df_eng['rsi_1m'] / 100) * 
        np.tanh(df_eng['macd_hist_1m'])  # tanh pour normaliser MACD
    )
    
    # Momentum 5m
    df_eng['momentum_5m'] = (
        (df_eng['rsi_5m'] / 100) * 
        np.tanh(df_eng['macd_hist_5m'])
    )
    
    # Momentum cross (divergence 1m vs 5m)
    df_eng['momentum_divergence'] = df_eng['momentum_1m'] - df_eng['momentum_5m']
    
    # ========== VOLATILITY FEATURES ==========
    # Volatility ratio (1m vs 5m)
    df_eng['volatility_ratio'] = df_eng['atr_pct_1m'] / (df_eng['atr_pct_5m'] + 1e-8)
    
    # Volatility expansion (si ratio > 1.5 = expansion)
    df_eng['volatility_expanding'] = (df_eng['volatility_ratio'] > 1.5).astype(int)
    
    # Bollinger squeeze (BB width faible = consolidation)
    df_eng['bb_squeeze_1m'] = (df_eng['bb_width_1m'] < 2.0).astype(int)
    df_eng['bb_squeeze_5m'] = (df_eng['bb_width_5m'] < 2.0).astype(int)
    
    # ========== RSI FEATURES ==========
    # RSI momentum (variation RSI)
    df_eng['rsi_change_1m'] = df_eng['rsi_1m'] - df_eng['rsi_prev_1m']
    df_eng['rsi_change_5m'] = df_eng['rsi_5m'] - df_eng['rsi_prev_5m']
    
    # RSI divergence cross-timeframe
    df_eng['rsi_divergence'] = abs(df_eng['rsi_1m'] - df_eng['rsi_5m'])
    
    # RSI zones
    df_eng['rsi_oversold_1m'] = (df_eng['rsi_1m'] < 30).astype(int)
    df_eng['rsi_overbought_1m'] = (df_eng['rsi_1m'] > 70).astype(int)
    df_eng['rsi_neutral_1m'] = ((df_eng['rsi_1m'] >= 30) & (df_eng['rsi_1m'] <= 70)).astype(int)
    
    # ========== MACD FEATURES ==========
    # MACD momentum (variation histogram)
    df_eng['macd_momentum_1m'] = df_eng['macd_hist_1m'] - df_eng['macd_hist_prev_1m']
    df_eng['macd_momentum_5m'] = df_eng['macd_hist_5m'] - df_eng['macd_hist_prev_5m']
    
    # MACD cross-timeframe
    df_eng['macd_divergence'] = abs(df_eng['macd_hist_1m'] - df_eng['macd_hist_5m'])
    
    # MACD reversal signal (histogram change de signe)
    df_eng['macd_bullish_cross_1m'] = (
        (df_eng['macd_hist_prev_1m'] < 0) & (df_eng['macd_hist_1m'] > 0)
    ).astype(int)
    df_eng['macd_bearish_cross_1m'] = (
        (df_eng['macd_hist_prev_1m'] > 0) & (df_eng['macd_hist_1m'] < 0)
    ).astype(int)
    
    # ========== ADX / TREND STRENGTH ==========
    # Trend strength (ADX * DI gap)
    df_eng['trend_strength_1m'] = df_eng['adx_1m'] * abs(df_eng['di_gap_1m']) / 100
    df_eng['trend_strength_5m'] = df_eng['adx_5m'] * abs(df_eng['di_gap_5m']) / 100
    
    # Strong trend detection
    df_eng['strong_trend_1m'] = ((df_eng['adx_1m'] > 25) & (abs(df_eng['di_gap_1m']) > 10)).astype(int)
    df_eng['strong_trend_5m'] = ((df_eng['adx_5m'] > 25) & (abs(df_eng['di_gap_5m']) > 10)).astype(int)
    
    # Trend direction
    df_eng['trend_bullish_1m'] = (df_eng['di_gap_1m'] > 0).astype(int)
    df_eng['trend_bearish_1m'] = (df_eng['di_gap_1m'] < 0).astype(int)
    
    # ========== EMA FEATURES ==========
    # EMA trend strength
    df_eng['ema_trend_strength_1m'] = abs(df_eng['ema_diff_pct_1m'])
    df_eng['ema_trend_strength_5m'] = abs(df_eng['ema_diff_pct_5m'])
    
    # EMA bullish/bearish
    df_eng['ema_bullish_1m'] = (df_eng['ema_diff_pct_1m'] > 0).astype(int)
    df_eng['ema_bullish_5m'] = (df_eng['ema_diff_pct_5m'] > 0).astype(int)
    
    # EMA cross-timeframe alignment
    df_eng['ema_aligned'] = (
        (df_eng['ema_bullish_1m'] == df_eng['ema_bullish_5m'])
    ).astype(int)
    
    # ========== VOLUME FEATURES ==========
    # Volume surge composite
    df_eng['volume_surge'] = (df_eng['volume_ratio_1m'] > 2.0).astype(int)
    df_eng['volume_spike_strong'] = (df_eng['volume_spike_1m'] > 3.0).astype(int)
    
    # Volume divergence
    df_eng['volume_divergence'] = abs(df_eng['volume_ratio_1m'] - df_eng['volume_ratio_5m'])
    
    # ========== QUALITY FILTERS COMPOSITE ==========
    # Quality score (sum of passed filters)
    filter_cols_1m = [
        'snr_passed_1m', 'breakout_passed_1m', 
        'wick_passed_1m', 'atr_optimal_passed_1m', 'volume_filter_passed_1m'
    ]
    filter_cols_5m = [
        'snr_passed_5m', 'breakout_passed_5m',
        'wick_passed_5m', 'atr_optimal_passed_5m', 'volume_filter_passed_5m'
    ]
    
    # Convertir en int (gère bool, object/string depuis PostgreSQL)
    for col in filter_cols_1m + filter_cols_5m:
        if col in df_eng.columns:
            # Convertir True/False strings ou bools en 1/0
            df_eng[col] = df_eng[col].astype(str).str.lower().map({'true': 1, 'false': 0, 't': 1, 'f': 0}).fillna(0).astype(int)
    
    df_eng['quality_score_1m'] = df_eng[filter_cols_1m].sum(axis=1)
    df_eng['quality_score_5m'] = df_eng[filter_cols_5m].sum(axis=1)
    df_eng['quality_score_total'] = df_eng['quality_score_1m'] + df_eng['quality_score_5m']
    
    # High quality setup (score >= 7/10)
    df_eng['high_quality_setup'] = (df_eng['quality_score_total'] >= 7).astype(int)
    
    # ========== CONFLUENCE FEATURES ==========
    # Multi-timeframe confluence (tous les signaux alignés)
    df_eng['bullish_confluence'] = (
        (df_eng['ema_bullish_1m'] == 1) &
        (df_eng['ema_bullish_5m'] == 1) &
        (df_eng['trend_bullish_1m'] == 1) &
        (df_eng['rsi_1m'] < 70) &
        (df_eng['macd_hist_1m'] > 0)
    ).astype(int)
    
    df_eng['bearish_confluence'] = (
        (df_eng['ema_bullish_1m'] == 0) &
        (df_eng['ema_bullish_5m'] == 0) &
        (df_eng['trend_bearish_1m'] == 1) &
        (df_eng['rsi_1m'] > 30) &
        (df_eng['macd_hist_1m'] < 0)
    ).astype(int)
    
    # ========== RISK INDICATORS ==========
    # High volatility risk
    df_eng['high_volatility_risk'] = (
        (df_eng['volatility_ratio'] > 2.0) |
        (df_eng['atr_pct_1m'] > 5.0)
    ).astype(int)
    
    # Low quality risk
    df_eng['low_quality_risk'] = (df_eng['quality_score_total'] < 4).astype(int)
    
    # Choppy market (ADX faible)
    df_eng['choppy_market'] = (
        (df_eng['adx_1m'] < 20) & (df_eng['adx_5m'] < 20)
    ).astype(int)
    
    # ========== REJECT CATEGORY ONE-HOT ENCODING ==========
    # 🔥 Encoder reject_reason_category en features booléennes
    if 'reject_reason_category' in df_eng.columns:
        # Catégories principales à encoder
        reject_categories = [
            'volume_filter', 'atr_filter', 'snr_filter', 'orderbook',
            'wick_filter', 'spread', 'structure_swing', 'score_insufficient',
            'ema_macd_coherence', 'volume_quality', 'micro_range',
            'confluence', 'correlation', 'recovery_mode'
        ]
        
        for category in reject_categories:
            col_name = f'reject_{category}'
            df_eng[col_name] = (df_eng['reject_reason_category'] == category).astype(int)
        
        # Feature 'accepted' (pas de rejet = opportunity)
        df_eng['reject_none'] = df_eng['reject_reason_category'].isna().astype(int)
        
        logger.info(f"🏷️ One-hot encoding reject_reason_category: {len(reject_categories)+1} features créées")
    
    logger.info(f"✅ Feature engineering de base terminé: {len(df_eng.columns)} features")
    
    # Ajouter features avancées
    df_eng = add_advanced_features(df_eng)
    
    logger.info(f"✅ Feature engineering complet: {len(df_eng.columns)} features totales")
    
    return df_eng


def get_feature_groups() -> dict:
    """
    Retourne groupes de features pour analyse
    
    Returns:
        Dict avec groupes de features
    """
    return {
        'momentum': [
            'momentum_1m', 'momentum_5m', 'momentum_divergence',
            'rsi_change_1m', 'rsi_change_5m', 'rsi_divergence',
            'macd_momentum_1m', 'macd_momentum_5m'
        ],
        'volatility': [
            'volatility_ratio', 'volatility_expanding',
            'bb_squeeze_1m', 'bb_squeeze_5m',
            'atr_pct_1m', 'atr_pct_5m'
        ],
        'trend': [
            'trend_strength_1m', 'trend_strength_5m',
            'strong_trend_1m', 'strong_trend_5m',
            'ema_trend_strength_1m', 'ema_trend_strength_5m',
            'adx_1m', 'adx_5m'
        ],
        'volume': [
            'volume_surge', 'volume_spike_strong',
            'volume_divergence', 'volume_ratio_1m', 'volume_ratio_5m'
        ],
        'quality': [
            'quality_score_1m', 'quality_score_5m', 'quality_score_total',
            'high_quality_setup'
        ],
        'confluence': [
            'bullish_confluence', 'bearish_confluence',
            'ema_aligned'
        ],
        'risk': [
            'high_volatility_risk', 'low_quality_risk', 'choppy_market'
        ]
    }


def select_top_features(
    df: pd.DataFrame,
    target_col: str = 'target_win',
    n_features: int = 30,
    method: str = 'correlation'
) -> List[str]:
    """
    Sélectionne top N features selon corrélation avec target
    
    Args:
        df: DataFrame avec features
        target_col: Colonne target
        n_features: Nombre de features à sélectionner
        method: 'correlation' ou 'mutual_info'
        
    Returns:
        Liste noms des top features
    """
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found")
    
    # Exclure colonnes non-features
    exclude_cols = ['scan_id', 'timestamp', 'symbol', target_col, 'target_pnl', 'is_opportunity']
    feature_cols = [col for col in df.columns if col not in exclude_cols]
    
    X = df[feature_cols]
    y = df[target_col]
    
    if method == 'correlation':
        # Corrélation avec target
        correlations = X.corrwith(y).abs()
        top_features = correlations.nlargest(n_features).index.tolist()
        
    elif method == 'mutual_info':
        from sklearn.feature_selection import mutual_info_classif
        
        # Convertir booléens en int
        X_numeric = X.copy()
        bool_cols = X_numeric.select_dtypes(include=['bool']).columns
        X_numeric[bool_cols] = X_numeric[bool_cols].astype(int)
        
        # Mutual information
        mi_scores = mutual_info_classif(X_numeric.fillna(0), y, random_state=42)
        mi_df = pd.DataFrame({'feature': feature_cols, 'score': mi_scores})
        top_features = mi_df.nlargest(n_features, 'score')['feature'].tolist()
    
    else:
        raise ValueError(f"Method '{method}' not supported")
    
    logger.info(f"📊 Selected top {n_features} features using {method}")
    
    return top_features


def add_advanced_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ajouter features avancées discriminantes
    
    Features temporelles, market regime, confluence, interactions
    
    Args:
        df: DataFrame avec timestamp
        
    Returns:
        DataFrame avec features avancées ajoutées
    """
    logger.info("🚀 Ajout features avancées")
    
    df_adv = df.copy()
    
    # ========== A. FEATURES TEMPORELLES ==========
    if 'timestamp' in df_adv.columns:
        # Convertir en datetime si nécessaire
        if not pd.api.types.is_datetime64_any_dtype(df_adv['timestamp']):
            df_adv['timestamp'] = pd.to_datetime(df_adv['timestamp'])
        
        df_adv['hour'] = df_adv['timestamp'].dt.hour
        df_adv['day_of_week'] = df_adv['timestamp'].dt.dayofweek
        df_adv['is_weekend'] = df_adv['day_of_week'].isin([5, 6]).astype(int)
        df_adv['is_market_hours'] = df_adv['hour'].between(8, 22).astype(int)
        
        # Trading session (Asian/European/US)
        df_adv['asian_session'] = df_adv['hour'].between(0, 8).astype(int)
        df_adv['european_session'] = df_adv['hour'].between(8, 16).astype(int)
        df_adv['us_session'] = df_adv['hour'].between(14, 22).astype(int)
        
        logger.info("  ✅ Features temporelles ajoutées")
    
    # ========== B. MARKET REGIME (VOLATILITY) ==========
    if 'atr_1m' in df_adv.columns:
        # Volatility regime (via rolling mean)
        df_adv['atr_1m_ma20'] = df_adv['atr_1m'].rolling(20, min_periods=1).mean()
        df_adv['high_volatility'] = (df_adv['atr_1m'] > df_adv['atr_1m_ma20']).astype(int)
        df_adv['volatility_expansion_ratio'] = df_adv['atr_1m'] / (df_adv['atr_1m_ma20'] + 1e-8)
        
        logger.info("  ✅ Features volatility regime ajoutées")
    
    # ========== C. MARKET REGIME (TREND) ==========
    if 'price' in df_adv.columns:
        # EMA crossover (9/21)
        df_adv['ema9'] = df_adv['price'].ewm(span=9, min_periods=1).mean()
        df_adv['ema21'] = df_adv['price'].ewm(span=21, min_periods=1).mean()
        df_adv['uptrend'] = (df_adv['ema9'] > df_adv['ema21']).astype(int)
        df_adv['ema_gap'] = (df_adv['ema9'] - df_adv['ema21']) / (df_adv['ema21'] + 1e-8) * 100
        
        # Price position vs EMAs
        df_adv['price_above_ema9'] = (df_adv['price'] > df_adv['ema9']).astype(int)
        df_adv['price_above_ema21'] = (df_adv['price'] > df_adv['ema21']).astype(int)
        
        logger.info("  ✅ Features trend regime ajoutées")
    
    # ========== D. CONFLUENCE AVANCÉE ==========
    if all(col in df_adv.columns for col in ['rsi_1m', 'macd_1m', 'macd_signal_1m', 'bb_position_1m']):
        # Bullish setup (oversold + MACD cross + BB bottom)
        df_adv['bullish_setup'] = (
            (df_adv['rsi_1m'] < 30) & 
            (df_adv['macd_1m'] > df_adv['macd_signal_1m']) &
            (df_adv['bb_position_1m'] < 0.2)
        ).astype(int)
        
        # Bearish setup (overbought + MACD cross + BB top)
        df_adv['bearish_setup'] = (
            (df_adv['rsi_1m'] > 70) & 
            (df_adv['macd_1m'] < df_adv['macd_signal_1m']) &
            (df_adv['bb_position_1m'] > 0.8)
        ).astype(int)
        
        # Multi-timeframe confluence (1m et 5m alignés)
        if all(col in df_adv.columns for col in ['rsi_5m', 'macd_5m', 'macd_signal_5m']):
            df_adv['bullish_confluence_multi_tf'] = (
                df_adv['bullish_setup'] &
                (df_adv['rsi_5m'] < 40) &
                (df_adv['macd_5m'] > df_adv['macd_signal_5m'])
            ).astype(int)
            
            df_adv['bearish_confluence_multi_tf'] = (
                df_adv['bearish_setup'] &
                (df_adv['rsi_5m'] > 60) &
                (df_adv['macd_5m'] < df_adv['macd_signal_5m'])
            ).astype(int)
        
        logger.info("  ✅ Features confluence avancée ajoutées")
    
    # ========== E. INTERACTIONS ==========
    if 'rsi_1m' in df_adv.columns and 'macd_1m' in df_adv.columns:
        df_adv['rsi_macd_product'] = df_adv['rsi_1m'] * df_adv['macd_1m']
    
    if 'volume_1m' in df_adv.columns and 'price' in df_adv.columns:
        df_adv['volume_price_ratio'] = df_adv['volume_1m'] / (df_adv['price'] + 1e-6)
    
    if 'atr_1m' in df_adv.columns and 'spread_pct' in df_adv.columns:
        df_adv['atr_spread_ratio'] = df_adv['atr_1m'] / (df_adv['spread_pct'] + 1e-6)
    
    if 'volatility_ratio' in df_adv.columns and 'momentum_1m' in df_adv.columns:
        df_adv['volatility_momentum_product'] = df_adv['volatility_ratio'] * df_adv['momentum_1m']
    
    logger.info("  ✅ Features interaction ajoutées")
    
    # Log résumé
    new_features_count = len(df_adv.columns) - len(df.columns)
    logger.info(f"✅ {new_features_count} features avancées créées")
    
    return df_adv
