-- Migration: Ajouter colonnes pour métriques de régression (XGBoost V2)
-- Date: 2025-11-25
-- Description: Ajoute les colonnes R², MAE, MSE pour les modèles de régression (V2)

-- Ajouter colonnes R² (coefficient de détermination)
ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS train_r2 DOUBLE PRECISION;
ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS val_r2 DOUBLE PRECISION;
ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS test_r2 DOUBLE PRECISION;

-- Ajouter colonnes MAE (Mean Absolute Error)
ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS train_mae DOUBLE PRECISION;
ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS val_mae DOUBLE PRECISION;
ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS test_mae DOUBLE PRECISION;

-- Ajouter colonnes MSE (Mean Squared Error)
ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS train_mse DOUBLE PRECISION;
ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS val_mse DOUBLE PRECISION;
ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS test_mse DOUBLE PRECISION;

-- Ajouter colonne F1 test (classification binaire avec seuil 0)
ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS test_f1 DOUBLE PRECISION;

-- Ajouter colonnes pour features sélectionnées
ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS selected_features JSONB;
ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS feature_selection_scores JSONB;

-- Commentaires
COMMENT ON COLUMN ml_models.train_r2 IS 'R² Score sur train set (régression V2)';
COMMENT ON COLUMN ml_models.val_r2 IS 'R² Score sur validation set (régression V2)';
COMMENT ON COLUMN ml_models.test_r2 IS 'R² Score sur test set (régression V2)';
COMMENT ON COLUMN ml_models.train_mae IS 'Mean Absolute Error sur train set (régression V2)';
COMMENT ON COLUMN ml_models.val_mae IS 'Mean Absolute Error sur validation set (régression V2)';
COMMENT ON COLUMN ml_models.test_mae IS 'Mean Absolute Error sur test set (régression V2)';
COMMENT ON COLUMN ml_models.train_mse IS 'Mean Squared Error sur train set (régression V2)';
COMMENT ON COLUMN ml_models.val_mse IS 'Mean Squared Error sur validation set (régression V2)';
COMMENT ON COLUMN ml_models.test_mse IS 'Mean Squared Error sur test set (régression V2)';
COMMENT ON COLUMN ml_models.test_f1 IS 'F1 Score avec seuil 0 (classification binaire WIN/LOSS)';
COMMENT ON COLUMN ml_models.selected_features IS 'Liste des features sélectionnées après feature selection';
COMMENT ON COLUMN ml_models.feature_selection_scores IS 'Scores de sélection (mutual information, etc.)';

-- Afficher résultat
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns
WHERE table_name = 'ml_models'
  AND column_name IN ('train_r2', 'val_r2', 'test_r2', 'train_mae', 'val_mae', 'test_mae', 'test_f1')
ORDER BY column_name;
