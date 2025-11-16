# ✅ Corrections appliquées - Colonnes vides

## Problèmes identifiés et corrigés

### 1. Erreur WebSocket "await wasn't used with future" ✅

**Fichiers modifiés** :
- `api/price_provider.py` (lignes 240-257)
- `main.py` (lignes 908-923)
- `core/callbacks/scanner_loop.py` (lignes 425-435)

**Corrections** :
- Ajout délai 0.5s après `stop_websocket()` avant `start_websocket()`
- Vérification que WebSocket est prêt avant réabonnement
- Gestion erreurs individuelles pour chaque symbole
- Traceback pour debug

### 2. Logs de debug pour colonnes vides ✅

**Fichier modifié** :
- `core/callbacks/scanner_loop.py` (lignes 716-794)

**Logs ajoutés** :
```python
# Ligne 716: Vérifier si top_pairs existe
logger.info(f"💹 DEBUG log_scan: _app_state existe={_app_state is not None}, top_pairs={'présent' if (_app_state and _app_state.get('top_pairs')) else 'absent'}")

# Ligne 718: Compter les paires dans top_pairs
logger.info(f"💹 DEBUG log_scan: top_pairs contient {len(_app_state['top_pairs'])} paires")

# Ligne 752: Confirmer quand scalability_data est trouvé
logger.info(f"✅ Scalability data trouvé pour {symbol} dans top_pairs: spread={spread_value}, depth={book_depth}")

# Ligne 757: Warning si scalability_data est vide
logger.warning(f"⚠️ scalability_data vide après recherche dans top_pairs pour {symbol}")

# Ligne 794: Log du fallback
logger.info(f"⚠️ Scalability data depuis fallback (analysis) pour {symbol}: spread={scalability_data.get('spread')}, depth={book_depth}")
```

## 🔍 Diagnostic à effectuer

### Étape 1 : Redémarrer le bot

```bash
# Arrêter le bot actuel
# Redémarrer avec les nouvelles corrections
python main.py
```

### Étape 2 : Observer les logs

Chercher dans les logs :

1. **WebSocket** :
   ```
   ✅ WebSocket redémarré pour position: SYMBOL UNIQUEMENT
   ```
   - Si vous voyez encore "❌ Erreur redémarrage WebSocket", le délai de 0.5s n'est pas suffisant

2. **top_pairs** :
   ```
   💹 DEBUG log_scan: top_pairs contient X paires
   ```
   - Si X = 0 → `top_pairs` est vide, c'est la cause des colonnes vides
   - Si X > 0 → `top_pairs` est rempli, vérifier si le symbole est trouvé

3. **scalability_data** :
   ```
   ✅ Scalability data trouvé pour SYMBOL dans top_pairs
   ```
   OU
   ```
   ⚠️ scalability_data vide après recherche dans top_pairs pour SYMBOL
   ```
   - Si vide → le symbole n'est pas dans `top_pairs` ou `top_pairs` est vide

### Étape 3 : Identifier la cause

**Cas A : `top_pairs` est vide**
- Cause : Le scan de scalabilité n'est pas exécuté ou échoue
- Solution : Vérifier `main.py` ligne ~4500 où `scanner.scan_top_pairs()` est appelé

**Cas B : `top_pairs` est rempli mais le symbole n'est pas trouvé**
- Cause : Le symbole scanné n'est pas dans le top 30
- Solution : Normale, le fallback depuis `analysis` devrait fonctionner

**Cas C : Fallback depuis `analysis` ne fonctionne pas**
- Cause : `analysis` ne contient pas `orderbook_check` ou `spread_pct`
- Solution : Vérifier que l'analyzer ajoute ces données

## 📊 Vérification des données

### SQL pour vérifier les nouvelles données

```sql
-- Derniers scans avec timestamp
SELECT 
    id,
    timestamp,
    symbol,
    spread_pct,
    book_depth,
    balance_score,
    bid_vol,
    ask_vol,
    book_imbalance
FROM scan_logs
WHERE timestamp > NOW() - INTERVAL '10 minutes'
ORDER BY timestamp DESC
LIMIT 20;
```

### Résultat attendu

**Si les corrections fonctionnent** :
- `spread_pct`, `book_depth`, `balance_score` ne sont PAS NULL
- `bid_vol`, `ask_vol` peuvent être NULL (normal si pas dans orderbook)

**Si les colonnes sont encore vides** :
- Vérifier les logs pour identifier quelle étape échoue
- Partager les logs avec moi pour diagnostic approfondi

## 🐛 Problème position SHIB fermée en TS

### Logs fournis

```
2025-11-16 01:44:14,189 - INFO - 🟢 POSITION OUVERTE (Auto): LONG SHIB/USDT:USDT | Entry: 0.000009 | Size: 20.00 USDT
2025-11-16 01:44:14,204 - INFO - 🔴 POSITION FERMÉE: SHIB/USDT:USDT | Raison: TS | PnL net: -0.01% (0.0280 USDT)
```

### Analyse

**Durée de la position** : ~0.015 secondes (15ms)

**Cause probable** :
1. Le prix d'entrée et le trailing stop sont identiques ou très proches
2. Le trailing stop se déclenche immédiatement après l'ouverture
3. Bug dans le calcul du trailing stop pour les paires à très faible prix (0.000009)

### Solution

**Vérifier** : `core/position_manager.py` méthode de calcul du trailing stop
- Pour SHIB avec prix = 0.000009, le TS doit être calculé avec suffisamment de décimales
- Vérifier que `entry * (1 + ts_percent)` ne donne pas `entry` à cause de l'arrondi

**Fix temporaire** :
- Augmenter le seuil minimal du trailing stop pour les paires à faible prix
- Ou désactiver le trailing stop pour les paires < 0.0001

## 📋 Checklist de vérification

- [ ] Bot redémarré avec les nouvelles corrections
- [ ] Logs observés pendant 5-10 minutes
- [ ] `top_pairs` contient des paires (log "💹 DEBUG log_scan: top_pairs contient X paires")
- [ ] `scalability_data` est trouvé pour au moins 1 symbole (log "✅ Scalability data trouvé")
- [ ] Nouvelles données dans la base ont les colonnes remplies (requête SQL ci-dessus)
- [ ] Erreur WebSocket "await wasn't used with future" n'apparaît plus
- [ ] Position SHIB ou similaire ne se ferme plus immédiatement en TS

## 🎯 Prochaines étapes

1. **Redémarrer le bot**
2. **Attendre 5-10 minutes** pour collecter des logs
3. **Partager les logs** qui contiennent "💹 DEBUG log_scan"
4. **Exporter vers Excel** et vérifier les colonnes pour les nouvelles lignes
5. **Si encore vide** : Partager les logs complets pour diagnostic approfondi
