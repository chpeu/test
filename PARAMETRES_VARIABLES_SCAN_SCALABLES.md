# 📊 Paramètres Variables Provenant du Scan des Paires Scalables

## Vue d'ensemble

Le scan des paires scalables (`ScalabilityScanner.scan_top_pairs()`) calcule et retourne plusieurs paramètres variables pour chaque paire. Ces paramètres sont utilisés pour :
- Calculer un score de scalabilité
- Filtrer les meilleures paires pour le trading
- Estimer le slippage lors de l'ouverture de positions
- Logger les données dans PostgreSQL

---

## 🔍 Paramètres Calculés par Paire

### 1. **Données de Prix et Volume**

| Paramètre | Type | Description | Source |
|-----------|------|-------------|--------|
| `symbol` | `str` | Symbole de la paire (ex: `SOL/USDT:USDT`) | Paramètre d'entrée |
| `price` | `float` | Prix actuel (dernier close) | `klines[-1][4]` (dernier close) |
| `recentVolume` | `float` | Volume total des 5 dernières bougies 1m | `sum(volumes[-5:])` |
| `vol5` | `float` | Volatilité sur 5 périodes (écart-type normalisé en %) | `calculate_volatility(closes, 5)` |
| `vol15` | `float` | Volatilité sur 15 périodes (écart-type normalisé en %) | `calculate_volatility(closes, 15)` |

**Formule volatilité** :
```python
volatilité = (écart_type / moyenne) * 100
```

---

### 2. **Données du Carnet d'Ordres (Orderbook)**

Ces paramètres sont récupérés via `fetch_spread_data()` qui analyse les 5 meilleurs niveaux du carnet d'ordres :

| Paramètre | Type | Description | Calcul |
|-----------|------|-------------|--------|
| `spread` | `float` | Spread en % entre best_bid et best_ask | `((best_ask - best_bid) / mid_price) * 100` |
| `bookDepth` | `float` | Profondeur totale du carnet (somme des 5 premiers niveaux) | `sum(bid_volumes) + sum(ask_volumes)` |
| `bidVol` | `float` | Volume total côté bid (achat) sur 5 niveaux | `sum(bids[:5][1])` |
| `askVol` | `float` | Volume total côté ask (vente) sur 5 niveaux | `sum(asks[:5][1])` |
| `balanceScore` | `float` | Score d'équilibre bid/ask (0-1) | `1 - (abs(bid_ask_ratio - 0.5) * 2)` |

**Formule balanceScore** :
```python
bid_ask_ratio = bidVol / (bidVol + askVol)
balanceScore = 1 - (abs(bid_ask_ratio - 0.5) * 2)
# 1.0 = parfaitement équilibré (50/50)
# 0.0 = complètement déséquilibré (100/0 ou 0/100)
```

---

### 3. **Score de Scalabilité**

| Paramètre | Type | Description | Calcul |
|-----------|------|-------------|--------|
| `score` | `float` | Score final de scalabilité (utilisé pour classer les paires) | `calculate_score(pair, max_volume, max_depth)` |

**Formule du score** :
```python
# Ratio volatilité/spread
vol_spread_ratio = vol5 / spread

# Facteur de normalisation (volume + depth)
norm_factor = 0.5 * (recentVolume / max_volume) + 0.5 * (bookDepth / max_depth)

# Bonus balance
balance_bonus = balanceScore

# Score brut
raw_score = vol_spread_ratio * log10(recentVolume + 1) * norm_factor * balance_bonus
```

**Filtres appliqués avant calcul du score** :
- `spread` doit être entre **0.001%** et **0.02%**
- `bookDepth` doit être **> 0**
- `recentVolume` doit être **≥ 100,000**
- `balanceScore` doit être **≥ TRADING_CONFIG['balance_score_min']**

---

## 📋 Structure Complète d'une Paire Scalable

```python
{
    # Identifiant
    'symbol': 'SOL/USDT:USDT',
    
    # Métadonnées
    'maker': 0.0,  # Fee maker (0% pour paires sélectionnées)
    'taker': 0.0,  # Fee taker (0% pour paires sélectionnées)
    
    # Prix et volume
    'price': 144.24,
    'recentVolume': 1250000.0,  # Volume 5 dernières bougies
    'vol5': 0.85,  # Volatilité 5 périodes (%)
    'vol15': 1.2,  # Volatilité 15 périodes (%)
    
    # Carnet d'ordres
    'spread': 0.0069,  # Spread en %
    'bookDepth': 103961.0,  # Profondeur totale
    'bidVol': 58774.0,  # Volume bid
    'askVol': 45187.0,  # Volume ask
    'balanceScore': 0.869,  # Score d'équilibre (0-1)
    
    # Score final
    'score': 12.45  # Score de scalabilité (utilisé pour classement)
}
```

---

## 🔄 Utilisation dans le Code

### 1. **Stockage dans `app_state`**
```python
top_pairs = await scanner.scan_top_pairs(n=20)
app_state['top_pairs'] = top_pairs  # Liste de 20 paires triées par score décroissant
```

### 2. **Récupération lors de l'ouverture de position**
```python
# Dans main.py ou scanner_loop.py
for pair in top_pairs:
    if pair['symbol'] == symbol:
        scalability_data = {
            'spread_pct': pair.get('spread', 0),
            'depth': pair.get('bookDepth', 0),
            'balance': pair.get('balanceScore', 1.0),
            'bidVol': pair.get('bidVol', 0),
            'askVol': pair.get('askVol', 0)
        }
```

### 3. **Estimation du slippage**
```python
# Dans position_manager.py
slippage_pct = _estimate_slippage(
    order_size=20.0,
    spread_pct=scalability_data['spread_pct'],
    depth=scalability_data['depth'],
    balance_score=scalability_data['balance']
)
```

### 4. **Logging dans PostgreSQL**
Ces paramètres sont loggés dans la table `trades` :
- `entry_spread_pct` : Spread au moment de l'entrée
- `entry_book_depth` : Profondeur du carnet à l'entrée
- `entry_balance_score` : Balance score à l'entrée
- `exit_spread_pct` : Spread au moment de la sortie
- `exit_book_depth` : Profondeur du carnet à la sortie
- `exit_balance_score` : Balance score à la sortie

---

## ⚠️ Valeurs par Défaut en Cas d'Erreur

Si le scan d'une paire échoue, les valeurs suivantes sont utilisées :
```python
{
    'recentVolume': 0,
    'vol5': 0,
    'vol15': 0,
    'spread': float('nan'),
    'bookDepth': 0,
    'balanceScore': 0,
    'bidVol': 0,
    'askVol': 0,
    'price': 0
}
```

---

## 📊 Fréquence de Mise à Jour

- **Scan initial** : Au démarrage du bot
- **Refresh périodique** : Toutes les **90 secondes** (configurable via `scalability_refresh_interval`)
- **Trigger manuel** : Via commande WebSocket `refresh_scalability`

---

## 🎯 Paramètres Utilisés pour le Calcul du Score

Le score de scalabilité est calculé en utilisant :
1. **`vol5`** : Volatilité récente (plus élevée = mieux)
2. **`spread`** : Spread (plus faible = mieux)
3. **`recentVolume`** : Volume récent (plus élevé = mieux)
4. **`bookDepth`** : Profondeur du carnet (plus élevée = mieux)
5. **`balanceScore`** : Équilibre bid/ask (plus proche de 1.0 = mieux)

**Formule complète** :
```
score = (vol5 / spread) × log10(recentVolume + 1) × norm_factor × balanceScore

où norm_factor = 0.5 × (recentVolume / max_volume) + 0.5 × (bookDepth / max_depth)
```

---

## 🔍 Exemple de Logs

D'après vos logs récents :
```
💹 DEBUG: Données brutes depuis top_pairs: 
  spread=0.006932168728980559, 
  bookDepth=103961.0, 
  balanceScore=0.8693067592654937, 
  bidVol=58774.0, 
  askVol=45187.0
```

Ces valeurs sont récupérées depuis `top_pairs` et utilisées pour :
- Calculer le slippage estimé
- Logger dans PostgreSQL
- Décider si une position peut être ouverte

---

## 📝 Notes Importantes

1. **`spread` peut être `NaN`** : Si le carnet d'ordres est vide ou invalide
2. **`balanceScore` varie entre 0 et 1** : 1.0 = parfaitement équilibré
3. **`bookDepth` est en unités de base** : Pas normalisé, valeur brute
4. **`vol5` et `vol15` sont en pourcentage** : Volatilité normalisée
5. **Le score est recalculé à chaque scan** : Les paires peuvent changer de classement

---

## 🔗 Fichiers Concernés

- **`core/scanner.py`** : Calcul des paramètres
- **`main.py`** : Utilisation lors de l'ouverture de position
- **`core/position_manager.py`** : Estimation du slippage
- **`core/postgresql_datalogger.py`** : Logging dans PostgreSQL
- **`core/callbacks/scalability_refresh.py`** : Refresh périodique

