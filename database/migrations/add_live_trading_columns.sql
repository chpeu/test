-- 🔥 Migration: Ajouter colonnes LIVE TRADING à la table trades
-- Date: 2025-11-25
-- Description: Extension de la table trades pour stocker les données de trading live (DRY-RUN et LIVE RÉEL)

-- ==================== MODE & TYPE ====================
ALTER TABLE trades ADD COLUMN IF NOT EXISTS is_live_trade BOOLEAN DEFAULT FALSE;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS is_dry_run BOOLEAN DEFAULT TRUE;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS live_execution_mode TEXT;

-- ==================== ORDRE D'ENTRÉE ====================
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_order_id TEXT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_order_type TEXT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_requested_price NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_fill_price NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_slippage_pct NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_latency_ms INTEGER;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_timestamp_live TIMESTAMPTZ;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_api_response JSONB;

-- ==================== ORDRE DE SORTIE ====================
ALTER TABLE trades ADD COLUMN IF NOT EXISTS exit_order_id TEXT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS exit_order_type TEXT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS exit_requested_price NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS exit_fill_price NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS exit_slippage_pct NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS exit_latency_ms INTEGER;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS exit_timestamp_live TIMESTAMPTZ;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS exit_api_response JSONB;

-- ==================== FUTURES / LEVIER ====================
ALTER TABLE trades ADD COLUMN IF NOT EXISTS leverage_used INTEGER DEFAULT 1;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS margin_mode TEXT DEFAULT 'isolated';
ALTER TABLE trades ADD COLUMN IF NOT EXISTS position_size_contracts NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS liquidation_price NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS margin_used NUMERIC;

-- ==================== FRAIS DÉTAILLÉS ====================
ALTER TABLE trades ADD COLUMN IF NOT EXISTS maker_fee_rate NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS taker_fee_rate NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_fee_usdt NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS exit_fee_usdt NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS total_fees_usdt NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS funding_rate_at_entry NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS funding_rate_at_exit NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS funding_paid_usdt NUMERIC;

-- ==================== PERFORMANCE TEMPS RÉEL ====================
ALTER TABLE trades ADD COLUMN IF NOT EXISTS time_to_fill_entry_ms INTEGER;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS time_to_fill_exit_ms INTEGER;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS price_at_signal NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS price_at_order_sent NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS signal_to_fill_slippage_pct NUMERIC;

-- ==================== API & RÉSEAU ====================
ALTER TABLE trades ADD COLUMN IF NOT EXISTS api_errors JSONB;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS exchange_latency_ms INTEGER;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS ws_latency_ms INTEGER;

-- ==================== CONTEXTE MARCHÉ À L'ENTRÉE ====================
ALTER TABLE trades ADD COLUMN IF NOT EXISTS market_volatility_entry NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS spread_at_entry_pct NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS volume_24h_at_entry NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS orderbook_imbalance_entry NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS atr_at_entry NUMERIC;

-- ==================== CONTEXTE MARCHÉ À LA SORTIE ====================
ALTER TABLE trades ADD COLUMN IF NOT EXISTS market_volatility_exit NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS spread_at_exit_pct NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS volume_24h_at_exit NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS orderbook_imbalance_exit NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS atr_at_exit NUMERIC;

-- ==================== INDICATEURS TECHNIQUES ENTRÉE ====================
ALTER TABLE trades ADD COLUMN IF NOT EXISTS rsi_at_entry NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS macd_at_entry NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS bb_position_entry NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS adx_at_entry NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS di_plus_entry NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS di_minus_entry NUMERIC;

-- ==================== INDICATEURS TECHNIQUES SORTIE ====================
ALTER TABLE trades ADD COLUMN IF NOT EXISTS rsi_at_exit NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS macd_at_exit NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS bb_position_exit NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS adx_at_exit NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS di_plus_exit NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS di_minus_exit NUMERIC;

-- ==================== SCORE & ML ====================
ALTER TABLE trades ADD COLUMN IF NOT EXISTS setup_score NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS ml_confidence NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS ml_prediction TEXT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS ml_features JSONB;

-- ==================== ANALYSE POST-TRADE ====================
ALTER TABLE trades ADD COLUMN IF NOT EXISTS optimal_exit_price NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS optimal_exit_time TIMESTAMPTZ;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS missed_profit_pct NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS risk_reward_actual NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS risk_reward_planned NUMERIC;

-- ==================== NOTES & TAGS ====================
ALTER TABLE trades ADD COLUMN IF NOT EXISTS trade_notes TEXT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS trade_tags JSONB;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS user_rating INTEGER;

-- ==================== INDEX POUR LIVE TRADING ====================
CREATE INDEX IF NOT EXISTS idx_trades_is_live ON trades(is_live_trade);
CREATE INDEX IF NOT EXISTS idx_trades_is_dry_run ON trades(is_dry_run);
CREATE INDEX IF NOT EXISTS idx_trades_leverage ON trades(leverage_used);
CREATE INDEX IF NOT EXISTS idx_trades_entry_order ON trades(entry_order_id);
CREATE INDEX IF NOT EXISTS idx_trades_exit_order ON trades(exit_order_id);
CREATE INDEX IF NOT EXISTS idx_trades_margin_mode ON trades(margin_mode);

-- ==================== COMMENTAIRES ====================
COMMENT ON COLUMN trades.is_live_trade IS 'True si trade exécuté via API exchange (pas paper trading)';
COMMENT ON COLUMN trades.is_dry_run IS 'True si mode DRY-RUN (simulé), False si LIVE RÉEL';
COMMENT ON COLUMN trades.leverage_used IS 'Levier utilisé pour le trade futures (1-125x)';
COMMENT ON COLUMN trades.margin_mode IS 'Mode de marge: isolated ou cross';
COMMENT ON COLUMN trades.liquidation_price IS 'Prix de liquidation calculé';
COMMENT ON COLUMN trades.entry_latency_ms IS 'Latence API pour ordre entrée en ms';
COMMENT ON COLUMN trades.exit_latency_ms IS 'Latence API pour ordre sortie en ms';
COMMENT ON COLUMN trades.signal_to_fill_slippage_pct IS 'Slippage entre signal et fill réel en %';
COMMENT ON COLUMN trades.funding_paid_usdt IS 'Frais de funding payés en USDT';
COMMENT ON COLUMN trades.setup_score IS 'Score du setup ayant généré le trade';
COMMENT ON COLUMN trades.ml_confidence IS 'Confiance du modèle ML pour ce trade';
COMMENT ON COLUMN trades.risk_reward_actual IS 'Ratio risk/reward réel (calculé après fermeture)';
COMMENT ON COLUMN trades.risk_reward_planned IS 'Ratio risk/reward planifié (avant ouverture)';
COMMENT ON COLUMN trades.user_rating IS 'Note utilisateur pour ce trade (1-5)';

-- ==================== FIN MIGRATION ====================
-- Pour exécuter: psql -U votre_user -d votre_db -f add_live_trading_columns.sql
