-- Migration: Ajout colonnes RSI Final Filter
-- Date: 2025-12-09
-- Description: Ajoute les colonnes pour tracker l'état du RSI Final Filter

-- ============================================
-- 1. Table scan_logs - Ajout colonne de blocage RSI
-- ============================================
ALTER TABLE scan_logs 
ADD COLUMN IF NOT EXISTS rsi_filter_blocked BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN scan_logs.rsi_filter_blocked IS 'True si le setup a été bloqué par le RSI Final Filter';

-- ============================================
-- 2. Table trades - Ajout colonnes config RSI
-- ============================================
ALTER TABLE trades 
ADD COLUMN IF NOT EXISTS config_rsi_filter_enabled BOOLEAN DEFAULT FALSE;

ALTER TABLE trades 
ADD COLUMN IF NOT EXISTS config_rsi_long_max FLOAT DEFAULT 70.0;

ALTER TABLE trades 
ADD COLUMN IF NOT EXISTS config_rsi_short_min FLOAT DEFAULT 30.0;

COMMENT ON COLUMN trades.config_rsi_filter_enabled IS 'État du RSI Final Filter au moment du trade';
COMMENT ON COLUMN trades.config_rsi_long_max IS 'Seuil RSI max pour LONG au moment du trade';
COMMENT ON COLUMN trades.config_rsi_short_min IS 'Seuil RSI min pour SHORT au moment du trade';

-- ============================================
-- 3. Backfill depuis config_snapshot existant
-- ============================================
UPDATE trades
SET 
    config_rsi_filter_enabled = COALESCE((config_snapshot->>'rsi_final_filter_enabled')::BOOLEAN, FALSE),
    config_rsi_long_max = COALESCE((config_snapshot->>'rsi_final_long_max')::FLOAT, 70.0),
    config_rsi_short_min = COALESCE((config_snapshot->>'rsi_final_short_min')::FLOAT, 30.0)
WHERE config_snapshot IS NOT NULL;

-- ============================================
-- 4. Index pour requêtes ML
-- ============================================
CREATE INDEX IF NOT EXISTS idx_trades_rsi_filter ON trades(config_rsi_filter_enabled);
CREATE INDEX IF NOT EXISTS idx_scan_rsi_blocked ON scan_logs(rsi_filter_blocked) WHERE rsi_filter_blocked = TRUE;

-- ============================================
-- 5. Vérification
-- ============================================
SELECT 
    'trades' as table_name,
    COUNT(*) as total_rows,
    COUNT(config_rsi_filter_enabled) as rsi_enabled_filled,
    COUNT(config_rsi_long_max) as rsi_long_max_filled,
    COUNT(config_rsi_short_min) as rsi_short_min_filled,
    ROUND(100.0 * COUNT(config_rsi_filter_enabled) / NULLIF(COUNT(*), 0), 1) as fill_rate_pct
FROM trades;
