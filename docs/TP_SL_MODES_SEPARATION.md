# 🔥 SÉPARATION DES MODES TP/SL - DOCUMENTATION CRITIQUE

## ⚠️ PROBLÈME RÉSOLU (17/01/2026)

**Problème initial :** Les modes TP/SL (FIXE/ATR/ESCALIER) partageaient incorrectement des paramètres, causant des comportements imprévisibles comme la stagnation en mode FIXE.

## 🎯 RÈGLES DE SÉPARATION STRICTE

### **Mode FIXE** 
- **Paramètres exclusifs :** `fixed_tp_pct`, `fixed_sl_pct`, `break_even_trigger` (en %)
- **Interdictions :**
  - ❌ Pas de paramètres ATR (`atr_mult_*`, `break_even_atr_mult`, etc.)
  - ❌ Pas de stagnation exit
  - ❌ Pas de régimes dynamiques (LOW/MEDIUM/HIGH volatilité)
  - ❌ Pas de `sl_max_pct` (limitation ATR uniquement)

### **Mode ATR**
- **Paramètres exclusifs :** `atr_mult_tp`, `atr_mult_sl`, `break_even_atr_mult`, `trailing_trigger_atr_mult`, etc.
- **Fonctionnalités :** Régimes dynamiques, stagnation exit, MFE protection
- **Interdictions :**
  - ❌ Pas d'utilisation des paramètres FIXE

### **Mode ESCALIER** 
- **Paramètres exclusifs :** `escalier_level*_pnl`, `escalier_level*_size`
- **Base :** Mode FIXE pour TP/SL de base, logique escalier pour sorties partielles
- **Interdictions :**
  - ❌ **NE DOIT PAS** hériter des paramètres ATR
  - ❌ Pas de stagnation exit
  - ❌ Pas de régimes dynamiques

## 🔧 CORRECTIONS APPLIQUÉES

### 1. Position Manager - Séparation des modes (`core/position_manager.py`)
```python
# AVANT (❌ INCORRECT)
use_atr = (tp_sl_mode == 'ATR' or tp_sl_mode == 'TP_MULTI' or tp_sl_mode == 'ESCALIER')

# APRÈS (✅ CORRECT)
use_atr = (tp_sl_mode == 'ATR') or self.config.use_atr
use_escalier = (tp_sl_mode in ['TP_MULTI', 'ESCALIER'])
is_fixe_mode = (tp_sl_mode == 'FIXE' and not use_atr and not use_escalier)
```

### 2. TP/SL Calculator - Isolation sl_max_pct (`core/position/tp_sl_calculator.py`)
```python
# AVANT (❌ INCORRECT)
from config import TRADING_CONFIG
sl_max_pct = TRADING_CONFIG.get('sl_max_pct', 0.50)
if sl_pct > sl_max_pct:
    logger.warning(f"⚠️ Mode FIXE: SL capped: {sl_pct:.2f}% → {sl_max_pct}% (max)")

# APRÈS (✅ CORRECT)
# Mode FIXE : utiliser directement les valeurs configurées sans limitation ATR
sl_pct = config.fixed_sl_pct
```

### 3. Stagnation Logic - ATR uniquement (`core/position_manager.py`)
```python
# AVANT (❌ INCORRECT)
use_atr = (tp_sl_mode in ['ATR', 'TP_MULTI', 'ESCALIER'])

# APRÈS (✅ CORRECT)
use_atr = (tp_sl_mode == 'ATR') or self.config.use_atr
if not use_atr:
    # 🔥 Mode FIXE/ESCALIER : Pas de stagnation exit
    logger.debug(f"🚫 Stagnation exit désactivée en mode {tp_sl_mode} (non-ATR)")
    return None
```

### 4. Break-Even Logic - Mode dépendant (`core/position_manager.py`)
```python
# AVANT (❌ INCORRECT)
break_even_use_atr = TRADING_CONFIG.get('break_even_use_atr', False)

# APRÈS (✅ CORRECT)
tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
break_even_use_atr = (tp_sl_mode == 'ATR') or self.config.use_atr
```

### 5. Trailing Logic - Mode dépendant (`core/position_manager.py`)
```python
# AVANT (❌ INCORRECT)
use_atr_trigger = (
    trailing_config.get('use_atr_trigger', False) or 
    TRADING_CONFIG.get('trailing_use_atr_trigger', False)
)

# APRÈS (✅ CORRECT)
tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
use_atr_trigger = (tp_sl_mode == 'ATR') or self.config.use_atr
```

### 6. Trailing MFE - ATR uniquement (`core/position_manager.py`)
```python
# AVANT (❌ INCORRECT)
if (TRADING_CONFIG.get('trailing_mfe_enabled', False) 
    and not self.active_position.trailing_mfe_triggered
    and self.active_position.max_pnl_reached is not None):

# APRÈS (✅ CORRECT)
tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
use_atr_for_mfe = (tp_sl_mode == 'ATR') or self.config.use_atr

if (use_atr_for_mfe
    and TRADING_CONFIG.get('trailing_mfe_enabled', False) 
    and not self.active_position.trailing_mfe_triggered
    and self.active_position.max_pnl_reached is not None):
```

### 7. WebSocket Handlers (`main.py`)
```python
# AVANT (❌ INCORRECT)
pos_cfg.use_atr = (tp_sl_mode == 'ATR' or tp_sl_mode == 'TP_MULTI' or tp_sl_mode == 'ESCALIER')

# APRÈS (✅ CORRECT)
pos_cfg.use_atr = (tp_sl_mode == 'ATR')
```

### 8. UI/Status Loop - Gating BE/Trailing/Stagnation/MFE (`core/callbacks/position_check_loop.py`)
```python
# AVANT (❌ INCORRECT)
break_even_use_atr = TRADING_CONFIG.get('break_even_use_atr', False)
trailing_use_atr_trigger = (
    trailing_config.get('use_atr_trigger', False)
    or TRADING_CONFIG.get('trailing_use_atr_trigger', False)
)
stagnation_enabled = TRADING_CONFIG.get('stagnation_exit_enabled', ...)

# APRÈS (✅ CORRECT)
tp_sl_mode = getattr(position, 'tp_sl_mode', None) or TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
use_atr_mode = (tp_sl_mode == 'ATR')
break_even_use_atr = use_atr_mode
trailing_use_atr_trigger = use_atr_mode
stagnation_enabled = use_atr_mode and TRADING_CONFIG.get('stagnation_exit_enabled', ...)
```

## 🚨 TESTS DE NON-RÉGRESSION

### Test Mode FIXE
```python
TRADING_CONFIG['tp_sl_mode'] = 'FIXE'
# Vérifier :
# ✅ Pas de paramètres ATR chargés
# ✅ Pas de stagnation exit
# ✅ SL respecte exactement fixed_sl_pct (pas de sl_max_pct)
```

### Test Mode ESCALIER  
```python
TRADING_CONFIG['tp_sl_mode'] = 'ESCALIER'
# Vérifier :
# ✅ use_atr = False
# ✅ Pas de régimes dynamiques (LOW/MEDIUM/HIGH)
# ✅ Pas de stagnation exit
# ✅ Logique escalier fonctionne avec paramètres FIXE de base
```

### Test Mode ATR
```python
TRADING_CONFIG['tp_sl_mode'] = 'ATR'
# Vérifier :
# ✅ use_atr = True
# ✅ Régimes dynamiques actifs
# ✅ Stagnation exit disponible
# ✅ Paramètres ATR chargés et appliqués
```

## 🎯 VALIDATION CONTINUE

### Points de contrôle à vérifier régulièrement :
1. **Aucun paramètre ATR ne doit être chargé en mode FIXE/ESCALIER**
2. **La stagnation ne doit jamais s'activer en mode FIXE/ESCALIER**
3. **Le mode ESCALIER ne doit jamais activer use_atr = True**
4. **Les régimes dynamiques ne doivent s'appliquer qu'en mode ATR**

### Comment détecter les régressions :
```bash
# Chercher les mélanges de paramètres suspects
grep -r "tp_sl_mode.*ESCALIER.*use_atr" .
grep -r "stagnation.*FIXE" .
grep -r "atr_mult.*FIXE" .
```

## 📋 HISTORIQUE DES CHANGEMENTS

**17/01/2026** - Séparation complète des modes :
- Position Manager corrigé
- TP/SL Calculator nettoyé
- Stagnation isolée au mode ATR
- WebSocket handlers mis à jour
- Documentation créée

---
**⚠️ IMPORTANT :** Ne jamais permettre aux modes de partager des paramètres à l'avenir. Chaque mode doit rester strictement isolé.
