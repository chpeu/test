# 🔍 Diagnostic : Colonnes vides dans scan_logs et opportunities

## Problème identifié

Les colonnes `spread_pct`, `book_depth`, `balance_score`, `bid_vol`, `ask_vol`, `book_imbalance` dans `scan_logs` et `score_long`, `score_short`, `score_min_required`, `trend_bonus`, `divergence_bonus`, `condition_count` dans `opportunities` sont vides.

## Cause racine

### 1. scan_logs - Colonnes de scalabilité vides

**Fichier** : `core/callbacks/scanner_loop.py` lignes 715-786

**Problème** : `scalability_data` est construit UNIQUEMENT si `_app_state.get('top_pairs')` existe.

```python
if _app_state and _app_state.get('top_pairs'):
    for pair in _app_state['top_pairs']:
        if pair.get('symbol') == symbol:
            # Construire scalability_data
```

**Si `top_pairs` est vide ou None** :
- `scalability_data` reste vide `{}`
- Les lignes 821-836 utilisent `scalability_data.get('spread')` → retourne `None`
- Les colonnes dans la base restent `NULL`

**Fallback présent mais insuffisant** (lignes 753-786) :
- Utilise `analysis.get('orderbook_check')` mais ces données ne sont pas toujours présentes
- Si `analysis` ne contient pas `orderbook_check`, `scalability_data` reste vide

### 2. opportunities - Colonnes de scores vides

**Fichier** : `core/callbacks/scanner_loop.py` lignes 908-948

**Problème** : Les scores sont extraits depuis `analysis` :

```python
score_long = analysis.get('score_long_1m') or analysis.get('score_long_5m')
score_short = analysis.get('score_short_1m') or analysis.get('score_short_5m')
```

**Si `analysis` ne contient pas ces clés** :
- `score_long` et `score_short` sont `None`
- Les colonnes dans la base restent `NULL`

## Solution

### Fix 1 : Garantir que `scalability_data` est toujours rempli

**Option A** : Forcer le scan de scalabilité AVANT le scan de setup
- Modifier `main.py` pour garantir que `top_pairs` est toujours à jour
- Appeler `scanner.scan_top_pairs()` avant chaque cycle de scan

**Option B** : Améliorer le fallback dans `scanner_loop.py`
- Si `top_pairs` est vide, récupérer les données directement depuis l'API
- Appeler `scanner.fetch_spread_data(symbol)` si `scalability_data` est vide

### Fix 2 : Garantir que `analysis` contient les scores

**Vérifier** : `core/analyzer.py` ou le module qui génère `analysis`
- S'assurer que `score_long_1m`, `score_short_1m`, etc. sont toujours calculés
- Ajouter des valeurs par défaut si les scores ne peuvent pas être calculés

## Tests de vérification

### 1. Vérifier que `top_pairs` est rempli

```python
# Dans scanner_loop.py, ligne 716
logger.info(f"💹 DEBUG: _app_state.get('top_pairs') = {_app_state.get('top_pairs') if _app_state else 'None'}")
if _app_state and _app_state.get('top_pairs'):
    logger.info(f"💹 DEBUG: top_pairs contient {len(_app_state['top_pairs'])} paires")
```

### 2. Vérifier que `scalability_data` est rempli

```python
# Dans scanner_loop.py, ligne 750
logger.info(f"💹 DEBUG: scalability_data après construction = {scalability_data}")
```

### 3. Vérifier que `analysis` contient les scores

```python
# Dans scanner_loop.py, ligne 908
logger.info(f"💹 DEBUG: analysis keys = {list(analysis.keys()) if analysis else 'None'}")
logger.info(f"💹 DEBUG: score_long_1m = {analysis.get('score_long_1m') if analysis else 'None'}")
```

## Prochaines étapes

1. Ajouter les logs de debug ci-dessus
2. Redémarrer le bot
3. Observer les logs pour identifier où `top_pairs` ou `analysis` sont vides
4. Appliquer le fix approprié (Option A ou B)
5. Vérifier que les nouvelles données ont les colonnes remplies
