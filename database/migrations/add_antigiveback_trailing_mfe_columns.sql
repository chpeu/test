-- Migration: Anti-Giveback / Trailing MFE columns (Trades)
-- Date: 2026-01-09
-- Description: Ajoute colonnes nécessaires pour analyser l'impact des protections anti-giveback.
--
-- Objectifs:
-- - Snapshot des paramètres utilisés au moment du trade (config_*)
-- - Tracking runtime (trailing_mfe_triggered + infos trigger)
-- - Garder le schéma compatible avec le code existant (IF NOT EXISTS)

-- ============================================================
-- 1) Colonnes CONFIG (snapshot)
-- ============================================================
ALTER TABLE trades ADD COLUMN IF NOT EXISTS config_trailing_mfe_enabled BOOLEAN DEFAULT NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS config_trailing_mfe_trigger_pct DOUBLE PRECISION DEFAULT NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS config_trailing_mfe_lock_in_pct DOUBLE PRECISION DEFAULT NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS config_partial_tp_be_lock_in_pct DOUBLE PRECISION DEFAULT NULL;

-- ============================================================
-- 2) Colonnes TRACKING (runtime)
-- ============================================================
ALTER TABLE trades ADD COLUMN IF NOT EXISTS trailing_mfe_triggered BOOLEAN DEFAULT FALSE;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS trailing_mfe_triggered_at TIMESTAMPTZ DEFAULT NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS trailing_mfe_trigger_pnl_pct DOUBLE PRECISION DEFAULT NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS trailing_mfe_trigger_price DOUBLE PRECISION DEFAULT NULL;

-- Optionnel: garder la valeur de SL appliquée au trigger (debug / analyse)
ALTER TABLE trades ADD COLUMN IF NOT EXISTS trailing_mfe_new_sl DOUBLE PRECISION DEFAULT NULL;

-- ============================================================
-- 3) Index utiles pour analyse
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_trade_trailing_mfe_triggered ON trades (trailing_mfe_triggered) WHERE trailing_mfe_triggered = TRUE;
CREATE INDEX IF NOT EXISTS idx_trade_exit_reason_sl_exchange ON trades (exit_reason) WHERE exit_reason = 'SL_EXCHANGE';

-- ============================================================
-- 4) Commentaires
-- ============================================================
COMMENT ON COLUMN trades.config_trailing_mfe_enabled IS 'Config: trailing MFE activé pour ce trade';
COMMENT ON COLUMN trades.config_trailing_mfe_trigger_pct IS 'Config: seuil MFE (%) pour déplacer SL (Trailing MFE)';
COMMENT ON COLUMN trades.config_trailing_mfe_lock_in_pct IS 'Config: lock-in (%) appliqué au SL lorsque Trailing MFE déclenche';
COMMENT ON COLUMN trades.config_partial_tp_be_lock_in_pct IS 'Config: lock-in (%) appliqué au SL après TP partiel';

COMMENT ON COLUMN trades.trailing_mfe_triggered IS 'True si Trailing MFE a déclenché (SL déplacé)';
COMMENT ON COLUMN trades.trailing_mfe_triggered_at IS 'Timestamp du déclenchement Trailing MFE';
COMMENT ON COLUMN trades.trailing_mfe_trigger_pnl_pct IS 'PnL% au moment du déclenchement Trailing MFE';
COMMENT ON COLUMN trades.trailing_mfe_trigger_price IS 'Prix au moment du déclenchement Trailing MFE';
COMMENT ON COLUMN trades.trailing_mfe_new_sl IS 'SL appliqué au moment du déclenchement Trailing MFE';

-- ============================================================
-- 5) Migration terminée
-- ============================================================
-- Migration antigiveback/trailing_mfe terminée avec succès
