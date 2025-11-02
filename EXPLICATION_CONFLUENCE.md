# 🎯 EXPLICATION : CONFLUENCE

**Trade Cursor v6.2**

---

## 🔲 CONFLUENCE DÉCOCHÉE (PERMISSIVE) 🔓

**Mode**: 1m **OU** 5m

### **Comment ça marche**
```
Si 1m validé OU 5m validé → TRADE ACCEPTÉ ✅
Choisir le timeframe avec le PLUS de conditions
```

### **Exemples**

#### **Exemple 1 : 1m validé, 5m invalide**
```
1m: LONG avec 7 conditions ✅
5m: Aucun signal valide ❌

→ TRADE ACCEPTÉ sur 1m
→ Log: "1m only (7 conds)"
```

#### **Exemple 2 : 1m invalide, 5m validé**
```
1m: SNR trop faible ❌
5m: LONG avec 6 conditions ✅

→ TRADE ACCEPTÉ sur 5m
→ Log: "5m only (6 conds)"
```

#### **Exemple 3 : 1m et 5m validés**
```
1m: LONG avec 7 conditions ✅
5m: LONG avec 5 conditions ✅

→ TRADE ACCEPTÉ sur 1m (le plus fort)
→ Log: "1m only (7 conds)"
```

---

## ✅ CONFLUENCE COCHÉE (STRICTE) 🔒

**Mode**: 1m **ET** 5m

### **Comment ça marche**
```
Les DEUX timeframe doivent être validés:
1. 1m ET 5m doivent avoir un signal valide
2. MÊME direction (LONG/LONG ou SHORT/SHORT)
3. Force 5m ≥ 80% de la force 1m
```

### **Exemples**

#### **Exemple 1 : 1m validé, 5m invalide**
```
1m: LONG avec 7 conditions ✅
5m: Aucun signal valide ❌

→ TRADE REFUSÉ ❌
→ Log: "❌ Confluence: directions opposées"
```

#### **Exemple 2 : Directions opposées**
```
1m: LONG avec 7 conditions ✅
5m: SHORT avec 6 conditions ✅

→ TRADE REFUSÉ ❌
→ Log: "❌ Confluence: directions opposées (1m: LONG, 5m: SHORT)"
```

#### **Exemple 3 : 5m trop faible**
```
1m: LONG avec 7 conditions ✅
5m: LONG avec 4 conditions ✅

→ TRADE REFUSÉ ❌
→ Calcul: 4 < (7 × 0.8 = 5.6)
→ Log: "⚠️ Confluence: 5m trop faible (1m: 7, 5m: 4)"
```

#### **Exemple 4 : Accepté**
```
1m: LONG avec 7 conditions ✅
5m: LONG avec 6 conditions ✅

→ Calcul: 6 ≥ (7 × 0.8 = 5.6) ✅
→ TRADE ACCEPTÉ
→ Log: "1m + 5m confluence"
```

---

## 📊 COMPARAISON

| Scénario | Permissive (Décoché) | Stricte (Coché) |
|----------|----------------------|-----------------|
| 1m✅ / 5m❌ | **ACCEPTÉ** | **REFUSÉ** |
| 1m❌ / 5m✅ | **ACCEPTÉ** | **REFUSÉ** |
| 1m✅ / 5m✅ (même direction) | **ACCEPTÉ** | **ACCEPTÉ** |
| 1m✅ / 5m✅ (directions opposées) | **ACCEPTÉ** (choix 1m) | **REFUSÉ** |
| 1m✅7 / 5m✅4 | **ACCEPTÉ** (choix 1m) | **REFUSÉ** (5m<80%) |
| 1m✅7 / 5m✅6 | **ACCEPTÉ** (choix 1m) | **ACCEPTÉ** (5m≥80%) |

---

## 🎯 QUAND UTILISER

### **Permissive (Décoché)** 🔓
**Avantages**:
- ✅ Plus de trades
- ✅ Meilleur timing d'entrée
- ✅ Moins de signaux manqués

**Inconvénients**:
- ⚠️ Moins de confirmation
- ⚠️ Plus de faux positifs potentiels

**Idéal pour**:
- Marchés très volatils
- Scalping rapide (1-2 min)
- Si winrate encore bon

---

### **Stricte (Coché)** 🔒
**Avantages**:
- ✅ Meilleure confirmation
- ✅ Moins de faux signaux
- ✅ Signaux plus solides

**Inconvénients**:
- ⚠️ Moins de trades
- ⚠️ Peut rater des opportunités

**Idéal pour**:
- Marchés calmes
- Volatilité moyenne
- Si trop de faux positifs en permissive

---

## 💡 RECOMMANDATION

**Par défaut**: **DÉCOCHÉ** (Permissive)

**Raison**: En scalping, timing > confirmation absolue.

**Activer** (Coché) si:
- Winrate < 60% en permissive
- Trop de faux signaux
- Marché très calme

---

## 📊 IMPACT SUR LES RÉSULTATS

### **Estimations**

| Métrique | Permissive | Stricte |
|----------|------------|---------|
| **Trades/jour** | 20-30 | 8-15 |
| **Winrate** | 70-75% | 80-90% |
| **Faux positifs** | ~25% | ~10% |
| **Opportunités manquées** | Faible | Moyenne |

---

## 🧪 TESTER

**Étape 1**: Démarrer en **Permissive**  
→ Mesurer winrate sur 50-100 trades

**Étape 2**: Si winrate < 70% → Activer **Stricte**  
→ Comparer résultats

**Étape 3**: Ajuster selon performance

---

**Date**: 2025-11-02  
**Version**: v6.2

