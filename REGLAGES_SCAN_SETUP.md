# ⚙️ RÉGLAGES CONFIGURABLES À LA VOLÉE - SCAN DES SETUPS

**Date**: 2025-01-05  
**Version**: v6.8  
**Statut**: ✅ Documentation complète

---

## 📋 RÉSUMÉ

Ce document explique tous les paramètres configurables **à la volée** (en temps réel) pour le scan des setups. Ces réglages permettent d'adapter la sélectivité et la qualité des setups détectés sans redémarrer l'application.

**Endpoint API** : `POST /api/config`

---

## 🔧 PARAMÈTRES DE FILTRAGE DES SETUPS

### 1. SNR THRESHOLD (Signal-to-Noise Ratio)

#### 📊 Qu'est-ce que c'est ?

Le **SNR (Signal-to-Noise Ratio)** mesure la force du signal par rapport au bruit du marché.

**Formule** :
```
SNR = |Prix - EMA21| / ATR
```

**Signification** :
- **SNR élevé** : Prix éloigné de l'EMA21 → Signal fort (tendance claire)
- **SNR faible** : Prix proche de l'EMA21 → Signal plat (pas de tendance)

#### ⚙️ Configuration

**Paramètre** : `snr_threshold`  
**Type** : Float  
**Plage** : `0.0` à `1.0`  
**Défaut** : `0.3`

**API** :
```json
POST /api/config
{
  "snr_threshold": 0.3
}
```

#### 📈 Impact des valeurs

| Valeur | Comportement | Impact |
|--------|--------------|--------|
| **0.1** | Très permissif | +50% setups acceptés, qualité moindre |
| **0.3** | ✅ Recommandé | Équilibre signal/bruit |
| **0.5** | Stricte | -30% setups, qualité supérieure |
| **0.7** | Très stricte | -60% setups, très haute qualité |

#### 🎯 Recommandations

- **Scalping agressif** : `0.2` - `0.3` (plus d'opportunités)
- **Scalping conservateur** : `0.4` - `0.5` (moins de setups, meilleure qualité)
- **Marché volatil** : `0.3` - `0.4` (ATR élevé, besoin de signal plus fort)
- **Marché calme** : `0.2` - `0.3` (ATR faible, signal plus subtil)

#### 📝 Exemple de log

```
📊 BTC/USDT 1m: SNR | Price: 43250.0 | EMA21: 43180.0 | Diff: 70.0 | 
ATR: 150.0 | SNR: 0.467 | Seuil: 0.3
→ ✅ ACCEPTÉ (0.467 > 0.3)
```

```
❌ ETH/USDT 1m: SNR trop faible: 0.15 < 0.3 (signal plat)
→ ❌ REJETÉ
```

---

### 2. BREAKOUT THRESHOLD

#### 📊 Qu'est-ce que c'est ?

Le **Breakout Threshold** détecte si le prix a effectué un breakout significatif par rapport à l'EMA21.

**Formule** :
```
Breakout Threshold = ATR × breakout_mult
Zone de breakout = EMA21 ± (ATR × breakout_mult)
```

**Validation** :
- Si prix **EN DEHORS** de la zone → ✅ Breakout détecté
- Si prix **DANS** la zone → ❌ Pas de breakout (rejeté)

#### ⚙️ Configuration

**Paramètre** : `breakout_threshold`  
**Type** : Float (multiplicateur ATR)  
**Plage** : `0.0` à `1.0`  
**Défaut** : `0.3`

**API** :
```json
POST /api/config
{
  "breakout_threshold": 0.3
}
```

#### 📈 Impact des valeurs

| Valeur | Zone autour EMA21 | Impact |
|--------|-------------------|--------|
| **0.1** | ±0.1×ATR (très étroite) | Très strict, -40% setups |
| **0.3** | ✅ ±0.3×ATR (équilibrée) | Équilibre recommandé |
| **0.5** | ±0.5×ATR (large) | Permissif, +30% setups |
| **0.8** | ±0.8×ATR (très large) | Très permissif, +60% setups |

#### 🎯 Recommandations

- **Tendances fortes** : `0.2` - `0.3` (breakouts clairs)
- **Marché range** : `0.4` - `0.5` (breakouts plus subtils)
- **Scalping agressif** : `0.3` - `0.4` (plus d'opportunités)
- **Scalping conservateur** : `0.2` - `0.3` (breakouts évidents)

#### 📝 Exemple de log

```
ATR: 150.0 | Breakout threshold: 45.0 (0.3 × 150)
EMA21: 43180.0
Zone: 43135.0 - 43225.0
Prix actuel: 43250.0
→ ✅ ACCEPTÉ (prix en dehors de la zone)
```

```
❌ SOL/USDT 1m: Pas de breakout: prix dans range ±ATR*0.3 autour de EMA21
→ ❌ REJETÉ
```

---

### 3. WICK RATIO MAX

#### 📊 Qu'est-ce que c'est ?

Le **Wick Ratio** détecte les bougies avec des mèches (wicks) suspectes, indicateur de manipulation ou de rejet.

**Formule** :
```
Wick Ratio = (High - Low) / |Open - Close|
```

**Signification** :
- **Ratio élevé** : Mèches très longues par rapport au corps → Manipulation possible
- **Ratio faible** : Corps dominant → Bougie normale

#### ⚙️ Configuration

**Paramètre** : `wick_ratio_max`  
**Type** : Float  
**Plage** : `1.0` à `10.0`  
**Défaut** : `2.5`

**API** :
```json
POST /api/config
{
  "wick_ratio_max": 2.5
}
```

#### 📈 Impact des valeurs

| Valeur | Tolérance | Impact |
|--------|-----------|--------|
| **1.5** | Très stricte | Rejette beaucoup de bougies, -40% setups |
| **2.5** | ✅ Recommandé | Équilibre manipulation/détection |
| **4.0** | Permissive | +30% setups, risque manipulation |
| **6.0** | Très permissive | +60% setups, manipulation probable |

#### 🎯 Recommandations

- **Marché normal** : `2.5` - `3.0` (détection équilibrée)
- **Marché volatil** : `3.0` - `4.0` (wicks normaux en volatilité)
- **Protection manipulation** : `2.0` - `2.5` (stricte)
- **Scalping agressif** : `3.0` - `4.0` (plus permissif)

#### 📝 Exemple de log

```
Bougie: Open=43200, Close=43250, High=43300, Low=43150
Corps: 50 | Range: 150 | Ratio: 3.0
Seuil: 2.5
→ ❌ REJETÉ (3.0 > 2.5 - wicks suspects)
```

```
Bougie: Open=43200, Close=43250, High=43270, Low=43190
Corps: 50 | Range: 80 | Ratio: 1.6
Seuil: 2.5
→ ✅ ACCEPTÉ (1.6 < 2.5)
```

---

### 4. DI GAP MIN

#### 📊 Qu'est-ce que c'est ?

Le **DI Gap** mesure l'écart entre DI+ et DI- (Directional Indicators), indicateur de la force directionnelle.

**Formule** :
```
DI Gap = |DI+ - DI-|
```

**Condition** :
- Si `ADX > di_gap_adx_threshold` ET `DI Gap > di_gap_min` → Condition ADX valide
- Sinon → Condition ADX standard (ADX > 30)

#### ⚙️ Configuration

**Paramètre** : `di_gap_min`  
**Type** : Float  
**Plage** : `0.0` à `50.0`  
**Défaut** : `5.0`

**API** :
```json
POST /api/config
{
  "di_gap_min": 5.0
}
```

#### 📈 Impact des valeurs

| Valeur | Exigence | Impact |
|--------|----------|--------|
| **2.0** | Permissive | +20% conditions ADX, qualité variable |
| **5.0** | ✅ Recommandé | Équilibre force/opportunités |
| **8.0** | Stricte | -30% conditions ADX, haute qualité |
| **12.0** | Très stricte | -50% conditions ADX, très haute qualité |

#### 🎯 Recommandations

- **Tendances fortes** : `5.0` - `8.0` (gaps importants)
- **Tendances faibles** : `3.0` - `5.0` (gaps plus petits)
- **Scalping conservateur** : `6.0` - `8.0` (force directionnelle élevée)
- **Scalping agressif** : `3.0` - `5.0` (plus d'opportunités)

#### 📝 Exemple de log

```
ADX: 28.5 | DI+: 18.0 | DI-: 12.0 | Gap: 6.0
Seuil: 5.0 | ADX threshold: 25
→ ✅ Condition ADX valide (Gap 6.0 > 5.0)
```

```
ADX: 30.0 | DI+: 16.0 | DI-: 14.0 | Gap: 2.0
Seuil: 5.0
→ ❌ Gap insuffisant (2.0 < 5.0) → Utilise condition standard ADX > 30
```

---

### 5. DI GAP ADX THRESHOLD

#### 📊 Qu'est-ce que c'est ?

Le **DI Gap ADX Threshold** détermine le niveau d'ADX minimum requis pour activer la condition DI Gap (au lieu de la condition ADX standard).

**Logique** :
- Si `ADX > di_gap_adx_threshold` ET `DI Gap > di_gap_min` → Condition ADX avec DI Gap
- Sinon → Condition ADX standard (`ADX > 30`)

#### ⚙️ Configuration

**Paramètre** : `di_gap_adx_threshold`  
**Type** : Float  
**Plage** : `0.0` à `100.0`  
**Défaut** : `25.0`

**API** :
```json
POST /api/config
{
  "di_gap_adx_threshold": 25.0
}
```

#### 📈 Impact des valeurs

| Valeur | Activation | Impact |
|--------|------------|--------|
| **20** | Plus facile | +15% conditions ADX |
| **25** | ✅ Recommandé | Équilibre |
| **30** | Plus strict | -20% conditions ADX |
| **35** | Très strict | -40% conditions ADX |

#### 🎯 Recommandations

- **Marché normal** : `25` - `30` (activation modérée)
- **Marché volatil** : `20` - `25` (activation plus facile)
- **Marché calme** : `25` - `30` (activation plus stricte)

---

### 6. OPTIMAL ATR (1m et 5m)

#### 📊 Qu'est-ce que c'est ?

Les **seuils ATR optimaux** filtrent les paires selon leur volatilité (ATR en %).

**Filtre** :
- Si `ATR% < optimal_atr_min` → Rejeté (trop calme)
- Si `ATR% > optimal_atr_max` → Rejeté (trop volatil)
- Si `optimal_atr_min ≤ ATR% ≤ optimal_atr_max` → ✅ Accepté

#### ⚙️ Configuration

**Paramètres** :
- `optimal_atr_min_1m` : ATR minimum pour 1m (défaut: `0.10%`)
- `optimal_atr_max_1m` : ATR maximum pour 1m (défaut: `0.8%`)
- `optimal_atr_min_5m` : ATR minimum pour 5m (défaut: `0.20%`)
- `optimal_atr_max_5m` : ATR maximum pour 5m (défaut: `1.5%`)

**API** :
```json
POST /api/config
{
  "optimal_atr_min_1m": 0.10,
  "optimal_atr_max_1m": 0.8,
  "optimal_atr_min_5m": 0.20,
  "optimal_atr_max_5m": 1.5
}
```

#### 📈 Impact des valeurs

**1m (Timeframe court)** :

| Min | Max | Comportement | Impact |
|-----|-----|--------------|--------|
| **0.05** | **1.0** | Très permissif | +40% setups acceptés |
| **0.10** | **0.8** | ✅ Recommandé | Équilibre volatilité |
| **0.15** | **0.6** | Stricte | -30% setups, qualité supérieure |
| **0.20** | **0.5** | Très stricte | -50% setups, très haute qualité |

**5m (Timeframe moyen)** :

| Min | Max | Comportement | Impact |
|-----|-----|--------------|--------|
| **0.15** | **2.0** | Très permissif | +50% setups acceptés |
| **0.20** | **1.5** | ✅ Recommandé | Équilibre volatilité |
| **0.30** | **1.2** | Stricte | -40% setups, qualité supérieure |

#### 🎯 Recommandations

**1m** :
- **Scalping agressif** : `0.08` - `1.0` (plus d'opportunités)
- **Scalping normal** : `0.10` - `0.8` (équilibré)
- **Scalping conservateur** : `0.15` - `0.6` (haute qualité)

**5m** :
- **Scalping agressif** : `0.15` - `2.0` (plus d'opportunités)
- **Scalping normal** : `0.20` - `1.5` (équilibré)
- **Scalping conservateur** : `0.30` - `1.2` (haute qualité)

#### 📝 Exemple de log

```
ATR: 0.15% | Seuil min: 0.10% | Seuil max: 0.8%
→ ✅ ACCEPTÉ (0.10% ≤ 0.15% ≤ 0.8%)
```

```
ATR: 0.05% | Seuil min: 0.10% | Seuil max: 0.8%
→ ❌ REJETÉ (0.05% < 0.10% - trop calme)
```

```
ATR: 1.2% | Seuil min: 0.10% | Seuil max: 0.8%
→ ❌ REJETÉ (1.2% > 0.8% - trop volatil)
```

---

### 7. VOLUME MULTIPLIER

#### 📊 Qu'est-ce que c'est ?

Le **Volume Multiplier** ajuste le seuil minimum de volume requis pour valider un setup.

**Formule** :
```
Min Volume Ratio = Base Min Vol × Volume Multiplier
```

**Base Min Vol** (adaptatif selon ATR) :
- Si `ATR% > 1.0%` → `1.0x`
- Si `ATR% < 0.3%` → `0.6x`
- Sinon → `0.8x`

**Final** :
```
Min Volume Ratio = Base × Volume Multiplier
Clamp: 0.4x - 1.5x
```

#### ⚙️ Configuration

**Paramètre** : `volume_multiplier`  
**Type** : Float  
**Plage** : `0.1` à `2.0`  
**Défaut** : `1.0`

**API** :
```json
POST /api/config
{
  "volume_multiplier": 1.0
}
```

#### 📈 Impact des valeurs

| Valeur | Multiplicateur | Impact |
|--------|----------------|--------|
| **0.5** | Réduit de 50% | +60% setups acceptés, qualité moindre |
| **1.0** | ✅ Normal | Équilibre volume/opportunités |
| **1.5** | Augmente de 50% | -40% setups, qualité supérieure |
| **2.0** | Double | -60% setups, très haute qualité |

#### 🎯 Recommandations

- **Marché faible volume** : `0.7` - `0.9` (plus permissif)
- **Marché normal** : `1.0` (équilibré)
- **Marché fort volume** : `1.2` - `1.5` (stricte, qualité élevée)
- **Scalping agressif** : `0.8` - `1.0` (plus d'opportunités)

#### 📝 Exemple de log

```
ATR%: 0.5% | Base min vol: 0.8x | Volume multiplier: 1.0
Min requis: 0.8x | Vol actuel: 1.2x
→ ✅ ACCEPTÉ (1.2x > 0.8x)
```

```
Volume multiplier: 1.5
Base min vol: 0.8x | Min requis: 1.2x (0.8 × 1.5)
Vol actuel: 1.0x
→ ❌ REJETÉ (1.0x < 1.2x)
```

---

## 🎛️ PARAMÈTRES DE SCORE ET CONDITIONS

### 8. MIN SCORE REQUIRED

#### 📊 Qu'est-ce que c'est ?

Le **Score Minimum Requis** détermine le score pondéré minimum pour valider un setup.

**Système de score pondéré** :
- Chaque condition a un poids (EMAs: 2.5, ADX_DI: 2.5, MACD: 2.0, etc.)
- Score total = Somme des poids des conditions détectées
- Si `Score ≥ Min Score Required` → ✅ Setup valide

#### ⚙️ Configuration

**Paramètres** :
- `min_score_required` : Score minimum standard (défaut: `7.5`)
- `min_score_adx_high` : Si ADX > 30 (défaut: `7.0`)
- `min_score_adx_low` : Si ADX < 25 (défaut: `8.0`)

**API** :
```json
POST /api/config
{
  "min_score_required": 7.5,
  "min_score_adx_high": 7.0,
  "min_score_adx_low": 8.0
}
```

#### 📈 Impact des valeurs

| Score Min | Sélectivité | Impact |
|-----------|-------------|--------|
| **6.0** | Permissive | +40% setups acceptés |
| **7.5** | ✅ Recommandé | Équilibre qualité/opportunités |
| **9.0** | Stricte | -35% setups, qualité supérieure |
| **10.5** | Très stricte | -50% setups, très haute qualité |

#### 🎯 Recommandations

- **Scalping agressif** : `6.5` - `7.5` (plus d'opportunités)
- **Scalping normal** : `7.5` - `8.5` (équilibré)
- **Scalping conservateur** : `9.0` - `10.0` (haute qualité)

---

## 🔄 AUTRES PARAMÈTRES CONFIGURABLES

### 9. CONFLUENCE

**Paramètre** : `use_confluence`  
**Type** : Boolean  
**Défaut** : `false`

**Comportement** :
- `false` : 1m **OU** 5m suffit (mode permissif)
- `true` : 1m **ET** 5m requis (mode strict)

**API** :
```json
POST /api/config
{
  "use_confluence": false
}
```

**Impact** :
- `false` : ~30-40 trades/jour
- `true` : ~15-20 trades/jour (winrate +5-7%)

---

### 10. TP/SL MODE

**Paramètre** : `tp_sl_mode`  
**Type** : String  
**Valeurs** : `"FIXE"`, `"ATR"`, `"TP_MULTI"`  
**Défaut** : `"FIXE"`

**API** :
```json
POST /api/config
{
  "tp_sl_mode": "FIXE"
}
```

---

### 11. TP/SL PERCENT

**Paramètres** :
- `tp_percent` : Take Profit en % (défaut: `0.6`)
- `sl_percent` : Stop Loss en % (défaut: `0.25`)

**API** :
```json
POST /api/config
{
  "tp_percent": 0.6,
  "sl_percent": 0.25
}
```

---

## 📝 EXEMPLE COMPLET D'UTILISATION

### Configuration recommandée pour scalping agressif

```json
POST /api/config
{
  "snr_threshold": 0.2,
  "breakout_threshold": 0.4,
  "wick_ratio_max": 3.0,
  "di_gap_min": 3.0,
  "di_gap_adx_threshold": 20,
  "optimal_atr_min_1m": 0.08,
  "optimal_atr_max_1m": 1.0,
  "optimal_atr_min_5m": 0.15,
  "optimal_atr_max_5m": 2.0,
  "volume_multiplier": 0.8,
  "min_score_required": 6.5,
  "use_confluence": false
}
```

**Impact attendu** : +50-70% setups acceptés, qualité légèrement inférieure

---

### Configuration recommandée pour scalping conservateur

```json
POST /api/config
{
  "snr_threshold": 0.4,
  "breakout_threshold": 0.2,
  "wick_ratio_max": 2.0,
  "di_gap_min": 8.0,
  "di_gap_adx_threshold": 30,
  "optimal_atr_min_1m": 0.15,
  "optimal_atr_max_1m": 0.6,
  "optimal_atr_min_5m": 0.30,
  "optimal_atr_max_5m": 1.2,
  "volume_multiplier": 1.2,
  "min_score_required": 9.0,
  "use_confluence": true
}
```

**Impact attendu** : -40-50% setups acceptés, qualité supérieure (+5-7% winrate)

---

## ⚠️ RECOMMANDATIONS IMPORTANTES

### 1. Ajustement progressif

**Ne pas modifier tous les paramètres en même temps** :
- Modifier 1-2 paramètres à la fois
- Tester pendant 50-100 trades
- Analyser impact (winrate, nombre de trades)
- Ajuster selon résultats

### 2. Monitoring

**Surveiller les logs** :
- Vérifier les raisons de rejet
- Identifier les paramètres trop stricts
- Ajuster les seuils qui rejettent trop

### 3. Cohérence

**Maintenir la cohérence** :
- Si `snr_threshold` bas → `min_score_required` peut être bas
- Si `volume_multiplier` bas → Peut compenser avec `min_score_required` haut
- Si `use_confluence` true → Peut réduire `min_score_required`

### 4. Conditions de marché

**Adapter selon marché** :
- **Marché volatil** : Augmenter `optimal_atr_max`, réduire `snr_threshold`
- **Marché calme** : Réduire `optimal_atr_min`, augmenter `snr_threshold`
- **Marché range** : Augmenter `breakout_threshold`

---

## 📊 RÉSUMÉ DES PLAGES RECOMMANDÉES

| Paramètre | Min | Max | Recommandé | Impact |
|-----------|-----|-----|------------|--------|
| **snr_threshold** | 0.1 | 0.7 | 0.3 | Signal vs Bruit |
| **breakout_threshold** | 0.1 | 0.8 | 0.3 | Breakout detection |
| **wick_ratio_max** | 1.5 | 6.0 | 2.5 | Manipulation filter |
| **di_gap_min** | 2.0 | 12.0 | 5.0 | Directional force |
| **di_gap_adx_threshold** | 20 | 35 | 25 | ADX activation |
| **optimal_atr_min_1m** | 0.05 | 0.20 | 0.10 | Volatility min 1m |
| **optimal_atr_max_1m** | 0.6 | 1.0 | 0.8 | Volatility max 1m |
| **optimal_atr_min_5m** | 0.15 | 0.30 | 0.20 | Volatility min 5m |
| **optimal_atr_max_5m** | 1.2 | 2.0 | 1.5 | Volatility max 5m |
| **volume_multiplier** | 0.5 | 2.0 | 1.0 | Volume requirement |
| **min_score_required** | 6.0 | 10.0 | 7.5 | Setup quality |

---

## ✅ CONCLUSION

Ces paramètres permettent un **contrôle fin** de la sélectivité des setups. L'ajustement doit être **progressif** et **basé sur les résultats** observés.

**Recommandation finale** : Commencer avec les valeurs par défaut, puis ajuster progressivement selon vos besoins et les conditions de marché.

---

## 📚 RÉFÉRENCES

- **Configuration** : `config.py`
- **Implémentation** : `core/analyzer.py`
- **API Endpoint** : `POST /api/config` dans `main.py`
- **Documentation Phase 6.1** : `AMELIORATIONS_PHASE_6_1.md`

