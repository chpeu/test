-- ============================================================================
-- REQUÊTES RAPIDES POUR VOIR LES LOGS
-- ============================================================================

-- 1. Vérifier que le datalogger fonctionne (dernières insertions)
SELECT 
    'scan_logs' as table_name,
    MAX(timestamp) as last_insert
FROM scan_logs
UNION ALL
SELECT 
    'trades',
    MAX(timestamp_entry)
FROM trades
UNION ALL
SELECT 
    'opportunities',
    MAX(timestamp)
FROM opportunities;

-- 2. Derniers scans (20 plus récents)
SELECT 
    id,
    timestamp,
    symbol,
    scan_duration_ms,
    price,
    score_total,
    is_opportunity,
    opportunity_direction,
    reject_reason
FROM scan_logs
ORDER BY timestamp DESC
LIMIT 20;

-- 3. Derniers trades
SELECT 
    id,
    timestamp_entry,
    timestamp_exit,
    symbol,
    direction,
    entry_price,
    exit_price,
    size_usdt,
    net_pnl_usdt,
    net_pnl_pct,
    exit_reason
FROM trades
ORDER BY timestamp_entry DESC
LIMIT 20;

-- 4. Opportunités détectées
SELECT 
    id,
    timestamp,
    symbol,
    direction,
    setup_score,
    entry_price,
    status
FROM opportunities
ORDER BY timestamp DESC
LIMIT 20;

-- 5. Erreurs de scan
SELECT 
    id,
    timestamp,
    symbol,
    error_type,
    error_message
FROM scan_errors
ORDER BY timestamp DESC
LIMIT 20;

-- 6. Statistiques rapides (24h)
SELECT 
    COUNT(DISTINCT sl.id) as total_scans,
    COUNT(DISTINCT o.id) as total_opportunities,
    COUNT(DISTINCT t.id) as total_trades,
    COALESCE(SUM(t.net_pnl_usdt), 0) as total_pnl_usdt
FROM scan_logs sl
LEFT JOIN opportunities o ON o.scan_log_id = sl.id
LEFT JOIN trades t ON t.opportunity_id = o.id
WHERE sl.timestamp > NOW() - INTERVAL '24 hours';

