-- ============================================
-- Vérifier que les nouvelles données ont bien les colonnes remplies
-- ============================================

-- 1. SCAN_LOGS - Vérifier les nouveaux scans (après 01:41)
SELECT 
    id,
    timestamp,
    symbol,
    spread_pct,
    book_depth,
    balance_score,
    bid_vol,
    ask_vol,
    book_imbalance
FROM scan_logs
WHERE timestamp > '2025-11-16 01:41:00'
ORDER BY timestamp DESC
LIMIT 20;

-- 2. OPPORTUNITIES - Vérifier les nouvelles opportunités (après 01:41)
SELECT 
    id,
    timestamp,
    symbol,
    direction,
    setup_score,
    score_long,
    score_short,
    score_min_required,
    trend_bonus,
    divergence_bonus,
    condition_count
FROM opportunities
WHERE timestamp > '2025-11-16 01:41:00'
ORDER BY timestamp DESC
LIMIT 20;

-- 3. Compter combien de lignes ont les colonnes remplies vs vides
-- SCAN_LOGS
SELECT 
    'scan_logs' as table_name,
    COUNT(*) as total_rows,
    COUNT(spread_pct) as spread_pct_filled,
    COUNT(book_depth) as book_depth_filled,
    COUNT(balance_score) as balance_score_filled,
    COUNT(bid_vol) as bid_vol_filled,
    COUNT(ask_vol) as ask_vol_filled,
    COUNT(book_imbalance) as book_imbalance_filled
FROM scan_logs
WHERE timestamp > '2025-11-16 01:41:00';

-- OPPORTUNITIES
SELECT 
    'opportunities' as table_name,
    COUNT(*) as total_rows,
    COUNT(score_long) as score_long_filled,
    COUNT(score_short) as score_short_filled,
    COUNT(score_min_required) as score_min_required_filled,
    COUNT(trend_bonus) as trend_bonus_filled,
    COUNT(divergence_bonus) as divergence_bonus_filled,
    COUNT(condition_count) as condition_count_filled
FROM opportunities
WHERE timestamp > '2025-11-16 01:41:00';

-- 4. Afficher les 5 derniers scans pour inspection visuelle
SELECT 
    id,
    timestamp,
    symbol,
    spread_pct,
    book_depth,
    balance_score,
    CASE 
        WHEN spread_pct IS NULL THEN '❌ VIDE'
        ELSE '✅ REMPLI'
    END as status
FROM scan_logs
ORDER BY timestamp DESC
LIMIT 5;
