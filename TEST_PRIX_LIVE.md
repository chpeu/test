# 🔍 TEST PRIX EN TEMPS RÉEL

**Date**: 2025-11-03  
**Status**: ✅ **ENDPOINT CRÉÉ**

---

## 🎯 OBJECTIF

Vérifier que le système récupère bien les prix en temps réel via WebSocket.

---

## 📊 ENDPOINTS DISPONIBLES

### 1. `/api/price/{symbol}` - Prix d'une paire

**Exemple** :
```bash
GET http://localhost:5000/api/price/SOL/USDT:USDT
```

**Réponse** :
```json
{
  "symbol": "SOL/USDT:USDT",
  "lastPrice": 175.42,
  "volume24": 1234567890,
  "high24": 176.50,
  "low24": 174.30,
  "timestamp": 1699027200.123,
  "_source": "WebSocket",  // ou "REST"
  "_age_seconds": 0.05     // Âge du prix en secondes
}
```

### 2. `/api/prices/live` - Tous les prix en cache WebSocket

**Exemple** :
```bash
GET http://localhost:5000/api/prices/live
```

**Réponse** :
```json
{
  "websocket_connected": true,
  "cache_size": 9,
  "timestamp": 1699027200.123,
  "prices": {
    "SOL/USDT:USDT": {
      "price": 175.42,
      "volume24": 1234567890,
      "age_seconds": 0.05,
      "timestamp": 1699027200.078
    },
    "ADA/USDT:USDT": {
      "price": 0.45,
      "volume24": 987654321,
      "age_seconds": 0.12,
      "timestamp": 1699027200.011
    }
    // ... autres paires
  }
}
```

---

## 🔍 COMMENT TESTER

### Option 1: Navigateur

1. Ouvrir `http://localhost:5000/api/prices/live` dans votre navigateur
2. Vérifier que `websocket_connected` est `true`
3. Vérifier que `cache_size` > 0
4. Vérifier que `age_seconds` est faible (< 1 seconde = temps réel)

### Option 2: curl

```bash
# Tous les prix
curl http://localhost:5000/api/prices/live

# Prix d'une paire spécifique
curl http://localhost:5000/api/price/SOL/USDT:USDT
```

### Option 3: JavaScript (Console navigateur)

```javascript
// Tous les prix
fetch('/api/prices/live')
  .then(r => r.json())
  .then(data => {
    console.log('WebSocket connecté:', data.websocket_connected);
    console.log('Nombre de prix:', data.cache_size);
    console.log('Prix:', data.prices);
  });

// Prix d'une paire
fetch('/api/price/SOL/USDT:USDT')
  .then(r => r.json())
  .then(data => {
    console.log('Prix:', data.lastPrice);
    console.log('Source:', data._source);
    console.log('Âge:', data._age_seconds, 'secondes');
  });
```

---

## ✅ CRITÈRES DE VALIDATION

- [ ] `websocket_connected` = `true`
- [ ] `cache_size` > 0 (au moins les top pairs)
- [ ] `age_seconds` < 1 seconde pour tous les prix (temps réel)
- [ ] `_source` = "WebSocket" pour les prix en cache
- [ ] Les prix se mettent à jour automatiquement (rafraîchir la page plusieurs fois)

---

## 🔧 DIAGNOSTIC

### Si `websocket_connected` = `false`
- Le WebSocket n'est pas connecté
- Vérifier les logs pour voir les erreurs de connexion
- Vérifier que le scanner a bien démarré (il démarre le WebSocket automatiquement)

### Si `cache_size` = 0
- Aucun prix en cache
- Le WebSocket est peut-être connecté mais ne reçoit pas de messages
- Vérifier les logs WebSocket

### Si `age_seconds` > 5
- Les prix ne sont plus mis à jour
- Le WebSocket est peut-être déconnecté
- Vérifier la connexion WebSocket

---

## 📝 NOTES

- Les prix sont mis à jour en temps réel via WebSocket MEXC
- Le cache est mis à jour à chaque message WebSocket reçu
- Si WebSocket déconnecté, fallback automatique sur REST
- Format des symboles : `SOL/USDT:USDT` (format ccxt standardisé)



