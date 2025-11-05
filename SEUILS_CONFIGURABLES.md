# ⚙️ SEUILS CONFIGURABLES À LA VOLÉE

**Trade Cursor v6.1 - Phase 1+2**

---

## ✅ IMPLÉMENTATION

Tous les seuils des filtres Phase 1+2 sont **configurables** directement via l'interface HTML.

---

## 🎚️ SLIDERS DISPONIBLES

### **1. SNR Threshold** 🔊
**Slider**: 0.1 à 1.0  
**Défaut**: 0.3  
**Variable JS**: `snrThreshold`

**Fonction**: Rejette les signaux "plats" sans momentum réel.  
**Impact**: `snr < 0.3` → trade rejeté

**Usage**:
- **Plus bas (0.1-0.2)** → Plus permissif (plus de trades, qualité moindre)
- **Plus haut (0.5-1.0)** → Plus strict (moins de trades, meilleure qualité)

---

### **2. Breakout Threshold** 🚀
**Slider**: 0.1 à 1.0  
**Défaut**: 0.3  
**Variable JS**: `breakoutThreshold`

**Fonction**: Multiplicateur ATR pour breakout filter.  
**Impact**: Prix doit casser EMA21 ± `ATR × 0.3`

**Usage**:
- **Plus bas (0.1-0.2)** → Plus permissif (breakouts plus petits acceptés)
- **Plus haut (0.5-1.0)** → Plus strict (breakouts forts uniquement)

---

### **3. Wick Ratio Max** 🕯️
**Slider**: 1.5 à 5.0  
**Défaut**: 2.5  
**Variable JS**: `wickRatioMax`

**Fonction**: Anti-manipulation, rejette wicks excessifs.  
**Impact**: Si `wick_ratio > 2.5` → trade rejeté

**Usage**:
- **Plus bas (1.5-2.0)** → Plus strict (rejette même petites wicks)
- **Plus haut (3.0-5.0)** → Plus permissif (tolère grandes wicks)

---

### **4. DI Gap Min** 📊
**Slider**: 3.0 à 10.0  
**Défaut**: 5.0  
**Variable JS**: `diGapMin`

**Fonction**: Gap minimum entre DI+ et DI- pour validation ADX.  
**Impact**: Si `|DI+ - DI-| < 5` → ADX seul (sans DI gap)

**Usage**:
- **Plus bas (3-4)** → Plus permissif (petits gaps acceptés)
- **Plus haut (6-10)** → Plus strict (gaps importants uniquement)

---

## 📍 LOCALISATION UI

Les sliders sont situés dans la section **"⚙️ SEUILS PHASE 1+2 (Configurables)"** en bas du panneau de configuration, juste avant le bouton **"SCANNER LES PAIRES"**.

```
┌─────────────────────────────────────────────────┐
│  🎚️ VOLUME MULTIPLIER                          │
│  📊 MODE TP/SL                                  │
│  💰 CAPITAL  |  🎯 CONFLUENCE                   │
│                                                │
│  ───────────────────────────────────────────── │
│  ⚙️ SEUILS PHASE 1+2 (Configurables)           │
│                                                │
│  [SNR] [Breakout] [Wick Ratio] [DI Gap]       │
│                                                │
│  [🔍 SCANNER LES PAIRES]                      │
└─────────────────────────────────────────────────┘
```

---

## 🔧 MODIFICATIONS

### **Backend (Python)**

**`config.py`** (lignes 47-52):
```python
# Phase 1+2: New filters (configurable)
"snr_threshold": 0.3,
"breakout_threshold": 0.3,
"wick_ratio_max": 2.5,
"di_gap_min": 5,
"di_gap_adx_threshold": 25,
```

**`core/analyzer.py`** (lignes 211-236):
```python
# Utilise TRADING_CONFIG pour lire les seuils
snr_threshold = TRADING_CONFIG.get('snr_threshold', 0.3)
breakout_mult = TRADING_CONFIG.get('breakout_threshold', 0.3)
wick_max = TRADING_CONFIG.get('wick_ratio_max', 2.5)
di_gap_min = TRADING_CONFIG.get('di_gap_min', 5)
```

---

### **Frontend (HTML/JS)**

**`templates/index.html`** (lignes 343-393):
- Section HTML avec 4 sliders configurés
- Variables JS déclarées (lignes 664-667)
- Mise à jour en temps réel via `oninput`

---

## ⚠️ IMPORTANT

**Actuellement, les sliders HTML sont prêts**, mais **le backend Python n'est pas encore connecté** au frontend JavaScript.

### **État actuel**:
- ✅ Sliders UI créés
- ✅ Variables JS déclarées
- ✅ Backend utilise `TRADING_CONFIG`
- ❌ Pas de liaison frontend ↔ backend
- ❌ JavaScript n'utilise pas ces variables

### **Solution**:
Le code JavaScript dans `index.html` utilise encore l'ancien système. Pour activer les sliders, il faut soit:
1. **Migrer complètement** vers Python (backend actuel)
2. **Modifier le JavaScript** pour utiliser les variables (ex. `snrThreshold`)

---

## 🎯 PROCHAINES ÉTAPES

### **Option A**: Migration Python complète
```python
# Créer endpoint API
@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    if request.method == 'POST':
        # Mettre à jour TRADING_CONFIG dynamiquement
        data = request.json
        TRADING_CONFIG.update(data)
        return jsonify({'status': 'updated'})
    else:
        return jsonify(TRADING_CONFIG)
```

### **Option B**: Utiliser le JS actuel
```javascript
// Dans analyzeTimeframe() ou équivalent
var snr = abs(price - ema21) / atr;
if (snr < snrThreshold) {  // Utilise variable slider
    return null;
}
```

---

## 📊 RECOMMANDATIONS

### **Seuils par défaut** (optimaux pour la plupart des cas)
| Paramètre | Min | Défaut | Max | Recommandé |
|-----------|-----|--------|-----|------------|
| SNR | 0.1 | 0.3 | 1.0 | 0.3 |
| Breakout | 0.1 | 0.3 | 1.0 | 0.3 |
| Wick Ratio | 1.5 | 2.5 | 5.0 | 2.5 |
| DI Gap | 3.0 | 5.0 | 10.0 | 5.0 |

### **Ajustements selon contexte**

**Marché très volatil**:
- SNR: 0.2-0.3
- Breakout: 0.2-0.3
- Wick Ratio: 2.5-3.0
- DI Gap: 5.0-6.0

**Marché calme**:
- SNR: 0.3-0.4
- Breakout: 0.3-0.4
- Wick Ratio: 2.0-2.5
- DI Gap: 4.0-5.0

**Sous-trading** (trop peu de trades):
- Réduire SNR (0.2)
- Réduire Breakout (0.2)
- Augmenter Wick (3.0)
- Réduire DI Gap (4.0)

---

**Date**: 2025-11-02  
**Version**: v6.1  
**Status**: ✅ UI implémentée, 🔄 Liaison backend pendante




