-- ============================================================
-- Migration: ML Auto-Calibration System
-- Description: Table pour stocker les statistiques de calibration ML
--              Permet de recalibrer la confiance ML selon les résultats live réels
-- Date: 2025-12-04
-- ============================================================

-- Table principale de calibration
CREATE TABLE IF NOT EXISTS ml_calibration (
    id SERIAL PRIMARY KEY,
    
    -- Clé composite: direction + bucket de confiance
    direction VARCHAR(10) NOT NULL,              -- 'LONG' ou 'SHORT'
    confidence_bucket VARCHAR(10) NOT NULL,      -- '30-35', '35-40', '40-45', '45-50', '50+'
    
    -- Statistiques pondérées
    weighted_wins DECIMAL(12, 4) DEFAULT 0,      -- Somme des poids des trades gagnants
    weighted_total DECIMAL(12, 4) DEFAULT 0,     -- Somme des poids de tous les trades
    total_trades INTEGER DEFAULT 0,              -- Nombre total de trades (non pondéré)
    
    -- Winrate calculé (pondéré)
    actual_winrate DECIMAL(5, 2),                -- WR réel = weighted_wins / weighted_total * 100
    
    -- PnL moyen
    avg_pnl_pct DECIMAL(8, 4) DEFAULT 0,         -- PnL moyen en % (pondéré)
    total_pnl_usdt DECIMAL(12, 4) DEFAULT 0,     -- PnL total en USDT
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Contrainte d'unicité
    CONSTRAINT ml_calibration_unique UNIQUE (direction, confidence_bucket)
);

-- Index pour recherche rapide
CREATE INDEX IF NOT EXISTS idx_ml_calibration_lookup 
ON ml_calibration(direction, confidence_bucket);

-- Fonction pour mettre à jour updated_at automatiquement
CREATE OR REPLACE FUNCTION update_ml_calibration_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    -- Calculer le winrate automatiquement
    IF NEW.weighted_total > 0 THEN
        NEW.actual_winrate = (NEW.weighted_wins / NEW.weighted_total) * 100;
    ELSE
        NEW.actual_winrate = NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger pour mise à jour automatique
DROP TRIGGER IF EXISTS trigger_ml_calibration_update ON ml_calibration;
CREATE TRIGGER trigger_ml_calibration_update
BEFORE UPDATE ON ml_calibration
FOR EACH ROW EXECUTE FUNCTION update_ml_calibration_timestamp();

-- Initialiser les buckets pour chaque direction
INSERT INTO ml_calibration (direction, confidence_bucket, weighted_wins, weighted_total, total_trades)
VALUES 
    ('LONG', '30-35', 0, 0, 0),
    ('LONG', '35-40', 0, 0, 0),
    ('LONG', '40-45', 0, 0, 0),
    ('LONG', '45-50', 0, 0, 0),
    ('LONG', '50+', 0, 0, 0),
    ('SHORT', '30-35', 0, 0, 0),
    ('SHORT', '35-40', 0, 0, 0),
    ('SHORT', '40-45', 0, 0, 0),
    ('SHORT', '45-50', 0, 0, 0),
    ('SHORT', '50+', 0, 0, 0)
ON CONFLICT (direction, confidence_bucket) DO NOTHING;

-- Table d'historique pour tracking des recalibrations (optionnel)
CREATE TABLE IF NOT EXISTS ml_calibration_history (
    id SERIAL PRIMARY KEY,
    direction VARCHAR(10) NOT NULL,
    confidence_bucket VARCHAR(10) NOT NULL,
    actual_winrate DECIMAL(5, 2),
    total_trades INTEGER,
    snapshot_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    reason VARCHAR(50)  -- 'daily_snapshot', 'model_reset', 'manual_reset'
);

-- Commentaires
COMMENT ON TABLE ml_calibration IS 'Statistiques de calibration ML pour recalibrer la confiance selon résultats live réels';
COMMENT ON COLUMN ml_calibration.weighted_wins IS 'Somme des poids des trades gagnants (trades récents/live comptent plus)';
COMMENT ON COLUMN ml_calibration.weighted_total IS 'Somme des poids de tous les trades';
COMMENT ON COLUMN ml_calibration.actual_winrate IS 'Winrate réel observé = weighted_wins / weighted_total * 100';

-- Verification
SELECT 'Table ml_calibration créée avec succès' as status;
SELECT * FROM ml_calibration ORDER BY direction, confidence_bucket;
