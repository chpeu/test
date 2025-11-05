# 📊 EXPLICATION COMPLÈTE : TP/SL FIXE vs ATR

**Trade Cursor v6.2**  
**Gestion détaillée des Take-Profit et Stop-Loss**

---

## 🎯 RÉSUMÉ EXÉCUTIF

| Aspect | Mode FIXE | Mode ATR |
|--------|-----------|----------|
| **TP/SL** | Pourcentages fixes | Adaptés à la volatilité |
| **Break-even** | Simple (+0.3%) | Progressif (phases) |
| **TP Partiel** | ✅ Oui (50%) | ❌ Non |
| **Trailing Stop** | ✅ Oui | ❌ Non |
| **Adaptatif** | ❌ Non | ✅ Oui (streaks, volatilité) |
| **Multi-TF** | ❌ Non | ✅ Oui (1m + 5m) |
| **Complexité** | Faible | Moyenne |

---

## 1️⃣ MODE FIXE

### 📐 **Calcul initial des niveaux**

**Configuration par défaut**:
```
TP = +0.25%
SL = -0.25%
Break-even = +0.3%
Trailing = 0.1%
TP Partiel = +0.25%
```

**Formule**:
```
LONG:
  SL = entry × (1 - 0.0025) = entry × 0.9975
  TP = entry × (1 + 0.0025) = entry × 1.0025

SHORT:
  SL = entry × (1 + 0.0025) = entry × 1.0025
  TP = entry × (1 - 0.0025) = entry × 0.9975
```

**Exemple pratique**:
```
Entry: 100 USDT
TP: 100.25 USDT (+0.25%)
SL: 99.75 USDT (-0.25%)
```

---

### 🎯 **TP Partiel (phase 1)**

**Condition**: P&L >= 0.25%

**Action**:
- Marquer `partial_tp_sold = True`  
- **Aucune vente physique**
- Simule "lock" de 50% du profit  
- Log: `🎯 TP PARTIEL 50%: Profit=0.25%`

**Logique**:  
Le TP partiel est **conceptuel**. Il ne ferme pas réellement 50% de la position, mais modifie la stratégie de gestion du SL par la suite.

**Exemple**:
```
Entry: 100 USDT
Prix actuel: 100.30 USDT (+0.30%)

→ TP Partiel déclenché ✅
→ partial_tp_sold = True
→ Continue vers break-even
```

---

### 🔒 **Break-even (phase 2)**

**Conditions**:
1. P&L >= 0.3%
2. TP Partiel déjà déclenché

**Action**:
```
LONG:  SL = entry
SHORT: SL = entry
break_even_set = True
```

**Exemple**:
```
Entry: 100 USDT
Prix actuel: 100.35 USDT (+0.35%)
partial_tp_sold = True ✅

→ Break-even déclenché ✅
→ SL = 100 USDT
→ break_even_set = True
→ Zéro perte garantie
```

---

### 📈 **Trailing Stop (phase 3)**

**Conditions**:
- Break-even déjà activé
- P&L positif

**Mécanisme**:
```
LONG:
  new_sl = current_price × (1 - 0.001) = current_price × 0.999
  Si new_sl > active_sl → active_sl = new_sl

SHORT:
  new_sl = current_price × (1 + 0.001) = current_price × 1.001
  Si new_sl < active_sl → active_sl = new_sl
```

**Exemple progressif**:
```
Entry: 100 USDT
Break-even: SL = 100 USDT

Prix 100.50 → SL = 100.45
Prix 100.60 → SL = 100.54
Prix 100.40 → SL = 100.54 (verrouillé)
Prix 100.53 → TOUCHÉ SL ✅
```

---

### 🔄 **Cycle complet**

**Timeline**:
```
0.00%   Entrée
         ↓
0.25%   TP Partiel ✅ → partial_tp_sold = True
         ↓
0.30%   Break-even ✅ → SL = entry, break_even_set = True
         ↓
         Trailing Stop actif
         ↓
>0.30%  SL monte progressivement
         ↓
Soit TP touché → +0.25%
Soit SL touché → ≥0% (pas de perte)
```

---

### 💰 **Calcul P&L Net (mode FIXE)**

**Frais par trade**: 0.04% × 2 (entrée + sortie) = **0.08%**

**Scénario 1**: TP touché
```
P&L Brut:  +0.25%
Frais:     -0.08%
P&L Net:   +0.17%
```

**Scénario 2**: SL avant break-even
```
P&L Brut:  -0.25%
Frais:     -0.08%
P&L Net:   -0.33%
```

**Scénario 3**: SL après trailing
```
P&L Brut:  +0.30%
Frais:     -0.08%
P&L Net:   +0.22%
```

---

## 2️⃣ MODE ATR

### 📐 **Calcul initial des niveaux**

**Configuration par défaut**:
```
ATR Mult TP = 3.0×
ATR Mult SL = 1.5×
ATR Min = 0.15%
ATR Max = 1.5%
Multi-TF: 70% 1m + 30% 5m
```

**Étape 1**: Blending ATR Multi-Timeframe
```
Si atr5m disponible:
  atr_blended = (atr_1m × 0.7) + (atr_5m × 0.3)
Sinon:
  atr_blended = atr_1m
```

**Étape 2**: Conversion en pourcentage et clamping
```
atr_percent = (atr_blended / entry) × 100

Si atr_percent < 0.15% → atr_percent = 0.15%
Si atr_percent > 1.5%  → atr_percent = 1.5%
```

**Étape 3**: Calcul TP/SL avec multiplicateurs
```
LONG:
  SL = entry × (1 - atr_percent / 100 × 1.5)
  TP = entry × (1 + atr_percent / 100 × 3.0)

SHORT:
  SL = entry × (1 + atr_percent / 100 × 1.5)
  TP = entry × (1 - atr_percent / 100 × 3.0)
```

**Exemple concret**:
```
Entry: 100 USDT
ATR 1m: 0.20 USDT
ATR 5m: 0.25 USDT

atr_blended = (0.20 × 0.7) + (0.25 × 0.3) = 0.215 USDT
atr_percent = (0.215 / 100) × 100 = 0.215%

TP = 100 × (1 + 0.00215 × 3.0) = 100.645 USDT (+0.645%)
SL = 100 × (1 - 0.00215 × 1.5) = 99.678 USDT (-0.322%)
```

---

### ⚖️ **Gestion dynamique par streaks**

**Win Streak ≥ 3**: Agressif
```
TP Multiplier: 3.0 → 4.0
SL Multiplier: 1.5 → 1.2
Log: "⚖️ Gestion dynamique: Wins=3 | TPx=4.0 | SLx=1.2 (agressif)"
```

**Loss Streak ≥ 2**: Prudent
```
TP Multiplier: 3.0 → 1.5
SL Multiplier: 1.5 → 1.2
Log: "⚖️ Gestion dynamique: Losses=2 | TPx=1.5 | SLx=1.2 (prudent)"
```

**Exemple**:
```
Entry: 100 USDT
ATR%: 0.5%

MODE NORMAL:
  TP = +1.5% (150 pips)
  SL = -0.75% (75 pips)

MODE AGRESSIF (3 wins):
  TP = +2.0% (200 pips)
  SL = -0.6% (60 pips)

MODE PRUDENT (2 losses):
  TP = +0.75% (75 pips)
  SL = -0.6% (60 pips)
```

---

### 🛡️ **Break-even progressif**

**Mécanisme** (ATR mode):
```
Phase 1 (50% ATR):
  P&L >= atr_percent × 0.5
  → Locker 50% du profit

Phase 2 (100% ATR):
  P&L >= atr_percent
  → SL = entry (zéro perte)
```

**Formules**:
```
Phase 1 (50% ATR):
  LONG:  new_sl = entry + (current_price - entry) × 0.5
  SHORT: new_sl = entry - (entry - current_price) × 0.5

Phase 2 (100% ATR):
  SL = entry (break_even_set = True)
```

**Exemple**:
```
Entry: 100 USDT
ATR%: 0.5%

Prix 100.26 USDT (+0.26%)
→ Phase 1 déclenchée
→ SL = 100 + (100.26 - 100) × 0.5 = 100.13 USDT

Prix 100.51 USDT (+0.51%)
→ Phase 2 déclenchée
→ SL = 100 USDT (break-even)
```

---

### 🔄 **Cycle complet ATR**

**Timeline**:
```
0.00%   Entrée
         ↓
50%ATR  Phase 1 ✅ → SL = entry + 50% profit
         ↓
100%ATR Phase 2 ✅ → SL = entry (break-even)
         ↓
>100%ATR SL verrouillé à entry
         ↓
Soit TP touché → +3× ATR
Soit SL touché → 0% (pas de perte)
```

---

### 💰 **Calcul P&L Net (mode ATR)**

**Frais par trade**: 0.04% × 2 = **0.08%**

**Exemple 1**: TP touché (ATR 0.5%, normal)
```
P&L Brut:  +1.5%
Frais:     -0.08%
P&L Net:   +1.42%
```

**Exemple 2**: TP touché (mode agressif, 3 wins)
```
P&L Brut:  +2.0%
Frais:     -0.08%
P&L Net:   +1.92%
```

**Exemple 3**: SL avant break-even
```
P&L Brut:  -0.75%
Frais:     -0.08%
P&L Net:   -0.83%
```

**Exemple 4**: SL après break-even
```
P&L Brut:  0.0%
Frais:     -0.08%
P&L Net:   -0.08%
```

---

## 3️⃣ COMPARAISON DÉTAILLÉE

### 📊 **Tableau comparatif complet**

| Paramètre | FIXE | ATR |
|-----------|------|-----|
| **TP** | +0.25% fixe | 1.5-6.0% variable |
| **SL** | -0.25% fixe | -0.6% à -2.25% |
| **Risk/Reward** | 1:1 | 1:2 à 1:4 |
| **Break-even** | +0.3% | Progressif (phases) |
| **TP Partiel** | ✅ 50% | ❌ |
| **Trailing Stop** | ✅ 0.1% | ❌ |
| **Multi-TF** | ❌ | ✅ 70%/30% |
| **Adaptatif Streak** | ❌ | ✅ Wins/Losses |
| **Clamping** | ❌ | ✅ 0.15-1.5% |
| **Meilleur marché** | Calme/stable | Volatile |

---

### 🎯 **Quand utiliser FIXE**

**Avantages**:
- ✅ Simple et prévisible
- ✅ Contrôle strict du risque
- ✅ Bon pour scalping court (1-2 min)
- ✅ Trailing stop pour maximiser gains

**Inconvénients**:
- ❌ Stopped trop rapidement sur marchés volatils
- ❌ Manque de gain sur gros mouvements
- ❌ Non adapté aux altcoins volatiles

**Idéal pour**:
- BTC/ETH/USDT sur 1m
- Marchés calmes (volatilité < 0.5%)
- Trading très fréquent (20-30 trades/jour)

---

### 📈 **Quand utiliser ATR**

**Avantages**:
- ✅ Adapté à la volatilité
- ✅ Meilleur ratio R:R (1:2 à 1:4)
- ✅ Moins de faux stops
- ✅ Gestion streak intelligente

**Inconvénients**:
- ❌ Plus complexe
- ❌ SL plus large → perte potentielle plus grande
- ❌ Pas de trailing stop automatique

**Idéal pour**:
- Altcoins volatiles
- Marchés explosifs (news, breakout)
- Trading moins fréquent (10-15 trades/jour)

---

## 4️⃣ EXEMPLES COMPLETS

### 📝 **Exemple 1 : FIXE - Cycle complet**

```
SCÉNARIO: LONG BTC_USDT

Entry: 67000 USDT
TP: 67000 × 1.0025 = 67016.75 USDT
SL: 67000 × 0.9975 = 66983.25 USDT

TIMELINE:
00:00 → Prix: 67000  | P&L: 0.00%  | SL: 66983.25
00:30 → Prix: 67020  | P&L: +0.03% | SL: 66983.25
01:00 → Prix: 67025  | P&L: +0.04% | ✅ TP PARTIEL
01:30 → Prix: 67032  | P&L: +0.05% | ✅ BREAK-EVEN → SL: 67000
02:00 → Prix: 67040  | P&L: +0.06% | 📈 TRAILING → SL: 67027
02:30 → Prix: 67050  | P&L: +0.07% | 📈 TRAILING → SL: 67040
03:00 → Prix: 67045  | P&L: +0.07% | 📈 TRAILING → SL: 67040
03:30 → Prix: 67038  | P&L: +0.06% | ⚠️ SL touché

RÉSULTAT:
P&L Brut: +0.06%
Frais: -0.08%
P&L Net: -0.02% (quasi break-even)
```

---

### 📝 **Exemple 2 : ATR - Cycle complet**

```
SCÉNARIO: LONG SOL_USDT

Entry: 150 USDT
ATR 1m: 0.15 USDT
ATR 5m: 0.20 USDT

atr_blended = (0.15 × 0.7) + (0.20 × 0.3) = 0.165 USDT
atr_percent = (0.165 / 150) × 100 = 0.11%

Clamping: 0.11% < 0.15% → 0.15%

TP = 150 × (1 + 0.0015 × 3.0) = 150.675 USDT (+0.45%)
SL = 150 × (1 - 0.0015 × 1.5) = 149.6625 USDT (-0.225%)

TIMELINE:
00:00 → Prix: 150.00 | P&L: 0.00%    | SL: 149.66
01:00 → Prix: 150.08 | P&L: +0.05%   | SL: 149.66
02:00 → Prix: 150.15 | P&L: +0.10%   | SL: 149.66
03:00 → Prix: 150.22 | P&L: +0.15%   | ✅ PHASE 1 → SL: 150.11
04:00 → Prix: 150.30 | P&L: +0.20%   | SL: 150.11
05:00 → Prix: 150.23 | P&L: +0.15%   | 🛡️ BREAK-EVEN → SL: 150.00
06:00 → Prix: 150.68 | P&L: +0.45%   | ✅ TP touché

RÉSULTAT:
P&L Brut: +0.45%
Frais: -0.08%
P&L Net: +0.37%
```

---

### 📝 **Exemple 3 : ATR - Mode agressif**

```
SCÉNARIO: LONG DOGE_USDT (après 3 wins consécutifs)

Entry: 0.080 USDT
ATR%: 0.8%

GESTION DYNAMIQUE:
TP Multiplier: 3.0 → 4.0
SL Multiplier: 1.5 → 1.2

TP = 0.080 × (1 + 0.008 × 4.0) = 0.08256 USDT (+3.2%)
SL = 0.080 × (1 - 0.008 × 1.2) = 0.07923 USDT (-0.96%)

TIMELINE:
00:00 → Prix: 0.0800 | P&L: 0.00%   | SL: 0.07923
01:00 → Prix: 0.0810 | P&L: +1.25% | ✅ PHASE 1 → SL: 0.0805
02:00 → Prix: 0.0820 | P&L: +2.50% | 🛡️ BREAK-EVEN → SL: 0.0800
03:00 → Prix: 0.0826 | P&L: +3.25% | ✅ TP touché

RÉSULTAT:
P&L Brut: +3.25%
Frais: -0.08%
P&L Net: +3.17%
```

---

## 5️⃣ CALCUL DES FRAIS

### 💰 **Formule générale**

```
Frais totaux = (entry + exit) / entry × taker_fee × 100
```

**Avec**:
- `taker_fee = 0.0004` (0.04%)
- Multiplication par 100 pour %  
- Facteur (entry + exit) / entry ≈ 2

**Simplification**:
```
Frais ≈ 0.0004 × 2 × 100 = 0.08%
```

---

### 📊 **Frais par scénario**

| Scénario | P&L Brut | Frais | P&L Net |
|----------|----------|-------|---------|
| **FIXE TP** | +0.25% | -0.08% | +0.17% |
| **FIXE SL (avant BE)** | -0.25% | -0.08% | -0.33% |
| **FIXE SL (après BE)** | +0.00% | -0.08% | -0.08% |
| **ATR TP normal** | +0.45% | -0.08% | +0.37% |
| **ATR TP agressif** | +2.00% | -0.08% | +1.92% |
| **ATR SL** | -0.75% | -0.08% | -0.83% |

---

### ⚠️ **Impact des frais**

**FIXE Mode**:  
Frais = **32% du profit potentiel** (0.08% / 0.25%)  
→ Critique pour scalping fréquent

**ATR Mode**:  
Frais = **~2-18% du profit potentiel** (0.08% / TP variable)  
→ Négligeable si TP > 0.5%

**Conclusion**:  
Mode ATR plus favorable pour réduire l'impact des frais proportionnellement.

---

## 6️⃣ RÉSUMÉ ET RECOMMANDATIONS

### ✅ **Résumé**

| Aspect | FIXE | ATR |
|--------|------|-----|
| **Simplicité** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Adaptabilité** | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **R:R** | 1:1 | 1:2 à 1:4 |
| **Protection** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Scalabilité** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Idéal** | BTC/ETH | Altcoins |

---

### 🎯 **Recommandations**

**Utiliser FIXE si**:
- Trading BTC/ETH/USDT major
- Scalping très fréquent
- Volatilité faible (< 0.5%)
- Objectif: 0.2-0.3% par trade

**Utiliser ATR si**:
- Trading altcoins
- Volatilité élevée (> 0.5%)
- Trading moins fréquent
- Objectif: 0.5-2% par trade

**Changer de mode si**:
- Winrate < 60% en FIXE → Essayer ATR
- Trop de faux stops → Essayer ATR
- Pas assez de mouvement → Essayer FIXE

---

**Date**: 2025-11-02  
**Version**: v6.2  
**Document**: Explication complète TP/SL





