-- Migration: Ajout de la colonne model_version à ml_calibration pour auto-reset
-- Date: 2025-12-20
-- Objectif: Permettre le tracking des versions de modèle GB pour auto-reset calibration

-- Ajout de la colonne model_version à la table ml_calibration
ALTER TABLE ml_calibration 
ADD COLUMN IF NOT EXISTS model_version VARCHAR(50) DEFAULT NULL;

-- Ajout d'un index pour optimiser les requêtes de recherche de version
CREATE INDEX IF NOT EXISTS idx_ml_calibration_model_version 
ON ml_calibration(model_version);

-- Commentaire sur la colonne
COMMENT ON COLUMN ml_calibration.model_version IS 'Timestamp du modèle GB utilisé pour cette calibration (format: 2025-12-20T00:41:39.610296)';

-- Mise à jour des entrées existantes avec une version par défaut si nécessaire
-- (optionnel - peut être fait par l'application)
UPDATE ml_calibration 
SET model_version = 'pre-auto-reset' 
WHERE model_version IS NULL 
AND created_at < NOW() - INTERVAL '1 day';

-- Vérification de la migration
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ml_calibration' 
        AND column_name = 'model_version'
    ) THEN
        RAISE NOTICE 'Migration réussie: colonne model_version ajoutée à ml_calibration';
    ELSE
        RAISE EXCEPTION 'Migration échouée: colonne model_version non trouvée';
    END IF;
END $$;
