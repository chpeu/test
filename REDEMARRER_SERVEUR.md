# 🔄 REDÉMARRER LE SERVEUR

**Date**: 2025-11-03  
**Status**: ⚠️ **ACTION REQUISE**

---

## 🐛 PROBLÈME

L'endpoint `/api/prices/live` retourne `{"detail":"Not Found"}`.

**Cause** : Le serveur n'a pas été redémarré après l'ajout du nouvel endpoint.

---

## ✅ SOLUTION

### 1. Arrêter le serveur

Dans le terminal où le serveur tourne :
- Appuyer sur `Ctrl+C` pour arrêter le serveur

### 2. Redémarrer le serveur

```bash
cd "C:\Users\sebta\Documents\code scalp\trade_cursor_py"
python main.py
```

Ou si vous utilisez uvicorn directement :
```bash
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

---

## 🧪 VÉRIFIER QUE ÇA FONCTIONNE

Après redémarrage, tester :

1. **Tous les prix** :
   ```
   http://localhost:5000/api/prices/live
   ```

2. **Prix d'une paire** :
   ```
   http://localhost:5000/api/price/SOL/USDT:USDT
   ```

---

## 📊 RÉSULTAT ATTENDU

Pour `/api/prices/live`, vous devriez voir :
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
    ...
  }
}
```

---

## ⚠️ NOTE IMPORTANTE

**Le serveur doit être redémarré** chaque fois qu'on modifie le code Python, notamment :
- Ajout/modification d'endpoints
- Changement de configuration
- Modification de la logique métier

**Exception** : Si vous utilisez `--reload` avec uvicorn, le serveur redémarre automatiquement.


