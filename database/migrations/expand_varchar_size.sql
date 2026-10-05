-- Migration trade_cursor_v7_expand_varchar.sql
-- Expand symbol and exit_reason columns to avoid "value too long" errors

-- 0. Drop dependent views first
DROP VIEW IF EXISTS ml_features;
DROP VIEW IF EXISTS scans_with_opportunities;
DROP VIEW IF EXISTS opportunities_executed;
DROP VIEW IF EXISTS daily_stats;
DROP VIEW IF EXISTS session_stats;

-- 1. Expand 'symbol' columns to VARCHAR(100)
ALTER TABLE scan_logs ALTER COLUMN symbol TYPE VARCHAR(100);
ALTER TABLE opportunities ALTER COLUMN symbol TYPE VARCHAR(100);
ALTER TABLE trades ALTER COLUMN symbol TYPE VARCHAR(100);
ALTER TABLE scan_errors ALTER COLUMN symbol TYPE VARCHAR(100);

-- 2. Expand 'exit_reason' in trades table
ALTER TABLE trades ALTER COLUMN exit_reason TYPE VARCHAR(100);

-- 3. Recreate views (definitions from schema_postgresql_complete.sql)

-- Vue : Scans avec opportunités
CREATE VIEW scans_with_opportunities AS
SELECT 
    s.*,
    o.id as opportunity_id,
    o.status as opportunity_status,
    o.setup_score,
    o.conditions_matched
FROM scan_logs s
LEFT JOIN opportunities o ON s.id = o.scan_log_id
WHERE s.is_opportunity = TRUE;

-- Vue : Opportunités exécutées
CREATE VIEW opportunities_executed AS
SELECT 
    o.*,
    t.id as trade_id,
    t.net_pnl_usdt,
    t.win,
    t.exit_reason,
    t.duration_seconds
FROM opportunities o
INNER JOIN trades t ON o.id = t.opportunity_id
WHERE o.status = 'EXECUTED';

-- Vue : Stats quotidiennes
CREATE VIEW daily_stats AS
SELECT 
    extract_date_immutable(timestamp_entry) as date,
    COUNT(*) as total_trades,
    COUNT(*) FILTER (WHERE win = TRUE) as wins,
    COUNT(*) FILTER (WHERE win = FALSE) as losses,
    ROUND((COUNT(*) FILTER (WHERE win = TRUE)::FLOAT / NULLIF(COUNT(*), 0) * 100)::numeric, 2) as win_rate_pct,
    ROUND(AVG(net_pnl_pct)::numeric, 4) as avg_pnl_pct,
    ROUND(SUM(net_pnl_usdt)::numeric, 4) as total_pnl_usdt,
    ROUND(AVG(duration_seconds)::numeric, 1) as avg_duration_sec,
    ROUND(AVG(risk_reward_ratio)::numeric, 2) as avg_risk_reward
FROM trades
WHERE timestamp_exit IS NOT NULL
GROUP BY extract_date_immutable(timestamp_entry)
ORDER BY date DESC;

-- Vue : Stats par session
CREATE VIEW session_stats AS
SELECT 
    ts.id as session_id,
    ts.start_time,
    ts.end_time,
    ts.total_scans,
    ts.opportunities_detected,
    ts.trades_executed,
    ts.wins,
    ts.losses,
    ts.total_pnl_usdt,
    ts.total_pnl_pct,
    ROUND((ts.wins::FLOAT / NULLIF(ts.trades_executed, 0) * 100)::numeric, 2) as win_rate_pct,
    COUNT(t.id) FILTER (WHERE t.win = TRUE) as actual_wins,
    COUNT(t.id) FILTER (WHERE t.win = FALSE) as actual_losses,
    ROUND(SUM(t.net_pnl_usdt)::numeric, 4) as actual_pnl_usdt
FROM trading_sessions ts
LEFT JOIN trades t ON ts.id = t.session_id
GROUP BY ts.id, ts.start_time, ts.end_time, ts.total_scans, 
         ts.opportunities_detected, ts.trades_executed, ts.wins, ts.losses, 
         ts.total_pnl_usdt, ts.total_pnl_pct
ORDER BY ts.start_time DESC;

-- Vue : Features pour ML
CREATE VIEW ml_features AS
SELECT 
    s.id as scan_id,
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
WHERE s.is_opportunity = TRUE AND t.timestamp_exit IS NOT NULL;

-- 4. Update comments to reflect changes
COMMENT ON COLUMN scan_logs.symbol IS 'Symbole de la paire (ex: BTCUSDT:USDT), supporte formats longs';
COMMENT ON COLUMN trades.exit_reason IS 'Raison de sortie (TP_HIT, SL_HIT, EARLY_INVALIDATION, etc.), supporte messages détaillés';
