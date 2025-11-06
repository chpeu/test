# 🔧 AJOUT SLIDER ATR OPTIMAL

**Date**: 2025-11-04  
**Status**: ✅ **AJOUTÉ**

---

## 🎯 OBJECTIF

Ajouter un slider pour configurer le seuil `optimal_atr_min_1m` dans l'interface, de **0.05% à 1.0%**.

---

## ✅ MODIFICATIONS APPLIQUÉES

### **1. Slider ATR Optimal ajouté**

**Fichier** : `templates/index.html`

**Emplacement** : Après le slider "DI Gap", dans la section "Phase 1+2: Seuils configurables"

**Code** :
```html
<div class="config-group">
    <div class="config-label">📈 ATR Optimal Min</div>
    <div style="display: flex; align-items: center; gap: 10px; margin-top: 8px;">
        <input type="range" id="atrOptimalSlider" min="0.05" max="1.0" step="0.01" value="0.10" 
               style="width: 150px; height: 20px; cursor: pointer;" 
               oninput="optimalAtrMin1m = parseFloat(this.value); document.getElementById('atrOptimalValue').textContent = optimalAtrMin1m.toFixed(2) + '%'; updateConfigThreshold('optimal_atr_min_1m', optimalAtrMin1m);">
        <span id="atrOptimalValue" style="color: #00ff88; font-weight: bold; min-width: 50px; font-size: 12px;">0.10%</span>
    </div>
    <span style="color: #888; font-size: 10px;">Seuil min 1m (0.05-1.0%)</span>
</div>
```

**Caractéristiques** :
- **Range** : 0.05% à 1.0%
- **Step** : 0.01% (précision)
- **Valeur par défaut** : 0.10% (depuis `config.py`)
- **Affichage** : Format "X.XX%" (ex: 0.10%)

---

### **2. Variable JavaScript ajoutée**

**Fichier** : `templates/index.html`

**Code** :
```javascript
var optimalAtrMin1m = 0.10;     // ATR Optimal minimum 1m (en %)
```

**Note** : La valeur est stockée en **décimal** (0.10 = 10%), pas en pourcentage.

---

### **3. Fonction `updateConfigThreshold()` créée**

**Fichier** : `templates/index.html`

**Code** :
```javascript
async function updateConfigThreshold(key, value) {
    try {
        var response = await fetch(API_BASE_URL + '/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                [key]: value
            })
        });
        
        if (response.ok) {
            var data = await response.json();
            if (data.status === 'updated') {
                debugLog('✅ Config mise à jour', key + ': ' + value);
            }
        } else {
            debugLog('⚠️ Erreur config', 'Impossible de mettre à jour ' + key);
        }
    } catch (error) {
        debugLog('❌ Erreur config', 'Erreur lors de la mise à jour de ' + key + ': ' + error.message);
    }
}
```

**Utilisation** :
- Appelée automatiquement lors du déplacement du slider
- Envoie une requête POST à `/api/config` avec la clé et la valeur
- Met à jour la configuration backend en temps réel

---

### **4. Sliders existants mis à jour**

**Fichiers modifiés** :
- `snrSlider` : Ajout `updateConfigThreshold('snr_threshold', snrThreshold)`
- `breakoutSlider` : Ajout `updateConfigThreshold('breakout_threshold', breakoutThreshold)`
- `wickSlider` : Ajout `updateConfigThreshold('wick_ratio_max', wickRatioMax)`
- `diGapSlider` : Ajout `updateConfigThreshold('di_gap_min', diGapMin)`

**Résultat** : Tous les sliders mettent maintenant à jour la configuration backend automatiquement.

---

## 📊 AFFICHAGE

**Slider ATR Optimal** :
- **Label** : "📈 ATR Optimal Min"
- **Valeur affichée** : "0.10%" (format décimal avec %)
- **Description** : "Seuil min 1m (0.05-1.0%)"
- **Position** : Après "DI Gap", dans la grille des seuils configurables

---

## 🔄 UTILISATION

### **1. Ajuster le seuil ATR**

1. Déplacer le slider entre **0.05%** et **1.0%**
2. La valeur s'affiche en temps réel (ex: "0.12%")
3. La configuration backend est mise à jour automatiquement

### **2. Impact**

- **Valeur plus basse** (ex: 0.05%) → Plus permissif (plus de setups acceptés)
- **Valeur plus élevée** (ex: 0.15%) → Plus strict (moins de setups acceptés)

**Exemple** :
- `0.10%` (défaut) → Accepte ATR ≥ 0.10%
- `0.08%` → Accepte ATR ≥ 0.08% (plus permissif)
- `0.12%` → Accepte ATR ≥ 0.12% (plus strict)

---

## ✅ RÉSULTAT

**Maintenant** :
- ✅ Slider ATR Optimal visible dans l'interface
- ✅ Range 0.05% à 1.0% avec step 0.01%
- ✅ Mise à jour automatique de la configuration backend
- ✅ Tous les sliders (SNR, Breakout, Wick, DI Gap, ATR) synchronisés avec le backend

**Prochaines étapes** (optionnel) :
- Charger les valeurs initiales depuis `/api/config` au chargement de la page
- Ajouter un slider pour `optimal_atr_min_5m` (5m timeframe)

---

## 🎯 REMARQUE

**Format de la valeur** :
- **Stockage** : Décimal (0.10 = 10%)
- **Affichage** : Format "X.XX%" (0.10%)
- **Backend** : Reçoit la valeur en décimal (0.10)

**Exemple** :
- Slider à 0.10 → Backend reçoit `0.10` → Affiche "0.10%"
- Slider à 0.15 → Backend reçoit `0.15` → Affiche "0.15%"




