-- Migration: Ajouter colonne ml_confidence à scan_logs
-- Date: 2025-12-01
-- Description: Stocke la confiance réelle du modèle ML à chaque scan

-- Ajouter la colonne à la table principale (partitionnée)
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS ml_confidence FLOAT;

-- Ajouter la colonne à toutes les partitions existantes
DO $$
DECLARE
    partition_name TEXT;
BEGIN
    FOR partition_name IN 
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename LIKE 'scan_logs_%'
    LOOP
        EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS ml_confidence FLOAT', partition_name);
        RAISE NOTICE 'Colonne ml_confidence ajoutée à %', partition_name;
    END LOOP;
END $$;

-- Ajouter un commentaire pour documenter la colonne
COMMENT ON COLUMN scan_logs.ml_confidence IS 'Confiance réelle du modèle ML (GradientBoosting) en pourcentage (ex: 38.5 = 38.5%)';

-- Vérifier que la colonne a été ajoutée
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'scan_logs' 
AND column_name = 'ml_confidence';
