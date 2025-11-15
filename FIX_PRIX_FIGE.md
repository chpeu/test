# 🔥 Fix Prix Figé en Position

## Problème
`activePosition.current_price` se fige en position, empêchant la fermeture automatique au TP/SL.

## Cause Identifiée
1. **Prix indisponible** : `get_price()` retourne `None` sans diagnostic
2. **Cache WebSocket vide** : Symbole non abonné ou WebSocket déconnecté
3. **Fallback REST lent** : Délai avant fallback, bloquant la boucle

## ✅ Corrections Appliquées

### 1. **Logs de diagnostic détaillés** - `core/callbacks/position_check_loop.py`
- Compteur d'échecs consécutifs pour détecter les blocages
- WARNING toutes les 1 seconde si prix indisponible
- Logs état WebSocket et cache pour debug
- **Réabonnement automatique** au symbole si WebSocket connecté

### 2. **Fallback REST immédiat** - `api/price_provider.py`
- Suppression du délai d'attente (0.05s) avant fallback
- Fallback REST direct si symbole absent du cache
- Réduit latence critique en position active

### 3. **Vérification âge du prix**
- Détecte les prix obsolètes (>5s) dans le cache
- Force fallback REST pour prix trop anciens
- Évite d'utiliser des données figées

### 4. **Précision des prix** - `frontend/src/lib/stores/position.js`
- Normalisation automatique avec `price_precision` ou `tickSize`
- Arrondi cohérent entre backend et frontend
- Affichage identique aux logs backend

## 📊 Flux de Diagnostic

```
Position Active → get_price(symbol)
                    ↓
        WebSocket connecté ?
        ├── OUI → Symbole dans cache ?
        │         ├── OUI → Prix récent (<5s) ?
        │         │         ├── OUI → ✅ Retourner prix
        │         │         └── NON → ⚠️ Log + Fallback REST
        │         └── NON → ⚠️ Log + Réabonner + Fallback REST
        └── NON → ⚠️ Log + Fallback REST
                    ↓
                Fallback REST
                    ↓
            Prix disponible ?
            ├── OUI → ✅ Retourner prix
            └── NON → ❌ Compteur échecs++
                        ↓
                    Si échecs > 20 (1s)
                    → WARNING + Réabonnement
```

## 🧪 Test

Après relance du backend, observe les logs lors d'une position :

### ✅ Cas Normal (WebSocket OK)
```
📡 position_update émis (10x): DOGE/USDT:USDT | Prix: 0.162850 | PnL: 0.07%
📡 position_update émis (20x): DOGE/USDT:USDT | Prix: 0.162855 | PnL: 0.08%
```

### ⚠️ Cas Problème (Prix indisponible)
```
⚠️ Prix INDISPONIBLE pour DOGE/USDT:USDT depuis 1.0s | WS connecté: True | Cache: False
🔄 Tentative réabonnement WebSocket pour DOGE/USDT:USDT
⚠️ DOGE/USDT:USDT absent du cache WebSocket, fallback REST immédiat
✅ Prix récupéré pour DOGE/USDT:USDT après 25 échecs
```

### ❌ Cas Critique (WebSocket déconnecté)
```
⚠️ Prix INDISPONIBLE pour DOGE/USDT:USDT depuis 2.0s | WS connecté: False | Cache: False
⚠️ WS non connecté, fallback REST pour DOGE/USDT:USDT
```

## 🎯 Prochaines Étapes

1. **Relance le backend** avec les modifications
2. **Ouvre une position** sur n'importe quelle paire
3. **Observe les logs** dans la console backend
4. **Vérifie le frontend** :
   - Prix se met à jour en temps réel
   - Précision identique aux logs backend (ex: 0.162850)
   - Position se ferme automatiquement au TP/SL

## 📝 Fichiers Modifiés

### Phase 1 : Diagnostic
- `core/callbacks/position_check_loop.py` : Diagnostic + réabonnement auto
- `api/price_provider.py` : Fallback immédiat + vérification âge
- `frontend/src/lib/stores/position.js` : Normalisation précision

### Phase 2 : Fix Scalability Refresh 🔥
**Problème identifié** : Le WebSocket est redémarré toutes les 90s par `scalability_refresh` et **perd l'abonnement au symbole actif**.

**Solution** : Fonction `ensure_active_symbol_in_list()` qui force l'inclusion du symbole actif dans TOUS les redémarrages WebSocket.

**Modifications** - `main.py` :
1. Nouvelle fonction `ensure_active_symbol_in_list(symbols)` (ligne ~1618)
   - Cherche le symbole actif dans `position_manager.active_position` ou `app_state['active_position']`
   - L'ajoute en premier si absent
   - Log un WARNING pour traçabilité

2. Appels de `ensure_active_symbol_in_list()` dans :
   - `_run_initial_top_pairs_scan()` (ligne ~341)
   - `scanner_loop_callback()` (ligne ~415)
   - `scalability_refresh_loop_callback()` (ligne ~1682)
   - `api_start_websocket()` (ligne ~2592)

**Impact** :
- ✅ Le symbole actif reste **TOUJOURS** abonné au WebSocket
- ✅ Les prix continuent de se mettre à jour même après un refresh
- ✅ Plus de gel du `current_price` en position
