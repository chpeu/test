# 📊 Analyse des Paramètres du Scan de Scalabilité

## 🔍 Paramètres Variables du Scan de Scalabilité

D'après `core/scanner.py` (classe `ScalabilityScanner`), le scan retourne les paramètres suivants :

| Paramètre | Type | Description | Source |
|-----------|------|-------------|--------|
| `price` | `float` | Prix actuel (dernier close) | `klines[-1]['close']` |
| `recentVolume` | `float` | Volume total des 5 dernières bougies 1m | `sum(volumes[-5:])` |
| `vol5` | `float` | Volatilité sur 5 périodes (écart-type normalisé en %) | `calculate_volatility(closes, 5)` |
| `vol15` | `float` | Volatilité sur 15 périodes (écart-type normalisé en %) | `calculate_volatility(closes, 15)` |
| `spread` | `float` | Spread en % entre best_bid et best_ask | `fetch_spread_data()` |
| `bookDepth` | `float` | Profondeur totale (somme des 5 premiers niveaux) | `fetch_spread_data()` |
| `bidVol` | `float` | Volume bid total | `fetch_spread_data()` |
| `askVol` | `float` | Volume ask total | `fetch_spread_data()` |
| `balanceScore` | `float` | Score d'équilibre bid/ask (0-1, 1.0 = équilibré) | `fetch_spread_data()` |
| `score` | `float` | Score de scalabilité final | `calculate_score()` |

### 📐 Formule du Score de Scalabilité

```python
vol_spread_ratio = vol5 / spread  # Si spread > 0 et vol5 > 0
norm_factor = 0.5 * (recentVolume / max_volume) + 0.5 * (bookDepth / max_depth)
balance_bonus = balanceScore  # 0-1
raw_score = vol_spread_ratio * log10(recentVolume + 1) * norm_factor * balance_bonus
```

---

## ✅ Présence dans le Schéma SQL

### 📋 Table `scan_logs`

| Paramètre Scan | Colonne SQL | Type | Statut |
|----------------|-------------|------|--------|
| `price` | `price` | `FLOAT NOT NULL` | ✅ **PRÉSENT** |
| `spread` | `spread_pct` | `FLOAT` | ✅ **PRÉSENT** |
| `bookDepth` | `book_depth` | `FLOAT` | ✅ **PRÉSENT** |
| `balanceScore` | `balance_score` | `FLOAT` | ✅ **PRÉSENT** |
| `bidVol` | `bid_vol` | `FLOAT` | ✅ **PRÉSENT** |
| `askVol` | `ask_vol` | `FLOAT` | ✅ **PRÉSENT** |
| `recentVolume` | - | - | ❌ **MANQUANT** |
| `vol5` | - | - | ❌ **MANQUANT** |
| `vol15` | - | - | ❌ **MANQUANT** |
| `score` | - | - | ❌ **MANQUANT** |

**Note** : `orderbook_imbalance_ratio` est présent dans le schéma (calculé comme `bid_vol / ask_vol`), mais n'est pas directement retourné par le scan.

---

### 📋 Table `trades`

| Paramètre Scan | Colonne SQL | Type | Statut |
|----------------|-------------|------|--------|
| `spread` (entry) | `entry_spread_pct` | `FLOAT` | ✅ **PRÉSENT** |
| `balanceScore` (entry) | `entry_balance_score` | `FLOAT` | ✅ **PRÉSENT** |
| `bookDepth` (entry) | `entry_book_depth` | `FLOAT` | ✅ **PRÉSENT** |
| `bidVol` (entry) | `entry_bid_vol` | `FLOAT` | ✅ **PRÉSENT** |
| `askVol` (entry) | `entry_ask_vol` | `FLOAT` | ✅ **PRÉSENT** |
| `spread` (exit) | `exit_spread_pct` | `FLOAT` | ✅ **PRÉSENT** |
| `balanceScore` (exit) | `exit_balance_score` | `FLOAT` | ✅ **PRÉSENT** |
| `recentVolume` (entry/exit) | - | - | ❌ **MANQUANT** |
| `vol5` (entry/exit) | - | - | ❌ **MANQUANT** |
| `vol15` (entry/exit) | - | - | ❌ **MANQUANT** |
| `score` (entry) | - | - | ❌ **MANQUANT** |

---

### 📋 Table `market_context`

| Paramètre Scan | Colonne SQL | Type | Statut |
|----------------|-------------|------|--------|
| `spread` (moyenne) | `avg_spread` | `FLOAT` | ✅ **PRÉSENT** |
| `vol5` / `vol15` (moyenne) | `avg_volatility_1m` / `avg_volatility_5m` | `FLOAT` | ⚠️ **PARTIEL** (moyennes, pas valeurs individuelles) |
| `recentVolume` | - | - | ❌ **MANQUANT** |
| `score` | - | - | ❌ **MANQUANT** |

---

## ❌ Paramètres Manquants dans le Schéma SQL

### 1. **`recentVolume`** (Volume des 5 dernières bougies)
- **Utilisation** : Utilisé dans le calcul du score de scalabilité (`log10(recentVolume + 1)`)
- **Alternative existante** : `volume_1m` et `volume_ratio_1m` dans `scan_logs`, mais pas le volume spécifique des 5 dernières bougies
- **Impact** : ⚠️ **MOYEN** - Peut être approximé par `volume_1m`, mais pas exactement la même valeur

### 2. **`vol5`** (Volatilité 5 périodes)
- **Utilisation** : Utilisé dans le calcul du score (`vol5 / spread`)
- **Alternative existante** : `atr_pct_1m` (ATR en %), mais ce n'est pas exactement la même métrique
- **Impact** : ⚠️ **MOYEN** - `atr_pct_1m` peut servir de proxy, mais `vol5` est un calcul spécifique (écart-type normalisé)

### 3. **`vol15`** (Volatilité 15 périodes)
- **Utilisation** : Utilisé pour le calcul du score (potentiellement)
- **Alternative existante** : `atr_pct_5m` (ATR en %), mais ce n'est pas exactement la même métrique
- **Impact** : ⚠️ **FAIBLE** - Moins utilisé que `vol5` dans le calcul du score

### 4. **`score`** (Score de scalabilité final)
- **Utilisation** : Score final utilisé pour classer les paires
- **Alternative existante** : Aucune
- **Impact** : ⚠️ **MOYEN** - Utile pour l'analyse ML (corrélation entre score de scalabilité et performance des trades)

---

## 💡 Recommandations

### Option 1 : Ajouter les Colonnes Manquantes (Recommandé)

```sql
-- Pour scan_logs
ALTER TABLE scan_logs ADD COLUMN recent_volume FLOAT;
ALTER TABLE scan_logs ADD COLUMN vol5 FLOAT;
ALTER TABLE scan_logs ADD COLUMN vol15 FLOAT;
ALTER TABLE scan_logs ADD COLUMN scalability_score FLOAT;

-- Pour trades (entry)
ALTER TABLE trades ADD COLUMN entry_recent_volume FLOAT;
ALTER TABLE trades ADD COLUMN entry_vol5 FLOAT;
ALTER TABLE trades ADD COLUMN entry_vol15 FLOAT;
ALTER TABLE trades ADD COLUMN entry_scalability_score FLOAT;

-- Pour trades (exit)
ALTER TABLE trades ADD COLUMN exit_recent_volume FLOAT;
ALTER TABLE trades ADD COLUMN exit_vol5 FLOAT;
ALTER TABLE trades ADD COLUMN exit_vol15 FLOAT;
```

### Option 2 : Utiliser les Alternatives Existantes (Temporaire)

- `recentVolume` → Utiliser `volume_1m` (approximation)
- `vol5` → Utiliser `atr_pct_1m` (proxy)
- `vol15` → Utiliser `atr_pct_5m` (proxy)
- `score` → Ne pas logger (perte d'information)

⚠️ **Note** : Cette option entraîne une perte de précision pour l'analyse ML.

---

## 📊 Résumé

| Paramètre | Présent dans `scan_logs` | Présent dans `trades` | Action Recommandée |
|-----------|-------------------------|----------------------|-------------------|
| `price` | ✅ | ✅ (via `entry_price`) | ✅ OK |
| `spread` | ✅ (`spread_pct`) | ✅ (`entry_spread_pct`, `exit_spread_pct`) | ✅ OK |
| `bookDepth` | ✅ (`book_depth`) | ✅ (`entry_book_depth`) | ✅ OK |
| `balanceScore` | ✅ (`balance_score`) | ✅ (`entry_balance_score`, `exit_balance_score`) | ✅ OK |
| `bidVol` | ✅ (`bid_vol`) | ✅ (`entry_bid_vol`) | ✅ OK |
| `askVol` | ✅ (`ask_vol`) | ✅ (`entry_ask_vol`) | ✅ OK |
| `recentVolume` | ❌ | ❌ | ⚠️ **AJOUTER** |
| `vol5` | ❌ | ❌ | ⚠️ **AJOUTER** |
| `vol15` | ❌ | ❌ | ⚠️ **AJOUTER** (optionnel) |
| `score` | ❌ | ❌ | ⚠️ **AJOUTER** |

---

## 🎯 Conclusion

**7 paramètres sur 10 sont présents** dans le schéma SQL.

**3 paramètres manquants** :
1. `recentVolume` (volume des 5 dernières bougies)
2. `vol5` (volatilité 5 périodes)
3. `score` (score de scalabilité final)

**Recommandation** : Ajouter ces 3 colonnes à `scan_logs` et `trades` pour une analyse ML complète.

