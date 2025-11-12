-- ============================================================================
-- Script de vérification du schéma PostgreSQL
-- Compare le schéma actuel avec le schéma attendu
-- ============================================================================

-- 1. Lister toutes les tables attendues
SELECT 
    'Tables attendues' as check_type,
    table_name,
    'EXISTS' as status
FROM information_schema.tables
WHERE table_schema = 'public'
    AND table_name IN (
        'trading_sessions',
        'config_snapshots',
        'scan_logs',
        'opportunities',
        'trades',
        'market_context',
        'scan_errors',
        'model_predictions',
        'features_engineered'
    )
ORDER BY table_name;

-- 2. Vérifier les colonnes de chaque table principale
-- trading_sessions
SELECT 
    'trading_sessions' as table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' 
    AND table_name = 'trading_sessions'
ORDER BY ordinal_position;

-- scan_logs
SELECT 
    'scan_logs' as table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' 
    AND table_name = 'scan_logs'
ORDER BY ordinal_position;

-- opportunities
SELECT 
    'opportunities' as table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' 
    AND table_name = 'opportunities'
ORDER BY ordinal_position;

-- trades (vérifier colonnes importantes)
SELECT 
    'trades' as table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' 
    AND table_name = 'trades'
    AND column_name IN (
        'id', 'timestamp_entry', 'timestamp_exit', 'symbol', 
        'direction', 'entry_price', 'exit_price', 'net_pnl_usdt', 
        'net_pnl_pct', 'exit_reason', 'session_id', 'opportunity_id'
    )
ORDER BY ordinal_position;

-- 3. Vérifier les index
SELECT 
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
    AND tablename IN (
        'trading_sessions',
        'scan_logs',
        'opportunities',
        'trades',
        'market_context',
        'scan_errors'
    )
ORDER BY tablename, indexname;

-- 4. Vérifier les contraintes (Foreign Keys)
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
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_schema = 'public'
    AND tc.table_name IN (
        'trading_sessions',
        'scan_logs',
        'opportunities',
        'trades',
        'market_context',
        'scan_errors'
    )
ORDER BY tc.table_name, tc.constraint_name;

-- 5. Vérifier les extensions (UUID)
SELECT 
    extname,
    extversion
FROM pg_extension
WHERE extname = 'uuid-ossp';

-- 6. Compter les colonnes par table (pour vérification rapide)
SELECT 
    table_name,
    COUNT(*) as column_count
FROM information_schema.columns
WHERE table_schema = 'public'
    AND table_name IN (
        'trading_sessions',
        'config_snapshots',
        'scan_logs',
        'opportunities',
        'trades',
        'market_context',
        'scan_errors'
    )
GROUP BY table_name
ORDER BY table_name;

-- 7. Vérifier les types de données JSONB
SELECT 
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_schema = 'public'
    AND data_type = 'jsonb'
ORDER BY table_name, column_name;

