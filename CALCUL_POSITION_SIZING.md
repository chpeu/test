# 📊 CALCUL POSITION SIZING & P&L USDT

**Date**: 2025-11-02  
**Problème**: Calcul position sizing et P&L USDT incorrect

---

## ❓ CALCUL ATTENDU (utilisateur)

### **Position Sizing**
```
Capital: 1000 USDT
Risk: 2%
Position par trade = 1000 × 0.02 = 20 USDT
```

**→ Position size = Capital × Risk%**  
**→ Risk% = % du capital risqué sur ce trade**

---

## 🤔 CALCUL ACTUEL (basé sur SL)

### **Formule**
```
finalRisk = riskPerTrade × qualityMultiplier × volMultiplier
positionSize = (accountSize × finalRisk) / (stopLossPercent / 100)
```

### **Exemple**
```
Capital: 1000 USDT
Risk: 2%
SL: 0.25%

finalRisk = 0.02 × 1.0 × 1.0 = 0.02
positionSize = (1000 × 0.02) / 0.0025 = 8000 USDT  ← ÉNORME!
```

**→ Basé sur Kelly Criterion / Risk/Reward**

---

## 🔍 DIFFÉRENCE

| Approche | Formule | Résultat (1000 USDT, 2%, SL 0.25%) |
|----------|---------|-------------------------------------|
| **Simple** | Capital × Risk% | 20 USDT ✅ |
| **Kelly** | (Capital × Risk%) / (SL%) | 8000 USDT ❌ |

---

## 💡 QUELLE APPROCHE ?

### **Approche Simple (utilisateur)**
- ✅ **Clair et prévisible**
- ✅ Position size = % du capital
- ✅ Généralement 2-5% du capital

### **Approche Kelly (actuel)**
- ✅ **Optimise R/R**
- ✅ Position proportionnelle au stop-loss
- ⚠️ **Généralement trop agressive**

---

## 🎯 RECOMMANDATION

**Utiliser l'approche simple**:
```javascript
// Position size = Capital × Risk%
var positionSize = accountSize * (riskPerTrade / 100);
```

**Exemple**:
```
Capital: 1000 USDT
Risk: 2%
Position: 20 USDT
```

---

## 📊 P&L USDT

### **Position Simple**
```
Position: 20 USDT (100%)
Entry: 100 USDT
Prix: 100.3 USDT (+0.3%)

P&L USDT = Position × P&L%
         = 20 × 0.003
         = 0.06 USDT
```

### **Position Partielle**
```
TP Partiel 50%:
  Ferme: 10 USDT
  Profit: 10 × 0.003 = 0.03 USDT

50% Restants:
  Prix: 100.6 USDT (+0.6%)
  Profit: 10 × 0.006 = 0.06 USDT

Total: 0.03 + 0.06 = 0.09 USDT
```

---

**Status**: ⚠️ **BUG IDENTIFIÉ - À CORRIGER**






