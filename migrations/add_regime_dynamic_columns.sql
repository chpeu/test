-- Migration: Ajout des colonnes de paramètres dynamiques du régime
-- Date: 2025-12-08
-- Description: Ajoute les colonnes pour enregistrer les valeurs effectives des paramètres
--              dynamiques du régime au moment de l'entrée en position

-- Table trades: Ajouter les nouvelles colonnes
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_volume_multiplier REAL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_rsi_filter_mode TEXT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_position_timeout INTEGER;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_optimal_atr_max_1m REAL;

-- Table scan_logs: Ajouter les colonnes correspondantes (optionnel)
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS volume_multiplier REAL;
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS rsi_filter_mode TEXT;

-- Commentaires sur les colonnes
COMMENT ON COLUMN trades.entry_volume_multiplier IS 'Multiplicateur volume effectif au moment de entrée (régime dynamique)';
COMMENT ON COLUMN trades.entry_rsi_filter_mode IS 'Mode filtre RSI effectif: STRICT, PERMISSIVE, STANDARD';
COMMENT ON COLUMN trades.entry_position_timeout IS 'Timeout position en secondes effectif au moment de entrée';
COMMENT ON COLUMN trades.entry_optimal_atr_max_1m IS 'ATR max 1m autorisé effectif au moment de entrée';

-- Vérification
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'trades' 
AND column_name IN ('entry_volume_multiplier', 'entry_rsi_filter_mode', 'entry_position_timeout', 'entry_optimal_atr_max_1m')
ORDER BY column_name;
