# 📚 Documentation Complète - Trade Cursor

## Table des Matières

1. [Système de Scan des Paires Scalables](#1-système-de-scan-des-paires-scalables)
2. [Système de Recherche de Setups](#2-système-de-recherche-de-setups)
3. [Système de Gestion des Positions](#3-système-de-gestion-des-positions)
4. [Système de Suivi des Positions](#4-système-de-suivi-des-positions)

---

## 1. Système de Scan des Paires Scalables

### 1.1 Vue d'ensemble

Le **ScalabilityScanner** identifie les meilleures paires pour le scalping basé sur plusieurs critères :
- Volatilité optimale
- Spread faible
- Volume élevé
- Profondeur du carnet d'ordres
- Balance bid/ask

### 1.2 Critères de Sélection

#### 1.2.1 Paires 0% Fees

**Source** : API MEXC Futures (`client.exchange.load_markets()`)

**Critères** :
- Type : `swap` (futures)
- Quote : `USDT`
- Maker fee : `0`
- Taker fee : `0`

**Méthode** : `scan_top_pairs(n=20)`

#### 1.2.2 Informations Récupérées de l'API

##### A. Données OHLCV (1 minute)
- **Source** : `client.fetch_ohlcv(symbol, '1m', limit=60)`
- **Période** : 60 bougies (1 heure)
- **Données extraites** :
  - `closes` : Prix de clôture
  - `volumes` : Volumes

##### B. Données Orderbook
- **Source** : `client.fetch_order_book(symbol, limit=5)`
- **Profondeur** : 5 meilleurs niveaux bid/ask
- **Données calculées** :
  - `spread` : Spread en % = `((best_ask - best_bid) / mid_price) * 100`
  - `bookDepth` : Volume total des 5 premiers niveaux = `sum(asks[:5]) + sum(bids[:5])`
  - `balanceScore` : Score d'équilibre (0-1) = `1 - (abs(bid_ask_ratio - 0.5) * 2)`
    - `bid_ask_ratio` = `bid_vol / total_vol`
    - Score = 1 si équilibré, 0 si déséquilibré
  - `bidVol` : Volume total des bids (5 niveaux)
  - `askVol` : Volume total des asks (5 niveaux)

##### C. Volatilités Calculées
- **Vol5** : Volatilité sur 5 bougies (écart-type normalisé en %)
- **Vol15** : Volatilité sur 15 bougies
- **Formule** :
  ```python
  mean = sum(closes[-period:]) / period
  variance = sum((v - mean) ** 2 for v in closes[-period:]) / period
  std = sqrt(variance)
  volatility = (std / mean) * 100
  ```

##### D. Volume Récent
- **Vol5_recent** : Somme des volumes des 5 dernières bougies

### 1.3 Système de Score

#### 1.3.1 Formule de Calcul

```python
score = (volSpreadRatio × log10(volume) × normFactor × balanceBonus)
```

**Composantes** :

1. **volSpreadRatio** :
   - `vol5 / spread` si `spread > 0` et `vol5 > 0`
   - Sinon : `0.0`
   - **Signification** : Ratio volatilité/spread (plus élevé = mieux)

2. **log10(volume)** :
   - `log10(recent_volume + 1)`
   - **Signification** : Logarithme du volume récent (normalisation)

3. **normFactor** :
   - `0.5 × (recent_volume / max_volume) + 0.5 × (book_depth / max_depth)`
   - **Signification** : Facteur de normalisation combinant volume et profondeur

4. **balanceBonus** :
   - `balanceScore` (0-1)
   - **Signification** : Bonus pour équilibre bid/ask

#### 1.3.2 Filtres Stricts

Une paire est **rejetée** (score = 0) si :
- `spread > 0.02%` (spread maximum)
- `recent_volume < 100,000` (volume minimum)
- `balanceScore < balance_score_min` (défaut : 0.7)

**Configuration** :
```python
TRADING_CONFIG['balance_score_min'] = 0.7  # Seuil minimum
```

#### 1.3.3 Normalisation

Avant le calcul des scores :
1. Trouver `max_volume` parmi toutes les paires valides
2. Trouver `max_depth` parmi toutes les paires valides
3. Normaliser chaque paire avec ces valeurs max

#### 1.3.4 Tri et Sélection

1. Filtrer les paires avec `score > 0`
2. Trier par score décroissant
3. Retourner les top N (défaut : 20)

**Configuration** :
```python
TRADING_CONFIG['top_pairs_limit'] = 20  # Nombre de paires à retourner
```

### 1.4 Processus de Scan

#### 1.4.1 Scan Initial

**Déclenchement** : Au démarrage du bot ou si `top_pairs` est vide

**Procédure** :
1. Récupérer toutes les paires futures USDT 0% fees
2. Scanner par batch de 5 paires en parallèle
3. Calculer métriques pour chaque paire
4. Calculer scores et normalisations
5. Trier et sélectionner top 20
6. Mettre en cache dans `app_state['top_pairs']`
7. Démarrer WebSocket pour monitoring prix

**Intervalle** : `TRADING_CONFIG['scalability_interval'] = 90` secondes

#### 1.4.2 Scan Continu

**Déclenchement** : Toutes les 90 secondes (si aucune position active)

**Procédure** :
1. Utiliser `top_pairs` en cache
2. Scanner uniquement les top N paires (défaut : 20)
3. Mettre à jour les métriques
4. Recalculer scores si nécessaire

### 1.5 Métriques Stockées

Chaque paire dans `top_pairs` contient :

```python
{
    'symbol': 'BTC/USDT:USDT',
    'price': 45000.0,              # Prix actuel
    'recentVolume': 1500000.0,     # Volume 5 dernières bougies
    'vol5': 0.45,                  # Volatilité 5 bougies (%)
    'vol15': 0.52,                 # Volatilité 15 bougies (%)
    'spread': 0.015,               # Spread (%)
    'bookDepth': 500000.0,         # Profondeur orderbook
    'balanceScore': 0.85,           # Score équilibre (0-1)
    'bidVol': 250000.0,            # Volume bids
    'askVol': 250000.0,            # Volume asks
    'score': 12.45,                # Score de scalabilité
    'maker': 0.0,                  # Maker fee
    'taker': 0.0                   # Taker fee
}
```

---

## 2. Système de Recherche de Setups

### 2.1 Vue d'ensemble

Le **TechnicalAnalyzer** analyse les paires scalables pour détecter des setups de trading LONG ou SHORT basés sur :
- Indicateurs techniques (EMA, RSI, MACD, ADX, Bollinger)
- Patterns de bougies
- Volume et volatilité
- Filtres de qualité (SNR, Breakout, Wicks, ATR)
- Système de score pondéré

### 2.2 Timeframes Analysés

- **1m** : Timeframe principal pour scalping
- **5m** : Timeframe de confirmation
- **15m** (ou configurable) : Timeframe pour calculer trend bonus

**Configuration** :
```python
TRADING_CONFIG['trend_timeframe'] = '15m'  # 5m, 15m, 30m, 1h
```

### 2.3 Mode Confluence

**Configuration** :
```python
TRADING_CONFIG['use_confluence'] = False  # False = 1m OU 5m, True = 1m ET 5m
```

- **False** : Setup valide si 1m **OU** 5m valide
- **True** : Setup valide si 1m **ET** 5m valides

### 2.4 Indicateurs Techniques

#### 2.4.1 EMA (Exponential Moving Average)

**Périodes** :
- EMA 9 : Tendance courte
- EMA 21 : Tendance moyenne

**Calcul** :
```python
k = 2 / (period + 1)
ema = close * k + ema_prev * (1 - k)
```

**Conditions** :
- **LONG** : `EMA9 > EMA21` ET `diff_percent > 0.05%`
- **SHORT** : `EMA9 < EMA21` ET `diff_percent > 0.05%`

**Poids** : `CONDITION_WEIGHTS['EMAs'] = 2.5` (critique)

#### 2.4.2 RSI (Relative Strength Index)

**Période** : 14

**Calcul** :
```python
avg_gain = sum(gains) / period
avg_loss = sum(losses) / period
rs = avg_gain / avg_loss
rsi = 100 - (100 / (1 + rs))
```

**Conditions LONG** :
- **RSI Rebound** : `30 ≤ RSI ≤ 40` ET `ADX < 20` ET `RSI > RSI_prev`
- **RSI Pullback** : `45 ≤ RSI ≤ 55` ET `MACD histogram > 0` ET `ADX > 25` ET `RSI > RSI_prev`

**Conditions SHORT** :
- **RSI Overbought** : `60 ≤ RSI ≤ 70` ET `ADX < 20` ET `RSI < RSI_prev`
- **RSI Rejection** : `45 ≤ RSI ≤ 55` ET `MACD histogram < 0` ET `ADX > 25` ET `RSI < RSI_prev`

**Poids** : `CONDITION_WEIGHTS['RSI'] = 1.5` (important)

#### 2.4.3 MACD (Moving Average Convergence Divergence)

**Périodes** :
- Fast EMA : 3
- Slow EMA : 10
- Signal : 16

**Calcul** :
```python
macd = EMA_fast - EMA_slow
signal = EMA(macd_values, signal_period)
histogram = macd - signal
```

**Conditions LONG** :
- `MACD > Signal` OU `histogram > 0`
- Bonus si `histogram > histogram_prev` (momentum)

**Conditions SHORT** :
- `MACD < Signal` OU `histogram < 0`
- Bonus si `histogram < histogram_prev` (momentum)

**Poids** : `CONDITION_WEIGHTS['MACD'] = 2.0` (fort)

#### 2.4.4 ADX (Average Directional Index)

**Période** : 14

**Calcul** :
```python
+DM = max(high[i] - high[i-1], 0) if up_move > down_move else 0
-DM = max(low[i-1] - low[i], 0) if down_move > up_move else 0
TR = max(high - low, abs(high - close_prev), abs(low - close_prev))
DI+ = 100 * (avg(+DM) / avg(TR))
DI- = 100 * (avg(-DM) / avg(TR))
DX = 100 * abs(DI+ - DI-) / (DI+ + DI-)
ADX = moyenne(DX)
```

**Conditions LONG** :
- **ADX + DI Gap** : `ADX > 25` ET `DI+ > DI-` ET `DI_gap > 4.0`
- **ADX Fort** : `ADX > 30` ET `DI+ > DI-`

**Conditions SHORT** :
- **ADX + DI Gap** : `ADX > 25` ET `DI- > DI+` ET `DI_gap > 4.0`
- **ADX Fort** : `ADX > 30` ET `DI- > DI+`

**Configuration** :
```python
TRADING_CONFIG['di_gap_min'] = 4.0                    # Gap minimum DI+ - DI-
TRADING_CONFIG['di_gap_adx_threshold'] = 25           # Seuil ADX pour gap
```

**Poids** : `CONDITION_WEIGHTS['ADX_DI'] = 2.5` (critique)

#### 2.4.5 Bollinger Bands

**Période** : 20
**Déviation standard** : 2.0

**Calcul** :
```python
SMA = sum(closes[-20:]) / 20
std = sqrt(sum((val - SMA)²) / 20))
upper = SMA + (std * 2.0)
lower = SMA - (std * 2.0)
width = (upper - lower) / SMA
```

**Conditions LONG** :
- `distance_to_lower < threshold`
- `threshold = max(0.3%, ATR% × 0.5)`

**Conditions SHORT** :
- `distance_to_upper < threshold`
- `threshold = max(0.3%, ATR% × 0.5)`

**Poids** : `CONDITION_WEIGHTS['Bollinger'] = 0.8` (moins fiable)

#### 2.4.6 ATR (Average True Range)

**Période** : 14

**Calcul** :
```python
TR = max(
    high - low,
    abs(high - close_prev),
    abs(low - close_prev)
)
ATR = moyenne(TR sur 14 périodes)
ATR% = (ATR / price) * 100
```

**Utilisation** :
- Filtre ATR optimal (voir section 2.5.4)
- Calcul TP/SL en mode ATR
- Trailing stop adaptatif

### 2.5 Filtres de Qualité

#### 2.5.1 Filtre Volume

**Fonction** : `check_volume_filter()`

**Seuil adaptatif** :
```python
if ATR% > 1.0:
    base_min_vol = 1.0
elif ATR% < 0.3:
    base_min_vol = 0.6
else:
    base_min_vol = 0.8

min_vol_ratio = base_min_vol × volume_multiplier
min_vol_ratio = clamp(min_vol_ratio, 0.4, 1.5)
```

**Configuration** :
```python
TRADING_CONFIG['volume_multiplier'] = 0.95  # Multiplicateur global (0.1-2.0)
```

**Rejet si** : `vol_spike < min_vol_ratio`

#### 2.5.2 Filtre SNR (Signal-to-Noise Ratio)

**Fonction** : `check_snr_filter()`

**Calcul** :
```python
SNR = abs(price - EMA21) / ATR
```

**Configuration** :
```python
TRADING_CONFIG['use_snr'] = True                    # Activer/désactiver
TRADING_CONFIG['snr_threshold'] = 0.25             # Seuil minimum
```

**Rejet si** : `SNR < snr_threshold` (signal trop plat)

#### 2.5.3 Filtre Breakout

**Fonction** : `check_breakout_filter()`

**Calcul** :
```python
breakout_threshold = ATR × breakout_mult
range = [EMA21 - breakout_threshold, EMA21 + breakout_threshold]
```

**Configuration** :
```python
TRADING_CONFIG['use_breakout'] = True               # Activer/désactiver
TRADING_CONFIG['breakout_threshold'] = 0.35         # Multiplicateur ATR
```

**Rejet si** : `price` dans `range` (pas de breakout)

#### 2.5.4 Filtre ATR Optimal

**Fonction** : `check_atr_filter()`

**Seuils par timeframe** :

**1m** :
```python
TRADING_CONFIG['optimal_atr_min_1m'] = 0.12%        # Minimum
TRADING_CONFIG['optimal_atr_max_1m'] = 0.75%        # Maximum
```

**5m** :
```python
TRADING_CONFIG['optimal_atr_min_5m'] = 0.22%        # Minimum
TRADING_CONFIG['optimal_atr_max_5m'] = 1.4%        # Maximum
```

**Rejet si** : `ATR% < min` OU `ATR% > max`

#### 2.5.5 Filtre Wick Ratio

**Fonction** : `check_wick_filter()`

**Calcul** :
```python
body = abs(close - open)
wick_ratio = (high - low) / body
```

**Configuration** :
```python
TRADING_CONFIG['use_wick'] = True                   # Activer/désactiver
TRADING_CONFIG['wick_ratio_max'] = 2.8             # Ratio maximum
```

**Rejet si** : `wick_ratio > wick_ratio_max` (possible manipulation)

### 2.6 Patterns de Bougies

#### 2.6.1 Patterns Simples (1 bougie)

**Détection** : `Indicators.detect_pattern(candle)`

**Patterns LONG** :
- **ENGULFING_BULLISH** : `open < close` ET `body > range × 0.7`
- **HAMMER** : `lower_shadow > body × 2` ET `upper_shadow < body × 0.3`

**Patterns SHORT** :
- **ENGULFING_BEARISH** : `open > close` ET `body > range × 0.7`
- **SHOOTING_STAR** : `upper_shadow > body × 2` ET `lower_shadow < body × 0.3`

**Configuration** :
```python
TRADING_CONFIG['use_engulfing'] = True
TRADING_CONFIG['use_hammer'] = True
TRADING_CONFIG['use_shooting_star'] = True
```

#### 2.6.2 Patterns Multi-Bougies

**Détection** : `Indicators.detect_pattern_multi(candles)`

**Patterns LONG** :
- **DOJI_DRAGONFLY** : `body < range × 0.1` ET `lower_shadow > range × 0.6`
- **DOJI** : `body < range × 0.1`
- **MARUBOZU_BULLISH** : `body > range × 0.95` ET `open < close`
- **MORNING_STAR** : 3 bougies (rouge → petite → verte forte)

**Patterns SHORT** :
- **DOJI_GRAVESTONE** : `body < range × 0.1` ET `upper_shadow > range × 0.6`
- **MARUBOZU_BEARISH** : `body > range × 0.95` ET `open > close`
- **EVENING_STAR** : 3 bougies (verte → petite → rouge forte)

**Configuration** :
```python
TRADING_CONFIG['use_doji'] = True
TRADING_CONFIG['use_marubozu'] = True
TRADING_CONFIG['use_morning_star'] = True
TRADING_CONFIG['use_evening_star'] = True
```

**Poids** : `CONDITION_WEIGHTS['Pattern'] = 0.8` (moins fiable)

### 2.7 Système de Score Pondéré

#### 2.7.1 Poids des Conditions

**Configuration** : `CONDITION_WEIGHTS`

```python
CONDITION_WEIGHTS = {
    'EMAs': 2.5,           # Critique (tendance)
    'ADX_DI': 2.5,         # Critique (force)
    'MACD': 2.0,           # Fort (momentum)
    'RSI': 1.5,            # Important (momentum)
    'Volume': 1.5,         # Important (confirmation)
    'Bollinger': 0.8,      # Moins fiable (niveau)
    'Pattern': 0.8,        # Moins fiable (structure)
    'Divergence': 1.0      # Bonus
}
```

#### 2.7.2 Calcul du Score

**Formule** :
```python
base_score = sum(CONDITION_WEIGHTS[type] for type in condition_types)
final_score = base_score + trend_bonus + divergence_bonus
```

**Activation** :
```python
TRADING_CONFIG['use_weighted_scoring'] = True
```

#### 2.7.3 Score Minimum Requis

**Configuration** :
```python
TRADING_CONFIG['min_score_required'] = 7.5           # Score de base
TRADING_CONFIG['min_score_adx_high'] = 7.0           # Si ADX > 30
TRADING_CONFIG['min_score_adx_low'] = 8.0            # Si ADX < 25
```

**Logique adaptative** :
- Si `ADX > 30` : `min_score = 7.0` (tendance forte, moins strict)
- Si `ADX < 25` : `min_score = 8.0` (tendance faible, plus strict)
- Sinon : `min_score = 7.5`

**Note** : Si l'utilisateur modifie `min_score_required` (≠ 7.5), cette valeur est utilisée directement sans ajustement ADX.

#### 2.7.4 Bonus Trend

**Calcul** :
```python
if direction == 'LONG' and trend == 'BULLISH':
    trend_bonus = bonus_value / divisor
elif direction == 'SHORT' and trend == 'BEARISH':
    trend_bonus = bonus_value / divisor
```

**Configuration** :
```python
TREND_BONUS_CONFIG = {
    'use_direct_score': True,      # Ajouter directement au score
    'bonus_divisor': 5             # Diviser bonus par 5
}
```

**Trend Data** : Calculé sur timeframe configuré (défaut : 15m)

#### 2.7.5 Bonus Divergence

**Détection** :
- **LONG** : `RSI < RSI_prev` ET `MACD histogram > MACD_prev histogram`
- **SHORT** : `RSI > RSI_prev` ET `MACD histogram < MACD_prev histogram`

**Configuration** :
```python
TRADING_CONFIG['use_divergence'] = True
```

**Poids** : `CONDITION_WEIGHTS['Divergence'] = 1.0`

### 2.8 Filtres de Marché

#### 2.8.1 Filtre Spread

**Fonction** : `check_spread()`

**Rejet si** : `spread > 0.02%` (déjà filtré par scanner)

#### 2.8.2 Filtre Orderbook Imbalance

**Fonction** : `check_orderbook_imbalance()`

**Calcul** :
```python
bid_vol = sum(bids[:5])
ask_vol = sum(asks[:5])
ratio = bid_vol / ask_vol if ask_vol > 0 else 0
```

**Rejet si** :
- **LONG** : `ratio < 1.1` (orderbook défavorable)
- **SHORT** : `ratio > 0.9` (orderbook défavorable)

**Log Level** : INFO (pas WARNING)

### 2.9 Processus d'Analyse

#### 2.9.1 Analyse d'une Paire

**Fonction** : `analyze_pair()`

**Procédure** :
1. Récupérer OHLCV 1m et 5m
2. Calculer indicateurs techniques
3. Détecter patterns de bougies
4. Calculer trend data (timeframe configuré)
5. Générer conditions LONG et SHORT
6. Appliquer filtres de qualité
7. Calculer scores pondérés
8. Appliquer bonus trend et divergence
9. Vérifier score minimum requis
10. Retourner setup valide ou raison de rejet

#### 2.9.2 Scan des Setups

**Déclenchement** : Toutes les 45 secondes (si aucune position active)

**Procédure** :
1. Récupérer top N paires depuis `top_pairs`
2. Analyser en parallèle avec `analyze_pair()`
3. Compter setups valides, rejets, erreurs
4. Sélectionner le meilleur setup (premier valide)
5. Ouvrir position si setup trouvé

**Configuration** :
```python
TRADING_CONFIG['scan_interval'] = 45  # Secondes
```

---

## 3. Système de Gestion des Positions

### 3.1 Vue d'ensemble

Le **PositionManager** gère l'ouverture, le suivi et la fermeture des positions avec :
- Calcul TP/SL (modes FIXE et ATR)
- Break-even automatique
- Trailing stop adaptatif
- TP partiel
- TP Escalier (multi-niveaux)
- Invalidation précoce
- Calcul PnL avec slippage et fees

### 3.2 Modes TP/SL

#### 3.2.1 Mode FIXE

**Configuration** :
```python
TRADING_CONFIG['tp_sl_mode'] = 'FIXE'
TRADING_CONFIG['tp_percent'] = 0.6%                  # Take Profit
TRADING_CONFIG['sl_percent'] = 0.25%                 # Stop Loss
```

**Calcul** :
- **LONG** :
  - `SL = entry × (1 - 0.25%)`
  - `TP = entry × (1 + 0.6%)`
- **SHORT** :
  - `SL = entry × (1 + 0.25%)`
  - `TP = entry × (1 - 0.6%)`

**Précision** :
- Prix < 0.001 : 10 décimales
- Prix < 0.01 : 9 décimales
- Sinon : 8 décimales

#### 3.2.2 Mode ATR

**Configuration** :
```python
TRADING_CONFIG['tp_sl_mode'] = 'ATR'
TRADING_CONFIG['atr_mult_tp'] = 1.5                  # Multiplicateur TP
TRADING_CONFIG['atr_mult_sl'] = 1.0                  # Multiplicateur SL
TRADING_CONFIG['atr_min'] = 0.15%                    # ATR minimum
TRADING_CONFIG['atr_max'] = 1.5%                     # ATR maximum
```

**Calcul** :
```python
# ATR Blended (70% 1m + 30% 5m)
atr_blended = (atr_1m × 0.7) + (atr_5m × 0.3)
atr_percent = (atr_blended / entry) × 100
atr_percent = clamp(atr_percent, atr_min, atr_max)

# TP/SL
if direction == 'LONG':
    SL = entry × (1 - atr_percent% × atr_mult_sl)
    TP = entry × (1 + atr_percent% × atr_mult_tp)
else:
    SL = entry × (1 + atr_percent% × atr_mult_sl)
    TP = entry × (1 - atr_percent% × atr_mult_tp)
```

**Ajustements Dynamiques** :
- **Win streak ≥ 3** : Mode agressif
  - `tp_mult = 4.0`
  - `sl_mult = 1.2`
- **Loss streak ≥ 2** : Mode prudent
  - `tp_mult = 1.5`
  - `sl_mult = 1.2`

### 3.3 Break-Even

#### 3.3.1 Déclenchement

**Configuration** :
```python
TRADING_CONFIG['break_even_trigger'] = 0.3%          # Seuil déclenchement
```

**Logique** :
1. Vérifier si `break_even_set = False` ET `partial_tp_sold = False`
2. Si `PnL ≥ break_even_trigger` :
   - `SL = entry` (break-even)
   - `break_even_set = True`

**Note** : En mode FIXE, `break_even_trigger` est aussi utilisé comme `trigger_pct` pour le TP partiel.

### 3.4 Trailing Stop

#### 3.4.1 Mode FIXE

**Configuration** :
```python
TRADING_CONFIG['trailing_distance'] = 0.15%          # Distance fixe
```

**Logique** :
1. Activer si `partial_tp_sold = True` OU `PnL ≥ break_even_trigger`
2. Calculer nouveau SL :
   - **LONG** : `new_sl = current_price × (1 - trailing_distance%)`
   - **SHORT** : `new_sl = current_price × (1 + trailing_distance%)`
3. Mettre à jour uniquement si favorable (SL monte pour LONG, descend pour SHORT)

**Méthode** : `_update_trailing_stop_fixe()`

#### 3.4.2 Mode ATR (Adaptatif)

**Configuration** :
```python
TRADING_CONFIG['trailing_stop'] = {
    'enabled': True,
    'trigger_pnl': 0.25%,                            # Déclenchement
    'atr_multiplier': 0.4,                           # Distance = ATR × 0.4
    'min_distance': 0.08%,                           # Minimum
    'max_distance': 0.25%                             # Maximum
}
```

**Calcul** :
```python
atr_percent = (ATR / entry) × 100
trailing_distance = atr_percent × atr_multiplier
trailing_distance = clamp(trailing_distance, min_distance, max_distance)

# LONG
new_sl = current_price × (1 - trailing_distance%)
# SHORT
new_sl = current_price × (1 + trailing_distance%)
```

**Méthode** : `TrailingStopManager.update_trailing_stop()`

### 3.5 TP Partiel

#### 3.5.1 Configuration

```python
TRADING_CONFIG['partial_tp_percent'] = 50%           # % de position vendue
```

**Note** : En mode FIXE, le TP partiel utilise `break_even_trigger` comme seuil de déclenchement.

#### 3.5.2 Déclenchement

**Mode FIXE** :
- Seuil : `break_even_trigger` (défaut : 0.3%)
- Vendre : `partial_tp_percent` (défaut : 50%)

**Mode ATR** :
- Seuil : `trigger_pnl` (défaut : 0.25%)
- Vendre : `partial_tp_percent` (défaut : 50%)

#### 3.5.3 Exécution

**Calcul** :
```python
size_sold = size × (partial_tp_percent / 100)
size_remaining = size × (1 - partial_tp_percent / 100)
profit_usdt = size_sold × (profit_pct / 100)
```

**Actions** :
1. Mettre à jour `partial_tp_sold = True`
2. Mettre à jour `size_remaining`
3. Mettre à jour `partial_profit_usdt`
4. Déplacer SL à break-even si pas déjà fait

**Méthode** : `PartialTPManager.execute_partial_tp()`

### 3.6 TP Escalier (Multi-Level TP)

#### 3.6.1 Configuration

**Format Legacy** :
```python
TRADING_CONFIG['tp_escalier'] = {
    'enabled': True,
    'levels': [
        {'pnl': 0.20%, 'size_pct': 0.25, 'move_sl': 'entry'},      # 25% à +0.20%
        {'pnl': 0.35%, 'size_pct': 0.25, 'move_sl': 'breakeven'},  # 25% à +0.35%
        {'pnl': 0.50%, 'size_pct': 0.25, 'move_sl': 'trailing'},   # 25% à +0.50%
        {'pnl': 0.80%, 'size_pct': 0.25, 'move_sl': 'trailing'}     # 25% à +0.80%
    ]
}
```

**Format Individuel** (pour frontend) :
```python
TRADING_CONFIG['escalier_level1_pnl'] = 0.20%
TRADING_CONFIG['escalier_level1_size'] = 25%
TRADING_CONFIG['escalier_level2_pnl'] = 0.35%
TRADING_CONFIG['escalier_level2_size'] = 25%
TRADING_CONFIG['escalier_level3_pnl'] = 0.50%
TRADING_CONFIG['escalier_level3_size'] = 25%
TRADING_CONFIG['escalier_level4_pnl'] = 0.80%
TRADING_CONFIG['escalier_level4_size'] = 25%
```

**Activation** : Automatique si `tp_sl_mode = 'ESCALIER'` ou `'TP_MULTI'`

#### 3.6.2 Exécution

**Procédure** :
1. Vérifier si niveau actuel atteint (prix ≥ TP niveau)
2. Vendre `size_pct` de la position
3. Calculer profit
4. Mettre à jour `tp_escalier_current_level`
5. Mettre à jour `tp_escalier_size_remaining`
6. Ajouter profit à `tp_escalier_profits`
7. Déplacer SL selon `move_sl` :
   - `'entry'` ou `'breakeven'` : `SL = entry`
   - `'trailing'` : Activer trailing stop

**Méthode** : `TPEscalierManager.check_and_execute_levels()`

### 3.7 Invalidation Précoce

#### 3.7.1 Configuration

```python
TRADING_CONFIG['early_invalidation'] = {
    'enabled': True,
    'delay': 10,                                        # Attendre 10s minimum
    'threshold_15s': -0.12%,                           # Seuil 10-15s
    'threshold_30s': -0.08%                            # Seuil 15-30s
}
```

#### 3.7.2 Seuils Adaptatifs

**Configuration** :
```python
TRADING_CONFIG['adaptive_thresholds'] = {
    'enabled': True,
    'early_invalidation': {
        'low_vol_multiplier': 0.7,                     # ATR < 0.3%
        'high_vol_multiplier': 1.3                     # ATR > 0.8%
    }
}
```

**Calcul** :
```python
if elapsed <= 15:
    base_threshold = threshold_15s
else:
    base_threshold = threshold_30s

if ATR% < 0.3:
    multiplier = low_vol_multiplier  # 0.7 (moins strict)
elif ATR% > 0.8:
    multiplier = high_vol_multiplier  # 1.3 (plus strict)
else:
    multiplier = 1.0

adaptive_threshold = base_threshold × multiplier
adaptive_threshold = clamp(adaptive_threshold, -0.15%, -0.05%)
```

**Fermeture si** : `PnL ≤ adaptive_threshold` ET `10s ≤ elapsed ≤ 30s`

**Méthode** : `EarlyInvalidationChecker.check_invalidation()`

### 3.8 Calcul PnL

#### 3.8.1 PnL Brut

**LONG** :
```python
pnl_pct = ((current_price - entry) / entry) × 100
pnl_usdt = size × (pnl_pct / 100)
```

**SHORT** :
```python
pnl_pct = ((entry - current_price) / entry) × 100
pnl_usdt = size × (pnl_pct / 100)
```

#### 3.8.2 Slippage Estimé

**Configuration** :
```python
TRADING_CONFIG['use_slippage_calculation'] = True
```

**Calcul** :
```python
# Données depuis scalability_data
spread_pct = scalability_data['spread_pct']
depth = scalability_data['depth']
balance = scalability_data['balance']

# Estimation
if spread_pct > 0.02:
    slippage_pct = spread_pct × 1.5
elif depth < 100000:
    slippage_pct = spread_pct × 1.2
else:
    slippage_pct = spread_pct × 0.8

slippage_pct = clamp(slippage_pct, 0.01, 0.1)
slippage_usdt = size × (slippage_pct / 100)
```

**Méthode** : `PositionManager._estimate_slippage()`

#### 3.8.3 Fees

**Configuration** :
```python
TRADING_CONFIG['fee_per_trade'] = 0.0004  # 0.04% par trade
```

**Calcul** :
```python
fees_usdt = size × fee_per_trade × 2  # Entrée + sortie
```

#### 3.8.4 PnL Net

```python
gross_pnl_usdt = pnl_usdt
total_costs = fees_usdt + slippage_usdt
net_pnl_usdt = gross_pnl_usdt - total_costs
net_pnl_pct = (net_pnl_usdt / size) × 100
```

### 3.9 Position Sizing

#### 3.9.1 Configuration

```python
TRADING_CONFIG['account_size'] = 1000.0              # Capital total (USDT)
TRADING_CONFIG['risk_per_trade'] = 2.0%             # Risque par trade
```

#### 3.9.2 Calcul Adaptatif

**Base** :
```python
base_risk = risk_per_trade / 100  # 2%
```

**Multiplicateurs Qualité** :
```python
TRADING_CONFIG['position_sizing'] = {
    'base_risk': 0.02,
    'min_risk': 0.005,                               # 0.5%
    'max_risk': 0.03,                                # 3%
    'quality_multipliers': {
        'excellent': 1.4,                            # Score ≥ 12
        'good': 1.2,                                 # Score ≥ 10
        'acceptable': 1.0,                           # Score ≥ 8
        'weak': 0.8                                  # Score < 8
    },
    'streak_multipliers': {
        'win_streak_3+': 1.1,                       # Win streak ≥ 3
        'loss_streak_2+': 0.85                      # Loss streak ≥ 2
    }
}
```

**Calcul** :
```python
quality_mult = quality_multipliers[quality]
streak_mult = streak_multipliers[streak] if streak else 1.0
final_risk = base_risk × quality_mult × streak_mult
final_risk = clamp(final_risk, min_risk, max_risk)

stop_loss_pct = abs((SL - entry) / entry) × 100
position_size = (account_size × final_risk) / (stop_loss_pct / 100)
```

**Méthode** : `PositionManager.calculate_position_size()`

---

## 4. Système de Suivi des Positions

### 4.1 Vue d'ensemble

Le **position_check_loop** vérifie la position active toutes les 0.1 secondes pour :
- Vérifier TP/SL
- Mettre à jour trailing stop
- Exécuter TP partiel/escalier
- Vérifier invalidation précoce
- Émettre mises à jour frontend

### 4.2 Intervalle de Vérification

**Configuration** :
```python
TRADING_CONFIG['check_interval'] = 0.1  # Secondes (ultra-rapide pour scalping)
```

### 4.3 Processus de Vérification

#### 4.3.1 Fonction Principale

**Fonction** : `position_check_loop_callback()`

**Procédure** :
1. Vérifier qu'une position est active
2. Récupérer prix actuel via WebSocket
3. Appeler `position_manager.check_position(current_price)`
4. Si position toujours active : émettre `position_update`
5. Si position fermée : archiver et nettoyer

#### 4.3.2 Méthode check_position()

**Procédure** :
1. **Invalidation précoce** (10-30s) :
   - Vérifier si `PnL ≤ adaptive_threshold`
   - Retourner `'EARLY_INVALIDATION'` si oui
2. **Break-even** (avant 1er TP) :
   - Si `break_even_set = False` ET `PnL ≥ break_even_trigger` :
     - `SL = entry`
     - `break_even_set = True`
3. **TP Partiel** (mode FIXE) :
   - Si `partial_tp_sold = False` ET `PnL ≥ break_even_trigger` :
     - Vendre `partial_tp_percent`
     - Déplacer SL à break-even
4. **TP Escalier** (si activé) :
   - Vérifier chaque niveau
   - Exécuter si prix atteint
5. **Trailing Stop** :
   - Si `partial_tp_sold = True` OU `PnL ≥ break_even_trigger` :
     - Mettre à jour SL selon mode (FIXE ou ATR)
6. **TP/SL** :
   - Vérifier si prix atteint TP ou SL
   - Retourner raison de fermeture si oui

### 4.4 Émission de Mises à Jour

#### 4.4.1 Événement position_update

**Déclenchement** : Toutes les 0.1s si position active

**Données** :
```python
{
    'symbol': 'BTC/USDT:USDT',
    'direction': 'LONG',
    'entry': 45000.0,
    'current_price': 45100.0,
    'sl': 44887.5,
    'tp': 45270.0,
    'pnl': 0.22,                    # %
    'pnl_usdt': 2.2,                # USDT
    'size': 1000.0,
    'opened_at': '2025-01-11T12:00:00',  # ISO format
    'break_even_set': False,
    'partial_tp_sold': False,
    'tp_sl_mode': 'FIXE',
    'dynamic_sl': None,             # SL dynamique (trailing)
    'size_remaining': 1000.0,
    'tp_escalier_levels': '[...]'  # JSON string
}
```

#### 4.4.2 Événement stats_update

**Déclenchement** : Après fermeture de position

**Données** :
```python
{
    'total_trades': 10,
    'wins': 7,
    'losses': 3,
    'total_pnl_usdt': 15.5,         # Net PnL (après fees + slippage)
    'total_pnl_pct': 1.55,          # Net PnL %
    'best_trade': {...},
    'worst_trade': {...},
    'avg_trade_duration': 45.2      # Secondes
}
```

**Calcul** :
- Récupérer trades depuis `analytics_db`
- Utiliser `net_pnl_usdt` et `net_pnl_pct`
- Arrondir à 4 décimales

### 4.5 Fermeture de Position

#### 4.5.1 Raisons de Fermeture

- `'TP_HIT'` : Take Profit atteint
- `'SL_HIT'` : Stop Loss atteint
- `'EARLY_INVALIDATION'` : Invalidation précoce
- `'MANUAL'` : Fermeture manuelle
- `'TIMEOUT'` : Timeout (défaut : 300s)

**Configuration** :
```python
TRADING_CONFIG['position_timeout'] = 300  # Secondes
```

#### 4.5.2 Méthode close_position()

**Procédure** :
1. Calculer PnL brut
2. Estimer slippage
3. Calculer fees
4. Calculer PnL net
5. Archiver dans `analytics_db`
6. Retourner résultat

**Résultat** :
```python
{
    'symbol': 'BTC/USDT:USDT',
    'direction': 'LONG',
    'entry': 45000.0,
    'exit': 45270.0,
    'size': 1000.0,
    'pnl_pct': 0.6,
    'pnl_usdt': 6.0,
    'slippage_pct': 0.02,
    'slippage_usdt': 0.2,
    'fees_usdt': 0.8,
    'gross_pnl_usdt': 6.0,
    'net_pnl_usdt': 5.0,
    'net_pnl_pct': 0.5,
    'duration_seconds': 45,
    'reason': 'TP_HIT',
    'timestamp': 1704974400
}
```

---

## 5. Configuration Complète

### 5.1 Variables Principales

Toutes les variables sont dans `config.py` sous `TRADING_CONFIG`.

### 5.2 Plages de Configuration

#### 5.2.1 TP/SL FIXE

- `tp_percent` : 0.1% - 5.0% (défaut : 0.6%)
- `sl_percent` : 0.1% - 2.0% (défaut : 0.25%)
- `break_even_trigger` : 0.05% - 2.0% (défaut : 0.3%)
- `trailing_distance` : 0.05% - 1.0% (défaut : 0.15%)
- `partial_tp_percent` : 10% - 90% (défaut : 50%)

#### 5.2.2 TP/SL ATR

- `atr_mult_tp` : 0.5 - 5.0 (défaut : 1.5)
- `atr_mult_sl` : 0.5 - 3.0 (défaut : 1.0)
- `atr_min` : 0.05% - 0.5% (défaut : 0.15%)
- `atr_max` : 0.5% - 3.0% (défaut : 1.5%)

#### 5.2.3 Filtres

- `snr_threshold` : 0.1 - 1.0 (défaut : 0.25)
- `breakout_threshold` : 0.1 - 1.0 (défaut : 0.35)
- `wick_ratio_max` : 1.5 - 5.0 (défaut : 2.8)
- `di_gap_min` : 2.0 - 10.0 (défaut : 4.0)
- `volume_multiplier` : 0.1 - 2.0 (défaut : 0.95)

#### 5.2.4 ATR Optimal

- `optimal_atr_min_1m` : 0.05% - 0.3% (défaut : 0.12%)
- `optimal_atr_max_1m` : 0.3% - 1.5% (défaut : 0.75%)
- `optimal_atr_min_5m` : 0.1% - 0.5% (défaut : 0.22%)
- `optimal_atr_max_5m` : 0.5% - 2.5% (défaut : 1.4%)

#### 5.2.5 Scoring

- `min_score_required` : 5.0 - 15.0 (défaut : 7.5)
- `min_score_adx_high` : 5.0 - 12.0 (défaut : 7.0)
- `min_score_adx_low` : 6.0 - 15.0 (défaut : 8.0)

#### 5.2.6 Trailing Stop

- `trigger_pnl` : 0.1% - 1.0% (défaut : 0.25%)
- `atr_multiplier` : 0.1 - 1.0 (défaut : 0.4)
- `min_distance` : 0.05% - 0.3% (défaut : 0.08%)
- `max_distance` : 0.1% - 0.5% (défaut : 0.25%)

#### 5.2.7 Early Invalidation

- `threshold_15s` : -0.2% - -0.05% (défaut : -0.12%)
- `threshold_30s` : -0.15% - -0.03% (défaut : -0.08%)

---

## 6. Notes Techniques

### 6.1 Précision des Prix

- Prix < 0.001 : 10 décimales
- Prix < 0.01 : 9 décimales
- Sinon : 8 décimales

### 6.2 WebSocket

- **URL** : `wss://contract.mexc.com/edge`
- **Ping** : Toutes les 30s
- **Reconnect** : Délai 5s
- **Timeout** : 10s

### 6.3 Base de Données

- **Path** : `data/analytics.db`
- **Tables** : `trades`, `trade_behavior`, `setups_validated`

### 6.4 Logs

- **Format** : `[HH:MM:SS] LEVEL - Message`
- **Couleurs** : ANSI (via colorama)
- **Emojis** : ✅ 📊 ❌ ⚠️ ℹ️ 🔍 💰 🛡️ 🔄

---

**Documentation générée le** : 2025-01-11  
**Version** : Trade Cursor v7.0
