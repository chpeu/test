DROP VIEW IF EXISTS ml_features;

CREATE VIEW ml_features AS
SELECT 
    t.scan_log_id AS scan_id,
    t.timestamp_entry AS timestamp,
    t.symbol,
    -- Features 1m (from trades entry snapshot)
    CAST(t.entry_rsi_1m AS DOUBLE PRECISION) AS rsi_1m,
    CAST(t.entry_rsi_prev_1m AS DOUBLE PRECISION) AS rsi_prev_1m,
    CAST(t.entry_macd_hist_1m AS DOUBLE PRECISION) AS macd_hist_1m,
    CAST(t.entry_macd_hist_prev_1m AS DOUBLE PRECISION) AS macd_hist_prev_1m,
    CAST(t.entry_adx_1m AS DOUBLE PRECISION) AS adx_1m,
    CAST(t.entry_di_plus_1m AS DOUBLE PRECISION) AS di_plus_1m,
    CAST(t.entry_di_minus_1m AS DOUBLE PRECISION) AS di_minus_1m,
    CAST(t.entry_di_gap_1m AS DOUBLE PRECISION) AS di_gap_1m,
    CAST(t.entry_atr_pct_1m AS DOUBLE PRECISION) AS atr_pct_1m,
    CAST(t.entry_ema_diff_pct_1m AS DOUBLE PRECISION) AS ema_diff_pct_1m,
    CAST(t.entry_volume_ratio_1m AS DOUBLE PRECISION) AS volume_ratio_1m,
    CAST(t.entry_volume_spike_1m AS DOUBLE PRECISION) AS volume_spike_1m,
    CAST(t.entry_bb_width_1m AS DOUBLE PRECISION) AS bb_width_1m,
    CAST(t.entry_bb_distance_to_lower_1m AS DOUBLE PRECISION) AS bb_distance_to_lower_1m,
    CAST(t.entry_bb_distance_to_upper_1m AS DOUBLE PRECISION) AS bb_distance_to_upper_1m,
    -- Features 5m (from trades entry snapshot)
    CAST(t.entry_rsi_5m AS DOUBLE PRECISION) AS rsi_5m,
    CAST(t.entry_rsi_prev_5m AS DOUBLE PRECISION) AS rsi_prev_5m,
    CAST(t.entry_macd_hist_5m AS DOUBLE PRECISION) AS macd_hist_5m,
    CAST(t.entry_macd_hist_prev_5m AS DOUBLE PRECISION) AS macd_hist_prev_5m,
    CAST(t.entry_adx_5m AS DOUBLE PRECISION) AS adx_5m,
    CAST(t.entry_di_plus_5m AS DOUBLE PRECISION) AS di_plus_5m,
    CAST(t.entry_di_minus_5m AS DOUBLE PRECISION) AS di_minus_5m,
    CAST(t.entry_di_gap_5m AS DOUBLE PRECISION) AS di_gap_5m,
    CAST(t.entry_atr_pct_5m AS DOUBLE PRECISION) AS atr_pct_5m,
    CAST(t.entry_ema_diff_pct_5m AS DOUBLE PRECISION) AS ema_diff_pct_5m,
    CAST(t.entry_volume_ratio_5m AS DOUBLE PRECISION) AS volume_ratio_5m,
    CAST(t.entry_volume_spike_5m AS DOUBLE PRECISION) AS volume_spike_5m,
    CAST(t.entry_bb_width_5m AS DOUBLE PRECISION) AS bb_width_5m,
    CAST(t.entry_bb_distance_to_lower_5m AS DOUBLE PRECISION) AS bb_distance_to_lower_5m,
    CAST(t.entry_bb_distance_to_upper_5m AS DOUBLE PRECISION) AS bb_distance_to_upper_5m,
    -- Quality filters (use scan_logs if available, otherwise NULL)
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
    -- 🔥 Config parameters (nouvelles colonnes)
    CAST(s.config_min_score_required AS DOUBLE PRECISION) AS config_min_score_required,
    CAST(s.config_snr_threshold AS DOUBLE PRECISION) AS config_snr_threshold,
    CAST(s.config_atr_min_1m AS DOUBLE PRECISION) AS config_atr_min_1m,
    CAST(s.config_atr_max_1m AS DOUBLE PRECISION) AS config_atr_max_1m,
    CAST(s.config_atr_min_5m AS DOUBLE PRECISION) AS config_atr_min_5m,
    CAST(s.config_atr_max_5m AS DOUBLE PRECISION) AS config_atr_max_5m,
    CAST(s.config_volume_multiplier AS DOUBLE PRECISION) AS config_volume_multiplier,
    s.config_use_confluence,
    -- 🔥 Reject category (nouvelle colonne)
    s.reject_reason_category,
    -- Labels / metadata
    s.is_opportunity,
    t.direction AS opportunity_direction,
    t.win AS target_win,
    t.pnl_pct AS target_pnl
FROM trades t
LEFT JOIN opportunities o ON t.opportunity_id = o.id
LEFT JOIN scan_logs s ON t.scan_log_id = s.id
WHERE t.timestamp_exit IS NOT NULL
  AND t.win IS NOT NULL;
