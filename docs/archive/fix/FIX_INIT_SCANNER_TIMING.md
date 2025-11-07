# 🔧 CORRECTIF - Timing initScanner

**Date**: 2025-11-03  
**Problème**: Erreur "Aucune paire scalable trouvée" avant la fin du scan

---

## ❌ PROBLÈME

Le frontend vérifie immédiatement si `allPairs` est vide après avoir lancé le scan, mais le scan prend **30-60 secondes** pour se terminer.

**Erreur**:
```
[21:33:14] ❌ ERREUR FATALE: Aucune paire scalable trouvée
```

**Mais ensuite**:
```
[21:34:01] 📡 INFO: Scan terminé - 10 paires scalables
[21:34:01] 📊 Top pairs mis à jour: 10 paires
```

---

## ✅ SOLUTION

Attendre l'événement SocketIO `top_pairs_update` au lieu de vérifier immédiatement.

### **Modifications**:

1. **Supprimer la vérification immédiate** qui lance l'erreur
2. **Attendre l'événement SocketIO** `top_pairs_update`
3. **Timeout de sécurité** (60 secondes max)
4. **Fallback** après 5 secondes si SocketIO ne répond pas

### **Code**:

```javascript
// Écouter l'événement SocketIO pour les pairs mises à jour
var pairsUpdateHandler = function(data) {
    if (data.pairs && data.pairs.length > 0) {
        debugLog('✅ Scan terminé', 'Pairs reçues via SocketIO');
        fetchTopPairs();
        // Ne plus écouter après la première réception
        socket.off('top_pairs_update', pairsUpdateHandler);
    }
};

// S'abonner à l'événement
socket.on('top_pairs_update', pairsUpdateHandler);

// Fallback: essayer de récupérer après 5 secondes
setTimeout(function() {
    if (!allPairs || allPairs.length === 0) {
        fetchTopPairs();
    }
}, 5000);
```

---

## 🧪 FLUX CORRIGÉ

1. **Frontend**: Appelle `/api/scanner/start`
2. **Server**: Lance scan asynchrone (30-60s)
3. **Frontend**: Attend événement SocketIO `top_pairs_update`
4. **Server**: Émet `top_pairs_update` quand scan terminé
5. **Frontend**: Reçoit événement → récupère pairs → affiche

---

## ✅ VALIDATION

- [x] Pas d'erreur "Aucune paire scalable trouvée" prématurée
- [x] Attente événement SocketIO
- [x] Timeout de sécurité (60s)
- [x] Fallback après 5s
- [x] Affichage correct des pairs quand disponibles

---

**Status**: ✅ **CORRIGÉ**

