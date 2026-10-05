-- Migration: Stagnation Positive Exit
-- Date: 2025-12-14
-- Description: Ajoute les colonnes pour la fonctionnalité de sortie positive en stagnation

-- ============================================================
-- 1. Colonnes de configuration (snapshot des paramètres au moment du trade)
-- ============================================================
ALTER TABLE trades ADD COLUMN IF NOT EXISTS config_stagnation_positive_exit_enabled BOOLEAN DEFAULT NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS config_stagnation_positive_threshold DOUBLE PRECISION DEFAULT NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS config_stagnation_positive_timeout_seconds INTEGER DEFAULT NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS config_stagnation_use_mfe_tracking BOOLEAN DEFAULT NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS config_stagnation_mfe_pullback_pct DOUBLE PRECISION DEFAULT NULL;

-- ============================================================
-- 2. Colonnes de tracking (métriques à la sortie)
-- ============================================================
ALTER TABLE trades ADD COLUMN IF NOT EXISTS stagnation_mfe_at_exit DOUBLE PRECISION DEFAULT NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS stagnation_positive_triggered BOOLEAN DEFAULT FALSE;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS stagnation_pullback_at_exit DOUBLE PRECISION DEFAULT NULL;

-- ============================================================
-- 3. Index pour analyse des performances
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_trade_stagnation_positive ON trades (stagnation_positive_triggered) WHERE stagnation_positive_triggered = true;
CREATE INDEX IF NOT EXISTS idx_trade_exit_reason_stagnation ON trades (exit_reason) WHERE exit_reason LIKE 'STAGNATION%';

-- ============================================================
-- 4. Commentaires explicatifs
-- ============================================================
COMMENT ON COLUMN trades.config_stagnation_positive_exit_enabled IS 'Config: Sortie positive anticipée activée';
COMMENT ON COLUMN trades.config_stagnation_positive_threshold IS 'Config: Seuil de profit minimum pour sortie positive (%)';
COMMENT ON COLUMN trades.config_stagnation_positive_timeout_seconds IS 'Config: Timeout réduit si en profit (secondes)';
COMMENT ON COLUMN trades.config_stagnation_use_mfe_tracking IS 'Config: Tracking MFE pour protection activé';
COMMENT ON COLUMN trades.config_stagnation_mfe_pullback_pct IS 'Config: Seuil de pullback depuis MFE pour sortie (%)';
COMMENT ON COLUMN trades.stagnation_mfe_at_exit IS 'MFE atteint au moment de la sortie stagnation (%)';
COMMENT ON COLUMN trades.stagnation_positive_triggered IS 'True si sortie déclenchée par stagnation positive';
COMMENT ON COLUMN trades.stagnation_pullback_at_exit IS 'Pullback depuis MFE au moment de la sortie (%)';

-- ============================================================
-- 5. Vérification
-- ============================================================
DO $$
BEGIN
    RAISE NOTICE '✅ Migration stagnation_positive_exit terminée';
    RAISE NOTICE '   - 5 colonnes config_* ajoutées';
    RAISE NOTICE '   - 3 colonnes tracking ajoutées';
    RAISE NOTICE '   - 2 index créés';
END $$;
