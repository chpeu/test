-- Migration: Add stagnation_positive and trailing_mfe config columns to trade_atr_metrics
-- Date: 2024-12-14
-- Purpose: Enable full logging of exit strategy configuration for ML analysis

-- Stagnation Positive configuration at trade time
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS param_stagnation_positive_enabled BOOLEAN;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS param_stagnation_positive_threshold FLOAT;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS param_stagnation_positive_timeout INT;

-- Trailing MFE configuration at trade time
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS param_trailing_mfe_enabled BOOLEAN;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS param_trailing_mfe_trigger_pct FLOAT;

-- Stagnation MFE Protection configuration
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS param_stagnation_mfe_tracking BOOLEAN;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS param_stagnation_mfe_pullback_pct FLOAT;

-- Additional metrics for STAGNATION_POSITIVE and STAGNATION_MFE_PROTECT exits
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS stagnation_positive_triggered BOOLEAN DEFAULT FALSE;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS stagnation_mfe_at_exit FLOAT;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS stagnation_pullback_at_exit FLOAT;

-- Index for filtering by exit strategy type
CREATE INDEX IF NOT EXISTS idx_trade_atr_metrics_stagnation_positive ON trade_atr_metrics(stagnation_positive_triggered) WHERE stagnation_positive_triggered = TRUE;
