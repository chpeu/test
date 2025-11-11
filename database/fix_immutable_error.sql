-- ============================================================================
-- TRADE CURSOR v7.0 - FIX IMMUTABLE ERROR
-- Script pour corriger l'erreur "functions in index expression must be marked IMMUTABLE"
-- ============================================================================

-- Ce script corrige les index qui utilisent EXTRACT() et DATE() directement
-- en créant des fonctions IMMUTABLE wrapper

BEGIN;

-- ============================================================================
-- ÉTAPE 1 : Créer les fonctions IMMUTABLE (toujours nécessaire)
-- ============================================================================

-- Fonction pour extraire l'heure (IMMUTABLE)
CREATE OR REPLACE FUNCTION extract_hour_immutable(timestamptz)
RETURNS INTEGER AS $$
    SELECT EXTRACT(HOUR FROM $1)::INTEGER;
$$ LANGUAGE SQL IMMUTABLE;

-- Fonction pour extraire la date (IMMUTABLE)
CREATE OR REPLACE FUNCTION extract_date_immutable(timestamptz)
RETURNS DATE AS $$
    SELECT DATE($1);
$$ LANGUAGE SQL IMMUTABLE;

-- ============================================================================
-- ÉTAPE 2 : Supprimer les index problématiques (si tables existent)
-- ============================================================================

DO $$ 
BEGIN
    -- Supprimer idx_scan_hour si scan_logs existe
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'scan_logs') THEN
        DROP INDEX IF EXISTS idx_scan_hour CASCADE;
        RAISE NOTICE 'Index idx_scan_hour supprimé (si existait)';
    END IF;
    
    -- Supprimer idx_trade_date_entry si trades existe
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'trades') THEN
        DROP INDEX IF EXISTS idx_trade_date_entry CASCADE;
        RAISE NOTICE 'Index idx_trade_date_entry supprimé (si existait)';
    END IF;
END $$;

-- ============================================================================
-- ÉTAPE 3 : Recréer les index avec les fonctions IMMUTABLE (si tables existent)
-- ============================================================================

DO $$ 
BEGIN
    -- Index sur l'heure du scan (si scan_logs existe)
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'scan_logs') THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_scan_hour ON scan_logs(extract_hour_immutable(timestamp))';
        RAISE NOTICE 'Index idx_scan_hour créé';
    ELSE
        RAISE NOTICE 'Table scan_logs n''existe pas encore - index idx_scan_hour sera créé lors de l''exécution du schéma complet';
    END IF;
    
    -- Index sur la date d'entrée du trade (si trades existe)
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'trades') THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_trade_date_entry ON trades(extract_date_immutable(timestamp_entry))';
        RAISE NOTICE 'Index idx_trade_date_entry créé';
    ELSE
        RAISE NOTICE 'Table trades n''existe pas encore - index idx_trade_date_entry sera créé lors de l''exécution du schéma complet';
    END IF;
END $$;

-- ============================================================================
-- ÉTAPE 4 : Corriger la vue daily_stats si elle existe
-- ============================================================================

DO $$ 
BEGIN
    -- Supprimer la vue si elle existe
    IF EXISTS (SELECT 1 FROM information_schema.views WHERE table_schema = 'public' AND table_name = 'daily_stats') THEN
        DROP VIEW daily_stats CASCADE;
        RAISE NOTICE 'Vue daily_stats supprimée';
    END IF;
    
    -- Recréer la vue avec la fonction IMMUTABLE (si trades existe)
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'trades') THEN
        EXECUTE '
        CREATE VIEW daily_stats AS
        SELECT 
            extract_date_immutable(timestamp_entry) as date,
            COUNT(*) as total_trades,
            COUNT(*) FILTER (WHERE win = TRUE) as wins,
            COUNT(*) FILTER (WHERE win = FALSE) as losses,
            ROUND((COUNT(*) FILTER (WHERE win = TRUE)::FLOAT / NULLIF(COUNT(*), 0) * 100)::numeric, 2) as win_rate_pct,
            ROUND(AVG(net_pnl_pct)::numeric, 4) as avg_pnl_pct,
            ROUND(SUM(net_pnl_usdt)::numeric, 4) as total_pnl_usdt,
            ROUND(AVG(duration_seconds)::numeric, 1) as avg_duration_sec,
            ROUND(AVG(risk_reward_ratio)::numeric, 2) as avg_risk_reward
        FROM trades
        WHERE timestamp_exit IS NOT NULL
        GROUP BY extract_date_immutable(timestamp_entry)
        ORDER BY date DESC';
        RAISE NOTICE 'Vue daily_stats recréée avec fonction IMMUTABLE';
    ELSE
        RAISE NOTICE 'Table trades n''existe pas encore - vue daily_stats sera créée lors de l''exécution du schéma complet';
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- VÉRIFICATION
-- ============================================================================

DO $$ 
DECLARE
    scan_logs_exists BOOLEAN;
    trades_exists BOOLEAN;
BEGIN
    -- Vérifier l'existence des tables
    SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'scan_logs') INTO scan_logs_exists;
    SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'trades') INTO trades_exists;
    
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ Correction terminée !';
    RAISE NOTICE '========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'Fonctions créées :';
    RAISE NOTICE '  - extract_hour_immutable()';
    RAISE NOTICE '  - extract_date_immutable()';
    RAISE NOTICE '';
    
    IF scan_logs_exists THEN
        RAISE NOTICE 'Index créé/corrigé :';
        RAISE NOTICE '  - idx_scan_hour ✓';
    ELSE
        RAISE NOTICE '⚠️  Table scan_logs n''existe pas encore';
        RAISE NOTICE '   L''index idx_scan_hour sera créé lors de l''exécution du schéma complet';
    END IF;
    
    IF trades_exists THEN
        RAISE NOTICE 'Index créé/corrigé :';
        RAISE NOTICE '  - idx_trade_date_entry ✓';
        RAISE NOTICE 'Vue corrigée :';
        RAISE NOTICE '  - daily_stats ✓';
    ELSE
        RAISE NOTICE '⚠️  Table trades n''existe pas encore';
        RAISE NOTICE '   L''index idx_trade_date_entry et la vue daily_stats seront créés lors de l''exécution du schéma complet';
    END IF;
    
    RAISE NOTICE '';
    IF NOT scan_logs_exists OR NOT trades_exists THEN
        RAISE NOTICE '💡 Pour créer les tables, exécutez :';
        RAISE NOTICE '   psql -U postgres -d trade_cursor_ml -f database/schema_postgresql_complete.sql';
    END IF;
    RAISE NOTICE '';
END $$;

