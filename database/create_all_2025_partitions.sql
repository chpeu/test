-- ============================================================================
-- Script pour créer toutes les partitions mensuelles pour 2025
-- ============================================================================
-- Crée les 12 partitions manquantes pour l'année 2025

BEGIN;

-- Partitions déjà créées (janvier, février, mars) - on les ignore avec IF NOT EXISTS
-- Créer les partitions restantes pour 2025

CREATE TABLE IF NOT EXISTS scan_logs_2025_04 PARTITION OF scan_logs
    FOR VALUES FROM ('2025-04-01') TO ('2025-05-01');

CREATE TABLE IF NOT EXISTS scan_logs_2025_05 PARTITION OF scan_logs
    FOR VALUES FROM ('2025-05-01') TO ('2025-06-01');

CREATE TABLE IF NOT EXISTS scan_logs_2025_06 PARTITION OF scan_logs
    FOR VALUES FROM ('2025-06-01') TO ('2025-07-01');

CREATE TABLE IF NOT EXISTS scan_logs_2025_07 PARTITION OF scan_logs
    FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');

CREATE TABLE IF NOT EXISTS scan_logs_2025_08 PARTITION OF scan_logs
    FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');

CREATE TABLE IF NOT EXISTS scan_logs_2025_09 PARTITION OF scan_logs
    FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');

CREATE TABLE IF NOT EXISTS scan_logs_2025_10 PARTITION OF scan_logs
    FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');

CREATE TABLE IF NOT EXISTS scan_logs_2025_11 PARTITION OF scan_logs
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');

CREATE TABLE IF NOT EXISTS scan_logs_2025_12 PARTITION OF scan_logs
    FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');

COMMIT;

-- ============================================================================
-- VÉRIFICATION
-- ============================================================================

DO $$ 
DECLARE
    partition_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO partition_count
    FROM pg_inherits
    WHERE inhparent = 'scan_logs'::regclass;
    
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Partitions creees pour 2025';
    RAISE NOTICE '========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'Nombre total de partitions: %', partition_count;
    RAISE NOTICE '';
    
    IF partition_count >= 12 THEN
        RAISE NOTICE 'Toutes les partitions pour 2025 sont presentes !';
    ELSE
        RAISE NOTICE 'Il manque encore des partitions.';
    END IF;
    
    RAISE NOTICE '';
    RAISE NOTICE 'Liste des partitions:';
    RAISE NOTICE '';
    
    FOR partition_count IN 
        SELECT schemaname || '.' || tablename 
        FROM pg_tables 
        WHERE tablename LIKE 'scan_logs_2025_%'
        ORDER BY tablename
    LOOP
        RAISE NOTICE '  - %', partition_count;
    END LOOP;
    
    RAISE NOTICE '';
END $$;

