-- Migration 004: Add partial_tp columns to trade_atr_metrics
-- These columns were referenced in code but may not exist

ALTER TABLE trade_atr_metrics 
ADD COLUMN IF NOT EXISTS partial_tp_profit FLOAT;

ALTER TABLE trade_atr_metrics 
ADD COLUMN IF NOT EXISTS partial_tp_percent FLOAT;

ALTER TABLE trade_atr_metrics 
ADD COLUMN IF NOT EXISTS partial_tp_executed BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN trade_atr_metrics.partial_tp_profit IS 'Profit from partial TP execution in USDT';
COMMENT ON COLUMN trade_atr_metrics.partial_tp_percent IS 'Percentage of position sold in partial TP';
COMMENT ON COLUMN trade_atr_metrics.partial_tp_executed IS 'Whether partial TP was executed';
