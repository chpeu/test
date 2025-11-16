-- Diagnostic: vérifier les types et valeurs dans ml_features
SELECT 
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'ml_features' 
ORDER BY ordinal_position;

-- Vérifier quelques valeurs réelles
SELECT 
    scan_id,
    timestamp,
    symbol,
    rsi_1m,
    rsi_5m,
    target_win,
    target_pnl
FROM ml_features 
LIMIT 3;
