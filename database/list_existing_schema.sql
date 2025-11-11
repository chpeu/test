-- ============================================================================
-- TRADE CURSOR v7.0 - LIST EXISTING SCHEMA
-- Script pour lister tous les objets existants dans la base de données
-- ============================================================================

\echo '========================================'
\echo '📋 INVENTAIRE DU SCHÉMA EXISTANT'
\echo '========================================'
\echo ''

-- ============================================================================
-- TABLES
-- ============================================================================

\echo '📊 TABLES :'
\echo '----------------------------------------'

SELECT 
    table_name,
    table_type,
    CASE 
        WHEN table_name LIKE 'scan_logs_%' THEN 'Partition de scan_logs'
        ELSE 'Table normale'
    END as type_detail
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_type = 'BASE TABLE'
ORDER BY table_name;

\echo ''

-- ============================================================================
-- VUES
-- ============================================================================

\echo '👁️  VUES :'
\echo '----------------------------------------'

SELECT 
    viewname as view_name,
    definition
FROM pg_views
WHERE schemaname = 'public'
ORDER BY viewname;

\echo ''

-- ============================================================================
-- FONCTIONS
-- ============================================================================

\echo '⚙️  FONCTIONS :'
\echo '----------------------------------------'

SELECT 
    p.proname as function_name,
    pg_get_function_arguments(p.oid) as arguments,
    pg_get_function_result(p.oid) as return_type,
    CASE p.prokind
        WHEN 'f' THEN 'Fonction'
        WHEN 'p' THEN 'Procédure'
        WHEN 'a' THEN 'Fonction agrégée'
        WHEN 'w' THEN 'Fonction window'
    END as function_type
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
WHERE n.nspname = 'public'
ORDER BY p.proname;

\echo ''

-- ============================================================================
-- TRIGGERS
-- ============================================================================

\echo '🔔 TRIGGERS :'
\echo '----------------------------------------'

SELECT 
    trigger_name,
    event_object_table as table_name,
    event_manipulation as event,
    action_timing as timing,
    action_statement as definition
FROM information_schema.triggers
WHERE trigger_schema = 'public'
ORDER BY event_object_table, trigger_name;

\echo ''

-- ============================================================================
-- SÉQUENCES
-- ============================================================================

\echo '🔢 SÉQUENCES :'
\echo '----------------------------------------'

SELECT 
    sequence_name,
    data_type,
    start_value,
    increment
FROM information_schema.sequences
WHERE sequence_schema = 'public'
ORDER BY sequence_name;

\echo ''

-- ============================================================================
-- INDEX
-- ============================================================================

\echo '📇 INDEX :'
\echo '----------------------------------------'

SELECT 
    t.tablename as table_name,
    i.indexname as index_name,
    i.indexdef as definition
FROM pg_indexes i
JOIN pg_tables t ON i.tablename = t.tablename
WHERE i.schemaname = 'public'
ORDER BY t.tablename, i.indexname;

\echo ''

-- ============================================================================
-- EXTENSIONS
-- ============================================================================

\echo '🔌 EXTENSIONS :'
\echo '----------------------------------------'

SELECT 
    extname as extension_name,
    extversion as version
FROM pg_extension
ORDER BY extname;

\echo ''

-- ============================================================================
-- CONTRAINTES (Foreign Keys, Primary Keys, etc.)
-- ============================================================================

\echo '🔗 CONTRAINTES :'
\echo '----------------------------------------'

SELECT 
    tc.table_name,
    tc.constraint_name,
    tc.constraint_type,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
LEFT JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
WHERE tc.table_schema = 'public'
ORDER BY tc.table_name, tc.constraint_type;

\echo ''

-- ============================================================================
-- RÉSUMÉ
-- ============================================================================

\echo '========================================'
\echo '📊 RÉSUMÉ'
\echo '========================================'

SELECT 
    'Tables' as object_type,
    COUNT(*) as count
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_type = 'BASE TABLE'

UNION ALL

SELECT 
    'Vues' as object_type,
    COUNT(*) as count
FROM pg_views
WHERE schemaname = 'public'

UNION ALL

SELECT 
    'Fonctions' as object_type,
    COUNT(*) as count
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
WHERE n.nspname = 'public'

UNION ALL

SELECT 
    'Triggers' as object_type,
    COUNT(*) as count
FROM information_schema.triggers
WHERE trigger_schema = 'public'

UNION ALL

SELECT 
    'Séquences' as object_type,
    COUNT(*) as count
FROM information_schema.sequences
WHERE sequence_schema = 'public'

UNION ALL

SELECT 
    'Index' as object_type,
    COUNT(*) as count
FROM pg_indexes
WHERE schemaname = 'public'

UNION ALL

SELECT 
    'Extensions' as object_type,
    COUNT(*) as count
FROM pg_extension;

\echo ''
\echo '========================================'
\echo '✅ Inventaire terminé'
\echo '========================================'
\echo ''
\echo '💡 Pour exporter cette liste dans un fichier :'
\echo '   psql -U postgres -d trade_cursor_ml -f database/list_existing_schema.sql > schema_inventory.txt'
\echo ''

