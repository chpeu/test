-- ============================================================================
-- Migration COMPLÈTE : Toutes les modifications du schéma
-- ============================================================================
-- Date : 2025-11-12
-- Description : Migration complète pour appliquer TOUS les changements au schéma
--               Inclut toutes les nouvelles colonnes pour trades

-- ============================================================================
-- 1. Indicateurs d'entrée additionnels
-- ============================================================================

-- RSI période précédente
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_rsi_prev_1m') THEN
        ALTER TABLE trades ADD COLUMN entry_rsi_prev_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_rsi_prev_5m') THEN
        ALTER TABLE trades ADD COLUMN entry_rsi_prev_5m FLOAT;
    END IF;
END $$;

-- MACD complet
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_macd_1m') THEN
        ALTER TABLE trades ADD COLUMN entry_macd_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_macd_signal_1m') THEN
        ALTER TABLE trades ADD COLUMN entry_macd_signal_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_macd_hist_prev_1m') THEN
        ALTER TABLE trades ADD COLUMN entry_macd_hist_prev_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_macd_5m') THEN
        ALTER TABLE trades ADD COLUMN entry_macd_5m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_macd_signal_5m') THEN
        ALTER TABLE trades ADD COLUMN entry_macd_signal_5m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_macd_hist_prev_5m') THEN
        ALTER TABLE trades ADD COLUMN entry_macd_hist_prev_5m FLOAT;
    END IF;
END $$;

-- ADX DI+ et DI-
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_di_plus_1m') THEN
        ALTER TABLE trades ADD COLUMN entry_di_plus_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_di_minus_1m') THEN
        ALTER TABLE trades ADD COLUMN entry_di_minus_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_di_gap_1m') THEN
        ALTER TABLE trades ADD COLUMN entry_di_gap_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_di_plus_5m') THEN
        ALTER TABLE trades ADD COLUMN entry_di_plus_5m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_di_minus_5m') THEN
        ALTER TABLE trades ADD COLUMN entry_di_minus_5m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_di_gap_5m') THEN
        ALTER TABLE trades ADD COLUMN entry_di_gap_5m FLOAT;
    END IF;
END $$;

-- EMA
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_ema9_1m') THEN
        ALTER TABLE trades ADD COLUMN entry_ema9_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_ema21_1m') THEN
        ALTER TABLE trades ADD COLUMN entry_ema21_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_ema_diff_pct_1m') THEN
        ALTER TABLE trades ADD COLUMN entry_ema_diff_pct_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_ema9_5m') THEN
        ALTER TABLE trades ADD COLUMN entry_ema9_5m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_ema21_5m') THEN
        ALTER TABLE trades ADD COLUMN entry_ema21_5m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_ema_diff_pct_5m') THEN
        ALTER TABLE trades ADD COLUMN entry_ema_diff_pct_5m FLOAT;
    END IF;
END $$;

-- ATR absolu
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_atr_1m') THEN
        ALTER TABLE trades ADD COLUMN entry_atr_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_atr_5m') THEN
        ALTER TABLE trades ADD COLUMN entry_atr_5m FLOAT;
    END IF;
END $$;

-- Bollinger Bands
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_bb_upper_1m') THEN
        ALTER TABLE trades ADD COLUMN entry_bb_upper_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_bb_middle_1m') THEN
        ALTER TABLE trades ADD COLUMN entry_bb_middle_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_bb_lower_1m') THEN
        ALTER TABLE trades ADD COLUMN entry_bb_lower_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_bb_width_1m') THEN
        ALTER TABLE trades ADD COLUMN entry_bb_width_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_bb_distance_to_lower_1m') THEN
        ALTER TABLE trades ADD COLUMN entry_bb_distance_to_lower_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_bb_distance_to_upper_1m') THEN
        ALTER TABLE trades ADD COLUMN entry_bb_distance_to_upper_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_bb_upper_5m') THEN
        ALTER TABLE trades ADD COLUMN entry_bb_upper_5m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_bb_middle_5m') THEN
        ALTER TABLE trades ADD COLUMN entry_bb_middle_5m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_bb_lower_5m') THEN
        ALTER TABLE trades ADD COLUMN entry_bb_lower_5m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_bb_width_5m') THEN
        ALTER TABLE trades ADD COLUMN entry_bb_width_5m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_bb_distance_to_lower_5m') THEN
        ALTER TABLE trades ADD COLUMN entry_bb_distance_to_lower_5m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_bb_distance_to_upper_5m') THEN
        ALTER TABLE trades ADD COLUMN entry_bb_distance_to_upper_5m FLOAT;
    END IF;
END $$;

-- Volume additionnel
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_volume_1m') THEN
        ALTER TABLE trades ADD COLUMN entry_volume_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_volume_avg_1m') THEN
        ALTER TABLE trades ADD COLUMN entry_volume_avg_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_volume_spike_1m') THEN
        ALTER TABLE trades ADD COLUMN entry_volume_spike_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_volume_5m') THEN
        ALTER TABLE trades ADD COLUMN entry_volume_5m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_volume_avg_5m') THEN
        ALTER TABLE trades ADD COLUMN entry_volume_avg_5m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_volume_spike_5m') THEN
        ALTER TABLE trades ADD COLUMN entry_volume_spike_5m FLOAT;
    END IF;
END $$;

-- Métriques temporelles entry
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_hour_of_day') THEN
        ALTER TABLE trades ADD COLUMN entry_hour_of_day INTEGER;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_day_of_week') THEN
        ALTER TABLE trades ADD COLUMN entry_day_of_week INTEGER;
    END IF;
END $$;

-- ============================================================================
-- 2. Indicateurs de sortie
-- ============================================================================

DO $$
BEGIN
    -- RSI
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'exit_rsi_1m') THEN
        ALTER TABLE trades ADD COLUMN exit_rsi_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'exit_rsi_5m') THEN
        ALTER TABLE trades ADD COLUMN exit_rsi_5m FLOAT;
    END IF;
    
    -- MACD
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'exit_macd_hist_1m') THEN
        ALTER TABLE trades ADD COLUMN exit_macd_hist_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'exit_macd_hist_5m') THEN
        ALTER TABLE trades ADD COLUMN exit_macd_hist_5m FLOAT;
    END IF;
    
    -- ADX
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'exit_adx_1m') THEN
        ALTER TABLE trades ADD COLUMN exit_adx_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'exit_adx_5m') THEN
        ALTER TABLE trades ADD COLUMN exit_adx_5m FLOAT;
    END IF;
    
    -- ATR
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'exit_atr_pct_1m') THEN
        ALTER TABLE trades ADD COLUMN exit_atr_pct_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'exit_atr_pct_5m') THEN
        ALTER TABLE trades ADD COLUMN exit_atr_pct_5m FLOAT;
    END IF;
    
    -- Score et autres
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'exit_score') THEN
        ALTER TABLE trades ADD COLUMN exit_score FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'exit_volume_ratio_1m') THEN
        ALTER TABLE trades ADD COLUMN exit_volume_ratio_1m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'exit_volume_ratio_5m') THEN
        ALTER TABLE trades ADD COLUMN exit_volume_ratio_5m FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'exit_spread_pct') THEN
        ALTER TABLE trades ADD COLUMN exit_spread_pct FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'exit_balance_score') THEN
        ALTER TABLE trades ADD COLUMN exit_balance_score FLOAT;
    END IF;
    
    -- Variation de prix
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_to_exit_price_change_pct') THEN
        ALTER TABLE trades ADD COLUMN entry_to_exit_price_change_pct FLOAT;
    END IF;
    
    -- Métriques temporelles exit
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'exit_hour_of_day') THEN
        ALTER TABLE trades ADD COLUMN exit_hour_of_day INTEGER;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'exit_day_of_week') THEN
        ALTER TABLE trades ADD COLUMN exit_day_of_week INTEGER;
    END IF;
END $$;

-- ============================================================================
-- 3. Métriques de performance additionnelles
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_to_max_profit_price_change_pct') THEN
        ALTER TABLE trades ADD COLUMN entry_to_max_profit_price_change_pct FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'entry_to_max_loss_price_change_pct') THEN
        ALTER TABLE trades ADD COLUMN entry_to_max_loss_price_change_pct FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'max_drawdown_pct') THEN
        ALTER TABLE trades ADD COLUMN max_drawdown_pct FLOAT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'max_drawdown_usdt') THEN
        ALTER TABLE trades ADD COLUMN max_drawdown_usdt FLOAT;
    END IF;
END $$;

-- ============================================================================
-- 4. Configuration snapshot
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_snapshot') THEN
        ALTER TABLE trades ADD COLUMN config_snapshot JSONB;
    END IF;
END $$;

-- ============================================================================
-- 5. Early Invalidation (détails)
-- ============================================================================

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

-- ============================================================================
-- 6. Market Context - Colonnes JSONB
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'market_context' AND column_name = 'global_metrics') THEN
        ALTER TABLE market_context ADD COLUMN global_metrics JSONB;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'market_context' AND column_name = 'session_stats') THEN
        ALTER TABLE market_context ADD COLUMN session_stats JSONB;
    END IF;
END $$;

-- ============================================================================
-- 7. Index pour les nouvelles colonnes
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_trade_entry_hour ON trades(entry_hour_of_day) WHERE entry_hour_of_day IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trade_entry_day ON trades(entry_day_of_week) WHERE entry_day_of_week IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trade_exit_hour ON trades(exit_hour_of_day) WHERE exit_hour_of_day IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trade_exit_day ON trades(exit_day_of_week) WHERE exit_day_of_week IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trade_early_invalidation ON trades(early_invalidation_triggered) WHERE early_invalidation_triggered = TRUE;

-- ============================================================================
-- Vérification finale
-- ============================================================================

DO $$
DECLARE
    total_columns INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_columns
    FROM information_schema.columns
    WHERE table_name = 'trades';
    
    RAISE NOTICE 'Migration terminée. Nombre total de colonnes dans trades: %', total_columns;
    RAISE NOTICE 'Vérifiez que toutes les colonnes sont présentes avec: SELECT column_name FROM information_schema.columns WHERE table_name = ''trades'' ORDER BY column_name;';
END $$;

-- Afficher toutes les colonnes de trades
SELECT 
    column_name, 
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'trades'
ORDER BY column_name;

