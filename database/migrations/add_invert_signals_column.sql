-- Migration: Ajouter config_invert_signals à la table trades
-- Créé le: 2025-01-03

-- Ajouter config_invert_signals (boolean) pour tracer l'inversion des signaux
ALTER TABLE trades 
ADD COLUMN IF NOT EXISTS config_invert_signals BOOLEAN;

-- Commentaire descriptif
COMMENT ON COLUMN trades.config_invert_signals IS 'Configuration: Inversion des signaux LONG ⟷ SHORT activée au moment du trade';

-- Index optionnel pour filtrage par inversion de signaux
CREATE INDEX IF NOT EXISTS idx_trades_config_invert_signals ON trades (config_invert_signals) WHERE config_invert_signals IS NOT NULL;

-- Migration complétée
SELECT 'Migration add_invert_signals_column.sql terminée' as status;
