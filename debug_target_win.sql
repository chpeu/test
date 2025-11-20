-- Vérifier pourquoi target_win est NULL dans ml_features
-- Comparer le nombre de lignes dans ml_features vs trades réels

SELECT 
    'ml_features total rows' as table_name,
    COUNT(*) as count
FROM ml_features 
WHERE timestamp > NOW() - INTERVAL '30 days'

UNION ALL

SELECT 
    'ml_features with non-null target_win' as table_name,
    COUNT(*) as count
FROM ml_features 
WHERE timestamp > NOW() - INTERVAL '30 days' 
AND target_win IS NOT NULL

UNION ALL

SELECT 
    'trades completed (with exit)' as table_name,
    COUNT(*) as count
FROM trades 
WHERE timestamp_exit IS NOT NULL 
AND timestamp_exit > NOW() - INTERVAL '30 days'

UNION ALL

SELECT 
    'opportunities without trades' as table_name,
    COUNT(*) as count
FROM opportunities o
LEFT JOIN trades t ON o.id = t.opportunity_id
WHERE o.created_at > NOW() - INTERVAL '30 days'
AND t.id IS NULL;
