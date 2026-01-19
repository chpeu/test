-- ============================================================================
-- MIGRATION: Add Market Regime columns to opportunities table
-- 19/01/2026
-- ============================================================================
-- Ces colonnes permettent de tracker le contexte Market Regime pour chaque
-- opportunité détectée, pour analyse ML et optimisation.
-- ============================================================================

-- ============================================================================
-- TABLE opportunities : Contexte Market Regime au moment de l'opportunité
-- ============================================================================

-- Régime de marché actif
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS market_regime VARCHAR(20);
COMMENT ON COLUMN opportunities.market_regime IS 'Régime marché: CALME, NORMAL, VOLATILE, CHOPPY, UNKNOWN';

-- Contexte session (JSON)
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS session_context JSONB;
COMMENT ON COLUMN opportunities.session_context IS 'Contexte session market (Asian, European, US, etc.)';

-- Score du régime
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS market_regime_score FLOAT;
COMMENT ON COLUMN opportunities.market_regime_score IS 'Score du régime de marché';

-- Confiance du régime
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS market_regime_confidence FLOAT;
COMMENT ON COLUMN opportunities.market_regime_confidence IS 'Niveau de confiance du régime (0-1)';

-- Raison du régime
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS market_regime_reason TEXT;
COMMENT ON COLUMN opportunities.market_regime_reason IS 'Raison/explication du régime détecté';

-- Détails du régime (JSON)
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS market_regime_details JSONB;
COMMENT ON COLUMN opportunities.market_regime_details IS 'Détails techniques du régime (métriques, seuils, etc.)';

-- Signal du régime
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS market_regime_signal VARCHAR(50);
COMMENT ON COLUMN opportunities.market_regime_signal IS 'Signal spécifique du régime (ex: BREAKOUT, REVERSAL, etc.)';

-- Index pour analyses
CREATE INDEX IF NOT EXISTS idx_opp_market_regime ON opportunities(market_regime) WHERE market_regime IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_opp_regime_status ON opportunities(market_regime, status) WHERE market_regime IS NOT NULL;

-- ============================================================================
-- FIN MIGRATION
-- ============================================================================
