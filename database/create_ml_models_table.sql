-- Table pour tracker les modèles ML (V1, V2, etc.)
CREATE TABLE IF NOT EXISTS ml_models (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL UNIQUE,  -- xgboost_v1, xgboost_v2, etc.
    model_type VARCHAR(50) NOT NULL,          -- XGBClassifier, XGBClassifier_V2_Temporal, etc.
    version VARCHAR(20) NOT NULL,             -- 1.0, 2.0, etc.
    model_path TEXT NOT NULL,                 -- Chemin vers .pkl
    preprocessor_path TEXT,                   -- Chemin vers preprocessor
    
    -- Métriques d'entraînement
    train_accuracy DOUBLE PRECISION,
    train_roc_auc DOUBLE PRECISION,
    test_accuracy DOUBLE PRECISION,
    test_roc_auc DOUBLE PRECISION,
    val_accuracy DOUBLE PRECISION,           -- V2 uniquement
    val_roc_auc DOUBLE PRECISION,            -- V2 uniquement
    
    -- Gaps (overfitting indicators)
    accuracy_gap DOUBLE PRECISION,
    roc_auc_gap DOUBLE PRECISION,
    
    -- Infos entraînement
    timeframe_days INTEGER,
    min_trades INTEGER,
    total_samples INTEGER,
    train_samples INTEGER,
    test_samples INTEGER,
    val_samples INTEGER,                     -- V2 uniquement
    training_time_seconds DOUBLE PRECISION,
    
    -- Paramètres spécifiques V2
    filter_marginal_trades BOOLEAN,
    marginal_threshold DOUBLE PRECISION,
    split_type VARCHAR(20),                  -- 'random' or 'temporal'
    max_features INTEGER,                    -- Nombre features sélectionnées
    
    -- Hyperparamètres du modèle (JSONB pour flexibilité)
    model_params JSONB,
    
    -- Feature importance (top 10)
    feature_importance JSONB,
    
    -- Statut
    is_active BOOLEAN DEFAULT FALSE,         -- Modèle actuellement utilisé
    
    -- Timestamps
    trained_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Index pour recherche rapide
CREATE INDEX IF NOT EXISTS idx_ml_models_name ON ml_models(model_name);
CREATE INDEX IF NOT EXISTS idx_ml_models_active ON ml_models(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_ml_models_trained_at ON ml_models(trained_at DESC);

-- Fonction pour mettre à jour updated_at automatiquement
CREATE OR REPLACE FUNCTION update_ml_models_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger
DROP TRIGGER IF EXISTS trigger_ml_models_updated_at ON ml_models;
CREATE TRIGGER trigger_ml_models_updated_at
    BEFORE UPDATE ON ml_models
    FOR EACH ROW
    EXECUTE FUNCTION update_ml_models_updated_at();

-- Commentaires
COMMENT ON TABLE ml_models IS 'Table pour tracker les différentes versions de modèles ML (V1, V2, etc.)';
COMMENT ON COLUMN ml_models.model_name IS 'Nom unique du modèle (xgboost_v1, xgboost_v2, etc.)';
COMMENT ON COLUMN ml_models.split_type IS 'Type de split: random (V1) ou temporal (V2)';
COMMENT ON COLUMN ml_models.is_active IS 'TRUE si c''est le modèle actuellement utilisé pour les prédictions';
COMMENT ON COLUMN ml_models.filter_marginal_trades IS 'V2: TRUE si les trades marginaux ont été filtrés lors de l''entraînement';
COMMENT ON COLUMN ml_models.val_accuracy IS 'V2: Accuracy sur le set de validation (absent en V1)';
