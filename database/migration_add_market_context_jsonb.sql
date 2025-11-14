-- ============================================================================
-- Migration : Ajouter colonnes JSONB à market_context
-- ============================================================================
-- Date : 2025-11-12
-- Description : Ajoute les colonnes global_metrics et session_stats (JSONB)
--               pour correspondre au code Python

-- Ajouter colonnes JSONB si elles n'existent pas
DO $$
BEGIN
    -- Ajouter global_metrics JSONB
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'market_context' 
        AND column_name = 'global_metrics'
    ) THEN
        ALTER TABLE market_context ADD COLUMN global_metrics JSONB;
        RAISE NOTICE 'Colonne global_metrics ajoutée';
    ELSE
        RAISE NOTICE 'Colonne global_metrics existe déjà';
    END IF;
    
    -- Ajouter session_stats JSONB
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'market_context' 
        AND column_name = 'session_stats'
    ) THEN
        ALTER TABLE market_context ADD COLUMN session_stats JSONB;
        RAISE NOTICE 'Colonne session_stats ajoutée';
    ELSE
        RAISE NOTICE 'Colonne session_stats existe déjà';
    END IF;
END $$;

-- Vérification
SELECT 
    column_name, 
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'market_context'
AND column_name IN ('global_metrics', 'session_stats')
ORDER BY column_name;

