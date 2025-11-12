# 🔍 Analyse Complétude Schéma PostgreSQL

**Date :** 2025-11-12  
**Objectif :** Vérifier que le schéma PostgreSQL est complet et correspond au code Python

---

## ✅ COLONNES UTILISÉES DANS LE CODE (Vérifiées)

### Table `trades` - Colonnes utilisées actuellement :
- ✅ `timestamp_entry`, `timestamp_exit`
- ✅ `session_id`, `opportunity_id`, `symbol`, `direction`
- ✅ `entry_price`, `exit_price`, `size_usdt`
- ✅ `tp_price`, `sl_price`, `tp_sl_mode`
- ✅ `gross_pnl_usdt`, `pnl_pct`, `pnl_usdt`
- ✅ `net_pnl_usdt`, `net_pnl_pct`
- ✅ `fees_usdt`, `slippage_pct`
- ✅ `exit_reason`, `duration_seconds`
- ✅ `break_even_set`, `trailing_stop_activated`, `partial_tp_executed`
- ✅ `tp_escalier_levels_executed`, `tp_escalier_profits`
- ✅ `win`

---

## ⚠️ COLONNES MANQUANTES DANS LE CODE (Présentes dans le schéma SQL)

### Table `trades` - Colonnes NON utilisées mais disponibles :

#### 1. **Indicateurs d'entrée (pour ML)** ⚠️ IMPORTANT
Le schéma SQL prévoit ces colonnes pour capturer les indicateurs au moment de l'entrée :
- ❌ `entry_rsi_1m`, `entry_rsi_5m`
- ❌ `entry_macd_hist_1m`, `entry_macd_hist_5m`
- ❌ `entry_adx_1m`, `entry_adx_5m`
- ❌ `entry_atr_pct_1m`, `entry_atr_pct_5m`
- ❌ `entry_score`
- ❌ `entry_volume_ratio_1m`, `entry_volume_ratio_5m`
- ❌ `entry_spread_pct`, `entry_balance_score`
- ❌ `entry_conditions TEXT[]`, `entry_condition_count`

**Impact :** Ces données sont cruciales pour le ML car elles permettent de corréler les conditions d'entrée avec les résultats.

**Code actuel :** `position_manager.py` prépare `entry_indicators` dans `trade_data` mais le datalogger ne les insère pas.

---

#### 2. **Métriques de position** ⚠️ UTILE
- ❌ `max_favorable_excursion` (meilleur prix atteint en %)
- ❌ `max_adverse_excursion` (pire prix atteint en %)
- ❌ `max_favorable_excursion_usdt`
- ❌ `max_adverse_excursion_usdt`

**Impact :** Utiles pour analyser la performance des positions et optimiser les TP/SL.

**Code actuel :** `position_manager.py` a `pnl_history` qui contient ces données (`max_pnl_reached`, `min_pnl_reached`), mais elles ne sont pas loggées.

---

#### 3. **Métriques de qualité** ⚠️ UTILE
- ❌ `risk_reward_ratio` ((TP - Entry) / (Entry - SL))
- ❌ `profit_factor` (pour analyse session)

**Impact :** Utiles pour l'analyse de qualité des setups.

---

#### 4. **Scalability data au entry** ⚠️ OPTIONNEL
- ❌ `entry_book_depth`
- ❌ `entry_bid_vol`, `entry_ask_vol`
- ❌ `entry_orderbook_imbalance`

**Impact :** Utiles pour analyser l'impact de la liquidité sur les résultats.

---

#### 5. **Timestamps détaillés** ⚠️ OPTIONNEL
- ❌ `break_even_triggered_at`
- ❌ `partial_tp_triggered_at`
- ❌ `trailing_stop_triggered_at`

**Impact :** Utiles pour analyser le timing des événements.

---

#### 6. **Détails TP partiel** ⚠️ OPTIONNEL
- ❌ `partial_tp_profit` (profit réalisé)
- ❌ `partial_tp_percent` (% de position vendue)

**Impact :** Utiles pour analyser l'efficacité des TP partiels.

---

#### 7. **Slippage en USDT** ⚠️ OPTIONNEL
- ❌ `slippage_usdt` (actuellement seul `slippage_pct` est loggé)

**Impact :** Utile pour analyser l'impact réel du slippage.

---

#### 8. **Référence scan_log_id** ⚠️ UTILE
- ❌ `scan_log_id` (référence au scan qui a généré l'opportunité)

**Impact :** Permet de lier directement un trade au scan qui l'a généré, utile pour le ML.

---

## 📊 Table `opportunities` - Vérification

### Colonnes utilisées :
- ✅ `scan_log_id`, `session_id`, `symbol`, `direction`
- ✅ `entry_suggested`, `tp_suggested`, `sl_suggested`, `tp_sl_mode`
- ✅ `status`, `setup_score`, `conditions_matched`

### Colonnes NON utilisées :
- ❌ `setup_reason` (TEXT)
- ❌ `condition_count` (INTEGER)
- ❌ `score_long`, `score_short`, `score_min_required`
- ❌ `trend_bonus`, `divergence_bonus`
- ❌ `ignored_reason`, `executed_at`, `expired_at`

**Impact :** Ces colonnes permettraient de mieux tracker l'évolution des opportunités.

---

## 📊 Table `scan_logs` - Vérification

### ✅ Colonnes utilisées : TOUTES
Le code Python utilise toutes les colonnes définies dans le schéma SQL pour `scan_logs`.

---

## 📊 Table `market_context` - Vérification

### ⚠️ INCOHÉRENCE DÉTECTÉE

**Problème :** Le code Python utilise des colonnes JSONB qui n'existent pas dans le schéma SQL :
- ❌ `global_metrics` (JSONB) - **N'EXISTE PAS** dans le schéma SQL
- ❌ `session_stats` (JSONB) - **N'EXISTE PAS** dans le schéma SQL

**Le schéma SQL a à la place :**
- ✅ `total_opportunities_detected` (INTEGER)
- ✅ `avg_spread` (FLOAT)
- ✅ `avg_volatility_1m`, `avg_volatility_5m` (FLOAT)
- ✅ `active_positions_count` (INTEGER)
- ✅ `session_win_rate`, `session_pnl_usdt`, `session_pnl_pct` (FLOAT)

### Colonnes utilisées correctement :
- ✅ `session_id`, `hour_of_day`, `day_of_week`
- ✅ `btc_price`, `eth_price`
- ✅ `market_trend`, `market_volatility`, `fear_greed_index`

### Colonnes NON utilisées (mais présentes dans le schéma) :
- ❌ `total_opportunities_detected`
- ❌ `avg_spread`, `avg_volatility_1m`, `avg_volatility_5m`
- ❌ `active_positions_count`
- ❌ `session_win_rate`, `session_pnl_usdt`, `session_pnl_pct`

**Impact :** 
- **ERREUR ACTUELLE :** Le code essaie d'insérer dans `global_metrics` et `session_stats` qui n'existent pas → **ERREUR SQL**
- **SOLUTION :** Soit ajouter ces colonnes JSONB au schéma, soit utiliser les colonnes spécifiques existantes

---

## 🚨 ERREURS DÉTECTÉES

### 🔴 ERREUR CRITIQUE : `market_context`
Le code Python essaie d'insérer dans des colonnes JSONB (`global_metrics`, `session_stats`) qui **n'existent pas** dans le schéma SQL.

**Fichier :** `core/postgresql_datalogger.py` ligne 586-601  
**Problème :** `INSERT INTO market_context (..., global_metrics, session_stats, ...)`  
**Solution :** Soit :
1. Ajouter `global_metrics JSONB` et `session_stats JSONB` au schéma SQL
2. OU utiliser les colonnes spécifiques existantes (`total_opportunities_detected`, `avg_spread`, etc.)

---

## 🎯 RÉSUMÉ DES MANQUES CRITIQUES

### 🔴 PRIORITÉ HAUTE (Pour ML)
1. **Indicateurs d'entrée dans `trades`** : `entry_rsi_1m`, `entry_rsi_5m`, `entry_macd_hist_1m`, etc.
   - **Pourquoi :** Essentiels pour corréler conditions d'entrée avec résultats
   - **Code :** `position_manager.py` prépare déjà `entry_indicators` mais ne les logge pas

2. **`scan_log_id` dans `trades`** : Lien direct entre trade et scan
   - **Pourquoi :** Permet de joindre directement trades et scans pour ML
   - **Code :** Non récupéré actuellement

3. **`max_favorable_excursion` / `max_adverse_excursion`** : Métriques de performance
   - **Pourquoi :** Utiles pour optimiser TP/SL
   - **Code :** `position_manager.py` a `pnl_history` avec ces données

### 🟡 PRIORITÉ MOYENNE (Utile mais pas critique)
4. **`risk_reward_ratio`** : Métrique de qualité
5. **`entry_conditions`** : Conditions matchées au entry
6. **Timestamps détaillés** : `break_even_triggered_at`, etc.

### 🟢 PRIORITÉ BASSE (Optionnel)
7. **Scalability data** : `entry_book_depth`, etc.
8. **Détails TP partiel** : `partial_tp_profit`, `partial_tp_percent`
9. **Colonnes `opportunities`** : `setup_reason`, `score_long`, etc.

---

## ✅ CONCLUSION

### Le schéma SQL est **QUASI-COMPLET** ⚠️
- ✅ Toutes les colonnes nécessaires pour `trades`, `scan_logs`, `opportunities` sont définies
- ❌ **ERREUR :** `market_context` manque les colonnes JSONB utilisées par le code (`global_metrics`, `session_stats`)

### Le code Python **A DES ERREURS** 🔴
1. **ERREUR SQL :** `market_context` utilise des colonnes inexistantes (`global_metrics`, `session_stats`)
2. **Colonnes non utilisées :** Indicateurs d'entrée dans `trades` (CRITIQUE pour ML)

### Recommandation
**Pour une optimisation ML complète, il faudrait :**
1. Logger les indicateurs d'entrée dans `trades` (colonnes `entry_*`)
2. Logger `scan_log_id` dans `trades`
3. Logger `max_favorable_excursion` / `max_adverse_excursion` depuis `pnl_history`

**Le schéma est prêt, il faut juste compléter le code Python pour utiliser toutes les colonnes disponibles.**

---

## 📝 NOTES

- Le schéma SQL est bien conçu et prévoit tout ce qu'il faut pour le ML
- Le code Python actuel fonctionne mais n'exploite pas toutes les capacités du schéma
- Les colonnes manquantes sont principalement dans `trades` (indicateurs d'entrée)
- Aucune modification du schéma SQL n'est nécessaire

