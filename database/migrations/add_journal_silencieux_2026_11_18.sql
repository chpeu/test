-- Colonnes que le robot écrit et que la base ne connaissait pas — 18/11/2026 soir
--
-- Pourquoi : le robot fermait des trades, le journal affichait « 🔴 POSITION
-- FERMÉE: XPL/USDT:USDT | Raison: SL | PnL net: -0.34 % », et la table `trades`
-- restait vide. La requête d'écriture échouait sur une colonne inconnue :
--
--   ERROR: column "adaptive_sizing_multiplier" of relation "trades" does not exist
--   ERROR: column "trailing_mfe_triggered" of relation "trade_atr_metrics" does not exist
--
-- Conséquence visible : l'écran Historique, la carte Corrélations et le bilan de
-- l'IA locale disaient tous « 0 trade fermé », alors que le robot en avait fermé.
--
-- Règles de ce fichier : que des ajouts (`ADD COLUMN IF NOT EXISTS`, index
-- `IF NOT EXISTS`). Rien n'est supprimé, aucune colonne existante n'est modifiée.
-- À appliquer APRÈS les fichiers déjà prévus par le dépôt :
--   migration_add_config_columns.sql
--   migrations/add_rsi_final_filter_columns.sql
--   migrations/add_stagnation_positive_exit.sql
--   migrations/add_antigiveback_trailing_mfe_columns.sql
--   migrations/add_invert_signals_column.sql
--   migrations/add_pair_scorer.sql
--
-- Contrôlé le 18/11/2026 : après application, écriture d'un trade factice par le
-- vrai chemin du code (log_trade), relecture, puis effacement : 0 erreur.

-- ---------------------------------------------------------------------------
-- trades : ce que `log_trade` écrit et qu'aucune migration du dépôt ne prévoyait
-- ---------------------------------------------------------------------------
ALTER TABLE trades ADD COLUMN IF NOT EXISTS adaptive_sizing_multiplier DOUBLE PRECISION;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS config_use_micro_confirmation BOOLEAN;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS config_micro_confirmation_delay_ms INTEGER;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_volume_multiplier DOUBLE PRECISION;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_rsi_filter_mode TEXT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_position_timeout DOUBLE PRECISION;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_optimal_atr_max_1m DOUBLE PRECISION;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_sl_exchange_percent DOUBLE PRECISION;

-- ---------------------------------------------------------------------------
-- trade_atr_metrics : pareil, du côté des métriques ATR de chaque trade
-- (le fichier add_antigiveback_trailing_mfe_columns.sql n'ajoutait ces colonnes
-- que pour `trades`, jamais pour `trade_atr_metrics`)
-- ---------------------------------------------------------------------------
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS trailing_mfe_triggered BOOLEAN;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS param_stagnation_positive_enabled BOOLEAN;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS param_trailing_mfe_enabled BOOLEAN;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS param_stagnation_mfe_tracking BOOLEAN;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS stagnation_positive_triggered BOOLEAN;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS sl_mexc_touched BOOLEAN;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS is_weekend BOOLEAN;

ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS param_stagnation_positive_threshold DOUBLE PRECISION;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS param_stagnation_positive_timeout DOUBLE PRECISION;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS param_trailing_mfe_trigger_pct DOUBLE PRECISION;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS param_stagnation_mfe_pullback_pct DOUBLE PRECISION;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS stagnation_mfe_at_exit DOUBLE PRECISION;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS stagnation_pullback_at_exit DOUBLE PRECISION;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS sl_mexc_price DOUBLE PRECISION;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS sl_mexc_pct DOUBLE PRECISION;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS sl_mexc_margin_used DOUBLE PRECISION;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS regime_confidence DOUBLE PRECISION;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS session_atr_multiplier DOUBLE PRECISION;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS regime_stability_minutes DOUBLE PRECISION;

ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS hour_utc INTEGER;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS day_of_week INTEGER;

ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS session_market TEXT;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS regime_detection_method TEXT;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS sl_mexc_touched_at TIMESTAMPTZ;

-- `log_trade_atr_metrics` termine par « ON CONFLICT (trade_id) DO UPDATE », ce
-- qui exige une contrainte d'unicité : il n'y avait qu'un index simple.
-- (Table vide au moment de l'application : aucun doublon possible.)
CREATE UNIQUE INDEX IF NOT EXISTS idx_atr_metrics_trade_unique ON trade_atr_metrics (trade_id);
