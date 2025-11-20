# ✅ FIX FINAL - Colonnes vides dans scan_logs et opportunities

## 🔍 Problème identifié

Les colonnes `spread_pct`, `book_depth`, `balance_score`, `bid_vol`, `ask_vol`, `book_imbalance` dans `scan_logs` étaient **toujours vides** car :

### Cause racine dans `main.py`

**Fichier** : `main.py` lignes 1358-1411

**Problème 1** : `scalability_data` ne contenait que 4 champs au lieu de 10
```python
# ❌ AVANT (INCOMPLET)
scalability_data = {
    'recent_volume': pair.get('recentVolume'),
    'vol5': pair.get('vol5'),
    'vol15': pair.get('vol15'),
    'scalability_score': pair.get('score'),
}
```

**Problème 2** : `scan_data['market_data']` utilisait `analysis.get('spread_pct')` au lieu de `scalability_data.get('spread_pct')`
```python
# ❌ AVANT (MAUVAISE SOURCE)
'market_data': {
    'price': scan_price,
    'spread_pct': analysis.get('spread_pct') if analysis else None,  # ❌ analysis ne contient pas spread_pct
    'book_depth': analysis.get('book_depth') if analysis else None,  # ❌ analysis ne contient pas book_depth
    ...
}
```

## ✅ Solution appliquée

### Fix 1 : Construction complète de `scalability_data` dans `main.py`

**Fichier modifié** : `main.py` lignes 1358-1434

```python
# ✅ APRÈS (COMPLET)
if app_state and app_state.get('top_pairs'):
    for pair in app_state.get('top_pairs', []):
        if pair.get('symbol') == symbol:
            spread_value = pair.get('spread') or pair.get('spread_pct')
            book_depth = pair.get('bookDepth')
            balance_score = pair.get('balanceScore')
            bid_vol = pair.get('bidVol')
            ask_vol = pair.get('askVol')
            if book_depth in (None, 0) and bid_vol and ask_vol:
                book_depth = bid_vol + ask_vol
            imbalance = None
            if bid_vol and ask_vol:
                try:
                    imbalance = bid_vol / ask_vol if ask_vol > 0 else None
                except Exception:
                    imbalance = None
            
            scalability_data = {
                'spread': spread_value,
                'spread_pct': spread_value,
                'bookDepth': book_depth,
                'book_depth': book_depth,
                'balanceScore': balance_score,
                'balance_score': balance_score,
                'bidVol': bid_vol,
                'askVol': ask_vol,
                'orderbook_imbalance_ratio': imbalance,
                'recent_volume': pair.get('recentVolume'),
                'recentVolume': pair.get('recentVolume'),
                'vol5': pair.get('vol5'),
                'vol15': pair.get('vol15'),
                'scalability_score': pair.get('score'),
                'score': pair.get('score')
            }
            logger.info(f"💹 DEBUG main.py: Scalability data trouvé pour {symbol}: spread={spread_value}, depth={book_depth}")
            break

# Fallback si top_pairs ne contient pas le symbole
if not scalability_data:
    logger.warning(f"⚠️ DEBUG main.py: scalability_data vide pour {symbol}, utilisation fallback depuis analysis")
    analysis_obj = analysis or {}
    orderbook_check = analysis_obj.get('orderbook_check') or {}
    bid_value = orderbook_check.get('bid_value') or analysis_obj.get('bid_vol')
    ask_value = orderbook_check.get('ask_value') or analysis_obj.get('ask_vol')
    book_depth = None
    if bid_value or ask_value:
        bid_value = bid_value or 0
        ask_value = ask_value or 0
        book_depth = bid_value + ask_value
    imbalance = None
    if bid_value and ask_value:
        try:
            imbalance = bid_value / ask_value if ask_value > 0 else None
        except Exception:
            imbalance = None

    scalability_data = {
        'spread': analysis_obj.get('spread_pct') or analysis_obj.get('spread'),
        'spread_pct': analysis_obj.get('spread_pct') or analysis_obj.get('spread'),
        'bookDepth': book_depth,
        'book_depth': book_depth,
        'balanceScore': analysis_obj.get('orderbook_balance'),
        'balance_score': analysis_obj.get('orderbook_balance'),
        'bidVol': bid_value,
        'askVol': ask_value,
        'orderbook_imbalance_ratio': imbalance,
        'recent_volume': analysis_obj.get('recent_volume'),
        'recentVolume': analysis_obj.get('recent_volume'),
        'vol5': analysis_obj.get('vol5'),
        'vol15': analysis_obj.get('vol15'),
        'scalability_score': analysis_obj.get('scalability_score'),
        'score': analysis_obj.get('scalability_score')
    }
    logger.info(f"⚠️ DEBUG main.py: Scalability data depuis fallback pour {symbol}: spread={scalability_data.get('spread')}, depth={book_depth}")
```

### Fix 2 : Utilisation de `scalability_data` dans `scan_data`

**Fichier modifié** : `main.py` lignes 1466-1487

```python
# ✅ APRÈS (BONNE SOURCE)
scan_data = {
    'scan_duration_ms': scan_duration_ms,
    'market_data': {
        'price': scan_price,
        # 🔥 FIX: Utiliser scalability_data au lieu de analysis pour les métriques de scalabilité
        'spread_pct': scalability_data.get('spread'),
        'book_depth': scalability_data.get('bookDepth'),
        'balance_score': scalability_data.get('balanceScore'),
        'bid_vol': scalability_data.get('bidVol'),
        'ask_vol': scalability_data.get('askVol'),
        # Calculer imbalance ratio si bid/ask disponibles
        'orderbook_imbalance_ratio': (
            scalability_data.get('bidVol') / scalability_data.get('askVol')
            if scalability_data.get('askVol') and scalability_data.get('askVol') > 0
            else None
        ),
        # Paramètres du scan de scalabilité
        'recent_volume': scalability_data.get('recent_volume'),
        'vol5': scalability_data.get('vol5'),
        'vol15': scalability_data.get('vol15'),
        'scalability_score': scalability_data.get('scalability_score'),
    },
    ...
}
```

### Fix 3 : Logs de debug ajoutés

**Logs ajoutés dans `main.py`** :
- `💹 DEBUG main.py: Scalability data trouvé pour {symbol}: spread={spread_value}, depth={book_depth}`
- `⚠️ DEBUG main.py: scalability_data vide pour {symbol}, utilisation fallback depuis analysis`
- `⚠️ DEBUG main.py: Scalability data depuis fallback pour {symbol}: spread={scalability_data.get('spread')}, depth={book_depth}`

**Logs ajoutés dans `scanner_loop.py`** (lignes 716-794) :
- `💹 DEBUG log_scan: _app_state existe={_app_state is not None}, top_pairs={'présent' if (_app_state and _app_state.get('top_pairs')) else 'absent'}`
- `💹 DEBUG log_scan: top_pairs contient {len(_app_state['top_pairs'])} paires`
- `✅ Scalability data trouvé pour {symbol} dans top_pairs: spread={spread_value}, depth={book_depth}`
- `⚠️ scalability_data vide après recherche dans top_pairs pour {symbol}`
- `⚠️ Scalability data depuis fallback (analysis) pour {symbol}: spread={scalability_data.get('spread')}, depth={book_depth}`

## 🎯 Actions requises

### 1. Redémarrer le bot

**IMPORTANT** : Les modifications ne seront actives qu'après redémarrage complet du bot.

```bash
# Arrêter le bot (Ctrl+C)
# Redémarrer
python main.py
```

### 2. Observer les nouveaux logs

Après redémarrage, vous devriez voir dans les logs :

```
2025-11-16 XX:XX:XX - INFO - 💹 DEBUG main.py: Scalability data trouvé pour SYMBOL: spread=0.018, depth=3052819.0
```

**Si vous voyez ce log** → `scalability_data` est correctement rempli ✅

**Si vous voyez** :
```
2025-11-16 XX:XX:XX - WARNING - ⚠️ DEBUG main.py: scalability_data vide pour SYMBOL, utilisation fallback depuis analysis
```
→ Le symbole n'est pas dans `top_pairs`, le fallback sera utilisé ⚠️

### 3. Vérifier les nouvelles données

**SQL pour vérifier les colonnes remplies** :

```sql
-- Derniers scans avec colonnes de scalabilité
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

**Résultat attendu** :
- `spread_pct` : valeur entre 0.01 et 0.5 (1% à 50%)
- `book_depth` : valeur > 0 (profondeur du carnet d'ordres)
- `balance_score` : valeur entre 0 et 1
- `bid_vol` et `ask_vol` : peuvent être NULL (normal si pas dans orderbook)
- `book_imbalance` : ratio bid/ask, peut être NULL

### 4. Exporter vers Excel

Après 5-10 minutes de fonctionnement :

1. Aller sur `http://localhost:5000/api/datalogger/export/excel`
2. Télécharger le fichier Excel
3. Ouvrir l'onglet `scan_logs`
4. Vérifier que les colonnes `spread_pct`, `book_depth`, `balance_score` sont **remplies** pour les nouvelles lignes

## 📊 Diagnostic si les colonnes sont encore vides

### Cas A : `top_pairs` est vide

**Logs à chercher** :
```
💹 DEBUG main.py: scalability_data vide pour TOUS les symboles
```

**Cause** : Le scan de scalabilité n'est pas exécuté ou échoue

**Solution** : Vérifier `main.py` ligne ~4500 où `scanner.scan_top_pairs()` est appelé

### Cas B : Le symbole n'est pas dans `top_pairs`

**Logs à chercher** :
```
⚠️ DEBUG main.py: scalability_data vide pour SYMBOL, utilisation fallback depuis analysis
⚠️ DEBUG main.py: Scalability data depuis fallback pour SYMBOL: spread=None, depth=None
```

**Cause** : Le symbole scanné n'est pas dans le top 30 des paires scalables

**Solution** : Normal, le fallback devrait fonctionner. Si `spread=None`, vérifier que `analysis` contient `orderbook_check` ou `spread_pct`

### Cas C : Fallback ne fonctionne pas

**Logs à chercher** :
```
⚠️ DEBUG main.py: Scalability data depuis fallback pour SYMBOL: spread=None, depth=None
```

**Cause** : `analysis` ne contient pas `orderbook_check` ou `spread_pct`

**Solution** : Vérifier que l'analyzer ajoute ces données dans l'objet `analysis`

## 📋 Checklist de vérification

- [ ] Bot redémarré avec les nouvelles modifications
- [ ] Logs observés pendant 5-10 minutes
- [ ] Log "💹 DEBUG main.py: Scalability data trouvé" apparaît pour au moins 1 symbole
- [ ] Nouvelles données dans la base ont les colonnes remplies (requête SQL ci-dessus)
- [ ] Export Excel téléchargé et vérifié
- [ ] Colonnes `spread_pct`, `book_depth`, `balance_score` sont remplies pour les nouvelles lignes

## 🔥 FIX SUPPLÉMENTAIRE - Colonnes opportunities vides

### Problème identifié (2ème partie)

Les colonnes `score_long`, `score_short`, `score_min_required`, `trend_bonus`, `divergence_bonus`, `condition_count` dans `opportunities` étaient vides car :

**Fichier** : `main.py` lignes 1554-1576

**Problème** : `opportunity_data` ne contenait pas ces champs

```python
# ❌ AVANT (INCOMPLET)
opportunity_data = {
    'status': 'PENDING',
    'direction': analysis.get('direction'),
    'setup_score': analysis.get('score_total') or analysis.get('totalScore'),
    'conditions_matched': analysis.get('condition_types', []) or analysis.get('signals', []),
    'entry_price': analysis.get('entry') or analysis.get('price'),
    'tp_price': analysis.get('tp'),
    'sl_price': analysis.get('sl'),
    'tp_sl_mode': TRADING_CONFIG.get('tp_sl_mode', 'FIXE'),
    'size_usdt': None,
    'risk_usdt': None,
    'reward_risk_ratio': None,
}
```

### Solution appliquée

**Fichier modifié** : `main.py` lignes 1554-1596

**IMPORTANT** : Les clés correctes dans `analysis` sont `long_score` et `short_score`, **pas** `score_long_1m` ou `score_long_5m`.

```python
# ✅ APRÈS (COMPLET - AVEC BONNES CLÉS)
if scan_data['is_opportunity'] and analysis:
    condition_list = analysis.get('condition_types', []) or analysis.get('signals', [])
    
    # 🔥 FIX: Les clés correctes sont 'long_score' et 'short_score'
    score_long = analysis.get('long_score')
    score_short = analysis.get('short_score')
    
    # Fallback: essayer aussi les anciennes clés si les nouvelles ne sont pas présentes
    if score_long is None:
        score_long = analysis.get('score_long_1m') or analysis.get('score_long_5m')
    if score_short is None:
        score_short = analysis.get('score_short_1m') or analysis.get('score_short_5m')
    
    # Fallback: chercher dans scan_data['scores'] si toujours None
    if score_long is None and 'scores' in scan_data:
        score_long = scan_data['scores'].get('score_long_1m') or scan_data['scores'].get('score_long_5m')
    if score_short is None and 'scores' in scan_data:
        score_short = scan_data['scores'].get('score_short_1m') or scan_data['scores'].get('score_short_5m')
    
    min_required = scan_data['params_snapshot'].get('min_score_required')
    trend_bonus = scan_data.get('trend_bonus')
    divergence_bonus = scan_data.get('divergence_bonus')
    setup_reason = analysis.get('reason')
    
    opportunity_data = {
        'status': 'PENDING',
        'direction': analysis.get('direction'),
        'setup_score': analysis.get('score_total') or analysis.get('totalScore'),
        'score_long': score_long,
        'score_short': score_short,
        'score_min_required': min_required,
        'trend_bonus': trend_bonus,
        'divergence_bonus': divergence_bonus,
        'conditions_matched': condition_list,
        'condition_count': len(condition_list),
        'setup_reason': setup_reason,
        'entry_suggested': analysis.get('entry') or analysis.get('price'),
        'tp_suggested': analysis.get('tp'),
        'sl_suggested': analysis.get('sl'),
        'tp_sl_mode': analysis.get('tp_sl_mode', 'FIXE'),
        # Legacy
        'entry_price': analysis.get('entry') or analysis.get('price'),
        'tp_price': analysis.get('tp'),
        'sl_price': analysis.get('sl'),
        'size_usdt': None,
        'risk_usdt': None,
        'reward_risk_ratio': None,
    }
```

### Vérification des nouvelles données (opportunities)

**SQL pour vérifier les colonnes remplies** :

```sql
-- Dernières opportunités avec colonnes de scores
SELECT 
    id,
    timestamp,
    symbol,
    direction,
    setup_score,
    score_long,
    score_short,
    score_min_required,
    trend_bonus,
    divergence_bonus,
    condition_count
FROM opportunities
WHERE timestamp > NOW() - INTERVAL '10 minutes'
ORDER BY timestamp DESC
LIMIT 20;
```

**Résultat attendu** :
- `score_long` : valeur entre 0 et 15 (score LONG)
- `score_short` : valeur entre 0 et 15 (score SHORT)
- `score_min_required` : valeur du seuil minimum (ex: 1.0, 7.5)
- `trend_bonus` : valeur entre 0 et 2 (bonus de tendance)
- `divergence_bonus` : valeur entre 0 et 2 (bonus de divergence)
- `condition_count` : nombre de conditions validées (ex: 2, 3, 4)

## 🎯 Résumé

**Fichiers modifiés** :
1. `main.py` (lignes 1358-1487) : Construction complète de `scalability_data` et utilisation dans `scan_data`
2. `main.py` (lignes 1554-1596) : Ajout des champs manquants dans `opportunity_data`
3. `scanner_loop.py` (lignes 716-794) : Logs de debug (déjà appliqués précédemment)

**Prochaines étapes** :
1. Redémarrer le bot
2. Observer les logs pendant 5-10 minutes
3. Vérifier les nouvelles données dans la base (scan_logs ET opportunities)
4. Exporter vers Excel et vérifier les colonnes

**Si les colonnes sont encore vides après redémarrage** :
- Partager les logs contenant "💹 DEBUG main.py"
- Partager le résultat des requêtes SQL ci-dessus
- Je pourrai alors diagnostiquer plus précisément le problème
