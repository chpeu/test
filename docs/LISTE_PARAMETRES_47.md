# Liste des 47 Paramètres Configurables

## ✅ Vérification de l'utilisation dynamique

Tous les paramètres sont sauvegardés dans `config_overrides.json` et mis à jour dynamiquement dans `TRADING_CONFIG` via l'endpoint `/api/config/update` dans `main.py`.

---

## 📊 CATÉGORIE 1: Patterns Techniques (4 paramètres)

| # | Paramètre | Type | Description | Utilisation dynamique | Fichier(s) |
|---|-----------|------|-------------|----------------------|------------|
| 1 | `use_breakout` | Boolean | Activer/désactiver détection breakout | ✅ `TRADING_CONFIG.get('use_breakout', True)` | `core/analyzer/filters.py:135` |
| 2 | `use_snr` | Boolean | Activer/désactiver filtre SNR | ✅ `TRADING_CONFIG.get('use_snr', True)` | `core/analyzer/filters.py:89` |
| 3 | `use_wick` | Boolean | Activer/désactiver filtre wick ratio | ✅ `TRADING_CONFIG.get('use_wick', True)` | `core/analyzer/filters.py:172` |
| 4 | `use_divergence` | Boolean | Activer/désactiver bonus divergence | ✅ `TRADING_CONFIG.get('use_divergence', True)` | `core/analyzer/scoring.py:131` |

**✅ Tous les patterns techniques sont maintenant lus dynamiquement depuis TRADING_CONFIG.**

---

## 🕯️ CATÉGORIE 2: Patterns de Bougies (7 paramètres)

| # | Paramètre | Type | Description | Utilisation dynamique | Fichier(s) |
|---|-----------|------|-------------|----------------------|------------|
| 5 | `use_engulfing` | Boolean | Activer pattern Engulfing | ✅ `TRADING_CONFIG.get('use_engulfing', True)` | `core/analyzer/signal_generator.py:211` |
| 6 | `use_hammer` | Boolean | Activer pattern Hammer | ✅ `TRADING_CONFIG.get('use_hammer', True)` | `core/analyzer/signal_generator.py:211` |
| 7 | `use_shooting_star` | Boolean | Activer pattern Shooting Star | ✅ `TRADING_CONFIG.get('use_shooting_star', True)` | `core/analyzer/signal_generator.py:211` |
| 8 | `use_doji` | Boolean | Activer pattern Doji | ✅ `TRADING_CONFIG.get('use_doji', True)` | `core/analyzer/signal_generator.py:211` |
| 9 | `use_marubozu` | Boolean | Activer pattern Marubozu | ✅ `TRADING_CONFIG.get('use_marubozu', True)` | `core/analyzer/signal_generator.py:211` |
| 10 | `use_morning_star` | Boolean | Activer pattern Morning Star | ✅ `TRADING_CONFIG.get('use_morning_star', True)` | `core/analyzer/signal_generator.py:211` |
| 11 | `use_evening_star` | Boolean | Activer pattern Evening Star | ✅ `TRADING_CONFIG.get('use_evening_star', True)` | `core/analyzer/signal_generator.py:211` |

**✅ Tous les patterns de bougies sont maintenant lus dynamiquement depuis TRADING_CONFIG via un mapping dans `check_pattern_condition()`.**

---

## 📈 CATÉGORIE 3: Indicateurs Techniques (9 paramètres)

| # | Paramètre | Type | Plage | Description | Utilisation dynamique | Fichier(s) |
|---|-----------|------|-------|-------------|----------------------|------------|
| 12 | `snr_threshold` | Float | 0.0-1.0 | Seuil SNR minimum | ✅ `TRADING_CONFIG.get('snr_threshold', 0.3)` | `core/analyzer/filters.py:89` |
| 13 | `breakout_threshold` | Float | 0.0-1.0 | Seuil breakout (multiplicateur ATR) | ✅ `TRADING_CONFIG.get('breakout_threshold', 0.3)` | `core/analyzer/filters.py:129` |
| 14 | `wick_ratio_max` | Float | 1.0-10.0 | Ratio wick maximum (anti-manipulation) | ✅ `TRADING_CONFIG.get('wick_ratio_max', 2.5)` | `core/analyzer/filters.py:166` |
| 15 | `di_gap_min` | Float | 0.0-50.0 | Écart DI minimum requis | ✅ `TRADING_CONFIG.get('di_gap_min', 5)` | `core/analyzer/signal_generator.py:160` |
| 16 | `di_gap_adx_threshold` | Float | 0.0-100.0 | Seuil ADX pour validation DI gap | ✅ `TRADING_CONFIG.get('di_gap_adx_threshold', 25)` | `core/analyzer/signal_generator.py:161` |
| 17 | `optimal_atr_min_1m` | Float | 0.01-1.0 | ATR minimum optimal (1m) | ✅ `TRADING_CONFIG.get('optimal_atr_min_1m', ...)` | `core/analyzer/filters.py` |
| 18 | `optimal_atr_max_1m` | Float | 0.1-5.0 | ATR maximum optimal (1m) | ✅ `TRADING_CONFIG.get('optimal_atr_max_1m', ...)` | `core/analyzer/filters.py` |
| 19 | `optimal_atr_min_5m` | Float | 0.01-2.0 | ATR minimum optimal (5m) | ✅ `TRADING_CONFIG.get('optimal_atr_min_5m', ...)` | `core/analyzer/filters.py` |
| 20 | `optimal_atr_max_5m` | Float | 0.5-10.0 | ATR maximum optimal (5m) | ✅ `TRADING_CONFIG.get('optimal_atr_max_5m', ...)` | `core/analyzer/filters.py` |

**✅ Tous les indicateurs techniques sont lus dynamiquement depuis TRADING_CONFIG.**

---

## 🎯 CATÉGORIE 4: Validation Setups (3 paramètres)

| # | Paramètre | Type | Plage | Description | Utilisation dynamique | Fichier(s) |
|---|-----------|------|-------|-------------|----------------------|------------|
| 21 | `use_confluence` | Boolean | - | Activer validation confluence | ✅ `TRADING_CONFIG.get('use_confluence', False)` | `core/callbacks/scanner_loop.py:311` |
| 22 | `volume_multiplier` | Float | 0.5-2.0 | Multiplicateur volume minimum | ✅ `TRADING_CONFIG.get('volume_multiplier', 1.0)` | `main.py:1003`, `core/callbacks/scanner_loop.py:312` |
| 23 | `min_score_required` | Float | 0.0-20.0 | Score minimum requis pour trade | ✅ `TRADING_CONFIG.get('min_score_required', 7.5)` | `core/analyzer/scoring.py` (✅ FIXÉ) |
| 24 | `trend_timeframe` | String | 5m/15m/30m/1h | Timeframe pour analyse trend | ✅ `TRADING_CONFIG.get('trend_timeframe', '15m')` | `core/analyzer.py:603`, `core/callbacks/scanner_loop.py:313` |

**✅ Tous les paramètres de validation sont lus dynamiquement depuis TRADING_CONFIG.**

---

## 💰 CATÉGORIE 5: Money Management (2 paramètres)

| # | Paramètre | Type | Plage | Description | Utilisation dynamique | Fichier(s) |
|---|-----------|------|-------|-------------|----------------------|------------|
| 25 | `account_size` | Float | 100.0-100000.0 | Taille du compte (USDT) | ✅ `TRADING_CONFIG.get('account_size', 1000.0)` | `core/callbacks/scanner_loop.py:213` |
| 26 | `risk_per_trade` | Float | 0.1-10.0 | Risque par trade (%) | ✅ `TRADING_CONFIG.get('risk_per_trade', 2.0)` | `core/position_manager.py:404` |

**✅ `risk_per_trade` est maintenant lu dynamiquement depuis TRADING_CONFIG dans `calculate_position_size()`.**

---

## 🎯 CATÉGORIE 6: TP/SL Mode (1 paramètre)

| # | Paramètre | Type | Valeurs | Description | Utilisation dynamique | Fichier(s) |
|---|-----------|------|---------|-------------|----------------------|------------|
| 27 | `tp_sl_mode` | String | FIXE/ATR/TP_MULTI | Mode de calcul TP/SL | ✅ `TRADING_CONFIG.get('tp_sl_mode', 'FIXE')` | `core/callbacks/position_check_loop.py:234`, `core/analyzer/market_data.py:48` |

**✅ Mode TP/SL est lu dynamiquement depuis TRADING_CONFIG.**

---

## 📊 CATÉGORIE 7: Mode FIXE (3 paramètres)

| # | Paramètre | Type | Plage | Description | Utilisation dynamique | Fichier(s) |
|---|-----------|------|-------|-------------|----------------------|------------|
| 28 | `tp_percent` | Float | 0.05-5.0 | Take Profit (%) | ✅ `TRADING_CONFIG.get('tp_percent', 0.25)` → `position_config.fixed_tp_pct` | `main.py:599, 1662` |
| 29 | `sl_percent` | Float | 0.05-5.0 | Stop Loss (%) | ✅ `TRADING_CONFIG.get('sl_percent', ...)` → `position_config.fixed_sl_pct` | `main.py:1664` |
| 30 | `partial_tp_percent` | Float | 0-100 | Pourcentage TP partiel | ✅ `TRADING_CONFIG.get('partial_tp_percent', 50.0)` | `core/position/partial_tp_manager.py:63` |

**✅ TP/SL FIXE et TP partiel sont lus dynamiquement depuis TRADING_CONFIG.**

---

## 📈 CATÉGORIE 8: Mode ATR (4 paramètres)

| # | Paramètre | Type | Plage | Description | Utilisation dynamique | Fichier(s) |
|---|-----------|------|-------|-------------|----------------------|------------|
| 31 | `atr_mult_tp` | Float | 0.5-5.0 | Multiplicateur ATR pour TP | ✅ `TRADING_CONFIG.get('atr_mult_tp', 1.5)` | `core/position_manager.py:313` |
| 32 | `atr_mult_sl` | Float | 0.5-3.0 | Multiplicateur ATR pour SL | ✅ `TRADING_CONFIG.get('atr_mult_sl', 1.0)` | `core/position_manager.py:314` |
| 33 | `atr_min` | Float | 0.05-1.0 | ATR minimum (%) | ✅ `TRADING_CONFIG.get('atr_min', 0.15)` | `core/position_manager.py:315` |
| 34 | `atr_max` | Float | 0.5-5.0 | ATR maximum (%) | ✅ `TRADING_CONFIG.get('atr_max', 1.5)` | `core/position_manager.py:316` |

**✅ Tous les paramètres ATR sont lus dynamiquement depuis TRADING_CONFIG dans `position_manager.py.open_position()`.**

---

## 🪜 CATÉGORIE 9: Mode ESCALIER (TP_MULTI) - 8 paramètres

| # | Paramètre | Type | Plage | Description | Utilisation dynamique | Fichier(s) |
|---|-----------|------|-------|-------------|----------------------|------------|
| 35 | `escalier_level1_pnl` | Float | 0.1-2.0 | PnL cible niveau 1 (%) | ✅ `TRADING_CONFIG.get('escalier_level1_pnl', 0.2)` | `core/position_manager.py:356` |
| 36 | `escalier_level1_size` | Float | 0-100 | Taille à vendre niveau 1 (%) | ✅ `TRADING_CONFIG.get('escalier_level1_size', 25.0)` | `core/position_manager.py:357` |
| 37 | `escalier_level2_pnl` | Float | 0.1-2.0 | PnL cible niveau 2 (%) | ✅ `TRADING_CONFIG.get('escalier_level2_pnl', 0.2)` | `core/position_manager.py:356` |
| 38 | `escalier_level2_size` | Float | 0-100 | Taille à vendre niveau 2 (%) | ✅ `TRADING_CONFIG.get('escalier_level2_size', 25.0)` | `core/position_manager.py:357` |
| 39 | `escalier_level3_pnl` | Float | 0.1-2.0 | PnL cible niveau 3 (%) | ✅ `TRADING_CONFIG.get('escalier_level3_pnl', 0.2)` | `core/position_manager.py:356` |
| 40 | `escalier_level3_size` | Float | 0-100 | Taille à vendre niveau 3 (%) | ✅ `TRADING_CONFIG.get('escalier_level3_size', 25.0)` | `core/position_manager.py:357` |
| 41 | `escalier_level4_pnl` | Float | 0.1-3.0 | PnL cible niveau 4 (%) | ✅ `TRADING_CONFIG.get('escalier_level4_pnl', 0.2)` | `core/position_manager.py:356` |
| 42 | `escalier_level4_size` | Float | 0-100 | Taille à vendre niveau 4 (%) | ✅ `TRADING_CONFIG.get('escalier_level4_size', 25.0)` | `core/position_manager.py:357` |

**✅ Tous les paramètres escalier sont lus dynamiquement depuis TRADING_CONFIG lors de l'initialisation TP Escalier dans `position_manager.py.open_position()`.**

---

## 🎯 CATÉGORIE 10: Trailing Stop Adaptatif (5 paramètres)

| # | Paramètre | Type | Plage | Description | Utilisation dynamique | Fichier(s) |
|---|-----------|------|-------|-------------|----------------------|------------|
| 43 | `trailing_enabled` | Boolean | - | Activer trailing stop | ✅ `TRADING_CONFIG.get('trailing_enabled', True)` | `core/position_manager.py:233` |
| 44 | `trailing_trigger_pnl` | Float | 0.1-3.0 | PnL déclenchement trailing (%) | ✅ `TRADING_CONFIG.get('trailing_trigger_pnl', 0.25)` | `core/position_manager.py:234` |
| 45 | `trailing_atr_multiplier` | Float | 0.1-2.0 | Multiplicateur ATR pour distance trailing | ✅ `TRADING_CONFIG.get('trailing_atr_multiplier', 0.4)` | `core/position_manager.py:235` |
| 46 | `trailing_min_distance` | Float | 0.05-0.5 | Distance minimale trailing (%) | ✅ `TRADING_CONFIG.get('trailing_min_distance', 0.08)` | `core/position_manager.py:236` |
| 47 | `trailing_max_distance` | Float | 0.1-2.0 | Distance maximale trailing (%) | ✅ `TRADING_CONFIG.get('trailing_max_distance', 0.25)` | `core/position_manager.py:237` |

**✅ Tous les paramètres trailing stop sont lus dynamiquement depuis TRADING_CONFIG dans `position_manager.py._init_modules()`.**

---

## 📝 RÉSUMÉ

- **Total paramètres**: 47
- **✅ Lus dynamiquement**: **47 paramètres** (100%)
- **✅ Tous les paramètres sont maintenant lus depuis TRADING_CONFIG**

### ✅ Corrections effectuées:

1. **✅ Patterns Techniques & Bougies** (11 paramètres): 
   - `use_breakout`, `use_snr`, `use_wick` vérifiés dans `filters.py`
   - `use_divergence` vérifié dans `scoring.py`
   - `use_engulfing`, `use_hammer`, `use_shooting_star`, `use_doji`, `use_marubozu`, `use_morning_star`, `use_evening_star` vérifiés dans `signal_generator.py`

2. **✅ Mode ATR** (4 paramètres): 
   - `atr_mult_tp`, `atr_mult_sl`, `atr_min`, `atr_max` lus depuis `TRADING_CONFIG` dans `position_manager.py` lors de l'ouverture de position

3. **✅ Mode ESCALIER** (8 paramètres): 
   - `escalier_level1_pnl`, `escalier_level1_size`, `escalier_level2_pnl`, `escalier_level2_size`, `escalier_level3_pnl`, `escalier_level3_size`, `escalier_level4_pnl`, `escalier_level4_size` lus depuis `TRADING_CONFIG` lors de l'initialisation TP Escalier dans `position_manager.py`

4. **✅ Trailing Stop** (5 paramètres): 
   - `trailing_enabled`, `trailing_trigger_pnl`, `trailing_atr_multiplier`, `trailing_min_distance`, `trailing_max_distance` lus depuis `TRADING_CONFIG` dans `position_manager.py._init_modules()`

5. **✅ Money Management** (1 paramètre): 
   - `risk_per_trade` lu depuis `TRADING_CONFIG` dans `position_manager.py.calculate_position_size()`

6. **✅ TP Partiel** (1 paramètre): 
   - `partial_tp_percent` lu depuis `TRADING_CONFIG` dans `partial_tp_manager.py.execute_partial_tp()`

---

## ✅ CONFIRMATION FINALE

Tous les 47 paramètres sont:
- ✅ Sauvegardés dans `config_overrides.json` via `config_manager.update_config()`
- ✅ Mis à jour dans `TRADING_CONFIG` en mémoire via `TRADING_CONFIG.update(validated_updates)`
- ✅ **Lus dynamiquement depuis TRADING_CONFIG dans tous les modules**

**Tous les paramètres sont maintenant fonctionnels et pris en compte à la volée** ✅

