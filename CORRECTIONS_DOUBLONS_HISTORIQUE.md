# 🔧 Corrections : Doublons dans l'historique des trades

## 📋 Problèmes identifiés

### 1. Erreur `'Position' object has no attribute 'tp_sl_mode'`
**Erreur** :
```
⚠️ Erreur logging Analytics DB: 'Position' object has no attribute 'tp_sl_mode'
```

**Cause** : La classe `Position` n'a pas d'attribut `tp_sl_mode`, mais le code essayait d'y accéder dans `close_position()` lors du logging vers `AnalyticsDatabase`.

**Solution** : Récupérer `tp_sl_mode` depuis `TRADING_CONFIG` au lieu de l'objet `Position`.

**Fichier modifié** : `core/position_manager.py` (ligne ~1604-1606)

```python
# 🔥 FIX: Récupérer tp_sl_mode depuis TRADING_CONFIG (Position n'a pas cet attribut)
from config import TRADING_CONFIG
tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')

trade_data = {
    # ...
    'tp_sl_mode': tp_sl_mode,  # 🔥 FIX: Utiliser valeur depuis config
    # ...
}
```

---

### 2. Doublons dans l'historique (deux lignes par trade)

**Symptôme** : Chaque trade apparaît deux fois dans l'historique avec des données légèrement différentes (une ligne avec "INVALID" et PnL négatif, une autre avec "N/A" et PnL à 0).

**Causes identifiées** :
1. Le frontend reçoit `position_closed` via SocketIO et ajoute le trade à `stats.tradeHistory`
2. `restoreAllState()` récupère les trades depuis `/api/state` et peut ajouter les mêmes trades avec un format différent
3. La détection des doublons n'était pas assez robuste (seulement par `closure_id` ou `timestamp + symbol`)

**Solutions implémentées** :

#### A. Amélioration de la détection des doublons dans SocketIO `position_closed`

**Fichier modifié** : `templates/index.html` (ligne ~768-807)

- Vérification par `closure_id` (le plus fiable)
- Fallback : vérification par `symbol + timestamp + reason` avec tolérance de 3 secondes
- Vérification sur les 10 derniers trades au lieu de 5

```javascript
// Vérifier par closure_id (le plus fiable)
if (closureId) {
    // ... vérification par closure_id
}

// Fallback: vérifier par symbol + timestamp + reason (plus robuste)
if (!alreadyCounted && stats.tradeHistory && stats.tradeHistory.length > 0) {
    for (var i = 0; i < Math.min(stats.tradeHistory.length, 10); i++) {
        var trade = stats.tradeHistory[i];
        if (trade && trade.symbol === result.symbol) {
            var timeDiff = Math.abs((trade.timestamp || 0) - resultTimestamp);
            if (timeDiff < 3000) {
                var tradeReason = trade.reason || trade.exit_reason || '';
                if (!tradeReason || tradeReason === resultReason || timeDiff < 1000) {
                    alreadyCounted = true;
                    break;
                }
            }
        }
    }
}
```

#### B. Fusion intelligente dans `restoreAllState()`

**Fichier modifié** : `templates/index.html` (ligne ~4862-4923)

- Au lieu de remplacer `stats.tradeHistory`, fusionner intelligemment
- Créer un Set des trades existants (par `symbol + timestamp + reason`)
- Ajouter seulement les trades qui ne sont pas déjà présents
- Normaliser le format des trades depuis l'API vers le format frontend

```javascript
// Créer un Set des trades existants (par symbol + timestamp + reason)
var existingKeys = new Set();
existingHistory.forEach(function(trade) {
    var key = (trade.symbol || '') + '_' + (trade.timestamp || 0) + '_' + (trade.reason || trade.exit_reason || '');
    existingKeys.add(key);
});

// Ajouter seulement les trades qui ne sont pas déjà présents
var newTrades = [];
apiTrades.forEach(function(trade) {
    var tradeTimestamp = trade.start_time ? (new Date(trade.start_time).getTime()) : (trade.timestamp || Date.now());
    var tradeReason = trade.exit_reason || trade.reason || 'UNKNOWN';
    var key = (trade.symbol || '') + '_' + tradeTimestamp + '_' + tradeReason;
    
    if (!existingKeys.has(key)) {
        // Convertir format API vers format frontend
        var tradeRecord = {
            // ... conversion du format
        };
        newTrades.push(tradeRecord);
        existingKeys.add(key);
    }
});

// Fusionner : nouveaux trades en premier, puis existants
stats.tradeHistory = newTrades.concat(existingHistory);
```

---

## ✅ Résultats attendus

1. **Plus d'erreur `tp_sl_mode`** : Le logging vers `AnalyticsDatabase` fonctionne correctement
2. **Plus de doublons** : Chaque trade n'apparaît qu'une seule fois dans l'historique
3. **Détection robuste** : Les doublons sont détectés même si le format des données est différent entre SocketIO et l'API
4. **Fusion intelligente** : `restoreAllState()` ne crée plus de doublons lors du refresh de la page

---

## 🧪 Tests recommandés

1. **Test fermeture position** :
   - Ouvrir une position
   - La fermer (TP, SL, ou EARLY_INVALIDATION)
   - Vérifier qu'il n'y a qu'une seule ligne dans l'historique

2. **Test refresh page** :
   - Ouvrir une position
   - La fermer
   - Rafraîchir la page (F5)
   - Vérifier qu'il n'y a toujours qu'une seule ligne dans l'historique

3. **Test EARLY_INVALIDATION** :
   - Ouvrir une position qui sera invalidée précocement
   - Vérifier qu'il n'y a qu'une seule ligne avec la raison "EARLY_INVALIDATION"

---

## 📝 Notes techniques

- La détection des doublons utilise maintenant `symbol + timestamp + reason` comme clé unique
- La tolérance de temps est de 3 secondes (3000ms) pour gérer les différences de timing
- Le format des trades depuis l'API est normalisé vers le format frontend dans `restoreAllState()`
- Les trades sont fusionnés au lieu d'être remplacés pour préserver les trades ajoutés via SocketIO

---

*Corrections implémentées le 2025-11-07*

