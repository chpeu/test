# 📊 Comparaison : Paramètres Scalables vs Schéma SQL

## ✅ Résumé

**La plupart des paramètres variables provenant du scan des paires scalables sont présents dans le schéma SQL**, mais certains paramètres spécifiques au calcul du score de scalabilité ne sont pas stockés directement.

---

## 📋 Tableau Comparatif

| Paramètre Scan Scalables | Nom dans Schéma SQL | Table | Statut | Notes |
|--------------------------|---------------------|-------|--------|-------|
| **`spread`** | `spread_pct` | `scan_logs` | ✅ **PRÉSENT** | Ligne 80 |
| **`bookDepth`** | `book_depth` | `scan_logs` | ✅ **PRÉSENT** | Ligne 81 |
| **`balanceScore`** | `balance_score` | `scan_logs` | ✅ **PRÉSENT** | Ligne 82 |
| **`bidVol`** | `bid_vol` | `scan_logs` | ✅ **PRÉSENT** | Ligne 83 |
| **`askVol`** | `ask_vol` | `scan_logs` | ✅ **PRÉSENT** | Ligne 84 |
| **`orderbook_imbalance_ratio`** | `orderbook_imbalance_ratio` | `scan_logs` | ✅ **PRÉSENT** | Ligne 85 (calculé : bid_vol / ask_vol) |
| **`vol5`** | ❌ | - | ❌ **MANQUANT** | Volatilité 5 périodes (utilisée pour calculer le score) |
| **`vol15`** | ❌ | - | ❌ **MANQUANT** | Volatilité 15 périodes (utilisée pour calculer le score) |
| **`recentVolume`** | ❌ | - | ❌ **MANQUANT** | Volume des 5 dernières bougies (utilisé pour calculer le score) |
| **`score`** | ❌ | - | ❌ **MANQUANT** | Score de scalabilité final (utilisé pour classer les paires) |
| **`price`** | `price` | `scan_logs` | ✅ **PRÉSENT** | Ligne 79 |

---

## 📍 Détails par Table

### 1. **Table `scan_logs`** ✅

**Paramètres présents** :
```sql
-- Données marché (lignes 78-85)
price FLOAT NOT NULL,
spread_pct FLOAT,
book_depth FLOAT,
balance_score FLOAT,
bid_vol FLOAT,
ask_vol FLOAT,
orderbook_imbalance_ratio FLOAT,  -- bid_vol / ask_vol
```

**Paramètres manquants** :
- `vol5` : Volatilité sur 5 périodes
- `vol15` : Volatilité sur 15 périodes
- `recentVolume` : Volume des 5 dernières bougies
- `score` : Score de scalabilité

**Note** : Les volumes sont stockés via `volume_1m` et `volume_5m`, mais pas le `recentVolume` spécifique (somme des 5 dernières bougies).

---

### 2. **Table `trades`** ✅

**Paramètres présents au moment de l'entrée** :
```sql
-- Score et autres (ligne 434-435)
entry_spread_pct FLOAT,
entry_balance_score FLOAT,

-- Scalability data au entry (lignes 550-553)
entry_book_depth FLOAT,
entry_bid_vol FLOAT,
entry_ask_vol FLOAT,
entry_orderbook_imbalance FLOAT,
```

**Paramètres présents au moment de la sortie** :
```sql
-- Score et autres (lignes 474-475)
exit_spread_pct FLOAT,
exit_balance_score FLOAT,
```

**Paramètres manquants** :
- `entry_vol5` / `exit_vol5` : Volatilité 5 périodes
- `entry_vol15` / `exit_vol15` : Volatilité 15 périodes
- `entry_recentVolume` / `exit_recentVolume` : Volume récent
- `entry_scalability_score` / `exit_scalability_score` : Score de scalabilité

---

### 3. **Table `market_context`** ⚠️ PARTIEL

**Paramètres présents** :
```sql
-- Métriques globales (lignes 601-603)
avg_spread FLOAT,
avg_volatility_1m FLOAT,
avg_volatility_5m FLOAT,
```

**Note** : Ces valeurs sont des **moyennes globales** pour toutes les paires, pas des valeurs spécifiques par paire.

---

## 🔍 Analyse des Paramètres Manquants

### 1. **`vol5` et `vol15`** (Volatilité)

**Impact** : ⚠️ **MOYEN**
- Utilisés pour calculer le score de scalabilité
- Pourraient être utiles pour l'analyse ML (corrélation volatilité/performance)
- **Alternative** : Les indicateurs ATR (`atr_pct_1m`, `atr_pct_5m`) sont déjà stockés et représentent la volatilité

**Recommandation** : 
- ✅ **Option 1** : Utiliser `atr_pct_1m` et `atr_pct_5m` comme proxy (déjà présents)
- ⚠️ **Option 2** : Ajouter `vol5` et `vol15` si besoin d'analyse spécifique

---

### 2. **`recentVolume`** (Volume des 5 dernières bougies)

**Impact** : ⚠️ **FAIBLE**
- Utilisé pour calculer le score de scalabilité
- **Alternative** : `volume_1m` et `volume_ratio_1m` sont déjà stockés

**Recommandation** :
- ✅ **Option 1** : Utiliser `volume_1m` comme proxy (déjà présent)
- ⚠️ **Option 2** : Ajouter `recent_volume_5m` si besoin d'analyse spécifique

---

### 3. **`score`** (Score de scalabilité)

**Impact** : ⚠️ **FAIBLE**
- Utilisé uniquement pour classer les paires lors du scan
- **Pas nécessaire pour ML** : Le score est une métrique composite qui peut être recalculé
- **Alternative** : Les composants du score (`spread_pct`, `book_depth`, `balance_score`, `volume_ratio_1m`, `atr_pct_1m`) sont déjà stockés

**Recommandation** :
- ✅ **Ne pas ajouter** : Le score peut être recalculé si nécessaire, et les features individuelles sont plus utiles pour ML

---

## ✅ Conclusion

### Paramètres Essentiels : **TOUS PRÉSENTS** ✅

Les paramètres **essentiels** pour l'analyse ML et le logging sont tous présents :
- ✅ `spread_pct` : Spread du carnet d'ordres
- ✅ `book_depth` : Profondeur du carnet
- ✅ `balance_score` : Équilibre bid/ask
- ✅ `bid_vol` / `ask_vol` : Volumes bid/ask
- ✅ `orderbook_imbalance_ratio` : Ratio d'équilibre

### Paramètres Optionnels : **MANQUANTS** ⚠️

Les paramètres suivants ne sont **pas stockés directement** mais peuvent être **reconstruits ou remplacés** :
- ⚠️ `vol5` / `vol15` → **Alternative** : `atr_pct_1m` / `atr_pct_5m` (déjà présents)
- ⚠️ `recentVolume` → **Alternative** : `volume_1m` / `volume_ratio_1m` (déjà présents)
- ⚠️ `score` → **Alternative** : Peut être recalculé depuis les features stockées

---

## 🎯 Recommandations

### ✅ **Action Immédiate : AUCUNE**

Le schéma SQL contient **tous les paramètres essentiels** pour :
- ✅ Logger les données de scalabilité
- ✅ Analyser la corrélation entre scalabilité et performance
- ✅ Entraîner des modèles ML

### ⚠️ **Action Optionnelle : Ajouter `vol5` et `vol15`**

Si vous souhaitez analyser spécifiquement la volatilité calculée par le scanner (différente de l'ATR), vous pouvez ajouter :

```sql
-- Dans scan_logs
ALTER TABLE scan_logs ADD COLUMN vol5 FLOAT;
ALTER TABLE scan_logs ADD COLUMN vol15 FLOAT;
ALTER TABLE scan_logs ADD COLUMN recent_volume_5m FLOAT;

-- Dans trades (optionnel)
ALTER TABLE trades ADD COLUMN entry_vol5 FLOAT;
ALTER TABLE trades ADD COLUMN entry_vol15 FLOAT;
ALTER TABLE trades ADD COLUMN exit_vol5 FLOAT;
ALTER TABLE trades ADD COLUMN exit_vol15 FLOAT;
```

**Mais ce n'est pas nécessaire** car :
- L'ATR (`atr_pct_1m`, `atr_pct_5m`) représente déjà la volatilité
- Le volume (`volume_1m`, `volume_ratio_1m`) représente déjà l'activité récente

---

## 📊 Utilisation Actuelle

D'après le code Python, les paramètres suivants sont **déjà loggés** :

### Dans `scan_logs` :
```python
# core/postgresql_datalogger.py - log_scan()
spread_pct=scan_data.get('spread_pct'),
book_depth=scan_data.get('book_depth'),
balance_score=scan_data.get('balance_score'),
bid_vol=scan_data.get('bid_vol'),
ask_vol=scan_data.get('ask_vol'),
```

### Dans `trades` :
```python
# core/postgresql_datalogger.py - log_trade()
entry_spread_pct=entry_scalability.get('spread_pct'),
entry_book_depth=entry_scalability.get('depth'),
entry_balance_score=entry_scalability.get('balance'),
entry_bid_vol=entry_scalability.get('bidVol'),
entry_ask_vol=entry_scalability.get('askVol'),
```

**Conclusion** : ✅ **Tous les paramètres essentiels sont déjà loggés correctement !**

