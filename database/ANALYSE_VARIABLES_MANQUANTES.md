# 🔍 Analyse : Variables Potentiellement Manquantes dans le Schéma

**Date :** 2025-11-12

---

## ✅ VARIABLES DÉJÀ PRÉSENTES DANS LE SCHÉMA

### Table `trades` - Indicateurs d'entrée (actuellement loggés)
- ✅ `entry_rsi_1m`, `entry_rsi_5m`
- ✅ `entry_macd_hist_1m`, `entry_macd_hist_5m`
- ✅ `entry_adx_1m`, `entry_adx_5m`
- ✅ `entry_atr_pct_1m`, `entry_atr_pct_5m`
- ✅ `entry_score`
- ✅ `entry_volume_ratio_1m`, `entry_volume_ratio_5m`
- ✅ `entry_spread_pct`, `entry_balance_score`
- ✅ `entry_conditions`, `entry_condition_count`
- ✅ `entry_book_depth`, `entry_bid_vol`, `entry_ask_vol`, `entry_orderbook_imbalance`

---

## ⚠️ VARIABLES DISPONIBLES DANS LE CODE MAIS NON LOGGÉES

### 1. Indicateurs d'entrée additionnels (disponibles dans `scan_logs` mais pas dans `trades`)

#### EMA (Exponential Moving Average)
- ❌ `entry_ema9_1m`, `entry_ema21_1m`, `entry_ema_diff_pct_1m`
- ❌ `entry_ema9_5m`, `entry_ema21_5m`, `entry_ema_diff_pct_5m`

**Disponibilité :** Disponibles dans `scan_logs` (lignes 92-94, 135-137)  
**Utilité ML :** ⭐⭐⭐ (Utile pour analyser la tendance au moment de l'entrée)

#### MACD complet (pas seulement histogramme)
- ❌ `entry_macd_1m`, `entry_macd_signal_1m` (actuellement seulement `entry_macd_hist_1m`)
- ❌ `entry_macd_5m`, `entry_macd_signal_5m` (actuellement seulement `entry_macd_hist_5m`)

**Disponibilité :** Disponibles dans `scan_logs` (lignes 101-104, 144-147)  
**Utilité ML :** ⭐⭐ (Histogramme est souvent suffisant, mais MACD et signal peuvent être utiles)

#### Bollinger Bands
- ❌ `entry_bb_upper_1m`, `entry_bb_middle_1m`, `entry_bb_lower_1m`
- ❌ `entry_bb_width_1m`, `entry_bb_distance_to_lower_1m`, `entry_bb_distance_to_upper_1m`
- ❌ `entry_bb_upper_5m`, `entry_bb_middle_5m`, `entry_bb_lower_5m`
- ❌ `entry_bb_width_5m`, `entry_bb_distance_to_lower_5m`, `entry_bb_distance_to_upper_5m`

**Disponibilité :** Disponibles dans `scan_logs` (lignes 117-122, 160-165)  
**Utilité ML :** ⭐⭐⭐ (Utile pour analyser la volatilité et la position du prix)

#### Volume additionnel
- ❌ `entry_volume_1m`, `entry_volume_avg_1m`, `entry_volume_spike_1m`
- ❌ `entry_volume_5m`, `entry_volume_avg_5m`, `entry_volume_spike_5m`

**Disponibilité :** Disponibles dans `scan_logs` (lignes 125-128, 168-171)  
**Utilité ML :** ⭐⭐ (Volume ratio est déjà présent, mais volume absolu peut être utile)

#### RSI période précédente
- ❌ `entry_rsi_prev_1m`, `entry_rsi_prev_5m`

**Disponibilité :** Disponibles dans `scan_logs` (lignes 98, 141)  
**Utilité ML :** ⭐⭐ (Utile pour détecter les changements de momentum)

#### MACD Histogramme période précédente
- ❌ `entry_macd_hist_prev_1m`, `entry_macd_hist_prev_5m`

**Disponibilité :** Disponibles dans `scan_logs` (lignes 104, 147)  
**Utilité ML :** ⭐⭐ (Utile pour détecter les changements de momentum)

#### ADX DI+ et DI-
- ❌ `entry_di_plus_1m`, `entry_di_minus_1m`, `entry_di_gap_1m`
- ❌ `entry_di_plus_5m`, `entry_di_minus_5m`, `entry_di_gap_5m`

**Disponibilité :** Disponibles dans `scan_logs` (lignes 108-110, 151-153)  
**Utilité ML :** ⭐⭐ (DI gap est déjà calculé, mais DI+ et DI- peuvent être utiles)

#### ATR absolu (pas seulement %)
- ❌ `entry_atr_1m`, `entry_atr_5m`

**Disponibilité :** Disponibles dans `scan_logs` (lignes 113, 156)  
**Utilité ML :** ⭐ (ATR % est généralement suffisant)

---

### 2. Indicateurs de sortie (actuellement absents)

**Problème :** Aucun indicateur de sortie n'est loggé actuellement.

#### Indicateurs de sortie suggérés
- ❌ `exit_rsi_1m`, `exit_rsi_5m`
- ❌ `exit_macd_hist_1m`, `exit_macd_hist_5m`
- ❌ `exit_adx_1m`, `exit_adx_5m`
- ❌ `exit_atr_pct_1m`, `exit_atr_pct_5m`
- ❌ `exit_score`
- ❌ `exit_volume_ratio_1m`, `exit_volume_ratio_5m`
- ❌ `exit_spread_pct`, `exit_balance_score`
- ❌ `exit_price_change_pct` (variation depuis l'entrée)

**Disponibilité :** ❌ Non capturés actuellement dans le code  
**Utilité ML :** ⭐⭐⭐⭐⭐ (CRITIQUE pour analyser pourquoi une position a été fermée et dans quelles conditions)

---

### 3. Métriques temporelles

#### Heure et jour
- ❌ `entry_hour_of_day` (0-23)
- ❌ `entry_day_of_week` (0-6, 0=Lundi)
- ❌ `exit_hour_of_day` (0-23)
- ❌ `exit_day_of_week` (0-6, 0=Lundi)

**Disponibilité :** ✅ Facilement calculable depuis `timestamp_entry` et `timestamp_exit`  
**Utilité ML :** ⭐⭐⭐ (Utile pour détecter des patterns temporels)

---

### 4. Métriques de performance additionnelles

#### Temps en profit/perte
- ❌ `time_in_profit_pct` (% du temps où la position était en profit)
- ❌ `time_in_loss_pct` (% du temps où la position était en perte)
- ❌ `time_to_max_profit_seconds` (Temps pour atteindre le profit maximum)
- ❌ `time_to_max_loss_seconds` (Temps pour atteindre la perte maximum)

**Disponibilité :** ⚠️ Nécessite `pnl_history` avec timestamps  
**Utilité ML :** ⭐⭐⭐ (Utile pour optimiser les durées de position)

#### Variation de prix
- ❌ `entry_to_exit_price_change_pct` (variation de prix entre entry et exit)
- ❌ `entry_to_max_profit_price_change_pct` (variation jusqu'au profit max)
- ❌ `entry_to_max_loss_price_change_pct` (variation jusqu'à la perte max)

**Disponibilité :** ✅ Facilement calculable depuis les prix  
**Utilité ML :** ⭐⭐ (Utile pour analyser les mouvements de prix)

---

### 5. Métriques de qualité additionnelles

#### Drawdown
- ❌ `max_drawdown_pct` (drawdown maximum en %)
- ❌ `max_drawdown_usdt` (drawdown maximum en USDT)
- ❌ `recovery_time_seconds` (temps pour récupérer du drawdown max)

**Disponibilité :** ⚠️ Nécessite `pnl_history` avec timestamps  
**Utilité ML :** ⭐⭐⭐ (Utile pour analyser la volatilité des positions)

---

## 🎯 RECOMMANDATIONS PAR PRIORITÉ

### 🔴 PRIORITÉ HAUTE (À ajouter absolument)

1. **Indicateurs de sortie** ⭐⭐⭐⭐⭐
   - `exit_rsi_1m`, `exit_rsi_5m`
   - `exit_macd_hist_1m`, `exit_macd_hist_5m`
   - `exit_adx_1m`, `exit_adx_5m`
   - `exit_atr_pct_1m`, `exit_atr_pct_5m`
   - `exit_score`
   - `exit_volume_ratio_1m`, `exit_volume_ratio_5m`
   - `exit_spread_pct`, `exit_balance_score`
   
   **Pourquoi :** Essentiel pour comprendre dans quelles conditions une position a été fermée et corréler avec les résultats.

2. **Métriques temporelles** ⭐⭐⭐
   - `entry_hour_of_day`, `entry_day_of_week`
   - `exit_hour_of_day`, `exit_day_of_week`
   
   **Pourquoi :** Permet de détecter des patterns temporels (ex: meilleures performances à certaines heures).

### 🟡 PRIORITÉ MOYENNE (Utile mais pas critique)

3. **EMA d'entrée** ⭐⭐⭐
   - `entry_ema9_1m`, `entry_ema21_1m`, `entry_ema_diff_pct_1m`
   - `entry_ema9_5m`, `entry_ema21_5m`, `entry_ema_diff_pct_5m`
   
   **Pourquoi :** Utile pour analyser la tendance au moment de l'entrée.

4. **Bollinger Bands d'entrée** ⭐⭐⭐
   - `entry_bb_upper_1m`, `entry_bb_middle_1m`, `entry_bb_lower_1m`
   - `entry_bb_width_1m`, `entry_bb_distance_to_lower_1m`, `entry_bb_distance_to_upper_1m`
   - `entry_bb_upper_5m`, `entry_bb_middle_5m`, `entry_bb_lower_5m`
   - `entry_bb_width_5m`, `entry_bb_distance_to_lower_5m`, `entry_bb_distance_to_upper_5m`
   
   **Pourquoi :** Utile pour analyser la volatilité et la position du prix.

### 🟢 PRIORITÉ BASSE (Optionnel)

5. **MACD complet** ⭐⭐
   - `entry_macd_1m`, `entry_macd_signal_1m`
   - `entry_macd_5m`, `entry_macd_signal_5m`
   
   **Pourquoi :** L'histogramme est généralement suffisant, mais MACD et signal peuvent être utiles.

6. **RSI/MACD période précédente** ⭐⭐
   - `entry_rsi_prev_1m`, `entry_rsi_prev_5m`
   - `entry_macd_hist_prev_1m`, `entry_macd_hist_prev_5m`
   
   **Pourquoi :** Utile pour détecter les changements de momentum.

7. **Métriques de performance additionnelles** ⭐⭐
   - `time_in_profit_pct`, `time_in_loss_pct`
   - `entry_to_exit_price_change_pct`
   - `max_drawdown_pct`, `max_drawdown_usdt`
   
   **Pourquoi :** Utile pour analyser la performance des positions, mais nécessite des données additionnelles.

---

## 📊 RÉSUMÉ

### Variables actuellement dans le schéma : **256 colonnes**

### Variables recommandées à ajouter :

| Catégorie | Nombre | Priorité |
|-----------|--------|----------|
| Indicateurs de sortie | ~12 | 🔴 HAUTE |
| Métriques temporelles | 4 | 🔴 HAUTE |
| EMA d'entrée | 6 | 🟡 MOYENNE |
| Bollinger Bands d'entrée | 12 | 🟡 MOYENNE |
| MACD complet | 4 | 🟢 BASSE |
| RSI/MACD période précédente | 4 | 🟢 BASSE |
| Métriques de performance | ~6 | 🟢 BASSE |
| **TOTAL** | **~48 colonnes** | |

---

## ✅ CONCLUSION

Le schéma actuel est **très complet** avec **256 colonnes**. 

**Les ajouts les plus importants seraient :**
1. **Indicateurs de sortie** (CRITIQUE pour ML)
2. **Métriques temporelles** (Utile pour patterns temporels)

Les autres variables sont optionnelles et peuvent être ajoutées progressivement selon les besoins du ML.

