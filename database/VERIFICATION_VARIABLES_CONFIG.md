# ✅ Vérification : Variables de Configuration dans le Schéma

**Date :** 2025-11-12

---

## 📊 Stockage des Variables de Configuration

### Table `config_snapshots`
- ✅ **`config_data JSONB`** : Stocke TOUTES les variables de configuration
- ✅ Toutes les variables listées sont stockées dans ce champ JSONB

### Table `scan_logs`
- ✅ **`params_snapshot JSONB`** : Snapshot des paramètres au moment du scan
- ✅ Peut contenir les paramètres pertinents pour le scan

### Table `trades` (NOUVEAU)
- ✅ **`config_snapshot JSONB`** : Snapshot de la configuration au moment du trade
- ✅ Permet de corréler la configuration avec les résultats du trade

---

## ✅ Variables de Configuration - Statut

### Général
- ✅ `fee_per_trade` → `config_snapshots.config_data`
- ✅ `use_slippage_calculation` → `config_snapshots.config_data`
- ✅ `position_timeout` → `config_snapshots.config_data`
- ✅ `check_interval` → `config_snapshots.config_data`
- ✅ `scan_interval` → `config_snapshots.config_data`
- ✅ `scalability_interval` → `config_snapshots.config_data`

### Validation & Scoring
- ✅ `min_conditions` → `config_snapshots.config_data`
- ✅ `use_weighted_scoring` → `config_snapshots.config_data`
- ✅ `min_score_required` → `config_snapshots.config_data`
- ✅ `min_score_adx_high` → `config_snapshots.config_data`
- ✅ `min_score_adx_low` → `config_snapshots.config_data`
- ✅ `dynamic_tolerance_adx_high` → `config_snapshots.config_data`
- ✅ `dynamic_tolerance_adx_low` → `config_snapshots.config_data`

### Patterns Techniques
- ✅ `use_breakout` → `config_snapshots.config_data`
- ✅ `use_snr` → `config_snapshots.config_data`
- ✅ `use_wick` → `config_snapshots.config_data`
- ✅ `use_divergence` → `config_snapshots.config_data`

### Patterns de Bougies
- ✅ `use_engulfing` → `config_snapshots.config_data`
- ✅ `use_hammer` → `config_snapshots.config_data`
- ✅ `use_shooting_star` → `config_snapshots.config_data`
- ✅ `use_doji` → `config_snapshots.config_data`
- ✅ `use_marubozu` → `config_snapshots.config_data`
- ✅ `use_morning_star` → `config_snapshots.config_data`
- ✅ `use_evening_star` → `config_snapshots.config_data`

### Seuils & Filtres
- ✅ `snr_threshold` → `config_snapshots.config_data`
- ✅ `breakout_threshold` → `config_snapshots.config_data`
- ✅ `wick_ratio_max` → `config_snapshots.config_data`
- ✅ `di_gap_min` → `config_snapshots.config_data`
- ✅ `di_gap_adx_threshold` → `config_snapshots.config_data`
- ✅ `optimal_atr_min_1m` → `config_snapshots.config_data`
- ✅ `optimal_atr_max_1m` → `config_snapshots.config_data`
- ✅ `optimal_atr_min_5m` → `config_snapshots.config_data`
- ✅ `optimal_atr_max_5m` → `config_snapshots.config_data`

### Money Management
- ✅ `account_size` → `config_snapshots.config_data`
- ✅ `risk_per_trade` → `config_snapshots.config_data`
- ✅ `volume_multiplier` → `config_snapshots.config_data`
- ✅ `use_confluence` → `config_snapshots.config_data`

### TP/SL Configuration
- ✅ `tp_sl_mode` → `config_snapshots.config_data` + `trades.tp_sl_mode` (VARCHAR)
- ✅ `tp_percent` → `config_snapshots.config_data`
- ✅ `sl_percent` → `config_snapshots.config_data`
- ✅ `break_even_trigger` → `config_snapshots.config_data`
- ✅ `trailing_distance` → `config_snapshots.config_data`

### Mode ATR
- ✅ `atr_mult_tp` → `config_snapshots.config_data`
- ✅ `atr_mult_sl` → `config_snapshots.config_data`
- ✅ `atr_min` → `config_snapshots.config_data`
- ✅ `atr_max` → `config_snapshots.config_data`

### TP Escalier
- ✅ `partial_tp_percent` → `config_snapshots.config_data`
- ✅ `escalier_level1_pnl` → `config_snapshots.config_data`
- ✅ `escalier_level1_size` → `config_snapshots.config_data`
- ✅ `escalier_level2_pnl` → `config_snapshots.config_data`
- ✅ `escalier_level2_size` → `config_snapshots.config_data`
- ✅ `escalier_level3_pnl` → `config_snapshots.config_data`
- ✅ `escalier_level3_size` → `config_snapshots.config_data`
- ✅ `escalier_level4_pnl` → `config_snapshots.config_data`
- ✅ `escalier_level4_size` → `config_snapshots.config_data`

### Trailing Stop
- ✅ `trailing_enabled` → `config_snapshots.config_data`
- ✅ `trailing_trigger_pnl` → `config_snapshots.config_data`
- ✅ `trailing_atr_multiplier` → `config_snapshots.config_data`
- ✅ `trailing_min_distance` → `config_snapshots.config_data`
- ✅ `trailing_max_distance` → `config_snapshots.config_data`

### Timeframe & Trend
- ✅ `trend_timeframe` → `config_snapshots.config_data` + `scan_logs.trend_timeframe` (VARCHAR)

### Scanner
- ✅ `top_pairs_limit` → `config_snapshots.config_data`
- ✅ `balance_score_min` → `config_snapshots.config_data`

### Configurations Avancées (Objets JSON)
- ✅ `early_invalidation` → `config_snapshots.config_data` (JSONB)
- ✅ `trailing_stop` → `config_snapshots.config_data` (JSONB)
- ✅ `adaptive_thresholds` → `config_snapshots.config_data` (JSONB)
- ✅ `dynamic_correlation` → `config_snapshots.config_data` (JSONB)
- ✅ `position_sizing` → `config_snapshots.config_data` (JSONB)
- ✅ `correlation_filter` → `config_snapshots.config_data` (JSONB)
- ✅ `recovery_mode` → `config_snapshots.config_data` (JSONB)
- ✅ `tp_escalier` → `config_snapshots.config_data` (JSONB)

### RISK_CONFIG
- ✅ `base_risk` → `config_snapshots.config_data`
- ✅ `quality_multiplier_perfect` → `config_snapshots.config_data`
- ✅ `quality_multiplier_good` → `config_snapshots.config_data`
- ✅ `quality_multiplier_ok` → `config_snapshots.config_data`
- ✅ `quality_multiplier_weak` → `config_snapshots.config_data`
- ✅ `vol_multiplier_high` → `config_snapshots.config_data`
- ✅ `vol_multiplier_low` → `config_snapshots.config_data`
- ✅ `max_risk` → `config_snapshots.config_data`
- ✅ `min_risk` → `config_snapshots.config_data`

### CONDITION_WEIGHTS
- ✅ `EMAs` → `config_snapshots.config_data`
- ✅ `ADX_DI` → `config_snapshots.config_data`
- ✅ `MACD` → `config_snapshots.config_data`
- ✅ `RSI` → `config_snapshots.config_data`
- ✅ `Volume` → `config_snapshots.config_data`
- ✅ `Bollinger` → `config_snapshots.config_data`
- ✅ `Pattern` → `config_snapshots.config_data`
- ✅ `Divergence` → `config_snapshots.config_data`

### TREND_BONUS_CONFIG
- ✅ `use_direct_score` → `config_snapshots.config_data`
- ✅ `bonus_divisor` → `config_snapshots.config_data`

### RETRY_CONFIG
- ✅ `max_attempts` → `config_snapshots.config_data`
- ✅ `wait_multiplier` → `config_snapshots.config_data`
- ✅ `wait_min` → `config_snapshots.config_data`
- ✅ `wait_max` → `config_snapshots.config_data`

### CIRCUIT_BREAKER_CONFIG
- ✅ `fail_max` → `config_snapshots.config_data`
- ✅ `reset_timeout` → `config_snapshots.config_data`

### WEBSOCKET_CONFIG
- ✅ `url` → `config_snapshots.config_data`
- ✅ `ping_interval` → `config_snapshots.config_data`
- ✅ `reconnect_delay` → `config_snapshots.config_data`
- ✅ `timeout` → `config_snapshots.config_data`
- ✅ `watchdog_timeout` → `config_snapshots.config_data`

---

## ✅ CONCLUSION

**TOUTES les variables de configuration sont déjà stockées dans le schéma via :**
1. ✅ `config_snapshots.config_data` (JSONB) - Historique complet
2. ✅ `scan_logs.params_snapshot` (JSONB) - Snapshot au moment du scan
3. ✅ `trades.config_snapshot` (JSONB) - **NOUVEAU** - Snapshot au moment du trade

**Aucune variable de configuration n'est manquante dans le schéma.**

Les variables sont stockées en JSONB, ce qui permet :
- ✅ Flexibilité (ajout/modification sans migration)
- ✅ Structure hiérarchique (objets imbriqués)
- ✅ Requêtes JSONB (PostgreSQL supporte les requêtes JSON)
- ✅ Pas de doublons (une seule colonne JSONB pour toutes les variables)

---

## 📝 Note sur les Variables Potentiellement Inutiles

### Variables qui pourraient être considérées comme "internes" (non critiques pour ML) :

1. **WEBSOCKET_CONFIG** ⚠️
   - `url`, `ping_interval`, `reconnect_delay`, `timeout`, `watchdog_timeout`
   - **Utilité ML :** ⭐ (Très faible - configuration technique)
   - **Recommandation :** Garder dans `config_snapshots` mais peut-être pas dans `trades.config_snapshot`

2. **RETRY_CONFIG** ⚠️
   - `max_attempts`, `wait_multiplier`, `wait_min`, `wait_max`
   - **Utilité ML :** ⭐ (Faible - configuration technique)
   - **Recommandation :** Garder dans `config_snapshots` mais peut-être pas dans `trades.config_snapshot`

3. **CIRCUIT_BREAKER_CONFIG** ⚠️
   - `fail_max`, `reset_timeout`
   - **Utilité ML :** ⭐ (Faible - configuration technique)
   - **Recommandation :** Garder dans `config_snapshots` mais peut-être pas dans `trades.config_snapshot`

**Toutes les autres variables sont importantes pour le ML** car elles influencent directement :
- Les décisions de trading (seuils, filtres, patterns)
- La gestion du risque (risk_per_trade, position_sizing)
- Les paramètres TP/SL (tp_percent, sl_percent, trailing, etc.)

---

## 🎯 Recommandation Finale

**Garder TOUTES les variables dans `config_snapshots.config_data`** (historique complet).

**Pour `trades.config_snapshot`**, on peut choisir de stocker seulement les variables pertinentes pour le ML :
- ✅ Toutes les variables de trading (seuils, filtres, patterns, TP/SL, risk, etc.)
- ⚠️ Optionnel : Variables techniques (WEBSOCKET, RETRY, CIRCUIT_BREAKER)

**Cela permet de :**
- Réduire la taille de `trades.config_snapshot` (si nécessaire)
- Garder seulement les variables qui influencent les résultats de trading
- Faciliter les requêtes ML (moins de données à parser)

**Mais on peut aussi tout garder** - JSONB est efficace même avec beaucoup de données.

