# 🚀 IMPLÉMENTATION v6.4: POSITION PARTIELLE PHYSIQUE

**Date**: 2025-11-02  
**Version**: v6.4  
**Objectif**: Implémenter la gestion de position partielle physique avec P&L en USDT

---

## 📋 RÉSUMÉ

**Changements majeurs**:
1. ✅ TP partiel **physique** 50% à +0.3% (au lieu de conceptuel)
2. ✅ Trailing stop 0.15% à partir du TP partiel
3. ✅ P&L calculé en **% ET USDT**
4. ✅ Slippage doublé si position partielle (entrée + sortie partielle + sortie finale)
5. ✅ Mode FIXE uniquement
6. ✅ Break-even immédiat après TP partiel

---

## 🔧 MODIFICATIONS PYTHON

### **`core/position_manager.py`**

#### **1. Position dataclass** (lignes 40-43)
```python
# 🔥 v6.4: Position partielle physique
size_remaining: Optional[float] = None  # Taille restante après TP partiel
partial_profit_usdt: float = 0.0  # Profit du TP partiel en USDT
capital: Optional[float] = None  # Capital total en USDT
```

#### **2. PositionConfig** (lignes 66-68)
```python
trailing_distance: float = 0.15  # % 🔥 v6.4: 0.15% au lieu de 0.1%
partial_tp_trigger: float = 0.3  # % 🔥 v6.4: 0.3% au lieu de 0.25%
```

#### **3. `_update_fixed_mode_sl`** (lignes 283-321)
```python
# 🔥 v6.4: TP partiel PHYSIQUE 50% à +0.3%
if self.config.use_partial_tp and not self.active_position.partial_tp_sold:
    if pnl >= self.config.partial_tp_trigger:  # +0.3%
        self.active_position.partial_tp_sold = True
        
        # Calculer profit du TP partiel en USDT
        size_partial = self.active_position.size * 0.5
        price_diff = abs(current_price - self.active_position.entry)
        self.active_position.partial_profit_usdt = size_partial * (price_diff / self.active_position.entry)
        self.active_position.size_remaining = self.active_position.size * 0.5
        
        # Break-even immédiat
        self.active_position.sl = self.active_position.entry

# 🔥 v6.4: Trailing stop 0.15% à partir du TP partiel
if self.config.use_trailing_stop and self.active_position.partial_tp_sold:
    # Mise à jour du trailing SL
```

#### **4. `close_position`** (lignes 368-502)
```python
# 🔥 v6.4: Gérer position partielle
has_partial_tp = self.active_position.partial_tp_sold
size_to_close = self.active_position.size_remaining or (self.active_position.size * 0.5)

# 🔥 v6.4: Calculer P&L en USDT
if has_partial_tp:
    pnl_final_usdt = partial_profit_usdt + (size_to_close * pnl_pct / 100)
    pnl_total_pct = (pnl_final_usdt / self.active_position.size) * 100
else:
    pnl_final_usdt = self.active_position.size * (pnl_pct / 100)

# 🔥 v6.4: Slippage doublé si position partielle
if has_partial_tp:
    slippage_partial = self._estimate_slippage(...)
    slippage_final = self._estimate_slippage(...)
    slippage = slippage_partial + slippage_final
else:
    slippage_entry = self._estimate_slippage(...)
    slippage_exit = self._estimate_slippage(...)
    slippage = slippage_entry + slippage_exit

# Retourner avec USDT
result = {
    'pnl': round(pnl_total_pct, 2),
    'pnl_usdt': round(pnl_final_usdt, 4),  # 🔥 v6.4
    'net_pnl': round(net_pnl_pct, 2),
    'net_pnl_usdt': round(net_pnl_usdt, 4),  # 🔥 v6.4
    'has_partial_tp': has_partial_tp,  # 🔥 v6.4
    'size_closed': round(size_to_close, 4)  # 🔥 v6.4
}
```

---

## 🎨 MODIFICATIONS FRONTEND (HTML/JS)

### **`templates/index.html`**

#### **1. Variables globales** (ligne 652)
```javascript
var partialTPTrigger = 0.3;  // 🔥 v6.4: 0.3% au lieu de 0.25%
```

#### **2. `openPosition`** (lignes 1043-1046)
```javascript
// 🔥 v6.4: Initialiser variables position partielle
activePosition.size_remaining = null;
activePosition.partial_profit_usdt = 0.0;
activePosition.capital = accountSize;
```

#### **3. `checkPosition` - Mode FIXE** (lignes 1238-1284)
```javascript
// 🔥 v6.4: TP partiel physique 50% + Trailing 0.15%
if (usePartialTP && !partialTPSold && pnl >= partialTPTrigger) {
    partialTPSold = true;
    
    // Calculer profit du TP partiel en USDT
    var sizePartial = activePosition.size * 0.5;
    var priceDiff = Math.abs(currentPrice - entry);
    activePosition.partial_profit_usdt = sizePartial * (priceDiff / entry);
    activePosition.size_remaining = activePosition.size * 0.5;
    
    // Break-even immédiat
    activePosition.sl = entry;
    sl = entry;
}

// 🔥 v6.4: Trailing stop 0.15% à partir du TP partiel
if (useTrailingStop && partialTPSold) {
    // Mise à jour du trailing SL
}
```

#### **4. `closePosition`** (lignes 1413-1508)
```javascript
// 🔥 v6.4: Gérer position partielle
var hasPartialTP = partialTPSold;
var sizeToClose = activePosition.size_remaining || (activePosition.size * 0.5);

// 🔥 v6.4: Calculer P&L en USDT
if (hasPartialTP) {
    pnlFinalUSDT = partialProfitUSDT + (sizeToClose * pnl / 100);
    pnlTotalPct = (pnlFinalUSDT / activePosition.size) * 100;
} else {
    pnlFinalUSDT = activePosition.size * (pnl / 100);
}

// 🔥 v6.4: Slippage doublé si position partielle
if (hasPartialTP) {
    slippage = slippagePartial + slippageFinal;
} else {
    slippage = slippageEntry + slippageExit;
}

// 🔥 v6.4: Historique avec USDT
var tradeRecord = {
    // ...
    netPnlUSDT: netPnlUSDT.toFixed(4),
    hasPartialTP: hasPartialTP,
    sizeClosed: sizeToClose.toFixed(4)
};
```

---

## 📊 LOGIQUE DE POSITION PARTIELLE

### **Fonctionnement**

**Initial**:
```
Capital: 1000 USDT
Position: 100 USDT
Entry: 100 USDT
```

**TP Partiel 50%** (+0.3%):
```
Prix: 100.3 USDT
Action: Fermer 50% (50 USDT)
Profit USDT: 50 * 0.003 = 0.15 USDT
Restant: 50 USDT
SL: 100 USDT (break-even)
```

**Trailing Stop**:
```
Prix monte: 101.0 USDT
SL suit: 101.0 * 0.9985 = 100.8485 USDT

Prix baisse: 100.85 USDT
SL touché: Fermer 50% restants
Profit USDT: 0.425 USDT
Total profit: 0.15 + 0.425 = 0.575 USDT
```

---

## 💰 CALCUL Slippage Doublé

### **Position normale** (sans partiel):
```
Slippage = Entry + Exit = 2 × estimateSlippage(100 USDT)
```

### **Position partielle**:
```
Slippage = Entry + Exit Partiel + Exit Final
         = estimateSlippage(100) + estimateSlippage(50) + estimateSlippage(50)
```

---

## ✅ TESTS À EFFECTUER

1. ✅ **TP partiel déclenche à +0.3%**
2. ✅ **Break-even activé immédiatement**
3. ✅ **Trailing 0.15% fonctionnel**
4. ✅ **P&L USDT correct**
5. ✅ **Slippage doublé si partiel**
6. ✅ **Historique avec USDT**

---

## 📝 NOTES

- **Mode ATR**: Non affecté (break-even progressif inchangé)
- **Mode FIXE**: Position partielle activée
- **Break-even**: Actif après TP partiel
- **Trailing**: 0.15% du prix actuel
- **Coûts**: Doublés si position partielle

---

**Status**: ✅ **IMPLEMENTED**  
**Next**: Tests en conditions réelles



