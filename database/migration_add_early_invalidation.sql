-- ============================================================================
-- Migration : Ajouter colonnes early_invalidation à trades
-- ============================================================================
-- Date : 2025-11-12
-- Description : Ajoute les colonnes pour stocker les détails de l'invalidation précoce

-- Early Invalidation (détails)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'early_invalidation_triggered') THEN
        ALTER TABLE trades ADD COLUMN early_invalidation_triggered BOOLEAN DEFAULT FALSE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'early_invalidation_triggered_at') THEN
        ALTER TABLE trades ADD COLUMN early_invalidation_triggered_at TIMESTAMPTZ;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'early_invalidation_threshold') THEN
        ALTER TABLE trades ADD COLUMN early_invalidation_threshold FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'early_invalidation_elapsed') THEN
        ALTER TABLE trades ADD COLUMN early_invalidation_elapsed FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'early_invalidation_atr_pct') THEN
        ALTER TABLE trades ADD COLUMN early_invalidation_atr_pct FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'early_invalidation_pnl_pct') THEN
        ALTER TABLE trades ADD COLUMN early_invalidation_pnl_pct FLOAT;
    END IF;
END $$;

-- Index pour requêtes sur early_invalidation
CREATE INDEX IF NOT EXISTS idx_trade_early_invalidation ON trades(early_invalidation_triggered) WHERE early_invalidation_triggered = TRUE;

-- Vérification
DO $$
BEGIN
    RAISE NOTICE 'Migration early_invalidation terminée.';
END $$;

SELECT 
    column_name, 
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'trades'
AND column_name LIKE 'early_invalidation%'
ORDER BY column_name;

