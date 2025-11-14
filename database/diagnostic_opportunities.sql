-- ============================================================================
-- DIAGNOSTIC : Pourquoi 0 opportunités dans la dernière heure ?
-- ============================================================================

-- 1. Vérifier combien de scans ont is_opportunity = true dans la dernière heure
SELECT 
    'Scans avec is_opportunity = true (dernière heure)' as type,
    COUNT(*) as count
FROM scan_logs
WHERE timestamp > NOW() - INTERVAL '1 hour'
  AND is_opportunity = true;

-- 2. Vérifier toutes les opportunités (pas seulement dernière heure)
SELECT 
    'Total opportunités (toutes périodes)' as type,
    COUNT(*) as count
FROM opportunities;

-- 3. Vérifier les opportunités dans la dernière heure
SELECT 
    'Opportunités (dernière heure)' as type,
    COUNT(*) as count
FROM opportunities
WHERE timestamp > NOW() - INTERVAL '1 hour';

-- 4. Vérifier les opportunités dans les dernières 24h
SELECT 
    'Opportunités (24 dernières heures)' as type,
    COUNT(*) as count
FROM opportunities
WHERE timestamp > NOW() - INTERVAL '24 hours';

-- 5. Vérifier les scans avec is_opportunity = true mais pas d'entrée dans opportunities
SELECT 
    s.symbol,
    s.timestamp,
    s.is_opportunity,
    s.opportunity_direction,
    s.score_total,
    o.id as opportunity_id
FROM scan_logs s
LEFT JOIN opportunities o ON s.id = o.scan_log_id
WHERE s.timestamp > NOW() - INTERVAL '1 hour'
  AND s.is_opportunity = true
ORDER BY s.timestamp DESC
LIMIT 10;

-- 6. Vérifier le statut des opportunités récentes
SELECT 
    status,
    COUNT(*) as count
FROM opportunities
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY status;

-- 7. Vérifier les dernières opportunités créées
SELECT 
    id,
    symbol,
    direction,
    status,
    timestamp,
    scan_log_id
FROM opportunities
ORDER BY timestamp DESC
LIMIT 10;

