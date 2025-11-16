DROP VIEW IF EXISTS ml_features;

CREATE VIEW ml_features AS
SELECT 
    s.id AS scan_id,
    s.timestamp,
    s.symbol,
    -- Features 1m
    s.rsi_1m,
    s.rsi_prev_1m,
    s.macd_hist_1m,
    s.macd_hist_prev_1m,
    s.adx_1m,
    s.di_plus_1m,
    s.di_minus_1m,
    s.di_gap_1m,
    s.atr_pct_1m,
    s.ema_diff_pct_1m,
    s.volume_ratio_1m,
    s.volume_spike_1m,
    s.bb_width_1m,
    s.bb_distance_to_lower_1m,
    s.bb_distance_to_upper_1m,
    -- Features 5m
    s.rsi_5m,
    s.rsi_prev_5m,
    s.macd_hist_5m,
    s.macd_hist_prev_5m,
    s.adx_5m,
    s.di_plus_5m,
    s.di_minus_5m,
    s.di_gap_5m,
    s.atr_pct_5m,
    s.ema_diff_pct_5m,
    s.volume_ratio_5m,
    s.volume_spike_5m,
    s.bb_width_5m,
    s.bb_distance_to_lower_5m,
    s.bb_distance_to_upper_5m,
    -- Quality filters
    s.snr_passed_1m,
    s.snr_passed_5m,
    s.breakout_passed_1m,
    s.breakout_passed_5m,
    s.wick_passed_1m,
    s.wick_passed_5m,
    s.atr_optimal_passed_1m,
    s.atr_optimal_passed_5m,
    s.volume_filter_passed_1m,
    s.volume_filter_passed_5m,
    -- Labels / metadata
    s.is_opportunity,
    s.opportunity_direction,
    t.win AS target_win,
    t.pnl_pct AS target_pnl
FROM scan_logs s
LEFT JOIN opportunities o ON s.id = o.scan_log_id
LEFT JOIN trades t ON o.id = t.opportunity_id;
