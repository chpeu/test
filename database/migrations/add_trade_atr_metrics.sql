-- Migration: Table trade_atr_metrics pour optimisation TP/SL ATR
-- Date: 2025-12-09
-- Description: Capture toutes les métriques ATR pour analyse What-If et optimisation

-- ============================================
-- 1. Table trade_atr_metrics
-- ============================================
CREATE TABLE IF NOT EXISTS trade_atr_metrics (
    id SERIAL PRIMARY KEY,
    trade_id UUID REFERENCES trades(id) ON DELETE CASCADE,
    
    -- ========================================
    -- Contexte ATR à l'entrée
    -- ========================================
    entry_atr_1m FLOAT,
    entry_atr_5m FLOAT,
    entry_atr_pct_1m FLOAT,
    entry_atr_pct_5m FLOAT,
    
    -- ========================================
    -- Paramètres utilisés pour CE trade (7 params finaux)
    -- ========================================
    param_atr_mult_sl FLOAT,
    param_atr_mult_tp FLOAT,
    param_trailing_trigger_mult FLOAT,
    param_trailing_distance_mult FLOAT,
    param_be_atr_mult FLOAT,              -- NULL si BE désactivé
    param_stagnation_timeout INT,         -- NULL si stagnation désactivée
    param_stagnation_min_pnl FLOAT,
    
    -- ========================================
    -- Context Tagging (Anti-Overfitting)
    -- ========================================
    market_volatility_state VARCHAR(10),  -- 'LOW', 'MEDIUM', 'HIGH'
    market_trend_state VARCHAR(20),       -- 'RANGING', 'TRENDING_WEAK', 'TRENDING_STRONG'
    entry_adx FLOAT,
    entry_atr_percentile FLOAT,           -- Percentile ATR vs historique (0-100)
    
    -- ========================================
    -- Niveaux calculés (en prix et %)
    -- ========================================
    calculated_sl_price FLOAT,
    calculated_tp_price FLOAT,
    calculated_sl_pct FLOAT,              -- Distance SL en %
    calculated_tp_pct FLOAT,              -- Distance TP en %
    calculated_be_trigger_pnl_pct FLOAT,  -- PnL% pour déclencher BE
    calculated_trailing_trigger_pnl_pct FLOAT,
    
    -- ========================================
    -- Événements Break-Even
    -- ========================================
    be_triggered BOOLEAN DEFAULT FALSE,
    be_triggered_at TIMESTAMPTZ,
    be_triggered_pnl_pct FLOAT,           -- PnL% au moment du trigger
    be_price_at_trigger FLOAT,            -- Prix quand BE déclenché
    
    -- ========================================
    -- Événements Trailing Stop
    -- ========================================
    trailing_activated BOOLEAN DEFAULT FALSE,
    trailing_activated_at TIMESTAMPTZ,
    trailing_activated_pnl_pct FLOAT,
    trailing_final_distance_pct FLOAT,    -- Distance finale du trailing
    trailing_final_sl_price FLOAT,        -- SL final du trailing
    
    -- ========================================
    -- Événements Stagnation
    -- ========================================
    stagnation_detected BOOLEAN DEFAULT FALSE,
    stagnation_detected_at TIMESTAMPTZ,
    stagnation_duration_seconds INT,
    stagnation_pnl_at_exit FLOAT,
    
    -- ========================================
    -- Maximum atteint pendant le trade
    -- ========================================
    max_pnl_reached FLOAT,
    min_pnl_reached FLOAT,
    max_price_reached FLOAT,
    min_price_reached FLOAT,
    time_to_max_pnl_seconds INT,
    time_to_min_pnl_seconds INT,
    
    -- ========================================
    -- Résultats "What-If" (calculés post-trade)
    -- ========================================
    pnl_if_no_be FLOAT,                   -- PnL si BE n'avait pas été activé
    pnl_if_no_trailing FLOAT,             -- PnL si trailing n'avait pas été activé
    pnl_if_fixed_tp FLOAT,                -- PnL avec TP fixe (sans trailing)
    pnl_if_wider_sl FLOAT,                -- PnL avec SL × 1.5
    pnl_if_tighter_sl FLOAT,              -- PnL avec SL × 0.75
    pnl_if_wider_trailing FLOAT,          -- PnL avec trailing × 1.5
    pnl_if_tighter_trailing FLOAT,        -- PnL avec trailing × 0.75
    
    -- ========================================
    -- Efficacité des paramètres
    -- ========================================
    sl_efficiency FLOAT,                  -- % du SL utilisé (0-100%)
    tp_efficiency FLOAT,                  -- % du TP atteint avant sortie
    be_efficiency FLOAT,                  -- Si BE: trade aurait-il été perdant sans?
    trailing_capture_pct FLOAT,           -- % du mouvement capturé par trailing
    
    -- ========================================
    -- Métadonnées
    -- ========================================
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- 2. Index pour analyses rapides
-- ============================================
CREATE INDEX IF NOT EXISTS idx_atr_metrics_trade ON trade_atr_metrics(trade_id);
CREATE INDEX IF NOT EXISTS idx_atr_metrics_be ON trade_atr_metrics(be_triggered) WHERE be_triggered = TRUE;
CREATE INDEX IF NOT EXISTS idx_atr_metrics_trailing ON trade_atr_metrics(trailing_activated) WHERE trailing_activated = TRUE;
CREATE INDEX IF NOT EXISTS idx_atr_metrics_stagnation ON trade_atr_metrics(stagnation_detected) WHERE stagnation_detected = TRUE;
CREATE INDEX IF NOT EXISTS idx_atr_metrics_volatility ON trade_atr_metrics(market_volatility_state);
CREATE INDEX IF NOT EXISTS idx_atr_metrics_trend ON trade_atr_metrics(market_trend_state);
CREATE INDEX IF NOT EXISTS idx_atr_metrics_created ON trade_atr_metrics(created_at DESC);

-- ============================================
-- 3. Commentaires
-- ============================================
COMMENT ON TABLE trade_atr_metrics IS 'Métriques ATR détaillées pour chaque trade - optimisation TP/SL';
COMMENT ON COLUMN trade_atr_metrics.param_trailing_distance_mult IS 'Distance du trailing stop (ATR × X)';
COMMENT ON COLUMN trade_atr_metrics.market_volatility_state IS 'Régime de volatilité: LOW (<0.2%), MEDIUM (0.2-0.5%), HIGH (>0.5%)';
COMMENT ON COLUMN trade_atr_metrics.pnl_if_no_be IS 'PnL simulé si Break-Even désactivé';
COMMENT ON COLUMN trade_atr_metrics.trailing_capture_pct IS 'Pourcentage du mouvement max capturé par le trailing';

-- ============================================
-- 4. Vue pour analyse rapide
-- ============================================
CREATE OR REPLACE VIEW v_atr_optimization_summary AS
SELECT 
    market_volatility_state,
    market_trend_state,
    COUNT(*) as total_trades,
    
    -- Moyennes des paramètres utilisés
    AVG(param_atr_mult_sl) as avg_sl_mult,
    AVG(param_atr_mult_tp) as avg_tp_mult,
    AVG(param_trailing_trigger_mult) as avg_trailing_trigger,
    AVG(param_trailing_distance_mult) as avg_trailing_distance,
    AVG(param_be_atr_mult) as avg_be_mult,
    
    -- Taux d'événements
    ROUND(100.0 * COUNT(CASE WHEN be_triggered THEN 1 END) / NULLIF(COUNT(*), 0), 1) as be_trigger_rate,
    ROUND(100.0 * COUNT(CASE WHEN trailing_activated THEN 1 END) / NULLIF(COUNT(*), 0), 1) as trailing_activation_rate,
    ROUND(100.0 * COUNT(CASE WHEN stagnation_detected THEN 1 END) / NULLIF(COUNT(*), 0), 1) as stagnation_rate,
    
    -- Efficacité moyenne
    AVG(trailing_capture_pct) as avg_trailing_capture,
    AVG(be_efficiency) as avg_be_efficiency,
    
    -- Impact What-If moyen
    AVG(pnl_if_no_be) as avg_pnl_if_no_be,
    AVG(pnl_if_no_trailing) as avg_pnl_if_no_trailing
    
FROM trade_atr_metrics
GROUP BY market_volatility_state, market_trend_state
ORDER BY total_trades DESC;

-- ============================================
-- 5. Vérification
-- ============================================
SELECT 
    'trade_atr_metrics' as table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'trade_atr_metrics') as column_count,
    'OK - Table créée' as status;
