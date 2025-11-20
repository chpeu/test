-- Vérifier les types de colonnes dans trades
SELECT 
    column_name,
    data_type,
    character_maximum_length
FROM information_schema.columns 
WHERE table_name = 'trades' 
  AND column_name LIKE 'entry_%'
ORDER BY ordinal_position
LIMIT 10;

-- Vérifier quelques valeurs réelles
SELECT 
    id,
    symbol,
    entry_rsi_1m,
    entry_adx_1m,
    entry_macd_hist_1m,
    win,
    pnl_pct
FROM trades 
WHERE timestamp_exit IS NOT NULL
LIMIT 3;
