-- Migration 003: Create trade_events table for Phase 2H.6
-- Historise tous les changements d'état d'un trade pour analyse post-mortem

CREATE TABLE IF NOT EXISTS trade_events (
    id SERIAL PRIMARY KEY,
    trade_id UUID REFERENCES trades(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    event_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    price_at_event FLOAT,
    pnl_pct_at_event FLOAT,
    pnl_usdt_at_event FLOAT,
    details JSONB,
    
    -- Index pour requêtes rapides
    CONSTRAINT valid_event_type CHECK (event_type IN (
        'ENTRY',
        'BE_TRIGGERED',
        'TRAILING_ACTIVATED', 
        'TRAILING_SL_MOVED',
        'MAX_PNL_REACHED',
        'MIN_PNL_REACHED',
        'PARTIAL_TP',
        'TP_ESCALIER_LEVEL',
        'STAGNATION_DETECTED',
        'STAGNATION_MFE_PROTECT',
        'TRAILING_MFE_TRIGGERED',
        'SL_EXCHANGE_SET',
        'EXIT'
    ))
);

-- Index pour recherche par trade_id
CREATE INDEX IF NOT EXISTS idx_trade_events_trade_id ON trade_events(trade_id);

-- Index pour recherche par type d'événement
CREATE INDEX IF NOT EXISTS idx_trade_events_type ON trade_events(event_type);

-- Index pour recherche par timestamp
CREATE INDEX IF NOT EXISTS idx_trade_events_timestamp ON trade_events(event_timestamp);

-- Commentaires
COMMENT ON TABLE trade_events IS 'Historique des événements pendant un trade (Phase 2H.6)';
COMMENT ON COLUMN trade_events.event_type IS 'Type: ENTRY, BE_TRIGGERED, TRAILING_ACTIVATED, etc.';
COMMENT ON COLUMN trade_events.details IS 'Détails JSON: sold_pct, new_sl, trigger_reason, etc.';
