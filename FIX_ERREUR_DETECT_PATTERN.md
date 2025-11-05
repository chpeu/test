# 🔧 CORRECTION ERREUR "'list' object has no attribute 'get'" - DETECT_PATTERN

**Date**: 2025-11-03  
**Status**: ✅ **CORRIGÉ**

---

## 🐛 PROBLÈME IDENTIFIÉ

**Erreur** :
```
File "core\indicators.py", line 245, in detect_pattern
    open_price = candle.get('open', candle.get('o', 0))
                 ^^^^^^^^^^
AttributeError: 'list' object has no attribute 'get'
```

**Cause** :
- `ccxt.fetch_ohlcv()` retourne une **liste** de listes : `[[timestamp, open, high, low, close, volume], ...]`
- `current_candle = ohlcv[-1]` est donc une **liste** : `[timestamp, open, high, low, close, volume]`
- Mais `detect_pattern()` attendait un **dictionnaire** avec des clés comme `'open'`, `'high'`, etc.

---

## ✅ CORRECTION APPLIQUÉE

### 1. Correction de `detect_pattern()`

**Fichier** : `core/indicators.py` lignes 235-261

**Avant** :
```python
def detect_pattern(candle: Dict) -> str:
    open_price = candle.get('open', candle.get('o', 0))  # ← Erreur si liste
    high = candle.get('high', candle.get('h', 0))
    ...
```

**Après** :
```python
def detect_pattern(candle) -> str:
    # 🔥 FIX: Accepter liste OHLCV (format ccxt) ou dict
    if isinstance(candle, list):
        # Format OHLCV: [timestamp, open, high, low, close, volume]
        if len(candle) < 5:
            return 'NONE'
        open_price = float(candle[1])  # open
        high = float(candle[2])  # high
        low = float(candle[3])  # low
        close = float(candle[4])  # close
    elif isinstance(candle, dict):
        # Format dict: {'open': ..., 'high': ..., etc.}
        open_price = candle.get('open', candle.get('o', 0))
        high = candle.get('high', candle.get('h', 0))
        low = candle.get('low', candle.get('l', 0))
        close = candle.get('close', candle.get('c', 0))
    else:
        return 'NONE'
```

### 2. Correction de `detect_pattern_multi()`

**Fichier** : `core/indicators.py` lignes 289-341

**Problème** : Même problème avec les bougies multiples

**Solution** : Ajout de la détection de format pour `current` et `prev`

```python
# 🔥 FIX: Accepter liste OHLCV (format ccxt) ou dict
if isinstance(current, list):
    open_price = float(current[1])
    high = float(current[2])
    low = float(current[3])
    close = float(current[4])
elif isinstance(current, dict):
    open_price = current.get('open', current.get('o', 0))
    ...

# 🔥 FIX: Extraire valeurs de prev aussi si c'est une liste
if prev:
    if isinstance(prev, list):
        prev_open = float(prev[1])
        prev_close = float(prev[4])
    elif isinstance(prev, dict):
        prev_open = prev.get('open', prev.get('o', 0))
        ...
```

---

## 📊 FORMAT OHLCV CCXT

**Format retourné par `ccxt.fetch_ohlcv()`** :
```python
[
    [timestamp, open, high, low, close, volume],  # Bougie 1
    [timestamp, open, high, low, close, volume],  # Bougie 2
    ...
]
```

**Indices** :
- `[0]` : timestamp
- `[1]` : open
- `[2]` : high
- `[3]` : low
- `[4]` : close
- `[5]` : volume

---

## ✅ VALIDATION

- [x] `detect_pattern()` accepte liste et dict
- [x] `detect_pattern_multi()` accepte liste et dict
- [x] Extraction correcte des valeurs pour `prev` aussi
- [x] Pas d'erreurs de linting

**Le code est maintenant compatible avec le format OHLCV de ccxt !**



