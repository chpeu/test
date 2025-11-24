"""
Feature Engineering Avancé - Nouvelles features pour maximiser accuracy
Ajoute : Contexte temporel, régime marché, historique, interactions
"""

import pandas as pd
import numpy as np
import logging
from typing import List

logger = logging.getLogger(__name__)


def add_temporal_context_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Contexte temporel : Session trading, jour semaine, période du mois

    Impact attendu : +2-3% accuracy
    """
    logger.info("🕐 Ajout features contexte temporel...")

    df = df.copy()

    # Convertir timestamp si nécessaire
    if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Heure de la journée
    df['trade_hour'] = df['timestamp'].dt.hour

    # Sessions trading (UTC)
    df['is_asian_session'] = df['trade_hour'].between(0, 7).astype(int)
    df['is_london_session'] = df['trade_hour'].between(8, 16).astype(int)
    df['is_ny_session'] = df['trade_hour'].between(13, 21).astype(int)
    df['is_overlap_session'] = df['trade_hour'].between(13, 16).astype(int)  # Londres + NY

    # Jour de la semaine
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    df['is_monday'] = (df['day_of_week'] == 0).astype(int)
    df['is_friday'] = (df['day_of_week'] == 4).astype(int)
    df['is_midweek'] = df['day_of_week'].between(1, 3).astype(int)

    # Début/fin de mois (comportement différent)
    df['day_of_month'] = df['timestamp'].dt.day
    df['is_month_start'] = (df['day_of_month'] <= 5).astype(int)
    df['is_month_end'] = (df['day_of_month'] >= 25).astype(int)

    logger.info(f"  ✅ {9} features temporelles ajoutées")

    return df


def add_market_regime_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Régime de marché : Trending, ranging, volatile

    Impact attendu : +3-5% accuracy
    """
    logger.info("📈 Ajout features régime marché...")

    df = df.copy()

    # 1. Trending vs Ranging (basé sur ADX)
    df['regime_trending_1m'] = (df['adx_1m'] > 25).astype(int)
    df['regime_ranging_1m'] = (df['adx_1m'] < 20).astype(int)

    df['regime_trending_5m'] = (df['adx_5m'] > 25).astype(int)
    df['regime_ranging_5m'] = (df['adx_5m'] < 20).astype(int)

    # 2. Alignement régimes (1m et 5m)
    df['regime_aligned_trending'] = (
        (df['regime_trending_1m'] == 1) & (df['regime_trending_5m'] == 1)
    ).astype(int)

    df['regime_aligned_ranging'] = (
        (df['regime_ranging_1m'] == 1) & (df['regime_ranging_5m'] == 1)
    ).astype(int)

    # 3. Volatilité relative (percentile)
    df['volatility_percentile_1m'] = df['atr_pct_1m'].rank(pct=True)
    df['volatility_percentile_5m'] = df['atr_pct_5m'].rank(pct=True)

    df['high_volatility_1m'] = (df['volatility_percentile_1m'] > 0.8).astype(int)
    df['low_volatility_1m'] = (df['volatility_percentile_1m'] < 0.2).astype(int)

    # 4. Expansion/contraction volatilité
    df['volatility_expanding'] = (df['atr_pct_1m'] > df['atr_pct_5m']).astype(int)
    df['volatility_contracting'] = (df['atr_pct_1m'] < df['atr_pct_5m']).astype(int)

    # 5. Force tendance (ADX * DI gap normalisé)
    df['trend_force_1m'] = df['adx_1m'] * np.tanh(df['di_gap_1m'] / 10)
    df['trend_force_5m'] = df['adx_5m'] * np.tanh(df['di_gap_5m'] / 10)

    logger.info(f"  ✅ {14} features régime marché ajoutées")

    return df


def add_historical_context_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Historique récent : Winrate, drawdown, streaks

    Impact attendu : +4-6% accuracy (très discriminant en trading)
    """
    logger.info("📊 Ajout features historique récent...")

    df = df.copy()
    df = df.sort_values('timestamp').reset_index(drop=True)

    # 1. Win rate récent (rolling)
    if 'target_win' in df.columns:
        df['recent_winrate_5'] = df['target_win'].rolling(5, min_periods=1).mean()
        df['recent_winrate_10'] = df['target_win'].rolling(10, min_periods=1).mean()
        df['recent_winrate_20'] = df['target_win'].rolling(20, min_periods=1).mean()

    # 2. PNL moyen récent
    if 'target_pnl' in df.columns:
        df['recent_avg_pnl_5'] = df['target_pnl'].rolling(5, min_periods=1).mean()
        df['recent_avg_pnl_10'] = df['target_pnl'].rolling(10, min_periods=1).mean()

        # Drawdown récent (max loss)
        df['recent_drawdown_10'] = df['target_pnl'].rolling(10, min_periods=1).min()
        df['recent_max_gain_10'] = df['target_pnl'].rolling(10, min_periods=1).max()

    # 3. Streaks (séries consécutives)
    if 'target_win' in df.columns:
        # Streak group
        streak_group = (df['target_win'] != df['target_win'].shift()).cumsum()

        # Consecutive wins
        df['consecutive_count'] = df.groupby(streak_group).cumcount() + 1
        df['consecutive_wins'] = df['consecutive_count'] * df['target_win']
        df['consecutive_losses'] = df['consecutive_count'] * (1 - df['target_win'])

        # In winning/losing streak
        df['in_winning_streak'] = (df['consecutive_wins'] >= 2).astype(int)
        df['in_losing_streak'] = (df['consecutive_losses'] >= 2).astype(int)

    # 4. Volatilité récente PNL (instabilité)
    if 'target_pnl' in df.columns:
        df['recent_pnl_volatility_10'] = df['target_pnl'].rolling(10, min_periods=1).std()

    # 5. Momentum historique (amélioration/dégradation)
    if 'target_win' in df.columns:
        df['winrate_momentum'] = df['recent_winrate_5'] - df['recent_winrate_20']

    logger.info(f"  ✅ {16} features historique ajoutées")

    return df


def add_interaction_features(df: pd.DataFrame, top_features: List[str] = None) -> pd.DataFrame:
    """
    Interactions entre features discriminantes

    Impact attendu : +2-4% accuracy
    """
    logger.info("🔗 Ajout features d'interactions...")

    df = df.copy()

    # Si pas de liste fournie, utiliser les top features connus
    if top_features is None:
        top_features = [
            'di_minus_1m', 'rsi_prev_1m', 'rsi_1m',
            'bb_distance_to_upper_1m', 'bb_distance_to_lower_1m',
            'macd_hist_1m', 'adx_1m', 'momentum_1m'
        ]

    interactions = []

    # Interactions 2-way (paires)
    interaction_pairs = [
        ('rsi_1m', 'macd_hist_1m', 'rsi_x_macd_1m'),
        ('adx_1m', 'di_gap_1m', 'adx_x_di_gap_1m'),
        ('volume_ratio_1m', 'atr_pct_1m', 'volume_x_volatility_1m'),
        ('momentum_1m', 'trend_strength_1m', 'momentum_x_trend_1m'),
        ('rsi_1m', 'bb_distance_to_lower_1m', 'rsi_x_bb_lower_1m'),
        ('di_minus_1m', 'di_plus_5m', 'di_cross_timeframe'),
    ]

    for feat1, feat2, name in interaction_pairs:
        if feat1 in df.columns and feat2 in df.columns:
            df[name] = df[feat1] * df[feat2]
            interactions.append(name)

    # Ratios intéressants
    ratio_pairs = [
        ('rsi_1m', 'rsi_5m', 'rsi_ratio_1m_5m'),
        ('adx_1m', 'adx_5m', 'adx_ratio_1m_5m'),
        ('volume_ratio_1m', 'volume_ratio_5m', 'volume_ratio_cross'),
    ]

    for feat1, feat2, name in ratio_pairs:
        if feat1 in df.columns and feat2 in df.columns:
            df[name] = df[feat1] / (df[feat2] + 1e-8)
            interactions.append(name)

    logger.info(f"  ✅ {len(interactions)} features d'interactions ajoutées")

    return df


def add_advanced_quality_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Features de qualité signal avancées

    Impact attendu : +2-3% accuracy
    """
    logger.info("⭐ Ajout features qualité signal avancées...")

    df = df.copy()

    # 1. Confluence multi-timeframe (score)
    confluence_components = []

    # EMA alignées
    if 'ema_bullish_1m' in df.columns and 'ema_bullish_5m' in df.columns:
        df['ema_confluence'] = (df['ema_bullish_1m'] == df['ema_bullish_5m']).astype(int)
        confluence_components.append('ema_confluence')

    # Trend alignés
    if 'trend_bullish_1m' in df.columns:
        df['trend_confluence'] = df['trend_bullish_1m']
        confluence_components.append('trend_confluence')

    # RSI zones alignées
    if 'rsi_1m' in df.columns and 'rsi_5m' in df.columns:
        rsi_1m_zone = pd.cut(df['rsi_1m'], bins=[0, 30, 70, 100], labels=['oversold', 'neutral', 'overbought'])
        rsi_5m_zone = pd.cut(df['rsi_5m'], bins=[0, 30, 70, 100], labels=['oversold', 'neutral', 'overbought'])
        df['rsi_zone_confluence'] = (rsi_1m_zone == rsi_5m_zone).astype(int)
        confluence_components.append('rsi_zone_confluence')

    # Score de confluence total
    if confluence_components:
        df['confluence_score'] = df[confluence_components].sum(axis=1)
        df['high_confluence'] = (df['confluence_score'] >= 2).astype(int)

    # 2. Pattern strength (candlestick strength proxy)
    if 'bb_distance_to_lower_1m' in df.columns and 'bb_distance_to_upper_1m' in df.columns:
        # Distance aux bandes (normalised)
        df['bb_position_1m'] = df['bb_distance_to_lower_1m'] / (
            df['bb_distance_to_lower_1m'] + df['bb_distance_to_upper_1m'] + 1e-8
        )

        # Extrêmes
        df['near_bb_lower'] = (df['bb_position_1m'] < 0.2).astype(int)
        df['near_bb_upper'] = (df['bb_position_1m'] > 0.8).astype(int)

    # 3. Volume confirmation
    if 'volume_spike_1m' in df.columns:
        df['strong_volume_confirmation'] = (df['volume_spike_1m'] > 2.0).astype(int)

    # 4. Risk-reward proxy (volatilité vs trend force)
    if 'trend_force_1m' in df.columns and 'atr_pct_1m' in df.columns:
        df['risk_reward_proxy'] = df['trend_force_1m'] / (df['atr_pct_1m'] + 1e-8)

    logger.info(f"  ✅ ~10 features qualité signal ajoutées")

    return df


def calculate_all_advanced_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applique TOUTES les transformations de features avancées

    Args:
        df: DataFrame avec features de base

    Returns:
        DataFrame avec toutes les features (base + engineered + advanced)
    """
    logger.info("=" * 80)
    logger.info("🔧 FEATURE ENGINEERING AVANCÉ - Toutes Optimisations")
    logger.info("=" * 80)

    initial_cols = len(df.columns)

    # 1. Features de base (existantes)
    from optimization.data.feature_engineering import calculate_derived_features
    df = calculate_derived_features(df)
    logger.info(f"✅ Features de base: {len(df.columns)} colonnes")

    # 2. Contexte temporel
    df = add_temporal_context_features(df)

    # 3. Régime marché
    df = add_market_regime_features(df)

    # 4. Historique
    df = add_historical_context_features(df)

    # 5. Interactions
    df = add_interaction_features(df)

    # 6. Qualité signal
    df = add_advanced_quality_features(df)

    final_cols = len(df.columns)
    added_cols = final_cols - initial_cols

    logger.info("=" * 80)
    logger.info(f"✅ Feature Engineering terminé:")
    logger.info(f"  - Colonnes initiales: {initial_cols}")
    logger.info(f"  - Colonnes finales: {final_cols}")
    logger.info(f"  - Nouvelles features: {added_cols}")
    logger.info("=" * 80)

    return df


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Test
    from optimization.data.feature_loader import load_features_from_postgres

    df = load_features_from_postgres(timeframe_days=90, min_trades=50)
    df_enhanced = calculate_all_advanced_features(df)

    print(f"\n✅ Features finales: {len(df_enhanced.columns)}")
    print(f"✅ Samples: {len(df_enhanced)}")
