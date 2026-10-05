-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRATION: Market Regime V2 + Saisonnalité + ML Integration
-- Date: 10/12/2025
-- Compatibilité: PostgreSQL 12+
-- SAFE: Toutes les commandes sont IF NOT EXISTS
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ TABLE: trade_atr_metrics                                                │
-- │ +15 colonnes pour contexte complet                                      │
-- └─────────────────────────────────────────────────────────────────────────┘

-- Saisonnalité
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    session_market VARCHAR(20) DEFAULT NULL;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    hour_utc INT DEFAULT NULL;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    day_of_week INT DEFAULT NULL;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    is_weekend BOOLEAN DEFAULT FALSE;

-- Régime V2 Metadata
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    regime_detection_method VARCHAR(30) DEFAULT 'RULE_BASED_V1';
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    regime_atr_median FLOAT DEFAULT NULL;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    regime_atr_smoothed FLOAT DEFAULT NULL;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    regime_confidence FLOAT DEFAULT NULL;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    regime_stability_minutes INT DEFAULT NULL;

-- ML Régime (Phase 3)
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    regime_ml_predicted VARCHAR(20) DEFAULT NULL;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    regime_ml_confidence FLOAT DEFAULT NULL;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    regime_ml_vs_rule_match BOOLEAN DEFAULT NULL;

-- What-If Régime
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    pnl_if_calme_params FLOAT DEFAULT NULL;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    pnl_if_normal_params FLOAT DEFAULT NULL;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    pnl_if_volatile_params FLOAT DEFAULT NULL;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    optimal_regime_retrospective VARCHAR(20) DEFAULT NULL;

-- Session Multiplier appliqué
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    session_atr_multiplier FLOAT DEFAULT 1.0;

-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ TABLE: market_regime_history                                            │
-- │ +7 colonnes pour traçabilité V2                                        │
-- └─────────────────────────────────────────────────────────────────────────┘

ALTER TABLE market_regime_history ADD COLUMN IF NOT EXISTS 
    detection_method VARCHAR(30) DEFAULT 'RULE_BASED_V1';
ALTER TABLE market_regime_history ADD COLUMN IF NOT EXISTS 
    atr_median FLOAT DEFAULT NULL;
ALTER TABLE market_regime_history ADD COLUMN IF NOT EXISTS 
    atr_smoothed FLOAT DEFAULT NULL;
ALTER TABLE market_regime_history ADD COLUMN IF NOT EXISTS 
    session_market VARCHAR(20) DEFAULT NULL;
ALTER TABLE market_regime_history ADD COLUMN IF NOT EXISTS 
    hysteresis_applied BOOLEAN DEFAULT FALSE;
ALTER TABLE market_regime_history ADD COLUMN IF NOT EXISTS 
    outliers_filtered_count INT DEFAULT 0;
ALTER TABLE market_regime_history ADD COLUMN IF NOT EXISTS 
    ml_confidence FLOAT DEFAULT NULL;

-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ TABLE: scan_logs                                                        │
-- │ +4 colonnes pour contexte au moment du scan                            │
-- └─────────────────────────────────────────────────────────────────────────┘

ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS 
    session_market VARCHAR(20) DEFAULT NULL;
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS 
    hour_utc INT DEFAULT NULL;
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS 
    regime_at_scan VARCHAR(20) DEFAULT NULL;
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS 
    regime_confidence_at_scan FLOAT DEFAULT NULL;

-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ INDEX pour performance                                                  │
-- └─────────────────────────────────────────────────────────────────────────┘

CREATE INDEX IF NOT EXISTS idx_tam_session_hour 
    ON trade_atr_metrics(session_market, hour_utc);
CREATE INDEX IF NOT EXISTS idx_tam_regime_method 
    ON trade_atr_metrics(regime_detection_method);
CREATE INDEX IF NOT EXISTS idx_tam_optimal_regime 
    ON trade_atr_metrics(optimal_regime_retrospective);
CREATE INDEX IF NOT EXISTS idx_scan_session 
    ON scan_logs(session_market, hour_utc);
CREATE INDEX IF NOT EXISTS idx_mrh_method 
    ON market_regime_history(detection_method);

-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ VUES d'analyse                                                          │
-- └─────────────────────────────────────────────────────────────────────────┘

-- Performance par Session
CREATE OR REPLACE VIEW v_performance_by_session AS
SELECT 
    tam.session_market,
    COUNT(*) as total_trades,
    SUM(CASE WHEN t.pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN t.pnl_pct <= 0 THEN 1 ELSE 0 END) as losses,
    ROUND(100.0 * SUM(CASE WHEN t.pnl_pct > 0 THEN 1 ELSE 0 END) 
          / NULLIF(COUNT(*), 0), 2) as win_rate,
    ROUND(AVG(t.pnl_pct)::numeric, 4) as avg_pnl_pct,
    ROUND(SUM(t.pnl_pct)::numeric, 4) as total_pnl_pct,
    ROUND(AVG(CASE WHEN t.pnl_pct > 0 THEN t.pnl_pct END)::numeric, 4) as avg_win,
    ROUND(AVG(CASE WHEN t.pnl_pct <= 0 THEN t.pnl_pct END)::numeric, 4) as avg_loss
FROM trade_atr_metrics tam
JOIN trades t ON t.id = tam.trade_id
WHERE tam.session_market IS NOT NULL
GROUP BY tam.session_market
ORDER BY win_rate DESC;

-- Performance par Régime × Session
CREATE OR REPLACE VIEW v_performance_by_regime_session AS
SELECT 
    tam.market_volatility_state as regime,
    tam.session_market,
    COUNT(*) as trades,
    ROUND(100.0 * SUM(CASE WHEN t.pnl_pct > 0 THEN 1 ELSE 0 END) 
          / NULLIF(COUNT(*), 0), 2) as win_rate,
    ROUND(AVG(t.pnl_pct)::numeric, 4) as avg_pnl
FROM trade_atr_metrics tam
JOIN trades t ON t.id = tam.trade_id
WHERE tam.session_market IS NOT NULL 
  AND tam.market_volatility_state IS NOT NULL
GROUP BY tam.market_volatility_state, tam.session_market
HAVING COUNT(*) >= 3
ORDER BY regime, win_rate DESC;

-- Analyse Régime Optimal Rétrospectif
CREATE OR REPLACE VIEW v_optimal_regime_analysis AS
SELECT 
    market_volatility_state as regime_used,
    optimal_regime_retrospective as would_be_optimal,
    COUNT(*) as occurrences,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY market_volatility_state), 2) 
        as pct_of_used_regime,
    ROUND(AVG(CASE 
        WHEN market_volatility_state = optimal_regime_retrospective THEN 1 
        ELSE 0 
    END) * 100, 2) as regime_was_correct_pct
FROM trade_atr_metrics
WHERE optimal_regime_retrospective IS NOT NULL
GROUP BY market_volatility_state, optimal_regime_retrospective
ORDER BY regime_used, occurrences DESC;

-- Performance par Heure UTC
CREATE OR REPLACE VIEW v_performance_by_hour AS
SELECT 
    tam.hour_utc,
    COUNT(*) as trades,
    ROUND(100.0 * SUM(CASE WHEN t.pnl_pct > 0 THEN 1 ELSE 0 END) 
          / NULLIF(COUNT(*), 0), 2) as win_rate,
    ROUND(AVG(t.pnl_pct)::numeric, 4) as avg_pnl
FROM trade_atr_metrics tam
JOIN trades t ON t.id = tam.trade_id
WHERE tam.hour_utc IS NOT NULL
GROUP BY tam.hour_utc
ORDER BY tam.hour_utc;

COMMIT;

-- ═══════════════════════════════════════════════════════════════════════════
-- VÉRIFICATION POST-MIGRATION
-- ═══════════════════════════════════════════════════════════════════════════

-- Lancer cette requête pour vérifier:
-- SELECT column_name, data_type 
-- FROM information_schema.columns 
-- WHERE table_name = 'trade_atr_metrics' 
--   AND column_name LIKE 'session_%' OR column_name LIKE 'regime_%'
-- ORDER BY ordinal_position;
