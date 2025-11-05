# 🔧 ENDPOINT CONFIGURATION - 4 SEUILS

**Date**: 2025-11-04  
**Status**: ✅ **CRÉÉ**

---

## 📋 ENDPOINTS CRÉÉS

### **1. GET `/api/config`** - Récupérer la configuration

**Description** : Récupère tous les paramètres configurables actuels

**Réponse** :
```json
{
  "volume_multiplier": 1.0,
  "use_confluence": false,
  "tp_sl_mode": "FIXE",
  "tp_percent": 0.25,
  "sl_percent": 0.25,
  "snr_threshold": 0.3,
  "breakout_threshold": 0.3,
  "wick_ratio_max": 2.5,
  "di_gap_min": 5,
  "di_gap_adx_threshold": 25
}
```

**Exemple** :
```bash
curl http://localhost:5000/api/config
```

---

### **2. POST `/api/config`** - Modifier la configuration

**Description** : Modifie un ou plusieurs paramètres à la volée

**Body** :
```json
{
  "snr_threshold": 0.25,
  "breakout_threshold": 0.4,
  "wick_ratio_max": 3.0,
  "di_gap_min": 7,
  "di_gap_adx_threshold": 30
}
```

**Réponse** :
```json
{
  "status": "updated",
  "updated": {
    "snr_threshold": 0.25,
    "breakout_threshold": 0.4,
    "wick_ratio_max": 3.0,
    "di_gap_min": 7,
    "di_gap_adx_threshold": 30
  }
}
```

**Exemple** :
```bash
curl -X POST http://localhost:5000/api/config \
  -H "Content-Type: application/json" \
  -d '{"snr_threshold": 0.25, "breakout_threshold": 0.4}'
```

---

## 🎯 4 SEUILS CONFIGURABLES

### **1. SNR Threshold** (`snr_threshold`)

**Description** : Signal-to-Noise Ratio minimum  
**Défaut** : `0.3`  
**Range** : `0.0 - 1.0`  
**Utilisation** : Filtre les signaux trop plats (prix proche de EMA21)

**Exemple** :
```json
{ "snr_threshold": 0.25 }  // Plus permissif (accepte signaux plus plats)
{ "snr_threshold": 0.4 }   // Plus strict (rejette signaux plats)
```

---

### **2. Breakout Threshold** (`breakout_threshold`)

**Description** : Multiplicateur pour calculer le seuil de breakout (× ATR)  
**Défaut** : `0.3`  
**Range** : `0.0 - 1.0`  
**Utilisation** : Filtre les prix qui ne sont pas en breakout (dans range ±ATR×threshold autour de EMA21)

**Exemple** :
```json
{ "breakout_threshold": 0.2 }  // Plus permissif (accepte prix proche EMA21)
{ "breakout_threshold": 0.5 }  // Plus strict (rejette prix proche EMA21)
```

---

### **3. Wick Ratio Max** (`wick_ratio_max`)

**Description** : Ratio maximum wick/body avant rejet (manipulation)  
**Défaut** : `2.5`  
**Range** : `1.0 - 10.0`  
**Utilisation** : Filtre les bougies avec wicks suspects (possible manipulation)

**Exemple** :
```json
{ "wick_ratio_max": 2.0 }  // Plus strict (rejette wicks importants)
{ "wick_ratio_max": 4.0 }  // Plus permissif (accepte wicks plus grands)
```

---

### **4. DI Gap Min** (`di_gap_min`)

**Description** : Gap minimum DI+ - DI- pour validation  
**Défaut** : `5`  
**Range** : `0.0 - 50.0`  
**Utilisation** : Filtre les setups avec ADX mais gap DI insuffisant

**Exemple** :
```json
{ "di_gap_min": 3 }  // Plus permissif (accepte gaps plus petits)
{ "di_gap_min": 8 }  // Plus strict (rejette gaps petits)
```

---

### **5. DI Gap ADX Threshold** (`di_gap_adx_threshold`)

**Description** : Seuil ADX minimum pour activer le filtre DI Gap  
**Défaut** : `25`  
**Range** : `0.0 - 100.0`  
**Utilisation** : ADX minimum requis pour que le DI Gap soit pris en compte

**Exemple** :
```json
{ "di_gap_adx_threshold": 20 }  // Plus permissif (active plus tôt)
{ "di_gap_adx_threshold": 30 }  // Plus strict (active plus tard)
```

---

## 🔄 VALIDATION ET CLAMPING

Tous les paramètres sont validés et clampés pour éviter les valeurs invalides :

- **snr_threshold** : `0.0 - 1.0`
- **breakout_threshold** : `0.0 - 1.0`
- **wick_ratio_max** : `1.0 - 10.0`
- **di_gap_min** : `0.0 - 50.0`
- **di_gap_adx_threshold** : `0.0 - 100.0`

---

## 📝 EXEMPLES D'UTILISATION

### **Modifier un seul seuil**
```bash
curl -X POST http://localhost:5000/api/config \
  -H "Content-Type: application/json" \
  -d '{"snr_threshold": 0.25}'
```

### **Modifier plusieurs seuils**
```bash
curl -X POST http://localhost:5000/api/config \
  -H "Content-Type: application/json" \
  -d '{
    "snr_threshold": 0.25,
    "breakout_threshold": 0.4,
    "wick_ratio_max": 3.0
  }'
```

### **Modifier tous les seuils**
```bash
curl -X POST http://localhost:5000/api/config \
  -H "Content-Type: application/json" \
  -d '{
    "snr_threshold": 0.25,
    "breakout_threshold": 0.4,
    "wick_ratio_max": 3.0,
    "di_gap_min": 7,
    "di_gap_adx_threshold": 30
  }'
```

---

## ✅ RÉSULTAT

**Maintenant** :
- ✅ Les 4 seuils sont modifiables à la volée via POST `/api/config`
- ✅ Les valeurs sont validées et clampées
- ✅ Les modifications sont immédiatement actives (pas besoin de redémarrer)
- ✅ Les logs montrent les modifications effectuées
- ✅ Le frontend peut utiliser ces endpoints pour synchroniser les sliders

---

## 🔍 VÉRIFICATION

**Test 1 : Récupérer config**
```bash
GET /api/config
# Vérifier valeurs par défaut
```

**Test 2 : Modifier un seuil**
```bash
POST /api/config { "snr_threshold": 0.25 }
# Vérifier logs : "✅ Configuration mise à jour: {'snr_threshold': 0.25}"
```

**Test 3 : Vérifier que c'est appliqué**
```bash
GET /api/config
# Vérifier que snr_threshold = 0.25
```

---

## 📌 NOTES

- **Persistance** : Les modifications sont en mémoire (perdues au redémarrage)
- **Synchronisation** : Les modifications sont immédiatement utilisées par `scan_pair_for_setup()`
- **Validation** : Les valeurs invalides sont clampées (pas d'erreur)
- **Logs** : Toutes les modifications sont loggées pour traçabilité


