-- ============================================================================
-- MIGRATION: Ajouter colonnes config_* extraites de params_snapshot
-- ============================================================================
-- Date: 2025-11-24
-- Description: Ajoute les colonnes config_* individuelles pour scan_logs et trades
--              afin d'être compatible avec le code actuel et la vue ml_features
-- ============================================================================

-- ============================================================================
-- TABLE scan_logs - Ajouter colonnes config_*
-- ============================================================================

DO $$
BEGIN
    -- Config columns pour scan_logs
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scan_logs' AND column_name = 'config_min_score_required') THEN
        ALTER TABLE scan_logs ADD COLUMN config_min_score_required FLOAT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scan_logs' AND column_name = 'config_snr_threshold') THEN
        ALTER TABLE scan_logs ADD COLUMN config_snr_threshold FLOAT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scan_logs' AND column_name = 'config_atr_min_1m') THEN
        ALTER TABLE scan_logs ADD COLUMN config_atr_min_1m FLOAT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scan_logs' AND column_name = 'config_atr_max_1m') THEN
        ALTER TABLE scan_logs ADD COLUMN config_atr_max_1m FLOAT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scan_logs' AND column_name = 'config_atr_min_5m') THEN
        ALTER TABLE scan_logs ADD COLUMN config_atr_min_5m FLOAT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scan_logs' AND column_name = 'config_atr_max_5m') THEN
        ALTER TABLE scan_logs ADD COLUMN config_atr_max_5m FLOAT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scan_logs' AND column_name = 'config_volume_multiplier') THEN
        ALTER TABLE scan_logs ADD COLUMN config_volume_multiplier FLOAT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scan_logs' AND column_name = 'config_use_confluence') THEN
        ALTER TABLE scan_logs ADD COLUMN config_use_confluence BOOLEAN;
    END IF;

    -- 🔥 OPT #15-19: Filtres avancés
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scan_logs' AND column_name = 'config_use_anti_whipsaw') THEN
        ALTER TABLE scan_logs ADD COLUMN config_use_anti_whipsaw BOOLEAN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scan_logs' AND column_name = 'config_whipsaw_lookback') THEN
        ALTER TABLE scan_logs ADD COLUMN config_whipsaw_lookback INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scan_logs' AND column_name = 'config_whipsaw_threshold_pct') THEN
        ALTER TABLE scan_logs ADD COLUMN config_whipsaw_threshold_pct FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scan_logs' AND column_name = 'config_whipsaw_max_alternations') THEN
        ALTER TABLE scan_logs ADD COLUMN config_whipsaw_max_alternations INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scan_logs' AND column_name = 'config_use_retest_confirmation') THEN
        ALTER TABLE scan_logs ADD COLUMN config_use_retest_confirmation BOOLEAN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scan_logs' AND column_name = 'config_retest_tolerance_pct') THEN
        ALTER TABLE scan_logs ADD COLUMN config_retest_tolerance_pct FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scan_logs' AND column_name = 'config_retest_timeout_seconds') THEN
        ALTER TABLE scan_logs ADD COLUMN config_retest_timeout_seconds INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scan_logs' AND column_name = 'config_use_cooldown') THEN
        ALTER TABLE scan_logs ADD COLUMN config_use_cooldown BOOLEAN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scan_logs' AND column_name = 'config_cooldown_seconds') THEN
        ALTER TABLE scan_logs ADD COLUMN config_cooldown_seconds INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scan_logs' AND column_name = 'config_cooldown_same_symbol') THEN
        ALTER TABLE scan_logs ADD COLUMN config_cooldown_same_symbol INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scan_logs' AND column_name = 'config_use_candle_close') THEN
        ALTER TABLE scan_logs ADD COLUMN config_use_candle_close BOOLEAN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scan_logs' AND column_name = 'config_candle_close_threshold_seconds') THEN
        ALTER TABLE scan_logs ADD COLUMN config_candle_close_threshold_seconds INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scan_logs' AND column_name = 'config_use_momentum_continuity') THEN
        ALTER TABLE scan_logs ADD COLUMN config_use_momentum_continuity BOOLEAN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scan_logs' AND column_name = 'config_momentum_lookback') THEN
        ALTER TABLE scan_logs ADD COLUMN config_momentum_lookback INTEGER;
    END IF;
    
    RAISE NOTICE '✅ Colonnes config_* ajoutées à scan_logs';
END $$;

-- Commentaires pour scan_logs
COMMENT ON COLUMN scan_logs.config_min_score_required IS 'Score minimum requis (extrait de params_snapshot)';
COMMENT ON COLUMN scan_logs.config_snr_threshold IS 'Seuil SNR (extrait de params_snapshot)';
COMMENT ON COLUMN scan_logs.config_atr_min_1m IS 'ATR min 1m (extrait de params_snapshot)';
COMMENT ON COLUMN scan_logs.config_atr_max_1m IS 'ATR max 1m (extrait de params_snapshot)';
COMMENT ON COLUMN scan_logs.config_atr_min_5m IS 'ATR min 5m (extrait de params_snapshot)';
COMMENT ON COLUMN scan_logs.config_atr_max_5m IS 'ATR max 5m (extrait de params_snapshot)';
COMMENT ON COLUMN scan_logs.config_volume_multiplier IS 'Multiplicateur volume (extrait de params_snapshot)';
COMMENT ON COLUMN scan_logs.config_use_confluence IS 'Mode confluence activé (extrait de params_snapshot)';
COMMENT ON COLUMN scan_logs.config_use_anti_whipsaw IS 'Filtre anti-whipsaw activé (extrait de params_snapshot)';
COMMENT ON COLUMN scan_logs.config_whipsaw_lookback IS 'Lookback whipsaw (extrait de params_snapshot)';
COMMENT ON COLUMN scan_logs.config_whipsaw_threshold_pct IS 'Seuil whipsaw % (extrait de params_snapshot)';
COMMENT ON COLUMN scan_logs.config_whipsaw_max_alternations IS 'Max alternances whipsaw (extrait de params_snapshot)';
COMMENT ON COLUMN scan_logs.config_use_retest_confirmation IS 'Retest breakout activé (extrait de params_snapshot)';
COMMENT ON COLUMN scan_logs.config_retest_tolerance_pct IS 'Tolérance retest % (extrait de params_snapshot)';
COMMENT ON COLUMN scan_logs.config_retest_timeout_seconds IS 'Timeout retest (extrait de params_snapshot)';
COMMENT ON COLUMN scan_logs.config_use_cooldown IS 'Cooldown activé (extrait de params_snapshot)';
COMMENT ON COLUMN scan_logs.config_cooldown_seconds IS 'Cooldown global (extrait de params_snapshot)';
COMMENT ON COLUMN scan_logs.config_cooldown_same_symbol IS 'Cooldown même symbole (extrait de params_snapshot)';
COMMENT ON COLUMN scan_logs.config_use_candle_close IS 'Confirmation fermeture bougie (extrait de params_snapshot)';
COMMENT ON COLUMN scan_logs.config_candle_close_threshold_seconds IS 'Seuil fermeture bougie (extrait de params_snapshot)';
COMMENT ON COLUMN scan_logs.config_use_momentum_continuity IS 'Filtre momentum activé (extrait de params_snapshot)';
COMMENT ON COLUMN scan_logs.config_momentum_lookback IS 'Lookback momentum (extrait de params_snapshot)';

-- ============================================================================
-- TABLE trades - Ajouter colonnes config_*
-- ============================================================================

DO $$
BEGIN
    -- Config columns pour trades
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_min_score_required') THEN
        ALTER TABLE trades ADD COLUMN config_min_score_required FLOAT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_snr_threshold') THEN
        ALTER TABLE trades ADD COLUMN config_snr_threshold FLOAT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_optimal_atr_min_1m') THEN
        ALTER TABLE trades ADD COLUMN config_optimal_atr_min_1m FLOAT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_optimal_atr_max_1m') THEN
        ALTER TABLE trades ADD COLUMN config_optimal_atr_max_1m FLOAT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_optimal_atr_min_5m') THEN
        ALTER TABLE trades ADD COLUMN config_optimal_atr_min_5m FLOAT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_optimal_atr_max_5m') THEN
        ALTER TABLE trades ADD COLUMN config_optimal_atr_max_5m FLOAT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_volume_multiplier') THEN
        ALTER TABLE trades ADD COLUMN config_volume_multiplier FLOAT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_use_confluence') THEN
        ALTER TABLE trades ADD COLUMN config_use_confluence BOOLEAN;
    END IF;

    -- 🔥 OPT #15-19: Filtres avancés
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_use_anti_whipsaw') THEN
        ALTER TABLE trades ADD COLUMN config_use_anti_whipsaw BOOLEAN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_whipsaw_lookback') THEN
        ALTER TABLE trades ADD COLUMN config_whipsaw_lookback INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_whipsaw_threshold_pct') THEN
        ALTER TABLE trades ADD COLUMN config_whipsaw_threshold_pct FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_whipsaw_max_alternations') THEN
        ALTER TABLE trades ADD COLUMN config_whipsaw_max_alternations INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_use_retest_confirmation') THEN
        ALTER TABLE trades ADD COLUMN config_use_retest_confirmation BOOLEAN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_retest_tolerance_pct') THEN
        ALTER TABLE trades ADD COLUMN config_retest_tolerance_pct FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_retest_timeout_seconds') THEN
        ALTER TABLE trades ADD COLUMN config_retest_timeout_seconds INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_use_cooldown') THEN
        ALTER TABLE trades ADD COLUMN config_use_cooldown BOOLEAN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_cooldown_seconds') THEN
        ALTER TABLE trades ADD COLUMN config_cooldown_seconds INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_cooldown_same_symbol') THEN
        ALTER TABLE trades ADD COLUMN config_cooldown_same_symbol INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_use_candle_close') THEN
        ALTER TABLE trades ADD COLUMN config_use_candle_close BOOLEAN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_candle_close_threshold_seconds') THEN
        ALTER TABLE trades ADD COLUMN config_candle_close_threshold_seconds INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_use_momentum_continuity') THEN
        ALTER TABLE trades ADD COLUMN config_use_momentum_continuity BOOLEAN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'trades' AND column_name = 'config_momentum_lookback') THEN
        ALTER TABLE trades ADD COLUMN config_momentum_lookback INTEGER;
    END IF;
    
    RAISE NOTICE '✅ Colonnes config_* ajoutées à trades';
END $$;

-- Commentaires pour trades
COMMENT ON COLUMN trades.config_min_score_required IS 'Score minimum requis (extrait de config_snapshot)';
COMMENT ON COLUMN trades.config_snr_threshold IS 'Seuil SNR (extrait de config_snapshot)';
COMMENT ON COLUMN trades.config_optimal_atr_min_1m IS 'ATR min 1m (extrait de config_snapshot)';
COMMENT ON COLUMN trades.config_optimal_atr_max_1m IS 'ATR max 1m (extrait de config_snapshot)';
COMMENT ON COLUMN trades.config_optimal_atr_min_5m IS 'ATR min 5m (extrait de config_snapshot)';
COMMENT ON COLUMN trades.config_optimal_atr_max_5m IS 'ATR max 5m (extrait de config_snapshot)';
COMMENT ON COLUMN trades.config_volume_multiplier IS 'Multiplicateur volume (extrait de config_snapshot)';
COMMENT ON COLUMN trades.config_use_confluence IS 'Mode confluence activé (extrait de config_snapshot)';
COMMENT ON COLUMN trades.config_use_anti_whipsaw IS 'Filtre anti-whipsaw activé (extrait de config_snapshot)';
COMMENT ON COLUMN trades.config_whipsaw_lookback IS 'Lookback whipsaw (extrait de config_snapshot)';
COMMENT ON COLUMN trades.config_whipsaw_threshold_pct IS 'Seuil whipsaw % (extrait de config_snapshot)';
COMMENT ON COLUMN trades.config_whipsaw_max_alternations IS 'Max alternances whipsaw (extrait de config_snapshot)';
COMMENT ON COLUMN trades.config_use_retest_confirmation IS 'Retest breakout activé (extrait de config_snapshot)';
COMMENT ON COLUMN trades.config_retest_tolerance_pct IS 'Tolérance retest % (extrait de config_snapshot)';
COMMENT ON COLUMN trades.config_retest_timeout_seconds IS 'Timeout retest (extrait de config_snapshot)';
COMMENT ON COLUMN trades.config_use_cooldown IS 'Cooldown activé (extrait de config_snapshot)';
COMMENT ON COLUMN trades.config_cooldown_seconds IS 'Cooldown global (extrait de config_snapshot)';
COMMENT ON COLUMN trades.config_cooldown_same_symbol IS 'Cooldown même symbole (extrait de config_snapshot)';
COMMENT ON COLUMN trades.config_use_candle_close IS 'Confirmation fermeture bougie (extrait de config_snapshot)';
COMMENT ON COLUMN trades.config_candle_close_threshold_seconds IS 'Seuil fermeture bougie (extrait de config_snapshot)';
COMMENT ON COLUMN trades.config_use_momentum_continuity IS 'Filtre momentum activé (extrait de config_snapshot)';
COMMENT ON COLUMN trades.config_momentum_lookback IS 'Lookback momentum (extrait de config_snapshot)';

-- ============================================================================
-- Backfill depuis params_snapshot (scan_logs)
-- ============================================================================

-- Extraire valeurs depuis params_snapshot JSONB et remplir colonnes individuelles
UPDATE scan_logs
SET 
    config_min_score_required = (params_snapshot->>'min_score_required')::FLOAT,
    config_snr_threshold = (params_snapshot->>'snr_threshold')::FLOAT,
    config_atr_min_1m = (params_snapshot->'optimal_atr'->'1m'->>'min')::FLOAT,
    config_atr_max_1m = (params_snapshot->'optimal_atr'->'1m'->>'max')::FLOAT,
    config_atr_min_5m = (params_snapshot->'optimal_atr'->'5m'->>'min')::FLOAT,
    config_atr_max_5m = (params_snapshot->'optimal_atr'->'5m'->>'max')::FLOAT,
    config_volume_multiplier = (params_snapshot->>'volume_multiplier')::FLOAT,
    config_use_confluence = (params_snapshot->>'use_confluence')::BOOLEAN,
    config_use_anti_whipsaw = (params_snapshot->>'use_anti_whipsaw')::BOOLEAN,
    config_whipsaw_lookback = (params_snapshot->>'whipsaw_lookback')::INTEGER,
    config_whipsaw_threshold_pct = (params_snapshot->>'whipsaw_threshold_pct')::FLOAT,
    config_whipsaw_max_alternations = (params_snapshot->>'whipsaw_max_alternations')::INTEGER,
    config_use_retest_confirmation = (params_snapshot->>'use_retest_confirmation')::BOOLEAN,
    config_retest_tolerance_pct = (params_snapshot->>'retest_tolerance_pct')::FLOAT,
    config_retest_timeout_seconds = (params_snapshot->>'retest_timeout_seconds')::INTEGER,
    config_use_cooldown = (params_snapshot->>'use_cooldown')::BOOLEAN,
    config_cooldown_seconds = (params_snapshot->>'cooldown_seconds')::INTEGER,
    config_cooldown_same_symbol = (params_snapshot->>'cooldown_same_symbol')::INTEGER,
    config_use_candle_close = (params_snapshot->>'use_candle_close')::BOOLEAN,
    config_candle_close_threshold_seconds = (params_snapshot->>'candle_close_threshold_seconds')::INTEGER,
    config_use_momentum_continuity = (params_snapshot->>'use_momentum_continuity')::BOOLEAN,
    config_momentum_lookback = (params_snapshot->>'momentum_lookback')::INTEGER
WHERE params_snapshot IS NOT NULL
  AND config_min_score_required IS NULL;

-- ============================================================================
-- Backfill depuis config_snapshot (trades)
-- ============================================================================

-- Extraire valeurs depuis config_snapshot JSONB et remplir colonnes individuelles
UPDATE trades
SET 
    config_min_score_required = (config_snapshot->>'min_score_required')::FLOAT,
    config_snr_threshold = (config_snapshot->>'snr_threshold')::FLOAT,
    config_optimal_atr_min_1m = (config_snapshot->'optimal_atr'->'1m'->>'min')::FLOAT,
    config_optimal_atr_max_1m = (config_snapshot->'optimal_atr'->'1m'->>'max')::FLOAT,
    config_optimal_atr_min_5m = (config_snapshot->'optimal_atr'->'5m'->>'min')::FLOAT,
    config_optimal_atr_max_5m = (config_snapshot->'optimal_atr'->'5m'->>'max')::FLOAT,
    config_volume_multiplier = (config_snapshot->>'volume_multiplier')::FLOAT,
    config_use_confluence = (config_snapshot->>'use_confluence')::BOOLEAN,
    config_use_anti_whipsaw = (config_snapshot->>'use_anti_whipsaw')::BOOLEAN,
    config_whipsaw_lookback = (config_snapshot->>'whipsaw_lookback')::INTEGER,
    config_whipsaw_threshold_pct = (config_snapshot->>'whipsaw_threshold_pct')::FLOAT,
    config_whipsaw_max_alternations = (config_snapshot->>'whipsaw_max_alternations')::INTEGER,
    config_use_retest_confirmation = (config_snapshot->>'use_retest_confirmation')::BOOLEAN,
    config_retest_tolerance_pct = (config_snapshot->>'retest_tolerance_pct')::FLOAT,
    config_retest_timeout_seconds = (config_snapshot->>'retest_timeout_seconds')::INTEGER,
    config_use_cooldown = (config_snapshot->>'use_cooldown')::BOOLEAN,
    config_cooldown_seconds = (config_snapshot->>'cooldown_seconds')::INTEGER,
    config_cooldown_same_symbol = (config_snapshot->>'cooldown_same_symbol')::INTEGER,
    config_use_candle_close = (config_snapshot->>'use_candle_close')::BOOLEAN,
    config_candle_close_threshold_seconds = (config_snapshot->>'candle_close_threshold_seconds')::INTEGER,
    config_use_momentum_continuity = (config_snapshot->>'use_momentum_continuity')::BOOLEAN,
    config_momentum_lookback = (config_snapshot->>'momentum_lookback')::INTEGER
WHERE config_snapshot IS NOT NULL
  AND config_min_score_required IS NULL;

-- ============================================================================
-- Index pour performance (optionnel)
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_scan_config_score ON scan_logs(config_min_score_required) 
    WHERE config_min_score_required IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_trade_config_score ON trades(config_min_score_required) 
    WHERE config_min_score_required IS NOT NULL;

-- ============================================================================
-- VÉRIFICATION
-- ============================================================================

DO $$
DECLARE
    scan_logs_count INTEGER;
    trades_count INTEGER;
    scan_logs_filled INTEGER;
    trades_filled INTEGER;
BEGIN
    -- Compter colonnes scan_logs
    SELECT COUNT(*) INTO scan_logs_count
    FROM information_schema.columns 
    WHERE table_name = 'scan_logs' 
      AND column_name LIKE 'config_%';
    
    -- Compter colonnes trades
    SELECT COUNT(*) INTO trades_count
    FROM information_schema.columns 
    WHERE table_name = 'trades' 
      AND column_name LIKE 'config_%';
    
    -- Compter lignes remplies scan_logs
    SELECT COUNT(*) INTO scan_logs_filled
    FROM scan_logs
    WHERE config_min_score_required IS NOT NULL;
    
    -- Compter lignes remplies trades
    SELECT COUNT(*) INTO trades_filled
    FROM trades
    WHERE config_min_score_required IS NOT NULL;
    
    RAISE NOTICE '================================================';
    RAISE NOTICE '✅ Migration terminée';
    RAISE NOTICE '================================================';
    RAISE NOTICE 'scan_logs: % colonnes config_* ajoutées', scan_logs_count;
    RAISE NOTICE 'trades: % colonnes config_* ajoutées', trades_count;
    RAISE NOTICE 'scan_logs: % lignes backfillées', scan_logs_filled;
    RAISE NOTICE 'trades: % lignes backfillées', trades_filled;
    RAISE NOTICE '================================================';
    
    -- Vérifier colonnes critiques
    IF scan_logs_count < 8 THEN
        RAISE WARNING 'Attention: Seulement % colonnes config_* dans scan_logs (attendu: 8)', scan_logs_count;
    END IF;
    
    IF trades_count < 8 THEN
        RAISE WARNING 'Attention: Seulement % colonnes config_* dans trades (attendu: 8)', trades_count;
    END IF;
END $$;

-- Afficher structure finale
SELECT 
    'scan_logs' AS table_name,
    column_name, 
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'scan_logs'
  AND column_name LIKE 'config_%'
ORDER BY column_name;

SELECT 
    'trades' AS table_name,
    column_name, 
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'trades'
  AND column_name LIKE 'config_%'
ORDER BY column_name;
