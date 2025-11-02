# 💰 ANALYSE : FRAIS & SLIPPAGE RÉELS

**Trade Cursor v6.2**  
**Proposition d'amélioration**

---

## 🎯 PROBLÈME ACTUEL

### **1. Situation**
```
Frais actuels = 0.04% × 2 = 0.08% par trade
Slippage = NON pris en compte
```

**Hypothèses**:
- Paires scalables = **0% fees maker/taker** ✅
- Slippage = **0%** ❌ (non réaliste)

---

## 📊 IMPACT DES FRAIS SUR LA RENTABILITÉ

### **Mode FIXE** (TP/SL = ±0.25%)
```
P&L Brut: +0.25%
Frais actuel: 0.08%
P&L Net: 0.17%  ← 68% du brut (perte de 32%)

Impact: CRITIQUE ⚠️
```

### **Mode ATR** (TP moyen ~1.0%)
```
P&L Brut: +1.0%
Frais actuel: 0.08%
P&L Net: 0.92%  ← 92% du brut (perte de 8%)

Impact: Acceptable ✅
```

**Conclusion**:  
En mode FIXE, les frais représentent 32% des gains, ce qui est problématique.

---

## 🔍 PROPOSITION : SLIPPAGE DYNAMIQUE

### **Fonction proposée**
```python
def estimate_slippage(
    order_size: float,      # Taille ordre en USDT
    bid_vol: float,         # Volume total bid (5 niveaux)
    ask_vol: float,         # Volume total ask (5 niveaux)
    spread_pct: float,      # Spread moyen en %
    balance_score: float    # Équilibre bid/ask (0-1)
) -> float:
    """
    Estime le slippage réaliste pour un ordre
    """
    # Ajuster spread selon déséquilibre
    imbalance_factor = 1 / balance_score
    
    # Ajuster selon profondeur
    depth_factor = order_size / (bid_vol + ask_vol)
    
    # Slippage estimé
    slippage_pct = spread_pct * (1 + depth_factor * imbalance_factor)
    
    return slippage_pct
```

---

## 📐 DÉTAILS DU CALCUL

### **1. Imbalance Factor**
```
balance_score = 1.0  → imbalance_factor = 1.0  (parfait)
balance_score = 0.7  → imbalance_factor = 1.43 (léger déséquilibre)
balance_score = 0.5  → imbalance_factor = 2.0  (fort déséquilibre)
```

**Logique**: Plus le déséquilibre est fort, plus le slippage est élevé.

---

### **2. Depth Factor**
```
order_size = 1000 USDT
bid_vol + ask_vol = 2000 USDT

depth_factor = 1000 / 2000 = 0.5

Si order_size << depth:
  depth_factor ≈ 0
  slippage minimal

Si order_size ≈ depth:
  depth_factor ≈ 1
  slippage maximal
```

**Logique**: Plus l'ordre est gros par rapport à la profondeur, plus le slippage est élevé.

---

### **3. Slippage Final**
```
slippage = spread_pct × (1 + depth_factor × imbalance_factor)
```

**Exemples**:

**Scénario 1: Marché parfait**
```
Spread: 0.02%
Balance: 1.0
Order: 500 USDT
Depth: 5000 USDT

imbalance_factor = 1.0
depth_factor = 500 / 5000 = 0.1

Slippage = 0.02% × (1 + 0.1 × 1.0)
         = 0.02% × 1.1
         = 0.022%  ✅ Très faible
```

**Scénario 2: Marché déséquilibré**
```
Spread: 0.03%
Balance: 0.7
Order: 2000 USDT
Depth: 1500 USDT

imbalance_factor = 1 / 0.7 = 1.43
depth_factor = 2000 / 1500 = 1.33

Slippage = 0.03% × (1 + 1.33 × 1.43)
         = 0.03% × 2.90
         = 0.087%  ⚠️ Significatif
```

**Scénario 3: Ordre très gros**
```
Spread: 0.04%
Balance: 0.8
Order: 5000 USDT
Depth: 1000 USDT

imbalance_factor = 1 / 0.8 = 1.25
depth_factor = 5000 / 1000 = 5.0

Slippage = 0.04% × (1 + 5.0 × 1.25)
         = 0.04% × 7.25
         = 0.29%  ❌ Énorme
```

---

## 📊 DONNÉES DISPONIBLES

### **Scanner de scalabilité**
```
pair = {
    'spread': 0.02,           # ✅ Spread moyen
    'bookDepth': 2020.0,      # ✅ Total depth
    'balanceScore': 0.95,     # ✅ Balance bid/ask
    'bid_vol': 950.0,         # ❌ PAS retourné actuellement
    'ask_vol': 1070.0         # ❌ PAS retourné actuellement
}
```

**Problème**: `bid_vol` et `ask_vol` ne sont pas retournés individuellement.

---

## 🎯 SOLUTION PROPOSÉE

### **Option 1: Sans bid_vol/ask_vol** (simplifié)
```python
def estimate_slippage_simple(order_size: float, spread_pct: float, 
                              depth: float, balance_score: float) -> float:
    """
    Version simplifiée utilisant seulement bookDepth total
    """
    # Approximer bid_vol + ask_vol = depth
    imbalance_factor = 1 / balance_score
    depth_factor = order_size / depth
    
    slippage_pct = spread_pct * (1 + depth_factor * imbalance_factor)
    
    return slippage_pct
```

**Avantages**:
- ✅ Simple à implémenter
- ✅ Données déjà disponibles
- ✅ Raisonnable pour petits ordres

**Inconvénients**:
- ⚠️ Moins précis que version complète

---

### **Option 2: Retourner bid_vol/ask_vol** (complet)
```python
# Modifier scanner.py
return {
    'spread': spread,
    'bookDepth': total_vol,
    'balanceScore': balance_score,
    'bidVol': bid_vol,        # NOUVEAU
    'askVol': ask_vol         # NOUVEAU
}
```

**Avantages**:
- ✅ Plus précis
- ✅ Données déjà calculées

**Inconvénients**:
- ⚠️ Légère modification du scanner

---

## 💡 IMPLÉMENTATION PROPOSÉE

### **Étape 1: Retourner bid_vol/ask_vol**

**Fichier**: `trade_cursor_py/core/scanner.py` (ligne 91-95)

**Avant**:
```python
return {
    'spread': spread,
    'bookDepth': total_vol,
    'balanceScore': balance_score
}
```

**Après**:
```python
return {
    'spread': spread,
    'bookDepth': total_vol,
    'balanceScore': balance_score,
    'bidVol': bid_vol,
    'askVol': ask_vol
}
```

---

### **Étape 2: Ajouter estimate_slippage**

**Fichier**: `trade_cursor_py/core/position_manager.py`

**Nouvelle méthode**:
```python
def _estimate_slippage(
    self,
    order_size: float,
    spread_pct: float,
    depth: float,
    balance_score: float,
    bid_vol: Optional[float] = None,
    ask_vol: Optional[float] = None
) -> float:
    """
    Estime le slippage réaliste pour un ordre
    
    Args:
        order_size: Taille de l'ordre en USDT
        spread_pct: Spread moyen en %
        depth: Profondeur totale du carnet
        balance_score: Équilibre bid/ask (0-1)
        bid_vol: Volume bid total (optionnel)
        ask_vol: Volume ask total (optionnel)
        
    Returns:
        Slippage estimé en %
    """
    # Imbalance factor
    imbalance_factor = 1 / balance_score if balance_score > 0 else 1.0
    
    # Depth factor
    if bid_vol and ask_vol:
        # Version précise
        depth_factor = order_size / (bid_vol + ask_vol)
    else:
        # Version simplifiée
        depth_factor = order_size / depth if depth > 0 else 0
    
    # Slippage estimé
    slippage_pct = spread_pct * (1 + depth_factor * imbalance_factor)
    
    # Limiter à un maximum raisonnable
    slippage_pct = min(slippage_pct, 1.0)  # Max 1%
    
    return round(slippage_pct, 4)
```

---

### **Étape 3: Calculer coûts totaux**

**Modifier `close_position`**:
```python
def close_position(self, reason: str, exit_price: Optional[float] = None,
                   scalability_data: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Scalability_data contient: spread, depth, balance, bidVol, askVol
    """
    # ... calcul P&L brut ...
    
    # Calculer frais + slippage
    total_costs = 0
    fees = 0
    
    if self.config.use_fee_calculation:
        # Frais maker/taker (0% pour paires scalables)
        fees = 0  # Changé de 0.08% à 0%
        
        # Slippage dynamique
        if scalability_data:
            spread = scalability_data.get('spread', 0)
            depth = scalability_data.get('bookDepth', 0)
            balance = scalability_data.get('balanceScore', 1.0)
            bid_vol = scalability_data.get('bidVol')
            ask_vol = scalability_data.get('askVol')
            
            # Estimation pour entrée
            slippage_entry = self._estimate_slippage(
                order_size=self.active_position.size,
                spread_pct=spread,
                depth=depth,
                balance_score=balance,
                bid_vol=bid_vol,
                ask_vol=ask_vol
            )
            
            # Estimation pour sortie
            slippage_exit = self._estimate_slippage(
                order_size=self.active_position.size,
                spread_pct=spread,
                depth=depth,
                balance_score=balance,
                bid_vol=bid_vol,
                ask_vol=ask_vol
            )
            
            total_costs = slippage_entry + slippage_exit
        else:
            # Fallback: estimation conservatrice
            total_costs = 0.05  # 0.05% par défaut
    
    net_pnl = pnl - total_costs
```

---

## 📈 IMPACT ESTIMÉ

### **Scénarios**

**Scénario 1: Marché parfait**
```
Spread: 0.02%
Balance: 0.95
Depth: 3000 USDT
Order: 1000 USDT

Slippage = 0.02% × (1 + 0.33 × 1.05) = 0.027%
Total coûts = 0.054% (vs 0.08% actuel)  ✅ Réduction de 32%
```

**Scénario 2: Marché moyen**
```
Spread: 0.03%
Balance: 0.80
Depth: 1500 USDT
Order: 1000 USDT

Slippage = 0.03% × (1 + 0.67 × 1.25) = 0.055%
Total coûts = 0.110% (vs 0.08% actuel)  ⚠️ Augmentation de 37%
```

**Scénario 3: Marché déséquilibré**
```
Spread: 0.04%
Balance: 0.60
Depth: 800 USDT
Order: 1000 USDT

Slippage = 0.04% × (1 + 1.25 × 1.67) = 0.163%
Total coûts = 0.326% (vs 0.08% actuel)  ❌ Augmentation de 300%
```

---

## ⚠️ CONSÉQUENCES

### **Avantages**
1. ✅ **Plus réaliste**: Slippage dépend réellement des conditions
2. ✅ **Sélectif**: Désavantage les paires illiquides/déséquilibrées
3. ✅ **Adaptatif**: Coûts réflètent la taille de l'ordre

---

### **Risques**
1. ⚠️ **Sélectivité accrue**: Moins de trades acceptés
2. ⚠️ **Winrate impacté**: Certains trades gagnants deviennent perdants
3. ⚠️ **Complexité**: Calculs supplémentaires

---

## 🎯 RECOMMANDATIONS

### **Option A: Conserver 0.08% fixe** (Simple)
```
Avantages: Simple, prévisible
Inconvénients: Non adaptatif, fausse sécurité
```

### **Option B: Slippage simple** (Balancé) ⭐ **RECOMMANDÉ**
```
Coûts = 0% fees + slippage estimé
Slippage min = 0.02% (marché parfait)
Slippage max = 0.1% (marché difficile)
Clamp: 0.02% à 0.1%

Avantages: Réaliste, simple à implémenter
```

### **Option C: Slippage complexe** (Précis)
```
Coûts = slippage_entry + slippage_exit
Slippage = f(spread, depth, balance, order_size)

Avantages: Très précis
Inconvénients: Complexe, peut être trop conservateur
```

---

## 🧪 TEST

**Proposer un test**:
1. Implémenter Option B (slippage simple)
2. Tester sur 50 trades
3. Comparer P&L Net vs. ancien système
4. Ajuster si nécessaire

---

## 📝 RÉSUMÉ

| Aspect | Actuel | Proposé (Option B) |
|--------|--------|-------------------|
| **Fees** | 0.08% fixe | 0% (paires 0 fees) |
| **Slippage** | 0% | 0.02-0.1% dynamique |
| **Total coûts** | 0.08% | 0.02-0.1% |
| **Réalisme** | ❌ Faible | ✅ Élevé |
| **Complexité** | ⭐ | ⭐⭐ |
| **Impact winrate** | - | ⚠️ Légèrement négatif |
| **Impact sélectivité** | - | ✅ Meilleure qualité |

---

**Date**: 2025-11-02  
**Version**: v6.2  
**Document**: Analyse frais/slippage

