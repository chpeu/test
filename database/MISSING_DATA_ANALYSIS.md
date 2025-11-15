# 🔍 ANALYSE - Colonnes vides dans la base

**Date**: 2025-11-16  
**Problème**: Certaines colonnes sont vides alors que des données sont présentes

---

## 📊 DONNÉES ACTUELLES

### Tables complètement vides (✅ NORMAL)
```
✅ features_engineered    - Pour ML feature engineering (pas encore implémenté)
✅ market_context         - Pour contexte marché agrégé ML (pas encore implémenté)
✅ model_predictions      - Pour prédictions ML futures (pas encore implémenté)
```

**Raison**: Ces tables sont prévues pour le pipeline ML qui n'est pas encore actif.

---

## ⚠️ COLONNES VIDES DANS TABLES ACTIVES

### 1. Table `scan_logs` (1160 scans)

#### Colonnes vides ou quasi-vides
```sql
-- Résultats requête
total: 1160
with_spread_pct: 35 (3%)        ❌ PROBLÈME
with_book_depth: 0 (0%)         ❌ PROBLÈME
with_balance_score: 0 (0%)      ❌ PROBLÈME
with_rsi_1m: 1160 (100%)        ✅ OK
with_macd_1m: 575 (~50%)        ⚠️ PARTIEL
```

#### Colonnes de scalabilité manquantes
- `spread_pct`: 0%
- `book_depth`: 0%
- `balance_score`: 0%
- `bid_vol`: probablement 0%
- `ask_vol`: probablement 0%
- `orderbook_imbalance_ratio`: probablement 0%

#### Cause identifiée
**Code actuel** (`scanner_loop.py` lignes 750-766):
```python
'market_data': {
    'price': scan_price,
    'spread_pct': analysis.get('spread_pct') if analysis else None,
    'book_depth': analysis.get('book_depth') if analysis else None,
    'balance_score': analysis.get('balance_score') if analysis else None,
    'bid_vol': analysis.get('bid_vol') if analysis else None,
    'ask_vol': analysis.get('ask_vol') if analysis else None,
    'orderbook_imbalance_ratio': analysis.get('orderbook_imbalance_ratio') if analysis else None,
    # ...
}
```

**Problème**: Ces données ne sont PAS dans `analysis` (retour de l'analyzer).  
Ces métriques de scalabilité sont calculées ailleurs mais pas transmises à `market_data`.

**Impact ML**: ⚠️ MOYEN
- Ces features sont utiles mais pas critiques
- Les indicateurs techniques (RSI, MACD, EMA, ADX, etc.) sont présents
- La décision de trading ne dépend pas principalement de ces métriques

---

### 2. Table `opportunities` (35 opportunités)

#### Colonnes vides
```sql
-- Résultats requête
total: 35
with_score_min_required: 0 (0%)     ❌ PROBLÈME
with_trend_bonus: 0 (0%)            ❌ PROBLÈME
with_divergence_bonus: 0 (0%)       ❌ PROBLÈME
with_setup_score: 35 (100%)         ✅ OK
with_score_long: 0 (0%)             ❌ PROBLÈME
with_score_short: 0 (0%)            ❌ PROBLÈME
```

#### Colonnes manquantes
- `score_min_required`
- `trend_bonus`
- `divergence_bonus`
- `score_long`
- `score_short`
- `condition_count`

#### Cause identifiée
**Code actuel** (`scanner_loop.py` lignes 838-849):
```python
opportunity_data = {
    'status': 'PENDING',
    'direction': analysis.get('direction'),
    'setup_score': analysis.get('score_total'),
    'conditions_matched': analysis.get('condition_types', []),
    'entry_price': analysis.get('entry') or analysis.get('price'),
    'tp_price': analysis.get('tp'),
    'sl_price': analysis.get('sl'),
    # ... seulement 7-8 champs
}
```

**Problème**: Le code ne transmet que quelques champs alors que beaucoup plus de données sont disponibles dans `analysis` et `scan_data`:
- `score_long_1m`, `score_short_1m` (dans `analysis`)
- `trend_bonus` (dans `scan_data.trend_bonus`)
- `divergence_bonus` (dans `scan_data.divergence_bonus`)
- `min_score_required` (dans `scan_data.params_snapshot`)

**Code datalogger** (`postgresql_datalogger.py` lignes 684-692):
```python
query = """
    INSERT INTO opportunities (
        scan_log_id, session_id, symbol, timestamp,
        status, direction, setup_score,
        conditions_matched, entry_suggested, tp_suggested, sl_suggested,
        tp_sl_mode
    )
    VALUES (...)
"""
```

**Problème double**:
1. Le scanner ne transmet pas toutes les données dans `opportunity_data`
2. Le datalogger n'insère que 11 colonnes sur ~25 disponibles

**Impact ML**: ⚠️ MOYEN À ÉLEVÉ
- `score_long`/`score_short`: Utiles pour analyser la confiance directionnelle
- `trend_bonus`/`divergence_bonus`: Utiles pour feature importance
- `score_min_required`: Important pour comprendre le seuil de validation

---

## 🔧 SOLUTIONS RECOMMANDÉES

### Option A: Correction complète (recommandée)

#### 1. Corriger `scan_logs` - Données scalabilité

**Ajouter dans `scanner_loop.py`** (récupérer scalability_data correctement):
```python
# Ligne ~750, dans la construction de scan_data
'market_data': {
    'price': scan_price,
    # 🔥 FIX: Utiliser scalability_data au lieu de analysis
    'spread_pct': scalability_data.get('spread'),
    'book_depth': scalability_data.get('bookDepth'),
    'balance_score': scalability_data.get('balanceScore'),
    'bid_vol': scalability_data.get('bidVol'),
    'ask_vol': scalability_data.get('askVol'),
    # Calculer imbalance_ratio si disponible
    'orderbook_imbalance_ratio': (
        scalability_data.get('bidVol') / scalability_data.get('askVol')
        if scalability_data.get('askVol') and scalability_data.get('askVol') > 0
        else None
    ),
    # ...
}
```

#### 2. Corriger `opportunities` - Scores et bonus

**Modifier `scanner_loop.py` lignes 838-849**:
```python
opportunity_data = {
    'status': 'PENDING',
    'direction': analysis.get('direction'),
    'setup_score': analysis.get('score_total'),
    
    # 🔥 FIX: Ajouter scores détaillés
    'score_long': analysis.get('score_long_1m') or analysis.get('score_long_5m'),
    'score_short': analysis.get('score_short_1m') or analysis.get('score_short_5m'),
    'score_min_required': scan_data['params_snapshot'].get('min_score_required'),
    
    # 🔥 FIX: Ajouter bonus
    'trend_bonus': scan_data.get('trend_bonus'),
    'divergence_bonus': scan_data.get('divergence_bonus'),
    
    # Existant
    'conditions_matched': analysis.get('condition_types', []),
    'condition_count': len(analysis.get('condition_types', [])),
    'entry_suggested': analysis.get('entry') or analysis.get('price'),
    'tp_suggested': analysis.get('tp'),
    'sl_suggested': analysis.get('sl'),
    'tp_sl_mode': analysis.get('tp_sl_mode', 'FIXE'),
    'setup_reason': analysis.get('reason'),
}
```

**Modifier `postgresql_datalogger.py` ligne 684**:
```python
query = """
    INSERT INTO opportunities (
        scan_log_id, session_id, symbol, timestamp,
        status, direction, setup_score,
        score_long, score_short, score_min_required,
        trend_bonus, divergence_bonus,
        conditions_matched, condition_count,
        entry_suggested, tp_suggested, sl_suggested,
        tp_sl_mode, setup_reason
    )
    VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id
"""

params = (
    scan_id, session_id, symbol,
    str(status) if status else 'PENDING',
    str(direction) if direction else None,
    float(setup_score) if setup_score is not None else None,
    # Nouveaux champs
    float(opportunity_data.get('score_long')) if opportunity_data.get('score_long') else None,
    float(opportunity_data.get('score_short')) if opportunity_data.get('score_short') else None,
    float(opportunity_data.get('score_min_required')) if opportunity_data.get('score_min_required') else None,
    float(opportunity_data.get('trend_bonus')) if opportunity_data.get('trend_bonus') else None,
    float(opportunity_data.get('divergence_bonus')) if opportunity_data.get('divergence_bonus') else None,
    # Existant
    conditions_matched,
    len(conditions_matched),
    float(entry_price) if entry_price is not None else None,
    float(tp_price) if tp_price is not None else None,
    float(sl_price) if sl_price is not None else None,
    str(tp_sl_mode) if tp_sl_mode else 'FIXE',
    opportunity_data.get('setup_reason')
)
```

---

### Option B: Laisser en l'état (acceptable pour MVP)

#### Rationale
1. **Pour ML**: Les indicateurs techniques principaux sont tous présents (100% pour RSI, EMAs, ADX, ATR, BB, etc.)
2. **Métriques de scalabilité**: Utiles mais non critiques pour la décision de trading
3. **Scores détaillés opportunities**: Le `setup_score` global est présent (essentiel)

#### Limitations acceptables
- Pas de feature engineering sur scalabilité détaillée
- Pas d'analyse de la confiance directionnelle (score_long vs score_short)
- Pas d'attribution de performance aux bonus (trend, divergence)

---

## 📈 RECOMMANDATION FINALE

### 🟢 ACTION RECOMMANDÉE: **Option A - Correction complète**

**Raison**:
1. ✅ Facile à implémenter (2 fichiers à modifier)
2. ✅ Améliore significativement la richesse des données ML
3. ✅ Pas d'impact performance (données déjà calculées)
4. ✅ Utile pour feature importance et optimisation paramètres

**Priorité**: MOYENNE
- Pas bloquant pour démarrer le ML
- Mais améliorera significativement l'analyse quand plus de données disponibles

**Impact attendu**:
- 🔥 **+6 features scalabilité** par scan (spread, depth, balance, bid/ask vol, imbalance)
- 🔥 **+7 features opportunité** (score_long/short, min_required, bonus, condition_count, reason)
- 🔥 **Meilleure attribution** de la performance aux features spécifiques

---

## 📋 CHECKLIST IMPLÉMENTATION

### Phase 1: Corriger scan_logs (scalabilité)
- [ ] Modifier `scanner_loop.py` ligne ~755 (market_data)
- [ ] Tester avec 1 scan
- [ ] Vérifier colonnes remplies dans DB

### Phase 2: Corriger opportunities (scores)
- [ ] Modifier `scanner_loop.py` ligne ~838 (opportunity_data)
- [ ] Modifier `postgresql_datalogger.py` ligne ~684 (INSERT query)
- [ ] Modifier `postgresql_datalogger.py` ligne ~732 (params)
- [ ] Tester avec 1 opportunité
- [ ] Vérifier colonnes remplies dans DB

### Phase 3: Vérification
- [ ] Laisser bot tourner 10 scans
- [ ] Vérifier complétude données avec requête SQL
- [ ] Mettre à jour `ML_READINESS_REPORT.md`

---

**Rapport généré le**: 2025-11-16 00:45 UTC+01:00  
**Analysé par**: Cascade AI  
**Statut**: ⚠️ DONNÉES PARTIELLES - Correction recommandée
