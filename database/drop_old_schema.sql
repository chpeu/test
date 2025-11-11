-- ============================================================================
-- TRADE CURSOR v7.0 - DROP OLD SCHEMA
-- Script pour supprimer l'ancien schéma PostgreSQL avant d'appliquer le nouveau
-- ============================================================================

-- ⚠️ ATTENTION : Ce script supprime TOUTES les tables, vues, fonctions, etc.
-- Assurez-vous d'avoir une sauvegarde si nécessaire

BEGIN;

-- ============================================================================
-- ÉTAPE 1 : Supprimer les VUES (dépendent des tables)
-- ============================================================================

DROP VIEW IF EXISTS daily_stats CASCADE;
DROP VIEW IF EXISTS opportunities_executed CASCADE;
DROP VIEW IF EXISTS scans_with_opportunities CASCADE;
DROP VIEW IF EXISTS session_stats CASCADE;
DROP VIEW IF EXISTS ml_features CASCADE;

-- Supprimer toutes les autres vues qui pourraient exister
DO $$ 
DECLARE
    r RECORD;
BEGIN
    FOR r IN (SELECT viewname FROM pg_views WHERE schemaname = 'public') 
    LOOP
        EXECUTE 'DROP VIEW IF EXISTS ' || quote_ident(r.viewname) || ' CASCADE';
    END LOOP;
END $$;

-- ============================================================================
-- ÉTAPE 2 : Supprimer les TRIGGERS
-- ============================================================================

DROP TRIGGER IF EXISTS update_trades_updated_at ON trades CASCADE;

-- Supprimer tous les autres triggers
DO $$ 
DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT trigger_name, event_object_table 
        FROM information_schema.triggers 
        WHERE trigger_schema = 'public'
    ) 
    LOOP
        EXECUTE 'DROP TRIGGER IF EXISTS ' || quote_ident(r.trigger_name) || 
                ' ON ' || quote_ident(r.event_object_table) || ' CASCADE';
    END LOOP;
END $$;

-- ============================================================================
-- ÉTAPE 3 : Supprimer les FONCTIONS
-- ============================================================================

DROP FUNCTION IF EXISTS cleanup_old_data() CASCADE;
DROP FUNCTION IF EXISTS get_global_stats() CASCADE;
DROP FUNCTION IF EXISTS create_monthly_partition(TEXT, DATE) CASCADE;
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;

-- Supprimer toutes les autres fonctions qui pourraient exister
DO $$ 
DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT proname, oidvectortypes(proargtypes) as argtypes
        FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE n.nspname = 'public'
        AND p.prokind = 'f'  -- Fonctions seulement (pas procédures)
    ) 
    LOOP
        BEGIN
            EXECUTE 'DROP FUNCTION IF EXISTS ' || quote_ident(r.proname) || 
                    '(' || r.argtypes || ') CASCADE';
        EXCEPTION WHEN OTHERS THEN
            -- Ignorer les erreurs si la fonction n'existe pas ou a une signature différente
            NULL;
        END;
    END LOOP;
END $$;

-- ============================================================================
-- ÉTAPE 4 : Supprimer les TABLES (dans l'ordre inverse des dépendances)
-- ============================================================================

-- Tables qui référencent d'autres tables (dépendances)
DROP TABLE IF EXISTS model_predictions CASCADE;
DROP TABLE IF EXISTS features_engineered CASCADE;
DROP TABLE IF EXISTS scan_errors CASCADE;
DROP TABLE IF EXISTS trades CASCADE;
DROP TABLE IF EXISTS opportunities CASCADE;
DROP TABLE IF EXISTS market_context CASCADE;
DROP TABLE IF EXISTS config_snapshots CASCADE;

-- Tables partitionnées (supprimer les partitions d'abord)
-- Supprimer toutes les partitions de scan_logs
DO $$ 
DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename LIKE 'scan_logs_%'
    ) 
    LOOP
        EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
    END LOOP;
END $$;

-- Supprimer la table principale partitionnée
DROP TABLE IF EXISTS scan_logs CASCADE;

-- Tables indépendantes
DROP TABLE IF EXISTS trading_sessions CASCADE;

-- ============================================================================
-- ÉTAPE 5 : Supprimer les EXTENSIONS (optionnel, garder uuid-ossp)
-- ============================================================================

-- Ne pas supprimer uuid-ossp car on en a besoin pour le nouveau schéma
-- DROP EXTENSION IF EXISTS "uuid-ossp" CASCADE;

-- ============================================================================
-- ÉTAPE 6 : Nettoyer les SEQUENCES orphelines
-- ============================================================================

DO $$ 
DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT sequence_name 
        FROM information_schema.sequences 
        WHERE sequence_schema = 'public'
    ) 
    LOOP
        EXECUTE 'DROP SEQUENCE IF EXISTS ' || quote_ident(r.sequence_name) || ' CASCADE';
    END LOOP;
END $$;

-- ============================================================================
-- ÉTAPE 7 : Vérification finale
-- ============================================================================

-- Afficher les tables restantes (devrait être vide)
DO $$ 
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_type = 'BASE TABLE';
    
    IF table_count > 0 THEN
        RAISE NOTICE '⚠️ Il reste % table(s) dans le schéma public', table_count;
        RAISE NOTICE 'Tables restantes :';
        FOR r IN (
            SELECT table_name 
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
        ) 
        LOOP
            RAISE NOTICE '  - %', r.table_name;
        END LOOP;
    ELSE
        RAISE NOTICE '✅ Toutes les tables ont été supprimées avec succès';
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- MESSAGE FINAL
-- ============================================================================

DO $$ 
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ Nettoyage terminé !';
    RAISE NOTICE '========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'Vous pouvez maintenant exécuter le nouveau schéma :';
    RAISE NOTICE '  psql -U postgres -d trade_cursor_ml -f database/schema_postgresql_complete.sql';
    RAISE NOTICE '';
END $$;

