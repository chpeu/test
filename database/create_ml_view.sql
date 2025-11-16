CREATE OR REPLACE VIEW ml_features AS
SELECT 
    s.id AS scan_id,
    s.timestamp,
    s.symbol,
    s.is_opportunity,
    s.opportunity_direction,
    s.score_total,
    s.rsi_1m,
    s.rsi_5m,
    s.macd_hist_1m,
    s.macd_hist_5m,
    s.adx_1m,
    s.adx_5m,
    s.atr_pct_1m,
    s.atr_pct_5m,
    s.volume_ratio_1m,
    s.volume_ratio_5m,
    s.spread_pct,
    s.balance_score,
    s.snr_1m,
    s.snr_5m,
    s.breakout_distance_1m,
    s.wick_ratio_1m,
    s.trend_direction,
    s.trend_strength,
    s.divergence_detected,
    s.confluence_met,
    t.win,
    t.net_pnl_pct,
    t.duration_seconds
FROM scan_logs s
LEFT JOIN opportunities o ON s.id = o.scan_log_id
LEFT JOIN trades t ON o.id = t.opportunity_id
WHERE s.is_opportunity = TRUE
  AND t.timestamp_exit IS NOT NULL;
