-- ============================================================================
-- Script pour modifier les partitions : garder seulement 3 mois
-- Novembre 2025, Décembre 2025, Janvier 2026
-- ============================================================================

BEGIN;

-- ============================================================================
-- ÉTAPE 1 : Supprimer les anciennes partitions (janvier, février, mars 2025)
-- ============================================================================

DROP TABLE IF EXISTS scan_logs_2025_01 CASCADE;
DROP TABLE IF EXISTS scan_logs_2025_02 CASCADE;
DROP TABLE IF EXISTS scan_logs_2025_03 CASCADE;

-- Supprimer aussi les autres partitions de 2025 si elles existent
DROP TABLE IF EXISTS scan_logs_2025_04 CASCADE;
DROP TABLE IF EXISTS scan_logs_2025_05 CASCADE;
DROP TABLE IF EXISTS scan_logs_2025_06 CASCADE;
DROP TABLE IF EXISTS scan_logs_2025_07 CASCADE;
DROP TABLE IF EXISTS scan_logs_2025_08 CASCADE;
DROP TABLE IF EXISTS scan_logs_2025_09 CASCADE;
DROP TABLE IF EXISTS scan_logs_2025_10 CASCADE;

-- ============================================================================
-- ÉTAPE 2 : Créer les nouvelles partitions (novembre, décembre 2025, janvier 2026)
-- ============================================================================

-- Novembre 2025
CREATE TABLE IF NOT EXISTS scan_logs_2025_11 PARTITION OF scan_logs
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');

-- Décembre 2025
CREATE TABLE IF NOT EXISTS scan_logs_2025_12 PARTITION OF scan_logs
    FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');

-- Janvier 2026
CREATE TABLE IF NOT EXISTS scan_logs_2026_01 PARTITION OF scan_logs
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

COMMIT;

-- ============================================================================
-- VÉRIFICATION
-- ============================================================================

DO $$ 
DECLARE
    partition_count INTEGER;
    partition_name TEXT;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Partitions mises a jour';
    RAISE NOTICE '========================================';
    RAISE NOTICE '';
    
    -- Compter les partitions
    SELECT COUNT(*) INTO partition_count
    FROM pg_inherits
    WHERE inhparent = 'scan_logs'::regclass;
    
    RAISE NOTICE 'Nombre total de partitions: %', partition_count;
    RAISE NOTICE '';
    RAISE NOTICE 'Partitions actives:';
    RAISE NOTICE '';
    
    -- Lister les partitions
    FOR partition_name IN 
        SELECT tablename 
        FROM pg_tables 
        WHERE tablename LIKE 'scan_logs_202%'
        ORDER BY tablename
    LOOP
        RAISE NOTICE '  - %', partition_name;
    END LOOP;
    
    RAISE NOTICE '';
    
    IF partition_count = 3 THEN
        RAISE NOTICE 'Parfait ! Vous avez maintenant 3 partitions :';
        RAISE NOTICE '  - Novembre 2025 (scan_logs_2025_11)';
        RAISE NOTICE '  - Decembre 2025 (scan_logs_2025_12)';
        RAISE NOTICE '  - Janvier 2026 (scan_logs_2026_01)';
    ELSE
        RAISE NOTICE 'Attention : Nombre de partitions inattendu (% au lieu de 3)', partition_count;
    END IF;
    
    RAISE NOTICE '';
END $$;


