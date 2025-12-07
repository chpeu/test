-- ============================================================================
-- MIGRATION: Ajout colonnes Order Flow pour ML avancé
-- Date: 2024-11-30
-- Description: Ajoute des colonnes pour capturer l'order flow et la microstructure
-- ============================================================================

-- Ces colonnes seront remplies pendant les scans pour le ML futur
-- Même si non utilisées immédiatement, elles collectent de la data

-- 1. Delta volume (différence bid - ask, pression nette)
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS delta_volume FLOAT;
COMMENT ON COLUMN scan_logs.delta_volume IS 'bid_vol - ask_vol, pression nette du marché';

-- 2. Imbalance ratio normalisé [-1, +1] (plus précis que bid/ask ratio)
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS imbalance_normalized FLOAT;
COMMENT ON COLUMN scan_logs.imbalance_normalized IS '(bid-ask)/(bid+ask), normalisé entre -1 et +1';

-- 3. Spread volatilité (sur les 5 dernières bougies)
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS spread_volatility_5 FLOAT;
COMMENT ON COLUMN scan_logs.spread_volatility_5 IS 'Écart-type du spread sur 5 bougies';

-- 4. Book depth ratio (profondeur relative)
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS book_depth_ratio FLOAT;
COMMENT ON COLUMN scan_logs.book_depth_ratio IS 'Ratio profondeur bid vs ask dans le carnet';

-- 5. Volume acceleration (changement de volume)
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS volume_acceleration FLOAT;
COMMENT ON COLUMN scan_logs.volume_acceleration IS 'Accélération du volume (dérivée)';

-- 6. Price momentum (vitesse du prix)
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS price_momentum_5 FLOAT;
COMMENT ON COLUMN scan_logs.price_momentum_5 IS 'Momentum prix sur 5 bougies (% change)';

-- Ajouter aussi dans opportunities si la table existe
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'opportunities') THEN
        ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS delta_volume FLOAT;
        ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS imbalance_normalized FLOAT;
        ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS spread_volatility_5 FLOAT;
        ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS book_depth_ratio FLOAT;
        ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS volume_acceleration FLOAT;
        ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS price_momentum_5 FLOAT;
    END IF;
END $$;

-- Index pour requêtes ML
CREATE INDEX IF NOT EXISTS idx_scan_logs_delta_volume ON scan_logs(delta_volume) WHERE delta_volume IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_scan_logs_imbalance ON scan_logs(imbalance_normalized) WHERE imbalance_normalized IS NOT NULL;

-- Vérification
SELECT 
    column_name, 
    data_type 
FROM information_schema.columns 
WHERE table_name = 'scan_logs' 
AND column_name IN ('delta_volume', 'imbalance_normalized', 'spread_volatility_5', 'book_depth_ratio', 'volume_acceleration', 'price_momentum_5')
ORDER BY column_name;
