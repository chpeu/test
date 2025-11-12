-- ============================================================================
-- Script de correction pour la fonction get_global_stats()
-- ============================================================================
-- Corrige le problème de type : NUMERIC vs FLOAT

BEGIN;

-- Recréer la fonction avec les conversions de type correctes
CREATE OR REPLACE FUNCTION get_global_stats()
RETURNS TABLE (
    total_scans BIGINT,
    total_opportunities BIGINT,
    total_trades BIGINT,
    win_rate FLOAT,
    total_pnl_usdt FLOAT,
    avg_pnl_pct FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        (SELECT COUNT(*) FROM scan_logs)::BIGINT,
        (SELECT COUNT(*) FROM opportunities)::BIGINT,
        (SELECT COALESCE(COUNT(*), 0) FROM trades WHERE timestamp_exit IS NOT NULL)::BIGINT,
        (SELECT COALESCE(ROUND((COUNT(*) FILTER (WHERE win = TRUE)::FLOAT / 
                      NULLIF(COUNT(*), 0) * 100)::numeric, 2)::FLOAT, 0.0) 
         FROM trades WHERE win IS NOT NULL),
        (SELECT COALESCE(ROUND(SUM(net_pnl_usdt)::numeric, 4)::FLOAT, 0.0) FROM trades),
        (SELECT COALESCE(ROUND(AVG(net_pnl_pct)::numeric, 4)::FLOAT, 0.0) FROM trades WHERE net_pnl_pct IS NOT NULL);
END;
$$ LANGUAGE plpgsql;

COMMIT;

-- ============================================================================
-- VÉRIFICATION
-- ============================================================================

DO $$ 
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Fonction get_global_stats() corrigee !';
    RAISE NOTICE '========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'Vous pouvez maintenant tester avec :';
    RAISE NOTICE '  SELECT * FROM get_global_stats();';
    RAISE NOTICE '';
END $$;


