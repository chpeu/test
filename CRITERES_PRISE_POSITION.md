# 📊 CRITÈRES & PARAMÈTRES PRISE DE POSITION

**Trade Cursor v6.0 - Détaillé**

---

## 🎯 RÉSUMÉ GLOBAL

**7 conditions** techniques + filtres de qualité + tolérance dynamique

---

## ✅ FILTRES PRÉLIMINAIRES (Bloquants)

### **1. Volatilité ATR** ⭐⭐⭐⭐⭐
**Bloquant**: Si ATR hors plage optimale

| Timeframe | ATR Min | ATR Max | Rationale |
|-----------|---------|---------|-----------|
| **1m** | 0.15% | 0.8% | Plus permissif |
| **5m** | 0.3% | 1.5% | Plus strict |

**Exemple**:
```
1m ATR: 0.10% → ❌ REJETÉ (trop bas)
5m ATR: 1.8% → ❌ REJETÉ (trop élevé)
```

---

### **2. Volume Spike** ⭐⭐⭐⭐⭐
**Bloquant**: Si volume insuffisant

**Calcul adaptatif**:
```python
# Base selon ATR
ATR > 1.0%: min_vol = 1.0x
ATR < 0.3%: min_vol = 0.6x  
Sinon: min_vol = 0.8x

# Appliquer volume_multiplier (slider 0.10-2.00)
final_vol = min_vol × volume_multiplier
```

**Bonus**:
- Volume > 1.5x: Bonus signal "Vol >>"

---

### **3. Micro-Range Filter** ⭐⭐⭐⭐⭐
**Bloquant**: Si bougie trop plate

```python
min_range = max(0.0003%, min(0.003%, ATR × 0.2))
candle_range = (high - low) / close × 100

Si candle_range < min_range → ❌ REJETÉ
```

**Protège** contre les faux signaux sur marchés calmes.

---

### **4. Volume Quality** ⭐⭐⭐⭐⭐
**Bloquant**: Quality < 75%

**Critères**:
- Cohérence Volume/ATR (penalty -20 si incohérent)
- Liquidité 24h (penalty -15 si < 1M USDT)

**Minimum**: 75% pour accepter le trade.

---

### **5. Cohérence EMA/MACD** ⭐⭐⭐⭐⭐
**Bloquant**: Contraire flagrant

```python
# LONG
Si EMA9 > EMA21 ET MACD hist ≤ -0.001 → ❌ REJETÉ

# SHORT
Si EMA9 < EMA21 ET MACD hist ≥ 0.001 → ❌ REJETÉ
```

---

## 📋 CONDITIONS TECHNIQUES (7 points)

### **Condition 1: EMAs**
**Calcul**: EMA9 vs EMA21

**LONG**:
- ✅ EMA9 > EMA21
- ✅ Écart > 0.05%

**SHORT**:
- ✅ EMA9 < EMA21
- ✅ Écart > 0.05%

---

### **Condition 2: RSI**
**Calcul**: RSI 14

**LONG**:
- ✅ **Rebound**: RSI 30-40 + ADX < 20 + RSI↑
- ✅ **Pullback**: RSI 45-55 + MACD+ + ADX > 25 + RSI↑

**SHORT**:
- ✅ **Overbought**: RSI 60-70 + ADX < 20 + RSI↓
- ✅ **Rejection**: RSI 45-55 + MACD- + ADX > 25 + RSI↓

---

### **Condition 3: Volume**
**Calcul**: Volume spike adaptatif

**LONG**:
- ✅ Volume > `min_vol_ratio` (adaptatif)
- ✅ Bonus: Volume > 1.5x

**SHORT**:
- ✅ Volume > `min_vol_ratio` (adaptatif)
- ✅ Bonus: Volume > 1.5x

---

### **Condition 4: MACD**
**Calcul**: MACD 3/10/16

**LONG**:
- ✅ MACD > Signal OU Histogramme > 0
- ✅ Bonus: Histogramme↑ (momentum)

**SHORT**:
- ✅ MACD < Signal OU Histogramme < 0
- ✅ Bonus: Histogramme↓ (momentum)

---

### **Condition 5: Bollinger Bands**
**Calcul**: BB 20, déviation 2

**LONG**:
- ✅ Prix proche bande inférieure
- ✅ Distance < `max(0.3%, ATR × 0.5)`

**SHORT**:
- ✅ Prix proche bande supérieure
- ✅ Distance < `max(0.3%, ATR × 0.5)`

---

### **Condition 6: ADX**
**Calcul**: ADX 14

**LONG**:
- ✅ ADX > 30
- ✅ DI+ > DI-

**SHORT**:
- ✅ ADX > 30
- ✅ DI- > DI+

---

### **Condition 7: Pattern**
**Détection**: Chandelier

**LONG**:
- ✅ Engulfing Bullish
- ✅ Hammer

**SHORT**:
- ✅ Engulfing Bearish
- ✅ Shooting Star

---

## ⚖️ TOLÉRANCE DYNAMIQUE

### **Basée sur ADX**

**Calcul conditions minimales**:
```python
Si ADX > 30:     min_conditions = 5   ✅ (Permissif)
Si ADX 25-30:    min_conditions = 5.5 ✅ (Zone grise)
Si ADX < 25:     min_conditions = 6   ✅ (Strict)
```

**Logique**: Marché tendu → moins de conditions requises.

---

## 🎁 BONUS

### **Bonus Trend**
Si tendance alignée:
```
Bonus = floor(trend_bonus / 10)
Conditions = conditions_natives + bonus
```

**Exemple**: Trend bonus 85 → +8 conditions virtuelles.

---

## 🔗 CONFLUENCE MULTI-TIMEFRAME

### **Mode Permissif** (par défaut)
- ✅ 1m OU 5m validé → OK
- ✅ Priorité: Timeframe avec le plus de conditions

### **Mode Strict** (Confluence)
- ✅ 1m ET 5m validés → OK
- ✅ Même direction
- ✅ 5m force ≥ 80% de 1m force

---

## 🚫 ORDRE DE FILTRAGE

```
Paire → Check Scalabilité → Check ATR → Check Volume 
  → Check Micro-Range → Calculate 7 Conditions 
    → Check Tolérance Dynamique → Check Volume Quality 
      → Check Cohérence EMA/MACD → OK!
```

---

## 📊 CONFIGURATION PAR DÉFAUT

**Fichier**: `config.py`

```python
# TP/SL
tp_sl_mode = "FIXE"  # ou "ATR"
tp_percent = 0.25%   # +0.25%
sl_percent = 0.25%   # -0.25%

# Break-even & Trailing
break_even_trigger = 0.3%   # Activation BE
trailing_distance = 0.1%    # Distance trailing

# Volume
volume_multiplier = 1.0     # Slider 0.10-2.00

# ATR Optimal
optimal_atr_min_1m = 0.15%
optimal_atr_max_1m = 0.8%
optimal_atr_min_5m = 0.3%
optimal_atr_max_5m = 1.5%

# Confluence
use_confluence = False  # False = OU, True = ET

# Fees
fee_per_trade = 0.04%

# Intervals
scan_interval = 45s      # Position scan
scalability_interval = 90s  # Scalability scan
check_interval = 2s      # Position check
```

---

## 🎯 EXEMPLE CONCRET

### **LONG Setup Validé**:

```
✅ Scalabilité: OK (score > 70%)
✅ ATR 1m: 0.45% (ok, 0.15-0.8%)
✅ Volume: 1.2x (ok, > 0.8x)
✅ Micro-range: 0.08% (ok, > 0.009%)

Conditions:
  ✅ EMAs Up (0.12%)
  ✅ RSI Rebound↑ (35, ADX<18)
  ✅ Vol >1.0x
  ✅ MACD+↑ (momentum)
  ✅ BB Lower
  ✅ ADX+ (>32)
  ❌ Pattern (aucun)

Total: 6/7 conditions
ADX: 32 > 30 → min = 5
Résultat: LONG VALIDÉ ✅
```

---

## 📈 POSITION SIZING

**Calcul adaptatif**:

**Base**: 2% de risque

**Multiplicateurs**:
- **7 conditions**: ×1.5 (risque 3%)
- **6 conditions**: ×1.2 (risque 2.4%)
- **5 conditions**: ×0.8 (risque 1.6%)
- **<5 conditions**: ×0.5 (risque 1%)

**Volatilité**:
- ATR > 2%: ×0.7 (réduire)
- ATR < 0.5%: ×1.3 (augmenter)

**Final**: 
```
position_size = (account × risk_final) / (stop_loss_percent)
```

---

## ⚠️ PROTECTION

### **Consecutive Loss**
```
Si 2 pertes consécutives sur même paire:
  → Blocage 15 minutes
```

---

## 🎯 RÉSUMÉ ULTRA-SYNTHÉTIQUE

**Pour ouvrir une position**:
1. ✅ Paire scalable (top 20)
2. ✅ ATR optimal (0.15-0.8% ou 0.3-1.5%)
3. ✅ Volume spike adaptatif
4. ✅ Pas de bougie plate
5. ✅ **5-6 conditions sur 7** (selon ADX)
6. ✅ Volume quality ≥ 75%
7. ✅ Cohérence EMA/MACD
8. ✅ Confluence OK (1m OU 5m)

**C'est TOUT!**

---

**Documentation complète**: Voir `core/analyzer.py` et `config.py`





