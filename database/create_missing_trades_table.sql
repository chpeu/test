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
    scan_log_id BIGINT,  -- Référence à scan_logs (sans FK pour performance)
    session_id UUID REFERENCES trading_sessions(id) ON DELETE SET NULL,
    symbol VARCHAR(30) NOT NULL,
    direction VARCHAR(10) NOT NULL,  -- LONG, SHORT
    
    -- ========================================
    -- Entry
    -- ========================================
    
    timestamp_entry TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    entry_price FLOAT NOT NULL,
    size_usdt FLOAT NOT NULL,
    tp_price FLOAT NOT NULL,
    sl_price FLOAT NOT NULL,
    tp_sl_mode VARCHAR(20),
    
    -- Snapshot indicateurs au moment entry (pour ML)
    entry_rsi_1m FLOAT,
    entry_rsi_5m FLOAT,
    entry_macd_hist_1m FLOAT,
    entry_macd_hist_5m FLOAT,
    entry_adx_1m FLOAT,
    entry_adx_5m FLOAT,
    entry_atr_pct_1m FLOAT,
    entry_atr_pct_5m FLOAT,
    entry_score FLOAT,
    entry_volume_ratio_1m FLOAT,
    entry_volume_ratio_5m FLOAT,
    entry_spread_pct FLOAT,
    entry_balance_score FLOAT,
    
    -- Conditions au entry
    entry_conditions TEXT[],
    entry_condition_count INTEGER,
    
    -- ========================================
    -- Exit
    -- ========================================
    
    timestamp_exit TIMESTAMPTZ,
    exit_price FLOAT,
    exit_reason VARCHAR(30),  -- TP_HIT, SL_HIT, EARLY_INVALIDATION, MANUAL, TIMEOUT
    
    -- ========================================
    -- Résultats
    -- ========================================
    
    duration_seconds FLOAT,
    pnl_pct FLOAT,
    pnl_usdt FLOAT,
    gross_pnl_usdt FLOAT,
    slippage_pct FLOAT,
    slippage_usdt FLOAT,
    fees_usdt FLOAT,
    net_pnl_usdt FLOAT,
    net_pnl_pct FLOAT,
    
    -- Label ML principal
    win BOOLEAN,  -- True si net_pnl_usdt > 0
    
    -- ========================================
    -- Events pendant position
    -- ========================================
    
    break_even_set BOOLEAN DEFAULT FALSE,
    break_even_triggered_at TIMESTAMPTZ,
    partial_tp_executed BOOLEAN DEFAULT FALSE,
    partial_tp_triggered_at TIMESTAMPTZ,
    partial_tp_profit FLOAT,
    partial_tp_percent FLOAT,  -- % de position vendue
    tp_escalier_levels_executed INTEGER DEFAULT 0,
    tp_escalier_profits FLOAT DEFAULT 0,
    trailing_stop_activated BOOLEAN DEFAULT FALSE,
    trailing_stop_triggered_at TIMESTAMPTZ,
    
    -- ========================================
    -- Métriques position
    -- ========================================
    
    max_favorable_excursion FLOAT,  -- Meilleur prix atteint (%)
    max_adverse_excursion FLOAT,    -- Pire prix atteint (%)
    max_favorable_excursion_usdt FLOAT,
    max_adverse_excursion_usdt FLOAT,
    
    -- ========================================
    -- Métriques de qualité
    -- ========================================
    
    risk_reward_ratio FLOAT,  -- (TP - Entry) / (Entry - SL)
    profit_factor FLOAT,  -- Pour analyse session
    
    -- ========================================
    -- Scalability data au entry
    -- ========================================
    
    entry_book_depth FLOAT,
    entry_bid_vol FLOAT,
    entry_ask_vol FLOAT,
    entry_orderbook_imbalance FLOAT,
    
    -- Métadonnées
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index
CREATE INDEX IF NOT EXISTS idx_trade_timestamp_entry ON trades(timestamp_entry DESC);
CREATE INDEX IF NOT EXISTS idx_trade_timestamp_exit ON trades(timestamp_exit DESC) WHERE timestamp_exit IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trade_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trade_win ON trades(win);
CREATE INDEX IF NOT EXISTS idx_trade_opportunity ON trades(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_trade_direction ON trades(direction);
CREATE INDEX IF NOT EXISTS idx_trade_exit_reason ON trades(exit_reason);
CREATE INDEX IF NOT EXISTS idx_trade_session ON trades(session_id);
CREATE INDEX IF NOT EXISTS idx_trade_pnl_usdt ON trades(net_pnl_usdt DESC);
CREATE INDEX IF NOT EXISTS idx_trade_duration ON trades(duration_seconds) WHERE duration_seconds IS NOT NULL;

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

