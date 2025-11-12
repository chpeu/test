# 📊 Schéma PostgreSQL Complet - Récapitulatif

**Date :** 2025-11-12  
**Version :** 7.0  
**Base de données :** `trade_cursor_ml`

---

## 📋 Tables (9 tables)

### 1. `trading_sessions`
**Description :** Sessions de trading pour analyse par période

**Colonnes (13) :**
- `id` (UUID, PK)
- `start_time` (TIMESTAMPTZ)
- `end_time` (TIMESTAMPTZ)
- `total_scans` (INTEGER)
- `opportunities_detected` (INTEGER)
- `trades_executed` (INTEGER)
- `wins` (INTEGER)
- `losses` (INTEGER)
- `total_pnl_usdt` (FLOAT)
- `total_pnl_pct` (FLOAT)
- `config_snapshot` (JSONB)
- `notes` (TEXT)
- `created_at` (TIMESTAMPTZ)

**Index :** 2
- `idx_sessions_start_time`
- `idx_sessions_end_time`

---

### 2. `config_snapshots`
**Description :** Historique des changements de configuration

**Colonnes (6) :**
- `id` (BIGSERIAL, PK)
- `timestamp` (TIMESTAMPTZ)
- `session_id` (UUID, FK → trading_sessions)
- `config_data` (JSONB) - **Toutes les variables de configuration**
- `changed_keys` (TEXT[])
- `changed_by` (VARCHAR(50))
- `notes` (TEXT)

**Index :** 2
- `idx_config_timestamp`
- `idx_config_session`

---

### 3. `scan_logs` (PARTITIONNÉE)
**Description :** Log de CHAQUE scan (opportunité ou non)

**Colonnes (95) :**

#### Métadonnées (4)
- `id` (BIGSERIAL)
- `timestamp` (TIMESTAMPTZ)
- `session_id` (UUID, FK)
- `symbol` (VARCHAR(30))
- `scan_duration_ms` (FLOAT)

#### Données marché (7)
- `price`, `spread_pct`, `book_depth`, `balance_score`
- `bid_vol`, `ask_vol`, `orderbook_imbalance_ratio`

#### Indicateurs 1m (24)
- **EMA (3)** : `ema9_1m`, `ema21_1m`, `ema_diff_pct_1m`
- **RSI (2)** : `rsi_1m`, `rsi_prev_1m`
- **MACD (4)** : `macd_1m`, `macd_signal_1m`, `macd_hist_1m`, `macd_hist_prev_1m`
- **ADX (4)** : `adx_1m`, `di_plus_1m`, `di_minus_1m`, `di_gap_1m`
- **ATR (2)** : `atr_1m`, `atr_pct_1m`
- **Bollinger (6)** : `bb_upper_1m`, `bb_middle_1m`, `bb_lower_1m`, `bb_width_1m`, `bb_distance_to_lower_1m`, `bb_distance_to_upper_1m`
- **Volume (4)** : `volume_1m`, `volume_avg_1m`, `volume_ratio_1m`, `volume_spike_1m`

#### Indicateurs 5m (24)
- Même structure que 1m (EMA, RSI, MACD, ADX, ATR, Bollinger, Volume)

#### Filtres de Qualité (12)
- **SNR (4)** : `snr_1m`, `snr_5m`, `snr_passed_1m`, `snr_passed_5m`
- **Breakout (4)** : `breakout_distance_1m`, `breakout_distance_5m`, `breakout_passed_1m`, `breakout_passed_5m`
- **Wick (4)** : `wick_ratio_1m`, `wick_ratio_5m`, `wick_passed_1m`, `wick_passed_5m`
- **ATR Optimal (2)** : `atr_optimal_passed_1m`, `atr_optimal_passed_5m`
- **Volume Filter (2)** : `volume_filter_passed_1m`, `volume_filter_passed_5m`

#### Confluence (8)
- `use_confluence`, `confluence_met`
- `score_1m`, `score_5m`, `score_total`
- `score_long_1m`, `score_short_1m`, `score_long_5m`, `score_short_5m`
- `timeframes_aligned`

#### Patterns (4)
- `pattern_1m`, `pattern_multi_1m`, `pattern_5m`, `pattern_multi_5m`

#### Trend (4)
- `trend_timeframe`, `trend_direction`, `trend_strength`, `trend_bonus`

#### Divergence (3)
- `divergence_detected`, `divergence_type`, `divergence_bonus`

#### Décision ML (4)
- `is_opportunity`, `opportunity_direction`, `reject_reason`, `reject_reason_category`

#### Paramètres (1)
- `params_snapshot` (JSONB)

**Partitions :** Par mois (2025-11, 2025-12, 2026-01)

**Index :** 9

---

### 4. `opportunities`
**Description :** Log des opportunités détectées (subset de scan_logs)

**Colonnes (18) :**
- `id` (UUID, PK)
- `scan_log_id` (BIGINT)
- `session_id` (UUID, FK)
- `timestamp` (TIMESTAMPTZ)
- `symbol` (VARCHAR(30))
- `direction` (VARCHAR(10))
- `entry_suggested`, `tp_suggested`, `sl_suggested` (FLOAT)
- `tp_sl_mode` (VARCHAR(20))
- `setup_score` (FLOAT)
- `setup_reason` (TEXT)
- `conditions_matched` (TEXT[])
- `condition_count` (INTEGER)
- `score_long`, `score_short`, `score_min_required` (FLOAT)
- `trend_bonus`, `divergence_bonus` (FLOAT)
- `status` (VARCHAR(20))
- `ignored_reason` (TEXT)
- `executed_at`, `expired_at` (TIMESTAMPTZ)
- `created_at` (TIMESTAMPTZ)

**Index :** 7

---

### 5. `trades` ⭐ **TABLE PRINCIPALE POUR ML**
**Description :** Log des trades exécutés avec résultats complets

**Colonnes (109) :**

#### Base (6)
- `id` (UUID, PK)
- `opportunity_id` (UUID, FK)
- `scan_log_id` (BIGINT)
- `session_id` (UUID, FK)
- `symbol` (VARCHAR(30))
- `direction` (VARCHAR(10))

#### Entry (6)
- `timestamp_entry` (TIMESTAMPTZ)
- `entry_price`, `size_usdt`, `tp_price`, `sl_price` (FLOAT)
- `tp_sl_mode` (VARCHAR(20))

#### Indicateurs d'entrée (58)
- **RSI (4)** : `entry_rsi_1m`, `entry_rsi_5m`, `entry_rsi_prev_1m`, `entry_rsi_prev_5m`
- **MACD (8)** : `entry_macd_1m`, `entry_macd_signal_1m`, `entry_macd_hist_1m`, `entry_macd_hist_prev_1m` (1m et 5m)
- **ADX (8)** : `entry_adx_1m`, `entry_adx_5m`, `entry_di_plus_1m`, `entry_di_minus_1m`, `entry_di_gap_1m` (1m et 5m)
- **EMA (6)** : `entry_ema9_1m`, `entry_ema21_1m`, `entry_ema_diff_pct_1m` (1m et 5m)
- **ATR (4)** : `entry_atr_1m`, `entry_atr_pct_1m`, `entry_atr_5m`, `entry_atr_pct_5m`
- **Bollinger (12)** : `entry_bb_upper_1m`, `entry_bb_middle_1m`, `entry_bb_lower_1m`, `entry_bb_width_1m`, `entry_bb_distance_to_lower_1m`, `entry_bb_distance_to_upper_1m` (1m et 5m)
- **Volume (8)** : `entry_volume_1m`, `entry_volume_avg_1m`, `entry_volume_ratio_1m`, `entry_volume_spike_1m` (1m et 5m)
- **Score (3)** : `entry_score`, `entry_spread_pct`, `entry_balance_score`
- **Conditions (2)** : `entry_conditions` (TEXT[]), `entry_condition_count` (INTEGER)
- **Temporel (2)** : `entry_hour_of_day`, `entry_day_of_week`

#### Exit (3)
- `timestamp_exit` (TIMESTAMPTZ)
- `exit_price` (FLOAT)
- `exit_reason` (VARCHAR(30))

#### Indicateurs de sortie (12)
- **RSI (2)** : `exit_rsi_1m`, `exit_rsi_5m`
- **MACD (2)** : `exit_macd_hist_1m`, `exit_macd_hist_5m`
- **ADX (2)** : `exit_adx_1m`, `exit_adx_5m`
- **ATR (2)** : `exit_atr_pct_1m`, `exit_atr_pct_5m`
- **Score (5)** : `exit_score`, `exit_volume_ratio_1m`, `exit_volume_ratio_5m`, `exit_spread_pct`, `exit_balance_score`
- **Variation (1)** : `entry_to_exit_price_change_pct`
- **Temporel (2)** : `exit_hour_of_day`, `exit_day_of_week`

#### Résultats (9)
- `duration_seconds` (FLOAT)
- `pnl_pct`, `pnl_usdt`, `gross_pnl_usdt` (FLOAT)
- `slippage_pct`, `slippage_usdt` (FLOAT)
- `fees_usdt` (FLOAT)
- `net_pnl_usdt`, `net_pnl_pct` (FLOAT)
- `win` (BOOLEAN)

#### Events (9)
- `break_even_set`, `break_even_triggered_at`
- `partial_tp_executed`, `partial_tp_triggered_at`, `partial_tp_profit`, `partial_tp_percent`
- `tp_escalier_levels_executed`, `tp_escalier_profits`
- `trailing_stop_activated`, `trailing_stop_triggered_at`

#### Métriques position (4)
- `max_favorable_excursion`, `max_adverse_excursion` (FLOAT)
- `max_favorable_excursion_usdt`, `max_adverse_excursion_usdt` (FLOAT)

#### Métriques qualité (2)
- `risk_reward_ratio`, `profit_factor` (FLOAT)

#### Métriques performance (4)
- `entry_to_max_profit_price_change_pct`, `entry_to_max_loss_price_change_pct` (FLOAT)
- `max_drawdown_pct`, `max_drawdown_usdt` (FLOAT)

#### Scalability (4)
- `entry_book_depth`, `entry_bid_vol`, `entry_ask_vol`, `entry_orderbook_imbalance` (FLOAT)

#### Configuration (1)
- `config_snapshot` (JSONB) - **Toutes les variables de configuration**

#### Métadonnées (2)
- `created_at`, `updated_at` (TIMESTAMPTZ)

**Index :** 10

---

### 6. `market_context`
**Description :** Contexte marché général (snapshot périodique)

**Colonnes (15) :**
- `id` (BIGSERIAL, PK)
- `timestamp` (TIMESTAMPTZ)
- `session_id` (UUID, FK)
- `hour_of_day`, `day_of_week` (INTEGER)
- `btc_price`, `eth_price` (FLOAT)
- `total_opportunities_detected` (INTEGER)
- `avg_spread`, `avg_volatility_1m`, `avg_volatility_5m` (FLOAT)
- `active_positions_count` (INTEGER)
- `session_win_rate`, `session_pnl_usdt`, `session_pnl_pct` (FLOAT)
- `market_trend`, `market_volatility` (VARCHAR(10))
- `fear_greed_index` (FLOAT)
- `global_metrics`, `session_stats` (JSONB)

**Index :** 4

---

### 7. `scan_errors`
**Description :** Logs d'erreurs de scan

**Colonnes (8) :**
- `id` (BIGSERIAL, PK)
- `timestamp` (TIMESTAMPTZ)
- `session_id` (UUID, FK)
- `symbol` (VARCHAR(30))
- `error_type` (VARCHAR(50))
- `error_message`, `error_stack` (TEXT)
- `scan_context` (JSONB)
- `resolved`, `resolved_at`

**Index :** 3

---

### 8. `model_predictions`
**Description :** Prédictions ML (pour futur)

**Colonnes (12) :**
- `id` (BIGSERIAL, PK)
- `timestamp` (TIMESTAMPTZ)
- `scan_log_id` (BIGINT)
- `opportunity_id` (UUID, FK)
- `model_version` (VARCHAR(50))
- `predicted_win` (BOOLEAN)
- `win_probability`, `predicted_pnl_pct`, `confidence_score` (FLOAT)
- `features_used` (JSONB)
- `actual_win`, `actual_pnl_pct` (FLOAT/BOOLEAN)
- `prediction_correct` (BOOLEAN)
- `created_at` (TIMESTAMPTZ)

**Index :** 4

---

### 9. `features_engineered`
**Description :** Features pré-calculées pour ML avancé

**Colonnes (12) :**
- `id` (BIGSERIAL, PK)
- `scan_log_id` (BIGINT)
- `timestamp` (TIMESTAMPTZ)
- `rsi_macd_divergence` (BOOLEAN)
- `ema_cross_signal` (VARCHAR(10))
- `volume_atr_ratio` (FLOAT)
- `bb_squeeze` (BOOLEAN)
- `adx_trend_alignment` (BOOLEAN)
- `multi_timeframe_alignment` (BOOLEAN)
- `momentum_score`, `trend_score`, `volatility_score`, `liquidity_score` (FLOAT)
- `feature_version` (VARCHAR(20))

**Index :** 2

---

## 📊 Statistiques Globales

- **Total tables :** 9
- **Total colonnes :** ~280 colonnes
- **Total index :** ~40 index
- **Vues :** 4
- **Fonctions :** 4
- **Triggers :** 1

---

## 🔗 Relations

```
trading_sessions (1) ──┐
                       ├── (N) config_snapshots
                       ├── (N) scan_logs
                       ├── (N) opportunities
                       ├── (N) trades
                       ├── (N) market_context
                       └── (N) scan_errors

opportunities (1) ──┬── (N) trades
                    └── (N) model_predictions

scan_logs (1) ──┬── (1) opportunities
                └── (N) features_engineered
```

---

## 📝 Variables de Configuration Stockées

Toutes les variables de configuration sont stockées dans :
1. **`config_snapshots.config_data`** (JSONB) - Historique complet
2. **`scan_logs.params_snapshot`** (JSONB) - Snapshot au moment du scan
3. **`trades.config_snapshot`** (JSONB) - Snapshot au moment du trade

**Variables incluses :**
- Général (6)
- Validation & Scoring (7)
- Patterns Techniques (4)
- Patterns de Bougies (7)
- Seuils & Filtres (9)
- Money Management (4)
- TP/SL Configuration (5)
- Mode ATR (4)
- TP Escalier (9)
- Trailing Stop (5)
- Timeframe & Trend (1)
- Scanner (2)
- Configurations Avancées (8 objets JSON)
- RISK_CONFIG (9)
- CONDITION_WEIGHTS (8)
- TREND_BONUS_CONFIG (2)
- RETRY_CONFIG (4)
- CIRCUIT_BREAKER_CONFIG (2)
- WEBSOCKET_CONFIG (5)

**Total : ~100+ variables de configuration**

---

## ✅ Vérification de Cohérence

### Colonnes attendues dans `trades` (109 colonnes)

✅ Toutes les colonnes sont présentes dans le schéma SQL  
✅ Toutes les colonnes sont utilisées dans le code Python  
✅ Les types de données correspondent  
✅ Les index sont créés pour les requêtes fréquentes  

---

## 🎯 Utilisation pour ML

### Features principales (depuis `trades`)
- **Indicateurs d'entrée :** 58 colonnes
- **Indicateurs de sortie :** 12 colonnes
- **Métriques temporelles :** 4 colonnes
- **Métriques de performance :** 8 colonnes
- **Configuration :** 1 colonne JSONB (100+ variables)
- **Label :** `win` (BOOLEAN)

### Features additionnelles (depuis `scan_logs`)
- **Indicateurs techniques :** 48 colonnes (1m + 5m)
- **Filtres de qualité :** 12 colonnes
- **Scores :** 8 colonnes
- **Patterns :** 4 colonnes
- **Trend :** 4 colonnes
- **Divergence :** 3 colonnes

**Total features disponibles :** ~200+ features

---

## 📚 Vues Utiles

1. **`scans_with_opportunities`** - Scans avec opportunités
2. **`opportunities_executed`** - Opportunités exécutées
3. **`daily_stats`** - Stats quotidiennes
4. **`session_stats`** - Stats par session
5. **`ml_features`** - Features pour ML

---

## 🔧 Fonctions Utiles

1. **`cleanup_old_data()`** - Nettoyer vieilles données
2. **`get_global_stats()`** - Stats globales
3. **`create_monthly_partition()`** - Créer partition mensuelle
4. **`update_updated_at_column()`** - Mettre à jour updated_at

---

## ✅ Checklist de Validation

- [x] Schéma SQL complet
- [x] Migration pour nouvelles colonnes
- [x] Code Python mis à jour
- [x] Toutes les variables de configuration stockées
- [x] Tous les indicateurs d'entrée/sortie loggés
- [x] Métriques temporelles calculées
- [x] Métriques de performance calculées
- [x] Index créés pour performance
- [x] Vues créées pour requêtes fréquentes
- [x] Fonctions utilitaires créées

---

## 🚀 Prêt pour ML !

Le schéma est complet et prêt pour l'optimisation ML avec :
- ✅ ~200+ features disponibles
- ✅ Labels (win/loss)
- ✅ Configuration snapshot pour chaque trade
- ✅ Métriques de performance complètes
- ✅ Données temporelles pour analyse de patterns

