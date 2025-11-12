# 📋 Liste Complète des Variables du Schéma PostgreSQL

**Date :** 2025-11-12  
**Base de données :** `trade_cursor_ml`

---

## 📊 TABLE 1 : `trading_sessions`

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | UUID | Identifiant unique de la session |
| `start_time` | TIMESTAMPTZ | Heure de début de la session |
| `end_time` | TIMESTAMPTZ | Heure de fin de la session (NULL si en cours) |
| `total_scans` | INTEGER | Nombre total de scans effectués |
| `opportunities_detected` | INTEGER | Nombre d'opportunités détectées |
| `trades_executed` | INTEGER | Nombre de trades exécutés |
| `wins` | INTEGER | Nombre de trades gagnants |
| `losses` | INTEGER | Nombre de trades perdants |
| `total_pnl_usdt` | FLOAT | PnL total en USDT |
| `total_pnl_pct` | FLOAT | PnL total en pourcentage |
| `config_snapshot` | JSONB | Snapshot de la configuration au démarrage |
| `notes` | TEXT | Notes additionnelles |
| `created_at` | TIMESTAMPTZ | Date de création |

**Total : 12 colonnes**

---

## 📊 TABLE 2 : `config_snapshots`

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | BIGSERIAL | Identifiant auto-incrémenté |
| `timestamp` | TIMESTAMPTZ | Date/heure du snapshot |
| `session_id` | UUID | Référence à trading_sessions |
| `config_data` | JSONB | Configuration complète |
| `changed_keys` | TEXT[] | Liste des clés modifiées |
| `changed_by` | VARCHAR(50) | 'system', 'user', 'auto' |
| `notes` | TEXT | Notes additionnelles |

**Total : 7 colonnes**

---

## 📊 TABLE 3 : `scan_logs` (PARTITIONNÉE)

### Métadonnées
| Colonne | Type | Description |
|---------|------|-------------|
| `id` | BIGSERIAL | Identifiant du scan |
| `timestamp` | TIMESTAMPTZ | Date/heure du scan |
| `session_id` | UUID | Référence à trading_sessions |
| `symbol` | VARCHAR(30) | Symbole de la paire (ex: BTCUSDT) |
| `scan_duration_ms` | FLOAT | Durée du scan en millisecondes |

### Données marché
| Colonne | Type | Description |
|---------|------|-------------|
| `price` | FLOAT | Prix actuel |
| `spread_pct` | FLOAT | Spread en pourcentage |
| `book_depth` | FLOAT | Profondeur du carnet d'ordres |
| `balance_score` | FLOAT | Score de balance |
| `bid_vol` | FLOAT | Volume des ordres d'achat |
| `ask_vol` | FLOAT | Volume des ordres de vente |
| `orderbook_imbalance_ratio` | FLOAT | Ratio bid_vol / ask_vol |

### Indicateurs 1m
| Colonne | Type | Description |
|---------|------|-------------|
| `ema9_1m` | FLOAT | EMA 9 périodes |
| `ema21_1m` | FLOAT | EMA 21 périodes |
| `ema_diff_pct_1m` | FLOAT | (EMA9 - EMA21) / EMA21 * 100 |
| `rsi_1m` | FLOAT | RSI |
| `rsi_prev_1m` | FLOAT | RSI période précédente |
| `macd_1m` | FLOAT | MACD |
| `macd_signal_1m` | FLOAT | Signal MACD |
| `macd_hist_1m` | FLOAT | Histogramme MACD |
| `macd_hist_prev_1m` | FLOAT | Histogramme MACD période précédente |
| `adx_1m` | FLOAT | ADX |
| `di_plus_1m` | FLOAT | DI+ |
| `di_minus_1m` | FLOAT | DI- |
| `di_gap_1m` | FLOAT | DI+ - DI- |
| `atr_1m` | FLOAT | ATR |
| `atr_pct_1m` | FLOAT | ATR en pourcentage |
| `bb_upper_1m` | FLOAT | Bollinger Bands - Bande supérieure |
| `bb_middle_1m` | FLOAT | Bollinger Bands - Bande médiane |
| `bb_lower_1m` | FLOAT | Bollinger Bands - Bande inférieure |
| `bb_width_1m` | FLOAT | Largeur des Bollinger Bands |
| `bb_distance_to_lower_1m` | FLOAT | Distance à la bande inférieure (%) |
| `bb_distance_to_upper_1m` | FLOAT | Distance à la bande supérieure (%) |
| `volume_1m` | FLOAT | Volume |
| `volume_avg_1m` | FLOAT | Volume moyen |
| `volume_ratio_1m` | FLOAT | volume / volume_avg |
| `volume_spike_1m` | FLOAT | Pic de volume |

### Indicateurs 5m
| Colonne | Type | Description |
|---------|------|-------------|
| `ema9_5m` | FLOAT | EMA 9 périodes |
| `ema21_5m` | FLOAT | EMA 21 périodes |
| `ema_diff_pct_5m` | FLOAT | (EMA9 - EMA21) / EMA21 * 100 |
| `rsi_5m` | FLOAT | RSI |
| `rsi_prev_5m` | FLOAT | RSI période précédente |
| `macd_5m` | FLOAT | MACD |
| `macd_signal_5m` | FLOAT | Signal MACD |
| `macd_hist_5m` | FLOAT | Histogramme MACD |
| `macd_hist_prev_5m` | FLOAT | Histogramme MACD période précédente |
| `adx_5m` | FLOAT | ADX |
| `di_plus_5m` | FLOAT | DI+ |
| `di_minus_5m` | FLOAT | DI- |
| `di_gap_5m` | FLOAT | DI+ - DI- |
| `atr_5m` | FLOAT | ATR |
| `atr_pct_5m` | FLOAT | ATR en pourcentage |
| `bb_upper_5m` | FLOAT | Bollinger Bands - Bande supérieure |
| `bb_middle_5m` | FLOAT | Bollinger Bands - Bande médiane |
| `bb_lower_5m` | FLOAT | Bollinger Bands - Bande inférieure |
| `bb_width_5m` | FLOAT | Largeur des Bollinger Bands |
| `bb_distance_to_lower_5m` | FLOAT | Distance à la bande inférieure (%) |
| `bb_distance_to_upper_5m` | FLOAT | Distance à la bande supérieure (%) |
| `volume_5m` | FLOAT | Volume |
| `volume_avg_5m` | FLOAT | Volume moyen |
| `volume_ratio_5m` | FLOAT | volume / volume_avg |
| `volume_spike_5m` | FLOAT | Pic de volume |

### Filtres de Qualité
| Colonne | Type | Description |
|---------|------|-------------|
| `snr_1m` | FLOAT | Signal-to-Noise Ratio (abs(price - EMA21) / ATR) |
| `snr_5m` | FLOAT | Signal-to-Noise Ratio 5m |
| `snr_passed_1m` | BOOLEAN | SNR passé 1m |
| `snr_passed_5m` | BOOLEAN | SNR passé 5m |
| `breakout_distance_1m` | FLOAT | Distance à EMA21 en ATR |
| `breakout_distance_5m` | FLOAT | Distance à EMA21 en ATR 5m |
| `breakout_passed_1m` | BOOLEAN | Breakout passé 1m |
| `breakout_passed_5m` | BOOLEAN | Breakout passé 5m |
| `wick_ratio_1m` | FLOAT | (high - low) / body |
| `wick_ratio_5m` | FLOAT | (high - low) / body 5m |
| `wick_passed_1m` | BOOLEAN | Wick ratio passé 1m |
| `wick_passed_5m` | BOOLEAN | Wick ratio passé 5m |
| `atr_optimal_passed_1m` | BOOLEAN | ATR optimal passé 1m |
| `atr_optimal_passed_5m` | BOOLEAN | ATR optimal passé 5m |
| `volume_filter_passed_1m` | BOOLEAN | Filtre volume passé 1m |
| `volume_filter_passed_5m` | BOOLEAN | Filtre volume passé 5m |

### Confluence
| Colonne | Type | Description |
|---------|------|-------------|
| `use_confluence` | BOOLEAN | Utilisation de la confluence |
| `confluence_met` | BOOLEAN | Confluence atteinte |
| `score_1m` | FLOAT | Score 1m |
| `score_5m` | FLOAT | Score 5m |
| `score_total` | FLOAT | Score total |
| `score_long_1m` | FLOAT | Score long 1m |
| `score_short_1m` | FLOAT | Score short 1m |
| `score_long_5m` | FLOAT | Score long 5m |
| `score_short_5m` | FLOAT | Score short 5m |
| `timeframes_aligned` | BOOLEAN | Timeframes alignés |

### Patterns
| Colonne | Type | Description |
|---------|------|-------------|
| `pattern_1m` | VARCHAR(50) | Pattern détecté 1m |
| `pattern_multi_1m` | VARCHAR(50) | Pattern multi 1m |
| `pattern_5m` | VARCHAR(50) | Pattern détecté 5m |
| `pattern_multi_5m` | VARCHAR(50) | Pattern multi 5m |

### Trend
| Colonne | Type | Description |
|---------|------|-------------|
| `trend_timeframe` | VARCHAR(10) | Timeframe du trend (défaut: '15m') |
| `trend_direction` | VARCHAR(10) | BULLISH, BEARISH, NEUTRAL |
| `trend_strength` | FLOAT | Force du trend |
| `trend_bonus` | FLOAT | Bonus trend |

### Divergence
| Colonne | Type | Description |
|---------|------|-------------|
| `divergence_detected` | BOOLEAN | Divergence détectée |
| `divergence_type` | VARCHAR(20) | 'BULLISH', 'BEARISH', null |
| `divergence_bonus` | FLOAT | Bonus divergence |

### Décision ML
| Colonne | Type | Description |
|---------|------|-------------|
| `is_opportunity` | BOOLEAN | Est une opportunité |
| `opportunity_direction` | VARCHAR(10) | LONG, SHORT, null |
| `reject_reason` | TEXT | Raison du rejet |
| `reject_reason_category` | VARCHAR(50) | 'FILTER', 'SCORE', 'MARKET', 'OTHER' |

### Paramètres
| Colonne | Type | Description |
|---------|------|-------------|
| `params_snapshot` | JSONB | Snapshot des paramètres |

**Total : 95 colonnes**

---

## 📊 TABLE 4 : `opportunities`

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | UUID | Identifiant unique |
| `scan_log_id` | BIGINT | Référence à scan_logs |
| `session_id` | UUID | Référence à trading_sessions |
| `timestamp` | TIMESTAMPTZ | Date/heure |
| `symbol` | VARCHAR(30) | Symbole |
| `direction` | VARCHAR(10) | LONG, SHORT |
| `entry_suggested` | FLOAT | Prix d'entrée suggéré |
| `tp_suggested` | FLOAT | Take Profit suggéré |
| `sl_suggested` | FLOAT | Stop Loss suggéré |
| `tp_sl_mode` | VARCHAR(20) | FIXE, ATR, ESCALIER |
| `setup_score` | FLOAT | Score du setup |
| `setup_reason` | TEXT | Raison du setup |
| `conditions_matched` | TEXT[] | Conditions matchées ['EMAs', 'RSI', ...] |
| `condition_count` | INTEGER | Nombre de conditions |
| `score_long` | FLOAT | Score long |
| `score_short` | FLOAT | Score short |
| `score_min_required` | FLOAT | Score minimum requis |
| `trend_bonus` | FLOAT | Bonus trend |
| `divergence_bonus` | FLOAT | Bonus divergence |
| `status` | VARCHAR(20) | PENDING, EXECUTED, IGNORED, EXPIRED, REJECTED |
| `ignored_reason` | TEXT | Raison d'ignorer |
| `executed_at` | TIMESTAMPTZ | Date d'exécution |
| `expired_at` | TIMESTAMPTZ | Date d'expiration |
| `created_at` | TIMESTAMPTZ | Date de création |

**Total : 24 colonnes**

---

## 📊 TABLE 5 : `trades`

### Métadonnées
| Colonne | Type | Description |
|---------|------|-------------|
| `id` | UUID | Identifiant unique |
| `opportunity_id` | UUID | Référence à opportunities |
| `scan_log_id` | BIGINT | Référence à scan_logs |
| `session_id` | UUID | Référence à trading_sessions |
| `symbol` | VARCHAR(30) | Symbole |
| `direction` | VARCHAR(10) | LONG, SHORT |

### Entry
| Colonne | Type | Description |
|---------|------|-------------|
| `timestamp_entry` | TIMESTAMPTZ | Date/heure d'entrée |
| `entry_price` | FLOAT | Prix d'entrée |
| `size_usdt` | FLOAT | Taille en USDT |
| `tp_price` | FLOAT | Take Profit |
| `sl_price` | FLOAT | Stop Loss |
| `tp_sl_mode` | VARCHAR(20) | FIXE, ATR, ESCALIER |

### Indicateurs d'entrée (pour ML)
| Colonne | Type | Description |
|---------|------|-------------|
| `entry_rsi_1m` | FLOAT | RSI 1m au moment de l'entrée |
| `entry_rsi_5m` | FLOAT | RSI 5m au moment de l'entrée |
| `entry_macd_hist_1m` | FLOAT | MACD Histogramme 1m |
| `entry_macd_hist_5m` | FLOAT | MACD Histogramme 5m |
| `entry_adx_1m` | FLOAT | ADX 1m |
| `entry_adx_5m` | FLOAT | ADX 5m |
| `entry_atr_pct_1m` | FLOAT | ATR % 1m |
| `entry_atr_pct_5m` | FLOAT | ATR % 5m |
| `entry_score` | FLOAT | Score au moment de l'entrée |
| `entry_volume_ratio_1m` | FLOAT | Ratio volume 1m |
| `entry_volume_ratio_5m` | FLOAT | Ratio volume 5m |
| `entry_spread_pct` | FLOAT | Spread % |
| `entry_balance_score` | FLOAT | Balance score |
| `entry_conditions` | TEXT[] | Conditions matchées |
| `entry_condition_count` | INTEGER | Nombre de conditions |

### Exit
| Colonne | Type | Description |
|---------|------|-------------|
| `timestamp_exit` | TIMESTAMPTZ | Date/heure de sortie |
| `exit_price` | FLOAT | Prix de sortie |
| `exit_reason` | VARCHAR(30) | TP_HIT, SL_HIT, EARLY_INVALIDATION, MANUAL, TIMEOUT |

### Résultats
| Colonne | Type | Description |
|---------|------|-------------|
| `duration_seconds` | FLOAT | Durée en secondes |
| `pnl_pct` | FLOAT | PnL brut en % |
| `pnl_usdt` | FLOAT | PnL brut en USDT |
| `gross_pnl_usdt` | FLOAT | PnL brut en USDT |
| `slippage_pct` | FLOAT | Slippage en % |
| `slippage_usdt` | FLOAT | Slippage en USDT |
| `fees_usdt` | FLOAT | Frais en USDT |
| `net_pnl_usdt` | FLOAT | PnL net en USDT |
| `net_pnl_pct` | FLOAT | PnL net en % |
| `win` | BOOLEAN | True si net_pnl_usdt > 0 |

### Events pendant position
| Colonne | Type | Description |
|---------|------|-------------|
| `break_even_set` | BOOLEAN | Break-even activé |
| `break_even_triggered_at` | TIMESTAMPTZ | Date d'activation break-even |
| `partial_tp_executed` | BOOLEAN | TP partiel exécuté |
| `partial_tp_triggered_at` | TIMESTAMPTZ | Date d'exécution TP partiel |
| `partial_tp_profit` | FLOAT | Profit du TP partiel |
| `partial_tp_percent` | FLOAT | % de position vendue |
| `tp_escalier_levels_executed` | INTEGER | Nombre de niveaux TP escalier exécutés |
| `tp_escalier_profits` | FLOAT | Profits totaux TP escalier |
| `trailing_stop_activated` | BOOLEAN | Trailing stop activé |
| `trailing_stop_triggered_at` | TIMESTAMPTZ | Date d'activation trailing stop |

### Métriques de position
| Colonne | Type | Description |
|---------|------|-------------|
| `max_favorable_excursion` | FLOAT | Meilleur prix atteint (%) |
| `max_adverse_excursion` | FLOAT | Pire prix atteint (%) |
| `max_favorable_excursion_usdt` | FLOAT | Meilleur prix atteint (USDT) |
| `max_adverse_excursion_usdt` | FLOAT | Pire prix atteint (USDT) |

### Métriques de qualité
| Colonne | Type | Description |
|---------|------|-------------|
| `risk_reward_ratio` | FLOAT | (TP - Entry) / (Entry - SL) |
| `profit_factor` | FLOAT | Pour analyse session |

### Scalability data au entry
| Colonne | Type | Description |
|---------|------|-------------|
| `entry_book_depth` | FLOAT | Profondeur du carnet d'ordres |
| `entry_bid_vol` | FLOAT | Volume bid |
| `entry_ask_vol` | FLOAT | Volume ask |
| `entry_orderbook_imbalance` | FLOAT | Déséquilibre du carnet d'ordres |

### Métadonnées
| Colonne | Type | Description |
|---------|------|-------------|
| `created_at` | TIMESTAMPTZ | Date de création |
| `updated_at` | TIMESTAMPTZ | Date de mise à jour |

**Total : 60 colonnes**

---

## 📊 TABLE 6 : `market_context`

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | BIGSERIAL | Identifiant |
| `timestamp` | TIMESTAMPTZ | Date/heure |
| `session_id` | UUID | Référence à trading_sessions |
| `hour_of_day` | INTEGER | Heure du jour (0-23) |
| `day_of_week` | INTEGER | Jour de la semaine (0-6, 0=Lundi) |
| `btc_price` | FLOAT | Prix BTC |
| `eth_price` | FLOAT | Prix ETH |
| `total_opportunities_detected` | INTEGER | Total opportunités détectées |
| `avg_spread` | FLOAT | Spread moyen |
| `avg_volatility_1m` | FLOAT | Volatilité moyenne 1m |
| `avg_volatility_5m` | FLOAT | Volatilité moyenne 5m |
| `active_positions_count` | INTEGER | Nombre de positions actives |
| `session_win_rate` | FLOAT | Win rate de la session |
| `session_pnl_usdt` | FLOAT | PnL session en USDT |
| `session_pnl_pct` | FLOAT | PnL session en % |
| `market_trend` | VARCHAR(10) | BULLISH, BEARISH, NEUTRAL |
| `market_volatility` | VARCHAR(10) | LOW, MEDIUM, HIGH |
| `fear_greed_index` | FLOAT | Indice Fear & Greed |
| `global_metrics` | JSONB | Métriques globales additionnelles |
| `session_stats` | JSONB | Stats session additionnelles |

**Total : 20 colonnes**

---

## 📊 TABLE 7 : `scan_errors`

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | BIGSERIAL | Identifiant |
| `timestamp` | TIMESTAMPTZ | Date/heure |
| `session_id` | UUID | Référence à trading_sessions |
| `symbol` | VARCHAR(30) | Symbole |
| `error_type` | VARCHAR(50) | 'API_ERROR', 'TIMEOUT', 'DATA_INVALID', etc. |
| `error_message` | TEXT | Message d'erreur |
| `error_stack` | TEXT | Stack trace |
| `scan_context` | JSONB | Contexte au moment de l'erreur |
| `resolved` | BOOLEAN | Erreur résolue |
| `resolved_at` | TIMESTAMPTZ | Date de résolution |

**Total : 10 colonnes**

---

## 📊 TABLE 8 : `model_predictions`

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | BIGSERIAL | Identifiant |
| `timestamp` | TIMESTAMPTZ | Date/heure |
| `scan_log_id` | BIGINT | Référence à scan_logs |
| `opportunity_id` | UUID | Référence à opportunities |
| `model_version` | VARCHAR(50) | Version du modèle |
| `predicted_win` | BOOLEAN | Prédiction win |
| `win_probability` | FLOAT | Probabilité de win (0.0-1.0) |
| `predicted_pnl_pct` | FLOAT | PnL prédit en % |
| `confidence_score` | FLOAT | Score de confiance (0.0-1.0) |
| `features_used` | JSONB | Features utilisées |
| `actual_win` | BOOLEAN | Résultat réel win |
| `actual_pnl_pct` | FLOAT | PnL réel en % |
| `prediction_correct` | BOOLEAN | Prédiction correcte |
| `created_at` | TIMESTAMPTZ | Date de création |

**Total : 14 colonnes**

---

## 📊 TABLE 9 : `features_engineered`

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | BIGSERIAL | Identifiant |
| `scan_log_id` | BIGINT | Référence à scan_logs |
| `timestamp` | TIMESTAMPTZ | Date/heure |
| `rsi_macd_divergence` | BOOLEAN | Divergence RSI-MACD |
| `ema_cross_signal` | VARCHAR(10) | 'BULLISH', 'BEARISH', 'NONE' |
| `volume_atr_ratio` | FLOAT | Ratio Volume/ATR |
| `bb_squeeze` | BOOLEAN | Bollinger Bands squeeze |
| `adx_trend_alignment` | BOOLEAN | Alignement ADX trend |
| `multi_timeframe_alignment` | BOOLEAN | Alignement multi-timeframe |
| `momentum_score` | FLOAT | Score de momentum |
| `trend_score` | FLOAT | Score de trend |
| `volatility_score` | FLOAT | Score de volatilité |
| `liquidity_score` | FLOAT | Score de liquidité |
| `feature_version` | VARCHAR(20) | Version des features (défaut: 'v1.0') |

**Total : 14 colonnes**

---

## 📊 RÉSUMÉ TOTAL

| Table | Nombre de colonnes |
|-------|-------------------|
| `trading_sessions` | 12 |
| `config_snapshots` | 7 |
| `scan_logs` | 95 |
| `opportunities` | 24 |
| `trades` | 60 |
| `market_context` | 20 |
| `scan_errors` | 10 |
| `model_predictions` | 14 |
| `features_engineered` | 14 |
| **TOTAL** | **256 colonnes** |

---

## 🔍 VARIABLES POTENTIELLEMENT MANQUANTES

### À vérifier dans le code :

1. **Indicateurs d'entrée manquants dans `trades`** :
   - ❓ `entry_macd_1m`, `entry_macd_signal_1m` (actuellement seulement `entry_macd_hist_1m`)
   - ❓ `entry_macd_5m`, `entry_macd_signal_5m` (actuellement seulement `entry_macd_hist_5m`)
   - ❓ `entry_ema9_1m`, `entry_ema21_1m`, `entry_ema_diff_pct_1m`
   - ❓ `entry_ema9_5m`, `entry_ema21_5m`, `entry_ema_diff_pct_5m`
   - ❓ `entry_bb_upper_1m`, `entry_bb_middle_1m`, `entry_bb_lower_1m`
   - ❓ `entry_bb_upper_5m`, `entry_bb_middle_5m`, `entry_bb_lower_5m`

2. **Indicateurs de sortie** :
   - ❓ `exit_rsi_1m`, `exit_rsi_5m`
   - ❓ `exit_macd_hist_1m`, `exit_macd_hist_5m`
   - ❓ `exit_adx_1m`, `exit_adx_5m`
   - ❓ `exit_atr_pct_1m`, `exit_atr_pct_5m`
   - ❓ `exit_score`
   - ❓ `exit_volume_ratio_1m`, `exit_volume_ratio_5m`
   - ❓ `exit_spread_pct`, `exit_balance_score`

3. **Métriques additionnelles** :
   - ❓ `entry_timestamp_scan` (timestamp du scan qui a généré l'opportunité)
   - ❓ `entry_to_exit_price_change_pct` (variation de prix entre entry et exit)
   - ❓ `time_in_profit_pct` (% du temps en profit)
   - ❓ `time_in_loss_pct` (% du temps en perte)

4. **Données de contexte** :
   - ❓ `entry_hour_of_day` (heure d'entrée)
   - ❓ `entry_day_of_week` (jour d'entrée)
   - ❓ `exit_hour_of_day` (heure de sortie)
   - ❓ `exit_day_of_week` (jour de sortie)

---

## ✅ CONCLUSION

Le schéma contient **256 colonnes** au total, réparties sur **9 tables**.

Les colonnes les plus importantes pour le ML sont déjà présentes :
- ✅ Indicateurs d'entrée de base (RSI, MACD hist, ADX, ATR, score, volume, spread, balance)
- ✅ Métriques de position (max_favorable_excursion, max_adverse_excursion)
- ✅ Métriques de qualité (risk_reward_ratio)
- ✅ Scalability data (book_depth, bid_vol, ask_vol, orderbook_imbalance)

**Variables potentiellement utiles à ajouter :**
- Indicateurs d'entrée additionnels (EMA, MACD complet, Bollinger Bands)
- Indicateurs de sortie (pour comparer entry vs exit)
- Métriques temporelles (heure/jour d'entrée/sortie)

