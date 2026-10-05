-- ============================================================================
-- Migration: Add entry_atr_pct_used and entry_atr_blended columns
-- Table: trade_atr_metrics
-- Date: 2024-12-29
-- Description: Ajoute les colonnes pour persister l'ATR% effectivement utilisé
--              (après clamp min/max) et l'ATR blendé (70% 1m + 30% 5m)
-- ============================================================================

-- Colonne entry_atr_pct_used: ATR% après clamping entre atr_min et atr_max
-- C'est la valeur réellement utilisée pour calculer TP/SL en mode ATR
ALTER TABLE trade_atr_metrics 
ADD COLUMN IF NOT EXISTS entry_atr_pct_used DOUBLE PRECISION;

COMMENT ON COLUMN trade_atr_metrics.entry_atr_pct_used IS 
    'ATR % effectivement utilisé à l''entrée, après clamping entre atr_min et atr_max';

-- Colonne entry_atr_blended: ATR blendé (0.7 * ATR_1m + 0.3 * ATR_5m)
-- Valeur brute avant conversion en pourcentage
ALTER TABLE trade_atr_metrics 
ADD COLUMN IF NOT EXISTS entry_atr_blended DOUBLE PRECISION;

COMMENT ON COLUMN trade_atr_metrics.entry_atr_blended IS 
    'ATR blendé à l''entrée (0.7 * ATR_1m + 0.3 * ATR_5m), valeur absolue en USDT';

-- Index optionnel pour analyses par ATR% utilisé
CREATE INDEX IF NOT EXISTS idx_trade_atr_metrics_atr_pct_used 
ON trade_atr_metrics(entry_atr_pct_used) 
WHERE entry_atr_pct_used IS NOT NULL;

-- ============================================================================
-- Vérification post-migration
-- ============================================================================
-- SELECT column_name, data_type 
-- FROM information_schema.columns 
-- WHERE table_name = 'trade_atr_metrics' 
--   AND column_name IN ('entry_atr_pct_used', 'entry_atr_blended');
