-- Migration: Ajouter ml_optimal_trailing_distance à trade_post_exit_analysis
-- Date: 2026-01-19
-- Description: Ajoute la colonne pour stocker la distance trailing optimale calculée
--              par simulation tick-by-tick des samples post-exit

-- 1. Ajouter la colonne
ALTER TABLE trade_post_exit_analysis 
ADD COLUMN IF NOT EXISTS ml_optimal_trailing_distance FLOAT;

-- 2. Ajouter un commentaire descriptif
COMMENT ON COLUMN trade_post_exit_analysis.ml_optimal_trailing_distance IS 
'Distance trailing optimale calculée par simulation tick-by-tick (en %)';

-- 3. Créer un index pour les requêtes d'analyse
CREATE INDEX IF NOT EXISTS idx_post_exit_ml_trailing_distance 
ON trade_post_exit_analysis(ml_optimal_trailing_distance) 
WHERE ml_optimal_trailing_distance IS NOT NULL;

-- 4. Vérification
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'trade_post_exit_analysis' 
        AND column_name = 'ml_optimal_trailing_distance'
    ) THEN
        RAISE NOTICE '✅ Colonne ml_optimal_trailing_distance ajoutée avec succès';
    ELSE
        RAISE EXCEPTION '❌ Échec: colonne ml_optimal_trailing_distance non trouvée';
    END IF;
END $$;
