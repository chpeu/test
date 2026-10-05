-- ============================================================================
-- MIGRATION: Add Market Regime Selector & Trading Circuit Breaker columns
-- Sprint 1 - 07/12/2025
-- ============================================================================
-- Ces colonnes permettent d'analyser les performances par régime de marché
-- et d'évaluer l'efficacité du circuit breaker pour optimisation ML.
-- ============================================================================

-- ============================================================================
-- TABLE scan_logs : Contexte régime au moment du scan
-- ============================================================================

-- Régime de marché actif au moment du scan
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS market_regime VARCHAR(20);
COMMENT ON COLUMN scan_logs.market_regime IS 'Régime marché: CALME, NORMAL, VOLATILE, CHOPPY, UNKNOWN';

-- ATR moyen du marché (calculé sur top pairs)
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS market_regime_avg_atr FLOAT;
COMMENT ON COLUMN scan_logs.market_regime_avg_atr IS 'ATR moyen du marché en % au moment du scan';

-- ADX moyen du marché
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS market_regime_avg_adx FLOAT;
COMMENT ON COLUMN scan_logs.market_regime_avg_adx IS 'ADX moyen du marché au moment du scan';

-- Index pour analyse par régime
CREATE INDEX IF NOT EXISTS idx_scan_market_regime ON scan_logs(market_regime) WHERE market_regime IS NOT NULL;

-- ============================================================================
-- TABLE trades : Contexte régime et circuit breaker au moment du trade
-- ============================================================================

-- === Market Regime au entry ===

-- Régime actif au moment de l'entrée
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_market_regime VARCHAR(20);
COMMENT ON COLUMN trades.entry_market_regime IS 'Régime marché au entry: CALME, NORMAL, VOLATILE, CHOPPY, UNKNOWN';

-- ATR moyen du marché au entry
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_market_regime_avg_atr FLOAT;
COMMENT ON COLUMN trades.entry_market_regime_avg_atr IS 'ATR moyen du marché en % au entry';

-- ADX moyen du marché au entry
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_market_regime_avg_adx FLOAT;
COMMENT ON COLUMN trades.entry_market_regime_avg_adx IS 'ADX moyen du marché au entry';

-- Score minimum requis appliqué (peut varier selon régime)
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_min_score_required FLOAT;
COMMENT ON COLUMN trades.entry_min_score_required IS 'Score minimum requis au entry (ajusté par régime)';

-- Multiplicateurs ATR appliqués
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_atr_mult_sl FLOAT;
COMMENT ON COLUMN trades.entry_atr_mult_sl IS 'Multiplicateur ATR pour SL au entry';

ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_atr_mult_tp FLOAT;
COMMENT ON COLUMN trades.entry_atr_mult_tp IS 'Multiplicateur ATR pour TP au entry';

-- === Trading Circuit Breaker au entry ===

-- État du circuit breaker au moment du trade
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_cb_state VARCHAR(20);
COMMENT ON COLUMN trades.entry_cb_state IS 'État circuit breaker: ACTIVE, PAUSED, STOPPED';

-- Pertes consécutives au moment du trade
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_consecutive_losses INTEGER DEFAULT 0;
COMMENT ON COLUMN trades.entry_consecutive_losses IS 'Nombre de pertes consécutives avant ce trade';

-- PnL journalier au moment du trade
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_daily_pnl_pct FLOAT DEFAULT 0;
COMMENT ON COLUMN trades.entry_daily_pnl_pct IS 'PnL journalier en % au moment du trade';

-- Score boost appliqué par le circuit breaker
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_cb_score_boost FLOAT DEFAULT 0;
COMMENT ON COLUMN trades.entry_cb_score_boost IS 'Score boost appliqué par circuit breaker (0 si désactivé)';

-- === Index pour analyses ML ===

-- Performance par régime
CREATE INDEX IF NOT EXISTS idx_trade_market_regime ON trades(entry_market_regime) WHERE entry_market_regime IS NOT NULL;

-- Analyse par régime + direction
CREATE INDEX IF NOT EXISTS idx_trade_regime_direction ON trades(entry_market_regime, direction) WHERE entry_market_regime IS NOT NULL;

-- Analyse par régime + win/loss
CREATE INDEX IF NOT EXISTS idx_trade_regime_win ON trades(entry_market_regime, win) WHERE entry_market_regime IS NOT NULL;

-- Analyse circuit breaker
CREATE INDEX IF NOT EXISTS idx_trade_cb_state ON trades(entry_cb_state) WHERE entry_cb_state IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trade_consecutive_losses ON trades(entry_consecutive_losses) WHERE entry_consecutive_losses > 0;

-- ============================================================================
-- TABLE circuit_breaker_events (NOUVELLE) : Historique des événements CB
-- ============================================================================
-- Utile pour analyser l'efficacité des pauses et corrélation avec performance

CREATE TABLE IF NOT EXISTS circuit_breaker_events (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_id UUID REFERENCES trading_sessions(id) ON DELETE SET NULL,
    
    -- Type d'événement
    event_type VARCHAR(20) NOT NULL,  -- 'pause', 'resume', 'stop', 'reset'
    
    -- Raison de l'événement
    reason TEXT NOT NULL,
    
    -- État avant/après
    state_before VARCHAR(20) NOT NULL,  -- ACTIVE, PAUSED, STOPPED
    state_after VARCHAR(20) NOT NULL,
    
    -- Métriques au moment de l'événement
    consecutive_losses INTEGER DEFAULT 0,
    daily_pnl_pct FLOAT DEFAULT 0,
    daily_pnl_usdt FLOAT DEFAULT 0,
    daily_trades INTEGER DEFAULT 0,
    daily_wins INTEGER DEFAULT 0,
    daily_losses INTEGER DEFAULT 0,
    score_boost FLOAT DEFAULT 0,
    
    -- Durée de pause (si resume)
    pause_duration_seconds FLOAT,
    
    -- Trades pendant la pause (si resume)
    trades_avoided INTEGER,  -- Opportunités détectées mais non exécutées
    
    -- Métadonnées
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index pour analyses
CREATE INDEX IF NOT EXISTS idx_cb_events_timestamp ON circuit_breaker_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_cb_events_type ON circuit_breaker_events(event_type);
CREATE INDEX IF NOT EXISTS idx_cb_events_session ON circuit_breaker_events(session_id);

-- ============================================================================
-- TABLE market_regime_history (NOUVELLE) : Historique des changements de régime
-- ============================================================================
-- Utile pour analyser les transitions et corrélation avec performance

CREATE TABLE IF NOT EXISTS market_regime_history (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_id UUID REFERENCES trading_sessions(id) ON DELETE SET NULL,
    
    -- Régimes
    old_regime VARCHAR(20),  -- CALME, NORMAL, VOLATILE, CHOPPY, UNKNOWN
    new_regime VARCHAR(20) NOT NULL,
    
    -- Métriques au moment du changement
    avg_atr FLOAT NOT NULL,  -- ATR moyen en %
    avg_adx FLOAT,  -- ADX moyen
    sample_count INTEGER,  -- Nombre de paires analysées
    
    -- Trigger
    trigger VARCHAR(20) DEFAULT 'auto',  -- 'auto', 'manual', 'startup'
    
    -- Durée dans l'ancien régime (en minutes)
    old_regime_duration_minutes FLOAT,
    
    -- Performance dans l'ancien régime (si disponible)
    old_regime_trades INTEGER,
    old_regime_wins INTEGER,
    old_regime_pnl_pct FLOAT,
    
    -- Métadonnées
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index pour analyses
CREATE INDEX IF NOT EXISTS idx_regime_history_timestamp ON market_regime_history(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_regime_history_new_regime ON market_regime_history(new_regime);
CREATE INDEX IF NOT EXISTS idx_regime_history_session ON market_regime_history(session_id);

-- ============================================================================
-- VUES pour analyses rapides
-- ============================================================================

-- Vue: Performance par régime de marché
CREATE OR REPLACE VIEW v_performance_by_regime AS
SELECT 
    entry_market_regime AS regime,
    COUNT(*) AS total_trades,
    SUM(CASE WHEN win THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN NOT win THEN 1 ELSE 0 END) AS losses,
    ROUND(100.0 * SUM(CASE WHEN win THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS winrate_pct,
    ROUND(AVG(net_pnl_pct)::numeric, 4) AS avg_pnl_pct,
    ROUND(SUM(net_pnl_usdt)::numeric, 2) AS total_pnl_usdt,
    ROUND(AVG(duration_seconds)::numeric, 0) AS avg_duration_seconds
FROM trades
WHERE entry_market_regime IS NOT NULL
GROUP BY entry_market_regime
ORDER BY winrate_pct DESC;

-- Vue: Performance par niveau de pertes consécutives
CREATE OR REPLACE VIEW v_performance_by_consecutive_losses AS
SELECT 
    entry_consecutive_losses AS losses_before_trade,
    COUNT(*) AS total_trades,
    SUM(CASE WHEN win THEN 1 ELSE 0 END) AS wins,
    ROUND(100.0 * SUM(CASE WHEN win THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS winrate_pct,
    ROUND(AVG(entry_cb_score_boost)::numeric, 2) AS avg_score_boost,
    ROUND(AVG(net_pnl_pct)::numeric, 4) AS avg_pnl_pct
FROM trades
WHERE entry_consecutive_losses IS NOT NULL
GROUP BY entry_consecutive_losses
ORDER BY entry_consecutive_losses;

-- ============================================================================
-- FIN MIGRATION
-- ============================================================================
