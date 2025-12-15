# 🔧 Fix Prix Manquants - Scanner & PostgreSQL Logger

**Date**: 24 novembre 2025 - 20h05  
**Problème**: Erreurs `Prix manquant` et `Format ticker invalide` bloquent le logging PostgreSQL

---

## ⚠️ PROBLÈME IDENTIFIÉ

### **Erreurs Observées**

```
WARNING:api.price_provider:⚠️ Format ticker invalide (attendu dict, reçu NoneType) pour APT/USDT:USDT - Pas de cache disponible
ERROR:core.postgresql_datalogger:❌ Prix manquant pour APT/USDT:USDT dans log_scan (batch), scan non ajouté au buffer

WARNING:api.price_provider:⚠️ Format ticker invalide (attendu dict, reçu NoneType) pour TRUMPOFFICIAL/USDT:USDT - Pas de cache disponible
ERROR:core.postgresql_datalogger:❌ Prix manquant pour TRUMPOFFICIAL/USDT:USDT dans log_scan (batch), scan non ajouté au buffer
```

### **Cause Racine**

1. **price_provider** retourne `None` quand :
   - Le ticker REST API est invalide (NoneType)
   - Aucun cache disponible (frais ou périmé)
   - Erreur de connexion Exchange

2. **postgresql_datalogger** refuse de logger si `price is None` :
   - Contrainte `NOT NULL` sur colonne `price`
   - Bloque tout le scan pour cette paire
   - Perte de données d'analyse ML

3. **Impact** :
   - Scans perdus pour certaines paires (APT, TRUMPOFFICIAL, etc.)
   - Dataset ML incomplet
   - Pas de tracking de rejections pour ces symboles

---

## ✅ SOLUTIONS IMPLÉMENTÉES

### **1. Amélioration price_provider.py**

#### **Fallback Cascade Amélioré**

**Avant** :
```python
if not isinstance(ticker, dict) or ticker is None:
    cached = await self._get_cached_price(symbol)
    if cached:
        return cached
    # Pas de cache → return None ❌
    logger.warning(f"Format ticker invalide pour {symbol} - Pas de cache disponible")
    return None
```

**Après** :
```python
if not isinstance(ticker, dict) or ticker is None:
    # 1. Cache valide (< 60s)
    cached = await self._get_cached_price(symbol)
    if cached:
        return cached
    
    # 2. Cache périmé (> 60s mais existe)
    if symbol in self.price_cache:
        expired_cache = self.price_cache[symbol]
        logger.warning(f"Utilisation cache périmé pour {symbol}")
        return expired_cache
    
    # 3. Prix par défaut (dernier recours)
    logger.warning(f"Format ticker invalide pour {symbol} - Retour prix par défaut")
    return {
        "symbol": symbol,
        "lastPrice": 0.0,
        "volume24": 0,
        "timestamp": time.time(),
        "fallback": True  # Flag pour identifier
    }
```

#### **Avantages**

- ✅ **Jamais de retour None** → Always return dict
- ✅ **Cache périmé utilisable** → Mieux que rien
- ✅ **Prix par défaut final** → Permet logging même sans prix
- ✅ **Flag `fallback`** → Identifier les prix douteux pour ML

---

### **2. Amélioration postgresql_datalogger.py**

#### **Mode Batch**

**Avant** :
```python
if price is None:
    logger.error(f"❌ Prix manquant pour {symbol}, scan non ajouté au buffer")
    return None  # ❌ Bloque tout le scan
```

**Après** :
```python
if price is None or price == 0:
    if price is None:
        price = 0.0
        logger.warning(f"⚠️ Prix manquant pour {symbol}, utilisation price=0")
    # Continuer le logging avec price=0 ✅
```

#### **Mode Direct** 

**Avant** :
```python
if price is None:
    logger.error(f"❌ Prix manquant pour {symbol}, insertion annulée")
    return None  # ❌ Perte de données
```

**Après** :
```python
if price is None or price == 0:
    if price is None:
        price = 0.0
        logger.warning(f"⚠️ Prix manquant pour {symbol}, utilisation price=0")
    # Continuer le logging avec price=0 ✅
```

#### **Avantages**

- ✅ **Aucune perte de scan** → Tous les scans sont loggés
- ✅ **price=0 au lieu de NULL** → Respecte contrainte DB
- ✅ **Warning au lieu d'ERROR** → Moins alarmiste
- ✅ **Dataset ML complet** → Toutes les paires trackées

---

## 📊 IMPACT SUR LE ML

### **Avant (Problème)**

```
Scans perdus:
- APT/USDT:USDT → ❌ Non loggé
- TRUMPOFFICIAL/USDT:USDT → ❌ Non loggé
- Autres paires avec prix invalides → ❌ Non loggées

Dataset ML incomplet:
- Manque exemples de rejections
- Biais dans les features
- Moins de données d'entraînement
```

### **Après (Fix)**

```
Tous les scans loggés:
- APT/USDT:USDT → ✅ Loggé avec price=0
- TRUMPOFFICIAL/USDT:USDT → ✅ Loggé avec price=0
- Toutes les paires → ✅ Loggées

Dataset ML complet:
- Toutes les rejections capturées
- Features complètes (sauf price)
- Maximum de données d'entraînement
```

### **Gestion ML des price=0**

Pour l'analyse ML, on peut :

1. **Filtrer les lignes avec price=0** (si nécessaire)
   ```sql
   SELECT * FROM scan_logs WHERE price > 0
   ```

2. **Identifier les scans avec fallback**
   - Scanner les logs pour `"fallback": true` dans metadata
   - Flag dans une nouvelle colonne `price_fallback BOOLEAN`

3. **Feature engineering**
   - Créer feature binaire : `has_valid_price` (0 ou 1)
   - Utiliser comme feature supplémentaire

---

## 🔍 VÉRIFICATION

### **Tester les corrections**

```python
# Test price_provider
from api.price_provider import get_price_provider

provider = get_price_provider()

# Symbole problématique
price_data = await provider.get_price("APT/USDT:USDT")

assert price_data is not None, "Ne devrait jamais être None"
assert isinstance(price_data, dict), "Doit être un dict"
assert "lastPrice" in price_data, "Doit avoir lastPrice"

print(f"Prix APT: {price_data}")
# Résultat attendu: {"symbol": "APT/USDT:USDT", "lastPrice": 0.0 ou prix valide, ...}
```

### **Vérifier PostgreSQL**

```sql
-- Vérifier scans avec price=0
SELECT 
    symbol,
    price,
    timestamp,
    reject_reason
FROM scan_logs
WHERE price = 0
ORDER BY timestamp DESC
LIMIT 20;
```

**Résultat attendu** :
```
symbol                       | price | timestamp           | reject_reason
----------------------------|-------|---------------------|---------------
APT/USDT:USDT               | 0.0   | 2025-11-24 20:05:00 | Prix invalide
TRUMPOFFICIAL/USDT:USDT     | 0.0   | 2025-11-24 20:04:30 | Prix invalide
```

---

## 📁 FICHIERS MODIFIÉS

| Fichier | Modifications | Lignes |
|---------|---------------|--------|
| **`api/price_provider.py`** | Fallback cascade amélioré (cache périmé + prix par défaut) | 314-392 |
| **`core/postgresql_datalogger.py`** | Permettre price=0 au lieu de bloquer (batch + direct) | 414-419, 552-557 |

---

## 🎯 RÉSUMÉ

### **Problème** ❌
- `price_provider` retournait `None` pour certains symboles
- `postgresql_datalogger` refusait de logger si `price is None`
- Perte de données de scan pour paires problématiques

### **Solution** ✅
- `price_provider` retourne **toujours** un dict (cache périmé ou prix=0 en fallback)
- `postgresql_datalogger` accepte `price=0` et continue le logging
- **Aucune perte de données**, même avec prix invalides

### **Impact ML** 📊
- Dataset complet avec toutes les paires
- Feature `price` peut être 0 (filtrable si nécessaire)
- Plus de données d'entraînement
- Rejections capturées pour toutes les paires

---

## 🚀 PROCHAINES ÉTAPES (Optionnel)

### **1. Ajouter colonne `price_fallback` dans scan_logs**

```sql
ALTER TABLE scan_logs ADD COLUMN price_fallback BOOLEAN DEFAULT FALSE;
```

Modifier logger pour setter `price_fallback=TRUE` quand `price_data.get('fallback') is True`.

### **2. Feature ML supplémentaire**

```python
# Dans feature_loader.py
df['has_valid_price'] = (df['price'] > 0).astype(int)
```

### **3. Monitoring des fallbacks**

```sql
-- Compter scans avec prix fallback
SELECT 
    DATE_TRUNC('hour', timestamp) as hour,
    COUNT(*) FILTER (WHERE price = 0) as fallback_count,
    COUNT(*) as total_count,
    ROUND(COUNT(*) FILTER (WHERE price = 0)::NUMERIC / COUNT(*) * 100, 2) as fallback_pct
FROM scan_logs
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour DESC;
```

---

**✅ Fix complet appliqué - Aucune perte de données de scan**
