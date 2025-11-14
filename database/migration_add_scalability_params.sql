-- ============================================================================
-- MIGRATION: Ajout des paramètres du scan de scalabilité
-- ============================================================================
-- Date: 2025-11-13
-- Description: Ajoute les colonnes manquantes pour logger les paramètres
--              du scan de scalabilité (recentVolume, vol5, vol15, score)
-- ============================================================================

-- ============================================================================
-- TABLE scan_logs
-- ============================================================================

-- Ajouter recent_volume (Volume des 5 dernières bougies 1m)
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS recent_volume FLOAT;

-- Ajouter vol5 (Volatilité sur 5 périodes en %)
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS vol5 FLOAT;

-- Ajouter vol15 (Volatilité sur 15 périodes en %)
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS vol15 FLOAT;

-- Ajouter scalability_score (Score de scalabilité final)
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS scalability_score FLOAT;

-- Commentaires
COMMENT ON COLUMN scan_logs.recent_volume IS 'Volume total des 5 dernières bougies 1m (utilisé pour calculer le score de scalabilité)';
COMMENT ON COLUMN scan_logs.vol5 IS 'Volatilité sur 5 périodes (écart-type normalisé en %)';
COMMENT ON COLUMN scan_logs.vol15 IS 'Volatilité sur 15 périodes (écart-type normalisé en %)';
COMMENT ON COLUMN scan_logs.scalability_score IS 'Score de scalabilité final calculé par ScalabilityScanner';

-- ============================================================================
-- TABLE trades
-- ============================================================================

-- Entry parameters
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_recent_volume FLOAT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_vol5 FLOAT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_vol15 FLOAT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_scalability_score FLOAT;

-- Exit parameters (optionnel, pour analyse comparative)
ALTER TABLE trades ADD COLUMN IF NOT EXISTS exit_recent_volume FLOAT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS exit_vol5 FLOAT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS exit_vol15 FLOAT;

-- Commentaires
COMMENT ON COLUMN trades.entry_recent_volume IS 'Volume des 5 dernières bougies au moment de l''entrée';
COMMENT ON COLUMN trades.entry_vol5 IS 'Volatilité 5 périodes au moment de l''entrée (%)';
COMMENT ON COLUMN trades.entry_vol15 IS 'Volatilité 15 périodes au moment de l''entrée (%)';
COMMENT ON COLUMN trades.entry_scalability_score IS 'Score de scalabilité au moment de l''entrée';
COMMENT ON COLUMN trades.exit_recent_volume IS 'Volume des 5 dernières bougies au moment de la sortie';
COMMENT ON COLUMN trades.exit_vol5 IS 'Volatilité 5 périodes au moment de la sortie (%)';
COMMENT ON COLUMN trades.exit_vol15 IS 'Volatilité 15 périodes au moment de la sortie (%)';

-- ============================================================================
-- INDEX pour performance (optionnel)
-- ============================================================================

-- Index sur scalability_score pour analyse ML
CREATE INDEX IF NOT EXISTS idx_scan_scalability_score ON scan_logs(scalability_score) 
    WHERE scalability_score IS NOT NULL;

-- Index sur entry_scalability_score pour corrélation avec performance
CREATE INDEX IF NOT EXISTS idx_trade_entry_scalability_score ON trades(entry_scalability_score) 
    WHERE entry_scalability_score IS NOT NULL;

-- ============================================================================
-- VÉRIFICATION
-- ============================================================================

-- Vérifier que les colonnes ont été ajoutées
DO $$
BEGIN
    -- Vérifier scan_logs
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'scan_logs' AND column_name = 'recent_volume'
    ) THEN
        RAISE EXCEPTION 'Colonne recent_volume non trouvée dans scan_logs';
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'scan_logs' AND column_name = 'vol5'
    ) THEN
        RAISE EXCEPTION 'Colonne vol5 non trouvée dans scan_logs';
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'scan_logs' AND column_name = 'scalability_score'
    ) THEN
        RAISE EXCEPTION 'Colonne scalability_score non trouvée dans scan_logs';
    END IF;
    
    -- Vérifier trades
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'trades' AND column_name = 'entry_recent_volume'
    ) THEN
        RAISE EXCEPTION 'Colonne entry_recent_volume non trouvée dans trades';
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'trades' AND column_name = 'entry_scalability_score'
    ) THEN
        RAISE EXCEPTION 'Colonne entry_scalability_score non trouvée dans trades';
    END IF;
    
    RAISE NOTICE '✅ Migration réussie: Toutes les colonnes ont été ajoutées';
END $$;

