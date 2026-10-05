-- Migration: Ajouter la persistance des trackers post-exit actifs
-- Permet de survivre aux redémarrages du backend

-- Table pour stocker les trackers actifs
CREATE TABLE IF NOT EXISTS post_exit_active_trackers (
    id SERIAL PRIMARY KEY,
    trade_id TEXT NOT NULL UNIQUE,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    
    -- Contexte de sortie
    exit_price DECIMAL(20, 8) NOT NULL,
    exit_timestamp TIMESTAMPTZ NOT NULL,
    exit_reason TEXT,
    realized_pnl_pct DECIMAL(10, 4),
    realized_pnl_usdt DECIMAL(20, 8),
    
    -- Niveaux originaux
    original_sl DECIMAL(20, 8),
    original_tp DECIMAL(20, 8),
    entry_price DECIMAL(20, 8) NOT NULL,
    
    -- Paramètres utilisés
    used_sl_pct DECIMAL(10, 4),
    used_tp_pct DECIMAL(10, 4),
    used_be_trigger DECIMAL(10, 4),
    used_trailing_trigger DECIMAL(10, 4),
    used_trailing_min_distance DECIMAL(10, 4),
    used_partial_tp_pct DECIMAL(10, 4),
    
    -- Configuration tracking
    tracking_duration_sec INT NOT NULL DEFAULT 600,
    sample_interval_ms INT NOT NULL DEFAULT 2000,
    
    -- État actuel
    start_time TIMESTAMPTZ NOT NULL,
    samples_collected INT NOT NULL DEFAULT 0,
    
    -- Métriques calculées (état courant)
    post_exit_mfe_pct DECIMAL(10, 4) DEFAULT 0,
    post_exit_mfe_price DECIMAL(20, 8),
    post_exit_mfe_timestamp TIMESTAMPTZ,
    post_exit_mae_pct DECIMAL(10, 4) DEFAULT 0,
    post_exit_mae_price DECIMAL(20, 8),
    post_exit_mae_timestamp TIMESTAMPTZ,
    
    -- Flags
    would_have_hit_original_tp BOOLEAN DEFAULT FALSE,
    would_have_hit_original_sl BOOLEAN DEFAULT FALSE,
    price_returned_to_entry BOOLEAN DEFAULT FALSE,
    
    -- Samples stockés en JSON (compact)
    samples_json JSONB DEFAULT '[]'::jsonb,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index pour recherche rapide par symbol
CREATE INDEX IF NOT EXISTS idx_post_exit_active_trackers_symbol 
ON post_exit_active_trackers(symbol);

-- Index pour nettoyage des trackers expirés
CREATE INDEX IF NOT EXISTS idx_post_exit_active_trackers_start_time 
ON post_exit_active_trackers(start_time);

-- Trigger pour mettre à jour updated_at automatiquement
CREATE OR REPLACE FUNCTION update_post_exit_tracker_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_post_exit_tracker_timestamp 
ON post_exit_active_trackers;

CREATE TRIGGER trigger_update_post_exit_tracker_timestamp
BEFORE UPDATE ON post_exit_active_trackers
FOR EACH ROW
EXECUTE FUNCTION update_post_exit_tracker_timestamp();

-- Commentaires
COMMENT ON TABLE post_exit_active_trackers IS 'Stocke les trackers post-exit actifs pour survivre aux redémarrages';
COMMENT ON COLUMN post_exit_active_trackers.samples_json IS 'Échantillons de prix collectés en format JSON compact';
