# 📚 EXPLICATION COMPLÈTE: MODE TP/SL ATR

**Date**: 2025-11-02  
**Version**: Trade Cursor v6.0  
**Auteur**: Assistant IA

---

## 🎯 OBJECTIF DU MODE ATR

**Problème du mode FIXE**:
- TP/SL fixes (ex: +0.25% / -0.25%)
- Ne s'adapte pas à la volatilité du marché
- Sur BTC calme: TP trop serré → Sortie prématurée
- Sur altcoin volatile: SL trop large → Perte importante

**Solution mode ATR**:
- TP/SL adaptés à la volatilité intrinsèque de chaque paire
- Calcul basé sur l'**Average True Range (ATR)**
- Plus de fakeouts, meilleur R:R

---

## 📊 CALCUL DE L'ATR

### **1. True Range (TR)**

**Définition**: Plus grand écart entre 3 distances possibles

```
TR = max(
    High - Low,                           # Distance intrabar
    abs(High - Close_prev),              # Gap haussier
    abs(Low - Close_prev)                # Gap baissier
)
```

**Exemple** (BTC 1min):
```
Bougie actuelle: H=100020, L=100000, C=100015
Bougie précédente: C_prev=100010

TR = max(
    100020 - 100000 = 20,
    abs(100020 - 100010) = 10,
    abs(100000 - 100010) = 10
) = 20
```

---

### **2. Average True Range (ATR)**

**Définition**: Moyenne des 14 derniers True Ranges

```
ATR = (TR1 + TR2 + ... + TR14) / 14
```

**Exemple**:
```
TR sur 14 bougies: [20, 15, 25, 30, 18, 22, 28, 16, 24, 26, 20, 19, 27, 23]

ATR = (20 + 15 + 25 + 30 + 18 + 22 + 28 + 16 + 24 + 26 + 20 + 19 + 27 + 23) / 14
    = 323 / 14
    = 23.07 USDT
```

---

### **3. ATR Multi-Timeframe (v4.3)**

**Formule**:
```
ATR_blended = (ATR_1m × 0.7) + (ATR_5m × 0.3)
```

**Pourquoi?**: Mix court terme (1m) + tendance (5m)

**Exemple**:
```
ATR_1m = 23.07 USDT
ATR_5m = 65.00 USDT

ATR_blended = (23.07 × 0.7) + (65.00 × 0.3)
            = 16.15 + 19.50
            = 35.65 USDT
```

---

### **4. ATR en Pourcentage**

**Formule**:
```
ATR_percent = (ATR_blended / Entry_Price) × 100
```

**Exemple**:
```
Entry = 100000 USDT
ATR_blended = 35.65 USDT

ATR_percent = (35.65 / 100000) × 100
            = 0.03565%
```

---

## 🔒 CLAMP ATR (v5.1)

**Objectif**: Éviter TP/SL extrêmes (trop serrés ou trop larges)

**Plage**: `0.15% ≤ ATR_percent ≤ 1.5%`

**Exemple**:
```
ATR_percent = 0.10% → Clamp à 0.15%
ATR_percent = 2.00% → Clamp à 1.5%
```

**Pourquoi?**:
- ATR < 0.15%: Marché trop calme → Risque faux signaux
- ATR > 1.5%: Marché trop volatil → Risque perte importante

---

## ⚙️ MULTIPLICATEURS ATR

### **Multiplicateurs de Base**

**Stop-Loss**: `SL_mult = 1.5× ATR`  
**Take-Profit**: `TP_mult = 3.0× ATR`

**Exemple**:
```
ATR_percent = 0.50%

SL = Entry × (1 - 0.50% × 1.5) = Entry × 99.25%
TP = Entry × (1 + 0.50% × 3.0) = Entry × 101.50%

Si Entry = 100000 USDT:
SL = 99250 USDT (-0.75%)
TP = 101500 USDT (+1.50%)
```

**Ratio R:R**: `1.5 : 3.0 = 1:2` (classique)

---

### **Ajustement Dynamique (v5.0)**

**Wins ≥ 3** (agressif):
```
TP_mult = 4.0× ATR
SL_mult = 1.2× ATR

Ratio R:R = 1.2 : 4.0 = 1:3.33
```

**Losses ≥ 2** (prudent):
```
TP_mult = 1.5× ATR
SL_mult = 1.2× ATR

Ratio R:R = 1.2 : 1.5 = 1:1.25
```

**Normal**:
```
TP_mult = 3.0× ATR
SL_mult = 1.5× ATR

Ratio R:R = 1.5 : 3.0 = 1:2.0
```

---

## 🛡️ BREAK-EVEN PROGRESSIF

**Objectif**: Sécuriser progressivement les profits

### **Phase 1: Lock 50%** (à 50% de l'ATR)

**Condition**: `PnL ≥ ATR_percent × 0.5`

**Action**:
```
SL_new = Entry + (CurrentPrice - Entry) × 0.5
```

**Exemple LONG**:
```
Entry = 100000 USDT
CurrentPrice = 100500 USDT (+0.50%)
ATR_percent = 1.00%

PnL = +0.50%
Seuil Phase 1 = 1.00% × 0.5 = 0.50% ✅

SL_new = 100000 + (100500 - 100000) × 0.5
       = 100000 + 250
       = 100250 USDT (+0.25%)
```

---

### **Phase 2: BE Total** (à 100% de l'ATR)

**Condition**: `PnL ≥ ATR_percent × 1.0` ET Phase 1 déclenchée

**Action**:
```
SL_new = Entry
```

**Exemple LONG**:
```
Entry = 100000 USDT
CurrentPrice = 101000 USDT (+1.00%)
ATR_percent = 1.00%

PnL = +1.00%
Seuil Phase 2 = 1.00% × 1.0 = 1.00% ✅

SL_new = 100000 USDT (BE total)
```

---

## 📈 EXEMPLE COMPLET (MODE ATR)

### **Setup**
```
Paire: BTC_USDT
Entry: 100000 USDT
Direction: LONG
ATR_1m: 35.65 USDT
ATR_5m: 65.00 USDT
Wins: 0
Losses: 0
```

---

### **Étape 1: Calcul ATR Multi-TF**

```
ATR_blended = (35.65 × 0.7) + (65.00 × 0.3)
            = 35.65 USDT

ATR_percent = (35.65 / 100000) × 100
            = 0.03565% (trop bas!)
```

---

### **Étape 2: Clamp**

```
ATR_percent < 0.15% → Clamp à 0.15%
```

---

### **Étape 3: Multiplicateurs**

```
TP_mult = 3.0
SL_mult = 1.5
```

---

### **Étape 4: Calcul TP/SL**

```
SL = 100000 × (1 - 0.15% × 1.5)
   = 100000 × 0.99775
   = 99775 USDT (-0.225%)

TP = 100000 × (1 + 0.15% × 3.0)
   = 100000 × 1.0045
   = 100450 USDT (+0.45%)
```

---

### **Étape 5: Gestion Break-Even**

**T+1min**: Prix monte à 100075 USDT
```
PnL = +0.075%
Seuil Phase 1 = 0.15% × 0.5 = 0.075% ✅

SL_new = 100000 + (100075 - 100000) × 0.5
       = 100037.5 USDT
```

**T+2min**: Prix monte à 100150 USDT
```
PnL = +0.15%
Seuil Phase 2 = 0.15% × 1.0 = 0.15% ✅

SL_new = 100000 USDT (BE total)
```

**T+3min**: Prix monte à 100450 USDT
```
Prix = TP → FERMETURE
Profit = +0.45%
```

---

## ⚖️ COMPARAISON FIXE vs ATR

### **BTC_USDT (marché calme)**
| Mode | SL | TP | Ratio R:R |
|------|----|----|-----------|
| **FIXE** | -0.25% | +0.25% | 1:1 |
| **ATR** | -0.225% | +0.45% | **1:2** ✅ |

---

### **ALTCOIN (marché volatil)**
| Mode | SL | TP | Ratio R:R |
|------|----|----|-----------|
| **FIXE** | -0.25% | +0.25% | 1:1 |
| **ATR** | -0.60% | +1.80% | **1:3** ✅ |

---

## 🎯 SCÉNARIOS RÉELS

### **Scénario 1: Marché calme (ATR 0.15%)**

**Setup**:
```
Entry: 100000
ATR: 0.15%
TP_mult: 3.0
SL_mult: 1.5

SL: 99775 (-0.225%)
TP: 100450 (+0.45%)
```

**Progression**:
```
T+0s:  Entry 100000 → PnL 0.00%
T+30s: Prix 100037 → PnL +0.037% → BE Phase 1
T+1min: Prix 100075 → SL 100037 (+0.037% lock)
T+2min: Prix 100150 → PnL +0.15% → BE Total
T+2min: Prix 100150 → SL 100000 (BE total)
T+3min: Prix 100450 → TP → +0.45%
```

---

### **Scénario 2: Marché volatil (ATR 0.80%)**

**Setup**:
```
Entry: 100000
ATR: 0.80%
TP_mult: 3.0
SL_mult: 1.5

SL: 98800 (-1.20%)
TP: 102400 (+2.40%)
```

**Progression**:
```
T+0s:  Entry 100000 → PnL 0.00%
T+1min: Prix 100400 → PnL +0.40% → BE Phase 1
T+1min: Prix 100400 → SL 100200 (+0.20% lock)
T+2min: Prix 100800 → PnL +0.80% → BE Total
T+2min: Prix 100800 → SL 100000 (BE total)
T+4min: Prix 102400 → TP → +2.40%
```

---

### **Scénario 3: Win Streak (≥3)**

**Setup**:
```
Entry: 100000
ATR: 0.50%
Wins: 4

TP_mult: 4.0 (agressif)
SL_mult: 1.2 (serré)

SL: 99400 (-0.60%)
TP: 102000 (+2.00%)
```

**Ratio R:R**: `1:3.33` (très favorable)

---

### **Scénario 4: Loss Streak (≥2)**

**Setup**:
```
Entry: 100000
ATR: 0.50%
Losses: 3

TP_mult: 1.5 (conservateur)
SL_mult: 1.2 (serré)

SL: 99400 (-0.60%)
TP: 100750 (+0.75%)
```

**Ratio R:R**: `1:1.25` (prudent)

---

## 🔍 CLÉS DE COMPRÉHENSION

### **1. ATR représente la volatilité**
- ATR faible = marché calme → TP/SL serrés
- ATR élevé = marché volatile → TP/SL larges

### **2. Multiplicateurs basiques**
- **TP 3× ATR**: Profit cible raisonnable
- **SL 1.5× ATR**: Protection du capital

### **3. Break-even progressif**
- **Phase 1** (50% ATR): Sécurise 25% des profits
- **Phase 2** (100% ATR): Garantit le capital

### **4. Ajustement dynamique**
- **Wins ≥ 3**: Plus agressif → Maximiser gains
- **Losses ≥ 2**: Plus prudent → Protéger le capital

---

## ⚙️ CONFIGURATION

**Fichier**: `core/position_manager.py`

```python
@dataclass
class PositionConfig:
    # Mode
    use_atr: bool = False  # True = ATR, False = FIXE
    
    # TP/SL ATR multipliers
    atr_mult_tp: float = 3.0
    atr_mult_sl: float = 1.5
    atr_min: float = 0.15   # Clamp min
    atr_max: float = 1.5    # Clamp max
    
    # Break-even progressif (ATR mode)
    be_atr_factor: float = 1.5
```

---

**Status**: ✅ **DOCUMENTATION COMPLÈTE**  
**Git**: `bb9ed70` (v6.4.3)






