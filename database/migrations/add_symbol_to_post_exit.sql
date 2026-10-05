-- Migration: Ajouter colonne symbol à trade_post_exit_analysis
-- Date: 2026-01-19
-- Raison: Permettre les requêtes directes par symbol sans JOIN

-- 1. Ajouter la colonne symbol
ALTER TABLE trade_post_exit_analysis 
ADD COLUMN IF NOT EXISTS symbol VARCHAR(50);

-- 2. Index pour recherche par symbol
CREATE INDEX IF NOT EXISTS idx_post_exit_symbol 
ON trade_post_exit_analysis(symbol);

-- 3. Remplir les symbols existants via JOIN
UPDATE trade_post_exit_analysis pea
SET symbol = t.symbol
FROM trades t
WHERE pea.trade_id::text = t.id::text
AND pea.symbol IS NULL;

-- 4. Vérification
SELECT 
    COUNT(*) as total,
    COUNT(symbol) as with_symbol,
    COUNT(*) - COUNT(symbol) as without_symbol
FROM trade_post_exit_analysis;
