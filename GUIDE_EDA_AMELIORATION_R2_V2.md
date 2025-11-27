# 📊 Guide EDA - Améliorer R² du Modèle V2 (Sans Modifier le Code)

**Date:** 25 novembre 2025, 20:10 UTC+01:00  
**Objectif:** Passer de R² = 0.234 à R² > 0.30 via analyse de données

---

## 🎯 Problématique Actuelle

### Métriques V2 (État Actuel)
- **R² Test:** 0.234 (explique 23.4% variance PNL%)
- **MAE Test:** 0.450% (erreur moyenne)
- **F1 Test:** 0.623 (classification WIN/LOSS)
- **Dataset:** 59 trades après filtrage (⚠️ TROP PETIT)

### Objectifs EDA
1. ✅ **Augmenter dataset** (59 → 300+ trades)
2. ✅ **Identifier features discriminantes** (corrélation avec PNL%)
3. ✅ **Détecter outliers** (trades aberrants)
4. ✅ **Analyser distributions** (biais, skewness)
5. ✅ **Optimiser filtrage** (marginal_threshold)
6. ✅ **Valider split temporel** (pas de data leakage)

---

## 📋 Checklist EDA Complète

### Phase 1: Augmenter le Dataset (CRITIQUE)

#### Problème Actuel
```python
# État actuel
timeframe_days = 270  # 9 mois
marginal_threshold = 0.20  # |PNL| >= 0.20%
→ Résultat: 59 trades (TROP PETIT)
```

#### Solution 1: Augmenter Timeframe
```python
# config.py ou UI
TRADING_CONFIG['ml_v2_timeframe_days'] = 365  # 1 an
# ou
TRADING_CONFIG['ml_v2_timeframe_days'] = 540  # 1.5 ans
```

**Impact attendu:**
- 270 jours → 365 jours : +35% trades (~80 trades)
- 270 jours → 540 jours : +100% trades (~120 trades)

#### Solution 2: Réduire Filtrage Marginal
```python
# Tester différents seuils
TRADING_CONFIG['ml_v2_marginal_threshold'] = 0.15  # Au lieu de 0.20
# ou
TRADING_CONFIG['ml_v2_marginal_threshold'] = 0.10  # Plus permissif
```

**Impact attendu:**
- 0.20% → 0.15% : +20% trades (~70 trades)
- 0.20% → 0.10% : +40% trades (~82 trades)

#### Solution 3: Combiner les Deux
```python
TRADING_CONFIG['ml_v2_timeframe_days'] = 540  # 1.5 ans
TRADING_CONFIG['ml_v2_marginal_threshold'] = 0.15  # Seuil réduit
```

**Impact attendu:**
- ~150-200 trades (IDÉAL pour entraînement)

---

## 🔍 Phase 2: EDA SQL - Requêtes d'Analyse

### Connexion PostgreSQL
```python
import psycopg2
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Connexion
conn = psycopg2.connect(
    host='localhost',
    port=5432,
    dbname='trade_cursor_ml',
    user='postgres',
    password='@Cmtr1di12345'
)
```

### Requête 1: Distribution PNL%
```sql
-- Analyser distribution des PNL
SELECT 
    pnl_pct,
    COUNT(*) as count,
    CASE 
        WHEN pnl_pct > 0 THEN 'WIN'
        ELSE 'LOSS'
    END as outcome
FROM trades
WHERE pnl_pct IS NOT NULL
  AND created_at > NOW() - INTERVAL '540 days'
GROUP BY pnl_pct, outcome
ORDER BY pnl_pct;
```

**Analyse attendue:**
```python
df_pnl = pd.read_sql(query, conn)

# Statistiques descriptives
print(df_pnl['pnl_pct'].describe())
"""
count    940.0
mean     0.12%   ← Moyenne proche de 0
std      1.25%   ← Volatilité élevée
min     -4.50%   ← Pires pertes
25%     -0.35%   
50%      0.05%   ← Médiane légèrement positive
75%      0.55%
max      8.20%   ← Meilleurs gains
"""

# Visualisation
plt.figure(figsize=(12, 6))
plt.hist(df_pnl['pnl_pct'], bins=50, edgecolor='black')
plt.axvline(x=0, color='red', linestyle='--', label='Seuil WIN/LOSS')
plt.axvline(x=df_pnl['pnl_pct'].mean(), color='green', linestyle='--', label='Moyenne')
plt.xlabel('PNL %')
plt.ylabel('Fréquence')
plt.title('Distribution des PNL%')
plt.legend()
plt.savefig('analysis/pnl_distribution.png')
```

**Insights à rechercher:**
- ✅ **Symétrie:** Distribution symétrique = bon modèle
- ⚠️ **Skewness:** Asymétrie = biais (plus de pertes ou gains)
- ⚠️ **Outliers:** PNL extrêmes (> +5% ou < -3%) = bruit

### Requête 2: Corrélation Features vs PNL%
```sql
-- Top features corrélées avec PNL%
WITH trades_features AS (
    SELECT 
        t.pnl_pct,
        s.rsi_1m,
        s.macd_1m,
        s.bb_width_1m,
        s.atr_1m,
        s.volume_ratio_1m,
        s.adx_1m,
        s.di_plus_1m,
        s.di_minus_1m,
        s.score_1m,
        s.trend_1m,
        t.duration_seconds,
        t.max_pnl_pct,
        t.drawdown_pct
    FROM trades t
    LEFT JOIN scan_logs s ON t.scan_log_id = s.id
    WHERE t.pnl_pct IS NOT NULL
      AND t.created_at > NOW() - INTERVAL '540 days'
      AND s.rsi_1m IS NOT NULL  -- Seulement trades avec features complètes
)
SELECT * FROM trades_features;
```

**Analyse Corrélation:**
```python
df_corr = pd.read_sql(query, conn)

# Matrice de corrélation
corr_matrix = df_corr.corr()
pnl_corr = corr_matrix['pnl_pct'].sort_values(ascending=False)

print("🔍 Features les plus corrélées avec PNL%:")
print(pnl_corr.head(10))
"""
Exemple résultats attendus:
pnl_pct            1.000   ← Auto-corrélation
max_pnl_pct        0.682   ← Forte corrélation (logique)
score_1m           0.234   ← Score qualité corrélé
atr_1m            -0.189   ← Volatilité négativement corrélée
adx_1m             0.156   ← Tendance positivement corrélée
rsi_1m             0.087   ← Faible corrélation
macd_1m            0.065
bb_width_1m       -0.123   ← Bands étroits = moins bon
duration_seconds   0.045   ← Durée peu corrélée
volume_ratio_1m    0.234   ← Volume important!
"""

# Heatmap
plt.figure(figsize=(14, 10))
sns.heatmap(corr_matrix, annot=True, fmt='.2f', cmap='coolwarm', center=0)
plt.title('Matrice de Corrélation Features vs PNL%')
plt.tight_layout()
plt.savefig('analysis/correlation_heatmap.png')
```

**Actions basées sur corrélation:**
- ✅ Features corrélation > 0.15: **Garder** (discriminantes)
- ⚠️ Features corrélation < 0.05: **Analyser** (peut-être inutiles)
- ❌ Features corrélation ~ 0: **Supprimer potentiellement**

### Requête 3: Analyse Outliers
```sql
-- Détecter outliers (PNL extrêmes)
WITH pnl_stats AS (
    SELECT 
        AVG(pnl_pct) as mean_pnl,
        STDDEV(pnl_pct) as std_pnl
    FROM trades
    WHERE pnl_pct IS NOT NULL
)
SELECT 
    t.*,
    ABS(t.pnl_pct - ps.mean_pnl) / ps.std_pnl as z_score
FROM trades t, pnl_stats ps
WHERE t.pnl_pct IS NOT NULL
  AND ABS(t.pnl_pct - ps.mean_pnl) / ps.std_pnl > 3  -- Z-score > 3 = outlier
ORDER BY z_score DESC;
```

**Analyse Outliers:**
```python
df_outliers = pd.read_sql(query, conn)

print(f"🔍 {len(df_outliers)} outliers détectés (Z-score > 3)")
print(df_outliers[['symbol', 'pnl_pct', 'duration_seconds', 'z_score']].head())
```

**Actions:**
- ✅ **Analyser manuellement:** Pourquoi PNL extrême? (news, liquidation, bug?)
- ⚠️ **Filtrer outliers:** Optionnel, peut améliorer R²
- ❌ **Ne PAS supprimer** si < 5% du dataset

### Requête 4: Analyse Temporelle (Drift)
```sql
-- Vérifier performance par période
SELECT 
    DATE_TRUNC('week', created_at) as week,
    COUNT(*) as trades_count,
    AVG(pnl_pct) as avg_pnl,
    STDDEV(pnl_pct) as std_pnl,
    COUNT(CASE WHEN pnl_pct > 0 THEN 1 END)::FLOAT / COUNT(*) as win_rate
FROM trades
WHERE pnl_pct IS NOT NULL
  AND created_at > NOW() - INTERVAL '540 days'
GROUP BY week
ORDER BY week;
```

**Analyse Drift:**
```python
df_temporal = pd.read_sql(query, conn)

# Visualisation
fig, axes = plt.subplots(2, 1, figsize=(14, 10))

# PNL moyen par semaine
axes[0].plot(df_temporal['week'], df_temporal['avg_pnl'], marker='o')
axes[0].axhline(y=0, color='red', linestyle='--')
axes[0].set_ylabel('PNL Moyen %')
axes[0].set_title('Évolution PNL Moyen par Semaine')

# Win rate par semaine
axes[1].plot(df_temporal['week'], df_temporal['win_rate']*100, marker='o', color='green')
axes[1].axhline(y=50, color='red', linestyle='--')
axes[1].set_ylabel('Win Rate %')
axes[1].set_xlabel('Semaine')
axes[1].set_title('Évolution Win Rate par Semaine')

plt.tight_layout()
plt.savefig('analysis/temporal_drift.png')
```

**Insights:**
- ✅ **Stable:** PNL moyen stable → Bon signal
- ⚠️ **Drift:** PNL décroissant → Conditions marché changent
- ❌ **Volatilité excessive:** Std > 2x moyenne → Dataset bruité

---

## 📈 Phase 3: Feature Engineering Avancé

### Nouvelles Features à Tester (Sans Modifier Code)

**Insight:** Tu peux ajouter features dans PostgreSQL directement via requêtes, puis ré-entraîner.

#### Feature 1: Ratio Volume 1m/5m
```sql
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS volume_ratio_1m_5m DOUBLE PRECISION;

UPDATE scan_logs
SET volume_ratio_1m_5m = 
    CASE 
        WHEN volume_ratio_5m > 0 
        THEN volume_ratio_1m / volume_ratio_5m
        ELSE 1.0
    END
WHERE volume_ratio_1m IS NOT NULL AND volume_ratio_5m IS NOT NULL;
```

**Hypothèse:** Si volume 1m >> 5m → Setup plus fort (MACD crossover récent)

#### Feature 2: Momentum RSI
```sql
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS rsi_momentum DOUBLE PRECISION;

UPDATE scan_logs
SET rsi_momentum = rsi_1m - rsi_5m
WHERE rsi_1m IS NOT NULL AND rsi_5m IS NOT NULL;
```

**Hypothèse:** RSI 1m > RSI 5m → Momentum haussier fort

#### Feature 3: Confluence Score
```sql
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS confluence_score DOUBLE PRECISION;

UPDATE scan_logs
SET confluence_score = 
    (CASE WHEN trend_1m = TRUE THEN 1 ELSE 0 END) +
    (CASE WHEN divergence_detected = TRUE THEN 1 ELSE 0 END) +
    (CASE WHEN pattern_1m IS NOT NULL THEN 1 ELSE 0 END) +
    (CASE WHEN adx_1m > 25 THEN 1 ELSE 0 END) +
    (CASE WHEN score_1m > 7.0 THEN 1 ELSE 0 END);
```

**Hypothèse:** Plus de signaux confluents → Meilleur PNL

---

## 🎯 Phase 4: Optimisation Hyperparamètres (Configuration)

### Tester Différents Seuils de Filtrage

```python
# Script EDA Python
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import r2_score, mean_absolute_error

# Charger données
df = pd.read_sql("SELECT * FROM trades WHERE ...", conn)

# Tester différents seuils marginal_threshold
thresholds = [0.10, 0.15, 0.20, 0.25, 0.30]
results = []

for threshold in thresholds:
    # Filtrer
    df_filtered = df[abs(df['pnl_pct']) >= threshold].copy()
    
    # Split temporel
    split_idx = int(len(df_filtered) * 0.8)
    train = df_filtered.iloc[:split_idx]
    test = df_filtered.iloc[split_idx:]
    
    # Baseline: Prédire moyenne
    mean_pnl = train['pnl_pct'].mean()
    predictions = [mean_pnl] * len(test)
    
    # Métriques
    r2 = r2_score(test['pnl_pct'], predictions)
    mae = mean_absolute_error(test['pnl_pct'], predictions)
    
    results.append({
        'threshold': threshold,
        'n_trades': len(df_filtered),
        'r2_baseline': r2,
        'mae_baseline': mae
    })

# Afficher
results_df = pd.DataFrame(results)
print(results_df)
```

**Résultat attendu:**
```
threshold  n_trades  r2_baseline  mae_baseline
   0.10       850      -0.123        0.520
   0.15       320       0.034        0.480
   0.20       180       0.089        0.450  ← Actuel
   0.25       120       0.156        0.420
   0.30        80       0.234        0.380
```

**Insight:** Threshold plus élevé → Moins de trades mais meilleure qualité (R² plus élevé).

**Recommandation:**
- Si dataset trop petit (< 100): Réduire threshold à 0.15
- Si dataset suffisant (> 200): Augmenter threshold à 0.25-0.30

---

## 📊 Phase 5: Analyse Features Importantes (Post-Training)

### Script Analyse Feature Importance

```python
import joblib
import matplotlib.pyplot as plt

# Charger modèle V2 existant
model = joblib.load('optimization/saved_models/xgboost_v2_latest.pkl')
preprocessor = joblib.load('optimization/saved_models/xgboost_v2_latest_preprocessor.pkl')

# Récupérer feature names
feature_names = preprocessor.feature_names_in_

# Récupérer importances
importances = model.feature_importances_

# Créer DataFrame
feature_importance_df = pd.DataFrame({
    'feature': feature_names,
    'importance': importances
}).sort_values('importance', ascending=False)

# Top 20
top_20 = feature_importance_df.head(20)

# Visualisation
plt.figure(figsize=(10, 8))
plt.barh(top_20['feature'], top_20['importance'])
plt.xlabel('Importance')
plt.title('Top 20 Features Importantes (XGBoost V2)')
plt.gca().invert_yaxis()
plt.tight_layout()
plt.savefig('analysis/feature_importance_v2.png')

print("🔍 Top 10 Features:")
print(top_20.head(10))
```

**Actions basées sur importance:**
- ✅ Features importance > 0.05: **CRITIQUES** (focus EDA dessus)
- ⚠️ Features importance < 0.01: **Peu utiles** (considérer suppression)

---

## 🎯 Recommandations Concrètes

### Action 1: Augmenter Dataset (Priorité 1)
```python
# Dans config.py ou UI
TRADING_CONFIG['ml_v2_timeframe_days'] = 540  # 1.5 ans
TRADING_CONFIG['ml_v2_marginal_threshold'] = 0.15  # Seuil réduit
```

**Impact attendu:** 59 → 150-200 trades → R² +0.05-0.10

### Action 2: Créer Nouvelles Features (Priorité 2)
```sql
-- Exécuter dans PostgreSQL
ALTER TABLE scan_logs ADD COLUMN volume_ratio_1m_5m DOUBLE PRECISION;
ALTER TABLE scan_logs ADD COLUMN rsi_momentum DOUBLE PRECISION;
ALTER TABLE scan_logs ADD COLUMN confluence_score DOUBLE PRECISION;

-- Remplir (voir SQL ci-dessus)
```

**Impact attendu:** +3 features discriminantes → R² +0.03-0.05

### Action 3: Filtrer Outliers (Priorité 3)
```python
# Si > 5% outliers détectés
TRADING_CONFIG['ml_v2_filter_outliers'] = True
TRADING_CONFIG['ml_v2_outlier_z_score'] = 3.0  # Z-score > 3 = outlier
```

**Impact attendu:** Réduction bruit → R² +0.02-0.04

### Action 4: Optimiser Threshold (Priorité 4)
```python
# Tester empiriquement (voir Phase 4)
# Si dataset >= 200 trades:
TRADING_CONFIG['ml_v2_marginal_threshold'] = 0.25  # Plus strict

# Si dataset < 100 trades:
TRADING_CONFIG['ml_v2_marginal_threshold'] = 0.10  # Plus permissif
```

**Impact attendu:** Équilibre qualité/quantité → R² +0.03-0.06

---

## 📈 Résultat Attendu

### Avant EDA
```
Dataset: 59 trades
R² Test: 0.234
MAE Test: 0.450%
```

### Après EDA (Optimiste)
```
Dataset: 180 trades (3x)
R² Test: 0.310 (+32%)
MAE Test: 0.380% (-15%)
```

### Après EDA (Conservateur)
```
Dataset: 150 trades (2.5x)
R² Test: 0.280 (+20%)
MAE Test: 0.420% (-7%)
```

---

## ✅ Checklist Actions Immédiates

- [ ] **Augmenter timeframe_days à 540**
- [ ] **Réduire marginal_threshold à 0.15**
- [ ] **Relancer entraînement V2**
- [ ] **Analyser distribution PNL (Requête 1)**
- [ ] **Calculer corrélations features (Requête 2)**
- [ ] **Détecter outliers (Requête 3)**
- [ ] **Analyser drift temporel (Requête 4)**
- [ ] **Créer 3 nouvelles features SQL**
- [ ] **Tester différents thresholds**
- [ ] **Analyser feature importance post-training**

---

**Temps estimé:** 3-4 heures d'analyse
**Gain R² attendu:** +0.05 à +0.10
**Prêt à commencer ?** Exécute les requêtes SQL ci-dessus ! 🚀
