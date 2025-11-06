# 🔍 CONDITIONS D'INVALIDATION AVANCÉE

**Date**: 2025-01-06  
**Version**: v7.0  
**Statut**: ✅ Implémenté

---

## 📋 RÉSUMÉ

Système d'invalidation dynamique avancée qui permet de fermer les positions qui ne progressent pas ou perdent leur momentum, **uniquement si elles ne sont pas en position de profit**.

**Principe** : Les modes Stagnation et Momentum sont activés **seulement si `only_if_not_profitable = True` ET `pnl < 0`**.

---

## 🎯 TROIS MODES D'INVALIDATION

### 1️⃣ MODE STAGNATION

**Quand** : Le PnL ne progresse pas pendant une durée donnée

**Conditions d'activation** :
- ✅ `elapsed >= 60s` (minimum 60 secondes écoulées)
- ✅ `only_if_not_profitable = True` → **Seulement si PnL < 0** (pas en profit)
- ✅ `pnl <= -0.05%` (PnL doit être en dessous de -0.05%)
- ✅ Variation PnL < 0.02% pendant 45 secondes (stagnation)

**Exemple** :
```
Temps 60s: PnL = -0.08%
Temps 75s: PnL = -0.07% (variation 0.01%)
Temps 90s: PnL = -0.08% (variation 0.01%)
Temps 105s: PnL = -0.09% (variation 0.01%)
→ ❌ INVALIDATION : PnL stagne (variation < 0.02%) pendant 45s et PnL < 0
```

**Si PnL > 0** :
```
Temps 60s: PnL = +0.15%
Temps 75s: PnL = +0.14% (stagnation)
→ ✅ PAS D'INVALIDATION : PnL > 0, donc on laisse continuer (pas de perte)
```

---

### 2️⃣ MODE MOMENTUM

**Quand** : Le prix perd son momentum (déclin progressif)

**Conditions d'activation** :
- ✅ `elapsed >= 30s` (minimum 30 secondes écoulées)
- ✅ `only_if_not_profitable = True` → **Seulement si PnL < 0** (pas en profit)
- ✅ `pnl <= -0.03%` (PnL doit être en dessous de -0.03%)
- ✅ Momentum moyen < -0.01% par période (sur 5 dernières périodes)

**Calcul du momentum** :
```python
recent_pnl = [h['pnl'] for h in pnl_history[-5:]]  # 5 dernières périodes
momentum = (recent_pnl[-1] - recent_pnl[0]) / len(recent_pnl)
```

**Exemple** :
```
Temps 30s: PnL = -0.02%
Temps 32s: PnL = -0.04%
Temps 34s: PnL = -0.06%
Temps 36s: PnL = -0.08%
Temps 38s: PnL = -0.10%
→ Momentum = (-0.10 - (-0.02)) / 5 = -0.016% par période
→ ❌ INVALIDATION : Momentum < -0.01% ET PnL < 0
```

**Si PnL > 0** :
```
Temps 30s: PnL = +0.05%
Temps 38s: PnL = +0.03% (momentum négatif)
→ ✅ PAS D'INVALIDATION : PnL > 0, donc on laisse continuer (pas de perte)
```

---

### 3️⃣ MODE SEUILS ADAPTATIFS (ATR)

**Quand** : Le PnL dépasse un seuil adaptatif basé sur la volatilité (ATR)

**Conditions d'activation** :
- ✅ `elapsed >= 30s` (minimum 30 secondes écoulées)
- ✅ `pnl < seuil_adaptatif` (calculé selon ATR)
- ⚠️ **Pas de condition `only_if_not_profitable`** : Ce mode fonctionne même si PnL > 0 (mais le seuil est négatif)

**Calcul du seuil adaptatif** :
```python
atr_percent = (position.atr / position.entry) * 100
adaptive_threshold = -atr_percent * 0.5  # Exemple: -0.5% si ATR = 1%
# Clamp entre -0.10% et -0.20%
adaptive_threshold = max(-0.10, min(-0.20, adaptive_threshold))
```

**Exemple** :
```
ATR = 0.8% → Seuil = -0.8% × 0.5 = -0.4% (clampé à -0.10%)
PnL = -0.12% après 30s
→ ❌ INVALIDATION : PnL < -0.10% (seuil adaptatif)
```

---

## 🔧 CONFIGURATION ACTUELLE

**Fichier** : `config.py`

```python
"advanced_invalidation": {
    "enabled": True,
    
    # Mode 1: Stagnation
    "stagnation_mode": {
        "enabled": True,
        "min_elapsed": 60,              # Commencer après 60s
        "stagnation_time": 45,           # Stagnation pendant 45s
        "stagnation_threshold": 0.02,     # Variation max 0.02%
        "only_if_not_profitable": True,  # ✅ Seulement si PnL < 0
        "min_pnl_for_stagnation": -0.05, # Seuil PnL minimum -0.05%
    },
    
    # Mode 2: Momentum
    "momentum_mode": {
        "enabled": True,
        "min_elapsed": 30,               # Commencer après 30s
        "lookback_periods": 5,            # Analyser 5 dernières périodes
        "momentum_threshold": -0.01,      # Momentum < -0.01% par période
        "only_if_not_profitable": True,  # ✅ Seulement si PnL < 0
        "min_pnl_for_momentum": -0.03,    # Seuil PnL minimum -0.03%
    },
    
    # Mode 3: Seuils Adaptatifs
    "adaptive_thresholds": {
        "enabled": True,
        "atr_multiplier": 0.5,           # Seuil = -ATR × 0.5
        "min_threshold": -0.10,          # Minimum -0.10%
        "max_threshold": -0.20,          # Maximum -0.20%
        "min_elapsed": 30,               # Commencer après 30s
        # ⚠️ Pas de only_if_not_profitable : fonctionne même si PnL > 0
    }
}
```

---

## 📊 LOGIQUE D'ACTIVATION

### Mode Stagnation

```python
if elapsed < 60s:
    return None  # Pas encore 60s

if only_if_not_profitable and pnl >= 0:
    return None  # ✅ PnL > 0 → PAS D'INVALIDATION (on laisse continuer)

if pnl > -0.05%:
    return None  # PnL trop proche de 0

# Vérifier stagnation
recent_history = [h for h in pnl_history if elapsed - h['elapsed'] <= 45]
if variation_pnl < 0.02%:
    return 'ADVANCED_INVALIDATION_STAGNATION'  # ❌ INVALIDATION
```

### Mode Momentum

```python
if elapsed < 30s:
    return None  # Pas encore 30s

if only_if_not_profitable and pnl >= 0:
    return None  # ✅ PnL > 0 → PAS D'INVALIDATION (on laisse continuer)

if pnl > -0.03%:
    return None  # PnL trop proche de 0

# Calculer momentum
recent_pnl = [h['pnl'] for h in pnl_history[-5:]]
momentum = (recent_pnl[-1] - recent_pnl[0]) / len(recent_pnl)
if momentum < -0.01%:
    return 'ADVANCED_INVALIDATION_MOMENTUM'  # ❌ INVALIDATION
```

### Mode Adaptive Thresholds

```python
if elapsed < 30s:
    return None

# Calculer seuil adaptatif
atr_percent = (position.atr / position.entry) * 100
adaptive_threshold = -atr_percent * 0.5
adaptive_threshold = max(-0.10, min(-0.20, adaptive_threshold))

if pnl < adaptive_threshold:
    return 'ADVANCED_INVALIDATION_ADAPTIVE'  # ❌ INVALIDATION
# ⚠️ Pas de vérification only_if_not_profitable : fonctionne même si PnL > 0
```

---

## ✅ RÉSUMÉ DES CONDITIONS

| Mode | Condition "Pas de Profit" | Condition "Momentum Perdu" | Seuil PnL | Temps Min |
|------|---------------------------|----------------------------|------------|-----------|
| **Stagnation** | ✅ `only_if_not_profitable = True` | ❌ Non (détecte stagnation) | `pnl <= -0.05%` | 60s |
| **Momentum** | ✅ `only_if_not_profitable = True` | ✅ `momentum < -0.01%` | `pnl <= -0.03%` | 30s |
| **Adaptive** | ❌ Non (fonctionne même si PnL > 0) | ❌ Non | `pnl < seuil_ATR` | 30s |

---

## 🎯 COMPORTEMENT ATTENDU

### ✅ Position en Profit (PnL > 0)

**Stagnation et Momentum** :
- ❌ **PAS D'INVALIDATION** : `only_if_not_profitable = True` empêche l'invalidation
- ✅ Position continue même si elle stagne ou perd du momentum
- **Raison** : On ne veut pas fermer une position qui est déjà en profit

**Adaptive Thresholds** :
- ⚠️ **Peut invalider** : Seuil adaptatif est négatif (-0.10% à -0.20%), donc si PnL devient très négatif même après un profit initial

### ❌ Position en Perte (PnL < 0)

**Stagnation** :
- ✅ **INVALIDATION** si PnL stagne pendant 45s et `pnl <= -0.05%`
- **But** : Éviter de garder une position qui ne progresse pas

**Momentum** :
- ✅ **INVALIDATION** si momentum < -0.01% et `pnl <= -0.03%`
- **But** : Éviter de garder une position qui décline progressivement

**Adaptive Thresholds** :
- ✅ **INVALIDATION** si `pnl < seuil_ATR` (ex: -0.10%)
- **But** : Seuil adaptatif selon la volatilité du marché

---

## 🔍 EXEMPLES PRATIQUES

### Exemple 1 : Stagnation en Perte

```
Temps 0s:   PnL = 0%
Temps 30s:  PnL = -0.08% (invalidation précoce non déclenchée)
Temps 60s:  PnL = -0.08%
Temps 75s:  PnL = -0.07% (variation 0.01%)
Temps 90s:  PnL = -0.08% (variation 0.01%)
Temps 105s: PnL = -0.09% (variation 0.01%)
           ↓
           ❌ INVALIDATION STAGNATION
           Raison: Variation < 0.02% pendant 45s ET PnL < 0
```

### Exemple 2 : Momentum Perdu en Perte

```
Temps 0s:   PnL = 0%
Temps 30s:  PnL = -0.02%
Temps 32s:  PnL = -0.04%
Temps 34s:  PnL = -0.06%
Temps 36s:  PnL = -0.08%
Temps 38s:  PnL = -0.10%
           ↓
           Momentum = (-0.10 - (-0.02)) / 5 = -0.016% par période
           ❌ INVALIDATION MOMENTUM
           Raison: Momentum < -0.01% ET PnL < 0
```

### Exemple 3 : Position en Profit (Pas d'Invalidation)

```
Temps 0s:   PnL = 0%
Temps 30s:  PnL = +0.15%
Temps 60s:  PnL = +0.14% (stagnation légère)
Temps 90s:  PnL = +0.13% (stagnation légère)
           ↓
           ✅ PAS D'INVALIDATION
           Raison: PnL > 0, donc only_if_not_profitable empêche l'invalidation
```

### Exemple 4 : Momentum Perdu mais en Profit

```
Temps 0s:   PnL = 0%
Temps 30s:  PnL = +0.20%
Temps 38s:  PnL = +0.10% (momentum négatif, mais toujours en profit)
           ↓
           ✅ PAS D'INVALIDATION
           Raison: PnL > 0, donc only_if_not_profitable empêche l'invalidation
```

---

## 🔧 FICHIERS IMPLÉMENTÉS

### `config.py`
- Configuration complète avec `only_if_not_profitable = True` pour Stagnation et Momentum

### `core/position_manager.py`
- `_check_stagnation_invalidation()` : Vérifie `only_if_not_profitable` et `pnl >= 0`
- `_check_momentum_invalidation()` : Vérifie `only_if_not_profitable` et `pnl >= 0`
- `_check_adaptive_thresholds_invalidation()` : Pas de vérification `only_if_not_profitable`
- `_update_pnl_history()` : Met à jour l'historique à chaque check

### `core/position_manager.py` - `check_position()`
- Appel après 30 secondes : `_check_advanced_invalidation()`
- Mise à jour `pnl_history` avant chaque check

---

## ✅ CONCLUSION

**Les conditions "momentum perdu" et "pas de profit" sont bien implémentées** :

1. ✅ **Mode Momentum** : Invalide si momentum < -0.01% **ET** `only_if_not_profitable = True` **ET** `pnl < 0`
2. ✅ **Mode Stagnation** : Invalide si stagnation **ET** `only_if_not_profitable = True` **ET** `pnl < 0`
3. ✅ **Mode Adaptive** : Invalide si `pnl < seuil_ATR` (pas de condition sur profit)

**Comportement** : Les positions en profit (PnL > 0) ne sont **PAS invalidées** par Stagnation et Momentum, même si elles stagnent ou perdent du momentum. C'est le comportement attendu pour protéger les profits.

