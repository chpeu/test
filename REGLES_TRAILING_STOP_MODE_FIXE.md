# 📊 RÈGLES TRAILING STOP EN MODE FIXE

**Date**: Novembre 2024  
**Version**: v7.1

---

## 🎯 RÈGLE GLOBALE

En mode FIXE, le **trailing stop adaptatif ATR** remplace le trailing stop fixe (0.15%) après le TP partiel. Il permet de suivre le prix de manière dynamique selon la volatilité.

---

## 📋 RÈGLES DÉTAILLÉES

### **PHASE 1 : AVANT TP PARTIEL (+0.25%)**

**Règle** : **Aucun trailing stop actif**

- ✅ **SL initial** : Reste au niveau calculé (SL = entry - 0.25% pour LONG)
- ✅ **Pas de trailing** : Le SL ne bouge pas
- ✅ **Objectif** : Attendre que le TP partiel se déclenche à +0.25%

**Exemple** :
```
Entry: 100.00 USDT
SL initial: 99.75 USDT (-0.25%)

Prix à 100.10 (+0.10%) → SL reste à 99.75
Prix à 100.20 (+0.20%) → SL reste à 99.75
Prix à 100.25 (+0.25%) → TP PARTIEL déclenché
```

---

### **PHASE 2 : APRÈS TP PARTIEL (+0.25%)**

**Règle** : **Trailing stop adaptatif ATR activé**

#### **2.1 Déclenchement**

- ✅ **Seuil** : PnL > +0.25% (déjà atteint après TP partiel)
- ✅ **Déclenché automatiquement** : Dès que TP partiel vendu
- ✅ **SL initial après TP partiel** : `entry` (break-even immédiat)

**Exemple** :
```
Entry: 100.00 USDT
TP partiel à 100.25 (+0.25%) → Vendu 50%
SL après TP partiel: 100.00 (break-even)
→ Trailing stop adaptatif activé
```

#### **2.2 Distance du Trailing**

La distance du trailing stop est **adaptative selon ATR** :

**Formule** :
```
Distance = ATR × 0.4
```

**Bornes** :
- **Minimum** : 0.08% (si ATR très faible)
- **Maximum** : 0.25% (si ATR très élevé)

**Exemples** :
```
ATR = 0.2% → Distance = 0.2% × 0.4 = 0.08% (minimum)
ATR = 0.5% → Distance = 0.5% × 0.4 = 0.20%
ATR = 0.8% → Distance = 0.8% × 0.4 = 0.32% → Clampé à 0.25% (maximum)
```

#### **2.3 Calcul du Nouveau SL**

**Pour LONG** :
```
Nouveau SL = Prix actuel × (1 - trailing_distance / 100)
```

**Règle** : Le SL **monte uniquement** (jamais descendre)
- ✅ Si `nouveau_sl > sl_actuel` → Mettre à jour
- ❌ Si `nouveau_sl ≤ sl_actuel` → Ignorer (ne pas descendre)

**Exemple LONG** :
```
Entry: 100.00 USDT
SL après TP partiel: 100.00 (break-even)
ATR: 0.5% → Distance: 0.20%

Prix à 100.50 (+0.50%) :
  Nouveau SL = 100.50 × (1 - 0.20/100) = 100.30
  → SL mis à jour : 100.00 → 100.30 ✅

Prix à 101.00 (+1.00%) :
  Nouveau SL = 101.00 × (1 - 0.20/100) = 100.80
  → SL mis à jour : 100.30 → 100.80 ✅

Prix redescend à 100.70 :
  Nouveau SL = 100.70 × (1 - 0.20/100) = 100.50
  → Ignoré (100.50 < 100.80) ❌
  → SL reste à 100.80 (protection garantie)
```

**Pour SHORT** :
```
Nouveau SL = Prix actuel × (1 + trailing_distance / 100)
```

**Règle** : Le SL **descend uniquement** (jamais monter)
- ✅ Si `nouveau_sl < sl_actuel` → Mettre à jour
- ❌ Si `nouveau_sl ≥ sl_actuel` → Ignorer (ne pas monter)

**Exemple SHORT** :
```
Entry: 100.00 USDT
SL après TP partiel: 100.00 (break-even)
ATR: 0.5% → Distance: 0.20%

Prix à 99.50 (-0.50%) :
  Nouveau SL = 99.50 × (1 + 0.20/100) = 99.70
  → SL mis à jour : 100.00 → 99.70 ✅

Prix à 99.00 (-1.00%) :
  Nouveau SL = 99.00 × (1 + 0.20/100) = 99.20
  → SL mis à jour : 99.70 → 99.20 ✅

Prix remonte à 99.30 :
  Nouveau SL = 99.30 × (1 + 0.20/100) = 99.50
  → Ignoré (99.50 > 99.20) ❌
  → SL reste à 99.20 (protection garantie)
```

---

## 🔄 SÉQUENCE COMPLÈTE

### **Scénario LONG**

```
T+0s   : Entry 100.00 | SL 99.75 (-0.25%)
        → Pas de trailing (attendre TP partiel)

T+5s   : Prix 100.25 (+0.25%)
        → TP PARTIEL : Vendu 50%
        → SL = 100.00 (break-even)
        → Trailing adaptatif activé

T+10s  : Prix 100.50 (+0.50%) | ATR 0.5% → Distance 0.20%
        → Nouveau SL = 100.50 × (1 - 0.20/100) = 100.30
        → SL mis à jour : 100.00 → 100.30 ✅

T+20s  : Prix 101.00 (+1.00%) | ATR 0.5% → Distance 0.20%
        → Nouveau SL = 101.00 × (1 - 0.20/100) = 100.80
        → SL mis à jour : 100.30 → 100.80 ✅

T+30s  : Prix 101.50 (+1.50%) | ATR 0.5% → Distance 0.20%
        → Nouveau SL = 101.50 × (1 - 0.20/100) = 101.20
        → SL mis à jour : 100.80 → 101.20 ✅

T+40s  : Prix redescend à 101.00
        → Nouveau SL = 101.00 × (1 - 0.20/100) = 100.80
        → Ignoré (100.80 < 101.20) ❌
        → SL reste à 101.20

T+50s  : Prix continue à descendre à 101.15
        → SL touché (101.15 < 101.20)
        → Position fermée à 101.15
        → Gain : +1.15% sur les 50% restants
```

---

## ⚙️ CONFIGURATION

**Fichier**: `config.py` (ligne 82-89)

```python
"trailing_stop": {
    "enabled": True,           # Activer/désactiver
    "trigger_pnl": 0.25,       # Déclencher à +0.25%
    "atr_multiplier": 0.4,     # Distance = ATR × 0.4
    "min_distance": 0.08,      # Minimum 0.08%
    "max_distance": 0.25,      # Maximum 0.25%
}
```

**Paramètres ajustables** :

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| `enabled` | `True` | Activer/désactiver trailing adaptatif |
| `trigger_pnl` | `0.25` | Seuil de déclenchement (%) |
| `atr_multiplier` | `0.4` | Multiplicateur ATR pour distance |
| `min_distance` | `0.08` | Distance minimum (%) |
| `max_distance` | `0.25` | Distance maximum (%) |

**Recommandations** :
- **Scalping agressif** : `atr_multiplier: 0.3`, `min_distance: 0.06`
- **Trading conservateur** : `atr_multiplier: 0.5`, `max_distance: 0.30`

---

## 📊 RÉSUMÉ DES RÈGLES

### **Avant TP Partiel**
- ❌ **Aucun trailing** : SL reste fixe
- ✅ **Attendre** : +0.25% pour déclencher TP partiel

### **Après TP Partiel**
- ✅ **Trailing adaptatif activé** : Distance = ATR × 0.4
- ✅ **Bornes** : 0.08% - 0.25%
- ✅ **LONG** : SL monte uniquement (jamais descendre)
- ✅ **SHORT** : SL descend uniquement (jamais monter)
- ✅ **TP final ignoré** : Seul le trailing stop gère la fermeture

---

## 🎯 AVANTAGES

1. ✅ **Adaptatif** : S'ajuste à la volatilité (ATR)
2. ✅ **Protection** : Verrouille les gains progressivement
3. ✅ **Flexibilité** : Distance entre 0.08% et 0.25% selon ATR
4. ✅ **Pas de recul** : SL ne peut que monter (LONG) ou descendre (SHORT)

---

## 🔍 LOGS ET MONITORING

### **Logs de trailing stop**

Quand le trailing stop se met à jour, vous verrez :

```
🔄 Trailing SL LONG BTC/USDT:USDT: 100.000000 → 100.300000 (-0.20%) [ATR: 0.50%]
```

### **Détails dans les logs**

- ✅ **Ancien SL** : 100.000000
- ✅ **Nouveau SL** : 100.300000
- ✅ **Distance** : -0.20%
- ✅ **ATR** : 0.50%

---

## ✅ VALIDATION

### **Règles vérifiées**

1. ✅ **Avant TP partiel** : Pas de trailing
2. ✅ **Après TP partiel** : Trailing adaptatif activé
3. ✅ **Distance adaptative** : ATR × 0.4 avec bornes
4. ✅ **LONG** : SL monte uniquement
5. ✅ **SHORT** : SL descend uniquement
6. ✅ **TP final ignoré** : Seul trailing stop gère

### **Fichiers**

- ✅ `core/position_manager.py` :
  - `check_position()` : Appel trailing adaptatif (ligne 554-557)
  - `_update_trailing_stop_adaptive()` : Logique complète (ligne 618-678)
  - `_check_levels()` : Ignore TP final après TP partiel (ligne 942-960)
- ✅ `config.py` : Configuration (ligne 82-89)

---

## 🎯 CONCLUSION

En mode FIXE, le trailing stop suit ces règles :

1. **Avant TP partiel** : Aucun trailing (SL fixe)
2. **Après TP partiel** : Trailing adaptatif ATR (distance 0.08% - 0.25%)
3. **Direction** : LONG monte, SHORT descend (jamais l'inverse)
4. **TP final** : Ignoré (seul trailing stop gère)

Cette approche permet de **capturer des gains au-delà de 0.6%** tout en **protégeant automatiquement** les profits avec un trailing stop adaptatif.

---

**Statut**: ✅ **ACTIVE ET FONCTIONNELLE**  
**Version**: v7.1  
**Date**: Novembre 2024

