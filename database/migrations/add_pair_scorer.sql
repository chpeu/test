-- ============================================================================
-- MIGRATION: Add Pair Scorer - Score Pair Dynamique
-- Sprint 2 - Phase 2.2 - 07/12/2025
-- ============================================================================
-- Ajuste le score minimum par paire selon performance historique
-- ============================================================================

-- ============================================================================
-- TABLE pair_performance_stats : Cache des stats par paire
-- ============================================================================

CREATE TABLE IF NOT EXISTS pair_performance_stats (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(50) UNIQUE NOT NULL,
    
    -- Statistiques de base
    total_trades INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    winrate FLOAT DEFAULT 0,
    
    -- PnL
    avg_pnl_pct FLOAT DEFAULT 0,
    total_pnl_pct FLOAT DEFAULT 0,
    avg_pnl_usdt FLOAT DEFAULT 0,
    total_pnl_usdt FLOAT DEFAULT 0,
    
    -- Score adjustment calculé
    score_adjustment FLOAT DEFAULT 0,  -- [-2.0, +2.0]
    
    -- Détails du calcul
    wr_component FLOAT DEFAULT 0,      -- Composante winrate
    pnl_component FLOAT DEFAULT 0,     -- Composante PnL
    
    -- Période analysée
    lookback_days INTEGER DEFAULT 30,
    first_trade_date TIMESTAMPTZ,
    last_trade_date TIMESTAMPTZ,
    
    -- Métadonnées
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index pour recherche rapide
CREATE INDEX IF NOT EXISTS idx_pair_stats_symbol ON pair_performance_stats(symbol);
CREATE INDEX IF NOT EXISTS idx_pair_stats_adjustment ON pair_performance_stats(score_adjustment);
CREATE INDEX IF NOT EXISTS idx_pair_stats_winrate ON pair_performance_stats(winrate);

-- ============================================================================
-- COLONNES trades : Contexte pair scorer au moment du trade
-- ============================================================================

-- Ajustement de score appliqué pour cette paire
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_pair_score_adjustment FLOAT DEFAULT 0;
COMMENT ON COLUMN trades.entry_pair_score_adjustment IS 'Ajustement score par paire [-2, +2] appliqué au entry';

-- Score minimum effectif après tous les ajustements
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_effective_min_score FLOAT;
COMMENT ON COLUMN trades.entry_effective_min_score IS 'Score minimum effectif (base - pair_adj - regime_adj + cb_boost)';

-- ============================================================================
-- COLONNES scan_logs : Contexte pair scorer au moment du scan
-- ============================================================================

-- Ajustement de score pour cette paire
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS pair_score_adjustment FLOAT DEFAULT 0;
COMMENT ON COLUMN scan_logs.pair_score_adjustment IS 'Ajustement score par paire [-2, +2]';

-- Score minimum effectif
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS config_effective_min_score FLOAT;
COMMENT ON COLUMN scan_logs.config_effective_min_score IS 'Score minimum effectif après tous ajustements';

-- ============================================================================
-- INDEX pour analyses ML
-- ============================================================================

-- Performance par niveau d'ajustement
CREATE INDEX IF NOT EXISTS idx_trade_pair_adjustment ON trades(entry_pair_score_adjustment) 
    WHERE entry_pair_score_adjustment IS NOT NULL AND entry_pair_score_adjustment != 0;

-- ============================================================================
-- VUE: Performance par paire avec ajustement
-- ============================================================================

CREATE OR REPLACE VIEW v_pair_performance_detailed AS
SELECT 
    symbol,
    COUNT(*) AS total_trades,
    SUM(CASE WHEN win THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN NOT win THEN 1 ELSE 0 END) AS losses,
    ROUND(100.0 * SUM(CASE WHEN win THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS winrate_pct,
    ROUND(AVG(pnl_pct)::numeric, 4) AS avg_pnl_pct,
    ROUND(SUM(pnl_pct)::numeric, 4) AS total_pnl_pct,
    ROUND(AVG(pnl_usdt)::numeric, 4) AS avg_pnl_usdt,
    ROUND(SUM(pnl_usdt)::numeric, 2) AS total_pnl_usdt,
    MIN(timestamp_entry) AS first_trade,
    MAX(timestamp_entry) AS last_trade
FROM trades
WHERE timestamp_entry > NOW() - INTERVAL '30 days'
GROUP BY symbol
HAVING COUNT(*) >= 5
ORDER BY winrate_pct DESC, total_pnl_pct DESC;

-- ============================================================================
-- VUE: Efficacité du pair scorer
-- ============================================================================

CREATE OR REPLACE VIEW v_pair_scorer_effectiveness AS
SELECT 
    CASE 
        WHEN entry_pair_score_adjustment > 0.5 THEN 'Bonus (>+0.5)'
        WHEN entry_pair_score_adjustment < -0.5 THEN 'Malus (<-0.5)'
        ELSE 'Neutre (-0.5 à +0.5)'
    END AS adjustment_category,
    COUNT(*) AS total_trades,
    SUM(CASE WHEN win THEN 1 ELSE 0 END) AS wins,
    ROUND(100.0 * SUM(CASE WHEN win THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS winrate_pct,
    ROUND(AVG(pnl_pct)::numeric, 4) AS avg_pnl_pct,
    ROUND(SUM(pnl_pct)::numeric, 4) AS total_pnl_pct
FROM trades
WHERE entry_pair_score_adjustment IS NOT NULL
GROUP BY 
    CASE 
        WHEN entry_pair_score_adjustment > 0.5 THEN 'Bonus (>+0.5)'
        WHEN entry_pair_score_adjustment < -0.5 THEN 'Malus (<-0.5)'
        ELSE 'Neutre (-0.5 à +0.5)'
    END
ORDER BY winrate_pct DESC;

-- ============================================================================
-- FIN MIGRATION
-- ============================================================================
