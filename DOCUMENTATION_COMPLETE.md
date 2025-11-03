# 📚 DOCUMENTATION COMPLÈTE - TRADE CURSOR v7.0

**Date**: 2025-11-03  
**Version**: 7.0 FastAPI  
**Status**: ✅ Documentation complète

---

## 📋 TABLE DES MATIÈRES

1. [Scanner de Scalabilité](#1-scanner-de-scalabilité)
2. [Conditions de Scalabilité 0% Fee](#2-conditions-de-scalabilité-0-fee)
3. [Rotation des Scans](#3-rotation-des-scans)
4. [Scan de Prise de Trade](#4-scan-de-prise-de-trade)
5. [Modes TP/SL](#5-modes-tpsl)
6. [Système de Confluence](#6-système-de-confluence)
7. [Timeframes et Tendances](#7-timeframes-et-tendances)
8. [Statistiques](#8-statistiques)
9. [Réglages Disponibles](#9-réglages-disponibles)
10. [Indicateurs Techniques](#10-indicateurs-techniques)
11. [Gestion des Positions](#11-gestion-des-positions)
12. [WebSocket & Prix en Temps Réel](#12-websocket--prix-en-temps-réel)

---

## 1. SCANNER DE SCALABILITÉ

### 🎯 **Objectif**

Le scanner de scalabilité identifie les meilleures paires pour le scalping en analysant plusieurs critères :
- Volatilité optimale
- Spread faible
- Volume élevé
- Profondeur du carnet d'ordres
- Balance bid/ask

### 📊 **Processus de Scan**

#### **Étape 1 : Récupération des Paires 0% Fee**

```python
# Fichier: core/scanner.py - scan_top_pairs()

# Récupère toutes les paires futures USDT
markets = await self.client.exchange.load_markets()
futures_pairs = []

for symbol, market in markets.items():
    if market['type'] == 'swap' and market['quote'] == 'USDT':
        # Vérifier 0% fees
        maker_fee = market.get('maker', 0)
        taker_fee = market.get('taker', 0)
        if maker_fee == 0 and taker_fee == 0:
            futures_pairs.append({
                'symbol': symbol,
                'maker': maker_fee,
                'taker': taker_fee
            })
```

**Critères** :
- ✅ Type : `swap` (contrats perpétuels)
- ✅ Quote : `USDT`
- ✅ Maker fee : `0%`
- ✅ Taker fee : `0%`

**Résultat typique** : ~115 paires trouvées

---

#### **Étape 2 : Scan par Batch (5 paires en parallèle)**

```python
BATCH_SIZE = 5
total_batches = math.ceil(len(futures_pairs) / BATCH_SIZE)

for i in range(0, len(futures_pairs), BATCH_SIZE):
    batch = futures_pairs[i:i + BATCH_SIZE]
    # Scanner en parallèle
    results = await asyncio.gather(*[self.scan_pair(p['symbol']) for p in batch])
```

**Avantages** :
- ✅ Rapidité : 5 paires analysées simultanément
- ✅ Pas de surcharge API
- ✅ Pause de 0.05s entre batches

---

#### **Étape 3 : Analyse de Chaque Paire**

**Métriques collectées** :

1. **Volatilité** :
   - `vol5` : Volatilité sur 5 périodes (1m)
   - `vol15` : Volatilité sur 15 périodes (1m)
   - Calcul : Écart-type normalisé des prix de clôture

2. **Volume** :
   - `recentVolume` : Volume cumulé sur 5 dernières bougies 1m

3. **Spread** :
   - `spread` : Écart bid/ask en %
   - Calcul : `((best_ask - best_bid) / mid_price) * 100`

4. **Profondeur** :
   - `bookDepth` : Volume total des 5 premiers niveaux (bid + ask)
   - `bidVol` : Volume bid cumulé
   - `askVol` : Volume ask cumulé

5. **Balance** :
   - `balanceScore` : Équilibre bid/ask (0-1)
   - Calcul : `1 - (abs(bid_ask_ratio - 0.5) * 2)`
   - `1.0` = parfaitement équilibré
   - `0.0` = très déséquilibré

---

#### **Étape 4 : Calcul du Score de Scalabilité**

**Formule** :
```python
score = (vol_spread_ratio × log10(volume) × norm_factor × balance_bonus)
```

**Composants** :

1. **vol_spread_ratio** :
   ```python
   vol_spread_ratio = (vol5 / spread) if spread > 0 else 0
   ```
   - Plus élevé = mieux (volatilité élevée, spread faible)

2. **log10(volume)** :
   - Normalise le volume (logarithme base 10)
   - Évite la domination des très gros volumes

3. **norm_factor** :
   ```python
   norm_factor = 0.5 * (recentVolume / max_volume) + 0.5 * (bookDepth / max_depth)
   ```
   - Combine volume et profondeur (normalisés)

4. **balance_bonus** :
   ```python
   balance_bonus = balanceScore
   ```
   - Multiplie par le score de balance

**Filtres stricts** :
- ❌ Spread > 0.02% → Score = 0
- ❌ Volume < 100,000 → Score = 0
- ❌ Balance score < 0.7 → Score = 0

---

#### **Étape 5 : Tri et Sélection Top N**

```python
# Filtrer et trier
scored_pairs = [p for p in futures_pairs if p.get('score', 0) > 0]
scored_pairs.sort(key=lambda x: x['score'], reverse=True)
top_pairs = scored_pairs[:n]  # Top 20 par défaut
```

**Résultat** : Liste des meilleures paires triée par score décroissant

---

### ⏱️ **Durée du Scan**

**Typique** :
- 115 paires × 5 batches = 23 batches
- ~40-50 secondes total

**Optimisations** :
- Scan en parallèle (5 paires simultanées)
- Pause minimale entre batches (0.05s)

---

## 2. CONDITIONS DE SCALABILITÉ 0% FEE

### ✅ **Conditions Requises**

Pour qu'une paire soit considérée comme "scalable", elle doit remplir **TOUTES** ces conditions :

#### **1. Type de Contrat**
- ✅ Type : `swap` (contrat perpétuel)
- ✅ Quote : `USDT` (pas USD, USDC, etc.)

#### **2. Frais**
- ✅ Maker fee : `0%`
- ✅ Taker fee : `0%`

#### **3. Spread**
- ✅ Spread ≤ 0.02%
- ❌ Si spread > 0.02% → Score = 0

#### **4. Volume**
- ✅ Volume récent (5 bougies 1m) ≥ 100,000
- ❌ Si volume < 100,000 → Score = 0

#### **5. Balance Bid/Ask**
- ✅ Balance score ≥ 0.7 (configurable via `balance_score_min`)
- ❌ Si balance < 0.7 → Score = 0

**Balance score** :
- `1.0` = Parfaitement équilibré (50% bid, 50% ask)
- `0.7` = Légèrement déséquilibré (acceptable)
- `0.0` = Très déséquilibré (rejeté)

---

### 📊 **Exemple de Paire Scalable**

```json
{
  "symbol": "HBAR/USDT:USDT",
  "score": 14.53,
  "spread": 0.015,
  "recentVolume": 2500000,
  "vol5": 0.8,
  "bookDepth": 500000,
  "balanceScore": 0.85,
  "bidVol": 240000,
  "askVol": 260000
}
```

**Analyse** :
- ✅ Spread : 0.015% < 0.02% ✅
- ✅ Volume : 2,500,000 > 100,000 ✅
- ✅ Balance : 0.85 > 0.7 ✅
- ✅ Score : 14.53 (élevé)

---

## 3. ROTATION DES SCANS

### 🔄 **Système de Rotation**

Le système utilise un **Scheduler** avec 3 boucles automatiques :

#### **1. Scanner Loop (45 secondes)**

**Fonction** : Scanner les top paires pour détecter des setups de trading

**Fichier** : `core/scheduler.py` + `main.py` (scanner_loop_callback)

**Processus** :
1. Vérifier si `top_pairs` existe
2. Si vide → Scanner initial (top 20)
3. Démarrer WebSocket pour top 30 paires
4. Scanner top 20 paires en parallèle
5. Sélectionner le meilleur setup
6. Attendre 45 secondes
7. Répéter

**Configuration** :
```python
TRADING_CONFIG = {
    "scan_interval": 45,  # secondes
}
```

---

#### **2. Position Check Loop (2 secondes)**

**Fonction** : Vérifier l'état de la position active (TP/SL, break-even, trailing)

**Fichier** : `core/scheduler.py` + `main.py` (position_check_loop_callback)

**Processus** :
1. Récupérer prix actuel (WebSocket prioritaire)
2. Calculer P&L
3. Vérifier break-even
4. Vérifier trailing stop
5. Vérifier TP/SL
6. Si TP/SL touché → Fermer position
7. Attendre 2 secondes
8. Répéter

**Configuration** :
```python
TRADING_CONFIG = {
    "check_interval": 2,  # secondes
}
```

---

#### **3. Scalability Refresh Loop (90 secondes)**

**Fonction** : Rafraîchir la liste des top paires scalables

**Fichier** : `core/scheduler.py` + `main.py` (scalability_refresh_loop_callback)

**Processus** :
1. Scanner toutes les paires 0% fee
2. Calculer scores de scalabilité
3. Sélectionner top 20
4. Mettre à jour `app_state['top_pairs']`
5. Arrêter WebSocket actuel
6. Redémarrer WebSocket avec nouvelles top pairs
7. Attendre 90 secondes
8. Répéter

**Configuration** :
```python
TRADING_CONFIG = {
    "scalability_interval": 90,  # secondes
}
```

---

### 📊 **Diagramme de Rotation**

```
┌─────────────────────────────────────────┐
│  Scanner Loop (45s)                     │
│  ├─ Scan top 20 paires                  │
│  ├─ Détecter setups                     │
│  └─ Ouvrir position si setup trouvé     │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│  Position Check Loop (2s)               │
│  ├─ Vérifier prix actuel                │
│  ├─ Calculer P&L                        │
│  ├─ Break-even / Trailing                │
│  └─ Fermer si TP/SL touché              │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│  Scalability Refresh (90s)              │
│  ├─ Scanner toutes les paires          │
│  ├─ Calculer scores                     │
│  ├─ Mettre à jour top 20                │
│  └─ Redémarrer WebSocket                │
└─────────────────────────────────────────┘
```

---

## 4. SCAN DE PRISE DE TRADE

### 🔍 **Processus de Détection de Setup**

Le scan de prise de trade analyse les top paires pour détecter des opportunités LONG ou SHORT.

---

#### **Étape 1 : Sélection des Paires à Scanner**

```python
# Fichier: main.py - scanner_loop_callback()

from config import TRADING_CONFIG
max_pairs = TRADING_CONFIG.get('top_pairs_limit', 20)
top_n = min(max_pairs, len(app_state['top_pairs']))
pairs_to_scan = app_state['top_pairs'][:top_n]
```

**Par défaut** : Top 20 paires scannées en parallèle

---

#### **Étape 2 : Analyse Parallèle**

```python
# Scanner toutes les paires en parallèle
scan_tasks = []
for pair in pairs_to_scan:
    symbol = pair.get('symbol', '')
    if symbol:
        scan_tasks.append(scan_pair_for_setup(symbol))

# Attendre tous les scans
results = await asyncio.gather(*scan_tasks, return_exceptions=True)
```

**Avantages** :
- ✅ 20 paires analysées simultanément
- ✅ Réduction temps d'attente (vs séquentiel)
- ✅ Détection plus rapide des opportunités

---

#### **Étape 3 : Analyse Technique par Timeframe**

Pour chaque paire, 2 timeframes sont analysés :

**1m (1 minute)** :
- Analyse rapide, setups de scalping
- Volatilité élevée détectée
- Signaux courts terme

**5m (5 minutes)** :
- Analyse plus stable, tendances courtes
- Moins de bruit, signaux plus fiables
- Confirmation de tendance

**Fichier** : `core/analyzer.py` - `analyze_timeframe()`

---

#### **Étape 4 : Application des Filtres**

**Filtres bloquants** (doivent tous passer) :

1. **Volume** :
   ```python
   min_vol_ratio = 0.8 * volume_multiplier  # Adaptatif selon ATR
   if vol_spike < min_vol_ratio:
       return None  # ❌ Rejeté
   ```

2. **Micro-range** :
   ```python
   min_range = atr_percent * 0.2
   if candle_range < min_range:
       return None  # ❌ Bougie trop plate
   ```

3. **ATR Optimal** :
   ```python
   # 1m
   if atr_percent < 0.15 or atr_percent > 0.8:
       return None  # ❌ ATR hors zone optimale
   
   # 5m
   if atr_percent < 0.3 or atr_percent > 1.5:
       return None  # ❌ ATR hors zone optimale
   ```

4. **SNR (Signal-to-Noise Ratio)** :
   ```python
   snr = abs(price - ema21) / atr
   if snr < 0.3:
       return None  # ❌ Signal trop faible
   ```

5. **Breakout** :
   ```python
   breakout_threshold = atr * 0.3
   if price dans range ±ATR*0.3 autour de EMA21:
       return None  # ❌ Pas de breakout
   ```

6. **Wick Ratio** :
   ```python
   wick_ratio = (high - low) / body
   if wick_ratio > 2.5:
       return None  # ❌ Wicks suspects (manipulation)
   ```

7. **Volume Quality** :
   ```python
   if quality < 75 or not shouldTrade:
       return None  # ❌ Volume qualité insuffisante
   ```

8. **Swing Structure** :
   ```python
   # LONG: HH ou HL requis
   # SHORT: LH ou LL requis
   if not has_swing:
       return None  # ❌ Pas de structure swing
   ```

---

#### **Étape 5 : Collecte des Conditions**

**Conditions LONG** (7 possibles) :

1. **EMAs** :
   ```python
   if ema9 > ema21 and ema_diff_percent > 0.05:
       conditions.append("EMAs Up")
   ```

2. **RSI** :
   ```python
   # Rebound: RSI 30-40, ADX < 20, RSI ↑
   # Pullback: RSI 45-55, MACD > 0, ADX > 25, RSI ↑
   if rsi_rebound or rsi_pullback:
       conditions.append("RSI Rebound↑" ou "RSI Pullback↑")
   ```

3. **Volume** :
   ```python
   if vol_spike > 1.5:
       conditions.append("Vol >>1.5x")
   else:
       conditions.append("Vol >0.8x")
   ```

4. **MACD** :
   ```python
   # Bullish: MACD > Signal OU Histogram > 0
   # Momentum: Histogram ↑
   if macd_bullish and macd_momentum:
       conditions.append("MACD+↑ (momentum)")
   ```

5. **Bollinger Bands** :
   ```python
   dist_to_lower = ((price - bb_lower) / bb_lower) * 100
   if dist_to_lower < threshold:
       conditions.append("BB Lower")
   ```

6. **ADX + DI Gap** :
   ```python
   # ADX > 25 + DI+ > DI- + Gap > 5
   if adx > 25 and diPlus > diMinus and gap > 5:
       conditions.append("ADX+ + DI Gap>5")
   ```

7. **Pattern** :
   ```python
   patterns = ['ENGULFING_BULLISH', 'HAMMER', 'DOJI_DRAGONFLY', ...]
   if pattern in patterns:
       conditions.append(f"Pattern: {pattern}")
   ```

**Conditions SHORT** (7 possibles) : Même logique inversée

---

#### **Étape 6 : Validation du Setup**

**Tolérance dynamique** :

```python
min_conditions = 6  # Par défaut

# Ajustement selon ADX
if adx > 30:
    min_conditions = 5      # Moins strict si tendance forte
elif adx >= 25:
    min_conditions = 5.5    # Intermédiaire
```

**Bonus** :
- **Trend bonus** : +0 à +3 conditions selon tendance
- **Divergence bonus** : +1 condition si divergence RSI/MACD

**Validation** :
```python
long_with_bonus = len(long_conditions) + trend_bonus + divergence_bonus
if long_with_bonus >= min_conditions:
    direction = 'LONG'
elif short_with_bonus >= min_conditions:
    direction = 'SHORT'
else:
    return None  # ❌ Pas assez de conditions
```

**Cohérence EMA/MACD** :
```python
# LONG mais MACD très négatif → Rejet
if direction == 'LONG' and ema9 > ema21 and macd_histogram <= -0.001:
    return None

# SHORT mais MACD très positif → Rejet
if direction == 'SHORT' and ema9 < ema21 and macd_histogram >= 0.001:
    return None
```

---

#### **Étape 7 : Sélection du Meilleur Setup**

```python
# Trouver le meilleur setup parmi tous les résultats
best_setup = None
best_symbol = None
best_score = 0

for result in results:
    if result and isinstance(result, dict):
        score = result.get('totalScore', 0)
        if score > best_score:
            best_setup = result
            best_symbol = symbol
            best_score = score

# Si setup trouvé, l'émettre
if best_setup and best_symbol:
    await sio.emit('setup_detected', {
        'symbol': best_symbol,
        'analysis': best_setup
    })
```

---

### 📊 **Résumé du Scan**

**Logs typiques** :
```
[22:25:53] INFO: Scanner loop - Analyse 20/20 paires disponibles
[22:25:53] 🔍 Analyse HBAR/USDT:USDT...
[22:25:53] 🔍 Analyse ADA/USDT:USDT...
...
[22:25:53] ✅ HBAR/USDT:USDT: Setup trouvé - LONG - Score: 8.5
[22:25:53] 📡 INFO: Résumé scan - 1 setups valides, 19 sans setup, 0 erreurs
```

---

## 5. MODES TP/SL

Le système supporte **2 modes** de gestion TP/SL :

### 🔧 **Mode FIXE**

**Configuration** :
```python
TRADING_CONFIG = {
    "tp_sl_mode": "FIXE",
    "tp_percent": 0.25,      # +0.25%
    "sl_percent": 0.25,      # -0.25%
}
```

**Calcul** :
```python
# LONG
sl = entry * (1 - 0.25 / 100)  # -0.25%
tp = entry * (1 + 0.25 / 100)  # +0.25%

# SHORT
sl = entry * (1 + 0.25 / 100)  # +0.25%
tp = entry * (1 - 0.25 / 100)  # -0.25%
```

**Exemple** :
```
Entry: 100.000
LONG:
  SL: 99.750 (-0.25%)
  TP: 100.250 (+0.25%)
  Ratio: 1:1
```

**Gestion avancée** :

1. **Break-even** :
   ```python
   if pnl >= 0.3%:  # +0.3%
       sl = entry  # SL au prix d'entrée
   ```
   - Déclenché à +0.3%
   - Protection : Position sans risque

2. **TP Partiel** :
   ```python
   if pnl >= 0.3% and not partial_tp_sold:
       # Vendre 50% à +0.3%
       partial_tp_sold = True
       size_remaining = size * 0.5
       sl = entry  # Break-even immédiat
   ```
   - 50% vendu à +0.3%
   - 50% restant protégé au break-even

3. **Trailing Stop** :
   ```python
   if partial_tp_sold and pnl > 0.3%:
       # LONG
       new_sl = current_price * (1 - 0.15 / 100)  # -0.15%
       if new_sl > sl:
           sl = new_sl  # Suit la hausse
   ```
   - Distance : 0.15%
   - Suit le prix après TP partiel
   - Verrouille les profits

---

### 📈 **Mode ATR**

**Configuration** :
```python
TRADING_CONFIG = {
    "tp_sl_mode": "ATR",
    "atr_mult_tp": 3.0,      # TP = ATR × 3.0
    "atr_mult_sl": 1.5,      # SL = ATR × 1.5
    "atr_min": 0.15,         # ATR minimum 0.15%
    "atr_max": 1.5,          # ATR maximum 1.5%
}
```

**Calcul** :
```python
# ATR Multi-Timeframe (70% 1m + 30% 5m)
atr_blended = (atr_1m * 0.7) + (atr_5m * 0.3)

# ATR en pourcentage
atr_percent = (atr_blended / entry) * 100

# Clamp ATR
if atr_percent < 0.15:
    atr_percent = 0.15
elif atr_percent > 1.5:
    atr_percent = 1.5

# Multipliers dynamiques selon win/loss streaks
if win_streak >= 3:
    tp_mult = 4.0  # Plus agressif
    sl_mult = 1.2
elif loss_streak >= 2:
    tp_mult = 1.5  # Plus prudent
    sl_mult = 1.2

# Calcul TP/SL
if direction == 'LONG':
    sl = entry * (1 - atr_percent / 100 * sl_mult)
    tp = entry * (1 + atr_percent / 100 * tp_mult)
else:
    sl = entry * (1 + atr_percent / 100 * sl_mult)
    tp = entry * (1 - atr_percent / 100 * tp_mult)
```

**Exemple** :
```
Entry: 100.000
ATR 1m: 0.8%
ATR 5m: 1.2%
ATR blended: (0.8 × 0.7) + (1.2 × 0.3) = 0.92%

LONG (normal):
  SL: 100.000 × (1 - 0.92% × 1.5) = 98.620 (-1.38%)
  TP: 100.000 × (1 + 0.92% × 3.0) = 102.760 (+2.76%)
  Ratio: 2:1

LONG (win streak 3+):
  SL: 98.920 (-1.08%)
  TP: 103.680 (+3.68%)
  Ratio: 3.4:1 (plus agressif)
```

**Gestion avancée** :

1. **Break-even Progressif** :
   ```python
   # Phase 1: Lock 50% du profit
   if pnl >= atr_percent * 0.5:
       sl = entry + (current_price - entry) * 0.5
   
   # Phase 2: BE total
   if pnl >= atr_percent * 1.0:
       sl = entry
   ```
   - Verrouille progressivement les profits
   - Plus doux que le mode FIXE

2. **Pas de TP Partiel** (mode ATR)
   - Position fermée en entier
   - Break-even progressif seulement

---

### 📊 **Comparaison des Modes**

| Critère | Mode FIXE | Mode ATR |
|---------|-----------|----------|
| **TP/SL** | Fixes (±0.25%) | Dynamiques (ATR × multi) |
| **Ratio** | 1:1 | 2:1 (variable) |
| **Break-even** | +0.3% | Progressif (50% puis 100% ATR) |
| **TP Partiel** | ✅ Oui (50% à +0.3%) | ❌ Non |
| **Trailing Stop** | ✅ Oui (0.15%) | ❌ Non |
| **Adaptation** | ❌ Non | ✅ Oui (volatilité) |
| **Streaks** | ❌ Non | ✅ Oui (win/loss) |

**Recommandation** :
- **Scalping agressif** : Mode FIXE (TP partiel + trailing)
- **Scalping adaptatif** : Mode ATR (s'adapte à la volatilité)

---

## 6. SYSTÈME DE CONFLUENCE

### 🎯 **Objectif**

Le système de confluence permet de combiner les analyses 1m et 5m pour améliorer la qualité des setups.

---

### 🔧 **Mode Confluence (Strict)**

**Configuration** :
```python
TRADING_CONFIG = {
    "use_confluence": True,  # 1m ET 5m requis
}
```

**Logique** :
```python
# Fichier: core/analyzer.py - analyze_pair()

if use_confluence and analysis_1m and analysis_5m:
    # 1. Directions doivent être identiques
    if analysis_1m['direction'] != analysis_5m['direction']:
        return None  # ❌ Rejeté
    
    # 2. Force 5m doit être ≥ 80% de force 1m
    strength_1m = len(analysis_1m['signals'])
    strength_5m = len(analysis_5m['signals'])
    
    if strength_5m < strength_1m * 0.8:
        return None  # ❌ 5m trop faible
    
    # 3. Retourner le meilleur (1m ou 5m)
    best = analysis_1m if strength_1m >= strength_5m else analysis_5m
    best['confirmedBy'] = '1m + 5m confluence'
    return best
```

**Exemple** :
```
Analysis 1m: LONG (6 conditions)
Analysis 5m: LONG (5 conditions)

✅ Directions identiques
✅ 5m ≥ 80% de 1m (5 ≥ 4.8)
✅ Setup valide → Retourne le meilleur (1m)
```

**Avantages** :
- ✅ Confirmation double (1m + 5m)
- ✅ Moins de faux signaux
- ✅ Meilleure qualité

**Inconvénients** :
- ❌ Moins d'opportunités (≈50% moins de trades)
- ❌ Plus strict

---

### 🔧 **Mode Permissif (1m OU 5m)**

**Configuration** :
```python
TRADING_CONFIG = {
    "use_confluence": False,  # 1m OU 5m suffit
}
```

**Logique** :
```python
# Sinon, accepter 1m OU 5m
strength_1m = len(analysis_1m['signals']) if analysis_1m else 0
strength_5m = len(analysis_5m['signals']) if analysis_5m else 0

if strength_1m > 0 or strength_5m > 0:
    # Retourner le meilleur (celui avec le plus de conditions)
    best = analysis_1m if strength_1m > strength_5m else analysis_5m
    best['confirmedBy'] = f"{best['timeframe']} only ({len(best['signals'])} conds)"
    return best
```

**Exemple** :
```
Analysis 1m: LONG (6 conditions)
Analysis 5m: None (pas de setup)

✅ 1m valide → Setup accepté
✅ confirmedBy: "1m only (6 conds)"
```

**Avantages** :
- ✅ Plus d'opportunités (≈2x plus de trades)
- ✅ Détection plus rapide
- ✅ Capture les setups courts terme

**Inconvénients** :
- ❌ Moins de confirmation
- ❌ Plus de faux signaux possibles

---

### 📊 **Recommandation**

**Mode Confluence (True)** :
- ✅ Winrate élevé recherché
- ✅ Capital conservateur
- ✅ Trades moins fréquents OK

**Mode Permissif (False)** :
- ✅ Plus d'opportunités recherchées
- ✅ Capital agressif
- ✅ Trades fréquents souhaités

---

## 7. TIMEFRAMES ET TENDANCES

### 📊 **Timeframes Analysés**

#### **1m (1 minute)**

**Utilisation** :
- Détection rapide des setups
- Scalping court terme
- Signaux réactifs

**Caractéristiques** :
- ATR optimal : 0.15% - 0.8%
- Volatilité élevée
- Plus de bruit
- Setup rapides

**Filtres spécifiques** :
```python
optimal_atr_min_1m = 0.15
optimal_atr_max_1m = 0.8
```

---

#### **5m (5 minutes)**

**Utilisation** :
- Confirmation de tendance
- Scalping moyen terme
- Signaux plus stables

**Caractéristiques** :
- ATR optimal : 0.3% - 1.5%
- Moins de bruit
- Setup plus fiables
- Tendance plus claire

**Filtres spécifiques** :
```python
optimal_atr_min_5m = 0.3
optimal_atr_max_5m = 1.5
```

---

### 📈 **Trend Data (Optionnel)**

**Fichier** : `core/analyzer.py` - `analyze_timeframe()`

**Utilisation** :
```python
# Trend bonus
if trend_data and temp_direction != 'NEUTRAL':
    if temp_direction == 'LONG' and trend_data.get('trend') == 'BULLISH':
        trend_bonus = math.floor(trend_data.get('bonus', 0) / 10)
    elif temp_direction == 'SHORT' and trend_data.get('trend') == 'BEARISH':
        trend_bonus = math.floor(trend_data.get('bonus', 0) / 10)
```

**Bonus** :
- Si direction setup = direction trend → +0 à +3 conditions
- Améliore la qualité des setups dans la tendance

**Note** : Actuellement non utilisé dans le code actuel, mais structure prête.

---

## 8. STATISTIQUES

### 📊 **Système de Métriques**

**Fichier** : `core/metrics.py`

**Métriques collectées** :

#### **1. Générales**
```python
{
    "uptime_seconds": 12345.67,
    "total_requests": 1500,
    "total_errors": 15
}
```

#### **2. Par Endpoint**
```python
{
    "/api/analyze/{symbol}": {
        "requests": 500,
        "successes": 485,
        "errors": 15,
        "success_rate": 97.0,
        "latency_ms": {
            "min": 45.2,
            "max": 1200.5,
            "avg": 125.3,
            "p50": 98.7,
            "p95": 450.2,
            "p99": 800.1
        }
    }
}
```

#### **3. WebSocket**
```python
{
    "connected": true,
    "price_updates": 12500,
    "rest_fallbacks": 45
}
```

#### **4. Trading**
```python
{
    "setups_detected": 25,
    "positions_opened": 20,
    "positions_closed": 18,
    "trades_wins": 12,
    "trades_losses": 6,
    "win_rate": 66.67
}
```

#### **5. Dernières Erreurs**
```python
{
    "last_errors": [
        {
            "timestamp": 1699001234.567,
            "endpoint": "/api/analyze/BTC/USDT:USDT",
            "error": "Price not available"
        }
    ]
}
```

---

### 📈 **Endpoint de Métriques**

**Route** : `GET /api/metrics`

**Réponse** :
```json
{
    "general": { ... },
    "endpoints": { ... },
    "websocket": { ... },
    "trading": { ... },
    "last_errors": [ ... ]
}
```

**Utilisation** :
- Monitoring performance
- Détection de problèmes
- Optimisation

---

## 9. RÉGLAGES DISPONIBLES

### ⚙️ **Configuration Complète**

**Fichier** : `config.py`

#### **Trading Parameters**

```python
TRADING_CONFIG = {
    # Intervalles
    "scan_interval": 45,              # Scanner loop (secondes)
    "check_interval": 2,              # Position check (secondes)
    "scalability_interval": 90,       # Scalability refresh (secondes)
    
    # Volume
    "volume_multiplier": 1.0,         # 0.1 - 2.0
    "volume_multiplier_range": (0.10, 2.00),
    
    # TP/SL Mode
    "tp_sl_mode": "FIXE",             # "FIXE" ou "ATR"
    
    # Mode FIXE
    "tp_percent": 0.25,               # +0.25%
    "sl_percent": 0.25,               # -0.25%
    "break_even_trigger": 0.3,        # +0.3%
    "trailing_distance": 0.1,         # 0.1%
    
    # Mode ATR
    "atr_mult_tp": 1.5,               # TP = ATR × 1.5
    "atr_mult_sl": 1.0,               # SL = ATR × 1.0
    "atr_min": 0.15,                  # ATR minimum 0.15%
    "atr_max": 1.5,                   # ATR maximum 1.5%
    
    # ATR Optimal Filter
    "optimal_atr_min_1m": 0.15,
    "optimal_atr_max_1m": 0.8,
    "optimal_atr_min_5m": 0.3,
    "optimal_atr_max_5m": 1.5,
    
    # Conditions
    "min_conditions": 6,              # Conditions minimum
    "dynamic_tolerance_adx_high": 30, # ADX > 30 → 5 conditions
    "dynamic_tolerance_adx_low": 25,  # ADX < 25 → 6 conditions
    
    # Filtres avancés
    "snr_threshold": 0.3,             # Signal-to-Noise Ratio
    "breakout_threshold": 0.3,        # Breakout multiplier
    "wick_ratio_max": 2.5,            # Max wick ratio
    "di_gap_min": 5,                  # DI gap minimum
    "di_gap_adx_threshold": 25,       # ADX threshold pour DI gap
    
    # Scanner
    "top_pairs_limit": 20,            # Nombre de paires à scanner
    "balance_score_min": 0.7,         # Balance score minimum
    
    # Confluence
    "use_confluence": False,          # True = 1m ET 5m, False = 1m OU 5m
}
```

#### **Risk Management**

```python
RISK_CONFIG = {
    "base_risk": 0.02,                # 2% par défaut
    "quality_multiplier_perfect": 1.5, # 7 conditions
    "quality_multiplier_good": 1.2,    # 6 conditions
    "quality_multiplier_ok": 0.8,     # 5 conditions
    "quality_multiplier_weak": 0.5,   # <5 conditions
    "vol_multiplier_high": 0.7,       # ATR > 2.0%
    "vol_multiplier_low": 1.3,         # ATR < 0.5%
    "max_risk": 0.05,                 # 5% maximum
    "min_risk": 0.005,                # 0.5% minimum
}
```

---

### 🎛️ **Paramètres Modifiables**

#### **Volume Multiplier**

**Range** : 0.1 - 2.0

**Effet** :
- `0.5` : Plus permissif (2x plus de candidats)
- `1.0` : Normal
- `1.5` : Plus strict (moins de candidats)

**Usage** :
```python
# Via API
GET /api/analyze/{symbol}?volume_multiplier=0.8
```

---

#### **Top Pairs Limit**

**Range** : 1 - 50 (recommandé: 20)

**Effet** :
- `10` : Moins de paires, moins de charge
- `20` : Équilibré (recommandé)
- `30` : Plus d'opportunités, plus de charge

---

#### **Confluence Mode**

**Options** :
- `False` : 1m OU 5m (plus d'opportunités)
- `True` : 1m ET 5m (meilleure qualité)

**Usage** :
```python
# Via API
GET /api/analyze/{symbol}?use_confluence=true
```

---

#### **TP/SL Mode**

**Options** :
- `"FIXE"` : TP/SL fixes (±0.25%)
- `"ATR"` : TP/SL dynamiques (ATR × multi)

**Usage** :
```python
# Via config.py
TRADING_CONFIG["tp_sl_mode"] = "ATR"
```

---

## 10. INDICATEURS TECHNIQUES

### 📊 **Indicateurs Utilisés**

**Fichier** : `core/indicators.py`

#### **1. RSI (Relative Strength Index)**

**Période** : 14

**Calcul** :
```python
rsi = calculate_rsi(closes, 14)
rsi_prev = calculate_rsi_previous(closes, 14)
```

**Usage** :
- **LONG** : RSI 30-40 (rebound) ou 45-55 (pullback) avec RSI ↑
- **SHORT** : RSI 60-70 (overbought) ou 45-55 (rejection) avec RSI ↓

---

#### **2. ATR (Average True Range)**

**Période** : 14

**Calcul** :
```python
atr = calculate_atr(highs, lows, closes, 14)
```

**Usage** :
- Filtrage ATR optimal
- Calcul TP/SL (mode ATR)
- Normalisation des distances

---

#### **3. EMAs (Exponential Moving Averages)**

**Périodes** : 9 et 21

**Calcul** :
```python
ema9 = calculate_ema(closes, 9)
ema21 = calculate_ema(closes, 21)
```

**Usage** :
- **LONG** : EMA9 > EMA21 + écart > 0.05%
- **SHORT** : EMA9 < EMA21 + écart > 0.05%
- Cohérence avec MACD

---

#### **4. MACD (Moving Average Convergence Divergence)**

**Paramètres** : Fast=3, Slow=10, Signal=16

**Calcul** :
```python
macd = calculate_macd(closes, 3, 10, 16)
macd_prev = calculate_macd_previous(closes, 3, 10, 16)
```

**Composants** :
- `macd` : Ligne MACD
- `signal` : Ligne de signal
- `histogram` : Histogramme (MACD - Signal)

**Usage** :
- **LONG** : MACD > Signal OU Histogram > 0 + Momentum ↑
- **SHORT** : MACD < Signal OU Histogram < 0 + Momentum ↓
- Divergence RSI/MACD

---

#### **5. Bollinger Bands**

**Paramètres** : Période=20, Écart-type=2

**Calcul** :
```python
bb = calculate_bollinger_bands(closes, 20, 2)
```

**Composants** :
- `upper` : Bande supérieure
- `middle` : Moyenne mobile (20)
- `lower` : Bande inférieure

**Usage** :
- **LONG** : Prix proche de `lower` (< threshold)
- **SHORT** : Prix proche de `upper` (< threshold)

---

#### **6. ADX (Average Directional Index)**

**Période** : 14

**Calcul** :
```python
adx = calculate_adx(highs, lows, closes, 14)
```

**Composants** :
- `adx` : Force de la tendance (0-100)
- `diPlus` : Directional Indicator +
- `diMinus` : Directional Indicator -

**Usage** :
- Tolérance dynamique (ADX > 30 → 5 conditions)
- **LONG** : ADX > 25 + DI+ > DI- + Gap > 5
- **SHORT** : ADX > 25 + DI- > DI+ + Gap > 5

---

#### **7. Patterns (Chandeliers)**

**Patterns détectés** :

**LONG** :
- `ENGULFING_BULLISH` : Absorption haussière
- `HAMMER` : Marteau
- `DOJI_DRAGONFLY` : Doji libellule
- `MARUBOZU_BULLISH` : Marubozu haussier
- `MORNING_STAR` : Étoile du matin
- `DOJI` : Doji neutre

**SHORT** :
- `ENGULFING_BEARISH` : Absorption baissière
- `SHOOTING_STAR` : Étoile filante
- `DOJI_GRAVESTONE` : Doji pierre tombale
- `MARUBOZU_BEARISH` : Marubozu baissier
- `EVENING_STAR` : Étoile du soir

**Détection** :
- Pattern simple (1 bougie)
- Pattern multi-bougies (3 bougies)

---

## 11. GESTION DES POSITIONS

### 📊 **Cycle de Vie d'une Position**

```
┌─────────────────┐
│  Setup Détecté  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Position Ouverte│
│  Entry: 100.000 │
│  SL: 99.750     │
│  TP: 100.250    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Check Loop (2s)│
│  - Prix actuel  │
│  - P&L calculé  │
│  - Break-even?  │
│  - Trailing?    │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌────────┐
│   TP   │ │   SL   │
│ Touché │ │ Touché │
└───┬────┘ └───┬────┘
    │          │
    └────┬─────┘
         │
         ▼
┌─────────────────┐
│ Position Fermée │
│ P&L calculé     │
│ Stats mises     │
└─────────────────┘
```

---

### 🔧 **Gestion Avancée**

#### **Break-even**

**Mode FIXE** :
```python
if pnl >= 0.3%:
    sl = entry  # Protection immédiate
```

**Mode ATR** :
```python
# Phase 1: Lock 50%
if pnl >= atr_percent * 0.5:
    sl = entry + (current_price - entry) * 0.5

# Phase 2: BE total
if pnl >= atr_percent * 1.0:
    sl = entry
```

---

#### **TP Partiel (Mode FIXE uniquement)**

```python
if pnl >= 0.3% and not partial_tp_sold:
    # Vendre 50%
    partial_tp_sold = True
    size_remaining = size * 0.5
    partial_profit_usdt = size * 0.5 * (pnl / 100)
    
    # Break-even immédiat
    sl = entry
```

**Avantages** :
- ✅ Sécurise 50% du profit
- ✅ 50% restant peut continuer
- ✅ Protection au break-even

---

#### **Trailing Stop**

**Mode FIXE** :
```python
if partial_tp_sold and pnl > 0.3%:
    # LONG
    new_sl = current_price * (1 - 0.15 / 100)
    if new_sl > sl:
        sl = new_sl  # Suit la hausse
```

**Distance** : 0.15%

---

#### **Win/Loss Streaks**

**Usage** (Mode ATR) :
```python
if win_streak >= 3:
    tp_mult = 4.0  # Plus agressif
    sl_mult = 1.2
elif loss_streak >= 2:
    tp_mult = 1.5  # Plus prudent
    sl_mult = 1.2
```

**Logique** :
- Win streak → Augmente TP (plus agressif)
- Loss streak → Réduit TP (plus prudent)

---

### 💰 **Calcul P&L**

**Brut** :
```python
pnl_pct = ((exit_price - entry) / entry) * 100
if direction == 'SHORT':
    pnl_pct = -pnl_pct
```

**Avec Position Partielle** :
```python
if has_partial_tp:
    # P&L = TP partiel + fermeture finale
    pnl_final_usdt = partial_profit_usdt + (size_remaining * pnl_pct / 100)
else:
    # Position fermée en entier
    pnl_final_usdt = size * (pnl_pct / 100)
```

**Net** (avec frais et slippage) :
```python
# Frais: 0% (paires scalables)
fees = 0

# Slippage estimé
slippage = estimate_slippage(size, spread, depth, balance)

# Net
net_pnl_pct = pnl_pct - (fees + slippage)
net_pnl_usdt = pnl_final_usdt - (total_costs / 100 * size)
```

---

## 12. WEBSOCKET & PRIX EN TEMPS RÉEL

### 🔌 **WebSocket MEXC**

**Fichier** : `api/price_provider.py`

**Configuration** :
```python
WEBSOCKET_CONFIG = {
    "url": "wss://contract.mexc.com/edge",
    "ping_interval": 30,
    "reconnect_delay": 5,
    "timeout": 10,
}
```

---

### 📊 **Fonctionnement**

#### **1. Connexion**

```python
await price_provider.start_websocket(symbols)
```

**Symboles** : Max 30 symboles par connexion

**Souscription** :
```python
# Format: symbol@ticker
subscriptions = ["HBAR/USDT:USDT@ticker", "ADA/USDT:USDT@ticker", ...]
```

---

#### **2. Réception des Prix**

```python
# WebSocket reçoit les mises à jour
{
    "c": "HBAR/USDT:USDT@ticker",
    "d": {
        "lastPrice": "0.05234",
        "volume24": "1250000",
        ...
    }
}
```

**Cache** : Prix stocké en mémoire avec timestamp

---

#### **3. Récupération du Prix**

```python
# Priorité: WebSocket > REST
price = await price_provider.get_price(symbol)
```

**Processus** :
1. Vérifier cache WebSocket (fraîcheur < 2s)
2. Si cache valide → Retourner prix WebSocket
3. Sinon → Fallback REST API

**Avantages** :
- ✅ Latence minimale (0ms si cache)
- ✅ Pas de rate limit
- ✅ Mises à jour en temps réel

---

### 📊 **Métriques WebSocket**

**Collectées** :
- `ws_connected` : État connexion
- `ws_price_count` : Nombre de prix via WebSocket
- `ws_rest_fallback_count` : Nombre de fallbacks REST

**Endpoint** : `GET /api/metrics`

---

## 🎯 **CONCLUSION**

Cette documentation couvre **toutes** les fonctionnalités du système Trade Cursor v7.0 :

✅ Scanner de scalabilité (0% fee, scoring)  
✅ Rotation des scans (3 boucles automatiques)  
✅ Scan de prise de trade (analyse technique multi-timeframe)  
✅ Modes TP/SL (FIXE et ATR avec gestion avancée)  
✅ Système de confluence (1m ET 5m ou 1m OU 5m)  
✅ Timeframes et tendances (1m, 5m)  
✅ Statistiques (métriques complètes)  
✅ Réglages disponibles (configuration exhaustive)  
✅ Indicateurs techniques (RSI, ATR, EMA, MACD, BB, ADX, Patterns)  
✅ Gestion des positions (break-even, TP partiel, trailing)  
✅ WebSocket & prix temps réel  

**Système prêt pour production** 🚀

