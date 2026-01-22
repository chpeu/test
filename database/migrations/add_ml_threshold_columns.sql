-- Migration: Ajouter colonnes pour stocker les seuils ML utilisés
-- Date: 16/01/2026
-- Objectif: Permettre l'analyse des seuils ML utilisés lors des rejets

-- Ajouter colonnes pour les seuils ML dans scan_logs
ALTER TABLE scan_logs 
ADD COLUMN IF NOT EXISTS ml_threshold_used DECIMAL(5,2) NULL,  -- Seuil de confiance utilisé (ex: 55.0 pour 55%)
ADD COLUMN IF NOT EXISTS ml_threshold_type VARCHAR(50) NULL,   -- Type de seuil: 'gb_confidence', 'calibration_winrate', 'xgboost_strict', etc.
ADD COLUMN IF NOT EXISTS calibrated_winrate DECIMAL(5,2) NULL; -- Winrate calibré si applicable

-- Index pour optimiser les requêtes d'analyse
CREATE INDEX IF NOT EXISTS idx_scan_logs_ml_threshold ON scan_logs(ml_threshold_type, ml_threshold_used);
CREATE INDEX IF NOT EXISTS idx_scan_logs_reject_category ON scan_logs(reject_reason_category);

-- Commentaires
COMMENT ON COLUMN scan_logs.ml_threshold_used IS 'Seuil de confiance ML utilisé pour la décision (en %)';
COMMENT ON COLUMN scan_logs.ml_threshold_type IS 'Type de seuil ML: gb_confidence, calibration_winrate, xgboost_strict, etc.';
COMMENT ON COLUMN scan_logs.calibrated_winrate IS 'Winrate calibré obtenu via ML calibration (en %)';
