-- ============================================================================
-- TRADE CURSOR v7.0 - ML DATA SCHEMA (COMPLETE)
-- PostgreSQL Schema pour Machine Learning & Optimization
-- ============================================================================

-- Extension pour UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- TABLE 1 : trading_sessions
-- ============================================================================
-- Sessions de trading pour analyse par période

CREATE TABLE trading_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    start_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_time TIMESTAMPTZ,
    
    -- Stats session
    total_scans INTEGER DEFAULT 0,
    opportunities_detected INTEGER DEFAULT 0,
    trades_executed INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    total_pnl_usdt FLOAT DEFAULT 0,
    total_pnl_pct FLOAT DEFAULT 0,
    
    -- Config snapshot au démarrage
    config_snapshot JSONB,
    
    -- Métadonnées
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sessions_start_time ON trading_sessions(start_time DESC);
CREATE INDEX idx_sessions_end_time ON trading_sessions(end_time DESC) WHERE end_time IS NOT NULL;

-- ============================================================================
-- TABLE 2 : config_snapshots
-- ============================================================================
-- Historique des changements de configuration

CREATE TABLE config_snapshots (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_id UUID REFERENCES trading_sessions(id) ON DELETE SET NULL,
    
    -- Config complète (JSONB)
    config_data JSONB NOT NULL,
    
    -- Changements détectés (pour tracking)
    changed_keys TEXT[],
    
    -- Métadonnées
    changed_by VARCHAR(50) DEFAULT 'system',  -- 'system', 'user', 'auto'
    notes TEXT
);

CREATE INDEX idx_config_timestamp ON config_snapshots(timestamp DESC);
CREATE INDEX idx_config_session ON config_snapshots(session_id);

-- ============================================================================
-- TABLE 3 : scan_logs (PARTITIONNÉE)
-- ============================================================================
-- Log de CHAQUE scan (opportunité ou non)
-- Base pour Feature Importance et Parameter Optimization

-- Table principale (partitionnée)
CREATE TABLE scan_logs (
    -- Métadonnées
    id BIGSERIAL NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_id UUID REFERENCES trading_sessions(id) ON DELETE SET NULL,
    symbol VARCHAR(30) NOT NULL,
    scan_duration_ms FLOAT,
    
    -- Données marché
    price FLOAT NOT NULL,
    spread_pct FLOAT,
    book_depth FLOAT,
    balance_score FLOAT,
    bid_vol FLOAT,
    ask_vol FLOAT,
    orderbook_imbalance_ratio FLOAT,  -- bid_vol / ask_vol
    
    -- ========================================
    -- Indicateurs 1m
    -- ========================================
    
    -- EMA
    ema9_1m FLOAT,
    ema21_1m FLOAT,
    ema_diff_pct_1m FLOAT,  -- (EMA9 - EMA21) / EMA21 * 100
    
    -- RSI
    rsi_1m FLOAT,
    rsi_prev_1m FLOAT,
    
    -- MACD
    macd_1m FLOAT,
    macd_signal_1m FLOAT,
    macd_hist_1m FLOAT,
    macd_hist_prev_1m FLOAT,
    
    -- ADX
    adx_1m FLOAT,
    di_plus_1m FLOAT,
    di_minus_1m FLOAT,
    di_gap_1m FLOAT,  -- DI+ - DI-
    
    -- ATR
    atr_1m FLOAT,
    atr_pct_1m FLOAT,
    
    -- Bollinger Bands
    bb_upper_1m FLOAT,
    bb_middle_1m FLOAT,
    bb_lower_1m FLOAT,
    bb_width_1m FLOAT,
    bb_distance_to_lower_1m FLOAT,  -- Distance en %
    bb_distance_to_upper_1m FLOAT,
    
    -- Volume
    volume_1m FLOAT,
    volume_avg_1m FLOAT,
    volume_ratio_1m FLOAT,  -- volume / volume_avg
    volume_spike_1m FLOAT,
    
    -- ========================================
    -- Indicateurs 5m
    -- ========================================
    
    -- EMA
    ema9_5m FLOAT,
    ema21_5m FLOAT,
    ema_diff_pct_5m FLOAT,
    
    -- RSI
    rsi_5m FLOAT,
    rsi_prev_5m FLOAT,
    
    -- MACD
    macd_5m FLOAT,
    macd_signal_5m FLOAT,
    macd_hist_5m FLOAT,
    macd_hist_prev_5m FLOAT,
    
    -- ADX
    adx_5m FLOAT,
    di_plus_5m FLOAT,
    di_minus_5m FLOAT,
    di_gap_5m FLOAT,
    
    -- ATR
    atr_5m FLOAT,
    atr_pct_5m FLOAT,
    
    -- Bollinger Bands
    bb_upper_5m FLOAT,
    bb_middle_5m FLOAT,
    bb_lower_5m FLOAT,
    bb_width_5m FLOAT,
    bb_distance_to_lower_5m FLOAT,
    bb_distance_to_upper_5m FLOAT,
    
    -- Volume
    volume_5m FLOAT,
    volume_avg_5m FLOAT,
    volume_ratio_5m FLOAT,
    volume_spike_5m FLOAT,
    
    -- ========================================
    -- Filtres de Qualité
    -- ========================================
    
    -- SNR (Signal-to-Noise Ratio)
    snr_1m FLOAT,  -- abs(price - EMA21) / ATR
    snr_5m FLOAT,
    snr_passed_1m BOOLEAN,
    snr_passed_5m BOOLEAN,
    
    -- Breakout
    breakout_distance_1m FLOAT,  -- Distance à EMA21 en ATR
    breakout_distance_5m FLOAT,
    breakout_passed_1m BOOLEAN,
    breakout_passed_5m BOOLEAN,
    
    -- Wick Ratio
    wick_ratio_1m FLOAT,  -- (high - low) / body
    wick_ratio_5m FLOAT,
    wick_passed_1m BOOLEAN,
    wick_passed_5m BOOLEAN,
    
    -- ATR Optimal
    atr_optimal_passed_1m BOOLEAN,
    atr_optimal_passed_5m BOOLEAN,
    
    -- Volume Filter
    volume_filter_passed_1m BOOLEAN,
    volume_filter_passed_5m BOOLEAN,
    
    -- ========================================
    -- Confluence
    -- ========================================
    
    use_confluence BOOLEAN,
    confluence_met BOOLEAN,
    score_1m FLOAT,
    score_5m FLOAT,
    score_total FLOAT,
    score_long_1m FLOAT,
    score_short_1m FLOAT,
    score_long_5m FLOAT,
    score_short_5m FLOAT,
    timeframes_aligned BOOLEAN,
    
    -- ========================================
    -- Patterns
    -- ========================================
    
    pattern_1m VARCHAR(50),
    pattern_multi_1m VARCHAR(50),
    pattern_5m VARCHAR(50),
    pattern_multi_5m VARCHAR(50),
    
    -- ========================================
    -- Trend data (15m ou configurable)
    -- ========================================
    
    trend_timeframe VARCHAR(10) DEFAULT '15m',
    trend_direction VARCHAR(10),  -- BULLISH, BEARISH, NEUTRAL
    trend_strength FLOAT,
    trend_bonus FLOAT,
    
    -- ========================================
    -- Divergence
    -- ========================================
    
    divergence_detected BOOLEAN DEFAULT FALSE,
    divergence_type VARCHAR(20),  -- 'BULLISH', 'BEARISH', null
    divergence_bonus FLOAT DEFAULT 0,
    
    -- ========================================
    -- Décision (LABELS ML)
    -- ========================================
    
    is_opportunity BOOLEAN NOT NULL DEFAULT FALSE,
    opportunity_direction VARCHAR(10),  -- LONG, SHORT, null
    reject_reason TEXT,
    reject_reason_category VARCHAR(50),  -- 'FILTER', 'SCORE', 'MARKET', 'OTHER'
    
    -- ========================================
    -- Paramètres snapshot (JSONB)
    -- ========================================
    
    params_snapshot JSONB,
    
    -- Partition key
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Partitions par mois (exemple pour 2025)
CREATE TABLE scan_logs_2025_01 PARTITION OF scan_logs
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
CREATE TABLE scan_logs_2025_02 PARTITION OF scan_logs
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
CREATE TABLE scan_logs_2025_03 PARTITION OF scan_logs
    FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');
-- ... Continuer pour chaque mois

-- Index pour performance (créés sur chaque partition automatiquement)
CREATE INDEX idx_scan_timestamp ON scan_logs(timestamp DESC);
CREATE INDEX idx_scan_symbol ON scan_logs(symbol);
CREATE INDEX idx_scan_opportunity ON scan_logs(is_opportunity);
CREATE INDEX idx_scan_timestamp_symbol ON scan_logs(timestamp DESC, symbol);
CREATE INDEX idx_scan_direction ON scan_logs(opportunity_direction) WHERE opportunity_direction IS NOT NULL;
CREATE INDEX idx_scan_session ON scan_logs(session_id);
CREATE INDEX idx_scan_win_features ON scan_logs(is_opportunity, opportunity_direction, score_total) 
    WHERE is_opportunity = TRUE;
-- Index sur heure (nécessite fonction IMMUTABLE)
CREATE OR REPLACE FUNCTION extract_hour_immutable(timestamptz)
RETURNS INTEGER AS $$
    SELECT EXTRACT(HOUR FROM $1)::INTEGER;
$$ LANGUAGE SQL IMMUTABLE;

CREATE INDEX idx_scan_hour ON scan_logs(extract_hour_immutable(timestamp));

CREATE INDEX idx_scan_reject_category ON scan_logs(reject_reason_category) WHERE reject_reason_category IS NOT NULL;

-- ============================================================================
-- TABLE 4 : opportunities
-- ============================================================================
-- Log des opportunités détectées (subset de scan_logs)

CREATE TABLE opportunities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scan_log_id BIGINT NOT NULL,  -- Référence à scan_logs (sans FK pour performance)
    session_id UUID REFERENCES trading_sessions(id) ON DELETE SET NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol VARCHAR(30) NOT NULL,
    direction VARCHAR(10) NOT NULL,  -- LONG, SHORT
    
    -- Setup info
    entry_suggested FLOAT NOT NULL,
    tp_suggested FLOAT NOT NULL,
    sl_suggested FLOAT NOT NULL,
    tp_sl_mode VARCHAR(20),  -- FIXE, ATR, ESCALIER
    setup_score FLOAT,
    setup_reason TEXT,
    
    -- Conditions matched
    conditions_matched TEXT[],  -- Array : ['EMAs', 'RSI', 'MACD', ...]
    condition_count INTEGER,
    
    -- Scores détaillés
    score_long FLOAT,
    score_short FLOAT,
    score_min_required FLOAT,
    trend_bonus FLOAT,
    divergence_bonus FLOAT,
    
    -- Status
    status VARCHAR(20) DEFAULT 'PENDING',  -- PENDING, EXECUTED, IGNORED, EXPIRED, REJECTED
    ignored_reason TEXT,
    executed_at TIMESTAMPTZ,
    expired_at TIMESTAMPTZ,
    
    -- Métadonnées
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index
CREATE INDEX idx_opp_timestamp ON opportunities(timestamp DESC);
CREATE INDEX idx_opp_scan_log ON opportunities(scan_log_id);
CREATE INDEX idx_opp_status ON opportunities(status);
CREATE INDEX idx_opp_symbol ON opportunities(symbol);
CREATE INDEX idx_opp_session ON opportunities(session_id);
CREATE INDEX idx_opp_direction ON opportunities(direction);
CREATE INDEX idx_opp_score ON opportunities(setup_score DESC) WHERE setup_score IS NOT NULL;

-- ============================================================================
-- TABLE 5 : trades
-- ============================================================================
-- Log des trades exécutés avec résultats
-- Base pour Predictive Model

CREATE TABLE trades (
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
    
    entry_spread_pct FLOAT,
    entry_book_depth FLOAT,
    entry_balance_score FLOAT,
    entry_bid_vol FLOAT,
    entry_ask_vol FLOAT,
    entry_orderbook_imbalance FLOAT,
    
    -- Métadonnées
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index
CREATE INDEX idx_trade_timestamp_entry ON trades(timestamp_entry DESC);
CREATE INDEX idx_trade_timestamp_exit ON trades(timestamp_exit DESC) WHERE timestamp_exit IS NOT NULL;
CREATE INDEX idx_trade_symbol ON trades(symbol);
CREATE INDEX idx_trade_win ON trades(win);
CREATE INDEX idx_trade_opportunity ON trades(opportunity_id);
CREATE INDEX idx_trade_direction ON trades(direction);
CREATE INDEX idx_trade_exit_reason ON trades(exit_reason);
CREATE INDEX idx_trade_session ON trades(session_id);
CREATE INDEX idx_trade_pnl_usdt ON trades(net_pnl_usdt DESC);
CREATE INDEX idx_trade_duration ON trades(duration_seconds) WHERE duration_seconds IS NOT NULL;
-- Index sur date (nécessite fonction IMMUTABLE)
CREATE OR REPLACE FUNCTION extract_date_immutable(timestamptz)
RETURNS DATE AS $$
    SELECT DATE($1);
$$ LANGUAGE SQL IMMUTABLE;

CREATE INDEX idx_trade_date_entry ON trades(extract_date_immutable(timestamp_entry));

-- ============================================================================
-- TABLE 6 : market_context (optionnel)
-- ============================================================================
-- Contexte marché général (snapshot périodique)

CREATE TABLE market_context (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_id UUID REFERENCES trading_sessions(id) ON DELETE SET NULL,
    hour_of_day INTEGER,  -- 0-23
    day_of_week INTEGER,  -- 0-6 (0=Monday)
    
    -- Métriques globales
    btc_price FLOAT,
    eth_price FLOAT,
    total_opportunities_detected INTEGER,
    avg_spread FLOAT,
    avg_volatility_1m FLOAT,
    avg_volatility_5m FLOAT,
    
    -- Stats session
    active_positions_count INTEGER DEFAULT 0,
    session_win_rate FLOAT,
    session_pnl_usdt FLOAT,
    session_pnl_pct FLOAT,
    
    -- Métriques de marché
    market_trend VARCHAR(10),  -- BULLISH, BEARISH, NEUTRAL
    market_volatility VARCHAR(10),  -- LOW, MEDIUM, HIGH
    fear_greed_index FLOAT  -- Si disponible via API externe
);

-- Index
CREATE INDEX idx_context_timestamp ON market_context(timestamp DESC);
CREATE INDEX idx_context_session ON market_context(session_id);
CREATE INDEX idx_context_hour ON market_context(hour_of_day);
CREATE INDEX idx_context_day ON market_context(day_of_week);

-- ============================================================================
-- TABLE 7 : scan_errors
-- ============================================================================
-- Logs d'erreurs de scan pour détecter patterns de problèmes

CREATE TABLE scan_errors (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_id UUID REFERENCES trading_sessions(id) ON DELETE SET NULL,
    symbol VARCHAR(30),
    error_type VARCHAR(50),  -- 'API_ERROR', 'TIMEOUT', 'DATA_INVALID', etc.
    error_message TEXT,
    error_stack TEXT,
    scan_context JSONB,  -- Contexte au moment de l'erreur
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ
);

CREATE INDEX idx_errors_timestamp ON scan_errors(timestamp DESC);
CREATE INDEX idx_errors_type ON scan_errors(error_type);
CREATE INDEX idx_errors_resolved ON scan_errors(resolved) WHERE resolved = FALSE;

-- ============================================================================
-- TABLE 8 : model_predictions (pour ML futur)
-- ============================================================================
-- Prédictions du modèle ML avec confiance

CREATE TABLE model_predictions (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scan_log_id BIGINT,
    opportunity_id UUID REFERENCES opportunities(id) ON DELETE SET NULL,
    model_version VARCHAR(50),
    
    -- Prédictions
    predicted_win BOOLEAN,
    win_probability FLOAT,  -- 0.0 - 1.0
    predicted_pnl_pct FLOAT,
    confidence_score FLOAT,  -- 0.0 - 1.0
    
    -- Features utilisées (snapshot)
    features_used JSONB,
    
    -- Résultat réel (rempli après trade)
    actual_win BOOLEAN,
    actual_pnl_pct FLOAT,
    prediction_correct BOOLEAN,
    
    -- Métadonnées
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_predictions_timestamp ON model_predictions(timestamp DESC);
CREATE INDEX idx_predictions_opportunity ON model_predictions(opportunity_id);
CREATE INDEX idx_predictions_correct ON model_predictions(prediction_correct);
CREATE INDEX idx_predictions_model ON model_predictions(model_version);

-- ============================================================================
-- TABLE 9 : features_engineered (optionnel, pour ML avancé)
-- ============================================================================
-- Features pré-calculées pour ML

CREATE TABLE features_engineered (
    id BIGSERIAL PRIMARY KEY,
    scan_log_id BIGINT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Features dérivées
    rsi_macd_divergence BOOLEAN,
    ema_cross_signal VARCHAR(10),  -- 'BULLISH', 'BEARISH', 'NONE'
    volume_atr_ratio FLOAT,
    bb_squeeze BOOLEAN,  -- Bollinger Bands squeeze
    adx_trend_alignment BOOLEAN,
    multi_timeframe_alignment BOOLEAN,
    
    -- Features composites
    momentum_score FLOAT,
    trend_score FLOAT,
    volatility_score FLOAT,
    liquidity_score FLOAT,
    
    -- Métadonnées
    feature_version VARCHAR(20) DEFAULT 'v1.0'
);

CREATE INDEX idx_features_scan_log ON features_engineered(scan_log_id);
CREATE INDEX idx_features_timestamp ON features_engineered(timestamp DESC);

-- ============================================================================
-- VUES UTILES
-- ============================================================================

-- Vue : Scans avec opportunités
CREATE VIEW scans_with_opportunities AS
SELECT 
    s.*,
    o.id as opportunity_id,
    o.status as opportunity_status,
    o.setup_score,
    o.conditions_matched
FROM scan_logs s
LEFT JOIN opportunities o ON s.id = o.scan_log_id
WHERE s.is_opportunity = TRUE;

-- Vue : Opportunités exécutées
CREATE VIEW opportunities_executed AS
SELECT 
    o.*,
    t.id as trade_id,
    t.net_pnl_usdt,
    t.win,
    t.exit_reason,
    t.duration_seconds
FROM opportunities o
INNER JOIN trades t ON o.id = t.opportunity_id
WHERE o.status = 'EXECUTED';

-- Vue : Stats quotidiennes
CREATE VIEW daily_stats AS
SELECT 
    extract_date_immutable(timestamp_entry) as date,
    COUNT(*) as total_trades,
    COUNT(*) FILTER (WHERE win = TRUE) as wins,
    COUNT(*) FILTER (WHERE win = FALSE) as losses,
    ROUND((COUNT(*) FILTER (WHERE win = TRUE)::FLOAT / NULLIF(COUNT(*), 0) * 100)::numeric, 2) as win_rate_pct,
    ROUND(AVG(net_pnl_pct)::numeric, 4) as avg_pnl_pct,
    ROUND(SUM(net_pnl_usdt)::numeric, 4) as total_pnl_usdt,
    ROUND(AVG(duration_seconds)::numeric, 1) as avg_duration_sec,
    ROUND(AVG(risk_reward_ratio)::numeric, 2) as avg_risk_reward
FROM trades
WHERE timestamp_exit IS NOT NULL
GROUP BY extract_date_immutable(timestamp_entry)
ORDER BY date DESC;

-- Vue : Stats par session
CREATE VIEW session_stats AS
SELECT 
    ts.id as session_id,
    ts.start_time,
    ts.end_time,
    ts.total_scans,
    ts.opportunities_detected,
    ts.trades_executed,
    ts.wins,
    ts.losses,
    ts.total_pnl_usdt,
    ts.total_pnl_pct,
    ROUND((ts.wins::FLOAT / NULLIF(ts.trades_executed, 0) * 100)::numeric, 2) as win_rate_pct,
    COUNT(t.id) FILTER (WHERE t.win = TRUE) as actual_wins,
    COUNT(t.id) FILTER (WHERE t.win = FALSE) as actual_losses,
    ROUND(SUM(t.net_pnl_usdt)::numeric, 4) as actual_pnl_usdt
FROM trading_sessions ts
LEFT JOIN trades t ON ts.id = t.session_id
GROUP BY ts.id, ts.start_time, ts.end_time, ts.total_scans, 
         ts.opportunities_detected, ts.trades_executed, ts.wins, ts.losses, 
         ts.total_pnl_usdt, ts.total_pnl_pct
ORDER BY ts.start_time DESC;

-- Vue : Features pour ML
CREATE VIEW ml_features AS
SELECT 
    s.id as scan_id,
    s.timestamp,
    s.symbol,
    s.is_opportunity,
    s.opportunity_direction,
    s.score_total,
    s.rsi_1m,
    s.rsi_5m,
    s.macd_hist_1m,
    s.macd_hist_5m,
    s.adx_1m,
    s.adx_5m,
    s.atr_pct_1m,
    s.atr_pct_5m,
    s.volume_ratio_1m,
    s.volume_ratio_5m,
    s.spread_pct,
    s.balance_score,
    s.snr_1m,
    s.snr_5m,
    s.breakout_distance_1m,
    s.wick_ratio_1m,
    s.trend_direction,
    s.trend_strength,
    s.divergence_detected,
    s.confluence_met,
    t.win,
    t.net_pnl_pct,
    t.duration_seconds
FROM scan_logs s
LEFT JOIN opportunities o ON s.id = o.scan_log_id
LEFT JOIN trades t ON o.id = t.opportunity_id
WHERE s.is_opportunity = TRUE AND t.timestamp_exit IS NOT NULL;

-- ============================================================================
-- FONCTIONS UTILES
-- ============================================================================

-- Fonction : Nettoyer vieilles données (>6 mois)
CREATE OR REPLACE FUNCTION cleanup_old_data()
RETURNS void AS $$
BEGIN
    -- Nettoyer scan_logs (garder opportunités)
    DELETE FROM scan_logs 
    WHERE timestamp < NOW() - INTERVAL '6 months'
    AND is_opportunity = FALSE;
    
    -- Nettoyer market_context
    DELETE FROM market_context 
    WHERE timestamp < NOW() - INTERVAL '6 months';
    
    -- Nettoyer scan_errors résolus
    DELETE FROM scan_errors 
    WHERE resolved = TRUE 
    AND resolved_at < NOW() - INTERVAL '3 months';
    
    -- Nettoyer model_predictions anciennes
    DELETE FROM model_predictions 
    WHERE timestamp < NOW() - INTERVAL '12 months';
END;
$$ LANGUAGE plpgsql;

-- Fonction : Stats globales
CREATE OR REPLACE FUNCTION get_global_stats()
RETURNS TABLE (
    total_scans BIGINT,
    total_opportunities BIGINT,
    total_trades BIGINT,
    win_rate FLOAT,
    total_pnl_usdt FLOAT,
    avg_pnl_pct FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        (SELECT COUNT(*) FROM scan_logs),
        (SELECT COUNT(*) FROM opportunities),
        (SELECT COUNT(*) FROM trades WHERE timestamp_exit IS NOT NULL),
        (SELECT ROUND((COUNT(*) FILTER (WHERE win = TRUE)::FLOAT / 
                      NULLIF(COUNT(*), 0) * 100)::numeric, 2) 
         FROM trades WHERE win IS NOT NULL),
        (SELECT ROUND(SUM(net_pnl_usdt)::numeric, 4) FROM trades),
        (SELECT ROUND(AVG(net_pnl_pct)::numeric, 4) FROM trades WHERE net_pnl_pct IS NOT NULL);
END;
$$ LANGUAGE plpgsql;

-- Fonction : Créer partition mensuelle automatiquement
CREATE OR REPLACE FUNCTION create_monthly_partition(table_name TEXT, start_date DATE)
RETURNS void AS $$
DECLARE
    partition_name TEXT;
    end_date DATE;
BEGIN
    end_date := start_date + INTERVAL '1 month';
    partition_name := table_name || '_' || TO_CHAR(start_date, 'YYYY_MM');
    
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
                   partition_name, table_name, start_date, end_date);
END;
$$ LANGUAGE plpgsql;

-- Fonction : Mettre à jour timestamp updated_at automatiquement
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger pour trades.updated_at
CREATE TRIGGER update_trades_updated_at
    BEFORE UPDATE ON trades
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- GRANTS (si utilisateur spécifique créé)
-- ============================================================================

-- Pour l'instant on utilise postgres (superuser)
-- Si vous créez un user "trade_cursor_app" plus tard :
-- CREATE USER trade_cursor_app WITH PASSWORD 'your_password';
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO trade_cursor_app;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO trade_cursor_app;
-- GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO trade_cursor_app;

-- ============================================================================
-- COMMENTAIRES SUR LES TABLES
-- ============================================================================

COMMENT ON TABLE scan_logs IS 'Logs complets de chaque scan avec tous les indicateurs techniques et filtres';
COMMENT ON TABLE opportunities IS 'Opportunités détectées (subset de scan_logs)';
COMMENT ON TABLE trades IS 'Trades exécutés avec résultats complets pour ML';
COMMENT ON TABLE trading_sessions IS 'Sessions de trading pour analyse par période';
COMMENT ON TABLE config_snapshots IS 'Historique des changements de configuration';
COMMENT ON TABLE market_context IS 'Contexte marché général (snapshot périodique)';
COMMENT ON TABLE scan_errors IS 'Logs d''erreurs de scan pour détecter patterns';
COMMENT ON TABLE model_predictions IS 'Prédictions ML avec résultats réels pour amélioration';
COMMENT ON TABLE features_engineered IS 'Features pré-calculées pour ML avancé';

-- ============================================================================
-- FIN SCHEMA
-- ============================================================================

