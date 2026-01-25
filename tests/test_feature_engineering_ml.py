import pandas as pd
import numpy as np

from optimization.data.feature_engineering import calculate_derived_features, select_top_features


def test_calculate_derived_features_minimal_defaults():
    df = pd.DataFrame({
        'timestamp': ['2026-01-25T10:00:00Z'],
        'reject_reason_category': [None],
    })

    df_eng = calculate_derived_features(df)

    # Colonnes dérivées critiques (doivent exister même si data manquante)
    assert 'momentum_1m' in df_eng.columns
    assert 'momentum_5m' in df_eng.columns
    assert 'volatility_ratio' in df_eng.columns
    assert 'quality_score_total' in df_eng.columns

    # Valeurs par défaut attendues
    assert float(df_eng.loc[0, 'momentum_1m']) == 0.0
    assert float(df_eng.loc[0, 'momentum_5m']) == 0.0
    assert float(df_eng.loc[0, 'volatility_ratio']) == 1.0


def test_calculate_derived_features_full_pipeline_no_nan_inf_and_one_hot():
    df = pd.DataFrame({
            'timestamp': ['2026-01-25 12:34:56'],
            'rsi_1m': [65.0],
            'rsi_prev_1m': [60.0],
            'rsi_5m': [55.0],
            'rsi_prev_5m': [54.0],
            'macd_hist_1m': [0.12],
            'macd_hist_prev_1m': [0.10],
            'macd_hist_5m': [-0.05],
            'macd_hist_prev_5m': [-0.06],
            'atr_pct_1m': [0.45],
            'atr_pct_5m': [0.30],
            'bb_width_1m': [1.2],
            'bb_width_5m': [2.4],
            'adx_1m': [22.0],
            'adx_5m': [18.0],
            'di_gap_1m': [8.0],
            'di_gap_5m': [-12.0],
            'ema_diff_pct_1m': [0.35],
            'ema_diff_pct_5m': [-0.20],
            'volume_ratio_1m': [2.5],
            'volume_ratio_5m': [1.1],
            'volume_spike_1m': [3.2],
            'snr_passed_1m': ['true'],
            'breakout_passed_1m': ['false'],
            'wick_passed_1m': [True],
            'atr_optimal_passed_1m': ['t'],
            'volume_filter_passed_1m': ['f'],
            'snr_passed_5m': [True],
            'breakout_passed_5m': [False],
            'wick_passed_5m': ['true'],
            'atr_optimal_passed_5m': ['false'],
            'volume_filter_passed_5m': ['true'],
            'reject_reason_category': ['volume_filter'],
            'price': [42000.0],
            'atr_1m': [120.0],
            'spread_pct': [0.03],
            'volume_1m': [1234.0],
            'macd_1m': [0.2],
            'macd_signal_1m': [0.1],
            'bb_position_1m': [0.15],
            'macd_5m': [0.05],
            'macd_signal_5m': [0.06],
        })

    df_eng = calculate_derived_features(df)

    expected_cols = [
        'momentum_1m',
        'momentum_5m',
        'momentum_divergence',
        'volatility_ratio',
        'volatility_expanding',
        'rsi_change_1m',
        'rsi_change_5m',
        'macd_momentum_1m',
        'macd_momentum_5m',
        'trend_strength_1m',
        'trend_strength_5m',
        'ema_trend_strength_1m',
        'ema_trend_strength_5m',
        'quality_score_total',
        'high_quality_setup',
        'reject_volume_filter',
        'reject_none',
        # Features temporelles (base)
        'hour_utc',
        'session_asia',
        'session_europe',
        'session_usa',
        'day_of_week',
        'is_weekend',
        # Features avancées (add_advanced_features)
        'hour',
        'is_market_hours',
        'high_volatility',
        'volatility_expansion_ratio',
        'uptrend',
        'ema_gap',
        'rsi_macd_product',
        'volume_price_ratio',
        'atr_spread_ratio',
        'volatility_momentum_product',
    ]

    for col in expected_cols:
        assert col in df_eng.columns

    # One-hot
    assert int(df_eng.loc[0, 'reject_volume_filter']) == 1

    # Pas de NaN/Inf (les NaN peuvent exister sur certaines rolling/ewm si bug)
    numeric_df = df_eng.select_dtypes(include=[np.number]).replace([np.inf, -np.inf], np.nan)
    assert not numeric_df.isna().any().any()


def test_select_top_features_raises_when_target_missing():
    df = pd.DataFrame({
        'f1': [1.0], 'f2': [2.0]
    })

    try:
        select_top_features(df, target_col='target_win')
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "Target column" in str(e)


def test_select_top_features_correlation_skips_constant_columns():
    df = pd.DataFrame({
        'f_const': [1.0, 1.0, 1.0, 1.0],
        'f_good': [0.0, 1.0, 2.0, 3.0],
        'target_win': [0, 1, 1, 1],
    })

    top = select_top_features(df, target_col='target_win', n_features=5, method='correlation')

    assert 'f_good' in top
    assert 'f_const' not in top


def test_select_top_features_mutual_info_uses_mocked_scores(monkeypatch):
    pytest = __import__('pytest')
    pytest.importorskip('sklearn')
    # Patch mutual_info_classif pour éviter dépendance au comportement exact sklearn
    def fake_mi(X, y, random_state=42):
        # Score élevé pour f2, faible pour f1
        return np.array([0.1, 0.9])

    monkeypatch.setattr('sklearn.feature_selection.mutual_info_classif', fake_mi)

    df = pd.DataFrame({
        'f1': [0.0, 1.0, 2.0, 3.0],
        'f2': [0.0, 1.0, 2.0, 3.0],
        'target_win': [0, 1, 1, 1],
    })

    top = select_top_features(df, target_col='target_win', n_features=1, method='mutual_info')
    assert top == ['f2']


def test_select_top_features_invalid_method_raises():
    df = pd.DataFrame({
        'f1': [1.0, 2.0],
        'target_win': [1, 0],
    })

    try:
        select_top_features(df, target_col='target_win', method='nope')
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "not supported" in str(e)
