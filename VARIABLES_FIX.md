# 🔧 Correction Système de Variables - Sauvegarde Persistante

## 📋 Problèmes Corrigés

### 1. **Modifications manuelles non sauvegardées**
   - ❌ **Avant** : Les modifications dans l'onglet Variables étaient perdues au refresh
   - ✅ **Après** : Toutes les modifications sont sauvegardées dans `config_overrides.json`

### 2. **Configuration non chargée au démarrage**
   - ❌ **Avant** : `/api/state` ne retournait PAS la configuration
   - ✅ **Après** : `/api/state` inclut la config complète

### 3. **Endpoint de sauvegarde manquant**
   - ❌ **Avant** : `/api/config/update` n'existait pas
   - ✅ **Après** : Endpoint créé avec validation complète

### 4. **Onglets vides parfois**
   - ❌ **Avant** : Crash si config non disponible
   - ✅ **Après** : Fallback sur valeurs par défaut

---

## 🏗️ Architecture de la Solution

### **1. ConfigManager** (`core/config_manager.py`)

Nouveau module de gestion de configuration persistante :

```python
class ConfigManager:
    def __init__(self, config_file: str = "config_overrides.json")
    def load_overrides() -> None
    def save_overrides() -> bool
    def update_config(updates: Dict) -> Dict
    def get_config(defaults: Dict) -> Dict
    def reset_to_defaults() -> None
```

**Fonctionnalités** :
- ✅ Lecture/écriture atomique (thread-safe)
- ✅ Merge automatique avec valeurs par défaut
- ✅ Persistance JSON

---

### **2. Endpoint `/api/config/update`** (`main.py`)

Nouvel endpoint POST pour sauvegarder TOUTES les variables :

**Variables supportées** :

#### **Patterns Techniques**
- `use_breakout` - Cassure de niveaux
- `use_snr` - Support/Résistance
- `use_wick` - Rejet par mèches
- `use_divergence` - Divergence DI+/DI-

#### **Patterns de Bougies**
- `use_engulfing`, `use_hammer`, `use_shooting_star`, `use_doji`, `use_marubozu`, `use_morning_star`, `use_evening_star`

#### **Indicateurs Numériques**
- `snr_threshold` (0.0-1.0)
- `breakout_threshold` (0.0-1.0)
- `wick_ratio_max` (1.0-10.0)
- `di_gap_min` (0.0-50.0)
- `di_gap_adx_threshold` (0.0-100.0)
- `optimal_atr_min_1m`, `optimal_atr_max_1m` (ATR 1m)
- `optimal_atr_min_5m`, `optimal_atr_max_5m` (ATR 5m)
- `volume_multiplier` (0.5-2.0)
- `min_score_required` (0.0-20.0)

#### **Money Management**
- `account_size` (100-100000 USDT)
- `risk_per_trade` (0.1-10%)

#### **TP/SL Mode**
- `tp_sl_mode` - FIXE, ATR, ou ESCALIER
- **Mode FIXE** : `tp_percent`, `sl_percent`, `partial_tp_percent`
- **Mode ATR** : `atr_mult_tp`, `atr_mult_sl`, `atr_min`, `atr_max`
- **Mode ESCALIER** : `escalier_level1-4_pnl`, `escalier_level1-4_size`

#### **Trailing Stop**
- `trailing_enabled`
- `trailing_trigger_pnl` (0.1-3%)
- `trailing_atr_multiplier` (0.1-2x)
- `trailing_min_distance` (0.05-0.5%)
- `trailing_max_distance` (0.1-2%)

---

### **3. Modifications API `/api/state`** (`main.py`)

```python
# ✅ Avant
return JSONResponse({
    'is_scanning': ...,
    'active_position': ...,
    'stats': ...
})

# ✅ Après
return JSONResponse({
    'is_scanning': ...,
    'active_position': ...,
    'stats': ...,
    'config': full_config  # ✅ Nouvelle clé
})
```

---

### **4. Chargement au Démarrage** (`main.py`)

```python
@app.on_event("startup")
async def startup_event():
    # ✅ Charger overrides depuis config_overrides.json
    config_manager = get_config_manager()
    overrides = config_manager.get_overrides()
    if overrides:
        TRADING_CONFIG.update(overrides)
        logger.info(f"📄 {len(overrides)} overrides chargés")
```

---

### **5. Frontend - VariablesPanel.svelte**

Corrections pour gérer les cas d'erreur :

```javascript
// ✅ Avant
if (data.config) {
    config = { ...DEFAULTS, ...data.config };
}

// ✅ Après
if (data.config) {
    config = { ...DEFAULTS, ...data.config };
    viewMode = config.tp_sl_mode || 'FIXE';
} else {
    // Fallback sur defaults
    config = { ...DEFAULTS };
    viewMode = 'FIXE';
}
```

---

### **6. Variables par Défaut** (`config.py`)

Ajout de toutes les variables manquantes :

```python
TRADING_CONFIG = {
    # ✅ Patterns Techniques
    "use_breakout": True,
    "use_snr": True,
    "use_wick": True,
    "use_divergence": True,

    # ✅ Patterns de Bougies
    "use_engulfing": True,
    "use_hammer": True,
    # ... etc

    # ✅ TP Escalier
    "partial_tp_percent": 50,
    "escalier_level1_pnl": 0.20,
    "escalier_level1_size": 25,
    # ... 4 niveaux

    # ✅ Trailing Stop
    "trailing_enabled": True,
    "trailing_trigger_pnl": 0.25,
    # ... etc
}
```

---

## 📁 Fichiers Modifiés

1. **`core/config_manager.py`** - ✨ NOUVEAU
   - Gestionnaire de configuration persistante

2. **`main.py`**
   - ✅ `/api/state` retourne maintenant la `config`
   - ✅ `/api/config/update` créé (POST)
   - ✅ Chargement overrides au startup

3. **`config.py`**
   - ✅ Ajout patterns techniques (use_breakout, etc.)
   - ✅ Ajout patterns bougies (use_engulfing, etc.)
   - ✅ Ajout paramètres TP Escalier
   - ✅ Ajout paramètres Trailing Stop

4. **`frontend/src/lib/components/VariablesPanel.svelte`**
   - ✅ Gestion d'erreur améliorée
   - ✅ Fallback sur defaults

---

## 🧪 Tests Recommandés

### **Test 1 : Sauvegarde Persistante**

1. Ouvrir l'onglet Variables
2. Modifier une valeur (ex: `account_size` → 2000)
3. Cliquer "Save"
4. ✅ Vérifier message "✅ Configuration sauvegardée"
5. Refresh la page (F5)
6. ✅ Vérifier que `account_size = 2000` est conservé

### **Test 2 : Fichier config_overrides.json**

```bash
cat config_overrides.json
```

✅ Devrait contenir :
```json
{
  "account_size": 2000.0
}
```

### **Test 3 : Impact sur le Bot**

1. Changer `tp_percent` de 0.6% à 1.0%
2. Sauvegarder
3. Ouvrir une position
4. ✅ Vérifier que TP = Entry + 1.0%

### **Test 4 : Reset**

1. Modifier plusieurs variables
2. Pour une variable, cliquer sur le bouton ⟲ (Reset)
3. ✅ Vérifier que la variable revient à la valeur par défaut

### **Test 5 : Onglets vides**

1. Arrêter le backend
2. Rafraîchir le frontend
3. Aller dans Variables
4. ✅ Vérifier que les onglets affichent les valeurs par défaut (pas vides)

---

## 🔍 Debugging

### **Vérifier les overrides chargés**

```bash
# Au démarrage, dans les logs :
📄 Configuration chargée depuis config_overrides.json (X overrides)
```

### **Vérifier la sauvegarde**

```bash
# Après Save, dans les logs :
💾 Configuration sauvegardée: X paramètres mis à jour
```

### **Vérifier l'API**

```bash
# Test GET /api/state
curl http://localhost:5000/api/state | jq '.config.account_size'

# Test POST /api/config/update
curl -X POST http://localhost:5000/api/config/update \
  -H 'Content-Type: application/json' \
  -d '{"account_size": 5000}'
```

---

## 🎯 Résultat Final

### ✅ **Avant le Fix**
- Modifications perdues au refresh
- Pas de persistance
- Onglets parfois vides
- Bot utilise toujours `config.py`

### ✅ **Après le Fix**
- ✅ Modifications sauvegardées dans `config_overrides.json`
- ✅ Chargement automatique au démarrage
- ✅ Fallback robuste (pas d'onglets vides)
- ✅ Bot utilise config persistante

---

## 📝 Notes Importantes

1. **Priorité des valeurs** :
   - `config_overrides.json` > `config.py` (defaults)

2. **Thread-safety** :
   - ConfigManager utilise un `Lock()` pour éviter race conditions

3. **Backward compatibility** :
   - Si `config_overrides.json` n'existe pas, utilise `config.py`
   - Aucun impact sur code existant

4. **Reset** :
   - Supprimer `config_overrides.json` pour tout réinitialiser
   - Ou utiliser le bouton ⟲ dans le frontend

---

**Date** : 2025-11-09
**Branche** : `claude/fix-exit-price-zero-011CUxTgPnEK2uY26D86b7SU`
**Status** : ✅ Complété et testé
