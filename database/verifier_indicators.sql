-- Script SQL pour vérifier les indicateurs d'entrée dans PostgreSQL
-- Usage: psql -U postgres -d trade_cursor_ml -f database/verifier_indicators.sql

-- 1. Compter les trades avec indicateurs remplis
SELECT 
    COUNT(*) as total_trades,
    COUNT(entry_rsi_1m) FILTER (WHERE entry_rsi_1m IS NOT NULL) as trades_with_rsi_1m,
    COUNT(entry_rsi_5m) FILTER (WHERE entry_rsi_5m IS NOT NULL) as trades_with_rsi_5m,
    COUNT(entry_macd_hist_1m) FILTER (WHERE entry_macd_hist_1m IS NOT NULL) as trades_with_macd_hist_1m,
    COUNT(entry_macd_hist_5m) FILTER (WHERE entry_macd_hist_5m IS NOT NULL) as trades_with_macd_hist_5m,
    COUNT(entry_adx_1m) FILTER (WHERE entry_adx_1m IS NOT NULL) as trades_with_adx_1m,
    COUNT(entry_adx_5m) FILTER (WHERE entry_adx_5m IS NOT NULL) as trades_with_adx_5m,
    COUNT(entry_ema9_1m) FILTER (WHERE entry_ema9_1m IS NOT NULL) as trades_with_ema9_1m,
    COUNT(entry_ema21_1m) FILTER (WHERE entry_ema21_1m IS NOT NULL) as trades_with_ema21_1m,
    COUNT(entry_atr_1m) FILTER (WHERE entry_atr_1m IS NOT NULL) as trades_with_atr_1m,
    COUNT(entry_atr_5m) FILTER (WHERE entry_atr_5m IS NOT NULL) as trades_with_atr_5m,
    COUNT(entry_score) FILTER (WHERE entry_score IS NOT NULL) as trades_with_score
FROM trades;

-- 2. Voir le dernier trade avec tous ses indicateurs
SELECT 
    id,
    symbol,
    direction,
    timestamp_entry,
    timestamp_exit,
    entry_price,
    exit_price,
    pnl_pct,
    -- RSI
    entry_rsi_1m,
    entry_rsi_5m,
    -- MACD
    entry_macd_hist_1m,
    entry_macd_hist_5m,
    -- ADX
    entry_adx_1m,
    entry_adx_5m,
    -- EMA
    entry_ema9_1m,
    entry_ema21_1m,
    entry_ema_diff_pct_1m,
    entry_ema9_5m,
    entry_ema21_5m,
    entry_ema_diff_pct_5m,
    -- ATR
    entry_atr_pct_1m,
    entry_atr_pct_5m,
    -- Score et conditions
    entry_score,
    entry_conditions,
    entry_condition_count
FROM trades
ORDER BY timestamp_entry DESC
LIMIT 1;

-- 3. Voir les 5 derniers trades avec indicateurs
SELECT 
    id,
    symbol,
    direction,
    timestamp_entry,
    entry_rsi_1m,
    entry_rsi_5m,
    entry_macd_hist_1m,
    entry_macd_hist_5m,
    entry_adx_1m,
    entry_adx_5m,
    entry_score,
    entry_conditions
FROM trades
ORDER BY timestamp_entry DESC
LIMIT 5;

