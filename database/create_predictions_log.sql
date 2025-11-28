-- Table pour logger les prédictions ML et leurs résultats
CREATE TABLE IF NOT EXISTS predictions_log (
    id SERIAL PRIMARY KEY,
    
    -- Metadata prédiction
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    model_name VARCHAR(50) NOT NULL,
    model_version VARCHAR(20),
    
    -- Opportunité source
    scan_id INTEGER REFERENCES scan_logs(id) ON DELETE SET NULL,
    symbol VARCHAR(20) NOT NULL,
    opportunity_timestamp TIMESTAMP,
    
    -- Prédiction ML
    prediction VARCHAR(10) NOT NULL, -- 'win' ou 'loss'
    win_probability FLOAT NOT NULL,
    loss_probability FLOAT NOT NULL,
    confidence FLOAT NOT NULL,
    
    -- Features importantes pour cette prédiction
    top_features JSONB,
    
    -- Trade associé (si exécuté)
    trade_id INTEGER REFERENCES trades(id) ON DELETE SET NULL,
    trade_executed BOOLEAN DEFAULT FALSE,
    
    -- Résultat réel (rempli après fermeture du trade)
    actual_result VARCHAR(10), -- 'win', 'loss', ou NULL si pas encore fermé
    actual_pnl FLOAT,
    actual_pnl_pct FLOAT,
    trade_closed_at TIMESTAMP,
    
    -- Métriques de performance
    correct_prediction BOOLEAN, -- TRUE si prediction = actual_result
    confidence_calibrated BOOLEAN, -- TRUE si confidence était justifiée
    
    -- Performance du modèle au moment de la prédiction
    model_test_accuracy FLOAT,
    model_test_f1 FLOAT,
    
    -- Métadata additionnelle
    metadata JSONB,
    
    -- Index
    CONSTRAINT valid_prediction CHECK (prediction IN ('win', 'loss')),
    CONSTRAINT valid_actual_result CHECK (actual_result IS NULL OR actual_result IN ('win', 'loss'))
);

-- Index pour performance
CREATE INDEX IF NOT EXISTS idx_predictions_timestamp ON predictions_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_symbol ON predictions_log(symbol);
CREATE INDEX IF NOT EXISTS idx_predictions_model ON predictions_log(model_name);
CREATE INDEX IF NOT EXISTS idx_predictions_trade ON predictions_log(trade_id);
CREATE INDEX IF NOT EXISTS idx_predictions_scan ON predictions_log(scan_id);
CREATE INDEX IF NOT EXISTS idx_predictions_result ON predictions_log(actual_result) WHERE actual_result IS NOT NULL;

-- Vue pour analytics des prédictions
CREATE OR REPLACE VIEW predictions_analytics AS
SELECT 
    model_name,
    COUNT(*) as total_predictions,
    COUNT(CASE WHEN actual_result IS NOT NULL THEN 1 END) as evaluated_predictions,
    COUNT(CASE WHEN correct_prediction = TRUE THEN 1 END) as correct_predictions,
    ROUND(AVG(CASE WHEN correct_prediction = TRUE THEN 1.0 ELSE 0.0 END) * 100, 2) as accuracy_pct,
    ROUND(AVG(confidence) * 100, 2) as avg_confidence_pct,
    COUNT(CASE WHEN prediction = 'win' THEN 1 END) as win_predictions,
    COUNT(CASE WHEN prediction = 'loss' THEN 1 END) as loss_predictions,
    COUNT(CASE WHEN trade_executed = TRUE THEN 1 END) as trades_executed,
    ROUND(AVG(CASE WHEN trade_executed = TRUE THEN actual_pnl_pct END), 2) as avg_pnl_pct_executed,
    MIN(timestamp) as first_prediction,
    MAX(timestamp) as last_prediction
FROM predictions_log
GROUP BY model_name;

-- Vue pour tracking prédictions par symbole
CREATE OR REPLACE VIEW predictions_by_symbol AS
SELECT 
    symbol,
    COUNT(*) as total_predictions,
    COUNT(CASE WHEN correct_prediction = TRUE THEN 1 END) as correct,
    ROUND(AVG(CASE WHEN correct_prediction = TRUE THEN 1.0 ELSE 0.0 END) * 100, 2) as accuracy_pct,
    COUNT(CASE WHEN prediction = 'win' THEN 1 END) as win_predictions,
    COUNT(CASE WHEN actual_result = 'win' THEN 1 END) as actual_wins,
    ROUND(AVG(confidence) * 100, 2) as avg_confidence_pct
FROM predictions_log
WHERE actual_result IS NOT NULL
GROUP BY symbol
ORDER BY total_predictions DESC;

-- Vue pour prédictions récentes avec leur statut
CREATE OR REPLACE VIEW recent_predictions AS
SELECT 
    pl.id,
    pl.timestamp,
    pl.symbol,
    pl.prediction,
    ROUND(pl.win_probability * 100, 1) as win_prob_pct,
    ROUND(pl.confidence * 100, 1) as confidence_pct,
    pl.trade_executed,
    pl.actual_result,
    pl.correct_prediction,
    ROUND(pl.actual_pnl_pct, 2) as pnl_pct,
    pl.model_name,
    CASE 
        WHEN pl.actual_result IS NULL AND pl.trade_executed THEN 'PENDING'
        WHEN pl.actual_result IS NULL THEN 'NOT_EXECUTED'
        WHEN pl.correct_prediction THEN 'CORRECT'
        ELSE 'INCORRECT'
    END as status
FROM predictions_log pl
ORDER BY pl.timestamp DESC
LIMIT 50;

COMMENT ON TABLE predictions_log IS 'Log de toutes les prédictions ML avec leur résultat réel';
COMMENT ON VIEW predictions_analytics IS 'Analytics globales par modèle';
COMMENT ON VIEW predictions_by_symbol IS 'Performance des prédictions par symbole';
COMMENT ON VIEW recent_predictions IS '50 dernières prédictions avec leur statut';
