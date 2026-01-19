-- Migration: Post-Exit Analysis Tables
-- Date: 2026-01-19
-- Description: Tables pour le suivi des prix après clôture et l'analyse ML des sorties

-- ============================================================================
-- Table 1: trade_post_exit_analysis
-- Métriques agrégées et targets ML pour chaque trade
-- ============================================================================

CREATE TABLE IF NOT EXISTS trade_post_exit_analysis (
    id SERIAL PRIMARY KEY,
    trade_id UUID NOT NULL,
    
    -- Contexte de sortie
    exit_price DECIMAL(20, 10) NOT NULL,
    exit_timestamp TIMESTAMPTZ NOT NULL,
    exit_reason VARCHAR(50),
    direction VARCHAR(10) NOT NULL,
    realized_pnl_pct DECIMAL(10, 4),
    realized_pnl_usdt DECIMAL(20, 8),
    
    -- Params utilisés (pour analyse comparative)
    used_sl_pct DECIMAL(10, 4),
    used_tp_pct DECIMAL(10, 4),
    used_be_trigger DECIMAL(10, 4),
    used_trailing_trigger DECIMAL(10, 4),
    used_trailing_min_distance DECIMAL(10, 4),
    used_partial_tp_pct DECIMAL(10, 4),
    
    -- Config tracking
    tracking_duration_sec INTEGER NOT NULL,
    sample_count INTEGER NOT NULL,
    sample_interval_ms INTEGER DEFAULT 1000,
    
    -- Métriques post-exit MFE (Max Favorable Excursion)
    post_exit_mfe_pct DECIMAL(10, 4),
    post_exit_mfe_price DECIMAL(20, 10),
    post_exit_mfe_timestamp TIMESTAMPTZ,
    time_to_mfe_sec INTEGER,
    
    -- Métriques post-exit MAE (Max Adverse Excursion)
    post_exit_mae_pct DECIMAL(10, 4),
    post_exit_mae_price DECIMAL(20, 10),
    post_exit_mae_timestamp TIMESTAMPTZ,
    
    -- Prix final après tracking
    post_exit_final_pct DECIMAL(10, 4),
    post_exit_final_price DECIMAL(20, 10),
    
    -- Métriques dérivées
    exit_efficiency_pct DECIMAL(10, 4),      -- realized / (realized + mfe) * 100
    regret_pct DECIMAL(10, 4),               -- PnL% manqué (= post_exit_mfe_pct)
    regret_usdt DECIMAL(20, 8),              -- PnL$ manqué
    exit_timing_grade CHAR(2),               -- A+, A, B+, B, C, D, F
    
    -- Flags d'analyse
    would_have_hit_original_tp BOOLEAN DEFAULT FALSE,
    would_have_hit_original_sl BOOLEAN DEFAULT FALSE,
    price_returned_to_entry BOOLEAN DEFAULT FALSE,
    
    -- ML Targets calculés (pour entraînement)
    ml_optimal_sl_pct DECIMAL(10, 4),
    ml_optimal_trailing_trigger DECIMAL(10, 4),
    ml_optimal_be_trigger DECIMAL(10, 4),
    ml_should_use_partial BOOLEAN,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT fk_post_exit_trade FOREIGN KEY (trade_id) 
        REFERENCES trades(id) ON DELETE CASCADE,
    CONSTRAINT uq_post_exit_trade_id UNIQUE(trade_id)
);

-- Index pour analyses rapides
CREATE INDEX IF NOT EXISTS idx_post_exit_trade_id ON trade_post_exit_analysis(trade_id);
CREATE INDEX IF NOT EXISTS idx_post_exit_efficiency ON trade_post_exit_analysis(exit_efficiency_pct);
CREATE INDEX IF NOT EXISTS idx_post_exit_exit_reason ON trade_post_exit_analysis(exit_reason);
CREATE INDEX IF NOT EXISTS idx_post_exit_created ON trade_post_exit_analysis(created_at);
CREATE INDEX IF NOT EXISTS idx_post_exit_direction ON trade_post_exit_analysis(direction);

-- ============================================================================
-- Table 2: trade_post_exit_samples
-- Données brutes haute précision (1 sample/sec pendant 5 min)
-- ============================================================================

CREATE TABLE IF NOT EXISTS trade_post_exit_samples (
    id SERIAL PRIMARY KEY,
    trade_id UUID NOT NULL,
    sample_index INTEGER NOT NULL,           -- 0, 1, 2, ... N
    timestamp TIMESTAMPTZ NOT NULL,
    price DECIMAL(20, 10) NOT NULL,
    pnl_vs_exit_pct DECIMAL(10, 4),          -- PnL% depuis exit
    cumulative_mfe_pct DECIMAL(10, 4),       -- MFE cumulé jusqu'à ce point
    cumulative_mae_pct DECIMAL(10, 4),       -- MAE cumulé jusqu'à ce point
    
    CONSTRAINT fk_samples_trade FOREIGN KEY (trade_id) 
        REFERENCES trades(id) ON DELETE CASCADE,
    CONSTRAINT uq_samples_trade_index UNIQUE(trade_id, sample_index)
);

-- Index pour récupération rapide des samples
CREATE INDEX IF NOT EXISTS idx_samples_trade_id ON trade_post_exit_samples(trade_id);
CREATE INDEX IF NOT EXISTS idx_samples_timestamp ON trade_post_exit_samples(timestamp);

-- ============================================================================
-- Vue: v_post_exit_summary
-- Agrégats par exit_reason pour analyse rapide
-- ============================================================================

CREATE OR REPLACE VIEW v_post_exit_summary AS
SELECT 
    exit_reason,
    direction,
    COUNT(*) as trade_count,
    ROUND(AVG(exit_efficiency_pct)::numeric, 2) as avg_efficiency,
    ROUND(AVG(post_exit_mfe_pct)::numeric, 4) as avg_missed_profit_pct,
    ROUND(AVG(regret_usdt)::numeric, 4) as avg_regret_usdt,
    ROUND(SUM(regret_usdt)::numeric, 2) as total_regret_usdt,
    ROUND(AVG(time_to_mfe_sec)::numeric, 0) as avg_time_to_optimal_sec,
    
    -- Distribution des grades
    SUM(CASE WHEN exit_timing_grade IN ('A+', 'A') THEN 1 ELSE 0 END) as grade_a_count,
    SUM(CASE WHEN exit_timing_grade IN ('B+', 'B') THEN 1 ELSE 0 END) as grade_b_count,
    SUM(CASE WHEN exit_timing_grade = 'C' THEN 1 ELSE 0 END) as grade_c_count,
    SUM(CASE WHEN exit_timing_grade IN ('D', 'F') THEN 1 ELSE 0 END) as grade_df_count,
    
    -- Flags
    ROUND(100.0 * SUM(CASE WHEN would_have_hit_original_tp THEN 1 ELSE 0 END) / COUNT(*)::numeric, 1) as pct_would_hit_tp,
    ROUND(100.0 * SUM(CASE WHEN would_have_hit_original_sl THEN 1 ELSE 0 END) / COUNT(*)::numeric, 1) as pct_would_hit_sl
    
FROM trade_post_exit_analysis
GROUP BY exit_reason, direction
ORDER BY avg_efficiency DESC;

-- ============================================================================
-- Vue: v_post_exit_by_hour
-- Analyse par heure UTC
-- ============================================================================

CREATE OR REPLACE VIEW v_post_exit_by_hour AS
SELECT 
    EXTRACT(HOUR FROM exit_timestamp) as hour_utc,
    COUNT(*) as trade_count,
    ROUND(AVG(exit_efficiency_pct)::numeric, 2) as avg_efficiency,
    ROUND(AVG(regret_pct)::numeric, 4) as avg_regret_pct,
    ROUND(AVG(time_to_mfe_sec)::numeric, 0) as avg_time_to_optimal
FROM trade_post_exit_analysis
GROUP BY EXTRACT(HOUR FROM exit_timestamp)
ORDER BY hour_utc;

-- ============================================================================
-- Commentaires
-- ============================================================================

COMMENT ON TABLE trade_post_exit_analysis IS 'Métriques post-exit par trade pour analyse ML des sorties';
COMMENT ON TABLE trade_post_exit_samples IS 'Samples de prix haute précision (1/sec) après clôture';
COMMENT ON COLUMN trade_post_exit_analysis.exit_efficiency_pct IS 'Efficacité de sortie: realized / (realized + mfe_missed) * 100';
COMMENT ON COLUMN trade_post_exit_analysis.ml_optimal_sl_pct IS 'SL optimal calculé pour entraînement ML';
COMMENT ON COLUMN trade_post_exit_analysis.exit_timing_grade IS 'Grade A+ à F basé sur exit_efficiency_pct';
