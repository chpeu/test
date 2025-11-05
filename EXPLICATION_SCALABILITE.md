# 📊 EXPLICATION COMPLÈTE : SCAN DE SCALABILITÉ

**Trade Cursor v6.2**  
**Métriques collectées et système de scoring**

---

## 🎯 OBJECTIF

Identifier les **meilleures paires** pour le scalping automatique parmi les paires **0% fees** de MEXC, en se basant sur:
- Volatilité optimale
- Spread faible
- Volume élevé
- Profondeur du carnet d'ordres
- Équilibre bid/ask

---

## 📍 POINT 1 : VOLATILITÉ

### **Définition**
Mesure de l'**amplitude des variations de prix** sur une période donnée.

### **Calcul**
```python
def calculate_volatility(closes: List[float], period: int) -> float:
    """
    Volatilité = Écart-type des prix de clôture / Moyenne des prix
    """
    recent_closes = closes[-period:]
    mean = sum(recent_closes) / len(recent_closes)
    variance = sum((v - mean) ** 2 for v in recent_closes) / len(recent_closes)
    std = math.sqrt(variance)
    
    return (std / mean) * 100  # En pourcentage
```

**Formule**:
```
σ = √[Σ(xi - μ)² / N]
Volatilité = (σ / μ) × 100%
```

Où:
- `σ` = écart-type
- `μ` = moyenne
- `N` = nombre de points

---

### **Périodes calculées**
1. **Vol5** (5 minutes)
   - Volatilité court terme
   - Reflète les mouvements récents
   - Idéal: 0.6-3%

2. **Vol15** (15 minutes)
   - Volatilité moyen terme
   - Lissage des variations
   - Idéal: 0.8-5%

---

### **Exemple pratique**

**BTC_USDT**:
```
Prix (5 dernières minutes):
[67000, 67025, 67010, 67040, 67020]

Mean = (67000 + 67025 + 67010 + 67040 + 67020) / 5 = 67019
Variance = [(67000-67019)² + (67025-67019)² + ...] / 5 = 214
Std = √214 = 14.6
Vol5 = (14.6 / 67019) × 100 = 0.022%  ← Très calme
```

**SOL_USDT**:
```
Prix (5 dernières minutes):
[150, 152, 149, 155, 148]

Mean = 150.8
Std = 2.8
Vol5 = (2.8 / 150.8) × 100 = 1.86%  ← Volatil, bon pour scalping
```

---

## 📍 POINT 2 : SPREAD

### **Définition**
**Différence** entre le prix de vente (ask) et le prix d'achat (bid) le plus proche.

### **Calcul**
```python
best_ask = 100.15  # Prix de vente minimum
best_bid = 100.10  # Prix d'achat maximum

mid_price = (best_ask + best_bid) / 2
spread = ((best_ask - best_bid) / mid_price) × 100
```

**Formule**:
```
Spread (%) = ((Ask - Bid) / Mid) × 100%

Où Mid = (Ask + Bid) / 2
```

---

### **Exemple pratique**

**Scénario 1 : Spread serré (bon)**
```
Ask: 100.15 USDT
Bid: 100.10 USDT
Mid: 100.125 USDT

Spread = ((100.15 - 100.10) / 100.125) × 100
       = (0.05 / 100.125) × 100
       = 0.05%  ✅ Excellent
```

**Scénario 2 : Spread large (mauvais)**
```
Ask: 100.50 USDT
Bid: 100.00 USDT
Mid: 100.25 USDT

Spread = ((100.50 - 100.00) / 100.25) × 100
       = 0.50%  ❌ Trop large, illiquid
```

---

### **Seuil de rejet**
```
Si spread > 0.05% → PAIRE REJETÉE ❌
```

**Pourquoi?**  
Un spread large indique:
- Faible liquidité
- Risque de slippage élevé
- Coûts d'entrée/sortie augmentés

---

## 📍 POINT 3 : VOLUME

### **Définition**
**Quantité totale** de crypto échangée sur une période.

### **Calcul**
```python
# Récupérer volumes des 60 dernières bougies 1m
volumes = [k[5] for k in klines]

# Volume 5 dernières minutes
vol5_recent = sum(volumes[-5:])

# Volume 15 dernières minutes
vol15_recent = sum(volumes[-15:])
```

---

### **Exemple pratique**

**BTC_USDT** (liquide):
```
Volumes 5m: [150, 180, 200, 170, 160]
Vol5_recent = 860 USDT  ✅ Élevé
```

**ALT_USDT** (faiblement liquide):
```
Volumes 5m: [5, 8, 3, 6, 4]
Vol5_recent = 26 USDT  ❌ Trop faible
```

---

### **Seuil minimum**
```
Volume 5m < 100,000 → PAIRE REJETÉE ❌
```

**Pourquoi?**  
Un volume faible indique:
- Risque de manipulation
- Difficulté à entrer/sortir
- Pas assez d'activité pour scalper

---

## 📍 POINT 4 : PROFONDEUR DU CARNET (Book Depth)

### **Définition**
**Volume total** disponible aux 5 meilleurs niveaux bid/ask dans le carnet d'ordres.

### **Calcul**
```python
# Récupérer carnet (5 niveaux)
orderbook = await client.fetch_order_book(symbol, limit=5)

asks = orderbook['asks']  # Prix de vente
bids = orderbook['bids']  # Prix d'achat

# Calculer volumes
ask_vol = sum(float(ask[1]) for ask in asks[:5])  # Volume total ask
bid_vol = sum(float(bid[1]) for bid in bids[:5])  # Volume total bid

total_vol = ask_vol + bid_vol  # Book depth
```

---

### **Exemple pratique**

**BTC_USDT** (profondeur élevée):
```
Ask (vente):
  [100.15, 150 USDT]
  [100.20, 200 USDT]
  [100.25, 180 USDT]
  [100.30, 220 USDT]
  [100.35, 190 USDT]
Ask total: 940 USDT

Bid (achat):
  [100.10, 200 USDT]
  [100.05, 250 USDT]
  [100.00, 180 USDT]
  [99.95, 210 USDT]
  [99.90, 240 USDT]
Bid total: 1080 USDT

Book Depth = 940 + 1080 = 2020 USDT  ✅ Très profond
```

**ALT_USDT** (profondeur faible):
```
Ask total: 50 USDT
Bid total: 45 USDT
Book Depth = 95 USDT  ❌ Trop peu profond
```

---

### **Utilité**
La profondeur indique:
- Facile d'exécuter des ordres importants
- Moins de risque de slippage
- Bons niveaux de support/résistance

---

## 📍 POINT 5 : BALANCE SCORE

### **Définition**
**Équilibre** entre volume bid (achat) et ask (vente) dans le carnet d'ordres.

### **Calcul**
```python
# Ratio bid/ask
bid_ask_ratio = bid_vol / total_vol if total_vol > 0 else 0.5

# Score (0-1)
# 0 = totalement déséquilibré
# 1 = parfaitement équilibré
balance_score = 1 - (abs(bid_ask_ratio - 0.5) × 2)
```

---

### **Exemple pratique**

**Scénario 1 : Équilibré (parfait)**
```
Bid total: 1000 USDT
Ask total: 1000 USDT
Total: 2000 USDT

Bid ratio = 1000 / 2000 = 0.5
Balance Score = 1 - (|0.5 - 0.5| × 2) = 1.0  ✅ Parfait
```

**Scénario 2 : Déséquilibré (mauvais)**
```
Bid total: 2000 USDT  (acheteurs)
Ask total: 100 USDT   (vendeurs)
Total: 2100 USDT

Bid ratio = 2000 / 2100 = 0.95
Balance Score = 1 - (|0.95 - 0.5| × 2) = 0.1  ❌ Très déséquilibré
```

**Scénario 3 : Légèrement déséquilibré**
```
Bid total: 1200 USDT
Ask total: 800 USDT
Total: 2000 USDT

Bid ratio = 1200 / 2000 = 0.6
Balance Score = 1 - (|0.6 - 0.5| × 2) = 0.8  ⚠️ Acceptable
```

---

### **Seuil minimum**
```
Balance Score < 0.7 → PAIRE REJETÉE ❌
```

**Pourquoi?**  
Un déséquilibre fort indique:
- Risque de slippage asymétrique
- Manipulation potentielle
- Ordres difficilement exécutables

---

## 📍 POINT 6 : SCORE FINAL

### **Formule**
```
Score = (VolSpreadRatio × log10(Volume) × NormFactor × BalanceBonus)

Avec:
  - VolSpreadRatio = Vol5 / Spread  (le plus élevé, le mieux)
  - log10(Volume) = Échelle logarithmique du volume
  - NormFactor = 50% Volume_norm + 50% Depth_norm
  - BalanceBonus = Balance Score
```

---

### **Détail des composantes**

**1. VolSpreadRatio**
```
Ratio = Vol5 / Spread

Exemple:
  Vol5 = 1.5%
  Spread = 0.03%
  Ratio = 1.5 / 0.03 = 50  ✅ Excellent
```

**Logique**: Plus la volatilité est élevée **par rapport** au spread, plus le ratio R:R est favorable.

---

**2. Log10(Volume)**
```
log10(100,000) = 5.0
log10(1,000,000) = 6.0
log10(10,000,000) = 7.0
```

**Logique**: Éviter que les gros volumes dominent trop le score. Le log réduit l'influence des très gros volumes.

---

**3. NormFactor** (Normalisation)
```
norm_factor = 0.5 × (Volume / MaxVolume) + 0.5 × (Depth / MaxDepth)

Exemple:
  Volume relatif = 800k / 2M = 0.4
  Depth relatif = 1.5k / 3k = 0.5
  NormFactor = 0.5 × 0.4 + 0.5 × 0.5 = 0.45
```

**Logique**: Normaliser volume et profondeur sur une échelle 0-1 pour comparaison équitable.

---

**4. BalanceBonus**
```
Balance Score (0-1) = 1 - (|bid_ratio - 0.5| × 2)
```

**Logique**: Pénaliser les paires déséquilibrées.

---

### **Exemple complet**

**Paire A : BTC_USDT**
```
Vol5: 0.5%
Spread: 0.02%
VolSpreadRatio: 25

Volume 5m: 2,000,000 USDT
log10(Volume): 6.3

MaxVolume: 5,000,000
MaxDepth: 5,000
NormFactor: 0.6

BalanceScore: 0.95

Score = 25 × 6.3 × 0.6 × 0.95 = 89.8  ✅ Très bon
```

**Paire B : ALT_USDT**
```
Vol5: 2.0%
Spread: 0.10%
VolSpreadRatio: 20

Volume 5m: 150,000 USDT
log10(Volume): 5.2

MaxVolume: 5,000,000
MaxDepth: 5,000
NormFactor: 0.1

BalanceScore: 0.6

Score = 20 × 5.2 × 0.1 × 0.6 = 6.2  ⚠️ Faible
```

---

## 📍 POINT 7 : FILTRAGE STICT

### **Critères de rejet**

**1. Spread**
```
Si spread > 0.05% → REJETÉ ❌
```

**2. Volume**
```
Si recentVolume < 100,000 → REJETÉ ❌
```

**3. Balance**
```
Si balanceScore < 0.7 → REJETÉ ❌
```

**4. Score**
```
Si score ≤ 0 → REJETÉ ❌
```

---

### **Valeurs NaN**
```
Si spread = NaN → REJETÉ ❌
Si bookDepth = 0 → REJETÉ ❌
```

---

## 📍 POINT 8 : PROCESSUS DE SCAN

### **Étapes**

**1. Récupération des paires 0% fees**
```python
# Charger tous les markets MEXC
markets = await client.exchange.load_markets()

# Filtrer: type = swap, quote = USDT
for symbol, market in markets.items():
    if market['type'] == 'swap' and market['quote'] == 'USDT':
        # Vérifier 0% fees
        if maker_fee == 0 and taker_fee == 0:
            futures_pairs.append(symbol)
```

---

**2. Scan par batch** (parallélisation)
```python
BATCH_SIZE = 5  # Scanner 5 paires simultanément

for i in range(0, len(futures_pairs), BATCH_SIZE):
    batch = futures_pairs[i:i + BATCH_SIZE]
    
    # Scanner en parallèle avec asyncio.gather
    results = await asyncio.gather(*[
        self.scan_pair(p['symbol']) for p in batch
    ], return_exceptions=True)
    
    # Pause 0.05s entre batches
    await asyncio.sleep(0.05)
```

**Avantage**: Scan **5× plus rapide** que séquentiel.

---

**3. Normalisation**
```python
# Trouver les maxima pour normalisation
max_volume = max([p['recentVolume'] for p in valid_pairs])
max_depth = max([p['bookDepth'] for p in valid_pairs])

# Calculer scores
for pair in futures_pairs:
    pair['score'] = self.calculate_score(pair, max_volume, max_depth)
```

---

**4. Tri et sélection**
```python
# Filtrer score > 0
scored_pairs = [p for p in futures_pairs if p.get('score', 0) > 0]

# Trier par score décroissant
scored_pairs.sort(key=lambda x: x['score'], reverse=True)

# Top N paires
top_pairs = scored_pairs[:n]
```

---

## 📍 POINT 9 : STRUCTURE DES DONNÉES

### **Objet paire**
```python
pair = {
    'symbol': 'BTC_USDT',
    'price': 67000.0,
    'recentVolume': 2000000.0,     # Volume 5m
    'vol5': 0.5,                    # Volatilité 5m (%)
    'vol15': 0.8,                   # Volatilité 15m (%)
    'spread': 0.02,                 # Spread (%)
    'bookDepth': 2020.0,            # Profondeur (USDT)
    'balanceScore': 0.95,           # Équilibre (0-1)
    'score': 89.8                   # Score final
}
```

---

### **Exemples de valeurs typiques**

| Paire | Vol5 | Spread | Volume | Depth | Balance | Score |
|-------|------|--------|--------|-------|---------|-------|
| **BTC_USDT** | 0.5% | 0.02% | 2M | 2K | 0.95 | **89.8** |
| **ETH_USDT** | 0.8% | 0.03% | 1.5M | 1.5K | 0.90 | **62.3** |
| **SOL_USDT** | 1.5% | 0.04% | 800K | 800 | 0.85 | **34.5** |
| **ALT_USDT** | 2.0% | 0.10% | 200K | 200 | 0.60 | **0.0** ❌ |

---

## 🔟 RÉSUMÉ

### **Métriques collectées**

| Métrique | Symbole | Formule | Idéal |
|----------|---------|---------|-------|
| **Volatilité 5m** | Vol5 | σ / μ × 100 | 0.6-3% |
| **Volatilité 15m** | Vol15 | σ / μ × 100 | 0.8-5% |
| **Spread** | - | (Ask-Bid)/Mid × 100 | < 0.05% |
| **Volume 5m** | - | Σ volumes | > 100K |
| **Profondeur** | Depth | Σ bid/ask 5 niveaux | > 1K |
| **Balance** | - | 1 - |ratio-0.5|×2 | > 0.7 |
| **Score** | - | VSR × log(V) × N × B | > 0 |

---

### **Critères de sélection**

**Obligatoires**:
1. ✅ Fees = 0%
2. ✅ Spread ≤ 0.05%
3. ✅ Volume ≥ 100K
4. ✅ Balance ≥ 0.7
5. ✅ Score > 0

**Plus le score est élevé, meilleure est la paire.**

---

**Date**: 2025-11-02  
**Version**: v6.2  
**Document**: Scan de scalabilité complet




