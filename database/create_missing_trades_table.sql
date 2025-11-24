-- ============================================================================
-- TRADE CURSOR v7.0 - CREATE MISSING TRADES TABLE
-- Script pour créer la table trades manquante
-- ============================================================================

BEGIN;

-- ============================================================================
-- TABLE : trades
-- ============================================================================
-- Log des trades exécutés avec résultats
-- Base pour Predictive Model

CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    opportunity_id UUID REFERENCES opportunities(id) ON DELETE SET NULL,
    scan_log_id BIGINT,
    session_id UUID REFERENCES trading_sessions(id) ON DELETE SET NULL,
    symbol VARCHAR(30) NOT NULL,
    direction VARCHAR(10) NOT NULL,

    timestamp_entry TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    entry_price DOUBLE PRECISION NOT NULL,
    size_usdt DOUBLE PRECISION NOT NULL,
    tp_price DOUBLE PRECISION NOT NULL,
    sl_price DOUBLE PRECISION NOT NULL,
    tp_sl_mode VARCHAR(20),

    entry_rsi_1m DOUBLE PRECISION,
    entry_rsi_5m DOUBLE PRECISION,
    entry_macd_hist_1m DOUBLE PRECISION,
    entry_macd_hist_5m DOUBLE PRECISION,
    entry_adx_1m DOUBLE PRECISION,
    entry_adx_5m DOUBLE PRECISION,
    entry_atr_pct_1m DOUBLE PRECISION,
    entry_atr_pct_5m DOUBLE PRECISION,
    entry_score DOUBLE PRECISION,
    entry_volume_ratio_1m DOUBLE PRECISION,
    entry_volume_ratio_5m DOUBLE PRECISION,
    entry_spread_pct DOUBLE PRECISION,
    entry_balance_score DOUBLE PRECISION,
    entry_conditions TEXT[],
    entry_condition_count INTEGER,

    timestamp_exit TIMESTAMPTZ,
    exit_price DOUBLE PRECISION,
    exit_reason VARCHAR(30),

    duration_seconds DOUBLE PRECISION,
    pnl_pct DOUBLE PRECISION,
    pnl_usdt DOUBLE PRECISION,
    gross_pnl_usdt DOUBLE PRECISION,
    slippage_pct DOUBLE PRECISION,
    slippage_usdt DOUBLE PRECISION,
    fees_usdt DOUBLE PRECISION,
    net_pnl_usdt DOUBLE PRECISION,
    net_pnl_pct DOUBLE PRECISION,
    win BOOLEAN,

    break_even_set BOOLEAN DEFAULT FALSE,
    break_even_triggered_at TIMESTAMPTZ,
    partial_tp_executed BOOLEAN DEFAULT FALSE,
    partial_tp_triggered_at TIMESTAMPTZ,
    partial_tp_profit DOUBLE PRECISION,
    partial_tp_percent DOUBLE PRECISION,
    tp_escalier_levels_executed INTEGER DEFAULT 0,
    tp_escalier_profits DOUBLE PRECISION DEFAULT 0,
    trailing_stop_activated BOOLEAN DEFAULT FALSE,
    trailing_stop_triggered_at TIMESTAMPTZ,

    max_favorable_excursion DOUBLE PRECISION,
    max_adverse_excursion DOUBLE PRECISION,
    max_favorable_excursion_usdt DOUBLE PRECISION,
    max_adverse_excursion_usdt DOUBLE PRECISION,
    risk_reward_ratio DOUBLE PRECISION,
    profit_factor DOUBLE PRECISION,

    entry_book_depth DOUBLE PRECISION,
    entry_bid_vol DOUBLE PRECISION,
    entry_ask_vol DOUBLE PRECISION,
    entry_orderbook_imbalance DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Champs additionnels utilisés par l'Analytics DataLogger (sync PG)
    entry_rsi_prev_1m DOUBLE PRECISION,
    entry_rsi_prev_5m DOUBLE PRECISION,
    entry_macd_1m DOUBLE PRECISION,
    entry_macd_signal_1m DOUBLE PRECISION,
    entry_macd_hist_prev_1m DOUBLE PRECISION,
    entry_macd_5m DOUBLE PRECISION,
    entry_macd_signal_5m DOUBLE PRECISION,
    entry_macd_hist_prev_5m DOUBLE PRECISION,
    entry_di_plus_1m DOUBLE PRECISION,
    entry_di_minus_1m DOUBLE PRECISION,
    entry_di_gap_1m DOUBLE PRECISION,
    entry_di_plus_5m DOUBLE PRECISION,
    entry_di_minus_5m DOUBLE PRECISION,
    entry_di_gap_5m DOUBLE PRECISION,
    entry_ema9_1m DOUBLE PRECISION,
    entry_ema21_1m DOUBLE PRECISION,
    entry_ema_diff_pct_1m DOUBLE PRECISION,
    entry_ema9_5m DOUBLE PRECISION,
    entry_ema21_5m DOUBLE PRECISION,
    entry_ema_diff_pct_5m DOUBLE PRECISION,
    entry_atr_1m DOUBLE PRECISION,
    entry_atr_5m DOUBLE PRECISION,
    entry_bb_upper_1m DOUBLE PRECISION,
    entry_bb_middle_1m DOUBLE PRECISION,
    entry_bb_lower_1m DOUBLE PRECISION,
    entry_bb_width_1m DOUBLE PRECISION,
    entry_bb_distance_to_lower_1m DOUBLE PRECISION,
    entry_bb_distance_to_upper_1m DOUBLE PRECISION,
    entry_bb_upper_5m DOUBLE PRECISION,
    entry_bb_middle_5m DOUBLE PRECISION,
    entry_bb_lower_5m DOUBLE PRECISION,
    entry_bb_width_5m DOUBLE PRECISION,
    entry_bb_distance_to_lower_5m DOUBLE PRECISION,
    entry_bb_distance_to_upper_5m DOUBLE PRECISION,
    entry_volume_1m DOUBLE PRECISION,
    entry_volume_avg_1m DOUBLE PRECISION,
    entry_volume_spike_1m DOUBLE PRECISION,
    entry_volume_5m DOUBLE PRECISION,
    entry_volume_avg_5m DOUBLE PRECISION,
    entry_volume_spike_5m DOUBLE PRECISION,
    entry_hour_of_day INTEGER,
    entry_day_of_week INTEGER,
    entry_recent_volume DOUBLE PRECISION,
    entry_vol5 DOUBLE PRECISION,
    entry_vol15 DOUBLE PRECISION,
    entry_scalability_score DOUBLE PRECISION,

    exit_rsi_1m DOUBLE PRECISION,
    exit_rsi_5m DOUBLE PRECISION,
    exit_macd_hist_1m DOUBLE PRECISION,
    exit_macd_hist_5m DOUBLE PRECISION,
    exit_adx_1m DOUBLE PRECISION,
    exit_adx_5m DOUBLE PRECISION,
    exit_atr_pct_1m DOUBLE PRECISION,
    exit_atr_pct_5m DOUBLE PRECISION,
    exit_score DOUBLE PRECISION,
    exit_volume_ratio_1m DOUBLE PRECISION,
    exit_volume_ratio_5m DOUBLE PRECISION,
    exit_spread_pct DOUBLE PRECISION,
    exit_balance_score DOUBLE PRECISION,
    entry_to_exit_price_change_pct DOUBLE PRECISION,
    exit_hour_of_day INTEGER,
    exit_day_of_week INTEGER,
    exit_recent_volume DOUBLE PRECISION,
    exit_vol5 DOUBLE PRECISION,
    exit_vol15 DOUBLE PRECISION,

    entry_to_max_profit_price_change_pct DOUBLE PRECISION,
    entry_to_max_loss_price_change_pct DOUBLE PRECISION,
    max_drawdown_pct DOUBLE PRECISION,
    max_drawdown_usdt DOUBLE PRECISION,

    config_snapshot JSONB,
    early_invalidation_triggered BOOLEAN DEFAULT FALSE,
    early_invalidation_triggered_at TIMESTAMPTZ,
    early_invalidation_threshold DOUBLE PRECISION,
    early_invalidation_elapsed DOUBLE PRECISION,
    early_invalidation_atr_pct DOUBLE PRECISION,
    early_invalidation_pnl_pct DOUBLE PRECISION
);

-- Index
CREATE INDEX IF NOT EXISTS idx_trade_timestamp_entry ON trades(timestamp_entry DESC);
CREATE INDEX IF NOT EXISTS idx_trade_timestamp_exit ON trades(timestamp_exit DESC) WHERE timestamp_exit IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trade_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trade_direction ON trades(direction);
CREATE INDEX IF NOT EXISTS idx_trade_exit_reason ON trades(exit_reason);
CREATE INDEX IF NOT EXISTS idx_trade_session ON trades(session_id);
CREATE INDEX IF NOT EXISTS idx_trade_opportunity ON trades(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_trade_win ON trades(win);
CREATE INDEX IF NOT EXISTS idx_trade_pnl_usdt ON trades(net_pnl_usdt DESC);
CREATE INDEX IF NOT EXISTS idx_trade_duration ON trades(duration_seconds) WHERE duration_seconds IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trade_entry_hour ON trades(entry_hour_of_day) WHERE entry_hour_of_day IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trade_entry_day ON trades(entry_day_of_week) WHERE entry_day_of_week IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trade_exit_hour ON trades(exit_hour_of_day) WHERE exit_hour_of_day IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trade_exit_day ON trades(exit_day_of_week) WHERE exit_day_of_week IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trade_entry_scalability_score ON trades(entry_scalability_score) WHERE entry_scalability_score IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trade_early_invalidation ON trades(early_invalidation_triggered) WHERE early_invalidation_triggered = TRUE;

-- Index sur date (nécessite fonction IMMUTABLE - devrait déjà exister)
CREATE OR REPLACE FUNCTION extract_date_immutable(timestamptz)
RETURNS DATE AS $$
    SELECT DATE($1);
$$ LANGUAGE SQL IMMUTABLE;

CREATE INDEX IF NOT EXISTS idx_trade_date_entry ON trades(extract_date_immutable(timestamp_entry));

-- Trigger pour updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_trades_updated_at ON trades;
CREATE TRIGGER update_trades_updated_at
    BEFORE UPDATE ON trades
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMIT;

-- ============================================================================
-- VÉRIFICATION
-- ============================================================================

DO $$ 
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'trades') THEN
        RAISE NOTICE '';
        RAISE NOTICE '========================================';
        RAISE NOTICE 'Table trades creee avec succes !';
        RAISE NOTICE '========================================';
        RAISE NOTICE '';
    ELSE
        RAISE EXCEPTION 'Erreur : La table trades n''a pas pu etre creee';
    END IF;
END $$;

