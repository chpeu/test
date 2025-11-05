# 🔧 CORRECTION SEUILS ATR OPTIMAL

**Date**: 2025-11-04  
**Status**: ✅ **CORRIGÉ**

---

## 🐛 PROBLÈME IDENTIFIÉ

**Symptôme** :
- Tous les setups sont rejetés avec "ATR sous-optimal: 0.119% (trop bas, optimal: 0.15-0.8%)"
- L'ATR mesuré est 0.119% mais le minimum requis est 0.15%
- Seuil trop strict, rejette trop de setups valides

**Cause** :
- `optimal_atr_min_1m = 0.15%` est trop élevé
- Beaucoup de paires ont un ATR entre 0.10% et 0.15%
- Pas de possibilité de modifier les seuils à la volée

---

## ✅ CORRECTIONS APPLIQUÉES

### **1. Ajustement des seuils par défaut**

**Fichier** : `config.py`

**Avant** :
```python
"optimal_atr_min_1m": 0.15,  # Trop strict
"optimal_atr_min_5m": 0.3,   # Trop strict
```

**Après** :
```python
"optimal_atr_min_1m": 0.10,  # 🔥 Plus permissif (était 0.15)
"optimal_atr_max_1m": 0.8,
"optimal_atr_min_5m": 0.20,  # 🔥 Plus permissif (était 0.3)
"optimal_atr_max_5m": 1.5,
```

**Impact** :
- 1m : Accepte maintenant ATR ≥ 0.10% (au lieu de 0.15%)
- 5m : Accepte maintenant ATR ≥ 0.20% (au lieu de 0.30%)
- Plus de setups acceptés sans compromettre la qualité

---

### **2. Seuils ATR configurables via `/api/config`**

**Fichier** : `main.py` - `api_get_config()` et `api_update_config()`

**Ajout dans GET `/api/config`** :
```python
'optimal_atr_min_1m': TRADING_CONFIG.get('optimal_atr_min_1m', 0.10),
'optimal_atr_max_1m': TRADING_CONFIG.get('optimal_atr_max_1m', 0.8),
'optimal_atr_min_5m': TRADING_CONFIG.get('optimal_atr_min_5m', 0.20),
'optimal_atr_max_5m': TRADING_CONFIG.get('optimal_atr_max_5m', 1.5)
```

**Ajout dans POST `/api/config`** :
```python
# Modification des 4 seuils ATR optimal
if 'optimal_atr_min_1m' in data:
    val = float(data['optimal_atr_min_1m'])
    val = max(0.01, min(1.0, val))  # Clamp 0.01-1.0%
    TRADING_CONFIG['optimal_atr_min_1m'] = val
    updated['optimal_atr_min_1m'] = val

# ... idem pour optimal_atr_max_1m, optimal_atr_min_5m, optimal_atr_max_5m
```

---

## 📊 RANGES CONFIGURABLES

| Paramètre | Range | Défaut | Description |
|-----------|-------|--------|-------------|
| `optimal_atr_min_1m` | 0.01-1.0% | 0.10% | ATR minimum 1m |
| `optimal_atr_max_1m` | 0.1-5.0% | 0.8% | ATR maximum 1m |
| `optimal_atr_min_5m` | 0.01-2.0% | 0.20% | ATR minimum 5m |
| `optimal_atr_max_5m` | 0.5-10.0% | 1.5% | ATR maximum 5m |

---

## 🔄 UTILISATION

### **Récupérer les seuils actuels**
```bash
GET /api/config
# Retourne: { "optimal_atr_min_1m": 0.10, ... }
```

### **Modifier les seuils**
```bash
POST /api/config
{
  "optimal_atr_min_1m": 0.08,  # Encore plus permissif
  "optimal_atr_max_1m": 1.0    # Plus large
}
```

---

## 📈 AVANT / APRÈS

### **Avant** :
- ATR 0.119% → ❌ Rejeté (0.119 < 0.15)
- ATR 0.12% → ❌ Rejeté (0.12 < 0.15)
- ATR 0.15% → ✅ Accepté

### **Après** :
- ATR 0.119% → ✅ Accepté (0.119 ≥ 0.10)
- ATR 0.12% → ✅ Accepté (0.12 ≥ 0.10)
- ATR 0.15% → ✅ Accepté

---

## ✅ RÉSULTAT

**Maintenant** :
- ✅ Seuils plus permissifs par défaut (0.10% au lieu de 0.15% pour 1m)
- ✅ Seuils configurables à la volée via `/api/config`
- ✅ Plus de setups acceptés (moins de rejets)
- ✅ Qualité maintenue (seuil max toujours 0.8%)

---

## 🎯 RECOMMANDATIONS

**Si trop de setups sont acceptés** :
- Augmenter `optimal_atr_min_1m` à 0.12% ou 0.15%
- Via POST `/api/config` { "optimal_atr_min_1m": 0.12 }

**Si pas assez de setups** :
- Réduire `optimal_atr_min_1m` à 0.08% ou 0.05%
- Via POST `/api/config` { "optimal_atr_min_1m": 0.08 }

---

## 📝 NOTES

- **Seuil minimum** : 0.10% pour 1m (était 0.15%)
- **Seuil maximum** : Inchangé (0.8% pour 1m, 1.5% pour 5m)
- **Modification en temps réel** : Les seuils sont appliqués immédiatement
- **Validation** : Clamp automatique pour éviter valeurs invalides



