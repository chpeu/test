# 📊 PHASE 4 : Feature Engineering Avancé

> **Date création:** 11/12/2025
> **Status:** 📋 PLANIFIÉ
> **Prérequis:** Phase 3 (Ensemble Learning) complétée
> **Effort estimé:** ~10h

---

## 🎯 OBJECTIF

Enrichir les features ML avec :
- Données temporelles (historique trades)
- Données cross-asset (BTC)
- Données sentiment (Fear & Greed, Long/Short)
- Order flow avancé

**Total nouvelles features:** 21

---

## 📋 DÉCISIONS BRAINSTORMING (11/12/2025)

| # | Question | Décision | Features |
|---|----------|----------|----------|
| 1 | Lag profondeur | Lag 1-3 (3 derniers trades) | - |
| 2 | Lag métriques | PnL + Win/Loss | 6 |
| 3 | Rolling windows | Windows 5 + 10 | 6 |
| 4 | BTC features | Price + Trend | 4 |
| 5 | Source API BTC | MEXC (déjà connecté) | - |
| 6 | Funding Rate | Binance public API | 1 |
| 7 | Sentiment | Fear & Greed + Long/Short Ratio | 2 |
| 8 | Order Flow | Ajouter cumulatives | 2 |

---

## 📊 DÉTAIL DES 21 FEATURES

### 1. Lag Features (6 features)
> Données des 3 derniers trades pour détecter momentum/séries

| Feature | Type | Description |
|---------|------|-------------|
| `lag_1_pnl` | float | PnL% du trade n-1 |
| `lag_1_win` | bool | Trade n-1 gagnant ? |
| `lag_2_pnl` | float | PnL% du trade n-2 |
| `lag_2_win` | bool | Trade n-2 gagnant ? |
| `lag_3_pnl` | float | PnL% du trade n-3 |
| `lag_3_win` | bool | Trade n-3 gagnant ? |

**Source:** PostgreSQL table `trades`
**Calcul:** Query ORDER BY timestamp DESC LIMIT 3

---

### 2. Rolling Features (6 features)
> Agrégations sur fenêtres glissantes

| Feature | Type | Description |
|---------|------|-------------|
| `rolling_winrate_5` | float | % wins sur 5 derniers trades |
| `rolling_pnl_avg_5` | float | PnL moyen sur 5 derniers |
| `rolling_pnl_std_5` | float | Volatilité PnL sur 5 derniers |
| `rolling_winrate_10` | float | % wins sur 10 derniers trades |
| `rolling_pnl_avg_10` | float | PnL moyen sur 10 derniers |
| `rolling_pnl_std_10` | float | Volatilité PnL sur 10 derniers |

**Source:** PostgreSQL table `trades`
**Calcul:** Window functions SQL

---

### 3. BTC Features (4 features)
> Corrélation avec Bitcoin

| Feature | Type | Description |
|---------|------|-------------|
| `btc_pct_change_1h` | float | Variation BTC dernière heure |
| `btc_pct_change_24h` | float | Variation BTC 24h |
| `btc_trend` | category | BULLISH / BEARISH / RANGING |
| `btc_above_ma20` | bool | BTC au-dessus de MA20 ? |

**Source:** MEXC API (déjà connecté)
```python
# Endpoints
mexc.get_ticker("BTCUSDT")
mexc.get_klines("BTCUSDT", "1h", limit=24)
```

---

### 4. Funding Rate (1 feature)
> Pression long/short sur futures

| Feature | Type | Description |
|---------|------|-------------|
| `funding_rate` | float | Taux de financement BTC |

**Source:** Binance Futures API (public, sans clés)
```python
url = "https://fapi.binance.com/fapi/v1/fundingRate"
params = {"symbol": "BTCUSDT", "limit": 1}
```

**Interprétation:**
- > 0.01% → Très bullish (risque correction)
- < -0.005% → Très bearish (risque rebond)

---

### 5. Sentiment Features (2 features)
> Mood global du marché

| Feature | Type | Description |
|---------|------|-------------|
| `fear_greed_index` | int | Index 0-100 (Fear → Greed) |
| `long_short_ratio` | float | % comptes long vs short |

**Sources:**
```python
# Fear & Greed (1×/jour)
url = "https://api.alternative.me/fng/?limit=1"

# Long/Short Ratio (Bybit, temps réel)
url = "https://api.bybit.com/v5/market/account-ratio"
params = {"category": "linear", "symbol": "BTCUSDT", "period": "1h", "limit": 1}
```

---

### 6. Order Flow Avancé (2 features)
> Extension des 6 features existantes

| Feature | Type | Description |
|---------|------|-------------|
| `cumulative_delta_10` | float | Somme delta sur 10 derniers scans |
| `imbalance_trend_5` | float | Pente imbalance sur 5 scans |

**Source:** PostgreSQL table `scan_logs`
**Calcul:** Window functions sur colonnes existantes

---

## 📁 FICHIERS À CRÉER/MODIFIER

### Nouveaux fichiers

| Fichier | Description |
|---------|-------------|
| `optimization/data/feature_engineering_v2.py` | Calcul des 21 nouvelles features |
| `core/data/btc_data_fetcher.py` | Fetch BTC depuis MEXC |
| `core/data/market_sentiment.py` | Fear&Greed + Funding + L/S Ratio |

### Fichiers à modifier

| Fichier | Modification |
|---------|--------------|
| `optimization/data/feature_loader.py` | Intégrer feature_engineering_v2 |
| `api/routes/ml.py` | Endpoints pour nouvelles features |

---

## ⏱️ PLAN D'IMPLÉMENTATION

### Étape 1: Lag + Rolling (2h)
- [ ] Créer `feature_engineering_v2.py`
- [ ] Implémenter `get_lag_features()`
- [ ] Implémenter `get_rolling_features()`
- [ ] Tests unitaires

### Étape 2: BTC Features (2h)
- [ ] Créer `btc_data_fetcher.py`
- [ ] Implémenter `get_btc_price_data()`
- [ ] Implémenter `calculate_btc_trend()`
- [ ] Cache 5min pour éviter rate limits

### Étape 3: Sentiment Features (2h)
- [ ] Créer `market_sentiment.py`
- [ ] Implémenter `get_fear_greed_index()`
- [ ] Implémenter `get_funding_rate()`
- [ ] Implémenter `get_long_short_ratio()`
- [ ] Cache adapté (F&G: 1h, autres: 5min)

### Étape 4: Order Flow (1h)
- [ ] Ajouter `cumulative_delta_10` dans feature_engineering_v2
- [ ] Ajouter `imbalance_trend_5`
- [ ] SQL window functions

### Étape 5: Intégration (3h)
- [ ] Modifier `feature_loader.py` pour inclure v2
- [ ] Tests d'intégration
- [ ] Vérifier que training ML fonctionne avec 21 nouvelles features
- [ ] Benchmarker impact sur accuracy

---

## 📊 APIS EXTERNES UTILISÉES

| API | Endpoint | Auth | Rate Limit | Cache |
|-----|----------|------|------------|-------|
| MEXC | `/api/v3/ticker/24hr` | Clés existantes | 1200/min | 5min |
| MEXC | `/api/v3/klines` | Clés existantes | 1200/min | 5min |
| Binance Futures | `/fapi/v1/fundingRate` | Aucune (public) | 2400/min | 5min |
| alternative.me | `/fng/` | Aucune (public) | Illimité | 1h |
| Bybit | `/v5/market/account-ratio` | Aucune (public) | 120/min | 5min |

---

## ✅ CRITÈRES DE SUCCÈS

| Métrique | Objectif |
|----------|----------|
| 21 features calculées | 100% sans erreur |
| Temps calcul features | < 500ms |
| Impact accuracy GB | > +1% |
| Pas de régression | Tests existants passent |

---

## 📝 NOTES

- Les features temporelles (Lag, Rolling) nécessitent un historique de trades
- Si < 10 trades, les rolling_10 seront NULL → gérer dans preprocessing
- Fear & Greed update 1×/jour → cacher agressivement
- Funding rate change toutes les 8h sur Binance

---

**Document créé suite au brainstorming du 11/12/2025**
